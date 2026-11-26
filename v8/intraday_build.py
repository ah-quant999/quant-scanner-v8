# -*- coding: utf-8 -*-
"""盘中轻量构建：直接调 update_v8.build()，绕开 main() 的工作区一致性守卫。

为什么绕开：update_v8.main() 开头先跑 v8_ws_sync_guard.py --heal（内含 git fetch）。
本机 DNS 间歇性解析失败时 git fetch 会挂住——2026-11-26 16:36 实测 update_v8 卡死
5 分钟以上零输出，整个盘中节拍被拖死。盘中 tick 只需要「raw_data → data/*.js」这一步，
缓存戳 / 健康校验 / 实验卡由云端盘后链负责，本脚本不碰。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ["V8_SKIP_EXPERIMENT_CARDS"] = "1"   # 盘中不需要实验卡（回测类，盘后跑）

import update_v8  # noqa: E402

rc = update_v8.build(category="intraday")
print(f"[intraday-build] rc={rc}", flush=True)
sys.exit(0 if rc in (0, None) else int(rc))
