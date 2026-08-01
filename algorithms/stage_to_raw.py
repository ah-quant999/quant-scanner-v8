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
from pathlib import Path

V8_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALGO = os.path.dirname(os.path.abspath(__file__))
# out 目录与 run_algorithms / 被迁移脚本口径一致 = 仓库根/out
OUT = os.path.join(V8_ROOT, "out")
RAW = os.path.join(V8_ROOT, "raw_data")

sys.path.insert(0, V8_ROOT)
import sync_v6_to_v8 as s  # 复用 V6_TO_V8 / _load_json / _add_timestamp / _save_json


def main():
    os.makedirs(RAW, exist_ok=True)
    promoted = 0
    for v6_name, v8_name in s.V6_TO_V8.items():
        src = os.path.join(OUT, v6_name)
        if not os.path.exists(src):
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
