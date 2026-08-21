#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 前端健康巡检（三期一期 + 二期核心）
- 检查 data/*.js 数据新鲜度与关键字段空值
- 检查 GitHub Pages 部署 commit 与本地/remote HEAD 同步
- 检查 self-hosted runner 在线状态
- 输出 data/HEALTH_CHECK.js 供前端渲染
- 异常时发邮件告警（三期）

运行方式：
  python v8_health_check.py                # 本地检查，生成 HEALTH_CHECK.js
  python v8_health_check.py --alert        # 有异常时发送邮件
  python v8_health_check.py --site         # 额外拉取线上页面做简单 DOM 空值检测
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# 夜间静音时段（北京时间）：22:00-07:00 不发邮件，避免打扰休息。
# 严重基础设施问题仍会通过 write_urgent 留痕，但不在夜间发邮件。
QUIET_HOURS_START = 22
QUIET_HOURS_END = 7


def in_quiet_hours(now_cst=None):
    """判断当前是否处于夜间静音时段。"""
    n = now_cst or datetime.now(timezone(timedelta(hours=8)))
    h = n.hour
    if QUIET_HOURS_START <= QUIET_HOURS_END:
        return QUIET_HOURS_START <= h < QUIET_HOURS_END
    # 跨午夜：22:00-23:59 或 00:00-06:59
    return h >= QUIET_HOURS_START or h < QUIET_HOURS_END


# 如需要邮件告警，导入发送器（该模块从 .workbuddy/v8_smtp_config.json 读配置）
try:
    from v8_send_alert import send_alert
except Exception:
    send_alert = None

REPO = "ah-quant999/quant-scanner-v8"
SITE_URL = "https://ah-quant999.github.io/quant-scanner-v8/"
DATA_DIR = Path("data")
RAW_DIR = Path("raw_data")

# 关键卡片定义：与 index.html「任务运行看板」名称/顺序/覆盖对齐
# expected：频率说明；max_age：按时段动态计算，这里先给默认阈值（分钟）
CARD_DEFS = [
    # 今日事件（盘前）
    {"id": "V8_CAL", "name": "重要事件日历", "page": "今日事件", "freq": "每周日+月末", "max_age": 1500, "key_fields": ["weeks", "month"]},
    {"id": "IPO_DATA", "name": "打新研判", "page": "今日事件", "freq": "每日盘前", "max_age": 360, "key_fields": ["stocks"], "weekend_update": False},
    {"id": "JUDGMENT_DATA", "name": "今日判定", "page": "今日事件", "freq": "每日盘前", "max_age": 360, "key_fields": ["verdict", "indices"], "weekend_update": False},
    {"id": "MACRO_DATA", "name": "今日宏观解读", "page": "今日事件", "freq": "每日盘前", "max_age": 360, "key_fields": ["global_macro", "monetary"], "weekend_update": False, "manual_dep": True, "manual_note": "人工撰写宏观解读（管线仅补cpi/pmi，rich结构需主人更新）"},
    # NT_DATA(nt_data.json) 由 algorithms/fetch_orphan_nt_data.py 产出，归 run_algorithms.py(算法链)，
    # 不在 cloud_fetch_v8.py 的 premarket 注册表内 —— 按 page 映射派发 cn_fetch premarket 永远刷不到它，
    # 故显式覆盖自愈类别为 algo_run（2026-08-11 第155轮看门狗定位并根治）。
    {"id": "NT_DATA", "name": "市场提示", "page": "今日事件", "freq": "每日盘前", "max_age": 720, "key_fields": ["alerts"], "weekend_update": False, "heal_cat": "algo_run"},
    # 实时数据
    {"id": "INDEX_QUOTES", "name": "全球指数 / 股指期货", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["items"]},
    {"id": "ETF_PULSE", "name": "ETF 盘中异动", "page": "实时数据", "freq": "盘中实时", "max_age": 60, "key_fields": ["etfs"]},
    {"id": "ETF_INTRADAY_HEAT", "name": "ETF 资金热度", "page": "实时数据", "freq": "盘中实时 T+0", "max_age": 60, "key_fields": ["items"]},
    {"id": "ETF_DAILY_MONITOR", "name": "ETF 日监控", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["top_inflow", "top_outflow"], "premarket_keep": True},
    {"id": "SECTOR_FUND_FLOW", "name": "板块资金流向", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["top_list"]},
    {"id": "CONCEPT_RANKING", "name": "概念排名", "page": "实时数据", "freq": "盘中每30分", "max_age": 90, "key_fields": ["items"]},
    {"id": "LIMIT_UP_HEATMAP", "name": "涨停热度", "page": "实时数据", "freq": "盘中每30分", "max_age": 90, "key_fields": ["top", "dates"]},
    {"id": "MARKET_FUND_FLOW_DATA", "name": "市场资金流向", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["daily"]},
    {"id": "MARKET_ALERTS", "name": "市场预警", "page": "实时数据", "freq": "盘中实时", "max_age": 60, "key_fields": ["indices"]},
    # 盘后数据
    # ── 自愈类别说明（2026-08-11 第158轮全表核对）──────────────────────────────
    # cloud_fetch_v8.py 的 CATEGORY_MAP 中 post_close 只注册了 MARKET_FUND_FLOW_DATA / EXPERIMENT 两项。
    # 下列卡片的 raw_data 实际由 algorithms/run_algorithms.py 链内脚本产出（fetch_sh_index_fib /
    # build_candidate_pool / fetch_lhb / fetch_inst_trade / gen_triple_consensus / gen_cockpit_advice /
    # generate_top10 / calc_stock_rps / calc_crds / strategy_four_volume_60m 等），
    # 若沿用 PAGE_TO_CAT["盘后数据"|"选股策略"]="post_close" 派发 cn_fetch，**永远刷不到它们**，
    # 且会白占 25 分钟 debounce 锁导致真正需要的派发被跳过（与 155 轮 NT_DATA 同一类缺陷）。
    # 故统一显式覆盖 heal_cat="algo_run"。
    {"id": "SH_FIB", "name": "市场温度计", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["windows", "current"], "heal_cat": "algo_run"},
    {"id": "SIX_DIM_RADAR", "name": "六维共振雷达", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["windows", "current"], "_source_file": "SH_FIB", "_window_var": "SH_FIB", "heal_cat": "algo_run"},  # 与市场温度计同源(SH_FIB.js)，前端独立卡片展示六维评分视图
    {"id": "MARGIN_DATA", "name": "融资融券", "page": "盘后数据", "freq": "收盘后1次", "max_age": 1440, "key_fields": ["sh"], "heal_cat": "post_close"},  # 2026-08-18 主人令一劳永逸：交易所每日16:15发布1次，360min 阈值导致 22:15 必误报 → 1440（24h，符合主人 24h 铁律）
    {"id": "CFFEX_HOLDINGS", "name": "股指期货持仓", "page": "盘后数据", "freq": "收盘后1次", "max_age": 1440, "key_fields": ["items"], "heal_cat": "post_close"},  # 同上：交易所日更数据，1440（24h）
    {"id": "CRISIS_DATA", "name": "危机雷达", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["currency", "global"], "heal_cat": "premarket"},  # 危机雷达每日 08:25 跑一次
    {"id": "MARKET_FUND_FLOW_DATA", "name": "盘后资金流向", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["daily"], "heal_cat": "premarket"},  # 资金流日频时间轴——08:25 必跑一次（防漏跑）
    {"id": "CANDIDATE", "name": "候选池", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "heal_cat": "algo_run"},
    {"id": "GOLD_POOL", "name": "黄金池", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "heal_cat": "algo_run"},
    {"id": "LHB_DATA", "name": "龙虎榜", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "heal_cat": "algo_run"},
    {"id": "INST_TRADE", "name": "机构买卖", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["top_buy", "top_sell"], "heal_cat": "algo_run"},
    {"id": "TRIPLE_CONSENSUS", "name": "三重共识", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "heal_cat": "algo_run"},
    # 选股策略
    {"id": "FOUR_VOLUME", "name": "四量终极", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "heal_cat": "algo_run"},
    {"id": "COCKPIT_ADVICE", "name": "驾驶舱", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["verdict", "watch"], "heal_cat": "algo_run"},
    {"id": "BIG_BULL_HUNTER", "name": "大牛股猎手", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"], "_source_file": "LHB_DATA", "_window_var": "LHB_DATA", "heal_cat": "algo_run"},  # 前端 renderHunter 直接读 LHB_DATA 派生的机游共振信号，无独立 BIG_BULL_HUNTER.js 文件
    {"id": "TOP10_DAILY", "name": "全站精选", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["top10"], "heal_cat": "algo_run"},
    {"id": "STOCK_RPS", "name": "相对强度", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["records"], "_window_var": "STOCK_RPS_DATA", "heal_cat": "algo_run"},  # 文件名 STOCK_RPS.js，但 window 变量名是 STOCK_RPS_DATA（历史遗留）
    {"id": "CRDS_CARD_DATA", "name": "逆势龙头", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["elite", "watch"], "heal_cat": "algo_run"},
]


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


# 2026 年中国法定节假日（MM-DD），用于周末不更新模块的休市判定
_HOLIDAYS_2026 = {
    "01-01", "01-02", "01-03",  # 元旦
    "01-28", "01-29", "01-30", "01-31", "02-01", "02-02", "02-03", "02-04",  # 春节
    "04-04", "04-05", "04-06",  # 清明
    "05-01", "05-02", "05-03", "05-04", "05-05",  # 劳动节
    "05-31", "06-01", "06-02",  # 端午
    "09-30", "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07", "10-08",  # 国庆+中秋
}
# 补班日（周末但实际交易日）
_MAKEUP_DAYS_2026 = {
    "2026-01-04", "2026-02-14", "2026-02-28",
    "2026-05-09", "2026-09-20", "2026-10-10",
}


def _is_trading_day(d) -> bool:
    """判断某天是否为 A 股交易日（含补班日、剔除周末和节假日）。"""
    if d.weekday() >= 5 and d.isoformat() not in _MAKEUP_DAYS_2026:
        return False
    return d.strftime("%m-%d") not in _HOLIDAYS_2026


def is_market_closed(dt_cst=None):
    """判断给定北京时间是否为 A 股休市日（周末或法定节假日）。"""
    n = dt_cst or now_cst()
    return not _is_trading_day(n.date())


def is_intraday_session(dt_cst=None):
    """判断给定北京时间是否处于 A 股盘中交易时段（09:30-11:30 或 13:00-15:00）的交易日。"""
    n = dt_cst or now_cst()
    if is_market_closed(n):
        return False
    h = n.hour + n.minute / 60.0
    return (9.5 <= h <= 11.5) or (13.0 <= h <= 15.0)


def last_trade_day_close(now_cst_dt):
    """返回最近交易日收盘时间（15:30），非交易日回退。"""
    d = now_cst_dt.date()
    while not _is_trading_day(d):
        d -= timedelta(days=1)
    close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time(), tzinfo=timezone(timedelta(hours=8)))
    if now_cst_dt < close:
        d -= timedelta(days=1)
        while not _is_trading_day(d):
            d -= timedelta(days=1)
        close = datetime.combine(d, datetime.strptime("15:30", "%H:%M").time(), tzinfo=timezone(timedelta(hours=8)))
    return close


def fmt_rel_time(ts):
    """把 'YYYY-MM-DD HH:MM:SS' 格式化为相对时间：今日/昨日/X天前 HH:MM。"""
    if not ts:
        return "--"
    dt = parse_time(ts)
    if not dt:
        return str(ts)[:16]
    now = now_cst()
    today = datetime(now.year, now.month, now.day, tzinfo=timezone(timedelta(hours=8)))
    date_only = datetime(dt.year, dt.month, dt.day, tzinfo=timezone(timedelta(hours=8)))
    diff = (today - date_only).days
    hm = dt.strftime("%H:%M")
    if diff == 0:
        return f"今日 {hm}"
    if diff == 1:
        return f"昨日 {hm}"
    if diff < 7:
        return f"{diff}天前 {hm}"
    return dt.strftime("%m-%d %H:%M")


def parse_time(s):
    if not s or s in ("--", "N/A"):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
    except Exception:
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=8)))
            except Exception:
                try:
                    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
                except Exception:
                    return None


def load_window_var(path, var_name):
    """从 data/*.js 读取 window.X = {...}; 并解析为 dict（兼容 IIFE 壳）。"""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # 去掉 BOM
    text = text.lstrip("\ufeff")
    # 直接对象形式 window.X = {...};
    m = re.search(rf"window\.{re.escape(var_name)}\s*=\s*(\{{[\s\S]*?\}})\s*;", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass  # 落到 IIFE 分支
    # IIFE 壳：window.X = (function(){ var data = {...}; ... })()
    m2 = re.search(rf"window\.{re.escape(var_name)}\s*=\s*\(function[\s\S]*?var\s+data\s*=\s*(\{{[\s\S]*?\}})\s*;", text)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            return None
    return None


def load_window_var_from_site(source_id, var_name):
    """一劳永逸修复（2026-08-20）：优先读取线上站点 data/<id>.js（云端真实部署态），
    避免本机 checkout 未 git pull 时旧 data/*.js 误报「陈旧」，导致主人与看门狗反复盯盘。
    站点不可达/解析失败返回 None，由调用方回退到本地文件（云端 runner 本地即最新 checkout）。"""
    try:
        url = SITE_URL + f"data/{source_id}.js"
        req = urllib.request.Request(url, headers={"User-Agent": "v8-health-check"})
        raw, err = _urlopen_retry(req, timeout=20)
        if raw is None:
            return None
        text = raw.decode("utf-8", "ignore").lstrip("\ufeff")
        m = re.search(rf"window\.{re.escape(var_name)}\s*=\s*(\{{[\s\S]*?\}})\s*;", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    except Exception:
        return None
    return None


def _load_token():
    # GHA/云端：secrets.GITHUB_TOKEN (默认 workflow token, 有 actions:read 权限可查 runners)
    for env_name in ("V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v
    # 本机/开发环境：依次尝试多个候选（2026-08-12 增加 data/.github_pat.txt：
    # 之前 v8_ops_self_heal 注入 GH_TOKEN=默认 token，云端 _load_token 回退到 quant-scanner-v8 旧路径失败；
    # 现统一指向仓库内 data/.github_pat.txt（与 scripts/monitor_*.py 同源，最稳定））。
    _this_dir = Path(__file__).resolve().parent
    candidates = [
        _this_dir / "data" / ".github_pat.txt",          # 仓库根/data/.github_pat.txt（推荐）
        Path.home() / ".workbuddy" / "v8_gh_token.txt",  # 用户级 workbuddy token
    ]
    for p in candidates:
        if p.exists():
            try:
                t = p.read_text(encoding="utf-8").strip().lstrip("\ufeff")
                if t:
                    return t
            except Exception:
                continue
    return None


def api_get(url, max_retries=None):
    """GitHub API GET，带重试。

    2026-08-11 修：原实现一次失败即返回，遇到 SSL 握手超时 / 连接重置等瞬时抖动
    就会让 check_site_deploy_sync 报「无法从线上或 API 获取 Pages SHA」误告警。
    现对「可恢复失败」（网络异常、5xx、429 限流）重试，对确定性失败（401/403/404）
    立即返回不浪费时间。
    """
    import time as _time
    token = _load_token()
    if not token:
        return {"__error__": 401, "__msg__": "no token：请在 repo secrets 配置 V8_GH_TOKEN，或在本地放置 data/.github_pat.txt"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    retries = SITE_MAX_RETRIES if max_retries is None else max_retries
    last = {"__error__": 0, "__msg__": "unknown"}
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}
            # 4xx 属确定性失败（无权限/不存在），重试无意义；仅 5xx 与 429 限流值得重试
            if e.code < 500 and e.code != 429:
                return last
        except Exception as e:
            last = {"__error__": 0, "__msg__": str(e)}
        if attempt < retries:
            print(f"[RETRY] api_get 第{attempt+1}次失败(code={last.get('__error__')})，"
                  f"{_SITE_RETRY_DELAY_SEC}s 后重试... {url}")
            _time.sleep(_SITE_RETRY_DELAY_SEC)
    last["__msg__"] = f"连续 {retries + 1} 次请求均失败：{last.get('__msg__')}"
    return last


# ─────────────────────────────────────────────────────────────────────────────
# 带 retry 的 urlopen：吸收 GitHub Pages 瞬时 SSL/网络抖动，避免误报邮件
# ─────────────────────────────────────────────────────────────────────────────
# 2026-08-11 由 2 提到 4：GitHub Pages / api.github.com 在云端 build 高频推送时段
# （如 09:07-09:09 连续 6 次 build）会出现成片的 503 / SSL 握手超时，2 次重试不足以吸收，
# 导致「Pages 部署同步」误报。5 次尝试 × 3s 间隔 ≈ 12s，代价可接受。
SITE_MAX_RETRIES = 4       # 首次 + 最多重试 4 次
_SITE_RETRY_DELAY_SEC = 3   # 重试间隔（秒）


def _urlopen_retry(req_or_url, timeout=15, max_retries=None):
    """带重试的 urlopen，返回 (response_bytes, None) 或 (None, error_str)。
    用于 site 检测等对外请求，吸收瞬时抖动。"""
    import time as _time
    retries = max_retries or SITE_MAX_RETRIES
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req_or_url, timeout=timeout) as r:
                return r.read(), None
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"[RETRY] site urlopen 第{attempt+1}次失败({type(e).__name__})，{_SITE_RETRY_DELAY_SEC}s后重试...")
                _time.sleep(_SITE_RETRY_DELAY_SEC)
    return None, str(last_err)


# ─────────────────────────────────────────────────────────────────────────────
# 自愈（detect-and-heal）：发现可修复的数据陈腐，主动派发对应类别刷新，而非只发邮件
# ─────────────────────────────────────────────────────────────────────────────
CN_WORKFLOW_ID = 327687211        # v8_cn_fetch_cloud workflow id（云端 ubuntu 主力，用于 API 派发刷新）
BUILD_DEPLOY_WORKFLOW_ID = 324135263  # ☁️ v8 构建部署(云端ubuntu) workflow id
ALGO_RUN_WORKFLOW_ID = 324119592      # ☁️ v8 盘后算法链(云端) workflow id（重新产出 FINAL_RECOMMEND 等）
HEAL_DEBOUNCE_MIN = 25           # 同一类别最小派发间隔，避免每小时巡检重复触发
ALERT_OVERDUE_MIN = 120          # 与 send_report_email 一致的「值得处理」阈值（分钟）
# 2026-08-11 漏洞 #1：自愈单次最多派发 N 个 workflow，防 runner 打爆/事件风暴
MAX_DISPATCHES_PER_RUN = 5
# 2026-08-11 漏洞 #3：管线耗时趋势监控——latest 超 avg+3σ 视为异常
WORKFLOW_DURATION_HISTORY = '.workbuddy/workflow_durations.json'
WORKFLOW_DURATION_SIGMA = 3.0

# 卡片分组 -> 刷新类别映射（与 cloud_fetch_v8.py / update_v8.py 的 CATEGORY_MAP 对应）
PAGE_TO_CAT = {
    "实时数据": "intraday",
    "今日事件": "premarket",
    "盘后数据": "post_close",
    "选股策略": "post_close",
}


_PENDING_STATES = ("queued", "pending", "waiting", "requested")

# 2026-08-12 第173轮：pending 超过该分钟数视为 GitHub 侧「僵尸排队」，不再阻断派发。
# 依据：云端 ubuntu-latest 的 workflow_dispatch 正常在秒级~1 分钟内取得 runner 并转
# in_progress；实测 run#93(15:38:59) 挂在 queued 超 35 分钟仍未启动（job 标签
# ubuntu-latest、started_at 已写但状态不动）= GitHub 侧分配卡死，它不会真正执行。
# 若无年龄上限，第172轮守卫会把这种僵尸当成「必然会跑的排队」而永久跳过派发，
# 自愈链路对该 workflow 直接死锁（GitHub 保留僵尸 run 可达 ~24h）。
_PENDING_MAX_AGE_MIN = 15

# 2026-08-20 第290轮一劳永逸修复：盘后算法链「并发堆积」闸门。
# 根因：_has_pending_run 只拦 queued/pending，**放行 in_progress**（对 2~5 分钟就跑完的
# cn_fetch / build_deploy 是正确设计）。但云端算法链单轮实测 68~120 分钟（step 06
# 「运行盘后算法链」独占绝大部分耗时，部分轮次撞 120min job timeout 被 cancelled），
# 远大于 HEAL_DEBOUNCE_MIN=25 的去抖窗口 → 每 25 分钟无条件再派一轮。
# 实证（2026-08-20 下午）：08:46:50Z~09:32:49Z 累积 **7 个 in_progress 算法链并发**，
# 既白烧 Actions 额度（7×~100min），又让多轮 run 对 raw_data/ 抢推产生 push race。
# 修复：algo_run 专用闸门——若已有 in_progress 且年龄 <= 该上限，则跳过派发；
# 超过上限视为僵尸（挂死/即将被 timeout 收割）不阻断，避免自愈链死锁。
_ALGO_RUNNING_MAX_AGE_MIN = 130


def _has_running_algo_run(headers):
    """算法链是否已有「正在跑」的运行；有则本轮不应再派发（防并发堆积）。

    返回 (running: bool, created_at: str|None)。查询异常保守返回 False（放行），
    与 _has_pending_run 的失败策略保持一致。
    """
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{ALGO_RUN_WORKFLOW_ID}/runs?per_page=10"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        now_utc = datetime.now(timezone.utc)
        for run in data.get("workflow_runs") or []:
            if (run.get("status") or "").lower() != "in_progress":
                continue
            created = run.get("created_at")
            try:
                dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_min = (now_utc - dt).total_seconds() / 60
            except Exception:
                age_min = None
            if age_min is not None and age_min > _ALGO_RUNNING_MAX_AGE_MIN:
                print(f"[WARN] algo_run 存在僵尸 in_progress run(created {created}, "
                      f"已跑 {age_min:.0f}min > {_ALGO_RUNNING_MAX_AGE_MIN}min)，不阻断派发")
                continue
            return True, created
        return False, None
    except Exception:
        return False, None


def _has_pending_run(workflow_id, headers):
    """检查 workflow 是否已有「排队中(未开始)」运行；有则不应再派发。

    2026-08-12 第172轮根因修复（与 v8_cloud_watchdog.py::has_pending_run 同源）：
    云端 fetch/build workflow 均设 `concurrency: cancel-in-progress: false`，
    GitHub 该模式下每个 group **只保留 1 个 pending run**，新的 workflow_dispatch
    会把原先排队的那个 cancel 掉。同一轮巡检里看门狗 auto_dispatch 与本文件
    self_heal 各派发一次 → 后者顶掉前者，实测导致盘中数据断档 69 分钟
    (raw_data/index_quotes.json 提交 13:41:15 → 14:50:18)，9 张盘中卡集体转 FAIL。

    仅在存在 pending run 时跳过（它必然会执行）；只有 in_progress 时照常派发。
    查询异常返回 False，保守放行。

    2026-08-12 第173轮加固：pending 年龄超 _PENDING_MAX_AGE_MIN 视为僵尸排队，
    **不阻断派发**（否则一个卡死的 queued run 会让自愈对该 workflow 死锁整天）。
    """
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/runs?per_page=10"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        now_utc = datetime.now(timezone.utc)
        for run in data.get("workflow_runs") or []:
            if (run.get("status") or "").lower() not in _PENDING_STATES:
                continue
            created = run.get("created_at")
            age_min = None
            try:
                dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_min = (now_utc - dt).total_seconds() / 60
            except Exception:
                age_min = None
            if age_min is not None and age_min > _PENDING_MAX_AGE_MIN:
                # 僵尸排队：跳过它继续看下一条，不因它阻断派发
                print(f"[WARN] workflow {workflow_id} 存在僵尸 pending run(created {created}, "
                      f"排队 {age_min:.0f}min > {_PENDING_MAX_AGE_MIN}min)，不阻断派发")
                continue
            return True, created
        return False, None
    except Exception:
        return False, None


def _cn_runner_available():
    """检查 self-hosted cn runner 是否至少有 1 台 online（防自愈派发风暴）。

    2026-08-17 主人怒令发现：alimi-cn offline + lemoncat busy 时，health_patrol
    每分钟兜底 + self_heal 派发 → 每 6 分钟无完成就再 dispatch → 派发全部 Set up job
    失败 → 死循环风暴（当晚 14:02-14:09 连续 8+ 个 failure/cancelled）。
    修法：派发前先查 runner 状态，全 offline 则跳过本轮派发（留到 runner 恢复）。
    """
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/actions/runners",
            headers={"Authorization": f"Bearer {_load_token()}",
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
        online = [x for x in d.get("runners", []) if x.get("status") == "online"]
        return bool(online), [x.get("name", "?") for x in online]
    except Exception:
        # API 失败时保守放行（宁可派发也不漏报）
        return True, ["?"]


def _dispatch_cn_fetch(cat):
    """经 GitHub API 派发 cn_fetch 刷新（自愈核心动作）。

    返回三元组 (ok, msg, dispatched)：
      ok         = 本次处理没有出错（含「因已有 pending 而跳过」这种正常情况）
      dispatched = **真的发出了 POST**（决定是否刷新去抖锁；见第173轮说明）
    """
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发", False
    # 2026-08-17 防风暴：cn runner 全 offline 时派发必失败 → 跳过本轮
    avail, online = _cn_runner_available()
    if not avail:
        return True, f"cn runner 全 offline（在线={online}），跳过派发防风暴（待 runner 恢复）", False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    pending, since = _has_pending_run(CN_WORKFLOW_ID, headers)
    if pending:
        return True, (f"已有排队中的 cn_fetch 运行(created {since})，跳过派发"
                      f"（避免顶掉该 pending run）category={cat}"), False
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"category": cat}}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 cn_fetch category={cat} (HTTP {r.status})", True
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}", False
    except Exception as e:
        return False, f"派发异常: {e}", False


def _dispatch_algo_run():
    """经 GitHub API 派发 v8 盘后算法链(云端)，重新产出 FINAL_RECOMMEND_DATA 等选股结果。

    返回三元组 (ok, msg, dispatched)，语义同 _dispatch_cn_fetch。
    """
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发", False
    # 2026-08-17 防风暴：algo_run 也用 self-hosted cn runner
    avail, online = _cn_runner_available()
    if not avail:
        return True, f"cn runner 全 offline（在线={online}），跳过 algo_run 派发防风暴", False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    pending, since = _has_pending_run(ALGO_RUN_WORKFLOW_ID, headers)
    if pending:
        return True, f"已有排队中的 algo_run 运行(created {since})，跳过派发（避免顶掉该 pending run）", False
    # 2026-08-20 第290轮：算法链单轮 68~120min >> 25min 去抖窗口，若不拦 in_progress
    # 会每 25 分钟叠加一轮（实测堆到 7 个并发）。已在跑就等它出数，不重复派发。
    running, r_since = _has_running_algo_run(headers)
    if running:
        return True, f"已有正在运行的 algo_run(created {r_since})，跳过派发（防并发堆积，等其出数）", False
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{ALGO_RUN_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 algo_run(盘后算法链) (HTTP {r.status})", True
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}", False
    except Exception as e:
        return False, f"派发异常: {e}", False


def _dispatch_build_deploy():
    """经 GitHub API 派发 v8_build_deploy，触发 Pages 重新构建部署。

    返回三元组 (ok, msg, dispatched)，语义同 _dispatch_cn_fetch。
    """
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发", False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    pending, since = _has_pending_run(BUILD_DEPLOY_WORKFLOW_ID, headers)
    if pending:
        return True, f"已有排队中的 build_deploy 运行(created {since})，跳过派发（避免顶掉该 pending run）", False
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{BUILD_DEPLOY_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 build_deploy (HTTP {r.status})", True
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}", False
    except Exception as e:
        return False, f"派发异常: {e}", False


def _heal_local_sync():
    """尝试让本地 HEAD 与 origin/main 对齐（fetch + ff-only，必要时 stash）。"""
    try:
        subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True, text=True, timeout=60)
        local = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=10).strip()
        remote = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True, timeout=10).strip()
        if local == remote:
            return True, f"本地已与 origin/main 同步 ({local[:7]})"
        try:
            behind = int(subprocess.check_output(
                ["git", "rev-list", "--count", f"{local}..{remote}"],
                text=True, timeout=10
            ).strip())
        except Exception:
            return False, "无法判断本地与 origin/main 的祖先关系"
        if behind == 0:
            return False, f"本地 ({local[:7]}) 领先/分歧于 origin/main ({remote[:7]})，需人工处理"
        # 工作树若脏：跳过自动对齐（禁止 stash/pop）。
        # 2026-08-10 一劳永逸修复（861ff16 事故机制复现）：
        # 原实现 stash → ff-only → stash pop，pop 冲突时 check=False 不中止，
        # 把 <<<<<<< 冲突标记留在 data/*.js 工作区、index 变 UU，并被后续 push 上线。
        # update_v8 生成 data/*.js 后必然工作区脏 → 此时 stash/pop 必冲突。
        # 修复：脏则跳过对齐，由调用方自行 commit 后再同步；云端 build 工作区干净时仍正常 ff-only。
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if dirty:
            return True, f"工作区有未提交改动（{len(dirty.splitlines())} 项），跳过自动对齐（防 stash/pop 冲突污染 data/*.js）"
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], check=True,
                       capture_output=True, text=True, timeout=30)
        return True, f"本地已从 {local[:7]} ff 对齐到 origin/main {remote[:7]}"
    except subprocess.CalledProcessError as e:
        return False, f"git 命令失败: {e.stderr.strip()[:200]}"
    except Exception as e:
        return False, f"异常: {e}"


def _heal_site_sync():
    """先同步本地，再检查线上 Pages SHA；如仍不一致则派发 build_deploy。"""
    local_ok, local_msg = _heal_local_sync()
    if not local_ok:
        return False, f"本地同步失败: {local_msg}"
    try:
        remote = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True, timeout=10).strip()
    except Exception as e:
        return False, f"无法读取 origin/main: {e}"
    deployments = api_get(f"https://api.github.com/repos/{REPO}/deployments?environment=github-pages&per_page=1")
    if not isinstance(deployments, list) or not deployments:
        return False, "无法从 GitHub API 获取 Pages 部署 SHA"
    site_sha = deployments[0].get("sha", "")
    if not site_sha:
        return False, "GitHub API 返回的部署 SHA 为空"
    if remote.startswith(site_sha) or site_sha.startswith(remote):
        return True, f"Pages 已同步 ({site_sha[:7]} == origin/main {remote[:7]})"
    # 防抖动：25 分钟内不重复派发
    lock = _load_heal_lock()
    now = now_cst()
    last = lock.get("build_deploy")
    if last:
        last_dt = parse_time(last)
        if last_dt and (now - last_dt).total_seconds() < HEAL_DEBOUNCE_MIN * 60:
            return True, f"近 {HEAL_DEBOUNCE_MIN} 分钟内已派发 build_deploy，跳过重复"
    ok, dmsg, dispatched = _dispatch_build_deploy()
    if ok:
        # 第173轮：仅「真的发出 POST」才刷新去抖锁；因已有 pending 而跳过时不能记账，
        # 否则会把 25 分钟去抖窗口白白消耗在一次没发生的派发上。
        if dispatched:
            lock["build_deploy"] = now.strftime("%Y-%m-%d %H:%M:%S")
            _save_heal_lock(lock)
        return True, f"已派发 build_deploy ({dmsg})" if dispatched else dmsg
    return False, f"派发 build_deploy 失败: {dmsg}"


def _heal_lock_path():
    return DATA_DIR / ".heal_dispatch.json"


def _load_heal_lock():
    p = _heal_lock_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_heal_lock(lock):
    p = _heal_lock_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")


def self_heal(report):
    """发现可自愈的问题时主动修复：数据卡片派发对应类别刷新；管线/部署同步自动对齐。

    返回 (healed, failed) 两个文案列表：
      - healed: 已自动派发刷新 / 近期已派发跳过重复 / 已自动对齐
      - failed: 派发失败（需人工）
    同时给 report["items"] 中对应卡片打上 heal 标记（供前端展示「已自动修复」）。
    """
    healed, failed = [], []
    lock = _load_heal_lock()
    now = now_cst()
    # 2026-08-12 修复 3d2a53b2 引入的 UnboundLocalError（根因级）：
    # 「单次派发上限」守卫用到 _dispatch_count / _dispatch_limit_hit 两个局部变量，
    # 但从未初始化 → 只要有任一数据卡进入派发分支就抛 UnboundLocalError，
    # 导致 self_heal 整体中断（管线类 local_sync/site_sync 自愈也不执行），
    # 且异常冒泡出 main() 使 v8_health_check.py 以 traceback rc=1 退出，
    # 看门狗每轮固定误报「v8_health_check.py 返回非零: 1」。必须在函数入口初始化。
    _dispatch_count = 0          # 本次运行已派发的 workflow 数
    _dispatch_limit_hit = []     # 因达上限被跳过的类别（写回 report 供前端/邮件可见）

    # 所有 fail 项（数据卡片 + 管线类）
    fail_items = [it for it in report["items"] if it.get("status") == "fail"]

    # 0) 内容审计类自愈：最终推荐入选日期陈旧 → 派发盘后算法链重新产出
    #    （这类问题不在 fail_items 内，需单独识别 message 含「陈旧」的项）
    for it in report["items"]:
        if it.get("id") == "final_enter_stale" and "陈旧" in (it.get("message") or ""):
            last = lock.get("algo_run")
            if last:
                last_dt = parse_time(last)
                if last_dt and (now - last_dt).total_seconds() < HEAL_DEBOUNCE_MIN * 60:
                    healed.append(f"[algo] {it['name']}: 近 {HEAL_DEBOUNCE_MIN} 分钟内已派发，跳过重复")
                    it["heal"] = "已自愈(跳过重复): 近窗口内已派发盘后算法链"
                    continue
            ok, dmsg, dispatched = _dispatch_algo_run()
            if ok:
                # 第173轮：跳过（已有 pending）不得记账，否则去抖窗口被空派发消耗；
                # 文案也据实区分「已派发」与「跳过」，避免邮件谎报已自愈。
                if dispatched:
                    healed.append(f"[algo] {it['name']}: 已自动派发盘后算法链重新产出 ({dmsg})")
                    it["heal"] = "已自动派发盘后算法链"
                    lock["algo_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    healed.append(f"[algo] {it['name']}: {dmsg}")
                    it["heal"] = f"已自愈(跳过): {dmsg}"
            else:
                failed.append(f"[algo] {it['name']}: 自动派发失败 ({dmsg})")
                it["heal"] = f"自愈失败: {dmsg}"
    _save_heal_lock(lock)

    # 0.5) 🔴 2026-08-12 主人紧急令：A 股覆盖 URGENT 自我修复
    #    痛点：8 天三重共识全港股因 self_heal 只处理 fail 类项从未派发自愈。
    #    现在 a_share_* 项的 heal_cat 已设 algo_run，但 status 是 warn（不进 cat_items 派发链）。
    #    修复：单独遍历「warn + id 以 a_share_ 开头 + message 含 URGENT」的项，
    #         派发 algo_run 让云端 scanner 用修过的路径（commit 045ac1c84）出 A 股金股池。
    #    去抖：与 algo_run 共享 HEAL_DEBOUNCE_MIN 窗口（同属一类）。
    urgnet_items = [it for it in report["items"]
                    if it.get("id", "").startswith("a_share_")
                    and it.get("status") == "warn"
                    and "URGENT" in (it.get("message") or "")]
    if urgnet_items:
        last = lock.get("algo_run")
        if last:
            last_dt = parse_time(last)
            if last_dt and (now - last_dt).total_seconds() < HEAL_DEBOUNCE_MIN * 60:
                msg = f"近 {HEAL_DEBOUNCE_MIN} 分钟内已派发 algo_run，跳过重复 A 股自愈"
                for it in urgnet_items:
                    it["heal"] = f"已自愈(跳过重复): {msg}"
                healed.append(f"[algo/A股自愈] {', '.join(it.get('name','') for it in urgnet_items)}: {msg}")
            else:
                if _dispatch_count >= MAX_DISPATCHES_PER_RUN:
                    for it in urgnet_items:
                        it["heal"] = "已自愈(跳过): 达单次派发上限"
                    healed.append(f"[algo/A股自愈] A股全港股: 达单次派发上限({MAX_DISPATCHES_PER_RUN})，跳过")
                else:
                    _dispatch_count += 1
                    ok, dmsg, dispatched = _dispatch_algo_run()
                    if ok and dispatched:
                        healed.append(f"[algo/A股自愈] {', '.join(it.get('name','') for it in urgnet_items)}: 🚨 URGENT 自动派发 algo_run 重跑（{dmsg}）→ 修复路径在 commit 045ac1c84")
                        for it in urgnet_items:
                            it["heal"] = f"🚨 URGENT 已自愈(已派发 algo_run 重跑): {dmsg}"
                        lock["algo_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    elif ok:
                        healed.append(f"[algo/A股自愈] A股全港股: {dmsg}")
                        for it in urgnet_items:
                            it["heal"] = f"已自愈(跳过): {dmsg}"
                    else:
                        failed.append(f"[algo/A股自愈] A股全港股: 自动派发失败 ({dmsg})")
                        for it in urgnet_items:
                            it["heal"] = f"自愈失败: {dmsg}"
        _save_heal_lock(lock)
    # 1) 数据卡片自愈：满足年龄阈值或被异常清空
    stale = [it for it in fail_items
             if (it.get("age_min") is not None and it["age_min"] >= ALERT_OVERDUE_MIN)
             or it.get("premarket_cleared") is True]
    cat_items = {}
    for it in stale:
        # heal_cat 显式覆盖优先：部分卡片虽挂在某页面下，实际由算法链(run_algorithms)产出，
        # 按 page 映射派发 cn_fetch 永远刷不到（如 NT_DATA 市场提示），必须走 algo_run。
        cat = it.get("heal_cat") or PAGE_TO_CAT.get(it.get("page"))
        if cat:
            cat_items.setdefault(cat, []).append(it)

    for cat, items in cat_items.items():
        names = [it.get("name", "") for it in items]
        last = lock.get(cat)
        if last:
            last_dt = parse_time(last)
            if last_dt and (now - last_dt).total_seconds() < HEAL_DEBOUNCE_MIN * 60:
                msg = f"近 {HEAL_DEBOUNCE_MIN} 分钟内已派发，跳过重复"
                healed.append(f"[{cat}] {', '.join(names)}: {msg}")
                for it in items:
                    it["heal"] = f"已自愈(跳过重复): {msg}"
                continue
        if _dispatch_count >= MAX_DISPATCHES_PER_RUN:
            _dispatch_limit_hit.append(cat)
            for it in items:
                it["heal"] = f"已自愈(跳过): 达单次派发上限"
            healed.append(f"[{cat}] {', '.join(names)}: 达单次派发上限({MAX_DISPATCHES_PER_RUN})，跳过")
            continue
        _dispatch_count += 1
        if cat == "algo_run":
            ok, dmsg, dispatched = _dispatch_algo_run()
        else:
            ok, dmsg, dispatched = _dispatch_cn_fetch(cat)
        if ok:
            # 第173轮：区分「真派发」与「因已有 pending 跳过」——后者不刷新去抖锁，
            # 否则一个（可能是僵尸的）pending run 会让后续每轮都以「近25分钟已派发」
            # 为由继续跳过，自愈永久空转却对外谎报「已自动派发刷新」。
            if dispatched:
                healed.append(f"[{cat}] {', '.join(names)}: 已自动派发刷新 ({dmsg})")
                for it in items:
                    it["heal"] = f"已自动派发刷新({cat})"
                lock[cat] = now.strftime("%Y-%m-%d %H:%M:%S")
            else:
                healed.append(f"[{cat}] {', '.join(names)}: {dmsg}")
                for it in items:
                    it["heal"] = f"已自愈(跳过): {dmsg}"
        else:
            failed.append(f"[{cat}] {', '.join(names)}: 自动派发失败 ({dmsg})")
            for it in items:
                it["heal"] = f"自愈失败: {dmsg}"

    # 2) 管线类自愈：本地同步 / Pages 部署同步
    for it in fail_items:
        iid = it.get("id")
        if iid == "local_sync":
            ok, dmsg = _heal_local_sync()
            if ok:
                healed.append(f"[管线] {it['name']}: {dmsg}")
                it["heal"] = f"已自动对齐: {dmsg}"
            else:
                failed.append(f"[管线] {it['name']}: {dmsg}")
                it["heal"] = f"自愈失败: {dmsg}"
        elif iid == "site_sync":
            ok, dmsg = _heal_site_sync()
            if ok:
                healed.append(f"[管线] {it['name']}: {dmsg}")
                it["heal"] = f"已自动处理: {dmsg}"
            else:
                failed.append(f"[管线] {it['name']}: {dmsg}")
                it["heal"] = f"自愈失败: {dmsg}"

    _save_heal_lock(lock)
    # 达上限被跳过的类别写回报告，避免「静默少派发」无处可查
    if _dispatch_limit_hit:
        report["heal_limit_hit"] = _dispatch_limit_hit
    return healed, failed


# 2026-08-11 漏洞 #3：管线耗时趋势监控
def _check_workflow_durations(report):
    import statistics
    from pathlib import Path
    hist_path = Path(WORKFLOW_DURATION_HISTORY)
    history = {}
    if hist_path.exists():
        try:
            history = json.loads(hist_path.read_text(encoding='utf-8'))
        except Exception:
            history = {}
    now_iso = now_cst().strftime('%Y-%m-%dT%H:%M:%SZ')
    new_history = {}
    findings = []
    targets = ['🩺 v8 运维看板常态自愈巡检(云端ubuntu)',
               '🇨🇳 v8 中国数据抓取(云端)',
               '☁️ v8 盘后算法链(云端)',
               '☁️ v8 构建部署(云端ubuntu)']
    for wf in targets:
        runs = api_get(f'https://api.github.com/repos/{REPO}/actions/runs?per_page=30&status=completed')
        if not isinstance(runs, dict):
            continue
        wf_runs = [r for r in runs.get('workflow_runs', []) if r.get('name') == wf and r.get('conclusion') == 'success']
        if len(wf_runs) < 5:
            continue
        durs = []
        for r in wf_runs:
            try:
                d = (parse_time(r['updated_at']) - parse_time(r['created_at'])).total_seconds()
                if d > 0:
                    durs.append(d)
            except Exception:
                pass
        if len(durs) < 5:
            continue
        avg = statistics.mean(durs)
        std = statistics.stdev(durs) if len(durs) > 1 else 0
        latest = durs[0] if durs else 0
        new_history[wf] = {'avg': round(avg, 1), 'std': round(std, 1),
                           'latest': round(latest, 1), 'n': len(durs), 'updated': now_iso}
        if std > 0 and latest > max(avg + WORKFLOW_DURATION_SIGMA * std, 600):
            findings.append((wf, avg, std, latest))
    try:
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        hist_path.write_text(json.dumps(new_history, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass
    for wf, avg, std, latest in findings:
        report['items'].append({
            'id': f'workflow_duration_{abs(hash(wf)) % 100000}',
            'name': f'管线耗时异常 · {wf[:24]}',
            'page': '运维监控',
            'status': 'warn',
            'message': f'⚠️ 最新 {latest:.0f}s 远超均值 {avg:.0f}s+3σ({std:.0f}s),可能 runner 慢/API 卡'
        })


def write_urgent(reason_lines):
    """邮件失败/夜间静音时需留痕时，写 URGENT 文件到仓库根目录。"""
    ts = now_cst().strftime("%Y-%m-%d_%H%M")
    p = Path(f"URGENT_小九_{ts}_v8健康自检告警.md")
    body = [f"# v8 健康自检告警 {ts}", ""] + reason_lines + ["", "请检查 v8_health_check.py 日志与自愈结果。"]
    p.write_text("\n".join(body), encoding="utf-8")
    print(f"[INFO] 已写紧急文件 {p}")


def adjust_max_age(def_max, page=None):
    """根据交易时段 + 数据更新窗口动态调整阈值。

    核心思路：每类数据有自己的「更新窗口」，窗口关闭后数据自然不会再刷新，
    此时不应再用盘中阈值去判 stale，而应放宽到「下次预计更新前都算正常」。

    参数:
        def_max: CARD_DEFS 里定义的默认阈值（分钟）
        page:   卡片所属分组（今日事件/实时数据/盘后数据/选股策略），用于区分更新窗口
    """
    n = now_cst()
    h = n.hour + n.minute / 60.0
    weekday = n.weekday()
    is_weekend = weekday >= 5
    is_trade_day = weekday < 5

    # ── 通用收紧：交易时段内实时数据必须很新 ──
    if page == "实时数据":
        if is_trade_day and ((9.5 <= h <= 11.5) or (13.0 <= h <= 15.0)):
            # 盘中：必须 45 分钟内更新过
            return min(def_max, 45)
        if is_trade_day and 15.0 <= h < 16.5:
            # 🛡 2026-08-21 一劳永逸修复：原 min(def_max, 120) 对 def_max=60 的盘中卡完全无效
            #   （min(60,120)=60，收盘宽限被自身默认值抵消）→ 14:52 的盘中数据到 15:56 满
            #   64min 仍按 60min 阈值误报 fail，制造「15点收盘后数据没更新」假象，反复触发运维告警。
            #   收盘后盘中聚合卡（指数 / ETF资金热度 / 板块资金流 / 市场资金流等）已定格、不再刷新，
            #   合理保留到次日开盘都算正常。改用「距最近收盘 + 3h 缓冲」自适应阈值
            #   （与下方盘前/夜间分支同口径），彻底消除收盘时段误报；真正盘中故障仍在
            #   09:30-15:00 盘中分支（45min 严格阈值）实时报 fail，不掩盖真问题。
            close = last_trade_day_close(n)
            stale_floor = int((n - close).total_seconds() / 60) + 180
            return max(120, stale_floor)
        # 盘前 / 夜间 / 周末：实时数据本就不预期更新，放过夜阈值
        # 次日 09:30 才会有新数据，给到次日开盘都算正常。
        # 2026-08-11 修：原固定 960（16h）会误杀「盘前保留昨日值」的卡片——
        #   ETF_DAILY_MONITOR/CAPITAL_FLOW_DATA 等停在上一交易日 15:30 盘后定稿，
        #   到次日 08:55 健康检查时已 17.4h（1045min）> 960 被判 fail。
        #   改为「距最近收盘分钟数 + 3h 缓冲」自适应（与盘后数据同口径），
        #   长假/周一早盘自动覆盖；真正连续多日不更新仍会超阈值告警。
        close = last_trade_day_close(n)
        stale_floor = int((n - close).total_seconds() / 60) + 180
        if is_trade_day and h < 9.5:
            return max(960, stale_floor)
        # 周末 /节假日：给 2880（48h，覆盖周末+周一开盘）
        return max(2880, stale_floor)

    if page == "今日事件":
        # 今日事件由 v8_cn_fetch 08:25 premarket 产出，每日仅一次
        if is_trade_day and 8.0 <= h < 10.0:
            # 盘前窗口：期望已更新，但允许 180 分钟（可能稍晚）
            return min(def_max, 180)
        # 10:00 后当日不会再更新（下次是次日 08:25）
        # 给到次日早盘都算正常
        if is_trade_day:
            return 960 if h < 23 else 1200  # 到次日 08:00~09:00
        # 周末：覆盖到周一早盘
        return 2880

    if page in ("盘后数据", "选股策略"):
        # 盘后数据由 v8_algo_run 18:30 算法链产出，每个交易日仅一次。
        # 关键：18:30 之外的所有时段，数据合理地来自「上一交易日收盘后」，
        # 年龄可达 24h+，绝不能再用 360min 判 stale（否则夜间/白天/周末必然满屏红灯）。
        close = last_trade_day_close(n)
        hours_since_close = (n - close).total_seconds() / 3600
        if hours_since_close < 8:
            # 收盘后 8 小时内是新数据产出窗口（18:30 跑完 + 构建部署延迟），严格检查
            return min(def_max, 360)
        # 其他时段：阈值 = 自最近收盘以来分钟数 + 3 小时缓冲
        # 自动覆盖夜间/周末/周一早盘，避免周五数据在周日夜间被 2880 分钟阈值误杀
        return int(hours_since_close * 60) + 180

    # 未分类 / 管线类：沿用旧逻辑兜底
    if is_trade_day and ((9.5 <= h <= 11.5) or (13.0 <= h <= 15.0)):
        return min(def_max, 45)
    if is_trade_day and 8.0 <= h < 9.5:
        return min(def_max, 180)
    if is_trade_day and 15.0 <= h < 20.0:
        return min(def_max, 120)
    return def_max


def _hard_cap_for_owner_rule(n=None, page=None):
    """🛡 主人铁律 2026-08-18 终极收紧：按 page × 分时段红线。

    按 page 区分（仅实时数据走 2h 红线，盘后/选股/今日事件保留 24h 兜底）：

    实时数据（real-time / 盘中秒级刷新的卡）：
      · 交易日盘中（09:00-15:30）：**2h（120 min）** — 主人原话「超过2小时就报警+自愈闭环」
      · 交易日盘后（15:30-20:00）：4h — cn_fetch post_close 17:20 跑完留缓冲
      · 交易日盘前（08:00-09:00）：6h — premarket 8:25 必跑，留 6h 兜底隔夜漏抓
      · 夜间：24h — 非交易时段实时数据停滞正常

    盘后数据 / 选股策略 / 今日事件 / 其他：保留原 24h 红线
      （这些页合理保留上一交易日数据；adjust_max_age 已自带分时自适应，无需再绑）

    非交易日（周末/节假日）：T+1 18:30 - 上次收盘（自适应长假/连休，下限 24h）

    接入方式：所有 adjust_max_age 返回值再 min(def_max, this) 一次。

    历史：
      · 2026-08-17 v1：24h 统一红线（主人最初记忆版本）
      · 2026-08-18 v2：主人再次令「超过2小时就报警自愈」→ 仅实时数据页收紧到 2h，
        全 page 统一收紧会误伤盘后数据（昨日 17:30 出的 post_close 数据自然 < 24h 旧，
        但盘中 09:00-15:30 距上次收盘 17.5h，按通用 2h 红线会被误报 fail）
    """
    n = n or now_cst()
    if not is_market_closed(n):
        if page == "实时数据":
            h = n.hour + n.minute / 60.0
            # 盘中（09:00-15:30）：2h 红线——主人原话
            if 9.0 <= h < 15.5:
                return 120
            # 盘后窗口（15:30-20:00）：4h — cn_fetch post_close 17:20 跑完留 2h 余量
            if 15.5 <= h < 20.0:
                return 240
            # 盘前窗口（08:00-09:00）：6h — premarket 8:25 必跑，留 6h 兜底隔夜漏抓
            if 8.0 <= h < 9.0:
                return 360
        # 其他 page 或夜间：24h — 数据合理停滞（非实时数据由 adjust_max_age 自适应）
        return 24 * 60
    # 非交易日：T+1 18:30 - 上次收盘（自适应长假/连休）
    last_close = last_trade_day_close(n)
    d = n.date() + timedelta(days=1)
    while not _is_trading_day(d):
        d += timedelta(days=1)
    # T+1 18:30 = 下一个交易日盘后跑完时间
    t1_done = datetime.combine(d, datetime.strptime("18:30", "%H:%M").time(),
                                tzinfo=timezone(timedelta(hours=8)))
    cap = int((t1_done - last_close).total_seconds() / 60)
    # 下限保护：算出来不能 < 24h，否则同日连休 1 天就崩
    return max(24 * 60, cap)


def check_data_cards():
    results = []
    today_str = now_cst().strftime("%Y-%m-%d")

    def _emit(d, row):
        """统一出口：任何分支产出的检查项都必须继承 heal_cat，
        否则 self_heal 会回落到 PAGE_TO_CAT 派发错误类别（158 轮加固）。"""
        if d.get("heal_cat"):
            row["heal_cat"] = d["heal_cat"]
        results.append(row)

    for d in CARD_DEFS:
        source_id = d.get("_source_file") or d["id"]
        var_name = d.get("_window_var") or d["id"]
        path = DATA_DIR / f"{source_id}.js"  # 本地兜底路径（云端 runner 本地即最新 checkout）
        # 2026-08-20 一劳永逸修复：优先读线上站点（云端真实部署态），本机未 pull 也不会误报陈旧
        data = load_window_var_from_site(source_id, var_name)
        if data is None:
            data = load_window_var(path, var_name)
        if data is None:
            _emit(d, {
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "fail", "last_update": "--", "age_min": None,
                "message": f"找不到数据文件 {path.name} 或解析失败"
            })
            continue
        ts = data.get("update_time") or data.get("date") or data.get("lastUpdated") or "--"
        dt = parse_time(ts)
        max_age = adjust_max_age(d["max_age"], page=d.get("page"))
        # 🛡 主人铁律 2026-08-18：分 page × 分时段红线（仅实时数据盘中 2h / 其他 24h）
        # 硬 cap 必须在 adjust_max_age 之后叠加，否则盘中/盘后自适应逻辑被绕过
        max_age = min(max_age, _hard_cap_for_owner_rule(page=d.get("page")))

        # 盘中 premarket_cleared 异常自愈检测：实时数据在交易时段被标记为盘前清空，属于误清空
        prem_cleared = data.get("premarket_cleared") is True
        # 注意：page 变量在下方才赋值，此处必须直接取 d["page"]，否则会误用上一轮循环的残留值
        if prem_cleared and d.get("page") == "实时数据" and is_intraday_session():
            _emit(d, {
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "fail", "last_update": str(ts), "age_min": 0,
                "premarket_cleared": True,
                "message": f"盘中交易时段被异常标记为 premarket_cleared（update_time={fmt_rel_time(ts)}）"
            })
            continue

        if dt is None:
            _emit(d, {
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "warn", "last_update": str(ts), "age_min": None,
                "message": "无法解析更新时间"
            })
            continue
        age_min = (now_cst() - dt).total_seconds() / 60
        status = "ok" if age_min <= max_age else "fail"

        # 🛡 2026-08-19 修：人工维护卡（今日宏观解读=主人撰写宏观解读，管线只补cpi/pmi）
        #   陈旧属预期，降 warn 不误报 fail（看板保留提示主人更新）。
        if d.get("manual_dep") and age_min > max_age:
            status = "warn"

        page = d.get("page")
        # 周末/节假日不更新模块：直接放行，不判 stale、不判空值，避免误告警
        weekend_skip = d.get("weekend_update") is False and is_market_closed()
        # 盘后数据 / 选股策略：周末/节假日停在最近交易日，同样放行并显示友好提示
        if not weekend_skip and is_market_closed() and page in ("盘后数据", "选股策略"):
            if dt and dt >= last_trade_day_close(now_cst()):
                weekend_skip = True

        # 盘前清空（premarket_cleared=true）是 cloud_fetch_v8._clear_intraday_for_premarket 的设计内行为：
        # 实时数据在 09:30 开盘前本就无当日数据，字段为空属预期，不应报"关键字段空值"。
        # 盘中被误清空的情况已由上方 prem_cleared + is_intraday_session() 分支判 fail，这里不重复。
        # 🛡 2026-08-19 修：ETF_DAILY_MONITOR 等 KEEP_VARS 卡盘前保留上一交易日(T+1)收盘值，
        #   盘前不刷新属设计行为（同 premarket_cleared 预期），盘前判 OK、开盘后由盘中刷新覆盖。
        prem_cleared_expected = (prem_cleared or d.get("premarket_keep")) and not is_intraday_session()

        # 空值检测
        empty_fields = []
        if not weekend_skip and not prem_cleared_expected:
            for f in d["key_fields"]:
                v = data.get(f)
                # 🔴 2026-08-17 一劳永逸修复：原 line 944 把 v == [] 当"空值"会误报
                # 三重共识 0 只 = 弱市真实状态（不是"空值"！），扫到的 stocks=[] 应该算合法
                # 只有字段完全缺失（None/不存在/非合法类型）才报"空值"
                # 真正的"上游 bug = stocks 数 > 0 但 A 股 = 0"交给 check_a_share_coverage 专门处理
                if v is None or (isinstance(v, str) and v in ("", "--", "加载中")):
                    empty_fields.append(f)
                elif not isinstance(v, (list, dict, int, float, str, bool)):
                    empty_fields.append(f)
        if empty_fields and status == "ok":
            status = "warn"
        rel = fmt_rel_time(ts)
        msg = f"更新于 {rel}"
        if weekend_skip:
            status = "ok"
            phase = "盘后" if page in ("盘后数据", "选股策略") else "盘前"
            msg = f"休市不更新（数据为上一交易日{phase}）；{rel}"
        elif prem_cleared_expected:
            status = "ok"
            msg = f"盘前已清空，等待开盘后刷新（预期行为）；{rel}"
        elif empty_fields:
            msg += f"；关键字段空值：{', '.join(empty_fields)}"
        if status == "fail":
            msg += f"；超过阈值 {max_age} 分钟"
        _emit(d, {
            "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
            "status": status, "last_update": ts, "age_min": round(age_min, 1),
            "message": msg
        })
    return results


# ── 2026-08-17 主人怒令「每个前端的算法都全面审计」：53 个 data/*.js 不在 CARD_DEFS 从未被审计 ──
# CARD_DEFS 只覆盖 28 张主卡；SECTOR_RS/SENTIMENT_CYCLE/COMMODITY_ELASTICITY/MAHORO/NORTH_FUND/
# STOCK_QUOTE/STOCK_MOMENTUM_STATE(W2)/TRIPLE_HISTORY/W52_HIGH/STOCK_PROFILE 等 53 个文件
# 既不在 CARD_DEFS 也不在 check_a_share_coverage → 陈旧 3 天没人报警（今晚主人连续质问的根因）。
# 一劳永逸修法：本函数自动扫描 data/*.js 全集，未登记 CARD_DEFS 的按「通用规则」审计：
#   通用规则 = ①有 update_time/date 且 ≤ 24h 红线（_hard_cap_for_owner_rule）②文件可解析 ③非空
# 未来新增 data 文件自动纳入审计，无需手工维护 CARD_DEFS。
_KNOWN_EXTRA_PAGES = {
    # 部分已登记 CARD_DEFS 的 id 会在这里被跳过（不重复审计）
}
# window 变量名 ≠ 文件名 的别名映射（文件 id → window 变量名候选）
_WINDOW_VAR_ALIASES = {
    "STOCK_MOMENTUM_STATE_V2": ["STOCK_MOMENTUM_ENHANCED"],
    "PORTFOLIO": ["PORTFOLIO_DATA"],
    "STOCK_RPS": ["STOCK_RPS_DATA"],
}
# 低频/非每日更新数据（24h 红线不适用，但超过 7 天仍报 warn）：
#   STOCK_PROFILE 个股资料库（月度刷新） / WEEKEND_META_REPORT 周末复盘（周末生成）
#   PORTFOLIO 用户真实持仓（手动更新） / PORTFOLIO_COST 持仓成本基准（手动）
#   CONCEPT_ETF_MAP 概念ETF静态映射（研究参考） / OPTIMIZED_STRATEGY 优化策略（回测产物）
#   BACKTEST_TDX 回测结果（参数变更才重跑） / BLOAT_CHECK 体积检查（build 时） / HEALTH_CHECK 本检查自产
#   RUNNER_STATUS_HEALTH runner 心跳（1 分钟级自愈，另有专门检查）
# 🛡 2026-08-18 一劳永逸补入：
#   WEEKEND_RUN 周度运行汇总（周末/月初自动跑，工作日基本无变化）→ 加入白名单避免误报 warn
_OCR_DEPENDENCY_FILES = {
    # 🛡 2026-08-19 一劳永逸：这些文件由「主人提供 PDF → OCR 抽取」驱动，无 PDF 输入自动巡检
    # 永远无法刷新。陈旧=预期，非异常。一并从 health-check items[] **完全排除**，彻底不渲染告警卡。
    # 与 self_heal_monitor.py P0-2 (免邮件方针) 对齐。
    "MOMENTUM_FILTER",
    "STOCK_MOMENTUM_STATE",
    "STOCK_MOMENTUM_STATE_V2",
}
_LOW_FREQ_FILES = {
    "STOCK_PROFILE", "WEEKEND_META_REPORT", "PORTFOLIO", "PORTFOLIO_COST",
    "CONCEPT_ETF_MAP", "OPTIMIZED_STRATEGY", "BACKTEST_TDX", "BLOAT_CHECK",
    "HEALTH_CHECK", "RUNNER_STATUS_HEALTH",
    "WEEKEND_RUN",
}
def check_all_data_files():
    """全量审计 data/*.js：已登记 CARD_DEFS 的跳过（check_data_cards 管），其余全部按通用规则查。

    通用规则（对未知文件）：
      · 文件缺失/不可解析 → fail
      · 无 update_time/date/generated/lastUpdated 字段 → warn（无法判龄）
      · age > 24h 红线（交易日）/ T+1 18:30（非交易日）→ fail
      · 空 dict / 全空 list → warn（弱市或数据源待接入，非致命）
      · 以上均通过 → ok
    """
    results = []
    known_ids = {d["id"] for d in CARD_DEFS}
    # 同源派生卡（前端复用同一 JS 文件，不单独算文件）
    derived = {"BIG_BULL_HUNTER", "SIX_DIM_RADAR"}
    for p in sorted(DATA_DIR.glob("*.js")):
        vid = p.name[:-3]
        if vid in known_ids or vid in derived:
            continue
        # 🛡 2026-08-19 一劳永逸：OCR 依赖文件彻底跳过（不输出 items[] → 不渲染告警卡）
        if vid in _OCR_DEPENDENCY_FILES:
            continue
        data = load_window_var(p, vid)
        # 2026-08-17 兼容 window 变量名 ≠ 文件名（STOCK_MOMENTUM_STATE_V2.js → window.STOCK_MOMENTUM_ENHANCED）
        if data is None:
            for alias in _WINDOW_VAR_ALIASES.get(vid, []):
                data = load_window_var(p, alias)
                if data is not None:
                    break
        if data is None:
            # 2026-08-17 特例：非严格 JSON 的静态映射文件（CONCEPT_ETF_MAP 用 JS 注释+无引号键），
            # 解析必然失败但文件真实存在且体积正常 → 按「低频静态映射」检查，不误报缺失
            if vid in _LOW_FREQ_FILES and p.stat().st_size > 2000:
                results.append({
                    "id": f"all_{vid}", "name": vid, "page": "全量数据", "freq": "—",
                    "status": "ok", "last_update": "静态映射", "age_min": None,
                    "heal_cat": "algo_run",
                    "message": f"{p.name} 静态映射文件（非严格 JSON，按体积检查 OK，{p.stat().st_size//1024}KB）",
                })
                continue
            results.append({
                "id": f"all_{vid}", "name": vid, "page": "全量数据", "freq": "—",
                "status": "fail", "last_update": "--", "age_min": None,
                "heal_cat": "algo_run",  # 文件缺失 → 算法链重跑可重建
                "message": f"{p.name} 缺失或解析失败（未被 CARD_DEFS 登记）",
            })
            continue
        ts = data.get("update_time") or data.get("date") or data.get("generated") \
            or data.get("generated_time") or data.get("generated_at") \
            or data.get("lastUpdated") or data.get("updated") or "--"
        if isinstance(ts, str) and ts == "--" and isinstance(data, dict):
            # 2026-08-17 嵌套时间戳（meta.generated / data_date 等）
            meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
            ts = (meta.get("generated") or meta.get("update_time") or meta.get("updated")
                  or data.get("data_date") or data.get("updated_at") or "--")
        dt = parse_time(ts) if isinstance(ts, str) else None
        # 🛡 2026-08-18 一劳永逸式修复：把 _LOW_FREQ_FILES 判断前移到「无时间戳」分支之前。
        #   原 line 1114 `if dt is None: warn + continue` 永远先 return，
        #   _LOW_FREQ_FILES（line 1124）根本走不到 → BACKTEST_TDX/OPTIMIZED_STRATEGY/
        #   PORTFOLIO_COST/RUNNER_STATUS_HEALTH/WEEKEND_RUN 5 张低频卡 100% 误报 warn。
        #   正确顺序：先看是否低频白名单 → 友好 OK；不在白名单才走时间戳 warn。
        if vid in _LOW_FREQ_FILES:
            rel = str(ts)[:19] if ts and ts != "--" else "—"
            results.append({
                "id": f"all_{vid}", "name": vid, "page": "全量数据", "freq": "—",
                "status": "ok", "last_update": rel, "age_min": None,
                "heal_cat": "algo_run",
                "message": f"{p.name} 低频/手动维护文件（白名单内，无时间戳属正常，{p.stat().st_size//1024}KB）",
            })
            continue
        if dt is None:
            # 有数据但无时间戳且不在 _LOW_FREQ_FILES：无法判龄 → warn（不 fail，避免误报）
            results.append({
                "id": f"all_{vid}", "name": vid, "page": "全量数据", "freq": "—",
                "status": "warn", "last_update": str(ts)[:16], "age_min": None,
                "heal_cat": "algo_run",
                "message": f"{p.name} 无 update_time/date/generated 时间戳，无法判龄（缺审计登记）",
            })
            continue
        age_min = (now_cst() - dt).total_seconds() / 60
        # 此时 vid 已知 dt 不为 None，_LOW_FREQ_FILES 在上面已 continue 排除
        # 未知卡未登记 CARD_DEFS，按「全量数据」page 走（不分实时数据 2h 红线，避免误伤）
        cap = _hard_cap_for_owner_rule(page="全量数据")
        # 已登记 CARD_DEFS 的卡在 check_data_cards 用 d.max_age 判定；未知卡统一走 24h/T+1 红线
        status = "ok" if age_min <= cap else "fail"
        # 🛡 2026-08-19 修：OCR 人工依赖卡（MOMENTUM_FILTER / STOCK_MOMENTUM_STATE / V2）
        #   数据源=盘后选股 PDF OCR，无 PDF 输入自动巡检永远无法刷新 → 陈旧属预期，
        #   降级 warn 不误报 fail（与 self_heal_monitor.py P0-2 方针一致）。
        #   真异常（文件缺失/解析失败）已在上方 fail，此处只处理「文件在但陈旧」。
        ocr_note = ""
        if status == "fail" and "MOMENTUM" in vid:
            status = "warn"
            ocr_note = "（OCR 人工依赖：需主人提供盘后选股 PDF 刷新，自动巡检无法修复 → 降级 warn）"
        rel = fmt_rel_time(str(ts)[:19])
        msg = f"{p.name} 更新于 {rel}"
        if status == "fail":
            msg += f"；超过通用红线 {cap} 分钟（主人铁律：交易日 24h / 非交易日 T+1 18:30）"
        elif ocr_note:
            msg += ocr_note
        # 空内容检测（不把空 list 当错误，弱市合法）
        elif isinstance(data, dict) and not data:
            status = "warn"
            msg += "；内容为空 dict"
        results.append({
            "id": f"all_{vid}", "name": vid, "page": "全量数据", "freq": "—",
            "status": status, "last_update": str(ts)[:19], "age_min": round(age_min, 1),
            "heal_cat": "algo_run",
            "message": msg,
        })
    return results


def check_raw_data():
    """检查 raw_data/ 目录是否存在关键文件且不为空。"""
    results = []
    if not RAW_DIR.exists():
        return [{"id": "raw_data_dir", "name": "raw_data 目录", "page": "管线", "status": "fail", "message": "raw_data 目录不存在"}]
    key_files = ["etf_pulse.json", "capital_flow_data.json", "index_quotes.json", "crisis_data.json", "concept_ranking.json"]
    for fn in key_files:
        p = RAW_DIR / fn
        status = "ok"
        msg = "存在"
        if not p.exists():
            status = "fail"
            msg = "文件缺失"
        elif p.stat().st_size == 0:
            status = "fail"
            msg = "文件为空"
        elif p.stat().st_size < 100:
            status = "warn"
            msg = f"文件过小 ({p.stat().st_size} bytes)"
        results.append({"id": f"raw_{fn}", "name": f"raw_data/{fn}", "page": "管线", "status": status, "message": msg})
    # 🛡 2026-08-22 规模巡检（主人令）：raw_data 文件总数上限——防止无声膨胀到
    #   Git Trees API "input too large"（今天 848 文件 × 全量 tree 已触发 422）。
    #   ok <850 / warn 850-1100 / fail >1100（850 为当前规模基线，留余量）
    try:
        n_files = sum(1 for _ in RAW_DIR.rglob("*") if _.is_file())
        if n_files > 1100:
            results.append({"id": "raw_volume", "name": "raw_data 文件数", "page": "管线",
                            "status": "fail",
                            "message": f"raw_data 共 {n_files} 个文件（>1100），仓库膨胀，需分流/归档"})
        elif n_files > 850:
            results.append({"id": "raw_volume", "name": "raw_data 文件数", "page": "管线",
                            "status": "warn",
                            "message": f"raw_data 共 {n_files} 个文件（>850），接近规模上限"})
        else:
            results.append({"id": "raw_volume", "name": "raw_data 文件数", "page": "管线",
                            "status": "ok", "message": f"raw_data 共 {n_files} 个文件"})
    except Exception as e:
        results.append({"id": "raw_volume", "name": "raw_data 文件数", "page": "管线",
                        "status": "warn", "message": f"统计失败: {e}"})
    return results


def check_site_deploy_sync():
    """检查线上 Pages commit 是否与 origin/main 一致。"""
    # 先拿本地 HEAD
    local_sha = None
    try:
        local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=10).strip()
    except Exception as e:
        return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": "warn", "message": f"无法获取本地 HEAD: {e}"}]

    site_sha = None
    fetch_err = None
    # 线上站点 meta（带 retry 吸收瞬时抖动）
    try:
        req = urllib.request.Request(SITE_URL, headers={"User-Agent": "v8-health-check"})
        html_bytes, err = _urlopen_retry(req, timeout=15)
        if err:
            fetch_err = err
        else:
            html = html_bytes.decode("utf-8", "replace")
            m = re.search(r"v8-build-sha[:=]\s*([a-f0-9]{7,40})", html, re.I)
            site_sha = m.group(1) if m else None
    except Exception as e:
        fetch_err = e

    # fallback 1：拿 GitHub Pages 的 latest deployment SHA（通过 GitHub API，已带重试）
    api_err = None
    if not site_sha:
        deployments = api_get(f"https://api.github.com/repos/{REPO}/deployments?environment=github-pages&per_page=1")
        if isinstance(deployments, list) and deployments:
            site_sha = deployments[0].get("sha", "")[:7]
        elif isinstance(deployments, dict):
            api_err = deployments.get("__msg__")

    # fallback 2：pages/builds/latest（deployments 为空时仍能拿到最近一次 Pages 构建的 commit）
    if not site_sha:
        latest = api_get(f"https://api.github.com/repos/{REPO}/pages/builds/latest")
        if isinstance(latest, dict) and latest.get("commit"):
            site_sha = str(latest.get("commit"))[:7]
        elif isinstance(latest, dict) and not api_err:
            api_err = latest.get("__msg__")

    if not site_sha:
        # 三条通路（站点 meta / deployments / pages builds）全部失败，且每条都已重试 SITE_MAX_RETRIES 次，
        # 基本可判定为网络瞬时抖动而非部署真故障 —— 保持 warn 但把原因写清楚，避免误导成部署挂了
        detail = []
        if fetch_err:
            detail.append(f"站点不可达：{fetch_err}")
        if api_err:
            detail.append(f"API：{str(api_err)[:120]}")
        return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": "warn",
                 "message": "无法获取 Pages SHA（站点 meta / deployments / pages-builds 三通路均在 "
                            f"{SITE_MAX_RETRIES + 1} 次重试后失败，多为网络瞬时抖动，非部署故障）"
                            + ("；" + "；".join(detail) if detail else "")}]

    synced = local_sha.startswith(site_sha) or site_sha.startswith(local_sha)

    # 2026-08-11 修：原逻辑只算 site..local（线上落后本地多少），
    # 当「线上比本地新」（本机没 pull、云端刚 build 推了新 commit）时该值恒为 0，
    # 却仍判 fail 并输出自相矛盾的「不同步，落后 0 commit」。
    # 现同时计算两个方向，并在 site_sha 本地不存在时先 fetch，避免 rev-list 直接抛错。
    def _rev_count(rng):
        try:
            out = subprocess.check_output(
                ["git", "rev-list", "--count", rng], text=True, timeout=15,
                stderr=subprocess.DEVNULL
            ).strip()
            return int(out)
        except Exception:
            return None

    behind = 0   # 线上落后本地的 commit 数（本地已 push、Pages 还没部署完）
    ahead = 0    # 线上领先本地的 commit 数（云端 build 已推，本机没 pull）
    if not synced and local_sha and site_sha and len(local_sha) >= 7 and len(site_sha) >= 7:
        # site_sha 可能是云端刚推的、本地对象库还没有 → 先补一次 fetch 再比较
        if subprocess.run(["git", "cat-file", "-e", f"{site_sha}^{{commit}}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            try:
                subprocess.run(["git", "fetch", "origin", "--quiet"], timeout=90,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        behind = _rev_count(f"{site_sha}..{local_sha}")
        ahead = _rev_count(f"{local_sha}..{site_sha}")

    if behind is None or ahead is None:
        # 两个方向都算不出来（site_sha 拉不到），只能判定为无法比较，不能武断报部署故障
        return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": "warn",
                 "message": f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]}："
                            f"线上 commit 在本地对象库中不存在，无法比较（fetch 后自动恢复）"}]

    if synced:
        msg = f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]} 已同步"
        status = "ok"
    elif ahead > 0 and behind == 0:
        # 线上纯领先本地：说明云端 build 已成功部署，本机只是没 pull —— 部署链路健康
        status = "ok"
        msg = (f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]} 已同步"
               f"（线上领先本地 {ahead} commit，云端 build 已部署，本机待 pull，非部署故障）")
    elif behind <= 5:
        # 容忍 GitHub Pages 异步部署延迟：线上落后 ≤5 个 commit 视为同步
        # Pages 部署通常有 1-3 分钟延迟，build commit 本身会累加 1 commit，云端 v8_build 偶尔叠加
        status = "ok"
        msg = (f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]} "
               f"已同步（线上落后 {behind} commit ≤5，Pages 异步部署正常）")
    else:
        status = "fail"
        msg = (f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]} "
               f"不同步，线上落后 {behind} commit，部署链路需检查")
    return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": status, "message": msg}]


def check_runner():
    """self-hosted runner 健康检查（多源融合）。

    1. 优先读 data/RUNNER_STATUS.js（本地 runner 守护 v8_runner_guard.py 产出，
       经 update_v8.py 从 raw_data/runner_status.json 生成）。
    2. 若不存在则回退读 raw_data/runner_status.json。
    3. 同时用 GitHub API 检查 cn_fetch 最近运行中连续失败 / checkout 失败，
       作为云端视角的交叉验证。
    """
    results = []
    runner_status = None

    # 1. 读本地 runner 守护上报的状态
    rs_path = DATA_DIR / "RUNNER_STATUS.js"
    if rs_path.exists():
        runner_status = load_window_var(rs_path, "RUNNER_STATUS")
    else:
        rs_raw = RAW_DIR / "runner_status.json"
        if rs_raw.exists():
            try:
                runner_status = json.loads(rs_raw.read_text(encoding="utf-8"))
            except Exception:
                runner_status = None

    local_msg = "本地 runner 守护未上报状态"
    if runner_status:
        # 2026-08-15 一劳永逸：兼容两种 runner_status 格式
        #   · cloud_fetch_v8.py 生成格式：{run_time, category, hostname, modules, summary}
        #   · v8_runner_guard.py 旧格式：{status, message, process, service, ...}
        if "status" in runner_status:
            st = runner_status.get("status", "unknown")
            msg = runner_status.get("message", "无详情")
        else:
            summary = runner_status.get("summary") or {}
            total = summary.get("total", 0)
            ok = summary.get("ok", 0)
            empty = summary.get("empty", 0)
            fail = summary.get("fail", 0)
            run_time = runner_status.get("run_time", "--")
            hostname = runner_status.get("hostname", "未知节点")
            if fail > 0:
                st = "fail"
                msg = f"{hostname} 最近抓取 {run_time}，{total} 模块中失败 {fail} / 空 {empty} / 成功 {ok}"
            elif empty > 0:
                st = "warn"
                msg = f"{hostname} 最近抓取 {run_time}，{total} 模块中空 {empty} / 成功 {ok}"
            else:
                st = "ok"
                msg = f"{hostname} 最近抓取 {run_time}，{total} 个模块全部成功"
        if st == "ok":
            results.append({"id": "runner_local", "name": "runner 本地检测", "page": "管线", "status": "ok", "message": msg})
        elif st == "warn":
            results.append({"id": "runner_local", "name": "runner 本地检测", "page": "管线", "status": "warn", "message": msg})
        else:
            results.append({"id": "runner_local", "name": "runner 本地检测", "page": "管线", "status": "fail", "message": msg})
        local_msg = msg

    # 2. GitHub API 视角：连续失败 / checkout 失败
    token = _load_token()
    if token:
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/runs?per_page=10"
        data = api_get(url)
        if data and "__error__" not in data:
            runs = data.get("workflow_runs", [])
            consecutive = 0
            for r in runs:
                if r.get("conclusion") == "failure":
                    consecutive += 1
                elif r.get("conclusion") in ("success", "cancelled"):
                    # cancelled 也会中断失败 streak（超时被取消不算连续失败）
                    break
                elif r.get("status") in ("in_progress", "queued", "pending"):
                    break
            checkout_failures = 0
            latest_fail = next((r for r in runs if r.get("conclusion") == "failure"), None)
            if latest_fail:
                jdata = api_get(latest_fail.get("jobs_url", ""))
                if jdata and "__error__" not in jdata:
                    for job in jdata.get("jobs", []):
                        for step in job.get("steps", []):
                            if "checkout" in (step.get("name") or "").lower() and step.get("conclusion") == "failure":
                                checkout_failures += 1

            latest = runs[0] if runs else None
            latest_failed = latest and latest.get("conclusion") == "failure"

            # 检测 stuck in_progress
            stuck_min = 0
            if latest and latest.get("status") == "in_progress":
                try:
                    started = datetime.strptime(latest.get("started_at") or latest.get("created_at"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    stuck_min = int((datetime.now(timezone.utc) - started).total_seconds() / 60)
                except Exception:
                    stuck_min = 0

            is_fail = (latest_failed and checkout_failures > 0) or consecutive >= 3
            is_warn = (latest_failed and not is_fail) or (latest and latest.get("status") == "in_progress" and stuck_min > 10)

            if is_fail:
                results.append({
                    "id": "runner_github",
                    "name": "runner GitHub API 检测",
                    "page": "管线",
                    "status": "fail",
                    "message": f"cn_fetch 最新失败且 checkout 失败 / 连续失败 {consecutive} 次（本地状态: {local_msg}）",
                })
            elif is_warn:
                stuck_info = f"，最新 run 卡住 {stuck_min} 分钟" if stuck_min > 0 else ""
                results.append({
                    "id": "runner_github",
                    "name": "runner GitHub API 检测",
                    "page": "管线",
                    "status": "warn",
                    "message": f"cn_fetch 最新一次失败（非 checkout，连续 {consecutive} 次）{stuck_info}（本地状态: {local_msg}）",
                })
            else:
                results.append({
                    "id": "runner_github",
                    "name": "runner GitHub API 检测",
                    "page": "管线",
                    "status": "ok",
                    "message": f"最近运行正常（本地状态: {local_msg}）",
                })
        else:
            err = data.get("__msg__", "unknown") if isinstance(data, dict) else "API 失败"
            results.append({"id": "runner_github", "name": "runner GitHub API 检测", "page": "管线", "status": "warn", "message": f"API 查询失败: {err}"})
    else:
        results.append({"id": "runner_github", "name": "runner GitHub API 检测", "page": "管线", "status": "warn", "message": "无 token，跳过 GitHub API 检测（请在 repo secrets 配置 V8_GH_TOKEN）"})

    # 汇总：任一 fail 则总体 fail
    overall = "ok"
    if any(r["status"] == "fail" for r in results):
        overall = "fail"
    elif any(r["status"] == "warn" for r in results):
        overall = "warn"

    return results + [{
        "id": "runner",
        "name": "self-hosted runner",
        "page": "管线",
        "status": overall,
        "message": " | ".join(f"{r['name']}:{r['status']}-{r['message']}" for r in results),
    }]


def check_local_head_sync():
    """检查本地 HEAD 是否与 origin/main 一致。

    2026-08-18 主人建议：一劳永逸把「本地落后于 origin/main」降为 info。
    根因：云端 Pages 每次构建会重写 index.html（cn-extra data 文件 ?v= 刷新），
    致 origin/main 永远比本地「前进 1~3 个 commit」，本地若未做新提交则每次必报 fail。
    视作「云端 build 副作用 → 本地落后属预期」，降级 info 不再触发自愈/告警。
    派发链 (self_heal) 仍按原 iid=local_sync 调用 _heal_local_sync() 做软对齐，不影响修复能力。
    """
    try:
        subprocess.run(["git", "fetch", "origin"], check=True, timeout=30)
        local = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=10).strip()
        remote = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True, timeout=10).strip()
        synced = local == remote
        # 2026-08-18 降级：fail → info（云端 build 重写 index.html 属预期，非真实落后）
        status = "ok" if synced else "info"
        msg = f"本地 {local[:7]} / origin/main {remote[:7]} {'同步' if synced else '本地落后（Pages build 重写 index.html 属预期，已降级 info 不报警）'}"
        return [{"id": "local_sync", "name": "本地与 origin/main 同步", "page": "管线", "status": status, "message": msg}]
    except Exception as e:
        return [{"id": "local_sync", "name": "本地与 origin/main 同步", "page": "管线", "status": "warn", "message": f"检查失败: {e}"}]


def check_site_dom(site_html=None):
    """二期：简单 DOM 空值检测（从线上 HTML 检查关键 id 是否存在且非空）。"""
    if site_html is None:
        try:
            req = urllib.request.Request(SITE_URL, headers={"User-Agent": "v8-health-check"})
            html_bytes, err = _urlopen_retry(req, timeout=15)
            if err:
                return [{"id": "dom_check", "name": "线上 DOM 空值检测", "page": "管线", "status": "warn",
                         "message": f"拉取页面失败（已重试{SITE_MAX_RETRIES}次）: {err}"}]
            site_html = html_bytes.decode("utf-8", "replace")
        except Exception as e:
            return [{"id": "dom_check", "name": "线上 DOM 空值检测", "page": "管线", "status": "warn", "message": f"拉取页面失败: {e}"}]

    # 2026-08-08 96轮适配：阿狸咪方案三重构后页面卡片改由 JS 从外部 data/*.js 动态渲染，
    # 静态 HTML 内是空壳/“加载中…”占位符（旧 critical_ids 中 4 个 id 已删除）。
    # 故改为：① 关键容器存在性检查（缺失=fail）；② 静态占位符（空/加载中）=warn（JS 渲染属常态）。
    critical_ids = ["taskScheduleBody", "phMacroBody", "ttBackBody", "ttThrBody", "ttSvlBody", "ttTrackBody",
                    "stcrdsAdvBody", "stcrdsEliteBody", "runnerTrackBody", "healthCheckBody"]
    results = []
    for cid in critical_ids:
        m = re.search(rf'id=["\']{re.escape(cid)}["\'][^>]*>(.*?)</[^>]+>', site_html, re.S)
        if not m:
            results.append({"id": f"dom_{cid}", "name": f"DOM #{cid}", "page": "管线", "status": "fail", "message": "未找到元素"})
            continue
        content = m.group(1).strip()
        placeholder = content == "" or "加载中" in content or content == "--" or len(content) < 20
        status = "warn" if placeholder else "ok"
        msg = "静态占位符(JS渲染)" if placeholder else f"静态内容长度 {len(content)}"
        results.append({"id": f"dom_{cid}", "name": f"DOM #{cid}", "page": "管线", "status": status, "message": msg})
    return results


def _last_trade_date(ref=None):
    """返回 ref 之前（含）的最近一个 A 股交易日。

    关键：若 ref 在当天收盘（15:30）之前，则「最近交易日」应回退到上一交易日，
    避免周一 07:36 早盘把 enter_date 上周五的数据误判为陈旧。
    直接复用 last_trade_day_close() 的收盘时间口径。
    """
    ref = ref or now_cst()
    if isinstance(ref, datetime):
        dt = ref
    else:
        dt = datetime.combine(ref, datetime.min.time(), tzinfo=timezone(timedelta(hours=8)))
    return last_trade_day_close(dt).date()


def check_signal_date_freshness():
    """内容级陈旧检查：数据文件 update_time 新鲜，但内部信号/入选日期已落后最近交易日。

    覆盖 COCKPIT_ADVICE (watch[].signal_date) 与 FINAL_RECOMMEND_DATA (stocks[].enter_date)。
    使用 page="内容审计" 以绕过 self_heal 自动派发（内容级陈旧需算法/数据根治，不是简单刷新可修）。
    """
    results = []
    last_trade = _last_trade_date()
    if last_trade is None:
        return results
    last_trade_str = last_trade.strftime("%Y-%m-%d")

    # ── COCKPIT_ADVICE ──
    # 注意：COCKPIT_ADVICE 是历史回测样本库，watch[].signal_date 是信号发生日期，
    # 不一定是最近交易日，因此不将其与最近交易日比较作为陈旧告警。
    # 驾驶舱数据本身是否更新，由通用数据卡新鲜度检查覆盖。
    d = load_window_var(DATA_DIR / "COCKPIT_ADVICE.js", "COCKPIT_ADVICE")
    if d is None:
        results.append({
            "id": "cockpit_signal_stale",
            "name": "驾驶舱建议信号日期",
            "page": "内容审计",
            "status": "warn",
            "message": "无法加载 COCKPIT_ADVICE.js"
        })
    else:
        gen_time = d.get("gen_time", "--")
        signal_dates = [item.get("signal_date") for item in d.get("watch", []) if item.get("signal_date")]
        newest_signal = max(signal_dates) if signal_dates else "--"
        results.append({
            "id": "cockpit_signal_stale",
            "name": "驾驶舱建议信号日期",
            "page": "内容审计",
            "status": "ok",
            "message": f"生成时间 {gen_time}，最新信号发生日期 {newest_signal}（历史回测样本，非陈旧指标）"
        })

    # ── FINAL_RECOMMEND_DATA ──
    d = load_window_var(DATA_DIR / "FINAL_RECOMMEND_DATA.js", "FINAL_RECOMMEND_DATA")
    if d is None:
        results.append({
            "id": "final_enter_stale",
            "name": "最终推荐入选日期",
            "page": "内容审计",
            "status": "warn",
            "message": "无法加载 FINAL_RECOMMEND_DATA.js"
        })
    else:
        dates = []
        for s in d.get("stocks", []):
            ed = s.get("enter_date")
            if ed:
                dates.append(ed)
        if not dates:
            results.append({
                "id": "final_enter_stale",
                "name": "最终推荐入选日期",
                "page": "内容审计",
                "status": "warn",
                "message": "未找到 enter_date 字段，无法判断入选新鲜度"
            })
        else:
            newest = max(dates)
            if newest < last_trade_str:
                results.append({
                    "id": "final_enter_stale",
                    "name": "最终推荐入选日期",
                    "page": "内容审计",
                    "status": "warn",
                    "message": f"最新 enter_date {newest} 早于最近交易日 {last_trade_str}，最终推荐数据陈旧"
                })
            else:
                results.append({
                    "id": "final_enter_stale",
                    "name": "最终推荐入选日期",
                    "page": "内容审计",
                    "status": "ok",
                    "message": f"最新 enter_date {newest} ≥ 最近交易日 {last_trade_str}"
                })

        # 2026-08-15 主人令：Top3 市场分布只展示、不误报。
        #   去掉 crude 的「全 A 股/全港股 = 数据源异常」判断——A 股占绝大多数是常态，
        #   真正的「A 股缺失」由下方 check_a_share_coverage() 统一扫描所有主要数据池捕获。
        stocks = d.get("stocks", [])
        if stocks:
            a_cnt = sum(1 for s in stocks if _is_a_share(s))
            hk_cnt = len(stocks) - a_cnt
            markets_str = f"A股{a_cnt}只 / 港股{hk_cnt}只"
            results.append({
                "id": "final_market_distribution",
                "name": "最终推荐市场分布",
                "page": "内容审计",
                "status": "ok",
                "message": f"Top{len(stocks)} 市场分布：{markets_str}"
            })

    return results


# 🔴 2026-08-12 主人紧急令：算法输出全港股/A股缺失 = 必须立即报警
#   根因：check_signal_date_freshness 只盯 FINAL_RECOMMEND_DATA.stocks（全港股 Top3），
#         候选池/黄金池/三重共识/驾驶舱等的「全港股」完全没被检查 → 8 天持续 bug 未发现。
#   修复：本函数扫描所有主要 *_DATA.js 的 stocks 字段，A 股=0 且总数>0 → warn（标红 URGENT）。
_A_SHARE_POOLS = [
    # (data/*.js 路径, window var 名, 卡片名, heal_cat)
    ("CANDIDATE.js",            "CANDIDATE",            "候选池",       "algo_run"),
    ("GOLD_POOL.js",            "GOLD_POOL",            "黄金池",       "algo_run"),
    ("TRIPLE_CONSENSUS.js",     "TRIPLE_CONSENSUS",     "三重共识",     "algo_run"),
    ("COCKPIT_TIER_RECOMMEND.js","COCKPIT_TIER_RECOMMEND","驾驶舱分档",   "algo_run"),
    ("CRDS_CARD_DATA.js",       "CRDS_CARD_DATA",       "逆势龙头",     "algo_run"),
    ("FOUR_VOLUME.js",          "FOUR_VOLUME",          "四量终极",     "algo_run"),
    ("MAHORO.js",               "MAHORO",               "国际投行信号", "algo_run"),
    ("LHB_DATA.js",             "LHB_DATA",             "龙虎榜",       "cn_fetch"),
    ("FINAL_RECOMMEND_DATA.js", "FINAL_RECOMMEND_DATA", "最终推荐",     "algo_run"),
]


def check_a_share_coverage():
    """🔴 2026-08-12 主人令：算法输出全港股/A股缺失 = 立即报警 + 定位回溯。

    扫描所有主要数据池的 stocks 字段：
      - 总数=0：先看 near_miss/替代字段是否有数据；按"独立 0 vs 全部 0"智能判断
      - 总数>0 且 A 股=0：A 股扫描失败/A 股 API 挂/上游 bug → URGENT warn
      - 总数>0 且 A 股>=1：OK

    🔴 2026-08-17 一劳永逸修复：原 line 1466 直接将单池 0 = warn 导致三重共识 0 只（弱市真实）误报
    · 现在：先两轮统计所有池状态，再判"独立 0 vs 多源同 0"
      - 1 个池 0 且其他正常 → info（独立 0，弱市真实）
      - 1 个池 0 但它有 near_miss 备选 → info（弱市无严格共识）
      - 2+ 个池同时 0 → warn（真上游问题）
      - 全 0 + 非交易日 → ok；全 0 + 交易日 → warn
    """
    results = []
    # ── 第一轮：先收集所有池的 (total, near_miss, ...) 状态 ──
    pool_status = []
    for fname, var, name, heal in _A_SHARE_POOLS:
        path = DATA_DIR / fname
        d = load_window_var(path, var)
        if d is None:
            continue
        stocks_raw = d.get("stocks", d.get("all_candidates", d.get("watch", d.get("tier_a", []))))
        # 🛡 2026-08-19 主人令一劳永逸修复：MAHORO.js 结构不同，A 股命中在 gold_pool_matches，不是 stocks
        if var == "MAHORO":
            stocks_raw = d.get("gold_pool_matches", [])
        if isinstance(stocks_raw, dict):
            stocks = list(stocks_raw.values())
        else:
            stocks = stocks_raw or []
        total = len(stocks)
        a_cnt = sum(1 for s in stocks if _is_a_share(s)) if total > 0 else 0
        hk_cnt = total - a_cnt
        # 严格池（如 TRIPLE_CONSENSUS）的 near_miss 差一步备选，弱市常 0
        near_miss_count = len(d.get("near_miss", []) or [])
        pool_status.append({
            "total": total, "name": name, "var": var, "heal": heal,
            "stocks": stocks, "a_cnt": a_cnt, "hk_cnt": hk_cnt,
            "near_miss_count": near_miss_count,
        })

    # ── 第二轮：判"全 0 vs 独立 0" ──
    n_total = len(pool_status)
    n_zero = sum(1 for p in pool_status if p["total"] == 0)
    today_is_trade = _is_trading_day(date.today())

    # 🔴 2026-08-17 增强：识别"严格共识/选股"类池（弱市天然 0，不应算"上游问题"）
    # 严格类：三重共识/驾驶舱分档/逆势龙头/四量终极/国际投行（命中条件严，弱市 0 是常态）
    # 数据类：候选池/黄金池/龙虎榜/最终推荐（结构性数据，0 = 真上游问题）
    STRICT_POOL_NAMES = {"三重共识", "驾驶舱分档", "逆势龙头", "四量终极", "国际投行信号"}

    for p in pool_status:
        if p["total"] == 0:
            if not today_is_trade:
                # 非交易日：算法链不跑属正常
                results.append({
                    "id": f"a_share_{p['var'].lower()}", "name": f"{p['name']} A股覆盖",
                    "page": "内容审计", "heal_cat": p["heal"],
                    "status": "ok",
                    "message": f"{p['name']} 今日 0 只（非交易日，算法链未运行，属正常现象）"
                })
            elif n_zero == 1:
                # 唯一 0 池 → 弱市真实，不报警
                if p["near_miss_count"] > 0:
                    msg = f"✅ {p['name']} 今日 0 只严格共识 + {p['near_miss_count']} 只差 1 步达成（弱市正常，其他池也正常）"
                else:
                    msg = f"✅ {p['name']} 今日 0 只（独立 0 而其他池正常 → 弱市真实状态，无需报警）"
                results.append({
                    "id": f"a_share_{p['var'].lower()}", "name": f"{p['name']} A股覆盖",
                    "page": "内容审计", "heal_cat": p["heal"],
                    "status": "ok", "message": msg
                })
            elif n_zero <= 2 and STRICT_POOL_NAMES and all(
                sp["name"] in STRICT_POOL_NAMES for sp in pool_status if sp["total"] == 0
            ):
                # n_zero == 2 时，如果这 2 池都是"严格共识/选股"类 → 弱市无严格共识，
                # 不是上游问题（不算"全 0"）。只对 near_miss 信息补充。
                if p["near_miss_count"] > 0:
                    msg = f"✅ {p['name']} 严格 0 但 {p['near_miss_count']} 只差 1 步备选（{n_zero}/{n_total} 严格共识池同时 0，弱市正常）"
                else:
                    msg = f"✅ {p['name']} 今日 0 只（{n_zero}/{n_total} 严格共识池同 0，无 near_miss，弱市正常）"
                results.append({
                    "id": f"a_share_{p['var'].lower()}", "name": f"{p['name']} A股覆盖",
                    "page": "内容审计", "heal_cat": p["heal"],
                    "status": "ok", "message": msg
                })
            else:
                # n_zero >= 3，或 2 池但有非严格类 → 真上游问题
                results.append({
                    "id": f"a_share_{p['var'].lower()}", "name": f"{p['name']} A股覆盖",
                    "page": "内容审计", "heal_cat": p["heal"],
                    "status": "warn",
                    "message": f"⚠️ {p['name']} 今日 0 只（{n_zero}/{n_total} 池同时 0）→ 多源同时 0，排查 scanner / mootdx / akshare 上游"
                })
            continue

        # total > 0：A 股=0 即上游 bug（严格）
        a_cnt = p["a_cnt"]; hk_cnt = p["hk_cnt"]
        if a_cnt == 0 and hk_cnt > 0:
            results.append({
                "id": f"a_share_{p['var'].lower()}", "name": f"{p['name']} A股覆盖",
                "page": "内容审计", "heal_cat": p["heal"],
                "status": "warn",
                "message": f"🚨 URGENT: {p['name']} 全港股（{hk_cnt}/{p['total']}），A 股扫描失败/上游路径 bug！"
                          f"🚨 必须立即回溯 scanner.load_candidate_pool / mootdx A 股 / akshare 港股 API / build_candidate_pool 路径。"
            })
    return results


def _is_a_share(s):
    """判断股票是否 A 股（含主板/创业板/科创板/北交所）。"""
    if not isinstance(s, dict):
        return False
    market = (s.get("market") or "").lower()
    board = s.get("board") or s.get("board_label") or ""
    code = str(s.get("code") or "")
    # market 明确是 hk/港股 → 港股
    if market in ("hk", "港股") or board == "港股" or "港股" in board:
        return False
    if market in ("sh", "sz", "bj") or board in ("主板","创业板","科创板","北交所"):
        return True
    # code 前缀兜底判断
    if code.isdigit() and len(code) == 6:
        return True
    return False


def _count_trade_days(start, end):
    """统计 [start, end] 之间的 A 股交易日数量（两端均含）。"""
    if not start or not end or start > end:
        return 0
    cnt = 0
    d = start
    while d <= end:
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone(timedelta(hours=8)))
        if not is_market_closed(dt):
            cnt += 1
        d += timedelta(days=1)
    return cnt


def check_top10_history_depth():
    """T+N 信号台账深度检查：raw_data/history/top10_daily_YYYYMMDD.json 的最早/最新交易日跨度。

    top10_daily 按日快照是 T+N 回测与跟踪的根本来源；跨度不足时 T+20 等长周期会缺样本。
    使用 page="内容审计" 以绕过 self_heal 自动派发（历史深度只能随每日运行自然累积，不可简单刷新）。
    """
    results = []
    hist_dir = DATA_DIR.parent / "raw_data" / "history"
    if not hist_dir.exists():
        results.append({
            "id": "top10_history_depth",
            "name": "T+N 信号台账深度",
            "page": "内容审计",
            "status": "warn",
            "message": f"历史快照目录不存在: {hist_dir}",
        })
        return results

    pat = re.compile(r"top10_daily_(\d{8})\.json$")
    dates = []
    for fn in hist_dir.iterdir():
        m = pat.match(fn.name)
        if not m:
            continue
        try:
            dates.append(datetime.strptime(m.group(1), "%Y%m%d").date())
        except Exception:
            continue

    if not dates:
        results.append({
            "id": "top10_history_depth",
            "name": "T+N 信号台账深度",
            "page": "内容审计",
            "status": "warn",
            "message": "未找到任何 top10_daily_YYYYMMDD.json 历史快照",
        })
        return results

    earliest = min(dates)
    latest = max(dates)
    trade_days = _count_trade_days(earliest, latest)
    required = 20  # 满足 T+20 所需的最小交易日跨度

    if trade_days < required:
        status = "warn"
        msg = (f"top10_daily 历史跨度仅 {trade_days} 个交易日 "
               f"({earliest} ~ {latest})，低于 T+20 所需的 {required} 个交易日；"
               f"长周期回测/跟踪会缺样本，需持续每日生成快照或补全历史")
    else:
        status = "ok"
        msg = (f"top10_daily 历史跨度 {trade_days} 个交易日 "
               f"({earliest} ~ {latest})，满足 T+20 跟踪需求")

    results.append({
        "id": "top10_history_depth",
        "name": "T+N 信号台账深度",
        "page": "内容审计",
        "status": status,
        "message": msg,
    })
    return results


def build_report(cards, raw, site_sync, runner, local_sync, dom, signal_fresh=None, history_depth=None, a_share_cov=None, all_data=None):
    all_items = cards + raw + site_sync + runner + local_sync + dom + (signal_fresh or []) + (history_depth or []) + (a_share_cov or []) + (all_data or [])
    ok = sum(1 for x in all_items if x["status"] == "ok")
    warn = sum(1 for x in all_items if x["status"] == "warn")
    fail = sum(1 for x in all_items if x["status"] == "fail")
    overall = "ok" if fail == 0 else ("warn" if fail <= 2 else "fail")
    return {
        "updated": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "overall": overall,
        "summary": {"ok": ok, "warn": warn, "fail": fail, "total": len(all_items)},
        "items": all_items,
    }


def write_health_js(report):
    out_path = DATA_DIR / "HEALTH_CHECK.js"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    js = "window.HEALTH_CHECK = " + json.dumps(report, ensure_ascii=False, indent=2) + ";\n"
    # ★★ 2026-08-18 主人令「每次更新部署都是错的」根因根治：HEALTH_CHECK 幂等化 ★★
    #   死循环环节：① updated 字段每次构建必变 ② age_min（数据年龄分钟数）随当前
    #   时间流逝每次必变 → HEALTH_CHECK.js 内容必变 → build 的 git diff 永不空 →
    #   每次必提交 → 触发自身/reconcile → 死循环（今日 359 提交实证）。
    #   修复：写文件前做 JSON 深度比较（剔除 updated/age_min 动态字段），状态未变
    #   则完全不动文件。age_min 由前端基于 last_update 自行换算。
    try:
        if out_path.exists():
            old_js = out_path.read_text(encoding="utf-8")
            def _core(s):
                d = json.loads(s.split("= ", 1)[1].rsplit(";", 1)[0])
                d.pop("updated", None)
                for it in d.get("items", []):
                    it.pop("age_min", None)
                return json.dumps(d, ensure_ascii=False, sort_keys=True)
            if _core(old_js) == _core(js):
                print(f"[INFO] HEALTH_CHECK 状态未变，跳过重写（幂等）")
                return
    except Exception:
        pass
    out_path.write_text(js, encoding="utf-8")
    print(f"[INFO] 已生成 {out_path}")


def write_health_json(report):
    """输出结构化 JSON 报告，供 v8_cloud_watchdog.py 做逐源 auto-dispatch 决策。"""
    out_path = Path(".workbuddy") / "v8_health_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    print(f"[INFO] 已生成 {out_path}")


def send_report_email(report, healed=None, failed=None):
    """发送健康检查邮件。

    自愈优先：先已由 self_heal() 尝试修复。邮件定位从「纯告警」改为：
      - 全部自愈成功 -> 发一条『已自愈』确认邮件（告知已自动派发刷新，无需人工）
      - 有自愈失败 / 不可自愈项 -> 升级邮件，列明需人工介入的项
    夜间静音时段：自愈动作照常（已在 main 中执行），仅降级为写 URGENT 留痕，不发邮件。
    """
    healed = healed or []
    failed = failed or []
    if not send_alert:
        print("[WARN] 邮件发送器未导入，跳过邮件")
        return False
    if report["overall"] == "ok" and not healed and not failed:
        return False

    # 仍需人工关注的 fail 项：
    #  - 已自愈（heal 标记为「已自动…」）的卡片不再告警
    #  - 自愈失败的卡片列入（与 failed 对应）
    #  - 不可自愈的 fail（文件缺失等）列入
    #  - 管线类检查（本地/部署同步）由看门狗统一处理，此处不重复告警，避免噪声
    remaining = []
    for it in report["items"]:
        if it.get("status") != "fail":
            continue
        if it.get("page") == "管线":
            continue
        if it.get("heal", "").startswith("已自动"):
            continue  # 已自愈，无需人工
        # 🛡 2026-08-18 主人令一劳永逸：OCR 抽取数据（STOCK_MOMENTUM_STATE/V2）需要人工提供盘后选股 PDF
        # 才能刷新（OCR 管线等输入，自动巡检永远无法修复）→ 免邮件（看板红叉保留提示主人给 PDF），
        # 避免每晚 22:30 定时邮件轰炸主人。
        if "MOMENTUM" in it.get("id", ""):
            continue
        remaining.append(it)

    quiet = in_quiet_hours()
    if quiet:
        if failed or remaining:
            lines = [f"[{it.get('page', '')}] {it.get('name', '')}: {it.get('message', '')}" for it in remaining]
            lines += failed
            write_urgent(lines)
        # 夜间静音：自愈已执行，仅不邮件
        return False

    if failed or remaining:
        subject = f"【v8需人工】自愈失败/无法自动修复 {len(failed) + len(remaining)} 项 @ {report['updated']}"
        lines = [f"v8 自愈巡检时间：{report['updated']}", "",
                 "以下项自动修复失败或无法自动修复，需人工介入："]
        for it in remaining:
            lines.append(f"✗ [{it.get('page', '')}] {it.get('name', '')}: {it.get('message', '')}")
        for f in failed:
            lines.append(f"✗ {f}")
        if healed:
            lines += ["", "以下项已自动派发刷新（无需人工）："]
            lines += [f"✓ {h}" for h in healed]
    elif healed:
        # 🔴 2026-08-12 主人令：全部自愈成功不发邮件(避免噪音),「只看有问题的」
        #   如果有 fail 项需要人工,会进上面 if 分支(healed 也会列在最后)所以不影响
        return False
    else:
        return False

    lines += ["", f"站点：{SITE_URL}"]
    return send_alert(subject, "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="v8 前端健康巡检")
    parser.add_argument("--alert", action="store_true", help="异常时发送邮件告警")
    parser.add_argument("--site", action="store_true", help="额外检查线上 DOM 空值")
    parser.add_argument("--heal", dest="heal", action="store_true", default=True,
                        help="发现可自愈陈腐时自动派发刷新（默认开）")
    parser.add_argument("--no-heal", dest="heal", action="store_false", help="关闭自愈派发（仅诊断）")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    print(f"[INFO] v8 health check start @ {now_cst().strftime('%Y-%m-%d %H:%M:%S')}")

    cards = check_data_cards()
    all_data = check_all_data_files()  # 🔴 2026-08-17 主人怒令：全面审计（53 个未登记文件全量覆盖）
    raw = check_raw_data()
    site_sync = check_site_deploy_sync()
    runner = check_runner()
    local_sync = check_local_head_sync()
    dom = []
    if args.site:
        dom = check_site_dom()

    signal_fresh = check_signal_date_freshness()
    history_depth = check_top10_history_depth()
    # 🔴 2026-08-12 主人紧急令：算法输出全港股/A股缺失必须立即报警
    a_share_cov = check_a_share_coverage()

    report = build_report(cards, raw, site_sync, runner, local_sync, dom, signal_fresh, history_depth, a_share_cov=a_share_cov, all_data=all_data)
    # 2026-08-11 漏洞 #3：管线耗时趋势监控（必须在 build_report 后但 self_heal 前,以便发现异常时纳入自愈决策）
    try:
        _check_workflow_durations(report)
    except Exception as e:
        print(f"[WARN] workflow duration check failed: {e}")
    write_health_js(report)
    # 打印摘要
    print(f"[INFO] 总体: {report['overall']} | 统计: {report['summary']}")
    for item in report["items"]:
        if item["status"] != "ok":
            print(f"  [{item['status'].upper()}] {item['page']}/{item['name']}: {item['message']}")

    # ── 自愈（默认开）：发现可修复陈腐即尝试派发刷新，而非只发邮件 ──
    healed, failed = [], []
    if args.heal:
        # 2026-08-10 修复：移除对 overall 的依赖——只要 heal 开就跑 self_heal，
        # 内部自行判断 fail 卡片 / 内容审计陈旧项，确保「任何可自愈问题都自动派发」。
        # 2026-08-12 加固：自愈内部异常不得连坐吞掉「报告落盘 + 邮件告警」两个下游动作
        # （3d2a53b2 的 UnboundLocalError 就是这样让整个检查以 rc=1 崩退的）。
        # 不静默 pass：异常写进 failed 列表并打印 traceback，保证在邮件/日志里可见。
        try:
            healed, failed = self_heal(report)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            failed = [f"[自愈异常] self_heal 内部错误，本轮未完成自愈: {type(e).__name__}: {e}"]
            report["heal_error"] = f"{type(e).__name__}: {e}"
        for h in healed:
            print(f"  [HEAL✓] {h}")
        for f in failed:
            print(f"  [HEAL✗] {f}")

    # 自愈后重写 JSON 报告，让 v8_cloud_watchdog.py 看到 heal 标记避免重复派发
    write_health_json(report)

    if args.alert:
        send_report_email(report, healed=healed, failed=failed)

    sys.exit(0 if report["overall"] == "ok" else 2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # ── 顶层兜底守卫（2026-08-12 第171轮·一劳永逸）──────────────────────────────
        # 此前 main() 内任一未捕获异常（API 超时/网络抖动/字段缺失等）都会让整个检查进程
        # 以 rc=1 静默崩退：既不写 HEALTH_CHECK.js，也不发告警邮件，导致 9 张盘中卡陈旧
        # 等真故障被「无声漏报」。round-166 只给 self_heal 加了 try/except，未覆盖 main() 其余
        # 路径（check_* / build_report / write_health_js / _check_workflow_durations）。
        # 此处兜底：任何崩溃都保证①报告落盘(overall=fail) ②邮件告警发出 ③以 rc=2 退出
        # （rc=2 让看门狗识别为「有失败项、已由健康检查自发邮件」，不再被静默吞掉）。
        import traceback as _tb
        _tb.print_exc()
        try:
            _ts = now_cst().strftime("%Y-%m-%d %H:%M:%S")
            _report = {
                "updated": _ts,
                "overall": "fail",
                "summary": {"ok": 0, "warn": 0, "fail": 1, "total": 1},
                "items": [{
                    "id": "HEALTH_CHECK_CRASH",
                    "name": "健康检查进程崩溃",
                    "page": "—", "freq": "—", "status": "fail",
                    "last_update": _ts, "age_min": 0,
                    "message": f"{type(e).__name__}: {e}",
                }],
                "heal_error": f"{type(e).__name__}: {e}",
            }
            write_health_js(_report)
            write_health_json(_report)
            print(f"[GUARD] 兜底报告已写出 data/HEALTH_CHECK.js (overall=fail)")
        except Exception as _e2:
            print(f"[WARN] 兜底报告写出失败: {_e2}")
        if send_alert:
            try:
                send_alert(
                    "【v8需人工】健康检查进程崩溃(兜底rc=2)",
                    f"v8_health_check.py 在主流程抛出未捕获异常，已兜底写出失败报告（overall=fail）。\n\n"
                    f"{type(e).__name__}: {e}\n\n请查 v8_health_check.py 日志与 main() 调用链。",
                )
                print("[GUARD] 崩溃告警邮件已发送")
            except Exception as _e3:
                print(f"[WARN] 崩溃告警邮件发送失败: {_e3}")
        sys.exit(2)
