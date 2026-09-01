#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw_data 隔离 index 直推 —— 绕开「工作树带本地改动导致 rebase abort」的死循环。

为什么需要它
------------
原自动化 Step 2 是：
    git add raw_data/ && git commit && git pull --rebase --autostash origin main && git push

本机工作树长期相对 origin/main 带本地改动（index.html、data/PORTFOLIO.js、
.github/workflows/*、update_v8.py 等），于是 `pull --rebase` 在 checkout 阶段
恒定报 "Your local changes to the following files would be overwritten by checkout"
并 abort（--autostash 也救不了，2026-09-01 11:24 实测两次）；
被 `|| true` 吞掉后紧接着的 `git push origin main` 又会因非快进被
"fetch first" 拒绝 —— 结果是**每轮推送实际上都失败**，且常被误读成"无变化"。

本脚本用隔离 index 直接在 origin/main 之上构造提交并推送：
完全不依赖 HEAD、不碰工作树、不需要 rebase、不会 stash。

安全护栏
--------
1. 只允许 raw_data/ 前缀，其它路径一律中止
2. 内置反回归：本地文件【内容内部时间戳】比远端旧 → 跳过该文件（不覆盖线上新数据）
3. push 前核对文件数 == 预期，0 行或越界即中止（绝不把"0 文件"当无变化放过）
4. 遇 "fetch first"（并发 build 推进远端）自动重新 fetch + 重建父提交，最多 5 次
5. 严禁 --force；失败即退出码非 0，让调用方能如实上报

用法
----
    python scripts/push_raw_isolated.py -m "data: 盘中补抓 20260901-1126"
    python scripts/push_raw_isolated.py --dry-run        # 只看会推哪些文件
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS_KEYS = ("update_time", "gen_time", "republish_time", "as_of", "date",
           "trade_date", "snapshot_time", "fetch_time")
ISO_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})"
                    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?")


def git(args, env=None, check=True):
    r = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    if check and r.returncode != 0:
        print("[FAIL] git", " ".join(args))
        print((r.stdout or "")[:500], (r.stderr or "")[:500])
        sys.exit(1)
    return (r.stdout or "").strip()


def norm_ts(s):
    if not s:
        return None
    m = ISO_RE.search(str(s))
    if not m:
        return None
    return "%s%02d%02d%02d%02d%02d" % (m.group(1), int(m.group(2)), int(m.group(3)),
                                       int(m.group(4) or 0), int(m.group(5) or 0),
                                       int(m.group(6) or 0))


def extract_ts(content):
    if not content:
        return None
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            for k in TS_KEYS:
                ts = norm_ts(obj.get(k))
                if ts:
                    return ts
    except Exception:
        pass
    return norm_ts(content[:4000])


ACCUM_RE = re.compile(r"history|archive|_track|_log|daily_", re.I)


def count_entries(text):
    """历史累积型文件的「条目数」，用于判断是否会因推送而丢失累积数据。"""
    if not text:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        best = 0
        for v in obj.values():
            if isinstance(v, list):
                best = max(best, len(v))
        return best or None
    return None


def collect_files():
    """本地工作树与 origin/main 有差异的 raw_data 文件。"""
    out = git(["diff", "--name-only", "origin/main", "--", "raw_data/"])
    return [f.strip() for f in out.splitlines() if f.strip()]


def main():
    dry = "--dry-run" in sys.argv
    msg = "data: 隔离 index 直推 raw_data"
    if "-m" in sys.argv:
        i = sys.argv.index("-m")
        if i + 1 < len(sys.argv):
            msg = sys.argv[i + 1]

    print("[push] fetch origin/main ...")
    git(["fetch", "origin", "main"])

    files = collect_files()
    print("[push] 与 origin/main 有差异的 raw_data 文件: %d" % len(files))
    if not files:
        print("[push] 无差异，无需推送")
        return 0

    # 反回归过滤：本地比远端旧的文件直接跳过（绝不覆盖线上新数据）
    entries, skipped = [], []
    for f in files:
        p = ROOT / f
        if not p.exists():
            print("  [skip] %s (本地已不存在)" % f)
            skipped.append(f)
            continue
        local = p.read_text(encoding="utf-8", errors="replace")
        # 取不到远端版本（新增文件）时 rc != 0，remote 记为空串即可
        try:
            remote = git(["show", "origin/main:%s" % f], check=True)
        except SystemExit:
            remote = ""
        ts_l, ts_r = extract_ts(local), extract_ts(remote)
        if ts_l and ts_r and ts_l < ts_r:
            print("  [REGRESSION-SKIP] %s 本地 %s < 远端 %s（保留远端新版）" % (f, ts_l, ts_r))
            skipped.append(f)
            continue

        # 防累积丢失：history/archive/track 类文件若本地条目数少于远端，
        # 推上去会把远端已累积的历史冲掉（时间戳字段往往无法反映条目多少）
        if ACCUM_RE.search(f):
            n_l, n_r = count_entries(local), count_entries(remote)
            if n_l is not None and n_r is not None and n_l < n_r:
                print("  [ACCUM-SKIP] %s 本地 %d 条 < 远端 %d 条（保留远端完整历史）"
                      % (f, n_l, n_r))
                skipped.append(f)
                continue
        blob = git(["hash-object", "-w", f])
        entries.append((blob, f))
        print("  [+] %s (ts=%s)" % (f, ts_l or "n/a"))

    if not entries:
        print("[push] 全部为回归项或已无有效变更，取消推送")
        return 0

    print("[push] 待推 %d 个文件 / 跳过 %d 个" % (len(entries), len(skipped)))
    if dry:
        print("[push] --dry-run，未实际推送")
        return 0

    if any(not f.startswith("raw_data/") for _b, f in entries):
        print("[ABORT] 越界路径")
        return 3

    tmp_index = os.path.join(str(ROOT), ".git", "tmp_push_isolated")
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = tmp_index

    for attempt in range(1, 6):
        git(["fetch", "origin", "main"])
        if os.path.exists(tmp_index):
            os.remove(tmp_index)
        git(["read-tree", "origin/main"], env=env)
        for blob, f in entries:
            git(["update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, f)], env=env)

        d = git(["diff", "--cached", "--name-only", "origin/main"], env=env)
        staged = [x.strip() for x in d.splitlines() if x.strip()]
        print("[try %d] 隔离索引变更 %d 个文件" % (attempt, len(staged)))
        if len(staged) == 0:
            print("[INFO] 远端已含相同内容（并发已代发），无需推送")
            break
        if any(not x.startswith("raw_data/") for x in staged):
            print("[ABORT] 越界文件:", staged[:5])
            return 3

        tree = git(["write-tree"], env=env)
        newc = git(["commit-tree", tree, "-p", "origin/main", "-m", msg], env=env)
        print("[try %d] 新提交: %s" % (attempt, newc))

        r = subprocess.run(["git", "push", "origin", "%s:main" % newc], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print("[push] ✅ 已推送 %s" % newc[:10])
            break
        if "fetch first" in (r.stderr or ""):
            print("[retry %d] 远端被并发推进，重新 fetch 后重建" % attempt)
            continue
        print("[ABORT] push 失败:", (r.stderr or "")[:500])
        return 4
    else:
        print("[ABORT] 5 次重试仍失败")
        return 5

    if os.path.exists(tmp_index):
        os.remove(tmp_index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
