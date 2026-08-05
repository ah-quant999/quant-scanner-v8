#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_source_gtimg — v8 云端数据源模块（腾讯 GTimg 前复权日K + 新浪活跃股排行）

用途：scanner.py 在 CLOUD_RUNNER=true 时经 `_gtimg()` 调用本模块，避免云端
mootdx/东财不可达。接口与 scanner 期望完全一致：
  fetch_a_daily_gtimg(code, market='sh'|'sz', bars=250)
      -> pandas DataFrame(date/open/close/high/low/volume/pct_chg) 或 None
  fetch_volume_top_stocks_gtimg(top_cy, top_kc, top_zb, top_hk)
      -> [(code, name, market, board_label, 0, turnover_rate, 0, fund_type), ...]
      （新浪 getHQNodeData 按成交额排序，分流 创业板/科创板/主板；港股暂不支持）

数据来源：
  - 日K：web.ifzq.gtimg.cn（腾讯行情，前复权 qfqday）
  - 活跃股：vip.stock.finance.sina.com.cn（新浪沪深A排行 sort=amount）
两者均为 HTTP JSON，无需本地库。
"""
import json
import time
import urllib.request

import pandas as pd

KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
RANK_API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _http(url, timeout=20, retries=3, referer="https://finance.sina.com.cn/"):
    """GET 并返回文本（带重试）。"""
    last = None
    for i in range(retries):
        try:
            headers = dict(_UA)
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    raise last


def fetch_a_daily_gtimg(code, market="sh", bars=250):
    """腾讯前复权日K → DataFrame(date/open/close/high/low/volume/pct_chg)。

    与 scanner.fetch_a_daily 的 mootdx 分支列结构一致；非未来函数（仅截至当日）。
    """
    sym = f"{market}{code}"
    raw = _http(f"{KLINE_API}?param={sym},day,,,{bars},qfq", referer="https://gu.qq.com/")
    d = json.loads(raw)
    node = (d.get("data") or {}).get(sym) or {}
    k = node.get("qfqday") or node.get("day") or []
    rows = []
    for it in k:
        if len(it) < 6:
            continue
        try:
            rows.append({
                "date": str(it[0]),
                "open": float(it[1]),
                "close": float(it[2]),
                "high": float(it[3]),
                "low": float(it[4]),
                "volume": float(it[5]),
            })
        except Exception:  # noqa: BLE001
            continue
    if len(rows) < 60:
        return None
    df = pd.DataFrame(rows)
    df["pct_chg"] = 0.0
    if len(df) > 1:
        df["pct_chg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
    return df


def _sina_rank(num=300):
    """新浪沪深A按成交额排序，最多翻 3 页×200。返回 list[dict]。"""
    arr = []
    page = 1
    while len(arr) < num and page <= 3:
        url = f"{RANK_API}?page={page}&num=200&sort=amount&asc=0&node=hs_a"
        try:
            raw = _http(url)
            batch = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            print(f"  [GTimg] 新浪排行第{page}页失败: {e}")
            break
        if not batch:
            break
        arr.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return arr[:num]


def fetch_volume_top_stocks_gtimg(top_cy=100, top_kc=100, top_zb=100, top_hk=50):
    """活跃股池：按成交额排序分流 创业板/科创板/主板。港股暂不支持（返回空）。"""
    try:
        rank = _sina_rank(max(top_cy + top_kc + top_zb, 300))
    except Exception as e:  # noqa: BLE001
        print(f"  [GTimg] 新浪活跃股排行失败: {e}")
        return []
    cy, kc, zb = [], [], []
    for x in rank:
        sym = (x.get("symbol") or "").lower()
        code = sym[2:] if sym.startswith(("sh", "sz")) else sym
        if not code.isdigit():
            continue
        market = "sh" if sym.startswith("sh") else "sz"
        name = x.get("name") or code
        try:
            to = float(x.get("turnoverratio") or 0)
        except Exception:  # noqa: BLE001
            to = 0.0
        if code.startswith(("300", "301")):
            cy.append((code, name, market, "创业板", 0, to, 0, "混合"))
        elif code.startswith(("688", "689")):
            kc.append((code, name, market, "科创板", 0, to, 0, "混合"))
        else:
            zb.append((code, name, market, "主板", 0, to, 0, "混合"))
    stocks = cy[:top_cy] + kc[:top_kc] + zb[:top_zb]
    print(f"  [GTimg] 活跃股池: 创业{len(cy[:top_cy])} 科创{len(kc[:top_kc])} 主板{len(zb[:top_zb])}")
    return stocks


if __name__ == "__main__":
    df = fetch_a_daily_gtimg("000001", "sz", 120)
    print("日K rows:", "None" if df is None else len(df),
          "| last:", "None" if df is None else f"{df.iloc[-1]['date']} close={df.iloc[-1]['close']}")
    st = fetch_volume_top_stocks_gtimg(5, 5, 5, 0)
    print("股池:", [(s[0], s[1], s[3]) for s in st])
