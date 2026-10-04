#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_sw_index_cache.py — 申万一级行业指数日线缓存增量更新器

🛡 2026-10-04 主人令：raw_data/sw_index_daily_cache/（31 个申万一级行业 1999-2026 日线）
   为永久防删的回测验证基础设施（见 DO_NOT_DELETE.md 保护段）。本脚本负责其增量刷新：
   - 数据源：akshare.index_hist_sw（新浪/腾讯源，cn 出口直连，实测 0.9s/行业）
   - 策略：每行业全量重拉 → 与存量 CSV 按日期增量合并（新数据追加，旧数据不动）
   - 幂等：无新交易日时不改文件（mtime 不变，防误触发缓存戳变化）

用法：python scripts/update_sw_index_cache.py
（独立脚本，不在算法链挂载；回测/研究按需手动运行）
"""

import os
import sys
import csv
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "raw_data", "sw_index_daily_cache")

FIELDS = ["代码", "日期", "收盘", "开盘", "最高", "最低", "成交量", "成交额"]


def load_existing(path):
    """读存量 CSV → (rows, 已有日期集合)。文件损坏时返回空（全量重建）。"""
    rows, dates = [], set()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("日期"):
                        rows.append(r)
                        dates.add(r["日期"])
        except Exception as e:
            print(f"  ⚠️ 存量读取失败({e})，将全量重建")
    return rows, dates


def update_one(code):
    import akshare as ak
    path = os.path.join(CACHE, f"{code}.csv")
    old_rows, old_dates = load_existing(path)
    try:
        df = ak.index_hist_sw(symbol=code, period="day")
    except Exception as e:
        print(f"  ❌ {code} 拉取失败: {type(e).__name__} {str(e)[:120]}")
        return None
    if df is None or df.empty:
        print(f"  ⚠️ {code} 返回空，跳过")
        return None
    new_rows = []
    for _, r in df.iterrows():
        d = str(r["日期"])[:10]
        if d not in old_dates:
            new_rows.append({
                "代码": code, "日期": d,
                "收盘": r.get("收盘"), "开盘": r.get("开盘"),
                "最高": r.get("最高"), "最低": r.get("最低"),
                "成交量": r.get("成交量"), "成交额": r.get("成交额"),
            })
    all_rows = old_rows + new_rows
    all_rows.sort(key=lambda x: x["日期"])
    if not new_rows:
        print(f"  ✅ {code}: 无新增（末根 {old_rows[-1]['日期'] if old_rows else '-'}），文件不动")
        return 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"  ✅ {code}: +{len(new_rows)} 行 → 共 {len(all_rows)} 行（末根 {all_rows[-1]['日期']}）")
    return len(new_rows)


def main():
    os.makedirs(CACHE, exist_ok=True)
    import akshare as ak
    # 行业清单：优先取申万官方一级目录；失败则回退存量 CSV 文件名
    codes = []
    try:
        info = ak.sw_index_first_info()
        codes = [str(c).split(".")[0] for c in info["行业代码"].tolist()]
    except Exception as e:
        print(f"⚠️ sw_index_first_info 失败({e})，回退存量 CSV 清单")
    if not codes:
        codes = sorted(f[:-4] for f in os.listdir(CACHE) if f.endswith(".csv"))
    print(f"== 申万一级行业缓存更新：{len(codes)} 个行业 @ {datetime.now():%Y-%m-%d %H:%M} ==")
    total = 0
    for c in codes:
        n = update_one(c)
        if n:
            total += n
    print(f"== 完成：新增 {total} 行 ==")


if __name__ == "__main__":
    sys.exit(main())
