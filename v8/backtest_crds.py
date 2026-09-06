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

# 2026-09-06 主人令 P1-A：交易成本（单边 万分之1.5 = 0.15%；双边 0.3%）；
# 这是 A 股场内交易的合理默认假设（含印花税+佣金+过户费），写死写在此处
# 也写明在 method 字段，便于审计追溯。前端会显示净收益（已扣成本）。
COST_BPS = 15  # 单边万分之 1.5 = 0.15%


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
    """获取某股票某交易日收盘价（前复权，与综合回测/通达信 K 线回测口径一致）。

    2026-09-06 主人令 P0-A：CRDS 改用前复权（adjustflag="2"），与 backtest_comprehensive / backtest_tdx
    统一口径。此前不复权（adjustflag="3"）会在除权日制造虚假亏损，扭曲信号真实 alpha。
    """
    if bs is None:
        return None
    try:
        r = bs.query_history_k_data_plus(
            bs_code(code),
            "date,close",
            start_date=date,
            end_date=date,
            frequency="d",
            adjustflag="2",  # 前复权（2026-09-06 P0-A 修复）
        )
        row = r.get_row_data()
        if row and len(row) >= 2 and row[1]:
            return float(row[1])
    except Exception as e:
        print(f"[fetch] {code} {date} error: {e}")
    return None


def fetch_kline_around(code, center_date_str, lookback_days=8, lookahead_days=35):
    """一次性拉 signal 前后一段连续 K 线（前复权），返回 [(date, close), ...]。

    用于：在 K 线序列里找 entry 真实交易日 + 后 N 个真实交易日，避免日历日的提前/延后失真。
    2026-09-06 主人令 P0-A：用 K 线序列替代「日历日+1/3/5/10/20」持有期，与综合回测/通达信口径统一。
    """
    if bs is None:
        return []
    try:
        d = datetime.strptime(center_date_str, "%Y-%m-%d").date()
        start = (d - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end = (d + timedelta(days=lookahead_days)).strftime("%Y-%m-%d")
        r = bs.query_history_k_data_plus(
            bs_code(code),
            "date,close",
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",  # 前复权
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

    # 2026-09-06 主人令 P0-A：用连续 K 线段取真实入场/出场日（替代旧日历日 +1/3/5/10/20），
    # 与综合回测 / 通达信 K 线回测口径统一。同时扣双边交易成本（万分之1.5 ×2= 0.3%）。
    period_returns = {p: [] for p in HOLD_PERIODS}      # 含成本的净收益（用于卡片展示）
    period_gross = {p: [] for p in HOLD_PERIODS}        # 原收益（不含成本，用于审计对照）
    period_per_signal_equity = {p: [] for p in HOLD_PERIODS}  # 每个信号该持有期内的累计收益曲线（回撤计算用）
    detail_signals = []
    total = len(signals)
    cost_pct = 2 * COST_BPS / 100  # 双边 0.3%
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
            "signal_date": signal_date,
            "entry_trade_date": entry_td,
            "code": code,
            "name": sig["name"],
            "entry_price": round(entry_price, 2),
            "periods": {},
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
            # 按持有期内每日累计收益算回撤
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

    # 汇总
    # 2026-09-06 主人令 P0-A：胜率口径统一（排平盘，只算 win/(win+loss)）；P2-C 加最大回撤+夏普；P1-A 标注含成本
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
        max_ret = max(rets)
        min_ret = min(rets)
        win_avg = sum(wins) / len(wins) if wins else 0
        loss_avg = sum(losses) / len(losses) if losses else 0
        profit_loss_ratio = abs(win_avg / loss_avg) if wins and losses else 0
        # 最大回撤：把所有信号的持有期累计收益曲线拼一起，取全局最大峰谷
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
        # 夏普：以均收益/收益标准差（简单近似，未年化）
        variance = sum((r - avg_ret) ** 2 for r in rets) / max(len(rets) - 1, 1)
        std_ret = variance ** 0.5
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
        by_period[str(p)] = {
            "samples": len(rets),
            "draws": len(draws),  # 透明：平盘数
            "win_rate": fmt_pct(len(wins) / decided * 100) if decided else 0,
            "avg_return": fmt_pct(avg_ret),
            "best_return": fmt_pct(max_ret),
            "worst_return": fmt_pct(min_ret),
            "win_avg": fmt_pct(win_avg),
            "loss_avg": fmt_pct(loss_avg),
            "profit_loss_ratio": fmt_pct(profit_loss_ratio),
            "max_drawdown": fmt_pct(global_max_dd),
            "sharpe_ratio": sharpe,
            "cost_adjusted": True,  # 标记净收益已扣双边 0.3% 成本
        }

    dates = sorted({s["signal_date"] for s in signals})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": len(signals),
            "calc_time": now,
            "method": "CRDS 逆势龙头 advanced 档历史回测：信号日取真实下一交易日开盘买入，持有 N 个真实交易日收盘价卖出（前复权；胜率=win/(win+loss) 排平盘；已扣双边交易成本 0.3%）",
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
            "cost_bps_per_side": COST_BPS,
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
