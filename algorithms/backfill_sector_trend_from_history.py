#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性回填 SECTOR_FUND_FLOW_TREND 的 5/10/20/60 日累计。

用途：v8 history 文件只有最近 2 天，但 v6 历史种子还有 7-06 ~ 8-03。
合并 history 后，重新基于 history 计算各周期累计，不改动当日 top_list
（当日 net / sectors_in/out 保持原样），避免家里机无 akshare 时引入偏差。

输出：raw_data/sector_fund_flow_trend.json
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREND_FILE = os.path.join(ROOT, "raw_data", "sector_fund_flow_trend.json")
HIST_FILE = os.path.join(ROOT, "raw_data", "sector_fund_flow_history.json")


def _real_n(hist, n):
    arr = [h for h in hist[-n:] if not h.get("carried")]
    return arr, round(sum(h["net"] for h in arr), 2)


def calc_consecutive(records):
    if not records:
        return 0, "neutral"
    days = 0
    trend = None
    for record in reversed(records):
        net = record["net"]
        if trend is None:
            if net > 0:
                trend = "in"
            elif net < 0:
                trend = "out"
            else:
                return 0, "neutral"
            days = 1
        else:
            if trend == "in" and net > 0:
                days += 1
            elif trend == "out" and net < 0:
                days += 1
            else:
                break
    return days, trend


def main():
    if not os.path.exists(TREND_FILE):
        print(f"❌ {TREND_FILE} 不存在，无法回填")
        return
    if not os.path.exists(HIST_FILE):
        print(f"❌ {HIST_FILE} 不存在，无法回填")
        return

    with open(TREND_FILE, "r", encoding="utf-8") as f:
        trend = json.load(f)
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")

    # candidate_map：以现有 top_list 为主，补充 history-only 板块
    candidate_map = {}
    for item in trend.get("top_list", []):
        candidate_map[item["name"]] = dict(item)

    for name, hist in history.items():
        if name in candidate_map:
            continue
        if len(hist) < 5:
            continue
        candidate_map[name] = {
            "name": name,
            "net": hist[-1]["net"] if hist else 0,
            "net_5d": 0, "net_20d": 0, "net_60d": None,
            "type": "行业" if "概念" not in name else "概念",
            "consecutive_days": 0, "trend": "neutral",
        }
        days, tr = calc_consecutive(hist)
        candidate_map[name]["consecutive_days"] = days
        candidate_map[name]["trend"] = tr

    # 基于 history 重新计算各周期累计
    for item in candidate_map.values():
        name = item["name"]
        hist = history.get(name, [])

        real_5, net_5d_val = _real_n(hist, 5)
        real_10, net_10d_val = _real_n(hist, 10)
        real_20, net_20d_val = _real_n(hist, 20)
        real_60, net_60d_val = _real_n(hist, 60)

        if net_5d_val != 0 and len(real_5) >= 5:
            item["net_5d"] = net_5d_val
        if net_10d_val != 0 and len(real_10) >= 10:
            item["net_10d"] = net_10d_val
        if net_20d_val != 0 and len(real_20) >= 20:  # 2026-08-12 修：原写>=10，20日趋势需至少20天真实数据
            item["net_20d"] = net_20d_val
        if len(real_60) >= 60:
            item["net_60d"] = net_60d_val
        else:
            item["net_60d"] = None

    candidate_list = list(candidate_map.values())

    trend_5d = sorted([x for x in candidate_list if x.get("net_5d") is not None and x["net_5d"] != 0],
                      key=lambda x: x.get("net_5d", 0), reverse=True)[:12]
    trend_10d = sorted([x for x in candidate_list if x.get("net_10d") is not None and x["net_10d"] != 0],
                       key=lambda x: x.get("net_10d", 0), reverse=True)[:12]
    trend_20d = sorted([x for x in candidate_list if x.get("net_20d") is not None and x["net_20d"] != 0],
                       key=lambda x: x.get("net_20d", 0), reverse=True)[:12]
    trend_60d = sorted([x for x in candidate_list if x.get("net_60d") is not None and x["net_60d"] != 0],
                       key=lambda x: x.get("net_60d", 0), reverse=True)[:12]

    trend["trend_5d"] = trend_5d
    trend["trend_10d"] = trend_10d
    trend["trend_20d"] = trend_20d
    trend["trend_60d"] = trend_60d
    trend["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    trend["data_note"] = "基于合并后的 history 回填 5/10/20/60 日累计（家里机无 akshare）"

    os.makedirs(os.path.dirname(TREND_FILE), exist_ok=True)
    with open(TREND_FILE, "w", encoding="utf-8") as f:
        json.dump(trend, f, ensure_ascii=False, indent=2)

    print(f"✅ 已回填: {TREND_FILE}")
    print(f"   trend_5d: {len(trend_5d)} 条")
    print(f"   trend_10d: {len(trend_10d)} 条")
    print(f"   trend_20d: {len(trend_20d)} 条")
    print(f"   trend_60d: {len(trend_60d)} 条")


if __name__ == "__main__":
    main()
