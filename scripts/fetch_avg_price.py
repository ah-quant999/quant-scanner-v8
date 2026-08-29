#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_avg_price.py — 平均股价（通达信 880003）轻量 fetcher

数据源：东方财富 push2his / akshare stock_zh_a_hist（指数 = 880003）
频度：盘后 1 次（日级）
产出：raw_data/avg_price.json + data/AVG_PRICE.js（window.AVG_PRICE）

数据形态（最近 5 日 + 最新值）：
  {
    "update_time": "2026-08-29 18:35:00",
    "current": 11.32,
    "history": [{"date":"2026-08-25","avg":11.20}, ...],
    "meta": {"指标":"沪深两市A股平均股价","source":"东财push2his"}
  }

落地：
  本机/云端 premarket 跑，UI 暂不直接挂卡（主人评估后再接驾驶舱/暂未上架页）。
"""
import os, json, sys, time
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

# 880003 在东方财富 push2his 的 secid（88=通达信风格指数，0003=编号）
SEC_ID = "88.0003"
URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

def http_get(url, params=None, timeout=15):
    try:
        import requests
        r = requests.get(url, params=params, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[warn] http_get failed: {e}", file=sys.stderr)
        return None

def main():
    today = datetime.now(CST).strftime("%Y-%m-%d")
    params = {
        "secid": SEC_ID,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",   # 日 K
        "fqt": "1",
        "beg": "0",
        "end": "20500101",
        "lmt": "120"
    }
    data = http_get(URL, params=params)
    if not data or not data.get("data"):
        print("[warn] avg_price fetch failed, exit 1 (云端可重试)", file=sys.stderr)
        return 1

    # parse klines: "date,open,close,high,low,vol,amount,..."
    klines = (data["data"].get("klines") or [])
    history = []
    for ln in klines:
        parts = ln.split(",")
        if len(parts) >= 5:
            history.append({"date": parts[0], "avg": float(parts[2])})
    if not history:
        return 2

    # 最近 5 日
    recent5 = history[-5:]
    result = {
        "current_date": history[-1]["date"],
        "current": history[-1]["avg"],
        "yesterday": history[-2]["avg"] if len(history) > 1 else None,
        "change_pct": round((history[-1]["avg"] / (history[-2]["avg"] or history[-1]["avg"]) - 1) * 100, 2) if len(history) > 1 else 0,
        "history_5d": recent5,
        "meta": {"指标": "沪深两市A股平均股价", "secid": SEC_ID, "source": "东方财富push2his"},
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    }

    out_raw = os.path.join(RAW_DIR, "avg_price.json")
    os.makedirs(RAW_DIR, exist_ok=True)
    open(out_raw, "w", encoding="utf-8").write(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[ok] {out_raw} current={result['current']} ({result['current_date']})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
