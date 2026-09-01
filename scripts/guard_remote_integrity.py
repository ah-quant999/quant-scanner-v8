#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远端 main 完整性哨兵 —— 检测并（可选）修复「仓库被一次推送清空」类灾难。

背景（2026-09-01 事故）
----------------------
某次「只改 index.html」的推送，因隔离 index 漏跑 `git read-tree origin/main`，
产出的树只有 index.html，一次推送删掉 899 个文件（900 -> 1）。
`.git/hooks/pre-push`（scripts/pre_push_tree_guard.sh）是**事前拦截**，
本脚本是**事后兜底**：他在他机推送、`--no-verify`、或钩子被覆盖时仍能发现。

做什么
------
1. fetch origin/main，统计文件数
2. 与基线（.git/remote_integrity.json 记录的历史最大文件数）比对
3. 正常：更新基线并退出 0
4. 崩塌（< 基线 60%）：退出 2 并打印告警；带 --fix 则自动快进恢复

恢复策略（--fix，永不 force push、永不改写历史）
-----------------------------------------------
  base   = origin/main 历史中「文件数 >= 基线*90%」的**最新**提交（自动挑，不用写死 sha）
  overlay= 当前 tip 的全部文件（这些是清空之后真实产生的新内容，如被改的 index.html）
  新树   = base 树 + overlay；父提交 = 当前 tip  →  天然 fast-forward
这样既不丢清空后的合法改动，也不回滚任何人的提交历史。

用法
----
    python scripts/guard_remote_integrity.py            # 只读检查
    python scripts/guard_remote_integrity.py --fix      # 检查 + 自动快进恢复
    python scripts/guard_remote_integrity.py --reset-baseline

退出码：0 正常 / 2 检测到崩塌（未修复）/ 3 修复失败 / 4 参数或环境异常
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".git" / "remote_integrity.json"
RATIO_ALERT = 0.60      # 低于基线这个比例即判崩塌
RATIO_GOODBASE = 0.90   # 挑选恢复基准时的文件数下限


def git(args, env=None, check=True, raw=False):
    # 注意：subprocess 只要传了 encoding= 就强制文本模式，text=False 也无效。
    # 所以 raw 模式下必须**完全不传** text/encoding/errors，才能拿到 bytes。
    kw = {} if raw else {"text": True, "encoding": "utf-8", "errors": "replace"}
    r = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True,
                       env=env, **kw)
    if check and r.returncode != 0:
        print("[FAIL] git", " ".join(args))
        print((r.stderr or (b"" if raw else ""))[:400])
        sys.exit(1)
    out = r.stdout or (b"" if raw else "")
    # 文本模式必须 strip：rev-parse / commit-tree 的返回值会带尾随换行，
    # 直接拼进 refspec 或对象名会变成 "Not a valid object name xxx\n"。
    # （2026-09-01 自查时踩到，commit-tree 的 sha 带 \n 会让 push 直接失败）
    return out.strip() if not raw else out


def count_files(rev):
    out = git(["ls-tree", "-r", "--name-only", rev])
    return len([x for x in out.split("\n") if x.strip()])


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def list_tree(rev):
    """返回 {path: (mode, sha)}，用 -z 保证中文路径不被转义。"""
    raw = git(["ls-tree", "-r", "-z", rev], raw=True)
    out = {}
    for chunk in raw.split(b"\x00"):
        if not chunk:
            continue
        meta, _, path = chunk.partition(b"\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        out[path.decode("utf-8", "replace")] = (parts[0].decode(), parts[2].decode())
    return out


def find_good_base(baseline, max_scan=400):
    """在 origin/main 历史里挑最新的、文件数仍健康（>= 基线*90%）的提交。"""
    revs = git(["rev-list", "--max-count=%d" % max_scan, "origin/main"]).split()
    floor = int(baseline * RATIO_GOODBASE)
    for rev in revs:
        if count_files(rev) >= floor:
            return rev
    return None


def do_fix(baseline, tip, tip_n):
    base = find_good_base(baseline)
    if not base:
        print("[ABORT] 历史中找不到健康基准（>= %d 文件）" % int(baseline * RATIO_GOODBASE))
        return 3
    base_n = count_files(base)
    print("[fix] 恢复基准: %s (%d 文件)" % (base[:10], base_n))

    tree = list_tree(base)
    overlay = list_tree(tip)
    for p, v in overlay.items():
        tree[p] = v
    print("[fix] base %d 文件 + tip overlay %d 个 -> 新树 %d 文件" % (base_n, len(overlay), len(tree)))

    tmp_index = str(ROOT / ".git" / "tmp_integrity_restore")
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = tmp_index
    if os.path.exists(tmp_index):
        os.remove(tmp_index)
    git(["read-tree", base], env=env)
    for p, (mode, sha) in tree.items():
        git(["update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, sha, p)], env=env)

    staged = git(["diff", "--cached", "--name-only", tip], env=env)
    n_staged = len([x for x in staged.split("\n") if x.strip()])
    print("[fix] 相对当前 tip 变更 %d 个文件" % n_staged)
    if n_staged == 0:
        print("[fix] 无差异，取消")
        if os.path.exists(tmp_index):
            os.remove(tmp_index)
        return 0

    new_tree = git(["write-tree"], env=env)
    newc = git(["commit-tree", new_tree, "-p", tip,
                "-m", "revert: 自动恢复被误清空的工作树（guard_remote_integrity）"], env=env)
    print("[fix] 新提交 %s -> push origin main" % newc[:10])
    r = subprocess.run(["git", "push", "origin", "%s:main" % newc], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if os.path.exists(tmp_index):
        os.remove(tmp_index)
    if r.returncode != 0:
        print("[ABORT] push 失败:", (r.stderr or "")[:400])
        return 3
    git(["fetch", "origin", "main"])
    new_n = count_files("origin/main")
    print("[fix] ✅ 恢复完成 tip=%s 文件数=%d (was %d)" % (
        git(["rev-parse", "--short", "origin/main"]), new_n, tip_n))
    return 0 if new_n >= int(baseline * RATIO_GOODBASE) else 3


def main():
    if "--reset-baseline" in sys.argv:
        save_state({})
        print("[state] 基线已清空")
        return 0

    git(["fetch", "origin", "main"])
    tip = git(["rev-parse", "origin/main"])
    n = count_files("origin/main")
    st = load_state()
    baseline = int(st.get("max_files") or 0)

    print("[integrity] origin/main = %s  文件数 = %d  基线 = %d" % (tip[:10], n, baseline))

    # 首次运行或基线为空：仅建立基线
    if baseline <= 0:
        save_state({"max_files": n, "last_good": tip, "updated": ""})
        print("[integrity] 首次运行，已建立基线 %d" % n)
        return 0

    # 正常：刷新基线（只增不减，防止把被削后的值当新基线）
    if n >= int(baseline * RATIO_ALERT):
        if n > baseline:
            save_state({"max_files": n, "last_good": tip, "updated": ""})
            print("[integrity] ✅ 正常，基线上调 %d -> %d" % (baseline, n))
        else:
            print("[integrity] ✅ 正常")
        return 0

    # 崩塌
    print("[integrity] 🚨 崩塌：%d -> %d（基线的 %.0f%%）" % (baseline, n, n * 100.0 / baseline))
    if "--fix" in sys.argv:
        return do_fix(baseline, tip, n)
    print("[integrity] 只读模式，未修复。加 --fix 可自动快进恢复。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
