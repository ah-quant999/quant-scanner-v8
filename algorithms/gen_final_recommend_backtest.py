#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_final_recommend_backtest.py — 最终推荐 Top5 · 信号层真实回测

2026-10-13 主人令：「最终推荐的前5名我也想有个回测，就放最终推荐下方，
和这个（强势跟踪回测卡）相同，我要看到底靠不靠谱。」

【信号源 = 真实信号流】（🔴 2026-10-11 主人令「所有回测只认真真信号流口径」）
  raw_data/history/final_recommend_YYYYMMDD.json —— 算法链每日**真实选股**的
  dated 快照归档（final_recommend.py 主函数末尾落盘，29 个文件，09-03~10-13）。
  **不是**历史规则回放（回放含当前股池幸存者偏差，禁作主榜/评级依据）。

【口径】（与 algorithms/backtest_life_cards.py 的 IMA 卡逐字同源，保证跨卡可比）
  · 信号日归因：update_time 小时 < 9 ⇒ 归前一自然日（与闸门 _NIGHT_CUT=9 同源；
    凌晨跑批产的是上一交易日收盘后的推荐，不能算成当天的）
  · 同一入场点去重：多个归档版本归因到同一入场日时**只认最新版**（旧版视为被
    刷新替代）—— 实测 09-04/09-05（完全相同 5 只）、09-18/19/20（周末三连跑）、
    09-30/10-01（国庆）、10-09/10/11（周末三连跑）等多组重跑，不去重即双计
  · 入场：归因信号日之后的**首个可交易日开盘**（按该票自身日K；停牌顺延至复牌）
  · 出场：持有 N 个交易日**收盘**卖出（按该票自身日K，与 IMA 卡同）
  · 成本：双边 0.30%（15bps x 2），与 FOUR_VOLUME_BACKTEST / IMA 卡一致
  · 未成熟 / 缺价 / K 线未覆盖：该档 samples=0 + immature=true，其余字段一律
    null —— **绝不用 0 冒充**（假 0 会污染胜率，是主人最痛恨的失真）
  · max_drawdown：每笔「持仓期内相对持仓期最高收盘价」的最大回撤，取全样本均值

【输出】
  - raw_data/final_recommend_backtest.json          （数据本体）
  - data/FINAL_RECOMMEND_BACKTEST.js               （window.FINAL_RECOMMEND_BACKTEST）
  两个文件均由本脚本直接写（与 final_recommend.py 写 FINAL_RECOMMEND_DATA.js 同写法），
  由 final_recommend.py 主函数末尾调用（try/except 包裹，回测失败绝不影响 D 批主产物）。

用法：
  python algorithms/gen_final_recommend_backtest.py
  python algorithms/gen_final_recommend_backtest.py --dry   # 只打印不写文件
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
DATA = ROOT / "data"
HIST = RAW / "history"
KC = RAW / "kline_cache"

# ── 口径常量（与 backtest_life_cards.py 同源，禁单方面修改）────────────────────
COST_PCT = 0.30                       # 双边总成本（%）= 15bps x 2
HORIZONS = [1, 2, 3, 5, 10, 20, 30, 45, 60, 75, 90, 180, 250]   # 与 IMA 卡同 ladder
NIGHT_CUT = 9                         # 与闸门 _NIGHT_CUT 同源：小时 < 9 归前一自然日
CST = dt.timezone(dt.timedelta(hours=8))

METHOD = ("信号日次一交易日开盘买入，持有 N 个交易日收盘价卖出"
          "（真实日K；已扣双边交易成本 0.30%）")

_BARS_CACHE: dict = {}


def now_cst() -> dt.datetime:
    return dt.datetime.now(CST)


# ── 真实日K读取（与 backtest_life_cards.bars_of 同构）────────────────────────
def bars_of(code: str):
    """→ {"dates":[...], "open":{d:px}, "close":{d:px}, "high":{d:px}, "low":{d:px}} 或 None"""
    code = str(code).strip().lstrip(".")
    if code in _BARS_CACHE:
        return _BARS_CACHE[code]
    out = None
    p = KC / f"{code}.json"
    if p.exists():
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(b, dict):
                b = b.get("bars") or b.get("data") or b.get("klines") or []
            rows = []
            for x in b:
                d = x.get("date")
                c = x.get("close")
                if not d or c is None:
                    continue
                rows.append((str(d), x.get("open"), float(c),
                             x.get("high"), x.get("low")))
            rows.sort(key=lambda t: t[0])
            if rows:
                out = {
                    "dates": [r[0] for r in rows],
                    "open":  {r[0]: r[1] for r in rows},
                    "close": {r[0]: r[2] for r in rows},
                    "high":  {r[0]: r[3] for r in rows if r[3] is not None},
                    "low":   {r[0]: r[4] for r in rows if r[4] is not None},
                }
        except Exception:
            out = None
    _BARS_CACHE[code] = out
    return out


def one_trade(series, entry_date: str, n: int):
    """单笔 T+N 收益(%)；未成熟/缺价 → None。

    entry_date = 归因信号日之后的首个**可交易日**（市场日历）。
    实际入场 = 该票自身日K中首个 >= entry_date 的交易日（停牌顺延至复牌）；
    出场 = 入场后再持有 (n-1) 个该票交易日的收盘。
    """
    if not series:
        return None
    ds = series["dates"]
    ei = None
    for i, d in enumerate(ds):
        if d >= entry_date:
            ei = i
            break
    if ei is None:
        return None                       # K 线未覆盖到入场日（如刚产生的推荐）—— 不当 0
    xi = ei + (n - 1)
    if xi >= len(ds):
        return None                       # 未成熟 —— 绝不当 0
    entry = series["open"].get(ds[ei]) or series["close"].get(ds[ei])
    exit_ = series["close"].get(ds[xi])
    if not entry or not exit_:
        return None                       # 停牌/缺价 —— 跳过
    gross = (exit_ - entry) / entry * 100.0
    peak = entry
    mdd = 0.0
    for k in range(ei, xi + 1):
        c = series["close"].get(ds[k])
        if c is None:
            continue
        if c > peak:
            peak = c
        dd = (c - peak) / peak * 100.0
        if dd < mdd:
            mdd = dd
    return round(gross - COST_PCT, 2), round(mdd, 2)


def _load_bench():
    """全市场等权基准（gen_market_bench.py → raw_data/market_bench.json）；缺文件 → {}。"""
    p = RAW / "market_bench.json"
    try:
        return (json.loads(p.read_text(encoding="utf-8")) or {}).get("by_date") or {}
    except Exception:
        return {}


def build_periods(signals, horizons=HORIZONS):
    """signals: [(code, entry_date), ...] → periods dict（键 '1d'/'3d'…，与 IMA 卡同构）"""
    bench = _load_bench()
    sig_days = sorted({d for _, d in signals})
    periods = {}
    for n in horizons:
        _bv = ([bench[d][str(n)] for d in sig_days
                if d in bench and (bench[d].get(str(n)) or {}).get("avg") is not None]
               if bench else [])
        rets, mdds = [], []
        for code, d in signals:
            r = one_trade(bars_of(code), d, n)
            if r is None:
                continue
            rets.append(r[0])
            mdds.append(r[1])
        key = f"{n}d"
        if not rets:
            periods[key] = {
                "samples": 0, "immature": True,
                "win": None, "loss": None,
                "win_rate": None, "avg_return": None, "median_return": None,
                "best_return": None, "worst_return": None, "max_drawdown": None,
            }
            continue
        win = sum(1 for r in rets if r > 0)
        periods[key] = {
            "samples": len(rets),
            "immature": False,
            "win": win,
            "loss": len(rets) - win,
            "win_rate": round(win / len(rets) * 100.0, 1),
            "avg_return": round(sum(rets) / len(rets), 2),
            "median_return": round(st.median(rets), 2),
            "best_return": round(max(rets), 2),
            "worst_return": round(min(rets), 2),
            "max_drawdown": round(sum(mdds) / len(mdds), 2),
        }
        if len(_bv) >= 5:
            periods[key]["bench_avg_return"] = round(sum(x["avg"] for x in _bv) / len(_bv), 4)
            _bw = [x.get("win") for x in _bv if x.get("win") is not None]
            if _bw:
                periods[key]["bench_win_rate"] = round(sum(_bw) / len(_bw), 2)
            periods[key]["bench_days"] = len(_bv)
    return periods


# ── 信号流装载与归因 ─────────────────────────────────────────────────────────
def _attributed_date(update_time: str, file_date: str) -> str:
    """update_time → 数据日（夜切：小时 < NIGHT_CUT 归前一自然日）。

    与 gen_backtest_all_algos._cand / 闸门 chain_day 同源。缺 update_time 时
    按文件日期 + 23 时（保守视为当晚跑批）处理。
    """
    s = (update_time or "").strip()
    if len(s) >= 13 and s[4] == "-" and s[10] in " T":
        try:
            d = dt.date.fromisoformat(s[:10])
            hh = int(s[11:13])
            if hh < NIGHT_CUT:
                d = d - dt.timedelta(days=1)
            return d.isoformat()
        except Exception:
            pass
    return file_date


def load_versions():
    """读全部归档 → [{file, file_date, attributed, update_time, stocks:[(code,name,rank)]}]"""
    out = []
    for p in sorted(HIST.glob("final_recommend_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️ {p.name} 解析失败: {e}")
            continue
        file_date = p.stem.replace("final_recommend_", "")
        try:
            fd = dt.date.fromisoformat(file_date).isoformat()
        except Exception:
            print(f"  ⚠️ {p.name} 文件名日期无法解析，跳过")
            continue
        stocks = []
        for s in (d.get("stocks") or []):
            c = str(s.get("code") or "").strip().lstrip(".")
            if not c:
                continue
            stocks.append((c, str(s.get("name") or ""), s.get("rank")))
        out.append({
            "file": p.name,
            "file_date": fd,
            "attributed": _attributed_date(d.get("update_time"), fd),
            "update_time": (d.get("update_time") or "")[:19],
            "top_n": d.get("top_n"),
            "stocks": stocks,
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印，不写文件")
    a = ap.parse_args(argv)

    print(f"[gen_final_recommend_backtest] {now_cst():%Y-%m-%d %H:%M:%S}")
    versions = load_versions()
    if not versions:
        print("  ⚠️ 无归档文件（raw_data/history/final_recommend_*.json），退出")
        return 1
    print(f"  · 归档版本 {len(versions)} 个（{versions[0]['file_date']} ~ {versions[-1]['file_date']}）")

    # ── 市场日历 = 全部涉及股票日K日期并集（推荐股均为流动性标的，并集即市场交易日）──
    all_codes = sorted({c for v in versions for c, _, _ in v["stocks"]})
    calendar = set()
    for c in all_codes:
        s = bars_of(c)
        if s:
            calendar.update(s["dates"])
    cal = sorted(calendar)
    if not cal:
        print("  ⚠️ K 线缓存无任何数据，退出")
        return 1
    print(f"  · 市场日历（K线并集）: {cal[0]} ~ {cal[-1]}（{len(cal)} 个交易日）")

    # ── 归因 → 入场日 → 同入场点只认最新版 ───────────────────────────────
    def next_trading_day(d: str):
        for x in cal:
            if x > d:
                return x
        return None

    groups = {}          # entry_date → version（最新版胜出）
    superseded = 0
    no_entry = 0
    for v in versions:
        e = next_trading_day(v["attributed"])
        if e is None:
            no_entry += 1
            continue
        v["entry_date"] = e
        if e in groups:
            superseded += 1
            if (v["update_time"] or "") >= (groups[e]["update_time"] or ""):
                groups[e] = v
        else:
            groups[e] = v
    print(f"  · 归因去重：{superseded} 个旧版被同入场点新版替代；"
          f"{no_entry} 个版本无后续可交易日（K 线未覆盖，不计）")
    print(f"  · 独立信号日（入场日）: {len(groups)} 个")

    # ── 信号集 ───────────────────────────────────────────────────────────
    signals = []          # (code, entry_date)
    detail = []
    missing_kline = []
    for e in sorted(groups):
        v = groups[e]
        for c, nm, rk in v["stocks"]:
            if bars_of(c) is None:
                missing_kline.append((c, e))
                continue
            signals.append((c, e))
            detail.append({"entry_date": e, "code": c, "name": nm,
                           "rank": rk, "src_file": v["file"]})
    if missing_kline:
        print(f"  ⚠️ {len(missing_kline)} 笔信号缺 K 线缓存，如实跳过: "
              f"{missing_kline[:5]}{'…' if len(missing_kline) > 5 else ''}")
    total_trades = len(signals)
    days = sorted({d for _, d in signals})
    print(f"  · 可用信号 {total_trades} 笔（{len(days)} 个入场日 × Top5；"
          f"缺K线跳过 {len(missing_kline)} 笔）")

    periods = build_periods(signals)
    n_ok = sum(1 for v in periods.values() if v.get("samples"))
    print(f"  · 成熟档 {n_ok}/{len(periods)}")
    for k in HORIZONS:
        v = periods[f"{k}d"]
        if v["samples"]:
            print(f"    T+{k:<3d} n={v['samples']:<4d} 胜率={v['win_rate']}% "
                  f"均收益={v['avg_return']}% 中位={v['median_return']}% "
                  f"最好={v['best_return']}% 最差={v['worst_return']}% 回撤={v['max_drawdown']}%")
        else:
            print(f"    T+{k:<3d} 未成熟（样本不足以覆盖此持有期，累积中）")

    payload = {
        "generated": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        # 🔴 必须自带 update_time：本脚本直写 data/*.js（不经 update_v8 桥接注入），
        #   而 v8_health_check.check_data_cards 的判龄字段是 update_time/date/lastUpdated
        #   （不含 generated）—— 缺它 = 巡检报「无法解析更新时间」假警报。
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "card": "最终推荐 · Top5",
        "method": METHOD,
        "cost_pct_roundtrip": COST_PCT,
        "cost_bps_per_side": 15,
        "cost_adjusted": True,
        "price_source": "raw_data/kline_cache（真实日K缓存）",
        "caliber": "signal_layer",
        "horizons": HORIZONS,
        "signal_source": ("raw_data/history/final_recommend_YYYYMMDD.json"
                          "（算法链每日真实选股的 dated 快照归档 —— 真实信号流口径，"
                          "非历史规则回放）"),
        "attribution_rule": ("update_time 小时 < 9 归前一自然日（与闸门 _NIGHT_CUT 同源）；"
                             "同一入场日的多个归档版本只认最新版（旧版视为被刷新替代），"
                             "杜绝周末/国庆重跑双计"),
        "versions_total": len(versions),
        "versions_superseded": superseded,
        "versions_no_entry": no_entry,
        "signals_missing_kline": len(missing_kline),
        "total_signals": total_trades,
        "signal_days": len(days),
        "signal_date_range": (f"{days[0]} ~ {days[-1]}" if days else None),
        "kline_calendar_range": f"{cal[0]} ~ {cal[-1]}",
        "periods": periods,
        "detail": detail,
    }

    if a.dry:
        print("  --dry：不写文件")
        return 0

    (RAW / "final_recommend_backtest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (DATA / "FINAL_RECOMMEND_BACKTEST.js").write_text(
        "/* 最终推荐 Top5 · 信号层真实回测 — gen_final_recommend_backtest.py 产出 */\n"
        "window.FINAL_RECOMMEND_BACKTEST = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8", newline="\n")
    print("  ✅ 写出 raw_data/final_recommend_backtest.json + data/FINAL_RECOMMEND_BACKTEST.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
