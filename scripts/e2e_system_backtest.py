# -*- coding: utf-8 -*-
"""
端到端系统回放 · 组合层（2026-10-25 主人令「现在马上做掉」）

用真实 dated top10_daily 归档 = 系统每日真实发出的推荐名单，重演「组合层」：
  每个信号日 d 取该日 Top-N（系统实发排序）→ 次日开盘等权买入 → 持有 H 交易日 → 卖出；
  滚动组合 = 任意交易日 t，持仓 = 近 H 内所有信号日 Top-N 的并，等权，满仓滚动。
  与"因子层电池/榜单层头对头"互补 —— 这是**整套系统跑出来的组合级净收益**真数字。

三套口径（同窗口、同持仓模型，只有名单来源不同）：
  OLD    = 归档真实 total_score 排序（旧代码，含 27 项因子，< 20261024）
  CLEAN  = 旧档同日把 DELIST_DIMS 九维度分数清零重排（= 清账后口径，回答"清账组合层是否变好"）
  NEW    = 2026-10-25 纯净档（仅 1 个信号日，曲线不足，仅报单笔）

参数扫描：N ∈ {5,10,20} × H ∈ {1,5,10}。
成本：双边 0.30%（进出各 0.15%，按每日持仓变动分摊）。
口径：close→close 近似（进入日收益 = close_d1/close_d - 1，等同开盘近似买入）。
净值曲线用全市场等权基准（000001 日历）对齐。

产出：raw_data/e2e_system_backtest.json
"""
import os
import json
import glob
import re
import math

REPO = os.environ.get("V8_ROOT") or r"E:/_wt_src_redesign"
RAW = os.path.join(REPO, "raw_data")
HIST = os.path.join(RAW, "history")
CACHE = os.path.join(RAW, "kline_cache_multi")
OUT = os.path.join(RAW, "e2e_system_backtest.json")

FORM_WEIGHT = 0.7
COST = 0.003
NS = (5, 10, 20)
HS = (1, 5, 10)
NEW_CODE_FROM = "20261024"
_kline = {}


def load_kline(code6):
    if code6 in _kline:
        return _kline[code6]
    p = os.path.join(CACHE, f"{code6}.json")
    bars = None
    if os.path.exists(p):
        try:
            bars = json.load(open(p, encoding="utf-8"))
        except Exception:
            bars = None
    _kline[code6] = bars
    return bars


def rsi14_at(bars, j):
    if j < 14:
        return None
    g, l = [], []
    for k in range(j - 13, j + 1):
        p0, p1 = float(bars[k - 1]["close"]), float(bars[k]["close"])
        d = p1 - p0 if p0 > 0 else 0.0
        g.append(max(d, 0.0)); l.append(max(-d, 0.0))
    ag = sum(g) / 14.0; al = sum(l) / 14.0
    if al <= 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def _num(x, default=0.0):
    return float(x) if isinstance(x, (int, float)) else default


def build_signals():
    """返回 {sysver: {date_str: [code6,...topN ordered]}} + 参考日历。"""
    files = sorted(glob.glob(os.path.join(HIST, "top10_daily_*.json")))
    files = [f for f in files if re.search(r"_(\d{8})\.json$", f)]
    sig = {"OLD": {}, "CLEAN": {}, "NEW": {}}
    ref_bars = json.load(open(os.path.join(CACHE, "000001.json"), encoding="utf-8"))
    ref_cal = {b["date"]: i for i, b in enumerate(ref_bars)}
    for f in files:
        m = re.search(r"_(\d{8})\.json$", f)
        dstr = m.group(1)
        d = json.load(open(f, encoding="utf-8"))
        entries = d.get("top10") or []
        rows = []
        for e in entries:
            code6 = re.sub(r"\D", "", str(e.get("code", "")))
            if len(code6) != 6:
                continue
            legacy = (_num(e.get("score_base")) + _num(e.get("score_enhance")) + _num(e.get("score_fund"))
                      + _num(e.get("score_sector")) + _num(e.get("score_inst")) + _num(e.get("score_quality"))
                      + _num(e.get("score_backtest")) + _num(e.get("score_form")) * FORM_WEIGHT
                      + (_num(e.get("score_winrate")) if e.get("score_winrate") is not None else 0.0))
            consec = int(_num(e.get("consecutive_days")))
            pct20 = _num(e.get("pct_chg_20d"))
            rsi_b = 0.0
            bars = load_kline(code6)
            if bars:
                si = None
                for i in range(len(bars) - 1, -1, -1):
                    if str(bars[i].get("date", "")).replace("-", "") <= dstr:
                        si = i; break
                if si is not None:
                    r = rsi14_at(bars, si)
                    if r is not None and r < 30:
                        rsi_b = 3.0
            mild_b = 2.0 if 0 < pct20 < 10 else 0.0
            del_exact = (_num(e.get("score_fund")) + _num(e.get("score_sector")) + _num(e.get("score_quality"))
                         + _num(e.get("score_form")) * FORM_WEIGHT + _num(e.get("score_research"))
                         + _num(e.get("score_breakout")) + _num(e.get("score_inst")))
            clean = legacy - del_exact - min(max(consec, 0) * 2, 8) - rsi_b - mild_b
            rows.append((code6, _num(e.get("total_score"), -999), clean))
            top_old = [c for c, _, _ in sorted(rows, key=lambda r: -r[1])]
            top_clean = [c for c, _, _ in sorted(rows, key=lambda r: -r[2])]
        if dstr < NEW_CODE_FROM:
            sig["OLD"][dstr] = top_old
            sig["CLEAN"][dstr] = top_clean
        else:
            sig["NEW"][dstr] = top_old
    return sig, ref_bars, ref_cal


def name_close_map(code6):
    bars = load_kline(code6)
    if not bars:
        return None
    return {b["date"]: float(b["close"]) for b in bars}, {b["date"]: i for i, b in enumerate(bars)}


def run_rolling(sysver, signals_d, ref_bars, ref_cal, N, H):
    """滚动组合净值曲线。signals_d: {date: [codes ordered]}。返回统计 dict 或 None。"""
    # 计算每只信号日的进入日(开)与退出日(收)在 ref 日历的索引
    sched = []  # (start_idx, end_idx, [codes up to N])
    valid_dates = set(ref_cal)
    for dstr, codes in signals_d.items():
        dashed = f"{dstr[:4]}-{dstr[4:6]}-{dstr[6:]}"
        if dashed not in valid_dates:
            continue
        di = ref_cal[dashed]
        si = di + 1          # 次日开盘进入
        ei = di + H          # 持有 H 交易日，ei-1 为最后持仓日
        if si >= len(ref_bars):
            continue
        sched.append((si, ei, codes[:N]))
    if not sched:
        return None
    max_end = max(ei for _, ei, _ in sched)
    # 预载持仓票 close 映射
    cmap = {}
    for _, _, codes in sched:
        for c in codes:
            if c not in cmap:
                cmap[c] = name_close_map(c)
    sched.sort(key=lambda x: x[0])
    # 逐交易日推进
    equity = 1.0
    peak = 1.0
    maxdd = 0.0
    start_idx = min(si for si, _, _ in sched)
    end_idx = min(max_end, len(ref_bars) - 1)
    # 窗口内的信号按 start 分组
    cur = []  # 当前持仓 (code, exit_idx)
    si_ptr = 0
    sched_by_start = sorted(sched, key=lambda x: x[0])
    daily_rets = []
    for j in range(start_idx, end_idx + 1):
        date = ref_bars[j]["date"]
        # 进入
        while si_ptr < len(sched_by_start) and sched_by_start[si_ptr][0] == j:
            si, ei, codes = sched_by_start[si_ptr]
            for c in codes:
                if c not in cur_codes(cur):
                    cur.append([c, ei])
            si_ptr += 1
        # 当日收益（等权，先按当前持仓算——持仓整天持有，日末才退出）
        n_enter = len([1 for si, ei, codes in sched_by_start if si == j])
        n_hold = len(cur)
        if n_hold == 0:
            cur = []
            continue
        tot = 0.0
        ok = 0
        for c, ei in cur:
            mp = cmap.get(c)
            if not mp:
                continue
            close_d = mp[0].get(date)
            prev = mp[0].get(ref_bars[j - 1]["date"]) if j > start_idx else None
            if close_d is None or prev is None or prev <= 0:
                continue
            tot += close_d / prev - 1.0
            ok += 1
        if ok == 0:
            cur = []
            continue
        r = tot / ok
        # 退出（日末结算后移除到期持仓）
        still = []
        n_exit = 0
        for c, ei in cur:
            if j >= ei:
                n_exit += 1
            else:
                still.append([c, ei])
        cur = still
        cost = ((n_enter + n_exit) / (2.0 * n_hold)) * COST
        r_after = r - cost
        equity *= (1.0 + r_after)
        daily_rets.append(r_after)
        if equity > peak:
            peak = equity
        maxdd = min(maxdd, equity / peak - 1.0)
    if equity <= 1.0 and len(daily_rets) == 0:
        return None
    # CAGR（交易日年化）
    n_days = end_idx - start_idx + 1
    cagr = (equity ** (252.0 / n_days) - 1.0) if n_days > 0 and equity > 0 else None
    win = (sum(1 for x in daily_rets if x > 0) / len(daily_rets)) if daily_rets else None
    # 逐年
    years = {}
    yr_equity_start = 1.0
    prev_year = None
    for idx in range(start_idx, end_idx + 1):
        y = ref_bars[idx]["date"][:4]
        if y != prev_year:
            if prev_year is not None and y + "_eq" not in years:
                pass
            years.setdefault(y, {})
            years[y]["start"] = equity if idx > start_idx else 1.0
            prev_year = y
        years[y]["end"] = equity
    yearly = {}
    for y, v in years.items():
        if "start" in v and "end" in v and v["end"] > 0:
            yearly[y] = round(v["end"] / v["start"] - 1, 4)
    # 单笔 tranche 均值（与头对头一致的股票事件口径，便于交叉核对）
    tranche_rets = []
    for si, ei, codes in sched:
        comp = []
        for c in codes[:N]:
            mp = cmap.get(c)
            if not mp:
                continue
            ent_idx = si - 1          # 入场基准 = 信号日收盘（si 前一交易日）
            ex_idx = ei              # 退出基准 = 末持仓日收盘(=si+H-1 那天的收盘, 与滚动模型一致)
            if ent_idx < 0 or ex_idx >= len(ref_bars):
                continue
            ent_date = ref_bars[ent_idx]["date"]
            ex_date = ref_bars[ex_idx]["date"]
            if ent_date not in mp[0] or ex_date not in mp[0]:
                continue
            comp.append(mp[0][ex_date] / mp[0][ent_date] - 1.0 - COST)
        if comp:
            tranche_rets.append(sum(comp) / len(comp))
    tm = sum(tranche_rets) / len(tranche_rets) if tranche_rets else None
    tt, tn = _tstat(tranche_rets)
    return {
        "n_signals": len(sched), "n_tranche_events": len(tranche_rets),
        "n_hold_days": n_days, "final_equity": round(equity, 4),
        "cagr": round(cagr, 4) if cagr is not None else None,
        "maxdd": round(maxdd, 4), "daily_win": round(win, 4) if win is not None else None,
        "yearly": yearly,
        "tranche_mean": round(tm, 5) if tm is not None else None,
        "tranche_t": round(tt, 2) if tt is not None else None,
        "tranche_win": round(sum(1 for x in tranche_rets if x > 0) / len(tranche_rets), 4) if tranche_rets else None,
    }


def cur_codes(cur):
    return {c for c, _ in cur}


def _tstat(xs):
    n = len(xs)
    if n < 2:
        return None, n
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    # 数值退化（var≈0，如所有单笔收益几乎相同）：t 无意义，返回 None 而非假大数
    if var <= 1e-12:
        return None, n
    return m / math.sqrt(var / n), n


def main():
    sig, ref_bars, ref_cal = build_signals()
    print(f"信号收集：OLD={len(sig['OLD'])} CLEAN={len(sig['CLEAN'])} NEW={len(sig['NEW'])} 天")
    result = {}
    for sysver in ("OLD", "CLEAN", "NEW"):
        sd = sig[sysver]
        result[sysver] = {}
        for N in NS:
            for H in HS:
                st = run_rolling(sysver, sd, ref_bars, ref_cal, N, H)
                result[sysver][f"N{N}H{H}"] = st
                tag = f"{sysver:5s} N{N} H{H}"
                if st:
                    print(f"{tag} | 信号{st['n_signals']:>3} 净权益{st['final_equity']:>7.3f} "
                          f"CAGR{'' if st['cagr'] is None else format(st['cagr']*100,'.1f')+'%'} "
                          f"MaxDD{'' if st['maxdd'] is None else format(st['maxdd']*100,'.1f')+'%'} "
                          f"日胜{'' if st['daily_win'] is None else format(st['daily_win']*100,'.1f')+'%'} "
                          f"单笔均{'' if st['tranche_mean'] is None else format(st['tranche_mean']*100,'.2f')+'%'}/t{st['tranche_t']}")
                else:
                    print(f"{tag} | 数据不足跳过")
    # 组合层 OLD vs CLEAN 配对（同 N,H）
    cmp = {}
    for key in result["OLD"]:
        o = result["OLD"][key]; c = result["CLEAN"].get(key)
        if o and c:
            cmp[key] = {"OLD_cagr": o["cagr"], "CLEAN_cagr": c["cagr"],
                        "OLD_tranche": o["tranche_mean"], "CLEAN_tranche": c["tranche_mean"],
                        "delta_tranche": (round(c["tranche_mean"] - o["tranche_mean"], 5)
                                          if o["tranche_mean"] and c["tranche_mean"] else None)}
    out = {
        "generated": "2026-10-25",
        "desc": "端到端系统回放·组合层（dated top10 归档=系统真实发出名单，滚动等权满仓，双边0.3%）",
        "params": {"N": list(NS), "H": list(HS), "cost": COST, "weight": "equal", "model": "rolling_full_invest"},
        "sysver": {
            "OLD": "归档真实total_score排序(旧代码,<20261024)",
            "CLEAN": "旧档同日清零DELIST_DIMS九维重排(清账口径)",
            "NEW": "2026-10-25纯净档(仅1信号日,曲线不足)",
        },
        "result": result, "old_vs_clean": cmp,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[ok] {OUT}")
    print("\n===== 组合层 OLD vs CLEAN（清账是否变好，单笔均收益）=====")
    for key in sorted(cmp):
        v = cmp[key]
        d = v["delta_tranche"]
        print(f"{key}: OLD {'' if v['OLD_tranche'] is None else format(v['OLD_tranche']*100,'.2f')+'%'} "
              f"→ CLEAN {'' if v['CLEAN_tranche'] is None else format(v['CLEAN_tranche']*100,'.2f')+'%'} "
              f"Δ {'' if d is None else format(d*100,'+.2f')+'%'}")


if __name__ == "__main__":
    main()
