#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_ic_gate.py — Tier 1 第 1 步「IC 门禁 MVP」

读：
  - raw_data/factor_ic_report.json     # v8_factor_ic.py 产出（滚动 IC）
  - raw_data/factor_validate_report.json # v8_factor_validate.py 产出（固定样本 win）
  - raw_data/h_auto_buy_track.json（可选）# H 反推累计胜率

写：
  - raw_data/ic_gate.json  # 每日门禁状态。供 generate_top10 / gen_triple_consensus
                           # 在算分前 require 这个 gate，决定当日某策略是否出票。

2026-11-27 主人令「IC 门禁改用真 OOS」：
  取样优先级 = out_of_sample > fixed_sample > in_sample；产物带 sample_used / oos_disclosure，
  不再让样本内乐观胜率单独决定门禁。

MVP 原则（2026-08-29 主人放行）：
  1. 只产出门禁信号文件，**不改任何选股逻辑**——最小杠杆。
  2. 缺数据时 gate = "insufficient_data"（保守默认值，避免空仓一日）。
  3. 阈值写进文件本身，方便主人日后一句话微调：
        T1_win < min_T1_win    → gate fail（策略当日不出票）
        fixed_T1_win < X       → 准入门禁（替代样本内乐观胜率）

落地路径：
  下游消费（建议一并提交）：
   - algorithms/generate_top10.py:614 的 score_backtest 用 ic_gate.json 中的 ic_weight 做额外微调
   - algorithms/gen_triple_consensus.py / calc_crds.py 在 select 前读 gate 字段做"准出门禁"
  本脚本 v1 仅产出 JSON + 终端摘要，**消费端接入下一步执行**。
"""
import os, json, sys, time, argparse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

THRESH = {
    "min_T1_win": 45.0,        # T+1 实测胜率 < 45% 当日不出票（近于随机）
    "min_T3_win": 35.0,        # T+3 < 35% 报警但允许出（短持有场景）
    "min_T5_win": 30.0,        # T+5 < 30% 关闭策略
    "min_fixed_T1_win": 47.0,  # 滚动固定样本（防样本内乐观）< 47% 关闭
    "min_fixed_T3_win": 32.0,
    "min_n_signals": 80,       # 样本量过低不算数（保留为 insufficient_data）
}

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return default

def _n_of(overall, fallback=0):
    """取某样本 overall 的 T1 样本量（各档 n 略有差异，统一用 T1 作代表）。"""
    try:
        n = int(((overall or {}).get("T1") or {}).get("n"))
    except Exception:
        n = 0
    return n if n > 0 else fallback


def oos_disclosure(ic_report):
    """把真样本外整体表现单列出来，供前端/日志对账（**不参与** gate 判定，只披露）。"""
    oos = (ic_report or {}).get("out_of_sample") or {}
    ov = oos.get("overall") or {}
    cfg = (ic_report or {}).get("config") or {}
    out = {"split_date": cfg.get("split_date"), "n_signals": oos.get("n_signals"), "periods": {}}
    for k in ("T1", "T3", "T5", "T10", "T20"):
        d = ov.get(k)
        if isinstance(d, dict):
            out["periods"][k] = {"n": d.get("n"), "win_rate": d.get("win_rate"),
                                 "avg_return": d.get("avg_return")}
    return out


def factor_ic_to_gate(name, ic_report):
    """从 factor_ic_report 抽门槛胜率。

    🔴 2026-11-27 主人令「IC 门禁改用真 OOS」：
       优先级 = out_of_sample（split_date 之后的真样本外）
              > fixed_sample（滚动固定样本）
              > in_sample（样本内，最乐观，仅当前两者皆不可用时兜底）。
       原因：11-26 实测同一份 factor_ic_report 里 in_sample T1 胜率 48.5%、
            而 out_of_sample（n=1222）T1 仅 38.5%、T5 均值 -4.80%、T20 均值 -19.49%。
             只看样本内，等于拿 9 月之前的表现给 11 月的策略背书。
       披露：返回体带 sample_used + 三档胜率/均值，前端与日志可直接对账。
    """
    if not ic_report:
        return None

    # 三种样本形态：
    #   out_of_sample / in_sample -> {overall: {T1: {n, win_rate, avg_return, median}}}
    #   fixed_sample              -> {periods: {T1: {n, win, avg}}}
    oos_overall = (ic_report.get("out_of_sample") or {}).get("overall") or {}
    in_overall = (ic_report.get("in_sample") or {}).get("overall") or {}
    fixed_periods = (ic_report.get("fixed_sample") or {}).get("periods") or {}

    n_in = ic_report.get("n_signals_tested") or ic_report.get("n_signals") or 0
    n_oos = _n_of(oos_overall, 0)

    if oos_overall and n_oos >= THRESH["min_n_signals"]:
        sample_used, body, n, wk, ak = "out_of_sample", oos_overall, n_oos, "win_rate", "avg_return"
    elif fixed_periods:
        sample_used, body, n, wk, ak = "fixed_sample", fixed_periods, n_in, "win", "avg"
    elif in_overall:
        sample_used, body, n, wk, ak = "in_sample", in_overall, n_in, "win_rate", "avg_return"
    else:
        return None

    def w(d):
        return (d or {}).get(wk) if isinstance(d, dict) else None

    def a(d):
        return (d or {}).get(ak) if isinstance(d, dict) else None

    gate = "ok"
    reasons = []

    T1, T3, T5 = w(body.get("T1")), w(body.get("T3")), w(body.get("T5"))
    R1, R3, R5 = a(body.get("T1")), a(body.get("T3")), a(body.get("T5"))
    _tag = {"out_of_sample": "样本外", "fixed_sample": "固定样本", "in_sample": "样本内"}[sample_used]

    if T1 is not None and T1 < THRESH["min_T1_win"]:
        gate = "fail"; reasons.append(f"{_tag}T1胜率{T1}<{THRESH['min_T1_win']}")
    if T3 is not None and T3 < THRESH["min_T3_win"] and gate == "ok":
        gate = "warn"; reasons.append(f"{_tag}T3胜率{T3}<{THRESH['min_T3_win']}")
    if T5 is not None and T5 < THRESH["min_T5_win"]:
        gate = "fail"; reasons.append(f"{_tag}T5胜率{T5}<{THRESH['min_T5_win']}")
    if n < THRESH["min_n_signals"]:
        gate = "insufficient_data"; reasons.append(f"样本量{n}<{THRESH['min_n_signals']}")

    # 固定样本闸：仅当主体不是真 OOS 时才有独立意义。OOS 已是最严口径，
    # 再叠一层固定样本只会在「OOS 好、固定样本差」时误杀，故不叠加。
    fT1 = fT3 = fT5 = None
    if sample_used != "out_of_sample":
        def fp(d):
            return (d or {}).get("win") if isinstance(d, dict) else None
        fT1, fT3, fT5 = fp(fixed_periods.get("T1")), fp(fixed_periods.get("T3")), fp(fixed_periods.get("T5"))
        if fT1 is not None and fT1 < THRESH["min_fixed_T1_win"]:
            gate = "fail"; reasons.append(f"固定样本T1胜率{fT1}<{THRESH['min_fixed_T1_win']}")
        if fT3 is not None and fT3 < THRESH["min_fixed_T3_win"] and gate == "ok":
            gate = "warn"; reasons.append(f"固定样本T3胜率{fT3}<{THRESH['min_fixed_T3_win']}")

    # ic_weight：胜率 55% -> 1.0，50% -> 0.5，clamp [0.5, 1.5]。
    #   真 OOS 模式下只认 OOS 自身，不再与样本内 fixed 取 max
    #   （取 max = 挑最乐观的那个，与「样本外优先」自相矛盾）。
    if sample_used == "out_of_sample":
        _w_base = T1 if T1 is not None else 50.0
    else:
        _w_base = max([T1 if T1 is not None else 50.0, fT1 if fT1 is not None else 50.0])

    return {
        "name": name,
        "sample_used": sample_used,
        "n_signals": n,
        "T1_win": T1, "T3_win": T3, "T5_win": T5,
        "T1_avg": R1, "T3_avg": R3, "T5_avg": R5,
        "fixed_T1_win": fT1, "fixed_T3_win": fT3, "fixed_T5_win": fT5,
        "gate": gate,
        "reasons": reasons,
        "ic_weight": round(min(1.5, max(0.5, 0.5 + (_w_base - 50) / 10.0)), 2),
        "update_time": ic_report.get("update_time")
    }

def track_to_gate(name, track):
    """从 *_track.json 读累计 T+N 胜率（更可信的 OOS 数据）"""
    if not track:
        return None
    return {
        "name": name,
        "T1_win": track.get("T1_win"),
        "T3_win": track.get("T3_win"),
        "T5_win": track.get("T5_win"),
        "n_signals": track.get("n_signals"),
        "update_time": track.get("update_time")
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RAW_DIR, "ic_gate.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ic_report        = load_json(os.path.join(RAW_DIR, "factor_ic_report.json"), {})
    validate_report = load_json(os.path.join(RAW_DIR, "factor_validate_report.json"), {})
    h_buy_track     = load_json(os.path.join(RAW_DIR, "h_auto_buy_track.json"), {})

    # 合并两路 IC 报告到一个总 IC 信号（ge3 / crds 等策略的输入统一）
    merged_ic = {
        "n_signals_tested": ic_report.get("n_signals_tested"),
        "in_sample": ic_report.get("in_sample"),
        # 🔴 2026-11-27：真样本外段落一并带下去，factor_ic_to_gate 优先消费它
        "out_of_sample": ic_report.get("out_of_sample"),
        "fixed_sample": (validate_report or {}).get("fixed_sample") or ic_report.get("fixed_sample"),
        "update_time": ic_report.get("update_time")
    }

    factors = {
        "ge3":          factor_ic_to_gate("ge3", merged_ic),
        "h_auto_buy_累计": track_to_gate("h_auto_buy_累计", h_buy_track)
    }

    # 决策摘要
    any_fail = any((f or {}).get("gate") == "fail" for f in factors.values() if f)
    any_warn = any((f or {}).get("gate") == "warn" for f in factors.values() if f)
    insuff  = any((f or {}).get("gate") == "insufficient_data" for f in factors.values() if f)

    if any_fail:
        action = "fail"
    elif any_warn:
        action = "warn"
    elif insuff:
        action = "insufficient_data"
    else:
        action = "ok"

    # 🔴 2026-11-26 主人令「不让 3 个月前的权重继续调今天的仓」：
    #   IC 报告超过 30 天即整体失效，下游 ic_weight 强制回到中性 1.0（不再用陈旧权重调分）。
    try:
        _rep_ut = datetime.strptime(str(ic_report.get("update_time") or ""), "%Y-%m-%d %H:%M:%S")
        _age_days = (datetime.now() - _rep_ut).days
    except Exception:
        _age_days = None
    stale = (_age_days is None or _age_days > 30)
    if stale:
        for _f in factors.values():
            if not _f:
                continue
            _f["ic_weight"] = 1.0
            _f.setdefault("reasons", []).append("IC报告超30天失效(%s天)" % _age_days)
        if action != "fail":
            action = "stale"

    gate = {
        "policy": "ic_gate_v1_conservative",
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "thresholds": THRESH,
        "sample_priority": "out_of_sample > fixed_sample > in_sample",
        "oos_disclosure": oos_disclosure(ic_report),
        "overall_action": action,
        "ic_report_age_days": _age_days,
        "ic_report_stale": stale,
        "factors": factors,
        "todo": [
            "下游接入 generate_top10.py：score_backtest 改读 ic_gate.json 的 ic_weight 做微调",
            "下游接入 gen_triple_consensus / calc_crds：select 前读 overall_action 做准出门禁",
            "src 仅产出 JSON，**不改选股逻辑**——MVP"
        ]
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(json.dumps(gate, ensure_ascii=False, indent=2))
    if not args.quiet:
        print(f"[ok] ic_gate.json → {args.out}")
        print(f"[action] overall={action}")
        for name, f in factors.items():
            if not f:
                print(f"  - {name}: missing data")
                continue
            T1 = f.get("T1_win")
            g = f.get("gate", "—")
            sm = f.get("sample_used", "—")
            reasons = "; ".join(f.get("reasons") or []) or "—"
            print(f"  - {name}: T1={T1}(样本={sm}), gate={g}, reasons=[{reasons}]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
