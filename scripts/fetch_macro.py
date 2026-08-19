#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观环境 fetcher：拉中国国债 + 美国国债 + LPR + 银行间利率
- 用途：利率上行期板块推荐框架（主人 2026-08-19 拍板）
- 数据源：akshare.bond_zh_us_rate / macro_china_lpr / rate_interbank
- 输出：out/macro.json + raw_data/macro.json
"""
import akshare as ak
import json
import os
import datetime
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out", "macro.json")


def log(msg):
    print(f"  [fetch_macro] {msg}", flush=True)


def main():
    log("拉中国+美国国债（ak.bond_zh_us_rate）...")
    try:
        df = ak.bond_zh_us_rate()
    except Exception as e:
        log(f"bond_zh_us_rate 失败: {e}")
        return 1
    df = df.dropna(subset=["日期"]).copy()
    df["date"] = df["日期"].astype(str)
    cn10 = df[["date", "中国国债收益率10年"]].rename(columns={"中国国债收益率10年": "cn_10y"}).dropna()
    us10 = df[["date", "美国国债收益率10年"]].rename(columns={"美国国债收益率10年": "us_10y"}).dropna()
    cn2 = df[["date", "中国国债收益率2年"]].rename(columns={"中国国债收益率2年": "cn_2y"}).dropna()
    us2 = df[["date", "美国国债收益率2年"]].rename(columns={"美国国债收益率2年": "us_2y"}).dropna() if "美国国债收益率2年" in df.columns else None

    log(f"中国 10Y: {len(cn10)} 条 | 美国 10Y: {len(us10)} 条")

    log("拉 LPR（ak.macro_china_lpr）...")
    try:
        df_lpr = ak.macro_china_lpr()
        lpr = []
        for _, r in df_lpr.iterrows():
            lpr.append({
                "date": str(r["TRADE_DATE"]),
                "lpr_1y": float(r["LPR1Y"]) if r["LPR1Y"] == r["LPR1Y"] else None,
                "lpr_5y": float(r["LPR5Y"]) if r["LPR5Y"] == r["LPR5Y"] else None,
            })
        log(f"LPR: {len(lpr)} 条, 最新 1Y={lpr[-1]['lpr_1y']}% 5Y={lpr[-1]['lpr_5y']}%")
    except Exception as e:
        log(f"LPR 失败: {e}")
        lpr = []

    log("拉银行间利率（ak.rate_interbank）...")
    try:
        df_ir = ak.rate_interbank()
        ir = []
        for _, r in df_ir.tail(60).iterrows():
            ir.append({
                "date": str(r["报告日"]),
                "rate": float(r["利率"]) if r["利率"] == r["利率"] else None,
                "chg_bp": float(r["涨跌"]) if r["涨跌"] == r["涨跌"] else None,
            })
        log(f"银行间利率: {len(ir)} 条, 最新 {ir[-1]['rate']}% ({ir[-1]['chg_bp']}bp)")
    except Exception as e:
        log(f"银行间利率失败: {e}")
        ir = []

    out = {
        "meta": {
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "source": "akshare: bond_zh_us_rate + macro_china_lpr + rate_interbank",
        },
        "cn_10y": cn10.to_dict("records")[-180:],   # 近半年
        "us_10y": us10.to_dict("records")[-180:],
        "lpr": lpr[-50:],   # 近 50 次
        "interbank": ir,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str, separators=(",", ":"))
    log(f"已写入 {OUT}, {os.path.getsize(OUT)} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())