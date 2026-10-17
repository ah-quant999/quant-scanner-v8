#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_ic_gate.py — Tier 1 第 1 步「IC 门禁 MVP」

读：
  - raw_data/factor_ic_report.json     # v8_factor_ic.py 产出（滚动 IC）
  - raw_data/factor_validate_report.json # v8_factor_validate.py 产出（固定样本 win）
  - raw_data/h_auto_buy_track.json（可选）# H 反推累计胜率

写：
  - raw_data/ic_gate.json  # 每日门禁状态。供 generate_top10 / gen_triple_consensus
                           # 在算分前 require 这个 gate，决定当日某策略是否出票。

MVP 原则（2026-08-29 主人放行）：
  1. 只产出门禁信号文件，**不改任何选股逻辑**——最小杠杆。
  2. 缺数据时 gate = "insufficient_data"（保守默认值，避免空仓一日）。
  3. 阈值写进文件本身，方便主人日后一句话微调：
        T1_win < min_T1_win    → gate fail（策略当日不出票）
        fixed_T1_win < X       → 准入门禁（替代样本内乐观胜率）

落地路径：
  下游消费（建议一并提交）：
   - algorithms/generate_top10.py:614 的 score_backtest 用 ic_gate.json 中的 ic_weight 做额外微调
   - algorithms/gen_triple_consensus.py / calc_crds.py 在 select 前读 gate 字段做"准出门禁"
  本脚本 v1 仅产出 JSON + 终端摘要，**消费端接入下一步执行**。
"""
import os, json, sys, time, argparse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

THRESH = {
    "min_T1_win": 45.0,        # T+1 实测胜率 < 45% 当日不出票（近于随机）
    "min_T3_win": 35.0,        # T+3 < 35% 报警但允许出（短持有场景）
    "min_T5_win": 30.0,        # T+5 < 30% 关闭策略
    "min_fixed_T1_win": 47.0,  # 滚动固定样本（防样本内乐观）< 47% 关闭
    "min_fixed_T3_win": 32.0,
    "min_n_signals": 80,       # 样本量过低不算数（保留为 insufficient_data）
}

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return default

def factor_ic_to_gate(name, ic_report):
    """从 factor_ic_report 抽 in_sample / fixed_sample 的 win_rate"""
    if not ic_report:
        return None
    # in_sample 路径：{overall: {T1: {n, win_rate, avg_return}}}
    sample_overall = ic_report.get("in_sample", {}).get("overall", {})
    # fixed_sample 路径：{periods: {T1: {n, win, avg}}}（validate_report 形态）
    fixed_periods = (ic_report.get("fixed_sample") or {}).get("periods") or {}
    n = ic_report.get("n_signals_tested") or ic_report.get("n_signals") or 0
    if not sample_overall and not fixed_periods:
        return None
    gate = "ok"
    reasons = []

    def w(d):
        return (d or {}).get("win_rate") if isinstance(d, dict) else None

    T1 = w(sample_overall.get("T1"))
    T3 = w(sample_overall.get("T3"))
    T5 = w(sample_overall.get("T5"))
    if T1 is not None and T1 < THRESH["min_T1_win"]:
        gate = "fail"; reasons.append(f"T1胜率{T1}<{THRESH['min_T1_win']}")
    if T3 is not None and T3 < THRESH["min_T3_win"] and gate == "ok":
        gate = "warn"; reasons.append(f"T3胜率{T3}<{THRESH['min_T3_win']}")
    if T5 is not None and T5 < THRESH["min_T5_win"]:
        gate = "fail"; reasons.append(f"T5胜率{T5}<{THRESH['min_T5_win']}")
    if n < THRESH["min_n_signals"]:
        gate = "insufficient_data"; reasons.append(f"样本量{n}<{THRESH['min_n_signals']}")

    def fp(d):
        return (d or {}).get("win") if isinstance(d, dict) else None
    fT1 = fp(fixed_periods.get("T1"))
    fT3 = fp(fixed_periods.get("T3"))
    fT5 = fp(fixed_periods.get("T5"))
    if fT1 is not None and fT1 < THRESH["min_fixed_T1_win"]:
        gate = "fail"; reasons.append(f"固定样本T1胜率{fT1}<{THRESH['min_fixed_T1_win']}")
    if fT3 is not None and fT3 < THRESH["min_fixed_T3_win"] and gate == "ok":
        gate = "warn"; reasons.append(f"固定样本T3胜率{fT3}<{THRESH['min_fixed_T3_win']}")

    return {
        "name": name,
        "n_signals": n,
        "T1_win": T1, "T3_win": T3, "T5_win": T5,
        "fixed_T1_win": fT1, "fixed_T3_win": fT3, "fixed_T5_win": fT5,
        "gate": gate,
        "reasons": reasons,
        # ic_weight 是给 score_backtest 的乘子：胜率高于 55% 加权，低于 50% 减权
        "ic_weight": round(min(1.5, max(0.5, 0.5 + (max([T1 or 50, fT1 or 50]) - 50) / 10)), 2),
        "update_time": ic_report.get("update_time")
    }

def track_to_gate(name, track):
    """从 *_track.json 读累计 T+N 胜率（更可信的 OOS 数据）"""
    if not track:
        return None
    return {
        "name": name,
        "T1_win": track.get("T1_win"),
        "T3_win": track.get("T3_win"),
        "T5_win": track.get("T5_win"),
        "n_signals": track.get("n_signals"),
        "update_time": track.get("update_time")
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RAW_DIR, "ic_gate.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ic_report        = load_json(os.path.join(RAW_DIR, "factor_ic_report.json"), {})
    validate_report = load_json(os.path.join(RAW_DIR, "factor_validate_report.json"), {})
    h_buy_track     = load_json(os.path.join(RAW_DIR, "h_auto_buy_track.json"), {})

    # 合并两路 IC 报告到一个总 IC 信号（ge3 / crds 等策略的输入统一）
    merged_ic = {
        "n_signals_tested": ic_report.get("n_signals_tested"),
        "in_sample": ic_report.get("in_sample"),
        "fixed_sample": (validate_report or {}).get("fixed_sample") or ic_report.get("fixed_sample"),
        "update_time": ic_report.get("update_time")
    }

    factors = {
        "ge3":          factor_ic_to_gate("ge3", merged_ic),
        "h_auto_buy_累计": track_to_gate("h_auto_buy_累计", h_buy_track)
    }

    # 决策摘要
    any_fail = any((f or {}).get("gate") == "fail" for f in factors.values() if f)
    any_warn = any((f or {}).get("gate") == "warn" for f in factors.values() if f)
    insuff  = any((f or {}).get("gate") == "insufficient_data" for f in factors.values() if f)

    if any_fail:
        action = "fail"
    elif any_warn:
        action = "warn"
    elif insuff:
        action = "insufficient_data"
    else:
        action = "ok"

    gate = {
        "policy": "ic_gate_v1_conservative",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "thresholds": THRESH,
        "overall_action": action,
        "factors": factors,
        "todo": [
            "下游接入 generate_top10.py：score_backtest 改读 ic_gate.json 的 ic_weight 做微调",
            "下游接入 gen_triple_consensus / calc_crds：select 前读 overall_action 做准出门禁",
            "src 仅产出 JSON，**不改选股逻辑**——MVP"
        ]
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(json.dumps(gate, ensure_ascii=False, indent=2))
    if not args.quiet:
        print(f"[ok] ic_gate.json → {args.out}")
        print(f"[action] overall={action}")
        for name, f in factors.items():
            if not f:
                print(f"  - {name}: missing data")
                continue
            T1 = f.get("T1_win")
            g = f.get("gate", "—")
            reasons = "; ".join(f.get("reasons") or []) or "—"
            print(f"  - {name}: T1={T1}, gate={g}, reasons=[{reasons}]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
