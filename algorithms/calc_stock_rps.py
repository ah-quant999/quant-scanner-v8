#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_stock_rps.py — 个股相对强度 RPS + RS + 年线门禁
=====================================================
来源:《RPS+RS+200/250 个股量化筛选》(公众号「小西 西湖区的孩纸」)
目标: 补上 v8 缺失的「自下而上·个股相对强度」半场。

输入:
  - raw_data/candidate.json (universe, 默认复用 ~310 候选池; 可通过 --universe 指定外部列表)
  - 沪深300 日线(000300) 作为 RS 分母

输出:
  - raw_data/stock_rps.json      (结构化数据, 供下游 Python 管线)
  - data/STOCK_RPS.js            (window.STOCK_RPS_DATA, 供前端直接消费)

核心字段:
  rps50/rps120/rps250 : 收益率在 universe 内的百分位 ×100(0~100, 通达信口径)
  rps_max              : max(rps50, rps120, rps250)
  rs                   : 曼斯菲尔德 RS = (C/INDEXC) / MA(C/INDEXC, 50) - 1, 百分化
  above_ma250          : 收盘价 > MA250, A 档硬门禁
  above_ma200          : 收盘价 > MA200
"""
import os, sys, json, time, gc, argparse
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import numpy as np
import requests as _requests

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")
CACHE_DIR = os.path.join(RAW, "_rps_cache")
OUT_JSON = os.path.join(RAW, "stock_rps.json")
OUT_JS = os.path.join(DATA, "STOCK_RPS.js")

os.makedirs(CACHE_DIR, exist_ok=True)

# ---- 参数 ----
DAYS_NEED = 300          # 取 K 线时多要一些, 留足 250 MA + 返回计算
RPS_WINDOWS = [50, 120, 250]
RS_WINDOW = 50
RPS_MIN_DAYS = 120     # 少于该交易日则放弃该票(避免新股/数据缺失导致失真)
INDEX_CODE = "000300"  # 沪深300
INDEX_FALLBACK = "000001"  # 上证指数兜底
INDEX_MARKET = "sh"    # 上海

# ---- mootdx 客户端(单例 + 周期重置, 防 socket 泄漏) ----
_TDX_CLIENT = None
_TDX_CALL_COUNT = 0
_TDX_RESET_INTERVAL = 50


def _get_tdx():
    global _TDX_CLIENT
    if _TDX_CLIENT is None:
        try:
            from mootdx.quotes import Quotes
            _TDX_CLIENT = Quotes.factory(market='std')
        except Exception as e:
            print(f"[mootdx] init failed: {e}")
            _TDX_CLIENT = None
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
    global _TDX_CALL_COUNT
    client = _get_tdx()
    if client is None:
        return None
    try:
        df = client.bars(symbol=code, category=9, offset=days)
        _TDX_CALL_COUNT += 1
        if _TDX_CALL_COUNT >= _TDX_RESET_INTERVAL:
            _tdx_reset()
        if df is None or len(df) < 20:
            return None
        dt = df["datetime"]
        if hasattr(dt, "dt"):
            dates = dt.dt.strftime("%Y-%m-%d")
        else:
            dates = dt.astype(str).str[:10]
        out = pd.DataFrame({
            "date": dates,
            "open": df["open"].astype(float),
            "high": df["high"].astype(float),
            "low": df["low"].astype(float),
            "close": df["close"].astype(float),
            "volume": df["volume"].astype(float),
            "amount": df["amount"].astype(float),
        })
        out = out.sort_values("date").reset_index(drop=True)
        out["pctChg"] = ((out["close"] / out["close"].shift(1) - 1) * 100).round(2)
        out["pctChg"] = out["pctChg"].fillna(0.0)
        return out
    except Exception as e:
        print(f"  [mootdx] {code} error: {e}")
        _tdx_reset()
        return None


# ---- 东方财富兜底(云端可用, 本机网络层可能拦截) ----
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_EM_MAX_RETRIES = 3


def _query_kline_em(code, secid_prefix, days):
    """东方财富日K线兜底。code: 6位; secid_prefix: '1'(沪)/'0'(深)。"""
    secid = f"{secid_prefix}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f61",
        "klt": 101, "fqt": 1,
        "beg": "0", "end": "20500101",
        "lmt": days,
    }
    for attempt in range(_EM_MAX_RETRIES):
        try:
            r = _requests.get(url, params=params, headers=_EM_HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json().get("data", {}) or {}
            klines = data.get("klines", [])
            if not klines:
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
            if len(rows) < 20:
                return None
            df = pd.DataFrame(rows)
            df = df.sort_values("date").reset_index(drop=True)
            df["pctChg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
            df["pctChg"] = df["pctChg"].fillna(0.0)
            return df
        except Exception:
            if attempt < _EM_MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
            continue
    return None


# ---- 2026-08-22 主人令一劳永逸：baostock 第三兜底（mootdx/东财均不可达时，A股）----
_BS_LOGGED_IN = False
def _query_kline_bs(code, days):
    """baostock 日K兜底（仅 A股，6 位数字代码）。返回 DataFrame 或 None。"""
    global _BS_LOGGED_IN
    if not (isinstance(code, str) and code.isdigit() and len(code) == 6):
        return None
    try:
        import baostock as bs
        if not _BS_LOGGED_IN:
            lg = bs.login()
            if lg.error_code != '0':
                return None
            _BS_LOGGED_IN = True
        prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
        start = (datetime.now() - timedelta(days=days * 2 + 20)).strftime('%Y-%m-%d')
        end = datetime.now().strftime('%Y-%m-%d')
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}", "date,code,open,high,low,close,volume,amount",
            start_date=start, end_date=end, frequency='d', adjustflag='2')
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        if len(rows) < 20:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        for c in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df = df.sort_values("date").reset_index(drop=True)
        df["pctChg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
        df["pctChg"] = df["pctChg"].fillna(0.0)
        return df
    except Exception:
        return None


def _query_kline(code, market, days):
    """取数调度: mootdx 优先 → 东财兜底 → baostock 兜底（2026-08-22 主人令防数据源全不可达）。"""
    df = _query_kline_mootdx(code, days)
    if df is not None and len(df) >= 60:
        return df
    # 东财
    prefix = "1" if market == "sh" else "0"
    df = _query_kline_em(code, prefix, days)
    if df is not None and len(df) >= 60:
        return df
    # baostock 第三兜底（A股）
    return _query_kline_bs(code, days)


# ---- 缓存 ----
def _cache_path(code):
    return os.path.join(CACHE_DIR, f"{code}.json")


def _load_cache(code, max_age_days=1):
    path = _cache_path(code)
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if (time.time() - mtime) > max_age_days * 86400:
            return None
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        if not rows or len(rows) < 20:
            return None
        return pd.DataFrame(rows)
    except Exception:
        return None


def _save_cache(code, df):
    try:
        df.to_json(_cache_path(code), orient="records", force_ascii=False)
    except Exception:
        pass


# ---- 计算 ----
def _market_prefix(market):
    m = (market or "").lower()
    if m == "sh":
        return "sh"
    if m == "sz":
        return "sz"
    if m in ("hk", "hongkong"):
        return "hk"
    return "sz"  # 默认深


def _norm_code(code):
    return re.sub(r"\D", "", str(code or ""))[-6:] if code else ""


import re


def load_universe(path):
    """读取 universe 文件。支持 candidate.json 格式或简单列表。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw_stocks = []
    if isinstance(data, dict) and "stocks" in data:
        v = data["stocks"]
        if isinstance(v, dict):
            raw_stocks = list(v.values())
        else:
            raw_stocks = v
    elif isinstance(data, list):
        raw_stocks = data
    else:
        raw_stocks = []
    out = []
    seen = set()
    for s in raw_stocks:
        if not isinstance(s, dict):
            continue
        code = _norm_code(s.get("code", ""))
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({
            "code": code,
            "name": s.get("name", code),
            "market": _market_prefix(s.get("market")),
            "board": s.get("board_label") or s.get("board", ""),
            "source": s.get("sources", []),
        })
    return out


def fetch_stock_df(code, market, days=DAYS_NEED):
    """获取单票 K 线, 优先读缓存。"""
    df = _load_cache(code)
    if df is not None and len(df) >= days * 0.8:
        return df
    df = _query_kline(code, market, days)
    if df is not None and len(df) >= 20:
        _save_cache(code, df)
    return df


def fetch_index_df(days=DAYS_NEED):
    """获取沪深300 K 线; 若取不到则用上证指数兜底。返回 (df, code)。"""
    for code in (INDEX_CODE, INDEX_FALLBACK):
        df = _load_cache(code)
        if df is not None and len(df) >= days * 0.8:
            return df, code
        df = _query_kline(code, INDEX_MARKET, days)
        if df is not None and len(df) >= RS_WINDOW + 1:
            _save_cache(code, df)
            return df, code
    return None, INDEX_CODE


def compute_metrics(stock_df, index_df):
    """给定个股和指数 K 线, 计算 RPS/RS/年线指标。返回 dict 或 None。"""
    if stock_df is None or len(stock_df) < RPS_MIN_DAYS:
        return None
    stock_df = stock_df.copy()
    stock_df["ma50"] = stock_df["close"].rolling(50).mean()
    stock_df["ma120"] = stock_df["close"].rolling(120).mean()
    stock_df["ma200"] = stock_df["close"].rolling(200).mean()
    stock_df["ma250"] = stock_df["close"].rolling(250).mean()

    last = stock_df.iloc[-1]
    close = float(last["close"])
    ret = {}
    for w in RPS_WINDOWS:
        if len(stock_df) >= w + 1:
            past = float(stock_df.iloc[-(w + 1)]["close"])
            ret[w] = (close / past - 1) * 100 if past > 0 else None
        else:
            ret[w] = None

    above_ma250 = close > float(last["ma250"]) if not pd.isna(last["ma250"]) else False
    above_ma200 = close > float(last["ma200"]) if not pd.isna(last["ma200"]) else False

    # RS (Mansfield): ratio = C/INDEXC, rs = ratio / MA(ratio, 50) - 1, 百分化
    rs_val = None
    if index_df is not None and len(index_df) >= RS_WINDOW + 1:
        # 按日期对齐
        merged = pd.merge(
            stock_df[["date", "close"]].rename(columns={"close": "s_close"}),
            index_df[["date", "close"]].rename(columns={"close": "i_close"}),
            on="date",
            how="inner",
        )
        if len(merged) >= RS_WINDOW + 1:
            merged["ratio"] = merged["s_close"] / merged["i_close"]
            merged["ratio_ma50"] = merged["ratio"].rolling(RS_WINDOW).mean()
            last_row = merged.iloc[-1]
            if not pd.isna(last_row["ratio_ma50"]) and last_row["ratio_ma50"] > 0:
                rs_val = (float(last_row["ratio"]) / float(last_row["ratio_ma50"]) - 1) * 100

    return {
        "close": round(close, 2),
        "ret50": ret.get(50),
        "ret120": ret.get(120),
        "ret250": ret.get(250),
        "above_ma250": above_ma250,
        "above_ma200": above_ma200,
        "ma50": round(float(last["ma50"]), 2) if not pd.isna(last["ma50"]) else None,
        "ma250": round(float(last["ma250"]), 2) if not pd.isna(last["ma250"]) else None,
        "rs": round(rs_val, 2) if rs_val is not None else None,
    }


def compute_rps_percentiles(metrics_list):
    """在 universe 内对每个窗口做百分位, 得到 rps50/120/250。"""
    windows = RPS_WINDOWS
    for w in windows:
        vals = [m.get(f"ret{w}") for m in metrics_list if m.get(f"ret{w}") is not None]
        if not vals:
            continue
        arr = np.array(vals)
        for m in metrics_list:
            key = f"ret{w}"
            v = m.get(key)
            if v is None:
                m[f"rps{w}"] = None
                continue
            # 百分位: 比 v 小的比例; scipy 不在时手写
            pct = np.mean(arr <= v) * 100
            m[f"rps{w}"] = round(pct, 1)
    return metrics_list


def build_output(stocks, metrics_map):
    records = []
    for s in stocks:
        code = s["code"]
        m = metrics_map.get(code)
        if not m:
            continue
        rps_list = [m.get(f"rps{w}") for w in RPS_WINDOWS if m.get(f"rps{w}") is not None]
        rps_max = max(rps_list) if rps_list else None
        records.append({
            "code": code,
            "name": s["name"],
            "market": s["market"],
            "board": s["board"],
            "close": m["close"],
            "ret50": m["ret50"],
            "ret120": m["ret120"],
            "ret250": m["ret250"],
            "rps50": m.get("rps50"),
            "rps120": m.get("rps120"),
            "rps250": m.get("rps250"),
            "rps_max": rps_max,
            "rs": m.get("rs"),
            "above_ma250": m["above_ma250"],
            "above_ma200": m["above_ma200"],
            "ma50": m.get("ma50"),
            "ma250": m.get("ma250"),
            "calc_date": datetime.now().strftime("%Y-%m-%d"),
        })
    # 排序: rps_max desc, then rs desc
    records.sort(key=lambda x: (-(x.get("rps_max") or 0), -(x.get("rs") or 0)))
    return records


def classify_tier(r):
    """A/B/C 分层。A 档硬门禁: above_ma250 + rs>0 + rps_max>=90。"""
    rps_max = r.get("rps_max") or 0
    rs = r.get("rs") or 0
    above250 = r.get("above_ma250") or False
    if above250 and rs > 0 and rps_max >= 90:
        return "A"
    if rps_max >= 80:
        return "B"
    if rps_max >= 60:
        return "C"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default=os.path.join(RAW, "candidate.json"),
                        help="universe JSON 路径")
    parser.add_argument("--max-age", type=int, default=1,
                        help="缓存最大天数")
    parser.add_argument("--limit", type=int, default=0,
                        help="仅处理前 N 只(调试用), 0=全部")
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始计算个股 RPS/RS/年线")
    print(f"universe: {args.universe}")
    if not os.path.exists(args.universe):
        print(f"[error] universe 文件不存在: {args.universe}")
        sys.exit(1)

    stocks = load_universe(args.universe)
    if args.limit > 0:
        stocks = stocks[:args.limit]
    print(f"universe 共 {len(stocks)} 只")

    print("先拉取沪深300指数( fallback 上证指数)...")
    index_df, actual_index_code = fetch_index_df()
    if index_df is None or len(index_df) < RS_WINDOW + 1:
        print("[warn] 指数数据不足, RS 将为空")
        index_df = None
    else:
        print(f"  使用指数: {actual_index_code} ({'沪深300' if actual_index_code == INDEX_CODE else '上证指数'}), {len(index_df)} 条")

    metrics_map = {}
    ok = fail = 0
    for i, s in enumerate(stocks, 1):
        code = s["code"]
        name = s["name"]
        print(f"[{i}/{len(stocks)}] {code} {name} ", end="", flush=True)
        df = fetch_stock_df(code, s["market"])
        m = compute_metrics(df, index_df)
        if m:
            metrics_map[code] = m
            ok += 1
            print(f"✓ close={m['close']} ret50={m['ret50']:.1f}%")
        else:
            fail += 1
            print(f"✗ 数据不足({len(df) if df is not None else 0}条)")

    print(f"\n取数完成: 成功 {ok}, 失败 {fail}")
    if not metrics_map:
        print("[error] 无任何有效个股数据, 退出")
        sys.exit(1)

    # 计算 RPS 百分位
    metrics_list = list(metrics_map.values())
    compute_rps_percentiles(metrics_list)

    records = build_output(stocks, metrics_map)

    # 加 tier
    for r in records:
        r["tier"] = classify_tier(r)

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe_count": len(stocks),
        "valid_count": len(records),
        "index_code": actual_index_code,
        "index_name": "沪深300" if actual_index_code == INDEX_CODE else "上证指数(兜底)",
        "records": records,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"写入 {OUT_JSON} ({len(records)} 条)")

    # 生成前端 JS
    js_text = "window.STOCK_RPS_DATA = " + json.dumps(out, ensure_ascii=False, indent=2) + ";\n"
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js_text)
    print(f"写入 {OUT_JS}")

    # 打印头部样本
    print("\nTop 10 (rps_max 排序):")
    for r in records[:10]:
        print(f"  {r['code']} {r['name']:6s} tier={r['tier']} rps_max={r.get('rps_max')} rs={r.get('rs')} above250={r['above_ma250']}")


if __name__ == "__main__":
    main()
