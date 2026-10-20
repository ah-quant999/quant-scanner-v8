# -*- coding: utf-8 -*-
"""us_hk_map_need_push.py — 判断隔夜美股映射两件产物是否需要推送。

存在理由（与 dajijin_need_push.py 同取舍）：
    v8_build_deploy 的 push.paths 含 `data/**` ⇒ 每推一次 data 文件都会触发
    **全量重建 + 部署**（~8min + Actions 配额）。若内容未变仍照推，就是白烧一次。
    故推送前先比对线上 blob 内容与本地内容，两件都相同即跳过。

比对对象（raw+data 两件同查，防跨层时间戳不一致被 v8_verify_layer_parity 判红）：
    raw_data/us_hk_map.json   ← cloud_fetch_v8.py --only US_HK_MAP 产出
    data/US_HK_MAP.js         ← update_v8.py --category premarket 重建

输出（供 workflow 用正则匹配，不依赖退出码）：
    NEED_PUSH=1  —— 任一文件不同 / 线上不存在 / 比对失败（保守：宁可多推一次）
    NEED_PUSH=0  —— 两件均逐字节相同（或本地缺失）

用法: python scripts/us_hk_map_need_push.py
环境: GH_PAT（GitHub token，contents:read 即可）
"""
import base64
import json
import os
import sys
import urllib.request

REPO = "ah-quant999/quant-scanner-v8"
TARGETS = ["raw_data/us_hk_map.json", "data/US_HK_MAP.js"]


def _remote(local_path, target, token):
    """返回 (same, detail)；比对失败/无 token 时保守 same=False。"""
    local = open(local_path, "rb").read()
    url = "https://api.github.com/repos/%s/contents/%s?ref=main" % (REPO, target)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "User-Agent": "v8-us-hk-map-fetcher",
        "Accept": "application/vnd.github+json",
    })
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    cur = json.loads(raw)
    remote = base64.b64decode((cur.get("content") or "").replace("\n", "").replace("\r", ""))
    same = (remote == local)
    print("%s local=%d bytes remote=%d bytes same=%s" % (target, len(local), len(remote), same))
    return same


def main() -> int:
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("[warn] 无 GH_PAT ⇒ 保守判定为需要推送")
        print("NEED_PUSH=1")
        return 0
    need = 0
    for target in TARGETS:
        if not os.path.exists(target):
            print("[warn] 本地文件不存在：%s ⇒ 无需推送该件" % target)
            continue
        try:
            if not _remote(target, target, token):
                need = 1
        except Exception as e:  # noqa: BLE001
            print("[warn] 线上比对失败(%s: %s) ⇒ 保守判定为需要推送" % (type(e).__name__, str(e)[:80]))
            need = 1
    print("NEED_PUSH=%d" % need)
    return 0


if __name__ == "__main__":
    sys.exit(main())
