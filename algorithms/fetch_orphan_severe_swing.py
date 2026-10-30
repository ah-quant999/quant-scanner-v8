#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v8 孤儿模块 SEVERE_SWING：严重异动雷达（暂未上架 › 观测类）

2026-10-30 主人令新建（查重结论：与投资避雷针[停牌/ST/减持]、解禁日历、业绩预告均不重复）。
口径：交易所"严重异动"实践口径的轻量化代理 ——
  ① 已触发档：连板≥2（涨停池"连续涨停"字段，连板股即严重异动高发群体）
  ② 逼近档：金股池 chg_5d/chg_20d ≥15% 或 概念龙头 chg_ratio ≥15%（3日偏离≥20% 触发线的逼近区）
数据源全为轻量接口（涨停池 1 次 + 本地池扫描），不扫全A历史K线。
用法：python fetch_orphan_severe_swing.py
输出：raw_data/severe_swing.json
"""

import json
import os
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "raw_data")
V6_DATA_DIR = os.path.join(os.path.dirname(ROOT), "data")
OUT = os.path.join(DATA_DIR, "severe_swing.json")

NEAR_THRESHOLD = 15.0   # 逼近档涨幅线（%）
TRIGGER_THRESHOLD = 20.0  # 交易所 3 日偏离触发线（%），用于 gap 计算


def log(msg):
    print(f"[severe_swing {datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def _load_pool(fname, key):
    """读 raw_data（回退 v6 data）里的池文件。"""
    p = os.path.join(DATA_DIR, fname)
    if not os.path.exists(p):
        p = os.path.join(V6_DATA_DIR, fname)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"  {fname} 读取失败: {e}")
        return None


def fetch_zt_pool(triggered, near, seen):
    """来源1：涨停池。连板≥2 → 已触发档；首板 → 逼近档。"""
    try:
        import akshare as ak
        from datetime import timedelta
        today = datetime.datetime.now()
        trade_date = today
        wd = today.weekday()
        if wd == 5:
            trade_date = today - timedelta(days=1)
        elif wd == 6:
            trade_date = today - timedelta(days=2)
        df = ak.stock_zt_pool_em(date=trade_date.strftime("%Y%m%d"))
        if df is None or df.empty:
            log("  涨停池为空")
            return
        n_trig = 0
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            if not code or code in seen:
                continue
            try:
                pct = float(row.get("涨跌幅", 0) or 0)
            except Exception:
                pct = 0.0
            # 连板数：优先"连续涨停"列（东财口径=连续几天），回退"涨停统计"(x天y板)
            boards = 0
            for col, getter in (("连续涨停", lambda v: float(v or 0)),
                                ("涨停统计", None)):
                if col in row.index:
                    try:
                        v = row.get(col)
                        if col == "涨停统计" and v:
                            # "3天2板" → 取板数 2；"2/2" → 取 2
                            s = str(v)
                            if "板" in s:
                                boards = float(s.split("天")[-1].replace("板", "") or 0)
                            elif "/" in s:
                                boards = float(s.split("/")[-1] or 0)
                        elif col == "连续涨停":
                            boards = float(v or 0)
                        break
                    except Exception:
                        continue
            item = {"code": code, "name": name, "pct": round(pct, 1),
                    "boards": int(boards)}
            if boards >= 2:
                item["desc"] = f"{int(boards)}连板·严重异动高发"
                triggered.append(item)
                seen.add(code)
                n_trig += 1
            elif pct >= 9.5:
                item["desc"] = "首板涨停·关注连板"
                near.append(item)
                seen.add(code)
        log(f"  涨停池: 触发档 {n_trig} 只")
    except Exception as e:
        log(f"  涨停池扫描异常: {e}")


def fetch_pools(near, seen):
    """来源2/3：金股池 + 概念龙头（≥15% 逼近档）。"""
    n = 0
    gp = _load_pool("gold_pool.json", "stocks")
    if gp:
        try:
            for code, s in (gp.get("stocks", {}) or {}).items():
                name = s.get("name", "") or ""
                if not name or code in seen:
                    continue
                chg = max(s.get("chg_5d", 0) or 0, s.get("chg_20d", 0) or 0)
                if chg >= NEAR_THRESHOLD:
                    near.append({"code": code, "name": name,
                                 "pct": round(chg, 1), "boards": 0,
                                 "desc": f"池内5/20日涨幅{chg:.0f}%·逼近{TRIGGER_THRESHOLD:.0f}%线"})
                    seen.add(code)
                    n += 1
        except Exception as e:
            log(f"  金股池扫描异常: {e}")
    cr = _load_pool("concept_ranking.json", "hot_list")
    if cr:
        try:
            for item in (cr.get("hot_list", []) or [])[:30]:
                for st in (item.get("leading_stocks", []) or []):
                    code = (st.get("code", "") or "").strip()
                    name = (st.get("name", "") or "").strip()
                    chg = st.get("chg_ratio", 0) or 0
                    if not code or not name or code in seen:
                        continue
                    if chg >= NEAR_THRESHOLD:
                        near.append({"code": code, "name": name,
                                     "pct": round(chg, 1), "boards": 0,
                                     "desc": f"概念[{item.get('name','')[:6]}]龙头+{chg:.0f}%"})
                        seen.add(code)
                        n += 1
        except Exception as e:
            log(f"  概念龙头扫描异常: {e}")
    log(f"  池扫描新增逼近档 {n} 只")


def main():
    triggered, near, seen = [], [], set()
    fetch_zt_pool(triggered, near, seen)
    fetch_pools(near, seen)
    triggered.sort(key=lambda x: -x.get("boards", 0))
    near.sort(key=lambda x: -x.get("pct", 0))
    out = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "caliber": "连板≥2=已触发档；池内涨幅≥15%=逼近档（3日偏离20%触发线）",
        "triggered": triggered[:12],
        "near": near[:12],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"  ✅ 已保存: {OUT} (触发{len(out['triggered'])}/逼近{len(out['near'])})")


if __name__ == "__main__":
    main()
