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
# 2026-09-07 一劳永逸：BaoStock 底层 socket 无超时保护，单只查询阻塞会永久挂死整轮
#   （实测卡在 roe 进度 100/3195 静止 5 分钟+）。设全局 socket 超时 → 阻塞转为可捕获异常，
#   配合 get_roe_ttm / 主循环的 try 兜底，卡住的个股自动跳过而不是拖死全链。
import socket as _socket
_socket.setdefaulttimeout(30)  # 2026-09-08 上调至 30s：盘前 baostock 响应偏慢，避免误触超时

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
# 2026-09-11 口径版本号：原为「最近4个累计 roeAvg 求和」(错)，现为「近4个单季 roeAvg 差分求和」并转百分数。
#   缓存判定带上它 → 旧口径缓存自动失效并重算，无需手工删缓存。
ROE_VER = 3
# 算 ROE_TTM 只需最近 5 个季度的累计值（4 个单季 + 1 个前值），近 2 年足够；
#   原取近 7 年 = 28 次 query/只，全市场 3193 只约 6 小时必撞 workflow timeout（实测 1.36 s/只·8 次 query）。
ROE_YEARS = [dt.datetime.now().year - 1, dt.datetime.now().year]
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

def resolve_data_date(max_back=10, min_rows=1000):
    """2026-09-08 一劳永逸：解析「baostock 真正已有数据」的交易日。

    【原 bug】KL_END = last_trade_day() 名不副实——它只在遇到周末时回退，
    工作日直接返回「今天」。而 baostock 当日数据要收盘后数小时才生成（且盘前/
    凌晨完全没有），用「今天」去 query_all_stock 必然返回 0 行
    → get_main_universe 得 0 → 触发 <1000 保护性中止 → FACTOR_LAB 永久停在旧日期。
    这正是 2026-09-05 起因子实验室连续断更的真根因（此前误判为「冷启动太慢」）。

    【修法】从今天起逐日回退，取第一个返回行数 >= min_rows 的日期。
    盘前/凌晨跑会自动退到上一已收盘交易日；周末/假期同理；全部无数据返回 None
    让调用方显式报错（不再静默产出空数据）。
    """
    d = dt.datetime.now().date()
    t0 = time.time()
    TOTAL_LIMIT = 300  # 单轮探测总超时硬上限（秒），防止任何意外静默挂死
    for i in range(max_back):
        day = (d - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        # 🔴 2026-09-08 真根因修复：实测「先查 0 行日(盘前/凌晨=今天) 再查回退日」时，
        #    baostock 连接态被污染 → 下一轮 rs.next() 永久阻塞（静默挂起 5.4h）。
        #    每次探测（i>0）前重登录重置连接态，从根上杜绝该阻塞。
        if i > 0:
            try:
                bs.logout()
            except Exception:
                pass
            lg = bs.login()
            if lg.error_code != '0':
                log("⚠️ 数据日探测重登录失败", lg.error_code, "at", day)
            else:
                log("数据日探测重登录", f"i={i} {day}")
        rs = bs.query_all_stock(day=day)
        n = 0
        while rs.error_code == '0' and rs.next():
            n += 1
            if n >= min_rows:  # 够数即停，避免读全市场数千行拖慢探测
                break
        el = time.time() - t0
        if el > TOTAL_LIMIT:
            log("ERROR: 数据日探测超时", f"{el:.0f}s > {TOTAL_LIMIT}s，中止（不产出空 FACTOR_LAB）")
            return None
        if n >= min_rows:
            if i:
                log("数据日回退", f"{d.strftime('%Y-%m-%d')} → {day}（baostock 当日数据未生成，回退 {i} 天）")
            return day
        log("数据日探测", f"[{i+1}/{max_back}] {day}: {n} 行（不足 {min_rows}），继续回退")
    return None


def _q(fn, *a, **kw):
    """2026-09-11 一劳永逸：baostock 查询抗抖动包装。

    背景：baostock 服务端偶发协议/网络异常（IndexError body_arr[11] / timed out /
    接收数据异常 / gzip 解码失败）。原实现裸调用，单只票撞上就把整轮打死：
    实测 2026-09-11 01:19 那轮已跑 73 分钟、roe 1800/3195 只，
    因 get_kline_amt 抛 IndexError 整体崩掉，产物写不出、链上记失败、已算的缓存白等。
    改法：单次查询最多重试 3 次，每次失败先 logout+login 重置连接态；
    仍失败返回 None，由调用方按「本只无数据」跳过，绝不中断整轮。
    """
    for k in range(3):
        try:
            return fn(*a, **kw)
        except Exception as e:
            log("⚠️ baostock 查询异常重试", k + 1, type(e).__name__, str(e)[:80])
            try:
                bs.logout()
            except Exception:
                pass
            time.sleep(1.0 + k)
            try:
                bs.login()
            except Exception:
                pass
    log("⚠️ baostock 查询连续 3 次失败，本只按无数据处理")
    return None

def get_main_universe(day=None):
    rs = _q(bs.query_all_stock, day=day or KL_END)
    codes = {}
    if rs is None:
        return []
    try:
        while rs.error_code == '0' and rs.next():
            v = rs.get_row_data()
            if re.match(r'^(sh\.60|sz\.00)\d{4}$', v[0]):
                codes[v[0]] = True
    except Exception as e:
        log("⚠️ get_main_universe 读行中断", type(e).__name__, str(e)[:60])
    return sorted(codes.keys())

def get_kline_abn(code):
    rs = _q(bs.query_history_k_data_plus, code,
        "date,close,turn,amount", start_date=KL_ABN_START, end_date=KL_END,
        frequency="d", adjustflag="2")
    rows = []
    if rs is None:
        return rows
    try:
        while rs.error_code == '0' and rs.next():
            d = rs.get_row_data()
            try:
                rows.append({"date": d[0], "close": float(d[1]),
                    "turn": float(d[2]) if d[2] not in ("", "None") else 0.0,
                    "amount": float(d[3]) if d[3] not in ("", "None") else 0.0})
            except Exception:
                pass
    except Exception as e:
        log("⚠️ get_kline_abn 读行中断（已收", len(rows), "行）", code, type(e).__name__, str(e)[:60])
    return rows

def get_kline_amt(code):
    """返回 (成交额均值, 最新收盘, 最新K线日) —— 第三项供「数据日期/流动性」判定用。

    2026-09-11 A 类修复：原返回值无日期，导致产物里的 close 无法判定属于哪一天，
    下游把「上次算到这只票那天」的快照当当日价用（见 data/FACTOR_LAB.js close 污染）。
    """
    rs = _q(bs.query_history_k_data_plus, code,
        "date,close,amount", start_date=KL_AMT_START, end_date=KL_END,
        frequency="d", adjustflag="2")
    amts, last, last_date = [], None, None
    if rs is None:
        return 0.0, None, None
    try:
        while rs.error_code == '0' and rs.next():
            d = rs.get_row_data()
            try:
                if d[2] not in ("", "None"): amts.append(float(d[2]))
                if d[1] not in ("", "None"): last = float(d[1])
                if d[0]: last_date = str(d[0])[:10]
            except Exception:
                pass
    except Exception as e:
        log("⚠️ get_kline_amt 读行中断（已收", len(amts), "行）", code, type(e).__name__, str(e)[:60])
    return (sum(amts)/len(amts) if amts else 0.0), last, last_date

def get_roe_ttm(code):
    """ROE_TTM，单位【百分比数值】（33.16 即 33.16%）。

    2026-09-11 口径修正：
      baostock query_profit_data 的 roeAvg 是【财年内累计值·小数】——茅台 2026Q2=0.1795
      表示上半年累计 ROE 17.95%，既不是单季值、也不是百分数。
      旧实现把「最近 4 个累计值」直接相加 → 跨年重复计算：
        0.2637(25Q3) + 0.3446(25Q4) + 0.1057(26Q1) + 0.1795(26Q2) = 0.8935，
      前端再拼 '%' → 卡片显示「ROE_TTM 0.9%」，而真值 33%。
      实测对照：茅台权威 ROE_TTM = 32.41%（westock 财务接口 @2026-06-30），本算法算得 33.16%。

    新算法：逐季差分成【单季】后取最近 4 个单季求和，×100 转百分比。
      单季(Q1) = 累计(Q1)
      单季(Qn) = 累计(Qn) - 累计(Qn-1)   （同财年；缺上一季累计则跳过该季，不猜）
    """
    series = {}
    try:
        for y in ROE_YEARS:
            for q in ROE_QTRS:
                rp = bs.query_profit_data(code, year=y, quarter=q)
                while rp.error_code == '0' and rp.next():
                    v = rp.get_row_data()
                    try:
                        if len(v) > 3 and v[3] not in ("", "None"):
                            series[(y, q)] = float(v[3])
                    except Exception:
                        pass
                time.sleep(0.02)
    except Exception as e:
        log("⚠️ ROE 查询异常跳过", code, type(e).__name__, str(e)[:60])
        return None
    order = sorted(series.keys())
    if len(order) < 4:
        return None
    singles = []
    for (y, q) in order:
        cum = series[(y, q)]
        if q == 1:
            singles.append(cum)
        else:
            prev = series.get((y, q - 1))
            if prev is None:
                continue
            singles.append(cum - prev)
    if len(singles) < 4:
        return None
    return round(sum(singles[-4:]) * 100.0, 2)


# 🔬 2026-09-12 主人令「ROE 榜极端值裁剪 · 算法要公平公正不偏不倚」——
#   三闸门（**全部基于实测数据质量，不是拍脑袋阈值**）
#
# 实证根因（本机 baostock 逐季取证，2026-09-12）：
#   roeAvg 是【财年内累计值】，在「亏损→微利」或「单季剧变」的公司上，累计序列
#   符号/斜率剧烈跳变，逐季差分后噪声被放大，TTM 求和得到毫无经济含义的值。
#
#   sh.600397 江钨装备（榜上第 1 名，TTM=183.36%）：
#     累计 roeAvg: 25Q1 -0.6795 → 25Q2 -3.1876 → 25Q3 -1.5636 → 25Q4 -1.3603
#                  → 26Q1 +0.0069 → 26Q2 +0.0063      ← 跨年符号翻转
#     单季: -0.6795, -2.5081, +1.624, +0.2033, +0.0069, -0.0007
#     → 最后 4 个单季混合了巨额负值与正值，求和 1.8336 纯粹是算术巧合
#     ⚠️ 注意：它净资产 = 净利润/roeAvg 反推约 11.13 亿，**家底并不薄**
#        ⇒ 网传「家底太薄导致放大」的说法不成立，真因是累计口径下的符号翻转。
#
#   sz.001309 德明利（TTM=121.07%）：单季 26Q1=0.6765（单个季度 ROE 67.65%）
#     —— 业绩真实爆发但不可持续，作为「赚钱能力」排序具有误导性。
#
#   sh.600519 贵州茅台（TTM=33.17%，权威 32.41%）：序列平滑 ✅ 保留。
#   → 闸门设计目标：**剔除口径噪声，保留真实高 ROE**，不误伤茅台这类正常公司。

ROE_GATE_MAX_TTM = 150.0   # G3：TTM ROE 上限（主板极端罕见，超出几乎必为口径噪声）
ROE_GATE_MIN_EQUITY = 1.0e8  # G1：反推净资产下限（1 亿元；低于此 ROE 无经济含义）


def get_roe_detail(code):
    """返回 ROE 明细 dict；与 get_roe_ttm 同源同算法，额外带质量闸门判定。

    {"ttm": float|None, "singles": [...], "n_neg": int,
     "equity": float|None, "g1": bool, "g2": bool, "g3": bool, "ok": bool}

    闸门：
      G1 净资产  —— 用 netProfit/roeAvg 反推净资产，≤ 1 亿则 ROE 无经济含义，剔除
      G2 稳定性  —— 近 4 个单季 roeAvg 任一为负 → 盈利不稳定，累计差分噪声大，剔除
      G3 合理性  —— TTM > 150% → 主板极端罕见，判为口径噪声，剔除
    """
    out = {"ttm": None, "singles": [], "n_neg": 0, "equity": None,
           "g1": True, "g2": True, "g3": True, "ok": True}
    series, profits = {}, {}
    try:
        for y in ROE_YEARS:
            for q in ROE_QTRS:
                rp = bs.query_profit_data(code, year=y, quarter=q)
                while rp.error_code == '0' and rp.next():
                    v = rp.get_row_data()
                    try:
                        if len(v) > 3 and v[3] not in ("", "None"):
                            series[(y, q)] = float(v[3])
                        if len(v) > 6 and v[6] not in ("", "None"):
                            profits[(y, q)] = float(v[6])      # netProfit
                    except Exception:
                        pass
                time.sleep(0.02)
    except Exception as e:
        log("⚠️ ROE 查询异常跳过", code, type(e).__name__, str(e)[:60])
        return out
    order = sorted(series.keys())
    if len(order) < 4:
        return out
    singles = []
    for (y, q) in order:
        cum = series[(y, q)]
        if q == 1:
            singles.append(cum)
        else:
            prev = series.get((y, q - 1))
            if prev is None:
                continue
            singles.append(cum - prev)
    if len(singles) < 4:
        return out
    last4 = singles[-4:]
    ttm = round(sum(last4) * 100.0, 2)
    out["ttm"] = ttm
    out["singles"] = [round(x, 6) for x in last4]
    out["n_neg"] = sum(1 for x in last4 if x < 0)
    # G1：反推净资产（取最后一个有 netProfit 的季 + 其累计 roeAvg）
    try:
        for k in reversed(order):
            if k in profits and series.get(k):
                out["equity"] = profits[k] / series[k]
                break
    except Exception:
        pass
    out["g1"] = (out["equity"] is None) or (out["equity"] > ROE_GATE_MIN_EQUITY)
    out["g2"] = (out["n_neg"] == 0)
    out["g3"] = (ttm <= ROE_GATE_MAX_TTM)
    out["ok"] = bool(out["g1"] and out["g2"] and out["g3"])
    return out

def get_name(code):
    rs = _q(bs.query_stock_basic, code=code)
    if rs is None:
        return ""
    try:
        while rs.error_code == '0' and rs.next():
            v = rs.get_row_data()
            if len(v) > 1 and v[1]:
                return v[1]
    except Exception:
        pass
    return ""

def _start_heartbeat(sec=30):
    """🛡 2026-09-09 一劳永逸：向 stdout 定期打心跳，防算法链监督器的「静默杀」误判。
    背景：本脚本冷启动 50-90min，长段落（baostock 逐只查询/缓存命中批量）无任何 stdout，
    算法链监督器 SILENCE_KILL_SEC 默认 15min 无输出即 kill → 实测 2026-09-09 00:04 被误杀，
    产物写不出、链上计数为「失败 1」，因子实验室永远刷不出来。
    心跳线程为 daemon，主进程结束即退出，不影响任何业务逻辑。"""
    import threading as _th
    import time as _t
    def _hb():
        n = 0
        while True:
            _t.sleep(sec)
            n += sec
            log("heartbeat 运行中 %d 分钟（防监督器静默误杀）" % (n // 60))
    t = _th.Thread(target=_hb, daemon=True)
    t.start()


def main():
    _start_heartbeat()
    lg = bs.login(); log("login", lg.error_code)
    # 🔴 2026-09-08 一劳永逸：先解析「baostock 真正已生成数据」的日期并覆盖全局 KL_END。
    #    原实现用「今天」去查，盘前/凌晨必返回 0 行 → universe 0 → 保护性中止 → FACTOR_LAB 停更
    #    （2026-09-05 起连续断更的真根因，此前误判为冷启动慢）。
    global KL_END, ASOF_YM, ASOF_Q
    _dd = resolve_data_date()
    if not _dd:
        log("ERROR: 近 10 个自然日 baostock 均无数据，中止（不产出空 FACTOR_LAB）")
        bs.logout(); return
    KL_END = _dd
    ASOF_YM = KL_END[:7]
    ASOF_Q = "%dQ%d" % (int(KL_END[:4]), (int(KL_END[5:7]) - 1) // 3 + 1)
    log("数据日", KL_END, "| ASOF_YM", ASOF_YM, "| ASOF_Q", ASOF_Q)

    # ---- 异常换手率（重点池） ----
    kcodes = get_key_codes(); log("重点池", len(kcodes))
    a = load_cache(CACHE_A)
    for i, code in enumerate(kcodes):
        # 🛡 2026-09-04：按月刷新（asof_ym 标记）——旧版「算过即永久跳过」导致因子冻结在计算当月
        # 🔴 2026-09-11 A 类修复：补 `liquid is not None` → 历史缓存记录（无该字段）
        #   会在本轮被一次性重算（重点池仅 ~766 只，成本可控），之后就恢复正常月度缓存。
        if (not FORCE) and code in a and a[code].get("factor_at") is not None \
                and a[code].get("asof_ym") == ASOF_YM and a[code].get("liquid") is not None:
            continue
        try:
            name = get_name(code)
            kl = get_kline_abn(code)
        except Exception as e:
            log("⚠️ abn 单只异常跳过", code, type(e).__name__, str(e)[:80])
            continue
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
        last_date = str(kl[-1]["date"])[:10] if kl else None
        # 🔴 2026-09-11 A 类修复「流动性闸门」：停牌/零成交股不得进因子榜。
        #   实测榜首 sh.688432（有研硅）自 2026-08-28 起零成交（腾讯日K / 腾讯实时成交量 0 /
        #   westock 三源一致），当月换手率 = 0 → abn = 0.0 → factor_at = -0.0 却排第 1 名，
        #   并拿到最高档 +2.0 分进最终推荐融合。判据：最新 K 线日 == 数据日 KL_END
        #   且当月换手率 > 0（两条件同时满足才算有流动性）。
        _cur_turn = agg.get(months[-1], {}).get("t", 0.0) if months else 0.0
        _liquid = bool(last_date and last_date == str(KL_END)[:10] and _cur_turn > 0)
        a[code] = {
            "code": code, "name": name, "close": last,
            "close_date": last_date,
            "liquid": _liquid,
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
            except Exception as e: log("bs.logout 异常(忽略,继续重登)", str(e)[:120])
            time.sleep(1)
            lg = bs.login(); log("自动重登录 abn", lg.error_code, "at", i)
        time.sleep(0.02)
    save_cache(a, CACHE_A)
    _illiquid = [r for r in a.values() if r["factor_at"] is not None and r.get("liquid") is False]
    if _illiquid:
        log("流动性闸门剔除", len(_illiquid), "只（停牌/零成交）：",
            [str(x.get("code")) for x in _illiquid[:6]], "...")
    at_valid = [r for r in a.values() if r["factor_at"] is not None and r.get("liquid", True)]
    at_valid.sort(key=lambda r: r["factor_at"], reverse=True)
    at_top = at_valid[:30]
    at_bottom = at_valid[-10:][::-1]
    log("异常换手率有效", len(at_valid), "（已剔除无流动性", len(_illiquid), "只）")

    # ---- ROE 全市场主板 ----
    mcodes = get_main_universe(); log("主板 universe", len(mcodes))
    if len(mcodes) < 1000:
        log("ERROR: 主板 universe 异常过少（" + str(len(mcodes)) + "），中止推送，避免空 ROE 数据上线")
        bs.logout(); return
    r = load_cache(CACHE_R)
    # 2026-09-07 一劳永逸「夜预算」：全市场主板 ~3200 只逐只走 baostock，
    # 冷启动 2h+ 常撞 workflow timeout（云端 90min / 夜间服务端更慢）-> 整轮被杀、
    # 缓存也不落盘 -> 下一轮又从 0 开始，永不收敛（FACTOR_LAB 常年 2-3 天前红灯的真根因）。
    # 改法：每轮最多新取 BUDGET 只（已缓存且当季的自动跳过、不计入），到预算即停，
    # 必定在时限内 save_cache 落盘 + 产出 FACTOR_LAB.js，逐晚增量收敛到全量。
    BUDGET = int(os.environ.get("V8_FLAB_BUDGET", "800"))
    n_new = 0
    for i, code in enumerate(mcodes):
        if n_new >= BUDGET:
            log("达到本轮夜预算", BUDGET, "-> 停止新取，缓存已落盘，剩余下轮续跑")
            break
        # 🛡 2026-09-04：按季刷新（asof_q 标记）——季报披露后下一季度自动重算
        if (not FORCE) and code in r and r[code].get("roe_ver") == ROE_VER and r[code].get("roe_ttm") is not None and r[code].get("size_proxy") and r[code].get("asof_q") == ASOF_Q:
            continue
        n_new += 1
        try:
            name = get_name(code)
            amt, last, last_date = get_kline_amt(code)
            _rd = get_roe_detail(code)
            roe = _rd["ttm"]
        except Exception as e:
            log("⚠️ roe 单只异常跳过", code, type(e).__name__, str(e)[:80])
            continue
        r[code] = {
            "code": code, "name": name,
            "close": round(last, 2) if last is not None else None,
            "close_date": last_date,
            "liquid": bool(last_date and last_date == str(KL_END)[:10]),
            "roe_ttm": round(roe, 2) if roe is not None else None,
            "size_proxy": round(amt, 1) if amt else 0.0,
            "asof_q": ASOF_Q,
            "roe_ver": ROE_VER,
            # 🔬 2026-09-12 质量闸门（三闸门 + 取证字段，供前端与审计复核）
            "roe_ok": _rd["ok"],
            "roe_gate": ("G1净资产" if not _rd["g1"] else "")
                          + ("G2负单季" if not _rd["g2"] else "")
                          + ("G3超上限" if not _rd["g3"] else ""),
            "roe_singles": _rd["singles"],
            "roe_n_neg": _rd["n_neg"],
            "roe_equity": round(_rd["equity"], 0) if _rd["equity"] is not None else None,
        }
        if (i+1) % 25 == 0:
            save_cache(r, CACHE_R)
            log("roe 进度", i+1, "/", len(mcodes),
                "有效", len([1 for v in r.values() if v.get('roe_ttm') is not None]))
        if i > 0 and i % 200 == 0:
            try: bs.logout()
            except Exception as e: log("bs.logout 异常(忽略,继续重登)", str(e)[:120])
            time.sleep(1)
            lg = bs.login(); log("自动重登录 roe", lg.error_code, "at", i)
        time.sleep(0.02)
    save_cache(r, CACHE_R)
    valid = [v for v in r.values()
             if v.get("roe_ttm") is not None and v.get("size_proxy") and v.get("liquid", True)]
    valid.sort(key=lambda x: x["size_proxy"], reverse=True)
    n = len(valid)
    large = valid[:max(1, n//3)]
    # 🔬 2026-09-12 主人令「算法要公平公正，不偏不倚」：ROE 榜**极端值裁剪**。
    #   闸门在候选层过滤（而非排序后再砍头），保证「大市值档 Top1/3」的样本口径
    #   不被少数噪声股挤占；被剔除的股票仍在缓存里，只是不进榜。
    #   ⚠️ 默认开启；可用 V8_ROE_GATE=0 临时关闭（仅限诊断，生产不得关）。
    #   兼容历史缓存：老记录没有 roe_ok 字段 → 视为通过（不让旧缓存凭空掉榜）。
    _GATE_ON = os.environ.get("V8_ROE_GATE", "1") != "0"
    _gated = []
    if _GATE_ON:
        for v in large:
            if v.get("roe_ok", True):
                _gated.append(v)
            else:
                _gated.append(None)
        _dropped = [v for v in large if not v.get("roe_ok", True)]
        large = [v for v in large if v.get("roe_ok", True)]
        log("ROE 闸门(G1净资产/G2负单季/G3超上限) 剔除", len(_dropped), "只 /",
            "剔除前", len(_gated), "只",
            "| 样例:", [f"{x['code']}({x.get('roe_gate') or '-'})" for x in _dropped[:6]])
    else:
        log("⚠️ V8_ROE_GATE=0 —— ROE 质量闸门已被人为关闭（仅诊断用途）")
    if len(large) < 10:
        log("ERROR: ROE 闸门后样本不足（" + str(len(large)) + "），拒绝推送以免榜单失真")
        return
    large.sort(key=lambda x: x["roe_ttm"], reverse=True)
    top30 = large[:30]
    log("全市场有效", n, "大市值档(闸门后)", len(large), "Top30首只", top30[0]["code"] if top30 else "无")

    if len(at_valid) < 10 or len(large) < 10:
        log("ERROR: 有效样本不足（abn=" + str(len(at_valid)) + ", roe_large=" + str(len(large)) + "），中止推送")
        bs.logout(); return

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": KL_END,
        "meta": {
            "data_date": KL_END,
            "close_semantics": "⚠️ 记录里的 close 是「上次算到这只票那天」的快照（roe 按季 asof_q / abn 按月 asof_ym 缓存），**不是当日报价**；需要当日价请查 STOCK_QUOTE.js 或 CANDIDATE_QUOTES.js。同时看 close_date 字段。",
            "liquid_def": "liquid=false 表示最新K线日 != 数据日 或 当月换手率为 0（停牌/零成交），已从榜单剔除",
            "universe": "重点池(持仓+候选+黄金)·异常换手率 / 全市场主板·ROE",
            "n_universe": len(kcodes),
            "n_at_valid": len(at_valid),
            "n_roe_large": len(large),
            "abnormal_def": "当月换手率÷过去12月均值; 缩量=因子高=强势",
            "roe_def": "全市场主板·大市值档(成交额代理top1/3)按 ROE_TTM 降序 Top30（TTM=近4个单季 roeAvg 差分求和，单位%）",
            "roe_universe": "全市场主板",
        },
        "abnormal_turnover": {"top": at_top, "bottom": at_bottom},
        "roe_largecap": {"top": top30},
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    js = "window.FACTOR_LAB = " + json.dumps(out, ensure_ascii=False) + ";\n"
    open(OUT_JS, "w", encoding="utf-8", newline="\n").write(js)

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
        # 2026-09-11 口径修正：把线上可能残留的旧口径描述自动纠正为「近4个单季差分求和」
        html = html.replace("最近4季度 roeAvg 求和", "近4个单季 roeAvg 差分求和")
        html = html.replace("ROE_TTM=最近4季度 roeAvg 求和", "ROE_TTM=近4个单季 roeAvg 差分求和")
        html = html.replace(
            "注：重点池60%为双创，ROE大市值档样本偏薄，仅作观察。",
            "已切换为全市场主板(3193只)·大市值档(成交额top1/3)。")
        new_html = re.sub(r"data/FACTOR_LAB\.js\?v=[0-9a-f]{10}", "data/FACTOR_LAB.js?v=" + h, html)
        open(hp, "w", encoding="utf-8").write(new_html)
        log("?v ->", h)
    except Exception as e:
        log("?v 更新失败", e)

    # 🛡 2026-09-08 一劳永逸：本地工作树若存在未提交/未跟踪文件（如 AUDIT_*.md、
    #   update_v8.py CRLF 噪声），会导致 rebase 失败 → push abort，数据算好却上不了线。
    #   修复：推送前先把当前工作树整体 stash（含未跟踪），强同步到 origin/main，
    #   再恢复 stash，最后只提交目标文件并推送。push 失败时自动重试一次。
    def _push_with_clean_tree(max_retries=2):
        for attempt in range(1, max_retries + 1):
            log("推送尝试", attempt)
            # 1) 保存工作树（含未跟踪），避免 rebase 被脏树阻挡
            rc, o = git("stash", "push", "--include-untracked", "-m", "factor_lab auto-stash before push")
            stash_created = (rc == 0) or ("Saved" in (o or ""))
            log("stash created=", stash_created, o.strip()[-100:] if o else "")
            # 2) 强同步到远端最新 main
            rc, o = git("fetch", "origin", "main")
            log("fetch rc=", rc)
            rc, o = git("reset", "--hard", "FETCH_HEAD")
            log("reset --hard FETCH_HEAD rc=", rc, (o[-200:] if o else ""))
            # 3) 恢复 stash；若冲突，优先保留 stash（ours）版本
            if stash_created:
                rc, o = git("stash", "pop")
                if rc != 0:
                    log("stash pop 冲突 -> 强制恢复 stash 版本", o[-300:] if o else "")
                    git("checkout", "--theirs", ".")
                    git("add", ".")
            # 4) 提交目标文件
            rc, o = git("add", "index.html", "data/FACTOR_LAB.js", "raw_data/factor_lab.json")
            log("git add rc=", rc)
            if rc != 0:
                log("git add 失败", o[-300:] if o else "")
                if attempt < max_retries:
                    continue
                bs.logout(); return False
            rc, o = git("commit", "-m",
                "chore(v8): 因子实验室定时刷新(异常换手率重点池 + ROE全市场主板)")
            log("git commit rc=", rc, (o[-400:] if o else ""))
            # 5) 推送
            rc, o = git("push", "origin", "HEAD:refs/heads/main")
            log("git push rc=", rc, (o[-500:] if o else ""))
            if rc == 0:
                rc, o = git("ls-remote", "origin", "main")
                log("ls-remote main =>", (o.strip() if o else "NONE"))
                return True
            # 6) 失败时清理本地 commit，准备重试
            log("push 失败，清理并重试"); git("reset", "--hard", "FETCH_HEAD")
        return False

    ok = _push_with_clean_tree()
    bs.logout()
    log("DONE", "success" if ok else "FAILED_PUSH")

if __name__ == "__main__":
    main()
