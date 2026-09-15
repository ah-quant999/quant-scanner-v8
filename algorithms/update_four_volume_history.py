#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_four_volume_history.py — 四量终极历史快照累加器（本地/云端累积，不部署）

2026-09-15 主人令：「四量终极卡下方也要像三重共识那种自己的回测和历史追踪。
四量是现查收益率最好的选股方式，必须有自己的一整套系统，特别是历史追踪。」

这是四量终极「历史追踪」页的地基：把每日四量信号 + 逐日真实收盘价沉淀成可回溯的账本。

每天（算法链 B 批，紧跟 strategy_four_volume.py 之后）运行一次：
  1. 读 data/FOUR_VOLUME.js（strategy_four_volume.py 当日产出，含 stocks[]）
  2. 读 raw_data/stock_quote.json（全市场 7000+ 只行情快照，日频，A 批产出）
  3. 维护 raw_data/four_volume_history.json：
       - 每个「信号日」一个 key（YYYY-MM-DD）→ 当日四量命中清单
       - _stock_price_history: {code: {date: close}}  ← 自建逐日真实收盘价序列
       - _tracking_latest: {code: {enter_date, enter_close, last_date, last_close,
                                    streak, total_days, status}}
       - _meta / 顶层 update_time
  4. 幂等：同一信号日重复运行只刷新当日快照，不重复累计 streak / total_days。

🔴 关键口径决策（均为四量的数据特性所决定，与三重共识的实现差异都写在这里）：
  A) **按「信号日」建 key，而不是按「跑批日」**：
     strategy_four_volume.py 取的是末根 K 线的触发票，signal_date = 真实信号日
     （实证：09-15 06:45 的产出 signal_date=2026-09-14）。按信号日建键 ⇒ 幂等天然成立。
  B) **0 命中的扫描不广播「掉出」**：
     write_four_volume_js 有「防洗空」闸门——今日 0 命中时保留磁盘旧文件、不刷 update_time。
     故「今日无记录」既可能是真无信号、也可能是扫描空转，无法区分 ⇒ 据此判「全部掉出」
     会造成假告警（踩踏）。掉出判定**只在「有命中的新信号日」进行**。
  C) **价格序列自建，不依赖 gtimg**：
     data_source_gtimg 的腾讯接口在 Windows 机上被 waf 反爬（实测 HTTP 501），
     云端 runner 可用但本地/阿狸咪机不可用 ⇒ 不能作为唯一价格源。
     改用 raw_data/stock_quote.json（全市场快照，键形如 sz300657，A 批日频产出）
     逐日累积成真实收盘价序列 —— 稳、真实、两机一致、无外部依赖。
     港股（hk_count=0，本表不含）与取不到价的票明确标 price_source="none"，绝不用 0 冒充。
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.abspath(__file__))          # .../algorithms
ROOT = os.path.dirname(WORKSPACE)                                # 仓库根
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")
OUTPUT = os.path.join(RAW_DIR, "four_volume_history.json")
SRC_JS = os.path.join(DATA_DIR, "FOUR_VOLUME.js")
QUOTE_JSON = os.path.join(RAW_DIR, "stock_quote.json")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRICE_RETENTION_DAYS = 400      # 价格序列保留天数（够长档 T+250 成熟）
TRACK_PRICE_AFTER_DROP = 150    # 掉出后仍继续记价的天数（让掉出后的 T+N 能成熟）


def cst_now():
    """runner 是 UTC，写盘/判日期必须显式 +8。"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now() + timedelta(hours=8)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def load_window_var(path, var_name):
    """读 data/*.js 的 `window.XXX = {...};` 形式（无正则、括号配对版）。

    兼容仓库的**单行压缩落盘态**与多行缩进态（见 skill v8-data-js-parsing）。
    """
    if not os.path.exists(path):
        return None
    try:
        src = open(path, "r", encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"  [warn] 读取 {path} 失败: {e}")
        return None
    try:
        idx = src.find(f"window.{var_name}")
        if idx == -1:
            return None
        eq = src.find("=", idx)
        start = src.find("{", eq) if eq != -1 else -1
        if start == -1:
            return None
        depth = 0
        in_str = esc = False
        for i in range(start, len(src)):
            ch = src[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(src[start:i + 1])
        return None
    except Exception as e:
        print(f"  [warn] 解析 {path} 失败: {e}")
        return None


def ncode(c):
    return (str(c or "").replace("sh_", "").replace("sz_", "").replace("hk_", "")
            .replace("bj_", "").replace("sh.", "").replace("sz.", "")
            .replace("hk.", "").replace("bj.", "").strip())


def quote_price(quote_stocks, code):
    """在 stock_quote.json 的 stocks 里按 sz/sh/bj 前缀找真实价。

    键形如 sz300657 / sh600410 / bj920000（无分隔符），返回 (price, 命中的键)。
    """
    c = ncode(code)
    if not c or not isinstance(quote_stocks, dict):
        return None, None
    for pre in ("sz", "sh", "bj"):
        k = pre + c
        rec = quote_stocks.get(k)
        if isinstance(rec, dict):
            p = rec.get("price")
            try:
                if p is not None and float(p) > 0:
                    return float(p), k
            except Exception:
                pass
    return None, None


def main():
    now = cst_now()
    today = now.strftime("%Y-%m-%d")
    print(f"  四量终极 历史累加  —  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    fv = load_window_var(SRC_JS, "FOUR_VOLUME") or {}
    stocks = fv.get("stocks") or []
    if not isinstance(stocks, list):
        stocks = []
    ut = str(fv.get("update_time") or "")
    ut_date = ut[:10] if DATE_RE.match(ut[:10] or "") else ""

    quote = load_json(QUOTE_JSON, {})
    quote_stocks = quote.get("stocks", {}) if isinstance(quote, dict) else {}
    q_ut = str((quote.get("meta") or {}).get("update_time") or quote.get("update_time") or "")
    price_date = q_ut[:10] if DATE_RE.match(q_ut[:10] or "") else ""
    if not price_date:
        price_date = today
    print(f"  行情快照 stock_quote: update_time={q_ut or '(空)'} → 价格日 {price_date}"
          f"（{len(quote_stocks)} 只）")

    # ---- 判定真实信号日（见文件头 §A）----
    sig_dates = sorted({str(s.get("signal_date") or "") for s in stocks
                        if DATE_RE.match(str(s.get("signal_date") or ""))})
    latest_sig = sig_dates[-1] if sig_dates else ""
    if latest_sig:
        try:
            _d = datetime.strptime(latest_sig, "%Y-%m-%d").date()
            if (_d - now.date()).days > 1 or (now.date() - _d).days > 10:
                print(f"  [warn] 信号日 {latest_sig} 距今日 {today} 过远，改用跑批日建键")
                latest_sig = ""
        except Exception:
            latest_sig = ""

    key = latest_sig or today
    ran_today = (ut_date == today)
    print(f"  源文件 update_time={ut or '(空)'} 信号日={latest_sig or '(无)'} → 建键 {key}")
    print(f"  今日已刷新={ran_today}  命中 {len(stocks)} 只")

    history = load_json(OUTPUT, {})
    if not isinstance(history, dict):
        history = {}
    date_keys = sorted([k for k in history.keys() if DATE_RE.match(k)])
    first_time = key not in date_keys

    prev_codes = set()
    _prev = [k for k in date_keys if k < key]
    if _prev and isinstance(history.get(_prev[-1]), list):
        for r in history[_prev[-1]]:
            if isinstance(r, dict) and r.get("code"):
                prev_codes.add(ncode(r["code"]))

    # ---- 1) 当日（信号日）快照 ----
    records = []
    seen = set()
    for s in stocks:
        code = ncode(s.get("code", ""))
        if not code or code in seen:
            continue
        seen.add(code)
        qp, _qk = quote_price(quote_stocks, code)
        close = s.get("close")
        try:
            close = float(close) if close is not None else None
        except Exception:
            close = None
        if close is None or close <= 0:
            close = qp          # 快照价优先于缺省 0
        records.append({
            "code": code,
            "name": s.get("name", ""),
            "market": s.get("market", ""),
            "board": s.get("board_label") or s.get("board") or "",
            "close": close,
            "quote_close": qp,       # 来自全市场快照的真实收盘（可能为 None）
            "pct_chg": s.get("pct_chg"),
            "turnover_rate": s.get("turnover_rate"),
            "fund_type": s.get("fund_type", ""),
            "qd": bool(s.get("qd")),
            "yzc": bool(s.get("yzc")),
            "jg": bool(s.get("jg")),
            "xc": bool(s.get("xc")),
            "four": bool(s.get("four")),
            "components": s.get("components") or {},
            "reason": s.get("reason", ""),
            "signal_date": s.get("signal_date") or key,
        })
    history[key] = records

    # ---- 2) _tracking_latest ----
    tracking = history.get("_tracking_latest", {})
    if not isinstance(tracking, dict):
        tracking = {}

    for r in records:
        code = r["code"]
        tr = tracking.get(code) or {}
        if not tr.get("enter_date") or key < tr["enter_date"]:
            tr["enter_date"] = key
            tr["enter_close"] = r.get("quote_close") or r.get("close")
        tr["last_date"] = key
        tr["last_close"] = r.get("quote_close") or r.get("close")
        tr["status"] = "active"
        tr["name"] = r.get("name", tr.get("name", ""))
        tr["market"] = r.get("market", tr.get("market", ""))
        if first_time:
            tr["streak"] = (tr.get("streak", 0) + 1) if code in prev_codes else 1
            tr["total_days"] = tr.get("total_days", 0) + 1
        else:
            if code not in prev_codes and tr.get("streak", 0) < 1:
                tr["streak"] = 1
            tr["total_days"] = max(tr.get("total_days", 1), 1)
        tracking[code] = tr

    # 掉出判定：仅在有命中的新信号日进行（见文件头 §B）
    drop_marks = 0
    if first_time and records:
        for code, tr in tracking.items():
            if code not in seen and tr.get("status") != "dropped":
                tr["status"] = "dropped"
                tr["dropped_at"] = key
                drop_marks += 1
    history["_tracking_latest"] = tracking

    # ---- 3) _stock_price_history：自建逐日真实收盘价序列（见文件头 §C）----
    price_hist = history.get("_stock_price_history", {})
    if not isinstance(price_hist, dict):
        price_hist = {}
    # 记录范围：所有曾入榜的票（含掉出后 TRACK_PRICE_AFTER_DROP 天内）→ 让 T+N 能成熟
    want = set(tracking.keys()) | seen
    for code in sorted(want):
        tr = tracking.get(code) or {}
        ld = tr.get("last_date") or ""
        if tr.get("status") == "dropped" and DATE_RE.match(ld):
            try:
                gap = (datetime.strptime(price_date, "%Y-%m-%d").date()
                       - datetime.strptime(ld, "%Y-%m-%d").date()).days
                if gap > TRACK_PRICE_AFTER_DROP:
                    continue      # 掉出太久 → 停止记价（控制体积）
            except Exception:
                pass
        p, _k = quote_price(quote_stocks, code)
        if p is None:
            # 兜底：当日入榜票用它自己的快照价（覆盖港股等 stock_quote 不含的标的）
            if code in seen:
                for r in records:
                    if r["code"] == code:
                        p = r.get("close")
                        break
        if p is None:
            continue
        price_hist.setdefault(code, {})[price_date] = p
    # 瘦身：单只保留最近 PRICE_RETENTION_DAYS 个价格点
    for code in list(price_hist.keys()):
        series = price_hist[code]
        if isinstance(series, dict) and len(series) > PRICE_RETENTION_DAYS:
            keep = sorted(series.keys())[-PRICE_RETENTION_DAYS:]
            price_hist[code] = {k: series[k] for k in keep}
    history["_stock_price_history"] = price_hist

    # ---- 4) 元数据 + 顶层时戳 ----
    meta = history.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}
    if not meta.get("track_start"):
        meta["track_start"] = key
    if not meta.get("created"):
        meta["created"] = now.strftime("%Y-%m-%d %H:%M:%S")
    meta["last_update"] = now.strftime("%Y-%m-%d %H:%M:%S")
    meta["last_signal_date"] = key
    meta["last_hit_count"] = len(records)
    meta["last_price_date"] = price_date
    history["_meta"] = meta
    history["update_time"] = now.strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    active = sum(1 for t in tracking.values() if t.get("status") == "active")
    dropped = sum(1 for t in tracking.values() if t.get("status") == "dropped")
    pt = sum(len(v) for v in price_hist.values() if isinstance(v, dict))
    print(f"  ✅ 信号日 {key}: 命中 {len(records)} 只"
          f"（新批次={first_time}）→ 本轮标记掉出 {drop_marks} 只")
    print(f"  📈 跟踪池 {len(tracking)} 只（active {active} / dropped {dropped}）"
          f" | 价格序列 {len(price_hist)} 只 / {pt} 个价格点")
    print(f"  输出: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
