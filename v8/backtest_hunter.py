# -*- coding: utf-8 -*-
"""
backtest_hunter.py — 大牛股猎手（机游共振核心信号）历史回测

背景：
  已下架选股模块中的「大牛股猎手」基于龙虎榜机游共振渲染：
  机构净买>0 且 游资净买>0 且 (机构+游资)>=8000万。
  星级 = ⭐⭐⭐（UI 展示级），但此前无回测证据。

本脚本：
  1. 读取 raw_data/lhb_history.json 全部历史龙虎榜。
  2. 按上述规则提取核心共振信号。
  3. 用 akshare 拉取信号股历史 K 线（缓存到 raw_data/kline_cache/）。
  4. 计算 T+1/T+3/T+5/T+10/T+20 持有期收益（信号日收盘价买入，持有 N 个交易日收盘价卖出）。
  5. 输出 raw_data/hunter_backtest.json + data/HUNTER_BACKTEST.js。

输出字段：
  - summary: 信号总数、可计算样本数、各持有期胜率/平均收益/盈亏比/最大收益/最大亏损
  - by_period: 各持有期明细统计
  - by_date: 按信号日聚合（便于追踪时间衰减）
  - signals: 逐信号明细（含买入/卖出价、收益、是否可算）

使用：
  python v8/backtest_hunter.py              # 全量回测
  python v8/backtest_hunter.py --dry        # 只统计信号数，不拉K线

注意：
  - lhb_history.json 中 price 字段全为 0，必须用外部 K 线。
  - 为避免盘中/开盘前网络抖动，单只 K 线失败 3 次重试，仍失败则该信号标记为 missing_kline。
  - 本脚本为本地数据层工具，可被 index.html 策略回测区读取展示；也可单独跑看报告。
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import baostock as bs

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
LHB_FILE = RAW_DIR / "lhb_history.json"
CACHE_DIR = RAW_DIR / "kline_cache"
OUT_JSON = RAW_DIR / "hunter_backtest.json"
OUT_JS = DATA_DIR / "HUNTER_BACKTEST.js"

CORE_THRESHOLD_WAN = 8000  # 机构+游资净买入阈值（万元）
HOLD_PERIODS = [1, 3, 5, 10, 20]


def load_lhb_history():
    if not LHB_FILE.exists():
        raise FileNotFoundError(f"找不到 {LHB_FILE}")
    with open(LHB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_core_signals(hist):
    """按大牛股猎手「核心共振」规则提取信号。"""
    signals = []
    for day, data in hist.items():
        if not isinstance(data, dict):
            continue
        # day 形如 '2026-06-10' 或 'update_time' 等元数据键
        if not (len(day) == 10 and day[4] == "-" and day[7] == "-"):
            continue
        for s in data.get("stocks", []):
            if not isinstance(s, dict):
                continue
            inst = float(s.get("inst_net_万") or 0)
            yz = float(s.get("yz_net_万") or 0)
            if inst > 0 and yz > 0 and (inst + yz) >= CORE_THRESHOLD_WAN:
                signals.append({
                    "signal_date": day,
                    "code": str(s.get("code", "")).strip(),
                    "name": str(s.get("name", "")).strip(),
                    "inst_net_wan": round(inst, 2),
                    "yz_net_wan": round(yz, 2),
                    "total_net_wan": round(inst + yz, 2),
                    "reason": str(s.get("reason", "")),
                })
    signals.sort(key=lambda x: (x["signal_date"], x["code"]))
    return signals


_BS_LOGGED_IN = False

def _bs_login():
    global _BS_LOGGED_IN
    if _BS_LOGGED_IN:
        return True
    lg = bs.login()
    if lg.error_code == "0":
        _BS_LOGGED_IN = True
        return True
    print(f"⚠️ baostock login failed: {lg.error_code} {lg.error_msg}")
    return False


def _bs_code(code):
    """6位数字转 baostock 代码格式。"""
    c = str(code).strip()
    if c.startswith("6"):
        return f"sh.{c}"
    elif c.startswith("0") or c.startswith("3"):
        return f"sz.{c}"
    elif c.startswith("4") or c.startswith("8") or c.startswith("92"):
        return f"bj.{c}"
    return f"sz.{c}"


def ensure_kline(code, start_date, end_date, retries=3, sleep=1.0):
    """获取/缓存单只股票前复权日K。code 为 6 位数字。"""
    if not _bs_login():
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{code}.json"
    # 简单缓存：只要存在就返回（后续可扩展按日期区间更新）
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    bs_symbol = _bs_code(code)
    fields = "date,open,close,high,low,volume,pctChg"
    for attempt in range(retries):
        try:
            rs = bs.query_history_k_data_plus(
                bs_symbol, fields,
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="2"  # 2=前复权
            )
            if rs.error_code != "0":
                print(f"  ⚠️ {code}({bs_symbol}) query error: {rs.error_code} {rs.error_msg}")
                time.sleep(sleep * (attempt + 1))
                continue
            records = []
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                try:
                    records.append({
                        "date": str(row[0]),
                        "open": float(row[1] or 0),
                        "close": float(row[2] or 0),
                        "high": float(row[3] or 0),
                        "low": float(row[4] or 0),
                        "volume": int(float(row[5] or 0)),
                        "pct": float(row[6] or 0),
                    })
                except Exception:
                    pass
            if records:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
                return records
        except Exception as e:
            print(f"  ⚠️ {code}({bs_symbol}) K线获取失败 (attempt {attempt+1}/{retries}): {e}")
            time.sleep(sleep * (attempt + 1))
    return None


def calc_return(kline, signal_date, hold_days):
    """
    信号日收盘价买入，持有 hold_days 个交易日收盘价卖出。
    返回 (is_valid, return_pct, exit_date, entry_price, exit_price, note)
    """
    if not kline:
        return False, None, None, None, None, "无K线"
    # 建立日期索引
    date_to_idx = {r["date"]: i for i, r in enumerate(kline)}
    if signal_date not in date_to_idx:
        return False, None, None, None, None, f"信号日 {signal_date} 不在K线中"
    entry_idx = date_to_idx[signal_date]
    entry = kline[entry_idx]
    entry_price = entry.get("close", 0)
    if entry_price <= 0:
        return False, None, None, None, None, "信号日收盘价异常"
    exit_idx = entry_idx + hold_days
    if exit_idx >= len(kline):
        return False, None, None, None, None, "持有期超出K线范围"
    exit_rec = kline[exit_idx]
    exit_price = exit_rec.get("close", 0)
    if exit_price <= 0:
        return False, None, None, None, None, "卖出日收盘价异常"
    ret = exit_price / entry_price - 1.0
    return True, ret, exit_rec["date"], entry_price, exit_price, "ok"


def backtest(signals, dry=False):
    today_str = date.today().isoformat()
    if signals:
        min_date = min(s["signal_date"] for s in signals)
        max_date = max(s["signal_date"] for s in signals)
        # 向后多取 35 个自然日以覆盖 T+20 交易日
        end_dt = datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=35)
        end_date = end_dt.strftime("%Y-%m-%d")
    else:
        min_date, end_date = "2026-01-01", today_str

    # 按股票聚合信号，减少重复拉 K 线
    code_to_signals = {}
    for s in signals:
        code_to_signals.setdefault(s["code"], []).append(s)

    enriched_signals = []
    code_klines = {}

    if dry:
        for s in signals:
            es = dict(s)
            es["results"] = {p: {"valid": False, "return": None, "note": "dry-run"} for p in HOLD_PERIODS}
            enriched_signals.append(es)
        return enriched_signals, code_klines

    total_codes = len(code_to_signals)
    for i, code in enumerate(sorted(code_to_signals.keys()), 1):
        print(f"[{i}/{total_codes}] 拉取 {code} K线...")
        kline = ensure_kline(code, min_date, end_date)
        code_klines[code] = kline
        for s in code_to_signals[code]:
            es = dict(s)
            results = {}
            for p in HOLD_PERIODS:
                valid, ret, exit_date, ep, xp, note = calc_return(kline, s["signal_date"], p)
                results[p] = {
                    "valid": valid,
                    "return_pct": round(ret * 100, 2) if ret is not None else None,
                    "exit_date": exit_date,
                    "entry_price": round(ep, 2) if ep else None,
                    "exit_price": round(xp, 2) if xp else None,
                    "note": note,
                }
            es["results"] = results
            enriched_signals.append(es)
        # 轻量限速，避免触发 baostock 频率限制
        time.sleep(0.2)

    enriched_signals.sort(key=lambda x: (x["signal_date"], x["code"]))
    return enriched_signals, code_klines


def summarize(enriched_signals):
    summary = {
        "total_signals": len(enriched_signals),
        "calc_time": datetime.now().isoformat(),
        "method": "大牛股猎手机游共振核心信号：机构净买>0 且 游资净买>0 且 (机构+游资)>=8000万；信号日收盘价买入，持有N个交易日收盘价卖出",
        "signal_date_range": "",
        "by_period": {},
        "by_date": {},
    }
    if enriched_signals:
        summary["signal_date_range"] = f"{enriched_signals[0]['signal_date']} ~ {enriched_signals[-1]['signal_date']}"

    for p in HOLD_PERIODS:
        valid = [s for s in enriched_signals if s["results"].get(p, {}).get("valid")]
        returns = [r["results"][p]["return_pct"] for r in valid]
        wins = [r for r in returns if r is not None and r > 0]
        losses = [r for r in returns if r is not None and r <= 0]
        summary["by_period"][p] = {
            "samples": len(valid),
            "win_rate": round(len(wins) / len(valid) * 100, 1) if valid else 0.0,
            "avg_return": round(sum(returns) / len(returns), 2) if returns else 0.0,
            "best_return": round(max(returns), 2) if returns else 0.0,
            "worst_return": round(min(returns), 2) if returns else 0.0,
            "win_avg": round(sum(wins) / len(wins), 2) if wins else 0.0,
            "loss_avg": round(sum(losses) / len(losses), 2) if losses else 0.0,
            "profit_loss_ratio": round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)), 2)
            if wins and losses and sum(losses) != 0 else None,
        }

    for s in enriched_signals:
        d = s["signal_date"]
        by = summary["by_date"].setdefault(d, {"count": 0, "valid_T+1": 0, "avg_T+1": None})
        by["count"] += 1
        r1 = s["results"].get(1, {})
        if r1.get("valid"):
            by["valid_T+1"] += 1
            if by["avg_T+1"] is None:
                by["avg_T+1"] = []
            by["avg_T+1"].append(r1["return_pct"])

    for d, by in summary["by_date"].items():
        if by["avg_T+1"]:
            by["avg_T+1"] = round(sum(by["avg_T+1"]) / len(by["avg_T+1"]), 2)
        else:
            by["avg_T+1"] = None

    return summary


def write_outputs(report):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    js = "window.HUNTER_BACKTEST = " + json.dumps(report, ensure_ascii=False, indent=2) + ";\n"
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"✅ 已写入 {OUT_JSON} 与 {OUT_JS}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="仅统计信号数，不拉K线")
    args = parser.parse_args()

    print("=" * 60)
    print("大牛股猎手（机游共振核心信号）历史回测")
    print("=" * 60)

    hist = load_lhb_history()
    signals = extract_core_signals(hist)
    print(f"📌 核心共振信号总数：{len(signals)}（涉及 {len(set(s['code'] for s in signals))} 只不同股票）")

    if not signals:
        print("无信号，退出")
        sys.exit(0)

    if args.dry:
        print("🚫 dry-run 模式，不拉K线")

    enriched, _ = backtest(signals, dry=args.dry)
    summary = summarize(enriched)

    report = {
        "summary": summary,
        "signals": enriched,
    }

    if not args.dry:
        write_outputs(report)

    if _BS_LOGGED_IN:
        bs.logout()

    # 控制台简表
    print("\n持有期统计（收盘价买入 -> 持有N日收盘价卖出）：")
    print(f"{'持有期':>8} {'样本':>6} {'胜率%':>8} {'平均收益%':>10} {'最佳%':>8} {'最差%':>8} {'盈亏比':>8}")
    for p, st in summary["by_period"].items():
        pl = st.get("profit_loss_ratio")
        pl_str = f"{pl:.2f}" if pl is not None else "—"
        print(f"{'T+'+str(p):>8} {st['samples']:>6} {st['win_rate']:>8.1f} {st['avg_return']:>10.2f} {st['best_return']:>8.2f} {st['worst_return']:>8.2f} {pl_str:>8}")


if __name__ == "__main__":
    main()
