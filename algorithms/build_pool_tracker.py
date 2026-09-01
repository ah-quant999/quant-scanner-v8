#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pool_tracker.py — v8 选股生命周期跟踪（阶段 1）+ 二维精选（K 批·板块流入×情绪周期）

输入：
  raw_data/algo_track.json — v8 三大算法（四量终极 / 板块龙头 / 大牛股猎手）的真实跟踪池
  raw_data/sentiment_cycle.json — 情绪周期
  raw_data/sector_fund_flow.json — 板块资金流
  raw_data/stock_profile.json — 股票→行业/概念映射

算法：
  1. 合并三 algo 的 tracking 列表，按 code 去重（保留 peak_pct 最大者）。
  2. 专家阈值判状态（强势/回调买点/见顶/走弱/正常）。
  3. 【K 批新增】二维精选（板块流入 × 情绪周期）：
       - 板块：股票命中 top_in 板块→加分；命中 top_out→减分
       - 情绪：根据当前 phase（退潮/高潮/修复/冰点）+ status 适配
       - 阈值：selected_score >= 8 进精选池

输出：
  raw_data/v8_pool_tracker.json
  data/V8_POOL_TRACKER.js

🛡 一劳永逸：
  - 零网络依赖；空文件容错；状态阈值集中在 _status_decide()。
  - 【K 批】情绪/板块数据缺失 → 精选维度置 0 不阻断主流程；profile 缺失 → sector_match=none。
  - 【K 批修复】_selection_score 接收的 item 必须带 status 字段（原 bug：item 来自 merged 无 status 字段）。
"""
import json
import os
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")

ALGO_TRACK_PATH = os.path.join(RAW_DIR, "algo_track.json")
SENTIMENT_PATH = os.path.join(RAW_DIR, "sentiment_cycle.json")
SECTOR_FLOW_PATH = os.path.join(RAW_DIR, "sector_fund_flow.json")
STOCK_PROFILE_PATH = os.path.join(RAW_DIR, "stock_profile.json")
OUT_JSON_PATH = os.path.join(RAW_DIR, "v8_pool_tracker.json")
OUT_JS_PATH = os.path.join(DATA_DIR, "V8_POOL_TRACKER.js")

SELECT_THRESHOLD = 8.0
SECTOR_TOP_N = 20


def log(msg):
    print(f"  [pool-tracker] {msg}", flush=True)


def _status_decide(peak_pct, last_pct, days_in):
    drawdown = round(peak_pct - last_pct, 2)
    if peak_pct <= 0:
        return ("weak", None, "走弱：峰值未跑赢基准价")
    if drawdown >= 20:
        return ("weak", None, f"走弱：深回撤 {drawdown:.1f}%")
    if last_pct <= -8:
        return ("weak", None, "走弱：重挫破位")
    if drawdown >= 10 and days_in >= 3 and last_pct < 0:
        return ("topped", None, f"见顶：回撤 {drawdown:.1f}%、持仓 {days_in} 日")
    if drawdown >= 15 and peak_pct > 0:
        return ("topped", None, f"见顶：深回撤 {drawdown:.1f}%")
    if peak_pct > 0 and 6 <= drawdown <= 12 and last_pct < 0:
        return ("buy_dip", f"回调买点（回撤 {drawdown:.1f}%）", None)
    if drawdown <= 3 and peak_pct > 0:
        return ("strong", None, None)
    if days_in >= 3 and last_pct > 0 and peak_pct > 0:
        hint = f"连涨强势确认（{days_in} 天）" if days_in >= 3 else None
        return ("strong", hint, None)
    return ("normal", None, None)


def _load_json(path, label):
    if not os.path.exists(path):
        log(f"⚠️ {label} 缺失：{path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"⚠️ {label} 解析失败：{e}")
        return None


def load_algo_track():
    return _load_json(ALGO_TRACK_PATH, "algo_track")


def load_sentiment_cycle():
    return _load_json(SENTIMENT_PATH, "情绪周期")


def load_sector_fund_flow():
    return _load_json(SECTOR_FLOW_PATH, "板块资金流")


def load_stock_profile():
    raw = _load_json(STOCK_PROFILE_PATH, "股票画像")
    if raw is None:
        return None
    return raw.get("profiles") if isinstance(raw, dict) else None


def dedupe_by_code(algos):
    """合并多 algo 的 tracking，按 code 去重（保留 peak_pct 最大者），
    并记录命中过的所有 algo 名（_algos_hit，用于阶段 2 多算法共识度 consensus_count）。"""
    best = {}
    for alg in algos:
        algo_key = alg.get("algo", "")
        display = alg.get("display_name", algo_key)
        for t in alg.get("tracking", []):
            code = t.get("code")
            if not code:
                continue
            peak = float(t.get("peak_pct") or 0)
            prev = best.get(code)
            if prev is None:
                best[code] = dict(t, _algo=display, _algos_hit=[display])
            elif peak > float(prev.get("peak_pct") or 0):
                # 新高者覆盖完整记录，但继承已累积的命中算法列表
                best[code] = dict(t, _algo=display, _algos_hit=list(prev.get("_algos_hit", [display])))
            else:
                # 同一 code 多次命中（非新高），累加 algo 名（去重）
                if display not in prev.get("_algos_hit", []):
                    prev["_algos_hit"].append(display)
    return list(best.values())


def _signal_type(it, reason, algos_hit):
    """阶段 2：推导信号类型（短线买点/反弹/加速/强势/回调/板块联动/强势突破/多算法共识）。
    优先多算法共识（≥2 个 algo 命中）；否则按 algo + signal_detail.reason 关键词兜底。"""
    if len(set(algos_hit)) >= 2:
        return "多算法共识"
    r = reason or ""
    if "加速" in r:
        return "加速"
    if "反弹" in r:
        return "反弹"
    if "突破" in r or "强势" in r:
        return "强势"
    if "回调" in r:
        return "回调"
    algo = it.get("_algo", "")
    if algo == "四量终极":
        return "短线买点"
    if algo == "板块龙头":
        return "板块联动"
    if algo == "大牛股猎手":
        return "强势突破"
    return "其他"


def _sector_match_item(item, sector_top_in, sector_top_out):
    item_concepts = set(item.get("_concepts", []) or [])
    item_industry = item.get("_industry", "") or ""
    best_match, best_concept, best_net = "none", "", 0.0
    best_abs = 0.0
    for s in sector_top_in:
        name = s.get("name", "")
        net = float(s.get("net") or 0)
        if not name or net <= 0:
            continue
        if name in item_concepts or name == item_industry:
            if abs(net) > best_abs:
                best_match = "top_inflow"
                best_concept = name
                best_net = net
                best_abs = abs(net)
    for s in sector_top_out:
        name = s.get("name", "")
        net = float(s.get("net") or 0)
        if not name or net >= 0:
            continue
        if name in item_concepts or name == item_industry:
            if abs(net) > best_abs:
                best_match = "outflow"
                best_concept = name
                best_net = net
                best_abs = abs(net)
    return best_match, best_concept, best_net


def _selection_score(item, phase, sector_top_in, sector_top_out):
    sector_bonus = 0.0
    sentiment_match = "neutral"
    sector_match, concept_top, sector_net = _sector_match_item(
        item, sector_top_in, sector_top_out
    )
    if sector_match == "top_inflow":
        sector_bonus = round(sector_net / 10.0, 2)
    elif sector_match == "outflow":
        sector_bonus = round(sector_net / 10.0, 2)

    status = item.get("status", "normal")
    if phase == "退潮":
        if status == "buy_dip" and sector_match == "top_inflow":
            sentiment_bonus, sentiment_match = 8, "ok"
        elif status == "strong" and sector_match == "top_inflow":
            sentiment_bonus, sentiment_match = 3, "caution"
        elif status == "buy_dip":
            sentiment_bonus, sentiment_match = 2, "neutral"
        elif status == "topped":
            sentiment_bonus, sentiment_match = -2, "caution"
        elif status == "weak" and sector_match == "outflow":
            sentiment_bonus, sentiment_match = -5, "reverse"
        elif status == "weak":
            sentiment_bonus, sentiment_match = -1, "caution"
        else:
            sentiment_bonus, sentiment_match = 0, "neutral"
    elif phase in ("高潮", "修复"):
        if status == "strong" and sector_match == "top_inflow":
            sentiment_bonus, sentiment_match = 8, "ok"
        elif status == "buy_dip" and sector_match == "top_inflow":
            sentiment_bonus, sentiment_match = 5, "ok"
        elif status == "strong":
            sentiment_bonus, sentiment_match = 4, "ok"
        else:
            sentiment_bonus, sentiment_match = 0, "neutral"
    else:
        if sector_match == "top_inflow":
            sentiment_bonus, sentiment_match = 5, "ok"
        elif sector_match == "outflow":
            sentiment_bonus, sentiment_match = -3, "caution"
        else:
            sentiment_bonus, sentiment_match = 0, "neutral"

    status_base = {"strong": 3, "buy_dip": 5, "topped": 1, "weak": 0, "normal": 1}.get(status, 1)
    selected_score = round(status_base + sector_bonus + sentiment_bonus, 2)
    selected = selected_score >= SELECT_THRESHOLD
    return (round(sector_bonus, 2), sentiment_bonus, sector_match, concept_top,
            round(sector_net, 2), sentiment_match, selected_score, selected)


def build_items(merged, sentiment, sector_flow, profile_map):
    phase = (sentiment or {}).get("phase", "未知") if sentiment else "未知"
    sector_top_in = ((sector_flow or {}).get("sectors_in") or [])[:SECTOR_TOP_N]
    sector_top_out = ((sector_flow or {}).get("sectors_out") or [])[:SECTOR_TOP_N]

    items = []
    for it in merged:
        peak = float(it.get("peak_pct") or 0)
        last = float(it.get("last_pct") or 0)
        days = int(it.get("days_in") or 0)
        status, buy_hint, sell_hint = _status_decide(peak, last, days)
        code = it["code"]
        prof = (profile_map or {}).get(code, {}) or {}
        # 阶段 2：多算法共识 + 信号类型
        algos_hit = it.get("_algos_hit", [it.get("_algo", "")])
        consensus_count = len(set(algos_hit))
        _reason = (it.get("signal_detail") or {}).get("reason", "")
        signal_type = _signal_type(it, _reason, algos_hit)
        # 🔧 K 批修复：必须把 status 也注入 it_for_select（否则 _selection_score 走 normal 分支）
        it_for_select = dict(it, _industry=prof.get("industry", ""),
                              _concepts=prof.get("concepts", []),
                              status=status)

        (sector_bonus, sentiment_bonus, sector_match, concept_top, sector_net,
         sentiment_match, selected_score, selected) = _selection_score(
            it_for_select, phase, sector_top_in, sector_top_out
        )

        items.append({
            "code": code,
            "name": it.get("name", ""),
            "algo": it.get("_algo", ""),
            "list_date": it.get("list_date_dashed") or it.get("list_date", ""),
            "entry_price": float(it.get("entry_price") or 0),
            "last_close": float(it.get("last_close") or 0),
            "last_pct": last,
            "peak_pct": peak,
            "drawdown": round(peak - last, 2),
            "days_in": days,
            "appear_count": int(it.get("appear_count") or 1),
            "status": status,
            "buy_hint": buy_hint,
            "sell_hint": sell_hint,
            "signal_reason": (it.get("signal_detail") or {}).get("reason", ""),
            # 阶段 2：多算法共识 + 信号类型
            "algos_hit": algos_hit,
            "consensus_count": consensus_count,
            "signal_type": signal_type,
            # K 批精选维度
            "industry": prof.get("industry", ""),
            "concept_top": concept_top,
            "sector_match": sector_match,
            "sector_net": sector_net,
            "sector_bonus": sector_bonus,
            "sentiment_match": sentiment_match,
            "sentiment_bonus": sentiment_bonus,
            "selected_score": selected_score,
            "selected": selected,
        })
    return items


def aggregate(items):
    status_counts = defaultdict(int)
    by_algo = defaultdict(lambda: defaultdict(int))
    selected_count = 0
    for it in items:
        status_counts[it["status"]] += 1
        by_algo[it["algo"]]["total"] += 1
        by_algo[it["algo"]][it["status"]] += 1
        if it.get("selected"):
            selected_count += 1
    return dict(status_counts), {k: dict(v) for k, v in by_algo.items()}, selected_count


def main():
    print(f"[build_pool_tracker] {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("读取 v8 算法跟踪池（零网络依赖）…")
    data = load_algo_track()
    sentiment = load_sentiment_cycle()
    sector_flow = load_sector_fund_flow()
    profile_map = load_stock_profile()
    if sentiment:
        log(f"情绪周期：phase={sentiment.get('phase','?')} score={sentiment.get('score','?')} delta={sentiment.get('delta_pct','?')}%")
    if sector_flow:
        log(f"板块资金：top_in={len(sector_flow.get('sectors_in',[]))} top_out={len(sector_flow.get('sectors_out',[]))}")
    if profile_map:
        log(f"股票画像：覆盖 {len(profile_map)} 只")

    if not data:
        log("❌ algo_track.json 不可用，输出空占位")
        out = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pool_size": 0, "raw_pool_size": 0, "selected_size": 0,
            "status_counts": {}, "by_algo": {}, "items": [],
            "sentiment_meta": None, "sector_meta": None,
            "note": "algo_track.json 缺失或解析失败",
        }
    else:
        raw_pool_size = sum(len(a.get("tracking", [])) for a in data.get("algos", []))
        merged = dedupe_by_code(data.get("algos", []))
        items = build_items(merged, sentiment, sector_flow, profile_map)
        status_counts, by_algo, selected_count = aggregate(items)
        consensus_count = sum(1 for it in items if it.get("consensus_count", 0) >= 2)
        def _sort_key(it):
            if it["status"] == "strong":
                return (0, -it["peak_pct"], -it["days_in"])
            if it["status"] == "buy_dip":
                return (0, it["drawdown"], -it["days_in"])
            return (0, -it["peak_pct"], -it["days_in"])
        items.sort(key=_sort_key)
        out = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pool_size": len(items),
            "raw_pool_size": raw_pool_size,
            "selected_size": selected_count,
            "consensus_count": consensus_count,
            "status_counts": status_counts,
            "by_algo": by_algo,
            "items": items,
            "sentiment_meta": {
                "phase": (sentiment or {}).get("phase"),
                "score": (sentiment or {}).get("score"),
                "delta_pct": (sentiment or {}).get("delta_pct"),
                "advice": (sentiment or {}).get("advice"),
                "source": (sentiment or {}).get("source"),
            } if sentiment else None,
            "sector_meta": {
                "top_in": [
                    {"name": s.get("name"), "type": s.get("type"), "net": s.get("net")}
                    for s in (sector_flow.get("sectors_in") or [])[:5]
                ],
                "top_out": [
                    {"name": s.get("name"), "type": s.get("type"), "net": s.get("net")}
                    for s in (sector_flow.get("sectors_out") or [])[:3]
                ],
            } if sector_flow else None,
            "select_threshold": SELECT_THRESHOLD,
            "note": (
                f"基于 v8 三大算法跟踪池 {raw_pool_size} 只去重 → {len(items)} 只；"
                f"K 批二维精选（板块流入 × 情绪周期 {((sentiment or {}).get('phase')) or '未知'}）→ 进精选 {selected_count} 只；"
                "阈值源自专家 track_daily.py analyze()（强势/回调6-12%/见顶/走弱）"
            ),
        }
        log(f"✅ 入池 {len(items)} 只（去重前 {raw_pool_size}）；精选 {selected_count} 只；多算法共识 {consensus_count} 只；状态分布 {dict(status_counts)}")

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log(f"📝 raw_data → {OUT_JSON_PATH}")

    os.makedirs(DATA_DIR, exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    js_body = (
        "/* v8 选股生命周期跟踪 · 自动生成，请勿手改 */\n"
        "window.V8_POOL_TRACKER = " + payload + ";\n"
    )
    with open(OUT_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_body)
    log(f"📝 data → {OUT_JS_PATH} ({len(js_body)} bytes)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())