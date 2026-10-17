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
IDX_MULTI_PATH = os.path.join(ROOT, "raw_data", "index_history_multi.json")
OUT_JSON = os.path.join(ROOT, "raw_data", "alpha_vs_beta_report.json")


def _log(m=""):
    print(m, flush=True)


def _load_rows_from_klines(klines):
    rows = []
    for r in klines:
        try:
            rows.append((r["d"], float(r["o"]), float(r["c"])))
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x[0])
    return rows


def load_indices():
    """加载所有可用基准指数。优先多基准文件；失败回退上证指数单文件。"""
    out = {}
    # 1) 多基准文件
    if os.path.exists(IDX_MULTI_PATH):
        try:
            d = json.load(open(IDX_MULTI_PATH, encoding="utf-8"))
            for code, sec in d.get("data", {}).items():
                rows = _load_rows_from_klines(sec.get("klines", []))
                if rows:
                    meta = sec.get("meta", {})
                    out[code] = {"name": meta.get("name", code), "rows": rows}
        except Exception as e:
            _log(f"  ⚠️ 多基准文件读取失败: {e}")
    # 2) 回退单文件上证指数
    if not out and os.path.exists(IDX_PATH):
        try:
            d = json.load(open(IDX_PATH, encoding="utf-8"))
            rows = _load_rows_from_klines(d.get("klines", []))
            if rows:
                meta = d.get("meta", {})
                code = meta.get("symbol", "000001.SH")
                out[code] = {"name": meta.get("name", "上证指数"), "rows": rows}
        except Exception as e:
            _log(f"  ⚠️ 上证指数文件读取失败: {e}")
    return out


_INDICES = None


def idx_rows(bench_code="000001.SH"):
    global _INDICES
    if _INDICES is None:
        _INDICES = load_indices()
    return _INDICES.get(bench_code, {}).get("rows", [])


def bench_return(signal_date, n, bench_code="000001.SH", cost=COST_ROUNDTRIP):
    """指定基准在同一窗口的收益，口径与个股完全一致"""
    rows = idx_rows(bench_code)
    if not rows:
        return None
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


def _analyze_one_benchmark(fixed, bench_code, bench_name):
    """对单一基准计算持有期/分月/分层结果"""
    periods = {}
    _log(f"\n  ── 基准：{bench_name} ({bench_code}) ──")
    _log(f"  {'持有期':<6}{'个股胜率':>9}{'个股均':>10}{'基准均':>10}{'超额均':>10}{'超额胜率':>10}")
    for n in HOLDS:
        ex, ab = [], []
        for r in fixed:
            if n not in r["_returns"]:
                continue
            b = bench_return(r["_date"], n, bench_code=bench_code)
            if b is None:
                continue
            ex.append(r["_returns"][n])          # 个股绝对收益（已扣成本）
            ab.append(r["_returns"][n] - b)      # 超额
        if not ex:
            continue
        s_ex, s_ab = stat(ex), stat(ab)
        periods[f"T{n}"] = {"stock": s_ex, "excess": s_ab,
                            "bench_avg": round(_mean(ex) - _mean(ab), 3)}
        _log(f"  T{n:<5}{s_ex['win']:>8.1f}%{s_ex['avg']:>9.3f}%"
             f"{s_ex['avg']-s_ab['avg']:>9.3f}%{s_ab['avg']:>9.3f}%{s_ab['win']:>9.1f}%")

    # 分月超额（T10）
    by_month = defaultdict(list)
    for r in fixed:
        by_month[r["_date"][:7]].append(r)
    monthly = {}
    for m in sorted(by_month):
        ex, ab = [], []
        for r in by_month[m]:
            if 10 not in r["_returns"]:
                continue
            b = bench_return(r["_date"], 10, bench_code=bench_code)
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

    # 高/低分组超额
    seg = sorted(fixed, key=lambda r: -r["total_score"])
    k = max(5, len(seg) // 3)
    tiers = {}
    for label, part in (("TOP1/3", seg[:k]), ("BOTTOM1/3", seg[-k:])):
        ex, ab = [], []
        for r in part:
            if 10 not in r["_returns"]:
                continue
            b = bench_return(r["_date"], 10, bench_code=bench_code)
            if b is None:
                continue
            ex.append(r["_returns"][10])
            ab.append(r["_returns"][10] - b)
        if not ex:
            continue
        tiers[label] = {"n": len(ex), "stock_avg": round(_mean(ex), 3),
                        "excess_avg": round(_mean(ab), 3),
                        "win": round(sum(1 for x in ab if x > 0) / len(ab) * 100, 1)}

    return {"periods": periods, "monthly_T10": monthly, "tiers_T10": tiers,
            "benchmark_name": bench_name, "benchmark_code": bench_code}


def main():
    indices = load_indices()
    primary_code = "000001.SH"
    if primary_code not in indices:
        primary_code = next(iter(indices.keys())) if indices else None
    if not primary_code:
        _log("❌ 无可用基准指数")
        return

    _log("=" * 76)
    _log(f"  超额收益检验（主基准 = {indices[primary_code]['name']}）  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"  成本口径：个股与基准【同样】扣除往返 {COST_ROUNDTRIP*100:.2f}%，保证可比")
    _log(f"  多基准：{', '.join(f'{v['name']}({k})' for k, v in indices.items())}")
    _log("=" * 76)

    ins, _ = collect_signals(None)
    recs, skipped = build_records(ins)
    _log(f"\n  可回测信号 {len(recs)} 条")

    # 固定样本：只保留能算满 T10 的，避免长短样本混在一起
    fixed = [r for r in recs if 10 in r["_returns"]]
    _log(f"  固定样本（可算满 T10）：{len(fixed)} 条\n")

    if not fixed:
        _log("  ❌ 无可回测样本，终止")
        return

    multi = {}
    for code, info in indices.items():
        multi[code] = _analyze_one_benchmark(fixed, code, info["name"])

    primary = multi[primary_code]
    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark": f"{indices[primary_code]['name']} {indices[primary_code].get('symbol', primary_code.lower().replace('.', ''))}",
        "n_fixed": len(fixed),
        "periods": primary["periods"],
        "monthly_T10": primary["monthly_T10"],
        "tiers_T10": primary["tiers_T10"],
        "multi_benchmark": multi,
    }

    # 打印分月（主基准）
    _log(f"\n{'─'*76}")
    _log("  分月超额收益（T10，成本已扣）— 主基准")
    _log(f"  {'月份':<10}{'样本':>6}{'个股均':>10}{'基准均':>10}{'超额均':>10}   判定")
    for m, d in sorted(primary["monthly_T10"].items()):
        _log(f"  {m:<10}{d['n']:>6}{d['stock_avg']:>9.3f}%"
             f"{d['stock_avg']-d['excess_avg']:>9.3f}%{d['excess_avg']:>9.3f}%   {d['verdict']}")

    # 打印分层（主基准）
    _log(f"\n{'─'*76}")
    _log("  高分组 vs 低分组 —— 超额收益 T10（评分是否有真实 alpha）— 主基准")
    for label, d in primary["tiers_T10"].items():
        _log(f"  {label:<10} n={d['n']:<4} 个股 {d['stock_avg']:>8.3f}%"
             f"   超额 {d['excess_avg']:>8.3f}%   超额胜率 {d['win']:>5.1f}%")

    # 打印多基准 T10 对比
    _log(f"\n{'─'*76}")
    _log("  多基准 T+10 超额对比（判断 +6% 是 alpha 还是风格 beta）")
    _log(f"  {'基准':<14}{'个股均':>10}{'基准均':>10}{'超额均':>10}{'超额胜率':>10}")
    for code, res in multi.items():
        t10 = res["periods"].get("T10", {})
        s_ex = t10.get("stock", {})
        s_ab = t10.get("excess", {})
        if s_ex and s_ab:
            _log(f"  {res['benchmark_name']:<14}"
                 f"{s_ex.get('avg', 0):>9.3f}%"
                 f"{s_ex.get('avg', 0)-s_ab.get('avg', 0):>9.3f}%"
                 f"{s_ab.get('avg', 0):>9.3f}%"
                 f"{s_ab.get('win', 0):>9.1f}%")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log(f"\n  ✅ 报告已写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
