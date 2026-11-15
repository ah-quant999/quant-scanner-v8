#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_final_recommend_replay.py — 最终推荐 Top3 · 全 OOS 段历史回放回测（口径 A+）

🔴 2026-11-15 主人令「能用新算法回测前面的数据吗，就不用再等 2-4 周了」
   + 后续确认「全 OOS 段 + 数据文件 + 报告」。

【这是什么 / 不是什么】（必须在产物里如实标注，禁止混淆）
  · 是：用【历史归档当日真实产出的 Top3 + 当日 final_score】做收益回放——
    信号是当时真实选出的票、分数是当时真实落盘的分数（无前视、非事后重算），
    只把收益按真实日 K 兑现，回答「这套最终推荐在 OOS 段其实能不能赚钱」。
  · 不是：不是实盘真跑（当日没有真实下单），不是历史规则回放（不重跑选股逻辑、
    不含当前股池幸存者偏差）。另有 gen_final_recommend_backtest.py 走 11-01 后
    真实信号流口径（当前仅 9 笔、3 入场日、20d+ immature，不能作收益结论）。

【范围】OOS 段 2026-09-20 ~ 2026-11-13。
  · 实证归档：09-20~10-31 有 32 个有效信号日 / 124 笔 Top3；
    11-01~11-13 归档全空（断流期，无信号可回放）——如实标注，不伪造。
  · 09-20 是 final_score 唯一口径=因子榜 total_score 的生效日，之前旧算法样本剔除。

【口径】（逐字复用 gen_final_recommend_backtest.py，保证跨卡可比）
  · 信号 = 归档 stocks（当日真实 Top3，含 code/name/rank/final_score）
  · 归因日：update_time 小时 < 9 ⇒ 归前一自然夜（NIGHT_CUT 同源）
  · 入场：归因日之后首个可交易日开盘；出场：持有 N 交易日收盘
  · 成本：双边 0.30%；未成熟/缺价 → None（绝不当 0）
  · 剔 beta = 个股收益 − 同信号日市场等权收益（market_bench.json，逐日对照）
  · 收益档：T+1/2/3/5/10/20（有样本的档才出结论，缺样本标 immature）

【输出】
  - raw_data/final_recommend_replay.json
  - data/FINAL_RECOMMEND_REPLAY.js          (window.FINAL_RECOMMEND_REPLAY)
  - 结构化报告：收益率最高 / 胜率最高 / 剔 beta 超额（写进 json 的 report 段）

用法：
  python algorithms/gen_final_recommend_replay.py --dry   # 只打印不写（默认安全）
  python algorithms/gen_final_recommend_replay.py --write  # 落盘正式产物
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 复用成熟回测口径（开盘入/收盘出/0.30%/剔beta/bars_of），禁止另起炉灶
import gen_final_recommend_backtest as bt  # noqa: E402

RAW = ROOT / "raw_data"
DATA = ROOT / "data"
HIST = RAW / "history"

OOS_START = "2026-09-20"
OOS_END = "2026-11-13"
HORIZONS = [1, 2, 3, 5, 10, 20]
COST_PCT = bt.COST_PCT  # 0.30


def load_signals():
    """→ (signals[(code,name,date,final_score,rank)], days_info, empty_days)"""
    signals = []
    days = []
    empty = []
    for p in sorted(HIST.glob("final_recommend_*.json")):
        d8 = p.stem.replace("final_recommend_", "")
        try:
            fd = dt.date.fromisoformat(d8).isoformat()
        except Exception:
            continue
        if not (OOS_START.replace("-", "") <= d8 <= OOS_END.replace("-", "")):
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        attributed = bt._attributed_date(doc.get("update_time"), fd)
        stocks = doc.get("stocks") or []
        if not stocks:
            empty.append(fd)
            continue
        ds = []
        for s in stocks:
            c = str(s.get("code") or "").strip().lstrip(".")
            if not c:
                continue
            fs = s.get("final_score")
            fs = float(fs) if isinstance(fs, (int, float)) else None
            signals.append((c, str(s.get("name") or ""), attributed, fs, s.get("rank")))
            ds.append(c)
        days.append({"date": attributed, "file_date": fd, "codes": ds,
                     "update_time": (doc.get("update_time") or "")[:19]})
    return signals, days, empty


def per_horizon(signals):
    """按档算收益/胜率/剔beta，并留每笔明细（供「最高收益/最高胜率个股」）。"""
    bench = bt._load_bench()
    out = {}
    for n in HORIZONS:
        recs = []
        for code, name, date, fs, rank in signals:
            r = bt.one_trade(bt.bars_of(code), date, n)
            if r is None:
                continue
            ret, mdd = r
            b = None
            # 剔beta：同信号日市场等权收益（按归因日，逐日对照）
            bd = bench.get(date) or {}
            bv = bd.get(str(n))
            if isinstance(bv, dict) and bv.get("avg") is not None:
                b = float(bv["avg"])
            recs.append({"code": code, "name": name, "date": date,
                         "final_score": fs, "rank": rank,
                         "return_pct": ret, "bench_pct": b,
                         "excess_pct": (round(ret - b, 2) if b is not None else None),
                         "mdd_pct": mdd})
        if not recs:
            out[f"{n}d"] = {"samples": 0, "immature": True, "records": []}
            continue
        rets = [x["return_pct"] for x in recs]
        exc = [x["excess_pct"] for x in recs if x["excess_pct"] is not None]
        win = sum(1 for r in rets if r > 0)
        out[f"{n}d"] = {
            "samples": len(rets),
            "immature": False,
            "win": win,
            "loss": len(rets) - win,
            "win_rate": round(win / len(rets) * 100.0, 1),
            "avg_return": round(sum(rets) / len(rets), 2),
            "median_return": round(st.median(rets), 2),
            "best_return": round(max(rets), 2),
            "worst_return": round(min(rets), 2),
            "max_drawdown": round(sum(x["mdd_pct"] for x in recs) / len(recs), 2),
            "excess_samples": len(exc),
            "avg_excess": round(sum(exc) / len(exc), 2) if exc else None,
            "excess_win_rate": round(sum(1 for e in exc if e > 0) / len(exc) * 100.0, 1) if exc else None,
            "records": recs,
        }
    return out


def build_report(periods):
    """结构化结论：收益率最高 / 胜率最高 / 剔beta超额最高（单票，≥3样本档优先 5d/10d）。"""
    def rank_key(code, name, metric):
        return {"code": code, "name": name, "metric": metric}

    # 汇总每只票在 5d / 10d 的表现（样本足够的核心档）
    agg = {}
    for key in ("5d", "10d"):
        p = periods.get(key) or {}
        for r in p.get("records") or []:
            a = agg.setdefault(r["code"], {"name": r["name"], "rets": [], "excess": []})
            a["rets"].append(r["return_pct"])
            if r["excess_pct"] is not None:
                a["excess"].append(r["excess_pct"])
    rows = []
    for code, a in agg.items():
        if not a["rets"]:
            continue
        avg = sum(a["rets"]) / len(a["rets"])
        wr = sum(1 for x in a["rets"] if x > 0) / len(a["rets"]) * 100
        ae = (sum(a["excess"]) / len(a["excess"])) if a["excess"] else None
        rows.append({"code": code, "name": a["name"], "n": len(a["rets"]),
                     "avg_return": round(avg, 2), "win_rate": round(wr, 1),
                     "avg_excess": round(ae, 2) if ae is not None else None})
    report = {}
    if rows:
        best_ret = max(rows, key=lambda x: x["avg_return"])
        report["收益率最高"] = {**rank_key(best_ret["code"], best_ret["name"], "5d/10d 平均收益"),
                              "avg_return": best_ret["avg_return"], "n": best_ret["n"]}
        # 胜率最高：n>=2 防单样本 100% 误报
        multi = [x for x in rows if x["n"] >= 2] or rows
        best_wr = max(multi, key=lambda x: (x["win_rate"], x["n"]))
        report["胜率最高"] = {**rank_key(best_wr["code"], best_wr["name"], "5d/10d 胜率"),
                            "win_rate": best_wr["win_rate"], "n": best_wr["n"]}
        ex = [x for x in rows if x["avg_excess"] is not None]
        if ex:
            best_ex = max(ex, key=lambda x: x["avg_excess"])
            report["剔beta超额最高"] = {**rank_key(best_ex["code"], best_ex["name"], "5d/10d 平均超额"),
                                    "avg_excess": best_ex["avg_excess"], "n": best_ex["n"]}
    # 各档一句结论
    summary = []
    for n in HORIZONS:
        p = periods.get(f"{n}d") or {}
        if p.get("immature") or not p.get("samples"):
            summary.append(f"T+{n}: 样本不足，无结论")
        else:
            summary.append(f"T+{n}: {p['samples']}笔 胜率{p['win_rate']}% "
                           f"均值{p['avg_return']}% 超额{p['avg_excess']}%")
    report["各档结论"] = summary
    # 🔴 样本警示（铁律：不得用 n=2 的 100% 胜率冒充「胜率最高的票」误导选股）
    report["样本警示"] = ("收益率最高/胜率最高均为个股累计 2 笔的小样本极值，"
                       "不具统计意义，禁止当作选股结论；可信结论以全样本各档胜率/超额为准。")
    # 🔴 口径真相：本段是 11-01 修复前旧算法（四量终极为主）的真实信号，非新算法历史成绩
    report["口径真相"] = ("09-20~10-31 归档 Top3 以已下架的「四量终极」为主，属 11-01 修复前旧算法；"
                      "全样本 T+2 起转负，印证下架正确。11-01~11-13（修复后新算法期）归档全空，"
                      "无信号可回放——本回放不是「新算法历史成绩」，新算法须等真实流积累验证。")
    return report, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印不写（默认）")
    ap.add_argument("--write", action="store_true", help="写正式产物")
    args = ap.parse_args(argv)
    do_write = args.write and not args.dry

    signals, days, empty = load_signals()
    periods = per_horizon(signals)
    report, rows = build_report(periods)

    # 真实时间基准：优先 GitHub API Date，否则本机 UTC+8（禁止用裸本机时钟写未来时间戳）
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.github.com", timeout=6) as resp:
            hd = resp.headers.get("Date")
        if hd:
            gen = dt.datetime.strptime(hd, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=dt.timezone.utc)
            gen = gen.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
        else:
            raise ValueError("no Date header")
    except Exception:
        gen = (dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))

    out = {
        "generated": gen,
        "card": "最终推荐 Top3 · 全 OOS 段历史回放回测（口径 A+）",
        "method": "历史回放：归档当日真实 Top3 + 当日 final_score（无前视），"
                  "次一交易日开盘买入，持有 N 交易日收盘卖出，扣双边成本 0.30%；"
                  "剔beta=个股收益−同日全市场等权收益",
        "disclaimer": "历史回放 ≠ 实盘真跑；信号为归档真实选股但当日无真实下单。"
                      "11-01~11-13 归档全空（断流期）无信号可回放，未伪造补齐。"
                      "本段信号以 11-01 修复前旧算法（四量终极）为主，非新算法历史成绩。",
        "oos_start": OOS_START, "oos_end": OOS_END,
        "signal_days": len(days),
        "signal_trades": len(signals),
        "empty_days": empty,
        "cost_pct": COST_PCT,
        "horizons": HORIZONS,
        "periods": periods,
        "report": report,
        "by_stock": sorted(rows, key=lambda x: -x["avg_return"]),
        "signal_day_list": days,
    }

    print(f"[回放] OOS {OOS_START}~{OOS_END} 信号日={len(days)} 笔数={len(signals)} 空档日={len(empty)}")
    for k in HORIZONS:
        p = periods.get(f"{k}d") or {}
        if p.get("samples"):
            print(f"  T+{k:<2}: n={p['samples']:>3} 胜率={p['win_rate']}% "
                  f"均值={p['avg_return']}% 超额={p['avg_excess']}% 剔beta胜率={p['excess_win_rate']}%")
        else:
            print(f"  T+{k:<2}: 样本不足")
    print("[结论]", json.dumps(report, ensure_ascii=False))

    if do_write:
        (RAW / "final_recommend_replay.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        js = "window.FINAL_RECOMMEND_REPLAY = " + json.dumps(out, ensure_ascii=False, indent=2) + ";"
        (DATA / "FINAL_RECOMMEND_REPLAY.js").write_text(js, encoding="utf-8")
        print(f"[ok] 写入 raw_data/final_recommend_replay.json + data/FINAL_RECOMMEND_REPLAY.js "
              f"(generated={gen})")
    else:
        print("[dry] 未写盘（加 --write 落盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
