#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_nightly.py — 每晚备份前轻量审计（聚焦 reconcile 不覆盖的盲区）。

设计定位（与现有组件分工）：
  - v8_health_check.py  : 健康面板（黄灯/红点/A股覆盖/站点同步），已独立运行。
  - reconcile_cache_busters.py : 每15分钟对齐 ?v 缓存戳（只管戳，不验证内容正确性）。
  - 本脚本 = 部署一致性 + 数据完整性 + 备份可用性（reconcile 不覆盖的盲区）。

检查项：
  1) 部署一致性：本地 data/*.js 与线上(github.io CDN) 真实字节比对（中性化换行符与
     republish_time），防"部署污染但 ?v 对了、内容却错了"。
  2) 数据完整性：data/*.js 是否被截断/清空（异常小）。
  3) 备份可用性：workbuddy.db 及其 bak_* 备份存在性。
异常时尝试触发 reconcile 自愈（仅缓存戳类），退出码 1；全过 0。
"""
import os
import re
import sys
import pathlib
import urllib.request
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://ah-quant999.github.io/quant-scanner-v8"
MIN_BYTES = 512  # data 文件小于此视为可疑截断/空


def download(url):
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "audit-nightly"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read()
    except Exception as e:
        return ("ERR", str(e))


def neut(b):
    """中性化换行符 + republish_time 时间戳，仅比内容实质差异。"""
    b = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return re.sub(rb'"republish_time"\s*:\s*"[^"]*"', b'"republish_time":""', b)


def main():
    problems = []
    print("=== 每晚轻量审计 @ %s ===" % ROOT.name)

    # 1) 部署一致性 + 2) 数据完整性
    if DATA.exists():
        for f in sorted(DATA.glob("*.js")):
            local = f.read_bytes()
            if len(local) < MIN_BYTES:
                problems.append("数据截断/过短: %s (%d 字节)" % (f.name, len(local)))
                continue
            remote = download("%s/data/%s" % (SITE, f.name))
            if isinstance(remote, tuple):
                problems.append("线上下载失败: %s -> %s" % (f.name, remote[1]))
                continue
            if neut(remote) != neut(local):
                problems.append("部署不一致: %s 本地%d字节 vs 线上%d字节" % (
                    f.name, len(local), len(remote)))
    else:
        problems.append("data 目录缺失")

    # 3) 备份可用性
    db = pathlib.Path.home() / ".workbuddy" / "workbuddy.db"
    if not db.exists():
        problems.append("workbuddy.db 缺失(备份源)")
    else:
        bak = list((pathlib.Path.home() / ".workbuddy").glob("workbuddy.db.bak_*"))
        if not bak:
            problems.append("未找到 workbuddy.db 备份(bak_*)")

    print("发现问题 %d 项：" % len(problems))
    print("\n".join(" - " + p for p in problems) or "✅ 轻量审计通过：部署一致、数据完整、备份可用")

    if problems:
        print("\n🔧 尝试触发缓存戳自愈(reconcile)…")
        try:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "reconcile_cache_busters.py")],
                           cwd=str(ROOT), timeout=120)
        except Exception as e:
            print("reconcile 触发失败: %s" % e)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
