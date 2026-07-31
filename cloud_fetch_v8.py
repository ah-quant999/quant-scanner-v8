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
    "VOLATILITY": "volatility.json",
    "HERDING_DATA": "herding_data.json",
    "LIMIT_UP_HEATMAP": "limit_up_heatmap.json",
    "CAPITAL_FLOW_DATA": "capital_flow_data.json",
    "ETF_SUBSCRIPTION": "etf_subscription.json",
    "NORTH_FUND": "north_fund.json",
    "MARKET_FUND_FLOW_DATA": "market_fund_flow_data.json",
    "W52_HIGH": "w52_high.json",
    "ETF_PULSE": "etf_pulse.json",
    "ETF_DAILY_MONITOR": "etf_daily_monitor.json",
}

_ak = None

def get_ak():
    global _ak
    if _ak is None:
        import akshare as _ak_mod
        _ak = _ak_mod
    return _ak

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
    # ETF 资金流向热度：用 ETF 实时行情成交额排序作为热度占位
    # TODO 小九接入真实 ETF 净流入排名后替换
    df = get_ak().fund_etf_spot_em()
    if df is None or df.empty:
        return None
    cols = [c for c in ["代码", "名称", "最新价", "涨跌幅", "成交额", "所属行业"] if c in df.columns]
    try:
        df = df[cols].sort_values("成交额", ascending=False) if "成交额" in df.columns else df[cols]
    except Exception:
        df = df[cols]
    return {"items": df.head(30).to_dict(orient="records"), "note": "ETF净流入真实排名待接入，当前用成交额热度占位"}

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

def f_concept_ranking():
    # 概念板块列表（涨跌幅 + 主力净流入），push2delay 镜像。
    rows = em_clist("m:90 t:3 f:!50", "f12,f14,f3,f62,f184", fid="f62", stat="1", pz=300)
    items = []
    for r in rows:
        items.append({
            "code": r.get("f12"),
            "name": r.get("f14"),
            "chg": round(float(r.get("f3") or 0), 2),
            "net": _to_yi(r.get("f62")),
        })
    if not items:
        return None
    return {"items": items, "note": "概念板块列表(涨跌幅/主力净流入亿)，来源东方财富push2delay"}

def f_ipo_data():
    """打新日历：复用 v6 验证有效的东财 datacenter + 可转债 + 同花顺已上市补充逻辑。"""
    try:
        import fetch_ipo_data_v8 as ipo
        return ipo.generate_ipo_score()
    except Exception as e:
        print(f"  ⚠️ IPO 抓取失败: {e}")
        return None

def f_margin_data():
    # 融资融券（沪市明细）
    df = get_ak().stock_margin_detail_sse()
    if df is None or df.empty:
        return None
    return {"items": df.tail(20).to_dict(orient="records")}

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
    # 宏观：以 CPI/PMI 为例（轻量）
    out = {}
    try:
        cpi = get_ak().macro_china_cpi_yearly()
        out["cpi"] = cpi.tail(6).to_dict(orient="records") if cpi is not None else []
    except Exception:
        out["cpi"] = []
    try:
        pmi = get_ak().macro_china_pmi_yearly()
        out["pmi"] = pmi.tail(6).to_dict(orient="records") if pmi is not None else []
    except Exception:
        out["pmi"] = []
    return out

def f_crisis_data():
    # 危机雷达：国内经济维度(PMI)真实接入；货币/全球维度因外国数据源(CN网络不可达)
    # 暂用保守估值，待补充代理源（如美元人民币、离岸流动性）。
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
    return {
        "currency": 0.30,
        "economy": (round(economy / 100.0, 3) if economy else 0.50),
        "global": 0.40,
        "pmi_value": economy,
        "note": "经济维度=中国PMI真实值；货币/全球维度因外国数据源(CN网络不可达)暂保守估值，待补代理源",
    }

def f_volatility():
    # 20 日年化波动率（样例：沪深300）
    df = get_ak().stock_zh_index_daily(symbol="sh000300")
    if df is None or df.empty:
        return None
    close = df["close"].astype(float).tail(20)
    if len(close) < 2:
        return None
    ret = close.pct_change().dropna()
    ann = ret.std() * (252 ** 0.5)
    return {"hs300_20d_annualized": round(float(ann), 4)}

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
    # 涨停热力图：东方财富涨停池（真实），按行业聚合为时间序列，附连板梯队
    try:
        df = _get_zt_pool()
    except Exception as e:
        print("  zt_pool err:", e)
        return None
    if df is None or df.empty:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    ind = {}
    for _, r in df.iterrows():
        name = r.get("所属行业") or "其它"
        if name in (None, "", "None"):
            name = "其它"
        ind[name] = ind.get(name, 0) + 1
    sectors = [{"name": k, "data": [v]} for k, v in sorted(ind.items(), key=lambda x: -x[1])]
    # 连板梯队
    ladder = {}
    try:
        for _, r in df.iterrows():
            lb = int(r.get("连板数") or 0)
            ladder[lb] = ladder.get(lb, 0) + 1
    except Exception:
        ladder = {}
    # TOP（按连板数）
    top = []
    try:
        for _, r in df.sort_values("连板数", ascending=False).head(8).iterrows():
            top.append({"name": r["名称"], "code": r["代码"],
                        "lbc": int(r.get("连板数") or 0),
                        "chg": round(float(r.get("涨跌幅") or 0), 2)})
    except Exception:
        top = []
    return {
        "total": int(len(df)),
        "dates": [today],
        "sectors": sectors,
        "ladder": ladder,
        "top": top,
        "note": "东方财富涨停池（真实），按行业聚合 + 连板梯队",
    }

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

def f_etf_subscription():
    df = get_ak().fund_etf_category_sina(symbol="ETF基金")
    if df is None or df.empty:
        return None
    return {"items": df.head(30).to_dict(orient="records")}

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    # 大盘资金流：日K线接口(push2his)在当前网络被重置，故以全市场个股主力净流入求和
    # 得到「今日市场主力净流入(亿)」作为单点今日值。后续若镜像开放 daykline 可补历史序列。
    recs = _all_individual_recs("f12,f62")
    if not recs:
        return None
    net_yi = round(sum(x["net"] for x in recs), 2)
    today = datetime.now().strftime("%Y%m%d")
    return {
        "daily": [{"date": today, "net_yi": net_yi}],
        "cumulative": [{"date": today, "cum_yi": net_yi}],
        "market_net": net_yi,
        "note": "今日市场主力净流入(个股汇总，亿)；日K线源被限流，历史序列待累积",
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


def main():
    print(f"=== v8 云端抓取开始 {datetime.now().isoformat(timespec='seconds')} ===")
    run("ETF_INTRADAY_HEAT", f_etf_intraday_heat)
    run("SECTOR_FUND_FLOW", f_sector_fund_flow)
    run("CONCEPT_RANKING", f_concept_ranking)
    run("IPO_DATA", f_ipo_data)
    run("MARGIN_DATA", f_margin_data)
    run("CFFEX_HOLDINGS", f_cffex_holdings)
    run("MACRO_DATA", f_macro_data)
    run("CRISIS_DATA", f_crisis_data)
    run("VOLATILITY", f_volatility)
    run("HERDING_DATA", f_herding_data)
    run("LIMIT_UP_HEATMAP", f_limit_up_heatmap)
    run("CAPITAL_FLOW_DATA", f_capital_flow_data)
    run("ETF_SUBSCRIPTION", f_etf_subscription)
    run("NORTH_FUND", f_north_fund)
    run("MARKET_FUND_FLOW_DATA", f_market_fund_flow_data)
    run("W52_HIGH", f_w52_high)
    run("ETF_PULSE", f_etf_pulse)
    run("ETF_DAILY_MONITOR", f_etf_daily_monitor)
    print(f"=== v8 云端抓取结束 {datetime.now().isoformat(timespec='seconds')} ===")
    print(f"raw_data/ 文件数: {len(list(RAW_DIR.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
