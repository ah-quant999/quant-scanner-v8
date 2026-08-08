# -*- coding: utf-8 -*-
"""通过 GitHub Contents API 直推单个文件（不触碰本地 git 工作区）。
用途：当工作区有他人未提交改动、无法安全 rebase 时，仅推送自己的文件。
一次性工具，用完即删。
"""
import base64
import json
import sys
import urllib.request
from pathlib import Path

REPO = "ah-quant999/quant-scanner-v8"
TOKEN = Path("E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt").read_text(encoding="utf-8").strip()
FILE = sys.argv[1]
MSG = sys.argv[2]

api = f"https://api.github.com/repos/{REPO}/contents/{urllib.parse.quote(FILE)}"
hdr = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "v8-watchdog",
}

# 1) 取远端当前 sha
sha = None
try:
    req = urllib.request.Request(api + "?ref=main", headers=hdr)
    with urllib.request.urlopen(req, timeout=60) as r:
        sha = json.load(r).get("sha")
    print(f"[INFO] remote sha = {sha[:10]}")
except Exception as e:
    print(f"[WARN] 取 sha 失败（可能是新文件）: {e}")

# 2) PUT
content = Path(FILE).read_bytes()
payload = {
    "message": MSG,
    "content": base64.b64encode(content).decode("ascii"),
    "branch": "main",
}
if sha:
    payload["sha"] = sha

req = urllib.request.Request(
    api, data=json.dumps(payload).encode("utf-8"), headers={**hdr, "Content-Type": "application/json"}, method="PUT"
)
with urllib.request.urlopen(req, timeout=120) as r:
    res = json.load(r)
print(f"[OK] 已推送 {FILE} -> commit {res['commit']['sha'][:10]}")
