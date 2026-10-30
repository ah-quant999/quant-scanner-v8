#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# v8_git_push.sh — 经分布式推送锁串行化后的 git push（best-effort，锁失败也照推）
#
# 用法（在仓库根目录执行）：
#   bash v8_git_push.sh [<remote-url-or-name>] [<target>]
#   默认：bash v8_git_push.sh origin HEAD:main
#
# 行为：
#   1) 抢锁 v8-push-lock（python v8_push_lock.py acquire，best-effort，失败不阻断）
#   2) git pull --rebase 把本地 commit 合到最新 main（防分叉 / 防 reset --hard 吞改动）
#   3) git push
#   4) 放锁（best-effort）
#
# 退出码：push 成功 0 / 失败 1。锁相关步骤任何异常都不影响 push 结果。
# ═══════════════════════════════════════════════════════════════════════════
set -u
REPO_URL="${1:-origin}"
TARGET="${2:-HEAD:main}"

HOLDER="gitcli:${GITHUB_WORKFLOW:-local}:${GITHUB_RUN_ID:-$$}"
PY="$(command -v python3 || command -v python)"

# ① 抢锁（best-effort）
"$PY" v8_push_lock.py acquire --holder "$HOLDER" --ttl 1200 --max-wait 600 || true

# ② 集成远端最新（best-effort，失败不阻断）
git pull --rebase "$REPO_URL" main 2>/dev/null || true

# ③ 推送
if git push "$REPO_URL" "$TARGET"; then
  RC=0
else
  RC=1
fi

# ④ 放锁（best-effort）
"$PY" v8_push_lock.py release --holder "$HOLDER" || true

exit $RC
