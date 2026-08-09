#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控 maharo_refresh.yml 最新 run：完成后拉日志确认发码/验证结果。"""
import os, time, json, base64, urllib.request, urllib.error, zipfile, io
from datetime import datetime, timezone

REPO = "ah-quant999/quant-scanner-v8"
BASE = f"https://api.github.com/repos/{REPO}"
WF = "maharo_refresh.yml"
ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(ROOT, "..", "data", ".github_pat.txt"), "rb").read().lstrip(b"\xef\xbb\xbf").decode("utf-8").strip()


def api(path, binary=False):
    req = urllib.request.Request(BASE + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "User-Agent": "v", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else json.loads(r.read().decode("utf-8"))


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def main():
    t0 = time.time()
    target = None
    for _ in range(30):
        try:
            runs = api(f"/actions/workflows/{WF}/runs?per_page=5")["workflow_runs"]
        except Exception as e:
            print("拉取失败:", e, flush=True)
            time.sleep(10)
            continue
        for r in runs:
            if parse_iso(r["created_at"]) >= t0 - 2:
                target = r
                break
        if target:
            break
        time.sleep(10)
    if not target:
        print("超时未等到新 run", flush=True)
        return

    rid = target["id"]
    print(f"锁定 run#{rid} (created={target['created_at']})", flush=True)
    while True:
        r = api(f"/actions/runs/{rid}")
        st = r["status"]
        print(f"[{time.strftime('%H:%M:%S')}] status={st} concl={r.get('conclusion')}", flush=True)
        if st in ("completed", "failure", "cancelled", "timed_out"):
            break
        time.sleep(30)

    print("\n=== 拉取日志 ===", flush=True)
    try:
        raw = api(f"/actions/runs/{rid}/logs", binary=True)
        z = zipfile.ZipFile(io.BytesIO(raw))
        full = ""
        for n in z.namelist():
            full += z.read(n).decode("utf-8", "replace") + "\n"
        for kw in ["发码", "send-code", "验证码已发送", "登录成功", "新 cookie", "verify", "失败", "Error", "Traceback"]:
            ls = [l.strip() for l in full.splitlines() if kw in l]
            if ls:
                print(f"--- {kw} ({len(ls)}) ---")
                for l in ls[:8]:
                    print("   ", l[:160])
    except Exception as e:
        print("日志拉取失败:", e)


if __name__ == "__main__":
    main()
