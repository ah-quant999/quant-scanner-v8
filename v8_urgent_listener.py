#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_urgent_listener.py — 紧急指令监听 + 健康检查（v8 去 v6 化版）
=========================================================
监听 URGENT_*.md（docs/ops/urgent/ 与仓库根目录双位置），读取最新内容并：
1. 运行 guard_v8_freshness.py 生成数据新鲜度报告；
2. 根据文件内容中的关键词自动 dispatch 对应 workflow；
3. 输出摘要供 automation 向主人汇报。

用法:
  python v8_urgent_listener.py              # 扫描 + 健康检查 + 自动 dispatch
  python v8_urgent_listener.py --dry-run    # 仅打印，不真 dispatch
"""
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

BASE = Path(__file__).resolve().parent
URGENT_DIR = BASE / "docs" / "ops" / "urgent"
REPO = "ah-quant999/quant-scanner-v8"

# workflow 文件名 -> dispatch payload
WF_MAP = {
    "cn_fetch_cloud": ("v8_cn_fetch_cloud.yml", {"ref": "main"}),
    "cn_fetch":       ("v8_cn_fetch_cloud.yml", {"ref": "main"}),  # 统一走云端主力
    "algo_cloud":     ("v8_algo_cloud.yml",     {"ref": "main"}),
    "algo":           ("v8_algo_cloud.yml",     {"ref": "main"}),
    "build_deploy":   ("v8_build_deploy.yml",   {"ref": "main"}),
    "safety_net":     ("v8_safety_net.yml",     {"ref": "main"}),
    "self_heal":      ("v8_self_heal.yml",      {"ref": "main"}),
    "weekly_cleanup": ("cloud_weekly_cleanup.yml", {"ref": "main"}),
}


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


def _scan_urgent_files():
    """扫描全部 URGENT 落盘位置（去重）：
    1. docs/ops/urgent/（历史位置，v8 去 v6 化前）
    2. 仓库根目录（小九 08-10 起使用，如 URGENT_小九_2026-08-18_*.md）
    """
    paths = set()
    for d in (URGENT_DIR, BASE):
        if d.is_dir():
            for p in d.glob("URGENT_*.md"):
                paths.add(p.resolve())
    return paths


def recent_urgent_files(n=5):
    files = sorted(_scan_urgent_files(), key=os.path.getmtime, reverse=True)
    return files[:n]


def read_head(path, lines=50):
    try:
        with open(path, encoding="utf-8") as f:
            return "".join(f.readlines()[:lines])
    except Exception as e:
        return f"[读取失败: {e}]"


def run_freshness_check():
    try:
        r = subprocess.run(
            [sys.executable, "guard_v8_freshness.py"],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, f"guard_v8_freshness.py 调用失败: {e}"


def parse_dispatch_commands(text, mtime_hours=24):
    """从 urgent 文本中识别 dispatch 指令。返回 [(reason, wf_name, payload)]

    仅当文本含显式 `[ACTION]` / `!dispatch` / `# action:` 标记时才自动触发；
    普通交接/巡检文档中的历史关键词不触发，避免误 dispatch。
    """
    cmds = []
    lower = text.lower()

    # 显式指令标记
    if not re.search(r"\[ACTION\]|!dispatch|# action:|## action", lower):
        return cmds

    # 直接显式 workflow 名
    for key, (wf, payload) in WF_MAP.items():
        if re.search(rf"\bdispatch\s+{key.replace('_', '[_-]?')}\b", lower):
            cmds.append((f"显式 ACTION 指令 dispatch {key}", wf, payload))

    # 无显式 workflow 名时，按关键词推断
    if re.search(r"\b(马上刷新|立即刷新|重新抓取|数据缺失|数据没更新|cn fetch|云端抓取)\b", lower):
        if not any(c[1] == "v8_cn_fetch_cloud.yml" for c in cmds):
            cmds.append(("ACTION：刷新/数据缺失", "v8_cn_fetch_cloud.yml", {"ref": "main"}))
    if re.search(r"\b(跑算法|算法链|盘后算法|algo|v8_algo_run)\b", lower):
        if not any(c[1] == "v8_algo_cloud.yml" for c in cmds):
            cmds.append(("ACTION：算法链", "v8_algo_cloud.yml", {"ref": "main"}))
    if re.search(r"\b(重新部署|部署网站|deploy|build and deploy)\b", lower):
        if not any(c[1] == "v8_build_deploy.yml" for c in cmds):
            cmds.append(("ACTION：部署", "v8_build_deploy.yml", {"ref": "main"}))
    return cmds


def dispatch_workflow(wf_name, payload):
    token = _load_token()
    if not token:
        return False, "未找到 GitHub token"
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_name}/dispatches"
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
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, str(e)[:150]


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    out = [f"# v8 紧急指令监听 ({now})", ""]

    files = recent_urgent_files()
    out.append(f"## 最近 urgent 文件（{len(files)} 个）")
    if not files:
        out.append("- 无")
    dispatch_cmds = []
    for p in files:
        head = read_head(p, 40)
        mtime_hours = (datetime.now().timestamp() - os.path.getmtime(p)) / 3600.0
        out.append(f"- **{os.path.basename(p)}** (mtime={mtime_hours:.1f}h)")
        out.append("```markdown")
        out.append(head)
        out.append("```")
        # 只有最近 1 个文件参与自动 dispatch（避免旧文件反复触发）
        if p == files[0]:
            dispatch_cmds = parse_dispatch_commands(head, mtime_hours)

    # 健康检查
    out.append("")
    out.append("## v8 数据新鲜度")
    rc, stdout = run_freshness_check()
    out.append(f"- 检查返回码: {rc}")
    out.append("```")
    out.append(stdout[:1500])
    out.append("```")

    # 自动 dispatch
    out.append("")
    out.append("## 自动 dispatch")
    if not dispatch_cmds:
        out.append("- 最新 urgent 文件未识别到自动 dispatch 指令，无需操作。")
    else:
        for reason, wf, payload in dispatch_cmds:
            if dry:
                out.append(f"- [DRY-RUN] {reason} → 将 dispatch `{wf}` payload={payload}")
            else:
                ok, msg = dispatch_workflow(wf, payload)
                out.append(f"- {'✅' if ok else '❌'} {reason} → `{wf}`: {msg}")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
