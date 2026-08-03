#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 云端管线看门狗（只监督，不部署）
- 检查 self-hosted runner 在线/忙碌状态
- 检查 v8_cn_fetch / v8_build_deploy 最近运行状态
- 检查 raw_data 最新提交是否陈旧
- 检查站点 HTTP 200
- 把异常写入 _v8_watchdog.log，供人工/自动化追踪
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = "ah-quant999/quant-scanner-v8"
SITE_URL = "https://ah-quant999.github.io/quant-scanner-v8/"
CN_WORKFLOW_NAME = "🇨🇳 v8 中国数据抓取(cn)"
BD_WORKFLOW_NAME = "☁️ v8 构建部署(云端ubuntu)"

# 尝试从多个位置读取 token（本地文件优先，不落入仓库）
def _load_token():
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    candidates = [
        Path("E:/workspace/stock-scanner/.workbuddy/v8_gh_token.txt"),
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None

TOKEN = _load_token()
if not TOKEN:
    print("[FATAL] 找不到 GitHub token，请设置 V8_GITHUB_TOKEN 或 ~/.workbuddy/v8_gh_token.txt")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def utc_to_cst(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone(timedelta(hours=8)))


def fmt_age(minutes):
    if minutes is None:
        return "N/A"
    if minutes < 60:
        return f"{int(minutes)}m"
    return f"{minutes/60:.1f}h"


def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}


def check_runner():
    d = api_get(f"https://api.github.com/repos/{REPO}/actions/runners")
    if "__error__" in d:
        return False, f"runner API error {d['__error__']}"
    runners = d.get("runners", [])
    if not runners:
        return False, "无 self-hosted runner"
    parts = []
    ok = True
    for r in runners:
        online = r.get("status") == "online"
        busy = r.get("busy", False)
        parts.append(f"{r['name']}: online={online}, busy={busy}")
        if not online:
            ok = False
    return ok, "; ".join(parts)


def latest_workflow_run(name):
    # list workflows then find by name
    wfs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows")
    if "__error__" in wfs:
        return None, f"workflows API error {wfs['__error__']}"
    wf_id = None
    for w in wfs.get("workflows", []):
        if w["name"] == name:
            wf_id = w["id"]
            break
    if not wf_id:
        return None, f"找不到 workflow '{name}'"
    runs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_id}/runs?per_page=1")
    if "__error__" in runs:
        return None, f"runs API error {runs['__error__']}"
    items = runs.get("workflow_runs", [])
    if not items:
        return None, "无运行记录"
    return items[0], None


def check_workflow(name, label, max_age_min=None):
    run, err = latest_workflow_run(name)
    if err:
        return False, err
    status = run["status"]
    con = run.get("conclusion")
    created = utc_to_cst(run["created_at"])
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    age_min = (now_cst - created).total_seconds() / 60
    created_str = created.strftime("%m-%d %H:%M") if created else "?"
    ok = status == "completed" and con == "success"
    if max_age_min and age_min > max_age_min:
        ok = False
    detail = f"{label} {status}/{con} @ {created_str} (age {fmt_age(age_min)})"
    return ok, detail


def check_raw_data_stale(threshold_min=90):
    commits = api_get(f"https://api.github.com/repos/{REPO}/commits?path=raw_data&per_page=1")
    if "__error__" in commits:
        return False, f"commits API error {commits['__error__']}"
    if not commits:
        return False, "raw_data 无提交记录"
    c = commits[0]
    dt = utc_to_cst(c["commit"]["author"]["date"])
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    age_min = (now_cst - dt).total_seconds() / 60
    ok = age_min <= threshold_min
    detail = f"raw_data last commit {dt.strftime('%m-%d %H:%M')} (age {fmt_age(age_min)}, threshold {fmt_age(threshold_min)})"
    return ok, detail


def check_site():
    try:
        req = urllib.request.Request(SITE_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
            return code == 200, f"site HTTP {code}"
    except Exception as e:
        return False, f"site unreachable: {e}"


def main():
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    results = []

    ok, msg = check_runner()
    results.append(("runner", ok, msg))

    ok, msg = check_workflow(CN_WORKFLOW_NAME, "cn_fetch", max_age_min=120)
    results.append(("cn_fetch", ok, msg))

    ok, msg = check_workflow(BD_WORKFLOW_NAME, "build_deploy", max_age_min=120)
    results.append(("build_deploy", ok, msg))

    ok, msg = check_raw_data_stale(threshold_min=90)
    results.append(("raw_data_fresh", ok, msg))

    ok, msg = check_site()
    results.append(("site", ok, msg))

    overall = all(ok for _, ok, _ in results)
    flag = "OK" if overall else "ALERT"

    lines = [f"{now} | {flag} | watchdog check"]
    for name, ok, msg in results:
        status = "OK" if ok else "FAIL"
        lines.append(f"  [{status}] {name}: {msg}")

    log_text = "\n".join(lines) + "\n"
    log_path = Path("_v8_watchdog.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_text)

    print(log_text, end="")
    sys.exit(0 if overall else 2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
