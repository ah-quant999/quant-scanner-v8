#!/usr/bin/env python3
# scripts/ai_entry_bootstrap.py — v8 入口文件本地铺设（双机通用 · 路径无关）
#
# 背景：2026-09-21 发现双机「用户级记忆目录互相独立」。小九机铺的指针写死了
#       小九机路径（E:\qs_workspaces\...），阿狸咪机读不到且路径错误；且阿狸咪机
#       没有小九机专属的 v8_handoff_edit_kit.py。故本脚本**自包含**、**路径无关**，
#       任何一台机 clone 后 `git pull` 跑一次即可把入口接通。
#
# 用法（在已 clone 的 v8 仓内或其子目录执行）：
#   python scripts/ai_entry_bootstrap.py
#
# 做了什么：
#   1. 把「路径无关版用户级指针」写入本机 ~/.codebuddy/CODEBUDDY.md 与
#      ~/.workbuddy/CODEBUDDY.md（覆盖「会话工作区不是仓根」的场景）；
#   2. 若仓内 .codebuddy/CODEBUDDY.md 缺失，从 origin/main 取真身落盘
#      （覆盖「工作区是仓根但缺文件」的场景）。
# 不做：绝不写协议正文、绝不碰 token、绝不改仓内任何源文件（只落入口指针）。

import os
import sys
import subprocess

# 🔴 路径无关版用户级指针（与绝对路径无关，双机通用）
POINTER = '''# CODEBUDDY.md — 用户级记忆（跨项目）

> 极简**指针**，只做一件事：把会话导到项目的**入口文件**。**不重复任何项目内规则**。

## 🔴 若你要动 `quant-scanner-v8`（唯一大项目）

- 仓库 `ah-quant999/quant-scanner-v8`：**双机（小九机／阿狸咪机）共写，`main` 分钟级 churn**。
- **动该仓任何文件之前，先读该仓仓根的 `AGENTS.md`** —— 它是**唯一入口索引**。
  读法（任选其一，**均不依赖绝对路径**）：
  - 若会话工作区＝仓根：WorkBuddy 会**自动加载** `.codebuddy/CODEBUDDY.md` → 指向 `AGENTS.md`，直接读工作树即可；
  - 否则：`git -C <你的仓根> show origin/main:AGENTS.md`，或 `git show FETCH_HEAD:AGENTS.md`。
- 它指向的四份**权威**：
  `docs/ops/HANDOFF.yaml`（唯一状态源，防重复劳动）·
  `docs/ops/skills/v8-handoff-gateway/SKILL.md`（并发协议唯一正文）·
  `SECURITY_RULES.md`（token 铁律）· `TIME_ORDER.md`（改 cron 前必读）。
- 该仓**写入窗口**：09:15–11:30 / 12:45–15:00 为盘中，**禁推**（改动先落 staging）。
'''


def _run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL)


def detect_repo_root():
    """从本脚本位置往上找带 .git 的目录；失败则用 git rev-parse 兜底。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        if os.path.isdir(os.path.join(cur, '.git')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    try:
        out = _run(['git', 'rev-parse', '--show-toplevel']).decode().strip()
        if out:
            return out
    except Exception:
        pass
    return None


def main():
    root = detect_repo_root()
    if not root:
        print('❌ 未检测到 v8 仓根（请在 clone 目录下运行本脚本，或先 cd 到仓根）')
        sys.exit(1)
    print('仓根 = %s' % root)

    # ① 仓内 .codebuddy/CODEBUDDY.md 缺失则落真身
    cb = os.path.join(root, '.codebuddy', 'CODEBUDDY.md')
    if not os.path.exists(cb):
        try:
            data = _run(['git', '-C', root, 'show', 'origin/main:.codebuddy/CODEBUDDY.md'])
            os.makedirs(os.path.dirname(cb), exist_ok=True)
            with open(cb, 'wb') as f:
                f.write(data)
            print('✅ 仓内 .codebuddy/CODEBUDDY.md 已落下 (%d B)' % len(data))
        except Exception as e:
            print('⚠️ 仓内 .codebuddy/CODEBUDDY.md 落下失败（不影响用户级指针）：%r' % (e,))
    else:
        print('＝ 仓内 .codebuddy/CODEBUDDY.md 已存在')

    # ② 用户级指针（双机通用）
    home = os.path.expanduser('~')
    targets = [
        os.path.join(home, '.codebuddy', 'CODEBUDDY.md'),
        os.path.join(home, '.workbuddy', 'CODEBUDDY.md'),
    ]
    for t in targets:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        if os.path.exists(t):
            with open(t, 'r', encoding='utf-8') as f:
                old = f.read()
            if old.strip() == POINTER.strip():
                print('＝ 已一致: %s' % t)
                continue
        with open(t, 'w', encoding='utf-8') as f:
            f.write(POINTER)
        print('↑ 已更新: %s (%d B)' % (t, len(POINTER)))

    print('完成。重开一个 WorkBuddy 会话（工作区指向仓根）即可自动加载入口；')
    print('若工作区不是仓根，本机用户级指针已就位，同样会注入。')


if __name__ == '__main__':
    main()
