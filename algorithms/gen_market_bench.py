#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全市场等权基准生成器（供回测/星级剔除大盘 β）—— 2026-09-17 阿狸咪的工程师

──────────── 为什么要这个东西 ────────────
主人 2026-09-17 令：「审计策略星级评判的科学性」。审计发现星级算法**没有基准维度**
（第③/⑥处缺陷）⇒ 分不清「+41.6pp 真 alpha」与「+10.5pp 靠大盘涨」，星级实际混入 β。
更糟的是短周期惩罚的参照系是**绝对 50% 胜率**，而弱市里全市场基准本身就只有 44.9%
⇒ 所有策略被一刀切，「罚的不是烂，是大盘跌」。

本脚本按**与各策略完全相同的时间口径**（每交易日为信号日 · 次一交易日开盘买入 ·
持有 N 个交易日收盘卖出 · 扣双边 0.30%），算出全市场等权基准的逐日序列，
供聚合器按各卡各自的信号区间求平均 ⇒ 写进 rows[].extra.bench_avg_return / bench_win_rate。

──────────── 口径三条铁律 ────────────
① **同源同口径**：入场/出场/成本与 strategy_*.py 完全一致（否则基准不可比）。
② **逐日全市场等权**：每日用「当日真实有数据」的全部股票算平均，不筛选、不加权、不剔除
   （剔涨跌停/ST 会引入选择偏差；等权即市场本身）。
③ **不猜**：某日样本 < MIN_UNIVERSE 则不产出该日该档（宁缺勿滥），聚合器侧按缺失处理。

──────────── 已知局限（如实标注，不隐瞒）────────────
· 数据源 `raw_data/kline_cache` 是**冻结快照**（get_kline 命中即返回、永不回补）。
  本脚本只依赖**历史段**（策略区间均早于各文件末根），故不受该缺陷影响；
  但**最近 3~5 个交易日**的基准会因末根散落而偏薄 ⇒ 由 MIN_UNIVERSE 兜底为「无数据」。
· 未做行业/市值中性化（v8 定位轻量，不做过度工程）。
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDS = [1, 2, 3, 5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
COST_PCT = 0.30          # 双边合计，与各 strategy_*.py 一致
MIN_UNIVERSE = 200       # 某日有效样本少于此数 ⇒ 该日该档不出数
START = "2025-01-01"     # 逐日序列起始（覆盖所有策略区间）


def _bars(path):
    try:
        b = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    if isinstance(b, dict):
        b = b.get("bars") or b.get("data") or b.get("klines") or []
    return b if isinstance(b, list) and b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=None,
                    help="输出 JSON 路径（默认 <root>/raw_data/market_bench.json）")
    ap.add_argument("--start", default=START)
    ap.add_argument("--min-universe", type=int, default=MIN_UNIVERSE)
    a = ap.parse_args()

    root = Path(a.root)
    cache = root / "raw_data" / "kline_cache"
    files = sorted(glob.glob(str(cache / "*.json")))
    print(f"[market_bench] {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  缓存目录: {cache}")
    print(f"  文件数:   {len(files)}")

    # ── 第一遍：把每只股票的 (日期→索引) 与序列读进内存（3120 只 × ~250 根，约 100MB 级）
    #    为控内存，按「日期 → [(code, idx)]」反向索引构建。
    day_index = {}          # date -> {code: idx}
    seq = {}                # code -> (dates, opens, closes)
    for p in files:
        code = Path(p).stem
        b = _bars(p)
        if not b or len(b) < 30:
            continue
        try:
            dates = [str(x.get("date"))[:10] for x in b]
            opens = [x.get("open") for x in b]
            closes = [x.get("close") for x in b]
        except Exception:
            continue
        seq[code] = (dates, opens, closes)
        for i, d in enumerate(dates):
            if d >= a.start:
                day_index.setdefault(d, {})[code] = i
    print(f"  可用股票: {len(seq)}   覆盖交易日: {len(day_index)}")

    # ── 第二遍：逐日 × 逐持有期算全市场等权基准
    by_date = {}
    for d in sorted(day_index):
        codes = day_index[d]
        per_hold = {}
        for h in HOLDS:
            rets = []
            for code, i in codes.items():
                dates, opens, closes = seq[code]
                bi = i + 1                    # 次一交易日开盘买入
                si = i + 1 + h - 1            # 持有 h 个交易日后收盘卖出 = i+h
                if bi >= len(closes) or si >= len(closes):
                    continue
                bo, sc, sc0 = opens[bi], closes[si], closes[i]
                if not bo or not sc or not sc0 or bo <= 0:
                    continue
                rets.append((sc / bo - 1) * 100 - COST_PCT)
            if len(rets) >= a.min_universe:
                rets.sort()
                per_hold[str(h)] = {
                    "avg": round(sum(rets) / len(rets), 4),
                    "win": round(sum(1 for x in rets if x > 0) / len(rets) * 100, 2),
                    "med": round(rets[len(rets) // 2], 4),
                    "n": len(rets),
                }
        if per_hold:
            by_date[d] = per_hold

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": ("全市场等权基准 · 每交易日为信号日 · 次一交易日开盘买入 · "
                   f"持有 N 个交易日收盘卖出 · 扣双边 {COST_PCT}%"),
        "cost_pct_roundtrip": COST_PCT,
        "universe_files": len(files),
        "universe_used": len(seq),
        "holds": HOLDS,
        "start": a.start,
        "min_universe": a.min_universe,
        "by_date": by_date,
    }

    outp = Path(a.out) if a.out else (root / "raw_data" / "market_bench.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8", newline="\n")
    print(f"  ✅ 写出 {outp}  ({outp.stat().st_size} B)")
    print(f"  逐日档数: {len(by_date)}   日期范围: "
          f"{(min(by_date) if by_date else '—')} ~ {(max(by_date) if by_date else '—')}")
    # 抽查：策略区间上的基准
    for d1, d2 in [("2026-06-09", "2026-08-24")]:
        for h in [1, 5, 30]:
            vs = [by_date[d][str(h)] for d in by_date if d1 <= d <= d2 and str(h) in by_date[d]]
            if vs:
                avg = sum(v["avg"] for v in vs) / len(vs)
                win = sum(v["win"] for v in vs) / len(vs)
                print(f"    基准 {d1}~{d2}  T+{h}: 均收益 {avg:+.2f}%  胜率 {win:.1f}%  ({len(vs)} 日)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
