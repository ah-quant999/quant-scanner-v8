#!/usr/bin/env python3
"""
cockpit_backtest_now.py — 驾驶舱共振候选股滚动回测 V2.0（方案二统一止损止盈）
口径：与驾驶舱共振候选区一致，取历史 top10_daily 快照中 total_score>=70 的票作为入场信号。

数据流：
1. 读取 raw_data/history/top10_daily_YYYYMMDD.json 所有历史快照
2. 每个交易日快照里筛选 total_score>=70 的票，入场价=快照.close，entry_date=快照日
3. 用 baostock 拉取入场前 90 日 ~ 最新交易日的 OHLC
4. 用 stop_target_logic.compute_stop_target 算入场当日的止损/止盈（仅用入场日及之前数据，非未来函数）
5. 从入场次日开始逐日 close 模拟：先触发止损/止盈者按该价出场，否则持有到最新
6. 输出 raw_data/cockpit_backtest.json（整体胜率/平均收益 + 每只票胜率/平均收益 + 每次信号明细）

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
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
from stop_target_logic import compute_stop_target, board_from_code  # noqa: E402

# 🔴 2026-08-06 修复：历史快照目录从 out/history（gitignore，云端丢）→ raw_data/history
HIST_DIR = os.path.join(BASE, "..", "raw_data", "history")
OUT = os.path.join(BASE, "..", "raw_data", "cockpit_backtest.json")
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


def bs_fetch_ohlc(bsc, start, end):
    """拉取前复权日K OHLC，返回 [[date, open, high, low, close], ...]"""
    rs = bs.query_history_k_data_plus(
        bsc, fields="date,open,high,low,close", start_date=start, end_date=end,
        frequency="d", adjustflag="2"
    )
    rows = []
    while (rs.error_code == "0") and rs.next():
        r = rs.get_row_data()
        try:
            if not r[4] or float(r[4]) <= 0:
                continue
        except Exception:
            continue
        rows.append(r)
    return rows


# 兼容旧调用名
bs_fetch_close = bs_fetch_ohlc


def rows_to_df(rows):
    """[[date,open,high,low,close], ...] -> DataFrame(float)"""
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"]).reset_index(drop=True)


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
    """从历史快照生成入场信号列表（只测 A 股）。

    兼容两种评分口径（与 backtest_comprehensive.discover_top10_signals 一致）：
    - 旧数据：total_score 为 0~100 百分制，>=70 视为有效共振。
    - 新数据（2026-08-01 后归一化）：total_score 实际分布偏低（上限约 40），
      若某日无 >=70 的股票，则按 top10 内排名取前 6 名作为共振候选。
    """
    signals = []
    for date_str, top10 in snaps.items():
        ranked = sorted(
            list(enumerate(top10)),
            key=lambda x: (x[1].get("total_score", 0) or 0),
            reverse=True,
        )
        has_legacy_resonance = any((s.get("total_score", 0) or 0) >= 70 for _, s in ranked)

        for rank0, s in ranked:
            score = s.get("total_score", 0) or 0
            rank = rank0 + 1
            if has_legacy_resonance:
                if score < 70:
                    continue
                tier = "gte80" if score >= 80 else "gte70_lt80"
            else:
                # 归一化口径：取当日排名前 6 名
                if rank > 6:
                    continue
                tier = "gte80" if rank <= 3 else "gte70_lt80"
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
                "rank": rank,
                "tier": tier,
                "score_scale": "legacy" if has_legacy_resonance else "normalized",
                "entry_price": float(close),
                "bsc": bsc,
                "signals": s.get("signals", {}),
                "sectors": s.get("sectors", []),
            })
    return signals


def calc_backtest(signals):
    """用 baostock 拉 OHLC，按方案二统一止损止盈口径计算每个信号的收益。

    - 入场价：entry_date 当天或之前最近一个交易日的 baostock 收盘价（与最新价同源）
    - 止损/止盈：用入场日及之前的K线算 compute_stop_target（非未来函数）
    - 出场：入场次日起逐日 close，先触发止损或止盈者按该价出场；未触发则持有到最新
    - return_pct 为「带止损止盈」的真实收益；raw_return_pct 保留「一直持有到今天」的浮动收益
    """
    results = []
    per_stock = defaultdict(list)
    win, loss, skip = 0, 0, 0
    all_rets = []
    exit_stat = {"stop": 0, "target": 0, "hold": 0}

    for i, sig in enumerate(signals):
        try:
            # 向前多取 90 个自然日，保证 ATR(14)/20日高低点有足够样本
            entry_dt = datetime.strptime(sig["entry_date"], "%Y-%m-%d")
            start = (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d")
            rows = bs_fetch_ohlc(sig["bsc"], start, TODAY)
            if not rows:
                skip += 1
                log(f"  跳过 {sig['code']} {sig['name']}: baostock 无数据")
                continue

            # 找到 <= entry_date 的最后一条作为真实入场日
            entry_idx = -1
            for j in range(len(rows) - 1, -1, -1):
                if rows[j][0] <= sig["entry_date"]:
                    entry_idx = j
                    break
            if entry_idx < 0:
                skip += 1
                log(f"  跳过 {sig['code']} {sig['name']}: entry_date 前无数据")
                continue

            df = rows_to_df(rows)
            if entry_idx >= len(df):
                entry_idx = len(df) - 1
            entry_date = str(df["date"].iloc[entry_idx])
            entry_price = float(df["close"].iloc[entry_idx])
            last_date = str(df["date"].iloc[-1])
            last_close = float(df["close"].iloc[-1])

            # 方案二统一止损止盈（只用入场日及之前的数据）
            board = sig.get("board") or board_from_code(sig["code"])
            st = compute_stop_target(df.iloc[: entry_idx + 1], board=board, strategy="cockpit")
            if st:
                stop_loss = st["stop_loss"]
                target_price = st["target_price"]
                stop_method = st["stop_loss_method"]
                target_method = st["target_price_method"]
                risk_reward = st["risk_reward"]
            else:
                # 样本不足回退方案三统一口径：固定10%止损 + R:R=1.5止盈
                stop_loss = round(entry_price * 0.90, 2)
                target_price = round(entry_price * 1.15, 2)
                stop_method = "fixedP10"
                target_method = "rrK1.5"
                risk_reward = 1.5

            # 提前出场模拟（入场次日起逐日 close）
            exit_idx, exit_price, exit_type = entry_idx, entry_price, None
            for k in range(entry_idx + 1, len(df)):
                cp = float(df["close"].iloc[k])
                if cp <= stop_loss:
                    exit_idx, exit_price, exit_type = k, stop_loss, "stop"
                    break
                if cp >= target_price:
                    exit_idx, exit_price, exit_type = k, target_price, "target"
                    break
            if exit_type is None:
                exit_idx, exit_price = len(df) - 1, last_close
            exit_date = str(df["date"].iloc[exit_idx])

            ret = round((exit_price - entry_price) / entry_price * 100, 2)
            raw_ret = round((last_close - entry_price) / entry_price * 100, 2)
            exit_stat[exit_type or "hold"] += 1

            rec = {
                "entry_date": entry_date,
                "code": sig["code"],
                "name": sig["name"],
                "market": sig["market"],
                "board": board,
                "total_score": sig["total_score"],
                "rank": sig.get("rank"),
                "tier": sig.get("tier", "gte70_lt80"),
                "score_scale": sig.get("score_scale", "legacy"),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "stop_loss_method": stop_method,
                "target_price": target_price,
                "target_price_method": target_method,
                "risk_reward": risk_reward,
                "exit_date": exit_date,
                "exit_price": round(exit_price, 2),
                "exit_type": exit_type or "hold",
                "latest_date": last_date,
                "latest_price": last_close,
                "return_pct": ret,
                "raw_return_pct": raw_ret,
                "is_win": ret > 0,
                "is_loss": ret < 0,
                "hold_days": max(1, exit_idx - entry_idx),
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
            all_rets.append(ret)
            tag = {"stop": "止损", "target": "止盈", None: "持有"}[exit_type]
            log(f"  {entry_date} {sig['code']} {sig['name']} {entry_price:.2f} "
                f"[SL {stop_loss:.2f}/TP {target_price:.2f}] -> {exit_price:.2f} "
                f"({exit_date} {tag}) = {ret:+.2f}% (裸持 {raw_ret:+.2f}%)")
            time.sleep(0.1)
        except Exception as e:
            skip += 1
            log(f"  {sig['code']} {sig['name']} FAIL: {str(e)[:80]}")

    return results, per_stock, win, loss, skip, all_rets, exit_stat


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
    # 按 tier 分组（兼容归一化评分：tier 由 build_signals 按分数或排名判定）
    gte80 = bucket_stats([r for r in records if r.get("tier") == "gte80"])
    gte70_lt80 = bucket_stats([r for r in records if r.get("tier") == "gte70_lt80"])

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
    scale = signals[0].get("score_scale", "legacy") if signals else "legacy"
    crit = "total_score>=70" if scale == "legacy" else "当日 top10 排名前 6（评分已归一化）"
    log(f"\n入场信号数 ({crit}): {len(signals)}")
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

    results, per_stock, win, loss, skip, all_rets, exit_stat = calc_backtest(signals)
    bs.logout()

    summary = summarize(results)
    overall = summary["overall"] or {}

    # 按 entry_date 分组，用于每天对比
    by_date = defaultdict(list)
    for r in results:
        by_date[r["entry_date"]].append(r)

    raw_rets = [r.get("raw_return_pct", r["return_pct"]) for r in results]
    out = {
        "calc_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": "baostock 真实K线滚动回测 · 统一止损止盈（低点/ATR×2/固定% 取最严，止盈前高/0.618/R:R=2 cascade）",
        "stop_target_rule": {
            "stop": "max(近20日低点, close-2×ATR14, close×固定%)",
            "fixed_pct": "创业板/科创板 90%，其他 93%",
            "target": "前高 → 0.618 回撤位 → R:R=2，取首个盈亏比≥1.5 者",
            "exit": "入场次日起逐日收盘价触发止损/止盈即出场，否则持有到最新",
        },
        "signal_criteria": f"{crit}（与驾驶舱共振候选口径一致）",
        "score_scale": scale,
        "tier_label": {"gte80": "≥80 分" if scale == "legacy" else "当日前 3 名",
                       "gte70_lt80": "70-79 分" if scale == "legacy" else "当日第 4-6 名"},
        "entry_window": [min(by_date.keys()), max(by_date.keys())] if by_date else [],
        "latest_date": max((r["latest_date"] for r in results), default=TODAY),
        "total_count": overall.get("count", 0),
        "win_count": overall.get("win_count", 0),
        "loss_count": overall.get("loss_count", 0),
        "skipped": skip,
        "exit_stat": exit_stat,
        "avg_raw_return": round(sum(raw_rets) / len(raw_rets), 2) if raw_rets else 0,
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
    log(f"平均收益(带止损止盈): {out['avg_return']}%  |  裸持有: {out['avg_raw_return']}%")
    log(f"出场分布: 止盈 {exit_stat['target']} / 止损 {exit_stat['stop']} / 未触发持有 {exit_stat['hold']}")
    log(f"最佳: {out['best_return']}% / 最差: {out['worst_return']}%")
    lbl = out["tier_label"]
    if summary["gte80"]:
        g80 = summary["gte80"]
        log(f"{lbl['gte80']}: {g80['win_rate']}% 胜率 / {g80['avg_return']}% 平均收益 ({g80['count']}只)")
    if summary["gte70_lt80"]:
        g70 = summary["gte70_lt80"]
        log(f"{lbl['gte70_lt80']}: {g70['win_rate']}% 胜率 / {g70['avg_return']}% 平均收益 ({g70['count']}只)")
    log(f"输出: {OUT}")


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/cockpit_backtest_now.py"):
        sys.exit(2)
    main()
