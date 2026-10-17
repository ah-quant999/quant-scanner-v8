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
    # 🔴 2026-09-14 小九审计修复：原实现在缺 optimized_summary 时直接 sys.exit(1)。
    #   而本脚本位于 run_algorithms 的 ORDER / STAGES["E"]，退出码非 0 会让 E 批链
    #   被判定残缺；更严重的是本脚本是**全站择时唯一真源** current_regime 的唯一产出方
    #   （index.html：「全站择时【唯一】以 OPTIMIZED_STRATEGY.current_regime 为准」）
    #   ⇒ 硬退 = 前端择时永远卡在旧值（假死），且无人知晓。
    #   现改为「降级但仍产出」：优化策略部分标 data_ok=false（不写 0 冒充），
    #   current_regime 照常计算写入，退出码归 0，并保留上游 audit note 便于定位。
    _opt_missing = not opt
    if _opt_missing:
        print("⚠️ backtest_tdx.json 中无 optimized_summary（上游 0 样本或未跑）"
              "→ 优化策略部分 data_ok=false，current_regime 照常产出（不再硬退）")
    _opt = opt or {}

    result = {
        "calc_time": bt.get("calc_time"),
        "update_time": bt.get("calc_time"),
        "method": "①持仓周期≤10d + ②≥3信号共振 + ③市场regime门控(grind/panic)",
        "backtest_sample": {
            "stocks_analyzed": bt.get("stocks_analyzed"),
            "gold_pool_size": bt.get("gold_pool_size"),
            "survivor_bias_warning": bt.get("survivor_bias_warning", False),
            # 2026-09-14：口径/样本窗口随产物一起下传，避免前端拿旧值当新值
            "entry_caliber_ver": bt.get("entry_caliber_ver"),
            "signal_window": bt.get("signal_window"),
        },
        "optimized": {
            "label": _opt.get("label"),
            "total_signals": _opt.get("total", 0) or 0,
            "periods": {},
            # data_ok=false 时前端应显示「暂无样本」，绝不用 0 冒充胜率
            "data_ok": bool(_opt and (_opt.get("total") or 0) > 0),
            **({"note": bt.get("optimized_summary_note")} if _opt_missing else {}),
        },
        "baseline_ge3": {},
        "config": _opt.get("config", {}),
    }

    # 提取优化策略各周期
    for d in [5, 10]:
        wr = _opt.get(f"win_rate_{d}d")
        ar = _opt.get(f"avg_return_{d}d")
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
    # 🔴 2026-09-11 A 类修复（A3 统一失败语义 + 去重复实现）：
    #   原实现 `from backtest_tdx import _merge_market_regime` 自带**另一套** regime 计算，
    #   与 regime_filter 各算各的，且取 max(keys) 后**不校验新鲜度**。实测同日三方结论：
    #     backtest_tdx 口径 → grind(09-10)、open_position=true  ← 前端 v8MarketGate 的"可开仓"
    #     regime_filter     → None（baostock 黑名单）           ← final_recommend 的"观望"
    #     generate_top10    → "stabilize"（硬编码兜底）
    #   现统一走 regime_filter 单一真源；取数失败时 regime=null → 前端显示"暂无数据"，
    #   绝不用几天前的缓存冒充"可开仓"。
    try:
        sys.path.insert(0, BASE)
        from regime_filter import get_current_regime_safe
        _ri, _rok, _rreason = get_current_regime_safe()
        result["current_regime"] = {
            "date": (_ri or {}).get("date") if _rok else None,
            "regime": (_ri or {}).get("regime") if _rok else None,
            "open_position": bool(_rok and (_ri or {}).get("regime") in ("grind", "panic")),
            "ok": _rok,
            "reason": _rreason,
        }
    except Exception as e:
        result["current_regime"] = {"date": None, "regime": None, "open_position": False,
                                    "ok": False, "reason": f"exception:{e}"}

    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ 已导出: {OUT}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
