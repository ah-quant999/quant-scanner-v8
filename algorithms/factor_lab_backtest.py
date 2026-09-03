#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factor_lab_backtest.py — 因子实验室独立分层回测（2026-09-04 主人令「都按你的建议做」·升4⭐证据链）

目的：因子实验室当前 ★★（观测仓）——升星硬伤是「无独立分层回测（胜率/回撤）」。本脚本补齐：
  对「异常量比(缩量=强势)」因子做 5 层(quintile)分层回测：各层净收益/胜率/分层净值最大回撤/
  分季稳定性/样本内外(OOS)一致性；对「ROE_TTM 大市值」因子做 Top30 组合 vs 全池等权基准对比。
  升 3⭐ 判据：Top−Bottom 利差>0 且 Top 层胜率≥55% 且 OOS 同号。
  升 4⭐ 另需「异常换手扩全市场扫描」（数据侧另行开启后复验）。

数据源：
  raw_data/_rps_cache/*.json — universe 名单（重点池 A股 6 位码；calc_stock_rps 当日产出）
  K 线历史 — 复用 calc_stock_rps 的三级兜底抓数链（mootdx→东财→baostock）拉 700 交易日长历史
             （拉不到的票回落 _rps_cache 的 300 日缓存，可回测调仓点相应变少）
  raw_data/factor_lab.json — 当期 ROE_TTM Top30（ROE 因子用）

方法论（每个数字可追溯，无前视）：
  · 异常量比因子：换手率比值中流通股本精确约掉 → 用「当20日日均成交量 ÷ 前240日日均成交量」
    的负值在每个调仓时点重构（缩量=强势=高分），全程 point-in-time；
  · 入场 = 信号次日开盘价（与 factor_ic_analysis 同口径），扣往返成本 0.20%；
  · 调仓 = 每 10 个交易日；持有 = 5/10/20 日；分层 = 每期因子值五分位（L1=最强）；
  · 净值/最大回撤 = 按 hold=10 非重叠链乘；OOS = 时间轴后半段；
  · ROE_TTM 因子局限：K 线无财务历史 → 当期 Top30 分组回看历史收益（隐含 ROE 排名持续性假设），
    证据强度弱于量比因子，升星以量比因子为主证。结果标 methodology_limit。

输出：raw_data/factor_lab_backtest.json（data/FACTOR_LAB_BACKTEST.js 由 update_v8 映射自动重建）
"""
import os, sys, json, time, argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
RAW = os.path.join(ROOT, "raw_data")
CACHE_DIR = os.path.join(RAW, "_rps_cache")
OUT_JSON = os.path.join(RAW, "factor_lab_backtest.json")

COST = 0.0020          # 往返成本
BASELINE = 240         # 量比基线窗口（前12月 ≈ 240 交易日）
RECENT = 20            # 当月窗口
STEP = 10              # 调仓间隔（交易日）
HOLDS = [5, 10, 20]
NEED_MIN = BASELINE + RECENT + 1   # 参与分层的最少历史
FETCH_DAYS = 700       # 拉取长历史（≈ 34 个月，可容纳 ~40 个调仓点）

sys.path.insert(0, BASE)
from calc_stock_rps import _query_kline, _load_cache  # noqa: E402  复用三级兜底抓数链


def _log(m=""):
    print(m, flush=True)


def _is_a6(code):
    return len(code) == 6 and code.isdigit()


def _market_of(code):
    return "sh" if code.startswith(("6", "9")) else "sz"


def _load_klines(codes, workers):
    """每票拉 700 日长历史；失败回落 _rps_cache 300 日缓存。返回 {code: rows}，rows 按 date 升序。"""
    out, n_fetched, n_cached, n_fail = {}, 0, 0, 0
    t0 = time.time()

    def _work(code):
        try:
            df = _query_kline(code, _market_of(code), FETCH_DAYS)
            if df is not None and len(df) >= 60:
                recs = df[["date", "open", "close", "volume"]].copy()
                recs["date"] = recs["date"].astype(str).str[:10]
                return code, recs.to_dict("records"), "fetch"
        except Exception:
            pass
        rows = _load_cache(code)
        if rows is not None and len(rows) >= 60:
            recs = rows[["date", "open", "close", "volume"]].copy()
            recs["date"] = recs["date"].astype(str).str[:10]
            return code, recs.to_dict("records"), "cache"
        return code, None, "fail"

    _log(f"[kline] 拉取 {len(codes)} 只 x {FETCH_DAYS} 日（{workers} 线程）...")
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
                _log(f"[kline] {i}/{len(codes)} 完成（抓取{n_fetched}/缓存{n_cached}/失败{n_fail}，"
                     f"耗时 {time.time()-t0:.0f}s）")
    return out


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def _net_ret(rows, t, h, cost=COST):
    """信号日 t（0-based），次日开盘入场，t+1+h 收盘出场，扣往返成本。返回 None=数据不足。"""
    if t + 1 + h >= len(rows):
        return None
    entry = _f(rows[t + 1].get("open"))
    exit_ = _f(rows[t + 1 + h].get("close"))
    if entry <= 0 or exit_ <= 0:
        return None
    return exit_ / entry - 1 - cost


def _abn_factor_at(rows, t):
    """异常量比因子（缩量=强势=高分）：-(当20日日均量 ÷ 前240日日均量)。"""
    recent = [_f(r.get("volume")) for r in rows[t - RECENT + 1: t + 1]]
    base = [_f(r.get("volume")) for r in rows[t - BASELINE - RECENT + 1: t - RECENT + 1]]
    mr, mb = sum(recent) / max(1, len(recent)), sum(base) / max(1, len(base))
    if mr <= 0 or mb <= 0:
        return None
    return -(mr / mb)


def _max_drawdown(nav):
    peak, mdd = -1e18, 0.0
    for v in nav:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return round(mdd * 100, 2)


def _layer_stats(samples_by_layer, dates_by_layer):
    """samples_by_layer: {layer: {hold: [ret,...]}}；返回每层统计 + hold=10 净值回撤。"""
    out = {}
    for layer in sorted(samples_by_layer):
        per = samples_by_layer[layer]
        stat = {"n": len(dates_by_layer.get(layer, []))}
        for h, rets in per.items():
            if not rets:
                continue
            stat[f"avg_{h}d"] = round(sum(rets) / len(rets) * 100, 3)
            stat[f"win_{h}d"] = round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1)
        # hold=10 非重叠净值（dates 与 rets 同序）
        rets10 = per.get(10, [])
        if len(rets10) >= 3:
            nav, v = [1.0], 1.0
            for r in rets10:
                v *= (1 + r)
                nav.append(v)
            stat["nav_mdd_10d"] = _max_drawdown(nav)
            stat["nav_total_10d"] = round((v - 1) * 100, 2)
        out[layer] = stat
    return out


def backtest_abn(klines, workers_note=""):
    """异常量比因子全池五分位分层回测。"""
    # 预计算每票每个调仓点的因子值与未来收益
    factor_at = {}   # {t: {code: factor}}
    rets_at = {}     # {t: {code: {hold: ret}}}
    for code, rows in klines.items():
        n = len(rows)
        if n < NEED_MIN + 2 * HOLDS[-1]:
            continue
        for t in range(BASELINE + RECENT - 1, n - 1 - HOLDS[-1], STEP):
            f = _abn_factor_at(rows, t)
            if f is None:
                continue
            rets = {h: _net_ret(rows, t, h) for h in HOLDS}
            if any(v is None for v in rets.values()):
                continue
            factor_at.setdefault(t, {})[code] = f
            rets_at.setdefault(t, {})[code] = rets
    ts = sorted(factor_at)
    if len(ts) < 4:
        return {"error": f"可回测调仓点不足（{len(ts)}），需 ≥4", "n_points": len(ts)}

    date_of = {}
    for code, rows in klines.items():
        for t in ts:
            if t < len(rows):
                date_of[t] = rows[t]["date"]
                break

    samples, dates_by_layer = {}, {}
    t_list = ts
    mid = t_list[len(t_list) // 2]
    for t in t_list:
        fmap = factor_at[t]
        codes_sorted = sorted(fmap, key=lambda c: fmap[c], reverse=True)  # 因子降序，L1=最强
        n = len(codes_sorted)
        if n < 25:   # 每层至少 5 只才有五分位意义
            continue
        for i, c in enumerate(codes_sorted):
            layer = min(4, i * 5 // n) + 1
            for h, r in rets_at[t][c].items():
                samples.setdefault(layer, {}).setdefault(h, []).append(r)
            dates_by_layer.setdefault(layer, []).append(t)
    layers = _layer_stats(samples, dates_by_layer)

    # 利差 / OOS / 分季稳定性（hold=10）
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
                r = rets_at[t][c].get(10)
                if r is not None:
                    top.append(r)
            for c in cs[-q:]:
                r = rets_at[t][c].get(10)
                if r is not None:
                    bot.append(r)
        if not top or not bot:
            return None
        return sum(top) / len(top) - sum(bot) / len(bot)

    spread_all = _spread(t_list)
    spread_is = _spread([t for t in t_list if t <= mid])
    spread_oos = _spread([t for t in t_list if t > mid])
    top_win = layers.get(1, {}).get("win_10d")

    # 分季同号
    qsign = {}
    for t in t_list:
        d = date_of.get(t, "")
        q = d[:4] + "Q" + str((int(d[5:7]) - 1) // 3 + 1) if len(d) >= 7 else "?"
        s = _spread([t])
        if s is not None:
            qsign.setdefault(q, []).append(s)
    quarterly = {q: {"avg_spread_10d": round(sum(v) / len(v) * 100, 3),
                     "n": len(v),
                     "positive": all(x > 0 for x in v)}
                 for q, v in sorted(qsign.items())}

    passed = bool(spread_all and spread_all > 0 and (top_win or 0) >= 55.0
                  and spread_oos is not None and ((spread_is or 0) > 0) == ((spread_oos or 0) > 0))
    return {
        "n_points": len(t_list),
        "point_dates": [date_of.get(t, "") for t in t_list],
        "universe_n": len(factor_at[t_list[0]]) if t_list else 0,
        "layers": layers,
        "spread_top_bottom_10d_pct": round((spread_all or 0) * 100, 3),
        "spread_in_sample_pct": round((spread_is or 0) * 100, 3),
        "spread_oos_pct": round((spread_oos or 0) * 100, 3),
        "top_layer_win_10d": top_win,
        "quarterly_stability": quarterly,
        "verdict_3star": "PASS" if passed else "FAIL",
        "verdict_note": "利差>0 + Top层胜率≥55% + OOS与IS同号 → 3星证据；4⭐另需扩全市场扫描后复验",
    }


def backtest_roe(klines):
    """ROE_TTM Top30 组合 vs 全池等权基准（当期分组回看，methodology_limit）。"""
    flab_path = os.path.join(RAW, "factor_lab.json")
    try:
        flab = json.load(open(flab_path, encoding="utf-8"))
        top30 = [it["code"].split(".")[-1] for it in flab.get("roe_largecap", {}).get("top", [])
                 if _is_a6(it.get("code", "").split(".")[-1])]
    except Exception as e:
        return {"error": f"factor_lab.json 读取失败: {e}"}
    if len(top30) < 10:
        return {"error": "ROE Top30 样本不足"}

    basket, univ = {}, {}
    for code, rows in klines.items():
        n = len(rows)
        if n < NEED_MIN + 2 * HOLDS[-1]:
            continue
        for t in range(BASELINE + RECENT - 1, n - 1 - HOLDS[-1], STEP):
            rets = {h: _net_ret(rows, t, h) for h in HOLDS}
            if any(v is None for v in rets.values()):
                continue
            tgt = basket if code in top30 else univ
            for h, r in rets.items():
                tgt.setdefault(h, []).append(r)
    if not basket or not univ:
        return {"error": "ROE 回测样本不足（K 线历史不够）"}

    stat = {"top30_n": len(top30)}
    for h in HOLDS:
        b, u = basket.get(h, []), univ.get(h, [])
        if not b or not u:
            continue
        stat[f"top30_avg_{h}d"] = round(sum(b) / len(b) * 100, 3)
        stat[f"top30_win_{h}d"] = round(sum(1 for r in b if r > 0) / len(b) * 100, 1)
        stat[f"univ_avg_{h}d"] = round(sum(u) / len(u) * 100, 3)
        stat[f"excess_{h}d"] = round((sum(b) / len(b) - sum(u) / len(u)) * 100, 3)
    return {
        **stat,
        "methodology_limit": "当期 ROE 分组回看历史（隐含 ROE 排名持续性假设），证据强度弱于量比因子的 point-in-time 分层",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=int(os.environ.get("RPS_WORKERS", "8")))
    args = ap.parse_args()

    _log("=" * 70)
    _log(f"  因子实验室独立分层回测 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 70)
    if not os.path.isdir(CACHE_DIR):
        _log(f"[error] universe 缓存目录不存在: {CACHE_DIR}（先跑 calc_stock_rps）")
        sys.exit(1)
    codes = [f[:-5] for f in os.listdir(CACHE_DIR)
             if f.endswith(".json") and _is_a6(f[:-5])]
    if not codes:
        _log("[error] _rps_cache 无 A股 6 位码 universe")
        sys.exit(1)
    _log(f"universe: {len(codes)} 只（重点池 A股，来自 _rps_cache）")

    klines = _load_klines(codes, args.workers)
    if not klines:
        _log("[error] 无任何 K 线数据")
        sys.exit(1)
    _log(f"K 线就绪: {len(klines)} 只")

    _log("\n—— 因子1：异常量比（缩量=强势）五分位分层回测 ——")
    abn = backtest_abn(klines)
    _log(json.dumps({k: v for k, v in abn.items()
                     if k in ("n_points", "universe_n", "spread_top_bottom_10d_pct",
                              "top_layer_win_10d", "spread_oos_pct", "verdict_3star")},
                    ensure_ascii=False))

    _log("\n—— 因子2：ROE_TTM 大市值 Top30 vs 全池等权 ——")
    roe = backtest_roe(klines)
    _log(json.dumps({k: v for k, v in roe.items() if not isinstance(v, dict)},
                    ensure_ascii=False))

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe": "重点池 A股（_rps_cache）",
        "cost_roundtrip": COST,
        "rebalance": f"每{STEP}个交易日，入场=次日开盘",
        "abnormal_volume": abn,
        "roe_largecap": roe,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _log(f"\n[ok] 写入 {OUT_JSON}")


if __name__ == "__main__":
    main()
