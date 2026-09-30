# -*- coding: utf-8 -*-
"""scripts/fetch_us_hk_map.py —— 「隔夜美股强势 → A股/港股 映射」数据生成器（v8）

用途
----
盘前（北京时间 08:25，美东已收盘）抓取**美股最近一个交易日**的近期动量，筛出
「近期涨幅好的美股个股 / ETF」，并把它们映射到对应的 A 股 / 港股标的，供前端
「🌙 隔夜美股强势 · 映射A/港股」观测卡渲染。

设计铁律（与 v8 既有审计结论对齐，勿轻易推翻）
--------------------------------------------
1. **只取「隔夜」**：08:25 抓的是美东上一交易日收盘，语义天然是隔夜。
   前端与文案禁止写成「实时 / 今日」。
2. **交易所前缀运行时发现，禁硬编码**：实测同一批美股 ETF 分散在 105(NASDAQ) /
   106(NYSE) / 107(NYSE Arca)，A 股分散在 1(沪) / 0(深)，港股在 116。
   硬编码前缀必然出错（历史事故：BABA 写成 105 实为 106；MCHI/PGJ 实为 105 而非 106）。
   本模块对每个候选裸代码用多前缀探测，按 `f12` 精确命中自动锁定 secid。
3. **映射表必须过「名称一致性闸门」**：US 侧中文名取东财，HK 侧中文名取
   **腾讯 gtimg（独立源）**，去掉 `-W / -SW / -S / (ADR)` 归一后须互相包含，
   否则该对**剔除并计入 gate 统计**，绝不静默降级。
   实测该闸门对 8 个故意混入的错配对（PDD→09988 / TAL→09901 / IQ→09626 /
   MOMO→03690 / FUTU→03690 / ATAT→09676 / VNET→00837 / WX→02359）**全部抓出，零漏网**。
4. **动量字段一次取全**：东财 `push2delay` 的 `ulist.np/get` 直接返回多周期涨跌幅，
   无需 K 线（东财 kline 端点对美股返回空；新浪美股日K 末根会滞后一天，仅可作对照）。
   字段语义（经新浪全历史日K 逐位精确对照确认）：
     f3=当日% / f127=3日% / f109=5日% / f160=10日% / f110=20日% / f24=60日%
5. **失败返回 None，不抛异常**：由调用方（cloud_fetch_v8.run）决定重试，
   绝不让单个数据源把整轮 job 打挂。

依赖：requests（cloud_fetch_v8.py 已依赖，runner 具备）
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

CST = timezone(timedelta(hours=8))
ET = ZoneInfo("America/New_York")  # 隔夜交易日必须按美东判，勿用 CST（会多算一天）

EM_DELAY = "https://push2delay.eastmoney.com"
# 🔴 2026-09-29 一劳永逸（小九）：换 host 重试 —— 09-24 对照实验已实证「东财 clist 单 host 单次
#   成功率仅 ~6-10%、换 host 才是解药，同 host 空等≈无效」（见 cloud_fetch_v8._EM_HOSTS 注释）。
#   当日实证：09-24 07:07 / 09-28 09:33 两轮 premarket 大盘锚(100.SPX/NDX/DJIA)全空、
#   而**同函数同轮** ADR/ETF 报价可得 ⇒ 单 host 3 连重试缺陷；本表与 cloud_fetch_v8 同源同语义。
EM_HOSTS = (EM_DELAY, "https://push2.eastmoney.com") + tuple(
    "https://%d.push2.eastmoney.com" % _i for _i in range(1, 13))
EM_UT = "b2884a393a59ad64002292a3e90d46a5"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
EM_HEADERS = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/", "Accept": "*/*"}
TX_HEADERS = {"User-Agent": UA, "Referer": "https://gu.qq.com/"}

# 动量字段（顺序即前端展示顺序）
MOM_FIELDS = [("d1", "f3"), ("d3", "f127"), ("d5", "f109"),
              ("d10", "f160"), ("d20", "f110"), ("d60", "f24")]
EM_FIELDS = "f12,f13,f14,f2,f124," + ",".join(f for _, f in MOM_FIELDS)

# 前缀候选
P_US = ["105", "106", "107"]
P_A = ["1", "0"]
P_HK = ["116"]
P_IDX = ["100", "124", "2", "1", "0"]

# ── 策划表 ①：中概 ADR ↔ 港股（31 对，全部通过名称闸门机检）──────────────────
ADR_PAIRS = [
    ("BABA", "09988"), ("JD", "09618"), ("BIDU", "09888"), ("NTES", "09999"),
    ("TCOM", "09961"), ("BEKE", "02423"), ("YUMC", "09987"), ("HTHT", "01179"),
    ("ZLAB", "09688"), ("MNSO", "09896"), ("TME", "01698"), ("ATHM", "02518"),
    ("ZH", "02390"), ("WB", "09898"), ("KC", "03896"), ("EDU", "09901"),
    ("LI", "02015"), ("NIO", "09866"), ("XPEV", "09868"), ("BILI", "09626"),
    ("ZTO", "02057"), ("GDS", "09698"), ("HCM", "00013"), ("QFIN", "03660"),
    ("NOAH", "06686"), ("BZUN", "09991"), ("TUYA", "02391"), ("BZ", "02076"),
    ("ONC", "06160"), ("HSBC", "00005"), ("PUK", "02378"),
]

# ── 策划表 ②：美股 ETF → A股 / 港股 / 指数 目标（55 组）──────────────────────
# 只保留「确有 A/港股或指数对位标的」的 ETF；ARKK / IWM / MAGS / EEM / VWO /
# URA / XRT / JETS / ITB / XLI / VNM 等无对位标的者**不入表**（主人令：只要映射得到的）。
ETF_MAP = [
    # 中国 / 中概主题
    ("KWEB", [("A", "513050")]),
    ("CWEB", [("HK", "07226")]),
    ("CQQQ", [("A", "513050"), ("HK", "03033")]),
    ("KTEC", [("HK", "03033"), ("IDX", "HSTECH")]),
    ("KSTR", [("A", "588000")]),
    ("PGJ", [("A", "513050")]),
    ("FXI", [("A", "510300"), ("HK", "02800"), ("IDX", "HSI")]),
    ("MCHI", [("A", "510300"), ("IDX", "HSI")]),
    ("ASHR", [("A", "510300")]),
    ("KBA", [("A", "510300")]),
    ("GXC", [("A", "510300")]),
    ("FLCH", [("A", "510300")]),
    ("CHAU", [("A", "510300")]),
    ("CHIQ", [("A", "159928")]),
    ("KURE", [("A", "512170")]),
    ("KGRN", [("A", "516160")]),
    ("EWH", [("HK", "02800"), ("IDX", "HSI")]),
    ("YINN", [("HK", "07226")]),
    ("YANG", [("HK", "07226")]),
    # 美股宽基
    ("QQQ", [("A", "159941")]),
    ("QQQM", [("A", "159941")]),
    ("TQQQ", [("A", "159941")]),
    ("SPY", [("A", "513500")]),
    ("VOO", [("A", "513500")]),
    ("IVV", [("A", "513500")]),
    ("DIA", [("A", "513400"), ("IDX", "DJIA")]),
    # 半导体 / 科技 / 生物医药
    ("SOXX", [("A", "512480")]),
    ("SMH", [("A", "512480")]),
    ("PSI", [("A", "512480")]),
    ("XSD", [("A", "512480")]),
    ("XBI", [("A", "512290")]),
    ("IBB", [("A", "512290")]),
    ("XLV", [("A", "512170")]),
    ("XLK", [("A", "515000")]),
    ("XLC", [("A", "515880")]),
    ("AIQ", [("A", "159819")]),
    ("BOTZ", [("A", "159770")]),
    ("ROBO", [("A", "159770")]),
    # 周期 / 行业
    ("XLE", [("A", "159930")]),
    ("XLF", [("A", "512800")]),
    ("XLP", [("A", "159928")]),
    ("XLY", [("A", "159928")]),
    ("XLU", [("A", "159611")]),
    ("XLB", [("A", "512400")]),
    ("GDX", [("A", "518880")]),
    # 商品 / 债券 / 海外
    ("GLD", [("A", "518880")]),
    ("SLV", [("A", "161226")]),
    ("USO", [("A", "501018")]),
    ("TLT", [("A", "511260")]),
    ("INDA", [("A", "164824")]),
    ("EWJ", [("A", "513520")]),
    # 新能源 / 车
    ("TAN", [("A", "515790")]),
    ("LIT", [("A", "159755")]),
    ("ICLN", [("A", "516160")]),
    ("KARS", [("A", "516110")]),
]

# 预留：**反向/做空**类 ETF（涨幅高 = 对应中国/主题资产走弱，方向与映射标的正相反）
#   前端必须显式标注「反向」，否则「YANG 涨 5% → 南方两倍做多恒生科技」会严重误导。
INVERSE_US = {"YANG", "FXP", "CHAD", "SH", "SDOW", "SQQQ", "SPXU", "TZA", "FAZ"}

# 隔夜大盘锚：**显式 secid，禁止走多前缀探测**
#   实测教训（2026-09-19）：`resolve(["DJIA"], ["105","106","107"])` 会命中
#   "Global X Dow 30 Covered Call ETF"（一只美股 ETF 恰好也叫 DJIA）——指数与 ETF
#   存在同代码不同市场号的情况，探测必错。SPX / NDX 更是压根不在 105/106/107，
#   而在 100（全球指数）。以下三个 secid 均已点名机检通过（价格 7650.5 / 26522.55 / 51682.64）。
US_ANCHORS = [
    ("100.SPX", "SPX", "标普500"),
    ("100.NDX", "NDX", "纳斯达克100"),
    ("100.DJIA", "DJIA", "道琼斯"),
]

MKT_LABEL = {"A": "A股", "HK": "港股", "IDX": "指数"}
PREFIXES = {"A": P_A, "HK": P_HK, "IDX": P_IDX}


def _now():
    return datetime.now(CST)


def _f(v):
    """安全转 float；空/'-'/None -> None。"""
    try:
        if v is None or v == "" or v == "-":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _em(batch, fields=EM_FIELDS, timeout=20, retries=3):
    """东财 ulist.np 批量点名（🔴 2026-09-29 改换 host 重试，见 EM_HOSTS 注释）。返回行列表（失败返回 []）。

    ⚠️ 只对「请求异常/非 JSON」换 host 重试；**空 diff 不重试** —— resolve() 的多前缀探测
       大量批次合法地为空，按空重试会把探测耗时放大 3 倍。空 diff 场景由调用方自判
       （锚点等「必非空」调用各自带重试+兜底）。"""
    last_err = None
    for i in range(retries):
        host = EM_HOSTS[i % len(EM_HOSTS)]
        try:
            r = requests.get(host + "/api/qt/ulist.np/get",
                             params={"fltt": "2", "invt": "2", "ut": EM_UT,
                                     "fields": fields, "secids": ",".join(batch)},
                             headers=EM_HEADERS, timeout=timeout)
            d = (r.json().get("data") or {}).get("diff")
            if isinstance(d, dict):
                d = list(d.values())
            return d or []
        except Exception as e:  # noqa: BLE001
            last_err = e
            if i < retries - 1:
                time.sleep(0.8)
    print(f"   [us_hk_map] ⚠️ ulist 点名失败（换host {retries} 次）: {type(last_err).__name__}: {last_err}")
    return []


def resolve(codes, prefixes, chunk=50):
    """多前缀探测 → 按 f12 精确命中锁定 secid。返回 {code: row}。

    行内含交易所市场号 f13，故 secid = "{f13}.{f12}"，无需人工维护前缀。
    若同一裸代码在多个前缀下都解析成功（跨市场同代码），保留先命中者并打印告警，
    便于人工复核（历史同类事故：DJIA 同时是指数名与一只美股 ETF 的代码）。
    """
    want = set(codes)
    got, clash = {}, []
    combos = ["%s.%s" % (p, c) for p in prefixes for c in codes]
    for i in range(0, len(combos), chunk):
        for row in _em(combos[i:i + chunk]):
            code = str(row.get("f12") or "")
            name = str(row.get("f14") or "").strip()
            if code not in want or not name or name == "-":
                continue
            if code in got:
                if got[code].get("f14") != name:
                    clash.append("%s: %s.%s(%s) vs %s.%s(%s)"
                                 % (code, got[code].get("f13"), code, got[code].get("f14"),
                                    row.get("f13"), code, name))
                continue
            got[code] = row
    if clash:
        print("   [us_hk_map] ⚠️ 跨市场同代码告警（已保留先命中者，请人工复核）: " + "; ".join(clash))
    # 🛡 2026-09-30 一劳永逸（阿狸咪的工程师）：东财未命中的 code → 腾讯+新浪兜底。
    #   东财美股接口 09-28 起对本机与云端同时拒绝（RemoteDisconnected 双侧实证）；
    #   部分命中场景同样只对缺失部分补，成本最小化。市场按前缀组合推断，
    #   无法识别的组合（不该出现）保持原行为（空就是空，由上层 None-重试兜底）。
    _miss = sorted(want - set(got))
    if _miss:
        _mk = _market_of(prefixes)
        if _mk:
            print("   [us_hk_map] 🛡 东财未命中 %d/%d（%s）→ 腾讯+新浪兜底"
                  % (len(_miss), len(want), _mk))
            got.update(_resolve_tx(_miss, _mk))
    return got


def tx_names(keys):
    """腾讯 gtimg 中文名（独立源，GBK）。keys 形如 hk09988 / usBABA。"""
    out = {}
    for i in range(0, len(keys), 30):
        try:
            r = requests.get("https://qt.gtimg.cn/q=" + ",".join(keys[i:i + 30]),
                             headers=TX_HEADERS, timeout=15)
            txt = r.content.decode("gbk", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        for line in txt.split(";"):
            line = line.strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            parts = v.strip().strip('"').split("~")
            if len(parts) > 1:
                out[k.replace("v_", "").strip()] = parts[1].strip()
    return out


# ── 🛡 2026-09-30 腾讯+新浪兜底（阿狸咪的工程师·一劳永逸）─────────────────────
# 背景：东财美股 ulist（push2delay/push2 系）自 2026-09-28 09:20 后对本机（中国家宽）
#   与云端（GHA 美国机房）**同时** RemoteDisconnected（两侧实测铁证），主路径已死；
#   原兜底只覆盖三大指数锚，86 只明细标的全空 ⇒ 整卡 return None ⇒ 断更。
# 方案：resolve() 对东财未命中的 code 自动降级 ——
#   · 报价/名称/涨跌幅/时间戳 = 腾讯 qt.gtimg.cn（指数锚兜底同源，云端已验证可达）；
#   · 多周期动量 = 新浪美股日K（US_MinKService.getDailyK，num=3000 一次拉全 3024 根、
#     末根=最近已收盘交易日；09-30 实测以 09-25 为端点复算 BABA 六周期，与东财
#     09-28 产物 mom 逐位一致：-0.8/-5.65/-3.09/0.4/-5.65/11.99 ⇒ 口径完全复刻）。
# 兜底行造与东财行同构的伪行（f12/f14/f2/f3/f124 + 动量字段位），下游 build() 零改动；
# 行内带 _src="tx" 标记，build() 汇总进 gate 透明透出。前端零消费 secid（09-30 grep 实证），
# f13 置空串不影响任何消费方。

TX_IDX_MAP = {"HSI": "hkHSI", "HSTECH": "hkHSTECH", "DJIA": "usDJI"}


def _tx_txkey(code, market):
    """裸代码 → 腾讯行情键；无映射返回 None。"""
    if market == "US":
        return "us" + code
    if market == "HK":
        return "hk" + code
    if market == "A":
        # A 股 ETF：5 开头=沪 sh，其余（1/0 开头）=深 sz（本表目标全部为 ETF/指数）
        return ("sh" if code.startswith("5") else "sz") + code
    if market == "IDX":
        return TX_IDX_MAP.get(code)
    return None


def _tx_quotes(tx_keys):
    """腾讯 gtimg 批量实时报价。返回 {tx_key: {name, price, pct, ts_str}}。

    字段位（实测 09-30）：p[1]=中文名 p[3]=最新价 p[32]=当日涨跌% p[30]=时间戳
    （美股「2026-09-29 16:00:01」美东；港/A「2026/09/30 11:59:59」北京）。
    无效代码返回 v_pv_none_match=1 之类短行 ⇒ 按 len<=32 跳过（诚实缺失）。"""
    out = {}
    for i in range(0, len(tx_keys), 30):
        try:
            r = requests.get("https://qt.gtimg.cn/q=" + ",".join(tx_keys[i:i + 30]),
                             headers=TX_HEADERS, timeout=15)
            txt = r.content.decode("gbk", errors="replace")
        except Exception as e:  # noqa: BLE001
            print(f"   [us_hk_map] ⚠️ 腾讯报价批量失败: {type(e).__name__}: {e}")
            continue
        for line in txt.split(";"):
            line = line.strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.replace("v_", "").strip()
            p = v.strip().strip('"').split("~")
            if len(p) <= 32 or not p[3] or p[3] in ("0.000", ""):
                continue
            try:
                out[k] = {"name": p[1].strip(), "price": float(p[3]),
                          "pct": float(p[32]), "ts_str": (p[30] or "").strip()}
            except ValueError:
                continue
    return out


def _sina_closes(symbol):
    """新浪美股全历史日K收盘。返回 [(date_str, close)]；失败 []。"""
    try:
        r = requests.get(
            "https://stock.finance.sina.com.cn/usstock/api/json_v2.php/"
            "US_MinKService.getDailyK?symbol=%s&page=1&num=3000" % symbol,
            headers={"User-Agent": UA}, timeout=20)
        arr = json.loads(r.text)
        return [(str(x.get("d") or ""), float(x.get("c"))) for x in arr
                if x.get("d") and x.get("c")]
    except Exception as e:  # noqa: BLE001
        print(f"   [us_hk_map] ⚠️ 新浪日K失败 {symbol}: {type(e).__name__}: {e}")
        return []


def _mom_from_closes(closes, end_date):
    """东财多周期动量的新浪复刻。dN = 末根收盘 / N 个交易日前收盘 - 1。

    护栏（诚实铁律）：新浪末根日期必须 == 腾讯报价的美东日期，否则整体 {} ——
    端点错位硬算出来的动量是假数据，宁缺毋滥。"""
    if not closes or len(closes) < 61 or closes[-1][0] != end_date:
        return {}
    last = closes[-1][1]
    return {"d%d" % n: round((last / closes[-1 - n][1] - 1) * 100, 2)
            for n in (1, 3, 5, 10, 20, 60)}


def _parse_tx_ts(ts_str, us=False):
    """腾讯 p[30] → epoch。美股按美东、港/A 按北京解释；失败 None。"""
    try:
        s = (ts_str or "").replace("/", "-").strip()
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=(ET if us else CST)).timestamp()
    except Exception:  # noqa: BLE001
        return None


def _resolve_tx(codes, market):
    """腾讯+新浪兜底版 resolve。返回 {code: 伪东财行}（结构同构，下游零改动）。"""
    keys = {}
    for c in codes:
        tk = _tx_txkey(c, market)
        if tk:
            keys[c] = tk
    if not keys:
        return {}
    qs = _tx_quotes(list(keys.values()))
    got = {}
    for c, tk in keys.items():
        q = qs.get(tk)
        if not q:
            print(f"   [us_hk_map] ⚠️ 腾讯亦无 {market} {c}（诚实缺失，计入 gate）")
            continue
        row = {"f12": c, "f13": "", "f14": q["name"],
               "f2": q["price"], "f3": q["pct"],
               "f124": _parse_tx_ts(q["ts_str"], us=(market == "US")),
               "_src": "tx"}
        if market == "US":
            # f3 本身就是 d1（与东财同位）；d3/d5/d10/d20/d60 填东财字段位
            m = _mom_from_closes(_sina_closes(c), (q["ts_str"] or "")[:10])
            time.sleep(0.15)  # 新浪礼貌间隔
            row["f127"] = m.get("d3")
            row["f109"] = m.get("d5")
            row["f160"] = m.get("d10")
            row["f110"] = m.get("d20")
            row["f24"] = m.get("d60")
        got[c] = row
        print(f"   [us_hk_map] 🛡 腾讯兜底 {market} {c}: {q['name']} "
              f"{q['price']} ({q['pct']}%)")
    return got


_MARKET_BY_PREFIXES = {}


def _market_of(prefixes):
    """按前缀组合推断市场（供兜底路由）。"""
    key = tuple(prefixes)
    if key not in _MARKET_BY_PREFIXES:
        for mk, pl in (("US", P_US), ("HK", P_HK), ("A", P_A), ("IDX", P_IDX)):
            if key == tuple(pl):
                _MARKET_BY_PREFIXES[key] = mk
                break
        else:
            _MARKET_BY_PREFIXES[key] = None
    return _MARKET_BY_PREFIXES[key]


def _norm_name(n):
    """名称归一：剥离港股后缀与 ADR 标注，供闸门比较。"""
    n = n or ""
    for s in ("(ADR)", "（ADR）", "-SB", "-SS", "-SW", "-W", "-S", "-B"):
        n = n.replace(s, "")
    return n.strip()


def _gate(us_name, hk_name):
    """名称一致性闸门。返回 (ok, reason)。"""
    if not us_name or us_name == "-":
        return False, "us_name_missing"
    if not hk_name or hk_name == "-":
        return False, "hk_name_missing"
    a, b = _norm_name(us_name), _norm_name(hk_name)
    if not a or not b:
        return False, "name_empty_after_norm"
    if a in b or b in a:
        return True, "ok"
    return False, "name_mismatch"


def _mom(row):
    """提取多周期动量。"""
    m = {}
    for key, fld in MOM_FIELDS:
        m[key] = _f(row.get(fld))
    return m


def _tag(m):
    """近期强弱标签（透明口径，无自由度）：以 5 日 / 20 日双窗口定性。"""
    d5, d20 = m.get("d5"), m.get("d20")
    if d5 is None and d20 is None:
        return "无数据"
    if (d5 or 0) > 0 and (d20 or 0) > 0:
        return "强势"
    if (d5 or 0) > 0:
        return "短期反弹"
    if (d20 or 0) > 0:
        return "中期强·短期回调"
    return "弱势"


def build():
    """返回 payload dict；无有效数据时返回 None（由调用方重试）。"""
    t0 = time.time()

    # ── 0) 语义/预算双闸门（🛡 2026-09-29 断更根治·小九）─────────────────────
    #   背景：本模块原挂 premarket 单档（08:25），实测三连坑 → 结构性断更：
    #     ① 盘前 cron「25 0 * * 1-5」历史实测被 GitHub 静默丢弃/延迟 4h46m（run #1630 铁证）；
    #     ② 早间 dispatch 被并发组挤兑排队 4.5h → 13:00 才执行 → workflow「僵尸盘前档」
    #        重判改跑 intraday/post_close → 本模块全天漏跑（09-29 卡面冻结在 09-28 09:20）；
    #     ③ 自愈侧 all_US_HK_MAP 落入 check_all_data_files 默认 algo_run 通道 → 被
    #        盘后产出窗口闸拦死 → 白天永不自愈。
    #   配套：cloud_fetch_v8 / update_v8 两张 CATEGORY_MAP 已同改挂
    #   "premarket,intraday,post_close" 三档 —— 档位只负责触发，数据语义由本函数闸门保证：
    #     闸1 美东时钟：ET 周一~五 09:30–16:00 常规交易时段内拒绝产出 —— 该时段 push2delay
    #         返回「当日盘中」数据，写卡会把「隔夜」语义漂移成盘中（违反卡片口径铁律）；
    #         其余时段数据恒为「美东最近已收盘交易日」＝隔夜语义安全。
    #     闸2 当日已产出：raw_data/us_hk_map.json 的 update_time 日期 == 今日 → 跳过重抓
    #         （每日仅首轮真实抓取；盘前轮失败/丢失时，盘中/盘后轮自动补位自愈，预算最小化）。
    et_now = datetime.now(ET)
    et_min = et_now.hour * 60 + et_now.minute
    if et_now.weekday() < 5 and 9 * 60 + 30 <= et_min < 16 * 60:
        print("   [us_hk_map] 美东常规交易时段(ET %s) → 拒绝产出（防隔夜语义漂移成盘中）"
              % et_now.strftime("%H:%M"))
        return None
    try:
        _raw_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "raw_data", "us_hk_map.json")
        # 🔴🔴 2026-09-30 一劳永逸（阿狸咪的工程师）：原 `as _f` 把模块级 float 转换函数
        #   `_f()`（L170）遮蔽成文件对象 —— with 块结束后该绑定不恢复，从此 build() 内
        #   所有 `_f(...)` 调用全部 TypeError: '_io.TextIOWrapper' object is not callable
        #   （09-30 08:47 云端 run 日志 L448 栈帧铁证）。这就是 09-29「断更根治」上线后
        #   本模块 09-29/09-30 两天全机器（云端+小九+本机）零成功、卡面冻结 09-28 09:20
        #   的**唯一真凶** —— 档位/闸门/兜底都白修，代码先炸。改名 _prev_fh 根治。
        with open(_raw_p, "r", encoding="utf-8") as _prev_fh:
            _prev = json.load(_prev_fh)
        if str(_prev.get("update_time", ""))[:10] == datetime.now(CST).strftime("%Y-%m-%d"):
            print("   [us_hk_map] 今日已产出（%s）→ 跳过重抓（预算闸门）" % _prev.get("update_time"))
            return None
    except FileNotFoundError:
        pass  # 首次产出，无既有产物 → 继续
    except Exception as _e:
        print("   [us_hk_map] 既有产物读取失败（忽略继续）: %s" % _e)

    # ── 1) 美股候选（ADR + ETF 去重）────────────────────────────────────────
    us_codes = sorted({c for c, _ in ADR_PAIRS} | {c for c, _ in ETF_MAP})
    us_rows = resolve(us_codes, P_US)
    print("   [us_hk_map] 美股候选解析 %d/%d" % (len(us_rows), len(us_codes)))
    # 🛡 2026-09-30 兜底透明化：统计经腾讯+新浪降级的行数，汇总进 gate/note
    n_tx_rows = sum(1 for r in us_rows.values() if r.get("_src") == "tx")

    # ── 2) ADR ↔ 港股 名称闸门 ─────────────────────────────────────────────
    hk_codes = sorted({h for _, h in ADR_PAIRS})
    hk_rows = resolve(hk_codes, P_HK)
    hk_tx = tx_names(["hk" + h for h in hk_codes])

    adr_items, adr_drop = [], []
    for us, hk in ADR_PAIRS:
        urow = us_rows.get(us)
        if not urow:
            adr_drop.append({"us": us, "hk": hk, "why": "us_unresolved"})
            continue
        hn_tx = hk_tx.get("hk" + hk)
        hn_em = (hk_rows.get(hk) or {}).get("f14")
        ok, why = _gate(urow.get("f14"), hn_tx or hn_em)
        if not ok:
            adr_drop.append({"us": us, "hk": hk, "why": why,
                             "us_name": urow.get("f14"), "hk_name": hn_tx or hn_em})
            continue
        m = _mom(urow)
        adr_items.append({
            "us": us,
            "us_name": str(urow.get("f14") or ""),
            "us_secid": "%s.%s" % (urow.get("f13"), us),
            "price": _f(urow.get("f2")),
            "mom": m,
            "tag": _tag(m),
            "kind": "ADR",
            "inverse": False,
            "targets": [{"secid": "116.%s" % hk, "code": hk,
                         "name": hn_tx or hn_em, "market": "HK", "label": "港股"}],
        })

    # ── 3) ETF → A/HK/指数 目标解析 ────────────────────────────────────────
    tgt_codes = {"A": set(), "HK": set(), "IDX": set()}
    for _, tgts in ETF_MAP:
        for mk, code in tgts:
            tgt_codes[mk].add(code)
    tgt_rows = {}
    for mk in ("A", "HK", "IDX"):
        if tgt_codes[mk]:
            tgt_rows[mk] = resolve(sorted(tgt_codes[mk]), PREFIXES[mk])

    etf_items, tgt_missing = [], []
    for us, tgts in ETF_MAP:
        urow = us_rows.get(us)
        if not urow:
            continue
        out_t = []
        for mk, code in tgts:
            trow = (tgt_rows.get(mk) or {}).get(code)
            if not trow:
                tgt_missing.append({"us": us, "market": mk, "code": code})
                continue
            out_t.append({
                "secid": "%s.%s" % (trow.get("f13"), code),
                "code": code,
                "name": str(trow.get("f14") or ""),
                "market": mk,
                "label": MKT_LABEL.get(mk, mk),
            })
        if not out_t:
            continue
        m = _mom(urow)
        etf_items.append({
            "us": us,
            "us_name": str(urow.get("f14") or ""),
            "us_secid": "%s.%s" % (urow.get("f13"), us),
            "price": _f(urow.get("f2")),
            "mom": m,
            "tag": _tag(m),
            "kind": "ETF",
            "inverse": us in INVERSE_US,
            "targets": out_t,
        })

    # ── 4) 隔夜大盘锚（显式 secid，见 US_ANCHORS 注释）─────────────────────
    # 🔴 2026-09-29 一劳永逸（小九）：锚点 secid（100.SPX/NDX/DJIA）**必非空**，空=瞬时故障。
    #   东财 3 次换 host 仍空 ⇒ 腾讯行情源兜底（qt.gtimg.cn 实测 CN 直连可用：
    #   usINX=标普500/.INX、usNDX=纳斯达克100/.NDX、usDJI=道琼斯/.DJI，字段[3]=价 [32]=涨跌%）。
    #   兜底值带 note 标注来源，绝不编造；两源都空才记「该指数点位未取到」。
    def _tx_anchor(tx_code):
        try:
            t = requests.get("https://qt.gtimg.cn/q=" + tx_code,
                             headers=TX_HEADERS, timeout=10).text
            seg = t.split('"')[1] if '"' in t else ""
            p = seg.split("~") if seg else []
            if len(p) > 32 and p[3] not in ("", "0.000"):
                return {"price": float(p[3]), "pct": float(p[32]), "em_name": p[1],
                        "note": "东财锚缺失，腾讯行情源兜底（" + (p[30] or "") + "）"}
        except Exception as _te:
            print(f"   [us_hk_map] ⚠️ 腾讯锚兜底失败 {tx_code}: {type(_te).__name__}: {_te}")
        return None

    anchors = []
    for secid, code, label in US_ANCHORS:
        row = None
        for _att in range(3):  # 锚点必非空 ⇒ 空结果也重试（换 host 由 _em 内部轮转）
            rows = _em([secid])
            row = rows[0] if rows else None
            if row and str(row.get("f14") or "").strip() not in ("", "-"):
                break
            row = None
            if _att < 2:
                time.sleep(0.5)
        if row:
            anchors.append({"code": code, "name": label,
                            "em_name": str(row.get("f14") or ""),
                            "price": _f(row.get("f2")), "pct": _f(row.get("f3"))})
        else:
            _tx = _tx_anchor({"SPX": "usINX", "NDX": "usNDX", "DJIA": "usDJI"}.get(code, ""))
            if _tx:
                anchors.append({"code": code, "name": label,
                                "em_name": _tx["em_name"],
                                "price": _tx["price"], "pct": _tx["pct"],
                                "note": _tx["note"]})
            else:
                anchors.append({"code": code, "name": label, "em_name": None,
                                "price": None, "pct": None,
                                "note": "该指数点位未取到，不编造"})
    ups = sum(1 for a in anchors if (a.get("pct") or 0) > 0)
    downs = sum(1 for a in anchors if (a.get("pct") or 0) < 0)
    if all(a.get("pct") is None for a in anchors):
        bias = "大盘锚缺失"
    elif ups > downs:
        bias = "隔夜美股偏强"
    elif downs > ups:
        bias = "隔夜美股偏弱"
    else:
        bias = "隔夜美股分化"

    # ── 5) 汇总排序（主排序 = 5 日涨幅降序，无自由度）────────────────────────
    items = adr_items + etf_items

    def _sort_key(x):
        d5 = x["mom"].get("d5")
        return (d5 is None, -(d5 if d5 is not None else 0.0))

    items.sort(key=_sort_key)
    strong = [x for x in items if (x["mom"].get("d5") or 0) > 0 and not x.get("inverse")]

    if not items:
        print("   [us_hk_map] ⚠️ 无任何有效标的，返回 None（触发上层重试）")
        return None

    # ── 6) 隔夜交易日（f124 = 该行最后更新时间戳）──────────────────────────
    #   ⚠️ 必须转 **美东** 再取日期：09-19 05:00 CST 对应 09-18 17:00 ET，
    #      用 CST 取日期会把「09-18 收盘」误标成 09-19（多算一天）。
    ts = None
    for r in us_rows.values():
        v = _f(r.get("f124"))
        if v and v > 1e9:
            ts = v if ts is None else max(ts, v)
    if ts:
        dd = datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d")
        dd_src = "em_f124_et"
    else:
        dd = datetime.fromtimestamp(_now().timestamp(), ET).strftime("%Y-%m-%d")
        dd_src = "local_et"

    n_drop = len(adr_drop)
    if n_drop > len(ADR_PAIRS) * 0.5:
        print("   [us_hk_map] ⚠️ 闸门剔除过多 %d/%d，疑似映射表失效或数据源异常"
              % (n_drop, len(ADR_PAIRS)))

    now = _now()
    payload = {
        "data_date": dd,
        "data_date_src": dd_src,
        "data_date_label": "美东最近一个交易日收盘（隔夜）",
        "trade_date_note": "北京时间 08:25 抓取时美股已收盘，本卡为「隔夜」口径，非实时。",
        "bias": bias,
        "us_indices": anchors,
        "items": items,
        "strong_count": len(strong),
        "total_count": len(items),
        "gate": {
            "adr_pairs": len(ADR_PAIRS),
            "adr_ok": len(adr_items),
            "adr_dropped": adr_drop,
            "etf_pairs": len(ETF_MAP),
            "etf_ok": len(etf_items),
            "target_missing": tgt_missing,
            "target_missing_n": len(tgt_missing),
            # 🛡 2026-09-30：东财美股接口不可达时经腾讯+新浪兜底的美股行数（透明审计）
            "us_tx_fallback": n_tx_rows,
            "us_source": ("tencent+sina(东财美股接口不可达兜底)" if n_tx_rows
                          else "eastmoney"),
        },
        "mom_fields": {"d1": "当日", "d3": "3日", "d5": "5日",
                       "d10": "10日", "d20": "20日", "d60": "60日"},
        "sort_rule": "按 5 日涨幅降序（同值按 20 日）",
        "note": ("隔夜口径：美东最近一个交易日收盘价与近期涨跌幅，由东财延迟镜像（push2delay）提供，"
                 "与报价同日同源；映射对已经「美股中文名 × 港股中文名（腾讯独立源）」一致性闸门校验，"
                 "名称不符者整对剔除（剔除数见 gate）。ETF 对位标的为『同类主题』映射，非完全同标的，"
                 "仅供盘前风险偏好参考。")
                + ("🔴 本次美股报价/动量经腾讯行情源+新浪日K兜底产出（东财美股接口不可达，"
                   "09-30 实测口径与东财逐位一致，来源见 gate.us_source）。" if n_tx_rows else ""),
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }
    print("   [us_hk_map] OK items=%d strong=%d adr_drop=%d tgt_missing=%d %.1fs"
          % (len(items), len(strong), n_drop, len(tgt_missing), time.time() - t0))
    return payload


if __name__ == "__main__":
    out = build()
    print(json.dumps(out, ensure_ascii=False, indent=1) if out else "None")
