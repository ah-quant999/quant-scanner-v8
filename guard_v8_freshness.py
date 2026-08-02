#!/usr/bin/env python3
"""v8 数据新鲜度看门狗（全量版）

检查 data/*.js 中的 update_time，对比最近交易日收盘时间。
- CORE   核心数据过期 → exit 1（CI 据此阻断/告警）
- WARN   网络易抖源过期 → 仅告警
- FROZEN 无云端生产者的冻结快照 → 单独列出，不静默放过

⚠️ 2026-07-31 审计修订：
  旧版只检查 16 个源，恰好全是 cloud_fetch_v8.py 能抓的模块；
  而真正会陈旧的 24 个「无生产者」模块全部在监控盲区外，
  导致守卫在 SECTOR_RS 陈旧 6.4 天时仍报「所有数据新鲜」。
  本版纳入全部 46 个模块，盲区清零。

依赖：无第三方库
运行：python guard_v8_freshness.py
"""

import json, re, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# ── 分类一：云端 cloud_fetch_v8.py 每日抓取，必须新鲜 ──────────────────
CORE_SOURCES = {
    "CRISIS_DATA": 4,
    "ETF_INTRADAY_HEAT": 26,
    "LIMIT_UP_HEATMAP": 26,
    "MACRO_DATA": 26,
    "MARGIN_DATA": 26,
    "NORTH_FUND": 26,
    "VOLATILITY": 26,
    "W52_HIGH": 26,
    "INDEX_QUOTES": 26,
    "ETF_PULSE": 26,
    "ETF_DAILY_MONITOR": 26,
    "V8_CAL": 6,    # 2026-08-02 收紧：日历为高频显示，48h 太宽；周内强制日刷新，节假日另豁免,
}

# ── 分类二：网络易抖 / 低频源 / v6 算法盘后产出，仅告警 ───────────────
# 2026-08-01：post_close 模块已建立 v6→v8 同步桥（sync_v6_to_v8.py），
# 这些模块不再属于「无生产者冻结快照」，但更新频率依赖 v6 收盘链路，
# 故归入 WARN，阈值 48h；股票名录月度更新即可。
WARN_SOURCES = {
    "SECTOR_FUND_FLOW": 26,
    "CONCEPT_RANKING": 26,
    "IPO_DATA": 72,
    "CFFEX_HOLDINGS": 72,
    "HERDING_DATA": 72,
    "CAPITAL_FLOW_DATA": 26,
    "ETF_SUBSCRIPTION": 26,
    "MARKET_FUND_FLOW_DATA": 26,
    "ANALYST_RATINGS": 72,
    "EXPERIMENT": 72,
    "GOLD_POOL": 48,
    "CANDIDATE": 48,
    "TRIPLE_CONSENSUS": 48,
    "TRIPLE_TRACK": 48,
    "TRIPLE_HISTORY": 48,
    "COCKPIT_ADVICE": 48,
    "COCKPIT_TIER_RECOMMEND": 48,
    "COCKPIT_BACKTEST": 48,
    "BACKTEST_COMPREHENSIVE": 48,
    "BACKTEST_TDX": 48,
    "CRDS_CARD_DATA": 48,
    "LHB_DATA": 48,
    "SH_FIB": 48,
    "SZ_FIB": 48,
    "SECTOR_RS": 48,
    "MAHORO": 48,
    "INST_TRADE": 48,
    "NT_DATA": 48,
    "TOP10_DAILY": 48,
    "SUSPENSION_ALERT": 48,
    "MARKET_ALERTS": 48,
    "STOCK_LIST": 24 * 30,
}

# ── 分类三：无云端生产者的冻结快照 ────────────────────────────────────
# 当前暂无。保留空 dict，便于未来新增模块时快速标记。
FROZEN_SOURCES = {
}

# 引入 update_v8.py 的时段映射，用于输出"每个模块由哪个定时任务更新"
from update_v8 import CATEGORY_MAP, CATEGORY_LABEL


def last_trade_day_close(now: datetime) -> datetime:
    """返回最近交易日收盘时间（15:30）。非交易日回退。"""
    d = now.date()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time())
    if now < close:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time())
    return close


def extract_update_time(path: Path):
    """从 data/X.js 中 window.X = {...}; 提取 update_time 字段。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', text)
    if not m:
        return None
    ts = m.group(1)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts.replace("T", " ") if fmt == "%Y-%m-%d %H:%M:%S" else ts, fmt)
        except ValueError:
            continue
    return None


def check_group(group, close, label):
    """返回 (stale_list, notime_list)"""
    stale, notime = [], []
    for var, max_hours in group.items():
        path = DATA_DIR / f"{var}.js"
        if not path.exists():
            stale.append((var, "文件缺失"))
            continue
        ts = extract_update_time(path)
        if ts is None:
            notime.append(var)
            continue
        age_hours = (close - ts).total_seconds() / 3600
        if age_hours > max_hours:
            days = age_hours / 24
            stale.append((var, f"更新于 {ts.strftime('%m-%d %H:%M')}，落后 {days:.1f} 天"))
    return stale, notime


def main():
    now = datetime.now()
    close = last_trade_day_close(now)

    core_stale, core_notime = check_group(CORE_SOURCES, close, "CORE")
    warn_stale, warn_notime = check_group(WARN_SOURCES, close, "WARN")
    frozen_stale, frozen_notime = check_group(FROZEN_SOURCES, close, "FROZEN")

    def _with_cat(items):
        return [{"var": v, "reason": r, "category": CATEGORY_MAP.get(v, "post_close")} for v, r in items]

    status = {
        "check_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "last_trade_close": close.strftime("%Y-%m-%d %H:%M:%S"),
        "core_stale": _with_cat(core_stale),
        "warn_stale": _with_cat(warn_stale),
        "frozen_stale": _with_cat(frozen_stale),
        "no_update_time": sorted(core_notime + warn_notime + frozen_notime),
        "summary": {
            "total_checked": len(CORE_SOURCES) + len(WARN_SOURCES) + len(FROZEN_SOURCES),
            "core_stale": len(core_stale),
            "warn_stale": len(warn_stale),
            "frozen_stale": len(frozen_stale),
            "no_timestamp": len(core_notime) + len(warn_notime) + len(frozen_notime),
        },
        "category_map": CATEGORY_MAP,
        "category_label": CATEGORY_LABEL,
    }
    out_path = DATA_DIR / "freshness_status.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    s = status["summary"]
    print(f"=== v8 数据新鲜度检查 {status['check_time']} ===")
    print(f"最近交易日收盘: {status['last_trade_close']}")
    print(f"受检模块: {s['total_checked']} 个\n")

    if core_stale:
        print(f"🔴 核心数据过期（{len(core_stale)} 个，云端抓取异常）:")
        for v, r in core_stale:
            print(f"  - {v}: {r}")
        print()
    if warn_stale:
        print(f"🟡 次要数据过期（{len(warn_stale)} 个，网络易抖）:")
        for v, r in warn_stale:
            print(f"  - {v}: {r}")
        print()
    if frozen_stale:
        print(f"🧊 冻结快照已停更（{len(frozen_stale)} 个，无云端生产者）:")
        for v, r in frozen_stale:
            print(f"  - {v}: {r}")
        print()
    if status["no_update_time"]:
        print(f"⏱️  无时间戳（{len(status['no_update_time'])} 个，前端不显示更新时间，用户无法察觉陈旧）:")
        print(f"  {', '.join(status['no_update_time'])}\n")

    if not (core_stale or warn_stale or frozen_stale or status["no_update_time"]):
        print("✅ 全部模块新鲜")
        return 0

    print(f"状态已写入: {out_path}")
    return 1 if core_stale else 0


if __name__ == "__main__":
    sys.exit(main())
