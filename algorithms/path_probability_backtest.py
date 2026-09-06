#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 预测·路径概率 walk-forward 回测（2026-09-06 主人令：暂未上架两卡实证 ①）
================================================================================
逐个交易日 t，只用 ≤t 的 K 线复跑【生产引擎】（market_path_probability 的
pattern_match + calc_path_prob，importlib 加载保证口径 100% 一致），
得到当日 A/B/C 概率预测 → 与实际 T+5 路径（>1% = A，<-1% = B，其余 = C）对照。

产出：raw_data/path_probability_backtest.json（update_v8 映射 → data/PATH_PROB_BACKTEST.js）
调度：算法链 E 批（21:00 CST，与 backtest 全家同批）

判据（内置，与 logic.html AI 预测段同步）：
  VALID   = 有效预测日 ≥100 且 主路径命中率−基率(最大类) ≥ +3pp 且 Brier < 基线 Brier
  WATCH   = Brier < 基线 Brier 但命中增益 < 3pp
  INVALID = 其余（含有效样本不足 60）

诚实原则：结论只看真实 edge，不造假；样本不足时 verdict=INVALID 并注明。
"""
import json
import os
import sys
import datetime
import importlib.util

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_MAIN = os.path.join(BASE, "out", "index_history.json")
OUT_JSON = os.path.join(BASE, "raw_data", "path_probability_backtest.json")
ENGINE = os.path.join(BASE, "algorithms", "market_path_probability.py")

WARMUP = 260      # 起始缓冲：至少 260 根历史才开始评估（匹配窗口 60 + 匹配池）
HORIZON = 5       # 生产路径 A/B/C 定义在 5 日前向上
TX_SYMBOL = "sh000001"


def _log(msg):
    print(f"  [path_prob_backtest] {msg}", flush=True)


def _load_engine():
    spec = importlib.util.spec_from_file_location("mpp_engine", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 只执行模块级常量/函数定义，__main__ 门禁不触发
    return mod


def _tx_fetch(count=800):
    """兜底：腾讯接口抓上证日 K（本机/云端/美区实测均通，0.3s 量级）。
    返回 [{d,o,h,l,c,v}]，顺序 date,open,close,high,low,volume（腾讯标准）。"""
    import urllib.request
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={TX_SYMBOL},day,,,{count},qfq")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    node = (d.get("data") or {}).get(TX_SYMBOL) or {}
    rows = node.get("qfqday") or node.get("day") or []
    kl = []
    for r in rows:
        try:
            kl.append({"d": r[0], "o": float(r[1]), "c": float(r[2]),
                       "h": float(r[3]), "l": float(r[4]), "v": float(r[5])})
        except (ValueError, IndexError):
            continue
    return kl


def _load_klines():
    kl = []
    if os.path.exists(IN_MAIN):
        try:
            with open(IN_MAIN, encoding="utf-8") as f:
                kl = json.load(f).get("klines") or []
            _log(f"输入 {IN_MAIN}: {len(kl)} 根 ({kl[0]['d']} ~ {kl[-1]['d']})")
        except Exception as e:
            _log(f"读取失败({e})，转腾讯兜底")
            kl = []
    if len(kl) < WARMUP + HORIZON + 80:
        _log("本地 K 线不足/缺失 → 腾讯接口兜底抓取")
        kl_tx = _tx_fetch()
        if len(kl_tx) > len(kl):
            kl = kl_tx
            _log(f"腾讯兜底 {len(kl)} 根 ({kl[0]['d']} ~ {kl[-1]['d']})")
    return kl


def _classify(f5):
    if f5 is None:
        return None
    if f5 > 1:
        return "A"
    if f5 < -1:
        return "B"
    return "C"


def main():
    if not os.path.exists(ENGINE):
        _log(f"生产引擎不存在: {ENGINE}")
        return 1
    eng = _load_engine()
    klines = _load_klines()
    n = len(klines)
    if n < WARMUP + HORIZON + 20:
        _log(f"K 线仅 {n} 根，不足以回测（需 ≥{WARMUP + HORIZON + 20}）")
        # 写最小占位 json 防 update_v8 映射报缺（带 INVALID verdict，不造假）
        out = {"update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "data_range": f"{klines[0]['d']}~{klines[-1]['d']}" if klines else "",
               "n_days_eval": 0, "n_valid": 0, "verdict": "INVALID",
               "verdict_note": f"样本不足（K线 {n} 根 < 最低要求）"}
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return 0

    closes = [k["c"] for k in klines]
    eval_days = range(WARMUP, n - HORIZON)  # t 需满足 t+HORIZON ≤ n-1
    n_eval = len(eval_days)

    recs = []          # 每有效预测日一条
    n_sample0 = 0      # 无匹配（prob.sample==0）跳过数
    done = 0
    for t in eval_days:
        sub = closes[: t + 1]
        matches = eng.pattern_match(sub)
        prob = eng.calc_path_prob(matches)
        done += 1
        if done % 100 == 0:
            _log(f"进度 {done}/{n_eval}")
        if not prob.get("sample"):
            n_sample0 += 1
            continue
        f5 = (closes[t + HORIZON] - closes[t]) / closes[t] * 100
        recs.append({
            "d": klines[t]["d"],
            "pA": prob["A_up"], "pB": prob["B_down"], "pC": prob["C_flat"],
            "sample": prob["sample"],
            "f5": round(f5, 3),
            "actual": _classify(f5),
        })

    if len(recs) < 60:
        verdict, note = "INVALID", f"有效预测样本不足（{len(recs)} < 60），不下结论"
    else:
        n = len(recs)
        # 基率（实际三类频率）
        base = {c: sum(1 for r in recs if r["actual"] == c) / n for c in "ABC"}
        # 主路径命中率（argmax 概率 vs 实际）
        hit = sum(1 for r in recs
                  if max("ABC", key=lambda c: r["p" + c]) == r["actual"])
        hit_rate = hit / n
        max_base = max(base.values())
        random_base = sum(base[c] ** 2 for c in "ABC")  # 按基率随机猜主类的期望命中率
        # Brier（三分类，sum (p-y)^2，范围 [0,2]）
        def _brier(rows):
            s = 0.0
            for r in rows:
                p = {"A": r["pA"] / 100, "B": r["pB"] / 100, "C": r["pC"] / 100}
                for c in "ABC":
                    s += (p[c] - (1.0 if r["actual"] == c else 0.0)) ** 2
            return s / len(rows)
        brier = _brier(recs)
        brier_base = _brier([{"pA": base["A"] * 100, "pB": base["B"] * 100,
                              "pC": base["C"] * 100, "actual": r["actual"]} for r in recs])
        avg_f5 = sum(r["f5"] for r in recs) / n

        # 条件 edge：pA≥40 / pB≥40 子集的对应类实际占比
        def _cond(key, cls):
            subr = [r for r in recs if r[key] >= 40]
            if not subr:
                return {"n": 0, "rate": None, "base": round(base[cls] * 100, 1),
                        "lift_pp": None}
            rate = sum(1 for r in subr if r["actual"] == cls) / len(subr)
            return {"n": len(subr), "rate": round(rate * 100, 1),
                    "base": round(base[cls] * 100, 1),
                    "lift_pp": round((rate - base[cls]) * 100, 1)}

        condA = _cond("pA", "A")
        condB = _cond("pB", "B")

        hit_gain_pp = round((hit_rate - max_base) * 100, 2)
        brier_gain = round(brier_base - brier, 4)  # >0 = 优于基线
        if n >= 100 and hit_gain_pp >= 3.0 and brier < brier_base:
            verdict = "VALID"
            note = (f"有效：{n} 日样本，主路径命中 {hit_rate:.1%} 比基率高 {hit_gain_pp}pp，"
                    f"Brier 优 {brier_gain}——概率有真实区分力")
        elif brier < brier_base:
            verdict = "WATCH"
            note = (f"观望：Brier 优于基线（+{brier_gain}）但主路径命中增益仅 {hit_gain_pp}pp"
                    f"（<3pp），方向对、点位不准")
        else:
            verdict = "INVALID"
            note = (f"无效：Brier 未优于基线（{brier:.3f} vs {brier_base:.3f}），"
                    f"当前形态匹配概率≈噪声")

        out = {
            "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_range": f"{klines[0]['d']} ~ {klines[-1]['d']}",
            "engine": {"source": "algorithms/market_path_probability.py（生产口径复用）",
                       "match": "方向一致率≥0.65 取Top20 加权",
                       "horizon_days": HORIZON,
                       "path_def": "A=T+5>+1% B=T+5<-1% C=其余"},
            "eval": {"n_days": n_eval, "n_valid": n, "n_no_match": n_sample0},
            "overall": {
                "hit_rate": round(hit_rate * 100, 1),
                "hit_gain_pp_vs_max_base": hit_gain_pp,
                "random_base_hit": round(random_base * 100, 1),
                "base_rates": {c: round(base[c] * 100, 1) for c in "ABC"},
                "brier": round(brier, 4),
                "brier_base": round(brier_base, 4),
                "brier_gain": brier_gain,
                "avg_f5_pct": round(avg_f5, 3),
            },
            "conditional": {"pA_ge40": condA, "pB_ge40": condB},
            "verdict": verdict,
            "verdict_note": note,
        }
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        _log(f"[ok] 写入 {OUT_JSON}  verdict={verdict}")
        _log(note)
        return 0

    # 样本不足分支
    out = {"update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "data_range": f"{klines[0]['d']} ~ {klines[-1]['d']}",
           "eval": {"n_days": n_eval, "n_valid": len(recs), "n_no_match": n_sample0},
           "verdict": verdict, "verdict_note": note}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _log(f"[ok] 写入 {OUT_JSON}  verdict={verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
