#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回调企稳池生成器（2026-11-22 主人令：选股策略→回调池子tab 展示数据源）

🔴 定位：独立的候选源展示卡。产出 raw_data/pullback_pool.json（全市场老票回调企稳信号，口径不变），
   经 update_v8 注入 data/PULLBACK_POOL.js，在「选股策略 → 🔄 回调池」子tab 展示真值。
   **本脚本只展示、不改 final_recommend Top3 排序**（Top3 硬闸 _aligned_topfactor 约束仍在，
   回调票不进 Top3；其价值是提供独立于因子榜的观察源，用前瞻数据持续验证）。
   V8_PULLBACK_COMPETE 开关（final_recommend 影子对照）默认 0，与本展示链路彼此独立。

🛡 科学口径（2026-11-21 真实回测定参，铁律①数据真实②算法科学④真实标注）：
   - 源：raw_data/kline_cache/<code>.json 真实前复权日K（收盘/最高/最低/量），绝不编数据。
   - 老票闸：判定时刻 t 的 K 线根数 >= 250（≈上市满1年）——用「时点根数」而非「今天回看上市日期」，
     天然避免前视偏差（见 separate.py 分离验证：老票超额+1.02% CI[+0.54,+1.47]显著>0；
     次新-0.93%，纯次新效应+1.13pp）。
   - 信号（无前视，只用 t 及之前数据，收盘后判定）：
       ① 从近20日最高收盘回撤 6%~22%（不接深跌飞刀，不追浅回调）
       ② 过去60日高点相对60日前收盘涨幅 >=6%（确认「曾经强」，有资金记忆）
       ③ 当日最低价 > 前3日最低（止跌企稳）
       ④ 当日量 < 近5日均量*0.85（缩量抛压衰竭）
       ⑤ 收盘 >= MA5（站上短期均线）
   - 实时口径：判到最后一根 K 线（不预留未来）；回测口径（duel.py）预留20根算 T+20，两者信号定义一致。
   - ETF/指数过滤：只保留 6 位 A 股代码（沪深主板/创业板/科创板/北交所），排除 ETF/指数。
   - 质量分 = 信号强度连续量（回撤适中性×缩量程度×趋势站稳），仅用于排序，非胜率承诺。

📤 输出：raw_data/pullback_pool.json
   {"update_time":..., "caliber":..., "signal_date":..., "count":N,
    "stocks":[{code,name,quality,dd20,vol_ratio,ma5_gap,sig_date}, ...按 quality 降序]}
   名称来自 raw_data/stock_names.json（真值），缺失则留空（不编造）。
"""

import json
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KDIR = os.path.join(ROOT, "raw_data", "kline_cache")
OUTPUT = os.path.join(ROOT, "raw_data", "pullback_pool.json")
NAMES_FILE = os.path.join(ROOT, "raw_data", "stock_names.json")

# 信号参数（duel.py / separate.py 验证口径，勿随意改）
DD_LO, DD_HI = 0.06, 0.22      # 回撤区间
PREV_UP = 0.06                 # 过去60日涨幅门槛
VOL_SHRINK = 0.85              # 缩量系数
LOW_LOOK = 3                   # 近几日不创新低
MIN_BARS = 250                 # 老票闸（时点K线根数）
MAX_QUALITY_STOCKS = 10        # 展示上限：主人令 2026-11-22「每天按评分显示前10只就够了」
                               # ⚠️ 只限流展示，绝不放宽信号口径。实测(pp_topk_check.py)：严格信号内取前10
                               #    与全量等价（同日配对 -0.07%，CI跨0，14/31胜出），不损害收益；
                               #    而放宽企稳凑10只会亏（pp_score_duel.py：配对 -1.44%/日）。故信号闸一个不动。
MAX_STALE_DAYS = 5             # 新鲜度闸：K线末日距今>5自然日视为停更，宁缺毋滥不输出（铁律①数据及时）

# 前瞻跟踪台账（主人令 2026-11-22「跟踪回测，看有没有更好」）
# 每天把当日命中票的信号日+次日开盘买价落盘；后续用真实K线回填 T+5/T+20 收益，
# 与因子榜同口径对比。台账独立于展示池，不参与任何排序。
TRACK_FILE = os.path.join(ROOT, "raw_data", "pullback_track.json")
TRACK_HORIZONS = (5, 20)       # 跟踪持有周期（交易日）


def _num(x):
    try:
        v = float(x)
        return v if v == v else 0.0
    except Exception:
        return 0.0


def _load_names():
    """名称真值（stock_names.json 可能是 dict of dict 或 list）"""
    out = {}
    try:
        j = json.load(open(NAMES_FILE, encoding="utf-8"))
    except Exception:
        return out
    seq = []
    if isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list):
                seq.extend(v)
            elif isinstance(v, dict) and "code" in v:
                seq.append(v)
    elif isinstance(j, list):
        seq = j
    for x in seq:
        if not isinstance(x, dict):
            continue
        c = str(x.get("code", "")).zfill(6)
        n = x.get("name")
        if c.isdigit() and n:
            out[c] = str(n)
    return out


def _is_a_share(code):
    """仅 A 股 6 位代码，排除 ETF(51/15/56/58...)、指数(000xxx 指数除外靠 kline 目录自然过滤)"""
    if not (code.isdigit() and len(code) == 6):
        return False
    return code[0] in "0368" or code.startswith("43") or code.startswith("83") or code.startswith("87")


def _load_kline(code):
    try:
        rows = json.load(open(os.path.join(KDIR, code + ".json"), encoding="utf-8"))
    except Exception:
        return None
    if not rows or len(rows) < MIN_BARS:
        return None
    d = [str(x.get("date", "")) for x in rows]
    c = [_num(x.get("close")) for x in rows]
    l = [_num(x.get("low")) for x in rows]
    v = [_num(x.get("volume")) for x in rows]
    o = [_num(x.get("open")) for x in rows]
    if any(not x for x in c):
        return None
    return {"d": d, "o": o, "c": c, "l": l, "v": v}


def _signal_at(K, t):
    """返回 (bool, quality, dd, vol_ratio, ma5_gap)；只用 t 及之前数据"""
    c, l, v = K["c"], K["l"], K["v"]
    if t < 60:
        return False, 0, 0, 0, 0
    hi20 = max(c[t - 19:t + 1])
    if hi20 <= 0:
        return False, 0, 0, 0, 0
    dd = c[t] / hi20 - 1.0                       # 负数=回撤
    if not (DD_LO <= -dd <= DD_HI):
        return False, 0, 0, 0, 0
    seg = c[t - 59:t + 1]
    if max(seg) / seg[0] - 1.0 < PREV_UP:
        return False, 0, 0, 0, 0
    if not (l[t] > min(l[t - LOW_LOOK:t])):
        return False, 0, 0, 0, 0
    v5 = sum(v[t - 4:t + 1]) / 5
    vol_ratio = (v[t] / v5) if v5 > 0 else 1.0
    if vol_ratio > VOL_SHRINK:
        return False, 0, 0, 0, 0
    ma5 = sum(c[t - 4:t + 1]) / 5
    if ma5 <= 0 or c[t] < ma5:
        return False, 0, 0, 0, 0
    ma5_gap = c[t] / ma5 - 1.0
    # 质量分（仅排序用）：回撤越靠近中段(14%)越好 + 缩量越明显越好 + 站上MA5越稳越好
    dd_score = 1.0 - min(1.0, abs(-dd - 0.14) / 0.14)
    vol_score = 1.0 - min(1.0, vol_ratio / VOL_SHRINK)
    ma5_score = min(1.0, ma5_gap / 0.03)
    quality = round(0.4 * dd_score + 0.35 * vol_score + 0.25 * ma5_score, 4)
    return True, quality, round(dd * 100, 2), round(vol_ratio, 3), round(ma5_gap * 100, 2)


def _load_benchmark():
    """中证1000 日线：date -> (open, close)，用于算前瞻超额收益"""
    p = os.path.join(ROOT, "raw_data", "index_history_multi.json")
    try:
        j = json.load(open(p, encoding="utf-8"))
        ks = j["data"]["000852.SH"]["klines"]
        return {str(r["d"]): (_num(r.get("o")), _num(r.get("c"))) for r in ks}
    except Exception:
        return {}


def _update_track(today_results, sig_date):
    """前瞻跟踪台账：
    1) 把当日命中票(最多前10)按 sig_date 追加落盘，记录信号日次日开盘买价(若K线已到位)；
    2) 对台账中已成熟(信号日之后已有 T+20 根K线)的票，回填真实 T+5/T+20 收益与超额；
    3) 未成熟的保留 buy_price 占位，等后续自然补齐。绝不回写/篡改历史信号日与质量分。
    """
    # 读旧台账
    track = {"version": 1, "caliber": "严格企稳信号·次日开盘买·T+5/T+20收盘卖·扣0.3%·基准中证1000",
             "last_update": "", "days": {}}
    try:
        old = json.load(open(TRACK_FILE, encoding="utf-8"))
        if isinstance(old, dict) and isinstance(old.get("days"), dict):
            track = old
    except Exception:
        pass

    days = track["days"]
    bm = _load_benchmark()

    # ① 追加当日信号（按 code 去重，同日同票只留一条）
    #    ⚠️ 0 信号日（如周末/大跌日）不新增，但仍继续走 ② 回填历史，不能早退。
    if sig_date:
        bucket = days.setdefault(sig_date, {})
        for x in today_results:
            code = x["code"]
            K = _load_kline(code)
            buy_price = None
            buy_date = ""
            if K and sig_date in K["d"]:
                t = K["d"].index(sig_date)
                if t + 1 < len(K["d"]):
                    buy_price = K["o"][t + 1]
                    buy_date = K["d"][t + 1]
            if code not in bucket:
                bucket[code] = {
                    "name": x.get("name", ""),
                    "quality": x["quality"],
                    "dd20": x["dd20"],
                    "vol_ratio": x["vol_ratio"],
                    "ma5_gap": x["ma5_gap"],
                    "buy_date": buy_date,
                    "buy_price": round(buy_price, 4) if buy_price else None,
                    "r5": None, "r20": None, "excess20": None,
                }

    # ② 回填所有未成熟信号（遍历全台账，幂等）
    for sd, codes in days.items():
        for code, rec in codes.items():
            if rec.get("r20") is not None:
                continue  # 已回填，跳过
            K = _load_kline(code)
            if not K or sd not in K["d"]:
                continue
            t = K["d"].index(sd)
            bi = t + 1
            if bi >= len(K["d"]):
                continue
            buy = K["o"][bi]
            if not buy:
                continue
            if not rec.get("buy_price"):
                rec["buy_price"] = round(buy, 4)
                rec["buy_date"] = K["d"][bi]
            # T+5
            if t + 5 < len(K["d"]) and rec.get("r5") is None:
                sell5 = K["c"][t + 5]
                if sell5:
                    rec["r5"] = round((sell5 / buy - 1 - 0.003) * 100, 2)
            # T+20
            if t + 20 < len(K["d"]):
                sell20 = K["c"][t + 20]
                if sell20:
                    rec["r20"] = round((sell20 / buy - 1 - 0.003) * 100, 2)
                    bd, sd20 = K["d"][bi], K["d"][t + 20]
                    if bd in bm and sd20 in bm:
                        bo, bc = bm[bd]
                        _, ec = bm[sd20]
                        if bo and bc:
                            rec["excess20"] = round(rec["r20"] - (ec / bo - 1) * 100, 2)

    track["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(TRACK_FILE), exist_ok=True)
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(track, f, ensure_ascii=False, indent=2)
    matured = sum(1 for ds in days.values() for r in ds.values() if r.get("r20") is not None)
    total = sum(len(ds) for ds in days.values())
    print(f"[pullback-track] 台账累计 {total} 条信号 / {len(days)} 个信号日，已成熟回填 {matured} 条 → {TRACK_FILE}")


def main():
    names = _load_names()
    results = []
    scanned = 0
    stale_skipped = 0
    today = datetime.now().date()
    import glob
    for p in glob.glob(os.path.join(KDIR, "*.json")):
        code = os.path.basename(p).replace(".json", "")
        if not _is_a_share(code):
            continue
        K = _load_kline(code)
        if not K:
            continue
        scanned += 1
        t = len(K["d"]) - 1                       # 实时口径：判到最后一根（不预留未来）
        # 新鲜度闸：末根K线距今>MAX_STALE_DAYS → 停更票，跳过（铁律①数据及时/宁缺毋滥）
        try:
            last_dt = datetime.strptime(K["d"][t], "%Y-%m-%d").date()
            if (today - last_dt).days > MAX_STALE_DAYS:
                stale_skipped += 1
                continue
        except Exception:
            stale_skipped += 1
            continue
        ok, q, dd, vr, mg = _signal_at(K, t)
        if not ok:
            continue
        results.append({
            "code": code,
            "name": names.get(code, ""),
            "quality": q,
            "dd20": dd,
            "vol_ratio": vr,
            "ma5_gap": mg,
            "sig_date": K["d"][t],
        })
    results.sort(key=lambda x: -x["quality"])
    all_hits = list(results)                       # 全量命中 → 供前瞻跟踪台账（样本充分）
    results = results[:MAX_QUALITY_STOCKS]         # 展示限流前10（不放宽信号）
    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "caliber": ("无前视·老票(判定时刻K线>=250)·回撤6-22%/过去60日涨>=6%/近3日不创新低/"
                    "缩量<0.85xMA5量/站上MA5·严格信号一个不放宽·按质量分取前10仅限流展示·"
                    "不参与Top3排序·前瞻跟踪逐日回填T+5/T+20真实收益"),
        "signal_date": results[0]["sig_date"] if results else "",
        "scanned": scanned,
        "stale_skipped": stale_skipped,
        "count": len(results),
        "stocks": results,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[pullback-pool] 扫描老票 {scanned} 只 → 新鲜度闸剔除停更 {stale_skipped} 只 → 命中 {len(results)} 只（质量分Top{MAX_QUALITY_STOCKS}）")
    print(f"[pullback-pool] 信号日={out['signal_date']}  输出={OUTPUT}")
    for x in results[:10]:
        print(f"  {x['code']} {x['name']:<8} 质量={x['quality']:.3f} 回撤={x['dd20']:+.1f}% 量比={x['vol_ratio']:.2f}")
    # 前瞻跟踪：全量命中落台账（当日0只则只回填历史，不新增）
    try:
        _update_track(all_hits, out["signal_date"])
    except Exception as e:
        print(f"[pullback-track] 台账更新异常（不影响展示池）：{e}")


if __name__ == "__main__":
    main()
