#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿狸咪 · 云端按铃脚本（主人授权 2026-08-19）

按铃 = 用 workflow_dispatch 戳云端主力 workflow（v8_cn_fetch_cloud / v8_algo_cloud），
      防 GitHub schedule 高负载丢触发（08-06 根因：单 workflow 多条 cron 会静默失效）。
按铃 ≠ 抓取：云端仍是数据主力（中国 IP），本机只负责「按铃」，本地 token 用量最小化。

幂等设计：仅在「该时段应有数据但云端最近未成功运行」时才 dispatch，
          避免重复消耗 GitHub Actions 分钟数（个人 repo 2000 分钟/月免费额度）。

用法：
    python scripts/alimi_bell.py [--dry-run] [--verbose]

时段规则（CST，工作日周一至周五）：
    cn_fetch_cloud（云端 ubuntu，25min timeout）：
        08:00-08:45 盘前   -> 上次成功 < 70min 则跳过
        08:45-17:00 盘中   -> 上次成功 < 45min 则跳过
        17:00-18:30 盘后   -> 上次成功 < 100min 则跳过
        18:30-23:00 晚间   -> 上次成功 < 3h 则跳过
        23:00-08:00 夜间   -> 不按铃
        周末 08:00-11:00   -> 上次成功 < 3h 则跳过；其余时间不按铃
    algo_cloud（[self-hosted, cn]，120min timeout，18:30 主档 + dispatch 兜底）：
        工作日 18:00-23:30 -> 上次成功 < 4h 则跳过；其余不按铃
        周末不按铃（workflow 内部有交易日历 gate，非交易日自动跳过）

权限：读 E:/workspace/stock-scanner/.gh_pat（已被 .gitignore 保护）。
"""
import json
import os
import sys
import datetime
import urllib.request
import urllib.error

_PAT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gh_pat")
_REPO = "ah-quant999/quant-scanner-v8"
_CST = datetime.timezone(datetime.timedelta(hours=8))

_WF_CN_FETCH = "v8_cn_fetch_cloud.yml"
_WF_ALGO = "v8_algo_cloud.yml"

_DRY = "--dry-run" in sys.argv
_VERBOSE = "--verbose" in sys.argv or _DRY


def _headers():
    pat = open(_PAT_FILE, encoding="utf-8").read().strip()
    return {
        "Authorization": "Bearer " + pat,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def _api(path, method="GET", data=None):
    req = urllib.request.Request(
        f"https://api.github.com{path}", headers=_headers(), method=method,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:  # 网络瞬断
        return -1, {"error": str(e)}


def _last_run(workflow_id):
    st, data = _api(f"/repos/{_REPO}/actions/workflows/{workflow_id}/runs?per_page=1")
    if st != 200 or not data.get("workflow_runs"):
        return None, f"API {st}: {data.get('error', 'no runs')}"
    return data["workflow_runs"][0], None


def _minutes_ago(ts_str, now):
    try:
        dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(_CST)
        return (now - dt).total_seconds() / 60.0
    except Exception:
        return None


def _cn_fetch_need_bell(now):
    wd = now.weekday()  # 0=Mon .. 6=Sun
    hhmm = now.hour * 60 + now.minute
    if wd >= 5:  # 周末：仅 08:00-11:00 窗口，阈值 3h
        if 8 * 60 <= hhmm < 11 * 60:
            return 180, "weekend-0900"
        return None, "weekend-off-hours"
    if 8 * 60 <= hhmm < 8 * 60 + 45:
        return 70, "premarket"
    if 8 * 60 + 45 <= hhmm < 17 * 60:
        return 45, "intraday"
    if 17 * 60 <= hhmm < 18 * 60 + 30:
        return 100, "post-close"
    if 18 * 60 + 30 <= hhmm < 23 * 60:
        return 180, "evening"
    return None, "night-off"


def _algo_need_bell(now):
    wd = now.weekday()
    hhmm = now.hour * 60 + now.minute
    if wd >= 5:
        return None, "weekend-off"
    if 18 * 60 <= hhmm < 23 * 60 + 30:
        return 240, "algo-main"
    return None, "algo-off-hours"


def _dispatch(workflow_id, payload=None):
    if _DRY:
        return "DRY-RUN(跳过真实dispatch)"
    st, data = _api(
        f"/repos/{_REPO}/actions/workflows/{workflow_id}/dispatches",
        method="POST", data=payload or {"ref": "main"},
    )
    if st == 204:
        return "DISPATCH OK(204)"
    return f"DISPATCH FAIL({st}): {data.get('error', '')[:150]}"


def _bell(workflow_id, rule, now):
    run, err = _last_run(workflow_id)
    if err:
        print(f"[{now:%H:%M}] {workflow_id} 查运行失败 -> 跳过本次按铃（{err}）")
        return
    status = run.get("status")
    conclusion = run.get("conclusion")
    created = run.get("created_at", "")
    ago = _minutes_ago(created, now)
    if _VERBOSE:
        print(f"  last run: status={status} conclusion={conclusion} created={created} ({ago:.0f}min前)" if ago is not None else f"  last run: status={status} conclusion={conclusion}")
    if status in ("in_progress", "queued", "waiting", "pending", "requested"):
        print(f"[{now:%H:%M}] {workflow_id} 正在运行({status}) -> 跳过按铃")
        return
    if ago is not None and ago < rule:
        print(f"[{now:%H:%M}] {workflow_id} 最近成功 {ago:.0f}min 前(<{rule}min) -> 跳过按铃")
        return
    print(f"[{now:%H:%M}] {workflow_id} 需要按铃(rule={rule}min, last={conclusion}/{ago:.0f}min前) -> {_dispatch(workflow_id)}")


def main():
    now = datetime.datetime.now(_CST)
    tag = "DRY" if _DRY else "RUN"
    print(f"=== alimi_bell {tag} {now:%Y-%m-%d %H:%M} CST ({'周末' if now.weekday()>=5 else '工作日'}) ===")

    rule, label = _cn_fetch_need_bell(now)
    if rule is None:
        print(f"[{now:%H:%M}] cn_fetch 非按铃时段({label}) -> 跳过")
    else:
        _bell(_WF_CN_FETCH, rule, now)

    rule, label = _algo_need_bell(now)
    if rule is None:
        print(f"[{now:%H:%M}] algo_cloud 非按铃时段({label}) -> 跳过")
    else:
        _bell(_WF_ALGO, rule, now)

    print("=== done ===")


if __name__ == "__main__":
    main()
