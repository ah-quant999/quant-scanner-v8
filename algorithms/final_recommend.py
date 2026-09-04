#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""final_recommend.py — 跨策略共振 + 板块强度 生成最终推荐 Top3

输入：
  - raw_data/triple_consensus.json
  - raw_data/top10_daily.json   (四量终极 / 主站 TOP10)
  - raw_data/crds_card_data.json (逆势龙头)
  - raw_data/sector_rs.json     (板块相对强度)
  - raw_data/stock_profile.json (个股行业/概念)
  - raw_data/crisis_data.json   (危机雷达，决定是否并入逆势龙头)
  - raw_data/triple_track.json     (三重跟踪告警，用于 Top3 跟踪)
  - (2026-09-04 主人令：cockpit_tier_recommend / cockpit_backtest / lhb 数据源整段删除——驾驶舱/大牛股猎手已下线，
     backtest 输出字段一并移除，前端无消费方，verify_chain_outputs 不校验)

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

# 名称归一化共享模块（2026-08-14 抽出，消除与 build_candidate_pool/guanlan_extractor/scanner 的重复）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_utils import norm_code, fix_name, strip_entitlement_prefix, STANDARD_NAME_MAP  # noqa: E402

CRISIS_HIGH_THRESHOLD = 50  # 危机雷达≥50才并入逆势龙头
SECTOR_TOP_N = 15
TOP_N = 5  # 2026-08-13 主人令：从 3 扩到 5（共振优先 + 分数其次，覆盖更多共识强票）
# 2026-08-11 主人令：去掉港股降权+去掉 A 股保底——「谁好谁上」原则。
#   之前 HK_PENALTY=1.5 + hard_a=MIN_A_SHARES_IN_TOP-1=1 是「主做 A 股」假设下的保护，
#   实际效果是市场歧视（港股凭空少 1.5 分）。现在改公平竞争，靠数据说话。
#   监控兜底：Top3 出现「全港股」或「全 A 股」时，v8_health_check 会写 URGENT 告警，
#   用于发现数据源异常（如港股 API 挂导致共振虚高、A 股 mootdx 挂导致扫描失败）。
HK_PENALTY = 0          # 港股不再降权（之前 1.5）——2026-08-11 主人令
MIN_A_SHARES_IN_TOP = 0  # A 股硬保底关闭（之前 max(1, TOP_N-1)=2）——公平竞争


_STOCK_NAME_MAP = None
def _stock_name_map():
    """延迟加载 raw_data/stock_names.json → {code: name}，用于候选池 code-only 补名。
    2026-08-22 主人令：最终推荐候选池出现多个「只有代码没股票名」条目
    （601899/600206/000725），fix_name 在 name==code 时直接返回 code，需在此兜底补全。"""
    global _STOCK_NAME_MAP
    if _STOCK_NAME_MAP is None:
        _m = {}
        try:
            sp = os.path.join(ROOT, "raw_data", "stock_names.json")
            if os.path.exists(sp):
                d = json.load(open(sp, encoding="utf-8"))
                for it in (d.get("data") or []):
                    if isinstance(it, dict) and it.get("code") and it.get("name"):
                        _m[str(it["code"])] = str(it["name"])
        except Exception as e:
            print(f"[warn] stock_names 加载失败: {e}")
        _STOCK_NAME_MAP = _m
    return _STOCK_NAME_MAP


def _resolve_name(code, name):
    """fix_name 兜底后仍为纯代码（name==code/缺失）时，用 stock_names 映射补全真实股票名。"""
    n = fix_name(code, name)
    c = norm_code(code)
    if not n or n == c:
        m = _stock_name_map().get(code) or _stock_name_map().get(c)
        if m:
            return m
    return n





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
    # 🛡 2026-08-20 主人令·一劳永逸：所有选股策略必须 18:00 后才能跑。
    # final_recommend 是跨策略共振最终产物，依赖港股/龙虎榜/北向/板块资金等全部盘后数据。
    # 此前 16:18 本地手动跑 + 17:13 CRDS 提前出结果，均因数据未全就绪导致结果不准。
    # 加统一选股策略守门：早于 18:00 直接 sys.exit(1)；应急可设 TIME_GATE_BYPASS=1。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='final_recommend')
    triple = load_json("triple_consensus.json")
    top10 = load_json("top10_daily.json")
    crds = load_json("crds_card_data.json")
    sector_rs = load_json("sector_rs.json")
    profile = load_json("stock_profile.json")
    crisis = load_json("crisis_data.json")
    gold_pool = load_json("gold_pool.json")

    rel_set, abs_set, score_map = build_sector_maps(sector_rs)

    # 读取 STOCK_STOP_DATA.js（支撑/压力/ATR）
    stop_data = load_js("STOCK_STOP_DATA.js", "STOCK_STOP_DATA")
    stop_stocks = stop_data.get("stocks") or {}

    # ── 读取四量终极共振数据（多周期确认）──
    # 🛡 2026-08-26 一劳永逸：优先 60min 版(FOUR_VOLUME_60M)；但其 update_time 非今日
    #   （baostock 60min 源常滞后，曾陈旧到 8/22）→ 回退读日线版 FOUR_VOLUME.js（新鲜），
    #   避免最终推荐用几天前的陈旧四量汇总（"逻辑不对"根因）。两份 schema 兼容(stocks[])。
    _four_vol_raw = load_js("FOUR_VOLUME_60M.js", "FOUR_VOLUME_60M")
    _four_vol_src = "60m"
    try:
        _ut = _four_vol_raw.get("update_time", "")
        _ut_date = datetime.strptime(_ut, "%Y-%m-%d %H:%M:%S").date()
        if _ut_date < datetime.now().date():
            _four_vol_raw = load_js("FOUR_VOLUME.js", "FOUR_VOLUME")
            _four_vol_src = "day(60m陈旧回退)"
            print(f"[warn] 60m 四量 update_time={_ut} 非今日，回退读日线四量终极")
    except Exception as e:
        print(f"[warn] 四量新鲜度校验失败，沿用 60m: {e}")
    _60m_hits = {}  # norm_code → {reason, signals[], qd, pct_chg, ...}
    for item in (_four_vol_raw.get("hits") or _four_vol_raw.get("stocks") or []):
        c = norm_code(item.get("code") or item.get("code"))
        if c:
            _60m_hits[c] = item
    print(f"[info] 四量数据({_four_vol_src}): 加载 {len(_60m_hits)} 只命中")

    # 2026-09-04 主人令：cockpit_backtest 死数据源整段删除（生成器 09-03 下线，load 恒空，仅产出全零 backtest 垃圾）
    tt = load_json("triple_track.json")
    tt_alerts = {}
    for a in tt.get("alerts") or []:
        code = a.get("code")
        if not code:
            continue
        tt_alerts.setdefault(code, []).append(a)

    crisis_score = safe_float(crisis.get("score"), 0.0)
    crisis_high = crisis_score >= CRISIS_HIGH_THRESHOLD

    # ── 市场状态 regime 门控（回测验证提升胜率，见 backtest_tdx.json optimized_summary）──
    # stabilize / rebound_diverge = 好状态：历史回测该阶段 ≥3 共振信号整体负期望 → 应少推/观察
    # grind / panic               = 可开仓状态 → 正常推
    try:
        from regime_filter import get_current_regime, is_open_regime
        _regime_info = get_current_regime()
        _open_regime = bool(_regime_info and is_open_regime(_regime_info.get("regime")))
    except Exception as e:
        print(f"  [warn] regime 门控不可用，跳过: {e}")
        _regime_info = None
        _open_regime = True  # 失败时默认正常推，不破坏原有逻辑
    _regime_name = (_regime_info or {}).get("regime")
    _regime_date = (_regime_info or {}).get("date")
    _effective_top_n = TOP_N if _open_regime else max(2, TOP_N // 2)
    _action_label = "买入" if _open_regime else "观察（市场企稳/反弹，历史回测负期望）"
    print(f"[regime] 市场状态={_regime_name}({_regime_date}) 开仓={_open_regime} 推票数 {TOP_N}→{_effective_top_n}")

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
        # 2026-09-03 主人令修复：FACTOR_LAB/外部源代码带 '.' 前缀（如 '.601899'），
        #   norm_code 不剥点 → pool key 带点 → 画像/止损/行情 lookup 全失配，
        #   Top5 第1/2名 concepts=0、reason 空、止损/目标/盈亏比全 None（第3名四量终极源正常）。
        _nc = norm_code(code).lstrip('.')
        r = pool[_nc]
        if not r["code"]:
            r["code"] = _nc
            r["name"] = fix_name(_nc, name)
            r["market"] = market or market_prefix(_nc)
            r["board"] = board or board_from_code(_nc)
            # 从 STOCK_STOP_DATA 预填支撑/压力/ATR/止损/目标（如存在）
            ss = stop_stocks.get(_nc) or stop_stocks.get(code)
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
        # 2026-08-13 公平性修复：去掉 score>=25 硬门槛（低于直接出局=歧视），
        # 改为统一归一化；入选即给基础分，避免强三重共识信号被误杀。
        src_score = min(4.0, max(0.5, score / 25.0))
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

    # 2026-09-03 主人令：#2 驾驶舱 A/B 档 source 整段下线（cockpit.* 不再读，sources 也不再 append "驾驶舱A档/B档"）
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

    # 2026-09-03 主人令：#4 全站精选 source 整段下线（allsite.* 不再读）

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

    # 2026-09-03 主人令：#6 大牛股猎手 source 整段下线（不再 append "大牛股猎手"，lhb 数据仍可被其他源使用）
    # 2026-09-03 主人令：#7 板块龙头 source 整段下线（不再 append "板块龙头"，sec_score 仍可用于其他源加分）
    # ── 第8节 因子实验室因子（方案B：智能融合，非简单硬加权）──
    # 维度1 异常换手率：缩量=因子高=强势（abnormal_turnover.top 前30）；放量弱势=bottom（扣0.5）
    # 维度2 ROE_TTM：全市场主板大市值档 Top30（高 ROE=质量）
    # 分层加权：前5名 +2.0 / 6-15名 +1.5 / 16-30名 +1.0
    # 择时控权：非开仓期(_open_regime=False) 因子权重 ×0.3（弱加成，避免逆势放大因子噪声）
    # 放量弱势：bottom 入池则打「放量弱势」信号，最终分 −0.5（弱势扣分）
    # 名字兜底：ROE 票 baostock 常返回 '1' → _resolve_name + stock_names 映射补全
    fl = load_js("FACTOR_LAB.js", "FACTOR_LAB")
    if fl:
        _at_top = (fl.get("abnormal_turnover") or {}).get("top") or []
        _at_bot = (fl.get("abnormal_turnover") or {}).get("bottom") or []
        _roe_top = (fl.get("roe_largecap") or {}).get("top") or []

        _at_rank = sorted(_at_top, key=lambda x: safe_float(x.get("factor_at")), reverse=True)
        for i, s in enumerate(_at_rank):
            code = s.get("code")
            if not code:
                continue
            _pure = norm_code(code)
            _pure6 = _pure.lstrip('.')
            _nm = _stock_name_map()
            display_name = (_nm.get(_pure6) or _nm.get(_pure) or _nm.get(code)
                           or (profiles.get(_pure6) or {}).get("name") or s.get("name") or "")
            r = ensure(code, display_name, "", "")
            sc = 2.0 if i < 5 else (1.5 if i < 15 else 1.0)
            sc *= (1.0 if _open_regime else 0.3)
            r["sources"].append("异常换手率")
            r["source_scores"]["异常换手率"] = round(sc, 2)
            r["signals"].append("缩量强势")
            if s.get("first_date"):
                r["enter_dates"].append(s["first_date"])

        _roe_rank = sorted(_roe_top, key=lambda x: safe_float(x.get("roe_ttm")), reverse=True)
        for i, s in enumerate(_roe_rank):
            code = s.get("code")
            if not code:
                continue
            _pure = norm_code(code)
            _pure6 = _pure.lstrip('.')
            _nm = _stock_name_map()
            display_name = (_nm.get(_pure6) or _nm.get(_pure) or _nm.get(code)
                           or (profiles.get(_pure6) or {}).get("name") or s.get("name") or "")
            r = ensure(code, display_name, "", "")
            sc = 2.0 if i < 5 else (1.5 if i < 15 else 1.0)
            sc *= (1.0 if _open_regime else 0.3)
            r["sources"].append("ROE_TTM")
            r["source_scores"]["ROE_TTM"] = round(sc, 2)
            r["signals"].append("高ROE")
            # 2026-09-03 主人令：补入选依据与行情（之前第1/2名 reason 空、无价格→分析不如第3名）
            r["reasons"].append(f"基本面因子 高ROE 排名第{i + 1}")
            if s.get("close"):
                r["close"] = s.get("close") or r["close"]
            if s.get("pct_chg"):
                r["pct_chg"] = s.get("pct_chg") or r["pct_chg"]
            if s.get("first_date"):
                r["enter_dates"].append(s["first_date"])

        _weak = {norm_code(x.get("code")) for x in _at_bot if x.get("code")}
        for key, r in pool.items():
            if key in _weak:
                r["signals"].append("放量弱势")
    else:
        print("[warn] FACTOR_LAB.js 缺失，跳过因子实验室方案B融合")

    # ── 第8.5节 高手共振（外部共振源之一：ima 高手强势股跟踪池）──
    # 与 v8 选股池 code 命中且 IMA 状态仍有效（非见顶/走弱）→ 独立外部共识信号，最终分 +1
    # 择时控权：非开仓期(_open_regime=False) 权重 ×0.3（弱加成）
    ima = load_js("IMA_STRONG_STOCK.js", "IMA_STRONG_STOCK")
    if ima:
        _ima_norm = {}
        for s in (ima.get("stocks") or []):
            _c = s.get("code")
            _st = (s.get("status") or "")
            if not _c:
                continue
            if _st in ("见顶", "走弱"):
                continue
            _ima_norm[norm_code(_c).lstrip('.')] = s
        _hit = 0
        for key, r in pool.items():
            _k = key.lstrip('.') if key.startswith('.') else key
            if _k in _ima_norm:
                sc = 1.0 * (1.0 if _open_regime else 0.3)
                r["sources"].append("高手跟踪")
                r["source_scores"]["高手跟踪"] = round(sc, 2)
                r["signals"].append("高手共振")
                r["reasons"].append("高手强势股跟踪池共振（IMA 状态有效）")
                _hit += 1
        print("[ok] 高手共振命中 v8 池 %d 只" % _hit)
    else:
        print("[warn] IMA_STRONG_STOCK.js 缺失，跳过高手共振融合")

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

    # 2026-09-03 主人令：候选池行情兜底——ROE_TTM/高手跟踪单源票常无 close，
    #   导致止损/目标/盈亏比全空、前端"第1/2名分析不如第3名"。从 CANDIDATE_QUOTES 补价。
    _cq_map = {}
    for _q in ((load_js("CANDIDATE_QUOTES.js", "CANDIDATE_QUOTES") or {}).get("items") or []):
        if isinstance(_q, dict) and _q.get("code"):
            _cq_map[norm_code(_q["code"]).lstrip('.')] = _q
    for key, r in pool.items():
        if not r["close"]:
            _q = _cq_map.get(key) or _cq_map.get(norm_code(key).lstrip('.'))
            if _q:
                if _q.get("price"):
                    r["close"] = _q["price"]
                if _q.get("chg") and not r["pct_chg"]:
                    r["pct_chg"] = _q["chg"]

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
        # 2026-08-13 公平性修复：若已是板块龙头源，板块强度已在源分体现，
        # 此处只对非板块龙头票加全局板块加分，避免板块被双重计价。
        sec_add = 0.0 if "板块龙头" in r["sources"] else sec_score
        # 方案B 放量弱势扣分：被异常换手率 bottom 命中的票，若同时被其他源选中则 −0.5
        weak_penalty = 0.5 if "放量弱势" in r.get("signals", []) else 0.0
        final_score = strength + resonance * 1.5 + sec_add - weak_penalty
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
    # 2026-08-13 公平性修复：排序第一关键字改为 final_score（分数优先），
    # 共振数/强度作次级 tie-breaker——公平计分后"最强"=分数最高，而非最多策略选中。
    scored.sort(key=lambda x: (x["final_score"], x["resonance"], x["strength"]), reverse=True)

    # ── Top3 选取（2026-08-11 主人令：公平竞争，谁好谁上）──
    # 之前 A 股硬保底逻辑：先灌 A 股 + 余下从全局高分（已被 HK_PENALTY 减分）填。
    #   实际效果：港股被歧视 + A 股被强保——两边都不公平。
    # 现改为：完全去掉 A 股硬保底（hard_a=0），直接取 scored 全局高分前 TOP_N 名。
    #   排序 key=(resonance, final_score, strength)——多源共振优先，分数次之，强度兜底。
    # 监控兜底：v8_health_check 检查 Top3 市场分布，全港股/全 A 股写 URGENT 告警（数据源异常）。
    a_shares = [s for s in scored if s.get("board") != "港股" and market_prefix(s.get("code", "")) != "hk"]
    hk_stocks = [s for s in scored if s.get("board") == "港股" or market_prefix(s.get("code", "")) == "hk"]
    top = []
    # 1) A 股硬保底 = 0（已关闭），直接进第 2 步
    hard_a = MIN_A_SHARES_IN_TOP  # 现 = 0，立即 break
    for s in a_shares:
        if len(top) >= _effective_top_n or len(top) >= hard_a:
            break
        top.append(s)
    # 2) 余下 slot 从 scored 全局高分填补（A 股 + 港股，按 (resonance, final_score, strength) 排序）
    top_codes = {t["key"] for t in top}
    for s in scored:
        if len(top) >= _effective_top_n:
            break
        if s["key"] in top_codes:
            continue
        top.append(s)
        top_codes.add(s["key"])
    # 3) 双轨排名（2026-08-13 主人令：共振最强 + 分数最强分开展示）
    #    top = 分数最强（公平计分后"绝对最强"）
    #    consensus_top = 共振最强（多策略交叉验证，抗单一策略失效）
    top.sort(key=lambda x: (x["final_score"], x["resonance"], x["strength"]), reverse=True)
    top = top[:_effective_top_n]
    # ── 共振最强副本（独立排序，不覆盖 top）──
    consensus_sorted = sorted(scored, key=lambda x: (x["resonance"], x["final_score"], x["strength"]), reverse=True)
    consensus_top = consensus_sorted[:_effective_top_n]
    # ── end 公平竞争 ──

    def horizon_for(sources, resonance=0, is_top=False):
        """horizon 判定
        is_top=True (top3/Allsite A/B档 持仓层):
          严格按 sources——主推"短线择时买入"，跨策略仍标"短线/中线共振"
        is_top=False (候选池/research 视角):
          仅含中线策略源(mid)归"中长线"；纯短线策略源保持"短线"（2026-08-13 公平性修复：标签须反映策略真实属性）
        2026-08-11 主人令：候选池的中长线列之前永远"暂无"——是判定过严。
        """
        short = {"四量终极"}  # 2026-09-03 主人令：大牛股猎手/板块龙头已下线
        mid = {"三重共识"}  # 2026-09-03 主人令：驾驶舱A/B档已下线
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
        # 候选池放宽：含中线策略源(mid)归中长线；纯短线共振≥2(多源交叉)也升中长线
        if has_mid:
            return "中长线"
        if has_short and resonance >= 2:
            return "中长线"
        return "短线"

    # 清理输出字段
    out_stocks = []
    for s in top:
        code = norm_code(s["code"]).lstrip('.')  # 2026-09-03 主人令：剥点（与 R1 ensure 对齐）
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
        alerts = tt_alerts.get(code, [])

        if close:
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
            "concepts": s["concepts"][:8],  # 2026-09-03 主人令：6→8
            "tracking": tracking,
            "action": _action_label,
            "market_regime": _regime_name,
        })

    # ── 共振最强列表（双轨排名第二轨）──
    consensus_stocks = []
    for s in consensus_top:
        code = s["key"]
        # 去重：已在分数最强中的不再重复构建完整数据
        # 但 consensus_stocks 需要独立 rank 和排序语义，所以仍完整构建
        market = {"sh": "沪市", "sz": "深市", "bj": "北交所", "hk": "港股"}.get((s["market"] or market_prefix(code)).lower(), s["market"] or market_prefix(code))
        board = s["board"] or board_from_code(code, s["market"])
        close = safe_float(s.get("close"))
        stop = s.get("stop_loss")
        target = s.get("target_price")
        rr = s.get("risk_reward")
        enter_date = s.get("enter_dates")[0] if s.get("enter_dates") else ""
        alerts = [a for a in (s.get("alerts") or []) if a not in ("已入库",)]
        if enter_date and close:
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
        consensus_stocks.append({
            "rank": len(consensus_stocks) + 1,
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
            "final_score": s["final_score"],
            "sector_score": s.get("sector_score", 0),
            "sector_hits": s.get("sector_hits", []),
            "enter_date": enter_date,
            "signals": s["signals"][:8],
            "_60m_resonance": s.get("_60m_resonance", False),
            "reason": "；".join(s["reasons"][:3]),
            "industry": s["industry"],
            "concepts": s["concepts"][:8],  # 2026-09-03 主人令：6→8
            "tracking": tracking,
            "action": _action_label,
            "market_regime": _regime_name,
        })
    # ── end 双轨 ──

    # 方案B：因子候选（异常换手率/ROE_TTM）因权重低常落在 top30 之后，需强制纳入候选池，否则方案B不可见
    _top30 = scored[:30]
    _top30_keys = {x["key"] for x in _top30}
    _factor_extra = [x for x in scored[30:] if ("异常换手率" in x["sources"] or "ROE_TTM" in x["sources"]) and x["key"] not in _top30_keys]

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crisis_score": round(crisis_score, 1),
        "crisis_high": crisis_high,
        "crisis_note": "逆势龙头已并入" if crisis_high else "危机雷达未达高位，逆势龙头暂不并入",
        "total_candidates": len(scored),
        "top_n": _effective_top_n,
        "market_regime": {
            "date": _regime_date,
            "regime": _regime_name,
            "open": _open_regime,
            "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推",
        },
        "strong_sectors": sorted(rel_set)[:20],
        "stocks": out_stocks,
        "consensus_stocks": consensus_stocks,  # 2026-08-13 双轨：共振最强排名（独立于 stocks 分数最强）
        "all_candidates": [
            {
                "code": x["key"],
                "name": _resolve_name(x["key"], x["name"]),
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
                "concepts": x.get("concepts", [])[:8],  # 2026-09-03 主人令：6→8
                "enter_date": (min([d for d in x.get("enter_dates", []) if d]) if x.get("enter_dates") else None) or datetime.now().strftime("%Y-%m-%d"),
                "stop_loss": round(safe_float(x.get("stop_loss")), 2) if x.get("stop_loss") is not None else None,
                "target_price": round(safe_float(x.get("target_price")), 2) if x.get("target_price") is not None else None,
                "risk_reward": round(safe_float(x.get("risk_reward")), 2) if x.get("risk_reward") is not None else None,
                "support": round(safe_float(x.get("support")), 2) if x.get("support") is not None else None,
                "resistance": round(safe_float(x.get("resistance")), 2) if x.get("resistance") is not None else None,
            }
            for x in (_top30 + _factor_extra)
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

    # 🗂 历史归档（all_site_backtest.py 已删除）：按 update_time 日期落盘 raw_data/history
    # 与 calc_crds.py 同源思路——只有落盘「每日 dated 快照」回测才有过去信号日可算前向收益。
    try:
        _dt = (result.get("update_time") or "")[:10].replace("-", "")
        if len(_dt) == 8 and _dt.isdigit():
            _hist_dir = os.path.join(RAW, "history")
            os.makedirs(_hist_dir, exist_ok=True)
            _hist_path = os.path.join(_hist_dir, f"final_recommend_{_dt}.json")
            with open(_hist_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[ok] history archive {_hist_path}")
    except Exception as e:
        print(f"[warn] final_recommend history archive skipped: {e}")

    # 打印 top3
    for s in out_stocks:
        print(f"  #{s['rank']} {s['name']}({s['code']}) 综合{s['final_score']} 共振{s['resonance']} 板块+{s['sector_score']} 来源{','.join(s['sources'])}")


if __name__ == "__main__":
    main()
