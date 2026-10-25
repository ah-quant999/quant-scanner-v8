#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_untested_factors.py — 未验证因子大清账（2026-10-25 主人令「今天验证完，好的留差的删」）

背景：26 项因子打分全表中，form(P2 形态)/P3 研究四因子/inst(52周新高) 一直无 expectancy 实锤，
长期「不确定地占位」。本脚本用 4.2 年 K线缓存（kline_cache_multi, 866只 ∩ 金股池 875），
按生产代码口径**忠实复刻**每个信号，跑「信号组 vs 池基线」前向 10 日期望差（与
backtest_expectancy.json by_factor 同款判读：正向加分项命中组跑输 = 拖累 = 删）。

方法纪律（同 validate/factor_battery）：
  - 月度再平衡（stride=20 交易日）；信号只用 ≤i 数据（无未来函数）；
  - 前向收益 close[i+10]/close[i]-1；每再平衡日：excess = 信号组均值 − 池基线均值；
  - 跨日聚合 期望/胜率/t；样本门槛：单日信号组 ≥5 票才计。
判读阈值：excess ≥ +0.30pp 且 t≥1 → 保留；excess ≤ −0.30pp → 删（实锤拖累）；
  其余（|excess|<0.30pp 或样本不足）→ 无证据 → 按「不留不确定」下架。

产出：终端报告 + raw_data/untested_factor_verdicts.json
"""
import json, os, math, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
CACHE = os.path.join(RAW, "kline_cache_multi")
OUT_JSON = os.path.join(RAW, "untested_factor_verdicts.json")

HOLD = 10
MIN_SIG = 5          # 单日信号组最小票数
POOL_FILE = os.path.join(RAW, "gold_pool.json")

# ── 生产口径复刻（algorithms/generate_top10.py + scanner.py，逐行对照） ──

def ema_series(data, span):
    alpha = 2.0 / (span + 1)
    out = [0.0] * len(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out

def forcast_val(series, n=6):
    # 线性回归拟合最近 n 个值，返回最后一个回归预测值（scanner.forcast_val 同款）
    y = series[-n:]
    m = float(n)
    sx = (m - 1) * m / 2.0
    sxx = sum(x * x for x in range(n))
    sy = sum(y)
    sxy = sum(x * v for x, v in enumerate(y))
    den = m * sxx - sx * sx
    if abs(den) < 1e-12:
        return y[-1]
    slope = (m * sxy - sx * sy) / den
    intercept = (sy - slope * sx) / m
    return slope * (n - 1) + intercept

PERIODS = [(3, 6, 9), (5, 10, 20), (7, 14, 28), (9, 18, 36), (11, 22, 44), (13, 26, 52), (21, 34, 68)]

def ema_up_at(bars, j):
    """scanner.calc_ema_trends 同款：7 组三EMA均值 FORCAST(6) 方向向上组数（0-7）。
    bars ≤ j（含当日），段长 = max(最长组+6, 50)。"""
    if j + 1 < 100:
        return 0
    seg = bars[max(0, j - 74): j + 1]
    ohlc = [(float(r["open"]) + float(r["high"]) + float(r["low"]) + float(r["close"])) / 4.0
            for r in seg]
    up = 0
    for s, m, l in PERIODS:
        e_s = ema_series(ohlc, s)
        e_m = ema_series(ohlc, m)
        e_l = ema_series(ohlc, l)
        triple = [(e_s[i] + e_m[i] + e_l[i]) / 3.0 for i in range(len(ohlc))]
        if forcast_val(triple, 6) > forcast_val(triple[:-1], 6):
            up += 1
    return up

def rsi14_at(bars, j):
    """scanner.calc_rsi 同款：SMA 方式 RSI14（rolling mean，非 Wilder）。"""
    if j < 14:
        return None
    gains, losses = [], []
    for k in range(j - 13, j + 1):
        p0, p1 = float(bars[k - 1]["close"]), float(bars[k]["close"])
        d = p1 - p0 if p0 > 0 else 0.0
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains) / 14.0
    al = sum(losses) / 14.0
    if al <= 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)

def is_limit_up(bars, j):
    """涨停代理（板块感知）：收盘涨幅 ≥9.8%（主板）或 ≥19.8%（创业板300/科创板688/北交所8/4）。
    生产用 scanner 的 当日涨停 标记；无历史标记，按板块规则代理。"""
    c0 = float(bars[j - 1]["close"])
    c1 = float(bars[j]["close"])
    if c0 <= 0:
        return False
    code = bars[j].get("code", "")
    th = 0.198 if code[:3] in ("300", "688", "830", "831", "832", "833", "834",
                               "835", "836", "837", "838", "839", "870", "871", "872", "873") or code[:1] in ("4", "8") else 0.098
    return c1 / c0 - 1.0 >= th

def breakout_5d(bars, j):
    """generate_top10.breakout_5d_of 同款：今日高价≥近5日高价最高 且 收盘>昨收。"""
    if j < 5:
        return False
    high_5d = max(float(r["high"]) for r in bars[j - 4: j + 1])
    return float(bars[j]["high"]) >= high_5d and float(bars[j]["close"]) > float(bars[j - 1]["close"])

def vol_metrics_at(bars, j):
    """generate_top10._kline_volume_metrics 同款（asof=j）。"""
    if j < 29:
        return None
    today = bars[j]
    prev_20 = bars[j - 20: j]
    vol_20 = sum(float(r["volume"]) for r in prev_20) / 20.0
    high_30 = max(float(r["high"]) for r in bars[j - 29: j + 1])
    low_30 = min(float(r["low"]) for r in bars[j - 29: j + 1])
    high_5 = max(float(r["high"]) for r in bars[j - 4: j + 1])
    low_5 = min(float(r["low"]) for r in bars[j - 4: j + 1])
    o, c = float(today["open"]), float(today["close"])
    return {
        "vol_ratio": (float(today["volume"]) / vol_20) if vol_20 > 0 else 1.0,
        "range_pos_30": ((c - low_30) / (high_30 - low_30)) if high_30 > low_30 else 0.5,
        "range_pos_5": ((c - low_5) / (high_5 - low_5)) if high_5 > low_5 else 0.5,
        "pct_today": ((c - o) / o * 100) if o > 0 else 0.0,
    }

def pct20_at(bars, j):
    if j < 20:
        return None
    p = float(bars[j - 20]["close"])
    return None if p <= 0 else float(bars[j]["close"]) / p * 100 - 100.0

def frog_streak(bars, j):
    """generate_top10._frog_in_pan_score 同款：连续小阳（0.2≤阳线幅度≤3.0，振幅<5%）计数。"""
    streak = 0
    for r in reversed(bars[max(0, j - 20): j + 1]):
        o = float(r["open"])
        if o <= 0:
            break
        pct = (float(r["close"]) - o) / o * 100
        rng = (float(r["high"]) - float(r["low"])) / o * 100
        if 0.2 <= pct <= 3.0 and rng < 5.0:
            streak += 1
        else:
            break
    return streak

def nearhigh250_at(bars, j):
    """inst 52周新高 的 K线代理：收盘距 250 日最高价距离（≥0.999 视为创/近新高）。"""
    if j < 250:
        return None
    hi = max(float(r["high"]) for r in bars[j - 249: j + 1])
    return None if hi <= 0 else float(bars[j]["close"]) / hi


def main():
    pool = json.load(open(POOL_FILE, encoding="utf-8"))
    pool_codes = set()
    for k, v in (pool.get("stocks") or {}).items():
        if v.get("code"):
            pool_codes.add(v["code"])
    print("金股池: %d 只" % len(pool_codes))

    mkt = json.load(open(os.path.join(CACHE, "000001.json"), encoding="utf-8"))
    all_dates = [r["date"] for r in mkt]
    rb_dates = all_dates[-1::-20][::-1]
    print("再平衡采样日: %d (%s ~ %s)" % (len(rb_dates), rb_dates[0], rb_dates[-1]))

    stocks = {}
    for fn in os.listdir(CACHE):
        if not fn.endswith(".json") or fn == "000001.json":
            continue
        code = fn[:-5]
        if code not in pool_codes:
            continue
        try:
            bars = json.load(open(os.path.join(CACHE, fn), encoding="utf-8"))
        except Exception:
            continue
        if isinstance(bars, list) and len(bars) >= 300:
            for r in bars:
                r["code"] = code
            idx = {r["date"]: j for j, r in enumerate(bars)}
            stocks[code] = (bars, idx)
    print("池内可回测: %d 只 (池∩缓存)" % len(stocks))

    # 每采样日 × 每票：signals + fwd
    # raw[d][code] = {"s": {...}, "fwd": ret}
    raw = {}
    for d in rb_dates:
        row = {}
        for code, (bars, idx) in stocks.items():
            j = idx.get(d)
            if j is None or j < 260 or j + HOLD >= len(bars):
                continue
            b = bars
            p0, p1 = float(b[j]["close"]), float(b[j + HOLD]["close"])
            if not (p0 and p0 > 0):
                continue
            vm = vol_metrics_at(b, j)
            p20 = pct20_at(b, j)
            rsi = rsi14_at(b, j)
            eu = ema_up_at(b, j)
            nh = nearhigh250_at(b, j)
            sig = {
                "ema5": 1 if eu >= 5 else 0,
                "ema34": 1 if 3 <= eu <= 4 else 0,
                "ema12": 1 if 1 <= eu <= 2 else 0,
                "ema0": 1 if eu == 0 else 0,
                "limitup": 1 if is_limit_up(b, j) else 0,
                "not_limitup": 0 if is_limit_up(b, j) else 1,
                "rsi68": 1 if (rsi is not None and rsi < 68) else 0,
                "rsi70hot": 1 if (rsi is not None and rsi > 70) else 0,
                "rsi30": 1 if (rsi is not None and rsi < 30) else 0,
                "mom0_10": 1 if (p20 is not None and 0 < p20 < 10) else 0,
                "mom20hot": 1 if (p20 is not None and p20 >= 20) else 0,
                "pct20lt35": 1 if (p20 is not None and p20 < 35) else 0,
                "brk5": 1 if breakout_5d(b, j) else 0,
                "vs1": 1 if (vm and vm["pct_today"] > 0 and 1.3 <= vm["vol_ratio"] < 1.8) else 0,
                "vs2": 1 if (vm and vm["pct_today"] > 0 and 1.8 <= vm["vol_ratio"] < 2.5) else 0,
                "vs3": 1 if (vm and vm["pct_today"] > 0 and vm["vol_ratio"] >= 2.5) else 0,
                "frog3": 1 if frog_streak(b, j) >= 3 else 0,
                "frog5": 1 if frog_streak(b, j) >= 5 else 0,
                "osb": 1 if (vm and p20 is not None and p20 <= -10 and vm["pct_today"] > 0) else 0,
                "rangecont": 1 if (vm and vm["range_pos_30"] >= 0.7 and vm["range_pos_5"] <= 0.3) else 0,
                "w52hi": 1 if (nh is not None and nh >= 0.999) else 0,
            }
            row[code] = {"s": sig, "fwd": p1 / p0 - 1.0}
        if len(row) >= 30:
            raw[d] = row
    dates = sorted(raw.keys())
    print("有效再平衡日: %d" % len(dates))

    SIGNALS = [
        ("ema5",       "EMA结构≥5 (+5分)"),
        ("ema34",      "EMA结构3-4 (+3分)"),
        ("ema12",      "EMA结构1-2 (+1分)"),
        ("ema0",       "EMA结构=0 (无结构,对照)"),
        ("limitup",    "当日涨停 (−5分,反向)"),
        ("not_limitup","非涨停 (+2分)"),
        ("rsi68",      "RSI<68 (+2分)"),
        ("rsi70hot",   "RSI>70 过热 (对照)"),
        ("rsi30",      "RSI<30 超卖 (+3分)"),
        ("mom0_10",    "20日涨幅0~10% (+2分)"),
        ("mom20hot",   "20日涨幅≥20% (−1/−3/−6罚)"),
        ("pct20lt35",  "20日涨幅<35% (+2分)"),
        ("brk5",       "5日突破 (P0加权)"),
        ("vs1",        "量能突破1档 vr1.3-1.8 (+1)"),
        ("vs2",        "量能突破2档 vr1.8-2.5 (+2)"),
        ("vs3",        "量能突破3档 vr≥2.5 (+3)"),
        ("frog3",      "温水煮青蛙 streak≥3 (+2)"),
        ("frog5",      "温水煮青蛙 streak≥5 (+4)"),
        ("osb",        "超跌反弹 (梯度>0)"),
        ("rangecont",  "上涨中继 (+3)"),
        ("w52hi",      "52周新高 (inst, +7档)"),
    ]

    results = {}
    print("\n=== 信号组 vs 池基线 · 前向%d日期望差 ===" % HOLD)
    print("%-28s %10s %8s %8s %8s %8s" % ("信号", "excess", "win%", "t", "票次", "覆盖日"))
    for key, label in SIGNALS:
        exs = []
        ns = 0
        covered = 0
        for d in dates:
            base_row = raw[d]
            base = sum(r["fwd"] for r in base_row.values()) / len(base_row)
            grp = [(c, r["fwd"]) for c, r in base_row.items() if r["s"].get(key)]
            if len(grp) < MIN_SIG:
                continue
            ex = sum(f for _, f in grp) / len(grp) - base
            exs.append(ex)
            ns += len(grp)
            covered += 1
        if not exs:
            results[key] = {"label": label, "n": 0}
            print("%-28s %10s" % (label, "样本不足"))
            continue
        mu = sum(exs) / len(exs)
        win = sum(1 for x in exs if x > 0) / len(exs)
        var = sum((x - mu) ** 2 for x in exs) / (len(exs) - 1) if len(exs) > 1 else 0.0
        t = mu / (var ** 0.5 / math.sqrt(len(exs))) if var > 0 else 0.0
        results[key] = {"label": label, "excess": mu, "win": win, "t": t,
                        "ns": ns, "days": covered, "n": len(exs)}
        print("%-28s %+9.2f%% %7.0f%% %8.2f %8d %8d" %
              (label, mu * 100, win * 100, t, ns, covered))

    # 裁决
    print("\n=== 裁决（阈值: excess≥+0.30pp 且 t≥1 → KEEP; ≤−0.30pp → DROP; 其余 → 无证据→DELIST）===")
    verdicts = {}
    for key, label in SIGNALS:
        r = results.get(key) or {}
        if r.get("n", 0) == 0:
            v = "NO_DATA"
        else:
            e, t = r["excess"], r["t"]
            if e >= 0.0030 and t >= 1.0:
                v = "KEEP"
            elif e <= -0.0030:
                v = "DROP"
            else:
                v = "NO_EDGE"
        verdicts[key] = v
        r["verdict"] = v
        print("%-28s %s  (%s)" % (label, v, r.get("excess", "n/a")))

    json.dump({"generated": "2026-10-25", "hold": HOLD, "universe": "gold_pool_875 ∩ kline_cache_multi",
               "results": results, "verdicts": verdicts},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n落盘: %s" % OUT_JSON)


if __name__ == "__main__":
    main()
