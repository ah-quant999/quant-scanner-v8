# -*- coding: utf-8 -*-
"""
【尾盘预选】生成器（2026-11-07 主人令②：数据源由 v8 自带，不依赖外部工具）

数据来源（真实、已在主站 data/ 注入）：
  - data/GOLD_POOL.js        —— window.GOLD_POOL.stocks[code].latest 实时信号旗标：
        缠论买_日K / 金钻_黄柱 / 金钻_起涨 / 四量图_机构变红 / 上涨趋势_条件1~4 / 上涨趋势 / signal_count
  - data/STOCK_MOMENTUM_STATE.js —— window.STOCK_MOMENTUM_STATE.days[last].categories
        今日「突破 / 启动」类动量票（给预选票打"今日突破"标记）

尾盘预选口径（诚实、可解释，非人工观点）：
  以 GOLD_POOL 中"有活跃买信号"的票为候选，按信号强度打分：
    缠论买_日K +3 | 金钻_起涨 +3 | 金钻_黄柱 +2 | 上涨趋势 +2 | 四量图_机构变红 +1
  + 命中今日"突破/启动"动量再 +1（贴"今日突破"标签）
  按总分降序取 Top10，前 3 标"精选"。
  说明：这是"今日有买信号、可关注次日低吸"的量化预选，非次日必涨保证。

输出：data/TAIL_SELECT.js —— window.TAIL_SELECT = {update_time, source, top10:[...]}
前端：暂未上架·观测类 卡（renderTailSelect）展示。

幂等：纯本地读取现有 data 文件，不联网，CI/本机均可跑。
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "GOLD_POOL.js"
MOM = ROOT / "data" / "STOCK_MOMENTUM_STATE.js"
OUT = ROOT / "data" / "TAIL_SELECT.js"

# 信号权重（与 user MEMORY 共识一致：jinzuan+chan 才是真赚钱信号）
WEIGHTS = {
    "缠论买_日K": 3,
    "金钻_起涨": 3,
    "金钻_黄柱": 2,
    "上涨趋势": 2,
    "四量图_机构变红": 1,
}


def _extract_simple(src: str) -> dict:
    """`window.X = {...};` 标准形式。"""
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", src, re.S)
    if not m:
        raise ValueError("无法解析 JSON 主体")
    return json.loads(m.group(1))


def _extract_iife_data(src: str) -> dict:
    """`window.X = (function(){ var data = {...}; return data; })();` 形式。"""
    i = src.find("var data")
    if i < 0:
        raise ValueError("未找到 var data 块")
    j = src.find("{", i)
    if j < 0:
        raise ValueError("未找到 data 起始 {")
    depth = 0
    k = j
    n = len(src)
    while k < n:
        ch = src[k]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return json.loads(src[j:k + 1])


def _momentum_today_codes() -> set:
    if not MOM.exists():
        return set()
    try:
        obj = _extract_iife_data(MOM.read_text(encoding="utf-8"))
    except Exception:
        return set()
    days = obj.get("days") or []
    if not days:
        return set()
    last = days[-1]
    cats = last.get("categories") or {}
    codes = set()
    for cat_name in ("突破", "启动"):
        for it in (cats.get(cat_name) or []):
            c = it.get("code")
            if c:
                codes.add(c)
    return codes


def main():
    if not POOL.exists():
        raise SystemExit(f"数据源缺失: {POOL}")
    pool = _extract_simple(POOL.read_text(encoding="utf-8"))
    pool_update = pool.get("update_time", "")
    stocks = pool.get("stocks", {})
    mom_codes = _momentum_today_codes()

    cands = []
    for key, s in stocks.items():
        latest = s.get("latest") or {}
        score = 0
        hit = []
        for sig, w in WEIGHTS.items():
            if latest.get(sig):
                score += w
                hit.append(sig)
        sc = s.get("signal_count") or 0
        if sc and sc > 0:
            score += min(sc, 3)  # signal_count 上限 3，避免刷分
        if score <= 0:
            continue
        is_mom = s.get("code") in mom_codes
        if is_mom:
            score += 1
            hit.append("今日突破/启动")
        cands.append({
            "code": s.get("code") or key,
            "name": s.get("name", ""),
            "board": s.get("board_label", "") or s.get("board", ""),
            "signal_count": sc,
            "score": score,
            "signals": hit,
            "momentum_today": is_mom,
            "sources": s.get("sources", []),
        })

    cands.sort(key=lambda x: (-x["score"], -x["signal_count"], x["code"]))
    top = cands[:10]
    for i, c in enumerate(top):
        c["rank"] = i + 1
        c["pick"] = (i < 3)  # 前 3 为精选

    payload = {
        "update_time": pool_update,
        "source": "GOLD_POOL(latest信号旗标) + STOCK_MOMENTUM_STATE(今日突破/启动)",
        "total_candidates": len(cands),
        "top10": top,
    }
    OUT.write_text(
        "window.TAIL_SELECT = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"[gen_tail_select] 候选 {len(cands)} 只 → Top10 (源 update_time={pool_update})")
    for c in top[:3]:
        print(f"  精选#{c['rank']} {c['code']} {c['name']} score={c['score']} {c['signals']}")


if __name__ == "__main__":
    main()
