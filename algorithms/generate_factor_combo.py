#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_factor_combo.py — 🆕 2026-10-21 新算法模块：科学因子精选组合
==========================================================================
把 factor_walkforward 引擎判 PASS 且 PSR 显著的因子，做组合层构造：
  · 截面 z-score → symmetric_orthogonalize 去共线 → 因子层 risk_parity_weights（按 OOS 波动倒数加权）
  · 合成 composite score → 全市场 Top-N → data/FACTOR_COMBO.js（window.FACTOR_COMBO）
  · 自带 combo OOS 回测（近 ~2 年）：Top-N 风险平价合成 vs 全池等权基准，
    用 backtest_lib 同口径建模涨停买不进/跌停顺延/停牌（治"假新鲜/可买≠可成交"）
依赖：factor_walkforward.py（读 raw_data/factor_walkforward.json 的 PASS 因子 + make_prep/build_panel）、backtest_lib.py
🚀 2026-10-21 主人令「新算法全要、带回测」：本模块 = ⑨组合层(正交+风险平价) + ⑩第四模块外全新策略 的合体交付。
"""
import json
import os
import sys
import math
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
RAW_DIR = os.path.join(BASE, "..", "raw_data")
KLINE_DIR = os.path.join(RAW_DIR, "kline_cache")
DATA_DIR = os.path.join(BASE, "..", "data")
FW_JSON = os.path.join(RAW_DIR, "factor_walkforward.json")
OUT_JSON = os.path.join(RAW_DIR, "factor_combo.json")
OUT_JS = os.path.join(DATA_DIR, "FACTOR_COMBO.js")

import backtest_lib
from factor_walkforward import (make_prep, FACTOR_DEFS, MIN_BARS, STEP,
                                build_panel, load_universe, _trade_ret)

COST = 0.003
TOP_N = 20
MIN_PRICE = 2.0
LIQ_AMT = 50_000_000.0
RECENT_DAYS = 500
COMBO_HOLD = 20


def log(m):
    print(m, flush=True)


def now_cst():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def load_names():
    p = os.path.join(RAW_DIR, "stock_names.json")
    names = {}
    try:
        d = json.load(open(p, encoding="utf-8"))
        rows = d.get("data") if isinstance(d, dict) else d
        if isinstance(rows, list):
            for it in rows:
                if isinstance(it, dict) and "code" in it and "name" in it:
                    names[str(it["code"])] = it["name"]
    except Exception as e:
        log("⚠️ stock_names.json 不可用（降级无名称）: %s" % str(e)[:80])
    return names


def load_klines():
    """全 A 日线缓存 → {code: bars}，仅留上市≥MIN_BARS（与引擎同口径）。"""
    out = {}
    for f in os.listdir(KLINE_DIR):
        code = f[:-5]
        if len(code) != 6 or code[0] not in "036":
            continue
        try:
            bars = json.load(open(os.path.join(KLINE_DIR, f), encoding="utf-8"))
        except Exception:
            continue
        if isinstance(bars, list) and len(bars) >= MIN_BARS:
            out[code] = bars
    return out


def read_pass_factors():
    """读 factor_walkforward.json，挑 verdict==PASS 且 PSR 显著的因子。"""
    if not os.path.exists(FW_JSON):
        return []
    d = json.load(open(FW_JSON, encoding="utf-8"))
    res = d.get("results", {})
    out = []
    for name, info in res.items():
        if info.get("verdict") != "PASS":
            continue
        psr = info.get("psr_oos")
        if psr is None or not info.get("significant"):
            continue
        # 因子层风险平价权重：按 OOS 年化波动倒数（vol_target_oos.ann_vol_raw_pct）
        vt = info.get("vol_target_oos") or {}
        av = vt.get("ann_vol_raw_pct")
        if av and av > 0:
            w = 1.0 / (av / 100.0)
        else:
            ir = info.get("ir_oos")
            w = (1.0 / abs(ir)) if (ir and ir != 0) else 1.0
        out.append({
            "name": name,
            "label": info.get("label", name),
            "hold": info.get("hold", 10),
            "psr_oos": psr,
            "ir_oos": info.get("ir_oos"),
            "weight": w,
        })
    # 归一化权重
    tot = sum(x["weight"] for x in out) or 1.0
    for x in out:
        x["weight"] /= tot
    return out


def elig_at(rows, i):
    """单票在全局日 i 的流动性/价格/停牌过滤（与 lowvol 同口径，零未来函数）。"""
    if i < 1 or i >= len(rows):
        return False
    c = rows[i].get("close") or 0.0
    if c < MIN_PRICE:
        return False
    if rows[i].get("volume") == 0:
        return False  # 停牌
    # 近 20 日均成交额 ≥ 5000 万
    lo = max(0, i - 19)
    amts = [rows[k].get("close", 0) * rows[k].get("volume", 0) for k in range(lo, i + 1)]
    if sum(amts) / max(1, (i - lo + 1)) < LIQ_AMT:
        return False
    return True


def _zscore(vals):
    n = len(vals)
    if n < 3:
        return [0.0] * n
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    sd = var ** 0.5
    if sd <= 0:
        return [0.0] * n
    return [(v - m) / sd for v in vals]


def build_composite(prep_map, pass_factors, codes, date_idx_map):
    """对给定股票集合，在各自 date 索引处算截面 z → 正交 → 风险平价合成。
    date_idx_map: {code: i}。返回 {code: composite} 与 z_by_factor。
    """
    fac_names = [f["name"] for f in pass_factors]
    eligible = []
    raw = {}
    for c in codes:
        i = date_idx_map.get(c)
        if i is None or i < 0:
            continue
        rows = prep_map[c]["_rows"]
        if not elig_at(rows, i):
            continue
        fdict = prep_map[c]["f"]
        vs = [fdict[nm](i) for nm in fac_names]
        if any(v is None for v in vs):
            continue
        eligible.append(c)
        raw[c] = vs
    if len(eligible) < max(3, len(fac_names)):
        return {}, {}
    # 截面 z：按因子列做（跨股票截面标准化，非逐股）
    z_by_col = []
    for fi in range(len(fac_names)):
        col = [raw[c][fi] for c in eligible]
        z_by_col.append(_zscore(col))
    zmat = [[z_by_col[fi][ci] for fi in range(len(fac_names))] for ci in range(len(eligible))]
    # 对称正交去共线
    try:
        ortho = backtest_lib.symmetric_orthogonalize(zmat)
    except Exception:
        ortho = zmat
    # 合成（因子层风险平价权重）
    w = [f["weight"] for f in pass_factors]
    comp = {}
    zbf = {}
    for ci, c in enumerate(eligible):
        s = 0.0
        zb = {}
        for fi, nm in enumerate(fac_names):
            s += w[fi] * ortho[ci][fi]
            zb[nm] = round(zmat[ci][fi], 3)
        comp[c] = s
        zbf[c] = zb
    return comp, zbf


def combo_current(klines, prep_map, pass_factors, names):
    """当前截面 composite → Top-N → 写 FACTOR_COMBO.js。"""
    codes = list(klines.keys())
    date_idx_map = {c: len(klines[c]) - 1 for c in codes}
    comp, zbf = build_composite(prep_map, pass_factors, codes, date_idx_map)
    if not comp:
        log("⚠️ 当前无足够合格票构造组合（PASS 因子可能不足）")
        return None
    ranked = sorted(comp.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    tot = sum(abs(v) for _, v in ranked) or 1.0
    top = []
    for c, v in ranked:
        top.append({
            "code": c,
            "name": names.get(c, c),
            "score": round(v, 4),
            "weight": round(v / tot, 4),
            "z": zbf.get(c, {}),
        })
    obj = {
        "update_time": now_cst(),
        "module": "generate_factor_combo.py",
        "method": "截面z → symmetric_orthogonalize去共线 → 因子层risk_parity(按OOS波动倒数) → Top-%d" % TOP_N,
        "top_n": TOP_N,
        "used_factors": [{"name": f["name"], "label": f["label"],
                          "weight": round(f["weight"], 4), "psr_oos": f["psr_oos"],
                          "ir_oos": f["ir_oos"]} for f in pass_factors],
        "top": top,
    }
    json.dump(obj, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(OUT_JS, "w", encoding="utf-8") as fp:
        fp.write("window.FACTOR_COMBO = ")
        json.dump(obj, fp, ensure_ascii=False)
        fp.write(";\n")
    log("✅ 当前组合已写：%d 只 PASS 因子 → Top-%d（%s）" % (len(pass_factors), TOP_N, OUT_JS))
    return obj


def combo_oos_backtest(klines, prep_map, pass_factors, names):
    """近 RECENT_DAYS 的 combo OOS 回测：每 STEP 调仓，Top-N 持有 COMBO_HOLD，对比全池等权基准。"""
    if not pass_factors:
        return None
    codes = list(klines.keys())
    dates, pos, bars = build_panel(klines)
    nd = len(dates)
    t0 = max(MIN_BARS + 1, nd - RECENT_DAYS)
    combo_rets, bench_rets = [], []
    n_rb = 0
    t = t0
    while t + 1 + COMBO_HOLD < nd:
        date_idx_map = {}
        for c in codes:
            p = pos.get(c)
            if p and t < len(p):
                date_idx_map[c] = p[t]
        comp, _ = build_composite(prep_map, pass_factors, codes, date_idx_map)
        # 基准 = 当期全部合格票等权
        bench_codes = [c for c in comp.keys()]
        if not bench_codes:
            t += STEP
            continue
        # 组合 Top-N
        topn = sorted(comp.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
        cr = [(_trade_ret(bars[c], pos[c][t], COMBO_HOLD, c) if pos[c][t] >= 0 else None)
              for c, _ in topn]
        cr = [x for x in cr if x is not None]
        br = [(_trade_ret(bars[c], pos[c][t], COMBO_HOLD, c) if pos[c][t] >= 0 else None)
              for c in bench_codes]
        br = [x for x in br if x is not None]
        if cr and br:
            combo_rets.append(sum(cr) / len(cr))
            bench_rets.append(sum(br) / len(br))
            n_rb += 1
        t += STEP
    if not combo_rets:
        return None

    def _ann(series):
        m = sum(series) / len(series)
        # STEP=20 交易日调仓 → 年调仓次数 ≈ 250/20
        ann_ret = ((1.0 + m) ** (250.0 / STEP) - 1.0) if m > -1 else -1.0
        var = sum((x - m) ** 2 for x in series) / max(1, len(series) - 1)
        sd = var ** 0.5
        ann_vol = sd * (250.0 / STEP) ** 0.5
        sharpe = (ann_ret / ann_vol) if ann_vol > 0 else 0.0
        return m, ann_ret, ann_vol, sharpe

    cm, ca, cv, cs = _ann(combo_rets)
    bm, ba, bv, bs = _ann(bench_rets)
    alpha = ca - ba
    summary = {
        "n_rebalance": n_rb,
        "window_days": nd - t0,
        "combo": {"mean_per_rb": round(cm, 5), "ann_ret": round(ca, 4),
                  "ann_vol": round(cv, 4), "sharpe": round(cs, 3)},
        "bench_equal_weight": {"mean_per_rb": round(bm, 5), "ann_ret": round(ba, 4),
                               "ann_vol": round(bv, 4), "sharpe": round(bs, 3)},
        "alpha_ann": round(alpha, 4),
    }
    log("📊 combo OOS 回测：n=%d  组合年化 %.2f%%(Sharpe %.2f) vs 基准 %.2f%%  ⇒ α %.2f%%"
        % (n_rb, ca * 100, cs, ba * 100, alpha * 100))
    return summary


def main():
    log("=" * 70)
    log("  科学因子精选组合（FACTOR_COMBO）  —  %s" % now_cst())
    log("=" * 70)
    pass_factors = read_pass_factors()
    if not pass_factors:
        log("⚠️ factor_walkforward.json 无 PASS 且 PSR 显著因子 → 组合空，跳过（先跑引擎回测）")
        return
    log("入选 PASS+显著因子 %d 个：%s" % (len(pass_factors),
        ", ".join("%s(w=%.2f)" % (f["name"], f["weight"]) for f in pass_factors)))
    klines = load_klines()
    log("universe: %d 只（kline_cache）" % len(klines))
    names = load_names()
    # 预计算因子序列（O(1) 求值）
    prep_map = {}
    for c, rows in klines.items():
        d = make_prep(rows)
        d["_rows"] = rows
        prep_map[c] = d
    log("  因子预计算完成 %d 只" % len(prep_map))

    cur = combo_current(klines, prep_map, pass_factors, names)
    bt = combo_oos_backtest(klines, prep_map, pass_factors, names)
    if cur is not None and bt is not None:
        cur["backtest"] = bt
        json.dump(cur, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with open(OUT_JS, "w", encoding="utf-8") as fp:
            fp.write("window.FACTOR_COMBO = ")
            json.dump(cur, fp, ensure_ascii=False)
            fp.write(";\n")
        log("✅ FACTOR_COMBO.js 已含当前组合 + OOS 回测摘要")


if __name__ == "__main__":
    main()
