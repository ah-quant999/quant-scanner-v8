#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成龙虎榜 7 日累计数据（机游共振 + 北向席位）。
输入：raw_data/lhb_history.json（历史） + raw_data/lhb_data.json（当日）
输出：raw_data/lhb_7d.json  +  data/LHB_7D.js

口径：
- 取最近 7 个有数据的交易日（含当日）。
- 每只股票在 7 日内按 code 去重汇总：机构买/卖/净额、游资买/卖/净额、北向席位买/卖/净额。
- 输出 7 日累计 TOP5：机构净买/净卖、游资净买/净卖、机游共振（机构+游资净买合计）、北向席位净买/净卖。
- 同时输出每日摘要（上榜股数 / 机游共振数 / 机构独买 / 游资独买 / 北向参与股数），用于趋势。
"""
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")

HISTORY_PATH = os.path.join(RAW_DIR, "lhb_history.json")
TODAY_PATH = os.path.join(RAW_DIR, "lhb_data.json")
OUT_JSON_PATH = os.path.join(RAW_DIR, "lhb_7d.json")
OUT_JS_PATH = os.path.join(DATA_DIR, "LHB_7D.js")


def log(msg):
    print(f"  [LHB-7D] {msg}", flush=True)


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_date_key(k):
    return isinstance(k, str) and len(k) == 10 and k[4] == "-" and k[7] == "-"


def aggregate_stock(days_data):
    """把多日的股票列表按 code 聚合。"""
    agg = defaultdict(lambda: {
        "code": "",
        "name": "",
        "inst_buy": 0.0, "inst_sell": 0.0, "inst_net": 0.0,
        "yz_buy": 0.0, "yz_sell": 0.0, "yz_net": 0.0,
        "north_buy": 0.0, "north_sell": 0.0, "north_net": 0.0,
        "combined_net": 0.0,
        "days": 0,
        "resonance_days": 0,
        "last_category": "",
    })
    for date_str, day in days_data.items():
        stocks = day.get("stocks") or []
        for s in stocks:
            code = s.get("code")
            if not code:
                continue
            a = agg[code]
            a["code"] = code
            a["name"] = s.get("name") or a["name"]
            a["inst_buy"] += float(s.get("inst_buy_万", 0) or 0)
            a["inst_sell"] += float(s.get("inst_sell_万", 0) or 0)
            a["inst_net"] += float(s.get("inst_net_万", 0) or 0)
            a["yz_buy"] += float(s.get("yz_buy_万", 0) or 0)
            a["yz_sell"] += float(s.get("yz_sell_万", 0) or 0)
            a["yz_net"] += float(s.get("yz_net_万", 0) or 0)
            seats = s.get("seats") or {}
            nb = seats.get("北向", {})
            nb_buy = float(nb.get("buy", 0) or 0)
            nb_sell = float(nb.get("sell", 0) or 0)
            a["north_buy"] += nb_buy
            a["north_sell"] += nb_sell
            a["north_net"] += nb_buy - nb_sell
            a["combined_net"] = a["inst_net"] + a["yz_net"]
            a["days"] += 1
            if s.get("category") == "机游共振":
                a["resonance_days"] += 1
            a["last_category"] = s.get("category") or a["last_category"]
    return {k: dict(v) for k, v in agg.items()}


def topn(stocks, key, n=5, asc=False):
    """按 key 排序取前 n，asc=False 取最大，asc=True 取最小（负值）。"""
    filtered = [s for s in stocks if s.get(key) is not None and (asc if s[key] < 0 else not asc)]
    filtered.sort(key=lambda x: x[key], reverse=not asc)
    return filtered[:n]


def fmt_stock_light(s):
    """输出轻量股票对象给前端。"""
    return {
        "code": s["code"],
        "name": s["name"],
        "inst_net": round(s["inst_net"], 2),
        "yz_net": round(s["yz_net"], 2),
        "north_net": round(s["north_net"], 2),
        "combined_net": round(s["inst_net"] + s["yz_net"], 2),
        "days": s["days"],
        "resonance_days": s["resonance_days"],
    }


def main():
    log("开始生成 7 日龙虎榜累计数据")
    history = load_json(HISTORY_PATH) or {}
    today = load_json(TODAY_PATH)

    # 过滤历史中的真实日期键
    date_data = {}
    for k, v in history.items():
        if is_date_key(k) and isinstance(v, dict) and v.get("trading") and v.get("stocks"):
            date_data[k] = v

    # 用当日数据覆盖/补充
    if today and today.get("stocks"):
        # lhb_data.json 的 date 是 20260807 格式，转成 2026-08-07
        d = today.get("date", "")
        if len(d) == 8:
            iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        else:
            iso = datetime.now().strftime("%Y-%m-%d")
        date_data[iso] = today
        log(f"当日数据 {iso} 覆盖/补充，stocks={len(today['stocks'])}")
    else:
        log("warn: 当日 lhb_data.json 无 stocks")

    if not date_data:
        log("error: 无任何有效日期数据")
        sys.exit(1)

    sorted_dates = sorted(date_data.keys())
    last7 = sorted_dates[-7:]
    log(f"7 日窗口：{last7[0]} ~ {last7[-1]}，共 {len(last7)} 天")

    days7 = {d: date_data[d] for d in last7}

    # 每日摘要
    daily_summary = []
    for d in last7:
        day = date_data[d]
        summary = day.get("summary") or {}
        stocks = day.get("stocks") or []
        north_cnt = sum(1 for s in stocks if (s.get("seats") or {}).get("北向"))
        daily_summary.append({
            "date": d,
            "total": int(summary.get("总计", len(stocks))),
            "resonance": int(summary.get("机游共振", 0)),
            "inst_only": int(summary.get("机构独买", 0)),
            "yz_only": int(summary.get("游资独买", 0)),
            "north_present": north_cnt,
        })

    # 聚合
    agg = aggregate_stock(days7)
    agg_list = list(agg.values())
    log(f"7 日累计去重股票：{len(agg_list)}")

    # 各类 TOP5
    top_inst_buy = [fmt_stock_light(s) for s in topn(agg_list, "inst_net", 5, False)]
    top_inst_sell = [fmt_stock_light(s) for s in topn(agg_list, "inst_net", 5, True)]
    top_yz_buy = [fmt_stock_light(s) for s in topn(agg_list, "yz_net", 5, False)]
    top_yz_sell = [fmt_stock_light(s) for s in topn(agg_list, "yz_net", 5, True)]
    # 机游共振：仅统计机构+游资都为正的股票，按合计净额排序
    resonance_candidates = [s for s in agg_list if s["inst_net"] > 0 and s["yz_net"] > 0]
    top_resonance = [fmt_stock_light(s) for s in topn(resonance_candidates, "combined_net", 5, False)]
    top_north_buy = [fmt_stock_light(s) for s in topn(agg_list, "north_net", 5, False)]
    top_north_sell = [fmt_stock_light(s) for s in topn(agg_list, "north_net", 5, True)]

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "range": [last7[0], last7[-1]],
        "days_count": len(last7),
        "daily_summary": daily_summary,
        "top_inst_buy": top_inst_buy,
        "top_inst_sell": top_inst_sell,
        "top_yz_buy": top_yz_buy,
        "top_yz_sell": top_yz_sell,
        "top_resonance": top_resonance,
        "top_north_buy": top_north_buy,
        "top_north_sell": top_north_sell,
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"已写 {OUT_JSON_PATH}")

    with open(OUT_JS_PATH, "w", encoding="utf-8") as f:
        f.write("window.LHB_7D = ")
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    log(f"已写 {OUT_JS_PATH}")


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/gen_lhb_7d.py"):
        sys.exit(2)
    main()
