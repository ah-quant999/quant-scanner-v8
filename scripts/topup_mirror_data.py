#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""topup_mirror_data.py — 定向补齐本地镜像里落后于线上/Pages 的 data/*.js。

背景：sync_local_mirror.py 整轮跑 3 分钟，若正好跨越 GitHub Pages 的部署窗口
（push → Pages 构建完成有 1~3 分钟延迟），会抓到「部署前」的 data 内容。
本脚本只对"与 origin/main 不一致且被 index.html 引用"的文件做补拉，
不动 index.html（避免因 raw.githubusercontent 缓存把已一致的主文件拉回旧版）。

红线：curl 绝不与 --retry 同用于管道（残包追加进同一 stdout → sha 变垃圾值）。
"""
import os, re, sys, subprocess, shutil, time

BASE = "https://ah-quant999.github.io/quant-scanner-v8"
DATA = r"E:/workspace/quant-scanner-v8/data"
INDEX = r"E:/workspace/quant-scanner-v8/index.html"
REPO = r"C:/Users/Administrator/qs8-tmp"


def git(args):
    return subprocess.run(["git"] + args, cwd=REPO, capture_output=True, text=True).stdout.strip()


def referenced():
    src = open(INDEX, encoding="utf-8", errors="replace").read()
    return sorted(set(re.findall(r'src="data/([A-Za-z0-9_\-]+\.js)', src)))


def local_blob(path):
    return git(["hash-object", path])


def main():
    names = referenced()
    stale = []
    for n in names:
        p = os.path.join(DATA, n)
        if not os.path.exists(p):
            stale.append(n)
            continue
        remote = git(["rev-parse", f"origin/main:data/{n}"])
        if remote and remote != local_blob(p):
            stale.append(n)
    print(f"[topup] 引用 {len(names)} 个，落后 {len(stale)} 个: {', '.join(stale) if stale else '(无)'}")

    ok, fail = 0, []
    for n in stale:
        dest = os.path.join(DATA, n)
        tmp = dest + ".tmp"
        got = False
        for attempt in range(3):
            r = subprocess.run(["curl", "-sS", "--max-time", "60", f"{BASE}/data/{n}"],
                               capture_output=True)
            body = r.stdout
            if r.returncode == 0 and body:
                if body[:9].upper().startswith(b"<!DOCTYPE") or b"<html" in body[:200].lower():
                    print(f"[topup] SKIP {n}: 拿到的是 HTML(404) 页面，放弃")
                    break
                with open(tmp, "wb") as f:
                    f.write(body)
                os.replace(tmp, dest)
                got = True
                ok += 1
                print(f"[topup] OK   {n}  {len(body):,} B")
                break
            time.sleep(3)
        if not got:
            fail.append(n)
            if os.path.exists(tmp):
                os.remove(tmp)
    print(f"[topup] 补齐 {ok}/{len(stale)}" + (f"，失败: {', '.join(fail)}" if fail else ""))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
