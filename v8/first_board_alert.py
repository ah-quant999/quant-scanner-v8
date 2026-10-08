#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连板梯队前哨（v8 · 一进二前哨 + 二进三观察 算法模块）

目的：把连板天梯的两端一次性捞出来——
- ① 首板倍量（一进二前哨）：在「首板」（连板数==1）当天，用**倍量（成交量/前20日均量）**
   筛出可能走多板拉升、值得次日「一进二」介入的候选。
- ② 二进三临界观察：连板数==2 的非一字板全量展示（量比/换手给足），供人工判断接力质量。
   定位=临界观察·非推荐（回测 2026-10 实测 4831 只·2025-08~2026-09：二进三晋级率≈27%（489/1822），T+1 开盘买入均值 -0.10%（t=-0.69）、仅可成交子集 -1.9%（t=-11.4）——「三板最难」难在买入价格而非晋级本身；首板倍量≥3 晋级率 14.1% vs 全体首板 14.3%——倍量无晋级增量，本卡=观察哨非买点）。

设计要点：
- 量比 = 当日成交量 / 前20个交易日成交量均值（不含当日）。
- 一字板（开=高=低=收）直接剔除：买不进，无介入价值。
- ST / *ST 剔除。
- 仅依赖新浪日K（与 v8 全站 K线源=新浪 一致），无额外依赖。

生产接入：cloud_fetch_v8.f_first_board_alert 经 importlib 调用本模块 build_alerts()，
宇宙由 _get_zt_pool()（akshare 涨停池）提供；meta 携带 名称/行业/换手率/连板数(lbc)。
lbc 缺省按 1 处理（向后兼容旧调用）。
"""
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")
VOL_RATIO_MIN = 3.0      # 倍量阈值（首板层）
CAP = 25                  # 首板层输出上限
CAP_L2 = 15               # 二进三观察层输出上限
KLINES = 30               # 取多少根日K算均量


def _now_cst():
    return datetime.now(CST)


def _sina_sym(code: str) -> str:
    code = str(code).strip()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code[0] == "6":
        return "sh" + code
    if code[0] in ("0", "3"):
        return "sz" + code
    if code[0] in ("8", "4"):
        return "bj" + code
    return "sh" + code


def _sina_kline(code: str, n: int = KLINES):
    sym = _sina_sym(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService"
           f".getKLineData?symbol={sym}&scale=240&ma=no&datalen={n}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
    })
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return json.loads(raw)


def _parse_bars(k):
    """新浪日K → [(day, open, high, low, close, volume)]"""
    bars = []
    for d in k:
        o = float(d.get("open") or 0)
        h = float(d.get("high") or 0)
        l = float(d.get("low") or 0)
        c = float(d.get("close") or 0)
        v = int(float(d.get("volume") or 0))
        bars.append((d.get("day"), o, h, l, c, v))
    return bars


def _is_yiziban(o, h, l, c):
    """一字板：开=高=低=收（全天无波动）"""
    return abs(o - h) < 1e-6 and abs(o - l) < 1e-6 and abs(o - c) < 1e-6


def _fmt_turnover(v):
    """换手率统一两位小数（akshare 原始值常带长尾浮点）"""
    try:
        f = float(v)
        return round(f, 2) if f == f else None  # NaN → None
    except Exception:
        return None


def vol_ratio_of(code: str, kline_cache: dict = None):
    """返回 (vol_ratio, bars[-1]) 或 (None, None)。kline_cache 可选，避免同股重复拉取。"""
    cache = kline_cache if kline_cache is not None else {}
    try:
        if code in cache:
            bars = cache[code]
        else:
            bars = _parse_bars(_sina_kline(code, KLINES))
            cache[code] = bars
    except Exception:
        return None, None
    if len(bars) < 21:
        return None, (bars[-1] if bars else None)
    today = bars[-1]
    prev20 = [b[5] for b in bars[-21:-1]]  # 不含当日
    avg = sum(prev20) / len(prev20)
    if avg <= 0:
        return None, today
    return today[5] / avg, today


def build_alerts(codes, meta=None, vol_ratio_min=VOL_RATIO_MIN, cap=CAP, as_of=None):
    """核心：对给定涨停池宇宙 codes，产出 ①首板倍量前哨 ②二进三临界观察。

    meta: 可选 {code: {"name","industry","turnover","lbc"}}（来自涨停池；lbc 缺省=1）。
    返回 dict（与 v8 其他 window.X 结构对齐；ladder2 为新增键，向后兼容）。
    """
    meta = meta or {}
    alerts = []
    ladder2 = []
    kcache = {}
    for code in codes:
        code = str(code).strip()
        m = meta.get(code) or meta.get(code.zfill(6)) or {}
        name = m.get("name") or code
        # ST 剔除
        if name.startswith(("ST", "*ST", "st", "*st")):
            continue
        try:
            lbc = int(m.get("lbc") or 1)
        except Exception:
            lbc = 1
        vr, today = vol_ratio_of(code, kcache)
        if vr is None or today is None:
            continue
        day, o, h, l, c, v = today
        # 一字板剔除（买不进）
        if _is_yiziban(o, h, l, c):
            continue
        if lbc == 2:
            # ② 二进三临界观察：全量展示（不做量比门槛），按量比降序
            ladder2.append({
                "code": code,
                "name": name,
                "board_date": day,
                "board_close": round(c, 2),
                "vol_ratio": round(vr, 2),
                "turnover": _fmt_turnover(m.get("turnover")),
                "industry": m.get("industry"),
                "note": "二进三临界观察·非推荐",
            })
        else:
            # ① 首板倍量：量比门槛
            if vr < vol_ratio_min:
                continue
            alerts.append({
                "code": code,
                "name": name,
                "board_date": day,
                "board_close": round(c, 2),
                "vol_ratio": round(vr, 2),
                "turnover": _fmt_turnover(m.get("turnover")),
                "industry": m.get("industry"),
                "note": "首板倍量，关注次日一进二",
            })
    alerts.sort(key=lambda x: x["vol_ratio"], reverse=True)
    ladder2.sort(key=lambda x: x["vol_ratio"], reverse=True)
    return {
        "update_time": (as_of or _now_cst()).strftime("%Y-%m-%d %H:%M:%S"),
        "params": {
            "vol_ratio_min": vol_ratio_min,
            "cap": cap,
            "cap_l2": CAP_L2,
            "exclude_yiziban": True,
            "exclude_st": True,
            "source": "sina_daily_k",
        },
        "alerts": alerts[:cap],
        "ladder2": ladder2[:CAP_L2],
    }


if __name__ == "__main__":
    import sys
    codes = sys.argv[1:] or ["000504", "600825", "600519", "000001"]
    out = build_alerts(codes)
    print(json.dumps(out, ensure_ascii=False, indent=2))
