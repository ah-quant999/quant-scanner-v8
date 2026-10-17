#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""secret_guard.py — 提交前凭据闸门（2026-09-14 小九）

【为什么需要它】
本仓（ah-quant999/quant-scanner-v8）是 **public** 仓库，已发生两次同类事故：
  · 2026-08-24  `data/.mahoro_cookies.txt` 被一次全域 `git add -f` 提交进 main
  · 2026-09-11  `data/zsxq_token.json`     同类，commit a865d6f11 永久留在公开历史，
                已暴露 61.4 h（`.gitignore` 早已忽略它，但 `-f` 强行绕过）

根因是**手工全域 `git add -f`**，不是某个脚本 ——
`v8_closing_data_refresh.py` 的 `git add -f data/*.js raw_data/*.json` 其实**匹配不到**
`data/zsxq_token.json`（pathspec 含 `/` 时 `*` 不跨 `/`，且带后缀要求）。
⇒ 防线必须做在**提交闸门**：写在某个脚本里的守卫挡不住手工操作。

【判定规则】
  A. 路径名规则
     · 文件名含 token/secret/cookie/credential/password/jwt/apikey 等词
       → 若在 `data/` 或 `raw_data/` 下，**无视扩展名一律拒绝**；
       → 否则仅当扩展名不属于「源码/文档白名单」时拒绝。
     （这条保证 `scripts/setup_credentials.py`、含 "token" 字样的 .md 不被误伤）
  B. 强加规则（专治 `git add -f` 绕过 .gitignore）
     · 被 `.gitignore` 忽略、却仍出现在待提交集合、且位于
       data/ raw_data/ out/ algorithms/out/ algorithms/data/ → 拒绝。
     （`v8/*.py` 这类**故意** `-f` 加入的白名单目录不受影响）
  C. 内容规则
     · 对非源码文件做高置信凭据模式扫描（GitHub PAT / zsxq_access_token / AWS / sk- 等）。

【用法】
  python scripts/secret_guard.py --staged           # pre-commit hook 调用
  python scripts/secret_guard.py --paths <f> [<f>]  # 脚本 add 前调用
  退出码 0 = 放行；1 = 命中（拒绝提交）；2 = 用法错误

【安装】
  python scripts/install_git_hooks.py   （幂等，双机各跑一次）
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 规则 A：凭据类文件名特征 ────────────────────────────────
CRED_WORDS = re.compile(
    r"(token|secret|cookie|credential|passwd|password|apikey|api[_-]?key"
    r"|private[_-]?key|access[_-]?key|gh_pat|\.jwt|session[_-]?id)",
    re.I,
)
# 源码/文档白名单：这些扩展名里出现上述词**不算**凭据
SRC_EXTS = (
    ".py", ".md", ".html", ".htm", ".yml", ".yaml", ".sh", ".js",
    ".css", ".ts", ".tsx", ".vue", ".rs", ".go", ".java",
)

# ── 规则 B：受保护目录（忽略文件被强加即拒）─────────────────
GUARDED_DIRS = (
    "data/", "raw_data/", "out/", "algorithms/out/", "algorithms/data/",
)

# ── 规则 C：内容级高置信凭据模式 ────────────────────────────
CONTENT_PATS = (
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "GitHub classic token"),
    (re.compile(r"gho_[A-Za-z0-9]{30,}"), "GitHub OAuth token"),
    (re.compile(r"\b\d{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                r"[0-9A-Fa-f]{12}_[0-9A-Fa-f]{12,}\b"), "zsxq_access_token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "OpenAI-style secret key"),
)


def _git(*args):
    """在仓库根执行 git（剥离 GIT_INDEX_FILE，避免命中隔离索引）。

    ⚠️ 必须带 `-c core.quotepath=false`：git 默认会把**非 ASCII 路径**（本仓交接
       文档大量使用中文名）转义成 `"\\351\\230\\277..."` 形式 —— 转义后扩展名会被
       识别成 `.md"`（带尾巴引号）而不在白名单里 ⇒ **中文名文档被误判为凭据**
       （2026-09-14 全量自检实测命中 1 例：`..._添加ZSXQ_TOKEN_Secret.md`）。
    """
    env = dict(os.environ)
    env.pop("GIT_INDEX_FILE", None)
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false"] + list(args), cwd=ROOT,
            capture_output=True, text=True, env=env, timeout=60,
        )
    except Exception:
        return None


def _is_ignored(path):
    r = _git("check-ignore", "-q", "--", path)
    return bool(r) and r.returncode == 0


def staged_files():
    """暂存区中本次将被提交的文件（新增/修改/改名）。"""
    r = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if not r:
        return []
    return [ln.strip().strip('"') for ln in r.stdout.splitlines() if ln.strip()]


def judge_path(path):
    """规则 A + B。返回拒绝原因字符串；None = 放行。"""
    p = path.replace("\\", "/")
    base = os.path.basename(p).lower()
    ext = os.path.splitext(base)[1].lower()

    if CRED_WORDS.search(base):
        if p.startswith("data/") or p.startswith("raw_data/"):
            return "A|数据目录下的凭据类文件名（%s）" % base
        if ext not in SRC_EXTS:
            return "A|凭据类文件名且非源码/文档（%s）" % base

    if any(p.startswith(d) for d in GUARDED_DIRS) and _is_ignored(p):
        return "B|被 .gitignore 忽略却仍被强加（git add -f 绕过）"

    return None


def _content_of(path, mode):
    if mode == "staged":
        r = _git("show", ":" + path)
        return r.stdout if (r and r.returncode == 0) else None
    try:
        with open(os.path.join(ROOT, path), "r", encoding="utf-8",
                  errors="replace") as fh:
            return fh.read()
    except Exception:
        return None


def judge_content(path, mode):
    """规则 C。返回拒绝原因；None = 放行。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in SRC_EXTS:
        return None  # 源码/文档不扫内容，避免误伤（如本文件自身）
    body = _content_of(path, mode)
    if not body:
        return None
    for pat, label in CONTENT_PATS:
        if pat.search(body):
            return "C|文件内容含高置信凭据（%s）" % label
    return None


def main():
    argv = sys.argv[1:]
    if "--staged" in argv:
        files, mode = staged_files(), "staged"
    elif "--paths" in argv:
        i = argv.index("--paths")
        files, mode = [f for f in argv[i + 1:] if f], "paths"
    else:
        print("用法: python scripts/secret_guard.py --staged | --paths <file> ...")
        return 2

    if not files:
        print("🛡 凭据闸门：待检查集合为空，放行")
        return 0

    bad = []
    for f in files:
        why = judge_path(f)
        if why is None:
            why = judge_content(f, mode)
        if why:
            bad.append((f, why))

    if not bad:
        print("🛡 凭据闸门：%d 个文件全部通过" % len(files))
        return 0

    print("")
    print("🚫🚫 凭据闸门拦截 —— 提交被拒绝 🚫🚫")
    print("")
    for f, why in bad:
        print("  %-58s %s" % (f[:58], why))
    print("")
    print("本仓是 public 仓库，凭据一旦进历史即视为泄漏（历史清洗需 force push，违反上线铁律）。")
    print("处置：")
    print("  1) git restore --staged <上述文件>      # 从暂存区摘掉，本地文件不受影响")
    print("  2) 确认它已被 .gitignore 覆盖           # git check-ignore -v <file>")
    print("  3) 若确属误报，用 SECRET_GUARD_ALLOW=1 显式放行（会记录到 stderr）")
    print("")
    return 1


if __name__ == "__main__":
    if os.environ.get("SECRET_GUARD_ALLOW") == "1":
        print("⚠️ SECRET_GUARD_ALLOW=1 —— 凭据闸门被显式旁路（请确认这是有意的）",
              file=sys.stderr)
        sys.exit(0)
    sys.exit(main())
