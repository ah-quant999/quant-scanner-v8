#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一进二/二进三 入选口径升级证据回测（2026-10-24 主人令「确认真的有收益率的提升才开始动手」）

【背景】真实信号流（lianban_winrate.py，10-16 起）T+1 已结仅 176 / T+5 仅 51——样本不足以
裁决任何口径改动。本工具用本地 kline_cache 全市场（~5300 只 × 251 交易日）重建
首板/二连板事件大样本，对候选入选口径做有统计功效的证据回测。

【口径（与 v8/lianban_winrate.py 生产完全对齐）】
  涨停判定   close >= round(prev_close×(1+幅),2)，幅=主板10%/双创20%/北交30%（剔 ST/退）
  一字板剔除 开=高=低=收 的信号日剔除（与生产同）
  首板       当日涨停 & 前一日未涨停；二连板 = 连续两日涨停
  倍量 VR    当日量 / 前 20 日均量（不含当日）
  晋级率     次日收盘涨停占比
  隔夜高开   次日开盘 > 信号日收盘 占比
  T+1 胜率   次日开盘买 → 次日收盘卖，净收益 > 0.3% 占比
  可成交T+1  同上，仅次日开盘非一字板（现实中买得进）子集
  T+5 胜率   次日开盘买 → 第 5 个交易日收盘卖，净收益 > 0.3% 占比

【候选口径（全部仅用 K 线可得，零未来函数）】
  B0  全体首板（基线）
  B1  VR>=3（现役①入选口径）
  B2  VR 3~5（现役子桶）
  B3  VR<3 缩量首板
  B4  VR 1~2 温和缩量
  B5  非一字 + 高=收（收盘封死）+ VR 1~3
  B6  首板 + 收盘价 > MA20
  B7  二连板全体
  B8  二连板缩量 VR<3

【预注册判优】候选须在 train(2025-10→2026-06) 与 holdout(2026-07→) **同向**满足：
  ① 晋级率 > B0 基线 ≥ +3pct ② 可成交T+1胜率 > B0 ≥ +3pct ③ 桶内 n_holdout ≥ 100
  全部满足 → 建议改 lianban_winrate.py 入选口径；否则如实「无可靠提升」。

输出：控制台对比表 + raw_data/lianban_upgrade_backtest_report.json
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "lianban_upgrade_backtest_report.json")

VR_WIN = 20
COST = 0.003
SPLIT = "2026-07-01"          # train / holdout 切分


def log(m):
    print(m, flush=True)


def load_names():
    """剔 ST/退（与生产同）。"""
    try:
        d = json.load(open(os.path.join(RAW, "stock_names.json")))
        out = {}
        for s in (d.get("data") or []):
            fc = s.get("full_code") or ""
            if isinstance(fc, str) and fc.startswith(("sh", "sz")):
                c6 = fc[2:]
                if c6.isdigit():
                    out[c6] = s.get("name") or ""
        return {c: n for c, n in out.items()
                if "ST" not in n.upper() and "退" not in n}
    except Exception:
        return None


def limit_ratio(code):
    if code.startswith(("300", "301", "688")):
        return 0.20
    if code.startswith(("43", "83", "87", "88", "92")):
        return 0.30
    return 0.10


def is_limit(rec, prev_close, ratio):
    c = rec.get("close")
    if not c or not prev_close or prev_close <= 0:
        return False
    return c >= round(prev_close * (1 + ratio), 2) - 1e-6


def main():
    t0 = time.time()
    log("=" * 88)
    log("  一进二/二进三 入选口径大样本证据回测（kline_cache 全市场重建）  %s"
        % datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 88)

    names = load_names()
    codes = [f[:-5] for f in os.listdir(os.path.join(RAW, "kline_cache"))
             if f.endswith(".json") and f[:-5].isdigit() and len(f[:-5]) == 6]
    log("kline_cache：%d 只（names 过滤 %s）" % (len(codes), "开启" if names else "不可用"))

    feats = ["first_all", "first_vr3", "first_vr3_5", "first_vr_lt3", "first_vr1_2",
             "first_seal_vr1_3", "first_ma20", "second_all", "second_vr_lt3"]
    # 每事件记录: dict(split, type, bucket 标记, 晋级, 高开, t1win, t1ok, t5win, t5ok)
    events = []
    n_stock = 0
    for code in codes:
        if names is not None and code not in names:
            continue
        try:
            d = json.load(open(os.path.join(RAW, "kline_cache", code + ".json")))
            recs = d if isinstance(d, list) else (d.get("data") or d.get("kline") or [])
        except Exception:
            continue
        if len(recs) < VR_WIN + 8:
            continue
        n_stock += 1
        ratio = limit_ratio(code)
        lim = [False] * len(recs)
        for i in range(1, len(recs)):
            lim[i] = is_limit(recs[i], recs[i - 1].get("close"), ratio)
        for i in range(VR_WIN, len(recs) - 2):
            r = recs[i]
            o, h, l, c, v = (r.get("open"), r.get("high"), r.get("low"),
                             r.get("close"), r.get("volume") or 0)
            if not (o and h and l and c) or v <= 0:
                continue
            if not lim[i]:
                continue
            # 一字板剔除（与生产同）
            if o == h == l == c:
                continue
            prev_vols = [x.get("volume") or 0 for x in recs[i - VR_WIN:i]]
            mv = sum(prev_vols) / VR_WIN
            if mv <= 0:
                continue
            vr = v / mv
            is_first = not lim[i - 1]
            is_second = lim[i - 1] and i >= 2 and not lim[i - 2]
            if not (is_first or is_second):
                continue
            # 前瞻：次日与 T+5
            nb = recs[i + 1]
            no, nc, nv = nb.get("open"), nb.get("close"), nb.get("volume") or 0
            if not no or no <= 0 or nv <= 0 or not nc:
                continue
            promote = is_limit(nb, c, ratio)
            gap_up = no > c
            next_limit_px = round(c * (1 + ratio), 2)
            buyable = no < next_limit_px - 1e-6        # 次日开盘非一字板
            t1 = nc / no - 1.0 - COST
            t5 = None
            if i + 1 + 5 < len(recs):
                px5 = recs[i + 1 + 5].get("open") if False else recs[i + 5].get("close")
                # 生产口径：次日开盘买 → 第 5 个交易日收盘卖（T+5 收盘=recs[i+5].close，
                # i+1 买入日为第 1 个交易日，i+5 为第 5 个）
                if px5 and px5 > 0:
                    t5 = px5 / no - 1.0 - COST
            ev = {
                "split": "train" if r["date"] < SPLIT else "holdout",
                "first": is_first,
                "vr": vr,
                "promote": promote, "gap": gap_up,
                "t1": t1, "buyable": buyable,
                "t5": t5,
                "seal": (h == c),
                "ma20": c > (sum(x.get("close") or 0 for x in recs[i - 19:i + 1]) / 20.0),
            }
            events.append(ev)
        if n_stock % 1000 == 0:
            log("  [%ds] 已扫 %d 只，事件 %d" % (time.time() - t0, n_stock, len(events)))

    log("完成：%d 只股票，首板/二板事件 %d 个（%.1fs）" % (n_stock, len(events), time.time() - t0))

    def bucket(e):
        if not e["first"]:
            return "second_vr_lt3" if e["vr"] < 3 else "second_all"
        if e["vr"] >= 3:
            return "first_vr3"
        if e["vr"] >= 5:
            return "first_vr3"      # 不可能（vr>=5 落入 >=3）
        return None

    def assign(e):
        out = []
        if e["first"]:
            out.append("first_all")
            if e["vr"] >= 3:
                out.append("first_vr3")
            if 3 <= e["vr"] < 5:
                out.append("first_vr3_5x")     # 3~5
            if e["vr"] < 3:
                out.append("first_vr_lt3")
            if 1 <= e["vr"] < 2:
                out.append("first_vr1_2")
            if e["seal"] and 1 <= e["vr"] < 3:
                out.append("first_seal_vr1_3")
            if e["ma20"]:
                out.append("first_ma20")
        else:
            out.append("second_all")
            if e["vr"] < 3:
                out.append("second_vr_lt3")
        return out

    def stat(sub, with_t5=True):
        n = len(sub)
        if n == 0:
            return None
        s = {
            "n": n,
            "promote": sum(1 for e in sub if e["promote"]) / n * 100,
            "gap": sum(1 for e in sub if e["gap"]) / n * 100,
        }
        t1s = [e["t1"] for e in sub]
        s["t1_win"] = sum(1 for x in t1s if x > 0) / n * 100
        s["t1_avg"] = sum(t1s) / n * 100
        bs = [e for e in sub if e["buyable"]]
        s["n_buyable"] = len(bs)
        s["t1_win_buyable"] = (sum(1 for e in bs if e["t1"] > 0) / len(bs) * 100) if bs else None
        s["t1_avg_buyable"] = (sum(e["t1"] for e in bs) / len(bs) * 100) if bs else None
        t5s = [e["t5"] for e in sub if e["t5"] is not None]
        s["n_t5"] = len(t5s)
        s["t5_win"] = (sum(1 for x in t5s if x > 0) / len(t5s) * 100) if t5s else None
        s["t5_avg"] = (sum(t5s) / len(t5s) * 100) if t5s else None
        return s

    # 基线（train 全体首板）
    base_tr = stat([e for e in events if e["first"] and e["split"] == "train"])
    base_ho = stat([e for e in events if e["first"] and e["split"] == "holdout"])

    groups = ["first_all", "first_vr3", "first_vr3_5x", "first_vr_lt3", "first_vr1_2",
              "first_seal_vr1_3", "first_ma20", "second_all", "second_vr_lt3"]
    label = {
        "first_all": "全体首板(基线)", "first_vr3": "首板VR>=3(现役①)", "first_vr3_5x": "首板VR3~5",
        "first_vr_lt3": "首板VR<3缩量", "first_vr1_2": "首板VR1~2温和",
        "first_seal_vr1_3": "首板封死+VR1~3", "first_ma20": "首板收盘>MA20",
        "second_all": "二连板全体(基线)", "second_vr_lt3": "二板缩量VR<3",
    }
    result = {}
    log("")
    log("%-18s %-6s %7s %8s %9s %9s %8s %9s" %
        ("口径", "段", "n", "晋级率", "可成交T+1胜", "T+1均益", "T+5胜", "T+5均益"))
    for g in groups:
        for sp in ("train", "holdout"):
            sub = [e for e in events if g in assign(e) and e["split"] == sp]
            s = stat(sub)
            if not s:
                continue
            result.setdefault(g, {})[sp] = s
            log("%-18s %-6s %7d %7.1f%% %9.1f%% %8.2f%% %7.1f%% %8.2f%%" %
                (label[g], "训练" if sp == "train" else "保留", s["n"], s["promote"],
                 s["t1_win_buyable"] if s["t1_win_buyable"] is not None else -1,
                 s["t1_avg_buyable"] if s["t1_avg_buyable"] is not None else -1,
                 s["t5_win"] if s["t5_win"] is not None else -1,
                 s["t5_avg"] if s["t5_avg"] is not None else -1))
        log("")

    # 预注册判优（首板口径 vs B0 基线）
    log("=" * 88)
    log("预注册判优（须 train/holdout 同向：①晋级率 > 基线+3pct ②可成交T+1胜率 > 基线+3pct ③holdout n>=100）")
    verdicts = {}
    for g in ["first_vr3", "first_vr3_5x", "first_vr_lt3", "first_vr1_2",
              "first_seal_vr1_3", "first_ma20"]:
        ok = {}
        for sp, base in (("train", base_tr), ("holdout", base_ho)):
            s = result.get(g, {}).get(sp)
            if not s or not base:
                ok[sp] = False
                continue
            c1 = s["promote"] - base["promote"] >= 3.0
            c2 = (s["t1_win_buyable"] or -1) - (base["t1_win_buyable"] or -1) >= 3.0
            c3 = s["n"] >= 100 if sp == "holdout" else True
            ok[sp] = c1 and c2 and c3
        passed = ok["train"] and ok["holdout"]
        verdicts[g] = {"train_pass": ok["train"], "holdout_pass": ok["holdout"], "pass": passed}
        log("  %-18s 训练:%s 保留:%s ⇒ %s" % (label[g],
            "✅" if ok["train"] else "❌", "✅" if ok["holdout"] else "❌",
            "通过（可建议改入选口径）" if passed else "否决"))

    n_pass = sum(1 for v in verdicts.values() if v["pass"])
    log("")
    log("⇒ 总判定：%s" % ("有 %d 个口径通过预注册判优，可进入生产改造评估" % n_pass
                          if n_pass else "无口径可靠优于全体首板基线——证据否决改动，如实落档"))

    json.dump({
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "一进二/二进三入选口径升级证据回测（主人令：确认提升才动手）",
        "universe": n_stock, "n_events": len(events), "split": SPLIT,
        "caliber": "与 v8/lianban_winrate.py 生产对齐（VR=当日量/前20日均量，一字板剔除，成本0.3%）",
        "baseline": {"train": base_tr, "holdout": base_ho},
        "groups": result, "verdicts": verdicts,
    }, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("[ok] %s" % OUT)


if __name__ == "__main__":
    main()
