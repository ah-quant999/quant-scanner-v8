#!/usr/bin/env python3
"""
v8 数据新鲜度守卫（freshness_guard.py）

一劳永逸式修复核心：每次自动化触发时先检查 raw_data 新鲜度，
若关键文件超阈值 → 立即标记需补抓；否则跳过本次抓取（避免无效重复请求）。

设计原则：
- 反应式：不依赖固定 schedule，而是根据数据实际年龄决定是否动作
- 静默容错：文件缺失 = 视为无限旧（需要抓取）
- 多通道友好：本机直抓 / GitHub Actions / 手动 均可调用

用法：
  python freshness_guard.py                    # 检查并输出报告
  python freshness_guard.py --check-only       # 仅检查，exit code 0=新鲜/1=陈旧
  python freshness_guard.py --category intraday # 指定类别检查
  python freshness_guard.py --threshold 25     # 自定义阈值（分钟）

退出码：
  0 = 所有文件新鲜（无需抓取）
  1 = 存在陈旧文件（需要立即抓取）
  2 = 非交易时段（跳过）

输出（stdout）：
  单行摘要 + 陈旧文件列表（供 automation prompt 消费）
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
CST = timezone(timedelta(hours=8))

# 关键文件 → 最大允许年龄（分钟）→ 所属时段
# 时段: premarket / intraday / post_close / all
FRESHNESS_RULES = {
    # ──盘中实时数据（交易时段每20分钟必须刷新）──
    "sector_fund_flow.json":      {"threshold": 25, "category": "intraday", "label": "板块资金流向"},
    "index_quotes.json":          {"threshold": 25, "category": "intraday", "label": "大盘指数"},
    "concept_ranking.json":       {"threshold": 25, "category": "intraday", "label": "概念排名"},
    "capital_flow_data.json":     {"threshold": 25, "category": "intraday", "label": "资金流向"},
    "etf_intraday_heat.json":     {"threshold": 25, "category": "intraday", "label": "ETF热度"},
    "etf_pulse.json":             {"threshold": 25, "category": "intraday", "label": "ETF脉搏"},
    "limit_up_heatmap.json":      {"threshold": 25, "category": "intraday", "label": "涨停热力"},
    "overseas_markets.json":      {"threshold": 30, "category": "intraday", "label": "亚太市场"},
    "avg_price_data.json":        {"threshold": 25, "category": "intraday", "label": "均价数据"},
    # ──盘前数据（08:15后有效至开盘）──
    "ipo_score.json":             {"threshold": 180, "category": "premarket", "label": "打新速览"},
    "margin_data.json":           {"threshold": 180, "category": "premarket", "label": "融资融券"},
    "north_fund.json":            {"threshold": 60,  "category": "premarket", "label": "北向资金"},
    "analyst_ratings.json":       {"threshold": 360, "category": "premarket", "label": "分析师评级"},
    "macro_data.json":            {"threshold": 360, "category": "premarket", "label": "宏观数据"},
    # ──盘后数据（15:30后）──
    "lhb_data.json":              {"threshold": 480, "category": "post_close", "label": "龙虎榜"},
    "sector_fund_flow_trend.json": {"threshold": 1440, "category": "post_close", "label": "板块资金趋势(5/10/20/60日)"},
    # 🛡 2026-08-27 主人令：SECTOR_FUND_FLOW_TREND 数据源（资金验证卡 5/10/20/60 日累计），
    #   由 fetch_orphan_sector_fund_flow.py 盘后产出，纳入审计杜绝"每天审计个毛线"漏检。
}

# 交易时段定义（CST HHMM）
TRADING_SESSIONS = [
    (930,  1130),  # 上午盘
    (1300, 1500),  # 下午盘
]

PREMARKET_WINDOW = (815, 925)   # 盘前窗口
POST_CLOSE_WINDOW = (1530, 1700) # 盘后窗口

# 午休时段（数据不更新但最后一批盘中数据仍有效）
LUNCH_BREAK = (1130, 1300)

# 午休期间允许的最大数据年龄（分钟）——11:30前的数据到13:00仍算新鲜
LUNCH_ALLOW_AGE = 65


def now_cst():
    return datetime.now(CST)


def get_update_time(filepath):
    """从 JSON 文件内读取 update_time 字段（含嵌套 meta）。"""
    p = RAW_DIR / filepath
    if not p.exists():
        return None
    try:
        d = json.load(open(p, encoding="utf-8"))
        if not isinstance(d, dict):
            return None
        ts = d.get("update_time") or d.get("timestamp") or d.get("updated_at") or d.get("generated")
        if not ts:
            meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
            ts = meta.get("update_time") or meta.get("timestamp") or meta.get("updated_at") or meta.get("generated")
        return ts
    except Exception:
        return None


def is_trading_day(d):
    """简化交易日判断：周一至周五（不含周末，忽略法定节假日）。"""
    return d.weekday() < 5


def last_published_lhb_date(now):
    """
    LHB（龙虎榜）于交易日 D 约 17:00 后由交易所发布。
    返回「最新已发布 LHB 对应的交易日」(date 对象)：
    - 若 today 是交易日且 now>=17:00 → today 已发布
    - 否则 → 向前回溯到最近的已收盘交易日
    用于根治 17:00 边界缝隙：mtime 新鲜 ≠ 内容已为当日龙虎榜。
    """
    d = now.date()
    if is_trading_day(d) and now.hour >= 17:
        return d
    cand = d - timedelta(days=1)
    while not is_trading_day(cand):
        cand -= timedelta(days=1)
    return cand


def is_pre_t1_hours(now=None):
    """非交易日 T+1 未发布闸门（主人 2026-09-05 令）。

    周末/法定假期的 09:00 之前，T+1 数据尚未发布：
      - 今日事件  最早 08:25
      - 实时数据  09:30 之后才稳定
      - 盘后/选股 T+1 要 18:30+
    此时任何抓取都会拿到前一天数据或误把陈旧当"新鲜"，应直接跳过。
    交易日不受此闸门限制（盘中/盘后调度照常）。

    返回 True 表示「应在 T+1 发布前跳过抓取/检查」。
    """
    if now is None:
        now = now_cst()
    if is_trading_day(now.date()):
        return False
    return now.hour < 9


def get_lhb_content_date(filepath):
    """读取 lhb_data.json 的 date 字段（YYYYMMDD，int）。缺失/异常返回 None。"""
    p = RAW_DIR / filepath
    if not p.exists():
        return None
    try:
        d = json.load(open(p, encoding="utf-8"))
        cd = d.get("date")
        if cd is None:
            return None
        return int(str(cd))
    except Exception:
        return None


def is_stopped_disclosure(filepath):
    """
    判断该文件是否为「数据源已永久停止披露」的占位文件。

    典型：raw_data/north_fund.json 恒为
        {"stopped": true, "note": "港交所 2024-05 后停止披露北向 top_buy"}
    内容不会再变化，两次抓取间隔必然 > 其 60 分钟阈值 → 永久假阳性 STALE。
    🛡 2026-09-03 修复（主人授权）：内容标记 stopped:true 时视为 FRESH。
    """
    p = RAW_DIR / filepath
    if not p.exists():
        return False
    try:
        d = json.load(open(p, encoding="utf-8"))
        return isinstance(d, dict) and d.get("stopped") is True
    except Exception:
        return False


def get_file_age(filepath):
    """返回文件年龄（分钟），文件不存在返回 None（视为无限旧）。

    🛡 2026-08-20 一劳永逸修复：优先按文件内层 update_time 判龄，fallback 到 mtime。
    根因：仅看 mtime 会出现「文件刚被 git checkout / sync 更新，但内层数据时间戳仍陈旧」
    的假绿；实盘应以数据本身声明的 update_time 为准。
    """
    p = RAW_DIR / filepath
    if not p.exists():
        return None
    ts = get_update_time(filepath)
    if ts:
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
            age_min = (now_cst() - dt).total_seconds() / 60
            return age_min
        except Exception:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=CST)
                age_min = (now_cst() - dt).total_seconds() / 60
                return age_min
            except Exception:
                pass
    mtime = os.path.getmtime(p)
    mt_dt = datetime.fromtimestamp(mtime, tz=CST)
    age_min = (now_cst() - mt_dt).total_seconds() / 60
    return age_min


def in_trading_hours(hhmm=None):
    """判断当前是否在交易连续竞价时段。"""
    if hhmm is None:
        hhmm = int(now_cst().strftime("%H%M"))
    for start, end in TRADING_SESSIONS:
        if start <= hhmm < end:
            return True
    return False


def in_lunch_break(hhmm=None):
    """判断当前是否在午休时段（11:30-13:00）。"""
    if hhmm is None:
        hhmm = int(now_cst().strftime("%H%M"))
    return LUNCH_BREAK[0] <= hhmm < LUNCH_BREAK[1]


def in_active_market_hours(hhmm=None):
    """判断当前是否在盘中或午休（任何需要监控数据新鲜度的时段）。"""
    return in_trading_hours(hhmm) or in_lunch_break(hhmm)


def in_premarket(hhmm=None):
    if hhmm is None:
        hhmm = int(now_cst().strftime("%H%M"))
    return PREMARKET_WINDOW[0] <= hhmm <= PREMARKET_WINDOW[1]


def in_post_close(hhmm=None):
    if hhmm is None:
        hhmm = int(now_cst().strftime("%H%M"))
    return POST_CLOSE_WINDOW[0] <= hhmm <= POST_CLOSE_WINDOW[1]


def determine_current_category(hhmm=None):
    """根据当前时间返回应检查的数据类别。"""
    if hhmm is None:
        hhmm = int(now_cst().strftime("%H%M"))
    if in_trading_hours(hhmm):
        return "intraday"
    elif in_lunch_break(hhmm):
        return "lunch"  # 午休：盘中数据不更新但应监控是否已过旧
    elif in_premarket(hhmm):
        return "premarket"
    elif in_post_close(hhmm):
        return "post_close"
    else:
        return "off_hours"


def check_freshness(category=None, threshold_override=None):
    """
    检查数据新鲜度。
    返回 (stale_files, fresh_count, stale_count, report_lines)
    """
    # 🛡 2026-09-05 主人令：非交易日 T+1 未发布闸门（09:00 前跳过）
    if is_pre_t1_hours():
        return [], 0, 0, ["非交易日T+1未发布(09:00前闸门)，跳过抓取"]

    now = now_cst()
    hhmm = int(now.strftime("%H%M"))

    if category is None:
        category = determine_current_category(hhmm)

    # 非交易时段且非盘前/盘后/午休 → 直接跳过
    if category == "off_hours":
        return [], 0, 0, [f"非交易时段(HHMM={hhmm:04d})，跳过新鲜度检查"]

    # 午休时段：使用宽松阈值（11:30前的数据到13:00仍算新鲜）
    lunch_mode = (category == "lunch")

    stale_files = []
    fresh_count = 0
    stale_count = 0
    lines = []

    for filename, rule in FRESHNESS_RULES.items():
        # 🛡 2026-09-03 修复（主人授权）：category="all" 曾是「空集恒真」陷阱——
        #    FRESHNESS_RULES 里没有任何文件 category=="all"，下面这层过滤会把每条规则
        #    全部 continue 掉 → 0 个文件被检查 → 恒返回 FRESH，
        #    导致「all FRESH」长期被误当成交叉验证证据（vacuous truth）。
        #    现语义修正为：category="all" = 检查全部文件（各用自身阈值）。
        if category != "all":
            # 只检查匹配类别的文件（all 类别始终检查；午休也检查 intraday）
            if rule["category"] not in ("all", category):
                if not (lunch_mode and rule["category"] == "intraday"):
                    continue

        threshold = threshold_override or rule["threshold"]
        # 午休模式：阈值放大到 LUNCH_ALLOW_AGE
        if lunch_mode and not threshold_override:
            threshold = max(threshold, LUNCH_ALLOW_AGE)
        age = get_file_age(filename)
        ut = get_update_time(filename)

        # ── LHB 语义门控（根治 17:00 边界缝隙）──
        # mtime 新鲜 ≠ 内容已为当日龙虎榜；按 content date 与「最新已发布交易日」比对
        semantic_stale = False
        if filename == "lhb_data.json":
            cd = get_lhb_content_date(filename)
            if cd is not None:
                expected = int(last_published_lhb_date(now).strftime("%Y%m%d"))
                if cd < expected:
                    semantic_stale = True

        if age is None:
            # 文件不存在 = 无限旧
            stale_files.append({
                "file": filename,
                "label": rule["label"],
                "age": -1,
                "threshold": threshold,
                "reason": "FILE_MISSING",
                "update_time": ut,
            })
            stale_count += 1
        elif is_stopped_disclosure(filename):
            # ── 停止披露豁免 ──
            # 数据源永久停更（如 north_fund 北向 top_buy）的占位文件，内容恒为
            # {"stopped": true, ...} → 不再以年龄判陈旧，直接计为新鲜，杜绝永久假阳性。
            fresh_count += 1
        elif semantic_stale:
            # 内容 date 早于最新已发布交易日（典型：17:00 边界 mtime 新鲜但仍是昨日龙虎榜）
            stale_files.append({
                "file": filename,
                "label": rule["label"],
                "age": round(age, 1) if age is not None else -1,
                "threshold": threshold,
                "reason": "LHB_CONTENT_STALE",
                "update_time": ut,
            })
            stale_count += 1
        elif age > threshold:
            stale_files.append({
                "file": filename,
                "label": rule["label"],
                "age": round(age, 1),
                "threshold": threshold,
                "reason": "STALE",
                "update_time": ut,
            })
            stale_count += 1
        else:
            fresh_count += 1

    # 构建报告
    cat_zh = {"intraday": "盘中", "premarket": "盘前", "post_close": "盘后"}.get(category, category)
    lines.append(f"[{now.strftime('%H:%M:%S')}] {cat_zh}新鲜度检查: {fresh_count}新鲜/{stale_count}陈旧")

    if stale_files:
        lines.append("⚠️ 陈旧文件:")
        for sf in stale_files:
            age_str = f"{sf['age']:.0f}分钟" if sf['age'] >= 0 else "缺失"
            reason_str = {"FILE_MISSING": "❌文件不存在", "STALE": "⏰超阈值",
                          "LHB_CONTENT_STALE": "📅内容非最新交易日"}[sf["reason"]]
            lines.append(
                f"  - [{sf['label']}] {sf['file']} ({age_str}, "
                f"阈值{sf['threshold']}min, {reason_str})"
            )
    else:
        lines.append("✅ 所有文件新鲜")

    return stale_files, fresh_count, stale_count, lines


def main():
    parser = argparse.ArgumentParser(description="v8 数据新鲜度守卫")
    parser.add_argument("--check-only", action="store_true", help="仅检查不输出详细报告")
    parser.add_argument("--category", choices=["intraday", "premarket", "post_close", "lunch", "all"],
                        default=None, help="指定检查类别")
    parser.add_argument("--threshold", type=int, default=None, help="全局覆盖阈值（分钟）")
    parser.add_argument("--quiet", action="store_true", help="静默模式，仅输出单行")
    args = parser.parse_args()

    stale_files, fresh, stale, lines = check_freshness(
        category=args.category,
        threshold_override=args.threshold
    )

    # 输出
    if args.quiet:
        if stale_files:
            print(f"STALE:{stale}:{','.join(s['file'] for s in stale_files)}")
        else:
            print("FRESH")
    elif args.check_only:
        print(lines[0])  # 只输出摘要行
    else:
        print("\n".join(lines))

    # 退出码
    if determine_current_category() == "off_hours":
        sys.exit(2)
    elif stale_files:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
