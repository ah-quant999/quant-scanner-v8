#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_regime_gate.py — Tier 1 第 2 步「regime 自动门控」

读：
  - raw_data/market_regime.json  # 利率 + 板块推荐框架

写：
  - raw_data/strategy_regime_gate.json

逻辑（保守 MVP）：
  - 从 market_regime.regime.label 抽 4 类：
      利率上行/利率下行/利率平稳/利率剧烈波动
  - 按主人 2026-08-19 拍板的利率上行期板块推荐框架 + alt_groups_down_regime：
      利率上行  → 红利/防御受益（ge3/crds 减弱 0.85、top5 中性 1.0）
      利率下行  → 成长受益（ge3 增强 1.10、crds 增强 1.05）
      利率平稳  → 中性（all 1.0）
      利率剧烈 → fail（策略当日不出票，市道不稳）
  - framework_match "部分匹配"/"不匹配" 时降权至 0.95/0.85。
  - 与 ic_gate.json 类似：仅产出门禁信号，**不改选股逻辑**。
"""
import os, json, sys, argparse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

# 利率 regime → 策略乘子（主人 2026-08-19 拍板的板块框架的选股层映射）
REGIME_MAP = {
    "利率上行":    {"ge3": 0.85, "top5": 1.00, "h_auto_buy": 0.90, "crds": 0.85},
    "利率下行":    {"ge3": 1.10, "top5": 1.00, "h_auto_buy": 1.10, "crds": 1.05},
    "利率平稳":    {"ge3": 1.00, "top5": 1.00, "h_auto_buy": 1.00, "crds": 1.00},
    "利率剧烈":    {"ge3": 0.0,  "top5": 0.0,  "h_auto_buy": 0.0,  "crds": 0.0},  # 触发 fail
}
STRATEGIES = ["ge3", "top5", "h_auto_buy", "crds"]

def load_json(p, default):
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return default

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RAW_DIR, "strategy_regime_gate.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    mr = load_json(os.path.join(RAW_DIR, "market_regime.json"), {})
    if not mr:
        if not args.quiet:
            print("[warn] market_regime.json missing or empty → output empty gate")
        open(args.out, "w", encoding="utf-8").write(json.dumps({
            "policy": "regime_gate_v1",
            "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "regime_label": None,
            "strategies": {},
            "overall_action": "insufficient_data",
            "todo": ["market_regime.json 缺失，下一次盘后跑批后重试"]
        }, ensure_ascii=False, indent=2))
        return 0

    label = (mr.get("regime") or {}).get("label", "未知")
    confidence = (mr.get("regime") or {}).get("confidence", "—")
    framework_match = mr.get("framework_match", "—")
    base_mult = REGIME_MAP.get(label, REGIME_MAP["利率平稳"])

    # framework_match 修正
    framework_mult = 1.0
    framework_note = ""
    if "不匹配" in framework_match:
        framework_mult = 0.85; framework_note = "框架不匹配"
    elif "部分匹配" in framework_match:
        framework_mult = 0.95; framework_note = "框架部分匹配"
    else:
        framework_note = "框架匹配"

    overall_action = "ok"
    if label == "利率剧烈":
        overall_action = "fail"
    elif framework_mult < 1.0:
        overall_action = "warn"

    strategies = {}
    for s in STRATEGIES:
        w = base_mult.get(s, 1.0) * framework_mult
        if w == 0.0:
            signal = "fail"
        elif w < 0.95:
            signal = "warn"
        elif w > 1.05:
            signal = "boost"
        else:
            signal = "neutral"
        strategies[s] = {
            "regime_signal": signal,
            "weight": round(w, 3),
            "reason": f"regime={label} ({framework_note}); base={base_mult.get(s,1.0)}×framework={framework_mult}"
        }

    gate = {
        "policy": "regime_gate_v1",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "regime_label": label,
        "confidence": confidence,
        "framework_match": framework_match,
        "framework_note": framework_note,
        "overall_action": overall_action,
        "strategies": strategies,
        "todo": [
            "下游接入 generate_top10.py / gen_triple_consensus：每个策略在算分前读 weight 做乘子",
            "alt_groups_down_regime 仅在 regime=利率下行 时启用，已写入 market_regime.json，gate 不重复记录"
        ],
        "src_update_time": mr.get("update_time")
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(json.dumps(gate, ensure_ascii=False, indent=2))
    if not args.quiet:
        print(f"[ok] {args.out}")
        print(f"[regime] {label} | confidence={confidence} | match={framework_match}")
        print(f"[overall] {overall_action}")
        for s, v in strategies.items():
            print(f"  - {s}: weight={v['weight']}, signal={v['regime_signal']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
