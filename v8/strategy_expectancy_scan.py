#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策略真实期望排行榜（2026-10-24 主人令「不要纠结FF3、一个月太久，怎么做到能信任」）

用与生产同源引擎（factor_walkforward：同 _wf_cache 宇宙/同因子口径/同 _trade_ret 执行约束+成本）
在本地多年历史上一次性算出每个因子的单因子策略 + 复合策略的**真实净期望**，回答
「到底哪些策略在扣费后真的赚钱、哪些只是看着热闹」。

【评估对象】
  单因子 Top5（turntrend/amt60/ivol60/skew60）各独立
  FF3 复合（3 因子，现役 S0 等权秩和）
  因子榜复合（4 因子：amt60+turntrend+ivol60+skew60，等权秩和）
  —— 全部 T+20 持有（现役主档），次开买入/一字板剔除/跌停顺延/双边 0.3%

【指标】每笔平均净收益 / 超额（vs 全截面基准）/ 超额胜率 / n 面板（2019→2026 本地宇宙）
【口径限制（如实声明）】宇宙=本地 _wf_cache 565 只子集；绝对水平与全宇宙有差，
  但策略间相对比较有效；所有数字扣费后，赢家即「可信任核心」。
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))
import factor_walkforward as fw

RAW = os.path.join(ROOT, "raw_data")
CACHE = os.path.join(RAW, "_wf_cache")
OUT = os.path.join(RAW, "strategy_expectancy_scan_report.json")
TOP_N = 5
HOLD = 20
STEP = fw.STEP
FACTORS = ("turntrend", "amt60", "ivol60", "skew60")

_t0 = time.time()
log = lambda m: print("[%7.1fs] %s" % (time.time() - _t0, m), flush=True)


def load_names():
    p = os.path.join(RAW, "stock_names.json")
    names = {}
    try:
        for s in (json.load(open(p)).get("data") or []):
            fc = s.get("full_code") or ""
            if fc.startswith(("sh", "sz")):
                c6 = fc[2:]
                if c6.isdigit():
                    names[c6] = s.get("name") or ""
    except Exception:
        pass
    return {c: n for c, n in names.items() if "ST" not in n.upper() and "退" not in n}


def rank_norm(vals):
    n = len(vals)
    if n < 2:
        return {c: 0.5 for c in vals}
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    return {c: 1.0 - pos / (n - 1) for pos, (c, _) in enumerate(order)}


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main():
    log("策略真实期望排行榜 · 多年本地历史 · T+%d 持有" % HOLD)
    codes = [f[:-5] for f in os.listdir(CACHE)
             if f.endswith(".json") and f[:-5].isdigit() and len(f[:-5]) == 6]
    names = load_names()
    codes = [c for c in codes if c in names] or codes
    klines = fw.get_klines(codes, 4, False)
    dates, pos, bars = fw.build_panel(klines)
    n = len(dates)
    pool_sum = [0.0] * n
    pool_cnt = [0] * n
    for c, rows in klines.items():
        r, _ = fw.stock_series(rows)
        p = pos[c]
        for g, i in enumerate(p):
            if i > 0:
                pool_sum[g] += r[i]; pool_cnt[g] += 1
    pool_r = [(pool_sum[g] / pool_cnt[g]) if pool_cnt[g] else 0.0 for g in range(n)]

    ts = []
    t = fw.MIN_BARS
    while t + 1 + HOLD < n:
        ts.append(t); t += STEP
    log("宇宙 %d 只 / 面板 %d 个 / %s→%s" % (len(klines), len(ts), dates[ts[0]], dates[ts[-1]]))

    fv = {k: {} for k in FACTORS}
    rets = {}
    for c, rows in klines.items():
        if len(rows) < fw.MIN_BARS:
            continue
        d = fw.make_prep(rows)
        pool_at = [None] * len(rows)
        p = pos[c]
        for g, ii in enumerate(p):
            if ii >= 0:
                pool_at[ii] = pool_r[g]
        d["f"].update(fw.make_resid_prep(rows, pool_at))
        for t in ts:
            i = p[t]
            if i < fw.MIN_BARS or i < 0:
                continue
            vs = {k: (d["f"][k](i) if d["f"].get(k) else None) for k in FACTORS}
            if any(v is None for v in vs.values()):
                continue
            fv["turntrend"][t] = fv["turntrend"].get(t, {})
            for k in FACTORS:
                fv[k].setdefault(t, {})[c] = vs[k]
            rt = {HOLD: fw._trade_ret(bars[c], i, HOLD, c)}
            rets.setdefault(t, {})[c] = rt
    panels = [t for t in ts if len(fv["turntrend"].get(t, {})) >= 15]
    log("有效面板 %d" % len(panels))

    def top5(comp):
        return sorted(comp, key=lambda c: -comp[c])[:TOP_N]

    rows_out = []
    # 单因子
    for k in FACTORS:
        rts, exc, base_n, wins = [], [], 0, 0
        for t in panels:
            cs = [c for c in fv[k][t] if fv["turntrend"][t].get(c) is not None
                  and rets[t].get(c, {}).get(HOLD) is not None]
            if len(cs) < 15:
                continue
            ranks = rank_norm({c: fv[k][t][c] for c in cs})
            top = top5(ranks)
            rr = [rets[t][c][HOLD] for c in top]
            rts.append(avg(rr))
            b = avg([rets[t][c][HOLD] for c in cs])
            if b is not None:
                exc.append(avg(rr) - b); base_n += 1
                if avg(rr) - b > 0:
                    wins += 1
        rows_out.append({"key": "单因子 %s" % k, "n": len(rts),
                          "avg": avg(rts), "excess": avg(exc),
                          "excess_wr": (wins / base_n * 100 if base_n else None)})
    # FF3 复合（3 因子）
    rts, exc, wins, bn = [], [], 0, 0
    for t in panels:
        cs = [c for c in fv["turntrend"][t]
              if all(fv[k].get(t, {}).get(c) is not None for k in FACTORS[:3])
              and rets[t].get(c, {}).get(HOLD) is not None]
        if len(cs) < 15:
            continue
        comp = {c: sum(rank_norm({c: fv[k][t][c] for c in cs})[c] for k in FACTORS[:3]) for c in cs}
        top = top5(comp)
        rr = [rets[t][c][HOLD] for c in top]
        b = avg([rets[t][c][HOLD] for c in cs])
        rts.append(avg(rr))
        if b is not None:
            exc.append(avg(rr) - b); bn += 1
            if avg(rr) - b > 0:
                wins += 1
    rows_out.append({"key": "FF3 复合(3因子)", "n": len(rts), "avg": avg(rts),
                     "excess": avg(exc), "excess_wr": (wins / bn * 100 if bn else None)})
    # 因子榜复合（4 因子）
    rts, exc, wins, bn = [], [], 0, 0
    for t in panels:
        cs = [c for c in fv["turntrend"][t]
              if all(fv[k].get(t, {}).get(c) is not None for k in FACTORS)
              and rets[t].get(c, {}).get(HOLD) is not None]
        if len(cs) < 15:
            continue
        comp = {c: sum(rank_norm({c: fv[k][t][c] for c in cs})[c] for k in FACTORS) for c in cs}
        top = top5(comp)
        rr = [rets[t][c][HOLD] for c in top]
        b = avg([rets[t][c][HOLD] for c in cs])
        rts.append(avg(rr))
        if b is not None:
            exc.append(avg(rr) - b); bn += 1
            if avg(rr) - b > 0:
                wins += 1
    rows_out.append({"key": "因子榜复合(4因子)", "n": len(rts), "avg": avg(rts),
                     "excess": avg(exc), "excess_wr": (wins / bn * 100 if bn else None)})

    log("")
    log("%-20s %6s %12s %12s %10s" % ("策略(T+%d)" % HOLD, "n面板", "均净收益", "超额/笔", "超额胜率"))
    for r in sorted(rows_out, key=lambda x: -(x["excess"] or -9)):
        log("%-20s %6d %12s %12s %10s" %
            (r["key"], r["n"],
             ("%+.2f%%" % (r["avg"] * 100)) if r["avg"] is not None else "--",
             ("%+.2f%%" % (r["excess"] * 100)) if r["excess"] is not None else "--",
             ("%.1f%%" % r["excess_wr"]) if r["excess_wr"] is not None else "--"))
    json.dump({"update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
               "purpose": "策略真实期望排行榜（回答「如何做到可信任」）",
               "universe": len(klines), "n_panels": len(panels), "hold": HOLD,
               "caliber": "生产同源引擎/执行约束/成本，全截面基准剔除前视",
               "rows": rows_out}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    log("[ok] %s" % OUT)


if __name__ == "__main__":
    main()
