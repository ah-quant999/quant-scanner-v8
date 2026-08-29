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


def collect_h_reverse(expert=False):
    """读 H_AUTO_BUY_TRACK 历史，返回每只 pick 的 T+1~T+10 实测涨幅。"""
    d = load_js_var(DATA_DIR / "H_AUTO_BUY_TRACK.js", "H_AUTO_BUY_TRACK")
    if not d:
        return []
    out = []
    key = "expert_by_date" if expert else "by_date"
    by_date = d.get(key, {}) or {}
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


def _t5_win_avg(s):
    t5 = (s or {}).get("horizons", {}).get("t5")
    if not t5:
        return None, None
    return t5.get("win"), t5.get("avg")


def verdict(ha, ha_expert, sb):
    parts = []
    names = {
        "h_reverse": "H 反推",
        "h_reverse_expert": "高手画像版H反推",
        "strong_breakout": "强势突破",
    }
    metrics = [(names["h_reverse"], ha), (names["h_reverse_expert"], ha_expert), (names["strong_breakout"], sb)]
    # 只参与有 T+5 样本的
    valid = [(n, _t5_win_avg(s)) for n, s in metrics if _t5_win_avg(s)[0] is not None]
    if not valid:
        return "三套算法均暂无足够 T+5 可比历史，等待盘后累积。"
    if len(valid) == 1:
        return f"仅 {valid[0][0]} 有 T+5 样本，待其他算法累积后对比。"
    # 胜率排名 + 平均收益排名
    by_win = sorted(valid, key=lambda x: x[1][0], reverse=True)
    by_avg = sorted(valid, key=lambda x: x[1][1], reverse=True)
    parts.append(f"T+5 胜率：{by_win[0][0]}（{by_win[0][1][0]}%）> {by_win[1][0]}（{by_win[1][1][0]}%）")
    if len(by_win) > 2:
        parts[-1] += f" > {by_win[2][0]}（{by_win[2][1][0]}%）"
    parts.append(f"T+5 平均收益：{by_avg[0][0]}（+{by_avg[0][1][1]}%）> {by_avg[1][0]}（+{by_avg[1][1][1]}%）")
    if len(by_avg) > 2:
        parts[-1] += f" > {by_avg[2][0]}（+{by_avg[2][1][1]}%）"
    return "；".join(parts)


def main():
    ha = summarize(collect_h_reverse())
    ha_expert = summarize(collect_h_reverse(expert=True))
    sb = summarize(collect_strong_breakout())
    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_def": "胜率=收益>0占比; 平均收益=收益均值%; 命中率=收益>=5%占比",
        "algorithms": {
            "h_reverse": {
                "name": "H 反推短线买点",
                "rule": "涨幅≥3% + 量比≥1.2（PDF 提取算法）",
                "source": "H_AUTO_BUY_TRACK.by_date",
                "summary": ha,
            },
            "h_reverse_expert": {
                "name": "高手画像版H反推",
                "rule": "涨幅≥3% + 量比≥1.2 + 价格<15 + 主板 + 医药/化工/贵金属/农业",
                "source": "H_AUTO_BUY_TRACK.expert_by_date",
                "summary": ha_expert,
            },
            "strong_breakout": {
                "name": "强势突破（H反推升级）",
                "rule": "涨幅≥3% + 量比≥1.2 + 突破前高 + RS前25%",
                "source": "STOCK_MOMENTUM_STATE_V2",
                "summary": sb,
            },
        },
        "verdict": verdict(ha, ha_expert, sb),
    }
    out = DATA_DIR / "ALGO_BACKTEST_COMPARE.js"
    out.write_text(
        "window.ALGO_BACKTEST_COMPARE = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    n_ha = ha["n_samples"] if ha else 0
    n_ha_ex = ha_expert["n_samples"] if ha_expert else 0
    n_sb = sb["n_samples"] if sb else 0
    print(f"[algo_backtest_compare] H反推 n={n_ha} | 高手画像版 n={n_ha_ex} | 强势突破 n={n_sb}")
    print(f"[algo_backtest_compare] 结论: {payload['verdict']}")


if __name__ == "__main__":
    main()
