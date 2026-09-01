#!/usr/bin/env python3
"""从历史遗留数据源补全 v8 raw_data/history/top10_daily_YYYYMMDD.json 快照。

来源 1：stock-scanner-wt-cards/data/history/（2026-07-17 ~ 07-30）
  - 已是 v8 兼容的 top10_daily 格式，直接复制。
  - 覆盖现有 20260726/27/30 的轻量回填（wt-cards 为 20 条完整快照）。

来源 2：九宝量化v6.0 260612 1500.tar.gz 的 backup_20260606 ~ backup_20260611
  - v6 没有 top10_daily_YYYYMMDD.json，只有 data/recommend.json。
  - 将 recommend.json 中的推荐列表转换为轻量 top10_daily 格式。

来源 3：本地增量备份
  - /e/workspace/backup_20260614_2100/stock-scanner_data/recommend.json
  - /e/workspace/backup_20260615_2100/stock-scanner/data/recommend.json
  - /e/workspace/stock-scanner/backup_202607*/data/history/top10_daily_*.json

注意：
  - 本脚本只读历史源，不写源。
  - 生成文件写入 E:/workspace/stock-scanner/raw_data/history/。
  - 更新 raw_data/history/top10_daily_history.json 索引（生成入口使用的格式）。
"""

import json
import os
import re
import tarfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
HIST_DIR = BASE / "raw_data" / "history"
WT_CARDS_DIR = Path("E:/workspace/stock-scanner-wt-cards/data/history")
V6_TAR = Path("E:/workspace/九宝量化v6.0 260612 1500.tar.gz")
V8_BACKUP_ROOT = Path("E:/workspace/stock-scanner")

V6_BACKUP_DATES = ["20260606", "20260607", "20260608", "20260609", "20260610", "20260611"]

# v6 格式 recommend.json 的额外本地备份（日期 -> recommend.json 路径）
EXTRA_V6_RECOMMEND = {
    "20260614": Path("E:/workspace/backup_20260614_2100/stock-scanner_data/recommend.json"),
    "20260615": Path("E:/workspace/backup_20260615_2100/stock-scanner/data/recommend.json"),
}


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _market_from_code(code: str) -> str:
    """从 6 位代码推断市场。"""
    c = str(code).strip()
    if not c.isdigit() or len(c) != 6:
        return ""
    if c.startswith(("600", "601", "603", "605", "688", "689")):
        return "sh"
    if c.startswith(("000", "001", "002", "003", "300", "301")):
        return "sz"
    if c.startswith(("430", "83", "87", "88", "92")):
        return "bj"
    return "sh" if c.startswith("6") or c.startswith("9") else "sz"


def _board_to_market(board: str, code: str) -> str:
    """优先用 board 标签推断市场，否则从代码推断。"""
    b = str(board)
    if "科创" in b:
        return "sh"
    if "创业" in b or "深圳" in b:
        return "sz"
    if "北交" in b or "新三板" in b:
        return "bj"
    if "上海" in b or "沪市" in b or "主板" in b:
        return "sh"
    if "港股" in b or "HK" in b.upper():
        return "hk"
    return _market_from_code(code)


def convert_v6_recommend_to_top10(recommend: list, date_str: str, update_time: str) -> dict:
    """把 v6 recommend.json 列表转成 v8 top10_daily 字典格式。"""
    top10 = []
    for i, r in enumerate(recommend):
        code = str(r.get("code", ""))
        if not code:
            continue
        board = r.get("board", "")
        market = _board_to_market(board, code)
        close = r.get("close", 0)
        pct_chg = r.get("pct_chg", 0)
        score = r.get("score", 0) or 0
        item = {
            "rank": i + 1,
            "code": code,
            "name": r.get("name", ""),
            "market": market,
            "board": board,
            "sig_count": r.get("sig_count", 0) or r.get("max_sig", 0) or 0,
            "close": float(close) if close else 0,
            "pct_chg": float(pct_chg) if pct_chg else 0,
            "pct_chg_20d": 0,
            "total_score": float(score),
            "sectors": [],
            "stop_loss": r.get("stop_loss", 0) or 0,
            "target_price": r.get("target", 0) or 0,
            "score_base": 0,
            "score_enhance": 0,
            "score_form": 0,
            "score_fund": 0,
            "score_sector": 0,
            "score_inst": 0,
            "score_quality": 0,
            "score_backtest": 0,
            "win_rate": 0,
            "quality_grade": "",
            "signals": {"chan": False, "jinzuan": False, "jigou": False, "trend": False, "form_A": False},
            "consecutive_days": r.get("days_in_pool", 0) or 0,
            "form_detail": "",
            "fund_detail": "",
            "sector_detail": "",
            "inst_detail": "",
            "quality_detail": " | ".join(r.get("reasons", [])) if isinstance(r.get("reasons"), list) else "",
            "source_note": "v6-recommend-derived",
        }
        top10.append(item)

    scores = [t["total_score"] for t in top10]
    return {
        "update_time": update_time,
        "source_note": "从 v6 recommend.json 轻量转换，仅用于 T+N 历史深度回填",
        "total_scored": len(top10),
        "count_80plus": sum(1 for s in scores if s >= 80),
        "max_score": max(scores) if scores else 0,
        "top10": top10,
    }


def backfill_wt_cards():
    """复制 stock-scanner-wt-cards 的 2026-07 快照到 v8。"""
    copied = []
    skipped = []
    if not WT_CARDS_DIR.exists():
        print(f"⚠️ wt-cards 目录不存在: {WT_CARDS_DIR}")
        return copied, skipped

    for src in sorted(WT_CARDS_DIR.glob("top10_daily_202607*.json")):
        data = load_json(src)
        if not isinstance(data, dict) or "top10" not in data:
            skipped.append((src.name, "format invalid"))
            continue
        dst = HIST_DIR / src.name
        if dst.exists():
            old = load_json(dst)
            old_len = len(old.get("top10", [])) if isinstance(old, dict) else 0
            new_len = len(data.get("top10", []))
            if new_len >= old_len:
                save_json(dst, data)
                copied.append((src.name, f"overwritten {old_len}->{new_len}"))
            else:
                skipped.append((src.name, f"existing longer {old_len}>{new_len}"))
        else:
            save_json(dst, data)
            copied.append((src.name, "new"))
    return copied, skipped


def backfill_v6_june():
    """从 v6 tar.gz 转换 2026-06-06 ~ 06-11 的 recommend.json。"""
    if not V6_TAR.exists():
        print(f"⚠️ v6 tar 不存在: {V6_TAR}")
        return []

    created = []
    with tarfile.open(V6_TAR, "r:gz", encoding="utf-8") as t:
        names = {m.name: m for m in t.getmembers()}
        for date_str in V6_BACKUP_DATES:
            inner = f"九宝量化v6.0 260612 1500/backup_{date_str}/data/recommend.json"
            if inner not in names:
                print(f"  ⚠️ {inner} not found in tar")
                continue
            f = t.extractfile(names[inner])
            recommend = json.loads(f.read().decode("utf-8"))
            if not isinstance(recommend, list):
                print(f"  ⚠️ {date_str} recommend.json not list")
                continue
            update_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} 15:00:00"
            result = convert_v6_recommend_to_top10(recommend, date_str, update_time)
            dst = HIST_DIR / f"top10_daily_{date_str}.json"
            new_len = len(result["top10"])
            if dst.exists():
                old = load_json(dst)
                old_len = len(old.get("top10", [])) if isinstance(old, dict) else 0
                if new_len >= old_len:
                    save_json(dst, result)
                    created.append((date_str, f"overwritten {old_len}->{new_len}"))
                else:
                    created.append((date_str, f"kept existing {old_len}>{new_len}"))
            else:
                save_json(dst, result)
                created.append((date_str, f"new {new_len}"))
    return created


def backfill_extra_v6_recommend():
    """转换本地额外 v6 格式 recommend.json（2026-06-14/15）。"""
    created = []
    for date_str, src in EXTRA_V6_RECOMMEND.items():
        if not src.exists():
            print(f"  ⚠️ {src} 不存在")
            continue
        recommend = load_json(src)
        if not isinstance(recommend, list):
            print(f"  ⚠️ {date_str} recommend.json not list")
            continue
        update_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} 15:00:00"
        result = convert_v6_recommend_to_top10(recommend, date_str, update_time)
        dst = HIST_DIR / f"top10_daily_{date_str}.json"
        new_len = len(result["top10"])
        if dst.exists():
            old = load_json(dst)
            old_len = len(old.get("top10", [])) if isinstance(old, dict) else 0
            if new_len >= old_len:
                save_json(dst, result)
                created.append((date_str, f"overwritten {old_len}->{new_len}"))
            else:
                created.append((date_str, f"kept existing {old_len}>{new_len}"))
        else:
            save_json(dst, result)
            created.append((date_str, f"new {new_len}"))
    return created


def backfill_v8_native_backups():
    """从 stock-scanner/backup_2026*/data/history/ 复制 v8 原生 top10_daily 快照。

    同一日期可能出现在多个备份目录中，保留 top10 条数最多的版本。
    """
    copied = []
    skipped = []
    candidates = {}
    if not V8_BACKUP_ROOT.exists():
        print(f"⚠️ v8 备份根目录不存在: {V8_BACKUP_ROOT}")
        return copied, skipped

    for src in sorted(V8_BACKUP_ROOT.glob("backup_*/data/history/top10_daily_2026*.json")):
        data = load_json(src)
        if not isinstance(data, dict) or "top10" not in data:
            skipped.append((src.name, f"format invalid ({src.parent.parent.name})"))
            continue
        date_str = src.stem.split("_")[-1]
        new_len = len(data.get("top10", []))
        if date_str not in candidates or new_len >= len(candidates[date_str]["data"].get("top10", [])):
            candidates[date_str] = {"data": data, "src": src}

    for date_str in sorted(candidates):
        data = candidates[date_str]["data"]
        src_name = candidates[date_str]["src"].parent.parent.name
        dst = HIST_DIR / f"top10_daily_{date_str}.json"
        new_len = len(data.get("top10", []))
        if dst.exists():
            old = load_json(dst)
            old_len = len(old.get("top10", [])) if isinstance(old, dict) else 0
            if new_len >= old_len:
                save_json(dst, data)
                copied.append((f"top10_daily_{date_str}.json", f"overwritten {old_len}->{new_len} from {src_name}"))
            else:
                skipped.append((f"top10_daily_{date_str}.json", f"existing longer {old_len}>{new_len}"))
        else:
            save_json(dst, data)
            copied.append((f"top10_daily_{date_str}.json", f"new {new_len} from {src_name}"))
    return copied, skipped


def update_history_index():
    """根据 raw_data/history/top10_daily_YYYYMMDD.json 重建 top10_daily_history.json。"""
    hist_file = HIST_DIR / "top10_daily_history.json"
    index = {}
    pat = re.compile(r"top10_daily_(\d{8})\.json$")
    for fn in sorted(os.listdir(HIST_DIR)):
        m = pat.match(fn)
        if not m:
            continue
        data = load_json(HIST_DIR / fn)
        if not isinstance(data, dict):
            continue
        iso = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
        index[iso] = {
            "count_80plus": data.get("count_80plus", 0),
            "total_scored": data.get("total_scored", 0),
            "max_score": data.get("max_score", 0),
            "update_time": data.get("update_time", ""),
        }
    save_json(hist_file, index)
    return len(index)


def main():
    HIST_DIR.mkdir(parents=True, exist_ok=True)

    print("=== 来源 1: v8 原生备份 stock-scanner/backup_2026*/data/history ===")
    copied, skipped = backfill_v8_native_backups()
    for name, note in copied:
        print(f"  ✅ {name}: {note}")
    for name, note in skipped:
        print(f"  ⏭️ {name}: {note}")

    print("\n=== 来源 2: stock-scanner-wt-cards 2026-07（补 v8 备份未覆盖日期） ===")
    copied, skipped = backfill_wt_cards()
    for name, note in copied:
        print(f"  ✅ {name}: {note}")
    for name, note in skipped:
        print(f"  ⏭️ {name}: {note}")

    print("\n=== 来源 3: v6 tar.gz 2026-06-06 ~ 06-11 ===")
    created = backfill_v6_june()
    for date_str, note in created:
        print(f"  ✅ top10_daily_{date_str}.json: {note}")

    print("\n=== 来源 4: 本地额外 v6 recommend 2026-06-14/15 ===")
    created = backfill_extra_v6_recommend()
    for date_str, note in created:
        print(f"  ✅ top10_daily_{date_str}.json: {note}")

    print("\n=== 更新历史索引 ===")
    count = update_history_index()
    print(f"  ✅ top10_daily_history.json 已更新，共 {count} 天")

    # 汇总
    all_files = sorted(HIST_DIR.glob("top10_daily_202*.json"))
    print(f"\n=== 汇总 ===")
    print(f"raw_data/history/top10_daily_*.json 总数: {len(all_files)}")
    if all_files:
        print(f"日期跨度: {all_files[0].stem.split('_')[-1]} ~ {all_files[-1].stem.split('_')[-1]}")


if __name__ == "__main__":
    main()
