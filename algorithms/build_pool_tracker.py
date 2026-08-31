#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pool_tracker.py — v8 选股生命周期跟踪（阶段 1）

输入：
  raw_data/algo_track.json — v8 三大算法（四量终极 / 板块龙头 / 大牛股猎手）的真实跟踪池，
       含 list_date/entry_price/last_close/last_pct/peak_pct/days_in/appear_count/signal_detail

算法：
  1. 合并三 algo 的 tracking 列表，按 code 去重（保留 peak_pct 最大者，记录首个 algo）。
  2. 计算 drawdown = peak_pct - last_pct。
  3. 应用专家阈值判状态（移植 track_daily.py 的 analyze()，用 v8 已有字段近似）：
       - 强势 strong: peak_pct > 0 且 drawdown <= 3%（仍贴近期高点/主升）
                     或 peak_pct > 0 且 days_in >= 3 且 last_pct > 0（连涨确认）
       - 回调买点 buy_dip: peak_pct > 0 且 drawdown ∈ [6%, 12%] 且 last_pct < 0
       - 见顶 topped: peak_pct > 0 且 drawdown >= 10% 且 days_in >= 3 且 last_pct < 0
                     或 peak_pct > 0 且 drawdown >= 15%
       - 走弱 weak: peak_pct <= 0（峰值未跑赢基准）
                   或 drawdown >= 20%（深回撤）
                   或 last_pct <= -8%（重挫）
       - 正常 normal: 以上皆不满足
  4. buy_hint：
       - buy_dip 状态 → "回调买点（回撤 {drawdown:.1f}%）"
       - 强势状态 且 days_in >= 3 且 last_pct > 0 → "连涨强势确认（{days_in}天）"
       - else null
  5. sell_hint：
       - 见顶 → "见顶：回撤 {drawdown:.1f}%"
       - 走弱 → "走弱：跌破基准价" / "走弱：回撤过大"
       - else null
  6. 按状态分桶，按 peak_pct 降序、days_in 降序。

输出：
  raw_data/v8_pool_tracker.json
  data/V8_POOL_TRACKER.js  （window.V8_POOL_TRACKER = {...};）

🛡 2026-08-31 一劳永逸：
  - 只读 algo_track.json 已有的 entry/last/peak/days_in 字段，零网络依赖（家里机/云端都能跑）。
  - 去重 by code，防同一只股票在多 algo 中重复上榜。
  - 空文件容错：algo_track.json 缺失或 algos 为空 → 输出空池 + 占位文案，不抛错。
  - 状态阈值集中在 _status_decide() 一处，未来回测调参改一处即可。
"""
import json
import os
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")

ALGO_TRACK_PATH = os.path.join(RAW_DIR, "algo_track.json")
OUT_JSON_PATH = os.path.join(RAW_DIR, "v8_pool_tracker.json")
OUT_JS_PATH = os.path.join(DATA_DIR, "V8_POOL_TRACKER.js")


def log(msg):
    print(f"  [pool-tracker] {msg}", flush=True)


def _status_decide(peak_pct: float, last_pct: float, days_in: int) -> tuple:
    """根据 v8 跟踪数据近似专家阈值，返回 (status, buy_hint, sell_hint)。
    状态取：strong/buy_dip/topped/weak/normal。"""
    drawdown = round(peak_pct - last_pct, 2)

    # 走弱（最低优先级，先判以免被后续阈值吃掉）
    if peak_pct <= 0:
        return ("weak", None, "走弱：峰值未跑赢基准价")
    if drawdown >= 20:
        return ("weak", None, f"走弱：深回撤 {drawdown:.1f}%")
    if last_pct <= -8:
        return ("weak", None, "走弱：重挫破位")

    # 见顶
    if drawdown >= 10 and days_in >= 3 and last_pct < 0:
        return ("topped", None, f"见顶：回撤 {drawdown:.1f}%、持仓 {days_in} 日")
    if drawdown >= 15 and peak_pct > 0:
        return ("topped", None, f"见顶：深回撤 {drawdown:.1f}%")

    # 回调买点（专家阈值的核心买点信号）
    if peak_pct > 0 and 6 <= drawdown <= 12 and last_pct < 0:
        return ("buy_dip", f"回调买点（回撤 {drawdown:.1f}%）", None)

    # 强势
    if drawdown <= 3 and peak_pct > 0:
        return ("strong", None, None)
    if days_in >= 3 and last_pct > 0 and peak_pct > 0:
        hint = f"连涨强势确认（{days_in} 天）" if days_in >= 3 else None
        return ("strong", hint, None)

    # 正常
    return ("normal", None, None)


def load_algo_track():
    """读 algo_track.json，缺/坏返回 None。"""
    if not os.path.exists(ALGO_TRACK_PATH):
        log(f"⚠️ 缺失：{ALGO_TRACK_PATH}")
        return None
    try:
        with open(ALGO_TRACK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"⚠️ 解析失败：{e}")
        return None


def dedupe_by_code(algos):
    """合并多 algo 的 tracking，按 code 去重（保留 peak_pct 最大者，记录首个 algo）。"""
    best = {}
    for alg in algos:
        algo_key = alg.get("algo", "")
        display = alg.get("display_name", algo_key)
        for t in alg.get("tracking", []):
            code = t.get("code")
            if not code:
                continue
            peak = float(t.get("peak_pct") or 0)
            prev = best.get(code)
            if (prev is None) or (peak > float(prev.get("peak_pct") or 0)):
                best[code] = dict(t, _algo=display)
    return list(best.values())


def build_items(merged):
    """对每只跟踪股算 status / buy_hint / sell_hint / drawdown。"""
    items = []
    for it in merged:
        peak = float(it.get("peak_pct") or 0)
        last = float(it.get("last_pct") or 0)
        days = int(it.get("days_in") or 0)
        status, buy_hint, sell_hint = _status_decide(peak, last, days)
        items.append({
            "code": it["code"],
            "name": it.get("name", ""),
            "algo": it.get("_algo", ""),
            "list_date": it.get("list_date_dashed") or it.get("list_date", ""),
            "entry_price": float(it.get("entry_price") or 0),
            "last_close": float(it.get("last_close") or 0),
            "last_pct": last,
            "peak_pct": peak,
            "drawdown": round(peak - last, 2),
            "days_in": days,
            "appear_count": int(it.get("appear_count") or 1),
            "status": status,
            "buy_hint": buy_hint,
            "sell_hint": sell_hint,
            "signal_reason": (it.get("signal_detail") or {}).get("reason", ""),
        })
    return items


def aggregate(items):
    """算 status_counts + by_algo。"""
    status_counts = defaultdict(int)
    by_algo = defaultdict(lambda: defaultdict(int))
    for it in items:
        status_counts[it["status"]] += 1
        by_algo[it["algo"]]["total"] += 1
        by_algo[it["algo"]][it["status"]] += 1
    return dict(status_counts), {k: dict(v) for k, v in by_algo.items()}


def main():
    print(f"[build_pool_tracker] {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("读取 v8 算法跟踪池（零网络依赖）…")
    data = load_algo_track()
    if not data:
        log("❌ algo_track.json 不可用，输出空占位")
        out = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pool_size": 0, "raw_pool_size": 0,
            "status_counts": {}, "by_algo": {}, "items": [],
            "note": "algo_track.json 缺失或解析失败",
        }
    else:
        raw_pool_size = sum(len(a.get("tracking", [])) for a in data.get("algos", []))
        merged = dedupe_by_code(data.get("algos", []))
        items = build_items(merged)
        status_counts, by_algo = aggregate(items)
        # 按 bucket 排序（强势：peak_pct desc；其他：drawdown asc 优先，days_in desc）
        def _sort_key(it):
            if it["status"] == "strong":
                return (0, -it["peak_pct"], -it["days_in"])
            if it["status"] == "buy_dip":
                return (0, it["drawdown"], -it["days_in"])
            return (0, -it["peak_pct"], -it["days_in"])
        items.sort(key=_sort_key)
        out = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pool_size": len(items),
            "raw_pool_size": raw_pool_size,
            "status_counts": status_counts,
            "by_algo": by_algo,
            "items": items,
            "note": (
                f"基于 v8 三大算法跟踪池 {raw_pool_size} 只去重 → {len(items)} 只；"
                "阈值源自专家 track_daily.py analyze()（强势/回调6-12%/见顶/走弱）"
            ),
        }
        log(f"✅ 入池 {len(items)} 只（去重前 {raw_pool_size}）；状态分布 {dict(status_counts)}")

    # 写 raw_data
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log(f"📝 raw_data → {OUT_JSON_PATH}")

    # 写 data/*.js（window.V8_POOL_TRACKER 注入）
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    js_body = (
        "/* v8 选股生命周期跟踪 · 自动生成，请勿手改 */\n"
        "window.V8_POOL_TRACKER = " + payload + ";\n"
    )
    with open(OUT_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_body)
    log(f"📝 data → {OUT_JS_PATH} ({len(js_body)} bytes)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())