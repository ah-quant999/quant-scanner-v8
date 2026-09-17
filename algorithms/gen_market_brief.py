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
            _out.append(
                '<span style="display:inline-block;vertical-align:top;'
                'margin:0 16px 0 0;line-height:1.45;white-space:nowrap;">'
                f'{_x.get("name", "")} {_net:+.2f}亿<br>'
                f'<span style="font-size:11px;color:#cbd5e1;">{_x.get("code", "")}</span></span>'
            )
            if len(_out) >= 5:
                break
        return _out

    def _etf_cat_name(_cat, _direction):
        """ETF 分类名 → 可读标签。分类为「行业」时用真实行业净额第一名，避免「布局行业」这种空话。"""
        if _cat != "行业":
            return _cat
        _rows = [s for s in _sector_list(sectors, "sectors_in" if _direction == "in" else "sectors_out")
                 if s.get("type") == "行业"]
        _rows.sort(key=lambda s: -float(s.get("net") or 0) if _direction == "in" else float(s.get("net") or 0))
        return (_rows[0]["name"] + "行业") if _rows else "行业"

    if etf_heat and "categories" in etf_heat:
        _cats = etf_heat["categories"]
        _relevant = {"宽基", "行业", "主题", "跨境", "商品", "策略"}   # 排除货币/债券/其他
        # 🛡 兼容旧结构（list）与新结构（dict with net_inflow_yi）
        cat_nets = [(_n, _cats[_n].get("net_inflow_yi", 0)) for _n in _relevant
                    if _n in _cats and isinstance(_cats[_n], dict)]
        cat_nets.sort(key=lambda x: x[1], reverse=True)
    else:
        cat_nets = []

    _etf_in5 = _etf_top5("top_inflow")
    _etf_out5 = _etf_top5("top_outflow")
    _etf_parts = []

    # 🛡 2026-09-17 主人令「总额要写在流入前面」：
    #   要求把「全市场 ETF 合计净流入」从 etf_insight（卡片底部小字）**提到本条第 1 段**，
    #   放在「净流入TOP5」之前 ⇒ 读者第一眼就看到总量级。
    #   🔴 同时修口径失真（本改动的前提）：原 `net_total` 取的是
    #     `sum(top_inflow) + sum(top_outflow)`，即**两个 TOP5 之和**（10 只 ETF），
    #     却贴「全市场 ETF 合计净流入」标签 ⇒ 实测 09-17 线上显示 +1.01亿，
    #     而 etf_daily_monitor.json 的 `total_net`（全市场 1605 只真实合计）= +47.39亿，
    #     相差 47 倍。既然要挪到最显眼位置，必须用真实合计，否则是放大版失真。
    #     优先取 `total_net`；缺失时**降级为不显示总额**，绝不用 TOP5 之和冒充全市场。
    _total_net_yi = None
    if isinstance(etf_daily, dict) and etf_daily.get("total_net") is not None:
        try:
            _total_net_yi = float(etf_daily["total_net"]) / 1e8
        except (TypeError, ValueError):
            _total_net_yi = None
    if _total_net_yi is not None:
        _tn_color = "#ef5350" if _total_net_yi >= 0 else "#26a69a"   # 红涨绿跌铁律
        _etf_parts.append(
            '<span style="white-space:nowrap;">全市场ETF合计净'
            f'<span style="color:{_tn_color};font-weight:600;">'
            f'{"流入" if _total_net_yi >= 0 else "流出"} {_total_net_yi:+.2f}亿</span></span>'
        )

    if cat_nets and cat_nets[0][1] >= 5:
        # 分类概览（保留原有判断口径与阈值：≥+5亿 才报）
        _etf_parts.append("%sETF 净流入 %+.2f亿" % (_etf_cat_name(cat_nets[0][0], "in"), cat_nets[0][1]))
    if _etf_in5:
        # 品种之间不再用「、」分隔：各品种已是 inline-block 小块（自带右间距），
        # 中文顿号挤在两行块的基线上会错位。
        _etf_parts.append("净流入TOP5：" + "".join(_etf_in5))
    if _etf_out5:
        # 🛡 2026-09-17 主人令「流出换到第二行」：
        #   原写法把「净流出TOP5」接在同一条的「 ｜ 」之后，与流入挤在一行里，
        #   两段各含 5 个 inline-block 小方块 ⇒ 单行过长、右侧被卡片宽度截断。
        #   改为在本段前置一个「<br>」硬换行，"净流出TOP5" 另起一行（不再用 ｜ 连接）。
        #   ⚠️ 前端 anomalies 渲染走 innerHTML（index.html 内 h+=a.text），<br> 原样生效；
        #     已确认无任何脚本解析本条文本（update_v8 / audit_empty_cards / logic.html
        #     均只读键名或整体存在性）⇒ 引入 <br> 安全。
        _etf_parts.append("<br>" + "净流出TOP5：" + "".join(_etf_out5))
    elif len(cat_nets) >= 2 and cat_nets[-1][1] <= -3:
        # 兜底：etf_daily 排名缺失时改用分类口径的净流出，避免整条丢信息
        _etf_parts.append("<br>" + "%sETF 净流出 %+.2f亿" % (_etf_cat_name(cat_nets[-1][0], "out"), cat_nets[-1][1]))
    if _etf_parts:
        # 「 ｜ 」只在「同段内」连接；含 <br> 的段自身已换行，故先按段拼再整体 join。
        _etf_text = ""
        for _i, _seg in enumerate(_etf_parts):
            if _seg.startswith("<br>"):
                _etf_text += _seg                      # 自带换行，不再前置 ｜
            else:
                _etf_text += (" ｜ " if _i else "") + _seg
        anomalies.append({
            "tag": "ETF资金",
            "emoji": "💰",
            "text": _etf_text,
            "color": "gold",
            "signal": "green" if _etf_in5 else "red",
        })

    # 3b. ETF 真实行业资金 TOP5（2026-09-11 主人令：按真行业写）
    if etf_heat and etf_heat.get("industry_flow"):
        top5 = etf_heat["industry_flow"][:5]
        if top5:
            text = "ETF 真实行业资金 TOP5：" + "、".join(
                f"{x['name']} {x['net_inflow_yi']:+.1f}亿" for x in top5
            )
            anomalies.append({
                "tag": "ETF行业资金",
                "emoji": "🏭",
                "text": text,
                "color": "gold",
                "signal": "green" if top5[0].get("net_inflow_yi", 0) > 0 else "red",
            })

    # 4. 概念热点（前 5）
    # 🛡 2026-09-11 主人令：口径改为与「板块资金趋势·盘中追热」卡的【概念流入 TOP5】同源同口径
    #   （sector_fund_flow.json 里 type=='概念' 的前 5 名，净额降序），替代原 concept_ranking 的 3 条，
    #   让同一屏上两处「概念」永远同一批名字、同一个数。
    hot_concepts = sorted([s for s in _sector_list(sectors, "sectors_in")
                           if s.get("type") == "概念" and float(s.get("net") or 0) > 0],
                          key=lambda s: -float(s.get("net") or 0))[:5]
    if hot_concepts:
        anomalies.append({
            "tag": "概念热点",
            "emoji": "🔥",
            "text": f"主力流向：{'、'.join(f"{s['name']}(+{float(s['net']):.1f}亿)" for s in hot_concepts)}",
            "color": "red",
            "signal": "green",
        })

    # 4b. 行业资金（新建独立行）
    # 🛡 2026-09-11 主人令：行业单独成行，与概念分开写明白。
    #   大数 = 申万一级 31 行业净额（与卡片大数同口径）；
    #   流入 TOP5 / 流出 TOP3 = type=='行业'（东财行业，含二三级细分）；
    #   🛡 同数据、同父级的重复项只保留层级最高的一条（如 地面兵装Ⅱ/Ⅲ 各 +9.74亿 → 只留 Ⅱ），
    #     其余条目一律保留（2026-09-11 主人令：「同数据有同级的就保留一级，其他不变」）。
    #   ⚠️ 流出榜必须【按净额升序取前三】= 真实最大流出；卡片旧写法 sectors_out.slice(0,3)
    #   取的是文件里"最小流出"的三条（≈-0.01亿），显示无意义。
    ind_in = _dedupe_same_level(sorted(
        [s for s in _sector_list(sectors, "sectors_in") if s.get("type") == "行业"],
        key=lambda s: -float(s.get("net") or 0)))[:5]
    ind_out = _dedupe_same_level(sorted(
        [s for s in _sector_list(sectors, "sectors_out") if s.get("type") == "行业"],
        key=lambda s: float(s.get("net") or 0)))[:3]
    sw1_net = sw1_industry_net(sectors)
    if sw1_net is not None or ind_in:
        parts = []
        parts.append(f"净额(行业31)：{sw1_net:+.1f}亿" if sw1_net is not None else "净额(行业)：待更新")
        if ind_in:
            parts.append("流入：" + _fmt_sector_list(ind_in))
        if ind_out:
            parts.append("流出：" + _fmt_sector_list(ind_out, signed=True))
        anomalies.append({
            "tag": "行业资金",
            "emoji": "🏭",
            "text": " ｜ ".join(parts),
            "color": "blue",
            "signal": "red" if (sw1_net is not None and sw1_net < 0) else "green",
        })

    # 5. 个股主力异动（净流入 TOP5 / 净流出 TOP5）
    # 🛡 2026-09-16 主人令「写出具体的TOP5流入和流出」：原各取前 2 名 → 改为各取前 5 名。
    #    数据源 capital_flow_data.json 的 top_inflow / top_outflow 各含 20 条真实主力净额排名，取 5 条充足。
    #    ⚠️ 前端 index.html 会把这两条同 tag 记录合并渲染成一行（流入在前、流出在后），
    #       合并条件是「text 以『主力大单流入/流出』开头」——本处保持前缀不变，故前端无需改动。
    if capital and capital.get("top_inflow"):
        top = capital["top_inflow"][:5]
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
        bot = capital["top_outflow"][:5]
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
    # 🛡 2026-09-11：上限 5 → 6 —— 新增「行业资金」独立行后，若仍限 5 条会把原有的
    #   「涨停热度 / 个股异动」挤掉（行为回退）。
    seen = set()
    unique = []
    for a in anomalies:
        key = a["tag"] + a["text"]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique[:6]


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
    elif health["fund"][1] == "green" or health["emotion"][1] == "green":
        s = f"指数方向不明但个股活跃、资金偏暖，可轻指数重个股，聚焦{sector_str}，关注{pick_str}，严格止损。"
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

    # 主力资金净额：优先用全市场主力净额 market_net；回退用个股主力前排净流入+净流出合计（含方向）
    # 🛡 2026-09-08 一劳永逸修复：原 main_net=概念净流入前十之和，但 concept_ranking 仅含正净流入，
    #    → 永远正大数、阈值100恒绿、资金灯失去区分度。改用真实双向主力净额。
    market_net = capital.get("market_net") if capital else None
    if market_net is not None:
        main_net = market_net
    else:
        cap_in = sum(x.get("net", 0) for x in capital.get("top_inflow", [])[:20])
        cap_out = sum(x.get("net", 0) for x in capital.get("top_outflow", [])[:20])
        main_net = cap_in + cap_out

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
        # 🛡 2026-09-17 主人令「总额要写在流入前面」口径对齐（必须与 anomalies ETF资金条同源）：
        #   本条总额已提到 anomalies ETF资金条第 1 段（卡片上方醒目位），此处**不再重复报总额**，
        #   避免同页出现两个「合计净流入」且口径不一致（实测 09-17：旧 TOP5 之和 +1.01亿
        #   vs 真全市场 total_net +47.39亿，差 47 倍）。
        #   若确有 total_net 只保留在本条做补充说明，也不重复渲染 —— 直接跳过总额行。
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

    # 🔴 2026-09-13 阿狸咪的工程师 · 根因修复（CI 门禁「AI_MARKET_BRIEF 真错位」恒失败）：
    #   原 payload **只有 gen_time**，而全仓其它 raw 文件的日期字段都是 update_time
    #   （实测：ai_insights_compare / algo_track / avg_price_data 均为 update_time）。
    #   而 v8_verify_layer_parity.py 的 DATE_KEYS 顺序是
    #   ("update_time","calc_time","gen_time",...) ⇒ 取「第一个命中项」：
    #     raw 侧只能取到 gen_time，data 侧优先取到 update_time
    #     （update_v8.py:stamp_missing_update_time() 在构建时把文件 mtime 补成 update_time）。
    #   ⇒ 两侧读的不是同一个字段，日期天然可能不一致 ⇒ 跨零点构建必判「真错位」阻断部署
    #     （2026-09-14 00:12 构建实证：raw=09-13 15:40:41 vs data=09-14 00:12:27）。
    #   修法：补一个与 gen_time **同值**的 update_time，让两侧口径一致。
    #   ⚠️ 一次取值两字段共用（禁两次 datetime.now()，防跨秒产生两个不同值）。
    #   ⚠️ 保留 gen_time 不动 ⇒ 前端/其他消费方零影响（向后兼容）。
    #   ⚠️ 语义诚实：该时刻既是生成时刻也是本数据的新鲜度时刻，同值是事实，非造假。
    _brief_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    brief = {
        "gen_time": _brief_now,
        "update_time": _brief_now,
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
