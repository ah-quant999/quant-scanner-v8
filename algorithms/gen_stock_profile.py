#!/usr/bin/env python3
"""2026-08-22 主人令：STOCK_PROFILE 自愈生成器。

背景（根因）：
  data/STOCK_PROFILE.js 是前端个股「行业/概念」兜底数据源（index.html 行 6025-6026
  fallback 读 window.STOCK_PROFILE）。其上游 raw_data/stock_profile.json 原仅由
  legacy_v6/sync_v6_to_v8.py 生成，而该脚本不在 v8 云端链路中 → 自 2026-08-07 起
  永久陈旧（审计实测 update_time=2026-08-07，且 raw mtime=08-10）。

修复：
  改为从【已维护】的 raw_data/stock_names.json 派生。stock_names 每日 post_close 刷新
  （STOCK_LIST），含 industry / concepts，覆盖 9591 只（原 stock_profile 仅 4801），
  覆盖率更高。本脚本每次 post_close 运行，写回 raw_data/stock_profile.json，
  再由 update_v8.py 转 data/STOCK_PROFILE.js —— 彻底摆脱 legacy 同步依赖，周一自动自愈。
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    ROOT = Path(__file__).resolve().parent.parent
except Exception:
    ROOT = Path(os.getcwd())
RAW = ROOT / "raw_data"
CST = ZoneInfo("Asia/Shanghai")


def main():
    names_path = RAW / "stock_names.json"
    if not names_path.exists():
        print("[gen_stock_profile] ⚠️ 缺 raw_data/stock_names.json，跳过")
        return 1
    try:
        with open(names_path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        print(f"[gen_stock_profile] ⚠️ 读取 stock_names.json 失败: {e}")
        return 1

    items = d.get("data") or d.get("stocks") or []
    profiles = {}
    for it in items:
        code = str(it.get("code", "") or "")
        if not code:
            continue
        profiles[code] = {
            "industry": (it.get("industry") or "").strip(),
            "concepts": list(it.get("concepts") or []),
        }

    out = {
        "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(profiles),
        "profiles": profiles,
    }
    out_path = RAW / "stock_profile.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[gen_stock_profile] ✅ 派生 {len(profiles)} 条 → raw_data/stock_profile.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
