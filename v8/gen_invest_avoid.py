#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_invest_avoid.py — 投资避雷针·新闻语料量化（轻量）数据 consolidate 生产者
================================================================
主人令（2026-10-27）：任务#5「新闻语料量化层轻量版 + 盘前并入 + 投资避雷针」的
  「盘前并入」落地 —— 把投资避雷针卡原本散读的 6 个数据源 consolidate 成单一原子文件
  data/INVEST_AVOID.js → window.INVEST_AVOID，由盘前链（v8_morning_plan.yml，07:50
  工作日 CST）统一刷新，杜绝「六源各自时效不一、卡体新鲜度不可控」的旧坑。

消费方：index.html __renderInvestAvoid（已改为优先读 window.INVEST_AVOID，缺失时降级到散源）。
口径（🔴 全部条目 = 规则从真实数据自动生成，无人工观点、无编造）：
  • 个股避雷   → data/DAJIJIN_REDUCTION.js.records（大基金减持·法定披露）
              + data/SUSPENSION_ALERT.js.stocks（*ST / 停牌预警）
  • 规避板块   → data/MARKET_REGIME.js.recommendation_groups（priority<0 = 规避）
  • 环境风险   → data/RISK_GAUGE.js（overall 红/黄/绿 + verdict）
  • 轻量舆情   → data/MACRO_BRIEF.js（crisis_score + news_brief 标签化要闻）
              + data/MARKET_ALERTS.js（mood + summary 盘后综述）
任一源缺失 ⇒ 对应条目降级（不产出该条目 / 置 None），绝不伪造、绝不崩链。

设计（与 gen_morning_plan.py 同款稳健口径）：
  - 纯前端聚合的「后端版」：读 data/*.js（window.X = {...}; 前缀剥离），写 data/INVEST_AVOID.js。
  - UTF-8 全程；cn runner（Windows+GBK）打印中文安全；解析失败静默降级（宁缺勿错）。
  - 输出含 update_time（生成时刻）+ data_date（数据日，取各源最新 update_time 的日期），
    前端新鲜度徽标用 update_time。

调度：被 .github/workflows/v8_morning_plan.yml 在盘前 07:50 调用（Contents API 同步本文件 +
  6 源，python 跑，api_put_file.py 推 data/INVEST_AVOID.js，空提交用 card_need_push 跳过）。
================================================================
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "INVEST_AVOID.js")


def read_js(fname):
    """读 data/<fname>.js → dict；缺失/坏 → None（静默降级，不伪造）"""
    p = os.path.join(ROOT, "data", fname + ".js")
    if not os.path.exists(p):
        print(f"  ⚠️ {fname}.js 缺失 ⇒ 该源按不可用处理")
        return None
    try:
        s = open(p, encoding="utf-8").read()
        i, j = s.index("{"), s.rindex("}")
        return json.loads(s[i:j + 1])
    except Exception as e:
        print(f"  ⚠️ {fname}.js 解析失败: {e} ⇒ 该源按不可用处理")
        return None


def main():
    now = datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🧭 投资避雷针 consolidate 生成 @ {now}")

    dj = read_js("DAJIJIN_REDUCTION")      # 大基金减持
    sa = read_js("SUSPENSION_ALERT")        # *ST / 停牌
    mr = read_js("MARKET_REGIME")           # 规避板块框架
    rg = read_js("RISK_GAUGE")              # 环境风险温度计
    mb = read_js("MACRO_BRIEF")             # 宏观危机分 + 轻量舆情
    ma = read_js("MARKET_ALERTS")           # 盘后综述 + 情绪

    # ── 规避板块（priority<0）──
    avoid_sectors = []
    if mr and mr.get("recommendation_groups"):
        for g in mr["recommendation_groups"]:
            if isinstance(g, dict) and (g.get("priority") or 0) < 0 and g.get("sectors"):
                avoid_sectors.extend(g["sectors"])

    # ── 数据日（取各源最新 update_time 的日期；全缺 ⇒ 今日）──
    dates = []
    for src in (dj, sa, mr, rg, mb, ma):
        ts = (src or {}).get("update_time") or (src or {}).get("date")
        if ts:
            dates.append(str(ts)[:10])
    data_date = max(dates) if dates else now[:10]

    payload = {
        "update_time": now,
        "data_date": data_date,
        "pipeline": "v8/gen_invest_avoid.py",
        # 个股避雷：原样保留 DAJIJIN_REDUCTION / SUSPENSION_ALERT 全量，前端按 .records/.stocks 读取
        "dajijin": dj,
        "suspension": sa,
        # 规避板块：已扁平化（从 MARKET_REGIME 抽取 priority<0）
        "avoid_sectors": avoid_sectors,
        # 环境风险
        "risk_overall": (rg or {}).get("overall"),
        "risk_verdict": (rg or {}).get("verdict"),
        # 轻量舆情 / 宏观危机分
        "crisis_score": (mb or {}).get("crisis_score"),
        "crisis_level": (mb or {}).get("crisis_level"),
        "news_brief": (mb or {}).get("news_brief") or [],
        # 盘后综述 / 情绪
        "mood": (ma or {}).get("mood"),
        "summary": (ma or {}).get("summary"),
        # 元信息：各源时效（前端如需逐源新鲜度可展示）
        "sources": {
            "dajijin": (dj or {}).get("update_time"),
            "suspension": (sa or {}).get("update_time"),
            "market_regime": (mr or {}).get("update_time"),
            "risk_gauge": (rg or {}).get("update_time"),
            "macro_brief": (mb or {}).get("update_time"),
            "market_alerts": (ma or {}).get("update_time"),
        },
        "note": "投资避雷针·新闻语料量化（轻量）：个股避雷来自法定披露（大基金减持）+ 停牌/*ST 预警，"
                "轻量舆情消费 MACRO_BRIEF 标签化要闻 + MARKET_ALERTS 综述，非逐条新闻 NLP；非投资建议。",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.INVEST_AVOID = " + json.dumps(payload, ensure_ascii=False) + ";\n")
    sz = os.path.getsize(OUT)
    n_dj = len((dj or {}).get("records") or [])
    n_sa = len((sa or {}).get("stocks") or [])
    print(f"  ✓ 产出 data/INVEST_AVOID.js（{sz} B）")
    print(f"    个股避雷：大基金减持 {n_dj} 条 · 停牌/*ST {n_sa} 只；规避板块 {len(avoid_sectors)} 个；"
          f"危机分 {payload['crisis_score']}；舆情 {len(payload['news_brief'])} 条；数据日 {data_date}")


if __name__ == "__main__":
    main()
