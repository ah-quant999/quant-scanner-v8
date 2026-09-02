#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""optimize_stop_target.py — 方案三：历史信号止损/止盈参数最优化回测

目标：用全站历史信号（backtest_tdx / backtest_comprehensive / /* cockpit 已下线 2026-09-03 */_backtest）
回测不同「止损口径 × 止盈口径」组合，自动选出对当前各策略最优的参数组合，
并支持不同策略配置不同口径（STOP_TARGET_PROFILES）。

方法（非未来函数）：
  - 止损价取自入场日及之前的历史窗口（trailing window），绝不使用入场后数据。
  - 入场日次日起逐日模拟：先判止损（low<=stop），再判止盈（high>=target），
    否则持有至 MAX_HOLD 交易日后以收盘价离场。
  - 仅纳入「入场后至少有 MAX_HOLD 个交易日数据」的信号，避免截尾偏差。

输出：raw_data/stop_target_optimization.json
"""
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

ALGO = os.path.dirname(os.path.abspath(__file__))
V8_ROOT = os.path.dirname(ALGO)
RAW = os.path.join(V8_ROOT, "raw_data")
sys.path.insert(0, ALGO)

from data_source_gtimg import fetch_a_daily_gtimg  # noqa: E402
from stop_target_logic import board_from_code, ATR_WINDOW  # noqa: E402

KLINE_CACHE = os.path.join(ALGO, "_opt_kline_cache")
os.makedirs(KLINE_CACHE, exist_ok=True)

MAX_HOLD = 20          # 入场后最多持有交易日
TRAIL = 65             # 入场前回看窗口（覆盖 prevHigh60 + ATR）
ATR_W = ATR_WINDOW     # 14

# ---- 参数网格 ----
STOP_RULES = [
    ("lowN", [10, 15, 20, 30]),
    ("atrM", [1.5, 2.0, 2.5, 3.0]),
    ("fixedP", [5, 7, 10, 12]),
]
TARGET_RULES = [
    ("prevHighN", [20, 60]),
    ("fibX", [0.382, 0.5, 0.618, 0.786]),
    ("rrK", [1.5, 2.0, 2.5, 3.0]),
]


# ---------------------------------------------------------------------------
# K 线获取（带本地缓存）
# ---------------------------------------------------------------------------
def get_kline(code, market):
    """返回 DataFrame(date,open,high,low,close,volume) 或 None。"""
    cf = os.path.join(KLINE_CACHE, f"{market}_{code}.json")
    if os.path.exists(cf):
        try:
            df = pd.DataFrame(json.load(open(cf, encoding="utf-8")))
            if len(df) >= 60:
                return df
        except Exception:
            pass
    df = fetch_a_daily_gtimg(code, market, bars=250)
    if df is None or len(df) < 60:
        return None
    df = df.reset_index(drop=True)
    json.dump(df.to_dict("records"), open(cf, "w", encoding="utf-8"))
    return df


def atr_series(df, n=ATR_W):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


# ---------------------------------------------------------------------------
# 信号收集
# ---------------------------------------------------------------------------
def market_of(key, sv):
    mkt = str(sv.get("market", "") if isinstance(sv, dict) else "")
    if "港" in mkt or key.startswith("hk"):
        return None
    digits = "".join(ch for ch in str(sv.get("code", key)) if ch.isdigit())
    if not digits:
        return None
    return "sh" if digits.startswith("6") else "sz", digits


def collect_signals():
    out = []  # {strategy, code, market, board, date, entry}

    # 1) tdx
    p = os.path.join(RAW, "backtest_tdx.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for key, sv in (d.get("stocks") or {}).items():
            if not isinstance(sv, dict) or sv.get("error"):
                continue
            m = market_of(key, sv)
            if not m:
                continue
            market, code = m
            board = sv.get("board") or board_from_code(code)
            for sdate, sval in (sv.get("signals") or {}).items():
                if not isinstance(sval, dict):
                    continue
                ep = sval.get("entry_price")
                if ep is None:
                    continue
                out.append({"strategy": "tdx", "code": code, "market": market,
                            "board": board, "date": sdate, "entry": float(ep)})

    # 2) comprehensive
    p = os.path.join(RAW, "backtest_comprehensive.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for sub, blob in (d.get("details") or {}).items():
            for s in (blob.get("signals") or []):
                if not isinstance(s, dict) or s.get("entry_price") is None:
                    continue
                mkt = str(s.get("market", ""))
                code = "".join(ch for ch in str(s.get("code", "")) if ch.isdigit())
                if not code or "港" in mkt:
                    continue
                market = "sh" if code.startswith("6") else "sz"
                out.append({"strategy": "comprehensive", "code": code, "market": market,
                            "board": s.get("board") or board_from_code(code),
                            "date": s.get("entry_date"), "entry": float(s["entry_price"])})

    # 3) /* cockpit 已下线 2026-09-03 */
    p = os.path.join(RAW, "/* cockpit 已下线 2026-09-03 */_backtest.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for s in (d.get("results") or []):
            if not isinstance(s, dict) or s.get("entry_price") is None:
                continue
            mkt = str(s.get("market", ""))
            code = "".join(ch for ch in str(s.get("code", "")) if ch.isdigit())
            if not code or "港" in mkt:
                continue
            market = "sh" if code.startswith("6") else "sz"
            out.append({"strategy": "/* cockpit 已下线 2026-09-03 */", "code": code, "market": market,
                        "board": s.get("board") or board_from_code(code),
                        "date": s.get("entry_date"), "entry": float(s["entry_price"])})

    # 去重（同策略同代码同日期）
    seen = set()
    uniq = []
    for s in out:
        kk = (s["strategy"], s["code"], s["date"])
        if kk in seen:
            continue
        seen.add(kk)
        uniq.append(s)
    return uniq


# ---------------------------------------------------------------------------
# 预计算每信号窗口统计 + 前向路径
# ---------------------------------------------------------------------------
def build_signal_records(sigs):
    recs = []
    cache = {}
    skipped_nodata = skipped_short = 0
    for s in sigs:
        code, market = s["code"], s["market"]
        if (code, market) not in cache:
            cache[(code, market)] = get_kline(code, market)
        df = cache[(code, market)]
        if df is None:
            skipped_nodata += 1
            continue
        dates = df["date"].tolist()
        try:
            eidx = dates.index(s["date"])
        except ValueError:
            # 入场日不在 K 线中（分红/停牌），跳过
            skipped_short += 1
            continue
        if eidx < TRAIL or eidx + MAX_HOLD >= len(df):
            # 入场前窗口不足 或 入场后不足 MAX_HOLD 交易日 → 截尾，跳过
            skipped_short += 1
            continue
        trail = df.iloc[eidx - TRAIL + 1: eidx + 1]      # 含入场日，共 TRAIL 行
        fwd = df.iloc[eidx + 1: eidx + 1 + MAX_HOLD]     # 入场次日起 MAX_HOLD 个交易日
        recs.append({
            "strategy": s["strategy"],
            "code": code,
            "entry": s["entry"],
            "trail_low": trail["low"].to_numpy(dtype=float),
            "trail_high": trail["high"].to_numpy(dtype=float),
            "entry_close": float(trail["close"].iloc[-1]),
            "atr": float(atr_series(trail).iloc[-1]),
            "fwd_low": fwd["low"].to_numpy(dtype=float),
            "fwd_high": fwd["high"].to_numpy(dtype=float),
            "fwd_close": fwd["close"].to_numpy(dtype=float),
        })
    return recs, skipped_nodata, skipped_short


# ---------------------------------------------------------------------------
# 组合生成
# ---------------------------------------------------------------------------
def combo_list():
    """返回 [(stop_label, stop_param, target_label, target_param), ...]"""
    combos = []
    for sl, sps in STOP_RULES:
        for tl, tps in TARGET_RULES:
            for sp in sps:
                for tp in tps:
                    combos.append((sl, sp, tl, tp))
    return combos


def compute_stop_target(rec, sl, sp, tl, tp):
    """返回 (stop_price, target_price) 或 (None,None) 若无效。"""
    E = rec["entry_close"]
    lows = rec["trail_low"]
    highs = rec["trail_high"]
    if sl == "lowN":
        stop = float(np.min(lows[-sp:]))
    elif sl == "atrM":
        stop = E - rec["atr"] * sp
    else:  # fixedP
        stop = E * (1 - sp / 100.0)
    if stop >= E:
        return None, None

    risk = E - stop
    if tl == "prevHighN":
        target = float(np.max(highs[-tp:]))
    elif tl == "fibX":
        wh = float(np.max(highs[-30:]))
        wl = float(np.min(lows[-30:]))
        target = wh - tp * (wh - wl)
    else:  # rrK
        target = E + tp * risk
    if target <= E:
        return None, None
    return stop, target


# ---------------------------------------------------------------------------
# 向量化回测
# ---------------------------------------------------------------------------
def backtest_combo(recs, combos):
    """对每个 combo 返回聚合指标字典。"""
    C = len(combos)
    n = len(recs)
    # 预存每信号 S,T 数组
    S_arr = np.zeros((n, C), dtype=float)
    T_arr = np.zeros((n, C), dtype=float)
    valid = np.zeros((n, C), dtype=bool)
    E_arr = np.array([r["entry_close"] for r in recs], dtype=float)  # (n,)
    for ci, (sl, sp, tl, tp) in enumerate(combos):
        for ri, r in enumerate(recs):
            s, t = compute_stop_target(r, sl, sp, tl, tp)
            if s is not None:
                S_arr[ri, ci] = s
                T_arr[ri, ci] = t
                valid[ri, ci] = True

    results = []
    for ci, (sl, sp, tl, tp) in enumerate(combos):
        msk = valid[:, ci]
        if msk.sum() < 50:
            continue
        # 收集有效信号的 fwd 数组（长度不一，统一 pad 到 MAX_HOLD）
        F = MAX_HOLD
        lowmat = np.full((msk.sum(), F), np.nan)
        highmat = np.full((msk.sum(), F), np.nan)
        closemat = np.full((msk.sum(), F), np.nan)
        E_valid = E_arr[msk]
        S = S_arr[msk, ci]
        T = T_arr[msk, ci]
        ridx = 0
        for ri in range(n):
            if not msk[ri]:
                continue
            r = recs[ri]
            L = min(len(r["fwd_low"]), F)
            lowmat[ridx, :L] = r["fwd_low"][:L]
            highmat[ridx, :L] = r["fwd_high"][:L]
            closemat[ridx, :L] = r["fwd_close"][:L]
            ridx += 1

        last_close = closemat[:, -1]
        # 止损命中（首根 low<=S）
        stop_hit = lowmat <= S[:, None]
        target_hit = (T[:, None] > E_valid[:, None]) & (highmat >= T[:, None])
        # 首命中索引
        def first_idx(mat):
            idx = np.full(mat.shape[0], F, dtype=int)
            rows, cols = np.nonzero(mat)
            if rows.size:
                order = np.argsort(cols)
                rows, cols = rows[order], cols[order]
                # 每个 row 取最小 col
                uniq = np.unique(rows)
                for u in uniq:
                    m = rows == u
                    idx[u] = cols[m][0]
            return idx
        istop = first_idx(stop_hit)
        itgt = first_idx(target_hit)
        exit_stop = (istop < itgt) & (istop < F)
        exit_target = (~exit_stop) & (itgt < F)
        exit_hold = (~exit_stop) & (~exit_target)
        exit_price = np.where(exit_stop, S,
                       np.where(exit_target, T, last_close))
        ret = (exit_price - E_valid) / E_valid * 100.0
        wins = ret > 0
        win_rate = float(wins.mean())
        avg_ret = float(ret.mean())
        pos = ret[ret > 0]
        neg = ret[ret <= 0]
        avg_win = float(pos.mean()) if pos.size else 0.0
        avg_loss = float(neg.mean()) if neg.size else 0.0
        pf = float(pos.sum() / abs(neg.sum())) if neg.size and neg.sum() != 0 else (float("inf") if pos.size else 0.0)
        rr = (T - E_valid) / (E_valid - S)
        median_rr = float(np.median(rr))
        results.append({
            "stop": f"{sl}{sp}", "stop_rule": sl, "stop_param": sp,
            "target": f"{tl}{tp}", "target_rule": tl, "target_param": tp,
            "n": int(msk.sum()),
            "win_rate": round(win_rate * 100, 2),
            "avg_return": round(avg_ret, 3),
            "avg_win": round(avg_win, 3),
            "avg_loss": round(avg_loss, 3),
            "profit_factor": round(pf, 3) if pf != float("inf") else None,
            "median_rr": round(median_rr, 3),
        })
    return results


# ---------------------------------------------------------------------------
# 选优
# ---------------------------------------------------------------------------
def select_best(results, min_rr=1.5):
    if not results:
        return None
    # 优先 median_rr>=min_rr 且 win_rate>=45 且 n>=100，取 expectancy(avg_return) 最大
    pool = [r for r in results if r["median_rr"] >= min_rr and r["win_rate"] >= 45 and r["n"] >= 100]
    if not pool:
        pool = [r for r in results if r["win_rate"] >= 45 and r["n"] >= 100]
    if not pool:
        pool = results
    pool.sort(key=lambda r: r["avg_return"], reverse=True)
    return pool[0], pool[:10]


# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    print(f"=== 方案三：止损/止盈参数最优化  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    sigs = collect_signals()
    print(f"收集历史信号: {len(sigs)} 条")
    recs, nodata, short = build_signal_records(sigs)
    print(f"可用信号(完整前向窗口): {len(recs)} | 跳过无K线:{nodata} | 跳过截尾:{short}")

    # 按策略分组
    by_strat = {}
    for r in recs:
        by_strat.setdefault(r["strategy"], []).append(r)

    combos = combo_list()
    print(f"参数组合总数: {len(combos)}")

    results_all = {}
    recommendation = {}
    for strat, rs in by_strat.items():
        print(f"\n--- 策略 [{strat}] 信号数={len(rs)} ---")
        res = backtest_combo(rs, combos)
        sel = select_best(res)
        best, top10 = (sel if sel is not None else (None, []))
        results_all[strat] = {
            "signal_count": len(rs),
            "combo_count_tested": len(res),
            "best": best,
            "top10": top10,
        }
        if best:
            recommendation[strat] = {
                "stop_rule": best["stop_rule"], "stop_param": best["stop_param"],
                "target_rule": best["target_rule"], "target_param": best["target_param"],
                "metrics": {k: best[k] for k in ("win_rate", "avg_return", "profit_factor", "median_rr")},
            }
            print(f"  最优: 止损 {best['stop']} / 止盈 {best['target']} | "
                  f"胜率 {best['win_rate']}% 期望 {best['avg_return']}% PF {best['profit_factor']} R:R {best['median_rr']}")

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": "非未来函数：止损/止盈取自入场日及之前窗口，次日起逐日模拟提前出场；仅纳入完整前向窗口信号",
        "max_hold_days": MAX_HOLD,
        "trailing_window": TRAIL,
        "grid": {
            "stop_rules": {k: v for k, v in STOP_RULES},
            "target_rules": {k: v for k, v in TARGET_RULES},
        },
        "universe": {s: len(rs) for s, rs in by_strat.items()},
        "recommendation": recommendation,
        "results": results_all,
    }
    op = os.path.join(RAW, "stop_target_optimization.json")
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n✅ 写出 {op} | 用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
