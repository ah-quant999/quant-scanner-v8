#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_triple_track.py — 三重共识「历史追踪」跟踪 + 回测分析器

读取：
  - data/triple_resonance_history.json  （update_triple_resonance_history.py 产出的本地累积）
  - data/gold_pool.json                 （当前收盘价/最新）
  - data/fundamental_quality.json       （催化剂 news.tags / 评分加减）
  - data/backtest_comprehensive.json    （baostock 真实收盘价滚动回测，信号层）
  - data/top10_daily.json               （TOP10≥70，用于全站精选重叠度）
  （2026-09-06 审计修复：cockpit_backtest.json / cockpit_tier_recommend.json 随驾驶舱 09-03 下线，
   相关读取与重叠度输出已移除——文件不存在时此前输出「与驾驶舱重叠 0」属伪数据）

写出：data/triple_track.json（前端 历史追踪 页消费）

覆盖 8 项能力：
  1) 持仓盈亏跟踪   2) 状态迁移告警   3) 催化剂兑现追踪
  4) 回测 N 日胜率（真实信号层 + 前向累积）  5) 严格 vs 宽松对比
  6) 阈值敏感性   7) 板块聚类   8) 全站精选重叠度

原则：不编造数据；样本不足处明确标注"积累中"。
"""
import json
import os
import re

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE, "..", "raw_data")  # 🔴 2026-08-06 改 raw_data：fundamental/top10/backtest 输入均已持久化在 raw_data（out/ 被 gitignore 云端丢）
OUT = os.path.join(DATA_DIR, "triple_track.json")
# 2026-08-06 补：line 57 `def load_meta_map(path=META_FILE)` 引用了本文件从未定义的 META_FILE
# （复制自 gen_triple_consensus.py 时漏带常量），默认参数在定义时即求值 → 每轮 NameError 必崩，
# out/triple_track.json 从未生成，前端「历史追踪」长期吃 08-04 僵尸数据。定义与 consensus 一致。
META_FILE = os.path.join(WORKSPACE, "stock_industry_concepts.json")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def ncode(c):
    return str(c or "").replace("sh_", "").replace("sz_", "").replace("hk_", "").replace("bj_", "").replace("sh.", "").replace("sz.", "").replace("hk.", "").replace("bj.", "").strip()


def r2(x):
    try:
        return round(float(x), 2)
    except Exception:
        return 0.0


def _gp_latest_close(gp_stock):
    """🛡 2026-08-28 修复：gold_pool.json 的 stock 没有 'latest.close'，
    真实最新价在 history[-1].close。统一读取，兜底旧的 latest 结构。"""
    if not isinstance(gp_stock, dict):
        return None
    hist = gp_stock.get("history") or []
    if isinstance(hist, list) and hist:
        last = hist[-1]
        if isinstance(last, dict):
            return last.get("close")
    latest = gp_stock.get("latest") or {}
    return latest.get("close")


def load_meta_map(path=META_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def board_from_code(code):
    c = re.sub(r"[^0-9]", "", str(code))
    if not c:
        return ""
    if c.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return ""


def main():
    print(f"  三重共识 跟踪/回测分析  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    history = load_json(os.path.join(DATA_DIR, "triple_resonance_history.json"), {})
    gold_pool = load_json(os.path.join(DATA_DIR, "gold_pool.json"), {})
    fq = load_json(os.path.join(DATA_DIR, "fundamental_quality.json"), {})
    bc = load_json(os.path.join(DATA_DIR, "backtest_comprehensive.json"), {})
    top10 = load_json(os.path.join(DATA_DIR, "top10_daily.json"), {})
    # 2026-09-06 审计修复：cockpit_backtest.json / cockpit_tier_recommend.json 读取移除（驾驶舱 09-03 下线）

    fq_stocks = fq.get("stocks", {}) if isinstance(fq, dict) else {}
    gp_stocks = gold_pool.get("stocks", {}) if isinstance(gold_pool, dict) else {}
    meta_map = load_meta_map()
    price_hist = history.get("_stock_price_history", {})
    tracking = history.get("_tracking_latest", {})
    meta = history.get("_meta", {})

    # 🛡 2026-09-06 一劳永逸：只认 YYYY-MM-DD 日期键——任何非日期脏键（如顶层 update_time）
    # 都不再可能被排序成「今天」（此前 "update_time" > "2026-…" 导致 today 取错、当日记录恒空、三卡全空）
    date_keys = sorted([k for k in history.keys() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)])
    today = date_keys[-1] if date_keys else datetime.now().strftime("%Y-%m-%d")
    today_records = history.get(today, []) if isinstance(history.get(today), list) else []

    # ---------- 1) 持仓盈亏跟踪 + 3) 催化剂兑现 ----------
    tracked = []
    for r in today_records:
        code = ncode(r.get("code", ""))
        meta = meta_map.get(code) or {}
        if not r.get("industry"):
            r["industry"] = meta.get("industry") or ""
        if not r.get("board"):
            r["board"] = meta.get("board") or board_from_code(code) or r.get("board", "")
        if (not r.get("sectors") or len(r.get("sectors", [])) == 0) and meta.get("concepts"):
            r["sectors"] = list(meta.get("concepts"))[:6]
        if meta.get("concepts") and not r.get("concepts"):
            r["concepts"] = meta.get("concepts")
        tr = tracking.get(code, {})
        enter_date = tr.get("enter_date", today)
        first_close = price_hist.get(code, {}).get(enter_date)
        current_close = price_hist.get(code, {}).get(today) or _gp_latest_close(gp_stocks.get(code, {}))
        pnl = None
        if first_close and current_close and first_close > 0:
            pnl = r2((current_close / first_close - 1) * 100)
        hold_days = tr.get("total_days", 1)
        consecutive = tr.get("streak", 1)

        # 催化剂
        fq_rec = fq_stocks.get(code) or fq_stocks.get("sh_" + code) or fq_stocks.get("sz_" + code) or fq_stocks.get("hk_" + code) or fq_stocks.get("bj_" + code)
        catalysts = []
        if fq_rec and isinstance(fq_rec.get("news"), dict):
            tags = fq_rec["news"].get("tags") or []
            nscore = fq_rec["news"].get("score", 0)
            for t in tags:
                # 兑现判定：入选以来是否价涨反应
                if pnl is None:
                    reaction = "—"
                elif pnl >= 3:
                    reaction = "已兑现(价涨)"
                elif pnl <= -3:
                    reaction = "走弱"
                else:
                    reaction = "观察中"
                catalysts.append({"tag": t, "score": nscore, "reaction": reaction})

        tracked.append({
            "code": code,
            "name": r.get("name", ""),
            "market": r.get("market", ""),
            "board": r.get("board", ""),
            "status": r.get("status", ""),
            "total_score": r.get("total_score", 0),
            "quality_grade": r.get("quality_grade", ""),
            "industry": r.get("industry", ""),
            "sectors": r.get("sectors", []),
            "signal_count": r.get("signal_count", 0),
            "enter_date": enter_date,
            "hold_days": hold_days,
            "consecutive_days": consecutive,
            "first_close": first_close,
            "current_close": current_close,
            "pnl_pct": pnl,
            "catalysts": catalysts,
        })
    tracked.sort(key=lambda x: -(x["pnl_pct"] if x["pnl_pct"] is not None else -999))

    # ---------- 2) 状态迁移告警 ----------
    alerts = []
    for code, tr in tracking.items():
        name = ""
        for r in today_records:
            if ncode(r.get("code")) == code:
                name = r.get("name", "")
                break
        if not name:
            # 从掉出记录找名字
            for dk in date_keys:
                for rr in (history.get(dk) if isinstance(history.get(dk), list) else []):
                    if not isinstance(rr, dict):
                        continue
                    if ncode(rr.get("code")) == code:
                        name = rr.get("name", "")
                        break
                if name:
                    break
        last = tr.get("last_date", "")
        if tr.get("status") == "dropped" and last and last != today:
            alerts.append({"level": "warn", "code": code, "name": name,
                           "text": f"{name}({code}) 于 {last} 跌出共识（曾连续 {tr.get('streak',0)} 日）"})
        elif tr.get("status") == "strict" and tr.get("streak", 0) >= 3:
            alerts.append({"level": "good", "code": code, "name": name,
                           "text": f"{name}({code}) 连续 {tr.get('streak')} 日稳居严格共识（高质量）"})
        if tr.get("status") != "dropped":
            # 入选以来大幅回撤告警
            fc = price_hist.get(code, {}).get(tr.get("enter_date", ""))
            cc = price_hist.get(code, {}).get(today)
            if fc and cc and fc > 0:
                p = (cc / fc - 1) * 100
                if p <= -8:
                    alerts.append({"level": "warn", "code": code, "name": name,
                                   "text": f"{name}({code}) 入选以来回撤 {p:.1f}%（{tr.get('enter_date')} 起）"})

    # ---------- 4) 回测 N 日胜率（真实信号层，来自 backtest_comprehensive）----------
    overview = bc.get("overview", {}) if isinstance(bc, dict) else {}
    res_all = overview.get("resonance_all", {})
    periods_src = res_all.get("periods", {}) if isinstance(res_all, dict) else {}
    period_map = {"1d": "hold_1d", "3d": "hold_3d", "5d": "hold_5d", "10d": "hold_10d", "20d": "hold_20d"}
    backtest_signal = {
        "method": bc.get("method", ""),
        "latest_date": bc.get("calc_time", ""),
        "total": res_all.get("total", 0),
        "best_hold_days": res_all.get("best_hold_days", 0),
        "periods": {},
    }
    for lbl, key in period_map.items():
        p = periods_src.get(key, {})
        if p:
            backtest_signal["periods"][lbl] = {
                "win_rate": r2(p.get("win_rate")),
                "avg_return": r2(p.get("avg_return")),
                "sharpe": r2(p.get("sharpe_ratio")),
                "count": p.get("count", 0),
                "best": r2(p.get("best_return")),
                "worst": r2(p.get("worst_return")),
            }

    # ---------- 6) 阈值敏感性（真实，来自 backtest_comprehensive.overview 分组）----------
    threshold_sensitivity = []
    band_map = {"resonance_gte80": "≥80", "resonance_gte70_lt80": "70~80"}
    for grp, band in band_map.items():
        g = overview.get(grp, {})
        gp5 = g.get("periods", {}).get("hold_5d", {})
        threshold_sensitivity.append({
            "band": band,
            "count": g.get("total", 0),
            "win_rate_5d": r2(gp5.get("win_rate")),
            "avg_ret_5d": r2(gp5.get("avg_return")),
            "best_win_rate": r2(g.get("best_win_rate")),
            "best_hold_days": g.get("best_hold_days", 0),
        })

    # ---------- 5) 严格 vs 宽松对比（真实，来自 backtest_comprehensive.comparison）----------
    comparison = bc.get("comparison", {}) if isinstance(bc, dict) else {}
    strict_vs_loose = {"periods": []}
    # 取 resonance_all(严格共振) 与 signal_ge2(宽松信号) 对比
    for lbl, key in period_map.items():
        c = comparison.get(key, {})
        strict = c.get("resonance_all", {})
        loose = c.get("signal_ge2", {})
        strict_vs_loose["periods"].append({
            "period": lbl,
            "strict_win": r2(strict.get("win_rate")),
            "strict_ret": r2(strict.get("avg_return")),
            "strict_count": strict.get("count", 0),
            "loose_win": r2(loose.get("win_rate")),
            "loose_ret": r2(loose.get("avg_return")),
            "loose_count": loose.get("count", 0),
        })

    # ---------- 4b) 前向累积回测（来自本策略自身价格历史，样本积累中）----------
    all_dates = date_keys
    self_per_stock = []
    self_agg = {lbl: {"count": 0, "win": 0, "avg": 0.0} for lbl in period_map}
    for code, tr in tracking.items():
        ed = tr.get("enter_date")
        if ed not in all_dates:
            continue
        idx = all_dates.index(ed)
        ph = price_hist.get(code, {})
        p0 = ph.get(ed)
        if not p0:
            continue
        row = {"code": code, "name": "", "enter_date": ed, "offsets": {}}
        # 名字
        for r in today_records:
            if ncode(r.get("code")) == code:
                row["name"] = r.get("name", "")
                break
        if not row["name"]:
            for dk in date_keys:
                for rr in (history.get(dk) if isinstance(history.get(dk), list) else []):
                    if not isinstance(rr, dict):
                        continue
                    if ncode(rr.get("code")) == code:
                        row["name"] = rr.get("name", "")
                        break
                if row["name"]:
                    break
        has_any = False
        for lbl, off in (("1d", 1), ("3d", 3), ("5d", 5), ("10d", 10), ("20d", 20)):
            ti = idx + off
            if ti < len(all_dates):
                tp = ph.get(all_dates[ti])
                if tp and p0 > 0:
                    ret = (tp / p0 - 1) * 100
                    row["offsets"][lbl] = r2(ret)
                    self_agg[lbl]["count"] += 1
                    if ret > 0:
                        self_agg[lbl]["win"] += 1
                    self_agg[lbl]["avg"] += ret
                    has_any = True
        if has_any:
            self_per_stock.append(row)
    self_summary = {}
    for lbl, a in self_agg.items():
        if a["count"] > 0:
            self_summary[lbl] = {"count": a["count"], "win_rate": r2(a["win"] / a["count"] * 100),
                                 "avg_return": r2(a["avg"] / a["count"])}
        else:
            self_summary[lbl] = {"count": 0, "win_rate": None, "avg_return": None}
    self_backtest = {
        "note": "本策略(严格三重共识交集)自上线起逐日累积价格样本；样本≥2个交易日方可计算。当前为前向累积，与上方信号层回测互补。" if all_dates else "样本积累中",
        "track_start": meta.get("track_start", today),
        "history_days": len(all_dates),
        "summary": self_summary,
        "per_stock": self_per_stock,
    }

    # ---------- 7) 板块聚类 ----------
    industry_count = {}
    sector_count = {}
    for t in tracked:
        ind = t.get("industry") or "未知"
        industry_count[ind] = industry_count.get(ind, 0) + 1
        for s in (t.get("sectors") or []):
            sector_count[s] = sector_count.get(s, 0) + 1
    sector_cluster = {
        "by_industry": sorted([{"industry": k, "count": v,
                                "names": [t["name"] for t in tracked if (t.get("industry") or "未知") == k]}
                               for k, v in industry_count.items()], key=lambda x: -x["count"]),
        "by_sector": sorted([{"sector": k, "count": v} for k, v in sector_count.items()], key=lambda x: -x["count"]),
        "concentration": 0,
    }
    if tracked:
        top_ind = sector_cluster["by_industry"][0]["count"]
        sector_cluster["concentration"] = r2(top_ind / len(tracked) * 100)

    # ---------- 8) 全站精选重叠度 ----------
    today_codes = set(ncode(t["code"]) for t in tracked)
    top10_ge70 = set()
    for s in top10.get("top10", []):
        if (s.get("total_score") or 0) >= 70:
            top10_ge70.add(ncode(s.get("code")))
    # 2026-09-06 审计修复：cockpit_a/cockpit_b 重叠度输出移除（驾驶舱下线，tier 恒空属伪数据；
    # 前端 ttOverlap 仅消费 top10_ge70，此改动零前端影响）
    overlap = {
        "total_tracked": len(today_codes),
        "top10_ge70": {"count": len(top10_ge70), "overlap": len(today_codes & top10_ge70),
                       "names": [t["name"] for t in tracked if ncode(t["code"]) in (top10_ge70 & today_codes)]},
    }

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": today,
        "track_start": meta.get("track_start", today),
        "history_days": len(all_dates),
        "strict_count": sum(1 for t in tracked if t["status"] == "strict"),
        "near_count": sum(1 for t in tracked if t["status"] == "near"),
        "tracked": tracked,
        "alerts": alerts,
        "sector_cluster": sector_cluster,
        "overlap": overlap,
        "backtest_signal": backtest_signal,
        "threshold_sensitivity": threshold_sensitivity,
        "strict_vs_loose": strict_vs_loose,
        "self_backtest": self_backtest,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 跟踪池 {len(tracked)} 只（严格 {result['strict_count']} / 差一步 {result['near_count']}）")
    print(f"  📊 告警 {len(alerts)} 条; 板块 {len(sector_cluster['by_industry'])} 类; 重叠 TOP10≥70 {overlap['top10_ge70']['overlap']} 只")
    print(f"  🎯 信号层回测样本 {backtest_signal['total']}（最新 {backtest_signal['latest_date']}）")
    print(f"  🔁 前向回测: {self_backtest['history_days']} 交易日 | {self_backtest['note'][:30]}")
    print(f"  输出: {OUT}")


if __name__ == "__main__":
    main()
