#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ⚠️ DEPRECATED 兼容层（2026-09-22 小九 · 算法链审计根治）
# ─────────────────────────────────────────────────────────────────────────────
# 本文件已不再是调度真身。真身 = algorithms/run_algorithms.py（CI 与本地统一调用）。
#
# 历史陷阱（本次审计根治）：2026-09-18 曾把
#   「backtest_expectancy 前置，让 final_recommend 吃到当日 edge」
# 的修复只改到本根文件，但 CI 实际跑的是 algorithms/run_algorithms.py
# ⇒ 修复永不生效，生产 final_recommend 长期读 T-1 edge（架构级时序倒挂）。
#
# 现改为纯委托，杜绝「双副本漂移 / 假身陷阱」：本文件不再保有任何算法逻辑。
# 真身若需改动，只改 algorithms/run_algorithms.py 一处（其内已有同文件硬断言兜底）。
import os
import runpy
import sys

_LIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algorithms", "run_algorithms.py")
if not os.path.exists(_LIVE):
    sys.stderr.write("FATAL: 算法链真身 algorithms/run_algorithms.py 缺失\n")
    sys.exit(2)
sys.argv[0] = _LIVE
runpy.run_path(_LIVE, run_name="__main__")
