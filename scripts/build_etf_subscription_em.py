#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_etf_subscription_em.py — raw_data/etf_subscription_em.json → data/ETF_SUBSCRIPTION_EM.js
                                                                 (2026-08-30 阿狸咪)

输入：  raw_data/etf_subscription_em.json（fetch_etf_subscription_em.py 产出，5 类聚合占位/真数据）
输出：  data/ETF_SUBSCRIPTION_EM.js（window.ETF_SUBSCRIPTION_EM）

东方财富口径（替代旧宽基指数 + 亿份）：
  5 类：股票型 / 债券型 / 货币型 / 商品型 / 跨境型
  单位：亿元（净申购赎回金额）
  字段：categories[c].{name, net_amount_yi, n_funds, top5[]}
"""
import os, json, sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
# ROOT 必须显式传入仓库根（如：C:/path/to/stock-scanner 或调用方 cwd=仓库根时可省）
import sys as _sys
if len(_sys.argv) > 1 and os.path.isdir(_sys.argv[1]):
    ROOT = os.path.abspath(_sys.argv[1])
else:
    # 默认：调用方 cwd 视为仓库根
    ROOT = os.path.abspath(os.getcwd())
RAW_PATH = os.path.join(ROOT, "raw_data", "etf_subscription_em.json")
OUT_PATH = os.path.join(ROOT, "data", "ETF_SUBSCRIPTION_EM.js")

JS_TMPL = """window.ETF_SUBSCRIPTION_EM = {payload};
"""

def main():
    if not os.path.exists(RAW_PATH):
        print(f"[warn] {RAW_PATH} missing, write placeholder", file=sys.stderr)
        placeholder = {
            "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "akshare etf_em (东财)",
            "categories": {
                "stock":       {"name": "股票型",   "net_amount_yi": 0.0, "n_funds": 0, "top5": []},
                "bond":        {"name": "债券型",   "net_amount_yi": 0.0, "n_funds": 0, "top5": []},
                "money":       {"name": "货币型",   "net_amount_yi": 0.0, "n_funds": 0, "top5": []},
                "commodity":   {"name": "商品型",   "net_amount_yi": 0.0, "n_funds": 0, "top5": []},
                "cross_border":{"name": "跨境型",   "net_amount_yi": 0.0, "n_funds": 0, "top5": []},
            }
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.write(JS_TMPL.format(payload=json.dumps(placeholder, ensure_ascii=False, indent=2)))
        return 2

    with open(RAW_PATH, encoding="utf-8") as f:
        data = json.load(f)

    payload = {
        "update_time": data.get("update_time") or datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare etf_em (东财)",
        "categories": data.get("categories", {})
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(JS_TMPL.format(payload=json.dumps(payload, ensure_ascii=False, indent=2)))
    print(f"[ok] {OUT_PATH} (5类已聚合)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
