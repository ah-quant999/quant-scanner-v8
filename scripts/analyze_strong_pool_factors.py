#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_strong_pool_factors.py — 强势池「池内因子分组 + 剔 beta」一次性分析（2026-11-15）

目的（主人令「强势跟踪收益率这么高…可以对这种算法选出来的股再因子排序变成最终推荐吗？你分析和建议一下」）：
  验证强势池 T+20 73% / T+45 89% 的高胜率里，有多少是**真 alpha**（相对市场的超额），
  以及池内是否存在**可稳定区分好坏票的因子**，够不够格作为「最终推荐的选池层」。

口径严格复用 algorithms/backtest_life_cards.py：
  - 入场=信号日次一交易日开盘；出场=持有 n 交易日收盘；扣双边 0.30%。
  - 基准=raw_data/market_bench.json 全市场等权、同入场/出场/成本口径。
  - 剔beta超额 = 个股 T+N 收益 − 同信号日市场等权 T+N 收益。

分组维度（池内可用因子）：
  1) strength_score 分层（v2 归档，高强度≥80 vs 中低）  —— 最重要的「池内排序」可行性检验
  2) buy_point 买点类型（v1 归档：连涨强势/回踩etc）
  3) status 状态（正常/回落/见顶）—— 验证「含已回落/见顶」是否拖累
  4) 信号日按月 —— 稳健性 / 是否只是某段行情的beta
  5) T+5/20/45 三档都算（T+5 对齐最终推荐 excess5 口径）

输出：终端结构化报告 + raw_data/strong_pool_factor_analysis.json（供审计，不注入前端）
"""
from __future__ import annotations
import json, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
KC = RAW / "kline_cache"
COST_PCT = 0.30
HORIZONS = [5, 20, 45]


def bars_of(code):
    p = KC / f"{str(code).strip()}.json"
    if not p.exists():
        return None
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(b, dict):
            b = b.get("bars") or b.get("data") or b.get("klines") or []
        rows = []
        for x in b:
            d, c = x.get("date"), x.get("close")
            if not d or c is None:
                continue
            rows.append((str(d), x.get("open"), float(c)))
        rows.sort(key=lambda t: t[0])
        if not rows:
            return None
        return {"dates": [r[0] for r in rows],
                "open": {r[0]: r[1] for r in rows},
                "close": {r[0]: r[2] for r in rows}}
    except Exception:
        return None


def one_trade(series, sig_date, n):
    if not series:
        return None
    ds = series["dates"]
    if sig_date not in ds:
        return None
    si = ds.index(sig_date); ei = si + 1; xi = ei + (n - 1)
    if xi >= len(ds):
        return None
    entry = series["open"].get(ds[ei]) or series["close"].get(ds[ei])
    exit_ = series["close"].get(ds[xi])
    if not entry or not exit_:
        return None
    return round((exit_ - entry) / entry * 100.0 - COST_PCT, 2)


def load_bench():
    try:
        return (json.loads((RAW / "market_bench.json").read_text(encoding="utf-8")) or {}).get("by_date") or {}
    except Exception:
        return {}


def load_sigs(fp, tag):
    if not fp.exists():
        return []
    o = json.loads(fp.read_text(encoding="utf-8"))
    out = []
    for x in (o.get("stocks") or []):
        c = str(x.get("code") or "").strip()
        d = str(x.get("first_selected") or "").strip()
        if not (c and len(d) == 10 and d[4] == "-"):
            continue
        out.append({"code": c, "date": d, "src": tag,
                    "strength_score": x.get("strength_score"),
                    "buy_point": x.get("buy_point"),
                    "status": x.get("status"),
                    "score": x.get("score"),
                    "turnover_pct": x.get("turnover_pct"),
                    "vol_ratio": x.get("vol_ratio")})
    return out


def summarize(name, rows, key):
    """rows: list of dict，每个含 key 字段（数值）→ 返回统计"""
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return {"n": 0}
    wins = sum(1 for v in vals if v > 0)
    return {"n": len(vals),
            "win_rate": round(wins / len(vals) * 100, 1),
            "avg": round(st.mean(vals), 2),
            "median": round(st.median(vals), 2)}


def main():
    bench = load_bench()
    latest = load_sigs(RAW / "ima_strong_stock.json", "latest")
    hist = load_sigs(RAW / "ima_strong_history.json", "hist")
    v2 = load_sigs(RAW / "ima_strong_history_v2.json", "v2")
    # 与生产完全一致的合并：同 code 取最早 first_selected
    merged = {}
    for x in hist + v2 + latest:
        c, d = x["code"], x["date"]
        if c not in merged or d < merged[c]["date"]:
            merged[c] = x
    sigs = sorted(merged.values(), key=lambda x: (x["date"], x["code"]))
    print(f"[强势池因子分析] 信号 {len(sigs)} 笔 | 日期 {sigs[0]['date']} ~ {sigs[-1]['date']}")
    print(f"  来源: latest {len(latest)} / hist {len(hist)} / v2 {len(v2)}\n")

    # 逐笔算个股 T+N 与基准 T+N，得剔beta超额
    detail = []
    for x in sigs:
        bars = bars_of(x["code"])
        rec = dict(x)
        for n in HORIZONS:
            r = one_trade(bars, x["date"], n) if bars else None
            b = None
            if x["date"] in bench:
                bn = bench[x["date"]].get(str(n)) or {}
                b = bn.get("avg")
            rec[f"ret{n}"] = r
            rec[f"bench{n}"] = b
            rec[f"exc{n}"] = round(r - b, 2) if (r is not None and b is not None) else None
        detail.append(rec)

    result = {"generated": "2026-11-15", "total_signals": len(sigs),
              "cost_pct": COST_PCT, "horizons": HORIZONS,
              "groups": {}}

    # ---------- 1) 全样本：个股 vs 基准 vs 剔beta超额 ----------
    print("=" * 78)
    print("【1】全样本：高胜率里有多少是真 alpha？")
    for n in HORIZONS:
        r = summarize("all", detail, f"ret{n}")
        e = summarize("all", detail, f"exc{n}")
        bm = [x[f"bench{n}"] for x in detail if x.get(f"bench{n}") is not None]
        print(f"  T+{n:<2} 个股: n={r['n']:>3} 胜率={r['win_rate']:>5}% 均收={r['avg']:>+7}% "
              f"| 市场等权均收={st.mean(bm):+7.2f}% "
              f"| 剔beta超额: n={e['n']:>3} 超额胜率={e['win_rate']:>5}% 超额均值={e['avg']:>+7}%")
        result["groups"][f"all_t{n}"] = {"ret": r, "excess": e,
                                          "bench_avg": round(st.mean(bm), 2) if bm else None}

    # ---------- 2) strength_score 分层（池内排序可行性核心） ----------
    print("\n" + "=" * 78)
    print("【2】strength_score 分层（v2 归档）：高强度能否显著跑赢低强度？")
    def sband(v):
        if v is None: return None
        try: s = float(v)
        except Exception: return None
        if s >= 90: return "≥90"
        if s >= 85: return "85-89"
        if s >= 80: return "80-84"
        return "<80"
    v2rows = [x for x in detail if x.get("src") == "v2" and x.get("strength_score") is not None]
    by_s = {}
    for x in v2rows:
        by_s.setdefault(sband(x["strength_score"]), []).append(x)
    for band in ["≥90", "85-89", "80-84", "<80"]:
        rows = by_s.get(band, [])
        if not rows: continue
        e20 = summarize(band, rows, "exc20")
        e5 = summarize(band, rows, "exc5")
        print(f"  强度 {band:<6}: n={len(rows):>3} | T+5超额 n={e5.get('n',0):>3} 均={e5.get('avg','NA'):>7} "
              f"胜率={e5.get('win_rate','NA')}% | T+20超额 n={e20.get('n',0):>3} 均={e20.get('avg','NA'):>7} 胜率={e20.get('win_rate','NA')}%")
        result["groups"][f"strength_{band}"] = {"n": len(rows), "exc5": e5, "exc20": e20}
    # 高(≥85) vs 低(<85) 对比
    hi = [x for x in v2rows if (sband(x["strength_score"]) in ("≥90", "85-89"))]
    lo = [x for x in v2rows if (sband(x["strength_score"]) in ("80-84", "<80"))]
    if hi and lo:
        eh, el = summarize("hi", hi, "exc20"), summarize("lo", lo, "exc20")
        print(f"  → 高(≥85) n={eh['n']} 超额={eh['avg']}% vs 低(<85) n={el['n']} 超额={el['avg']}%  "
              f"差={round(eh['avg']-el['avg'],2)}pct")

    # ---------- 3) buy_point 买点类型 ----------
    print("\n" + "=" * 78)
    print("【3】buy_point 买点类型（v1 归档）：哪类买点有超额？")
    by_bp = {}
    for x in detail:
        bp = x.get("buy_point")
        if not bp: continue
        by_bp.setdefault(str(bp), []).append(x)
    for bp, rows in sorted(by_bp.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < 5: continue
        e20 = summarize(bp, rows, "exc20")
        print(f"  {bp:<14}: n={len(rows):>3} | T+20超额 n={e20.get('n',0):>3} 均={e20.get('avg','NA'):>7} 胜率={e20.get('win_rate','NA')}%")
        result["groups"][f"buypoint_{bp}"] = {"n": len(rows), "exc20": e20}

    # ---------- 4) status 状态（幸存者偏差检验） ----------
    print("\n" + "=" * 78)
    print("【4】status 状态：已回落/见顶票是否拖累？（验证「防幸存者偏差」代价）")
    by_st = {}
    for x in detail:
        s = x.get("status")
        if not s: continue
        by_st.setdefault(str(s), []).append(x)
    for s, rows in sorted(by_st.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < 5: continue
        e20 = summarize(s, rows, "exc20")
        print(f"  {s:<10}: n={len(rows):>3} | T+20超额 n={e20.get('n',0):>3} 均={e20.get('avg','NA'):>7} 胜率={e20.get('win_rate','NA')}%")
        result["groups"][f"status_{s}"] = {"n": len(rows), "exc20": e20}

    # ---------- 5) 信号日按月：稳健性 ----------
    print("\n" + "=" * 78)
    print("【5】信号日按月：超额是否稳定，还是只靠某段行情？")
    by_m = {}
    for x in detail:
        m = x["date"][:7]
        by_m.setdefault(m, []).append(x)
    for m in sorted(by_m):
        rows = by_m[m]
        e20 = summarize(m, rows, "exc20")
        print(f"  {m}: n={len(rows):>3} | T+20超额 n={e20.get('n',0):>3} 均={e20.get('avg','NA'):>8} 胜率={e20.get('win_rate','NA')}%")
        result["groups"][f"month_{m}"] = {"n": len(rows), "exc20": e20}

    out = RAW / "strong_pool_factor_analysis.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 明细已存 {out}（仅供审计，未注入前端）")


if __name__ == "__main__":
    main()
