#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计：本地镜像的 data/*.js（来自 GitHub Pages）是否与 origin/main 的 data/*.js 一致。

背景（2026-09-01）：sync_local_mirror.py 的 index.html 取自 raw.githubusercontent(main)，
而 data/*.js 取自 GitHub Pages(ah-quant999.github.io)。两条链路不同源：
若 Pages 尚未 rebuild，Pages 上的 data 会滞后于 main —— index.html 是新版的、数据却是旧的，
且这种脱节在「只校验 index.html sha」的流程里完全看不出来。

实现：直接读 git 对象（git show origin/main:data/XXX.js）比对 sha256，零网络开销、全量覆盖。
"""
import hashlib
import os
import re
import subprocess

REPO = r"C:/Users/Administrator/qs8-tmp"
MIRROR = r"E:/workspace/quant-scanner-v8"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    idx_path = os.path.join(MIRROR, "index.html")
    src = open(idx_path, encoding="utf-8", errors="replace").read()
    names = sorted(set(re.findall(r'src="data/([A-Za-z0-9_\-]+\.js)', src)))

    same, diff, missing_on_main, missing_local = [], [], [], []

    for n in names:
        local_path = os.path.join(MIRROR, "data", n)
        if not os.path.exists(local_path):
            missing_local.append(n)
            continue

        r = subprocess.run(
            ["git", "show", f"origin/main:data/{n}"],
            cwd=REPO, capture_output=True,
        )
        if r.returncode != 0:
            missing_on_main.append(n)
            continue

        local_b = open(local_path, "rb").read()
        main_b = r.stdout
        if sha(local_b) == sha(main_b):
            same.append(n)
        else:
            diff.append((n, len(local_b), len(main_b)))

    print(f"[audit] index.html 引用 data/*.js 共 {len(names)} 个")
    print(f"[audit] Pages 与 main 一致 : {len(same)}")
    print(f"[audit] 不一致(Pages滞后?) : {len(diff)}")
    print(f"[audit] main 上不存在      : {len(missing_on_main)}")
    print(f"[audit] 本地缺失           : {len(missing_local)}")

    if diff:
        print("\n=== 不一致明细（Pages 字节数 / main 字节数）===")
        for n, a, b in diff:
            print(f"  {n:<38} pages={a:>10,}  main={b:>10,}  delta={b - a:+,}")
    if missing_on_main:
        print("\n=== main 上不存在 ===")
        for n in missing_on_main:
            print(f"  {n}")
    if missing_local:
        print("\n=== 本地镜像缺失 ===")
        for n in missing_local:
            print(f"  {n}")

    if not diff and not missing_on_main and not missing_local:
        print("\n[audit] PASS GitHub Pages 的 data/*.js 与 origin/main 完全一致（Pages 已跟上 main）")
        return 0
    print("\n[audit] WARN 存在脱节，见上方明细")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
