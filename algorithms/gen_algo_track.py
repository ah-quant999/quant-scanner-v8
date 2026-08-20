#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_algo_track.py — 三算法（四量终极/板块龙头/大牛股猎手）独立追踪

输入：
  - data/FOUR_VOLUME.js          四量终极日线信号
  - data/FOUR_VOLUME_60M.js      四量终极60分钟信号
  - data/FINAL_RECOMMEND_DATA.js 推荐池（含板块龙头/大牛股猎手 source 标记）
  - raw_data/stock_quote.json    行情（取 entry_price）
  - raw_data/algo_track.json     上期追踪状态

输出：
  - raw_data/algo_track.json

  ⚠️ 2026-08-15 防覆盖铁律根因修复：本脚本**禁止**再写 data/ALGO_TRACK.js。
     data/ALGO_TRACK.js 必须由 build/deploy 流水线（update_v8.py 的 _make_js +
     _rewrite_index_html_cache_busters）从 raw_data/algo_track.json 重生，
     否则双写竞态 → 算法链写的新时间戳文件与流水线算出的 ?v 赛跑，
     造成 index.html ?v 与文件内容 sha 不符 → CDN 吐旧副本（缓存戳失配）。
     流水线才是 data/ALGO_TRACK.js 的唯一写者。

维护逻辑（与 gen_top5_track.py 同构）：
  - 每日盘后跑批：将今日各算法信号入追踪池
  - 每只追踪中的票：每天追加价格 → 判定 exit（stop/target/timeout≥90天）
  - exit 的标的移到 history，保留归档样本
  - history 滚动保留 90 天

2026-08-15 阿狸咪落地
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
DATA = ROOT / "data"
WINDOW_DAYS = 90


def _now_cst():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now()


def _today_str():
    return _now_cst().strftime("%Y%m%d")


def _today_dashed():
    return _now_cst().strftime("%Y-%m-%d")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ 读取失败 {path}: {e}")
        return None


def _load_js_var(js_path, var_name):
    """解析 data/*.js 中 window.VAR = {...};"""
    try:
        if not js_path.exists():
            return None
        text = js_path.read_text(encoding="utf-8").strip()
        # 兼容 window.VAR = {...} 和 window.VAR={...} 两种格式
        marker = f"window.{var_name}"
        i = text.find(marker)
        if i < 0:
            return None
        # 跳过 marker 到第一个 { 或 =
        after_marker = text[i + len(marker):].lstrip()
        if not after_marker.startswith("="):
            return None
        payload = after_marker[1:].lstrip()  # 跳过 =
        while payload and payload[-1] in "; \r\n\t":
            payload = payload[:-1]
        return json.loads(payload)
    except Exception as e:
        print(f"  ⚠️ 解析 {js_path.name} 失败: {e}")
        return None


def _quote_map(stock_quote):
    """stock_quote.json → code → {close, high, low}."""
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
        for prefix in ("sh", "sz", "bj"):
            if code_clean.startswith(prefix):
                code_clean = code_clean[2:]
                break
        v = {
            "close": q.get("close") or q.get("price") or q.get("now"),
            "high": q.get("high"),
            "low": q.get("low"),
            "prev_close": q.get("prev_close"),
        }
        if v["close"] is None:
            pc = q.get("prev_close")
            pct_today = q.get("pct")
            if pc is not None and pct_today is not None:
                v["close"] = round(pc * (1 + pct_today / 100), 2)
        mp[code_clean] = v
        if str(code_key).lower() != code_clean:
            mp[str(code_key).lower()] = v
    return mp


def _extract_four_volume():
    """从 FOUR_VOLUME.js + FOUR_VOLUME_60M.js 提取今日信号。"""
    signals = []
    for js_name in ["FOUR_VOLUME", "FOUR_VOLUME_60M"]:
        d = _load_js_var(DATA / f"{js_name}.js", js_name)
        if not d:
            continue
        period = d.get("period", "daily")
        for s in d.get("stocks", []):
            code = s.get("code")
            if not code:
                continue
            signals.append({
                "code": str(code),
                "name": s.get("name", ""),
                "market": s.get("market", ""),
                "algo": "four_volume",
                "period": period,
                "signal_date": s.get("signal_date") or s.get("enter_date") or _today_dashed(),
                "components": s.get("components", {}),
                "reason": s.get("reason", ""),
                "pct_chg": s.get("pct_chg"),
                "close": s.get("close"),
            })
    return signals


def _extract_big_bull():
    """从 raw_data/lhb_data.json 提取大牛股猎手信号（机构+游资双正）。
    
    数据源：龙虎榜 lhb_data.json → 与 final_recommend.py line 469-497 同逻辑
    条件：inst_net_万 > 0 且 yz_net_万 > 0（机构净买入 & 游资净买入）
    """
    ld = _load_json(RAW / "lhb_data.json")
    if not ld:
        return []
    signals = []
    for s in ld.get("stocks", []):
        inst = float(s.get("inst_net_万") or 0)
        yz = float(s.get("yz_net_万") or 0)
        if inst <= 0 or yz <= 0:
            continue
        code = s.get("code")
        if not code:
            continue
        signals.append({
            "code": str(code),
            "name": s.get("name", ""),
            "market": s.get("market", ""),
            "algo": "big_bull",
            "signal_date": ld.get("date") or _today_dashed(),
            "inst_net_wan": inst,
            "yz_net_wan": yz,
            "category": s.get("category", ""),
            "reason": f"机构{inst/10000:.1f}亿+游资{yz/10000:.1f}亿",
            "close": s.get("close"),
            "pct_chg": s.get("pct"),
        })
    return signals


def _extract_from_final_rec(source_name):
    """从 FINAL_RECOMMEND_DATA.js 提取指定 source 的股票。"""
    d = _load_js_var(DATA / "FINAL_RECOMMEND_DATA.js", "FINAL_RECOMMEND_DATA")
    if not d:
        return []
    results = []
    for s in d.get("stocks", []):
        sources = s.get("sources") or []
        if source_name not in sources:
            continue
        code = s.get("code")
        if not code:
            continue
        # algo name mapping
        algo_map = {"板块龙头": "sector_lead", "大牛股猎手": "big_bull"}
        results.append({
            "code": str(code),
            "name": s.get("name", ""),
            "market": s.get("board", ""),
            "algo": algo_map.get(source_name, source_name),
            "signal_date": _today_dashed(),
            "sources": sources,
            "source_scores": s.get("source_scores", {}),
            "close": s.get("close"),
            "pct_chg": s.get("pct_chg"),
            "reasons": s.get("reasons", []),
        })
    return results


def _advance_tracking(prev_tracking, qmap, today):
    """将上期追踪池推进一步，判定退出。"""
    new_tracking = []
    new_history = []

    for code, old in prev_tracking.items():
        days_in = old.get("days_in", 0) + 1
        q = qmap.get(code) or {}
        last_close = q.get("close") if q.get("close") is not None else old.get("last_close")
        entry_price = old.get("entry_price")
        exit_type = None
        last_pct = None
        peak_pct = old.get("peak_pct")

        if entry_price and last_close is not None:
            last_pct = round((last_close - entry_price) / entry_price * 100, 2)
            if peak_pct is None or last_pct > peak_pct:
                peak_pct = last_pct

        # 简化退出：仅 timeout（止损止盈需要 stop 数据，暂不接入）
        if days_in >= WINDOW_DAYS:
            exit_type = "timeout"

        if exit_type:
            new_history.append({
                "code": code,
                "name": old.get("name"),
                "algo": old.get("algo"),
                "list_date": old.get("list_date"),
                "exit_date": today,
                "entry_price": entry_price,
                "exit_price": last_close,
                "peak_pct": peak_pct,
                "exit_pct": last_pct,
                "exit_type": exit_type,
                "days_in": days_in,
            })
            print(f"    🚪 出场 {old.get('name')}({code}) [{old.get('algo')}] {exit_type} {last_pct}%")
        else:
            new_tracking.append({
                **old,
                "last_close": last_close,
                "last_pct": last_pct,
                "peak_pct": peak_pct,
                "days_in": days_in,
            })

    return new_tracking, new_history


def main():
    print(f"\n[gen_algo_track] {_now_cst():%Y-%m-%d %H:%M:%S}  三算法追踪")
    today = _today_str()
    today_dashed = _today_dashed()
    cutoff_90d = (_now_cst() - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")

    # ---- 1. 提取各算法今日信号 ----
    all_signals = {}
    
    # 1a. 四量终极（日线+60分钟合并）
    fv_signals = _extract_four_volume()
    all_signals["four_volume"] = fv_signals
    print(f"  ▶ 四量终极 = {len(fv_signals)} 只: " +
          ", ".join(f"{s['name']}({s['code']})" for s in fv_signals))

    # 1b. 板块龙头
    sl_signals = _extract_from_final_rec("板块龙头")
    all_signals["sector_lead"] = sl_signals
    print(f"  ▶ 板块龙头 = {len(sl_signals)} 只: " +
          ", ".join(f"{s['name']}({s['code']})" for s in sl_signals))

    # 1c. 大牛股猎手（直接从龙虎榜提取，不依赖 FINAL_RECOMMEND_DATA）
    bb_signals = _extract_big_bull()
    all_signals["big_bull"] = bb_signals
    print(f"  ▶ 大牛股猎手 = {len(bb_signals)} 只: " +
          ", ".join(f"{s['name']}({s['code']})" for s in bb_signals))

    # ---- 2. 读行情 ----
    stock_quote = _load_json(RAW / "stock_quote.json")
    qmap = _quote_map(stock_quote)

    # ---- 3. 读 baseline ----
    baseline = _load_json(RAW / "algo_track.json") or {}
    prev_by_algo = {}
    for algo_data in baseline.get("algos", []):
        algo_name = algo_data.get("algo", "")
        prev_tracking = {str(r.get("code")): r for r in algo_data.get("tracking", []) if r.get("code")}
        prev_history = algo_data.get("history", [])
        prev_by_algo[algo_name] = {
            "tracking": prev_tracking,
            "history": list(prev_history),
        }
    prev_summary = ", ".join(f"{k}={len(v['tracking'])}只" for k, v in prev_by_algo.items())
    print(f"  ▶ 上期追踪池: {prev_summary}")

    # ---- 4. 按算法分别推进 ----
    result_algos = []
    total_stats = {}

    for algo_key, signals in all_signals.items():
        prev = prev_by_algo.get(algo_key, {"tracking": {}, "history": []})
        new_tracking_list, new_history_list = _advance_tracking(
            prev["tracking"], qmap, today
        )
        # 合并旧 history
        all_history = list(prev["history"]) + new_history_list
        
        # 今日信号入池
        signal_codes = set()
        for s in signals:
            code = s["code"]
            signal_codes.add(code)
            close = s.get("close") or (qmap.get(code) or {}).get("close")

            if code in {t.get("code") for t in new_tracking_list}:
                # 已在池中，更新 last_seen
                for t in new_tracking_list:
                    if t.get("code") == code:
                        t["last_seen"] = today
                        break
                continue

            new_tracking_list.append({
                "code": code,
                "name": s.get("name", ""),
                "algo": algo_key,
                "list_date": today,
                "list_date_dashed": today_dashed,
                "entry_price": close,
                "last_close": close,
                "last_pct": 0.0 if close else None,
                "peak_pct": 0.0 if close else None,
                "days_in": 0,
                "appear_count": 1,
                "last_seen": today,
                "signal_detail": {
                    "period": s.get("period", "daily"),
                    "reason": s.get("reason", "") or ", ".join(s.get("reasons", [])),
                    "pct_chg": s.get("pct_chg"),
                },
            })
            print(f"    🆕 入池 [{algo_key}] {s.get('name')}({code}) entry={close}")

        # 计算 stats
        history_90d = [h for h in all_history if (h.get("exit_date") or "") >= cutoff_90d]
        win = sum(1 for h in history_90d if h.get("exit_type") == "target")
        loss = sum(1 for h in history_90d if h.get("exit_type") == "stop")
        timeout = sum(1 for h in history_90d if h.get("exit_type") == "timeout")
        total_decided = win + loss
        wr = round(win / total_decided, 4) if total_decided else 0
        eps = [h.get("exit_pct") for h in history_90d if h.get("exit_pct") is not None]
        avg_r = round(sum(eps) / len(eps), 2) if eps else 0

        algo_stats = {
            "tracking": len(new_tracking_list),
            "history_samples": len(history_90d),
            "win_rate": wr,
            "avg_return": avg_r,
            "exit_target": win,
            "exit_stop": loss,
            "exit_timeout": timeout,
            "today_signals": len(signals),
        }
        total_stats[algo_key] = algo_stats

        algo_display_names = {
            "four_volume": "四量终极",
            "sector_lead": "板块龙头",
            "big_bull": "大牛股猎手",
        }

        result_algos.append({
            "algo": algo_key,
            "display_name": algo_display_names.get(algo_key, algo_key),
            "stats": algo_stats,
            "tracking": new_tracking_list,
            "history": history_90d,
        })

    # ---- 5. 组装输出 ----
    result = {
        "update_time": _now_cst().strftime("%Y-%m-%d %H:%M"),
        "window_days": WINDOW_DAYS,
        "total_stats": total_stats,
        "algos": result_algos,
        "_meta": {
            "version": "v1",
            "schema_date": today_dashed,
            "note": "三算法独立追踪；entry=信号日收盘，exit=timeout≥90天（stop/target待接止损数据）",
        },
    }

    # ---- 6. 写入 ----
    # ⚠️ 只写 raw_data/algo_track.json。data/ALGO_TRACK.js 由 build/deploy 流水线重生，
    #   本脚本不得写，否则双写竞态击穿 ?v 防覆盖铁律（2026-08-15 根因修复）。
    RAW.mkdir(exist_ok=True)

    raw_path = RAW / "algo_track.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {raw_path.name}")
    print(f"  📊 总览={json.dumps(total_stats, ensure_ascii=False)}")
    print(f"  ℹ️ data/ALGO_TRACK.js 由 v8_build_deploy.yml(update_v8.py) 从本文件重生，此处不写")


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/gen_algo_track.py"):
        sys.exit(2)
    main()
