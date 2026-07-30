#!/usr/bin/env python3
"""v8 部署脚本 — 推 index.html 到 quant-scanner-v8 的 gh-pages 分支（独立仓库，不依赖 v6）"""

import subprocess, sys, os, shutil, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V8_SRC = os.path.join(REPO, "v8", "dist", "index.html")
GH_PAGES_URL = "git@github.com:ah-quant999/quant-scanner-v8.git"

def log(msg):
    print(f"  {msg}")

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=120)
    if r.returncode != 0:
        log(f"⚠️  {cmd}: {r.stderr.strip()}")
    return r.stdout.strip()

def deploy():
    tmp = tempfile.mkdtemp(prefix="v8deploy_")
    try:
        log("📥 克隆 main 分支...")
        run(f"git clone --depth=1 {GH_PAGES_URL} .", cwd=tmp)

        log(f"📄 复制 index.html...")
        shutil.copy2(V8_SRC, os.path.join(tmp, "index.html"))

        run("git add -A", cwd=tmp)
        st = run("git status --porcelain", cwd=tmp)
        if not st:
            log("✅ 无变化，跳过部署")
            return

        run('git config user.email "2814546@qq.com"', cwd=tmp)
        run('git config user.name "ah-quant999"', cwd=tmp)
        run('git commit -m "deploy $(date +\\%Y-\\%m-\\%d_\\%H:\\%M)"', cwd=tmp)
        log("🚀 推送到 main...")
        run(f"git push origin main", cwd=tmp)
        log("✅ v8 部署成功！")
        log(f"   🌐 https://ah-quant999.github.io/quant-scanner-v8/")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    deploy()
