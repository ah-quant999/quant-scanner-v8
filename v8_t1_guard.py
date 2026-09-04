#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_t1_guard.py — 周六 T+1 兜底检查与自愈（v8 去 v6 化版）
==========================================================
周六 09:30 主检查 + 周一 07:00 盘前兜底：
检查 guard_v8_freshness.py 输出，若 post_close 类关键文件 update_time 早于
最近一个周六 00:00，则判定 T+1 失败 → dispatch 云端补跑。

用法:
  python v8_t1_guard.py              # 检查 + 必要时 dispatch
  python v8_t1_guard.py --dry-run    # 仅打印判定
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = "ah-quant999/quant-scanner-v8"
STATE_FILE = BASE / ".t1_heal_state.json"

#  post_close 算法链产物，T+1 应在周六补全
T1_FILES = [
    "data/CANDIDATE.js",
    "data/GOLD_POOL.js",
    "data/LHB_DATA.js",
    "data/INST_TRADE.js",
    "data/TRIPLE_CONSENSUS.js",
    # 2026-09-04 主人令收尾：COCKPIT_TIER_RECOMMEND/COCKPIT_ADVICE 已删（驾驶舱模块下线）
    "data/SH_FIB.js",
    "data/SZ_FIB.js",
    "data/NT_DATA.js",
    "data/LHB_HISTORY.js",
]


def _load_token():
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    for p in [
        BASE / ".workbuddy" / "v8_gh_token.txt",
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def run_freshness():
    try:
        r = subprocess.run(
            [sys.executable, "guard_v8_freshness.py"],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 1, str(e)


def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def last_saturday_midnight():
    now = datetime.now()
    days_since_sat = (now.weekday() - 5) % 7
    return (now - timedelta(days=days_since_sat)).replace(hour=0, minute=0, second=0, microsecond=0)


def extract_update_time(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        # 优先 update_time/calc_time/gen_time；无则用 date（日频数据）
        for key in ["update_time", "calc_time", "gen_time", "date"]:
            m = __import__("re").search(rf'"{key}"\s*:\s*"([^"]+)"', text)
            if m:
                ts = m.group(1).strip()
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(ts[:19] if ':' in ts else ts[:10], fmt)
                    except ValueError:
                        continue
    except Exception:
        pass
    return None


def t1_failed_files():
    deadline = last_saturday_midnight()
    failed = []
    for rel in T1_FILES:
        p = BASE / rel
        ts = extract_update_time(p)
        if not ts:
            failed.append((rel, "无时间戳/文件缺失"))
        elif ts < deadline:
            failed.append((rel, ts.strftime("%Y-%m-%d %H:%M")))
    return failed


def dispatch_workflow(wf_name, inputs=None):
    token = _load_token()
    if not token:
        print("  ❌ 未找到 GitHub token")
        return False
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_name}/dispatches"
    payload = {"ref": "main"}
    if inputs:
        payload["inputs"] = inputs
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  ✅ dispatch {wf_name}: HTTP {r.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ❌ dispatch {wf_name} 失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}")
        return False
    except Exception as e:
        print(f"  ❌ dispatch {wf_name} 异常: {e}")
        return False


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.now()

    # 防御性：仅周六主检查与周一盘前兜底运行
    if now.weekday() not in (5, 0):
        print("📅 非周六/周一，跳过 T+1 自愈检查")
        return 0
    if now.weekday() == 0 and now.hour >= 9:
        print("📅 周一已开盘，跳过盘前兜底")
        return 0

    print(f"🔍 v8 T+1 自愈检查 — {now.strftime('%Y-%m-%d %H:%M')}")
    print("  运行 guard_v8_freshness.py ...")
    run_freshness()

    failed = t1_failed_files()
    if not failed:
        print("  ✅ 所有关键数据文件均已刷新（T+1 成功），无需自愈")
        return 0

    print(f"  🔴 发现 {len(failed)} 个文件未刷新（T+1 疑似失败）:")
    for f, detail in failed:
        print(f"     - {f}: {detail}")

    state = load_state()
    today = now.strftime("%Y-%m-%d")
    if state.get("last_t1_dispatch", "").startswith(today) and not dry:
        print("  🔕 今日已触发过 T+1 补跑，跳过重复触发")
    else:
        if dry:
            print("  [DRY-RUN] 将 dispatch v8_cn_fetch_cloud.yml(category=all) + v8_algo_cloud.yml")
        else:
            ok1 = dispatch_workflow("v8_cn_fetch_cloud.yml", {"category": "all"})
            ok2 = dispatch_workflow("v8_algo_cloud.yml")
            if ok1 or ok2:
                state["last_t1_dispatch"] = now.strftime("%Y-%m-%d %H:%M")
                save_state(state)

    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
