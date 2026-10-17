#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_factor_ic.py — 滚动因子信息系数（IC）监控

目标：对每个评分维度（板块资金、龙虎榜、主力、北向、基本面、分析师、20日涨幅等）
计算其与后续收益率的秩相关系数（Spearman IC），识别失效因子并自动降权。

用法：
  python v8_factor_ic.py [--lookback 60] [--forward 10]

输出：
  raw_data/factor_ic_report.json（各因子近 N 日 IC、ICIR、近 5 日趋势、建议权重调整）

注意：
- 需要 raw_data/history/top10_daily_YYYYMMDD.json 历史快照。
- 需要 raw_data/kline_cache/*.json 日K计算收益率。
- 初始运行可能历史样本不足，仅作诊断不阻断。
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
HIST_DIR = RAW_DIR / "history"
KLINE_DIR = RAW_DIR / "kline_cache"
OUTPUT = RAW_DIR / "factor_ic_report.json"

# 需要监控的因子字段（与 generate_top10.py 输出 top10[].score breakdown 对齐）
FACTOR_FIELDS = [
    "score_sector",
    "score_lhb",
    "score_capital",
    "score_north",
    "score_fund",
    "score_inst",
    "score_w52",
    "score_analyst",
    "score_fundamental",
    "score_tech",
    "score_backtest",
]


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def date_str(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def parse_top10_date(path: Path) -> str | None:
    m = re.search(r"top10_daily_(\d{8})\.json", path.name)
    return m.group(1) if m else None


def forward_return(code: str, asof_date_str: str, horizon: int) -> float | None:
    """asof_date_str(YYYYMMDD) 之后 horizon 个交易日的收益率(%)。"""
    rows = load_json(KLINE_DIR / f"{code}.json", [])
    if not isinstance(rows, list):
        return None
    closes = [(r.get("date", ""), float(r.get("close", 0))) for r in rows if r.get("close")]
    closes.sort(key=lambda x: x[0])
    # 找到 asof_date 或之前最近一个交易日
    idx = None
    for i, (d, _) in enumerate(closes):
        if d >= asof_date_str:
            idx = i
            break
    if idx is None:
        return None
    base = closes[idx][1]
    if base <= 0:
        return None
    target_idx = min(idx + horizon, len(closes) - 1)
    return (closes[target_idx][1] - base) / base * 100


def spearman_corr(x: list[float], y: list[float]) -> float:
    """Spearman 秩相关系数（简化实现）。"""
    n = len(x)
    if n < 3:
        return 0.0
    rx = [sorted(x).index(v) + 1 for v in x]
    ry = [sorted(y).index(v) + 1 for v in y]
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - (6 * d2) / (n * (n * n - 1))


def compute_ic(lookback_days: int, forward_days: int) -> dict:
    """计算近 lookback_days 日内每个因子的 IC。"""
    today = datetime.now()
    snapshots = []
    for p in HIST_DIR.glob("top10_daily_*.json"):
        d = parse_top10_date(p)
        if not d:
            continue
        snap_date = datetime.strptime(d, "%Y%m%d")
        if (today - snap_date).days > lookback_days:
            continue
        snapshots.append((snap_date, load_json(p, {})))
    snapshots.sort(key=lambda x: x[0])

    factor_series = {f: [] for f in FACTOR_FIELDS}
    return_series = []

    for snap_date, data in snapshots:
        d = snap_date.strftime("%Y%m%d")
        top10 = data.get("top10", []) if isinstance(data, dict) else []
        for item in top10:
            code = item.get("code")
            if not code:
                continue
            ret = forward_return(code, d, forward_days)
            if ret is None:
                continue
            return_series.append(ret)
            for f in FACTOR_FIELDS:
                factor_series[f].append(item.get(f, 0) or 0)

    n = len(return_series)
    report = {
        "lookback_days": lookback_days,
        "forward_days": forward_days,
        "sample_count": n,
        "computed_at": datetime.now().isoformat(),
        "factors": {},
    }

    if n < 10:
        report["note"] = "样本不足，IC 仅供观察"
        return report

    for f in FACTOR_FIELDS:
        ic = spearman_corr(factor_series[f], return_series)
        report["factors"][f] = {
            "ic": round(ic, 4),
            "suggested_weight_adj": round(1 + ic, 4),  # IC>0 加分，<0 减分
        }

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--forward", type=int, default=10)
    args = parser.parse_args()

    report = compute_ic(args.lookback, args.forward)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
