#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alpha_vs_beta.py — 超额收益检验（2026-08-28）

问题：信号 T10 平均 +8.7%，看着很好。但如果同期上证也涨了 8%，
      那就只是 beta（买了大盘），不是策略的 alpha。

做法：以【上证指数 sh000001】为基准，对每个信号计算同一入场/出场
      窗口的基准收益，超额 = 个股收益 − 基准收益。

输出 raw_data/alpha_vs_beta_report.json
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, BASE)

from factor_ic_analysis import (  # noqa: E402
    collect_signals, build_records, get_kline, _bisect_after,
    HOLDS, COST_ROUNDTRIP, _mean, spearman,
)

IDX_PATH = os.path.join(ROOT, "raw_data", "index_history.json")
OUT_JSON = os.path.join(ROOT, "raw_data", "alpha_vs_beta_report.json")


def _log(m=""):
    print(m, flush=True)


def load_index():
    d = json.load(open(IDX_PATH, encoding="utf-8"))
    rows = []
    for r in d.get("klines", []):
        try:
            rows.append((r["d"], float(r["o"]), float(r["c"])))
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x[0])
    return rows


_IDX = None


def idx_rows():
    global _IDX
    if _IDX is None:
        _IDX = load_index()
    return _IDX


def bench_return(signal_date, n, cost=COST_ROUNDTRIP):
    """基准（上证指数）在同一窗口的收益，口径与个股完全一致"""
    rows = idx_rows()
    i = _bisect_after(rows, signal_date)
    if i < 0:
        return None
    entry = rows[i][1]
    j = i + n - 1
    if j >= len(rows) or entry <= 0:
        return None
    return (rows[j][2] - entry) / entry * 100 - cost * 100


def stat(v):
    if not v:
        return None
    return {"n": len(v),
            "win": round(sum(1 for x in v if x > 0) / len(v) * 100, 1),
            "avg": round(_mean(v), 3)}


def main():
    _log("=" * 76)
    _log(f"  超额收益检验（基准 = 上证指数）  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"  成本口径：个股与基准【同样】扣除往返 {COST_ROUNDTRIP*100:.2f}%，保证可比")
    _log("=" * 76)

    ins, _ = collect_signals(None)
    recs, skipped = build_records(ins)
    _log(f"\n  可回测信号 {len(recs)} 条")

    # 固定样本：只保留能算满 T10 的，避免长短样本混在一起
    fixed = [r for r in recs if 10 in r["_returns"]]
    _log(f"  固定样本（可算满 T10）：{len(fixed)} 条\n")

    result = {"update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "benchmark": "上证指数 sh000001", "n_fixed": len(fixed), "periods": {}}

    _log(f"  {'持有期':<6}{'个股胜率':>9}{'个股均':>10}{'基准均':>10}{'超额均':>10}{'超额胜率':>10}")
    for n in HOLDS:
        ex, ab = [], []
        for r in fixed:
            if n not in r["_returns"]:
                continue
            b = bench_return(r["_date"], n)
            if b is None:
                continue
            ex.append(r["_returns"][n])          # 个股绝对收益（已扣成本）
            ab.append(r["_returns"][n] - b)      # 超额
        if not ex:
            continue
        s_ex, s_ab = stat(ex), stat(ab)
        result["periods"][f"T{n}"] = {"stock": s_ex, "excess": s_ab,
                                      "bench_avg": round(_mean(ex) - _mean(ab), 3)}
        _log(f"  T{n:<5}{s_ex['win']:>8.1f}%{s_ex['avg']:>9.3f}%"
             f"{s_ex['avg']-s_ab['avg']:>9.3f}%{s_ab['avg']:>9.3f}%{s_ab['win']:>9.1f}%")

    # 分月超额（T10）
    _log(f"\n{'─'*76}")
    _log("  分月超额收益（T10，成本已扣）")
    by_month = defaultdict(list)
    for r in fixed:
        by_month[r["_date"][:7]].append(r)
    _log(f"  {'月份':<10}{'样本':>6}{'个股均':>10}{'基准均':>10}{'超额均':>10}   判定")
    monthly = {}
    for m in sorted(by_month):
        ex, ab = [], []
        for r in by_month[m]:
            if 10 not in r["_returns"]:
                continue
            b = bench_return(r["_date"], 10)
            if b is None:
                continue
            ex.append(r["_returns"][10])
            ab.append(r["_returns"][10] - b)
        if not ex:
            continue
        a_ex, a_ab = _mean(ex), _mean(ab)
        verdict = "有超额" if a_ab > 1.0 else ("跑输" if a_ab < -1.0 else "持平")
        monthly[m] = {"n": len(ex), "stock_avg": round(a_ex, 3),
                      "excess_avg": round(a_ab, 3), "verdict": verdict}
        _log(f"  {m:<10}{len(ex):>6}{a_ex:>9.3f}%{a_ex-a_ab:>9.3f}%{a_ab:>9.3f}%   {verdict}")
    result["monthly_T10"] = monthly

    # 高/低分组超额（关键：评分到底有没有 alpha）
    _log(f"\n{'─'*76}")
    _log("  高分组 vs 低分组 —— 超额收益 T10（评分是否有真实 alpha）")
    seg = sorted(fixed, key=lambda r: -r["total_score"])
    k = max(5, len(seg) // 3)
    tiers = {}
    for label, part in (("TOP1/3", seg[:k]), ("BOTTOM1/3", seg[-k:])):
        ex, ab = [], []
        for r in part:
            if 10 not in r["_returns"]:
                continue
            b = bench_return(r["_date"], 10)
            if b is None:
                continue
            ex.append(r["_returns"][10])
            ab.append(r["_returns"][10] - b)
        if not ex:
            continue
        tiers[label] = {"n": len(ex), "stock_avg": round(_mean(ex), 3),
                        "excess_avg": round(_mean(ab), 3),
                        "win": round(sum(1 for x in ab if x > 0) / len(ab) * 100, 1)}
        _log(f"  {label:<10} n={len(ex):<4} 个股 {_mean(ex):>8.3f}%   超额 {_mean(ab):>8.3f}%"
             f"   超额胜率 {sum(1 for x in ab if x>0)/len(ab)*100:>5.1f}%")
    result["tiers_T10"] = tiers

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log(f"\n  ✅ 报告已写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
