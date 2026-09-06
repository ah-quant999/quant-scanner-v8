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
    algo_cloud（ubuntu-latest，120min timeout，19:15 主档 + dispatch 兜底）：
        工作日 19:15-23:30 -> 上次成功 < 4h 则跳过；最近 run 失败/取消则 30min 重试
        盘后若 BACKTEST_TDX/BACKTEST_COMPREHENSIVE 仍为旧日期 -> 直接按铃
        周末不按铃（workflow 内部有交易日历 gate，非交易日自动跳过）

权限：读 E:/workspace/stock-scanner/.gh_pat（已被 .gitignore 保护）。
"""
import json
import os
import re
import sys
import datetime
import urllib.request
import urllib.error

# 安全铁律(2026-09-05): token 单点存仓库外 ~/.workbuddy/v8_gh_pat(坚果云同步范围外);
# 仓库内 .gh_pat 仅作未迁移机器的兜底, 严禁新建含明文 token 的同步盘文件
_PAT_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), ".workbuddy", "v8_gh_pat"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gh_pat"),
]
_PAT_FILE = next((p for p in _PAT_CANDIDATES if os.path.exists(p)), _PAT_CANDIDATES[0])
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
        return None, None, "weekend-off"
    if 19 * 60 + 15 <= hhmm < 23 * 60 + 30:
        return 240, 30, "algo-main"
    return None, None, "algo-off-hours"


def _read_cloud_update_time(var_name):
    """从 GitHub Contents API 读取 data/X.js 内层 update_time / calc_time（避免本地滞后）。"""
    import base64
    st, data = _api(f"/repos/{_REPO}/contents/data/{var_name}.js")
    if st != 200:
        return None
    try:
        text = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _read_update_time(var_name):
    """读取本地 data/X.js 内层 update_time / calc_time（云端失败时 fallback）。"""
    p = os.path.join(os.path.dirname(_PAT_FILE), "data", f"{var_name}.js")
    if not os.path.exists(p):
        return None
    text = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r'"calc_time"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _algo_data_need_bell(now):
    """盘后 19:15-23:30 直接检查回测卡数据是否已更新到今天。

    根因：只看 workflow 上次成功不够——workflow 成功也可能因为 19:15 前跑过，
    而选股策略被我们永久门控在 18:00 后、主档调为 19:15，回测数据必须今天才新鲜。
    """
    hhmm = now.hour * 60 + now.minute
    if not (19 * 60 + 15 <= hhmm < 23 * 60 + 30):
        return None
    if now.weekday() >= 5:
        return None
    today = now.date().isoformat()
    # 2026-08-20 主人令审计补全：加入 INDEX_HISTORY，
    # 防 19:15 算法链失败时 K 线归档静默陈旧。
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST 已删（驾驶舱模块下线，留在清单会因文件消失永久误报按铃）
    vars_ = ["BACKTEST_TDX", "BACKTEST_COMPREHENSIVE",
             "INDEX_HISTORY"]
    stale = []
    for v in vars_:
        ts = _read_cloud_update_time(v)
        if ts is None:
            ts = _read_update_time(v)  # fallback 本地
        if not ts or not ts.startswith(today):
            stale.append((v, ts))
    return stale


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


def _bell(workflow_id, rule_success, rule_failure, now):
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
    rule = rule_success if conclusion == "success" else rule_failure
    if rule is None:
        print(f"[{now:%H:%M}] {workflow_id} 当前规则不适用(last={conclusion}) -> 跳过按铃")
        return
    if ago is not None and ago < rule:
        print(f"[{now:%H:%M}] {workflow_id} 最近 {conclusion} {ago:.0f}min 前(<{rule}min) -> 跳过按铃")
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
        _bell(_WF_CN_FETCH, rule, 30, now)

    rule_s, rule_f, label = _algo_need_bell(now)
    if rule_s is None:
        print(f"[{now:%H:%M}] algo_cloud 非按铃时段({label}) -> 跳过")
    else:
        # 先直接检查回测数据文件新鲜度：比看 workflow 状态更准
        stale = _algo_data_need_bell(now)
        if stale:
            run, err = _last_run(_WF_ALGO)
            if err:
                print(f"[{now:%H:%M}] algo_cloud 数据陈旧但查运行失败({err}) -> 仍尝试dispatch: {_dispatch(_WF_ALGO)}")
            elif run.get("status") in ("in_progress", "queued", "waiting", "pending", "requested"):
                print(f"[{now:%H:%M}] algo_cloud 数据陈旧但已有 run 在跑({run['status']}) -> 跳过按铃，等本轮完成")
            else:
                print(f"[{now:%H:%M}] algo_cloud 数据陈旧需补跑: {stale} -> {_dispatch(_WF_ALGO)}")
        else:
            # V5 2026-09-03 主人令「风暴一劳永逸」：回测/AI 数据已新鲜时，不因 run 失败/取消
            #   重试按铃——假阳性失败会引 30min 循环派发 → 队列互踩风暴（2026-09-03 实证）。
            #   主档 schedule(16:40/18:10/19:15/20:00) + 21:30 内容级最终闸已覆盖兜底。
            print(f"[{now:%H:%M}] algo_cloud 回测/AI 数据已新鲜 -> 跳过按铃（含失败重试，防风暴）")

    print("=== done ===")


if __name__ == "__main__":
    main()
