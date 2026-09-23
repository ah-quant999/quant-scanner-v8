# -*- coding: utf-8 -*-
"""dajijin_need_push.py — 判断 data/DAJIJIN_REDUCTION.js 是否需要推送。

存在理由（本链必需的取舍）：
    v8_build_deploy 的 push.paths 含 `data/**` ⇒ 每推一次 data 文件都会触发
    **全量重建 + 部署**（~8min + Actions 配额）。若当日无新公告仍照推，
    就是每天白烧一次 build。故推送前先比对线上 blob 内容与本地内容，相同即跳过。

输出（供 workflow 用正则匹配，不依赖退出码）：
    NEED_PUSH=1  —— 内容不同 / 线上不存在 / 比对失败（保守：宁可多推一次）
    NEED_PUSH=0  —— 内容逐字节相同

用法: python scripts/dajijin_need_push.py [本地路径]
环境: GH_PAT（GitHub token，contents:read 即可）
"""
import base64
import json
import os
import sys
import urllib.request

REPO = "ah-quant999/quant-scanner-v8"
TARGET = "data/DAJIJIN_REDUCTION.js"


def main() -> int:
    local_path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    if not os.path.exists(local_path):
        print("[warn] 本地文件不存在：%s ⇒ 无需推送" % local_path)
        print("NEED_PUSH=0")
        return 0

    local = open(local_path, "rb").read()
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("[warn] 无 GH_PAT ⇒ 保守判定为需要推送")
        print("NEED_PUSH=1")
        return 0

    url = "https://api.github.com/repos/%s/contents/%s?ref=main" % (REPO, TARGET)
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "v8-dajijin-fetcher",
            "Accept": "application/vnd.github+json",
        })
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        cur = json.loads(raw)
        remote = base64.b64decode((cur.get("content") or "").replace("\n", "").replace("\r", ""))
    except Exception as e:  # noqa: BLE001
        print("[warn] 线上比对失败(%s: %s) ⇒ 保守判定为需要推送" % (type(e).__name__, str(e)[:80]))
        print("NEED_PUSH=1")
        return 0

    same = (remote == local)
    print("local=%d bytes  remote=%d bytes  same=%s" % (len(local), len(remote), same))
    print("NEED_PUSH=%d" % (0 if same else 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
