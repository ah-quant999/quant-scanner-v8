#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 · 点位重放补算（2026-08-03 ~ 2026-09-11 真实流空窗期参考数据）

2026-10-11 阿狸咪的工程师（主人令：四量真实流归档 9-14 才建，8 月初上线~9-13 空窗
  期的「当日活跃池」实时快照没有留档 ⇒ 真实信号流永久缺失；本脚本做「点位重放」近似重建）：

口径声明（写进产物，防止被当主榜）：
  · 这是【重放/replay】，不是真实信号流 —— 按主人 2026-10-11 铁令「所有回测只认真实信号流口径，
    历史规则回放禁作主榜/上下架依据」，本产物仅作 8 月那段行情的参考对照，不进 BACKTEST_ALL_ALGOS 主榜。
  · 与旧回放（FOUR_VOLUME_BACKTEST）的本质区别：活跃池按「当日成交量·分板块前100」
    【点位重建】（当日真实截面），修掉「用当前活跃股池回放 5 年」的幸存者偏差。
  · 指标只用 ≤T 的日 K（无未来函数）；信号 = T 日收盘触发的 XG；
    入场 = 次一交易日开盘（与 backtest_four_volume 2026-09-13 口径一致）；
    扣双边成本 0.3%；未走满持有期如实标 immature。
  · 取数路径与实盘完全一致：scanner.fetch_a_daily（GITHUB_ACTIONS 下自动走 GTimg 前复权）。
  · 已知残差（如实）：① 股票清单用当前 stock_names.json → 窗口内退市股缺失（少量幸存者残差）；
    ② 前复权为「当前时点」复权因子，与 8 月当时略有差异；③ 实时盘中池 vs 收盘后重排池有边缘差异。

产出：raw_data/four_volume_pit_replay.json + Contents API 推 main（不触碰 index.html / 主榜）。

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

from scanner import fetch_a_daily, DAILY_BARS  # noqa: E402
from strategy_four_volume import calc_siliang_ultimate_signal  # noqa: E402

REPO = "ah-quant999/quant-scanner-v8"
RAW_DIR = os.path.join(ROOT, "raw_data")
WORK_DIR = os.path.join(RAW_DIR, "pit_replay_work")
OUT_JSON = os.path.join(RAW_DIR, "four_volume_pit_replay.json")
CACHE_VER = "PIT_V1"          # 改口径必须升版本，否则旧缓存被当已算跳过
SIGNAL_START = "2026-08-03"   # 算法 8 月初上线（FOUR_VOLUME.js 首次 update_time 8-07，模块注释 8-05/08-07）
SIGNAL_END = "2026-09-11"     # 真实流归档起点 9-14 的前一个交易日（9-12/13 为周末）
HOLD_PERIODS = [1, 3, 5, 10, 20, 30, 45, 60, 75, 90, 180, 250]  # 同源 HOLD_LADDER + [1,3]
COST_PCT = 0.3                # 双边万分之1.5×2
TOP_PER_BOARD = 100           # 与 scan_four_volume(top_cy=100, top_kc=100, top_zb=100) 对齐
BARS = max(280, DAILY_BARS)

_T0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - _T0, msg), flush=True)


def board_of(code6):
    if code6.startswith(("300", "301")):
        return "cyb"
    if code6.startswith(("688", "689")):
        return "kcb"
    return "zb"


def load_universe():
    """全 A 清单：优先 raw_data/stock_names.json（每日元数据维护产出）；
    缺失/不足时兜底 akshare stock_info_a_code_name（当前上市清单，退市股缺失如实标注）。"""
    p = os.path.join(RAW_DIR, "stock_names.json")
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            names = json.load(f).get("data") or []
        for s in names:
            fc = s.get("full_code") or ""
            if not isinstance(fc, str) or not fc.startswith(("sh", "sz")):
                continue
            code6 = fc[2:]
            if not code6.isdigit():
                continue
            out.append({"code": code6, "name": s.get("name") or code6, "board": board_of(code6)})
    except Exception as e:
        log("⚠️ stock_names.json 不可用: %s %s" % (type(e).__name__, str(e)[:80]))
    if len(out) >= 3000:
        log("清单加载：全 A %d 只（stock_names.json）" % len(out))
        return out
    log("stock_names.json 不足 3000 只（%d），兜底 akshare stock_info_a_code_name" % len(out))
    import akshare as ak
    df = ak.stock_info_a_code_name()
    for _, row in df.iterrows():
        code6 = str(row["code"])
        if not code6.isdigit():
            continue
        if code6.startswith(("688", "689", "60")):
            pass  # sh
        elif code6.startswith(("000", "001", "002", "003", "300", "301")):
            pass  # sz
        else:
            continue  # bj / 其它
        out.append({"code": code6, "name": str(row["name"]), "board": board_of(code6)})
    log("清单加载：全 A %d 只（akshare 兜底）" % len(out))
    return out


def load_or_fetch_bars(item):
    """逐只日 K：本地缓存优先（可续跑），缺失才 fetch_a_daily。返回 df 兼容 dict 或 None。"""
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
            "high": [round(float(x), 4) for x in df["high"]],
            "low": [round(float(x), 4) for x in df["low"]],
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
    for i, item in enumerate(uni):
        r = load_or_fetch_bars(item)
        n_done += 1
        if r is not None:
            bars_map[item["code"]] = r
        if n_done % 50 == 0:
            log("K线进度 %d/%d（命中缓存+%s新拉，有效 %d）" % (n_done, len(uni), "", len(bars_map)))

    # ── 第 2 步：交易日历（全市场并集） ──
    all_dates = set()
    for r in bars_map.values():
        all_dates.update(r["date"])
    days = sorted(all_dates)
    log("交易日历：%s ~ %s（%d 个交易日）" % (days[0], days[-1], len(days)))

    # ── 第 3 步：窗口内每日活跃池点位重建（当日成交量·分板块前100） ──
    win_days = [d for d in days if SIGNAL_START <= d <= SIGNAL_END]
    if not win_days:
        raise SystemExit("信号窗口无交易日（%s~%s），保护性中止" % (SIGNAL_START, SIGNAL_END))
    # 预索引：date -> {code: idx}
    idx_by_day = {}
    for code, r in bars_map.items():
        for j, d in enumerate(r["date"]):
            idx_by_day.setdefault(d, {})[code] = j
    uni_by_day = {}
    board_map = {u["code"]: u["board"] for u in uni}
    for T in win_days:
        holders = idx_by_day.get(T, {})
        per_board = {"cyb": [], "kcb": [], "zb": []}
        for code, r in bars_map.items():
            j = holders.get(code)
            if j is None:
                continue
            v = r["vol"][j]
            if v and v > 0:
                per_board[board_map.get(code, "zb")].append((v, code))
        pool = set()
        for b, lst in per_board.items():
            lst.sort(reverse=True)
            pool.update(c for _, c in lst[:TOP_PER_BOARD])
        uni_by_day[T] = pool
    log("活跃池点位重建完成：%d 个交易日，日均池 %d 只" % (
        len(win_days), sum(len(v) for v in uni_by_day.values()) // max(len(win_days), 1)))

    # ── 第 4 步：信号检测（指标只用 ≤T 的 K 线） ──
    name_map = {u["code"]: u["name"] for u in uni}
    signals = []  # {code,name,T,close,components}
    n_codes_ind = 0
    for k, (code, r) in enumerate(bars_map.items(), 1):
        try:
            df = pd.DataFrame({
                "date": r["date"], "open": r["open"], "high": r["high"],
                "low": r["low"], "close": r["close"], "volume": r["vol"],
            })
            ind = calc_siliang_ultimate_signal(df)
            xg = ind["四量终极_XG"].fillna(False).values
            dates = r["date"]
            if k % 300 == 0:
                log("信号检测进度 %d/%d（命中 %d 笔）" % (k, len(bars_map), len(signals)))
            n_codes_ind += 1
            for T in win_days:
                if code not in uni_by_day[T]:
                    continue
                # T 必须是该股的最后一根已有 K 线（等价实盘「末根 XG」）
                j = idx_by_day[T].get(code)
                if j is None or j != len(dates) - 1:
                    continue
                if not bool(xg[j]):
                    continue
                signals.append({
                    "code": code, "name": name_map.get(code, code), "signal_date": T,
                    "close": r["close"][j],
                    "yzc": bool(ind["四量终极_YZC"].values[j]),
                    "jg": bool(ind["四量终极_JG"].values[j]),
                    "xc": bool(ind["四量终极_XC"].values[j]),
                    "four": bool(ind["四量终极_FOUR"].values[j]),
                })
        except Exception as e:
            log("⚠️ 指标单只异常跳过 %s: %s %s" % (code, type(e).__name__, str(e)[:80]))
    log("信号检测完成：候选指标 %d 只，命中 %d 笔（%d 个信号日）" % (
        n_codes_ind, len(signals), len(set(s["signal_date"] for s in signals))))

    # ── 第 5 步：前向收益（次开买入，扣 0.3% 双边） ──
    day_index = {d: i for i, d in enumerate(days)}
    for s in signals:
        r = bars_map[s["code"]]
        j = idx_by_day[s["signal_date"]][s["code"]]
        s["returns"] = {}
        s["immature"] = []
        if j + 1 >= len(r["date"]):
            s["returns"] = {str(p): None for p in HOLD_PERIODS}
            s["immature"] = [str(p) for p in HOLD_PERIODS]
            continue
        entry = r["open"][j + 1]
        for p in HOLD_PERIODS:
            e = j + p
            if e >= len(r["date"]):
                s["returns"][str(p)] = None
                s["immature"].append(str(p))
                continue
            net = (r["close"][e] / entry - 1.0) * 100.0 - COST_PCT
            s["returns"][str(p)] = round(net, 2)

    # ── 第 6 步：统计 ──
    def stats_for(signals_subset, p):
        vals = [s["returns"][str(p)] for s in signals_subset if s["returns"].get(str(p)) is not None]
        immature = sum(1 for s in signals_subset if str(p) in s["immature"])
        if not vals:
            return {"n": 0, "immature": immature, "win_rate": None, "avg": None,
                    "best": None, "worst": None}
        wins = sum(1 for v in vals if v > 0)
        return {"n": len(vals), "immature": immature,
                "win_rate": round(wins / len(vals) * 100, 1),
                "avg": round(sum(vals) / len(vals), 2),
                "best": round(max(vals), 2), "worst": round(min(vals), 2)}

    by_period = {str(p): stats_for(signals, p) for p in HOLD_PERIODS}
    aug = [s for s in signals if s["signal_date"].startswith("2026-08")]
    sep = [s for s in signals if s["signal_date"].startswith("2026-09")]
    by_month = {
        "2026-08": {str(p): stats_for(aug, p) for p in (1, 3, 5, 10, 20)},
        "2026-09": {str(p): stats_for(sep, p) for p in (1, 3, 5, 10, 20)},
    }

    out = {
        "method": "pit_replay_reference",
        "caliber": "重放参考（非真实信号流）：活跃池按「当日成交量·分板块前100」点位重建，"
                   "指标只用<=T日K，信号日次开买入，扣双边0.3%；未走满标 immature。"
                   "按 2026-10-11 铁令不进主榜、不作上下架依据，仅作 8 月空窗期参考对照。",
        "known_residual": [
            "股票清单=当前 stock_names.json，窗口内退市股缺失（少量幸存者残差）",
            "前复权=当前时点因子，与 8 月当时略有差异",
            "实时盘中池 vs 收盘后重排池有边缘差异",
        ],
        "signal_window": [SIGNAL_START, SIGNAL_END],
        "bars_range": [days[0], days[-1]],
        "universe_size": len(uni),
        "bars_valid": len(bars_map),
        "signal_days": len(set(s["signal_date"] for s in signals)),
        "total_signals": len(signals),
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "by_period": by_period,
        "by_month": by_month,
        "signals": signals,
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False)
    log("产物已写 %s（%d 字节）" % (OUT_JSON, os.path.getsize(OUT_JSON)))

    # ── 第 7 步：日志摘要表 ──
    log("========== 四量终极 点位重放参考（%s ~ %s，%d 笔）==========" % (
        SIGNAL_START, SIGNAL_END, len(signals)))
    log("持有期 | 成熟样本 | 胜率 | 均收 | 最好 | 最差")
    for p in HOLD_PERIODS:
        st = by_period[str(p)]
        log("T+%2d | %d | %s%% | %s%% | %s%% | %s%%" % (
            p, st["n"], st["win_rate"], st["avg"], st["best"], st["worst"]))

    push_result(out)
    log("全部完成")


def push_result(payload):
    """Contents API 推 raw_data/four_volume_pit_replay.json（先取 sha 再 PUT，防覆盖）。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log("⚠️ 无 GITHUB_TOKEN，跳过推送（产物仅留在 runner 本地）")
        return
    url = "https://api.github.com/repos/%s/contents/%s" % (REPO, "raw_data/four_volume_pit_replay.json")
    H = {"Authorization": "Bearer " + token,
         "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    sha = None
    try:
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=60) as resp:
            sha = json.load(resp).get("sha")
    except Exception:
        sha = None  # 文件不存在 → 新建
    body = {
        "message": "data: 四量终极 8月初~9-11 点位重放参考(pit-replay, 阿狸咪的工程师)",
        "content": base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(),
        "branch": "main",
    }
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=H, method="PUT")
    with urllib.request.urlopen(req, timeout=120) as resp:
        r = json.load(resp)
    log("✅ 已推 main: %s (commit %s)" % ("raw_data/four_volume_pit_replay.json",
                                          (r.get("commit") or {}).get("sha", "")[:8]))


if __name__ == "__main__":
    main()
