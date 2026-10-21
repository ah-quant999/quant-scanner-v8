# -*- coding: utf-8 -*-
"""card_need_push.py — 判断指定 data/*.js 是否需要推送（新卡日更链通用内容比对）。

存在理由（每张日更卡都必需的取舍）：
    v8_build_deploy 的 push.paths 含 `data/**` ⇒ 每推一次 data 文件都会触发
    **全量重建 + 部署**（~8min + Actions 配额）。若内容与线上逐字节相同仍照推，
    就是白烧一次 build（且刷一次无意义的 ?v）。故推送前先比对线上 blob 与本地
    内容，相同即 SKIP。
    与生成器内的「同源去重」互补：去重管「上游没新数据不生成」，本脚本管
    「生成了但内容没变不推」双保险。

输出（供 workflow 用正则匹配，不依赖退出码）：
    NEED_PUSH=1  —— 内容不同 / 线上不存在 / 比对失败（保守：宁可多推一次）
    NEED_PUSH=0  —— 内容逐字节相同 / 本地文件不存在

用法: python scripts/card_need_push.py <仓库内相对路径>
环境: GH_PAT 或 GITHUB_TOKEN（contents:read 即可）
"""
import base64
import json
import os
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"


def main() -> int:
    if len(sys.argv) < 2:
        print("[warn] 用法: python scripts/card_need_push.py <相对路径>")
        print("NEED_PUSH=0")
        return 0
    target = sys.argv[1].replace("\\", "/")
    if not os.path.exists(target):
        print("[warn] 本地文件不存在：%s ⇒ 无需推送" % target)
        print("NEED_PUSH=0")
        return 0

    local = open(target, "rb").read()
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("[warn] 无 GH_PAT ⇒ 保守判定为需要推送")
        print("NEED_PUSH=1")
        return 0

    from urllib.parse import quote
    quoted = "/".join(quote(seg, safe="") for seg in target.split("/"))
    url = "https://api.github.com/repos/%s/contents/%s?ref=main" % (REPO, quoted)
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "v8-card-need-push",
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
    print("target=%s local=%d bytes  remote=%d bytes  same=%s" % (target, len(local), len(remote), same))
    print("NEED_PUSH=%d" % (0 if same else 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
