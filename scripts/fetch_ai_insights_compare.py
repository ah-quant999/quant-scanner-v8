#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 洞察多源观点对比卡 fetcher
- 数据源：data/maharo_macro.js（已由小九日 07:22 拉好的活数据）
- 解析 daily/weekly/monthly 三段文本，统计"AI 在不同时长尺度上的板块/主题关注度"
- 输出：raw_data/ai_insights_compare.json
"""
import json
import re
from collections import Counter
from datetime import datetime
from json import JSONDecoder
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data" / "maharo_macro.js"
INSIGHTS_SRC = REPO / "data" / "maharo_insights.js"  # 2026-09-10 一劳永逸：独立 insights 文件
DST = REPO / "raw_data" / "ai_insights_compare.json"

# 50 个 A 股常见板块/主线词典（按数据自洽顺序，手工整理；后续主人可补）
SECTOR_DICT = [
    "AI 缺电", "液冷", "金刚石", "涨价链", "铜", "MLCC", "CPU", "存储",
    "SOFC", "BloomEnergy", "三环集团", "中原内配", "数据中心", "电力",
    "银行", "红利", "券商", "保险", "地产", "新能源", "光伏", "锂电",
    "汽车", "整车", "汽零", "军工", "半导体", "光模块", "芯片", "存储芯片",
    "稀土", "有色", "煤炭", "钢铁", "化工", "医药", "创新药", "CXO",
    "CRO", "消费", "食品", "白酒", "家电", "纺织", "游戏", "传媒",
    "互联网", "教育", "农业", "猪肉", "鸡苗",
]

# 看多/看空/中性关键词（用段落级判别，只在文本中提取极性）
BULL_KW = ["看多", "做多", "受益", "景气", "加速", "上涨", "布局", "持有", "机会", "正当时", "催化", "看好", "扩大", "高增"]
BEAR_KW = ["看空", "做空", "回撤", "防御", "谨慎", "回避", "风险", "承压", "回调", "看跌", "熊", "爆雷", "下行", "收缩", "压力"]


def _load_maharo_macro():
    """容错解析 window.MAHORO_MACRO = {...};（之前发现文件末尾有额外字符）"""
    txt = SRC.read_text(encoding="utf-8")
    m = re.search(r"window\.MAHORO_MACRO\s*=\s*\{", txt)
    d, _ = JSONDecoder().raw_decode(txt, m.end() - 1)
    return d


def _load_maharo_insights():
    """2026-09-10 一劳永逸：优先从独立文件读 insights；缺失则 fallback 到 maharo_macro.js 内嵌。
    返回 {daily, weekly, monthly}（各为 {"text": ...}）。"""
    if INSIGHTS_SRC.exists():
        txt = INSIGHTS_SRC.read_text(encoding="utf-8")
        m = re.search(r"window\.MAHORO_INSIGHTS\s*=\s*\{", txt)
        if m:
            d, _ = JSONDecoder().raw_decode(txt, m.end() - 1)
            return d
    # fallback
    return _load_maharo_macro().get("insights", {})


def _extract(text: str):
    """从一段 AI 文本中提取：板块提及次数、句子极性分布"""
    sector_hits = Counter()
    for kw in SECTOR_DICT:
        n = text.count(kw)
        if n > 0:
            sector_hits[kw] = n
    # 句子极性（按。！？分段）
    sents = re.split(r"[。！？\n]+", text)
    bull, bear, neutral = 0, 0, 0
    for s in sents:
        s = s.strip()
        if not s:
            continue
        b = any(kw in s for kw in BULL_KW)
        br = any(kw in s for kw in BEAR_KW)
        if b and br:
            neutral += 1
        elif b:
            bull += 1
        elif br:
            bear += 1
        else:
            neutral += 1
    return {
        "sector_hits": dict(sector_hits.most_common(15)),
        "polarity": {"bull": bull, "bear": bear, "neutral": neutral,
                     "bull_ratio": round(bull / max(bull + bear + neutral, 1), 3),
                     "bear_ratio": round(bear / max(bull + bear + neutral, 1), 3)},
    }


def main():
    d = _load_maharo_macro()
    ins = _load_maharo_insights()
    daily_text = ins.get("daily", {}).get("text", "")
    weekly_text = ins.get("weekly", {}).get("text", "")
    monthly_text = ins.get("monthly", {}).get("text", "")

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_update_time": d.get("update_time", "?"),
        "scope": {
            "daily": {"date": ins.get("daily", {}).get("date", "?"),
                      "sources_read": ins.get("daily", {}).get("sources_read", 0)},
            "weekly": {"period": ins.get("weekly", {}).get("period", "?")},
            "monthly": {"period": ins.get("monthly", {}).get("period", "?")},
        },
        "texts": {
            "daily": daily_text,
            "weekly": weekly_text,
            "monthly": monthly_text,
        },
        "extracted": {
            "daily": _extract(daily_text),
            "weekly": _extract(weekly_text),
            "monthly": _extract(monthly_text),
        },
        "sources_count": len(d.get("sources", [])),
        "watched_count": len(d.get("watched", [])),
    }

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {DST.name} written, {len(daily_text) + len(weekly_text) + len(monthly_text)} chars total")
    print(f"  daily sectors: {len(out['extracted']['daily']['sector_hits'])}")
    print(f"  weekly sectors: {len(out['extracted']['weekly']['sector_hits'])}")
    print(f"  monthly sectors: {len(out['extracted']['monthly']['sector_hits'])}")


if __name__ == "__main__":
    main()
