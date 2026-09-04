#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_etf_subscription_em.py — ETF 申购赎回东方财富口径 fetcher

按主人 2026-08-29 指令：东方财富分类（股票型 / 债券型 / 货币型 / 商品型 / 跨境型）+ 亿元。

# 2026-09-04 一劳永逸修复：akshare 1.18.64 起原接口双双失效：
#   - ak.fund_etf_flow_em()        —— 已删除，AttributeError
#   - ak.fund_etf_category_ths()   —— 列名变更，「规模」列已不存在（只剩净值/增长率/申赎状态）
# 现改用 ak.fund_etf_spot_em() 替代，包含【最新份额 / 流通市值 / 总市值 / 主力净流入-净额】
#   - 5 类分类：用 spot_em 名称规则 + category_ths 字段映射
#   - 净申赎(亿) = 主力净流入-净额 ÷ 1e8（已是元单位）
#   - 规模(亿)   = 总市值 ÷ 1e8
#   - n_funds    = 分类下非零只数
"""
import os, json, sys, re
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

CATEGORY_MAP = {
    "股票型": "stock",
    "债券型": "bond",
    "货币型": "money",
    "商品型": "commodity",
    "跨境型": "cross_border",
}


def _norm_cn(s):
    """把 spot_em 名称里的关键字映射到 5 大类的中文名（与 CATEGORY_MAP key 对齐）。"""
    if not s:
        return None
    name = str(s)
    if re.search(r"(货币|现金)", name):
        return "货币型"
    if re.search(r"(债券|可转债|政金|地方债)", name):
        return "债券型"
    if re.search(r"(黄金|白银|有色金属|豆粕|商品|能源化工|原油|石油|有色)", name):
        return "商品型"
    if re.search(r"(跨境|纳指|标普|港股通|恒生|海外|境外|亚洲|印度|德国|日经|越南|沙特|美股|中概|QDII)", name):
        return "跨境型"
    return "股票型"


def _yuan_to_yi(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f:  # NaN
        return 0.0
    return f / 1e8


def main():
    try:
        import akshare as ak
    except ImportError:
        print("[warn] akshare not installed, skip (云端有)", file=sys.stderr)
        return 0

    out = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare fund_etf_spot_em (东方财富)",
        "metric": "净流入(亿元) + 规模(亿元)",
        "categories": {v: {"name": k, "net_amount_yi": 0.0, "scale_yi": 0.0,
                           "n_funds": 0, "top5": []}
                       for k, v in CATEGORY_MAP.items()}
    }

    try:
        spot = ak.fund_etf_spot_em()
    except Exception as e:
        print(f"[err] fund_etf_spot_em failed: {e}", file=sys.stderr)
        _write(out)
        return 2

    if spot is None or len(spot) == 0:
        print("[warn] fund_etf_spot_em empty, placeholder", file=sys.stderr)
        _write(out)
        return 3

    code_col = "代码"
    name_col = "名称"
    type_col = "基金类型" if "基金类型" in spot.columns else None
    flow_col = next((c for c in ["主力净流入-净额", "净流入", "净额", "净申购"] if c in spot.columns), None)
    mv_col = next((c for c in ["总市值", "流通市值"] if c in spot.columns), None)
    date_col = "数据日期" if "数据日期" in spot.columns else None

    if not flow_col:
        print("[warn] 主力净流入列缺失，net 字段将全 0（仅展示规模）", file=sys.stderr)

    per_cat_top = {v: [] for v in CATEGORY_MAP.values()}
    for _, row in spot.iterrows():
        code = str(row.get(code_col, "")).strip()
        name = str(row.get(name_col, "")).strip()
        if not code:
            continue

        cn_type = None
        if type_col:
            t = str(row.get(type_col, "")).strip()
            for cn in CATEGORY_MAP.keys():
                if cn in t:
                    cn_type = cn
                    break
        if not cn_type:
            cn_type = _norm_cn(name)
        if not cn_type:
            continue
        cat_en = CATEGORY_MAP[cn_type]

        net = _yuan_to_yi(row.get(flow_col, 0)) if flow_col else 0.0
        scale = _yuan_to_yi(row.get(mv_col, 0)) if mv_col else 0.0

        bucket = out["categories"][cat_en]
        bucket["net_amount_yi"] += net
        bucket["scale_yi"] += scale
        bucket["n_funds"] += 1

        if scale > 0:
            per_cat_top[cat_en].append({
                "code": code,
                "name": name,
                "scale_yi": round(scale, 2),
                "net_amount_yi": round(net, 4),
            })

    for cat_en, items in per_cat_top.items():
        items.sort(key=lambda x: x["scale_yi"], reverse=True)
        out["categories"][cat_en]["top5"] = items[:5]

    if date_col:
        dates = spot[date_col].astype(str).unique()
        if len(dates) == 1:
            out["data_date"] = str(dates[0])[:10]
        else:
            out["data_date"] = str(sorted(dates)[-1])[:10]

    _write(out)
    summary = ", ".join(f"{k}={v['n_funds']}只/净{v['net_amount_yi']:+.1f}亿/规模{v['scale_yi']:.0f}亿"
                         for k, v in out["categories"].items())
    print(f"[ok] etf_subscription_em.json written ({summary})")
    return 0


def _write(out):
    raw_out = os.path.join(RAW_DIR, "etf_subscription_em.json")
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[ok] {raw_out}")


if __name__ == "__main__":
    sys.exit(main())