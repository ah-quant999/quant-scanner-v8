#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track_resonance.py — 「最强共振」信号 T+1→T+250 持久跟踪器
- 重建历史全部最强共振信号(机构+游资双正,合计≥8000万,龙虎榜)
- 每只记录 入场=T+1开盘(信号盘后可知,次日开盘可买), 单边成本0.15%
- 计算各期限收益: 数据成熟到哪档算哪档, 未到标 pending
- 输出 raw_data/resonance_track.json (供每日洞察卡渲染 / 长期跟踪)
口径与 algo_track.json 对齐: horizons 含 [1,5,10,20,30,60,90,120,180,250]
"""
import json, re, os, statistics
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw_data")
CST = timezone(timedelta(hours=8))
COST = 0.0015
HORIZONS = [1, 5, 10, 20, 30, 60, 90, 120, 180, 250]


def load_signals():
    h = json.load(open(os.path.join(RAW, "lhb_history.json"), encoding="utf-8"))
    dates = sorted(k for k in h if re.match(r"^\d{4}-\d{2}-\d{2}$", k))
    sigs = []
    for d in dates:
        day = h[d]
        if not day.get("trading"):
            continue
        for s in day.get("stocks", []):
            i, y = s.get("inst_net_万", 0), s.get("yz_net_万", 0)
            if i > 0 and y > 0 and (i + y) >= 8000 and not re.match(r"^(11|12)\d{4}$", s["code"]):
                sigs.append({"date": d, "code": s["code"], "name": s["name"],
                             "pct": s.get("pct", 0.0),
                             "inst_yi": round(i / 1e4, 3), "yz_yi": round(y / 1e4, 3),
                             "sum_yi": round((i + y) / 1e4, 3)})
    return sigs


def main():
    sigs = load_signals()
    kc = os.path.join(RAW, "kline_cache")
    rows = []
    for s in sigs:
        p = os.path.join(kc, s["code"] + ".json")
        if not os.path.exists(p):
            rows.append(dict(s, entry=None, status="no_kline")); continue
        bars = json.load(open(p, encoding="utf-8"))
        idx = next((i for i, b in enumerate(bars) if b["date"] == s["date"]), None)
        if idx is None or idx + 1 >= len(bars):
            rows.append(dict(s, entry=None, status="pending_t1")); continue
        entry = bars[idx + 1]["open"]
        rec = dict(s, entry=round(entry, 3), gap=round((entry / bars[idx]["close"] - 1) * 100, 2))
        max_fwd = len(bars) - 1 - idx
        rec["max_fwd"] = max_fwd
        for hz in HORIZONS:
            j = idx + hz
            if j < len(bars):
                rec[f"r{hz}"] = round((bars[j]["close"] / entry - 1 - COST) * 100, 2)
            else:
                rec[f"r{hz}"] = None
        rows.append(rec)

    def agg(hz, recs):
        vals = [r[f"r{hz}"] for r in recs if r.get(f"r{hz}") is not None]
        if not vals:
            return {"mature": 0, "pending": len(recs), "win%": None, "avg%": None, "med%": None}
        return {"mature": len(vals), "pending": len(recs) - len(vals),
                "win%": round(100 * sum(1 for v in vals if v > 0) / len(vals), 1),
                "avg%": round(statistics.mean(vals), 2), "med%": round(statistics.median(vals), 2),
                "best%": round(max(vals), 1), "worst%": round(min(vals), 1)}

    mature_recs = [r for r in rows if r.get("entry") is not None]
    per_horizon = {f"T+{hz}": agg(hz, mature_recs) for hz in HORIZONS}

    # 🆕 2026-10-21 基准超额拆解（880003 平均股价·等权全A，raw_data/bench_880003.json）
    #   无基准则跳过（不阻塞主链）；日期对齐：信号日 T+0 与基准同日收盘相比
    bench_path = os.path.join(RAW, "bench_880003.json")
    if os.path.exists(bench_path):
        try:
            _braw = json.load(open(bench_path, encoding="utf-8"))
            bench = {f"{k[:4]}-{k[4:6]}-{k[6:]}": float(v) for k, v in _braw.items()} if all(len(k) == 8 for k in _braw) else {k: float(v) for k, v in _braw.items()}
            bks = sorted(bench)
            for hz in HORIZONS:
                er, br, sr = [], [], []
                for r in mature_recs:
                    sv = r.get(f"r{hz}")
                    if sv is None or r["date"] not in bench:
                        continue
                    i = bks.index(r["date"])
                    j = i + hz
                    if j >= len(bks):
                        continue
                    bv = (bench[bks[j]] / bench[bks[i]] - 1 - COST) * 100
                    sr.append(sv); br.append(bv); er.append(sv - bv)
                if er:
                    per_horizon[f"T+{hz}"].update({
                        "bench_avg%": round(statistics.mean(br), 2),
                        "excess_avg%": round(statistics.mean(er), 2),
                        "excess_med%": round(statistics.median(er), 2),
                        "excess_win%": round(100 * sum(1 for x in er if x > 0) / len(er), 1)})
        except Exception as e:
            print(f"[WARN] 基准超额计算跳过: {e}")

    def cohort(rows, pred, label):
        sub = [r for r in rows if pred(r)]
        d = {"label": label, "n": len(sub)}
        for hz in (1, 5, 10, 30, 90, 250):   # 🆕 2026-10-21 加 T+1/T+10（重复共振子信号的短窗 alpha 是唯一正贡献，卡片要展示）
            a = agg(hz, sub)
            d[f"T+{hz}"] = a
        return d
    big = cohort(mature_recs, lambda r: r["sum_yi"] >= 2, "合计净买≥2亿")
    small = cohort(mature_recs, lambda r: r["sum_yi"] < 2, "合计净买0.8~2亿")
    seen = set(); first = []; rep = []
    for r in sorted(mature_recs, key=lambda x: x["date"]):
        (rep if r["code"] in seen else first).append(r); seen.add(r["code"])
    first_c = cohort(first, lambda r: True, "首次共振")
    rep_c = cohort(rep, lambda r: True, "重复共振")

    report = {
        "generated": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "window": "2026-06-10 ~ "+max((s["date"] for s in sigs), default=""),
        "criteria": "龙虎榜: inst_net>0 且 yz_net>0 且 (inst+yz)≥8000万; 转债剔除",
        "entry": "T+1 开盘买入, 单边成本0.15%, 净口径; 未成熟期限标 pending",
        "benchmark": "880003 平均股价(等权全A)·同成本口径" if os.path.exists(bench_path) else None,
        "n_signals": len(sigs), "n_tracked": len(mature_recs),
        "per_horizon": per_horizon,
        "cohorts_T5_T30_T90_T250": {"金额≥2亿": big, "金额0.8~2亿": small,
                                     "首次共振": first_c, "重复共振": rep_c},
        "rows": rows,
    }
    out = os.path.join(RAW, "resonance_track.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[DONE] {out}")
    print(f"信号 {len(sigs)} / 已跟踪(有T+1) {len(mature_recs)}")
    print("\n== 全期限聚合(成熟样本数 / 胜率 / 均 / 中位) ==")
    print(f"{'期限':<8}{'成熟':>6}{'待熟':>6}{'胜率':>8}{'均%':>9}{'中位%':>9}")
    for hz in HORIZONS:
        a = per_horizon[f"T+{hz}"]
        if a["mature"] == 0:
            print(f"T+{hz:<5}{'0':>6}{a['pending']:>6}{'  —':>9}{'  —':>9}{'  —':>9}")
        else:
            print(f"T+{hz:<5}{a['mature']:>6}{a['pending']:>6}{a['win%']:>7}%{a['avg%']:>+8}%{a['med%']:>+8}%")
    print("\n== cohorts (T+5 / T+30 / T+90 成熟统计) ==")
    for c in (big, small, first_c, rep_c):
        print(f"\n[{c['label']}] n={c['n']}")
        for hz in (5, 30, 90):
            a = c[f"T+{hz}"]
            if a["mature"]:
                print(f"  T+{hz}: 成熟{a['mature']} 胜率{a['win%']}% 均{a['avg%']:+}% 中位{a['med%']:+}%")
            else:
                print(f"  T+{hz}: 待熟({a['pending']})")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
