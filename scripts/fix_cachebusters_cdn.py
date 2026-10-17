#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_cachebusters_cdn.py — 以 CDN(github.io) 真实服务内容为权威，对齐本地 index.html 全部 ?v。

与 reconcile_cache_busters.py 互补：
  - reconcile 取 git blobs(main 分支快照) 算 ?v；当本地 origin/main 缓存滞后于远端
    （cn git 墙导致 fetch 失败）时，它会按旧 blob 算旧 ?v，无法对齐 CDN。
  - 本工具直接下载 CDN 实际服务的内容算 sha（data 中性化 republish_time、v6 原始字节），
    保证 ?v == 浏览器真正拿到的文件 sha，彻底消除「main 缓存旧 + CDN 新」型失配。

用法：python scripts/fix_cachebusters_cdn.py
"""
import re
import hashlib
import pathlib
import os
import urllib.request

# ══════════════════════════════════════════════════════════════════════════════
# 🛑 2026-09-20 阿狸咪的工程师 · 停写护栏（?v 口径已于 2026-09-10 主人令废除）
# ══════════════════════════════════════════════════════════════════════════════
# 本脚本写出的 ?v 是「sha1 内容哈希」口径，已被废除
#   （原因：数据被回滚时哈希恰好等于旧版 ⇒ 浏览器永远吐旧数据，表现为「最终推荐回退到2天前」）。
# 现行权威口径 = **单调 unix 秒令牌**，唯一实现 = update_v8.py::_data_file_update_time()，
# 唯一正确调用方 = .github/workflows/v8_cache_buster_reconcile.yml
#   （每 15 分钟 + 每次 data push：git fetch+reset --hard origin/main → python update_v8.py --only-cache-busters）。
# ⇒ 本脚本已被取代。继续运行只会在 index.html 里写回废除口径，
#   并被 v8_build_deploy.yml 提交前核验判为「?v 出现非 unix 秒令牌(旧内容哈希口径回潮)」。
# 如需临时强制旧行为（**仅供取证，禁用于生产**）：设环境变量 V8_ALLOW_OBSOLETE_CB=1。
if os.environ.get("V8_ALLOW_OBSOLETE_CB") != "1":
    print("🛑 fix_cachebusters_cdn.py 已停用：?v 口径已于 2026-09-10 由内容哈希改为单调 unix 秒令牌")
    print("   正解：python update_v8.py --only-cache-busters")
    print("   （或交给 .github/workflows/v8_cache_buster_reconcile.yml 每 15 分钟自动对齐）")
    print("   强制旧行为（仅取证）：V8_ALLOW_OBSOLETE_CB=1")
    raise SystemExit(1)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ah-quant999.github.io/quant-scanner-v8"


def download(url):
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache", "User-Agent": "fix-cb"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def neut(b):
    b = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return re.sub(rb'"republish_time"\s*:\s*"[^"]*"', b'"republish_time":""', b)


def main():
    idxp = ROOT / "index.html"
    idx = idxp.read_text(encoding="utf-8")
    n = 0

    def repl(m):
        nonlocal n
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        try:
            data = download(f"{SITE}/{src}")
        except Exception:
            return m.group(0)
        calc = hashlib.sha1(neut(data)).hexdigest()[:10]
        n += 1
        return f"{q1}{src}?v={calc}{q2}"

    pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?v=[0-9a-fA-F]{1,40})?([\'"])')
    new = pat.sub(repl, idx)

    m6 = re.search(r'(v6_memo\.html)(\?v=[0-9a-fA-F]{1,40})?', new)
    if m6:
        v6 = download(f"{SITE}/v6_memo.html")
        calc = hashlib.sha1(v6).hexdigest()[:10]
        new = new[:m6.start()] + f"v6_memo.html?v={calc}" + new[m6.end():]

    if new != idx:
        idxp.write_text(new, encoding="utf-8")
        print(f"✅ 已按 CDN 真实内容对齐 {n} 处 data ?v + v6 ?v，写回 index.html")
    else:
        print(f"ℹ️ {n} 处 ?v 已全部与 CDN 一致，无需改动")


if __name__ == "__main__":
    main()
