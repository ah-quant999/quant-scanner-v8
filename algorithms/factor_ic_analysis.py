#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factor_ic_analysis.py — 因子有效性检验 / 可信回测框架（2026-08-28 新增）

目的：回答「哪个评分维度真的能预测收益」，为权重校准提供统计依据。

与旧回测（backtest_comprehensive.py）的三处关键差异：
  1. 入场价 = 信号日【次一交易日的开盘价】——消除前视偏差
     （旧回测用信号日收盘价，但信号 18:00 后才生成，实盘买不到）
  2. 扣除交易成本（默认往返 0.20%）
  3. 输出因子 IC（Spearman 秩相关）+ 分层表现，而非只看总分分层

用法：
  python factor_ic_analysis.py                # 全样本
  python factor_ic_analysis.py --split-date 2026-08-01   # 样本内/外切分

输出：
  raw_data/factor_ic_report.json
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
HIST_DIR = os.path.join(ROOT, "raw_data", "history")
KLINE_DIR = os.path.join(ROOT, "raw_data", "kline_cache")
OUT_JSON = os.path.join(ROOT, "raw_data", "factor_ic_report.json")

# 交易成本（往返，含印花税+佣金+滑点）
COST_ROUNDTRIP = 0.0020
HOLDS = [1, 3, 5, 10, 20]

FACTORS = [
    "score_base", "score_enhance", "score_form", "score_fund",
    "score_sector", "score_inst", "score_quality", "score_backtest",
    "total_score", "sig_count", "consecutive_days", "pct_chg_20d",
]


def _log(msg=""):
    print(msg, flush=True)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


# --------------------------------------------------------------------------
# K 线缓存
# --------------------------------------------------------------------------
_KLINE_CACHE = {}


def get_kline(code):
    """返回 [(date, open, close), ...] 按日期升序；无数据返回 None"""
    if code in _KLINE_CACHE:
        return _KLINE_CACHE[code]
    p = os.path.join(KLINE_DIR, f"{code}.json")
    data = load_json(p)
    rows = None
    if isinstance(data, list) and data:
        rows = []
        for r in data:
            try:
                d = r.get("date")
                o = float(r.get("open") or 0)
                c = float(r.get("close") or 0)
            except (TypeError, ValueError):
                continue
            if d and o > 0 and c > 0:
                rows.append((d, o, c))
        rows.sort(key=lambda x: x[0])
    _KLINE_CACHE[code] = rows
    return rows


def _bisect_after(rows, date_str):
    """返回 rows 中第一个 date > date_str 的下标；找不到返回 -1"""
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid][0] <= date_str:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(rows) else -1


def future_returns(code, signal_date, holds=HOLDS, cost=COST_ROUNDTRIP):
    """
    计算未来收益。
    入场 = 信号日之后第一个交易日的【开盘价】
    出场 = 入场日起第 n 个交易日的【收盘价】
    返回 {n: net_return_pct}（已扣成本）
    """
    rows = get_kline(code)
    if not rows:
        return None
    i = _bisect_after(rows, signal_date)
    if i < 0:
        return None                      # 信号日之后无数据（停牌/最新一天）
    entry = rows[i][1]                   # 次日开盘
    if entry <= 0:
        return None
    out = {}
    for n in holds:
        j = i + n - 1                    # 持有 n 日 → 第 n 根 K 线收盘
        if j >= len(rows):
            continue
        exit_p = rows[j][2]
        if exit_p <= 0:
            continue
        gross = (exit_p - entry) / entry * 100
        out[n] = gross - cost * 100      # 成本以百分点计
    return out or None


# --------------------------------------------------------------------------
# 统计工具
# --------------------------------------------------------------------------
def _rank(vals):
    """平均秩（并列取均值）"""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman 秩相关；样本 <5 或常数序列返回 None"""
    n = len(xs)
    if n < 5 or len(ys) != n:
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx <= 0 or dy <= 0:
        return None
    return num / (dx * dy) ** 0.5


def _mean(v):
    return sum(v) / len(v) if v else 0.0


def summarize(records, label=""):
    """records: [{n: ret}, ...] → 各持有期胜率/平均收益"""
    res = {}
    for n in HOLDS:
        vals = [r[n] for r in records if n in r]
        if not vals:
            continue
        wins = sum(1 for v in vals if v > 0)
        res[f"T{n}"] = {
            "n": len(vals),
            "win_rate": round(wins / len(vals) * 100, 1),
            "avg_return": round(_mean(vals), 3),
            "median": round(sorted(vals)[len(vals) // 2], 3),
        }
    return {"label": label, "periods": res}


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def collect_signals(split_date=None):
    """收集历史信号 → [(date, item, is_oos), ...]"""
    in_sample, out_sample = [], []
    if not os.path.isdir(HIST_DIR):
        _log(f"  ❌ 历史目录不存在: {HIST_DIR}")
        return in_sample, out_sample
    files = sorted(f for f in os.listdir(HIST_DIR)
                   if f.startswith("top10_daily_2026") and f.endswith(".json"))
    for fn in files:
        date_str = fn[len("top10_daily_"):-5]          # 20260828
        iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        data = load_json(os.path.join(HIST_DIR, fn), {})
        for it in data.get("top10", []):
            code = (it.get("code") or "").strip()
            if not code or len(code) != 6 or not code.isdigit():
                continue                                # 跳过港股(5位)与异常
            tgt = out_sample if (split_date and iso >= split_date) else in_sample
            tgt.append((iso, it))
    return in_sample, out_sample


def build_records(signals, cost=COST_ROUNDTRIP):
    """信号 → 可回测记录（含各维度取值与未来收益）"""
    recs, skipped = [], 0
    for iso, it in signals:
        rets = future_returns(it["code"], iso, cost=cost)
        if not rets:
            skipped += 1
            continue
        feat = {f: float(it.get(f) or 0) for f in FACTORS}
        feat["_returns"] = rets
        feat["_code"] = it["code"]
        feat["_name"] = it.get("name", "")
        feat["_date"] = iso
        recs.append(feat)
    return recs, skipped


def analyze(recs, tag=""):
    if not recs:
        return None
    out = {"tag": tag, "n_signals": len(recs)}

    # 1) 整体表现
    out["overall"] = summarize([r["_returns"] for r in recs], "全样本")["periods"]

    # 2) 因子 IC
    ic_rows = []
    for f in FACTORS:
        row = {"factor": f, "n": len(recs)}
        nonzero = sum(1 for r in recs if r[f] != 0)
        row["nonzero_pct"] = round(nonzero / len(recs) * 100, 1)
        ics = []
        for n in HOLDS:
            xs = [r[f] for r in recs if n in r["_returns"]]
            ys = [r["_returns"][n] for r in recs if n in r["_returns"]]
            ic = spearman(xs, ys)
            row[f"ic_T{n}"] = round(ic, 4) if ic is not None else None
            if ic is not None:
                ics.append(abs(ic))
        row["ic_abs_mean"] = round(_mean(ics), 4) if ics else 0.0
        ic_rows.append(row)
    ic_rows.sort(key=lambda r: -r["ic_abs_mean"])
    out["factor_ic"] = ic_rows

    # 3) total_score 分层（按分位数，而非绝对阈值 —— 阈值会随口径漂移）
    sorted_by_score = sorted(recs, key=lambda r: -r["total_score"])
    n = len(sorted_by_score)
    tiers = {}
    for label, frac in (("TOP20%", 0.2), ("TOP40%", 0.4), ("BOTTOM40%", 1.0)):
        if label == "BOTTOM40%":
            seg = sorted_by_score[int(n * 0.6):]
        else:
            seg = sorted_by_score[:max(1, int(n * frac))]
        tiers[label] = summarize([r["_returns"] for r in seg], label)["periods"]
    out["score_tiers"] = tiers

    # 4) 单信号维度分层（以最具预测力的持有期为准）
    out["signal_tiers"] = {}
    for f in ("sig_count", "score_form", "score_quality"):
        vals = sorted({r[f] for r in recs})
        if len(vals) < 2:
            continue
        mid = vals[len(vals) // 2]
        hi = [r for r in recs if r[f] >= mid]
        lo = [r for r in recs if r[f] < mid]
        out["signal_tiers"][f] = {
            "split_at": mid,
            "high": summarize([r["_returns"] for r in hi], f">{mid}")["periods"],
            "low": summarize([r["_returns"] for r in lo], f"<{mid}")["periods"],
        }
    return out


def _print_summary(res, title):
    if not res:
        _log(f"\n{title}: 无样本")
        return
    _log(f"\n{'='*72}")
    _log(f"  {title}   样本信号数 = {res['n_signals']}")
    _log("=" * 72)
    ov = res["overall"]
    _log(f"  {'持有期':<8}{'样本':>6}{'胜率':>9}{'平均收益':>11}{'中位':>9}")
    for k in ("T1", "T3", "T5", "T10", "T20"):
        if k not in ov:
            continue
        d = ov[k]
        _log(f"  {k:<8}{d['n']:>6}{d['win_rate']:>8.1f}%{d['avg_return']:>10.3f}%{d['median']:>8.3f}%")

    _log(f"\n  ── 因子 IC（Spearman 秩相关，|IC|>0.05 才谈得上有预测力）──")
    _log(f"  {'因子':<18}{'非零%':>7}{'T1':>8}{'T3':>8}{'T5':>8}{'T10':>8}{'T20':>8}{'|IC|均':>8}")
    for r in res["factor_ic"]:
        cells = "".join(
            f"{(r[f'ic_T{n}'] if r[f'ic_T{n}'] is not None else 0):>8.3f}" for n in HOLDS)
        _log(f"  {r['factor']:<18}{r['nonzero_pct']:>6.1f}%{cells}{r['ic_abs_mean']:>8.3f}")

    _log(f"\n  ── 按总分分层的表现 ──")
    for label, per in res["score_tiers"].items():
        best = max(per.items(), key=lambda kv: kv[1]["avg_return"])
        t5 = per.get("T5", {})
        _log(f"  {label:<10} T5胜率 {t5.get('win_rate', 0):>5.1f}%  平均 {t5.get('avg_return', 0):>7.3f}%"
             f"   最优持有期 {best[0]} 平均 {best[1]['avg_return']:>7.3f}%")


def main():
    split_date = None
    if "--split-date" in sys.argv:
        split_date = sys.argv[sys.argv.index("--split-date") + 1]

    _log("=" * 72)
    _log(f"  因子有效性检验 / 可信回测   —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"  入场价 = 信号日次一交易日【开盘价】   交易成本 = 往返 {COST_ROUNDTRIP*100:.2f}%")
    _log("=" * 72)

    ins, oos = collect_signals(split_date)
    _log(f"\n  历史信号: 样本内 {len(ins)} 条" + (f" / 样本外 {len(oos)} 条（≥{split_date}）" if split_date else ""))

    recs, skipped = build_records(ins)
    _log(f"  可回测: {len(recs)} 条（K线缺失跳过 {skipped} 条）")

    if not recs:
        _log("  ❌ 无可回测样本，终止")
        return

    res_in = analyze(recs, "全样本/样本内")
    _print_summary(res_in, "样本内" if split_date else "全样本")

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "entry": "next_day_open",
            "cost_roundtrip": COST_ROUNDTRIP,
            "holds": HOLDS,
            "split_date": split_date,
        },
        "n_signals_total": len(ins) + len(oos),
        "n_signals_tested": len(recs),
        "n_skipped_no_kline": skipped,
        "in_sample": res_in,
    }

    if split_date and oos:
        recs_o, skip_o = build_records(oos)
        _log(f"\n  样本外可回测: {len(recs_o)} 条（跳过 {skip_o} 条）")
        if recs_o:
            res_o = analyze(recs_o, "样本外")
            _print_summary(res_o, f"样本外（≥{split_date}）")
            result["out_of_sample"] = res_o

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log(f"\n  ✅ 报告已写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
