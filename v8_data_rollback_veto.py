#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_data_rollback_veto.py — push 前数据回滚否决（v8_git_push.sh 第②½步，best-effort）
================================================================================
主人令接线：2026-11-20「加！不要一直被覆盖！」+ 2026-11-23「任务运行看板红叉一劳永逸修复」。

事故链（三次实证，同根因）：
  落后/陈旧基线工作区（持久 runner clone、长跑 job、本地脏树）把 data/ raw_data/ 的
  【旧内容】作为【新提交】推上 main，把新鲜版本盖回旧基线——
  2026-11-20 01:51 / 11-21 / 11-23 08:24 stock_names.json + resonance_track.json
  被盖回 11-11 内容，parity 跨层闸门拦截成功（没上线）但每轮构建部署全红叉。
  safe_batch_commit.py 闸②同类逻辑 11-20 已建但零接线；本脚本装进 v8_git_push.sh
  （12 条 workflow + safe_batch_commit 的共用推送咽喉点）→ 整类回滚一次堵死。

行为（对 origin/main..HEAD 中 data/|raw_data/ 差异文件逐一比对权威时间戳，
      口径与 safe_batch_commit.data_ts / v8_verify_layer_parity.DATE_KEYS 同源）：
  · HEAD 版时间戳 < origin/main 版 ⇒ 放弃本地旧版，checkout 远端新版并 fixup 提交
    （绝不带陈旧数据上线）
  · HEAD 更新 / 相等 / 任一侧无时间戳 / 显式删除 ⇒ 不动（不越权）
  · 任何异常只打印告警、exit 0 —— 与 v8_git_push.sh ①②④ 同为 best-effort，不阻断 push 本体。
  · 差异文件 >300 视为全量重建类提交，跳过否决（防大 tree 拖慢/误伤）。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIRS = ("data/", "raw_data/")
MAX_FILES = 300

# 与 safe_batch_commit.data_ts 同口径 + parity.DATE_KEYS 补充，正则只认真日期形态（防误匹配）
TS_RE = re.compile(
    r'"?(update_time|generated|data_date|generated_at|updateTime|calc_time|gen_time|run_time|last_time)"?'
    r'\s*[:=]\s*"?('
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(:[0-9]{2})?'
    r'|[0-9]{4}-[0-9]{2}-[0-9]{2}'
    r')'
)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def data_ts(blob_text: str | None) -> str | None:
    if not blob_text:
        return None
    m = TS_RE.search(blob_text[:200000])
    if not m:
        return None
    return m.group(2).replace("T", " ")


def show(ref: str, path: str) -> str | None:
    r = git("show", f"{ref}:{path}")
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    try:
        # ⓪ 确保拿到最新远端（v8_git_push.sh ② 已 pull，此处兜底自取）
        git("fetch", "origin", "main")

        # ① 找 origin/main 与 HEAD 在 data/|raw_data/ 下的差异文件
        d = git("diff", "--name-only", "origin/main", "HEAD", "--", *DATA_DIRS)
        files = [l.strip() for l in d.stdout.splitlines() if l.strip()]
        if d.returncode != 0:
            print(f"⚠️ 回滚否决跳过：git diff 失败 {d.stderr.strip()[:150]}")
            return 0
        if not files:
            return 0
        if len(files) > MAX_FILES:
            print(f"⚠️ 回滚否决跳过：差异文件 {len(files)} 个 > {MAX_FILES}（全量重建类提交，交由 parity 闸门把关）")
            return 0

        # ② 逐个比对权威时间戳
        vetoed, errors = [], 0
        for p in files:
            try:
                ts_head = data_ts(show("HEAD", p))
                ts_remote = data_ts(show("origin/main", p))
                if ts_head is None or ts_remote is None:
                    continue          # 任一侧无日期 → 不越权（parity 闸门有另外的陈旧判定）
                if ts_head[:19] < ts_remote[:19]:
                    r = git("checkout", "origin/main", "--", p)
                    if r.returncode != 0:
                        errors += 1
                        continue
                    vetoed.append(f"{p} (本地{ts_head[:19]} < 远端{ts_remote[:19]})")
            except Exception:
                errors += 1

        if errors:
            print(f"⚠️ 回滚否决：{errors} 个文件比对异常（已跳过，不阻断 push）")
        if not vetoed:
            return 0

        # ③ fixup 提交（只提交被否决文件，不碰暂存区其他内容）
        msg = "fix(veto): push前数据回滚否决——" + str(len(vetoed)) + "个数据文件放弃本地旧版取远端新版 (2026-11-23 一劳永逸接线)"
        c = git("commit", "-m", msg, "--", *vetoed)
        if c.returncode != 0:
            print(f"⚠️ 否决 fixup 提交失败（不影响 push 本体）：{c.stderr.strip()[:150]}")
            return 0
        print(f"🛑 数据回滚否决 {len(vetoed)} 项（已取远端新版随本 push 上线）：")
        for v in vetoed[:10]:
            print("   ", v)
        if len(vetoed) > 10:
            print(f"    … 共 {len(vetoed)} 项")
        return 0
    except Exception as e:
        print(f"⚠️ 回滚否决异常跳过（不阻断 push）：{e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
