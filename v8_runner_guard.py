#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 self-hosted runner 本地守护 + 自愈脚本（2026-08-18 完整版恢复 + 老 bug 根治）

运行位置：必须在小九本机（self-hosted runner 所在 Windows 机器）上执行，
        因为它要读 D:/actions-runner-v8/_diag/Worker_*.log、查 Windows 服务/进程。

职责：
  1. 多维度检测 runner 健康（进程 / 服务 / Worker 日志 / GitHub API 连续失败）
  2. 发现真错误立即自动 remediation：重启服务/拉起进程、清理 _work、派发 fallback 等
  3. 把状态写入 raw_data/runner_status.json，经 update_v8.py 生成 data/RUNNER_STATUS.js
  4. 严重时发邮件告警到 2814546@qq.com

运行方式：
  python v8_runner_guard.py                # 检测+记录，不自动修复
  python v8_runner_guard.py --check        # 只检测（简洁输出，供自动化/手动快查）
  python v8_runner_guard.py --heal         # 检测+自动修复（推荐用于自动化）
  python v8_runner_guard.py --heal --push  # 检测+自动修复+状态推送到 main
  python v8_runner_guard.py --heal --push --alert  # 再加 fail 邮件告警

修复历史（2026-08-18，用户令「发现错就修」）：
  - 简化版(08-18 07:20 a63cb4486)缺 --heal/--push/--alert → 恢复完整版
  - RUNNER_DIR 修正为 D:/actions-runner-v8（简化版误写 D:\\actions\\cn-runner）
  - PAT 多源探测（data/.github_pat.txt → ~/.workbuddy/v8_gh_token.txt →
    E:/workspace/stock-scanner/.workbuddy/v8_gh_token.txt → 环境变量）
  - push_status_file 根治老 bug（第5-14次 autostash 拖红线→UU 死锁）：
      * commit 超时 10s→60s，TimeoutExpired 后校验是否真提交成功
      * rebase/autostash-pop 冲突自动取本地 live 版(--theirs)+add+continue/drop
      * 只 add/commit 指定 path，绝不带上红线文件
  - check_processes 只判 Listener 常驻（Worker 空闲=正常，修第18次误报）
  - --alert 仅 fail 触发（对齐文档；warn 只记录不打扰）
  - 退出码：ok=0 / warn=1 / fail=2（warn 不再误当失败）
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = "ah-quant999/quant-scanner-v8"
RUNNER_DIR = Path("D:/actions-runner-v8")
WORK_DIR = RUNNER_DIR / "_work"
SERVICE_NAME = "actions.runner.ah-quant999-quant-scanner-v8.lemoncat-cn"
RUNNER_CMD = "run.cmd"
# ⚠️ 2026-08-18 修正：327687211 是【云端 ubuntu 主力】workflow，其失败≠本地 runner 挂
#    （云端 HEALTH_CHECK 步骤问题由 v8_cloud_watchdog.py 处置）。
#    runner 守护的 GitHub 维度必须查【self-hosted】workflow：
#      · v8_cn_fetch.yml                 (324135267, self-hosted cn 应急)
#      · v8_cn_fetch_cloud_selfhosted.yml (336661558, 小九应急兜底)
#      · v8_algo_run.yml                 (324833339, self-hosted 算法链)
#    全部无近期记录 → ok（self-hosted 是兜底，云端主力时无 job 属正常）
SELFHOSTED_WORKFLOW_IDS = [324135267, 336661558, 324833339]
CN_CLOUD_WORKFLOW_ID = 327687211   # 云端 ubuntu 主力（仅 runner 全挂时派发 fallback 用）
BUILD_DEPLOY_WORKFLOW_ID = 324135263

CST = timezone(timedelta(hours=8))

# 检测到的错误模式（按严重级别）
LOG_ERROR_PATTERNS = [
    ("SAFE_DELETE_BULK_CONFIRM_REQUIRED", "safe-delete批量删除被拦截", "fail"),
    ("File was unable to be removed", "checkout清理文件失败", "fail"),
    ("fatal: unable to access", "git网络/权限失败", "warn"),
    ("The process cannot access the file", "文件被占用", "warn"),
    ("Cannot delete directory", "目录删除失败", "warn"),
    ("exit code 128", "git退出码128", "warn"),
]

# token 加载（多源探测，与 v8_health_check.py / _v8_cloud_dispatch_patrol.py 同源）
TOKEN_PATHS = [
    Path(__file__).resolve().parent / "data" / ".github_pat.txt",
    Path.home() / ".workbuddy" / "v8_gh_token.txt",
    Path("E:/workspace/stock-scanner/.workbuddy/v8_gh_token.txt"),
]


def _load_token():
    for env_name in ("V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v
    for p in TOKEN_PATHS:
        if p.exists():
            t = p.read_text(encoding="utf-8").strip().lstrip("\ufeff")
            if t:
                return t
    return None


def now_cst():
    return datetime.now(CST)


def _run_powershell(cmd, timeout=30):
    """执行 PowerShell 命令并返回 (stdout, stderr, rc)。

    强制 UTF-8 输出，避免 Windows 中文环境返回 GBK 导致解码失败。
    """
    wrapped = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        + cmd
    )
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", wrapped],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.stdout, r.stderr, r.returncode
    except Exception as e:
        return "", str(e), 1


def check_processes():
    """检查 Runner.Listener / Runner.Worker 进程是否存在。

    ⚠️ 判定标准：只判 Listener 常驻（ok = listener 在跑）。
    Worker 空闲时按 job 临时拉起，属正常，不得判为异常（修 2026-08-18 误报）。
    """
    stdout, stderr, rc = _run_powershell(
        "Get-Process | Where-Object { $_.Name -like '*Runner*' } | Select-Object Name, Id | ConvertTo-Json -Compress"
    )
    if rc != 0:
        return {"ok": False, "listener": False, "worker": False, "details": stderr[:200]}
    try:
        data = json.loads(stdout) if stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        names = [x.get("Name", "").lower() for x in data]
        listener = any("runner.listener" in n for n in names)
        worker = any("runner.worker" in n for n in names)
        return {"ok": listener, "listener": listener, "worker": worker, "details": names}
    except Exception as e:
        return {"ok": False, "listener": False, "worker": False, "details": f"解析失败: {e}"}


def check_service():
    """查询 runner Windows 服务状态。

    返回英文状态名（Running/Stopped/...），避免中文系统本地化的解析问题。
    服务不存在（进程方式运行）属正常，NOT_FOUND 不视为错误。
    """
    stdout, stderr, rc = _run_powershell(
        f"try {{ $s = Get-Service -Name '{SERVICE_NAME}'; $s.Status.ToString() }} catch {{ 'NOT_FOUND' }}"
    )
    status = stdout.strip() if rc == 0 else f"ERROR:{stderr[:100]}"
    STATUS_MAP = {
        "Running": "Running", "正在运行": "Running",
        "Stopped": "Stopped", "已停止": "Stopped",
        "StartPending": "StartPending", "正在启动": "StartPending",
        "StopPending": "StopPending", "正在停止": "StopPending",
        "NOT_FOUND": "NOT_FOUND",
    }
    status_en = STATUS_MAP.get(status, status)
    return {
        "ok": status_en == "Running",
        "status": status_en,
        "exists": status_en != "NOT_FOUND",
    }


def scan_worker_logs(lookback_min=30, max_logs=20):
    """扫描最近 Worker 日志中的错误模式。"""
    diag_dir = RUNNER_DIR / "_diag"
    if not diag_dir.exists():
        return {"ok": True, "errors": [], "scanned": 0, "message": "_diag 目录不存在"}

    logs = sorted(diag_dir.glob("Worker_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    logs = logs[:max_logs]
    cutoff = datetime.now(timezone.utc).timestamp() - lookback_min * 60

    errors = []
    scanned = 0
    for log in logs:
        mtime = log.stat().st_mtime
        if mtime < cutoff:
            continue
        scanned += 1
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern, desc, level in LOG_ERROR_PATTERNS:
            if pattern in text:
                count = text.count(pattern)
                errors.append({
                    "file": log.name,
                    "pattern": pattern,
                    "desc": desc,
                    "level": level,
                    "count": count,
                    "mtime": datetime.fromtimestamp(mtime, tz=CST).strftime("%Y-%m-%d %H:%M:%S"),
                })

    return {
        "ok": not any(e["level"] == "fail" for e in errors),
        "errors": errors,
        "scanned": scanned,
        "message": f"扫描 {scanned} 份日志，发现 {len(errors)} 类错误" if errors else "最近日志无错误",
    }


def _github_api_get(url, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"
    except Exception as e:
        return None, f"请求失败: {e}"


def check_github_runs(token, workflow_ids, lookback_hours=24, max_runs=15):
    """检查 self-hosted workflow 最近运行，识别连续失败/checkout 失败。

    workflow_ids: 列表，任一 workflow 有近期 run 即纳入统计；全部无记录 → ok
    （self-hosted 是兜底角色，云端主力时无 job 属正常，不得判 fail/warn）。
    """
    all_runs = []
    api_err = None
    for wid in workflow_ids:
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wid}/runs?per_page={max_runs}"
        data, err = _github_api_get(url, token)
        if err:
            api_err = err
            continue
        runs = data.get("workflow_runs", [])
        if runs:
            all_runs.extend(runs)
    if not all_runs:
        if api_err:
            return {"ok": False, "error": api_err, "consecutive_failures": 0, "checkout_failures": 0}
        return {"ok": True, "consecutive_failures": 0, "checkout_failures": 0, "message": "self-hosted 无近期运行（兜底角色，正常）"}

    # 按时间倒序取最近 max_runs 条
    all_runs.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    runs = all_runs[:max_runs]

    consecutive = 0
    for r in runs:
        if r.get("conclusion") == "failure":
            consecutive += 1
        elif r.get("conclusion") in ("success", "cancelled"):
            # cancelled 也会中断失败 streak（超时被取消不算连续失败）
            break
        elif r.get("status") in ("in_progress", "queued", "pending"):
            # 正在运行的不算失败也不算成功
            break

    # 检查最新失败 run 的 checkout step 是否失败
    checkout_failures = 0
    latest_fail = next((r for r in runs if r.get("conclusion") == "failure"), None)
    if latest_fail and token:
        jobs_url = latest_fail.get("jobs_url", "")
        if jobs_url:
            jdata, jerr = _github_api_get(jobs_url, token)
            if jdata:
                for job in jdata.get("jobs", []):
                    for step in job.get("steps", []):
                        name = (step.get("name") or "").lower()
                        if "checkout" in name and step.get("conclusion") == "failure":
                            checkout_failures += 1

    latest = runs[0] if runs else None
    latest_failed = latest and latest.get("conclusion") == "failure"

    # 检测 stuck in_progress：最新 run 处于 in_progress 且已运行超过 10 分钟
    stuck_min = 0
    if latest and latest.get("status") == "in_progress":
        try:
            started = datetime.strptime(latest.get("started_at") or latest.get("created_at"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            stuck_min = int((datetime.now(timezone.utc) - started).total_seconds() / 60)
        except Exception:
            stuck_min = 0

    # 判定：
    # - 最新一次失败且 checkout 失败 → fail（checkout 失败=self-hosted 工作目录问题）
    # - 连续 3 次失败 → fail
    # - 最新 run stuck in_progress > 10min → warn（runner 可能卡住，需人工或本地重启）
    is_fail = (latest_failed and checkout_failures > 0) or consecutive >= 3
    is_warn = (latest_failed and not is_fail) or (latest and latest.get("status") == "in_progress" and stuck_min > 10)

    wf_name = latest.get("name") if latest else ""
    return {
        "ok": not is_fail and not is_warn,
        "consecutive_failures": consecutive,
        "checkout_failures": checkout_failures,
        "latest_run_id": latest.get("id") if latest else (latest_fail.get("id") if latest_fail else None),
        "latest_failed": latest_failed,
        "latest_status": latest.get("status") if latest else None,
        "stuck_min": stuck_min,
        "is_fail": is_fail,
        "is_warn": is_warn,
        "message": (
            f"self-hosted 最近 {len(runs)} 条中连续失败 {consecutive} 次，checkout 失败 {checkout_failures} 次，"
            f"最新 {wf_name} {'失败' if latest_failed else latest.get('status','未知') if latest else '无'}"
            f"{f' (已卡住 {stuck_min} 分)' if stuck_min > 0 else ''}"
        ),
    }


def check_runner_env():
    """检查 runner .env 是否配置了 safe-delete 阈值。"""
    env_file = RUNNER_DIR / ".env"
    if not env_file.exists():
        return {"ok": False, "threshold": None, "message": ".env 不存在"}
    text = env_file.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD\s*=\s*(\d+)", text)
    if m:
        threshold = int(m.group(1))
        return {"ok": threshold >= 500, "threshold": threshold, "message": f"阈值={threshold}"}
    return {"ok": False, "threshold": None, "message": "未配置 CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD"}


def restart_runner_service():
    """尝试重启 runner Windows 服务。"""
    _, stderr, rc = _run_powershell(
        f"Restart-Service -Name '{SERVICE_NAME}' -Force; (Get-Service -Name '{SERVICE_NAME}').Status"
    )
    return rc == 0, stderr[:200] if rc != 0 else "服务已重启"


def start_runner_process():
    """进程方式拉起 runner（无服务时的兜底启动，run.cmd 后台运行）。"""
    log_path = RUNNER_DIR / "_diag" / "guard_start.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        f'Set-Location "{RUNNER_DIR}"; '
        f'Start-Process -FilePath "{RUNNER_DIR}\\{RUNNER_CMD}" -WorkingDirectory "{RUNNER_DIR}" '
        f'-RedirectStandardOutput "{log_path}" -RedirectStandardError "{log_path}"'
    )
    try:
        subprocess.Popen(['powershell', '-NoProfile', '-Command', cmd],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return True, "已发起进程拉起"
    except Exception as e:
        return False, f"拉起失败: {e}"


def clear_work_dir():
    """清理 _work 目录（危险操作，只在明确调用时执行）。"""
    if not WORK_DIR.exists():
        return True, "_work 不存在，无需清理"
    try:
        empty = Path(os.environ.get("TEMP", "C:/Windows/Temp")) / "empty_work_dir"
        empty.mkdir(exist_ok=True)
        subprocess.run(
            ["robocopy", str(empty), str(WORK_DIR), "/MIR", "/MT:8", "/R:1", "/W:0"],
            capture_output=True, text=True, timeout=120,
        )
        return True, "_work 已清空(MIR)"
    except Exception as e:
        return False, f"清理失败: {e}"


def dispatch_fallback_workflow(token, workflow_id, inputs=None):
    """经 GitHub API dispatch 指定 workflow。"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/dispatches"
    payload = {"ref": "main"}
    if inputs:
        payload["inputs"] = inputs
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"
    except Exception as e:
        return False, f"请求失败: {e}"


def send_alert(subject, body):
    """调用 v8_send_alert.py 发邮件。"""
    try:
        from v8_send_alert import send_alert as _send
        return _send(subject, body)
    except Exception as e:
        print(f"[WARN] 邮件发送失败: {e}")
        return False


def write_status_file(status_dict):
    """写入 raw_data/runner_status.json。"""
    RAW_DIR = Path(__file__).resolve().parent / "raw_data"
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / "runner_status.json"
    path.write_text(json.dumps(status_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def push_status_file(path):
    """推送 runner_status.json 到 main（Contents API 单文件直推，根治本地 git 死锁）。

    历史教训（2026-08-14~18 连续 10+ 轮老 bug，本机环境已实测多种方案）：
      ① naive 版 `git commit`(10s) + `git pull --rebase --autostash`：
         autostash 把红线/数据文件拖入冲突 → UU → 下轮 "unmerged files" 断链。
      ② 显式 stash 管理（15:18 实测）：本机是坚果云同步目录 + update_v8/cloud_fetch
         持续写 data/*.js，rebase 阶段工作树无法保持干净 → 70+ 文件冲突。
      → 彻底放弃本地 git push 链路，改 GitHub Contents API 单文件直推：
        只 PUT raw_data/runner_status.json 一个文件（铁律「只 push 状态文件」完全满足），
        不 commit、不 stash、不 rebase、不碰本地工作树/红线文件，绝无 UU 可能。
        Contents API 写 main 同样触发云端 build → data/RUNNER_STATUS.js 更新。
    """
    token = _load_token()
    if not token:
        return False, "无 GitHub token，无法 Contents API 推送"

    api = f"https://api.github.com/repos/{REPO}/contents/raw_data/runner_status.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    try:
        import base64
        content = path.read_bytes()
        # 1) 获取远端当前 sha（避免覆盖他人新提交；404=首次创建）
        req = urllib.request.Request(api, headers=headers, method="GET")
        sha = None
        remote_b64 = ""
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                remote = json.loads(r.read().decode("utf-8"))
                sha = remote.get("sha")
                remote_b64 = remote.get("content", "")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return False, f"GET sha 失败: HTTP {e.code}"
        # 2) 远端内容与本地相同 → 跳过推送
        if sha and remote_b64:
            try:
                if base64.b64decode(remote_b64.replace("\n", "")) == content:
                    return True, "远端已是最新，跳过推送"
            except Exception:
                pass
        # 3) PUT 覆盖
        payload = {
            "message": f"data: runner 状态上报 {now_cst().strftime('%Y%m%d-%H%M')}",
            "content": base64.b64encode(content).decode("utf-8"),
        }
        if sha:
            payload["sha"] = sha
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api, data=body, headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=25) as r:
            return True, f"Contents API 已推送 (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return False, f"Contents API 失败: HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"
    except Exception as e:
        return False, f"Contents API 异常: {e}"


def decide_overall(process_ok, service_exists, service_ok, log_ok, github, env_ok):
    """综合判定 runner 健康状态。

    关键原则：
    - runner 可以进程方式运行（服务不存在属正常，NOT_FOUND 非错误）
    - 进程在 + GitHub 最近运行正常 + env 阈值已配 → ok
    - GitHub API 不可达（含 error 键，网络瞬断/认证失败）→ 该维度降级不参与判定，
      整体由本地检测决定（避免国内网络瞬断导致每轮误报 warn）
    - 日志错误单独出现但 GitHub 已恢复 → warn（避免旧日志导致误报）
    - 连续失败 / 最新失败且 checkout 失败 / 进程缺失 / 服务存在但停止 → fail
    """
    github_ok = github.get("ok", False)
    github_fail = github.get("is_fail", False)
    github_warn = github.get("is_warn", False)
    github_reachable = "error" not in github

    # 硬性失败（本地维度优先）
    if not process_ok:
        if service_exists and not service_ok:
            return "fail"
        # 进程不在但服务也不存在：可能是临时启动方式，warn
        return "warn"
    if service_exists and not service_ok:
        return "fail"
    if github_reachable and github_fail:
        return "fail"
    if not env_ok:
        return "warn"
    if not log_ok:
        # 日志有错误但 GitHub 最近已正常 → 只 warn
        return "warn"
    if github_reachable and (github_warn or not github_ok):
        return "warn"
    return "ok"


def main():
    parser = argparse.ArgumentParser(description="v8 self-hosted runner 本地守护")
    parser.add_argument("--check", action="store_true", help="只检测（简洁输出，不写状态不修复）")
    parser.add_argument("--heal", action="store_true", help="执行自动修复动作")
    parser.add_argument("--push", action="store_true", help="状态变更后推送到 main")
    parser.add_argument("--clear-work", action="store_true", help="强制清空 _work 目录（危险）")
    parser.add_argument("--alert", action="store_true", help="fail 状态时发邮件告警")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    print(f"[INFO] v8_runner_guard start @ {now_cst().strftime('%Y-%m-%d %H:%M:%S')}")

    token = _load_token()
    if not token:
        print("[WARN] 未找到 GitHub token，无法查询 GitHub API 和 dispatch fallback")

    # ── 检测层 ──
    proc = check_processes()
    svc = check_service()
    logs = scan_worker_logs(lookback_min=30, max_logs=20)
    github = check_github_runs(token, SELFHOSTED_WORKFLOW_IDS) if token else {"ok": False, "error": "无 token"}
    env = check_runner_env()

    print(f"  进程: listener={proc['listener']} worker={proc['worker']} | {proc.get('details', '')}")
    print(f"  服务: {svc['status']} | exists={svc['exists']}")
    print(f"  日志: {logs['message']}")
    if logs['errors']:
        for e in logs['errors'][:5]:
            print(f"    - [{e['level']}] {e['desc']} @ {e['file']} x{e['count']}")
    print(f"  GitHub: {github.get('message', github.get('error', ''))}")
    print(f"  环境: {env['message']}")

    overall = decide_overall(
        proc["ok"], svc["exists"], svc["ok"], logs["ok"], github, env["ok"]
    )
    print(f"[INFO] 综合状态: {overall.upper()}")

    # --check 模式：简洁输出后即返回（供自动化/手动快查，不写文件不修复）
    if args.check:
        gh_short = {
            "ok": "online", "is_fail": "fail", "is_warn": "warn",
        }.get("ok" if github.get("ok") else ("is_fail" if github.get("is_fail") else ("is_warn" if github.get("is_warn") else "unknown")), "unknown")
        if not token:
            gh_short = "unknown"
        print(f"  [CHECK] GitHub={gh_short} | 本地进程={proc['ok']} | 需要拉起={not proc['ok']}")
        sys.exit(0 if overall == "ok" else (1 if overall == "warn" else 2))

    # ── 自愈层 ──
    actions = []
    if args.heal:
        # 1. 服务存在但未运行 → 重启服务
        if svc["exists"] and not svc["ok"]:
            ok, msg = restart_runner_service()
            actions.append(f"重启服务: {'成功' if ok else '失败'} ({msg})")
            if ok:
                svc = check_service()  # 重新检查

        # 2. 进程缺失 → 优先重启服务；无服务则以进程方式拉起 run.cmd
        if not proc["ok"]:
            if svc["ok"]:
                ok, msg = restart_runner_service()
                actions.append(f"进程缺失重启服务: {'成功' if ok else '失败'} ({msg})")
            else:
                ok, msg = start_runner_process()
                actions.append(f"进程缺失拉起 run.cmd: {'成功' if ok else '失败'} ({msg})")
            proc = check_processes()
            svc = check_service()

        # 3. safe-delete 被拦截（本地日志实锤）→ 才建议/执行清空 _work。
        #    ⚠️ 2026-08-18 修正：GitHub 侧 checkout 失败【不再】触发清空 _work 建议——
        #    实测失败根因是「Failed to connect to github.com:443」（cn git 墙网络超时），
        #    清 _work 无效且属危险操作；仅本地 Worker 日志扫到
        #    SAFE_DELETE_BULK_CONFIRM_REQUIRED（文件清理被拦）才清。
        has_safe_delete = any(e["pattern"] == "SAFE_DELETE_BULK_CONFIRM_REQUIRED" for e in logs["errors"])
        if has_safe_delete and args.clear_work:
            ok, msg = clear_work_dir()
            actions.append(f"清空 _work: {'成功' if ok else '失败'} ({msg})")
        elif has_safe_delete:
            actions.append("建议：清空 _work 目录并重启服务（加 --clear-work 执行）")
        elif github.get("checkout_failures", 0) > 0:
            actions.append("checkout 失败为网络型（github.com:443 超时），无需清空 _work，等待网络恢复")

        # 4. runner 完全不可用 → dispatch fallback 到云端 ubuntu（中国数据可能抓不到，但好过没有）
        if not svc["ok"] and not proc["ok"] and token:
            ok, msg = dispatch_fallback_workflow(token, CN_CLOUD_WORKFLOW_ID, {"category": "intraday"})
            actions.append(f"dispatch cn_fetch 云端 fallback: {'成功' if ok else '失败'} ({msg})")
            # 同时触发 build 兜底
            dispatch_fallback_workflow(token, BUILD_DEPLOY_WORKFLOW_ID)

    # ── 状态落盘 ──
    status = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "status": overall,
        "process": proc,
        "service": svc,
        "worker_logs": logs,
        "github": github,
        "runner_env": env,
        "actions_taken": actions,
        "message": (
            f"runner进程={'正常' if proc['ok'] else '异常'}; "
            f"服务={svc['status']}; "
            f"日志={logs['message']}; "
            f"GitHub={github.get('message', github.get('error', ''))}"
        ),
    }

    path = write_status_file(status)
    print(f"[INFO] 状态已写入 {path}")

    # ── 推送 ──
    pushed = False
    if args.push:
        ok, msg = push_status_file(path)
        pushed = ok
        print(f"[INFO] 推送: {msg}")

    # ── 告警（仅 fail 触发，对齐文档；warn 只记录不打扰）──
    # 2026-08-18 新增去重：同级别 fail 60 分钟内只发一封，避免网络型持续失败
    # （github.com:443 超时等）每 20 分钟轰炸邮箱。
    if args.alert and overall == "fail":
        ALERT_TS_FILE = Path(__file__).resolve().parent / "raw_data" / ".runner_alert_ts"
        now_ts = now_cst().timestamp()
        last_ts = 0.0
        if ALERT_TS_FILE.exists():
            try:
                last_ts = float(ALERT_TS_FILE.read_text(encoding="utf-8").strip())
            except Exception:
                last_ts = 0.0
        if now_ts - last_ts >= 3600:
            subject = f"【v8 runner 故障】{now_cst().strftime('%m-%d %H:%M')}"
            lines = [
                f"runner 本地守护检测到 FAIL 状态",
                f"时间: {status['update_time']}",
                f"进程: listener={proc['listener']} worker={proc['worker']}",
                f"服务: {svc['status']}",
                f"日志: {logs['message']}",
                f"GitHub: {github.get('message', github.get('error', ''))}",
                f"环境: {env['message']}",
            ]
            if actions:
                lines += ["", "已执行自愈动作:"]
                lines += [f"  - {a}" for a in actions]
            if pushed:
                lines.append("状态已推送 raw_data/runner_status.json")
            send_alert(subject, "\n".join(lines))
            try:
                ALERT_TS_FILE.write_text(str(now_ts), encoding="utf-8")
            except Exception:
                pass
        else:
            print("[INFO] 60 分钟内已告警过同级别 fail，跳过重复邮件")

    print(f"[INFO] v8_runner_guard done")
    sys.exit(0 if overall == "ok" else (1 if overall == "warn" else 2))


if __name__ == "__main__":
    main()
