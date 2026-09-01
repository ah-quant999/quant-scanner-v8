#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""长历史 K 线 fetcher：拉上证指数近 N 年日 K 线 → out/index_history.json
- 数据源：akshare.stock_zh_index_daily（新浪接口，2005-至今）
- 用途：路径概率预测卡（波浪/江恩/缠论/形态匹配需要 5+ 年长历史）
- 输出：out/index_history.json + bridge 到 raw_data/index_history.json
- 主人授权：2026-08-19 「做 v8 卡片版 + 5 年长 K 线」
"""
import akshare as ak
import json
import os
import datetime
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out", "index_history.json")
RAW = os.path.join(BASE, "raw_data", "index_history.json")
YEARS = 5  # 默认 5 年，按主人拍板

def log(msg):
    print(f"  [fetch_index_history] {msg}", flush=True)

def main(years=YEARS):
    log(f"拉上证指数近 {years} 年日 K 线（akshare.stock_zh_index_daily）")
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=365 * years + 30)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
    except Exception as e:
        log(f"akshare 拉取失败: {e}")
        return 1
    # df 列: date, open, high, low, close, volume
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
    log(f"拿到 {len(rows)} 条记录，时间跨度 {rows[0]['d']} ~ {rows[-1]['d']}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {
        "meta": {
            "symbol": "sh000001",
            "name": "上证指数",
            "years": years,
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "count": len(rows),
        },
        "klines": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已写入 {OUT}")
    # 🛡 2026-08-20 一劳永逸：bridge 到 raw_data/（update_v8 只读 raw_data/ 生成
    #   data/INDEX_HISTORY.js；之前无调度方 + 无 bridge → 主站永远用旧 K 线）。
    #   与 docstring 声明保持一致（原注释声称有 bridge，实际缺失，补上）。
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    with open(RAW, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已 bridge → raw_data/index_history.json")
    return 0

if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.join(BASE, "algorithms"))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("scripts/fetch_index_history.py"):
        sys.exit(2)
    years = int(sys.argv[1]) if len(sys.argv) > 1 else YEARS
    sys.exit(main(years))