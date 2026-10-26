# -*- coding: utf-8 -*-
"""
gen_strategy_walkforward.py —— ③ 策略级 Walk-Forward（基石 4 落地）

【目的】
  把「因子清账 + 胜率加权」这套组合选股方法，拿到历史每日快照上做滚动样本外（OOS）验证。
  历史快照（raw_data/history/final_recommend_YYYYMMDD.json，168 个每日文件）自带推荐清单 +
  行业 + final_score，但【不含已实现盈亏】，故本脚本以「选股方法的稳定性/集中度一致性」
  作为 OOS 代理指标（而非收益率 OOS）—— 诚实标注，不臆造收益。

【指标】
  · top_n_overlap   ：当日 top_n 与次日 top_n 的重合只数（稳定性代理；越高=方法越一致、越可预期）
  · industry_HHI    ：当日行业集中度（赫芬达尔指数，1/n→1）；越高=越押单一行业
  · max_industry_pct：当日最大单一行业占比（直接对应「同行业≤30%」闸）
  · avg_final_score ：当日平均 final_score

【Walk-Forward 设计】
  按日期升序切分：IS = 前 70% 快照（校准/训练窗），OOS = 后 30% 快照（验证窗）。
  比较两窗的均值指标；OOS 与 IS 接近 ⇒ 方法在样本外稳定；OOS 明显恶化 ⇒ 预警。

【用法】
  python3 gen_strategy_walkforward.py
  输出 data/STRATEGY_WALKFORWARD.js（window.STRATEGY_WALKFORWARD）
"""
import os
import re
import json
import glob
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(os.path.dirname(HERE), "raw_data", "history")
OUTPUT_PATH = os.path.join(os.path.dirname(HERE), "data", "STRATEGY_WALKFORWARD.js")
IS_RATIO = 0.70


def _code_of(s):
    c = str(s.get("code", "") or "")
    return c.lstrip(".")


def load_snapshots():
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "final_recommend_*.json")))
    snaps = []
    for fp in files:
        try:
            d = json.load(open(fp, "r", encoding="utf-8"))
        except Exception:
            continue
        m = re.search(r"(\d{8})", os.path.basename(fp))
        date = m.group(1) if m else ""
        stocks = d.get("stocks") or []
        codes = [_code_of(x) for x in stocks if _code_of(x)]
        inds = [str(x.get("industry") or "未知") for x in stocks]
        scores = [float(x.get("final_score") or 0) for x in stocks]
        snaps.append({
            "date": date,
            "codes": codes,
            "industries": inds,
            "scores": scores,
        })
    snaps = [s for s in snaps if s["codes"]]
    snaps.sort(key=lambda s: s["date"])
    return snaps


def hhi(industries):
    n = len(industries)
    if n == 0:
        return 0.0, 0.0
    from collections import Counter
    c = Counter(industries)
    shares = [v / n for v in c.values()]
    h = sum(x * x for x in shares)
    max_pct = max(shares) * 100 if shares else 0.0
    return round(h, 4), round(max_pct, 1)


def analyze(snaps):
    rows = []
    for i, s in enumerate(snaps):
        h, maxp = hhi(s["industries"])
        avg_score = round(sum(s["scores"]) / len(s["scores"]), 2) if s["scores"] else 0.0
        nxt = snaps[i + 1]["codes"] if i + 1 < len(snaps) else []
        overlap = len(set(s["codes"]) & set(nxt))
        rows.append({
            "date": s["date"],
            "n": len(s["codes"]),
            "overlap": overlap,
            "overlap_ratio": round(overlap / len(s["codes"]), 3) if s["codes"] else 0.0,
            "industry_hhi": h,
            "max_industry_pct": maxp,
            "avg_final_score": avg_score,
        })
    return rows


def summarize(rows):
    is_n = int(len(rows) * IS_RATIO)
    is_rows = rows[:is_n]
    oos_rows = rows[is_n:]
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None
    is_stat = {
        "n": len(is_rows),
        "overlap_ratio": mean([r["overlap_ratio"] for r in is_rows]),
        "industry_hhi": mean([r["industry_hhi"] for r in is_rows]),
        "max_industry_pct": mean([r["max_industry_pct"] for r in is_rows]),
        "avg_final_score": mean([r["avg_final_score"] for r in is_rows]),
    }
    oos_stat = {
        "n": len(oos_rows),
        "overlap_ratio": mean([r["overlap_ratio"] for r in oos_rows]),
        "industry_hhi": mean([r["industry_hhi"] for r in oos_rows]),
        "max_industry_pct": mean([r["max_industry_pct"] for r in oos_rows]),
        "avg_final_score": mean([r["avg_final_score"] for r in oos_rows]),
    }
    # 稳定性判读：OOS 相对 IS 的偏离（重合度不降、集中度不升 = 稳定）
    ov_is = is_stat["overlap_ratio"] or 0
    ov_oos = oos_stat["overlap_ratio"] or 0
    hhi_is = is_stat["industry_hhi"] or 0
    hhi_oos = oos_stat["industry_hhi"] or 0
    maxp_oos = oos_stat["max_industry_pct"] or 0
    stable = (ov_oos >= ov_is * 0.85) and (hhi_oos <= hhi_is * 1.15) and (maxp_oos <= 35.0)
    verdict = "样本外稳定 ✅" if stable else "样本外需关注 ⚠️"
    return is_stat, oos_stat, stable, verdict


def main():
    snaps = load_snapshots()
    if not snaps:
        print("  ⚠️ 未找到历史快照，跳过策略级 walk-forward")
        return
    rows = analyze(snaps)
    is_stat, oos_stat, stable, verdict = summarize(rows)
    # 滚动 10 日均值（用于折线图）
    win = 10
    roll = []
    for i in range(len(rows)):
        seg = rows[max(0, i - win + 1): i + 1]
        ov = sum(r["overlap_ratio"] for r in seg) / len(seg)
        hh = sum(r["industry_hhi"] for r in seg) / len(seg)
        mx = sum(r["max_industry_pct"] for r in seg) / len(seg)
        roll.append({
            "date": rows[i]["date"],
            "overlap_ratio": round(ov, 3),
            "industry_hhi": round(hh, 4),
            "max_industry_pct": round(mx, 1),
        })
    out = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": f"raw_data/history/final_recommend_*.json（{len(snaps)} 个每日快照）",
        "method": "因子清账 + 胜率加权 组合的【样本外选股稳定性】walk-forward（非收益率 OOS，历史快照无已实现盈亏）",
        "is_ratio": IS_RATIO,
        "is_window": is_stat,
        "oos_window": oos_stat,
        "verdict": verdict,
        "stable": stable,
        "metric_notes": {
            "overlap_ratio": "当日 top_n 与次日 top_n 重合比例（稳定性代理；越高=方法越一致）",
            "industry_hhi": "行业集中度（赫芬达尔，1/n→1；越高=越押单一行业）",
            "max_industry_pct": "当日最大单一行业占比（对应「同行业≤30%」闸；>30 即触发约束）",
            "avg_final_score": "当日平均 final_score",
        },
        "rolling": roll,
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("window.STRATEGY_WALKFORWARD = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";")
    print(f"  📐 策略级 walk-forward：{len(snaps)} 快照 | IS={is_stat['n']} OOS={oos_stat['n']} "
          f"| OOS 重合={oos_stat['overlap_ratio']} HHI={oos_stat['industry_hhi']} 最大行业={oos_stat['max_industry_pct']}% "
          f"⇒ {verdict}，已写 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
