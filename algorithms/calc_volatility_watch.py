#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT DELETE: v8 原生波动率观测计算脚本
# 用途：拉取主要 A 股指数日 K 收盘，计算「已实现波动率」与「大盘波动率环境 / 企稳信号」，
#       直接输出 v8 raw_data/volatility.json（由 v8_build_deploy 构建为 data/VOLATILITY.js）。
# 数据源：baostock 日 K（主，避开 akshare 限流 / mootdx 崩溃）→ akshare index_zh_a_hist（备）
#        → 本地缓存 carry-forward（兜底）。
# 铁律：数据源全失败 / 数据不足 → available=false + 说明，绝不造假（空数据只给框架+暂无数据）。
#
# 波动率口径（量化标准）：
#   r_t = ln(C_t / C_{t-1})                      对数日收益
#   vol_20d(t) = std(r_{t-19..t}) * sqrt(252) * 100   20 日年化已实现波动率(%)
#   vol_5d(t)  = std(r_{t-4..t})  * sqrt(252) * 100    近 5 日年化波动率(%)
#   vol_trend% = (vol_20d(t) - vol_20d(t-5)) / vol_20d(t-5) * 100   负值=波动率下降
#   vol_pctile = 当前 vol_20d 在「近 120 个交易日的 vol_20d 序列」中的分位(0~100)
#   ret_5d/20d/60d = 区间累计收益(%)
#
# 复合「大盘波动率环境 / 企稳信号」逻辑（直接回答「指数涨+波动降=企稳回升？」）：
#   指数20日平均收益 ≥ 0 且 波动率5日趋势 < 0  → 企稳回升(stabilize, 绿)
#   指数20日平均收益 < 0 且 波动率5日趋势 < 0  → 阴跌磨底(grind, 琥珀)
#   指数20日平均收益 ≥ 0 且 波动率5日趋势 ≥ 0  → 反弹分歧(rebound_diverge, 蓝)
#   指数20日平均收益 < 0 且 波动率5日趋势 ≥ 0  → 恐慌下行(panic, 红)
import os
import sys
import json
import math
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V8_ROOT = os.path.dirname(BASE_DIR)
RAW_DIR = os.path.join(V8_ROOT, "raw_data")
CACHE_PATH = os.path.join(BASE_DIR, "volatility_cache.json")

# 主要指数（baostock 代码 = 市场前缀.代码）
INDICES = [
    ("000001", "sh", "上证指数"),
    ("000300", "sh", "沪深300"),
    ("399006", "sz", "创业板指"),
    ("000905", "sh", "中证500"),
    ("000852", "sh", "中证1000"),
]

TRADING_DAYS = 252
HIST_CALENDAR_DAYS = 400   # 拉取约 400 自然日（≈ 270 交易日）以支撑 120 日分位


def log(msg):
    print(f"[vol-watch] {msg}")


def _std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def fetch_baostock(code, prefix, start, end):
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}", "date,close",
            start_date=start, end_date=end, frequency="d", adjustflag="3",
        )
        rows = []
        while (rs.error_code == "0") & rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        out = []
        for r in rows:
            try:
                out.append((r[0], float(r[1])))
            except Exception:
                pass
        return out
    except Exception as e:
        log(f"baostock {code} 失败: {e}")
        return []


def fetch_akshare(code, start, end):
    try:
        import akshare as ak
        df = ak.index_zh_a_hist(symbol=code, period="daily",
                                 start_date=start, end_date=end)
        out = []
        for _, row in df.iterrows():
            try:
                d = str(row.get("日期", ""))
                c = float(row.get("收盘", 0))
                if d and c:
                    out.append((d, c))
            except Exception:
                pass
        return out
    except Exception as e:
        log(f"akshare {code} 失败: {e}")
        return []


def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"缓存写入失败: {e}")


def get_series(code, prefix, start, end, cache):
    """返回 [(date, close)]，优先实时拉取，失败回退缓存。"""
    series = fetch_baostock(code, prefix, start, end)
    if not series:
        series = fetch_akshare(code, start, end)
    src = "baostock" if series else "cache"
    if not series:
        series = cache.get(code, [])
        src = "cache"
    # 合并缓存（拉取成功时，用新数据覆盖同日期、补齐缺失）
    if src != "cache" and code in cache:
        cache_dates = {d for d, _ in series}
        for d, c in cache[code]:
            if d not in cache_dates:
                series.append((d, c))
    series.sort(key=lambda x: x[0])
    return series, src


def compute_index(series, source):
    dates = [d for d, _ in series]
    closes = [c for _, c in series]
    n = len(closes)
    if n < 21:
        return None
    # 对数日收益
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]
    # 每日 vol_20d 序列（从有足够数据起）
    daily_vol = []
    for i in range(19, len(rets)):
        window = rets[i - 19:i + 1]
        daily_vol.append(_std(window) * math.sqrt(TRADING_DAYS) * 100.0)
    if len(daily_vol) < 6:
        return None
    vol_20d = daily_vol[-1]
    vol_20d_ago5 = daily_vol[-6]
    vol_trend_pct = ((vol_20d - vol_20d_ago5) / vol_20d_ago5 * 100.0) if vol_20d_ago5 else 0.0
    # 近 5 日 vol
    recent5 = rets[-5:]
    vol_5d = _std(recent5) * math.sqrt(TRADING_DAYS) * 100.0 if len(recent5) >= 2 else vol_20d
    # 120 日分位
    ref = daily_vol[-121:-1] if len(daily_vol) >= 121 else daily_vol[:-1]
    if ref:
        below = sum(1 for v in ref if v < vol_20d)
        vol_pctile = (below + 0.5) / len(ref) * 100.0
    else:
        vol_pctile = 50.0
    # 各周期收益
    def ret_k(k):
        return (closes[-1] / closes[-1 - k] - 1.0) * 100.0 if n > k else 0.0
    ret_5d = ret_k(5)
    ret_20d = ret_k(20)
    ret_60d = ret_k(60)
    today_pct = rets[-1] * 100.0
    return {
        "code": None, "name": None,
        "close": round(closes[-1], 2),
        "today_pct": round(today_pct, 2),
        "vol_20d": round(vol_20d, 2),
        "vol_5d": round(vol_5d, 2),
        "vol_trend_pct": round(vol_trend_pct, 2),
        "vol_pctile": round(vol_pctile, 1),
        "ret_5d": round(ret_5d, 2),
        "ret_20d": round(ret_20d, 2),
        "ret_60d": round(ret_60d, 2),
        "source": source,
    }


def regime(idx_metrics):
    """根据各指数 20日收益 与 波动率(短端vs长端) 生成复合信号。"""
    valid = [m for m in idx_metrics if m]
    if not valid:
        return {
            "regime": "数据不足", "regime_code": "unknown",
            "regime_color": "#9e9e9e",
            "avg_vol_20d": 0.0, "avg_vol_5d": 0.0,
            "avg_vol_trend_pct": 0.0, "vol_short_vs_long_pct": 0.0,
            "idx_20d_avg_ret": 0.0,
            "idx_up_20d": False, "vol_falling": False,
            "signal_summary": "指数波动率数据不足，无法生成复合信号。",
            "hypothesis": "无法判断：波动率数据缺失。",
            "today_note": "",
        }
    avg_vol_20d = sum(m["vol_20d"] for m in valid) / len(valid)
    avg_vol_5d = sum(m["vol_5d"] for m in valid) / len(valid)
    svl = [ (m["vol_5d"] - m["vol_20d"]) / m["vol_20d"] * 100.0
            for m in valid if m["vol_20d"] ]
    vol_short_vs_long = sum(svl) / len(svl) if svl else 0.0
    avg_trend = sum(m["vol_trend_pct"] for m in valid) / len(valid)
    avg_ret = sum(m["ret_20d"] for m in valid) / len(valid)
    up_cnt = sum(1 for m in valid if m["ret_20d"] >= 0)
    fall_cnt = sum(1 for m in valid if m["vol_trend_pct"] < 0)
    svl_fall_cnt = sum(1 for m in valid
                     if (m["vol_5d"] - m["vol_20d"]) < 0)

    idx_up_20d = avg_ret >= 0
    vol_falling = vol_short_vs_long < 0

    if idx_up_20d and vol_falling:
        code, label, color = "stabilize", "企稳回升", "#2e7d32"
    elif (not idx_up_20d) and vol_falling:
        code, label, color = "grind", "阴跌磨底", "#f57f17"
    elif idx_up_20d and (not vol_falling):
        code, label, color = "rebound_diverge", "反弹分歧", "#1565c0"
    else:
        code, label, color = "panic", "恐慌下行", "#c62828"

    trend_word = (f"短端5日波动率({avg_vol_5d:.1f}%)"
                    f"{'低于' if vol_falling else '高于'}20日中枢({avg_vol_20d:.1f}%) "
                    f"{abs(vol_short_vs_long):.1f}%（较5日前则{'降' if avg_trend<0 else '升'}{abs(avg_trend):.1f}%）")
    ret_word = f"主要指数近 20 日平均收益 {avg_ret:+.1f}%（{up_cnt}/{len(valid)} 个指数转正）"
    if code == "stabilize":
        summary = (f"呈现「指数磨底回升 + 波动收敛」组合：{ret_word}，且{trend_word}，"
                   f"波动率已明确低于长端。历史上该组合常对应恐慌释放后的企稳阶段，"
                   f"但需后续放量确认，单日信号不构成趋势反转保证。")
    elif code == "grind":
        summary = (f"呈现「价未止跌 + 波动收敛」组合：{ret_word}，但{trend_word}。"
                   f"杀跌动能边际衰减，价格仍处下行通道，属阴跌磨底，尚不能判定企稳，"
                   f"需观察波动率何时伴随价格同步转正。")
    elif code == "rebound_diverge":
        summary = (f"呈现「价反弹 + 波动仍升」组合：{ret_word}，但{trend_word}。"
                   f"反弹中波动率不降反升，分歧/抛压仍在，多为技术性反抽或假摔风险，"
                   f"需警惕冲高回落。")
    else:
        summary = (f"呈现「价跌 + 波动升」组合：{ret_word}，且{trend_word}。"
                   f"恐慌情绪仍在释放、抛压未止，属典型下行加速段，应控制仓位、等待波动率见顶。")

    p_up_pos = "指数近20日已转正（涨）" if idx_up_20d else "指数近20日仍为负（未涨）"
    p_vol_pos = "波动率已下降（短端低于长端）" if vol_falling else "波动率仍未下降（短端高于长端）"
    if code == "stabilize":
        hypo = f"假设成立 ✅：{p_up_pos} 且 {p_vol_pos}，构成企稳回升。"
    else:
        missing = []
        if not idx_up_20d:
            missing.append("指数近20日未转正")
        if not vol_falling:
            missing.append("波动率未下降")
        hypo = (f"假设暂不成立 ❌：企稳回升需同时满足「指数近20日已转正（涨）」"
                f"且「波动率已下降（短端低于长端）」。当前 {'、'.join(missing)}，"
                f"故判定为「{label}」而非企稳回升。")

    todays = [f"{m['name']}{m['today_pct']:+.2f}%" for m in valid]
    today_note = (f"今日：" + "、".join(todays) + "；"
                  + (f"短端波动率低于长端({svl_fall_cnt}/{len(valid)}个)，符合「价"
                     + ("涨" if idx_up_20d else "跌") + "波落」"
                     if vol_falling else
                     f"短端波动率仍高于长端({len(valid)-svl_fall_cnt}/{len(valid)}个)，属「价"
                     + ("涨" if idx_up_20d else "跌") + "波升」")
                  + "特征。")

    return {
        "regime": label, "regime_code": code, "regime_color": color,
        "avg_vol_20d": round(avg_vol_20d, 2),
        "avg_vol_5d": round(avg_vol_5d, 2),
        "avg_vol_trend_pct": round(avg_trend, 2),
        "vol_short_vs_long_pct": round(vol_short_vs_long, 2),
        "idx_20d_avg_ret": round(avg_ret, 2),
        "up_idx_count": up_cnt, "total_idx": len(valid),
        "down_vol_idx_count": fall_cnt,
        "svl_fall_idx_count": svl_fall_cnt,
        "idx_up_20d": idx_up_20d, "vol_falling": vol_falling,
        "signal_summary": summary,
        "hypothesis": hypo,
        "today_note": today_note,
    }


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    today = datetime.date.today()
    end = today.strftime("%Y-%m-%d")
    start = (today - datetime.timedelta(days=HIST_CALENDAR_DAYS)).strftime("%Y-%m-%d")

    cache = load_cache()
    metrics = []
    any_real = False
    for code, prefix, name in INDICES:
        series, src = get_series(code, prefix, start, end, cache)
        # 写回缓存（仅当本次成功拉取到数据时更新，避免用空覆盖）
        if src != "cache" and series:
            cache[code] = series
            any_real = True
        m = compute_index(series, src)
        if m:
            m["code"] = code
            m["name"] = name
            metrics.append(m)
        else:
            log(f"{name}({code}) 数据不足({len(series)} 根)，跳过")

    # 仅当本次有真实拉取时才落盘缓存（carry-forward 不污染）
    if any_real:
        save_cache(cache)

    comp = regime(metrics)
    result = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "update_date": end,
        "available": len(metrics) > 0,
        "indices": metrics,
        "composite": comp,
        "note": ("数据源：baostock 指数日 K（主）/ akshare（备）/ 本地缓存兜底。"
                 "波动率 = 20 日对数收益标准差年化(×√252)。"
                 + ("" if metrics else " 本次各指数均未取到可用日 K，暂不生成波动率观测（不造假）。")),
    }
    out_path = os.path.join(RAW_DIR, "volatility.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"已写出 {out_path}")
    log(f"复合信号：{comp['regime']}（平均20日波动 {comp['avg_vol_20d']}%，"
         f"波动5日趋势 {comp['avg_vol_trend_pct']:+.1f}%，指数20日均收益 {comp['idx_20d_avg_ret']:+.1f}%）")
    for m in metrics:
        log(f"  {m['name']}: 收 {m['close']} 今 {m['today_pct']:+.2f}% | "
             f"20日波动 {m['vol_20d']}% (分位 {m['vol_pctile']}) 趋势 {m['vol_trend_pct']:+.1f}% | "
             f"20日收益 {m['ret_20d']:+.1f}%")
    return result


if __name__ == "__main__":
    main()
