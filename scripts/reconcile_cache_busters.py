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


def neutral_sha_bytes(b: bytes) -> str:
    """内容哈希（中性化 republish_time 构建时间戳），与 update_v8._rewrite 完全一致。

    ★ 2026-08-16 修复：入参改为原始字节。此前 content_for 返回文本（read_text 在 Windows
    会把 CRLF 归一化为 LF），导致算出的 ?v 是「LF 版内容 sha」，而 Blobs API 实际推送的是
    磁盘原始字节（CRLF）→ 线上真实服务内容的 sha 与 index.html 的 ?v 永远不相等
    （正是 v6_memo 铁律最忌的缓存戳失配复发）。改为对原始字节求 sha，?v 即严格等于
    CDN 实际吐出的文件 sha。
    """
    neutral = re.sub(rb'"republish_time"\s*:\s*"[^"]*"', b'"republish_time":""', b)
    return hashlib.sha1(neutral).hexdigest()[:10]


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


def _api_bytes_blob(repo: str, path: str, token: str, tree: dict):
    """经 Git blobs API 取完整文件「原始字节」（不做 utf-8 解码，保证 sha1 字节级精确）。

    ⚠️ v6_memo.html 的 ?v 必须按原始字节算 sha1（与 guard_v6_memo.sha10_of 的
    open(path,'rb') 完全一致）。若改用 _api_text_blob（decode 带 replace）会破坏
    字节精度，导致 reconcile 与 guard 算出不同戳、互相来回改写，比不修更糟。
    """
    sha = tree.get(path)
    if not sha:
        return None
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_hdr(token)), timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        if isinstance(d, dict) and "content" in d:
            return base64.b64decode(d["content"])
    except Exception:
        return None
    return None


def reconcile_v6_memo(html: str, repo: str, token: str, tree: dict) -> str:
    """对齐「逻辑详解页 v6备忘录」iframe 的 ?v 戳（第二道保险）。

    ★ 2026-08-16 新增。根因：v6_memo.html 的缓存戳此前【无任何自愈网】——
      本函数之前的 data/*.js 正则 (data/[A-Z0-9_]+\\.js) 完全不匹配 v6_memo.html，
      而唯一会写该戳的 guard_v6_memo.py 在 build 里的修正会被紧随其后的
      `git reset --hard FETCH_HEAD` 擦掉，于是戳长期停在远端旧值，浏览器/CDN
      一直按旧 URL 吐早已作废的旧副本 → v6备忘录页面空白、反复"修不好"。
      build 侧已在 reset 之后重跑 guard 根治；此处作为独立 15 分钟自愈兜底。

    算法与 guard_v6_memo.sha10_of 严格一致：原始字节 sha1 前 10 位（不中性化）。
    """
    if "v6_memo.html" not in html:
        return html
    raw = None
    if not os.environ.get("RECONCILE_LOCAL") and token and repo:
        raw = _api_bytes_blob(repo, "v6_memo.html", token, tree)
    if raw is None:
        p = ROOT / "v6_memo.html"
        if p.exists():
            raw = p.read_bytes()
    # 缺失或明显被截断（<60KB，同 guard 的 MIN_BYTES 口径）时不动戳，交 guard 自愈
    if not raw or len(raw) < 60_000:
        print("⚠️ v6_memo.html 不可用/过短，跳过 v6 ?v 对齐（交 guard_v6_memo.py 自愈）")
        return html
    true_sha = hashlib.sha1(raw).hexdigest()[:10]
    new_html, n = re.subn(
        r'(src="v6_memo\.html)(?:\?v=[0-9a-fA-F]+)?(")',
        rf'\1?v={true_sha}\2', html)
    if n and new_html != html:
        print(f"🔄 v6备忘录 ?v 已对齐 → ?v={true_sha}")
    return new_html


def content_for(fname: str, data_dir: pathlib.Path, repo: str, token: str, tree: dict):
    """内容来源策略（★ 2026-08-16 起返回原始字节，确保 ?v == 线上真实内容 sha）：
    - RECONCILE_LOCAL=1（build 内部调用）：强制用本地磁盘文件。build 已 `git reset
      --hard FETCH_HEAD` + 本地重写产出「即将提交的内容」，本地即权威；若改用线上
      API 反而会拿到「尚未 push 的本轮新数据」之前的旧版本，导致 ?v 与本轮落库文件
      失配（CDN 吐旧副本）。本地磁盘即本轮真实产物，必须用本地。
    - 否则（独立 reconcile workflow）：CI 且 token 可用时优先线上真实版本
      （git blobs API 取完整内容，避开 checkout 陈旧 blob / Contents API >1MB 截断），
      回退本地磁盘。
    """
    if os.environ.get("RECONCILE_LOCAL"):
        p = data_dir / fname
        if p.exists():
            return p.read_bytes()
        return None
    if token and repo:
        b = _api_bytes_blob(repo, f"data/{fname}", token, tree)
        if b is not None:
            return b
    p = data_dir / fname
    if p.exists():
        return p.read_bytes()
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
        # 🔴 空文件(被并发重写瞬间清空/未就绪)不写空 ?v（sha1("")[:10]=da39a3ee5e），
        #   否则污染缓存戳、永不 bust。保留原 ?v 等文件就绪后下次构建再对齐。
        if not txt.strip():
            return m.group(0)
        return f"{q1}{src}?v={neutral_sha_bytes(txt)}{q2}"

    new_html = pat.sub(repl, html)
    # ★ 2026-08-16：v6备忘录 iframe 戳同样纳入自愈（此前无任何自愈网，详见 reconcile_v6_memo）
    new_html = reconcile_v6_memo(new_html, repo, token, tree)
    mode = "本地磁盘(RECONCILE_LOCAL)" if os.environ.get("RECONCILE_LOCAL") else "线上真实数据(git blobs API)"
    if new_html != html:
        idx.write_text(new_html, encoding="utf-8")
        print(f"✅ 部署前 ?v 已强对齐（基于{mode}）")
    else:
        print(f"ℹ️ 部署前 ?v 已一致，无需改动（{mode}）")


if __name__ == "__main__":
    main()
