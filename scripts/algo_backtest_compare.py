#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
algo_backtest_compare.py — 两套算法回测横向对比
================================================
把「H 反推短线买点」与「强势突破(H反推升级)」的实盘入选样本，
用【同一口径】聚合，输出可直接比较的胜率 / 收益率：

  - 胜率     = 该周期收益 > 0 的样本占比(%)
  - 平均收益 = 样本该周期收益均值(%)
  - 命中率   = 该周期收益 >= 5% 的样本占比(%)（H反推原始定义，仅供参照）

数据来源（均为既有产物，无新增外部依赖）：
  - H 反推     : data/H_AUTO_BUY_TRACK.js
                 (history.by_date[date].picks[] 内含 T+1~T+10 实测涨幅)
  - 强势突破   : data/STOCK_MOMENTUM_STATE_V2.js
                 (periods.*.all[].t1_gain_pct ~ t10_gain_pct)

输出：data/ALGO_BACKTEST_COMPARE.js  (window.ALGO_BACKTEST_COMPARE)
用法：python scripts/algo_backtest_compare.py
"""
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HIT_PCT = 5.0
HORIZONS = [("t1", "T+1"), ("t3", "T+3"), ("t5", "T+5"), ("t10", "T+10")]


def load_js_var(path, var_name):
    if not path.exists():
        return None
    src = open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s\s*=\s*(\{.*\});\s*$" % var_name, src, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _agg(values):
    """values: list of float/None。返回 {n, win, avg, hit} 或 None。"""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    n = len(vals)
    win = round(100 * sum(1 for v in vals if v > 0) / n, 1)
    avg = round(statistics.mean(vals), 2)
    hit = round(100 * sum(1 for v in vals if v >= HIT_PCT) / n, 1)
    return {"n": n, "win": win, "avg": avg, "hit": hit}


def collect_h_reverse():
    """读 H_AUTO_BUY_TRACK 历史，返回每只 pick 的 T+1~T+10 实测涨幅。"""
    d = load_js_var(DATA_DIR / "H_AUTO_BUY_TRACK.js", "H_AUTO_BUY_TRACK")
    if not d:
        return []
    out = []
    by_date = d.get("by_date", {}) or {}
    for date, rec in by_date.items():
        for p in rec.get("picks", []) or []:
            row = {
                "code": p.get("code"), "date": date,
                "t1": p.get("T+1"), "t3": p.get("T+3"),
                "t5": p.get("T+5"), "t10": p.get("T+10"),
            }
            if any(row[k] is not None for k in ("t1", "t3", "t5", "t10")):
                out.append(row)
    return out


def collect_strong_breakout():
    """读 STOCK_MOMENTUM_STATE_V2，返回每只 all[] 的 t1~t10_gain_pct。"""
    d = load_js_var(DATA_DIR / "STOCK_MOMENTUM_STATE_V2.js", "STOCK_MOMENTUM_ENHANCED")
    if not d:
        return []
    out = []
    periods = d.get("periods", {}) or {}
    for pv in periods.values():
        for r in pv.get("all", []) or []:
            row = {
                "code": r.get("code"), "date": r.get("date"),
                "t1": r.get("t1_gain_pct"), "t3": r.get("t3_gain_pct"),
                "t5": r.get("t5_gain_pct"), "t10": r.get("t10_gain_pct"),
            }
            if any(row[k] is not None for k in ("t1", "t3", "t5", "t10")):
                out.append(row)
    return out


def summarize(rows):
    if not rows:
        return None
    metrics = {}
    for key, _ in HORIZONS:
        col = [r.get(key) for r in rows]
        a = _agg(col)
        if a:
            metrics[key] = a
    return {"n_samples": len(rows), "horizons": metrics}


def verdict(ha, sb):
    if not ha and not sb:
        return "两套算法暂无可比历史，等待盘后累积（每日自动累加）。"
    if not ha:
        return "H 反推暂无历史样本；强势突破已就绪，等待 H 反推累积后对比。"
    if not sb:
        return "强势突破暂无历史样本（首次云运行后开始累积）；H 反推已就绪。"
    ha_t5 = ha["horizons"].get("t5")
    sb_t5 = sb["horizons"].get("t5")
    if not ha_t5 or not sb_t5:
        return "T+5 样本不足，待累积后给出结论。"
    lines = []
    if sb_t5["win"] > ha_t5["win"]:
        lines.append(f"强势突破 T+5 胜率更高（{sb_t5['win']}% vs {ha_t5['win']}%）")
    else:
        lines.append(f"H 反推 T+5 胜率更高（{ha_t5['win']}% vs {sb_t5['win']}%）")
    if sb_t5["avg"] > ha_t5["avg"]:
        lines.append(f"强势突破 T+5 平均收益更好（+{sb_t5['avg']}% vs +{ha_t5['avg']}%）")
    else:
        lines.append(f"H 反推 T+5 平均收益更好（+{ha_t5['avg']}% vs +{sb_t5['avg']}%）")
    return "；".join(lines)


def main():
    ha = summarize(collect_h_reverse())
    sb = summarize(collect_strong_breakout())
    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_def": "胜率=收益>0占比; 平均收益=收益均值%; 命中率=收益>=5%占比",
        "algorithms": {
            "h_reverse": {
                "name": "H 反推短线买点",
                "rule": "涨幅≥3% + 量比≥1.2（PDF 提取算法）",
                "source": "H_AUTO_BUY_TRACK",
                "summary": ha,
            },
            "strong_breakout": {
                "name": "强势突破（H反推升级）",
                "rule": "涨幅≥3% + 量比≥1.2 + 突破前高 + RS前25%",
                "source": "STOCK_MOMENTUM_STATE_V2",
                "summary": sb,
            },
        },
        "verdict": verdict(ha, sb),
    }
    out = DATA_DIR / "ALGO_BACKTEST_COMPARE.js"
    out.write_text(
        "window.ALGO_BACKTEST_COMPARE = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    n_ha = ha["n_samples"] if ha else 0
    n_sb = sb["n_samples"] if sb else 0
    print(f"[algo_backtest_compare] H反推 n={n_ha} | 强势突破 n={n_sb}")
    print(f"[algo_backtest_compare] 结论: {payload['verdict']}")


if __name__ == "__main__":
    main()
