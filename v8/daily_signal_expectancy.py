#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日精选强势股信号 · 独立真实期望 + 与现有因子相关性
（2026-10-24 主人令「ima 算出的加入因子合适吗」+「ima 里有其他文件夹从6月每日跑，查一下」）

【目的】回答：把"每日专家/算法精选的强势股信号"当因子加进去，是否合适？
  分两块证据：
  A) 信号【独立】扣费后真实期望（生产同源引擎 factor_walkforward._trade_ret：
     次开买入/一字板剔除/跌停顺延/双边0.3%，与策略真实期望排行榜完全可比）→ 它自己赚不赚钱？
  B) 信号选股与现有因子(amt60/turntrend)【相关性】→ 加进去是重复(高相关)还是互补(正交)？
     ① 各入选票在「最近面板」amt60/turntrend 原始值分位(越低=该因子越强；
        若偏好已被 amt60/turntrend 看好的票→分位偏低→冗余；≈0.5→正交)
     ② 与因子榜 TopN 在共有日的 Jaccard 重叠

【信号源·多来源】
  · ima_v2      : raw_data/ima_strong_history_v2.json → stocks[].first_selected(首次入选日)+code
                  （阿狸咪「短线情绪选股」逐日笔记转录，09-18 起）
  · strong_break: raw_data/strong_breakout_history.json → {date: [{code,...}]}
                  （强势突破/动量突破 账本，08-31 起；虽 09-19 已全站删除，账本留作信号合成）

【诚实约束(必须声明)】
  · 无 6 月数据：磁盘上 ima 转录最早 09-18、强势突破账本最早 08-31；若 ima 真从 6 月每日发，
    那些数据从未落盘，须从 live 源回填才能测。本脚本用现有最长日更档案。
  · _wf_cache 仅至 2026-10-23，T+20 需前看到 ~11 月初 ⇒ 后期信号因缓存截断无 T+20，样本再缩
  ⇒ 任何"正"结果都【非稳健】，本脚本只给方向+如实样本量，绝不夸大可信任度
"""
import os
import sys
import json
import glob
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))
import factor_walkforward as fw

RAW = os.path.join(ROOT, "raw_data")
CACHE = os.path.join(RAW, "_wf_cache")
OUT = os.path.join(RAW, "daily_signal_expectancy_report.json")
TOP_N = 5
HOLDS = (5, 10, 20)
STEP = fw.STEP
FACTORS = ("turntrend", "amt60", "ivol60", "skew60")

_t0 = time.time()
log = lambda m: print("[%8.1fs] %s" % (time.time() - _t0, m), flush=True)


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


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def collect_ima_v2():
    im = json.load(open(os.path.join(RAW, "ima_strong_history_v2.json")))
    out = {}
    for s in (im.get("stocks") or []):
        fs = (s.get("first_selected") or "").replace("-", "")
        c = str(s.get("code") or "").zfill(6)
        if len(fs) == 8 and fs.isdigit() and c.isdigit():
            out.setdefault(fs, []).append(c)
    return out


def collect_strong_breakout():
    d = json.load(open(os.path.join(RAW, "strong_breakout_history.json")))
    out = {}
    for ds, lst in d.items():
        if not isinstance(lst, list) or not ds or ds[:4] != "2026":
            continue
        dd = ds.replace("-", "")
        if len(dd) != 8 or not dd.isdigit():
            continue
        for e in lst:
            c = str((e.get("code") if isinstance(e, dict) else e) or "").zfill(6)
            if c.isdigit():
                out.setdefault(dd, []).append(c)
    return out


def analyze(sig_by_date, label, dates, pos, bars, gidx, panels, fv, bench_by_date):
    def baridx(code, dstr):
        gi = gidx.get(dstr)
        if gi is None or code not in pos:
            return None
        i = pos[code][gi]
        return i if i > 0 else None

    def nearest_panel(dstr):
        best = None
        for t in panels:
            if dates[t].replace("-", "") <= dstr:
                best = t
            else:
                break
        return best

    exp = {h: {"rts": [], "exc": [], "exc_win": 0, "bench_n": 0} for h in HOLDS}
    pick_pct = {"amt60": [], "turntrend": []}
    skipped_cache = 0
    for d, cs in sig_by_date.items():
        tn = nearest_panel(d)
        for c in cs:
            ji = baridx(c, d)
            if ji is not None:
                for h in HOLDS:
                    rt = fw._trade_ret(bars[c], ji, h, c)
                    if rt is None:
                        if h == max(HOLDS):
                            skipped_cache += 1
                        continue
                    exp[h]["rts"].append(rt)
                    bm = bench_by_date.get(d, {}).get(h)
                    if bm is not None:
                        exp[h]["exc"].append(rt - bm)
                        exp[h]["bench_n"] += 1
                        if rt - bm > 0:
                            exp[h]["exc_win"] += 1
            if tn is not None:
                for k in ("amt60", "turntrend"):
                    vals = fv[k].get(tn)
                    if vals and c in vals:
                        v = vals[c]
                        pc = sum(1 for x in vals.values() if x <= v) / len(vals)
                        pick_pct[k].append(pc)

    exp_rows = []
    for h in HOLDS:
        rts = exp[h]["rts"]
        exc = exp[h]["exc"]
        a = avg(rts)
        e = avg(exc)
        wr = (sum(1 for x in rts if x > 0) / len(rts) * 100) if rts else None
        ewr = (exp[h]["exc_win"] / exp[h]["bench_n"] * 100) if exp[h]["bench_n"] else None
        exp_rows.append({"hold": h, "n": len(rts), "avg_net": (round(a * 100, 2) if a is not None else None),
                         "winrate": (round(wr, 1) if wr is not None else None), "n_excess": exp[h]["bench_n"],
                         "avg_excess": (round(e * 100, 2) if e is not None else None),
                         "excess_winrate": (round(ewr, 1) if ewr is not None else None)})

    corr = {
        "amt60_pick_avg_percentile": (round(avg(pick_pct["amt60"]) * 100, 1) if pick_pct["amt60"] else None),
        "amt60_n_picks": len(pick_pct["amt60"]),
        "turntrend_pick_avg_percentile": (round(avg(pick_pct["turntrend"]) * 100, 1) if pick_pct["turntrend"] else None),
        "turntrend_n_picks": len(pick_pct["turntrend"]),
        "interpretation": ("分位越低=该因子越强；若信号偏好已被 amt60/turntrend 看好的票→分位偏低→冗余；≈50%→正交互补"),
    }
    log("  [%s] 信号 %d 日 / %d 票；T+20 因缓存截断跳过 %d 笔"
        % (label, len(sig_by_date), sum(len(v) for v in sig_by_date.values()), skipped_cache))
    return {"label": label, "n_signal_dates": len(sig_by_date),
            "n_signals": sum(len(v) for v in sig_by_date.values()),
            "date_range": [min(sig_by_date), max(sig_by_date)],
            "expectancy": exp_rows, "correlation": corr,
            "skipped_T20_cache": skipped_cache}


def main():
    log("每日精选强势股信号 · 独立期望 + 相关性（多来源）")
    sources = {"ima_v2": collect_ima_v2(), "strong_break": collect_strong_breakout()}
    for k, v in sources.items():
        log("%s: %d 日 / %d 票 / %s→%s" % (k, len(v),
             sum(len(x) for x in v.values()),
             min(v) if v else "-", max(v) if v else "-"))

    # 宇宙 + 同源引擎面板
    codes = [f[:-5] for f in os.listdir(CACHE)
             if f.endswith(".json") and f[:-5].isdigit() and len(f[:-5]) == 6]
    names = load_names()
    codes = [c for c in codes if c in names] or codes
    klines = fw.get_klines(codes, 4, False)
    # ── 内存续接：_wf_cache 仅到 2026-09-18，用权威的 kline_cache(到10-23) 续最近一段，
    #    使近期信号(09-18→10-23)有前看数据可算。不动磁盘缓存文件，可逆。
    KC = os.path.join(RAW, "kline_cache")
    ext_n = 0
    for c, rows in klines.items():
        kcp = os.path.join(KC, c + ".json")
        if not os.path.exists(kcp) or not rows:
            continue
        try:
            kc = json.load(open(kcp, encoding="utf-8"))
        except Exception:
            continue
        last = rows[-1].get("date")
        if not last:
            continue
        have = {r.get("date") for r in rows}
        extra = [r for r in kc if r.get("date") and r["date"] > last and r["date"] not in have]
        if extra:
            rows.extend(extra)
            ext_n += 1
    log("内存续接 kline_cache：%d 只补到 2026-10-23" % ext_n)
    dates, pos, bars = fw.build_panel(klines)
    gidx = {d.replace("-", ""): i for i, d in enumerate(dates)}
    n = len(dates)
    log("宇宙 %d 只 / 面板轴 %d 天 / 缓存末日 %s" % (len(klines), n, dates[-1]))

    pool_sum = [0.0] * n
    pool_cnt = [0] * n
    for c, rows in klines.items():
        r, _ = fw.stock_series(rows)
        p = pos[c]
        for g, i in enumerate(p):
            if i > 0:
                pool_sum[g] += r[i]
                pool_cnt[g] += 1
    pool_r = [(pool_sum[g] / pool_cnt[g]) if pool_cnt[g] else 0.0 for g in range(n)]

    ts = []
    t = fw.MIN_BARS
    while t + 1 + max(HOLDS) < n:
        ts.append(t)
        t += STEP
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
            for k in FACTORS:
                fv[k].setdefault(t, {})[c] = vs[k]
            rt = {h: fw._trade_ret(bars[c], i, h, c) for h in HOLDS}
            rets.setdefault(t, {})[c] = rt
    panels = [t for t in ts if len(fv["turntrend"].get(t, {})) >= 15]
    log("有效面板 %d" % len(panels))

    # 逐信号日基准（跨截面全宇宙同日期 T+HOLD 均值），覆盖所有来源信号日
    all_dates = set()
    for v in sources.values():
        all_dates |= set(v.keys())
    bench_by_date = {}
    for d in all_dates:
        gi = gidx.get(d)
        if gi is None:
            continue
        bm = {h: [] for h in HOLDS}
        for c in klines:
            i = pos[c][gi]
            if i <= 0:
                continue
            for h in HOLDS:
                r = fw._trade_ret(bars[c], i, h, c)
                if r is not None:
                    bm[h].append(r)
        bench_by_date[d] = {h: avg(bm[h]) for h in HOLDS}

    results = []
    for label, sig in sources.items():
        if not sig:
            log("[%s] 空，跳过" % label)
            continue
        results.append(analyze(sig, label, dates, pos, bars, gidx, panels, fv, bench_by_date))

    # 与因子榜 TopN 在共有日的 Jaccard
    A = {}
    for f in glob.glob(os.path.join(RAW, "history", "top10_daily_*.json")):
        ds = os.path.basename(f)[12:20]
        if not ds.isdigit():
            continue
        try:
            d = json.load(open(f))
            lst = [str(x.get("code") or "").zfill(6) for x in (d.get("top10") or []) if x.get("code")]
            if lst:
                A[ds] = lst
        except Exception:
            continue
    overlap = {}
    for label, sig in sources.items():
        common = sorted(set(sig) & set(A))
        jac = []
        for d in common:
            s_set = set(sig[d])
            a_set = set(A[d][:TOP_N])
            inter = len(s_set & a_set)
            union = len(s_set | a_set)
            jac.append(inter / union if union else 0)
        overlap[label] = {"n_common": len(common), "avg_jaccard": (round(avg(jac) * 100, 1) if jac else None)}

    log("")
    for r in results:
        log("===== %s =====" % r["label"])
        log("%-8s %6s %12s %10s %8s %12s %10s" %
            ("持有", "n", "均净收益", "胜率", "n超额", "均超额", "超额胜率"))
        for x in r["expectancy"]:
            log("T+%-5d %6d %12s %9s%% %7d %12s %9s%%" %
                (x["hold"], x["n"],
                 ("%+.2f%%" % x["avg_net"]) if x["avg_net"] is not None else "--",
                 ("%.0f" % x["winrate"]) if x["winrate"] is not None else "--",
                 x["n_excess"],
                 ("%+.2f%%" % x["avg_excess"]) if x["avg_excess"] is not None else "--",
                 ("%.0f" % x["excess_winrate"]) if x["excess_winrate"] is not None else "--"))
        c = r["correlation"]
        log("  相关性 amt60 均值分位=%s(n=%d) · turntrend 均值分位=%s(n=%d)"
            % (c["amt60_pick_avg_percentile"], c["amt60_n_picks"],
               c["turntrend_pick_avg_percentile"], c["turntrend_n_picks"]))
        ov = overlap.get(r["label"])
        if ov:
            log("  与因子榜 Top%d 共有日 %d · 平均 Jaccard=%s" % (TOP_N, ov["n_common"], ov["avg_jaccard"]))

    out = {
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "每日精选强势股信号(ima_v2 / 强势突破账本)独立期望 + 与现有因子相关性",
        "caliber": "生产同源引擎 factor_walkforward._trade_ret：次开买入/一字板剔除/跌停顺延/双边0.3%",
        "cache_last_date": dates[-1],
        "sources": {r["label"]: {"n_signals": r["n_signals"], "n_signal_dates": r["n_signal_dates"],
                                  "date_range": r["date_range"], "skipped_T20_cache": r["skipped_T20_cache"]}
                    for r in results},
        "results": results,
        "overlap_with_factor_topN": overlap,
        "caveat": ("无 6 月数据(磁盘上 ima 转录最早 09-18、强势突破账本最早 08-31)；"
                   "_wf_cache 末日 %s 致后期信号 T+20 截断；样本仍偏小且近期单窗口，"
                   "任何正值均非稳健结论，仅作方向参考；正式准入须真实信号流≥30信号日" % dates[-1]),
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("[ok] %s" % OUT)


if __name__ == "__main__":
    main()
