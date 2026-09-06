#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_comprehensive.py — 全面回测引擎 V2.5（方案二：止损止盈升级）
=======================================================================
多策略 × 多持有期 × 统一止损止盈口径 滚动回测

数据流：
1. 扫描 data/history/top10_daily_*.json 及 backup_*/data/scan_result.json
2. 提取各策略的入场信号
3. 用 baostock 拉历史日 K，按方案二口径计算止损/止盈
4. 模拟每日 close 触发止损/止盈的提前出场，输出 data/backtest_comprehensive.json

止损止盈口径（方案二）：
  止损 = max(近20日低点, close-2ATR, 固定百分比)
  止盈 = cascade：前高 → 0.618回撤位 → R:R=2对称位，取满足盈亏比≥1.5的最严者

支持策略：
  策略ID                    来源              分数门槛
  ────────────────────────────────────────────────────
  resonance_gte80           top10_daily        total_score>=80
  resonance_gte70_lt80      top10_daily        70<=total_score<80
  resonance_all             top10_daily        total_score>=70
  signal_ge2                backukp/scan       signal_count>=2
  signal_ge3                backup/scan        signal_count>=3
"""
import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import re
import sys
import time
import math
from datetime import datetime, timedelta
from collections import defaultdict

import baostock as bs

import pandas as pd

sys.path.insert(0, BASE)
from stop_target_logic import (  # noqa: E402
    compute_stop_target,
    board_from_code,
    fixed_stop_pct,
)

# ── 常量 ──
BASE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：历史快照目录从 out/history（gitignore，云端丢）→ raw_data/history（git 跟踪 + api_push 推送持久化）
HIST_DIR = os.path.join(BASE, "..", "raw_data", "history")
BACKUP_DIR = os.path.join(BASE, "backup")  # 多个 backup_YYYYMMDD
OUT = os.path.join(BASE, "..", "raw_data", "backtest_comprehensive.json")
TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")

# 持有期测试列表（交易日）
HOLD_PERIODS = [1, 3, 5, 10, 20]

# 是否启用 baostock（离线模式跳过拉价格，只统计信号数）
BAOSTOCK_ENABLED = True

DEBUG = False  # True 时输出更多日志

# 2026-09-06 主人令 P1-A：A 股交易成本默认假设（单边 万分之1.5，双边 0.3%）。
# 综合回测已含止损止盈 exit_price 隐含滑点，此处再扣一次显式成本 → 防止方法学上重复计入。
COST_BPS = 15  # 单边


def log(msg):
    print(msg, flush=True)


def load_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def parse_date(d: str) -> str:
    d = str(d).replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else d


def bs_code(code: str, market: str = "") -> str | None:
    c = str(code).zfill(6)
    m = (market or "").lower()
    if m.startswith("hk") or (m == "hk" and c.startswith(("0", "1"))):
        return None
    if c.startswith(("8", "4", "92")) and len(c) == 6:
        return None
    if m in ("sh", "sz"):
        return f"{m}.{c}"
    return f"sh.{c}" if c[0] == "6" else f"sz.{c}"


# ════════════════════════════════════════════
# 第1步：发现并提取入场信号
# ════════════════════════════════════════════

def discover_top10_signals() -> list[dict]:
    """从 data/history/top10_daily_*.json 提取三种策略信号

    兼容两种评分口径：
    - 旧数据：total_score 为 0~100 百分制，>=70 视为有效共振。
    - 新数据（2026-08-01 后归一化）：total_score 上限 100 但实际分布偏低，
      若某日无 >=70 的股票，则按 top10 内排名分层：前 3 名≈精选、4~6 名≈观察。
    """
    signals = []
    if not os.path.isdir(HIST_DIR):
        return signals
    pat = re.compile(r"top10_daily_(\d{8})\.json$")
    for fn in sorted(os.listdir(HIST_DIR)):
        m = pat.match(fn)
        if not m:
            continue
        date_str = parse_date(m.group(1))
        data = load_json(os.path.join(HIST_DIR, fn))
        top10 = data.get("top10", []) if isinstance(data, dict) else []

        # 按分数降序并带上原始排名（1-based）
        ranked = sorted(
            [(i, s) for i, s in enumerate(top10)],
            key=lambda x: (x[1].get("total_score", 0) or 0),
            reverse=True,
        )
        has_legacy_resonance = any(
            (s.get("total_score", 0) or 0) >= 70 for _, s in ranked
        )

        for rank0, s in ranked:
            score = s.get("total_score", 0) or 0
            code = str(s.get("code", ""))
            market = str(s.get("market", ""))
            close = s.get("close", 0)
            if not close or close <= 0:
                continue
            bsc = bs_code(code, market)
            if not bsc:
                continue

            rec = {
                "entry_date": date_str,
                "code": code,
                "name": s.get("name", ""),
                "market": market,
                "board": s.get("board", "") or s.get("board_label", ""),
                "total_score": score,
                "entry_price": float(close),
                "bsc": bsc,
                "source": "top10_daily",
            }

            if has_legacy_resonance:
                # 旧百分制口径：保留原有语义
                if score >= 80:
                    rec80 = {**rec, "strategy": "resonance_gte80"}
                    signals.append(rec80)
                if 70 <= score < 80:
                    rec70 = {**rec, "strategy": "resonance_gte70_lt80"}
                    signals.append(rec70)
                if score >= 70:
                    rec_all = {**rec, "strategy": "resonance_all"}
                    signals.append(rec_all)
            else:
                # 新归一化口径：按 top10 内排名分层
                rank = rank0 + 1
                if rank <= 3:
                    rec80 = {**rec, "strategy": "resonance_gte80"}
                    signals.append(rec80)
                if 4 <= rank <= 6:
                    rec70 = {**rec, "strategy": "resonance_gte70_lt80"}
                    signals.append(rec70)
                if rank <= 6:
                    rec_all = {**rec, "strategy": "resonance_all"}
                    signals.append(rec_all)

    return signals


def discover_backup_signals() -> list[dict]:
    """从 backup_*/data/scan_result.json 提取信号"""
    signals = []
    if not os.path.isdir(BASE):
        return signals
    pat = re.compile(r"^backup_(\d{8})$")
    for dn in sorted(os.listdir(BASE)):
        m = pat.match(dn)
        if not m:
            continue
        date_str = parse_date(m.group(1))
        scan_path = os.path.join(BASE, dn, "data", "scan_result.json")
        if not os.path.exists(scan_path):
            continue
        data = load_json(scan_path)
        results = data.get("all_results", [])
        for s in results:
            sc = s.get("signal_count", 0)
            if sc < 2:
                continue
            code = str(s.get("code", ""))
            market = str(s.get("market", ""))
            close = s.get("close", 0) or s.get("price", 0)
            if not close or close <= 0:
                continue
            bsc = bs_code(code, market)
            if not bsc:
                continue
            rec = {
                "entry_date": date_str,
                "code": code,
                "name": s.get("name", ""),
                "market": market,
                "board": s.get("board_label", "") or s.get("board", ""),
                "entry_price": float(close),
                "bsc": bsc,
                "source": "backup_scan",
                "signal_count": sc,
            }
            if sc >= 3:
                rec3 = {**rec, "strategy": "signal_ge3"}
                signals.append(rec3)
            rec2 = {**rec, "strategy": "signal_ge2"}
            signals.append(rec2)
    return signals


def collect_signals() -> list[dict]:
    """收集所有策略的入场信号"""
    s1 = discover_top10_signals()
    s2 = discover_backup_signals()
    combined = s1 + s2
    log(f"  top10 信号: {len(s1)}")
    log(f"  backup 信号: {len(s2)}")
    log(f"  总计: {len(combined)}")
    # 去重：同策略+同股票+同日期的只保留一个（按 source 优先级 top10 > backup）
    seen = set()
    deduped = []
    for sig in combined:
        key = (sig["strategy"], sig["code"], sig["entry_date"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sig)
    log(f"  去重后: {len(deduped)}")
    return deduped


# ════════════════════════════════════════════
# 第2步：价格回测（多持有期）
# ════════════════════════════════════════════

def calc_multi_hold(entry_date: str, entry_price: float, bsc: str, board: str = "主板", code: str = "") -> dict | None:
    """拉 baostock 日 K，计算多持有期收益、最大回撤，并按方案二止损/止盈口径模拟提前出场。

    返回 {hold_1d:{ret, date, exit_type}, ..., max_drawdown, latest_return, stop_loss, target_price, ...}
    若 baostock 无数据返回 None
    """
    if not BAOSTOCK_ENABLED:
        return None
    entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
    # 多取 30 天历史，保证能算近 20 日高低
    start = (entry_dt - timedelta(days=35)).strftime("%Y-%m-%d")
    end = (entry_dt + timedelta(days=35)).strftime("%Y-%m-%d")

    rs = bs.query_history_k_data_plus(
        bsc, fields="date,open,high,low,close,volume",
        start_date=start, end_date=end,
        frequency="d", adjustflag="2"
    )
    rows = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return None

    # 找到 <= entry_date 的最后一条（真实入场日/价）
    entry_idx = None
    for i in reversed(range(len(rows))):
        if rows[i][0] <= entry_date:
            entry_idx = i
            break
    if entry_idx is None:
        return None

    real_entry_date = rows[entry_idx][0]
    real_entry_price = float(rows[entry_idx][4])

    # 建 DataFrame（前复权）
    df_all = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for c in ["open", "high", "low", "close", "volume"]:
        df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

    # 用 entry 当日及之前数据算止损/止盈（非未来函数）
    df_entry = df_all.iloc[: entry_idx + 1].copy()
    st = compute_stop_target(df_entry, board=board, strategy="comprehensive")
    if not st:
        # 历史数据不足时回退方案三统一口径：固定10%止损 + R:R=1.5止盈
        stop_loss = real_entry_price * 0.90
        target_price = real_entry_price * 1.15
    else:
        stop_loss = st["stop_loss"]
        target_price = st["target_price"]

    # 入场后所有交易日
    after = df_all.iloc[entry_idx:].reset_index(drop=True)
    if len(after) == 0:
        return None

    # 模拟每日 close 触发止损/止盈（先触发先执行）
    n = len(after)
    exit_idx = n - 1
    exit_price = float(after["close"].iloc[-1])
    exit_type = None
    for i in range(1, n):
        cp = float(after["close"].iloc[i])
        if cp <= stop_loss:
            exit_idx = i
            exit_price = stop_loss
            exit_type = "stop"
            break
        if cp >= target_price:
            exit_idx = i
            exit_price = target_price
            exit_type = "target"
            break

    exit_date = after["date"].iloc[exit_idx]

    # 多持有期收益：若在该周期前已触发 stop/target，则按提前出场收益；否则按周期收盘价
    holds = {}
    cost_pct = 2 * COST_BPS / 100  # 双边 0.3%
    for hp in HOLD_PERIODS:
        if len(after) - 1 < hp:
            continue
        if exit_idx <= hp:
            # 周期内已提前出场
            hp_ret = round((exit_price - real_entry_price) / real_entry_price * 100 - cost_pct, 2)
            hp_date = exit_date
            hp_price = exit_price
            hp_exit_type = exit_type
        else:
            # 未触发，按周期收盘价
            hp_ret = round((float(after["close"].iloc[hp]) - real_entry_price) / real_entry_price * 100 - cost_pct, 2)
            hp_date = after["date"].iloc[hp]
            hp_price = float(after["close"].iloc[hp])
            hp_exit_type = None
        holds[f"hold_{hp}d"] = {
            "ret": hp_ret,
            "target_date": hp_date,
            "target_price": hp_price,
            "exit_type": hp_exit_type,
            "cost_adjusted": True,
        }

    # 最大回撤（按收盘价，入场后至实际出场日）
    peak = real_entry_price
    max_dd = 0.0
    for i in range(exit_idx + 1):
        cp = float(after["close"].iloc[i])
        if cp > peak:
            peak = cp
        dd = (cp - peak) / peak
        if dd < max_dd:
            max_dd = dd

    return {
        "entry_date": real_entry_date,
        "entry_price": real_entry_price,
        "latest_date": after["date"].iloc[-1],
        "latest_price": float(after["close"].iloc[-1]),
        "hold_days": exit_idx,
        "max_drawdown": round(max_dd * 100, 2),
        "latest_return": round((exit_price - real_entry_price) / real_entry_price * 100, 2) if exit_type else round((float(after["close"].iloc[-1]) - real_entry_price) / real_entry_price * 100, 2),
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_reward": st.get("risk_reward") if st else round((target_price - real_entry_price) / (real_entry_price - stop_loss), 2),
        "exit_date": exit_date,
        "exit_price": exit_price,
        "exit_type": exit_type,
        **holds,
    }


def run_backtest(signals: list[dict]) -> dict:
    """执行全量回测，按策略分组输出结果"""
    log("\n登录 baostock...")
    lg = bs.login()
    log(f"  baostock: {lg.error_msg}")

    # 分组：{strategy: [signal, ...]}
    by_strategy = defaultdict(list)
    for sig in signals:
        by_strategy[sig["strategy"]].append(sig)

    results = {}
    strategies = sorted(by_strategy.keys())

    for st_name in strategies:
        group = by_strategy[st_name]
        log(f"\n策略 [{st_name}]: {len(group)} 个信号")

        per_signal = []
        win_rate_data = {f"hold_{hp}d": {"win": 0, "loss": 0, "rets": []} for hp in HOLD_PERIODS}

        for i, sig in enumerate(group):
            board = sig.get("board", "") or board_from_code(sig.get("code", ""))
            result = calc_multi_hold(
                sig["entry_date"], sig["entry_price"], sig["bsc"], board=board, code=sig.get("code", "")
            )
            if result is None:
                continue

            rec = {**sig, **result}
            per_signal.append(rec)

            for hp in HOLD_PERIODS:
                hk = f"hold_{hp}d"
                hd = result.get(hk, {})
                ret = hd.get("ret", 0)
                win_rate_data[hk]["rets"].append(ret)
                if ret > 0:
                    win_rate_data[hk]["win"] += 1
                elif ret < 0:
                    win_rate_data[hk]["loss"] += 1

            if DEBUG and (i % 5 == 0):
                r1 = result.get("hold_1d", {}).get("ret", 0)
                log(f"  [{i+1}/{len(group)}] {sig['code']} {sig['name']} "
                    f"入{sig['entry_date']} {sig['entry_price']:.2f} "
                    f"→ 1d {r1:+.2f}%")

            time.sleep(0.05)  # baostock 限流防护

        # 组装分持有期统计
        period_stats = {}
        for hp in HOLD_PERIODS:
            hk = f"hold_{hp}d"
            wd = win_rate_data[hk]
            total_decided = wd["win"] + wd["loss"]
            rets = wd["rets"]
            avg_ret = round(sum(rets) / len(rets), 2) if rets else 0
            median_ret = round(sorted(rets)[len(rets)//2], 2) if rets else 0
            std_ret = round((sum((r - avg_ret)**2 for r in rets) / len(rets))**0.5, 2) if len(rets) > 1 else 0
            sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0

            period_stats[hk] = {
                "count": len(rets),
                "win": wd["win"],
                "loss": wd["loss"],
                "draw": len(rets) - wd["win"] - wd["loss"],
                "win_rate": round(wd["win"] / total_decided * 100, 1) if total_decided else 0,
                "avg_return": avg_ret,
                "median_return": median_ret,
                "best_return": max(rets) if rets else 0,
                "worst_return": min(rets) if rets else 0,
                "std_return": std_ret,
                "sharpe_ratio": sharpe,
            }

            if DEBUG and period_stats[hk]["count"] >= 3:
                log(f"    {hp}日: {period_stats[hk]['win_rate']}%胜率 "
                    f"/ {period_stats[hk]['avg_return']}%平均 "
                    f"/ Sharpe {period_stats[hk]['sharpe_ratio']}")

        # 整体策略统计（取最佳持有期）
        best_hp = max(
            HOLD_PERIODS,
            key=lambda hp: period_stats.get(f"hold_{hp}d", {}).get("win_rate", 0)
        )
        best_stats = period_stats.get(f"hold_{best_hp}d", {})

        results[st_name] = {
            "total_signals": len(group),
            "valid_signals": len(per_signal),
            "best_hold_days": best_hp,
            "best_hold_win_rate": best_stats.get("win_rate", 0),
            "best_hold_avg_return": best_stats.get("avg_return", 0),
            "periods": period_stats,
            "signals": per_signal,  # 完整明细（用于前端 JS 按需加载）
        }

        log(f"  → 有效: {len(per_signal)}/{len(group)} 最佳持有{best_hp}日 "
            f"胜率{best_stats.get('win_rate',0)}% 平均{best_stats.get('avg_return',0)}%")

    bs.logout()
    return results


# ════════════════════════════════════════════
# 第3步：输出
# ════════════════════════════════════════════

def build_output(results: dict, total_signals: int) -> dict:
    """组装前端可用结构

    2026-09-06 主人令 P1-B：统计 score_regime 分布，把主流 regime 写到 output.score_regime，
    前端 labelMap 据此自动切换 '百分制 · 历史' vs '排名 · 当日' 标注，避免混淆误导。
    """
    # 策略总览表（前端 Chart.js 用）
    overview = {}
    for st_name, v in results.items():
        overview[st_name] = {
            "total": v["total_signals"],
            "valid": v["valid_signals"],
            "best_hold_days": v["best_hold_days"],
            "best_win_rate": v["best_hold_win_rate"],
            "best_avg_return": v["best_hold_avg_return"],
            "periods": v["periods"],
        }

    # 策略对比矩阵
    comparison = {}
    for hp in HOLD_PERIODS:
        hk = f"hold_{hp}d"
        row = {}
        for st_name, v in results.items():
            ps = v["periods"].get(hk, {})
            row[st_name] = {
                "win_rate": ps.get("win_rate", 0),
                "avg_return": ps.get("avg_return", 0),
                "sharpe": ps.get("sharpe_ratio", 0),
                "count": ps.get("count", 0),
            }
        comparison[hk] = row

    return {
        "calc_time": TODAY.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "baostock 真实收盘价全面回测（前复权；按方案二止损止盈 exit_price 计算；已扣双边交易成本 0.3%）",
        "hold_periods_tested": HOLD_PERIODS,
        "strategies_tested": sorted(results.keys()),
        "cost_bps_per_side": COST_BPS,
        "cost_adjusted": True,
        "overview": overview,
        "comparison": comparison,
        "details": {k: v for k, v in results.items()},
        "update_stamp": int(TODAY.timestamp()),
    }


def main():
    log("=" * 50)
    log("  全面回测引擎 V2")
    log("=" * 50)
    log(f"运行时间: {TODAY_STR}")

    # Step 1: 收集信号
    log("\n[1/3] 扫描入场信号...")
    signals = collect_signals()
    if not signals:
        log("⚠️ 无可用信号，输出空框架")
        out = build_output({}, 0)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        log(f"输出: {OUT}")
        return

    # Step 2: 执行回测
    log("\n[2/3] 执行多持有期回测...")
    results = run_backtest(signals)

    # Step 3: 输出
    log("\n[3/3] 输出结果...")
    out = build_output(results, len(signals))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    log(f"\n=== 回测完成 ===")
    log(f"输出: {OUT}")
    for st_name, v in results.items():
        log(f"  [{st_name}] {v['valid_signals']}/{v['total_signals']} 有效 "
            f"· 最佳持有{v['best_hold_days']}日 "
            f"· 胜率{v['best_hold_win_rate']}% "
            f"· 平均{v['best_hold_avg_return']}%")


if __name__ == "__main__":
    main()
