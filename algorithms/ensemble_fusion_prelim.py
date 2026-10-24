#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多策略 Ensemble（rank-fusion）初步证据回测（2026-10-24 主人令「确认真的有收益率的提升才开始动手」）

【目的】在动手建生产 Ensemble 之前，用现有真实信号档案验证「融合名单是否真的比单策略好」。
证据边界（如实声明，不夸大）：
  · 因子榜 top10 每日快照：93 天（2026-06-06 → 2026-10-24，raw_data/history/top10_daily_*.json）
  · 强势跟踪每日新选：仅 10 批（2026-09-18 → 2026-10-12，ima_strong_history_v2.json first_selected）
  · FF3 每日信号：仅 2 天（2026-09-18 / 2026-10-21，ff3_ranksum_history.json）——历史融合回测不可得
  ⇒ 三路重叠窗口 ≈ 2026-09-18 → 2026-10-09（T+10 可算）/ 10-16（T+5 可算），样本极小，
    本结果仅作**方向性初步证据**；正式准入仍须走「真实信号流归档 ≥30 信号日」纪律（与 FF3 上线同轨）。

【方案】
  A5    因子榜 Top5（rank 1-5，现役主口径基线）
  Ball  强势跟踪当日新选（全部，通常 5-7 只）
  RRF5  Reciprocal Rank Fusion：score(c)=Σ_list 1/(60+rank_c)，A/B/C 三路（当日有则参与）→ Top5
        当日仅 A 可用 ⇒ RRF5 ≡ A5（无信息日，自动不计入配对差异）

【执行口径（初步）】次开买入（次日开盘≥涨停价视为买不进剔除）；T+N 开盘卖出；扣双边 0.3%。
  与生产 _trade_ret 的差异：无跌停顺延/停牌细判——正式版走 backtest_lib，本脚本仅初筛方向。

输出：控制台对比 + raw_data/ensemble_fusion_prelim_report.json
"""
import os
import sys
import json
import glob
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "ensemble_fusion_prelim_report.json")

TOP_N = 5
K_RRF = 60
COST = 0.003
HOLDS = (5, 10)


def log(m):
    print(m, flush=True)


def avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def load_kline(code):
    p = os.path.join(RAW, "kline_cache", code + ".json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    return d if isinstance(d, list) else (d.get("data") or d.get("kline") or [])


_KC = {}
def kline(code):
    if code not in _KC:
        _KC[code] = load_kline(code)
    return _KC[code]


def fwd_ret(code, dstr, hold):
    """信号日 dstr（T 日收盘定名单）→ T+1 开盘买入，T+1+hold 开盘卖出，扣双边 0.3%。
    次日开盘 ≥ 涨停价（按板别幅度精确判定）→ 买不进，None。"""
    recs = kline(code)
    if not recs:
        return None
    idx = None
    for i, r in enumerate(recs):
        if r.get("date") == dstr:
            idx = i
            break
    if idx is None or idx + 1 + hold >= len(recs):
        return None
    b_prev = recs[idx]
    b_in = recs[idx + 1]
    o1 = b_in.get("open")
    if not o1 or o1 <= 0 or b_in.get("volume") == 0:
        return None
    prev = b_prev.get("close")
    if prev and prev > 0:
        c6 = str(code)
        ratio = 0.20 if c6.startswith(("300", "301", "688")) else (
            0.30 if c6.startswith(("43", "83", "87", "88", "92")) else 0.10)
        if o1 >= round(prev * (1 + ratio), 2) - 1e-6:
            return None          # 一字/开盘即涨停，买不进
    px = recs[idx + 1 + hold].get("open")
    if not px or px <= 0:
        return None
    return px / o1 - 1.0 - COST


def main():
    log("=" * 78)
    log("  多策略 Ensemble 初步证据回测（A 因子榜 / B 强势跟踪 / C FF3 → RRF 融合）")
    log("=" * 78)

    # A 路：因子榜每日 Top10（按 rank）
    A = {}
    for f in glob.glob(os.path.join(RAW, "history", "top10_daily_*.json")):
        ds = os.path.basename(f)[12:20]
        if not ds.isdigit():
            continue
        try:
            d = json.load(open(f))
            lst = [(str(x.get("code") or "").zfill(6), int(x.get("rank") or 99))
                   for x in (d.get("top10") or []) if x.get("code")]
            lst = [x for x in lst if x[1] <= 10]
            if lst:
                A[ds] = lst
        except Exception:
            continue

    # B 路：强势跟踪每日新选
    B = {}
    im = json.load(open(os.path.join(RAW, "ima_strong_history_v2.json")))
    for s in (im.get("stocks") or []):
        fs = (s.get("first_selected") or "")[:10]
        if fs:
            B.setdefault(fs.replace("-", ""), set()).add(str(s.get("code") or "").zfill(6))

    # C 路：FF3
    C = {}
    try:
        ff = json.load(open(os.path.join(RAW, "ff3_ranksum_history.json")))
        for ds, sig in (ff.get("signals") or {}).items():
            codes = [str(x.get("code") or "").zfill(6) for x in (sig if isinstance(sig, list) else sig.get("picks") or [])]
            C[ds.replace("-", "")] = codes
    except Exception as e:
        log("⚠️ FF3 读取失败：%s" % e)

    log("A 因子榜：%d 天 | B 强势跟踪：%d 批 | C FF3：%d 天" % (len(A), len(B), len(C)))

    def rrf(ds):
        """当日三路 RRF 分 → Top5；仅 A 可用返回 None（≡A5 无信息）。"""
        lists = []
        if ds in A:
            lists.append([c for c, _r in sorted(A[ds], key=lambda x: x[1])])
        if ds in B:
            lists.append(sorted(B[ds]))
        if ds in C:
            lists.append(C[ds])
        if len(lists) < 2:
            return None
        sc = {}
        for L in lists:
            for i, c in enumerate(L):
                sc[c] = sc.get(c, 0.0) + 1.0 / (K_RRF + i + 1)
        return [c for c, _s in sorted(sc.items(), key=lambda kv: -kv[1])][:TOP_N]

    common = sorted(set(A) & set(B))
    log("重叠信号日（A∩B）：%s" % ", ".join(common))

    res = {k: {h: [] for h in HOLDS} for k in ("A5", "Ball", "RRF5")}
    paired = {h: [] for h in HOLDS}
    n_rrf_diff = 0
    for ds in common:
        dstr = "%s-%s-%s" % (ds[:4], ds[4:6], ds[6:])
        a5 = [c for c, _r in sorted(A[ds], key=lambda x: x[1])][:TOP_N]
        bl = sorted(B[ds])
        r5 = rrf(ds)
        for h in HOLDS:
            ra = [fwd_ret(c, dstr, h) for c in a5]
            ra = [x for x in ra if x is not None]
            rb = [fwd_ret(c, dstr, h) for c in bl]
            rb = [x for x in rb if x is not None]
            if ra:
                res["A5"][h].append(avg(ra))
            if rb:
                res["Ball"][h].append(avg(rb))
            if r5:
                rr = [fwd_ret(c, dstr, h) for c in r5]
                rr = [x for x in rr if x is not None]
                if rr:
                    res["RRF5"][h].append(avg(rr))
        if r5 and r5 != a5:
            n_rrf_diff += 1
            for h in HOLDS:
                ra = [x for x in (fwd_ret(c, dstr, h) for c in a5) if x is not None]
                rr = [x for x in (fwd_ret(c, dstr, h) for c in r5) if x is not None]
                if ra and rr:
                    paired[h].append(avg(rr) - avg(ra))

    def pct(x):
        return "--" if x is None else "%+.2f%%" % (x * 100)

    log("")
    log("%-6s %-6s %12s %8s %6s" % ("方案", "持有", "均净收益/笔", "胜率", "日数"))
    summary = {}
    for k in ("A5", "Ball", "RRF5"):
        for h in HOLDS:
            xs = res[k][h]
            a = avg(xs)
            wr = sum(1 for x in xs if x > 0) / len(xs) * 100 if xs else None
            log("%-6s T+%-4d %12s %8s %6d" % (k, h, pct(a),
                ("%.0f%%" % wr) if wr is not None else "--", len(xs)))
            summary[k] = summary.get(k, {})
            summary[k][h] = {"avg_ret": a, "winrate": wr, "n": len(xs)}

    log("")
    log("RRF 与 A5 名单不同的天数：%d/%d" % (n_rrf_diff, len(common)))
    log("配对（RRF5 − A5，仅名单不同日）：")
    for h in HOLDS:
        d = paired[h]
        wr = sum(1 for x in d if x > 0) / len(d) * 100 if d else None
        log("  T+%d：Δ=%s  配对胜率=%s  n=%d"
            % (h, pct(avg(d)), ("%.0f%%" % wr) if wr is not None else "--", len(d)))

    # 判定（初步）：RRF 在 T+5 且 T+10 配对均 >0 才算方向为正
    d5 = avg(paired[5]) or 0
    d10 = avg(paired[10]) or 0
    verdict = "POSITIVE方向为正→可进影子流" if (d5 > 0 and d10 > 0) else "NEGATIVE/不足→暂缓建生产Ensemble"
    log("")
    log("⇒ 初步判定：%s（样本仅 %d 重叠日，非最终结论）" % (verdict, len(common)))

    out = {
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "Ensemble rank-fusion 初步证据（主人令：确认有提升才动手）",
        "evidence_boundary": "A 93天 / B 10批 / C 2天；重叠日=%d" % len(common),
        "common_days": common, "rrf_diff_days": n_rrf_diff,
        "summary": summary,
        "paired": {str(h): {"mean_delta": avg(paired[h]),
                             "winrate": (sum(1 for x in paired[h] if x > 0) / len(paired[h]) * 100) if paired[h] else None,
                             "n": len(paired[h])} for h in HOLDS},
        "verdict_prelim": verdict,
        "caveat": "样本极小仅方向性参考；正式准入须真实信号流≥30信号日",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("[ok] %s" % OUT)


if __name__ == "__main__":
    main()
