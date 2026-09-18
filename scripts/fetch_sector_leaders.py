#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主升/启动板块 · 龙头股抓取器（2026-09-17 主人令建；2026-09-18 主人令扩档 主升+启动；
2026-09-18 晚 阿狸咪的工程师 二修）：
  修①（系统性丢板块，实锤复现：skip(no-same-name) 电子化学品/其他电子）
     同花顺行业名 vs 东财板块名精确匹配必丢 —— 东财这两个板块叫「电子化学品Ⅱ/Ⅲ」「其他电子Ⅱ/Ⅲ」。
     改为：精确匹配 → 失败则去 Ⅰ/Ⅱ/Ⅲ 级后缀归一匹配；同级碰撞时优先 Ⅱ 级（行业标准中层层级）。
  修②（瞬时丢板块无痕）：个股行情抓取失败（东财反爬/限流）时旧版 continue 静默丢弃整板块，
     ⇒ 前端「启动 · N 个板块」与「板块资金趋势」卡口径对不上且无任何提示。
     改为：双轮重试（3 重试/轮 × 2 轮，轮间 2.5s）；仍失败则保留板块（leaders=[] + leaders_error=1），
     前端按「抓取失败待补抓」明示，阶段判定口径不受影响。
  修③：汇总日志输出 主升(x/y) 启动(z/w)（x=有龙头 y=应输出），一眼可审。"""
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
LEVEL_SUFFIX = ("Ⅲ", "Ⅱ", "Ⅰ")   # 东财板块级后缀（同花顺名不带）

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


def _norm(nm):
    for suf in LEVEL_SUFFIX:
        if nm.endswith(suf):
            return nm[:-1]
    return nm


def fetch_em_boards():
    """返回 (精确名映射, 归一名映射)。归一碰撞时优先 Ⅱ 级，其次先到先得。"""
    exact, norm = {}, {}
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
                exact[nm] = bk
                k = _norm(nm)
                if k not in norm or nm.endswith("Ⅱ"):
                    norm[k] = bk
        total = (d.get("data") or {}).get("total") or 0
        if len(exact) >= total:
            break
        time.sleep(0.25)
    return exact, norm


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


def fetch_cons_safe(bk):
    """双轮重试：每轮内部 _get_json 已带 3 重试；轮间 2.5s 缓冲防东财限流。"""
    last = None
    for rnd in range(2):
        try:
            return fetch_cons(bk)
        except Exception as e:
            last = e
            if rnd == 0:
                time.sleep(2.5)
    raise last


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
    n_fail = 0
    if leaders_all:
        boards_exact, boards_norm = fetch_em_boards()
        log("em boards: exact=%d norm=%d" % (len(boards_exact), len(boards_norm)))
        for x in leaders_all:
            nm = x["name"]
            bk = boards_exact.get(nm) or boards_norm.get(_norm(nm))
            if not bk:
                log("skip(no-match-even-norm): %s（同花顺名在东财无对应板块，需人工别名表）" % nm)
                continue
            try:
                cons = fetch_cons_safe(bk)
            except Exception as e:
                n_fail += 1
                log("cons fail2 %s(%s): %s —— 保留板块，个股留空待下轮补抓" % (nm, bk, str(e)[:60]))
                sectors_out.append({
                    "name": nm, "bk": bk, "phase": x.get("phase", "主升"),
                    "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                    "cons_count": 0, "leaders": [], "leaders_error": 1,
                })
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
        "note": "板块归属按同花顺行业分类；个股涨幅/价格为东方财富实时口径；leaders_error=1 表示个股行情本轮抓取失败待补抓",
    }
    with open(OUT_RAW, "wb") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(OUT_JS, "wb") as f:
        f.write(b"window.SECTOR_LEADERS = " + body + b";\n")
    _cnt = {}
    for x in sectors_out:
        p = x.get("phase", "主升")
        _cnt.setdefault(p, [0, 0])
        _cnt[p][0] += 1 if x.get("leaders") else 0
        _cnt[p][1] += 1
    log("OK %s js_bytes=%d leaders_fail=%d" % (
        " ".join("%s(%d/%d)" % (p, v[0], v[1]) for p, v in sorted(_cnt.items(), key=lambda kv: _po.get(kv[0], 9))),
        len(body), n_fail))
    return payload


if __name__ == "__main__":
    build()
