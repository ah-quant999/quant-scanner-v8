#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alpha101_backtest.py — 101 Formulaic Alphas 独立分层回测（阶段1/P0-P2）

目标：对候选 alpha 做 point-in-time 五分位分层回测，筛选出收益率为正、胜率>52% 的因子，
为接入 final_recommend.py 提供数据依据。持有期覆盖 T+1/T+5/T+10/T+20，短线+中长均有。

数据源：raw_data/_rps_cache/*.json（已有 K 线缓存，不拉新数据）。
输出：raw_data/alpha101_backtest.json（本机跑批产物，需 ALLOW_LOCAL_ALGO=1）。

口径与 alpha101_v8_analysis.md 一致：
  vwap = amount / volume, adv20 = mean(amount,20)
  rank 用当日截面 pct=True, delta(x,d)=x_t-x_{t-d}
"""
import os, sys, json, time, argparse, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
RAW = os.path.join(ROOT, "raw_data")
CACHE_DIR = os.path.join(RAW, "_rps_cache")
OUT_JSON = os.path.join(RAW, "alpha101_backtest.json")

COST = 0.0020
HOLDS = [1, 5, 10, 20, 30, 60, 90, 180, 250]
STEP = 10
FETCH_DAYS = 800

sys.path.insert(0, BASE)
from calc_stock_rps import _load_cache_raw  # noqa: E402

KLINE_CACHE_DIR = os.path.join(RAW, "kline_cache")


def _load_cache_any(code):
    """本地 K 线读取（双源，按可用性自动选择）。

    ① raw_data/_rps_cache/ —— **长历史（413 条）+ 真实 amount**，本机离线回测用。
       该目录被 .gitignore:39 忽略（2026-09-08 主人令「仅 kline_cache 一项入仓」）
       ⇒ 云端 runner 的 actions/checkout 会 git clean -ffdx 掉它，故**不能作为唯一源**。
    ② raw_data/kline_cache/ —— **已入仓 · 云端零网络可取**（3120 只）。只存
       date/open/high/low/close/volume（前复权）⇒ amount 用 close×volume×100 近似，
       与 calc_crds.py::_records_to_df **同源同口径**。

    返回 records list（date/open/high/low/close/volume/amount）或 None。
    """
    # ① _rps_cache（长历史 + 真实成交额）
    try:
        df = _load_cache_raw(code)
        if df is not None and len(df) >= 60:
            recs = df[["date", "open", "high", "low", "close", "volume", "amount"]].copy()
            recs["date"] = recs["date"].astype(str).str[:10]
            return recs.to_dict("records")
    except Exception:
        pass
    # ② kline_cache（已入仓 · 云端可用）
    p = os.path.join(KLINE_CACHE_DIR, "%s.json" % code)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return None
    if isinstance(rows, dict):
        rows = rows.get("bars") or rows.get("data") or []
    if not isinstance(rows, list) or len(rows) < 60:
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            o = float(r["open"]); c = float(r["close"])
            h = float(r["high"]); l = float(r["low"]); v = float(r["volume"])
        except Exception:
            continue
        d = str(r.get("date") or r.get("day") or "")[:10]
        if not d or c <= 0:
            continue
        out.append({"date": d, "open": o, "high": h, "low": l, "close": c,
                    "volume": v, "amount": c * v * 100.0})
    if len(out) < 60:
        return None
    out.sort(key=lambda x: x["date"])
    return out




def _log(m=""):
    print(m, flush=True)


def _is_a6(code):
    return len(code) == 6 and code.isdigit()


def _market_of(code):
    return "sh" if code.startswith(("6", "9")) else "sz"


def _load_klines(codes, workers):
    """只读本地 _rps_cache（本机断网环境不触发网络拉取，避免超时拖慢）。"""
    out, n_fetched, n_cached, n_fail = {}, 0, 0, 0
    t0 = time.time()

    def _work(code):
        recs = _load_cache_any(code)
        if recs:
            return code, recs, "cache"
        return code, None, "fail"

    _log(f"[kline] 读本地缓存 {len(codes)} 只 x {FETCH_DAYS} 日（{workers} 线程）...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_work, c): c for c in codes}
        for i, fut in enumerate(as_completed(futs), 1):
            code, recs, how = fut.result()
            if recs:
                out[code] = sorted(recs, key=lambda r: r["date"])
                if how == "fetch":
                    n_fetched += 1
                else:
                    n_cached += 1
            else:
                n_fail += 1
            if i % 40 == 0 or i == len(codes):
                _log(f"[kline] {i}/{len(codes)} 完成（抓取{n_fetched}/缓存{n_cached}/失败{n_fail}，耗时 {time.time()-t0:.0f}s）")
    return out


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def _net_ret(rows, t, h, cost=COST):
    if t + 1 + h >= len(rows):
        return None
    entry = _f(rows[t + 1].get("open"))
    exit_ = _f(rows[t + 1 + h].get("close"))
    if entry <= 0 or exit_ <= 0:
        return None
    return exit_ / entry - 1 - cost


def _sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def _rank_series(values):
    """pct=True 排名，返回 0~1 数组。"""
    n = len(values)
    if n == 0:
        return []
    sorted_idx = sorted(range(n), key=lambda i: values[i])
    ranks = [0] * n
    for rank, idx in enumerate(sorted_idx, start=1):
        ranks[idx] = rank
    return [(r - 0.5) / n for r in ranks]


def _correlation(x, y):
    """皮尔逊相关系数。"""
    if len(x) < 2 or len(x) != len(y):
        return None
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = sum((a - mx) ** 2 for a in x)
    sy = sum((b - my) ** 2 for b in y)
    if sx <= 0 or sy <= 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sx * sy)


def _covariance(x, y):
    if len(x) < 2 or len(x) != len(y):
        return None
    mx, my = sum(x) / len(x), sum(y) / len(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / len(x)


def _ts_rank(series, d):
    """过去 d 天内的时序排名（pct=True）。返回最新值在过去 d 天中的排名分位。"""
    if len(series) < d:
        return None
    window = series[-d:]
    latest = window[-1]
    sorted_w = sorted(window)
    # 找 latest 在排序后的位置
    lo = 0
    for i, v in enumerate(sorted_w):
        if v < latest:
            lo = i + 1
    hi = len(sorted_w)
    for i in range(len(sorted_w) - 1, -1, -1):
        if sorted_w[i] <= latest:
            hi = i + 1
            break
    return ((lo + hi) / 2.0 - 0.5) / len(sorted_w)


# ---------- alpha 因子函数（返回 float 或 None） ----------

def alpha12(rows, t):
    """sign(delta(volume,1)) * (-delta(close,1))"""
    if t < 1:
        return None
    dv = _f(rows[t]["volume"]) - _f(rows[t - 1]["volume"])
    dc = _f(rows[t]["close"]) - _f(rows[t - 1]["close"])
    return _sign(dv) * (-dc)


def alpha2(rows, t):
    """-correlation(rank(delta(log(volume),2)), rank((close-open)/open), 6)"""
    if t < 6:
        return None
    dv, co = [], []
    for i in range(t - 5, t + 1):
        v0 = _f(rows[i - 2]["volume"])
        v1 = _f(rows[i]["volume"])
        dv.append(math.log(v1 / v0) if v0 > 0 and v1 > 0 else 0.0)
        o = _f(rows[i]["open"])
        c = _f(rows[i]["close"])
        co.append((c - o) / o if o > 0 else 0.0)
    rdv = _rank_series(dv)
    rco = _rank_series(co)
    corr = _correlation(rdv, rco)
    return -corr if corr is not None else None


def alpha33(rows, t):
    """rank(-(1 - open/close))"""
    o = _f(rows[t]["open"])
    c = _f(rows[t]["close"])
    if c == 0:
        return None
    return -(1.0 - o / c)


def alpha101(rows, t):
    """(close - open) / ((high - low) + .001)"""
    o = _f(rows[t]["open"])
    c = _f(rows[t]["close"])
    h = _f(rows[t]["high"])
    l = _f(rows[t]["low"])
    return (c - o) / (h - l + 0.001)


def alpha3(rows, t):
    """-correlation(rank(open), rank(volume), 10)"""
    if t < 9:
        return None
    opens, vols = [], []
    for i in range(t - 9, t + 1):
        opens.append(_f(rows[i]["open"]))
        vols.append(_f(rows[i]["volume"]))
    ro = _rank_series(opens)
    rv = _rank_series(vols)
    corr = _correlation(ro, rv)
    return -corr if corr is not None else None


def alpha6(rows, t):
    """-correlation(open, volume, 10)"""
    if t < 9:
        return None
    opens, vols = [], []
    for i in range(t - 9, t + 1):
        opens.append(_f(rows[i]["open"]))
        vols.append(_f(rows[i]["volume"]))
    corr = _correlation(opens, vols)
    return -corr if corr is not None else None


def alpha13(rows, t):
    """-rank(covariance(rank(close), rank(volume), 5))"""
    if t < 4:
        return None
    closes, vols = [], []
    for i in range(t - 4, t + 1):
        closes.append(_f(rows[i]["close"]))
        vols.append(_f(rows[i]["volume"]))
    rc = _rank_series(closes)
    rv = _rank_series(vols)
    cov = _covariance(rc, rv)
    return -cov if cov is not None else None


def alpha42(rows, t):
    """rank((vwap - close) / (vwap + close))"""
    v = _f(rows[t]["volume"])
    a = _f(rows[t]["amount"])
    c = _f(rows[t]["close"])
    if v <= 0:
        return None
    vwap = a / v
    return (vwap - c) / (vwap + c)


def alpha7(rows, t):
    """((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))"""
    if t < 19 or t < 60:
        return None
    vol = _f(rows[t]["volume"])
    amounts = [_f(rows[i]["amount"]) for i in range(t - 19, t + 1)]
    adv20 = sum(amounts) / len(amounts)
    dc = _f(rows[t]["close"]) - _f(rows[t - 7]["close"])
    if adv20 < vol:
        series = [abs(_f(rows[i]["close"]) - _f(rows[i - 7]["close"])) for i in range(t - 59, t + 1)]
        tr = _ts_rank(series, 60)
        return (-tr * _sign(dc)) if tr is not None else None
    return -1.0


def alpha34(rows, t):
    """rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))"""
    if t < 4:
        return None
    rets = []
    for i in range(1, t + 1):
        c0 = _f(rows[i - 1]["close"])
        c1 = _f(rows[i]["close"])
        rets.append(c1 / c0 - 1 if c0 > 0 else 0.0)
    # stddev(returns,2) 和 stddev(returns,5) 是滚动窗口，截面计算每个时点
    s2_list, s5_list, dc_list = [], [], []
    for i in range(t - 3, t + 1):
        window2 = rets[max(0, i - 1):i + 1]
        window5 = rets[max(0, i - 4):i + 1]
        m2 = sum(window2) / len(window2)
        m5 = sum(window5) / len(window5)
        s2 = math.sqrt(sum((x - m2) ** 2 for x in window2) / len(window2)) if len(window2) > 1 else 0.0
        s5 = math.sqrt(sum((x - m5) ** 2 for x in window5) / len(window5)) if len(window5) > 1 else 0.0
        s2_list.append(s2 / s5 if s5 > 0 else 0.0)
        dc_list.append(_f(rows[i]["close"]) - _f(rows[i - 1]["close"]))
    rs2 = _rank_series(s2_list)
    rdc = _rank_series(dc_list)
    if not rs2 or not rdc:
        return None
    return (1 - rs2[-1]) + (1 - rdc[-1])


def alpha21(rows, t):
    """布林带+成交量过滤"""
    if t < 7:
        return None
    closes = [_f(rows[i]["close"]) for i in range(t - 7, t + 1)]
    ma8 = sum(closes) / len(closes)
    m = sum(closes) / len(closes)
    s = math.sqrt(sum((x - m) ** 2 for x in closes) / len(closes))
    upper = ma8 + s
    lower = ma8 - s
    ma2 = (_f(rows[t]["close"]) + _f(rows[t - 1]["close"])) / 2.0
    if upper < ma2:
        return -1.0
    if ma2 < lower:
        return 1.0
    amounts = [_f(rows[i]["amount"]) for i in range(t - 19, t + 1)] if t >= 19 else []
    if amounts:
        adv20 = sum(amounts) / len(amounts)
        v_today = _f(rows[t]["volume"])
        a_today = _f(rows[t]["amount"])
        vwap = a_today / v_today if v_today > 0 else 0
        return 1.0 if vwap >= adv20 else -1.0
    return -1.0


def alpha54(rows, t):
    """((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))"""
    o = _f(rows[t]["open"])
    c = _f(rows[t]["close"])
    h = _f(rows[t]["high"])
    l = _f(rows[t]["low"])
    denom = (l - h) * (c ** 5)
    if denom == 0:
        return None
    return (-1 * (l - c) * (o ** 5)) / denom


ALPHA_DEFS = [
    {"name": "ALPHA_12", "fn": alpha12, "min_hist": 1, "note": "量价背离：放量跌=正，缩量涨=负"},
    {"name": "ALPHA_2", "fn": alpha2, "min_hist": 6, "note": "量变化与开盘收益秩相关为负"},
    {"name": "ALPHA_33", "fn": alpha33, "min_hist": 1, "note": "开盘-收盘反转"},
    {"name": "ALPHA_101", "fn": alpha101, "min_hist": 1, "note": "日内实体占波幅比"},
    {"name": "ALPHA_3", "fn": alpha3, "min_hist": 10, "note": "开盘价与成交量秩相关为负"},
    {"name": "ALPHA_6", "fn": alpha6, "min_hist": 10, "note": "开盘价与成交量相关为负"},
    {"name": "ALPHA_13", "fn": alpha13, "min_hist": 5, "note": "收盘价与成交量秩协方差为负"},
    {"name": "ALPHA_42", "fn": alpha42, "min_hist": 1, "note": "vwap偏离反转"},
    {"name": "ALPHA_7", "fn": alpha7, "min_hist": 60, "note": "放量7日动量/反转"},
    {"name": "ALPHA_34", "fn": alpha34, "min_hist": 5, "note": "波动率收敛+价格动量"},
    {"name": "ALPHA_21", "fn": alpha21, "min_hist": 20, "note": "布林带+成交量过滤"},
    {"name": "ALPHA_54", "fn": alpha54, "min_hist": 1, "note": "日内极端位置加权反转"},
]


def _max_drawdown(nav):
    peak, mdd = -1e18, 0.0
    for v in nav:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return round(mdd * 100, 2)


def _layer_stats(samples_by_layer, dates_by_layer):
    out = {}
    for layer in sorted(samples_by_layer):
        per = samples_by_layer[layer]
        stat = {"n": len(dates_by_layer.get(layer, []))}
        for h, rets in per.items():
            if not rets:
                continue
            stat[f"avg_{h}d"] = round(sum(rets) / len(rets) * 100, 3)
            stat[f"win_{h}d"] = round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1)
        # 注：当前样本是「每个调仓点每层内各票」的收益集合，非组合时间序列，
        # 因此不计算净值链；避免把重叠/非重叠收益误连乘得出天文数字。
        out[layer] = stat
    return out


def backtest_alpha(klines, alpha_def):
    """按持有期 h 做非重叠分层回测：持有 h 日就每 h 日调仓一次，避免长持有期收益被重复平均。"""
    fn, min_hist = alpha_def["fn"], alpha_def["min_hist"]
    max_h = max(HOLDS)

    # 先收集所有可用时点的因子值（与 h 无关）
    all_factors = {}
    for code, rows in klines.items():
        n = len(rows)
        if n < min_hist + max_h + 10:
            continue
        for t in range(min_hist - 1, n - 1 - max_h):
            try:
                f = fn(rows, t)
            except Exception:
                f = None
            if f is None or math.isnan(f):
                continue
            all_factors.setdefault(t, {})[code] = f

    valid_ts = sorted(all_factors)
    if len(valid_ts) < 4:
        return {"error": f"有效因子时点不足（{len(valid_ts)}），需 ≥4"}

    per_hold = {}
    for h in HOLDS:
        # 非重叠调仓点：间隔 = h（T+1 每日，T+250 约 2-3 次）
        rebalance_ts = valid_ts[::max(h, 1)]
        if len(rebalance_ts) < 3:
            continue

        factor_at, rets_at = {}, {}
        for t in rebalance_ts:
            for code, f in all_factors[t].items():
                rows = klines[code]
                if t + 1 + h >= len(rows):
                    continue
                ret = _net_ret(rows, t, h)
                if ret is None:
                    continue
                factor_at.setdefault(t, {})[code] = f
                rets_at.setdefault(t, {})[code] = {h: ret}

        ts = sorted(factor_at)
        if len(ts) < 3:
            continue

        samples, dates_by_layer = {}, {}
        for t in ts:
            fmap = factor_at[t]
            codes_sorted = sorted(fmap, key=lambda c: fmap[c], reverse=True)
            n = len(codes_sorted)
            if n < 25:
                continue
            for i, c in enumerate(codes_sorted):
                layer = min(4, i * 5 // n) + 1
                r = rets_at[t][c][h]
                samples.setdefault(layer, {}).setdefault(h, []).append(r)
                dates_by_layer.setdefault(layer, []).append(t)
        layers = _layer_stats(samples, dates_by_layer)

        def _spread(sub_ts):
            top, bot = [], []
            for t in sub_ts:
                fmap = factor_at[t]
                cs = sorted(fmap, key=lambda c: fmap[c], reverse=True)
                n = len(cs)
                if n < 25:
                    continue
                q = max(1, n // 5)
                for c in cs[:q]:
                    top.append(rets_at[t][c][h])
                for c in cs[-q:]:
                    bot.append(rets_at[t][c][h])
            if not top or not bot:
                return None
            return sum(top) / len(top) - sum(bot) / len(bot)

        mid = ts[len(ts) // 2]
        top1 = layers.get(1, {})
        per_hold[h] = {
            "n_points": len(ts),
            "universe_n": len(factor_at[ts[0]]) if ts else 0,
            "avg_top_pct": top1.get(f"avg_{h}d"),
            "win_top_pct": top1.get(f"win_{h}d"),
            "spread_top_bottom_pct": round((_spread(ts) or 0) * 100, 3),
            "spread_is_pct": round((_spread([t for t in ts if t <= mid]) or 0) * 100, 3),
            "spread_oos_pct": round((_spread([t for t in ts if t > mid]) or 0) * 100, 3),
            "layers": layers,
        }

    if not per_hold:
        return {"error": "所有持有期样本不足"}

    # 最佳持有期：选满足「收益>0 且胜率≥52% 且 n_points≥5」中 avg 最高的
    best = None
    for h, r in per_hold.items():
        avg = r["avg_top_pct"]
        win = r["win_top_pct"]
        npts = r["n_points"]
        if avg is None or win is None:
            continue
        if avg <= 0 or win < 52.0 or npts < 5:
            continue
        # 🔴 2026-09-14 修正（关键）：原判定只看 «Top 层 avg>0 且胜率≥52%»，**不判
        #   Top-Bottom 利差** ⇒ 会把「只捕获市场 beta、截面零/负区分度」的因子误判为
        #   PASS。实测（_rps_cache 702 只 × 413 日，补利差字段后复算）：
        #     ALPHA_12 利差 -2.78%(OOS -6.87%) / ALPHA_21 -3.78%(-6.29%) /
        #     ALPHA_7  -3.45%(-7.86%)        / ALPHA_34 -2.30%(-2.94%) /
        #     ALPHA_42 -0.81%(-1.25%，且其 vwap 在 amount 近似时取值恒为 99/101 常数)
        #   —— 这些因子 Top 层的高收益/高胜率**全部来自股池整体上涨**，排序能力为负。
        #   现补「利差>0 且 OOS 利差>0」双门槛：只有真有截面区分度的才判 PASS。
        if not ((r.get("spread_top_bottom_pct") or 0) > 0):
            continue
        if r.get("spread_oos_pct") is None or r["spread_oos_pct"] <= 0:
            continue
        if best is None or avg > best["avg"]:
            best = {"hold": h, "avg": avg, "win": win, "n_points": npts}

    passed = bool(best)

    return {
        "valid_factor_dates": len(valid_ts),
        "per_hold": per_hold,
        "best_hold": best,
        "verdict": "PASS" if passed else "FAIL",
        "verdict_note": ("最优持有期 Top 层收益>0 且胜率≥52% 且 n_points≥5，"
                         "**且 Top-Bottom 利差>0 且 OOS 利差>0** → 可接入候选；否则剔除。"
                         "（2026-09-14 补利差门槛：只捕获市场 beta 的因子利差为负，原判定会误判为达标）"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=int(os.environ.get("RPS_WORKERS", "8")))
    args = ap.parse_args()

    _log("=" * 70)
    _log(f"  Alpha101 独立分层回测 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 70)
    # universe 目录：优先 _rps_cache（长历史，本机离线回测）；否则 kline_cache（已入仓·云端可取）
    uni_dir = CACHE_DIR if os.path.isdir(CACHE_DIR) else KLINE_CACHE_DIR
    if not os.path.isdir(uni_dir):
        _log(f"[error] universe 缓存目录都不存在: {CACHE_DIR} / {KLINE_CACHE_DIR}")
        sys.exit(1)
    codes = [f[:-5] for f in os.listdir(uni_dir)
             if f.endswith(".json") and _is_a6(f[:-5])]
    if not codes:
        _log(f"[error] {uni_dir} 无 A股 6 位码 universe")
        sys.exit(1)
    _log(f"universe: {len(codes)} 只（重点池 A股，来自 {os.path.basename(uni_dir)}）")

    klines = _load_klines(codes, args.workers)
    if not klines:
        _log("[error] 无任何 K 线数据")
        sys.exit(1)
    _log(f"K 线就绪: {len(klines)} 只")

    results = {}
    for ad in ALPHA_DEFS:
        _log(f"\n—— {ad['name']}：{ad['note']} ——")
        res = backtest_alpha(klines, ad)
        summary = {"valid_dates": res.get("valid_factor_dates"),
                   "best_hold": res.get("best_hold"),
                   "verdict": res.get("verdict")}
        if "per_hold" in res:
            summary["holds_tested"] = sorted(res["per_hold"].keys())
        _log(json.dumps(summary, ensure_ascii=False))
        results[ad["name"]] = res

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe": "重点池 A股（_rps_cache 优先 / kline_cache 回退）",
        "cost_roundtrip": COST,
        "rebalance": f"每{STEP}个交易日，入场=次日开盘",
        "alphas": results,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _log(f"\n[ok] 写入 {OUT_JSON}")


if __name__ == "__main__":
    main()
