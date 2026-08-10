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
from datetime import datetime, timezone, timedelta
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
    {"id": "MACRO_DATA", "name": "今日宏观解读", "page": "今日事件", "freq": "每日盘前", "max_age": 360, "key_fields": ["global_macro", "monetary"], "weekend_update": False},
    {"id": "NT_DATA", "name": "市场提示", "page": "今日事件", "freq": "每日盘前", "max_age": 720, "key_fields": ["alerts"], "weekend_update": False},
    # 实时数据
    {"id": "INDEX_QUOTES", "name": "全球指数 / 股指期货", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["items"]},
    {"id": "ETF_PULSE", "name": "ETF 盘中异动", "page": "实时数据", "freq": "盘中实时", "max_age": 60, "key_fields": ["etfs"]},
    {"id": "ETF_INTRADAY_HEAT", "name": "ETF 资金热度", "page": "实时数据", "freq": "盘中实时 T+0", "max_age": 60, "key_fields": ["items"]},
    {"id": "ETF_DAILY_MONITOR", "name": "ETF 日监控", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["top_inflow", "top_outflow"]},
    {"id": "SECTOR_FUND_FLOW", "name": "板块资金流向", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["top_list"]},
    {"id": "CONCEPT_RANKING", "name": "概念排名", "page": "实时数据", "freq": "盘中每30分", "max_age": 90, "key_fields": ["items"]},
    {"id": "LIMIT_UP_HEATMAP", "name": "涨停热度", "page": "实时数据", "freq": "盘中每30分", "max_age": 90, "key_fields": ["top", "dates"]},
    {"id": "MARKET_FUND_FLOW_DATA", "name": "市场资金流向", "page": "实时数据", "freq": "盘中每30分", "max_age": 60, "key_fields": ["daily"]},
    {"id": "MARKET_ALERTS", "name": "市场预警", "page": "实时数据", "freq": "盘中实时", "max_age": 60, "key_fields": ["indices"]},
    # 盘后数据
    {"id": "SH_FIB", "name": "市场温度计", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["windows", "current"]},
    {"id": "MARGIN_DATA", "name": "融资融券", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["sh"]},
    {"id": "CFFEX_HOLDINGS", "name": "股指期货持仓", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["items"]},
    {"id": "CRISIS_DATA", "name": "危机雷达", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["currency", "global"]},
    {"id": "MARKET_FUND_FLOW_DATA", "name": "盘后资金流向", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["daily"]},
    {"id": "CANDIDATE", "name": "候选池", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},
    {"id": "GOLD_POOL", "name": "黄金池", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},
    {"id": "LHB_DATA", "name": "龙虎榜", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},
    {"id": "INST_TRADE", "name": "机构买卖", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["top_buy", "top_sell"]},
    {"id": "TRIPLE_CONSENSUS", "name": "三重共识", "page": "盘后数据", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},
    # 选股策略
    {"id": "FOUR_VOLUME", "name": "四量终极", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},
    {"id": "COCKPIT_ADVICE", "name": "驾驶舱", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["verdict", "watch"]},
    {"id": "BIG_BULL_HUNTER", "name": "大牛股猎手", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["stocks"]},  # 派生自 lhb+inst_trade，data/BIG_BULL_HUNTER.js 待生成；当前复用源数据 lhb_data.js
    {"id": "TOP10_DAILY", "name": "全站精选", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["top10"]},
    {"id": "STOCK_RPS", "name": "相对强度", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["records"], "_window_var": "STOCK_RPS_DATA"},  # 文件名 STOCK_RPS.js，但 window 变量名是 STOCK_RPS_DATA（历史遗留）
    {"id": "CRDS_CARD_DATA", "name": "逆势龙头", "page": "选股策略", "freq": "收盘后1次", "max_age": 360, "key_fields": ["elite", "watch"]},
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
            return None


def load_window_var(path, var_name):
    """从 data/*.js 读取 window.X = {...}; 并解析为 dict。"""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # 去掉 BOM
    text = text.lstrip("\ufeff")
    m = re.search(rf"window\.{re.escape(var_name)}\s*=\s*([\s\S]*?);\s*\n", text)
    if not m:
        # 尝试更宽松的匹配
        m = re.search(rf"window\.{re.escape(var_name)}\s*=\s*(\{{[\s\S]*?\}})\s*;", text)
        if not m:
            return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _load_token():
    # GHA/云端：secrets.GITHUB_TOKEN (默认 workflow token, 有 actions:read 权限可查 runners)
    for env_name in ("V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v
    # 本机/开发环境：读 .workbuddy/v8_gh_token.txt
    candidates = [
        Path("E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"),
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def api_get(url):
    token = _load_token()
    if not token:
        return {"__error__": 401, "__msg__": "no token"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}
    except Exception as e:
        return {"__error__": 0, "__msg__": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 带 retry 的 urlopen：吸收 GitHub Pages 瞬时 SSL/网络抖动，避免误报邮件
# ─────────────────────────────────────────────────────────────────────────────
SITE_MAX_RETRIES = 2       # 首次 + 最多重试 2 次
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

# 卡片分组 -> 刷新类别映射（与 cloud_fetch_v8.py / update_v8.py 的 CATEGORY_MAP 对应）
PAGE_TO_CAT = {
    "实时数据": "intraday",
    "今日事件": "premarket",
    "盘后数据": "post_close",
    "选股策略": "post_close",
}


def _dispatch_cn_fetch(cat):
    """经 GitHub API 派发 cn_fetch 刷新（自愈核心动作）。"""
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"category": cat}}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 cn_fetch category={cat} (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, f"派发异常: {e}"


def _dispatch_algo_run():
    """经 GitHub API 派发 v8 盘后算法链(云端)，重新产出 FINAL_RECOMMEND_DATA 等选股结果。"""
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{ALGO_RUN_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 algo_run(盘后算法链) (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, f"派发异常: {e}"


def _dispatch_build_deploy():
    """经 GitHub API 派发 v8_build_deploy，触发 Pages 重新构建部署。"""
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法派发"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{BUILD_DEPLOY_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 build_deploy (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, f"派发异常: {e}"


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
    ok, dmsg = _dispatch_build_deploy()
    if ok:
        lock["build_deploy"] = now.strftime("%Y-%m-%d %H:%M:%S")
        _save_heal_lock(lock)
        return True, f"已派发 build_deploy ({dmsg})"
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
            ok, dmsg = _dispatch_algo_run()
            if ok:
                healed.append(f"[algo] {it['name']}: 已自动派发盘后算法链重新产出 ({dmsg})")
                it["heal"] = "已自动派发盘后算法链"
                lock["algo_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
            else:
                failed.append(f"[algo] {it['name']}: 自动派发失败 ({dmsg})")
                it["heal"] = f"自愈失败: {dmsg}"
    _save_heal_lock(lock)

    # 1) 数据卡片自愈：满足年龄阈值或被异常清空
    stale = [it for it in fail_items
             if (it.get("age_min") is not None and it["age_min"] >= ALERT_OVERDUE_MIN)
             or it.get("premarket_cleared") is True]
    cat_items = {}
    for it in stale:
        cat = PAGE_TO_CAT.get(it.get("page"))
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
        ok, dmsg = _dispatch_cn_fetch(cat)
        if ok:
            healed.append(f"[{cat}] {', '.join(names)}: 已自动派发刷新 ({dmsg})")
            for it in items:
                it["heal"] = f"已自动派发刷新({cat})"
            lock[cat] = now.strftime("%Y-%m-%d %H:%M:%S")
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
    return healed, failed


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
            # 收盘后 1 小时宽限（收盘整理 + 构建部署延迟）
            return min(def_max, 120)
        # 盘前 / 夜间 / 周末：实时数据本就不预期更新，放过夜阈值
        # 次日 09:30 才会有新数据，给到次日开盘都算正常
        if is_trade_day and h < 9.5:
            return 960  # 16h：从前一天收盘到当天开盘
        # 周末 /节假日：给 2880（48h，覆盖周末+周一开盘）
        return 2880

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


def check_data_cards():
    results = []
    today_str = now_cst().strftime("%Y-%m-%d")
    for d in CARD_DEFS:
        path = DATA_DIR / f"{d['id']}.js"
        var_name = d.get("_window_var") or d["id"]
        data = load_window_var(path, var_name)
        if data is None:
            results.append({
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "fail", "last_update": "--", "age_min": None,
                "message": f"找不到数据文件 {path.name} 或解析失败"
            })
            continue
        ts = data.get("update_time") or data.get("date") or data.get("lastUpdated") or "--"
        dt = parse_time(ts)
        max_age = adjust_max_age(d["max_age"], page=d.get("page"))

        # 盘中 premarket_cleared 异常自愈检测：实时数据在交易时段被标记为盘前清空，属于误清空
        prem_cleared = data.get("premarket_cleared") is True
        if prem_cleared and page == "实时数据" and is_intraday_session():
            results.append({
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "fail", "last_update": str(ts), "age_min": 0,
                "premarket_cleared": True,
                "message": f"盘中交易时段被异常标记为 premarket_cleared（update_time={fmt_rel_time(ts)}）"
            })
            continue

        if dt is None:
            results.append({
                "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
                "status": "warn", "last_update": str(ts), "age_min": None,
                "message": "无法解析更新时间"
            })
            continue
        age_min = (now_cst() - dt).total_seconds() / 60
        status = "ok" if age_min <= max_age else "fail"

        page = d.get("page")
        # 周末/节假日不更新模块：直接放行，不判 stale、不判空值，避免误告警
        weekend_skip = d.get("weekend_update") is False and is_market_closed()
        # 盘后数据 / 选股策略：周末/节假日停在最近交易日，同样放行并显示友好提示
        if not weekend_skip and is_market_closed() and page in ("盘后数据", "选股策略"):
            if dt and dt >= last_trade_day_close(now_cst()):
                weekend_skip = True

        # 空值检测
        empty_fields = []
        if not weekend_skip:
            for f in d["key_fields"]:
                v = data.get(f)
                # 结果池字段（如 stocks）空列表 = 正常业务状态（今日无入选），不算空值
                if v == [] and f == "stocks":
                    continue
                if v is None or v == "" or v == [] or v == {} or v == "--" or v == "加载中":
                    empty_fields.append(f)
        if empty_fields and status == "ok":
            status = "warn"
        rel = fmt_rel_time(ts)
        msg = f"更新于 {rel}"
        if weekend_skip:
            status = "ok"
            phase = "盘后" if page in ("盘后数据", "选股策略") else "盘前"
            msg = f"休市不更新（数据为上一交易日{phase}）；{rel}"
        elif empty_fields:
            msg += f"；关键字段空值：{', '.join(empty_fields)}"
        if status == "fail":
            msg += f"；超过阈值 {max_age} 分钟"
        results.append({
            "id": d["id"], "name": d["name"], "page": d["page"], "freq": d["freq"],
            "status": status, "last_update": ts, "age_min": round(age_min, 1),
            "message": msg
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

    # fallback：拿 GitHub Pages 的 latest deployment SHA（通过 GitHub API）
    if not site_sha:
        deployments = api_get(f"https://api.github.com/repos/{REPO}/deployments?environment=github-pages&per_page=1")
        if isinstance(deployments, list) and deployments:
            site_sha = deployments[0].get("sha", "")[:7]

    if not site_sha:
        return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": "warn",
                 "message": f"无法从线上或 API 获取 Pages SHA" + (f"（站点不可达：{fetch_err}）" if fetch_err else "")}]

    synced = local_sha.startswith(site_sha) or site_sha.startswith(local_sha)
    # 容忍 GitHub Pages 异步部署延迟：线上 SHA 落后 ≤5 个 commit 视为同步
    # GitHub Pages 部署通常有 1-3 分钟延迟，且 build commit 本身会累加 1 commit，
    # 加上云端自动 v8_build 偶尔叠加，落后 4-5 commit 都属正常
    behind = 0
    if not synced and local_sha and site_sha and len(local_sha) >= 7 and len(site_sha) >= 7:
        try:
            out = subprocess.check_output(
                ["git", "rev-list", "--count", f"{site_sha}..{local_sha}"],
                text=True, timeout=10
            ).strip()
            behind = int(out)
            if behind <= 5:
                synced = True
        except Exception:
            pass
    status = "ok" if synced else "fail"
    msg = f"本地 HEAD {local_sha[:7]} / 线上 {site_sha[:7]} {'已同步（落后 ≤5 commit，Pages 异步部署正常）' if synced and behind > 0 else '已同步' if synced else '不同步，落后 '+str(behind)+' commit，部署链路需检查'}"
    return [{"id": "site_sync", "name": "Pages 部署同步", "page": "管线", "status": status, "message": msg}]


def check_runner():
    """self-hosted runner（lemoncat-cn）已弃用，全部 workflow 迁 GitHub Actions 云端 ubuntu-latest。
    该检查项保留为历史占位，状态恒 ok，避免误告警。"""
    return [{"id": "runner", "name": "self-hosted runner", "page": "管线", "status": "ok", "message": "已迁移至 GitHub Actions 云端 ubuntu-latest，本地 runner 监控已下线"}]


def check_local_head_sync():
    """检查本地 HEAD 是否与 origin/main 一致。"""
    try:
        subprocess.run(["git", "fetch", "origin"], check=True, timeout=30)
        local = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=10).strip()
        remote = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True, timeout=10).strip()
        synced = local == remote
        status = "ok" if synced else "fail"
        msg = f"本地 {local[:7]} / origin/main {remote[:7]} {'同步' if synced else '本地落后，需 pull/push'}"
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

    return results


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


def build_report(cards, raw, site_sync, runner, local_sync, dom, signal_fresh=None, history_depth=None):
    all_items = cards + raw + site_sync + runner + local_sync + dom + (signal_fresh or []) + (history_depth or [])
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
        subject = f"【v8已自愈】{len(healed)} 项数据陈腐已自动派发刷新 @ {report['updated']}"
        lines = [f"v8 自愈巡检时间：{report['updated']}", "",
                 "检测到以下数据陈腐，已自动派发对应类别刷新（runner 执行中，稍后线上刷新）："]
        lines += [f"✓ {h}" for h in healed]
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
    raw = check_raw_data()
    site_sync = check_site_deploy_sync()
    runner = check_runner()
    local_sync = check_local_head_sync()
    dom = []
    if args.site:
        dom = check_site_dom()

    signal_fresh = check_signal_date_freshness()
    history_depth = check_top10_history_depth()

    report = build_report(cards, raw, site_sync, runner, local_sync, dom, signal_fresh, history_depth)
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
        healed, failed = self_heal(report)
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
    main()
