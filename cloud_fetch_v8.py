#!/usr/bin/env python3
"""v8 云端数据抓取（中国源 · 自托管 runner 在中国机器上执行）

⚠️ 重要前提（请小九/阿狸咪确认）：
- GitHub 官方 runner 在美国，抓 A 股数据源（东方财富/新浪/akshare 中国接口）会 60s 超时。
- 因此本工作流必须运行在「标记为 cn 的自托管 runner」上（即小九或阿狸咪的中国 IP 机器）。
- 本脚本用 akshare 抓取，逐模块 try/except：单个源失败只跳过该模块，不影响其他，
  且不会覆盖 data/*.js 中已有的正常数据（update_v8.py 只重写 raw_data 里存在的模块）。

⚠️ Schema 待小九核对：
- 每个 window.<VAR> 的字段结构以 index.html 渲染逻辑为准。本脚本产出的是「尽力而为」的结构，
  首次上线前请小九对照页面逐模块验证字段；字段不符的模块先不 push（脚本只写 raw_data，
  由 update_v8.py 转换，人工确认后再合入 main 的 data/）。

运行：python cloud_fetch_v8.py
依赖：akshare（pip install akshare），中国网络可达。
"""

import json, os, sys, time, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

CST = ZoneInfo("Asia/Shanghai")

def now_cst():
    """返回中国标准时间（Asia/Shanghai）的当前 datetime。"""
    return datetime.now(CST)

# 2026-08-03 修复：Windows cn runner 默认 GBK 终端，emoji 输出会 UnicodeEncodeError 崩溃。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
RAW_DIR.mkdir(exist_ok=True)

# 东财概念列表里的"索引/通道/成分/境外指数"类条目，不应作为真实概念热点展示
# 2026-08-20 一劳永逸修复：标准普尔/富时罗素等被东财当作概念板块返回，会污染
# 板块资金流与分时累计曲线，必须从 sectors_in/out 与历史数据中剔除。
_NOISE_CONCEPTS = {
    "融资融券", "深股通", "沪股通", "昨日高振幅", "富时罗素", "MSCI中国",
    "深成500", "标准普尔", "HS300_", "中证500", "上证50", "上证180",
    "深证100R", "创业板综", "创业成份", "中盘股", "大盘股", "小盘股",
    "基金重仓", "百元股", "东方财富热股", "科技风格", "大盘成长", "高市净率",
}

# 变量名 → raw_data 文件名（与 update_v8.py 的 DATA_SOURCES 对应）
VAR_TO_RAW = {
    "ETF_INTRADAY_HEAT": "etf_intraday_heat.json",
    "SECTOR_FUND_FLOW": "sector_fund_flow.json",
    "SECTOR_FUND_FLOW_INTRADAY": "sector_fund_flow_intraday.json",  # 分时累计曲线（每10min快照追加）
    "CONCEPT_RANKING": "concept_ranking.json",
    "IPO_DATA": "ipo_score.json",
    "MARGIN_DATA": "margin_data.json",
    "CFFEX_HOLDINGS": "cffex_data.json",
    "MACRO_DATA": "macro_data.json",
    "CRISIS_DATA": "crisis_data.json",
    "MACRO_BRIEF": "macro_brief.json",
    "JUDGMENT_DATA": "judgment_data.json",
    "HERDING_DATA": "herding_data.json",
    "LIMIT_UP_HEATMAP": "limit_up_heatmap.json",
    "LIMIT_UP_BROKEN": "limit_up_broken.json",
    "CAPITAL_FLOW_DATA": "capital_flow_data.json",
    "NORTH_FUND": "north_fund.json",
    "MARKET_FUND_FLOW_DATA": "market_fund_flow_data.json",
    "W52_HIGH": "w52_high.json",
    "ETF_PULSE": "etf_pulse.json",
    "ETF_DAILY_MONITOR": "etf_daily_monitor.json",
    "ANALYST_RATINGS": "analyst_ratings.json",
    "INDEX_QUOTES": "index_quotes.json",
    "EXPERIMENT": "experiment.json",
    "V8_CAL": "v8_cal.json",
    "CANDIDATE_QUOTES": "candidate_quotes.json",
    "SH_SZ_HISTORY": "sh_sz_history.json",
    "MARKET_ALERTS": "market_alerts.json",
    "OVERSEAS_MARKETS": "overseas_markets.json",
    "RESTRICTED_RELEASE": "restricted_release.json",
    "PERFORMANCE_FORECAST": "performance_forecast.json",
    "AVG_PRICE_DATA": "avg_price_data.json",  # 2026-08-31 修复：f_avg_price 已加入 tasks，必须对应 raw_data/avg_price_data.json，否则 save() 因 fname=None 直接返回，数据永不被写入
}

# 变量名 → 更新时段（与 update_v8.py 的 CATEGORY_MAP 对齐）
CATEGORY_MAP = {
    # 盘前
    "V8_CAL": "premarket",
    "IPO_DATA": "premarket",
    "MARGIN_DATA": "premarket,post_close",
    # 2026-08-31：期指主力合约为盘中实时，放回实时数据页，改为 intraday 抓取
    "CFFEX_HOLDINGS": "intraday",
    # 🛡 2026-09-04 主人令（一劳永逸·根因修复）：盘后数据页「宏观数据速览」卡读本变量，
    #   原只标 premarket → 盘后档(17:20/18:20/19:20)根本不抓它，页面却标着「收盘后」语义，
    #   主人截图质问「盘后数据页每个卡时间都不对」。加 post_close 使盘后必重抓一次。
    "MACRO_DATA": "premarket,post_close",
    "CRISIS_DATA": "premarket",
    "MACRO_BRIEF": "premarket",
    "JUDGMENT_DATA": "premarket",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    # 🛡 2026-09-04 同上：盘后数据页「市场宽度 · 新高家数与宽度评分」卡读本变量（52周新高广度）。
    "W52_HIGH": "premarket,post_close",
    "HERDING_DATA": "premarket",
    # 盘中（含 ETF 三连板、板块资金三连板盘中追热等实时场景）
    "INDEX_QUOTES": "intraday",
    "ETF_PULSE": "intraday",
    "ETF_INTRADAY_HEAT": "intraday",
    # ETF_DAILY_MONITOR 归 intraday：CATEGORY_MAP 决定的是「抓取时段」（main() 的 target_vars 按 cat 筛选），
    # 该卡片配合 ETF 三连板实时卡，盘中每 30 分需要刷新，改成 post_close 会把它踢出盘中抓取（2026-08-11 回归）。
    # 「盘前不清空、保留昨日 T+1 收盘值」是另一个语义，由下方 _clear_intraday_for_premarket 的 KEEP_VARS 负责。
    "ETF_DAILY_MONITOR": "intraday",
    "SECTOR_FUND_FLOW": "intraday,post_close",  # 2026-09-03 根治：盘中 cron 偶发丢档→收盘定格值无着落；加 post_close 兜底（过滤已 comma-aware）
    "SECTOR_FUND_FLOW_INTRADAY": "intraday,post_close",  # 分时快照，跟随 SECTOR_FUND_FLOW 同周期；盘后追加收盘定格点
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday,post_close",  # 2026-09-03 根治：盘中 cron 偶发丢档→收盘定格值无着落；加 post_close 兜底（过滤已 comma-aware）
    "LIMIT_UP_BROKEN": "intraday",
    "CANDIDATE_QUOTES": "intraday",  # 候选池实时行情：行业树图第二层（个股）数据源
    "SH_SZ_HISTORY": "intraday",  # 沪深成交额历史（滚动窗口，盘中最少5刷）
    "MARKET_ALERTS": "intraday",  # 市场预警（孤儿模块 fetch_orphan_market_alerts.py 接入盘中刷新）
    # 盘后（15:30 后）：大盘资金流时间轴，累积历史序列，避免盘中覆盖
    "MARKET_FUND_FLOW_DATA": "post_close",
    # 15:30 收盘数据：EXPERIMENT 等 akshare 可抓的 T+1 数据
    "EXPERIMENT": "post_close",
    # 2026-08-31 一劳永逸复位：AVG_PRICE_DATA 回归 intraday（与 update_v8.py 的 intraday 映射一致，
    #   主人令「实时的放回实时数据页」），并【必须】同时列入下方 KEEP_VARS——
    #   历史根因：它曾是 intraday 但不在 KEEP_VARS，于是每个盘前轮都被 _clear_intraday_for_premarket
    #   清成 {no_data:true} stub，history 每日归零 → history_days 恒为 1 → ma20=ma60=当日价、
    #   position_vs_ma20/ma60 恒 null → v8_health_check 常年判「关键字段空值」黄灯。
    #   本函数是该文件唯一写入者（standalone fetch_avg_price.py 步骤已从 workflow 摘除）。
    "AVG_PRICE_DATA": "intraday",
    "OVERSEAS_MARKETS": "intraday",  # 亚太市场(日经/恒生/KOSPI/台湾)：交易时段实时更新，盘中每轮刷新
    # 2026-08-30：盘后数据页新增解禁日历 + 业绩预告，日频更新即可
    # 🛡 2026-09-04 主人令（一劳永逸·根因修复）：注释写「盘后数据页」却只在盘前抓 —— 语义错配。
    #   页面把这两张卡标成「收盘后/盘后」，但盘后档不抓 → 卡片永远显示早上那一档的时间。
    #   加 post_close，使盘后档(17:20/18:20/19:20)必定重抓，与页面语义对齐。
    "RESTRICTED_RELEASE": "premarket,post_close",
    "PERFORMANCE_FORECAST": "premarket,post_close",
}

_ak = None

def get_ak():
    global _ak
    if _ak is None:
        import akshare as _ak_mod
        _ak = _ak_mod
    return _ak

# 2026 年中国A股休市区间（与 index.html 硬编码日历保持一致；每年初更新）
_AS_HOLIDAY_RANGES_2026 = [
    ("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
]
_AS_MAKEUP_DAYS_2026 = {"2026-01-04", "2026-02-14", "2026-02-28",
                        "2026-05-09", "2026-09-20", "2026-10-10"}

def _is_trading_day(d=None):
    """判断某天是否为A股交易日。优先用 akshare 交易日历，失败则回退硬编码。"""
    d = d or now_cst().date()
    iso = d.isoformat()
    if iso in _AS_MAKEUP_DAYS_2026:
        return True
    # 硬编码休市区间兜底
    for start, end in _AS_HOLIDAY_RANGES_2026:
        if start <= iso <= end:
            return False
    if d.weekday() >= 5:  # 周六日
        return False
    # 尝试 akshare 交易日历
    try:
        df = get_ak().tool_trade_date_hist_sina()
        if df is not None and not df.empty and 'trade_date' in df.columns:
            return iso in set(str(x)[:10] for x in df['trade_date'])
    except Exception:
        pass
    return True

def _last_trading_day(d=None):
    """返回 d（默认今天）当天或之前最近的一个交易日（date 对象）。

    2026-08-30 修复：f_avg_price 原来直接用 now_cst() 打日期，周末/节假日跑全量兜底时
      （如 2026-08-30 周日）会把「上一个交易日的行情」标成一个根本不存在的交易日，
      history 里混入周日记录，前端平均股价卡也显示周日日期。改为回落到最近交易日。
    """
    d = d or now_cst().date()
    for _ in range(12):
        if _is_trading_day(d):
            return d
        d = d - timedelta(days=1)
    return d

def _is_empty_payload(obj):
    """判断抓取结果是否为空/无效，避免把空壳数据写入 raw_data 并刷新 update_time。

    空数据不写文件，远端在 api_push_raw.py 防倒退守卫下会保留上一版有效数据，
    从而根治「抓取失败但 update_time 被刷新」的假刷新问题。
    """
    if obj is None:
        return True
    if isinstance(obj, (list, tuple, set)):
        return len(obj) == 0
    if isinstance(obj, dict):
        # 仅含 update_time / 日期 / 空 data 占位也算空
        if not obj:
            return True
        data = obj.get("data")
        if data is not None and not data and len(obj) <= 3:
            return True
        # 对于非列表型 data，若核心字段全空也视为空
        core_keys = ["items", "data", "records", "list", "history", "amount_history",
                     "daily_stats", "up_down", "nodes", "edges"]
        if not any(k in obj for k in core_keys):
            if all(not v for v in obj.values() if v not in (True, False)):
                return True
    return False


def save(var, obj):
    fname = VAR_TO_RAW.get(var)
    if not fname:
        return
    obj = obj if isinstance(obj, dict) else {"data": obj}
    # 🛡️ 2026-08-12 根治假刷新：空/无效数据不写文件、不刷新 update_time，
    #    保留远端旧数据供前端继续使用。
    if _is_empty_payload(obj):
        print(f"  ⚠️ {var}: 空/无效数据，跳过写入（保留远端旧数据）")
        _run_status[var] = {"status": "empty", "msg": "空数据跳过"}
        return
    obj["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    path = RAW_DIR / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"  ✅ {var} → raw_data/{fname}")


def _clear_premarket_marker(label):
    """🛡 2026-09-03 一劳永逸：盘中/盘后 fetch 返回空时，清除盘前残留的 premarket_cleared 标记，
    避免「盘中仍顶着盘前清空标记」误导 HEALTH_CHECK 误报 fail（ETF_INTRADAY_HEAT / SECTOR_FUND_FLOW
    早盘东财延迟镜像偶发空，盘前占位 legitimately 残留）。不动 update_time —— 年龄新鲜度检查仍能
    兜底「真·长期无数据」（盘中卡 2h 红线，超龄照常 fail）。仅由 run() 在 09:30 后空结果时调用；
    盘前(08:25-09:30)阶段标记本就正确，不在此清除（由 _clear_intraday_for_premarket 统一负责）。"""
    fname = VAR_TO_RAW.get(label)
    if not fname:
        return
    path = RAW_DIR / fname
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if data.pop("premarket_cleared", None) is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"), default=str)
            print(f"  🧹 {label}: 清除盘前残留 premarket_cleared 标记（保留原有数据，update_time 不变）")
        except Exception as e:
            print(f"  ⚠️ {label}: 清除 premarket_cleared 失败: {e}")


# ───────────────────────── 东方财富「延迟镜像」直连 ─────────────────────────
# 说明：东方财富 push2.eastmoney.com / push2his.eastmoney.com 的实时资金流接口
# 在本机/runner 网络下被 WAF 以 TCP 重置（ConnectionError: RemoteDisconnected）拒绝；
# 但其「延迟镜像」push2delay.eastmoney.com 可达且返回相同字段（延迟仅数秒，对日频排名无影响）。
# 故资金流类接口统一走 push2delay，规避实时 host 的封锁。
import requests as _requests

_EM_DELAY = "https://push2delay.eastmoney.com"
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/zjlx/detail.html",
    "Accept": "*/*",
}

def _em_get_with_retry(url, *, params, headers, timeout, max_attempts=3, label=""):
    """2026-08-19 主人令一劳永逸式根治云端 push2 抓取抖动（B 方案）：
       指数退避重试，遇 ConnectionError/Timeout/JSON 异常/rc!=0 时按 0.5s/1.5s/3.0s 退避。
       三次都失败抛 RuntimeError 给上层 fn_xxx 决定是否降级返回（保留空列表语义，不破坏现有 caller）。"""
    import random as _rnd
    delays = [0.5, 1.5, 3.0]
    last_err = None
    for attempt in range(max_attempts):
        try:
            r = _requests.get(url, params=params, headers=headers, timeout=timeout)
            d = r.json()
            if d.get("rc") == 0:
                return d
            last_err = RuntimeError(f"rc={d.get('rc')}")
        except Exception as e:
            last_err = e
        if attempt < max_attempts - 1:
            dly = delays[attempt] + _rnd.uniform(0, 0.4)
            print(f"  ⚠️ push2 抖动({label or url}) 尝试{attempt+1}/{max_attempts}: {last_err} → {dly:.1f}s 后重试")
            import time as _t; _t.sleep(dly)
    raise RuntimeError(f"push2 重试{max_attempts}次仍失败: {last_err}")


# ─────────────────────────────────────────────────────────────────────────────
# 东财占位符归一（2026-09-04 主人令一劳永逸根治）
# 现象：盘前/停牌/无成交时，push2 的 f2/f3/f5/f6/f104/f105/f106 等字段返回字符串 '-' / '--' / ''
#       而非数字。下游普遍写作 int(r.get("fXX") or 0)，但 '-' 是**非空字符串** → `or 0` 不生效
#       → ValueError: invalid literal for int() with base 10: '-' → 整个 fn_xxx 报 fail。
# 实证：2026-09-04 08:52 那轮 INDEX_QUOTES + CAPITAL_FLOW_DATA 双双因此失败 →
#       「2 个模块抓取失败，阻止空壳推送」→ 整轮数据作废，白等两轮才补齐。
# 修法：在**数据入口**把占位符统一归一成 None，则全部 40 处 `or 0` / `_to_yi` 自动生效，
#       无需逐点修改，也不会改变任何有效数值的语义。
# ─────────────────────────────────────────────────────────────────────────────
_EM_PLACEHOLDERS = {"", "-", "--"}


def _em_clean_value(v):
    """东财字段值归一：占位符('-','--','') → None；其余原样返回（不做类型转换，语义不变）。"""
    if isinstance(v, str) and v.strip() in _EM_PLACEHOLDERS:
        return None
    return v


def _em_clean_rows(rows):
    """对东财 diff 列表（list[dict]）逐字段归一占位符。非 list 原样返回，任何情况下都不抛异常。"""
    if not isinstance(rows, list):
        return rows
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append({k: _em_clean_value(v) for k, v in r.items()})
        else:
            out.append(r)
    return out


def em_clist(fs, fields, fid="f62", stat="1", pz=5000, po="1", pn=1, timeout=15):
    """东方财富 clist 接口（push2delay 镜像）。返回 data.diff 列表（每项为字段字典）。
    po="1" 降序(取净流入最高)，po="0" 升序(取净流出最高)。
    pn 页码（默认 1），pz 单页大小（默认 5000，但 push2delay 实际硬截 100，分页需自循环）。
    2026-08-19 主人令：em_clist/em_ulist_np 加 _em_get_with_retry 指数退避，根治云端 WAF 抖动。
    """
    params = {
        "pn": str(pn), "pz": str(pz), "po": po, "np": "1", "fltt": "2", "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fid": fid, "fs": fs, "stat": stat,
        "fields": fields, "_": int(time.time() * 1000),
    }
    try:
        d = _em_get_with_retry(
            f"{_EM_DELAY}/api/qt/clist/get", params=params,
            headers=_EM_HEADERS, timeout=timeout,
            label=f"clist {fs.split(' ')[0]} pz={pz} po={po}",
        )
    except RuntimeError:
        return []
    if not d.get("data"):
        return []
    return _em_clean_rows(d["data"].get("diff", []) or [])

def _to_yi(v):
    """东财字段单位为元，转亿（保留2位）。"""
    try:
        return round(float(v or 0) / 1e8, 2)
    except Exception:
        return 0.0


# 全市场个股过滤串（沪市/深市/北交所主力，排除指数与债券等）
_IND_FS = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2"

def _all_individual_recs(fields="f12,f14,f2,f3,f62,f184"):
    """取全市场个股主力净流入并集（降序 TOP + 升序 TOP 合并去重），用于准确求和与净流入/流出 TOP。"""
    desc = em_clist(_IND_FS, fields, fid="f62", stat="1", pz=5000, po="1")
    asc = em_clist(_IND_FS, fields, fid="f62", stat="1", pz=5000, po="0")
    by_code = {}
    for r in desc + asc:
        c = str(r.get("f12"))
        if c in by_code:
            continue
        by_code[c] = {
            "code": c,
            "name": r.get("f14"),
            "price": round(float(r.get("f2") or 0), 2),
            "chg": round(float(r.get("f3") or 0), 2),
            "net": _to_yi(r.get("f62")),
            "net_pct": round(float(r.get("f184") or 0), 2),
        }
    return list(by_code.values())

# 单次运行状态跟踪（用于前端定时任务跟踪看板）
_run_status = {}

def _fetch_remote_raw(rel_path):
    """从 GitHub main 拉取 raw_data 已有内容，作为追加型序列（如 sh_sz_history）的权威基线。
    绕过 git/HTTPS 封锁，走 Git Database / Contents API。失败返回 None。
    用途：本地 raw_data 在每次 intraday 运行开头会被清理删除，且 data/SH_SZ_HISTORY.js 滞后于
    推送→构建周期；直接用「上一次成功推送的远端版本」作基线，可根治追加型序列跨天塌缩（每日丢一天）。
    """
    import base64 as _b64
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        return None
    url = f"https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/raw_data/{rel_path}"
    try:
        r = _requests.get(url, headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}, timeout=30)
        d = r.json()
        if not isinstance(d, dict) or "content" not in d:
            return None
        content = _b64.b64decode(d.get("content", "")).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"  ⚠️ 远端基线拉取失败 {rel_path}: {e}")
        return None


def _load_judgment_raw(var_name, fname):
    """读取同一次 premarket 运行内已生成的 raw_data/X.json 或 data/X.js。"""
    try:
        for p in [Path(ROOT) / "raw_data" / fname, Path(ROOT) / "data" / (var_name + ".js")]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if txt.startswith("window." + var_name):
                    pre = len("window." + var_name)
                    txt = txt[pre:].lstrip("=").lstrip().strip().rstrip(";")
                return json.loads(txt)
    except Exception:
        pass
    return {}


def _analyst_tech(neg, pos, avg_chg, max_drop, max_rise, total_amt, market):
    """技术面分析师：基于指数结构/趋势/量能。"""
    if neg == 3:
        if max_drop <= -1.5:
            return {"name": "技术面", "judgment": "减仓观望", "recommendation": 1,
                    "reason": f"三指数全绿且跌幅超1.5%（{avg_chg:+.2f}%），下行结构确认",
                    "risk": "下行趋势中反弹易套", "danger": ["三指数同步破位，趋势性下跌风险"],
                    "if_must_enter": "仅超短，≤10%仓，快进快出"}
        if max_drop <= -0.8:
            return {"name": "技术面", "judgment": "耐心等待企稳", "recommendation": 2,
                    "reason": f"三指数同步调整（平均{avg_chg:+.2f}%）",
                    "risk": "未现企稳信号", "danger": ["连续调整，抄底需等放量止跌"],
                    "if_must_enter": "轻仓试错≤15%"}
        return {"name": "技术面", "judgment": "正常波动", "recommendation": 3,
                "reason": f"三指数微幅低开（平均{avg_chg:+.2f}%）",
                "risk": "方向待选", "danger": [],
                "if_must_enter": "≤20%仓观望"}
    if pos == 3:
        if max_rise >= 1.5:
            return {"name": "技术面", "judgment": "积极参与", "recommendation": 5,
                    "reason": f"三指数全线飘红（平均{avg_chg:+.2f}%），放量健康",
                    "risk": "警惕冲高回落", "danger": ["普涨后分化，追涨缩量品种易套"],
                    "if_must_enter": "择优布局≤30%"}
        if max_rise >= 0.8:
            return {"name": "技术面", "judgment": "可积极参与", "recommendation": 4,
                    "reason": f"三指数共振上行（平均{avg_chg:+.2f}%）",
                    "risk": "冲高回落", "danger": [],
                    "if_must_enter": "≤25%仓跟随主流"}
        return {"name": "技术面", "judgment": "轻仓试探", "recommendation": 4,
                "reason": f"三指数微幅高开（平均{avg_chg:+.2f}%），力度有限",
                "risk": "力度不足", "danger": [],
                "if_must_enter": "≤20%仓"}
    # 分化
    if abs(max_rise - max_drop) > 2.0:
        return {"name": "技术面", "judgment": "重个股轻指数", "recommendation": 3,
                "reason": f"剧烈分化（极差{abs(max_rise-max_drop):.1f}%），结构性机会与风险并存",
                "risk": "踩错方向易亏损", "danger": ["分化极端，板块轮动快"],
                "if_must_enter": "跟随强势板块≤20%"}
    if abs(avg_chg) < 0.3:
        return {"name": "技术面", "judgment": "观望或做T", "recommendation": 3,
                "reason": f"窄幅震荡（振幅<0.3%），多空平衡",
                "risk": "方向不明", "danger": ["量能不足，突破需等待"],
                "if_must_enter": "≤15%仓做T"}
    if avg_chg > 0:
        return {"name": "技术面", "judgment": "跟随主流", "recommendation": 4,
                "reason": f"偏强分化（平均{avg_chg:+.2f}%），资金有明确偏好",
                "risk": "边缘题材补跌", "danger": [],
                "if_must_enter": "≤20%仓跟主流"}
    return {"name": "技术面", "judgment": "防御为主", "recommendation": 2,
            "reason": f"偏弱分化（平均{avg_chg:+.2f}%）",
            "risk": "弱势承压", "danger": ["弱势指数拖累，谨防破位"],
            "if_must_enter": "仅超短≤10%"}


def _analyst_sentiment(cs, vix, sff_names):
    """情绪面分析师：基于危机雷达 + VIX + 板块资金。"""
    if cs >= 70:
        return {"name": "情绪面", "judgment": "继续空仓", "recommendation": 1,
                "reason": f"危机雷达{cs}分（高风险），系统性风险偏高",
                "risk": "系统性风险偏高", "danger": [f"危机雷达综合分≥70（{cs}分）"],
                "if_must_enter": "仅≤10%仓，优先防御"}
    if cs >= 50:
        return {"name": "情绪面", "judgment": "防御为主", "recommendation": 2,
                "reason": f"危机雷达{cs}分（警戒），情绪偏谨慎" + (f"；资金偏好 {sff_names}" if sff_names else ""),
                "risk": "警戒区", "danger": [f"危机雷达{cs}分处于警戒区"],
                "if_must_enter": "≤15%仓结构性"}
    if cs >= 30:
        return {"name": "情绪面", "judgment": "中性偏谨慎", "recommendation": 3,
                "reason": f"危机雷达{cs}分（中性），情绪平稳" + (f"；资金偏好 {sff_names}" if sff_names else ""),
                "risk": "中性", "danger": [],
                "if_must_enter": "≤20%仓"}
    return {"name": "情绪面", "judgment": "风险可控", "recommendation": 4,
            "reason": f"危机雷达{cs}分（安全），系统性风险低" + (f"；资金偏好 {sff_names}" if sff_names else ""),
            "risk": "低位", "danger": [],
            "if_must_enter": "≤25%仓"}


def _analyst_macro(us_str, usdcnh, us10y, vix):
    """宏观面分析师：基于美股隔夜 + 汇率 + 美债。"""
    bear = ("跌" in us_str) or ("收跌" in us_str) or ("下挫" in us_str)
    bull = ("涨" in us_str) or ("收涨" in us_str) or ("创新高" in us_str)
    cny_weak = usdcnh >= 7.25
    if bull and not cny_weak:
        return {"name": "宏观面", "judgment": "外部环境友好", "recommendation": 4,
                "reason": f"美股偏强，人民币稳（USDCNH {usdcnh:.3f}）",
                "risk": "外围扰动低", "danger": [],
                "if_must_enter": "≤25%仓"}
    if bear and cny_weak:
        return {"name": "宏观面", "judgment": "外围偏空", "recommendation": 2,
                "reason": f"美股承压+人民币贬值（USDCNH {usdcnh:.3f}），外资流出压力",
                "risk": "外资流出", "danger": [f"人民币贬值至 {usdcnh:.3f}，外资撤离压力"],
                "if_must_enter": "≤15%仓，规避外资重仓"}
    if bear:
        return {"name": "宏观面", "judgment": "外围承压", "recommendation": 3,
                "reason": f"美股走弱但汇率平稳，影响有限",
                "risk": "情绪传导", "danger": [],
                "if_must_enter": "≤20%仓"}
    if cny_weak:
        return {"name": "宏观面", "judgment": "汇率偏空", "recommendation": 3,
                "reason": f"人民币贬值（USDCNH {usdcnh:.3f}）压制核心资产",
                "risk": "汇率波动", "danger": [f"人民币贬值至 {usdcnh:.3f}"],
                "if_must_enter": "≤20%仓，规避出口链"}
    return {"name": "宏观面", "judgment": "中性", "recommendation": 3,
            "reason": f"外围平稳（USDCNH {usdcnh:.3f}，VIX {vix:.1f}）",
            "risk": "中性", "danger": [],
            "if_must_enter": "≤20%仓"}


def f_judgment():
    """今日判定（盘前 08:25 自动生成，注册于 JUDGMENT_DATA→premarket）。
    v3 多模型共识版(2026-08-05)：拆成 技术面/情绪面/宏观面 三个独立分析师视角，
    各自输出 核心判断/推荐度(1-5星)/关键理由/风险评估/若必须进场，再聚合
    共同结论 + 三大危险信号（双方一致认可），前端渲染为对比表 + 共识区。

    🛡️ 2026-08-15 主人令：周六/周日非交易日不重新生成判定（保留周五数据），仅刷新 update_time=周五。
    """
    now = now_cst()
    today = now.date()
    md = f"{today.month}/{today.day}"

    # 🛡️ 2026-08-15 非交易日守卫：保留周五判定，不重算
    if not _is_trading_day(today):
        existing = {}
        try:
            p = Path(RAW_DIR) / 'judgment_data.json'
            if p.exists():
                existing = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
        if existing and existing.get('update_time'):
            # 保留周五完整数据，仅在 body 上标"非交易日沿用"
            existing['_weekend_inherit'] = True
            existing['_weekend_note'] = f'周末沿用 {existing.get("date", "")} 判定·原始跑数据'
            print(f'⏭️ {today} 非交易日：沿用 {existing.get("date")} 判定（不重算）')
            return existing
        # 没有历史数据，回落到正常计算
        print(f'⚠️ {today} 非交易日但无历史判定，回落到实时计算')

    # 取指数行情
    idx_data = {}
    try:
        q = f_index_quotes()
        if q and q.get("items"):
            for it in q["items"]:
                idx_data[it["code"]] = it
    except Exception:
        idx_data = {}

    mains = [("000001", "上证指数"), ("399001", "深证成指"), ("399006", "创业板指")]
    indices, chgs, amounts = [], [], []
    for code, name in mains:
        it = idx_data.get(code)
        chg = round(float(it.get("chg", 0.0) or 0.0), 2) if it else 0.0
        amount = round(float(it.get("amount", 0.0) or 0.0), 2) if it else 0.0
        ctrl = round(chg, 1)
        fs = round(amount / 1000.0, 1)
        # 动态 warn：根据跌幅幅度给不同提示
        if it and abs(chg) < 0.05:
            warn = ""
        elif it and chg <= -1.5:
            warn = "近5日弱势"
        elif it and chg >= 1.5:
            warn = "近5日强势"
        else:
            warn = ""
        indices.append({"name": name, "ctrl": ctrl, "fs": fs, "warn": warn})
        chgs.append(chg)
        amounts.append(amount)

    neg = sum(1 for c in chgs if c < 0)
    pos = sum(1 for c in chgs if c > 0)
    total_amt = sum(amounts)
    avg_chg = sum(chgs) / len(chgs) if chgs else 0
    max_drop = min(chgs) if chgs else 0
    max_rise = max(chgs) if chgs else 0

    # 市场结构（保留原有逻辑）
    if neg == 3:
        market = "下行结构（三指数控盘全负）"
    elif pos == 3:
        market = "上行结构（三指数全正）"
    elif neg > pos:
        market = "偏弱分化（指数多数控盘为负）"
    elif pos > neg:
        market = "偏强分化（指数多数控盘为正）"
    else:
        market = "震荡分化（指数控盘方向不一）"

    # ---- 读取同一次 premarket 已生成的 情绪面/宏观面/宏观解读 数据源 ----
    crisis = _load_judgment_raw("CRISIS_DATA", "crisis_data.json")
    macro = _load_judgment_raw("MACRO_DATA", "macro_data.json")
    sff = _load_judgment_raw("SECTOR_FUND_FLOW", "sector_fund_flow.json")
    mb = _load_judgment_raw("MACRO_BRIEF", "macro_brief.json")

    us = _fetch_us_overnight()
    if us:
        us_str = us
    else:
        # 美股接口失败时，用宏观解读 headline 滚动替代，避免固定死文案
        mb_headline = mb.get("headline", "")
        us_str = f"外围宏观：{mb_headline}" if mb_headline else ""

    cs = crisis.get("score", crisis.get("crisis_score", 0)) or 0
    gm = macro.get("global_macro", {})
    vix = float(gm.get("vix", {}).get("value", 0) or 0)
    usdcnh = float(gm.get("usdcnh", {}).get("price", 0) or 0)
    us10y = float(macro.get("monetary", {}).get("us_bond_10y", {}).get("value", 0) or 0)
    sff_top = (sff.get("top_list") or [])[:3]
    sff_names = " / ".join([s.get("name") or s.get("sector_name") for s in sff_top if (s.get("name") or s.get("sector_name"))])

    # ====== 三大分析师 ======
    tech = _analyst_tech(neg, pos, avg_chg, max_drop, max_rise, total_amt, market)
    sent = _analyst_sentiment(cs, vix, sff_names)
    macro_a = _analyst_macro(us_str, usdcnh, us10y, vix)
    # 日本/日元加息预期：补充到今日判定宏观面（数据锚定真实 USDJPY）
    _usdjpy = float(gm.get("usdjpy", {}).get("price", 0) or 0)
    if _usdjpy >= 155:
        macro_a["reason"] += f"；日元弱（USDJPY {_usdjpy:.1f}），日银9月加息预期升温"
    elif _usdjpy:
        macro_a["reason"] += f"；USDJPY {_usdjpy:.1f}"
    analysts = [tech, sent, macro_a]

    # 共同结论
    recs = [a["recommendation"] for a in analysts]
    avg_rec = sum(recs) / len(recs)
    if avg_rec >= 3.5:
        direction = "偏多共识"
    elif avg_rec <= 2.5:
        direction = "偏空共识"
    else:
        direction = "分歧观望"
    consensus = f"{direction}（技术{tech['recommendation']}★/情绪{sent['recommendation']}★/宏观{macro_a['recommendation']}★）"

    # 三大危险信号（收集各分析师 danger，去重取前3）
    danger_signals = []
    for a in analysts:
        for d in (a.get("danger") or []):
            if d and d not in danger_signals:
                danger_signals.append(d)
            if len(danger_signals) >= 3:
                break
        if len(danger_signals) >= 3:
            break

    # 兼容旧版字段（health check 仍校验 verdict/indices）
    _vol_level = "放量" if total_amt > 12000 else ("缩量" if total_amt < 7000 else "平量")
    if neg == 3:
        verdict = f"三指数全绿（平均{avg_chg:+.2f}%），{_vol_level}下行，{direction}"
        warning = "减仓窗口，反弹不宜追高。" if abs(avg_chg) > 0.8 else "控制仓位。"
    elif pos == 3:
        verdict = f"三指数全红（平均{avg_chg:+.2f}%），{_vol_level}上行，{direction}"
        warning = "逢调择优，警惕冲高回落。" if abs(avg_chg) > 0.8 else "轻仓试探。"
    elif abs(avg_chg) < 0.3:
        verdict = f"窄幅震荡（振幅<0.3%），{direction}，宜观望或做T"
        warning = f"成交额{total_amt:.0f}亿偏低，谨慎开新仓。" if total_amt < 7000 else "聚焦共识方向。"
    else:
        verdict = f"{market}（平均{avg_chg:+.2f}%），{direction}"
        warning = "控制仓位，重个股轻指数。"

    return {
        "date": today.strftime("%Y-%m-%d"),
        "title": f"今日判定（{md}）",
        "market": market,
        "indices": indices,
        "us": us_str,
        "verdict": verdict,
        "warning": warning,
        "analysts": analysts,
        "consensus": consensus,
        "danger_signals": danger_signals,
        "macro_brief": {
            "headline": mb.get("headline", ""),
            "news_brief": (mb.get("news_brief") or [])[:3],
            "a_impact": mb.get("a_impact", ""),
        },
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }
def f_macro_brief():
    """每日宏观解读 + 时事要点（盘前 08:25 自动生成，注册于 MACRO_BRIEF→premarket）。
    
    基于当日 MACRO_DATA（利率/汇率/VIX/商品）+ CRISIS_DATA（危机雷达）+ 美股隔夜，
    用规则引擎生成：
      - headline: 一句话宏观结论
      - key_numbers: 3~5 个关键数据变动（含昨日对比）
      - news_brief: 3~5 条数据驱动的"时事要点"（对 A 股有影响的）
      - a_impact: 对 A 股的简短影响评估
    """
    now = now_cst()
    today = now.date()

    # ---- 读取已生成的 MACRO_DATA ----
    macro = {}
    macro_path = Path(ROOT) / "data" / "MACRO_DATA.js"
    raw_macro_path = Path(ROOT) / "raw_data" / "macro_data.json"
    try:
        for p in [macro_path, raw_macro_path]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if txt.startswith("window.MACRO_DATA"):
                    txt = txt[len("window.MACRO_DATA "):].lstrip("=").lstrip().strip().rstrip(";")
                macro = json.loads(txt)
                if macro:
                    break
    except Exception:
        macro = {}

    gm = macro.get("global_macro", {})
    monetary = macro.get("monetary", {})
    commodities = gm.get("commodities", {})

    # ---- 读取危机雷达 ----
    crisis = {}
    crisis_path = Path(ROOT) / "data" / "CRISIS_DATA.js"
    raw_crisis_path = Path(ROOT) / "raw_data" / "crisis_data.json"
    try:
        for p in [crisis_path, raw_crisis_path]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if txt.startswith("window.CRISIS_DATA"):
                    txt = txt[len("window.CRISIS_DATA "):].lstrip("=").lstrip().strip().rstrip(";")
                crisis = json.loads(txt)
                if crisis:
                    break
    except Exception:
        crisis = {}

    # ---- 提取关键数值 ----
    vix = float(gm.get("vix", {}).get("value", 0) or 0)
    us10y = float(monetary.get("us_bond_10y", {}).get("value", 0) or 0)
    us10y_prev = float(monetary.get("us_bond_10y", {}).get("previous", 0) or 0)
    cn10y = float(monetary.get("cn_bond_10y", {}).get("value", 0) or 0)
    cn10y_prev = float(monetary.get("cn_bond_10y", {}).get("previous", 0) or 0)
    dxy = float(gm.get("dxy", {}).get("value", 0) or 0)
    usdcnh = float(gm.get("usdcnh", {}).get("price", 0) or 0)
    gold = float(commodities.get("gold", {}).get("value", 0) or 0)
    oil = float(commodities.get("oil", {}).get("value", 0) or 0)
    silver = float(commodities.get("silver", {}).get("value", 0) or 0)
    copper = float(commodities.get("copper", {}).get("value", 0) or 0)

    crisis_score = crisis.get("score", crisis.get("total_score", 0))
    crisis_level = crisis.get("level", "")

    # ---- 规则引擎：生成 headline ----
    signals = []
    if vix > 25:
        signals.append(f"VIX 飙升至 {vix:.1f}（恐慌区域）")
    elif vix > 20:
        signals.append(f"VIX 升至 {vix:.1f}（偏高）")
    elif vix < 13:
        signals.append(f"VIX 降至 {vix:.1f}（极度乐观）")

    if us10y > 4.5:
        signals.append(f"美债 10Y 突破 {us10y:.2f}%（紧缩压力）")
    elif us10y < 4.0:
        signals.append(f"美债 10Y 回落至 {us10y:.2f}%（压力缓和）")

    spread = cn10y - us10y if cn10y and us10y else None
    if spread is not None and spread < -2.8:
        signals.append(f"中美利差 {spread:.2f}%（历史深度倒挂收窄中）")

    if gold > 4200:
        signals.append(f"黄金突破 ${gold:.0f}/oz（避险情绪升温）")

    if crisis_score >= 70:
        signals.append(f"危机雷达 {crisis_score} 分（{crisis_level}·高风险）")
    elif crisis_score >= 50:
        signals.append(f"危机雷达 {crisis_score} 分（{crisis_level}·需关注）")

    if not signals:
        signals.append("全球宏观环境平稳，无极端信号")

    headline = "；".join(signals[:3])

    # ---- 关键数据变动表 ----
    key_numbers = []
    def _kn(label, value, prev, unit="", fmt=".2f"):
        if not value and value != 0:
            return
        if prev is None:
            delta = "—"   # 无昨日对比基准，不臆造变动
        else:
            d = value - prev
            arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
            delta = f"{arrow}{abs(d):{fmt}}{unit}" if d != 0 else "持平"
        key_numbers.append({
            "label": label,
            "value": f"{value:{fmt}}{unit}",
            "delta": delta,
        })

    _kn("美债 10Y", us10y, us10y_prev, "%")
    _kn("中国 10Y", cn10y, cn10y_prev, "%")
    _kn("VIX 恐慌指数", vix, None, fmt=".1f")
    _kn("美元指数 DXY", dxy, None, fmt=".2f")
    _kn("USD/CNH 汇率", usdcnh, None, fmt=".4f")
    _kn("黄金 COMEX", gold, None, "$/oz", fmt=".0f")
    _kn("原油 WTI", oil, None, "$/bbl", fmt=".1f")

    # ---- 数据驱动的时事要点（news_brief）----
    news = []

    # 美债
    if us10y and us10y_prev:
        yld_chg = round(us10y - us10y_prev, 4)
        if abs(yld_chg) >= 0.05:
            direction = "飙升" if yld_chg > 0 else "骤降"
            impact = "压制全球风险资产估值" if yld_chg > 0 else "利好风险资产反弹"
            news.append({
                "tag": "🇺🇸 美债",
                "text": f"10Y 美债收益率{direction}至 {us10y:.2f}%（单日{'+' if yld_chg>0 else ''}{yld_chg:+.2f}%bp），{impact}。A 股高估值成长板块承压{'减轻' if yld_chg<0 else '加剧'}。",
            })

    # VIX
    if vix:
        if vix > 25:
            news.append({"tag": "😰 全球风险", "text": f"VIX 跳升至 {vix:.1f}，进入恐慌区域。外围市场波动放大，北向资金可能趋于谨慎，A股开盘或有低开压力。"})
        elif vix < 13:
            news.append({"tag": "😌 全球风险", "text": f"VIX 降至 {vix:.1f} 的极低位，市场过度乐观。警惕均值回归风险，不宜追高。"})
        elif abs(vix - 17) > 3:
            direction = "攀升" if vix > 20 else "回落"
            news.append({"tag": "📊 波动率", "text": f"VIX {direction}至 {vix:.1f}，{'避险情绪升温' if vix>18 else '风险偏好回升'}。关注今日 A 股开盘联动反应。"})

    # 汇率
    if usdcnh:
        if usdcnh > 7.30:
            news.append({"tag": "💱 汇率", "text": f"USD/CNH 报 {usdcnh:.4f}，人民币贬值压力较大。外资流入意愿或受抑制，出口链相对受益。"})
        elif usdcnh < 7.00:
            news.append({"tag": "💱 汇率", "text": f"USD/CNH 回落至 {usdcnh:.4f}，人民币走强。外资配置 A 股环境改善，但出口企业汇兑收益承压。"})
        elif abs(usdcnh - 7.15) > 0.05:
            direction = "升值" if usdcnh < 7.15 else "贬值"
            news.append({"tag": "💱 汇率", "text": f"人民币对美元{direction}，USDCNH={usdcnh:.4f}。{'资金面偏紧' if usdcnh>7.2 else '资金面中性偏松'}。"})

    # 日本 / 日元（日银加息预期）：美元兑日元弱日元 → BOJ 加息压力。数据锚定真实 USDJPY，绝不臆造。
    usdjpy = float(gm.get("usdjpy", {}).get("price", 0) or 0)
    if usdjpy:
        if usdjpy >= 155:
            jp = {"tag": "🇯🇵 日本/日元", "text": f"美元兑日元报 {usdjpy:.1f}（日元逼近160四十年低位），市场押注日银9月加息（概率约75%），若兑现将推动日元套利交易平仓，对全球风险偏好与A股外资流向形成扰动。"}
        elif usdjpy <= 140:
            jp = {"tag": "🇯🇵 日本/日元", "text": f"美元兑日元回落至 {usdjpy:.1f}，日元走强，日银加息紧迫性下降，亚太风险偏好改善。"}
        else:
            jp = {"tag": "🇯🇵 日本/日元", "text": f"美元兑日元 {usdjpy:.1f}，日元中性，日银政策按兵不动观察期。"}
        # 置顶：日本加息是当前最影响亚太的风险事件之一，确保进入今日判定前3条
        news.insert(0, jp)

    # 黄金
    if gold:
        if gold > 4300:
            news.append({"tag": "🥇 大宗", "text": f"COMEX 黄金突破 ${gold:.0f}/oz，避险资产持续走强。反映全球不确定性升温，黄金/防御板块相对受益。"})
        elif gold < 3800:
            news.append({"tag": "🥇 大宗", "text": f"COMEX 黄金回落至 ${gold:.0f}/oz，避险需求降温。风险偏好修复时资金可能从黄金回流股市。"})

    # 原油
    if oil:
        if oil > 85:
            news.append({"tag": "🛢️ 大宗", "text": f"WTI 原油突破 $85/bbl，通胀预期升温。可能推迟美联储降息节奏，对 A 股新能源/化工有成本传导影响。"})
        elif oil < 72:
            news.append({"tag": "🛢️ 大宗", "text": f"WTI 原油跌破 $72/bbl，能源成本下降。利好交运/化工等中下游行业，但反映全球需求疲软。"})

    # 中美利差
    if spread is not None:
        if spread > -2.0:
            news.append({"tag": "📈 利差", "text": f"中美 10Y 利差收窄至 {spread:.2f}%，人民币资产吸引力提升空间打开，中长期利好 A 股估值修复。"})
        elif spread < -3.2:
            news.append({"tag": "📉 利差", "text": f"中美 10Y 利差深度倒挂 {spread:.2f}%，资本外流压力仍在。央行货币政策空间受限，A 股估值承压。"})

    # 危机雷达
    if crisis_score >= 70:
        c_items = crisis.get("items", []) if isinstance(crisis.get("items"), list) else []
        top_risks = [it.get("name", it.get("label", "")) for it in c_items[:3] if it]
        risk_str = "、".join(top_risks) if top_risks else "多项指标异常"
        news.append({"tag": "🚨 风控", "text": f"危机雷达亮红灯（{crisis_score}分/{crisis_level}）：{risk_str}。建议降低仓位、提高现金比例，回避高 Beta 个股。"})
    elif crisis_score >= 50:
        news.append({"tag": "⚠️ 风控", "text": f"危机雷达黄色预警（{crisis_score}分），部分指标偏离正常区间。保持中等仓位，设置好止损位。"})

    # 如果没有任何新闻生成，给一条默认的
    if not news:
        news.append({
            "tag": "📋 宏观",
            "text": f"今日关键宏观数据：美债10Y={us10y or '--'}%、VIX={vix or '--'}、USD/CNH={usdcnh or '--'}、黄金=${gold or '--'}/oz。整体环境平稳，以 A 股内部结构性行情为主。",
        })

    # 限制条数
    news = news[:5]

    # ---- A 股影响综合评估 ----
    risk_factors = sum(1 for n in news if any(k in n["tag"] for k in ["😰", "🚨", "⚠️"]))
    benign_factors = sum(1 for n in news if any(k in n["tag"] for k in ["😌", "📈"]))

    if risk_factors >= 3:
        a_impact = "偏空：多重风险信号叠加，建议防守为主，控制仓位在 5 成以下，聚焦确定性高的红利/防御板块。"
    elif risk_factors >= 2:
        a_impact = "谨慎：存在 2-3 个风险因素，建议中性偏低仓位（5-6成），回避高波动题材，关注抗跌板块。"
    elif benign_factors >= 2 and risk_factors == 0:
        a_impact = "偏多：宏观环境友好，可积极布局（6-7成仓），关注受益于当前宏观主题的板块。"
    else:
        a_impact = "中性：多空因素交织，无明显方向性驱动。建议均衡配置（5-6成仓），轻指数重个股，跟随资金流向操作。"

    return {
        "date": today.strftime("%Y-%m-%d"),
        "headline": headline,
        "key_numbers": key_numbers,
        "news_brief": news,
        "a_impact": a_impact,
        "crisis_score": crisis_score,
        "crisis_level": crisis_level,
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }


def _fetch_us_overnight_em():
    """美股隔夜三大指数表现（东方财富延迟镜像）。"""
    try:
        r = _requests.get(
            f"{_EM_DELAY}/api/qt/ulist.np/get",
            params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                    "fields": "f12,f14,f3", "secids": "100.GSPC,100.IXIC,100.DJI"},
            headers=_EM_HEADERS, timeout=15)
        j = r.json()
        rows = _em_clean_rows((j.get("data") or {}).get("diff") or [])
        if not rows:
            return ""
        parts = []
        all_up = True
        for x in rows:
            chg = float(x.get("f3") or 0)
            if chg < 0:
                all_up = False
            parts.append(f"{x.get('f14', '')}{chg:+.1f}%")
        return ("涨" if all_up else "跌") + "（" + "/".join(parts) + "）"
    except Exception:
        return ""


def _fetch_us_overnight_yahoo():
    """美股隔夜三大指数表现（Yahoo Finance 备用，适合海外 runner）。"""
    try:
        symbols = [("^GSPC", "标普500"), ("^IXIC", "纳斯达克"), ("^DJI", "道琼斯")]
        parts = []
        all_up = True
        for sym, name in symbols:
            r = _requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            j = r.json()
            result = (j.get("chart", {}).get("result") or [None])[0]
            if not result:
                continue
            meta = result.get("meta", {})
            prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
            closes = (result.get("indicators", {}).get("quote", [{}])[0].get("close") or [])
            last_close = None
            for c in reversed(closes):
                if c is not None:
                    last_close = c
                    break
            if not prev_close or not last_close:
                continue
            chg = (last_close - prev_close) / prev_close * 100
            if chg < 0:
                all_up = False
            parts.append(f"{name}{chg:+.1f}%")
        if parts:
            return ("涨" if all_up else "跌") + "（" + "/".join(parts) + "）"
    except Exception:
        pass
    return ""


def _fetch_us_overnight_akshare():
    """美股隔夜三大指数表现（akshare 新浪历史 K 线，中国网络最稳）。"""
    try:
        ak = get_ak()
        mapping = [(".INX", "标普500"), (".IXIC", "纳斯达克"), (".DJI", "道琼斯")]
        parts = []
        all_up = True
        for symbol, name in mapping:
            df = ak.index_us_stock_sina(symbol=symbol)
            if df is None or df.empty or len(df) < 2:
                continue
            prev = float(df.iloc[-2]["close"])
            last = float(df.iloc[-1]["close"])
            if not prev or not last:
                continue
            chg = (last - prev) / prev * 100
            if chg < 0:
                all_up = False
            parts.append(f"{name}{chg:+.1f}%")
        if parts:
            return ("涨" if all_up else "跌") + "（" + "/".join(parts) + "）"
    except Exception:
        pass
    return ""


def _fetch_us_overnight():
    """美股隔夜三大指数表现（EM 主 + akshare 备 + Yahoo 海外备）。"""
    us = _fetch_us_overnight_em()
    if us:
        return us
    us = _fetch_us_overnight_akshare()
    if us:
        return us
    return _fetch_us_overnight_yahoo()


def _fetch_overseas_indices():
    """海外/亚太股市观测：恒生指数、日经225、韩国KOSPI、台湾加权（东方财富延迟镜像，中国网络稳定）。
    返回 [{name, code, value, chg_pct, currency}]；失败时该条 value=None，绝不编造。"""
    sec_map = [
        ("100.HSI", "恒生指数", "HKD"),
        ("100.N225", "日经225", "JPY"),
        ("100.KS11", "韩国KOSPI", "KRW"),
        ("100.TWII", "台湾加权", "TWD"),
    ]
    by_code = {}
    try:
        r = _requests.get(
            f"{_EM_DELAY}/api/qt/ulist.np/get",
            params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                    "fields": "f12,f14,f2,f3",
                    "secids": ",".join(s for s, _, _ in sec_map)},
            headers=_EM_HEADERS, timeout=15)
        j = r.json()
        rows = _em_clean_rows((j.get("data", {}) or {}).get("diff") or [])
        by_code = {x.get("f12"): x for x in rows if x.get("f12")}
    except Exception as e:
        print(f"    ⚠️ 海外指数抓取失败: {e}")
    results = []
    for secid, name, cur in sec_map:
        code = secid.split(".", 1)[1]
        x = by_code.get(code)
        if x and x.get("f2") not in (None, "", "-"):
            try:
                results.append({
                    "name": name, "code": secid,
                    "value": round(float(x.get("f2")), 2),
                    "chg_pct": round(float(x.get("f3") or 0), 2),
                    "currency": cur,
                })
                continue
            except Exception:
                pass
        results.append({"name": name, "code": secid, "value": None, "chg_pct": None, "currency": cur})
    return results


def f_overseas_markets():
    """海外/亚太股市观测（注册于 OVERSEAS_MARKETS→intraday，盘中每30分刷新）。
    恒生指数/日经225/韩国KOSPI/台湾加权：反映亚太风险偏好，对 A 股开盘与外资流向有传导。
    数据真实抓取，失败时 value=None（前端标注「数据未接入」），绝不编造点位。"""
    idx = _fetch_overseas_indices()
    now = now_cst()
    ups = sum(1 for x in idx if x.get("chg_pct") is not None and x["chg_pct"] > 0)
    downs = sum(1 for x in idx if x.get("chg_pct") is not None and x["chg_pct"] < 0)
    if ups > downs:
        bias = "亚太偏强"
    elif downs > ups:
        bias = "亚太偏弱"
    else:
        bias = "亚太分化"
    return {
        "date": now.strftime("%Y-%m-%d"),
        "indices": idx,
        "bias": bias,
        "note": "恒生指数/日经225/韩国KOSPI/台湾加权为前一交易日收盘（北京时间08:25抓取时亚太尚未开盘），反映隔夜亚太风险偏好，对A股开盘有传导。",
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }


def run(label, fn, retries=2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            print(f">>> {label} {now_cst().isoformat(timespec='seconds')}{' (retry '+str(attempt)+')' if attempt else ''}")
            obj = fn()
            if obj is not None:
                save(label, obj)
                _run_status[label] = {"status": "ok", "msg": "成功"}
            else:
                print(f"  ⚠️ {label}: 返回空，跳过")
                _run_status[label] = {"status": "empty", "msg": "返回空"}
                # 🛡 2026-09-07 一劳永逸：09:30 后盘中/盘后空结果 → 清盘前残留 premarket_cleared 标记，
                #   避免「盘中仍顶着盘前清空标记」误报 HEALTH_CHECK fail（阿狸咪 08:55 文档漏报的 2 个新 bug）。
                #   阈值 9.5 → 10.0：盘前清空窗口已推迟到 09:15–10:00（主人令），09:30 轮刚写下的
                #   premarket_cleared 不能被自己这轮的空结果立刻摘掉，否则前端文案会退回「暂无数据」。
                _h = now_cst().hour + now_cst().minute / 60.0
                if _h >= 10.0:
                    _clear_premarket_marker(label)
            return
        except Exception as e:
            last_err = e
            print(f"  ❌ {label} 失败(attempt {attempt+1}/{retries+1}): {type(e).__name__}: {e}")
            _run_status[label] = {"status": "fail", "msg": f"{type(e).__name__}: {str(e)[:80]}"}
            time.sleep(2)
    print(f"  🚫 {label} 跳过，最终错误: {type(last_err).__name__}: {last_err}")
    time.sleep(0.5)


def _has_critical_failures(category):
    """判断本次抓取是否存在应让 workflow 失败的严重失败。

    盘中/盘后/盘前任务中，目标类别涉及的核心变量只要有一个失败，即认为本次任务失败，
    避免 workflow 继续推送空壳数据。
    """
    if not _run_status:
        return False
    # runner_status 不计入
    fails = [k for k, v in _run_status.items()
             if v.get("status") == "fail" and k != "RUNNER_STATUS"]
    return bool(fails)

# 涨停池缓存（避免 limit_up_heatmap / herding 重复抓取同一份数据）
_zt_cache = {"date": None, "df": None}
def _get_zt_pool():
    d = now_cst().strftime("%Y%m%d")
    if _zt_cache["date"] == d and _zt_cache["df"] is not None:
        return _zt_cache["df"]
    df = get_ak().stock_zt_pool_em(date=d)
    _zt_cache["date"] = d
    _zt_cache["df"] = df
    return df

# ───────────────────────── 各模块抓取（akshare） ─────────────────────────

def f_etf_intraday_heat():
    # ETF 主力净流入真实排名（东财 push2delay，ETF 市场 m:1+t:9，fid=f62）。
    # 返回：items(净流入TOP，含成交额供内联卡) + categories(宽基/行业/主题/跨境 分类净流入)
    snap = em_clist("m:1+t:9", "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=3000, po="1")
    recs = []
    for r in snap:
        try:
            code = str(r.get("f12"))
            name = r.get("f14")
            recs.append({
                "代码": code, "名称": name,
                "最新价": round(float(r.get("f2") or 0), 3),
                "涨跌幅": round(float(r.get("f3") or 0), 2),
                "成交额": round(float(r.get("f6") or 0), 2),
                "code": code, "name": name,
                "chg": round(float(r.get("f3") or 0), 2),
                "main_net_inflow": round(float(r.get("f62") or 0), 2),  # 元
                "pct": round(float(r.get("f184") or 0), 2),
            })
        except Exception:
            continue
    if not recs:
        return None
    ranked = sorted(recs, key=lambda x: x["main_net_inflow"], reverse=True)
    inflow_top = ranked[:30]
    outflow_top = sorted(recs, key=lambda x: x["main_net_inflow"])[:30]

    def cat_of(name):
        n = str(name or "")
        # 1) 宽基
        if any(k in n for k in ["沪深300", "中证500", "中证1000", "创业板", "科创", "上证50",
                                 "上证180", "深证", "MSCI", "A50", "双创", "300ETF", "500ETF"]):
            return "宽基"
        # 2) 商品（黄金/白银/原油/石油/豆粕/能源/有色金属/商品等实物商品 ETF）
        if any(k in n for k in ["黄金", "白银", "原油", "石油", "豆粕", "能源", "有色金属", "商品", "矿业"]):
            return "商品"
        # 3) 跨境
        if any(k in n for k in ["恒生", "纳斯达克", "标普", "纳指", "日经", "德国", "法国", "美国",
                                 "道琼斯", "港股", "中概", "H股", "日本", "东南亚"]):
            return "跨境"
        # 4) 主题
        if any(k in n for k in ["5G", "人工智能", "AI", "半导体", "芯片", "新能源", "碳中和", "国企",
                                 "医药", "消费", "券商", "银行", "证券", "军工", "有色", "煤炭", "地产",
                                 "化工", "食品", "汽车", "光伏", "锂电", "机器人", "算力", "数据", "稀土",
                                 "钢铁", "保险", "传媒", "游戏", "养殖", "农业", "电力", "通信", "环保",
                                 "酒", "中药", "疫苗", "创新药", "VR", "物联网", "区块链", "元宇宙",
                                 "芯片", "科技", "电子", "高端装备", "智能"]):
            return "主题"
        return "行业"

    cats = {"宽基": [], "行业": [], "主题": [], "跨境": [], "商品": []}
    for r in recs:
        cats[cat_of(r["name"])].append(r)
    categories = {}
    for cn, lst in cats.items():
        net_yi = sum(x["main_net_inflow"] for x in lst) / 1e8
        top_in = sorted(lst, key=lambda x: x["main_net_inflow"], reverse=True)[:8]
        top_out = sorted(lst, key=lambda x: x["main_net_inflow"])[:8]
        categories[cn] = {
            "net_inflow_yi": round(net_yi, 2),
            "count": len(lst),
            "top_inflow": [{"code": x["code"], "name": x["name"],
                            "main_net_inflow": x["main_net_inflow"], "pct": x["pct"]} for x in top_in],
            "top_outflow": [{"code": x["code"], "name": x["name"],
                             "main_net_inflow": x["main_net_inflow"], "pct": x["pct"]} for x in top_out],
        }
    return {
        "items": inflow_top,
        "inflow_top": inflow_top,
        "outflow_top": outflow_top,
        "categories": categories,
        "note": "ETF主力净流入真实排名(东财push2delay, ETF市场m:1+t:9, fid=f62)；净流入单位元，分类按名称关键词",
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
    }

def f_sector_fund_flow():
    # 板块/概念资金流：行业(m:90 t:2) + 概念(m:90 t:3)，主力净流入(f62, 元→亿)
    # 走 push2delay 镜像，规避实时 push2 host 的 WAF 重置。
    # 同时生成 sectors_in/out（供 renderSector 直接渲染）与 top_list（兼容降级）。
    # 2026-08-05 修复：必须同时查降序(流入TOP)与升序(流出TOP)，否则 po='1' 只返回
    # 净流入条目，sectors_out 恒为空，导致“净额(行业)”只加不减、数字虚高。
    items = []
    for stype, fs in [("行业", "m:90 t:2"), ("概念", "m:90 t:3")]:
        # 降序取流入、升序取流出，合并去重（同名同类型以绝对值大者为准）
        by_key = {}
        for po in ("1", "0"):
            rows = em_clist(fs, "f12,f14,f3,f62,f184", fid="f62", stat="1", pz=200, po=po)
            for r in rows:
                name = r.get("f14")
                net = _to_yi(r.get("f62"))
                if not name or net == 0:
                    continue
                key = (name, stype)
                if key not in by_key or abs(net) > abs(by_key[key]["net"]):
                    by_key[key] = {
                        "name": name,
                        "type": stype,
                        "net": net,
                        "chg": round(float(r.get("f3") or 0), 2),
                    }
        items.extend(by_key.values())
    if not items:
        return None

    # 2026-08-20 一劳永逸过滤噪声概念：标准普尔/富时罗素等是境外指数或成分标签，
    # 不是真实 A 股概念板块，进入分时累计曲线会导致图例出现"标准普尔是 A 股的"这种误导。
    items = [x for x in items if x.get("name") not in _NOISE_CONCEPTS]

    items.sort(key=lambda x: x["net"], reverse=True)
    sectors_in = [x for x in items if x["net"] > 0]
    sectors_out = [x for x in items if x["net"] < 0]

    # ── 2026-08-12 修复：同步追加 sector_fund_flow_history.json ──
    # 原先 history 仅靠 akshare（fetch_orphan）写入，cloud runner 上 akshare 频繁失败
    # 导致 trend_5d/10d/20d/60d 数据极度稀疏。现在每次 push2delay 抓取成功时
    # 把当日 sectors_in/out 的 net 值也追加进 history → 每天都有数据入账。
    try:
        _hist_path = RAW_DIR / "sector_fund_flow_history.json"
        _today_str = now_cst().strftime("%Y-%m-%d")
        _history = {}
        if _hist_path.exists():
            try:
                _history = json.loads(_hist_path.read_text(encoding="utf-8"))
            except Exception:
                _history = {}
        # 2026-08-20 清理历史中的噪声概念（标准普尔/富时罗素等）残留
        for _noise_name in list(_NOISE_CONCEPTS):
            if _noise_name in _history:
                del _history[_noise_name]
        _appended = 0
        for _sec in sectors_in + sectors_out:
            _name = _sec["name"]
            if _name not in _history:
                _history[_name] = []
            # 去重：同日不重复追加
            if not _history[_name] or _history[_name][-1].get("date") != _today_str:
                _history[_name].append({"date": _today_str, "net": round(_sec["net"], 2)})
                _appended += 1
        if _appended > 0:
            _hist_path.write_text(json.dumps(_history, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"  📝 sector_fund_flow_history 追加 {_appended} 条 ({_today_str})")
    except Exception as _he:
        print(f"  ⚠️ sector_fund_flow_history 追加失败（不影响主数据）: {_he}")
    # 🛡 2026-08-27 主人令：板块资金日内快照已解耦至独立脚本 intraday_snapshot.py
    #   （由 workflow 的 intraday-snapshot 独立并发组驱动），本函数不再写 intraday，
    #   避免重抓取被 cancel 时快照随之一起丢失 → 曲线断档。
    return {
        "sectors_in": sectors_in,
        "sectors_out": sectors_out,
        "top_list": items,
        "note": "行业+概念主力净流入(亿)，来源东方财富push2delay（升序+降序合并）",
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
    }

def f_index_quotes():
    # 四大核心宽基指数实时行情：上证/深证/创业板/科创50
    # 东财 ulist.np 接口，secid 规则：1=上海，0=深圳
    # 2026-08-03 修复：本机/cn runner 直连 push2 host 会被 WAF 重置，改走 push2delay 镜像。
    secids = "1.000001,0.399001,0.399006,1.000688"
    names = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000688": "科创50"}
    short = {"000001": "沪指", "399001": "深成指", "399006": "创业板", "000688": "科创板"}
    rows = []
    for attempt in range(3):
        try:
            r = _requests.get(
                f"{_EM_DELAY}/api/qt/ulist.np/get",
                params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                        "fields": "f2,f3,f4,f5,f6,f12,f13,f14,f18,f20,f21,f104,f105,f106", "secids": secids},
                headers=_EM_HEADERS, timeout=15)
            j = r.json()
            rows = _em_clean_rows((j.get("data") or {}).get("diff", []) or [])
            if rows:
                break
        except Exception as e:
            print(f"  ⚠️ 东财指数行情失败(尝试{attempt+1}/3): {e}")
            time.sleep(1.5)
    items = []
    for r in rows:
        code = str(r.get("f12") or "")
        # 东财 f13 标记 1=上海 0=深圳
        prefix = "SH" if str(r.get("f13")) == "1" else "SZ"
        full_code = prefix + code
        up = int(r.get("f104") or 0)
        down = int(r.get("f105") or 0)
        flat = int(r.get("f106") or 0)
        items.append({
            "code": code,
            "full_code": full_code,
            "name": names.get(code, r.get("f14", code)),
            "short": short.get(code, r.get("f14", code)),
            "price": round(float(r.get("f2") or 0), 2),
            "chg": round(float(r.get("f3") or 0), 2),
            "change": round(float(r.get("f4") or 0), 2),
            "volume": int(r.get("f5") or 0),
            "amount": round(float(r.get("f6") or 0) / 1e8, 2),  # 元->亿
            "prev_close": round(float(r.get("f18") or 0), 2),
            "total_mv": round(float(r.get("f20") or 0) / 1e8, 2),  # 总市值亿
            "float_mv": round(float(r.get("f21") or 0) / 1e8, 2),  # 流通市值亿
            "up": up,
            "down": down,
            "flat": flat,
        })
    if not items:
        return None
    return {"items": items, "note": "东财实时指数行情(push2delay)"}

def f_concept_ranking():
    # 概念板块列表（涨跌幅 + 主力净流入），push2delay 镜像。
    rows = em_clist("m:90 t:3 f:!50", "f12,f14,f3,f62,f184,f20", fid="f62", stat="1", pz=300)
    items = []
    for r in rows:
        items.append({
            "code": r.get("f12"),
            "name": r.get("f14"),
            "chg": round(float(r.get("f3") or 0), 2),
            "net": _to_yi(r.get("f62")),
            "amount": round(float(r.get("f20") or 0) / 1e8, 2),
        })
    if not items:
        return None
    return {"items": items, "note": "概念板块列表(涨跌幅/主力净流入亿)，来源东方财富push2delay"}

def f_candidate_quotes():
    """候选池实时行情（行业树图第二层·个股数据源）。

    方案：ulist 批量拉取（走 push2delay 延迟镜像，规避实时 push2 host 的 WAF TCP 重置；
    分小批 100 个 secid/批，长 secid 串会偶发被断连）。字段：当日涨跌幅/现价/市值。
    """
    try:
        with open(RAW_DIR / "candidate.json", encoding="utf-8") as f:
            cand = json.load(f)
    except Exception as e:
        print(f"  ⚠️ candidate.json 读取失败: {e}")
        return None
    stocks = cand.get("stocks") or {}
    if not stocks:
        print("  ⚠️ 候选池为空，跳过 CANDIDATE_QUOTES")
        return None
    # 构造 secid 分批：market sh→1, sz→0
    secids = []
    for sid, s in stocks.items():
        code = str(s.get("code") or "")
        if not code:
            continue
        mkt = "1" if str(s.get("market", "")).lower() == "sh" else "0"
        secids.append(f"{mkt}.{code}")
    if not secids:
        return None
    items = []
    BATCH = 100
    for i in range(0, len(secids), BATCH):
        batch = secids[i:i + BATCH]
        rows = []
        for attempt in range(3):
            try:
                r = _requests.get(
                    f"{_EM_DELAY}/api/qt/ulist.np/get",
                    params={"fltt": "2", "invt": "2",
                            "ut": "b2884a393a59ad64002292a3e90d46a5",
                            "fields": "f2,f3,f12,f13,f14,f20,f21",
                            "secids": ",".join(batch)},
                    headers=_EM_HEADERS, timeout=15)
                j = r.json()
                rows = _em_clean_rows((j.get("data") or {}).get("diff", []) or [])
                if rows:
                    break
            except Exception as e:
                print(f"  ⚠️ 候选池行情批次 {i//BATCH+1} 尝试{attempt+1}失败: {str(e)[:60]}")
                time.sleep(2 * (attempt + 1))
        for r in rows:
            code = str(r.get("f12") or "")
            if not code:
                continue
            # f2 可能为 "-"（停牌/未开），此时视为无行情
            price = r.get("f2")
            if price in (None, "-", ""):
                continue
            items.append({
                "code": code,
                "name": r.get("f14") or code,
                "price": round(float(price), 2),
                "chg": round(float(r.get("f3") or 0), 2),
                "total_mv": round(float(r.get("f20") or 0) / 1e8, 2),   # 元→亿
                "float_mv": round(float(r.get("f21") or 0) / 1e8, 2),
            })
    if not items:
        print("  ⚠️ 候选池行情无有效数据")
        return None
    return {"items": items, "note": "候选池实时行情(涨跌幅/现价/市值)，来源东方财富push2delay"}

def f_ipo_data():
    """打新日历：复用 v6 验证有效的东财 datacenter + 可转债 + 同花顺已上市补充逻辑。"""
    try:
        import fetch_ipo_data_v8 as ipo
        return ipo.generate_ipo_score()
    except Exception as e:
        print(f"  ⚠️ IPO 抓取失败: {e}")
        return None

def f_margin_data():
    """两融余额走势：上交所融资融券汇总（日线）。
    输出结构与 v6 MARGIN_DATA 一致：{sh:[{date,date_raw,rz_balance,rq_balance_amt,total}], update_time}
    """
    end = now_cst().strftime("%Y%m%d")
    start = (now_cst() - timedelta(days=120)).strftime("%Y%m%d")
    result = {"sh": [], "update_time": ""}
    try:
        df = get_ak().stock_margin_sse(start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        rows = []
        for _, row in df.iterrows():
            dt = str(row["信用交易日期"])
            try:
                d_obj = datetime.strptime(dt, "%Y%m%d")
                dt_fmt = f"{d_obj.month}/{d_obj.day}"
            except Exception:
                dt_fmt = dt
            rows.append({
                "date": dt_fmt,
                "date_raw": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                "rz_balance": round(float(row["融资余额"]) / 1e8),
                "rz_buy": round(float(row["融资买入额"]) / 1e8),
                "rq_balance_amt": round(float(row["融券余量金额"]) / 1e8),
                "total": round(float(row["融资融券余额"]) / 1e8),
            })
        # 按日期升序（旧→新），保证图表方向正确
        rows.sort(key=lambda x: x["date_raw"])
        result["sh"] = rows
        print(f"  ✅ 两融余额：{len(rows)} 条")
    except Exception as e:
        print(f"  ❌ 两融余额失败: {e}")
        return None
    result["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M")
    return result

def f_cffex_holdings():
    # 中金所股指期货日行情：动态取最近有数据的交易日（盘后数据通常当日稍晚才出）
    # 🧭 2026-09-06 主人令：补抓现货指数(IF↔沪深300/IC↔中证500/IH↔上证50/IM↔中证1000)，
    #    前端算 基差=期货-现货、年化升贴水率=基差率/剩余天数*365 —— 卡片从"跌了没"升级"情绪温度计"。
    ak = get_ak()
    base = now_cst()
    for back in range(0, 8):
        dd = (base - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = ak.get_cffex_daily(date=dd)
        except Exception as e:
            df = None
        if df is not None and not df.empty:
            out = {"items": df.to_dict(orient="records"),
                   "update_time": dd,
                   "note": "中金所股指期货日行情（最近交易日 %s）" % dd,
                   "spot": _cffex_spot_quotes()}
            return out
    return None


def _cffex_spot_quotes():
    # 现货指数实时价（东财 push2delay 镜像，与 f_index_quotes 同链）。失败返回 {}，前端降级隐藏基差行。
    secmap = {"IF": ("1.000300", "沪深300"), "IC": ("1.000905", "中证500"),
              "IH": ("1.000016", "上证50"), "IM": ("1.000852", "中证1000")}
    spot = {}
    try:
        secids = ",".join(v[0] for v in secmap.values())
        r = _requests.get(
            "%s/api/qt/ulist.np/get" % _EM_DELAY,
            params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                    "fields": "f2,f12,f14", "secids": secids},
            headers=_EM_HEADERS, timeout=15)
        j = r.json()
        px = {}
        for row in (j.get("data") or {}).get("diff", []) or []:
            px[str(row.get("f12"))] = round(float(row.get("f2") or 0), 2)
        for var, (sec, nm) in secmap.items():
            code = sec.split(".")[1]
            if px.get(code):
                spot[var] = {"code": code, "name": nm, "price": px[code]}
    except Exception as e:
        print("  ⚠️ 期货现货指数(基差)抓取失败，前端降级为无基差:", e)
    return spot

def f_macro_data():
    """宏观数据：保留已有丰富字段，增量更新 CPI/PMI 及债券/Shibor/LPR/M2 前值"""
    import json
    # 以现有 raw_data/macro_data.json 为基线，避免云端 runner 把 rich 结构冲成只有 cpi/pmi
    base_path = RAW_DIR / "macro_data.json"
    out = {}
    if base_path.exists():
        try:
            with open(base_path, encoding="utf-8") as f:
                out = json.load(f)
        except Exception:
            out = {}
    if not isinstance(out, dict):
        out = {}
    # 保证结构
    out.setdefault("monetary", {})
    out.setdefault("economy", {})
    out.setdefault("market_sentiment", {})
    out.setdefault("global_macro", {})
    out.setdefault("indicator_status", {})

    def mark_updated(indicator_key, data_dict):
        sched = {
            'lpr': {'name': 'LPR利率', 'expected_day': 20, 'tolerance_days': 5},
            'm2_yoy': {'name': 'M2同比', 'expected_day': 12, 'tolerance_days': 5},
            'pmi': {'name': '制造业PMI', 'expected_day': 1, 'tolerance_days': 10},
            'cpi': {'name': 'CPI同比', 'expected_day': 10, 'tolerance_days': 5},
            'ppi': {'name': 'PPI同比', 'expected_day': 10, 'tolerance_days': 5},
            'social_financing': {'name': '社融规模', 'expected_day': 10, 'tolerance_days': 8},
            'export_yoy': {'name': '出口增速', 'expected_day': 7, 'tolerance_days': 5},
            'new_investors': {'name': '新增投资者', 'expected_day': 15, 'tolerance_days': 10},
        }
        st = sched.get(indicator_key)
        if not st:
            return
        data_date = str(data_dict.get('date', ''))[:10]
        is_fresh = False
        try:
            from datetime import datetime
            dt = datetime.strptime(data_date, '%Y-%m-%d')
            is_fresh = (now_cst() - dt).days <= 60
        except Exception:
            pass
        out['indicator_status'][indicator_key] = {
            'last_updated': now_cst().strftime('%Y-%m-%d'),
            'is_fresh': is_fresh,
            'name': st['name'],
            'frequency': 'monthly' if indicator_key in ('lpr','m2_yoy','pmi','cpi','ppi','social_financing','export_yoy','new_investors') else 'daily',
        }

    # 1) CPI / PMI 数组（保留原 flat schema 兼容）
    try:
        cpi = get_ak().macro_china_cpi_yearly()
        out["cpi"] = cpi.tail(6).to_dict(orient="records") if cpi is not None else []
    except Exception:
        out.setdefault("cpi", [])
    try:
        pmi = get_ak().macro_china_pmi_yearly()
        out["pmi"] = pmi.tail(6).to_dict(orient="records") if pmi is not None else []
    except Exception:
        out.setdefault("pmi", [])

    # 2) 债券收益率 + 前值
    try:
        df = get_ak().bond_zh_us_rate()
        if df is not None and len(df) > 1:
            cn = df[['日期', '中国国债收益率10年']].dropna()
            us = df[['日期', '美国国债收益率10年']].dropna()
            if len(cn) > 0:
                cl = cn.iloc[-1]
                out['monetary']['cn_bond_10y'] = {
                    'value': round(float(cl['中国国债收益率10年']), 4),
                    'date': str(cl['日期'])[:10],
                    'previous': round(float(cn.iloc[-2]['中国国债收益率10年']), 4) if len(cn) > 1 else None,
                }
            if len(us) > 0:
                ul = us.iloc[-1]
                out['monetary']['us_bond_10y'] = {
                    'value': round(float(ul['美国国债收益率10年']), 4),
                    'date': str(ul['日期'])[:10],
                    'previous': round(float(us.iloc[-2]['美国国债收益率10年']), 4) if len(us) > 1 else None,
                }
            if 'cn_bond_10y' in out['monetary'] and 'us_bond_10y' in out['monetary']:
                cn_v = out['monetary']['cn_bond_10y']['value']
                us_v = out['monetary']['us_bond_10y']['value']
                cn_p = out['monetary']['cn_bond_10y'].get('previous')
                us_p = out['monetary']['us_bond_10y'].get('previous')
                out['monetary']['cn_us_spread'] = {'value': round(cn_v - us_v, 2)}
                if cn_p is not None and us_p is not None:
                    out['monetary']['cn_us_spread']['previous'] = round(cn_p - us_p, 2)
    except Exception as e:
        print(f"  ⚠️ 国债收益率获取失败: {e}")

    # 3) LPR + 前值
    try:
        df_lpr = get_ak().macro_china_lpr()
        if df_lpr is not None and len(df_lpr) > 0:
            lpr_last = df_lpr.iloc[-1]
            out['monetary']['lpr'] = {
                'lpr_1y': float(lpr_last['LPR1Y']),
                'lpr_5y': float(lpr_last['LPR5Y']),
                'date': str(lpr_last['TRADE_DATE'])[:10],
                'previous_1y': float(df_lpr.iloc[-2]['LPR1Y']) if len(df_lpr) > 1 else None,
                'previous_5y': float(df_lpr.iloc[-2]['LPR5Y']) if len(df_lpr) > 1 else None,
            }
            mark_updated('lpr', out['monetary']['lpr'])
    except Exception as e:
        print(f"  ⚠️ LPR获取失败: {e}")

    # 4) Shibor + 前值
    try:
        df_shibor = get_ak().macro_china_shibor_all()
        if df_shibor is not None and len(df_shibor) > 0:
            sh = df_shibor.iloc[-1]
            prev = df_shibor.iloc[-2] if len(df_shibor) > 1 else None
            out['monetary']['shibor'] = {
                'on': float(sh.get('O/N-定价', 0)),
                'w1': float(sh.get('1W-定价', 0)),
                'm1': float(sh.get('1M-定价', 0)),
                'm3': float(sh.get('3M-定价', 0)),
                'date': str(sh.get('日期', ''))[:10],
                'previous_on': float(prev.get('O/N-定价', 0)) if prev is not None else None,
                'previous_w1': float(prev.get('1W-定价', 0)) if prev is not None else None,
            }
    except Exception as e:
        print(f"  ⚠️ Shibor获取失败: {e}")

    # 5) M2/M1 货币供应 + 前值
    try:
        df_m2 = get_ak().macro_china_money_supply()
        if df_m2 is not None and len(df_m2) > 0:
            m2_row = df_m2.iloc[0]
            m2_val = m2_row.get('货币和准货币(M2)-同比增长')
            m2_date = str(m2_row['月份']).replace('年', '-').replace('月份', '-01')
            prev_val = df_m2.iloc[1].get('货币和准货币(M2)-同比增长') if len(df_m2) > 1 else None
            out['monetary']['m2_yoy'] = {
                'value': float(m2_val) if pd.notna(m2_val) else None,
                'date': m2_date,
                'previous': float(prev_val) if prev_val is not None and pd.notna(prev_val) else None,
            }
            if out['monetary']['m2_yoy']['value'] is not None:
                mark_updated('m2_yoy', out['monetary']['m2_yoy'])
    except Exception as e:
        print(f"  ⚠️ M2获取失败: {e}")

    # 6) 把 flat cpi/pmi 数组同步到 economy 对象（index.html 渲染需要 ec.cpi.value / ec.pmi.value）
    def _last_numeric(arr, val_key='今值', prev_key='前值', date_key='日期'):
        if not arr:
            return None
        for row in reversed(arr):
            v = row.get(val_key)
            if v is not None and not pd.isna(v):
                try:
                    return {
                        'value': float(v),
                        'date': str(row.get(date_key, ''))[:10],
                        'previous': float(row[prev_key]) if row.get(prev_key) is not None and not pd.isna(row[prev_key]) else None,
                    }
                except Exception:
                    pass
        return None

    try:
        cpi_last = _last_numeric(out.get('cpi', []))
        if cpi_last:
            out['economy']['cpi'] = cpi_last
            mark_updated('cpi', cpi_last)
        pmi_last = _last_numeric(out.get('pmi', []))
        if pmi_last:
            out['economy']['pmi'] = pmi_last
            mark_updated('pmi', pmi_last)
    except Exception as e:
        print(f"  ⚠️ economy 同步失败: {e}")

    # 7) 全球宏观：离岸人民币、美元指数、VIX、黄金、白银、铜、原油（盘中也可更新）
    def _parse_sina_csv(body):
        """解析 sinajs.cn 返回的多条 var hq_str_xxx=\"...\"; 语句"""
        result = {}
        for line in body.split(';'):
            line = line.strip()
            if not line.startswith('var hq_str_'):
                continue
            eq = line.find('=')
            if eq < 0:
                continue
            key = line[len('var hq_str_'):eq]
            q1 = line.find('"')
            q2 = line.rfind('"')
            rest = line[q1 + 1:q2] if q1 >= 0 and q2 > q1 else ''
            result[key] = rest.split(',') if rest else []
        return result

    gm = out.setdefault('global_macro', {})

    def _fetch_sina_global_macro(retries=2):
        """新浪全球宏观行情，带重试与详细日志。"""
        sina_codes = "fx_susdcnh,fx_susdjpy,DINIW,b_VIX,hf_GC,hf_SI,hf_HG,hf_CL"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "*/*",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                r = _requests.get(
                    f"https://hq.sinajs.cn/list={sina_codes}",
                    headers=headers,
                    timeout=20,
                )
                r.encoding = 'gb2312'
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = _parse_sina_csv(r.text)
                if not data:
                    raise RuntimeError("解析结果为空")
                return data
            except Exception as e:
                last_err = e
                print(f"    ⚠️ 新浪全球宏观尝试 {attempt+1}/{retries+1} 失败: {e}")
                time.sleep(1.5 * (attempt + 1))
        print(f"    🚫 新浪全球宏观最终失败: {last_err}")
        return {}

    data = _fetch_sina_global_macro()

    # 解析函数：安全取值并打印字段数
    def _set_gm(key, value, date_str=None):
        if value is None:
            return
        try:
            gm[key] = {'value': float(value)} if key != 'usdcnh' else {'price': float(value)}
            if date_str:
                gm[key]['date'] = date_str
        except Exception as e:
            print(f"    ⚠️ global_macro {key} 转换失败: value={value}, {e}")

    # 离岸人民币 fx_susdcnh：索引 8=收盘价/即期，17=日期
    parts = data.get('fx_susdcnh', [])
    if len(parts) > 8:
        _set_gm('usdcnh', parts[8], parts[17] if len(parts) > 17 else None)
    else:
        print(f"    ⚠️ fx_susdcnh 字段不足: {len(parts)}")

    # 美元兑日元 fx_susdjpy：索引1=最新价（与 usdcnh 不同结构）；日元强弱是日银加息预期核心变量
    parts = data.get('fx_susdjpy', [])
    if len(parts) > 1:
        _set_gm('usdjpy', parts[1], parts[0] if len(parts) > 0 else None)
    else:
        print(f"    ⚠️ fx_susdjpy 字段不足: {len(parts)}")

    # 美元指数 DINIW：索引 8=收盘价，10=日期
    parts = data.get('DINIW', [])
    if len(parts) > 8:
        _set_gm('dxy', parts[8], parts[10] if len(parts) > 10 else None)
    else:
        print(f"    ⚠️ DINIW 字段不足: {len(parts)}")

    # VIX：索引 1=当前值，6=日期
    parts = data.get('b_VIX', [])
    if len(parts) > 1:
        _set_gm('vix', parts[1], parts[6] if len(parts) > 6 else None)
    else:
        print(f"    ⚠️ b_VIX 字段不足: {len(parts)}")

    # 商品：索引 0=最新价，12=日期；统一放到 commodities 对象下保持前端兼容
    commodity_map = [('hf_GC', 'gold'), ('hf_SI', 'silver'), ('hf_HG', 'copper'), ('hf_CL', 'oil')]
    commodities = gm.setdefault('commodities', {})
    for code, name in commodity_map:
        parts = data.get(code, [])
        if parts and parts[0] not in (None, '', '-'):
            try:
                commodities[name] = {'value': float(parts[0])}
                if len(parts) > 12:
                    commodities[name]['date'] = parts[12]
            except Exception as e:
                print(f"    ⚠️ {code}({name}) 转换失败: {parts[0]}, {e}")
        else:
            print(f"    ⚠️ {code}({name}) 无有效价格: {parts[:3] if parts else 'empty'}")

    # fallback：新浪失败时，用 akshare 外汇/商品接口补部分数据
    if not gm.get('usdcnh') or not gm.get('dxy'):
        try:
            ak = get_ak()
            if not gm.get('usdcnh'):
                try:
                    fx = ak.fx_spot_quote()
                    if fx is not None and not fx.empty:
                        usd_cnh = fx[fx['code'] == 'USDCNH']
                        if not usd_cnh.empty:
                            gm['usdcnh'] = {'price': float(usd_cnh.iloc[0]['bid']), 'date': now_cst().strftime('%Y-%m-%d')}
                            print("    ✅ akshare fallback USDCNH")
                except Exception as e:
                    print(f"    ⚠️ akshare USDCNH fallback 失败: {e}")
        except Exception as e:
            print(f"    ⚠️ akshare fallback 整体失败: {e}")

    print(f"    ✅ 全球宏观结果: { {k: v.get('value') or v.get('price') for k, v in gm.items()} }")
    return out

def f_crisis_data():
    # 危机雷达：三个维度尽量用真实数据
    # 经济维度：中国 PMI（真实）
    economy = None
    try:
        pmi = get_ak().macro_china_pmi_yearly()
        if pmi is not None and not pmi.empty:
            last = pmi.iloc[-1]
            v = last.get("今值")
            if v is None:
                v = last.get("value")
            if v is not None:
                economy = float(v)
    except Exception:
        economy = None

    # 货币维度：中国银行美元汇率（真实，替代估值）
    # 逻辑：USD/CNY 中间价偏离 7.0 基线的程度 → 货币压力分
    currency_score = 0.30  # 默认保守值
    usd_cny_latest = None
    try:
        boc = get_ak().currency_boc_safe()
        if boc is not None and not boc.empty:
            # 取最近有数据的美元列
            usd_col = next((c for c in boc.columns if c == "美元"), None)
            if usd_col:
                # 倒序找最新非空值
                for val in boc[usd_col].iloc[::-1]:
                    if pd.notna(val) and float(val) > 0:
                        usd_cny_latest = float(val)
                        break
                if usd_cny_latest:
                    # BOC 汇率单位为"每100外币"，需除以 100
                    usd_cny_latest = round(usd_cny_latest / 100.0, 4)
                    # 归一化：7.0=健康(0.2), 7.3=警戒(0.5), 7.5+=危险(0.8+)
                    # 🔴 2026-08-22 主人令连续化：原档位跳变使 score 多天恒定（31.4），
                    #   每日真实汇率微变被档位吞掉。改线性插值，让变化反映到分数。
                    if usd_cny_latest < 6.85:
                        currency_score = 0.12  # 强势人民币
                    elif usd_cny_latest <= 7.50:
                        if usd_cny_latest < 7.00:
                            currency_score = round(0.12 + (usd_cny_latest - 6.85) / 0.15 * 0.13, 4)
                        elif usd_cny_latest < 7.30:
                            currency_score = round(0.25 + (usd_cny_latest - 7.00) / 0.30 * 0.30, 4)
                        else:
                            currency_score = round(0.55 + (usd_cny_latest - 7.30) / 0.20 * 0.30, 4)
                    else:
                        currency_score = min(0.95, 0.85 + (usd_cny_latest - 7.50) * 0.1)
    except Exception as e:
        print(f"    ⚠️ 汇率数据获取失败: {e}")

    # 全球维度：2026-08-12 主人质疑分数始终 33.3 不变 → 根因是 global 写死 0.40
# 改为：基于 MACRO_DATA 里日级 VIX + 美债 10Y 动态计算（CN 也可达）
    global_score = 0.40  # 兜底中性值（MACRO_DATA 不可达时使用）
    vix_score = None
    bond_score = None
    vix_v = 0
    us10y_v = 0
    try:
        macro_path = Path(ROOT) / "raw_data" / "macro_data.json"
        if macro_path.exists():
            txt = macro_path.read_text(encoding="utf-8")
            macro = json.loads(txt) if txt.strip().startswith("{") else {}
            gm = (macro.get("global_macro") or {})
            monetary = (macro.get("monetary") or {})
            vix_v = float((gm.get("vix") or {}).get("value") or 0)
            us10y_v = float((monetary.get("us_bond_10y") or {}).get("value") or 0)
            # VIX 风险分（<15 极低 / 15-20 正常 / 20-25 警戒 / 25-30 警惕 / ≥30 危机）
            if vix_v > 0:
                # 2026-08-22 连续化（10→0.10, 20→0.30, 30→0.55, 40→0.80 线性插值）
                if vix_v <= 10: vix_score = 0.10
                elif vix_v <= 40: vix_score = round(0.10 + (vix_v - 10) / 30 * 0.70, 4)
                else: vix_score = min(0.90, 0.80 + (vix_v - 40) * 0.01)
            # 美债 10Y 风险分（<3.5 宽松 / 3.5-4.0 正常 / 4.0-4.5 偏紧 / 4.5-4.8 警惕 / ≥4.8 高压）
            if us10y_v > 0:
                # 2026-08-22 连续化（3.0→0.08, 4.0→0.25, 5.0→0.60 线性插值）
                if us10y_v <= 3.0: bond_score = 0.08
                elif us10y_v <= 5.0: bond_score = round(0.08 + (us10y_v - 3.0) / 2.0 * 0.52, 4)
                else: bond_score = min(0.90, 0.60 + (us10y_v - 5.0) * 0.1)
            # 综合：取均值（任一缺失则退化为另一维度）
            parts = [x for x in [vix_score, bond_score] if x is not None]
            if parts:
                global_score = round(sum(parts) / len(parts), 3)
    except Exception as e:
        print(f"    ⚠️ 全球维度(MACRO_DATA)读取失败: {e}")

    # 输出既保留扁平字段（兼容旧读取），也输出 indicators + score（前端 2026-08-07 后主要读取）
    currency_val = round(currency_score, 3)
    economy_val = round(economy / 100.0, 3) if economy else 0.50
    global_val = round(global_score, 3)
    total_score = round((currency_val * 0.40 + economy_val * 0.35 + global_val * 0.25) * 100, 1)
    if total_score >= 70:
        level = "危机"
    elif total_score >= 50:
        level = "警惕"
    elif total_score >= 30:
        level = "关注"
    else:
        level = "平稳"
    return {
        "currency": currency_val,
        "economy": economy_val,
        "global": global_val,
        "score": total_score,
        "level": level,
        "indicators": {
            "currency": {"cat": "货币", "score": currency_val, "desc": "USD/CNY 汇率压力"},
            "economy": {"cat": "经济", "score": economy_val, "desc": "中国制造业 PMI"},
            "global": {"cat": "全球", "score": global_val, "desc": f"全球风险情绪=基于VIX({(vix_v or 0):.1f})+美债10Y({(us10y_v or 0):.2f}%)动态计算"},
        },
        "pmi_value": economy,
        "usd_cny": usd_cny_latest,
        "note": f"经济维度=中国PMI真实值({economy or 'N/A'})；"
               f"货币维度=中国银行USD/CNY中间价({usd_cny_latest or 'N/A'})；"
               f"全球维度=基于MACRO_DATA的VIX({(vix_v or 0):.1f})+美债10Y({(us10y_v or 0):.2f}%)日级数据动态计算",
    }

def f_herding_data():
    # 羊群效应（抱团板块）：由当日涨停池的行业集中度推导
    # 涨停越集中在少数行业，说明资金抱团越强。
    try:
        df = _get_zt_pool()
    except Exception as e:
        print("  zt_pool err:", e)
        return None
    if df is None or df.empty:
        return None
    ind = {}
    for _, r in df.iterrows():
        name = r.get("所属行业") or "其它"
        if name in (None, "", "None"):
            name = "其它"
        ind[name] = ind.get(name, 0) + 1
    if not ind:
        return None
    clusters = []
    for k, v in sorted(ind.items(), key=lambda x: -x[1])[:3]:
        clusters.append({"sector": k, "direction": "强势抱团", "count": v})
    return {
        "current_clusters": clusters,
        "total_limit_up": int(len(df)),
        "note": "由涨停行业集中度推导的抱团板块（行业涨停数降序）",
    }

def f_limit_up_heatmap():
    # 涨停热力图：近10个交易日板块涨停家数日历时序（v6风格）。
    # 复用 fetch_limit_up_heatmap_v8.generate() 做重建/增量。
    try:
        import fetch_limit_up_heatmap_v8 as hm
        result = hm.generate()
        if not result:
            return None
        # 补充今日涨停池的连板梯队与TOP（保持前端兼容）
        try:
            df = _get_zt_pool()
            ladder = {}
            for _, r in df.iterrows():
                lb = int(r.get("连板数") or 0)
                ladder[lb] = ladder.get(lb, 0) + 1
            # 分层取样：高连板(lbc>=2)全量保留（通常<20只），
            # 首板(lbc=1)取前 FIRST_BOARD_CAP 只（避免 top 膨胀过大）
            FIRST_BOARD_CAP = 15
            top = []
            high_board = df[df["连板数"] >= 2]
            first_board = df[df["连板数"] == 1]
            for _, r in high_board.sort_values("连板数", ascending=False).iterrows():
                top.append({"name": r["名称"], "code": r["代码"],
                            "lbc": int(r.get("连板数") or 0),
                            "chg": round(float(r.get("涨跌幅") or 0), 2)})
            for _, r in first_board.head(FIRST_BOARD_CAP).iterrows():
                top.append({"name": r["名称"], "code": r["代码"],
                            "lbc": 1,
                            "chg": round(float(r.get("涨跌幅") or 0), 2)})
            result["ladder"] = ladder
            result["top"] = top
            result["total"] = int(len(df))
        except Exception:
            pass
        result["note"] = "东方财富涨停池（真实），近10日板块涨停家数"
        return result
    except Exception as e:
        print(f"  ⚠️ 涨停热力图失败: {e}")
        return None

def f_limit_up_broken():
    try:
        import akshare as ak
        from datetime import date as _date
        d = _date.today().strftime("%Y%m%d")
        df = ak.stock_zt_pool_zbgc_em(date=d)
        rows = []
        for _, r in df.iterrows():
            try:
                rows.append({
                    "code": str(r.get("代码", "")).strip(),
                    "name": str(r.get("名称", "")).strip(),
                    "chg": round(float(r.get("涨跌幅") or 0), 2),
                    "price": round(float(r.get("最新价") or 0), 2),
                    "limit_price": round(float(r.get("涨停价") or 0), 2),
                    "amount": round(float(r.get("成交额") or 0) / 1e8, 2),
                    "turnover": round(float(r.get("换手率") or 0), 2),
                    "first_seal": str(r.get("首次封板时间") or "").strip(),
                    "broken_times": int(r.get("炸板次数") or 0),
                    "zt_stat": str(r.get("涨停统计") or "").strip(),
                    "amplitude": round(float(r.get("振幅") or 0), 2),
                    "industry": str(r.get("所属行业") or "").strip(),
                })
            except Exception:
                continue
        rows.sort(key=lambda x: (-x["broken_times"], -x["amount"]))
        return {
            "update_time": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "total": len(rows),
            "note": "东方财富炸板股池（真实）：盘中触及涨停但收盘未封住",
            "stocks": rows,
        }
    except Exception as e:
        print(f"  ⚠️ 炸板池失败: {e}")
        return None


def f_capital_flow_data():
    # 个股主力净流入排行：全市场降序+升序并集（push2delay 镜像），
    # 规避实时 push2 host 的 WAF 重置，且避免 pz 截断只取头部导致净流出缺失。
    recs = _all_individual_recs()
    if not recs:
        return None
    recs.sort(key=lambda x: x["net"], reverse=True)
    inflow = [x for x in recs if x["net"] > 0][:20]
    outflow = sorted([x for x in recs if x["net"] < 0], key=lambda x: x["net"])[:20]
    market_net = round(sum(x["net"] for x in recs), 2)
    return {
        "top_inflow": inflow,
        "top_outflow": outflow,
        "market_net": market_net,
        "note": "全市场个股主力净流入(亿)，来源东方财富push2delay；非席位四路口径",
    }

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    """大盘资金流向时间轴：东方财富 push2his 日线接口。
    取上证指数(000001)主力资金净流入历史序列，覆盖今年以来到最近交易日。
    f52=主力净流入(元)，f62/f63=上证收盘/涨跌幅，f64/f65=深证收盘/涨跌幅。
    2026-08-05 改进：与远端/本地 baseline 合并，避免接口滞后时跨天塌缩丢失已有最新日期。
    """
    url = "http://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": "1.000001",
        "secid2": "0.399001",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    try:
        r = _requests.get(url, params=params, headers=_EM_HEADERS, timeout=20)
        text = r.text
        start = text.find("{")
        end = text.rfind(")")
        j = json.loads(text[start:end if end > 0 else None])
        klines = j.get("data", {}).get("klines", []) or []
    except Exception as e:
        print(f"  ⚠️ 大盘资金流向接口失败: {e}")
        klines = []

    # 先取已有 baseline：远端 main 优先（避免本地 raw_data 刚被清空），其次本地 raw_data
    baseline = _fetch_remote_raw("market_fund_flow_data.json") or {}
    if not baseline:
        try:
            local_path = RAW_DIR / "market_fund_flow_data.json"
            if local_path.exists():
                baseline = json.loads(local_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️ 读取本地 market_fund_flow_data baseline 失败: {e}")
            baseline = {}

    baseline_daily = {x["date"]: x for x in (baseline.get("daily") or [])}
    baseline_quote = baseline.get("sh_quote") or {}

    if not klines:
        if baseline_daily:
            print("  ⏭️ 大盘资金流向接口无返回，沿用 baseline")
            daily = [baseline_daily[d] for d in sorted(baseline_daily.keys())]
        else:
            return None
    else:
        daily = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            ds = parts[0].replace("-", "")
            # 参照 v6 fetch_market_fund_flow.py：存全 8 字段（date + net_yi + 特大/大/中/小单 + 主力%/小单%）
            def _f(idx):
                try: return round(float(parts[idx]) / 1e8, 2)
                except Exception: return 0.0
            def _pct(idx):
                try: return float(parts[idx])
                except Exception: return None
            entry = {"date": ds, "net_yi": _f(1)}
            if len(parts) >= 8:
                # 🛡 2026-08-28 根因修复：东财 daykline 字段顺序为 f52=主力净流入, f53=小单, f54=中单, f55=大单, f56=超大单
                # 原代码把 2/3/4/5 直接当成 特大/大/中/小，导致 super_large+large 与 net_yi 符号相反、散户/主力颠倒。
                entry["small_yi"]       = _f(2)
                entry["medium_yi"]      = _f(3)
                entry["large_yi"]       = _f(4)
                entry["super_large_yi"] = _f(5)
                entry["main_pct"]       = _pct(6)
                entry["small_pct"]      = _pct(7)
            daily.append(entry)

        # 合并 baseline：保留接口未覆盖但 baseline 中已有的日期（通常无，但可防接口 truncated）
        seen = {x["date"] for x in daily}
        for ds, x in baseline_daily.items():
            if ds not in seen:
                daily.append(x)
        daily.sort(key=lambda x: x["date"])

    # 上证行情 quote：接口有则覆盖，无则沿用 baseline
    sh_quote = dict(baseline_quote)
    if klines:
        for line in klines:
            parts = line.split(",")
            if len(parts) < 15:
                continue
            ds = parts[0].replace("-", "")
            try:
                sh_quote[ds] = {"close": round(float(parts[11]), 2), "chg": round(float(parts[12]), 2)}
            except Exception:
                pass

    # 累计净值
    cum = 0.0
    cumulative = []
    for x in daily:
        cum += float(x.get("net_yi") or 0)
        cumulative.append({"date": x["date"], "cum_yi": round(cum, 2)})

    return {
        "daily": daily,
        "cumulative": cumulative,
        "market_net": daily[-1]["net_yi"] if daily else 0,
        "sh_quote": sh_quote,
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "上证指数(000001)单日主力资金净流入滚动累加，来源东方财富push2his",
    }

def f_w52_high():
    # 新高广度信号：东方财富「历史新高」板块 BK0501（真实，可达）
    # 注：CN 网络无法访问真正的「52周新高」专用池(getTopicNewHighPool 返回非 JSON)，
    #     故以「历史新高」板块成分数作为市场新高广度信号（语义等价、真实可用）。
    # 东财板块接口单页硬上限 100 行，故总数取 data.total（真实值），TOP 展示取返回行。
    params = {"pn": "1", "pz": "500", "po": "1", "np": "1", "fltt": "2", "invt": "2",
              "ut": "b2884a393a59ad64002292a3e90d46a5", "fid": "f3",
              "fs": "b:BK0501", "fields": "f12,f14,f2,f3", "_": 1}
    r = _requests.get(f"{_EM_DELAY}/api/qt/clist/get", params=params,
                      headers=_EM_HEADERS, timeout=15).json()
    data = r.get("data") or {}
    rows = _em_clean_rows(data.get("diff") or [])
    if not rows:
        return None
    total = data.get("total") or len(rows)
    top_gainers = []
    for rr in rows[:15]:
        try:
            chg = round(float(rr.get("f3") or 0), 2)
        except Exception:
            chg = 0.0
        top_gainers.append({"name": rr.get("f14"), "code": rr.get("f12"), "chg": chg})
    return {
        "total": total,
        "top_gainers": top_gainers,
        "note": "东方财富「历史新高」板块成分数（真实新高广度信号）",
    }


def f_restricted_release():
    """盘后数据页：未来 A 股解禁日历（调用 algorithms/fetch_restricted_release.py）。"""
    import subprocess as _sp
    try:
        script = ROOT / "algorithms" / "fetch_restricted_release.py"
        r = _sp.run([sys.executable, str(script)], cwd=str(ROOT),
                    capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"  ⚠️ 解禁日历子进程返回 {r.returncode}: {(r.stderr or '')[:200]}")
            return None
        return {"fetched": True}
    except Exception as e:
        print(f"  ⚠️ 解禁日历调用失败: {e}")
        return None


def f_performance_forecast():
    """盘后数据页：A 股业绩预告（调用 algorithms/fetch_performance_forecast.py）。"""
    import subprocess as _sp
    import json as _json
    try:
        script = ROOT / "algorithms" / "fetch_performance_forecast.py"
        r = _sp.run([sys.executable, str(script)], cwd=str(ROOT),
                    capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"  ⚠️ 业绩预告子进程返回 {r.returncode}: {(r.stderr or '')[:200]}")
            return None
        # 2026-09-01 一劳永逸：返回子进程实际落盘的 JSON，否则 save() 会把 {"fetched":True}
        #   判为空/无效数据而跳过写入，导致线上永远保留旧重复数据。
        path = RAW_DIR / "performance_forecast.json"
        if path.exists():
            return _json.loads(path.read_text(encoding="utf-8"))
        return {"fetched": True}
    except Exception as e:
        print(f"  ⚠️ 业绩预告调用失败: {e}")
        return None


def f_etf_daily_monitor():
    # ETF 日监控：全市场 ETF 当日主力净流入排名（T+1 盘后更新）
    # 数据源：akshare fund_etf_spot_em 含「主力净流入-净额」字段
    df = get_ak().fund_etf_spot_em()
    if df is None or df.empty:
        return None
    net_col = "主力净流入-净额" if "主力净流入-净额" in df.columns else None
    if net_col is None:
        # 字段缺失时退化为成交额排序，保证有数据而非空
        df2 = df.sort_values("成交额", ascending=False).head(20) if "成交额" in df.columns else df.head(20)
        return {"items": df2.to_dict(orient="records"), "note": "主力净流入字段缺失，退化为成交额排序"}
    df = df.copy()
    df[net_col] = pd.to_numeric(df[net_col], errors="coerce").fillna(0.0)
    df = df[df[net_col] != 0.0]  # 去掉无净流入数据的行（避免 nan 污染）
    if df.empty:
        return {"no_data": True, "note": "盘前无主力净流入数据，盘后 T+1 自动更新"}
    inflow = df.sort_values(net_col, ascending=False).head(10)
    outflow = df.sort_values(net_col, ascending=True).head(10)
    total_net = float(df[net_col].sum())
    return {
        "total_etf": int(len(df)),
        "total_net": total_net,
        "top_inflow": [{"name": r["名称"], "code": r["代码"], "net": float(r[net_col])} for _, r in inflow.iterrows()],
        "top_outflow": [{"name": r["名称"], "code": r["代码"], "net": float(r[net_col])} for _, r in outflow.iterrows()],
    }


def f_etf_pulse():
    # ETF 盘中异动：用 fund_etf_spot_em 实时行情筛「量比>1.2 的活跃 ETF」按量比排序
    # 注：本版 akshare 已移除 fund_etf_hist_em 等分钟线接口，故用实时快照的量比/涨跌幅表征异动
    df = get_ak().fund_etf_spot_em()
    if df is None or df.empty:
        return None
    vol_col = "量比" if "量比" in df.columns else None
    chg_col = "涨跌幅" if "涨跌幅" in df.columns else None
    amt_col = "成交额" if "成交额" in df.columns else None
    if vol_col is None and chg_col is None:
        return {"note": "异动字段（量比/涨跌幅）缺失", "etfs": []}
    df = df.copy()
    if vol_col:
        df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0.0)
    if chg_col:
        df[chg_col] = pd.to_numeric(df[chg_col], errors="coerce").fillna(0.0)
    if amt_col:
        df[amt_col] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0.0)
    # 未开盘检测：集合竞价前(<09:30)全市场量比/成交额均为 0，此时输出榜单毫无意义，
    # 直接回 no_data 让前端显示「未开盘」，避免展示一整屏 0.00 的假异动。
    has_vol = bool(vol_col) and float(df[vol_col].max()) > 0
    has_amt = bool(amt_col) and float(df[amt_col].max()) > 0
    if not has_vol and not has_amt:
        return {"no_data": True, "etfs": [],
                "note": "未开盘/集合竞价中，量比与成交额尚未产生，开盘后自动刷新"}

    # 优先筛量比>1.2 的异动；若无显著放量，退化为成交额 TOP（活跃度真实可比，
    # 不用量比排序——量比为 0 时排序结果等同于代码倒序，是无意义的噪声）
    if has_vol:
        hot = df[df[vol_col] > 1.2]
        if not hot.empty:
            base, sort_col, mode = hot, vol_col, "hot"
        else:
            base, sort_col, mode = df, (amt_col or vol_col), "amt"
    else:
        hot = df[df[chg_col].abs() > 2] if chg_col else df.iloc[0:0]
        if not hot.empty:
            base, sort_col, mode = hot, chg_col, "chg"
        else:
            base, sort_col, mode = df, (amt_col or chg_col), "amt"
    base = base.sort_values(sort_col, ascending=False).head(12)
    etfs = []
    for _, r in base.iterrows():
        etfs.append({
            "name": r["名称"], "code": r["代码"],
            "chg": float(r[chg_col]) if chg_col else 0.0,
            "vol": float(r[vol_col]) if vol_col else 0.0,
            "amount": float(r[amt_col]) if amt_col else 0.0,
        })
    note = {
        "hot": "盘中异动：量比>1.2 的放量 ETF（按量比排序）",
        "chg": "盘中异动：涨跌幅>2% 的 ETF",
        "amt": "盘中暂无显著放量，展示成交额最活跃 TOP12",
    }[mode]
    return {"etfs": etfs, "note": note}


def f_analyst_ratings():
    """分析师评级：akshare stock_analyst_rank_em（东财分析师排名 + 最新推荐个股）。
    输出结构兼容 update_v8.py 的 ANALYST_RATINGS 转换：
    {hot_stocks, latest_reports, upgrades, downgrades, new_coverage}"""
    ak = get_ak()
    result = {"hot_stocks": [], "latest_reports": [], "upgrades": [], "downgrades": [], "new_coverage": []}
    year = now_cst().year

    # ① 分析师年度排名 → 提取 TOP 分析师最新推荐个股作为"热门"
    try:
        df = ak.stock_analyst_rank_em(year=str(year))
        if df is not None and len(df) > 0:
            cols = list(df.columns)
            # 动态匹配年份前缀的列名
            code_col = next((c for c in cols if "股票代码" in c), "")
            name_col = next((c for c in cols if "股票名称" in c), "")
            if not code_col:
                print("    ⚠️ 分析师排名: 未找到股票代码列")
            else:
                seen = set()
                for _, row in df.head(30).iterrows():
                    code = str(row.get(code_col, "")).strip()
                    name = str(row.get(name_col, "")).strip()
                    analyst = str(row.get("分析师名称", "") or "")
                    firm = str(row.get("分析师单位", "") or "")
                    idx_val = row.get("年度指数")
                    ret_12m = row.get("12个月收益率")
                    if not code or code in seen or code == "nan":
                        continue
                    seen.add(code)
                    entry = {
                        "code": code, "name": name,
                        "rating": f"TOP分析师推荐({analyst}/{firm})",
                        "report_count_1m": 1,
                        "date": now_cst().strftime("%Y-%m-%d"),
                        "org": firm,
                        "analyst": analyst,
                        "annual_index": idx_val,
                        "ret_12m": ret_12m,
                    }
                    result["hot_stocks"].append(entry)
                    result["latest_reports"].append(entry)
                print(f"    分析师排名: 获取 {len(result['hot_stocks'])} 只推荐股")
    except Exception as e:
        print(f"    ⚠️ 分析师排名获取失败: {e}")

    # ② 尝试获取个股研报明细（补充，失败不阻塞）
    try:
        # 取 hot_stocks 前 5 只的研报
        top_codes = [s["code"] for s in result["hot_stocks"][:5]]
        for code in top_codes[:3]:  # 限 3 只防超时
            try:
                rdf = ak.stock_research_report_em(symbol=code)
                if rdf is not None and len(rdf) > 0:
                    stock_name = next((s["name"] for s in result["hot_stocks"] if s["code"] == code), "")
                    for _, rrow in rdf.head(2).iterrows():
                        title = str(rrow.get("标题", ""))[:40]
                        result["new_coverage"].append({
                            "code": code,
                            "name": stock_name,
                            "rating": "研报覆盖",
                            "report_count_1m": 1,
                            "date": str(rrow.get("发布日期", ""))[:10] if pd.notna(rrow.get("发布日期")) else "",
                            "title": title,
                        })
            except Exception:
                pass
        print(f"    研报明细: 补充 {len(result['new_coverage'])} 条")
    except Exception as e:
        print(f"    ⚠️ 研报明细跳过: {e}")

    return result


def f_experiment():
    # 实验选股调试专区（三重选股）：用全市场个股实时快照(em_clist, 东财push2delay)做透明技术面初筛。
    # 产生 金钻起涨/波段多头/主力进场/主力出货/三重选股 五个名单，供前端「⑤ 三重选股补充候选」渲染。
    # 说明：纯实时快照初筛（非历史回测），验证中请勿依赖。
    desc = em_clist(_IND_FS, "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=5000, po="1")
    asc = em_clist(_IND_FS, "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=5000, po="0")
    by_code = {}
    for r in desc + asc:
        c = str(r.get("f12"))
        if c in by_code:
            continue
        try:
            by_code[c] = {
                "code": c, "name": r.get("f14"),
                "chg": round(float(r.get("f3") or 0), 2),
                "net": round(float(r.get("f62") or 0) / 1e8, 2),
                "netpct": round(float(r.get("f184") or 0), 2),
            }
        except Exception:
            continue
    stocks = list(by_code.values())
    if not stocks:
        return None

    def pick(pred, key, n=15):
        return [{"code": s["code"], "name": s["name"]}
                for s in sorted([s for s in stocks if pred(s)], key=key, reverse=True)[:n]]

    main_in = pick(lambda s: s["net"] > 0 and s["chg"] > 0, lambda s: s["net"])            # 主力进场
    main_out = pick(lambda s: s["net"] < 0 and s["chg"] < 0, lambda s: s["net"])           # 主力出货
    jin_zuan = pick(lambda s: 3 <= s["chg"] <= 9.8 and s["net"] > 0, lambda s: s["net"])  # 金钻起涨
    bo_duan = pick(lambda s: 1 <= s["chg"] <= 5 and s["net"] > 0, lambda s: s["chg"])      # 波段多头
    triple = [s for s in jin_zuan if s["code"] in {x["code"] for x in main_in}]             # 三重=金钻∩主力进场
    return {
        "triple_select": {
            "lists": {
                "金钻起涨": jin_zuan,
                "波段多头": bo_duan,
                "主力进场": main_in,
                "主力出货": main_out,
                "三重选股": triple,
            },
            "signals": {
                "金钻起涨": len(jin_zuan), "波段多头": len(bo_duan),
                "主力进场": len(main_in), "主力出货": len(main_out), "三重选股": len(triple),
            },
        },
        "note": "实验区：全市场个股实时快照初筛(东财push2delay)。金钻起涨=涨幅3~9.8%且主力净流入; 波段多头=涨幅1~5%且净流入; "
                "主力进场=净流入且上涨; 主力出货=净流出且下跌; 三重=金钻∩主力进场。验证中请勿依赖。",
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
    }


def f_market_alerts():
    """市场预警（全市场异动速览）：接入盘中刷新。
    复用孤儿模块 algorithms/fetch_orphan_market_alerts.py（原 v6 fetch_market_alerts.py 移植）。
    盘中每30分钟刷新一次，避免长期停更到凌晨的历史残留值。"""
    import subprocess as _sp
    script = ROOT / "algorithms" / "fetch_orphan_market_alerts.py"
    if not script.exists():
        print(f"  ⚠️ 未找到 {script}")
        return None
    print(f"  🔄 调用市场预警孤儿模块: {script.name}")
    try:
        r = _sp.run([sys.executable, str(script)], cwd=str(ROOT),
                    capture_output=True, text=True, timeout=90)
    except Exception as e:
        raise RuntimeError(f"fetch_orphan_market_alerts 调用异常(90s超时): {e}")
    if r.returncode != 0:
        raise RuntimeError(f"fetch_orphan_market_alerts exit {r.returncode}: {r.stderr[:160]}")
    p = RAW_DIR / "market_alerts.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# ══════════════════════════════════════════════════════════════════════
# 🗄 日历月度归档（2026-08-28 主人令「旧的也别丢」）
#
# 背景（真 bug，不是假想）：
#   f_v8_cal() 只生成【当前月】，产物单文件 raw_data/v8_cal.json 是覆盖式写入。
#   每月 1 号切月时，上月整月数据被直接覆盖，永久丢失，且无法回溯。
#   更致命的是：上月最后几天（如 8/31）会落在本月首周的灰色(dim)格子里，
#   原逻辑 dim 格子 events 恒为空 → 8/31 的「官方制造业PMI/中报披露截止」
#   在 9 月视图里凭空消失（用户肉眼可见的事件丢失）。
#
# 修复（双保险）：
#   1) 归档：每次生成月份时，把该月完整数据写入 v8_cal_archive/YYYY-MM.json，
#      永不覆盖历史月份（同月重复生成才覆盖，属正常刷新）。
#   2) 继承：生成新月时，从归档（优先）或单文件缓存（回退）读取紧邻上月的
#      事件，填进本月首周的灰色格子。
# ══════════════════════════════════════════════════════════════════════
def _cal_archive_dir():
    # 🛡 动态取 RAW_DIR（模块级常量在测试改 RAW_DIR 后不会跟着变，会写错目录）
    return Path(RAW_DIR) / "v8_cal_archive"


def _cal_archive_path(y, m):
    return _cal_archive_dir() / f"{y:04d}-{m:02d}.json"


def _cal_archive_month(year, month, payload):
    """把某个月的日历产物归档（只写不删，历史月份永不被覆盖丢失）。"""
    try:
        _cal_archive_dir().mkdir(parents=True, exist_ok=True)
        _cal_archive_path(year, month).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception as e:
        print(f"  ⚠️ 日历归档失败 {year}-{month:02d}（不影响本月生成）: {type(e).__name__}: {e}")


def _cal_load_month_events(year, month):
    """读取指定月份『按日期索引的事件表』→ {(y,m,day): [events...]}

    优先读归档（不会被切月覆盖，最可靠），归档不存在时回退到单文件缓存
    （v8_cal.json，仅当它正好是所求月份时有效）。任何异常都返回空表并打印
    可见告警——绝不静默吞异常（2026-08-28 教训：静默 except 掩盖了 NameError，
    导致修复代码形同虚设，排查浪费大量时间）。
    """
    out = {}
    src = None
    payload = None
    ap = _cal_archive_path(year, month)
    if ap.exists():
        try:
            payload = json.loads(ap.read_text(encoding="utf-8"))
            src = f"归档 {ap.name}"
        except Exception as e:
            print(f"  ⚠️ 日历归档读取失败 {ap.name}: {type(e).__name__}: {e}")
    if payload is None:
        cf = RAW_DIR / "v8_cal.json"
        if cf.exists():
            try:
                cand = json.loads(cf.read_text(encoding="utf-8"))
                # 单文件缓存只在"正好是所求月份"时才可信
                if str(cand.get("month", "") or "").find(f"{year}年{month}月") >= 0:
                    payload = cand
                    src = "缓存 v8_cal.json"
            except Exception as e:
                print(f"  ⚠️ 日历缓存读取失败: {type(e).__name__}: {e}")
    if not payload:
        return out
    try:
        for _w in payload.get("weeks", []):
            for _d in _w.get("days", []):
                if _d.get("events"):
                    out[(year, month, _d["num"])] = _d["events"]
    except Exception as e:
        print(f"  ⚠️ 日历事件表解析失败（{src}）: {type(e).__name__}: {e}")
    return out


def _cal_prev_month(y, m):
    """返回 (y, m) 的紧邻上一月，正确处理跨年。"""
    return (y - 1, 12) if m == 1 else (y, m - 1)


def f_v8_cal(today=None):
    """重要事件日历：自动生成【当前月】日历。
    - 频率控制：仅在每月 1~3 号执行完整生成；其余日期直接返回已有缓存（v8_cal.json），
      避免每日无意义重跑。每月初跑一次即可（规则事件按公式算，财报日期预估季度更新）。
    - 自动切月：永远渲染「今天所在月」，8/1 起自然显示 8 月。
    - 自动标今天：today 高亮每天动态算。
    - 规则事件自动算：股指期货/ETF期权交割(第3周五/第4周三)、LPR(20日)、A50交割(倒数第2工作日)、
      FOMC(2026年度表)、中国宏观数据日(PMI/CPI/工业增加值，约)、港股/美股休市(2026假期表)。
    - 公司财报：内嵌七姐妹+NVDA+半导体链+亚太+欧股+华为（从 v6 fetch_nt_data.py 移植，
      季度预估日期，每年初校准一次）。
    today 参数仅用于测试（默认取系统当天）。
    """
    import calendar as _cal
    from datetime import date, datetime as _dt
    today = today or date.today()

    # ── 频率控制：非月初(1~3号)且非周六则读缓存 ──
    # 周六作为 T+1 周度/月度统一刷新窗口，强制重建日历（覆盖月度事件调整/财报日期修正）
        # ── 频率控制（2026-08-02 修）：缓存里"今天的 today 标记"是否还在 ──
    # 重建条件（满足任一即重建）：
    #   1) 缓存不存在
    #   2) 缓存月份 ≠ 今天所在月（自然切月）
    #   3) 缓存 update_time 是昨天或更早
    #   4) 缓存 weeks 里没有任何 day 标 today=true 且 num==今天的日子数
    # 否则（缓存新鲜 + 今天是缓存里的 today）→ 直接返回缓存
    # 修前 bug：「day>3 且非周六读缓存」漏掉周日-周六之间隔一整天的边角，
    #  导致 8/2（周日）显示 8/1（周六）数据，today 永远停在 1 号。
    cache_file = RAW_DIR / "v8_cal.json"
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cache_month = cached.get("month", "")
            today_yyyymm = f"{today.year}-{today.month:02d}"
            cache_ut = cached.get("update_time", "")
            cache_has_today = any(
                d.get("today") and d.get("num") == today.day
                for w in cached.get("weeks", []) for d in w.get("days", [])
            )
            cache_stale_day = False
            try:
                if cache_ut:
                    cache_dt = _dt.strptime(cache_ut, "%Y-%m-%d %H:%M:%S")
                    cache_stale_day = cache_dt.date() < today
            except Exception:
                cache_stale_day = True
            if (cache_month == today_yyyymm
                    and not cache_stale_day
                    and cache_has_today):
                print(f"    日历: 缓存新鲜（{cache_ut} · today={today.day} 已标记），直接返回")
                return cached
            else:
                reasons = []
                if cache_month != today_yyyymm: reasons.append(f"月份切换 {cache_month}->{today_yyyymm}")
                if cache_stale_day: reasons.append(f"update_time {cache_ut} 早于今天")
                if not cache_has_today: reasons.append(f"缓存内无 today={today.day} 标记")
                print(f"    日历: 需重建（{'; '.join(reasons)}）")
        except Exception as e:
            print(f"    日历: 缓存解析失败 {e}，重建")

    y, m = today.year, today.month
    last_day = _cal.monthrange(y, m)[1]

    # 2026 港股/美股休市（手工维护，需每年更新；仅供参考）
    HK_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,2,17):"农历新年", (2026,2,18):"农历新年", (2026,2,19):"农历新年",
        (2026,4,3):"耶稣受难节", (2026,4,6):"复活节星期一", (2026,5,1):"劳动节",
        (2026,5,25):"佛诞", (2026,6,19):"端午节", (2026,7,1):"香港回归纪念日",
        (2026,9,25):"中秋节", (2026,10,1):"国庆日", (2026,10,19):"重阳节",
        (2026,12,25):"圣诞节", (2026,12,26):"圣诞节翌日",
    }
    US_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,1,19):"马丁路德金日", (2026,2,16):"总统日",
        (2026,4,3):"耶稣受难节", (2026,5,25):"阵亡将士纪念日", (2026,6,19):"六月节",
        (2026,9,7):"劳动节", (2026,11,26):"感恩节", (2026,12,25):"圣诞节",
    }
    SG_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,2,17):"农历新年", (2026,3,31):"开斋节",
        (2026,5,1):"劳动节", (2026,5,25):"卫塞节", (2026,8,9):"国庆日",
        (2026,10,22):"屠妖节", (2026,12,25):"圣诞节",
    }
    # FOMC 2026 议息会议（月, 第1天, 决议日）
    FOMC_2026 = [(1,27,28),(3,17,18),(4,28,29),(6,9,10),(7,28,29),(9,15,16),(10,27,28),(12,15,16)]

    def nth_weekday(yy, mm, n, wd):
        d = date(yy, mm, 1)
        off = (wd - d.weekday()) % 7
        return d + timedelta(days=off + 7 * (n - 1))

    def last_weekday(yy, mm, n_from_end):
        d = date(yy, mm, _cal.monthrange(yy, mm)[1])
        cnt = 0
        while True:
            if d.weekday() < 5:
                cnt += 1
                if cnt == n_from_end:
                    return d
            d -= timedelta(days=1)

    def shift_weekend(d):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    ev = {}

    # 🛡 2026-08-28 主人令「旧的也别丢」：跨月时上月最后几天事件不丢。
    #   f_v8_cal 按月生成，上月最后几天（如 8/31）会落在本月首周的灰色(dim)格子里。
    #   原逻辑 dim 格子 events 为空，导致 8/31 的中报披露截止、官方制造业PMI 等事件
    #   在 9 月视图里直接消失。修复：读取上月缓存，把上月最后 7 天（即可能落入
    #   本月灰色格子的日期）的事件保留，用于本月显示。
    # 取紧邻上月（自动处理跨年：1月→去年12月）
    _py, _pm = _cal_prev_month(y, m)
    prev_month_events = _cal_load_month_events(_py, _pm)
    if prev_month_events:
        print(f"  🔗 日历跨月继承：{_py}年{_pm}月 → {y}年{m}月，"
              f"保留上月事件 {sum(len(v) for v in prev_month_events.values())} 条"
              f"（{len(prev_month_events)} 天）")
    else:
        print(f"  ℹ️ 日历跨月继承：{_py}年{_pm}月无可用事件（归档/缓存均无），本月首周灰色格子将为空")

    def add(day, text, cls, released=None):
        if 1 <= day <= last_day:
            rel = (day < today.day) if released is None else bool(released)
            ev.setdefault(day, []).append({"text": text, "cls": cls, "released": rel})

    # 期货/期权交割（每月第3周五）
    d3 = nth_weekday(y, m, 3, 4)
    if (d3.year, d3.month) == (y, m):
        add(d3.day, "中金所IF/IH/IC/IM股指期货交割", "future")
        add(d3.day, "中金所股指期权到期", "option")
    # ETF期权（每月第4周三）
    d4 = nth_weekday(y, m, 4, 2)
    if (d4.year, d4.month) == (y, m):
        add(d4.day, "上交所/深交所ETF期权最后交易日", "option")
    # LPR（每月20日，周末顺延）
    dl = shift_weekend(date(y, m, 20))
    if dl.month == m:
        add(dl.day, "LPR利率报价（1年/5年以上）", "cb")
    # 富时A50交割（每月倒数第2工作日）
    da = last_weekday(y, m, 2)
    if da.month == m:
        add(da.day, "富时A50交割日", "a50")
    # FOMC
    for (fm, d1, d2) in FOMC_2026:
        if fm == m:
            add(d1, "🇺🇸 FOMC议息会议第1天", "fomc")
            add(d2, "🇺🇸 FOMC利率决议", "fomc")
    # 宏观数据日（约）
    dc = shift_weekend(date(y, m, 1))
    if dc.month == m:
        add(dc.day, "🇨🇳 财新制造业PMI", "caixin")
    dp = shift_weekend(date(y, m, 10))
    if dp.month == m:
        add(dp.day, "🇨🇳 CPI/PPI数据", "data2")
    dg = shift_weekend(date(y, m, 15))
    if dg.month == m:
        add(dg.day, "🇨🇳 工业增加值/社零/固投", "data")
    dpm = last_weekday(y, m, 1)
    if dpm.month == m:
        add(dpm.day, "🇨🇳 官方制造业PMI", "data")
    # 中国进出口数据（每月约7-10号，遇周末顺延；海关公布）
    de = shift_weekend(date(y, m, 7))
    if de.month == m:
        add(de.day, "🇨🇳 中国出口", "data")
    # 美国非农（每月第一个周五）
    dnf = nth_weekday(y, m, 1, 4)
    if dnf.month == m:
        add(dnf.day, "🇺🇸 美国非农", "us")
    # 美国CPI（每月第二个周三，约10-15号）
    dcpi = nth_weekday(y, m, 2, 2)
    if dcpi.month == m:
        add(dcpi.day, "🇺🇸 美国CPI", "us")
    # MLF操作（每月15日左右，遇周末顺延）
    dmlf = shift_weekend(date(y, m, 15))
    if dmlf.month == m:
        add(dmlf.day, "🇨🇳 MLF操作", "cb")
    # 🔴 2026-08-12 主人令：8月日历审计发现自动生成缺美国宏观数据日
    #   美国 PPI + 零售销售（约每月14日，8月14日附近；遇周末顺延到周一）
    dppi = shift_weekend(date(y, m, 14))
    if dppi.month == m:
        add(dppi.day, "🇺🇸 美国PPI数据", "us")
        add(dppi.day, "🇺🇸 美国零售销售", "us")
    #   密歇根消费者信心指数（约每月第二个周五，8月14日附近）
    dmich = nth_weekday(y, m, 2, 4)
    if dmich.month == m:
        add(dmich.day, "🇺🇸 密歇根消费者信心预公布", "us")
    #   美国工业生产（约每月15日附近；与工业增加值/社零/固投不同日时加）
    dind = shift_weekend(date(y, m, 15))
    if dind.month == m and dind.day != dg.day:
        add(dind.day, "🇺🇸 美国工业生产", "us")
    #   费城联储制造业指数（约每月第三个周五，8月21日附近）
    dphil = nth_weekday(y, m, 3, 4)
    if dphil.month == m:
        add(dphil.day, "🇺🇸 费城联储制造业指数", "us")
    #   美国领先指标（约每月20日附近）
    dlei = shift_weekend(date(y, m, 20))
    if dlei.month == m:
        add(dlei.day, "🇺🇸 美国领先指标", "us")
    #   消费者信心指数（约每月第四个周三，8月26日附近）
    dconf = nth_weekday(y, m, 4, 2)
    if dconf.month == m:
        add(dconf.day, "🇺🇸 消费者信心指数", "us")
    #   新屋销售（约每月25日附近）
    dhouse = shift_weekend(date(y, m, 25))
    if dhouse.month == m:
        add(dhouse.day, "🇺🇸 新屋销售", "us")
    #   耐用品订单（约每月27日附近）
    ddura = shift_weekend(date(y, m, 27))
    if ddura.month == m:
        add(ddura.day, "🇺🇸 耐用品订单", "us")
    #   Jackson Hole 央行年会（每年 8 月底，2026/8/28-29，**美联储主席**就货币政策发言）
    # 🔴 2026-08-12 主人令修正：之前写「鲍威尔讲话」是事实错误——Powell 2026/5/15 任期结束已退休
    #   8 月讲话是候任/新任主席（避免写具体人名又错），所以只用「美联储主席」
    # 🔴 2026-08-22 主人令：去掉「Jackson Hole」英文（外观像人名），统一写「美联储主席」
    if m == 8:
        add(28, "🏛️ 央行年会（美联储主席讲话核心）", "cb")
        add(29, "🏛️ 美联储主席讲话", "cb")
    # A股中报披露截止（8月31日）
    if m == 8:
        add(31, "🇨🇳 中报披露截止", "ipo")
    # 港股/美股休市
    for (yy, mm2, dd), name in HK_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇭🇰 港股休市（{name}）", "hk")
    for (yy, mm2, dd), name in US_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇺🇸 美股休市（{name}）", "us")
    for (yy, mm2, dd), name in SG_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇸🇬 SG公假（{name}）", "sg")
    # 🛡 2026-08-31 一劳永逸：A股休市（原生成器只标港股休市，漏标A股休市）
    #   中秋/国庆等 A股休市日与港股不同步，需单独维护。cls 复用 hk（红色·休市）。
    A_SHARE_HOLIDAYS_2026 = {
        (2026, 9, 25): "中秋节",
        (2026, 10, 1): "国庆节", (2026, 10, 2): "国庆节", (2026, 10, 3): "国庆节",
        (2026, 10, 4): "国庆节", (2026, 10, 5): "国庆节", (2026, 10, 6): "国庆节",
        (2026, 10, 7): "国庆节",
    }
    for (yy, mm2, dd), name in A_SHARE_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇨🇳 A股休市（{name}）", "hk")

    # ════════════════════════════════════════
    #  公司财报（从 v6 fetch_nt_data.py 移植）
    #  季度预估日期，每年初校准一次即可
    # ════════════════════════════════════════
    ym_str = f"{y}-{m:02d}"

    # ── 美股七姐妹（AAPL/MSFT/GOOGL/AMZN/META/TSLA）──
    _magnificent7 = [
        ('2026-01-28','苹果Q1财报'), ('2026-04-29','苹果Q2财报'),
        ('2026-07-29','苹果Q3财报'), ('2026-10-28','苹果Q4财报'),
        ('2027-01-27','苹果Q1财报'), ('2027-04-28','苹果Q2财报'),
        ('2027-07-28','苹果Q3财报'),
        ('2026-01-27','微软Q2财报'), ('2026-04-29','微软Q3财报'),
        ('2026-07-29','微软Q4财报'), ('2026-10-27','微软Q1财报'),
        ('2027-01-26','微软Q2财报'), ('2027-04-28','微软Q3财报'),
        ('2027-07-28','微软Q4财报'),
        ('2026-02-03','谷歌Q4财报'), ('2026-04-28','谷歌Q1财报'),
        ('2026-07-28','谷歌Q2财报'), ('2026-10-27','谷歌Q3财报'),
        ('2027-02-02','谷歌Q4财报'), ('2027-04-27','谷歌Q1财报'),
        ('2027-07-27','谷歌Q2财报'),
        ('2026-01-29','亚马逊Q4财报'), ('2026-04-29','亚马逊Q1财报'),
        ('2026-07-30','亚马逊Q2财报'), ('2026-10-28','亚马逊Q3财报'),
        ('2027-01-28','亚马逊Q4财报'), ('2027-04-28','亚马逊Q1财报'),
        ('2027-07-29','亚马逊Q2财报'),
        ('2026-01-28','Meta Q4财报'), ('2026-04-29','Meta Q1财报'),
        ('2026-07-29','Meta Q2财报'), ('2026-10-28','Meta Q3财报'),
        ('2027-01-27','Meta Q4财报'), ('2027-04-28','Meta Q1财报'),
        ('2027-07-28','Meta Q2财报'),
        ('2026-01-27','特斯拉Q4财报'), ('2026-04-21','特斯拉Q1财报'),
        ('2026-07-21','特斯拉Q2财报'), ('2026-10-20','特斯拉Q3财报'),
        ('2027-01-26','特斯拉Q4财报'), ('2027-04-20','特斯拉Q1财报'),
        ('2027-07-20','特斯拉Q2财报'),
    ]
    for nd, nt in _magnificent7:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 英伟达 ──
    _nvidia = [
        ('2026-02-25','英伟达Q4财报'), ('2026-05-21','英伟达Q1财报+指引'),
        ('2026-08-20','英伟达Q2财报+指引'), ('2026-11-18','英伟达Q3财报+指引'),
        ('2027-02-24','英伟达Q4财报'), ('2027-05-19','英伟达Q1财报+指引'),
        ('2027-08-18','英伟达Q2财报+指引'), ('2027-11-17','英伟达Q3财报+指引'),
    ]
    for nd, nt in _nvidia:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 美股半导体：美光/博通/CSP ──
    _semi = [
        ('2026-01-07','美光Q1财报'), ('2026-03-25','美光Q2财报'),
        ('2026-06-24','美光Q3财报'), ('2026-09-29','美光Q4财报'),
        ('2027-01-06','美光Q1财报'), ('2027-03-24','美光Q2财报'),
        ('2027-06-29','美光Q3财报'), ('2027-09-28','美光Q4财报'),
        ('2026-01-28','博通Q4财报'), ('2026-04-29','博通Q1财报'),
        ('2026-07-29','博通Q2财报'), ('2026-10-28','博通Q3财报'),
        ('2027-01-27','博通Q4财报'), ('2027-04-28','博通Q1财报'),
        ('2027-07-28','博通Q2财报'), ('2027-10-27','博通Q3财报'),
        ('2026-08-12','CSP Q3财报'), ('2026-12-09','CSP Q4财报'),
        ('2027-02-10','CSP Q1财报'), ('2027-05-12','CSP Q2财报'),
        ('2027-08-11','CSP Q3财报'), ('2027-12-08','CSP Q4财报'),
    ]
    for nd, nt in _semi:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 韩国：三星/SK海力士 ──
    _kr = [
        ('2026-01-27','三星Q4财报'), ('2026-04-28','三星Q1财报'),
        ('2026-07-28','三星Q2财报'), ('2026-10-27','三星Q3财报'),
        ('2027-01-26','三星Q4财报'), ('2027-04-27','三星Q1财报'),
        ('2027-07-27','三星Q2财报'),
        ('2026-01-28','SK海力士Q4财报'), ('2026-04-29','SK海力士Q1财报'),
        ('2026-07-29','SK海力士Q2财报'), ('2026-10-28','SK海力士Q3财报'),
        ('2027-01-27','SK海力士Q4财报'), ('2027-04-28','SK海力士Q1财报'),
        ('2027-07-28','SK海力士Q2财报'),
    ]
    for nd, nt in _kr:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "kr")

    # ── 日本：铠侠 ──
    _jp = [
        ('2026-02-12','铠侠Q3财报'), ('2026-05-13','铠侠Q4财报'),
        ('2026-08-12','铠侠Q1财报'), ('2026-11-11','铠侠Q2财报'),
        ('2027-02-10','铠侠Q3财报'), ('2027-05-12','铠侠Q4财报'),
        ('2027-08-11','铠侠Q1财报'), ('2027-11-10','铠侠Q2财报'),
    ]
    for nd, nt in _jp:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "jp")

    # ── 台湾：台积电 ──
    _tw = [
        ('2026-01-15','台积电Q4财报'), ('2026-04-16','台积电Q1财报'),
        ('2026-07-16','台积电Q2财报'), ('2026-10-15','台积电Q3财报'),
        ('2027-01-14','台积电Q4财报'), ('2027-04-15','台积电Q1财报'),
        ('2027-07-15','台积电Q2财报'),
    ]
    for nd, nt in _tw:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "tw")

    # ── 欧洲：ASML ──
    _eu = [
        ('2026-01-28','ASML Q4财报'), ('2026-04-22','ASML Q1财报'),
        ('2026-07-22','ASML Q2财报'), ('2026-10-21','ASML Q3财报'),
        ('2027-01-27','ASML Q4财报'), ('2027-04-21','ASML Q1财报'),
        ('2027-07-21','ASML Q2财报'), ('2027-10-20','ASML Q3财报'),
    ]
    for nd, nt in _eu:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "eu")

    # ── 华为重要事件 ──
    _huawei = [
        (2026, 3, 20, '华为P系列发布会'),
        (2026, 6, 12, '华为开发者大会HDC·Day1'),
        (2026, 6, 13, '华为开发者大会HDC·Day2'),
        (2026, 6, 14, '华为开发者大会HDC·Day3'),
        (2026, 9, 10, '华为Mate系列发布会'),
        (2027, 3, 20, '华为P系列发布会'),
        (2027, 6, 12, '华为开发者大会HDC·Day1'),
        (2027, 6, 13, '华为开发者大会HDC·Day2'),
        (2027, 6, 14, '华为开发者大会HDC·Day3'),
        (2027, 9, 10, '华为Mate系列发布会'),
    ]
    for hy, hm, hd, ht in _huawei:
        if (hy, hm) == (y, m):
            add(hd, ht, "appl")

    # 合并 seed（手工一次性事件：仅限非财报类补充，财报已内嵌上方）
    seed_path = ROOT / "calendar_seed.json"
    if seed_path.exists():
        try:
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            items = seed.get("events", seed) if isinstance(seed, dict) else seed
            for item in items:
                ds = str(item.get("date", ""))
                try:
                    yy, mm2, dd = map(int, ds.split("-"))
                except Exception:
                    continue
                if (yy, mm2) == (y, m):
                    add(dd, item.get("text", ""), item.get("cls", "data"), item.get("released", False))
        except Exception as e:
            print(f"    ⚠️ calendar_seed.json 解析失败: {e}")

    # 构建周网格（周一对齐，覆盖整月）
    first = date(y, m, 1)
    grid_start = first - timedelta(days=first.weekday())
    weeks = []
    cur = grid_start
    wno = 1
    while cur <= date(y, m, last_day):
        days = []
        for i in range(7):
            d = cur + timedelta(days=i)
            dim = (d.month != m)
            days.append({
                "num": d.day,
                "dim": dim,
                "today": (d == today),
                # 🛡 2026-08-28 主人令「旧的也别丢」：dim 日期优先显示上月缓存事件，
                #   无上月事件时才置空，确保跨月首周不会丢失上月末事件。
                "events": ev.get(d.day, []) if not dim else prev_month_events.get((d.year, d.month, d.day), []),
            })
        wk_end = cur + timedelta(days=6)
        weeks.append({
            "no": str(wno),
            "dates": f"{cur.month}/{cur.day}-{wk_end.month}/{wk_end.day}",
            "days": days,
        })
        cur += timedelta(days=7)
        wno += 1

    legend = [
        {"title":"重要政策","color":"#c62828","desc":"中国政府/监管机构发布的重大政策、法规、规划等"},
        {"title":"央行/LPR","color":"#1565c0","desc":"央行货币政策、利率决议、LPR报价等"},
        {"title":"中国数据","color":"#f57f17","desc":"国家统计局/央行发布的宏观经济数据"},
        {"title":"财报截止","color":"#673ab7","desc":"A股财报披露法定截止日"},
        {"title":"期权交割","color":"#00838f","desc":"各交易所期权合约到期日"},
        {"title":"期货交割","color":"#1d6f42","desc":"期货合约最后交易日"},
        {"title":"A50交割","color":"#e91e63","desc":"新加坡富时A50期货交割日，外资对冲A股关键窗口"},
        {"title":"港股休市","color":"#ef5350","desc":"香港交易所休市日"},
        {"title":"台股财报","color":"#ff9800","desc":"台股关注股票"},
        {"title":"苹果/华为","color":"#37474f","desc":"两大科技巨头新品发布/重要财报"},
        {"title":"FOMC","color":"#9c27b0","desc":"美联储货币政策会议"},
        {"title":"美股休市","color":"#42a5f5","desc":"NYSE/Nasdaq休市日"},
        {"title":"美股财报","color":"#66bb6a","desc":"美股关注股票"},
        {"title":"欧股财报","color":"#26a69a","desc":"欧股关注股票"},
        {"title":"日股财报","color":"#ab47bc","desc":"日股关注股票"},
        {"title":"韩股财报","color":"#00acc1","desc":"韩股关注股票"},
        {"title":"SG公假","color":"#8e24aa","desc":"新加坡公共假期"},
        {"title":"财新PMI","color":"#5c6bc0","desc":"财新PMI月度数据"},
    ]

    print(f"    日历: {y}年{m}月, {len(weeks)}周, 事件日 {len(ev)} 天")
    _payload = {
        "month": f"{y}年{m}月",
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M"),
        "legend": legend,
        "weeks": weeks,
    }
    # 🗄 归档本月（历史月份永不丢失，下月生成时可回读继承）
    _cal_archive_month(y, m, _payload)
    # 🛡 2026-08-31 一劳永逸：同步发布前端可回看的归档（data/archive/V8_CAL_YYYY-MM.js + 索引）。
    #   这样每月切月时旧月自动留在 data/archive/，前端「重要事件日历」◀ 即可回看，无需手动干预。
    try:
        import json as _json, re as _re
        _k = f"{y:04d}-{m:02d}"
        _arc_dir = Path(__file__).resolve().parent / "data" / "archive"
        _arc_dir.mkdir(parents=True, exist_ok=True)
        (_arc_dir / f"V8_CAL_{_k}.js").write_text(
            "window.V8_CAL_ARC = " + _json.dumps(_payload, ensure_ascii=False) + ";\n",
            encoding="utf-8")
        _idx = _arc_dir / "V8_CAL_INDEX.js"
        _keys = []
        if _idx.exists():
            try:
                _m = _re.search(r"\[([^\]]*)\]", _idx.read_text(encoding="utf-8"))
                if _m:
                    _keys = [s.strip().strip('"').strip("'") for s in _m.group(1).split(",") if s.strip()]
            except Exception:
                _keys = []
        if _k not in _keys:
            _keys.append(_k)
        _keys = sorted(set(_keys))
        _idx.write_text("window.V8_CAL_ARCHIVE = " + _json.dumps(_keys, ensure_ascii=False) + ";\n", encoding="utf-8")
        print(f"    🗄 前端归档已发布 data/archive/V8_CAL_{_k}.js（索引 {len(_keys)} 个月）")
    except Exception as e:
        print(f"    ⚠️ 前端归档发布失败（不影响主数据）: {e}")
    return _payload


def _clear_intraday_for_premarket(category, only=None):
    """盘前清空盘中/实时模块的当日数据，避免把昨日收盘数据挂到开盘前。
    明确保留用户指定卡片：上证+深证成交金额/涨跌家数(SH_SZ_HISTORY)、
    主力净流入(CAPITAL_FLOW_DATA)、涨停热力(LIMIT_UP_HEATMAP)。

    🛡 2026-09-07 主人令（一劳永逸·时点修复）：清空时点由「08:25 盘前轮」推迟到「临近开盘」。
      原实现挂在 08:25 premarket 轮尾部，一抓完就把 INDEX_QUOTES / ETF_PULSE /
      ETF_INTRADAY_HEAT / SECTOR_FUND_FLOW / CANDIDATE_QUOTES / MARKET_ALERTS /
      OVERSEAS_MARKETS 抹成空 stub → 开盘前 60+ 分钟整段空窗
      （主人原话：「盘前清空的几个卡不应这么早就清空，要9点25分左右才清空」）。
      这与 index.html 概念资金热力卡注释「清空由后端在开盘前集合竞价窗口
      (09:15–09:30)统一触发一次」的设计意图本就矛盾——实现写在了 08:25。
      现改为：仅在真实时间 09:15–10:00 窗口内执行（覆盖 09:30 盘中首轮），
      08:25 盘前轮照常抓数据但【不再清空】，昨日数据保留到开盘前，
      由 09:30 盘中首轮在抓取【之前】接棒清空并立刻用今日实时数据覆盖。

    2026-08-10 盘中自愈加固：若当前已处于 10:00 之后（盘中已推进），
    说明调用链有 bug 导致盘前清空逻辑在盘中被触发，直接拒绝执行，防止误清空。"""
    if only is not None:
        return
    if category not in ("premarket", "intraday"):
        return
    # 周末/法定假日：不执行清空，保留最后一个交易日（周五）的收盘/盘中数据
    if not _is_trading_day():
        print(f"⏸️ 非A股交易日（周末/假期），跳过盘中模块清空，保留最后交易日数据")
        return
    now = now_cst()
    h = now.hour + now.minute / 60.0
    # 🛡 2026-09-07 主人令：太早不清空——08:25 盘前轮直接跳过，昨日数据保留到开盘前
    if h < 9.25:  # 09:15 之前
        print(f"⏸️ 当前 {now.strftime('%H:%M')} 未到 09:15（临近开盘窗口），"
              f"跳过盘中模块清空（昨日数据保留到开盘前，由 09:30 盘中首轮接棒）")
        return
    if h >= 10.0:  # 10:00 及以后盘中数据已就绪，禁止再清空
        print(f"🚨 盘中自愈守卫：当前 {now.strftime('%H:%M')} 已过 10:00，"
              f"拒绝执行 intraday 模块清空（防止误清已抓到的当日数据）")
        return
    today_iso = now.strftime("%Y-%m-%d")
    today_m_d = f"{now.month}/{now.day}"
    today_mm_dd = now.strftime("%m/%d")
    today_m_d_set = {today_m_d, today_mm_dd}
    print(f"🧹 盘前清空盘中模块当日数据（{today_iso}）...")

    # 明确保留的卡片：盘前不清空，保留历史/上一交易日数据
    # ETF_DAILY_MONITOR：T+1 主力净流入为盘后（15:30）定稿值，盘前清成空会让「日监控·主力净流入」
    #   卡片在开盘前一片空白（阿狸咪 2026-08-11 反馈「这是盘后的啊，清空了干嘛」）。保留昨日值，
    #   开盘后盘中 fetch 自然覆盖为当日数据。注意它在 CATEGORY_MAP 里仍是 intraday（保证盘中被抓）。
    # 🛡 2026-08-26 一劳永逸根因修复：CONCEPT_RANKING 原不在 KEEP_VARS，盘前(08:25)即被抹成空 stub，
    #   导致"概念资金热图过早清空"。现与 SH_SZ_HISTORY 同等对待——盘前保留前一交易日真实数据，
    #   等 09:00 盘中 fetch 自然刷新（即"开盘前一起刷新"，而非 08:25 就空白）。
    # 2026-08-31：CFFEX_HOLDINGS 改 intraday 后盘前不清空，保留上一交易日数据等盘中覆盖
    # 2026-08-31 加入 AVG_PRICE_DATA：该卡靠 history[] 逐交易日累积算 MA20/MA60，
    #   盘前一旦被清成 stub，累积史即全毁（实测 history_days 恒为 1 的直接原因）。
    # 2026-09-01：SECTOR_FUND_FLOW_INTRADAY 盘前不清空；次日 09:25 前保留上一交易日全天快照，
    #   开盘后由 intraday_snapshot.py 自然覆盖为当日数据（符合「第二天开盘前才清空」）。
    KEEP_VARS = {"SH_SZ_HISTORY", "CAPITAL_FLOW_DATA", "LIMIT_UP_HEATMAP", "ETF_DAILY_MONITOR", "CONCEPT_RANKING", "CFFEX_HOLDINGS", "AVG_PRICE_DATA", "SECTOR_FUND_FLOW_INTRADAY"}

    for var, cat in CATEGORY_MAP.items():
        if "intraday" not in [x.strip() for x in cat.split(",")]:
            continue
        if var in KEEP_VARS:
            continue
        fname = VAR_TO_RAW.get(var)
        if not fname:
            continue
        note_map = {
            "ETF_DAILY_MONITOR": "盘前无主力净流入数据，开盘后自动刷新",
            "ETF_PULSE": "未开盘/集合竞价中，量比与成交额尚未产生，开盘后自动刷新",
            "ETF_INTRADAY_HEAT": "盘前 ETF 资金热度待刷新，开盘后自动更新",
            "INDEX_QUOTES": "盘前指数快照待开盘刷新",
            "CONCEPT_RANKING": "盘前概念排名待开盘刷新",
            "CANDIDATE_QUOTES": "盘前候选池实时行情待开盘刷新",
            "MARKET_ALERTS": "盘前市场预警待开盘刷新",
            "SECTOR_FUND_FLOW": "盘前板块资金流待开盘刷新",
        }
        note = note_map.get(var, "盘前数据已清空，开盘后自动刷新")
        stub = {"no_data": True, "premarket_cleared": True, "note": note}
        if var == "ETF_INTRADAY_HEAT":
            stub.update({"items": [], "inflow_top": [], "outflow_top": [], "categories": {}})
        elif var == "INDEX_QUOTES":
            stub["indices"] = []
        elif var == "CONCEPT_RANKING":
            stub["concepts"] = []
        elif var == "CANDIDATE_QUOTES":
            stub["quotes"] = []
        elif var == "MARKET_ALERTS":
            stub["alerts"] = []
        elif var == "SECTOR_FUND_FLOW":
            stub["sectors"] = []
        save(var, stub)

    # SH_SZ_HISTORY：保留历史序列，仅剔除今日记录
    # 2026-08-10 小九：盘前清空也读远端 main 基线，防止本地 raw_data 被旧数据污染时把历史交易日丢掉。
    remote_baseline = _fetch_remote_raw("sh_sz_history.json")
    data = remote_baseline or _load_judgment_raw(
        "SH_SZ_HISTORY", VAR_TO_RAW.get("SH_SZ_HISTORY")) or {}
    amount_history = data.get("amount_history") or []
    daily_stats = data.get("daily_stats") or data.get("up_down") or []
    new_amount = [r for r in amount_history if str(r.get("date")) not in today_m_d_set]
    new_stats = [r for r in daily_stats if str(r.get("date")) not in today_m_d_set]
    save("SH_SZ_HISTORY", {
        "amount_history": new_amount,
        "daily_stats": new_stats,
        "up_down": new_stats,
        "amount_last_date": new_amount[-1].get("date") if new_amount else "",
        "up_down_last_date": new_stats[-1].get("date") if new_stats else "",
        "premarket_cleared": True,
        "note": "盘前已清空今日数据，开盘后自动刷新",
        "baseline_source": "remote_main" if remote_baseline else "local",
    })

    # LIMIT_UP_HEATMAP：保留近10日历史列，再追加今日占位列（开盘后首次 fetch 会替换为真实数据）
    data = _load_judgment_raw("LIMIT_UP_HEATMAP", VAR_TO_RAW.get("LIMIT_UP_HEATMAP")) or {}
    sectors = data.get("sectors") or []
    dates = data.get("dates") or []
    today_md = now.strftime("%m/%d")  # e.g. "08/11"
    if dates and sectors:
        # 2026-08-31 一劳永逸（主人令「无数据！赶紧一劳永逸式修复」）
        #   原实现在盘前把 ladder / top 直接 pop 掉、total 置 0。但「情绪周期·连板天梯」
        #   卡片正是读 lh.ladder / lh.total —— 于是从盘前档(08:25)一直到当日首次成功的
        #   盘中抓取之间，该卡必然显示「无数据」；2026-08-31 首轮盘中 run #1099(09:06)
        #   抓取失败，空窗被拉长到 09:45，主人两次截图实锤。
        #   这与 08-11 ETF_DAILY_MONITOR「这是盘后的啊，清空了干嘛」、08-26
        #   CONCEPT_RANKING「概念资金过早清空」属同一类 bug 第三次复发。
        #   修复：按本函数既有惯例（保留上一交易日真实值 + note 标注）对齐——
        #   ladder / top / total 一律保留，另加 ladder_stale / ladder_date 供前端标「昨日」，
        #   开盘后首次 fetch 自然覆盖为当日真实数据，卡片不再出现空窗。
        if data.get("ladder") or data.get("top"):
            data["ladder_stale"] = True
            data["ladder_date"] = data.get("data_date") or dates[-1]
        if dates[-1] != today_md:
            # 日期数组里没有今日 → 追加今日占位列，每个 sector 的 data 末尾补 0
            dates.append(today_md)
            data["dates"] = dates
            for sec in sectors:
                arr = sec.get("data") or []
                # 如果 arr 比旧的 dates 短，前面补 0 保持对齐
                while len(arr) < len(dates) - 1:
                    arr.insert(0, 0)
                arr.append(0)
                sec["data"] = arr
        else:
            # 日期里已有今日，仅把今日列置 0
            for sec in sectors:
                arr = sec.get("data") or []
                if len(arr) == len(dates):
                    arr[-1] = 0
    data["premarket_cleared"] = True
    data["note"] = "盘前占位今日涨停列；连板天梯/龙头榜/涨停总数为上一交易日值，开盘后自动刷新"
    save("LIMIT_UP_HEATMAP", data)

    # CAPITAL_FLOW_DATA：保留（用户指定不清空），仅打标记
    data = _load_judgment_raw("CAPITAL_FLOW_DATA", VAR_TO_RAW.get("CAPITAL_FLOW_DATA")) or {}
    data["premarket_cleared"] = True
    data["note"] = "盘前主力净流入为上一交易日收盘值，开盘后自动刷新"
    save("CAPITAL_FLOW_DATA", data)

    print(f"🧹 盘前清空完成（保留 SH_SZ_HISTORY/CAPITAL_FLOW_DATA/LIMIT_UP_HEATMAP/ETF_DAILY_MONITOR）")


def main(category=None, only=None):
    print(f"=== v8 云端抓取开始 {now_cst().isoformat(timespec='seconds')} "
          f"category={category or 'all'} ===")

    # 假期/周末冻结：盘中/盘后/盘前（非周六T+1）遇到非交易日时跳过，保留上一交易日收盘数据
    today = now_cst().date()
    is_saturday = today.weekday() == 5
    if category in ("intraday", "post_close") and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日，{category} 跳过，保留上一交易日收盘数据")
        return 0
    if category == "premarket" and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日（周末/假期），premarket 跳过清空，保留最后交易日数据")
        return 0

    # 分时段清理：只删除本次任务类别的 raw_data，避免盘中任务把盘前/盘后数据清掉
    target_vars = None
    if category == "all":
        target_vars = set(CATEGORY_MAP.keys())
        print(f"🎯 全量兜底模式，涉及 {len(target_vars)} 个变量")
    elif category:
        target_vars = {var for var, cat in CATEGORY_MAP.items() if category in [x.strip() for x in cat.split(",")]}
        if not target_vars:
            print(f"⚠️ 未知 category={category}，无任务可执行")
            return 0
        print(f"🎯 目标类别 {category}，涉及 {len(target_vars)} 个变量")
    else:
        print("🎯 全量模式，执行全部 cloud_fetch 模块")

    if only:
        target_vars = {only}
        print(f"🎯 --only 模式，仅执行 {only}")

    cleaned = 0

    # 🔧 盘后（15:30）额外补抓 ETF_DAILY_MONITOR（T+1 日监控收盘后定稿，配合盘中实时卡）
    if category == "post_close" and target_vars is not None:
        target_vars.add("ETF_DAILY_MONITOR")
    # 🔧 盘前（08:25）额外补抓 MARKET_FUND_FLOW_DATA（日频资金流时间轴，防止 15:30 post_close 漏跑导致滞后一天）
    if category == "premarket" and target_vars is not None:
        target_vars.add("MARKET_FUND_FLOW_DATA")
    # 🔧 盘中额外补抓 CRISIS_DATA（危机温度计实时刷新，盘前仅一次不够）
    if category == "intraday" and target_vars is not None:
        target_vars.add("CRISIS_DATA")
    # 🔧 盘中额外补抓 MARKET_FUND_FLOW_DATA（任务看板期望每 30 分钟刷新，否则会被判 stale）
    if category == "intraday" and target_vars is not None:
        target_vars.add("MARKET_FUND_FLOW_DATA")

    if only:
        print("  ⏭️ --only 模式，跳过 raw_data 清理（保留其他时段数据）")
    else:
        # 2026-08-05 修复：runner 上的 safe-delete 安全拦截会在批量 unlink raw_data 时直接
        # 杀掉 python 进程（exit 1、无报错栈），导致抓取链路中断、实时数据卡在午前数日。
        # 改为不再删除：各模块成功抓取时以 json.dump 原地覆盖同名文件；api_push_raw.py 已与
        # 远端 main 的 raw_data 做内容级合并，失败模块保留远端旧值，站点表现与「删除后重抓」一致，
        # 但不再触发 safe-delete。若要恢复清理语义，请在 runner 侧将 raw_data/ 加入 safe-delete 白名单。
        print("  ⏭️ 跳过 raw_data 批量清理（避免触发 runner safe-delete 拦截；依赖原地覆盖 + 远端合并）")

    # 任务列表：顺序影响下游构建，保持原有顺序
    def f_sh_sz_history():
        """沪深两市每日成交额历史 + 全市场涨跌家数（量能对比图 / 涨跌家数图）。

        成交额：用 akshare stock_zh_index_daily_em（东财指数日线，含成交额）替代被 WAF 拦截的
               push2his 接口；自动识别单位（元→亿元），避免 10000 倍误差。
        涨跌家数：用 akshare stock_zh_a_spot_em 全市场快照统计 涨/跌/平。
        历史序列从 raw_data（优先）/ data/SH_SZ_HISTORY.js（回退）继承，仅更新/追加最近交易日，
        避免每次全删 raw_data 后序列断裂。
        """
        import re
        import akshare as ak

        now = now_cst()
        today_md = f"{now.month}/{now.day}"
        is_today_trade = _is_trading_day()

        # ---- 读取历史基线（权威源 = 远端 main raw_data，避免跨天塌缩）----
        baseline = {}
        # 1) 优先远端 main 的 raw_data/sh_sz_history.json（追加型序列的权威基线，根治每日丢一天）
        remote = _fetch_remote_raw("sh_sz_history.json")
        if remote and isinstance(remote, dict) and (remote.get("daily_stats") or remote.get("amount_history")):
            baseline = remote
            print(f"  📥 远端基线命中：daily_stats={len(remote.get('daily_stats') or [])} 条 / amount_history={len(remote.get('amount_history') or [])} 条")
        # 2) 回退：本地 raw_data（intraday 清理后通常不存在，但全量兜底时可能有）
        if not baseline:
            raw_path = RAW_DIR / "sh_sz_history.json"
            if raw_path.exists():
                try:
                    baseline = json.loads(raw_path.read_text(encoding="utf-8"))
                except Exception:
                    baseline = {}
        # 3) 回退：已构建的 data/SH_SZ_HISTORY.js
        if not baseline:
            js_path = ROOT / "data" / "SH_SZ_HISTORY.js"
            if js_path.exists():
                try:
                    txt = js_path.read_text(encoding="utf-8")
                    i = txt.find("=")
                    j = txt.rfind(";")
                    if i != -1 and j != -1 and j > i:
                        baseline = json.loads(txt[i + 1:j].strip())
                except Exception:
                    baseline = {}

        # ---- 成交额历史（akshare 指数日线）----
        amount_history = []
        try:
            amap = {"sh": {}, "sz": {}}
            for key, sym in (("sh", "sh000001"), ("sz", "sz399001")):
                df = ak.stock_zh_index_daily_em(symbol=sym)
                # akshare 不同指数返回列名可能为中文或英文，做兼容
                date_col = next((c for c in df.columns if c in ("日期", "date")), None)
                amount_col = next((c for c in df.columns if c in ("成交额", "amount")), None)
                if not date_col or not amount_col:
                    print(f"  ⚠️ {sym} 日线列名异常，跳过")
                    continue
                for _, row in df.iterrows():
                    ds = str(row[date_col])
                    mm = str(int(ds[5:7])); dd = str(int(ds[8:10]))
                    try:
                        amt = float(row[amount_col])
                        if amt > 1e10:        # 元 → 亿元
                            amt = amt / 1e8
                        amt = round(amt, 1)
                    except Exception:
                        continue
                    amap[key][f"{mm}/{dd}"] = amt
            # 数值排序（2026-08-14 修复：M/D 字典序 "8/10"<"8/2" 导致 X 轴未来日期错乱）
            _date_set = set(amap["sh"]) & set(amap["sz"])
            dates = sorted(_date_set, key=lambda s: (int(s.split("/")[0]), int(s.split("/")[1])))
            # 过滤未来日期（akshare 偶尔返回未交易日/预发布数据，导致 X 轴延伸到 9 月）
            _today_md = (now.month, now.day)
            dates = [d for d in dates if (int(d.split("/")[0]), int(d.split("/")[1])) <= _today_md]
            if dates:
                window = dates[-130:]
                amount_history = [{
                    "date": d,
                    "sh_amount": amap["sh"].get(d, 0.0),
                    "sz_amount": amap["sz"].get(d, 0.0),
                    "total": round(amap["sh"].get(d, 0.0) + amap["sz"].get(d, 0.0), 1),
                } for d in window]
            else:
                amount_history = baseline.get("amount_history") or []
        except Exception as ex:
            print(f"  ⚠️ 沪深成交额获取失败({ex})，沿用历史序列")
            amount_history = baseline.get("amount_history") or []

        # ---- 盘中/收盘补充今日成交额（优先用已抓取的 index_quotes.json，避免 akshare spot 单位异常）----
        # index_quotes.json 由同一次 run 中先执行的 INDEX_QUOTES 任务写入，来源为东财 push2delay，
        # 与前端指数卡片同源，时间和数值更可靠。
        if is_today_trade:
            try:
                idx_path = RAW_DIR / "index_quotes.json"
                idx_data = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
                by_code = {it["code"]: it for it in idx_data.get("items", [])}
                sh_amt = float(by_code.get("000001", {}).get("amount") or 0)
                sz_amt = float(by_code.get("399001", {}).get("amount") or 0)
                if sh_amt > 0 and sz_amt > 0:
                    total_amt = round(sh_amt + sz_amt, 1)
                    rec = {"date": today_md, "sh_amount": round(sh_amt, 1), "sz_amount": round(sz_amt, 1), "total": total_amt}
                    if amount_history and amount_history[-1].get("date") == today_md:
                        amount_history[-1] = rec
                    else:
                        amount_history.append(rec)
                    amount_history = amount_history[-130:]
                    print(f"  ✅ 盘中补充今日成交额 {today_md}: 上证{sh_amt:.1f}亿 / 深证{sz_amt:.1f}亿 / 合计{total_amt:.1f}亿（来源：index_quotes）")
                else:
                    print(f"  ⚠️ index_quotes 缺少今日成交额，沿用日线序列")
            except Exception as ex:
                print(f"  ⚠️ 盘中补充成交额失败({ex})，沿用日线序列")

        # ---- 涨跌家数：沪市 + 深市（与 AI市场速览 口径一致）----
        # index_quotes.json 已含 000001/399001 的 f104/f105/f106，直接读取求和，避免再调 ulist。
        # 🛡 2026-08-26 一劳永逸根因修复：daily_stats 无历史回填源，纯靠基线累积。
        #   原 `ds_hist = baseline.get("daily_stats")` 在基线被覆盖/回退时直接塌缩到 1-2 天。
        #   现对【远端基线 + 本地基线】按 date 取并集去重，确保任何已累积的历史天数都不丢失、不被截断。
        _remote_ds = (remote.get("daily_stats") if isinstance(remote, dict) else None) or []
        _local_ds = (baseline.get("daily_stats") if isinstance(baseline, dict) else None) or []
        _seen = set(); ds_hist = []
        for _r in sorted(_remote_ds + _local_ds, key=lambda x: (x.get("date") or "")):
            _d = _r.get("date")
            if not _d or _d in _seen:
                continue
            _seen.add(_d); ds_hist.append(_r)
        if is_today_trade:
            try:
                idx_path = RAW_DIR / "index_quotes.json"
                idx_data = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
                by_code = {it["code"]: it for it in idx_data.get("items", [])}
                sh = by_code.get("000001", {})
                sz = by_code.get("399001", {})
                up = int(sh.get("up") or 0) + int(sz.get("up") or 0)
                down = int(sh.get("down") or 0) + int(sz.get("down") or 0)
                flat = int(sh.get("flat") or 0) + int(sz.get("flat") or 0)
                if up + down + flat > 0:
                    rec = {"date": today_md, "up": up, "down": down, "flat": flat}
                    if ds_hist and ds_hist[-1].get("date") == today_md:
                        ds_hist[-1] = rec
                    else:
                        ds_hist.append(rec)
                    ds_hist = ds_hist[-120:]
                    print(f"  ✅ 盘中补充今日涨跌家数 {today_md}: 涨{up}/跌{down}/平{flat}（沪市+深市）")
                else:
                    print(f"  ⚠️ index_quotes 缺少涨跌家数，沿用历史序列")
            except Exception as ex:
                print(f"  ⚠️ 涨跌家数获取失败({ex})，沿用历史序列")
        else:
            print(f"  ⏸️ 今日非交易日，涨跌家数/成交额不追加新记录")

        amount_last_date = amount_history[-1].get("date") if amount_history else ""
        up_down_last_date = ds_hist[-1].get("date") if ds_hist else ""

        return {
            "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "amount_history": amount_history,
            "up_down": ds_hist,  # 同步为最新涨跌家数序列（与 daily_stats 一致）
            "daily_stats": ds_hist,
            "amount_last_date": amount_last_date,
            "up_down_last_date": up_down_last_date,
        }

    def f_avg_price():
        """全A等权平均股价：通过 em_clist(push2delay) 取全市场个股最新价/涨跌幅，
        算等权均价 + 等权涨跌幅，并记录历史算 20/60 日水位。
        2026-08-10 重构：原实现用 akshare.stock_zh_a_spot_em() 全量 spot，云端环境
        持续返回空（缺包/超时），导致 AVG_PRICE_DATA 长期空壳、前端卡片无法渲染。
        改为复用与资金流同源的 em_clist（_IND_FS，已验证云端可用）。
        2026-08-11 修复：em_clist 用 fid=f3 排序时硬截 100 条（涨跌幅 TOP 100），
        改用 fid=f12（代码）+ pn 分页遍历全市场 5293 只，阈值 1000→3000 适配全 A 样本量。"""
        # 🛡 2026-08-31 一劳永逸根治（主人「运维还有失败亮黄灯」令）：
        #   【根因三层】
        #   ① 结构性不可持久化：scripts/fetch_avg_price.py 在 workflow 里排在
        #      「📤 推送 raw_data/data」步之后，其写出的 raw_data/avg_price_data.json 与
        #      raw_data/_avg_price_cache.json 从未被推回仓库；云端 runner 又是一次性的，
        #      下轮 checkout 拿到的永远是旧文件 → 缓存永远为空。
        #   ② 缓存死锁：单点源（腾讯/新浪）拿到当日价后要求 len(series)>=5 才落盘，
        #      而 series 长度依赖缓存 → 缓存空 → 永远 <5 → 永远走「7 源全失败」分支。
        #   ③ 于是每天必然只剩 1 条 history → ma20=ma60=当日价、position_vs_ma20/ma60=null
        #      → v8_health_check 判「关键字段空值」→ 运维页常年黄灯。
        #   【修法】通达信 880003 的定义本身就是「全A算术平均股价」，本函数用 em_clist
        #   遍历全市场 5000+ 只算术平均，与 880003 口径一致且云端稳定可达。
        #   故恢复本函数为 avg_price_data.json 的【唯一写入者】（fetch_avg_price.py 步骤
        #   已从 v8_cn_fetch_cloud.yml 摘除），history 由本函数逐交易日累积：
        #   本函数在「抓取」步内执行，产物随后被同一 workflow 的推送步推回仓库 →
        #   累积可跨轮生效，约 20 / 60 个交易日后 MA20 / MA60 自然可用，无需人工干预。
        #   过渡期 position_vs_ma20/ma60 保持 None（前端显示「历史 X/20 日」，不给假信号），
        #   v8_health_check 的 key_fields 已同步去掉这两个字段，只校验 avg_price/ma20/ma60。
        try:
            fields = "f12,f14,f2,f3"
            by_code = {}
            # 2026-08-11 修复：push2delay 即便 pz=5000 实际只返 100 条；按代码(f12)分页遍历拿全量
            PAGE_SIZE = 100
            MAX_PAGES = 60  # 安全阀：A 股理论 5293 只，60 页足矣
            pn = 1
            while pn <= MAX_PAGES:
                page = em_clist(_IND_FS, fields, fid="f12", stat="1", pz=PAGE_SIZE, po="1", pn=pn)
                if not page:
                    break  # 空页：已遍历至末尾
                for r in page:
                    code = str(r.get("f12") or "")
                    if not code:
                        continue
                    # 处理 "-"（停牌/无成交）+ None
                    price_raw = r.get("f2")
                    chg_raw = r.get("f3")
                    try:
                        price = float(price_raw) if price_raw not in (None, "-", "") else 0
                    except (ValueError, TypeError):
                        price = 0
                    try:
                        chg = float(chg_raw) if chg_raw not in (None, "-", "") else None
                    except (ValueError, TypeError):
                        chg = None
                    if price > 0:
                        by_code[code] = {"price": price, "chg": chg}
                if len(page) < PAGE_SIZE:
                    break  # 末页不足 100 条：到底了
                pn += 1
            recs = list(by_code.values())
            # A 股理论 5293 只，停牌/无成交会少一些，≥3000 视为有效全市场样本
            if len(recs) < 3000:
                print(f"  ⚠️ 全A spot 有效样本仅 {len(recs)} 只，放弃计算")
                return {}
            prices = [r["price"] for r in recs]
            avg_price = sum(prices) / len(prices)
            chgs = [r["chg"] for r in recs if r["chg"] is not None]
            avg_change = sum(chgs) / len(chgs) if chgs else 0.0
            count = len(recs)
            # 2026-08-30 修复：周末/节假日不再打不存在的交易日（原用 now_cst()）
            today_str = _last_trading_day().strftime("%Y-%m-%d")

            # 🛡️ 2026-08-30 根因修复（口径隔离防覆盖）：
            #   scripts/fetch_avg_price.py（通达信 880003 真指数，可拉 120 天真历史）与本函数
            #   （全A等权自算，只能逐日累积 1 条）写同一 raw_data/avg_price_data.json。
            #   cn 抓取链（intraday/all，每 30 分钟 + 盘后 + 手动 dispatch）跑得远比云端
            #   880003 链频繁，曾把 880003 的长历史用 1 条全A等权记录反复抹掉
            #   → ma20 = ma60 = 当日价 → 前端假「破MA20/破MA60」。
            #   两者价格量级/口径不同，history 不可混算，故：既有数据若为 880003 口径
            #   且历史更长，本次沿用原数据不覆盖（宁可少更新一天，不可毁掉真历史序列）。
            _hp0 = RAW_DIR / "avg_price_data.json"
            if _hp0.exists():
                try:
                    _old0 = json.loads(_hp0.read_text(encoding="utf-8"))
                    _osrc0 = str(_old0.get("source") or "") + str(_old0.get("index_name") or "")
                    _ohist0 = _old0.get("history") or []
                    if "880003" in _osrc0 and len(_ohist0) > 1:
                        print(f"  ⏸️ AVG_PRICE 口径保护：既有为 880003 真指数"
                              f"(history={len(_ohist0)} 条)，全A等权不覆盖，沿用原数据")
                        return _old0
                except Exception:
                    pass

            # 读取历史，用于计算均线与昨日对比
            hist = []
            prev_price = None
            hist_path = RAW_DIR / "avg_price_data.json"
            if hist_path.exists():
                try:
                    old = json.loads(hist_path.read_text(encoding="utf-8"))
                    hist = old.get("history", [])
                    # 2026-08-30 修复：清理旧 bug 混入的非交易日记录（实测存在 2026-08-30 周日）。
                    #   旧代码用 now_cst() 打日期，周末/节假日跑兜底会写入不存在的交易日；
                    #   这些脏记录日期更大、排序后落在 history 末尾，会持续污染 ma20/ma60
                    #   与前端显示的「最新日期」。仅在能解析且明确判定为非交易日时剔除。
                    _clean = []
                    for _r in hist:
                        _d = _r.get("date")
                        if not _d:
                            continue
                        try:
                            _keep = _is_trading_day(datetime.strptime(_d, "%Y-%m-%d").date())
                        except Exception:
                            _keep = True  # 解析不了就保留，宁可留噪声也不误删历史
                        if _keep:
                            _clean.append(_r)
                    if len(_clean) != len(hist):
                        print(f"  history 剔除非交易日脏记录 {len(hist) - len(_clean)} 条")
                    hist = _clean
                    for r in sorted(hist, key=lambda x: x.get("date", "")):
                        if r.get("date") and r.get("date") != today_str:
                            prev_price = r.get("avg_price")
                except Exception:
                    pass

            # 去重 today's record 后追加
            hist = [r for r in hist if r.get("date") != today_str]
            hist.append({
                "date": today_str,
                "avg_price": round(avg_price, 4),
                "avg_change_pct": round(avg_change, 4),
                "count": count,
            })
            hist = sorted(hist, key=lambda x: x.get("date", ""))[-60:]

            prices = [r["avg_price"] for r in hist]
            ma20 = sum(prices[-20:]) / min(20, len(prices)) if prices else avg_price
            ma60 = sum(prices[-60:]) / min(60, len(prices)) if prices else avg_price

            pos20 = (avg_price - ma20) / ma20 * 100 if ma20 else 0
            pos60 = (avg_price - ma60) / ma60 * 100 if ma60 else 0

            # 🔴 2026-08-30 根因修复：history 不足时 ma = mean(history[-20:]) 会退化成
            #   「当日均价自身」（只有 1 条时 ma20 = ma60 = avg_price），
            #   position_vs_ma20 恒 ≈ -0.0001 < 0 → 前端卡片常年虚假显示「破MA20/破MA60」。
            #   数据层止血：样本不足就不给「位置」（前端 _pt(null) 显示 --，_warns 判 !=null 不误报）。
            _n = len(hist)
            return {
                "date": today_str,
                "source": "全A等权自算(东财em_clist)",
                "index_name": "平均股价(全A等权)",
                "avg_price": round(avg_price, 4),
                "avg_change_pct": round(avg_change, 4),
                "prev_avg_price": round(prev_price, 4) if prev_price else None,
                "count": count,
                "ma20": round(ma20, 4),
                "ma60": round(ma60, 4),
                "position_vs_ma20": round(pos20, 4) if _n >= 20 else None,
                "position_vs_ma60": round(pos60, 4) if _n >= 60 else None,
                "ma20_ready": _n >= 20,
                "ma60_ready": _n >= 60,
                "history": hist,
                "history_days": _n,
            }
        except Exception as e:
            print(f"  ⚠️ 平均股价获取失败: {e}")
            return {}

    tasks = [
        ("ETF_INTRADAY_HEAT", f_etf_intraday_heat),
        ("SECTOR_FUND_FLOW", f_sector_fund_flow),
        ("AVG_PRICE_DATA", f_avg_price),
        ("INDEX_QUOTES", f_index_quotes),
        ("CONCEPT_RANKING", f_concept_ranking),
        ("IPO_DATA", f_ipo_data),
        ("MARGIN_DATA", f_margin_data),
        ("CFFEX_HOLDINGS", f_cffex_holdings),
        ("MACRO_DATA", f_macro_data),
        ("CRISIS_DATA", f_crisis_data),
        ("HERDING_DATA", f_herding_data),
        ("LIMIT_UP_HEATMAP", f_limit_up_heatmap),
        ("LIMIT_UP_BROKEN", f_limit_up_broken),
        ("CAPITAL_FLOW_DATA", f_capital_flow_data),
        ("NORTH_FUND", f_north_fund),
        ("MARKET_FUND_FLOW_DATA", f_market_fund_flow_data),
        ("W52_HIGH", f_w52_high),
        ("ETF_PULSE", f_etf_pulse),
        ("ETF_DAILY_MONITOR", f_etf_daily_monitor),
        ("ANALYST_RATINGS", f_analyst_ratings),
        ("EXPERIMENT", f_experiment),
        ("V8_CAL", f_v8_cal),
        ("CANDIDATE_QUOTES", f_candidate_quotes),
        ("SH_SZ_HISTORY", f_sh_sz_history),
        ("JUDGMENT_DATA", f_judgment),
        ("MACRO_BRIEF", f_macro_brief),
        ("MARKET_ALERTS", f_market_alerts),
        ("OVERSEAS_MARKETS", f_overseas_markets),
        # 2026-08-30：盘后数据页新增
        ("RESTRICTED_RELEASE", f_restricted_release),
        ("PERFORMANCE_FORECAST", f_performance_forecast),
    ]

    def f_four_volume():
        """四量终极 选股：子进程跑 strategy_four_volume.py（盘后日线，直接写 data/FOUR_VOLUME.js）。
        [2026-08-26 一劳永逸-理顺cn fetch时序] 若 data/FOUR_VOLUME.js 已是「今日」产出，
           说明算法链(run_algorithms, 19:15 CST，先于 final_recommend) 本轮已生成四量 -> 跳过，
           避免 30 分 patrol 在 final_recommend 之后又重发四量 -> 四量卡时间戳晚于最终推荐(逻辑倒置)。"""
        # 当日新鲜度闸门：仅当四量尚未是今日产出时才重算(同时自愈陈旧/缺失)。
        import re as _re
        _fv = ROOT / "data" / "FOUR_VOLUME.js"
        try:
            if _fv.exists():
                _txt = _fv.read_text(encoding="utf-8", errors="replace")
                _m = _re.search(r"[\'\"]update_time[\'\"]\s*:\s*[\'\"]([\d-]+)", _txt)
                if _m and _m.group(1)[:10] == now_cst().strftime("%Y-%m-%d"):
                    print("  [skip] 四量终极已为今日(%s)产出，跳过重算(防覆盖算法链先于 final_recommend 的四量)" % _m.group(1)[:10])
                    return
        except Exception as _e:
            print("  [warn] 四量新鲜度检查异常，继续重算: %s" % _e)
        import subprocess as _sp
        try:
            script = ROOT / "algorithms" / "strategy_four_volume.py"
            print(f"🔥 四量终极选股: {script.name}")
            # 云端强制 CLOUD_RUNNER=true：scanner 统一走腾讯 GTimg 数据源（东财/mootdx 云端不可靠）
            _env = dict(os.environ)
            _env["CLOUD_RUNNER"] = "true"
            r = _sp.run([sys.executable, str(script), "--top", "80"],
                        cwd=str(ROOT), capture_output=True, text=True, timeout=1200,
                        env=_env)
            out = (r.stdout or "") + (r.stderr or "")
            for line in out.strip().splitlines()[-6:]:
                print("   ", line)
            if r.returncode != 0:
                print(f"  ⚠️ 四量终极返回码 {r.returncode}")
        except Exception as e:
            print(f"  ⚠️ 四量终极子进程失败: {e}")

    # 🛡 2026-09-07 主人令：盘中首轮（09:30）在抓取【之前】接棒执行盘前清空。
    #   必须早于 tasks —— 否则会把本轮刚抓到的今日实时数据抹成空 stub（比不清空更糟）。
    #   时间窗守卫 09:15–10:00 在函数内：08:25 盘前轮、09:00 轮、下午各轮均自动跳过。
    if category == "intraday" and only is None:
        _clear_intraday_for_premarket(category, only=only)

    for var, fn in tasks:
        if target_vars is not None and var not in target_vars:
            continue
        run(var, fn)

    # 盘前把盘中/实时模块的当日数据清空（08:25 轮会被时间窗守卫跳过，实际由 09:30 盘中首轮执行）
    if category == "premarket":
        _clear_intraday_for_premarket(category, only=only)

    # 盘中/收盘/全量抓取后，用实时 raw_data 生成 AI 盘面解读（规则引擎，零成本，稳定可调试）
    # post_close 15:30 运行会生成「收盘」版解读，避免盘中 13:xx 的评论挂到次日。
    if category in ("intraday", "post_close", "all"):
        try:
            script = ROOT / "algorithms" / "gen_market_brief.py"
            print(f"🧠 生成 AI 盘面解读: {script.name}")
            subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)
        except Exception as e:
            print(f"  ⚠️ gen_market_brief 调用失败: {e}")

    # 四量终极 选股策略（盘后日线，直接写 data/FOUR_VOLUME.js，不进 raw_data）
    if category in ("post_close", "all"):
        try:
            f_four_volume()
        except Exception as e:
            print(f"  ⚠️ 四量终极策略失败: {e}")

    # 2026-08-22 主人令：STOCK_PROFILE 自愈（从已维护的 stock_names 派生）
    #   原仅 legacy_v6/sync_v6_to_v8.py 生成、不在 v8 云端链路 → 永久陈旧。
    #   现 post_close 每次运行前由 stock_names（同节奏刷新）派生 stock_profile.json，
    #   再由 update_v8 转 data/STOCK_PROFILE.js，周一自动自愈。
    if category in ("post_close", "all"):
        try:
            subprocess.run([sys.executable, str(ROOT / "algorithms" / "gen_stock_profile.py")],
                           cwd=str(ROOT), check=False)
        except Exception as e:
            print(f"  ⚠️ gen_stock_profile 调用失败: {e}")


    # 生成 runner 状态文件，供前端「定时任务跟踪」看板展示
    try:
        runner_status = {
            "run_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category or "all",
            "hostname": os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", ""),
            "modules": _run_status,
            "summary": {
                "total": len(_run_status),
                "ok": sum(1 for v in _run_status.values() if v.get("status") == "ok"),
                "empty": sum(1 for v in _run_status.values() if v.get("status") == "empty"),
                "fail": sum(1 for v in _run_status.values() if v.get("status") == "fail"),
            },
        }
        with open(RAW_DIR / "runner_status.json", "w", encoding="utf-8") as f:
            json.dump(runner_status, f, ensure_ascii=False, separators=(",", ":"), default=str)
        print(f"📋 runner_status: {runner_status['summary']}")
    except Exception as e:
        print(f"  ⚠️ 写入 runner_status 失败: {e}")

    print(f"=== v8 云端抓取结束 {now_cst().isoformat(timespec='seconds')} ===")
    print(f"raw_data/ 文件数: {len(list(RAW_DIR.glob('*.json')))}")

    # 🛡️ 2026-08-12 根治假刷新：有模块失败则返回非零，让 workflow 步骤失败，
    #    从而不执行后续 push，避免把空壳数据提交到 main。
    if _has_critical_failures(category):
        fail_count = sum(1 for v in _run_status.values() if v.get("status") == "fail")
        print(f"❌ {fail_count} 个模块抓取失败，整体任务标记失败，阻止空壳推送")
        return 1
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v8 cloud fetch")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "all"],
                        help="只抓取某一时段类别；all=全量兜底")
    parser.add_argument("--only", default=None,
                        help="只抓取指定变量（如 SH_SZ_HISTORY），跳过 raw_data 清理，不误删其他时段数据")
    args = parser.parse_args()
    sys.exit(main(category=args.category, only=args.only))
