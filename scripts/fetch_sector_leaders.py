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

# 🛡 2026-09-30 小九（主人令「暂未上架这卡这里为什么没有？一劳永逸修复」）：
#   东财 push2 对云端 runner 全 host RemoteDisconnected（run#36691760288 实测，
#   algo_run_report fail=2 记账在案）⇒ 本脚本 09-29 19:28 后断供 2 天 ⇒
#   「主升/启动·龙头股」卡今日 2 个启动板块（小金属/风电设备）龙头股位全空。
#   修法 = 三层兜底（只加降级路径，不动任何取数口径）：
#     ① 板块名→BK 映射缓存  raw_data/em_boards_cache.json  （成功轮全量回写，随 git 跨 run/跨日累积）
#     ② 板块成员名单缓存    raw_data/em_members_cache.json  （fetch_cons 成功轮回写）
#     ③ 行情腾讯兜底        qt.gtimg.cn 批量报价（fetch_us_hk_map 同源，云端已验证可达）
#   ⇒ 东财全断日：板块清单走缓存、行情走腾讯；缓存也缺时板块结构仍照写照推（明示
#     no_match/leaders_error），dict **每日刷新绝不中断**，不再整脚本崩退出 1。
CACHE_BOARDS = os.path.join(ROOT, "raw_data", "em_boards_cache.json")
CACHE_MEMBERS = os.path.join(ROOT, "raw_data", "em_members_cache.json")

# 本轮板块名→BK 映射的来源审计（live=东财在线 / cache=本地缓存兜底 / unavailable=缓存也缺）
EM_BOARDS_SOURCE = "live"

TOP_N = 5
PHASE_RULE_VER = 2
PHASES = ("主升", "启动")
LEVEL_SUFFIX = ("Ⅲ", "Ⅱ", "Ⅰ")   # 东财板块级后缀（同花顺名不带）

# 人工别名表（2026-09-19 阿狸咪的工程师·主人令「两卡对应清楚」配套）：
#   实测 42 个主升/启动板块里「塑料制品 / 橡胶制品 / 汽车服务及其他」三个，精确名与去级后缀归一都匹配不上；
#   旧版 `continue` 直接静默丢弃该板块 ⇒ 前端「启动 · N 个板块」与「板块资金趋势」卡计数对不上且无任何提示。
#   ⚠️ 只放两侧语义等价、已人工确认的映射；新增前必须核对两侧成分股范围，防张冠李戴。
#   命中别名时产物标记 match="alias:*"，便于审计追溯。
MANUAL_ALIAS = {
    "塑料制品": "塑料",           # 申万二级「塑料制品」↔ 东财「塑料」
    "橡胶制品": "橡胶",           # ↔ 东财「橡胶」
    "汽车服务及其他": "汽车服务",   # ↔ 东财「汽车服务」
}

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
EM = "https://push2delay.eastmoney.com"

# 🔴 2026-09-24 阿狸咪的工程师（主人令「一劳永逸」· 按特征扫全仓收口）：
#   小九今日已在 cloud_fetch_v8.py 用对照实验证伪「同 host 重试」，本脚本却仍是单 host。
#   铁证（v8_cn_fetch_cloud run 35997809909 step22）：
#     `_get_json` line 62 urlopen → `urllib.error.HTTPError: HTTP Error 502: Bad Gateway`
#     ⇒ 脚本 exit 1 ⇒ SECTOR_LEADERS 卡自 2026-09-22 18:15 停更（HEALTH_CHECK 连判 3 次 fail、
#       自愈派发 2 次皆无效，因为下一次仍打同一个 502 的 host）。
#   对照结论（cloud_fetch_v8.py _EM_HOSTS 注释，小九 2026-09-24 实测）：
#     同 host 重试 3 次 成功 1/17；**失败换 host 重试 成功 15/17** ⇒ 换 host 才是解药。
#   故此处与 cloud_fetch_v8.py 同源同语义地加 host 池；只改建连策略，不动任何取数口径。
EM_HOSTS = ("https://push2delay.eastmoney.com", "https://push2.eastmoney.com") + tuple(
    "https://%d.push2.eastmoney.com" % _i for _i in range(1, 13))


def log(msg):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def _get_json(url, timeout=20, retry=3, hosts=None):
    """东财 push2 请求（含重试）。

    🔴 2026-09-24 阿狸咪的工程师：**改为「换 host 重试」**（对照实验见 EM_HOSTS 注释）。
       · 未给 hosts 时行为**与旧版完全一致**（单 host + 退避 1.2s），向后兼容；
       · 给了 hosts 时，第 k 次尝试改用 hosts[k]，**保留原 path/query 只换域名**；
       · 退避同步调短为 0.6/1.1s（实测换 host 远胜空等，也给同轮其它任务让出预算）；
       · 解析失败 ⇒ 退回旧行为，绝不因此抛错。
    """
    last = None
    _path = ""
    if hosts:
        try:
            from urllib.parse import urlsplit, urlunsplit
            _sp = urlsplit(url)
            _path = urlunsplit(("", "", _sp.path, _sp.query, ""))
        except Exception:
            hosts = None
    delays = [0.6, 1.1]
    for i in range(retry):
        _u = url
        if hosts:
            _u = hosts[i % len(hosts)].rstrip("/") + _path
        try:
            req = urllib.request.Request(_u, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            if i < retry - 1:
                _d = delays[i] if i < len(delays) else delays[-1]
                if hosts:
                    print("  ⚠️ 东财 push2 抖动(%s) 尝试%d/%d: %s → %.1fs 后换 host 重试"
                          % (_u.split("/")[2], i + 1, retry, str(e)[:60], _d), flush=True)
                time.sleep(_d)
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


def _cache_load(path):
    """读 JSON 缓存；任何异常返回 None（兜底路径绝不抛错）。"""
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except Exception:
        return None


def _cache_save(path, obj):
    """原子写 JSON 缓存；失败仅记日志，不阻塞主流程。"""
    try:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
        os.replace(tmp, path)
    except Exception as e:
        log("cache save fail %s: %s" % (os.path.basename(path), str(e)[:60]))


# 🛡 2026-10-01 阿狸咪的工程师（第四层兜底·NeoData）：东财 push2 全家族 09-30 起对本机+云端
#   runner 全 HTTP 层 RemoteDisconnected（TCP/TLS 可建连、HTTP 请求即被掐），而 ①②③ 三层
#   兜底缓存需一次成功抓取才建立 ⇒ 东财断日缓存也缺 ⇒ 全板块 no_match/leaders 空（10-01
#   实测 4 板块 leaders 全 0、卡面龙头股位整段空白，主人令根治）。
#   NeoData「板块成分明细」（copilot.tencent.com/agenttool/v1/neodata）与 fetch_sector_rs.py
#   同源同 token 通道、实测可达；**仅在前三层全失效时启用**，任何失败 return None 不抛错。
#   节假日「今日」= 最近交易日（2026-10-01 与腾讯 qt.gtimg.cn 逐股核验 8/8 一致）。
NEODATA_URL = "https://copilot.tencent.com/agenttool/v1/neodata"
NEO_TOKEN_PATHS = (
    os.path.join(ROOT, "algorithms", ".neodata_token"),
    "E:/.workbuddy/skills/.neodata_token",
    os.path.expanduser("~/.workbuddy/.neodata_token"),
    os.path.expanduser("~/.workbuddy/skills/.neodata_token"),
)


def _neo_token():
    """NeoData token：algorithms/.neodata_token 优先（视为权威不查时效），其余 JSON 缓存
    路径要求 saved_at 12h 内。全缺返回 None（调用方按无兜底降级，行为与旧版一致）。"""
    for i, p in enumerate(NEO_TOKEN_PATHS):
        try:
            if not os.path.exists(p):
                continue
            with open(p) as f:
                cache = json.load(f)
            tok = cache.get("token") if isinstance(cache, dict) else None
            saved = cache.get("saved_at", 0) if isinstance(cache, dict) else 0
            if tok and (i == 0 or (time.time() - saved < 43200)):
                return tok
        except Exception:
            continue
    return None


def _neo_cons(name):
    """NeoData 板块成分兜底：返回与 fetch_cons 同构 rows（涨幅降序；调用方截 TOP_N）。
    仅前三层（东财在线/名单缓存/腾讯行情）全失效时调用；任何失败 return None 不抛错。
    表格行首带 '|' ⇒ split 空首元素：[1]=代码 [2]=名称 [4]=最新价 [6]=涨跌幅 [15]=主力净流入。"""
    import re as _re
    tok = _neo_token()
    if not tok:
        return None
    try:
        body = json.dumps({"query": "%s板块成分股今日涨幅前5" % name,
                           "channel": "neodata", "sub_channel": "workbuddy"}).encode("utf-8")
        req = urllib.request.Request(NEODATA_URL, data=body, method="POST", headers={
            "Authorization": "Bearer " + tok, "Content-Type": "application/json",
            "User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=40) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        if not d.get("suc"):
            log("neo fail %s: %s" % (name, str(d)[:80]))
            return None
        rows = []
        for item in (d.get("data", {}).get("apiData", {}).get("apiRecall") or []):
            if item.get("type") != "板块成分明细":
                continue
            for line in (item.get("content") or "").split("\n"):
                cols = [x.strip() for x in line.split("|")]
                if len(cols) < 8 or ":" in cols[0]:
                    continue
                m = _re.match(r"^(\d{6})\.(SZ|SH|BJ)$", cols[1])
                if not m:
                    continue

                def _f(idx):
                    try:
                        return float(cols[idx].replace(",", ""))
                    except Exception:
                        return None
                chg = _f(6)
                if chg is None:
                    continue
                rows.append({"code": m.group(1), "name": cols[2], "price": _f(4),
                             "chg": chg, "main_net": _f(15)})
        rows.sort(key=lambda r: r["chg"], reverse=True)
        return rows or None
    except Exception as e:
        log("neo cons fail %s: %s" % (name, str(e)[:60]))
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


def _resolve_bk(nm, exact, norm):
    """三档匹配板块代码：① 东财精确名 ② 去 Ⅰ/Ⅱ/Ⅲ 级后缀归一 ③ 人工别名表。
    返回 (bk, how)；how ∈ {exact, norm, alias:exact, alias:norm, ""}；全失败 (None, "")。"""
    if nm in exact:
        return exact[nm], "exact"
    k = _norm(nm)
    if k in norm:
        return norm[k], "norm"
    al = MANUAL_ALIAS.get(nm)
    if al:
        if al in exact:
            return exact[al], "alias:exact"
        ka = _norm(al)
        if ka in norm:
            return norm[ka], "alias:norm"
    return None, ""


def fetch_em_boards():
    """返回 (精确名映射, 归一名映射)。归一碰撞时优先 Ⅱ 级，其次先到先得。
    🛡 2026-09-30 小九：**本函数永不 raise**——东财全 host 断连（RemoteDisconnected）
    时回退 raw_data/em_boards_cache.json（成功轮全量回写、随 git 跨日累积）；
    缓存也没有则返回空映射（build 层按 no_match=1 明示保留板块），dict 断供根除。"""
    exact, norm = {}, {}
    global EM_BOARDS_SOURCE
    try:
        for pn in range(1, 9):
            url = ("%s/api/qt/clist/get?pn=%d&pz=100&po=1&np=1&fltt=2&invt=2"
                   "&fid=f3&fs=m:90+t:2&fields=f12,f14,f3" % (EM, pn))
            d = _get_json(url, hosts=EM_HOSTS)
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
    except Exception as e:
        log("⚠️ em boards 东财全 host 失败(%s) → 回退本地缓存" % str(e)[:70])
        cached = _cache_load(CACHE_BOARDS)
        if cached and cached.get("boards"):
            _boards = cached["boards"]
            exact.update(_boards)
            # 归一重建：Ⅱ 级优先（与在线逻辑同规则），其余先到先得
            for _pass in ("Ⅱ", None):
                for nm2, bk2 in _boards.items():
                    if _pass == "Ⅱ" and not nm2.endswith("Ⅱ"):
                        continue
                    if _pass != "Ⅱ" and nm2.endswith("Ⅱ"):
                        continue
                    k2 = _norm(nm2)
                    if k2 not in norm:
                        norm[k2] = bk2
            log("em boards cache: %d 条（updated=%s）" % (len(exact), cached.get("_updated", "?")))
            EM_BOARDS_SOURCE = "cache"
            return exact, norm
        log("em boards cache 无 ⇒ 本轮全部板块按 no_match 明示（结构不断供）")
        EM_BOARDS_SOURCE = "unavailable"
        return {}, {}
    if exact:
        _cache_save(CACHE_BOARDS, {"_updated": time.strftime("%Y-%m-%d %H:%M:%S"), "boards": exact})
        EM_BOARDS_SOURCE = "live"
    return exact, norm


def fetch_cons(bk):
    url = ("%s/api/qt/clist/get?pn=1&pz=400&po=1&np=1&fltt=2&invt=2"
           "&fid=f3&fs=b:%s&fields=f12,f14,f2,f3,f62" % (EM, bk))
    d = _get_json(url, hosts=EM_HOSTS)
    diff = ((d.get("data") or {}).get("diff")) or []
    # 🛡 2026-09-30 小九：成功轮全量回写成员名单缓存（code+name），供东财断连日
    #   腾讯行情兜底使用；随 git 跨 run/跨日累积。失败仅记日志不阻塞。
    _members = []
    for x in diff:
        _c, _n = x.get("f12"), x.get("f14")
        if _c and _n:
            _members.append({"code": str(_c), "name": str(_n)})
    if _members:
        _mc = _cache_load(CACHE_MEMBERS) or {}
        _mem_all = _mc.get("members") or {}
        _mem_all[bk] = _members
        _cache_save(CACHE_MEMBERS, {"_updated": time.strftime("%Y-%m-%d %H:%M:%S"), "members": _mem_all})
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


def _tx_cons(members):
    """腾讯 qt.gtimg.cn 批量行情兜底（2026-09-30 小九；源与 fetch_us_hk_map 同，
    云端已验证可达）。members=[{code,name}]（东财 6 位代码）→ 与 fetch_cons 同结构 rows。
    腾讯行情无主力净额 ⇒ main_net=None（前端龙头股位只展示涨幅，不受影响）。"""
    def _txkey(c):
        c = str(c)
        if c.startswith(("sh", "sz")):
            return c
        return ("sh" if c[:1] in ("6", "9") else "sz") + c

    out = []
    keys = [_txkey(m["code"]) for m in members]
    tx_headers = {"User-Agent": UA["User-Agent"], "Referer": "https://gu.qq.com/"}
    for i in range(0, len(keys), 30):
        url = "https://qt.gtimg.cn/q=" + ",".join(keys[i:i + 30])
        req = urllib.request.Request(url, headers=tx_headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            txt = resp.read().decode("gbk", "replace")
        for line in txt.split(";"):
            line = line.strip()
            if '="' not in line:
                continue
            f = line.split('="', 1)[1].rstrip('";').split("~")
            if len(f) <= 3 or not f[3]:
                continue
            try:
                price = float(f[3])
                pct = float(f[32]) if len(f) > 32 and f[32] not in ("", "-") else 0.0
            except (ValueError, IndexError):
                continue
            if price <= 0:
                continue
            out.append({"code": f[2], "name": f[1], "price": round(price, 2),
                        "chg": round(pct, 2), "main_net": None})
        time.sleep(0.2)
    out.sort(key=lambda r: r["chg"], reverse=True)
    return out


def fetch_cons_safe(bk):
    """双轮重试（东财）：每轮内部 _get_json 已带 3 重试；轮间 2.5s 缓冲防东财限流。
    🛡 2026-09-30 小九：东财两轮全断（RemoteDisconnected/502）时改走**腾讯成员缓存兜底**
    （名单来自 fetch_cons 成功轮回写的 raw_data/em_members_cache.json）；腾讯也失败才
    raise（走 leaders_error 明示保留路径）。绝不因东财单源断连而丢龙头股。"""
    last = None
    for rnd in range(2):
        try:
            return fetch_cons(bk)
        except Exception as e:
            last = e
            if rnd == 0:
                time.sleep(2.5)
    cached = _cache_load(CACHE_MEMBERS)
    ml = ((cached or {}).get("members") or {}).get(bk) or []
    if ml:
        try:
            rows = _tx_cons(ml)
            log("cons fallback(tencent) %s: %d rows（东财断连，名单缓存 updated=%s）"
                % (bk, len(rows), (cached or {}).get("_updated", "?")))
            return rows
        except Exception as e2:
            log("cons tencent fallback fail %s: %s" % (bk, str(e2)[:60]))
    raise last


def build():
    rs = _read_window_js(SRC_RS)
    if not rs or not rs.get("sectors"):
        log("no SECTOR_RS sectors")
        return None
    _dd = rs.get("data_date")
    src_date = str(_dd)[:10] if _dd else ""
    # 审计追溯：本产物完全派生自 SECTOR_RS，记录其版本戳，便于判断是否与前端同源同批
    log("source SECTOR_RS: update_time=%s data_date=%s sectors=%d"
        % (rs.get("update_time"), rs.get("data_date"), len(rs.get("sectors") or [])))
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
    n_nomatch = 0
    n_neo = 0
    if leaders_all:
        boards_exact, boards_norm = fetch_em_boards()
        log("em boards: exact=%d norm=%d" % (len(boards_exact), len(boards_norm)))
        for x in leaders_all:
            nm = x["name"]
            bk, how = _resolve_bk(nm, boards_exact, boards_norm)
            if not bk:
                _neo = _neo_cons(nm)
                if _neo:
                    n_neo += 1
                    log("neo fallback %s: %d rows（东财板块映射缺失，NeoData 兜底）" % (nm, len(_neo)))
                    sectors_out.append({
                        "name": nm, "bk": None, "phase": x.get("phase", "主升"),
                        "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                        "cons_count": len(_neo), "leaders": _neo[:TOP_N], "match": "neodata",
                    })
                    continue
                # 🎯 2026-09-19 主人令·两卡对应：不再静默丢板块！保留 + no_match=1，
                #   前端明示「该板块在东财无对应行业板块，需人工别名表补」⇒ 两卡计数因此对齐。
                n_nomatch += 1
                log("no-match: %s（东财无对应板块；已保留 + no_match=1，请补 MANUAL_ALIAS）" % nm)
                sectors_out.append({
                    "name": nm, "bk": None, "phase": x.get("phase", "主升"),
                    "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                    "cons_count": 0, "leaders": [], "no_match": 1, "match": "",
                })
                continue
            try:
                cons = fetch_cons_safe(bk)
            except Exception as e:
                _neo = _neo_cons(nm)
                if _neo:
                    n_neo += 1
                    log("neo fallback %s(%s): %d rows（东财个股断连，NeoData 兜底）" % (nm, bk, len(_neo)))
                    sectors_out.append({
                        "name": nm, "bk": bk, "phase": x.get("phase", "主升"),
                        "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                        "cons_count": len(_neo), "leaders": _neo[:TOP_N], "match": "neodata",
                    })
                    continue
                n_fail += 1
                log("cons fail2 %s(%s): %s —— 保留板块，个股留空待下轮补抓" % (nm, bk, str(e)[:60]))
                sectors_out.append({
                    "name": nm, "bk": bk, "phase": x.get("phase", "主升"),
                    "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                    "cons_count": 0, "leaders": [], "leaders_error": 1, "match": how,
                })
                continue
            sectors_out.append({
                "name": nm, "bk": bk, "phase": x.get("phase", "主升"),
                "pct_5d": x.get("pct_5d"), "pct_20d": x.get("pct_20d"),
                "cons_count": len(cons), "leaders": cons[:TOP_N], "match": how,
            })
            time.sleep(0.3)
    # 🛡 2026-09-25 阿狸咪的工程师（主人令「改好直接上线」· 卡面假刷新根治）：
    #   原口径 `"update_time": time.strftime(...)` = **本脚本落盘时刻**，与数据日期无关。
    #   实测后果：卡面「更新于」永远显示成今晚上次构建时间，而内容可能仍是 T-1
    #   （09-25 19:44 那轮SECTOR_LEADERS.js 的 update_time=09-25 19:44 但 data_date=09-24），
    #   主人据此判定「数据已刷新」⇒ 正是「今天有 t+1 数据、怎么全部没更新」的直接成因。
    #   修法（不造假原则）：update_time 一律取**源数据时间**（SECTOR_RS 的 update_time，
    #   与「板块资金趋势」卡同源同规则）；源缺失时才退回构建时刻，并显式写入
    #   `republish_time` 供排障。数据日期仍取 src_date，两者语义分离、不再混淆。
    _src_ut = ""
    try:
        if isinstance(rs, dict):
            _src_ut = rs.get("update_time") or ""
    except Exception:
        _src_ut = ""
    _built_ut = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": _src_ut or _built_ut,
        "republish_time": _built_ut,
        "data_date": src_date, "rule_ver": PHASE_RULE_VER, "top_n": TOP_N,
        "source": ("东方财富(push2delay) 板块成分股 + 同花顺 SECTOR_RS 板块周期"
                   + (" + 腾讯NeoData 板块成分明细（东财 push2 封禁兜底 %d 板块）" % n_neo if n_neo else "")),
        "phase": "主升+启动", "sector_count": len(sectors_out), "sectors": sectors_out,
        "nomatch_count": n_nomatch, "leaders_fail_count": n_fail,
        "neo_fallback_count": n_neo,
        "em_boards_source": EM_BOARDS_SOURCE,
        "note": "板块清单与 phase/pct_5d/pct_20d 直接取自 SECTOR_RS（与前端「板块资金趋势」卡同源同规则）；"
                "个股涨幅/价格为东方财富实时口径；leaders_error=1=个股行情本轮抓取失败待补抓；"
                "no_match=1=该板块在东财无对应行业板块（需补 MANUAL_ALIAS）；match 记录匹配方式(exact/norm/alias:*)",
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
    log("OK %s js_bytes=%d leaders_fail=%d no_match=%d neo_fallback=%d" % (
        " ".join("%s(%d/%d)" % (p, v[0], v[1]) for p, v in sorted(_cnt.items(), key=lambda kv: _po.get(kv[0], 9))),
        len(body), n_fail, n_nomatch, n_neo))
    return payload


if __name__ == "__main__":
    # 🛡 2026-09-24 阿狸咪的工程师（主人令「一劳永逸」· 红卡停更根治）：
    #   原为裸 `build()`：build() 内部在「SECTOR_RS 无 sectors」时 return None，
    #   而进程**仍以 0 退出** ⇒ 上层 run_algorithms 视为成功、failed_scripts 不记
    #   ⇒ 与产卡侧 save() 的静默跳过叠加，表现为「SECTOR_LEADERS 卡永久停在旧日期
    #   而整条算法链全绿」。实测铁证：raw_data/sector_leaders.json 停在
    #   2026-09-22 18:15（data_date 09-21），同轮 algo_run_report.json 却是 ok=1/fail=0。
    #   修法：空返回时显式打 ::error:: 并**非零退出**，让失败计入账本、Actions 标红。
    #   仅在「不写盘」路径上新增可见性，不改口径、不动任何好数据。
    _res = build()
    if not _res:
        print("::error title=v8-sector-leaders-no-data::SECTOR_LEADERS 构建返回空"
              "（SECTOR_RS 无 sectors 或全部板块均未产出）——本轮不写盘，"
              "卡片保持上一次成功日期；请检查上游 fetch_sector_rs 是否正常产出。")
        raise SystemExit(1)
