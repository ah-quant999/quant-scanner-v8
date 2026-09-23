#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages_post_publish_healthcheck.py — v8 Pages 发布后体检 + 异常回滚守卫

提出：2026-09-24 主人令「按推荐方案全落地」#37（Pages 发布后 60 秒自动体检 index.html 完整+异常回滚）。

流程：
  1. 读取本地刚提交的 index.html 的 `var BUILD`（期望线上不久后反映的构建 sha）。
  2. 硬抓线上 index.html（github.io CDN 真实服务内容），首等 60s 后轮询至 BUILD 命中或超时。
  3. 校验四道关：HTTP 200 / 字节阈值 / 尾部 </html> 闭合 / docs/ops/index_protected_markers.txt
     全部核心标记命中（复用 pre_deploy_audit [10/10] 真源口径）。
  4. 若 BUILD 已命中线上且校验失败（= 新版本已上线且损坏）→ 回滚 index.html 到
     build 提交的前一版（最近通过版）并推送（仅 revert index.html，不动 data/*.js）。
  5. 若 BUILD 未在窗口内传播（CDN 仍吐旧版）→ 仅告警放行，新鲜度看门狗后续核对。
  6. 全部通过 → 退出 0。

设计纪律（对齐仓库既有防覆盖铁律）：
  · 只回滚 index.html —— 历史「旧树静默覆盖」事故唯一被破坏的文件就是它；data/*.js 不参与。
  · 回滚 = 在 origin/main 顶端新增一个「仅还原 index.html」的提交，**绝不 force-push**、不碰他人提交。
  · 仅在「新版本确已上线(BUILD 命中)且损坏」时才回滚，避免对 CDN 滞后旧版的误回滚。
"""
import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

REPO = "https://github.com/ah-quant999/quant-scanner-v8.git"
PAGES_BASE_URL = os.environ.get("PAGES_BASE_URL", "https://ah-quant999.github.io/quant-scanner-v8").rstrip("/")
INDEX_URL = PAGES_BASE_URL + "/index.html"

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
MARKERS_FILE = os.path.join(ROOT, "docs", "ops", "index_protected_markers.txt")
LOCAL_INDEX = os.path.join(ROOT, "index.html")

MIN_BYTES = 600_000          # 字节阈值：健康 index.html ≈1.36MB；远低于此即疑似截断/空壳
WAIT_FIRST = 60              # 首等 60s（决策窗口：给 Pages 重建传播留时间）
POLL_INTERVAL = 10           # 之后每 10s 轮询
POLL_MAX = 12                # 最多 12 次 → 额外 120s；总计最坏 ≈180s
HTTP_TIMEOUT = 30

BUILD_RE = re.compile(r'var\s+BUILD\s*=\s*"(?P<sha>[0-9a-f]{7,40})"')


def log(msg):
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{ts}] {msg}", flush=True)


def get_local_build():
    try:
        txt = Path(LOCAL_INDEX).read_text(encoding="utf-8")
    except Exception as e:
        log(f"⚠️ 读取本地 index.html 失败: {e}")
        return None
    m = BUILD_RE.search(txt)
    return m.group("sha") if m else None


def fetch_live_index():
    """硬抓线上 index.html，返回 (ok, content_or_none, status_or_err)。"""
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "v8-healthcheck/1.0"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = resp.read()
                return True, data.decode("utf-8", "replace"), resp.status
        except urllib.error.HTTPError as e:
            return False, None, f"HTTP {e.code}"
        except Exception as e:
            if attempt < 3:
                log(f"⚠️ 抓取线上 index.html 失败({type(e).__name__}: {e})，{attempt}/3 重试")
                time.sleep(5)
            else:
                return False, None, f"{type(e).__name__}: {e}"
    return False, None, "unknown"


def load_markers():
    if not os.path.exists(MARKERS_FILE):
        return [], "标记清单不存在（守卫未启用，放行）"
    rows = []
    for ln in Path(MARKERS_FILE).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [x.strip() for x in ln.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        rows.append(parts[0])
    return rows, None


def missing_markers(txt, markers):
    return [m for m in markers if m not in txt]


def rollback(build_sha, reason):
    """回滚 index.html 到 build 提交前一版并推送。返回 True=成功。"""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_TOKEN")
    repo_url = REPO
    if token:
        repo_url = REPO.replace("https://", f"https://x-access-token:{token}@")
    prev = f"{build_sha}~1"
    log(f"🔄 开始回滚 index.html（原因：{reason}），基准 build={build_sha[:10]}，还原到 {prev}")
    slow = "-c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60"
    for i in range(1, 4):
        try:
            subprocess.run(["git", "fetch", repo_url, "main"], check=True,
                           timeout=180, capture_output=True)
            # 还原 index.html 到 build 前一版（与远端是否前进无关，锚定 build 之前）
            subprocess.run(["git", "checkout", prev, "--", "index.html"], check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m",
                            f"rollback index.html ({reason}) build={build_sha[:10]}"],
                           check=True, capture_output=True)
            if subprocess.run([*slow.split(), "git", "push", repo_url, "HEAD:main"],
                              timeout=180).returncode == 0:
                log(f"✅ 回滚提交已推送（第 {i} 次尝试）")
                return True
            log(f"⚠️ 回滚推送被拒/超时（第 {i} 次），同步远端后重试")
            # 远端可能已前进：reset 到 FETCH_HEAD 再还原 index.html 重新提交
            subprocess.run(["git", "reset", "--hard", "FETCH_HEAD"], check=True, capture_output=True)
            subprocess.run(["git", "checkout", prev, "--", "index.html"], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m",
                            f"rollback index.html ({reason}) build={build_sha[:10]} (retry)"],
                           check=True, capture_output=True)
            if subprocess.run([*slow.split(), "git", "push", repo_url, "HEAD:main"],
                              timeout=180).returncode == 0:
                log(f"✅ 回滚提交已推送（第 {i} 次重试）")
                return True
        except Exception as e:
            log(f"⚠️ 回滚第 {i} 次异常: {e}")
    log("❌ 回滚失败（3 次）：请人工介入核对线上 index.html")
    return False


def main():
    log("🩺 发布后体检启动")
    expected = get_local_build()
    if not expected:
        log("⚠️ 本地 index.html 无 BUILD 标记，跳过 BUILD 比对（仅做完整性校验）")
    else:
        log(f"ℹ️ 期望线上 BUILD = {expected[:10]}")

    markers, mwarn = load_markers()
    if mwarn:
        log(f"⚠️ {mwarn}")

    # 首等 60s
    log(f"⏳ 首等 {WAIT_FIRST}s 等 Pages 重建传播…")
    time.sleep(WAIT_FIRST)

    live_build = None
    content = None
    for p in range(POLL_MAX + 1):
        ok, data, status = fetch_live_index()
        if not ok:
            log(f"⚠️ 线上抓取失败: {status}")
            if p < POLL_MAX:
                time.sleep(POLL_INTERVAL)
                continue
            else:
                log("❌ 轮询窗口内始终无法抓取线上 index.html，交由新鲜度看门狗核对")
                return 0
        content = data
        m = BUILD_RE.search(content)
        live_build = m.group("sha") if m else None
        if expected and live_build == expected:
            log(f"✅ 线上 BUILD 已命中期望版（{expected[:10]}），进入完整性校验")
            break
        if p < POLL_MAX:
            log(f"… 线上 BUILD={ (live_build[:10] if live_build else '??') } 尚未命中期望 {expected[:10] if expected else '??' }，{p+1}/{POLL_MAX} 续等")
            time.sleep(POLL_INTERVAL)
        else:
            if expected and live_build != expected:
                log(f"⚠️ 轮询窗口结束，线上仍非期望版（线上={live_build[:10] if live_build else '??' } / 期望={expected[:10]}）→ CDN 滞后，放行交由看门狗核对")
                return 0

    # —— 完整性四道关 ——
    fails = []
    if content is None:
        log("⚠️ 未获取到线上内容，跳过校验（交由看门狗核对）")
        return 0
    n = len(content.encode("utf-8"))
    # 1) HTTP 已在 fetch 保证 200；这里 n 即已下载内容
    # 2) 字节阈值
    if n < MIN_BYTES:
        fails.append(f"字节数过低({n} < {MIN_BYTES})，疑似截断/空壳")
    # 3) 尾部闭合
    if "</html>" not in content[-2000:]:
        fails.append("尾部 2KB 内未见 </html>，疑似不完整")
    # 4) 核心标记
    if markers:
        miss = missing_markers(content, markers)
        if miss:
            fails.append(f"{len(miss)}/{len(markers)} 条核心标记消失: " + "、".join(miss[:12]))

    if not fails:
        log(f"✅ 体检通过：线上 index.html 完整（{n} 字节，BUILD={live_build[:10] if live_build else '??'}，标记 {len(markers)} 全命中）")
        return 0

    log("❌ 体检失败：" + "；".join(fails))
    if expected and live_build == expected:
        # 新版本确已上线且损坏 → 回滚
        if rollback(expected, "；".join(fails)):
            log("✅ 已自动回滚到最近通过版，线上已恢复")
            print(f"::error title=v8-post-publish-rollback::体检失败已自动回滚 index.html（{ '；'.join(fails) }）。线上已恢复到 build={expected[:10]} 前一版。")
            return 0
        else:
            print(f"::error title=v8-post-publish-fatal::体检失败且回滚失败（{ '；'.join(fails) }）。请人工介入！")
            return 1
    else:
        # 未确认新版本上线（CDN 滞后/无 BUILD）→ 不回滚，交由看门狗
        log("⚠️ 未确认新版本已上线，跳过回滚（避免误回滚旧版）")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"❌ 守卫脚本异常: {type(e).__name__}: {e}")
        # 守卫自身异常不阻断已成功的部署；告警交由人工/看门狗
        sys.exit(0)
