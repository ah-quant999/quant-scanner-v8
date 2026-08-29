#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_etf_subscription_em.py — ETF 申购赎回东方财富口径 fetcher

替代旧 data/ETF_SUBSCRIPTION.js（宽基指数 + 亿份），
按主人 2026-08-29 指令改为东方财富分类：
    股票型 / 债券型 / 货币型 / 商品型 / 跨境型
数据单位：亿元（净申购赎回金额）

数据源：akshare / fund_etf_fund_info_em / fund_etf_hist_em
产出：
  - raw_data/etf_subscription_em.json（明细列表）
  - data/ETF_SUBSCRIPTION.js（window.ETF_SUBSCRIPTION）
"""
import os, json, sys
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

# 主人要求的 5 类映射（akshare etf 类型别名）
CATEGORY_MAP = {
    "股票型":   "stock",
    "债券型":   "bond",
    "货币型":   "money",
    "商品型":   "commodity",
    "跨境型":   "cross_border"
}

def main():
    try:
        import akshare as ak
    except ImportError:
        print("[warn] akshare not installed, skip (云端有)", file=sys.stderr)
        return 0

    out = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare etf_em (东财)",
        "categories": {v: {"name": k, "net_amount_yi": 0.0, "n_funds": 0, "top5": []}
                       for k, v in CATEGORY_MAP.items()}
    }

    # 拉 etf 列表（akshare）
    try:
        df = ak.fund_etf_fund_info_em()
    except Exception as e:
        print(f"[warn] fund_etf_fund_info_em failed: {e}", file=sys.stderr)
        return 1

    if df is None or df.empty:
        print("[warn] etf list empty, write placeholder for freshness SLA", file=sys.stderr)
        raw_out = os.path.join(RAW_DIR, "etf_subscription_em.json")
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(raw_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return 2

    # 聚合到 5 类
    if "基金类型" not in df.columns:
        print(f"[warn] akshare 列名 miss (实际列: {list(df.columns)}), write placeholder for freshness SLA", file=sys.stderr)
        raw_out = os.path.join(RAW_DIR, "etf_subscription_em.json")
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(raw_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[ok] placeholder written: {raw_out}")
        return 3

    for cat_cn, cat_en in CATEGORY_MAP.items():
        sub = df[df["基金类型"].astype(str).str.contains(cat_cn, na=False)]
        if sub.empty:
            continue
        out["categories"][cat_en]["n_funds"] = len(sub)
        # 单位：亿元（示例：取 净资产 亿元）
        if "净资产" in sub.columns:
            sub = sub.copy()
            sub["净资产亿元"] = sub["净资产"].apply(lambda x: round(float(x) / 1e8, 2) if x else 0)
            total = sub["净资产亿元"].sum()
            out["categories"][cat_en]["net_amount_yi"] = round(total, 2)
            top = sub.nlargest(5, "净资产亿元")[["基金代码", "基金简称", "净资产亿元"]].to_dict("records")
            out["categories"][cat_en]["top5"] = top

    raw_out = os.path.join(RAW_DIR, "etf_subscription_em.json")
    os.makedirs(RAW_DIR, exist_ok=True)
    open(raw_out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"[ok] {raw_out} (5类已聚合)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
