# -*- coding: utf-8 -*-
"""板块周期档案生成器 —— 从 raw_data/limit_up_heatmap.json 派生 data/SECTOR_CYCLE_ARCHIVE.js

■ 用途（2026-09-16 主人令「放宽，用于累积」）
  涨停热力矩阵原本只保留近 30 日，看不出板块的完整周期。
  改为永久累积后，本脚本把长表「翻译」成**可读的周期档案**：
  每个板块的「启动 → 退潮」区间（几几年几月启动、几月结束），可逐年回查。

■ 为什么必须保留（禁止删除）
  数据源（东方财富涨停池）**只保留最近 1 个月**，历史无法重新拉取。
  本档案是长期累积数据，价值随年月增长，删除即永久丢失。
  ⇒ 已在 PROTECTED_FILES.json 登记，由 guard_protected_files.py 守卫。

■ 产出
  raw_data/sector_cycle.json    （中间产物，供 update_v8.py 转 js）
  data/SECTOR_CYCLE_ARCHIVE.js  （前端注入 window.SECTOR_CYCLE_ARCHIVE）

■ 周期判定
  某板块某日涨停家数 >= HOT_MIN(3) 视为「活跃日」；
  活跃日之间间隔 > CYCLE_GAP(3) 个交易日 ⇒ 断为一个新周期。
"""
import json, io, os, sys
from datetime import datetime

HOT_MIN = 3       # 单日 >=3 家算活跃
CYCLE_GAP = 3     # 活跃日间隔 >3 个交易日 ⇒ 断为新周期
MIN_LEN = 1       # 周期最短活跃日数

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "raw_data", "limit_up_heatmap.json")
MID = os.path.join(ROOT, "raw_data", "sector_cycle.json")
OUT = os.path.join(ROOT, "data", "SECTOR_CYCLE_ARCHIVE.js")


def build():
    if not os.path.exists(SRC):
        print(f"  ⚠️ 源文件不存在: {SRC}，跳过板块周期档案")
        return None
    d = json.load(io.open(SRC, encoding="utf-8"))
    dates = d.get("dates") or []
    sectors = d.get("sectors") or []
    if not dates or not sectors:
        print("  ⚠️ 源数据为空，跳过板块周期档案")
        return None

    cycles = []
    for s in sectors:
        name, arr = s.get("name"), s.get("data") or []
        hot = [i for i, v in enumerate(arr) if isinstance(v, (int, float)) and v >= HOT_MIN]
        if not hot:
            continue
        groups = [[hot[0]]]
        for i in hot[1:]:
            if i - groups[-1][-1] > CYCLE_GAP:
                groups.append([i])
            else:
                groups[-1].append(i)
        for g in groups:
            if len(g) < MIN_LEN:
                continue
            seg = arr[g[0]:g[-1] + 1]
            mx = max(seg) if seg else 0
            cycles.append({
                "sector": name,
                "start": dates[g[0]],
                "end": dates[g[-1]],
                "start_idx": g[0],
                "end_idx": g[-1],
                "days": g[-1] - g[0] + 1,
                "hot_days": len(g),
                "peak": mx,
                "peak_date": dates[g[0] + seg.index(mx)] if seg else "-",
                "total": sum(seg) if seg else 0,
                "ongoing": (g[-1] >= len(dates) - 2),
            })
    cycles.sort(key=lambda x: (x["start_idx"], x["sector"]))

    payload = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": 1,
        "source": "raw_data/limit_up_heatmap.json",
        "params": {"hot_min": HOT_MIN, "cycle_gap": CYCLE_GAP, "min_len": MIN_LEN},
        "range": [dates[0], dates[-1]],
        "columns": len(dates),
        "cycle_count": len(cycles),
        "cycles": cycles,
    }
    io.open(MID, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, indent=2))

    banner = (
        "// ═══════════════════════════════════════════════════════════════════════\n"
        "// 🔴🔴 重要档案文件 · 禁止删除 · 禁止 git rm · 禁止加入清理白名单 🔴🔴\n"
        "//\n"
        "// 板块周期档案（SECTOR_CYCLE_ARCHIVE）\n"
        "//   —— 由 raw_data/limit_up_heatmap.json 的累积长表派生，记录每个板块的\n"
        "//      「启动 → 退潮」周期区间（几几年几月启动、几月结束），可逐年回查。\n"
        "//\n"
        "// ⚠️ 本文件是**长期累积数据**，价值随年月增长，一旦删除无法恢复\n"
        "//    （涨停数据源只保留最近 1 个月，历史无法重新拉取）。\n"
        "//    已登记于 PROTECTED_FILES.json，由 guard_protected_files.py 守卫。\n"
        "//\n"
        "// 生成器：build_sector_cycle_archive.py\n"
        "// 最后更新：" + payload["update_time"] + "\n"
        "// ═══════════════════════════════════════════════════════════════════════\n"
        "\n")
    body = "window.SECTOR_CYCLE_ARCHIVE = " + json.dumps(
        payload, ensure_ascii=False, indent=2) + ";\n"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(banner + body)

    print(f"  ✅ 板块周期档案: {len(cycles)} 个周期 "
          f"({dates[0]}~{dates[-1]}, {len(dates)} 列) → data/SECTOR_CYCLE_ARCHIVE.js")
    return payload


if __name__ == "__main__":
    print("=" * 60)
    print(f"  板块周期档案生成  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    p = build()
    sys.exit(0 if p else 1)
