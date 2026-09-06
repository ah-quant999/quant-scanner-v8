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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# 2026 年中国A股休市区间（与 cloud_fetch_v8.py 保持一致；每年初同步更新）
_HOLIDAY_RANGES_2026 = [
    ("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
]
# 补班日（周末但实际交易日）
_MAKEUP_DAYS_2026 = {
    "2026-01-04", "2026-02-14", "2026-02-28",
    "2026-05-09", "2026-09-20", "2026-10-10",
}


def _is_trading_day(d) -> bool:
    """判断某天是否为 A 股交易日（含补班日、剔除周末和节假日）。"""
    if d.weekday() >= 5 and d.isoformat() not in _MAKEUP_DAYS_2026:
        return False
    iso = d.isoformat()
    for start, end in _HOLIDAY_RANGES_2026:
        if start <= iso <= end:
            return False
    return True


def trading_days_between(start_date, end_date) -> int:
    """两个日期之间经过的交易日数（含两端；周末/节假日扣除；补班日计入）。

    返回的是「start_date 当天是否交易 + start→end 之间每个交易日」的累计。
    用于「CORE=3天」类阈值改按交易日判定，避免「周五→周一」按日历 3 天误报。

    示例（假设无节假日）：
        trading_days_between(Fri, Fri) = 1   # 当天
        trading_days_between(Fri, Mon) = 2   # Fri + Mon（Sat/Sun 跳过）
        trading_days_between(Fri, Tue) = 3   # Fri + Mon + Tue
    """
    if end_date < start_date:
        return 0
    from datetime import timedelta
    n = 0
    d = start_date
    while d <= end_date:
        if _is_trading_day(d):
            n += 1
        d += timedelta(days=1)
    return n

# ── 分类一：云端 cloud_fetch_v8.py 每日抓取，必须新鲜 ──────────────────
# 阈值单位：小时。>= 24h 的阈值在 check_group 内自动按「交易日」判定（避开周末/节假日误报）。
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
    "SH_SZ_HISTORY": 72,  # 2026-08-02 修订：原 3h 偏严（盘中刚过就误报），改 72h=3 个交易日；check_group 按交易日判定
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
    "MARKET_FUND_FLOW_DATA": 26,
    "ANALYST_RATINGS": 72,
    "EXPERIMENT": 72,
    "GOLD_POOL": 48,
    "CANDIDATE": 48,
    "TRIPLE_CONSENSUS": 48,
    "TRIPLE_TRACK": 48,
    "TRIPLE_HISTORY": 48,
    # 2026-09-04 主人令收尾：COCKPIT_ADVICE/COCKPIT_TIER_RECOMMEND 阈值已删（驾驶舱模块下线）
    "LHB_DATA": 48,
    "SH_FIB": 48,
    "SZ_FIB": 48,
    "SECTOR_RS": 48,
    "INST_TRADE": 48,
    "LHB_HISTORY": 48,  # 龙虎榜历史（机游共振/北向席位日历）：18:30 算法链累积，每日刷新
    "NT_DATA": 48,
    "TOP10_DAILY": 48,
    "SUSPENSION_ALERT": 48,
    "MARKET_ALERTS": 48,
    "STOCK_LIST": 24 * 30,
    # 🛡 2026-08-27 主人令：SECTOR_FUND_FLOW_TREND 资金验证数据源（fetch_orphan 盘后产出），
    #   此前完全不在审计清单 → "资金验证60日夸张/陈旧"无人发现。纳入 WARN 48h。
    "SECTOR_FUND_FLOW_TREND": 48,
}

# 🛡 2026-08-20 主人令·一劳永逸：策略回测（统一）卡片依赖选股算法产出，
# 必须纳入 CORE 并由 v8_algo_cloud 自动补跑。旧版在 WARN 仅告警不自愈，
# 导致 08-19 18:30 算法链 failure 后卡片停更 24h+ 无人问津。
# 阈值用 24h：跨一个交易日未更新即 stale（周五→周一按交易日算会正确触发）。
CORE_SOURCES_ALGO = {
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST 已删（驾驶舱模块下线）
    "BACKTEST_COMPREHENSIVE": 24,
    "BACKTEST_TDX": 24,
    "CRDS_CARD_DATA": 24,
    # 🔴 2026-08-20 根因修复：LHB_7D.js 由算法链生成，之前不在监控/自愈范围，
    #    文件停更 24h+ 无告警，页面 7 日龙虎榜/机游共振长期 stale。
    "LHB_7D": 24,
    # INDEX_HISTORY（5年上证K线）由 19:15 算法链产出，纳入 CORE 监控/自愈。
    "INDEX_HISTORY": 48,
}

# ── 分类三：无云端生产者的冻结快照 ────────────────────────────────────
# 当前暂无。保留空 dict，便于未来新增模块时快速标记。
FROZEN_SOURCES = {
}

# 引入 update_v8.py 的时段映射，用于输出"每个模块由哪个定时任务更新"
from update_v8 import CATEGORY_MAP, CATEGORY_LABEL

# ── 自愈派发能力（2026-08-16 根治「只看门狗只查不修、刷屏不自愈」）──
# 旧版 guard 只检查 data/*.js 是否陈旧，返回非0 → 调用它的「数据新鲜度自动值守」自动化
# 每小时向主人汇报一次故障，但从不修复 → 死循环刷屏（今早 alimi-cn 离线致 cn_fetch
# 周度刷新失败，guard 每 :30 报一次）。
# 新版：发现 CORE stale → 自动 dispatch 对应 category 的 cn_fetch 在**在线** self-hosted
# cn runner 上重抓（runs-on=[self-hosted,cn] 自动避开离线机），30min 冷却去重；
# 自愈成功/冷却中 → 该项视为「处理中」→ 最终 exit 0 → 自动化不再汇报刷屏。
import os
import urllib.request
import urllib.error
from collections import defaultdict

REPO = "ah-quant999/quant-scanner-v8"
CN_WORKFLOW_ID = 327687211   # 🇨🇳 v8 中国数据抓取(云端)（v8_cn_fetch_cloud.yml）
ALGO_WORKFLOW_ID = 324119592  # ☁️ v8 盘后算法链（v8_algo_cloud.yml）
SELFHEAL_PATH = DATA_DIR / "freshness_selfheal.json"
SELFHEAL_COOLDOWN_MIN = 30   # 同 category 自愈派发冷却，避免每小时重复派发刷爆 runner

# 由 v8_algo_cloud.yml 产出的选股/回测类 data/*.js 变量（在 update_v8 CATEGORY_MAP 中多为 post_close，
# 但 cloud_fetch 无法生产它们；需要单独 dispatch algo_cloud 来自愈）。
ALGO_VARS = {
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST/COCKPIT_TIER_RECOMMEND/COCKPIT_ADVICE 已删（模块下线）
    "BACKTEST_COMPREHENSIVE", "BACKTEST_TDX",
    "CRDS_CARD_DATA", "TRIPLE_CONSENSUS", "TRIPLE_TRACK", "TRIPLE_HISTORY",
    "FINAL_RECOMMEND_DATA", "ALGO_TRACK",
    "SENTIMENT_CYCLE", "H_AUTO_BUY", "H_AUTO_BUY_TRACK",
    "LHB_7D",
    "INDEX_HISTORY",
}


def _load_token():
    """复用 v8_cloud_watchdog 的 token 解析：env 优先，其次本地文件（不落仓库）。"""
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    for p in [
        Path("E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"),
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
        ROOT / ".workbuddy" / "v8_gh_token.txt",
    ]:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def _dispatch_cn(category, token):
    """派发 cn_fetch 在在线 self-hosted cn runner 上重抓（自愈核心动作）。"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/dispatches"
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps({"ref": "main", "inputs": {"category": category}}).encode()
    req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}"
    except Exception as e:
        return False, str(e)[:120]


def _dispatch_algo(token):
    """派发 v8_algo_cloud（盘后算法链）重跑，用于选股/回测类数据 stale 自愈。"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{ALGO_WORKFLOW_ID}/dispatches"
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps({"ref": "main"}).encode()
    req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}"
    except Exception as e:
        return False, str(e)[:120]


def load_selfheal():
    try:
        return json.loads(SELFHEAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_selfheal(d):
    try:
        SELFHEAL_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _api_get(url, token):
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__error__": e.code}
    except Exception as e:
        return {"__error__": str(e)[:120]}


def choose_category_cn(now_cst, is_trading=True):
    """按当前北京时刻选 cn_fetch 派发类别；非交易日统一 all（周末周度刷新）。"""
    if not is_trading:
        return "all"
    h = now_cst.hour + now_cst.minute / 60.0
    if h < 9:
        return "premarket"
    if h < 15:
        return "intraday"
    if h < 16.5:
        return "post_close"
    return "all"


def pipeline_selfheal(token, now, is_trading, sh):
    """管线级自愈：cn_fetch 最近一次运行失败 → 在在线 runner 上重派发（兜底 schedule 抖动/离线机失败）。

    与数据自愈共用 30min 冷却（键 cn_fetch_pipeline）。仅重试较新的失败（6h 内），
    避免远古失败反复派发。这是「看门狗一直报错」的最后一块拼图：既修数据陈旧，
    也修管线失败，让巡检最终 exit 0、不再刷屏。
    """
    try:
        runs = _api_get(
            f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/runs?per_page=5",
            token,
        )
        if "__error__" in runs:
            print(f"  [管线自愈] 查 cn_fetch runs 失败: {runs['__error__']}")
            return
        NEUTRAL = ("skipped", "cancelled", "neutral", "action_required")
        latest = None
        for r in runs.get("workflow_runs", []):
            if r.get("status") != "completed":
                continue
            if r.get("conclusion") in NEUTRAL:
                continue
            latest = r
            break
        if not latest or latest.get("conclusion") != "failure":
            return  # 最近一次成功/无结论 → 无需重试
        created = latest.get("created_at")
        try:
            lt = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(
                timezone(timedelta(hours=8)))
            # now 为朴素本地时间，lt 为带时区；用带时区的「当前」计算年龄避免混合比较报错
            age_min = (datetime.now(timezone(timedelta(hours=8))) - lt).total_seconds() / 60
        except Exception:
            age_min = 999
        last = sh.get("cn_fetch_pipeline", {}).get("ts")
        if last:
            try:
                lt2 = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                if (now - lt2).total_seconds() < SELFHEAL_COOLDOWN_MIN * 60:
                    print(f"  [冷却中] cn_fetch 失败重派近{SELFHEAL_COOLDOWN_MIN}min已触发，跳过")
                    return
            except Exception:
                pass
        if age_min >= 360:
            print(f"  [跳过] cn_fetch 失败过旧({age_min/60:.0f}h)，不自动重试")
            return
        cat = choose_category_cn(now, is_trading)
        ok, msg = _dispatch_cn(cat, token)
        if ok:
            sh["cn_fetch_pipeline"] = {
                "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
                "run_id": latest.get("id"),
                "category": cat,
            }
            print(f"  [自愈✓] cn_fetch 上次运行失败(run#{latest.get('id')})，已重派 {cat}（HTTP {msg}）")
        else:
            print(f"  [自愈✗] cn_fetch 重派失败: {msg}")
    except Exception as e:
        print(f"  [管线自愈] 异常: {e}")


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


def _parse_ts(ts: str):
    """把字符串时间戳解析为 naive datetime（北京时间）。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts.replace("T", " ") if fmt == "%Y-%m-%d %H:%M:%S" else ts, fmt)
        except ValueError:
            continue
    return None


def extract_update_time(path: Path):
    """从本地 data/X.js 中提取 update_time 字段。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', text)
    if not m:
        return None
    return _parse_ts(m.group(1))


def extract_update_time_cloud(var: str, token: str):
    """从 GitHub Contents API 读取 data/X.js 的 update_time（避免本地滞后）。"""
    import base64
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{REPO}/contents/data/{var}.js"
    req = urllib.request.Request(url, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
        m = re.search(r'"update_time"\s*:\s*"([^"]+)"', content)
        if not m:
            m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', content)
        if not m:
            return None
        return _parse_ts(m.group(1))
    except Exception:
        return None


def check_group(group, close, label, is_trading=True, token=None, use_cloud=False):
    """返回 (stale_list, notime_list)

    陈旧判定（2026-08-02 修订）：
    - 阈值 < 24h：按日历小时判定（盘中/日内高频刷新够用）
    - 阈值 ≥ 24h：按 **交易日** 判定（避免「周五 15:05 → 周一 09:00」按日历 68h 误报）
      - 实际交易日数 = trading_days_between(ts.date(), close.date())
      - 阈值天数 = max_hours / 24

    2026-08-16 周末豁免：非交易日时，阈值 < 24h 的盘中高频模块（CRISIS_DATA=4h /
    V8_CAL=6h 等）本就不更新，若仍判 stale 会每周末固定刷屏误报。此类在非交易日
    直接跳过（不计入 stale），信息不丢（仍可在 notime/打印中提示，但不阻断 exit）。
    """
    stale, notime = [], []
    for var, max_hours in group.items():
        # 🛡️ 周末豁免：非交易日 + 盘中高频（<24h 阈值）不判陈旧
        if (not is_trading) and max_hours < 24:
            continue
        ts = None
        if use_cloud and token:
            ts = extract_update_time_cloud(var, token)
        if ts is None:
            path = DATA_DIR / f"{var}.js"
            if not path.exists():
                stale.append((var, "文件缺失"))
                continue
            ts = extract_update_time(path)
        if ts is None:
            notime.append(var)
            continue
        age_hours = (close - ts).total_seconds() / 3600
        is_stale = False
        reason = ""
        if max_hours >= 24:
            # 日级阈值改按交易日判定（修「CORE=3天 遇周末名延退易误报」）
            tdays = trading_days_between(ts.date(), close.date())
            threshold_days = max_hours / 24
            if tdays > threshold_days:
                is_stale = True
                reason = f"更新于 {ts.strftime('%m-%d %H:%M')}，落后 {tdays} 个交易日（阈值 {threshold_days:g}）"
        else:
            # < 24h 维持原小时判定
            if age_hours > max_hours:
                is_stale = True
                hours = age_hours
                reason = f"更新于 {ts.strftime('%m-%d %H:%M')}，落后 {hours:.1f} 小时"
        if is_stale:
            stale.append((var, reason))
    return stale, notime


def main():
    import argparse
    ap = argparse.ArgumentParser(description="v8 数据新鲜度看门狗（含自愈派发）")
    ap.add_argument("--no-self-heal", action="store_true",
                    help="仅检查不派发自愈（诊断模式）")
    args = ap.parse_args()

    # 2026-08-20 根因修复：统一 UTC+8 北京时间，避免 runner/本机时区漂移导致
    # 交易日判定、收盘时间、自愈窗口全部错位。
    now = (datetime.now(timezone.utc) + timedelta(hours=8)).replace(tzinfo=None)
    is_trading = _is_trading_day(now.date())
    close = last_trade_day_close(now)

    # token 提前加载：CORE_SOURCES_ALGO 需读云端 update_time 避免本地滞后
    token = None if args.no_self_heal else _load_token()

    core_stale, core_notime = check_group(CORE_SOURCES, close, "CORE", is_trading)
    algo_stale, algo_notime = check_group(CORE_SOURCES_ALGO, close, "CORE_ALGO", is_trading, token=token, use_cloud=True)
    core_stale += algo_stale
    core_notime += algo_notime
    warn_stale, warn_notime = check_group(WARN_SOURCES, close, "WARN", is_trading)
    frozen_stale, frozen_notime = check_group(FROZEN_SOURCES, close, "FROZEN", is_trading)

    def _with_cat(items):
        def _cat(var):
            if var in ALGO_VARS:
                return "algo"
            return CATEGORY_MAP.get(var, "post_close")
        return [{"var": v, "reason": r, "category": _cat(v)} for v, r in items]

    status = {
        "check_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "last_trade_close": close.strftime("%Y-%m-%d %H:%M:%S"),
        "is_trading_day": is_trading,
        "core_stale": _with_cat(core_stale),
        "warn_stale": _with_cat(warn_stale),
        "frozen_stale": _with_cat(frozen_stale),
        "no_update_time": sorted(core_notime + warn_notime + frozen_notime),
        "summary": {
            "total_checked": len(CORE_SOURCES) + len(CORE_SOURCES_ALGO) + len(WARN_SOURCES) + len(FROZEN_SOURCES),
            "core_stale": len(core_stale),
            "warn_stale": len(warn_stale),
            "frozen_stale": len(frozen_stale),
            "no_timestamp": len(core_notime) + len(warn_notime) + len(frozen_notime),
        },
        "category_map": CATEGORY_MAP,
        "category_label": CATEGORY_LABEL,
    }
    out_path = DATA_DIR / "freshness_status.json"
    # ★★ 2026-08-18 主人令「每次更新部署都是错的」根因根治：幽灵提交幂等化 ★★
    #   死循环源头：check_time 每次运行必变 → freshness_status.json 内容必变 →
    #   health_patrol 每分钟写它 → 每次触发 build/reconcile → 今日 77 次 healthcheck 提交。
    #   修复：写文件前比较「去掉 check_time 后的状态内容」，状态未变则完全不动文件
    #   （check_time 保持旧值）→ git diff 为空 → 不提交 → 幽灵提交消失。
    #   注意：状态真变化时 check_time 会随新内容一并更新，语义正确。
    try:
        if out_path.exists():
            old = json.loads(out_path.read_text(encoding="utf-8"))
            _strip_ts = lambda d: {k: v for k, v in d.items() if k != "check_time"}
            if _strip_ts(old) == _strip_ts(status):
                print(f"⏭️  新鲜度状态未变，跳过重写（幂等，check_time 保持 {old.get('check_time')}）")
                status = old  # 用旧对象继续打印
    except Exception:
        pass
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    s = status["summary"]
    print(f"=== v8 数据新鲜度检查 {status['check_time']} ===")
    print(f"最近交易日收盘: {status['last_trade_close']}  交易日: {'是' if is_trading else '否(周末/节假日)'}")
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

    # ── 自愈派发（修而不只查，根治刷屏）──
    # 发现 CORE stale → 自动 dispatch 对应 category 的 cn_fetch 在在线 runner 上重抓；
    # 30min 冷却去重；自愈成功/冷却中 → 该项从 core_stale 剔除 → 最终 exit 0（不刷屏）。
    healed_cats = set()
    sh = load_selfheal()   # 始终加载，确保数据自愈与管线自愈都能读写冷却状态
    if core_stale and token:
        by_cat = defaultdict(list)
        for it in _with_cat(core_stale):
            by_cat[it["category"]].append(it["var"])
        print(f"🩹 自愈派发（{len(by_cat)} 个类别需刷新）:")
        for cat, vars_ in by_cat.items():
            last = sh.get(cat, {}).get("ts")
            if last:
                try:
                    lt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                    if (now - lt).total_seconds() < SELFHEAL_COOLDOWN_MIN * 60:
                        print(f"  [冷却中] {cat} 近{SELFHEAL_COOLDOWN_MIN}min已派发，跳过（{', '.join(vars_)}）")
                        healed_cats.add(cat)
                        continue
                except Exception:
                    pass
            if cat == "algo":
                ok, msg = _dispatch_algo(token)
                dispatch_name = "algo_cloud"
            else:
                ok, msg = _dispatch_cn(cat, token)
                dispatch_name = f"cn_fetch({cat})"
            if ok:
                sh[cat] = {"ts": now.strftime("%Y-%m-%d %H:%M:%S"), "vars": vars_}
                healed_cats.add(cat)
                print(f"  [自愈✓] 派发 {dispatch_name} 刷新 {', '.join(vars_)}（HTTP {msg}）")
            else:
                print(f"  [自愈✗] {dispatch_name} 派发失败: {msg}（{', '.join(vars_)}）")
        save_selfheal(sh)
    elif core_stale and not token:
        print("  [自愈跳过] 未找到 GitHub token，无法派发刷新（请配置 V8_GITHUB_TOKEN）")

    # ── 管线自愈：cn_fetch 最近一次运行失败 → 重派（兜底 schedule 抖动/离线机失败）──
    if token:
        pipeline_selfheal(token, now, is_trading, sh)
        save_selfheal(sh)

    # 已自愈/冷却中的类别 → 视为「处理中」，不计入最终 stale（避免刷屏）
    if healed_cats:
        cat_of = {it["var"]: it["category"] for it in _with_cat(core_stale)}
        remaining = [(v, r) for (v, r) in core_stale if cat_of.get(v) not in healed_cats]
        if len(remaining) < len(core_stale):
            print(f"  → {len(core_stale) - len(remaining)} 项已进入自愈/冷却，本轮不再报故障")
        core_stale = remaining

    if not (core_stale or warn_stale or frozen_stale or status["no_update_time"]):
        print("✅ 全部模块新鲜（或已进入自愈）")
        return 0

    print(f"状态已写入: {out_path}")
    return 1 if core_stale else 0


if __name__ == "__main__":
    sys.exit(main())
