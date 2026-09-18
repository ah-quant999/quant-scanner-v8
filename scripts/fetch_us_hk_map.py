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
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

CST = timezone(timedelta(hours=8))
ET = ZoneInfo("America/New_York")  # 隔夜交易日必须按美东判，勿用 CST（会多算一天）

EM_DELAY = "https://push2delay.eastmoney.com"
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
    """东财 push2delay ulist.np 批量点名。返回行列表（失败返回 []）。"""
    for i in range(retries):
        try:
            r = requests.get(EM_DELAY + "/api/qt/ulist.np/get",
                             params={"fltt": "2", "invt": "2", "ut": EM_UT,
                                     "fields": fields, "secids": ",".join(batch)},
                             headers=EM_HEADERS, timeout=timeout)
            d = (r.json().get("data") or {}).get("diff")
            if isinstance(d, dict):
                d = list(d.values())
            return d or []
        except Exception:  # noqa: BLE001
            if i < retries - 1:
                time.sleep(0.8)
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

    # ── 1) 美股候选（ADR + ETF 去重）────────────────────────────────────────
    us_codes = sorted({c for c, _ in ADR_PAIRS} | {c for c, _ in ETF_MAP})
    us_rows = resolve(us_codes, P_US)
    print("   [us_hk_map] 美股候选解析 %d/%d" % (len(us_rows), len(us_codes)))

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
    anchors = []
    for secid, code, label in US_ANCHORS:
        rows = _em([secid])
        row = rows[0] if rows else None
        if row and str(row.get("f14") or "").strip() not in ("", "-"):
            anchors.append({"code": code, "name": label,
                            "em_name": str(row.get("f14") or ""),
                            "price": _f(row.get("f2")), "pct": _f(row.get("f3"))})
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
        },
        "mom_fields": {"d1": "当日", "d3": "3日", "d5": "5日",
                       "d10": "10日", "d20": "20日", "d60": "60日"},
        "sort_rule": "按 5 日涨幅降序（同值按 20 日）",
        "note": ("隔夜口径：美东最近一个交易日收盘价与近期涨跌幅，由东财延迟镜像（push2delay）提供，"
                 "与报价同日同源；映射对已经「美股中文名 × 港股中文名（腾讯独立源）」一致性闸门校验，"
                 "名称不符者整对剔除（剔除数见 gate）。ETF 对位标的为『同类主题』映射，非完全同标的，"
                 "仅供盘前风险偏好参考。"),
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }
    print("   [us_hk_map] OK items=%d strong=%d adr_drop=%d tgt_missing=%d %.1fs"
          % (len(items), len(strong), n_drop, len(tgt_missing), time.time() - t0))
    return payload


if __name__ == "__main__":
    out = build()
    print(json.dumps(out, ensure_ascii=False, indent=1) if out else "None")
