#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factor_validate.py — 因子结论稳健性检验（2026-08-28）

factor_ic_analysis 暴露了三个惊人结论，但不能直接采信：
  · T20 样本仅占 51%，长持有期样本几乎全部来自 6-7 月 → 幸存者/时段偏差
  · 高分组跑输低分组，可能是时段集中造成的假象

本脚本做三项检验：
  A. 固定样本对比：只保留能算满 T20 的信号，重新比较各持有期
  B. 分月稳定性：每个因子在不同月份的 IC 是否同号
  C. 高/低分组分月对比：跑输是否在各个月份都成立

输出 raw_data/factor_validate_report.json
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_ic_analysis import (  # noqa: E402
    collect_signals, build_records, future_returns, spearman, HOLDS,
    FACTORS, COST_ROUNDTRIP, _mean,
)

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT_JSON = os.path.join(ROOT, "raw_data", "factor_validate_report.json")


def _log(m=""):
    print(m, flush=True)


def month_of(iso):
    return iso[:7]


def stat(vals):
    if not vals:
        return None
    wins = sum(1 for v in vals if v > 0)
    return {
        "n": len(vals),
        "win": round(wins / len(vals) * 100, 1),
        "avg": round(_mean(vals), 3),
    }


def main():
    _log("=" * 74)
    _log(f"  因子结论稳健性检验   —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 74)

    ins, _ = collect_signals(None)
    recs, skipped = build_records(ins)
    _log(f"\n  可回测信号 {len(recs)} 条（跳过 {skipped}）")

    by_month = defaultdict(list)
    for r in recs:
        by_month[month_of(r["_date"])].append(r)
    _log("  分月样本: " + "  ".join(f"{m}={len(v)}" for m, v in sorted(by_month.items())))

    result = {"update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "n_signals": len(recs), "months": {}}

    # ── A. 固定样本：只保留有 T20 的信号 ──────────────────────────────
    fixed = [r for r in recs if 20 in r["_returns"]]
    _log(f"\n{'─'*74}")
    _log(f"  【检验 A】固定样本对比（只保留能算满 T20 的 {len(fixed)} 条，排除幸存者偏差）")
    _log(f"  {'持有期':<8}{'样本':>6}{'胜率':>9}{'平均收益':>11}")
    rows_a = {}
    for n in HOLDS:
        vals = [r["_returns"][n] for r in fixed if n in r["_returns"]]
        s = stat(vals)
        if s:
            rows_a[f"T{n}"] = s
            _log(f"  T{n:<7}{s['n']:>6}{s['win']:>8.1f}%{s['avg']:>10.3f}%")
    result["fixed_sample"] = {"n": len(fixed), "periods": rows_a}

    # ── B. 分月 IC 稳定性 ─────────────────────────────────────────────
    _log(f"\n{'─'*74}")
    _log("  【检验 B】分月 IC 稳定性（同号率越高，因子越可信）")
    months = sorted(by_month)
    watch = ["total_score", "pct_chg_20d", "score_form", "score_base",
             "score_quality", "score_enhance", "sig_count"]
    _log(f"  {'因子':<16}{'T5各月IC':<44}{'同号':>6}")
    rows_b = {}
    for f in watch:
        cells, signs = [], []
        for m in months:
            seg = by_month[m]
            xs = [r[f] for r in seg if 5 in r["_returns"]]
            ys = [r["_returns"][5] for r in seg if 5 in r["_returns"]]
            if len(xs) < 8:
                cells.append("   --  ")
                continue
            ic = spearman(xs, ys)
            if ic is None:
                cells.append("   --  ")
                continue
            cells.append(f"{ic:+.3f}")
            signs.append(1 if ic > 0 else -1)
        if signs:
            pos = sum(1 for s in signs if s > 0)
            rate = max(pos, len(signs) - pos) / len(signs) * 100
            rows_b[f] = {"ic_T5_by_month": dict(zip(months, cells)),
                         "same_sign_rate": round(rate, 1)}
            _log(f"  {f:<16}{' '.join(cells):<44}{rate:>5.0f}%")
        else:
            _log(f"  {f:<16}{' '.join(cells):<44}{'  n/a':>6}")
    result["monthly_ic"] = rows_b

    # ── C. 高/低分组分月对比 ──────────────────────────────────────────
    _log(f"\n{'─'*74}")
    _log("  【检验 C】高分组 vs 低分组，分月对比（T5 平均收益）")
    _log(f"  {'月份':<10}{'样本':>6}{'高分组均':>11}{'低分组均':>11}{'差值':>10}   判定")
    rows_c = {}
    for m in months:
        seg = sorted(by_month[m], key=lambda r: -r["total_score"])
        if len(seg) < 10:
            _log(f"  {m:<10}{len(seg):>6}   样本不足，跳过")
            continue
        k = max(2, len(seg) // 3)
        hi = [r["_returns"][5] for r in seg[:k] if 5 in r["_returns"]]
        lo = [r["_returns"][5] for r in seg[-k:] if 5 in r["_returns"]]
        if not hi or not lo:
            continue
        a, b = _mean(hi), _mean(lo)
        diff = a - b
        verdict = "高分胜" if diff > 0.5 else ("低分胜" if diff < -0.5 else "无差异")
        rows_c[m] = {"n": len(seg), "high_avg": round(a, 3), "low_avg": round(b, 3),
                     "diff": round(diff, 3), "verdict": verdict}
        _log(f"  {m:<10}{len(seg):>6}{a:>10.3f}%{b:>10.3f}%{diff:>9.3f}%   {verdict}")
    result["monthly_hi_lo"] = rows_c

    # ── D. pct_chg_20d 方向检验（当前代码给 20~50% 涨幅加分，对不对？）──
    _log(f"\n{'─'*74}")
    _log("  【检验 D】20日涨幅分层 → T5/T10 平均收益（验证加分方向）")
    buckets = [(-999, 0, "亏损<0%"), (0, 10, "0~10%"), (10, 20, "10~20%"),
               (20, 35, "20~35%"), (35, 50, "35~50%"), (50, 9999, "≥50%")]
    _log(f"  {'区间':<12}{'样本':>6}{'T5均':>10}{'T10均':>10}   当前代码")
    cur = {"亏损<0%": "+0", "0~10%": "+0", "10~20%": "+0",
           "20~35%": "+3", "35~50%": "+5", "≥50%": "-5"}
    rows_d = {}
    for lo_b, hi_b, label in buckets:
        seg = [r for r in recs if lo_b <= r["pct_chg_20d"] < hi_b]
        if not seg:
            continue
        t5 = stat([r["_returns"][5] for r in seg if 5 in r["_returns"]])
        t10 = stat([r["_returns"][10] for r in seg if 10 in r["_returns"]])
        a5 = t5["avg"] if t5 else 0
        a10 = t10["avg"] if t10 else 0
        rows_d[label] = {"n": len(seg), "t5": a5, "t10": a10, "current": cur.get(label, "?")}
        _log(f"  {label:<12}{len(seg):>6}{a5:>9.3f}%{a10:>9.3f}%   {cur.get(label,'?')}")
    result["pct20_buckets"] = rows_d

    # ── E. score_form 分层（唯一的正向因子，验证单调性）────────────────
    _log(f"\n{'─'*74}")
    _log("  【检验 E】技术形态分 score_form 分层 → T5 表现（验证单调性）")
    _log(f"  {'form分':<10}{'样本':>6}{'T5胜率':>9}{'T5均':>10}")
    rows_e = {}
    for lo_b, hi_b in [(-99, 0), (0, 5), (5, 9), (9, 12), (12, 99)]:
        seg = [r for r in recs if lo_b <= r["score_form"] < hi_b]
        if not seg:
            continue
        s = stat([r["_returns"][5] for r in seg if 5 in r["_returns"]])
        if not s:
            continue
        rows_e[f"[{lo_b},{hi_b})"] = s
        _log(f"  [{lo_b:>3},{hi_b:>3}){'':<3}{s['n']:>6}{s['win']:>8.1f}%{s['avg']:>9.3f}%")
    result["form_buckets"] = rows_e

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log(f"\n  ✅ 检验报告已写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
