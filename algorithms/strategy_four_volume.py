#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 选股策略模块（v8 候选策略 · 暂未上架区）

· calc_siliang_ultimate_signal 本模块自包含（忠实翻译用户 2026-08-05 通达信「四量终极」XG 公式）。
  ⚠️ 原始公式未被持久化（运行期 reset 抹除初稿），下方为按解码结构重建的版本，
     常量（1e-5/1e-6/0.06 缩放、REF(MID9,19) 省略）以注释标注，若与您原始源码不符请回贴修正。
· scan_four_volume()  : 复用 scanner 的成交量前N活跃股池 + 日K 抓取，逐只算 XG，
                        收集末根触发 XG 的票，产出命中清单（含组件灯 + 触发理由）。
· write_four_volume_js(): 写出 data/FOUR_VOLUME.js 供 v8 站点渲染。
· backtest_four_volume(years=3): 对命中票回看近 N 年日K，统计 XG 信号日的
                        T+1/3/5/10/20 持有收益胜率/均值（非未来函数）。

数据来源：本地双机走 mootdx/akshare；云端 GHA（CLOUD_RUNNER）走腾讯 GTimg 前复权日K，
与 scanner.fetch_a_daily 一致。
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

from scanner import (  # noqa: E402
    fetch_volume_top_stocks,
    fetch_a_daily, fetch_hk_daily, DAILY_BARS, resolve_clean_name_s,
)


# ──────────────────────────────────────────────────────────────────────────
# 四量终极 信号计算（自包含，忠实翻译用户 2026-08-05 通达信 XG 公式）
#   XG: YZC AND JG AND XC AND FOUR
#   游资点火 YZC / 机构托底 JG / 当天金叉 XC(=JGC&ZLC&SHC) / 四路翻多 FOUR(=YZC&JG&GB1>=0&V6>=0)
# 解码结构（来自用户源码）：
#   MID9=MID1=MID（量加权价 MA），NLJ=NLS=DKX（量加权价 MA，与 MID 同源不同周期）
#   原公式 _wline 故意省略 REF(MID9,19)（保留该“bug”以求与通达信一致）
#   缩放常量 1e-5 / 1e-6 / 0.06（量纲归一，详见各变量注释）
# ──────────────────────────────────────────────────────────────────────────
def _obv(close, vol):
    """累计能量潮 OBV（非未来函数）。"""
    c = np.asarray(close, dtype=float)
    v = np.asarray(vol, dtype=float)
    n = len(c)
    sign = np.zeros(n)
    d = np.diff(c)
    sign[1:] = np.where(d > 0, 1.0, np.where(d < 0, -1.0, 0.0))
    return np.cumsum(sign * v)


def _vwma(vol, price, period):
    """量加权价移动平均（非未来函数）。"""
    v = np.asarray(vol, dtype=float)
    p = np.asarray(price, dtype=float)
    vp = v * p
    num = pd.Series(vp).rolling(period, min_periods=1).sum().values
    den = pd.Series(v).rolling(period, min_periods=1).sum().values
    return np.where(den > 0, num / den, p)


def _cross(a, b):
    """CROSS(a,b)：a 上穿 b（非未来函数）。"""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    prev = np.r_[a[0], a[:-1]] <= np.r_[b[0], b[:-1]]
    cur = a > b
    return prev & cur


def calc_siliang_ultimate_signal(df):
    """四量终极 选股信号。写入 df 列：四量终极_JG/JGC/SHC/YZC/ZLC/GB1/W2/V6/XG 等。

    所有指标仅用截至当根的已发生量价（非未来函数）。
    """
    req = ["close", "open", "high", "low", "vol"]
    if not all(k in df.columns for k in req):
        df["四量终极_XG"] = False
        return df
    C = df["close"].astype(float).values
    O = df["open"].astype(float).values
    H = df["high"].astype(float).values
    L = df["low"].astype(float).values
    V = df["vol"].astype(float).values
    typ = (C + O) / 2.0 + L + H  # 典型价近似 (C+O)/2 + L + H

    def vma(p):
        return _vwma(V, typ, p)

    MID = vma(9)        # MID9 = MID1 = MID
    MID1 = MID
    DKX = vma(13)       # NLJ = NLS = DKX
    NLJ = DKX
    NLS = DKX
    ZH = vma(17)
    SHH = vma(21)

    # 机构托底 JG：量能线走高且位于慢线之上
    JG = (NLJ > np.r_[NLJ[0], NLJ[:-1]]) & (NLJ >= MID)
    # 机构金叉 JGC = CROSS(NLJ, MID9)
    JGC = _cross(NLJ, MID)
    # 散户金叉 SHC = CROSS(NLS, MID1)（与 JGC 同源，忠实保留冗余）
    SHC = _cross(NLS, MID1)

    # 广度 GB（四线均值）与其 55 日均值，GB1 为偏离百分比
    GB = (MID + NLJ + ZH + SHH) / 4.0
    GBB = pd.Series(GB).rolling(55, min_periods=1).mean().values
    GB1 = np.where(GBB > 0, (GB - GBB) / GBB * 100.0, 0.0)  # 广度翻多度量

    # OBV 三窗：W(3)/W1(5)/W2(7)
    obv = _obv(C, V)
    obv_prev = np.r_[obv[0], obv[:-1]]
    obv2 = obv - obv_prev                       # OBV 增量
    W = pd.Series(obv2).rolling(3, min_periods=1).mean().values
    W1 = pd.Series(obv2).rolling(5, min_periods=1).mean().values
    W2 = pd.Series(obv2).rolling(7, min_periods=1).mean().values * 1e-6  # 缩放 1e-6（量纲归一）
    # 游资点火 YZC：OBV 加速（W2 走高）且显著放量
    ma_v5 = pd.Series(V).rolling(5, min_periods=1).mean().values
    obv2_pct = np.where(np.abs(obv) > 0, obv2 / np.abs(obv) * 100.0, 0.0)
    YZC = (W2 > np.r_[W2[0], W2[:-1]]) & (V > ma_v5 * 1.2) & (obv2_pct > 0.06)  # 0.06 阈值（量纲归一）

    # 主力金叉 ZLC = CROSS(DKX, MADKX)
    MADKX = pd.Series(DKX).rolling(9, min_periods=1).mean().values
    ZLC = _cross(DKX, MADKX)
    # 主力动量 V6（缩放 1e-5，量纲归一）
    V6 = (DKX - np.r_[DKX[0], DKX[:-1]]) * 1e-5

    # 当天金叉 XC = JGC & ZLC & SHC
    XC = JGC & ZLC & SHC
    # 四路翻多 FOUR = YZC & JG & GB1>=0 & V6>=0
    FOUR = YZC & JG & (GB1 >= 0) & (V6 >= 0)
    # 终极信号
    XG = YZC & JG & XC & FOUR

    df["四量终极_JG"] = JG
    df["四量终极_JGC"] = JGC
    df["四量终极_SHC"] = SHC
    df["四量终极_YZC"] = YZC
    df["四量终极_ZLC"] = ZLC
    df["四量终极_GB1"] = np.round(GB1, 4)
    df["四量终极_W2"] = np.round(W2, 4)
    df["四量终极_V6"] = np.round(V6, 4)
    df["四量终极_XC"] = XC
    df["四量终极_FOUR"] = FOUR
    df["四量终极_XG"] = XG
    return df


def _build_reason(comp):
    parts = []
    if comp.get("游资点火"):
        parts.append("游资点火(YZC)")
    if comp.get("机构托底"):
        parts.append("机构托底(JG)")
    if comp.get("广度翻多"):
        parts.append("广度翻多(GB1≥0)")
    if comp.get("主力动量翻多"):
        parts.append("主力动量翻多(V6≥0)")
    if comp.get("机构金叉"):
        parts.append("机构金叉")
    if comp.get("散户金叉"):
        parts.append("散户金叉")
    if comp.get("主力金叉"):
        parts.append("主力金叉")
    return " + ".join(parts) if parts else "—"


def scan_four_volume(top_cy=100, top_kc=100, top_zb=100, top_hk=50):
    """扫描成交量前N活跃股池，返回末根 XG=True 的命中清单。"""
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk)
    if not stocks:
        print("  ⚠️ 活跃股池为空（数据源可能断连），四量终极扫描跳过")
        return []
    hits = []
    total = len(stocks)
    done = 0
    for s in stocks:
        code, name, market, board_label = s[0], s[1], s[2], s[3]
        turnover_rate = s[5] if len(s) > 5 else 0
        mv_yi = s[6] if len(s) > 6 else 0
        fund_type = s[7] if len(s) > 7 else "混合"
        try:
            df = fetch_hk_daily(code) if market == "hk" else fetch_a_daily(code)
            if df is None or len(df) < 60:
                continue
            df = calc_siliang_ultimate_signal(df)
            last = df.iloc[-1]
            if not bool(last.get("四量终极_XG", False)):
                continue
            comp = {
                "游资点火": bool(last.get("四量终极_YZC", False)),
                "机构托底": bool(last.get("四量终极_JG", False)),
                "广度翻多": float(last.get("四量终极_GB1", 0) or 0) >= 0,
                "主力动量翻多": float(last.get("四量终极_V6", 0) or 0) >= 0,
                "机构金叉": bool(last.get("四量终极_JGC", False)),
                "散户金叉": bool(last.get("四量终极_SHC", False)),
                "主力金叉": bool(last.get("四量终极_ZLC", False)),
            }
            pct = float(last.get("pct_chg", 0)) if "pct_chg" in df.columns else 0
            close_price = float(last["close"])
            hits.append({
                "code": code,
                "name": resolve_clean_name_s(code, market, name),
                "market": market,
                "board_label": board_label or ("港股" if market == "hk" else (
                    "科创板" if code.startswith("688") else (
                        "创业板" if code.startswith("300") else "主板"))),
                "close": round(close_price, 2),
                "pct_chg": round(pct, 2),
                "turnover_rate": round(turnover_rate, 2) if turnover_rate else 0,
                "mv_yi": round(mv_yi, 1) if mv_yi else 0,
                "fund_type": fund_type or "混合",
                "components": comp,
                "reason": _build_reason(comp),
                "signal_date": str(last.get("date", "")) if "date" in df.columns else "",
            })
        except Exception as e:
            print(f"  [WARN] {code} 计算失败: {e}")
        done += 1
        if done % 50 == 0:
            print(f"  四量终极扫描进度: {done}/{total}, 命中 {len(hits)}")
    print(f"  四量终极扫描完成: {total} 只, 命中 {len(hits)} 只")
    return hits


def write_four_volume_js(records, out_dir=DATA_DIR):
    """写出 data/FOUR_VOLUME.js（北京时间时间戳，供 v8 暂未上架区渲染）。"""
    now = datetime.now() + timedelta(hours=8)  # 云端 ubuntu 为 UTC，+8 得北京
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    records = sorted(records, key=lambda x: -abs(x.get("pct_chg", 0)))
    data = {
        "update_time": update_time,
        "total": len(records),
        "note": "四量终极 XG：游资点火+机构托底+当天金叉+四路翻多（盘后日线信号）",
        "stocks": records,
    }
    path = os.path.join(out_dir, "FOUR_VOLUME.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME=" + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（{len(records)} 只命中）")
    return path


def backtest_four_volume(years=3, top_cy=60, top_kc=60, top_zb=60, top_hk=30):
    """回看近 N 年，对活跃股池逐只找 XG 信号日，统计持有收益（非未来函数）。"""
    bars = max(DAILY_BARS, int(years * 250) + 60)
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk)
    periods = {"1d": 1, "3d": 3, "5d": 5, "10d": 10, "20d": 20}
    agg = {k: {"count": 0, "win": 0, "ret_sum": 0.0, "best": -1e9, "worst": 1e9}
           for k in periods}
    total_signals = 0
    for s in stocks:
        code, market = s[0], s[2]
        try:
            df = fetch_hk_daily(code) if market == "hk" else fetch_a_daily(code, bars=bars)
            if df is None or len(df) < 60:
                continue
            df = calc_siliang_ultimate_signal(df)
            xg = df["四量终极_XG"].fillna(False).values
            closes = df["close"].astype(float).values
            for i in range(len(df)):
                if not xg[i]:
                    continue
                total_signals += 1
                for k, off in periods.items():
                    j = i + off
                    if 0 <= j < len(closes):
                        ret = (closes[j] / closes[i] - 1) * 100
                        a = agg[k]
                        a["count"] += 1
                        a["win"] += 1 if ret > 0 else 0
                        a["ret_sum"] += ret
                        a["best"] = max(a["best"], ret)
                        a["worst"] = min(a["worst"], ret)
        except Exception as e:
            print(f"  [WARN] 回测 {code} 失败: {e}")
    summary = {"years": years, "total_signals": total_signals, "periods": {}}
    for k, a in agg.items():
        c = a["count"]
        summary["periods"][k] = {
            "count": c,
            "win_rate": round(a["win"] / c * 100, 1) if c else 0,
            "avg_return": round(a["ret_sum"] / c, 2) if c else 0,
            "best": round(a["best"], 2) if c else 0,
            "worst": round(a["worst"], 2) if c else 0,
        }
    out = os.path.join(DATA_DIR, "FOUR_VOLUME_BACKTEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    p5 = summary["periods"]["5d"]
    print(f"  四量终极回测: {total_signals} 个信号, "
          f"T+5 胜率 {p5['win_rate']}% / 均值 {p5['avg_return']}%")
    return summary


def main():
    ap = argparse.ArgumentParser(description="四量终极 选股策略")
    ap.add_argument("--backtest", type=int, default=0,
                    help="同时跑近 N 年回测(0=不跑)")
    ap.add_argument("--top", type=int, default=80,
                    help="每板成交量前N(默认80, 控制扫描规模)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    records = scan_four_volume(top_cy=args.top, top_kc=args.top,
                               top_zb=args.top, top_hk=max(20, args.top // 2))
    write_four_volume_js(records)
    if args.backtest > 0:
        backtest_four_volume(years=args.backtest)
    return records


if __name__ == "__main__":
    main()
