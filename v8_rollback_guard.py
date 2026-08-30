#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 防回滚 / 结构完整性自检（v8_rollback_guard.py）

设计目标（2026-08-30 主人令「别让小九明天开盘一无所知、别回滚回旧版」）：
  现有自愈器（v8_health_patrol.yml / self_heal_monitor.py）只盯【数据卡新鲜度】，
  不能发现「index.html / 关键脚本被回退到旧版（旧 bug 复现）」这类【结构回归】。
  本脚本补这一环——开盘前（阿狸咪 7:25 窗口，早于小九 7:45）校验结构完整性，
  一旦检测到一劳永逸修复被回退 / 关键文件被坚果云删丢，立即【从 origin/main 安全还原】。

安全铁律：
  1. 只【还原】（git checkout origin/main -- <file>），绝不 git reset --hard、绝不 force push。
     origin/main 即权威（所有一劳永逸修复已在其上），还原 = 回到正确版本，非破坏性。
  2. 仅当【关键标记确实缺失】才还原 index.html；缓存戳 ?v 差异等无害改动不触发还原。
  3. 还原动作必写日志 + 退出码区分，便于自动化/微信告警呈现。
  4. 不修改任何算法/管线代码，只读 + 安全还原。

退出码：
  0 = 结构完整，无需动作
  1 = 已执行安全还原（index.html / 关键文件从 origin/main 取回）
  2 = 发现异常但无法自动修复（需人工介入，例如 origin/main 自身也缺标记）

用法：
  python v8_rollback_guard.py            # 检查 + 安全还原
  python v8_rollback_guard.py --check-only  # 仅检查不还原
  python v8_rollback_guard.py --json     # JSON 输出（供自动化消费）
"""

import json
import os
import re
import sys
import subprocess
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CST = timezone(timedelta(hours=8))

# 关键文件：本地缺失但 origin/main 有 → 安全还原（防坚果云秒删后漏推，如 wf_health.yml 事件）
CRITICAL_FILES = [
    "index.html",
    "v8_health_check.py",
    "wf_health.yml",
    "data/DELISTED.js",
    "data/UNLISTED_PANEL.js",
    "data/HEALTH_CHECK.js",
    "scripts/build_delisted.py",
    "scripts/build_unlisted_panel.py",
]

# index.html 结构标记（一劳永逸修复的"指纹"）：
#   must_present=True  → 当前版本【必须】含此串，缺失=被回退
#   must_present=False → 当前版本【必须不含】此串，存在=旧 bug 复现
STRUCTURAL_MARKERS = [
    {"name": "AI速览改持仓建议", "needle": "⚖ 持仓建议", "must_present": True},
    {"name": "已下架数据注入", "needle": "data/DELISTED.js?", "must_present": True},
    {"name": "暂未上架模块索引注入", "needle": "data/UNLISTED_PANEL.js?", "must_present": True},
    {"name": "运维nav解锁兜底", "needle": "_v8ForceUnlockAdminTabs", "must_present": True},
    {"name": "炸板6列(grid)", "needle": "repeat(6, minmax(0,1fr));gap:5px 6px", "must_present": True},
    {"name": "大盘判断去重(无stcrdsWeakSpec)", "needle": 'id="stcrdsWeakSpec"', "must_present": False},
    {"name": "平均股价真实数据", "needle": "window.AVG_PRICE_DATA", "must_present": True},
    {"name": "调试专区无个股动量状态卡", "needle": "🚀 个股动量状态", "must_present": False},
]


def now_cst():
    return datetime.now(CST)


def log(msg, level="INFO"):
    ts = now_cst().strftime("%H:%M:%S")
    line = "[" + ts + "] [" + level + "] " + msg
    if getattr(log, "to_stderr", False):
        print(line, file=sys.stderr)
    else:
        print(line)


def git(args, timeout=60):
    return subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(ROOT), timeout=timeout
    )


def fetch_origin_main():
    r = git(["fetch", "origin", "main"], timeout=90)
    return r.returncode == 0


def read_origin_file(relpath):
    """读取 origin/main 上的文件内容（git show origin/main:<path>）；不存在返回 None。"""
    r = git(["show", "origin/main:" + relpath], timeout=30)
    if r.returncode != 0:
        return None
    return r.stdout


def read_local_file(relpath):
    p = ROOT / relpath
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="v8 防回滚/结构完整性自检")
    ap.add_argument("--check-only", action="store_true", help="仅检查不还原")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()
    if args.json:
        log.to_stderr = True

    actions = []
    exit_code = 0
    report = {"timestamp": now_cst().isoformat(), "checks": [], "actions": [], "exit_code": 0}

    # 1. 拉取最新 origin/main（还原的来源必须是权威最新）
    if not fetch_origin_main():
        log("[WARN] git fetch origin main 失败，将基于缓存的 origin/main 校验", "WARN")
    else:
        log("[OK] git fetch origin main 完成", "OK")

    # 2. 校验关键文件存在性（防坚果云删除漏推）
    for f in CRITICAL_FILES:
        local = read_local_file(f)
        remote = read_origin_file(f)
        if remote is None:
            # origin/main 也没有 → 不还原（避免创建不该存在的文件）
            if local is None:
                log("[SKIP] %s 本地与 origin/main 均不存在，跳过" % f, "SKIP")
                report["checks"].append({"file": f, "status": "skip", "detail": "both missing"})
            else:
                log("[OK] %s 本地存在（origin/main 无，保留本地）" % f, "OK")
                report["checks"].append({"file": f, "status": "ok", "detail": "local only"})
            continue
        if local is None:
            # 本地被删（坚果云事件）→ 从 origin/main 安全还原
            log("[FAIL] %s 本地缺失！疑似坚果云删除，将还原" % f, "FAIL")
            report["checks"].append({"file": f, "status": "fail", "detail": "local missing"})
            if not args.check_only:
                r = git(["checkout", "origin/main", "--", f], timeout=30)
                if r.returncode == 0:
                    log("[HEAL] 已还原 %s (from origin/main)" % f, "HEAL")
                    actions.append("还原关键文件: " + f)
                else:
                    log("[FAIL] 还原 %s 失败: %s" % (f, r.stderr[-160:]), "FAIL")
                    exit_code = max(exit_code, 2)
            else:
                actions.append("需还原(未执行): " + f)
                exit_code = max(exit_code, 1)
        else:
            report["checks"].append({"file": f, "status": "ok", "detail": "present"})

    # 3. 校验 index.html 结构标记（一劳永逸修复指纹）
    local_html = read_local_file("index.html")
    remote_html = read_origin_file("index.html")
    if remote_html is None:
        log("[FAIL] origin/main:index.html 读取失败，无法校验结构", "FAIL")
        exit_code = max(exit_code, 2)
        report["checks"].append({"structural": "error", "detail": "origin/main index.html unreadable"})
    elif local_html is None:
        log("[FAIL] 本地 index.html 缺失，将还原", "FAIL")
        if not args.check_only:
            r = git(["checkout", "origin/main", "--", "index.html"], timeout=30)
            if r.returncode == 0:
                log("[HEAL] 已还原 index.html", "HEAL")
                actions.append("还原 index.html")
            else:
                exit_code = max(exit_code, 2)
        else:
            actions.append("需还原 index.html(未执行)")
            exit_code = max(exit_code, 1)
    else:
        # origin/main 自身的标记应先校验（若权威版本也缺标记，说明修复未入库，需人工）
        remote_missing = [m["name"] for m in STRUCTURAL_MARKERS
                          if (m["must_present"] and m["needle"] not in remote_html)
                          or (not m["must_present"] and m["needle"] in remote_html)]
        if remote_missing:
            log("[FAIL] origin/main 自身缺少一劳永逸标记: %s —— 需人工确认修复是否已 push" % ", ".join(remote_missing), "FAIL")
            exit_code = max(exit_code, 2)
            report["checks"].append({"structural": "fail", "detail": "origin/main missing: " + ", ".join(remote_missing)})
        else:
            # 本地对比 origin/main 标记
            local_missing = [m["name"] for m in STRUCTURAL_MARKERS
                             if (m["must_present"] and m["needle"] not in local_html)
                             or (not m["must_present"] and m["needle"] in local_html)]
            if local_missing:
                log("[FAIL] 本地 index.html 被回退，缺失标记: %s" % ", ".join(local_missing), "FAIL")
                report["checks"].append({"structural": "fail", "detail": "local reverted: " + ", ".join(local_missing)})
                if not args.check_only:
                    r = git(["checkout", "origin/main", "--", "index.html"], timeout=30)
                    if r.returncode == 0:
                        log("[HEAL] 已还原 index.html 到 origin/main（修复回退）", "HEAL")
                        actions.append("结构回退→还原 index.html")
                    else:
                        log("[FAIL] 还原 index.html 失败: %s" % r.stderr[-160:], "FAIL")
                        exit_code = max(exit_code, 2)
                else:
                    actions.append("结构回退需还原(未执行): " + ", ".join(local_missing))
                    exit_code = max(exit_code, 1)
            else:
                log("[OK] index.html 结构完整（8 项一劳永逸标记全部到位）", "OK")
                report["checks"].append({"structural": "ok", "detail": "all markers present"})

    # 4. 顺带跑数据自愈（复用既有 --heal，确保开盘前数据也新鲜）
    if not args.check_only and actions:
        # 仅当已做还原时才触发数据自愈，避免无谓运行
        hc = ROOT / "v8_health_check.py"
        if hc.exists():
            log("[RUN] 触发 v8_health_check.py --heal（数据自愈兜底）", "RUN")
            r = git if False else subprocess.run(
                ["python", str(hc), "--heal"], capture_output=True, text=True,
                cwd=str(ROOT), timeout=300
            )
            if r.returncode == 0:
                log("[OK] 数据自愈完成", "OK")
            else:
                log("[WARN] 数据自愈返回非0（%s），详见运维页" % r.returncode, "WARN")

    report["actions"] = actions
    report["exit_code"] = exit_code

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if actions:
            log("=== 自检完成：%d 项动作 ===" % len(actions), "SUMMARY")
            for a in actions:
                log("  -> " + a, "ACTION")
        else:
            log("=== 结构完整，无需动作 ===", "PASS")

    if exit_code == 1:
        log("结论：已自动还原，开盘前状态已对齐 origin/main ✅", "SUMMARY")
    elif exit_code == 2:
        log("结论：发现无法自动修复的异常，需人工介入（见上方 FAIL）⚠️", "SUMMARY")
    else:
        log("结论：全部正常，可放心开盘 ✅", "SUMMARY")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
