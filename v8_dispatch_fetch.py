#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_dispatch_fetch.py — 经 GitHub REST API 主动派发 cn_fetch workflow
（绕过 GitHub Actions 不可靠的 on.schedule 定时器，下午/收盘档常漏触发）

用法:
    python v8_dispatch_fetch.py                 # 默认 all（全量兜底）
    python v8_dispatch_fetch.py intraday        # 盘中刷新
    python v8_dispatch_fetch.py post_close       # 收盘数据 + 龙虎榜回填
    python v8_dispatch_fetch.py premarket        # 盘前

依赖: E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt （OAuth token，不入库）
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

REPO = "ah-quant999/quant-scanner-v8"
WF_ID = 324135267  # v8_cn_fetch workflow id
TOKEN_PATH = "E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"
VALID = {"premarket", "intraday", "post_close", "all"}


def load_token():
    try:
        return open(TOKEN_PATH, encoding="utf-8").read().strip()
    except Exception as e:
        print(f"[FATAL] 读取 token 失败: {e}")
        sys.exit(1)


def dispatch(category):
    token = load_token()
    if category not in VALID:
        print(f"[FATAL] 非法 category={category!r}，可选: {sorted(VALID)}")
        sys.exit(1)
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WF_ID}/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"category": category}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            now = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
            print(f"[{now}] ✅ 已派发 cn_fetch category={category} (HTTP {r.status})")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ 派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        return False


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    cat = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = dispatch(cat)
    sys.exit(0 if ok else 1)
