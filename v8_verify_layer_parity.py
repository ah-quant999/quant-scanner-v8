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
from datetime import datetime, date, timedelta, timezone
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

# 🛡 2026-09-11 小九的股票专家（主人批准「时段白名单」方案）：
#   病灶：「raw 已更新到今日、data/*.js 尚未重建」被一律判 FAIL 并阻断部署。
#   而这是每日盘前/盘中的【正常中间态】—— 纯盘后产物（CATEGORY_MAP 归 post_close）
#   只在 v8_cn_fetch_cloud.yml 的 17:20/18:20/19:20 三档 --category post_close 构建时才重建；
#   盘前 raw 一刷新，mismatch 立刻出现，闸门 100% 阻断盘前部署（实测 11 项 FAIL）。
#   修法：改为【方向 + 时段】双判，不削弱真护栏：
#     · raw 比 data 新（待重建）→ 仅当已过「盘后重建窗口结束」才判失败，其余时段降级为告警
#     · data 比 raw 新 / 任一侧无日期 → 恒判失败（真错位，任何时段都不放行）
POSTCLOSE_REBUILD_DONE = (20, 30)


def _now_cst() -> datetime:
    """取中国时区当前【时刻】。

    🔴 勿用 datetime.now()：GitHub runner 是 UTC，datetime.now().date() 取到的是 UTC 日期
    （CST 00:00-08:00 时段会整整差一天）。用 timezone.utc + 8h 在 runner 与本机都正确。
    校验不依赖 v8_date，避免循环导入。
    """
    return datetime.now(timezone.utc) + timedelta(hours=8)


def _today_cst() -> date:
    """取当前日期（中国时区）。"""
    return _now_cst().date()


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
    mismatches = []          # 真错位（data 比 raw 新 / 无法解析）→ 恒判失败
    pending_mismatches = []  # raw 比 data 新（待 post_close 构建重建）→ 按时段判定
    unable = []
    stale_data = []
    missing_raw = []
    missing_data = []
    checked = 0
    _now = _now_cst()
    today = _now.date()
    after_rebuild = (_now.hour, _now.minute) >= POSTCLOSE_REBUILD_DONE

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
            _r = _parse_date(raw_date)
            _d = _parse_date(data_date)
            _rec = {
                "var": var_name,
                "raw": str(raw_path),
                "raw_date": raw_date,
                "data": str(data_path),
                "data_date": data_date,
            }
            # 🛡 方向判定：raw 比 data 新 ⇔ 消费层待重建（正常中间态，看时段）；
            #    data 比 raw 新或任一侧无日期 ⇔ 真错位（恒判失败）。
            if _r is not None and _d is not None and _r > _d:
                pending_mismatches.append(_rec)
            else:
                mismatches.append(_rec)

    print(f"🔍 跨层一致性校验完成：检查 {checked} 对，缺失 raw {len(missing_raw)} 个，缺失 data {len(missing_data)} 个，无法校验 {len(unable)} 个，真错位 {len(mismatches)} 个，待重建 {len(pending_mismatches)} 个，data 层陈旧 {len(stale_data)} 个")
    print(f"   时段判定：当前 CST {_now.strftime('%Y-%m-%d %H:%M')}，"
          f"{'已过' if after_rebuild else '未过'}盘后重建窗口结束点 "
          f"({POSTCLOSE_REBUILD_DONE[0]:02d}:{POSTCLOSE_REBUILD_DONE[1]:02d})")

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
        print("  ❌ 真错位（data 比 raw 新 / 任一侧无日期）——任何时段都不放行：")
        for m in mismatches:
            print(f"    - {m['var']}: raw={m['raw_date']} vs data={m['data_date']}")
    if pending_mismatches:
        print(f"  {'❌' if after_rebuild else '⏳'} raw 已更新、data 待 post_close 构建重建（{len(pending_mismatches)} 个）：")
        for m in pending_mismatches:
            print(f"    - {m['var']}: raw={m['raw_date']} vs data={m['data_date']}")

    # 🛡 失败条件（2026-09-11 起）：
    #   · 真错位（mismatches）              → 恒失败
    #   · data 层陈旧静默上线（stale_data）  → 恒失败（>STALE_DAYS 天，与时段无关）
    #   · 待重建（pending_mismatches）       → 仅当已过盘后重建窗口才失败；盘前/盘中只告警放行
    _hard = bool(mismatches) or bool(stale_data) or (bool(pending_mismatches) and after_rebuild)
    if _hard:
        _why = []
        if mismatches:
            _why.append(f"真错位 {len(mismatches)} 项")
        if stale_data:
            _why.append(f"陈旧静默上线 {len(stale_data)} 项")
        if pending_mismatches and after_rebuild:
            _why.append(f"盘后重建窗口已过仍有 {len(pending_mismatches)} 项未重建")
        print(f"\n🛑 {'；'.join(_why)}，阻断部署/推送。")
        return 1

    if pending_mismatches:
        print(f"\n⏳ 仅存在「raw 已更新、data/*.js 待下一次 post_close 构建重建」的正常中间态"
              f"（{len(pending_mismatches)} 项，未过盘后重建窗口），不阻断部署。")
        print("   预期由 v8_cn_fetch_cloud.yml 的 17:20/18:20/19:20 --category post_close 构建消解。")
        return 0

    print("✅ data/*.js 与 raw_data/*.json 时间戳一致，且无陈旧静默上线风险")
    return 0


if __name__ == "__main__":
    sys.exit(main())
