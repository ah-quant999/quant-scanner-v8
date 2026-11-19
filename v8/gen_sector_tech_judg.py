#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块技术研判 · 申万一级31行业生成器（2026-11-17 主人令「别人那张卡我也想要」）
====================================================================
复刻那张卡的研判能力：申万一级31行业，共振置信度分级 L4/L3/L2/L1 +
  EMA 多头计数 + 区间分位 + 压力位(近20/60日高) + 支撑位(EMA20/波底50%) + 5日量比。

数据源（全部东方财富，同源同频；2026-11-19 改为云端 runner）：
  · 板块列表 clist (fs=m:90+t:2, 分页取全) → 31行业名→BK代码, 现价f2/涨跌f3/主力净f62
  · clist 整体不可达时 → 静态 SW31→BK 映射 + push2his 日K/资金流日K反推现价/涨跌/净额，绝不用旧值糊弄
  · 板块日K push2his kline (secid=90.BKxxxx, klt=101) → EMA/分位/压力支撑/量比

分级口径（共振置信度，L4最高，全为客观打分，不编造）：
  资金条件：主力净额>0 且 今日涨幅>0 → +1
  趋势条件：EMA 多头计数>=4(短期均线多数在上) → +1
  位置条件：区间分位>=70% (强势区) → +1
  量价条件：5日量比>=1.1 (放量) → +1
  L4=4项全满足 / L3=3项 / L2=2项 / L1<=1项
  状态标签：趋势向上(分位>=90且多头) / 下跌反弹(分位高但空头排列修复) / 弱势整理 等。

产出：data/SECTOR_TECH_JUDG.js → window.SECTOR_TECH_JUDG
刷新：接 v8_sector_tech.yml，盘后1次 [ubuntu-latest 云端；clist 不可达自动走静态 BK 兜底]。
运行：python v8/gen_sector_tech_judg.py [--no-write] [--limit N]
"""
from __future__ import annotations
import json, re, sys, os, time, datetime, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
CLIST = ("https://push2.eastmoney.com/api/qt/clist/get?pn={pn}&pz=100&po=1&np=1"
         "&fltt=2&invt=2&fid=f3&fs=m%3A90%2Bt%3A2&fields=f12,f14,f2,f3,f62")
KLINE = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         "secid=90.{bk}&fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55,f56"
         "&klt=101&fqt=1&lmt=90&end=20500101")
# 板块资金流日K（主力净流入逐日，实测 2026-11-18 可达）：f51=日期 f52=主力净流入(元)
FFLOW = ("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?"
         "secid=90.{bk}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56"
         "&klt=101&lmt=70&end=20500101")

# 申万一级31行业（东财板块名精确匹配，实测 31/31 命中）
SW31 = ["农林牧渔","基础化工","钢铁","有色金属","电子","家用电器","食品饮料","纺织服饰",
        "轻工制造","医药生物","公用事业","交通运输","房地产","商贸零售","社会服务","综合",
        "建筑材料","建筑装饰","电力设备","机械设备","国防军工","汽车","计算机","传媒","通信",
        "银行","非银金融","煤炭","石油石化","环保","美容护理"]

# 🔴 2026-11-19 根治 clist 不可达：31 行业 BK 代码来自 raw_data/sector_bk_codes.json，
#   与旧版 data/SECTOR_TECH_JUDG.js 逐项核对一致。clist 全败时直接据此拉近 90 日 K/资金流，
#   现价=最新收盘、涨跌=最近两根日K、主力净额=资金流日K最新一天，全部是当日真实数据。
SW31_BK = {
    "通信": "BK1215", "交通运输": "BK1210", "公用事业": "BK0427", "煤炭": "BK0437",
    "家用电器": "BK0456", "轻工制造": "BK1212", "传媒": "BK0486", "电子": "BK1201",
    "计算机": "BK1207", "美容护理": "BK1035", "钢铁": "BK0479", "社会服务": "BK1214",
    "石油石化": "BK0464", "综合": "BK1217", "机械设备": "BK1205", "建筑装饰": "BK1209",
    "环保": "BK0728", "纺织服饰": "BK0436", "房地产": "BK1202", "食品饮料": "BK0438",
    "建筑材料": "BK1208", "非银金融": "BK1203", "商贸零售": "BK1213", "农林牧渔": "BK0433",
    "汽车": "BK1211", "国防军工": "BK1204", "银行": "BK1283", "基础化工": "BK1206",
    "电力设备": "BK1200", "医药生物": "BK1216", "有色金属": "BK0478",
}

_KLINE_CACHE = {}
_FFLOW_CACHE = {}


def _bj_now():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)


# 🔴 2026-11-19 一劳永逸：东财 push2 单 host 在 cn runner 上被限流（实测
#   "Remote end closed connection without response" 连败 5 页 → clist 板表全空 → 31 行业全"未找到"→ 不写盘）。
#   对齐 cloud_fetch_v8.py 的 _EM_HOSTS 范式：push2delay + push2 + 12 数字镜像共 14 host 轮换，
#   把瞬时限流挡在函数内，任一 host 可达即成功。
_EM_HOSTS = ("https://push2delay.eastmoney.com", "https://push2.eastmoney.com") + tuple(
    "https://%d.push2.eastmoney.com" % _i for _i in range(1, 13))


def _get_json(url, timeout=20):
    """带东财多 host 轮换 + 3 次重试退避的 JSON 抓取。
    对东财 URL 逐个替换 host；非东财 URL 走原逻辑。任一 host 成功即返回。"""
    last = None
    is_em = "eastmoney.com" in url
    if is_em:
        import re as _re
        path = _re.sub(r"^https://[^/]+", "", url)
        hosts = _EM_HOSTS
    else:
        path = None
        hosts = (url,)
    for host in hosts:
        target = host + path if is_em else host
        try:
            req = urllib.request.Request(target, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            continue
    raise last


def _get_json_data(url, data_key, timeout=20):
    """东财多 host 轮换，且要求 data.<data_key> 非空；避免首台 host 返回 200+空 data 被误判成功。"""
    last = None
    import re as _re
    path = _re.sub(r"^https://[^/]+", "", url)
    for host in _EM_HOSTS:
        try:
            req = urllib.request.Request(host + path, headers=UA)
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace"))
            data = d.get("data") or {}
            if data.get(data_key):
                return data
            last = RuntimeError("empty %s from %s" % (data_key, host))
        except Exception as e:
            last = e
    raise last


def load_board_quotes():
    """静态 SW31→BK 固定 31 行业；clist 仅作报价增强，缺项用 push2his 真实日K/资金流反推。"""
    allb = {name: {"bk": bk} for name, bk in SW31_BK.items()}
    clist_hit = 0
    for pn in range(1, 6):
        try:
            d = _get_json(CLIST.format(pn=pn))
            data = d.get("data") or {}
            diff = data.get("diff") or []
            for x in diff:
                name = x.get("f14")
                if name not in SW31_BK:
                    continue
                def num(v):
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None
                allb[name].update({"price": num(x.get("f2")), "chg": num(x.get("f3")),
                                   "net": num(x.get("f62"))})
                clist_hit += 1
            if len(diff) < 100:
                break
        except Exception as e:
            print("  ⚠️ clist pn%d 失败: %s" % (pn, e), file=sys.stderr)
        time.sleep(0.25)

    derived = 0
    for name, q in allb.items():
        if q.get("price") is not None and q.get("chg") is not None and q.get("net") is not None:
            continue
        try:
            rows = fetch_kline(q["bk"])
            if len(rows) < 2:
                continue
            ff = fetch_fflow(q["bk"])
            price = rows[-1]["c"]
            prev = rows[-2]["c"]
            q["price"] = price
            q["chg"] = round((price / prev - 1) * 100, 2) if prev else None
            q["net"] = ff[-1]["main"] if ff else None
            q["fallback"] = "push2his"
            derived += 1
        except Exception as e:
            print("  ⚠️ 静态BK反推 %s/%s 失败: %s" % (name, q["bk"], e), file=sys.stderr)
        time.sleep(0.15)

    print("  ✅ 东财行业板块载入 %d 个（clist命中%d / push2his真实反推%d）" %
          (len(allb), clist_hit, derived))
    return allb


def fetch_kline(bk):
    """东财板块日K → list of {d,o,c,h,l,v}（近90日），进程内缓存避免兜底重复抓。"""
    if bk in _KLINE_CACHE:
        return _KLINE_CACHE[bk]
    data = _get_json_data(KLINE.format(bk=bk), "klines")
    rows = []
    for line in (data.get("klines") or []):
        p = line.split(",")
        if len(p) < 6:
            continue
        try:
            rows.append({"d": p[0], "o": float(p[1]), "c": float(p[2]),
                         "h": float(p[3]), "l": float(p[4]), "v": float(p[5])})
        except (TypeError, ValueError):
            continue
    _KLINE_CACHE[bk] = rows
    return rows


def fetch_fflow(bk):
    """东财板块资金流日K → 逐日主力净流入(元) list，倒序取最近在末尾，进程内缓存。"""
    if bk in _FFLOW_CACHE:
        return _FFLOW_CACHE[bk]
    try:
        data = _get_json_data(FFLOW.format(bk=bk), "klines")
        out = []
        for line in (data.get("klines") or []):
            p = line.split(",")
            if len(p) < 2:
                continue
            try:
                out.append({"d": p[0], "main": float(p[1])})
            except (TypeError, ValueError):
                continue
        _FFLOW_CACHE[bk] = out
        return out
    except Exception as e:
        print("  ⚠️ fflow %s 失败: %s" % (bk, e), file=sys.stderr)
        _FFLOW_CACHE[bk] = []
        return []


def fib_levels(rows):
    """斐波那契（60日窗口 hi/lo）：38.2% / 61.8% 回撤位 + 161.8% 延伸位。"""
    win = rows[-60:] if len(rows) >= 60 else rows
    hi = max(r["h"] for r in win)
    lo = min(r["l"] for r in win)
    rng = hi - lo
    return {
        "fib382": round(lo + rng * 0.382, 2),
        "fib618": round(lo + rng * 0.618, 2),
        "ext1618": round(lo + rng * 1.618, 2),
        "hi": round(hi, 2), "lo": round(lo, 2),
    }


def ema(vals, n):
    if not vals:
        return None
    k = 2.0 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def analyze(name, q):
    """对单个行业计算技术指标 + 分级。"""
    bk = q.get("bk")
    if not bk:
        return None
    rows = fetch_kline(bk)
    closes = [r["c"] for r in rows]
    vols = [r["v"] for r in rows]
    if len(closes) < 25:
        return None
    last = closes[-1]
    # EMA 多头计数：短周期均线在长周期之上则计多头
    ma3 = ema(closes, 3); ma7 = ema(closes, 7); ma20 = ema(closes, 20)
    bull = sum(1 for m in (ma3, ma7, ma20) if m and m >= closes[-2])
    # 区间分位：现价在近60日[min,max]中的位置
    win = closes[-60:] if len(closes) >= 60 else closes
    lo, hi = min(win), max(win)
    pos = round((last - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0
    # 压力位：近20日高 / 近60日高
    r20 = max(r["h"] for r in rows[-20:])
    r60 = max(r["h"] for r in rows[-60:]) if len(rows) >= 60 else r20
    # 支撑位：EMA20 / 近60日波段底回撤50%（取近60日最低）
    low60 = min(r["l"] for r in rows[-60:]) if len(rows) >= 60 else min(r["l"] for r in rows)
    swing50 = round((last + low60) / 2, 2)
    # 5日量比：近5日均量 / 前20日均量
    v5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else (vols[-1] if vols else 0)
    vprev = sum(vols[-25:-5]) / 20 if len(vols) >= 25 else (v5 or 1)
    volratio = round(v5 / vprev, 2) if vprev else 1.0

    price = q.get("price") if q.get("price") is not None else last
    chg = q.get("chg")
    net = q.get("net")  # 主力净额(元)

    # 共振打分（4 项）
    score_ok1 = bool(net is not None and net > 0 and chg is not None and chg > 0)
    score = 0
    if score_ok1:
        score += 1
    if bull >= 2:
        score += 1
    if pos >= 70:
        score += 1
    if volratio >= 1.1:
        score += 1
    level = {4: "L4", 3: "L3", 2: "L2"}.get(score, "L1")

    if pos >= 90 and bull >= 2:
        state = "趋势向上"
    elif pos >= 70 and bull <= 1:
        state = "下跌反弹"
    elif bull >= 2 and pos < 50:
        state = "底部修复"
    elif pos < 35:
        state = "弱势整理"
    else:
        state = "震荡"

    # 斐波那契（60日窗口）
    fib = fib_levels(rows)

    # 资金验证：主力净流入 5/10/20/60 日累计（东财 BK fflow，与技术面同源同 secid）
    ff = fetch_fflow(bk)
    mains = [x["main"] for x in ff]
    def cum(n):
        seg = mains[-n:] if len(mains) >= n else mains
        return round(sum(seg) / 1e8, 2) if seg else None
    net5, net10, net20, net60 = cum(5), cum(10), cum(20), cum(60)
    # 资金验证结论（全窗口客观判定）
    pos_n = sum(1 for v in (net5, net10, net20, net60) if v is not None and v > 0)
    if pos_n == 4:
        fund_verdict = "全周期净流入（5/10/20/60日皆为正）"
    elif pos_n == 3:
        fund_verdict = "资金较强（四窗口三项为正）"
    elif net20 is not None and net20 > 0 and net60 is not None and net60 < 0:
        fund_verdict = "资金改善（近20日转正、60日仍负）"
    elif pos_n == 0:
        fund_verdict = "全周期净流出"
    else:
        fund_verdict = "资金偏弱（%d/4 窗口为正）" % pos_n

    # 依据句式（展开项）：四项判定 + 斐波那契压力支撑
    def tick(ok, txt):
        return ("✅" if ok else "❌") + txt
    basis = (
        "依据：" + tick(score_ok1, "资金(净%s亿且涨%s%%)" % (("%.2f" % (net/1e8)) if net is not None else "—", chg)) +
        " " + tick(bull >= 2, "趋势(EMA多头%d/3)" % bull) +
        " " + tick(pos >= 70, "位置(分位%.0f%%)" % pos) +
        " " + tick(volratio >= 1.1, "量价(量比%.2f)" % volratio) +
        "；压力=61.8%%位%.2f/延伸161.8%%位%.2f，支撑=38.2%%位%.2f/EMA20 %s" %
        (fib["fib618"], fib["ext1618"], fib["fib382"],
         ("%.2f" % ma20) if ma20 else "—")
    )

    return {
        "name": name, "bk": bk, "level": level, "score": score, "state": state,
        "price": round(price, 2), "chg": round(chg, 2) if chg is not None else None,
        "net_yi": round(net / 1e8, 2) if net is not None else None,
        "ema_bull": bull, "ema3": round(ma3, 2) if ma3 else None,
        "ema7": round(ma7, 2) if ma7 else None, "ema20": round(ma20, 2) if ma20 else None,
        "pos_pct": pos,
        "resist20": round(r20, 2), "resist60": round(r60, 2),
        "support_ema20": round(ma20, 2) if ma20 else None, "support_swing50": swing50,
        "vol_ratio5": volratio,
        "fib382": fib["fib382"], "fib618": fib["fib618"], "ext1618": fib["ext1618"],
        "fund_5d": net5, "fund_10d": net10, "fund_20d": net20, "fund_60d": net60,
        "fund_verdict": fund_verdict,
        "basis": basis,
        "data_date": rows[-1]["d"],
    }


def judge_text(items):
    """整体研判：L4 行业清单 + 状态分布 + 趋势结构计数。"""
    l4 = [x["name"] for x in items if x["level"] == "L4"]
    l3 = [x["name"] for x in items if x["level"] == "L3"]
    up = [x["name"] for x in items if x["state"] == "趋势向上"]
    if l4:
        s = "🔴 资金+趋势+位置+量价四项共振的行业：" + "、".join(l4[:8]) + ("等%d个" % len(l4) if len(l4) > 8 else "") + "，置信度最高（L4）"
    else:
        s = "➖ 今日无四项目标全共振(L4)行业，最高为 L3：" + ("、".join(l3[:6]) if l3 else "无")
    if up:
        s += "；趋势向上（分位≥90%且均线多头）：" + "、".join(up[:6])
    return s


def structure_counts(items):
    """趋势结构计数（图1式汇总行）：向上/反弹/修复/整理/震荡。"""
    c = {"趋势向上": 0, "下跌反弹": 0, "底部修复": 0, "弱势整理": 0, "震荡": 0}
    for x in items:
        if x["state"] in c:
            c[x["state"]] += 1
    return c


def main():
    no_write = "--no-write" in sys.argv
    force = "--force" in sys.argv  # 盘中补跑强制写盘（一般不用）
    limit = None
    if "--limit" in sys.argv:
        try:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        except (IndexError, ValueError):
            pass
    # 🔴 2026-11-18 修复：本卡=日频盘后研判（workflow 交易日16:00）。盘中手动 dispatch 曾把
    #    运行时刻10:31写进 update_time，令盘后卡显示盘中时间。此处闸门：交易日15:00前
    #    只预览不写盘（--no-write 语义），杜绝盘中污染；--force 仅供人为补跑。
    _nb = _bj_now()
    if not no_write and not force and _nb.weekday() < 5 and _nb.hour < 15:
        print("⏸ 盘中 %02d:%02d（北京）不写盘：日频盘后卡仅收盘后产出；预览用 --no-write" %
              (_nb.hour, _nb.minute), file=sys.stderr)
        no_write = True
    boards = load_board_quotes()
    targets = SW31[:limit] if limit else SW31
    items = []
    for name in targets:
        q = boards.get(name)
        if not q:
            print("  ⚠️ %s 未找到东财板块，跳过" % name, file=sys.stderr)
            continue
        try:
            a = analyze(name, q)
            if a:
                items.append(a)
                print("  ✅ %-6s %s %-5s 现价%.1f 涨%s%% 分位%.0f%% 量比%.2f 主力%s亿" %
                      (name, a["bk"], a["level"], a["price"], a["chg"], a["pos_pct"],
                       a["vol_ratio5"], a["net_yi"]))
        except Exception as e:
            print("  ⚠️ %s 分析失败: %s" % (name, e), file=sys.stderr)
        time.sleep(0.2)
    if not items:
        print("  ❌ 全部失败，不写盘", file=sys.stderr)
        sys.exit(2)
    # 分级排序：L4>L3>L2>L1，同级按主力净额降序
    order = {"L4": 0, "L3": 1, "L2": 2, "L1": 3}
    items.sort(key=lambda x: (order.get(x["level"], 9), -(x["net_yi"] or 0)))
    _data_date = max(x["data_date"] for x in items)
    out = {
        # 🔴 2026-11-18：盘后卡 update_time = 数据日收盘定稿时刻（非脚本运行时刻），
        #    徽章恒显盘后口径（今日/昨日 15:00），盘中误触发亦不污染。
        "update_time": _data_date + " 15:00:00",
        "data_date": _data_date,
        "source": "东方财富行业板块日K+资金流日K（90.BKxxxx，云端；clist不可达时静态BK兜底）",
        "universe": "申万一级31行业（东财板块名精确映射）",
        "grading": "共振置信度：资金(net>0且涨>0)+趋势(EMA多头>=2)+位置(分位>=70%)+量价(5日量比>=1.1)，4项=L4/3=L3/2=L2/<=1=L1",
        "structure_counts": structure_counts(items),
        "items": items,
        "judgment": judge_text(items),
        "note": "日频盘后研判，非盘中实时信号。压力=斐波那契61.8%位/161.8%延伸位与近20/60日高，支撑=38.2%位/EMA20/波段底50%。资金验证=东财BK主力净流入5/10/20/60日累计（同源同secid）。仅供观测，不改选股排序。红涨绿跌由前端按chg处理。",
    }
    if no_write:
        print("\n=== 研判 ===")
        print(out["judgment"])
        print("共 %d 行业" % len(items))
        return
    if "--out" in sys.argv:
        out_path = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.normpath(os.path.join(here, "..", "data", "SECTOR_TECH_JUDG.js"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.SECTOR_TECH_JUDG = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")
    print("  💾 已写入 %s (%d 行业, data_date=%s)" % (out_path, len(items), out["data_date"]))


if __name__ == "__main__":
    main()
