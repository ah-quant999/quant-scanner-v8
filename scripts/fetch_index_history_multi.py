#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多基准指数长历史 K 线 fetcher
拉取上证指数 / 中证1000 / 国证A指 近 N 年日 K 线，
供 alpha_vs_beta.py 做多基准超额检验（判断 +6% 是 alpha 还是风格 beta）。
输出：raw_data/index_history_multi.json（不破坏原 index_history.json 格式）。
"""
import akshare as ak
import json
import os
import datetime
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw_data", "index_history_multi.json")
YEARS = 5

INDICES = [
    {"symbol": "sh000001", "name": "上证指数", "code": "000001.SH"},
    {"symbol": "sh000852", "name": "中证1000", "code": "000852.SH"},
    {"symbol": "sz399317", "name": "国证A指", "code": "399317.SZ"},
]


def log(msg):
    print(f"  [fetch_index_history_multi] {msg}", flush=True)


def fetch_one(symbol, name, years=YEARS):
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=365 * years + 30)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
    except Exception as e:
        log(f"{name}({symbol}) 拉取失败: {e}")
        return None
    rows = []
    for _, r in df.iterrows():
        try:
            d = str(r["date"])[:10]
            if d < start or d > end:
                continue
            rows.append({
                "d": d,
                "o": round(float(r["open"]), 2),
                "h": round(float(r["high"]), 2),
                "l": round(float(r["low"]), 2),
                "c": round(float(r["close"]), 2),
                "v": int(float(r["volume"])) if r["volume"] == r["volume"] else 0,
            })
        except Exception:
            continue
    rows.sort(key=lambda x: x["d"])
    if not rows:
        return None
    log(f"{name}({symbol}): {len(rows)} 条 {rows[0]['d']} ~ {rows[-1]['d']}")
    return rows


def main(years=YEARS):
    log("拉取多基准指数长历史 K 线")
    payload = {
        "meta": {
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "years": years,
            "indices": [{k: v for k, v in idx.items() if k != "symbol"} for idx in INDICES],
        },
        "data": {},
    }
    for idx in INDICES:
        rows = fetch_one(idx["symbol"], idx["name"], years)
        if rows:
            payload["data"][idx["code"]] = {
                "meta": {"symbol": idx["symbol"], "name": idx["name"], "code": idx["code"], "count": len(rows)},
                "klines": rows,
            }
    if not payload["data"]:
        log("所有基准均失败")
        return 1
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    with open(RAW, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已写入 {RAW}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(BASE, "algorithms"))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("scripts/fetch_index_history_multi.py"):
        sys.exit(2)
    years = int(sys.argv[1]) if len(sys.argv) > 1 else YEARS
    sys.exit(main(years))
