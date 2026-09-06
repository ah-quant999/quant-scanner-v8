#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_unlisted_panel.py — 生成 data/UNLISTED_PANEL.js（2026-08-30 一劳永逸）

设计说明：暂未上架 = 主人/AI 决定暂时不公开的实验模块占位。
本脚本只把 8 个面板目标拍平，不读 raw（避免误读三方）。
hero.json / modules.json / meta 全部内嵌，meta 必须存在（CARD_DEFS key_fields 要求）。

调用：
    python scripts/build_unlisted_panel.py
CI workflow: manual_dep=True（主人拍板再推）
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "data" / "UNLISTED_PANEL.js"


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


# 2026-08-30 主仓库摸排：8 个实验模块暂未上架的归类（手动维护；新增模块必须主人确认）
_MODULES = [
    {"id": "ETF_4WAY",       "name": "ETF 四路资金流向",      "reason": "稳定但缺 ETF 全量榜单交付",                "status": "evaluation"},
    {"id": "SECTOR_PHASE_HISTORY", "name": "板块周期历史曲线", "reason": "vs push2 接口 5d/10d/20d/60d 趋势",     "status": "spec_lock"},
    {"id": "INDUSTRY_TREE_DRILL", "name": "行业树图（下钻）",  "reason": "申万三级下钻与个股联动未对齐",            "status": "blocked"},
    {"id": "STOCK_RPS_MULTI",   "name": "相对强度多周期",      "reason": "数据齐备，前端卡片未设计",                "status": "design"},
    # 🛡 2026-09-02 主人令：3⭐ 大牛股猎手已决定删除，其独立实验卡（大牛股猎手 X）从模块去向索引移除。
    {"id": "RUNNER_HEALTH",     "name": "Runner 健康监控卡",   "reason": "RUNNER_STATUS 数据已有，前端图表规格未定", "status": "design"},
    {"id": "FY_CALENDAR",       "name": "财年事件日历",        "reason": "v8 改为每月 1 日自动更新（8/30 已上线）", "status": "shipped_via_v8_cal"},
]


def main():
    today = now_cst().strftime("%Y-%m-%d")
    now_hms = now_cst().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "modules": _MODULES,
        "update_time": today,                  # ← 健康检查红线
        "note": "实验模块去向由主人拍板；新增模块请改 scripts/build_unlisted_panel.py",
        "meta": {                              # ← CARD_DEFS key_fields ["modules","meta"] 要求 meta 必填
            "schema_version": 1,
            "total": len(_MODULES),
            "owner": "master",
            "last_review": today,
            "source": "scripts/build_unlisted_panel.py",
            "generated_at": now_hms,
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"/* data/UNLISTED_PANEL.js — 暂未上架模块索引（{now_hms} 由 scripts/build_unlisted_panel.py 重建） */\n")
        f.write("window.UNLISTED_PANEL = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"[OK] {OUT_PATH} | modules={len(_MODULES)} | update_time={payload['update_time']}")


if __name__ == "__main__":
    main()
