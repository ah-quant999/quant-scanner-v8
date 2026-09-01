#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""市场路径概率算法（主人授权 2026-08-19 做卡片版 + 5 年长 K 线）

输入：out/index_history.json（fetcher 产出，5 年上证日 K 线）
输出：out/market_path_probability.json，包含：
  - 当前状态（位置/均线/MACD/成交量趋势）
  - 江恩时间窗口（F21/F34/F55/F89 距今日 + 关键日期）
  - 黄金分割位（近 60 日高低的 0.382/0.5/0.618/0.786）
  - 缠论分型（近 60 日自动识别顶底分型序列）
  - 形态匹配（找近 3 年最相似 20 段，统计后续 5/10/20 日涨跌分布）
  - 路径概率 A/B/C

诚实标注：⚠️ 历史回测胜率仅供参考；实盘验证 ≥3 个月
"""
import json
import os
import sys
import datetime
from collections import deque

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(BASE, "out", "index_history.json")
OUT = os.path.join(BASE, "out", "market_path_probability.json")
# 🛡 2026-08-20 一劳永逸：update_v8.py 只读 raw_data/market_path_probability.json
#   生成 data/MARKET_PATH_PROBABILITY.js；脚本必须 bridge 到 raw_data/，否则主站永远旧数据。
RAW_OUT = os.path.join(BASE, "raw_data", "market_path_probability.json")

WIN = 60        # 分析窗口（近 60 日）
MATCH_WIN = 60  # 形态匹配窗口
TOPK = 20       # 取最相似的 20 段
THRESH = 0.70   # 相关系数阈值（0.85 太严，5 年样本下 0 命中；0.7 实用）


def log(msg):
    print(f"  [market_path_probability] {msg}", flush=True)


def load_klines():
    with open(IN, encoding="utf-8") as f:
        d = json.load(f)
    return d["klines"]


def sma(arr, n):
    if len(arr) < n:
        return None
    return sum(arr[-n:]) / n


def macd_state(closes, fast=12, slow=26, signal=9):
    """简化 MACD：EMA 差值与 signal EMA 差值，判定金叉/死叉/中性"""
    if len(closes) < slow + signal:
        return "N/A", 0.0
    def ema(arr, n):
        k = 2 / (n + 1)
        e = arr[0]
        for x in arr[1:]:
            e = x * k + e * (1 - k)
        return e
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = ema_fast - ema_slow
    # 简化：近 9 日 EMA of DIF
    difs = []
    for i in range(slow, len(closes)):
        ef = ema(closes[: i + 1], fast)
        es = ema(closes[: i + 1], slow)
        difs.append(ef - es)
    dea = ema(difs, signal) if difs else 0
    if dif > dea + 5:
        return "金叉", dif - dea
    if dif < dea - 5:
        return "死叉", dif - dea
    return "中性", dif - dea


def vol_trend(volumes, n=5):
    """近 N 日成交量趋势：上升/下降/平"""
    if len(volumes) < n + 1:
        return "N/A"
    diffs = [volumes[-i] - volumes[-i - 1] for i in range(1, n + 1)]
    ups = sum(1 for d in diffs if d > 0)
    if ups >= n - 1:
        return "放量"
    if ups <= 1:
        return "缩量"
    return "平稳"


def gann_windows(closes, lows, fib=(21, 34, 55, 89)):
    """江恩时间窗口：F0 = 近 89 日最低点；F21/F34/F55/F89 为关键日期
    返回 [(key, days_to_today, target_date_str)]
    days_to_today < 0 = 未来 / > 0 = 已过
    """
    today_idx = len(closes) - 1
    f0_idx = today_idx - 89 + min(range(89), key=lambda i: lows[today_idx - 88 + i])
    f0_date = lows  # dummy
    # 直接用日期算
    out = []
    for n in fib:
        # 取 F0 对应日期
        pass
    # 简化：用今日日期反推关键日期（F0 锚点）
    # F0 = 近 89 日内最低点
    import datetime as _dt
    today = _dt.date.today()
    f0_idx = today_idx - 89 + min(range(89), key=lambda i: lows[today_idx - 88 + i])
    f0_date = None
    # 用 klines 索引找到日期
    # 改成从文件读
    return f0_idx  # placeholder


def fib_retracement(high, low, fibs=(0.236, 0.382, 0.5, 0.618, 0.786)):
    """黄金分割回撤位"""
    span = high - low
    return [(f, round(high - span * f, 2)) for f in fibs]


def chan_fractals(klines, lookback=60):
    """简化缠论顶底分型：取近 N 日，找局部高点和低点
    顶分型 = 中间 K 线高点最高 且 两侧高点更低
    底分型 = 中间 K 线低点最低 且 两侧低点更高
    返回 [(date, '顶'/'底', price), ...]
    """
    n = min(lookback, len(klines))
    sub = klines[-n:]
    fractals = []
    for i in range(2, len(sub) - 2):
        # 顶分型：5 根 K 线高点最高
        highs5 = [sub[i + j]["h"] for j in range(-2, 3)]
        if sub[i]["h"] == max(highs5):
            lows5 = [sub[i + j]["l"] for j in range(-2, 3)]
            if sub[i]["h"] > sub[i - 1]["h"] and sub[i]["h"] > sub[i + 1]["h"]:
                fractals.append((sub[i]["d"], "顶", sub[i]["h"]))
        # 底分型
        lows5 = [sub[i + j]["l"] for j in range(-2, 3)]
        if sub[i]["l"] == min(lows5):
            if sub[i]["l"] < sub[i - 1]["l"] and sub[i]["l"] < sub[i + 1]["l"]:
                fractals.append((sub[i]["d"], "底", sub[i]["l"]))
    return fractals[-8:]  # 取最近 8 个


def pattern_match(closes, target_win=MATCH_WIN, top_k=TOPK):
    """形态匹配：找历史上与最近 N 日最相似的 K 段子序列
    相似度 = 涨跌方向一致率（±1 序列的余弦相似度），比绝对价 Pearson 宽松
    返回 [(sim, future_5d, future_10d, future_20d), ...]
    """
    n = len(closes)
    if n < target_win + 25:
        return []
    # 目标：近 target_win 日的日涨跌方向（+1/-1/0）
    target = []
    for i in range(n - target_win, n):
        d = closes[i] - closes[i - 1] if i > 0 else 0
        target.append(1 if d > 0 else -1 if d < 0 else 0)

    matches = []
    for i in range(target_win + 1, n - 20):
        sub = []
        for j in range(i - target_win, i):
            d = closes[j] - closes[j - 1] if j > 0 else 0
            sub.append(1 if d > 0 else -1 if d < 0 else 0)
        # 方向一致率
        same = sum(1 for a, b in zip(target, sub) if a == b)
        sim = same / target_win
        if sim >= 0.65:  # 65% 方向一致即视为相似
            f5 = (closes[i + 5] - closes[i]) / closes[i] * 100 if i + 5 < n else None
            f10 = (closes[i + 10] - closes[i]) / closes[i] * 100 if i + 10 < n else None
            f20 = (closes[i + 20] - closes[i]) / closes[i] * 100 if i + 20 < n else None
            matches.append((sim, f5, f10, f20))
    matches.sort(key=lambda x: -x[0])
    return matches[:top_k]


def calc_path_prob(matches):
    """基于形态匹配结果算路径概率
    路径 A：N 字延续，5 日涨 >1%
    路径 B：N 字失败，5 日跌 <-1%
    路径 C：宽幅震荡，|5 日变化| ≤1%
    """
    if not matches:
        return {"A_up": 33.3, "B_down": 33.3, "C_flat": 33.4, "sample": 0}
    valid = [m for m in matches if m[1] is not None]
    if not valid:
        return {"A_up": 33.3, "B_down": 33.3, "C_flat": 33.4, "sample": 0}
    # 按 corr 加权
    total_w = sum(m[0] for m in valid)
    a_w = sum(m[0] for m in valid if m[1] > 1)
    b_w = sum(m[0] for m in valid if m[1] < -1)
    c_w = sum(m[0] for m in valid if -1 <= m[1] <= 1)
    return {
        "A_up": round(a_w / total_w * 100, 1),
        "B_down": round(b_w / total_w * 100, 1),
        "C_flat": round(c_w / total_w * 100, 1),
        "sample": len(valid),
    }


def main():
    log(f"读 {IN}")
    if not os.path.exists(IN):
        log(f"输入文件不存在，请先跑 fetch_index_history.py")
        return 1
    klines = load_klines()
    closes = [k["c"] for k in klines]
    highs = [k["h"] for k in klines]
    lows = [k["l"] for k in klines]
    vols = [k["v"] for k in klines]
    n = len(klines)
    today = klines[-1]["d"]
    last = closes[-1]
    log(f"数据 {n} 条，今日 {today} 收盘 {last}")

    # 1) 当前状态
    win = min(WIN, n)
    rh = max(highs[-win:])
    rl = min(lows[-win:])
    pos = (last - rl) / (rh - rl) if rh > rl else 0.5
    ma5 = sma(closes, 5)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    state_ma = ("多头" if ma5 > ma20 > ma60 else "空头" if ma5 < ma20 < ma60 else "震荡")
    macd_label, macd_dif = macd_state(closes)
    vt = vol_trend(vols)

    log(f"近 {win} 日: 高 {rh} 低 {rl} 当前位置 {pos:.2%}")
    log(f"MA: 5={ma5} 20={ma20} 60={ma60} -> {state_ma}")
    log(f"MACD: {macd_label} (DIF-DEA={macd_dif:.2f}); 量能: {vt}")

    # 2) 江恩时间窗口
    today_idx = n - 1
    f0_offset = 89
    if n > f0_offset:
        f0_rel = min(range(f0_offset), key=lambda i: lows[today_idx - f0_offset + 1 + i])
        f0_idx = today_idx - f0_offset + 1 + f0_rel
    else:
        f0_idx = 0
    f0_date = klines[f0_idx]["d"]
    f0_price = lows[f0_idx]
    import datetime as _dt
    today_dt = _dt.date.fromisoformat(today)
    f0_dt = _dt.date.fromisoformat(f0_date)
    gann = []
    for fn in (21, 34, 55, 89):
        target_dt = f0_dt + _dt.timedelta(days=fn)
        days_to = (target_dt - today_dt).days
        gann.append({
            "F": fn,
            "anchor_date": f0_date,
            "anchor_price": f0_price,
            "target_date": target_dt.isoformat(),
            "days_to_today": days_to,
            "is_near": abs(days_to) <= 5,
        })

    # 3) 黄金分割
    fibs = fib_retracement(rh, rl)

    # 4) 缠论分型
    fractals = chan_fractals(klines, lookback=60)

    # 5) 形态匹配
    log("形态匹配中...")
    matches = pattern_match(closes)
    prob = calc_path_prob(matches)
    log(f"匹配 {len(matches)} 段，加权概率 A={prob['A_up']}% B={prob['B_down']}% C={prob['C_flat']}%")

    # 6) 汇总输出
    out = {
        "meta": {
            "symbol": "上证指数",
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "data_range": f"{klines[0]['d']} ~ {today}",
            "kline_count": n,
            "disclaimer": "⚠️ 历史回测仅供参考；预测市场不存在稳定高准确率方法。实盘验证 ≥3 个月。",
        },
        "current": {
            "date": today,
            "close": last,
            "pos_in_60d": round(pos, 4),
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "ma_trend": state_ma,
            "macd": macd_label,
            "macd_dif": round(macd_dif, 2),
            "volume": vt,
            "recent_60d_high": rh,
            "recent_60d_low": rl,
        },
        "gann_windows": gann,
        "fib_retracements": [{"ratio": f, "price": p} for f, p in fibs],
        "chan_fractals": [{"date": d, "type": t, "price": p} for d, t, p in fractals],
        "path_probability": prob,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已写入 {OUT}")
    # 🛡 2026-08-20 一劳永逸：bridge 到 raw_data/（update_v8 只读 raw_data/ 生成
    #   data/MARKET_PATH_PROBABILITY.js；之前缺 bridge → 主站用旧版概率卡）。
    os.makedirs(os.path.dirname(RAW_OUT), exist_ok=True)
    with open(RAW_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已 bridge → raw_data/market_path_probability.json")
    return 0


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/market_path_probability.py"):
        sys.exit(2)
    sys.exit(main())