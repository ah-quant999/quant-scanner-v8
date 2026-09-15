#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股艾略特波浪定位 · 数据日频刷新（小九机 / 收盘后自动）

【做什么】
  - 拉指数日K（上证指数 + 5 指数：沪深300/创业板指/深证成指/科创50）
    三级降级源：腾讯 ifzq → 新浪 → 东财 push2his；纯标准库 urllib，无需 westock/任何连接器
    （东财对本机 IP 有节流，实测分钟级封禁，故不作主源）
  - 客观序列 series(上证 dates/closes) + idx(5指数 last/hi/hdate/dd) 自动刷新
  - marks(人工浪型拐点 ①起~⑤高) 原样保留，绝不由脚本重新判定
  - 幂等：若拉到的最新交易日 == 已记录最新日（周末/假期无新K），跳过推送，仅校验+渲染
  - 刷新后隔离索引单文件推送 data/WAVE_ELLIOTT.js 到 origin/main（raw-tree-push，防覆盖，不碰 index.html 热文件）
  - 最后跑 gen_wave_report.py 出 HTML（本地 out/，不推）

【谁跑】
  小九机 WorkBuddy automation 日频 16:00（收盘后数据齐）。阿狸咪机无此 automation（也无 westock），
  她只需 git pull 最新 data/WAVE_ELLIOTT.js + python v8/gen_wave_report.py 出报告。

【用法】
  python v8/fetch_wave_elliott.py            # 正常日频（幂等）
  python v8/fetch_wave_elliott.py --force    # 强制重算并推送（即使最新日相同）
"""
import re, json, os, sys, subprocess, argparse, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "WAVE_ELLIOTT.js")
GEN  = os.path.join(ROOT, "v8", "gen_wave_report.py")

# 指数代码映射：东方财富 secid / 腾讯代码 / 新浪代码
# 腾讯=主源（实测最稳），新浪=备源，东财=末位备源（本机 IP 有节流）
SECIDS = [
    ("上证指数", "1.000001", "sh000001"),
    ("沪深300", "1.000300", "sh000300"),
    ("创业板指", "0.399006", "sz399006"),
    ("深证成指", "0.399001", "sz399001"),
    ("科创50",  "1.000688", "sh000688"),
]
LMT = 700  # 约 2.7 年交易日，覆盖全部浪型拐点
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}


def _get_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_tencent(tcode):
    """腾讯 ifzq 日K（主源）。返回 [(date, close), ...]"""
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           "?param=%s,day,,,%d,qfq" % (tcode, LMT))
    j = _get_json(url)
    d = j.get("data", {}).get(tcode) or {}
    k = d.get("qfqday") or d.get("day") or []
    if not k:
        raise RuntimeError("腾讯返回空 kline")
    # 每行: [date, open, close, high, low, volume, ...]
    return [(row[0], float(row[2])) for row in k]


def fetch_sina(scode):
    """新浪日K（备源）。返回 [(date, close), ...]"""
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d" % (scode, LMT))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        txt = r.read().decode("utf-8", "ignore")
    arr = json.loads(txt)
    if not arr:
        raise RuntimeError("新浪返回空数组")
    return [(x["day"], float(x["close"])) for x in arr]


def fetch_eastmoney(secid):
    """东财 push2his（末位备源，本机 IP 有节流）。返回 [(date, close), ...]"""
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
           "?secid=%s&fields1=f1,f2,f3&fields2=f51,f53&klt=101&fqt=0&end=20500101&lmt=%d" % (secid, LMT))
    j = _get_json(url)
    if not j.get("data") or not j["data"].get("klines"):
        raise RuntimeError("东财返回空 data")
    return [(k.split(",")[0], float(k.split(",")[1])) for k in j["data"]["klines"]]


def fetch_kline(name, secid, tcode, retries=3):
    """三级降级拉日K：腾讯 → 新浪 → 东财。返回 ([(date, close), ...], 实际源名)。"""
    sources = [
        ("腾讯", lambda: fetch_tencent(tcode)),
        ("新浪", lambda: fetch_sina(tcode)),
        ("东财", lambda: fetch_eastmoney(secid)),
    ]
    errs = []
    for sname, fn in sources:
        for i in range(retries):
            try:
                out = fn()
                if len(out) < 2:
                    raise RuntimeError("序列过短 %d 条" % len(out))
                out.sort(key=lambda x: x[0])
                print("  · %s 取数成功（源=%s，%d 条，末 %s）" % (name, sname, len(out), out[-1][0]))
                return out, sname
            except Exception as e:
                errs.append("%s/%d: %s" % (sname, i + 1, type(e).__name__))
                if i < retries - 1:
                    time.sleep(1 + i * 2)
    raise RuntimeError("三级源全部失败（%s）" % "; ".join(errs[-6:]))


def parse_data():
    h = open(DATA, encoding="utf-8").read()
    # 兼容本地美化态与 update_v8.py 压缩态（仓库内 data/*.js 最终均为单行）
    m = re.search(r'window\.WAVE_ELLIOTT\s*=\s*(\{.*\});\s*$', h.strip(), re.S)
    if not m:
        raise RuntimeError("无法解析 data/WAVE_ELLIOTT.js")
    return json.loads(m.group(1))


def dump_js(obj):
    """产出与 update_v8.py 一致的压缩态（单行），避免落入仓库后被二次重写。"""
    return "window.WAVE_ELLIOTT = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n"


def git(args, env=None):
    e = dict(os.environ)
    e["MSYS_NO_PATHCONV"] = "1"
    if env:
        e.update(env)
    return subprocess.run(["git"] + args, cwd=ROOT, env=e, capture_output=True, text=True)


def sync_local():
    """把本地工作树的 data/WAVE_ELLIOTT.js 对齐到 origin/main。

    🔴 必须用远端 blob 直写（而非 checkout/pull）：本仓工作树常被 monitor 持续写入 raw_data，
    常规 pull 会因脏树失败或误伤他人 WIP；只取单文件远端内容覆盖是零副作用的做法。
    """
    f = git(["fetch", "origin"])
    if f.returncode != 0:
        print("· 警告：fetch 失败，沿用本地副本")
        return
    blob = git(["show", "origin/main:data/WAVE_ELLIOTT.js"])
    if blob.returncode != 0 or not blob.stdout.strip():
        print("· 警告：远端无 data/WAVE_ELLIOTT.js，沿用本地副本")
        return
    cur = open(DATA, encoding="utf-8").read() if os.path.exists(DATA) else ""
    if cur != blob.stdout:
        with open(DATA, "w", encoding="utf-8", newline="") as fp:
            fp.write(blob.stdout)
        print("· 已对齐远端最新 data/WAVE_ELLIOTT.js")
    else:
        print("· 本地已是远端最新 data/WAVE_ELLIOTT.js")


def raw_push(relpath, blob_path, commit_msg):
    """隔离索引单文件推送（raw-tree-push），范围守卫仅本文件。"""
    git(["fetch", "origin"])
    tip = git(["rev-parse", "origin/main"]).stdout.strip()
    if not tip:
        raise RuntimeError("fetch 失败，无 origin/main")
    tree_sha = git(["rev-parse", tip + "^{tree}"]).stdout.strip()
    idx = os.path.join(os.environ.get("TEMP", "/tmp"), "v8_iso_wave_auto")
    env = {"GIT_INDEX_FILE": idx}
    if os.path.exists(idx):
        os.remove(idx)
    git(["read-tree", tree_sha], env=env)
    blob = git(["hash-object", "-w", blob_path], env=env).stdout.strip()
    git(["update-index", "--cacheinfo", "100644", blob, relpath], env=env)
    tree = git(["write-tree"], env=env).stdout.strip()
    # 范围守卫
    out = git(["diff-tree", "--no-commit-id", "--name-only", "-r", tip, tree], env=env).stdout.strip()
    changed = [c for c in out.split("\n") if c]
    if not changed:
        print("· 内容无变化，跳过推送")
        return
    if changed != [relpath]:
        print("✗ 范围守卫失败，改动文件=%s" % changed)
        sys.exit(1)
    commit = git(["commit-tree", tree, "-p", tip, "-m", commit_msg], env=env).stdout.strip()
    p = git(["push", "origin", commit + ":refs/heads/main"], env=env)
    if p.returncode != 0:
        print("✗ push 失败:\n%s" % p.stderr)
        sys.exit(1)
    print("✓ 推送成功 %s -> main（仅 %s）" % (commit[:10], relpath))


def render():
    r = subprocess.run([sys.executable, GEN], cwd=ROOT, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("✗ 渲染报告失败:\n%s" % r.stderr)
        sys.exit(1)


def freshness_guard(last_date, stale_days=15):
    """数据新鲜度守卫：最新交易日距今天超过 stale_days 自然日 → 说明取数异常（源给出陈旧数据）。

    交易日历校验：正常情况最新交易日距今 ≤ 4 自然日（含周末）；长假最多 9 天（春节/国庆）。
    超过 15 天必是异常，拒绝写入以防把陈旧数据推上仓库。
    """
    try:
        from datetime import datetime, date as _d
        ld = datetime.strptime(last_date, "%Y-%m-%d").date()
    except Exception:
        print("· 警告：无法解析最新交易日 %s，跳过新鲜度校验" % last_date)
        return
    gap = (_d.today() - ld).days
    if gap > stale_days:
        print("✗ 新鲜度守卫：最新交易日 %s 距今 %d 天（>%d），疑似取到陈旧数据，拒绝写入"
              % (last_date, gap, stale_days))
        sys.exit(2)
    print("· 新鲜度：最新交易日 %s（距今 %d 天）" % (last_date, gap))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="即使无新交易日也重算并推送")
    args = ap.parse_args()

    # 1) 拉上证
    try:
        sh, sh_src = fetch_kline(*SECIDS[0])
    except Exception as e:
        print("✗ 拉取上证日K失败: %s" % e)
        sys.exit(1)
    dates = [x[0] for x in sh]
    closes = [x[1] for x in sh]
    if len(dates) < 2:
        print("✗ 上证序列过短")
        sys.exit(1)
    last = closes[-1]
    prev = closes[-2]
    # 涨跌幅 = (最新收盘 - 上一交易日收盘) / 上一交易日收盘。序列本身已剔除休市日，
    # 长假后 closes[-2] 即节前最后一个交易日，天然正确，无需另行处理交易日历。
    pct = round((last - prev) / prev * 100, 2)
    new_last_date = dates[-1]

    # 数据新鲜度守卫（防源返回陈旧数据被推上仓库）
    freshness_guard(new_last_date)

    # 2) 拉 5 指数
    idx_new = []
    srcs = set([sh_src])
    for name, secid, tcode in SECIDS:
        if name == "上证指数":
            k = sh
        else:
            try:
                k, sname = fetch_kline(name, secid, tcode)
                srcs.add(sname)
            except Exception as e:
                print("✗ 拉取 %s 失败: %s" % (name, e))
                sys.exit(1)
        kd = [x[0] for x in k]
        kc = [x[1] for x in k]
        hi = max(kc)
        hdate = kd[kc.index(hi)]
        dd = round((kc[-1] - hi) / hi * 100, 2)
        idx_new.append({"name": name, "last": kc[-1], "date": kd[-1], "hi": hi, "hdate": hdate, "dd": dd})

    # 3) 先把本地与远端对齐，再读旧数据（否则可能基于落后副本误判"无新交易日"）
    sync_local()

    old = parse_data()
    marks = old.get("marks", [])

    # 4) 幂等判断（基于已对齐远端的最新副本）
    old_last_date = old.get("series", {}).get("dates", [""])[-1]
    if (not args.force) and new_last_date == old_last_date:
        print("· 无新交易日（最新 %s == 已记录 %s），跳过推送，仅校验+渲染" % (new_last_date, old_last_date))
        render()
        sys.exit(0)

    # 5) 组装新对象（客观刷新 + marks 保留）
    meta = old.get("meta", {})
    meta.update({
        "date": new_last_date,
        "last": last,
        "pct": pct,
        "source": " + ".join(sorted(srcs)) + " 行情接口（小九机日频自动化 / 三级降级）",
        "update_by": "小九机收盘后日频自动化 fetch_wave_elliott.py（客观序列自动 / marks 人工保留）",
    })
    if "note" not in meta:
        meta["note"] = "客观数据层：上证日线序列 + 浪型拐点 + 5指数对照。主观研判固化在 v8/wave_report_template.html。"
    meta["note"] = ("客观数据层：上证日线序列 + 浪型拐点 + 5指数对照（腾讯/新浪/东财三级降级取数）。"
                    "marks 为人工浪型拐点，脚本只保留不重判；主观研判固化在 v8/wave_report_template.html。"
                    "更新仅需小九机跑 v8/fetch_wave_elliott.py 自动刷新并推仓库，阿狸咪无需 westock。")
    new_obj = {"meta": meta, "series": {"dates": dates, "closes": closes}, "marks": marks, "idx": idx_new}

    # 6) 校验
    if len(dates) != len(closes):
        print("✗ 校验失败：dates/closes 长度不一致"); sys.exit(1)
    if not marks or not idx_new:
        print("✗ 校验失败：marks/idx 为空"); sys.exit(1)

    # 7) 写回
    with open(DATA, "w", encoding="utf-8") as f:
        f.write(dump_js(new_obj))
    print("✓ 数据刷新：截至 %s 上证收 %s (%s%%) | %d 交易日 | 5指数/ %d 拐点(人工保留)"
          % (new_last_date, last, pct, len(dates), len(marks)))

    # 8) 推送（防覆盖，单文件）
    raw_push("data/WAVE_ELLIOTT.js", DATA, "data(wave): 日频刷新波浪客观序列(截至%s)" % new_last_date)

    # 9) 渲染报告
    render()


if __name__ == "__main__":
    main()
