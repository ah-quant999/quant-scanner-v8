#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_forward_alpha.py — 个股级「未来收益预测分」因子（2026-11-18 主人令新建）

目标（主人原话）：把「测算推荐未来收益率最高的个股」做实。
  现有 expected_return_term 只按 4 个信号组合给分（今日 19/20 只同组合→同分），
  同组合内实际靠个股历史均益/胜率排序 —— 不是个股级未来收益测算。
  本模块补上真正【个股级、指向未来、经 OOS 验证】的横截面预测因子。

方法（严守科学铁律，不 data snooping、不放宽判据）：
  1. 特征：纯 OHLCV 个股级特征（rev5/rev20 反转、vol60 低波、h52 突破、
     amt60 小盘、vol_conf 量价共振、dviol60 下行波动）—— 全部来自 make_prep。
  2. 合成：alpha = Σ w_k · z_k，其中 w_k = 该特征【IS 段】逐调仓点截面 Spearman IC
     的均值（含符号）。OOS 段【绝不重拟合】，只套用 IS 学到的固定权重。
  3. 标准化：每个调仓点对各特征值做横截面 rank→[-1,1]（去量纲、抗极值）。
  4. 验证：完全复用 factor_walkforward.py 的 run_factor/summarize —— 逐调仓点
     五分层 L1-L5、次日开盘进场、往返成本 0.2%、全池等权基准、IS/OOS 60/40 切分、
     IR_OOS>0.3 且连续 WIN_YEARS(5) 年内 WIN_PASS_N(4) 年 Top 层跑赢基准>55%。
     判据一字不改（主人 2026-09-09 硬门槛，注释明载「不可放宽」）。
  5. 产物 raw_data/stock_forward_alpha.json：
     · overall / per_hold：与 factor_walkforward 同构的 OOS 证据 + verdict
     · latest_scores：最新交易日截面每只票的 Alpha 预测分（0~1 截面分位），
       供 generate_top10.py 的 alpha_term 排序使用。
       🛡 2026-11-19 主人令「发现就马上解决」：原实现误取最后一个回测调仓点（截面滞后
       约 hold+2 个交易日）；权重是 IS 固定值，套最新截面合法、不构成前视。
     · 闸门：generate_top10 仅当 verdict=PASS 才启用 alpha_term；FAIL 则权重 0（零影响）。

运行（cn runner，明晚真实数据）：
  python algorithms/stock_forward_alpha.py --no-fetch
  本机境外 IP 无 kline 缓存/拉不到日 K，禁止在本地伪造跑数。
"""
import os
import sys
import json
import argparse
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
ROOT = os.environ.get("V8_ROOT") or os.path.dirname(BASE)
RAW = os.path.join(ROOT, "raw_data")
OUT_JSON = os.path.join(RAW, "stock_forward_alpha.json")

# 复用现有引擎的全部统计口径/交易约束/判据 —— 零口径漂移
try:
    import factor_walkforward as fw
except Exception as _e:
    print("FATAL: 无法 import factor_walkforward:", _e)
    raise

# 参与合成的个股级特征（纯 OHLCV、make_prep 可算；避开动量家族 W2 禁入）
FEATURES = ["rev5", "rev20", "vol60", "h52", "amt60", "vol_conf", "dviol60"]
HOLD_PRIMARY = 10          # 主判据持有期（与引擎主口径一致）
MIN_IC_POINTS = 8          # IS 段 IC 样本下限（< 此不采信该特征权重）


def _log(m=""):
    print(m, flush=True)


def _rank01(vals):
    """截面 rank → [-1,1]（并列取平均秩）；vals: list[(code, value)] → {code: z}。"""
    n = len(vals)
    if n < 2:
        return {}
    order = sorted(range(n), key=lambda i: vals[i][1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[j + 1][1] == vals[i][1]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    out = {}
    for idx, (code, _v) in enumerate(vals):
        out[code] = (2.0 * ranks[idx] / (n - 1)) - 1.0
    return out


def build_synthetic_prep(dates, pos, bars, base_prep, hold):
    """
    每个票构造一个 lambda i -> alpha(i)：
      alpha(i) = Σ_k w_k · z_k(i)
      w_k = IS 段逐调仓点截面 IC 均值（固定，OOS 不重拟合）
      z_k(i) = 该特征在【该调仓点截面】的 rank[-1,1]（按交易日对齐后查表）
    返回 (prep_syn, weights, cover, latest_scores)
    """
    t_points = []
    t = fw.MIN_BARS
    while t + 1 + hold < len(dates):
        t_points.append(t)
        t += fw.STEP
    if len(t_points) < 20:
        return {}, {}, 0, {}

    # 1) 每个调仓点、每个特征：截面 (code, value) 与 IC
    cross = {k: {} for k in FEATURES}       # k -> {t: {code: z}}
    ic_series = {k: [] for k in FEATURES}   # k -> [ic per t]（按 t_points 顺序）
    for t in t_points:
        # 前瞻收益（同 _trade_ret 口径，仅 IS 用）
        rets_map = {}
        for c in pos:
            j = pos[c][t]
            if j < 0:
                continue
            rr = fw._trade_ret(bars[c], j, hold, c)
            if rr is not None:
                rets_map[c] = rr
        if len(rets_map) < 15:
            for k in FEATURES:
                ic_series[k].append(None)
            continue
        for k in FEATURES:
            vals = []
            for c in base_prep:
                if c not in rets_map:
                    continue
                i = pos[c][t]
                if i < fw.MIN_BARS:
                    continue
                fn = base_prep[c]["f"].get(k)
                if fn is None:
                    continue
                v = fn(i)
                if v is None:
                    continue
                vals.append((c, v))
            if len(vals) >= 15:
                z = _rank01(vals)
                cross[k][t] = z
                ic_series[k].append(fw._spearman([(v, rets_map[c]) for c, v in vals
                                                  if c in z and c in rets_map]))
            else:
                ic_series[k].append(None)

    # 2) IS 段（前 60%）定权重；OOS 段绝不参与
    cut = int(len(t_points) * 0.6)
    weights = {}
    for k in FEATURES:
        seq = [x for x in ic_series[k][:cut] if x is not None]
        weights[k] = (sum(seq) / len(seq)) if len(seq) >= MIN_IC_POINTS else 0.0
    # 全 0 权重（IS 无任何 IC 证据）→ 合成失效，交由 verdict=FAIL 处理，不硬造方向
    active = {k: w for k, w in weights.items() if abs(w) > 1e-9}
    _log("  IS 学到的特征权重（OOS 不重拟合）: " +
         json.dumps({k: round(w, 4) for k, w in weights.items()}, ensure_ascii=False))

    # 3) 合成每个票、每个调仓点的 alpha 值 → prep 查表
    #    key: (code, global_t) → alpha；run_factor 调 lambda i 时用 pos 反查 global_t
    g2t = {g: idx for idx, g in enumerate(t_points)}  # 用调仓点序号定位 cross 表
    alpha_at = {}   # code -> {local_i: alpha}
    for c in base_prep:
        table = {}
        for gt in t_points:
            i = pos[c][gt]
            if i < 0:
                continue
            parts = []
            for k, w in active.items():
                z = cross[k].get(gt, {}).get(c)
                if z is not None:
                    parts.append(w * z)
            if parts:
                table[i] = sum(parts) / sum(abs(w) for w in active.values())
        alpha_at[c] = table

    prep_syn = {}
    for c in base_prep:
        tbl = alpha_at[c]
        prep_syn[c] = {"f": {"forward_alpha": (lambda i, t=tbl: t.get(i))}}

    # 4) 最新交易日截面个股预测分 → 0~1 截面分位（供排序）
    #    🛡 2026-11-19 主人令「发现就马上解决」：原取最后一个回测调仓点 t_points[-1]
    #    （受 t+1+hold<len(dates) 约束，截面滞后约 hold+2 个交易日，rev5/rev20 十二天前
    #    的排序≠今日排序）。w_k 是 IS 段固定权重，套最新截面只用当日信息，合法无前视。
    latest_scores = {}
    t_last = len(dates) - 1                      # 全局轴最新交易日
    feat_vals = {}                               # k -> [(code, raw_value)]
    for c in base_prep:
        i = pos[c][t_last]
        if i < fw.MIN_BARS:                      # 最新日停牌/历史不足，与回测口径一致
            continue
        for k in active:
            fn = base_prep[c]["f"].get(k)
            if fn is None:
                continue
            v = fn(i)
            if v is None:
                continue
            feat_vals.setdefault(k, []).append((c, v))
    zs = {k: _rank01(vals) for k, vals in feat_vals.items() if len(vals) >= 15}
    zs = {k: z for k, z in zs.items() if z}
    if zs:
        codes_last = set()
        for z in zs.values():
            codes_last.update(z)
        alpha_raw = {}
        for c in codes_last:
            parts = [w * zs[k][c] for k, w in active.items() if k in zs and c in zs[k]]
            if parts:
                alpha_raw[c] = sum(parts) / sum(abs(w) for w in active.values())
        if alpha_raw:
            z = _rank01(list(alpha_raw.items()))
            latest_scores = {c: round((v + 1.0) / 2.0, 4) for c, v in z.items()}

    cover = sum(1 for c, tbl in alpha_at.items() if tbl)
    return prep_syn, {k: round(v, 6) for k, v in weights.items()}, cover, latest_scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--no-fetch", action="store_true", help="只用本地缓存，不联网")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 只（调试）")
    ap.add_argument("--out", default=OUT_JSON)
    args = ap.parse_args()

    _log("=" * 74)
    _log("  个股级前瞻预测因子 Alpha（IS 拟合权重 / OOS 严格不重拟合）  %s"
         % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _log("=" * 74)

    codes = fw.load_universe("kline_cache")
    if args.limit:
        codes = codes[:args.limit]
    _log("  universe: %d 只" % len(codes))
    klines = fw.get_klines(codes, args.workers, not args.no_fetch)
    if len(klines) < 200:
        _log("  ⚠️ 有效 K 线 <200，放弃（不在本机伪造）")
        return
    dates, pos, bars = fw.build_panel(klines)

    # 基础特征 prep（复用引擎）
    base_prep = {}
    for c, rows in klines.items():
        base_prep[c] = fw.make_prep(rows)

    per_hold = {}
    latest_scores = {}
    weights_used = {}
    for hold in fw.HOLDS:
        _log("\n  ▶ 合成 Alpha  hold=%dd" % hold)
        prep_syn, weights, cover, latest = build_synthetic_prep(dates, pos, bars, base_prep, hold)
        if not prep_syn:
            _log("    调仓点不足 / 合成失败，跳过")
            continue
        recs = fw.run_factor("forward_alpha", dates, pos, bars, prep_syn, hold)
        s = fw.summarize(recs)
        if not s:
            _log("    summarize 为空，跳过")
            continue
        per_hold[hold] = s
        weights_used[hold] = weights
        if hold == HOLD_PRIMARY:
            latest_scores = latest
        _log("    覆盖 %d 只  点=%d  利差=%+.3f%%(OOS %+.3f%%)  IR_OOS=%s  年率 %d/%d ⇒ %s"
             % (cover, s["n_points"], s["spread_avg_pct"], s["spread_oos_pct"] or 0,
                s["ir_oos"], s["years_beat_gt55"], s["years_total"], s["verdict"]))

    if not per_hold:
        _log("  ⚠️ 无有效持有期结果，不写产物")
        return

    # 主判据 hold=10 的 verdict 决定闸门；缺失则按 HOLDS 固定次序取第一个 PASS。
    # 🛡 2026-11-19 主人令「修」：原回退在 PASS 档里挑 IR_OOS 最高者 = 多持有期多重检验，
    #   改为确定性次序（fw.HOLDS=[5,10,20]），不挑最优；全 FAIL 时维持取最后一个档。
    primary = per_hold.get(HOLD_PRIMARY)
    if primary is None:
        ok = [(h, s) for h in fw.HOLDS
              if h in per_hold and per_hold[h].get("verdict") == "PASS"]
        primary = ok[0][1] if ok else list(per_hold.values())[-1]

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": "algorithms/stock_forward_alpha.py",
        "purpose": "个股级未来收益预测分（同信号组合内分高下），generate_top10 alpha_term 消费",
        "methodology": (
            "Alpha = Σ w_k·rank_z(feature_k)；w_k = IS 段(前60%调仓点)逐点截面 Spearman IC 均值(含符号)，"
            "OOS 段绝不重拟合；latest_scores 取最新交易日截面(2026-11-19 主人令修正，原误用最后回测调仓点滞后约hold+2日)。"
            "特征=rev5/rev20/vol60/h52/amt60/vol_conf/dviol60（纯OHLCV，避开W2禁入动量家族）。"
            "验证完全复用 factor_walkforward 引擎：次日开盘进场、往返成本0.20%、五分层、"
            "全池等权基准、IS/OOS 60/40；判据 IR_OOS>0.3 且连续5年内≥4年Top层跑赢基准>55%（硬门槛不放宽）；"
            "verdict 回退按 HOLDS 固定次序取首个 PASS（不挑最优）。"),
        "features": FEATURES,
        "hold_primary": HOLD_PRIMARY,
        "gate_hold": HOLD_PRIMARY,
        "verdict": primary.get("verdict"),
        "ir_oos": primary.get("ir_oos"),
        "years_beat_gt55": primary.get("years_beat_gt55"),
        "years_total": primary.get("years_total"),
        "spread_oos_pct": primary.get("spread_oos_pct"),
        "weights_is": weights_used.get(HOLD_PRIMARY, {}),
        "criteria": fw.FACTOR_WF_CRITERIA if hasattr(fw, "FACTOR_WF_CRITERIA")
                    else ("IR_OOS > 0.3 且 连续 5 年窗口内 ≥4 年 Top 层跑赢同期全池等权基准的调仓点占比 > 55%"),
        "per_hold": {str(h): {k: s.get(k) for k in
                       ("verdict", "ir_oos", "ir_is", "spread_oos_pct", "years_beat_gt55",
                        "years_total", "n_points", "beat_base_rate")} for h, s in per_hold.items()},
        "latest_scores": latest_scores,   # code -> 0~1 预测分位（最后调仓点截面）
        "survivor_bias_disclosure": "universe=raw_data/kline_cache 当前在册 A 股（幸存池），回测含幸存者偏差；仅用于池内相对排序。",
    }
    os.makedirs(RAW, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    _log("\n  ✅ 写入 %s  verdict=%s  IR_OOS=%s  个股分覆盖 %d"
         % (args.out, out["verdict"], out["ir_oos"], len(latest_scores)))


if __name__ == "__main__":
    main()
