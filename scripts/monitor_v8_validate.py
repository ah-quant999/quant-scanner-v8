#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控最新 v8_algo_cloud run 完成，然后从 main 分支拉取 raw_data/candidate.json
   校验候选池来源分布（外资研投/maharo研报 应 > 0），落盘证据。"""
import os, json, time, urllib.request, urllib.error
from datetime import datetime, timezone

REPO = "ah-quant999/quant-scanner-v8"
BASE = f"https://api.github.com/repos/{REPO}"
ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(ROOT, "..", "data", ".github_pat.txt"), "rb").read().lstrip(b"\xef\xbb\xbf").decode().strip()
EVID = os.path.join(ROOT, "..", "data", "_v8validate.log")

def api(p, binary=False):
    req = urllib.request.Request(BASE + p, headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
        "User-Agent": "v", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
        return b if binary else json.loads(b.decode())

def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()

def log(*a):
    line = " ".join(str(x) for x in a)
    with open(EVID, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {line}\n")
    print(line, flush=True)

# 锁定已触发的 run（dispatch 与 monitor 启动存在时间差，用固定 run id 而非“新 run”过滤）
import sys
rid = int(sys.argv[1]) if len(sys.argv) > 1 else 31342871642
target = api(f"/actions/runs/{rid}")
log(f"锁定 run#{rid} created={target['created_at']} head={target.get('head_sha','')[:8]}")

for _ in range(180):  # 最多 60 分钟（完整算法链 20~45 分钟）
    r = api(f"/actions/runs/{rid}")
    if r["status"] in ("completed", "failure", "cancelled", "timed_out"):
        break
    time.sleep(20)

log(f"status={r['status']} concl={r.get('conclusion')}")

# 从 main 分支拉取最新 candidate.json 校验来源
try:
    c = api("/contents/raw_data/candidate.json?ref=main")
    import base64
    raw = base64.b64decode(c["content"]).decode("utf-8")
    data = json.loads(raw)
    dist = data.get("source_dist", {})
    total = data.get("total")
    log(f"candidate.json total={total}")
    log(f"source_dist={json.dumps(dist, ensure_ascii=False)}")
    # 关键来源（2026-08-10: 外资研投研报已合并入外资研投，不再单独校验）
    for key in ["外资研投", "maharo研报", "maharo"]:
        found = {k: v for k, v in dist.items() if key in k}
        if found:
            log(f"  ✅ {key}: {found}")
        else:
            log(f"  ⚠️ {key}: 未出现在 source_dist")
except Exception as e:
    log("拉取 candidate.json 失败:", e)
PY