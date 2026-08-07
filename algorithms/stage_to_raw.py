#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stage_to_raw.py — 把 algorithms/out/ 下的 v6 命名文件，按 V6_TO_V8 重命名为
v8 raw_data/ 命名，并注入 update_time（复用 sync_v6_to_v8 的成熟逻辑）。

只提升 V6_TO_V8 中登记的产物；out/ 里的“输入类”文件（scan_result /
guanlan_* / mahoro_signals / fundamental_quality / lhb_history 等）保持不动，
作为下一轮运行的输入，由 run_algorithms.py 每轮从 v6 重新灌入。
"""
import os
import sys
import json
import datetime
from pathlib import Path

# 2026-08-07 修复：以下产物由生成器【直写 raw_data/】（gen_triple_consensus /
# gen_triple_track 于 08-06 改造），out/ 下同名文件是历史僵尸副本。
# 若继续搬运，会用 08-06 旧数据覆盖当日新结果 -> 前端长期显示 3 天前数据。
SKIP_STAGE = {
    "triple_consensus.json",
    "triple_track.json",
}

V8_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALGO = os.path.dirname(os.path.abspath(__file__))
# out 目录与 run_algorithms / 被迁移脚本口径一致 = 仓库根/out
OUT = os.path.join(V8_ROOT, "out")
RAW = os.path.join(V8_ROOT, "raw_data")

sys.path.insert(0, V8_ROOT)
import sync_v6_to_v8 as s  # 复用 V6_TO_V8 / _load_json / _add_timestamp / _save_json


_TS_KEYS = ("update_time", "gen_time", "calc_time", "run_time",
            "fetch_time", "snapshot_time")


def _ts_date(path):
    """取文件内容里的时间戳日期(YYYY-MM-DD)；无时间戳字段则回退到 mtime 日期。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            for k in _TS_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and len(v) >= 10:
                    return v[:10]
    except Exception:
        pass
    try:
        return datetime.datetime.fromtimestamp(
            os.path.getmtime(path)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def main():
    os.makedirs(RAW, exist_ok=True)
    promoted = 0
    for v6_name, v8_name in s.V6_TO_V8.items():
        src = os.path.join(OUT, v6_name)
        if not os.path.exists(src):
            continue
        # (1) 生成器直写 raw_data 的产物，禁止再从 out/ 搬运覆盖
        if v6_name in SKIP_STAGE or v8_name in SKIP_STAGE:
            print(f"  [skip] 生成器直写 raw_data: {v6_name}")
            continue
        # (2) 防僵尸覆盖：out 源比 raw 目标旧则拒绝搬运
        dst_path = os.path.join(RAW, v8_name)
        if os.path.exists(dst_path):
            s_date, d_date = _ts_date(src), _ts_date(dst_path)
            if s_date and d_date and s_date < d_date:
                print(f"  [guard] out更旧({s_date}) < raw({d_date}): {v6_name}")
                continue
        obj = s._load_json(src)
        if obj is None:
            print(f"  ⚠️ 跳过（解析失败）: {v6_name}")
            continue
        obj = s._add_timestamp(obj)
        # sync_v6_to_v8._save_json 期望 pathlib.Path（内部调用 path.parent.mkdir）
        s._save_json(Path(RAW) / v8_name, obj)
        promoted += 1
        print(f"  ✅ {v6_name} -> raw_data/{v8_name}")
    print(f"\nstaged: {promoted} 个文件")
    return promoted


if __name__ == "__main__":
    main()
