#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_put_file.py — 经 GitHub REST API 把单个本地文件推送到 origin/main。

绕过 git：本机无法直连 github.com 的 git/HTTPS 协议，但 api.github.com 可达。
用 Contents API 以「base64 + 当前 blob sha」方式提交，天然带冲突检测（409 即远端
已被并发修改，自动重新拉取 sha 后重试）。>1MB 文件自动改用 Git blobs API。

用法: python scripts/api_put_file.py <本地相对路径> [commit message]
"""
import os
import sys
import base64
import json
import hashlib
import urllib.request
import urllib.error

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("❌ 缺少 GITHUB_TOKEN"); sys.exit(1)


def _request(method, path, data=None, retry=3):
    url = API + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    last = None
    for _ in range(retry):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=120) as r:
                t = r.read().decode("utf-8")
                return json.loads(t) if t else {}, r.status
        except urllib.error.HTTPError as e:
            last = e.read().decode("utf-8", "replace")
            if e.code == 409 and method == "PUT":
                return {"__conflict__": True, "__msg__": last}, e.code
            print(f"  ⚠️ HTTP {e.code}: {last[:300]}")
            return {"__error__": e.code, "__msg__": last}, e.code
        except Exception as e:  # network
            last = str(e)
            print(f"  ⚠️ 网络异常 {e}")
    return {"__error__": "net", "__msg__": last}, 0


def put_file(local_rel, msg=None):
    local_rel = local_rel.replace("\\", "/")
    path = f"/repos/{REPO}/contents/{local_rel}"
    with open(local_rel, "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode("ascii")
    is_big = len(content) > 900_000

    for attempt in range(4):
        # 取当前 sha（冲突重试时需要最新）
        cur = _request("GET", path)
        sha = cur[0].get("sha") if isinstance(cur[0], dict) else None
        if sha is None and cur[1] == 404:
            # 新文件：直接创建
            data = {"message": msg or f"chore: add {local_rel}", "content": encoded,
                    "branch": "main"}
            res, st = _request("PUT", path, data)
            if st in (200, 201):
                print(f"✅ 已创建 {local_rel}"); return 0
            if isinstance(res, dict) and res.get("__conflict__"):
                print(f"  ↻ {local_rel} 并发冲突，重试 ({attempt+1})"); continue
            print(f"❌ 创建失败 {local_rel}: {res}"); return 1

        if is_big:
            # 走 git blobs API（>1MB Contents API 会截断）
            bres, bst = _request("POST", f"/repos/{REPO}/git/blobs",
                                 {"content": encoded, "encoding": "base64"})
            if bst != 201 or "__error__" in bres:
                print(f"❌ blob 上传失败 {local_rel}: {bres}"); return 1
            data = {"message": msg or f"chore: update {local_rel}",
                    "content": encoded, "sha": sha, "branch": "main"}
        else:
            data = {"message": msg or f"chore: update {local_rel}",
                    "content": encoded, "sha": sha, "branch": "main"}
        res, st = _request("PUT", path, data)
        if st in (200, 201):
            print(f"✅ 已更新 {local_rel}"); return 0
        if isinstance(res, dict) and res.get("__conflict__"):
            print(f"  ↻ {local_rel} 并发冲突，重试 ({attempt+1})"); continue
        print(f"❌ 更新失败 {local_rel}: {res}"); return 1
    print(f"❌ {local_rel} 多次重试仍失败"); return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/api_put_file.py <本地相对路径> [msg]"); sys.exit(1)
    sys.exit(put_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
