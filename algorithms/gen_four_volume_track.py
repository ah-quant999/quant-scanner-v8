#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_four_volume_track.py — 四量终极「历史追踪 + 前向回测」分析器

2026-09-15 主人令：「四量终极卡下方也要像三重共识那种自己的回测和历史追踪。
四量是现查收益率最好的选股方式，必须有自己的一整套系统，特别是历史追踪。」

读取：
  - raw_data/four_volume_history.json      （update_four_volume_history.py 的累积账本，
                                            含每日快照 + _tracking_latest + _stock_price_history）
  - algorithms/stock_industry_concepts.json（行业/概念映射，与三重共识同源）
  - raw_data/top10_daily.json              （TOP10≥70，用于全站精选重叠度）

写出：raw_data/four_volume_track.json（前端「四量终极」tab 的跟踪/回测子卡消费）

覆盖 7 项能力：
  1) 持仓盈亏跟踪（入选以来涨跌 / 持有信号日数 / 连续信号日数）
  2) 状态迁移告警（新入选 / 掉出 / 连续入选 / 大幅回撤 / 信号兑现）
  3) 前向累积回测（自建逐日真实收盘价序列 T+1/3/5/10/20/30/45/60）
  4) 板块聚类（行业集中度 → 相关性风险）
  5) 全站精选重叠度
  6) 四量四灯状态（QD / 游资点火 / 机构托底 / 当天金叉 / 四路翻多）
  7) 价格来源透明化（quote / ledger / none 逐只标注，取不到就留空）

🔴 与三重共识的关键差异：**四量的票不在金股池**。
   三重的跟踪价取自 raw_data/gold_pool.json（三重的票本就是金股池子集）；
   四量扫描「各板成交额前 80」的独立宇宙，绝大多数不在金股池 ⇒ 价格改由
   update_four_volume_history.py 从全市场快照 stock_quote.json 逐日自建序列
   （不依赖 gtimg：该接口在 Windows 机被腾讯 waf 反爬，实测 HTTP 501）。

原则：不编造数据；取不到价就标 price_source="none"、pnl 留 None，绝不用 0 冒充。
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.abspath(__file__))   # .../algorithms
ROOT = os.path.dirname(WORKSPACE)
ALGO_DIR = WORKSPACE
RAW_DIR = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW_DIR, "four_volume_track.json")
HISTORY_FILE = os.path.join(RAW_DIR, "four_volume_history.json")
META_FILE = os.path.join(ALGO_DIR, "stock_industry_concepts.json")
QUOTE_JSON = os.path.join(RAW_DIR, "stock_quote.json")

# 前向累积的可成熟档位。长档（75/90/180/250）需数百交易日才成熟，由
# strategy_four_volume.py 的回测分层（data/FOUR_VOLUME_BACKTEST.js，近5年1457信号）
# 负责，前端「回测 N 日胜率」卡直接读那份 —— 二者互补、口径同源、不重复。
HOLD_HORIZONS = (1, 3, 5, 10, 20, 30, 45, 60)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def cst_now():
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


def ncode(c):
    return (str(c or "").replace("sh_", "").replace("sz_", "").replace("hk_", "")
            .replace("bj_", "").replace("sh.", "").replace("sz.", "")
            .replace("hk.", "").replace("bj.", "").strip())


def r2(x):
    try:
        return round(float(x), 2)
    except Exception:
        return None


def board_from_code(code):
    c = re.sub(r"[^0-9]", "", str(code))
    if not c:
        return ""
    if c.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return ""


def main():
    now = cst_now()
    today = now.strftime("%Y-%m-%d")
    print(f"  四量终极 跟踪/前向回测分析  —  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    history = load_json(HISTORY_FILE, {})
    if not isinstance(history, dict) or not history:
        print(f"  ❌ 账本缺失或为空: {HISTORY_FILE}（先跑 update_four_volume_history.py）")
        _write_empty(now, today)
        return 0
    meta_map = load_json(META_FILE, {})
    if not isinstance(meta_map, dict):
        meta_map = {}
    top10 = load_json(os.path.join(RAW_DIR, "top10_daily.json"), {})
    quote = load_json(QUOTE_JSON, {})
    quote_stocks = quote.get("stocks", {}) if isinstance(quote, dict) else {}

    price_hist = history.get("_stock_price_history", {})
    if not isinstance(price_hist, dict):
        price_hist = {}
    tracking = history.get("_tracking_latest", {})
    if not isinstance(tracking, dict):
        tracking = {}
    meta = history.get("_meta", {}) or {}
    date_keys = sorted([k for k in history.keys() if DATE_RE.match(k)])
    data_date = date_keys[-1] if date_keys else today
    today_records = history.get(data_date) if isinstance(history.get(data_date), list) else []
    today_codes = {ncode(r.get("code", "")) for r in today_records if isinstance(r, dict)}

    # ---- 全市场交易日轴（所有价格日的并集；作为 T+N 的真实交易日基准）----
    all_dates = sorted({d for s in price_hist.values() if isinstance(s, dict) for d in s.keys()
                        if DATE_RE.match(d)})
    date_idx = {d: i for i, d in enumerate(all_dates)}
    print(f"  账本信号日 {len(date_keys)} 个 | 价格序列 {len(price_hist)} 只"
          f" | 交易日轴 {len(all_dates)} 天"
          + (f"（{all_dates[0]} ~ {all_dates[-1]}）" if all_dates else ""))

    # ---- 最新信号日的记录索引（补 industry/concepts/四灯）----
    rec_by_code = {}
    for r in today_records:
        if not isinstance(r, dict):
            continue
        code = ncode(r.get("code", ""))
        if not code:
            continue
        r = dict(r)
        m = meta_map.get(code) or {}
        if not r.get("industry"):
            r["industry"] = m.get("industry") or ""
        if not r.get("board"):
            r["board"] = m.get("board") or board_from_code(code) or ""
        if not r.get("sectors"):
            r["sectors"] = list(m.get("concepts") or [])[:6]
        rec_by_code[code] = r

    # ---- 跟踪范围：active 优先，再按最近活跃日倒序（确定性排序，不用 hash）----
    _act = [kv for kv in tracking.items() if kv[1].get("status") == "active"]
    _oth = [kv for kv in tracking.items() if kv[1].get("status") != "active"]
    _act.sort(key=lambda kv: kv[1].get("last_date") or "", reverse=True)
    _oth.sort(key=lambda kv: kv[1].get("last_date") or "", reverse=True)
    items = _act + _oth
    print(f"  跟踪池 {len(tracking)} 只（active {len(_act)} / dropped {len(_oth)}）")

    tracked = []
    per_stock = []
    agg = {n: {"count": 0, "win": 0, "sum": 0.0} for n in HOLD_HORIZONS}
    missing = []

    for code, tr in items:
        rec = rec_by_code.get(code) or {}
        # 🛡 行业/板块回退到全市场映射表：掉出票与「不在最新信号日」的票
        #   在 today_records 里查不到 → 若不回退，板块聚类会被「未知」占据（假数据）
        _m = meta_map.get(code) or {}
        market = rec.get("market") or tr.get("market") or ""
        name = rec.get("name") or tr.get("name") or ""
        industry = rec.get("industry") or _m.get("industry") or ""
        board = rec.get("board") or _m.get("board") or board_from_code(code) or ""
        sectors = rec.get("sectors") or list(_m.get("concepts") or [])[:6]
        enter_date = tr.get("enter_date") or ""
        series = price_hist.get(code) or {}
        sdates = sorted(series.keys()) if isinstance(series, dict) else []

        # 价格来源判定（透明化，绝不用 0 冒充）
        in_quote = any((pre + code) in quote_stocks for pre in ("sz", "sh", "bj"))
        if in_quote and sdates:
            price_source = "quote"
        elif sdates:
            price_source = "ledger"
        else:
            price_source = "none"

        current_close = series.get(sdates[-1]) if sdates else tr.get("last_close")
        first_close = tr.get("enter_close")
        if first_close is None and sdates and enter_date:
            after = [d for d in sdates if d >= enter_date]
            if after:
                first_close = series.get(after[0])

        pnl = None
        try:
            if first_close and current_close and float(first_close) > 0:
                pnl = r2((float(current_close) / float(first_close) - 1) * 100)
        except Exception:
            pnl = None
        if pnl is None:
            missing.append(code)

        # ---- 前向 T+N（真实交易日轴；基准=入选日收盘，非未来函数）----
        offs = {}
        best_n = best_pct = None
        if sdates and enter_date and all_dates:
            after = [d for d in sdates if d >= enter_date]
            if after:
                base_date = after[0]                      # 入选日（或其后首个有价日）
                base_close = series.get(base_date)
                bi = date_idx.get(base_date)
                if base_close and bi is not None:
                    for n in HOLD_HORIZONS:
                        ti = bi + n
                        if ti < len(all_dates):
                            td = all_dates[ti]
                            px = series.get(td)           # 停牌则无价 → 跳过该档
                            if px:
                                ret = (px / base_close - 1) * 100
                                offs[f"{n}d"] = r2(ret)
                                agg[n]["count"] += 1
                                agg[n]["sum"] += ret
                                if ret > 0:
                                    agg[n]["win"] += 1
        for k_, v_ in offs.items():
            if v_ is None:
                continue
            if best_pct is None or v_ > best_pct:
                best_pct, best_n = v_, int(k_.rstrip("d"))
        if offs:
            per_stock.append({"code": code, "name": name, "enter_date": enter_date,
                              "offsets": offs,
                              "best_n": best_n,
                              "best_pct": r2(best_pct) if best_pct is not None else None})

        tracked.append({
            "code": code,
            "name": name,
            "market": market,
            "board": board,
            "industry": industry,
            "sectors": sectors,
            "status": tr.get("status") or "",
            "enter_date": enter_date,
            "last_date": tr.get("last_date") or "",
            "dropped_at": tr.get("dropped_at") or "",
            "hold_days": tr.get("total_days", 1),
            "consecutive_days": tr.get("streak", 1),
            "first_close": r2(first_close) if first_close is not None else None,
            "current_close": r2(current_close) if current_close is not None else None,
            "pnl_pct": pnl,
            "price_source": price_source,
            "offsets": offs,
            "best_n": best_n,
            "best_pct": r2(best_pct) if best_pct is not None else None,
            "qd": rec.get("qd"),
            "yzc": rec.get("yzc"),
            "jg": rec.get("jg"),
            "xc": rec.get("xc"),
            "four": rec.get("four"),
            "components": rec.get("components") or {},
            "reason": rec.get("reason") or "",
            "is_new": bool(enter_date and enter_date == data_date),
        })

    tracked.sort(key=lambda x: -(x["pnl_pct"] if x["pnl_pct"] is not None else -999))

    # ---- 状态迁移告警 ----
    alerts = []
    for t in tracked:
        nm, cd = t["name"] or t["code"], t["code"]
        if t["is_new"]:
            alerts.append({"level": "info", "code": cd, "name": nm,
                           "text": f"{nm}({cd}) 于 {t['enter_date']} 新入选四量信号"})
        if t["status"] == "dropped" and t["last_date"]:
            alerts.append({"level": "warn", "code": cd, "name": nm,
                           "text": f"{nm}({cd}) 于 {t['last_date']} 跌出四量信号"
                                   f"（曾连续 {t['consecutive_days']} 个信号日）"})
        elif t["status"] == "active" and (t["consecutive_days"] or 0) >= 3:
            alerts.append({"level": "good", "code": cd, "name": nm,
                           "text": f"{nm}({cd}) 连续 {t['consecutive_days']} 个信号日稳居四量信号（高质量）"})
        if t["status"] != "dropped" and t["pnl_pct"] is not None:
            if t["pnl_pct"] <= -8:
                alerts.append({"level": "warn", "code": cd, "name": nm,
                               "text": f"{nm}({cd}) 入选以来回撤 {t['pnl_pct']:.2f}%"
                                       f"（{t['enter_date']} 起）"})
            elif t["pnl_pct"] >= 15:
                alerts.append({"level": "good", "code": cd, "name": nm,
                               "text": f"{nm}({cd}) 入选以来 +{t['pnl_pct']:.2f}%（信号兑现）"})

    # ---- 板块聚类 ----
    # 🔴 口径：只统计**当前仍在池**（status=active）的票 —— 掉出票已不在四量信号里，
    #   把它们算进「行业集中度」会虚增相关性风险（是伪风险）。全掉出时退化为全量。
    cl = [t for t in tracked if t.get("status") == "active"] or tracked
    ind_cnt, sec_cnt = {}, {}
    for t in cl:
        ind = t.get("industry") or "未知"
        ind_cnt[ind] = ind_cnt.get(ind, 0) + 1
        for s in (t.get("sectors") or []):
            sec_cnt[s] = sec_cnt.get(s, 0) + 1
    by_industry = sorted([{"industry": k, "count": v,
                           "names": [x["name"] for x in cl if (x.get("industry") or "未知") == k]}
                          for k, v in ind_cnt.items()], key=lambda x: -x["count"])
    by_sector = sorted([{"sector": k, "count": v} for k, v in sec_cnt.items()], key=lambda x: -x["count"])
    sector_cluster = {
        "by_industry": by_industry,
        "by_sector": by_sector,
        "scope": "当前在池（active）",
        "pool_size": len(cl),
        "concentration": r2(by_industry[0]["count"] / len(cl) * 100) if (cl and by_industry) else 0,
    }

    # ---- 全站精选重叠度 ----
    top10_ge70 = set()
    for s in (top10.get("top10", []) if isinstance(top10, dict) else []):
        if (s.get("total_score") or 0) >= 70:
            top10_ge70.add(ncode(s.get("code")))
    ov = (top10_ge70 & today_codes) if today_codes else set()
    overlap = {
        "total_tracked": len(today_codes),
        "top10_ge70": {"count": len(top10_ge70), "overlap": len(ov),
                       "names": [r.get("name", "") for r in today_records
                                 if ncode(r.get("code")) in ov]},
    }

    # ---- 前向累积回测汇总 ----
    self_summary = {}
    for n in HOLD_HORIZONS:
        a = agg[n]
        self_summary[f"{n}d"] = ({"count": a["count"],
                                  "win_rate": r2(a["win"] / a["count"] * 100),
                                  "avg_return": r2(a["sum"] / a["count"])}
                                 if a["count"] > 0 else
                                 {"count": 0, "win_rate": None, "avg_return": None})
    matured = [f"{n}d" for n in HOLD_HORIZONS if agg[n]["count"] > 0]
    self_backtest = {
        "note": ("四量信号自上线起逐日累积真实收盘价前向样本（基准=入选日收盘，"
                 "T+N 按真实交易日推进，不含未来函数）。样本随持有天数成熟而增加；"
                 "长档（75/90/180/250）见上方「回测 N 日胜率」的信号层回测。"),
        "track_start": meta.get("track_start", data_date),
        "history_days": len(date_keys),
        "price_days": len(all_dates),
        "horizons": [f"{n}d" for n in HOLD_HORIZONS],
        "matured": matured,
        "summary": self_summary,
        "per_stock": per_stock,
    }

    result = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": data_date,
        "track_start": meta.get("track_start", data_date),
        "history_days": len(date_keys),
        "price_days": len(all_dates),
        "signal_count": len(today_records),
        "tracked_total": len(tracking),
        "active_count": sum(1 for t in tracked if t.get("status") == "active"),
        "dropped_count": sum(1 for t in tracked if t.get("status") == "dropped"),
        "priced_count": sum(1 for t in tracked if t.get("pnl_pct") is not None),
        "tracked": tracked,
        "alerts": alerts,
        "sector_cluster": sector_cluster,
        "overlap": overlap,
        "self_backtest": self_backtest,
        "price_missing": missing,
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    p5 = self_summary.get("5d", {})
    print(f"  ✅ 跟踪 {len(tracked)} 只（active {result['active_count']} / dropped {result['dropped_count']}）"
          f" | 有价 {result['priced_count']} 只")
    print(f"  📊 告警 {len(alerts)} 条; 板块 {len(by_industry)} 类; 重叠 TOP10≥70 {overlap['top10_ge70']['overlap']} 只")
    print(f"  🔁 前向累积：信号日 {len(date_keys)} 个 / 交易日轴 {len(all_dates)} 天"
          f" | 成熟档位 {matured or '暂无'}"
          + (f" | T+5 样本 {p5.get('count')} 胜率 {p5.get('win_rate')}% 均收 {p5.get('avg_return')}%"
             if p5.get("count") else ""))
    if missing:
        print(f"  ⚠️ 无价 {len(missing)} 只（留空不用 0 冒充）: {', '.join(missing[:10])}")
    print(f"  输出: {OUT}")
    return 0


def _write_empty(now, today):
    """账本缺失时的兜底空壳：保证前端卡与健康巡检拿到新鲜时戳，而非僵尸数据。"""
    result = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": today, "track_start": today,
        "history_days": 0, "price_days": 0, "signal_count": 0,
        "tracked_total": 0, "active_count": 0, "dropped_count": 0, "priced_count": 0,
        "tracked": [],
        "alerts": [{"level": "warn", "code": "", "name": "",
                    "text": "四量历史账本尚未建立（首次运行后自动累积）"}],
        "sector_cluster": {"by_industry": [], "by_sector": [], "concentration": 0},
        "overlap": {"total_tracked": 0, "top10_ge70": {"count": 0, "overlap": 0, "names": []}},
        "self_backtest": {"note": "样本积累中", "track_start": today, "history_days": 0,
                          "price_days": 0, "horizons": [f"{n}d" for n in HOLD_HORIZONS],
                          "matured": [], "summary": {}, "per_stock": []},
        "price_missing": [],
    }
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ⚠️ 已写出空壳: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
