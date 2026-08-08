#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_stock_stop.py — v8 算法精确止损/止盈（方案三：全站统一 fixedP10/rrK1.5）

产出 data/STOCK_STOP_DATA.js（window.STOCK_STOP_DATA），为「今日可入手候选」卡片与
个股查询界面提供固定10%止损 + R:R=1.5止盈的统一口径。

候选宇宙：TRIPLE_CONSENSUS + COCKPIT_TIER_RECOMMEND(tier_a) + FOUR_VOLUME + GOLD_POOL
（金股池虽已移出候选卡，但其独立卡片与个股查询仍可用精确止损，故一并计算）。
"""
import json
import os
import re
import sys
from datetime import datetime

ALGO = os.path.dirname(os.path.abspath(__file__))
V8_ROOT = os.path.dirname(ALGO)
DATA_DIR = os.path.join(V8_ROOT, "data")
sys.path.insert(0, ALGO)

from data_source_gtimg import fetch_a_daily_gtimg  # noqa: E402
from stop_target_logic import (  # noqa: E402
    compute_stop_target,
    board_from_code,
    PRICE_WINDOW,
)


def load_js(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", txt, re.S)
    return json.loads(m.group(1)) if m else None


def gtimg_market(code, market_str):
    """映射成 gtimg 支持的 sh/sz 前缀；港股/北交所返回 None（跳过）。"""
    code = str(code or "").strip()
    digits = re.sub(r"\D", "", code)
    ms = (market_str or "").lower()
    if ms == "港股" or (len(digits) == 5 and digits.startswith("0")):
        return None  # 港股
    if ms == "bj":
        return None  # 北交所 gtimg 日K 不稳，跳过
    if ms in ("sh", "sz"):
        return ms
    # 退化推断：6 开头上证，其余深证
    return "sh" if digits.startswith("6") else "sz"


def collect_universe():
    """code -> {market, board, name}。board 优先用源数据，缺失则按代码推断。"""
    codes = {}

    def add(s):
        if not s or not s.get("code"):
            return
        code = str(s.get("code"))
        board = s.get("board") or s.get("board_label") or board_from_code(code)
        codes[code] = {
            "market": s.get("market", ""),
            "board": board,
            "name": s.get("name", ""),
        }

    tc = load_js("TRIPLE_CONSENSUS.js")
    if tc:
        for s in tc.get("stocks", []) or []:
            add(s)

    cr = load_js("COCKPIT_TIER_RECOMMEND.js")
    if cr:
        for s in cr.get("tier_a", []) or []:
            add(s)

    fv = load_js("FOUR_VOLUME.js")
    if fv:
        for s in fv.get("stocks", []) or []:
            add(s)

    gp = load_js("GOLD_POOL.js")
    if gp:
        for k, s in (gp.get("stocks", {}) or {}).items():
            add(s)

    return codes


def main():
    print(f"=== gen_stock_stop (方案三统一 fixedP10/rrK1.5)  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    universe = collect_universe()
    print(f"候选宇宙去重: {len(universe)} 只")

    stocks = {}
    ok = skip = fail = 0
    for code, meta in universe.items():
        gmkt = gtimg_market(code, meta["market"])
        if not gmkt:
            skip += 1
            continue
        digits = re.sub(r"\D", "", str(code))
        try:
            df = fetch_a_daily_gtimg(digits, gmkt, bars=250)
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️ {code} 取K线异常: {e}")
            fail += 1
            continue
        stats = compute_stop_target(df, board=meta.get("board", "主板"), strategy="general")
        if not stats:
            fail += 1
            continue
        stats["market"] = gmkt
        stocks[str(code)] = stats
        ok += 1

    method_desc = (
        "全站统一口径(方案三优化): 固定10%止损 + R:R=1.5止盈; "
        f"窗口=近{PRICE_WINDOW}日"
    )
    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": method_desc,
        "count": len(stocks),
        "stocks": stocks,
    }
    js_path = os.path.join(DATA_DIR, "STOCK_STOP_DATA.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.STOCK_STOP_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"✅ data/STOCK_STOP_DATA.js | 成功 {ok} / 跳过(港股等) {skip} / 失败 {fail} | {os.path.getsize(js_path)//1024} KB")
    return out


if __name__ == "__main__":
    main()
