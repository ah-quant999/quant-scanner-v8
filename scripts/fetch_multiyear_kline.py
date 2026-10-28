#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_multiyear_kline.py — 用 gtimg 前复权日K为金股池拉多年历史（本地决定性验证用）

数据源：web.ifzq.gtimg.cn fqkline（与生产 data_source_gtimg._kline_json 同源同口径）
实测：个股上限 640 根（约2.6年，2024-03→今）；指数 sh000001 可给 1200 根。
输出：raw_data/kline_cache_multi/<code6>.json  = [{date,open,close,high,low,volume},...] 升序
      raw_data/kline_cache_multi/000001.json  = 上证指数（ivol60 基准，生产同口径）
"""
import json, os, re, time, urllib.request, sys, glob
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
# 🛡 2026-10-28 根治：直接写到 raw_data/kline_cache（≥640 根），使生产回测脚本在云端零网络可取、
#   且深度满足 factor_lab_backtest(NEED_MIN=261)/factor_walkforward(MIN_BARS=515)/backtest_tdx(TDX_BARS=520)。
#   旧的 kline_cache_multi 短缓存(250 根)喂不饱长持有期，故统一升级到 kline_cache。
OUT = os.path.join(RAW, "kline_cache")
GOLD = os.environ.get("GOLD_PATH", os.path.join(RAW, "gold_pool_origin_main.json"))

os.makedirs(OUT, exist_ok=True)


HOSTS = (
    # 🛡 2026-10-28 根治：web.ifzq.gtimg.cn 子域 10-24 起恒 501（腾讯下线），主域 ifzq.gtimg.cn 实测
    #   个股 801 根 / 指数 1201 根，提到首位；web. 子域保留兜底。
    "https://ifzq.gtimg.cn/appstock/app/fqkline/get",
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
    # 🛡 2026-10-28 根治：只升级「金股池并集」(当前池 + 历史快照) 的 kline_cache 到 ≥800 根，
    #   而非全市场 5371 只 —— 避免一次性往 git 塞 ~320MB 触发 v8 膨胀红线。
    #   金股池(≈936 只)正是 backtest_tdx / backtest_comprehensive 的真实 universe；
    #   factor_walkforward / factor_lab_backtest 默认遍历全 kline_cache，但只有金股池这批有深度 →
    #   真回测只落在金股池(策略相关池)，其余被 MIN_BARS 自然过滤，语义正确且零浪费。
    #   上证指数 000001 基准单独保留(1200 根)。已 ≥761 根的直接跳过，不重复刷。
    os.makedirs(OUT, exist_ok=True)
    codes = set()
    # 覆盖 backtest_tdx 实际读取的 gold_pool 源（_load_gold_pool 优先 out/ 再 data/，
    # stage_to_raw 后 raw_data/ 才刷新）—— 三处并集即回测真实 universe。
    for gp in (GOLD, os.path.join(RAW, "gold_pool.json"),
               os.path.join(ROOT, "out", "gold_pool.json"),
               os.path.join(ROOT, "data", "gold_pool.json")):
        try:
            d = json.load(open(gp, encoding="utf-8"))
            s = d.get("stocks", d) if isinstance(d, dict) else d
            if isinstance(s, dict):
                for k, v in s.items():
                    c = (v.get("code") if isinstance(v, dict) else None) or k.split("_")[-1]
                    if re.match(r"^\d{6}$", c):
                        codes.add(c)
        except Exception:
            pass
    for p in glob.glob(os.path.join(RAW, "gold_pool_*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            s = d.get("stocks", d) if isinstance(d, dict) else d
            if isinstance(s, dict):
                for k, v in s.items():
                    c = (v.get("code") if isinstance(v, dict) else None) or k.split("_")[-1]
                    if re.match(r"^\d{6}$", c):
                        codes.add(c)
        except Exception:
            pass
    jobs = [("000001", "sh000001")]  # 上证指数基准最前
    for c in sorted(codes):
        jobs.append((c, "sh" + c if c.startswith("6") else "sz" + c))
    ok = fail = skip = 0
    n = len(jobs)
    for idx, (code, sym) in enumerate(jobs, 1):
        outp = os.path.join(OUT, code + ".json")
        if os.path.exists(outp):
            try:
                # 🛡 2026-10-28 新鲜度门槛：深度 ≥761 且末根日期在 4 天内才跳过（幂等增量）。
                #   只看深度会让缓存永远缺最新交易日（回测吃陈旧数据）；4 天窗口覆盖周末+短假期，
                #   长假后首个交易日自动全量补抓（~19min，2400s 预算内）。
                _rows = json.load(open(outp, encoding="utf-8"))
                _last = _rows[-1].get("date", "") if isinstance(_rows, list) and _rows else ""
                _fresh = (datetime.date.today() - datetime.timedelta(days=4)).isoformat()
                if len(_rows) >= 761 and _last >= _fresh:
                    skip += 1
                    continue
            except Exception:
                pass
        # 🛡 2026-10-28 根治：个股目标 800 根（非 640）。
        #   原 640 仍低于 factor_lab_backtest 的硬门槛 MIN_BARS=761（NEED_MIN=261+2×250），
        #   云端 V8_NO_NET 下 factor_lab 仍会写「累积中」而非真回测。800 留足余量（761+39），
        #   与 FETCH_DAYS=800 同口径；上证指数基准保持 1200。
        bars_n = 1200 if sym == "sh000001" else 800
        k = fetch_kline(sym, bars_n)
        rows = to_rows(k)
        if len(rows) >= 60:
            json.dump(rows, open(outp, "w", encoding="utf-8"))
            ok += 1
            time.sleep(0.4)  # 慢速防 429
        else:
            fail += 1
            time.sleep(6.0)  # 🛡 2026-10-28 限流冷却：突发窗口被打爆后 0.4s 间隔会连环失败，拉长间隔自愈
        if idx % 100 == 0 or idx == n:
            print("progress %d/%d ok=%d fail=%d skip=%d" % (idx, n, ok, fail, skip), flush=True)
    print("DONE ok=%d fail=%d skip=%d" % (ok, fail, skip), flush=True)


if __name__ == "__main__":
    main()
