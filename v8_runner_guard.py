#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 self-hosted runner 本地守护 + 自愈脚本

运行位置：必须在小九本机（self-hosted runner 所在 Windows 机器）上执行，
        因为它要读 D:/actions-runner-v8/_diag/Worker_*.log、查 Windows 服务/进程。

职责：
  1. 多维度检测 runner 健康（进程 / 服务 / Worker 日志 / GitHub API 连续失败）
  2. 发现真错误立即自动 remediation：重启服务、清理 _work、派发 fallback 等
  3. 把状态写入 raw_data/runner_status.json，经 update_v8.py 生成 data/RUNNER_STATUS.js
  4. 严重时发邮件告警到 2814546@qq.com

运行方式：
  python v8_runner_guard.py                # 检测+记录，不自动修复
  python v8_runner_guard.py --heal         # 检测+自动修复（推荐用于自动化）
  python v8_runner_guard.py --heal --push  # 检测+自动修复+状态推送到 main
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
CN_WORKFLOW_ID = 327687211
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

# token 加载（与 v8_health_check.py / _v8_cloud_dispatch_patrol.py 同源）
TOKEN_PATHS = [
    Path("data/.github_pat.txt"),
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
    # 先设置 Console 输出编码为 UTF-8，再执行用户命令
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
    """检查 Runner.Listener / Runner.Worker 进程是否存在。"""
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
    """
    stdout, stderr, rc = _run_powershell(
        f"try {{ $s = Get-Service -Name '{SERVICE_NAME}'; $s.Status.ToString() }} catch {{ 'NOT_FOUND' }}"
    )
    status = stdout.strip() if rc == 0 else f"ERROR:{stderr[:100]}"
    # 中文系统可能仍返回本地化字符串，做兼容映射
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
    # 统一用 UTC epoch 比较，避免本地时区歧义
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
                # 统计命中次数
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


def check_github_runs(token, workflow_id, lookback_hours=2, max_runs=15):
    """检查 GitHub API 中某 workflow 的最近运行，识别连续失败/checkout 失败。"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/runs?per_page={max_runs}"
    data, err = _github_api_get(url, token)
    if err:
        return {"ok": False, "error": err, "consecutive_failures": 0, "checkout_failures": 0}

    runs = data.get("workflow_runs", [])
    if not runs:
        return {"ok": True, "consecutive_failures": 0, "checkout_failures": 0, "message": "无运行记录"}

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
    # - 最新一次失败且 checkout 失败 → fail
    # - 连续 3 次失败 → fail
    # - 最新 run stuck in_progress > 10min → warn（runner 可能卡住，需人工或本地重启）
    is_fail = (latest_failed and checkout_failures > 0) or consecutive >= 3
    is_warn = (latest_failed and not is_fail) or (latest and latest.get("status") == "in_progress" and stuck_min > 10)

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
            f"最近 {len(runs)} 条中连续失败 {consecutive} 次，checkout 失败 {checkout_failures} 次，"
            f"最新 {'失败' if latest_failed else latest.get('status','未知') if latest else '无'}"
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


def clear_work_dir():
    """清理 _work 目录（危险操作，只在明确调用时执行）。"""
    if not WORK_DIR.exists():
        return True, "_work 不存在，无需清理"
    try:
        # 用 robocopy 把空目录镜像过去，实现快速清空（比 shutil.rmtree 更稳）
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
    """提交并推送 runner_status.json。"""
    try:
        subprocess.run(["git", "fetch", "origin", "main"], check=True, timeout=60)
        subprocess.run(["git", "add", str(path)], check=True, timeout=10)
        r = subprocess.run(
            ["git", "status", "--short", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        if not r.stdout.strip():
            return True, "无变更，跳过推送"
        msg = f"data: runner 状态上报 {now_cst().strftime('%Y%m%d-%H%M')}"
        subprocess.run(["git", "commit", "-m", msg, str(path)], check=True, timeout=10)
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], check=True, timeout=60)
        subprocess.run(["git", "push", "origin", "main"], check=True, timeout=60)
        return True, "已推送"
    except subprocess.CalledProcessError as e:
        return False, f"git 失败: {e}"
    except Exception as e:
        return False, f"异常: {e}"


def decide_overall(process_ok, service_exists, service_ok, log_ok, github, env_ok):
    """综合判定 runner 健康状态。

    关键原则：
    - runner 可以进程方式运行（服务不存在属正常）
    - 进程在 + GitHub 最近运行正常 + env 阈值已配 → ok
    - 日志错误单独出现但 GitHub 已恢复 → warn（避免旧日志导致误报）
    - 连续失败 / 最新失败且 checkout 失败 / 进程缺失 / 服务存在但停止 → fail
    """
    github_ok = github.get("ok", False)
    github_fail = github.get("is_fail", False)
    github_warn = github.get("is_warn", False)

    # 硬性失败
    if not process_ok:
        if service_exists and not service_ok:
            return "fail"
        # 进程不在但服务也不存在：可能是临时启动方式，warn
        return "warn"
    if service_exists and not service_ok:
        return "fail"
    if github_fail:
        return "fail"
    if not env_ok:
        return "warn"
    if not log_ok:
        # 日志有错误但 GitHub 最近已正常 → 只 warn
        return "warn"
    if github_warn or not github_ok:
        return "warn"
    return "ok"


def main():
    parser = argparse.ArgumentParser(description="v8 self-hosted runner 本地守护")
    parser.add_argument("--heal", action="store_true", help="执行自动修复动作")
    parser.add_argument("--push", action="store_true", help="状态变更后推送到 main")
    parser.add_argument("--clear-work", action="store_true", help="强制清空 _work 目录（危险）")
    parser.add_argument("--alert", action="store_true", help="异常时发邮件告警")
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
    github = check_github_runs(token, CN_WORKFLOW_ID) if token else {"ok": False, "error": "无 token"}
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

    # ── 自愈层 ──
    actions = []
    if args.heal:
        # 1. 服务未运行则重启
        if svc["exists"] and not svc["ok"]:
            ok, msg = restart_runner_service()
            actions.append(f"重启服务: {'成功' if ok else '失败'} ({msg})")
            if ok:
                svc = check_service()  # 重新检查

        # 2. 进程缺失但服务在，也重启服务
        if not proc["ok"] and svc["ok"]:
            ok, msg = restart_runner_service()
            actions.append(f"进程缺失重启服务: {'成功' if ok else '失败'} ({msg})")
            proc = check_processes()
            svc = check_service()

        # 3. 持续 safe-delete / checkout 失败 → 清空 _work
        has_safe_delete = any(e["pattern"] == "SAFE_DELETE_BULK_CONFIRM_REQUIRED" for e in logs["errors"])
        if (has_safe_delete or github.get("checkout_failures", 0) > 0) and args.clear_work:
            ok, msg = clear_work_dir()
            actions.append(f"清空 _work: {'成功' if ok else '失败'} ({msg})")
        elif has_safe_delete or github.get("checkout_failures", 0) > 0:
            actions.append("建议：清空 _work 目录并重启服务（加 --clear-work 执行）")

        # 4. runner 完全不可用 → dispatch fallback 到云端 ubuntu（中国数据可能抓不到，但好过没有）
        if not svc["ok"] and not proc["ok"] and token:
            ok, msg = dispatch_fallback_workflow(token, CN_WORKFLOW_ID, {"category": "intraday"})
            actions.append(f"dispatch cn_fetch fallback: {'成功' if ok else '失败'} ({msg})")
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

    # ── 告警 ──
    if args.alert and overall in ("warn", "fail"):
        subject = f"【v8 runner {'故障' if overall=='fail' else '告警'}】{now_cst().strftime('%m-%d %H:%M')}"
        lines = [
            f"runner 本地守护检测到 {overall.upper()} 状态",
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

    print(f"[INFO] v8_runner_guard done")
    sys.exit(0 if overall == "ok" else 2)


if __name__ == "__main__":
    main()
