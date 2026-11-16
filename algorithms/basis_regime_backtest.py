#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贴水 regime 前瞻回测（2026-11-16 主人令「贴水加大可否加仓」第三步·科学落地）。

原则（务必先读）：
  · 当前历史快照（109 天）**从未记录过贴水**，无法回填 ⇒ 本脚本不编造历史、不提前下结论。
  · 数据源 = FUTURES_REALTIME.js 内嵌的 basis_history（自今天起每班累积，随 data 文件推送自持）。
  · 口径完全复用 backtest_expectancy：load_snapshots / get_kline / forward_return / signal_tuple_of。
  · 只按「贴水 regime」分组比较同一批选股信号的前向收益；**不修改任何选股排序/打分**。
  · 样本 <30 一律 watch（沿用框架 classify_verdict 口径）。

用法：
  python algorithms/basis_regime_backtest.py
  python algorithms/basis_regime_backtest.py --selftest
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "algorithms"))
import backtest_expectancy as be

FR_JS = os.path.join(BASE, "data", "FUTURES_REALTIME.js")
OUT = os.path.join(BASE, "raw_data", "basis_regime_backtest.json")
MIN_N = 30
REGIMES = ("deep_converge", "deep_widen", "shallow", "unknown")


def load_basis_history():
    """从 FUTURES_REALTIME.js 读内嵌 basis_history → {date: {variety: {ann,pctile,chg_1d}}}。"""
    import re
    raw = open(FR_JS, encoding="utf-8").read()
    m = re.search(r"window\.FUTURES_REALTIME\s*=\s*(\{.*\})\s*;?\s*$", raw, re.S)
    if not m:
        return {}
    d = json.loads(m.group(1))
    hist = d.get("basis_history") or []
    # 取每日收盘 slot（定稿）优先，盘中次之
    by_date = {}
    for h in hist:
        date = h.get("date")
        if not date or not h.get("ann"):
            continue
        if date not in by_date or h.get("slot") == "close":
            by_date[date] = h
    return by_date


def regime_of(day):
    """按 IF（大盘情绪代表）三共振条件给当日贴水 regime。"""
    ann = (day.get("ann") or {}).get("IF")
    if not isinstance(ann, (int, float)):
        return "unknown"
    # 历史内每条只有 ann/basis；pctile/chg_1d 是当日 metrics，不在历史里 ⇒ 用 ann 序列现算
    return None  # 由 classify_all 统一算分位/变化后回填


def classify_all(by_date):
    """按 ann 序列算分位与日变化 → 每日一个 regime。"""
    dates = sorted(by_date)
    anns = []
    for dt in dates:
        a = by_date[dt].get("ann", {}).get("IF")
        anns.append(a if isinstance(a, (int, float)) else None)
    out = {}
    for i, dt in enumerate(dates):
        a = anns[i]
        if a is None:
            out[dt] = "unknown"
            continue
        valid = [x for x in anns[:i + 1] if x is not None]
        pct = sum(1 for x in valid if x <= a) / len(valid) * 100 if valid else 50
        prev = next((anns[j] for j in range(i - 1, -1, -1) if anns[j] is not None), None)
        chg = a - prev if prev is not None else 0.0
        if pct <= 35 and chg > 0:
            out[dt] = "deep_converge"
        elif pct <= 35 and chg < 0:
            out[dt] = "deep_widen"
        elif pct <= 35:
            out[dt] = "shallow"  # 深但无变化方向（首日）→ 保守
        else:
            out[dt] = "shallow"
    return out


def forward_ret(kline_fn, code, date, h=5):
    try:
        k = kline_fn(code)
        r = be.forward_return(k, date, h)
        return r.get("ret") if isinstance(r, dict) else r
    except Exception:
        return None


def run():
    by_date = load_basis_history()
    reg = classify_all(by_date)
    n_days = len(by_date)
    if n_days < MIN_N:
        out = {"status": "watch", "reason": "贴水历史样本不足（%d 天 < %d），不回测不结论；"
               "待 basis_history 累积达标后自动可跑" % (n_days, MIN_N),
               "n_days": n_days, "regimes": {}, "generated": be.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, default=str)
        print("⏸️ watch:", out["reason"])
        return out

    snaps = be.load_snapshots(os.path.join(BASE, "raw_data", "history"))
    valid = be.load_valid_codes(be.VALID_CODES_PATH, use_baostock=False)
    kline_fn = lambda code: be.get_kline(code, "", os.path.join(BASE, "raw_data", "kline_cache"), False)
    buckets = defaultdict(list)
    for date, stocks in snaps:
        r = reg.get(date)
        if r is None or r == "unknown":
            continue
        for s in stocks[:10]:
            ret = forward_ret(kline_fn, s.get("code"), date, 5)
            if isinstance(ret, (int, float)):
                buckets[r].append(ret)
    result = {}
    for name in REGIMES:
        xs = buckets.get(name, [])
        if not xs:
            continue
        result[name] = {"n": len(xs), "win5": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 2),
                        "ret5": round(sum(xs) / len(xs), 3),
                        "verdict": be.classify_verdict(sum(xs) / len(xs), len(xs)) if hasattr(be, "classify_verdict") else ("watch" if len(xs) < MIN_N else "evaluated")}
    out = {"status": "evaluated", "n_days": n_days, "regimes": result,
           "generated": be.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, default=str)
    print("✅ 回测完成:", json.dumps(result, ensure_ascii=False)[:600])
    return out


def selftest():
    by_date = {"2026-11-%02d" % i: {"ann": {"IF": -2.0 - i * 0.1}} for i in range(1, 31)}
    r = classify_all(by_date)
    assert set(r.values()) <= set(REGIMES)
    print("✅ selftest OK: 30 天序列分类:", {k: list(r.values()).count(k) for k in REGIMES if k in r.values()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else run()
