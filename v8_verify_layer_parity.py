#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_verify_layer_parity.py — data/*.js 与 raw_data/*.json 时间戳一致性校验

背景：update_v8.py 负责把 raw_data/*.json 桥接到 data/*.js。若二者时间戳不一致，
说明消费层没有正确重建（如 2026-08-29 data/CANDIDATE.js 卡在 08-26 而 raw_data/candidate.json
已是 08-29）。本脚本在构建末尾运行，发现不一致即 fail，防止此类错位 silent 多日。

🛡 2026-08-29 升级：raw 无日期字段的「无法校验」文件，额外检查 data 层 update_time
与今日日期差值，超过 STALE_DAYS 视为「陈旧数据静默上线」，纳入失败项。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

# 把仓库根加入路径以导入 update_v8 的 DATA_SOURCES
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from update_v8 import DATA_SOURCES

RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"

# 按优先级取最可靠的日期字段
DATE_KEYS = ("update_time", "calc_time", "gen_time", "run_time", "date", "data_date")

# 🛡 2026-08-29：raw 无日期字段时，data 层超过此天数即判为陈旧静默上线
STALE_DAYS = 3


def _today_cst() -> date:
    """取当前日期（中国时区）。校验不依赖 v8_date，避免循环导入。"""
    return datetime.now().date()


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
    """优先解析整个 JS 对象取顶层日期字段，避免嵌套数组里的旧时间戳被误取
    （如 SECTOR_PHASE_HISTORY.js 的 snaps 里含多个 update_time）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    # 尝试 1：完整 JSON 解析，取顶层字段
    body = text
    m = re.search(r'window\.[A-Z0-9_]+\s*=\s*', body)
    if m:
        body = body[m.end():].rstrip()
    if body.endswith(';'):
        body = body[:-1]
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            for k in DATE_KEYS:
                if k in obj and obj[k]:
                    return str(obj[k])
    except Exception:
        pass

    # 尝试 2：IIFE 壳 —— var data = {...};
    m2 = re.search(r'var\s+data\s*=\s*(\{[\s\S]*?\})\s*;', text)
    if m2:
        try:
            obj = json.loads(m2.group(1))
            if isinstance(obj, dict):
                for k in DATE_KEYS:
                    if k in obj and obj[k]:
                        return str(obj[k])
        except Exception:
            pass

    # 兜底：正则找第一个日期字段（旧行为，保持兼容性）
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


def _parse_date(value: str | None) -> date | None:
    """从字符串中解析日期（支持 YYYY-MM-DD 或 ISO 格式前缀）。"""
    if not value:
        return None
    s = str(value).strip()
    if len(s) >= 10:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def main() -> int:
    mismatches = []
    unable = []
    stale_data = []
    missing_raw = []
    missing_data = []
    checked = 0
    today = _today_cst()

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

        # raw 无日期字段 → 无法直接校验；但检查 data 层是否已陈旧（静默上线）
        if raw_dp is None:
            data_dt = _parse_date(data_date)
            if data_dt is not None and (today - data_dt).days > STALE_DAYS:
                stale_data.append({
                    "var": var_name,
                    "data_date": data_date,
                    "stale_days": (today - data_dt).days,
                })
            else:
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

    print(f"🔍 跨层一致性校验完成：检查 {checked} 对，缺失 raw {len(missing_raw)} 个，缺失 data {len(missing_data)} 个，无法校验 {len(unable)} 个，日期不一致 {len(mismatches)} 个，data 层陈旧 {len(stale_data)} 个")

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
    if stale_data:
        print(f"  ❌ data 层超过 {STALE_DAYS} 天未更新（raw 无日期字段，属陈旧静默上线）：")
        for s in stale_data:
            print(f"    - {s['var']}: data={s['data_date']} 已陈旧 {s['stale_days']} 天")
    if mismatches:
        print("  ❌ 日期不一致（消费层陈旧 / 未重建）：")
        for m in mismatches:
            print(f"    - {m['var']}: raw={m['raw_date']} vs data={m['data_date']}")

    # 日期不一致 或 data 层陈旧静默上线 均视为失败
    if mismatches or stale_data:
        print("\n🛑 存在消费层时间戳不一致或陈旧数据静默上线，阻断部署/推送。")
        return 1

    print("✅ data/*.js 与 raw_data/*.json 时间戳一致，且无陈旧静默上线风险")
    return 0


if __name__ == "__main__":
    sys.exit(main())
