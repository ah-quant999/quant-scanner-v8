#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_verify_layer_parity.py — data/*.js 与 raw_data/*.json 时间戳一致性校验

背景：update_v8.py 负责把 raw_data/*.json 桥接到 data/*.js。若二者时间戳不一致，
说明消费层没有正确重建（如 2026-08-29 data/CANDIDATE.js 卡在 08-26 而 raw_data/candidate.json
已是 08-29）。本脚本在构建末尾运行，发现不一致即 fail，防止此类错位 silent 多日。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 把仓库根加入路径以导入 update_v8 的 DATA_SOURCES
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from update_v8 import DATA_SOURCES

RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"

# 按优先级取最可靠的日期字段
DATE_KEYS = ("update_time", "calc_time", "gen_time", "run_time", "date", "data_date")


def _extract_date_from_json(path: Path) -> str | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    for k in DATE_KEYS:
        if k in obj and obj[k]:
            return str(obj[k])
    return None


def _extract_date_from_js(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    for k in DATE_KEYS:
        m = re.search(rf'"{re.escape(k)}"\s*:\s*"([^"]+)"', text)
        if m:
            return m.group(1)
    return None


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    # 支持 "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD"
    if len(value) >= 10:
        return value[:10]
    return value


def main() -> int:
    mismatches = []
    unable = []
    missing_raw = []
    missing_data = []
    checked = 0

    for raw_name, var_name in DATA_SOURCES.items():
        raw_path = RAW_DIR / raw_name
        data_path = DATA_DIR / f"{var_name}.js"

        if not raw_path.exists():
            missing_raw.append(var_name)
            continue
        if not data_path.exists():
            missing_data.append(var_name)
            continue

        raw_date = _extract_date_from_json(raw_path)
        data_date = _extract_date_from_js(data_path)
        checked += 1

        raw_dp = _date_part(raw_date)
        data_dp = _date_part(data_date)

        # raw 无日期字段 → 无法校验，仅记录；data 无日期但 raw 有 → 算不一致
        if raw_dp is None:
            unable.append({"var": var_name, "raw_date": raw_date, "data_date": data_date})
            continue
        if data_dp is None or raw_dp != data_dp:
            mismatches.append(
                {
                    "var": var_name,
                    "raw": str(raw_path),
                    "raw_date": raw_date,
                    "data": str(data_path),
                    "data_date": data_date,
                }
            )

    print(f"🔍 跨层一致性校验完成：检查 {checked} 对，缺失 raw {len(missing_raw)} 个，缺失 data {len(missing_data)} 个，无法校验 {len(unable)} 个，日期不一致 {len(mismatches)} 个")

    if missing_raw:
        print("  ⚠️ 缺失 raw_data（数据源未产出）:")
        for v in missing_raw:
            print(f"    - {v}")
    if missing_data:
        print("  ⚠️ 缺失 data/*.js（消费层未生成）:")
        for v in missing_data:
            print(f"    - {v}")
    if unable:
        print("  ⚠️ raw_data 无日期字段，无法校验：")
        for u in unable:
            print(f"    - {u['var']}: raw={u['raw_date']} data={u['data_date']}")
    if mismatches:
        print("  ❌ 日期不一致（消费层陈旧 / 未重建）：")
        for m in mismatches:
            print(f"    - {m['var']}: raw={m['raw_date']} vs data={m['data_date']}")

    # 日期不一致必须阻塞；缺失/无法校验仅告警
    if mismatches:
        print("\n🛑 存在消费层时间戳不一致，阻断部署/推送以防止陈旧数据上线。")
        return 1

    print("✅ data/*.js 与 raw_data/*.json 时间戳一致（或可校验部分一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
