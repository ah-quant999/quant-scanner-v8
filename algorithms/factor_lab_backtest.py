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
  K 线历史 — 用 mootdx/东财/baostock 拉 700 交易日长历史
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
OUT_JSON = os.path.join(RAW, "factor_lab_backtest.json")

COST = 0.0020          # 往返成本
BASELINE = 240         # 量比基线窗口（前12月 ≈ 240 交易日）
RECENT = 20            # 当月窗口
STEP = 10              # 调仓间隔（交易日）
# 🔴 2026-09-14 主人令（图3「这个也要按图4这个模式写」）：持有期档位扩展为
#   与「四量终极」同档（T+1 … T+250），使因子卡能展示完整「持有期档位表」。
#   实现铁律 = **按档取用**：某档因 K 线历史不足算不出，就只跳过该档，
#   绝不让它拖累其余档 —— 某档样本数单独统计（n_{h}d），
#   也绝不拿短档的样本数冒充长档（旧版 `any(v is None) -> 整点丢弃` 会让
#   T+250 反过来把 T+1..T+20 的样本一起废掉，属于典型的「长档拖死短档」）。
HOLDS = [1, 3, 5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
MIN_HOLD = min(HOLDS)
NEED_MIN = BASELINE + RECENT + 1   # 参与分层的最少历史
# 🔴 2026-09-15 主人令（图2「那就去获取761根，拿不到就写累积中，直到累积到为止」）：
#   761 = NEED_MIN(261) + 2×250 —— 最长档 T+250 需要「预热段 + 持有段 + 末根余量」。
#   FETCH_DAYS 取 800（留 39 根余量），使 T+250 档也能有足够调仓点参与分层。
#   仍拿不到的票（次新股）**不许静默 0 样本** —— 由 `_hold_status()` 逐档标记
#   「累积中」，并随交易日推移自然累积到满足 MIN_BARS 为止。
MIN_BARS = NEED_MIN + 2 * max(HOLDS)          # = 761
FETCH_DAYS = 800       # 拉取长历史（≈ 38 个月，覆盖 MIN_BARS 并留余量）

sys.path.insert(0, BASE)

# 🛡 2026-09-15：复用 strong_breakout.py 的 `_fetch_kline`（gtimg 主源 → 新浪兜底，
# 双域名级故障转移）作为长历史主源 —— 该实现已在盘后链稳定运行，不另造第三条取数路径。
from strong_breakout import _fetch_kline as _fetch_hist  # noqa: E402


# ── 🛡 2026-09-15 小九的工程师：补回整层「取数层」─────────────────────────────
# 本脚本自 2026-09-04 上线起**从未跑通过**：CACHE_DIR / _query_kline / _load_cache
# 三个名字被引用却从未定义 ⇒ 一进 main() 即 NameError 秒退（2026-09-15 08:56 实测复现），
# raw_data/factor_lab_backtest.json 永远停在旧值 → data/FACTOR_LAB_BACKTEST.js 陈旧
# → 运维面板常驻红灯「更新于 3 天前」。
# 修法：直接复用已在稳定运行的 alpha101_backtest.py 同源实现（双源缓存，云端零网络可取），
# 不再自造网络拉取路径 —— 本仓「云端 runner 无外网」的现实下那条路本就不成立。
# 注：原本想复用 alpha101_backtest.py 的实现，但它的
#   `from calc_stock_rps import _load_cache_raw` 指向的模块**已随 RPS 下线从全仓删除**
#   （远端 ls-tree 亦无）⇒ 复用等于换个坑再摔一次。故这里做成**自包含**：
#   纯 json、零第三方依赖、零网络。
CACHE_DIR = os.path.join(RAW, "_rps_cache")
KLINE_CACHE_DIR = os.path.join(RAW, "kline_cache")


def _read_cache_file(path):
    """读单个 K 线缓存文件 → records list（按 date 升序）或 None。

    兼容两种落盘形状：纯 list[dict]，或 dict 包一层（bars/data/rows）。
    最小字段 date/open/close；high/low/volume/amount 缺失时安全降级。
    """
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return None
    if isinstance(rows, dict):
        rows = rows.get("bars") or rows.get("data") or rows.get("rows") or []
    if not isinstance(rows, list) or len(rows) < 60:
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            o = float(r["open"]); c = float(r["close"])
        except Exception:
            continue
        d = str(r.get("date") or r.get("day") or r.get("trade_date") or "")[:10]
        if not d or c <= 0:
            continue
        try:
            h = float(r["high"])
        except Exception:
            h = max(o, c)
        try:
            low = float(r["low"])
        except Exception:
            low = min(o, c)
        try:
            v = float(r["volume"])
        except Exception:
            v = 0.0
        try:
            amt = float(r["amount"])
        except Exception:
            amt = c * v * 100.0
        out.append({"date": d, "open": o, "high": h, "low": low, "close": c,
                    "volume": v, "amount": amt})
    if len(out) < 60:
        return None
    out.sort(key=lambda x: x["date"])
    return out


def _load_cache_any(code):
    """本地 K 线读取（双源，按可用性自动选择）。与 alpha101_backtest.py 同源同口径。

    ① raw_data/_rps_cache/ —— 长历史 + 真实 amount（.gitignore:39 忽略，云端会被
       actions/checkout 的 git clean -ffdx 清掉 ⇒ **不能作为唯一源**）。
    ② raw_data/kline_cache/ —— **已入仓 · 云端零网络可取**（3000+ 只）。

    返回 records list（date/open/high/low/close/volume/amount）或 None。
    """
    for _d in (CACHE_DIR, KLINE_CACHE_DIR):
        _p = os.path.join(_d, "%s.json" % code)
        if os.path.exists(_p):
            _recs = _read_cache_file(_p)
            if _recs:
                return _recs
    return None


def _net_kline_records(code):
    """网络长历史（700 日）→ records list；不可达则 None。

    复用 algorithms/strong_breakout.py 的 `_fetch_kline`（gtimg 主源 → 新浪兜底，
    双域名级故障转移，已在盘后链稳定运行）——不另造第三条取数路径。
    返回行序为 [date, open, close, high, low, volume]（前复权）。
    """
    try:
        k = _fetch_hist(code, FETCH_DAYS)
    except Exception:
        return None
    if not k or len(k) < 60:
        return None
    out = []
    for row in k:
        try:
            d = str(row[0])[:10]
            o = float(row[1]); c = float(row[2])
            h = float(row[3]); low = float(row[4]); v = float(row[5])
        except Exception:
            continue
        if not d or c <= 0:
            continue
        out.append({"date": d, "open": o, "high": h, "low": low, "close": c,
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
    """网络长历史为主、本地缓存兜底。返回 {code: rows}，rows 按 date 升序。

    🛡 2026-09-15：原实现调用的 _query_kline / _load_cache 从未定义（NameError → 全链秒退，
    该脚本自 09-04 上线起从未产出过），现按原设计意图补齐：
      ① 网络 700 日（gtimg→新浪，复用 strong_breakout._fetch_kline）——保证样本深度；
      ② 失败回落本地缓存（_rps_cache → kline_cache）——保证云端/断网时不空手而归。
    只读缓存会让样本深度掉到 251 日（NEED_MIN=261 都过不了），分层只剩个位数调仓点，
    等于用「能跑」换「不算数」，故网络仍是主源。
    """
    out, n_net, n_cached, n_fail = {}, 0, 0, 0
    t0 = time.time()

    def _work(code):
        recs = _net_kline_records(code)
        if recs:
            return code, recs, "net"
        recs = _load_cache_any(code)
        if recs:
            return code, recs, "cache"
        return code, None, "fail"

    _log(f"[kline] 拉取 {len(codes)} 只 x {FETCH_DAYS} 日（{workers} 线程，失败回落本地缓存）...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_work, c): c for c in codes}
        for i, fut in enumerate(as_completed(futs), 1):
            code, recs, how = fut.result()
            if recs:
                out[code] = sorted(recs, key=lambda r: r["date"])
                if how == "net":
                    n_net += 1
                else:
                    n_cached += 1
            else:
                n_fail += 1
            if i % 200 == 0 or i == len(codes):
                _log(f"[kline] {i}/{len(codes)} 完成（网络{n_net}/缓存{n_cached}/失败{n_fail}，"
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


def _layer_stats(samples_by_layer, dates_by_layer, holds=None):
    """samples_by_layer: {layer: {hold: [ret,...]}}；返回每层统计 + hold=10 净值回撤。

    🔴 2026-09-15 主人令：`holds` 传入完整档位后，**缺数据的档也显式输出
    `n_{h}d=0` 与 `win/avg/best/worst_{h}d=null`**。两个作用：
      ① 「本档无数据」被诚实表达为 null（不是 0，更不是拿短档样本冒充）；
      ② 前端档位表是**动态发现** `win_Nd` 键的 ⇒ 显式 null 键让该档仍出现在
         表里，从而能显示「累积中」，而不是整档消失、让人误以为没有这档。
    """
    out = {}
    for layer in sorted(samples_by_layer):
        per = samples_by_layer[layer]
        stat = {"n": len(dates_by_layer.get(layer, []))}
        for h in (holds if holds else sorted(per)):
            rets = [r for r in per.get(h, []) if r is not None]
            if not rets:
                stat[f"n_{h}d"] = 0
                stat[f"win_{h}d"] = None
                stat[f"avg_{h}d"] = None
                stat[f"best_{h}d"] = None
                stat[f"worst_{h}d"] = None
                continue
            stat[f"avg_{h}d"] = round(sum(rets) / len(rets) * 100, 3)
            stat[f"win_{h}d"] = round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1)
            # 🔴 2026-09-14：每档各自样本数 + 最佳/最差 —— 前端「持有期档位表」需要，
            #   且各档样本数必须独立统计（长档因 K 线不足天然更少，不能共用 n）。
            stat[f"n_{h}d"] = len(rets)
            stat[f"best_{h}d"] = round(max(rets) * 100, 3)
            stat[f"worst_{h}d"] = round(min(rets) * 100, 3)
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


def _hold_status(klines, layers=None):
    """各持有期的「数据就绪度」——拿不到就写累积中，禁静默 0 样本。

    🔴 2026-09-15 主人令：「那就去获取 761 根，拿不到就写累积中，直到累积到为止。」

    need_bars(h) = NEED_MIN + 2×h
      预热 261 根（BASELINE 240 + RECENT 20 + 1）
      ＋ 持有段 h 根（信号日次一交易日开盘买入 → 第 h 个交易日收盘卖出）
      ＋ 末段 h 根余量（保证最后一个调仓点也能算完整收益）

    layers：`_layer_stats()` 的输出（{layer: {"n_{h}d": N, ...}}），用于累计该档实际样本数。
    判据：可用票 < 25（凑不出 5 层 × 5 只）或该档零样本 ⇒ accumulating。
    返回 (holds_detail, n_accumulating)。
    """
    lens = sorted(len(r) for r in klines.values())
    n_stock = len(lens)
    max_bars = lens[-1] if lens else 0
    detail, n_acc = {}, 0
    for h in HOLDS:
        need = NEED_MIN + 2 * h
        ready = sum(1 for x in lens if x >= need)
        n_samp = 0
        for _per in (layers or {}).values():
            if isinstance(_per, dict):
                v = _per.get("n_%dd" % h)
                if isinstance(v, int):
                    n_samp += v
        st = "ready" if (ready >= 25 and n_samp > 0) else "accumulating"
        if st == "accumulating":
            n_acc += 1
        detail["%dd" % h] = {
            "need_bars": need,
            "stocks_ready": ready,
            "stocks_total": n_stock,
            "max_bars_available": max_bars,
            "samples": n_samp,
            "status": st,
        }
    return detail, n_acc


def backtest_abn(klines, workers_note=""):
    """异常量比因子全池五分位分层回测。"""
    # 预计算每票每个调仓点的因子值与未来收益
    factor_at = {}   # {t: {code: factor}}
    rets_at = {}     # {t: {code: {hold: ret}}}
    for code, rows in klines.items():
        n = len(rows)
        if n < NEED_MIN + 2 * MIN_HOLD:
            continue
        for t in range(BASELINE + RECENT - 1, n - 1 - MIN_HOLD, STEP):
            f = _abn_factor_at(rows, t)
            if f is None:
                continue
            # 按档取用：只保留算得出的档，缺档跳过而非整点丢弃
            rets = {}
            for _h in HOLDS:
                _v = _net_ret(rows, t, _h)
                if _v is not None:
                    rets[_h] = _v
            if not rets:
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
    layers = _layer_stats(samples, dates_by_layer, HOLDS)

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
        if n < NEED_MIN + 2 * MIN_HOLD:
            continue
        for t in range(BASELINE + RECENT - 1, n - 1 - MIN_HOLD, STEP):
            # 按档取用：只保留算得出的档，缺档跳过而非整点丢弃
            rets = {}
            for _h in HOLDS:
                _v = _net_ret(rows, t, _h)
                if _v is not None:
                    rets[_h] = _v
            if not rets:
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
        stat[f"top30_n_{h}d"] = len(b)
        stat[f"top30_best_{h}d"] = round(max(b) * 100, 3)
        stat[f"top30_worst_{h}d"] = round(min(b) * 100, 3)
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
    # universe 目录：优先 _rps_cache（长历史，本机离线）；否则 kline_cache（已入仓·云端可取）。
    # 🛡 2026-09-15：原实现只认 CACHE_DIR 且只判 isdir —— 该目录被 gitignore、云端清空后
    #   仍然是「存在的空目录」，会走到 codes 为空再 sys.exit(1)，根因被掩盖成「无 universe」。
    #   改为按**实际含 A股 6 位码 json** 逐目录探测，取第一个可用者。
    def _uni_codes(d):
        try:
            return sorted(f[:-5] for f in os.listdir(d)
                          if f.endswith(".json") and _is_a6(f[:-5]))
        except Exception:
            return []

    uni_dir, codes = None, []
    for _d in (CACHE_DIR, KLINE_CACHE_DIR):
        _cs = _uni_codes(_d)
        if _cs:
            uni_dir, codes = _d, _cs
            break
    if not codes:
        _log(f"[error] universe 缓存目录均无 A股 6 位码数据: {CACHE_DIR} / {KLINE_CACHE_DIR}")
        sys.exit(1)
    _log(f"universe: {len(codes)} 只（重点池 A股，来自 {os.path.basename(uni_dir)}）")

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

    # 🔴 2026-09-15 主人令：逐档报「就绪 / 累积中」——
    #   拿不到 MIN_BARS(761) 根就写累积中，绝不静默 0 样本。
    hold_status, n_acc = _hold_status(
        klines, abn.get("layers") if isinstance(abn, dict) else None)
    _log("  档位就绪度: " + json.dumps(
        {k: ("就绪" if v["status"] == "ready"
             else "累积中（可用票 %d/%d）" % (v["stocks_ready"], v["stocks_total"]))
         for k, v in hold_status.items()}, ensure_ascii=False))
    if n_acc:
        _log("  ⏳ %d/%d 档处于累积中（需 %d 根 K 线，当前最长 %d 根）"
             % (n_acc, len(HOLDS), MIN_BARS, max(len(r) for r in klines.values())))

    _log("\n—— 因子2：ROE_TTM 大市值 Top30 vs 全池等权 ——")
    roe = backtest_roe(klines)
    _log(json.dumps({k: v for k, v in roe.items() if not isinstance(v, dict)},
                    ensure_ascii=False))

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # 🛡 2026-09-15（小九的工程师）：原为硬编码「（_rps_cache）」，
        #    但 _rps_cache 被 .gitignore 忽略且本机为空 ⇒ 实际走 kline_cache，
        #    文案与实际来源不符（数据口径失真）。改为回填实测目录名。
        "universe": "重点池 A股（%s）" % os.path.basename(uni_dir),
        "cost_roundtrip": COST,
        "rebalance": f"每{STEP}个交易日，入场=次日开盘",
        # 🔴 2026-09-15 主人令（图2）：「拿不到就写累积中，直到累积到为止」。
        #   本块是「累积进度账」：逐档给出 need_bars / 可用票数 / 实际样本数 / status。
        #   前端据此把无数据的档显示为「累积中」而非空表或 0。
        "data_accumulation": {
            "fetch_days": FETCH_DAYS,
            "min_bars_required": MIN_BARS,          # 761
            "universe_requested": len(codes),
            "stocks_loaded": len(klines),
            "coverage_pct": round(100.0 * len(klines) / max(1, len(codes)), 1),
            "max_bars_available": (max(len(r) for r in klines.values()) if klines else 0),
            "accumulating_holds": n_acc,
            "holds_total": len(HOLDS),
            "status": "accumulating" if n_acc else "ready",
            "holds": hold_status,
            "note": ("拿不到足够 K 线的票（多为次新股）随时间自然累积；"
                     "本块即累积进度，拿不到即显示「累积中」，禁止以 0 冒充样本。"),
        },
        "abnormal_volume": abn,
        "roe_largecap": roe,
    }
    # 🛡 2026-09-15（小九的工程师）：显式 newline="\n"。
    #    Windows 文本模式下 open(...,"w") 默认把 \n 转成 CRLF，而本仓 raw_data/*.json
    #    与远端统一为 LF ⇒ 曾产出 488 处 CRLF，diff 出现 412/93 的假性大改。
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _log(f"\n[ok] 写入 {OUT_JSON}")


if __name__ == "__main__":
    main()
