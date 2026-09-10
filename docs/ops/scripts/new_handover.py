#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_handover.py — 生成合规交接文件名（2026-09-10 主人令）
=========================================================
规范：YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md
唯一目录：docs/ops/handover/

为什么要有这个脚本：
  手写文件名会漂移（历史上有 HANDOVER_/URGENT_/纯日期/带 ? 等 8 种写法，
  还出现过同一份被复制到 3 个目录）。用脚本生成 = 名字与目录都不可漂移。

用法：
  python docs/ops/scripts/new_handover.py --from 阿狸咪 --to 小九 --topic "收盘核验回执"
  python docs/ops/scripts/new_handover.py --from 小九 --to 阿狸咪 --topic "回执" --urgent
  # 只打印不落盘：
  python docs/ops/scripts/new_handover.py --from 阿狸咪 --to 小九 --topic "x" --dry-run
"""
import re
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]          # 仓库根
HANDOVER_DIR = BASE / "docs" / "ops" / "handover"
CST = timezone(timedelta(hours=8))
BAD = re.compile(r'[?*:"<>|\\/]')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", required=True, help="发件机/人，如 阿狸咪 / 小九")
    ap.add_argument("--to", dest="to", required=True, help="收件机/人")
    ap.add_argument("--topic", required=True, help="主题（简明中文）")
    ap.add_argument("--urgent", action="store_true", help="紧急件，插入 URGENT 段")
    ap.add_argument("--dry-run", action="store_true", help="只打印路径，不创建文件")
    a = ap.parse_args()

    topic = BAD.sub("", a.topic).strip().replace(" ", "_")
    if not topic:
        sys.exit("ABORT: --topic 去非法字符后为空")
    if BAD.search(a.frm) or BAD.search(a.to):
        sys.exit("ABORT: --from/--to 含 Windows 非法字符 ?*:\"<>|\\/")

    now = datetime.now(CST)
    seg = [now.strftime("%Y-%m-%d"), now.strftime("%H%M")]
    if a.urgent:
        seg.append("URGENT")
    seg += [f"{a.frm}给{a.to}", topic]
    path = HANDOVER_DIR / ("_".join(seg) + ".md")

    if path.exists():
        sys.exit(f"ABORT: 已存在同名文件（1 分钟内重复？）: {path}")

    if a.dry_run:
        print(path)
        return 0

    HANDOVER_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {('🚨 URGENT｜' if a.urgent else 'HANDOVER｜')}{a.frm} → {a.to}"
        f"｜{now.strftime('%Y-%m-%d %H:%M')}｜{topic}\n\n"
        f"> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）\n\n"
        f"---\n\n## 一句话结论\n\n\n\n---\n\n## 正文\n\n",
        encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
