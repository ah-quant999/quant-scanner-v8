#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_top5_track.py — finalRec Top5 90 天滚动追踪盘

输入：
  - raw_data/final_recommend.json （今日 Top5）
  - raw_data/stock_quote.json （今日收盘价）
  - raw_data/stock_stop.json （每只股的精确止损/止盈）
  - 上期 raw_data/top5_track.json （追踪池 + 历史归档，优先远端 main）

输出：
  - raw_data/top5_track.json
  - data/TOP5_TRACK.js

维护逻辑：
  - 每日 15:30 盘后跑批：将今日 Top5 入追踪池（已经存在的跳过，仅更新）
  - 每只在追踪池的股：每天追加价格 → 判定 exit（stop/target/timeout≥90天）
  - exit 的标的从 tracking 移到 history，保留为归档样本
  - history 仅保留 90 天内的样本（按 exit_date 滚动裁剪）

口径：
  - 入场价 = 上榜当日收盘价（entry_price）
  - 盈亏比口径 = (close - entry_price) / entry_price * 100
  - 胜率 = exit_type=='target' 单数 / (target+stop)
  - avg_return = 所有出场样本的算术平均 exit_pct

2026-08-13 小九落地
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
DATA = ROOT / "data"

WINDOW_DAYS = 90  # 滚动窗口


def _now_cst():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now()


def _today_str():
    return _now_cst().strftime("%Y%m%d")


def _today_str_dashed():
    return _now_cst().strftime("%Y-%m-%d")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️  读取失败 {path}: {e}")
        return None


def _load_js_var(js_path, var_name):
    """解析 data/*.js 中 `window.VAR = {...};` 包裹层（STOCK_STOP_DATA.js 用此格式）。

    用于 gen_stock_stop.py 直接输出 data/STOCK_STOP_DATA.js（不经 raw_data/）的场景。
    """
    try:
        if not js_path.exists():
            return None
        text = js_path.read_text(encoding="utf-8").strip()
        marker = f"window.{var_name} = "
        i = text.find(marker)
        if i < 0:
            return None
        payload = text[i + len(marker):].strip()
        # 末尾 ; 与换行都要去掉
        while payload and payload[-1] in "; \r\n\t":
            payload = payload[:-1]
        return json.loads(payload)
    except Exception as e:
        print(f"  ⚠️  解析 {js_path.name} 失败: {e}; 文本长度={len(text) if 'text' in dir() else 'N/A'}")
        return None


def _load_remote_or_local(name):
    """2026-08-12 铁律：先读远端 main 兜底（防本机 raw_data stale），再回退本地。"""
    try:
        import urllib.request
        url = f"https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/raw_data/{name}"
        req = urllib.request.Request(url, headers={"User-Agent": "v8-gen-top5-track"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️  远端 raw_data/{name} 读取失败 {e}，回退本地")
        return _load_json(RAW / name)


def _quote_map(stock_quote):
    """stock_quote.json → code → {close, high, low}.

    真实格式（fetch_stock_quote_v8.py）：{"meta": ..., "stocks": {code_prefixed: {price, change, pct, ...}}}

    code 形如 "sh600000" / "sz000001" / "bj920000"，清洗统一为 6 位数字不带前缀。
    返回值为双向索引：既支持带前缀也支持 6 位数字。
    """
    if not stock_quote:
        return {}
    raw = stock_quote.get("stocks")
    if not raw:
        return {}

    items = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = [(x.get("code"), x) for x in raw if x.get("code")]

    mp = {}
    for code_key, q in items:
        if not code_key:
            continue
        code_clean = str(code_key).lower()
        for prefix in ("sh", "sz", "bj", "hk"):
            if code_clean.startswith(prefix):
                code_clean = code_clean[2:]
                break
        v = {
            # 注：fetch_stock_quote_v8 输出字段是 price / prev_close / open, 不是 close
            "close": q.get("close") or q.get("price") or q.get("now"),
            "high":  q.get("high"),
            "low":   q.get("low"),
            "prev_close": q.get("prev_close"),
        }
        if v["close"] is None:
            # 当天还没收盘 → 用 prev_close + change_pct 兜底（仅用于追踪 entry/floating pct）
            pc = q.get("prev_close")
            pct_today = q.get("pct")
            if pc is not None and pct_today is not None:
                v["close"] = round(pc * (1 + pct_today / 100), 2)
                v["close_synthetic"] = True
        mp[code_clean] = v
        # 同时保留带前缀版本
        if str(code_key).lower() != code_clean:
            mp[str(code_key).lower()] = v
    return mp


def _stop_map(stock_stop):
    """stock_stop.json → code → {stop_loss, target_price, stop_loss_method, target_price_method}."""
    if not stock_stop:
        return {}
    # 格式兼容：stocks 可能是 list（每项含 code）或 dict（code→info）
    stocks = stock_stop.get("stocks")
    if isinstance(stocks, list):
        return {str(s.get("code")): s for s in stocks if s.get("code")}
    if isinstance(stocks, dict):
        return {str(k): v for k, v in stocks.items()}
    return {}


def main():
    print(f"\n[gen_top5_track] {datetime.now():%Y-%m-%d %H:%M:%S}  90 天滚动追踪")
    now = _now_cst()
    today = _today_str()
    today_dashed = _today_str_dashed()
    cutoff_90d = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")

    # ---- 1. 读今日 Top5 ----
    final_rec = _load_json(RAW / "final_recommend.json")
    today_top5 = []
    if final_rec:
        for s in (final_rec.get("stocks") or [])[:5]:
            code = s.get("code")
            if code:
                today_top5.append(s)
    print(f"  ▶ 今日 Top5 = {len(today_top5)} 只: " +
          ", ".join(f"{s.get('name')}({s.get('code')})" for s in today_top5))

    # ---- 2. 读今日行情 ----
    stock_quote = _load_json(RAW / "stock_quote.json")
    qmap = _quote_map(stock_quote)

    # ---- 3. 读止损/止盈（gen_stock_stop.py 直接产出 data/STOCK_STOP_DATA.js，不经 raw_data/）----
    stock_stop = _load_js_var(DATA / "STOCK_STOP_DATA.js", "STOCK_STOP_DATA")
    smap = _stop_map(stock_stop)

    # ---- 4. 读 baseline（远端 main 优先 → 本地）----
    baseline = _load_remote_or_local("top5_track.json") or {}
    prev_tracking_list = baseline.get("tracking") or []
    prev_history_list  = baseline.get("history")  or []

    # 索引化
    prev_tracking = {str(r.get("code")): r for r in prev_tracking_list if r.get("code")}
    print(f"  ▶ 上期追踪池 {len(prev_tracking)} 只，归档 {len(prev_history_list)} 条")

    # ---- 5. 维护：把上期追踪池股票推进一步 ----
    new_tracking = []
    new_history  = list(prev_history_list)
    top5_codes   = {str(s.get("code")) for s in today_top5}

    # 退出累计峰值
    for code, old in list(prev_tracking.items()):
        days_in_old = old.get("days_in", 0) or 0
        # 周一到周五才 day++; 简化（默认 +1，工作日/节假日判断留给后续优化）
        new_days_in = days_in_old + 1
        q = qmap.get(code) or {}
        stop_info = smap.get(code) or {}
        last_close = q.get("close") if q.get("close") is not None else old.get("last_close")
        # 🛡 2026-08-17 一劳永逸修复：写时缺失→永久 null 的污染模式
        # entry_price 在入池当日 fetch 失败（港股/小众股）为 null 后，再也补不回。
        # 现在每日重新尝试：1)优先沿用旧 entry_price  2)若旧为 null 但 qmap 里有 close→用最近价作为 entry（保守）
        # 3) 若 qmap 无 close 但旧 last_close 有值→用旧 last_close 兜底（至少能算盈亏）
        # 这样后续 fetch 补到数据时自动恢复盈亏计算
        entry_price = old.get("entry_price")
        entry_price_fallback = False
        if entry_price is None:
            if q.get("close") is not None:
                entry_price = q["close"]
                entry_price_fallback = True
            elif old.get("last_close") is not None:
                entry_price = old["last_close"]
                entry_price_fallback = True
        exit_type = None
        last_pct = None
        peak_pct = old.get("peak_pct")

        if entry_price and last_close:
            last_pct = round((last_close - entry_price) / entry_price * 100, 2)
            if peak_pct is None or last_pct > peak_pct:
                peak_pct = last_pct

        # 退出判定（止损/止盈优先，timeout 最后）
        if last_close is not None:
            sl = stop_info.get("stop_loss")
            tp = stop_info.get("target_price")
            if sl and last_close <= sl:
                exit_type = "stop"
            elif tp and last_close >= tp:
                exit_type = "target"

        if exit_type is None and new_days_in >= WINDOW_DAYS:
            exit_type = "timeout"

        if exit_type:
            # 出场归档
            new_history.append({
                "code":      code,
                "name":      old.get("name"),
                "list_date": old.get("list_date"),
                "exit_date": today,
                "list_rank": old.get("list_rank"),
                "list_sources": old.get("list_sources", []),
                "entry_price": entry_price,
                "entry_price_fallback": entry_price_fallback or old.get("entry_price_fallback", False),
                "exit_price":  last_close,
                "peak_pct":    peak_pct,
                "exit_pct":    last_pct,
                "exit_type":   exit_type,
                "days_in":     new_days_in,
                "entry_price_fallback": entry_price_fallback or old.get("entry_price_fallback", False),
            })
            print(f"    🚪 出场 {old.get('name')}({code}) {exit_type} 盈亏 {last_pct}% 当日 {new_days_in} 天")
        else:
            # 续追踪
            new_tracking.append({
                **old,
                "entry_price": entry_price,
                "last_close": last_close,
                "last_pct":   last_pct,
                "peak_pct":   peak_pct,
                "days_in":    new_days_in,
                "entry_price_fallback": entry_price_fallback or old.get("entry_price_fallback", False),
            })

    # ---- 6. 今日 Top5 入池（新上榜 / 已存在续追踪）----
    for s in today_top5:
        code = str(s.get("code"))
        name = s.get("name")
        rank = s.get("rank")
        sources = s.get("sources") or []
        q = qmap.get(code) or {}
        close = q.get("close")

        if code in prev_tracking:
            # 已经在池里 → 不重开，仅 bump appear_count 与 last_seen
            for t in new_tracking:
                if str(t.get("code")) == code:
                    t["appear_count"] = (t.get("appear_count") or 1) + 0  # 不累加，等下次 daily 合并
                    t["last_seen"] = today
                    t["last_rank"] = rank
                    t["last_sources"] = sources
                    break
            continue

        # 新入池
        new_tracking.append({
            "code":          code,
            "name":          name,
            "list_date":     today,
            "list_date_dashed": today_dashed,
            "list_rank":     rank,
            "list_sources":  sources,
            "entry_price":   close,
            "last_close":    close,
            "last_pct":      0.0 if close else None,
            "peak_pct":      0.0 if close else None,
            "days_in":       0,
            "appear_count":  1,
            "last_seen":     today,
            "last_rank":     rank,
            "last_sources":  sources,
            "first_list":    today,
        })
        print(f"    🆕 入池 {name}({code}) rank={rank} entry={close}")

    # ---- 7. 计算 stats ----
    history_90d = [h for h in new_history if (h.get("exit_date") or "") >= cutoff_90d]
    win  = sum(1 for h in history_90d if h.get("exit_type") == "target")
    loss = sum(1 for h in history_90d if h.get("exit_type") == "stop")
    timeout = sum(1 for h in history_90d if h.get("exit_type") == "timeout")
    total_decided = win + loss
    win_rate  = round(win / total_decided, 4) if total_decided else 0
    exit_pcts = [h.get("exit_pct") for h in history_90d if h.get("exit_pct") is not None]
    avg_return = round(sum(exit_pcts) / len(exit_pcts), 2) if exit_pcts else 0
    max_return = max(exit_pcts) if exit_pcts else 0
    max_loss   = min(exit_pcts) if exit_pcts else 0

    stats = {
        "window_days":   WINDOW_DAYS,
        "tracking":      len(new_tracking),
        "exit_target":   win,
        "exit_stop":     loss,
        "exit_timeout":  timeout,
        "samples":       len(history_90d),
        "win_rate":      win_rate,
        "avg_return":    avg_return,
        "max_return":    max_return,
        "max_loss":      max_loss,
        "tracking_distribution": {
            "rank1": sum(1 for t in new_tracking if t.get("last_rank") == 1),
            "rank2": sum(1 for t in new_tracking if t.get("last_rank") == 2),
            "rank3": sum(1 for t in new_tracking if t.get("last_rank") == 3),
            "rank4": sum(1 for t in new_tracking if t.get("last_rank") == 4),
            "rank5": sum(1 for t in new_tracking if t.get("last_rank") == 5),
        },
    }

    result = {
        "update_time": now.strftime("%Y-%m-%d %H:%M"),
        "window_days": WINDOW_DAYS,
        "stats":       stats,
        "tracking":    new_tracking,
        "history":     history_90d,
        "_meta": {
            "version": "v1",
            "schema_date": today_dashed,
            "note": "90 天滚动追踪 finalRec Top5；entry=上榜日收盘，exit 判定=stoploss/target/timeout",
        },
    }

    # ---- 8. 写入 raw_data + data/.js ----
    RAW.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)

    raw_path = RAW / "top5_track.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {raw_path.name}  tracking={len(new_tracking)} history={len(history_90d)}")

    js_path = DATA / "TOP5_TRACK.js"
    js = "window.TOP5_TRACK = " + json.dumps(result, ensure_ascii=False, indent=2) + ";"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"  ✅ {js_path.name}")

    print(f"  📊 stats={json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
