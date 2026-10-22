#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立、无副作用地核验线上 index.html 的全部 ?v 是否与真实 data 内容一致。
使用 Git blobs API（无 >1MB 截断），对线上站做最终一致性体检。
"""
import os, re, sys, json, hashlib, base64, urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"

def api_get(url, raw=False):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "verify-coherence",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        if raw:
            return r.read()
        return json.loads(r.read().decode("utf-8"))

def neutral_sha(text):
    neutral = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
    return hashlib.sha1(neutral.encode("utf-8")).hexdigest()[:10]

def repo_tree():
    t = api_get(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1")
    return {i["path"]: i["sha"] for i in t.get("tree", []) if i["type"] == "blob"}

def blob_text(sha):
    b = api_get(f"https://api.github.com/repos/{REPO}/git/blobs/{sha}")
    enc = b.get("encoding", "base64")
    data = b.get("content", "")
    if enc == "base64":
        return base64.b64decode(data).decode("utf-8", "replace")
    return data

print("== 拉取线上 index.html ==")
idx = api_get(f"https://api.github.com/repos/{REPO}/contents/index.html")
idx_sha = idx["sha"]
idx_text = base64.b64decode(idx["content"]).decode("utf-8", "replace")
print(f"index.html blob sha={idx_sha[:10]}  长度={len(idx_text)}")

print("== 构建线上 git tree ==")
tree = repo_tree()
print(f"tree 文件数={len(tree)}")

pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?v=([0-9a-fA-F]{1,40}))?([\'"])')
refs = {}
for m in pat.finditer(idx_text):
    url = m.group(2)
    v = m.group(3)
    refs.setdefault(url, set()).add(v)

print(f"== 发现 ?v 引用 {sum(len(v) for v in refs.values())} 条，去重文件 {len(refs)} 个 ==\n")

mismatch = 0
checked = 0
for fname in sorted(refs):
    path = f"data/{fname}" if not fname.startswith("data/") else fname
    blob = tree.get(path)
    if not blob:
        print(f"[缺失] {fname}: 线上 tree 无此文件")
        mismatch += 1
        continue
    try:
        txt = blob_text(blob)
    except Exception as e:
        print(f"[读取失败] {fname}: {e}")
        mismatch += 1
        continue
    calc = neutral_sha(txt)
    seen = refs[fname]
    # 一个文件可能有多处引用（同值应一致）
    uniq = sorted(x for x in seen if x)
    ok = all(x == calc for x in uniq)
    checked += 1
    if not ok:
        mismatch += 1
        print(f"[失配] {fname}: 计算={calc}  线上?v={'/'.join(uniq) or '无'}")
    else:
        print(f"[OK]   {fname}: v={calc}")

print(f"\n== 核验完成: 检查 {checked} 个文件 | 失配 {mismatch} ==")
print("FINAL:" , "PASS ✅" if mismatch == 0 else "FAIL ❌")
sys.exit(0 if mismatch == 0 else 1)
