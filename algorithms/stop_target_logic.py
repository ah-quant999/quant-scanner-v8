#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stop_target_logic.py — 方案二统一止损/止盈口径

止损三口径取最严（最高止损价）：
  1) 近 20 日低点 low20
  2) ATR(14) × 2
  3) 固定百分比：创业板/科创板 90%，其他 93%

止盈三口径按优先级 cascade（取满足盈亏比≥1.5 的最严者）：
  1) 前高 = 近 20 日最高价
  2) 0.618 回撤位 = high - 0.618 × (high - low)
  3) R:R=2 对称位 = close + 2 × (close - chosen_stop)

返回 dict 与 gen_stock_stop.py 产出的单只股票字段保持一致。
"""
import json
import os

import numpy as np
import pandas as pd

ATR_WINDOW = 14
PRICE_WINDOW = 20
STOP_ATR_MULT = 2.0
RR_RATIO = 2.0


def fixed_stop_pct(board: str) -> float:
    return 0.90 if board in ("创业板", "科创板") else 0.93


def board_from_code(code) -> str:
    c = str(code or "").strip()
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith("688"):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return "主板"


# ---------------------------------------------------------------------------
# 方案三：分策略止损/止盈口径配置（不同策略可配不同口径）
# ---------------------------------------------------------------------------
_PROFILES_CACHE = None


def _load_profiles():
    """加载 algorithms/stop_target_profiles.json。

    格式：{"tdx": {"stop":"fixedP10","target":"rrK1.5"}, ...}
    "auto" 或缺失 → 使用 方案二 默认口径（compute_stop_target_v2）。
    """
    global _PROFILES_CACHE
    if _PROFILES_CACHE is not None:
        return _PROFILES_CACHE
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stop_target_profiles.json")
    try:
        with open(p, encoding="utf-8") as f:
            _PROFILES_CACHE = json.load(f)
    except Exception:
        _PROFILES_CACHE = {}
    return _PROFILES_CACHE


def _parse_spec(spec):
    """'fixedP10'→('fixedP',10) / 'rrK1.5'→('rrK',1.5) / 'prevHighN60'→('prevHighN',60)
    / 'fibX0.618'→('fibX',0.618) / 'auto'/None→None"""
    if not spec or str(spec).lower() == "auto":
        return None
    import re
    m = re.match(r"^([A-Za-z]+?)([0-9.]+)$", str(spec))
    if not m:
        return None
    return m.group(1), float(m.group(2))


def compute_stop_target_by_rules(df, board, stop_rule, stop_param, target_rule, target_param):
    """按显式规则（方案三优化结果）计算止损止盈，返回与 compute_stop_target 同构 dict。"""
    if df is None or len(df) < max(ATR_WINDOW, PRICE_WINDOW) + 1:
        return None
    try:
        close = float(df["close"].iloc[-1])
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        prev_close = df["close"].astype(float).shift(1)
    except Exception:
        return None
    if close <= 0:
        return None
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(ATR_WINDOW).mean())
    if atr <= 0:
        return None

    lows = low.to_numpy(dtype=float)
    highs = high.to_numpy(dtype=float)

    # 止损
    if stop_rule == "lowN":
        stop = float(np.min(lows[-int(stop_param):]))
    elif stop_rule == "atrM":
        stop = close - atr * stop_param
    else:  # fixedP
        stop = close * (1 - stop_param / 100.0)
    if stop >= close:
        stop = close * 0.5
    stop = max(stop, close * 0.5)
    risk = close - stop
    if risk <= 0:
        return None

    # 止盈
    if target_rule == "prevHighN":
        target = float(np.max(highs[-int(target_param):]))
    elif target_rule == "fibX":
        wh = float(np.max(highs[-30:]))
        wl = float(np.min(lows[-30:]))
        target = wh - target_param * (wh - wl)
    else:  # rrK
        target = close + target_param * risk
    if target <= close:
        target = close + 2.0 * risk
    reward = target - close
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    return {
        "close": round(close, 2),
        "atr": round(atr, 3),
        "board": board,
        "stop_loss": round(stop, 2),
        "stop_loss_method": f"{stop_rule}{int(stop_param) if stop_param == int(stop_param) else stop_param}",
        "target_price": round(target, 2),
        "target_price_method": f"{target_rule}{int(target_param) if target_param == int(target_param) else target_param}",
        "support": round(float(np.min(lows[-PRICE_WINDOW:])), 2),
        "resistance": round(float(np.max(highs[-PRICE_WINDOW:])), 2),
        "risk_reward": rr,
        "risk_pct": round(risk / close * 100, 2),
        "reward_pct": round(reward / close * 100, 2),
        "profile": True,
    }


def compute_stop_target(df: pd.DataFrame, board: str = "主板", strategy: str = None) -> dict | None:
    """从日K DataFrame 计算止损止盈。

    - strategy=None（默认）：先读取 profiles 中 "default" 配置；若 default 为 auto 则回退方案二口径。
    - strategy 命中 stop_target_profiles.json 中的非 auto 配置：改用该策略优化后的口径。
    """
    prof = _load_profiles().get(strategy or "default")
    if prof:
        sr = _parse_spec(prof.get("stop"))
        tr = _parse_spec(prof.get("target"))
        if sr and tr:
            r = compute_stop_target_by_rules(df, board, sr[0], sr[1], tr[0], tr[1])
            if r:
                return r
    return _compute_stop_target_v2(df, board)


def _compute_stop_target_v2(df: pd.DataFrame, board: str = "主板") -> dict | None:
    """方案二统一口径（原 compute_stop_target 逻辑，保持不动）。"""
    if df is None or len(df) < max(ATR_WINDOW, PRICE_WINDOW) + 1:
        return None
    try:
        close = float(df["close"].iloc[-1])
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        prev_close = df["close"].astype(float).shift(1)
    except Exception:
        return None
    if close <= 0:
        return None

    # ATR(14)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = float(tr.tail(ATR_WINDOW).mean())
    if atr <= 0:
        return None

    window_high = float(high.tail(PRICE_WINDOW).max())
    window_low = float(low.tail(PRICE_WINDOW).min())

    # 止损三口径取最严
    fixed_pct = fixed_stop_pct(board)
    stop_candidates = {
        "low20": window_low,
        "atr2": close - STOP_ATR_MULT * atr,
        "fixed": close * fixed_pct,
    }
    chosen_stop_method = max(stop_candidates, key=stop_candidates.get)
    chosen_stop = stop_candidates[chosen_stop_method]
    if chosen_stop >= close:
        chosen_stop = close * 0.93
        chosen_stop_method = "fixed"
    chosen_stop = max(chosen_stop, close * 0.5)

    # 止盈 cascade
    fib618 = window_high - 0.618 * (window_high - window_low)
    rr2 = close + RR_RATIO * (close - chosen_stop)
    target_candidates = [
        ("prev_high", window_high),
        ("fib618", fib618),
        ("rr2", rr2),
    ]
    target_candidates_dict = dict(target_candidates)
    chosen_target_method = "rr2"
    chosen_target = rr2
    risk = close - chosen_stop
    for method, price in target_candidates:
        if price <= close:
            continue
        rr = (price - close) / risk if risk > 0 else 0
        if rr >= 1.5:
            chosen_target_method = method
            chosen_target = price
            break
    if chosen_target <= close:
        chosen_target = rr2
        chosen_target_method = "rr2"

    risk = close - chosen_stop
    reward = chosen_target - close
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    return {
        "close": round(close, 2),
        "atr": round(atr, 3),
        "window_high": round(window_high, 2),
        "window_low": round(window_low, 2),
        "board": board,
        "stop_loss": round(chosen_stop, 2),
        "stop_loss_method": chosen_stop_method,
        "stop_loss_candidates": {k: round(v, 2) for k, v in stop_candidates.items()},
        "target_price": round(chosen_target, 2),
        "target_price_method": chosen_target_method,
        "target_price_candidates": {k: round(v, 2) for k, v in target_candidates_dict.items()},
        "support": round(window_low, 2),
        "resistance": round(window_high, 2),
        "risk_reward": rr,
        "risk_pct": round(risk / close * 100, 2),
        "reward_pct": round(reward / close * 100, 2),
    }


def compute_stop_target_from_closes(closes, board: str = "主板", strategy: str = None) -> dict | None:
    """降级版：只有收盘价序列（无 high/low）时使用。

    - strategy=None（默认）：先读取 profiles 中 "default" 配置；若 default 为 auto 则回退方案二降级口径。
    - 命中非 auto 配置时：仅支持 fixedP/rrK 组合（因无 high/low 无法算 prevHighN/fibX）。
    适用于 generate_top10.py 这类只能拿到 close 序列的场景。
    返回字段为 compute_stop_target 的子集，并带 precise=False 标记。
    """
    vals = [float(c) for c in (closes or []) if c and float(c) > 0]
    if not vals:
        return None
    close = vals[-1]
    win = vals[-PRICE_WINDOW:] if len(vals) >= PRICE_WINDOW else vals
    window_high = max(win)
    window_low = min(win)

    # 优先读取 profile（默认/general 等）
    prof = _load_profiles().get(strategy or "default")
    if prof:
        sr = _parse_spec(prof.get("stop"))
        tr = _parse_spec(prof.get("target"))
        if sr and tr and sr[0] == "fixedP" and tr[0] == "rrK":
            stop_param, target_param = sr[1], tr[1]
            chosen_stop = close * (1 - stop_param / 100.0)
            chosen_stop = max(chosen_stop, close * 0.5)
            risk = close - chosen_stop
            chosen_target = close + target_param * risk if risk > 0 else close * 1.03
            chosen_target = max(chosen_target, close * 1.03)
            reward = chosen_target - close
            return {
                "close": round(close, 2),
                "board": board,
                "precise": False,
                "profile": True,
                "stop_loss": round(chosen_stop, 2),
                "stop_loss_method": f"fixedP{int(stop_param) if stop_param == int(stop_param) else stop_param}",
                "target_price": round(chosen_target, 2),
                "target_price_method": f"rrK{int(target_param) if target_param == int(target_param) else target_param}",
                "risk_reward": round(reward / risk, 2) if risk > 0 else 0.0,
                "risk_pct": round(risk / close * 100, 2),
                "reward_pct": round(reward / close * 100, 2),
            }

    # 回退：方案二降级口径（low20 / fixed 取最严，cascade 止盈）
    fixed_pct = fixed_stop_pct(board)
    stop_candidates = {
        "low20": window_low,
        "fixed": close * fixed_pct,
    }
    chosen_stop_method = max(stop_candidates, key=stop_candidates.get)
    chosen_stop = stop_candidates[chosen_stop_method]
    if chosen_stop >= close:
        chosen_stop = close * fixed_pct
        chosen_stop_method = "fixed"
    chosen_stop = max(chosen_stop, close * 0.5)

    risk = close - chosen_stop
    fib618 = window_high - 0.618 * (window_high - window_low)
    rr2 = close + RR_RATIO * risk
    target_candidates = [
        ("prev_high", window_high),
        ("fib618", fib618),
        ("rr2", rr2),
    ]
    chosen_target_method = "rr2"
    chosen_target = rr2
    for method, price in target_candidates:
        if price <= close:
            continue
        rr = (price - close) / risk if risk > 0 else 0
        if rr >= 1.5:
            chosen_target_method = method
            chosen_target = price
            break
    if chosen_target <= close:
        chosen_target = rr2
        chosen_target_method = "rr2"

    reward = chosen_target - close
    return {
        "close": round(close, 2),
        "board": board,
        "precise": False,
        "stop_loss": round(chosen_stop, 2),
        "stop_loss_method": chosen_stop_method,
        "stop_loss_candidates": {k: round(v, 2) for k, v in stop_candidates.items()},
        "target_price": round(chosen_target, 2),
        "target_price_method": chosen_target_method,
        "target_price_candidates": {
            k: round(v, 2) for k, v in dict(target_candidates).items()
        },
        "risk_reward": round(reward / risk, 2) if risk > 0 else 0.0,
        "risk_pct": round(risk / close * 100, 2),
        "reward_pct": round(reward / close * 100, 2),
    }


def simulate_early_exit(df: pd.DataFrame, entry_idx: int, stop_loss: float, target_price: float):
    """从 entry_idx 开始模拟每日 close 触发止损/止盈，返回 (exit_idx, exit_price, exit_type)。

    exit_type: 'stop' / 'target' / None
    若 never 触发，返回 (len-1, close, None)
    """
    n = len(df)
    for i in range(entry_idx + 1, n):
        cp = float(df["close"].iloc[i])
        if cp <= stop_loss:
            return i, stop_loss, "stop"
        if cp >= target_price:
            return i, target_price, "target"
    return n - 1, float(df["close"].iloc[-1]), None
