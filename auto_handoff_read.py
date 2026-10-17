#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 交接文件读取器（2026-09-14 远端优先版）
==========================================
唯一交接目录：docs/ops/handover/
命名规范：YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md
输出摘要供 AI 自动化汇报。

🔴 三个刻意的设计（勿改回）：
  1. 只扫一个目录（旧版同时扫 handover + urgent，导致同一份被复制到多处才看得见）。
  2. 按【文件名倒序】取最新，不按 mtime —— 本仓库被坚果云实时同步，
     同步会重写 mtime，按 mtime 取"最新"会取错。
  3. 【2026-09-14 新增 · 远端优先】本机（阿狸咪机）工作树长期落后远端、且从不 pull，
     交接档由另一台机（小九机）+ CI 直接写远端 ⇒ 只读工作树会把**三天前的旧档当成今天**报
     （2026-09-14 实测：本地目录 184 份 / 远端 259 份，本地最新按名倒序仍是 09-11 15:05）。
     故改为默认读 `git fetch` 后的 FETCH_HEAD 树：
       列目录  git -c core.quotepath=false ls-tree -r --name-only FETCH_HEAD -- docs/ops/handover/
       读内容  git -c core.quotepath=false show FETCH_HEAD:docs/ops/handover/<name>
     只有 git/FETCH_HEAD 不可用时才回退工作树。**全程只读，绝不写仓库、不 pull、不动 index。**
"""
import os
import sys
import glob
import subprocess
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
HANDOVER_REL = "docs/ops/handover"
HANDOVER_DIR = BASE / HANDOVER_REL
SKIP_PREFIX = ("README", "_")


def _sh(args, timeout=60):
    """跑一条 git 命令，成功返回 stdout（str），失败/异常返回 None。只读。"""
    try:
        r = subprocess.run(["git"] + args, cwd=str(BASE), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode == 0:
            return r.stdout
    except Exception:
        return None
    return None


def _remote_list():
    """远端（FETCH_HEAD）交接目录全部文件名；不可用时返回 None。"""
    out = _sh(["-c", "core.quotepath=false", "ls-tree", "-r", "--name-only",
               "FETCH_HEAD", "--", HANDOVER_REL + "/"])
    if not out:
        return None
    names = [os.path.basename(l.strip()) for l in out.splitlines() if l.strip().endswith(".md")]
    names = [n for n in names if not n.startswith(SKIP_PREFIX)]
    return names or None


def _remote_head(name, lines):
    out = _sh(["-c", "core.quotepath=false", "show", f"FETCH_HEAD:{HANDOVER_REL}/{name}"])
    if out is None:
        return None
    return "".join(out.splitlines(keepends=True)[:lines])


def _local_list():
    files = [p for p in glob.glob(str(HANDOVER_DIR / "*.md"))
             if not os.path.basename(p).startswith(SKIP_PREFIX)]
    return [os.path.basename(p) for p in files]


def _local_head(name, lines):
    try:
        with open(HANDOVER_DIR / name, encoding="utf-8") as f:
            return "".join(f.readlines()[:lines])
    except Exception as e:
        return f"[读取失败: {e}]"


def _pick(n, urgent_only):
    """返回 [(name, head_text)]，按文件名倒序取前 n。远端优先，回退工作树。"""
    names = _remote_list()
    src_remote = names is not None
    if names is None:
        names = _local_list()
    if urgent_only:
        names = [x for x in names if "_URGENT_" in x]
    names.sort(reverse=True)
    names = names[:n]
    out = []
    for nm in names:
        txt = _remote_head(nm, 20) if src_remote else None
        if txt is None:
            txt = _local_head(nm, 20)
        out.append((nm, txt))
    return out, src_remote


def main():
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    tip = (_sh(["rev-parse", "--short", "FETCH_HEAD"]) or "").strip() or "未知"
    src = "远端 FETCH_HEAD"
    probe = _remote_list()
    if probe is None:
        src = "⚠️ 本地工作树（FETCH_HEAD 不可用，可能落后）"

    out = [f"# 交接读取 ({today})", "",
           f"目录: `{HANDOVER_REL}/`（唯一交接目录，按文件名 = 时间倒序）",
           f"数据来源: **{src}**" + (f" · tip=`{tip}`" if probe is not None else ""),
           f"总数: {len(probe) if probe is not None else len(_local_list())} 份", ""]

    # ① 今日新交接（本自动化真正要看的东西）
    all_names = probe if probe is not None else _local_list()
    today_names = sorted([n for n in all_names if n.startswith(today)], reverse=True)
    out.append(f"## 📅 今日（{today}）新交接：{len(today_names)} 份")
    if not today_names:
        out.append("- 无")
    else:
        for n in today_names:
            out.append(f"- {n}")
    out.append("")

    for title, urgent_only in (("最近交接文件（全部）", False),
                               ("最近紧急文件（*_URGENT_*）", True)):
        items, src_remote = _pick(5, urgent_only)
        out.append(f"## {title}")
        if not items:
            out.append("- 无")
        else:
            for nm, txt in items:
                out.append(f"- {nm}")
                out.append("```")
                out.append(txt)
                out.append("```")
        out.append("")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
