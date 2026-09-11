#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_backtest_all_algos.py — 全算法回测汇总（**按前端卡名**）

2026-09-11 主人令：「策略回测页的逻辑也要跟上，在每日最终推荐出来后，开始回测所有算法，
按前端卡名都写出来，真实回测，不得造假！杜绝一切假成功！按收益率和胜率，从高到低排序，
回测累积到一定时间，收益率和胜率低的要提醒我是否要下架不再跟踪。」

本脚本把散落在各处的**真实回测产物**聚合成单一来源，供前端「策略回测」页读取。

【设计铁律 · 不得造假】
  1. **未知一律 null，绝不用 0 冒充**。0 是「真实算出来就是 0」，null 是「没算/没样本」；
     二者在前端分别渲染为 `0.00%` 与 `—`。历史上 FOUR_VOLUME_BACKTEST 的 best/worst
     因键名不匹配被静默填 0，正是本铁律要根治的形态。
  2. **不把不可比的口径硬塞进同一排名**。交易型（有买卖价、可算胜率/收益）与
     研究型（因子分层超额，无逐笔买卖）分列 `cat`，排名只含交易型。
  3. **不遗漏、不隐瞒**。源文件缺失/陈旧/样本不足 → 该行照常列出，标 `status`，
     让缺口可见；绝不因为「数字不好看」而不列。

【与闸门同源】数据日与新鲜度判据**完全复用** `.github/scripts/v8_stage_gate.py`
  的 `chain_day()` / `FLOOR_TRADING=(16,30)` / `FLOOR_T1=(8,0)` / `_NIGHT_CUT=9`
  与「凌晨 00:00-08:59 归前一自然日 24:xx」的候选展开。**禁止在本文件另立一套口径**
  （两套口径必然漂移 —— 历史教训）。

输出：
  - raw_data/backtest_all_algos.json   （数据本体）
  - data/BACKTEST_ALL_ALGOS.js         （前端产物 window.BACKTEST_ALL_ALGOS）

用法：
  python algorithms/gen_backtest_all_algos.py
  python algorithms/gen_backtest_all_algos.py --dry          # 只打印不写文件
  python algorithms/gen_backtest_all_algos.py --today 2026-09-12 --kind t1   # 演练
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = ROOT / "raw_data"

# ── 阈值（主人可调；改这里即可，前端声明与实际同源由「页面口径」小节保证）──
MIN_SAMPLES = 30          # 累积样本门槛：低于此只观测、不进排名、不评估下架（= 前端既有 MIN=30）
# 🔴 2026-09-12 主人令（拍板第 1 项·①）：各回测脚本持有期已扩为
#   [1, 3] + [5,10,20,30,45,60,75,90]（同源常量 HOLD_LADDER，见各脚本）。
#   ⚠️ 本脚本的**主口径刻意仍取 T+5**（各 src 的 primary 字段）：
#     主表是「同口径横比」，T+5 是各卡唯一共同拥有的短档，样本最厚、可比性最强；
#     若改 T+90，则① 长档样本天然薄（回测区间早期信号凑不满 90 日）
#     ② 各卡主口径可能取到不同档 ⇒ 横比失去意义。
#     长档（30/45/60/75/90）全部照常进 ranking_all 明细表 + 前端分档视图，
#     主人要的「从近到远慢慢跟踪」由明细表 + track_ladder 承担，不由主表承担。
LOW_WIN_RATE = 45.0       # 胜率红线：低于此判「低胜率」
LOW_AVG_RETURN = 0.0      # 平均收益红线：<= 此判「低收益」（已扣成本口径）

_NIGHT_CUT = 9            # 与闸门 _NIGHT_CUT / _NEXT_DAY_CUTOFF_HOUR / _NIGHT_CUT_HOUR 同源
FLOOR_TRADING = (16, 30)  # 与闸门 FLOOR_TRADING 同源
FLOOR_T1 = (8, 0)         # 与闸门 FLOOR_T1 同源

# ── 源登记表：**card = 前端卡名**（权威出处 index.html 的 V8_PAGE_SCHEDULE + 策略回测页）──
SOURCES = [
    dict(card="三重共识", page="选股策略", icon="🧲", cat="trade",
         var="BACKTEST_COMPREHENSIVE", rel="data/BACKTEST_COMPREHENSIVE.js",
         parser="comprehensive", label_prefix="共振", primary="共振≥80（严格）",
         method="baostock 真实收盘价（前复权·扣双边 0.3%）"),
    dict(card="四量终极", page="选股策略", icon="📊", cat="trade",
         var="FOUR_VOLUME_BACKTEST", rel="data/FOUR_VOLUME_BACKTEST.js",
         parser="by_period", label_prefix="持有", primary="持有 T+5",
         method="信号日收盘价买入、持有 N 个真实交易日收盘价卖出（前复权·扣双边 0.3%）"),
    dict(card="逆势龙头", page="选股策略", icon="🐉", cat="trade",
         var="CRDS_BACKTEST", rel="data/CRDS_BACKTEST.js",
         parser="by_period", label_prefix="持有", primary="持有 T+5",
         method="信号日次一交易日开盘买入、持有 N 日收盘卖出（前复权·扣双边 0.3%）"),
    dict(card="相对强度", page="选股策略", icon="📐", cat="trade",
         var="RPS_BACKTEST", rel="data/RPS_BACKTEST.js",
         parser="by_period", label_prefix="持有", primary="持有 T+5",
         method="RPS A档：次一交易日开盘买入、持有 N 日收盘卖出（前复权·扣双边 0.3%）",
         chain_member=False,
         chain_note="该源**不在盘后算法链内**（v8_health_check 登记为 manual_dep），新鲜度无保证"),
    dict(card="强势突破", page="暂未上架", icon="🚀", cat="trade",
         var="ALGO_BACKTEST_COMPARE", rel="data/ALGO_BACKTEST_COMPARE.js",
         parser="algo_compare", label_prefix="", primary=None,
         method="实盘入选样本同口径聚合（T+1~T+10 前向收益）",
         chain_member=False,
         chain_note="生成脚本 scripts/algo_backtest_compare.py 原为孤儿（未挂 STAGES）"),
    dict(card="K线信号层", page="策略回测", icon="📈", cat="signal",
         var="BACKTEST_TDX", rel="data/BACKTEST_TDX.js",
         parser="tdx", label_prefix="", primary=None,
         method="9 类 K 线信号 60 日前向回测（前复权）"),
    dict(card="因子实验室", page="暂未上架", icon="🧪", cat="research",
         var="FACTOR_LAB_BACKTEST", rel="data/FACTOR_LAB_BACKTEST.js",
         parser="factor_lab", label_prefix="", primary=None,
         method="因子五分位分层超额（每10交易日调仓·次一交易日开盘入场）"),
]

_UT_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})')
_DT_ONLY_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})')
_DATE_RE = re.compile(r'"data_date"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')


# ────────────────────────────── 基础工具 ──────────────────────────────
def now_cst():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return dt.datetime.utcnow() + dt.timedelta(hours=8)


def read_ut(root, rel):
    """读产物时间 → (YYYY-MM-DD, hh, mm)。**与闸门 read_ut 逐字同源**（仅日期 → 23:59）。"""
    path = os.path.join(root, rel)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(20000)
    except OSError:
        return None
    m = _UT_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", int(m.group(4)), int(m.group(5))
    m = _DT_ONLY_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 23, 59
    m = _DATE_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 23, 59
    return None


def _cand(r):
    """候选解释：原样 +（hh < _NIGHT_CUT 时）归前一自然日的 24:xx。**与闸门 _cand 同源**。"""
    out = [(r[0], r[1], r[2])]
    if r[1] < _NIGHT_CUT:
        d = dt.date.fromisoformat(r[0]) - dt.timedelta(days=1)
        out.append((d.strftime("%Y-%m-%d"), r[1] + 24, r[2]))
    return out


def judge_fresh(root, rel, day, kind):
    """产物是否「算数据日 day 的」：与闸门 check_ready 同口径（日期==day 且时刻 >= floor）。"""
    r = read_ut(root, rel)
    if r is None:
        return False, None
    floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
    for c in _cand(r):
        if c[0] == day and (c[1], c[2]) >= floor:
            return True, r
    return False, r


def load_js_var(rel):
    """解析 data/*.js 的 window.X = {...};（含等号两侧空格差异）。失败返回 (None, 原因)。"""
    p = DATA / Path(rel).name
    if not p.exists():
        return None, "文件不存在"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return None, f"读取失败 {e.__class__.__name__}"
    m = re.search(r"window\.[A-Za-z_0-9]+\s*=\s*(\{.*\})\s*;?\s*$", text, re.S)
    if not m:
        return None, "未匹配到 window.X = {...}"
    try:
        return json.loads(m.group(1)), None
    except Exception as e:
        return None, f"JSON 解析失败 {e.__class__.__name__}"


def _num(v):
    """数值归一：None/空串/NaN → None（**绝不用 0 冒充**）；数字原样。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int(v):
    """样本数归一为 int；未知 → None（**绝不用 0 冒充**）。"""
    f = _num(v)
    return None if f is None else int(round(f))


def _resolve_chain(day_arg, kind_arg):
    """取 (数据日, 类型)。**复用闸门 chain_day**；闸门不可用时降级并在输出里显式标注。"""
    if day_arg:
        d = dt.date.fromisoformat(day_arg)
        return d.strftime("%Y-%m-%d"), (kind_arg or "trading"), "命令行指定"
    gate = ROOT / ".github" / "scripts" / "v8_stage_gate.py"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_v8_stage_gate", str(gate))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d, kind, note = mod.chain_day(now_cst().date())
        if d is None:
            return now_cst().date().strftime("%Y-%m-%d"), "none", f"闸门判定 {note}"
        return d.strftime("%Y-%m-%d"), kind, f"闸门 chain_day：{note}"
    except Exception as e:
        # 降级必须**可见**，不得静默（否则口径漂移无人知）
        d = now_cst().date()
        return d.strftime("%Y-%m-%d"), "trading", f"⚠️ 闸门不可用({e.__class__.__name__})，降级为「今天=交易日」"


# ────────────────────────────── 各源解析器 ──────────────────────────────
def _mk_row(src, label, sample, win_rate, avg_return, hold, extra=None, status=None,
            primary=None, card=None):
    return {
        "card": card or src["card"], "page": src["page"], "icon": src["icon"], "cat": src["cat"],
        "label": label, "source_var": src["var"], "source_file": src["rel"],
        "hold": hold, "sample": _int(sample),
        "win_rate": _num(win_rate), "avg_return": _num(avg_return),
        "extra": extra or {}, "status": status, "method": src.get("method", ""),
        "_primary_override": primary,
    }


def parse_comprehensive(src, obj):
    """BACKTEST_COMPREHENSIVE：共振三档，每档取「最佳持有期」为主口径。"""
    rows = []
    ov = (obj or {}).get("overview") or {}
    band = [("resonance_all", "共振≥2（宽松）"), ("resonance_gte70_lt80", "共振70-79分"),
            ("resonance_gte80", "共振≥80（严格）")]
    for key, name in band:
        o = ov.get(key)
        if not isinstance(o, dict) or o.get("best_win_rate") is None:
            rows.append(_mk_row(src, name, None, None, None, None,
                                status="该分档无有效样本"))
            continue
        hd = o.get("best_hold_days")
        per = (o.get("periods") or {}).get(f"hold_{hd}d") or {}
        rows.append(_mk_row(
            src, name, o.get("valid", o.get("total")),
            o.get("best_win_rate"), o.get("best_avg_return"),
            f"T+{hd}" if hd else None,
            extra={"best_return": _num(per.get("best_return")),
                   "worst_return": _num(per.get("worst_return")),
                   "max_drawdown": _num(per.get("max_drawdown")),
                   "sharpe": _num(per.get("sharpe_ratio")),
                   "median_return": _num(per.get("median_return"))},
        ))
    return rows


def parse_by_period(src, obj):
    """summary.by_period：四量/CRDS/RPS 同构。每个持有期一行（主人要按收益/胜率排序）。"""
    sm = (obj or {}).get("summary") or {}
    bp = sm.get("by_period") or {}
    rows = []
    if not bp:
        return [_mk_row(src, "—", None, None, None, None, status="无 by_period 数据")]
    for k in sorted(bp.keys(), key=lambda x: (_num(x) is None, _num(x) or 0)):
        r = bp.get(k) or {}
        n = _num(r.get("samples"))
        if n is None:
            n = _num(r.get("count"))
        rows.append(_mk_row(
            src, f"持有 T+{k}", n, r.get("win_rate"), r.get("avg_return"), f"T+{k}",
            extra={"best_return": _num(r.get("best_return")),
                   "worst_return": _num(r.get("worst_return")),
                   "max_drawdown": _num(r.get("max_drawdown")),
                   "sharpe": _num(r.get("sharpe_ratio")),
                   "win_avg": _num(r.get("win_avg")), "loss_avg": _num(r.get("loss_avg")),
                   "signal_date_range": sm.get("signal_date_range")},
            status=None if (n or 0) > 0 else "样本为 0（尚无历史信号）",
        ))
    return rows


def parse_tdx(src, obj):
    """BACKTEST_TDX.summary：每类 K 线信号一行，主口径 T+1、副口径 T+5。"""
    sm = (obj or {}).get("summary") or {}
    rows = []
    if not sm:
        return [_mk_row(src, "—", None, None, None, None, status="无 summary 数据")]
    for k, v in sm.items():
        if not isinstance(v, dict):
            continue
        rows.append(_mk_row(
            src, (v.get("label") or k), _num(v.get("total")),
            v.get("win_rate_1d"), v.get("avg_return_1d"), "T+1",
            extra={"win_rate_5d": _num(v.get("win_rate_5d")),
                   "avg_return_5d": _num(v.get("avg_return_5d")),
                   "win_rate_3d": _num(v.get("win_rate_3d")),
                   "avg_return_3d": _num(v.get("avg_return_3d"))},
        ))
    return rows


def parse_algo_compare(src, obj):
    """ALGO_BACKTEST_COMPARE：多算法同口径聚合，取 T+5 为主口径。"""
    rows = []
    algos = (obj or {}).get("algos") or (obj or {}).get("results") or {}
    if isinstance(algos, dict):
        items = algos.items()
    elif isinstance(algos, list):
        items = [(a.get("key") or a.get("algo") or "", a) for a in algos]
    else:
        items = []
    for k, a in items:
        if not isinstance(a, dict):
            continue
        hs = (a.get("horizons") or {})
        t5 = hs.get("t5") or {}
        rows.append(_mk_row(
            src, (a.get("name") or a.get("display_name") or k), _num(a.get("n_samples")),
            t5.get("win"), t5.get("avg"), "T+5",
            extra={"hit": _num(t5.get("hit"))},
            status=None if _num(a.get("n_samples")) else "暂无足够可比历史（等待盘后累积）",
            # 本产物聚合多个算法；只有「强势突破」那一行属于本卡，其余留给其自身卡位
            primary=("强势" in str(a.get("name") or a.get("display_name") or k)),
        ))
    if not rows:
        return [_mk_row(src, "—", None, None, None, None,
                        status="产物无可用算法行（等待盘后累积）")]
    return rows


def parse_factor_lab(src, obj):
    """FACTOR_LAB_BACKTEST：研究型分层超额，**不产出交易型胜率/收益率**。

    诚实处理：把可比的「样本内/样本外超额」与「分层胜率」如实列出，`cat=research`
    使其**不进入交易型排名**（硬塞进同一排名就是造假）。
    """
    rows = []
    av = (obj or {}).get("abnormal_volume") or {}
    if av:
        rows.append(_mk_row(
            src, "异常放量·分层价差", _num(av.get("n_points")),
            av.get("top_layer_win_10d"), av.get("spread_oos_pct"), "T+10 价差",
            extra={"spread_in_sample_pct": _num(av.get("spread_in_sample_pct")),
                   "spread_top_bottom_10d_pct": _num(av.get("spread_top_bottom_10d_pct")),
                   "universe_n": _num(av.get("universe_n")),
                   "verdict": av.get("verdict_note") or av.get("verdict_3star")},
            status="研究型：值为「分层价差%」非「平均收益%」，不与交易型同列排名",
        ))
    roe = (obj or {}).get("roe_largecap") or {}
    if roe:
        rows.append(_mk_row(
            src, "大盘ROE·TOP30超额", _num(roe.get("top30_n")),
            roe.get("top30_win_5d"), roe.get("excess_5d"), "T+5 超额",
            extra={"top30_avg_5d": _num(roe.get("top30_avg_5d")),
                   "univ_avg_5d": _num(roe.get("univ_avg_5d")),
                   "excess_10d": _num(roe.get("excess_10d")),
                   "excess_20d": _num(roe.get("excess_20d"))},
            status="研究型：值为「相对全池超额%」非「平均收益%」，不与交易型同列排名",
        ))
    if not rows:
        return [_mk_row(src, "—", None, None, None, None, status="无分层回测数据")]
    return rows


PARSERS = {
    "comprehensive": parse_comprehensive,
    "by_period": parse_by_period,
    "tdx": parse_tdx,
    "algo_compare": parse_algo_compare,
    "factor_lab": parse_factor_lab,
}


# ────────────────────────────── 主流程 ──────────────────────────────
def _is_low(r):
    """是否为「低绩效」：胜率或平均收益低于红线。返回原因列表（空 = 不低）。"""
    out = []
    wr, ar = r.get("win_rate"), r.get("avg_return")
    if wr is not None and wr < LOW_WIN_RATE:
        out.append(f"胜率 {wr}% < 红线 {LOW_WIN_RATE}%")
    if ar is not None and ar <= LOW_AVG_RETURN:
        out.append(f"平均收益 {ar}% ≤ 红线 {LOW_AVG_RETURN}%（已扣成本）")
    return out


def build(root, day, kind, note, extra_note=""):
    rows = []
    for src in SOURCES:
        obj, err = load_js_var(src["rel"])
        fresh, ut = judge_fresh(root, src["rel"], day, kind)
        if obj is None:
            parsed = [_mk_row(src, "—", None, None, None, None,
                              status=f"源不可读（{err}）")]
        else:
            parsed = PARSERS[src["parser"]](src, obj)
        for r in parsed:
            r["source_time"] = (f"{ut[0]} {ut[1]:02d}:{ut[2]:02d}" if ut else None)
            r["fresh"] = bool(fresh)
            r["chain_member"] = src.get("chain_member", True)
            r["chain_note"] = src.get("chain_note")
            if not fresh:
                # 陈旧 ≠ 数字错：陈旧的是「批次」。数值照实保留，只加状态标注（不隐藏）
                r["status"] = (r["status"] + "；" if r["status"] else "") + \
                    f"源未在数据日 {day} 刷新（最后 {r['source_time'] or '未知'}）"
            ov = r.pop("_primary_override", None)
            r["is_primary"] = bool(ov) if ov is not None else (r["label"] == src.get("primary"))
            rows.append(r)

    # ── 卡级主表（主人要的「按收益率和胜率从高到低排序」）──
    #   🔴 诚实性铁律①：**只比同口径**。主表每张卡只取 1 行「既定主口径」，
    #      绝不把 T+1 与 T+20 放进同一张表比大小（持有期不同，横比即误导）。
    #   🔴 诚实性铁律②：**累积样本不足不排名**。逆势龙头曾以 n=4 / 胜率 100% 排在
    #      样本 1415 的四量之上 —— 这是小样本噪声顶掉真实强度，正是主人说的
    #      「回测累积到一定时间」才评估。未达 MIN_SAMPLES 的主口径行进 `insufficient`。
    primary = [r for r in rows if r.get("is_primary") and r["cat"] == "trade"]
    eligible = [r for r in primary if (r["sample"] or 0) >= MIN_SAMPLES and r["win_rate"] is not None]
    insufficient = [r for r in primary if r not in eligible]
    ranked = sorted(eligible, key=lambda r: (-(r["win_rate"] if r["win_rate"] is not None else -999),
                                            -(r["avg_return"] if r["avg_return"] is not None else -999)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    for r in insufficient:
        r["rank"] = None
        r["status"] = (r["status"] + "；" if r["status"] else "") + \
            f"样本 {(r['sample'] or 0)} < 门槛 {MIN_SAMPLES} → 累积中，不进主表排名"

    # ── 全量明细排序（同为「胜率降序 → 平均收益降序」，与星级对比表同口径）──
    allowed = [r for r in rows
               if r["cat"] in ("trade", "signal") and (r["sample"] or 0) >= MIN_SAMPLES
               and r["win_rate"] is not None]
    ranking_all = sorted(allowed, key=lambda r: (-(r["win_rate"] or 0), -(r["avg_return"] or -999)))

    # ── 下架建议（**卡级**：一卡一条，且只在链内 + 累积样本达标时才提）──
    advice, watch = [], []
    for r in primary:
        n = r["sample"] or 0
        reasons = _is_low(r)
        if not reasons:
            continue
        entry = {
            "card": r["card"], "label": r["label"], "icon": r["icon"], "rank": r.get("rank"),
            "sample": n, "win_rate": r["win_rate"], "avg_return": r["avg_return"],
            "win_rate_5d": (r.get("extra") or {}).get("win_rate_5d"),
            "reasons": reasons,
            "source_time": r.get("source_time"), "fresh": r.get("fresh"),
        }
        if not r.get("chain_member"):
            # 源不在算法链内 → 数据可能残缺，**不可据此提议下架**（先修产出再评估）
            entry["note"] = r.get("chain_note") or "该源不在盘后算法链内"
            watch.append(entry)
        elif n < MIN_SAMPLES:
            entry["note"] = f"样本 {n} < 门槛 {MIN_SAMPLES}，累积不足，仅观察"
            watch.append(entry)
        else:
            entry["ask"] = f"是否下架「{r['card']}」并停止跟踪？"
            advice.append(entry)
    advice.sort(key=lambda a: (a["win_rate"] if a["win_rate"] is not None else 999))
    watch.sort(key=lambda a: -(a["sample"] or 0))

    # ── 分档提示（不构成下架问题，只如实说明）──
    #   🔴 仅当该卡**主口径本身不低**时才加此注；否则主口径已被 advice/watch 覆盖，
    #      再写「主口径不弱」就是自相矛盾（实测踩到：相对强度主口径 T+5 仅 19.44%）。
    notes = []
    for src in SOURCES:
        if not src.get("primary"):
            continue      # 无既定主口径的源（信号层/研究型）不产生「主口径不弱」这类空话
        prim = [r for r in rows if r["card"] == src["card"] and r.get("is_primary")]
        if not prim or _is_low(prim[0]):
            continue
        bands = [r for r in rows if r["card"] == src["card"] and not r.get("is_primary")
                 and r["label"] != "—"]
        weak = [b for b in bands if _is_low(b) and (b["sample"] or 0) >= MIN_SAMPLES]
        if weak:
            notes.append({
                "card": src["card"],
                "text": ("同卡其他分档表现偏弱（不作为下架依据，因为该卡主口径 "
                         f"「{src.get('primary')}」不弱）：" +
                         "；".join(f"{b['label']} 胜率 {b['win_rate']}% / 收益 {b['avg_return']}%"
                                   for b in weak)),
            })

    return {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "data_day": day,
        "chain_kind": kind,
        "chain_note": note + (("；" + extra_note) if extra_note else ""),
        "min_samples": MIN_SAMPLES,
        "low_win_rate": LOW_WIN_RATE,
        "low_avg_return": LOW_AVG_RETURN,
        "sort_rule": "胜率降序 → 平局看平均收益降序（与页内星级对比表同口径）",
        "primary_rule": ("卡级主表每卡只取 1 行既定主口径（三重共识＝共振≥80 严格；"
                         "四量/逆势/相对强度＝T+5；强势突破＝T+5），**不跨持有期横比**；"
                         f"且**样本 < {MIN_SAMPLES} 不进主表**（累积不足不排名）。"),
        "honesty_note": ("未知一律 null（前端显示 —），绝不用 0 冒充；"
                         f"样本< {MIN_SAMPLES} 只观测、不进排名、不做下架评估；"
                         "研究型（因子分层）不与交易型同列比较；"
                         "源不在算法链内的，只入观察名单、不提议下架。"),
        "rows": rows,
        "ranking": ranked,
        "ranking_all": ranking_all,
        "insufficient": insufficient,
        "delist_advice": advice,
        "watch_list": watch,
        "band_notes": notes,
        "coverage": _coverage(rows),
    }


def _coverage(rows):
    """按前端卡名给覆盖面结论 —— 缺口必须可见，不得静默。"""
    seen = {}
    for r in rows:
        c = seen.setdefault(r["card"], {"card": r["card"], "page": r["page"],
                                        "cat": r["cat"], "labels": 0,
                                        "has_sample": False, "fresh": False})
        c["labels"] += 1
        if (r["sample"] or 0) > 0:
            c["has_sample"] = True
        if r.get("fresh"):
            c["fresh"] = True
    out = []
    for c in seen.values():
        if c["has_sample"] and c["fresh"]:
            st = "✅ 有真实样本且本数据日已刷新"
        elif c["has_sample"]:
            st = "🟡 有真实样本，但源未在本数据日刷新"
        else:
            st = "⚪ 产物存在但样本为 0（累积中）"
        c["status"] = st
        out.append(c)
    # 已知无回测产物的算法卡（**如实列出，不用编造数字填补**）
    known_gaps = [
        {"card": "候选池", "page": "选股策略", "status": "⚪ 无独立前向收益回测（仅 V8_POOL_TRACKER 跟踪池，可算浮动盈亏）"},
        {"card": "黄金池", "page": "选股策略", "status": "⚪ 无独立前向收益回测"},
        {"card": "机游共振", "page": "盘后数据", "status": "⚪ 无独立前向收益回测"},
    ]
    have = {c["card"] for c in out}
    for g in known_gaps:
        if g["card"] not in have:
            out.append(g)
    return out


def build_ladder(root):
    """跟踪池分档阶梯（从近到远 T+5…T+90）—— 读 raw_data/algo_track.json。

    🔴 与「历史回测」是两个不同口径，**不混进卡级排名**：
      · 历史回测（backtest_*）= 对历史信号做固定持有期回溯；
      · 本阶梯 = **逐日现采前向跟踪**：信号日入场 → 真实持有到第 h 个交易日收盘。
    口径由 gen_algo_track.py 产出（只取 raw_data/kline_cache 真实日线、扣双边 0.3%），
    累积多少个交易日就出多少个档位，**不必等 90 天期满**（主人 2026-09-11 令）。
    未就绪档位 samples=0 且 win_rate/avg_return 为 null —— 前端显示「累积中」，
    绝不把「没样本」画成「0% 胜率」。
    """
    p = Path(root) / "raw_data" / "algo_track.json"
    if not p.exists():
        return {"available": False, "reason": "raw_data/algo_track.json 不存在"}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"available": False, "reason": f"raw_data/algo_track.json 不可读: {e.__class__.__name__}"}
    out = {
        "available": True,
        "update_time": obj.get("update_time"),
        "horizons": obj.get("horizons") or [],
        "cost_pct_roundtrip": obj.get("cost_pct_roundtrip"),
        "note": ("逐日现采前向跟踪（非历史回溯）：入场=信号日收盘，持有到第 h 个真实"
                 "交易日收盘，扣双边成本；样本随交易日自然累积，不必等 90 天期满。"
                 "samples=0 的档位=样本未成熟，不是 0% 胜率。"),
        "algos": [],
    }
    for a in obj.get("algos", []) or []:
        st = a.get("stats") or {}
        out["algos"].append({
            "algo": a.get("algo"),
            "display_name": a.get("display_name"),
            "tracking": st.get("tracking"),
            "history_samples": st.get("history_samples"),
            "coverage": st.get("coverage"),
            "by_horizon": st.get("by_horizon") or {},
            "unrealized": a.get("unrealized") or [],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--today", default=None, help="演练：指定数据日 YYYY-MM-DD")
    ap.add_argument("--kind", default=None, choices=["trading", "t1", "none"])
    ap.add_argument("--dry", action="store_true", help="只打印，不写文件")
    a = ap.parse_args()

    root = a.root
    day, kind, note = _resolve_chain(a.today, a.kind)
    print(f"[gen_backtest_all_algos] {now_cst():%Y-%m-%d %H:%M:%S}")
    print(f"  数据日={day}  类型={kind}  依据={note}")

    if kind == "none":
        # 休市日不产「当日」结论，避免把非交易日刷成数据日（与闸门 NONE 同义）
        print("  ⏭ 闸门判 NONE（休市）→ 本脚本不写产物（避免刷新非交易日数据日）")
        return 0

    out = build(root, day, kind, note)
    out["track_ladder"] = build_ladder(root)

    print(f"  覆盖 {len(out['rows'])} 行 / {len(out['coverage'])} 张卡")
    for r in out["rows"]:
        mark = "✅" if r.get("fresh") else "🟡"
        star = "★" if r.get("is_primary") else " "
        print(f"    {mark}{star} [{r['cat']:8s}] {r['card']}·{r['label']}: "
              f"n={r['sample']} wr={r['win_rate']} ar={r['avg_return']} "
              f"src={r['source_time']}" + (f"  ⚠ {r['status']}" if r.get("status") else ""))
    print(f"  ★ 卡级主表（同口径横比，胜率降序）：")
    for r in out["ranking"]:
        print(f"    #{r['rank']} {r['card']}·{r['label']}  胜率 {r['win_rate']}%  "
              f"平均收益 {r['avg_return']}%  n={r['sample']}")
    if not out["ranking"]:
        print("    （无达标行）")
    if out["insufficient"]:
        print(f"  累积中（样本<{MIN_SAMPLES}，不进主表）：")
        for r in out["insufficient"]:
            print(f"    … {r['card']}·{r['label']}  n={r['sample']}  "
                  f"胜率 {r['win_rate']}%（小样本，不排名）")
    print(f"  全量明细达标行 {len(out['ranking_all'])} 条（含各持有期/各分档）")
    print(f"  🔔 下架建议（卡级·累积样本≥{MIN_SAMPLES}·且源在链内）{len(out['delist_advice'])} 条：")
    for ad in out["delist_advice"]:
        print(f"    ⚠️ {ad['card']} → {'；'.join(ad['reasons'])}（n={ad['sample']}）")
    if not out["delist_advice"]:
        print("    （无低绩效达标策略）")
    print(f"  👀 观察名单（不提议下架）{len(out['watch_list'])} 条：")
    for w in out["watch_list"]:
        print(f"    • {w['card']} → {'；'.join(w['reasons'])}（n={w['sample']}）｜{w.get('note','')}")
    for b in out["band_notes"]:
        print(f"  ℹ️ {b['card']}: {b['text']}")

    if a.dry:
        print("  --dry：不写文件")
        return 0

    (RAW / "backtest_all_algos.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (DATA / "BACKTEST_ALL_ALGOS.js").write_text(
        "/* 全算法回测汇总（按前端卡名）— gen_backtest_all_algos.py 于 E 批产出 */\n"
        "window.BACKTEST_ALL_ALGOS = " + json.dumps(out, ensure_ascii=False) + ";\n",
        encoding="utf-8", newline="\n")
    print("  ✅ 写出 raw_data/backtest_all_algos.json + data/BACKTEST_ALL_ALGOS.js")
    return 0


if __name__ == "__main__":
    # 🛡 云端算法链统一护栏（与 gen_algo_track / backtest_* 同约定）：
    #   算法一律云端跑，本地手跑退出 2 —— 避免本机脏工作树产出「假新鲜」回测。
    #   本地演练请用 run_algorithms.py 的演练开关，勿绕过。
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from utils.time_gate import check_cloud_only
        if not check_cloud_only("algorithms/gen_backtest_all_algos.py"):
            sys.exit(2)
    except ImportError as e:
        print(f"  ⚠️ 云端护栏不可用（{e}）——继续执行")
    sys.exit(main())
