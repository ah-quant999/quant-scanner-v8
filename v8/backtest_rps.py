#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_rps.py — 相对强度 RPS 历史回测占位生成器

背景：
  RPS 为当日截面计算模块（raw_data/stock_rps.json），
  但当前尚未建立历史归档（缺少 stock_rps_YYYYMMDD.json 序列）。

本脚本：
  1. 读取当日 stock_rps.json，仅作 universe/A 档数量统计。
  2. 输出 data/RPS_BACKTEST.js（与 HUNTER_BACKTEST 同构）。
  3. 当未来建立历史归档后，可在此脚本中补充真实收益计算。

注意：
  - 当前为 0 信号/空回测结构，前端会显示「暂无历史信号」。
  - 不阻塞 CI：mootdx/baostock 等依赖仅在真实回测分支中使用。
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
OUT_JS = DATA_DIR / "RPS_BACKTEST.js"
OUT_JSON = RAW_DIR / "rps_backtest.json"
HOLD_PERIODS = [1, 3, 5, 10, 20]


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid_count = 0
    tier_a_count = 0
    try:
        rps = json.loads((RAW_DIR / "stock_rps.json").read_text(encoding="utf-8"))
        records = rps.get("records") or []
        valid_count = rps.get("valid_count") or len(records)
        tier_a_count = len([r for r in records if (r.get("tier") or "").upper() == "A"])
    except Exception as e:
        print(f"[rps backtest] stock_rps.json not available: {e}")

    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": 0,
            "calc_time": now,
            "method": f"RPS 相对强度历史回测占位（当前 valid={valid_count}，A档={tier_a_count}；待建立 stock_rps_YYYYMMDD.json 历史序列后升级为真实回测）",
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
    OUT_JS.write_text("window.RPS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[rps backtest] placeholder written (valid={valid_count}, tier_a={tier_a_count}, history=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
