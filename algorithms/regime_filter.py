#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regime_filter.py — 市场状态(regime)计算与门控（从 backtest_tdx.py 提炼复用）

提供：
  - get_current_regime(force=False) -> dict|None
      返回 {"date", "regime": "grind"/"panic"/"stabilize"/"rebound_diverge", "series":{date:regime}}
  - is_open_regime(regime) -> bool   （grind/panic = 可开仓；stabilize/rebound = 应观望）
  - passes_optimized_filter(sigs, regime) -> bool

regime 口径（与 backtest_tdx.py / analyze_regime_filter.py 完全一致）：
  基于上证+沪深300 的 20日收益 + 20日波动率趋势（取两者中更悲观者）：
    ret_20d>=0 & vol_trend<0  -> stabilize       （企稳，空仓）
    ret_20d<0  & vol_trend<0  -> grind           （阴跌，可开仓）
    ret_20d>=0 & vol_trend>=0 -> rebound_diverge （反弹背离，空仓）
    ret_20d<0  & vol_trend>=0 -> panic           （恐慌，可开仓）

回测验证（backtest_tdx.json optimized_summary）：
  仅在 grind/panic 开仓的优化策略，5天胜率 58.7%/收益4.92%，10天 54.6%/收益5.32%，
  显著优于无过滤版本。故实盘选股应复用同一 regime 门控。

失败安全：联网抓指数失败时回落本地缓存（_regime_cache/），再失败返回 None，
调用方据此跳过门控（不影响原有选股逻辑）。
"""
import os
import math
import json
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "_regime_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 优化策略允许开仓的 regime -> 子信号（与 backtest_tdx.OPTIMIZED 一致）
OPTIMIZED_REGIME_SIGNALS = {
    "stabilize": [],
    "rebound_diverge": [],
    "grind": ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence"],
    "panic": ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence"],
}


def _fetch_index_ohlc(code, prefix, days=150):
    """从 baostock 拉指数日K，带本地缓存（当日有效）。返回 [(date, close)]。"""
    cf = os.path.join(CACHE_DIR, f"idx_{prefix}_{code}.json")
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(cf):
        try:
            data = json.load(open(cf, encoding="utf-8"))
            if data.get("date") == today and data.get("rows"):
                return data["rows"]
        except Exception:
            pass
    try:
        import baostock as bs
        end = today
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        bs.login()
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}", "date,close", start_date=start, end_date=end,
            frequency="d", adjustflag="3"
        )
        rows = []
        while (rs.error_code == "0") & rs.next():
            r = rs.get_row_data()
            try:
                rows.append((r[0], float(r[1])))
            except Exception:
                pass
        bs.logout()
        rows.sort(key=lambda x: x[0])
        if rows:
            json.dump({"date": today, "rows": rows}, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        return rows
    except Exception as e:
        print(f"[regime_filter] 指数 {prefix}.{code} 抓取失败: {e}")
        return []


def _compute_regime_series(rows):
    """从指数 close 序列计算每日 regime。"""
    closes = [c for _, c in rows]
    n = len(closes)
    if n < 22:
        return {}
    log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]

    def _std(xs):
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    daily_vol = []
    for i in range(19, len(log_rets)):
        w = log_rets[i - 19:i + 1]
        daily_vol.append(_std(w) * math.sqrt(252) * 100.0)

    regime_by_date = {}
    for i in range(21, n):
        vol_idx = i - 21
        if vol_idx < 5:
            continue
        vol_20d = daily_vol[vol_idx]
        vol_20d_ago5 = daily_vol[vol_idx - 5]
        vol_trend_pct = ((vol_20d - vol_20d_ago5) / vol_20d_ago5 * 100.0) if vol_20d_ago5 else 0.0
        ret_20d = (closes[i] / closes[i - 20] - 1.0) * 100.0
        if ret_20d >= 0 and vol_trend_pct < 0:
            regime = "stabilize"
        elif ret_20d < 0 and vol_trend_pct < 0:
            regime = "grind"
        elif ret_20d >= 0 and vol_trend_pct >= 0:
            regime = "rebound_diverge"
        else:
            regime = "panic"
        regime_by_date[rows[i][0]] = regime
    return regime_by_date


def _merge_market_regime():
    """合并上证与沪深300 regime，取更悲观者。"""
    priority = {"panic": 3, "grind": 2, "rebound_diverge": 1, "stabilize": 0}
    sh = _compute_regime_series(_fetch_index_ohlc("000001", "sh"))
    hs = _compute_regime_series(_fetch_index_ohlc("000300", "sh"))
    all_dates = set(sh.keys()) | set(hs.keys())
    merged = {}
    for d in all_dates:
        r1 = sh.get(d, "stabilize")
        r2 = hs.get(d, "stabilize")
        merged[d] = r1 if priority.get(r1, 0) >= priority.get(r2, 0) else r2
    return merged


def get_current_regime(force=False):
    """返回最新交易日 regime。带缓存（当日有效）。失败安全。"""
    cf = os.path.join(CACHE_DIR, "regime_latest.json")
    today = datetime.now().strftime("%Y-%m-%d")
    if not force and os.path.exists(cf):
        try:
            data = json.load(open(cf, encoding="utf-8"))
            if data.get("cached_date") == today and data.get("regime"):
                return data
        except Exception:
            pass
    try:
        merged = _merge_market_regime()
        if not merged:
            return None
        latest = sorted(merged.keys())[-1]
        out = {"cached_date": today, "date": latest, "regime": merged[latest], "series": merged}
        json.dump(out, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        return out
    except Exception as e:
        print(f"[regime_filter] regime 计算失败: {e}")
        if os.path.exists(cf):
            try:
                return json.load(open(cf, encoding="utf-8"))
            except Exception:
                pass
        return None


def is_open_regime(regime):
    """grind/panic = 可开仓；stabilize/rebound_diverge = 应观望/空仓。"""
    return regime in ("grind", "panic")


def passes_optimized_filter(sigs, regime):
    """判断一组信号是否满足优化策略入池条件：ge3 + 市场regime-信号匹配。"""
    if not sigs.get("ge3_signals", False):
        return False
    if regime not in OPTIMIZED_REGIME_SIGNALS:
        return False
    allowed = OPTIMIZED_REGIME_SIGNALS[regime]
    active = {k for k, v in sigs.items() if v and not k.startswith("ge")}
    return bool(active & set(allowed))


if __name__ == "__main__":
    r = get_current_regime(force=True)
    if r:
        print(f"最新交易日 {r['date']} 市场状态: {r['regime']}  (grind/panic=可开仓)")
    else:
        print("regime 计算失败")
