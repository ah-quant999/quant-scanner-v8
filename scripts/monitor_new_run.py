#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等待本次新触发的 v8_algo_cloud run 出现并完成，再取回调试证据。

用法: python scripts/monitor_new_run.py
"""
import os, time, json, base64, urllib.request, urllib.error, zipfile, io
from datetime import datetime, timezone

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


def parse_iso(s):
    # 2026-08-09T23:29:13Z -> epoch
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def main():
    t0 = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] 等待新触发的 run 出现（已记录 t0={t0:.0f}）...", flush=True)
    target = None
    for _ in range(40):  # 最多等 ~6.5 分钟让 run 创建
        try:
            runs = api("/actions/workflows/v8_algo_cloud.yml/runs?per_page=5")["workflow_runs"]
        except Exception as e:
            print("  拉取 runs 失败:", e, flush=True)
            time.sleep(10)
            continue
        # 找 created_at 明显晚于 t0 的 run（新触发的）
        for r in runs:
            if parse_iso(r["created_at"]) >= t0 - 2:
                target = r
                break
        if target:
            break
        time.sleep(10)
    if not target:
        print("超时未等到新 run，退出", flush=True)
        return

    rid = target["id"]
    print(f"[{time.strftime('%H:%M:%S')}] 锁定 run#{rid} (created_at={target['created_at']})", flush=True)
    while True:
        r = api(f"/actions/runs/{rid}")
        st = r["status"]
        print(f"[{time.strftime('%H:%M:%S')}] status={st} concl={r.get('conclusion')}", flush=True)
        if st in ("completed", "failure", "cancelled", "timed_out"):
            break
        time.sleep(60)

    print(f"\n=== run#{rid} 完成，拉取日志 ===", flush=True)
    try:
        raw = api(f"/actions/runs/{rid}/logs", binary=True)
        z = zipfile.ZipFile(io.BytesIO(raw))
        full = ""
        for n in z.namelist():
            full += z.read(n).decode("utf-8", "replace") + "\n"
        for kw in ["maharo", "EOFError", "非交互", "跳过 maharo", "ValueError", "guanlan", "外资研投", "候选股池构建", "来源分布"]:
            ls = [l.strip() for l in full.splitlines() if kw.lower() in l.lower()]
            if ls:
                print(f"--- {kw} ({len(ls)}) ---")
                for l in ls[:8]:
                    print("   ", l[:160])
    except Exception as e:
        print("日志拉取失败:", e)

    print(f"\n=== 取回 raw_data/build_candidate_debug.json ===", flush=True)
    time.sleep(25)
    for attempt in range(6):
        try:
            d = api("/contents/raw_data/build_candidate_debug.json")
            content = base64.b64decode(d["content"]).decode("utf-8")
            dbg = json.loads(content)
            print(json.dumps(dbg, ensure_ascii=False, indent=2))
            break
        except Exception as e:
            print(f"  尝试 {attempt+1} 失败: {e}", flush=True)
            time.sleep(20)


if __name__ == "__main__":
    main()
