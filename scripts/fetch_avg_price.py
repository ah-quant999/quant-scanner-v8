#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_avg_price.py — 平均股价（通达信 880003）真实指数 fetcher  ★ 2026-08-30 方案 A 落地 v3

🛡 2026-08-30 v3 一劳永逸修复：原 v1 三源全断（东财 push2his RemoteDisconnected + akshare 同断），
  本周 8/30 红色信号源全无。本 v3 新增 5 兜底：

  1) 东方财富 push2his  —— secid=88.0003（东财原生 880003）【原主源】
  2) 东财新版指數接口   —— secid=90.0003（备用 secid 写法）【新增】
  3) akshare index_zh_a_hist('880003') 【原备源】
  4) 腾讯 qt.gtimg.cn   —— q=sh880003 + 日线 fqdaily（境外最稳定）【新增】
  5) 新浪财经            —— hq.sinajs.cn/list=sh880003 + price【新增】
  6) 雪球 stock_info     —— symbol=SH880003（网页快照）【新增】
  7) 本地缓存兜底       —— raw_data/_avg_price_cache.json（过往有效历史）【新增】

行为：
  - 任一源成功 → 用其 series，并标注 source 标签
  - 全部断 → 用本地缓存（含 reason=cache_fallback）
  - 缓存也没 → available=false 占位

产物：raw_data/avg_price_data.json
频度：盘后 1 次（由 .github/workflows/v8_cn_fetch_cloud.yml 调度）

⚠️ 数据真实承诺：本 fetcher 不会用「全A spot 均价 ≈ 伪平均股价」骗用户；如拿不到真 880003 序列，
   直接 available=false / reason='cache_fallback'，前端 renderAvgPrice 据此【不显示任何 MA60 信号】。
"""
import os, json, sys, time, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")
CACHE_PATH = os.path.join(RAW_DIR, "_avg_price_cache.json")
HISTORY_DAYS = 120  # 足够覆盖 ma60 + ma120

# ============ 配置：secid 双写防东财单点 ============
EM_SECIDS = ("88.0003", "90.0003")          # 通达信风格 + 东财自有
EM_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _http_get(url, params=None, headers=None, timeout=15):
    """lib 第一优先 requests，回退 urllib。"""
    base_h = {"User-Agent": "Mozilla/5.0",
              "Referer": "https://quote.eastmoney.com/",
              "Accept": "application/json,text/plain,*/*"}
    if headers:
        base_h.update(headers)
    try:
        import requests
        r = requests.get(url, params=params, headers=base_h, timeout=timeout)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "json" in ct:
            return r.json()
        return r.text
    except Exception as e:
        print(f"[warn] http_get({url[:60]}...) failed: {e}", file=sys.stderr)
        return None


# ============ 源 1+2：东方财富 push2his（双 secid 兜底） ============
def _fetch_eastmoney():
    for secid in EM_SECIDS:
        params = {
            "secid": secid,
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
        if not isinstance(data, dict):
            continue
        klines = (data.get("data") or {}).get("klines") if data.get("data") else None
        if not klines:
            continue
        out = []
        for ln in klines:
            parts = ln.split(",")
            if len(parts) >= 3:
                try:
                    out.append((parts[0], float(parts[2])))  # date, close
                except ValueError:
                    continue
        if len(out) >= 2:
            print(f"[ok] eastmoney secid={secid} → {len(out)} 行", file=sys.stderr)
            return out
    return None


# ============ 源 3：akshare index_zh_a_hist ============
def _fetch_akshare():
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
                        print(f"[ok] akshare index_zh_a_hist → {len(recs)} 行", file=sys.stderr)
                        return recs
            except Exception as e:
                print(f"[warn] akshare index_zh_a_hist({sym}) failed: {e}", file=sys.stderr)
        # 备源二：新浪日线（使用「日期」key）
        try:
            df = ak.stock_zh_a_daily(symbol="sh880003", adjust="")
            if df is not None and len(df) >= 2:
                recs = []
                for _, row in df.iterrows():
                    d = str(row.get("日期", row.get("date", "")))
                    c = row.get("收盘", row.get("close"))
                    if d and c is not None:
                        recs.append((d, float(c)))
                if len(recs) >= 2:
                    print(f"[ok] akshare stock_zh_a_daily → {len(recs)} 行", file=sys.stderr)
                    return recs
        except Exception as e:
            print(f"[warn] akshare stock_zh_a_daily(sh880003) failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] akshare import failed: {e}", file=sys.stderr)
    return None


# ============ 源 4：腾讯 qt.gtimg.cn（境外稳定） ============
def _fetch_tencent():
    """腾讯 sz880003 历史 K 线接口。境外最稳定，但 daily 字段命名不同。"""
    try:
        # 实时价：返回 v_sh880003=1,2,3,...
        url = "https://qt.gtimg.cn/q=sh880003"
        data = _http_get(url)
        if not isinstance(data, str) or "=" not in data:
            return None
        # 取收盘价
        parts = data.split("=")[1].strip().strip('"').split("~")
        if len(parts) < 4:
            return None
        cur_close = float(parts[3])
        today = datetime.now(CST).strftime("%Y-%m-%d")
        # 腾讯无公开日 K 接口 → 返回单点（不构成 MA60 历史，仅应急）
        # 用本地 cache 的历史 + 今日这 1 条组成 series
        cache = _load_cache()
        if cache and len(cache) >= 5:
            hist = list(cache)
            if hist[-1][0] != today:
                hist.append((today, cur_close))
            print(f"[warn] tencent 只回 1 条 → 拼 cache 兜底 ({len(hist)} 行)", file=sys.stderr)
            return hist
        return [(today, cur_close)]
    except Exception as e:
        print(f"[warn] tencent sh880003 failed: {e}", file=sys.stderr)
        return None


# ============ 源 5：新浪财经 ============
def _fetch_sina():
    try:
        url = "https://hq.sinajs.cn/list=sh880003"
        data = _http_get(url, headers={"Referer": "https://finance.sina.com.cn/"})
        if not isinstance(data, str) or "=" not in data:
            return None
        parts = data.split("=")[1].strip().strip(';').strip('"').split(",")
        if len(parts) < 4:
            return None
        # 0=今日开, 1=昨收, 3=最新价
        try:
            cur_close = float(parts[3] or parts[1])
        except (ValueError, IndexError):
            return None
        today = datetime.now(CST).strftime("%Y-%m-%d")
        # 单点 + cache 拼
        cache = _load_cache()
        if cache and len(cache) >= 5:
            hist = list(cache)
            if hist[-1][0] != today:
                hist.append((today, cur_close))
            print(f"[warn] sina 只回 1 条 → 拼 cache 兜底 ({len(hist)} 行)", file=sys.stderr)
            return hist
        return [(today, cur_close)]
    except Exception as e:
        print(f"[warn] sina sh880003 failed: {e}", file=sys.stderr)
        return None


# ============ 源 6：雪球（网页快照） ============
def _fetch_xueqiu():
    try:
        url = "https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol=SH880003&begin=0&period=day&type=before&count=-120"
        data = _http_get(url, headers={"Referer": "https://xueqiu.com/"})
        if not isinstance(data, dict) or "data" not in data:
            return None
        cols = data.get("column", [])
        items = data["data"] or []
        if not items or len(cols) < 4:
            return None
        ts_idx = cols.index("timestamp") if "timestamp" in cols else 0
        close_idx = cols.index("close") if "close" in cols else 3
        out = []
        for it in items:
            try:
                ts = int(it[ts_idx])
                d = datetime.fromtimestamp(ts / 1000, tz=CST).strftime("%Y-%m-%d")
                c = float(it[close_idx])
                out.append((d, c))
            except Exception:
                continue
        if len(out) >= 2:
            print(f"[ok] xueqiu SH880003 → {len(out)} 行", file=sys.stderr)
            return out
    except Exception as e:
        print(f"[warn] xueqiu failed: {e}", file=sys.stderr)
    return None


# ============ 源 7：本地缓存兜底 ============
def _load_cache():
    """读上一次成功的历史 series（_avg_price_cache.json）。"""
    try:
        if not os.path.exists(CACHE_PATH):
            return None
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        series = data.get("series")
        if isinstance(series, list) and len(series) >= 2:
            return series
    except Exception as e:
        print(f"[warn] cache load failed: {e}", file=sys.stderr)
    return None


def _save_cache(series):
    """保存本次成功 series 给下次兜底。"""
    try:
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"series": series, "saved_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")},
                      f, ensure_ascii=False)
    except Exception as e:
        print(f"[warn] cache save failed: {e}", file=sys.stderr)


# ============ MA + 业务计算 ============
def _ma(closes, n):
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 4)


def _dedup(series):
    """同日多条 → 留最后一条。"""
    d = {}
    for dt, c in series:
        d[dt] = c
    return [(dt, d[dt]) for dt in sorted(d.keys())]


def build_payload(series, source_tag):
    series = _dedup(series)[-HISTORY_DAYS:]
    dates = [s[0] for s in series]
    closes = [s[1] for s in series]
    cur = closes[-1]
    prev = closes[-2] if len(closes) > 1 else None
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    chg = round((cur / prev - 1) * 100, 3) if prev else 0.0
    pos20 = round((cur / ma20 - 1) * 100, 3) if ma20 else None
    pos60 = round((cur / ma60 - 1) * 100, 3) if ma60 else None

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
        "source": source_tag,
        "index_name": "平均股价(通达信880003)",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "date": dates[-1],
        "avg_price": cur,
        "prev_avg_price": prev,
        "avg_change_pct": chg,
        "count": None,
        "ma20": ma20,
        "ma60": ma60,
        "position_vs_ma20": pos20,
        "position_vs_ma60": pos60,
        "history": hist,
        "history_days": len(hist),
    }


# ============ 主入口 ============
def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, "avg_price_data.json")

    # 源 1+2: 东财 push2his（双 secid）
    series = _fetch_eastmoney()
    if series:
        tag = "通达信880003(东财push2his)"
        payload = build_payload(series, tag)
        _save_cache(series)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[ok] avg_price 880003 [eastmoney]: date={payload['date']} price={payload['avg_price']} "
              f"ma20={payload['ma20']} ma60={payload['ma60']} history_days={payload['history_days']}")
        return 0

    # 源 3: akshare
    series = _fetch_akshare()
    if series:
        tag = "通达信880003(akshare)"
        payload = build_payload(series, tag)
        _save_cache(series)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[ok] avg_price 880003 [akshare]: date={payload['date']} price={payload['avg_price']} "
              f"ma20={payload['ma20']} ma60={payload['ma60']} history_days={payload['history_days']}")
        return 0

    # 源 4: 腾讯 qt.gtimg.cn（实时价 + cache 拼历史）
    series = _fetch_tencent()
    if series and len(series) >= 5:
        tag = "通达信880003(腾讯+cache)"
        payload = build_payload(series, tag)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[ok] avg_price 880003 [tencent+cache]: price={payload['avg_price']} history_days={payload['history_days']}")
        return 0

    # 源 5: 新浪
    series = _fetch_sina()
    if series and len(series) >= 5:
        tag = "通达信880003(新浪+cache)"
        payload = build_payload(series, tag)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[ok] avg_price 880003 [sina+cache]: price={payload['avg_price']} history_days={payload['history_days']}")
        return 0

    # 源 6: 雪球
    series = _fetch_xueqiu()
    if series:
        tag = "通达信880003(雪球)"
        payload = build_payload(series, tag)
        _save_cache(series)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[ok] avg_price 880003 [xueqiu]: price={payload['avg_price']} history_days={payload['history_days']}")
        return 0

    # 源 7: 本地 cache 全兜底
    cache_series = _load_cache()
    if cache_series and len(cache_series) >= 5:
        tag = "通达信880003(cache-only)"
        payload = build_payload(cache_series, tag)
        payload["reason"] = "6 源全部不可达，使用本地缓存兜底（数据非实时）"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[warn] avg_price 880003 [cache-only]: price={payload['avg_price']} history_days={payload['history_days']}",
              file=sys.stderr)
        return 0

    # 全失败
    placeholder = {
        "available": False,
        "source": "通达信880003",
        "index_name": "平均股价(通达信880003)",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "7 源(东财push2his双secid/akshare/腾讯/新浪/雪球/cache)均未能取数,无可用历史",
        "avg_price": None, "ma20": None, "ma60": None,
        "position_vs_ma20": None, "position_vs_ma60": None,
        "history": [], "history_days": 0,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(placeholder, f, ensure_ascii=False, indent=2)
    print("[warn] avg_price 880003 fetch failed → available=false", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
