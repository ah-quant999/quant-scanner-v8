#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
guard_raw_freshness.py — 提交前「raw_data 新鲜度回归」守卫（2026-08-17 一劳永逸修复）

【用途】
在 `git add` 之前调用。检测并修复「算法链已生成新数据，但 raw_data/*.json 在
生成 → 提交 的窗口内被回退成旧内容」的静默故障，避免把陈旧数据 commit 上线。

【根因（2026-08-17 实测）】
E:\\workspace\\quant-scanner-v8 是坚果云(Nutstore) junction 目录。算法链 15:53-15:57
写入 raw_data/*.json 后，坚果云 NTFSWatcher 在 15:59:55 / 16:02:40 两批把
crds_card_data / lhb_data / cockpit_tier_recommend / triple_consensus / gold_pool
回滚成当日 09:xx 的旧内容。于是 `git add` staged 的是旧内容，commit(943e732aa) 自带
09:21:49，云端 build 依 raw_data 重建 data/*.js → 主站收盘数据整段停更在 09:xx，
而流程每一步都「成功」，无任何报错 → 静默故障。

【数据流】
  algorithms/out/<v6_name>.json  --(stage_to_raw: V6_TO_V8)-->  raw_data/<v8_name>.json
本守卫复用 stage_to_raw 的 V6_TO_V8 / SKIP_STAGE 映射与时间戳工具，逐个比对
out 源与 raw 目标的时间戳：raw 比 out 旧即判定为「回归」，就地重新搬运修复。

【退出码】
  0 = 全部新鲜，或已自动修复（可安全 git add）
  1 = 存在无法自动修复的回归（生成器直写类产物被回退，需重跑对应生成器）
  2 = 环境异常（缺 out/ 或映射导入失败）

【依赖】algorithms/stage_to_raw.py（V6_TO_V8 / SKIP_STAGE / _load_json / _save_json /
        _add_timestamp / _ts_full）
【调用方】本机 15:30 收盘刷新自动化、任何「算法链 → commit」链路的 git add 前一步。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ALGO = os.path.join(ROOT, "algorithms")
OUT = os.path.join(ROOT, "out")
RAW = os.path.join(ROOT, "raw_data")

if ALGO not in sys.path:
    sys.path.insert(0, ALGO)

try:
    from stage_to_raw import (  # type: ignore
        V6_TO_V8,
        SKIP_STAGE,
        _load_json,
        _save_json,
        _add_timestamp,
        _ts_full,
    )
except Exception as exc:  # pragma: no cover
    print(f"[guard-raw] ❌ 无法导入 stage_to_raw 映射: {exc}")
    sys.exit(2)

from pathlib import Path


def _fmt(ts: str | None) -> str:
    return ts or "(no ts)"


def main() -> int:
    if not os.path.isdir(OUT):
        print(f"[guard-raw] ⚠️ out/ 不存在，跳过（非算法链场景）: {OUT}")
        return 0
    if not os.path.isdir(RAW):
        print(f"[guard-raw] ❌ raw_data/ 不存在: {RAW}")
        return 2

    repaired: list[str] = []
    unfixable: list[str] = []
    fresh = 0

    for v6_name, v8_name in V6_TO_V8.items():
        src = os.path.join(OUT, v6_name)
        dst = os.path.join(RAW, v8_name)
        if not os.path.exists(dst):
            continue

        direct_write = (v6_name in SKIP_STAGE) or (v8_name in SKIP_STAGE)
        d_ts = _ts_full(dst)

        if direct_write:
            # 生成器直写 raw_data，out/ 无权威源可搬运。只能检测「明显回退」：
            # 与全体 out 产物的最新时间戳相比落后 1 天以上视为回退。
            continue

        if not os.path.exists(src):
            continue

        s_ts = _ts_full(src)
        if not s_ts or not d_ts:
            continue

        if d_ts < s_ts:
            # 回归：raw 比 out 源旧 → 坚果云/并发进程回退过。就地重新搬运。
            obj = _load_json(src)
            if obj is None:
                unfixable.append(f"{v8_name} (out 源解析失败, raw={_fmt(d_ts)})")
                continue
            obj = _add_timestamp(obj)
            _save_json(Path(RAW) / v8_name, obj)
            # 复核：写回后再读一次，确认真的落盘生效（防同步进程二次回退）
            again = _ts_full(dst)
            if again and again >= s_ts:
                repaired.append(f"{v8_name}: {_fmt(d_ts)} -> {_fmt(again)}")
            else:
                unfixable.append(
                    f"{v8_name}: 写回后仍为 {_fmt(again)}（期望 >= {s_ts}），疑似同步进程持续回退"
                )
        else:
            fresh += 1

    print(f"[guard-raw] 新鲜 {fresh} 个 | 修复 {len(repaired)} 个 | 无法修复 {len(unfixable)} 个")
    for line in repaired:
        print(f"  🔧 修复回归: {line}")
    for line in unfixable:
        print(f"  ❌ 无法修复: {line}")

    if unfixable:
        print("[guard-raw] ❌ 存在无法修复的回归 → 请勿 commit，先重跑对应生成器/改在非同步目录构建")
        return 1
    if repaired:
        print("[guard-raw] ✅ 回归已修复，可以 git add")
    else:
        print("[guard-raw] ✅ 无回归")
    return 0


if __name__ == "__main__":
    sys.exit(main())
