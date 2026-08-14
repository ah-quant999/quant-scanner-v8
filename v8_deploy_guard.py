#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 部署前产物校验（防空 raw_data 把 good data 覆盖成 shell 致整站空）

规则：
- 关键 data/*.js 必须存在且字节数 >= 阈值（阈值远小于正常体积，只拦 shell/空文件）。
- 首行必须是 `window.<NAME> =` 形式（非报错页/空文件）。
- 任一不达标 -> exit 1，CI 据此阻断部署，保留上一次 good data。
依赖：仅标准库
"""
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

MIN_SIZE = {
    "FINAL_RECOMMEND_DATA.js": 8000,
    "CANDIDATE.js": 60000,
    "STOCK_RPS.js": 60000,
    "SECTOR_FUND_FLOW.js": 8000,
    "TOP10_DAILY.js": 4000,
    "STOCK_QUOTE.js": 100000,
    "CANDIDATE_QUOTES.js": 8000,
    "GOLD_POOL.js": 8000,
    "LHB_DATA.js": 8000,
    "COCKPIT_BACKTEST.js": 40000,
}

bad = []
for name, mn in MIN_SIZE.items():
    p = DATA / name
    if not p.exists():
        bad.append((name, 0, mn, "缺失")); continue
    sz = p.stat().st_size
    if sz < mn:
        bad.append((name, sz, mn, "过小(疑似shell)")); continue
    head = p.read_text(encoding="utf-8", errors="ignore")[:60]
    if not head.lstrip().startswith("window."):
        bad.append((name, sz, mn, "首行非 window. 赋值(格式异常)"))

if bad:
    print("X 部署前校验失败，疑似空/陈旧 raw_data 生成 shell，阻断部署：".replace("X","❌"))
    for name, sz, mn, why in bad:
        print(f"   {name}: {sz}B ({why}, 阈值 {mn}B)")
    sys.exit(1)

print(f"OK 部署前校验通过：{len(MIN_SIZE)} 个关键产物均非空且格式正常".replace("OK","✅"))
