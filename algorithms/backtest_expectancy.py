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

# ════════════════════════════════════════════════════════════════
# 交易口径常量（2026-09-20 主人拍板「改动①」：口径可配置 + 成本显式化）
# ------------------------------------------------------------------
# 背景：旧口径 forward_return 用「T 日收盘价」买入（p0 = kline[date]）——
#   信号由当日收盘数据算出，却按当日收盘价成交，属前视偏差（无法实盘实现）。
#   同时未扣任何交易成本，期望值系统性虚高。
# 新口径（默认）：
#   ENTRY_MODE = "next_open"  信号日 T → 次日 T+1 开盘价买入；
#                             持有到 T+1+h 的开盘价卖出（h 个交易日）
#                             若信号日/次日无开盘价则回退收盘价（并在 meta 记账）
#   COST_ROUND_TRIP_PCT = 0.2 双边总成本（%），从每笔收益中扣除
# 回退：设环境变量 V8_BT_LEGACY_ENTRY=1 可恢复旧口径（T 日收盘价、零成本），
#   用于「新旧口径同源对比」，发布前可复核。切勿在正式产物中开启。
# ════════════════════════════════════════════════════════════════
COST_ROUND_TRIP_PCT = 0.2          # 双边总成本（%）：印花税+佣金+滑点
# 口径开关（可用环境变量 V8_BT_LEGACY_ENTRY=1 恢复旧口径，供新旧对比；正式产物切勿开启）
ENTRY_MODE = "close" if os.environ.get("V8_BT_LEGACY_ENTRY") == "1" else "next_open"
LEGACY_ENTRY = ENTRY_MODE == "close"

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
    """读本地 K 线缓存 → {date: {"close": c, "open": o}}（open 缺失时为 None）

    🔴 命名回退（2026-09-20 修）：仓库内 K 线缓存存在两套命名体系——
       ① 纯 6 位：`603993.json`（raw_data/kline_cache 口径）
       ② 带市场前缀：`sh_603993.json` / `sh.603993.json`（algorithms/_opt_kline_cache 口径）
    原实现只找 ②，导致 ① 全量落空（表现为 with_kline 意外为 0 或误判 partial）。
    按 ③① ② 顺序逐个尝试，命中即用。
    """
    bs = _bs_code(code, market) or f"sh.{code.zfill(6)}"
    c6 = bs.split(".")[-1]
    try:
        with open(os.path.join(kline_cache, f"{bs}.json"), "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        rows = None
        for _fn in (f"{bs}.json", f"{bs.replace('.', '_')}.json", f"{c6}.json"):
            p = os.path.join(kline_cache, _fn)
            if not os.path.isfile(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                break
            except Exception:
                continue
    if not isinstance(rows, list):
        return None
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        dt = r.get("date")
        cl = r.get("close")
        if not dt:
            continue
        if cl is None or (isinstance(cl, float) and math.isnan(cl)):
            continue
        try:
            cl = float(cl)
        except (TypeError, ValueError):
            continue
        op = r.get("open")
        if op is not None and isinstance(op, float) and math.isnan(op):
            op = None
        try:
            op = float(op) if op is not None else None
        except (TypeError, ValueError):
            op = None
        out[dt] = {"close": cl, "open": op}
    return out or None


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
            bs_code, "date,open,close",
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
        if len(r) >= 3 and r[0] and r[2]:
            try:
                op = float(r[1]) if r[1] else None
                out[r[0]] = {"close": float(r[2]),
                             "open": op if (op and op > 0) else None}
            except ValueError:
                pass
    if out and cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, f"{bs_code}.json"), "w", encoding="utf-8") as f:
            json.dump([{"date": k, "open": v["open"], "close": v["close"]}
                       for k, v in sorted(out.items())], f)
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


# ── 前向收益（2026-09-20 口径改造，主人拍板「改动①」）──
# 旧口径缺陷：p0 = kline[dates[i]]（信号日收盘）→ 前视偏差 + 零成本。
# 新口径：T 日信号 → T+1 开盘买入 → T+1+h 开盘卖出，扣 COST_ROUND_TRIP_PCT。
_FALLBACK_STAT = {"next_open": 0, "close_fallback": 0, "too_short": 0, "no_entry": 0}


def closes_of(kline):
    """从 {date:{"close":c,"open":o}} 取升序收盘价列表（P4 因子/残差动量用）。
    🔴 口径统一助手：全脚本只此一处把 K 线字典转成价格序列，避免散落 `kline[d]`。"""
    if not kline:
        return []
    return [kline[d]["close"] for d in sorted(kline.keys())]


def dates_of(kline):
    return sorted(kline.keys())


def _px(rec, field):
    """从 {date:{"close":c,"open":o}} 记录取价；open 缺失回退 close（并记账）"""
    if rec is None:
        return None
    v = rec.get(field)
    if v is None or v <= 0:
        if field == "open":
            v = rec.get("close")
            if v is not None and v > 0:
                _FALLBACK_STAT["close_fallback"] += 1
                return float(v)
        return None
    return float(v)


def forward_return(kline, date, h, cost_pct=None):
    """前向收益(%)。

    默认口径（ENTRY_MODE="next_open"）：
      入场 = 信号日 T 的**下一个交易日**开盘价（T+1 open）
      出场 = 从 T+1 起再数 h 个交易日的开盘价（T+1+h open）
      收益 = (出场/入场 - 1)*100 - cost_pct
    回退口径（LEGACY_ENTRY=True）：入场=出场基准均为 T 日收盘价，零成本（旧行为）。

    🔴「未到期写 null」：前端还未走完 h 个交易日的样本一律返回 None（旧版返回 None 但
      上层用 0 兜底填充，等效于「零收益样本」污染均值；本版由上层显式区分 None 与 0）。
    """
    if not kline or date not in kline:
        return None
    cost = COST_ROUND_TRIP_PCT if cost_pct is None else cost_pct
    dates = sorted(kline.keys())
    try:
        i = dates.index(date)
    except ValueError:
        return None

    if LEGACY_ENTRY:
        j = i + h
        if j >= len(dates):
            return None
        p0 = _px(kline.get(dates[i]), "close")
        p1 = _px(kline.get(dates[j]), "close")
        if not p0 or not p1:
            return None
        return (p1 - p0) / p0 * 100.0

    # 新口径：T+1 开盘入场
    e = i + 1
    if e >= len(dates):
        _FALLBACK_STAT["too_short"] += 1
        return None
    p0 = _px(kline.get(dates[e]), "open")
    if not p0:
        _FALLBACK_STAT["no_entry"] += 1
        return None
    _FALLBACK_STAT["next_open"] += 1
    j = e + h
    if j >= len(dates):
        _FALLBACK_STAT["too_short"] += 1
        return None
    p1 = _px(kline.get(dates[j]), "open")
    if not p1:
        return None
    return (p1 - p0) / p0 * 100.0 - cost


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
    _sc, _mc = closes_of(kline), closes_of(mkt_kline)
    _smap = dict(zip(kd, _sc))
    _mmap = dict(zip(md, _mc))
    pairs = [(_smap[d], _mmap[d]) for d in dates if d in _smap and d in _mmap]
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
def aggregate(snapshots, kline_fn, mkt_kline=None, regime_series=None, valid_codes=None,
              is_dates=None, oos_dates=None):
    """
    snapshots: [(date, [stock,...])]
    kline_fn(code, market) -> {date:{"close":c,"open":o}} or None
    mkt_kline: {date:...} 上证指数（P4 因子用）；None 则 P4 因子跳过
    regime_series: {date: regime}（P4 门控诊断用）；空则跳过
    valid_codes: 有效A股参考集（噪声闸门）；None 回退全量计入
    is_dates / oos_dates: IS/OOS 日期集合（改动③ 分段统计用）；None 则不分段
    返回 (by_signal, by_factor, coverage, by_regime, by_factor_raw, fac_is, fac_oos)
    """
    _is_dates = is_dates or set()
    _oos_dates = oos_dates or set()
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
    # IS/OOS 分段原始池（改动③）：与 by_factor 同构，供 build_excess 分段算超额
    by_factor_is = {f: {h: {"on": [], "off": []} for h in HORIZONS} for f in factor_defs}
    by_factor_oos = {f: {h: {"on": [], "off": []} for h in HORIZONS} for f in factor_defs}

    # P4 因子桶（需要 kline+mkt，惰性计算并缓存 per (code,date)）
    p4_defs = {}
    if mkt_kline:
        p4_defs = {
            "p4_lowvol45": lambda closes, i, kd: (realized_vol_pct(closes, i, 20) or 999) <= 45,
            "p4_lowvol55": lambda closes, i, kd: (realized_vol_pct(closes, i, 20) or 999) <= 55,
        }
    by_factor.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_defs})
    for _d in (by_factor_is, by_factor_oos):
        _d.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_defs})

    # 残差动量：连续值，分档布尔（>5 / >10 / <-5 弱化桶）
    resid_cache = {}
    p4_resid_defs = {
        "p4_resid5": lambda r: (r is not None) and (r > 5),
        "p4_resid10": lambda r: (r is not None) and (r > 10),
    }
    by_factor.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_resid_defs})
    for _d in (by_factor_is, by_factor_oos):
        _d.update({f: {h: {"on": [], "off": []} for h in HORIZONS} for f in p4_resid_defs})

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
                    closes = closes_of(kline)
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
                # IS/OOS 分段（2026-09-20 改动③）
                _seg = (by_factor_is if date in _is_dates else
                        (by_factor_oos if date in _oos_dates else None))
                for f, on in fflags.items():
                    if f not in by_factor:
                        continue
                    by_factor[f][h]["on" if on else "off"].append(ret)
                    if _seg is not None:
                        _seg[f][h]["on" if on else "off"].append(ret)
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

    return sig_out, fac_out, coverage, reg_out, by_factor, by_factor_is, by_factor_oos


# ════════════════════════════════════════════════════════════════
# 4.5 超额基准基准线（2026-09-20 改动④：下架判据改「超额」）
# --------------------------------------------------------------
# 旧判据用「绝对收益 edge」⇒ 长持有期档被大盘 β 撑高（T+10 全线飘红实为 β 假象）。
# 新判据：每笔样本收益 − 同期「全样本基线均值」（= 该 T+h 档位所有样本的平均收益，
#   即市场/池子 β 的代理），得到 excess 超额。以超额排源、以超额判下架。
# ════════════════════════════════════════════════════════════════
def _split_is_oos(snapshots, is_ratio=0.6):
    """按时间顺序切 IS（样本内）/ OOS（样本外）。返回 (is_dates_set, oos_dates_set)。"""
    n = len(snapshots)
    k = int(round(n * is_ratio))
    k = max(1, min(n - 1, k)) if n >= 2 else n
    is_set = set(d for d, _ in snapshots[:k])
    oos_set = set(d for d, _ in snapshots[k:])
    return is_set, oos_set


def _baseline_by_h(bucket_map, h):
    """给定 {key: [ret,...]} 求全样本均值（基准线）"""
    allr = []
    for rs in bucket_map.values():
        allr.extend(rs)
    return mean(allr)


def _all_on_off_returns(fac_raw):
    """把 {f: {h: {"on":[...], "off":[...]}}} 展平成 {f: {h: [...]}}（全样本池）"""
    pools = {}
    for f, hd in (fac_raw or {}).items():
        pools[f] = {}
        for h, d in (hd or {}).items():
            pools[f][h] = list(d.get("on") or []) + list(d.get("off") or [])
    return pools


def build_excess(fac_out, fac_raw, fac_is, fac_oos, horizons=None):
    """给 by_factor 补「超额」口径字段（改动④）：

      excess{h}      = ret_on{h} − baseline{h}   baseline = 该 T+h 档全样本均值（β代理）
      excess_is{h}   = IS 段在场均值 − IS 段全样本均值
      excess_oos{h}  = OOS 段在场均值 − OOS 段全样本均值
      verdict        = keep / watch / drop（按 T+5 超额，见 classify_verdict）
    """
    horizons = horizons or HORIZONS
    pools = _all_on_off_returns(fac_raw)
    out = {}
    for f, rec in (fac_out or {}).items():
        r = dict(rec)
        r["baseline"] = {}
        for h in horizons:
            pool = (pools.get(f) or {}).get(h) or []
            base = mean(pool)
            r["baseline"][f"{h}"] = round(base, 3)
            ret_on = rec.get(f"ret_on{h}")
            r[f"excess{h}"] = round(ret_on - base, 3) if ret_on is not None else None
        r["excess_is"] = _seg_excess(fac_is, f, horizons)
        r["excess_oos"] = _seg_excess(fac_oos, f, horizons)
        ex5 = r.get("excess5")
        r["verdict"] = classify_verdict(ex5, rec.get("n_on5"), rec.get("edge5"))
        r["verdict_basis"] = ("T+5 超额 (excess5=%.3f, n_on5=%s) 阈值 ±0.30pp；样本<30 一律 watch"
                              % (ex5 if ex5 is not None else float("nan"), rec.get("n_on5")))
        out[f] = r
    return out


def _seg_excess(fac_seg, f, horizons):
    """分段（IS/OOS）在场超额：在场均值 − 该段全样本均值"""
    seg = (fac_seg or {}).get(f)
    if not seg:
        return None
    res = {}
    for h in horizons:
        on = seg.get(h, {}).get("on") or []
        off = seg.get(h, {}).get("off") or []
        if not on:
            res[f"{h}"] = None
            continue
        res[f"{h}"] = round(mean(on) - mean(on + off), 3)
    return res


def classify_verdict(excess5, n_on5, exedge5=None):
    """下架判据（2026-09-20 改动④）：以 T+5 超额为准。
      excess5 >= +0.30pp 且 n>=30  → keep   保留
      -0.30 < excess5 < +0.30      → watch  观察
      excess5 <= -0.30pp           → drop   候选下架
    样本不足(<30) 一律 watch（不得据薄样本下架）。
    """
    if excess5 is None or (n_on5 or 0) < 30:
        return "watch"
    if excess5 >= 0.30:
        return "keep"
    if excess5 <= -0.30:
        return "drop"
    return "watch"


# ════════════════════════════════════════════════════════════════
# 5. 自检（合成数据）
# ════════════════════════════════════════════════════════════════
def selftest():
    print("=== 自检：收缩 / 胜率 / 期望 / P4 / 新口径 ===")
    rs = [5.0, 5.0, 5.0]
    n = len(rs)
    assert abs(shrink_win(win_rate(rs), n) - (50 + (100 - 50) * n / (n + SHRINK_K))) < 1e-6
    assert abs(shrink(mean(rs), n) - (5.0 * n / (n + SHRINK_K))) < 1e-6
    big = [5.0] * 200
    assert abs(shrink(mean(big), 200) - 5.0 * 200 / (200 + SHRINK_K)) < 1e-6
    assert abs(win_rate([1.0, -1.0, 0.0]) - 100 / 3) < 1e-6

    # ── 口径自检（2026-09-20 改动①）────────────────────────────
    def mk(rows):
        """rows: [(date, open, close)] → 新结构 K 线"""
        return {d: {"close": c, "open": o} for d, o, c in rows}

    kl = mk([("2026-01-01", 99.0, 100.0), ("2026-01-02", 110.0, 111.0),
             ("2026-01-03", 121.0, 122.0), ("2026-01-04", 121.0, 121.0)])
    if LEGACY_ENTRY:
        # 旧口径：T 收盘 → T+h 收盘，零成本
        assert abs(forward_return(kl, "2026-01-01", 1) - 10.0) < 1e-6, "旧口径 T+1 应为 +10%"
    else:
        # 新口径：T+1 开盘(110) → T+1+1 开盘(121) = +10%，再扣 0.2% 成本
        r = forward_return(kl, "2026-01-01", 1)
        assert abs(r - (10.0 - COST_ROUND_TRIP_PCT)) < 1e-6, f"新口径 T+1 应={10-COST_ROUND_TRIP_PCT}, 实={r}"
        # 🔴 未到期必须 None（不得用 0 冒充）
        assert forward_return(kl, "2026-01-01", 10) is None, "未到期应返回 None"
        assert forward_return(kl, "2026-01-03", 1) is None, "序列尾端未到期应返回 None"
        # 成本确实被扣（与零成本对照）
        r0 = forward_return(kl, "2026-01-01", 1, cost_pct=0.0)
        assert abs((r0 - r) - COST_ROUND_TRIP_PCT) < 1e-9, "成本未按 round-trip 扣除"
        # open 缺失回退 close
        kl_noopen = {"2026-01-01": {"close": 100.0, "open": None},
                     "2026-01-02": {"close": 110.0, "open": None},
                     "2026-01-03": {"close": 121.0, "open": None}}
        r2 = forward_return(kl_noopen, "2026-01-01", 1)
        assert r2 is not None and abs(r2 - (10.0 - COST_ROUND_TRIP_PCT)) < 1e-6, f"缺 open 应回退 close: {r2}"
    # closes_of 口径统一助手
    assert closes_of(kl) == [100.0, 111.0, 122.0, 121.0], "closes_of 应取升序收盘"
    assert closes_of(None) == []

    # P4：恒定价格 → 波动率 0 → lowvol True；残差 = 个股收益 − β×市场收益
    # 合成 90 个交易日（est=60 + window=20 需要足量历史）
    import datetime as _dt
    _dates = []
    _d = _dt.date(2026, 1, 1)
    while len(_dates) < 90:
        if _d.weekday() < 5:
            _dates.append(_d.isoformat())
        _d += _dt.timedelta(days=1)
    flat = {d: {"close": 100.0, "open": 100.0} for d in _dates}
    assert realized_vol_pct(closes_of(flat), len(flat) - 1, 20) == 0.0
    up_mkt = {d: {"close": 100.0 + i, "open": 100.0 + i} for i, d in enumerate(_dates)}
    rm = resid_momentum_pct(flat, _dates[-1], up_mkt)
    assert rm is not None and rm < 0, f"平价股对上涨市场残差应为负: {rm}"
    snap = [("2026-01-01", [{"code": "600000", "market": "sh",
                             "signals": {"chan": True, "jinzuan": False, "jigou": True, "trend": True},
                             "score_fund": 5, "score_sector": 0, "score_quality": 3}])]
    _pre = {f"2025-12-{d:02d}": {"close": 90.0 + d, "open": 90.0 + d} for d in range(1, 32)}
    sig, fac, cov, reg, _raw, _is, _oos = aggregate(
        snap, lambda c, m: {**kl, **_pre},
        mkt_kline=None, regime_series={"2026-01-01": "grind"},
        is_dates={"2026-01-01"}, oos_dates=set())
    if LEGACY_ENTRY:
        assert abs(sig["1,0,1,1"]["ret3"] - round(21.0 / (1 + SHRINK_K), 3)) < 1e-6
    else:
        # T+1 开盘 110 → 需再数 3 个交易日，合成K线不足 ⇒ 该样本不成立
        # 注意：样本被 None 淘汰后，by_signal 里根本不会产生该 key（这正是「未到期不计入」的体现）
        assert "1,0,1,1" not in sig, f"新口径下样本不足不应产出该组合: {list(sig.keys())}"
        assert cov["occ_total"] == 0, f"新口径下有效样本应为 0, 实={cov['occ_total']}"
    assert "p4_lowvol25" not in fac, "无市场K线时 P4 因子应跳过"
    # 门控分桶：旧口径（T日收盘）下 2026-01-01 有 T+3 样本；新口径需 T+1 入场+再走 h 日，
    # 合成K线不足 ⇒ 门控桶应为 0（这本身即「未到期不计入」的验证）
    if LEGACY_ENTRY:
        assert reg["gate_open"]["n3"] == 1 and reg["gate_open"]["n10"] == 0, "门控分桶错（合成K线仅够T+3）"
    else:
        assert reg["gate_open"]["n3"] == 0, f"新口径下门控桶应为 0, 实={reg['gate_open']['n3']}"

    # ── 正向端到端：足够长的合成 K 线，验证「次日开盘」真的被用作入场价 ──
    import datetime as _dt2
    _ds = []
    _x = _dt2.date(2026, 3, 2)
    while len(_ds) < 30:
        if _x.weekday() < 5:
            _ds.append(_x.isoformat())
        _x += _dt2.timedelta(days=1)
    # 构造：close 恒为 open*1.01，open 每日 +2%（日线口径下 open/close 可追溯）
    klong, px = {}, 100.0
    for d in _ds:
        klong[d] = {"open": px, "close": px * 1.01}
        px *= 1.02
    sigL = [(_ds[0], [{"code": "600000", "market": "sh",
                       "signals": {"chan": True, "jinzuan": True, "jigou": False, "trend": False},
                       "score_fund": 0, "score_sector": 0, "score_quality": 0}])]
    sL, fL, cL, rL, rawL, isL, oosL = aggregate(sigL, lambda c, m: klong,
                                                mkt_kline=None, regime_series={},
                                                is_dates={_ds[0]}, oos_dates=set())
    key = "1,1,0,0"
    assert key in sL, f"正向用例应产出组合 {key}: {list(sL.keys())}"
    # 入场 = _ds[1].open = 102.0，出场(h=3) = _ds[4].open = 102*1.02^3
    # 收益 = (1.02^3 - 1)*100 - 成本
    exp = ((1.02 ** 3) - 1) * 100.0 - COST_ROUND_TRIP_PCT
    # 🔴 反收缩还原：ret = round(shrink(mean,n),3)，其中 shrink = mean * n/(n+k)
    n3 = sL[key]["n3"]
    got = sL[key]["ret3"] / (n3 / (n3 + SHRINK_K))   # 还原为原始均值
    assert abs(got - exp) < 1e-2, f"次日开盘口径收益不符: 期望≈{exp:.4f}, 反收缩还原={got:.4f} (n3={n3})"
    # 超额口径字段在位（须先过 build_excess —— 与 main() 同一路径）
    # 注意：fac 的 key 是因子名（sig_jinzuan 等），不是信号组合 key
    fL2 = build_excess(fL, rawL, isL, oosL)
    fk = "sig_jinzuan"
    assert fk in fL2, f"by_factor 应含 {fk}: {list(fL2.keys())}"
    assert "excess5" in fL2[fk] and "verdict" in fL2[fk], "应产出 excess/verdict 字段"
    assert "excess_is" in fL2[fk] and "excess_oos" in fL2[fk], "应产出 IS/OOS 分段超额"
    assert fL2[fk]["verdict"] in ("keep", "watch", "drop"), f"verdict 取值非法: {fL2[fk]['verdict']}"
    assert fL2[fk]["excess5"] is not None, "excess5 不应为 None（该因子有在场样本）"
    assert isinstance(fL2[fk]["baseline"], dict), "应输出 baseline 基准线"
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
    is_dates, oos_dates = _split_is_oos(snapshots)
    print(f"   IS/OOS 切分: IS={len(is_dates)}天 / OOS={len(oos_dates)}天"
          f"  IS末={max(is_dates) if is_dates else '-'}  OOS首={min(oos_dates) if oos_dates else '-'}")
    sig, fac, cov, reg, fac_raw, fac_is, fac_oos = aggregate(
        snapshots,
        lambda code, market: get_kline(code, market, args.kline_cache, args.use_baostock),
        mkt_kline=mkt,
        regime_series=regime_series,
        valid_codes=valid_codes,
        is_dates=is_dates,
        oos_dates=oos_dates,
    )
    # 超额口径 + 下架判据（改动④）
    fac = build_excess(fac, fac_raw, fac_is, fac_oos)

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
            # ── 口径元信息（2026-09-20 改动①②③④，可审计）──
            "entry_mode": ENTRY_MODE,
            "entry_note": ("次日开盘成交（T+1 open）：信号由 T 日收盘数据算出，最早只能 T+1 开盘买入；"
                           "旧版用 T 日收盘价成交属前视偏差，已废弃"
                           if not LEGACY_ENTRY else "旧口径：T 日收盘成交（仅供新旧对比，勿用于决策）"),
            "cost_round_trip_pct": COST_ROUND_TRIP_PCT,
            "cost_note": "双边总成本（印花税+佣金+滑点），已从每笔样本收益中扣除",
            "is_oos": {
                "is_ratio": 0.6,
                "is_dates": len(is_dates), "oos_dates": len(oos_dates),
                "is_range": [min(is_dates), max(is_dates)] if is_dates else None,
                "oos_range": [min(oos_dates), max(oos_dates)] if oos_dates else None,
                "note": "按时间顺序切分；OOS 段结论才是可外推的",
            },
            "downrank_basis": "T+5 超额（excess5）阈值 ±0.30pp，样本<30 一律 watch",
            "entry_fallback_stat": dict(_FALLBACK_STAT),
            "note": ("P4 版 + 次日开盘/扣成本/IS-OOS/超额判据（2026-09-20 口径改造）："
                     "含低波/残差动量因子与漂移门控诊断（sh.000001 市场代理）+ 噪声代码闸门"),
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
    print(f"   口径: entry={ENTRY_MODE} 成本={COST_ROUND_TRIP_PCT}%  "
          f"IS/OOS={len(is_dates)}/{len(oos_dates)}天")
    print(f"   信号组合数: {len(sig)} | 因子数: {len(fac)}")
    print(f"   覆盖: 股票{nev(cov,'stocks_total')} / 有K线{nev(cov,'with_kline')} / 有效样本{nev(cov,'occ_total')} / P4评估{nev(cov,'p4_evaluated')}")
    print(f"   剔除源噪声脏码(出现次数): {nev(cov,'excluded_garbage')}")
    print(f"   部分数据: {out['meta']['partial']}")
    print(f"   入场回退统计: {_FALLBACK_STAT}")
    print("   ── 因子超额速览（改动④：按 T+5 超额排序，判据 ±0.30pp）──")
    _rows = sorted(((f, r.get("excess5"), r.get("excess3"), r.get("excess10"),
                     r.get("n_on5"), r.get("verdict")) for f, r in fac.items()),
                   key=lambda x: (x[1] if x[1] is not None else -999), reverse=True)
    print(f"   {'因子':<14}{'ex3':>8}{'ex5':>8}{'ex10':>8}{'n_on5':>7}  判定")
    for f, e5, e3, e10, n5, vd in _rows:
        def _fm(v):
            return f"{v:+.3f}" if isinstance(v, (int, float)) else "  -"
        print(f"   {f:<14}{_fm(e3):>8}{_fm(e5):>8}{_fm(e10):>8}{str(n5):>7}  {vd}")
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
