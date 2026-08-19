#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_market_brief.py — 基于 v8 实时数据生成「AI市场速览」
=============================================================
读取 raw_data/ 下的盘中数据源，用规则引擎生成结构化市场解读，
输出 raw_data/ai_market_brief.json，供 index.html 顶部 AI市场速览渲染。

设计原则：
- 不依赖 LLM，本地/云端 runner 均可秒级生成，稳定不花钱。
- 规则透明、可调试，结论由数据驱动。
- 输出 5 个模块：日内风向、市场健康度、指数纵览、市场异动、操作建议。

数据源：
  index_quotes.json      四大指数 + 涨跌家数
  concept_ranking.json   概念板块净流入/涨幅
  sector_fund_flow.json  行业/概念资金排名
  etf_intraday_heat.json ETF 分类净流入
  etf_daily_monitor.json 全市场 ETF 净流入排名
  capital_flow_data.json 个股主力净流入排名
  limit_up_heatmap.json  涨停热力
"""
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "ai_market_brief.json")


def load_raw(name, default=None):
    path = os.path.join(RAW, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ gen_market_brief 读取 {name} 失败: {e}")
        return default if default is not None else {}


def fmt_pct(v):
    if v is None:
        return "--"
    return f"{v:+.2f}%"


def fmt_yi(v):
    """元 -> 亿并格式化"""
    if v is None:
        return "--亿"
    yi = float(v) / 1e8 if abs(float(v)) > 1e7 else float(v)
    return f"{yi:+.2f}亿" if yi != 0 else f"{yi:.2f}亿"


def fmt_amount(v):
    if v is None:
        return "--亿"
    return f"{float(v):.0f}亿"


def _sentiment_signal(label):
    """情绪 → 灯（红=防守/黄=观望/绿=积极）"""
    if label in ("情绪高涨", "情绪偏暖", "情绪温和"): return "green"
    if label in ("情绪冰点", "情绪偏冷"): return "red"
    return "yellow"


def classify_sentiment(sh_chg, up_down_ratio):
    """情绪定级"""
    if sh_chg >= 1.0 and up_down_ratio >= 2.0:
        return "情绪高涨", "普涨格局，资金积极", "green"
    if sh_chg >= 0.5 and up_down_ratio >= 1.5:
        return "情绪偏暖", "结构性上涨，热点活跃", "green"
    if sh_chg <= -1.5 and up_down_ratio <= 0.5:
        return "情绪冰点", "普跌格局，避险为主", "red"
    if sh_chg <= -0.5 and up_down_ratio <= 0.8:
        return "情绪偏冷", "跌多涨少，谨慎操作", "red"
    if sh_chg >= 0.2 and up_down_ratio >= 1.0:
        return "情绪温和", "震荡偏多，精选个股", "green"
    if sh_chg <= -0.2 and up_down_ratio < 1.0:
        return "情绪谨慎", "震荡偏弱，控制仓位", "yellow"
    return "情绪震荡", "多空拉锯，观望为主", "yellow"


# 东财概念列表里的"索引/通道/成分"类条目，不应作为真实概念热点展示
_NOISE_CONCEPTS = {
    "融资融券", "深股通", "沪股通", "昨日高振幅", "富时罗素", "MSCI中国",
    "深成500", "标准普尔", "HS300_", "中证500", "上证50", "上证180",
    "深证100R", "创业板综", "创业成份", "中盘股", "大盘股", "小盘股",
    "基金重仓", "百元股", "东方财富热股", "科技风格", "大盘成长", "高市净率",
}


def real_concepts(items):
    """过滤掉索引类概念，返回真实板块"""
    return [c for c in items if c.get("name") not in _NOISE_CONCEPTS]


def health_lights(indices, up_down_ratio, main_net):
    """三灯：结构/资金/情绪 + 整行聚合灯（取最差）"""
    # 结构：四大指数同向性 + 平均涨跌幅
    chgs = [it.get("chg", 0) for it in indices]
    avg_chg = sum(chgs) / len(chgs) if chgs else 0
    same_direction = all(c >= 0 for c in chgs) or all(c <= 0 for c in chgs)
    if avg_chg >= 1.0 and same_direction:
        structure = ("结构强势", "green")
    elif avg_chg >= 0.3:
        structure = ("结构偏强", "green")
    elif avg_chg <= -1.0 and same_direction:
        structure = ("结构承压", "red")
    elif avg_chg <= -0.3:
        structure = ("结构偏弱", "red")
    else:
        structure = ("结构震荡", "yellow")

    # 资金：主力净流入（亿）
    if main_net is None:
        fund = ("资金待更新", "gray")
    elif main_net >= 100:
        fund = ("资金大幅流入", "green")
    elif main_net >= 20:
        fund = ("资金流入", "green")
    elif main_net <= -100:
        fund = ("资金大幅流出", "red")
    elif main_net <= -20:
        fund = ("资金流出", "red")
    else:
        fund = ("资金均衡", "yellow")

    # 情绪：涨跌家数比
    if up_down_ratio is None:
        emotion = ("情绪待更新", "gray")
    elif up_down_ratio >= 2.0:
        emotion = ("情绪高涨", "green")
    elif up_down_ratio >= 1.3:
        emotion = ("情绪偏暖", "green")
    elif up_down_ratio <= 0.5:
        emotion = ("情绪冰点", "red")
    elif up_down_ratio <= 0.8:
        emotion = ("情绪偏冷", "red")
    else:
        emotion = ("情绪震荡", "yellow")

    # 整行聚合灯：取最差一档（red > yellow > green > gray）
    PRIO = {"red": 3, "yellow": 2, "gray": 1, "green": 0}
    overall = "green"
    for _, c in (structure, fund, emotion):
        if PRIO.get(c, 0) > PRIO.get(overall, 0):
            overall = c
    # 但若资金大幅流入且结构非红，可以缓和到 yellow
    if overall == "green" and PRIO.get(emotion[1], 0) >= 2:
        overall = "yellow"

    return {"structure": structure, "fund": fund, "emotion": emotion, "signal": overall}


def _anomaly_signal(text):
    """anomaly text → 灯（关键词判定）"""
    if any(k in text for k in ["赎回", "撤离", "低迷", "暴跌"]):
        return "red"
    if any(k in text for k in ["净流出", "流出", "领跌", "大跌"]):
        return "red"
    if any(k in text for k in ["炽热", "过热", "极端", "剧烈"]):
        return "yellow"
    if any(k in text for k in ["净流入", "流入", "领涨", "大涨", "占优", "轮动"]):
        return "green"
    if any(k in text for k in ["分化", "波动", "偏弱", "偏强", "震荡"]):
        return "yellow"
    return "yellow"


def detect_anomalies(indices, concepts, sectors, etf_heat, etf_daily, capital, limitup):
    """基于规则生成 3~5 条市场异动（每项附 signal 灯）"""
    anomalies = []
    by_code = {it["code"]: it for it in indices}

    # 1. 大盘异动
    sh = by_code.get("000001", {})
    sz = by_code.get("399001", {})
    cy = by_code.get("399006", {})
    kc = by_code.get("000688", {})
    max_chg = max(abs(sh.get("chg", 0)), abs(sz.get("chg", 0)), abs(cy.get("chg", 0)), abs(kc.get("chg", 0)))
    if max_chg >= 2.0:
        leader = max([sh, sz, cy, kc], key=lambda x: abs(x.get("chg", 0)))
        chg = leader.get("chg", 0)
        word = "大涨" if chg >= 0 else "大跌"
        text = f"{leader.get('name', '领涨指数')} {word} {chg:+.2f}%，市场波动剧烈"
        anomalies.append({
            "tag": "大盘异动",
            "emoji": "📊",
            "text": text,
            "color": "blue",
            "signal": _anomaly_signal(text),
        })
    elif max_chg >= 1.0:
        leader = max([sh, sz, cy, kc], key=lambda x: abs(x.get("chg", 0)))
        chg = leader.get("chg", 0)
        word = "领涨" if chg >= 0 else "领跌"
        text = f"{leader.get('name', '领涨指数')} {word} {chg:+.2f}%，市场{'偏强' if chg >= 0 else '偏弱'}"
        anomalies.append({
            "tag": "大盘异动",
            "emoji": "📊",
            "text": text,
            "color": "blue",
            "signal": _anomaly_signal(text),
        })

    # 2. 科创/创业板 vs 主板 分化
    # 🛡 2026-08-19 主人令一劳永逸修复：涨跌幅格式化由硬编 "+{x:.2f}%" 改为 "{x:+.2f}%"，
    #   避免下跌时输出 "+-2.40%" 这种双重符号，确保涨+跌-语义统一。
    if cy.get("chg", 0) - sh.get("chg", 0) >= 1.5:
        text = f"创业板({cy.get('chg', 0):+.2f}%) 明显强于沪指({sh.get('chg', 0):+.2f}%)，成长风格占优"
        anomalies.append({
            "tag": "风格分化",
            "emoji": "⚡",
            "text": text,
            "color": "purple",
            "signal": "green",
        })
    elif sh.get("chg", 0) - cy.get("chg", 0) >= 1.5:
        text = f"沪指({sh.get('chg', 0):+.2f}%) 强于创业板({cy.get('chg', 0):+.2f}%)，蓝筹防御占优"
        anomalies.append({
            "tag": "风格分化",
            "emoji": "⚡",
            "text": text,
            "color": "purple",
            "signal": "yellow",
        })

    # 3. ETF 资金流向（宽基/行业）
    if etf_heat and "categories" in etf_heat:
        cats = etf_heat["categories"]
        # 找出净流入/流出最大的分类
        cat_nets = [(n, c.get("net_inflow_yi", 0)) for n, c in cats.items()]
        cat_nets.sort(key=lambda x: x[1], reverse=True)
        if cat_nets and cat_nets[0][1] >= 5:
            top_cat, top_val = cat_nets[0]
            text = f"{top_cat}ETF 净流入 {top_val:+.2f}亿，资金借道 ETF 布局{top_cat}"
            anomalies.append({
                "tag": "ETF资金",
                "emoji": "💰",
                "text": text,
                "color": "gold",
                "signal": "green",
            })
        if len(cat_nets) >= 2 and cat_nets[-1][1] <= -3:
            bot_cat, bot_val = cat_nets[-1]
            text = f"{bot_cat}ETF 净流出 {bot_val:+.2f}亿，资金从{bot_cat}撤离"
            anomalies.append({
                "tag": "ETF资金",
                "emoji": "💰",
                "text": text,
                "color": "gold",
                "signal": "red",
            })

    # 4. 概念/行业异动（过滤索引类条目）
    if concepts and concepts.get("items"):
        top = [c for c in real_concepts(concepts["items"]) if c.get("net", 0) > 0][:3]
        hot_concepts = [f"{c['name']}(+{c['net']:.1f}亿)" for c in top]
        if hot_concepts:
            text = f"主力流向：{'、'.join(hot_concepts[:3])}"
            anomalies.append({
                "tag": "概念热点",
                "emoji": "🔥",
                "text": text,
                "color": "red",
                "signal": "green",
            })

    # 5. 个股主力异动
    if capital and capital.get("top_inflow"):
        top = capital["top_inflow"][:2]
        names = [f"{c['name']}(+{c['net']:.1f}亿)" for c in top]
        text = f"主力大单流入：{'、'.join(names)}"
        anomalies.append({
            "tag": "个股异动",
            "emoji": "🚀",
            "text": text,
            "color": "cyan",
            "signal": "green",
        })
    if capital and capital.get("top_outflow"):
        bot = capital["top_outflow"][:2]
        names = [f"{c['name']}({c['net']:.1f}亿)" for c in bot]
        text = f"主力大单流出：{'、'.join(names)}"
        anomalies.append({
            "tag": "个股异动",
            "emoji": "🚨",
            "text": text,
            "color": "cyan",
            "signal": "red",
        })

    # 6. 涨停家数异动
    if limitup and limitup.get("total"):
        total = limitup["total"]
        if total >= 80:
            text = f"涨停 {total} 家，短线情绪炽热"
            anomalies.append({
                "tag": "涨停热度",
                "emoji": "🎆",
                "text": text,
                "color": "red",
                "signal": "yellow",
            })
        elif total <= 30:
            text = f"涨停仅 {total} 家，短线情绪低迷"
            anomalies.append({
                "tag": "涨停热度",
                "emoji": "❄️",
                "text": text,
                "color": "blue",
                "signal": "red",
            })

    # 去重并限制条数
    seen = set()
    unique = []
    for a in anomalies:
        key = a["tag"] + a["text"]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique[:5]


def _strategy_signal(text):
    """策略文本 → 灯"""
    if any(k in text for k in ["赎回", "撤离", "降低仓位", "防御属性弱化", "反弹或遇抛压"]):
        return "red"
    if any(k in text for k in ["减仓", "注意减仓", "赎回", "出货", "弱势"]):
        return "red"
    if any(k in text for k in ["可持筹待涨", "可加仓", "择机加仓", "加仓主线", "占优"]):
        return "green"
    if any(k in text for k in ["观望", "轻仓试错", "震荡", "控制仓位", "等待企稳", "风格占优"]):
        return "yellow"
    return "yellow"


def _top_real_concepts(concepts, n=3):
    """取真实概念净流入前 n 名（仅正流入），返回名称列表"""
    if not concepts:
        return []
    items = real_concepts(concepts.get("items", []))
    items = [c for c in items if c.get("net", 0) > 0]
    items.sort(key=lambda x: x.get("net", 0), reverse=True)
    return [c["name"] for c in items[:n]]


def _top_picks(capital, n=2):
    """取主力净流入个股前 n 名，返回 {code,name,net} 列表"""
    if not capital or not capital.get("top_inflow"):
        return []
    picks = capital["top_inflow"][:n]
    return [{"code": p.get("code", ""), "name": p.get("name", ""), "net": round(p.get("net", 0), 2)} for p in picks]


def build_strategy(sentiment_label, health, anomalies, indices, etf_daily, concepts=None, capital=None):
    """基于当前状态生成 1~2 条操作建议（每条带 signal），并把主线板块/推荐个股落地到文本"""
    strategies = []
    by_code = {it["code"]: it for it in indices}
    sh = by_code.get("000001", {})
    cy = by_code.get("399006", {})
    structure_ok = health["structure"][1] == "green"
    fund_ok = health["fund"][1] == "green"

    # 主线板块 & 推荐个股（用于把模糊建议落地为具体名称）
    sectors = _top_real_concepts(concepts, 3)
    picks = _top_picks(capital, 2)
    sector_str = "、".join(sectors) if sectors else "领涨板块"
    pick_str = "、".join([p["name"] for p in picks]) if picks else "主力净流入前排个股"

    # 根据情绪、结构、资金综合给出仓位建议
    if sentiment_label in ("情绪高涨", "情绪偏暖") and structure_ok and fund_ok:
        s = f"大盘量价配合、资金流入，可持筹待涨；追高需谨慎，优选{sector_str}低位补涨，关注{pick_str}。"
        strategies.append({"text": s, "signal": "green"})
    elif sentiment_label in ("情绪冰点", "情绪偏冷") and health["fund"][1] in ("red", "gray"):
        s = "市场情绪低迷、资金流出，建议控制仓位，避免追涨杀跌，等待企稳信号。"
        strategies.append({"text": s, "signal": "red"})
    elif structure_ok and fund_ok:
        s = f"指数结构偏强且资金配合，可择机加仓{sector_str}，关注{pick_str}，设置好止损。"
        strategies.append({"text": s, "signal": "green"})
    elif health["structure"][1] == "yellow" and health["emotion"][1] == "green":
        s = f"指数震荡但个股活跃，可轻指数重个股，聚焦{sector_str}，关注{pick_str}。"
        strategies.append({"text": s, "signal": "yellow"})
    else:
        s = "当前市场方向不明或资金犹豫，建议保持观望或轻仓试错，严格止损纪律。"
        strategies.append({"text": s, "signal": "yellow"})

    # ETF 资金流向提示：仅列出真正属于科技/成长或宽基的赎回品种
    if etf_daily and etf_daily.get("top_outflow"):
        tech_keys = ["科创", "创业板", "半导体", "芯片", "通信"]
        broad_keys = ["上证50", "沪深300", "中证500", "中证1000"]
        tech_out = [x for x in etf_daily["top_outflow"]
                    if any(k in x.get("name", "") for k in tech_keys)]
        broad_out = [x for x in etf_daily["top_outflow"]
                     if any(k in x.get("name", "") for k in broad_keys)]
        if tech_out:
            names = "、".join([x["name"] for x in tech_out[:2]])
            s = f"科技/成长类 ETF 出现赎回({names})，反弹或遇抛压，注意减仓科技仓位。"
            strategies.append({"text": s, "signal": "red"})
        elif broad_out:
            names = "、".join([x["name"] for x in broad_out[:2]])
            s = f"宽基 ETF 净流出({names})，机构配置意愿减弱，宜降低仓位。"
            strategies.append({"text": s, "signal": "red"})

    # 若创业板强于主板，提示风格
    if cy.get("chg", 0) - sh.get("chg", 0) >= 1.0:
        s = "成长风格占优，可关注创业板/科创板中主力净流入个股；蓝筹防御属性弱化。"
        strategies.append({"text": s, "signal": "yellow"})
    elif sh.get("chg", 0) - cy.get("chg", 0) >= 1.0:
        s = "蓝筹/价值风格占优，可关注上证50、沪深300 成分股；成长股承压。"
        strategies.append({"text": s, "signal": "yellow"})

    return strategies[:2]


def get_market_status():
    """根据当前时间判断盘前/盘中/收盘。"""
    now = datetime.now()
    hm = now.hour * 100 + now.minute
    if hm >= 1500:
        return "收盘"
    if hm >= 930:
        return "盘中"
    return "盘前"


def build_closing_summary(indices, up, down, flat, amount_total):
    """收盘后生成一句话总结。"""
    by_code = {it["code"]: it for it in indices}
    sh = by_code.get("000001", {})
    cy = by_code.get("399006", {})
    sh_chg = sh.get("chg", 0) or 0
    cy_chg = cy.get("chg", 0) or 0
    total_ud = up + down + flat
    up_pct = round(up / total_ud * 100, 1) if total_ud else 0
    parts = []
    if sh_chg >= 1.0:
        parts.append(f"沪指收涨 {sh_chg:+.2f}%")
    elif sh_chg <= -1.0:
        parts.append(f"沪指收跌 {sh_chg:+.2f}%")
    else:
        parts.append(f"沪指{'收涨' if sh_chg>=0 else '收跌'} {sh_chg:+.2f}%")
    parts.append(f"{up} 只上涨（{up_pct}%）")
    if amount_total:
        parts.append(f"两市合计成交 {amount_total:.0f} 亿元")
    if abs(cy_chg - sh_chg) >= 1.5:
        parts.append(f"创业板{'大涨' if cy_chg>=0 else '大跌'} {cy_chg:+.2f}%，风格分化明显")
    return "。".join(parts) + "。"


def main():
    print(f"=== gen_market_brief 开始 {datetime.now().isoformat(timespec='seconds')} ===")

    idx = load_raw("index_quotes.json", {})
    concepts = load_raw("concept_ranking.json", {})
    sectors = load_raw("sector_fund_flow.json", {})
    etf_heat = load_raw("etf_intraday_heat.json", {})
    etf_daily = load_raw("etf_daily_monitor.json", {})
    capital = load_raw("capital_flow_data.json", {})
    limitup = load_raw("limit_up_heatmap.json", {})

    indices = idx.get("items", [])
    by_code = {it["code"]: it for it in indices}
    sh = by_code.get("000001", {})
    sz = by_code.get("399001", {})

    # 涨跌家数：沪市 + 深市（东财 f104/f105/f106）
    up = (sh.get("up", 0) or 0) + (sz.get("up", 0) or 0)
    down = (sh.get("down", 0) or 0) + (sz.get("down", 0) or 0)
    flat = (sh.get("flat", 0) or 0) + (sz.get("flat", 0) or 0)
    total_ud = up + down
    up_down_ratio = round(up / down, 2) if down else None

    amount_total = round((sh.get("amount", 0) or 0) + (sz.get("amount", 0) or 0), 1)

    market_status = get_market_status()

    # 日内风向
    sh_chg = sh.get("chg", 0)
    sentiment_label, sentiment_desc, sentiment_signal = classify_sentiment(sh_chg, up_down_ratio or 0)

    # 主力净流入估算：真实概念排名前十净流入之和（亿）
    real_items = real_concepts(concepts.get("items", [])) if concepts else []
    main_net = sum(c.get("net", 0) for c in real_items[:10])

    # 健康度
    health = health_lights(indices, up_down_ratio, main_net)

    # 指数纵览
    index_overview = []
    for it in indices:
        index_overview.append({
            "name": it.get("short", it.get("name", "")),
            "chg": it.get("chg", 0),
            "amount": it.get("amount", 0),
        })

    # 异动
    anomalies = detect_anomalies(indices, concepts, sectors, etf_heat, etf_daily, capital, limitup)

    # 操作建议
    strategies = build_strategy(sentiment_label, health, anomalies, indices, etf_daily, concepts, capital)

    # 主线板块 & 推荐个股（结构化落地，供前端展示）
    mainline_sectors = _top_real_concepts(concepts, 5)
    mainline_picks = _top_picks(capital, 3)

    # ETF 资金解读（类似截图风格）
    etf_insight = []
    if etf_daily and etf_daily.get("top_inflow") and etf_daily.get("top_outflow"):
        net_total = sum(x.get("net", 0) for x in etf_daily.get("top_inflow", [])) + \
                    sum(x.get("net", 0) for x in etf_daily.get("top_outflow", []))
        etf_insight.append(f"全市场 ETF 合计净流入 {net_total/1e8:+.2f}亿")
        # 科技类净流出提示
        tech_out = [x for x in etf_daily.get("top_outflow", [])
                    if any(k in x.get("name", "") for k in ["科创", "创业板", "半导体", "芯片", "通信"])]
        if tech_out:
            etf_insight.append(f"{'、'.join([x['name'] for x in tech_out[:2]])} 被赎回，大资金借反弹出货科技。")
        # 宽基流入提示
        broad_in = [x for x in etf_daily.get("top_inflow", [])
                    if any(k in x.get("name", "") for k in ["上证50", "沪深300", "中证500", "中证1000"])]
        if broad_in:
            etf_insight.append(f"资金同时流入 {'、'.join([x['name'] for x in broad_in[:2]])}，向蓝筹和中盘轮动。")

    closing_summary = build_closing_summary(indices, up, down, flat, amount_total) if market_status == "收盘" else ""

    brief = {
        "gen_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_status": market_status,
        "sentiment": {
            "label": sentiment_label,
            "description": sentiment_desc,
            "signal": sentiment_signal,
            "up": up,
            "down": down,
            "flat": flat,
            "up_down_ratio": up_down_ratio,
        },
        "health": health,
        "indices": index_overview,
        "amount_total": amount_total,
        "anomalies": anomalies,
        "strategies": strategies,
        "mainline_sectors": mainline_sectors,
        "mainline_picks": mainline_picks,
        "etf_insight": etf_insight,
        "closing_summary": closing_summary,
        "note": f"由{market_status}数据规则生成，非投资建议",
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ 已生成 {OUT}")
    print(f"   状态: {market_status} | 风向: {sentiment_label} | 涨跌比 {up_down_ratio} | 异动 {len(anomalies)} 条 | 策略 {len(strategies)} 条")


if __name__ == "__main__":
    main()
