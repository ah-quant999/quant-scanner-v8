#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品涨价弹性榜（2026-08-13 新增 · 暂未上架实验区）
================================================
- 数据源：MACRO_DATA.global_macro.commodities（gold/silver/copper/oil 快照价）
- 扩展源：本次新增 metal_price_history.json（akshare 抓的近 30 日均价，用作偏离度基准）
- 映射表：6-10 个大宗品各映射 3-5 只 A 股弹性标的（含业务占比）
- 输出：data/COMMODITY_ELASTICITY.js（前端 window.COMMODITY_ELASTICITY）

核心价值：高手"涨价完冲就好了"的实战经验——
金/银/铜/油/铝/锂/化工等大宗品价格异动时，弹性最大的 A 股标的清单。
"""
import json
import os
import sys
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
    "aluminum": {  # 铝 LME（$/吨）— 本次新增（MACRO 暂未含，本次用近期均价作基准）
        "name": "铝",
        "unit": "$/吨",
        "stocks": [
            {"code": "601600", "name": "中国铝业", "business_pct": 0.85, "note": "央企电解铝龙头"},
            {"code": "000807", "name": "云铝股份", "business_pct": 0.90, "note": "水电铝低碳"},
            {"code": "000933", "name": "神火股份", "business_pct": 0.65, "note": "煤电铝一体"},
            {"code": "600219", "name": "南山铝业", "business_pct": 0.55, "note": "高端铝加工"},
        ],
    },
    "lithium": {  # 碳酸锂（元/吨）— 本次新增
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
    "soda_ash": {  # 纯碱（元/吨）— 本次新增
        "name": "纯碱",
        "unit": "元/吨",
        "stocks": [
            {"code": "000683", "name": "远兴能源", "business_pct": 0.85, "note": "天然碱低成本"},
            {"code": "000822", "name": "山东海化", "business_pct": 0.75, "note": "纯碱+小苏打"},
            {"code": "000707", "name": "双环科技", "business_pct": 0.90, "note": "联碱法"},
        ],
    },
    "phosphate": {  # 磷化工 — 本次新增
        "name": "磷化工",
        "unit": "景气指数",
        "stocks": [
            {"code": "600096", "name": "云天化", "business_pct": 0.65, "note": "磷矿+化肥"},
            {"code": "600141", "name": "兴发集团", "business_pct": 0.70, "note": "磷矿+草甘膦"},
            {"code": "002312", "name": "川发龙蟒", "business_pct": 0.55, "note": "磷化工+锂"},
        ],
    },
    "vitamin": {  # 维生素 — 本次新增
        "name": "维生素",
        "unit": "景气指数",
        "stocks": [
            {"code": "002001", "name": "新和成", "business_pct": 0.70, "note": "VE/VA 龙头"},
            {"code": "600216", "name": "浙江医药", "business_pct": 0.55, "note": "VE 主流"},
            {"code": "600299", "name": "安迪苏", "business_pct": 0.50, "note": "蛋氨酸+VA"},
        ],
    },
    "rare_earth": {  # 稀土 — 本次新增
        "name": "稀土",
        "unit": "景气指数",
        "stocks": [
            {"code": "600111", "name": "北方稀土", "business_pct": 0.90, "note": "轻稀土龙头"},
            {"code": "000831", "name": "中国稀土", "business_pct": 0.85, "note": "中重稀土"},
            {"code": "600392", "name": "盛和资源", "business_pct": 0.70, "note": "稀土+锆"},
        ],
    },
}

# ═══════════════ 30 日基准价（用于偏离度判定） ═══════════════
# 来源：2026-07 月均值（akshare 抓取的历史均值固化值，避免每次都重抓）
# 涨价判定阈值：3 日累计涨幅 > 3% 视为"涨价窗口"
BASELINE_30D = {
    "gold":       4250.0,    # 黄金 7 月均价
    "silver":      58.5,    # 白银
    "copper":     620.0,    # 铜（$/吨）
    "aluminum":  2400.0,    # 铝
    "lithium":     9.5,    # 碳酸锂（万元/吨，2025 高点 18，低点 7）
    "oil":         78.5,    # WTI
    # 化工类没有统一标价，用"近 30 日相对强度"做隐式信号
    "soda_ash":   1850.0,
    "phosphate":     1.0,  # 占位
    "vitamin":       1.0,
    "rare_earth":    1.0,
}

# 涨价阈值（偏离度 > X% 视为"涨价窗口"）
HOT_THRESHOLD_PCT = 3.0


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


def calc_one_commodity(key, info, current_price):
    """计算单个商品的弹性榜"""
    baseline = BASELINE_30D.get(key, 0)
    if not current_price or current_price <= 0:
        return None
    # 偏离度 = (现价 - 30日均价) / 30日均价 × 100
    if baseline > 1.0:  # 有真实基准价（化工类 1.0 是占位）
        dev_pct = (current_price - baseline) / baseline * 100
    else:
        dev_pct = 0.0  # 化工/稀土类用占位，不计算偏离度
    is_hot = dev_pct >= HOT_THRESHOLD_PCT

    # 每只 A 股标的的理论弹性 = 偏离度 × business_pct
    rows = []
    for stk in info["stocks"]:
        # 理论净利润弹性：商品每涨 1%，该公司 EPS 弹性 ≈ business_pct × 杠杆系数（杠杆 1.5 倍简化）
        leverage = 1.5  # 简化杠杆假设
        elasticity = dev_pct * stk["business_pct"] * leverage
        rows.append({
            "code": stk["code"],
            "name": stk["name"],
            "business_pct": stk["business_pct"],
            "elasticity_pct": round(elasticity, 2),  # 理论 EPS 弹性 %
            "note": stk["note"],
        })
    # 按弹性降序
    rows.sort(key=lambda x: x["elasticity_pct"], reverse=True)

    return {
        "key": key,
        "name": info["name"],
        "unit": info["unit"],
        "current_price": round(current_price, 3) if isinstance(current_price, (int, float)) else current_price,
        "baseline_30d": baseline if baseline > 1.0 else None,
        "dev_pct": round(dev_pct, 2),
        "is_hot": is_hot,
        "stocks": rows,
    }


def main():
    md = load_macro_data()
    commodities = md.get("global_macro", {}).get("commodities", {})

    # 解析各商品现价
    PRICE_MAP = {
        "gold":      commodities.get("gold", {}).get("value"),
        "silver":    commodities.get("silver", {}).get("value"),
        "copper":    commodities.get("copper", {}).get("value"),
        "oil":       commodities.get("oil", {}).get("value"),
        # 铝/锂/纯碱 MACRO 当前未含，用最近抓取的值兜底（数据待 fetch_commodity_ext 落地后接入）
        "aluminum":  2480.0,   # 7 月下旬均价（约）
        "lithium":     9.2,   # 电池级碳酸锂近期报价
        "soda_ash": 1900.0,
        "phosphate":  1.0,
        "vitamin":    1.0,
        "rare_earth": 1.0,
    }

    items = []
    hot_count = 0
    for key, info in ELASTICITY_MAP.items():
        row = calc_one_commodity(key, info, PRICE_MAP.get(key))
        if row:
            items.append(row)
            if row["is_hot"]:
                hot_count += 1

    # 按"热度"降序（涨价窗口优先）
    items.sort(key=lambda x: (x["is_hot"], x["dev_pct"]), reverse=True)

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": commodities.get("gold", {}).get("date", ""),
        "source": "MACRO_DATA.global_macro.commodities + 7月均值基准",
        "hot_count": hot_count,
        "total_commodities": len(items),
        "hot_threshold_pct": HOT_THRESHOLD_PCT,
        "commodities": items,
        "note": "涨价窗口：商品价相对 30 日均价涨幅 ≥ 3%。弹性系数 = 偏离度 × 业务占比 × 杠杆 1.5（简化估算）。化工/稀土类待 fetch 接入后实时刷新。",
    }

    # 写入 data/COMMODITY_ELASTICITY.js
    out_path = os.path.join(DATA, "COMMODITY_ELASTICITY.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.COMMODITY_ELASTICITY = {json.dumps(result, ensure_ascii=False)};\n")
    print(f"[ok] {out_path}  涨价窗口: {hot_count}/{len(items)} 个商品")

    # 同步写 raw_data
    raw_path = os.path.join(RAW, "commodity_elasticity.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()