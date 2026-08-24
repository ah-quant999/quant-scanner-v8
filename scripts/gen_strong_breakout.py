#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强势突破 · 升级算法生成器（H 反推升级版，彻底脱离 PDF OCR）
============================================================

🎯 设计目标（主人 2026-08-22 令）：
   原 STOCK_MOMENTUM_STATE / V2 由每日 PDF → OCR 录入外部大V共识，断供即 stale。
   改用「从 PDF 提取的 H 反推算法」升级版，每日盘后自己算「强势突破」候选并回测：

   ① H 反推基础（PDF 8.10/8.17 短线买点反推，auto_run_dn_algorithm.py 同源）：
        涨幅 ≥ 3%   （基于样本中位数 3.03）
        量比 ≥ 1.2  （当日量 / 4日均量，中位数 1.19）
   ② 升级项（突破 + 相对强度）：
        突破：当日收盘 ≥ 20 日最高价的 98%（平台/前高突破，量比已确认放量）
        相对强度 RS：在「涨幅≥3% 活跃股」队列中，20 日收益排名前 25%（强势股优先）
   ③ 对每只入选股，用入选日（当日）前复权日K线算 T+1~T+10 真实历史回测 +
      入选前特征（连涨天数 / 行业板块阶段 / 走势分类），写入 V2。
   ④ 维护 45 天滚动窗口（历史快照落 raw_data/strong_breakout_history.json），
      写 data/STOCK_MOMENTUM_STATE_V2.js（被 momentum_common_filter.py 消费 → MOMENTUM_FILTER）
      写 data/STOCK_MOMENTUM_STATE.js（共识视图，schema 兼容前端，零改动）。

🛡 门控：必须 ≥18:00 CST（盘后数据就绪）才跑；非交易日 / 行情非当日不追加新条目，
   但仍重建 V2/STATE（保持卡片新鲜）。K线取数全程 try 隔离，失败仅标记 data_available=false。

用法：
   python scripts/gen_strong_breakout.py [--limit N]   # N=仅对前 N 只重算K线(本地调试)
"""
import json
import os
import re
import sys
import argparse
import datetime
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent)  # scripts/ 上一级 = 项目根
DATA_DIR = Path(ROOT) / "data"
RAW_DIR = Path(ROOT) / "raw_data"
CACHE_DIR = RAW_DIR / "kline_cache"
HISTORY_FILE = RAW_DIR / "strong_breakout_history.json"
WINDOW_DAYS = 45

# ── H 反推阈值（与 auto_run_dn_algorithm.py 同源，PDF 8.10/8.17 样本）──
CHG_MIN = 3.0      # 涨幅下限
VR_MIN = 1.2       # 量比下限（当日量 / 4日均量）
VR_WINDOW = 4      # 量比窗口
BREAKOUT_RATIO = 0.98   # 收盘 ≥ 20日最高 * 该比例 = 突破
RS_WINDOW = 20     # 相对强度回看窗口（日）
RS_TOP_PCT = 0.25  # 相对强度前 25%

# ── 时间门控（与 momentum_common_filter 一致）────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "algorithms"))
from utils.time_gate import check_stock_picking_ready, _now_cst  # noqa: E402


def log(*a):
    print("[gen_strong_breakout]", *a, file=sys.stderr)


# ── 通用 js 读取 ───────────────────────────────────────
def load_js_var(path, var_name):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s\s*=\s*(\{.*\});\s*$" % var_name, src, re.S)
    if not m:
        raise ValueError(f"找不到 window.{var_name} in {path}")
    return json.loads(m.group(1))


def num_code(code):
    return re.sub(r"\D", "", str(code or ""))


def market_of(code):
    n = num_code(code)
    if len(n) != 6:
        return None
    if n[0] == "6":
        return "sh"
    if n[0] in ("0", "3"):
        return "sz"
    if n[0] in ("8", "4"):
        return "bj"
    return "sh"


# ── STOCK_QUOTE 行情查表 ───────────────────────────────
def load_quote():
    by = {}
    p = DATA_DIR / "STOCK_QUOTE.js"
    if not p.exists():
        return by, ""
    try:
        d = load_js_var(str(p), "STOCK_QUOTE")
        meta = d.get("meta", {}) or {}
        qdate = (meta.get("date") or meta.get("update_time") or "")[:10]
        for k, v in (d.get("stocks") or {}).items():
            by[num_code(k)] = {
                "name": v.get("name", ""),
                "price": v.get("price"),
                "pct": v.get("pct"),
                "prev_close": v.get("prev_close"),
                "volume": v.get("volume"),
            }
        return by, qdate
    except Exception as e:
        log("STOCK_QUOTE 读取失败:", e)
        return {}, ""


# ── K线缓存 ────────────────────────────────────────────
def get_kline(code):
    """返回 腾讯前复权日K DataFrame(date/open/close/high/low/volume/pct_chg)，带本地缓存。"""
    n = num_code(code)
    if len(n) != 6:
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = CACHE_DIR / f"{n}.json"
    try:
        if cp.exists():
            raw = json.loads(cp.read_text(encoding="utf-8"))
            if raw:
                import pandas as pd
                df = pd.DataFrame(raw)
                if len(df) >= 60:
                    return df
        from data_source_gtimg import fetch_a_daily_gtimg
        mkt = market_of(code)
        df = fetch_a_daily_gtimg(n, market=mkt, bars=250)
        if df is None or len(df) < 60:
            alt = "sz" if mkt == "sh" else "sh"
            df = fetch_a_daily_gtimg(n, market=alt, bars=250)
        if df is None:
            return None
        cp.write_text(json.dumps(df.to_dict(orient="records"), ensure_ascii=False), encoding="utf-8")
        return df
    except Exception as e:
        log(f"  K线获取失败 {code}: {e}")
        return None


def _idx_on_or_before(df, date_str):
    mask = df["date"] <= date_str
    if not mask.any():
        return -1
    return int(mask[mask].index[-1])


def compute_metrics(code, sel_date, kline):
    """对入选股计算 T+1~T+10 动量指标 + 入选前特征。返回 dict 或 None。"""
    if kline is None or len(kline) < 60:
        return None
    try:
        df = kline.copy()
        df = df.reset_index(drop=True)
        i = _idx_on_or_before(df, sel_date)
        if i < 1:
            return None
        sel_close = float(df.loc[i, "close"])
        sel_pct = float(df.loc[i, "pct_chg"]) if "pct_chg" in df else 0.0
        prev = df.iloc[:i]
        ret20 = 0.0
        if i >= 20:
            ret20 = float(df.loc[i - 1, "close"]) / float(df.loc[i - 20, "close"]) - 1
        consec_before = 0
        for j in range(i - 1, -1, -1):
            p = float(df.loc[j, "pct_chg"]) if "pct_chg" in df else 0.0
            if p > 0:
                consec_before += 1
            else:
                break
        daily_returns = []
        gains = []
        max_gain = None
        min_close_ratio = 1.0
        for t in range(1, 11):
            j = i + t
            if j >= len(df):
                daily_returns.append({"T": f"T+{t}", "date": "", "gain": None})
                gains.append(None)
                continue
            c = float(df.loc[j, "close"])
            g = (c / sel_close - 1) * 100
            daily_returns.append({"T": f"T+{t}", "date": str(df.loc[j, "date"]), "gain": round(g, 2)})
            gains.append(g)
            if max_gain is None or g > max_gain:
                max_gain = g
            ratio = c / sel_close
            if ratio < min_close_ratio:
                min_close_ratio = ratio
        valid = [g for g in gains if g is not None]
        _get = lambda idx: (valid[idx] if len(valid) > idx else (valid[-1] if valid else None))
        t1 = _get(0)
        t3 = _get(2)
        t5 = _get(4)
        t10 = _get(9)
        last = valid[-1] if valid else None
        max_gain_pct = round(max_gain, 2) if max_gain is not None else 0.0
        max_drawdown_pct = round((1 - min_close_ratio) * 100, 2)
        t1_gain_pct = round(t1, 2) if t1 is not None else 0.0
        t3_gain_pct = round(t3, 2) if t3 is not None else 0.0
        t5_gain_pct = round(t5, 2) if t5 is not None else 0.0
        t10_gain_pct = round(t10, 2) if t10 is not None else 0.0
        last_gain_pct = round(last, 2) if last is not None else 0.0
        consecutive_up_days = 0
        for j in range(i + 1, len(df)):
            p = float(df.loc[j, "pct_chg"]) if "pct_chg" in df else 0.0
            if p > 0:
                consecutive_up_days += 1
            else:
                break
        if ret20 >= 0.25:
            stage = "主升"
        elif ret20 >= 0.10:
            stage = "启动"
        elif ret20 <= -0.05:
            stage = "退潮"
        else:
            stage = "震荡"
        if consecutive_up_days >= 5 and max_drawdown_pct <= 5:
            pattern = "连续涨不回撤"
        elif max_gain_pct >= 40:
            pattern = "强势股"
        elif max_drawdown_pct >= 15:
            pattern = "波动大"
        else:
            pattern = "普通"
        return {
            "sel_change_pct": round(float(sel_pct), 2),
            "consec_before": consec_before,
            "stage": stage,
            "consecutive_up_days": consecutive_up_days,
            "max_gain_pct": max_gain_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "t1_gain_pct": t1_gain_pct,
            "t3_gain_pct": t3_gain_pct,
            "t5_gain_pct": t5_gain_pct,
            "t10_gain_pct": t10_gain_pct,
            "last_gain_pct": last_gain_pct,
            "pattern": pattern,
            "entry_price": round(sel_close, 2),
            "daily_returns": daily_returns,
            "data_available": True,
        }
    except Exception as e:
        log(f"  metrics 计算失败 {code}: {e}")
        return None


def classify_style(ret20, sel_pct, breakout):
    """按大V栏目语义做风格分类（升级版含「突破」）。返回去重保序 label 列表。"""
    labels = []
    if ret20 <= -0.12 and sel_pct > 0:
        labels.append("超跌反弹")
    elif -0.12 < ret20 <= 0 and sel_pct > 0:
        labels.append("反弹")
    if breakout:
        labels.append("突破")
    if ret20 >= 0.25:
        labels.append("加速")
    elif ret20 >= 0.12:
        labels.append("强势股")
    if not labels:
        labels.append("短线选股")
    # 短线选股作为底层兜底桶（所有入选股都算短线标的）
    labels.append("短线选股")
    seen = set()
    out = []
    for l in labels:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def select_breakouts(quote, limit=0):
    """H 反推升级版：涨幅≥3% + 量比≥1.2 + 突破前高 + RS 前25%。返回候选记录列表。"""
    # ① 预筛：当日涨幅 ≥ 3%（廉价，来自 STOCK_QUOTE）
    pre = [(c, v) for c, v in quote.items()
           if isinstance(v.get("pct"), (int, float)) and v["pct"] >= CHG_MIN]
    if limit:
        pre = pre[:limit]
    cands = []
    for c, v in pre:
        kline = get_kline(c)
        if kline is None or len(kline) < 60:
            continue
        closes = kline["close"].tolist()
        vols = kline["volume"].tolist()
        highs = kline["high"].tolist()
        today_vol = vols[-1]
        prev4 = vols[-(VR_WINDOW + 1):-1]   # 前 4 个交易日量
        avg4 = sum(prev4) / len(prev4) if prev4 else 0.0
        vr = (today_vol / avg4) if avg4 > 0 else None
        if vr is None or vr < VR_MIN:
            continue
        # ② 突破：收盘 ≥ 20日最高 * 比例
        hi20 = max(highs[-RS_WINDOW:])
        breakout = closes[-1] >= BREAKOUT_RATIO * hi20
        if not breakout:
            continue
        ret20 = (closes[-1] / closes[-(RS_WINDOW + 1)] - 1) if len(closes) >= (RS_WINDOW + 1) else 0.0
        cands.append({
            "code": c, "name": v.get("name", ""), "pct": v.get("pct"),
            "price": v.get("price"), "vol_ratio": round(vr, 3),
            "ret20": ret20, "breakout": True,
        })
    # ③ 相对强度 RS：20 日收益在活跃股队列前 25%
    if len(cands) > 4:
        cands.sort(key=lambda x: x["ret20"], reverse=True)
        keep = max(1, int(round(len(cands) * RS_TOP_PCT)))
        cands = cands[:keep]
    return cands


def build_record(c, v):
    """对单只候选做分类，返回写入历史的「入选记录」（不含指标；指标在输出时按入选日实时算）。"""
    cats = classify_style(v.get("ret20", 0.0), v.get("pct", 0.0), True)
    return {
        "code": c, "name": v.get("name", ""), "pct": v.get("pct"), "price": v.get("price"),
        "vol_ratio": v.get("vol_ratio"), "ret20": v.get("ret20", 0.0),
        "categories": cats,
    }


def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="仅重算前 N 只 K线(调试)")
    args = ap.parse_args()

    # 🛡 时间门控：盘后选股策略须 ≥18:00 CST
    check_stock_picking_ready(by="gen_strong_breakout")

    now = _now_cst()
    today = now.strftime("%Y-%m-%d")
    is_weekend = now.weekday() >= 5

    quote, qdate = load_quote()
    yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    # 🛡 2026-08-25 主人令：放宽「行情新鲜」判定。行情文件 update_time 常为盘后抓取壁钟，
    #   可能跨午夜（如 08-25 04:27 抓的是 08-24 收盘），若严格 qdate==today 会让 select_breakouts
    #   被静默跳过 → 强势突破页长期空。改为接受「今天或昨天(交易日)」的行情；周末本就不追加。
    quote_fresh = bool(qdate) and (qdate == today or qdate == yesterday)

    history = load_history()

    # ── 1) 追加今日强势突破候选 ─────────────────────────
    appended = False
    if not is_weekend and quote_fresh and quote:
        cands = select_breakouts(quote, limit=args.limit)
        recs = [build_record(cd["code"], cd) for cd in cands]
        # 同日期替换，否则追加
        history[today] = recs
        appended = True
        log(f"今日强势突破候选 {today}：初筛通过 {len(cands)} 只（涨幅≥3%+量比≥1.2+突破+RS前25%）")

    # ── 2) 45 天滚动窗口 ───────────────────────────────
    dates = sorted(history.keys())
    cutoff = (now - datetime.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    dates = [d for d in dates if d >= cutoff]
    history = {d: history[d] for d in dates}

    # ── 3) 汇总窗口内每只股（入选首日 / 次数 / 分类）────
    uni = {}  # code -> {first_date, count, cats:set, last_rec}
    for d in dates:
        for rec in history[d]:
            c = num_code(rec.get("code"))
            if not c:
                continue
            cats = set(rec.get("categories", []))
            e = uni.setdefault(c, {"first_date": d, "count": 0, "cats": set(), "last_rec": rec})
            if d < e["first_date"]:
                e["first_date"] = d
            e["count"] += 1
            e["cats"] |= cats
            e["last_rec"] = rec

    # ── 4) 输出时按入选日实时算指标（带缓存；K线增长即重算，自动填满 T+1~T+10）──
    METRICS_CACHE = RAW_DIR / "momentum_metrics.json"
    metrics_cache = {}
    if METRICS_CACHE.exists():
        try:
            metrics_cache = json.loads(METRICS_CACHE.read_text(encoding="utf-8"))
        except Exception:
            metrics_cache = {}
    metrics_map = {}
    for c, info in uni.items():
        fd = info["first_date"]
        kline = get_kline(c)
        klen = len(kline) if kline is not None else 0
        mc = metrics_cache.get(c)
        if mc and mc.get("first_date") == fd and mc.get("klen") == klen and "metrics" in mc:
            mtr = mc["metrics"]
        else:
            mtr = compute_metrics(c, fd, kline)
            if mtr is None:
                mtr = {"data_available": False, "sel_change_pct": 0.0, "consec_before": None,
                       "stage": "", "consecutive_up_days": 0, "max_gain_pct": 0.0, "max_drawdown_pct": 0.0,
                       "t1_gain_pct": 0.0, "t3_gain_pct": 0.0, "t5_gain_pct": 0.0, "t10_gain_pct": 0.0,
                       "last_gain_pct": 0.0, "pattern": "", "entry_price": None, "daily_returns": []}
            mtr["first_date"] = fd
            metrics_cache[c] = {"first_date": fd, "klen": klen, "metrics": mtr}
        metrics_map[c] = mtr
    METRICS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_CACHE.write_text(json.dumps(metrics_cache, ensure_ascii=False), encoding="utf-8")

    # ── 5) 组装 V2 periods（按入选首月分组）─────────────
    periods = {}
    kline_ok = 0
    total_uni = len(uni)
    for c, info in uni.items():
        rec = info["last_rec"]
        m = metrics_map.get(c, {})
        fd = info["first_date"]
        month = fd[:7] if fd else "unknown"
        pv = periods.setdefault(month, {"count": 0, "leaders": [], "all": []})
        pv["count"] += info["count"]
        name = rec.get("name", "") or ""
        pvrec = {
            "code": c,
            "symbol": (market_of(c) or "") + c,
            "name": name,
            "date": fd,
            "count": info["count"],
            "categories": sorted(info["cats"]),
            "change_pct": m.get("sel_change_pct", 0.0),
            "sel_change_pct": m.get("sel_change_pct", 0.0),
            "data_available": m.get("data_available", False),
            "consec_before": m.get("consec_before"),
            "stage": m.get("stage", ""),
            "consecutive_up_days": m.get("consecutive_up_days", 0),
            "max_gain_pct": m.get("max_gain_pct", 0.0),
            "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
            "t1_gain_pct": m.get("t1_gain_pct", 0.0),
            "t3_gain_pct": m.get("t3_gain_pct", 0.0),
            "t5_gain_pct": m.get("t5_gain_pct", 0.0),
            "t10_gain_pct": m.get("t10_gain_pct", 0.0),
            "last_gain_pct": m.get("last_gain_pct", 0.0),
            "pattern": m.get("pattern", ""),
            "note": f"连涨前{m.get('consec_before')}天 回撤{m.get('max_drawdown_pct',0)}%",
            "daily_returns": m.get("daily_returns", []),
            "entry_price": m.get("entry_price"),
        }
        if m.get("data_available"):
            kline_ok += 1
        pv["all"].append(pvrec)

    for pv in periods.values():
        avail = [r for r in pv["all"] if r["data_available"]]
        avail.sort(key=lambda r: r["t5_gain_pct"], reverse=True)
        pv["leaders"] = avail[:10]

    v2 = {
        "meta": {
            "generated": today + " " + now.strftime("%H:%M:%S"),
            "description": "个股动量状态增强分析 V2：基于「H反推升级算法」(涨幅≥3%+量比≥1.2+突破前高+RS前25%) 每日自选强势突破 + 真实日K线(前复权)计算 T+1~T+10 回测",
            "data_source": "腾讯ifzq K线(日,前复权) + STOCK_QUOTE(涨幅/量比)",
            "source": "h_reverse_upgraded_breakout(脱离PDF OCR)",
            "method": f"涨幅≥{CHG_MIN}% + 量比≥{VR_MIN}({VR_WINDOW}日均量) + 突破{BREAKOUT_RATIO*100:.0f}%20日高 + RS前{RS_TOP_PCT*100:.0f}%",
            "total_unique_stocks": total_uni,
            "total_appearances": sum(p["count"] for p in periods.values()),
            "kline_available": kline_ok,
            "kline_unavailable": total_uni - kline_ok,
        },
        "periods": periods,
    }

    # ── 5) 组装 STOCK_MOMENTUM_STATE.js（共识视图，兼容前端）──
    days = []
    for d in dates:
        cats = {}
        consensus_map = {}
        for rec in history[d]:
            c = num_code(rec.get("code"))
            if not c:
                continue
            for lab in rec.get("categories", []):
                cats.setdefault(lab, []).append({
                    "code": c, "name": rec.get("name", ""),
                    "change_pct": rec.get("pct", 0.0),
                    "price": rec.get("price"), "category": lab,
                })
            # 共识：入选≥2 次（跨日重复入选）视为共识
            cm = consensus_map.setdefault(c, {"code": c, "name": rec.get("name", ""), "count": 0, "categories": set()})
            cm["count"] += 1
            cm["categories"] |= set(rec.get("categories", []))
        consensus = []
        for c, cm in consensus_map.items():
            if cm["count"] >= 2:
                consensus.append({"code": c, "name": cm["name"], "count": cm["count"],
                                   "categories": sorted(cm["categories"])})
        days.append({"date": d, "categories": cats, "consensus": consensus})

    state = {
        "update_time": today + " " + now.strftime("%H:%M"),
        "generated": today + " " + now.strftime("%H:%M"),
        "meta": {
            "generated": today + " " + now.strftime("%H:%M"),
            "source": "h_reverse_upgraded_breakout(脱离PDF OCR)",
            "total_days": len(days),
            "days_with_consensus": sum(1 for d in days if d.get("consensus")),
            "total_consensus_stocks": sum(len(d.get("consensus", [])) for d in days),
        },
        "days": days,
    }

    # ── 6) 写出 ─────────────────────────────────────────
    v2_js = "window.STOCK_MOMENTUM_ENHANCED = " + json.dumps(v2, ensure_ascii=False, indent=1) + ";\n"
    (DATA_DIR / "STOCK_MOMENTUM_STATE_V2.js").write_text(v2_js, encoding="utf-8")
    # 共识视图：保持 IIFE 包装兼容前端 getAll()
    state_js = ("window.STOCK_MOMENTUM_STATE = (function() {\n"
                "  var data = " + json.dumps(state, ensure_ascii=False, indent=1) + ";\n"
                "  return {\n"
                "    getDays: function() { return data.days; },\n"
                "    getConsensus: function(date) {\n"
                "      for (var i=0;i<data.days.length;i++) { if(data.days[i].date===date) return data.days[i].consensus; }\n"
                "      return [];\n"
                "    },\n"
                "    getTopConsensus: function(n) { return []; },\n"
                "    getSummary: function() { return data.meta; },\n"
                "    getAll: function() { return data; }\n"
                "  };\n"
                "})();\n")
    (DATA_DIR / "STOCK_MOMENTUM_STATE.js").write_text(state_js, encoding="utf-8")

    # 落历史
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")

    log(f"✅ 写出 STOCK_MOMENTUM_STATE_V2.js（{total_uni} 只唯一，K线可用 {kline_ok}，月份 {len(periods)}）")
    log(f"✅ 写出 STOCK_MOMENTUM_STATE.js（窗口 {len(days)} 天，今日追加={appended}）")


if __name__ == "__main__":
    main()
