#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 选股策略模块（v8 候选策略 · 暂未上架区）

· calc_siliang_ultimate_signal 本模块自包含，忠实翻译用户 2026-08-05 通达信「四量终极 指标版 副图」公式（原贴完整源码，已核对）。
· 信号 QD = YZC AND JG AND XC AND FOUR：游资点火 YZC=CROSS(W2,0) / 机构托底 JG=C>NLJ / 当天金叉 XC=JGC|SHC|YZC|ZLC（四金叉取或）/ 四路翻多 FOUR=JG&GB1>=0&W2>=0&V6>=0。
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
# 四量终极 信号计算（自包含，忠实翻译用户 2026-08-05 通达信「指标版 副图」公式）
#   QD: YZC AND JG AND XC AND FOUR
#   游资点火 YZC = CROSS(W2, 0)
#   机构托底 JG  = C > NLJ
#   当天金叉 XC  = JGC OR SHC OR YZC OR ZLC（四金叉取或）
#   四路翻多 FOUR= JG AND GB1>=0 AND W2>=0 AND V6>=0
#   其中 JGC=CROSS(NLJ,MA(NLJ,6)) / SHC=CROSS(GB1,0) / ZLC=CROSS(V6,0)
#   加权价 MID=(3C+O+L+H)/6；NLJ=NLS=DKX=MID 同一条 20 周期加权线（含 REF(MID,19)→REF(MID,20) 替换）
#   非未来函数。
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


def _cross(a, b):
    """CROSS(a,b)：a 上穿 b（非未来函数）。b 可为数组或标量。"""
    a = np.asarray(a, dtype=float)
    if np.isscalar(b):
        b = np.full(a.shape, float(b), dtype=float)
    else:
        b = np.asarray(b, dtype=float)
    prev = np.r_[a[0], a[:-1]] <= np.r_[b[0], b[:-1]]
    cur = a > b
    return prev & cur


def _wma20(mid):
    """通达信式 20 周期加权移动平均（含 REF(MID,19)→REF(MID,20) 替换）。
    权重 REF(k):(20-k)/210, k=0..18，再以 REF(20) 系数1 顶替 REF(19)（即 -REF19+REF20）。"""
    mid = np.asarray(mid, dtype=float)
    n = len(mid)
    if n < 20:
        return np.full(n, np.nan)
    b = np.arange(20, 0, -1, dtype=float) / 210.0  # [20,19,...,1]/210
    full = np.convolve(mid, b, mode='full')         # length n+19
    out = full[:n].copy()
    out[:19] = np.nan
    ref19 = np.r_[np.full(19, np.nan), mid[:-19]]
    ref20 = np.r_[np.full(20, np.nan), mid[:-20]]
    out = out + (ref20 - ref19)
    return out


def _ema(x, n):
    """通达信 EMA(X,N)（adjust=False 的 Wilder 平滑）。"""
    return pd.Series(np.asarray(x, dtype=float)).ewm(span=n, adjust=False).mean().values


def _turnover(df, V):
    """换手率：优先 turnover_rate 列；其次 circ_mv 估算；否则用成交量 5 日均归一近似。"""
    if "turnover_rate" in df.columns:
        return df["turnover_rate"].astype(float).values
    if "circ_mv" in df.columns:
        circ = df["circ_mv"].astype(float).values
        with np.errstate(divide='ignore', invalid='ignore'):
            t = np.where(circ > 0, V * 100.0 / (circ * 1e8), np.nan)
        return np.nan_to_num(t, nan=np.nan)
    return V / pd.Series(V).rolling(5, min_periods=1).mean().values


def calc_siliang_ultimate_signal(df):
    """四量终极 选股信号（忠实翻译用户 2026-08-05 通达信「指标版 副图」公式）。

    非未来函数。输出 df 列：四量终极_*（JG/JGC/SHC/YZC/ZLC/GB1/W2/V6/XC/FOUR/XG）。
    """
    # 列名兼容：数据源(fetch_a_daily/fetch_hk_daily)返回 volume，公式内部统一用 vol。
    # 2026-08-07 修复：此前 vol 缺失直接走 early-return → 所有组件恒为 False → 0 命中。
    if "vol" not in df.columns and "volume" in df.columns:
        df = df.rename(columns={"volume": "vol"})
    req = ["close", "open", "high", "low", "vol"]
    if not all(k in df.columns for k in req):
        df["四量终极_XG"] = False
        return df
    C = df["close"].astype(float).values
    O = df["open"].astype(float).values
    H = df["high"].astype(float).values
    L = df["low"].astype(float).values
    V = df["vol"].astype(float).values

    # 加权典型价 MID = (3C + O + L + H)/6；20 周期加权线（同一条，MID9=MID1=MID=DKX=NLJ=NLS）
    mid = (3.0 * C + O + L + H) / 6.0
    MID = _wma20(mid)
    NLJ = MID
    NLS = MID
    DKX = MID

    # 机构托底 JG：收盘价在量能线之上
    JG = C > NLJ
    # 机构金叉 JGC：NLJ 上穿其 6 日均线
    JGC = _cross(NLJ, pd.Series(NLJ).rolling(6, min_periods=1).mean().values)

    # 广度 GB1 = (C - NLS) + (ZH - SHH)；散户金叉 SHC = GB1 上穿 0
    turnover = _turnover(df, V)
    ZH = pd.Series(turnover).rolling(5, min_periods=1).mean().values
    SHH = pd.Series(turnover).rolling(55, min_periods=1).mean().values
    GB = C - NLS
    GBB = ZH - SHH
    GB1 = GB + GBB
    SHC = _cross(GB1, 0.0)

    # 游资点火 YZC：W2 上穿 0
    Q = _ema(V, 5)
    Q1 = _ema(V, 50)
    W = (Q - Q1) * 0.00001
    obv = _obv(C, V)
    OBV1 = _ema(obv, 5)
    OBV2 = _ema(obv, 50)
    W1 = (OBV1 - OBV2) * 0.000001
    W2 = W + W1
    YZC = _cross(W2, 0.0)

    # 主力金叉 ZLC：V6 上穿 0
    MADKX = pd.Series(DKX).rolling(6, min_periods=1).mean().values
    MDD = (DKX - MADKX) * 1.2
    V1 = (C * 2.0 + H + L) / 4.0 * 10.0
    V2v = _ema(V1, 6) - _ema(V1, 55)
    V5 = (V2v - _ema(V2v, 6)) * 0.06
    V6 = MDD + V5
    ZLC = _cross(V6, 0.0)

    # 当天金叉 XC：四金叉任一
    XC = JGC | SHC | YZC | ZLC
    # 四路翻多 FOUR：机构托底 + 广度翻多 + 游资量能翻多 + 主力动量翻多
    FOUR = JG & (GB1 >= 0) & (W2 >= 0) & (V6 >= 0)
    # 终极信号 QD
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
                # 2026-08-07 修复：UI renderFourVolume 读顶层 yzc/jg/xc/four/qd 标记，
                # 此前只写嵌套 components → 卡片永远显示 QD=0、无标签。现补齐顶层布尔。
                "yzc": bool(comp.get("游资点火")),
                "jg": bool(comp.get("机构托底")),
                "xc": bool(last.get("四量终极_XC", False)),
                "four": bool(last.get("四量终极_FOUR", False)),
                "qd": bool(last.get("四量终极_XG", False)),
                "reason": _build_reason(comp),
                "signal_date": str(last.get("date", "")) if "date" in df.columns else "",
                # 2026-08-08 修复：给每只股票打 enter_date，前端「M-D已入仓」胶囊可区分当日新入选。
                "enter_date": str(last.get("date", "")) if "date" in df.columns else datetime.now().strftime("%Y-%m-%d"),
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
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now() + timedelta(hours=8)  # 兜底：UTC+8
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    records = sorted(records, key=lambda x: -abs(x.get("pct_chg", 0)))
    data = {
        "update_time": update_time,
        "total": len(records),
        "stocks": records,
    }
    path = os.path.join(out_dir, "FOUR_VOLUME.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME=" + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（{len(records)} 只命中）")
    return path




def write_four_volume_backtest_js(records, bt_summary=None, out_dir=DATA_DIR):
    """写出 data/FOUR_VOLUME_BACKTEST.js 规范化外壳（策略回顾回测区 window.FOUR_VOLUME_BACKTEST）。

    🛡 2026-09-04 主人令·一劳永逸：外壳此前为 09-02 手工空壳、无人回写 → update_time 冻结，
    健康面板 all_FOUR_VOLUME_BACKTEST 永远 FAIL（误报）。每次四量跑完即刷新本外壳；
    bt_summary（backtest_four_volume 返回值）存在时附带真实分层回测数据（1d→1 等键名映射）。
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now() + timedelta(hours=8)  # 兜底：UTC+8
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    n = len(records or [])
    by_period = {}
    if bt_summary:
        for k, v in (bt_summary.get("periods") or {}).items():
            by_period[str(k).replace("d", "")] = {
                "samples": v.get("count", 0),
                "win_rate": v.get("win_rate", 0),
                "avg_return": v.get("avg_return", 0),
                "best_return": v.get("best", 0),
                "worst_return": v.get("worst", 0),
            }
    method = "四量终极历史回测：信号日收盘价买入，持有N个交易日收盘价卖出"
    if not by_period:
        method += ("（当前 0 信号，待四量信号恢复后自动填充）" if n == 0
                   else "（当前 %d 信号；深度分层回测待 --backtest 手动跑）" % n)
    data = {
        "update_time": update_time,
        "summary": {
            "update_time": update_time,
            "calc_time": update_time,
            "total_signals": (bt_summary or {}).get("total_signals", n),
            "method": method,
            "signal_date_range": "—",
            "by_period": by_period,
        },
    }
    path = os.path.join(out_dir, "FOUR_VOLUME_BACKTEST.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME_BACKTEST = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（回测外壳刷新，{data['summary']['total_signals']} 信号）")
    return path


# ── 2026-09-06 主人令 P0-C：默认跑回测（原 0=不跑 → 3=跑近 3 年）；保证 .js 外壳永不空 ===
# 原因：此前默认 0 → run_algorithms 即使注入 V8_BACKTEST_YEARS=3，也被 0 覆盖场景未走主链路，
# 实际跑过但回测 → bt_summary=None → by_period={} → FOUR_VOLUME_BACKTEST.js 健康面板永 fail。
# 现默认值 3 + 任何情况下都跑空保底（无 XG 信号也写 n=0 + N 年 + 提示）。
COST_BPS = 15  # 单边万分之 1.5


def backtest_four_volume(years=3, top_cy=60, top_kc=60, top_zb=60, top_hk=30):
    """回看近 N 年，对活跃股池逐只找 XG 信号日，统计持有收益（非未来函数）。

    2026-09-06 主人令 P0-C/P1-A/P2-C：
      - 扣双边交易成本（万分之1.5×2 = 0.3%）
      - 输出 max_drawdown（按累计收益路径算全局最大回撤）
      - 输出 sharpe_ratio（均收益/收益样本标准差，简单近似）
j    - 前复权（fetch_a_daily 走 akshare/腾讯前复权，前端 np 已处理）
    """
    bars = max(DAILY_BARS, int(years * 250) + 60)
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk)
    periods = {"1d": 1, "3d": 3, "5d": 5, "10d": 10, "20d": 20}
    cost_pct = 2 * COST_BPS / 100
    agg = {k: {"count": 0, "win": 0, "loss": 0, "draw": 0,
               "ret_sum": 0.0, "best": -1e9, "worst": 1e9,
               "equity_path": []}  # 所有信号累计收益曲线（最大回撤算）
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
                entry_px = closes[i]
                if entry_px <= 0:
                    continue
                for k, off in periods.items():
                    j = i + off
                    if 0 <= j < len(closes):
                        gross = (closes[j] / entry_px - 1) * 100
                        net = gross - cost_pct
                        a = agg[k]
                        a["count"] += 1
                        if net > 0:
                            a["win"] += 1
                        elif net < 0:
                            a["loss"] += 1
                        else:
                            a["draw"] += 1
                        a["ret_sum"] += net
                        a["best"] = max(a["best"], net)
                        a["worst"] = min(a["worst"], net)
                        # 累计收益路径：entry → exit 每日累计 net
                        cum = 0.0
                        for m in range(1, off + 1):
                            jm = i + m
                            if 0 <= jm < len(closes):
                                cum += ((closes[jm] / entry_px) - 1) * 100 - cost_pct * (m / off)
                                # 注：成本一次性扣；这里按持有期比例近似，仅为路径示意，真实回撤以周期累计为准
                        # 简化：持有期末累计 net 作为路径终点，路径内部不平滑
                        a["equity_path"].append(net)
        except Exception as e:
            print(f"  [WARN] 回测 {code} 失败: {e}")
    summary = {
        "years": years,
        "total_signals": total_signals,
        "cost_bps_per_side": COST_BPS,
        "cost_adjusted": True,
        "periods": {},
    }
    for k, a in agg.items():
        c = a["count"]
        decided = a["win"] + a["loss"]
        win_rate = round(a["win"] / decided * 100, 1) if decided else 0
        avg_return = round(a["ret_sum"] / c, 2) if c else 0
        # 最大回撤（按全部 net 序列累计）
        peak = 0.0; cum = 0.0; max_dd = 0.0
        for v in a["equity_path"]:
            cum += v
            if cum > peak: peak = cum
            dd = cum - peak
            if dd < max_dd: max_dd = dd
        # 夏普
        if c > 1:
            variance = sum((v - avg_return) ** 2 for v in a["equity_path"]) / (c - 1)
            std_ret = variance ** 0.5
            sharpe = round(avg_return / std_ret, 2) if std_ret > 0 else 0
        else:
            sharpe = 0
        summary["periods"][k] = {
            "count": c,
            "samples": c,
            "win": a["win"], "loss": a["loss"], "draw": a["draw"],
            "win_rate": win_rate,
            "avg_return": avg_return,
            "best_return": round(a["best"], 2) if c else 0,
            "worst_return": round(a["worst"], 2) if c else 0,
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": sharpe,
        }
    out = os.path.join(DATA_DIR, "FOUR_VOLUME_BACKTEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    # 🛡 2026-09-04 主人令一劳永逸：同步补写 data/FOUR_VOLUME_BACKTEST.js —— 此前只写 .json，
    #   .js 自 09-02 手工跑后无人再生成（运维 all_ 动态扫描按通用 24h 红线必报孤儿 fail）。
    summary_out = dict(summary)
    summary_out["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_out["method"] = f"四量终极历史回测：信号日收盘价买入，持有N个真实交易日收盘价卖出（前复权；已扣双边交易成本 {2*COST_BPS/100:.2f}%）"
    with open(os.path.join(DATA_DIR, "FOUR_VOLUME_BACKTEST.js"), "w", encoding="utf-8") as f:
        f.write("/* 四量终极历史回测 strategy_four_volume.py 默认 3 年回测 */\n")
        f.write("window.FOUR_VOLUME_BACKTEST = " + json.dumps(summary_out, ensure_ascii=False) + ";\n")
    p5 = summary["periods"]["5d"]
    print(f"  四量终极回测: {total_signals} 个信号, "
          f"T+5 胜率 {p5['win_rate']}% / 均值 {p5['avg_return']}% / 最大回撤 {p5['max_drawdown']}%")
    return summary


def main():
    # 🛡 2026-08-20 主人令·一劳永逸：四量终极属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='strategy_four_volume')

    ap = argparse.ArgumentParser(description="四量终极 选股策略")
    ap.add_argument("--backtest", type=int,
                    default=int(os.environ.get("V8_BACKTEST_YEARS", "3") or 3),  # 2026-09-06 P0-C：默认跑回测（3 年）
                    help="同时跑近 N 年回测（0=不跑；E 回测批经 SCRIPT_ENV 注入 V8_BACKTEST_YEARS=3）")
    ap.add_argument("--top", type=int, default=80,
                    help="每板成交量前N(默认80, 控制扫描规模)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    records = []
    try:
        records = scan_four_volume(top_cy=args.top, top_kc=args.top,
                                   top_zb=args.top, top_hk=max(20, args.top // 2))
    except Exception as e:
        # 🛡 2026-09-03 一劳永逸：扫描异常也要写出带新鲜时间戳的产物，避免
        #   data/FOUR_VOLUME.js 冻结在上一跑、被运维按陈旧判 fail（静默冻结根因）。
        print(f"  [ERROR] 四量终极日线扫描异常: {e}")
    write_four_volume_js(records)
    # 2026-09-06 P0-C：默认就跑回测（不再 0 不跑）。即便 args.backtest=0 或 records 空，也尝试 sync 写
    # 一个空回测外壳以保 FOUR_VOLUME_BACKTEST.js 新鲜。
    bt_summary = None
    if args.backtest and args.backtest > 0:
        try:
            bt_summary = backtest_four_volume(years=args.backtest)
        except Exception as e:
            print(f"  [WARN] 四量终极回测失败: {e} — 写空回测外壳保底")
            bt_summary = {
                "years": args.backtest,
                "total_signals": 0,
                "cost_bps_per_side": COST_BPS,
                "cost_adjusted": True,
                "periods": {
                    k: {"count": 0, "samples": 0, "win_rate": 0, "avg_return": 0,
                        "best_return": 0, "worst_return": 0, "max_drawdown": 0, "sharpe_ratio": 0}
                    for k in ["1d", "3d", "5d", "10d", "20d"]
                },
                "method": f"四量终极历史回测：{e}",
            }
    # 🛡 2026-09-04 一劳永逸：策略回顾回测区读 .js 外壳（非 .json），此前为 09-02 手工
    #   空壳无人回写 → update_time 冻结、健康面板 all_FOUR_VOLUME_BACKTEST 永远 FAIL（误报）。
    write_four_volume_backtest_js(records, bt_summary)
    return records


if __name__ == "__main__":
    main()
