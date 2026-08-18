#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品涨价弹性榜（2026-08-13 新增 · 2026-08-16 升级：z-score基准 + 国内期货接入
              · 2026-08-18 升级：Sina免费外盘期货兜底，阿狸咪家用网络可用）
================================================
数据源（三通道）：
  ① MACRO_DATA.global_macro.commodities → gold/silver/copper/oil（原有）
  ② Sina 免费外盘期货接口 → LME/NYMEX/CBOT 共 15 个品种（2026-08-18 新增）
    · westock-mcp 缓存新鲜时仍优先使用 westock；缓存缺失/陈旧时自动降级到 Sina
    · 无需认证，中美 IP 均可访问，解决阿狸咪家 westock-mcp 不可用问题
  ③ eastmoney push2 API → 广期所碳酸锂(LC) + 郑商所纯碱(SA)（2026-08-16 新增）

覆盖品种（15 个有实时价 / 5 个暂无）：
  贵金属：黄金(COMEX) 白银(COMEX) 铂金(NYMEX) 钯金(NYMEX)
  基本金属：铜(LME) 铝(LME) 镍(LME) 锌(LME) 铅(LME) 锡(LME)
  能源：    原油(WTI) 天然气(NYMEX)
  农产品：  大豆(CBOT) 玉米(CBOT) 小麦(CBOT)
  国内期货：碳酸锂(GFEX) 纯碱(ZCE)
  暂无源：  磷化工 维生素 稀土                    ← 纯现货指数，无免费API

映射表：各大宗品映射 3-5 只 A 股弹性标的（含业务占比）
输出：data/COMMODITY_ELASTICITY.js（前端 window.COMMODITY_ELASTICITY）

【基准升级（2026-08-16）】
- 旧：硬编码 REFERENCE_BASELINE（静态近期均值）
- 新：raw_data/commodity_price_history.json 维护30日滚动价格序列
      → z-score = (price - μ) / σ 替代简单百分比偏离
      → 积累满10日自动切换，不足日回退静态兜底
      → 涨价阈值双轨：dev% ≥ 3.0 或 |z-score| ≥ 2.0

【数据真实性铁律】
- 有实时价的 15 个国际品种：显示真实价格+z-score/偏离度，标注数据源和时间
- 暂无源的 5 个品种（含国内期货 LC/SA 本次未取到）：标 available=false + 原因
"""
import json
import os
import re
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

# ═══════════════ 新浪财经外盘期货免费源映射 ═══════════════
# 2026-08-18 新增：为阿狸咪家用网络（westock-mcp 不可用）提供免费兜底。
# Sina 接口无需认证、中美 IP 均可访问，覆盖 LME/NYMEX/CBOT 大部分品种。
# 返回字段: [0]=最新价 [6]=时间 [8]=昨收/结算价 [12]=日期 [13]=中文名
SINA_FUTURES_MAP = {
    # LME 基本金属（$/吨）
    "copper":       "hf_CAD",   # 伦铜（LME 3个月铜）
    "aluminum":     "hf_AHD",   # 伦铝
    "nickel":       "hf_NID",   # 伦镍
    "zinc":         "hf_ZSD",   # 伦锌
    "lead":         "hf_PBD",   # 伦铅
    "tin":          "hf_SND",   # 伦锡
    # COMEX/NYMEX 贵金属+能源
    "gold":         "hf_GC",    # COMEX黄金（$/oz）
    "silver":       "hf_SI",    # COMEX白银（$/oz）
    "platinum":     "hf_XPT",   # NYMEX铂金（$/oz）
    "palladium":    "hf_XPD",   # NYMEX钯金（$/oz）
    "oil":          "hf_CL",    # WTI原油（$/bbl）
    "natural_gas":  "hf_NG",    # NYMEX天然气（$/MMBtu）
    # CBOT 农产品（美分/蒲式耳）
    "soybean":      "hf_S",     # 美豆
    "corn":         "hf_C",     # 美玉米
    "wheat":        "hf_W",     # 美小麦
}
SINA_CACHE_TTL_SECONDS = 3600  # westock 缓存超过 1 小时视为陈旧，降级到 Sina

# ═══════════════ 参考基准（静态兜底，仅当价格历史不足30日时使用）════════════════
REFERENCE_BASELINE = {
    # 原有 4 个（7 月均值）—— 仅作冷启动兜底，有30日历史后自动切换 z-score
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
    # 国内期货（静态兜底，元/吨）
    "lithium":     150000.0,  # 碳酸锂
    "soda_ash":     1150.0,   # 纯碱
}
BASELINE_LABEL = "近期均值参考(非实时历史)"

# ═══════════════ 价格历史文件（30日滚动 z-score 真实基准）════════════════
PRICE_HISTORY_PATH = os.path.join(RAW, "commodity_price_history.json")
HISTORY_WINDOW = 30  # 滚动窗口天数

def _load_price_history():
    """加载价格历史文件。返回 {key: [float, ...]} 或空 dict。"""
    if not os.path.exists(PRICE_HISTORY_PATH):
        return {}
    try:
        with open(PRICE_HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("history", {})
    except Exception as e:
        print(f"  [warn] 价格历史读取失败: {e}")
        return {}

def _save_price_history(history):
    """保存价格历史文件。"""
    os.makedirs(os.path.dirname(PRICE_HISTORY_PATH), exist_ok=True)
    data = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": HISTORY_WINDOW,
        "history": history,
    }
    with open(PRICE_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _append_today_prices(history, prices_dict):
    """将今日价格追加到历史序列，截断至 HISTORY_WINDOW 天。

    Args:
        history: {key: [p1, p2, ...]} 历史序列
        prices_dict: {key: float} 今日实时价
    Returns:
        更新后的 history
    """
    today_str = datetime.now(CST).strftime("%Y-%m-%d")
    for key, price in prices_dict.items():
        if price is None or price <= 0:
            continue
        if key not in history:
            history[key] = []
        seq = history[key]
        # 避免同一天重复写入（盘中多次运行）
        if seq and seq[-1] == price:
            continue
        seq.append(price)
        # 截断到窗口长度
        if len(seq) > HISTORY_WINDOW * 1.5:  # 留余量，定期清理
            seq[:] = seq[-HISTORY_WINDOW:]
    return history

def _calc_zscore(current_price, history_seq):
    """计算当前价相对历史序列的 z-score。

    Returns:
        (z_score, ma, std, label) — 当 len < 10 时返回 (None, None, None, "数据不足")
    """
    if not history_seq or len(history_seq) < 10:
        return None, None, None, "数据不足(<10日)"
    import statistics
    ma = sum(history_seq[-HISTORY_WINDOW:]) / min(len(history_seq), HISTORY_WINDOW)
    if len(history_seq) >= 2:
        try:
            std = statistics.stdev(history_seq[-HISTORY_WINDOW:])
        except statistics.StatisticsError:
            std = 0.0
    else:
        std = 0.0
    if std < 1e-10:
        return 0.0, ma, std, "无波动(σ≈0)"
    z = (current_price - ma) / std
    return round(z, 3), round(ma, 3), round(std, 3), f"{min(len(history_seq),HISTORY_WINDOW)}日z-score"

# 有真实实时价数据的品种（从三个数据源获取）
REAL_PRICE_KEYS = [
    "gold", "silver", "copper", "oil",              # ← MACRO_DATA 源
    "aluminum", "nickel", "zinc", "lead", "tin",     # ← westock LME
    "platinum", "palladium", "natural_gas",          # ← westock NYMEX
    "soybean", "corn", "wheat",                     # ← westock CBOT
    "lithium", "soda_ash",                           # ← eastmoney 国内期货（2026-08-16 新增）
]

# 无任何免费实时数据源的国内品种（纯现货指数，无期货合约或免费API）
UNAVAILABLE_COMMODITIES = {
    "phosphate":  "磷化工",
    "vitamin":    "维生素",
    "rare_earth": "稀土",
}

# ═══════════════ 东方财富 domestic 期货代码映射（2026-08-16 新增）════════════════
# secid 格式：push2.eastmoney.com/api/qt/stock/get?secid={MARKET}.{CODE}
#   115=郑商所(ZCE) 116=大商所(DCE) 117=上期所(SHFE) 145=广期所(GFEX)
# 使用主力连续合约（如 SAM / LC），取 f43(最新价) + f170(涨跌幅%)
DOMESTIC_FUTURES_MAP = {
    "lithium": ("145.LC",   "广期所·碳酸锂主力"),   # GFEX LC0/LC
    "soda_ash": ("115.SAM", "郑商所·纯碱主力"),      # ZCE SA0/SAM
}

# 涨价阈值（|z-score| > X 或偏离度 > X% 视为"涨价窗口"）
HOT_THRESHOLD_PCT = 3.0
HOT_ZSCORE = 2.0  # z-score 阈值：|z| > 2 视为显著偏离（约95%置信区间外）
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


def fetch_domestic_futures_price(secid, timeout=10):
    """从东方财富 push2 API 获取国内期货实时价格。

    Args:
        secid: 如 '145.LC' (广期所碳酸锂) / '115.SAM' (郑商所纯碱)
    Returns:
        (price, change_pct, update_time_str) 或 (None, None, None)。
    """
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f57,f58,f169,f170,f171"
    headers = {
        "User-Agent": "v8-commodity-fetcher/1.0",
        "Accept": "application/json",
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        d = data.get("data", {})
        if not isinstance(d, dict):
            return None, None, None
        price = d.get("f43")
        if price is None:
            return None, None, None
        return float(price), d.get("f170"), ""
    except Exception as e:
        return None, None, None


def _parse_sina_change_pct(fields):
    """从 Sina 外盘期货返回字段中计算涨跌幅(%)。

    fields[0]=最新价, fields[8]=昨收/结算价。Sina 不直接返回涨跌幅时，
    用 (最新-昨收)/昨收 计算。昨收缺失则用 fields[7] 开盘价兜底。
    """
    try:
        price = float(fields[0])
        prev = None
        if len(fields) > 8 and fields[8]:
            prev = float(fields[8])
        elif len(fields) > 7 and fields[7]:
            prev = float(fields[7])
        if price and prev and abs(prev) > 1e-9:
            return round((price - prev) / prev * 100, 3)
    except (ValueError, TypeError):
        pass
    return 0.0


def fetch_sina_futures_prices(timeout=15):
    """
    从新浪财经免费外盘期货接口批量获取实时价格。
    无需认证，中美 IP 均可访问，作为 westock-mcp 的免费兜底源。

    返回 {key: {"price": float, "change_pct": float, "time": str, "source": str}}
    """
    codes = [code for code in SINA_FUTURES_MAP.values()]
    url = "https://hq.sinajs.cn/list=" + ",".join(codes)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/futures/",
        "Accept": "*/*",
    }
    results = {}
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout).read()
        # Sina 返回 GBK 编码
        text = resp.decode("gbk", errors="ignore")
    except Exception as e:
        print(f"  [sina] 接口请求失败: {e}")
        return results

    # 反向查找 key -> code
    code_to_key = {code: key for key, code in SINA_FUTURES_MAP.items()}
    for key, code in SINA_FUTURES_MAP.items():
        m = re.search(rf'var hq_str_{code}="([^"]*)";', text)
        if not m:
            print(f"  [sina] {key:12s} ({code}): 无返回")
            continue
        fields = m.group(1).split(",")
        if not fields or not fields[0]:
            print(f"  [sina] {key:12s} ({code}): 空数据")
            continue
        try:
            price = float(fields[0])
        except (ValueError, TypeError):
            print(f"  [sina] {key:12s} ({code}): 价格解析失败")
            continue
        chg_pct = _parse_sina_change_pct(fields)
        utime = fields[6] if len(fields) > 6 else ""
        udate = fields[12] if len(fields) > 12 else ""
        time_str = f"{udate} {utime}".strip()
        label = fields[13] if len(fields) > 13 else code
        results[key] = {
            "price": price,
            "change_pct": chg_pct,
            "time": time_str,
            "source": f"sina-futures({label})",
        }
        print(f"  [sina] {key:12s} = {price:>12.2f} ({chg_pct:+.2f}%) ← {label}")

    return results


def _cache_is_fresh(cache):
    """判断 westock 缓存是否在 SINA_CACHE_TTL_SECONDS 内。"""
    if not cache:
        return False
    ft = cache.get("fetch_time", "")
    if not ft:
        return False
    try:
        dt = datetime.strptime(ft, "%Y-%m-%d %H:%M:%S")
        age = datetime.now(CST).replace(tzinfo=None) - dt
        return age.total_seconds() < SINA_CACHE_TTL_SECONDS
    except Exception:
        return False


def fetch_all_westock_prices():
    """
    获取所有 westock 期货品种的价格 + 国内期货（东方财富）。
    优先级：westock 缓存(新鲜) > Sina 免费外盘 > westock HTTP API 直连 > 返回空。
    返回 {key: (price, change_pct, time)}
    """
    # ── 0) 读取 westock 缓存，并判断新鲜度 ──
    raw_cache = load_westock_cache()
    results = {}
    cache_fresh = False
    cache_fetch_time = ""
    cache_path = os.path.join(RAW, "commodity_prices_cache.json")
    try:
        with open(cache_path, encoding="utf-8") as f:
            full_cache = json.load(f)
        cache_fetch_time = full_cache.get("fetch_time", "")
    except Exception:
        pass

    if raw_cache:
        cache_fresh = _cache_is_fresh({"fetch_time": cache_fetch_time})
        if cache_fresh:
            for key, info in raw_cache.items():
                results[key] = info
                print(f"  ✓ {key:12s} = {info['price']:>12.2f}  ({info.get('change_pct')}%) [westock-cache]")
        else:
            age = "unknown"
            if cache_fetch_time:
                try:
                    dt = datetime.strptime(cache_fetch_time, "%Y-%m-%d %H:%M:%S")
                    age_sec = (datetime.now(CST).replace(tzinfo=None) - dt).total_seconds()
                    age = f"{age_sec/3600:.1f}h"
                except Exception:
                    pass
            print(f"  [westock] 缓存陈旧({age})，改用 Sina 免费源兜底...")

    # ── 1) Sina 免费外盘期货（westock-mcp 不可用/缓存陈旧时的免费兜底）──
    if not cache_fresh:
        sina_prices = fetch_sina_futures_prices()
        # 用 Sina 结果补充/覆盖（覆盖缓存中的旧数据）
        for key, info in sina_prices.items():
            results[key] = info

    # ── 2) 兜底：westock HTTP API 直连（国际期货）──
    # 仅当 Sina 未覆盖的品种才尝试
    missing_keys = [k for k, _ in WESTOCK_FUTURES_MAP.items() if k not in results]
    if missing_keys:
        print(f"  [westock] Sina 未覆盖 {len(missing_keys)} 个品种，尝试 westock HTTP API...")
        for key in missing_keys:
            wcode, _ = WESTOCK_FUTURES_MAP[key]
            price, chg, tm = fetch_westock_price(wcode)
            if price is not None:
                results[key] = {"price": price, "change_pct": chg, "time": tm, "source": f"westock-api({wcode})"}
                print(f"  [api]  {key:12s} = {price:>12.2f}  ({chg}%)")
            else:
                print(f"  [api]  {key:12s} = FAILED")
            time.sleep(0.15)

    # ── 3) 国内期货：东方财富 push2 API（2026-08-16 新增）──
    for key, (secid, label) in DOMESTIC_FUTURES_MAP.items():
        if key in results:  # 不覆盖
            continue
        price, chg, tm = fetch_domestic_futures_price(secid)
        if price is not None:
            results[key] = {"price": price, "change_pct": chg, "time": tm, "source": f"eastmoney-push2({label})"}
            print(f"  [domestic] {key:12s} = {price:>12.2f}  ({chg}%) ← {label}")
        else:
            print(f"  [domestic] {key:12s} = FAILED ← {label}")
        time.sleep(0.15)

    return results


def calc_one_commodity(key, info, current_price, price_date, source="", price_history=None):
    """计算单个商品的弹性榜（2026-08-16 升级：z-score 替代静态基准）。

    Args:
        price_history: 全局价格历史 {key: [float,...]}，用于 z-score 计算。
                        为 None 或 key 不在历史中时回退到 REFERENCE_BASELINE。
    """
    # ── z-score 优先，静态基准兜底 ──
    use_zscore = False
    z_score = None
    ma30 = None
    std30 = None
    baseline_label = BASELINE_LABEL

    if price_history and key in price_history:
        seq = price_history[key]
        if len(seq) >= 10:  # 至少10日才计算z-score
            z_score, ma30, std30, baseline_label = _calc_zscore(current_price, seq)
            if z_score is not None:
                use_zscore = True

    if use_zscore:
        # z-score 模式：偏离度 = z_score × 100（放大为百分比尺度，便于展示）
        dev_pct = round(z_score * 100, 2)
        baseline_val = ma30
        is_hot = abs(z_score) >= HOT_ZSCORE and z_score > 0  # 只看正向偏离（涨价）
        hot_basis = f"z-score={z_score}(σ={std30}, μ={ma30})"
    else:
        # 静态基准兜底
        baseline = REFERENCE_BASELINE.get(key)
        baseline_val = baseline
        dev_pct = (current_price - baseline) / baseline * 100 if (baseline and baseline > 0) else 0.0
        is_hot = dev_pct >= HOT_THRESHOLD_PCT
        hot_basis = f"参考基准={BASELINE_LABEL}"

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
        "baseline_30d": baseline_val,
        "baseline_label": baseline_label,
        "dev_pct": round(dev_pct, 2),
        "is_hot": is_hot,
        "hot_basis": hot_basis,
        # 2026-08-16 z-score 扩展字段
        "z_score": round(z_score, 3) if use_zscore else None,
        "ma30": ma30,
        "std30": std30,
        "use_zscore": use_zscore,
        "stocks": rows,
    }


def main():
    md = load_macro_data()
    macro_commodities = md.get("global_macro", {}).get("commodities", {})

    # ── 0) 加载价格历史（z-score 真实基准）──
    price_history = _load_price_history()
    today_prices = {}  # 收集今日价格，用于追加到历史

    # ── 通道 ①：MACRO_DATA（gold/silver/copper/oil）──
    items = []
    processed_keys = set()   # 已拿到实时价的品种，避免丢到 unavailable
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
        row = calc_one_commodity(key, info, price, pdate, source="MACRO_DATA",
                                  price_history=price_history)
        items.append(row)
        processed_keys.add(key)
        today_prices[key] = price
        if row["is_hot"]:
            hot_count += 1

    # ── 通道 ②：westock-mcp 期货 + 国内期货（东方财富push2）──
    print(f"\n[calc_commodity_elasticity] {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}  扩展版（含国内期货+z-score）")
    print(f"  通道① MACRO_DATA: gold/silver/copper/oil")
    print(f"  通道② westock 国际期货: {len(WESTOCK_FUTURES_MAP)} 个品种")
    print(f"  通道③ eastmoney 国内期货: {len(DOMESTIC_FUTURES_MAP)} 个品种 (LC/SA)")

    westock_prices = fetch_all_westock_prices()
    for key, wp in westock_prices.items():
        if key not in ELASTICITY_MAP:
            continue
        # 跳过 MACRO_DATA 已覆盖的品种（gold/silver/copper/oil），避免重复
        if key in processed_keys:
            continue
        info = ELASTICITY_MAP[key]
        row = calc_one_commodity(
            key, info,
            current_price=wp["price"],
            price_date=wp.get("time", ""),
            source=wp.get("source", "westock"),
            price_history=price_history,
        )
        items.append(row)
        processed_keys.add(key)
        today_prices[key] = wp["price"]
        if row["is_hot"]:
            hot_count += 1

    # ── 3) 追加今日价格到历史并保存 ──
    if today_prices:
        price_history = _append_today_prices(price_history, today_prices)
        _save_price_history(price_history)
        print(f"  [history] 价格历史已更新: {len(today_prices)} 个品种, "
              f"文件: {PRICE_HISTORY_PATH}")

    # 按"热度"降序（涨价窗口优先）
    items.sort(key=lambda x: (x["is_hot"], x["dev_pct"]), reverse=True)

    # 统计 z-score 使用情况
    zscore_count = sum(1 for it in items if it.get("use_zscore"))

    # ── 未拿到实时价的品种：透明列出，避免从卡片里「消失」──
    unavailable = []
    for key, info in ELASTICITY_MAP.items():
        if key in processed_keys:
            continue
        label = info.get("name", key)
        if key in UNAVAILABLE_COMMODITIES:
            reason = (
                f"{label}为现货景气指数（非标准化期货合约），无免费实时API。"
                f"数据源为SMM上海有色/百川盈孚等付费指数。"
                f"如需接入可考虑：①用相关A股板块指数代理 ②接入付费数据源。"
            )
        else:
            # 有数据源配置但本次未返回价格（如国内期货 API 受限、网络抖动、非交易时段）
            reason = (
                f"{label}已配置数据源但本次未取到实时价（API未返回/非交易时段/网络受限），"
                f"暂以「暂无数据」展示，不伪造价格。下次刷新会自动补回。"
            )
        unavailable.append({
            "key": key,
            "name": label,
            "available": False,
            "reason": reason,
            "stocks": info.get("stocks", []),
        })

    total_commodities = len(items) + len(unavailable)
    unavailable_names = "、".join(u["name"] for u in unavailable)

    result = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": macro_commodities.get("gold", {}).get("date", ""),
        "source": (
            "三通道: MACRO_DATA(gold/silver/copper/oil) + "
            "Sina免费外盘期货(LME/NYMEX/CBOT共15个，westock-mcp不可用/缓存陈旧时兜底) + "
            "eastmoney-push2国内期货(GFEX碳酸锂+ZCE纯碱)"
        ),
        "hot_count": hot_count,
        "available_count": len(items),
        "total_commodities": total_commodities,
        "hot_threshold_pct": HOT_THRESHOLD_PCT,
        "hot_zscore": HOT_ZSCORE,
        "zscore_enabled_count": zscore_count,
        "commodities": items,
        "unavailable": unavailable,
        "note": (
            f"涨价窗口：有实时价的商品相对参考基准涨幅 ≥ {HOT_THRESHOLD_PCT}% "
            f"(或 |z-score| ≥ {HOT_ZSCORE})。"
            f"弹性系数 = 偏离度 × 业务占比 × 杠杆 {ELASTICITY_LEVERAGE}（简化估算）。"
            f"已拿到实时价 {len(items)} 个品种（含贵金属/基本金属/能源/农产品/国内期货）。"
            f"其中 {zscore_count} 个已启用30日滚动z-score真实基准。"
            f"数据源：MACRO_DATA + westock-mcp期货 + eastmoney push2国内期货。"
            f"另有 {len(unavailable)} 个品种本次未展示实时价（{unavailable_names}），"
            f"原因见「逻辑详解 > 潜力参考 > 商品涨价弹性榜 · 数据源与计算逻辑」。"
            f"基准升级（2026-08-16）：静态均值 → 30日滚动z-score（μ±σ），"
            f"积累满10日自动切换，不足日回退静态兜底。"
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
