#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_intraday_momentum.py — 日内动量（第三支自研算法）· 真实信号流生产者
==========================================================================
🚀 2026-10-18 主人令「可靠科学且有效的我都要。今晚能做都做」：第二批候选因子
   上市前置回测（bt_factors.py，口径=全市场等权基准·T+1 开盘买·持 N 收盘卖·双边 0.3%，
   窗口 2025-04-24~2026-10-16，全 A 2574 只过滤后）结果——
   · S7 日内动量 ✅ 唯一跑赢：N=20 avg +2.59% vs 基准 +0.86%（α +1.73pp，n=2411）；
     N=10 α +0.57pp、N=30 α +1.21pp；**N≥45 衰减转负（-0.57/-0.82pp）⇒ 短中持有期有效，
     主档 T+20**。胜率 42.6% 为动量类天然特征（正偏度策略：小亏多次+大赢少数覆盖）。
   · 同批 S5 短期反转（全档 α −0.7~−4.1pp）/ S6 52周新高贴近（全档 α −0.3~−1.1pp）
     未跑赢基准 ⇒ 留档不上线。

选股（每日，全部只用 ≤T 数据，零未来函数）：
  · 股票池：全 A（00/30/60/68）· 上市 ≥120 交易日 · 剔 ST/退（当前名单）· 收盘 ≥2 元
    · 近 20 日均成交额 ≥5000 万（量纲哨兵判手/股，同 gen_lqsq_top5 口径）
    · 数据日对齐（末根=data_date）· 近 20 日无停牌
  · 信号：近 20 日日内累计收益（∑ close/open − 1）全市场最高 + 收盘 > MA60
    （Lou-Polk-Skouras 隔夜/日内拆分：日内动量延续、隔夜溢价衰减）
  · 每日取日内累计收益最高 Top5，逐日归档 raw_data/intraday_momentum_history.json
    （真实信号流，上线首日即建，含已回落票，防幸存者偏差——同 LQSQ 纪律）

自回测主榜（data/INTRADAY_MOMENTUM_BACKTEST.js，真实信号流口径 2026-10-11 主人令）：
  · 每日归档信号 → 次日开盘买 → 持 N 收盘卖 → 扣双边 0.3%；基准=同过滤 universe 等权
  · 未走满不计入；主档 T+20；🔴 历史规则回放禁作主榜——主榜只认本归档前向跟踪
  · replay 段（样本内·参考·禁作主榜依据）内置 bt_factors S7 全档结果，重写时透传保留

依赖：挂在 strategy_lowvol_trend.py 紧后（其前 gen_lqsq_top5.refresh_stale 已刷 ext，
     本脚本零重复拉数）。
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
RAW_DIR = os.path.join(BASE, "..", "raw_data")
KLINE_DIR = os.path.join(RAW_DIR, "kline_cache")
EXT_DIR = os.path.join(RAW_DIR, "kline_cache_ext")
HISTORY = os.path.join(RAW_DIR, "intraday_momentum_history.json")
OUT_JSON = os.path.join(RAW_DIR, "intraday_momentum.json")
OUT_JS = os.path.join(BASE, "..", "data", "INTRADAY_MOMENTUM_BACKTEST.js")

COST = 0.003
MIN_PRICE = 2.0
MIN_BARS = 120
EXT_MIN_LEN = 300
RECENT_N = 20
MOM_WIN = 20
LIQ_AMT = 50_000_000.0
AMT_MEDIAN_LO, AMT_MEDIAN_HI = 1e7, 1e10
TOP_K = 5
ALIGN_RATIO = 0.60
LADDERS = [5, 10, 20, 30, 45, 60]
PRIMARY_N = 20
MIN_UNIVERSE = 500

# ── replay：bt_factors.py S7 上市前置回放（样本内·参考·禁作主榜依据）──
REPLAY_BY_PERIOD = {
    "5":  {"samples": 1315, "win_rate": 45.1, "avg_return": 0.76, "bench_avg_return": -0.04, "alpha_pp": 0.80,  "best_return": 72.9,  "worst_return": -40.0},
    "10": {"samples": 1281, "win_rate": 43.4, "avg_return": 1.78, "bench_avg_return": 0.31,  "alpha_pp": 1.47,  "best_return": 113.8, "worst_return": -50.3},
    "20": {"samples": 1209, "win_rate": 45.7, "avg_return": 4.13, "bench_avg_return": 0.86,  "alpha_pp": 3.27,  "best_return": 154.5, "worst_return": -61.9},
    "30": {"samples": 1133, "win_rate": 45.6, "avg_return": 4.80, "bench_avg_return": 1.41,  "alpha_pp": 3.39,  "best_return": 247.0, "worst_return": -65.1},
    "45": {"samples": 1095, "win_rate": 41.6, "avg_return": 4.20, "bench_avg_return": 2.10,  "alpha_pp": 2.10,  "best_return": 349.5, "worst_return": -65.6},
    "60": {"samples": 1035, "win_rate": 41.4, "avg_return": 2.89, "bench_avg_return": 1.99,  "alpha_pp": 0.90,  "best_return": 248.9, "worst_return": -67.1},
}


def log(m):
    print(m, flush=True)


def now_cst():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def load_names():
    p = os.path.join(RAW_DIR, "stock_names.json")
    names = {}
    try:
        d = json.load(open(p, encoding="utf-8"))
        rows = d.get("data") if isinstance(d, dict) else d
        if isinstance(rows, list):
            for it in rows:
                if isinstance(it, dict) and "code" in it and "name" in it:
                    names[str(it["code"])] = it["name"]
    except Exception as e:
        log("⚠️ stock_names.json 不可用（ST 过滤降级）: %s" % str(e)[:80])
    return names


def load_bars():
    """全 A 日线缓存 → {code: bars}。ext（若 ≥300 根）优先于冻结 cache。"""
    out = {}
    for f in os.listdir(KLINE_DIR):
        code = f[:-5]
        if len(code) != 6 or code[0] not in "036":
            continue
        try:
            bars = json.load(open(os.path.join(KLINE_DIR, f), encoding="utf-8"))
        except Exception:
            continue
        if isinstance(bars, list) and len(bars) >= MIN_BARS:
            out[code] = bars
    if os.path.isdir(EXT_DIR):
        for code in list(out):
            p = os.path.join(EXT_DIR, code + ".json")
            if not os.path.exists(p):
                continue
            try:
                eb = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if isinstance(eb, list) and len(eb) >= EXT_MIN_LEN and len(eb) >= len(out[code]):
                out[code] = eb
    return out


def indicators(bars):
    """返回 (intra20数组, ma60数组)。只用 ≤i 数据。"""
    c = [float(b.get("close") or 0.0) for b in bars]
    o = [float(b.get("open") or 0.0) for b in bars]
    n = len(c)
    ma60 = [None] * n
    if n >= 60:
        s = sum(c[:60])
        ma60[59] = s / 60
        for i in range(60, n):
            s += c[i] - c[i - 60]
            ma60[i] = s / 60
    intra20 = [None] * n
    if n > MOM_WIN:
        for i in range(MOM_WIN, n):
            acc = 0.0
            ok = True
            for j in range(i - MOM_WIN + 1, i + 1):
                if o[j] <= 0:
                    ok = False
                    break
                acc += c[j] / o[j] - 1.0
            intra20[i] = acc if ok else None
    return intra20, ma60


def main():
    t0 = datetime.now(timezone(timedelta(hours=8)))
    names = load_names()
    ok_names = {c for c, nm in names.items()
                if "ST" not in nm.upper() and "退" not in nm} if names else None
    bars_map = load_bars()
    log("载入 %d 只（ext 优先）" % len(bars_map))

    # ── 自刷新：复用 gen_lqsq_top5.refresh_stale（与量质双擎/低波同源同通道，禁第二套实现）──
    try:
        from gen_lqsq_top5 import refresh_stale
        refresh_stale(bars_map)
    except Exception as e:
        log("⚠️ refresh_stale 复用失败（退化为纯缓存口径）: %s" % str(e)[:100])

    # ── 数据日：最近一个对齐率 ≥60% 的交易日 ──
    last_dates = Counter(b[-1]["date"] for b in bars_map.values() if len(b) >= MIN_BARS)
    if not last_dates:
        raise SystemExit("无有效 K 线缓存")
    total = sum(last_dates.values())
    data_date, cnt = None, 0
    for d in sorted(last_dates, reverse=True):
        if last_dates[d] >= total * ALIGN_RATIO:
            data_date, cnt = d, last_dates[d]
            break
    if data_date is None:
        raise SystemExit("无任何交易日对齐率 ≥%d%%——缓存新鲜度异常" % (ALIGN_RATIO * 100))
    log("数据日=%s（对齐 %d/%d=%.0f%%）" % (data_date, cnt, total, 100.0 * cnt / total))

    # ── 过滤：ST/退、价格、对齐、停牌、量纲哨兵+流动性 ──
    uni = {}
    for code, bars in bars_map.items():
        if len(bars) < MIN_BARS or bars[-1]["date"] != data_date:
            continue
        if ok_names is not None and code not in ok_names:
            continue
        if float(bars[-1].get("close") or 0.0) < MIN_PRICE:
            continue
        seg = bars[-RECENT_N:]
        if len(seg) < RECENT_N or any(float(b.get("volume") or 0.0) <= 0 for b in seg):
            continue
        uni[code] = bars
    raw_liq = []
    for bars in uni.values():
        seg = bars[-RECENT_N:]
        raw_liq.append(sum(float(b.get("volume") or 0.0) * float(b.get("close") or 0.0) for b in seg) / RECENT_N)
    unit = 1.0
    if raw_liq:
        med = sorted(raw_liq)[len(raw_liq) // 2]
        if AMT_MEDIAN_LO <= med <= AMT_MEDIAN_HI:
            unit = 1.0
        elif AMT_MEDIAN_LO <= med * 100 <= AMT_MEDIAN_HI:
            unit = 100.0
        else:
            unit = 0.0
            log("⚠️ 量纲哨兵报警：中位成交额 %.3g ⇒ 放弃绝对流动性闸门" % med)
    else:
        unit = 0.0
    if unit:
        uni = {c: b for c, b in uni.items()
               if sum(float(x.get("volume") or 0.0) * float(x.get("close") or 0.0)
                      for x in b[-RECENT_N:]) / RECENT_N * unit >= LIQ_AMT}
    log("过滤后候选池：%d 只" % len(uni))
    if len(uni) < MIN_UNIVERSE:
        raise SystemExit("候选池 %d < %d —— 放弃本日（宁缺勿滥）" % (len(uni), MIN_UNIVERSE))

    # ── 选股：近20日日内累计收益最高 ∧ 收盘>MA60 → Top5 ──
    scored = []
    for code, bars in uni.items():
        intra20, ma60 = indicators(bars)
        j = len(bars) - 1
        iv, m = intra20[j], ma60[j]
        cl = float(bars[j].get("close") or 0.0)
        if iv is None or m is None or cl <= 0 or cl <= m or iv <= 0:
            continue
        scored.append((iv, code, cl, m))
    scored.sort(reverse=True)
    picks = scored[:TOP_K]
    log("信号股 %d → Top%d" % (len(scored), len(picks)))
    if not picks:
        raise SystemExit("今日零信号（异常：日内动量+MA60 上方在正常市应非空）——中止不写档")

    pick_rows = [{"code": c, "name": names.get(c, ""), "close": round(cl, 2),
                  "intra20": round(iv, 4), "ma60": round(m, 2)}
                 for iv, c, cl, m in picks]

    # ── 归档（幂等：同日重跑覆盖）──
    hist = {"days": {}}
    if os.path.exists(HISTORY):
        try:
            hist = json.load(open(HISTORY, encoding="utf-8"))
        except Exception:
            hist = {"days": {}}
    hist.setdefault("days", {})[data_date] = {
        "picks": [r["code"] for r in pick_rows], "pool_size": len(uni)}
    days = hist["days"]
    json.dump(hist, open(HISTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump({"update_time": now_cst(), "data_date": data_date,
               "method": "日内动量：近20日日内累计收益(∑close/open-1)最高 Top5 ∧ 收盘>MA60（真实信号流，次开买入）",
               "pool_size": len(uni), "picks": pick_rows},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── 自回测（真实信号流口径；未走满不计入）──
    gset = set()
    for b in uni.values():
        gset.update(x["date"] for x in b)
    gd = sorted(gset)
    gidx = {d: i for i, d in enumerate(gd)}
    pos_map, bar_map = {}, {}
    for c, b in uni.items():
        pos_map[c] = {gidx[x["date"]]: i for i, x in enumerate(b)}
        bar_map[c] = b
    lim = {c: (1.197 if c[0] == "3" or c[:2] == "68" else 1.097) for c in uni}

    sig_days = sorted(days)
    by_period = {}
    for N in LADDERS:
        rets, bsum, bcnt = [], 0.0, 0
        for d in sig_days:
            g = gidx.get(d)
            if g is None or g + 1 + N > len(gd) - 1:
                continue
            for c in (days[d].get("picks") or []):
                pos = pos_map.get(c)
                if not pos:
                    continue
                ie, ix = pos.get(g + 1), pos.get(g + 1 + N)
                if ie is None or ix is None or ie == 0:
                    continue
                b = bar_map[c]
                pc = float(b[ie - 1].get("close") or 0.0)
                op = float(b[ie].get("open") or 0.0)
                xc = float(b[ix].get("close") or 0.0)
                if pc <= 0 or op <= 0 or xc <= 0 or op >= pc * lim[c]:
                    continue
                rets.append(xc / op - 1.0 - COST)
            s = 0.0
            k = 0
            for c, pos in pos_map.items():
                ie, ix = pos.get(g + 1), pos.get(g + 1 + N)
                if ie is None or ix is None or ie == 0:
                    continue
                b = bar_map[c]
                pc = float(b[ie - 1].get("close") or 0.0)
                op = float(b[ie].get("open") or 0.0)
                xc = float(b[ix].get("close") or 0.0)
                if pc <= 0 or op <= 0 or xc <= 0 or op >= pc * lim[c]:
                    continue
                s += xc / op - 1.0 - COST
                k += 1
            if k >= MIN_UNIVERSE:
                bsum += s / k
                bcnt += 1
        if rets:
            by_period[str(N)] = {
                "samples": len(rets),
                "win_rate": round(100.0 * sum(1 for r in rets if r > 0) / len(rets), 1),
                "avg_return": round(100.0 * sum(rets) / len(rets), 2),
                "best_return": round(100.0 * max(rets), 2),
                "worst_return": round(100.0 * min(rets), 2),
                "bench_avg_return": round(100.0 * bsum / bcnt, 2) if bcnt else None,
                "bench_days": bcnt,
            }
            log("T+%d：样本 %d，avg %.2f%%，胜率 %.1f%%，基准 %.2f%%（%d 日）"
                % (N, len(rets), by_period[str(N)]["avg_return"],
                   by_period[str(N)]["win_rate"],
                   by_period[str(N)]["bench_avg_return"] or 0, bcnt))

    total_signals = sum(len(v.get("picks") or []) for v in days.values())
    # 透传旧 replay（防链上日跑冲掉；仅当旧 replay 同为 Top5 口径才透传，
    # 否则用本文件内置 REPLAY_BY_PERIOD 兜底——保证口径升级后旧 Top10 回放不被误留）
    _replay_keep = None
    try:
        if os.path.exists(OUT_JS):
            _old = open(OUT_JS, encoding="utf-8").read()
            _i, _j = _old.find("{"), _old.rfind("}")
            if 0 <= _i < _j:
                _rp = json.loads(_old[_i:_j + 1]).get("replay")
                if isinstance(_rp, dict) and _rp.get("top_per_day") == 5:
                    _replay_keep = _rp
    except Exception:
        _replay_keep = None
    if _replay_keep is None:
        _replay_keep = {
            "kind": "historical_rule_replay_sample_in",
            "note": ("历史规则回放（样本内·参考）：与线上完全同口径规则（近20日日内累计收益Top5且收盘>MA60）"
                     "在窗口 2025-04-24~2026-10-16 逐日重放（bt_factors.py）；规则在同一窗口选出→存在样本内"
                     "选择偏差，按 2026-10-11 铁律禁作主榜/评级/上下架依据；权威口径=真实信号流（summary.by_period）"),
            "window": ["2025-04-24", "2026-10-16"], "universe": 2574, "top_per_day": 5,
            "cost_pct": 0.3,
            "engine": "上市前置·等权基准（同过滤 universe）·与 bt_factors 同源",
            "by_period": REPLAY_BY_PERIOD,
        }
    payload = {
        "update_time": now_cst(), "calc_time": now_cst(), "data_date": data_date,
        "method": ("真实信号流口径（2026-10-11 主人令）：每日全市场近 20 日日内累计收益（∑close/open−1）最高 Top5 "
                   "且收盘>MA60（日内动量，Top5 口径上市前置回测 N=20 α+3.27pp/胜率45.7pct 全档正α；N≥60 衰减 ⇒ 主档 T+"
                   + str(PRIMARY_N) + "），次开买入、持有 N 个交易日收盘卖出（前复权·扣双边 0.3pct）；"
                   "基准=同过滤 universe 等权。样本随持有天数成熟而增加，未走满不计入。"),
        "signal_source": "intraday_momentum_history 逐日真实选股归档（上线首日即建，含已回落票，防幸存者偏差）",
        "track_start": min(sig_days) if sig_days else data_date,
        "signal_date_range": "%s ~ %s" % (min(sig_days), max(sig_days)) if sig_days else data_date,
        "total_signals": total_signals,
        "cost_adjusted": True,
        "replay": _replay_keep,
        "summary": {"by_period": by_period},
        "republish_time": now_cst(),
    }
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    with open(OUT_JS, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.INTRADAY_MOMENTUM_BACKTEST = " +
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";")
    # ── 前端 picks 视图 ──
    picks_js = os.path.join(BASE, "..", "data", "INTRADAY_MOMENTUM.js")
    tracked = [{"signal_date": data_date,
                "code": r["code"], "name": r["name"], "close": r["close"],
                "intra20": r["intra20"], "ma60": r["ma60"]} for r in pick_rows]
    picks_payload = {
        "update_time": now_cst(), "data_date": data_date, "pool_size": len(uni),
        "picks": pick_rows, "tracked": tracked,
        "track_start": min(sig_days) if sig_days else data_date,
        "total_signals": total_signals,
    }
    with open(picks_js, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.INTRADAY_MOMENTUM = " +
                json.dumps(picks_payload, ensure_ascii=False, separators=(",", ":")) + ";")
    log("完成：%s / %s（用时 %.0fs）" % (OUT_JS, picks_js,
                                        datetime.now(timezone(timedelta(hours=8))).timestamp() - t0.timestamp()))


if __name__ == "__main__":
    main()
