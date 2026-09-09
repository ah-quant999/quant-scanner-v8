#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""maharo API 探测：抓取 data.maharo.cn 的真实 API 结构，并把结果直接
通过 GitHub Contents API 写回仓库（绕开 git push，避免浅克隆 refspec 问题）。
本脚本在云端 runner（境外 IP，可解析 data.maharo.cn）运行。
"""
import os
import re
import json
import base64
import urllib.request
import urllib.error

BASE = "https://data.maharo.cn"
COOKIE = os.environ.get("MAHORO_COOKIE", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "ah-quant999/quant-scanner-v8")
RESULT_PATH = "maharo_probe_result.txt"


def fetch(url, headers=None, timeout=25):
    h = {"User-Agent": "Mozilla/5.0 (compatible; quant-scanner-probe/1.0)"}
    if COOKIE:
        h["Cookie"] = COOKIE
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace"), e.code
    except Exception as e:  # noqa
        return "ERR: %s" % e, 0


def github_put(path, content_text, token):
    """通过 Contents API 写/更新仓库内文件。返回 (ok, msg)。"""
    api = "https://api.github.com/repos/%s/contents/%s" % (REPO, path)
    auth = {"Authorization": "Bearer %s" % token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json"}
    # 取既有 sha（更新需要）
    sha = None
    try:
        req = urllib.request.Request(api, headers={k: auth[k] for k in ("Authorization", "Accept")})
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        sha = None
    payload = {
        "message": "maharo probe result",
        "content": base64.b64encode(content_text.encode("utf-8")).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(payload).encode("utf-8"),
                                 headers=auth, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, "HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        return False, "HTTP %d %s" % (e.code, e.read().decode("utf-8", "replace")[:300])


def main():
    L = []
    L.append("MAHARO API PROBE @ %s" % os.environ.get("GITHUB_SHA", "local"))
    L.append("COOKIE set: %s" % ("YES" if COOKIE else "NO"))
    L.append("")

    # 1) 首页，抽取 /api/ 链接
    html, st = fetch(BASE + "/")
    L.append("== HOME status=%s len=%d" % (st, len(html)))
    api_links = sorted(set(re.findall(r"/api/[A-Za-z0-9_\-/?&=.]+", html)))
    L.append("API links in homepage: " + (", ".join(api_links) if api_links else "(none found)"))

    # 2) 已知 signals 端点
    sig, sst = fetch(BASE + "/api/signals?limit=2")
    L.append("== /api/signals status=%s len=%d" % (sst, len(sig)))
    L.append(sig[:1200])
    L.append("")

    # 3) 候选端点（重点：专家档案 / 估值分位 / 研究聚合）
    cands = [
        "/api/experts", "/api/expert", "/api/expert/profile",
        "/api/valuation", "/api/valuation-percentile", "/api/valuation_percentile",
        "/api/indicators", "/api/research", "/api/sources", "/api/source",
        "/api/profile", "/api/aggregate", "/api/signal/aggregate",
        "/api/docs", "/api/user", "/api/insights", "/api/macro",
        "/api/strategy", "/api/views", "/api/consensus", "/api/group",
    ]
    for c in cands:
        body, cs = fetch(BASE + c)
        snippet = re.sub(r"\s+", " ", body)[:400]
        L.append("== %s status=%s len=%d :: %s" % (c, cs, len(body), snippet))

    result = "\n".join(L)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        f.write(result)

    print("PROBE DONE, total bytes=%d" % len(result))

    if GH_TOKEN:
        ok, msg = github_put(RESULT_PATH, result, GH_TOKEN)
        print("PUSH result: ok=%s %s" % (ok, msg))
    else:
        print("PUSH skipped: no GITHUB_TOKEN")


if __name__ == "__main__":
    main()
