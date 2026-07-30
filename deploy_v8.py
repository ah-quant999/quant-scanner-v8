#!/usr/bin/env python3
"""v8 部署脚本 — 推 v8/index.html 到 gh-pages 的 v8/ 子目录（不影响 v6 主站）"""

import subprocess, sys, os, shutil, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V8_SRC = os.path.join(REPO, "v8", "dist", "index.html")
GH_PAGES_URL = "https://github.com/ah-quant999/quant-scanner-v6.git"

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
        log("📥 克隆 gh-pages 分支...")
        run(f"git clone -b gh-pages --depth=1 {GH_PAGES_URL} .", cwd=tmp)

        target = os.path.join(tmp, "v8")
        os.makedirs(target, exist_ok=True)

        log(f"📄 复制 v8/index.html...")
        shutil.copy2(V8_SRC, os.path.join(target, "index.html"))

        run("git add -A", cwd=tmp)
        st = run("git status --porcelain", cwd=tmp)
        if not st:
            log("✅ v8 无变化，跳过部署")
            return

        run('git commit -m "deploy v8 $(date +\\%Y-\\%m-\\%d_\\%H:\\%M)"', cwd=tmp)
        log("🚀 推送到 gh-pages...")
        run(f"git push origin gh-pages", cwd=tmp)
        log("✅ v8 部署成功！")
        log(f"   🌐 https://ah-quant999.github.io/quant-scanner-v6/v8/")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    deploy()
