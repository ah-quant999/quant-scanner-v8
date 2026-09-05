#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_expectancy_p4.py — P4 因子回测（工作副本，基于 algorithms/backtest_expectancy.py）
================================================================================
在原 walk-forward 引擎上新增（2026-09-05 主人拍板：低波动 + 残差动量 + 漂移门控）：

1. p4_lowvol25 / p4_lowvol35 ：20日实现波动率(年化%) ≤25 / ≤35 在场
2. p4_resid5 / p4_resid10    ：20日残差动量（个股收益 − β×市场收益）>5% / >10% 在场
   β 用过去 60 日个股~市场日收益 OLS 估计；市场代理 = 上证指数 sh.000001
3. by_regime 段（漂移门控诊断）：按 regime_filter 口径（grind/panic=开门），
   输出开门/关门两桶的 T+3/5/10 整体统计 + 每信号组合分桶 edge，
   用于验证「门控开时信号更准」并支撑因子级 regime 开关。

用法（本地 venv 有 baostock）：
  python backtest_expectancy_p4.py --hist-dir H --kline-cache K --out O --use-baostock
原文件保持不动；本文件验证通过后由部署脚本原子复制回 algorithms/。
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
SHRINK_K = 10
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ALGO = BASE_DIR   # 仓库部署时与原版一致：相对脚本自身目录
DEFAULT_HIST = os.path.join(DEFAULT_ALGO, "..", "raw_data", "history")
DEFAULT_KLINE = os.path.join(DEFAULT_ALGO, "_opt_kline_cache")
OUT_PATH = os.path.join(DEFAULT_ALGO, "..", "raw_data", "backtest_expectancy.json")
VALID_CODES_PATH = os.path.join(DEFAULT_ALGO, "_valid_codes.json")   # 有效A股参考集（缺失时 baostock 自动生成）


# ════════════════════════════════════════════════════════════════
# 1. 数学工具（带收缩）— 与原版一致
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
    return value * (n / (n + k)) if n > 0 else 0.0


def shrink_win(wr, n, k=SHRINK_K):
    return 50.0 + (wr - 50.0) * (n / (n + k)) if n > 0 else 50.0


# ════════════════════════════════════════════════════════════════
# 2. 历史快照加载 — 与原版一致
# ════════════════════════════════════════════════════════════════
def parse_date_from_fn(fn):
    m = re.search(r"(\d{8})", fn)
    if not m:
        return None
    d = m.group(1)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def load_snapshots(hist_dir):
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
# 噪声代码闸门（2026-09-05，原闸门版合并）：历史快照混入不存在/已退市脏码
# （永远取不到K线、长期污染 partial 覆盖率）。既不在参考集又无K线 → 剔除。
# 参考集缺失时用 baostock 全市场上市股票列表自动生成；再失败回退全量计入。
# ════════════════════════════════════════════════════════════════
def _generate_valid_codes_baostock(path):
    """baostock 拉全市场上市股票（type=1, status=1）生成参考集。返回 set 或 None"""
    try:
        import baostock as bs
        lg = bs.login()
        if not lg or lg.error_code != "0":
            return None
        try:
            rs = bs.query_stock_basic()
            rows = []
            while rs and rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
        finally:
            bs.logout()
        codes = set()
        for r in rows:
            # fields: code, code_name, ipoDate, outDate, type, status
            if len(r) >= 6 and r[4] == "1" and r[5] == "1":
                codes.add(str(r[0]).split(".")[-1].zfill(6))
        if len(codes) > 1000:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"codes": sorted(codes),
                           "source": "baostock query_stock_basic",
                           "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
            return codes
    except Exception as e:
        print(f"  ⚠️ baostock 生成有效代码参考集失败: {e}")
    return None


def load_valid_codes(path, use_baostock=True):
    """加载有效A股代码参考集（6位零填充集合）。缺失时 baostock 自动生成；再失败返回 None（回退全量计入）。"""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            codes = d.get("codes") or []
            if isinstance(codes, list) and len(codes) > 1000:
                return set(str(c).zfill(6) for c in codes)
        except Exception:
            pass
    if use_baostock:
        return _generate_valid_codes_baostock(path)
    return None


# ════════════════════════════════════════════════════════════════
# 3. K线来源 — 与原版一致 + 指数加载
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
    bs = _bs_code(code, market) or f"sh.{code.zfill(6)}"
    fname = bs.replace(".", "_") + ".json"
    path = os.path.join(kline_cache, fname)
    if not os.path.isfile(path):
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
# 3.5 P4 因子数学（低波 / 残差动量 / 漂移门控）
# ════════════════════════════════════════════════════════════════
def realized_vol_pct(closes, i, window=20):
    """closes 升序列表，截至下标 i（含）的 window 日年化波动率(%)；不足返回 None"""
    if i < window or i >= len(closes):
        return None
    seg = closes[i - window:i + 1]
    rets = []
    for j in range(1, len(seg)):
        if seg[j - 1] > 0 and seg[j] > 0:
            rets.append(math.log(seg[j] / seg[j - 1]))
    if len(rets) < window:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100.0


def window_return_pct(closes, i, window=20):
    """截至下标 i 的 window 日收益(%)"""
    if i < window or i >= len(closes):
        return None
    p0, p1 = closes[i - window], closes[i]
    if not p0:
        return None
    return (p1 - p0) / p0 * 100.0


def resid_momentum_pct(kline, date, mkt_kline, window=20, est=60):
    """残差动量(%)：近 window 日个股收益 − β×同期市场收益。
    β = 过去 est 日个股/市场日收益 OLS 斜率（截至 date，含当日）。
    数据不足返回 None。"""
    if not mkt_kline or date not in kline or date not in mkt_kline:
        return None
    kd = sorted(kline.keys())
    md = sorted(mkt_kline.keys())
    i = kd.index(date)
    j = md.index(date)
    if i < est or j < est:
        return None
    # 对齐两序列的公共日期（取个股日期为基准，向前 est+window 个交易日）
    dates = kd[max(0, i - est - window - 5):i + 1]
    pairs = [(kline[d], mkt_kline[d]) for d in dates if d in mkt_kline]
    if len(pairs) < est:
        return None
    sc = [p[0] for p in pairs]
    mc = [p[1] for p in pairs]
    n = len(sc)
    sret = [math.log(sc[k] / sc[k - 1]) for k in range(1, n) if sc[k - 1] > 0 and sc[k] > 0]
    mret = [math.log(mc[k] / mc[k - 1]) for k in range(1, n) if mc[k - 1] > 0 and mc[k] > 0]
    if len(sret) != len(mret) or len(sret) < est:
        return None
    ms, mm = sum(sret) / len(sret), sum(mret) / len(mret)
    cov = sum((a - ms) * (b - mm) for a, b in zip(sret, mret)) / (len(sret) - 1)
    var = sum((b - mm) ** 2 for b in mret) / (len(mret) - 1)
    beta = cov / var if var > 1e-12 else 1.0
    beta = max(0.2, min(2.5, beta))   # β 夹逼防爆炸
    stock_r = window_return_pct(sc, n - 1, window)
    mkt_r = window_return_pct(mc, n - 1, window)
    if stock_r is None or mkt_r is None:
        return None
    return stock_r - beta * mkt_r


def load_regime_series(algo_dir, use_baostock):
    """复用 regime_filter 口径计算每日市场 regime → {date: regime}；失败返回 {}"""
    try:
        sys.path.insert(0, algo_dir)
        import regime_filter as rf
        merged = rf._merge_market_regime()
        return merged or {}
    except Exception as e:
        print(f"  ⚠️ regime series 计算失败（门控诊断将跳过）: {e}")
        return {}


# ════════════════════════════════════════════════════════════════
# 4. 聚合（P4 扩展）
# ════════════════════════════════════════════════════════════════
def aggregate(snapshots, kline_fn, mkt_kline=None, regime_series=None, valid_codes=None):
    """
    snapshots: [(date, [stock,...])]
    kline_fn(code, market) -> {date:close} or None
    mkt_kline: {date:close} 上证指数（P4 因子用）；None 则 P4 因子跳过
    regime_series: {date: regime}（P4 门控诊断用）；空则跳过
    valid_codes: 有效A股参考集（噪声闸门）；None 回退全量计入
    返回 (by_signal, by_factor, coverage, by_regime)
    """
    by_signal = defaultdict(lambda: {h: [] for h in HORIZONS})
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

    # P4 因子桶（需要 kline+mkt，惰性计算并缓存 per (code,date)）
    p4_defs = {}
    if mkt_kline:
        p4_defs = {
            "p4_lowvol45": lambda closes, i, kd: (realized_vol_pct(closes, i, 20) or 999) <= 45,
            "p4_lowvol55": lambda closes, i, kd: (realized_vol_pct(closes, i, 20) or 999) <= 55,
        }
    by_factor.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_defs})

    # 残差动量：连续值，分档布尔（>5 / >10 / <-5 弱化桶）
    resid_cache = {}
    p4_resid_defs = {
        "p4_resid5": lambda r: (r is not None) and (r > 5),
        "p4_resid10": lambda r: (r is not None) and (r > 10),
    }
    by_factor.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_resid_defs})

    # 漂移门控诊断桶
    gate_open = {h: [] for h in HORIZONS}
    gate_closed = {h: [] for h in HORIZONS}
    gate_open_by_signal = {h: defaultdict(list) for h in HORIZONS}   # 仅开门日的信号分桶
    # 因子 × 门控 分桶（P4 漂移门控落地核心：因子在开门/关门状态下的 edge 对比）
    by_factor_gate = defaultdict(lambda: {
        "open": {h: [] for h in HORIZONS},
        "closed": {h: [] for h in HORIZONS},
    })

    coverage = {"stocks_total": 0, "with_kline": 0, "occ_total": 0,
                "p4_evaluated": 0, "p4_skipped_no_mkt": 0, "excluded_garbage": 0}

    for date, stocks in snapshots:
        gate_regime = (regime_series or {}).get(date)
        gate_is_open = gate_regime in ("grind", "panic") if gate_regime else None
        for s in stocks:
            code = str(s.get("code") or s.get("full_code") or "").zfill(6)
            if not code:
                continue
            # 市场以代码前缀为准（沪6/深0,3），不信任快照里可能写错的 market 字段（闸门版口径）
            market = "sh" if code[0] == "6" else "sz"
            kline = kline_fn(code, market)
            has_k = kline is not None
            # 噪声代码闸门：既不在参考集、又无K线的脏码直接剔除（不计入覆盖，不算缺失）
            if valid_codes is not None and (code not in valid_codes) and (not has_k):
                coverage["excluded_garbage"] += 1
                continue
            coverage["stocks_total"] += 1
            if not has_k:
                continue
            coverage["with_kline"] += 1
            tup = signal_tuple_of(s)
            fflags = {f: fn(s) for f, fn in factor_defs.items()}

            # P4 波动率因子（惰性）
            if p4_defs:
                kd = sorted(kline.keys())
                if date in kd:
                    i = kd.index(date)
                    closes = [kline[d] for d in kd]
                    for f, fn in p4_defs.items():
                        try:
                            fflags[f] = bool(fn(closes, i, kd))
                        except Exception:
                            fflags[f] = False
                    # 残差动量
                    ck = (code, date)
                    if ck not in resid_cache:
                        resid_cache[ck] = resid_momentum_pct(kline, date, mkt_kline)
                    rv = resid_cache[ck]
                    for f, fn in p4_resid_defs.items():
                        fflags[f] = fn(rv)
                    coverage["p4_evaluated"] += 1
                else:
                    for f in list(p4_defs) + list(p4_resid_defs):
                        fflags[f] = False
            else:
                coverage["p4_skipped_no_mkt"] += 1

            for h in HORIZONS:
                ret = forward_return(kline, date, h)
                if ret is None:
                    continue
                coverage["occ_total"] += 1
                by_signal[tup][h].append(ret)
                for f, on in fflags.items():
                    if f not in by_factor:
                        continue
                    by_factor[f][h]["on" if on else "off"].append(ret)
                # 门控诊断
                if gate_is_open is True:
                    gate_open[h].append(ret)
                    gate_open_by_signal[h][tup].append(ret)
                elif gate_is_open is False:
                    gate_closed[h].append(ret)
                # 因子 × 门控
                if gate_is_open is not None:
                    gk = "open" if gate_is_open else "closed"
                    for f, on in fflags.items():
                        if f not in by_factor:
                            continue
                        if on:
                            by_factor_gate[f][gk][h].append(ret)

    # 汇总 by_signal（原样）
    sig_out = {}
    for tup, hd in by_signal.items():
        rec = {"key": ",".join("1" if x else "0" for x in tup)}
        for h in HORIZONS:
            rs = hd[h]
            n = len(rs)
            rec[f"n{h}"] = n
            rec[f"win{h}"] = round(shrink_win(win_rate(rs), n), 2)
            rec[f"ret{h}"] = round(shrink(mean(rs), n), 3)
            rec[f"edge{h}"] = round(shrink(mean(rs), n), 3)
        sig_out[rec["key"]] = rec

    # 汇总 by_factor（原样）
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

    # 汇总 by_regime（漂移门控诊断）
    reg_out = {}
    for label, bucket in (("gate_open", gate_open), ("gate_closed", gate_closed)):
        rec = {}
        for h in HORIZONS:
            rs = bucket[h]
            n = len(rs)
            rec[f"n{h}"] = n
            rec[f"win{h}"] = round(shrink_win(win_rate(rs), n), 2)
            rec[f"ret{h}"] = round(shrink(mean(rs), n), 3)
        reg_out[label] = rec
    # 开门日各信号组合的 T+10 edge（供因子级 regime 开关用）
    open_sig = {}
    for h in HORIZONS:
        for tup, rs in gate_open_by_signal[h].items():
            key = ",".join("1" if x else "0" for x in tup)
            rec = open_sig.setdefault(key, {})
            rec[f"n{h}"] = len(rs)
            rec[f"edge{h}"] = round(shrink(mean(rs), len(rs)), 3)
    reg_out["gate_open_by_signal"] = open_sig
    reg_out["note"] = ("gate = grind/panic（regime_filter 口径，可开仓）；"
                       "gate_open_by_signal 仅统计开门日信号组合的前向收益")

    # 因子 × 门控 汇总：edge_closed = 门控关时在场收益 − 全体均值；edge_open 同理
    # （用「在场 − 全体」而非「在场 − 不在场」：门控要回答的是该因子在当前市况还灵不灵）
    fac_gate_out = {}
    for f, gk in by_factor_gate.items():
        rec = {}
        for state in ("open", "closed"):
            for h in HORIZONS:
                rs = gk[state][h]
                n = len(rs)
                all_rs = gate_open[h] if state == "open" else gate_closed[h]
                base_mean = mean(all_rs)
                rec[f"n_{state}{h}"] = n
                rec[f"ret_{state}{h}"] = round(shrink(mean(rs), n), 3)
                rec[f"edge_{state}{h}"] = round(shrink(mean(rs), n) - base_mean, 3)
                rec[f"win_{state}{h}"] = round(shrink_win(win_rate(rs), n), 2)
        fac_gate_out[f] = rec
    reg_out["by_factor_gate"] = fac_gate_out

    return sig_out, fac_out, coverage, reg_out


# ════════════════════════════════════════════════════════════════
# 5. 自检（合成数据）
# ════════════════════════════════════════════════════════════════
def selftest():
    print("=== 自检：收缩 / 胜率 / 期望 / P4 ===")
    rs = [5.0, 5.0, 5.0]
    n = len(rs)
    assert abs(shrink_win(win_rate(rs), n) - (50 + (100 - 50) * n / (n + SHRINK_K))) < 1e-6
    assert abs(shrink(mean(rs), n) - (5.0 * n / (n + SHRINK_K))) < 1e-6
    big = [5.0] * 200
    assert abs(shrink(mean(big), 200) - 5.0 * 200 / (200 + SHRINK_K)) < 1e-6
    assert abs(win_rate([1.0, -1.0, 0.0]) - 100 / 3) < 1e-6
    kl = {"2026-01-01": 100.0, "2026-01-02": 110.0, "2026-01-03": 121.0, "2026-01-04": 121.0}
    assert abs(forward_return(kl, "2026-01-01", 1) - 10.0) < 1e-6
    assert forward_return(kl, "2026-01-01", 10) is None
    # P4：恒定价格 → 波动率 0 → lowvol True；残差 = 个股收益 − β×市场收益
    # 合成 90 个交易日（est=60 + window=20 需要足量历史）
    import datetime as _dt
    _dates = []
    _d = _dt.date(2026, 1, 1)
    while len(_dates) < 90:
        if _d.weekday() < 5:
            _dates.append(_d.isoformat())
        _d += _dt.timedelta(days=1)
    flat = {d: 100.0 for d in _dates}
    assert realized_vol_pct(list(flat.values()), len(flat) - 1, 20) == 0.0
    up_mkt = {d: 100.0 + i for i, d in enumerate(_dates)}
    rm = resid_momentum_pct(flat, _dates[-1], up_mkt)
    assert rm is not None and rm < 0, f"平价股对上涨市场残差应为负: {rm}"
    snap = [("2026-01-01", [{"code": "600000", "market": "sh",
                             "signals": {"chan": True, "jinzuan": False, "jigou": True, "trend": True},
                             "score_fund": 5, "score_sector": 0, "score_quality": 3}])]
    sig, fac, cov, reg = aggregate(snap, lambda c, m: {**kl, **{f"2025-12-{d:02d}": 90.0 + d for d in range(1, 32)}},
                                   mkt_kline=None, regime_series={"2026-01-01": "grind"})
    assert abs(sig["1,0,1,1"]["ret3"] - round(21.0 / (1 + SHRINK_K), 3)) < 1e-6
    assert "p4_lowvol25" not in fac, "无市场K线时 P4 因子应跳过"
    assert reg["gate_open"]["n3"] == 1 and reg["gate_open"]["n10"] == 0, "门控分桶错（合成K线仅够T+3）"
    print("✅ 全部自检通过")


def nev(d, k):
    return d.get(k, 0)


# ════════════════════════════════════════════════════════════════
# 6. 主流程
# ════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist-dir", default=DEFAULT_HIST)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--kline-cache", default=DEFAULT_KLINE)
    ap.add_argument("--algorithms-dir", default=DEFAULT_ALGO)
    ap.add_argument("--use-baostock", dest="use_baostock", action="store_true")
    ap.add_argument("--no-baostock", dest="use_baostock", action="store_false")
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

    print(f"📈 加载上证指数（市场代理，baostock={args.use_baostock}）")
    mkt = get_kline("000001", "sh", args.kline_cache, args.use_baostock)
    print(f"   指数K线: {len(mkt) if mkt else 0} 天"
          + (f" [{min(mkt)} ~ {max(mkt)}]" if mkt else ""))

    valid_codes = load_valid_codes(VALID_CODES_PATH, use_baostock=args.use_baostock)
    if valid_codes is None:
        print("   ⚠️ 未取得有效A股参考集（且自动生成失败），回退全量计入模式（partial 可能含脏码）")
    else:
        print(f"   有效A股参考集: {len(valid_codes)} 只（不在集内又无K线的脏码将剔除）")

    print("🌊 计算漂移门控 regime 序列（regime_filter 口径）")
    regime_series = load_regime_series(args.algorithms_dir, args.use_baostock)
    if regime_series:
        rng = sorted(regime_series.keys())
        print(f"   regime 覆盖: {len(rng)} 天 [{rng[0]} ~ {rng[-1]}]")
        from collections import Counter
        print(f"   分布: {dict(Counter(regime_series.values()))}")

    print(f"📈 聚合（cache={args.kline_cache}）")
    sig, fac, cov, reg = aggregate(
        snapshots,
        lambda code, market: get_kline(code, market, args.kline_cache, args.use_baostock),
        mkt_kline=mkt,
        regime_series=regime_series,
        valid_codes=valid_codes,
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
            "code_gate": ("valid_a_share_reference(%d)" % len(valid_codes)) if valid_codes else "none",
            "note": "P4 版：含低波/残差动量因子与漂移门控诊断（sh.000001 市场代理）+ 噪声代码闸门",
        },
        "by_signal": sig,
        "by_factor": fac,
        "by_regime": reg,
    }
    _od = os.path.dirname(args.out)
    if _od:
        os.makedirs(_od, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 写出: {args.out}")
    print(f"   信号组合数: {len(sig)} | 因子数: {len(fac)}")
    print(f"   覆盖: 股票{nev(cov,'stocks_total')} / 有K线{nev(cov,'with_kline')} / 有效样本{nev(cov,'occ_total')} / P4评估{nev(cov,'p4_evaluated')}")
    print(f"   剔除源噪声脏码(出现次数): {nev(cov,'excluded_garbage')}")
    print(f"   部分数据: {out['meta']['partial']}")
    print("   ── P4 因子 edge 速览 ──")
    for f in ("p4_lowvol25", "p4_lowvol35", "p4_resid5", "p4_resid10"):
        r = fac.get(f) or {}
        print(f"   {f:14s} edge10={r.get('edge10')} (on n={r.get('n_on10')}, "
              f"win_on={r.get('win_on10')}, off win={r.get('win_off10')})")
    print("   ── 漂移门控速览 (T+10) ──")
    go, gc = reg.get("gate_open", {}), reg.get("gate_closed", {})
    print(f"   开门: n={go.get('n10')} win={go.get('win10')}% ret={go.get('ret10')}%")
    print(f"   关门: n={gc.get('n10')} win={gc.get('win10')}% ret={gc.get('ret10')}%")
    print("   ── 因子×门控 edge 速览 (T+10, 在场−全体) ──")
    for f, r in (reg.get("by_factor_gate") or {}).items():
        print(f"   {f:14s} 开门edge={r.get('edge_open10')} (n={r.get('n_open10')})  "
              f"关门edge={r.get('edge_closed10')} (n={r.get('n_closed10')})")


if __name__ == "__main__":
    main()
