#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情绪周期定位器（2026-08-13 新增 · 暂未上架实验区）
================================================
- 数据源：LIMIT_UP_HEATMAP（ladder + top + total + sectors）
- 算法：涨停家数 + 最高连板 + 板块分布 + 趋势对比 → 四象限定位
- 输出：data/SENTIMENT_CYCLE.js

四象限定义：
  冰点：涨停 < 30 家 且 最高连板 ≤ 2（赚钱效应归零，报复性窗口临近）
  回暖：涨停 30-60 或 最高连板 3（开始出现赚钱效应）
  高潮：涨停 ≥ 80 且 最高连板 ≥ 5（情绪狂热，警惕追高）
  退潮：相较昨日涨停数下滑 30%+（昨日高位今日转弱）
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw_data")


def load_limit_up():
    """读取 data/LIMIT_UP_HEATMAP.js"""
    path = os.path.join(DATA, "LIMIT_UP_HEATMAP.js")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if text.startswith("window.LIMIT_UP_HEATMAP"):
        text = text.split("=", 1)[1]
    text = text.rstrip(";\n ")
    try:
        return json.loads(text)
    except Exception as e:
        print(f"[warn] LIMIT_UP_HEATMAP 解析失败: {e}")
        return {}


def calc_phase(total_up, max_ladder, ladder, prev_total):
    """根据当日指标判定情绪周期象限

    Returns: (phase, score, advice)
    """
    # 综合分（0-100）
    # 涨停家数（0-60分）：60 家封顶
    score_up = min(60, total_up)
    # 最高连板（0-25分）：5板封顶
    score_ladder = min(25, max_ladder * 5)
    # 连板梯队广度（0-15分）：≥3 板家数加权
    high_ladder_count = sum(ladder.get(str(n), 0) for n in range(3, 11))
    score_breadth = min(15, high_ladder_count * 1.5)
    score = round(score_up + score_ladder + score_breadth, 1)

    # 趋势（昨日对比）
    if prev_total and prev_total > 0:
        delta_pct = (total_up - prev_total) / prev_total * 100
    else:
        delta_pct = 0.0

    # 象限判定（先看绝对水平，再看趋势）
    if total_up < 30 and max_ladder <= 2:
        phase = "冰点"
        color = "#3b82f6"  # 蓝
        advice = "💡 报复性连板窗口临近：冰点后情绪修复，关注低位/首板"
    elif delta_pct <= -30:
        phase = "退潮"
        color = "#f97316"  # 橙
        advice = "⚠️ 情绪退潮中：高位股注意回撤，关注高低切换"
    elif score >= 80:
        phase = "狂热"
        color = "#ef4444"  # 红
        advice = "🔥 情绪狂热：警惕追高，等待分歧后的二波机会"
    elif score >= 60:
        phase = "高潮"
        color = "#f59e0b"  # 黄
        advice = "✨ 高潮持续：聚焦核心龙头，注意仓位管理"
    elif score >= 30:
        phase = "回暖"
        color = "#10b981"  # 绿
        advice = "🌱 情绪回暖：可适度参与，盯紧最高板扩展"
    else:
        phase = "低迷"
        color = "#64748b"  # 灰
        advice = "⏸️ 情绪低迷：观望为主，等待明确方向"

    return phase, score, color, advice, round(delta_pct, 2)


def main():
    lm = load_limit_up()
    if not lm:
        print("[warn] LIMIT_UP_HEATMAP 缺失，跳过")
        return

    ladder = lm.get("ladder", {}) or {}
    total = lm.get("total", 0)
    top = lm.get("top", []) or []
    sectors = lm.get("sectors", []) or []

    # 最高连板数 = ladder 的最大 key
    max_ladder = max(int(k) for k in ladder.keys()) if ladder else 0
    # 连板梯队明细（数字排序）
    ladder_dist = {int(k): int(v) for k, v in ladder.items()}
    ladder_dist = dict(sorted(ladder_dist.items()))

    # 昨日全市场涨停总数 = 所有板块昨日涨停数之和
    # 注意：sectors 是板块列表（非按日期排），每个 s.data 是该板块近 10 日涨停家数序列
    # 取所有板块 data[-2]（昨日）求和 = 全市场昨日总数（口径：LIMIT_UP_HEATMAP 注 "近10日板块涨停家数"）
    prev_total = None
    if sectors:
        yesterday_vals = []
        for s in sectors:
            d = s.get("data", []) if isinstance(s, dict) else []
            if len(d) >= 2:
                try:
                    yesterday_vals.append(int(d[-2]))
                except (TypeError, ValueError):
                    pass
        if yesterday_vals:
            prev_total = sum(yesterday_vals)

    phase, score, color, advice, delta_pct = calc_phase(total, max_ladder, ladder_dist, prev_total)

    # 龙头票（连板最高的 3 只）
    top_sorted = sorted(top, key=lambda x: x.get("lbc", 0), reverse=True)[:3]
    leaders = [{"code": s.get("code"), "name": s.get("name"), "lbc": s.get("lbc"), "chg": s.get("chg")} for s in top_sorted]

    # 高连板家数
    high_ladder_count = sum(ladder_dist.get(n, 0) for n in range(3, 11))

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": lm.get("update_time", "")[:10],
        "source": "LIMIT_UP_HEATMAP",
        "phase": phase,
        "color": color,
        "score": score,
        "delta_pct": delta_pct,
        "advice": advice,
        "metrics": {
            "total_up": total,
            "max_ladder": max_ladder,
            "high_ladder_count": high_ladder_count,  # ≥3板家数
            "sectors_count": len(sectors),
        },
        "ladder_dist": ladder_dist,
        "leaders": leaders,
        "prev_total": prev_total,
        "note": "冰点=涨停<30家且最高板≤2（报复性窗口临近）；高潮=涨停≥80且最高板≥5；退潮=较昨日-30%+",
    }

    # 写入
    out_path = os.path.join(DATA, "SENTIMENT_CYCLE.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.SENTIMENT_CYCLE = {json.dumps(result, ensure_ascii=False)};\n")
    print(f"[ok] {out_path}  phase={phase} score={score} total_up={total}")

    # 同步 raw
    raw_path = os.path.join(RAW, "sentiment_cycle.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()