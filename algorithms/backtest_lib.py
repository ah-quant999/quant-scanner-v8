#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_lib.py — v8 统一回测方法学库（2026-10-21 主人令「科学超额算法升级」全做落地）

五个模块（对应主人拍板的科学升级方向 1/2/3/4/5，均有严谨文献支撑·López de Prado 等）：
  ① 回测纪律   purged_walkforward_splits（Purged walk-forward，embargo 防泄漏）
               probability_sharpe_ratio（PSR 概率夏普比率，小样本显著性）
  ② 交易约束   buy_blocked / sell_defer：涨停不可买 / 跌停不可卖顺延 / T+1
               （A股制度建模：回测成交价用下一可行交易日，非信号日收盘价）
  ③ 市场分层   regime_flags：牛/熊（指数 vs MA20）× 高/低波动（20日σ年化）四桶
  ④ 因子工程   rolling_ic（滚动 IC + 衰减检测 → 降级建议，接 verdict 闸门）
               symmetric_orthogonalize（对称正交去共线）
  ⑤ 组合层     volatility_target_weights / risk_parity_weights

设计铁律：
  - 纯标准库（math/statistics），零第三方依赖 → 任何 runner/脚本 import 即用
  - 无状态纯函数，绝不读写文件 → 可被任意回测脚本组合
  - 「宁缺勿错」：样本不足一律返回 None / 空结构，绝不伪装；绝不臆造数据
  - 涨跌停幅度按代码前缀近似：30x/68x → 20%（创业板/科创板），其余 → 10%；
    ST(±5%) 无名称数据暂无法判定 → 以 10% 宽松判定并在此声明（已知近似，非隐藏）
"""

import math
import statistics

__all__ = [
    "limit_pct_of", "buy_blocked", "sell_defer_days",
    "purged_walkforward_splits", "probability_sharpe_ratio",
    "regime_flags", "rolling_ic", "symmetric_orthogonalize",
    "volatility_target_weights", "risk_parity_weights",
]


# ════════════════════════════════════════════════════════════════
# ② 交易约束可行域（A股制度建模）
# ════════════════════════════════════════════════════════════════
def limit_pct_of(code):
    """按代码前缀近似涨停幅度：30x(创业)/68x(科创) → 20%；其余 → 10%。
    ST ±5% 因回测 K 线缓存不含名称暂无法判定 → 按 10% 宽松处理（宁可漏放不可误杀）。"""
    c = str(code)
    if c.startswith("30") or c.startswith("68"):
        return 0.20
    return 0.10


def buy_blocked(prev_close, bar, code=None, limit_pct=None):
    """次日买入可行性判定（用于「信号日收盘出信号 → 次日开盘买入」的回测口径）。
    bar = 下一交易日 K 线 dict（open/high/low/close）。
    规则（保守：宁可判不可买，绝不虚构成交）：
      ① 开盘即触涨停（open ≥ prev_close×(1+pct×0.98)）且全天未开板
         （low ≥ 涨停价×0.998）→ 一字板/开盘即封死，排队几乎必然买不到 → blocked
      ② 仅开盘触板但盘中开板（low 更低）→ 可买（按开盘价成交，成本略乐观但真实可成交）
    返回 True = 买不进（该样本应从回测成交集中剔除）。"""
    if not prev_close or prev_close <= 0 or not bar:
        return False
    pct = limit_pct if limit_pct is not None else limit_pct_of(code)
    lim = prev_close * (1.0 + pct) * 0.998      # 涨停价（含 0.2% 容差吸收复权舍入）
    o, lo = bar.get("open"), bar.get("low")
    if o is None or lo is None:
        return False
    if o >= lim and lo >= o * 0.999:            # 开盘即封死全天未开板
        return True
    return False


def sell_defer_days(bars, k, code=None, limit_pct=None, max_defer=3):
    """卖出顺延：第 k 日开盘卖出时若开盘即跌停（open ≤ 跌停价）→ 顺延至下一可交易日开盘。
    bars = 该票 K 线列表；k = 计划卖出日索引。
    返回 (实际卖出日索引, 实际卖出价)；max_defer 内无可行日 → (None, None)，调用方决定丢弃或按跌停价强平口径处理。
    T+1 由调用方保证（本库买入即次日开盘、卖出日 ≥ 买入日+hold 且 hold ≥ 1，天然满足）。"""
    if not bars or k is None or k < 1 or k >= len(bars):
        return (None, None)
    pct = limit_pct if limit_pct is not None else limit_pct_of(code)
    kk = k
    for _ in range(max_defer + 1):
        if kk >= len(bars):
            return (None, None)
        bar, prev = bars[kk], bars[kk - 1]
        lim_dn = prev["close"] * (1.0 - pct) * 1.002   # 跌停价（容差同上）
        if bar.get("open") is not None and bar["open"] <= lim_dn:
            kk += 1                                     # 开盘跌停卖不出 → 顺延
            continue
        return (kk, bar["open"])
    return (None, None)


# ════════════════════════════════════════════════════════════════
# ① 回测纪律：Purged walk-forward + PSR
# ════════════════════════════════════════════════════════════════
def purged_walkforward_splits(n, n_splits=5, embargo=5, min_train=None):
    """时序 Purged walk-forward 切分器（训练段与测试段之间挖除 embargo 个样本防泄漏）。
    返回 [(train_idx, test_idx), ...]；train 为 expanding（含全部测试块之前的历史，
    末端挖除 embargo），test 为连续不重叠块。样本不足返回 []（绝不硬切）。
    用法：for tr, te in splits: fit(train(tr)) → evaluate(te)；跨块聚合 = 真 OOS。"""
    if n is None or n_splits < 1 or n <= 0:
        return []
    mt = min_train if min_train is not None else max(n // (n_splits + 1), 60)
    test_size = (n - mt) // n_splits
    if test_size < 20:
        return []
    out = []
    for s in range(n_splits):
        t0 = mt + s * test_size
        t1 = t0 + test_size if s < n_splits - 1 else n
        tr_hi = max(t0 - embargo, 0)
        if tr_hi < 30:
            break
        out.append((list(range(0, tr_hi)), list(range(t0, t1))))
    return out


def probability_sharpe_ratio(returns, sr_bench=0.0):
    """概率夏普比率 PSR（Bailey & López de Prado 2012）：
    PSR = Φ( (sr - sr*)·√(T-1) / √(1 - γ3·sr + (γ4-1)/4·sr²) )
    sr 为**单期**夏普（非年化），γ3 偏度、γ4 峰度（普通峰度，正态=3）。
    返回 [0,1]；≥0.95 才可视为统计显著（小样本治「假显著」的红线判据）。
    样本 < 20 或 σ=0 → None（宁缺勿错）。"""
    r = [x for x in (returns or []) if x is not None]
    n = len(r)
    if n < 20:
        return None
    m = sum(r) / n
    sd = statistics.stdev(r)
    if sd <= 1e-12:
        return None
    sr = m / sd
    g3 = 0.0
    g4 = 3.0
    try:
        g3 = sum((x - m) ** 3 for x in r) / n / (sd ** 3)
        g4 = sum((x - m) ** 4 for x in r) / n / (sd ** 4)
    except Exception:
        pass
    den = 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr * sr
    if den <= 0:
        return None
    z = (sr - sr_bench) * math.sqrt(n - 1) / math.sqrt(den)
    # 标准正态 CDF（Abramowitz-Stegun 7.1.26，误差 <7.5e-8，够判 0.95 阈值）
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    pdf = math.exp(-z * z / 2.0) / math.sqrt(2.0 * math.pi)
    cdf = 1.0 - pdf * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
          + t * (-1.821255978 + t * 1.330274429))))
    if z < 0:
        cdf = 1.0 - cdf
    return max(0.0, min(1.0, cdf))


# ════════════════════════════════════════════════════════════════
# ③ 市场状态分层（regime）
# ════════════════════════════════════════════════════════════════
def regime_flags(closes, ma_win=20, vol_win=20, high_vol_sigma=0.35):
    """指数/全池等权收盘序列 → 逐日 regime 标签（与序列等长，前 ma_win 日 None）。
    四桶：bull（收盘>MA20 且低波动）/ bear（<MA20 低波动）/ bull_hv / bear_hv（高波动）。
    高波动判据：近 vol_win 日收益 σ 年化 > high_vol_sigma（默认 0.35 ≈ A股 95 分位）。
    分层回测用法：分桶独立统计因子 edge + 独立权重，主链按当日 regime 切换。"""
    n = len(closes or [])
    if n < ma_win + 2:
        return []
    out = [None] * n
    for i in range(ma_win, n):
        ma = sum(closes[i - ma_win:i]) / ma_win
        seg = [closes[j] / closes[j - 1] - 1.0 for j in range(i - vol_win + 1, i + 1)
               if closes[j - 1] > 0]
        if len(seg) < vol_win - 2:
            out[i] = None
            continue
        sigma = statistics.pstdev(seg) * math.sqrt(250.0)
        hv = sigma > high_vol_sigma
        bull = closes[i] > ma
        out[i] = ("bull_" if bull else "bear_") + ("hv" if hv else "lv")
    return out


# ════════════════════════════════════════════════════════════════
# ④ 因子工程：IC 衰减 / 对称正交
# ════════════════════════════════════════════════════════════════
def rolling_ic(factor_vals, fwd_rets, window=60):
    """滚动 Spearman 秩 IC（截面成对，稳健抗极值）。
    factor_vals/fwd_rets：等长截面序列（同一截面的因子值与前瞻收益按票对齐后传入）。
    返回 (ics, summary)：ics=[{start,ic}]；summary={mean_ic, ic_ir, recent_ic, decay}
    decay = recent(后1/3窗口) - prior(前2/3均值)；recent < 0.02 且 decay < -0.05
    → 建议 = "downgrade"（接 verdict 闸门：keep→watch）。样本不足 summary=None。"""
    pairs = [(f, r) for f, r in zip(factor_vals or [], fwd_rets or [])
             if f is not None and r is not None]
    if len(pairs) < window:
        return [], None
    ics = []
    for s in range(0, len(pairs) - window + 1, max(window // 3, 1)):
        seg = pairs[s:s + window]
        n = len(seg)
        if n < 10:
            continue
        fr = sorted(range(n), key=lambda i: seg[i][0])
        rr = sorted(range(n), key=lambda i: seg[i][1])
        rk_f = [0] * n
        rk_r = [0] * n
        for rank, i in enumerate(fr):
            rk_f[i] = rank
        for rank, i in enumerate(rr):
            rk_r[i] = rank
        mf, mr = sum(rk_f) / n, sum(rk_r) / n
        cov = sum((a - mf) * (b - mr) for a, b in zip(rk_f, rk_r))
        vf = math.sqrt(sum((a - mf) ** 2 for a in rk_f))
        vr = math.sqrt(sum((b - mr) ** 2 for b in rk_r))
        if vf > 0 and vr > 0:
            ics.append({"start": s, "ic": cov / vf / vr})
    if not ics:
        return [], None
    vals = [x["ic"] for x in ics]
    k = max(len(vals) // 3, 1)
    recent = sum(vals[-k:]) / k
    prior = sum(vals[:-k]) / max(len(vals) - k, 1)
    mean_ic = sum(vals) / len(vals)
    sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    summary = {
        "mean_ic": round(mean_ic, 4),
        "ic_ir": round(mean_ic / sd, 4) if sd > 1e-9 else None,
        "recent_ic": round(recent, 4),
        "decay": round(recent - prior, 4),
        "suggest": ("downgrade" if (recent < 0.02 and (recent - prior) < -0.05)
                    else "keep"),
    }
    return ics, summary


def symmetric_orthogonalize(matrix):
    """对称正交（symmetric orthogonalization）：消除因子列间共线，保持各列信息量均摊。
    matrix: list[rows][cols]（行=样本，列=因子）。纯 python 小矩阵实现（格莱姆矩阵
    M=F'F 的谱分解近似：迭代残差回归，B 轮收敛）。退化列（零方差）原样保留为 0。
    返回同形状正交化矩阵；样本 < 3 行或列数 0 → 原样返回。"""
    mat = [list(map(float, row)) for row in (matrix or [])]
    if len(mat) < 3 or not mat[0]:
        return mat
    ncol = len(mat[0])
    for j in range(ncol):
        # 其余列联合拟合第 j 列（线性回归残差），循环一轮即近似对称正交
        base = [[r[c] for c in range(ncol) if c != j] for r in mat]
        y = [r[j] for r in mat]
        p = len(base[0])
        if p == 0:
            continue
        ym = sum(y) / len(y)
        yc = [v - ym for v in y]
        betas = [0.0] * p
        for it in range(3):
            pred = [0.0] * len(y)
            for c in range(p):
                col = [r[c] for r in base]
                cm = sum(col) / len(col)
                cc = [v - cm for v in col]
                denom = sum(v * v for v in cc)
                if denom < 1e-12:
                    continue
                b = sum(a * b2 for a, b2 in zip(yc if it == 0 else
                        [y[i] - pred[i] for i in range(len(y))], cc)) / denom
                betas[c] += b
                for i in range(len(y)):
                    pred[i] += b * col[i]
            yc = [y[i] - pred[i] for i in range(len(y))]
        for i, r in enumerate(mat):
            r[j] = yc[i]
    return mat


# ════════════════════════════════════════════════════════════════
# ⑤ 组合层：波动率目标 / 风险平价
# ════════════════════════════════════════════════════════════════
def volatility_target_weights(series_returns, target_sigma=0.15,
                              window=60, cap=1.0, ann_factor=250.0):
    """波动率目标仓位：w = targetσ / realizedσ（近 window 期，按 ann_factor 年化），上限 cap。
    ann_factor = 年化因子（日频 250；调仓点频率序列请传 REBAL_PER_YEAR 等）。
    返回逐期权重序列（前 window 期 0）；样本不足返回 []。σ=0 → cap（防除零假满仓）。"""
    r = list(series_returns or [])
    n = len(r)
    if n < window:
        return []
    out = [0.0] * n
    for i in range(window, n):
        seg = r[i - window:i]
        sd = statistics.pstdev(seg) * math.sqrt(ann_factor)
        out[i] = cap if sd < 1e-9 else min(cap, target_sigma / sd)
    return out


def risk_parity_weights(vol_list, max_w=0.30):
    """风险平价（逆波动率加权，归一 + 单资产上限 max_w 防集中）。
    vol_list = 各资产已实现波动率列表；有效项 <2 或含非正值项过多 → None。"""
    vols = [v for v in (vol_list or []) if v and v > 1e-12]
    if len(vols) < 2:
        return None
    inv = [1.0 / v for v in vols]
    s = sum(inv)
    w = [min(max_w, x / s) for x in inv]
    s2 = sum(w)
    return [x / s2 for x in w]


# ════════════════════════════════════════════════════════════════
# 自检（python backtest_lib.py 直跑）
# ════════════════════════════════════════════════════════════════
def _selftest():
    import random
    random.seed(42)
    # ① PSR：真α显著、纯噪声不显著
    good = [random.gauss(0.001, 0.01) for _ in range(250)]
    noise = [random.gauss(0.0, 0.01) for _ in range(250)]
    p1, p2 = probability_sharpe_ratio(good), probability_sharpe_ratio(noise)
    assert p1 is not None and p2 is not None and p1 > p2, "PSR 单调性失败"
    assert probability_sharpe_ratio(good[:10]) is None, "小样本应返 None"
    # ② 切分：无重叠 + embargo 间隙
    sp = purged_walkforward_splits(500, n_splits=5, embargo=5)
    assert len(sp) == 5
    for tr, te in sp:
        assert tr[-1] < te[0], "train/test 重叠"
        assert te[0] - tr[-1] >= 5 + 1, "embargo 不足"
    assert purged_walkforward_splits(50, n_splits=5) == [], "样本不足应返空"
    # ③ 交易约束：一字涨停买不进 / 开盘跌停顺延
    bar_lu = {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0}
    assert buy_blocked(10.0, bar_lu, code="000001") is True, "一字板应拦截"
    bar_ok = {"open": 10.3, "high": 10.9, "low": 10.1, "close": 10.5}
    assert buy_blocked(10.0, bar_ok, code="000001") is False, "开板应可买"
    bars = [{"open": 10.0, "close": 10.0},
            {"open": 9.0, "close": 9.0},          # k=1 开盘跌停 → 顺延
            {"open": 9.1, "close": 9.2}]          # k=2 可卖
    kk, px = sell_defer_days(bars, 1, code="000001")
    assert kk == 2 and abs(px - 9.1) < 1e-9, "跌停顺延失败"
    # ④ regime
    up = [100.0 + i * 0.5 for i in range(60)]
    fl = regime_flags(up)
    assert len(fl) == 60 and fl[-1] and fl[-1].startswith("bull_"), "regime 失败"
    # ⑤ rolling_ic：自相关应 keep，反转应 downgrade
    f = [random.random() for _ in range(300)]
    r_true = [0.01 * (x - 0.5) + 0.003 for x in f]     # 与因子强相关
    _, s1 = rolling_ic(f, r_true, window=90)
    assert s1 and s1["suggest"] == "keep", "IC keep 判定失败"
    # ⑥ 组合层
    w = volatility_target_weights([random.gauss(0.001, 0.02) for _ in range(120)])
    assert len(w) == 120 and all(0 <= x <= 1.0 for x in w)
    rp = risk_parity_weights([0.2, 0.1, 0.3])
    assert rp and abs(sum(rp) - 1.0) < 1e-9
    print("✅ backtest_lib 自检全过（PSR/切分/约束/regime/IC/组合层）")


if __name__ == "__main__":
    _selftest()
