#!/usr/bin/env python3
"""v8 守护脚本 — 每次 v6 自动 deploy 后自动重新推 v8/index.html 到 gh-pages/v8/

调用方式（由 v6 deploy 完成后的钩子触发，或定时每 30 分钟跑一次）：
  python v8/guard_v8.py
"""

import subprocess, os, sys, shutil, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V8_DIST = os.path.join(REPO, "v8", "dist", "index.html")
GH_PAGES_URL = "git@github.com:ah-quant999/quant-scanner-v6.git"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def log(msg):
    print(f"  [guard] {msg}")


def needs_repush():
    """检查 gh-pages 上是否有 v8/index.html，没有则需要推"""
    code, out, err = run("git ls-remote origin gh-pages")
    if code != 0:
        log(f"无法访问远程 gh-pages: {err}")
        return False
    tmp = tempfile.mkdtemp(prefix="guard_")
    try:
        code, out, err = run(f"git clone --depth=1 -b gh-pages {GH_PAGES_URL} .", cwd=tmp)
        if code != 0:
            return False
        v8_exists = os.path.exists(os.path.join(tmp, "v8", "index.html"))
        return not v8_exists
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def repush():
    if not os.path.exists(V8_DIST):
        log(f"本地 v8/dist/index.html 不存在，跳过")
        return False
    tmp = tempfile.mkdtemp(prefix="v8push_")
    try:
        log("克隆 gh-pages...")
        code, _, err = run(f"git clone --depth=1 -b gh-pages {GH_PAGES_URL} .", cwd=tmp)
        if code != 0:
            log(f"克隆失败: {err}")
            return False
        os.makedirs(os.path.join(tmp, "v8"), exist_ok=True)
        shutil.copy2(V8_DIST, os.path.join(tmp, "v8", "index.html"))
        run('git config user.email "2814546@qq.com"', cwd=tmp)
        run('git config user.name "ah-quant999"', cwd=tmp)
        run("git add -A", cwd=tmp)
        st_code, st_out, _ = run("git status --porcelain", cwd=tmp)
        if not st_out:
            log("v8 已存在无需重推")
            return True
        run('git commit -m "guard: restore v8 index.html"', cwd=tmp)
        log("推 v8 到 gh-pages...")
        code, out, err = run("git push origin gh-pages", cwd=tmp)
        if code == 0:
            log(f"v8 已恢复 ({out.splitlines()[-1] if out else 'OK'})")
            return True
        log(f"推送失败: {err}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    log("检查 v8 状态...")
    if needs_repush():
        log("v8 丢失，正在恢复...")
        repush()
    else:
        log("v8 正常")
