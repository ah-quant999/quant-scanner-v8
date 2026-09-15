# -*- coding: utf-8 -*-
"""health_patrol 去抖 gate — 2026-08-21 一劳永逸根因修复（主人令）

背景（实证）：
  patrol 由 workflow_run 触发（cn_fetch / 盘后算法链 完成即触发），上游今日 150 run，
  patrol 随之被触发 100+ 次。原 concurrency 为 cancel-in-progress: true，配合本 workflow
  内含 sleep 600 的「自愈验证」step，导致每个 patrol 都在 sleep 中被后来者 cancel，
  100 run 里 98 cancelled —— 自愈器实际失能，锁文件（data/.heal_dispatch.json）写不回。

修复分两半：
  1. concurrency 改 cancel-in-progress: false —— running 不再被打断，能跑完整闭环；
  2. 本脚本（去抖 gate）—— false 之后排队 run 会接力连跑，若不去抖会把 group 与
     GitHub API 配额占满（正是 secondary rate limit 403 风暴的燃料）。故：
     近 WINDOW_MIN 分钟内已有「完整跑完（success/failure，非 cancelled）」的 patrol，
     则本轮直接 no-op 秒退，不做任何重活、不发任何派发 API。

判定只依赖 GitHub Runs API（无状态），不读 repo 内锁文件 —— 因为锁文件本身正是
被 cancel 写不回的受害者，用它判定会自我欺骗。

输出：GITHUB_OUTPUT 写 skip=true/false、reason=...
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("REPO", "ah-quant999/quant-scanner-v8")
TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
MY_RUN_ID = str(os.environ.get("GITHUB_RUN_ID", ""))
EVENT = os.environ.get("EVENT_NAME", "")
FORCE = (os.environ.get("FORCE", "") or "").strip().lower()
OUT = os.environ.get("GITHUB_OUTPUT", "")

WINDOW_MIN = int(os.environ.get("DEBOUNCE_WINDOW_MIN", "15"))
WF_FILE = "v8_health_patrol.yml"


def emit(skip: bool, reason: str) -> None:
    print(("⏭️  SKIP：" if skip else "▶️  RUN：") + reason)
    if OUT:
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(f"skip={'true' if skip else 'false'}\n")
            f.write(f"reason={reason}\n")


def api(path):
    url = f"https://api.github.com/repos/{REPO}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "v8-patrol-debounce",
    })
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"API {path} 失败：{last}")


def main() -> int:
    # 手动强制：永不去抖（人工要看结果时必须真跑）
    if EVENT == "workflow_dispatch" and FORCE in ("true", "1", "yes"):
        emit(False, "手动 force=true，绕过去抖 gate")
        return 0
    if not TOKEN:
        emit(False, "无 token，无法判定，保守放行")
        return 0

    try:
        data = api(f"/actions/workflows/{WF_FILE}/runs?per_page=20")
    except Exception as e:  # noqa: BLE001
        # 查不到就放行 —— 宁可多跑一轮，不可漏掉自愈
        emit(False, f"Runs API 查询失败（{e}），保守放行")
        return 0

    now = datetime.now(timezone.utc)
    for r in data.get("workflow_runs", []):
        if str(r.get("id")) == MY_RUN_ID:
            continue
        # 只认「完整跑完」的：cancelled 说明被打断，等于没巡检，不能当去抖依据
        if r.get("status") != "completed":
            continue
        if r.get("conclusion") not in ("success", "failure"):
            continue
        ts = r.get("updated_at") or r.get("run_started_at")
        if not ts:
            continue
        done = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        gap = (now - done).total_seconds() / 60.0
        cn = done.astimezone(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M:%S")
        if gap < WINDOW_MIN:
            emit(True, f"上轮 patrol #{r.get('id')} 于 {cn}(CST) 完整跑完，距今 {gap:.1f}min < {WINDOW_MIN}min 去抖窗口")
            return 0
        emit(False, f"上轮 patrol #{r.get('id')} 于 {cn}(CST) 完成，距今 {gap:.1f}min ≥ {WINDOW_MIN}min，本轮正常巡检")
        return 0

    emit(False, f"近 20 run 内无完整跑完的 patrol（多为 cancelled），本轮必须跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
