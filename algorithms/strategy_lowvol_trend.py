#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_lowvol_trend.py — 低波趋势（第二支自研算法）· 真实信号流生产者
==========================================================================
🚀 2026-10-18 主人令「按建议做新算法·回测过了才上线」：四方向上市前置回测
   （bt 口径=全市场等权基准·T+1 开盘买·持 N 日收盘卖·双边 0.3%，窗口 2025-04~2026-10，
   全 A 2574 只过滤后）结果——
   · S2 低波+趋势 ✅ 唯一显著跑赢：N=60 avg +5.99% vs 基准 +1.99%（α +4.00pp，胜率 53.3%，n=2013）
     N=45 α +1.50pp；同窗口 S1 板块轮动 / S3 稳健突破 / S4 回踩 MA20 全部未跑赢基准 ⇒ 不上线。
   · 故本策略上线，其余三方向回测结论留档（详见 HANDOFF fourvolume 后续挂账）。

选股（每日，全部只用 ≤T 数据，零未来函数）：
  · 股票池：全 A（00/30/60/68）· 上市 ≥120 交易日（kline_cache 冻结快照所限；
    线上读 kline_cache_ext 700 根后同样满足）· 剔 ST/退（当前名单）· 收盘 ≥2 元
    · 近 20 日均成交额 ≥5000 万（量纲哨兵判手/股，同 gen_lqsq_top5 口径）
    · 数据日对齐（末根=data_date）· 近 20 日无停牌（vol≤0 视为停牌）
  · 信号：60 日日收益波动率全市场最低 + 收盘 > MA60（低波且处上升趋势）
  · 每日取波动率最低 Top5，逐日归档 raw_data/lowvol_trend_history.json（真实信号流，
    上线首日即建，含已回落票，防幸存者偏差——同 LQSQ 纪律）

自回测主榜（data/LOWVOL_TREND_BACKTEST.js，真实信号流口径 2026-10-11 主人令）：
  · 每日归档信号 → 次一交易日开盘买入 → 持有 N 个交易日收盘卖出 → 扣双边 0.3%
  · 基准 = 同过滤 universe 等权（同日同梯）
  · 未走满持有期不计入（immature 不冒充）；主档 T+60（上市前置回测 α 最大档）
  · 🔴 历史规则回放禁作主榜（10-11 主人令铁律）——主榜只认本归档前向跟踪。

依赖：挂在 gen_lqsq_top5.py 紧后（其维护 kline_cache_ext 新鲜度，本脚本零重复拉数）。
"""
import json
import os
import sys
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
RAW_DIR = os.path.join(BASE, "..", "raw_data")
KLINE_DIR = os.path.join(RAW_DIR, "kline_cache")
EXT_DIR = os.path.join(RAW_DIR, "kline_cache_ext")
HISTORY = os.path.join(RAW_DIR, "lowvol_trend_history.json")
OUT_JSON = os.path.join(RAW_DIR, "lowvol_trend.json")
OUT_JS = os.path.join(BASE, "..", "data", "LOWVOL_TREND_BACKTEST.js")

COST = 0.003
MIN_PRICE = 2.0
MIN_BARS = 120          # 冻结快照下限（线上 ext 700 根时自然满足更长）
EXT_MIN_LEN = 300
RECENT_N = 20
VOL_WIN = 60
LIQ_AMT = 50_000_000.0
AMT_MEDIAN_LO, AMT_MEDIAN_HI = 1e7, 1e10
TOP_K = 5
ALIGN_RATIO = 0.60
LADDERS = [1, 3, 5, 10, 20, 30, 45, 60]
PRIMARY_N = 60
MIN_UNIVERSE = 500      # 基准逐日样本下限（宁缺勿滥）

# ── replay：bt_newalgos.py S2 上市前置回放（样本内·参考·禁作主榜依据）·Top5 口径 ──
REPLAY_BY_PERIOD = {
    "1":  {"samples": 1341, "win_rate": 40.9, "avg_return": -0.19, "bench_avg_return": -0.18, "alpha_pp": -0.01, "best_return": 10.2,  "worst_return": -6.2},
    "3":  {"samples": 1326, "win_rate": 44.4, "avg_return": -0.04, "bench_avg_return": -0.13, "alpha_pp": 0.09,  "best_return": 31.6,  "worst_return": -7.8},
    "5":  {"samples": 1308, "win_rate": 46.2, "avg_return": 0.15,  "bench_avg_return": -0.04, "alpha_pp": 0.19,  "best_return": 59.8,  "worst_return": -20.7},
    "10": {"samples": 1264, "win_rate": 46.3, "avg_return": 0.32,  "bench_avg_return": 0.31,  "alpha_pp": 0.01,  "best_return": 64.3,  "worst_return": -33.0},
    "20": {"samples": 1190, "win_rate": 46.7, "avg_return": 0.27,  "bench_avg_return": 0.86,  "alpha_pp": -0.59, "best_return": 50.6,  "worst_return": -38.5},
    "30": {"samples": 1132, "win_rate": 50.3, "avg_return": 1.74,  "bench_avg_return": 1.41,  "alpha_pp": 0.34,  "best_return": 261.2, "worst_return": -32.1},
    "45": {"samples": 1081, "win_rate": 54.6, "avg_return": 3.92,  "bench_avg_return": 2.10,  "alpha_pp": 1.82,  "best_return": 504.7, "worst_return": -28.3},
    "60": {"samples": 1009, "win_rate": 55.6, "avg_return": 5.71,  "bench_avg_return": 1.99,  "alpha_pp": 3.72,  "best_return": 767.0, "worst_return": -29.7},
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
    """返回 (vol60数组, ma60数组)。只用 ≤i 数据。"""
    c = [float(b.get("close") or 0.0) for b in bars]
    n = len(c)
    rets = [0.0] * n
    for i in range(1, n):
        rets[i] = c[i] / c[i - 1] - 1.0 if c[i - 1] > 0 else 0.0
    vol60 = [None] * n
    for i in range(VOL_WIN, n):
        seg = rets[i - VOL_WIN + 1:i + 1]
        m = sum(seg) / VOL_WIN
        vol60[i] = math.sqrt(sum((x - m) ** 2 for x in seg) / (VOL_WIN - 1))
    ma60 = [None] * n
    if n >= 60:
        s = sum(c[:60])
        ma60[59] = s / 60
        for i in range(60, n):
            s += c[i] - c[i - 60]
            ma60[i] = s / 60
    return vol60, ma60


def main():
    t0 = datetime.now(timezone(timedelta(hours=8)))
    names = load_names()
    ok_names = {c for c, n in names.items()
                if "ST" not in n.upper() and "退" not in n} if names else None
    bars_map = load_bars()
    log("载入 %d 只（ext 优先）" % len(bars_map))

    # ── 自刷新：复用 gen_lqsq_top5.refresh_stale（GTimg 700 根整根替换 + ext 持久，
    #    与量质双擎同源同通道同预算，禁第二套实现防口径漂移）──
    try:
        from gen_lqsq_top5 import refresh_stale
        refresh_stale(bars_map)
    except Exception as e:
        log("⚠️ refresh_stale 复用失败（退化为纯缓存口径）: %s" % str(e)[:100])

    # ── 数据日：候选末根众数日期序列里，取「最近一个对齐率 ≥60%」的交易日 ──
    #   （云端 ext 新鲜时即今日；本地/刷新欠账日自动回退最近完整日——归档 data_date
    #    如实记录真实数据日，不冒充今日。全部日期都不足 60% 才报死。）
    last_dates = Counter(b[-1]["date"] for b in bars_map.values()
                         if len(b) >= MIN_BARS)
    if not last_dates:
        raise SystemExit("无有效 K 线缓存")
    total = sum(last_dates.values())
    data_date, cnt = None, 0
    for d in sorted(last_dates, reverse=True):
        if last_dates[d] >= total * ALIGN_RATIO:
            data_date, cnt = d, last_dates[d]
            break
    if data_date is None:
        raise SystemExit("无任何交易日对齐率 ≥%d%%（最大 %.0f%%）——缓存新鲜度异常"
                         % (ALIGN_RATIO * 100,
                            100.0 * max(last_dates.values()) / total))
    log("数据日=%s（对齐 %d/%d=%.0f%%）" % (data_date, cnt, total, 100.0 * cnt / total))

    # ── 过滤：ST/退、价格、对齐、停牌、量纲哨兵+流动性 ──
    uni = {}
    for code, bars in bars_map.items():
        if len(bars) < MIN_BARS or bars[-1]["date"] != data_date:
            continue
        if ok_names is not None and code not in ok_names:
            continue
        c1 = float(bars[-1].get("close") or 0.0)
        if c1 < MIN_PRICE:
            continue
        seg = bars[-RECENT_N:]
        if len(seg) < RECENT_N or any(float(b.get("volume") or 0.0) <= 0 for b in seg):
            continue  # 近 20 日有停牌/无量
        uni[code] = bars
    # 量纲哨兵
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
            log("⚠️ 量纲哨兵报警：中位成交额 %.3g 不落常识区间 ⇒ 放弃绝对流动性闸门" % med)
    else:
        unit = 0.0
    if unit:
        uni = {c: b for c, b in uni.items()
               if sum(float(x.get("volume") or 0.0) * float(x.get("close") or 0.0)
                      for x in b[-RECENT_N:]) / RECENT_N * unit >= LIQ_AMT}
    log("过滤后候选池：%d 只" % len(uni))
    if len(uni) < MIN_UNIVERSE:
        raise SystemExit("候选池 %d < %d —— 放弃本日（宁缺勿滥）" % (len(uni), MIN_UNIVERSE))

    # ── 选股：vol60 最低 ∧ 收盘>MA60 → Top5 ──
    scored = []
    for code, bars in uni.items():
        vol60, ma60 = indicators(bars)
        j = len(bars) - 1
        v, m = vol60[j], ma60[j]
        cl = float(bars[j].get("close") or 0.0)
        if v is None or m is None or cl <= 0 or cl <= m:
            continue
        scored.append((v, code, cl, m))
    scored.sort()
    picks = scored[:TOP_K]
    log("信号股 %d → Top%d" % (len(scored), len(picks)))
    if not picks:
        raise SystemExit("今日零信号（异常：低波+MA60 上方在正常市应非空）——中止不写档")

    pick_rows = [{"code": c, "name": names.get(c, ""), "close": round(cl, 2),
                  "vol60": round(v, 5), "ma60": round(m, 2)}
                 for v, c, cl, m in picks]

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

    # 当日产物
    json.dump({"update_time": now_cst(), "data_date": data_date,
               "method": "低波趋势：60日波动率最低 Top5 ∧ 收盘>MA60（真实信号流，次开买入）",
               "pool_size": len(uni), "picks": pick_rows},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── 自回测（真实信号流口径；未走满不计入）──
    # 全局交易日轴
    gset = set()
    for b in uni.values():
        gset.update(x["date"] for x in b)
    gd = sorted(gset)
    gidx = {d: i for i, d in enumerate(gd)}
    pos_map = {}
    bar_map = {}
    for c, b in uni.items():
        pos_map[c] = {gidx[x["date"]]: i for i, x in enumerate(b)}
        bar_map[c] = b
    lim = {c: (1.197 if c[0] == "3" or c[:2] == "68" else 1.097) for c in uni}

    sig_days = sorted(days)
    by_period = {}
    for N in LADDERS:
        rets, bsum, bcnt, bpos = [], 0.0, 0, 0
        for d in sig_days:
            g = gidx.get(d)
            if g is None or g + 1 + N > len(gd) - 1:
                continue  # 未走满（全局轴末段）
            day_picks = days[d].get("picks") or []
            for c in day_picks:
                pos = pos_map.get(c)
                if not pos:
                    continue
                ie, ix = pos.get(g + 1), pos.get(g + 1 + N)
                if ie is None or ix is None or ie == 0:
                    continue  # 停牌/未上市
                b = bar_map[c]
                pc = float(b[ie - 1].get("close") or 0.0)
                op = float(b[ie].get("open") or 0.0)
                xc = float(b[ix].get("close") or 0.0)
                if pc <= 0 or op <= 0 or xc <= 0 or op >= pc * lim[c]:
                    continue
                rets.append(xc / op - 1.0 - COST)
            # 基准（同日同梯，同过滤 universe 等权）
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
            "note": ("历史规则回放（样本内·参考）：与线上完全同口径规则（60日波动率最低Top5且收盘>MA60）"
                     "在窗口 2025-04-24~2026-10-16 逐日重放（bt_newalgos.py）；规则在同一窗口选出→存在样本内"
                     "选择偏差，按 2026-10-11 铁律禁作主榜/评级/上下架依据；权威口径=真实信号流（summary.by_period）"),
            "window": ["2025-04-24", "2026-10-16"], "universe": 2574, "top_per_day": 5,
            "cost_pct": 0.3,
            "engine": "上市前置·等权基准（同过滤 universe）·与 bt_newalgos 同源",
            "by_period": REPLAY_BY_PERIOD,
        }
    payload = {
        "update_time": now_cst(), "calc_time": now_cst(), "data_date": data_date,
        "method": ("真实信号流口径（2026-10-11 主人令）：每日全市场 60 日波动率最低 Top5 且收盘>MA60"
                   "（低波+趋势，Top5 口径上市前置回测 N=60 α+3.72pp/胜率55.6pct 显著跑赢），"
                   "次开买入、持有 N 个交易日收盘卖出（前复权·扣双边 0.3pct）；基准=同过滤 universe 等权。"
                   "样本随持有天数成熟而增加，未走满不计入；主档 T+" + str(PRIMARY_N) + "。"),
        "signal_source": "lowvol_trend_history 逐日真实选股归档（上线首日 2026-10-18 即建，含已回落票，防幸存者偏差）",
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
        f.write("window.LOWVOL_TREND_BACKTEST = " +
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";")
    # ── 前端 picks 视图（选股策略·低波趋稳子页消费）──
    picks_js = os.path.join(BASE, "..", "data", "LOWVOL_TREND.js")
    tracked = [{"signal_date": data_date,
                "code": r["code"], "name": r["name"], "close": r["close"],
                "vol60": r["vol60"], "ma60": r["ma60"]} for r in pick_rows]
    picks_payload = {
        "update_time": now_cst(), "data_date": data_date, "pool_size": len(uni),
        "picks": pick_rows, "tracked": tracked,
        "track_start": min(sig_days) if sig_days else data_date,
        "total_signals": total_signals,
    }
    with open(picks_js, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.LOWVOL_TREND = " +
                json.dumps(picks_payload, ensure_ascii=False, separators=(",", ":")) + ";")
    log("已写出 %s（信号 %d 日 / %d 条）+ picks 视图" % (OUT_JS, len(sig_days), total_signals))
    log("耗时 %.1fs" % (datetime.now(timezone(timedelta(hours=8))).timestamp() - t0.timestamp()))


if __name__ == "__main__":
    main()
