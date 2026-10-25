# -*- coding: utf-8 -*-
"""
删前/删后 TOP10 头对头回放（2026-10-25 主人令「一定要周一么？今晚不行试试？」）

问题：2026-10-25 因子清账下架 14 项后，TOP10 的实际前向收益到底有没有变好？
      （纪律：代码改了 ≠ 已验证生效。不等周一实盘，今晚用历史归档回放头对头。）

两臂设计（同一归档日、同一候选名单、同一前向口径，只有排序规则不同）：
  删前臂(OLD) = 归档真实 top10（旧代码 total_score 排序，含全部 27 项因子）
  删后臂(NEW) = 同日把 DELIST_DIMS 九维度的分数贡献清零后重排取前 10
      可精确扣减（归档逐字段在案）：fund / sector / quality / form(×0.7) / research /
      brk5 / inst —— score_inst、score_quality 归档值已是加权后值，直接减
      需重算扣减（归档折叠在 enhance 里）：consec(×2 封顶8, consecutive_days 在案) /
      rsi<30(+3, RSI14 由 kline_cache_multi 按 scanner.calc_rsi 同款 SMA 复算) /
      温和上涨 0<pct20<10(+2, pct_chg_20d 在案)
  净残差 = base + enhance + backtest + winrate(如有) − 上述被删分量 ⇒ 按 monotonic
  变换（gate_multiplier / NORM_DIVISOR / clamp 为逐日常数或边界效应）排序等价。

  变体 B（敏感性）：只扣"归档逐字段在案"的 7 维，不碰 consec/rsi/mild 小分量，
  检验小分量公式漂移（P2 再平衡改过档位值）是否影响结论。

校验门（证据先行）：
  每归档日先验证 legacy_raw×regime_adj 的排序 vs 归档 total_score 排序的一致率
  （pairwise concordance）——不一致的归档（如 10-23 起混入 winrate rank-fusion 的档）
  剔除主统计，单列报告。

前向口径：信号日=归档日（取 ≤ 归档日最后根K线），次日开盘买入 → T+N 收盘卖出，
  双边 0.30%；N = 1 / 5 / 10。两臂完全同口径 ⇒ 配对差分有效。

产出：raw_data/delist_headtohead_verdict.json
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
OUT = os.path.join(RAW, "delist_headtohead_verdict.json")

FORM_WEIGHT = 0.7          # generate_top10.py L75
COST = 0.003               # 双边 0.30%（与回测铁律口径一致）
HORIZONS = (1, 5, 10)
NEW_CODE_FROM = "20261024"  # 10-25 14:48 起为纯净版代码；之前的归档=旧代码
CONCORD_MIN = 0.90

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
    """scanner.calc_rsi 同款：SMA 方式 RSI14（rolling mean，非 Wilder）——同 verify_untested_factors.py。"""
    if j < 14:
        return None
    gains, losses = [], []
    for k in range(j - 13, j + 1):
        p0, p1 = float(bars[k - 1]["close"]), float(bars[k]["close"])
        d = p1 - p0 if p0 > 0 else 0.0
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains) / 14.0
    al = sum(losses) / 14.0
    if al <= 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def _num(x, default=0.0):
    return float(x) if isinstance(x, (int, float)) else default


def concordance(order_a, order_b):
    """pairwise 一致率：两排序在所有可比分对上方向一致的比例。"""
    n = len(order_a)
    if n < 2:
        return 1.0
    agree = total = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = order_a[i] - order_a[j]
            db = order_b[i] - order_b[j]
            if da == 0 or db == 0:
                continue
            total += 1
            if (da > 0) == (db > 0):
                agree += 1
    return agree / total if total else 1.0


def tstat(xs):
    n = len(xs)
    if n < 2:
        return None, n
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    if var <= 0:
        return (None if m == 0 else math.copysign(99, m)), n
    return m / math.sqrt(var / n), n


def fwd_returns(code6, sig_date, cost=COST):
    """信号日=≤sig_date 最后根K线；次日开盘买 → T+N 收盘卖。返回 {N: ret} 或 None。"""
    bars = load_kline(code6)
    if not bars or len(bars) < 30:
        return None
    sig = None
    for i in range(len(bars) - 1, -1, -1):
        if str(bars[i].get("date", "")).replace("-", "") <= sig_date:
            sig = i
            break
    if sig is None or sig + 1 >= len(bars):
        return None
    try:
        entry = float(bars[sig + 1]["open"])
        if entry <= 0:
            return None
    except Exception:
        return None
    out = {}
    for n in HORIZONS:
        k = sig + n
        if k >= len(bars):
            continue
        c = float(bars[k]["close"])
        if c <= 0:
            continue
        out[n] = (c / entry - 1.0) - cost
    return out if out else None


def main():
    files = sorted(glob.glob(os.path.join(HIST, "top10_daily_*.json")))
    files = [f for f in files if re.search(r"_(\d{8})\.json$", f)
             and re.search(r"_(\d{8})\.json$", f).group(1) < NEW_CODE_FROM]
    print(f"旧代码 dated 归档：{len(files)} 份（< {NEW_CODE_FROM}）")

    days = []
    val_fail = []
    for f in files:
        dstr = re.search(r"_(\d{8})\.json$", f).group(1)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        entries = d.get("top10") or []
        if len(entries) < 5:
            continue
        # 构建分量
        rows = []
        for e in entries:
            code6 = re.sub(r"\D", "", str(e.get("code", "")))
            if len(code6) != 6:
                continue
            base = _num(e.get("score_base"))
            enh = _num(e.get("score_enhance"))
            form = _num(e.get("score_form"))
            fund = _num(e.get("score_fund"))
            sec = _num(e.get("score_sector"))
            inst = _num(e.get("score_inst"))
            qua = _num(e.get("score_quality"))
            bt = _num(e.get("score_backtest"))
            res = _num(e.get("score_research"))
            brk = _num(e.get("score_breakout"))
            wr = _num(e.get("score_winrate")) if e.get("score_winrate") is not None else 0.0
            total = e.get("total_score")
            regime = _num(e.get("regime_adjust"), 1.0) or 1.0
            consec = int(_num(e.get("consecutive_days")))
            pct20 = _num(e.get("pct_chg_20d"))
            legacy_raw = base + enh + fund + sec + inst + qua + bt + form * FORM_WEIGHT + wr
            rows.append({
                "code": code6, "name": e.get("name", ""), "total": total,
                "legacy_raw": legacy_raw, "regime": regime,
                "del_exact": fund + sec + qua + form * FORM_WEIGHT + res + brk + inst,
                "consec_b": min(max(consec, 0) * 2, 8),
                "pct20": pct20, "rank": e.get("rank"),
            })
        if len(rows) < 5:
            continue
        # 校验门：legacy_raw×regime 排序 vs total_score 排序
        oa = [r["legacy_raw"] * r["regime"] for r in rows]
        ob = [_num(r["total"], -999) for r in rows]
        conc = concordance(oa, ob)
        top_n = min(10, len(rows))
        day = {"date": dstr, "conc": round(conc, 4), "n": len(rows), "rows": rows,
               "top_n": top_n}
        if conc >= CONCORD_MIN:
            days.append(day)
        else:
            val_fail.append({"date": dstr, "conc": round(conc, 4), "n": len(rows)})
    print(f"过校验门(≥{CONCORD_MIN})：{len(days)} 天 | 剔除：{len(val_fail)} 天 "
          f"{[v['date'] for v in val_fail][:8]}")

    # 两臂前向收益
    per_horizon = {n: {"old": [], "newA": [], "newB": []} for n in HORIZONS}
    per_day = []   # 配对差分（按日均值）
    audit = []
    for day in days:
        dstr = day["date"]
        rows = day["rows"]
        # 删后排序（变体A 全扣 / 变体B 只扣在案7维）
        for r in rows:
            bars = load_kline(r["code"])
            r["rsi30_b"] = 0.0
            if bars:
                sig_i = None
                for i in range(len(bars) - 1, -1, -1):
                    if str(bars[i].get("date", "")).replace("-", "") <= dstr:
                        sig_i = i
                        break
                if sig_i is not None:
                    rsi = rsi14_at(bars, sig_i)
                    if rsi is not None and rsi < 30:
                        r["rsi30_b"] = 3.0
            r["mild_b"] = 2.0 if 0 < r["pct20"] < 10 else 0.0
            r["cleanA"] = r["legacy_raw"] - r["del_exact"] - r["consec_b"] - r["rsi30_b"] - r["mild_b"]
            r["cleanB"] = r["legacy_raw"] - r["del_exact"]
        old_top = sorted(rows, key=lambda r: -_num(r["total"], -999))[:day["top_n"]]
        newA_top = sorted(rows, key=lambda r: -r["cleanA"])[:day["top_n"]]
        newB_top = sorted(rows, key=lambda r: -r["cleanB"])[:day["top_n"]]
        # 前向收益
        arm_rets = {arm: {n: [] for n in HORIZONS} for arm in ("old", "newA", "newB")}
        for arm, lst in (("old", old_top), ("newA", newA_top), ("newB", newB_top)):
            for r in lst:
                fr = fwd_returns(r["code"], dstr)
                if fr:
                    for n in HORIZONS:
                        if n in fr:
                            per_horizon[n][arm].append(fr[n])
                            arm_rets[arm][n].append(fr[n])
        # 配对（按日均值差）
        diffs = {}
        for n in HORIZONS:
            if arm_rets["old"][n] and arm_rets["newA"][n]:
                diffs[n] = (sum(arm_rets["newA"][n]) / len(arm_rets["newA"][n])
                            - sum(arm_rets["old"][n]) / len(arm_rets["old"][n]))
        overlap = (len(set(r["code"] for r in old_top) & set(r["code"] for r in newA_top)))
        per_day.append({"date": dstr, "conc": day["conc"], "n": day["n"],
                        "overlap10": overlap, "top_n": day["top_n"], "diffs": diffs,
                        "old_mean": {n: (sum(arm_rets['old'][n]) / len(arm_rets['old'][n])
                                         if arm_rets['old'][n] else None)
                                     for n in HORIZONS},
                        "newA_mean": {n: (sum(arm_rets['newA'][n]) / len(arm_rets['newA'][n])
                                          if arm_rets['newA'][n] else None)
                                      for n in HORIZONS}})
        audit.append({"date": dstr, "old": [r["code"] for r in old_top],
                      "newA": [r["code"] for r in newA_top],
                      "changed": sum(1 for a, b in zip(old_top, newA_top) if a["code"] != b["code"])})

    # 汇总统计
    summary = {}
    for n in HORIZONS:
        row = {}
        for arm in ("old", "newA", "newB"):
            xs = per_horizon[n][arm]
            t, cnt = tstat(xs)
            m = sum(xs) / len(xs) if xs else None
            w = (sum(1 for x in xs if x > 0) / len(xs)) if xs else None
            row[arm] = {"n": cnt, "mean": round(m, 5) if m is not None else None,
                        "win": round(w, 4) if w is not None else None,
                        "t": round(t, 2) if t is not None else None}
        # 配对差分（按日）
        ds = [p["diffs"].get(n) for p in per_day
              if isinstance(p["diffs"].get(n), (int, float))]
        td, cd = tstat(ds)
        row["paired_diff_newA_minus_old"] = {
            "n_days": cd,
            "mean": round(sum(ds) / len(ds), 5) if ds else None,
            "t": round(td, 2) if td is not None else None,
            "win_days": round(sum(1 for x in ds if x > 0) / len(ds), 4) if ds else None,
        }
        summary[f"T{n}"] = row

    print("\n===== 头对头结果（删前 OLD vs 删后 NEW-A 全扣 / NEW-B 仅在案7维）=====")
    for h, row in summary.items():
        line = f"{h}: "
        for arm in ("old", "newA", "newB"):
            r = row[arm]
            line += f"{arm} n={r['n']} mean={'' if r['mean'] is None else format(r['mean']*100,'.2f')+'%'} " \
                    f"win={'' if r['win'] is None else format(r['win']*100,'.1f')+'%'} t={r['t']} | "
        pd_ = row["paired_diff_newA_minus_old"]
        line += f"配对(A−O) 天数={pd_['n_days']} 均差={'' if pd_['mean'] is None else format(pd_['mean']*100,'.3f')+'%'} t={pd_['t']} 胜率={pd_['win_days']}"
        print(line)

    out = {
        "generated": "2026-10-25",
        "question": "因子清账下架14项后 TOP10 前向收益是否变好（不等周一，归档回放头对头）",
        "archives_old_code": len(files), "days_used": len(days),
        "days_val_excluded": val_fail, "concord_min": CONCORD_MIN,
        "arm_def": {
            "old": "归档真实top10（total_score 排序）",
            "newA": "DELIST_DIMS 9维全扣（fund/sector/quality/form×0.7/research/brk5/inst 归档在案 + consec×2封顶8 + rsi<30 +3(kline复算RSI) + 温和上涨+2）",
            "newB": "仅扣归档逐字段在案7维（敏感性变体）",
        },
        "fwd": "信号日≤归档日最后K线，次日开盘买→T+N收盘卖，双边0.30%",
        "summary": summary,
        "per_day": per_day,
        "audit_lists": audit,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[ok] {OUT}")
    # 名单变动概览
    ch = [a for a in audit if a["changed"]]
    print(f"名单变动天数：{len(ch)}/{len(audit)}；平均每期变动 {sum(a['changed'] for a in audit)/max(1,len(audit)):.1f} 席")


if __name__ == "__main__":
    main()
