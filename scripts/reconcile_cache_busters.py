#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reconcile_cache_busters.py — 部署前 ?v 强对齐（防覆盖铁律根因修复）。

根因（2026-08-15 实测）：CI 的 actions/checkout 检出 main 时，data/*.js 中部分文件
偶发检出「旧 blob」（与 raw.githubusercontent / Contents API 实际服务的版本不一致）。
若按「检出文件」重算 ?v，会算到旧哈希、误判「已一致」→ 缓存戳长期失配、CDN 持续
吐旧副本（正是防覆盖铁律最忌的回归）。

修复：CI 环境（存在 GITHUB_TOKEN）下，直接用 GitHub 「Git Database API」拉取线上真实
服务版本的数据文件内容来算 ?v（与浏览器/CDN 实际拿到的完全一致），彻底摆脱 checkout
陈旧 blob / Contents API >1MB 截断 的影响：
  - 先取 main 的 git tree（path→blob sha 映射，缓存一次）；
  - 再经 /git/blobs/{sha} 取完整内容（该接口不对 >1MB 文件截断，Contents API 会截断）。
本地无 token 时回退磁盘文件（本地生成的数据即最新）。

所有 ?v 计算均与 update_v8._rewrite 完全一致：中性化 republish_time 后取 sha1 前 10 位。
"""
import re
import hashlib
import pathlib
import os
import base64
import json
import urllib.request

ROOT = pathlib.Path(".")


def neutral_sha(text: str) -> str:
    """内容哈希（中性化 republish_time 构建时间戳），与 update_v8._rewrite 完全一致。"""
    neutral = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
    return hashlib.sha1(neutral.encode("utf-8")).hexdigest()[:10]


def _hdr(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "reconcile",
    }


def _repo_tree(repo: str, token: str):
    """取 main 的 git tree（path→blob sha），缓存一次。失败返回空 dict。"""
    url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_hdr(token)), timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {e["path"]: e["sha"] for e in d.get("tree", []) if e["type"] == "blob"}
    except Exception:
        return {}


def _api_text_blob(repo: str, path: str, token: str, tree: dict):
    """经 Git blobs API 取完整文件内容（>1MB 不截断）。失败返回 None。"""
    sha = tree.get(path)
    if not sha:
        return None
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_hdr(token)), timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        if isinstance(d, dict) and "content" in d:
            return base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:
        return None
    return None


def content_for(fname: str, data_dir: pathlib.Path, repo: str, token: str, tree: dict):
    """优先线上真实版本（CI 且 token 可用，走 git blobs API 取完整内容），回退本地磁盘。"""
    if token and repo:
        t = _api_text_blob(repo, f"data/{fname}", token, tree)
        if t is not None:
            return t
    p = data_dir / fname
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def main():
    data_dir = ROOT / "data"
    idx = ROOT / "index.html"
    if not idx.exists():
        print("ℹ️ index.html 不存在，跳过 ?v 对齐")
        return

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"
    tree = _repo_tree(repo, token) if (token and repo) else {}

    html = idx.read_text(encoding="utf-8")
    # 全量匹配 index.html 中所有「带引号」的 data/X.js(?:\?v=...)? 出现
    # （script 标签 / fetch / BIG 数组均引号包裹），与 update_v8._rewrite 完全一致。
    pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')

    def repl(m):
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        fname = src.split("/")[-1]
        txt = content_for(fname, data_dir, repo, token, tree)
        if txt is None:
            return m.group(0)
        return f"{q1}{src}?v={neutral_sha(txt)}{q2}"

    new_html = pat.sub(repl, html)
    if new_html != html:
        idx.write_text(new_html, encoding="utf-8")
        print("✅ 部署前 ?v 已强对齐（基于线上真实数据，git blobs API）")
    else:
        print("ℹ️ 部署前 ?v 已一致，无需改动")


if __name__ == "__main__":
    main()
