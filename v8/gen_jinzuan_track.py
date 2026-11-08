#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8/gen_jinzuan_track.py — 💎 大资金买点三样·金钻跟踪（v8 日更监控管线 · 非盈利信号）
================================================================================
主人令（2026-11-08）：演示卡「大资金买点三档·金钻跟踪」由参考图还原的硬编码 demo，
  升级为 v8 自己的真实管线：机构六维 352 池 + 金钻起涨(XMA 复现·因果) + 多周期黄金分割支撑
  + 金钻紧迫度(六条件接近度加权) + 四档（确认/价格/临近/蓄势），日更并跟踪显示。

⚠️ 性质（与用户约定「只做跟踪监控·不做买点」一致）：
  本卡是**监控/跟踪**展示，不是选股买点算法。回测已证该信号无稳定盈利边缘
  （胜率≈硬币、中位不赚），故数据内嵌 honest backtest 摘要，前端如实标注「监控用途·非盈利信号」。

管线（与 v8 其它 data/*.js 同源）：
  · 读固定「机构六维 352 池」raw_data/jinzuan_pool.json（含 name，本地一次性 build，无需每日 akshare）
  · 对池中每只票用本地 raw_data/kline_cache/*.json 计算**最新一日**金钻起涨/紧迫度/支撑/四档
  · 产出 data/JINZUAN_TRACK.js → window.JINZUAN_TRACK，由 index.html 选股策略页「💎 金钻跟踪」子TAB 读取
  · 前端以 window.X 注入读取，禁止 fetch('../data/...')（v8 铁律）

铁律（对齐回测根因修复）：
  · 金钻趋势/金牛线一律用**因果 XMA（xma_causal, trailing）**，与回测一致，杜绝居中 XMA 的未来函数泄漏
  · 全程 pandas/numpy + 本地 kline_cache，不联网抓取（对齐 V8_NO_NET 精神，CI 离线可跑）
  · 仅算最新一根 bar（last-bar-only），O(1)/股，避免全序列回测开销，日更秒级

依赖：pandas, numpy（ubuntu-latest 标准安装；name 已预置池内，无需 akshare）
用法：
  python v8/gen_jinzuan_track.py              # 读池 → 算最新一日 → 写 data/JINZUAN_TRACK.js
  python v8/gen_jinzuan_track.py --rebuild-pool   # 先用 akshare 重建 352 池（含 name）再生成
"""
import json, os, sys, glob, time, argparse
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
RAW  = os.path.join(REPO, "raw_data")
KC   = os.path.join(RAW, "kline_cache")
POOL_JSON = os.path.join(RAW, "jinzuan_pool.json")
OUT  = os.path.join(REPO, "data", "JINZUAN_TRACK.js")

# ============================== 金钻原语（移植自 scanner.py，因果 XMA） ==============================
def ref(series, n):
    return series.shift(int(n) if pd.notna(n) else 0)

def sma_tdx(series, n, m):
    arr = series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    if len(arr) == 0:
        return pd.Series(out, index=series.index)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = (arr[i] * m + out[i-1] * (n - m)) / n
    return pd.Series(out, index=series.index)

def xma_causal(series, n):
    """✅ 因果 XMA（trailing）—— 仅用过去+当日，无未来泄漏。线上末根与居中 XMA 等价。"""
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
    for c in ("open", "close", "high", "low", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = df["date"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    return df

def calc_jinzuan(df):
    """复现 scanner.calc_jinzuan_signal；因果 XMA 版，无未来泄漏。"""
    H = df["high"]; L = df["low"]; C = df["close"]; O = df["open"]
    V = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)
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

# ============================== 金钻紧迫度（六条件接近度加权） ==============================
TOL = {1: 0.05, 3: 0.08, 4: 0.05, 5: 0.08, 6: 0.08}
W   = {1: 1.0, 2: 0.8, 3: 1.3, 4: 1.3, 5: 1.0, 6: 1.0}
WSUM = sum(W.values())
COND_LABEL = {1: "收阳 C>O", 2: "资金流 DY2<0.02", 3: "趋势 MA5>MA60",
              4: "涨幅≥2%", 5: "最高价 H<金牛线", 6: "最低价 L<金钻趋势"}

def last_urgency(df):
    """仅算最新一根 bar 的紧迫度/满足数/未满足条件（O(1)），杜绝全序列回测开销。"""
    i = len(df) - 1
    C = df["close"]; O = df["open"]; H = df["high"]; L = df["low"]
    MA5 = ma(C, 5).iloc[i]; MA60 = ma(C, 60).iloc[i]
    DY2 = df["DY2"]
    c1 = float(C.iloc[i]); o1 = float(O.iloc[i]); h1 = float(H.iloc[i]); l1 = float(L.iloc[i])
    # c1 收阳
    prox1 = 1.0 if c1 > o1 else max(0.0, min(1.0, 1 - (o1 - c1) / c1 / TOL[1]))
    # c3 趋势
    gap3 = (MA60 - MA5) / MA5 if MA5 else 0
    prox3 = 1.0 if MA5 > MA60 else max(0.0, min(1.0, 1 - gap3 / TOL[3]))
    # c4 涨幅≥2%
    r4 = c1 / float(ref(C, 1).iloc[i]) if ref(C, 1).iloc[i] else 1.0
    gap4 = 1.02 - r4
    prox4 = 1.0 if r4 >= 1.02 else max(0.0, min(1.0, 1 - gap4 / TOL[4]))
    # c5 最高价 H<金牛线
    jn = float(df["金牛"].iloc[i]); jq = float(df["金钻趋势"].iloc[i])
    gap5 = (h1 - jn) / jn if jn else 0
    prox5 = 1.0 if h1 < jn else max(0.0, min(1.0, 1 - gap5 / TOL[5]))
    # c6 最低价 L<金钻趋势线
    gap6 = (l1 - jq) / jq if jq else 0
    prox6 = 1.0 if l1 < jq else max(0.0, min(1.0, 1 - gap6 / TOL[6]))
    # c2 资金流 DY2<0.02：取过去≤120日（min 60）DY2，pct=≤末值占比，接近度=1-pct
    w = DY2.iloc[max(0, i-119):i+1].dropna()
    if len(w) >= 60:
        pct = float((w <= w.iloc[-1]).mean())
        mn = float(w.min())
        prox2 = 0.0 if mn > 0.02 else max(0.0, min(1.0, 1 - pct))
    else:
        prox2 = 0.0
    prox = {1: prox1, 2: prox2, 3: prox3, 4: prox4, 5: prox5, 6: prox6}
    urg = sum(W[k] * prox[k] for k in range(1, 7)) / WSUM * 100
    sat = sum(1 for k in range(1, 7) if prox[k] >= 0.5)
    unmet = [COND_LABEL[k] for k in range(1, 7) if prox[k] < 0.5]
    return round(urg, 1), sat, unmet

def last_supports(df):
    """仅算最新一根 bar 的多周期黄金分割(fib) + VWAP 支撑与距撑%。"""
    i = len(df) - 1
    C = df["close"]; H = df["high"]; L = df["low"]; V = df["volume"]
    c = float(C.iloc[i])
    fibs, vws = [], []
    for W_ in (60, 120, 252):
        s = max(0, i - W_ + 1)
        if i - s + 1 < 20:
            continue
        sh = H.iloc[s:i+1]; sl = L.iloc[s:i+1]; sc = C.iloc[s:i+1]; sv = V.iloc[s:i+1]
        hmax = float(sh.max()); lmin = float(sl.min()); rng = hmax - lmin
        levels = [hmax - rng * r for r in (0.382, 0.5, 0.618)]
        below = [lv for lv in levels if lv <= c]
        fibs.append(max(below) if below else min(levels))
        vws.append(float((sc * sv).sum() / sv.sum()) if sv.sum() > 0 else np.nan)
    sup_fib = max(fibs) if fibs else np.nan
    sup_vwap = max(vws) if vws else np.nan
    dist_fib = (c - sup_fib) / c * 100 if pd.notna(sup_fib) else None
    dist_vwap = (c - sup_vwap) / c * 100 if pd.notna(sup_vwap) else None
    return (round(float(sup_fib), 2) if pd.notna(sup_fib) else None,
            round(float(dist_fib), 1) if pd.notna(sup_fib) else None,
            round(float(sup_vwap), 2) if pd.notna(sup_vwap) else None,
            round(float(dist_vwap), 1) if pd.notna(sup_vwap) else None)

def market_of(code):
    if code.startswith("688") or code.startswith("8") or code.startswith("4"):
        return "科/创"
    if code.startswith("60"):
        return "沪"
    if code.startswith(("00", "30")):
        return "深"
    return "其他"

def jnum(x):
    """NaN/inf → None（JSON 安全）。"""
    try:
        if x is None:
            return None
        f = float(x)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except Exception:
        return None

# ============================== 机构六维评分（仅状态/资金类，无前视） ==============================
def six_dim_features(df, end_idx=None):
    C = df["close"]; V = df["volume"]
    n = len(df)
    e = n if end_idx is None else min(end_idx, n)
    if e < 252:
        return None
    seg = df.iloc[e-252:e]
    d = seg["DY2"].dropna()
    main = float((d < 0).mean()) if len(d) else 0.0
    ma20 = ma(C, 20).iloc[e-1]; ma60 = ma(C, 60).iloc[e-1]; ma250 = ma(C, 250).iloc[e-1]
    mom = 1.0 if (C.iloc[e-1] > ma20 and ma20 > ma60) else (0.5 if C.iloc[e-1] > ma20 else 0.0)
    above_year = 1.0 if C.iloc[e-1] > ma250 else 0.0
    amt = float((seg["close"] * seg["volume"]).mean())
    rets = C.pct_change().iloc[e-252:e]
    vol = float(rets.std()) if len(rets.dropna()) else 0.0
    fund = float(d.tail(20).mean() - d.head(100).mean()) if len(d) >= 120 else 0.0
    return {"main": main, "mom": mom, "amt": amt, "vol": vol, "fund": fund, "year": above_year}

def get_a_codes():
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        codes = set(df["code"].astype(str).tolist())
        names = {str(r["code"]): str(r["name"]) for _, r in df.iterrows()}
        if codes:
            return codes, names
    except Exception as e:
        print("  [warn] akshare A股列表获取失败，回退正则过滤:", e)
    pat = ("60", "68", "00", "30", "8", "4")
    out = set(); names = {}
    for p in glob.glob(os.path.join(KC, "*.json")):
        c = os.path.basename(p)[:-5]
        if len(c) == 6 and c[:2] in pat:
            out.add(c)
    return out, names

def build_pool():
    """本地一次性：机构六维 352 池（含 name），固定截止日 len-250，写 raw_data/jinzuan_pool.json。"""
    t0 = time.time()
    a_codes, names = get_a_codes()
    print(f"[pool] A股代码集合: {len(a_codes)} 只")
    feats = {}
    for code in a_codes:
        df = load_kline(code)
        if df is None or len(df) < 502:
            continue
        if df["date"].iloc[-1] < "2025-06-01":
            continue
        df = calc_jinzuan(df)
        co = len(df) - 250
        f = six_dim_features(df, end_idx=co)
        if f is None:
            continue
        feats[code] = f
    print(f"[pool] 有效评分股票: {len(feats)} 只（耗时 {time.time()-t0:.0f}s）")
    fdf = pd.DataFrame(feats).T
    fdf["s_main"]   = fdf["main"].rank(pct=True) * 100
    fdf["s_mom"]    = fdf["mom"] * 100
    fdf["s_amt"]    = fdf["amt"].rank(pct=True) * 100
    fdf["s_lowvol"] = (1 - fdf["vol"].rank(pct=True)) * 100
    fdf["s_fund"]   = fdf["fund"].rank(pct=True) * 100
    fdf["s_year"]   = fdf["year"] * 100
    fdf["score"]    = fdf[["s_main", "s_mom", "s_amt", "s_lowvol", "s_fund", "s_year"]].mean(axis=1)
    pool = fdf.sort_values("score", ascending=False).head(352)
    recs = [{"code": c, "name": names.get(c, ""), "score": round(float(pool.loc[c, "score"]), 2)}
            for c in pool.index]
    json.dump({"updated": time.strftime("%Y-%m-%d"),
               "method": "bias-free: 六维全为状态/资金类维度; 池子特征截至 len-250 固定截止日",
               "pool_size": len(recs), "stocks": recs},
              open(POOL_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[pool] 机构六维 352 池已定 → {os.path.basename(POOL_JSON)}；score {pool['score'].min():.1f}~{pool['score'].max():.1f}")
    return recs

# ============================== 主流程：算最新一日 → 写 data/JINZUAN_TRACK.js ==============================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-pool", action="store_true", help="先用 akshare 重建 352 池（含 name）")
    args = ap.parse_args()
    t0 = time.time()
    if args.rebuild_pool or not os.path.exists(POOL_JSON):
        pool = build_pool()
    else:
        try:
            pool = json.load(open(POOL_JSON, encoding="utf-8"))["stocks"]
        except Exception:
            pool = build_pool()
    print(f"[main] 载入池: {len(pool)} 只")

    tiers = {"confirm": [], "price": [], "near": [], "acc": []}
    top = []
    data_dates = []
    for rec in pool:
        code = rec["code"]; name = rec.get("name", "")
        df = load_kline(code)
        if df is None or len(df) < 260:
            continue
        df = calc_jinzuan(df)
        urg, sat, unmet = last_urgency(df)
        sup_fib, dist_fib, sup_vwap, dist_vwap = last_supports(df)
        i = len(df) - 1
        price = round(float(df["close"].iloc[i]), 2)
        v5 = df["volume"].iloc[max(0, i-5):i].mean()
        vi = float(df["volume"].iloc[i])
        vr = round(vi / v5, 2) if v5 and v5 > 0 else None
        is_confirm = bool(df["金钻起涨"].iloc[i])
        # 四档（与演示卡 / 回测同阈值）
        if is_confirm:
            tier = "confirm"
        elif (dist_fib is not None and dist_fib <= 3.5 and urg >= 78 and sat >= 4):
            tier = "price"
        elif (dist_fib is not None and dist_fib <= 8.0 and urg >= 75 and sat >= 3):
            tier = "near"
        elif (urg >= 85 and sat >= 4 and (dist_fib is None or dist_fib > 8.0)):
            tier = "acc"
        else:
            tier = None
        rec_out = {
            "code": code, "name": name, "mkt": market_of(code),
            "price": price, "urg": urg, "sat": sat,
            "tier": tier,
            "sup_fib": sup_fib, "dist_fib": dist_fib,
            "sup_vwap": sup_vwap, "dist_vwap": dist_vwap,
            "vr": vr, "unmet": unmet,
            "date": df["date"].iloc[i],
        }
        if tier:
            tiers[tier].append(rec_out)
        top.append(rec_out)
        data_dates.append(df["date"].iloc[i])

    # 各档按紧迫度降序
    for k in tiers:
        tiers[k].sort(key=lambda x: -x["urg"])
    top.sort(key=lambda x: -x["urg"])
    top30 = top[:30]
    cnt = {k: len(tiers[k]) for k in tiers}
    data_date = max(data_dates) if data_dates else time.strftime("%Y-%m-%d")

    payload = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": data_date,
        "pool_size": len(pool),
        "monitor_only": True,
        "tier_counts": cnt,
        "tiers": tiers,
        "top": top30,
        "calib": "基于「大资金（机构六维）股池」352 只，金钻起涨（XMA 复现·因果）与多周期黄金分割"
                 "（60/120/252 日）合成，与股东加仓《买点三档》同阈值同分档——"
                 "①确认买点：金钻起涨当日触发；②价格买点：现价回踩多周期重合支撑(≤3.5%)且紧迫度≥78、满足≥4/6；"
                 "③临近买点：价格近支撑(≤8%)且紧迫度≥75、满足≥3/6；④蓄势：紧迫度≥85、满足≥4/6 但价未回支撑。",
        "note": "监控用途·非盈利信号：回测实证该信号无稳定超额收益（胜率≈硬币、中位不赚），"
                "本卡仅跟踪机构六维股池内金钻紧迫度与四档分布，不构成投资建议。",
        "backtest": {
            "dated": "2026-11-08",
            "method": "352池·信号日次开盘买·双边0.30%·因果XMA(非未来函数)",
            "verdict": "无稳定盈利边缘：tier1 确认买点仅 21 信号，T+1~T+10 胜率 33-48%、中位为负；"
                       "tier2/3 价格/临近约 1.1万/1.8万信号，胜率 43-49%（近似硬币），T+60/T+120 正均收来自"
                       "肥尾+幸存者偏差（中位≈0/负）。本卡仅作监控跟踪，非买卖建议。",
            "tier1": {"n": 21, "T1_win": 38.1, "T1_avg": -0.5, "T10_win": 47.6, "T10_avg": 0.52,
                      "T60_win": 25.0, "T60_avg": -3.55, "T120_win": 62.5, "T120_avg": 9.64},
            "tier2_fib": {"n": 11203, "T1_win": 42.8, "T1_avg": -0.26, "T60_win": 49.0, "T120_avg": 15.26,
                          "median_T60": -0.37, "best_T60": 816.57},
            "tier3_fib": {"n": 17798, "T1_win": 42.8, "T1_avg": -0.29, "T60_win": 48.8, "T120_avg": 15.73,
                          "median_T60": -0.5},
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.JINZUAN_TRACK = " + json.dumps(payload, ensure_ascii=False) + ";\n")
    sz = os.path.getsize(OUT)
    print(f"[main] 产出 {os.path.basename(OUT)}（{sz} B）数据日 {data_date}")
    print(f"       四档计数 ①确认={cnt['confirm']} ②价格={cnt['price']} ③临近={cnt['near']} ④蓄势={cnt['acc']}"
          f" ｜ TOP30 就绪 ｜ 总耗时 {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
