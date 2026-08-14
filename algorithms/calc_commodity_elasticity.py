#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品涨价弹性榜（2026-08-13 新增 · 暂未上架实验区）
================================================
- 实时价数据源：MACRO_DATA.global_macro.commodities（gold/silver/copper/oil 快照价，含 date）
- 基准：REFERENCE_BASELINE（2026-年7月均值，固化参考，非实时；真实 30 日历史待 fetch_commodity_ext 落地后替换）
- 映射表：各大宗品映射 3-5 只 A 股弹性标的（含业务占比）
- 输出：data/COMMODITY_ELASTICITY.js（前端 window.COMMODITY_ELASTICITY）

【数据真实性铁律（2026-08-14 升级）】
- 仅 gold/silver/copper/oil 有真实实时价（来自 MACRO_DATA，带 date）。
- 铝/锂/纯碱/磷化工/维生素/稀土 **当前无任何实时数据源**（metal_price_history.json 不存在、
  fetch_commodity_ext 未落地），一律标 available=false + 原因，绝不编造现价或偏离度。
- 偏离度基准用 7 月均值"参考值"，明确标注 baseline_label，不伪装成实时 30 日信号。
- 没有就是没有，写清楚原因即可，绝不弄虚作假。
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

# ═══════════════ A 股弹性标的映射表 ═══════════════
# 每只标的含: code/name/business_pct(主营业务占比)/note
# business_pct 用于计算"理论弹性系数"：商品涨 X% × business_pct = EPS 弹性
ELASTICITY_MAP = {
    "gold": {  # 黄金 COMEX（$/oz）
        "name": "黄金",
        "unit": "$/oz",
        "stocks": [
            {"code": "600547", "name": "山东黄金", "business_pct": 0.85, "note": "纯金矿龙头"},
            {"code": "600489", "name": "中金黄金", "business_pct": 0.75, "note": "央企金矿"},
            {"code": "600988", "name": "赤峰黄金", "business_pct": 0.90, "note": "高弹性纯金"},
            {"code": "000975", "name": "银泰黄金", "business_pct": 0.55, "note": "金+银双驱"},
            {"code": "601899", "name": "紫金矿业", "business_pct": 0.30, "note": "金+铜综合"},
        ],
    },
    "silver": {  # 白银 COMEX（$/oz）
        "name": "白银",
        "unit": "$/oz",
        "stocks": [
            {"code": "000975", "name": "银泰黄金", "business_pct": 0.30, "note": "银副业但量大"},
            {"code": "000426", "name": "兴业银锡", "business_pct": 0.25, "note": "银锡矿为主"},
            {"code": "000603", "name": "盛达资源", "business_pct": 0.35, "note": "银+铅锌"},
            {"code": "601020", "name": "华钰矿业", "business_pct": 0.40, "note": "锑银矿"},
        ],
    },
    "copper": {  # 铜 LME（$/吨）
        "name": "铜",
        "unit": "$/吨",
        "stocks": [
            {"code": "601899", "name": "紫金矿业", "business_pct": 0.30, "note": "全球铜矿巨头"},
            {"code": "603993", "name": "洛阳钼业", "business_pct": 0.40, "note": "刚果（金）铜钴"},
            {"code": "600362", "name": "江西铜业", "business_pct": 0.65, "note": "国内冶炼龙头"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.35, "note": "铜+铅锌"},
            {"code": "000630", "name": "铜陵有色", "business_pct": 0.75, "note": "纯铜冶炼"},
        ],
    },
    "aluminum": {  # 铝 LME（$/吨）— 暂无实时数据源
        "name": "铝",
        "unit": "$/吨",
        "stocks": [
            {"code": "601600", "name": "中国铝业", "business_pct": 0.85, "note": "央企电解铝龙头"},
            {"code": "000807", "name": "云铝股份", "business_pct": 0.90, "note": "水电铝低碳"},
            {"code": "000933", "name": "神火股份", "business_pct": 0.65, "note": "煤电铝一体"},
            {"code": "600219", "name": "南山铝业", "business_pct": 0.55, "note": "高端铝加工"},
        ],
    },
    "lithium": {  # 碳酸锂（元/吨）— 暂无实时数据源
        "name": "锂",
        "unit": "万元/吨",
        "stocks": [
            {"code": "002466", "name": "天齐锂业", "business_pct": 0.75, "note": "锂矿+锂盐"},
            {"code": "002460", "name": "赣锋锂业", "business_pct": 0.80, "note": "全产业链"},
            {"code": "000792", "name": "盐湖股份", "business_pct": 0.55, "note": "盐湖提锂"},
            {"code": "000408", "name": "藏格矿业", "business_pct": 0.45, "note": "钾锂双驱"},
        ],
    },
    "oil": {  # 原油 WTI（$/bbl）
        "name": "原油",
        "unit": "$/bbl",
        "stocks": [
            {"code": "601857", "name": "中国石油", "business_pct": 0.70, "note": "上游勘探主"},
            {"code": "600028", "name": "中国石化", "business_pct": 0.55, "note": "炼化一体"},
            {"code": "600938", "name": "中国海油", "business_pct": 0.85, "note": "海上油气龙头"},
            {"code": "002353", "name": "杰瑞股份", "business_pct": 0.35, "note": "油服设备弹性"},
        ],
    },
    "soda_ash": {  # 纯碱（元/吨）— 暂无实时数据源
        "name": "纯碱",
        "unit": "元/吨",
        "stocks": [
            {"code": "000683", "name": "远兴能源", "business_pct": 0.85, "note": "天然碱低成本"},
            {"code": "000822", "name": "山东海化", "business_pct": 0.75, "note": "纯碱+小苏打"},
            {"code": "000707", "name": "双环科技", "business_pct": 0.90, "note": "联碱法"},
        ],
    },
    "phosphate": {  # 磷化工 — 暂无实时数据源
        "name": "磷化工",
        "unit": "景气指数",
        "stocks": [
            {"code": "600096", "name": "云天化", "business_pct": 0.65, "note": "磷矿+化肥"},
            {"code": "600141", "name": "兴发集团", "business_pct": 0.70, "note": "磷矿+草甘膦"},
            {"code": "002312", "name": "川发龙蟒", "business_pct": 0.55, "note": "磷化工+锂"},
        ],
    },
    "vitamin": {  # 维生素 — 暂无实时数据源
        "name": "维生素",
        "unit": "景气指数",
        "stocks": [
            {"code": "002001", "name": "新和成", "business_pct": 0.70, "note": "VE/VA 龙头"},
            {"code": "600216", "name": "浙江医药", "business_pct": 0.55, "note": "VE 主流"},
            {"code": "600299", "name": "安迪苏", "business_pct": 0.50, "note": "蛋氨酸+VA"},
        ],
    },
    "rare_earth": {  # 稀土 — 暂无实时数据源
        "name": "稀土",
        "unit": "景气指数",
        "stocks": [
            {"code": "600111", "name": "北方稀土", "business_pct": 0.90, "note": "轻稀土龙头"},
            {"code": "000831", "name": "中国稀土", "business_pct": 0.85, "note": "中重稀土"},
            {"code": "600392", "name": "盛和资源", "business_pct": 0.70, "note": "稀土+锆"},
        ],
    },
}

# ═══════════════ 真实实时价来源（仅这些有数据） ═══════════════
# MACRO_DATA.global_macro.commodities 实际仅含 gold/silver/copper/oil 四项真实价。
REAL_PRICE_KEYS = ["gold", "silver", "copper", "oil"]

# 30 日参考基准 = 2026 年 7 月均值（固化值，非实时历史；
# 真实 30 日序列待 fetch_commodity_ext / metal_price_history.json 落地后替换）。
# 明确标注 baseline_label，绝不伪装成实时信号。
REFERENCE_BASELINE = {
    "gold":   4250.0,
    "silver":   58.5,
    "copper":  620.0,
    "oil":      78.5,
}
BASELINE_LABEL = "7月均值(参考,非实时)"

# 无实时数据源的大宗品（待 fetch_commodity_ext 落地后接入）。
# 一律标 available=false，绝不编造现价/偏离度。
UNAVAILABLE_COMMODITIES = {
    "aluminum":   "铝",
    "lithium":    "锂(碳酸锂)",
    "soda_ash":   "纯碱",
    "phosphate":  "磷化工",
    "vitamin":    "维生素",
    "rare_earth": "稀土",
}

# 涨价阈值（偏离度 > X% 视为"涨价窗口"）
HOT_THRESHOLD_PCT = 3.0
# 弹性杠杆简化假设（仅用于有真实价的商品做理论 EPS 弹性估算）
ELASTICITY_LEVERAGE = 1.5


def load_macro_data():
    """读取 data/MACRO_DATA.js"""
    path = os.path.join(DATA, "MACRO_DATA.js")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if text.startswith("window.MACRO_DATA"):
        text = text.split("=", 1)[1]
    text = text.rstrip(";\n ")
    try:
        return json.loads(text)
    except Exception as e:
        print(f"[warn] MACRO_DATA 解析失败: {e}")
        return {}


def calc_one_commodity(key, info, current_price, price_date):
    """计算单个商品的弹性榜（传入真实现价；无现价返回 None 由调用方标 unavailable）"""
    baseline = REFERENCE_BASELINE.get(key)
    # 偏离度 = (现价 - 参考基准) / 参考基准 × 100（基准已标注为非实时参考）
    dev_pct = (current_price - baseline) / baseline * 100 if baseline else 0.0
    is_hot = dev_pct >= HOT_THRESHOLD_PCT

    # 每只 A 股标的的理论弹性 = 偏离度 × business_pct × 杠杆
    rows = []
    for stk in info["stocks"]:
        elasticity = dev_pct * stk["business_pct"] * ELASTICITY_LEVERAGE
        rows.append({
            "code": stk["code"],
            "name": stk["name"],
            "business_pct": stk["business_pct"],
            "elasticity_pct": round(elasticity, 2),
            "note": stk["note"],
        })
    rows.sort(key=lambda x: x["elasticity_pct"], reverse=True)

    return {
        "key": key,
        "name": info["name"],
        "unit": info["unit"],
        "available": True,
        "current_price": round(current_price, 3),
        "price_date": price_date or "",
        "baseline_30d": baseline,
        "baseline_label": BASELINE_LABEL,
        "dev_pct": round(dev_pct, 2),
        "is_hot": is_hot,
        "hot_basis": "参考基准=7月均值(非实时)",
        "stocks": rows,
    }


def main():
    md = load_macro_data()
    commodities = md.get("global_macro", {}).get("commodities", {})

    items = []
    hot_count = 0
    for key in REAL_PRICE_KEYS:
        if key not in ELASTICITY_MAP:
            continue
        info = ELASTICITY_MAP[key]
        c = commodities.get(key, {})
        price = c.get("value")
        pdate = c.get("date", "")
        if price is None or price <= 0:
            # 真实数据源缺价：标 unavailable，绝不编造
            continue
        row = calc_one_commodity(key, info, price, pdate)
        items.append(row)
        if row["is_hot"]:
            hot_count += 1

    # 按"热度"降序（涨价窗口优先）
    items.sort(key=lambda x: (x["is_hot"], x["dev_pct"]), reverse=True)

    # 无实时数据源的大宗品：透明列出，绝不造假
    unavailable = []
    for key, label in UNAVAILABLE_COMMODITIES.items():
        info = ELASTICITY_MAP.get(key, {})
        unavailable.append({
            "key": key,
            "name": label,
            "available": False,
            "reason": "无实时数据源（metal_price_history.json 不存在 / fetch_commodity_ext 未落地），待接入后显示",
            "stocks": info.get("stocks", []),
        })

    total_commodities = len(items) + len(unavailable)
    unavailable_names = "、".join(u["name"] for u in unavailable)

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": commodities.get("gold", {}).get("date", ""),
        "source": "MACRO_DATA.global_macro.commodities(实时价 gold/silver/copper/oil)",
        "hot_count": hot_count,
        "available_count": len(items),
        "total_commodities": total_commodities,
        "hot_threshold_pct": HOT_THRESHOLD_PCT,
        "commodities": items,
        "unavailable": unavailable,
        "note": (
            f"涨价窗口：有实时价的商品相对 7 月均值参考基准涨幅 ≥ {HOT_THRESHOLD_PCT}%。"
            f"弹性系数 = 偏离度 × 业务占比 × 杠杆 {ELASTICITY_LEVERAGE}（简化估算）。"
            f"⚠️ 数据真实性：仅 gold/silver/copper/oil 有真实实时价（来自 MACRO_DATA，带日期）；"
            f"铝、锂、纯碱、磷化工、维生素、稀土 共 6 项暂无实时数据源，已标「未接入」，不显示假信号。"
            f"30 日基准目前为 7 月均值参考值（非实时），待 fetch_commodity_ext 落地后替换为真实历史。"
        ),
    }

    # 写入 data/COMMODITY_ELASTICITY.js
    out_path = os.path.join(DATA, "COMMODITY_ELASTICITY.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.COMMODITY_ELASTICITY = {json.dumps(result, ensure_ascii=False)};\n")
    print(f"[ok] {out_path}  实时价商品: {len(items)}/{total_commodities}  涨价窗口: {hot_count}  未接入: {unavailable_names}")

    # 同步写 raw_data
    raw_path = os.path.join(RAW, "commodity_elasticity.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
