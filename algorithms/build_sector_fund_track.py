#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_sector_fund_track.py
2026-09-01 主人令：为「暂未上架」原生卡「热门赛道资金追踪」生成数据。
数据源：raw_data/sector_fund_flow_history.json（各板块/概念每日净流入历史）。
输出：raw_data/sector_fund_track.json（update_v8 映射为 data/SECTOR_FUND_TRACK.js）。
逻辑：取 lookback_days（默认 20）累计净流入 top10 赛道，输出每日累计净流入序列，供前端折线图+紧凑矩阵。
"""
import json
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_IN = os.path.join(ROOT, "raw_data", "sector_fund_flow_history.json")
RAW_OUT = os.path.join(ROOT, "raw_data", "sector_fund_track.json")
LOOKBACK_DAYS = 20
TOP_N = 10

# 10 条一眼区分的折线色（非涨跌语义，仅用于区分赛道；红涨绿跌在数字/表头中体现）
PALETTE = [
    "#ef5350", "#42a5f5", "#26a69a", "#ab47bc", "#ffa726",
    "#7e57c2", "#ec407a", "#26c6da", "#8d6e63", "#78909c",
]


def load_history(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {path}: {e}")
        return {}


def main():
    hist = load_history(RAW_IN)
    if not hist:
        print("[ sector_fund_track ] 输入为空，跳过")
        return

    today = datetime.now().astimezone().replace(tzinfo=None)
    cutoff = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    # 对每个赛道，保留 lookback 窗口内的 {date: net}，并计算累计净流入
    sector_stats = []
    all_dates_set = set()
    for name, rows in hist.items():
        if not isinstance(rows, list):
            continue
        # 过滤并去重：同一天取最后一个 net
        daily = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            d = r.get("date")
            if not d or d < cutoff:
                continue
            try:
                daily[d] = float(r.get("net", 0))
            except Exception:
                daily[d] = 0.0
        if not daily:
            continue
        total = sum(daily.values())
        all_dates_set.update(daily.keys())
        sector_stats.append({
            "name": name,
            "daily": daily,
            "total": total,
            "days": len(daily),
        })

    if not sector_stats:
        print("[ sector_fund_track ] 无有效窗口数据，跳过")
        return

    # 取累计净流入 top10（降序）
    sector_stats.sort(key=lambda x: x["total"], reverse=True)
    top = sector_stats[:TOP_N]

    # 统一日期轴：窗口内所有出现过的日期排序
    dates = sorted(all_dates_set)
    # 进一步截断到最近 LOOKBACK_DAYS 个自然日（保证图表 x 轴连续）
    dates = dates[-LOOKBACK_DAYS:]

    # 为每个 top 赛道补齐序列，缺失日 net=0，再算累计
    top_10 = []
    for i, s in enumerate(top):
        cum = 0.0
        series_net = []
        series_cum = []
        for d in dates:
            net = s["daily"].get(d, 0.0)
            cum += net
            series_net.append(round(net, 2))
            series_cum.append(round(cum, 2))
        top_10.append({
            "rank": i + 1,
            "name": s["name"],
            "total": round(s["total"], 2),
            "days": s["days"],
            "color": PALETTE[i % len(PALETTE)],
            "series_net": series_net,
            "series_cum": series_cum,
        })

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    summary = "、".join([
        f"{x['name']}{x['total']:+.1f}亿" for x in top_10[:5]
    ]) if top_10 else "暂无数据"

    out = {
        "update_time": update_time,
        "lookback_days": LOOKBACK_DAYS,
        "dates": dates,
        "top_10": top_10,
        "summary": summary,
    }

    os.makedirs(os.path.dirname(RAW_OUT), exist_ok=True)
    with open(RAW_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[ sector_fund_track ] 已生成 {RAW_OUT}: top10 赛道 / {len(dates)} 天 / update={update_time}")


if __name__ == "__main__":
    main()
