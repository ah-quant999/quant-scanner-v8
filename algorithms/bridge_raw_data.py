#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bridge_raw_data.py — raw_data → raw_data 内部桥接器

🛡 2026-08-18 主人紧急令根治「云端不能 100% 自治」核心洞：
  algorithms/stage_to_raw.py 只搬运 algorithms/out/ → raw_data/（v6 → v8 命名）。
  但部分 v8 自研算法（gen_triple_consensus.py / update_triple_resonance_history.py /
  gen_triple_track.py 等）已经直接写 raw_data/，导致「同源不同名」场景下：
    · 生成器写 raw_data/triple_resonance_history.json
    · update_v8 读 raw_data/triple_history.json
    · stage_to_raw.py 找 out/triple_resonance_history.json（永远找不到，gitignore 屏蔽）
    · raw_data/triple_history.json 永远停在旧版本
    · 前端 data/TRIPLE_HISTORY.js 陈旧 4 天
  这种结构性断点靠 self_heal 派发 algo_run 永远治不好——algo_run 跑完一遍又到同一断点。

本脚本：raw_data → raw_data 内部桥接（独立于 stage_to_raw 的 out → raw 角色）。
  把生成器直写的源文件复制成 update_v8 期望的目标文件名，注入 update_time。

接入方式：
  1) v8_algo_cloud.yml 在 run_algorithms.py 之后、update_v8.py 之前调用
  2) v8_cn_fetch_cloud.yml 在 api_push_raw.py 之后、update_v8.py 之前调用
  3) v8_algo_run.yml 同位置（cn runner 应急回退）
  4) 本机 WorkBuddy automation 也可手动调用

幂等性：源 mtime ≤ 目标 mtime 时跳过，避免空跑覆盖；目标不存在但源存在时无条件桥接。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"

CST = timezone(timedelta(hours=8))


def _now_cst_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


# raw_data → raw_data 桥接表（生成器源名 → update_v8 期望目标名）
# 任何「生成器直写 raw_data/<src>，但 update_v8 读 raw_data/<dst>」的改名场景必须登记在此
BRIDGE_MAP = {
    # 🛡 2026-08-18 主人紧急令根治：4 天前 TRIPLE_HISTORY 不更新的根因
    "triple_resonance_history.json": "triple_history.json",
    # 未来扩展点：所有 raw_data 改名场景都登记在这里
}


def _load(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ❌ 读取失败 {p}: {e}")
        return None


def _save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ✅ 写入 {p.name} ({p.stat().st_size} bytes)")


def _add_ts(obj):
    if isinstance(obj, list):
        return {"data": obj, "update_time": _now_cst_str()}
    if not isinstance(obj, dict):
        return obj
    if "update_time" not in obj and "calc_time" not in obj and "date" not in obj:
        obj["update_time"] = _now_cst_str()
    return obj


def main():
    if not RAW.exists():
        print(f"❌ raw_data 目录不存在: {RAW}")
        return 1

    bridged = 0
    skipped = 0
    for src_name, dst_name in BRIDGE_MAP.items():
        src = RAW / src_name
        dst = RAW / dst_name
        if not src.exists():
            print(f"  [skip] 源缺失: {src_name}")
            skipped += 1
            continue
        # 守护：源 mtime ≤ 目标 mtime 时跳过（避免空跑覆盖更新版本）
        if dst.exists() and src.stat().st_mtime <= dst.stat().st_mtime:
            print(f"  [skip] 源较旧（src mtime ≤ dst mtime）: {src_name} → {dst_name}")
            skipped += 1
            continue
        obj = _load(src)
        if obj is None:
            skipped += 1
            continue
        obj = _add_ts(obj)
        _save(dst, obj)
        bridged += 1
        print(f"  🔗 桥接: raw_data/{src_name} → raw_data/{dst_name} ({_now_cst_str()})")

    print(f"\nbridge_raw_data: 桥接 {bridged} 个，跳过 {skipped} 个（{_now_cst_str()}）")
    return 0 if bridged > 0 else 1 if skipped == 0 else 0


if __name__ == "__main__":
    sys.exit(main())