#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💎 大资金买点三样 · 金钻跟踪 —— Phase 1 回测原型（本地，不推送）

目标：在 v8 现有 raw_data/kline_cache/*.json（6139 只本地日K）上，
按「选股策略演示卡」规格（index.html::__renderJinzuanTrack 注释写死）实现：
  · 机构六维评分 → 取前 352 只作固定股池
  · 金钻起涨(金钻趋势/金牛线 XMA双25 复现) + DY2 资金流
  · 金钻紧迫度（六条件接近度加权 → 0~100）
  · 多周期黄金分割(60/120/252)重合支撑 与 资金加权成本(VWAP)支撑 两种定义
  · 四档：①确认买点(金钻起涨触发) ②价格买点 ③临近买点 ④信号蓄势
  · 四档各自独立回测：信号日次开盘买、持有 N 日收盘卖、双边成本 0.30%
  · 斐波那契 vs VWAP 两种支撑的 ②③④ 档前向收益对比，实证选优

铁律：非未来函数；纯 pandas/numpy；不写 data/、不推送。
"""
import json, os, sys, glob, time
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
RAW  = os.path.join(REPO, "raw_data")
KC   = os.path.join(RAW, "kline_cache")
POOL_JSON   = os.path.join(RAW, "jinzuan_pool.json")
BACKTEST_JSON = os.path.join(RAW, "jinzuan_track_backtest.json")

# ============== 金钻原语（移植自 scanner.py，纯 pandas/numpy） ==============
def ref(series, n):
    return series.shift(int(n) if pd.notna(n) else 0)

def sma_tdx(series, n, m):
    result = pd.Series(np.nan, index=series.index)
    arr = series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    if len(arr) == 0:
        return result
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = (arr[i] * m + out[i-1] * (n - m)) / n
    return pd.Series(out, index=series.index)

def xma_causal(series, n):
    """✅ 因果 XMA（trailing）—— 仅用过去+当日，无未来泄漏。
    线上末根与居中 XMA 等价；回测必须用此版本，保证 backtest==production。"""
    s = pd.Series(series.to_numpy(dtype=float), index=series.index)
    return s.rolling(window=n, min_periods=1).mean()

def ma(series, n):
    return series.rolling(window=n, min_periods=1).mean()

def load_kline(code):
    p = os.path.join(KC, f"{code}.json")
    if not os.path.exists(p):
        return None
    try:
        b = json.loads(open(p, encoding="utf-8").read())
    except Exception:
        return None
    if not b:
        return None
    df = pd.DataFrame(b)
    for c in ("open","close","high","low","volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = df["date"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    return df

# ============== 金钻趋势指标（scanner.py calc_jinzuan_signal 精确移植） ==============
def calc_jinzuan(df):
    H = df["high"]; L = df["low"]; C = df["close"]; O = df["open"]
    V = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)
    # 🔴 回测/复现一律用因果 XMA（xma_causal），杜绝未来函数；线上末根与居中 XMA 等价
    AH = xma_causal(xma_causal(H, 25), 25)
    AL = xma_causal(xma_causal(L, 25), 25)
    金钻趋势 = AL - (AH - AL)
    金牛 = AH - (AL - AH)
    df["金钻趋势"] = 金钻趋势
    df["金牛"] = 金牛
    if "volume" in df.columns and V.sum() > 0:
        JJ = (H + L + C) / 3
        HL_eq = (H == L)
        QJ0 = V / pd.Series(np.where(HL_eq, 4, H - L), index=df.index)
        T1 = pd.Series(np.where(HL_eq, 1, np.minimum(C, O) - L), index=df.index)
        T2 = pd.Series(np.where(HL_eq, 1, JJ - np.minimum(C, O)), index=df.index)
        T3 = pd.Series(np.where(HL_eq, 1, H - np.maximum(C, O)), index=df.index)
        T4 = pd.Series(np.where(HL_eq, 1, np.maximum(C, O) - JJ), index=df.index)
        QJ1 = QJ0 * T1; QJ2 = QJ0 * T2; QJ3 = QJ0 * T3; QJ4 = QJ0 * T4
        DDX = ((QJ1 + QJ2) - (QJ3 + QJ4)) / 10000
        V2 = sma_tdx(pd.Series(np.where(C >= ref(C, 1), DDX, -DDX / 100), index=df.index), 2, 1)
        DY = (C < ref(C, 1)).astype(float)
        DY2 = ref(V2, 1) - DY
        金钻起涨 = (C > O) & (DY2 < 0.02) & (ma(C, 5) > ma(C, 60)) & \
                  (C / ref(C, 1) >= 1.02) & (H < 金牛) & (L < 金钻趋势)
        df["DY2"] = DY2
    else:
        金钻起涨 = pd.Series(False, index=df.index)
        df["DY2"] = np.nan
    df["金钻起涨"] = 金钻起涨
    return df

# ============== 金钻紧迫度（六条件接近度加权，规格见 index.html L15633-15636） ==============
TOL = {1:0.05, 3:0.08, 4:0.05, 5:0.08, 6:0.08}   # c2 用分位，不走 TOL
W   = {1:1.0, 2:0.8, 3:1.3, 4:1.3, 5:1.0, 6:1.0}
WSUM = sum(W.values())

def compute_urgency(df):
    C = df["close"]; O = df["open"]; H = df["high"]; L = df["low"]
    MA5 = ma(C, 5); MA60 = ma(C, 60)
    DY2 = df["DY2"]
    # c1 收阳 C>O
    prox1 = np.where(C > O, 1.0, np.clip(1 - (O - C) / C / TOL[1], 0, 1))
    # c3 趋势 MA5>MA60
    gap3 = (MA60 - MA5) / MA5
    prox3 = np.where(MA5 > MA60, 1.0, np.clip(1 - gap3 / TOL[3], 0, 1))
    # c4 涨幅≥2%
    r4 = C / ref(C, 1)
    gap4 = (1.02 - r4)
    prox4 = np.where(r4 >= 1.02, 1.0, np.clip(1 - gap4 / TOL[4], 0, 1))
    # c5 最高价 H<金牛线
    gap5 = (H - df["金牛"]) / df["金牛"]
    prox5 = np.where(H < df["金牛"], 1.0, np.clip(1 - gap5 / TOL[5], 0, 1))
    # c6 最低价 L<金钻趋势线
    gap6 = (L - df["金钻趋势"]) / df["金钻趋势"]
    prox6 = np.where(L < df["金钻趋势"], 1.0, np.clip(1 - gap6 / TOL[6], 0, 1))
    # c2 资金流 DY2<0.02：过去120日 DY2 历史分位 pct，接近度=1-pct；120日内从未≤0.02 记0
    roll = DY2.rolling(120, min_periods=60)
    pct = roll.apply(lambda w: float((w <= w.iloc[-1]).mean()), raw=False)
    mn  = roll.min()
    prox2 = np.where(mn > 0.02, 0.0, np.clip(1 - pct, 0, 1))
    prox = {1:prox1,2:prox2,3:prox3,4:prox4,5:prox5,6:prox6}
    urg = sum(W[i]*prox[i] for i in range(1,7)) / WSUM * 100
    sat = sum((prox[i] >= 0.5).astype(int) for i in range(1,7))
    df["prox1"]=prox1; df["prox2"]=prox2; df["prox3"]=prox3
    df["prox4"]=prox4; df["prox5"]=prox5; df["prox6"]=prox6
    df["urg"] = urg
    df["sat"] = sat
    return df

# ============== 多周期支撑（两种定义） ==============
def compute_supports(df):
    C = df["close"]; H = df["high"]; L = df["low"]; V = df["volume"]
    n = len(df)
    sup_fib = np.full(n, np.nan); sup_vwap = np.full(n, np.nan)
    WINS = [60, 120, 252]
    for i in range(n):
        fib_levels_w = []
        vwap_w = []
        for W_ in WINS:
            s = max(0, i - W_ + 1)
            if i - s + 1 < 20:
                continue
            sub_h = H.iloc[s:i+1]; sub_l = L.iloc[s:i+1]; sub_c = C.iloc[s:i+1]
            sub_v = V.iloc[s:i+1]
            hmax = sub_h.max(); lmin = sub_l.min()
            rng = hmax - lmin
            levels = [hmax - rng*r for r in (0.382, 0.5, 0.618)]
            cprice = sub_c.iloc[-1]
            below = [lv for lv in levels if lv <= cprice]
            fib_levels_w.append(max(below) if below else min(levels))
            vwap_w.append((sub_c * sub_v).sum() / sub_v.sum() if sub_v.sum() > 0 else np.nan)
        sup_fib[i]  = max(fib_levels_w) if fib_levels_w else np.nan
        sup_vwap[i] = max(vwap_w)   if vwap_w   else np.nan
    df["sup_fib"] = sup_fib; df["sup_vwap"] = sup_vwap
    df["dist_fib"]  = (C - sup_fib) / C * 100
    df["dist_vwap"] = (C - sup_vwap) / C * 100
    return df

# ============== 四档 ==============
def compute_tiers(df):
    urgent = df["金钻起涨"]
    urg = df["urg"]; sat = df["sat"]
    df["tier1"] = urgent.astype(bool)                      # ①确认买点
    df["tier2_fib"]  = (df["dist_fib"]  <= 3.5) & (urg >= 78) & (sat >= 4)
    df["tier3_fib"]  = (df["dist_fib"]  <= 8.0) & (urg >= 75) & (sat >= 3)
    df["tier4_fib"]  = (urg >= 85) & (sat >= 4) & (df["dist_fib"]  > 8.0)
    df["tier2_vwap"] = (df["dist_vwap"] <= 3.5) & (urg >= 78) & (sat >= 4)
    df["tier3_vwap"] = (df["dist_vwap"] <= 8.0) & (urg >= 75) & (sat >= 3)
    df["tier4_vwap"] = (urg >= 85) & (sat >= 4) & (df["dist_vwap"] > 8.0)
    return df

# ============== 回测单笔 ==============
def one_trade(dates, opens, closes, sig_date, n):
    idxs = [i for i, d in enumerate(dates) if d > sig_date]
    if not idxs:
        return None
    ei = idxs[0]
    if ei + n >= len(dates):
        return None
    entry = opens[ei]; exit_ = closes[ei + n]
    if entry is None or exit_ is None or entry == 0:
        return None
    ret = (exit_ * (1 - 0.0015)) / (entry * (1 + 0.0015)) - 1   # 双边 0.30%
    hold = closes[ei:ei + n + 1]
    mdd = (min(hold) / entry - 1) if entry else 0
    return ret, mdd

def aggregate(signals, dates_map, opens_map, closes_map, ns):
    out = {}
    for name, sigs in signals.items():
        out[name] = {}
        for n in ns:
            rets = []; mdds = []
            for code, sd in sigs:
                r = one_trade(dates_map[code], opens_map[code], closes_map[code], sd, n)
                if r:
                    rets.append(r[0]); mdds.append(r[1])
            if rets:
                arr = np.array(rets)
                out[name][f"{n}d"] = {
                    "n": len(arr),
                    "win": round(float((arr > 0).mean() * 100), 1),
                    "avg": round(float(arr.mean() * 100), 2),
                    "median": round(float(np.median(arr) * 100), 2),
                    "best": round(float(arr.max() * 100), 2),
                    "worst": round(float(arr.min() * 100), 2),
                    "mdd": round(float(min(mdds) * 100), 2),
                }
            else:
                out[name][f"{n}d"] = {"n": 0}
    return out

# ============== 机构六维评分（纯状态/资金类维度，杜绝前视偏差） ==============
# 🔴 铁律修复：选池只用「状态类/资金类」维度，禁止用近期收益/相对强度排名参与选池
#   （ret60/RPS 会带来幸存者+前视偏差，使回测虚高）。六维全为「截至 cutoff 当日状态」：
#   1 主力资金强度(DY2负占比) 2 动量结构(MA5>MA20>MA60) 3 流动性(均额)
#   4 低波动(质量代理) 5 资金趋势(DY2改善) 6 年线态势(C>MA250)
def six_dim_features(df, end_idx=None):
    C = df["close"]; V = df["volume"]
    n = len(df)
    e = n if end_idx is None else min(end_idx, n)
    if e < 252:
        return None
    seg = df.iloc[e-252:e]                     # 仅用截至 cutoff 的 252 根
    d = seg["DY2"].dropna()
    main = float((d < 0).mean()) if len(d) else 0.0
    ma20 = ma(C, 20).iloc[e-1]; ma60 = ma(C, 60).iloc[e-1]; ma250 = ma(C, 250).iloc[e-1]
    mom = 1.0 if (C.iloc[e-1] > ma20 and ma20 > ma60) else (0.5 if C.iloc[e-1] > ma20 else 0.0)
    above_year = 1.0 if C.iloc[e-1] > ma250 else 0.0
    amt = float((seg["close"] * seg["volume"]).mean())
    rets = C.pct_change().iloc[e-252:e]
    vol = float(rets.std()) if len(rets.dropna()) else 0.0
    fund = float(d.tail(20).mean() - d.head(100).mean()) if len(d) >= 120 else 0.0
    return {"main":main, "mom":mom, "amt":amt, "vol":vol, "fund":fund, "year":above_year}

def get_a_codes():
    """真实 A 股代码集合（去指数/ETF 污染）；失败则回退正则过滤。"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        codes = set(df["code"].astype(str).tolist())
        if codes:
            return codes
    except Exception as e:
        print("  [warn] akshare A股列表获取失败，回退正则过滤:", e)
    pat = ("60", "68", "00", "30", "8", "4")
    out = set()
    for p in glob.glob(os.path.join(KC, "*.json")):
        c = os.path.basename(p)[:-5]
        if len(c) == 6 and c[:2] in pat:
            out.add(c)
    INDEX = {"000300","399001","399006","000688","399005","399100","399101","399106",
             "399300","999999","000010","000009","000012","000016","000905","000906",
             "000852","399008","399330","399673","000698","000090","000013","000011","000002"}
    return out - INDEX

def main():
    t0 = time.time()
    a_codes = get_a_codes()
    print(f"[1] A股代码集合: {len(a_codes)} 只")

    # ---- Phase A: 六维评分 → 352 池（🔴 固定截止日，杜绝前视） ----
    feats = {}
    cutoffs = {}
    for code in a_codes:
        df = load_kline(code)
        if df is None or len(df) < 502:           # 252 特征窗 + 250 回测窗
            continue
        if df["date"].iloc[-1] < "2025-06-01":     # 剔除陈旧数据
            continue
        df = calc_jinzuan(df)                       # 需 DY2 才能算 main
        co = len(df) - 250                          # 🔴 截止日：回测窗口起点（池子在此之前定好）
        f = six_dim_features(df, end_idx=co)
        if f is None:
            continue
        feats[code] = f
        cutoffs[code] = co
    print(f"[2] 有效评分股票: {len(feats)} 只（耗时 {time.time()-t0:.0f}s）")

    fdf = pd.DataFrame(feats).T
    # 横截面归一（🔴 仅状态/资金类六维，不含近期收益排名）
    fdf["s_main"]   = fdf["main"].rank(pct=True) * 100
    fdf["s_mom"]    = fdf["mom"] * 100
    fdf["s_amt"]    = fdf["amt"].rank(pct=True) * 100
    fdf["s_lowvol"] = (1 - fdf["vol"].rank(pct=True)) * 100
    fdf["s_fund"]   = fdf["fund"].rank(pct=True) * 100
    fdf["s_year"]   = fdf["year"] * 100
    fdf["score"]    = fdf[["s_main","s_mom","s_amt","s_lowvol","s_fund","s_year"]].mean(axis=1)
    pool = fdf.sort_values("score", ascending=False).head(352)
    pool_codes = pool.index.tolist()
    json.dump({"updated": "2026-11-08",
               "method": "bias-free: 六维全为状态/资金类维度; 池子特征截至 len-250 固定截止日, 回测仅用其后窗口",
               "pool_size": len(pool_codes),
               "codes": pool_codes,
               "scores": {c: round(float(pool.loc[c, "score"]), 2) for c in pool_codes}},
              open(POOL_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[3] 机构六维352池已定（落 {os.path.basename(POOL_JSON)}）；池内 score 区间 "
          f"{pool['score'].min():.1f}~{pool['score'].max():.1f}")

    # ---- Phase B: 352 池逐股算金钻+紧迫度+双支撑+四档，回测 ----
    dates_map, opens_map, closes_map = {}, {}, {}
    sigs_fib  = {"tier1":[], "tier2":[], "tier3":[], "tier4":[]}
    sigs_vwap = {"tier1":[], "tier2":[], "tier3":[], "tier4":[]}
    daily_snap = []   # 最近一日快照（用于展示）
    ns = [1, 2, 3, 5, 10, 20, 30, 60, 120, 250]
    # 统计四档当日计数（用池内最新一日）
    cnt = {"fib":[0,0,0,0], "vwap":[0,0,0,0]}
    for code in pool_codes:
        df = load_kline(code)
        if df is None or len(df) < 260:
            continue
        df = calc_jinzuan(df)
        df = compute_urgency(df)
        df = compute_supports(df)
        df = compute_tiers(df)
        dates = df["date"].tolist()
        opens = df["open"].tolist()
        closes = df["close"].tolist()
        dates_map[code] = dates; opens_map[code] = opens; closes_map[code] = closes
        start = cutoffs.get(code, 252)   # 🔴 固定截止日，杜绝前视
        for i in range(start, len(df)):
            d = dates[i]
            if df["tier1"].iloc[i]:
                sigs_fib["tier1"].append((code, d)); sigs_vwap["tier1"].append((code, d))
            if df["tier2_fib"].iloc[i]:
                sigs_fib["tier2"].append((code, d))
            if df["tier3_fib"].iloc[i]:
                sigs_fib["tier3"].append((code, d))
            if df["tier4_fib"].iloc[i]:
                sigs_fib["tier4"].append((code, d))
            if df["tier2_vwap"].iloc[i]:
                sigs_vwap["tier2"].append((code, d))
            if df["tier3_vwap"].iloc[i]:
                sigs_vwap["tier3"].append((code, d))
            if df["tier4_vwap"].iloc[i]:
                sigs_vwap["tier4"].append((code, d))
        # 最新一日四档计数
        li = len(df) - 1
        if df["tier1"].iloc[li]: cnt["fib"][0]+=1; cnt["vwap"][0]+=1
        if df["tier2_fib"].iloc[li]: cnt["fib"][1]+=1
        if df["tier3_fib"].iloc[li]: cnt["fib"][2]+=1
        if df["tier4_fib"].iloc[li]: cnt["fib"][3]+=1
        if df["tier2_vwap"].iloc[li]: cnt["vwap"][1]+=1
        if df["tier3_vwap"].iloc[li]: cnt["vwap"][2]+=1
        if df["tier4_vwap"].iloc[li]: cnt["vwap"][3]+=1
        # 最新一日紧迫度 TOP（用于展示，带支撑）
        if df["urg"].iloc[li] >= 70:
            daily_snap.append({
                "code": code, "urg": round(float(df["urg"].iloc[li]), 1),
                "sat": int(df["sat"].iloc[li]), "price": round(float(df["close"].iloc[li]), 2),
                "dist_fib": round(float(df["dist_fib"].iloc[li]), 1) if pd.notna(df["dist_fib"].iloc[li]) else None,
                "dist_vwap": round(float(df["dist_vwap"].iloc[li]), 1) if pd.notna(df["dist_vwap"].iloc[li]) else None,
            })
    print(f"[4] 逐股计算完成（耗时 {time.time()-t0:.0f}s）")

    res_fib  = aggregate(sigs_fib,  dates_map, opens_map, closes_map, ns)
    res_vwap = aggregate(sigs_vwap, dates_map, opens_map, closes_map, ns)
    daily_snap.sort(key=lambda x: -x["urg"])
    out = {
        "updated": "2026-11-08",
        "pool_size": len(pool_codes),
        "tier_counts_latest": cnt,
        "backtest_fib": res_fib,
        "backtest_vwap": res_vwap,
        "daily_snapshot_top": daily_snap[:30],
    }
    json.dump(out, open(BACKTEST_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 打印成绩表 ----
    print("\n========== 💎 金钻跟踪 回测成绩（信号日次开盘买 / 双边0.30% / 352池）==========")
    for sup, res in (("斐波那契重合支撑", res_fib), ("资金加权成本VWAP支撑", res_vwap)):
        print(f"\n--- 支撑口径：{sup} | 最新一日四档计数 ①~④ = {cnt['fib' if sup.startswith('斐波') else 'vwap']} ---")
        for tier in ("tier1","tier2","tier3","tier4"):
            print(f"  [{tier}] 信号数(t+1): {res[tier].get('1d',{}).get('n',0)}")
            for n in (1,2,3,5,10,20,60,120,250):
                k = f"{n}d"; r = res[tier].get(k, {})
                if r.get("n"):
                    print(f"    T+{n:>3}: n={r['n']:>4} 胜率={r['win']:>5}% 均收={r['avg']:>7}% 中位={r['median']:>7}% 最好={r['best']:>7}% 最差={r['worst']:>7}% 回撤={r['mdd']:>7}%")
                else:
                    print(f"    T+{n:>3}: 样本不足")
    print(f"\n[done] 总耗时 {time.time()-t0:.0f}s · 结果落 {os.path.basename(BACKTEST_JSON)}")

if __name__ == "__main__":
    main()
