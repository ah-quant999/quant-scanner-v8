#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_missing3_factors.py — 补验三个此前「未验证就删」的因子（2026-10-25 主人令纠偏）

主人令：「把未验证的都验证完再决定去留，不是未验证就直接删！」
此前 verify_untested_factors.py 漏掉/做错的三个：
  A. 连续共振天数 —— 直接标 NO_DATA 没测。实际 gold_pool.json 个股自带 history
     （2026-09-07~10-23, 29 交易日, 金钻真506/缠论真783），可真实回测。
  B. 分析师关注 —— 没加载文件就判无数据。实际 raw_data/analyst_ratings.json 存在，
     且 git 有 ~8 个不同日期快照，可重建「哪天哪些票在名单」做真实回测。
  C. 52周新高 —— 此前用 K线代理（贴近250日高点全体），但生产信号是 top_gainers
     每日仅 15 只（强选择性子集），人群不同、代理不等价。git 有 ~9 个日期快照，
     用真实名单重测。

统一口径：信号日 d 的名单 → 前向10日收益（close[d+10]/close[d]-1）vs 池基线均值，
跨日聚合期望差/胜率/t。快照抓取时间均为盘前(07-08点)→数据反映前一交易日收盘状态，
故信号日取「严格早于抓取日的最近交易日」（无未来函数）。
样本量警示：B/C 仅 ~8-9 个快照日，t 值参考意义有限，结论标注置信度。
"""
import json, os, math, subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
CACHE = os.path.join(RAW, "kline_cache_multi")
POOL_FILE = os.path.join(RAW, "gold_pool.json")
OUT_JSON = os.path.join(RAW, "missing3_factor_verdicts.json")
HOLD = 10

# ── 数据加载 ──
pool = json.load(open(POOL_FILE, encoding="utf-8"))
pool_meta = {}   # bare code -> name
for v in (pool.get("stocks") or {}).values():
    if v.get("code"):
        pool_meta[v["code"]] = v.get("name", "")

stocks = {}
for fn in os.listdir(CACHE):
    if not fn.endswith(".json") or fn == "000001.json":
        continue
    code = fn[:-5]
    if code not in pool_meta:
        continue
    try:
        bars = json.load(open(os.path.join(CACHE, fn), encoding="utf-8"))
    except Exception:
        continue
    if isinstance(bars, list) and len(bars) >= 300:
        idx = {r["date"]: j for j, r in enumerate(bars)}
        stocks[code] = (bars, idx)
print("池∩缓存可回测: %d 只" % len(stocks))

mkt = json.load(open(os.path.join(CACHE, "000001.json"), encoding="utf-8"))
all_dates = [r["date"] for r in mkt]
date_set = set(all_dates)
# 每个日期在 kline 中的位置，用于 fwd10 存在性判断
pos = {d: i for i, d in enumerate(all_dates)}

def fwd10(code, d):
    """前向10日收益；需 d 在 kline 且 d+10 存在。"""
    bars, idx = stocks.get(code, (None, None))
    if bars is None:
        return None
    j = idx.get(d)
    if j is None or j + HOLD >= len(bars) or j < 1:
        return None
    p0, p1 = float(bars[j]["close"]), float(bars[j + HOLD]["close"])
    if not (p0 and p0 > 0):
        return None
    return p1 / p0 - 1.0

def prev_trade_date(fetch_date):
    """严格早于抓取日的最近 kline 交易日（盘前抓取→信号日=前一收盘日）。"""
    cand = [d for d in all_dates if d < fetch_date]
    return cand[-1] if cand else None

# ── git 快照提取 ──
def git_snapshots(path, code_extract):
    """返回 {snapshot_date: set(codes)}，同日多版本取最新提交。"""
    log = subprocess.run(
        ["git", "log", "--all", "--format=%h %ad", "--date=format:%Y-%m-%d", "--", path],
        capture_output=True, text=True, cwd=ROOT).stdout.strip().splitlines()
    snaps = {}
    for line in log:
        parts = line.split()
        if len(parts) < 2:
            continue
        c, d = parts[0], parts[1]
        try:
            data = json.loads(subprocess.run(
                ["git", "show", f"{c}:{path}"], capture_output=True, text=True, cwd=ROOT).stdout)
        except Exception:
            continue
        codes = code_extract(data)
        if codes:
            snaps[d] = codes          # git log 倒序，后写覆盖=同日取最新
    return snaps

# ═══ A. 连续共振天数 ═══
print("\n═══ A. 连续共振天数（金钻|缠论 连续日 streak，生产口径 L1648-1657）═══")
# 每票: [(date, has_sig)] 按 date 升序
hist_map = {}
for v in (pool.get("stocks") or {}).values():
    code = v.get("code")
    if code not in stocks:
        continue
    rows = []
    for h in v.get("history", []):
        d = h.get("date")
        if not d:
            continue
        sig = bool(h.get("金钻_起涨") or h.get("金钻_黄柱")) or bool(h.get("缠论买_日K"))
        rows.append((d, sig))
    rows.sort()
    # 同日去重（保留后者）
    dd = {}
    for d, s in rows:
        dd[d] = s
    hist_map[code] = sorted(dd.items())

def consec_at(code, d):
    """生产口径：最近一条 ≤d 的 history 起，向前数连续 sig=True 的天数。"""
    rows = hist_map.get(code) or []
    prior = [s for (hd, s) in rows if hd <= d]
    if not prior or not prior[-1]:
        return 0
    n = 0
    for s in reversed(prior):
        if s:
            n += 1
        else:
            break
    return n

# 评估日：history 覆盖的交易日里，fwd10 可用的全部（stride=1，窗口短只有~20日）
hist_dates = sorted({d for rows in hist_map.values() for d, _ in rows})
eval_dates = [d for d in hist_dates if any(
    (lambda j: j is not None and j + HOLD < len(stocks[c][0]))(
        stocks[c][1].get(d)) for c in list(stocks)[:50] if d in stocks[c][1])]
eval_dates = [d for d in eval_dates if pos.get(d, -1) + HOLD < len(all_dates)]

GROUPS = [("consec1", lambda n: n >= 1, "streak≥1 (+2分档)"),
          ("consec2", lambda n: n >= 2, "streak≥2 (+4分档)"),
          ("consec3", lambda n: n >= 3, "streak≥3 (+6分档)")]

resA = {}
for key, cond, label in GROUPS:
    exs, ns, covered = [], 0, 0
    for d in eval_dates:
        base_vals = [f for c in stocks if (f := fwd10(c, d)) is not None]
        if len(base_vals) < 30:
            continue
        base = sum(base_vals) / len(base_vals)
        grp = []
        for c in stocks:
            if cond(consec_at(c, d)):
                f = fwd10(c, d)
                if f is not None:
                    grp.append(f)
        if len(grp) < 5:
            continue
        exs.append(sum(grp) / len(grp) - base)
        ns += len(grp)
        covered += 1
    if exs:
        mu = sum(exs) / len(exs)
        win = sum(1 for x in exs if x > 0) / len(exs)
        var = sum((x - mu) ** 2 for x in exs) / (len(exs) - 1) if len(exs) > 1 else 0.0
        t = mu / (var ** 0.5 / math.sqrt(len(exs))) if var > 0 else 0.0
        resA[key] = {"label": label, "excess": mu, "win": win, "t": t, "ns": ns, "days": covered}
        print("%-22s %+7.2f%%  win %3.0f%%  t=%+.2f  票次 %5d  日 %d" %
              (label, mu * 100, win * 100, t, ns, covered))
    else:
        resA[key] = {"label": label, "n": 0}
        print("%-22s 样本不足" % label)

# ═══ B. 分析师关注（真实快照名单）═══
print("\n═══ B. 分析师关注（git 快照 hot_stocks+new_coverage，生产口径 L1522-1528）═══")
def analyst_codes_of(data):
    codes = set()
    for key in ("hot_stocks", "new_coverage", "upgrades"):
        for a in data.get(key, []) or []:
            if a.get("code"):
                codes.add(str(a["code"]).zfill(6))
    return codes

snapsB = git_snapshots("raw_data/analyst_ratings.json", analyst_codes_of)
print("快照日: %d (%s)" % (len(snapsB), ", ".join(sorted(snapsB))))
exsB, nsB = [], 0
for F in sorted(snapsB):
    d = prev_trade_date(F)
    if d is None:
        continue
    members = [c for c in snapsB[F] if c in stocks]
    base_vals = [f for c in stocks if (f := fwd10(c, d)) is not None]
    if len(base_vals) < 30 or len(members) < 5:
        print("  %s(信号日%s): 成员%d/基线%d 样本不足" % (F, d, len(members), len(base_vals)))
        continue
    base = sum(base_vals) / len(base_vals)
    grp = [f for c in members if (f := fwd10(c, d)) is not None]
    if len(grp) < 5:
        continue
    ex = sum(grp) / len(grp) - base
    exsB.append(ex)
    nsB += len(grp)
    print("  %s(信号日%s): 成员%2d  组均值 %+5.2f%% vs 基线 %+5.2f%% → excess %+5.2f%%" %
          (F, d, len(grp), (sum(grp)/len(grp))*100, base*100, ex*100))
if exsB:
    mu = sum(exsB) / len(exsB)
    win = sum(1 for x in exsB if x > 0) / len(exsB)
    var = sum((x - mu) ** 2 for x in exsB) / (len(exsB) - 1) if len(exsB) > 1 else 0.0
    tB = mu / (var ** 0.5 / math.sqrt(len(exsB))) if var > 0 else 0.0
    resB = {"excess": mu, "win": win, "t": tB, "ns": nsB, "days": len(exsB)}
    print("  ⇒ 期望差 %+7.2f%%  win %3.0f%%  t=%+.2f  票次 %d  日 %d" %
          (mu * 100, win * 100, tB, nsB, len(exsB)))
else:
    resB = {"n": 0}
    print("  ⇒ 样本不足")

# ═══ C. 52周新高（真实 top_gainers 名单，每日仅15只）═══
print("\n═══ C. 52周新高（git 快照 top_gainers 真实名单，生产口径 L1513-1518）═══")
def w52_codes_of(data):
    return {str(s["code"]).zfill(6) for s in data.get("top_gainers", []) if s.get("code")}

snapsC = git_snapshots("raw_data/w52_high.json", w52_codes_of)
print("快照日: %d" % len(snapsC))
exsC, nsC = [], 0
for F in sorted(snapsC):
    d = prev_trade_date(F)
    if d is None:
        continue
    members = [c for c in snapsC[F] if c in stocks]
    base_vals = [f for c in stocks if (f := fwd10(c, d)) is not None]
    if len(base_vals) < 30 or len(members) < 5:
        print("  %s(信号日%s): 成员%d 样本不足" % (F, d, len(members)))
        continue
    base = sum(base_vals) / len(base_vals)
    grp = [f for c in members if (f := fwd10(c, d)) is not None]
    if len(grp) < 5:
        continue
    ex = sum(grp) / len(grp) - base
    exsC.append(ex)
    nsC += len(grp)
    print("  %s(信号日%s): 成员%2d  组均值 %+5.2f%% vs 基线 %+5.2f%% → excess %+5.2f%%" %
          (F, d, len(grp), (sum(grp)/len(grp))*100, base*100, ex*100))
if exsC:
    mu = sum(exsC) / len(exsC)
    win = sum(1 for x in exsC if x > 0) / len(exsC)
    var = sum((x - mu) ** 2 for x in exsC) / (len(exsC) - 1) if len(exsC) > 1 else 0.0
    tC = mu / (var ** 0.5 / math.sqrt(len(exsC))) if var > 0 else 0.0
    resC = {"excess": mu, "win": win, "t": tC, "ns": nsC, "days": len(exsC)}
    print("  ⇒ 期望差 %+7.2f%%  win %3.0f%%  t=%+.2f  票次 %d  日 %d" %
          (mu * 100, win * 100, tC, nsC, len(exsC)))
else:
    resC = {"n": 0}
    print("  ⇒ 样本不足")

# ═══ 裁决 ═══
print("\n═══ 裁决（同口径: ≥+0.30pp且t≥1→KEEP; ≤−0.30pp→DROP; 其余→无证据）═══")
out = {"generated": "2026-10-25", "method": "真实生产数据（gold_pool history + git 快照名单）+ kline fwd10",
       "consec": resA, "analyst": resB, "w52_real": resC}

def verdict(r):
    if r.get("n") == 0 or ("excess" not in r):
        return "NO_DATA(样本不足)"
    e, t = r["excess"], r["t"]
    if e >= 0.0030 and t >= 1.0:
        return "KEEP"
    if e <= -0.0030:
        return "DROP"
    return "NO_EDGE"

for name, r in [("consec(各档)", resA), ("analyst", resB), ("w52_real", resC)]:
    if name == "consec(各档)":
        for k, rr in r.items():
            print("%-18s %s" % (rr.get("label", k), verdict(rr)))
    else:
        print("%-18s %s" % (name, verdict(r)))

json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n落盘: %s" % OUT_JSON)
