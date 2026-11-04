#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FF3 组合方式升级对比回测（2026-10-24 主人令「设计好后要确认真的有收益率的提升才开始动手，不能拍脑袋」）

目的：在动手改 gen_ff3_ranksum.py 之前，用与生产完全同源的引擎（factor_walkforward：
同 _wf_cache 宇宙 / 同 make_prep+make_resid_prep 因子口径 / 同 _trade_ret 执行约束+成本）
对「组合方式」候选方案做头对头回测，只有真跑出收益提升才允许上线。

【候选方案】
  S0  等权秩和（现役）：三因子各降序归一化秩 [0,1]，复合分=秩和，Top5。        ← 现役基线
  S_z z-score 复合：三因子截面 z-score 等权和（对离群敏感，预期不优，作对照）。
  S_icW  滚动 IC 加权（候选升级）：逐调仓点用**过去 W 个调仓点**的各因子 IC（Spearman，
         因子值 vs 前向可成交净收益，因果无前视）均值为权重（负 IC 截 0，归一化）；
         全因子 IC ≤ 0 时回退等权。W=12（约 120 交易日）主口径，W=6/W=24 敏感性。
  S_icFull 全样本 IC 加权（仅作天花板诊断，含前视，**永不上线**）。

【判优规则（预注册，防拍脑袋）】
  以主持有期 T+10 为准（T+5/T+20 一致性作佐证），S_icW 相对 S0 必须同时满足：
    ① 每笔平均净收益提升 ≥ +0.30%（30bp/笔）
    ② 逐调仓点配对胜率 ≥ 55%（S_icW 优于 S0 的日期占比）
    ③ T+5 与 T+20 档方向一致（同正）
  全部满足 → 准入上线；任一不满足 → 维持 S0 并把结论落档（本轮即「证据否决」）。

【口径与限制（如实声明）】
  · 宇宙 = 本地 _wf_cache 603 只（云端全宇宙 ~5000+ 只的子集）——方案间**相对比较**有效，
    绝对收益水平与全宇宙榜单会有差异；上线后由 ff3_ranksum 真实信号流继续跟踪验证。
  · 执行约束与成本 = factor_walkforward._trade_ret（次开买入/一字板剔除/跌停顺延/双边成本），
    与云上生产同口径，非简化近似。
  · 调仓点 STEP=10（与 factor_walkforward 同），样本期 ~2019 → 2026-09（本地缓存末根）。

输出：
  控制台对比表 + raw_data/ff3_upgrade_backtest_report.json（落档备查）
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))

import factor_walkforward as fw  # noqa: E402  零第二口径：同引擎/同因子/同执行

RAW_DIR = os.path.join(ROOT, "raw_data")
CACHE_DIR = os.path.join(RAW_DIR, "_wf_cache")
REPORT = os.path.join(RAW_DIR, "ff3_upgrade_backtest_report.json")

TOP_N = 5
FACTORS3 = ("turntrend", "amt60", "ivol60")
HOLDS = (5, 10, 20)
HOLD_PRIMARY = 10
IC_WINDOWS = (6, 12, 24)          # 敏感性；主口径 W=12
STEP = fw.STEP                    # 10，与 factor_walkforward 同
MIN_VALID = 15                    # 截面有效数保护（与 run_factor 同）

_t0 = time.time()


def log(msg):
    print("[%7.1fs] %s" % (time.time() - _t0, msg), flush=True)


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def load_names():
    """当前名单（ST/退 过滤，与 gen_ff3_ranksum 同）。"""
    p = os.path.join(RAW_DIR, "stock_names.json")
    names = {}
    try:
        with open(p, encoding="utf-8") as f:
            for s in (json.load(f).get("data") or []):
                fc = s.get("full_code") or ""
                if isinstance(fc, str) and fc.startswith(("sh", "sz")):
                    code6 = fc[2:]
                    if code6.isdigit():
                        names[code6] = s.get("name") or code6
    except Exception as e:
        log("⚠️ stock_names.json 不可用（名称/ST 过滤降级）: %s" % str(e)[:80])
    return {c: n for c, n in names.items()
            if "ST" not in n.upper() and "退" not in n}


def rank_norm(vals_by_code, k):
    """单因子降序归一化秩 [0,1]（值越大=越强；因子值均已同向化，bigger=stronger）。"""
    n = len(vals_by_code)
    if n < 2:
        return {c: 0.5 for c in vals_by_code}
    order = sorted(vals_by_code.items(), key=lambda kv: -kv[1])
    out = {}
    for pos, (c, _v) in enumerate(order):
        out[c] = 1.0 - pos / float(n - 1)
    return out


def z_norm(vals_by_code):
    """截面 z-score（离群敏感，仅作对照）。"""
    n = len(vals_by_code)
    if n < 3:
        return {c: 0.0 for c in vals_by_code}
    xs = list(vals_by_code.values())
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    sd = var ** 0.5
    if sd <= 0:
        return {c: 0.0 for c in vals_by_code}
    return {c: (v - m) / sd for c, v in vals_by_code.items()}


def top5_pick(comp):
    """复合分降序 Top5。"""
    return sorted(comp, key=lambda c: -comp[c])[:TOP_N]


def avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def main():
    log("=" * 78)
    log("  FF3 组合方式升级对比回测（S0 等权秩和 vs 候选升级）  %s"
        % now_cst().strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 78)

    codes = [fn[:-5] for fn in os.listdir(CACHE_DIR)
             if fn.endswith(".json") and fn[:-5].isdigit() and len(fn[:-5]) == 6]
    names = load_names()
    codes = [c for c in codes if c in names] or codes
    log("_wf_cache 宇宙：%d 只（names 过滤后）" % len(codes))

    klines = fw.get_klines(codes, 4, False)
    if len(klines) < 100:
        raise SystemExit("有效 K 线不足（%d）" % len(klines))
    log("有效 K 线：%d 只" % len(klines))
    dates, pos, bars = fw.build_panel(klines)
    n = len(dates)
    log("全局交易日轴：%d 天  %s → %s" % (n, dates[0], dates[-1]))

    # 全池等权日收益（ivol60 残差基准，与 gen_ff3 同源）
    log("计算全池等权日收益 …")
    pool_sum = [0.0] * n
    pool_cnt = [0] * n
    for c, rows in klines.items():
        r, _ = fw.stock_series(rows)
        p = pos[c]
        for g, i in enumerate(p):
            if i > 0:
                pool_sum[g] += r[i]
                pool_cnt[g] += 1
    pool_r = [(pool_sum[g] / pool_cnt[g]) if pool_cnt[g] else 0.0 for g in range(n)]
    log("  完成（有效日均 %d 只）" % (sum(pool_cnt) // max(1, n)))

    # 调仓点
    ts = []
    t = fw.MIN_BARS
    while t + 1 + max(HOLDS) < n:
        ts.append(t)
        t += STEP
    log("调仓点：%d 个（STEP=%d，%s → %s）" % (len(ts), STEP, dates[ts[0]], dates[ts[-1]]))

    # 因子截面值 + 前向可成交净收益（同源 _trade_ret，含执行约束与成本）
    log("预计算因子截面值与前向净收益（_trade_ret，含一字板/跌停约束）…")
    fv = {k: {} for k in FACTORS3}      # fv[k][t] = {code: value}
    rets = {}                            # rets[t] = {code: {hold: ret}}
    for c, rows in klines.items():
        if len(rows) < fw.MIN_BARS:
            continue
        d = fw.make_prep(rows)
        pool_at = [None] * len(rows)
        p = pos[c]
        for g, ii in enumerate(p):
            if ii >= 0:
                pool_at[ii] = pool_r[g]
        d["f"].update(fw.make_resid_prep(rows, pool_at))
        for t in ts:
            i = p[t]
            if i < fw.MIN_BARS or i < 0:
                continue
            vs = {}
            ok = True
            for k in FACTORS3:
                fn = d["f"].get(k)
                v = fn(i) if fn else None
                if v is None:
                    ok = False
                    break
                vs[k] = v
            if not ok:
                continue
            for k in FACTORS3:
                fv[k].setdefault(t, {})[c] = vs[k]
            rt = {}
            for h in HOLDS:
                rt[h] = fw._trade_ret(bars[c], i, h, c)
            rets.setdefault(t, {})[c] = rt
    log("  完成。")

    # 截面有效集（三因子齐备 + 当期 T+PRIMARY 可成交）——方案公平比较的公共集
    panels = []   # (t, codes_common)
    for t in ts:
        cs = [c for c in (fv["turntrend"].get(t) or {})
              if c in (fv["amt60"].get(t) or {}) and c in (fv["ivol60"].get(t) or {})
              and c in rets.get(t, {}) and rets[t][c][HOLD_PRIMARY] is not None]
        if len(cs) >= MIN_VALID:
            panels.append((t, cs))
    log("有效调仓截面：%d/%d（≥%d 只）" % (len(panels), len(ts), MIN_VALID))
    if len(panels) < 30:
        raise SystemExit("有效截面不足 30，样本不可信，拒绝出结论")

    # 逐因子逐持有期 IC 序列（供滚动 IC 加权；因果：只用过去）
    ic_hist = {h: {k: {} for k in FACTORS3} for h in HOLDS}   # ic_hist[h][k][t] = ic
    for t, cs in panels:
        for h in HOLDS:
            for k in FACTORS3:
                pairs = [(fv[k][t][c], rets[t][c][h]) for c in cs
                         if rets[t][c].get(h) is not None]
                ic = fw._spearman(pairs) if len(pairs) >= MIN_VALID else None
                ic_hist[h][k][t] = ic

    def scheme_composite(t, cs, scheme, hold):
        """返回 {code: composite}；scheme ∈ S0/S_z/S_icW{W}/S_icFull。"""
        if scheme == "S0":
            ranks = [rank_norm({c: fv[k][t][c] for c in cs}, k) for k in FACTORS3]
            return {c: ranks[0][c] + ranks[1][c] + ranks[2][c] for c in cs}
        if scheme == "S_z":
            zs = [z_norm({c: fv[k][t][c] for c in cs}) for k in FACTORS3]
            return {c: zs[0][c] + zs[1][c] + zs[2][c] for c in cs}
        if scheme == "S_icFull":
            w = {}
            for k in FACTORS3:
                ics = [v for tt, v in ic_hist[hold][k].items() if v is not None]
                w[k] = max(avg(ics) or 0.0, 0.0)
            s = sum(w.values())
            if s <= 0:
                w = {k: 1.0 for k in FACTORS3}
                s = 3.0
            ranks = [rank_norm({c: fv[k][t][c] for c in cs}, k) for k in FACTORS3]
            return {c: sum(w[k] / s * ranks[j][c] for j, k in enumerate(FACTORS3)) for c in cs}
        if scheme.startswith("S_icW"):
            W = int(scheme[5:])
            prior_ts = [tt for tt in ic_hist[hold][FACTORS3[0]].keys() if tt < t][-W:]
            w = {}
            for k in FACTORS3:
                ics = [ic_hist[hold][k][tt] for tt in prior_ts
                       if ic_hist[hold][k].get(tt) is not None]
                w[k] = max(avg(ics) or 0.0, 0.0)
            s = sum(w.values())
            if s <= 0:
                w = {k: 1.0 for k in FACTORS3}
                s = 3.0
            ranks = [rank_norm({c: fv[k][t][c] for c in cs}, k) for k in FACTORS3]
            return {c: sum(w[k] / s * ranks[j][c] for j, k in enumerate(FACTORS3)) for c in cs}
        raise ValueError(scheme)

    SCHEMES = ["S0", "S_z", "S_icW6", "S_icW12", "S_icW24", "S_icFull"]
    stats = {s: {h: {"picks": [], "excess": [], "dates": 0} for h in HOLDS} for s in SCHEMES}
    paired = {h: [] for h in HOLDS}   # (t, S0_avg, S_icW12_avg)

    log("逐截面回测 %d 个方案 × %d 持有期 …" % (len(SCHEMES), len(HOLDS)))
    for t, cs in panels:
        base = {h: avg([rets[t][c][h] for c in cs if rets[t][c].get(h) is not None])
                for h in HOLDS}
        picks_cache = {}
        for s in SCHEMES:
            for h in HOLDS:
                comp = scheme_composite(t, cs, s, h)
                top = top5_pick(comp)
                rs = [rets[t][c][h] for c in top if rets[t][c].get(h) is not None]
                if len(rs) < TOP_N:      # 可成交不足 5 只的截面按实际只数计，不虚构
                    if not rs:
                        continue
                a = avg(rs)
                st = stats[s][h]
                st["picks"].append(a)
                if base.get(h) is not None:
                    st["excess"].append(a - base[h])
                st["dates"] += 1
                if s == "S0":
                    picks_cache[h] = a
        # 配对：S_icW12 vs S0（主候选）
        comp = scheme_composite(t, cs, "S_icW12", HOLD_PRIMARY)
        top = top5_pick(comp)
        rs = [rets[t][c][HOLD_PRIMARY] for c in top if rets[t][c].get(HOLD_PRIMARY) is not None]
        if rs and picks_cache.get(HOLD_PRIMARY) is not None:
            paired[HOLD_PRIMARY].append((t, picks_cache[HOLD_PRIMARY], avg(rs)))

    # ── 汇总与判优 ──
    def fmt_pct(x):
        return "--" if x is None else "%+.2f%%" % (x * 100)

    summary = {}
    log("")
    log("=" * 78)
    log("  对比结果（每笔平均净收益 / 超额 vs 全截面基准 / 样本日数）")
    log("=" * 78)
    log("%-9s %-5s %10s %12s %12s %8s" % ("方案", "持有", "均净收益", "超额/笔", "超额胜率", "日数"))
    for s in SCHEMES:
        for h in HOLDS:
            st = stats[s][h]
            a = avg(st["picks"])
            e = avg(st["excess"])
            wr = (sum(1 for x in st["excess"] if x > 0) / len(st["excess"]) * 100
                  if st["excess"] else None)
            tag = " ←现役" if s == "S0" else (" ←主候选" if s == "S_icW12" else
                  (" ←天花板(前视)" if s == "S_icFull" else ""))
            log("%-9s T+%-3d %10s %12s %12s %8d%s"
                % (s, h, fmt_pct(a), fmt_pct(e),
                   ("%.1f%%" % wr) if wr is not None else "--", st["dates"], tag))
            summary.setdefault(s, {})[h] = {
                "avg_ret": a, "avg_excess": e,
                "excess_winrate": wr, "n_dates": st["dates"],
            }

    # 判优（预注册规则）
    log("")
    log("=" * 78)
    d10 = [x2 - x1 for _t, x1, x2 in paired[HOLD_PRIMARY]]
    dpct = (sum(1 for x in d10 if x > 0) / len(d10) * 100) if d10 else None
    log("  预注册判优（S_icW12 vs S0，主持有期 T+%d）：" % HOLD_PRIMARY)
    log("    ① 每笔均净收益提升 ≥ +0.30%% ：实际 %s  → %s"
        % (fmt_pct(avg(d10)), "✅" if (avg(d10) or -9) >= 0.003 else "❌"))
    log("    ② 逐截面配对胜率 ≥ 55%%    ：实际 %s  → %s"
        % (("%.1f%%" % dpct) if dpct is not None else "--",
           "✅" if (dpct or 0) >= 55 else "❌"))
    e5 = summary.get("S_icW12", {}).get(5, {}).get("avg_excess")
    e5b = summary.get("S0", {}).get(5, {}).get("avg_excess")
    e20 = summary.get("S_icW12", {}).get(20, {}).get("avg_excess")
    e20b = summary.get("S0", {}).get(20, {}).get("avg_excess")
    dir5 = (e5 is not None and e5b is not None and (e5 - e5b) > 0)
    dir20 = (e20 is not None and e20b is not None and (e20 - e20b) > 0)
    log("    ③ T+5/T+20 方向一致（同正）  ：T+5 %s / T+20 %s → %s"
        % (fmt_pct((e5 or 0) - (e5b or 0)), fmt_pct((e20 or 0) - (e20b or 0)),
           "✅" if (dir5 and dir20) else "❌"))
    verdict = "PASS_ICW" if ((avg(d10) or -9) >= 0.003 and (dpct or 0) >= 55 and dir5 and dir20) else "KEEP_S0"
    log("  ⇒ 判定：%s" % ("滚动IC加权可上线" if verdict == "PASS_ICW" else "维持 S0 等权秩和（证据否决升级）"))
    log("=" * 78)

    out = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "FF3 组合方式升级证据回测（2026-10-24 主人令「确认真的有收益率的提升才开始动手」）",
        "universe": len(klines), "cache_dir": "_wf_cache（本地 603 只子集）",
        "data_range": [dates[0], dates[-1]], "n_panels": len(panels),
        "step": STEP, "top_n": TOP_N, "cost_included": True,
        "trade_rule": "次开买入/一字板剔除/跌停顺延/双边成本（factor_walkforward._trade_ret 同源）",
        "summary": summary,
        "paired_icw12_vs_s0_t10": {
            "mean_delta": avg(d10), "winrate_pct": dpct, "n": len(d10)},
        "verdict": verdict,
        "verdict_rule": "①Δ≥+0.30%/笔 ②配对胜率≥55% ③T+5/T+20 方向一致",
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log("[ok] 报告落盘 %s" % REPORT)


if __name__ == "__main__":
    main()
