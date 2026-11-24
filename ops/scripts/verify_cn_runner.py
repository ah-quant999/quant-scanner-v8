#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
九宝量化 v8 — 双 cn runner 自审/对比脚本
===========================================
用途: 验证 GitHub Actions self-hosted runners (label=cn) 数量、在线状态,
      对比云端 raw_data/* 关键盘中模块的 update_time, 给出健康报告.

用法:
    # 1. 需要 GitHub PAT (有 repo 读权限)
    set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    # 2. 直接跑
    python verify_cn_runner.py
    # 或
    python verify_cn_runner.py --repo ah-quant999/quant-scanner-v8

退出码:
    0 = 健康 (>=1 个 cn runner online + raw_data 盘中模块 < 30 分钟)
    1 = 警告 (0 cn runner 但 fallback OK)
    2 = 失败 (0 cn runner + raw_data 盘中模块 > 45 分钟)

不做修改: 只读 GitHub API + git cat-file, 不写任何文件.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("[X] 需要 requests: pip install requests", file=sys.stderr)
    sys.exit(99)

CST = timezone(timedelta(hours=8))
INTRADAY_KEY_FILES = [
    "raw_data/index_quotes.json",
    "raw_data/sector_fund_flow.json",
    "raw_data/etf_pulse.json",
    "raw_data/limit_up_heatmap.json",
    "raw_data/avg_price_data.json",
]


def now_cst():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def hr(title):
    print()
    print("=" * 64)
    print(f" {title}")
    print("=" * 64)


def list_runners(repo, token):
    """GET /repos/{owner}/{repo}/actions/runners — 列所有 self-hosted runners"""
    url = f"https://api.github.com/repos/{repo}/actions/runners"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "v8-cn-runner-verify",
    }
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code == 401:
        print("[X] GitHub token 无效或无 repo 读权限", file=sys.stderr)
        return None
    r.raise_for_status()
    return r.json().get("runners", [])


def filter_cn_runners(runners):
    out = []
    for r in runners or []:
        labels = [l.get("name") for l in r.get("labels", [])]
        if "cn" in labels:
            out.append({
                "name": r.get("name"),
                "os": r.get("os"),
                "status": r.get("status"),  # online | offline
                "busy": r.get("busy"),
                "labels": labels,
                "groups": [g.get("name") for g in r.get("runner_groups", [])],
                "last_contact": r.get("last_contact", {}).get("graphql_field_name")
                                or r.get("last_contact_aware_at"),
            })
    return out


def raw_data_freshness(repo="origin/main"):
    """读 git 远端 raw_data/ 关键盘中模块的 update_time"""
    out = []
    for f in INTRADAY_KEY_FILES:
        try:
            r = subprocess.run(
                ["git", "show", f"{repo}:{f}"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                out.append({"file": f, "update_time": None, "status": "MISSING"})
                continue
            data = json.loads(r.stdout)
            ts = data.get("update_time")
            out.append({"file": f, "update_time": ts, "status": "OK"})
        except Exception as e:
            out.append({"file": f, "update_time": None, "status": f"ERR:{e}"})
    return out


def age_minutes(ts_str):
    if not ts_str:
        return None
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
        return (datetime.now(CST) - dt).total_seconds() / 60
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="ah-quant999/quant-scanner-v8")
    p.add_argument("--warn-min", type=int, default=30,
                   help="盘中模块超 N 分钟报黄, 默认 30")
    p.add_argument("--fail-min", type=int, default=45,
                   help="盘中模块超 N 分钟报红, 默认 45")
    args = p.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[X] 需要环境变量 GITHUB_TOKEN (PAT, 含 repo:read 权限)", file=sys.stderr)
        print("    临时设: set GITHUB_TOKEN=ghp_xxx", file=sys.stderr)
        sys.exit(99)

    hr(f"v8 cn runner 自审报告 · {now_cst()}")

    # ---- 1. Runners 列表 ----
    runners = list_runners(args.repo, token)
    cn = filter_cn_runners(runners)
    online = [r for r in cn if r["status"] == "online"]

    print(f"\n[Runners] 共 {len(runners)} 台 self-hosted, 其中 cn 标签 {len(cn)} 台")
    if cn:
        for r in cn:
            mark = "🟢" if r["status"] == "online" else ("🟡" if r["busy"] else "🔴")
            print(f"  {mark} {r['name']:<24} status={r['status']:<8} "
                  f"busy={r['busy']!s:<5} groups=[{','.join(r['groups'])}] "
                  f"labels=[{','.join(r['labels'])}]")
    else:
        print("  ⚠️ 没有任何 cn 标签 runner 已注册(快去 Setup!)")

    # ---- 2. raw_data 新鲜度 ----
    hr("raw_data 关键盘中模块新鲜度")
    items = raw_data_freshness()
    any_overdue = False
    any_far_overdue = False
    for it in items:
        if it["status"] != "OK":
            print(f"  ❌ {it['file']:<42} {it['status']}")
            any_overdue = True
            continue
        age = age_minutes(it["update_time"])
        if age is None:
            print(f"  ❓ {it['file']:<42} update_time 解析失败")
            continue
        if age > args.fail_min:
            mark = "🔴"; any_overdue = True; any_far_overdue = True
        elif age > args.warn_min:
            mark = "🟡"; any_overdue = True
        else:
            mark = "🟢"
        print(f"  {mark} {it['file']:<42} {it['update_time']} "
              f"({age:>5.1f} 分钟前)")

    # ---- 3. 决策 ----
    hr("决策")
    if len(online) == 0 and any_far_overdue:
        print("  🔴 FAIL: 0 个 cn runner online 且盘中数据严重过期")
        print("     → v8_health_patrol 会 dispatch self-heal, 但 self-heal 也派发到 cn runner")
        print("     → 如果所有 cn runner 都掉, 数据会被 fallback 到 ubuntu-latest 抓 (美国 IP, 概率性)")
        sys.exit(2)
    if len(online) == 0 and any_overdue:
        print("  🟡 WARN: cn runner 离线中, 靠 ubuntu-latest 兜底, 数据有延迟")
        sys.exit(1)
    if any_far_overdue:
        print("  🔴 FAIL: 有 cn runner 但数据仍过期 > 45 分钟 (检查抓取脚本)")
        sys.exit(2)
    if any_overdue:
        print("  🟡 WARN: 数据新鲜但已 > 30 分钟(单 runner 队列拥挤或某个槽位漏跑)")
        sys.exit(1)
    print("  🟢 OK: cn runner 在线 + 盘中数据新鲜")
    sys.exit(0)


if __name__ == "__main__":
    main()