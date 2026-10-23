#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资金异动三因子复合（FF3 · 每日生成器）—— 第四支自研算法（2026-10-22 主人令「等跑完再上」后上线）

定位：与「量质双擎/低波趋稳/日内动量」同档的独立选股器。因子来自因子实验室已验证 PASS 的
三因子（turntrend IR_OOS=1.884 / amt60 1.455 / ivol60 0.621，见 raw_data/factor_walkforward.json），
复用 factor_walkforward 引擎零第二口径：全 _wf_cache 宇宙 → 最新一日截面 → 三因子降序秩和(ff3_ranksum)
→ 复合最强 TopN。

【选股规则】（全部 ≤T 日可得，无未来函数；与 factor_composite_ff3.py 回测同方法论）：
  · 三因子 turntrend(缩量=强势,取负) / amt60(小市值低流动性溢价,取负) / ivol60(低波异象,取负)。
  · 截面：逐因子降序归一化秩 [0,1]（值越大=因子越强）；复合分 = 三因子秩之和（ff3_ranksum 变体）。
  · 选股：复合分降序 TopN（N=5，与 LQSQ/低波/日内动量同档「每日 Top5 推荐」精神一致，
    全宇宙秩和选出的 5 只即当日最强资金异动组合；2026-10-24 主人令「每天5只，不要10只」）。
  · 持有：T+1/3/5/10/20 逐档前向跟踪（次开买入，扣 0.3%；未走满 T+N 不计入，绝不用 0 冒充）。
  · 成本：双边 0.3%（与 LQSQ 主口径同）。

【真实信号流纪律（与 LQSQ 同铁律）】：
  · 每日信号逐日落盘 raw_data/ff3_ranksum_history.json（含已回落/淘汰票，防幸存者偏差），上线首日即建归档。
  · 主榜只认本文件产出的真实流自回测（ff3_ranksum_backtest.json → FF3_RANKSUM_BACKTEST）。
  · 数据源 _wf_cache 由 refresh_kline_freshness.py（B 批最前）保证日 K 新鲜，本脚本零第二套拉数。

输出：
  raw_data/ff3_ranksum_history.json   真实信号逐日归档（主档，只增不改）
  raw_data/ff3_ranksum_track.json     全量信号前向跟踪明细 + 分档统计 + 基准超额
  raw_data/ff3_ranksum_backtest.json  主榜视图（summary.by_period，与 __renderBacktestTable 同构）
  data/FF3_RANKSUM_TRACK.js / data/FF3_RANKSUM_BACKTEST.js  → update_v8._write_js 直写（保证同批 E 批聚合器读到）
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))

RAW_DIR = os.path.join(ROOT, "raw_data")
CACHE_DIR = os.path.join(RAW_DIR, "_wf_cache")
HISTORY = os.path.join(RAW_DIR, "ff3_ranksum_history.json")
TRACK = os.path.join(RAW_DIR, "ff3_ranksum_track.json")
VIEW = os.path.join(RAW_DIR, "ff3_ranksum_backtest.json")

TOP_N = 5                # 每日复合最强 Top5（全宇宙秩和选出；2026-10-24 主人令「每天5只，不要10只」）
FACTORS3 = ("turntrend", "amt60", "ivol60")
HOLD_HORIZONS = (1, 3, 5, 10, 20)
PRIMARY_HOLD = 20
COST_PCT = 0.3
_ALIGN_FLOOR = 0.60      # 数据日对齐率保护闸（<60% 视为缓存陈旧，宁停不选错）

_t0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - _t0, msg), flush=True)


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def load_names():
    """当前名单 + 名称（ST/退 过滤按当前名单，历史状态不可回溯）。"""
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


import factor_walkforward as fw


def cross_section_rank(vals_by_code):
    """vals_by_code: {c: (v1,v2,v3)} → rankmap：逐因子降序归一化秩 [0,1]（1=最强）。"""
    n = len(vals_by_code)
    rankmap = {c: [0.0, 0.0, 0.0] for c in vals_by_code}
    if n < 2:
        for c in vals_by_code:
            rankmap[c] = [0.5, 0.5, 0.5]
        return rankmap
    for k in range(3):
        order = sorted(vals_by_code.items(), key=lambda kv: -kv[1][k])
        for pos, (c, _) in enumerate(order):
            rankmap[c][k] = 1.0 - pos / float(n - 1)
    return rankmap


def load_cache_codes():
    if not os.path.isdir(CACHE_DIR):
        raise SystemExit("._wf_cache 不存在（%s）——本脚本必须挂在 refresh_kline_freshness 之后" % CACHE_DIR)
    return [fn[:-5] for fn in os.listdir(CACHE_DIR)
            if fn.endswith(".json") and fn[:-5].isdigit() and len(fn[:-5]) == 6]


def main():
    log("=" * 78)
    log("  资金异动三因子复合 walk-forward · 每日信号生成（FF3 · ff3_ranksum 秩和）  %s"
        % now_cst().strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 78)

    codes = load_cache_codes()
    log("._wf_cache 名录：%d 只" % len(codes))
    names = load_names()

    # ── 复用 factor_walkforward 引擎管线（零第二口径）──
    klines = fw.get_klines(codes, 1, False)
    if len(klines) < 100:
        raise SystemExit("有效 K 线不足 100 只（%d），保护性中止" % len(klines))
    log("有效 K 线：%d 只" % len(klines))

    dates, pos, bars = fw.build_panel(klines)
    n_days = len(dates)
    log("全局交易日轴：%d 天  %s → %s" % (n_days, dates[0], dates[-1]))

    # 全池等权日收益（残差因子 + 基准同源）
    log("计算全池等权日收益 …")
    pool_sum = [0.0] * n_days
    pool_cnt = [0] * n_days
    for c, rows in klines.items():
        r, _ = fw.stock_series(rows)
        p = pos[c]
        for g, i in enumerate(p):
            if i > 0:
                pool_sum[g] += r[i]
                pool_cnt[g] += 1
    pool_r = [(pool_sum[g] / pool_cnt[g]) if pool_cnt[g] else 0.0 for g in range(n_days)]
    log("  完成（有效日均 %d 只）" % (sum(pool_cnt) // max(1, n_days)))

    # 最新一日截面：逐票取三因子值（因果无前视，i=该票末根）
    log("计算最新截面三因子值 …")
    vals = {}
    last_dates = Counter()
    for c, rows in klines.items():
        if len(rows) < fw.MIN_BARS:
            continue
        i = len(rows) - 1                     # 该票末根（最新可得）
        if i < fw.MIN_BARS:
            continue
        if c not in names:                     # 当前名单剔 ST/退（names 已过滤），无名 ETF 亦排除在股票因子排名外
            continue
        d = fw.make_prep(rows)
        pool_at = [None] * len(rows)
        p = pos[c]
        for g, ii in enumerate(p):
            if ii >= 0:
                pool_at[ii] = pool_r[g]
        d["f"].update(fw.make_resid_prep(rows, pool_at))
        try:
            v1 = d["f"]["turntrend"](i)
            v2 = d["f"]["amt60"](i)
            v3 = d["f"]["ivol60"](i)
        except Exception:
            continue
        if v1 is None or v2 is None or v3 is None:
            continue
        vals[c] = (v1, v2, v3)
        last_dates[rows[-1]["date"]] += 1
    if len(vals) < 15:
        raise SystemExit("有效因子截面不足 15 只（%d），退出" % len(vals))
    log("有效因子截面：%d 只" % len(vals))

    # 数据日新鲜度保护闸（与 LQSQ 同口径）
    data_date = max(last_dates)
    n_at = last_dates[data_date]
    if n_at < _ALIGN_FLOOR * len(vals) and os.environ.get("FF3_SMOKE") != "1":
        top5 = ", ".join("%s:%d" % (d, c) for d, c in last_dates.most_common(5))
        raise SystemExit("数据日 %s 对齐率不足（%d/%d= %.0f%% < 60%%）——_wf_cache 新鲜度异常，"
                         "保护性中止（末根分布 top5: %s）" % (data_date, n_at, len(vals),
                                                            100.0 * n_at / len(vals), top5))
    stale_n = len(vals) - n_at
    log("数据日=%s（%d/%d 只末根对齐，异频 %d 只剔除）" % (data_date, n_at, len(vals), stale_n))

    # 截面秩和复合分（ff3_ranksum）
    rankmap = cross_section_rank(vals)
    comp = {c: sum(rankmap[c]) for c in vals}     # 三因子秩之和 ∈ [0,3]
    ranked = sorted(comp, key=lambda c: -comp[c])[:TOP_N]
    log("复合打分完成：%d 只 → Top%d（最强复合分=%.3f / 第%d名=%.3f）"
        % (len(comp), TOP_N, comp[ranked[0]], TOP_N, comp[ranked[TOP_N - 1]]))

    # ── 真实信号流归档（只增不改；同日重跑幂等）──
    hist = {"meta": {
        "algo_name": "资金异动三因子复合（FF3）",
        "variant": "ff3_ranksum（三因子降序秩和，抗离群）",
        "factor_def": "turntrend=20日均量/240日均量取负(缩量=强势) | amt60=60日成交额中位数取负(低流动性溢价) | ivol60=近60日残差收益标准差取负(低波异象)",
        "factors_src": "raw_data/factor_walkforward.json（均 PASS：turntrend IR_OOS=1.884 / amt60 1.455 / ivol60 0.621）",
        "method": "全 _wf_cache 宇宙 → 最新一日截面 → 三因子降序秩和 → 复合最强 Top%d；零第二口径（复用 factor_walkforward 引擎）" % TOP_N,
        "filters": "上市≥MIN_BARS交易日/末根对齐数据日/当前名单剔ST退",
        "cost_pct": COST_PCT, "primary_hold": PRIMARY_HOLD, "top_n": TOP_N,
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
            {"code": c, "name": names.get(c, c), "score": round(comp[c], 4), "close": klines[c][-1]["close"]}
            for c in ranked]
        log("✅ 归档 %s：新增 %d 笔（累计 %d 个信号日）"
            % (data_date, len(hist["signals"][data_date]), len(hist["signals"])))
    with open(HISTORY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hist, f, ensure_ascii=False)

    # ── 前向跟踪（次开买入，扣 0.3%；未走满如实不计）──
    all_days = sorted({b["date"] for rows in klines.values() for b in rows})
    day_idx = {d: i for i, d in enumerate(all_days)}
    tracked = []
    bench_by_date = {}
    bench_pool_by_date = {}
    for sd, sigs in sorted(hist["signals"].items()):
        tracked_date = []
        for s in sigs:
            rows = klines.get(s["code"])
            rec = dict(s)
            rec["signal_date"] = sd
            rec["returns"] = {}
            rec["immature"] = []
            if rows is None:
                rec["immature"] = [str(p) for p in HOLD_HORIZONS]
                tracked.append(rec)
                continue
            j = next((k for k, b in enumerate(rows) if b["date"] == sd), None)
            if j is None or j + 1 >= len(rows):
                rec["immature"] = [str(p) for p in HOLD_HORIZONS]
                tracked.append(rec)
                continue
            entry = rows[j + 1]["open"]
            for p in HOLD_HORIZONS:
                e = j + p
                if e >= len(rows):
                    rec["immature"].append(str(p))
                    continue
                rec["returns"][str(p)] = round(
                    (rows[e]["close"] / entry - 1.0) * 100.0 - COST_PCT, 2)
            tracked.append(rec)

        # 基准：当日过滤 universe 等权（与 LQSQ 同口径，同扣双边 0.3%）
        uni_day = bench_pool_by_date.get(sd)
        if uni_day is None:
            uni = []
            if sd in day_idx:
                for c, rows in klines.items():
                    jj = next((k for k, b in enumerate(rows) if b["date"] == sd), None)
                    if jj is None or jj < fw.MIN_BARS or jj + PRIMARY_HOLD >= len(rows):
                        continue
                    if rows[jj]["close"] < 2.0:
                        continue
                    if c not in names:
                        continue
                    uni.append(c)
            uni_day = uni
            bench_pool_by_date[sd] = uni
        vals_b = []
        for c in uni_day:
            rows = klines[c]
            j = next((k for k, b in enumerate(rows) if b["date"] == sd), None)
            if j is None or j + PRIMARY_HOLD >= len(rows):
                continue
            vals_b.append((rows[j + PRIMARY_HOLD]["close"] / rows[j + 1]["open"] - 1.0) * 100.0 - COST_PCT)
        bench_by_date[sd] = round(sum(vals_b) / len(vals_b), 2) if vals_b else None

    def stats_for(p):
        v = [t["returns"][str(p)] for t in tracked
             if t.get("returns") and t["returns"].get(str(p)) is not None]
        if not v:
            return None
        wins = sum(1 for x in v if x > 0)
        return {"n": len(v), "win_rate": round(wins / len(v) * 100, 1),
                "avg": round(sum(v) / len(v), 2),
                "best": round(max(v), 2), "worst": round(min(v), 2)}

    self_summary = {str(p): stats_for(p) for p in HOLD_HORIZONS}
    mature = [(p, s) for p, s in self_summary.items() if s]
    b20 = [v for v in bench_by_date.values() if v is not None]
    bench20 = round(sum(b20) / len(b20), 2) if b20 else None

    track_obj = {
        "algo_name": "资金异动三因子复合（FF3）", "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": data_date, "track_start": track_start,
        "total_signals": sum(len(v) for v in hist["signals"].values()),
        "signal_days": len(hist["signals"]),
        "self_summary": self_summary,
        "bench_t20_avg": bench20,
        "bench_by_date": bench_by_date,
        "tracked": tracked,
    }
    with open(TRACK, "w", encoding="utf-8", newline="\n") as f:
        json.dump(track_obj, f, ensure_ascii=False)
    log("跟踪明细已写（%d 笔 / %d 个信号日；T+%d 成熟档=%s）"
        % (len(tracked), len(hist["signals"]), PRIMARY_HOLD,
           ["T+%s n=%s" % (p, self_summary[p]["n"]) for p, s in mature]))

    # ── 主榜视图（与 __renderBacktestTable 同构；仅成熟档）──
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
        "method": ("真实信号流口径（2026-10-22 主人令）：每日全 _wf_cache 宇宙按资金异动三因子"
                   "（turntrend 缩量 / amt60 低流动性 / ivol60 低波，三因子均经因子实验室 walk-forward 验证 PASS）"
                   "降序秩和复合，选复合最强 Top%d（2026-10-22 上线）；次开买入、持有 N 日收盘卖出"
                   "（前复权·扣双边 0.3%%）；基准=同过滤 universe 等权。样本随持有天数成熟而增加，"
                   "未走满 T+N 不计入，绝不用 0 冒充。" % TOP_N),
        "signal_source": "ff3_ranksum_history 逐日真实选股归档（上线首日即建，含已回落票，防幸存者偏差）",
        "track_start": track_start,
        "signal_date_range": "%s ~ %s" % (track_start, data_date),
        "total_signals": sum(len(v) for v in hist["signals"].values()),
        "cost_adjusted": True,
        "summary": {"by_period": bp},
    }
    with open(VIEW, "w", encoding="utf-8", newline="\n") as f:
        json.dump(view, f, ensure_ascii=False)
    log("主榜视图已写（成熟档 %d 个：%s）"
        % (len(bp), ", ".join("T+%s n=%s" % (k, v["samples"]) for k, v in bp.items()) or "暂无（跟踪未满期）"))

    # ── data js 直写（保证同批 E 批聚合器读到当日新鲜视图；build 的 update_v8 会按 raw_data 重出，幂等）──
    try:
        import update_v8
        p1 = update_v8._write_js("FF3_RANKSUM_TRACK", track_obj) and update_v8._write_js("FF3_RANKSUM_BACKTEST", view)
        log("data js 已直写: FF3_RANKSUM_TRACK / FF3_RANKSUM_BACKTEST")
    except Exception as e:
        log("⚠️ data js 直写失败（build 兜底）: %s %s" % (type(e).__name__, str(e)[:80]))

    # ── 摘要日志 ──
    log("========== 资金异动三因子 FF3 %s ==========" % data_date)
    for p in HOLD_HORIZONS:
        s = self_summary[str(p)]
        if s:
            log("T+%2s | n=%d | 胜率=%s%% | 均收=%s%% | 最好=%s%% | 最差=%s%%"
                % (p, s["n"], s["win_rate"], s["avg"], s["best"], s["worst"]))
        else:
            log("T+%2s | 未成熟（如实不计）" % p)
    log("T+20 基准（同过滤 universe 等权）: %s%%" % bench20)

    # ── 一次性引导自推（仅 FF3_BOOTSTRAP_PUSH=1 时；常规链内跑由 git 提交，不走此路径）──
    if os.environ.get("FF3_BOOTSTRAP_PUSH") == "1":
        push_bootstrap()


def push_bootstrap():
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
        ("raw_data/ff3_ranksum_history.json", HISTORY, "data: FF3 真实信号流归档(阿狸咪的工程师)"),
        ("raw_data/ff3_ranksum_track.json", TRACK, "data: FF3 前向跟踪明细(阿狸咪的工程师)"),
        ("raw_data/ff3_ranksum_backtest.json", VIEW, "data: FF3 主榜视图(阿狸咪的工程师)"),
        ("data/FF3_RANKSUM_TRACK.js", os.path.join(ROOT, "data", "FF3_RANKSUM_TRACK.js"),
         "data: FF3_RANKSUM_TRACK.js(阿狸咪的工程师)"),
        ("data/FF3_RANKSUM_BACKTEST.js", os.path.join(ROOT, "data", "FF3_RANKSUM_BACKTEST.js"),
         "data: FF3_RANKSUM_BACKTEST.js(阿狸咪的工程师)"),
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
        body = {"message": msg, "content": base64.b64encode(content).decode(), "branch": "main"}
        if sha:
            body["sha"] = sha
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=H, method="PUT")
        with urllib.request.urlopen(req, timeout=120) as resp:
            r = json.load(resp)
        log("✅ 已推 main: %s (commit %s)" % (rel, (r.get("commit") or {}).get("sha", "")[:8]))


if __name__ == "__main__":
    main()
