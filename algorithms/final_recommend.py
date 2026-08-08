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
    c = str(code or "")
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


def board_from_code(code):
    c = str(code or "")
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
    hits = []
    score = 0.0
    seen = set()

    # 概念→强势板块别名映射（数据中概念名与板块名不完全一致）
    CONCEPT_ALIASES = {
        "黄金概念": "贵金属",
        "小金属概念": "小金属",
        "稀土永磁": "小金属",
        "有色金属": "有色金属",
        "半导体概念": "半导体",
    }

    def hit(name):
        nonlocal score
        if name in seen:
            return
        seen.add(name)
        if name in rel_set:
            hits.append(f"{name}(强)")
            score += 1.0
        elif name in abs_set:
            hits.append(name)
            score += 0.5

    def hit_alias(name):
        hit(name)
        alias = CONCEPT_ALIASES.get(name)
        if alias and alias != name:
            hit(alias)

    # 行业
    ind = stock.get("industry") or ""
    if ind:
        hit_alias(ind)

    # 概念
    for c in stock.get("concepts") or []:
        hit_alias(c)

    # 名称/行业/概念中显含贵金属/黄金/小金属/有色的，直接补分（让黄金股在无精确板块名数据时也能被捞起）
    name = stock.get("name", "")
    has_metal_keyword = (
        any(k in name for k in ("黄金", "中金", "银泰", "赤峰", "山东", "紫金", "湖南")) and "金" in name
    )
    for raw in [ind] + (stock.get("concepts") or []):
        if isinstance(raw, str) and any(k in raw for k in ("黄金", "贵金属", "小金属", "有色金属")):
            has_metal_keyword = True
            break
    if has_metal_keyword and not any("黄金" in h or "贵金属" in h or "小金属" in h or "有色" in h for h in hits):
        score += 0.8
        hits.append("贵金属/有色(关键词)")

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
        "sources": [],
        "source_scores": {},
        "industry": "",
        "concepts": [],
        "reasons": [],
    })

    def ensure(code, name, market, board):
        r = pool[norm_code(code)]
        if not r["code"]:
            r["code"] = code
            r["name"] = name
            r["market"] = market or market_prefix(code)
            r["board"] = board or board_from_code(code)
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

    # 3) 四量终极 (top10_daily.top10)
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
        src_score = round(min(4.0, max(0.0, src_score)), 2)
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
            r["sources"].append("大牛股猎手")
            r["source_scores"]["大牛股猎手"] = round(src_score, 2)
            r["close"] = s.get("close") or r["close"]
            r["pct_chg"] = s.get("pct") or r["pct_chg"]
            r["reasons"].append(f"大牛股猎手 机构{inst/10000:.1f}亿+游资{yz/10000:.1f}亿")

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
        r["reasons"].append(f"板块龙头 {','.join(sec_hits[:2])}")

    # 补齐个股画像（行业/概念）
    for key, r in pool.items():
        prof = profiles.get(key) or profiles.get(norm_code(key))
        if prof:
            if not r["industry"]:
                r["industry"] = prof.get("industry") or ""
            if prof.get("concepts"):
                r["concepts"] = list(set(r["concepts"] + prof.get("concepts")))

    # 计算板块加分 与 最终分
    scored = []
    for key, r in pool.items():
        if len(r["sources"]) == 0:
            continue
        sec_score, sec_hits = sector_score_for(r, rel_set, abs_set, score_map)
        resonance = len(set(r["sources"]))
        strength = sum(r["source_scores"].values())
        final_score = strength + resonance * 1.5 + sec_score
        # 同分：共振次数多优先，其次源强度
        scored.append({
            **r,
            "key": key,
            "resonance": resonance,
            "strength": round(strength, 2),
            "sector_score": sec_score,
            "sector_hits": sec_hits,
            "final_score": round(final_score, 2),
        })

    # 排序：先按共振次数，再按综合分，再按源强度（多源共振优先）
    scored.sort(key=lambda x: (x["resonance"], x["final_score"], x["strength"]), reverse=True)

    top = scored[:TOP_N]

    # 清理输出字段
    out_stocks = []
    for s in top:
        code = norm_code(s["code"])
        market = s["market"] or market_prefix(code)
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
        out_stocks.append({
            "rank": len(out_stocks) + 1,
            "code": code,
            "name": s["name"],
            "market": market,
            "board": board,
            "close": round(close, 2) if close else None,
            "pct_chg": safe_float(s["pct_chg"]),
            "stop_loss": round(safe_float(stop), 2) if stop else None,
            "target_price": round(safe_float(target), 2) if target else None,
            "risk_reward": round(safe_float(rr), 2) if rr else None,
            "sources": sorted(set(s["sources"])),
            "source_scores": s["source_scores"],
            "resonance": s["resonance"],
            "strength": s["strength"],
            "sector_score": s["sector_score"],
            "sector_hits": s["sector_hits"],
            "final_score": s["final_score"],
            "reason": "；".join(s["reasons"][:3]),
            "industry": s["industry"],
            "concepts": s["concepts"][:6],
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
            {"code": x["key"], "name": x["name"], "final_score": x["final_score"], "resonance": x["resonance"], "sources": sorted(set(x["sources"]))}
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
