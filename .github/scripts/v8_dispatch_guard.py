# -*- coding: utf-8 -*-
"""v8_dispatch_guard — fetch 三链并发组统一让位守卫（2026-11-23 死亡旋转根治）

【病理实证】11-23 14:43-15:00：hosted 兜底轮占住 v8-cn-fetch-cloud-intraday 组 →
  selfhosted 各档 dispatch 全变 pending → GitHub 并发组机制「cancel-in-progress:false
  只保护**运行中** run，组内排队 run 会被新 dispatch **顶杀**」→ 看门狗/调度器多源
  派发互相顶杀排队轮 = 死亡旋转（14:02/14:14/14:27/14:39/14:55 五轮实证全被顶杀）。
【盲区根因】三链（hosted/selfhosted/lemoncat）共用 `v8-cn-fetch-cloud-<category>` 组，
  而各派发源只查**自己 workflow** 的 run ⇒ 跨链盲区：本链无 run ≠ 组空闲。
【修法】任何派发源 dispatch fetch 三链前，必须查**全组**：三条链任一存在
  「近期（<=40min）启动的 in_progress / queued」run ⇒ 让位不派（返回 busy）。
  · 40min 新鲜窗防死锁：>40min 仍 queued = runner 死亡/僵尸，此时派发顶掉它反而是清理；
  · 探测 API 失败 ⇒ 按 busy 处理（宁少派一档，不冒顶杀风险；下一档会重试）；
  · 本模块只读，不写不 cancel。
"""
import json
import urllib.request

FETCH_TRIO = (
    "v8_cn_fetch_cloud.yml",
    "v8_cn_fetch_cloud_selfhosted.yml",
    "v8_cn_fetch_intraday_lemoncat.yml",
)
RECENT_SEC = 40 * 60   # 活跃 run 新鲜窗


def fetch_trio_busy(token, repo, per_page=12, timeout=20, log=print):
    """True = fetch 三链任一有近期在跑/排队 run ⇒ 派发源让位。"""
    api = "https://api.github.com/repos/" + repo + "/actions/workflows/"
    now = __import__("datetime").datetime.utcnow()
    detail = []
    for wf in FETCH_TRIO:
        try:
            rq = urllib.request.Request(
                api + wf + "/runs?per_page=%d" % per_page,
                headers={"Authorization": "Bearer " + token,
                         "Accept": "application/vnd.github+json",
                         "User-Agent": "v8-dispatch-guard"})
            with urllib.request.urlopen(rq, timeout=timeout) as resp:
                runs = json.loads(resp.read()).get("workflow_runs", [])
        except Exception as e:
            # fail-closed：探测失败按忙碌处理（少派一档无害，顶杀排队轮有害）
            detail.append("%s probe_err(%s)" % (wf, type(e).__name__))
            continue
        for r in runs:
            if r.get("status") not in ("in_progress", "queued"):
                continue
            started = r.get("run_started_at") or r.get("created_at") or ""
            try:
                ts = __import__("datetime").datetime.strptime(
                    started.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                age = (now - ts).total_seconds()
            except Exception:
                age = 0.0
            if age > RECENT_SEC:
                continue  # 远古 queued = 僵尸，不阻断（派发顶掉它是清理）
            detail.append("%s#%s %s (%.0fmin)" % (wf.split("_")[3][:6], r.get("id"),
                                                  r.get("status"), age / 60))
            break
    busy = bool(detail)
    if busy:
        log("  🛡 dispatch-guard: fetch 组忙碌，让位不派 → " + "; ".join(detail))
    return busy
