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
    # 🔴 2026-08-15 根因修复（与 update_v8._rewrite 保持完全一致）：
    # 原正则只匹配 `<script src="data/X.js..."></script>` 整段，漏掉 A2 懒加载
    # `var BIG=[{...,url:'data/X.js?v=...'}]` 与 `fetch('data/X.js?v=...')` 里的字符串
    # 引用 → 这些 ?v 永远不重算，CDN 长期吐旧副本。改为全量匹配所有带引号的
    # data/X.js(?:\?v=...)? 出现（script 标签 / fetch / BIG 数组均引号包裹）。
    pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')

    def repl(m):
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        f = data_dir / src.split("/")[-1]
        if not f.exists():
            return m.group(0)
        ts = neutral_sha(f.read_text(encoding="utf-8"))
        return f"{q1}{src}?v={ts}{q2}"

    new_html = pat.sub(repl, html)
    if new_html != html:
        idx.write_text(new_html, encoding="utf-8")
        print("✅ 部署前 ?v 已强对齐")
    else:
        print("ℹ️ 部署前 ?v 已一致，无需改动")


if __name__ == "__main__":
    main()
