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
# 🆕 2026-09-16 主人令「这些马上回测…不要整个版面都在等待」：
#   由 algorithms/factor_walkforward.py 跑出的真回测结果，供本 fetcher 判 done / 删除。
WF_JSON = REPO / "raw_data" / "factor_walkforward.json"

# 台账因子名 → 回测引擎因子键（algorithms/factor_walkforward.py :: FACTOR_DEFS）
WF_MAP = {
    "12-1 跨周期动量":     "mom12_1",
    "残差动量":            "resid_mom",
    "最大日收益 MAX":      "max20",
    "特质波动率 IVOL":     "ivol60",
    "换手率趋势":          "turntrend",
    "隔夜跳空累积":        "overnight20",
    "60日波动率":          "vol60",
    "60日成交额中位数":    "amt60",
}


def _load_walkforward():
    """读 factor_walkforward.json → ({因子键: 结果}, update_time)。缺失/损坏返回空。"""
    if not WF_JSON.exists():
        return {}, None
    try:
        d = json.loads(WF_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] factor_walkforward.json 解析失败，按无结果处理: {e}")
        return {}, None
    return (d.get("factors") or {}), d.get("update_time")

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

# ═══════════════════════════════════════════════════════════════════════════
# 待回测候选因子台账（阿狸咪的工程师 2026-09-15 07:50 · 主人令）
#
# 主人 2026-09-15 07:33：「是你准备回测可以追加的因子，准备有空再做的那种，
#   都写在里面，一旦回测新因子不行再删，这样才知道进度和备忘。」
#
# 【台账规则】
#   ① 凡「准备回测 / 准备追加进选股」的因子，一律先登记在此（status=pending）；
#      只有登记过的因子才允许进 generate_top10.py —— 禁止绕过台账硬编码因子。
#   ② 回测达标（OOS IR > 0.3 且 4/5 年胜率 > 55%）⇒ 改 done 并回填 oos_ir；
#   ③ 回测不达标 ⇒ **从本池直接删除该条**（主人令「不行再删」，不留遗体）；
#   ④ 每条在 data_source 里写明「离能开跑还差什么」—— 这是排程依据。
#
# 【选池原则】与现有四量终极 / CRDS / 三重共识**正交度优先**（同族因子重复登记
#   = 虚增进度）；A 组只依赖已入仓的 kline_cache ⇒ 本机随时可跑，是「有空就做」
#   的第一顺位；B 组需扩财报字段 ⇒ 排在 A 组之后，避免卡在数据抓取上。
#
# 【已排除、故不登记】（留痕用，不是待办）
#   2026-09-15 Alpha101 因子族两项均经实测否决，未入池：
#     · 82 因子共识组合超额 —— 门槛越高超额越大且 IS/OOS 同号，但**按日 t 值
#       全部 |t| < 2**（K≥12 时 T+30 超额 +1.38% 而 t=1.70），且 K≥14 触发率
#       跌破 5% ⇒ 统计不显著，不予接入；
#     · Bottom 层「一票否决」排除项 —— T+20 利差 −6~−7.75% 但仅前半段成立，
#       后半段 8/8 组反转（不满足 OOS 同号），T+5/T+10 配对 p=0.35~0.72 不显著。
# ═══════════════════════════════════════════════════════════════════════════
CANDIDATE_POOL = [
    # ── A 组：数据就绪（kline_cache 已入仓，本机可立即 walk-forward）──
    {
        "name": "12-1 跨周期动量", "label": "动量因子 Mom12-1",
        "logic": "过去 12 个月收益**剔除最近 1 个月**（避开短期反转污染）",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "与现有短线动量正交，用于测长周期选股能力",
        "priority": "高", "batch": 1,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "12m×5y walk-forward",
    },
    {
        "name": "残差动量", "label": "动量因子 ResidMom",
        "logic": "对全池等权回归，取个股残差的 12-1 累积",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "剥离 beta 后的纯个股动量，比原始动量更抗市场同涨同跌",
        "priority": "中", "batch": 2,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "12m×5y walk-forward",
    },
    {
        "name": "最大日收益 MAX", "label": "行为因子 MAX(彩票偏好)",
        "logic": "近 20 日最大单日涨幅；**高 MAX 扣分**（彩票偏好异象）",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "负向因子，可直接做「剔除高 MAX 票」的排除项验证",
        "priority": "中", "batch": 2,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "20d 滚动 + 12m×5y walk-forward",
    },
    {
        "name": "特质波动率 IVOL", "label": "低波因子 IVOL",
        "logic": "近 60 日剔除市场因子后的残差波动；**高 IVOL 扣分**",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "比裸 60 日波动率更纯的低波异象（已与「60日波动率」并行对比）",
        "priority": "中", "batch": 2,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "60d 滚动 + 12m×5y walk-forward",
    },
    {
        "name": "换手率趋势", "label": "量能因子 TurnTrend(20d/240d)",
        "logic": "20 日均量 ÷ 240 日均量的**时序**变化",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "与已有「异常量比」（20d/240d 的**截面**分位）正交，测时序信息量",
        "priority": "中", "batch": 2,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "20d/240d 比 + 12m×5y walk-forward",
    },
    {
        "name": "隔夜跳空累积", "label": "日内拆分 OvernightMom",
        "logic": "近 20 日隔夜收益（今开 ÷ 昨收）之和",
        "data_source": "kline_cache 现成 ⇒ 就绪（零新数据）",
        "gap": "隔夜与日内收益定价机制不同，可测是否含独立信息",
        "priority": "低", "batch": 3,
        "owner": "阿狸咪(kline_cache)",
        "estimate_loops": "20d 滚动 + 12m×5y walk-forward",
    },
    # ── B 组：需扩财报字段（排在 A 组之后）──
    {
        "name": "Piotroski F-Score", "label": "质量因子 F-Score(9 项)",
        "logic": "盈利/杠杆/流动性/运营 四维共 9 项打分（0~9）",
        "data_source": "需扩财报字段 ⇒ 待抓取（毛利/总资产/经营现金流/负债/营收）",
        "gap": "教科书级质量综合分，可一次补齐本卡「质量维度」多个缺口",
        "priority": "高", "batch": 1,
        "owner": "小九(财报抓取)",
        "estimate_loops": "5y×12m walk-forward",
    },
    {
        "name": "应计质量 Accruals", "label": "质量因子 Accruals",
        "logic": "(净利润 − 经营现金流) ÷ 总资产；**高应计扣分**",
        "data_source": "需扩财报字段 ⇒ 待抓取（净利润/经营现金流/总资产）",
        "gap": "盈利质量检验，与「经营现金流/总资产」互为明暗两面",
        "priority": "高", "batch": 1,
        "owner": "小九(财报抓取)",
        "estimate_loops": "5y×12m walk-forward",
    },
    {
        "name": "资产周转率", "label": "质量因子 AssetTurnover",
        "logic": "营业收入 ÷ 总资产（GPOA 的分解项之一）",
        "data_source": "需扩财报字段 ⇒ 待抓取（营收/总资产）",
        "gap": "GPOA 的先行分项：先单独验证周转率，再合成 GPOA，降低一次上多个因子的风险",
        "priority": "中", "batch": 2,
        "owner": "小九(财报抓取)",
        "estimate_loops": "5y×12m walk-forward",
    },
]


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
            "pool": "audit",                # 来源：主人截图因子表审计（2026-09-09）
            "notes": "等小九 baostock/akshare 数据到位后跑 walk-forward，OOS IR > 0.3 且 4/5 连续 5 年胜率 > 55% 方可上线",
        })

    # ── 合并「待回测候选因子台账」（阿狸咪的工程师 2026-09-15 主人令）──
    #    登记 ≠ 接入：入池只表示「排进回测队列」，回测不达标即从本池删除。
    for c in CANDIDATE_POOL:
        progress.append({
            "name": c["name"],
            "label": c["label"],
            "batch": c["batch"],
            "batch_label": PRIORITY_NOTE.get(c["batch"], "?"),
            "priority": c["priority"],
            "v8_status": "未使用" if c["batch"] != 3 else "部分使用",
            "data_source": c["data_source"],
            "gap": c["gap"],
            "logic": c["logic"],
            "backtest_status": "pending",
            "oos_ir": None,
            "sharpe_oos": None,
            "max_drawdown_oos": None,
            "last_run_at": None,
            "owner": c["owner"],
            "estimate_loops": c["estimate_loops"],
            "deploy_status": "未上线",
            "pool": "candidate",            # 来源：待回测候选台账（2026-09-15 登记）
            "notes": "待回测候选：达标即接入 generate_top10.py；不达标则从台账删除该条",
        })

    # ── 🆕 2026-09-16 主人令：套用 walk-forward 真结果 ──────────────────────
    #    「这些马上回测，不好的不要的就删除，留下可用的优质因子，全部接入。
    #      不要整个版面都在等待，一直也解决不了！」
    #    台账规则 ②（达标⇒done+回填 oos_ir）/ ③（不达标⇒删除该条，不留遗体）。
    wf, wf_time = _load_walkforward()
    print(f"  walk-forward 结果: {len(wf)} 个因子"
          + (f"（{wf_time}）" if wf_time else "（无 —— factor_walkforward.json 缺失）"))
    kept, retired = [], []
    n_done_wf = 0
    for p in progress:
        key = WF_MAP.get(p["name"])
        r = wf.get(key) if key else None
        if not r or not r.get("verdict"):
            kept.append(p)          # 无回测结果 ⇒ 保持 pending（仍待数据/待跑）
            continue
        if r["verdict"] == "PASS":
            p["backtest_status"] = "done"
            p["oos_ir"] = r.get("ir_oos")
            p["sharpe_oos"] = r.get("sharpe_oos")
            p["max_drawdown_oos"] = r.get("max_drawdown_top_pct")
            p["last_run_at"] = wf_time
            p["beat_base_rate"] = r.get("beat_base_rate")
            p["top_win_avg"] = r.get("top_win_avg")
            p["base_win_avg"] = r.get("base_win_avg")
            p["spread_oos_pct"] = r.get("spread_oos_pct")
            p["deploy_status"] = "已达标·待接入 generate_top10.py"
            p["notes"] = (f"✅ walk-forward 达标（{r.get('date_from')}~{r.get('date_to')}，"
                          f"{r.get('n_points')} 个调仓点，hold={r.get('hold')}d）："
                          f"IR_OOS={r.get('ir_oos')} · Top跑赢基准率={r.get('beat_base_rate')}% · "
                          f"Top绝对胜率={r.get('top_win_avg')}%（基准{r.get('base_win_avg')}%）· "
                          f"Top回撤={r.get('max_drawdown_top_pct')}%。")
            kept.append(p)
            n_done_wf += 1
        else:
            # ③ 不达标 ⇒ 从台账删除，不留遗体（仅在 summary 里留一条汇总备忘）
            retired.append({
                "name": p["name"], "pool": p.get("pool", "?"),
                "ir_oos": r.get("ir_oos"), "beat_base_rate": r.get("beat_base_rate"),
                "top_win_avg": r.get("top_win_avg"), "base_win_avg": r.get("base_win_avg"),
                "spread_oos_pct": r.get("spread_oos_pct"),
            })
    progress = kept
    print(f"  ⇒ 达标 done {n_done_wf} 个 · 不达标删除 {len(retired)} 个 · 仍 pending {len(progress) - n_done_wf} 个")

    # 全局进度汇总
    n_total = len(progress)
    n_pending = sum(1 for p in progress if p["backtest_status"] == "pending")
    n_done = sum(1 for p in progress if p["backtest_status"] == "done")
    n_audit = sum(1 for p in progress if p.get("pool") == "audit")
    n_cand = sum(1 for p in progress if p.get("pool") == "candidate")
    batch_done = {}
    for p in progress:
        b = p["batch"]
        batch_done.setdefault(b, {"total": 0, "pending": 0, "done": 0})
        batch_done[b]["total"] += 1
        batch_done[b][p["backtest_status"]] += 1

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_update_time": d.get("update_time", "?"),
        "policy": ("主人 2026-09-09 22:31 决策：分批 walk-forward，禁止直接硬编码高分；"
                   "OOS IR > 0.3 且 4/5 年胜率 > 55% 方可上线。"
                   "主人 2026-09-15 07:33 令：本表即「待回测候选因子台账」——"
                   "准备回测/准备追加的因子一律先登记在此（备忘），"
                   "回测达标则接入、不达标则从台账删除该条（不留遗体）。"),
        "summary": {
            "total": n_total,
            "pending": n_pending,
            "done": n_done,
            "from_audit": n_audit,          # 主人截图因子表（2026-09-09）
            "from_candidate": n_cand,       # 待回测候选台账（2026-09-15）
            "batches": batch_done,
            # 🆕 2026-09-16 walk-forward 实跑归因（可审计）
            "walkforward_run_at": wf_time,
            "walkforward_done": n_done_wf,
            "walkforward_retired": len(retired),
            "retired_by_backtest": retired,   # 不达标被删的条目（仅汇总备忘，不留 pending 遗体）
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
