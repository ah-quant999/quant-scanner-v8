#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_crds.py — CRDS 逆势龙头（advanced 档位）历史回测

背景：
  CRDS_CARD_DATA 将信号分为 elite / advanced / watch 三档，
  其中 advanced 为默认主推档（cond1+cond3 重合或得分前列）。

本脚本：
  1. 读取 out/history/crds_*.json + raw_data/history/crds_*.json 历史 CRDS 输出。
  2. 取每日 advanced 列表作为信号（信号日收盘价买入）。
  3. 用 baostock 拉取信号股日K线，计算 T+1/T+3/T+5/T+10/T+20 持有期收益。
  4. 输出 raw_data/crds_backtest.json + data/CRDS_BACKTEST.js。

输出字段（与 HUNTER_BACKTEST 同构，便于前端统一渲染）：
  - summary: update_time, total_signals, calc_time, method, signal_date_range,
             by_period {1/3/5/10/20: {samples, win_rate, avg_return, best_return, worst_return, ...}}
  - signals: 逐信号明细

使用：
  python v8/backtest_crds.py              # 全量回测
  python v8/backtest_crds.py --dry        # 只统计信号数，不拉K线

注意：
  - baostock 登录失败时自动降级为空回测（避免 CI 挂死）。
  - 历史文件时间戳为文件名后 8 位 yyyymmdd，优先取文件内的 update_time/data_time。
"""
import argparse
import json
import os
import sys
import time
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
HISTORY_DIRS = [HERE / "out" / "history", RAW_DIR / "history"]
OUT_JSON = RAW_DIR / "crds_backtest.json"
OUT_JS = DATA_DIR / "CRDS_BACKTEST.js"
HOLD_PERIODS = [1, 3, 5, 10, 20]


def parse_date_from_filename(name):
    """crds_20260817.json -> 2026-08-17"""
    stem = Path(name).stem
    if stem.startswith("crds_") and len(stem) >= 13:
        d = stem[-8:]
        if d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def load_signals():
    """加载历史 CRDS advanced 信号。"""
    signals = []
    seen = set()
    for hist_dir in HISTORY_DIRS:
        if not hist_dir.exists():
            continue
        for f in sorted(hist_dir.glob("crds_*.json")):
            if f.name == "crds_history.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[skip] {f}: {e}")
                continue
            # 取日期：内部元数据优先
            dt = (data.get("update_time") or data.get("data_time") or "").strip()[:10]
            if not dt or dt == "2026-09-02":
                # 内部日期缺失或明显为今天（可能是重建），用文件名
                dt = parse_date_from_filename(f.name)
            if not dt or len(dt) != 10:
                continue
            # 取 advanced 档信号
            advanced = data.get("advanced") or []
            if not advanced and data.get("cond3_list"):
                advanced = data.get("cond3_list")
            for s in advanced:
                code = str(s.get("code", "")).strip()
                name = str(s.get("name", "")).strip()
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
    """6位代码转 baostock 格式。"""
    code = code.zfill(6)
    if code.startswith("6") or code.startswith("5") or code.startswith("11") or code.startswith("51"):
        return f"sh.{code}"
    return f"sz.{code}"


def add_trade_days(date_str, n):
    """简单版：按日历日加，不处理节假日。回测口径与 HUNTER_BACKTEST 保持一致即可。"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    d += timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def fetch_close(code, date):
    """获取某股票某交易日收盘价。"""
    if bs is None:
        return None
    try:
        r = bs.query_history_k_data_plus(
            bs_code(code),
            "date,close",
            start_date=date,
            end_date=date,
            frequency="d",
            adjustflag="3",
        )
        row = r.get_row_data()
        if row and len(row) >= 2 and row[1]:
            return float(row[1])
    except Exception as e:
        print(f"[fetch] {code} {date} error: {e}")
    return None


def fmt_pct(v):
    return round(v, 2)


def fetch_close_roll(code, date_str, max_fwd=8):
    """向前滚动到最近的交易日取收盘价。

    信号生成日可能是周末/节假日（如 2026-08-01 为周六），无法在当日买入，
    须顺延到下一交易日。逐日尝试直到取到有效收盘价即视为该信号的交易日。
    """
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
            "method": f"CRDS 逆势龙头 advanced 档历史回测 · {reason}",
            "signal_date_range": "—",
            "by_period": {
                str(p): {
                    "samples": 0,
                    "win_rate": 0,
                    "avg_return": 0,
                    "best_return": 0,
                    "worst_return": 0,
                    "win_avg": 0,
                    "loss_avg": 0,
                    "profit_loss_ratio": 0,
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
    print(f"[CRDS backtest] loaded {len(signals)} advanced signals")
    if not signals:
        payload = empty_backtest("无历史 advanced 信号")
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[CRDS backtest] written empty backtest")
        return 0

    if args.dry:
        dates = sorted({s["signal_date"] for s in signals})
        print(f"[DRY] date range: {dates[0]} ~ {dates[-1]}, signals={len(signals)}")
        return 0

    if not baostock_login():
        payload = empty_backtest("baostock 登录失败，自动降级")
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[CRDS backtest] baostock login failed -> empty backtest")
        return 0

    # 计算每个信号各持有期收益
    period_returns = {p: [] for p in HOLD_PERIODS}
    detail_signals = []
    total = len(signals)
    for idx, sig in enumerate(signals, 1):
        code = sig["code"]
        entry_date = sig["signal_date"]
        entry_price, entry_td = fetch_close_roll(code, entry_date)
        if entry_price is None or entry_price <= 0:
            print(f"[{idx}/{total}] skip {code} {entry_date}: no entry price (rolled)")
            continue
        sig_result = {
            "signal_date": entry_date,
            "entry_trade_date": entry_td,
            "code": code,
            "name": sig["name"],
            "entry_price": entry_price,
            "periods": {},
        }
        for p in HOLD_PERIODS:
            exit_target = (datetime.strptime(entry_td, "%Y-%m-%d").date() + timedelta(days=p)).strftime("%Y-%m-%d")
            exit_price, exit_td = fetch_close_roll(code, exit_target)
            if exit_price is None or exit_price <= 0:
                sig_result["periods"][str(p)] = {"return_pct": None, "exit_price": None, "exit_date": exit_target}
                continue
            ret = (exit_price - entry_price) / entry_price * 100
            sig_result["periods"][str(p)] = {"return_pct": fmt_pct(ret), "exit_price": exit_price, "exit_date": exit_td}
            period_returns[p].append(ret)
        detail_signals.append(sig_result)
        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] {code} {entry_date} -> entry {entry_td} done")

    try:
        bs.logout()
    except Exception:
        pass

    # 汇总
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
            "method": "CRDS 逆势龙头 advanced 档历史回测：信号日收盘价买入，持有N个交易日收盘价卖出（不处理节假日，按日历日+1/3/5/10/20）",
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
            "by_period": by_period,
        },
        "signals": detail_signals,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[CRDS backtest] done: {len(signals)} signals, periods={ {p: len(period_returns[p]) for p in HOLD_PERIODS} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
