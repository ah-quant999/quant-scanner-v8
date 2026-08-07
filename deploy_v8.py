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
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env, timeout=420)
    if r.returncode != 0:
        log(f"⚠️  {' '.join(args)}: {r.stderr.strip()}")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def deploy():
    tmp = tempfile.mkdtemp(prefix="v8deploy_")
    try:
        # 【防回退】先同步本地仓库到 origin/main，避免用陈旧本地副本覆盖线上
        log("🔄 同步本地到 origin/main（防回退）...")
        run(["git", "fetch", "origin"], cwd=REPO)
        rc, _, _ = run(["git", "rebase", "origin/main"], cwd=REPO)
        if rc != 0:
            run(["git", "rebase", "--abort"], cwd=REPO)
            run(["git", "stash"], cwd=REPO)
            rc, _, _ = run(["git", "rebase", "origin/main"], cwd=REPO)
            run(["git", "stash", "pop"], cwd=REPO)
            if rc != 0:
                log("⚠️ 本地与 origin/main 冲突，请先解决后再部署")
                return 1

        log("📥 克隆 main 分支...")
        code, _, err = run(["git", "clone", "--depth=1", GH_PAGES_URL, "."], cwd=tmp)
        if code != 0:
            log(f"克隆失败: {err}")
            return 1

        log("📄 复制 index.html + data/...")
        # 护栏：先记录 origin/main 当前 index.html 拥有的板块 id，防止本地旧副本覆盖掉既有板块
        import re as _re
        _origin_html = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
        _origin_secs = set(_re.findall(r'data-sec="([^"]+)"', _origin_html))
        _origin_secs |= set(_re.findall(r'data-lg="([^"]+)"', _origin_html))

        shutil.copy2(os.path.join(REPO, "index.html"), os.path.join(tmp, "index.html"))
        src_data = os.path.join(REPO, "data")
        dst_data = os.path.join(tmp, "data")
        if os.path.exists(dst_data):
            shutil.rmtree(dst_data)
        if os.path.exists(src_data):
            shutil.copytree(src_data, dst_data)
        else:
            log("⚠️  本地 data/ 目录不存在")

        # 护栏：若本地 index.html 缺少 origin 已有的板块（如 v6备忘录），中止部署，避免冲掉他人/历史内容
        _local_html = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
        _local_secs = set(_re.findall(r'data-sec="([^"]+)"', _local_html))
        _local_secs |= set(_re.findall(r'data-lg="([^"]+)"', _local_html))
        _dropped = _origin_secs - _local_secs
        if _dropped:
            log(f"⚠️ 部署中止：本地 index.html 缺少 origin 已有板块 {sorted(_dropped)}，会覆盖掉既有内容。请先 'git pull' 同步后再部署。")
            return 1

        # 校验：index.html 引用的 data/*.js 必须都存在，防止部署残缺页面
        _refs = _re.findall(r'src="data/([A-Z_]+)\.js"', _local_html)
        _missing = [r for r in _refs if not os.path.exists(os.path.join(tmp, "data", r + ".js"))]
        if _missing:
            log(f"⚠️ 数据文件缺失，部署中止: {_missing}")
            return 1

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
