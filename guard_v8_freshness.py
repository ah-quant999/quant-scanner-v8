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

import json, re, sys, time, http.client
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# ── 2026-09-20 读超时加固（阿狸咪 09-19_2345 §三；小九落码）──────────────
# 根因：urllib 的 `timeout=` 只约束**单次 recv**；对端保持连接却不再送字节时
#       `r.read()` 可无限等待 ⇒ 单次卡住即整轮挂死（家机实测连续 7 次，零输出）。
# 三条加固：① 整体读超时（分块读 + 截止时间）② IncompleteRead/SSLError 退避重试
#           ③ 进度打印 + 总时限（即使再挂死，调用方也能拿到「检到第几项」）
# 安全边界：超时/重试耗尽一律 `return None` ⇒ 走**现有**回退（本机文件 + 明确
#           reason），与旧行为完全一致；不新增任何派发路径、不改阈值。
_READ_DEADLINE_SEC = 20      # 单次 HTTP 响应体的整体读超时（旧 timeout=30 只管单次 recv）
_RETRY_TIMES = 2             # IncompleteRead / SSLError 退避重试次数
_RETRY_BACKOFF = (0.8, 1.6)  # 退避秒数
_MAIN_TOTAL_SEC = 150        # main() 总时限（超时带已检结果退出，不静默挂死）


def _read_all_deadline(resp, deadline_sec=_READ_DEADLINE_SEC):
    """带**整体截止时间**的响应体读取（治本）。

    替代 `resp.read()`：后者在「对端保持连接但不再送字节」时可无限等待。
    返回 bytes；超时/异常返回 None（调用方回退到现有逻辑）。
    """
    end = time.monotonic() + deadline_sec
    chunks = []
    while True:
        remain = end - time.monotonic()
        if remain <= 0:
            return None
        try:
            resp.fp.raw._sock.settimeout(min(remain, 5.0))
        except Exception:
            try:
                resp.fp.raw.settimeout(min(remain, 5.0))
            except Exception:
                pass
        try:
            chunk = resp.read(65536)
        except (TimeoutError, OSError):
            continue
        if not chunk:
            break
        chunks.append(chunk)
        if len(chunk) < 65536:
            # 小包通常意味着已读完；但保险起见再看一次
            if time.monotonic() >= end:
                break
    return b"".join(chunks) if chunks else b""


def _fetch_json(url, hdr, deadline_sec=_READ_DEADLINE_SEC, retries=_RETRY_TIMES):
    """GET url → 解析 JSON。带整体读超时 + 退避重试（加固 ①②）。

    返回 (obj, err)；obj 为 None 时 err 载明原因（供日志）。
    """
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=deadline_sec) as r:
                raw = _read_all_deadline(r, deadline_sec)
            if raw is None:
                last = "read-timeout(%ds)" % deadline_sec
            elif not raw:
                last = "empty-body"
            else:
                return json.loads(raw.decode("utf-8")), None
        except http.client.IncompleteRead as e:
            last = "IncompleteRead(partial=%d)" % len(getattr(e, "partial", b"") or b"")
        except (TimeoutError, OSError) as e:
            last = "%s: %s" % (type(e).__name__, str(e)[:60])
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, str(e)[:60])
        if attempt < retries:
            time.sleep(_RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)])
    return None, last

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


def _is_market_open(now) -> bool:
    """判断当前是否处于 A 股连续竞价时段（09:30-11:30 / 13:00-15:00，北京时间）。
    盘前(09:00-09:30)/午休(11:30-13:00)/盘后(15:00-16:30)及非交易日，STOCK_QUOTE 本就不刷新，
    不应判陈旧、也不应自愈派发（避免收盘后误报风暴 + 冗余派发）。"""
    if not _is_trading_day(now.date()):
        return False
    hm = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= hm <= 11 * 60 + 30) or (13 * 60 <= hm <= 15 * 60)


def _is_premarket_window(now, minutes_before_open: int = 180) -> bool:
    """盘前窗口：开盘前 N 分钟内（默认 180min，即 06:30-09:30）。用于 NT_DATA 等
    盘前不跑的模块豁免陈旧判定，避免清晨误报。"""
    if not _is_trading_day(now.date()):
        return False
    hm = now.hour * 60 + now.minute
    open_min = 9 * 60 + 30
    return open_min - minutes_before_open <= hm < open_min


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
    "CANDIDATE_QUOTES": 35,   # 🔴 2026-09-09 盘中更新审计：候选池纳入 CORE（阈值 35min，盘中每20分刷新留冗余）；非交易时段由下方 _is_market_open 过滤豁免
    "ETF_PULSE": 26,
    # 🛡 2026-09-11 主人令（卡迁移）：ETF_DAILY_MONITOR（「日监控·主力净流入」）已由「实时数据」
    #   页迁至「盘后数据」页，但**数据节拍未变**——仍是盘中每 30 分链刷新（T+0 字段）。
    #   故本护栏继续按盘中 CORE 26min 看守，不要因为「页面搬到盘后数据」就把它挪进盘后清单，
    #   否则盘中该卡静默停更将无人报警（本次迁页的算法侧对齐点之一）。
    "ETF_DAILY_MONITOR": 26,
    # 🛡 2026-09-08 盘中更新审计·一劳永逸：STOCK_QUOTE 此前不在任何监控清单，
    # 且 guard 自愈只派发 cn_fetch/algo、无 STOCK_QUOTE 通道 → 反复陈旧只能用户肉眼发现。
    # 现纳入 CORE（阈值 35min，非交易日按 check_group 周末豁免自动跳过），并以专属通道
    # 派发 v8_stock_quote_refresh.yml（云端 ubuntu-latest）自愈，不再依赖哨兵单点。
    "STOCK_QUOTE": 35,
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
    "CAPITAL_FLOW_DATA": 26,
    "MARKET_FUND_FLOW_DATA": 26,
    # 🧹 2026-09-16 阿狸咪的工程师：ANALYST_RATINGS **已退役摘除**（原阈值 72）。
    #    依据（三处独立取证，双机复核）：① 前端零引用 —— index.html L565/590 仅存注释
    #    「2026-08-31 轻量化：data/ANALYST_RATINGS.js（3.5 KB）前端零引用，停止注入」；
    #    ② 生产者已断 —— update_v8.py L90/L201 的转换映射于 09-11 被小九按「死数据清理·P1」
    #    注释移除 ⇒ `data/ANALYST_RATINGS.js` **结构上永不生成**；③ 远端 `data/` 无该文件。
    #    ⇒ 留在本表则每轮巡检必报 🟡「文件缺失」，属**结构性恒黄灯**：它永远无法转绿，
    #    只会稀释真红的信噪比（与 09-14 LHB_7D、09-04 COCKPIT_* 同族病，同法处置）。
    #    ⚠️ 回滚：从 08-31 及更早提交取回 data/ANALYST_RATINGS.js，恢复 update_v8.py 两处
    #    映射（L90 / L201），并把本条阈值 72 加回本表。
    #    🔴 遗留（另立待办，不在本表职责面内）：`cloud_fetch_v8.py` L76/L108/L3802 **仍在
    #    盘前 08:25 拉取** `raw_data/analyst_ratings.json`（远端该 raw 确实存在）⇒ 该 raw
    #    **无消费方 = 纯死拉取**（浪费云端每轮盘前配额），宜随本轮退役一并摘除；本轮未动
    #    该主抓取脚本（避免在监巡轮次碰数据管线）。
    # "ANALYST_RATINGS": 72,
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
    # 🛡 2026-09-14 阿狸咪的工程师（双机独立复核后裁定）：LHB_7D 已从本组**移出**。
    #    → 09-15 小九的工程师进一步**退役删除**（data/LHB_7D.js 已不存在，见下方 FROZEN_SOURCES 注释）。
    #    根因：唯一生产者 gen_lhb_7d.py 于 09-13 主动停跑（run_algorithms.py 摘除调度 + 注释调用），
    #    前端零引用（index.html L565 注明「停止注入」）、raw 无消费方 ⇒ **它已无生产者**。
    #    留在本组（+ ALGO_VARS）的后果：每 30min 必判红 → 必自愈派 algo_cloud，而结构上
    #    永远治不好 ⇒ 无限红灯 + 空跑 run 抢同并发组（本机 listener 与云端 health_patrol
    #    两处 guard 各判各的 ⇒ 双源抢派，同 INDEX_HISTORY 型）。
    #    ⚠️ 若日后回滚 gen_lhb_7d.py 调度，请把它一并挪回本组（阈值 24）。
    # INDEX_HISTORY（5年上证K线）由 19:15 算法链产出，纳入 CORE 监控/自愈。
    "INDEX_HISTORY": 48,
}

# ── 分类三：无云端生产者的冻结快照 ────────────────────────────────────
# 当前暂无。保留空 dict，便于未来新增模块时快速标记。
FROZEN_SOURCES = {
    # 🧹 2026-09-15 小九的工程师：LHB_7D 已**退役删除**（data/LHB_7D.js 不复存在），
    #    故从本表摘除 —— 否则 check_group 会走到 line 501 的 `if not path.exists()`
    #    产出「文件缺失」，把刚消掉的红灯换个名字放回来。
    #    退役依据：唯一生产者 gen_lhb_7d.py 于 09-13 停跑（run_algorithms.py 摘调度）、
    #    前端零引用（index.html「停止注入」）、raw 无消费方 ⇒ 无生产者亦无消费者。
    #    回滚：从 09-14 及更早的提交取回 data/LHB_7D.js，并把本条与
    #    run_algorithms.py 的 step_gen_lhb_7d 一并恢复。
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
# 🔴 2026-09-17 阿狸咪的工程师·口径纠正（判据 92「注释与实体错配」）：
#   本行原注「云端 ubuntu-latest」与**实体相反** —— 336548691 的官方档案 path =
#   .github/workflows/v8_stock_quote_refresh.yml，其 job 已于 2026-09-08 主人令回迁
#   runs-on=[self-hosted, cn]（小九单位机·中国 IP，绕开美国 IP 盘中反爬）。
#   ⇒ 本常量派发的是**主链（小九单位机）**：小九机离线时该 run 只会**排队**，不会
#     自动改派云端；离线兜底由哨兵 v3 派发 v8_stock_quote_refresh_cloud.yml 承担
#     （仓内另有 1 处派发点：v8_cn_fetch_cloud.yml relay ②，同样指向该兜底链）。
STOCK_QUOTE_WORKFLOW_ID = 336548691
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
    # LHB_7D 已移出（2026-09-14 阿狸咪的工程师）：无生产者，不再属 algo_cloud 自愈面，
    #   详见上方 CORE_SOURCES_ALGO 段注释。
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


def _algo_active_run(token, lookback_min=180):
    """查 v8_algo_cloud 是否**已有活跃/排队 run** —— 有则不再重复派发（先查再派）。

    🛡 2026-09-15（阿狸咪的工程师，第 412 轮实证）：19:27 派发的算法链仍在跑（step 12/17，
    已 2h20m+），而 30min 冷却一到 guard 又派一发 ⇒ 新 run 只能 `pending` **排在链条之后**
    （同 concurrency 组），链条跑完再空转跳过（step 8 闸门判「批次已完成」→ 秒退）。
    这正是 algo_cloud「周期性空转 + 抢同并发组」的机制缺口（与 FROZEN 组漏判并列）。
    与 `.github/scripts/cloud_dispatcher.py` 的 latest_run/dispatch_guard 同口径：**先查再派**。
    lookback_min 内的活跃 run 才算「正在处理」；更老的活跃 run 视为僵尸（仍派发，交给看门狗清理）。

    返回 (run_id, status, created_cst_str) 或 None（无活跃 run / 查询失败）。
    """
    url = (f"https://api.github.com/repos/{REPO}/actions/workflows/"
           f"{ALGO_WORKFLOW_ID}/runs?per_page=10")
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        req = urllib.request.Request(url, headers=hdr, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None   # 查询失败 → 不阻断派发（宁可多派一次，不可漏治）
    ACTIVE = ("in_progress", "queued", "pending", "requested", "waiting")
    now_utc = datetime.now(timezone.utc)
    for run in data.get("workflow_runs", []):
        if run.get("status") not in ACTIVE:
            continue
        try:
            created = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except Exception:
            continue
        if (now_utc - created).total_seconds() / 60.0 > lookback_min:
            continue   # 僵尸活跃 run：不据此跳过（由 cloud_dispatcher 看门狗清理）
        cst = (created + timedelta(hours=8)).strftime("%H:%M")
        return (run.get("id"), run.get("status"), cst)
    return None


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


def _dispatch_stock_quote(token):
    """派发 v8_stock_quote_refresh.yml（主链 · [self-hosted, cn] 小九单位机）重抓个股行情，
    用于 STOCK_QUOTE stale 自愈。小九机离线时本 run 仅排队，离线兜底见哨兵 v3。"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{STOCK_QUOTE_WORKFLOW_ID}/dispatches"
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


def _heal_stock_quote(token, sh, now, items):
    """STOCK_QUOTE 专属自愈：30min 冷却去重 + 派发 v8_stock_quote_refresh.yml（主链 self-hosted）。"""
    last = sh.get("stock_quote", {}).get("ts")
    if last:
        try:
            lt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
            if (now - lt).total_seconds() < SELFHEAL_COOLDOWN_MIN * 60:
                print(f"  [冷却中] stock_quote 近{SELFHEAL_COOLDOWN_MIN}min已派发，跳过（{', '.join(v for v, _ in items)}）")
                return True
        except Exception:
            pass
    ok, msg = _dispatch_stock_quote(token)
    if ok:
        sh["stock_quote"] = {"ts": now.strftime("%Y-%m-%d %H:%M:%S"), "vars": [v for v, _ in items]}
        print(f"  [自愈✓] 派发 stock_quote(主链 self-hosted) 刷新 {', '.join(v for v, _ in items)}（HTTP {msg}）")
        return True
    else:
        print(f"  [自愈✗] stock_quote 派发失败: {msg}（{', '.join(v for v, _ in items)}）")
        return False


def load_selfheal():
    try:
        return json.loads(SELFHEAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_selfheal(d):
    try:
        # 🔴 2026-09-20 行尾防回潮（与 v8_runner_guard.write_heartbeat 同案）：
        #   本文件落在 `data/*.json  eol=lf` 覆盖内，且经 Contents API 直传（绕过 clean 过滤器）。
        #   原 `write_text(...)` 在 Windows 下 newline=None ⇒ "\n" 落盘成 CRLF ⇒ 远端 blob 带 CR。
        #   当前 blob 实测 CR=0（519 B），属潜伏项，此处显式 newline="\n" 断根。
        with open(SELFHEAL_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=2))
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
    """从 GitHub Contents API 读取 data/X.js 的 update_time（避免本地滞后）。

    2026-09-16 治本（两处，均为「假红」根因）：

    ① **>1MB 文件回退 blob API**：Contents API 对 >1MB 的文件只给 `sha`、`content`
       为空串（本仓 `STOCK_QUOTE.js` 3.28MB）。旧实现解出空串 ⇒ 正则不中 ⇒ 返回
       None ⇒ 调用方回退读**本机**文件 ⇒ 「本机陈旧 + 远端新鲜」的模块继续假红。
       实测：本轮 `STOCK_QUOTE` 判「更新于 09-11 15:02 落后 3 个交易日」，云复核为
       **远端 09-16 10:52:06（盘中最新）** ⇒ 假红还连带一次冗余自愈派发。
       现 content 为空时改走 `git/blobs/<sha>`（支持至 100MB）。

    ② 该函数被 `use_cloud=True` 的调用方使用；CORE 组见 check_group 调用处。
    """
    import base64
    hdr = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{REPO}"
    # 2026-09-20 加固：改用 _fetch_json（整体读超时 + 退避重试），
    # 替代原先裸 urlopen(...).read()（无整体超时 ⇒ 可无限挂起）。
    try:
        meta, err = _fetch_json(f"{base}/contents/data/{var}.js", hdr)
        if meta is None:
            print(f"    [cloud✗] {var}: {err}（回退本机文件）")
            return None
        content = meta.get("content") or ""
        if not content.strip():
            # >1MB：Contents API 不返回 content，只给 sha ⇒ 取 blob
            sha = meta.get("sha")
            if not sha:
                return None
            blob, err2 = _fetch_json(f"{base}/git/blobs/{sha}", hdr, deadline_sec=30)
            if blob is None:
                print(f"    [cloud✗] {var}(blob): {err2}（回退本机文件）")
                return None
            content = blob.get("content") or ""
        text = base64.b64decode(content).decode("utf-8", errors="ignore")
        m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
        if not m:
            m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', text)
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
    _items = list(group.items())
    _n = len(_items)
    for _i, (var, max_hours) in enumerate(_items, 1):
        # 🛡️ 2026-09-20 加固③：进度打印 —— 若整轮仍挂死，调用方能看到「检到第几项」
        if use_cloud and token:
            print(f"  [{label} {_i}/{_n}] {var}", flush=True)
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

    # 🛡️ 2026-09-20 加固③：总时限。超时后**带已检结果**退出（exit 2），
    # 而不是让调用方只看到「timed out」而不知检到第几项（旧痛点）。
    _t0 = time.monotonic()

    def _over_budget():
        if time.monotonic() - _t0 > _MAIN_TOTAL_SEC:
            print(f"⏰ 总时限 {_MAIN_TOTAL_SEC}s 已到，提前结束（已检部分结果可信）")
            return True
        return False

    # token 提前加载：CORE_SOURCES_ALGO 需读云端 update_time 避免本地滞后
    # 🔴 2026-09-16 治本（阿狸咪的工程师）：原实现把「是否派发」与「能否云复核」
    #    耦合在同一个 token 上，而 `--no-self-heal` **在全脚本其它任何地方都未被引用**
    #    （grep 仅 argparse 定义 + 本行）⇒ 所谓「不派发」完全是靠 token=None 让
    #    dispatch_* 报「未找到 GitHub token」这一**副作用**兜出来的。
    #    后果：诊断模式连带关掉云复核 ⇒ CORE/CORE_ALGO 退回读**本机** data/X.js
    #    （本机经坚果云同步、远端 CI 推的新数据不落地）⇒ **假红**。
    #    同机同一时刻实测（2026-09-16 15:4x）：正常跑 CORE 红 **4** 个；
    #    `--no-self-heal` 红 **16** 个，多出的 12 个纯由 token=None 造成
    #    ⇒ 违背该开关自己的契约「仅检查不派发」，会误导排查方向。
    #    修法：**云复核与派发脱钩** —— 另取 `check_token` 专供 check_group；
    #    `token` 仍按原样（诊断时为 None）⇒ **不触碰任何派发路径，零新增派发风险**。
    token = None if args.no_self_heal else _load_token()
    check_token = _load_token()      # 只读云复核用；_load_token 取不到时返回 None（不抛）

    # 🔴 2026-09-16 治本：CORE 组原先**未传 token/use_cloud** ⇒ 一律读本机 data/X.js。
    # 本机经坚果云同步、远端 CI 推的新数据不落地 ⇒ 本机陈旧即**假红**（本轮实测
    # STOCK_QUOTE：本机 09-11 15:02 vs 远端 09-16 10:52）⇒ 连带冗余自愈派发。
    # CORE_ALGO 组早已 use_cloud=True（见下一行），此处补齐保持一致。
    core_stale, core_notime = check_group(CORE_SOURCES, close, "CORE", is_trading, token=check_token, use_cloud=True)
    algo_stale, algo_notime = check_group(CORE_SOURCES_ALGO, close, "CORE_ALGO", is_trading, token=check_token, use_cloud=True)
    core_stale += algo_stale
    core_notime += algo_notime
    if _over_budget():
        print(f"  已检 CORE={len(core_stale)} 陈旧 / {len(core_notime)} 无时间戳；"
              f"WARN/FROZEN 未检（总时限）")
        return 2
    # 🛡 2026-09-08 盘中更新审计：STOCK_QUOTE 仅连续竞价时段(09:30-11:30/13:00-15:00)才刷新，
    # 盘前/午休/盘后及非交易日本就冻结 → 仅交易时段判定陈旧，避免收盘后误报 + 冗余自愈派发。
    if not _is_market_open(now):
        core_stale = [(v, r) for (v, r) in core_stale if v != "STOCK_QUOTE"]
        core_notime = [v for v in core_notime if v != "STOCK_QUOTE"]
    # 🔴 2026-09-17 治本（阿狸咪，与 09-16 CORE/CORE_ALGO 同源）：WARN/FROZEN 原先
    # **未传 token/use_cloud** ⇒ 一律读本机 data/X.js。本机经坚果云同步、远端 CI 推的
    # 新数据不落地 ⇒ 本机滞后即**假黄灯**（09-17 实测：本机 SECTOR_FUND_FLOW 等 4 项
    # 09-16 18:5x，而远端同日 18:28~18:29 全新鲜；TRIPLE_HISTORY 本机 09-15 23:25 vs
    # 远端 09-17 05:23）⇒ 恒黄 5 项造成**告警疲劳**，真黄灯被淹没。
    # 传 token 后逐文件走云端读；**取不到仍回退本机**（check_group L580 内建兜底）
    # ⇒ 行为只增不减、零新增误报。
    warn_stale, warn_notime = check_group(WARN_SOURCES, close, "WARN", is_trading, token=check_token, use_cloud=True)
    # 🛡 2026-09-08 NT_DATA 盘前 180min 豁免：NT_DATA 是 ETF 实时异动，盘前本就不刷新，
    #    06:30-09:30 之间陈旧不告警、不派发，避免清晨误报。
    if _is_premarket_window(now, 180):
        warn_stale = [(v, r) for (v, r) in warn_stale if v != "NT_DATA"]
        warn_notime = [v for v in warn_notime if v != "NT_DATA"]
    if _over_budget():
        print(f"  已检 CORE={len(core_stale)} / WARN={len(warn_stale)}；FROZEN 未检（总时限）")
        return 2
    frozen_stale, frozen_notime = check_group(FROZEN_SOURCES, close, "FROZEN", is_trading, token=check_token, use_cloud=True)

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
    # 🛡 2026-09-08 盘中更新审计·一劳永逸：STOCK_QUOTE 走专属通道自愈（不进 cn_fetch 错派）
    sq_stale = [(v, r) for (v, r) in core_stale if v == "STOCK_QUOTE"]
    if sq_stale and token:
        _heal_stock_quote(token, sh, now, sq_stale)
        save_selfheal(sh)
        core_stale = [(v, r) for (v, r) in core_stale if v != "STOCK_QUOTE"]
    elif sq_stale and not token:
        print("  [自愈跳过] STOCK_QUOTE 陈旧但未找到 GitHub token，无法派发刷新")
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
                # 🛡 2026-09-15 先查再派：链条已在跑 ⇒ 不再堆第二发（防抢同并发组 + 空转）
                act = _algo_active_run(token)
                if act:
                    rid, st, cst = act
                    print(f"  [排队中] 算法链已有活跃 run #{rid}（{st}，{cst} 创建）"
                          f"⇒ 跳过重复派发，视为处理中（{', '.join(vars_)}）")
                    healed_cats.add(cat)
                    sh[cat] = {"ts": now.strftime("%Y-%m-%d %H:%M:%S"), "vars": vars_,
                               "note": f"skip: active run #{rid} ({st})"}
                    continue
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
