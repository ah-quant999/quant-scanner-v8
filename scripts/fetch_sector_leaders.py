#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主升板块 · 龙头股抓取器（2026-09-17 主人令建；2026-09-18 主人令扩档 主升+启动）"""
import io
import json
import os
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC_RS = os.path.join(ROOT, "data", "SECTOR_RS.js")
OUT_RAW = os.path.join(ROOT, "raw_data", "sector_leaders.json")
OUT_JS = os.path.join(ROOT, "data", "SECTOR_LEADERS.js")

TOP_N = 5
PHASE_RULE_VER = 2
PHASES = ("主升", "启动")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
EM = "https://push2delay.eastmoney.com"


def log(msg):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def _get_json(url, timeout=20, retry=3):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            if i < retry - 1:
                time.sleep(1.2)
    raise last


def _read_window_js(path):
    if not os.path.exists(path):
        return None
    txt = io.open(path, encoding="utf-8", errors="ignore").read()
    i = txt.find("{")
    j = txt.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(txt[i:j + 1])
    except Exception:
        return None


def _phase_of(s):
    d5 = s.get("pct_5d") or 0
    d20 = s.get("pct_20d") or 0
    if d5 > 3 and d20 > 5:
        return "主升"
    if d5 > 1.5 and d20 > -8:
        return "启动"
    if d5 < -1.5:
        return "退潮"
    if d20 < -8:
        return "底部"
    return "震荡"


def fetch_em_boards():
    out = {}
    for pn in range(1, 9):
        url = ("%s/api/qt/clist/get?pn=%d&pz=100&po=1&np=1&fltt=2&invt=2"
               "&fid=f3&fs=m:90+t:2&fields=f12,f14,f3" % (EM, pn))
        d = _get_json(url)
        diff = ((d.get("data") or {}).get("diff")) or []
        if not diff:
            break
        for x in diff:
            nm, bk = x.get("f14"), x.get("f12")
            if nm and bk:
                out[nm] = bk
        total = (d.get("data") or {}).get("total") or 0
        if len(out) >= total:
            break
        time.sleep(0.25)
    return out


def fetch_cons(bk):
    url = ("%s/api/qt/clist/get?pn=1&pz=400&po=1&np=1&fltt=2&invt=2"
           "&fid=f3&fs=b:%s&fields=f12,f14,f2,f3,f62" % (EM, bk))
    d = _get_json(url)
    diff = ((d.get("data") or {}).get("diff")) or []
    rows = []
    for x in diff:
        code = x.get("f12")
        if not code:
            continue
        chg = x.get("f3")
        price = x.get("f2")
        if chg in (None, "-") or price in (None, "-", 0):
            continue
        try:
            chg = float(chg)
            price = float(price)
            mnet = float(x.get("f62")) if x.get("f62") not in (None, "-") else None
        except (TypeError, ValueError):
            continue
        rows.append({"code": code, "name": x.get("f14") or "",
                     "price": round(price, 2), "chg": round(chg, 2), "main_net": mnet})
    rows.sort(key=lambda r: r["chg"], reverse=True)
    return rows


def build():
    rs = _read_window_js(SRC_RS)
    if not rs or not rs.get("sectors"):
        log("no SECTOR_RS sectors")
        return None
    _dd = rs.get("data_date")
    src_date = str(_dd)[:10] if _dd else ""
    leaders_all = []
    for s in rs["sectors"]:
        nm = s.get("name")
        if not nm:
            continue
        ph = _phase_of(s)
        if ph not in PHASES:
            continue
        leaders_all.append({"name": nm, "phase": ph, "pct_5d": s.get("pct_5d"), "pct_20d": s.get("pct_20d")})
    _po = {"主升": 0, "启动": 1}
    leaders_all.sort(key=lambda x: (_po.get(x["phase"], 9), -(x.get("pct_5d") or 0)))
    log("phases: %s" % "、".join("%s(%s)" % (x["name"], x["phase"]) for x in leaders_all))
    sectors_out = []
    if leaders_all:
        boards = fetch_em_boards()
        for x in leaders_all:
            nm = x["name"]
            bk = boards.get(nm)
            if not bk:
                log("skip(no-same-name): %s" % nm)
                continue
            try:
                cons = fetch_cons(bk)
            except Exception as e:
                log("cons fail %s: %s" % (nm, str(e)[:60]))
                continue
            sectors_out.append({
                "name": nm, "bk": bk, "phase": x.get("phase", "主升"),
                "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                "cons_count": len(cons), "leaders": cons[:TOP_N],
            })
            time.sleep(0.3)
    payload = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": src_date, "rule_ver": PHASE_RULE_VER, "top_n": TOP_N,
        "source": "东方财富(push2delay) 板块成分股 + 同花顺 SECTOR_RS 板块周期",
        "phase": "主升+启动", "sector_count": len(sectors_out), "sectors": sectors_out,
        "note": "板块归属按同花顺行业分类；个股涨幅/价格为东方财富实时口径",
    }
    with open(OUT_RAW, "wb") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(OUT_JS, "wb") as f:
        f.write(b"window.SECTOR_LEADERS = " + body + b";\n")
    log("OK %d sectors (up=%d qidong=%d) js_bytes=%d" % (
        len(sectors_out),
        sum(1 for x in sectors_out if x.get("phase") == "主升"),
        sum(1 for x in sectors_out if x.get("phase") == "启动"), len(body)))
    return payload


if __name__ == "__main__":
    build()
