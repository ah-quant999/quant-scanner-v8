#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控本次云端 run：完成后取回 build_candidate_debug.json 真实证据 + mahoro 日志。"""
import os, time, json, urllib.request, urllib.error, zipfile, io

REPO = "ah-quant999/quant-scanner-v8"
BASE = f"https://api.github.com/repos/{REPO}"
ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(ROOT, "..", "data", ".github_pat.txt"), "rb").read().lstrip(b"\xef\xbb\xbf").decode("utf-8").strip()

def api(path, binary=False):
    req = urllib.request.Request(BASE + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "User-Agent": "v", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else json.loads(r.read().decode("utf-8"))

def latest_run():
    runs = api("/actions/workflows/v8_algo_cloud.yml/runs?per_page=1")
    return runs["workflow_runs"][0]

def main():
    print(f"[{time.strftime('%H:%M:%S')}] 等待最新 run 完成...", flush=True)
    run = latest_run()
    print(f"  run#{run['id']} status={run['status']}", flush=True)
    while True:
        run = latest_run()
        st = run["status"]
        print(f"[{time.strftime('%H:%M:%S')}] status={st} concl={run.get('conclusion')}", flush=True)
        if st in ("completed", "failure", "cancelled", "timed_out"):
            break
        time.sleep(60)

    rid = run["id"]
    print(f"\n=== run#{rid} 完成，拉取日志 ===", flush=True)
    try:
        raw = api(f"/actions/runs/{rid}/logs", binary=True)
        z = zipfile.ZipFile(io.BytesIO(raw))
        full = ""
        for n in z.namelist():
            full += z.read(n).decode("utf-8", "replace") + "\n"
        for kw in ["maharo", "EOFError", "非交互", "跳过 mahoro", "✅ ok |   结果", "ValueError"]:
            ls = [l.strip() for l in full.splitlines() if kw.lower() in l.lower()]
            if ls:
                print(f"--- {kw} ({len(ls)}) ---")
                for l in ls[:6]:
                    print("   ", l[:150])
    except Exception as e:
        print("日志拉取失败:", e)

    print(f"\n=== 取回 raw_data/build_candidate_debug.json ===", flush=True)
    # 等几秒让 api_push 提交可见
    time.sleep(20)
    for attempt in range(5):
        try:
            d = api("/contents/raw_data/build_candidate_debug.json")
            content = __import__("base64").b64decode(d["content"]).decode("utf-8")
            dbg = json.loads(content)
            print(json.dumps(dbg, ensure_ascii=False, indent=2))
            break
        except Exception as e:
            print(f"  尝试 {attempt+1}: {str(e)[:100]}")
            time.sleep(20)

if __name__ == "__main__":
    main()
