#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_weekend_light.py — 周末轻量维护（v8 去 v6 化版）
====================================================
周末不抓行情、不改任何数据时间戳，仅：
1. 读取最新交接/紧急文件（复用 auto_handoff_read.py）；
2. 生成/更新 data/WEEKEND_RUN.js 标注；
3. dispatch v8_build_deploy.yml 重新部署站点。

用法:
  python v8_weekend_light.py              # 执行维护
  python v8_weekend_light.py --dry-run    # 仅打印，不 dispatch
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = "ah-quant999/quant-scanner-v8"
WEEKEND_JS = BASE / "data" / "WEEKEND_RUN.js"


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


def read_handoff():
    try:
        r = subprocess.run(
            [sys.executable, "auto_handoff_read.py"],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        return r.returncode, r.stdout
    except Exception as e:
        return 1, f"auto_handoff_read.py 调用失败: {e}"


def write_weekend_run():
    now = datetime.now()
    wk_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    wk_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][now.weekday()]
    data = {
        "last_run": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": wk_cn,
        "weekday_en": wk_en,
        "note": "周末轻量维护已执行（数据仍为最近交易日收盘）",
    }
    WEEKEND_JS.write_text(
        f"window.WEEKEND_RUN = {json.dumps(data, ensure_ascii=False)};\n",
        encoding="utf-8",
    )
    print(f"✅ 已更新 {WEEKEND_JS} ({wk_cn} {data['last_run']})")
    return data


def dispatch_build_deploy():
    token = _load_token()
    if not token:
        print("❌ 未找到 GitHub token，无法 dispatch build_deploy")
        return False
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/v8_build_deploy.yml/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
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
            print(f"✅ 已 dispatch v8_build_deploy.yml (HTTP {r.status})")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ dispatch 失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        return False
    except Exception as e:
        print(f"❌ dispatch 异常: {e}")
        return False


def refresh_stock_metadata():
    """周度全量股票基础元数据巡检：新股上市/退市检测，并更新行业/概念/拼音映射。"""
    script = BASE / "algorithms" / "refresh_stock_metadata.py"
    if not script.exists():
        print(f"  ⚠️ 缺失 {script}，跳过元数据巡检")
        return 1
    print(f"  ▶ 运行 {script.name}")
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BASE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=1200,
    )
    tail = "\n".join((r.stdout or "").strip().splitlines()[-20:])
    if tail:
        print("  " + tail.replace("\n", "\n  "))
    if r.returncode != 0:
        err = "\n".join((r.stderr or "").strip().splitlines()[-10:])
        print(f"  ⚠️ 元数据巡检退出码 {r.returncode}: {err}")
    return r.returncode


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"# v8 周末轻量维护 ({now})")

    # 1. 读交接
    print("\n## 最新交接/紧急文件")
    rc, out = read_handoff()
    print(out[:2000])

    # 2. 周度股票基础元数据巡检（新股/退市/行业/概念/拼音）
    print("\n## 周度股票基础元数据巡检（不抓行情）")
    if dry:
        print("[DRY-RUN] 将运行 refresh_stock_metadata.py")
    else:
        refresh_stock_metadata()

    # 3. 写 WEEKEND_RUN.js
    print("\n## 注入 WEEKEND_RUN 标注")
    if dry:
        now = datetime.now()
        print(f"[DRY-RUN] 将写入 {WEEKEND_JS}: {now.strftime('%Y-%m-%d %H:%M:%S')} {['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]}")
    else:
        write_weekend_run()

    # 4. dispatch build_deploy
    print("\n## 触发部署")
    if dry:
        print("[DRY-RUN] 将 dispatch v8_build_deploy.yml")
    else:
        dispatch_build_deploy()

    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
