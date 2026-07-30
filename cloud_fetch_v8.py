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
}

_ak = None

def ak():
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
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ✅ {var} → raw_data/{fname}")

def run(label, fn):
    try:
        print(f">>> {label} {datetime.now().isoformat(timespec='seconds')}")
        obj = fn()
        if obj is not None:
            save(label, obj)
        else:
            print(f"  ⚠️ {label}: 返回空，跳过")
    except Exception as e:
        print(f"  ❌ {label} 失败: {type(e).__name__}: {e}")
    time.sleep(0.5)

# ───────────────────────── 各模块抓取（akshare） ─────────────────────────

def f_etf_intraday_heat():
    # ETF 资金流向热度（东方财富）
    df = ak.fund_flow_rank(indicator="ETF")
    if df is None or df.empty:
        return None
    return {"items": df.head(30).to_dict(orient="records")}

def f_sector_fund_flow():
    df = ak.stock_sector_fund_flow_rank(indicator="今日")
    if df is None or df.empty:
        return None
    return {"items": df.head(50).to_dict(orient="records")}

def f_concept_ranking():
    df = ak.stock_board_concept_name_em()
    if df is None or df.empty:
        return None
    return {"items": df.head(80).to_dict(orient="records")}

def f_ipo_data():
    df = ak.stock_ipo_summary()
    if df is None or df.empty:
        return None
    return {"items": df.tail(30).to_dict(orient="records")}

def f_margin_data():
    # 融资融券（沪市汇总）
    df = ak.stock_margin_detail_sh()
    if df is None or df.empty:
        return None
    return {"items": df.tail(20).to_dict(orient="records")}

def f_cffex_holdings():
    df = ak.futures_cffex_detail_sr()
    if df is None or df.empty:
        return None
    return {"items": df.head(20).to_dict(orient="records")}

def f_macro_data():
    # 宏观：以 CPI/PMI 为例（轻量）
    out = {}
    try:
        cpi = ak.macro_china_cpi_yearly()
        out["cpi"] = cpi.tail(6).to_dict(orient="records") if cpi is not None else []
    except Exception:
        out["cpi"] = []
    try:
        pmi = ak.macro_china_pmi_yearly()
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
    df = ak.stock_zh_index_daily(symbol="sh000300")
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
    df = ak.stock_individual_fund_flow_rank()
    if df is None or df.empty:
        return None
    return {"items": df.head(50).to_dict(orient="records")}

def f_etf_subscription():
    df = ak.fund_etf_category_sina(symbol="ETF基金")
    if df is None or df.empty:
        return None
    return {"items": df.head(30).to_dict(orient="records")}

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    df = ak.stock_market_fund_flow()
    if df is None or df.empty:
        return None
    return {"items": df.tail(10).to_dict(orient="records")}

def f_w52_high():
    # 52 周新高（占位，需小九接入真实列表）
    return {"note": "占位结构，待小九接入 52 周新高列表", "total": 0, "top_gainers": []}


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
    print(f"=== v8 云端抓取结束 {datetime.now().isoformat(timespec='seconds')} ===")
    print(f"raw_data/ 文件数: {len(list(RAW_DIR.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
