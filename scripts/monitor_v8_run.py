#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 run ID 监控 v8_algo_cloud 指定 run：完成後拉日志 + 取回 build_candidate_debug.json。

用法: python scripts/monitor_v8_run.py [RUN_ID]
默认监控 31340937182（本次诊断候选池 0 来源的那次）。
"""
import os, sys, time, json, base64, urllib.request, zipfile, io
from datetime import datetime, timezone

REPO = "ah-quant999/quant-scanner-v8"
BASE = f"https://api.github.com/repos/{REPO}"
ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(ROOT, "..", "data", ".github_pat.txt"), "rb").read().lstrip(b"\xef\xbb\xbf").decode("utf-8").strip()
RID = int(sys.argv[1]) if len(sys.argv) > 1 else 31340937182
OUT_LOG = os.path.join(ROOT, "..", "data", "_v8run_evidence.log")
OUT_DBG = os.path.join(ROOT, "..", "data", "_v8run_debug.json")


def api(path, binary=False):
    req = urllib.request.Request(BASE + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "User-Agent": "v", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else json.loads(r.read().decode("utf-8"))


def logs(rid):
    raw = api(f"/actions/runs/{rid}/logs", binary=True)
    z = zipfile.ZipFile(io.BytesIO(raw))
    full = ""
    for n in z.namelist():
        full += z.read(n).decode("utf-8", "replace") + "\n"
    return full


def main():
    lines = []
    lines.append(f"[{time.strftime('%H:%M:%S')}] 监控 run#{RID}")
    target = None
    for _ in range(100):  # 最多 ~100 分钟
        try:
            r = api(f"/actions/runs/{RID}")
        except Exception as e:
            lines.append(f"  [拉取失败] {e}")
            time.sleep(60)
            continue
        st = r["status"]
        concl = r.get("conclusion")
        lines.append(f"[{time.strftime('%H:%M:%S')}] status={st} concl={concl}")
        if st in ("completed", "failure", "cancelled", "timed_out"):
            target = r
            break
        time.sleep(60)

    if not target:
        lines.append("超时未等到完成，写盘退出")
        open(OUT_LOG, "w", encoding="utf-8").write("\n".join(lines))
        return

    rid = RID
    lines.append(f"\n=== run#{rid} 完成: status={target['status']} concl={target.get('conclusion')} ===")
    # 日志
    try:
        full = logs(rid)
        kws = ["maharo", "EOFError", "非交互", "跳过 maharo", "ValueError", "guanlan", "外资研投",
               "候选", "来源", "build_candidate", "Error", "Traceback", "candidate", "0 来源", "来源分布"]
        for kw in kws:
            ls = [l.strip() for l in full.splitlines() if kw.lower() in l.lower()]
            if ls:
                lines.append(f"\n--- {kw} ({len(ls)}) ---")
                for l in ls[:10]:
                    lines.append("   " + l[:200])
    except Exception as e:
        lines.append(f"日志拉取失败: {e}")

    # build_candidate_debug.json
    lines.append("\n=== 取回 raw_data/build_candidate_debug.json ===")
    time.sleep(25)
    for attempt in range(8):
        try:
            d = api("/contents/raw_data/build_candidate_debug.json")
            content = base64.b64decode(d["content"]).decode("utf-8")
            dbg = json.loads(content)
            lines.append(json.dumps(dbg, ensure_ascii=False, indent=2))
            open(OUT_DBG, "w", encoding="utf-8").write(json.dumps(dbg, ensure_ascii=False, indent=2))
            break
        except Exception as e:
            lines.append(f"  尝试 {attempt+1} 失败: {e}")
            time.sleep(20)

    open(OUT_LOG, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
