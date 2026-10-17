#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error
import zipfile
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", ".github_pat.txt")
OWNER = "ah-quant999"
REPO = "quant-scanner-v8"
WF = "v8_algo_cloud.yml"

def load_token():
    with open(TOKEN_FILE, "rb") as f:
        raw = f.read()
    # strip UTF-8 BOM / whitespace
    if raw[:3] == b'\xef\xbb\xbf':
        raw = raw[3:]
    tok = raw.decode("utf-8", "ignore").strip()
    return tok

def api(path, token):
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "v8-actions-monitor",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    token = load_token()
    if not token:
        print("TOKEN_EMPTY")
        sys.exit(1)
    print("== 最近 workflow runs ==")
    runs = api(f"/repos/{OWNER}/{REPO}/actions/workflows/{WF}/runs?per_page=5", token)
    items = runs.get("workflow_runs", [])
    if not items:
        print("没有找到运行记录")
        return
    for r in items:
        print(f"  run#{r['id']} | {r['status']} | {r.get('conclusion')} | {r['created_at']} | {r.get('event')}")
    latest = items[0]
    rid = latest["id"]
    print(f"\n== 最新 run#{rid} 详情 ==")
    print(f"  状态: {latest['status']}  结论: {latest.get('conclusion')}")
    print(f"  创建: {latest['created_at']}  更新: {latest['updated_at']}")
    print(f"  URL: {latest.get('html_url')}")

    if latest["status"] in ("queued", "in_progress"):
        print("\n>> 仍在运行中，稍后（用户输入 '再查'）再拉日志。")
        return

    # completed: fetch logs
    print("\n== 拉取日志并筛选 guanlan/maharo ==")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{rid}/logs",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "v8-actions-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        print(f"日志下载失败: {e.code} {e.reason}")
        return
    z = zipfile.ZipFile(io.BytesIO(data))
    hits = []
    for name in z.namelist():
        with z.open(name) as fh:
            for line in fh:
                try:
                    s = line.decode("utf-8", "ignore")
                except Exception:
                    continue
                low = s.lower()
                if any(k in low for k in ("guanlan", "maharo", "zsxq", "token invalid", "401", "cookie", "secret")):
                    hits.append(s.rstrip())
    if not hits:
        print("  日志中未发现 guanlan/maharo 相关行")
    else:
        for h in hits[:80]:
            print("  ", h)

if __name__ == "__main__":
    main()
