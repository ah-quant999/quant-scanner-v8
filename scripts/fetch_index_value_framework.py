#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_index_value_framework.py — A股指数「估值中枢 + 价格档位 + 趋势门控」实验卡

把 QQQ/TQQQ 那套"估值中枢 + 价格档位 + 趋势门控"框架迁移到 A 股指数。
主数据源：data/INDEX_HISTORY.js（上证指数 5 年日K，v8 已有）。
中证系列因当前环境 akshare/东财接口不可用，仅作占位待后续补全。

计算：120日布林带位置、250日/120日/60日/20日 EMA 趋势、综合门控信号。
输出：raw_data/index_value_framework.json

2026-09-09 主人令：放暂未上架·实验区，暂不接入主站。
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"
OUT_PATH = RAW_DIR / "index_value_framework.json"


def ema(series, span):
    if len(series) < span:
        return None
    arr = np.array(series, dtype=float)
    alpha = 2.0 / (span + 1)
    out = np.zeros_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def bollinger_position(prices, window=120):
    if len(prices) < window:
        return None
    arr = np.array(prices[-window:], dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return 0
    latest = prices[-1]
    return max(-1, min(1, (latest - mean) / (2 * std)))


def analyze_prices(dates, prices):
    if len(prices) < 250:
        return None
    e20 = ema(prices, 20)
    e60 = ema(prices, 60)
    e120 = ema(prices, 120)
    e250 = ema(prices, 250)
    latest = prices[-1]
    pos = bollinger_position(prices, 120)

    trend_short = "上升" if e20[-1] > e60[-1] else "下降"
    trend_long = "上升" if e60[-1] > e250[-1] else "下降"

    long_ok = latest > e120[-1]
    mid_ok = e20[-1] > e60[-1]
    if long_ok and mid_ok:
        gate, gate_color = "多头开放", "红"
    elif not long_ok and not mid_ok:
        gate, gate_color = "空头/观望", "绿"
    else:
        gate, gate_color = "混沌/震荡", "黄"

    if pos is None:
        bucket = "未知"
    elif pos <= -0.8:
        bucket = "极度低估"
    elif pos <= -0.4:
        bucket = "低估"
    elif pos <= 0.4:
        bucket = "合理"
    elif pos <= 0.8:
        bucket = "高估"
    else:
        bucket = "极度高估"

    return {
        "latest_date": dates[-1],
        "latest_close": round(latest, 2),
        "ema20": round(e20[-1], 2),
        "ema60": round(e60[-1], 2),
        "ema120": round(e120[-1], 2),
        "ema250": round(e250[-1], 2),
        "boll_position": round(pos, 3) if pos is not None else None,
        "bucket": bucket,
        "trend_short": trend_short,
        "trend_long": trend_long,
        "gate": gate,
        "gate_color": gate_color,
    }


def load_index_history_js():
    """读取 data/INDEX_HISTORY.js 中的上证指数历史。"""
    js_path = DATA_DIR / "INDEX_HISTORY.js"
    if not js_path.exists():
        return None
    text = js_path.read_text(encoding="utf-8")
    # 提取 JSON 部分
    m = re.search(r"window\.INDEX_HISTORY\s*=\s*\{", text)
    if not m:
        return None
    try:
        json_text = text[m.end() - 1:].rstrip()
        # 去掉末尾可能的分号 / CRLF
        json_text = json_text.rstrip(";\r\n")
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    klines = data.get("klines", [])
    if not klines:
        return None
    dates = [k["d"] for k in klines]
    prices = [k["c"] for k in klines]
    return {"name": data.get("meta", {}).get("name", "上证指数"),
            "code": "000001",
            "dates": dates, "prices": prices}


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    errors = []

    # 主指数：上证指数（来自已有 INDEX_HISTORY.js）
    sh = load_index_history_js()
    if sh:
        stats = analyze_prices(sh["dates"], sh["prices"])
        if stats:
            results.append({"name": sh["name"], "code": sh["code"], **stats})
        else:
            errors.append("上证指数: insufficient history")
    else:
        errors.append("上证指数: INDEX_HISTORY.js not available")

    # 中证系列：当前环境接口不可用，仅占位
    for cfg in [
        {"name": "沪深300", "code": "000300"},
        {"name": "中证500", "code": "000905"},
        {"name": "中证1000", "code": "000852"},
    ]:
        results.append({
            "name": cfg["name"],
            "code": cfg["code"],
            "available": False,
            "reason": "akshare/东财接口当前环境不可用，待后续补数据",
        })

    payload = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "data/INDEX_HISTORY.js + 框架迁移",
        "note": "价格中枢框架迁移（QQQ/TQQQ → A股指数），基于收盘价布林带/EMA趋势，非PE估值分位；中证序列待补",
        "indices": results,
    }
    if errors:
        payload["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {OUT_PATH} ({len(results)} indices)", file=sys.stderr)


if __name__ == "__main__":
    main()
