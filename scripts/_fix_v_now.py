#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性：拉取线上 index.html，按线上真实 data 内容重算全部 ?v 并原子回推。
不依赖本地文件，避免 stale local 覆盖线上。冲突(409)自动重拉重算重试。
"""
import os, re, json, base64, hashlib, urllib.request, urllib.error, time

TOK = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"
API = "https://api.github.com/repos/" + REPO
H = {"Authorization": "Bearer " + TOK, "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "fix-v-now"}

def get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

def get_raw(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def neutral_sha(text):
    n = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
    return hashlib.sha1(n.encode("utf-8")).hexdigest()[:10]

def fetch_index():
    """返回 (content_str, sha)"""
    d = get(API + "/contents/index.html")
    return base64.b64decode(d["content"]).decode("utf-8", "replace"), d["sha"]

def fetch_tree():
    d = get(API + "/git/trees/main?recursive=1")
    return {e["path"]: e["sha"] for e in d.get("tree", []) if e["type"] == "blob"}

def blob_text(sha):
    d = get(API + "/git/blobs/" + sha)
    if d.get("encoding") == "base64":
        return base64.b64decode(d["content"]).decode("utf-8", "replace")
    return d.get("content", "")

def recompute(html, tree):
    pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')
    def repl(m):
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        fname = src.split("/")[-1]
        blob = tree.get("data/" + fname)
        if not blob:
            return m.group(0)
        txt = blob_text(blob)
        if not txt.strip():
            return m.group(0)
        return f"{q1}{src}?v={neutral_sha(txt)}{q2}"
    return pat.sub(repl, html)

def put_index(content, sha):
    body = {"message": "chore: 缓存戳实时对齐 ?v → 防覆盖 (手动 reconcile)",
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "sha": sha, "branch": "main"}
    req = urllib.request.Request(API + "/contents/index.html",
                                 data=json.dumps(body).encode(), headers=H, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8")), r.status
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "__msg__": e.read().decode("utf-8","replace")[:300]}, e.code

for attempt in range(4):
    html, sha = fetch_index()
    tree = fetch_tree()
    new = recompute(html, tree)
    if new == html:
        print(f"ℹ️ 第 {attempt+1} 次检测：?v 已一致，无需推送")
        break
    res, st = put_index(new, sha)
    if st in (200, 201):
        print(f"✅ 第 {attempt+1} 次：已对齐并推送 index.html ?v")
        break
    if isinstance(res, dict) and res.get("__error__") == 409:
        print(f"  ↻ 并发冲突，重拉重算重试 ({attempt+1}/4)")
        time.sleep(2)
        continue
    print(f"❌ 推送失败: {res}")
    break
else:
    print("❌ 多次冲突重试仍失败")
