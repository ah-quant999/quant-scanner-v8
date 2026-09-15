#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_top10_from_triple_history.py
=====================================
用 raw_data/triple_history.json 里已有的历史共振数据，补全缺失的
raw_data/history/top10_daily_YYYYMMDD.json 快照，延长 T+N 回测/跟踪深度。

说明：
- triple_history 只含 code/name/board/close/total_score/sectors 等核心字段；
  补全出的 top10_daily 是"轻量版"，缺失 stop_loss/target_price/score 明细等字段。
- 该轻量版足够 backtest_comprehensive.py 使用（它只读 top10[].total_score/code/name）。
- 对已有快照的日期不覆盖，避免破坏生成器产出的完整版。
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TRIPLE_FILE = BASE / "raw_data" / "triple_history.json"
HIST_DIR = BASE / "raw_data" / "history"

# 从现有 top10_daily 快照里抄一份字段模板（用于新字段对齐）
TEMPLATE_FILE = None
for f in sorted(HIST_DIR.glob("top10_daily_*.json")):
    TEMPLATE_FILE = f
    break


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ 读取 {path} 失败: {e}")
        return None


def _stock_template():
    """从现有完整快照取第一条作为字段模板；没有则使用轻量默认值。"""
    if not TEMPLATE_FILE:
        return {}
    data = _load_json(TEMPLATE_FILE)
    if not data or not isinstance(data, dict):
        return {}
    top10 = data.get("top10", [])
    if not top10:
        return {}
    tpl = dict(top10[0])
    # 保留字段结构，但把可变值置空/默认
    for k in tpl:
        if k in ("rank", "code", "name", "market", "board", "sig_count",
                 "close", "pct_chg", "pct_chg_20d", "total_score",
                 "score_base", "score_enhance", "score_form", "score_fund",
                 "score_sector", "score_inst", "score_quality", "score_backtest",
                 "win_rate", "consecutive_days", "signals"):
            continue
        tpl[k] = "" if isinstance(tpl[k], str) else (0 if isinstance(tpl[k], (int, float)) else [])
    return tpl


def _market_prefix(code):
    c = str(code)
    if c.startswith(("6", "68", "69")):
        return "sh"
    if c.startswith(("0", "3", "4", "8", "92")):
        return "sz"
    return ""


def _backfill_date(triple_data, date_str, template):
    """为单个日期生成 top10_daily 快照。"""
    stocks = triple_data.get(date_str, [])
    if not stocks:
        return None
    # 按 total_score 降序、code 升序
    ranked = sorted(stocks, key=lambda s: (-(s.get("total_score") or 0), str(s.get("code", ""))))

    top10 = []
    for rank, s in enumerate(ranked, start=1):
        code = str(s.get("code", "")).strip()
        name = s.get("name", "")
        board = s.get("board", "") or _board_of_a(code)
        market = s.get("market", "") or _market_prefix(code)
        sectors = s.get("sectors", []) or []
        if isinstance(sectors, str):
            sectors = [sectors]

        rec = dict(template)
        rec.update({
            "rank": rank,
            "code": code,
            "name": name,
            "market": market,
            "board": board,
            "sig_count": s.get("signal_count", 0) or 0,
            "close": s.get("close", 0) or 0,
            "pct_chg": s.get("pct_chg", 0) or 0,
            "pct_chg_20d": 0,
            "total_score": s.get("total_score", 0) or 0,
            "sectors": sectors,
            "score_base": 50,
            "score_enhance": 0,
            "score_form": s.get("signal_count", 0) or 0,
            "score_fund": 0,
            "score_sector": 0,
            "score_inst": 0,
            "score_quality": 0,
            "score_backtest": 0,
            "win_rate": 0,
            "quality_grade": s.get("quality_grade", ""),
            "signals": {"chan": False, "jinzuan": False, "jigou": False,
                        "trend": False, "form_A": False},
        })
        top10.append(rec)

    total_scored = len(stocks)
    count_80plus = sum(1 for s in stocks if (s.get("total_score") or 0) >= 80)
    max_score = max((s.get("total_score") or 0) for s in stocks) if stocks else 0

    return {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_note": "本快照由 triple_history.json 回溯补全（轻量版，供 T+N 跟踪用）",
        "total_scored": total_scored,
        "count_80plus": count_80plus,
        "max_score": max_score,
        "top10": top10,
    }


def _board_of_a(code):
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
    print("=" * 60)
    print("  从 triple_history 补全 top10_daily 历史快照")
    print("=" * 60)

    triple_data = _load_json(TRIPLE_FILE)
    if triple_data is None:
        print("  ❌ 无法读取 triple_history.json，退出")
        return 1

    HIST_DIR.mkdir(parents=True, exist_ok=True)
    template = _stock_template()

    # 所有日期键（排除内部元数据键）
    date_keys = [k for k in triple_data.keys() if re.match(r"^\d{4}-\d{2}-\d{2}$", k)]

    created = 0
    skipped = 0
    for date_str in sorted(date_keys):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        fname = f"top10_daily_{dt.strftime('%Y%m%d')}.json"
        fpath = HIST_DIR / fname
        if fpath.exists():
            skipped += 1
            continue
        snapshot = _backfill_date(triple_data, date_str, template)
        if not snapshot:
            continue
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        created += 1
        print(f"  ✅ 生成 {fname}（{len(snapshot['top10'])} 只，max_score={snapshot['max_score']:.1f}）")

    print(f"\n  完成：新建 {created} 个，跳过已有 {skipped} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
