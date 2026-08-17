# -*- coding: utf-8 -*-
"""
v8_runner_guard.py — 永久守护 alimi-cn runner
每 5 分钟检查 GitHub runner 状态，离线立刻拉起。
依赖：windows-cmd run.cmd (D:\\actions\\cn-runner\\run.cmd)
调用：python v8_runner_guard.py --check
      python v8_runner_guard.py --loop  # 后台守护
"""
import sys
import time
import subprocess
import urllib.request
import json
import argparse
from pathlib import Path

PAT_FILE = Path(r'E:\workspace\stock-scanner\data\.github_pat.txt')
REPO = 'ah-quant999/quant-scanner-v8'
RUNNER_NAME = 'alimi-cn'
RUNNER_DIR = r'D:\actions\cn-runner'
RUNNER_CMD = 'run.cmd'
GITHUB_API = f'https://api.github.com/repos/{REPO}/actions/runners'


def load_pat():
    if PAT_FILE.exists():
        return PAT_FILE.read_text().strip()
    import os
    return os.environ.get('GITHUB_TOKEN', '')


def get_runner_status():
    pat = load_pat()
    if not pat:
        return None
    req = urllib.request.Request(GITHUB_API, headers={
        'Authorization': f'Bearer {pat}',
        'Accept': 'application/vnd.github+json'
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    for runner in d.get('runners', []):
        if runner.get('name') == RUNNER_NAME:
            return runner
    return None


def is_runner_alive():
    """检查 Windows 进程 Runner.Listener / Runner.Worker 是否在跑"""
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             "Get-Process | Where-Object { $_.Name -like '*Runner*' } | Select-Object -ExpandProperty Name"],
            timeout=10
        ).decode('utf-8', 'replace')
        return 'Runner.Listener' in out and 'Runner.Worker' in out
    except Exception:
        return False


def start_runner():
    """启动 runner（后台）"""
    log_path = Path(RUNNER_DIR) / '_diag' / 'guard_start.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'Set-Location {RUNNER_DIR}; Start-Process -FilePath "D:\\actions\\cn-runner\\{RUNNER_CMD}" -WorkingDirectory "D:\\actions\\cn-runner" -RedirectStandardOutput "{log_path}" -RedirectStandardError "{log_path}"'
    try:
        subprocess.Popen(['powershell', '-NoProfile', '-Command', cmd],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        print(f'拉起失败: {e}', file=sys.stderr)
        return False


def check_once():
    runner = get_runner_status()
    status = (runner or {}).get('status', 'unknown')
    alive_local = is_runner_alive()
    needs_start = (status == 'offline') or (not alive_local and status == 'online')
    print(f'[{time.strftime("%H:%M:%S")}] {RUNNER_NAME}: GitHub={status} | 本地进程={alive_local} | 需要拉起={needs_start}')
    if needs_start:
        if start_runner():
            print(f'  ✅ 已发起拉起命令')
            time.sleep(15)
            new_status = get_runner_status() or {}
            print(f'  拉起后状态: {new_status.get("status", "?")}')
        else:
            print(f'  ❌ 拉起失败')
    return not needs_start


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true', help='只检查一次')
    p.add_argument('--loop', action='store_true', help='循环守护（每 5 分钟）')
    p.add_argument('--interval', type=int, default=300, help='循环间隔秒数')
    args = p.parse_args()

    if args.check:
        ok = check_once()
        sys.exit(0 if ok else 1)
    elif args.loop:
        print(f'v8_runner_guard 启动，每 {args.interval}s 检查一次')
        while True:
            try:
                check_once()
            except Exception as e:
                print(f'检查异常: {e}', file=sys.stderr)
            time.sleep(args.interval)
    else:
        # 默认 check 一次
        ok = check_once()
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
