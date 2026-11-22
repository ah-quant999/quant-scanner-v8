# -*- coding: utf-8 -*-
"""
A股现金流质量榜生成器 (2026-11-22 主人令：观测「A股现金流最好的股票」卡)

数据铁律：
  1) 数据真实：akshare 批量业绩报表 stock_yjbb_em(报告期)，全市场一次拉取，
     含每股经营现金流/每股收益/净利润/ROE/营收增速/行业/公告日期；计算日与报告期如实标注。
     该接口走东财数据中心(datacenter-web)，非 push2，不受行情接口限流影响。
  2) 算法科学 + 真实标注：
     「现金流最好」定义 = 盈利现金含量 = 每股经营现金流 / 每股收益
       —— 每赚 1 元利润实际收到多少经营现金，衡量盈利质量（非绝对规模；
          绝对现金流大的是银行石油，无观测意义）。
     质量闸：报告期为最新、EPS>=0.2、经营现金流>0、净利润>0、ROE>0、营收>=5亿、
             剔除 ST/退市、剔除金融业(银行/证券/期货/保险/多元金融——现金流含客户存款/保证金，口径不可比)。
     双维度展示：主排序=现金含量(质量)，辅助列=每股经营现金流(规模)+ROE+营收增速。
     ⚠ 诚实边界：三季报为累计值；现金含量倍数受低EPS放大，故设EPS>=0.2闸并同时展示绝对现金流；
        本榜为纯观测快照，不进 Top3 / 终选，不构成投资建议。
  3) 无前视：只用已披露财报(截至计算日可获取的报告期)，公告日期逐只标注。

运行： python algorithms/gen_cashflow_quality.py
产出： raw_data/cashflow_quality.json + data/CASHFLOW_QUALITY.js
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

TOP_N = 15          # 展示前15只
MIN_EPS = 0.2       # 现金含量分母下限，防低EPS虚高
MIN_REVENUE = 5e8   # 营收规模闸 5亿，滤壳股/微盘

BOUNDARY = (
    "现金流质量=每股经营现金流/每股收益(每赚1元利润收到多少现金)；"
    "三季报累计值，含量倍数受低EPS放大(已设EPS≥0.2闸并展示绝对现金流)；"
    "剔除金融业(现金流含客户存款/保证金口径不可比)。纯观测快照，不进Top3/终选。"
)


def pick_period(ak):
    """自动探测最新有数据的报告期（财报披露有滞后，从最近往前试）"""
    now = datetime.now()
    year = now.year
    # 候选报告期：按披露节奏，从最近一期往前
    cands = []
    for y in [year, year - 1, year - 2]:
        for md in ["0930", "0630", "0331", "1231"]:
            cands.append(f"{y}{md}")
    seen = set()
    for period in cands:
        if period in seen:
            continue
        seen.add(period)
        try:
            df = ak.stock_yjbb_em(date=period)
            if df is not None and len(df) > 500 and "每股经营现金流量" in df.columns:
                return period, df
        except Exception:
            continue
    raise RuntimeError("未找到可用的业绩报告期数据")


def main():
    import akshare as ak
    print("[cashflow] 探测最新报告期并拉取全市场业绩报表…")
    period, df = pick_period(ak)
    total_all = len(df)

    d = df.copy()
    d["股票代码"] = d["股票代码"].astype(str).str.zfill(6)

    # 公告日期闸：只留本期新披露(2026年公告)，避免陈旧的半年报/年报混入
    ann = d["最新公告日期"].astype(str)
    d = d[ann.str.startswith(str(datetime.now().year))]

    # 剔除 ST / 退市
    d = d[~d["股票简称"].astype(str).str.contains("ST|退", na=False)]

    # 剔除金融业（现金流口径不可比）
    fin = d["所处行业"].astype(str).str.contains("银行|证券|期货|保险|金融", na=False)
    d = d[~fin]

    # 数值质量闸
    for col in ["每股收益", "每股经营现金流量", "净利润-净利润", "净资产收益率", "营业总收入-营业总收入"]:
        d[col] = __import__("pandas").to_numeric(d[col], errors="coerce")
    d = d[d["每股收益"] >= MIN_EPS]
    d = d[d["每股经营现金流量"] > 0]
    d = d[d["净利润-净利润"] > 0]
    d = d[d["净资产收益率"] > 0]
    d = d[d["营业总收入-营业总收入"] >= MIN_REVENUE]

    # 现金含量
    d["含量"] = d["每股经营现金流量"] / d["每股收益"]

    def market(code):
        if code.startswith(("8", "4")):
            return "北交所"
        if code.startswith("688"):
            return "科创板"
        if code.startswith("30"):
            return "创业板"
        return "主板"

    top = d.sort_values("含量", ascending=False).head(TOP_N)
    stocks = []
    for _, r in top.iterrows():
        stocks.append({
            "code": r["股票代码"],
            "name": str(r["股票简称"]),
            "quality": round(float(r["含量"]), 2),          # 现金含量(主排序)
            "cash_ps": round(float(r["每股经营现金流量"]), 2),  # 每股经营现金流(规模)
            "eps": round(float(r["每股收益"]), 2),
            "roe": round(float(r["净资产收益率"]), 2),
            "rev_growth": round(float(r["营业总收入-同比增长"]), 1)
                          if __import__("pandas").notna(r.get("营业总收入-同比增长")) else None,
            "industry": str(r["所处行业"]) if __import__("pandas").notna(r.get("所处行业")) else "—",
            "market": market(r["股票代码"]),
            "ann_date": str(r["最新公告日期"]),
        })

    out = {
        "version": 1,
        "calc_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period": period,
        "period_label": f"{period[:4]}年{int(period[4:6])}月报(累计)",
        "source": "akshare stock_yjbb_em (东财数据中心批量业绩报表，非push2)",
        "boundary": BOUNDARY,
        "universe": {"all": total_all, "after_filter": len(d)},
        "criteria": {
            "rank_by": "现金含量=每股经营现金流/每股收益",
            "gates": f"EPS≥{MIN_EPS}, 经营现金流>0, 净利润>0, ROE>0, 营收≥{MIN_REVENUE/1e8:.0f}亿, 剔ST/金融",
        },
        "stocks": stocks,
    }

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    jp = os.path.join(RAW, "cashflow_quality.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    js = os.path.join(DATA, "CASHFLOW_QUALITY.js")
    with open(js, "w", encoding="utf-8") as f:
        f.write("window.CASHFLOW_QUALITY = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"[cashflow] 报告期 {period} | 全市场 {total_all} → 闸后 {len(d)} → 展示 {len(stocks)}")
    print(f"[cashflow] 输出 {jp} / {js}")
    if stocks:
        t = stocks[0]
        print(f"[cashflow] 榜首 {t['name']}({t['code']}) 含量{t['quality']} 每股现金流{t['cash_ps']}")
    return out


if __name__ == "__main__":
    main()
