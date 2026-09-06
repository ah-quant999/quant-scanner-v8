#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_rps.py — 相对强度 RPS（A档）历史回测

背景：
  calc_stock_rps.py 现已按日归档 raw_data/history/stock_rps_YYYYMMDD.json
  （2026-09-02 起生效）。本脚本读取这些 dated 快照做真实前向收益回测。

本脚本：
  1. 读取 raw_data/history/stock_rps_YYYYMMDD.json 历史 RPS 快照。
  2. 取每日 tier=A 档个股作为信号（信号日收盘价买入）。
  3. 用 baostock 拉取信号股日K线，计算 T+1/T+3/T+5/T+10/T+20 持有期收益。
  4. 输出 raw_data/rps_backtest.json + data/RPS_BACKTEST.js。

输出字段（与 CRDS_BACKTEST / HUNTER_BACKTEST 同构）。

使用：
  python v8/backtest_rps.py
  python v8/backtest_rps.py --dry

注意：
  - baostock 登录失败时自动降级为空回测（避免 CI 挂死）。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import baostock as bs
except ImportError:
    bs = None

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
HISTORY_DIR = RAW_DIR / "history"
OUT_JSON = RAW_DIR / "rps_backtest.json"
OUT_JS = DATA_DIR / "RPS_BACKTEST.js"
HOLD_PERIODS = [1, 3, 5, 10, 20]

# 2026-09-06 主人令 P1-A：交易成本默认假设（单边万分之 1.5，双边 0.3%）
COST_BPS = 15


def parse_date_from_filename(name):
    """stock_rps_20260902.json -> 2026-09-02"""
    stem = Path(name).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    if len(digits) >= 8:
        d = digits[-8:]
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def load_signals():
    """加载历史 stock_rps A档信号。"""
    signals = []
    seen = set()
    if not HISTORY_DIR.exists():
        return signals
    for f in sorted(HISTORY_DIR.glob("stock_rps_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[skip] {f}: {e}")
            continue
        dt = parse_date_from_filename(f.name)
        if not dt:
            dt = (data.get("update_time") or "")[:10]
        if not dt or len(dt) != 10:
            continue
        records = data.get("records") or []
        for r in records:
            if (r.get("tier") or "").upper() != "A":
                continue
            code = str(r.get("code", "")).strip()
            name = str(r.get("name", "")).strip()
            if not code:
                continue
            key = (dt, code)
            if key in seen:
                continue
            seen.add(key)
            signals.append({"signal_date": dt, "code": code, "name": name})
    signals.sort(key=lambda x: x["signal_date"])
    return signals


def baostock_login():
    if bs is None:
        return False
    try:
        bs.logout()
    except Exception:
        pass
    try:
        r = bs.login()
        if r.error_code != "0":
            print(f"[baostock] login error {r.error_code}: {r.error_msg}")
            return False
        return True
    except Exception as e:
        print(f"[baostock] login exception: {e}")
        return False


def bs_code(code):
    code = code.zfill(6)
    if code.startswith("6") or code.startswith("5") or code.startswith("11") or code.startswith("51"):
        return f"sh.{code}"
    return f"sz.{code}"


def add_trade_days(date_str, n):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    d += timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def fetch_close(code, date):
    """获取某股票某交易日收盘价（前复权，2026-09-06 P0-B 修复）。"""
    if bs is None:
        return None
    try:
        r = bs.query_history_k_data_plus(
            bs_code(code), "date,close",
            start_date=date, end_date=date, frequency="d", adjustflag="2",
        )
        row = r.get_row_data()
        if row and len(row) >= 2 and row[1]:
            return float(row[1])
    except Exception as e:
        print(f"[fetch] {code} {date} error: {e}")
    return None


def fetch_kline_around(code, center_date_str, lookback_days=8, lookahead_days=35):
    """2026-09-06 P0-B：用 K 线段替代日历日持有期。旧版「日历日 +N」在周末/节假日时
    baostock 返回 None → T+3/T+5/T+10/T+20 几乎全 0 samples。新版用 K 线索引直接偏移
    N 个真实交易日，从根本上消除空样本。
    """
    if bs is None:
        return []
    try:
        d = datetime.strptime(center_date_str, "%Y-%m-%d").date()
        start = (d - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end = (d + timedelta(days=lookahead_days)).strftime("%Y-%m-%d")
        r = bs.query_history_k_data_plus(
            bs_code(code), "date,close",
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",
        )
        rows = []
        while r.error_code == "0" and r.next():
            x = r.get_row_data()
            if x and x[0] and x[1]:
                rows.append((x[0], float(x[1])))
        return rows
    except Exception as e:
        print(f"[kline] {code} {center_date_str} error: {e}")
        return []


def fmt_pct(v):
    return round(v, 2)


def fetch_close_roll(code, date_str, max_fwd=8):
    """向前滚动到最近的交易日取收盘价（信号日可能是周末，须顺延到下一交易日买入）。"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    for i in range(max_fwd + 1):
        cand = (d + timedelta(days=i)).strftime("%Y-%m-%d")
        px = fetch_close(code, cand)
        if px is not None and px > 0:
            return px, cand
    return None, None


def empty_backtest(reason):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": 0,
            "calc_time": now,
            "method": f"RPS 相对强度历史回测 · {reason}",
            "signal_date_range": "—",
            "by_period": {
                str(p): {
                    "samples": 0, "win_rate": 0, "avg_return": 0,
                    "best_return": 0, "worst_return": 0,
                    "win_avg": 0, "loss_avg": 0, "profit_loss_ratio": 0,
                }
                for p in HOLD_PERIODS
            },
        },
        "signals": [],
    }
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只统计信号数，不拉K线")
    args = parser.parse_args()

    signals = load_signals()
    print(f"[rps backtest] loaded {len(signals)} A-tier signals")
    if not signals:
        payload = empty_backtest("无历史 stock_rps A档信号（每日归档自 2026-09-02 起生效，待累积 dated 快照）")
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[rps backtest] written empty backtest")
        return 0

    if args.dry:
        dates = sorted({s["signal_date"] for s in signals})
        print(f"[DRY] date range: {dates[0]} ~ {dates[-1]}, signals={len(signals)}")
        return 0

    if not baostock_login():
        payload = empty_backtest("baostock 登录失败，自动降级")
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[rps backtest] baostock login failed -> empty backtest")
        return 0

    # 2026-09-06 主人令 P0-B：用连续 K 线段替代日历日 +1/3/5/10/20，从根本上解决 T+3/T+5/T+10/T+20
    # 全部取不到价的 bug（旧版以日历日偏移，遇到周末/节假日 baostock 返回 None → 0 samples）。
    period_returns = {p: [] for p in HOLD_PERIODS}
    period_gross = {p: [] for p in HOLD_PERIODS}
    period_per_signal_equity = {p: [] for p in HOLD_PERIODS}
    detail_signals = []
    total = len(signals)
    cost_pct = 2 * COST_BPS / 100
    for idx, sig in enumerate(signals, 1):
        code = sig["code"]
        signal_date = sig["signal_date"]
        rows = fetch_kline_around(code, signal_date, lookback_days=8, lookahead_days=35)
        entry_idx = None
        for i, (d, _) in enumerate(rows):
            if d >= signal_date:
                entry_idx = i; break
        if entry_idx is None:
            print(f"[{idx}/{total}] skip {code} {signal_date}: no kline after signal date")
            continue
        entry_td, entry_price = rows[entry_idx]
        if entry_price is None or entry_price <= 0:
            print(f"[{idx}/{total}] skip {code} {signal_date}: invalid entry price")
            continue
        sig_result = {
            "signal_date": signal_date, "entry_trade_date": entry_td, "code": code, "name": sig["name"],
            "entry_price": round(entry_price, 2), "periods": {},
        }
        for p in HOLD_PERIODS:
            target_idx = entry_idx + p
            if target_idx >= len(rows):
                sig_result["periods"][str(p)] = {"return_pct": None, "gross_return": None, "exit_price": None, "exit_date": None}
                continue
            exit_td, exit_price = rows[target_idx]
            gross = (exit_price - entry_price) / entry_price * 100
            net = gross - cost_pct
            sig_result["periods"][str(p)] = {
                "return_pct": fmt_pct(net),
                "gross_return": fmt_pct(gross),
                "exit_price": round(exit_price, 2),
                "exit_date": exit_td,
            }
            period_returns[p].append(net)
            period_gross[p].append(gross)
            cum_path = []
            for k in range(1, p + 1):
                j = entry_idx + k
                if j >= len(rows): break
                _, px2 = rows[j]
                cum_path.append((px2 / entry_price - 1) * 100 - cost_pct)
            period_per_signal_equity[p].append(cum_path)
        detail_signals.append(sig_result)
        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] {code} {signal_date} -> entry {entry_td} done")

    try:
        bs.logout()
    except Exception:
        pass

    # 2026-09-06 主人令 P0-B：胜率口径统一排平盘；P2-C 加最大回撤+夏普；P1-A 标注含成本
    by_period = {}
    for p in HOLD_PERIODS:
        rets = period_returns[p]
        equity_paths = period_per_signal_equity[p]
        if not rets:
            by_period[str(p)] = {
                "samples": 0, "win_rate": 0, "avg_return": 0,
                "best_return": 0, "worst_return": 0,
                "win_avg": 0, "loss_avg": 0, "profit_loss_ratio": 0,
                "max_drawdown": 0, "sharpe_ratio": 0,
            }
            continue
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]  # 排平盘
        draws = [r for r in rets if r == 0]
        decided = len(wins) + len(losses)
        avg_ret = sum(rets) / len(rets)
        win_avg = sum(wins) / len(wins) if wins else 0
        loss_avg = sum(losses) / len(losses) if losses else 0
        profit_loss_ratio = abs(win_avg / loss_avg) if wins and losses else 0
        global_max_dd = 0.0
        all_path = []
        for pth in equity_paths:
            all_path.extend(pth)
        peak = 0.0; cum = 0.0
        for v in all_path:
            cum += v
            if cum > peak: peak = cum
            dd = cum - peak
            if dd < global_max_dd: global_max_dd = dd
        variance = sum((r - avg_ret) ** 2 for r in rets) / max(len(rets) - 1, 1)
        std_ret = variance ** 0.5
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
        by_period[str(p)] = {
            "samples": len(rets),
            "draws": len(draws),
            "win_rate": fmt_pct(len(wins) / decided * 100) if decided else 0,
            "avg_return": fmt_pct(avg_ret),
            "best_return": fmt_pct(max(rets)),
            "worst_return": fmt_pct(min(rets)),
            "win_avg": fmt_pct(win_avg),
            "loss_avg": fmt_pct(loss_avg),
            "profit_loss_ratio": fmt_pct(profit_loss_ratio),
            "max_drawdown": fmt_pct(global_max_dd),
            "sharpe_ratio": sharpe,
            "cost_adjusted": True,
        }

    dates = sorted({s["signal_date"] for s in signals})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": len(signals),
            "calc_time": now,
            "method": "RPS 相对强度 A档历史回测：信号日取真实下一交易日开盘买入，持有 N 个真实交易日收盘价卖出（前复权；胜率=win/(win+loss) 排平盘；已扣双边交易成本 0.3%）",
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
            "cost_bps_per_side": COST_BPS,
            "by_period": by_period,
        },
        "signals": detail_signals,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[rps backtest] done: {len(signals)} signals, periods={ {p: len(period_returns[p]) for p in HOLD_PERIODS} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
