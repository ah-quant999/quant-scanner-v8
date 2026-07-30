#!/usr/bin/env python3
"""v8 数据新鲜度看门狗

检查 data/*.js 中的 update_time，对比最近交易日收盘时间。
- 核心数据过期 → exit 1（CI/自动化据此阻断部署）
- 网络抖动/交互源仅告警 → exit 0

依赖：无第三方库
运行：python guard_v8_freshness.py
"""

import json, os, re, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# 数据源 → 允许最大过期小时数（按最近交易日收盘计）
# core: 部署阻断；warn: 仅告警不阻断
CORE_SOURCES = {
    "CRISIS_DATA": 4,
    "ETF_INTRADAY_HEAT": 26,
    "LIMIT_UP_HEATMAP": 26,
    "MACRO_DATA": 26,
    "MARGIN_DATA": 26,
    "NORTH_FUND": 26,
    "VOLATILITY": 26,
    "W52_HIGH": 26,
}

WARN_SOURCES = {
    "SECTOR_FUND_FLOW": 26,
    "CONCEPT_RANKING": 26,
    "IPO_DATA": 72,
    "CFFEX_HOLDINGS": 72,
    "HERDING_DATA": 72,
    "CAPITAL_FLOW_DATA": 26,
    "ETF_SUBSCRIPTION": 26,
    "MARKET_FUND_FLOW_DATA": 26,
}


def last_trade_day_close(now: datetime) -> datetime:
    """返回最近交易日收盘时间（15:30）。非交易日回退。"""
    # 简单版：周一到周五；若当前时间 < 15:30，回退到昨天收盘
    d = now.date()
    # 回退周末
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time())
    if now < close:
        # 今天还没收盘，用昨天收盘
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time())
    return close


def extract_update_time(path: Path) -> datetime | None:
    """从 data/X.js 中 window.X = {...}; 提取 update_time 字段。"""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def js_var_name(path: Path) -> str:
    return path.stem


def main():
    now = datetime.now()
    close = last_trade_day_close(now)
    stale_core = []
    stale_warn = []
    missing = []

    all_sources = {**CORE_SOURCES, **WARN_SOURCES}
    for var, max_hours in all_sources.items():
        path = DATA_DIR / f"{var}.js"
        if not path.exists():
            missing.append(var)
            if var in CORE_SOURCES:
                stale_core.append((var, "文件缺失"))
            continue
        ts = extract_update_time(path)
        if ts is None:
            if var in CORE_SOURCES:
                stale_core.append((var, "无 update_time"))
            else:
                stale_warn.append((var, "无 update_time"))
            continue
        age_hours = (close - ts).total_seconds() / 3600
        if age_hours > max_hours:
            reason = f"更新于 {ts.strftime('%m-%d %H:%M')}，落后收盘 {age_hours:.1f}h"
            if var in CORE_SOURCES:
                stale_core.append((var, reason))
            else:
                stale_warn.append((var, reason))

    status = {
        "check_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "last_trade_close": close.strftime("%Y-%m-%d %H:%M:%S"),
        "stale_core": [{"var": v, "reason": r} for v, r in stale_core],
        "stale_warn": [{"var": v, "reason": r} for v, r in stale_warn],
        "missing": missing,
    }
    out_path = DATA_DIR / "freshness_status.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"=== v8 数据新鲜度检查 {status['check_time']} ===")
    print(f"最近交易日收盘: {status['last_trade_close']}")
    if stale_core:
        print(f"\n🔴 核心数据过期（{len(stale_core)} 个，应阻断部署）:")
        for v, r in stale_core:
            print(f"  - {v}: {r}")
    if stale_warn:
        print(f"\n🟡 仅告警（{len(stale_warn)} 个）:")
        for v, r in stale_warn:
            print(f"  - {v}: {r}")
    if missing:
        print(f"\n⚠️  缺失文件: {', '.join(missing)}")
    if not stale_core and not stale_warn:
        print("\n✅ 所有数据新鲜")
        return 0

    print(f"\n状态已写入: {out_path}")
    return 1 if stale_core else 0


if __name__ == "__main__":
    sys.exit(main())
