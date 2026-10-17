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
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw_data")


CST = timezone(timedelta(hours=8))


def now_cst():
    """北京时间 CST+8。禁止无 tz 的本地时钟：云 runner (UTC) 会写出 -8h 的假时间戳。"""
    return datetime.now(CST)


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
    # 🛡 2026-10-15 一劳永逸：类型防御。
    #   `total` 现为**数字**＝今日个股涨停池家数（由 cloud_fetch_v8.f_limit_up_heatmap 回填）；
    #   历史/异常产物里它曾是"近N日每日家数"数组（与「今日家数」同名不同义），一旦当数字用，
    #   下游 min(60, 数组) 会得到 NaN ⇒ 情绪分显示 NaN（2026-10-15 主人截图实锤）。
    #   数组时退化为 today_total 并告警，绝不把数组当标量。
    total = lm.get("total", 0)
    if isinstance(total, (list, tuple)):
        print("[warn] LIMIT_UP_HEATMAP.total 为数组（旧 schema 残留），退化为 today_total")
        total = lm.get("today_total", 0) or 0
    if isinstance(ladder, list):
        # ladder 曾被占位写成 []（假占位）⇒ 退化为空 dict，由 cloud_fetch 回填真值
        ladder = {}
    top = lm.get("top", []) or []
    if not isinstance(top, list):
        top = []
    sectors = lm.get("sectors", []) or []

    # 最高连板数 = ladder 的最大 key
    max_ladder = max(int(k) for k in ladder.keys()) if ladder else 0
    # 连板梯队明细（数字排序）
    ladder_dist = {int(k): int(v) for k, v in ladder.items()}
    ladder_dist = dict(sorted(ladder_dist.items()))

    # 昨日全市场涨停家数（用于环比 delta_pct）
    # 🛡 2026-10-15 一劳永逸：**优先**用 cloud_fetch 回填的 prev_total = 上一交易日**涨停池家数**
    #   （与今日 total 完全同口径）⇒ 环比是真实、口径一致的比较。
    #   旧实现直接用"所有板块昨日家数之和"（板块口径，实测 183）与个股口径今日值（35）相减
    #   ⇒ delta_pct 恒失真（2026-10-15 线上实测 -80.87%，属典型口径混算）。
    #   板块口径求和仅作**兜底**（prev_total 缺失时），并在日志标注口径。
    prev_total = None
    _pt = lm.get("prev_total")
    if isinstance(_pt, int) and _pt > 0:
        prev_total = _pt
    elif sectors:
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
            print("[warn] prev_total 缺失，环比退回板块口径求和（与个股口径混算，仅供参考）")

    phase, score, color, advice, delta_pct = calc_phase(total, max_ladder, ladder_dist, prev_total)

    # 龙头票（连板最高的 3 只）
    # 🛡 2026-10-15：过滤掉无 lbc 的条目 —— top 在异常产物里可能是"板块榜"（name/total/recent5），
    #   若不过滤会把板块名当成"龙头个股"渲染。
    top_sorted = sorted([t for t in top if isinstance(t, dict) and t.get("lbc")],
                        key=lambda x: x.get("lbc", 0), reverse=True)[:3]
    leaders = [{"code": s.get("code"), "name": s.get("name"), "lbc": s.get("lbc"), "chg": s.get("chg")} for s in top_sorted]

    # 高连板家数
    high_ladder_count = sum(ladder_dist.get(n, 0) for n in range(3, 11))

    result = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
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