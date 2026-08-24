#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cockpit_advice.py — 生成驾驶舱顶部「回测驱动的买卖建议」横幅数据
==================================================================
逻辑：
1. 读 data/backtest_tdx.json（K线60日全量回测，已含每只票逐日信号 + 回测汇总）
2. 回测结论：从 summary 取 5日突破(breakout_5d) 的 T+3/T+5 胜率与收益作为主推信号
3. 当前候选：对每只票取「最近一次触发 breakout_5d 的日期」作为新近突破，
   按信号日期降序取前 N 只（最新突破优先），并标注该信号日的入场价与历史T+3/T+5收益
4. 输出 data/cockpit_advice.json，供 index_master.html 顶部横幅读取

口径说明：
- 候选代表「近期出现 5日突破 形态」，非保证未来上涨；按回测胜率纪律操作。
- 仅作决策辅助，不构成投资建议。
"""
import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime, timedelta

from fundamental_helper import fq_key_of, load_fundamental, quality_points

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "..", "out", "backtest_tdx.json")
OUT = os.path.join(BASE, "..", "out", "cockpit_advice.json")
FQ = load_fundamental()  # 基本面质量分（含消息面加减分）
TODAY = datetime.now().strftime("%Y-%m-%d")

TOP_N = 8  # 顶部横幅最多展示的候选数


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def main():
    bt = load_json(SRC)
    if not bt:
        print("⚠️ 无 backtest_tdx.json，无法生成建议")
        return

    summary = bt.get("summary", {})
    bk = summary.get("breakout_5d", {})
    # 2026-07-26: 动态挑选 5日突破 最佳持有期（1/3/5/10/20日）
    periods = [1, 3, 5, 10, 20]
    best_pd = 5
    best_wr = 0.0
    for pd in periods:
        wr = bk.get(f"win_rate_{pd}d", 0)
        if wr > best_wr:
            best_wr = wr
            best_pd = pd
    wr_best = bk.get(f"win_rate_{best_pd}d", 0)
    ar_best = bk.get(f"avg_return_{best_pd}d", 0)
    smp = bk.get("total", 0)

    # 取一份对照信号（量价背离、放量上涨）用于横幅副信息
    div = summary.get("divergence", {})
    vol = summary.get("volume_surge", {})

    stocks = bt.get("stocks", {})

    # 收集每只票「最近一次 breakout_5d」信号（近35天内）
    recents = []
    for key, sr in stocks.items():
        sigs = sr.get("signals")
        if not sigs:
            continue
        latest_dt = None
        latest_sd = None
        for dt, sd in sigs.items():
            if "breakout_5d" in sd.get("signals", {}):
                if latest_dt is None or dt > latest_dt:
                    latest_dt = dt
                    latest_sd = sd
        if latest_sd is None:
            continue
        try:
            sig_d = datetime.strptime(latest_dt, "%Y-%m-%d")
            if (datetime.now() - sig_d).days > 35:
                continue
        except Exception:
            pass
        qscore, qgrade, qdetail = quality_points(
            FQ.get(fq_key_of(sr.get("market"), sr.get("code")), {}))
        # 读取全部周期收益，并计算最佳周期
        ret_map = {pd: latest_sd.get(f"ret_{pd}d") for pd in periods}
        valid_rets = {pd: v for pd, v in ret_map.items() if v is not None}
        best_stock_pd = best_pd
        best_stock_ret = ret_map.get(best_pd)
        if valid_rets:
            best_stock_pd = max(valid_rets, key=lambda p: valid_rets[p])
            best_stock_ret = valid_rets[best_stock_pd]
        recents.append({
            "code": sr.get("code", ""),
            "name": sr.get("name", key),
            "market": sr.get("market", ""),
            "signal_date": latest_dt,
            "entry_price": latest_sd.get("entry_price"),
            "ret_1d": latest_sd.get("ret_1d"),
            "ret_3d": latest_sd.get("ret_3d"),
            "ret_5d": latest_sd.get("ret_5d"),
            "ret_10d": latest_sd.get("ret_10d"),
            "ret_20d": latest_sd.get("ret_20d"),
            "best_period": best_stock_pd,
            "best_ret": best_stock_ret,
            "quality_grade": qgrade,
            "quality_score": qscore,
            "quality_detail": qdetail,
        })

    # 关注池：近期突破且按最佳周期未深跌（>= -3%），按信号日期降序、最佳收益降序
    watch = [c for c in recents if (c["best_ret"] is None or c["best_ret"] >= -3)]
    watch.sort(key=lambda x: (x["signal_date"], x["best_ret"] if x["best_ret"] is not None else 999),
               reverse=True)
    watch = watch[:TOP_N]

    # 回避名单：近期突破但按最佳周期已破位（< -5%），按跌幅升序取最差的几只作反面教材
    avoid = [c for c in recents if c["best_ret"] is not None and c["best_ret"] < -5]
    avoid.sort(key=lambda x: x["best_ret"])
    avoid = avoid[:3]

    advice = {
        "gen_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verdict": {
            "best_signal": "5日突破",
            "win_rate_3d": bk.get("win_rate_3d", 0),
            "avg_return_3d": bk.get("avg_return_3d", 0),
            "win_rate_5d": bk.get("win_rate_5d", 0),
            "avg_return_5d": bk.get("avg_return_5d", 0),
            "win_rate_best": wr_best,
            "avg_return_best": ar_best,
            "best_period": best_pd,
            "sample": smp,
            "hold_days": best_pd,
            "ref_signal_2": "量价背离" if div else "",
            "ref_wr3_2": div.get("win_rate_3d", 0),
            "ref_signal_3": "放量上涨" if vol else "",
            "ref_wr3_3": vol.get("win_rate_3d", 0),
        },
        "watch": watch,
        "avoid": avoid,
        "risk": f"基于金股池历史回测胜率纪律：轻仓试多、单只≤30%、持有{best_pd}日；止损止盈按全站统一口径执行（止损取近20日低点/ATR×2/固定百分比中最严者，止盈按前高→0.618回撤→R:R=2 择首个盈亏比≥1.5 者），盈亏比不足 1.5 不介入；共振≥80样本不足，不作为单一信号。",
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(advice, f, ensure_ascii=False, indent=2)

    # 🔴 2026-08-25 一劳永逸：直接导出 data/COCKPIT_ADVICE.js（脱离云端未知导出步）
    #   此前该脚本只写 out/cockpit_advice.json，data/X.js 由云端 build 特有导出步生成；
    #   云端整链超时截断后方脚本 → out 陈旧 → 每次 build 用旧 out 重导出覆盖本地推送的新鲜 data。
    #   脚本自带 data 导出后，云端 run_algorithms 跑到本脚本即直接写出新鲜 data/X.js，不再被覆盖。
    DATA_JS = os.path.join(BASE, "..", "data", "COCKPIT_ADVICE.js")
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write("window.COCKPIT_ADVICE = ")
        json.dump(advice, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    print(f"✅ 导出 {DATA_JS}")

    print(f"✅ 生成 {OUT}")
    print(f"   主推信号: 5日突破 | 最佳T+{best_pd}胜率 {wr_best}% / 收益 {ar_best:+.2f}% | 样本 {smp}")
    print(f"   关注池(近期突破且守住): {len(watch)} 只 | 回避名单(已破位): {len(avoid)} 只")
    for c in watch:
        print(f"     [关注] {c['signal_date']} {c['name']}({c['code']}) 入场{c['entry_price']} 最佳T+{c['best_period']}={c['best_ret']}% 基本面{c['quality_grade'] or '-'}({c['quality_score']:+d})")
    for c in avoid:
        print(f"     [回避] {c['signal_date']} {c['name']}({c['code']}) 最佳T+{c['best_period']}={c['best_ret']}% 基本面{c['quality_grade'] or '-'}({c['quality_score']:+d})")


if __name__ == "__main__":
    main()
