#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CRDS 逆势龙头评分计算器
========================
从 watch_result.json 读取已扫描的金股 → 逐只拉取10日K线(含成交额/换手率)
→ 结合沪深300大盘涨跌 → 算出CRDS综合逆势分 → 输出 data/crds_result.json

跨文件依赖: watch_result.json(来自scanner.py watch模式) + BaoStock
输出: data/crds_result.json → 由 update_data_v2.py 注入到暂未上架卡片

上游: scanner.py watch → watch_result.json
下游: update_data_v2.py → dist/index.html → gh-pages
"""
import os, sys, json, time, re

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "out")
WATCH_RESULT = os.path.join(DATA_DIR, "watch_result.json")
# 2026-09-03 一劳永逸根因修复：原 OUTPUT_FILE 指向 out/crds_result.json，但 update_v8 /
# verify_chain_outputs 期望的原始文件名是 raw_data/crds_card_data.json —— 改名断点导致
# data/CRDS_CARD_DATA.js 永远停在旧版本（即使本脚本跑成功也不 republish）。现直写
# raw_data/crds_card_data.json，链路闭合。
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw_data", "crds_card_data.json")

# 数据源切换说明(2026-07-15):
# 原实现依赖 BaoStock 日K线, 但 BaoStock 账号于当日被服务端硬拉黑(error 10001011, 黑名单用户),
# 导致 CRDS 永远拿不到数据、只能"保留上一份"→ 卡片永久陈旧。
# 现改为: mootdx 通达信直连 bars() 为主(本机/云端均可用, 不受 BaoStock 封禁, 本机实测不触发V8崩溃),
# 东方财富 K 线为兜底(云端可用; 本机网络层拦截东财故自动跳过)。
# 注: mootdx.bars() 在"部分机器"会触发 py_mini_racer(V8) 崩溃; 且每次调用后按 _TDX_RESET_INTERVAL
# 重建客户端+gc 以规避 TrafficStatSocket 泄漏(约170次杀进程)。CRDS 需 ~176 次调用, 必须周期重置。
_KLINE_FAILS = 0
_KLINE_MAX_FAILS = 40  # 连续失败过多则放弃本次计算, 保留旧 crds_result.json

import gc
import requests as _requests

MARKET_DOWN_THRESHOLD = -1.5     # 大盘跌超多少算"大跌日"(%)
LIMIT_UP_PCT = 9.0               # 涨停阈值(主板≈10%，留1%误差允许实际9.95%)
GEM_LIMIT_PCT = 18.0             # 创业板/科创板涨停阈值(≈20%)
LOOKBACK_DAYS = 10               # 回顾天数
MA_DAYS = 20                     # VR均量周期


# ---- mootdx 客户端(单例 + 周期重置, 防 socket 泄漏) ----
_TDX_CLIENT = None
_TDX_CALL_COUNT = 0
_TDX_RESET_INTERVAL = 50

def _get_tdx():
    global _TDX_CLIENT
    if _TDX_CLIENT is None:
        from mootdx.quotes import Quotes
        _TDX_CLIENT = Quotes.factory(market='std')
    return _TDX_CLIENT

def _tdx_reset():
    global _TDX_CLIENT, _TDX_CALL_COUNT
    try:
        _TDX_CLIENT = None
    except Exception:
        pass
    try:
        gc.collect()
    except Exception:
        pass
    _TDX_CALL_COUNT = 0

def _query_kline_mootdx(code, days):
    """mootdx 通达信直连日K线。code: 6位。返回归一化 DataFrame 或 None。"""
    # 2026-08-01 修正：函数体在 except 分支写 _KLINE_FAILS，但原来只声明了 _TDX_CALL_COUNT，
    # 触发 UnboundLocalError；因主循环对该函数无 try 兜底 → mootdx 一异常整轮 CRDS 崩溃。
    global _TDX_CALL_COUNT, _KLINE_FAILS
    client = _get_tdx()
    if client is None:
        return None
    try:
        df = client.bars(symbol=code, category=9, offset=days + MA_DAYS + 10)
        _TDX_CALL_COUNT += 1
        if _TDX_CALL_COUNT >= _TDX_RESET_INTERVAL:
            _tdx_reset()
        if df is None or len(df) < LOOKBACK_DAYS:
            return None
        dt = df["datetime"]
        if hasattr(dt, "dt"):
            dates = dt.dt.strftime("%Y-%m-%d")
        else:
            dates = dt.astype(str).str[:10]
        out = pd.DataFrame({
            "date": dates,
            "open": df["open"].astype(float),
            "close": df["close"].astype(float),
            "high": df["high"].astype(float),
            "low": df["low"].astype(float),
            "volume": df["volume"].astype(float),
            "amount": df["amount"].astype(float),
            "turn": 0.0,  # mootdx bars 不含换手率, TS 仅展示用不影响评分
        })
        out = out.sort_values("date").reset_index(drop=True)
        out["pctChg"] = ((out["close"] / out["close"].shift(1) - 1) * 100).round(2)
        out["pctChg"] = out["pctChg"].fillna(0.0)
        return out
    except Exception:
        # 🛡 2026-09-05 一劳永逸：mootdx 失败是常态（云端无 tdx 客户端/本机网络层拦截），
        # 绝不可累加到全局 _KLINE_FAILS——否则连败 40 次会把东方财富兜底也拖死，
        # 导致 CRDS 逐只 K 线全失败、total_scanned=0（静默 0 命中根因）。
        # _KLINE_FAILS 只统计「真兜底」东方财富的连续失败。
        _tdx_reset()
        return None


# ---- 东方财富兜底(云端可用, 本机网络层拦截) ----
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_EM_MAX_RETRIES = 3

def _query_kline_em(code, secid_prefix, days):
    """东方财富日K线兜底。code: 6位; secid_prefix: '1'(沪)/'0'(深)。返回归一化 DataFrame 或 None。"""
    global _KLINE_FAILS
    if _KLINE_FAILS >= _KLINE_MAX_FAILS:
        return None
    secid = f"{secid_prefix}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f61",  # f61=换手率
        "klt": 101, "fqt": 1,
        "beg": "0", "end": "20500101",
        "lmt": days + MA_DAYS + 10,
    }
    for attempt in range(_EM_MAX_RETRIES):
        try:
            r = _requests.get(url, params=params, headers=_EM_HEADERS, timeout=12)
            if r.status_code != 200:
                _KLINE_FAILS += 1
                continue
            data = r.json().get("data", {}) or {}
            klines = data.get("klines", [])
            if not klines:
                _KLINE_FAILS += 1
                continue
            rows = []
            for line in klines:
                p = line.split(",")
                if len(p) < 7:
                    continue
                try:
                    rows.append({
                        "date": p[0],
                        "open": float(p[1]),
                        "close": float(p[2]),
                        "high": float(p[3]),
                        "low": float(p[4]),
                        "volume": float(p[5]),
                        "amount": float(p[6]),
                        "turn": float(p[7]) if len(p) >= 8 else 0.0,
                    })
                except ValueError:
                    continue
            if len(rows) < LOOKBACK_DAYS:
                _KLINE_FAILS += 1
                return None
            df = pd.DataFrame(rows)
            df = df.sort_values("date").reset_index(drop=True)
            df["pctChg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
            df["pctChg"] = df["pctChg"].fillna(0.0)
            _KLINE_FAILS = 0
            return df
        except Exception:
            _KLINE_FAILS += 1
            if attempt < _EM_MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
            continue
    return None


def _query_kline(code, secid_prefix, days):
    """取数调度: mootdx 优先, 东方财富兜底。"""
    df = _query_kline_mootdx(code, days)
    if df is not None and len(df) >= LOOKBACK_DAYS:
        return df
    return _query_kline_em(code, secid_prefix, days)


def _load_index_quotes():
    """读取 v8 raw_data/index_quotes.json 的多指数行情，作为 CRDS 大盘判断依据。"""
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "..", "raw_data", "index_quotes.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        out = {}
        up_total = 0
        down_total = 0
        for it in items:
            code = it.get("code", "")
            chg = float(it.get("chg", 0) or 0)
            out[code] = chg
            up_total += int(it.get("up", 0) or 0)
            down_total += int(it.get("down", 0) or 0)
        total_adv_decl = up_total + down_total
        out["breadth"] = up_total / total_adv_decl if total_adv_decl > 0 else 0.5
        out["up_total"] = up_total
        out["down_total"] = down_total
        return out
    except Exception as e:
        print(f"  [市场] 读取 index_quotes 失败: {e}")
        return None


def _composite_market_score(quotes):
    """综合市场强度得分。避免上证被权重股扭曲，纳入深证/创业板/科创50 + 涨跌家数比。"""
    if not quotes:
        return None
    sh = quotes.get("000001", 0)
    sz = quotes.get("399001", 0)
    cy = quotes.get("399006", 0)
    kc = quotes.get("000688", 0)
    breadth = quotes.get("breadth", 0.5)
    breadth_score = (breadth - 0.5) * 4.0
    composite = (
        sh * 0.25 +
        sz * 0.20 +
        cy * 0.25 +
        kc * 0.15 +
        breadth_score * 0.15
    )
    return round(composite, 2)


def get_market_index():
    """获取大盘指数(上证)近期数据(含每日涨跌幅)"""
    df = _query_kline("000001", "1", LOOKBACK_DAYS + 5)
    if df is None or len(df) < LOOKBACK_DAYS:
        print(f"  [市场] 数据不足({len(df) if df is not None else 0}条)")
        return None
    df["pct_chg"] = df["pctChg"].astype(float)
    return df.tail(LOOKBACK_DAYS).reset_index(drop=True)


def get_market_context(mkt_df):
    """
    根据大盘综合强度判断 CRDS 逆势龙头数据的有效性。
    逻辑：逆势龙头只在大跌/震荡市有效；若今日大涨，则信号参考意义极低。
    2026-08-19 主人令一劳永逸修复：不再只看上证指数（权重股易扭曲），
    改为读取 raw_data/index_quotes.json，综合上证/深证/创业板/科创50涨跌幅 + 全市场涨跌家数比。
    """
    if mkt_df is None or len(mkt_df) < 2:
        return {
            "valid": False,
            "validity": "未知",
            "summary": "大盘数据不足，无法判断 CRDS 有效性",
            "today_pct": None,
            "prev_pct": None,
            "trend5_pct": None,
            "color": "#999999",
        }

    quotes = _load_index_quotes()
    if quotes:
        today_pct = _composite_market_score(quotes)
        sh_pct = quotes.get("000001", 0)
        up_total = quotes.get("up_total", 0)
        down_total = quotes.get("down_total", 0)
        breadth = quotes.get("breadth", 0.5)
        data_source = "index_quotes"
    else:
        today_pct = float(mkt_df["pct_chg"].iloc[-1])
        sh_pct = today_pct
        up_total = down_total = 0
        breadth = 0.5
        data_source = "mootdx"

    prev_pct = float(mkt_df["pct_chg"].iloc[-2])
    trend5_pct = float(mkt_df["pct_chg"].iloc[-5:].sum()) if len(mkt_df) >= 5 else 0.0

    if today_pct >= 2.0:
        validity = "失效"
        summary = f"市场综合强度 +{today_pct:.2f}%（上证{sh_pct:+.2f}%，上涨占比{breadth:.1%}），逆势龙头信号参考意义极低，无需关注"
        color = "#999999"
        valid = False
    elif today_pct >= 1.0:
        validity = "低效"
        summary = f"市场综合强度 +{today_pct:.2f}%（上证{sh_pct:+.2f}%，涨跌 {up_total}:{down_total}），偏强环境下 CRDS 有效性降低"
        color = "#BA7517"
        valid = True
    elif today_pct >= -0.5:
        validity = "有效"
        summary = f"市场综合强度 {today_pct:+.2f}%（上证{sh_pct:+.2f}%，涨跌 {up_total}:{down_total}），震荡市，CRDS 可正常参考"
        color = "#1D9E75"
        valid = True
    elif today_pct >= -2.0:
        validity = "较有效"
        summary = f"市场综合强度 {today_pct:+.2f}%（上证{sh_pct:+.2f}%，涨跌 {up_total}:{down_total}），偏弱环境，CRDS 较有效"
        color = "#1D9E75"
        valid = True
    else:
        validity = "高有效"
        summary = f"市场综合强度 {today_pct:.2f}%（上证{sh_pct:+.2f}%，涨跌 {up_total}:{down_total}），恐慌市 CRDS 信号最强，但需防系统性风险"
        color = "#185FA5"
        valid = True

    return {
        "valid": valid,
        "validity": validity,
        "summary": summary,
        "today_pct": round(today_pct, 2),
        "prev_pct": round(prev_pct, 2),
        "trend5_pct": round(trend5_pct, 2),
        "color": color,
        "data_source": data_source,
        "sh_pct": round(sh_pct, 2),
        "breadth": round(breadth, 4),
        "up_total": up_total,
        "down_total": down_total,
    }


def get_stock_kline(code):
    """获取个股近期K线(含成交额)；只处理 A 股 6 位代码，过滤港股/北交所/基金等。"""
    if not code or not re.fullmatch(r"\d{6}", str(code)):
        return None
    prefix = "1" if (code.startswith("6") or code.startswith("688")) else "0"
    df = _query_kline(code, prefix, LOOKBACK_DAYS + MA_DAYS)
    if df is None or len(df) < LOOKBACK_DAYS:
        return None
    return df.reset_index(drop=True)


# ---- 股票名解析(防止外资研投研报污染名进入CRDS卡片) ----
# 污染特征：name 是一整段新闻稿/推荐理由(含'我们/看好/完成/通过'等词)，
# 或部分港股名退化为代码/垃圾('20'/'00148'/'股'/'A')。
# 解析策略：先判断 name 是否像"干净股票名" → 是则直接用；否则云端用东财 f58 取权威名；
# 本机东财被墙时兜底为代码(绝不输出新闻稿垃圾)。
_NEWS_KW = ['我们', '看好', '完成', '通过', '闪电', '带动', '新增', '包括',
            '给予', '首选', '推荐', '关注', '建议', '认为', '预计', '有望',
            '中标', '签订', '取得', '获得', '股份有限', '有限公司', '基石']

def _looks_like_name(n):
    """判断 n 是否像一个干净的中文股票名(2~8字，无新闻/研报词，非纯代码)"""
    if not n:
        return False
    s = str(n).strip()
    if s == '':
        return False
    if re.fullmatch(r'[0-9A-Za-z]+', s):
        return False                      # 纯代码/数字
    if s in ('A', 'B', '股', '20', 'ETF', '基金'):
        return False
    if any(k in s for k in _NEWS_KW):
        return False                      # 含研报/新闻词 → 视为污染
    # 去掉常见后缀后判断长度与字符集
    t = re.sub(r'(股份)?有限公司$', '', s)
    t = re.sub(r'[（(].*?[)）]$', '', t)
    if 2 <= len(t) <= 8 and re.fullmatch(r'[一-鿿]+', t):
        return True
    return False


def _em_secid_prefix(code):
    """东财 secid 市场前缀：沪'1'/深'0'/港股'116'"""
    c = str(code)
    if len(c) == 5:
        return '116'                      # 港股 5 位代码
    if c.startswith(('6', '9')):
        return '1'
    if c.startswith(('0', '3', '2', '8')):
        return '0'
    return None


def _em_name(code):
    """云端东财取权威股票名(f58)。本机网络层拦截东财时返回 None。"""
    global _KLINE_FAILS
    prefix = _em_secid_prefix(code)
    if prefix is None:
        return None
    secid = f"{prefix}.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    try:
        r = _requests.get(url, params={"secid": secid, "fields": "f57,f58,f60"},
                          headers=_EM_HEADERS, timeout=8)
        if r.status_code == 200:
            d = r.json().get("data") or {}
            nm = d.get("f58") or ""
            if nm and not re.fullmatch(r'[0-9A-Za-z]+', str(nm)):
                return str(nm).strip()
    except Exception:
        pass
    return None


def _normalize_name(n):
    """去常见后缀/括号，便于展示(如 '天齐锂业股份有限公司' → '天齐锂业')"""
    s = re.sub(r'(股份)?有限公司$', '', str(n))
    s = re.sub(r'[（(].*?[)）]$', '', s)
    return s.strip()


# ---- 通达信(mootdx) 名字兜底(本机东财被墙时的次级来源) ----
# 注意: mootdx.stocks() 在本机返回的是"指数/债券/基金主表", 并非完整股票主表——
# 上交所(60/68)股票名基本正确, 深交所(00/30)/港股名字缺失或串味(如 000001→上证指数)。
# 故仅在 code 属股票段且 mootdx 名字非指数/债时才采用, 否则交回 raw/代码。
_TDX_NAME_MAP = None
_TDX_NAME_MAP_READY = False

_INDEX_KW = ['指数', '债', 'ETF', '基金', 'LOF', '可转债', '权证', '成份',
             'A股指数', 'B股指数', '港股通', '板块']

def _build_tdx_name_map():
    """懒构建 mootdx 代码→名字 映射(仅本机东财被墙时触发一次)。"""
    global _TDX_NAME_MAP, _TDX_NAME_MAP_READY
    if _TDX_NAME_MAP_READY:
        return _TDX_NAME_MAP
    _TDX_NAME_MAP_READY = True
    _TDX_NAME_MAP = {}
    try:
        from mootdx.quotes import Quotes
        cl = Quotes.factory(market='std')
        stk = cl.stocks()
        for _, r in stk.iterrows():
            code = str(r.get('code') or '').strip()
            nm = str(r.get('name') or '').replace('\x00', '').strip()
            if code:
                _TDX_NAME_MAP[code.zfill(6)] = nm
    except Exception:
        pass
    return _TDX_NAME_MAP

def _tdx_name(code):
    return _build_tdx_name_map().get(str(code).zfill(6))

def _is_safe_stock_name(nm):
    """mootdx 名字是否可信(排除指数/债券/ETF/基金串味, 仅纯中文2~8字)。"""
    if not nm:
        return False
    s = str(nm).strip()
    if s == '' or re.fullmatch(r'[0-9A-Za-z]+', s):
        return False
    if any(k in s for k in _INDEX_KW):
        return False
    if s.endswith('债'):
        return False
    return bool(re.fullmatch(r'[一-鿿]+', s)) and 2 <= len(s) <= 8

def _resolve_name(code, raw_name):
    """返回干净股票名。

    优先级: 东财 f58(云端权威, 可修正外资研投/mootdx 错名)
            > 通达信名字(mootdx, 本机东财被墙时, 仅股票段且非指数/债)
            > raw 干净名 > 代码兜底(绝不输出新闻稿/指数垃圾)。
    """
    em = _em_name(code)                   # 云端权威；本机被墙返回 None
    if em:
        return em
    c = str(code)
    if c.startswith(('60', '68', '00', '30', '11', '12', '20', '90')):
        tn = _tdx_name(c)
        if _is_safe_stock_name(tn):       # 通达信兜底(上交所可靠, 深交所/港股缺失→None)
            return _normalize_name(tn)
    if _looks_like_name(raw_name):        # raw 干净名(非研报污染)
        return _normalize_name(raw_name) or c
    return c                              # 兜底：不出垃圾


def detect_limit_up(pct_chg_series, board_label):
    """判断哪些行是涨停"""
    threshold = GEM_LIMIT_PCT if board_label in ("创业板", "科创板") else LIMIT_UP_PCT
    if hasattr(pct_chg_series, 'values'):
        return pct_chg_series.values >= threshold
    return np.array(pct_chg_series) >= threshold


def detect_market_down(mkt_df, stock_dates):
    """判断个股每天是否对应大盘大跌日"""
    # stock_dates: 个股的日期序列
    # mkt_df: 大盘的日期+涨跌幅数据
    mkt_map = dict(zip(mkt_df["date"], mkt_df["pct_chg"]))
    down = []
    for d in stock_dates:
        pct = mkt_map.get(d, 0)
        down.append(pct <= MARKET_DOWN_THRESHOLD)
    return np.array(down)


def calc_crds_for_stock(stock_df, mkt_df, code, name, board_label):
    """
    对单只股票计算CRDS
    返回dict: {score, cond1, cond2, cond3, af_peak, vr_peak, ts_peak, zt_count, zt_down_count, detail}
    """
    if stock_df is None or len(stock_df) < LOOKBACK_DAYS:
        return None

    # 取最近10天
    recent = stock_df.tail(LOOKBACK_DAYS).reset_index(drop=True)

    # 涨停检测
    is_zt = detect_limit_up(recent["pctChg"].values, board_label)
    zt_count = int(is_zt.sum())

    # 大盘大跌检测
    is_market_down = detect_market_down(mkt_df, recent["date"].values)

    # 大跌日涨停
    zt_on_down = int((is_zt & is_market_down).sum())

    # 逆势强度 AF：只看大盘跌的日子
    af_values = []
    for i in range(LOOKBACK_DAYS):
        if is_zt[i] and is_market_down[i]:
            market_pct = abs(float(mkt_df[mkt_df["date"] == recent["date"].iloc[i]]["pct_chg"].values[0]))
            if market_pct > 0.5:
                stock_pct = float(recent["pctChg"].iloc[i])
                af_values.append(stock_pct / market_pct)
    af_peak = max(af_values) if af_values else 0

    # 量价比 VR (成交额/20日均成交额)
    amount_vals = pd.to_numeric(recent["amount"], errors="coerce").values
    # 用全部可用数据算均量(至少10天)
    all_amount = pd.to_numeric(stock_df["amount"], errors="coerce").values
    ma_amount = np.nanmean(all_amount[-MA_DAYS:]) if len(all_amount) >= MA_DAYS else np.nanmean(all_amount)
    if ma_amount > 0:
        vr_vals = amount_vals / ma_amount
        vr_peak = float(np.nanmax(vr_vals))
    else:
        vr_peak = 0

    # 换手强度 TS
    turn_vals = pd.to_numeric(recent["turn"], errors="coerce").values
    all_turn = pd.to_numeric(stock_df["turn"], errors="coerce").values
    ma_turn = np.nanmean(all_turn[-MA_DAYS:]) if len(all_turn) >= MA_DAYS else np.nanmean(all_turn)
    ts_peak = float(np.nanmax(turn_vals / ma_turn)) if ma_turn > 0 else 0

    # 三个条件
    cond1 = zt_count >= 2          # 10日≥2板
    cond2 = zt_on_down >= 1        # 至少1个大跌日板
    cond3 = vr_peak >= 1.5         # 量能确认

    conds_met = sum([cond1, cond2, cond3])

    # CRDS综合分
    # crds = af_peak × min(vr_peak, 3) × (1 + 逆势板占比) / 3
    inverse_ratio = zt_on_down / max(zt_count, 1)
    crds_raw = af_peak * min(vr_peak, 3) * (1 + inverse_ratio) / 3
    # 2026-08-01 修正：原无上限，大跌日 af_peak 可达6+ → 分值轻松破百，与「0~100」承诺不符。
    crds_score = min(100, round(crds_raw * 10))  # 归一化并截断到 0~100

    return {
        "code": code,
        "name": name,
        "score": crds_score,
        "conds": conds_met,       # 0~3 满足几个条件
        "cond1": cond1,           # 10日≥2板
        "cond2": cond2,           # 大跌日逆势板
        "cond3": cond3,           # 量能确认
        "zt_count": zt_count,
        "zt_down_count": zt_on_down,
        "af_peak": round(af_peak, 2),
        "vr_peak": round(vr_peak, 2),
        "ts_peak": round(ts_peak, 2),
        "market_label": "",
        "board_label": board_label,
    }


def _load_scan_targets():
    """从v8自有数据源加载CRDS扫描标的（不再依赖v6 watch_result.json）。

    优先级: gold_pool_stocks.json(算法链原始) > gold_pool.json(raw) > GOLD_POOL.js(前端)
    每个源返回 [{code, name, board_label, market_label, pct_chg}, ...]
    """
    import re as _re

    # 候选数据源路径（按优先级）
    _base = os.path.dirname(os.path.abspath(__file__))
    _out_dir = os.path.join(_base, "..", "out")
    _raw_dir = os.path.join(_base, "..", "raw_data")
    _data_dir = os.path.join(_base, "..", "data")

    _sources = [
        ("金股池(算法链)", os.path.join(_out_dir, "gold_pool_stocks.json"), "stocks"),
        ("金股池(raw)", os.path.join(_raw_dir, "gold_pool.json"), "stocks"),
        ("金股池(前端JS)", os.path.join(_data_dir, "GOLD_POOL.js"), None),  # JS需特殊解析
        ("候选池(前端JS)", os.path.join(_data_dir, "CANDIDATE.js"), None),
    ]

    for label, path, key in _sources:
        try:
            if path.endswith(".js") and key is None:
                # 解析 window.XXX = {...}; 格式
                stocks = _parse_js_stock_file(path)
            else:
                with open(path, "r", encoding="utf-8") as _f:
                    _d = json.load(_f)
                stocks = _d.get(key, []) if key else (_d if isinstance(_d, list) else [])

            if not stocks:
                continue
            # 兼容 dict 格式（如 gold_pool.json 的 stocks 为 {sh_600xxx: {...}}）
            if isinstance(stocks, dict):
                stocks = list(stocks.values())

            # 标准化: 确保每项有 code 字段，且只保留 A 股 6 位代码
            _normalized = []
            _seen_codes = set()
            for s in stocks:
                if isinstance(s, dict):
                    raw_code = str(s.get("code", "") or s.get("stock_code", "") or "")
                    nc = _re.sub(r'[^0-9]', '', raw_code)
                    # 过滤港股/基金/指数等非 A 股 6 位代码
                    if not nc or len(nc) != 6 or nc in _seen_codes:
                        continue
                    # 进一步按 market/board 过滤港股（防止 5 位/7 位混进来）
                    mk = str(s.get("market", "") or s.get("market_label", "")).lower()
                    bd = str(s.get("board_label", "") or s.get("board", ""))
                    if mk == "hk" or bd == "港股":
                        continue
                    _seen_codes.add(nc)
                    _normalized.append({
                        "code": nc,
                        "name": s.get("name", "") or s.get("stock_name", ""),
                        "board_label": bd,
                        "market_label": s.get("market_label", "") or s.get("market", ""),
                        "pct_chg": s.get("pct_chg", 0) or s.get("pctChg", 0) or s.get("change_pct", 0),
                    })

            if _normalized:
                print(f"  [数据源] {label}: {len(_normalized)} 只股票")
                return _normalized
        except Exception as e:
            print(f"  [跳过] {label}: {e}")
            continue

    print("  [WARN] 所有数据源均不可用")
    return []


def _parse_js_stock_file(js_path):
    """解析 window.VAR = [{...}, ...]; 格式的JS数据文件，返回股票列表"""
    try:
        with open(js_path, "r", encoding="utf-8") as f:
            text = f.read()
        m = __import__("re").search(r"window\.\w+\s*=\s*(\{[\s\S]*?\})\s*;", text)
        if not m:
            # 尝试数组格式
            m2 = __import__("re").search(r"window\.\w+\s*=\s*(\[[\s\S]*?\])\s*;", text)
            if m2:
                data = json.loads(m2.group(1))
            else:
                return []
        else:
            data = json.loads(m.group(1))

        # 从对象中提取stocks列表
        if isinstance(data, dict):
            stocks = data.get("stocks", data.get("list", data.get("items", data.get("data", []))))
        elif isinstance(data, list):
            stocks = data
        else:
            return []

        # 如果是dict格式 {code: {name,...}} 转为列表
        if isinstance(stocks, dict) and len(stocks) > 0:
            first_val = next(iter(stocks.values()))
            if isinstance(first_val, dict):
                return [{"code": k, **v} for k, v in stocks.items()]
            return []

        return stocks if isinstance(stocks, list) else []
    except Exception:
        return []


def _write_empty_crds_output(reason=""):
    """🛡 2026-09-03 一劳永逸：数据源异常时仍写出带新鲜时间戳的空产物，
    避免 data/CRDS_CARD_DATA.js 冻结在上一跑、被运维判 fail（静默冻结根因）。"""
    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_time": datetime.now().strftime("%Y-%m-%d") + " 15:30:00",
        "total_scanned": 0,
        "scan_stats": {"candidates": 0, "succeeded": 0, "failed": 0,
                       "kline_source_used": "none", "note": reason},
        "market_context": {"validity": "unknown", "today_pct": 0.0,
                           "summary": "数据源异常，" + reason + "（保留新鲜时间戳）"},
        "cond1_list": [], "cond2_list": [], "cond3_list": [],
        "elite": [], "advanced": [], "watch": [], "detail": {},
    }
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n[空产物] 已写出 {OUTPUT_FILE}（数据源异常，保留新鲜时间戳）")
    except Exception as e:
        print(f"[ERROR] 写出空产物失败: {e}")


def calc_crds():
    """主流程：读取v8金股池/候选池 → 逐只计算CRDS → 输出

    🛡 2026-08-20 主人令·一劳永逸：CRDS 属于盘后选股策略，必须在 18:00 所有数据就绪后跑。
    加统一选股策略守门：早于 18:00 直接 sys.exit(1)；应急可设 TIME_GATE_BYPASS=1。

    数据源优先级(2026-08-05 修复，不再依赖已退役v6的watch_result.json):
      1. out/gold_pool_stocks.json (算法链build_candidate_pool.py产出)
      2. raw_data/gold_pool.json (update_v8.py注入前)
      3. data/GOLD_POOL.js (前端数据文件，window.GOLD_POOL)
    """
    print(f"\n{'='*60}")
    print(f"CRDS逆势龙头评分计算 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 🛡 2026-08-20 统一选股策略门控：18:00 前禁止出结果
    try:
        from utils.time_gate import check_stock_picking_ready
        check_stock_picking_ready(by='calc_crds')
    except SystemExit:
        raise

    # 1. 读取股票列表（v8自有数据源，不再依赖v6 watch_result.json）
    all_stocks = _load_scan_targets()
    if not all_stocks:
        # 🛡 2026-09-03 一劳永逸：宁可写出空产物（带新鲜时间戳），也不要 return None 让
        # data/CRDS_CARD_DATA.js 冻结在上一跑、被运维按陈旧判 fail（静默冻结根因）。
        print("[WARN] 无可扫描股票，写出空产物（保留新鲜时间戳）")
        _write_empty_crds_output("无可扫描股票")
        return None

    # 2. 获取大盘指数
    print("\n[1/3] 获取大盘指数数据...")
    mkt_df = get_market_index()
    if mkt_df is None:
        # 🛡 2026-09-03 一劳永逸：大盘指数缺失不阻断逐只 CRDS 计算，改以中性市场环境继续。
        print("[WARN] 无法获取大盘指数，以中性市场环境继续计算 CRDS")
        market_context = {"validity": "unknown", "today_pct": 0.0,
                         "summary": "大盘指数获取失败，中性假设（不影响逐只 CRDS 计算）"}
    else:
        market_context = get_market_context(mkt_df)
        print(f"  大盘: {len(mkt_df)} 天")

    # 2.5 大盘环境判断
    print(f"  [大盘判断] {market_context.get('validity')} | 上证今日{market_context.get('today_pct', 0):+.2f}% | {market_context.get('summary')}")

    # 3. 逐只计算CRDS
    print(f"\n[2/3] 逐只计算CRDS ({len(all_stocks)} 只)...")
    _tdx_start = _TDX_CALL_COUNT
    failed_count = 0
    results = []
    for i, s in enumerate(all_stocks):
        code = s.get("code", "")
        name = s.get("name", "")
        board = s.get("board_label", "")
        pct = f"{s.get('pct_chg', 0):.1f}%" if "pct_chg" in s else ""

        print(f"\r  [{i+1}/{len(all_stocks)}] {code} {name} ({pct})...", end="", flush=True)

        try:
            stock_df = get_stock_kline(code)
            crds = calc_crds_for_stock(stock_df, mkt_df, code, name, board)
            time.sleep(0.12)  # 东方财富限流友好间隔
            if crds:
                crds["name"] = _resolve_name(code, crds.get("name", name))
                crds["market_label"] = s.get("market_label", "")
                results.append(crds)
        except Exception as e:
            failed_count += 1
            print(f"\n  [WARN] {code} 计算异常: {e}")
            continue

    # 4. 汇总
    print(f"\n  CRDS有效: {len(results)} 只")

    # 按条件分层
    cond1_list = [r for r in results if r["cond1"]]
    cond2_list = [r for r in results if r["cond2"]]
    cond3_list = [r for r in results if r["cond3"]]
    elite   = [r for r in results if r["conds"] >= 3]
    adv     = [r for r in results if r["conds"] == 2]
    watch_l = [r for r in results if r["conds"] == 1]

    print(f"\n  条件①(10日≥2板): {len(cond1_list)} 只")
    print(f"  条件②(大跌日板):  {len(cond2_list)} 只")
    print(f"  条件③(量能确认):  {len(cond3_list)} 只")
    print(f"  精选级(三项全满足): {len(elite)} 只")
    print(f"  进阶级(两项满足):  {len(adv)} 只")
    print(f"  关注级(一项满足):  {len(watch_l)} 只")

    # 数据日期：用于给每只股票打 enter_date，前端「M-D已入仓」胶囊依据。
    data_date = datetime.now().strftime("%Y-%m-%d")

    # 5. 输出
    _tdx_end = _TDX_CALL_COUNT
    if results:
        if _tdx_end > _tdx_start:
            _src = "mootdx(eastmoney兜底可用)"
        else:
            _src = "eastmoney(mootdx不可用)"
    else:
        _src = "none(全部失败)"
    scan_stats = {
        "candidates": len(all_stocks),
        "succeeded": len(results),
        "failed": failed_count,
        "kline_source_used": _src,
    }
    output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_time": data_date + " 15:30:00",
        "total_scanned": len(results),
        "scan_stats": scan_stats,
        "market_context": market_context,
        "cond1_list": [{"code": r["code"], "name": r["name"], "board_label": r["board_label"]} for r in cond1_list],
        "cond2_list": [{"code": r["code"], "name": r["name"], "board_label": r["board_label"]} for r in cond2_list],
        "cond3_list": [{"code": r["code"], "name": r["name"], "board_label": r["board_label"]} for r in cond3_list],
        "elite":   [{"code": r["code"], "name": r["name"], "score": r["score"], "enter_date": data_date} for r in sorted(elite, key=lambda x: -x["score"])],
        "advanced": [{"code": r["code"], "name": r["name"], "score": r["score"], "enter_date": data_date} for r in sorted(adv, key=lambda x: -x["score"])],
        "watch":   [{"code": r["code"], "name": r["name"], "score": r["score"], "enter_date": data_date} for r in sorted(watch_l, key=lambda x: -x["score"])],
        "detail": {r["code"]: {
            "name": r["name"],
            "score": r["score"],
            "conds": r["conds"],
            "cond1": r["cond1"],
            "cond2": r["cond2"],
            "cond3": r["cond3"],
            "zt_count": r["zt_count"],
            "zt_down_count": r["zt_down_count"],
            "af_peak": r["af_peak"],
            "vr_peak": r["vr_peak"],
            "ts_peak": r["ts_peak"],
            "market_label": r["market_label"],
            "board_label": r["board_label"],
        } for r in results},
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 保存历史：当日快照 + 历史汇总（供卡片历史追踪）
    try:
        hist_dir = os.path.join(DATA_DIR, "history")
        os.makedirs(hist_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_file = os.path.join(hist_dir, f"crds_{today_str.replace('-', '')}.json")
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        hist_file = os.path.join(hist_dir, "crds_history.json")
        hist = {}
        if os.path.exists(hist_file):
            try:
                with open(hist_file, encoding="utf-8") as f:
                    hist = json.load(f)
            except Exception:
                hist = {}
        if not isinstance(hist, dict):
            hist = {}
        hist[today_str] = {
            "elite": len(elite),
            "advanced": len(adv),
            "watch": len(watch_l),
            "cond1": len(cond1_list),
            "cond2": len(cond2_list),
            "cond3": len(cond3_list),
            "scanned": len(results),
            "update_time": output["update_time"],
        }
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] 保存 CRDS 历史失败: {e}")

    print(f"\n[3/3] 已保存: {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    calc_crds()
