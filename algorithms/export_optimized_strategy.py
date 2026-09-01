#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_optimized_strategy.py — 将 backtest_tdx.json 中的优化策略汇总导出为站点可读的 JSON
============================================================================================
用于在「逻辑详解」/「运维」面板展示 ①+②+③ 优化策略效果：
  ① 持仓周期纪律（最长 10d）
  ② ≥3 信号共振过滤
  ③ 市场 regime 门控（仅在 grind/panic 段开仓）
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
RAW_DIR = os.path.join(ROOT, "raw_data")
SRC = os.path.join(RAW_DIR, "backtest_tdx.json")
OUT = os.path.join(RAW_DIR, "optimized_strategy.json")


def main():
    if not os.path.exists(SRC):
        print(f"⚠️ {SRC} 不存在，跳过")
        sys.exit(1)

    bt = json.load(open(SRC, encoding="utf-8"))
    opt = bt.get("optimized_summary")
    if not opt:
        print("⚠️ backtest_tdx.json 中无 optimized_summary，先运行 backtest_tdx.py")
        sys.exit(1)

    result = {
        "calc_time": bt.get("calc_time"),
        "update_time": bt.get("calc_time"),
        "method": "①持仓周期≤10d + ②≥3信号共振 + ③市场regime门控(grind/panic)",
        "backtest_sample": {
            "stocks_analyzed": bt.get("stocks_analyzed"),
            "gold_pool_size": bt.get("gold_pool_size"),
            "survivor_bias_warning": bt.get("survivor_bias_warning", False),
        },
        "optimized": {
            "label": opt.get("label"),
            "total_signals": opt.get("total"),
            "periods": {},
        },
        "baseline_ge3": {},
        "config": opt.get("config", {}),
    }

    # 提取优化策略各周期
    for d in [5, 10]:
        wr = opt.get(f"win_rate_{d}d")
        ar = opt.get(f"avg_return_{d}d")
        if wr is not None:
            result["optimized"]["periods"][f"T+{d}"] = {
                "win_rate_pct": wr,
                "avg_return_pct": ar,
            }

    # 提取 baseline ge3 作为对比
    ge3 = bt.get("summary", {}).get("ge3_signals", {})
    if ge3:
        for d in [5, 10]:
            wr = ge3.get(f"win_rate_{d}d")
            ar = ge3.get(f"avg_return_{d}d")
            if wr is not None:
                result["baseline_ge3"][f"T+{d}"] = {
                    "win_rate_pct": wr,
                    "avg_return_pct": ar,
                }
        result["baseline_ge3"]["total_signals"] = ge3.get("total")

    # 当前市场 regime（用于前端提示是否处于开仓段）
    try:
        sys.path.insert(0, BASE)
        from backtest_tdx import _merge_market_regime
        regime_map = _merge_market_regime()
        if regime_map:
            latest_date = max(regime_map.keys())
            result["current_regime"] = {
                "date": latest_date,
                "regime": regime_map[latest_date],
                "open_position": regime_map[latest_date] in ("grind", "panic"),
            }
    except Exception as e:
        result["current_regime_error"] = str(e)

    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ 已导出: {OUT}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
