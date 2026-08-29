#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_avg_price.py — 平均股价（通达信 880003）真实指数 fetcher  ★ 2026-08-30 方案 A 落地

数据源（按优先级）：
  1) 东方财富 push2his  —— secid=88.0003（通达信「平均股价」指数，东财原生支持）
  2) akshare index_zh_a_hist(symbol='880003')  —— 备源
  3) akshare stock_zh_a_daily(symbol='sh880003') —— 备源二

口径：取 880003 真实日 K 收盘价序列（最多 120 交易日），
      计算 MA20 / MA60、相对均线偏离、单日涨跌，并输出「买/加」「卖/减」信号判定。

⚠️ 与旧版区别：
  - 旧版 cloud_fetch_v8.f_avg_price() 用全 A spot 等权收盘价 ≈ 伪「平均股价」，
    且历史累积损坏（只有 2 天且值相同）→ MA 信号全是假的。
  - 本脚本直接抓真实指数 880003，MA 信号有真实 120 日历史支撑。
  - 若三源全部失败 → 输出 available=false 占位，前端据此【不显示任何买卖信号】
    （主人令：做不到的就不能展示，绝不用假数据填充）。

产出：raw_data/avg_price_data.json → update_v8.py 映射为 data/AVG_PRICE_DATA.js
频度：盘后 1 次（由 .github/workflows/v8_cn_fetch_cloud.yml 调度）
"""
import os, json, sys, time
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")
HISTORY_DAYS = 120  # 取足 120 交易日，保证 MA60 有缓冲

# 通达信 880003 在东财 push2his 的 secid（88=通达信风格指数，0003=编号）
SEC_ID = "88.0003"
EM_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _http_get(url, params=None, timeout=15):
    try:
        import requests
        r = requests.get(url, params=params, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[warn] http_get failed: {e}", file=sys.stderr)
        return None


def _fetch_eastmoney():
    """东财 push2his 取 880003 日 K（主源）。返回 [(date, close), ...] 或 None。"""
    params = {
        "secid": SEC_ID,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",   # 日 K
        "fqt": "1",     # 前复权
        "beg": "0",
        "end": "20500101",
        "lmt": str(HISTORY_DAYS + 10),
        "ut": "fa5fd1943c7b386f172d6893dbfba1a9",
        "_": str(int(time.time() * 1000)),
    }
    data = _http_get(EM_URL, params=params)
    if not data or not data.get("data") or not data["data"].get("klines"):
        return None
    out = []
    for ln in data["data"]["klines"]:
        parts = ln.split(",")
        if len(parts) >= 3:
            try:
                out.append((parts[0], float(parts[2])))  # date, close
            except ValueError:
                continue
    return out if len(out) >= 2 else None


def _fetch_akshare():
    """akshare 备源。返回 [(date, close), ...] 或 None。"""
    try:
        import akshare as ak
        for sym in ("880003",):
            try:
                df = ak.index_zh_a_hist(symbol=sym, period="daily",
                                        start_date="20250101", end_date="20500101")
                if df is not None and len(df) >= 2:
                    recs = []
                    for _, row in df.iterrows():
                        d = str(row.get("日期", ""))
                        c = row.get("收盘")
                        if d and c is not None:
                            recs.append((d, float(c)))
                    if len(recs) >= 2:
                        return recs
            except Exception as e:
                print(f"[warn] akshare index_zh_a_hist({sym}) failed: {e}", file=sys.stderr)
        # 备源二：新浪日线
        try:
            df = ak.stock_zh_a_daily(symbol="sh880003", adjust="")
            if df is not None and len(df) >= 2:
                recs = []
                for _, row in df.iterrows():
                    d = str(row.get("date", ""))
                    c = row.get("close")
                    if d and c is not None:
                        recs.append((d, float(c)))
                if len(recs) >= 2:
                    return recs
        except Exception as e:
            print(f"[warn] akshare stock_zh_a_daily(sh880003) failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] akshare import failed: {e}", file=sys.stderr)
    return None


def _ma(closes, n):
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 4)


def build_payload(series):
    """series: [(date, close), ...] 升序。返回 dict。"""
    series = series[-HISTORY_DAYS:]  # 裁剪到窗口
    dates = [s[0] for s in series]
    closes = [s[1] for s in series]
    cur = closes[-1]
    prev = closes[-2] if len(closes) > 1 else None
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    chg = round((cur / prev - 1) * 100, 3) if prev else 0.0
    pos20 = round((cur / ma20 - 1) * 100, 3) if ma20 else None
    pos60 = round((cur / ma60 - 1) * 100, 3) if ma60 else None

    # 历史（用于前端连跌后首阳等形态判断）
    hist = []
    for i, (d, c) in enumerate(series):
        pc = series[i - 1][1] if i > 0 else None
        hist.append({
            "date": d,
            "avg_price": c,
            "avg_change_pct": round((c / pc - 1) * 100, 3) if pc else 0.0,
        })

    return {
        "available": True,
        "source": "通达信880003(东财push2his)",
        "index_name": "平均股价(通达信880003)",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "date": dates[-1],
        "avg_price": cur,
        "prev_avg_price": prev,
        "avg_change_pct": chg,
        "count": None,  # 880003 是指数，不是「N 只股票」
        "ma20": ma20,
        "ma60": ma60,
        "position_vs_ma20": pos20,
        "position_vs_ma60": pos60,
        "history": hist,
        "history_days": len(hist),
    }


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, "avg_price_data.json")

    series = _fetch_eastmoney() or _fetch_akshare()
    if not series:
        placeholder = {
            "available": False,
            "source": "通达信880003(东财push2his)",
            "index_name": "平均股价(通达信880003)",
            "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "三源(东财push2his/akshare)均未能取数，待云端重试",
            "avg_price": None, "ma20": None, "ma60": None,
            "position_vs_ma20": None, "position_vs_ma60": None,
            "history": [], "history_days": 0,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(placeholder, f, ensure_ascii=False, indent=2)
        print("[warn] avg_price fetch failed → placeholder(available=false) written", file=sys.stderr)
        return 1

    payload = build_payload(series)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[ok] avg_price 880003: date={payload['date']} price={payload['avg_price']} "
          f"ma20={payload['ma20']} ma60={payload['ma60']} history_days={payload['history_days']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
