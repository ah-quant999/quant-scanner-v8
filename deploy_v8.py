#!/usr/bin/env python3
"""v8 部署脚本 — 推送 index.html + data/ 到 quant-scanner-v8 的 main 分支

部署内容：
- index.html（轻量模板）
- data/*.js（同步加载的数据块）

注意：
- quant-scanner-v8 是独立仓库，GitHub Pages 从 main 分支直接服务。
- 本脚本使用列表参数 + --force 推送，避免 shell 对路径的误解析。
"""

import os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
GH_PAGES_URL = "git@github.com:ah-quant999/quant-scanner-v8.git"
SSH_CMD = 'ssh -o ConnectTimeout=15'


def log(msg):
    print(f"  {msg}")


def run(args, cwd=None):
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = SSH_CMD
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env, timeout=120)
    if r.returncode != 0:
        log(f"⚠️  {' '.join(args)}: {r.stderr.strip()}")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def deploy():
    tmp = tempfile.mkdtemp(prefix="v8deploy_")
    try:
        log("📥 克隆 main 分支...")
        code, _, err = run(["git", "clone", "--depth=1", GH_PAGES_URL, "."], cwd=tmp)
        if code != 0:
            log(f"克隆失败: {err}")
            return 1

        log("📄 复制 index.html + data/...")
        shutil.copy2(os.path.join(REPO, "index.html"), os.path.join(tmp, "index.html"))
        src_data = os.path.join(REPO, "data")
        dst_data = os.path.join(tmp, "data")
        if os.path.exists(dst_data):
            shutil.rmtree(dst_data)
        if os.path.exists(src_data):
            shutil.copytree(src_data, dst_data)
        else:
            log("⚠️  本地 data/ 目录不存在")

        run(["git", "config", "user.email", "2814546@qq.com"], cwd=tmp)
        run(["git", "config", "user.name", "ah-quant999"], cwd=tmp)
        run(["git", "add", "-A"], cwd=tmp)

        code, st_out, _ = run(["git", "status", "--porcelain"], cwd=tmp)
        if not st_out:
            log("✅ 无变化，跳过部署")
            return 0

        run(["git", "commit", "-m", "deploy v8 lightweight"], cwd=tmp)
        log("🚀 推送到 main...")
        code, out, err = run(["git", "push", "origin", "main", "--force"], cwd=tmp)
        if code != 0:
            log(f"推送失败: {err}")
            return 1
        log("✅ v8 部署成功！")
        log("   🌐 https://ah-quant999.github.io/quant-scanner-v8/")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(deploy())
