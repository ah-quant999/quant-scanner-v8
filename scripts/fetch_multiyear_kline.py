#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_multiyear_kline.py — 用 gtimg 前复权日K为金股池拉多年历史（本地决定性验证用）

数据源：web.ifzq.gtimg.cn fqkline（与生产 data_source_gtimg._kline_json 同源同口径）
实测：个股上限 640 根（约2.6年，2024-03→今）；指数 sh000001 可给 1200 根。
输出：raw_data/kline_cache_multi/<code6>.json  = [{date,open,close,high,low,volume},...] 升序
      raw_data/kline_cache_multi/000001.json  = 上证指数（ivol60 基准，生产同口径）
"""
import json, os, time, urllib.request, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "kline_cache_multi")
GOLD = os.environ.get("GOLD_PATH", os.path.join(RAW, "gold_pool_origin_main.json"))

os.makedirs(OUT, exist_ok=True)


HOSTS = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get",  # 生产同款备用域
)


_DEAD_HOSTS = set()  # 进程内拉黑（生产 _kline_json 同款：域名级 501 不再白撞）


def fetch_kline(sym, bars):
    param = "%s,day,,,%d,qfq" % (sym, bars)
    last = None
    for host in HOSTS:
        if host in _DEAD_HOSTS:
            continue  # 本进程内已确认失效，直接跳过
        url = host + "?param=" + param
        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    d = json.loads(r.read().decode("utf-8"))
                node = (d.get("data") or {}).get(sym) or {}
                return node.get("qfqday") or node.get("day") or []
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 403, 501):
                    time.sleep(2.0 + attempt * 3.0)
                    continue
                break  # 其他HTTP错误换域
            except Exception as e:
                last = e
                time.sleep(1.5)
        # 该域连续 4 次尝试均失败 → 进程内拉黑（域名级故障，不必每只票白撞）
        _DEAD_HOSTS.add(host)
        print("  [fetch] %s 连续失败(%s) → 进程内拉黑，后续直连下一域" % (host.split("/")[2], last), flush=True)
    return None


def to_rows(k):
    rows = []
    for it in k or []:
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
        except Exception:
            continue
    return rows


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    stocks = gold["stocks"]
    jobs = []
    for k in stocks.keys():
        pre, code = k.split("_")[0], k.split("_")[-1]
        jobs.append((code, pre + code))
    # 上证指数基准放最前
    jobs.insert(0, ("000001", "sh000001"))
    ok = fail = skip = 0
    n = len(jobs)
    for idx, (code, sym) in enumerate(jobs, 1):
        outp = os.path.join(OUT, code + ".json")
        if os.path.exists(outp):
            skip += 1
            continue
        bars_n = 1200 if sym == "sh000001" else 640
        k = fetch_kline(sym, bars_n)
        rows = to_rows(k)
        if len(rows) >= 60:
            json.dump(rows, open(outp, "w", encoding="utf-8"))
            ok += 1
        else:
            fail += 1
        if idx % 100 == 0 or idx == n:
            print("progress %d/%d ok=%d fail=%d skip=%d" % (idx, n, ok, fail, skip), flush=True)
        time.sleep(0.4)  # 慢速防 429
    print("DONE ok=%d fail=%d skip=%d" % (ok, fail, skip), flush=True)


if __name__ == "__main__":
    main()
