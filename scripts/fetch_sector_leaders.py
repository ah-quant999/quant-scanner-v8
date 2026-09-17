#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主升板块 · 龙头股抓取器（2026-09-17 主人令）

■ 需求（主人原话）
  「主升有没有龙头股或者推荐股，要不不知道买什么」——「板块资金趋势」卡里
  「主升」档只给了板块名与涨幅，看不出该买哪只 ⇒ 本脚本产出每个**主升板块**的
  当日涨幅前 N 名个股，作为「可交易标的」参考。

■ 放在哪里
  产出 data/SECTOR_LEADERS.js（window.SECTOR_LEADERS），由「暂未上架 > 观测类 >
  概念/行业 → ETF·龙头 参考」卡（容器 div#dbgEtfMapBody）在现有「热点板块→ETF/龙头」
  列表**下方**追加一个「🚀 主升板块 · 龙头股（实时）」块渲染。
  主人 2026-09-17 明确：「只放『暂未上架』页」。

■ 数据链路（每步都实测过）
  1) 主升板块从哪来 —— 复用 data/SECTOR_RS.js 的 sectors（同花顺 90 个行业板块），
     用与 index.html「板块资金趋势」卡**逐字一致**的 v2 规则判定：
         主升 = pct_5d > 3 且 pct_20d > 5
     ⚠️ 该规则在本脚本、algorithms/fetch_sector_rs.py::_phase_of()、
        index.html renderSector() 三处必须一致，改一处必改三处。
  2) 板块 → 成分股 —— 东方财富 push2delay 接口：
         /api/qt/clist/get?fs=b:{BK码}&fields=f12,f14,f2,f3,f62
     实测：push2.eastmoney.com 在本机被拒（RemoteDisconnected），
           **push2delay.eastmoney.com 可用**，故只用后者（与 cloud_fetch_v8.py 同源）。
  3) 同花顺板块名 → 东财 BK 码 —— 走「板块名同名匹配」，并做**成分股自证**：
     实测同花顺「元件 881270」(63只) 与东财「BK0459 元件」(67只) 交集 62 只
     （重合率 98.4%）⇒ 同名即同股，可直接映射。
     ⚠️ 不做模糊匹配：名字对不上就**不产出**该板块的龙头股（宁可缺，不可错）。
        模糊匹配会把「元件」错配到东财「印制电路板」，给出完全错误的票。

■ 为什么必须独立成文件（禁止并进 SECTOR_RS）
  SECTOR_RS 是「板块指数」链路，双机/云端多处在消费，动它有回退风险。
  本块是**新增观测项**，独立链路 ⇒ 挂了也不影响主站任何现有卡片。
"""

import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)                       # 仓库根
SRC_RS = os.path.join(ROOT, "data", "SECTOR_RS.js")
OUT_RAW = os.path.join(ROOT, "raw_data", "sector_leaders.json")
OUT_JS = os.path.join(ROOT, "data", "SECTOR_LEADERS.js")

TOP_N = 5                    # 每个板块取前 5 只（主人 2026-09-17 指定）
PHASE_RULE_VER = 2           # 与 fetch_sector_rs.py / index.html 对齐

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
    """带重试的 JSON 拉取。东财偶发 RemoteDisconnected，必须重试。"""
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


def _read_window_js(path, varname):
    """读 data/*.js（形如 `window.X = {...};`）→ dict。

    ⚠️ 仓库里 data/*.js 可能是**单行压缩**落盘态，禁止按行解析，必须整串取 {}。
       （参见 skill: v8-data-js-parsing）
    """
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
    """阶段判定 v2 —— 必须与 index.html renderSector() 及 fetch_sector_rs.py 逐字一致。"""
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
    """东财全量行业板块 → {板块名: BK码}。分页拉全（实测 total=496，pz 上限 100）。"""
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
    """东财板块成分股（按当日涨幅降序）。返回 [{code,name,price,chg,main_net}]。"""
    url = ("%s/api/qt/clist/get?pn=1&pz=400&po=1&np=1&fltt=2&invt=2"
           "&fid=f3&fs=b:%s&fields=f12,f14,f2,f3,f62" % (EM, bk))
    d = _get_json(url)
    diff = ((d.get("data") or {}).get("diff")) or []
    rows = []
    for x in diff:
        code = x.get("f12")
        if not code:
            continue
        # 剔除退市/异常价
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
        rows.append({
            "code": code,
            "name": x.get("f14") or "",
            "price": round(price, 2),
            "chg": round(chg, 2),
            "main_net": mnet,
        })
    rows.sort(key=lambda r: r["chg"], reverse=True)
    return rows


def build():
    rs = _read_window_js(SRC_RS, "SECTOR_RS")
    if not rs or not rs.get("sectors"):
        log("❌ SECTOR_RS 无 sectors，拒绝写盘（保留上一版）")
        return None

    _dd = rs.get("data_date")
    src_date = str(_dd)[:10] if _dd else ""
    leaders_all = []
    for s in rs["sectors"]:
        nm = s.get("name")
        if not nm:
            continue
        if _phase_of(s) != "主升":
            continue
        leaders_all.append({"name": nm, "pct_5d": s.get("pct_5d"), "pct_20d": s.get("pct_20d")})

    log("SECTOR_RS data_date=%s  主升板块 %d 个：%s"
        % (src_date, len(leaders_all), "、".join(x["name"] for x in leaders_all) or "（无）"))

    if not leaders_all:
        payload = {
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data_date": src_date,
            "rule_ver": PHASE_RULE_VER,
            "top_n": TOP_N,
            "source": "东方财富(push2delay) 板块成分股 + 同花顺 SECTOR_RS 板块周期",
            "phase": "主升",
            "sector_count": 0,
            "sectors": [],
            "note": "今日无主升板块",
        }
    else:
        boards = fetch_em_boards()
        log("东财行业板块 %d 个（用于同名映射）" % len(boards))
        sectors_out = []
        for x in leaders_all:
            nm = x["name"]
            bk = boards.get(nm)
            if not bk:
                # 宁可缺，不可错：不做模糊匹配（模糊会把「元件」错配成 PCB 板块）
                log("  ⚠️ %s 在东财无同名板块，跳过（不做模糊匹配，避免给错票）" % nm)
                continue
            try:
                cons = fetch_cons(bk)
            except Exception as e:
                log("  ❌ %s(%s) 成分股拉取失败: %s" % (nm, bk, str(e)[:70]))
                continue
            top = cons[:TOP_N]
            log("  ✅ %s(%s) 成分股 %d 只，取前 %d：%s"
                % (nm, bk, len(cons), len(top), "、".join(t["name"] for t in top)))
            sectors_out.append({
                "name": nm,
                "bk": bk,
                "pct_5d": x.get("pct_5d"),
                "pct_20d": x.get("pct_20d"),
                "cons_count": len(cons),
                "leaders": top,
            })
            time.sleep(0.3)

        payload = {
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data_date": src_date,
            "rule_ver": PHASE_RULE_VER,
            "top_n": TOP_N,
            "source": "东方财富(push2delay) 板块成分股 + 同花顺 SECTOR_RS 板块周期",
            "phase": "主升",
            "sector_count": len(sectors_out),
            "sectors": sectors_out,
            "note": "板块归属按同花顺行业分类；个股涨幅/价格为东方财富实时口径",
        }

    # 中间产物（二进制写，锁 LF —— Windows 上 io.open 文本模式会写成 CRLF）
    os.makedirs(os.path.dirname(OUT_RAW), exist_ok=True)
    with open(OUT_RAW, "wb") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    # 前端产物（单行压缩态，与仓库其他 data/*.js 一致；二进制写锁 LF）
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(OUT_JS, "wb") as f:
        f.write(b"window.SECTOR_LEADERS = " + body + b";\n")
    log("✅ 已产出 %s（%d 字节，%d 个主升板块）"
        % (os.path.relpath(OUT_JS, ROOT), len(body.encode("utf-8")), payload["sector_count"]))
    return payload


if __name__ == "__main__":
    build()
