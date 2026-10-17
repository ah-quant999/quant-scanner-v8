#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_git_hooks.py — 一键安装仓库 git hooks（幂等，双机各跑一次）

装两件事：
  1. **提交前凭据闸门**（`.githooks/pre-commit` → `scripts/secret_guard.py`）
  2. **防覆盖闸门**（`.githooks/pre-push`）——🔴 2026-09-20 追加：
     主机感知，**仅家机**（存在 ~/.workbuddy/v8_home_block_push）拦截
     「会覆盖/改写远端 main 权威历史」的非快进推送（含 --force）；
     小九机（lemoncat-cn）无标记 → 完全放行，行为与装前一致。

为什么需要单独安装：
  git 的 `core.hooksPath` 是**本地配置**，不随仓库分发；`.git/hooks/` 也不入库。
  所以 hook 文件本身能提交进仓库，但「启用它」必须每台机各做一次。

用法：
  python scripts/install_git_hooks.py          # 安装
  python scripts/install_git_hooks.py --check  # 只检查当前状态

装完可用 `git commit` 时故意 stage 一个凭据文件来自测（应被拒绝）。
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WANT = ".githooks"
HOOKS = ("pre-commit", "pre-push")


def hook_path(name):
    return os.path.join(ROOT, WANT, name)


def git(*args, **kw):
    env = dict(os.environ)
    env.pop("GIT_INDEX_FILE", None)
    return subprocess.run(["git"] + list(args), cwd=ROOT,
                          capture_output=True, text=True, env=env, **kw)


def current():
    r = git("config", "--local", "--get", "core.hooksPath")
    return r.stdout.strip() if r.returncode == 0 else ""


def main():
    check_only = "--check" in sys.argv
    cur = current()
    present = {h: os.path.exists(hook_path(h)) for h in HOOKS}

    print("仓库根        : %s" % ROOT)
    print("core.hooksPath: %s" % (cur or "(未设置 → 用 .git/hooks，闸门不生效)"))
    for h in HOOKS:
        p = hook_path(h)
        mode = ("0o%o" % (os.stat(p).st_mode & 0o777)) if present[h] else "-"
        print("hook 文件     : %-11s %-4s %s" % (h, "存在" if present[h] else "缺失", mode))

    missing = [h for h in HOOKS if not present[h]]
    if missing:
        print("\n⚠️ 缺少 hook 文件: %s —— 请先 git pull 同步仓库" % ", ".join(missing))

    if check_only:
        ok = (cur == WANT) and not missing
        print("\n✅ 钩子已启用且文件齐备" if ok else "\n⚠️ 钩子未就绪 —— 运行 `python scripts/install_git_hooks.py` 安装")
        return 0 if ok else 1

    if missing:
        return 1

    r = git("config", "--local", "core.hooksPath", WANT)
    if r.returncode != 0:
        print("\n🚫 设置 core.hooksPath 失败: %s" % r.stderr.strip())
        return 1

    # 尽力补上可执行位（Windows 上无意义，Linux/macOS/CI 上有意义；
    # 🔴 不 chmod 的话在 POSIX 上钩子会被静默跳过 = 假保护）
    for h in HOOKS:
        try:
            os.chmod(hook_path(h), 0o755)
        except OSError:
            pass

    print("\n✅ 已设置 core.hooksPath = %s，并已补齐 %d 个钩子的可执行位" % (WANT, len(HOOKS)))
    print("   · pre-commit 自测：git add <某个凭据文件> && git commit  →  应被拒绝")
    print("   · pre-push   自测：git push origin main  →  家机应拦截；小九机应放行")
    print("   撤销：git config --local --unset core.hooksPath")
    return 0


if __name__ == "__main__":
    sys.exit(main())
