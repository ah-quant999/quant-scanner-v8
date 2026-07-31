#!/usr/bin/env python3
# api_push_raw.py — 经 GitHub REST API 把 raw_data/ 推送到 main
# 绕过 git：本机(cn runner, NETWORK SERVICE)无法直连 github.com 的 git/HTTPS 协议，
# 但 api.github.com 可达。故用 Git Database API 以「单次 commit」方式提交 raw_data。
import os, sys, json, base64, hashlib, datetime
import urllib.request, urllib.error

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPO", "ah-quant999/quant-scanner-v8")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("❌ 缺少 GITHUB_TOKEN"); sys.exit(1)


def api(method, path, data=None):
    url = API + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}


def walk_raw():
    out = {}
    if not os.path.isdir("raw_data"):
        return out
    for root, _dirs, files in os.walk("raw_data"):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, ".").replace("\\", "/")
            with open(full, "rb") as fh:
                out[rel] = fh.read()
    return out


def main():
    files = walk_raw()
    if not files:
        print("ℹ️ raw_data 为空，跳过"); sys.exit(0)
    print(f"待推送文件: {len(files)} 个 -> {sorted(files)[:5]} ...")

    # 现有 main 树里的 raw_data 子树的 blob sha，用于变更检测
    ref = api("GET", f"/repos/{REPO}/git/refs/heads/main")
    if "__error__" in ref:
        print("❌ 获取 main ref 失败:", ref.get("__msg__")); sys.exit(1)
    base_sha = ref["object"]["sha"]
    cmt = api("GET", f"/repos/{REPO}/git/commits/{base_sha}")
    base_tree = cmt["tree"]["sha"]
    existing = {}
    tfull = api("GET", f"/repos/{REPO}/git/trees/{base_tree}?recursive=1")
    for e in tfull.get("tree", []):
        if e["path"].startswith("raw_data/") and e["type"] == "blob":
            existing[e["path"]] = e["sha"]

    # 上传 blobs（幂等：内容相同则 sha 相同）
    new_entries = {}
    for path, content in files.items():
        b = api("POST", f"/repos/{REPO}/git/blobs",
                {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if "__error__" in b:
            print("❌ 创建 blob 失败:", path, b.get("__msg__")); sys.exit(1)
        new_entries[path] = b["sha"]

    if existing == new_entries:
        print("ℹ️ raw_data 内容无变化，跳过提交"); sys.exit(0)

    tree_items = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                  for p, s in new_entries.items()]

    msg = "v8 cn fetch: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for attempt in range(1, 4):
        # 重新读取最新 main（与 build_deploy 并发安全）
        r2 = api("GET", f"/repos/{REPO}/git/refs/heads/main")
        base_sha2 = r2["object"]["sha"]
        cmt2 = api("GET", f"/repos/{REPO}/git/commits/{base_sha2}")
        base_tree2 = cmt2["tree"]["sha"]
        new_tree = api("POST", f"/repos/{REPO}/git/trees",
                       {"base_tree": base_tree2, "tree": tree_items})
        if "__error__" in new_tree:
            print("❌ 创建 tree 失败:", new_tree.get("__msg__")); sys.exit(1)
        commit = api("POST", f"/repos/{REPO}/git/commits",
                     {"message": msg, "tree": new_tree["sha"], "parents": [base_sha2]})
        if "__error__" in commit:
            print("❌ 创建 commit 失败:", commit.get("__msg__")); sys.exit(1)
        # force=True 但 parent 始终为最新 main，不会丢失他人提交
        upd = api("PATCH", f"/repos/{REPO}/git/refs/heads/main",
                  {"sha": commit["sha"], "force": True})
        if "__error__" in upd:
            print(f"⚠️ ref 更新冲突 ({upd.get('__error__')})，重试 ({attempt}/3)")
            continue
        print(f"✅ raw_data 已推送（第 {attempt} 次）commit {commit['sha'][:8]}")
        sys.exit(0)
    print("❌ 3 次重试后仍失败"); sys.exit(1)


if __name__ == "__main__":
    main()
