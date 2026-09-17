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
  etf_daily_monitor.json 全市场 ETF 净流入排名（ETF资金条的「净流入/净流出 TOP5」品种明细；
                         品种块 = 名称+金额一行 / 代码小字另起一行，见 detect_anomalies 第 3 段）
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
    """情绪定级：涨跌家数比优先，沪指单点仅作微调
    🛡 2026-09-08 一劳永逸修复：
      1) 涨跌比优先定级（原只看沪指单点，窄幅震荡市每日落兜底'情绪震荡'）。
      2) 窄幅偏分支：沪指涨跌幅绝对值<0.5% 时，按涨跌比直接给偏暖/偏冷，不再死落'震荡'。
      3) 剔除原 sh_chg>=1.0 / sh_chg<=-1.5 两处分支——在涨跌比优先后几乎不可达，且会覆盖
         已定的涨跌比结论，造成'日内风向'文字忽高忽低。"""
    r = up_down_ratio or 0
    narrow = abs(sh_chg) < 0.5

    # 宽幅+极端涨跌比：直接定级
    if r >= 2.0 and sh_chg >= 0.3:
        return "情绪高涨", "普涨格局，资金积极", "green"
    if r <= 0.5 and sh_chg <= -0.3:
        return "情绪冰点", "普跌格局，避险为主", "red"

    # 窄幅（沪指<0.5%）按涨跌比分支，避免死落"情绪震荡"
    if narrow:
        if r >= 1.5:
            return "情绪偏暖", "涨多跌少，热点活跃", "green"
        if r <= 0.7:
            return "情绪偏冷", "跌多涨少，谨慎操作", "red"
        if r >= 1.2:
            return "情绪温和", "震荡偏多，精选个股", "green"
        if r <= 0.85:
            return "情绪谨慎", "震荡偏弱，控制仓位", "yellow"
        return "情绪震荡", "多空拉锯，观望为主", "yellow"

    # 非窄幅：涨跌比+沪指方向综合
    if r >= 1.5 and sh_chg >= -0.3:
        return "情绪偏暖", "涨多跌少，热点活跃", "green"
    if r <= 0.7 and sh_chg <= 0.3:
        return "情绪偏冷", "跌多跌少，谨慎操作", "red"
    if r >= 1.0 and sh_chg >= 0.2:
        return "情绪温和", "震荡偏多，精选个股", "green"
    if r < 1.0 and sh_chg <= -0.2:
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


# 申万一级行业白名单（31 个）
# 🛡 2026-09-11 主人令：AI速览「行业」行的大数必须与前端「板块资金趋势·盘中追热」的
#   SW1 大数逐字一致（同源 sector_fund_flow，剔除二/三级子行业避免重复计入）。
#   改这里 = 必须同步 index.html renderSector() 里的 SW_LV1_NAMES。
_SW_LV1_NAMES = {
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子", "家用电器", "食品饮料", "纺织服饰",
    "轻工制造", "医药生物", "公用事业", "交通运输", "房地产", "商贸零售", "社会服务", "综合",
    "建筑材料", "建筑装饰", "电力设备", "机械设备", "国防军工", "汽车", "美容护理", "石油石化",
    "煤炭", "环保", "传媒", "计算机", "通信", "银行", "非银金融",
}


def _sector_list(sectors, key):
    """取 sector_fund_flow.json 的 sectors_in/out 列表（缺字段返回空表）"""
    if not sectors:
        return []
    return [s for s in (sectors.get(key) or []) if isinstance(s, dict) and s.get("name")]


def sw1_industry_net(sectors):
    """申万一级 31 行业口径的主力净额汇总（流入 - 流出，亿元）。

    与 index.html renderSector() 的 SW1 大数 1:1 对齐：只认 type=='行业' 且在 31 个一级名单内的条目。
    数据缺失/盘前清空时返回 None（不得用 0 兜底，0 会被误读成「资金平衡」）。
    """
    ins = [s for s in _sector_list(sectors, "sectors_in")
           if s.get("type") == "行业" and s["name"] in _SW_LV1_NAMES]
    outs = [s for s in _sector_list(sectors, "sectors_out")
            if s.get("type") == "行业" and s["name"] in _SW_LV1_NAMES]
    if not ins and not outs:
        return None
    total_in = sum(float(s.get("net") or 0) for s in ins)
    total_out = abs(sum(float(s.get("net") or 0) for s in outs))
    return round(total_in - total_out, 1)


def _fmt_sector_list(items, signed=False):
    """[{name,net}] → ‘名称 +x.x亿、…’（signed=True 时保留数值自带符号）"""
    out = []
    for s in items:
        net = float(s.get("net") or 0)
        out.append(f"{s['name']} {net:+.1f}亿" if signed else f"{s['name']} +{net:.1f}亿")
    return "、".join(out)


_ROMAN_LV = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4}


def _split_level(name):
    """(基名, 层级序号)：`地面兵装Ⅲ` -> ('地面兵装', 3)；无罗马数字后缀 -> (原名, 1)"""
    if name and name[-1] in _ROMAN_LV:
        return name[:-1], _ROMAN_LV[name[-1]]
    return name, 1


def _dedupe_same_level(items):
    """剔除「同数据、同父级」的父子级重复项：每个基名只保留层级最高的一条。

    东财行业源（m:90 t:2）同时给出 Ⅱ/Ⅲ 细分，父子同额并排（如 地面兵装Ⅱ/Ⅲ 各 +9.74亿
    = 同一笔资金被算两遍）。本函数按基名去重、保留层级最高的一个（Ⅱ 优先于 Ⅲ），
    其余非层级条目按原顺序原样保留（2026-09-11 主人令：「同数据有同级的就保留一级，其他不变」）。
    """
    best = {}
    order = []
    for s in items:
        base, lvl = _split_level(s.get("name") or "")
        if base not in best:
            best[base] = (lvl, s)
            order.append(base)
        elif lvl < best[base][0]:
            best[base] = (lvl, s)
    return [best[b][1] for b in order]


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
    # 🛡 2026-09-08 一劳永逸修复：原口径用概念净流入前十之和(永远正数)且阈值100/20，
    #    资金灯恒"大幅流入"，其下分支全部死行。改用真实双向主力净额 market_net + 300亿阈值，
    #    让资金灯恢复区分度。
    if main_net is None:
        fund = ("资金待更新", "gray")
    elif main_net >= 300:
        fund = ("资金大幅流入", "green")
    elif main_net >= 60:
        fund = ("资金流入", "green")
    elif main_net <= -300:
        fund = ("资金大幅流出", "red")
    elif main_net <= -60:
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
    """基于规则生成 3~6 条市场异动（每项附 signal 灯；上限 6 条见函数末尾 unique[:6]）"""
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

    # 3. ETF 资金流向：【分类概览 ｜ 净流入TOP5 ｜ 净流出TOP5】
    # 🛡 2026-09-16 主人令「写出具体的TOP5流入和流出」：
    #   原写法只报分类第一名（「宽基ETF 净流入 +31.49亿，资金借道 ETF 布局宽基」），
    #   看不出钱具体进了哪只 ETF，且分类第一名以外的信息全丢。
    #   现改为在同一条内给出：分类概览 ｜ 具体品种净流入 TOP5 ｜ 具体品种净流出 TOP5，
    #   品种明细取自 etf_daily_monitor.json（全市场 ETF 净流入真实排名，含代码，net 单位元）。
    #   版式（2026-09-16 二次主人令「代码写在名字下方，要不会很长」）：
    #   每品种 =「名称 +x.xx亿」一行 + 代码小字（11px · #cbd5e1）一行，5 个并排两行高。
    #   ⚠️ 必须保持「一条 anomaly」：anomalies 上限 6 条且当前正好用满 6 条，
    #      若拆成「流入/流出」两条会把后面的「个股异动」挤出（见函数末尾 unique[:6]），
    #      故用「 ｜ 」分段合并为一条（与下方「行业资金」条同款版式）。
    def _etf_top5(_key):
        """全市场 ETF 净流入排名前 5 → HTML 小块列表（名称+金额一行、代码小字另起一行）"""
        _out = []
        for _x in ((etf_daily or {}).get(_key) or []):
            try:
                _net = float(_x.get("net") or 0) / 1e8
            except (TypeError, ValueError):
                continue
            # 🛡 2026-09-16 主人令「ETF 的代码写在名字下方，要不会很长」「字小一点、
            #   不要占用太大版面、字色提亮」：
            #   代码另起一行（11px + 提亮 #cbd5e1），横向只占「名称 +金额」的宽度，
            #   5 个品种并排也不挤；两行块用 inline-block 并排、行高 1.45 控高。
            #   ⚠️ 前端 anomalies 渲染走 innerHTML（index.html:2286 h+=a.text），
            #     本条的 signal 为显式给定，`_fallbackLight()` 不会被调用 ⇒ 带标签安全；
            #     已全仓核查：无任何脚本解析本条文本（update_v8/audit_empty_cards/
            #     logic.html 均只读键名或整体存在性）。
            # 🛡 2026-09-17 主人令「流入流出的那些ETF字体全部调小，合计的大小不变」：
            #   仅**品种小块**（名称+金额、代码小字）整体降一档字号，让 5×2 两行并排
            #   更紧凑；本条里其余文字（「全市场ETF合计净流入/流出」总额、
            #   「净流入/流出TOP5」标签、分类概览）**一律保持容器默认 13px 不变**。
            #   实现方式：不给外层块设字号（否则会连带放大/缩小整段），而是分别落到
            #   两行内层 span —— 名称金额行 12px、代码行 11px→10px，
            #   两档等比递减，层次不丢（"合计的大小不变" 由此保证）。
            #   ⚠️ 前端 anomalies 渲染走 innerHTML（index.html 内 h+=a.text），
            #     内联 font-size 原样生效；已确认无任何脚本解析本条文本。
            _out.append(
                '<span style="display:inline-block;vertical-align:top;'
                'margin:0 16px 0 0;line-height:1.45;white-space:nowrap;">'
                f'<span style="font-size:12px;">{_x.get("name", "")} {_net:+.2f}亿</span><br>'
                f'<span style="font-size:10px;color:#cbd5e1;">{_x.get("code", "")}</span></span>'
            )
            if len(_out) >= 5:
                break
        return _out

    def _etf_cat_name(_cat, _direction):
        """ETF 分类名 -> 可读标签。

        🛡 2026-09-17 主人令（截图核查）：原实现分类为「行业」时跨文件借名（SECTOR_FUND_FLOW
           第一名「汽车」硬拼「汽车行业ETF」），数字却来自 ETF 分类「行业」合计，两者不同源 =>
           读起来像「汽车是 ETF 净流入第一」、TOP5 却没有汽车，自相矛盾。
           既已确认「行业」即 ETF 分类口径本身，直接返回分类名；若要标具体行业应从本分类
           top_inflow 取第一名，而非跨文件借用股票板块榜。
        """
        return _cat
