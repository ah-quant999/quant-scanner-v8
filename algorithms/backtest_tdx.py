#!/usr/bin/env python3
"""
backtest_tdx.py — 通达信60天全量回测引擎 V3.2（方案二：止损止盈升级）
==========================================================================
用通达信K线拉金池股60天日K，计算全部可检测信号的T+1/T+3/T+5/T+10/T+20胜率。
收益口径已升级为「统一止损止盈 + 提前出场」：
  止损 = max(近20日低点, close-2ATR, 固定百分比)
  止盈 = cascade：前高 → 0.618回撤位 → R:R=2对称位（盈亏比≥1.5）
  ret_Nd 为提前出场后收益；raw_ret_Nd 为原持有期收盘价收益。

可检测信号（价格/量可推导）：
  - 上涨趋势  (EMA7>EMA14>EMA20)
  - 缠论买点  (底分型+量确认)
  - 逆势红色  (大盘跌时个股涨)
  - 价格突破  (5日/20日新高)
  - 放量上涨  (量>1.5倍均值+收阳)
  - 量价背离  (价新高但量萎缩）

不可检测（需外部数据）：
  - 金钻/黄柱 (需要XMA+DDX)
  - 机构变红  (需要机构数据)
  - 机游共振  (需要龙虎榜席位）

输出: data/backtest_tdx.json
"""
import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

sys.path.insert(0, BASE)
from stop_target_logic import (  # noqa: E402
    compute_stop_target,
    board_from_code,
)

BASE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：历史快照目录从 out/（gitignore，云端丢）→ raw_data/
DATA_DIR = os.path.join(BASE, "..", "raw_data")
OUT = os.path.join(DATA_DIR, "backtest_tdx.json")
TODAY = datetime.now().strftime("%Y-%m-%d")
HOLD_DAYS = [1, 3, 5, 10, 20]  # 2026-07-26: 从 3d/5d 扩展到 1/3/5/10/20d

def log(msg):
    print(f"  {msg}")

# ─── 通达信K线工具 ───
def tdx_kline(code, setcode, period="4", count=60):
    """通过subprocess调通达信MCP接口（因部署环境可能无MCP，做本地回退）"""
    # 如果本地有缓存优先用
    cache_dir = os.path.join(DATA_DIR, "_tdx_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = f"{setcode}_{code}_{period}_{count}"
    cache_file = os.path.join(cache_dir, cache_key.replace(".", "_") + ".json")
    if os.path.exists(cache_file) and os.path.getmtime(cache_file) > time.time() - 86400:
        try:
            d = json.load(open(cache_file, "r", encoding="utf-8"))
            if d.get("rows") and len(d["rows"]) >= 10:
                log(f"  [缓存] {code} ({setcode}) → {len(d['rows'])} 根K")
                return d["rows"]
        except:
            pass
    
    # 用 baostock 作主数据源（云端/本地都能跑，比MCP可靠）
    # 通达信MCP在自动化环境可能不可用，baostock是Pypi包，已安装
    import baostock as bs
    try:
        lg = bs.login()
        if lg.error_code != "0":
            log(f"  baostock登录失败: {lg.error_msg}")
            return None
        # code needs to be like "sz.002141" or "sh.601318"
        market_map = {"0": "sz", "1": "sh", "2": "bj", "31": "hk"}
        prefix = market_map.get(str(setcode), "sz")
        bs_code = f"{prefix}.{code}"
        
        end_date = TODAY  # 保持 YYYY-MM-DD
        start_dt = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        start_date = start_dt
        
        # baostock 不支持港股，跳过
        if prefix == "hk":
            return None
        
        rs = bs.query_history_k_data_plus(bs_code,
            "date,close,high,low,open,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="2")  # 后复权
        bs.logout()
        
        # rs 可能为 None（查询失败）
        if rs is None or rs.error_code != "0":
            log(f"  [baostock] {code}: 查询失败 ({rs.error_msg if rs else 'unknown'})")
            return None
        
        rows = []
        while rs.next():
            r = rs.get_row_data()
            if r[0] and float(r[1]) > 0:
                rows.append({
                    "date": r[0],
                    "close": float(r[1]),
                    "high": float(r[2]) if r[2] else float(r[1]),
                    "low": float(r[3]) if r[3] else float(r[1]),
                    "open": float(r[4]) if r[4] else float(r[1]),
                    "volume": float(r[5]) if r[5] else 0,
                    "amount": float(r[6]) if r[6] else 0,
                })
        
        if rows:
            rows.sort(key=lambda x: x["date"])
            log(f"  [baostock] {code} ({bs_code}) → {len(rows)} 根K ({rows[0]['date']} ~ {rows[-1]['date']})")
            # 缓存
            json.dump({"rows": rows, "ts": TODAY}, open(cache_file, "w", encoding="utf-8"))
            return rows
        else:
            log(f"  [baostock] {code}: 空数据")
            return None
    except Exception as e:
        log(f"  [baostock] {code}: {e}")
        return None


# ─── 信号检测器 ───
def detect_signals(rows):
    """从K线序列检测所有可计算信号，返回 {date: {signal_name: bool}}"""
    signals = {}
    n = len(rows)
    if n < 30:
        return signals
    
    # 提前算好所有需要的指标
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    opens = [r["open"] for r in rows]
    volumes = [r["volume"] for r in rows]
    
    # EMA计算
    def ema(data, period):
        result = [data[0]]
        k = 2 / (period + 1)
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result
    
    ema7 = ema(closes, 7)
    ema14 = ema(closes, 14)
    ema20 = ema(closes, 20)
    
    # 均量线
    vol_ma20 = []
    for i in range(len(volumes)):
        start = max(0, i - 19)
        vol_ma20.append(sum(volumes[start:i+1]) / (i - start + 1))
    
    for i in range(20, n):
        date = rows[i]["date"]
        sigs = {}
        
        # 1. 上涨趋势: EMA7 > EMA14 > EMA20
        sigs["trend_up"] = ema7[i] > ema14[i] > ema20[i]
        
        # 2. 下跌趋势 (补充)
        sigs["trend_down"] = ema7[i] < ema14[i] < ema20[i]
        
        # 3. 缠论底分型: 低-低-高 结构 + 量确认
        if i >= 2:
            low_prev2 = lows[i-2]
            low_prev1 = lows[i-1]
            low_curr = lows[i]
            # 底分型: 前低 < 前前低, 当日低 < 前低 (形成底部), 当日收阳
            is_bottom_pattern = lows[i-1] < lows[i-2] and lows[i] < lows[i-1] and closes[i] > lows[i]
            vol_confirm = volumes[i] > vol_ma20[i] * 0.8
            sigs["chan_buy"] = is_bottom_pattern and vol_confirm
        
        # 4. 逆势红色: 大盘跌时个股涨 (简化: 连跌2天后今日收涨)
        if i >= 2:
            prev_down = closes[i-2] > closes[i-1]  # 前日跌
            today_up = closes[i] > opens[i] and closes[i] > closes[i-1]  # 今日收涨
            sigs["contrarian"] = prev_down and today_up
        
        # 5. 价格突破: 创5日新高
        high_5d = max(highs[max(0,i-4):i+1])
        sigs["breakout_5d"] = highs[i] >= high_5d and closes[i] > closes[i-1]
        
        # 6. 放量上涨: 量>1.5×均量 + 收阳
        sigs["volume_surge"] = volumes[i] > vol_ma20[i] * 1.5 and closes[i] > opens[i]
        
        # 7. 量价背离: 价新高但量萎缩
        if i >= 5:
            price_up = closes[i] > closes[i-1] > closes[i-2]
            vol_down = volumes[i] < volumes[i-1] < volumes[i-2]
            sigs["divergence"] = price_up and vol_down
        
        # 8. 综合多信号 (≥2个信号同时触发)
        signal_count = sum(1 for v in sigs.values() if v)
        sigs["ge2_signals"] = signal_count >= 2
        sigs["ge3_signals"] = signal_count >= 3
        
        if any(sigs.values()):
            signals[date] = sigs
    
    return signals


def calc_forward_return(rows, idx, hold_days, board="主板"):
    """计算T+N日收益（方案二：按统一止损止盈口径模拟提前出场）。

    返回 {"ret": 提前出场后收益, "raw_ret": 原持有期收盘价收益,
          "exit_type": 'stop'/'target'/None, "stop_loss": ..., "target_price": ..., "risk_reward": ...}
    """
    n = len(rows)
    target = idx + hold_days
    if target >= n:
        return None
    entry = rows[idx]["close"]
    if entry <= 0:
        return None

    # 用 idx 当日及之前数据计算止损/止盈（非未来函数）
    df = pd.DataFrame(rows[: idx + 1])
    st = compute_stop_target(df, board=board)
    if st:
        stop_loss = st["stop_loss"]
        target_price = st["target_price"]
        rr = st["risk_reward"]
    else:
        # 数据不足时回退固定百分比
        stop_pct = 0.10 if board in ("创业板", "科创板") else 0.07
        stop_loss = entry * (1 - stop_pct)
        target_price = entry * (1 + max(0.105, stop_pct * 1.5))
        rr = round((target_price - entry) / (entry - stop_loss), 2)

    # 模拟每日 close 触发止损/止盈
    exit_price = rows[target]["close"]
    exit_type = None
    for j in range(idx + 1, target + 1):
        cp = rows[j]["close"]
        if cp <= stop_loss:
            exit_price = stop_loss
            exit_type = "stop"
            break
        if cp >= target_price:
            exit_price = target_price
            exit_type = "target"
            break

    raw_ret = round((rows[target]["close"] - entry) / entry * 100, 2)
    early_ret = round((exit_price - entry) / entry * 100, 2)
    return {
        "ret": early_ret,
        "raw_ret": raw_ret,
        "exit_type": exit_type,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_reward": rr,
    }


def _load_historical_pool_union(current_gp):
    """读取最近 90 天金股池快照的并集，减少「当前池=幸存者」偏差。
    快照不足时回退到当前池，并返回警告标志。"""
    hist_dir = os.path.join(DATA_DIR, "history")
    if not os.path.isdir(hist_dir):
        return current_gp, False, 0

    union_stocks = {}
    today = datetime.now().date()
    snapshots_used = 0
    for fn in sorted(os.listdir(hist_dir), reverse=True):
        if not fn.startswith("gold_pool_") or not fn.endswith(".json"):
            continue
        # 解析日期 gold_pool_YYYYMMDD.json
        try:
            date_str = fn.replace("gold_pool_", "").replace(".json", "")
            snap_date = datetime.strptime(date_str, "%Y%m%d").date()
        except Exception:
            continue
        if (today - snap_date).days > 90:
            continue
        try:
            snap = json.load(open(os.path.join(hist_dir, fn), "r", encoding="utf-8"))
            union_stocks.update(snap.get("stocks", {}))
            snapshots_used += 1
        except Exception:
            pass

    if snapshots_used <= 1:
        # 只有今天或没有快照，尚无法纠偏，回退当前池
        return current_gp, True, snapshots_used
    return union_stocks, False, snapshots_used


def main():
    print(f"\n{'='*60}")
    print(f"  通达信60天全量回测引擎 V3")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 读金股池，并尝试用历史快照并集作为回测宇宙（纠偏幸存者偏差）
    gp = json.load(open(os.path.join(DATA_DIR, "gold_pool.json"), "r", encoding="utf-8"))
    current_gp_stocks = gp.get("stocks", {})
    gp_stocks, survivor_bias_warning, snapshots_used = _load_historical_pool_union(current_gp_stocks)
    log(f"金股池: 当前 {len(current_gp_stocks)} 只 / 回测宇宙 {len(gp_stocks)} 只（历史快照 {snapshots_used} 个）")
    if survivor_bias_warning:
        log("⚠️ 历史金股池快照不足，回测仍含幸存者偏差（会随着每日快照累积逐步消除）")
    
    # 读取现有回测结果（用于增量追加）
    existing = {}
    try:
        existing = json.load(open(OUT, "r", encoding="utf-8"))
        log(f"读取已有回测: {len(existing.get('stocks', {}))} 只")
    except:
        pass
    
    stock_results = existing.get("stocks", {})
    
    # market映射
    setcode_map = {"hk": "31", "sh": "1", "sz": "0", "bj": "2"}
    
    for key, s in gp_stocks.items():
        code = s.get("code", "")
        mkt = s.get("market", "")
        name = s.get("name", key)
        
        # 跳过已处理的（缓存），但若旧数据缺少新增周期字段则重新计算
        if key in stock_results:
            old_sigs = stock_results[key].get("signals") or {}
            has_all_periods = bool(old_sigs) and all(
                f"ret_{d}d" in next(iter(old_sigs.values()), {}) and f"raw_ret_{d}d" in next(iter(old_sigs.values()), {})
                for d in HOLD_DAYS
            )
            if has_all_periods:
                log(f"  跳过 {name}({key}) — 已有回测")
                continue
            log(f"  重算 {name}({key}) — 补齐新周期")
        
        setcode = setcode_map.get(mkt, "0")
        rows = tdx_kline(code, setcode, count=60)
        if not rows or len(rows) < 30:
            stock_results[key] = {"code": code, "name": name, "market": mkt, "error": "数据不足", "signals": {}}
            continue
        
        # 检测信号
        signals = detect_signals(rows)
        n = len(rows)
        
        # 计算每个信号日期的T+1/T+3/T+5/T+10/T+20收益
        stock_signals = {}
        for date, sigs in signals.items():
            # 找到在K线中的索引
            idx = None
            for j in range(n):
                if rows[j]["date"] == date:
                    idx = j
                    break
            if idx is None or idx + max(HOLD_DAYS) >= n:
                continue

            returns = {}
            wins = {}
            raw_returns = {}
            exit_types = {}
            board = board_from_code(code)
            for d in HOLD_DAYS:
                res = calc_forward_return(rows, idx, d, board=board)
                if res is None:
                    returns[f"ret_{d}d"] = None
                    wins[f"win_{d}d"] = None
                    raw_returns[f"raw_ret_{d}d"] = None
                    exit_types[f"exit_type_{d}d"] = None
                else:
                    returns[f"ret_{d}d"] = res["ret"]
                    wins[f"win_{d}d"] = res["ret"] > 0
                    raw_returns[f"raw_ret_{d}d"] = res["raw_ret"]
                    exit_types[f"exit_type_{d}d"] = res["exit_type"]

            stock_signals[date] = {
                "signals": {k: v for k, v in sigs.items() if v and k not in ("ge2_signals", "ge3_signals")},
                "signal_count": sum(1 for k, v in sigs.items() if v and k not in ("ge2_signals", "ge3_signals")),
                "ge2": sigs.get("ge2_signals", False),
                "ge3": sigs.get("ge3_signals", False),
                "entry_price": rows[idx]["close"],
                **returns,
                **wins,
                **raw_returns,
                **exit_types,
            }
        
        stock_results[key] = {
            "code": code,
            "name": name,
            "market": mkt,
            "date_range": f"{rows[0]['date']}~{rows[-1]['date']}",
            "kline_days": n,
            "days_with_signals": len(stock_signals),
            "signals": stock_signals,
        }
        signal_days = len(stock_signals)
        log(f"  {name}({code}): {n}天K线, {signal_days}天含信号")
        
        # 每处理一只存一次（防中断丢失）
        json.dump({
            "calc_time": TODAY,
            "method": f"baostock 60日K线全量回测 (T+{', T+'.join(map(str, HOLD_DAYS))})",
            "gold_pool_size": len(gp_stocks),
            "stocks": stock_results,
        }, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    
    # ── 汇总统计 ──
    log(f"\n{'='*60}")
    log(f"生成汇总统计...")
    
    # 按信号类型汇总（动态支持 HOLD_DAYS 所有周期）
    def _new_summary():
        d = {"total": 0}
        for d_ in HOLD_DAYS:
            d[f"win_{d_}d"] = 0
            d[f"loss_{d_}d"] = 0
            d[f"draw_{d_}d"] = 0
            d[f"total_ret_{d_}d"] = 0.0
            d[f"win_ret_{d_}d"] = 0.0
            d[f"loss_ret_{d_}d"] = 0.0
        return d
    summary = defaultdict(_new_summary)

    def _accumulate(s, sd):
        """把单个信号日 sd 的各周期收益累加到汇总对象 s。
        胜率口径与 backtest_comprehensive 统一：排除平盘，只统计 win/(win+loss)。"""
        s["total"] += 1
        for d_ in HOLD_DAYS:
            r = sd.get(f"ret_{d_}d")
            if r is None:
                continue
            s[f"total_ret_{d_}d"] += r
            if r > 0:
                s[f"win_{d_}d"] += 1
                s[f"win_ret_{d_}d"] += r
            elif r < 0:
                s[f"loss_{d_}d"] += 1
                s[f"loss_ret_{d_}d"] += r
            else:
                s[f"draw_{d_}d"] += 1

    for key, sr in stock_results.items():
        if "signals" not in sr:
            continue
        for date, sd in sr["signals"].items():
            # 按信号类型
            for sig_name, sig_val in sd.get("signals", {}).items():
                _accumulate(summary[sig_name], sd)
            # 组合信号
            if sd.get("ge2"):
                _accumulate(summary["ge2_signals"], sd)
            if sd.get("ge3"):
                _accumulate(summary["ge3_signals"], sd)

    # 格式化
    signal_names = {
        "trend_up": "📈 上涨趋势",
        "trend_down": "📉 下跌趋势",
        "chan_buy": "🟣 缠论买点",
        "contrarian": "🔴 逆势红色",
        "breakout_5d": "🚀 5日突破",
        "volume_surge": "💥 放量上涨",
        "divergence": "⚠️ 量价背离",
        "ge2_signals": "🎯 双信号共振",
        "ge3_signals": "🎯 三信号共振",
    }
    
    result_data = {
        "calc_time": TODAY,
        "method": f"baostock 60日K线全量回测 (T+{', T+'.join(map(str, HOLD_DAYS))})",
        "gold_pool_size": len(gp_stocks),
        "stocks_analyzed": len([k for k in stock_results if "signals" in stock_results[k]]),
        "survivor_bias_warning": survivor_bias_warning,
        "pool_snapshots_used": snapshots_used,
        "summary": {},
        "stocks": stock_results,
    }
    
    print(f"\n{'='*60}")
    print(f"  回测结果汇总")
    print(f"{'='*60}")
    hdr = f"{'信号类型':<16} {'样本':>5}"
    for d_ in HOLD_DAYS:
        hdr += f" {'T+'+str(d_)+'胜率':>8} {'T+'+str(d_)+'收益':>9}"
    print(f"\n{hdr}")
    print(f"{'─'*len(hdr)}")

    for sig_key in ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence", "ge2_signals", "ge3_signals"]:
        s = summary[sig_key]
        if s["total"] == 0:
            continue
        label = signal_names.get(sig_key, sig_key)
        row = f"  {label:<14} {s['total']:>5}"
        sd = {"label": label, "total": s["total"]}
        for d_ in HOLD_DAYS:
            decided = s[f"win_{d_}d"] + s[f"loss_{d_}d"]  # 排除平盘，与 comprehensive 统一
            wr = round(s[f"win_{d_}d"] / decided * 100, 1) if decided else 0
            ar = round(s[f"total_ret_{d_}d"] / s["total"], 2) if s["total"] else 0
            row += f" {wr:>6}%  {ar:>+8}%"
            sd[f"win_{d_}d"] = s[f"win_{d_}d"]
            sd[f"loss_{d_}d"] = s[f"loss_{d_}d"]
            sd[f"draw_{d_}d"] = s[f"draw_{d_}d"]
            sd[f"win_rate_{d_}d"] = wr
            sd[f"avg_return_{d_}d"] = ar
        print(row)
        result_data["summary"][sig_key] = sd
    
    total_entries = sum(len(sr.get("signals", {})) for sr in stock_results.values())
    print(f"\n{'─'*56}")
    print(f"  总计: {len(gp_stocks)} 只股, {total_entries} 条信号")
    print(f"  输出: {OUT}")
    
    json.dump(result_data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n  结果: ✓ {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
