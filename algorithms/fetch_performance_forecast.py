#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 A 股业绩预告（东方财富），输出 raw_data/performance_forecast.json
2026-08-30 新增：盘后数据页「业绩预告」数据源。
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import akshare as ak


def _current_report_date():
    """返回当前最近的财报季日期字符串，如 20250630 / 20250930 / 20251231 / 20260331。"""
    now = datetime.now()
    y, m = now.year, now.month
    # 1-3 月 -> 上年度 Q3(1231)；4-5 月 -> 本年度 Q1(0331)；
    # 6-8 月 -> 本年度 Q2(0630)；9-10 月 -> 本年度 Q3(0930)；11-12 月 -> 本年度 Q3(0930)（预告Q4）
    if m <= 3:
        return f"{y-1}1231"
    elif m <= 5:
        return f"{y}0331"
    elif m <= 8:
        return f"{y}0630"
    elif m <= 10:
        return f"{y}0930"
    else:
        return f"{y}0930"


def _parse_change_pct(s):
    if s is None:
        return None
    s = str(s)
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", s)
    if not m:
        return None
    return float(m.group(1))


def _type_to_key(t):
    """预告类型 -> 汇总计数键。"""
    t = str(t)
    if "预增" in t or "略增" in t:
        return "increase"
    elif "预减" in t or "略减" in t:
        return "decrease"
    elif "预亏" in t or "首亏" in t or "续亏" in t:
        return "loss"
    else:
        return "uncertain"


def _dedup_by_code(items):
    """同一股票可能因多个预测指标（归母净利润/扣非/营收）出现多条预告，
    去重保留 change_pct 绝对值最大的一条，避免前端重复展示。
    保持原列表首次出现顺序。
    """
    best = {}
    for it in items:
        code = it.get("code")
        if not code:
            continue
        old = best.get(code)
        if old is None:
            best[code] = it
        else:
            old_v = old.get("change_pct")
            new_v = it.get("change_pct")
            old_abs = abs(old_v) if old_v is not None else -1
            new_abs = abs(new_v) if new_v is not None else -1
            if new_abs > old_abs:
                best[code] = it
    seen = set()
    out = []
    for it in items:
        code = it.get("code")
        if not code or code in seen:
            continue
        if best.get(code) is it:
            out.append(it)
            seen.add(code)
    return out


def fetch_performance_forecast():
    date = _current_report_date()
    out = {"update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "report_date": date, "items": [], "summary": {}}
    try:
        df = ak.stock_yjyg_em(date=date)
        if df is None or df.empty:
            return out
        df = df.rename(columns={
            "股票代码": "code",
            "股票简称": "name",
            "预测指标": "indicator",
            "业绩变动": "change_desc",
            "业绩变动幅度": "change_pct_str",
            "预告类型": "type",
            "公告日期": "notice_date",
        })
        # 2026-08-30：新增「今日口径」——按公告日期（notice_date）筛当日新发布的预告，
        #   供「今日事件」页「今日业绩预告」卡使用；summary 仍是全报告期累计，两者不混用。
        today_str = datetime.now().strftime("%Y-%m-%d")
        items = []
        today_items = []
        date_count = {}
        for _, r in df.iterrows():
            t = str(r.get("type", ""))
            pct = _parse_change_pct(r.get("change_pct_str"))
            nd = str(r.get("notice_date", ""))[:10]
            rec = {
                "code": str(r.get("code", "")),
                "name": str(r.get("name", "")),
                "type": t,
                "change_pct": pct,
                "indicator": str(r.get("indicator", "")),
                "notice_date": str(r.get("notice_date", "")),
            }
            items.append(rec)
            if nd:
                date_count[nd] = date_count.get(nd, 0) + 1
            if nd == today_str:
                today_items.append(rec)
        # 2026-09-01 主人令：同一股票因多个预测指标会出现多条预告，去重保留 change_pct 绝对值最大的一条，
        #   并基于去重后结果重新计算 summary / today_summary，避免前端重复展示。
        items = _dedup_by_code(items)
        today_items = _dedup_by_code(today_items)
        summary = {"increase": 0, "decrease": 0, "loss": 0, "uncertain": 0, "total": len(items)}
        today_summary = {"increase": 0, "decrease": 0, "loss": 0, "uncertain": 0, "total": len(today_items)}
        for rec in items:
            summary[_type_to_key(rec["type"])] += 1
        for rec in today_items:
            today_summary[_type_to_key(rec["type"])] += 1
        # 按预增幅度排序，取前 15（全报告期 TOP，供盘后「业绩预告」汇总卡）
        items.sort(key=lambda x: (x.get("change_pct") if x.get("change_pct") is not None else -99999), reverse=True)
        today_items.sort(key=lambda x: (x.get("change_pct") if x.get("change_pct") is not None else -99999), reverse=True)
        out["items"] = items[:15]
        out["summary"] = summary
        out["today_summary"] = today_summary
        out["today_items"] = today_items[:8]
        out["today_date"] = today_str
        # 最近一批公告日期（今日无新增时用于兜底展示，避免「今日」卡空而无信息）
        if date_count:
            latest = sorted(date_count.items(), key=lambda kv: kv[0], reverse=True)
            out["latest_notice_date"] = latest[0][0]
            out["latest_notice_count"] = latest[0][1]
            out["recent_notice_dates"] = [{"date": d, "count": c} for d, c in latest[:5]]
    except Exception as e:
        print(f"  ⚠️ 业绩预告抓取失败: {e}")
        out["error"] = str(e)
    return out


def main():
    out = fetch_performance_forecast()
    RAW_DIR = ROOT / "raw_data"
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / "performance_forecast.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"✅ 业绩预告: {path} items={len(out.get('items', []))} summary={out.get('summary', {})}")
    return 0 if out.get("items") or not out.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
