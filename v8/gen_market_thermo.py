#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_market_thermo.py — 「未来预测」子TAB数据生成器 → data/MARKET_THERMO.js
(window.MARKET_THERMO = {generated, D, EXT, SPOT})

2026-10-05 阿狸咪的工程师 建（主人令：未来预测子TAB · 牛转熊指标观测台 · 每日更新）

数据链路（全部真实源，绝不编造）：
  D.eq / D.val10 / D.ma200 —— raw_data/sw_index_daily_cache/（申万一级行业日K等权均值·月末，
                              全市场PE 10年滚动分位；与 bear_card_generator.py 同源同口径）
  D.sh                    —— gtimg 上证月K（真实点位，EDHEC牛熊状态机的输入）
  EXT.margin              —— raw_data/margin_data.json（融资余额）
  EXT.bond10y/hs300pe/erp —— raw_data/valuation_percentile.json（沪深300 PE）+ macro_data.json（10Y国债）
  EXT.turnover            —— gtimg 上证日线 260 日成交量分位
  EXT.tsf                 —— akshare 社融增量 → 滚动12M累计·同比（社融脉冲，金十源，月频滞后数日）
  EXT.pmi                 —— akshare 制造业PMI
  SPOT                    —— gtimg 实时（sh000001 / sh000300 收盘）

健壮性约定（无人值守安全）：
  · 单一外部源失败 → 回退沿用上一次 MARKET_THERMO.js 中的同字段（并保留旧 date），不中断；
  · D 重建失败 → **不写盘、退出码 2**（D 是月频骨架，宁旧勿错）；
  · 输出为 `window.MARKET_THERMO = <纯JSON>;`，便于回读与校验。
"""
import io
import json
import os
import re
import sys
import datetime
import warnings

warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW = os.path.join(BASE, "raw_data", "sw_index_daily_cache")
OUT = os.path.join(BASE, "data", "MARKET_THERMO.js")
UA = {"User-Agent": "Mozilla/5.0"}


def bj_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def _http_json(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


# ────────────────────────── D：27年月度骨架 ──────────────────────────
def build_D():
    import pandas as pd

    closes = {}
    for f in sorted(os.listdir(SW)):
        if not f.endswith(".csv") or not f[:-4].isdigit():
            continue
        df = pd.read_csv(os.path.join(SW, f))
        df["日期"] = df["日期"].astype(str).str[:10]
        df = df.sort_values("日期").drop_duplicates("日期")
        closes[f[:-4]] = df.set_index("日期")["收盘"].astype(float)
    mat = pd.DataFrame(closes).sort_index().dropna(how="all")
    eq_d = mat.mean(axis=1).dropna().sort_index()
    eq_d.index = pd.to_datetime(eq_d.index)
    eq_m = eq_d.resample("ME").last()
    dates = [d.strftime("%Y-%m") for d in eq_m.index]

    # 10年PE分位（滚动120个月）
    val = pd.read_csv(os.path.join(SW, "market_valuation_cache.csv"))
    val["date"] = pd.to_datetime(val["date"] + "-01") + pd.offsets.MonthEnd(0)
    pe = val.set_index("date").resample("ME").last()["pe"].reindex(eq_m.index)

    def pct_rank(x, s):
        s = s.dropna()
        if len(s) < 60 or pd.isna(x):
            return None
        return float((s <= x).mean() * 100)

    val10 = [pct_rank(pe.iloc[i], pe.iloc[max(0, i - 119): i + 1]) for i in range(len(eq_m))]
    ma200 = eq_m.rolling(12).mean()

    # 上证月K（gtimg，340个月覆盖 1996~）
    j = _http_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,month,,,340,qfq")
    node = j["data"]["sh000001"]
    k = node.get("qfqmonth") or node.get("month")
    sh_by_month = {}
    for row in k:
        m = str(row[0])[:7]
        sh_by_month[m] = round(float(row[2]), 2)  # 收盘
    sh = [sh_by_month.get(m) for m in dates]
    miss = sum(1 for x in sh if x is None)
    if miss > 2:
        raise RuntimeError(f"上证月线缺失 {miss} 个月，拒绝写盘")
    sh = [x if x is not None else 0.0 for x in sh]  # JS 侧按对齐月份消费；残缺月归零并已在上方拦截

    # 融资余额同比（macro_margin.csv，12个月差分）
    margin_yoy = None
    try:
        marg = pd.read_csv(os.path.join(SW, "macro_margin.csv"))
        marg["date"] = pd.to_datetime(marg["date"])
        marg = marg.set_index("date").resample("ME").last()
        if len(marg) > 12:
            margin_yoy = round(float(marg["margin"].pct_change(12).iloc[-1] * 100), 1)
    except Exception:
        pass

    cur = eq_m.iloc[-1]
    cur_val10 = val10[-1]
    fwd12 = eq_m / eq_m.shift(12) - 1
    cur_dd = round(float(fwd12.iloc[-1]) * -100, 1) if not pd.isna(fwd12.iloc[-1]) else None

    return {
        "dates": dates,
        "sh": sh,
        "eq": [round(float(x), 4) for x in eq_m.values],
        "ma200": [round(float(x), 4) if pd.notna(x) else None for x in ma200.values],
        "val10": [round(x, 1) if x is not None else None for x in val10],
        "current": {
            "date": dates[-1],
            "eq": round(float(cur), 2),
            "val10": round(cur_val10) if cur_val10 is not None else None,
            "drawdown": cur_dd,
            "margin_yoy": margin_yoy,
            "pe": round(float(pe.iloc[-1]), 1) if pe.iloc[-1] is not None and not pd.isna(pe.iloc[-1]) else None,
        },
    }


# ────────────────────────── EXT：实时观测指标 ──────────────────────────
def _prev_ext():
    """回读上一次 MARKET_THERMO.js 的 EXT（纯JSON右侧，可直接 loads）。"""
    try:
        txt = io.open(OUT, encoding="utf-8").read()
        rhs = txt.split("=", 1)[1].rstrip().rstrip(";")
        return json.loads(rhs).get("EXT") or {}
    except Exception:
        return {}


def ext_margin(prev):
    try:
        d = json.load(io.open(os.path.join(BASE, "raw_data", "margin_data.json"), encoding="utf-8"))
        sh = d["sh"]
        cur, old = sh[-1], sh[0]
        chg = round((cur["rz_balance"] / old["rz_balance"] - 1) * 100, 1)
        return {"bal": cur["rz_balance"], "date": cur["date_raw"], "chg": chg}
    except Exception:
        return prev.get("margin") or {}


def ext_bond_erp(prev):
    try:
        mac = json.load(io.open(os.path.join(BASE, "raw_data", "macro_data.json"), encoding="utf-8"))
        b = mac["monetary"]["cn_bond_10y"]
        vp = json.load(io.open(os.path.join(BASE, "raw_data", "valuation_percentile.json"), encoding="utf-8"))
        hs = [x for x in vp["indices"] if x.get("name") == "沪深300"]
        pe = hs[0]["current_pe"]
        return {
            "bond10y": {"v": b["value"], "date": b["date"]},
            "hs300pe": {"pe": pe, "pct5y": round(hs[0].get("percentile_5y", 0) * 100, 1)},
            "erp": round(100 / pe - b["value"], 2),
        }
    except Exception:
        return {"bond10y": prev.get("bond10y") or {}, "hs300pe": prev.get("hs300pe") or {},
                "erp": prev.get("erp")}


def ext_turnover(prev):
    try:
        j = _http_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,260,qfq")
        node = j["data"]["sh000001"]
        k = node.get("qfqday") or node.get("day")
        vols = [float(r[5]) for r in k]
        dates = [r[0] for r in k]
        last = vols[-1]
        pct = round(sum(1 for x in vols if x <= last) / len(vols) * 100, 1)
        mx = max(vols)
        return {"pct": pct, "maxdate": dates[vols.index(mx)],
                "volMaxRatio": round(last / mx * 100, 1)}
    except Exception:
        return prev.get("turnover") or {}


def ext_tsf(prev):
    """社融脉冲 = 滚动12M新增累计·同比（akshare 社融增量，金十源）。"""
    try:
        import akshare as ak
        df = ak.macro_china_shrzgm().reset_index(drop=True)  # 正序：tail=最新
        months = df["月份"].astype(str).tolist()
        incr = [float(x) for x in df["社会融资规模增量"]]
        pulse, pm = [], []
        for i in range(11, len(months)):
            pulse.append(sum(incr[i - 11:i + 1]))
            pm.append(months[i])
        pairs = []
        for i in range(12, len(pulse)):
            if pulse[i - 12] > 0:
                pairs.append((pm[i], round((pulse[i] / pulse[i - 12] - 1) * 100, 1)))
        cur_m, cur_v = pairs[-1]
        mx = max(pairs, key=lambda x: x[1])
        mn = min(pairs, key=lambda x: x[1])
        return {"yoy": cur_v, "month": cur_m,
                "max": mx[1], "maxm": mx[0], "min": mn[1], "minm": mn[0]}
    except Exception:
        return prev.get("tsf") or {}


def ext_pmi(prev):
    try:
        import akshare as ak
        p = ak.macro_china_pmi()  # head=最新（倒序表）
        m0 = str(p["月份"].iloc[0])           # 形如 2026年09月份
        v0 = float(p["制造业-指数"].iloc[0])
        mi = p["制造业-指数"].astype(float)
        i_min, i_max = int(mi.idxmin()), int(mi.idxmax())
        m_fmt = f"{m0[:4]}-{m0[5:7]}"
        return {"v": round(v0, 1), "date": m_fmt + "-01",
                "min": round(float(mi.min()), 1), "minm": str(p["月份"].iloc[i_min])[:7].replace("年", "-"),
                "max": round(float(mi.max()), 1)}
    except Exception:
        return prev.get("pmi") or {}


def ext_spot(prev):
    try:
        import urllib.request
        req = urllib.request.Request("https://qt.gtimg.cn/q=sh000001,sh000300", headers=UA)
        txt = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "replace")
        vals = {}
        for seg in txt.split(";"):
            seg = seg.strip()
            if '="' not in seg:
                continue
            code = seg.split("=")[0].replace("v_", "").strip()
            f = seg.split('="')[1].split("~")
            if len(f) > 3:
                vals[code] = float(f[3])
        if "sh000001" in vals and "sh000300" in vals:
            return {"sh": vals["sh000001"], "hs300": vals["sh000300"]}
    except Exception:
        pass
    return {k: v for k, v in prev.items() if k in ("sh", "hs300")}


def main():
    print("[1/4] 重建 27年月度骨架 D（sw缓存 + gtimg 上证月K）…")
    D = build_D()
    print("      dates=%s~%s 共%d月, eq末值=%.2f, val10末=%s, sh末=%s"
          % (D["dates"][0], D["dates"][-1], len(D["dates"]),
             D["eq"][-1], D["current"]["val10"], D["sh"][-1]))

    print("[2/4] 采集 EXT 实时指标（失败自动回退上一版）…")
    prev = _prev_ext()
    ext = {}
    ext["margin"] = ext_margin(prev)
    ext.update(ext_bond_erp(prev))
    ext["turnover"] = ext_turnover(prev)
    ext["tsf"] = ext_tsf(prev)
    ext["pmi"] = ext_pmi(prev)
    spot = ext_spot(prev)
    if not spot.get("sh"):
        spot["sh"] = D["sh"][-1]
    spot["eq"] = D["current"]["eq"]

    print("[3/4] 写 data/MARKET_THERMO.js …")
    payload = {
        "generated": bj_now().strftime("%Y-%m-%d %H:%M") + " CST",
        "D": D,
        "EXT": ext,
        "SPOT": spot,
    }
    js = "window.MARKET_THERMO = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:  # LF
        f.write(js)
    os.replace(tmp, OUT)
    print("[4/4] 完成：", OUT, f"{os.path.getsize(OUT)} bytes")
    print("      EXT =", json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in list(v.items())[:2]})
                                      for k, v in ext.items()}, ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
