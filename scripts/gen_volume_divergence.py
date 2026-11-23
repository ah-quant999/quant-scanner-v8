# -*- coding: utf-8 -*-
"""量价背离预警观测（缩量新高灯）— 2026-11-23 主人令
【背景】主人自选票（赛分/纳微/药康/成都先导）9月集体见顶，共性=顶前缩量新高（量价背离）。
【回测实证】2026-11-23 本机回测：科创板30只随机池 255 次信号，信号后 T+20 均 -2.05% /
  胜率 40% vs 全期基线 +0.98% / 45%，超额 -3.0 个百分点 ⇒ 「缩量新高」为有效见顶预警灯。
【定位】⚠️ 预警/过滤层，不参与选股评分（评审中，主人定夺后再议接入）；预警≠卖出。
【扫描域】候选池精选（raw_data/candidate_quotes.json，~75只）+ 主人4只案例票。
【信号】收盘创20日新高 且 5日均量 < 0.85×20日均量（与回测口径逐字一致）。
产出：data/VOLUME_DIVERGENCE.js（window.VOLUME_DIVERGENCE）
"""
import json
import os
import sys
import datetime

import pandas as pd

try:
    import akshare as ak
except ImportError:
    print("FATAL: akshare 未安装", file=sys.stderr)
    sys.exit(2)

BJ = datetime.timezone(datetime.timedelta(hours=8))


def _bj_now():
    return datetime.datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")


OUT = "data/VOLUME_DIVERGENCE.js"
CASES = [("688758", "赛分科技"), ("688690", "纳微科技"),
         ("688046", "药康生物"), ("688222", "成都先导")]

# 2026-11-23 回测实证（科创板30只随机池，种子42；本机探针 E:/v8data/qs8-tmp/probe_pool_test.py）
BACKTEST = dict(pool_n=30, sig_n=255, t20=-2.05, wr20=40, base_t20=0.98, base_wr=45,
                excess=-3.0, note="信号=收盘创20日新高且5均量<0.85×20均量；T+20前瞻；样本内统计≠未来承诺")

# 案例票实证（顶部/回撤/顶前20日缩量天数/量峰领先天数），2026-11-23 实测
CASE_EVIDENCE = [
    ("688758", "赛分科技", "2026-09-22", -43.3, 18, 31, 6),
    ("688690", "纳微科技", "2026-09-23", -34.2, 17, 39, 1),
    ("688046", "药康生物", "2026-08-13", -34.1, 3, 7, 14),
    ("688222", "成都先导", "2026-09-23", -43.8, 17, 18, 0),
]


def _sina_symbol(code):
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    return None  # 北交所/港股/美股跳过（信号域=A股沪深）


def load_daily(code):
    sym = _sina_symbol(code)
    if not sym:
        return None
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust="qfq")
    except Exception:
        return None
    if df is None or len(df) < 60:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def analyze(df):
    """返回 dict 或 None。信号与 2026-11-23 回测口径逐字一致。"""
    c = df["close"]
    v = df["volume"].astype(float)
    v5 = v.rolling(5).mean()
    v20 = v.rolling(20).mean()
    hi20 = c.rolling(20).max()
    ma20 = c.rolling(20).mean()
    sig = (c >= hi20) & (v5 < 0.85 * v20)
    i = len(df) - 1
    last_date = str(df["date"].iloc[i].date())
    # 最近一次信号（找近20日内）
    recent = None
    for k in range(i, max(i - 20, 60), -1):
        if bool(sig.iloc[k]):
            recent = dict(date=str(df["date"].iloc[k].date()),
                          days_ago=int(i - k),
                          vol_ratio=round(float(v5.iloc[k] / v20.iloc[k]), 3))
            break
    return dict(
        date=last_date,
        close=float(c.iloc[i]),
        above_ma20=bool(c.iloc[i] > ma20.iloc[i]),
        hit_now=bool(sig.iloc[i]),
        recent=recent,
        cur_vol_ratio=round(float(v5.iloc[i] / v20.iloc[i]), 3) if v20.iloc[i] > 0 else None,
        off_high20=round(float(c.iloc[i] / hi20.iloc[i] - 1) * 100, 2),
    )


def main():
    universe = []
    seen = set()
    # ① 主人案例票（始终在场，便于对照）
    for code, name in CASES:
        universe.append((code, name, True))
        seen.add(code)
    # ② 候选池精选快照
    try:
        cq = json.load(open("raw_data/candidate_quotes.json", encoding="utf-8"))
        for it in cq.get("items", []):
            code = str(it.get("code", "")).strip()
            if not code or code in seen or not code.isdigit() or len(code) != 6:
                continue
            universe.append((code, str(it.get("name", "")), False))
            seen.add(code)
    except Exception as e:
        print(f"⚠️ candidate_quotes 读取失败（仅案例票模式）: {e}", file=sys.stderr)
    print(f"扫描域 {len(universe)} 只", flush=True)

    hits, watched, cases_now = [], [], []
    n_ok = 0
    for code, name, is_case in universe:
        df = load_daily(code)
        if df is None:
            continue
        n_ok += 1
        try:
            a = analyze(df)
        except Exception:
            continue
        if a is None:
            continue
        row = dict(code=code, name=name, case=is_case, price=a["close"],
                   above_ma20=a["above_ma20"], vol_ratio=a["cur_vol_ratio"],
                   off_high20=a["off_high20"],
                   hit_now=a["hit_now"],
                   recent=a["recent"])
        if is_case:
            cases_now.append(row)
        if a["hit_now"] or (a["recent"] and a["recent"]["days_ago"] <= 5):
            hits.append(row)
        else:
            watched.append(row)
    # 排序：今日命中 > 近5日命中；同级按缩量程度（vol_ratio 越小背离越重）
    hits.sort(key=lambda r: (0 if r["hit_now"] else 1,
                             r["recent"]["days_ago"] if r.get("recent") else 99,
                             r["vol_ratio"] if r["vol_ratio"] is not None else 9))

    out = dict(
        update_time=_bj_now(),
        data_date=hits[0]["recent"]["date"] if hits else None,
        universe=dict(total=len(universe), scanned=n_ok),
        signal="收盘创20日新高 且 5日均量<0.85×20日均量（量价背离·缩量新高）",
        hits=hits,
        cases_now=cases_now,
        backtest=BACKTEST,
        case_evidence=[dict(code=c, name=n, peak_date=p, drawdown=d,
                            shrink_days=s, vol_peak_lead=v, ma20_break=b)
                       for c, n, p, d, s, v, b in CASE_EVIDENCE],
        boundary="预警观测层：预警≠卖出，不参与选股评分（评审中）。样本内统计≠未来承诺；分型确认与量能口径基于日K收盘定稿；不构成投资建议",
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// 量价背离预警观测（缩量新高灯）— 自动生成，勿手改\n")
        f.write("window.VOLUME_DIVERGENCE = ")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"✅ {OUT}: 扫描{n_ok}/{len(universe)}，命中 {len(hits)} 只（今日 {sum(1 for h in hits if h['hit_now'])}）", flush=True)


if __name__ == "__main__":
    main()
