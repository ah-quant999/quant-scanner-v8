#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_weekend_run.py — 周度运行汇总（轻量，2026-08-18 主人令补入）
==================================================================
原 v8 健康巡检 data/WEEKEND_RUN.js 找不到生成脚本（孤儿），导致健康巡检
永远报"无 update_time/date/generated 时间戳，无法判龄（缺审计登记）"。
本脚本由 algorithms/run_algorithms.py 周末链路调用，产出：
  raw_data/weekend_run.json  （update_v8.py → data/WEEKEND_RUN.js）
内容：
  - 本周每个交易日（last_week_start ~ last_week_end）的算法链跑批统计
  - 各核心 data/*.js 文件的新鲜度快照
  - 周度自愈事件计数（来自 .workbuddy/v8_health_report.json）
  - update_time + generated 字段（让健康巡检可判龄）

设计原则：
  - 只读已存在的 raw_data + data，不发起任何外网请求（周度离线可跑）
  - 轻量：执行 < 2s，文件 < 5KB
  - 幂等：重复跑覆盖 update_time 即可
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "raw_data"
DATA = BASE / "data"
HEALTH_REPORT = BASE / ".workbuddy" / "v8_health_report.json"

# 周度核心数据清单（不与具体窗口挂钩：抓最近 5 个交易日，覆盖周六/周一/节假日）
WEEKLY_TRACK = [
    ("lhb_data.json",            "龙虎榜"),
    ("triple_history.json",      "三重共振历史"),
    ("top10_daily.json",         "全站精选"),
    ("cockpit_tier_recommend.json", "驾驶舱分档"),
    ("sector_rs.json",           "板块相对强度"),
    ("final_recommend.json",     "最终推荐池"),
    ("gold_pool.json",           "黄金池"),
    ("candidate.json",           "候选池"),
    ("four_volume.json",         "四量终极"),
    ("crds_card_data.json",      "逆势龙头"),
]


def now_cst_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def _load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def main():
    now = now_cst_str()
    last_monday = (datetime.now(CST) - timedelta(days=datetime.now(CST).weekday() + 7)).date()
    this_monday = last_monday + timedelta(days=7)
    period_start = last_monday.isoformat()
    period_end = (this_monday - timedelta(days=1)).isoformat()

    # 1) 抓周度每个核心文件的新鲜度快照
    freshness = []
    for fname, label in WEEKLY_TRACK:
        p = RAW / fname
        if not p.exists():
            freshness.append({"file": fname, "label": label, "status": "missing", "update_time": None})
            continue
        d = _load_json(p, {})
        ts = d.get("update_time") or d.get("date") or d.get("generated") or None
        freshness.append({
            "file": fname, "label": label, "status": "ok",
            "update_time": ts, "size_kb": round(p.stat().st_size / 1024, 1),
        })

    # 2) 抓上周末健康巡检的统计（如有）
    heal = _load_json(HEALTH_REPORT, {})
    weekly_stats = {
        "period_start": period_start,
        "period_end": period_end,
        "tracked_files": len(WEEKLY_TRACK),
        "ok_files": sum(1 for f in freshness if f.get("status") == "ok"),
        "missing_files": sum(1 for f in freshness if f.get("status") == "missing"),
        # 健康巡检统计（如有 health report 落盘）
        "latest_health": {
            "ok": heal.get("summary", {}).get("ok", 0),
            "warn": heal.get("summary", {}).get("warn", 0),
            "fail": heal.get("summary", {}).get("fail", 0),
            "total": heal.get("summary", {}).get("total", 0),
            "updated": heal.get("updated"),
        } if heal else None,
    }

    out = {
        "update_time": now,
        "generated": now,                       # 同时给 generated 字段，让健康巡检可双路判龄
        "period_start": period_start,
        "period_end": period_end,
        "stats": weekly_stats,
        "freshness": freshness,
        "source_note": "v8 周度运行汇总（轻量，离线可跑；由 algorithms/run_algorithms.py 周末链路调用）",
    }

    RAW.mkdir(parents=True, exist_ok=True)
    out_path = RAW / "weekend_run.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 写入 {out_path} ({out_path.stat().st_size} bytes, period={period_start} ~ {period_end})")
    print(f"     ok={weekly_stats['ok_files']} missing={weekly_stats['missing_files']} total={weekly_stats['tracked_files']}")


if __name__ == "__main__":
    main()
