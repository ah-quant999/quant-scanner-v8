#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regime_filter.py — 市场状态(regime)计算与门控（从 backtest_tdx.py 提炼复用）

提供：
  - get_current_regime(force=False) -> dict|None
      返回 {"date", "regime", "series", "ok", "stale_days", "source"}
  - get_current_regime_safe() -> (info, ok, reason)  ★ 统一失败语义，调用方应优先用这个
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

取数兜底（2026-09-11 A 类修复）：baostock 优先，失败改用腾讯 proxy 指数日K 兜底。
  背景：本机 baostock 返回 10001011「黑名单用户，请与管理员联系」→ 原单源实现在此机上
  永远拿不到数据，regime 门控整链失效（generate_top10 / final_recommend /
  export_optimized_strategy 三方各出一个结论）。
失败安全：当日取数失败时回落本地缓存（_regime_cache/），结果里的 "ok" 字段显式为 False。
  ⚠️ 调用方请用 get_current_regime_safe() 读取，不要把 "regime" 直接当「当日状态」用。
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


def _fetch_index_gtimg(code, prefix, days=150):
    """非 baostock 兜底源：腾讯 proxy 指数日K（sh.000001 → sh000001 / sh.000300 → sh000300）。

    🔴 2026-09-11 A 类修复：原 _fetch_index_ohlc 只有 baostock 单一源，而本机 baostock
      直接返回 10001011「黑名单用户」→ regime 序列恒为空 → 门控整链失效。腾讯源实测
      可用且含当日收盘（09-11 上证 3888.110 / 沪深300 4510.160）。
    返回 [(date, close)]；失败返回 []。
    """
    import ssl
    import urllib.request
    sym = f"{prefix}{code}"
    url = ("https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get"
           f"?param={sym},day,,,{int(days)},qfq")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = None
    for _ctx in (ssl.create_default_context(), None):
        try:
            if _ctx is None:
                _ctx = ssl.create_default_context()
                _ctx.check_hostname = False
                _ctx.verify_mode = ssl.CERT_NONE
            raw = urllib.request.urlopen(req, timeout=25, context=_ctx).read().decode("utf-8", "replace")
            break
        except Exception as e:
            _last = e
    if raw is None:
        print(f"[regime_filter] 腾讯指数 {sym} 兜底失败: {_last}")
        return []
    try:
        d = (json.loads(raw).get("data") or {}).get(sym) or {}
        kl = d.get("qfqday") or d.get("day") or []
        rows = []
        for it in kl:
            if len(it) >= 3:
                try:
                    rows.append((str(it[0])[:10], float(it[2])))
                except Exception:
                    pass
        rows.sort(key=lambda x: x[0])
        return rows
    except Exception as e:
        print(f"[regime_filter] 腾讯指数 {sym} 解析失败: {e}")
        return []


def _fetch_index_ohlc(code, prefix, days=150):
    """指数日K，带本地缓存。取数链：当日缓存 → baostock → 腾讯兜底 → 旧缓存（不论日期）。

    返回 [(date, close)]。⚠️ 返回值新鲜度由 get_current_regime() 的 stale_days 统一判定，
    此处不做「非当日即返回空」的硬拒绝 —— 否则本机 baostock 被拉黑时会直接 0 数据。
    """
    cf = os.path.join(CACHE_DIR, f"idx_{prefix}_{code}.json")
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(cf):
        try:
            data = json.load(open(cf, encoding="utf-8"))
            if data.get("date") == today and data.get("rows"):
                return data["rows"]
        except Exception:
            pass

    rows = []
    # ① baostock
    try:
        import baostock as bs
        end = today
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        bs.login()
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}", "date,close", start_date=start, end_date=end,
            frequency="d", adjustflag="3"
        )
        while (rs.error_code == "0") & rs.next():
            r = rs.get_row_data()
            try:
                rows.append((r[0], float(r[1])))
            except Exception:
                pass
        bs.logout()
        rows.sort(key=lambda x: x[0])
    except Exception as e:
        print(f"[regime_filter] 指数 {prefix}.{code} baostock 失败: {e}")

    # ② 腾讯兜底（baostock 被拉黑 / 空数据时）
    if not rows:
        rows = _fetch_index_gtimg(code, prefix, days)
        if rows:
            print(f"[regime_filter] 指数 {prefix}.{code} 已由腾讯源兜底（{len(rows)} 行，末行 {rows[-1][0]}）")

    if rows:
        try:
            json.dump({"date": today, "rows": rows}, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass
        return rows

    # ③ 当日取数全失败 → 退回旧缓存（不论日期），新鲜度交 stale_days 判定
    if os.path.exists(cf):
        try:
            data = json.load(open(cf, encoding="utf-8"))
            if data.get("rows"):
                print(f"[regime_filter] 指数 {prefix}.{code} 当日取数失败，退回缓存（fdate={data.get('date')}）")
                return data["rows"]
        except Exception:
            pass
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


STALE_TOLERANCE_DAYS = 4   # regime 序列最新日距今超过该天数 → 视为不可用（ok=False）
                            # 4 天 = 周末(2) + 常见连休(≤2)；超过则绝不冒充「当日状态」。


def _annotate(out, source):
    """统一补 ok / stale_days / source —— 新鲜度**只在这里判**，别处不得重复实现。"""
    try:
        _latest = str(out.get("date") or "")
        _age = (datetime.now().date() - datetime.strptime(_latest, "%Y-%m-%d").date()).days
    except Exception:
        _age = 999
    out["stale_days"] = _age
    out["source"] = source
    out["ok"] = _age <= STALE_TOLERANCE_DAYS
    return out


def get_current_regime(force=False):
    """返回最新交易日 regime。带缓存（当日有效）。失败安全。

    返回值恒带 "ok"（bool）与 "stale_days"（int）——调用方**不要**只看 "regime" 字符串。
    2026-09-11 A 类修复：原实现「重算为空 → return None」与「重算抛异常 → 回落旧缓存」
    两条失败路径行为不同，且 except 分支把几天前的旧缓存当成功返回（静默假新鲜）。
    现统一：两条路径都回落旧缓存，但一律 _annotate(source="stale_cache")。
    """
    cf = os.path.join(CACHE_DIR, "regime_latest.json")
    today = datetime.now().strftime("%Y-%m-%d")
    if not force and os.path.exists(cf):
        try:
            data = json.load(open(cf, encoding="utf-8"))
            if data.get("cached_date") == today and data.get("regime"):
                return _annotate(dict(data), data.get("source") or "today_cache")
        except Exception:
            pass
    try:
        merged = _merge_market_regime()
        if merged:
            latest = sorted(merged.keys())[-1]
            out = _annotate({"cached_date": today, "date": latest,
                             "regime": merged[latest], "series": merged}, "fresh")
            json.dump(out, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
            if not out["ok"]:
                print(f"[regime_filter] ⚠️ 取数成功但数据日 {latest} 距今 {out['stale_days']} 天 → ok=False")
            return out
        print("[regime_filter] ⚠️ 指数取数为空（baostock 与腾讯源均失败）")
    except Exception as e:
        print(f"[regime_filter] regime 计算失败: {e}")

    # 统一失败回落：读旧缓存（不论日期），显式标注 ok/stale_days，绝不静默当"当日状态"
    if os.path.exists(cf):
        try:
            old = json.load(open(cf, encoding="utf-8"))
            if old.get("regime"):
                old = _annotate(dict(old), "stale_cache")
                print(f"[regime_filter] 回落旧缓存：date={old.get('date')} regime={old.get('regime')} "
                      f"ok={old['ok']} stale_days={old['stale_days']}")
                return old
        except Exception:
            pass
    return None


def get_current_regime_safe():
    """★ 唯一推荐的读取入口 —— 统一失败语义（2026-09-11 A 类修复）。

    返回 (info, ok, reason)：
      ok=True  → info 为当前有效 regime（可正常门控）
      ok=False → info 为 None 或陈旧缓存（仅供展示/追溯），**调用方必须显式保守**：
                 不得把 regime 当"可开仓"、不得用 "stabilize" 等具体状态冒充，
                 并应把 ok/reason 写进产物供前端与巡检核对。

    背景：修复前同一类取数失败引出三种结论 ——
      generate_top10 → current_regime="stabilize"（写进产物）
      final_recommend → _regime_info=None → 观望、推票数 5→2
      export_optimized_strategy → 自带一套算法 → "grind"(09-10)、open_position=true
    """
    try:
        info = get_current_regime()
    except Exception as e:
        return None, False, f"exception:{e}"
    if not info:
        return None, False, "unavailable:baostock与腾讯源均失败且无缓存"
    if not info.get("ok", True):
        return info, False, f"stale_cache:{info.get('date')}({info.get('stale_days')}天)"
    return info, True, "ok"


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
