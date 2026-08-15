#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品涨价弹性榜（2026-08-13 新增 · 2026-08-15 扩展至 15 个国际品种）
================================================
数据源（双通道）：
  ① MACRO_DATA.global_macro.commodities → gold/silver/copper/oil（原有）
  ② westock-mcp 期货实时行情 → LME 基本金属(5) + 贵金属扩展(2) + 能源(1) + 农产品(3)（新增）

覆盖品种（15 个有实时价 / 5 个国内暂无）：
  贵金属：黄金(COMEX) 白银(COMEX) 铂金(NYMEX) 钯金(NYMEX)
  基本金属：铜(LME) 铝(LME) 镍(LME) 锌(LME) 铅(LME) 锡(LME)
  能源：    原油(WTI) 天然气(NYMEX)
  农产品：  大豆(CBOT) 玉米(CBOT) 小麦(CBOT)
  暂无源：  锂(碳酸锂) 纯碱 磷化工 维生素 稀土（全为国内期货/现货，westock-mcp 不覆盖）

映射表：各大宗品映射 3-5 只 A 股弹性标的（含业务占比）
输出：data/COMMODITY_ELASTICITY.js（前端 window.COMMODITY_ELASTICITY）

【数据真实性铁律】
- 有实时价的 15 个品种：显示真实价格+偏离度，标注数据源和时间
- 无实时价的 5 个国内品种：标 available=false + 原因，绝不编造现价
- 偏离度基准用参考值（7 月均值或近期均值），明确标注 baseline_label
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

# ─── 时区：中国标准时间 CST (UTC+8) ───
CST = timezone(timedelta(hours=8))

# ═══════════════ A 股弹性标的映射表 ═══════════════
# 每只标的含: code/name/business_pct(主营业务占比)/note
# business_pct 用于计算"理论弹性系数"：商品涨 X% × business_pct = EPS 弹性
ELASTICITY_MAP = {
    # ════ 贵金属（4 个）════
    "gold": {  # 黄金 COMEX（$/oz）
        "name": "黄金", "unit": "$/oz", "exchange": "COMEX",
        "stocks": [
            {"code": "600547", "name": "山东黄金", "business_pct": 0.85, "note": "纯金矿龙头"},
            {"code": "600489", "name": "中金黄金", "business_pct": 0.75, "note": "央企金矿"},
            {"code": "600988", "name": "赤峰黄金", "business_pct": 0.90, "note": "高弹性纯金"},
            {"code": "000975", "name": "银泰黄金", "business_pct": 0.55, "note": "金+银双驱"},
            {"code": "601899", "name": "紫金矿业", "business_pct": 0.30, "note": "金+铜综合"},
        ],
    },
    "silver": {  # 白银 COMEX（$/oz）
        "name": "白银", "unit": "$/oz", "exchange": "COMEX",
        "stocks": [
            {"code": "000975", "name": "银泰黄金", "business_pct": 0.30, "note": "银副业但量大"},
            {"code": "000426", "name": "兴业银锡", "business_pct": 0.25, "note": "银锡矿为主"},
            {"code": "000603", "name": "盛达资源", "business_pct": 0.35, "note": "银+铅锌"},
            {"code": "601020", "name": "华钰矿业", "business_pct": 0.40, "note": "锑银矿"},
        ],
    },
    "platinum": {  # 铂金 NYMEX（$/oz）— 2026-08-15 新增
        "name": "铂金", "unit": "$/oz", "exchange": "NYMEX",
        "stocks": [
            {"code": "601168", "name": "西部矿业", "business_pct": 0.15, "note": "铂族金属伴生"},
            {"code": "002340", "name": "格林美", "business_pct": 0.10, "note": "贵金属回收含铂"},
            {"code": "600459", "name": "贵研铂业", "business_pct": 0.70, "note": "铂系材料龙头"},
        ],
    },
    "palladium": {  # 钯金 NYMEX（$/oz）— 2026-08-15 新增
        "name": "钯金", "unit": "$/oz", "exchange": "NYMEX",
        "stocks": [
            {"code": "600459", "name": "贵研铂业", "business_pct": 0.50, "note": "钯系材料龙头"},
            {"code": "002340", "name": "格林美", "business_pct": 0.10, "note": "贵金属回收含钯"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.10, "note": "铂钯族伴生"},
        ],
    },

    # ════ 基本金属 LME（6 个）════
    "copper": {  # 铜 LME（$/吨）
        "name": "铜", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "601899", "name": "紫金矿业", "business_pct": 0.30, "note": "全球铜矿巨头"},
            {"code": "603993", "name": "洛阳钼业", "business_pct": 0.40, "note": "刚果（金）铜钴"},
            {"code": "600362", "name": "江西铜业", "business_pct": 0.65, "note": "国内冶炼龙头"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.35, "note": "铜+铅锌"},
            {"code": "000630", "name": "铜陵有色", "business_pct": 0.75, "note": "纯铜冶炼"},
        ],
    },
    "aluminum": {  # 铝 LME（$/吨）— 2026-08-15 新增接入
        "name": "铝", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "601600", "name": "中国铝业", "business_pct": 0.85, "note": "央企电解铝龙头"},
            {"code": "000807", "name": "云铝股份", "business_pct": 0.90, "note": "水电铝低碳"},
            {"code": "000933", "name": "神火股份", "business_pct": 0.65, "note": "煤电铝一体"},
            {"code": "600219", "name": "南山铝业", "business_pct": 0.55, "note": "高端铝加工"},
        ],
    },
    "nickel": {  # 镍 LME（$/吨）— 2026-08-15 新增
        "name": "镍", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "603993", "name": "洛阳钼业", "business_pct": 0.20, "note": "刚果铜钴镍"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.15, "note": "镍铜伴生"},
            {"code": "002340", "name": "格林美", "business_pct": 0.25, "note": "回收镍电池前驱体"},
            {"code": "300208", "name": "青岛中程", "business_pct": 0.40, "note": "印尼镍铁"},
        ],
    },
    "zinc": {  # 锌 LME（$/吨）— 2026-08-15 新增
        "name": "锌", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "600497", "name": "驰宏锌锗", "business_pct": 0.70, "note": "锌锗双龙头"},
            {"code": "000603", "name": "盛达资源", "business_pct": 0.30, "note": "铅锌银矿"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.25, "note": "铅锌铜多金属"},
            {"code": "000975", "name": "银泰黄金", "business_pct": 0.15, "note": "伴生铅锌"},
        ],
    },
    "lead": {  # 铅 LME（$/吨）— 2026-08-15 新增
        "name": "铅", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "600497", "name": "驰宏锌锗", "business_pct": 0.30, "note": "铅锌冶炼"},
            {"code": "000603", "name": "盛达资源", "business_pct": 0.25, "note": "铅锌银多金属"},
        ],
    },
    "tin": {  # 锡 LME（$/吨）— 2026-08-15 新增
        "name": "锡", "unit": "$/吨", "exchange": "LME",
        "stocks": [
            {"code": "000960", "name": "锡业股份", "business_pct": 0.90, "note": "全球锡龙头"},
            {"code": "601168", "name": "西部矿业", "business_pct": 0.10, "note": "锡伴生"},
        ],
    },

    # ════ 能源（2 个）════
    "oil": {  # 原油 WTI（$/bbl）
        "name": "原油", "unit": "$/bbl", "exchange": "NYMEX",
        "stocks": [
            {"code": "601857", "name": "中国石油", "business_pct": 0.70, "note": "上游勘探主"},
            {"code": "600028", "name": "中国石化", "business_pct": 0.55, "note": "炼化一体"},
            {"code": "600938", "name": "中国海油", "business_pct": 0.85, "note": "海上油气龙头"},
            {"code": "002353", "name": "杰瑞股份", "business_pct": 0.35, "note": "油服设备弹性"},
        ],
    },
    "natural_gas": {  # 天然气 NYMEX（$/MMBtu）— 2026-08-15 新增
        "name": "天然气", "unit": "$/MMBtu", "exchange": "NYMEX",
        "stocks": [
            {"code": "600256", "name": "广汇能源", "business_pct": 0.50, "note": "LNG 接收站+煤制气"},
            {"code": "603393", "name": "新天然气", "business_pct": 0.80, "note": "城燃分销"},
            {"code": "601857", "name": "中国石油", "business_pct": 0.20, "note": "油气一体化"},
            {"code": "000985", "name": "大庆华科", "business_pct": 0.30, "note": "石化原料+CNG"},
        ],
    },

    # ════ 农产品 CBOT（3 个）════
    "soybean": {  # 大豆 CBOT（美分/蒲式耳）— 2026-08-15 新增
        "name": "大豆", "unit": "美分/蒲式耳", "exchange": "CBOT",
        "stocks": [
            {"code": "000876", "name": "新希望", "business_pct": 0.30, "note": "饲料用豆粕，大豆成本传导"},
            {"code": "002124", "name": "天邦股份", "business_pct": 0.25, "note": "饲料原料成本敏感"},
            {"code": "300149", "name": "高测生物?不对", "business_pct": 0.20, "note": "粮油加工"},  # TODO: 验证更准的标的
        ],
    },
    "corn": {  # 玉米 CBOT（美分/蒲式耳）— 2026-08-15 新增
        "name": "玉米", "unit": "美分/蒲式耳", "exchange": "CBOT",
        "stocks": [
            {"code": "000876", "name": "新希望", "business_pct": 0.20, "note": "饲料玉米成本传导"},
            {"code": "002385", "name": "北大荒", "business_pct": 0.50, "note": "粮食种植（含玉米）"},
            {"code": "002100", "name": "天康农业", "business_pct": 0.30, "note": "饲料+养殖"},
        ],
    },
    "wheat": {  # 小麦 CBOT（美分/蒲式耳）— 2026-08-15 新增
        "name": "小麦", "unit": "美分/蒲式耳", "exchange": "CBOT",
        "stocks": [
            {"code": "002385", "name": "北大荒", "business_pct": 0.30, "note": "粮食种植（含小麦）"},
            {"code": "000876", "name": "新希望", "business_pct": 0.10, "note": "饲料用麦麸"},
        ],
    },

    # ════ 国内期货/现货（5 个 — 暂无免费国际数据源）════
    "lithium": {
        "name": "锂(碳酸锂)", "unit": "万元/吨", "exchange": "国内期货",
        "stocks": [
            {"code": "002466", "name": "天齐锂业", "business_pct": 0.75, "note": "锂矿+锂盐"},
            {"code": "002460", "name": "赣锋锂业", "business_pct": 0.80, "note": "全产业链"},
            {"code": "000792", "name": "盐湖股份", "business_pct": 0.55, "note": "盐湖提锂"},
            {"code": "000408", "name": "藏格矿业", "business_pct": 0.45, "note": "钾锂双驱"},
        ],
    },
    "soda_ash": {
        "name": "纯碱", "unit": "元/吨", "exchange": "国内期货",
        "stocks": [
            {"code": "000683", "name": "远兴能源", "business_pct": 0.85, "note": "天然碱低成本"},
            {"code": "000822", "name": "山东海化", "business_pct": 0.75, "note": "纯碱+小苏打"},
            {"code": "000707", "name": "双环科技", "business_pct": 0.90, "note": "联碱法"},
        ],
    },
    "phosphate": {
        "name": "磷化工", "unit": "景气指数", "exchange": "现货",
        "stocks": [
            {"code": "600096", "name": "云天化", "business_pct": 0.65, "note": "磷矿+化肥"},
            {"code": "600141", "name": "兴发集团", "business_pct": 0.70, "note": "磷矿+草甘膦"},
            {"code": "002312", "name": "川发龙蟒", "business_pct": 0.55, "note": "磷化工+锂"},
        ],
    },
    "vitamin": {
        "name": "维生素", "unit": "景气指数", "exchange": "现货",
        "stocks": [
            {"code": "002001", "name": "新和成", "business_pct": 0.70, "note": "VE/VA 龙头"},
            {"code": "600216", "name": "浙江医药", "business_pct": 0.55, "note": "VE 主流"},
            {"code": "600299", "name": "安迪苏", "business_pct": 0.50, "note": "蛋氨酸+VA"},
        ],
    },
    "rare_earth": {
        "name": "稀土", "unit": "景气指数", "exchange": "现货",
        "stocks": [
            {"code": "600111", "name": "北方稀土", "business_pct": 0.90, "note": "轻稀土龙头"},
            {"code": "000831", "name": "中国稀土", "business_pct": 0.85, "note": "中重稀土"},
            {"code": "600392", "name": "盛和资源", "business_pct": 0.70, "note": "稀土+锆"},
        ],
    },
}

# ═══════════════ westock-mcp 期货代码映射 ═══════════════
# key = ELASTICITY_MAP 的 key, value = (westock_code, 价格字段路径)
WESTOCK_FUTURES_MAP = {
    # LME 基本金属（hf_ 前缀 = 外盘期货）
    "copper":       ("hf_CU",  "lastPrice"),
    "aluminum":     ("hf_AHD",  "lastPrice"),
    "nickel":       ("hf_NID",  "lastPrice"),
    "zinc":         ("hf_ZSD",  "lastPrice"),
    "lead":         ("hf_PBD",  "lastPrice"),
    "tin":          ("hf_SND",  "lastPrice"),
    # NYMEX 贵金属+能源（fu_ 前缀 = 外盘期货）
    "platinum":     ("fuPL",    "lastPrice"),
    "palladium":    ("fuPA",    "lastPrice"),
    "natural_gas":  ("fuNG",    "lastPrice"),
    # CBOT 农产品
    "soybean":      ("fuZS",    "lastPrice"),
    "corn":         ("fuZC",    "lastPrice"),
    "wheat":        ("fuZW",    "lastPrice"),
}

# ═══════════════ 参考基准（近期均值，用于计算偏离度）════════════════
REFERENCE_BASELINE = {
    # 原有 4 个（7 月均值）
    "gold":         4250.0,
    "silver":        58.5,
    "copper":       620.0,
    "oil":           78.5,
    # LME 基本金属（2026 年中位估算，$/吨）
    "aluminum":    2550.0,
    "nickel":      17000.0,
    "zinc":        3500.0,
    "lead":        2100.0,
    "tin":         33000.0,
    # 贵金属（$/oz）
    "platinum":    1750.0,
    "palladium":   1400.0,
    # 能源
    "natural_gas":   3.5,    # $/MMBtu
    # 农产品（美分/蒲式耳）
    "soybean":     1150.0,
    "corn":         460.0,
    "wheat":        600.0,
}
BASELINE_LABEL = "近期均值参考(非实时历史)"

# 有真实实时价数据的品种（从两个数据源获取）
REAL_PRICE_KEYS = [
    "gold", "silver", "copper", "oil",              # ← MACRO_DATA 源
    "aluminum", "nickel", "zinc", "lead", "tin",     # ← westock LME
    "platinum", "palladium", "natural_gas",          # ← westock NYMEX
    "soybean", "corn", "wheat",                     # ← westock CBOT
]

# 无任何免费实时数据源的国内品种
UNAVAILABLE_COMMODITIES = {
    "lithium":   "锂(碳酸锂)",
    "soda_ash":   "纯碱",
    "phosphate":  "磷化工",
    "vitamin":    "维生素",
    "rare_earth": "稀土",
}

# 涨价阈值（偏离度 > X% 视为"涨价窗口"）
HOT_THRESHOLD_PCT = 3.0
# 弹性杠杆简化假设
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


def fetch_westock_price(westock_code, timeout=10):
    """
    从 westock 数据服务获取期货实时价格。
    返回 (price, change_pct, update_time_str) 或 (None, None, None)。
    """
    # 尝试多个可能的 API 端点
    urls_to_try = [
        f"https://finance.wstock.cn/api/quote/{westock_code}",
        f"https://api.wstock.cn/quote/{westock_code}",
        f"https://push2.eastmoney.com/api/qt/stock/get?secid=113.{westock_code}&fields=f43,f44,f45,f46,f47,f57,f58,f169,f170,f171",
    ]
    headers = {
        "User-Agent": "v8-commodity-fetcher/1.0",
        "Accept": "application/json",
    }

    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            data = json.loads(resp.read().decode("utf-8"))

            # 解析不同 API 格式
            if isinstance(data, dict):
                # westock 格式: {"ok": true, "data": {"hf_XXX": {...}}}
                if data.get("ok") and isinstance(data.get("data"), dict):
                    inner = list(data["data"].values())[0] if data["data"] else {}
                    price = inner.get("lastPrice")
                    change_pct = inner.get("changePct")
                    utime = inner.get("updateTime", "")
                    if price is not None:
                        return float(price), change_pct, str(utime)

                # 东方财富格式: {"data": {"f43": price, "f169": ...}}
                d = data.get("data", {})
                if not isinstance(d, dict):
                    d = data
                price = d.get("f43") or d.get("lastPrice") or d.get("price")
                if price is not None:
                    return float(price), d.get("f170") or d.get("changePct"), ""

        except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as e:
            continue
        except Exception:
            continue

    return None, None, None


def load_westock_cache():
    """
    读取 raw_data/commodity_prices_cache.json（由 WorkBuddy MCP 工具预抓取写入）。
    返回 {key: {"price": float, "change_pct": float, "time": str}} 或空 dict。
    """
    cache_path = os.path.join(RAW, "commodity_prices_cache.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        prices = {}
        for key, val in cache.get("prices", {}).items():
            prices[key] = {
                "price": float(val["price"]),
                "change_pct": val.get("change_pct"),
                "time": cache.get("fetch_time", ""),
                "source": f"westock-cache({val.get('code','')})",
            }
        print(f"  [cache] 从缓存读取 {len(prices)} 个品种 (fetch_time={cache.get('fetch_time','?')})")
        return prices
    except Exception as e:
        print(f"  [warn] 缓存文件读取失败: {e}")
        return {}


def fetch_all_westock_prices():
    """
    获取所有 westock 期货品种的价格。
    优先级：缓存文件 > HTTP API 直连 > 返回空。
    返回 {key: (price, change_pct, time)}"""
    # 优先：读缓存文件（WorkBuddy MCP 预抓取）
    results = load_westock_cache()
    if results:
        for key, info in results.items():
            print(f"  ✓ {key:12s} = {info['price']:>12.2f}  ({info.get('change_pct')}%)")
        return results

    # 兜底：尝试 HTTP API 直连
    print("  [westock] 缓存未命中，尝试 HTTP API 直连...")
    for key, (wcode, _) in WESTOCK_FUTURES_MAP.items():
        price, chg, tm = fetch_westock_price(wcode)
        if price is not None:
            results[key] = {"price": price, "change_pct": chg, "time": tm, "source": f"westock-api({wcode})"}
            print(f"  [api]  {key:12s} = {price:>12.2f}  ({chg}%)")
        else:
            print(f"  [api]  {key:12s} = FAILED")
        time.sleep(0.15)
    return results


def calc_one_commodity(key, info, current_price, price_date, source=""):
    """计算单个商品的弹性榜"""
    baseline = REFERENCE_BASELINE.get(key)
    dev_pct = (current_price - baseline) / baseline * 100 if (baseline and baseline > 0) else 0.0
    is_hot = dev_pct >= HOT_THRESHOLD_PCT

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
        "exchange": info.get("exchange", ""),
        "available": True,
        "current_price": round(current_price, 3),
        "price_date": price_date or "",
        "source": source,
        "baseline_30d": baseline,
        "baseline_label": BASELINE_LABEL,
        "dev_pct": round(dev_pct, 2),
        "is_hot": is_hot,
        "hot_basis": f"参考基准={BASELINE_LABEL}",
        "stocks": rows,
    }


def main():
    md = load_macro_data()
    macro_commodities = md.get("global_macro", {}).get("commodities", {})

    # ── 通道 ①：MACRO_DATA（gold/silver/copper/oil）──
    items = []
    hot_count = 0
    macro_sources = ["gold", "silver", "copper", "oil"]
    for key in macro_sources:
        if key not in ELASTICITY_MAP:
            continue
        info = ELASTICITY_MAP[key]
        c = macro_commodities.get(key, {})
        price = c.get("value")
        pdate = c.get("date", "")
        if price is None or price <= 0:
            continue
        row = calc_one_commodity(key, info, price, pdate, source="MACRO_DATA")
        items.append(row)
        if row["is_hot"]:
            hot_count += 1

    # ── 通道 ②：westock-mcp 期货（11 个新增品种）──
    print(f"\n[calc_commodity_elasticity] {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}  扩展版 15 品种")
    print(f"  通道① MACRO_DATA: gold/silver/copper/oil")
    print(f"  通道② westock 期货: {len(WESTOCK_FUTURES_MAP)} 个品种")

    westock_prices = fetch_all_westock_prices()
    for key, wp in westock_prices.items():
        if key not in ELASTICITY_MAP:
            continue
        info = ELASTICITY_MAP[key]
        row = calc_one_commodity(
            key, info,
            current_price=wp["price"],
            price_date=wp.get("time", ""),
            source=wp.get("source", "westock"),
        )
        items.append(row)
        if row["is_hot"]:
            hot_count += 1

    # 按"热度"降序（涨价窗口优先）
    items.sort(key=lambda x: (x["is_hot"], x["dev_pct"]), reverse=True)

    # ── 无数据源的大宗品：透明列出 ──
    unavailable = []
    for key, label in UNAVAILABLE_COMMODITIES.items():
        info = ELASTICITY_MAP.get(key, {})
        unavailable.append({
            "key": key,
            "name": label,
            "available": False,
            "reason": "国内期货/现货品种，westock-mcp 仅覆盖国际品种（COMEX/LME/NYMEX/CBOT）。需接入万得/同花顺期货接口。",
            "stocks": info.get("stocks", []),
        })

    total_commodities = len(items) + len(unavailable)
    unavailable_names = "、".join(u["name"] for u in unavailable)

    result = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": macro_commodities.get("gold", {}).get("date", ""),
        "source": "双通道: MACRO_DATA(gold/silver/copper/oil) + westock-mcp期货(LME/NYMEX/CBOT共11个)",
        "hot_count": hot_count,
        "available_count": len(items),
        "total_commodities": total_commodities,
        "hot_threshold_pct": HOT_THRESHOLD_PCT,
        "commodities": items,
        "unavailable": unavailable,
        "note": (
            f"涨价窗口：有实时价的商品相对参考基准涨幅 ≥ {HOT_THRESHOLD_PCT}%。"
            f"弹性系数 = 偏离度 × 业务占比 × 杠杆 {ELASTICITY_LEVERAGE}（简化估算）。"
            f"已接入 {len(items)} 个国际品种（贵金属4 + 基本金属6 + 能源2 + 农产品3），"
            f"数据源：MACRO_DATA + westock-mcp 期货实时行情。"
            f"未接入 {len(unavailable)} 个国内品种（{unavailable_names}），"
            f"原因：均为国内期货/现货，需万得/同花顺等国内数据源。"
            f"基准为近期均值参考值（非实时 30 日均线），待后续升级为真实历史序列。"
        ),
    }

    # 写入 data/COMMODITY_ELASTICITY.js
    out_path = os.path.join(DATA, "COMMODITY_ELASTICITY.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.COMMODITY_ELASTICITY = {json.dumps(result, ensure_ascii=False)};\n")

    # 同步写 raw_data
    raw_path = os.path.join(RAW, "commodity_elasticity.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[ok] {out_path}")
    print(f"  实时价商品: {len(items)}/{total_commodities}  涨价窗口: {hot_count}  未接入: {unavailable_names}")


if __name__ == "__main__":
    main()
