# -*- coding: utf-8 -*-
"""
中信 PE 双卡生成器
======================================================================
读 raw_data/citic_pe_history.json → 产出 data/CITIC_PE_THERMO.js + data/CITIC_PE_BACKTEST.js
两张卡挂在「暂未上架 · 实验区」最下方：
  1) 未来卡 = 实时温度计（当前 PE + 历史百分位 + 大底对比 + 信号灯）
  2) 回测卡 = "PE<10 买入后持有 60/120/250 日"历史胜率 + 阈值敏感性
2026-09-07 主人令：1 个未来 + 1 个回测，两个都做。
"""
import json, os, datetime as dt, math, statistics

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(REPO, "raw_data", "citic_pe_history.json")
OUT_T = os.path.join(REPO, "data", "CITIC_PE_THERMO.js")
OUT_B = os.path.join(REPO, "data", "CITIC_PE_BACKTEST.js")

# 大底参考日（沪深300/上证综指大底日 8 个，验证方法 = 后续 12 个月最大收益 > 15%）
BIG_BOTOMS = [
    {"d": "2010-07-05", "tag": "2010 中期调整底"},
    {"d": "2012-12-04", "tag": "2012 创业板前夜底"},
    {"d": "2014-07-22", "tag": "2014 牛前底"},
    {"d": "2016-01-28", "tag": "2016 熔断底"},
    {"d": "2018-10-19", "tag": "2018 政策底"},
    {"d": "2019-01-04", "tag": "2019 国庆后底"},
    {"d": "2020-03-23", "tag": "2020 疫情底"},
    {"d": "2022-10-31", "tag": "2022 国庆后底"},
    {"d": "2024-09-24", "tag": "2024 政策反转"},
]


def load_data():
    with open(SRC, "r", encoding="utf-8") as f:
        return json.load(f)


def percentile_rank(series, value):
    """当前 value 在 series 中的百分位（0=最低，100=最高）"""
    s = sorted([x for x in series if x is not None])
    if not s:
        return None
    n = len(s)
    left = sum(1 for x in s if x < value)
    eq = sum(1 for x in s if x == value)
    return round(100.0 * (left + 0.5 * eq) / n, 1)


def gen_thermo(d):
    """未来卡：温度计"""
    rows = d["data"]
    pe_series = [r["pe"] for r in rows if r.get("pe") is not None]
    pb_series = [r["pb"] for r in rows if r.get("pb") is not None]
    last = rows[-1]
    current_pe = last["pe"]
    current_pb = last["pb"]
    current_price = last["c"]

    pct_rank = percentile_rank(pe_series, current_pe)
    pct_rank_pb = percentile_rank(pb_series, current_pb)

    pe_p25 = statistics.quantiles(pe_series, n=4)[0] if len(pe_series) > 4 else None
    pe_p50 = statistics.median(pe_series)
    pe_p75 = statistics.quantiles(pe_series, n=4)[2] if len(pe_series) > 4 else None
    pb_p25 = statistics.quantiles(pb_series, n=4)[0] if len(pb_series) > 4 else None
    pb_p50 = statistics.median(pb_series)
    pb_p75 = statistics.quantiles(pb_series, n=4)[2] if len(pb_series) > 4 else None

    # 信号灯：deep_value(<10) / value(<12) / normal(12-20) / expensive(>20)
    if current_pe < 10:
        zone, zone_label, zone_color = "deep_value", "深度低估", "#26a69a"
    elif current_pe < 12:
        zone, zone_label, zone_color = "value", "低估边缘", "#fbbf24"
    elif current_pe < 20:
        zone, zone_label, zone_color = "normal", "正常区间", "#94a3b8"
    else:
        zone, zone_label, zone_color = "expensive", "偏贵", "#ef5350"

    # 大底对比
    big_bottom_compare = []
    by_date = {r["d"]: r for r in rows}
    for bb in BIG_BOTOMS:
        rec = by_date.get(bb["d"])
        if rec and rec.get("pe") is not None:
            # 找该日后 60/120/250 交易日的价格
            idx = next((i for i, r in enumerate(rows) if r["d"] == bb["d"]), None)
            if idx is not None:
                ret_60 = None
                ret_120 = None
                ret_250 = None
                base_p = rec["c"]
                for j, off, key in [(60,60,"60d"),(120,120,"120d"),(250,250,"250d")]:
                    if idx+j < len(rows):
                        nxt = rows[idx+j]["c"]
                        if base_p: ret_60 = round((nxt/base_p-1)*100, 1) if off==60 else ret_60
                        if base_p: ret_120 = round((nxt/base_p-1)*100, 1) if off==120 else ret_120
                        if base_p: ret_250 = round((nxt/base_p-1)*100, 1) if off==250 else ret_250
                big_bottom_compare.append({
                    "date": bb["d"],
                    "tag": bb["tag"],
                    "pe": round(rec["pe"], 2),
                    "pb": round(rec["pb"], 2) if rec.get("pb") else None,
                    "price": round(rec["c"], 2),
                    "ret_60d": ret_60,
                    "ret_120d": ret_120,
                    "ret_250d": ret_250,
                })

    # 历史 PE 跌破 <10 的累计时长占比
    days_below_10 = sum(1 for x in pe_series if x < 10)
    days_below_12 = sum(1 for x in pe_series if x < 12)
    days_below_15 = sum(1 for x in pe_series if x < 15)
    days_total = len(pe_series)

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_date": last["d"],
        "data_range": [d["start_date"], d["end_date"]],
        "row_count": d["row_count"],
        # 实时数据
        "current": {
            "price": round(current_price, 2),
            "pe_ttm": round(current_pe, 2),
            "pb_mrq": round(current_pb, 2) if current_pb else None,
        },
        # 历史分位
        "percentile": {
            "pe_rank": pct_rank,
            "pb_rank": pct_rank_pb,
            "pe_p25": round(pe_p25, 1) if pe_p25 else None,
            "pe_p50": round(pe_p50, 1),
            "pe_p75": round(pe_p75, 1) if pe_p75 else None,
            "pb_p25": round(pb_p25, 2) if pb_p25 else None,
            "pb_p50": round(pb_p50, 2),
            "pb_p75": round(pb_p75, 2) if pb_p75 else None,
        },
        # 信号灯
        "signal": {
            "zone": zone,
            "label": zone_label,
            "color": zone_color,
            "pe_threshold": {"deep": 10, "value": 12, "expensive": 20},
        },
        # 历史"低估"时间占比
        "valuation_history": {
            "days_total": days_total,
            "days_below_pe10": days_below_10,
            "days_below_pe12": days_below_12,
            "days_below_pe15": days_below_15,
            "pct_below_pe10": round(100*days_below_10/days_total, 1),
            "pct_below_pe12": round(100*days_below_12/days_total, 1),
            "pct_below_pe15": round(100*days_below_15/days_total, 1),
        },
        # 大底对比
        "big_bottom_compare": big_bottom_compare,
        # 风险提示
        "note": "PE/PB 截面为 TTM，仅作参考。回测卡独立给出历史胜率。",
    }
    return out


def gen_backtest(d):
    """回测卡：PE<10 买入后持有 60/120/250 日 胜率 + 阈值敏感性"""
    rows = d["data"]
    pe_series = [(r["d"], r["pe"], r["c"]) for r in rows if r.get("pe") is not None and r.get("c") is not None]

    def run_threshold(threshold, hold_days):
        """对每一日，PE<threshold 视为买入信号，持有 hold_days 日"""
        n = 0
        wins = 0  # 持有期末收益 > 0
        ret_list = []
        max_dd = 0  # 持有期内最大回撤
        for i, (d0, pe0, c0) in enumerate(pe_series):
            if pe0 < threshold and i + hold_days < len(pe_series):
                c_end = pe_series[i+hold_days][2]
                ret = (c_end / c0 - 1) * 100
                ret_list.append(ret)
                n += 1
                if ret > 0: wins += 1
                # 持有期内最大回撤
                mdd = 0
                peak = c0
                for j in range(i, min(i+hold_days+1, len(pe_series))):
                    p = pe_series[j][2]
                    peak = max(peak, p)
                    dd = (p/peak - 1) * 100
                    mdd = min(mdd, dd)
                max_dd = min(max_dd, mdd)
        if n == 0:
            return None
        return {
            "n": n,
            "win_rate": round(100*wins/n, 1),
            "avg_ret": round(statistics.mean(ret_list), 2),
            "median_ret": round(statistics.median(ret_list), 2),
            "max_ret": round(max(ret_list), 2),
            "min_ret": round(min(ret_list), 2),
            "max_dd": round(max_dd, 2),
        }

    # 三个持有期 × 四个阈值
    thresholds = [10, 12, 15, 20]
    hold_days_list = [60, 120, 250]
    result = {}
    for th in thresholds:
        result[f"pe<{th}"] = {}
        for hd in hold_days_list:
            r = run_threshold(th, hd)
            result[f"pe<{th}"][f"hold_{hd}d"] = r

    # 找出"PE<10 + 持有 250 日"的具体信号列表（详细展示前 6 条）
    signal_list = []
    for i, (d0, pe0, c0) in enumerate(pe_series):
        if pe0 < 10 and i + 250 < len(pe_series):
            c_end = pe_series[i+250][2]
            ret = round((c_end / c0 - 1) * 100, 1)
            # 持有期内最大回撤
            mdd = 0
            peak = c0
            for j in range(i, min(i+251, len(pe_series))):
                p = pe_series[j][2]
                peak = max(peak, p)
                dd = (p/peak - 1) * 100
                mdd = min(mdd, dd)
            signal_list.append({
                "date": d0,
                "pe": round(pe0, 2),
                "price": round(c0, 2),
                "ret_250d_pct": ret,
                "max_dd_pct": round(mdd, 1),
                "end_price": round(c_end, 2),
            })

    # 启示
    pe10_250 = result["pe<10"]["hold_250d"]
    insights = []
    if pe10_250:
        if pe10_250["n"] < 5:
            insights.append(f"样本仅 {pe10_250['n']} 个，统计意义极弱，不宜作交易信号")
        if pe10_250["win_rate"] >= 60 and pe10_250["avg_ret"] > 0:
            insights.append(f"胜率 {pe10_250['win_rate']}%，平均收益 {pe10_250['avg_ret']}%，统计上有正向期望")
        elif pe10_250["win_rate"] >= 50:
            insights.append(f"胜率 {pe10_250['win_rate']}%（接近 50/50），需结合其他信号过滤")
        else:
            insights.append(f"胜率 {pe10_250['win_rate']}%，历史未显示统计优势 → 谨防单信号陷阱")
        if pe10_250["max_dd"] < -20:
            insights.append(f"⚠️ 持有期内最大回撤 {pe10_250['max_dd']}%，心理压力大")

    # 大底日 vs 跌破 PE<10 同步性
    pe10_dates = {s["date"] for s in signal_list}
    overlap = [bb["d"] for bb in BIG_BOTOMS if bb["d"] in pe10_dates]
    insights.append(f"近 16 年共 {pe10_250['n'] if pe10_250 else 0} 次 PE<10 信号，其中 {len(overlap)} 个落在已知大底日（{', '.join(overlap) if overlap else '无'}）")

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "method": "中信证券 PE TTM < 阈值 当日收盘价买入 → 持有 60/120/250 交易日 → 当日收盘价卖出",
        "data_range": [d["start_date"], d["end_date"]],
        "data_source": "baostock sh.600030 PE TTM 日线",
        "signals_pe10_total": pe10_250["n"] if pe10_250 else 0,
        "result": result,
        "signal_list_pe10_hold250": signal_list,
        "insights": insights,
        "note": "未计交易成本/分红再投。回测对象：中信证券个股，未做对冲。统计置信度受样本数限制。",
    }
    return out


def write_js(path, var_name, payload):
    js = f"window.{var_name} = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"[citic-pe-gen] ✅ {path} ({os.path.getsize(path)//1024} KB, {len(payload.get('big_bottom_compare', payload.get('signal_list_pe10_hold250', [])))} items)")


def main():
    print("[citic-pe-gen] REPO:", REPO)
    d = load_data()
    print(f"[citic-pe-gen] 载入 {d['row_count']} 行 ({d['start_date']} ~ {d['end_date']})")
    t = gen_thermo(d)
    b = gen_backtest(d)
    write_js(OUT_T, "CITIC_PE_THERMO", t)
    write_js(OUT_B, "CITIC_PE_BACKTEST", b)
    print(f"[citic-pe-gen] 当前 PE TTM = {t['current']['pe_ttm']} ({t['signal']['label']})")
    print(f"[citic-pe-gen] PE<10 信号 × 250d 持有 = {b['signals_pe10_total']} 次")


if __name__ == "__main__":
    main()
