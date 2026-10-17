#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_etf_intraday.py — ETF 三件套数据生成
  · ETF_INTRADAY_HEAT（盘中：主力净流入排名 TOP5/OUTFLOW5 + 分类汇总）
  · ETF_DAILY_MONITOR（日监控：TOP_INFLOW/OUTFLOW + 总额统计）
  · ETF_PULSE（放量异动：量比 > 1.2 按量比排序）

数据源：东方财富 push2（fundETFmarketList / ETF 实时价 / 主力净流入）
主要 ETF push2 端点：
  · ETF 列表：https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=200&fs=m:1+t:9 (m:1=沪基金,t:9=ETF)
  · 实时行情：https://push2.eastmoney.com/api/qt/stock/get?secid=1.510300&fields=f43,f44,f45,f46,f47,f48,f60,f62,f168,f169,f170
  · 主力净流入：f62（主力净流入，单位元）
  · 涨跌幅：f170  当日涨跌幅
"""
import os, json, sys, time, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
CST = ZoneInfo("Asia/Shanghai")

ETF_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=300&fs=m:1,t:9,m:0,t:9&fields=f12,f14,f13,f2,f3,f5,f6,f62,f168,f170"
QUOTE_URL_TPL = "https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f12,f13,f43,f44,f45,f46,f47,f48,f60,f62,f168,f169,f170"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/fund/etf/",
    "Accept": "application/json, text/plain, */*",
}


# ---------- ETF 真实行业分类（2026-09-11 一劳永逸修复：按名称关键词，不再按 code 前缀分交易所） ----------
# 🛡 规则顺序即优先级；货币/债券/商品/跨境先判定，避免宽基/行业误归类。
_ETF_CLASS_RULES = [
    # (keywords_tuple, type, real_industry_or_None)
    # 货币 / 债券 / 商品 / 跨境
    (("日利", "添益", "现金", "货币", "保证金", "快线", "财富宝", "理财金", "薪钱包", "添富通", "易支付", "增值宝", "钱包"), "货币", None),
    (("国债", "政金债", "城投债", "信用债", "可转债", "公司债", "地方债", "债券", "国开债", "农发债", "铁道债", "科创债", "短融", "中票"), "债券", None),
    (("黄金", "原油", "白银", "豆粕", "能源化工", "商品", "有色金属", "农产品", "CRB", "金ETF"), "商品", None),
    (("恒生", "港股", "香港", "中概", "纳指", "标普", "道琼斯", "道指", "日经", "印度", "越南", "德国", "法国", "英国", "欧洲", "亚太", "美国", "美股", "跨境", "韩国", "日本", "莫斯科", "台湾", "富时"), "跨境", None),
    # 宽基 / 策略
    (("沪深300", "中证500", "中证1000", "中证2000", "上证50", "深证50", "创业板", "科创板", "科创50", "科创100", "上证指数", "深证成指", "中小100", "中证800", "中证100", "A50", "国证2000", "国证1000", "深证100", "创业板50", "双创50", "中证A50", "MSCI"), "宽基", None),
    (("红利", "低波", "价值", "成长", "质量", "龙头", "等权", "动量", "反转", "高股息", "高分红", "基本面", "增强", "现金流", "ESG", "Smart"), "策略", None),
    # 真实行业/主题（按名称关键词）
    (("银行",), "行业", "银行"),
    (("保险",), "行业", "保险"),
    (("证券", "券商", "非银金融"), "行业", "证券"),
    (("医药", "医疗", "创新药", "生物医药", "医疗器械", "疫苗", "医美", "中药", "生物科技", "医疗保健", "健康", "恒生医疗"), "行业", "医药生物"),
    (("食品饮料", "酒", "白酒", "啤酒", "消费", "家电", "旅游", "酒店", "餐饮", "农业", "养殖", "畜牧", "预制菜", "免税", "饮料", "乳品", "食品", "农牧", "猪肉", "鸡肉", "种业"), "行业", "消费"),
    (("通信设备",), "行业", "通信设备"),
    (("5G", "通信", "基站"), "行业", "通信"),
    (("半导体", "芯片", "集成电路"), "行业", "半导体"),
    (("科技",), "行业", "TMT/科技"),
    (("电子", "被动元件", "元件", "消费电子", "光电", "PCB", "MLCC"), "行业", "电子元件"),
    (("计算机", "软件", "人工智能", "AI", "算力", "云计算", "大数据", "网络安全", "物联网", "区块链", "数字货币", "信创", "IT", "数据中心", "东数西算", "数字经济"), "行业", "计算机/软件"),
    (("传媒", "游戏", "影视", "动漫", "文娱", "直播"), "行业", "传媒/游戏"),
    (("新能源", "光伏", "电池", "储能", "锂电", "新能源车", "智能汽车", "锂电池", "太阳能", "风电", "核电", "水电", "火电", "绿电", "电力", "电网", "特高压", "能源"), "行业", "新能源/电力"),
    (("军工", "国防", "航天", "航空", "船舶", "地面兵装", "大飞机", "军民融合"), "行业", "军工"),
    (("稀土", "钴", "镍", "铜", "铝", "钢铁", "煤炭", "化工", "石化", "石油", "基础化工", "化学", "化纤", "建材", "水泥", "玻璃", "磷化工", "有机硅", "钛白粉", "纯碱", "PVC"), "行业", "周期/资源"),
    (("地产", "基建", "建筑", "建材", "装饰", "家具", "工程机械", "挖掘", "装配式建筑"), "行业", "地产/基建"),
    (("汽车", "机械", "制造", "机器人", "工业母机", "高端装备", "智能制造", "机床", "汽车零部", "整车"), "行业", "汽车/制造"),
    (("交运", "物流", "港口", "航运", "机场", "高铁", "铁路", "公路", "快递"), "行业", "交通运输"),
    (("环保", "公用事业", "水务", "燃气"), "行业", "环保/公用"),
]


def _classify_etf(name, code):
    """按 ETF 名称关键词返回 (type, industry)。
    type ∈ {宽基, 行业, 主题, 跨境, 商品, 债券, 货币, 策略, 其他}
    industry 仅对 行业/主题 类型返回真实行业名，其余为 None。
    """
    n = (name or "").upper()
    for keywords, etf_type, industry in _ETF_CLASS_RULES:
        if any(k in n for k in keywords):
            return etf_type, industry
    return "其他", None


def _http(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"_err": str(e)[:80]}


def fetch_etf_list():
    """拉东方财富 ETF 列表（沪+深 各前 100），返回 [{code,name,pct,amount_main}, ...]"""
    d = _http(ETF_LIST_URL)
    if d.get("_err"):
        return None, d["_err"]
    rows = []
    for it in d.get("data", {}).get("diff", []) or []:
        rows.append({
            "code": str(it.get("f12")).zfill(6),
            "name": it.get("f14"),
            "price": it.get("f2") / 100 if it.get("f2") else None,
            "pct": it.get("f3") / 100 if it.get("f3") else None,
            "amount": (it.get("f5") or 0),
            "vol_ratio": (it.get("f6") or 0),  # 量比
            "main_net_inflow": it.get("f62") or 0,  # 元
            "amplitude": it.get("f168") or 0,
        })
    return rows, None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    # 1) ETF_INTRADAY_HEAT
    items, err = fetch_etf_list()
    # 🛡 2026-08-17 主人怒令发现：网络失败时写 error=True 空结构会覆盖小九真版本（1564 只真数据全没了）
    # 一劳永逸修：网络失败直接 sys.exit(0) 不写任何文件，保留 raw_data/etf_*.json 现有真数据
    # 云端自托管 runner 没这个问题（云端可直连 eastmoney），本守卫只防家里机被风控覆盖
    if items is None:
        print(f"  ❌ eastmoney push2 失败: {err} — 不写盘，保留现有 raw_data/etf_*.json（避免覆盖小九真版本）")
        print(f"  ℹ️  家里机网络风控，请云端 v8_cn_fetch_cloud.yml category=intraday 重跑补救")
        sys.exit(0)
    else:
        # 按主力净流入排序
        items_sorted = sorted(items, key=lambda x: x.get("main_net_inflow", 0), reverse=True)
        inflow_top = [x for x in items_sorted if x.get("main_net_inflow", 0) > 0][:10]
        outflow_top = [x for x in items_sorted if x.get("main_net_inflow", 0) < 0][-10:][::-1]
        for x in items:
            x["main_net_inflow_yi"] = round(x["main_net_inflow"] / 1e8, 2)  # 转亿元
        # 真实分类：按名称关键词，不再按交易所 code 前缀
        for x in items:
            etf_type, industry = _classify_etf(x["name"], x["code"])
            x["type"] = etf_type
            x["industry"] = industry or ""

        # 类型口径汇总（宽基/行业/主题/跨境/商品/债券/货币/策略/其他）
        type_cats = {}
        for x in items:
            t = x["type"]
            if t not in type_cats:
                type_cats[t] = {"net_inflow_yi": 0.0, "count": 0, "items": []}
            type_cats[t]["net_inflow_yi"] += x["main_net_inflow_yi"]
            type_cats[t]["count"] += 1
            type_cats[t]["items"].append(x)
        for c in type_cats.values():
            c["net_inflow_yi"] = round(c["net_inflow_yi"], 2)

        # 真实行业资金汇总（仅 行业/主题 ETF）
        ind_flow = {}
        for x in items:
            if x["type"] in ("行业", "主题") and x.get("industry"):
                ind = x["industry"]
                if ind not in ind_flow:
                    ind_flow[ind] = {"name": ind, "net_inflow_yi": 0.0, "count": 0, "items": []}
                ind_flow[ind]["net_inflow_yi"] += x["main_net_inflow_yi"]
                ind_flow[ind]["count"] += 1
                ind_flow[ind]["items"].append(x)
        industry_flow = sorted(
            [dict(v, net_inflow_yi=round(v["net_inflow_yi"], 2)) for v in ind_flow.values()],
            key=lambda d: d["net_inflow_yi"],
            reverse=True,
        )

        # 交易所口径保留作调试/兼容
        exchange_buckets = {"沪市ETF": [], "深市ETF": [], "跨市场ETF": []}
        for x in items:
            if x["code"].startswith("5"):
                exchange_buckets["沪市ETF"].append(x)
            elif x["code"].startswith("1"):
                exchange_buckets["深市ETF"].append(x)
            else:
                exchange_buckets["跨市场ETF"].append(x)

        result_heat = {
            "update_time": now,
            "items": items,
            "inflow_top": inflow_top,
            "outflow_top": outflow_top,
            "categories": type_cats,
            "industry_flow": industry_flow,
            "exchange_buckets": exchange_buckets,
            "note": "主力净流入 TOP10/外流 TOP10；categories 已改为真实类型（宽基/行业/主题/跨境/商品/债券/货币/策略/其他），industry_flow 为真实行业资金",
            "total_etf": len(items),
            "error": False,
        }

    # 2) ETF_DAILY_MONITOR（与 INTRADAY_HEAT 数据同源但简化 + 汇总指标）
    result_daily = {
        "update_time": now,
        "total_etf": result_heat.get("total_etf", 0),
        "total_net": round(sum(x.get("main_net_inflow", 0) for x in items or []) / 1e8, 2) if items else 0,
        "top_inflow": result_heat.get("inflow_top", [])[:5],
        "top_outflow": result_heat.get("outflow_top", [])[:5],
        "note": "ETF 全市场日度汇总，净流入单位亿元",
    }

    # 3) ETF_PULSE（量比 > 1.2 放量异动）
    if items:
        pulse_list = sorted(
            [x for x in items if (x.get("vol_ratio") or 0) > 1.2 and abs(x.get("pct") or 0) > 0.1],
            key=lambda x: x.get("vol_ratio", 0),
            reverse=True,
        )[:30]
    else:
        pulse_list = []
    result_pulse = {
        "update_time": now,
        "etfs": pulse_list,
        "note": "盘中异动：量比>1.2 + 涨跌幅>0.1% 的放量 ETF（按量比排序）",
        "count": len(pulse_list),
    }

    # 写出 raw_data/
    write_json(os.path.join(RAW, "etf_intraday_heat.json"), result_heat)
    write_json(os.path.join(RAW, "etf_daily_monitor.json"), result_daily)
    write_json(os.path.join(RAW, "etf_pulse.json"), result_pulse)
    print(f"  ✅ etf_intraday_heat: total_etf={result_heat.get('total_etf')}, error={result_heat.get('error')}")
    print(f"  ✅ etf_daily_monitor: total_net={result_daily['total_net']}亿")
    print(f"  ✅ etf_pulse: count={result_pulse['count']} (放量 ETF)")
    return result_heat.get("error", False)


if __name__ == "__main__":
    print(f"[calc_etf_intraday] {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    err = build()
    sys.exit(1 if err else 0)
