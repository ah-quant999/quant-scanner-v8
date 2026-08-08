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


def compute_stop_target(df: pd.DataFrame, board: str = "主板") -> dict | None:
    """从日K DataFrame(date/open/close/high/low/...) 计算统一止损止盈。

    df 至少需要 PRICE_WINDOW+1 根K线，close/high/low 为 float。
    """
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


def compute_stop_target_from_closes(closes, board: str = "主板") -> dict | None:
    """降级版：只有收盘价序列（无 high/low）时使用，规则形状与 compute_stop_target 一致。

    用近 PRICE_WINDOW 日收盘价的极值代替真实高低点，无 ATR 口径。
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
