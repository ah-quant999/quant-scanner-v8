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

import json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

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

# 变量名 → raw_data 文件名（与 update_v8.py 的 DATA_SOURCES 对应）
VAR_TO_RAW = {
    "ETF_INTRADAY_HEAT": "etf_intraday_heat.json",
    "SECTOR_FUND_FLOW": "sector_fund_flow.json",
    "CONCEPT_RANKING": "concept_ranking.json",
    "IPO_DATA": "ipo_score.json",
    "MARGIN_DATA": "margin_data.json",
    "CFFEX_HOLDINGS": "cffex_data.json",
    "MACRO_DATA": "macro_data.json",
    "CRISIS_DATA": "crisis_data.json",
    "HERDING_DATA": "herding_data.json",
    "LIMIT_UP_HEATMAP": "limit_up_heatmap.json",
    "CAPITAL_FLOW_DATA": "capital_flow_data.json",
    "ETF_SUBSCRIPTION": "etf_subscription.json",
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
}

# 变量名 → 更新时段（与 update_v8.py 的 CATEGORY_MAP 对齐）
CATEGORY_MAP = {
    # 盘前
    "V8_CAL": "premarket",
    "IPO_DATA": "premarket",
    "MARGIN_DATA": "premarket",
    "CFFEX_HOLDINGS": "premarket",
    "MACRO_DATA": "premarket",
    "CRISIS_DATA": "premarket",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    "W52_HIGH": "premarket",
    "HERDING_DATA": "premarket",
    # 盘中（含 ETF 三连板、板块资金三连板盘中追热等实时场景）
    "INDEX_QUOTES": "intraday",
    "ETF_PULSE": "intraday",
    "ETF_INTRADAY_HEAT": "intraday",
    "ETF_DAILY_MONITOR": "intraday",
    "ETF_SUBSCRIPTION": "premarket",  # T+1 盘后/盘前更新一次即可
    "SECTOR_FUND_FLOW": "intraday",
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday",
    "CANDIDATE_QUOTES": "intraday",  # 候选池实时行情：行业树图第二层（个股）数据源
    "SH_SZ_HISTORY": "intraday",  # 沪深成交额历史（滚动窗口，盘中最少5刷）
    # 盘后（15:30 后）：大盘资金流时间轴，累积历史序列，避免盘中覆盖
    "MARKET_FUND_FLOW_DATA": "post_close",
    # 15:30 收盘数据：EXPERIMENT 等 akshare 可抓的 T+1 数据
    "EXPERIMENT": "post_close",
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
    d = d or datetime.now().date()
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

def save(var, obj):
    fname = VAR_TO_RAW.get(var)
    if not fname:
        return
    obj = obj if isinstance(obj, dict) else {"data": obj}
    obj["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = RAW_DIR / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"  ✅ {var} → raw_data/{fname}")


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

def em_clist(fs, fields, fid="f62", stat="1", pz=5000, po="1", timeout=15):
    """东方财富 clist 接口（push2delay 镜像）。返回 data.diff 列表（每项为字段字典）。
    po="1" 降序(取净流入最高)，po="0" 升序(取净流出最高)。"""
    params = {
        "pn": "1", "pz": str(pz), "po": po, "np": "1", "fltt": "2", "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fid": fid, "fs": fs, "stat": stat,
        "fields": fields, "_": int(time.time() * 1000),
    }
    r = _requests.get(f"{_EM_DELAY}/api/qt/clist/get", params=params,
                      headers=_EM_HEADERS, timeout=timeout)
    d = r.json()
    if d.get("rc") != 0 or not d.get("data"):
        return []
    return d["data"].get("diff", []) or []

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

def run(label, fn, retries=2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            print(f">>> {label} {datetime.now().isoformat(timespec='seconds')}{' (retry '+str(attempt)+')' if attempt else ''}")
            obj = fn()
            if obj is not None:
                save(label, obj)
            else:
                print(f"  ⚠️ {label}: 返回空，跳过")
            return
        except Exception as e:
            last_err = e
            print(f"  ❌ {label} 失败(attempt {attempt+1}/{retries+1}): {type(e).__name__}: {e}")
            time.sleep(2)
    print(f"  🚫 {label} 跳过，最终错误: {type(last_err).__name__}: {last_err}")
    time.sleep(0.5)

# 涨停池缓存（避免 limit_up_heatmap / herding 重复抓取同一份数据）
_zt_cache = {"date": None, "df": None}
def _get_zt_pool():
    d = datetime.now().strftime("%Y%m%d")
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
        if any(k in n for k in ["沪深300", "中证500", "中证1000", "创业板", "科创", "上证50",
                                 "上证180", "深证", "MSCI", "A50", "双创", "300ETF", "500ETF"]):
            return "宽基"
        if any(k in n for k in ["恒生", "纳斯达克", "标普", "纳指", "日经", "德国", "法国", "美国",
                                 "道琼斯", "港股", "中概", "标普", "H股", "日本", "东南亚"]):
            return "跨境"
        if any(k in n for k in ["5G", "人工智能", "AI", "半导体", "芯片", "新能源", "碳中和", "国企",
                                 "医药", "消费", "券商", "银行", "证券", "军工", "有色", "煤炭", "地产",
                                 "化工", "食品", "汽车", "光伏", "锂电", "机器人", "算力", "数据", "稀土",
                                 "钢铁", "保险", "传媒", "游戏", "养殖", "农业", "电力", "通信", "环保",
                                 "酒", "中药", "疫苗", "创新药", "VR", "物联网", "区块链", "元宇宙",
                                 "芯片", "科技", "电子", "高端装备", "智能"]):
            return "主题"
        return "行业"

    cats = {"宽基": [], "行业": [], "主题": [], "跨境": []}
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
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def f_sector_fund_flow():
    # 板块/概念资金流：行业(m:90 t:2) + 概念(m:90 t:3)，主力净流入(f62, 元→亿)
    # 走 push2delay 镜像，规避实时 push2 host 的 WAF 重置。renderSector 从 top_list 派生流入/流出。
    items = []
    for stype, fs in [("行业", "m:90 t:2"), ("概念", "m:90 t:3")]:
        rows = em_clist(fs, "f12,f14,f3,f62,f184", fid="f62", stat="1", pz=200)
        for r in rows:
            net = _to_yi(r.get("f62"))
            if net == 0:
                continue
            items.append({
                "name": r.get("f14"),
                "type": stype,
                "net": net,
                "chg": round(float(r.get("f3") or 0), 2),
            })
    if not items:
        return None
    items.sort(key=lambda x: x["net"], reverse=True)
    return {"top_list": items, "note": "行业+概念主力净流入(亿)，来源东方财富push2delay"}

def f_index_quotes():
    # 四大核心宽基指数实时行情：上证/深证/创业板/科创50
    # 东财 ulist.np 接口，secid 规则：1=上海，0=深圳
    secids = "1.000001,0.399001,0.399006,1.000688"
    names = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000688": "科创50"}
    short = {"000001": "沪指", "399001": "深成指", "399006": "创业板", "000688": "科创板"}
    try:
        r = _requests.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                    "fields": "f2,f3,f4,f5,f6,f12,f13,f14,f18,f20,f21", "secids": secids},
            headers=_EM_HEADERS, timeout=12)
        j = r.json()
        rows = j.get("data", {}).get("diff", []) or []
    except Exception as e:
        print(f"  ⚠️ 东财指数行情失败: {e}")
        rows = []
    items = []
    for r in rows:
        code = str(r.get("f12") or "")
        # 东财 f13 标记 1=上海 0=深圳
        prefix = "SH" if str(r.get("f13")) == "1" else "SZ"
        full_code = prefix + code
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
        })
    if not items:
        return None
    return {"items": items, "note": "东财实时指数行情"}

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
                rows = j.get("data", {}).get("diff", []) or []
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
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
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
    result["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return result

def f_cffex_holdings():
    # 中金所股指期货日行情：动态取最近有数据的交易日（盘后数据通常当日稍晚才出）
    ak = get_ak()
    base = datetime.now()
    for back in range(0, 8):
        dd = (base - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = ak.get_cffex_daily(date=dd)
        except Exception as e:
            df = None
        if df is not None and not df.empty:
            return {"items": df.to_dict(orient="records"),
                    "update_time": dd,
                    "note": "中金所股指期货日行情（最近交易日 %s）" % dd}
    return None

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
            is_fresh = (datetime.now() - dt).days <= 60
        except Exception:
            pass
        out['indicator_status'][indicator_key] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
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
            key = line[len('var hq_str_'):line.find('=')]
            rest = line[line.find('"') + 1:line.rfind('"')]
            result[key] = rest.split(',') if rest else []
        return result

    try:
        sina_codes = "fx_susdcnh,DINIW,b_VIX,hf_GC,hf_SI,hf_HG,hf_CL"
        r = _requests.get(
            f"https://hq.sinajs.cn/list={sina_codes}",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=15,
        )
        r.encoding = 'gb2312'
        data = _parse_sina_csv(r.text)

        gm = out.setdefault('global_macro', {})
        # 离岸人民币：取第 8 位（收盘价/即期）
        if data.get('fx_susdcnh') and len(data['fx_susdcnh']) > 8:
            gm['usdcnh'] = {'price': float(data['fx_susdcnh'][8])}
        # 美元指数 DINIW：取第 8 位
        if data.get('DINIW') and len(data['DINIW']) > 8:
            gm['dxy'] = {'value': float(data['DINIW'][8])}
        # VIX：取第 1 位；日期为美股交易日
        if data.get('b_VIX') and len(data['b_VIX']) > 1:
            try:
                gm['vix'] = {'value': float(data['b_VIX'][1])}
            except Exception:
                pass
        # 商品：取第 0 位最新价
        for code, name in [('hf_GC', 'gold'), ('hf_SI', 'silver'), ('hf_HG', 'copper'), ('hf_CL', 'oil')]:
            parts = data.get(code, [])
            if parts and len(parts) > 0:
                try:
                    gm[name] = {'value': float(parts[0])}
                except Exception:
                    pass
    except Exception as e:
        print(f"  ⚠️ 全球宏观获取失败: {e}")

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
                    if usd_cny_latest < 6.9:
                        currency_score = 0.15  # 强势人民币
                    elif usd_cny_latest < 7.1:
                        currency_score = 0.25  # 正常偏强
                    elif usd_cny_latest < 7.25:
                        currency_score = 0.40  # 正常区间
                    elif usd_cny_latest < 7.35:
                        currency_score = 0.55  # 有贬值压力
                    else:
                        currency_score = min(0.85, 0.55 + (usd_cny_latest - 7.35) * 0.3)
    except Exception as e:
        print(f"    ⚠️ 汇率数据获取失败: {e}")

    # 全球维度：仍用保守估值（CN 网络难达 VIX/美债等实时源），但标注更清晰
    global_score = 0.40  # 中性

    return {
        "currency": round(currency_score, 3),
        "economy": (round(economy / 100.0, 3) if economy else 0.50),
        "global": round(global_score, 3),
        "pmi_value": economy,
        "usd_cny": usd_cny_latest,
        "note": f"经济维度=中国PMI真实值({economy or 'N/A'})；"
               f"货币维度=中国银行USD/CNY中间价({usd_cny_latest or 'N/A'})；"
               f"全球维度因VIX/美债等源CN不可达暂用中性估值",
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
            top = []
            for _, r in df.sort_values("连板数", ascending=False).head(8).iterrows():
                top.append({"name": r["名称"], "code": r["代码"],
                            "lbc": int(r.get("连板数") or 0),
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

# 宽基ETF申赎：行业/主题排除关键词（与 v6 fetch_etf_subscription.py 保持一致）
_ETF_SECTOR_KEYWORDS = [
    '半导体','芯片','医药','医疗','券商','银行','煤炭','通信','消费','军工','电池','新能源','光伏','有色','化工',
    '物联网','云计算','互联','科技','传媒','地产','基建','食品','汽车','钢铁','建材','农业','环保','旅游','教育',
    '港股','恒生','H股','德国','日本','法国','印度','越南','黄金','原油','豆粕','能源','商品','货币','债券','国债',
    '国开','政金','城投','信用','短融','存单','理财','标普','纳斯达克','MSCI','富时','央企','国企','产业','畜牧',
    '养殖','种植','渔业','种业','化肥','农药','服装','家电','造纸','包装','石油','天然气','电力','水务','燃气',
    '供热','固废','污水','风电','核电','水电','储能','氢能','生物质','充电桩','换电','锂电','钠电','固态','燃料电池',
    '电机','电控','轨道交通','航空航天','船舶','港口','机场','公路','铁路','物流','快递','仓储','供应链','贸易',
    '零售','电商','免税','餐饮','酒店','演艺','会展','体育','游戏','动漫','影视','音乐','广告','营销','家政','共享',
    '租赁','卫星','火箭','基因','干细胞','机器人','无人机','虚拟','增强','量子','纳米','石墨烯','超导','核聚变',
    '信创','电子','电信','5G','6G','AI','智能制造','工业','芯','数字','大数据','金融科技','区块链','元宇宙','碳中和',
]
_ETF_BROAD_PATTERNS = [
    r'(?:沪深)?300(?:ETF|指数|基金|[A-Z]|增|价值|成长|质量|ESG|红利|指增|增强)?$',
    r'^(?:中证)?500(?:ETF|指数|基金|质量|低波|价值|成长|增强)?$',
    r'^(?:中证)?1000(?:ETF|指数|基金|价值|成长|增强)?$',
    r'^(?:上证)?50(?:ETF|指数|基金|[A-Z])?$',
    r'^(?:上证)?180(?:ETF|指数|基金|[A-Z])?$',
    r'^创业板(?:ETF|指数|50)?$',
    r'^创50(?:ETF)?$',
    r'^(?:科创板|科创)(?:50|100|200)(?:ETF|指数|基金|[A-Za-z])?$',
    r'^(?:中证)?A500(?:ETF|基金|指数|龙头|添富|富国|华宝|中金|申万|银河|红利|增强|[A-Z])?$',
    r'^A500[EF]?$',
    r'^综指ETF$',
    r'^(?:上证|沪深|中证)综合(?:ETF|指数)?$',
    r'^AH300ETF$',
    r'^AH500ETF$',
    r'^A50ETF$',
    r'^双创50(?:ETF)?$',
]

def _is_broad_etf(name):
    n = str(name or "").strip()
    for kw in _ETF_SECTOR_KEYWORDS:
        if kw in n:
            return False
    for p in _ETF_BROAD_PATTERNS:
        if __import__("re").search(p, n):
            return True
    return False

def _trade_dates(n=60):
    dates = []
    d = datetime.now()
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return list(reversed(dates))

def f_etf_subscription():
    """宽基ETF净申赎：上交所ETF份额日环比，筛选宽基指数ETF。
    输出结构与 v6 ETF_SUBSCRIPTION 一致：{sh:[{date,date_raw,total_shares_bil,net_subscribe_bil}], update_time}
    """
    dates = _trade_dates(60)
    result = {"sh": [], "sh_all": [], "update_time": ""}
    prev_total = None
    prev_total_all = None
    for d in dates:
        try:
            df = get_ak().fund_etf_scale_sse(date=d)
            if df is None or len(df) == 0:
                continue
            # 基金份额字段名兼容
            share_col = "基金份额" if "基金份额" in df.columns else None
            if share_col is None:
                continue
            df_broad = df[df["基金简称"].apply(_is_broad_etf)]
            broad_shares = float(df_broad[share_col].sum()) if len(df_broad) else 0.0
            all_shares = float(df[share_col].sum())
            dt_fmt = f"{int(d[4:6])}/{int(d[6:8])}"
            dt_raw = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            entry = {"date": dt_fmt, "date_raw": dt_raw, "total_shares_bil": round(broad_shares / 1e8, 2)}
            if prev_total is not None:
                entry["net_subscribe_bil"] = round((broad_shares - prev_total) / 1e8, 2)
            else:
                entry["net_subscribe_bil"] = 0.0
            result["sh"].append(entry)
            prev_total = broad_shares

            entry_all = {"date": dt_fmt, "date_raw": dt_raw, "total_shares_bil": round(all_shares / 1e8, 2)}
            if prev_total_all is not None:
                entry_all["net_subscribe_bil"] = round((all_shares - prev_total_all) / 1e8, 2)
            else:
                entry_all["net_subscribe_bil"] = 0.0
            result["sh_all"].append(entry_all)
            prev_total_all = all_shares
        except Exception:
            pass
        time.sleep(0.15)
    if not result["sh"]:
        return None
    result["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"  ✅ 宽基ETF净申赎：{len(result['sh'])} 条")
    return result

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    """大盘资金流向时间轴：东方财富 push2his 日线接口。
    取上证指数(000001)主力资金净流入历史序列，覆盖今年以来到最近交易日。
    f52=主力净流入(元)，f62/f63=上证收盘/涨跌幅，f64/f65=深证收盘/涨跌幅。
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

    if not klines:
        return None

    daily = []
    sh_quote = {}
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
            entry["super_large_yi"] = _f(2)
            entry["large_yi"]       = _f(3)
            entry["medium_yi"]      = _f(4)
            entry["small_yi"]       = _f(5)
            entry["main_pct"]       = _pct(6)
            entry["small_pct"]      = _pct(7)
        daily.append(entry)
        if len(parts) >= 15:
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
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    rows = data.get("diff") or []
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
    year = datetime.now().year

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
                        "date": datetime.now().strftime("%Y-%m-%d"),
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
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


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
                "events": ev.get(d.day, []) if not dim else [],
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
    return {
        "month": f"{y}年{m}月",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "legend": legend,
        "weeks": weeks,
    }


def main(category=None):
    print(f"=== v8 云端抓取开始 {datetime.now().isoformat(timespec='seconds')} "
          f"category={category or 'all'} ===")

    # 假期/周末冻结：盘中/盘后/盘前（非周六T+1）遇到非交易日时跳过，保留上一交易日收盘数据
    today = datetime.now().date()
    is_saturday = today.weekday() == 5
    if category in ("intraday", "post_close") and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日，{category} 跳过，保留上一交易日收盘数据")
        return 0
    if category == "premarket" and not is_saturday and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日且非周六T+1，premarket 跳过")
        return 0

    # 分时段清理：只删除本次任务类别的 raw_data，避免盘中任务把盘前/盘后数据清掉
    target_vars = None
    if category == "all":
        target_vars = set(CATEGORY_MAP.keys())
        print(f"🎯 全量兜底模式，涉及 {len(target_vars)} 个变量")
    elif category:
        target_vars = {var for var, cat in CATEGORY_MAP.items() if cat == category}
        if not target_vars:
            print(f"⚠️ 未知 category={category}，无任务可执行")
            return 0
        print(f"🎯 目标类别 {category}，涉及 {len(target_vars)} 个变量")
    else:
        print("🎯 全量模式，执行全部 cloud_fetch 模块")

    cleaned = 0
    for old in RAW_DIR.glob("*.json"):
        if category:
            # 只清理属于当前 category 的文件
            var_for_file = None
            for var, fname in VAR_TO_RAW.items():
                if fname == old.name:
                    var_for_file = var
                    break
            if var_for_file not in target_vars:
                continue
        try:
            old.unlink()
            cleaned += 1
        except Exception as e:
            print(f"  ⚠️  清理旧文件失败 {old.name}: {e}")
    if cleaned:
        print(f"  🧹 已清理 {cleaned} 个旧 raw_data/*.json")

    # 任务列表：顺序影响下游构建，保持原有顺序
    def f_sh_sz_history():
        """沪深两市每日成交额历史（滚动窗口，供量能对比图）。

        东财 push2his 指数日线接口分别取上证(1.000001)与深证(0.399001)的
        成交额(f57, 单位元)，按日期对齐后输出 amount_history：
            [{date:'M/D', sh_amount, sz_amount, total}]  （单位：亿元）
        滚动保留最近 ~130 个交易日；index.html 按数组顺序渲染折线。
        """
        def _fetch_amount(secid):
            url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                "lmt": "0", "klt": "101", "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f57",   # f51=日期, f57=成交额(元)
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "_": int(time.time() * 1000),
            }
            try:
                r = _requests.get(url, params=params, headers=_EM_HEADERS, timeout=20)
                text = r.text
                s = text.find("{"); e = text.rfind(")")
                j = json.loads(text[s:e if e > 0 else None])
                klines = (j.get("data") or {}).get("klines") or []
                out = {}
                for line in klines:
                    parts = line.split(",")
                    if len(parts) < 7:
                        continue
                    ds = parts[0].replace("-", "")
                    try:
                        out[ds] = round(float(parts[6]) / 1e8, 1)  # 元 → 亿
                    except Exception:
                        continue
                return out
            except Exception as ex:
                print(f"  ⚠️ 沪深成交额接口失败({secid}): {ex}")
                return {}

        sh = _fetch_amount("1.000001")
        sz = _fetch_amount("0.399001")
        dates = sorted(set(sh) & set(sz))
        if not dates:
            return None
        window = dates[-130:]
        amount_history = []
        for d in window:
            sh_a = sh.get(d, 0.0)
            sz_a = sz.get(d, 0.0)
            mm = str(int(d[4:6]))
            dd = str(int(d[6:8]))
            amount_history.append({
                "date": f"{mm}/{dd}",
                "sh_amount": sh_a,
                "sz_amount": sz_a,
                "total": round(sh_a + sz_a, 1),
            })
        return {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount_history": amount_history,
        }

    tasks = [
        ("ETF_INTRADAY_HEAT", f_etf_intraday_heat),
        ("SECTOR_FUND_FLOW", f_sector_fund_flow),
        ("INDEX_QUOTES", f_index_quotes),
        ("CONCEPT_RANKING", f_concept_ranking),
        ("IPO_DATA", f_ipo_data),
        ("MARGIN_DATA", f_margin_data),
        ("CFFEX_HOLDINGS", f_cffex_holdings),
        ("MACRO_DATA", f_macro_data),
        ("CRISIS_DATA", f_crisis_data),
        ("HERDING_DATA", f_herding_data),
        ("LIMIT_UP_HEATMAP", f_limit_up_heatmap),
        ("CAPITAL_FLOW_DATA", f_capital_flow_data),
        ("ETF_SUBSCRIPTION", f_etf_subscription),
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
    ]

    for var, fn in tasks:
        if target_vars is not None and var not in target_vars:
            continue
        run(var, fn)

    print(f"=== v8 云端抓取结束 {datetime.now().isoformat(timespec='seconds')} ===")
    print(f"raw_data/ 文件数: {len(list(RAW_DIR.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v8 cloud fetch")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "all"],
                        help="只抓取某一时段类别；all=全量兜底")
    args = parser.parse_args()
    sys.exit(main(category=args.category))
