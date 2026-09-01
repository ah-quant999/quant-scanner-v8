#!/bin/sh
# pre-push 钩子：拦截「树被清空」型灾难推送
#
# === 事故背景（2026-09-01）===
# 并发自动化用「隔离 index 直推」技术推送单个文件改动时，
# update-index --cacheinfo 之前漏了 `git read-tree origin/main`，
# 于是 write-tree 产出的树**只含那一个文件**，commit-tree 拿它当新树推送，
# 结果是：一次「清理 index.html 陈旧注释」的推送，删掉了 899 个文件
# （data/*.js、raw_data/*.json、scripts/、algorithms/、.github/workflows/ 全灭），
# GitHub Pages 站点当场裸奔。
#
#   720171f13 (900 文件)  ->  bab3c5afa (1 文件)  ->  fd7fea82b (1 文件)
#   diff --name-status:   899 D  +  1 M(index.html)
#
# === 本钩子的设计原则 ===
# 1. **只拦截，绝不改写**：不 rebase、不 stash、不 checkout、不动工作树。
#    老的 scripts/pre-push 会自动 rebase，与隔离直推流程冲突，故不采用其行为。
# 2. **fail-open**：任何内部异常（取不到对象、命令失败）一律放行，
#    绝不能因为护栏自身出 bug 而卡死整条数据管线。
# 3. **可豁免**：确需大规模清理时，设环境变量 V8_PUSH_ALLOW_WIPE=1 放行。
#
# === 判据（对 refs/heads/main 生效）===
#   A. 推送后的树文件数 < 推送前远端文件数的 60%
#   B. 删除文件数 >= 30 且 >= 远端文件数的 10%
#   命中任一即拦截。正常清理（删 5~20 个文件）不会触发。
#
# 安装：
#   cp scripts/pre_push_tree_guard.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push
# 卸载：
#   rm .git/hooks/pre-push
# 临时放行：
#   V8_PUSH_ALLOW_WIPE=1 git push ...

LOG_FILE="$(git rev-parse --git-dir 2>/dev/null)/prepush_guard.log"

log() {
    [ -n "$LOG_FILE" ] && echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE" 2>/dev/null
    return 0
}

# 人工明确豁免
if [ "${V8_PUSH_ALLOW_WIPE:-0}" = "1" ]; then
    log "SKIP  已设置 V8_PUSH_ALLOW_WIPE=1，本次放行"
    exit 0
fi

blocked=0
reason=""

while read -r local_ref local_sha remote_ref remote_sha; do
    # 只管 main
    case "$remote_ref" in
        refs/heads/main) ;;
        *) continue ;;
    esac

    # 跳过删除分支 / 新建分支
    case "$local_sha" in
        0000000000000000000000000000000000000000) continue ;;
    esac
    case "$remote_sha" in
        0000000000000000000000000000000000000000) continue ;;
    esac

    n_old=$(git ls-tree -r --name-only "$remote_sha" 2>/dev/null | wc -l | tr -d '[:space:]')
    n_new=$(git ls-tree -r --name-only "$local_sha"  2>/dev/null | wc -l | tr -d '[:space:]')
    n_del=$(git diff --name-only --diff-filter=D "$remote_sha" "$local_sha" 2>/dev/null | wc -l | tr -d '[:space:]')

    # 取不到数（对象缺失/命令失败）→ fail-open
    case "$n_old" in
        ''|*[!0-9]*) log "SKIP  n_old 非法 [$n_old]，放行"; continue ;;
    esac
    if [ "$n_old" -lt 10 ]; then
        log "SKIP  远端文件数 $n_old 过少，无基线可比，放行"
        continue
    fi

    log "CHECK main: remote=$n_old -> push=$n_new, deleted=$n_del  (local_sha=$local_sha)"

    # 判据 A：结果树文件数不足 60%
    thr_a=$(( n_old * 60 / 100 ))
    if [ "$n_new" -lt "$thr_a" ]; then
        blocked=1
        reason="推送后文件数 $n_new < 远端基线 $n_old 的 60%（阈值 $thr_a）"
        log "BLOCK-A $reason"
    fi

    # 判据 B：大规模删除
    thr_b=$(( n_old / 10 ))
    if [ "$n_del" -ge 30 ] && [ "$n_del" -ge "$thr_b" ]; then
        blocked=1
        reason="删除 $n_del 个文件（>=30 且 >= 基线 $n_old 的 10%=$thr_b）"
        log "BLOCK-B $reason"
    fi
done

if [ "$blocked" = "1" ]; then
    echo "" >&2
    echo "############################################################" >&2
    echo "#  pre-push 护栏已拦截：这次推送会大规模删除 main 上的文件   #" >&2
    echo "############################################################" >&2
    echo "#  原因：$reason" >&2
    echo "#" >&2
    echo "#  2026-09-01 曾发生同类事故（899 文件被一次推送清空）。" >&2
    echo "#  若用「隔离 index 直推」，请确认执行了：" >&2
    echo "#      git read-tree origin/main      # <- 漏了这步就会清空仓库" >&2
    echo "#      git update-index --add --cacheinfo 100644,<blob>,<path>" >&2
    echo "#" >&2
    echo "#  确属有意为之，请用下面任一方式放行：" >&2
    echo "#      V8_PUSH_ALLOW_WIPE=1 git push ..." >&2
    echo "#      git push --no-verify ..." >&2
    echo "############################################################" >&2
    echo "" >&2
    log "RESULT BLOCKED"
    exit 1
fi

log "RESULT PASS"
exit 0
