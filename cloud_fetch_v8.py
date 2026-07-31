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
from datetime import datetime
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
    df = get_ak().stock_sector_fund_flow_rank(indicator="今日")
    if df is None or df.empty:
        return None
    return {"items": df.head(50).to_dict(orient="records")}

def f_concept_ranking():
    df = get_ak().stock_board_concept_name_em()
    if df is None or df.empty:
        return None
    return {"items": df.head(80).to_dict(orient="records")}

def f_ipo_data():
    df = get_ak().stock_ipo_summary_cninfo()
    if df is None or df.empty:
        return None
    return {"items": df.tail(30).to_dict(orient="records")}

def f_margin_data():
    # 融资融券（沪市明细）
    df = get_ak().stock_margin_detail_sse()
    if df is None or df.empty:
        return None
    return {"items": df.tail(20).to_dict(orient="records")}

def f_cffex_holdings():
    # 中金所股指期货日行情（最近20个交易日）
    df = get_ak().get_cffex_daily(date="20260730")
    if df is None or df.empty:
        return None
    return {"items": df.tail(20).to_dict(orient="records"), "note": "占位：中金所日行情，真实持仓/情绪指标待接入"}

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
    # 危机雷达：货币/经济/全球三类打分（占位，需小九接入真实宏观信号）
    return {
        "currency": 0.30, "economy": 0.35, "global": 0.25,
        "note": "占位结构，待小九接入真实宏观/货币/全球风险信号",
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
    # 羊群效应（占位，需小九接入真实计算）
    return {"note": "占位结构，待小九接入真实羊群效应计算"}

def f_limit_up_heatmap():
    # 涨停热力图（需涨停池数据，akshare 无直接接口，占位）
    return {"note": "占位结构，涨停池由小九本地 fetch_limit_up 提供"}

def f_capital_flow_data():
    df = get_ak().stock_individual_fund_flow_rank()
    if df is None or df.empty:
        return None
    return {"items": df.head(50).to_dict(orient="records")}

def f_etf_subscription():
    df = get_ak().fund_etf_category_sina(symbol="ETF基金")
    if df is None or df.empty:
        return None
    return {"items": df.head(30).to_dict(orient="records")}

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    df = get_ak().stock_market_fund_flow()
    if df is None or df.empty:
        return None
    return {"items": df.tail(10).to_dict(orient="records")}

def f_w52_high():
    # 52 周新高（占位，需小九接入真实列表）
    return {"note": "占位结构，待小九接入 52 周新高列表", "total": 0, "top_gainers": []}


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
