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
    # 🛡 2026-11-20 根治（Alpha 空转根因链）：旧串行版 958 只 × (0.4s sleep + 境外IP延迟 + 失败冷却6s)
    #   每次都 >40min 硬超时被杀 → 金股池深缓存(≥800根)从未建成 → kline_cache 全局日期轴仅 ~251 天
    #   < factor_walkforward MIN_BARS=515 → stock_forward_alpha 调仓点恒为 0 →「无有效持有期结果」
    #   → Alpha 因子结构性空转（2026-11-19 云端批次日志实证）。
    #   【修法】线程池并行（实测境内网络 0.2s/只，12 workers ≈ 3~5min 全量完成）+ wall-clock 预算
    #   保护（默认 25min < 监督器 40min 硬超时，超预算保留已完成进度，幂等下轮续跑）。
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=int(os.environ.get("MULTIYEAR_WORKERS", "12")))
    ap.add_argument("--budget", type=int, default=int(os.environ.get("MULTIYEAR_BUDGET_S", "1500")),
                    help="wall-clock 预算秒数，超预算保留进度退出（幂等可续跑）")
    ap.add_argument("--force", action="store_true", help="忽略跳过条件全量重抓")
    args = ap.parse_args()
    from concurrent.futures import ThreadPoolExecutor, as_completed
    jobs = [("000001", "sh000001")]  # 上证指数基准最前
    for c in sorted(codes):
        jobs.append((c, "sh" + c if c.startswith("6") else "sz" + c))
    # 幂等增量：深度 ≥761 且末根日期在 4 天内才跳过（覆盖周末+短假期；长假后自动全量补抓）
    _fresh = (datetime.date.today() - datetime.timedelta(days=4)).isoformat()
    todo, skip = [], 0
    for code, sym in jobs:
        outp = os.path.join(OUT, code + ".json")
        if not args.force and os.path.exists(outp):
            try:
                _rows = json.load(open(outp, encoding="utf-8"))
                _last = _rows[-1].get("date", "") if isinstance(_rows, list) and _rows else ""
                if len(_rows) >= 761 and _last >= _fresh:
                    skip += 1
                    continue
            except Exception:
                pass
        todo.append((code, sym))
    n = len(todo)
    print("plan: total=%d skip=%d todo=%d workers=%d budget=%ds" % (len(jobs), skip, n, args.workers, args.budget), flush=True)
    t0 = time.time()
    ok = fail = 0
    failed_codes = []

    def _one(job):
        code, sym = job
        bars_n = 1200 if sym == "sh000001" else 800
        k = fetch_kline(sym, bars_n)
        rows = to_rows(k)
        if len(rows) >= 60:
            json.dump(rows, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"))
            return code, True, len(rows)
        return code, False, 0

    done_cnt = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_one, j): j for j in todo}
        for fu in as_completed(futs):
            # wall-clock 预算保护：超预算不再等新任务提交结果，保留已完成进度（幂等可续跑）
            if time.time() - t0 > args.budget:
                print("BUDGET_EXCEEDED %.0fs done=%d ok=%d fail=%d —— 保留进度退出，下轮幂等续跑" % (time.time() - t0, done_cnt, ok, fail), flush=True)
                for f2 in futs:
                    f2.cancel()
                break
            code, good, nr = fu.result()
            done_cnt += 1
            if good:
                ok += 1
            else:
                fail += 1
                failed_codes.append(code)
            if done_cnt % 100 == 0 or done_cnt == n:
                print("progress %d/%d ok=%d fail=%d skip=%d %.0fs" % (done_cnt, n, ok, fail, skip, time.time() - t0), flush=True)
    print("DONE ok=%d fail=%d skip=%d 用时%.0fs" % (ok, fail, skip, time.time() - t0), flush=True)
    if failed_codes:
        print("FAILED_CODES(%d): %s" % (len(failed_codes), ",".join(failed_codes[:50])), flush=True)


if __name__ == "__main__":
    main()
