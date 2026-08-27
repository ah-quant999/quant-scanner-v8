#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track_h_auto_buy.py — H 反推算法的每日跟踪 + 累积胜率
=====================================================

🎯 职责：
  - 读 raw_data/h_auto_buy_YYYYMMDD.json 拿到「昨日」候选股
  - 用 gtimg 拉每只股票从「昨日」到「今日」的日线（最多 10 个交易日）
  - 算 T+1/T+3/T+5/T+10 涨跌幅 + 是否「有效买点」（>=5% 视为命中）
  - 写入 raw_data/h_auto_buy_history.json（累积，跨日去重保留最新跟踪记录）
  - 输出 data/H_AUTO_BUY_TRACK.js 给前端展示胜率表（admin-only 调试卡）

📐 规则（与主人 PDF 的「短线买点」定义一致）：
  - 命中 = 候选日的下一个交易日相对候选日收盘价 涨幅 >= 5%  → T+1 hit
  - 跟踪日最大 = T+10（候选后 10 个交易日内的最高涨幅命中即算）
  - 候选后第 N 日价格取不到（停牌/退市）→ 跳过该样本

🚫 无 PDF/OCR 依赖：仅 data_source_gtimg + raw_data 既有 h_auto_buy_*.json。

📤 输出：
  - raw_data/h_auto_buy_history.json — 累积历史（含每日候选 + 跟踪结果）
  - data/H_AUTO_BUY_TRACK.js — 前端 window.H_AUTO_BUY_TRACK（带 ?v=）
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = ROOT / "raw_data"
ALGO_DIR = ROOT / "algorithms"
OUT_JS_TRACK = DATA_DIR / "H_AUTO_BUY_TRACK.js"

HISTORY_FILE = RAW_DIR / "h_auto_buy_history.json"
HIT_PCT = 5.0   # T+N 涨幅 >= 5% 视为「成功短线买点」
MAX_LOOKBACK = 10  # 候选后最多看 10 个交易日


def _norm_code(code):
    return re.sub(r"\D", "", str(code or ""))


def load_window_var(path, var_name):
    """读 data/*.js 的 window.XXX = {...}; 形式"""
    if not path.exists():
        return None
    src = open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s\s*=\s*(\{.*?\})\s*;?\s*$" % var_name, src, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return json.loads(m.group(1).replace("'", '"'))


def _gtimg_kl(code, bars=30):
    """从 腾讯 gtimg 拉近 N 日 K线（避免 data_source_gtimg 不存在的硬错）"""
    try:
        sys.path.insert(0, str(ALGO_DIR))
        from data_source_gtimg import fetch_a_daily_gtimg
    except Exception as e:
        print(f"  ⚠️ 导入 data_source_gtimg 失败: {e}")
        return None
    try:
        c = _norm_code(code)
        if c.startswith(("60", "68", "90", "11", "13", "5", "1")):
            market = "sh"
        elif c.startswith(("00", "30", "20")):
            market = "sz"
        elif c.startswith(("8", "43", "92")):
            market = "bj"
        else:
            market = "sh"
        df = fetch_a_daily_gtimg(c, market=market, bars=bars)
        if df is None:
            return None
        # 标准 DataFrame：date/open/high/low/close/volume/pct_chg
        return [(row["date"], float(row["close"])) for _, row in df.iterrows()]
    except Exception as e:
        return None


def track_one_pick(code, pick_date_str, today_str):
    """对一只候选：拿到候选日及之后 ~10 个交易日的收盘价。
    返回 dict: {T+1/T+3/T+5/T+10 涨幅、命中标志、最佳涨幅}"""
    kl = _gtimg_kl(code, bars=70)  # 🔴 2026-08-27 修复：fetch_a_daily_gtimg 要求 ≥60 条，之前 bars=40 永远 None
    if not kl:
        return None
    # 把 kl 索引化（list of dict）
    rows = [{"date": d, "close": c} for d, c in kl]
    # 找候选日 idx
    pick_idx = None
    for i, r in enumerate(rows):
        if r["date"] >= pick_date_str:
            pick_idx = i
            break
    if pick_idx is None:
        return None
    base_close = rows[pick_idx]["close"]
    if not base_close:
        return None
    out = {
        "code": code,
        "pick_date": pick_date_str,
        "base_close": base_close,
        "samples": len(rows) - pick_idx - 1,
        "T+1": None, "T+1_hit": None,
        "T+3": None, "T+3_hit": None,
        "T+5": None, "T+5_hit": None,
        "T+10": None, "T+10_hit": None,
        "best_T_plus": None, "best_pct": None,
    }
    horizons = {1: "T+1", 3: "T+3", 5: "T+5", 10: "T+10"}
    best_pct = None
    for n, key in horizons.items():
        if pick_idx + n < len(rows):
            close_n = rows[pick_idx + n]["close"]
            pct = round((close_n - base_close) / base_close * 100, 2)
            out[key] = pct
            out[key + "_hit"] = bool(pct >= HIT_PCT)
            if best_pct is None or pct > best_pct:
                best_pct = pct
                out["best_T_plus"] = n
                out["best_pct"] = pct
    return out


def load_history():
    if not HISTORY_FILE.exists():
        # 🛡 2026-08-19 一劳永逸：顶层带 generated/update_time（v8_health_check 找时戳用，缺时戳永远判"无法判龄"）
        return {"first_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "by_date": {}, "summary": {"days": 0, "tracked_picks": 0, "T+1_hit": 0, "T+3_hit": 0, "T+5_hit": 0, "T+10_hit": 0}}
    try:
        h = json.load(open(HISTORY_FILE, encoding="utf-8"))
        # 老文件无顶层时戳 → 当作历史补打一次
        if "update_time" not in h or "generated" not in h:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            h["generated"] = ts
            h["update_time"] = ts
        return h
    except Exception:
        return {"by_date": {}, "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _load_candidates(target_date):
    """读 target_date 的候选股。

    主源：raw_data/h_auto_buy_<date>.json（auto_run_dn_algorithm.py 产出）。
    🛡 兜底（2026-08-23 修复）：云端流水线若时序错位（track 早于 auto_run 跑），
       raw json 缺失/为空 → 静默 0 样本，导致「H反推」永远比不出胜率。
       此时退回已部署且每日刷新的 data/H_AUTO_BUY.js（含 date + candidates），
       用快照里的真实候选日做 key，保证每日跟踪不落空。
    返回 (candidates_list, real_date_str)。主源可用时 real_date=target_date。
    """
    pick_file = RAW_DIR / f"h_auto_buy_{target_date.replace('-', '')}.json"
    if pick_file.exists():
        try:
            pick = json.load(open(pick_file, encoding="utf-8"))
            cands = pick.get("candidates", []) or []
            if cands:
                return cands, target_date
        except Exception:
            pass
    # 兜底：data/H_AUTO_BUY.js
    hjs = DATA_DIR / "H_AUTO_BUY.js"
    if hjs.exists():
        try:
            src = open(hjs, encoding="utf-8").read()
            m = re.search(r"window\.H_AUTO_BUY\s*=\s*(\{.*?\});\s*$", src, re.S)
            if m:
                d = json.loads(m.group(1))
                cands = d.get("candidates", []) or []
                if cands:
                    real = d.get("date") or target_date
                    print(f"  🛡 主源缺失/空，兜底读 data/H_AUTO_BUY.js（候选日 {real}，{len(cands)} 只）")
                    return cands, real
        except Exception:
            pass
    return None, target_date


def run(target_date=None, emit_js=True, top_n=50):
    """
    把 target_date（默认昨日）的 h_auto_buy 候选股全部跟踪一遍，
    写进 history + 重新计 summary + 输出 H_AUTO_BUY_TRACK.js。
    每日盘后调度：拿到昨日候选 → 等到今天才能算 T+1。
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    candidates, real_date = _load_candidates(target_date)
    if candidates is None:
        print(f"❌ 候选文件不存在且 data/H_AUTO_BUY.js 无候选: target={target_date}")
        return None

    history = load_history()
    day_rec = history["by_date"].get(real_date, {"picks": []})

    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"📊 跟踪 {real_date} 的 {len(candidates)} 只候选（top {top_n}）")
    tracked = []
    ok = 0
    for i, c in enumerate(candidates):
        code = c.get("code") or _norm_code(c.get("symbol", ""))
        if not code:
            continue
        rec = track_one_pick(code, real_date, today_str)
        if rec is None:
            continue
        rec["name"] = c.get("name", "")
        rec["industry"] = c.get("industry", "")
        rec["pct_at_pick"] = c.get("pct")
        rec["vol_ratio_at_pick"] = c.get("vol_ratio")
        tracked.append(rec)
        ok += 1
        if ok % 10 == 0:
            print(f"   ... {ok}/{len(candidates)}")

    # 累计当日 summary
    s = {
        "picks": tracked,
        "n": len(tracked),
        "T+1_hit": sum(1 for r in tracked if r.get("T+1_hit")),
        "T+3_hit": sum(1 for r in tracked if r.get("T+3_hit")),
        "T+5_hit": sum(1 for r in tracked if r.get("T+5_hit")),
        "T+10_hit": sum(1 for r in tracked if r.get("T+10_hit")),
        "tracked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    s["T+1_rate"] = round(s["T+1_hit"] / s["n"] * 100, 1) if s["n"] else 0
    s["T+5_rate"] = round(s["T+5_hit"] / s["n"] * 100, 1) if s["n"] else 0
    history["by_date"][real_date] = s
    history["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 🔴 2026-08-22 主人令修复：顶层 update_time 必须随每次生成刷新，
    #   否则 v8_health_check/前端判龄一直读到旧时戳（08-20）误判陈旧
    history["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 重算 cumulative summary
    summary = {"days": 0, "tracked_picks": 0,
               "T+1_hit": 0, "T+3_hit": 0, "T+5_hit": 0, "T+10_hit": 0}
    for d, rec in history["by_date"].items():
        if "n" in rec and rec["n"]:
            summary["days"] += 1
            summary["tracked_picks"] += rec["n"]
            summary["T+1_hit"] += rec.get("T+1_hit", 0)
            summary["T+3_hit"] += rec.get("T+3_hit", 0)
            summary["T+5_hit"] += rec.get("T+5_hit", 0)
            summary["T+10_hit"] += rec.get("T+10_hit", 0)
    if summary["tracked_picks"]:
        summary["T+1_rate"] = round(summary["T+1_hit"] / summary["tracked_picks"] * 100, 1)
        summary["T+5_rate"] = round(summary["T+5_hit"] / summary["tracked_picks"] * 100, 1)
        summary["T+10_rate"] = round(summary["T+10_hit"] / summary["tracked_picks"] * 100, 1)
    history["summary"] = summary

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"✅ {HISTORY_FILE.name}: 累计 {summary['tracked_picks']} picks · "
          f"T+1 winrate {summary.get('T+1_rate', 0)}% · "
          f"T+5 winrate {summary.get('T+5_rate', 0)}%")

    if emit_js:
        payload = "/* H 反推算法跟踪 / 累积胜率（脱离 PDF OCR） */\n" \
                  "window.H_AUTO_BUY_TRACK = " + json.dumps(history, ensure_ascii=False) + ";\n"
        OUT_JS_TRACK.write_text(payload, encoding="utf-8")
        print(f"✅ {OUT_JS_TRACK.name} 已写入")
    return history


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="候选日 YYYY-MM-DD（默认昨日）")
    p.add_argument("--top", type=int, default=50, help="最多跟踪几只（默认 top50）")
    p.add_argument("--no-emit", dest="emit_js", action="store_false")
    # 🛡 2026-08-19 默认 emit_js ON：daily 调用无需 flag，部署口径统一
    p.set_defaults(emit_js=True)
    args = p.parse_args()
    out = run(target_date=args.date, emit_js=args.emit_js, top_n=args.top)
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
