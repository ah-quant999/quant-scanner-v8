#!/usr/bin/env python3
"""
cockpit_backtest_now.py — 驾驶舱共振候选股滚动回测
口径：与驾驶舱共振候选区一致，取历史 top10_daily 快照中 total_score>=70 的票作为入场信号。

数据流：
1. 读取 data/history/top10_daily_YYYYMMDD.json 所有历史快照
2. 每个交易日快照里筛选 total_score>=70 的票，入场价=快照.close，entry_date=快照日
3. 用 baostock 拉取 entry_date 到最新交易日的收盘价，算浮动收益
4. 输出 data/cockpit_backtest.json（整体胜率/平均收益 + 每只票胜率/平均收益 + 每次信号明细）

滚动机制：每天盘后运行一次，会加入新一天快照，自动扩大样本。
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
from datetime import datetime, timedelta
from collections import defaultdict

import baostock as bs

BASE = os.path.dirname(os.path.abspath(__file__))
HIST_DIR = os.path.join(BASE, "..", "out", "history")
OUT = os.path.join(BASE, "..", "out", "cockpit_backtest.json")
TODAY = datetime.now().strftime("%Y-%m-%d")


def log(msg):
    print(msg, flush=True)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def parse_date(d):
    """把 YYYY-MM-DD 或 YYYYMMDD 统一为 YYYY-MM-DD"""
    d = str(d).replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def last_trade_date():
    """baostock 返回的最后一个交易日；若今天非交易日则自动取上一个"""
    return TODAY


def bs_code(code, market):
    c = str(code).zfill(6)
    m = (market or "").lower()
    # 港股不支持
    if m.startswith("hk") or c.startswith(("0", "1")) and m == "hk":
        return None
    # 北交所 baostock 没有，跳过
    if c.startswith(("8", "4", "92")) and len(c) == 6:
        return None
    if m in ("sh", "sz"):
        return f"{m}.{c}"
    # 兜底：按代码前缀判
    if c[0] == "6":
        return f"sh.{c}"
    return f"sz.{c}"


def bs_fetch_close(bsc, start, end):
    rs = bs.query_history_k_data_plus(
        bsc, fields="date,close", start_date=start, end_date=end,
        frequency="d", adjustflag="2"
    )
    rows = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    return rows


def discover_snapshots():
    """扫描历史快照，返回 {date_str: top10_list}，按日期升序"""
    snaps = {}
    if not os.path.isdir(HIST_DIR):
        return snaps
    pat = re.compile(r"top10_daily_(\d{8})\.json$")
    for fn in os.listdir(HIST_DIR):
        m = pat.match(fn)
        if not m:
            continue
        date_str = parse_date(m.group(1))
        data = load_json(os.path.join(HIST_DIR, fn))
        top10 = data.get("top10", []) if isinstance(data, dict) else []
        if top10:
            snaps[date_str] = top10
    return dict(sorted(snaps.items()))


def build_signals(snaps):
    """从历史快照生成入场信号列表，只保留 total_score>=70 的 A 股"""
    signals = []
    for date_str, top10 in snaps.items():
        for s in top10:
            score = s.get("total_score", 0) or 0
            if score < 70:
                continue
            code = s.get("code", "")
            market = s.get("market", "")
            mlow = str(market).lower()
            # 只测 A 股
            if mlow.startswith("hk") or str(code).startswith("hk"):
                continue
            close = s.get("close", 0)
            if not close or close <= 0:
                continue
            bsc = bs_code(code, market)
            if not bsc:
                continue
            signals.append({
                "entry_date": date_str,
                "code": code,
                "name": s.get("name", ""),
                "market": market,
                "board": s.get("board", "") or s.get("board_label", ""),
                "total_score": score,
                "entry_price": float(close),
                "bsc": bsc,
                "signals": s.get("signals", {}),
                "sectors": s.get("sectors", []),
            })
    return signals


def calc_backtest(signals):
    """用 baostock 拉收盘价，计算每个信号的浮动收益。
    由于历史快照的 entry_date 可能是生成日期（如周六），
    实际取 entry_date 当天或之前最近一个交易日的 baostock 收盘价作为入场价，
    保证入场价与最新价来自同一数据源。"""
    results = []
    per_stock = defaultdict(list)
    win, loss, skip = 0, 0, 0
    all_rets = []

    for i, sig in enumerate(signals):
        try:
            # 向前多取 5 天，确保能找到 entry_date 对应的交易日（含非交易日回退）
            entry_dt = datetime.strptime(sig["entry_date"], "%Y-%m-%d")
            start = (entry_dt - timedelta(days=7)).strftime("%Y-%m-%d")
            rows = bs_fetch_close(sig["bsc"], start, TODAY)
            if not rows:
                skip += 1
                log(f"  跳过 {sig['code']} {sig['name']}: baostock 无数据")
                continue

            # 找到 <= entry_date 的最后一条作为真实入场日
            entry_row = None
            for r in reversed(rows):
                if r[0] <= sig["entry_date"]:
                    entry_row = r
                    break
            if not entry_row:
                skip += 1
                log(f"  跳过 {sig['code']} {sig['name']}: entry_date 前无数据")
                continue

            entry_date = entry_row[0]
            entry_price = float(entry_row[1])
            last_row = rows[-1]
            last_date, last_close = last_row[0], float(last_row[1])

            ret = round((last_close - entry_price) / entry_price * 100, 2)
            rec = {
                "entry_date": entry_date,
                "code": sig["code"],
                "name": sig["name"],
                "market": sig["market"],
                "board": sig["board"],
                "total_score": sig["total_score"],
                "entry_price": entry_price,
                "latest_date": last_date,
                "latest_price": last_close,
                "return_pct": ret,
                "is_win": ret > 0,
                "is_loss": ret < 0,
                "hold_days": max(1, len([r for r in rows if r[0] >= entry_date])),
                "bsc": sig["bsc"],
                "signals": sig["signals"],
                "sectors": sig["sectors"],
            }
            results.append(rec)
            per_stock[sig["code"]].append(rec)
            if ret > 0:
                win += 1
            elif ret < 0:
                loss += 1
            else:
                pass  # 0% 不计入胜负
            all_rets.append(ret)
            log(f"  {entry_date} {sig['code']} {sig['name']} {entry_price:.2f} -> {last_close:.2f} ({last_date}) = {ret:+.2f}%")
            time.sleep(0.1)
        except Exception as e:
            skip += 1
            log(f"  {sig['code']} {sig['name']} FAIL: {str(e)[:80]}")

    return results, per_stock, win, loss, skip, all_rets


def summarize(records):
    """汇总整体 + 按分数段 + 每只票历史胜率"""
    total = len(records)
    wins = [r for r in records if r["is_win"]]
    losses = [r for r in records if r.get("is_loss")]
    draws = [r for r in records if r["return_pct"] == 0]
    rets = [r["return_pct"] for r in records]

    def bucket_stats(sub):
        if not sub:
            return None
        sub_wins = [r for r in sub if r["is_win"]]
        sub_losses = [r for r in sub if r.get("is_loss")]
        sub_rets = [r["return_pct"] for r in sub]
        decided = len(sub_wins) + len(sub_losses)
        return {
            "count": len(sub),
            "win_count": len(sub_wins),
            "loss_count": len(sub_losses),
            "draw_count": len(sub) - decided,
            "win_rate": round(len(sub_wins) / decided * 100, 1) if decided else 0,
            "avg_return": round(sum(sub_rets) / len(sub_rets), 2) if sub_rets else 0,
            "best_return": max(sub_rets) if sub_rets else 0,
            "worst_return": min(sub_rets) if sub_rets else 0,
        }

    overall = bucket_stats(records)
    gte80 = bucket_stats([r for r in records if r["total_score"] >= 80])
    gte70_lt80 = bucket_stats([r for r in records if 70 <= r["total_score"] < 80])

    # 每只票的历史胜率/平均收益
    by_code = defaultdict(list)
    for r in records:
        by_code[r["code"]].append(r)
    stock_summary = []
    for code, subs in by_code.items():
        sub_rets = [r["return_pct"] for r in subs]
        sub_wins = sum(1 for r in subs if r["is_win"])
        sub_losses = sum(1 for r in subs if r.get("is_loss"))
        decided = sub_wins + sub_losses
        stock_summary.append({
            "code": code,
            "name": subs[0]["name"],
            "signals": len(subs),
            "win_count": sub_wins,
            "loss_count": sub_losses,
            "win_rate": round(sub_wins / decided * 100, 1) if decided else 0,
            "avg_return": round(sum(sub_rets) / len(sub_rets), 2) if sub_rets else 0,
            "best_return": max(sub_rets) if sub_rets else 0,
            "worst_return": min(sub_rets) if sub_rets else 0,
        })
    stock_summary.sort(key=lambda x: x["avg_return"], reverse=True)

    return {
        "overall": overall,
        "gte80": gte80,
        "gte70_lt80": gte70_lt80,
        "stock_summary": stock_summary,
    }


def main():
    log("=== 驾驶舱共振候选股滚动回测 ===")
    snaps = discover_snapshots()
    log(f"发现历史快照: {len(snaps)} 天")
    for d in snaps:
        log(f"  {d}: {len(snaps[d])} 只")

    signals = build_signals(snaps)
    log(f"\n入场信号数 (total_score>=70): {len(signals)}")
    if not signals:
        log("⚠️ 暂无 >=70 分历史信号，输出空结果")
        out = {
            "calc_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method": "baostock 真实收盘价滚动回测",
            "signal_criteria": "total_score>=70（与驾驶舱共振候选口径一致）",
            "entry_window": list(snaps.keys())[:1] + [list(snaps.keys())[-1]] if snaps else [],
            "latest_date": TODAY,
            "results": [],
            "summary": {"overall": None, "gte80": None, "gte70_lt80": None, "stock_summary": []},
        }
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return

    log("\n登录 baostock...")
    lg = bs.login()
    log(f"baostock: {lg.error_msg}")

    results, per_stock, win, loss, skip, all_rets = calc_backtest(signals)
    bs.logout()

    summary = summarize(results)
    overall = summary["overall"] or {}

    # 按 entry_date 分组，用于每天对比
    by_date = defaultdict(list)
    for r in results:
        by_date[r["entry_date"]].append(r)

    out = {
        "calc_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": "baostock 真实收盘价滚动回测",
        "signal_criteria": "total_score>=70（与驾驶舱共振候选口径一致）",
        "entry_window": [min(by_date.keys()), max(by_date.keys())] if by_date else [],
        "latest_date": max((r["latest_date"] for r in results), default=TODAY),
        "total_count": overall.get("count", 0),
        "win_count": overall.get("win_count", 0),
        "loss_count": overall.get("loss_count", 0),
        "skipped": skip,
        "win_rate": overall.get("win_rate", 0),
        "avg_return": overall.get("avg_return", 0),
        "best_return": overall.get("best_return", 0),
        "worst_return": overall.get("worst_return", 0),
        "by_date": dict(by_date),
        "by_score": {"gte80": summary["gte80"], "gte70_lt80": summary["gte70_lt80"]},
        "stock_summary": summary["stock_summary"],
        "results": results,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    log("\n=== 结果 ===")
    log(f"有效信号: {out['total_count']} (跳过 {skip})")
    log(f"胜: {out['win_count']} / 负: {out['loss_count']}")
    log(f"胜率: {out['win_rate']}%")
    log(f"平均收益: {out['avg_return']}%")
    log(f"最佳: {out['best_return']}% / 最差: {out['worst_return']}%")
    if summary["gte80"]:
        log(f"≥80 分: {summary['gte80']['win_rate']}% 胜率 / {summary['gte80']['avg_return']}% 平均收益 ({summary['gte80']['count']}只)")
    if summary["gte70_lt80"]:
        g70 = summary["gte70_lt80"]
        log(f"70-79 分: {g70['win_rate']}% 胜率 / {g70['avg_return']}% 平均收益 ({g70['count']}只)")
    log(f"输出: {OUT}")


if __name__ == "__main__":
    main()
