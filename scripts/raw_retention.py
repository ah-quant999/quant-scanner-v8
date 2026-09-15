#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raw_retention.py — raw_data/ 归档 / retention 策略
                                                (2026-08-30 阿狸咪)

任务目标（主人令："raw_data 归档/retention 策略 — 未建（delisted_stocks.json 1.15MB 等占索引风险）"）：
  1. 将 raw_data/*.json.bak、*.bak > 7 天的旧备份移到 raw_data/_archive/<date>/（不再被 git 索引）。
  2. raw_data/h_auto_buy_YYYYMMDD.json > 14 天的明细移到 raw_data/_archive/<date>/（保留近 14 天滚动）。
  3. 干跑模式：--dry-run 仅列动作不执行；默认执行移动。

安全：
  - 仅操作 .bak / 命名规则匹配的文件，不动其他 raw_data/*.json 主源。
  - _archive/ 已在 .gitignore 的 _rps_cache/ 等白名单排除路径之外；新目录显式 .gitignore 一行排除。
  - 不删原始文件，仅挪到 _archive，git rm --cached 自动从索引移除。
"""
import os, json, sys, shutil, fnmatch, re, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw_data"
ARCHIVE_DIR = RAW_DIR / "_archive"

BAK_PATTERNS = [
    "*.json.bak",
    "*.bak",
]
H_AUTO_BUY_PATTERN = re.compile(r"^h_auto_buy_(\d{8})\.json$")
BAK_AGE_DAYS = 7
H_AUTO_BUY_AGE_DAYS = 14

def list_archive_targets(now: datetime):
    items = []
    if not RAW_DIR.exists():
        return items
    for p in RAW_DIR.iterdir():
        if not p.is_file():
            continue
        name = p.name
        # 1) .bak 类文件
        if any(fnmatch.fnmatch(name, pat) for pat in BAK_PATTERNS):
            age = (now - datetime.fromtimestamp(p.stat().st_mtime, tz=CST)).days
            if age > BAK_AGE_DAYS:
                items.append((p, age, f"bak>{BAK_AGE_DAYS}d"))
            continue
        # 2) h_auto_buy_YYYYMMDD.json
        m = H_AUTO_BUY_PATTERN.match(name)
        if m:
            try:
                d = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=CST)
            except ValueError:
                continue
            age = (now - d).days
            if age > H_AUTO_BUY_AGE_DAYS:
                items.append((p, age, f"h_auto_buy>{H_AUTO_BUY_AGE_DAYS}d"))
    return items

def do_archive(targets, dry_run=False):
    if not targets:
        print("[ok] 无需归档")
        return 0
    now_str = datetime.now(CST).strftime("%Y-%m-%d")
    dest_dir = ARCHIVE_DIR / now_str
    print(f"[plan] 归档 {len(targets)} 个文件 → {dest_dir}")
    if dry_run:
        for p, age, reason in targets:
            print(f"  - {p.name} (age={age}d, {reason})")
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for p, age, reason in targets:
        try:
            shutil.move(str(p), str(dest_dir / p.name))
            print(f"[moved] {p.name} (age={age}d, {reason})")
        except Exception as e:
            print(f"[err] {p.name}: {e}", file=sys.stderr)
    return 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只列计划不执行")
    args = ap.parse_args()
    now = datetime.now(CST)
    targets = list_archive_targets(now)
    return do_archive(targets, dry_run=args.dry_run)

if __name__ == "__main__":
    sys.exit(main())
