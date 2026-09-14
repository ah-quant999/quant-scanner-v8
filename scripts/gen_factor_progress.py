#!/usr/bin env python
# -*- coding: utf-8 -*-
"""
因子补缺 walk-forward 进度跟踪卡 fetcher
- 数据源：data/FACTOR_AUDIT.js（已有 7 因子审计）
- 扩展：按主人 2026-09-09 22:31 提议的「分批回测」决策预填 batch / status
- 输出：raw_data/factor_progress.json
"""
import json
import re
from datetime import datetime
from json import JSONDecoder
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data" / "FACTOR_AUDIT.js"
DST = REPO / "raw_data" / "factor_progress.json"

# 主人 2026-09-09 22:31 决定（"分批回测"）：
#   批次 1（高优 3 个，质量+价值稳健维度）：GPOA / 经营现金流-总资产 / 盈利收益率 E/P
#   批次 2（中优 2 个，规模+流动性过滤）：总市值 / 60 日成交额中位数
#   批次 3（低优 1 个，已覆盖框架）：60 日波动率
#   剩余（中优 1 个）：负债/总资产 → 并入批次 2
# 初始 status 全 pending；实际回测结果由小九跑完 walk-forward 后手工补回，再 dispatch 重跑本 fetcher。

BATCH_MAP = {
    "总市值":             {"batch": 2, "owner": "小九(baostock)", "estimate_loops": "5y×12m walk-forward"},
    "盈利收益率":         {"batch": 1, "owner": "小九(akshare PE)",  "estimate_loops": "5y×12m walk-forward"},
    "GPOA":               {"batch": 1, "owner": "小九(财报+akshare)", "estimate_loops": "5y×12m walk-forward"},
    "经营现金流/总资产":  {"batch": 1, "owner": "小九(财报)",       "estimate_loops": "5y×12m walk-forward"},
    "负债/总资产":        {"batch": 2, "owner": "小九(财报)",       "estimate_loops": "5y×12m walk-forward"},
    "60日成交额中位数":   {"batch": 2, "owner": "小九(kline_cache)", "estimate_loops": "60d 滚动 std"},
    "60日波动率":         {"batch": 3, "owner": "agent(kline_cache)","estimate_loops": "已覆盖，扩展分位即可"},
}

PRIORITY_NOTE = {
    1: "高优（质量+价值稳健）",
    2: "中优（规模+流动性过滤）",
    3: "低优（框架已覆盖）",
}


def _load_factor_audit():
    txt = SRC.read_text(encoding="utf-8")
    m = re.search(r"window\.FACTOR_AUDIT\s*=\s*\{", txt)
    d, _ = JSONDecoder().raw_decode(txt, m.end() - 1)
    return d


def main():
    d = _load_factor_audit()
    factors = d.get("factors", [])
    progress = []
    for f in factors:
        name = f.get("name", "?")
        meta = BATCH_MAP.get(name, {"batch": 3, "owner": "待定", "estimate_loops": "?"})
        progress.append({
            "name": name,
            "label": f.get("label", "?"),
            "batch": meta["batch"],
            "batch_label": PRIORITY_NOTE.get(meta["batch"], "?"),
            "priority": f.get("priority", "?"),
            "v8_status": f.get("v8_status", "?"),
            "data_source": f.get("data_source", "?"),
            "gap": f.get("gap", "?"),
            "backtest_status": "pending",   # 初始全部 pending；回测结果由小九回填
            "oos_ir": None,                 # 预期年化 IR；-0.5 ~ 0.5 区间，walk-forward 后回填
            "sharpe_oos": None,
            "max_drawdown_oos": None,
            "last_run_at": None,
            "owner": meta["owner"],
            "estimate_loops": meta["estimate_loops"],
            "deploy_status": "未上线",
            "notes": "等小九 baostock/akshare 数据到位后跑 walk-forward，OOS IR > 0.3 且 4/5 连续 5 年胜率 > 55% 方可上线",
        })

    # 全局进度汇总
    n_total = len(progress)
    n_pending = sum(1 for p in progress if p["backtest_status"] == "pending")
    n_done = sum(1 for p in progress if p["backtest_status"] == "done")
    batch_done = {}
    for p in progress:
        b = p["batch"]
        batch_done.setdefault(b, {"total": 0, "pending": 0, "done": 0})
        batch_done[b]["total"] += 1
        batch_done[b][p["backtest_status"]] += 1

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_update_time": d.get("update_time", "?"),
        "policy": "主人 2026-09-09 22:31 决策：分批 walk-forward，禁止直接硬编码高分；OOS IR > 0.3 且 4/5 年胜率 > 55% 方可上线",
        "summary": {
            "total": n_total,
            "pending": n_pending,
            "done": n_done,
            "batches": batch_done,
        },
        "factors": progress,
    }

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {DST.name} written")
    print(f"  total={n_total}  pending={n_pending}  done={n_done}")
    for b, s in batch_done.items():
        print(f"  batch {b}: total={s['total']} pending={s['pending']} done={s['done']}")


if __name__ == "__main__":
    main()
