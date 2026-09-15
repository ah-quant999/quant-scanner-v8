#!/usr/bin/env python3
"""v8 守护脚本 — 守护 quant-scanner-v8 独立仓库的 main 分支

职责：
- 检查远程 main 分支是否包含 index.html 与 data/ 目录。
- 若缺失，从本地重新推送完整站点。

注意：
- 本脚本只守护 v8 独立仓库（quant-scanner-v8），不再指向 v6。
- 调用前请确保本地 index.html 与 data/ 是最新且正确的版本。
"""

import os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
GH_PAGES_URL = "git@github.com:ah-quant999/quant-scanner-v8.git"
SSH_CMD = 'ssh -o ConnectTimeout=15'


def log(msg):
    print(f"  [guard] {msg}")


def run(args, cwd=None):
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = SSH_CMD
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def needs_repush():
    """检查远程 main 上是否缺失 index.html 或 data/。"""
    tmp = tempfile.mkdtemp(prefix="guard_")
    try:
        code, _, err = run(["git", "clone", "--depth=1", GH_PAGES_URL, "."], cwd=tmp)
        if code != 0:
            log(f"克隆失败: {err}")
            return False
        has_index = os.path.exists(os.path.join(tmp, "index.html"))
        has_data = os.path.exists(os.path.join(tmp, "data"))
        return not (has_index and has_data)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def repush():
    local_index = os.path.join(REPO, "index.html")
    local_data = os.path.join(REPO, "data")
    if not os.path.exists(local_index):
        log("本地 index.html 不存在，跳过")
        return False

    tmp = tempfile.mkdtemp(prefix="v8push_")
    try:
        log("克隆 main...")
        code, _, err = run(["git", "clone", "--depth=1", GH_PAGES_URL, "."], cwd=tmp)
        if code != 0:
            log(f"克隆失败: {err}")
            return False

        shutil.copy2(local_index, os.path.join(tmp, "index.html"))
        dst_data = os.path.join(tmp, "data")
        if os.path.exists(dst_data):
            shutil.rmtree(dst_data)
        if os.path.exists(local_data):
            shutil.copytree(local_data, dst_data)

        run(["git", "config", "user.email", "2814546@qq.com"], cwd=tmp)
        run(["git", "config", "user.name", "ah-quant999"], cwd=tmp)
        run(["git", "add", "-A"], cwd=tmp)
        _, st_out, _ = run(["git", "status", "--porcelain"], cwd=tmp)
        if not st_out:
            log("远程已是最新，无需重推")
            return True

        run(["git", "commit", "-m", "guard: restore v8 lightweight"], cwd=tmp)
        log("推送 main...")
        # 🛡 分支保护已生效（2026-09-04，main 禁 force push）：
        # 改为先 fetch 对齐再普通推送；被拒（并发互踩/保护）时 fetch+rebase 后重试，
        # 与 .github/workflows/v8_algo_intraday_lite.yml 的加固模式一致。
        pushed = False
        for i in (1, 2, 3):
            code, out, err = run(["git", "push", "origin", "main"], cwd=tmp)
            if code == 0:
                pushed = True
                break
            log(f"⚠️ push 被拒（并发互踩/保护），fetch+rebase 后重试 ({i}/3)")
            if run(["git", "fetch", "--depth=100", "origin", "main"], cwd=tmp)[0] != 0:
                break
            if run(["git", "rebase", "FETCH_HEAD"], cwd=tmp)[0] != 0:
                run(["git", "rebase", "--abort"], cwd=tmp)
                log("❌ rebase 冲突：远端已有更新内容，放弃本轮（绝不 force），以远端为准")
                return False
        if not pushed:
            log("推送失败: 3 次重试后仍失败")
            return False
        log(f"v8 已恢复 ({out.splitlines()[-1] if out else 'OK'})")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    log("检查 v8 独立仓库状态...")
    if needs_repush():
        log("v8 远程文件缺失，正在恢复...")
        repush()
    else:
        log("v8 正常")
