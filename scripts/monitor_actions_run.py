#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error
import zipfile
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", ".github_pat.txt")
OWNER = "ah-quant999"
REPO = "quant-scanner-v8"
WF = "v8_algo_cloud.yml"
RUN_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None
POLL = 60

def load_token():
    with open(TOKEN_FILE, "rb") as f:
        raw = f.read()
    if raw[:3] == b'\xef\xbb\xbf':
        raw = raw[3:]
    return raw.decode("utf-8", "ignore").strip()

def api_get(path, token):
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "v8-actions-monitor"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    token = load_token()
    rid = RUN_ID
    if rid is None:
        # 默认取最新一次 workflow_dispatch 或 schedule 的 run
        runs = api_get(f"/repos/{OWNER}/{REPO}/actions/workflows/{WF}/runs?per_page=1", token)
        rid = runs["workflow_runs"][0]["id"]
        print(f"[{time.strftime('%H:%M:%S')}] 未指定 run id，自动取最新 run#{rid}", flush=True)
    print(f"[{time.strftime('%H:%M:%S')}] 开始监控 run#{rid}", flush=True)
    while True:
        try:
            run = api_get(f"/repos/{OWNER}/{REPO}/actions/runs/{rid}", token)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 查询失败: {e}", flush=True)
            time.sleep(POLL)
            continue
        status = run["status"]
        concl = run.get("conclusion")
        print(f"[{time.strftime('%H:%M:%S')}] status={status} conclusion={concl}", flush=True)
        if status in ("completed", "failure", "cancelled", "timed_out"):
            break
        time.sleep(POLL)

    if concl != "success":
        print(f"\n>> 运行结束但结论为 {concl}，可能不是成功。仍尝试拉日志。", flush=True)

    print("\n== 拉取日志并筛选 guanlan/maharo ==")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{rid}/logs",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "v8-actions-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        print(f"日志下载失败: {e.code} {e.reason}", flush=True)
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
                if any(k in low for k in ("guanlan", "maharo", "zsxq",
                                          "token invalid", "401", "cookie",
                                          "secret", "error", "失败", "成功")):
                    hits.append(s.rstrip())
    if not hits:
        print("  日志中未发现 guanlan/maharo 相关行", flush=True)
    else:
        for h in hits[:120]:
            print("  ", h, flush=True)
    print("\n[DONE]", flush=True)

if __name__ == "__main__":
    main()
