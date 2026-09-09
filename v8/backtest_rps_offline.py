#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_rps_offline.py — RPS A 档离线回测（kline_cache 替 baostock）

🔴 2026-09-10 主人令：阿狸咪（家用中国宽带）baostock 被风控黑名单（10001011 匿名用户），
   但本机 raw_data/kline_cache/ 已有 2724 只股票近 60 日 K 线，覆盖 A 档 96.9%。
   用本地缓存替 baostock 跑 T+1/T+3/T+5/T+10/T+20 真实收益回测，缺的窗口 samples=0
   + degraded=true，不冒充"小九在线产出"。

用法：python v8/backtest_rps_offline.py
产出：raw_data/rps_backtest.json + data/RPS_BACKTEST.js（与 baostock 版同 schema）
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(os.environ.get('V8_ROOT', os.getcwd())).resolve()
# 兜底：如果 V8_ROOT 不对，向上找到含 raw_data 的目录
if not (HERE / 'raw_data').exists():
    cur = HERE
    while cur.parent != cur:
        cur = cur.parent
        if (cur / 'raw_data').exists():
            HERE = cur
            break
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
HISTORY_DIR = RAW_DIR / "history"
CACHE_DIR = RAW_DIR / "kline_cache"
OUT_JSON = RAW_DIR / "rps_backtest.json"
OUT_JS = DATA_DIR / "RPS_BACKTEST.js"
HOLD_PERIODS = [1, 3, 5, 10, 20]
COST_BPS = 15  # 双边 0.3%


def parse_date_from_filename(name):
    stem = Path(name).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    if len(digits) >= 8:
        d = digits[-8:]
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def load_signals():
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


def load_cache_kline(code):
    """读 raw_data/kline_cache/<code>.json → list[(date, close)]"""
    p = CACHE_DIR / f"{code}.json"
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for r in rows:
        d = r.get("date", "")[:10]
        c = r.get("close")
        if d and c not in (None, "", "None"):
            try:
                out.append((d, float(c)))
            except (TypeError, ValueError):
                pass
    out.sort(key=lambda x: x[0])
    return out


def fetch_kline_around(code, center_date_str, lookback_days=8, lookahead_days=35):
    return load_cache_kline(code)


def fmt_pct(v):
    return round(v, 2)


def empty_backtest(reason, degraded=True):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "degraded": degraded,
        "summary": {
            "update_time": now,
            "total_signals": 0,
            "calc_time": now,
            "method": f"RPS 离线回测 · {reason}",
            "signal_date_range": "—",
            "by_period": {
                str(p): {
                    "samples": 0, "win_rate": 0, "avg_return": 0,
                    "best_return": 0, "worst_return": 0,
                    "win_avg": 0, "loss_avg": 0, "profit_loss_ratio": 0,
                    "max_drawdown": 0, "sharpe_ratio": 0,
                }
                for p in HOLD_PERIODS
            },
        },
        "signals": [],
    }
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只统计信号数，不算持有期")
    args = parser.parse_args()

    signals = load_signals()
    print(f"[rps offline] loaded {len(signals)} A-tier signals")

    if not signals:
        payload = empty_backtest("无历史 stock_rps A档信号")
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[rps offline] written empty backtest")
        return 0

    # 信号股 cache 覆盖率统计
    cache_hit = sum(1 for s in signals if (CACHE_DIR / f"{s['code']}.json").exists())
    print(f"[rps offline] cache coverage: {cache_hit}/{len(signals)} = {cache_hit/len(signals)*100:.1f}%")

    if args.dry:
        dates = sorted({s["signal_date"] for s in signals})
        print(f"[DRY] date range: {dates[0]} ~ {dates[-1]}, signals={len(signals)}")
        return 0

    period_returns = {p: [] for p in HOLD_PERIODS}
    period_gross = {p: [] for p in HOLD_PERIODS}
    period_per_signal_equity = {p: [] for p in HOLD_PERIODS}
    detail_signals = []
    total = len(signals)
    cost_pct = 2 * COST_BPS / 100
    skipped_no_cache = 0
    skipped_no_window = 0

    for idx, sig in enumerate(signals, 1):
        code = sig["code"]
        signal_date = sig["signal_date"]
        rows = fetch_kline_around(code, signal_date)
        if not rows:
            skipped_no_cache += 1
            continue
        entry_idx = None
        for i, (d, _) in enumerate(rows):
            if d >= signal_date:
                entry_idx = i
                break
        if entry_idx is None:
            skipped_no_window += 1
            continue
        entry_td, entry_price = rows[entry_idx]
        if entry_price is None or entry_price <= 0:
            continue
        sig_result = {
            "signal_date": signal_date, "entry_trade_date": entry_td, "code": code, "name": sig["name"],
            "entry_price": round(entry_price, 2), "periods": {},
        }
        any_period_calculated = False
        for p in HOLD_PERIODS:
            target_idx = entry_idx + p
            if target_idx >= len(rows):
                sig_result["periods"][str(p)] = {
                    "return_pct": None, "gross_return": None, "exit_price": None, "exit_date": None,
                }
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
                if j >= len(rows):
                    break
                _, px2 = rows[j]
                cum_path.append((px2 / entry_price - 1) * 100 - cost_pct)
            period_per_signal_equity[p].append(cum_path)
            any_period_calculated = True
        if any_period_calculated:
            detail_signals.append(sig_result)
        if idx % 20 == 0 or idx == total:
            print(f"[{idx}/{total}] {code} {signal_date} -> entry {entry_td} done")

    print(f"[rps offline] skipped_no_cache={skipped_no_cache}, skipped_no_window={skipped_no_window}")

    by_period = {}
    for p in HOLD_PERIODS:
        rets = period_returns[p]
        equity_paths = period_per_signal_equity[p]
        if not rets:
            by_period[str(p)] = {
                "samples": 0, "draws": 0, "win_rate": 0, "avg_return": 0,
                "best_return": 0, "worst_return": 0, "win_avg": 0, "loss_avg": 0,
                "profit_loss_ratio": 0, "max_drawdown": 0, "sharpe_ratio": 0,
            }
            continue
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]
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
        peak = 0.0
        cum = 0.0
        for v in all_path:
            cum += v
            if cum > peak:
                peak = cum
            dd = cum - peak
            if dd < global_max_dd:
                global_max_dd = dd
        variance = sum((r - avg_ret) ** 2 for r in rets) / max(len(rets) - 1, 1)
        std_ret = variance ** 0.5
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
        by_period[str(p)] = {
            "samples": len(rets), "draws": len(draws),
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
    degraded = (skipped_no_cache + skipped_no_window) > 0
    samples_per_period = {p: by_period[str(p)]["samples"] for p in HOLD_PERIODS}
    # 如果所有期都 0 samples → 彻底退化
    if all(s == 0 for s in samples_per_period.values()):
        method_desc = (
            "RPS 离线回测：基于 raw_data/kline_cache 本地缓存。⚠️ 本机 baostock 被风控黑名单"
            "(10001011 匿名用户)，T+1~T+20 持有期数据全部缺失（kline_cache 仅缓存至 09-08，"
            "无法覆盖 09-08 后持有窗口)。需待小九中国 IP 在线跑 baostock 版获取完整回测。"
        )
        degraded_reason = "本机 baostock 被风控 + kline_cache 仅覆盖至 09-08，无法计算持有期收益"
    elif samples_per_period.get(1, 0) == 0:
        method_desc = (
            "RPS 离线回测（部分缺失）：基于 raw_data/kline_cache 本地缓存。"
            "T+1 完整样本数=0 仅 T+3+ 有数据（kline_cache 09-05 缺日/09-08 后持有期缺）。"
            "需待小九中国 IP 在线跑 baostock 版获取完整回测。"
        )
        degraded_reason = "T+1 样本=0，cache 部分覆盖"
    else:
        method_desc = (
            f"RPS 离线回测：基于 raw_data/kline_cache 本地缓存（T+1~T+20 各期样本数="
            f"{samples_per_period}）。⚠️ 本机 baostock 被风控黑名单(10001011 匿名用户)，"
            f"仅用本地缓存；持有期窗口超出 cache 范围的 periods 样本=0。"
            f"需待小九中国 IP 在线跑 baostock 版获取完整回测。"
        )
        degraded_reason = "本地 cache 覆盖，baostock 版需小九中国 IP"

    payload = {
        "update_time": now,
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "summary": {
            "update_time": now,
            "total_signals": len(signals),
            "calc_time": now,
            "method": method_desc,
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
            "cost_bps_per_side": COST_BPS,
            "cache_hit_rate": round(cache_hit / len(signals) * 100, 1),
            "skipped_no_cache": skipped_no_cache,
            "skipped_no_window": skipped_no_window,
            "by_period": by_period,
        },
        "signals": detail_signals,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[rps offline] done: {len(signals)} signals, samples={samples_per_period}, degraded={degraded}")
    return 0


if __name__ == "__main__":
    sys.exit(main())