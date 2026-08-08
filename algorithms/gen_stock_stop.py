#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_stock_stop.py — v8 算法精确止损/止盈（ATR 法）

产出 data/STOCK_STOP_DATA.js（window.STOCK_STOP_DATA），为「今日可入手候选」卡片与
个股查询界面提供基于真实波动率的止损/止盈，取代固定百分比参考值。

算法（非未来函数，仅用截至当日的日K）：
  - 经 data_source_gtimg.fetch_a_daily_gtimg 取前复权日K（腾讯，HTTP，云端/本机均可达）。
  - ATR(14) = 真实波幅 TR 的 14 日均值；TR = max(H-L, |H-前收|, |L-前收|)。
  - 止损 stop_loss = close - 2*ATR（风险预算约 2 日波幅）。
  - 目标 target   = close + 3*ATR（盈亏比 1.5:1，满足「三不原则·盈亏比<1.5不介入」）。
  - 支撑 support  = 近 20 日最低价；压力 resistance = 近 20 日最高价（展示用）。
  - 港股/北交所 gtimg 日K不稳，跳过（前端回退固定百分比参考）。

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

ATR_WINDOW = 14
STOP_MULT = 2.0
TARGET_MULT = 3.0
SUPPORT_RESIST_WINDOW = 20


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
    codes = {}  # code -> market_str

    def add(code, market):
        if code:
            codes[str(code)] = market

    tc = load_js("TRIPLE_CONSENSUS.js")
    if tc:
        for s in tc.get("stocks", []) or []:
            add(s.get("code"), s.get("market"))

    cr = load_js("COCKPIT_TIER_RECOMMEND.js")
    if cr:
        for s in cr.get("tier_a", []) or []:
            add(s.get("code"), s.get("market"))

    fv = load_js("FOUR_VOLUME.js")
    if fv:
        for s in fv.get("stocks", []) or []:
            add(s.get("code"), s.get("market"))

    gp = load_js("GOLD_POOL.js")
    if gp:
        for k, s in (gp.get("stocks", {}) or {}).items():
            add(s.get("code"), s.get("market"))

    return codes


def compute_kline_stats(df):
    if df is None or len(df) < ATR_WINDOW + 1:
        return None
    close = float(df["close"].iloc[-1])
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = df["close"].astype(float).shift(1)
    tr = (
        (high - low)
        .combine(((high - prev_close).abs()), max)
        .combine(((low - prev_close).abs()), max)
    )
    atr = float(tr.tail(ATR_WINDOW).mean())
    if atr <= 0 or close <= 0:
        return None
    stop = close - STOP_MULT * atr
    target = close + TARGET_MULT * atr
    # 兜底：止损不得非正或高于收盘
    stop = max(stop, close * 0.5)
    if stop >= close:
        stop = close * 0.93
    support = float(low.tail(SUPPORT_RESIST_WINDOW).min())
    resistance = float(high.tail(SUPPORT_RESIST_WINDOW).max())
    return {
        "atr": round(atr, 3),
        "close": round(close, 2),
        "stop_loss": round(stop, 2),
        "target_price": round(target, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }


def main():
    print(f"=== gen_stock_stop (ATR 精确止损止盈)  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    universe = collect_universe()
    print(f"候选宇宙去重: {len(universe)} 只")

    stocks = {}
    ok = skip = fail = 0
    for code, market_str in universe.items():
        gmkt = gtimg_market(code, market_str)
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
        stats = compute_kline_stats(df)
        if not stats:
            fail += 1
            continue
        stats["market"] = gmkt
        stocks[str(code)] = stats
        ok += 1

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": f"ATR({ATR_WINDOW}): 止损=收盘-{STOP_MULT:.0f}ATR, 目标=收盘+{TARGET_MULT:.0f}ATR (盈亏比1.5:1); 支撑/压力=近{SUPPORT_RESIST_WINDOW}日高低",
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
