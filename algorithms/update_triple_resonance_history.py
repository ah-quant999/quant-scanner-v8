#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_triple_resonance_history.py — 三重共识历史快照累加器（本地累积，不部署）

每天（收盘流水线 close_p2）运行一次：
  1. 读取 data/triple_consensus.json（严格共识 stocks + 差一步 near_miss）
  2. 维护 data/triple_resonance_history.json（被 .gitignore 忽略，仅本地/云端构建读取）：
       - 每个交易日一个 key（YYYY-MM-DD）-> 当日入榜股票记录列表
       - _stock_price_history: {code: {date: close}}  对所有"曾入榜"股票持续记录**真实**收盘价（含已掉出股续接）。
         🔴 2026-09-22 价格源 = raw_data/stock_quote.json（A 批全市场快照），与 update_four_volume_history.py 文件头 §C 同口径；取不到价就不写该格。
       - _tracking_latest: {code: {enter_date, last_date, streak, total_days, status, enter_close, last_close}}
  3. 幂等：同一天重复运行只刷新当日快照，不重复累计 streak/total_days。

这是"历史追踪"页跟踪（入选以来涨跌、连续入选天数、掉出告警）与回测（入选后N日收益）的地基。
"""
import json
import os
import re

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime, date

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE, "..", "raw_data")  # 🔴 2026-08-06 改 raw_data：fundamental/top10/backtest 输入均已持久化在 raw_data（out/ 被 gitignore 云端丢）
OUTPUT = os.path.join(DATA_DIR, "triple_resonance_history.json")
CONSENSUS_FILE = os.path.join(DATA_DIR, "triple_consensus.json")
QUOTE_JSON = os.path.join(DATA_DIR, "stock_quote.json")   # A 批全市场行情快照 = 现价唯一真源
META_PREFIX = "_"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def normalize_code(c):
    return str(c or "").replace("sh_", "").replace("sz_", "").replace("hk_", "").replace("bj_", "").replace("sh.", "").replace("sz.", "").replace("hk.", "").replace("bj.", "").strip()


def load_quote_snapshot():
    """读 A 批全市场行情快照 raw_data/stock_quote.json。返回 (stocks_dict, 快照日期)。

    口径与 update_four_volume_history.py 文件头 §C 完全一致：现价唯一来源是全市场快照，
    **不是** gold_pool.history[-1]（那是"最后一次信号命中日"，非当日）。
    """
    q = load_json(QUOTE_JSON, {})
    if not isinstance(q, dict):
        return {}, ""
    ut = str(q.get("update_time") or "")
    d = ut[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ut[:10] or "") else ""
    st = q.get("stocks")
    return (st if isinstance(st, dict) else {}), d


def quote_price(quote_stocks, code):
    """在当日全市场快照里按 sz/sh/bj 前缀取真实价；取不到返回 None（绝不用 0 冒充）。"""
    c = normalize_code(code)
    if not c or not isinstance(quote_stocks, dict):
        return None
    for pre in ("sz", "sh", "bj"):
        rec = quote_stocks.get(pre + c)
        if isinstance(rec, dict):
            p = rec.get("price")
            try:
                if p is not None and float(p) > 0:
                    return float(p)
            except Exception:
                pass
    return None


def _gp_latest(gp_stock, today=None):
    """gold_pool 记录的「最近一次信号命中日」快照。

    🔴 2026-09-22 阿狸咪根治：history[-1] 是**该股最后一次被信号命中的那天**，不是当日。
       实测（69 只跟踪股 / 362 个可比格）：与真实日K不符率 69.6% —— 恒逸石化冻在 09-08 的
       18.89（当日真值 16.81，偏差 −12.4%）、另有票直接是 0。
       ⇒ **禁止**把它的 close 当当日价：只有 date == today 时才返回 close/pct_chg，
         否则这两个字段一律 None（signal_count / date 仍返回，供信号统计用）。
    """
    if not isinstance(gp_stock, dict):
        return {}
    rec = {}
    hist = gp_stock.get("history") or []
    if isinstance(hist, list) and hist:
        last = hist[-1]
        if isinstance(last, dict):
            rec = {
                "close": last.get("close"),
                "pct_chg": last.get("pct_chg"),
                "signal_count": last.get("signal_count"),
                "date": last.get("date"),
            }
    if not rec:
        latest = gp_stock.get("latest") or {}
        rec = {
            "close": latest.get("close"),
            "pct_chg": latest.get("pct_chg"),
            "signal_count": latest.get("signal_count"),
            "date": None,
        }
    if today and str(rec.get("date")) != str(today):
        rec["close"] = None
        rec["pct_chg"] = None
        rec["stale_price_dropped"] = True
    return rec

def build_gp_map(gold_pool):
    gp = gold_pool.get("stocks", {}) if isinstance(gold_pool, dict) else {}
    m = {}
    for key, s in gp.items():
        nc = normalize_code(key)
        if nc:
            m[nc] = s
    return m


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  三重共识历史累加  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    consensus = load_json(os.path.join(DATA_DIR, "triple_consensus.json"), {})
    gold_pool = load_json(os.path.join(DATA_DIR, "gold_pool.json"), {})
    gp_map = build_gp_map(gold_pool)
    quote_stocks, quote_date = load_quote_snapshot()
    print(f"  当日行情快照 stock_quote.json: {len(quote_stocks)} 只（{quote_date or '日期未知'}）")

    history = load_json(OUTPUT, {})
    # 仅保留真实日期 key（排除 _ 开头的 meta）
    # 🛡 2026-09-06 一劳永逸：只认 YYYY-MM-DD 日期键（排除 _meta 与顶层 update_time 等非日期键，
    # 顶层 update_time 是 08-29 有意补写的全站约定，保留；但不得混进日期键列表）
    date_keys = sorted([k for k in history.keys() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)])
    prev_date = None
    for dk in date_keys:
        if dk < today:
            prev_date = dk
    prev_codes = set()
    if prev_date and isinstance(history.get(prev_date), list):
        for r in history[prev_date]:
            if isinstance(r, dict) and r.get("code"):
                prev_codes.add(normalize_code(r["code"]))

    first_today = today not in date_keys

    today_records = []
    seen_codes = set()
    for grp, status in ((consensus.get("stocks", []), "strict"), (consensus.get("near_miss", []), "near")):
        for s in grp:
            code = normalize_code(s.get("code", ""))
            if not code:
                continue
            seen_codes.add(code)
            gp = gp_map.get(code, {})
            gp_latest = _gp_latest(gp, today)
            # 🔴 现价优先级：当日全市场快照 > consensus 记录价 > 当日信号快照；**绝不写 0**
            close = (quote_price(quote_stocks, code)
                     or (s.get("close") or None)
                     or gp_latest.get("close"))
            rec = {
                "code": code,
                "name": s.get("name", gp.get("name", "")),
                "market": s.get("market", gp.get("market", "")),
                "board": s.get("board", gp.get("board", "")),
                "close": close,
                "pct_chg": s.get("pct_chg", gp_latest.get("pct_chg")),
                "total_score": s.get("total_score", 0),
                "quality_grade": s.get("quality_grade", gp.get("quality_grade", "")),
                "industry": s.get("industry", gp.get("industry", "")),
                "sectors": s.get("sectors", []) or gp.get("sectors", []),
                "signal_count": s.get("signal_count", gp_latest.get("signal_count", 0)),
                "status": status,
            }
            today_records.append(rec)

    history[today] = today_records

    # ---- _stock_price_history：所有曾入榜股票今日收盘价（含掉出股续接）----
    price_hist = history.get("_stock_price_history", {})
    if not isinstance(price_hist, dict):
        price_hist = {}
    all_ever = set(price_hist.keys()) | seen_codes
    for code in all_ever:
        # 🔴 2026-09-22 阿狸咪根治：当日价只认当日全市场快照（stock_quote.json）。
        #    旧实现用 gold_pool.history[-1].close「续接」——那不是当日价（见 _gp_latest 注释），
        #    实测污染 69.6% 的格子，且会把 0 写进序列。
        close = quote_price(quote_stocks, code)
        if close is None and code in seen_codes:
            # 兜底：当日入榜票用它自己的记录价（覆盖港股等 stock_quote 不含的标的）
            for r in today_records:
                if r["code"] == code:
                    close = r["close"]
                    break
        if not close or float(close) <= 0:
            continue          # 取不到价 ⇒ 不写该格（绝不用 0 / 滞后价冒充）
        code_ph = price_hist.setdefault(code, {})
        code_ph[today] = float(close)
        code_ph[today] = close
    history["_stock_price_history"] = price_hist

    # ---- _tracking_latest ----
    tracking = history.get("_tracking_latest", {})
    if not isinstance(tracking, dict):
        tracking = {}

    for r in today_records:
        code = r["code"]
        tr = tracking.get(code, {})
        if not tr.get("enter_date") or today < tr["enter_date"]:
            tr["enter_date"] = today
            tr["enter_close"] = r["close"]
        tr["last_date"] = today
        tr["last_close"] = r["close"]
        tr["status"] = r["status"]
        if first_today:
            tr["streak"] = (tr.get("streak", 0) + 1) if code in prev_codes else 1
            tr["total_days"] = tr.get("total_days", 0) + 1
        else:
            # 同日重跑：保持 streak（仍视为连续），不重复计数
            if code not in prev_codes and tr.get("streak", 0) < 1:
                tr["streak"] = 1
        tracking[code] = tr

    # 标记掉出：曾入榜但今日不在、且未标记 dropped
    for code, tr in tracking.items():
        if code not in seen_codes and tr.get("last_date") != today and tr.get("status") != "dropped":
            tr["status"] = "dropped"

    history["_tracking_latest"] = tracking

    # 同步回写 enter_date 到 triple_consensus.json，让前端能区分"今日新入仓"与"持续持仓"
    consensus = load_json(CONSENSUS_FILE, {})
    if consensus:
        for grp_key in ("stocks", "near_miss"):
            for s in consensus.get(grp_key, []) or []:
                code = normalize_code(s.get("code", ""))
                tr = tracking.get(code, {})
                # 从未跟踪过的股票视为今日新入选
                s["enter_date"] = tr.get("enter_date", today)
        with open(CONSENSUS_FILE, "w", encoding="utf-8") as f:
            json.dump(consensus, f, ensure_ascii=False, indent=2)

    # 元数据
    meta = history.get("_meta", {})
    if not meta.get("track_start"):
        meta["track_start"] = today
    if not meta.get("created"):
        meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history["_meta"] = meta

    # 🛡 2026-08-29 一劳永逸式修复：补写顶层 update_time，与全站 raw 文件约定一致。
    # 此前只写 meta.last_update，导致 update_v8 / 跨层校验读到的顶层 update_time 停留在旧值，
    # 触发「消费层时间戳不一致」误报，阻断推送。
    history["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 今日快照 {today}: {len(today_records)} 只（严格 {sum(1 for r in today_records if r['status']=='strict')} / 差一步 {sum(1 for r in today_records if r['status']=='near')}）")
    print(f"  📈 价格历史覆盖 {len(price_hist)} 只; 跟踪池 {len(tracking)} 只")
    print(f"  🗓 起始日 {meta['track_start']} | 历史交易日 {len(date_keys)+1}")
    print(f"  输出: {OUTPUT}")


if __name__ == "__main__":
    main()
