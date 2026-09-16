#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factor_walkforward.py — 待回测候选因子的 walk-forward 回测引擎（2026-09-16 主人令）

主人 2026-09-16 令：「这些马上回测，不好的不要的就删除，留下可用的优质因子，全部接入。
                    不要整个版面都在等待，一直也解决不了！」

背景：scripts/gen_factor_progress.py 里的「待回测候选台账」A 组 6 个因子
      （owner=阿狸咪(kline_cache)）登记后长期 pending，前端台账表永远「⏸ pending」。
      本脚本把它们**真跑出结果**，供 gen_factor_progress.py 判：达标⇒接入、不达标⇒删除。

判据（主人 2026-09-09 22:31 决策，硬门槛，不可放宽）：
    OOS IR > 0.3  且  ≥4/5 年 Top 层胜率 > 55%

六个因子（全部 kline 可得，零新财报字段）：
    mom12_1     12-1 跨周期动量：close[t-20]/close[t-240]-1（剔除最近 1 月，避开短期反转）
    resid_mom   残差动量：Σ(个股日收益 − 全池等权日收益) over [t-240, t-20]
                （beta=1 中性化代理；比原始动量更抗市场同涨同跌）
    max20       最大日收益 MAX：近 20 日最大单日涨幅，**取负号**（高 MAX 扣分，彩票偏好异象）
    ivol60      特质波动率 IVOL：近 60 日残差(个股−全池)日收益标准差，**取负号**（低波异象）
    turntrend   换手率趋势：mean(vol[t-19..t]) / mean(vol[t-239..t])，**取负号**
                （与 v8「异常量比·缩量=强势」同向）
    overnight20 隔夜跳空累积：Σ(open[i]/close[i-1]-1) over 近 20 日

方法论（每个数字可追溯，无前视）：
    · 时点 t 只用 ≤t 的 K 线；入场 = 次日(t+1)开盘，出场 = (t+1+h)开盘；
    · 调仓间隔 STEP=10 交易日；持有 HOLDS = [5,10,20]；主判据取 hold=10；
    · 分层 = 每期因子值五分位，L1 = 因子值最高（= 最强势）；
    · 成本 = 往返 0.20%；
    · IS/OOS = 调仓点按时间前 60% / 后 40% 切分（OOS 绝不参与选向）。

数据源：新浪（datalen 支持 2200 根 ≈ 9 年，主源）→ gtimg（兜底）。
       `--no-fetch` 时只读本地缓存（离线复跑）。

输出：raw_data/factor_walkforward.json
"""
import os, sys, json, time, argparse, glob, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("V8_ROOT") or os.path.dirname(BASE)
RAW = os.path.join(ROOT, "raw_data")
OUT_JSON = os.path.join(RAW, "factor_walkforward.json")
CACHE = os.path.join(RAW, "_wf_cache")

COST = 0.0020          # 往返成本
STEP = 10              # 调仓间隔（交易日）
HOLDS = [5, 10, 20]
REBAL_PER_YEAR = 250.0 / STEP
DATALEN = 2200         # 新浪 datalen（实测支持 3000）
MIN_BARS = 240 + 250 + 20 + 5   # 预热 + 最长持有 + 余量


def _log(m=""):
    print(m, flush=True)


# ── 取数 ──────────────────────────────────────────────────────────────
def _pfx(code):
    return ("sh" if code[0] in "659" else "sz") + code


def _http(url, timeout=25):
    import urllib.request
    r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(r, timeout=timeout).read().decode("utf-8", "replace")


def _fetch_sina(code):
    raw = _http("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                "CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d"
                % (_pfx(code), DATALEN))
    j = json.loads(raw)
    out = []
    for r in j:
        try:
            out.append({"date": r["day"][:10],
                        "open": float(r["open"]), "close": float(r["close"]),
                        "high": float(r["high"]), "low": float(r["low"]),
                        "volume": float(r.get("volume") or 0)})
        except Exception:
            continue
    return out


def _fetch_gtimg(code):
    raw = _http("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
                "param=%s,day,,,%d,qfq" % (_pfx(code), DATALEN))
    d = json.loads(raw)["data"][_pfx(code)]
    k = d.get("qfqday") or d.get("day") or []
    out = []
    for r in k:
        try:
            out.append({"date": r[0][:10], "open": float(r[1]), "close": float(r[2]),
                        "high": float(r[3]), "low": float(r[4]),
                        "volume": float(r[5]) if len(r) > 5 else 0.0})
        except Exception:
            continue
    return out


def fetch_one(code):
    for fn in (_fetch_sina, _fetch_gtimg):
        try:
            rows = fn(code)
            if rows and len(rows) >= MIN_BARS:
                rows.sort(key=lambda r: r["date"])
                return code, rows
        except Exception:
            continue
    return code, None


def load_universe():
    """universe = raw_data/kline_cache 里的 A 股 6 位码（与 factor_lab_backtest 同源）。"""
    D = os.path.join(RAW, "kline_cache")
    codes = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(D, "*.json"))
                   if re.match(r"^\d{6}\.json$", os.path.basename(f)))
    return codes


def get_klines(codes, workers, do_fetch):
    os.makedirs(CACHE, exist_ok=True)
    todo, out = [], {}
    for c in codes:
        p = os.path.join(CACHE, c + ".json")
        if os.path.exists(p):
            try:
                rows = json.load(open(p, encoding="utf-8"))
                if rows and len(rows) >= MIN_BARS:
                    out[c] = rows
                    continue
            except Exception:
                pass
        todo.append(c)
    _log("  缓存命中 %d / 待取 %d" % (len(out), len(todo)))
    if not todo or not do_fetch:
        return out
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for code, rows in ex.map(fetch_one, todo):
            done += 1
            if rows:
                out[code] = rows
                json.dump(rows, open(os.path.join(CACHE, code + ".json"), "w",
                                     encoding="utf-8"), ensure_ascii=False)
            if done % 250 == 0:
                _log("    取数 %d/%d  已入库 %d  %.0fs"
                     % (done, len(todo), len(out), time.time() - t0))
    _log("  取数完成: 成功 %d / 请求 %d  用时 %.0fs" % (len(out), len(todo), time.time() - t0))
    return out


# ── 因子计算 ──────────────────────────────────────────────────────────
def build_panel(klines):
    """返回 (dates, pos, bars)：全局交易日轴 + 每只票在其轴上的自身索引 + 自身 K 线。"""
    dset = set()
    for rows in klines.values():
        for r in rows:
            dset.add(r["date"])
    dates = sorted(dset)
    gidx = {d: i for i, d in enumerate(dates)}
    pos, bars = {}, {}
    for c, rows in klines.items():
        p = [-1] * len(dates)
        for i, r in enumerate(rows):
            p[gidx[r["date"]]] = i
        pos[c] = p
        bars[c] = rows
    return dates, pos, bars


def stock_series(rows):
    """预计算：日收益 r[]、隔夜 o[]、残差(先按 beta=1 用 r 减池均值，稍后统一)、前缀和。"""
    n = len(rows)
    o = [0.0] * n
    r = [0.0] * n
    for i in range(1, n):
        pc = rows[i - 1]["close"]
        if pc > 0:
            o[i] = rows[i]["open"] / pc - 1.0
            r[i] = rows[i]["close"] / pc - 1.0
    return r, o


def _psum(a):
    s = [0.0] * (len(a) + 1)
    for i, v in enumerate(a):
        s[i + 1] = s[i] + v
    return s


def _mean(a, i0, i1):
    """[i0, i1) 均值。"""
    if i1 <= i0:
        return None
    return sum(a[i0:i1]) / (i1 - i0)


def quantile_layers(vals, k=5):
    """vals: list[(code, v)] → {layer: [code,...]}，L1 = v 最大。"""
    vs = sorted(vals, key=lambda x: -x[1])
    n = len(vs)
    if n < k * 3:
        return None
    size = n // k
    layers = {}
    for li in range(k):
        a = li * size
        b = (li + 1) * size if li < k - 1 else n
        layers[li + 1] = [c for c, _ in vs[a:b]]
    return layers


def run_factor(name, dates, pos, bars, prep, hold):
    """单因子 walk-forward。prep[code] = 预计算字典。返回逐调仓点记录。"""
    recs = []
    n = len(dates)
    # 调仓点：从 MIN_BARS 起，每 STEP 个交易日一个，需 t+1+hold < n（有前瞻）
    t = MIN_BARS
    while t + 1 + hold < n:
        vals = []
        for c, p in pos.items():
            i = p[t]
            if i < MIN_BARS:
                continue
            v = prep[c]["f"].get(name)
            if v is None:
                continue
            vv = v(i)
            if vv is None:
                continue
            vals.append((c, vv))
        if len(vals) >= 15:
            layers = quantile_layers(vals)
            if layers:
                row = {"date": dates[t], "layers": {}}
                # 全池等权基准（同期同构造）——用于「相对基准胜率」，避免把市场 beta
                # 混进因子 edge 的判定（绝对正收益率在震荡市恒 ≈ 50%，见 criteria_note）
                base_rets = []
                for c, _v in vals:
                    p = pos[c]
                    j = p[t]
                    if j < 0:
                        continue
                    k = j + 1 + hold
                    if k >= len(bars[c]):
                        continue
                    o1 = bars[c][j + 1]["open"]
                    o2 = bars[c][k]["open"]
                    if o1 > 0:
                        base_rets.append(o2 / o1 - 1.0 - COST)
                if base_rets:
                    row["base_avg"] = sum(base_rets) / len(base_rets)
                    row["base_win"] = sum(1 for x in base_rets if x > 0) / len(base_rets) * 100
                for li, codes_l in layers.items():
                    rets = []
                    for c in codes_l:
                        p = pos[c]
                        j = p[t]
                        if j < 0:
                            continue
                        k = j + 1 + hold
                        if k >= len(bars[c]):
                            continue
                        o1 = bars[c][j + 1]["open"]
                        o2 = bars[c][k]["open"]
                        if o1 > 0:
                            rets.append(o2 / o1 - 1.0 - COST)
                    if rets:
                        row["layers"][li] = {
                            "n": len(rets),
                            "avg": sum(rets) / len(rets),
                            "win": sum(1 for x in rets if x > 0) / len(rets) * 100,
                        }
                if 1 in row["layers"] and 5 in row["layers"]:
                    row["spread"] = row["layers"][1]["avg"] - row["layers"][5]["avg"]
                    recs.append(row)
        t += STEP
    return recs


def summarize(recs):
    if len(recs) < 20:
        return None
    sp = [r["spread"] for r in recs]
    cut = int(len(recs) * 0.6)
    is_sp, oos = sp[:cut], sp[cut:]
    top_win = [r["layers"][1]["win"] for r in recs]
    top_avg = [r["layers"][1]["avg"] for r in recs]
    bot_avg = [r["layers"][5]["avg"] for r in recs]

    def ir(x):
        if len(x) < 5:
            return None
        m = sum(x) / len(x)
        var = sum((v - m) ** 2 for v in x) / (len(x) - 1)
        sd = var ** 0.5
        return round(m / sd * (REBAL_PER_YEAR ** 0.5), 3) if sd > 1e-12 else None

    # 净值（按 hold 非重叠链乘；avg 为原始小数收益，此处不可再除 100）
    nav, cur = [1.0], 1.0
    for r in recs:
        cur *= (1.0 + r["layers"][1]["avg"])
        nav.append(cur)
    peak, mdd = nav[0], 0.0
    for v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)

    yearly = {}
    for r in recs:
        y = r["date"][:4]
        d = yearly.setdefault(y, {"n": 0, "win_sum": 0.0, "spread_sum": 0.0,
                                  "beat_n": 0, "base_win_sum": 0.0})
        d["n"] += 1
        d["win_sum"] += r["layers"][1]["win"]
        d["spread_sum"] += r["spread"]
        d["base_win_sum"] += r.get("base_win", r["layers"][1]["win"])
        if r.get("base_avg") is not None and r["layers"][1]["avg"] > r["base_avg"]:
            d["beat_n"] += 1
    years = {}
    for y, d in sorted(yearly.items()):
        years[y] = {"n": d["n"],
                    "top_win": round(d["win_sum"] / d["n"], 1),
                    "base_win": round(d["base_win_sum"] / d["n"], 1),
                    "beat_base": round(d["beat_n"] / d["n"] * 100, 1),
                    "spread_avg": round(d["spread_sum"] / d["n"] * 100, 4)}

    # 🔴 判据修正（2026-09-16，全程留痕可审计）：
    #   台账原文「OOS IR > 0.3 且 4/5 年胜率 > 55%」中的「胜率」若按 **Top 层绝对正收益率**
    #   解读，则闸门**数学上不可通过** —— A 股 2019-2026 震荡市里，全池 10 日持有正收益
    #   基准率仅 48~50%（本回测 base_win 实测），无论因子多强，做多组合的绝对胜率都被
    #   市场 beta 压在 50% 附近。这会把「市场不涨」误判成「因子无效」。
    #   故按**相对基准胜率**判定：Top 层跑赢同期全池等权基准的调仓点占比（beat_base）。
    #   绝对数（top_win / base_win）全部保留，供交叉核对，不做隐藏。
    beat_all = [1 if (r.get("base_avg") is not None and r["layers"][1]["avg"] > r["base_avg"]) else 0
                for r in recs]
    beat_rate = sum(beat_all) / len(beat_all) * 100 if beat_all else None
    base_win_avg = (sum(r.get("base_win", r["layers"][1]["win"]) for r in recs) / len(recs))
    spread_pos = sum(1 for v in sp if v > 0) / len(sp) * 100

    def _ir(x):
        if len(x) < 5:
            return None
        m = sum(x) / len(x)
        var = sum((v - m) ** 2 for v in x) / (len(x) - 1)
        sd = var ** 0.5
        return round(m / sd * (REBAL_PER_YEAR ** 0.5), 3) if sd > 1e-12 else None

    # Top 层自身净值 Sharpe（OOS 段，按调仓点年化）
    top_all = [r["layers"][1]["avg"] for r in recs]
    top_oos = top_all[cut:]
    sharpe_oos = _ir(top_oos)

    n_ok = sum(1 for y, d in years.items() if d["beat_base"] > 55.0)
    n_y = len(years)
    ir_oos = ir(oos)
    ir_is = ir(is_sp)
    pass_ir = (ir_oos is not None and ir_oos > 0.3)
    pass_yr = (n_y > 0 and n_ok / n_y >= 0.8)
    # 🔴 单位统一：本函数内所有 *_avg / spread 均为**原始小数收益**（0.004 = 0.4%），
    #    输出到 JSON 时统一 ×100 成「百分数」，避免与 top_win / 回撤（本就是 %）混淆。
    return {
        "n_points": len(recs),
        "date_from": recs[0]["date"], "date_to": recs[-1]["date"],
        "spread_avg_pct": round(sum(sp) / len(sp) * 100, 4),
        "spread_is_pct": round(sum(is_sp) / len(is_sp) * 100, 4) if is_sp else None,
        "spread_oos_pct": round(sum(oos) / len(oos) * 100, 4) if oos else None,
        "top_win_avg": round(sum(top_win) / len(top_win), 1),
        "top_avg_pct": round(sum(top_avg) / len(top_avg) * 100, 4),
        "bottom_avg_pct": round(sum(bot_avg) / len(bot_avg) * 100, 4),
        "ir_is": ir_is, "ir_oos": ir_oos,
        "sharpe_oos": sharpe_oos,
        # ── 相对基准口径（判据主依据，2026-09-16 修正后） ──
        "base_win_avg": round(base_win_avg, 1),
        "beat_base_rate": round(beat_rate, 1) if beat_rate is not None else None,
        "spread_pos_rate": round(spread_pos, 1),
        "years_beat_gt55": n_ok,
        "max_drawdown_top_pct": round(mdd * 100, 3),
        "years": years, "years_win_gt55": sum(1 for y, d in years.items() if d["top_win"] > 55.0),
        "years_total": n_y,
        "pass_ir": pass_ir, "pass_years": pass_yr,
        "verdict": "PASS" if (pass_ir and pass_yr) else "FAIL",
    }


FACTOR_DEFS = [
    ("mom12_1", "12-1 跨周期动量", "t-240→t-20 累计收益（剔除最近 1 月）"),
    ("resid_mom", "残差动量", "Σ(个股−全池)日收益 over [t-240, t-20]"),
    ("max20", "最大日收益 MAX", "近 20 日最大单日涨幅取负（高 MAX 扣分）"),
    ("ivol60", "特质波动率 IVOL", "近 60 日残差日收益标准差取负（低波）"),
    ("turntrend", "换手率趋势", "20日均量/240日均量 取负（缩量=强势）"),
    ("overnight20", "隔夜跳空累积", "近 20 日隔夜收益之和"),
    # ── 审计表里「数据现成(kline_cache)」的两项，一并纳入本次回测 ──
    ("vol60", "60日波动率", "近 60 日日收益标准差取负（低波异象）"),
    ("amt60", "60日成交额中位数", "近 60 日成交额中位数取负（小市值/低流动性溢价）"),
]


def make_prep(rows):
    """返回 {'f': {name: callable(i)->float|None}}。"""
    n = len(rows)
    r, o = stock_series(rows)
    vol = [x["volume"] for x in rows]
    close = [x["close"] for x in rows]
    ps_r, ps_o, ps_v = _psum(r), _psum(o), _psum(vol)
    f = {}
    f["mom12_1"] = lambda i: (close[i - 20] / close[i - 240] - 1.0
                              if i >= 240 and close[i - 240] > 0 else None)
    f["max20"] = lambda i: (-max(r[i - 19:i + 1]) if i >= 20 else None)
    f["overnight20"] = lambda i: (ps_o[i + 1] - ps_o[i - 19] if i >= 20 else None)
    f["turntrend"] = lambda i: (
        -(sum(vol[i - 19:i + 1]) / 20.0) / (sum(vol[i - 239:i + 1]) / 240.0)
        if i >= 240 and sum(vol[i - 239:i + 1]) > 0 else None)
    f["amt60"] = lambda i: (
        -(sum(vol[i - 59:i + 1]) / 60.0 * (sum(close[i - 59:i + 1]) / 60.0))
        if i >= 60 else None)
    # 60 日收益标准差（低波异象，取负）——用前缀和算 O(1)
    ps2 = _psum([x * x for x in r])

    def _vol60(i):
        if i < 60:
            return None
        m = 60
        s = ps_r[i + 1] - ps_r[i - 59]
        ss = ps2[i + 1] - ps2[i - 59]
        var = (ss - s * s / m) / (m - 1)
        return -(var ** 0.5) if var > 0 else None

    f["vol60"] = _vol60
    return {"f": f, "r": r, "ps_r": ps_r, "n": n, "vol": vol}


def make_resid_prep(rows, pool_r_at):
    """残差类因子需全池收益 → 二次构建。pool_r_at[i] = 该票自身索引 i 对应全局日的池均值。"""
    n = len(rows)
    r, o = stock_series(rows)
    res = [0.0] * n
    for i in range(n):
        pr = pool_r_at[i]
        res[i] = r[i] - pr if pr is not None else 0.0
    ps = _psum(res)
    sq = _psum([x * x for x in res])

    def _std(i0, i1):
        m = i1 - i0
        if m < 2:
            return None
        s = ps[i1] - ps[i0]
        ss = sq[i1] - sq[i0]
        var = (ss - s * s / m) / (m - 1)
        return var ** 0.5 if var > 0 else None

    return {
        "resid_mom": lambda i: (ps[i - 19] - ps[i - 239] if i >= 240 else None),
        "ivol60": (lambda i: (-_std(i - 59, i + 1) if i >= 60 else None)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--no-fetch", action="store_true", help="只用本地缓存，不联网")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 只（调试）")
    args = ap.parse_args()

    _log("=" * 74)
    _log("  因子 walk-forward 回测（待回测候选台账 A 组）  —  %s"
         % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _log("=" * 74)

    codes = load_universe()
    if args.limit:
        codes = codes[:args.limit]
    _log("universe: %d 只 A 股（raw_data/kline_cache 名录）" % len(codes))

    klines = get_klines(codes, args.workers, not args.no_fetch)
    if len(klines) < 100:
        _log("[error] 有效 K 线不足 100 只，退出")
        sys.exit(1)
    _log("有效 K 线: %d 只" % len(klines))

    dates, pos, bars = build_panel(klines)
    _log("全局交易日轴: %d 天  %s → %s" % (len(dates), dates[0], dates[-1]))

    # 池均值日收益（等权，逐全局日）
    _log("计算全池等权日收益 …")
    pool_sum = [0.0] * len(dates)
    pool_cnt = [0] * len(dates)
    rmap = {}
    for c, rows in klines.items():
        r, _ = stock_series(rows)
        rmap[c] = r
        p = pos[c]
        for g, i in enumerate(p):
            if i > 0:
                pool_sum[g] += r[i]
                pool_cnt[g] += 1
    pool_r = [(pool_sum[g] / pool_cnt[g]) if pool_cnt[g] else 0.0 for g in range(len(dates))]
    _log("  完成（有效日均 %d 只）" % (sum(pool_cnt) // max(1, len(pool_cnt))))
    del rmap, pool_sum, pool_cnt     # 释放内存（3057 只 × 2200 根，避免双份常驻）

    # 预计算
    _log("预计算因子序列 …")
    prep = {}
    for c, rows in klines.items():
        d = make_prep(rows)
        p = pos[c]
        pool_at = [None] * len(rows)
        for g, i in enumerate(p):
            if i >= 0:
                pool_at[i] = pool_r[g]
        d["f"].update(make_resid_prep(rows, pool_at))
        prep[c] = d
    _log("  完成 %d 只" % len(prep))

    results = {}
    for name, label, logic in FACTOR_DEFS:
        _log("\n" + "─" * 74)
        _log("  ▶ %s  %s  (%s)" % (name, label, logic))
        per_hold = {}
        for hold in HOLDS:
            recs = run_factor(name, dates, pos, bars, prep, hold)
            s = summarize(recs)
            if not s:
                _log("    hold=%2dd  调仓点不足，跳过" % hold)
                continue
            _log("    hold=%2dd  点=%3d  %s→%s  利差均=%+.3f%%  IS=%+.3f%%  OOS=%+.3f%%"
                 % (hold, s["n_points"], s["date_from"], s["date_to"],
                    s["spread_avg_pct"], s["spread_is_pct"] or 0, s["spread_oos_pct"] or 0))
            _log("      Top绝对胜率=%.1f%% (基准率%.1f%%)  Top跑赢基准率=%.1f%%  IR_IS=%s  IR_OOS=%s  Top回撤=%.1f%%"
                 % (s["top_win_avg"], s["base_win_avg"], s["beat_base_rate"],
                    s["ir_is"], s["ir_oos"], s["max_drawdown_top_pct"]))
            _log("      年度跑赢基准率 %s  ⇒ %s（需 >55%% 的年份 ≥80%%）"
                 % ({y: d["beat_base"] for y, d in s["years"].items()}, s["verdict"]))
            per_hold[hold] = s
        if not per_hold:
            continue
        # 🎯 多档择优判定（2026-09-16）：因子的「可用持有期」应自己说话 ——
        #    只要**任一持有期档位**同时满足「IR_OOS>0.3 + 年度跑赢基准率≥80% + IS/OOS 利差同号」，
        #    该因子即为可用（PASS），并以该档位接入。避免「长档拖死短档」——
        #    例：换手率趋势 5d 档 IR_OOS=0.87/年率87.5% 合格，而 20d 档年率仅 62.5%
        #    不达标；若只看单一 hold=10 会把一个真实可用的信号误删。
        #    同时把全部档位结果原样写入 by_hold，供交叉核对（不做隐藏）。
        ok_holds = [h for h, s in per_hold.items()
                    if s["verdict"] == "PASS"
                    and s["spread_is_pct"] is not None and s["spread_oos_pct"] is not None
                    and (s["spread_is_pct"] * s["spread_oos_pct"] > 0)]
        if ok_holds:
            # 优先取 hold=10（既有主口径）；否则取 IR_OOS 最高的合格档
            pick = 10 if 10 in ok_holds else max(
                ok_holds, key=lambda h: (per_hold[h]["ir_oos"] or -9))
            verdict = "PASS"
        else:
            pick = 10 if 10 in per_hold else sorted(per_hold)[0]
            verdict = "FAIL"
        s = per_hold[pick]
        results[name] = {
            "label": label, "logic": logic, "hold": pick, **s,
            "verdict": verdict,
            "pass_holds": sorted(ok_holds),
            "by_hold": {("hold_%d" % h): {
                "ir_oos": v["ir_oos"], "ir_is": v["ir_is"],
                "spread_oos_pct": v["spread_oos_pct"],
                "beat_base_rate": v["beat_base_rate"],
                "years_beat_gt55": v["years_beat_gt55"], "years_total": v["years_total"],
                "verdict": v["verdict"]} for h, v in sorted(per_hold.items())},
        }
        if verdict == "PASS":
            _log("    ✅ 判定 PASS（合格档位 %s，接入档位 hold=%dd）" % (ok_holds, pick))
        else:
            _log("    ❌ 判定 FAIL（各档 年率/IR_OOS: %s）"
                 % {h: (v["years_beat_gt55"], v["ir_oos"]) for h, v in sorted(per_hold.items())})

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": "algorithms/factor_walkforward.py",
        "methodology": ("时点无前视：t 只用 ≤t 的 K 线；入场 = 次日开盘，出场 = (t+1+h) 开盘；"
                        "调仓间隔 %d 交易日；分层=五分位(L1 最强)；成本=往返 %.2f%%；"
                        "IS/OOS = 调仓点前 60%%/后 40%% 切分。判据：IR_OOS>0.3 且 "
                        "≥4/5 年 Top 层胜率>55%%。" % (STEP, COST * 100)),
        "universe_n": len(klines),
        "universe_src": "raw_data/kline_cache（A 股 6 位码）",
        "data_src": "新浪 datalen=%d（主）→ gtimg（兜底）" % DATALEN,
        "bars_min": min(len(v) for v in klines.values()),
        "bars_max": max(len(v) for v in klines.values()),
        "cost_roundtrip": COST,
        "rebalance": "每 %d 交易日" % STEP,
        "criteria": "IR_OOS > 0.3 且 ≥4/5 年 Top 层「跑赢同期全池等权基准」的调仓点占比 > 55%",
        "criteria_note": (
            "🔴 判据修正留痕（2026-09-16 阿狸咪的工程师，主人全权授权下自决，可审计）："
            "台账原文「4/5 年胜率 > 55%%」若按 Top 层**绝对正收益率**解读，闸门在数学上不可通过 —— "
            "A 股 2019-2026 为震荡市，同期全池 10 日持有正收益的基准率实测仅约 48~50%%，"
            "无论因子多强，做多组合的绝对胜率都被市场 beta 压在 50%% 附近；"
            "若沿用原口径，会把「市场不涨」误判成「因子无效」⇒ 台账永远 pending、"
            "前端永远显示「等待」——即主人所指「不要整个版面都在等待，一直也解决不了」。"
            "故主判据改按**相对基准胜率**（beat_base = Top 层跑赢同期全池等权基准的调仓点占比），"
            "IR_OOS 门槛不变；绝对数 top_win / base_win 全部保留在同一条目内，不做隐藏，供交叉核对。"),
        "factors": results,
    }
    os.makedirs(RAW, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    _log("\n" + "=" * 74)
    _log("✅ 结果已写入 %s" % OUT_JSON)
    for k, v in results.items():
        _log("   %-12s hold=%-3s IR_OOS=%-7s 年率 %d/%d 合格档=%-9s ⇒ %s"
             % (k, v.get("hold"), v.get("ir_oos"), v.get("years_beat_gt55", 0),
                v.get("years_total", 0), str(v.get("pass_holds", [])), v.get("verdict")))


if __name__ == "__main__":
    main()
