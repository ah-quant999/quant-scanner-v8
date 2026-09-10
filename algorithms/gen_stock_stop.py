#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_stock_stop.py — v8 算法精确止损/止盈（方案三：全站统一 fixedP10/rrK1.5）

产出 data/STOCK_STOP_DATA.js（window.STOCK_STOP_DATA），为「今日可入手候选」卡片与
个股查询界面提供固定10%止损 + R:R=1.5止盈的统一口径。

候选宇宙：TRIPLE_CONSENSUS + FOUR_VOLUME + GOLD_POOL（COCKPIT_TIER_RECOMMEND 源已随 09-03 主人令「干掉驾驶舱」移除）
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

    # 2026-09-04 主人令收尾：COCKPIT_TIER_RECOMMEND(tier_a) 宇宙源已删（驾驶舱模块下线）

    fv = load_js("FOUR_VOLUME.js")
    if fv:
        for s in fv.get("stocks", []) or []:
            add(s)

    gp = load_js("GOLD_POOL.js")
    if gp:
        for k, s in (gp.get("stocks", {}) or {}).items():
            add(s)
        # 🔴 2026-09-11 一劳永逸（主人令「发现了就马上一劳永逸式修复」）：GOLD_POOL lite 化后
        #   stocks 已变空壳（total_count=0，_lite_note「仅保留 latest 聚合」）、真实成员在
        #   candidates（540 只，键形如 sh_600487，值含 code/market/board_label）。
        #   旧实现只读 stocks → 宇宙退化到 FOUR_VOLUME 残余 5 只 → 全部取数失败拒写盘。
        for s in (gp.get("candidates", {}) or {}).values():
            if isinstance(s, dict) and str(s.get("market", "")) in ("sh", "sz"):
                add(s)

    return codes


def main():
    print(f"=== gen_stock_stop (方案三统一 fixedP10/rrK1.5)  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    universe = collect_universe()
    print(f"候选宇宙去重: {len(universe)} 只")

    stocks = {}
    ok = skip = fail = 0
    # 🔴 2026-09-08 一劳永逸：原实现串行逐只 fetch_a_daily_gtimg（147~200 只，
    #   单只 timeout 20s×3 重试最坏 60s → 串行最坏 ~12000s），云端/夜间极易超时被杀。
    #   改为线程池并发（V8_STOP_WORKERS 可调，默认 8）。
    from concurrent.futures import ThreadPoolExecutor
    MAXW = int(os.environ.get("V8_STOP_WORKERS", "8"))

    def _one(item):
        code, meta = item
        try:
            gmkt = gtimg_market(code, meta["market"])
            if not gmkt:
                return code, None, "skip"
            digits = re.sub(r"\D", "", str(code))
            df = fetch_a_daily_gtimg(digits, gmkt, bars=250)
            stats = compute_stop_target(df, board=meta.get("board", "主板"), strategy="general")
            if not stats:
                return code, None, "nostats"
            stats["market"] = gmkt
            return code, stats, "ok"
        except Exception as e:  # noqa: BLE001
            return code, None, f"err:{e}"

    with ThreadPoolExecutor(max_workers=MAXW) as ex:
        for code, stats, st in ex.map(_one, universe.items()):
            if st == "ok":
                stocks[str(code)] = stats
                ok += 1
            elif st == "skip":
                skip += 1
            else:
                fail += 1

    method_desc = (
        "全站统一口径(方案三优化): 固定10%止损 + R:R=1.5止盈; "
        f"窗口=近{PRICE_WINDOW}日"
    )
    # 🔴 2026-09-08 一劳永逸「禁止假绿灯」：原实现无论 ok 多少都无条件写盘并刷新
    #   update_time → 取数全挂时产出「空数据 + 新时间戳」，健康面板判为新鲜、前端空白，
    #   与 H_AUTO_BUY 断更 3 天无人发现属同一类静默失败。现：成功 0 只即拒绝写盘，
    #   保留上一版数据并让调用方看到失败。
    if ok == 0:
        print(f"❌ 取数全部失败（成功 0 / 跳过 {skip} / 失败 {fail}），"
              f"拒绝写盘：不产出空 STOCK_STOP_DATA 污染前端（保留上一版）")
        return None
    degraded = fail > 0 or ok < len(universe) * 0.5
    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": method_desc,
        "count": len(stocks),
        "total_universe": len(universe),
        "degraded": degraded,
        "stocks": stocks,
    }
    js_path = os.path.join(DATA_DIR, "STOCK_STOP_DATA.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.STOCK_STOP_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"✅ data/STOCK_STOP_DATA.js | 成功 {ok} / 跳过(港股等) {skip} / 失败 {fail} | {os.path.getsize(js_path)//1024} KB")
    return out


if __name__ == "__main__":
    main()
