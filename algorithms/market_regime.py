#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观环境判定（利率上行/下行/平稳）
- 输入：out/macro.json（fetcher 产出，中国+美国国债+LPR+银行间）
- 输出：out/market_regime.json
- 主人框架（2026-08-19）：
    利率上行期 → 推荐银行/煤炭/运营商/公用事业 + 黄金/油气 + 保险 + 低位医药
    利率下行期 → 推荐科技/成长/创业板
- 诚实标注：⚠️ 利率与板块映射是经验关系，非因果；回测胜率 55-65% 是上限
"""
import json
import os
import sys
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(BASE, "out", "macro.json")
OUT = os.path.join(BASE, "out", "market_regime.json")


def log(msg):
    print(f"  [market_regime] {msg}", flush=True)


def pct_change(series, days):
    """取最近 N 日相对前 N 日的变化百分比"""
    if len(series) < days + 5:
        return None
    recent = sum(s for s in series[-days:] if s is not None) / max(1, sum(1 for s in series[-days:] if s is not None))
    prior = sum(s for s in series[-days * 2:-days] if s is not None) / max(1, sum(1 for s in series[-days * 2:-days] if s is not None))
    if prior is None or recent is None:
        return None
    return (recent - prior) * 100  # bp


def classify_trend(bp_change, threshold=8.0):
    """按 bp 变化判定上行/下行/平稳
    threshold: 默认 8bp（10Y 国债），超出算显著变化"""
    if bp_change is None:
        return "N/A", 0
    if bp_change > threshold:
        return "上行", 1
    if bp_change < -threshold:
        return "下行", -1
    return "平稳", 0


def main():
    if not os.path.exists(IN):
        log(f"缺 {IN}，先跑 fetch_macro.py")
        return 1
    with open(IN, encoding="utf-8") as f:
        data = json.load(f)

    # 中国 10Y 趋势（20 日窗口）
    cn_series = [r.get("cn_10y") for r in data.get("cn_10y", []) if r.get("cn_10y") is not None]
    cn_now = cn_series[-1] if cn_series else None
    cn_5d = pct_change(cn_series, 5)
    cn_20d = pct_change(cn_series, 20)
    cn_5d_label, cn_5d_dir = classify_trend(cn_5d)
    cn_20d_label, cn_20d_dir = classify_trend(cn_20d)

    # 美国 10Y 趋势
    us_series = [r.get("us_10y") for r in data.get("us_10y", []) if r.get("us_10y") is not None]
    us_now = us_series[-1] if us_series else None
    us_5d = pct_change(us_series, 5)
    us_20d = pct_change(us_series, 20)
    us_5d_label, us_5d_dir = classify_trend(us_5d)
    us_20d_label, us_20d_dir = classify_trend(us_20d)

    # LPR 立场（最新 3 期）
    lpr = data.get("lpr", [])
    lpr_recent = lpr[-3:] if lpr else []
    lpr_changes = []
    for i in range(1, len(lpr_recent)):
        cur, prev = lpr_recent[i], lpr_recent[i - 1]
        if cur.get("lpr_1y") and prev.get("lpr_1y") and cur["lpr_1y"] != prev["lpr_1y"]:
            lpr_changes.append(f"1Y {prev['lpr_1y']}→{cur['lpr_1y']}")
        if cur.get("lpr_5y") and prev.get("lpr_5y") and cur["lpr_5y"] != prev["lpr_5y"]:
            lpr_changes.append(f"5Y {prev['lpr_5y']}→{cur['lpr_5y']}")
    lpr_stance = "降息" if lpr_changes else ("中性" if lpr_recent else "N/A")
    lpr_1y_now = lpr_recent[-1]["lpr_1y"] if lpr_recent else None
    lpr_5y_now = lpr_recent[-1]["lpr_5y"] if lpr_recent else None

    # 综合判定
    # 主：cn_20d 方向；辅：us_20d（影响黄金/油气/银行）；LPR 是政策面信号
    cn_score = cn_20d_dir  # -1/0/+1
    us_score = us_20d_dir

    if cn_score > 0 and us_score > 0:
        regime = "利率双升"
        conf = "高"
    elif cn_score > 0 and us_score <= 0:
        regime = "中国利率上行"
        conf = "中"
    elif cn_score < 0 and us_score < 0:
        regime = "利率双降"
        conf = "高"
    elif cn_score < 0 and us_score >= 0:
        regime = "中国利率下行"
        conf = "中"
    else:
        regime = "利率平稳"
        conf = "低"

    # 推荐板块：始终按主人指定的「利率上行期」框架输出（独立于当前 regime）
    # 主人自行决定：当前实际 regime 与框架假设是否匹配 → 是否采纳推荐
    rec_groups = [
        {"priority": 1, "name": "红利/高股息", "sectors": ["银行", "煤炭", "通信运营", "公用事业"], "logic": "利率上行利好银行净息差；高股息防御"},
        {"priority": 2, "name": "黄金/油气", "sectors": ["贵金属", "油气"], "logic": "实际利率上行推升金价；油气对冲"},
        {"priority": 3, "name": "保险", "sectors": ["保险"], "logic": "利率上行修复投资收益"},
        {"priority": 4, "name": "低位医药", "sectors": ["中药", "化学制药", "医疗服务"], "logic": "月线低位 + 利率上行期防御"},
        {"priority": -1, "name": "规避", "sectors": ["半导体", "通信设备", "计算机设备"], "logic": "高位成长股对利率敏感"},
    ]
    alt_groups_down = [
        {"priority": 1, "name": "科技/成长", "sectors": ["半导体", "计算机", "通信设备", "电子元件"], "logic": "利率下行利好成长股估值"},
        {"priority": 2, "name": "消费", "sectors": ["白酒", "食品饮料", "家用电器"], "logic": "利率下行提振消费"},
    ]

    out = {
        "meta": {
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "disclaimer": "⚠️ 利率与板块映射是经验关系，非因果；回测胜率 55-65% 上限。实盘验证 ≥3 个月。",
            "framework_source": "主人 2026-08-19 拍板（利率上行期板块推荐框架）",
        },
        "current_rates": {
            "cn_10y": round(cn_now, 4) if cn_now else None,
            "us_10y": round(us_now, 4) if us_now else None,
            "lpr_1y": lpr_1y_now,
            "lpr_5y": lpr_5y_now,
        },
        "trends": {
            "cn_5d": {"label": cn_5d_label, "bp": round(cn_5d, 2) if cn_5d else None},
            "cn_20d": {"label": cn_20d_label, "bp": round(cn_20d, 2) if cn_20d else None},
            "us_5d": {"label": us_5d_label, "bp": round(us_5d, 2) if us_5d else None},
            "us_20d": {"label": us_20d_label, "bp": round(us_20d, 2) if us_20d else None},
            "lpr_recent_changes": lpr_changes,
            "lpr_stance": lpr_stance,
        },
        "regime": {
            "label": regime,
            "confidence": conf,
            "cn_score": cn_score,
            "us_score": us_score,
        },
        "recommendation_groups": rec_groups,
        "alt_groups_down_regime": alt_groups_down,
        "framework_match": "匹配上行框架" if "上行" in regime else ("分化: 当前实际与框架假设不符，主人自行判断" if regime != "利率平稳" else "中国平稳+美国上行 = 框架部分匹配"),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已写入 {OUT}")
    log(f"  现状: 中国10Y={cn_now}% 美国10Y={us_now}% LPR1Y={lpr_1y_now}%")
    log(f"  趋势: 中国5d {cn_5d_label} ({cn_5d}bp), 20d {cn_20d_label} ({cn_20d}bp); 美国5d {us_5d_label} ({us_5d}bp), 20d {us_20d_label} ({us_20d}bp)")
    log(f"  判定: {regime} (置信={conf})")
    log(f"  推荐组数: {len(rec_groups)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())