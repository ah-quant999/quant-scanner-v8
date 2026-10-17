#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
renormalize_top10_history.py — 历史 TOP10 快照口径统一（2026-08-28）

背景（审计确认的致命问题）：
  7/17–7/30 的 total_score 是 raw 分直存（比值 1.00），8/01 起改成 raw/250×100
  （比值 0.40）。同一 raw 分（99 vs 101）显示分却差 2.45 倍 —— 回测验证出来的
  「≥80 分规律」对实盘完全不适用。

  本次把分母从 250 校准为 NORM_DIVISOR=130（依据实测 756 个信号分布：
  P50=69 / P90=88 / P95=93 / MAX=106，用 250 时 ≥80 分数学上不可达）。

做法：
  从每条信号的 breakdown 还原 raw_total，再按统一分母重算 total_score，
  并写入 norm_version 标记防止二次归一化。

⚠️ 限制：历史快照里 fund/inst/sector 三维度当时就是 0（数据源当时读不到），
   本脚本【不会】伪造补分，只统一口径。修复后的新数据才会真正带上这三项。

用法：
  python renormalize_top10_history.py            # 试运行，只报告不改
  python renormalize_top10_history.py --apply    # 实际改写
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
HIST_DIR = os.path.join(ROOT, "raw_data", "history")
LATEST = os.path.join(ROOT, "raw_data", "top10_daily.json")

NORM_DIVISOR = 130
NORM_VERSION = 130
OLD_DIVISOR = 250

BREAKDOWN_KEYS = ("base", "enhance", "form", "fund", "sector",
                  "inst", "quality", "backtest")


def _log(m=""):
    print(m, flush=True)


def load_json(p, d=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d if d is not None else {}


def save_json(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def raw_of(item):
    """从 breakdown 还原 raw_total；无 breakdown 时退回各 score_* 字段求和"""
    bd = item.get("breakdown")
    if isinstance(bd, dict) and bd:
        return sum(float(bd.get(k) or 0) for k in BREAKDOWN_KEYS)
    return sum(float(item.get(f"score_{k}") or 0) for k in BREAKDOWN_KEYS)


def process(path, apply=False):
    """返回 (是否变更, 统计)

    统计可能是：
      "skip"          已是本口径
      "unrecoverable" 明细缺失、无法还原 raw —— 坚决不动，避免编造
      dict            正常处理
    """
    data = load_json(path)
    if not isinstance(data, dict) or not data.get("top10"):
        return False, None
    if data.get("norm_version") == NORM_VERSION:
        return False, "skip"

    items = data["top10"]
    # 先探测可还原性：任一条目能还原出 raw 才算可处理
    recoverable = sum(1 for it in items if raw_of(it) > 0)
    if recoverable == 0:
        # 早期格式（实测 2026-06 那批）score_* 明细全缺，无法还原 → 不动
        return False, "unrecoverable"

    max_s, c80, changed_scores = 0.0, 0, 0
    for it in items:
        old = it.get("total_score", 0) or 0
        raw = raw_of(it)
        if raw <= 0:
            continue                      # 明细缺失的单条也跳过，保留原值
        new = round(min(100, max(0, raw / NORM_DIVISOR * 100)), 1)
        if abs(old - new) > 0.05:
            changed_scores += 1
        it["total_score"] = new
        max_s = max(max_s, new)
        if new >= 80:
            c80 += 1
    data["max_score"] = max_s
    data["count_80plus"] = c80
    data["norm_version"] = NORM_VERSION
    data["norm_divisor"] = NORM_DIVISOR
    if apply:
        save_json(path, data)
    return True, {"n": len(items), "recovered": recoverable,
                  "changed": changed_scores, "max": max_s, "c80": c80}


def main():
    apply = "--apply" in sys.argv
    _log("=" * 74)
    _log(f"  历史 TOP10 评分口径统一   —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"  分母 {OLD_DIVISOR} → {NORM_DIVISOR}    模式: {'实际改写' if apply else '【试运行·不改文件】'}")
    _log("=" * 74)

    if not os.path.isdir(HIST_DIR):
        _log(f"  ❌ 目录不存在: {HIST_DIR}")
        return

    files = sorted(f for f in os.listdir(HIST_DIR)
                   if f.startswith("top10_daily_") and f.endswith(".json"))
    _log(f"\n  待处理历史快照: {len(files)} 个\n")
    _log(f"  {'文件':<34}{'条目':>6}{'可还原':>7}{'改分':>6}{'新最高':>9}{'≥80':>6}")

    done = skipped = 0
    unrecoverable = []
    all_new = []
    for fn in files:
        ch, stat = process(os.path.join(HIST_DIR, fn), apply)
        if stat == "skip":
            skipped += 1
            continue
        if stat == "unrecoverable":
            unrecoverable.append(fn)
            continue
        if not ch:
            continue
        done += 1
        _log(f"  {fn:<34}{stat['n']:>6}{stat['recovered']:>7}{stat['changed']:>6}"
             f"{stat['max']:>8.1f}{stat['c80']:>6}")
        all_new.append(stat["max"])

    # 当日主文件
    if os.path.exists(LATEST):
        ch, stat = process(LATEST, apply)
        if isinstance(stat, dict) and ch:
            _log(f"  {'top10_daily.json (当日)':<34}{stat['n']:>6}{stat['recovered']:>7}"
                 f"{stat['changed']:>6}{stat['max']:>8.1f}{stat['c80']:>6}")

    if unrecoverable:
        _log(f"\n  ⚠️ 以下 {len(unrecoverable)} 个文件明细缺失、无法还原 raw，"
             f"【未做任何改动】（不编造数据）：")
        for fn in unrecoverable:
            _log(f"     · {fn}")

    _log(f"\n  处理 {done} 个文件，跳过(已本口径) {skipped} 个，"
         f"无法还原 {len(unrecoverable)} 个")
    if all_new:
        all_new.sort()
        n = len(all_new)
        _log(f"  口径统一后各日最高分: 中位 {all_new[n//2]:.1f}  "
             f"最低 {all_new[0]:.1f}  最高 {all_new[-1]:.1f}")
    if not apply:
        _log("\n  ⚠️ 这是试运行。确认无误后加 --apply 实际改写。")
    else:
        _log("\n  ✅ 已改写。历史与当日口径一致，回测阈值重新可用。")


if __name__ == "__main__":
    main()
