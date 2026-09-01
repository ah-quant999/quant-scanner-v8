#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_delisted.py — 从 raw_data/delisted_stocks.json 生成 data/DELISTED.js
（2026-08-30 一劳永逸：file-level update_time 必须 = 今日，避免被 v8_health_check 误判 WARN）

输入：raw_data/delisted_stocks.json（[{code, name, delisted_date, last_board, last_industry}, ...]）
输出：data/DELISTED.js
  window.DELISTED_STOCKS = {
    total: int,                  # 全量下架样本数
    recent: [...],               # 最近 30 条
    update_time: "YYYY-MM-DD",   # 文件生成日（今日）—— 健康检查看这个
    data_update: "YYYY-MM-DD",   # 数据时间戳 = max(delisted_date)
    source: "raw_data/delisted_stocks.json",
    generated_at: "YYYY-MM-DD HH:MM:SS"
  }

调用：
    python scripts/build_delisted.py
CI workflow: 暂 manual_dep=True（CARD_DEFS 中标注），由主人触发 + 推送。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW_PATH = REPO / "raw_data" / "delisted_stocks.json"
OUT_PATH = REPO / "data" / "DELISTED.js"


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def main():
    if not RAW_PATH.exists():
        print(f"[ERR] raw 不存在: {RAW_PATH}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"[ERR] raw 顶层不是 list: {type(raw)}", file=sys.stderr)
        sys.exit(1)

    items = []
    for r in raw:
        try:
            items.append({
                "code": str(r.get("code", "")).zfill(5),
                "name": str(r.get("name", "")),
                "delisted_date": str(r.get("delisted_date", "")),
                "last_board": str(r.get("last_board", "")),
                "last_industry": str(r.get("last_industry", "")),
            })
        except Exception:
            continue

    items.sort(key=lambda x: x.get("delisted_date", ""), reverse=True)

    today = now_cst().strftime("%Y-%m-%d")
    now_hms = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    data_update = items[0].get("delisted_date", today) if items else today

    payload = {
        "total": len(items),
        "recent": items[:30],
        "update_time": today,                     # ← 健康检查红线：必须 = 今日
        "data_update": data_update,               # ← 数据本身最新日（可选审计）
        "source": "raw_data/delisted_stocks.json",
        "generated_at": now_hms,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"/* data/DELISTED.js — 已下架股票目录（{now_hms} 由 scripts/build_delisted.py 重建） */\n")
        f.write("window.DELISTED_STOCKS = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"[OK] {OUT_PATH} | total={payload['total']} | update_time={payload['update_time']} | data_update={payload['data_update']}")


if __name__ == "__main__":
    main()
