#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 2026-11-19 主人令：股票型ETF申赎净流入 · 观测卡（暂未上架>观测类）—— 主备双源 fetcher
需求原话：「这个kimi的网址随时会断，你可以先用它做成张观测卡，但还是要有自己的数据源备份，
          万一断了就可以自己的顶上」

主源: Kimi 页 https://5jiniyutijiye.ok.kimi.link/data.js
      window.ETF_FLOW_DATA = {title, unit:"亿元", source:"Wind（全市场股票型ETF日度资金净流入合计）",
                              updated:"YYYY-MM-DD", daily:[["2024-01-02",-49.74], ...]}
      ⚠️ 该站有间歇性反爬验证墙（503 "Website access could not be verified"），随时会断。
备源: raw_data/etf_net_subscription.json（上交所官方份额日环比，cloud_fetch_v8.py 同轮产出，
      categories_em.股票型 子集口径最接近 Wind「股票型」）→ 自建累积序列
      raw_data/etf_flow_backup_history.json（逐日沉淀，断源也能撑起近5/20日与累计口径）。
last-good: raw_data/etf_flow_kimi_lastgood.json（最近一次成功抓取的 Kimi 全量快照，供断源日对比/降级）。

产出: raw_data/etf_flow_obs.json → update_v8.py 映射 window.ETF_FLOW_OBS（data/ETF_FLOW_OBS.js）
切源规则: Kimi updated >= 备源 data_date ⇒ active_source=kimi（新鲜优先）；
          Kimi 断/过期 ⇒ active_source=backup（自己的顶上），卡面标注口径差异。
幂等: 重跑安全；history 按日期覆盖写；只写 raw_data，不碰 data/（update_v8 统一生成）。
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
OUT = os.path.join(RAW, "etf_flow_obs.json")
HIST = os.path.join(RAW, "etf_flow_backup_history.json")
LASTGOOD = os.path.join(RAW, "etf_flow_kimi_lastgood.json")
KIMI_URL = "https://5jiniyutijiye.ok.kimi.link/data.js"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.JSONDecoder().raw_decode(f.read())[0]
    except Exception:
        return None


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _stats(daily):
    """daily: [[date, val], ...] 按日期升序 → (last_val, last_date, sum5, sum20, total)"""
    vals = [(d, float(v)) for d, v in daily if v is not None]
    if not vals:
        return None
    last_date, last_val = vals[-1]
    return {
        "last_date": last_date,
        "last_val": round(last_val, 2),
        "sum5": round(sum(v for _, v in vals[-5:]), 2),
        "sum20": round(sum(v for _, v in vals[-20:]), 2),
        "total": round(sum(v for _, v in vals), 2),
        "days": len(vals),
    }


def fetch_kimi():
    """抓 Kimi data.js，成功返回 dict（原始解析结果），失败返回 None。重试 2 次外层循环（铁律⑰：单次全新请求）。"""
    for attempt in range(2):
        try:
            req = urllib.request.Request(KIMI_URL, headers={
                "User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read().decode("utf-8", "ignore")
            if "could not be verified" in body or len(body) < 200:
                raise ValueError("kimi wall/empty (%dB)" % len(body))
            m = re.search(r"window\.ETF_FLOW_DATA\s*=\s*", body)
            if not m:
                raise ValueError("window.ETF_FLOW_DATA not found")
            obj, _ = json.JSONDecoder().raw_decode(body[m.end():])
            daily = obj.get("daily") or []
            if len(daily) < 100 or not obj.get("updated"):
                raise ValueError("daily too short: %d" % len(daily))
            obj["_live"] = True
            return obj
        except Exception as e:
            print("[kimi] attempt %d failed: %s" % (attempt + 1, e))
    return None


def main():
    # ── 1) 备源：上交所份额日环比（同轮 cloud_fetch_v8 已产出；缺文件则只用历史累积） ──
    sub = _load_json(os.path.join(RAW, "etf_net_subscription.json")) or {}
    em_stock = ((sub.get("categories_em") or {}).get("股票型") or {})
    backup_data_date = sub.get("data_date") or ""
    stock_net = em_stock.get("net_amount_yi")
    if stock_net is None:
        stock_net = sub.get("total_net_amount_yi")  # 降级：全类合计（标注 scope）
        em_stock = {"net_amount_yi": stock_net, "count": sub.get("total_etf")}
    hist = _load_json(HIST) or {"series": {}}
    series = hist.get("series") or {}
    if backup_data_date and stock_net is not None:
        series[backup_data_date] = round(float(stock_net), 3)
    hist_series = [[d, series[d]] for d in sorted(series)]
    backup_stats = _stats(hist_series) if hist_series else None
    if hist_series:
        _save_json(HIST, {"series": series, "scope": "上交所ETF份额日环比(股票型优先,缺则全类)",
                          "update_time": sub.get("update_time")})

    # ── 2) 主源：Kimi（失败回落 lastgood，但新鲜度判定不变） ──
    kimi_live = fetch_kimi()
    kimi_src = kimi_live or _load_json(LASTGOOD)
    if kimi_live:
        _save_json(LASTGOOD, {k: kimi_live.get(k) for k in
                              ("title", "unit", "source", "updated", "daily")})
    kimi_stats = _stats(kimi_src["daily"]) if kimi_src and kimi_src.get("daily") else None

    # ── 3) 切源判定：Kimi 数据日 ≥ 备源数据日 ⇒ 主源；否则备源顶上 ──
    kimi_updated = (kimi_src or {}).get("updated") or ""
    kimi_fresh = bool(kimi_stats and backup_data_date and kimi_updated >= backup_data_date)
    active = "kimi" if kimi_fresh else "backup"

    out = {
        "update_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": backup_data_date or (kimi_stats or {}).get("last_date", ""),
        "active_source": active,
        "kimi": {
            "ok": bool(kimi_stats),
            "live": bool(kimi_live),
            "updated": kimi_updated,
            "title": (kimi_src or {}).get("title", "ETF累计申赎净流入"),
            "unit": (kimi_src or {}).get("unit", "亿元"),
            "source": (kimi_src or {}).get("source", "Wind（全市场股票型ETF日度资金净流入合计）"),
            "stats": kimi_stats,
            "daily": (kimi_src or {}).get("daily") or [],
        },
        "backup": {
            "ok": bool(backup_stats),
            "data_date": backup_data_date,
            "scope": ("上交所股票型ETF份额净申赎" if em_stock.get("count") else "上交所全部ETF份额净申赎"),
            "etf_count": em_stock.get("count"),
            "source": "上交所官方基金份额日环比 × 单位净值（自建累积，与Wind流量口径有差异）",
            "stats": backup_stats,
            "daily": hist_series,
        },
        "note": ("主源 Kimi/Wind 全市场股票型ETF净流入（口径：日度资金净流入合计）；"
                 "Kimi 断源或过期时自动切备源上交所口径（份额日环比×净值，不含深市）"),
    }
    _save_json(OUT, out)
    print("[etf_flow_obs] active=%s kimi_live=%s kimi_updated=%s backup_date=%s backup_days=%d -> %s"
          % (active, bool(kimi_live), kimi_updated or "-", backup_data_date or "-",
             len(hist_series), os.path.basename(OUT)))
    return 0 if (kimi_stats or backup_stats) else 1


if __name__ == "__main__":
    sys.exit(main())
