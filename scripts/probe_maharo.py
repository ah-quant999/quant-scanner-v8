#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针：用 MAHORO_COOKIE 从云端抓取 data.maharo.cn 的 API 结构，落 maharo_probe_result.txt。
仅用于探查新功能端点，非生产代码，用完即删。"""
import urllib.request, os, re, sys

BASE = "https://data.maharo.cn"
CK = os.environ.get("MAHORO_COOKIE", "").strip()

def get(path, cookie=""):
    url = BASE + path
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"})
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.read().decode("utf-8", "replace"), r.headers.get("content-type", "")
    except Exception as e:
        return "ERR: %s" % e, "text/plain"

out = []
html, ct = get("/")
apis = sorted(set(re.findall(r'(/api/[A-Za-z0-9_./-]+)', html)))
out.append("=== 首页 /api/ 链接 (ct=%s) ===" % ct)
out.append("\n".join(apis) or "(无)")

sig, ct2 = get("/api/signals?limit=2", CK)
out.append("\n=== /api/signals (ct=%s) ===" % ct2)
out.append((sig[:2000] if not sig.startswith("ERR") else sig))

cands = ["/api/experts", "/api/valuation", "/api/research", "/api/sources",
         "/api/profile", "/api/aggregate", "/api/docs", "/api/user",
         "/api/signal/aggregate", "/api/insights", "/api/macro"]
for c in cands:
    r, _ = get(c, CK)
    out.append("\n=== %s ===" % c)
    out.append((r[:1500] if not r.startswith("ERR") else r))

result = "\n".join(out)
open("maharo_probe_result.txt", "w", encoding="utf-8").write(result)
print("PROBE DONE, total bytes=", len(result))
