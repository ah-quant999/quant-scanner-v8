#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量质双擎 · 上线前置点位重放（异常量比单因子 · 全市场 Top30 · T+20 调仓）

2026-10-11 阿狸咪的工程师（主人令「按你建议做吧」）：第一支自研算法，从因子实验室
  已验证的「异常量比（缩量=强势）」因子出发。本脚本 = 上线门槛的历史点位回放：

口径声明（写进产物，防止被当主榜）：
  · 这是【上线前置重放/replay】，不是真实信号流 —— 按 2026-10-11 铁令，真实流口径才是
    主榜唯一依据；本回放仅作「算法北极星=收益率与胜率」的上线前置验证，不进主榜。
  · 点位纪律（与 four_volume_pit_replay 同源）：因子只用 ≤T 的日 K（无未来函数）；
    T 日收盘打分 → Top30 → 次一交易日开盘买入 → T+20 收盘卖出；扣双边 0.3%。
  · 因子定义（point-in-time）：量比 r = mean(vol, 近20交易日) / mean(vol, 之前240交易日)；
    r 越小 = 越缩量 = 因子越强（与 FACTOR_LAB「当月换手率÷过去12月均值，缩量=强势」同义，
    用成交量代换手率——同一股票内比值对流通股本变化近似不敏感）。
  · 选股过滤（全部 ≤T 可得）：上市≥261 交易日；当日未停牌；近20日每日均未停牌；
    收盘价≥2元（仙股过滤）；流动性代理=近20日日均 vol×close ≥ 5000万元；
    按当前名单剔除 ST/退市标记股（历史 ST 状态不可回溯，残差如实标注）。
  · ROE 复合因子【不参与本回放】：财务数据的 point-in-time 历史不可回溯（用当前快照
    回放=未来函数）。上线版在真实信号流中以当日可得财报叠 ROE 过滤；本回放只验证量因子。
  · 基准：同一过滤 universe 的等权平均（同入场/出场/无成本），报告超额。
  · 已知残差（如实）：① 清单=当前上市清单，窗口内退市股缺失；② 前复权=当前时点因子；
    ③ 成交额用 vol×close 代理（非真实 VWAP 成交额）；④ ST 按当前名单近似。

产出：raw_data/lqsq_pit_replay.json + Contents API 推 main（不触碰 index.html / 主榜）。

抗抖动三件套（skill v8-baostock-longrun-resilience 同规）：单只隔离 try/except、
逐只落盘缓存（raw_data/pit_replay_work/，可续跑）、心跳 flush 防 SILENCE_KILL。
"""
import os
import sys
import json
import time
import base64
import urllib.request
from datetime import datetime, timezone, timedelta

import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "algorithms"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scanner import fetch_a_daily  # noqa: E402

REPO = "ah-quant999/quant-scanner-v8"
RAW_DIR = os.path.join(ROOT, "raw_data")
WORK_DIR = os.path.join(RAW_DIR, "pit_replay_work")
OUT_JSON = os.path.join(RAW_DIR, "lqsq_pit_replay.json")
CACHE_VER = "LQSQ_V1_B700"    # 改口径必须升版本，否则旧缓存被当已算跳过
BARS = 700                    # 240 基线 + 20 近窗 + 20 前向 + 余量；可覆盖 ~2.5 年回放窗口
RECENT_N = 20                 # 「当月」= 近 20 交易日
BASELINE_N = 240              # 「过去 12 月」= 之前 240 交易日（不含近窗）
MIN_HISTORY = 261             # 上市最少交易日（20+240+1）
HOLD_PERIODS = [5, 10, 20]    # T+20 为主档
TOP_N = 30                    # 每次调仓选 Top30
REBALANCE_STEP = 20           # 每 20 交易日调仓（与持有期一致，满仓轮动口径）
COST_PCT = 0.3                # 双边 0.3%
MIN_PRICE = 2.0               # 仙股过滤
MIN_TURNOVER_YUAN = 50_000_000  # 流动性代理下限：近20日日均 vol×close ≥ 5000 万元

_T0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - _T0, msg), flush=True)


def load_universe():
    """全 A 清单：raw_data/stock_names.json 优先，缺失兜底 akshare（同 four_volume 管线）。"""
    p = os.path.join(RAW_DIR, "stock_names.json")
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            names = json.load(f).get("data") or []
        for s in names:
            fc = s.get("full_code") or ""
            nm = s.get("name") or ""
            if not isinstance(fc, str) or not fc.startswith(("sh", "sz")):
                continue
            code6 = fc[2:]
            if not code6.isdigit():
                continue
            out.append({"code": code6, "name": nm or code6})
    except Exception as e:
        log("⚠️ stock_names.json 不可用: %s %s" % (type(e).__name__, str(e)[:80]))
    if len(out) >= 3000:
        out = [u for u in out if "ST" not in u["name"].upper() and "退" not in u["name"]]
        log("清单加载：全 A %d 只（剔除当前 ST/退标记后）" % len(out))
        return out
    log("stock_names.json 不足 3000 只（%d），兜底 akshare stock_info_a_code_name" % len(out))
    import akshare as ak
    df = ak.stock_info_a_code_name()
    for _, row in df.iterrows():
        code6 = str(row["code"])
        nm = str(row["name"])
        if not code6.isdigit():
            continue
        if not (code6.startswith(("6", "0", "3"))):
            continue  # bj / 其它
        if "ST" in nm.upper() or "退" in nm:
            continue
        out.append({"code": code6, "name": nm})
    log("清单加载：全 A %d 只（akshare 兜底，剔除 ST/退）" % len(out))
    return out


def load_or_fetch_bars(item):
    """逐只日 K：本地缓存优先（可续跑），缺失才 fetch_a_daily。"""
    code = item["code"]
    cpath = os.path.join(WORK_DIR, "bars_%s.json" % code)
    if os.path.exists(cpath):
        try:
            with open(cpath, encoding="utf-8") as f:
                c = json.load(f)
            if c.get("ver") == CACHE_VER:
                return c
        except Exception:
            pass
    try:
        df = fetch_a_daily(code, bars=BARS)
        if df is None or len(df) < 60:
            return None
        rows = {
            "ver": CACHE_VER,
            "code": code,
            "date": [str(x) for x in df["date"].tolist()],
            "open": [round(float(x), 4) for x in df["open"]],
            "close": [round(float(x), 4) for x in df["close"]],
            "vol": [round(float(x), 2) for x in df["volume"]],
        }
        with open(cpath, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, ensure_ascii=False)
        return rows
    except Exception as e:
        log("⚠️ 单只异常跳过 %s: %s %s" % (code, type(e).__name__, str(e)[:80]))
        return None


def main():
    os.makedirs(WORK_DIR, exist_ok=True)
    uni = load_universe()
    if len(uni) < 3000:
        raise SystemExit("清单不足 3000 只，保护性中止（universe=%d）" % len(uni))

    # ── 第 1 步：逐只拉日 K（可续跑缓存） ──
    bars_map = {}
    n_done = 0
    for item in uni:
        r = load_or_fetch_bars(item)
        n_done += 1
        if r is not None:
            bars_map[item["code"]] = r
        if n_done % 100 == 0:
            log("K线进度 %d/%d（有效 %d）" % (n_done, len(uni), len(bars_map)))

    lens = sorted(len(r["date"]) for r in bars_map.values())
    med = lens[len(lens) // 2] if lens else 0
    log("K线长度中位数=%d（P10=%d / P90=%d）" % (med, lens[max(0, len(lens)//10)], lens[min(len(lens)-1, len(lens)*9//10)]))
    if med < 400:
        raise SystemExit("K线长度中位数 %d < 400，数据源疑似不支持 %d 根，保护性中止" % (med, BARS))

    # ── 第 2 步：交易日历（全市场并集） ──
    all_dates = set()
    for r in bars_map.values():
        all_dates.update(r["date"])
    days = sorted(all_dates)
    log("交易日历：%s ~ %s（%d 个交易日）" % (days[0], days[-1], len(days)))

    # date -> {code: idx}
    idx_by_day = {}
    for code, r in bars_map.items():
        for j, d in enumerate(r["date"]):
            idx_by_day.setdefault(d, {})[code] = j

    # ── 第 3 步：调仓日（每 20 交易日一个，留足历史与前向） ──
    rebal_days = [d for i, d in enumerate(days) if i >= MIN_HISTORY and i % REBALANCE_STEP == 0
                  and i + REBALANCE_STEP <= len(days) - 1]
    if len(rebal_days) < 5:
        raise SystemExit("可用调仓日不足 5 个（%d），保护性中止" % len(rebal_days))
    log("调仓日 %d 个：%s ~ %s（每 %d 交易日）" % (
        len(rebal_days), rebal_days[0], rebal_days[-1], REBALANCE_STEP))

    # ── 第 4 步：逐调仓日打分选股（因子只用 ≤T） ──
    name_map = {u["code"]: u["name"] for u in uni}
    picks = []   # {code,name,T,ratio,close}
    bench_pool = {}  # T -> [codes]（过滤后 universe，作基准）
    for ti, T in enumerate(rebal_days, 1):
        scored = []
        for code, r in bars_map.items():
            j = idx_by_day.get(T, {}).get(code)
            if j is None or j < MIN_HISTORY:
                continue
            close = r["close"]; vol = r["vol"]
            if close[j] < MIN_PRICE or vol[j] <= 0:
                continue
            recent = vol[j - RECENT_N + 1: j + 1]
            base = vol[j - RECENT_N - BASELINE_N + 1: j - RECENT_N + 1]
            if len(recent) < RECENT_N or len(base) < BASELINE_N:
                continue
            if any(v <= 0 for v in recent):
                continue  # 近月有停牌
            liq = sum(v * c for v, c in zip(recent, close[j - RECENT_N + 1: j + 1])) / RECENT_N
            if liq < MIN_TURNOVER_YUAN:
                continue
            ratio = (sum(recent) / RECENT_N) / (sum(base) / BASELINE_N)
            scored.append((ratio, code))
        scored.sort()
        bench_pool[T] = [c for _, c in scored]
        for ratio, code in scored[:TOP_N]:
            r = bars_map[code]
            picks.append({"code": code, "name": name_map.get(code, code), "signal_date": T,
                          "ratio": round(ratio, 4), "close": r["close"][idx_by_day[T][code]]})
        log("调仓日 %d/%d %s：过滤后 %d 只 → Top%d（min_ratio=%.3f）" % (
            ti, len(rebal_days), T, len(scored), TOP_N, scored[0][0] if scored else -1))

    # ── 第 5 步：前向收益（次开买入，扣 0.3%）+ 基准 ──
    day_index = {d: i for i, d in enumerate(days)}

    def fwd(code, T, p, with_cost):
        r = bars_map[code]
        j = idx_by_day[T][code]
        e = j + p
        if j + 1 >= len(r["date"]) or e >= len(r["date"]):
            return None
        net = (r["close"][e] / r["open"][j + 1] - 1.0) * 100.0
        return round(net - (COST_PCT if with_cost else 0.0), 2)

    for s in picks:
        s["returns"] = {str(p): fwd(s["code"], s["signal_date"], p, True) for p in HOLD_PERIODS}
    bench = {}  # T -> {p: mean}
    for T, codes in bench_pool.items():
        bench[T] = {}
        for p in HOLD_PERIODS:
            vals = [fwd(c, T, p, False) for c in codes]
            vals = [v for v in vals if v is not None]
            bench[T][str(p)] = round(sum(vals) / len(vals), 2) if vals else None

    # ── 第 6 步：统计 ──
    def stats_for(sub, p):
        vals = [s["returns"][str(p)] for s in sub if s["returns"].get(str(p)) is not None]
        if not vals:
            return {"n": 0, "win_rate": None, "avg": None, "best": None, "worst": None}
        wins = sum(1 for v in vals if v > 0)
        return {"n": len(vals), "win_rate": round(wins / len(vals) * 100, 1),
                "avg": round(sum(vals) / len(vals), 2),
                "best": round(max(vals), 2), "worst": round(min(vals), 2)}

    by_period = {}
    for p in HOLD_PERIODS:
        st = stats_for(picks, p)
        bv = [bench[T][str(p)] for T in rebal_days if bench[T].get(str(p)) is not None]
        st["bench_avg"] = round(sum(bv) / len(bv), 2) if bv else None
        st["excess"] = (round(st["avg"] - st["bench_avg"], 2)
                        if st["avg"] is not None and st["bench_avg"] is not None else None)
        by_period[str(p)] = st

    per_rebalance = []
    for T in rebal_days:
        sub = [s for s in picks if s["signal_date"] == T]
        row = {"date": T, "n": len(sub)}
        for p in HOLD_PERIODS:
            row["top%d_avg" % p] = stats_for(sub, p)["avg"]
            row["bench_avg" if p == 20 else "bench_avg_%d" % p] = bench[T].get(str(p))
        per_rebalance.append(row)

    by_year = {}
    for y in sorted(set(T[:4] for T in rebal_days)):
        sub = [s for s in picks if s["signal_date"].startswith(y)]
        by_year[y] = {str(p): stats_for(sub, p) for p in HOLD_PERIODS}

    out = {
        "algo_name": "量质双擎（LQSQ）",
        "method": "launch_gate_pit_replay",
        "caliber": "上线前置重放（非真实信号流）：异常量比单因子 r=mean(近20日vol)/mean(之前240日vol)，"
                   "r 越小越缩量=越强；T 收盘打分全市场过滤后 Top30，次开买入 T+20 收盘卖出，扣双边 0.3%；"
                   "基准=同过滤 universe 等权（无成本）。按 2026-10-11 铁令不进主榜，仅作上线前置验证。",
        "roe_note": "ROE 复合因子不参与本回放（财务 point-in-time 不可回溯，当前快照回放=未来函数）；"
                    "上线版在真实信号流中以当日可得财报叠加 ROE 过滤。",
        "known_residual": [
            "股票清单=当前上市名单，窗口内退市股缺失（少量幸存者残差）",
            "前复权=当前时点复权因子",
            "成交额用 vol×close 代理（非 VWAP 成交额）",
            "ST/退市按当前名单近似剔除，历史状态不可回溯",
        ],
        "filters": {"min_history_bars": MIN_HISTORY, "min_price": MIN_PRICE,
                    "min_daily_turnover_yuan_proxy": MIN_TURNOVER_YUAN,
                    "no_suspension_recent20": True},
        "factor_def": "r = mean(vol[近20]) / mean(vol[之前240])；升序取 Top%d（最缩量）" % TOP_N,
        "bars_range": [days[0], days[-1]],
        "rebalance_dates": rebal_days,
        "n_rebalances": len(rebal_days),
        "total_picks": len(picks),
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "by_period": by_period,
        "per_rebalance": per_rebalance,
        "by_year": by_year,
        "picks": picks,
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False)
    log("产物已写 %s（%d 字节）" % (OUT_JSON, os.path.getsize(OUT_JSON)))

    log("========== 量质双擎 上线前置重放（%d 次调仓 × Top%d，%d 笔）=========="
        % (len(rebal_days), TOP_N, len(picks)))
    log("持有期 | 样本 | 胜率 | 均收 | 基准 | 超额")
    for p in HOLD_PERIODS:
        st = by_period[str(p)]
        log("T+%2d | %d | %s%% | %s%% | %s%% | %s%%" % (
            p, st["n"], st["win_rate"], st["avg"], st["bench_avg"], st["excess"]))
    log("分年 T+20：")
    for y, ys in by_year.items():
        st = ys.get("20") or {}
        log("  %s | n=%s 胜率=%s%% 均收=%s%%" % (y, st.get("n"), st.get("win_rate"), st.get("avg")))

    push_result(out)
    log("全部完成")


def push_result(payload):
    """Contents API 推 raw_data/lqsq_pit_replay.json（先取 sha 再 PUT，防覆盖）。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log("⚠️ 无 GITHUB_TOKEN，跳过推送（产物仅留在 runner 本地）")
        return
    url = "https://api.github.com/repos/%s/contents/%s" % (REPO, "raw_data/lqsq_pit_replay.json")
    H = {"Authorization": "Bearer " + token,
         "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    sha = None
    try:
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=60) as resp:
            sha = json.load(resp).get("sha")
    except Exception:
        sha = None
    body = {
        "message": "data: 量质双擎 上线前置点位重放(launch-gate pit-replay, 阿狸咪的工程师)",
        "content": base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(),
        "branch": "main",
    }
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=H, method="PUT")
    with urllib.request.urlopen(req, timeout=120) as resp:
        r = json.load(resp)
    log("✅ 已推 main: %s (commit %s)" % ("raw_data/lqsq_pit_replay.json",
                                          (r.get("commit") or {}).get("sha", "")[:8]))


if __name__ == "__main__":
    main()
