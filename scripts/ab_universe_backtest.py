#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B 选股宇宙回测框架（2026-08-29）
==================================
问题：金股池 65 只 vs 候选池 372 只 vs 全市场，同一信号的收益差异。

用法：
  python scripts/ab_universe_backtest.py

逻辑：
  1. 用 gen_strong_breakout 的 5日突破信号，分别在三组宇宙上选股。
  2. 对每个命中票，用 kline_cache 计算 T+1/3/5/10/20 持有收益（次开入场，扣 0.20% 成本）。
  3. 每日追加到 raw_data/ab_universe_backtest.json，累积 30 天后可判断「缩小范围是否有价值」。

注意：
  - 全市场需要全量 K 线，首次运行会批量拉取（耗时较长）。
  - 本脚本只产「当日信号 + 后续收益追踪骨架」；真实收益要等 T+N 天后回填。
"""
import json
import os
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
OUT = ROOT / "out"
DATA = OUT
sys.path.insert(0, str(ROOT / "algorithms"))

from generate_top10 import _load_kline, _num_code, _market_of

COST = 0.0020
HOLDS = [1, 3, 5, 10, 20]
OUT_JSON = RAW / "ab_universe_backtest.json"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(path, data):
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_quote():
    """读取行情：优先 data/STOCK_QUOTE.js，回退 raw_data/stock_quote.json"""
    d = None
    for p in [ROOT / "data" / "STOCK_QUOTE.js", RAW / "stock_quote.json"]:
        if not p.exists():
            continue
        try:
            src = p.read_text(encoding="utf-8")
            if p.suffix == ".js":
                m = __import__("re").search(r"window\.STOCK_QUOTE\s*=\s*(\{.*\});\s*$", src, __import__("re").S)
                if not m:
                    continue
                d = json.loads(m.group(1))
            else:
                d = json.loads(src)
            break
        except Exception as e:
            print(f"[A/B] {p} 读取失败: {e}")
            continue
    if not d:
        return {}, ""
    meta = d.get("meta", {}) or {}
    qdate = (meta.get("date") or meta.get("update_time") or "")[:10]
    by = {}
    for k, v in (d.get("stocks") or {}).items():
        n = _num_code(k)
        if len(n) == 6:
            by[n] = {
                "name": v.get("name", ""),
                "price": v.get("price"),
                "pct": v.get("pct"),
                "volume": v.get("volume"),
            }
    return by, qdate


def load_universes():
    """返回三组代码集合：gold_pool / candidate_pool / all(from quote)"""
    quote, qdate = load_quote()
    all_codes = set(quote.keys())

    gp = load_json(RAW / "gold_pool.json", {"stocks": {}})
    gold_codes = set(_num_code(c) for c in gp.get("stocks", {}).keys())

    cand = load_json(RAW / "candidate.json", {"stocks": {}})
    cand_codes = set(_num_code(c) for c in cand.get("stocks", {}).keys())

    return {
        "gold": gold_codes & all_codes,
        "candidate": cand_codes & all_codes,
        "all": all_codes,
    }, qdate


def signal_5d_breakout(code, quote):
    """简化版 5日突破：当日涨幅≥3% 且 收盘≥5日最高×0.98"""
    v = quote.get(code)
    if not v or v.get("pct") is None or v.get("price") is None:
        return False
    if v["pct"] < 3.0:
        return False
    rows = _load_kline(code)
    if len(rows) < 6:
        return False
    closes = [r[1] for r in rows]
    hi5 = max(closes[-6:-1])
    return closes[-1] >= hi5 * 0.98


def future_returns(code, signal_date):
    """从 signal_date 次日开盘起算持有期收益"""
    rows = _load_kline(code)
    if not rows:
        return None
    # 找到 signal_date 之后第一个交易日
    idx = -1
    for i, (d, _) in enumerate(rows):
        if d > signal_date:
            idx = i
            break
    if idx < 0 or idx >= len(rows):
        return None
    entry = rows[idx][1]
    if entry <= 0:
        return None
    out = {}
    for n in HOLDS:
        j = idx + n - 1
        if j >= len(rows):
            continue
        exit_p = rows[j][1]
        if exit_p <= 0:
            continue
        gross = (exit_p - entry) / entry * 100
        out[n] = round(gross - COST * 100, 3)
    return out or None


def run_day():
    quote, qdate = load_quote()
    if not quote:
        print("[A/B] 无行情数据，跳过")
        return
    universes, _ = load_universes()
    today = datetime.date.today().isoformat()

    result = load_json(OUT_JSON, {"update_time": "", "days": []})

    day_record = {"date": today, "quote_date": qdate, "universes": {}}
    for name, codes in universes.items():
        hits = []
        for code in sorted(codes):
            if signal_5d_breakout(code, quote):
                hits.append({
                    "code": code,
                    "name": quote.get(code, {}).get("name", ""),
                    "price": quote.get(code, {}).get("price"),
                    "pct": quote.get(code, {}).get("pct"),
                    "returns": None,  # 待 T+N 后回填
                })
        day_record["universes"][name] = {
            "universe_size": len(codes),
            "hits": hits,
            "n_hits": len(hits),
        }
        print(f"[A/B] {name}: 宇宙 {len(codes)} 只，信号 {len(hits)} 只")

    # 回填历史收益（对已有 days 中 returns 为 None 的记录）
    for old in result.get("days", []):
        for uv in old.get("universes", {}).values():
            for h in uv.get("hits", []):
                if h.get("returns") is None:
                    rets = future_returns(h["code"], old["date"])
                    if rets:
                        h["returns"] = rets

    result["days"].append(day_record)
    result["update_time"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_json(OUT_JSON, result)
    print(f"[A/B] 已写入 {OUT_JSON}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "algorithms"))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("scripts/ab_universe_backtest.py"):
        sys.exit(2)
    run_day()
