#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_local_mirror.py — 把主站（GitHub Pages）最新 index.html + data/*.js 同步到本地镜像目录
                                                        (2026-08-31 小九)

用途：E:/workspace/quant-scanner-v8/index.html 的"本地版"必须与主站一致，
      否则本地打开看到的是旧页面/旧数据。本脚本一次性拉齐：
        1) index.html    ← GitHub raw main
        2) data/*.js     ← GitHub Pages 线上（按 index.html 里 src="data/xxx.js" 清单）

用法：
    python scripts/sync_local_mirror.py                # 默认镜像到 E:/workspace/quant-scanner-v8
    python scripts/sync_local_mirror.py D:/somewhere   # 指定目录

注意：
    - 网络一律走 curl 子进程（沙箱内 python urllib 会 SSL handshake timeout）。
    - 只覆盖 index.html 与 data/*.js，不动 HANDOVER_*.md / URGENT_*.md 等交接文档。
"""
import os, re, sys, subprocess, shutil, time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://ah-quant999.github.io/quant-scanner-v8"
RAW_INDEX = "https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/index.html"
DEFAULT_TARGET = r"E:/workspace/quant-scanner-v8"

# 超时阶梯（2026-09-01 加固）：首轮 60s（正常情况下 raw.githubusercontent 秒回、
# 整个 945KB 的 index.html 也就几秒），后续重试逐级放宽。
# 起因：实测出现过「连接 stalled —— 60s 内收到 0/945,808 B，但连接其实活着只是极慢」，
# 固定 60s 会让 4 次重试全部超时、白跑 5m42s 后才中止；紧接着手动重跑 2m0s 就成功。
# 结论：慢 ≠ 断，重试必须放宽超时，否则重试等于无效重试。
TIMEOUTS = (60, 120, 180, 240)
TIMEOUT = TIMEOUTS[0]  # 兼容旧调用


def _curl_to_file(url, tmp, timeout):
    """方式A：curl -o 直接落盘（快，省内存）。"""
    r = subprocess.run(
        ["curl", "-sS", "--max-time", str(timeout), "-o", tmp, url],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if r.returncode != 0 or not os.path.exists(tmp):
        raise RuntimeError(f"rc={r.returncode} {(r.stderr or '').strip()[:80]}")
    return os.path.getsize(tmp)


def _curl_pipe(url, tmp, timeout):
    """方式B（退路）：curl 管道直喂 stdout，由 python 写盘。

    沙箱环境里 `curl -o 落盘` 会被拦截，报 `curl: (23) client returned ERROR on write`
    甚至 `(28) 超时`，但 HTTP 其实是 200、连接是通的——失败发生在【写文件】这一步。
    此时改用管道把响应体读进内存再写盘即可绕过。
    """
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                       capture_output=True)
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace").strip()[:80]
        raise RuntimeError(f"pipe rc={r.returncode} {err}")
    body = r.stdout
    if not body:
        raise RuntimeError("pipe empty body")
    with open(tmp, "wb") as f:
        f.write(body)
    return len(body)


def fetch(url, dest, timeout=None, tries=None):
    """用 curl 下载；成功返回字节数，失败返回 -1。
    带重试：GitHub Pages 在国内链路上偶发 (56) Connection reset / 超时，
    单次失败不代表文件缺失，重试可消除误报告警。
    每轮先试 `-o 落盘`，失败再退到 `管道直喂`（见 _curl_pipe 注释）。

    超时按 TIMEOUTS 阶梯递增：慢连接（stalled 但活着）用首轮 60s 会恒失败，
    重试时必须放宽，否则 4 次重试等于 4 次无效重试。
    """
    if tries is None:
        tries = len(TIMEOUTS)
    last_err = ""
    for attempt in range(tries):
        tmo = TIMEOUTS[attempt] if attempt < len(TIMEOUTS) else TIMEOUTS[-1]
        tmp = dest + ".tmp"
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            try:
                size = _curl_to_file(url, tmp, tmo)
            except Exception as e_a:
                last_err = f"A:{e_a}"
                if os.path.exists(tmp):
                    os.remove(tmp)
                size = _curl_pipe(url, tmp, tmo)
            if size == 0:
                os.remove(tmp)
                raise RuntimeError("empty body")
            os.replace(tmp, dest)
            return size
        except Exception as e:
            last_err = f"{last_err} | B:{e}"
            if attempt == tries - 1:
                if os.path.exists(tmp):
                    os.remove(tmp)
                print(f"[sync] ⚠️ 下载失败 {os.path.basename(dest)}: {last_err[:160]}")
                return -1
            time.sleep(2 * (attempt + 1))
    return -1


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    os.makedirs(target, exist_ok=True)
    data_dir = os.path.join(target, "data")
    os.makedirs(data_dir, exist_ok=True)

    print(f"[sync] 目标目录: {target}")

    # 1) index.html（先拉主站原始版，用于解析 data 清单）
    idx_path = os.path.join(target, "index.html")
    n = fetch(RAW_INDEX, idx_path)
    if n < 0:
        print("[sync] ❌ index.html 下载失败，中止")
        return 2
    if "<!DOCTYPE" not in open(idx_path, encoding="utf-8", errors="replace").read(200).upper():
        print("[sync] ❌ index.html 内容异常（非 HTML），中止")
        return 2
    print(f"[sync] ✅ index.html  {n:,} bytes")

    # 2) 解析 data 清单
    src = open(idx_path, encoding="utf-8", errors="replace").read()
    names = sorted(set(re.findall(r'src="data/([A-Za-z0-9_\-]+\.js)', src)))
    print(f"[sync] 需同步 data/*.js 共 {len(names)} 个")

    def one(name):
        url = f"{BASE_URL}/data/{name}"
        dest = os.path.join(data_dir, name)
        size = fetch(url, dest)
        if size > 0:
            # 防 GitHub Pages 404 页面被当成数据落盘（404 HTML 会被 curl 以 200/404 返回体写入）
            with open(dest, "rb") as f:
                head = f.read(4096)
            # 注意：不能匹配完整的 "<!DOCTYPE html>"（单空格）——实测本仓 index.html 头部是
            # "<!DOCTYPE  html>"（DOCTYPE 与 html 之间有两个空格），严格串匹配会假阴性漏判。
            # 一律只比首 9 字节的 "<!DOCTYPE"（大小写不敏感）或前 200 字节含 "<html"。
            if head[:9].upper().startswith(b"<!DOCTYPE") or b"<html" in head[:200].lower():
                os.remove(dest)
                return name, -1
        return name, size

    ok, fail = 0, []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, size in ex.map(one, names):
            if size < 0:
                fail.append(name)
            else:
                ok += 1
    print(f"[sync] ✅ data 同步完成 {ok}/{len(names)}")
    if fail:
        print(f"[sync] ⚠️ 失败 {len(fail)} 个: {', '.join(fail[:10])}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
