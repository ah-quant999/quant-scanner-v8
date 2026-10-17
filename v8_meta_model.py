#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_meta_model.py — 行情 regime 驱动的选股策略元模型

目标：根据当前宏观/市场 regime 动态调整不同选股模块的权重，以及个股在行业风格
上的加分/减分，从而提升 TOP10 精选的胜率与收益率。

当前输入：
- raw_data/market_regime.json：利率 regime + 推荐/规避板块列表
- raw_data/sh_sz_history.json / index_history.json：用于判断市场趋势 regime
- raw_data/market_fund_flow_data.json：全市场资金流向

输出：
- strategy_weights(): 各选股策略（三重共识 / CRDS / 动量 / 机构）的权重
- sector_multiplier(sectors, concepts): 基于推荐/规避板块名单的分数乘数
- regime_summary(): 当前 regime 摘要（用于 TOP10 明细展示）

设计原则：
- 默认权重为 1.0（不改变原有评分），由 regime 信号产生 ±20% 以内的微调。
- 所有调整必须打印日志，保证可解释、可回测。
- 未识别 regime 时保守返回中性权重，不强行发挥。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"

# 默认中性：不改变任何策略分数
DEFAULT_WEIGHTS = {
    "triple_consensus": 1.0,   # 三重共识
    "crds": 1.0,               # 逆势龙头
    "momentum": 1.0,           # 动量/突破
    "institution": 1.0,        # 机构/龙虎榜
    "north_fund": 1.0,         # 北向资金
    "fundamental": 1.0,        # 基本面质量
}


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


@dataclass
class RegimeState:
    label: str
    confidence: str
    cn_score: int
    us_score: int
    recommended_sectors: list[str]
    avoid_sectors: list[str]
    market_trend: str  # 'up' / 'down' / 'oscillation' / 'unknown'


def _parse_market_regime() -> dict[str, Any]:
    return _load_json(RAW_DIR / "market_regime.json", {}) or {}


def _parse_index_trend() -> str:
    """基于上证指数 20 日与 5 日收盘判断简单趋势 regime。"""
    hist = _load_json(RAW_DIR / "sh_sz_history.json", {}) or {}
    sh = hist.get("sh", {})
    closes = sh.get("close", []) if isinstance(sh, dict) else []
    if len(closes) < 20:
        # 回退读 index_history
        ih = _load_json(RAW_DIR / "index_history.json", {}) or {}
        closes = ih.get("close", []) if isinstance(ih, dict) else []
    if len(closes) < 20:
        return "unknown"
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    latest = closes[-1]
    if latest > ma5 > ma20:
        return "up"
    if latest < ma5 < ma20:
        return "down"
    return "oscillation"


def get_regime_state() -> RegimeState:
    """解析当前 regime 状态（宏观利率 + 市场趋势）。"""
    mr = _parse_market_regime()
    regime = mr.get("regime", {}) if isinstance(mr, dict) else {}
    label = regime.get("label", "未知")
    confidence = regime.get("confidence", "低")
    cn_score = regime.get("cn_score", 0)
    us_score = regime.get("us_score", 0)

    recommended = []
    avoid = []
    for g in mr.get("recommendation_groups", []):
        recommended.extend(g.get("sectors", []))
    for g in mr.get("alt_groups_down_regime", []):
        avoid.extend(g.get("sectors", []))

    market_trend = _parse_index_trend()
    return RegimeState(
        label=label,
        confidence=confidence,
        cn_score=cn_score,
        us_score=us_score,
        recommended_sectors=list(set(recommended)),
        avoid_sectors=list(set(avoid)),
        market_trend=market_trend,
    )


def strategy_weights(state: RegimeState | None = None) -> dict[str, float]:
    """根据 regime 返回各策略权重。默认 1.0，仅在高置信信号时微调。"""
    if state is None:
        state = get_regime_state()

    w = dict(DEFAULT_WEIGHTS)

    # 市场趋势 regime
    if state.market_trend == "up":
        w["momentum"] *= 1.15
        w["triple_consensus"] *= 1.10
        w["crds"] *= 0.90
    elif state.market_trend == "down":
        w["momentum"] *= 0.80
        w["crds"] *= 1.15
        w["institution"] *= 0.95
    elif state.market_trend == "oscillation":
        w["triple_consensus"] *= 1.05
        w["crds"] *= 1.05

    # 利率/宏观 regime（仅高置信时放大）
    if state.confidence == "高":
        if state.cn_score > 0:          # 中国利率上行 → 银行/高股息等价值风格受益
            w["fundamental"] *= 1.10
            w["north_fund"] *= 1.05
        elif state.cn_score < 0:        # 中国利率下行 → 成长风格受益
            w["momentum"] *= 1.10

    # 未知 regime 保守处理：全部保持中性
    return w


def sector_multiplier(
    sectors: list[str],
    concepts: list[str],
    state: RegimeState | None = None,
) -> float:
    """根据当前 regime 推荐/规避板块，给个股一个 ±10% 的乘数。"""
    if state is None:
        state = get_regime_state()

    tags = set((sectors or []) + (concepts or []))
    if not tags:
        return 1.0

    rec = set(state.recommended_sectors or [])
    avoid = set(state.avoid_sectors or [])

    hit_rec = bool(tags & rec)
    hit_avoid = bool(tags & avoid)

    if hit_rec and not hit_avoid:
        return 1.08
    if hit_avoid and not hit_rec:
        return 0.92
    if hit_rec and hit_avoid:
        return 1.0
    return 1.0


def regime_summary() -> dict[str, Any]:
    """生成供 TOP10 明细展示用的 regime 摘要。"""
    state = get_regime_state()
    return {
        "label": state.label,
        "confidence": state.confidence,
        "market_trend": state.market_trend,
        "recommended_sectors": state.recommended_sectors,
        "avoid_sectors": state.avoid_sectors,
        "strategy_weights": strategy_weights(state),
    }


def main() -> None:
    s = get_regime_state()
    print(f"regime={s.label} confidence={s.confidence} trend={s.market_trend}")
    print("strategy_weights:", strategy_weights(s))
    print("recommended:", s.recommended_sectors)
    print("avoid:", s.avoid_sectors)


if __name__ == "__main__":
    main()
