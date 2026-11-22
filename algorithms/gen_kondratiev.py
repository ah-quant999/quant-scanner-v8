# -*- coding: utf-8 -*-
"""
康波周期观测数据生成器  (2026-11-22 主人令：中国经济 × A股 双周期对照卡)

数据铁律（主人最高优先级）：
  1) 数据真实：全部来自 akshare 公开真实序列（上证全历史 / GDP季度 / CPI / PPI），
     计算日标注，绝不伪造、绝不占位。
  2) 算法科学 + 真实标注 —— 关键诚实边界：
     康波长波 50~60 年；本机 A股仅 36 年、GDP 仅 20.8 年，
     均不足一个完整康波 ⇒ **不得声称"数据拟合出康波长波"**。
     本生成器把两类信息严格分离：
       [实测] 中短周期（FFT 朱格拉/基钦）+ 历史大底序列 + 当前相对位置 —— 本机数据计算；
       [理论锚定] 康波第几波/阶段 —— 学界框架（康德拉季耶夫/周金涛划分），仅作定位参考，非数据拟合。
  3) 不参与选股排序：本卡为观测研判，仅放"暂未上架"，不进 Top3 / 终选任何环节。

无前视：只用截至计算日的公开数据；FFT/分位/波谷均为历史已实现值。
运行： python algorithms/gen_kondratiev.py   →  raw_data/kondratiev.json + data/KONDRATIEV.js
"""
import json
import os
import sys
from datetime import datetime

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

# ── 理论框架锚定（学界划分，非本机数据拟合；仅作长波阶段定位参考）──
# 康德拉季耶夫长波主流五波划分 + 周金涛等中国学者对第五波阶段的判断。
THEORY = {
    "wave": 5,
    "name": "第五次康波 · 信息技术/数字革命",
    "span": "约1980s–2030s",
    "stage": "衰退 → 萧条过渡（筑底区）",
    "scholar": "康德拉季耶夫长波五波划分 + 周金涛等学界阶段判断",
    "note": "长波阶段为学界理论框架锚定，非本机数据拟合；本机数据长度不足以统计验证50–60年长波，仅定位中短周期与当前相对位置。",
}


def _pct(arr, val):
    return round(float((np.asarray(arr) <= val).sum()) / len(arr) * 100, 1)


def calc_a_share():
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol="sh000001")[["date", "close"]].dropna()
    df["date"] = df["date"].astype(str)
    px = df["close"].values.astype(float)
    last = float(px[-1])

    df["ym"] = df["date"].str[:7]
    monthly = df.groupby("ym")["close"].last()
    m = monthly.values.astype(float)
    n = len(m)

    # 月度同比去均值 → FFT 找主导周期（月→年）
    yoy = np.full(n, np.nan)
    for i in range(12, n):
        yoy[i] = m[i] / m[i - 12] - 1
    s = yoy[12:] - np.nanmean(yoy[12:])
    N = len(s)
    fft = np.abs(np.fft.rfft(s * np.hanning(N)))
    freq = np.fft.rfftfreq(N, d=1.0)
    # 周期下限 6 个月（滤噪声），上限 N/2（=18年，超过则样本不足1.5个周期不可靠）
    valid = [(float(fft[k]), 1.0 / freq[k]) for k in range(1, len(freq))
             if freq[k] > 0 and 6 <= 1.0 / freq[k] <= N / 2.0]
    valid.sort(reverse=True)
    cycles = []
    for p, per_m in valid:
        per_y = per_m / 12.0  # FFT 频率主轴单位=月 → 转成年
        if all(abs(per_y - c["years"]) > 1.5 for c in cycles):  # 去重间隔1.5年，保留基钦+朱格拉多个尺度
            cycles.append({"years": round(float(per_y), 1), "power": round(float(p), 1)})
        if len(cycles) >= 3:
            break

    # 年度收盘局部大底（±3年）
    annual = df.groupby(df["date"].str[:4])["close"].last()
    ay, av = list(annual.index), annual.values.astype(float)
    troughs = []
    for i in range(3, len(av) - 3):
        if av[i] == av[i - 3:i + 4].min() and (not troughs or i - troughs[-1][0] >= 3):
            troughs.append((i, ay[i], round(float(av[i]), 1)))

    ma120 = float(np.mean(m[-120:]))
    gap = (last / ma120 - 1) * 100
    # 距最近大底的年数（用年度序列最后一底）
    yrs_since_trough = int(ay[-1]) - int(troughs[-1][1]) if troughs else None

    return {
        "span": f"{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}",
        "years": round(n / 12, 1),
        "close": round(last, 1),
        "asof": df["date"].iloc[-1],
        "price_pctile": _pct(px, last),
        "ma120": round(ma120, 1),
        "ma120_gap_pct": round(gap, 1),
        "fft_cycles": cycles,
        "troughs": [{"year": y, "close": c} for _, y, c in troughs],
        "trough_gaps": [int(troughs[i][0] - troughs[i - 1][0]) for i in range(1, len(troughs))],
        "yrs_since_trough": yrs_since_trough,
        "phase": "朱格拉升段中后段" if gap > 0 else "朱格拉回落段",
    }


def calc_cn_economy():
    import akshare as ak
    gdp = ak.macro_china_gdp()[["季度", "国内生产总值-同比增长"]].iloc[::-1].reset_index(drop=True)
    gv = []
    for _, r in gdp.iterrows():
        v = r["国内生产总值-同比增长"]
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            gv.append((str(r["季度"]), float(v)))
    gvals = np.array([v for _, v in gv])

    cpi = ak.macro_china_cpi()[["月份", "全国-同比增长"]].iloc[::-1].reset_index(drop=True)
    cp = []
    for _, r in cpi.iterrows():
        v = r["全国-同比增长"]
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            cp.append((str(r["月份"]), float(v)))
    cv = np.array([v for _, v in cp])

    ppi = ak.macro_china_ppi()[["月份", "当月同比增长"]].iloc[::-1].reset_index(drop=True)
    pv = []
    for _, r in ppi.iterrows():
        v = r["当月同比增长"]
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            pv.append((str(r["月份"]), float(v)))
    pvals = np.array([v for _, v in pv])

    return {
        "gdp": {
            "span": f"{gv[0][0]} ~ {gv[-1][0]}", "years": round(len(gv) / 4, 1),
            "current": round(float(gvals[-1]), 1), "pctile": _pct(gvals, gvals[-1]),
            "max": round(float(gvals.max()), 1), "min": round(float(gvals.min()), 1),
            "mean": round(float(gvals.mean()), 1),
        },
        "cpi": {
            "span": f"{cp[0][0]} ~ {cp[-1][0]}", "current": round(float(cv[-1]), 1),
            "pctile": _pct(cv, cv[-1]),
        },
        "ppi": {
            "span": f"{pv[0][0]} ~ {pv[-1][0]}", "current": round(float(pvals[-1]), 1),
            "pctile": _pct(pvals, pvals[-1]),
        },
        "phase": "增速换挡下行 · PPI/CPI剪刀差",
    }


def main():
    print("[kondratiev] 拉取真实数据并计算…")
    a = calc_a_share()
    cn = calc_cn_economy()
    out = {
        "version": 1,
        "calc_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "akshare: stock_zh_index_daily(sh000001) / macro_china_gdp / macro_china_cpi / macro_china_ppi",
        "boundary": THEORY["note"],
        "theory": THEORY,
        "a_share": a,
        "cn_economy": cn,
    }
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    jp = os.path.join(RAW, "kondratiev.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # 前端注入格式与 update_v8._write_js 一致： window.X = {json};
    js = os.path.join(DATA, "KONDRATIEV.js")
    with open(js, "w", encoding="utf-8") as f:
        f.write("window.KONDRATIEV = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"[kondratiev] 输出 {jp} / {js}")
    print(f"[kondratiev] A股 {a['close']} {a['price_pctile']}%分位 | FFT {[c['years'] for c in a['fft_cycles']]} | GDP {cn['gdp']['current']}%")
    return out


if __name__ == "__main__":
    main()
