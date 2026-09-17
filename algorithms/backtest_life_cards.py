# -*- coding: utf-8 -*-
"""
选股生命周期子页面 · 各卡「信号层」真实回测（2026-09-16 主人令）

主人原话：「在生命周期子页面下面，分部用（选股生命周期 / 强势突破 / 高手强势股跟踪）
           这三个做回测，要求用真实数据回测，并打上真实数据回测标识。
           一定要确保数据的真实性！」

本脚本为「强势突破」「高手强势股跟踪」两张卡产出**真实**信号层回测
（第三张「选股生命周期」的回测由 algorithms/gen_algo_track.py → data/ALGO_TRACK.js
  的 algos[0].stats.by_horizon 提供，本脚本不重复计算）：

  · 强势突破         信号源 raw_data/strong_breakout_history.json（逐日真实信号账本）
  · 高手强势股跟踪    信号源 raw_data/ima_strong_stock.json（IMA 同步的真实入选日）

  价格源 raw_data/kline_cache/<code>.json —— 本地真实日K缓存，
  与 algorithms/gen_algo_track.py / calc_crds.py 同源同口径（非估算、非模拟）。

【口径】（与四量终极 FOUR_VOLUME_BACKTEST、回测页主表同族）
  · 入场：信号日【次一交易日开盘价】买入
  · 出场：持有 N 个交易日后【收盘价】卖出
  · 成本：双边 0.30%（15bps x 2），与 FOUR_VOLUME_BACKTEST.cost_bps_per_side 一致
  · 未成熟：样本尚未走满 N 个交易日 ⇒ 该档 samples=0 且 immature=true，
            其余字段一律 null。**绝不填 0 冒充**（假 0 会污染胜率，是主人最痛恨的失真）
  · 缺价/停牌：该笔直接跳过，不参与该档统计（同样绝不用 0 顶替）

【诚实铁律】
  · 只输出真实可算出的数字；无成熟样本的档位如实标 immature
  · 回测窗口不足导致的档位缺失如实保留，不插值、不外推、不美化
  · max_drawdown 口径：每笔「持仓期内相对持仓期最高收盘价」的最大回撤，再取全样本均值

【挂链】
  · 由 update_v8.py 的 experiment 段调用（紧随 scripts/gen_strong_breakout.py 之后，
    确保读到当日最新信号账本），产出两个 raw_data/*.json
  · 再由 update_v8.py 的 DATA_SOURCES / CATEGORY_MAP(post_close) 桥接为 data/*.js
"""
from __future__ import annotations

import json
import statistics as st
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
KC = RAW / "kline_cache"

# ── 口径常量 ──────────────────────────────────────────────────────────────────
COST_PCT = 0.30                      # 双边总成本（%）= 15bps x 2
# 档位 = 全站规范 ladder（HOLD_LADDER：backtest_comprehensive / backtest_tdx /
# gen_algo_track / strategy_four_volume / gen_backtest_all_algos 同源），
# **并保留本卡既有的 T+1/T+2/T+3 短线档**（已在屏、有真实样本，不动）。
# 🔴 2026-09-16 主人令：「这两张卡怎么只有 T+10，要这些」⇒ 补齐 T+20~T+250。
# ⚠️ 长档要能成熟，账本必须留得住信号 —— 见 scripts/gen_strong_breakout.py
#    的 LEDGER_KEEP_DAYS（原 45 天窗口下 T+45 以上结构性不可能有样本）。
HORIZONS = [1, 2, 3, 5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
CST = timezone(timedelta(hours=8))

METHOD = ("信号日次一交易日开盘买入，持有 N 个交易日收盘价卖出"
          "（真实日K；已扣双边交易成本 0.30%）")


# ── 真实日K读取（带缓存，避免同票重复读盘）────────────────────────────────────
_BARS_CACHE: dict = {}


def bars_of(code: str):
    """→ {"dates":[...], "open":{d:px}, "close":{d:px}, "high":{d:px}, "low":{d:px}} 或 None"""
    code = str(code).strip()
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


def one_trade(series, sig_date: str, n: int):
    """单笔 T+N 收益(%)；未成熟/缺价 → None。

    入场 = 信号日次一交易日开盘；出场 = 转日数第 n 个交易日的收盘。
    """
    if not series:
        return None
    ds = series["dates"]
    if sig_date not in ds:
        return None
    si = ds.index(sig_date)
    ei = si + 1                       # 次一交易日开盘买入
    xi = ei + (n - 1)                 # 持有 n 个交易日收盘卖出
    if xi >= len(ds):
        return None                   # 未成熟 —— 绝不当 0
    entry = series["open"].get(ds[ei]) or series["close"].get(ds[ei])
    exit_ = series["close"].get(ds[xi])
    if not entry or not exit_:
        return None                   # 停牌/缺价 —— 跳过
    gross = (exit_ - entry) / entry * 100.0
    # 持仓期内最大回撤（相对持仓期最高收盘）
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
    """全市场等权基准（gen_market_bench.py → raw_data/market_bench.json）；缺文件/解析失败 → {}。"""
    p = RAW / "market_bench.json"
    try:
        return (json.loads(p.read_text(encoding="utf-8")) or {}).get("by_date") or {}
    except Exception:
        return {}


def build_periods(signals, horizons=HORIZONS):
    """signals: [(code, date), ...] → periods dict"""
    periods = {}
    # 🆕 2026-09-17 小九（主人令「全站口径统一·诚实」）：逐档补全市场等权基准。
    #   基准源 raw_data/market_bench.json（与策略同入场/出场/成本口径）；
        #   信号日**精确对齐**（sig_days 即本卡真实信号日）；基准缺该日/该档如实少算，
    #   命中 <5 个基准日不写（宁缺勿滥）。基准是市场事实，与策略档位是否 immature 无关。
    bench = _load_bench()
    sig_days = sorted({d for _, d in signals})
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


def _emit(name: str, payload: dict):
    p = RAW / name
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    n_ok = sum(1 for v in payload.get("periods", {}).values() if v.get("samples"))
    print(f"  ✅ {name}  信号 {payload.get('total_signals')} 笔 · 成熟档 {n_ok}/{len(payload.get('periods', {}))}")


def _envelope(**kw):
    d = {
        "generated": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "method": METHOD,
        "cost_pct_roundtrip": COST_PCT,
        "cost_bps_per_side": 15,
        "cost_adjusted": True,
        "price_source": "raw_data/kline_cache（真实日K缓存）",
        "caliber": "signal_layer",       # 信号层：入场=信号日次一交易日开盘
        "horizons": HORIZONS,
    }
    d.update(kw)
    return d


# ── ① 强势突破 ────────────────────────────────────────────────────────────────
def run_strong_breakout():
    fp = RAW / "strong_breakout_history.json"
    if not fp.exists():
        print("  ⚠️ 缺 raw_data/strong_breakout_history.json，跳过强势突破回测")
        return
    try:
        hist = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠️ strong_breakout_history.json 解析失败: {e}")
        return
    sigs = []
    for d in sorted(k for k in hist if len(str(k)) == 10 and str(k)[4] == "-"):
        for r in (hist.get(d) or []):
            c = str(r.get("code") or "").strip()
            if c:
                sigs.append((c, d))
    if not sigs:
        print("  ⚠️ 强势突破账本为空，跳过")
        return
    days = sorted({d for _, d in sigs})
    _emit("strong_breakout_backtest.json", _envelope(
        card="强势突破",
        signal_source="raw_data/strong_breakout_history.json（逐日真实信号账本）",
        total_signals=len(sigs),
        signal_days=len(days),
        signal_date_range=f"{days[0]} ~ {days[-1]}",
        periods=build_periods(sigs),
    ))


# ── ② 高手强势股跟踪（IMA） ───────────────────────────────────────────────────
def run_ima_strong():
    fp = RAW / "ima_strong_stock.json"
    if not fp.exists():
        print("  ⚠️ 缺 raw_data/ima_strong_stock.json，跳过 IMA 回测")
        return
    try:
        obj = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠️ ima_strong_stock.json 解析失败: {e}")
        return
    sigs, skipped = [], 0
    for x in (obj.get("stocks") or []):
        c = str(x.get("code") or "").strip()
        d = str(x.get("first_selected") or "").strip()
        if c and len(d) == 10 and d[4] == "-":
            sigs.append((c, d))
        else:
            skipped += 1          # 无「首次入选日」的标的无法定位信号时点 —— 如实跳过
    if not sigs:
        print("  ⚠️ IMA 无可定位信号时点的标的，跳过")
        return
    days = sorted({d for _, d in sigs})
    _emit("ima_strong_backtest.json", _envelope(
        card="高手强势股跟踪",
        signal_source="raw_data/ima_strong_stock.json（IMA 同步的真实首次入选日）",
        total_signals=len(sigs),
        skipped_no_signal_date=skipped,
        signal_days=len(days),
        signal_date_range=f"{days[0]} ~ {days[-1]}",
        ima_update_time=obj.get("update_time"),
        periods=build_periods(sigs),
    ))


def main():
    print(f"[backtest_life_cards] ▶ 选股生命周期子页面 · 信号层真实回测 ({datetime.now(CST):%H:%M:%S})")
    print(f"  价格源 raw_data/kline_cache（真实日K） · 成本口径 双边 {COST_PCT}%")
    run_strong_breakout()
    run_ima_strong()
    print("[backtest_life_cards] ✅ 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
