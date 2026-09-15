#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_git_hooks.py — 一键安装仓库 git hooks（幂等，双机各跑一次）

当前只装一件事：**提交前凭据闸门**（`.githooks/pre-commit` → `scripts/secret_guard.py`）。

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
    hook = os.path.join(ROOT, WANT, "pre-commit")

    print("仓库根        : %s" % ROOT)
    print("core.hooksPath: %s" % (cur or "(未设置 → 用 .git/hooks，闸门不生效)"))
    print("hook 文件     : %s %s" % (hook, "存在" if os.path.exists(hook) else "缺失"))

    if cur == WANT and os.path.exists(hook):
        print("\n✅ 凭据闸门已启用，无需操作")
        return 0

    if check_only:
        print("\n⚠️ 凭据闸门未启用 —— 运行 `python scripts/install_git_hooks.py` 安装")
        return 1

    if not os.path.exists(hook):
        print("\n🚫 %s/pre-commit 不存在，无法安装（请先 git pull 同步仓库）" % WANT)
        return 1

    r = git("config", "--local", "core.hooksPath", WANT)
    if r.returncode != 0:
        print("\n🚫 设置 core.hooksPath 失败: %s" % r.stderr.strip())
        return 1

    # 尽力补上可执行位（Windows 上无意义，Linux/macOS/CI 上有意义）
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass

    print("\n✅ 已设置 core.hooksPath = %s" % WANT)
    print("   自测：git add <某个凭据文件> && git commit  →  应被拒绝")
    print("   撤销：git config --local --unset core.hooksPath")
    return 0


if __name__ == "__main__":
    sys.exit(main())
