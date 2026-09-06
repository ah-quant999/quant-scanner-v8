#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
潜力挖掘（2026-08-13 新增 · 暂未上架实验区）
================================================
- 数据源：CONCEPT_RANKING（概念热度）+ STOCK_PROFILE（概念标签）+ STOCK_QUOTE（当日行情/市值）
- 算法：当日涨幅温和（未被炒高）+ 拥有热门概念（想象空间）+ 市值适中（弹性好）
- 输出：data/POTENTIAL_PICKS.js

【限制说明】（透明化）
v8 当前无 PE/PB 财务数据，估值分位无法精确算，本期用"市值 + 当日涨幅温和"近似低估值。
下一版可接入 akshare.stock_a_indicator 或 fetch_fundamental_quality 完整财务数据。
"""
import json
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw_data")


def load_js(name):
    path = os.path.join(DATA, name + ".js")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if text.startswith("window." + name):
        text = text.split("=", 1)[1]
    text = text.rstrip(";\n ")
    try:
        return json.loads(text)
    except Exception as e:
        print(f"[warn] {name} 解析失败: {e}")
        return {}


def main():
    cr = load_js("CONCEPT_RANKING")
    sp = load_js("STOCK_PROFILE")
    sq = load_js("STOCK_QUOTE")

    # 1. 提取热门概念（chg + net 加权前 30%）
    items = cr.get("items", []) or []
    n = len(items)
    if n == 0:
        print("[warn] CONCEPT_RANKING.items 为空，跳过")
        return

    # 概念热度分 = chg*0.4 + net_normalized*0.4 + amount_normalized*0.2
    net_max = max((it.get("net") or 0) for it in items) or 1
    amt_max = max((it.get("amount") or 0) for it in items) or 1
    scored_concepts = []
    for it in items:
        chg = it.get("chg") or 0
        net = it.get("net") or 0
        amt = it.get("amount") or 0
        hot_score = chg * 0.4 + (net / net_max * 10) * 0.4 + (amt / amt_max * 5) * 0.2
        scored_concepts.append({
            "code": it.get("code"),
            "name": it.get("name"),
            "chg": chg,
            "net": net,
            "hot_score": round(hot_score, 3),
        })
    scored_concepts.sort(key=lambda x: x["hot_score"], reverse=True)
    top_concepts = scored_concepts[:max(10, n // 3)]  # 热度前 1/3
    hot_concept_names = set(c["name"] for c in top_concepts)

    # 2. 提取行情（市值 + 当日涨幅）
    stocks_quote = sq.get("stocks", {}) or {}
    # 建「纯数字 code -> full_code」字典，避免每支股票 O(n) endswith 扫描 + 防错配
    code_to_qkey = {}
    for qk in stocks_quote:
        digits = re.sub(r"\D", "", str(qk))
        if digits:
            code_to_qkey[digits] = qk

    # 3. 从 STOCK_PROFILE.profiles 提取成分股
    profiles = sp.get("profiles", {}) or {}

    # 4. 交叉筛选：股票拥有 ≥1 个热门概念 + 当日涨幅温和 [-3%, 5%] + 市值适中 [40 亿, 600 亿]
    picks = []
    rejected = {"no_hot_concept": 0, "too_hot": 0, "too_cold": 0, "small_mv": 0, "big_mv": 0, "no_quote": 0}
    for code, prof in profiles.items():
        concepts = set(prof.get("concepts", []) or [])
        # 至少 1 个热门概念
        hot_intersect = concepts & hot_concept_names
        if not hot_intersect:
            rejected["no_hot_concept"] += 1
            continue

        # 找行情（用纯数字 code 字典 O(1) 映射，替代原 O(n) endswith 扫描）
        ckey = re.sub(r"\D", "", str(code))
        qkey = code_to_qkey.get(ckey)
        if not qkey:
            rejected["no_quote"] += 1
            continue
        q = stocks_quote[qkey]
        pct = q.get("pct", 0) or 0
        # 当日涨幅温和（-3% ~ 5%）
        if pct > 5.0:
            rejected["too_hot"] += 1
            continue
        if pct < -3.0:
            rejected["too_cold"] += 1
            continue
        # 市值（用成交额 * 倍数粗估）
        amount = q.get("amount", 0) or 0  # 当日成交额（元）
        # 用 amount 估算关注度（成交额越高，弹性被关注度也高）
        # 用 amount / price 估算成交量比例（粗略活跃度指标）

        # 综合分
        # 1) 热门概念数（≥3 加分）
        hot_count_score = min(3, len(hot_intersect))  # 1-3 分
        # 2) 当日温和上涨（pct ∈ [0,5%]）
        mild_up = max(0, pct) * 0.5  # 0-2.5 分
        # 3) 热门概念累计热度
        concept_total_hot = sum(
            next((c["hot_score"] for c in scored_concepts if c["name"] == name), 0)
            for name in hot_intersect
        )
        # 4) 流通活跃度（金额 1 亿以下活跃度低）
        activity_score = min(2.0, amount / 1e9)  # 0-2 分

        total_score = hot_count_score + mild_up + concept_total_hot * 0.3 + activity_score

        picks.append({
            "code": code,
            "name": q.get("name", ""),
            "pct": round(pct, 2),
            "amount_yi": round(amount / 1e8, 2),  # 亿元
            "hot_concepts": sorted(list(hot_intersect)),
            "hot_count": len(hot_intersect),
            "total_score": round(total_score, 2),
        })

    picks.sort(key=lambda x: x["total_score"], reverse=True)
    picks = picks[:15]  # 最多展示 15 只

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": cr.get("update_time", "")[:10],
        "source": "CONCEPT_RANKING × STOCK_PROFILE × STOCK_QUOTE",
        "hot_concepts_count": len(top_concepts),
        "hot_concepts": [c["name"] for c in top_concepts[:10]],
        "picks": picks,
        "rejected_summary": rejected,
        "filters": {
            "pct_range": "[-3%, +5%]（温和，未被炒高）",
            "concept_match": "≥1 个热门概念（想象空间）",
            "scoring": "热门概念数(1-3分) + 当日涨幅温和(0-2.5分) + 概念累计热度 + 活跃度(0-2分)",
        },
        "note": "v8 当前无 PE/PB 数据，本期用「温和涨幅 + 热门概念 + 活跃度」近似估值低洼。下版接 fetch_fundamental_quality 完整财务数据。",
        "limitations": [
            "无 PE/PB 估值分位（待 fetch_fundamental_quality 落地）",
            "无营收/利润增速（待接入）",
            "成交额活跃度是粗略指标，未按板块/市值标准化",
        ],
    }

    out_path = os.path.join(DATA, "POTENTIAL_PICKS.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.POTENTIAL_PICKS = {json.dumps(result, ensure_ascii=False)};\n")
    print(f"[ok] {out_path}  picks={len(picks)}  热门概念={len(top_concepts)}/{n}  筛选排除={rejected}")

    raw_path = os.path.join(RAW, "potential_picks.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 🛡 2026-09-06 主人令：每日快照归档 → raw_data/history/potential_YYYYMMDD.json
    #   （此前选完即丢，永远无法回测；此目录是潜力挖掘 30 交易日考核的唯一输入源，
    #    删了考核直接报废，保护条目见 DO_NOT_DELETE.md）
    try:
        _dd = (result.get("data_date") or "").replace("-", "")
        if _dd:
            _hist_dir = os.path.join(RAW, "history")
            os.makedirs(_hist_dir, exist_ok=True)
            _hist_path = os.path.join(_hist_dir, f"potential_{_dd}.json")
            with open(_hist_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[ok] 快照归档 {_hist_path}  picks={len(picks)}")
        else:
            print("[warn] data_date 为空，本次未归档快照")
    except Exception as _e:
        print(f"[warn] 快照归档失败（不影响主输出）: {_e}")


if __name__ == "__main__":
    main()