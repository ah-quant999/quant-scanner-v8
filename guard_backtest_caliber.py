#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard_backtest_caliber.py — 回测产物口径守卫（2026-09-20 建立）

问题背景（实证，非推断）：
  raw_data/backtest_expectancy.json 是融合器权重的**唯一真源**，但全仓 34 个
  校验/守卫脚本**无一登记它**（2026-09-20 实测：在 .github/scripts、guard_*、
  verify_*、v8_health_check 等脚本中检索 "backtest_expectancy" 命中 0）。
  后果有三，均已实际发生：
    ① 口径回退无人拦：2026-09-20 09:44 推送的新口径产物（entry_mode=next_open、
       46 快照），7 分钟后被 A 批「v8 cn fetch: 2026-09-20 09:51」提交用云端旧
       版本反向覆盖（generated 退回 09-19 18:18、n_snapshots 退回 65）——
       git 不报任何冲突，是干净 fast-forward 提交，静默完成。
    ② 假 partial 无人发现：旧产物长期声称 coverage.with_kline=1124/1124=100%、
       partial=false；实测真值 686/803=85%、有效样本 588、T+10 仅 495/1124=44%。
    ③ β 假象无人拦：旧产物 by_factor 只给 edge(on−off) 绝对收益差，T+10 档被大盘
       β 撑高 ⇒ 融合器按 edge10×2.5 计权，sig_jinzuan 得 +20 分（实盘 T+5 超额
       应 +1 分），高估约 20 倍。
  本守卫即为此建立：产物缺口径字段、或口径回退到旧版，一律 fail（可 --warn 降级）。

不做什么（边界，避免误伤）：
  · 不改产物、不重算、不推送 —— 纯只读校验。
  · 不校验「数值好坏」（不判 edge 正负、不判源数增减）——那是主人的裁量权，
    本脚本只判「口径字段是否到位、是否自洽」。
  · 不依赖网络、不依赖 baostock —— 只读本地 json，可在 CI 与双机任意环境跑。

用法：
  python guard_backtest_caliber.py                      # 默认读仓根 raw_data/backtest_expectancy.json
  python guard_backtest_caliber.py --path X.json
  python guard_backtest_caliber.py --warn               # 只告警不失败（过渡期用）
  python guard_backtest_caliber.py --json               # 输出机器可读结果

退出码：0=通过 / 1=失败（发现口径缺失或回退） / 2=文件缺失（暂不视为失败，但报告）
"""
import argparse
import io
import json
import os
import sys

# ── 口径基线：与 algorithms/backtest_expectancy.py 的常量保持同源 ──
# 若脚本侧改了 COST_ROUND_TRIP_PCT / ENTRY_MODE，本处须同步（否则守卫会误判）
EXPECT_ENTRY_MODE = "next_open"
EXPECT_COST = 0.2
# 这些 meta 键是 2026-09-20 口径改造新增，缺任一即表示「产物仍是旧口径」
REQUIRED_META_KEYS = (
    "entry_mode", "entry_note", "cost_round_trip_pct", "cost_note",
    "is_oos", "downrank_basis",
)
# 每个 by_factor 源必须具备的字段（超额层 + 判定层）
REQUIRED_FACTOR_KEYS = ("excess3", "excess5", "excess10", "baseline", "verdict", "verdict_basis")
REQUIRED_SEG_KEYS = ("excess_is", "excess_oos")
# 期望收益回测里必须存在的信号因子（融合器四信号权重的来源）
SIGNAL_FACTORS = ("sig_jinzuan", "sig_chan", "sig_trend", "sig_jigou")


def _load(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check(d, path):
    """返回 (problems, warns, info)。problems 非空即失败。"""
    P, W, I = [], [], []

    meta = d.get("meta") or {}
    if not meta:
        P.append("meta 段缺失或为空 —— 无法判断产物口径")
        return P, W, I

    I.append("generated      = %s" % meta.get("generated"))
    I.append("n_snapshots    = %s   date_range=%s" % (meta.get("n_snapshots"), meta.get("date_range")))
    I.append("entry_mode     = %s" % meta.get("entry_mode"))
    I.append("cost           = %s" % meta.get("cost_round_trip_pct"))

    # ── 1. 口径字段是否到位 ──
    miss = [k for k in REQUIRED_META_KEYS if meta.get(k) in (None, "")]
    if miss:
        P.append(
            "meta 缺口径字段 %s ⇒ 产物仍是 2026-09-20 口径改造前的旧版"
            "（旧版无 entry_mode/cost/is_oos，融合器会退回 T+10 edge 的 β 假象）" % miss
        )

    # ── 2. 口径值是否与脚本同源 ──
    em = meta.get("entry_mode")
    if em is not None and em != EXPECT_ENTRY_MODE:
        P.append("entry_mode=%r ≠ 期望 %r ⇒ 入场口径回退（旧版按 T 日收盘成交，含前视偏差）"
                 % (em, EXPECT_ENTRY_MODE))
    cp = meta.get("cost_round_trip_pct")
    if cp is not None:
        try:
            if abs(float(cp) - EXPECT_COST) > 1e-9:
                P.append("cost_round_trip_pct=%s ≠ 期望 %s ⇒ 成本口径漂移" % (cp, EXPECT_COST))
        except (TypeError, ValueError):
            P.append("cost_round_trip_pct=%r 非数值" % cp)

    # ── 3. IS/OOS 结构 ──
    iso = meta.get("is_oos")
    if isinstance(iso, dict) and iso:
        for k in ("is_ratio", "is_dates", "oos_dates", "is_range", "oos_range"):
            if iso.get(k) in (None, ""):
                P.append("meta.is_oos 缺子键 %s ⇒ IS/OOS 分段不完整" % k)
        if iso.get("is_dates") == 0 or iso.get("oos_dates") == 0:
            P.append("IS 或 OOS 段样本为 0 ⇒ 无法做跨期稳健性判定")
        I.append("is_oos         = IS %s 日 / OOS %s 日  (%s → %s)"
                 % (iso.get("is_dates"), iso.get("oos_dates"), iso.get("is_range"), iso.get("oos_range")))
    elif iso is not None:
        P.append("meta.is_oos 非 dict（%r）" % type(iso).__name__)

    # ── 4. coverage 自洽（抓「假 partial=false」家族） ──
    cov = meta.get("coverage") or {}
    if cov:
        tot = cov.get("stocks_total") or 0
        wk = cov.get("with_kline") or 0
        ok_ = cov.get("occ_total") or 0
        if tot and wk > tot:
            P.append("coverage.with_kline(%s) > stocks_total(%s) ⇒ 数据自相矛盾" % (wk, tot))
        rate = (wk / tot * 100.0) if tot else 0.0
        I.append("coverage       = with_kline %s/%s (%.1f%%)  occ_total=%s" % (wk, tot, rate, ok_))
        # partial 与可得率是否自洽：可得率明显 <95% 却声称 partial=false ⇒ 可疑
        if meta.get("partial") is False and tot and rate < 95.0:
            W.append("meta.partial=false 但 with_kline 可得率仅 %.1f%% ⇒ partial 标记可能失真"
                     "（请核对，不自动判错）" % rate)

    # ── 5. by_factor 超额层 + verdict ──
    bf = d.get("by_factor") or {}
    if not bf:
        P.append("by_factor 为空 ⇒ 融合器无权重可取")
    else:
        I.append("by_factor 源数  = %d" % len(bf))
        I.append("")
        I.append("%-16s %10s %10s %8s %-8s" % ("factor", "excess5", "edge10(旧)", "n_on5", "verdict"))
        for k, v in sorted(bf.items(), key=lambda kv: -(kv[1].get("excess5") or -999)):
            I.append("%-16s %+10.3f %+10.3f %8s %-8s" % (
                k, v.get("excess5") or 0,
                (v.get("edge10") if v.get("edge10") is not None else 0),
                v.get("n_on5"), v.get("verdict")))
        for k, v in bf.items():
            m = [x for x in REQUIRED_FACTOR_KEYS if v.get(x) is None]
            if m:
                P.append("by_factor[%s] 缺字段 %s ⇒ 未过 build_excess（超额层未生效）" % (k, m))
            seg = v.get("excess_is"), v.get("excess_oos")
            if any(isinstance(s, dict) and not s for s in seg if s is not None):
                W.append("by_factor[%s] 分段超额为空 dict" % k)
            vd = v.get("verdict")
            if vd is not None and vd not in ("keep", "watch", "drop"):
                P.append("by_factor[%s].verdict=%r 非 keep/watch/drop" % (k, vd))
            # verdict 与 excess5 的自洽（判据阈值 ±0.30，样本<30 一律 watch）
            n5, ex5 = v.get("n_on5") or 0, v.get("excess5")
            if ex5 is not None and vd:
                exp = "watch" if n5 < 30 else ("keep" if ex5 >= 0.30 else ("drop" if ex5 <= -0.30 else "watch"))
                if vd != exp:
                    W.append("by_factor[%s] verdict=%s 与 excess5=%+.3f/n_on5=%s 推算的 %s 不符"
                             % (k, vd, ex5, n5, exp))
        miss_sig = [s for s in SIGNAL_FACTORS if s not in bf]
        if miss_sig:
            P.append("四信号因子缺失 %s ⇒ 融合器信号权重将回退硬编码默认值" % miss_sig)

    # ── 6. by_signal（P2 组合反哺的来源） ──
    bs = d.get("by_signal") or {}
    if not bs:
        W.append("by_signal 为空 ⇒ 组合级回测反哺失效（score_backtest 全为 0）")
    else:
        I.append("")
        I.append("by_signal 组合数 = %d" % len(bs))
        bad = []
        for k, v in bs.items():
            if v.get("edge5") is None:
                bad.append(k)
        if bad:
            P.append("by_signal 组合 %s 缺 edge5 ⇒ 组合反哺取不到值（改动15 已改读 edge5）" % bad)
        # 提示：by_signal 无 excess 层（仅 by_factor 有 baseline），守卫只校验 edge5 在位
        I.append("  （注：by_signal 层无 excess 基准，融合器读其 edge5；by_factor 层读 excess5）")

    return P, W, I


def main():
    ap = argparse.ArgumentParser(description="回测产物口径守卫（只读；异常可 --warn 降级）")
    ap.add_argument("--path", default=None, help="产物路径（默认 <repo>/raw_data/backtest_expectancy.json）")
    ap.add_argument("--warn", action="store_true", help="只告警，失败也返回 0（过渡期用）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    a = ap.parse_args()

    path = a.path
    if not path:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "raw_data", "backtest_expectancy.json")

    if not os.path.exists(path):
        msg = "[口径守卫] 产物不存在：%s（跳过校验）" % path
        if a.json:
            print(json.dumps({"ok": None, "missing": True, "path": path, "message": msg}, ensure_ascii=False))
        else:
            print(msg)
        return 2

    try:
        d = _load(path)
    except Exception as e:
        print("[口径守卫] ❌ 产物解析失败：%s: %s" % (type(e).__name__, e))
        return 1

    P, W, I = check(d, path)
    ok = not P

    if a.json:
        print(json.dumps({"ok": ok, "path": path, "problems": P, "warns": W, "info": I},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print("回测产物口径守卫  %s" % path)
        print("=" * 78)
        for x in I:
            print(x)
        print("")
        for x in W:
            print("  ⚠️  " + x)
        for x in P:
            print("  ❌ " + x)
        print("")
        if ok:
            print("✅ 口径校验通过（entry_mode=%s / cost=%s / IS-OOS 在位 / 超额层完整）"
                  % (d.get("meta", {}).get("entry_mode"), d.get("meta", {}).get("cost_round_trip_pct")))
        else:
            print("❌ 口径校验失败：%d 项问题 ⇒ 融合器权重可能建立在旧口径（β 假象）之上" % len(P))
            print("   处置：确认 algorithms/backtest_expectancy.py 为新版，并让 E 批重跑产出；")
            print("        若确为回退事故，参照 docs/ops/handover 中「产物被 A 批 fetch 覆盖」的记录。")
        print("")

    if not ok and not a.warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
