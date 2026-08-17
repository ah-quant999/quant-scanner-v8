#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_from_origin.py — 主站（云端 origin/main）→ 本地工作树 增量同步

背景（2026-08-17 22:34 主人发现）：本地 git main 落后云端 origin main 1 小时，
主人看到的页面是云端 CDN 真版本（如 AVG_PRICE 29.391），本地仓库却停在旧版本。
根因：本机 Windows 网络封 git 协议（github.com:443 经常 timeout / connection reset），
但 Contents API（HTTPS 走 api.github.com）稳定可用。

用途：
  1. 每晚 19:30 交接检查前同步（主人令 2026-08-17 23:14）
  2. 主人白天任何时刻手动跑（如部署前先拉最新）
  3. 云端 algo/cn_fetch 跑完后，本地可拉最新产物

用法：
  python scripts/sync_from_origin.py [--only data] [--dry-run]

输出：
  · 从云端 main 拉取 data/*.js + index.html + 关键脚本，覆盖本地
  · 打印每个文件的云端 sha + 是否变化
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "ah-quant999/quant-scanner-v8"
# 🔴 PAT 不硬编码在仓库（GitHub secret scan 拦 409）—— 从环境变量/本地文件读取
# 候选顺序：V8_GITHUB_TOKEN / GH_TOKEN 环境变量 → data/.github_pat.txt → ~/.workbuddy/v8_gh_token.txt
def _load_token():
    for env_name in ("V8_GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v.strip()
    for cand in (ROOT / "data" / ".github_pat.txt",
                 Path.home() / ".workbuddy" / "v8_gh_token.txt"):
        if cand.exists():
            t = cand.read_text(encoding="utf-8").strip().lstrip("\ufeff")
            if t:
                return t
    return None

TOKEN = _load_token()
if not TOKEN:
    print("❌ 未找到 GitHub PAT（环境变量 V8_GITHUB_TOKEN/GH_TOKEN 或 data/.github_pat.txt）")
    sys.exit(2)
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
           "User-Agent": "v8-sync-from-origin"}

# 同步清单：data/*.js 全量 + index.html + 关键 py（保护 .workbuddy/memory 本地优先，不拉）
FILES = [
    "index.html",
    # 核心算法/工作流（避免本地改坏被覆盖：先拉云端权威版本）
    "v8_health_check.py",
    "cloud_fetch_v8.py",
    "update_v8.py",
    "api_push_raw.py",
    "algorithms/run_algorithms.py",
    "algorithms/calc_etf_intraday.py",
    "algorithms/calc_commodity_elasticity.py",
    "algorithms/fetch_sector_rs.py",
    "algorithms/gen_top5_track.py",
    "algorithms/gen_stock_stop.py",
    "algorithms/stop_target_logic.py",
    "algorithms/build_candidate_pool.py",
    "algorithms/stage_to_raw.py",
]


def fetch_content(path):
    """经 Contents API 拉云端 main 某文件内容 + sha。"""
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref=main"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    content = base64.b64decode(d.get("content", "")).decode("utf-8")
    return content, d.get("sha", "")


def sync(only_data=False, dry_run=False):
    changed = []
    unchanged = 0
    errs = []

    # data/*.js 全量清单（本地已有的文件名 → 拉云端同名）
    data_files = sorted(p.name for p in (ROOT / "data").glob("*.js"))
    files = [f"data/{f}" for f in data_files]
    if not only_data:
        files += FILES

    print(f"🧲 主站 → 本地同步 共 {len(files)} 个文件 (only_data={only_data})")
    for i, f in enumerate(files, 1):
        local = ROOT / f
        try:
            content, sha = fetch_content(f)
        except Exception as e:
            errs.append(f"❌ {f}: {str(e)[:80]}")
            continue
        if local.exists():
            local_sha = hashlib.sha1(local.read_bytes()).hexdigest()[:10]
            remote_sha = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
            if local_sha == remote_sha:
                unchanged += 1
                continue
        if dry_run:
            print(f"  ⏩ {f}: 将更新 ({len(content):,}B)")
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(content, encoding="utf-8", newline="")
        changed.append(f)
        print(f"  ✅ {f} ({len(content):,}B, sha={sha[:8]})")

    print(f"\n📊 完成: 更新 {len(changed)} / 未变 {unchanged} / 失败 {len(errs)}")
    for e in errs:
        print("  " + e)
    if changed:
        print(f"\n⚠️ 本地有 {len(changed)} 个文件被主站覆盖——如需保留本地改动请先 git stash/commit")
    return 0 if not errs else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="主站 → 本地同步")
    ap.add_argument("--only-data", action="store_true", help="只同步 data/*.js")
    ap.add_argument("--dry-run", action="store_true", help="只列差异不写入")
    args = ap.parse_args()
    sys.exit(sync(only_data=args.only_data, dry_run=args.dry_run))
