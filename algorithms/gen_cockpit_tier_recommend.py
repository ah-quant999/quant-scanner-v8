#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cockpit_tier_recommend.py — 生成驾驶舱顶部「A/B 档推荐」横幅数据（阿狸咪独立版）
============================================================================
【2026-07-24 主人决定】删除小九宽松版，仅保留阿狸咪严格算法（双真+不超买+EMA完好）。

数据源: data/scan_result.json（候选池实时扫描结果）
输出:
  - data/cockpit_tier_recommend_alimi.json  ← 阿狸咪独立计算（前端 fetch 唯一源）

阿狸咪 A 档（拿住别动型）：上涨趋势+机构变红+RSI<68+20日<35%+EMA>=5+非涨停
阿狸咪 B 档（提前埋伏型）：机构变红+缠论买/三线共振+RSI<65+回调健康+EMA>=4，来源更多元
"""

import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
from datetime import datetime

from fundamental_helper import fq_key_of, load_fundamental, quality_points

BASE = os.path.dirname(os.path.abspath(__file__))
SCAN_PATH = os.path.join(BASE, "..", "out", "scan_result.json")
OUT_ALIMI = os.path.join(BASE, "..", "out", "cockpit_tier_recommend_alimi.json")
FQ = load_fundamental()  # 基本面质量分（含消息面加减分）

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def market_label(s):
    """从 scan_result 条目判读市场标签"""
    m = (s.get("market") or "").lower()
    if m == "hk":
        return "港股"
    if m == "sh":
        b = (s.get("board_label") or "")
        return "科创板" if "科创" in b else "沪市"
    if m == "sz":
        b = (s.get("board_label") or "")
        return "创业板" if "创业" in b else "深市"
    return "其他"


def build_alimi(all_results, data_date=None, fq_map=FQ):
    """阿狸咪独立计算：基于 scan_result 新鲜数据，严格算法（双真+不超买+EMA完好）"""
    if data_date is None:
        data_date = datetime.now().strftime("%Y-%m-%d")

    def _q(s):
        fq = fq_map.get(fq_key_of(s.get("market"), s.get("code")), {})
        return quality_points(fq)

    # ── A 档筛选条件 ──
    tier_a_raw = []
    for s in all_results:
        up = s.get("上涨趋势")
        inst = s.get("四量图_机构变红")
        rsi = s.get("rsi_14") or 0
        pct20 = s.get("pct_chg_20d") or 0
        ema = s.get("ema_up") or 0
        limit = s.get("当日涨停") or False
        if not (up and inst):
            continue
        if rsi >= 68:        # 比原小九的 70 更严，留超买缓冲
            continue
        if pct20 >= 35:      # 比原小九的 40% 更严
            continue
        if ema < 5:          # EMA 结构必须健康
            continue
        if limit:
            continue
        qscore, qgrade, qdetail = _q(s)
        tech_score = int(35 + ema * 3 + (s.get("signal_count") or 0) * 2)
        total_score = int(tech_score + qscore)
        tier_a_raw.append({
            "code": s.get("code", ""),
            "name": s.get("name", ""),
            "market": market_label(s),
            "rsi": round(rsi, 1),
            "ret20": round(pct20, 1),
            "ema": ema,
            "quality_grade": qgrade,
            "quality_score": qscore,
            "quality_detail": qdetail,
            "tech_score": tech_score,
            "total_score": total_score,
            "comment": "双真+不超买+EMA完好" + (f" · 基本面{qgrade}" if qgrade else ""),
            "raw": s,
        })

    # 排序：按总评分降序（技术分 + 基本面分），同分再按基本面分、技术面强度 tiebreak
    tier_a_raw.sort(key=lambda x: (-x.get("total_score", 0), -x.get("quality_score", 0), -x.get("ema", 0), -(x["raw"].get("signal_count") or 0), x.get("rsi", 0)))
    tier_a_out = []
    for x in tier_a_raw:
        tier_a_out.append({
            "code": x["code"],
            "name": x["name"],
            "market": x["market"],
            "rsi": x["rsi"],
            "ret20": x["ret20"],
            "ema": x["ema"],
            "quality_grade": x["quality_grade"],
            "quality_score": x["quality_score"],
            "quality_detail": x["quality_detail"],
            "tech_score": x["tech_score"],
            "total_score": x["total_score"],
            "comment": x["comment"],
            "enter_date": data_date,
        })
    tier_a_out = tier_a_out[:10]  # 最多 10 只

    # ── B 档筛选条件 ──
    tier_b_raw = []
    for s in all_results:
        up = s.get("上涨趋势")
        inst = s.get("四量图_机构变红")
        chan = s.get("缠论买_日K")
        rsi = s.get("rsi_14") or 0
        pct20 = s.get("pct_chg_20d") or 0
        ema = s.get("ema_up") or 0
        triple = s.get("三线共振")
        score = s.get("signal_score") or 0

        if up:  # 趋势已确认的归 A 档
            continue
        # 需要至少机构变红 或 三线共振（原 `(inst and chan)` 是死项，恒被 inst 覆盖，已删）
        # 注：缠论买(chan) 单独目前不构成入档条件，与文档「缠论买/三线共振」表述不完全一致，
        #     是否让 chan 单独入 B 档属选股口径变更，保持现状待确认，不擅自扩大选股范围。
        if not (inst or triple):
            continue
        if rsi >= 65:
            continue
        if pct20 <= -15 or pct20 >= 30:
            continue
        if ema < 4:
            continue
        # 构造早期信号备注
        early_parts = []
        if inst:
            early_parts.append("机构变红")
        if chan:
            early_parts.append("缠论买")
        if triple:
            early_parts.append("三线共振")
        if not early_parts:
            early_parts.append("早期信号")

        qscore, qgrade, qdetail = _q(s)
        tech_score = int(score * 5)
        total_score = int(tech_score + qscore)
        tier_b_raw.append({
            "code": s.get("code", ""),
            "name": s.get("name", ""),
            "market": market_label(s),
            "rsi": round(rsi, 1),
            "ret20": round(pct20, 1),
            "ema": ema,
            "early": "+".join(early_parts),
            "score": score,
            "tech_score": tech_score,
            "total_score": total_score,
            "quality_grade": qgrade,
            "quality_score": qscore,
            "quality_detail": qdetail,
            "comment": f"早期:{'+'.join(early_parts)}" + (f" · 基本面{qgrade}" if qgrade else ""),
            "enter_date": data_date,
        })

    tier_b_raw.sort(key=lambda x: (-x.get("total_score", 0), -x.get("quality_score", 0), -x["score"], -x["ema"], x["rsi"]))
    tier_b_out = tier_b_raw[:15]

    return tier_a_out, tier_b_out


def main():
    scan_data = load_json(SCAN_PATH)
    if not scan_data or not scan_data.get("all_results"):
        print("⚠️ 无 scan_result.json 或 all_results 为空，无法生成推荐")
        return 1

    all_results = scan_data["all_results"]
    scan_time = scan_data.get("scan_time", NOW)
    # 数据日期：优先 scan_time 日期，否则今天；用于给每只股票打 enter_date。
    data_date = (scan_time[:10] if isinstance(scan_time, str) and len(scan_time) >= 10
                 else datetime.now().strftime("%Y-%m-%d"))
    total = len(all_results)
    print(f"  scan_result: {total} 只 · 扫描时间 {scan_time}")

    # 1. 阿狸咪独立计算
    tier_a, tier_b = build_alimi(all_results, data_date)

    # 2. 构建输出
    alimi = {
        "gen_time": NOW,
        "source": "阿狸咪-独立计算(主站数据)",
        "data_time": scan_time,
        "method": {
            "A档": "上涨趋势 & 机构变红 & RSI<68 & 20日涨幅<35% & EMA>=5 & 非涨停",
            "B档": "非上涨趋势 & (机构变红|缠论买|三线共振) & RSI<65 & -15%<20日<30% & EMA>=4",
        },
        "tier_a": tier_a,
        "tier_b": tier_b,
    }

    # 3. 写入 data/
    with open(OUT_ALIMI, "w", encoding="utf-8") as f:
        json.dump(alimi, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 阿狸咪独立 → {OUT_ALIMI}")

    # 4. 输出摘要
    print(f"\n  📊 阿狸咪 A 档({len(tier_a)}只) [技术分+基本面分=总评分]:")
    for a in tier_a:
        print(f"    🅰️ {a['name']:<6} {a['code']:<8} 总评{a['total_score']:+d}(技术{a['tech_score']:+d}+基本{a['quality_score']:+d}) RSI={a['rsi']} 20日{a['ret20']:+.1f}% EMA={a['ema']}")
    print(f"\n  📊 阿狸咪 B 档({len(tier_b)}只) [技术分(信号×5)+基本面分=总评分]:")
    for b in tier_b:
        print(f"    🅱️ {b['name']:<6} {b['code']:<8} 总评{b['total_score']:+d}(技术{b['tech_score']:+d}+基本{b['quality_score']:+d}) RSI={b['rsi']} 20日{b['ret20']:+.1f}% 信号={b['early']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())