#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_sina_kline_gaps.py — QQ域被WAF拉黑时，用项目栈内的新浪接口补拉缺失A股多年K线

数据源：quotes.sina.cn CN_MarketDataService.getKLineData（scale=240 日线，datalen≤1023≈4.2年）
单位校准（2026-10-25 600519 同日实锤）：gtimg vol=手(33514) / sina vol=股(3351416)，整100倍
      ⇒ sina volume ÷100 后与 gtimg/生产口径一致（amt60 横截面排序不被打乱）
诚实边界：sina 此接口为不复权价，除权除息日会产生人为收益缺口（仅影响本批补拉票的前向收益，
      占池 23%，事件稀疏）；gtimg qfq 与之混用需在结论中注明。
"""
import json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "kline_cache_multi")
GOLD = os.environ.get("GOLD_PATH", os.path.join(RAW, "gold_pool_origin_main.json"))

os.makedirs(OUT, exist_ok=True)


def sina_kline(sym, datalen=1023):
    url = ("https://quotes.sina.cn/cn/api/jsonp_v2.php/cb/CN_MarketDataService.getKLineData"
           "?symbol=%s&scale=240&ma=no&datalen=%d" % (sym, datalen))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                txt = r.read().decode("utf-8")
            i = txt.find("(")
            j = txt.rfind(")")
            return json.loads(txt[i + 1:j])
        except Exception:
            time.sleep(2.0 + attempt * 2.0)
    return None


def to_rows(arr):
    rows = []
    for x in arr or []:
        try:
            rows.append({
                "date": str(x["day"]),
                "open": float(x["open"]),
                "close": float(x["close"]),
                "high": float(x["high"]),
                "low": float(x["low"]),
                "volume": float(x["volume"]) / 100.0,  # 股→手，对齐 gtimg/生产口径
            })
        except Exception:
            continue
    return rows


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    jobs = []
    for k in gold["stocks"].keys():
        pre, code = k.split("_")[0], k.split("_")[-1]
        if pre not in ("sh", "sz"):
            continue  # 港股新浪此接口无数据，诚实排除
        if os.path.exists(os.path.join(OUT, code + ".json")):
            continue
        jobs.append((code, pre + code))
    print("待补拉 A股: %d" % len(jobs), flush=True)
    ok = fail = 0
    for idx, (code, sym) in enumerate(jobs, 1):
        arr = sina_kline(sym)
        rows = to_rows(arr)
        if len(rows) >= 60:
            json.dump(rows, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"))
            ok += 1
        else:
            fail += 1
        if idx % 50 == 0 or idx == len(jobs):
            print("progress %d/%d ok=%d fail=%d" % (idx, len(jobs), ok, fail), flush=True)
        time.sleep(0.35)
    print("DONE ok=%d fail=%d" % (ok, fail), flush=True)


if __name__ == "__main__":
    main()
