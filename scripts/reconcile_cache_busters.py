#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reconcile_cache_busters.py — 部署前 ?v 强对齐（防覆盖铁律根因修复）。

在 v8_build_deploy.yml 的部署步骤里、git add 之前运行：用「当前磁盘上
data/*.js 的真实内容」重算 index.html 每个 data/*.js 引用的 ?v（内容 sha1[:10]，
中性化 republish_time 构建时间戳），使本次提交 index.html 与即将 git add 的
data 文件严格一致，彻底杜绝 build 内 _rewrite 与最终落库文件因重生/reset 竞态
导致的缓存戳失配（CDN 吐旧副本）。

与 update_v8.py 的 _data_file_update_time 中性化逻辑保持一致。
"""
import re
import hashlib
import pathlib

ROOT = pathlib.Path(".")


def neutral_sha(text: str) -> str:
    """内容哈希（中性化 republish_time 构建时间戳），与 update_v8.py 一致。"""
    neutral = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
    return hashlib.sha1(neutral.encode("utf-8")).hexdigest()[:10]


def main():
    data_dir = ROOT / "data"
    idx = ROOT / "index.html"
    if not idx.exists():
        print("ℹ️ index.html 不存在，跳过 ?v 对齐")
        return

    html = idx.read_text(encoding="utf-8")
    pat = re.compile(r'(<script src=")(data/[A-Z0-9_]+\.js)(?:\?[^"]*)?("[^>]*></script>)')

    def repl(m):
        pre, src, suf = m.group(1), m.group(2), m.group(3)
        f = data_dir / src.split("/")[-1]
        if not f.exists():
            return m.group(0)
        ts = neutral_sha(f.read_text(encoding="utf-8"))
        return f"{pre}{src}?v={ts}{suf}"

    new_html = pat.sub(repl, html)
    if new_html != html:
        idx.write_text(new_html, encoding="utf-8")
        print("✅ 部署前 ?v 已强对齐")
    else:
        print("ℹ️ 部署前 ?v 已一致，无需改动")


if __name__ == "__main__":
    main()
