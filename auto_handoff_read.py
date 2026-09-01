#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 交接文件读取器（去 v6 化替代版）
读取 docs/ops/handover/ 与 docs/ops/urgent/ 下的最新交接/紧急文件，
输出摘要供 AI 自动化汇报。
"""
import os
import sys
import glob
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
HANDOVER_DIR = BASE / "docs" / "ops" / "handover"
URGENT_DIR = BASE / "docs" / "ops" / "urgent"

def _recent_files(d, pattern, n=3):
    files = sorted(glob.glob(str(d / pattern)), key=os.path.getmtime, reverse=True)
    return files[:n]

def _read_head(path, lines=30):
    try:
        with open(path, encoding="utf-8") as f:
            return "".join(f.readlines()[:lines])
    except Exception as e:
        return f"[读取失败: {e}]"

def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out = []
    out.append(f"# 交接读取 ({today})")
    out.append("")

    handover = _recent_files(HANDOVER_DIR, "HANDOVER_*.md", 5)
    urgent = _recent_files(URGENT_DIR, "URGENT_*.md", 5)

    out.append("## 最近交接文件")
    if not handover:
        out.append("- 无")
    else:
        for p in handover:
            out.append(f"- {os.path.basename(p)}")
            out.append("```")
            out.append(_read_head(p, 20))
            out.append("```")

    out.append("")
    out.append("## 最近紧急文件")
    if not urgent:
        out.append("- 无")
    else:
        for p in urgent:
            out.append(f"- {os.path.basename(p)}")
            out.append("```")
            out.append(_read_head(p, 20))
            out.append("```")

    print("\n".join(out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
