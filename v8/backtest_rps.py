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
    if bs is None:
        return None
    try:
        r = bs.query_history_k_data_plus(
            bs_code(code), "date,close",
            start_date=date, end_date=date, frequency="d", adjustflag="3",
        )
        row = r.get_row_data()
        if row and len(row) >= 2 and row[1]:
            return float(row[1])
    except Exception as e:
        print(f"[fetch] {code} {date} error: {e}")
    return None


def fmt_pct(v):
    return round(v, 2)


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

    period_returns = {p: [] for p in HOLD_PERIODS}
    detail_signals = []
    total = len(signals)
    for idx, sig in enumerate(signals, 1):
        code = sig["code"]
        entry_date = sig["signal_date"]
        entry_price = fetch_close(code, entry_date)
        if entry_price is None or entry_price <= 0:
            print(f"[{idx}/{total}] skip {code} {entry_date}: no entry price")
            continue
        sig_result = {
            "signal_date": entry_date, "code": code, "name": sig["name"],
            "entry_price": entry_price, "periods": {},
        }
        for p in HOLD_PERIODS:
            exit_date = add_trade_days(entry_date, p)
            exit_price = fetch_close(code, exit_date)
            if exit_price is None or exit_price <= 0:
                sig_result["periods"][str(p)] = {"return_pct": None, "exit_price": None, "exit_date": exit_date}
                continue
            ret = (exit_price - entry_price) / entry_price * 100
            sig_result["periods"][str(p)] = {"return_pct": fmt_pct(ret), "exit_price": exit_price, "exit_date": exit_date}
            period_returns[p].append(ret)
        detail_signals.append(sig_result)
        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] {code} {entry_date} done")

    try:
        bs.logout()
    except Exception:
        pass

    by_period = {}
    for p in HOLD_PERIODS:
        rets = period_returns[p]
        if not rets:
            by_period[str(p)] = {
                "samples": 0, "win_rate": 0, "avg_return": 0,
                "best_return": 0, "worst_return": 0,
                "win_avg": 0, "loss_avg": 0, "profit_loss_ratio": 0,
            }
            continue
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        by_period[str(p)] = {
            "samples": len(rets),
            "win_rate": fmt_pct(len(wins) / len(rets) * 100),
            "avg_return": fmt_pct(sum(rets) / len(rets)),
            "best_return": fmt_pct(max(rets)),
            "worst_return": fmt_pct(min(rets)),
            "win_avg": fmt_pct(sum(wins) / len(wins)) if wins else 0,
            "loss_avg": fmt_pct(sum(losses) / len(losses)) if losses else 0,
            "profit_loss_ratio": fmt_pct(abs((sum(wins) / len(wins)) / (sum(losses) / len(losses)))) if wins and losses else 0,
        }

    dates = sorted({s["signal_date"] for s in signals})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": len(signals),
            "calc_time": now,
            "method": "RPS 相对强度 A档历史回测：信号日收盘价买入，持有N个交易日收盘价卖出（不处理节假日，按日历日+1/3/5/10/20）",
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
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
