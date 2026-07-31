#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fundamental_helper.py — 基本面分数复用模块（金股观测 / 驾驶舱 共用）
================================================================
统一封装：
  - fq_key_of(market, code)   : 由 scan_result / backtest_tdx 的 market+code 拼出
                                fundamental_quality.json 的键 (sh_600030 / hk_00005)
  - load_fundamental(path)    : 读取 stocks 映射
  - quality_points(fq)        : 计算 (quality_score, grade, detail)，与 generate_top10 口径一致
                                A=15~25 / B=5 / D=-10 / C或中性=0；叠加消息面 news ±15(截断)
                                港股中性兜底：reason 含「港股」则 grade="" 不扣分
                                （兼容 2026-07-25 修复前旧数据把港股误标 D 的情况）

设计目的：金股观测与驾驶舱使用完全相同的评分逻辑，避免两套面板分数不一致。
"""
import os
import json

BASE = os.path.dirname(os.path.abspath(__file__))

# market 中文标签 / 原始前缀 归一
_MARKET_MAP = {
    "沪市": "sh", "上海": "sh", "深市": "sz", "深圳": "sz", "港股": "hk",
    "科创": "sh", "创业": "sz",
}


def fq_key_of(market, code):
    """拼 fundamental_quality.json 的键：sh_600030 / sz_300750 / hk_00005"""
    m = (market or "").lower()
    c = str(code or "").strip()
    m = _MARKET_MAP.get(m, m)
    if not m or not c:
        return c  # 退化：只返回 code
    return f"{m}_{c}"


def load_fundamental(path=None):
    if path is None:
        path = os.path.join(BASE, "data", "fundamental_quality.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("stocks", {})
    except Exception:
        return {}


def quality_points(fq):
    """返回 (quality_score, grade, detail)。

    grade 取值: A / B / C / D / ""(中性)
    quality_score 计算规则（与 generate_top10.py 2026-07-22 优化一致）：
      A级: 基准15 + (ROE≥30:+5 / ≥20:+2) + (营收≥200%:+5 / ≥100%:+3) → 15~25
      B级: 5
      D级: -10
      C级/无数据: 0
    叠加消息面 news.score（业绩预告/重组类公告，已在采集端截断 ±20，此处再夹 ±15）。
    """
    if not fq:
        return 0, "", ""
    grade = fq.get("grade", "")
    reason = fq.get("reason", "") or ""
    # 中性兜底：2026-07-25 修复前，无基本面数据的股票（含港股）被误判为 D 冤扣 -10。
    # 修复后无数据应为中性 grade="" 。此处对陈旧数据做兼容修正，避免金股/驾驶舱误罚。
    if grade == "D" and reason == "无基本面数据":
        grade = ""

    roe = fq.get("roe")
    rev = fq.get("revenue_growth")
    if grade == "A":
        qs = 15
        if roe is not None:
            if roe >= 30:
                qs += 5
            elif roe >= 20:
                qs += 2
        if rev is not None:
            if rev >= 200:
                qs += 5
            elif rev >= 100:
                qs += 3
    elif grade == "B":
        qs = 5
    elif grade == "D":
        qs = -10
    else:
        qs = 0  # C 或 中性("")

    # 消息面加减分
    news = fq.get("news") or {}
    ns = int(news.get("score") or 0)
    ns = max(-15, min(15, ns))
    qs += ns

    detail = reason or ""
    tags = news.get("tags") or []
    if tags:
        detail = (detail + " | 消息:" + ",".join(tags)).strip(" |")
    return qs, grade, detail
