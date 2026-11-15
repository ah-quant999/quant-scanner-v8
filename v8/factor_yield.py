# -*- coding: utf-8 -*-
"""
因子实验室 · 按收益率排选（真实回测，2026-11-15 主人令「因子也要按收益率来排选」）

目的：把因子实验室的候选股（异常换手率重点池 + ROE 全市场主板大市值档），
用【本地真实日K】(raw_data/kline_cache) 回测各持有期真实收益率 + 胜率，
按 T+20 平均收益降序排选 —— 与「回测跟踪页·最终推荐真实收益率回测」同引擎同口径：
  入场 = 信号日次一交易日开盘价；
  出场 = t+N 交易日收盘价；
  双边成本 0.30%（与 FINAL_RECOMMEND_BACKTEST / 强势跟踪卡一致）。

与 FINAL_RECOMMEND_BACKTEST 的区别：本模块 = 因子候选池的收益率排选；
FINAL_RECOMMEND_BACKTEST = 终选真实信号流（算法链每日真实选股快照）。
两者口径一致、互为印证。

数据源：raw_data/kline_cache/{6位代码}.json（全站统一真实日K缓存，已入仓，云端零网络可取）。
次新股 K 线不足 NEED_MIN 根 → 标 available=False、不参排（绝不静默 0 冒充样本）。

输出（compute）：
  { "update_time":..., "meta":{...}, "ranked":[ {code,name,available,
      yield_t5/10/20/30/60, win_t5/10/20/30/60, n_t5/10/20/30/60, n_klines}, ... ] }
  ranked 已按 T+20 平均收益降序（available 优先；数据不足沉底）。
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
KL_DIR = os.path.join(RAW, "kline_cache")
COST = 0.0030          # 双边 0.30%
HORIZONS = [5, 10, 20, 30, 60]
MAX_H = max(HORIZONS)
NEED_MIN = MAX_H + 30  # 至少要有足够 K 线算 T+60（留余量）
SIGNAL_WINDOW = 250    # 仅用最近 250 个交易日作为信号点（反映近期 regime）


def _norm_code(code):
    c = re.sub(r"\D", "", str(code or ""))
    return c[-6:] if len(c) >= 6 else c


def _load_klines(code):
    p = os.path.join(KL_DIR, "%s.json" % _norm_code(code))
    if not os.path.exists(p):
        return None
    try:
        rows = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            d = str(r.get("date") or r.get("day") or "")[:10]
            o = float(r["open"])
            c = float(r["close"])
        except Exception:
            continue
        if not d or c <= 0 or o <= 0:
            continue
        out.append({"date": d, "open": o, "close": c})
    out.sort(key=lambda x: x["date"])
    return out if len(out) >= 60 else None


def _net_ret(rows, t, h):
    """t 为信号日(0-based)；次一交易日开盘入、t+1+h 收盘出；扣双边成本。None=数据不足。"""
    if t + 1 + h >= len(rows):
        return None
    entry = rows[t + 1]["open"]
    exit_ = rows[t + 1 + h]["close"]
    if entry <= 0 or exit_ <= 0:
        return None
    return exit_ / entry - 1 - COST


def compute(codes, top_n=40, window=SIGNAL_WINDOW):
    """codes: list of {code, name}。返回 {update_time, meta, ranked}。"""
    from datetime import datetime
    ranked = []
    for item in codes:
        code = item.get("code")
        name = item.get("name", "") or ""
        ncode = _norm_code(code)
        rows = _load_klines(code)
        rec = {"code": code, "name": name, "n_klines": len(rows) if rows else 0}
        if not rows or len(rows) < NEED_MIN:
            rec["available"] = False
            for h in HORIZONS:
                rec["yield_t%d" % h] = None
                rec["win_t%d" % h] = None
                rec["n_t%d" % h] = 0
            ranked.append(rec)
            continue
        per = {h: [] for h in HORIZONS}
        start = max(0, len(rows) - window)
        for t in range(start, len(rows) - 1 - MAX_H):
            for h in HORIZONS:
                r = _net_ret(rows, t, h)
                if r is not None:
                    per[h].append(r)
        rec["available"] = True
        for h in HORIZONS:
            rets = per[h]
            if rets:
                rec["yield_t%d" % h] = round(sum(rets) / len(rets) * 100, 3)
                rec["win_t%d" % h] = round(sum(1 for x in rets if x > 0) / len(rets) * 100, 1)
                rec["n_t%d" % h] = len(rets)
            else:
                rec["yield_t%d" % h] = None
                rec["win_t%d" % h] = None
                rec["n_t%d" % h] = 0
        ranked.append(rec)
    # 按 T+20 平均收益降序；数据不足(None)沉底
    ranked.sort(key=lambda x: (x.get("yield_t20") if x.get("yield_t20") is not None else -1e9), reverse=True)
    meta = {
        "cost_pct_roundtrip": COST * 100,
        "entry": "信号日次一交易日开盘",
        "exit": "t+N 交易日收盘",
        "signal_window": window,
        "need_min_klines": NEED_MIN,
        "universe": "因子实验室候选股（异常换手率重点池 + ROE 全市场主板大市值档）",
        "source": "raw_data/kline_cache（本地真实日K）",
        "caliber_note": "与 FINAL_RECOMMEND_BACKTEST / 强势跟踪卡同引擎同口径；本榜=因子候选池，那卡=终选真实信号流",
    }
    return {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "meta": meta,
        "ranked": ranked[:top_n],
    }


if __name__ == "__main__":
    import sys
    # 简易自测：传入若干代码，打印收益率排选结果
    _codes = [{"code": c, "name": ""} for c in (sys.argv[1:] or ["sh.600519", "sz.000001", "sh.601318"])]
    _out = compute(_codes)
    print(json.dumps(_out, ensure_ascii=False, indent=2))
