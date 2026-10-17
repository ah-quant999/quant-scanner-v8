#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶舱两盏预警灯 · 前向有效性审计（2026-08-29）
================================================
问题：驾驶舱「宏观环境灯（红/黄/绿）」与「短期波动结构灯（企稳/阴跌/反弹分歧/恐慌）」
      到底能不能预警？此前没有历史快照，无法回测 —— 只能从今天开始前向累积。

做法：
  1. 每个交易日盘后记录两盏灯的状态（与前端 renderCockpit 完全同一套判定逻辑）。
  2. 同时记录当日上证指数收盘价。
  3. 之后每次运行时，对已有记录回填 T+1/T+3/T+5/T+10 的上证真实收益。
  4. 累积 ≥20 个交易日后即可判定：哪个灯态之后大盘更容易涨/跌。

输出：raw_data/history/cockpit_light_audit.json

用法：
  python scripts/audit_cockpit_lights.py
"""
import json
import os
import sys
import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw_data")
HIST = os.path.join(RAW, "history")
OUT_JSON = os.path.join(HIST, "cockpit_light_audit.json")
IDX_PATH = os.path.join(RAW, "index_history.json")

MIN_SAMPLE = 20  # 至少多少条才输出判定


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def idx_closes():
    """上证指数 [(date, close), ...] 升序"""
    d = load_json(IDX_PATH, {})
    rows = []
    for r in d.get("klines", []):
        try:
            rows.append((r["d"], float(r["c"])))
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x[0])
    return rows


def forward_idx_returns(signal_date, holds=(1, 3, 5, 10)):
    """从 signal_date 次日收盘起算的上证区间收益(%)"""
    rows = idx_closes()
    if not rows:
        return None
    dates = [r[0] for r in rows]
    # 找到 signal_date 在序列中的位置
    try:
        i = max(j for j, dstr in enumerate(dates) if dstr <= signal_date)
    except ValueError:
        return None
    out = {}
    for n in holds:
        j = i + n
        if j >= len(rows):
            continue
        base = rows[i][1]
        if base <= 0:
            continue
        out[n] = round((rows[j][1] - base) / base * 100, 3)
    return out or None


def read_state():
    """读取当日两盏灯状态（与前端 renderCockpit 同一套判定）"""
    crisis = load_json(os.path.join(RAW, "crisis_data.json"), {})
    north = load_json(os.path.join(RAW, "north_fund.json"), {})
    alerts = load_json(os.path.join(RAW, "market_alerts.json"), {})
    vol = load_json(os.path.join(RAW, "volatility.json"), {})

    # ── 灯1：宏观环境（与 index.html renderCockpit 一致）──
    inds = crisis.get("indicators") or {}
    if inds:
        cat_sum, cat_cnt = {}, {}
        for it in inds.values():
            if it and it.get("cat") and it.get("score") is not None:
                cat_sum[it["cat"]] = cat_sum.get(it["cat"], 0) + it["score"]
                cat_cnt[it["cat"]] = cat_cnt.get(it["cat"], 0) + 1
        cM = cat_sum.get("货币", 0) / cat_cnt["货币"] if cat_cnt.get("货币") else 0
        cE = cat_sum.get("经济", 0) / cat_cnt["经济"] if cat_cnt.get("经济") else 0
        cG = cat_sum.get("全球", 0) / cat_cnt["全球"] if cat_cnt.get("全球") else 0
    else:
        cM = crisis.get("currency", 0) or 0
        cE = crisis.get("economy", 0) or 0
        cG = crisis.get("global", 0) or 0
    # 兼容 0~1 小数口径（前端会 ×100）
    crisis_score = round((cM * 0.4 + cE * 0.35 + cG * 0.25) * 100)
    if crisis_score == 0 and (cM or cE or cG):
        crisis_score = round((cM * 0.4 + cE * 0.35 + cG * 0.25))

    south_h = (north.get("south_history") or [])[-5:]
    north5 = sum((x.get("net_buy") or 0) for x in south_h)

    a_idx = [x for x in (alerts.get("indices") or [])
             if x.get("name") in ("上证指数", "深证成指", "创业板指", "科创50")]
    mkt_avg = sum((x.get("pct") or 0) for x in a_idx) / len(a_idx) if a_idx else 0.0

    if crisis_score >= 70 or mkt_avg <= -3:
        light1, light1_code = "红灯·仅观望", "red"
    elif crisis_score >= 50 or (north5 < 0 and crisis_score >= 40) or mkt_avg < 0:
        light1, light1_code = "黄灯·谨慎低吸", "yellow"
    else:
        light1, light1_code = "绿灯·可操作", "green"

    # ── 灯2：短期波动结构 ──
    comp = vol.get("composite") or {}
    vol_code = comp.get("regime_code") or "unknown"
    vol_name = comp.get("regime") or "暂无数据"

    return {
        "light1": light1,
        "light1_code": light1_code,
        "crisis_score": crisis_score,
        "mkt_avg": round(mkt_avg, 3),
        "north5": round(north5, 2),
        "light2": vol_name,
        "light2_code": vol_code,
    }


def run():
    today = datetime.date.today().isoformat()
    result = load_json(OUT_JSON, {"update_time": "", "days": [], "min_sample": MIN_SAMPLE})

    # 1) 回填历史记录的前向收益
    filled = 0
    for rec in result.get("days", []):
        if rec.get("fwd") is None or rec.get("fwd") == {}:
            r = forward_idx_returns(rec["date"])
            if r:
                rec["fwd"] = {str(k): v for k, v in r.items()}
                filled += 1

    # 2) 记录今日状态（同日重复运行则覆盖）
    st = read_state()
    st["date"] = today
    st["fwd"] = None
    result["days"] = [d for d in result.get("days", []) if d.get("date") != today]
    result["days"].append(st)
    result["days"].sort(key=lambda x: x["date"])
    result["update_time"] = datetime.datetime.now().isoformat(timespec="seconds")

    # 3) 汇总（样本足够时）
    summary = {}
    for key in ("light1_code", "light2_code"):
        grp = defaultdict(list)
        for rec in result["days"]:
            f = rec.get("fwd") or {}
            if not f:
                continue
            grp[rec.get(key, "unknown")].append(f)
        agg = {}
        for code, fwd_list in grp.items():
            n = len(fwd_list)
            per = {}
            for h in ("1", "3", "5", "10"):
                vals = [f[h] for f in fwd_list if h in f]
                if not vals:
                    continue
                per["T" + h] = {
                    "n": len(vals),
                    "avg": round(sum(vals) / len(vals), 3),
                    "win": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
                }
            agg[code] = {"n": n, "periods": per,
                         "ready": n >= MIN_SAMPLE}
        summary[key] = agg
    result["summary"] = summary
    result["n_days"] = len(result["days"])
    result["n_days_with_fwd"] = sum(1 for d in result["days"] if d.get("fwd"))

    save_json(OUT_JSON, result)
    print(f"[audit_cockpit_lights] 已记录 {today}：灯1={st['light1']} 灯2={st['light2']}")
    print(f"  累积 {result['n_days']} 天，其中 {result['n_days_with_fwd']} 天已回填前向收益（本次回填 {filled} 条）")
    print(f"  样本达 {MIN_SAMPLE} 条后开始输出有效/无效判定")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(BASE, "algorithms"))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("scripts/audit_cockpit_lights.py"):
        sys.exit(2)
    run()
