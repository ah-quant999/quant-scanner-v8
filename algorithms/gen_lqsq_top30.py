#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量质双擎（LQSQ）· 每日生成器 —— 第一支自研算法（2026-10-11 主人令「按你建议做吧/今晚上线」）

定位：与「因子实验室」严格区隔 —— 因子实验室继续为其他算法的股票评分排序（评分卡）；
本算法是**独立选股器**：全市场直选 Top30，真实信号流口径上主榜（与四量同榜同纪律）。

【选股规则 v1】（全部 ≤T 日可得，无未来函数）：
  · 因子 r = mean(vol, 近20交易日) / mean(vol, 之前240交易日)；r 越小=越缩量=越强
    （与 FACTOR_LAB「异常量比：当月换手率÷过去12月均值，缩量=强势」同义；
    成交量代换手率——同一股票内比值对流通股本变化近似不敏感）。
  · 过滤：上市≥261 交易日；数据日未停牌且近20日每日未停牌；收盘≥2元（仙股过滤）；
    流动性代理=近20日日均 vol×close ≥ 5000 万元；按当前名单剔除 ST/退。
  · 选股：r 升序 Top30。
  · 持有：T+20 个交易日收盘卖出（主人令「跟踪20日再打分」；1/3/5/10 为参考档）。
  · 成本：双边 0.3%（次开买入口径）。
  · 🔴 ROE 质地引擎 v2 待接：财务 point-in-time 历史不可回溯，回放/真实流 v1 先单量因子
    跑通；v2 在真实信号流中以当日可得财报叠 ROE 过滤（回看归档历史样本不改动）。

【真实信号流纪律（2026-10-11 铁令）】：
  · 每日信号逐日落盘 raw_data/lqsq_history.json（含已回落/淘汰票，防幸存者偏差），
    **上线第一天即建归档**（四量「算法早跑、归档晚建」的欠账不再犯）。
  · 主榜只认本文件产出的真实流自回测（raw_data/lqsq_backtest.json → LQSQ_BACKTEST），
    未走满 T+20 的样本不计入，成熟一档进一档。
  · 数据源 raw_data/kline_cache/*.json 是 gen_strong_breakout 的副产物缓存（仅 ~251 根/只、
    且只逐晚回写强势股 —— 末根碎片化是常态，2026-10-11 bootstrap 实测对齐率仅 12%）。
    🔴 本脚本因此**自带全量自刷新**（refresh_stale）：对末根落后/根数不足的股票，
    经 scanner.fetch_a_daily（云端=GTimg 前复权，与实盘同通道）6 线程并发拉 700 根
    **整根替换**（禁增量拼接——除权会使拼接缝量纲断裂），内存参与打分；
    成功（末根=数据日）的写入 raw_data/kline_cache_ext/（runner 持久、不入仓，
    .gitignore 隔离），次日仅增量请求，日常全市场 ~4 分钟。

输出：
  raw_data/lqsq_history.json   真实信号逐日归档（主档，只增不改）
  raw_data/lqsq_track.json     全量信号前向跟踪明细 + 分档统计 + 基准超额
  raw_data/lqsq_backtest.json  主榜视图（summary.by_period 与四量同构 → parse_by_period 零改动）
  data/LQSQ_BACKTEST.js        update_v8._write_js 直写（保证同批 E 批聚合器读到当日新鲜视图）
"""
import os
import sys
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))

RAW_DIR = os.path.join(ROOT, "raw_data")
KLINE_DIR = os.path.join(RAW_DIR, "kline_cache")
EXT_DIR = os.path.join(RAW_DIR, "kline_cache_ext")  # 本脚本专属扩展缓存（700根，不入仓）
HISTORY = os.path.join(RAW_DIR, "lqsq_history.json")
TRACK = os.path.join(RAW_DIR, "lqsq_track.json")
VIEW = os.path.join(RAW_DIR, "lqsq_backtest.json")

RECENT_N = 20
BASELINE_N = 240
MIN_HISTORY = 261
HOLD_HORIZONS = (1, 3, 5, 10, 20)
PRIMARY_HOLD = 20
TOP_N = 30
COST_PCT = 0.3
MIN_PRICE = 2.0
MIN_TURNOVER_YUAN = 50_000_000
# ── 自刷新 ──
EXT_BARS = 700            # 扩展缓存/拉取根数（覆盖 261+240+余量）
EXT_MIN_LEN = 300         # 视为「根数足够」的下限（<MIN_HISTORY+BASELINE 缓冲）
STALE_SKIP_DAYS = 60      # 末根落后超过 60 个自然日的僵尸股跳过不拉（反正被数据日对齐剔除）
REFRESH_WORKERS = 6       # 云端并发拉取线程数（GTimg 轻量 HTTP，6 并发 ≈ 20 QPS）
REFRESH_BUDGET_SEC = float(os.environ.get("LQSQ_REFRESH_BUDGET_SEC", "840"))

_T0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - _T0, msg), flush=True)


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def load_names():
    """当前名单 + 名称（ST/退 过滤按当前名单，历史状态不可回溯，残差如实）。"""
    p = os.path.join(RAW_DIR, "stock_names.json")
    names = {}
    try:
        with open(p, encoding="utf-8") as f:
            for s in (json.load(f).get("data") or []):
                fc = s.get("full_code") or ""
                if isinstance(fc, str) and fc.startswith(("sh", "sz")):
                    code6 = fc[2:]
                    if code6.isdigit():
                        names[code6] = s.get("name") or code6
    except Exception as e:
        log("⚠️ stock_names.json 不可用（名称/ST 过滤降级）: %s" % str(e)[:80])
    return {c: n for c, n in names.items()
            if "ST" not in n.upper() and "退" not in n}


def load_bars():
    """读全市场 K 线缓存 → {code: bars}。bar={date,open,close,high,low,volume}。"""
    out = {}
    if not os.path.isdir(KLINE_DIR):
        raise SystemExit("kline_cache 不存在（%s）——本脚本必须挂在 factor_lab_gen 之后" % KLINE_DIR)
    files = [f for f in os.listdir(KLINE_DIR) if f.endswith(".json")]
    for fn in files:
        code = fn[:-5]
        if not code.isdigit() or len(code) != 6:
            continue
        try:
            with open(os.path.join(KLINE_DIR, fn), encoding="utf-8") as f:
                bars = json.load(f)
            if isinstance(bars, list) and len(bars) >= 60:
                out[code] = bars
        except Exception:
            continue
    log("K线缓存加载：%d 只（来自 %d 个文件）" % (len(out), len(files)))
    return out


# ───────────────────────── 全量自刷新（2026-10-11 bootstrap 对齐率 12% 根治） ─────────────────────────

def _df_to_records(df):
    """fetch_a_daily 的 df → kline records（与缓存同构）。字段缺失返回 None。"""
    try:
        cols = df.columns
        need = ("date", "open", "close", "high", "low", "volume")
        if any(c not in cols for c in need):
            return None
        return [{"date": str(d), "open": round(float(o), 4), "high": round(float(h), 4),
                 "low": round(float(l), 4), "close": round(float(c), 4),
                 "volume": round(float(v), 2)}
                for d, o, h, l, c, v in zip(df["date"], df["open"], df["high"],
                                            df["low"], df["close"], df["volume"])]
    except Exception:
        return None


def _ext_path(code):
    return os.path.join(EXT_DIR, "%s.json" % code)


def _ext_load_fresh(code, data_date):
    """读扩展缓存：仅当末根 == 数据日（且根数足）才可信返回，否则 None（触发重拉）。"""
    try:
        with open(_ext_path(code), encoding="utf-8") as f:
            bars = json.load(f)
        if isinstance(bars, list) and len(bars) >= EXT_MIN_LEN and bars[-1]["date"] == data_date:
            return bars
    except Exception:
        pass
    return None


def _ext_save(code, records):
    try:
        os.makedirs(EXT_DIR, exist_ok=True)
        tmp = _ext_path(code) + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(records, f, ensure_ascii=False)
        os.replace(tmp, _ext_path(code))
    except Exception:
        pass


def _fetch_one(code):
    from scanner import fetch_a_daily
    df = fetch_a_daily(code, bars=EXT_BARS)
    return _df_to_records(df) if df is not None else None


def refresh_stale(bars_map):
    """全量自刷新：末根落后或根数不足的股票 → GTimg 700 根整根替换（并发、预算内、可续跑）。
    成功（末根=数据日）写扩展缓存；停牌/僵尸不写（重拉判定天然兜底）。原地更新 bars_map。"""
    t0 = time.time()
    data_date = max(r[-1]["date"] for r in bars_map.values())
    from datetime import datetime as _dt

    def _days_lag(dstr):
        try:
            return (_dt.strptime(data_date, "%Y-%m-%d") - _dt.strptime(dstr, "%Y-%m-%d")).days
        except Exception:
            return 9999

    todo = []
    for code, bars in bars_map.items():
        ld = bars[-1]["date"]
        if ld == data_date and len(bars) >= EXT_MIN_LEN:
            continue  # 新鲜且根数足
        if ld != data_date and _days_lag(ld) > STALE_SKIP_DAYS:
            continue  # 僵尸/长期停牌：跳过（数据日对齐过滤天然剔除）
        # 扩展缓存命中（末根==数据日）直接换上，零请求
        ext = _ext_load_fresh(code, data_date)
        if ext is not None:
            bars_map[code] = ext
            continue
        todo.append(code)
    log("自刷新：需拉取 %d 只（数据日 %s；预算 %.0fs / 并发 %d）" % (
        len(todo), data_date, REFRESH_BUDGET_SEC, REFRESH_WORKERS))
    ok = fail = 0
    cloud = os.environ.get("CLOUD_RUNNER", "").lower() == "true" or \
            os.environ.get("GITHUB_ACTIONS", "").lower() == "true"

    def _work(code):
        try:
            return code, _fetch_one(code)
        except Exception as e:  # 单只隔离：网络抖动/单票异常只计失败，绝不打死整轮
            return code, ("%s %s" % (type(e).__name__, str(e)[:60]))

    pool = ThreadPoolExecutor(max_workers=REFRESH_WORKERS if cloud else 1)
    try:
        futs = {pool.submit(_work, c): c for c in todo}
        err_shown = 0
        for fut in as_completed(futs):
            code, recs = fut.result()
            if isinstance(recs, str):  # 异常摘要（明细限流：最多打印 5 条）
                fail += 1
                if err_shown < 5:
                    log("⚠️ 单只异常 %s: %s" % (code, recs))
                    err_shown += 1
                continue
            if recs and len(recs) >= 60 and recs[-1]["date"] >= bars_map.get(code, [{}])[-1].get("date", ""):
                bars_map[code] = recs
                if recs[-1]["date"] == data_date:
                    _ext_save(code, recs)
                ok += 1
            else:
                fail += 1
                if recs is None and err_shown < 5:
                    log("⚠️ 单只无数据 %s（源返回空）" % code)
                    err_shown += 1
            if (ok + fail) % 500 == 0:
                log("  自刷新进度 %d/%d（ok=%d fail=%d，%.0fs）" % (
                    ok + fail, len(todo), ok, fail, time.time() - t0))
            if time.time() - t0 > REFRESH_BUDGET_SEC:
                log("⚠️ 自刷新预算 %.0fs 耗尽（完成 %d/%d）——余下按缓存旧值参与（保护闸把关）" % (
                    REFRESH_BUDGET_SEC, ok + fail, len(todo)))
                break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    log("自刷新完成：%d 只成功 / %d 失败（%.0fs）" % (ok, fail, time.time() - t0))
    return ok, fail


def main():
    bars_map = load_bars()
    if len(bars_map) < 3000:
        raise SystemExit("缓存不足 3000 只（%d），保护性中止" % len(bars_map))
    names = load_names()

    # ── 全量自刷新（kline_cache 是强势股副产物缓存，末根碎片化/仅251根是常态） ──
    if os.environ.get("LQSQ_REFRESH") != "0":
        refresh_stale(bars_map)

    # ── 数据日 = 各股末根的最大日期（缓存新鲜度保护闸：对齐率<60% 保护性中止，宁停不选错） ──
    last_dates = Counter(r[-1]["date"] for r in bars_map.values())
    data_date = max(last_dates)
    n_at = last_dates[data_date]
    if n_at < 0.6 * len(bars_map) and os.environ.get("LQSQ_SMOKE") != "1":
        top5 = ", ".join("%s:%d" % (d, c) for d, c in last_dates.most_common(5))
        raise SystemExit("数据日 %s 对齐率不足（%d/%d= %.0f%% < 60%%）——kline_cache 新鲜度异常，"
                         "保护性中止（末根分布 top5: %s）" % (data_date, n_at, len(bars_map),
                                                            100.0 * n_at / len(bars_map), top5))
    stale_n = len(bars_map) - n_at
    log("数据日=%s（%d/%d 只末根对齐，异频 %d 只剔除）" % (data_date, n_at, len(bars_map), stale_n))

    # ── 当日打分（因子只用 ≤T） ──
    scored = []
    for code, bars in bars_map.items():
        if len(bars) < MIN_HISTORY or bars[-1]["date"] != data_date:
            continue
        if code not in names:
            continue  # 名称缺失/当前 ST/退
        j = len(bars) - 1
        close = bars[j]["close"]
        if close < MIN_PRICE:
            continue
        recent = [b["volume"] for b in bars[j - RECENT_N + 1: j + 1]]
        base = [b["volume"] for b in bars[j - RECENT_N - BASELINE_N + 1: j - RECENT_N + 1]]
        if len(recent) < RECENT_N or len(base) < BASELINE_N:
            continue
        if any(v <= 0 for v in recent):
            continue  # 近月有停牌
        liq = sum(v * b["close"] for v, b in zip(recent, bars[j - RECENT_N + 1: j + 1])) / RECENT_N
        if liq < MIN_TURNOVER_YUAN:
            continue
        ratio = (sum(recent) / RECENT_N) / (sum(base) / BASELINE_N)
        scored.append((round(ratio, 4), code, close))
    scored.sort()
    log("打分完成：过滤后 %d 只 → Top%d（min_ratio=%.3f / 第30名=%.3f）" % (
        len(scored), TOP_N, scored[0][0] if scored else -1,
        scored[TOP_N - 1][0] if len(scored) >= TOP_N else -1))

    # ── 真实信号流归档（只增不改；同日重跑幂等） ──
    hist = {"meta": {
        "algo_name": "量质双擎（LQSQ）",
        "factor_def": "r=mean(vol[近20日])/mean(vol[之前240日])，升序Top30（最缩量=最强）",
        "filters": "上市≥261交易日/当日未停牌/近20日无停牌/收盘≥2元/日均vol×close≥5000万/当前名单剔ST",
        "cost_pct": COST_PCT, "primary_hold": PRIMARY_HOLD,
    }, "signals": {}}
    if os.path.exists(HISTORY):
        try:
            with open(HISTORY, encoding="utf-8") as f:
                old = json.load(f)
            hist["meta"]["track_start"] = old.get("meta", {}).get("track_start")
            hist["signals"] = old.get("signals") or {}
        except Exception as e:
            log("⚠️ 旧归档读取失败（以新档继续，旧档保留备份）: %s" % str(e)[:80])
    track_start = hist["meta"].get("track_start") or data_date
    hist["meta"]["track_start"] = track_start
    if data_date in hist["signals"]:
        log("数据日 %s 已在归档（幂等跳过追加）" % data_date)
    else:
        hist["signals"][data_date] = [
            {"code": c, "name": names.get(c, c), "ratio": r, "close": cl}
            for r, c, cl in scored[:TOP_N]]
        log("✅ 归档 %s：新增 %d 笔（累计 %d 个信号日）" % (
            data_date, len(hist["signals"][data_date]), len(hist["signals"])))
    with open(HISTORY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hist, f, ensure_ascii=False)

    # ── 前向跟踪（次开买入，扣 0.3%；未走满如实不计） ──
    all_days = sorted({b["date"] for bars in bars_map.values() for b in bars})
    day_idx = {d: i for i, d in enumerate(all_days)}
    tracked = []   # {code,name,signal_date,ratio,close,returns{},immature[]}
    bench_by_date = {}  # date -> {p: universe mean}
    bench_pool_by_date = {}
    for sd, sigs in sorted(hist["signals"].items()):
        pool = [s["code"] for s in sigs]
        tracked_date = []
        for s in sigs:
            bars = bars_map.get(s["code"])
            rec = dict(s)
            rec["signal_date"] = sd
            rec["returns"] = {}
            rec["immature"] = []
            if bars is None:
                rec["immature"] = [str(p) for p in HOLD_HORIZONS]
                tracked.append(rec)
                continue
            # 信号日位置：以该股自身 K 线定位（当日必在）
            j = next((k for k, b in enumerate(bars) if b["date"] == sd), None)
            if j is None or j + 1 >= len(bars):
                rec["immature"] = [str(p) for p in HOLD_HORIZONS]
                tracked.append(rec)
                continue
            entry = bars[j + 1]["open"]
            for p in HOLD_HORIZONS:
                e = j + p
                if e >= len(bars):
                    rec["immature"].append(str(p))
                    continue
                rec["returns"][str(p)] = round(
                    (bars[e]["close"] / entry - 1.0) * 100.0 - COST_PCT, 2)
            tracked.append(rec)

        # 基准：当日过滤 universe（缓存内与数据日对齐、满足同过滤）等权无成本
        uni_day = bench_pool_by_date.get(sd)
        if uni_day is None:
            uni = []
            if sd in day_idx:
                for code, bars in bars_map.items():
                    jj = next((k for k, b in enumerate(bars) if b["date"] == sd), None)
                    if jj is None or jj < MIN_HISTORY or jj + PRIMARY_HOLD >= len(bars):
                        continue
                    if bars[jj]["close"] < MIN_PRICE:
                        continue
                    recent = [b["volume"] for b in bars[jj - RECENT_N + 1: jj + 1]]
                    base = [b["volume"] for b in bars[jj - RECENT_N - BASELINE_N + 1: jj - RECENT_N + 1]]
                    if len(recent) < RECENT_N or len(base) < BASELINE_N or any(v <= 0 for v in recent):
                        continue
                    if code not in names:
                        continue
                    uni.append(code)
            uni_day = uni
            bench_pool_by_date[sd] = uni
        vals = []
        for code in uni_day:
            bars = bars_map[code]
            j = next((k for k, b in enumerate(bars) if b["date"] == sd), None)
            if j is None or j + PRIMARY_HOLD >= len(bars):
                continue
            vals.append((bars[j + PRIMARY_HOLD]["close"] / bars[j + 1]["open"] - 1.0) * 100.0)
        bench_by_date[sd] = round(sum(vals) / len(vals), 2) if vals else None

    # ── 分档统计 ──
    def stats_for(p):
        vals = [t["returns"][str(p)] for t in tracked
                if t["returns"].get(str(p)) is not None]
        if not vals:
            return None
        wins = sum(1 for v in vals if v > 0)
        return {"n": len(vals), "win_rate": round(wins / len(vals) * 100, 1),
                "avg": round(sum(vals) / len(vals), 2),
                "best": round(max(vals), 2), "worst": round(min(vals), 2)}

    self_summary = {str(p): stats_for(p) for p in HOLD_HORIZONS}
    mature = [(p, s) for p, s in self_summary.items() if s]
    b20 = [v for v in bench_by_date.values() if v is not None]
    bench20 = round(sum(b20) / len(b20), 2) if b20 else None

    with open(TRACK, "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "algo_name": "量质双擎（LQSQ）", "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
            "data_date": data_date, "track_start": track_start,
            "total_signals": sum(len(v) for v in hist["signals"].values()),
            "signal_days": len(hist["signals"]),
            "self_summary": self_summary,
            "bench_t20_avg": bench20,
            "bench_by_date": bench_by_date,
            "tracked": tracked,
        }, f, ensure_ascii=False)
    log("跟踪明细已写（%d 笔 / %d 个信号日；T+%d 成熟档=%s）" % (
        len(tracked), len(hist["signals"]), PRIMARY_HOLD,
        ["T+%s n=%s" % (p, self_summary[p]["n"]) for p, s in [(k, v) for k, v in self_summary.items() if v]]))

    # ── 主榜视图（与四量 summary.by_period 同构；仅成熟档） ──
    bp = {}
    for k in sorted(self_summary, key=int):
        s = self_summary[k]
        if not s:
            continue
        bp[k] = {"samples": s["n"], "win_rate": s["win_rate"], "avg_return": s["avg"],
                 "best_return": s["best"], "worst_return": s["worst"]}
    view = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "calc_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": data_date,
        "method": ("真实信号流口径（2026-10-11 主人令）：每日全市场按异常量比（缩量=强势）打分选 Top30，"
                   "次开买入、持有 20 个交易日收盘卖出（前复权·扣双边 0.3%）；基准=同过滤 universe 等权。"
                   "样本随持有天数成熟而增加，未走满 T+20 不计入；ROE 质地过滤 v2 待接。"),
        "signal_source": "lqsq_history 逐日真实选股归档（上线首日即建，含已回落票，防幸存者偏差）",
        "track_start": track_start,
        "signal_date_range": "%s ~ %s" % (track_start, data_date),
        "total_signals": sum(len(v) for v in hist["signals"].values()),
        "cost_adjusted": True,
        "summary": {"by_period": bp},
    }
    with open(VIEW, "w", encoding="utf-8", newline="\n") as f:
        json.dump(view, f, ensure_ascii=False)
    log("主榜视图已写（成熟档 %d 个：%s）" % (
        len(bp), ", ".join("T+%s n=%s" % (k, v["samples"]) for k, v in bp.items()) or "暂无（跟踪未满期）"))

    # ── data js 直写（保证同批 E 批聚合器读到当日新鲜视图；build 的 update_v8 会按 raw_data 重出，幂等） ──
    try:
        import update_v8
        p = update_v8._write_js("LQSQ_BACKTEST", view)
        log("data js 已直写: %s" % p)
    except Exception as e:
        log("⚠️ data js 直写失败（build 兜底）: %s %s" % (type(e).__name__, str(e)[:80]))

    # ── 摘要日志 ──
    log("========== 量质双擎 %s ==========" % data_date)
    for p in HOLD_HORIZONS:
        s = self_summary[str(p)]
        if s:
            log("T+%2s | n=%d | 胜率=%s%% | 均收=%s%% | 最好=%s%% | 最差=%s%%" % (
                p, s["n"], s["win_rate"], s["avg"], s["best"], s["worst"]))
        else:
            log("T+%2s | 未成熟（如实不计）" % p)
    log("T+20 基准（同过滤 universe 等权）: %s%%" % bench20)

    # ── bootstrap 自推（仅一次性工作流 LQSQ_PUSH=1 时；链内常规跑由 git 提交，不走此路径） ──
    if os.environ.get("LQSQ_PUSH") == "1":
        push_bootstrap()


def push_bootstrap():
    """Contents API 推 4 个产物（先取 sha 再 PUT，防覆盖）。"""
    import base64
    import urllib.request
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log("⚠️ 无 GITHUB_TOKEN，跳过自推")
        return
    REPO = "ah-quant999/quant-scanner-v8"
    H = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    files = [
        ("raw_data/lqsq_history.json", HISTORY, "data: 量质双擎 真实信号流归档(阿狸咪的工程师)"),
        ("raw_data/lqsq_track.json", TRACK, "data: 量质双擎 前向跟踪明细(阿狸咪的工程师)"),
        ("raw_data/lqsq_backtest.json", VIEW, "data: 量质双擎 主榜视图(阿狸咪的工程师)"),
        ("data/LQSQ_BACKTEST.js", os.path.join(ROOT, "data", "LQSQ_BACKTEST.js"),
         "data: LQSQ_BACKTEST.js 真实信号流视图(阿狸咪的工程师)"),
    ]
    for rel, local, msg in files:
        if not os.path.exists(local):
            log("⚠️ 跳过不存在的 %s" % rel)
            continue
        with open(local, "rb") as f:
            content = f.read()
        url = "https://api.github.com/repos/%s/contents/%s" % (REPO, rel)
        sha = None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as resp:
                sha = json.load(resp).get("sha")
        except Exception:
            sha = None
        body = {"message": msg,
                "content": base64.b64encode(content).decode(), "branch": "main"}
        if sha:
            body["sha"] = sha
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=H, method="PUT")
        with urllib.request.urlopen(req, timeout=120) as resp:
            r = json.load(resp)
        log("✅ 已推 main: %s (commit %s)" % (rel, (r.get("commit") or {}).get("sha", "")[:8]))


if __name__ == "__main__":
    main()
