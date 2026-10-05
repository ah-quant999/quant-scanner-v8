# 九宝量化 v8.0 — 🔮「未来预测」raw_data 依赖同步（cn runner 专用）
#
# 2026-10-05 阿狸咪的工程师 建。
# 为什么独立成文件（而非 workflow 内嵌 heredoc）：
#   PowerShell 的 @'...'@ here-string 终结符 '@ 必须位于行首，
#   缩进会被忽略导致整段被吞、Python 报 SyntaxError。独立 .py 调用最稳。
# 为什么走 Git Data API 而非 Contents API / git clone：
#   cn runner 上 git 协议访问 github.com 必被 Connection reset（见兄弟工作流注释），
#   且 Contents API + Invoke-WebRequest 在 cn 网络下 31 文件顺序拉会中途 EOF。
#   抄 v8_cn_fetch_cloud_selfhosted.yml 的 proven fetch_blob 模式：
#   /git/blobs/{sha} + raw media（载荷小防截断）+ 每次 sha 校验（静默截断永不被写入）+ tries=6 指数退避 + raw/b64 交替。
#
# gen_market_thermo.py 实测依赖（grep 得出）仅 5 个文件：
#   raw_data/sw_index_daily_cache/market_valuation_cache.csv
#   raw_data/sw_index_daily_cache/macro_margin.csv
#   raw_data/margin_data.json
#   raw_data/macro_data.json
#   raw_data/valuation_percentile.json

import os
import base64
import json
import hashlib
import urllib.request
import time

TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    raise SystemExit("缺少环境变量 GH_PAT")
REPO = "ah-quant999/quant-scanner-v8"
H = {
    "Authorization": "Bearer " + TOKEN,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def sha_of(data):
    h = hashlib.sha1()
    h.update(("blob %d\0" % len(data)).encode())
    h.update(data)
    return h.hexdigest()


def get_json(url, tries=6):
    last = None
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=H), timeout=120))
        except Exception as e:
            last = e
            print("  retry %d: %s" % (i + 1, e), flush=True)
            time.sleep(min(2 ** i, 20))
    raise SystemExit("API fetch failed: %s (%s)" % (url, last))


def fetch_blob(sha, tries=6):
    url = "https://api.github.com/repos/%s/git/blobs/%s" % (REPO, sha)
    raw_h = dict(H)
    raw_h["Accept"] = "application/vnd.github.raw"
    last = None
    for i in range(tries):
        mode = "raw" if i % 2 == 0 else "b64"
        try:
            hdr = raw_h if mode == "raw" else H
            resp = urllib.request.urlopen(
                urllib.request.Request(url, headers=hdr), timeout=180)
            body = resp.read()
            data = body if mode == "raw" else base64.b64decode(
                json.loads(body.decode())["content"])
            if sha_of(data) != sha:
                raise ValueError("sha mismatch (truncated?) got %d bytes" % len(data))
            return data
        except Exception as e:
            last = e
            print("  blob retry %d [%s]: %s" % (i + 1, mode, e), flush=True)
            time.sleep(min(2 ** i, 20))
    raise SystemExit("blob fetch failed: %s (%s)" % (sha, last))


def main():
    tip = get_json("https://api.github.com/repos/%s/git/ref/heads/main" % REPO)["object"]["sha"]
    top = get_json("https://api.github.com/repos/%s/git/trees/%s" % (REPO, tip))
    raw_sha = None
    for e in top["tree"]:
        if e["path"] == "raw_data":
            raw_sha = e["sha"]
            break
    if not raw_sha:
        raise SystemExit("远端无 raw_data")
    raw_tree = get_json("https://api.github.com/repos/%s/git/trees/%s" % (REPO, raw_sha))
    sw_entry = None
    for e in raw_tree["tree"]:
        if e["path"] == "sw_index_daily_cache":
            sw_entry = e
            break
    if not sw_entry:
        raise SystemExit("远端无 sw_index_daily_cache")
    sw_tree = get_json("https://api.github.com/repos/%s/git/trees/%s" % (REPO, sw_entry["sha"]))

    # path -> sha 查表（raw_data 顶层 + sw 子树）
    sha_of_path = {}
    for e in raw_tree["tree"]:
        sha_of_path["raw_data/" + e["path"]] = e["sha"]
    for e in sw_tree["tree"]:
        sha_of_path["raw_data/sw_index_daily_cache/" + e["path"]] = e["sha"]

    NEED = [
        "raw_data/sw_index_daily_cache/market_valuation_cache.csv",
        "raw_data/sw_index_daily_cache/macro_margin.csv",
        "raw_data/margin_data.json",
        "raw_data/macro_data.json",
        "raw_data/valuation_percentile.json",
    ]
    for rel in NEED:
        if rel not in sha_of_path:
            raise SystemExit("远端缺依赖文件: %s" % rel)
        os.makedirs(os.path.dirname(rel), exist_ok=True)
        data = fetch_blob(sha_of_path[rel])
        with open(rel, "wb") as f:
            f.write(data)
        print("synced %s (%d bytes, sha ok)" % (rel, len(data)))
    print("raw_data 同步完成（5 文件，全部 sha 校验通过）")


if __name__ == "__main__":
    main()
