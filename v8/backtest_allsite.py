#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_allsite.py — 全站精选历史回测占位生成器

背景：
  全站精选为最终推荐聚合模块（raw_data/final_recommend.json），
  但当前尚未建立历史归档（缺少 final_recommend_YYYYMMDD.json 序列）。

本脚本：
  1. 读取当日 final_recommend.json，仅作信号数量统计。
  2. 输出 data/ALLSITE_BACKTEST.js（与 HUNTER_BACKTEST 同构）。
  3. 当未来建立历史归档后，可在此脚本中补充真实收益计算。

注意：
  - 当前为 0 信号/空回测结构，前端会显示「暂无历史信号」。
  - 不阻塞 CI：baostock 等依赖仅在真实回测分支中使用。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
OUT_JS = DATA_DIR / "ALLSITE_BACKTEST.js"
OUT_JSON = RAW_DIR / "allsite_backtest.json"
HOLD_PERIODS = [1, 3, 5, 10, 20]


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_signals = 0
    try:
        fr = json.loads((RAW_DIR / "final_recommend.json").read_text(encoding="utf-8"))
        today_signals = len(fr.get("stocks") or [])
    except Exception as e:
        print(f"[allsite backtest] final_recommend.json not available: {e}")

    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": 0,
            "calc_time": now,
            "method": f"全站精选历史回测占位（当前 final_recommend 当日信号 {today_signals} 只，但无历史归档；待建立 final_recommend_YYYYMMDD.json 历史序列后升级为真实回测）",
            "signal_date_range": "—",
            "by_period": {
                str(p): {
                    "samples": 0,
                    "win_rate": 0,
                    "avg_return": 0,
                    "best_return": 0,
                    "worst_return": 0,
                    "win_avg": 0,
                    "loss_avg": 0,
                    "profit_loss_ratio": 0,
                }
                for p in HOLD_PERIODS
            },
        },
        "signals": [],
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text("window.ALLSITE_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[allsite backtest] placeholder written (today_signals={today_signals}, history=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
