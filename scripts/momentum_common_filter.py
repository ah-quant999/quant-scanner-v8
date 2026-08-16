#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股动量共识股 · 共同点筛选器（2026-08-16）
================================================
输入：data/STOCK_MOMENTUM_STATE_V2.js（V2 增强分析，360 只 / 385 次出现）
      data/STOCK_QUOTE.js（名字/行业/概念补全）
输出：满足共同点规则的候选清单（按强度分级）

共同点结论（数据验证，385 次出现）：
  ★ 核心硬指标 = 入选时「连续上涨天数」：
      连涨 1 天 → T+5 胜率  5.5%，均值 -8.37%（买入即套）
      连涨 3-4天 → T+5 胜率 32.7%，均值 -0.84%
      连涨 5-7天 → T+5 胜率 89.7%，均值 +5.15%   ★ 分水岭
      连涨 8-10天→ T+5 胜率 100%，均值 +14.26%   ★ 最强
  ★ 入选日涨幅 / 共识次数：好坏票无差异（约 8.7% / 2.25），不可作为过滤条件
  ★ 板块阶段反向过滤（V2 sectorConfluence）：
      震荡板块共识股最优（胜率 50.4%，均值 +2.45%）
      主升/启动板块共识股显著跑输（17.0% / 16.3%，均值 -10.41% / -4.06%）
      → 剔除「入选日所属板块处于主升/启动」的共识股
  ★ 回撤控制：好票 max_drawdown 均值 8.5% vs 差票 17.7% → 上限 10% 更稳
  ★ 行业倾向（连涨≥5 子集内仍超额）：电子(96.6%,+16.4%) / 化工(100%,+12.9%) / 医药(100%,+12.5%)
      / 软件(100%,+11.3%) / 电气(100%,+5.7%) —— 加权不硬过滤

用法：python scripts/momentum_common_filter.py
输出：候选清单（默认打印，--json 输出 JSON 到 raw_data/momentum_filter_result.json）
"""
import json, re, sys, statistics
from collections import defaultdict
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent)  # scripts/ 上一级 = 项目根（云端/本机通用）

def load_js_var(path, var_name):
    """读取 data/*.js 中的 window.XXX = {...}; """
    src = open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s\s*=\s*(\{.*\});\s*$" % var_name, src, re.S)
    if not m:
        raise ValueError(f"找不到 window.{var_name} in {path}")
    return json.loads(m.group(1))

def sector_stage(s, pct_5d, pct_20d):
    """与前端板块周期判定同口径"""
    if pct_5d > 3 and pct_20d > 5: return "主升"
    if pct_5d > 1.5 and pct_20d > 0: return "启动"
    if pct_5d < -3 and pct_20d < -10: return "底部"
    if pct_5d < -1.5 and pct_20d < -5: return "退潮"
    return "震荡"

def main():
    d = load_js_var(f"{ROOT}/data/STOCK_MOMENTUM_STATE_V2.js", "STOCK_MOMENTUM_ENHANCED")
    q = load_js_var(f"{ROOT}/data/STOCK_QUOTE.js", "STOCK_QUOTE")
    srs = load_js_var(f"{ROOT}/data/SECTOR_RS.js", "SECTOR_RS")

    # 板块阶段映射表：板块名 -> stage（2026-08-16 收盘口径）
    stage_of_sector = {}
    for s in srs.get("sectors", []):
        stage_of_sector[s["name"]] = sector_stage(s["name"], s.get("pct_5d") or 0, s.get("pct_20d") or 0)

    # code -> quote（去前缀归一）
    by_code = {}
    for k, v in q.get("stocks", {}).items():
        by_code.setdefault(re.sub(r"\D", "", k), v)

    # 展开所有出现 + 用概念匹配板块阶段
    rows = []
    for pk, pv in d["periods"].items():
        for s in pv["all"]:
            sq = by_code.get(re.sub(r"\D", "", s["code"]), {}) or {}
            concepts = sq.get("concepts", []) or []
            # 概念 → 板块阶段（匹配 SECTOR_RS 板块名）
            stage = ""
            for c in concepts:
                for sec_name, st in stage_of_sector.items():
                    if sec_name in c or c in sec_name:
                        stage = st
                        break
                if stage:
                    break
            rows.append({**s, "period": pk,
                         "qname": sq.get("name", ""),
                         "industry": sq.get("industry", ""),
                         "concepts": concepts,
                         "pct_now": sq.get("pct"),
                         "stage": stage})

    def t5(sel):
        t = [r["t5_gain_pct"] for r in sel if r.get("t5_gain_pct") is not None]
        if not t:
            return None
        return (len(t), 100 * sum(1 for v in t if v > 0) / len(t), statistics.mean(t))

    # ─────────── 筛选链 ───────────
    S1 = [r for r in rows if (r.get("consecutive_up_days") or 0) >= 5]          # 核心：连涨≥5
    S2 = [r for r in S1 if (r.get("max_drawdown_pct") or 99) <= 10]             # 回撤≤10%
    # S3 板块阶段反向过滤：剔除主升/启动（V2 已验证：主升 17.0% / 启动 16.3% 胜率，震荡 50.4%）
    S3 = [r for r in S2 if r["stage"] not in ("主升", "启动")]
    S3_unknown = [r for r in S2 if r["stage"] == ""]                            # 概念未匹配板块 → 保留但标注

    def t5(sel):
        t = [r["t5_gain_pct"] for r in sel if r.get("t5_gain_pct") is not None]
        if not t:
            return None
        return (len(t), 100 * sum(1 for v in t if v > 0) / len(t), statistics.mean(t))

    s0, s1, s2, s3 = t5(S1), t5(S2), t5(S3), t5(S3_unknown)
    print("=" * 74)
    print("筛选链 T+5 表现验证（385 次出现 → 逐级收窄）")
    print("=" * 74)
    print(f"  全样本                 n=385  胜率 42.1%  均值 -1.18%")
    print(f"  S1 连涨≥5              n={s0[0]:3d}  胜率 {s0[1]:5.1f}%  均值 {s0[2]:+6.2f}%")
    print(f"  S2 +回撤≤10%           n={s1[0]:3d}  胜率 {s1[1]:5.1f}%  均值 {s1[2]:+6.2f}%")
    print(f"  S3 +剔除主升/启动板块    n={s2[0]:3d}  胜率 {s2[1]:5.1f}%  均值 {s2[2]:+6.2f}%")
    if s3:
        print(f"  （概念未匹配板块，保留观察  n={s3[0]:3d}  胜率 {s3[1]:5.1f}%  均值 {s3[2]:+6.2f}%）")

    # ─────────── 候选清单（去重，取最新出现） ───────────
    all_kept = S3 + S3_unknown
    by_code_sel = {}
    for r in sorted(all_kept, key=lambda x: x["date"], reverse=True):
        by_code_sel.setdefault(r["code"], r)
    cands = list(by_code_sel.values())
    cands.sort(key=lambda r: (r.get("consecutive_up_days") or 0), reverse=True)

    print("\n" + "=" * 74)
    print(f"候选清单（连涨≥5 + 回撤≤10% + 非主升/启动板块，去重 {len(cands)} 只，按连涨天数排序）")
    print("=" * 74)
    print(f"  {'代码':<8}{'名称':<10}{'行业':<20}{'连涨':>4}{'入选日%':>8}{'T+5%':>8}{'回撤%':>7}  阶段")
    for r in cands[:30]:
        stg = r["stage"] or "未匹配"
        flag = "⚠️" if r["stage"] == "" else ""
        print(f"  {r['code']:<8}{r['qname'] or r['code']:<10}{r['industry'][:18]:<20}"
              f"{r.get('consecutive_up_days', 0):>4}{r.get('sel_change_pct', 0):>+8.1f}"
              f"{(r.get('t5_gain_pct') or 0):>+8.1f}{r.get('max_drawdown_pct', 0):>+7.1f}  {stg}{flag}")

    # ─────────── 输出 JSON / JS 注入 ───────────
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = {
        "generated": now,
        "rule": {"S1_consecutive_up_days_ge5": True, "S2_max_drawdown_le10": True,
                 "S3_exclude_leadup_launch_stage": True},
        "stats": {"total": 385, "s1": s0[0], "s2": s1[0], "s3": s2[0],
                  "s1_win": round(s0[1], 1), "s1_mean": round(s0[2], 2),
                  "s2_win": round(s1[1], 1), "s2_mean": round(s1[2], 2),
                  "s3_win": round(s2[1], 1), "s3_mean": round(s2[2], 2)},
        "candidates": [{"code": r["code"], "name": r["qname"], "industry": r["industry"],
                        "consecutive_up_days": r.get("consecutive_up_days"),
                        "sel_change_pct": r.get("sel_change_pct"),
                        "t5_gain_pct": r.get("t5_gain_pct"),
                        "max_drawdown_pct": r.get("max_drawdown_pct"),
                        "stage": r.get("stage"),
                        "date": r.get("date")} for r in cands],
    }
    if "--json" in sys.argv:
        with open(f"{ROOT}/raw_data/momentum_filter_result.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"\n已输出 raw_data/momentum_filter_result.json（{len(cands)} 只）")
    if "--emit-js" in sys.argv:
        # 注入版：window.MOMENTUM_FILTER = {...};（带 republish_time，供缓存戳中性化）
        out["republish_time"] = now
        js = "window.MOMENTUM_FILTER = " + json.dumps(out, ensure_ascii=False) + ";\n"
        js_path = f"{ROOT}/data/MOMENTUM_FILTER.js"
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js)
        print(f"✅ 已输出 data/MOMENTUM_FILTER.js（{len(cands)} 只候选）→ {now}")

if __name__ == "__main__":
    main()
