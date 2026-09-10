#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 交接文件读取器（2026-09-10 统一目录版）
==========================================
唯一交接目录：docs/ops/handover/
命名规范：YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md
输出摘要供 AI 自动化汇报。

🔴 两个刻意的设计（勿改回）：
  1. 只扫一个目录（旧版同时扫 handover + urgent，导致同一份被复制到多处才看得见）。
  2. 按【文件名倒序】取最新，不按 mtime —— 本仓库被坚果云实时同步，
     同步会重写 mtime，按 mtime 取"最新"会取错。
"""
import os
import sys
import glob
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
HANDOVER_DIR = BASE / "docs" / "ops" / "handover"


def _recent(n=5, urgent_only=False):
    """按文件名倒序（= 时间倒序）取最近 n 份；跳过 README/_ 前缀的非交接文件。"""
    pat = "*_URGENT_*.md" if urgent_only else "*.md"
    files = [p for p in glob.glob(str(HANDOVER_DIR / pat))
             if not os.path.basename(p).startswith(("README", "_"))]
    files.sort(key=os.path.basename, reverse=True)
    return files[:n]


def _read_head(path, lines=20):
    try:
        with open(path, encoding="utf-8") as f:
            return "".join(f.readlines()[:lines])
    except Exception as e:
        return f"[读取失败: {e}]"


def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out = [f"# 交接读取 ({today})", "",
           "目录: `docs/ops/handover/`（唯一交接目录，按文件名 = 时间倒序）", ""]

    for title, urgent_only in (("最近交接文件（全部）", False),
                               ("最近紧急文件（*_URGENT_*）", True)):
        files = _recent(5, urgent_only)
        out.append(f"## {title}")
        if not files:
            out.append("- 无")
        else:
            for p in files:
                out.append(f"- {os.path.basename(p)}")
                out.append("```")
                out.append(_read_head(p, 20))
                out.append("```")
        out.append("")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
