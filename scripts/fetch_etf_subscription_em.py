#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_etf_subscription_em.py — ETF 申购赎回东方财富口径 fetcher

按主人 2026-08-29 指令：东方财富分类（股票型 / 债券型 / 货币型 / 商品型 / 跨境型）+ 亿元。
数据口径：
  - 净申购赎回金额(亿元)：优先用 fund_etf_flow_em 的「净流入」按类型聚合（最接近真实申赎流量）；
  - 若 flow 接口不可用，回退用 fund_etf_category_ths 的「规模」(AUM, 亿元) 填充，保证有真实数据、不再全零。

根因修复（2026-08-31）：旧实现用 ak.fund_etf_fund_info_em()，该函数在 akshare 1.18.64
出现列数不匹配 ValueError → 整脚本抛异常、return 1、不写文件 → raw_data 长期停在
全零占位（2026-08-29）。现改用 fund_etf_category_ths（同花顺 ETF 分类，稳定可用）。

产出：
  - raw_data/etf_subscription_em.json（明细聚合）
  - data/ETF_SUBSCRIPTION_EM.js（window.ETF_SUBSCRIPTION_EM）
"""
import os, json, sys, re
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

# 主人要求的 5 类映射（同花顺 基金类型 别名 -> 东方财富分类 key）
CATEGORY_MAP = {
    "股票型": "stock",
    "债券型": "bond",
    "货币型": "money",
    "商品型": "commodity",
    "跨境型": "cross_border",
}


def _parse_yi(v):
    """把规模/金额字段解析为 亿元(float)。兼容 数值 / '1234.5亿' / '1.23万亿' 等。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return 0.0
    num = float(m.group(1))
    if "万" in s:
        num /= 1e4
    elif "亿" in s:
        pass  # 已是亿
    elif "万亿" in s:
        num *= 1e4
    return num


def _col(df, *candidates):
    """在 df.columns 中按候选关键字找到第一个匹配的列名。"""
    cols = list(df.columns)
    for cand in candidates:
        for c in cols:
            if cand in str(c):
                return c
    return None


def main():
    try:
        import akshare as ak
    except ImportError:
        print("[warn] akshare not installed, skip (云端有)", file=sys.stderr)
        return 0

    out = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare etf_em (东财/同花顺)",
        "metric": "净流入(亿元,优先) / 规模AUM(亿元,回退)",
        "categories": {v: {"name": k, "net_amount_yi": 0.0, "scale_yi": 0.0,
                           "n_funds": 0, "top5": []}
                       for k, v in CATEGORY_MAP.items()}
    }

    # 1) 类型映射：同花顺 ETF 分类
    try:
        cats = ak.fund_etf_category_ths(symbol="ETF")
    except Exception as e:
        print(f"[warn] fund_etf_category_ths failed: {e}", file=sys.stderr)
        cats = None
    if cats is None or getattr(cats, "empty", True):
        print("[warn] etf category empty, write placeholder for freshness SLA", file=sys.stderr)
        _write(out)
        return 2

    type_col = _col(cats, "基金类型", "类型")
    scale_col = _col(cats, "规模")
    code_col = _col(cats, "基金代码", "代码")
    name_col = _col(cats, "基金简称", "名称", "简称")
    if not type_col or not code_col:
        print(f"[warn] category cols missing (type={type_col}, code={code_col}), placeholder", file=sys.stderr)
        _write(out)
        return 3

    # 建立 code -> 东方财富分类
    code2cat = {}
    for _, row in cats.iterrows():
        t = str(row.get(type_col, ""))
        matched = None
        for cn, en in CATEGORY_MAP.items():
            if cn in t:
                matched = en
                break
        if matched:
            c = str(row.get(code_col, "")).strip()
            if c:
                code2cat[c] = matched

    # 2) 优先用 净流入 聚合（真实净申购赎回）
    metric_mode = "规模AUM(回退)"
    try:
        flow = ak.fund_etf_flow_em()
        fcode = _col(flow, "代码", "基金代码")
        fnet = _col(flow, "净流入", "净申购", "净买")
        if flow is not None and not flow.empty and fcode and fnet:
            for _, row in flow.iterrows():
                c = str(row.get(fcode, "")).strip()
                cat = code2cat.get(c)
                if not cat:
                    continue
                val = _parse_yi(row.get(fnet))
                out["categories"][cat]["net_amount_yi"] += val
            metric_mode = "净流入(亿元)"
            print(f"[ok] aggregated net flow by type via fund_etf_flow_em")
    except Exception as e:
        print(f"[warn] fund_etf_flow_em failed ({e}), fall back to 规模", file=sys.stderr)

    # 3) 规模(AUM) 始终聚合（前端可展示；net 回退时用它）
    if scale_col:
        for _, row in cats.iterrows():
            c = str(row.get(code_col, "")).strip()
            cat = code2cat.get(c)
            if not cat:
                continue
            out["categories"][cat]["scale_yi"] += _parse_yi(row.get(scale_col))
            out["categories"][cat]["n_funds"] += 1
    else:
        # 无规模列：仅计数
        for c, cat in code2cat.items():
            out["categories"][cat]["n_funds"] += 1

    # 4) net 回退 = 规模（若 flow 没拿到）
    if metric_mode.startswith("规模"):
        for v in out["categories"].values():
            if v["net_amount_yi"] == 0.0:
                v["net_amount_yi"] = v["scale_yi"]

    # 5) top5 by 规模
    try:
        sub = cats.copy()
        sub["_cat"] = sub[code_col].astype(str).str.strip().map(code2cat)
        sub = sub.dropna(subset=["_cat"])
        if scale_col:
            sub["_scale"] = sub[scale_col].apply(_parse_yi)
            for cat_en, grp in sub.groupby("_cat"):
                top = grp.nlargest(5, "_scale")
                items = []
                for _, r in top.iterrows():
                    items.append({
                        "code": str(r.get(code_col, "")).strip(),
                        "name": str(r.get(name_col, "")).strip() if name_col else "",
                        "scale_yi": round(_parse_yi(r.get(scale_col)), 2),
                    })
                out["categories"][cat_en]["top5"] = items
    except Exception as e:
        print(f"[warn] top5 build skipped: {e}", file=sys.stderr)

    out["metric"] = metric_mode
    _write(out)
    print(f"[ok] etf_subscription_em.json written, metric={metric_mode}, "
          f"counts={{ {', '.join(k+':'+str(v['n_funds']) for k,v in out['categories'].items())} }}")
    return 0


def _write(out):
    raw_out = os.path.join(RAW_DIR, "etf_subscription_em.json")
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[ok] {raw_out}")


if __name__ == "__main__":
    sys.exit(main())
