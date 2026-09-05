#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_expectancy.py — 期望收益回测引擎（walk-forward / 样本外 / 防过拟合）
================================================================================
目的：为 generate_top10.py 的「按回测胜率+收益加权」提供真实数据源。

设计原则（对齐主人宗旨：数据及时准确 · 算法优良 · 胜率高且收益率好）：
1. 样本外：对历史每个交易日 D，用「截至 D 已可知」的信号状态，测量其后
   T+3 / T+5 / T+10 的真实收益，绝不把 D 之后的信息 leakage 进 D 的打分。
2. 期望收益 = 净平均收益（已内含胜率与幅度），同时保留 win_rate 供 P2 组合使用。
3. 样本收缩（Shrinkage）：小样本向中性（胜率50% / 收益0）回归，避免噪声被当信号。
4. 因子有效性：对每个因子分别计算「因子在场 vs 不在场」的前向收益差（edge），
   让 P2 能按因子自身回测期望来定权重，而非拍脑袋 +N。

输入：
  - raw_data/history/top10_daily_*.json  （历史信号快照，含 signals / score_* / close）
  - K线：优先 baostock（runner 环境），本地 _opt_kline_cache 兜底（沙箱验证用）

输出：
  - raw_data/backtest_expectancy.json
      { meta, by_signal{信号元组: {n,win,ret,edge}*horizon},
        by_factor{因子: {n_on,ret_on,win_on,n_off,ret_off,win_off,edge}*horizon} }

用法：
  python backtest_expectancy.py --selftest            # 内置数学自检
  python backtest_expectancy.py --hist-dir D --out O --kline-cache K [--no-baostock]
"""
import json
import os
import re
import sys
import math
import argparse
from collections import defaultdict
from datetime import datetime

# ── 常量 ──
HORIZONS = [3, 5, 10]
SHRINK_K = 10          # 收缩先验强度：等效 10 个中性样本（小样本强收缩防过拟合，大样本近原值）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HIST = os.path.join(BASE_DIR, "..", "raw_data", "history")
DEFAULT_KLINE = os.path.join(BASE_DIR, "_opt_kline_cache")
OUT_PATH = os.path.join(BASE_DIR, "..", "raw_data", "backtest_expectancy.json")


# ════════════════════════════════════════════════════════════════
# 1. 数学工具（带收缩）
# ════════════════════════════════════════════════════════════════
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def win_rate(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return 0.0
    return sum(1 for x in xs if x > 0) / len(xs) * 100.0


def shrink(value, n, k=SHRINK_K):
    """向 0 收缩：样本越多越相信自己。"""
    return value * (n / (n + k)) if n > 0 else 0.0


def shrink_win(wr, n, k=SHRINK_K):
    """胜率向 50% 收缩。"""
    return 50.0 + (wr - 50.0) * (n / (n + k)) if n > 0 else 50.0


# ════════════════════════════════════════════════════════════════
# 2. 加载历史信号快照
# ════════════════════════════════════════════════════════════════
def parse_date_from_fn(fn):
    m = re.search(r"(\d{8})", fn)
    if not m:
        return None
    d = m.group(1)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def load_snapshots(hist_dir):
    """返回 [(date_str, [stock_dict,...]), ...] 按日期升序。"""
    if not os.path.isdir(hist_dir):
        return []
    rows = []
    pat = re.compile(r"top10_daily_(\d{8})\.json$")
    for fn in sorted(os.listdir(hist_dir)):
        m = pat.match(fn)
        if not m:
            continue
        date_str = parse_date_from_fn(fn)
        try:
            with open(os.path.join(hist_dir, fn), "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        arr = d.get("top10") or d.get("stocks") or d.get("top") or []
        if not isinstance(arr, list):
            continue
        rows.append((date_str, arr))
    rows.sort(key=lambda r: r[0])
    return rows


def signal_tuple_of(stk):
    sig = stk.get("signals") or {}
    return (
        bool(sig.get("chan")),
        bool(sig.get("jinzuan") or sig.get("金钻_起涨") or sig.get("金钻_黄柱")),
        bool(sig.get("jigou") or sig.get("四量图_机构变红")),
        bool(sig.get("trend") or sig.get("上涨趋势")),
    )


# ════════════════════════════════════════════════════════════════
# 3. K线来源（baostock 优先，本地缓存兜底）
# ════════════════════════════════════════════════════════════════
def _bs_code(code, market=""):
    c = str(code).zfill(6)
    m = (market or "").lower()
    if c.startswith(("8", "4", "92")):
        return None
    if m in ("sh", "sz"):
        return f"{m}.{c}"
    return f"sh.{c}" if c[0] == "6" else f"sz.{c}"


def load_kline_local(code, market, kline_cache):
    """从本地缓存读 K线，返回 {date: close} 升序 dict。缓存命名用下划线（sh_600036.json）。"""
    bs = _bs_code(code, market) or f"sh.{code.zfill(6)}"
    fname = bs.replace(".", "_") + ".json"
    path = os.path.join(kline_cache, fname)
    if not os.path.isfile(path):
        # 兼容点号命名兜底
        path2 = os.path.join(kline_cache, f"{bs}.json")
        if not os.path.isfile(path2):
            return None
        path = path2
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return None
    out = {}
    for r in rows:
        dt = r.get("date")
        cl = r.get("close")
        if dt and cl is not None and not (isinstance(cl, float) and math.isnan(cl)):
            out[dt] = float(cl)
    return out


def load_kline_baostock(code, market, cache_dir):
    """runner 环境：用 baostock 拉全量日K并写缓存。沙箱无网络则抛异常由调用方兜底。"""
    import baostock as bs  # noqa
    bs_code = _bs_code(code, market)
    if bs_code is None:
        return None
    lg = bs.login()
    if not lg or lg.error_code != "0":
        return None
    try:
        rs = bs.query_history_k_data_plus(
            bs_code, "date,close",
            start_date="2025-01-01", end_date=datetime.now().strftime("%Y-%m-%d"),
            frequency="d", adjustflag="2",
        )
        rows = []
        while rs and rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
    finally:
        bs.logout()
    out = {}
    for r in rows:
        if len(r) >= 2 and r[0] and r[1]:
            try:
                out[r[0]] = float(r[1])
            except ValueError:
                pass
    # 写缓存
    if out and cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, f"{bs_code}.json"), "w", encoding="utf-8") as f:
            json.dump([{"date": k, "close": v} for k, v in sorted(out.items())], f)
    return out


def get_kline(code, market, kline_cache, use_baostock):
    k = load_kline_local(code, market, kline_cache)
    if k:
        return k
    if use_baostock:
        try:
            return load_kline_baostock(code, market, kline_cache)
        except Exception as e:
            print(f"  ⚠️ baostock 拉 {code} 失败: {e}")
    return None


def forward_return(kline, date, h):
    """返回 date 之后第 h 个交易日的收益(%)；无法计算返回 None。"""
    if not kline or date not in kline:
        return None
    dates = sorted(kline.keys())
    try:
        i = dates.index(date)
    except ValueError:
        return None
    j = i + h
    if j >= len(dates):
        return None
    p0, p1 = kline[dates[i]], kline[dates[j]]
    if not p0:
        return None
    return (p1 - p0) / p0 * 100.0


# ════════════════════════════════════════════════════════════════
# 4. 聚合
# ════════════════════════════════════════════════════════════════
def aggregate(snapshots, kline_fn):
    """
    snapshots: [(date, [stock,...])]
    kline_fn(code, market) -> {date:close} or None
    返回 (by_signal, by_factor, coverage)
    """
    by_signal = defaultdict(lambda: {h: [] for h in HORIZONS})
    # 因子：在场/不在场 两个桶
    factor_defs = {
        "fund": lambda s: (s.get("score_fund") or 0) > 0,
        "sector": lambda s: (s.get("score_sector") or 0) > 0,
        "quality": lambda s: (s.get("score_quality") or 0) > 0,
        "sig_jinzuan": lambda s: signal_tuple_of(s)[1],
        "sig_jigou": lambda s: signal_tuple_of(s)[2],
        "sig_trend": lambda s: signal_tuple_of(s)[3],
        "sig_chan": lambda s: signal_tuple_of(s)[0],
    }
    by_factor = {f: {h: {"on": [], "off": []} for h in HORIZONS} for f in factor_defs}

    coverage = {"stocks_total": 0, "with_kline": 0, "occ_total": 0}

    for date, stocks in snapshots:
        for s in stocks:
            code = str(s.get("code") or s.get("full_code") or "").zfill(6)
            market = str(s.get("market") or ("" if not code else ("sh" if code[0] == "6" else "sz")))
            kline = kline_fn(code, market)
            coverage["stocks_total"] += 1
            if not kline:
                continue
            coverage["with_kline"] += 1
            tup = signal_tuple_of(s)
            fflags = {f: fn(s) for f, fn in factor_defs.items()}
            for h in HORIZONS:
                ret = forward_return(kline, date, h)
                if ret is None:
                    continue
                coverage["occ_total"] += 1
                by_signal[tup][h].append(ret)
                for f, on in fflags.items():
                    by_factor[f][h]["on" if on else "off"].append(ret)

    # 汇总 by_signal
    sig_out = {}
    for tup, hd in by_signal.items():
        rec = {"key": ",".join("1" if x else "0" for x in tup)}
        for h in HORIZONS:
            rs = hd[h]
            n = len(rs)
            rec[f"n{h}"] = n
            rec[f"win{h}"] = round(shrink_win(win_rate(rs), n), 2)
            rec[f"ret{h}"] = round(shrink(mean(rs), n), 3)
            # 期望收益（净平均收益，已含胜率与幅度），带收缩
            rec[f"edge{h}"] = round(shrink(mean(rs), n), 3)
        sig_out[rec["key"]] = rec

    # 汇总 by_factor（edge = 在场收益 - 不在场收益，带收缩）
    fac_out = {}
    for f, hd in by_factor.items():
        rec = {}
        for h in HORIZONS:
            on, off = hd[h]["on"], hd[h]["off"]
            non, noff = len(on), len(off)
            r_on, r_off = shrink(mean(on), non), shrink(mean(off), noff)
            w_on, w_off = shrink_win(win_rate(on), non), shrink_win(win_rate(off), noff)
            rec[f"n_on{h}"] = non
            rec[f"n_off{h}"] = noff
            rec[f"ret_on{h}"] = round(r_on, 3)
            rec[f"ret_off{h}"] = round(r_off, 3)
            rec[f"win_on{h}"] = round(w_on, 2)
            rec[f"win_off{h}"] = round(w_off, 2)
            rec[f"edge{h}"] = round(r_on - r_off, 3)
        fac_out[f] = rec

    return sig_out, fac_out, coverage


# ════════════════════════════════════════════════════════════════
# 5. 自检（合成数据，验证数学）
# ════════════════════════════════════════════════════════════════
def selftest():
    print("=== 自检：收缩 / 胜率 / 期望 ===")
    # 小样本（n=3，全涨 5%）应被强烈收缩
    rs = [5.0, 5.0, 5.0]
    n = len(rs)
    assert abs(shrink_win(win_rate(rs), n) - (50 + (100 - 50) * n / (n + SHRINK_K))) < 1e-6, "win收缩错"
    assert abs(shrink(mean(rs), n) - (5.0 * n / (n + SHRINK_K))) < 1e-6, "收益收缩错"
    # 大样本（n=200，全涨 5%）应接近原值（按公式 5.0*200/(200+K)）
    big = [5.0] * 200
    assert abs(shrink(mean(big), 200) - 5.0 * 200 / (200 + SHRINK_K)) < 1e-6, "大样本收缩公式错"
    # 胜率数学（0.0 不计入胜）
    assert abs(win_rate([1.0, -1.0, 0.0]) - 100 / 3) < 1e-6, "胜率错"
    assert abs(win_rate([1.0, 2.0, 3.0]) - 100) < 1e-6, "全胜应=100"
    # forward_return 逻辑
    kl = {"2026-01-01": 100.0, "2026-01-02": 110.0, "2026-01-03": 121.0, "2026-01-04": 121.0}
    assert abs(forward_return(kl, "2026-01-01", 1) - 10.0) < 1e-6, "T+1收益错"
    assert abs(forward_return(kl, "2026-01-01", 2) - 21.0) < 1e-6, "T+2收益错"
    assert forward_return(kl, "2026-01-01", 10) is None, "越界应返回None"
    assert forward_return(kl, "2026-99-99", 1) is None, "缺日期应返回None"
    # aggregate 端到端（合成快照 + 合成kline）
    snap = [("2026-01-01", [{"code": "600000", "market": "sh",
                             "signals": {"chan": True, "jinzuan": False, "jigou": True, "trend": True},
                             "score_fund": 5, "score_sector": 0, "score_quality": 3}])]
    def fake_kline(code, market):
        return {"2026-01-01": 100.0, "2026-01-02": 105.0, "2026-01-03": 110.0,
                "2026-01-04": 115.0, "2026-01-05": 120.0, "2026-01-06": 125.0,
                "2026-01-07": 130.0, "2026-01-08": 135.0, "2026-01-09": 140.0,
                "2026-01-10": 145.0, "2026-01-11": 150.0}
    sig, fac, cov = aggregate(snap, fake_kline)
    # T+3: 100->115 => +15%；n=1 收缩后 = round(15/(1+K),3)
    assert abs(sig["1,0,1,1"]["ret3"] - round(15.0 / (1 + SHRINK_K), 3)) < 1e-6, f"聚合ret3错={sig['1,0,1,1']['ret3']}"
    assert fac["fund"]["edge3"] is not None, "因子edge应存在"
    assert fac["fund"]["n_on3"] == 1 and fac["fund"]["n_off3"] == 0, "因子分桶错"
    print("✅ 全部自检通过")
    print(f"   样例信号(1,0,1,1) T+3 收缩后收益={sig['1,0,1,1']['ret3']}%, 因子fund在场n={fac['fund']['n_on3']}")


# ════════════════════════════════════════════════════════════════
# 6. 主流程
# ════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist-dir", default=DEFAULT_HIST)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--kline-cache", default=DEFAULT_KLINE)
    ap.add_argument("--use-baostock", dest="use_baostock", action="store_true")
    ap.add_argument("--no-baostock", dest="use_baostock", action="store_false")
    # runner 无参调用时由 SCRIPT_ENV 注入 V8_USE_BAOSTOCK=1 启用 baostock 拉全量K线
    _default_bs = os.environ.get("V8_USE_BAOSTOCK") == "1"
    ap.set_defaults(use_baostock=_default_bs)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print(f"📂 加载历史快照: {args.hist_dir}")
    snapshots = load_snapshots(args.hist_dir)
    print(f"   快照数: {len(snapshots)}")
    if not snapshots:
        print("   ⚠️ 无快照，退出")
        return

    print(f"📈 加载K线（cache={args.kline_cache}, baostock={args.use_baostock}）")
    sig, fac, cov = aggregate(
        snapshots,
        lambda code, market: get_kline(code, market, args.kline_cache, args.use_baostock),
    )

    out = {
        "meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method": "walk-forward / out-of-sample, shrinkage_k=%d" % SHRINK_K,
            "horizons": HORIZONS,
            "n_snapshots": len(snapshots),
            "date_range": [snapshots[0][0], snapshots[-1][0]],
            "coverage": cov,
            "partial": (cov["with_kline"] < cov["stocks_total"]),
            "needs_refresh": (cov["with_kline"] < cov["stocks_total"]),
            "note": "本地缓存仅含部分股票且日期可能滞后；完整新鲜数据请在 runner 用 --use-baostock 重跑。",
        },
        "by_signal": sig,
        "by_factor": fac,
    }
    _od = os.path.dirname(args.out)
    if _od:
        os.makedirs(_od, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 写出: {args.out}")
    print(f"   信号组合数: {len(sig)} | 因子数: {len(fac)}")
    print(f"   覆盖: 股票{nev(cov,'stocks_total')} / 有K线{nev(cov,'with_kline')} / 有效样本{nev(cov,'occ_total')}")
    print(f"   部分数据: {out['meta']['partial']}")


def nev(d, k):
    return d.get(k, 0)


if __name__ == "__main__":
    main()
