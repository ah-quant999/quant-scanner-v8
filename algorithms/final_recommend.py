#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""final_recommend.py — 跨策略共振 + 板块强度 生成最终推荐 Top3

输入：
  - raw_data/triple_consensus.json
  - raw_data/cockpit_tier_recommend.json
  - raw_data/top10_daily.json   (四量终极 / 主站 TOP10)
  - raw_data/crds_card_data.json (逆势龙头)
  - raw_data/lhb_data.json      (龙虎榜 → 大牛股猎手机游共振)
  - raw_data/sector_rs.json     (板块相对强度)
  - raw_data/stock_profile.json (个股行业/概念)
  - raw_data/crisis_data.json   (危机雷达，决定是否并入逆势龙头)
  - raw_data/cockpit_backtest.json (驾驶舱历史回测，用于 Top3 回测/跟踪)
  - raw_data/triple_track.json     (三重跟踪告警，用于 Top3 跟踪)

输出：
  - raw_data/final_recommend.json
  - data/FINAL_RECOMMEND_DATA.js

统一优先级分 = Σ(源强度分) + 共振次数×1.5 + 板块强度加分
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

CRISIS_HIGH_THRESHOLD = 50  # 危机雷达≥50才并入逆势龙头
SECTOR_TOP_N = 15
TOP_N = 3
HK_PENALTY = 1.5        # 港股分值惩罚（用户主做 A 股，港股不应霸榜 TOP_N）
MIN_A_SHARES_IN_TOP = max(1, TOP_N - 1)  # TOP_N 中至少保留 N-1 只 A 股

# 常见港股/美股代码兜底名称表（当上游 name 缺失或等于 code 时使用）
# 格式：统一用纯数字 code（无 hk/sh 前缀）作为 key
NAME_FIX_MAP = {
    "00700": "腾讯控股",
    "09988": "阿里巴巴-W",
    "01024": "快手-W",
    "09618": "京东物流",
    "01093": "石药集团",
    "03690": "美团-W",
    "01810": "小米集团-W",
    "02331": "李宁",
    "02015": "理想汽车-W",
    "09888": "百度集团-SW",
    "06060": "众安在线",
    "01299": "友邦保险",
    "02318": "中国平安",
    "03988": "中国银行",
    "01398": "工商银行",
    "00939": "建设银行",
    "01208": "五矿资源",
    "00883": "中国海洋石油",
    "00857": "中国石油股份",
    "00386": "中国石油化工股份",
    "02628": "中国人寿",
    "02328": "中国财险",
    "03328": "交通银行",
    "06818": "中国光大银行",
    "01988": "民生银行",
    "01658": "邮储银行",
    "01199": "中远海运港口",
    "00489": "东风集团股份",
    "01797": "新东方在线",
    "02020": "安踏体育",
    "02319": "蒙牛乳业",
    "01898": "中煤能源",
    "01088": "中国神华",
    "00358": "江西铜业股份",
    "02600": "中国铝业",
    "01776": "广发证券",
    "06837": "海通证券",
    "06030": "中信证券",
    "03908": "中金公司",
    "06690": "海尔智家",
    "09633": "农夫山泉",
    "09868": "小鹏汽车-W",
    "02018": "瑞声科技",
    "02382": "舜宇光学科技",
    "01478": "丘钛科技",
    "02899": "紫金矿业",
    "01787": "山东黄金",
    # 2026-08-11 补：今日候选池出现的港股（之前缺失导致 09866/02269 等显示代码而非名称）
    # 同步 raw_data/candidate.json 中实际命中的 14 只港股，确保最终推荐卡 name 字段正确
    "00388": "香港交易所",
    "01209": "华润万象生活",
    "01211": "比亚迪股份",
    "01801": "信达生物",
    "02269": "药明生物",
    "02359": "药明康德",
    "06160": "百济神州",
    "06618": "京东健康",
    "06990": "科伦博泰",
    "09866": "蔚来-SW",
}


def fix_name(code, name):
    """如果 name 为空或与 code 相同，用兜底映射表/画像修复。

    2026-08-11 修复：NAME_FIX_MAP 优先级 > profile name。
    背景：stock_profile.json 中 09618 给的是「京东集团-SW」（错），而港交所标准名称是「京东物流」。
    原逻辑「profile name 存在即用」会让上游 profile 的错误名称覆盖 NAME_FIX_MAP 标准名。
    改为"标准名映射表兜底优先"，保证 09988/09618/09866/00700 等港股始终显示标准中文名。
    """
    c = norm_code(code)
    n = (name or "").strip()
    # 1) 标准映射表优先（防 profile 错覆盖标准名）
    if c in NAME_FIX_MAP:
        return NAME_FIX_MAP[c]
    # 2) profile name 合法时退回 profile
    if n and n != c:
        return n
    # 3) 兜底
    return n or c


def load_js(name, var_name):
    """读取 data/xxx.js（window.X = {...}; 格式）并返回 JSON 对象"""
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.strip()
        if text.startswith("window." + var_name):
            text = text.split("=", 1)[1]
        text = text.rstrip(";\n ")
        return json.loads(text)
    except Exception as e:
        print(f"[warn] 读取 JS 失败 {name}: {e}")
        return {}


def load_json(name):
    path = os.path.join(RAW, name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] 读取失败 {name}: {e}")
        return {}


def norm_code(c):
    return str(c or "").replace("sh", "").replace("sz", "").replace("bj", "").replace("hk", "").replace("_", "").strip()


def market_prefix(code):
    c = str(code or "").strip()
    if not c:
        return "sz"
    # 港股：5 位纯数字（A股为 6 位）
    if c.isdigit() and len(c) == 5:
        return "hk"
    if c.startswith(("300", "301")):
        return "sz"
    if c.startswith(("688", "689")):
        return "sh"
    if c.startswith(("8", "4", "92")):
        return "bj"
    if c.startswith(("6",)):
        return "sh"
    if c.startswith(("0", "3")):
        return "sz"
    return "sz"


def board_from_code(code, market=None):
    c = str(code or "")
    m = str(market or "").lower()
    # 港股：5 位纯数字（A股为 6 位），或显式 market 为港股
    if m in ("hk", "港股") or (c.isdigit() and len(c) == 5):
        return "港股"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith("688"):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return "主板"


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def build_sector_maps(sector_rs):
    sectors = sector_rs.get("sectors") or []
    strong_rel = sector_rs.get("strong_relative_5d") or []
    strong_abs = sector_rs.get("strong_5d") or []

    rel_set = set()
    abs_set = set()
    score_map = {}

    for s in sectors:
        name = s.get("name")
        if not name:
            continue
        score_map[name] = {
            "relative_5d": safe_float(s.get("relative_5d")),
            "pct_5d": safe_float(s.get("pct_5d")),
            "pct_20d": safe_float(s.get("pct_20d")),
        }

    for item in strong_rel[:SECTOR_TOP_N]:
        if isinstance(item, dict):
            rel_set.add(item.get("name"))
        else:
            rel_set.add(item)
    for item in strong_abs[:SECTOR_TOP_N]:
        if isinstance(item, dict):
            abs_set.add(item.get("name"))
        else:
            abs_set.add(item)

    # 额外把贵金属/黄金概念/小金属/有色金属也纳入强板块集合
    for s in sectors:
        name = s.get("name", "")
        if any(k in name for k in ("贵金属", "黄金", "小金属", "有色金属")):
            rel_set.add(name)
            if safe_float(s.get("relative_5d")) > 0 or safe_float(s.get("pct_5d")) > 0:
                score_map.setdefault(name, {})

    return rel_set, abs_set, score_map


def sector_score_for(stock, rel_set, abs_set, score_map):
    """返回 (板块加分, [hit对象, ...])。
    hit 对象含 name/pct_5d/relative_5d/strong，便于前端展示「关联板块资金」。
    """
    hits = []
    score = 0.0
    seen = set()

    CONCEPT_ALIASES = {
        "黄金概念": "贵金属",
        "小金属概念": "小金属",
        "稀土永磁": "小金属",
        "有色金属": "有色金属",
        "半导体概念": "半导体",
    }

    def make_hit(name):
        info = score_map.get(name) or {}
        return {
            "name": name,
            "pct_5d": safe_float(info.get("pct_5d")),
            "relative_5d": safe_float(info.get("relative_5d")),
            "strong": name in rel_set,
        }

    def hit(name):
        nonlocal score
        if name in seen:
            return
        seen.add(name)
        if name in rel_set:
            hits.append(make_hit(name))
            score += 1.0
        elif name in abs_set:
            hits.append(make_hit(name))
            score += 0.5

    def hit_alias(name):
        hit(name)
        alias = CONCEPT_ALIASES.get(name)
        if alias and alias != name:
            hit(alias)

    ind = stock.get("industry") or ""
    if ind:
        hit_alias(ind)

    for c in stock.get("concepts") or []:
        hit_alias(c)

    # 名称/行业/概念中显含贵金属/黄金/小金属/有色的，直接补分
    name = stock.get("name", "")
    has_metal_keyword = (
        any(k in name for k in ("黄金", "中金", "银泰", "赤峰", "山东", "紫金", "湖南")) and "金" in name
    )
    for raw in [ind] + (stock.get("concepts") or []):
        if isinstance(raw, str) and any(k in raw for k in ("黄金", "贵金属", "小金属", "有色金属")):
            has_metal_keyword = True
            break
    if has_metal_keyword and not any("黄金" in h["name"] or "贵金属" in h["name"] or "小金属" in h["name"] or "有色" in h["name"] for h in hits):
        score += 0.8
        hits.append({"name": "贵金属/有色(关键词)", "pct_5d": 0.0, "relative_5d": 0.0, "strong": True})

    return round(score, 2), hits


def main():
    triple = load_json("triple_consensus.json")
    cockpit = load_json("cockpit_tier_recommend.json")
    top10 = load_json("top10_daily.json")
    crds = load_json("crds_card_data.json")
    lhb = load_json("lhb_data.json")
    sector_rs = load_json("sector_rs.json")
    profile = load_json("stock_profile.json")
    crisis = load_json("crisis_data.json")
    gold_pool = load_json("gold_pool.json")

    rel_set, abs_set, score_map = build_sector_maps(sector_rs)

    # 读取 STOCK_STOP_DATA.js（支撑/压力/ATR）
    stop_data = load_js("STOCK_STOP_DATA.js", "STOCK_STOP_DATA")
    stop_stocks = stop_data.get("stocks") or {}

    # ── 读取 60min 四量终极共振数据（多周期确认）──
    _60m_raw = load_js("FOUR_VOLUME_60M.js", "FOUR_VOLUME_60M")
    _60m_hits = {}  # norm_code → {reason, signals[], qd, pct_chg, ...}
    for item in (_60m_raw.get("hits") or _60m_raw.get("stocks") or []):
        c = norm_code(item.get("code") or item.get("code"))
        if c:
            _60m_hits[c] = item
    print(f"[info] 60m 四量数据: 加载 {len(_60m_hits)} 只命中")

    # 读取回测/跟踪数据（用于 Top3 卡片展示）
    cb = load_json("cockpit_backtest.json")
    cb_summary = {x.get("code"): x for x in (cb.get("stock_summary") or []) if x.get("code")}
    cb_results = {}
    for r in cb.get("results") or []:
        code = r.get("code")
        if not code:
            continue
        if code not in cb_results:
            cb_results[code] = []
        cb_results[code].append(r)
    # 按 entry_date 取最新结果
    for code in cb_results:
        cb_results[code].sort(key=lambda x: x.get("entry_date", ""), reverse=True)

    tt = load_json("triple_track.json")
    tt_alerts = {}
    for a in tt.get("alerts") or []:
        code = a.get("code")
        if not code:
            continue
        tt_alerts.setdefault(code, []).append(a)

    # 综合回测策略级统计（个股无历史时作为策略置信度展示）
    # cockpit_backtest.json 顶层字段即整体统计
    strategy_backtest = {
        "total": cb.get("total_count"),
        "win_rate": cb.get("win_rate"),
        "avg_return": cb.get("avg_return"),
        "best_return": cb.get("best_return"),
        "worst_return": cb.get("worst_return"),
        "valid": cb.get("total_count"),
        "best_hold_days": 3,  # 驾驶舱回测按固定窗口
    }

    crisis_score = safe_float(crisis.get("score"), 0.0)
    crisis_high = crisis_score >= CRISIS_HIGH_THRESHOLD

    profiles = (profile or {}).get("profiles") or {}

    pool = defaultdict(lambda: {
        "code": "",
        "name": "",
        "market": "",
        "board": "",
        "close": None,
        "pct_chg": None,
        "stop_loss": None,
        "target_price": None,
        "risk_reward": None,
        "support": None,
        "resistance": None,
        "atr": None,
        "sources": [],
        "source_scores": {},
        "industry": "",
        "concepts": [],
        "reasons": [],
        "signals": [],           # 中文信号标签
        "enter_dates": [],         # 各源记录的入选日
        "sector_hits": [],         # 板块命中（带涨幅）
    })

    def ensure(code, name, market, board):
        r = pool[norm_code(code)]
        if not r["code"]:
            r["code"] = code
            r["name"] = fix_name(code, name)
            r["market"] = market or market_prefix(code)
            r["board"] = board or board_from_code(code)
            # 从 STOCK_STOP_DATA 预填支撑/压力/ATR/止损/目标（如存在）
            ss = stop_stocks.get(norm_code(code)) or stop_stocks.get(code)
            if ss:
                for k in ["support", "resistance", "atr", "stop_loss", "target_price", "risk_reward"]:
                    if ss.get(k) is not None:
                        r[k] = ss[k]
        else:
            # 已有记录时，若旧 name 为空/等于 code，尝试用新 name/映射表更新
            if not r["name"] or r["name"] == r["code"]:
                r["name"] = fix_name(code, name)
        return r

    # 1) 三重共识
    for s in triple.get("stocks") or []:
        code = s.get("code")
        if not code:
            continue
        r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
        score = safe_float(s.get("total_score") or s.get("score"))
        src_score = min(4.0, max(1.0, score / 20.0)) if score >= 25 else 0.0
        if src_score > 0:
            r["sources"].append("三重共识")
            r["source_scores"]["三重共识"] = round(src_score, 2)
            r["close"] = s.get("close") or r["close"]
            r["pct_chg"] = s.get("pct_chg") or r["pct_chg"]
            r["stop_loss"] = s.get("stop_loss") or r["stop_loss"]
            r["target_price"] = s.get("target_price") or r["target_price"]
            r["risk_reward"] = s.get("risk_reward") or r["risk_reward"]
            r["industry"] = r["industry"] or (s.get("industry") or "")
            r["concepts"] = list(set((r["concepts"] or []) + (s.get("concepts") or [])))
            r["reasons"].append(f"三重共识 评分{score:.0f}")
            r["signals"].append("跨策略共振")
            if s.get("enter_date"):
                r["enter_dates"].append(s["enter_date"])

    # 2) 驾驶舱 A/B 档
    for tier, label in [("tier_a", "驾驶舱A档"), ("tier_b", "驾驶舱B档")]:
        for s in cockpit.get(tier) or []:
            code = s.get("code")
            if not code:
                continue
            r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
            tech = safe_float(s.get("tech_score"))
            qs = safe_float(s.get("quality_score"))
            total = safe_float(s.get("total_score")) or (tech + qs)
            if tier == "tier_a":
                src_score = 2.5 + min(1.5, max(0.0, (total - 50) / 50.0 * 1.5))
            else:
                src_score = 1.0
            r["sources"].append(label)
            r["source_scores"][label] = round(src_score, 2)
            r["industry"] = r["industry"] or (s.get("industry") or "")
            r["concepts"] = list(set((r["concepts"] or []) + (s.get("concepts") or [])))
            r["reasons"].append(f"{label} 技术{tech:.0f} 质量{qs:.0f}")
            # ── 60m 共振确认（A 档仅标签，不改变评分）──
            _60m_a = _60m_hits.get(norm_code(code))
            if _60m_a and tier == "tier_a":
                r["signals"].append("60m共振确认")
                r["_60m_resonance"] = True
            # ── end 60m ──
            if s.get("comment"):
                r["signals"].append(s["comment"])
            if s.get("enter_date"):
                r["enter_dates"].append(s["enter_date"])

    # 3) 四量终极 (top10_daily.top10)
    SIG_MAP = {
        "chan": "缠论买点",
        "jinzuan": "金钻信号",
        "jigou": "机构变红",
        "trend": "上涨趋势",
        "form_A": "形态A",
    }
    for s in top10.get("top10") or []:
        code = s.get("code")
        if not code:
            continue
        r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
        sig_count = safe_float(s.get("sig_count"))
        qd = bool(s.get("qd"))
        src_score = sig_count * 0.6
        if qd:
            src_score += 0.5
        # ── 60min 多周期共振加分（同算法不同时间框架 = 经典共振）──
        _60m_item = _60m_hits.get(norm_code(code))
        if _60m_item:
            _60m_qd = bool(_60m_item.get("qd") or _60m_item.get("XG"))
            _60m_bonus = 0.8 if _60m_qd else 0.5
            src_score += _60m_bonus
            r["signals"].append("60min多周期共振")
            r["_60m_resonance"] = True
        # ── end 60m ──
        src_score = round(min(4.5, max(0.0, src_score)), 2)
        if src_score > 0:
            r["sources"].append("四量终极")
            r["source_scores"]["四量终极"] = src_score
            r["close"] = s.get("close") or r["close"]
            r["pct_chg"] = s.get("pct_chg") or r["pct_chg"]
            r["stop_loss"] = s.get("stop_loss") or r["stop_loss"]
            r["target_price"] = s.get("target_price") or r["target_price"]
            r["risk_reward"] = s.get("risk_reward") or r["risk_reward"]
            r["industry"] = r["industry"] or ""
            r["concepts"] = list(set((r["concepts"] or []) + (s.get("sectors") or [])))
            r["reasons"].append(f"四量终极 信号{sig_count:.0f}项")
            for k, label in SIG_MAP.items():
                if s.get("signals", {}).get(k):
                    r["signals"].append(label)
            if qd:
                r["signals"].append("主力动量翻多")
            if s.get("enter_date"):
                r["enter_dates"].append(s["enter_date"])
            elif top10.get("update_time"):
                r["enter_dates"].append(top10["update_time"][:10])

    # 4) 全站精选：与驾驶舱A/B档同源，不再重复计分，但保留源标签用于展示
    #    （后续 render 时可单独展示 A/B 档）

    # 5) 逆势龙头：仅在危机雷达高位时并入
    if crisis_high:
        for tier, label, base in [
            ("elite", "逆势龙头·精锐", 3.0),
            ("advanced", "逆势龙头·进阶", 2.0),
            ("watch", "逆势龙头·观察", 1.0),
        ]:
            for s in crds.get(tier) or []:
                code = s.get("code")
                if not code:
                    continue
                r = ensure(code, s.get("name"), "", "")
                r["sources"].append(label)
                r["source_scores"][label] = round(base, 2)
                r["reasons"].append(f"{label} 评分{s.get('score')}")
                r["signals"].append(f"{label}")
                if s.get("enter_date"):
                    r["enter_dates"].append(s["enter_date"])

    # 6) 大牛股猎手：龙虎榜机构+游资共振
    for s in lhb.get("stocks") or []:
        inst = safe_float(s.get("inst_net_万"))
        yz = safe_float(s.get("yz_net_万"))
        if inst > 0 and yz > 0:
            code = s.get("code")
            if not code:
                continue
            r = ensure(code, s.get("name"), "", "")
            src_score = min(3.5, 2.0 + (inst + yz) / 80000.0)
            # ── 60min 动量延续确认（龙虎榜 T 日进场 → T+1 分钟级动量仍在 = 非一日游）──
            _60m_lhb = _60m_hits.get(norm_code(code))
            if _60m_lhb:
                _60m_lhb_bonus = 0.5
                src_score += _60m_lhb_bonus
                r["signals"].append("60min动量延续")
                r["_60m_resonance"] = True
            # ── end 60m ──
            src_score = round(min(4.0, src_score), 2)
            r["sources"].append("大牛股猎手")
            r["source_scores"]["大牛股猎手"] = round(src_score, 2)
            r["close"] = s.get("close") or r["close"]
            r["pct_chg"] = s.get("pct") or r["pct_chg"]
            r["reasons"].append(f"大牛股猎手 机构{inst/10000:.1f}亿+游资{yz/10000:.1f}亿")
            r["signals"].append(s.get("category") or "机游共振")
            if s.get("reason"):
                r["signals"].append(s["reason"])
            if lhb.get("date"):
                r["enter_dates"].append(lhb["date"])

    # 7) 板块龙头：当前强势板块里的金股池成员（让“板块强→个股被推”生效）
    gp_stocks = gold_pool.get("stocks") or {}
    if isinstance(gp_stocks, dict):
        gp_items = list(gp_stocks.values())
    else:
        gp_items = list(gp_stocks)
    for s in gp_items:
        code = s.get("code") if isinstance(s, dict) else None
        if not code:
            continue
        # 先补齐画像
        prof = profiles.get(norm_code(code)) or profiles.get(code)
        tmp_stock = {
            "industry": s.get("industry") or (prof.get("industry") if prof else "") or "",
            "concepts": list(set((s.get("concepts") or []) + (prof.get("concepts") if prof else []))),
            "name": s.get("name", ""),
        }
        sec_score, sec_hits = sector_score_for(tmp_stock, rel_set, abs_set, score_map)
        if sec_score <= 0:
            continue
        # 只取每个强势板块里综合板块分最高的前若干只，避免噪声
        r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
        src_score = round(min(3.0, 0.5 + sec_score), 2)
        r["sources"].append("板块龙头")
        r["source_scores"]["板块龙头"] = src_score
        r["industry"] = r["industry"] or tmp_stock["industry"]
        r["concepts"] = list(set(r["concepts"] + tmp_stock["concepts"]))
        r["close"] = s.get("close") or r["close"]
        r["pct_chg"] = s.get("pct_chg") or r["pct_chg"]
        r["stop_loss"] = s.get("stop_loss") or r["stop_loss"]
        r["target_price"] = s.get("target_price") or r["target_price"]
        r["risk_reward"] = s.get("risk_reward") or r["risk_reward"]
        r["reasons"].append(f"板块龙头 {','.join([h['name'] for h in sec_hits[:2]])}")
        r["signals"].append("板块强势")
        # 合并板块命中（去重），保留涨幅
        existing = {h["name"] for h in r["sector_hits"]}
        for h in sec_hits:
            if h["name"] not in existing:
                r["sector_hits"].append(h)
                existing.add(h["name"])
        if s.get("first_date"):
            r["enter_dates"].append(s["first_date"])

    # 补齐个股画像（行业/概念/名称）
    for key, r in pool.items():
        prof = profiles.get(key) or profiles.get(norm_code(key))
        if prof:
            if not r["name"] or r["name"] == r["code"]:
                r["name"] = fix_name(r["code"], prof.get("name"))
            if not r["industry"]:
                r["industry"] = prof.get("industry") or ""
            if prof.get("concepts"):
                r["concepts"] = list(set(r["concepts"] + prof.get("concepts")))

    # 计算板块加分 与 最终分
    scored = []
    for key, r in pool.items():
        if len(r["sources"]) == 0:
            continue
        sec_score, fresh_hits = sector_score_for(r, rel_set, abs_set, score_map)
        # 合并板块命中（板块龙头已写入部分命中）
        existing = {h["name"] for h in r["sector_hits"]}
        for h in fresh_hits:
            if h["name"] not in existing:
                r["sector_hits"].append(h)
                existing.add(h["name"])
        resonance = len(set(r["sources"]))
        strength = sum(r["source_scores"].values())
        final_score = strength + resonance * 1.5 + sec_score
        # 港股惩罚：用户主做 A 股，港股不应因多源共振天然霸榜
        if r.get("board") == "港股" or market_prefix(r.get("code", "")) == "hk":
            final_score -= HK_PENALTY
        scored.append({
            **r,
            "key": key,
            "resonance": resonance,
            "strength": round(strength, 2),
            "sector_score": sec_score,
            "sector_hits": r["sector_hits"],
            "final_score": round(final_score, 2),
        })

    # 排序：先按共振次数，再按综合分，再按源强度（多源共振优先）
    scored.sort(key=lambda x: (x["resonance"], x["final_score"], x["strength"]), reverse=True)

    # ── A 股保底：TOP_N 中至少保留 MIN_A_SHARES_IN_TOP 只 A 股（用户主做 A 股）──
    # 2026-08-11 修复：原逻辑先 for s in a_shares 取满 TOP_N，再 for s in hk_stocks 判断——
    #   导致 a_shares 直接灌满 3 个 slot，共振=2 的高分港股（09988/09618/06618）全部挡在 Top3 外面，
    #   而 3 只大牛股猎手低分 A 股（3.68/3.75/4.69）强行霸榜 ——"其他算法没跑出来更好的"就是这个 bug。
    # 现改为：先取 A 股前 (MIN_A_SHARES_IN_TOP-1) 只作为硬保底，
    #         余下 slot 从 scored 全局高分（含 A 股+港股，港股已 HK_PENALTY 减分）填补——
    #         共振次数高的港股就能挤进 Top3。
    a_shares = [s for s in scored if s.get("board") != "港股" and market_prefix(s.get("code", "")) != "hk"]
    hk_stocks = [s for s in scored if s.get("board") == "港股" or market_prefix(s.get("code", "")) == "hk"]
    top = []
    # 1) A 股硬保底 = MIN_A_SHARES_IN_TOP-1 只（=TOP_N-2 只，最少保留 1 只"硬 A 股"作为看 A 股主盘的入口）
    hard_a = max(0, MIN_A_SHARES_IN_TOP - 1)
    for s in a_shares:
        if len(top) >= TOP_N or len(top) >= hard_a:
            break
        top.append(s)
    # 2) 余下 slot 从 scored 全局高分填补（scored 已按 (resonance, final_score, strength) 排好）
    top_codes = {t["key"] for t in top}
    for s in scored:
        if len(top) >= TOP_N:
            break
        if s["key"] in top_codes:
            continue
        top.append(s)
        top_codes.add(s["key"])
    # 3) 排序保持 (resonance, final_score, strength) — 保证 Top3 顺序与候选池一致
    top.sort(key=lambda x: (x["resonance"], x["final_score"], x["strength"]), reverse=True)
    top = top[:TOP_N]
    # ── end A 股保底 ──

    def horizon_for(sources, resonance=0, is_top=False):
        """horizon 判定
        is_top=True (top3/Allsite A/B档 持仓层):
          严格按 sources——主推"短线择时买入"，跨策略仍标"短线/中线共振"
        is_top=False (候选池/research 视角):
          放宽——含中线策略 或 多源短线共振 ≥2 自动归"中长线"，避免 longList 永远空
        2026-08-11 主人令：候选池的中长线列之前永远"暂无"——是判定过严。
        """
        short = {"四量终极", "大牛股猎手", "板块龙头"}
        mid = {"三重共识", "驾驶舱A档", "驾驶舱B档"}
        defense = {"逆势龙头·精锐", "逆势龙头·进阶", "逆势龙头·观察"}
        srcs = set(sources)
        has_short = bool(srcs & short)
        has_mid = bool(srcs & mid)
        has_defense = bool(srcs & defense)
        if has_defense:
            return "中线防御"
        if is_top:
            # 严格按 sources 划分（top3 仍按短线择时语义）
            if has_short and has_mid: return "短线/中线共振"
            if has_short: return "短线"
            if has_mid: return "中长线"
            return "短线"
        # 候选池放宽：含中线策略 → 中长线 / 多源短线共振≥2 → 中长线
        if has_mid:
            return "中长线"
        if has_short and resonance >= 2:
            return "中长线"
        return "短线"

    # 清理输出字段
    out_stocks = []
    for s in top:
        code = norm_code(s["code"])
        # market 统一为交易所前缀；原始 s["market"] 可能是中文描述，不可靠
        market = market_prefix(code)
        board = s["board"] or board_from_code(code)
        close = safe_float(s["close"])
        stop = s["stop_loss"]
        target = s["target_price"]
        rr = s["risk_reward"]
        # 若缺少精确 stop/target，用 fixedP10/rrK1.5 兜底
        if close and not stop:
            pct = 0.90 if board in ("创业板", "科创板") else 0.93
            stop = round(close * pct, 2)
            target = round(close * (1 + (1 - pct) * 1.5), 2)
            rr = 1.5
        # 关联板块资金：取命中板块涨幅前 4
        sector_fund = []
        for h in (s.get("sector_hits") or [])[:4]:
            if "关键词" in h["name"]:
                continue
            sector_fund.append({
                "name": h["name"],
                "pct_5d": round(h["pct_5d"], 2),
                "relative_5d": round(h["relative_5d"], 2),
                "strong": h["strong"],
            })
        # 入选日：取各源最早日期，无则使用当前 update_time
        enter_dates = [d for d in (s.get("enter_dates") or []) if d]
        enter_date = min(enter_dates) if enter_dates else datetime.now().strftime("%Y-%m-%d")
        signals = sorted(set(s.get("signals") or []))
        if not signals:
            # 兜底：根据来源生成一句信号
            signals = [f"{src}共振" for src in sorted(set(s["sources"]))]

        # ---- 回测 & 跟踪（当前 Top3 股票的历史表现与入选后状态） ----
        summary = cb_summary.get(code)
        latest_result = cb_results.get(code, [None])[0]
        alerts = tt_alerts.get(code, [])

        if summary and summary.get("signals", 0) > 0:
            backtest = {
                "signals": int(summary.get("signals") or 0),
                "win_count": int(summary.get("win_count") or 0),
                "loss_count": int(summary.get("loss_count") or 0),
                "win_rate": round(safe_float(summary.get("win_rate")), 1),
                "avg_return": round(safe_float(summary.get("avg_return")), 2),
                "best_return": round(safe_float(summary.get("best_return")), 2),
                "worst_return": round(safe_float(summary.get("worst_return")), 2),
                "note": f"该股历史共触发 {summary.get('signals')} 次驾驶舱/共振信号",
            }
        elif strategy_backtest:
            # 个股无历史：展示策略级回测作为参考
            best_hold = strategy_backtest.get("best_hold_days")
            backtest = {
                "signals": int(strategy_backtest.get("total_signals") or strategy_backtest.get("valid_signals") or strategy_backtest.get("total") or 0),
                "win_rate": round(safe_float(strategy_backtest.get("best_hold_win_rate") or strategy_backtest.get("win_rate")), 1),
                "avg_return": round(safe_float(strategy_backtest.get("best_hold_avg_return") or strategy_backtest.get("avg_return")), 2),
                "best_hold_days": best_hold,
                "note": f"个股暂无历史信号，展示策略级统计（最佳持有 {best_hold} 天）",
            }
        else:
            backtest = {"signals": 0, "win_rate": 0.0, "avg_return": 0.0, "note": "暂无回测数据"}

        if latest_result:
            entry_price = safe_float(latest_result.get("entry_price"))
            latest_price = safe_float(latest_result.get("latest_price"))
            ret = safe_float(latest_result.get("return_pct"))
            tracking = {
                "entry_date": latest_result.get("entry_date") or enter_date,
                "entry_price": round(entry_price, 2) if entry_price else None,
                "latest_price": round(latest_price, 2) if latest_price else None,
                "return_pct": round(ret, 2),
                "hold_days": int(latest_result.get("hold_days") or 1),
                "exit_type": latest_result.get("exit_type") or "hold",
                "stop_loss": round(safe_float(latest_result.get("stop_loss")), 2) if latest_result.get("stop_loss") is not None else None,
                "target_price": round(safe_float(latest_result.get("target_price")), 2) if latest_result.get("target_price") is not None else None,
                "note": "已入场跟踪中" if (latest_result.get("exit_type") == "hold" or latest_result.get("hold_days", 1) <= 1) else "已触发退出",
            }
        elif close:
            # 没有历史跟踪记录：以今日入选价 = 当前价展示
            tracking = {
                "entry_date": enter_date,
                "entry_price": round(close, 2),
                "latest_price": round(close, 2),
                "return_pct": 0.0,
                "hold_days": 1,
                "exit_type": "hold",
                "note": "今日新入选，自动开始跟踪",
            }
        else:
            tracking = {"entry_date": enter_date, "entry_price": None, "latest_price": None, "return_pct": None, "hold_days": 1, "exit_type": "hold", "note": "等待行情数据开始跟踪"}

        if alerts:
            tracking["alerts"] = alerts[:3]

        out_stocks.append({
            "rank": len(out_stocks) + 1,
            "code": code,
            "name": fix_name(code, s["name"]),
            "market": market,
            "board": board,
            "horizon": horizon_for(s["sources"], s.get("resonance",0), is_top=True),
            "close": round(close, 2) if close else None,
            "pct_chg": safe_float(s["pct_chg"]),
            "stop_loss": round(safe_float(stop), 2) if stop else None,
            "target_price": round(safe_float(target), 2) if target else None,
            "risk_reward": round(safe_float(rr), 2) if rr else None,
            "support": round(safe_float(s.get("support")), 2) if s.get("support") else None,
            "resistance": round(safe_float(s.get("resistance")), 2) if s.get("resistance") else None,
            "atr": round(safe_float(s.get("atr")), 2) if s.get("atr") else None,
            "sources": sorted(set(s["sources"])),
            "source_scores": s["source_scores"],
            "resonance": s["resonance"],
            "strength": s["strength"],
            "sector_score": s["sector_score"],
            "sector_hits": s["sector_hits"],
            "sector_fund": sector_fund,
            "final_score": s["final_score"],
            "buy_score": s["final_score"],
            "enter_date": enter_date,
            "signals": signals[:8],
            "_60m_resonance": s.get("_60m_resonance", False),
            "reason": "；".join(s["reasons"][:3]),
            "industry": s["industry"],
            "concepts": s["concepts"][:6],
            "backtest": backtest,
            "tracking": tracking,
        })

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crisis_score": round(crisis_score, 1),
        "crisis_high": crisis_high,
        "crisis_note": "逆势龙头已并入" if crisis_high else "危机雷达未达高位，逆势龙头暂不并入",
        "total_candidates": len(scored),
        "top_n": TOP_N,
        "strong_sectors": sorted(rel_set)[:20],
        "stocks": out_stocks,
        "all_candidates": [
            {
                "code": x["key"],
                "name": fix_name(x["key"], x["name"]),
                "market": {"sh": "沪市", "sz": "深市", "bj": "北交所", "hk": "港股"}.get((x["market"] or market_prefix(x["key"])).lower(), x["market"] or market_prefix(x["key"])),
                "board": x["board"] or board_from_code(x["key"], x["market"]),
                "horizon": horizon_for(x["sources"], x.get("resonance",0)),
                "close": round(safe_float(x["close"]), 2) if safe_float(x["close"]) else None,
                "pct_chg": safe_float(x["pct_chg"]),
                "final_score": x["final_score"],
                "resonance": x["resonance"],
                "sources": sorted(set(x["sources"])),
                "signals": sorted(set(x.get("signals") or []))[:6],
                "industry": x.get("industry", ""),
                "concepts": x.get("concepts", [])[:6],
                "enter_date": (min([d for d in x.get("enter_dates", []) if d]) if x.get("enter_dates") else None) or datetime.now().strftime("%Y-%m-%d"),
                "stop_loss": round(safe_float(x.get("stop_loss")), 2) if x.get("stop_loss") is not None else None,
                "target_price": round(safe_float(x.get("target_price")), 2) if x.get("target_price") is not None else None,
                "risk_reward": round(safe_float(x.get("risk_reward")), 2) if x.get("risk_reward") is not None else None,
                "support": round(safe_float(x.get("support")), 2) if x.get("support") is not None else None,
                "resistance": round(safe_float(x.get("resistance")), 2) if x.get("resistance") is not None else None,
            }
            for x in scored[:30]
        ],
    }

    # 写 raw_data json
    out_path = os.path.join(RAW, "final_recommend.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[ok] {out_path}  top3={len(out_stocks)} total_candidates={len(scored)}")

    # 写 data js
    js_path = os.path.join(DATA, "FINAL_RECOMMEND_DATA.js")
    js = "window.FINAL_RECOMMEND_DATA = " + json.dumps(result, ensure_ascii=False, indent=2) + ";"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"[ok] {js_path}")

    # 打印 top3
    for s in out_stocks:
        print(f"  #{s['rank']} {s['name']}({s['code']}) 综合{s['final_score']} 共振{s['resonance']} 板块+{s['sector_score']} 来源{','.join(s['sources'])}")


if __name__ == "__main__":
    main()
