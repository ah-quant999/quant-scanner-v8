# -*- coding: utf-8 -*-
"""
因子实验室 全量生成器（小九本机 baostock 定时刷新用 · 稳定版，随仓库 v8/ 提交）

  - 异常换手率(缩量=多)：重点池(持仓+候选+黄金) 当月换手率 ÷ 过去12月均值，因子 = -abn
  - ROE(TTM) 全市场主板大市值档：sh.60/sz.00 主板，近4季 roeAvg 求和；
    大市值档 = 成交额代理 Top1/3；按 ROE_TTM 降序 Top30

输出：
  raw_data/factor_lab.json + data/FACTOR_LAB.js (window.FACTOR_LAB)
同一进程内原子 commit + fetch + rebase + push（防止 Nutstore 回退插针）。

数据源：baostock。断点续跑：缓存默认存 raw_data/flab_work（随 git 提交，云端/双机共享热缓存）；
本机可用环境变量 V8_FLAB_WORK 指到仓库外。2026-09-04 云端适配：REPO/WORK 自适应 + 链内跳过自带推送。
"""
import baostock as bs, json, time, datetime as dt, re, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自适应：本机 E:/workspace/stock-scanner = 云端 checkout 根（2026-09-04 云端适配，根治硬编码路径致云端必挂）
# 缓存目录：默认仓库内 raw_data/flab_work（随 git 提交 → 云端/双机共享热缓存，冷启动逐晚收敛）；
# 本机想放仓库外可用环境变量 V8_FLAB_WORK 覆盖
WORK = os.environ.get("V8_FLAB_WORK") or os.path.join(REPO, "raw_data", "flab_work")
if not os.path.exists(WORK):
    os.makedirs(WORK, exist_ok=True)
OUT_JSON = os.path.join(REPO, "raw_data", "factor_lab.json")
OUT_JS   = os.path.join(REPO, "data", "FACTOR_LAB.js")
CACHE_A  = os.path.join(WORK, "flab_abn_cache.json")   # 异常换手率(重点池)
CACHE_R  = os.path.join(WORK, "flab_roe_cache.json")   # ROE 全市场主板
KL_ABN_START = "2025-06-01"
KL_AMT_START = "2026-06-01"

def last_trade_day(ref=None):
    """取 ref 的上一交易日（仅处理周末，节假日极少落在周六运行，后续可接 holiday 表）"""
    d = ref or dt.datetime.now()
    # 若 d 是 datetime，先转成 date
    if isinstance(d, dt.datetime):
        d = d.date()
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= dt.timedelta(days=1)
    return d.strftime("%Y-%m-%d")

KL_END   = last_trade_day()                        # 动态到上一交易日（根治周末 query_all_stock 返回 0 只）
ASOF_YM  = KL_END[:7]                              # abn 因子按月刷新标记（ym() 同格式）
ASOF_Q   = "%dQ%d" % (int(KL_END[:4]), (int(KL_END[5:7]) - 1) // 3 + 1)  # ROE 按季刷新标记
# ROE 因子取近 7 年（含当前年），动态滑动——根治硬编码 2025-2027 在 2027-01-01 起的冻结
ROE_YEARS = list(range(max(2015, dt.datetime.now().year - 6), dt.datetime.now().year + 1))
ROE_QTRS  = (1, 2, 3, 4)
FORCE = "--force" in " ".join(sys.argv)

def log(*a):
    s = "[flabgen] " + " ".join(str(x) for x in a)
    print(s, flush=True)
def mean(x): return sum(x)/len(x) if x else 0.0
def ym(d): return d[:7]

def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return r.returncode, r.stdout

def load_cache(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}

def save_cache(recs, p):
    try:
        json.dump(recs, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        log("cache save err", e)

def _load_js_codes(path):
    try:
        t = open(path, encoding="utf-8").read()
        m = re.search(r"window\.\w+\s*=\s*", t)
        if not m: return []
        txt = t[m.end():]
        d = json.loads(txt.rstrip().rstrip(";"))
        codes = set()
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(k, str) and re.fullmatch(r"(sh|sz|bj)[._]\d{6}", k):
                        codes.add(k.replace("_", "."))
                    if isinstance(v, (dict, list)): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(d)
        return codes
    except Exception as e:
        log("读失败", path, e); return []

def get_key_codes():
    files = [os.path.join(REPO, "data", f) for f in
             ("PORTFOLIO.js", "CANDIDATE.js", "GOLD_POOL.js")]
    codes = set()
    for f in files:
        for c in _load_js_codes(f):
            codes.add(c)
    return sorted(codes)

def get_main_universe():
    rs = bs.query_all_stock(day=KL_END)
    codes = {}
    while rs.error_code == '0' and rs.next():
        v = rs.get_row_data()
        if re.match(r'^(sh\.60|sz\.00)\d{4}$', v[0]):
            codes[v[0]] = True
    return sorted(codes.keys())

def get_kline_abn(code):
    rs = bs.query_history_k_data_plus(code,
        "date,close,turn,amount", start_date=KL_ABN_START, end_date=KL_END,
        frequency="d", adjustflag="2")
    rows = []
    while rs.error_code == '0' and rs.next():
        d = rs.get_row_data()
        try:
            rows.append({"date": d[0], "close": float(d[1]),
                "turn": float(d[2]) if d[2] not in ("", "None") else 0.0,
                "amount": float(d[3]) if d[3] not in ("", "None") else 0.0})
        except Exception:
            pass
    return rows

def get_kline_amt(code):
    rs = bs.query_history_k_data_plus(code,
        "date,close,amount", start_date=KL_AMT_START, end_date=KL_END,
        frequency="d", adjustflag="2")
    amts, last = [], None
    while rs.error_code == '0' and rs.next():
        d = rs.get_row_data()
        try:
            if d[2] not in ("", "None"): amts.append(float(d[2]))
            if d[1] not in ("", "None"): last = float(d[1])
        except Exception:
            pass
    return (sum(amts)/len(amts) if amts else 0.0), last

def get_roe_ttm(code):
    series = {}
    for y in ROE_YEARS:
        for q in ROE_QTRS:
            rp = bs.query_profit_data(code, year=y, quarter=q)
            while rp.error_code == '0' and rp.next():
                v = rp.get_row_data()
                try:
                    if len(v) > 3 and v[3] not in ("", "None"):
                        series[f"{y}{q:02d}"] = float(v[3])
                except Exception:
                    pass
            time.sleep(0.02)
    order = sorted(series.keys())
    if len(order) < 4:
        return None
    return sum(series[order[i]] for i in range(len(order)-4, len(order)))

def get_name(code):
    try:
        rs = bs.query_stock_basic(code=code)
        while rs.error_code == '0' and rs.next():
            v = rs.get_row_data()
            if len(v) > 1 and v[1]:
                return v[1]
    except Exception:
        pass
    return ""

def main():
    lg = bs.login(); log("login", lg.error_code)

    # ---- 异常换手率（重点池） ----
    kcodes = get_key_codes(); log("重点池", len(kcodes))
    a = load_cache(CACHE_A)
    for i, code in enumerate(kcodes):
        # 🛡 2026-09-04：按月刷新（asof_ym 标记）——旧版「算过即永久跳过」导致因子冻结在计算当月
        if (not FORCE) and code in a and a[code].get("factor_at") is not None and a[code].get("asof_ym") == ASOF_YM:
            continue
        name = get_name(code)
        kl = get_kline_abn(code)
        agg = {}
        for r in kl:
            x = agg.setdefault(ym(r["date"]), {"t": 0.0, "a": 0.0})
            x["t"] += r["turn"]; x["a"] += r["amount"]
        months = sorted(agg)
        factor_at = None; abn = None
        if len(months) >= 7:
            cur = months[-1]
            hist = [agg[m]["t"] for m in months[:-1]]
            trailing = mean(hist[-12:]) if len(hist) >= 12 else mean(hist)
            if trailing > 0:
                abn = agg[cur]["t"] / trailing
                factor_at = -abn
        size = mean([agg[m]["a"] for m in months]) if months else 0.0
        last = kl[-1]["close"] if kl else None
        a[code] = {
            "code": code, "name": name, "close": last,
            "abn": round(abn, 3) if abn is not None else None,
            "factor_at": round(factor_at, 4) if factor_at is not None else None,
            "roe_ttm": a[code].get("roe_ttm") if code in a else None,
            "size_proxy": round(size, 1) if size else 0.0,
            "asof_ym": ASOF_YM,
        }
        if (i+1) % 25 == 0:
            save_cache(a, CACHE_A)
            log("abn 进度", i+1, "/", len(kcodes))
        if i > 0 and i % 100 == 0:
            try: bs.logout()
            except Exception: pass
            time.sleep(1)
            lg = bs.login(); log("自动重登录 abn", lg.error_code, "at", i)
        time.sleep(0.02)
    save_cache(a, CACHE_A)
    at_valid = [r for r in a.values() if r["factor_at"] is not None]
    at_valid.sort(key=lambda r: r["factor_at"], reverse=True)
    at_top = at_valid[:30]
    at_bottom = at_valid[-10:][::-1]
    log("异常换手率有效", len(at_valid))

    # ---- ROE 全市场主板 ----
    mcodes = get_main_universe(); log("主板 universe", len(mcodes))
    if len(mcodes) < 1000:
        log("ERROR: 主板 universe 异常过少（" + str(len(mcodes)) + "），中止推送，避免空 ROE 数据上线")
        bs.logout(); return
    r = load_cache(CACHE_R)
    for i, code in enumerate(mcodes):
        # 🛡 2026-09-04：按季刷新（asof_q 标记）——季报披露后下一季度自动重算
        if (not FORCE) and code in r and r[code].get("roe_ttm") is not None and r[code].get("size_proxy") and r[code].get("asof_q") == ASOF_Q:
            continue
        name = get_name(code)
        amt, last = get_kline_amt(code)
        roe = get_roe_ttm(code)
        r[code] = {
            "code": code, "name": name,
            "close": round(last, 2) if last is not None else None,
            "roe_ttm": round(roe, 2) if roe is not None else None,
            "size_proxy": round(amt, 1) if amt else 0.0,
            "asof_q": ASOF_Q,
        }
        if (i+1) % 25 == 0:
            save_cache(r, CACHE_R)
            log("roe 进度", i+1, "/", len(mcodes),
                "有效", len([1 for v in r.values() if v.get('roe_ttm') is not None]))
        if i > 0 and i % 200 == 0:
            try: bs.logout()
            except Exception: pass
            time.sleep(1)
            lg = bs.login(); log("自动重登录 roe", lg.error_code, "at", i)
        time.sleep(0.02)
    save_cache(r, CACHE_R)
    valid = [v for v in r.values() if v.get("roe_ttm") is not None and v.get("size_proxy")]
    valid.sort(key=lambda x: x["size_proxy"], reverse=True)
    n = len(valid)
    large = valid[:max(1, n//3)]
    large.sort(key=lambda x: x["roe_ttm"], reverse=True)
    top30 = large[:30]
    log("全市场有效", n, "大市值档", len(large), "Top30首只", top30[0]["code"] if top30 else "无")

    if len(at_valid) < 10 or len(large) < 10:
        log("ERROR: 有效样本不足（abn=" + str(len(at_valid)) + ", roe_large=" + str(len(large)) + "），中止推送")
        bs.logout(); return

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "meta": {
            "universe": "重点池(持仓+候选+黄金)·异常换手率 / 全市场主板·ROE",
            "n_universe": len(kcodes),
            "n_at_valid": len(at_valid),
            "n_roe_large": len(large),
            "abnormal_def": "当月换手率÷过去12月均值; 缩量=因子高=强势",
            "roe_def": "全市场主板(3193)·大市值档(成交额代理top1/3)按ROE_TTM降序 Top30",
            "roe_universe": "全市场主板",
        },
        "abnormal_turnover": {"top": at_top, "bottom": at_bottom},
        "roe_largecap": {"top": top30},
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    js = "window.FACTOR_LAB = " + json.dumps(out, ensure_ascii=False) + ";\n"
    open(OUT_JS, "w", encoding="utf-8").write(js)

    # 更新 index.html 的 ?v 缓存戳 + 强制 ROE 段文案为全市场主板口径
    # ===== 同一进程内原子提交推送（仅本机 standalone 模式；链内由 run_algorithms 统一提交，防双推插针） =====
    if os.environ.get("V8_IN_CHAIN") == "1":
        log("链内模式(V8_IN_CHAIN=1)：跳过自带 ?v 改写与 git 推送（链尾 update_v8 统一重戳 ?v + 推送）")
        bs.logout()
        log("DONE(in-chain)")
        return
    try:
        import hashlib
        h = hashlib.sha1(js.encode("utf-8")).hexdigest()[:10]
        hp = os.path.join(REPO, "index.html")
        html = open(hp, encoding="utf-8").read()
        html = html.replace(
            "② ROE(TTM) 大市值档（成交额代理 Top1/3）— Top 30",
            "② ROE(TTM) 全市场主板·大市值档（成交额代理 Top1/3）— Top 30")
        html = html.replace(
            "注：重点池60%为双创，ROE大市值档样本偏薄，仅作观察。",
            "已切换为全市场主板(3193只)·大市值档(成交额top1/3)。")
        new_html = re.sub(r"data/FACTOR_LAB\.js\?v=[0-9a-f]{10}", "data/FACTOR_LAB.js?v=" + h, html)
        open(hp, "w", encoding="utf-8").write(new_html)
        log("?v ->", h)
    except Exception as e:
        log("?v 更新失败", e)

    # ===== 同一进程内原子提交推送 =====
    rc, o = git("add", "index.html", "data/FACTOR_LAB.js", "raw_data/factor_lab.json")
    log("git add rc=", rc)
    if rc != 0:
        log("git add 失败", o[-300:]); bs.logout(); return
    rc, o = git("commit", "-m",
        "chore(v8): 因子实验室定时刷新(异常换手率重点池 + ROE全市场主板)")
    log("git commit rc=", rc, (o[-400:] if o else ""))
    rc, o = git("fetch", "origin", "main")
    log("git fetch rc=", rc)
    rc, o = git("rebase", "FETCH_HEAD")
    if rc != 0:
        log("rebase 失败 -> abort"); git("rebase", "--abort")
    else:
        log("rebase ok")
    rc, o = git("push", "origin", "HEAD:refs/heads/main")
    log("git push rc=", rc, (o[-500:] if o else ""))
    rc, o = git("ls-remote", "origin", "main")
    log("ls-remote main =>", (o.strip() if o else "NONE"))
    bs.logout()
    log("DONE")

if __name__ == "__main__":
    main()
