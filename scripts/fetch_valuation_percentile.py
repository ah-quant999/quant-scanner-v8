#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_valuation_percentile.py — A股主要指数 PE-TTM 历史分位抓取

数据源：akshare stock_index_pe_lg（理杏仁）
覆盖指数：沪深300(000300)、中证500(000905)、中证1000(000852)
计算窗口：近5年/近3年/近1年滚动市盈率(TTM)分位数
输出：raw_data/valuation_percentile.json

2026-09-09 主人令：作为「估值分位切换」实验卡放入暂未上架页。
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw_data"
OUT_PATH = RAW_DIR / "valuation_percentile.json"

INDEX_CONFIG = [
    {"name": "沪深300", "code": "000300", "ak_symbol": "沪深300", "style": "大盘价值"},
    {"name": "中证500", "code": "000905", "ak_symbol": "中证500", "style": "中盘均衡"},
    {"name": "中证1000", "code": "000852", "ak_symbol": "中证1000", "style": "小盘成长"},
]


def now_cst():
    return datetime.now(CST)


def percentile_rank(series, value):
    """返回 value 在 series 中的分位（0~1），series 为列表。"""
    arr = sorted([float(x) for x in series if x is not None])
    if not arr:
        return None
    n = len(arr)
    below = sum(1 for x in arr if x < value)
    eq = sum(1 for x in arr if x == value)
    return (below + 0.5 * eq) / n


def bucket_label(p):
    if p is None:
        return "未知"
    if p < 0.30:
        return "低估"
    if p < 0.50:
        return "偏低"
    if p < 0.70:
        return "偏高"
    return "高估"


def fetch_one(symbol):
    import akshare as ak
    df = ak.stock_index_pe_lg(symbol=symbol)
    if df is None or df.empty:
        return None
    df = df.sort_values("日期")
    records = []
    for _, row in df.iterrows():
        d = str(row["日期"])
        pe = row.get("滚动市盈率")
        if pe is None:
            continue
        try:
            records.append({"date": d, "pe": float(pe)})
        except (ValueError, TypeError):
            continue
    return records


def compute_percentiles(records, as_of_date):
    """基于 as_of_date 往前推 1/3/5 年计算分位。"""
    if not records:
        return {}
    today = datetime.strptime(as_of_date, "%Y-%m-%d")
    cur = records[-1]["pe"]
    windows = {
        "1y": (today - timedelta(days=365), "percentile_1y"),
        "3y": (today - timedelta(days=3*365), "percentile_3y"),
        "5y": (today - timedelta(days=5*365), "percentile_5y"),
    }
    out = {"current_pe": cur, "date": as_of_date}
    for key, (cutoff, outkey) in windows.items():
        cutoff_s = cutoff.strftime("%Y-%m-%d")
        pe_series = [r["pe"] for r in records if r["date"] >= cutoff_s]
        out[outkey] = percentile_rank(pe_series, cur)
    return out


def overall_strategy(indices):
    """根据三个指数的分位给出顶层风格/仓位建议。"""
    # 取 5 年分位作为周期定位主指标
    buckets = [idx["bucket_5y"] for idx in indices if idx.get("percentile_5y") is not None]
    if not buckets:
        return {"overall": "未知", "suggestion": "数据不足", "defensive_ratio": 0.5}

    low_count = sum(1 for b in buckets if b in ("低估", "偏低"))
    high_count = sum(1 for b in buckets if b in ("高估", "偏高"))

    if low_count >= 2:
        overall = "低估区间"
        suggestion = "权益仓位偏积极；风格上小盘成长>中盘均衡>大盘价值"
        defensive_ratio = 0.2
    elif high_count >= 2:
        overall = "高估区间"
        suggestion = "降低权益仓位，增配红利/价值防御；规避高估值小盘"
        defensive_ratio = 0.6
    else:
        overall = "中估区间"
        suggestion = "均衡配置，按景气轮动；成长与价值保持动态平衡"
        defensive_ratio = 0.4

    return {"overall": overall, "suggestion": suggestion, "defensive_ratio": defensive_ratio}


def main():
    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        print("[error] akshare not installed", file=sys.stderr)
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []
    for cfg in INDEX_CONFIG:
        try:
            recs = fetch_one(cfg["ak_symbol"])
            if not recs:
                errors.append(f"{cfg['name']}: no data")
                continue
            as_of = recs[-1]["date"]
            stats = compute_percentiles(recs, as_of)
            item = {
                "name": cfg["name"],
                "code": cfg["code"],
                "style": cfg["style"],
                "current_pe": round(stats["current_pe"], 2),
                "date": stats["date"],
                "percentile_5y": round(stats.get("percentile_5y"), 4) if stats.get("percentile_5y") is not None else None,
                "percentile_3y": round(stats.get("percentile_3y"), 4) if stats.get("percentile_3y") is not None else None,
                "percentile_1y": round(stats.get("percentile_1y"), 4) if stats.get("percentile_1y") is not None else None,
            }
            item["bucket_5y"] = bucket_label(item["percentile_5y"])
            item["bucket_3y"] = bucket_label(item["percentile_3y"])
            item["bucket_1y"] = bucket_label(item["percentile_1y"])
            # 用 5 年分位给出单指数信号
            p5 = item["percentile_5y"]
            if p5 is None:
                item["signal"] = "数据不足"
            elif p5 < 0.30:
                item["signal"] = "加仓/超配"
            elif p5 < 0.50:
                item["signal"] = "标配"
            elif p5 < 0.70:
                item["signal"] = "谨慎"
            else:
                item["signal"] = "减仓/规避"
            results.append(item)
        except Exception as e:
            errors.append(f"{cfg['name']}: {e}")
            print(f"[warn] {cfg['name']} failed: {e}", file=sys.stderr)

    strategy = overall_strategy(results)

    payload = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare/stock_index_pe_lg",
        "indices": results,
        "strategy": strategy,
    }
    if errors:
        payload["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {OUT_PATH} ({len(results)} indices)", file=sys.stderr)


if __name__ == "__main__":
    main()
