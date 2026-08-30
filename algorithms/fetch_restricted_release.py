#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取未来 A 股解禁日历（东方财富），输出 raw_data/restricted_release.json
2026-08-30 新增：盘后数据页「解禁日历」数据源。
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import akshare as ak


def _fmt_yi(v):
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return str(v)
    if v >= 1e8:
        return f"{v/1e8:.2f}亿"
    if v >= 1e4:
        return f"{v/1e4:.2f}万"
    return f"{v:.0f}"


def fetch_restricted_release():
    today = datetime.now()
    start = today.strftime("%Y%m%d")
    ranges = {
        "d7": (today, today + timedelta(days=7)),
        "d30": (today, today + timedelta(days=30)),
        "d90": (today, today + timedelta(days=90)),
    }
    all_items = []
    stats = {}
    try:
        end90 = ranges["d90"][1].strftime("%Y%m%d")
        df = ak.stock_restricted_release_detail_em(start_date=start, end_date=end90)
        if df is None or df.empty:
            return {"update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "items": [], "stats": {}}
        df = df.rename(columns={
            "股票代码": "code",
            "股票简称": "name",
            "解禁时间": "date",
            "解禁数量": "shares",
            "实际解禁市值": "market_cap",
            "限售股类型": "type",
        })
        for _, r in df.iterrows():
            cap = r.get("market_cap")
            item = {
                "code": str(r.get("code", "")),
                "name": str(r.get("name", "")),
                "date": str(r.get("date", "")),
                "amount": _fmt_yi(cap),
                "type": str(r.get("type", "")),
                "market_cap": float(cap) if cap is not None else None,
            }
            all_items.append(item)
        # 按日期统计各区间
        for key, (s, e) in ranges.items():
            cnt = sum(1 for it in all_items if s.strftime("%Y-%m-%d") <= it["date"] <= e.strftime("%Y-%m-%d"))
            stats[key] = cnt
        # 按解禁市值排序取前 15
        all_items.sort(key=lambda x: (x.get("market_cap") or 0), reverse=True)
        all_items = all_items[:15]
        # 去掉原始数值，仅保留展示字段
        for it in all_items:
            it.pop("market_cap", None)
    except Exception as e:
        print(f"  ⚠️ 解禁日历抓取失败: {e}")
        return {"update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "items": [], "stats": {}, "error": str(e)}

    return {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": all_items,
        "stats": stats,
    }


def main():
    out = fetch_restricted_release()
    RAW_DIR = ROOT / "raw_data"
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / "restricted_release.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"✅ 解禁日历: {path} items={len(out.get('items', []))} stats={out.get('stats', {})}")
    return 0 if out.get("items") or not out.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
