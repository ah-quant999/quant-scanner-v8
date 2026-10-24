#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_goldpool_expectancy.py — 验证宇宙对齐生产宇宙（补齐缺口测试）

目的：在「真正挑给用户的金股池」上重算 amt60/turntrend/ivol60 三因子前向期望，
      关闭此前「验证宇宙(_wf_cache 565, 14.9%重叠) ≠ 生产选股宇宙(金股池609)」的致命缺口。

口径（严格对齐生产，来源已钉死）：
  amt60     = mean(vol[-60:]) * mean(close[-60:])        [×100 为统一量纲常数，排序不变，略]
             越小越强（低流动性/小市值溢价）  hold=10
  turntrend = (mean(vol[-20:])/20) / (mean(vol[-240:])/240)
             越小越强（缩量=强势）            hold=5
  ivol60    = std( 个股日收益[-60:] − 上证日收益[-60:] )
             越小越强（低特质波动异象）        hold=10
             上证基准 = kline_cache/000001.json（与 generate_top10._p4_market_kline 同）

方法：月度再平衡（信号日跨 stride=20 取近独立时间样本），无未来函数：
      信号在 i 日收盘用 ≤i 数据算；前向收益 = close[i+hold]/close[i] − 1（用 >i 数据）。
      每个再平衡日，对当日可算因子的票按 raw 升序（越小越强）取后 25%（因子优选档），
      等权篮子前向收益；跨再平衡日聚合得到 期望/胜率/样本数。

重要诚实边界：本地 kline_cache 最长 ~351 根（约1年），240 回顾因子仅近数月可用。
      本测试反映 2026 年近期 regime，非多年样本；生产级多年 WF 需云端 fetch 多年历史。
      本脚本仅做「对齐金股池」的证据补齐，不替代生产引擎。
"""
import json, os, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
CACHE = os.path.join(RAW, "kline_cache")
GOLD = os.environ.get("GOLD_PATH", os.path.join(RAW, "gold_pool.json"))
MKT = os.path.join(CACHE, "000001.json")  # 上证指数代理（生产同口径）

HOLD = {"amt60": 10, "turntrend": 5, "ivol60": 10}
BURN = {"amt60": 60, "turntrend": 240, "ivol60": 60}
STRIDE = 20  # 再平衡跨步（交易日），近独立时间样本


def load_bars(code):
    p = os.path.join(CACHE, code + ".json")
    if not os.path.exists(p):
        return None
    try:
        d = json.load(open(p, encoding="utf-8"))
        return d if isinstance(d, list) else None
    except Exception:
        return None


def daily_rets(bars):
    """bars 升序 → {date: 日收益}"""
    out = {}
    for i in range(1, len(bars)):
        c0 = bars[i - 1].get("close")
        c1 = bars[i].get("close")
        if c0 and c1 and c0 > 0:
            out[bars[i]["date"]] = (c1 - c0) / c0
    return out


def mkt_ret_dict():
    bars = load_bars("000001")
    if not bars:
        return {}
    return daily_rets(bars)


def factor_raw_amt60(bars, i):
    seg = bars[i - 59:i + 1]
    v = sum(float(r.get("volume") or 0) for r in seg) / 60.0
    c = sum(float(r.get("close") or 0) for r in seg) / 60.0
    return v * c


def factor_raw_turntrend(bars, i):
    if i < 240:
        return None
    base = sum(float(bars[k].get("volume") or 0) for k in range(i - 239, i + 1)) / 240.0
    if base <= 0:
        return None
    recent = sum(float(bars[k].get("volume") or 0) for k in range(i - 19, i + 1)) / 20.0
    return recent / base


def factor_raw_ivol60(bars, i, mkt_r):
    """残差标准差；按日期对齐上证。"""
    if i < 60:
        return None
    res = []
    for k in range(i - 59, i + 1):
        d = bars[k]["date"]
        sr = None
        c0 = bars[k - 1].get("close"); c1 = bars[k].get("close")
        if c0 and c1 and c0 > 0:
            sr = (c1 - c0) / c0
        mr = mkt_r.get(d)
        if sr is None or mr is None:
            return None
        res.append(sr - mr)
    n = len(res)
    if n < 60:
        return None
    mean = sum(res) / n
    var = sum((x - mean) ** 2 for x in res) / (n - 1)
    return var ** 0.5 if var > 0 else None


def build_factor_map(codes, fname, compute):
    """返回 {date: {code: (raw, fwd_ret)}}，fwd_ret 用 close[i+hold]/close[i]-1。"""
    hold = HOLD[fname]
    out = {}
    for code in codes:
        bars = load_bars(code)
        if not bars or len(bars) < BURN[fname] + hold:
            continue
        for i in range(BURN[fname], len(bars) - hold):
            raw = compute(bars, i)
            if raw is None:
                continue
            d = bars[i]["date"]
            fwd = bars[i + hold]["close"] / bars[i]["close"] - 1.0
            out.setdefault(d, {})[code] = (raw, fwd)
    return out


def run_expectancy(fmap):
    """月度再平衡：跨所有日期 stride 取样，每日取后25%因子优选档，聚合。"""
    dates = sorted(fmap.keys())
    if not dates:
        return None
    # 取近独立再平衡日：从末向前每 STRIDE 一个
    rb = dates[-1::-STRIDE][::-1]
    expo_sum = 0.0
    wins = 0
    n_dates = 0
    n_stocks = 0
    span = [dates[0], dates[-1]]
    per_date = []
    for d in rb:
        row = fmap[d]
        if len(row) < 50:  # 截面太薄跳过
            continue
        raws = sorted(v[0] for v in row.values())  # 升序（小=强）
        q = raws[int(len(raws) * 0.25)]  # 25% 分位
        sel = [v[1] for v in row.values() if v[0] <= q]
        if not sel:
            continue
        br = sum(sel) / len(sel)
        expo_sum += br
        wins += 1 if br > 0 else 0
        n_dates += 1
        n_stocks += len(sel)
        per_date.append(br)
    if n_dates == 0:
        return None
    expo = expo_sum / n_dates
    winrate = wins / n_dates
    # 简单 t 值（跨再平衡日）
    if n_dates > 1:
        mu = expo
        var = sum((x - mu) ** 2 for x in per_date) / (n_dates - 1)
        t = mu / (var ** 0.5 / math.sqrt(n_dates)) if var > 0 else 0.0
    else:
        t = 0.0
    return {"expo": expo, "winrate": winrate, "n_dates": n_dates,
            "n_stocks": n_stocks, "span": span, "t": t}


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    stocks = gold["stocks"]
    filt = None
    fs = os.environ.get("FILTER_SOURCES", "")
    if fs:
        filt = set(fs.split(","))
    codes = []
    for k, v in stocks.items():
        c = k.split("_")[-1] if "_" in k else k
        if filt:
            srcs = v.get("sources", []) if isinstance(v, dict) else []
            if not (filt & set(srcs)):
                continue
        if load_bars(c):
            codes.append(c)
    tag = (" [仅来源: %s]" % ",".join(sorted(filt))) if filt else ""
    print("金股池总数 %d，本次测试%s %d 只（kline_cache 覆盖）" % (len(stocks), tag, len(codes)))
    mkt_r = mkt_ret_dict()
    print("上证基准(000001)日收益点数: %d" % len(mkt_r))

    # 各因子可算票数
    def count_computable(codes, fname, compute):
        n = 0
        for code in codes:
            bars = load_bars(code)
            if not bars:
                continue
            for i in range(BURN[fname], len(bars) - HOLD[fname]):
                if compute(bars, i) is not None:
                    n += 1
                    break
        return n

    fmap_amt = build_factor_map(codes, "amt60", factor_raw_amt60)
    fmap_tur = build_factor_map(codes, "turntrend", factor_raw_turntrend)
    fmap_ivo = build_factor_map(codes, "ivol60",
                                lambda b, i: factor_raw_ivol60(b, i, mkt_r))

    print("\n=== 金股池对齐测试（验证宇宙=生产选股宇宙）===")
    results = {}
    for name, fmap in (("amt60", fmap_amt), ("turntrend", fmap_tur), ("ivol60", fmap_ivo)):
        r = run_expectancy(fmap)
        results[name] = r
        if not r:
            print("  %s: 样本不足" % name)
            continue
        print("  %-10s 期望=%+.2f%%  胜率=%d%%  再平衡日=%d  票次=%d  跨度=%s~%s  t=%.2f"
              % (name, r["expo"] * 100, int(r["winrate"] * 100), r["n_dates"],
                 r["n_stocks"], r["span"][0], r["span"][1], r["t"]))
    print("\n（注：本地kline_cache约1年，240回顾因子仅近数月可用；反映2026近期regime。）")
    return results


if __name__ == "__main__":
    main()
