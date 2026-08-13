#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_closing_data_refresh.py - one-shot replacement for automation-1785388522458 prompt
15:30 v8 收盘数据刷新 + 算法链重跑

设计变更（2026-08-13 主人令「全面一劳永逸式修复」后 15:35 根因诊断）：
- 原 prompt 让 AI 用 v8_dispatch_fetch.py post_close 派发**云端 cn_fetch** workflow
  → 云端 runs-on: [self-hosted, cn] → 本机未装 cn runner → fallback github runner（美国 IP）
  → A 股东财/新浪源 60s+ 超时 → fail → 算法链拿到空数据 → 盘后批次停更
- 现改为：**本机中国 IP 直抓为主** + **派发作最末兜底**
  · step 3 直接在本地跑 cloud_fetch_v8.py --category post_close（少数固有时段可补的）
  · step 4 调 algorithms/run_algorithms.py 跑 算法链 + stage_to_raw + 生成 23 个 data/*.js
  · step 5 update_v8.py 把 raw_data/ → data/*.js
  · step 6 commit + push
  · step 7 派发云端 workflow_dispatch 作"再补一次"兜底（哪怕 fallback 跑挂也不影响主路径已落地的产物）

这一步一改，盘中盘后批次的"全面一劳永逸式修复"就闭环了。
"""

import os, sys, json, time, subprocess
from datetime import datetime, timezone, timedelta

ROOT = "E:/workspace/quant-scanner-v8"
PY = "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

def log(s):
    print(f"[{datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')}] {s}", flush=True)

def run(cmd, timeout=1800, env=None):
    """run shell command with full output captured"""
    log(f"$ {' '.join(cmd)[:80]}...")
    e = os.environ.copy()
    e['V8_PYTHON'] = PY
    e['V8_OUT_DIR'] = f"{ROOT}/out"
    if env: e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=e, cwd=ROOT)
    log(f"  exit={p.returncode}")
    if p.stdout: log(f"  stdout tail: {p.stdout.strip()[-400:]}")
    if p.stderr and p.returncode != 0: log(f"  stderr tail: {p.stderr.strip()[-400:]}")
    return p.returncode

def shell(cmd, timeout=1800):
    return run(cmd, timeout)

if __name__ == "__main__":
    log("=== v8 15:30 收盘数据刷新（新版·本机直抓）开始 ===")

    # 1) 先同步远端
    shell(["git", "fetch", "origin", "main"], timeout=60)

    # 2) 本地直抓 post_close（cloud_fetch_v8.py）—— 主路径
    log("【本机直抓 post_close】")
    rc = run([PY, "cloud_fetch_v8.py", "--category", "post_close"], timeout=900)
    log(f"  cloud_fetch_v8 --category post_close exit={rc}")

    # 3) 算法链（含 scanner.py upstream + all 23 scripts）—— 主路径
    log("【本机直跑算法链】")
    rc = run([PY, "algorithms/run_algorithms.py"], timeout=2700)
    log(f"  run_algorithms exit={rc}")

    # 4) 重建 data/*.js
    log("【update_v8 重建】")
    rc = run([PY, "update_v8.py"], timeout=300)
    log(f"  update_v8 exit={rc}")

    # 5) 推送 main（commit 只 stage 这次新产物，未跟踪/红线文件不动）
    log("【commit + push】")
    shell(["git", "add", "-f", "data/*.js", "raw_data/*.json"], timeout=60)
    # fallback：accept-blue index.html 红线已经在 .gitignore 处理 (bloat check 接管)
    rc = run(["git", "-c", "user.name=jiubao", "-c", "user.email=bot@jiubao.local",
              "commit", "-m",
              f"auto: 15:30 收盘+算法链刷新 {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')}"],
             timeout=120)
    log(f"  commit exit={rc}")

    # autostash rebase 应对远端有更新
    rc = run(["git", "pull", "--rebase", "--autostash", "origin", "main"], timeout=120)
    log(f"  rebase exit={rc}")
    rc = run(["git", "push", "origin", "main"], timeout=120)
    log(f"  push exit={rc}")

    # 6) 派发云端（兜底）
    log("【派发云端兜底】")
    rc = run([PY, "v8_dispatch_fetch.py", "post_close"], timeout=60)
    log(f"  dispatch exit={rc}")

    log("=== 收盘数据刷新完成 ===")
