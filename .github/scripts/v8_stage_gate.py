#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 批次闸门（唯一决策点）—— 2026-09-10 主人令「一劳永逸·简化优化·不缺档·不抢跑」

■ 这个脚本解决什么（09-10 事故根因，两条都实测过）
  ① 旧逻辑按 CST 小时「盲猜」批次（16/17→A 18/19→B 20→D 21→E），
     21:00 的 E(回测) 触发时完全不管 B(选股)/D(汇总) 跑没跑，拿凌晨陈旧数据跑回测
     → 「最终推荐被回退」；查得 A/B/D 三批当日从未真跑。
  ② 更深一层：本仓库 GitHub Actions 的 schedule(cron) 实测约 95% 不触发
     （09-10 全天 v8_algo_cloud 14 个 run 里 13 个是 workflow_dispatch，
       intraday_snapshot 应 42 次只触发 1 次）。所以「哪天跑、跑哪批」绝不能靠钟点，
     只能靠**产物内容**判定。

■ 本脚本 = 唯一决策点（替代：按小时盲猜 / 静默闸门V5 / 探针路由 三层历史设计）
  1) 先定「今天该不该跑、跑哪个数据日」——用统一交易日历 v8_date：
       交易日            → 数据日=今天，盘后产出须 >= 16:30
       周六 / 假期首日    → T+1 数据日，当日 08:00 后即可
       周日 / 假期中末段  → NONE（休市，无 T+1）
       凌晨(00:00-08:59) → 归前一自然日（夜间补跑窗口，允许继续跑未完的批）
  2) 再「缺什么跑什么」（**纯内容级**，不吃 git checkout 的 mtime）：
       A 未就绪            → A
       A 就绪 且 B 未就绪   → B
       B 就绪 且 D 未就绪   → D
       D 就绪 且 E 未就绪   → E
       全就绪 / 未到起点    → NONE（空转=真成功，不是假成功）
     说明：删掉了旧版每批各自的 MIN_HOUR(16/18/20/21)。
      那套钟点阈值有两个毛病 ——
        (a) 凌晨 eff_hour 归 0 → 00:30 接力档恒判 NONE，B 若 22:30 后才完，
            D/E 当晚**永远补不上**（漏档实锤）；
        (b) 与内容级就绪重复，A 已新鲜还硬等 18 点，纯拖延。
      现在只保留「盘后链起点」一个时间闸（交易日 16:00 / T+1 日 08:00），
      批次推进完全由上游产物说了算 —— 数据到了就跑，没到就不跑。
  3) 上游未就绪 → stage_ok=false → 调用方**必须红灯 + 拒绝执行 + 紧急报告**
     （主人令「发现前面是错的，就该退回拒绝之后的执行并紧急报告」）。

■ 就绪判据（READY_SPEC）
  A 采集批：龙虎榜(必) + 板块相对强度 + 个股档案  → 交易日期望 3/3 且龙虎榜必新
  B 选股批：三重共识 / 四量终极 / 逆势龙头卡        → 3/3
  D 汇总批：最终推荐                              → 1/1
  E 回测批：CRDS 回测 / TDX 回测                   → 任一即可
  「今日盘后」= update_time 的日期==数据日 且 (时:分) >= 该日门槛。

■ 用法
  python .github/scripts/v8_stage_gate.py --root .                        # 自动
  python .github/scripts/v8_stage_gate.py --root . --explicit-stage B      # 人工指定(仍过上游闸门)
  python .github/scripts/v8_stage_gate.py --root . --force                 # 忽略时间门控(周末审计补跑)
  python .github/scripts/v8_stage_gate.py --root . --hour 22 --today 2026-09-10  # 本地演练

■ 输出（stdout key=value，供 $GITHUB_OUTPUT 消费）
  target_stage=A|B|D|E|ALL|NONE

■ 跨批顺序（2026-09-10 加严，实测两缺陷后修）
  下游最新产物 必须 ≥ 上游基准产物（SEQ_REF），否则判未就绪 → 重算。
  产物时间戳含「凌晨 00:00-05:59 归前一自然日 24:xx」的候选解释（防凌晨死循环）。
  stage_ok=true|false
  proceed=true|false            ← 后续步骤只看这一个值
  chain_day=YYYY-MM-DD|none      chain_kind=trading|t1|none
  today / cst_hour / reason / ready_A..E / detail
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
v8_date = None
try:
    import v8_date  # 统一交易日历（内部复用 fetch_lhb 的日历缓存）
except Exception:
    pass


def _ensure_v8_date(root: str) -> None:
    """确保能从 --root（仓库根）导入 v8_date；导入失败时退回「周一~周五」保守日历。"""
    global v8_date
    if v8_date is not None:
        return
    try:
        ra = os.path.abspath(root)
        if ra not in sys.path:
            sys.path.insert(0, ra)
        import v8_date as _vd  # type: ignore
        v8_date = _vd
    except Exception:
        v8_date = None

# ── 就绪判据 ────────────────────────────────────────────────────────────────
#   items : 代表性产物（读文件内容 update_time / data_date）
#   need  : 至少命中几项算就绪
#   must  : 其中必须命中（全中）的关键项
READY_SPEC: dict[str, dict] = {
    "A": {
        "items": ["data/LHB_DATA.js", "raw_data/sector_rs.json", "raw_data/stock_profile.json"],
        "need": 3,
        "must": ["data/LHB_DATA.js"],   # 龙虎榜是「16:30后数据」的核心标志
    },
    "B": {
        # 🛡 2026-09-11 主人令「一劳永逸」：readiness 清单从 3 项代表产物扩到 8 项。
        #   根因（2026-09-11 09:5x 实证）：原清单只校验 3 个代表产物，而 B 批实际有
        #   28 个脚本、产出几十个 raw_data/*.json。当这 3 项鲜活、其余产物陈旧时，
        #   闸门判「B 批已就绪」→ target_stage=NONE / OUTCOME=skipped
        #   （reason=「✅ 四批产物均已就绪 → 空转」）→ 9 张卡（AI_INSIGHTS_COMPARE /
        #   FACTOR_AUDIT / FACTOR_PROGRESS / VALUATION_PERCENTILE / INDEX_VALUE_FRAMEWORK /
        #   TOP10_DAILY / BACKTEST_COMPREHENSIVE / SUSPENSION_ALERT /
        #   SECTOR_FUND_FLOW_TREND）整日红灯却无人重跑。
        #   修法：纳入 5 个刚从 experiments workflow 收编的新产物，使「B 批已就绪」
        #   必须以它们也鲜活为前提 —— 标本兼治（挂链 + 闸门双向对齐）。
        "items": [
            "data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js",
            "raw_data/ai_insights_compare.json",
            "raw_data/factor_audit.json",
            "raw_data/factor_progress.json",
            "raw_data/valuation_percentile.json",
            "raw_data/index_value_framework.json",
        ],
        # need 用 5/8：3 个核心选股产物 + 5 个新收编产物中至少命中 2 个，
        #   既覆盖新卡、又不在个别 fetcher 因上游限流失败时把整链锁死。
        "need": 5,
        "must": [],
    },
    "D": {"items": ["data/FINAL_RECOMMEND_DATA.js"], "need": 1, "must": []},
    "E": {"items": ["data/CRDS_BACKTEST.js", "data/BACKTEST_TDX.js"], "need": 1, "must": []},
}

# 各批上游：上游不就绪则拒绝开跑（顺序闸门 · 一环套一环）
PREREQ: dict[str, str | None] = {"A": None, "B": "A", "D": "B", "E": "D"}

# 盘后链「起点」（该时刻之前不跑任何批）
START_TRADING = (16, 0)
START_T1 = (8, 0)
# 产物「算今日盘后」的最低时刻
FLOOR_TRADING = (16, 30)
FLOOR_T1 = (8, 0)

# 🛡 2026-09-11 一劳永逸（run#1692 / run#34535287523 双实证）：夜间补跑窗口上界。
#   原为 6（00:00-05:59）。缺陷：算法链实测耗时 84+ 分钟，凡 05:00 后起跑的夜间补跑
#   必然在跑到一半时跨出窗口 —— run#1692 于 05:16 起跑，B 批 06:43 才跑完，而 06:01
#   派发的那一轮闸门在 06:51 判定「未到本日 16:00 起点 → NONE」→ 整链空转，
#   B 批 84 分钟成果无人接力，TOP10_DAILY/FINAL_RECOMMEND_DATA 整日停更。
#   修法：窗口放宽到 08:59（开盘前），使「本日链未到起点」的时段仍能补跑上一数据日。
#   与 algorithms/run_algorithms.py::_NEXT_DAY_CUTOFF_HOUR、algorithms/utils/time_gate.py::
#   _NIGHT_CUT_HOUR 三处同源对齐 —— 两套口径必然漂移（历史教训）。
_NIGHT_CUT = 9

_UT_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})')
_DT_ONLY_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})')
_DATE_RE = re.compile(r'"data_date"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')


def read_ut(root: str, rel: str):
    """读产物时间 → (YYYY-MM-DD, hh, mm)；只有日期无时刻时记为 23:59（宽松）。"""
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
    """把 (day, hh, mm) 展开成候选解释：原样 +（若 hh<6）归前一自然日的 24:xx。

    🔴 2026-09-10 实测缺陷修复：夜间补跑窗口（00:00-08:59）写出的产物戳是「当天」，
    但该档判定的数据日是「前一自然日」→ 只认原样会永不匹配 → 00:30-05:59 每档重跑该批
    （死循环，实测已复现）。两种解释都接受即根治。
    """
    out = [(r[0], r[1], r[2])]
    if r[1] < _NIGHT_CUT:
        d = dt.date.fromisoformat(r[0]) - dt.timedelta(days=1)
        out.append((d.strftime("%Y-%m-%d"), r[1] + 24, r[2]))
    return out


def _newest(root: str, items):
    """取这些产物里「最新」的时间戳（含凌晨候选解释），无则 None。"""
    best = None
    for it in items:
        r = read_ut(root, it)
        if not r:
            continue
        for c in _cand(r):
            if best is None or c > best:
                best = c
    return best


# 🔴 跨批顺序判据（一环套一环的硬约束）：下游最新产物必须 ≥ 上游基准产物。
#   基准只挑「单一来源、写一次就固定」的产物，避免被后续抓取链刷新导致反复重算。
SEQ_REF: dict[str, str] = {
    "B": "data/LHB_DATA.js",             # A 批核心标志（17:30 落盘后不再变）
    "D": "data/TRIPLE_CONSENSUS.js",     # B 批代表产物
    "E": "data/FINAL_RECOMMEND_DATA.js", # D 批产物
}


def check_ready(root: str, stage: str, day: str, floor: tuple[int, int], kind: str = "trading"):
    """返回 (是否就绪, '命中/总数', 明细)。

    kind='t1'（周六/假期首日）时放宽 A 采集批：T+1 日数据天然是「部分刷新」，
      若仍按交易日 3/3 + 龙虎榜必新，A 会永远不就绪 → 整条 T+1 链卡死（漏档）。
      放宽为「任一 A 产物当日刷新即视为采集完成」，把节奏交给 B/D/E 三批。
    """
    spec = READY_SPEC[stage]
    need = spec["need"]
    must = list(spec["must"])
    if kind != "trading" and stage == "A":
        need, must = 1, []
    hit, must_ok, parts = 0, True, []
    for it in spec["items"]:
        r = read_ut(root, it)
        ok = bool(r and any(c[0] == day and (c[1], c[2]) >= floor for c in _cand(r)))
        if ok:
            hit += 1
            parts.append(f"{os.path.basename(it)}=OK({r[0]} {r[1]:02d}:{r[2]:02d})")
        elif r:
            parts.append(f"{os.path.basename(it)}=STALE({r[0]} {r[1]:02d}:{r[2]:02d})")
        else:
            parts.append(f"{os.path.basename(it)}=MISS")
        if it in must and not ok:
            must_ok = False

    ready = must_ok and hit >= need
    # 🔴 跨批顺序闸门：下游算完但上游之后又被刷新过 → 判未就绪，必须重算（防「拿旧上游算下游」）
    if ready and stage in SEQ_REF:
        up = read_ut(root, SEQ_REF[stage])
        mine = _newest(root, spec["items"])
        if up and mine:
            up_best = max(_cand(up))
            if mine < up_best:
                parts.append(
                    "\u26d4\u4e0b\u6e38\u65e9\u4e8e\u4e0a\u6e38(%s=%s %02d:%02d)\u2192\u9700\u91cd\u7b97"
                    % (os.path.basename(SEQ_REF[stage]), up_best[0], up_best[1], up_best[2]))
                ready = False
    return ready, f"{hit}/{len(spec['items'])}", " ".join(parts)


# ── 交易日历：今天该跑哪个「数据日」 ─────────────────────────────────────────
def _is_trading_day(d: dt.date) -> bool:
    if v8_date is None:
        return d.weekday() < 5
    try:
        return bool(v8_date.is_trading_day(d))
    except Exception:
        return d.weekday() < 5


def _last_trading_day(ref: dt.date) -> dt.date | None:
    if v8_date is None:
        d = ref
        for _ in range(15):
            if d.weekday() < 5:
                return d
            d -= dt.timedelta(days=1)
        return None
    try:
        return dt.datetime.strptime(v8_date.last_trading_day(ref, max_lookback=15), "%Y-%m-%d").date()
    except Exception:
        return None


def chain_day(ref: dt.date, lookback: int = 0):
    """返回 (数据日 | None, 类型 trading|t1|none, 说明)。

    lookback>0 时向前找最近一个「应跑日」（供 --force 周末审计补跑）。
    """
    for i in range(lookback + 1):
        d = ref - dt.timedelta(days=i)
        if _is_trading_day(d):
            return d, "trading", f"交易日 {d}"
        if d.weekday() == 6:      # 周日休市（周五 T+1 周六已处理）
            continue
        ld = _last_trading_day(d)
        if ld is not None:
            gap = (d - ld).days
            if 0 < gap <= 3:
                return d, "t1", f"T+1 数据日 {d}（上一交易日 {ld}）"
    return None, "none", "非交易日（休市，无 T+1 需求）"


def _backfill_candidate(root: str, ref: dt.date):
    """上一数据日仍有未完成批次时返回 (day, kind, note, ready)，否则 None。

    🛡 2026-09-11 一劳永逸（闸门死区根治）：
      原设计只在「本数据日的链起点」之后才跑批，工作日 09:00~15:59 遂成死区 ——
      若上一数据日的链中途失败没跑完，这段时段**任何补跑都被判 NONE**。
      实测 run#1692：B 批 06:43 才跑完（链耗时 84min，跨出了夜间补跑窗口），
      06:01 派发的那一轮闸门 06:51 判「未到本日 16:00 → NONE」→ 整链空转，
      84 分钟成果无人接力，TOP10_DAILY / FINAL_RECOMMEND_DATA / V8_POOL_TRACKER /
      BACKTEST_COMPREHENSIVE 四个模块停更一整天。
      判据严格限定为「上一数据日**确有**未完成批次」，正常日不受任何影响。
    """
    prev = ref - dt.timedelta(days=1)
    pday, pkind, pnote = chain_day(prev, lookback=2)
    if pkind == "none" or pday is None:
        return None
    pfloor = FLOOR_TRADING if pkind == "trading" else FLOOR_T1
    pday_s = pday.strftime("%Y-%m-%d")
    pready = {s: check_ready(root, s, pday_s, pfloor, pkind) for s in READY_SPEC}
    if all(pready[s][0] for s in ("A", "B", "D", "E")):
        return None
    missing = "/".join(s for s in ("A", "B", "D", "E") if not pready[s][0])
    return (pday, pkind,
            f"{pnote}·上一数据日链未完成({missing})→补跑（本数据日链未到起点）",
            pready)


def decide(root: str, now: dt.datetime, explicit: str, force: bool):
    hh, mm = now.hour, now.minute
    ref = now.date()
    if hh < _NIGHT_CUT:             # 凌晨归前一自然日（夜间补跑窗口）
        ref -= dt.timedelta(days=1)
    day, kind, note = chain_day(ref, lookback=3 if force else 0)

    if kind == "none":
        return ("NONE", True, f"⏸ {note} → 不跑任何批（合规空转）", day, kind, {})

    floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
    day_s = day.strftime("%Y-%m-%d")
    ready = {s: check_ready(root, s, day_s, floor, kind) for s in READY_SPEC}

    def out():
        return {f"ready_{s}": ready[s][1] for s in ("A", "B", "D", "E")}

    # ── 0) 显式全链（人工应急全量补算）──────────────────────────────────────
    if explicit == "ALL":
        return ("ALL", True, "显式 ALL：应急全量补算（缺什么跑什么，由 run_algorithms 全链兜底）",
                day, kind, out())

    # ── 1) 显式 stage（人工应急）—— 仍必须过上游顺序闸门 ─────────────────────
    if explicit in ("A", "B", "D", "E"):
        pre = PREREQ[explicit]
        if pre is None:
            return (explicit, True, f"显式 {explicit}（最上游，无前置）", day, kind, out())
        if ready[pre][0]:
            return (explicit, True, f"显式 {explicit}，前置 {pre} 已就绪({ready[pre][1]})", day, kind, out())
        return (explicit, False,
                f"⛔ 显式 {explicit} 但前置 {pre} 未就绪({ready[pre][1]}) —— 拒绝执行，"
                f"否则会用陈旧数据算出假新鲜产物", day, kind, out())

    # ── 2) 时间闸：盘后链起点（交易日 16:00 / T+1 日 08:00；--force 跳过）────
    #   凌晨 00:00-08:59 属**前一数据日的夜间补跑窗口** → 有效时刻按 24:xx 计，
    #   否则 00:30 接力档会恒判「未到起点」→ B 若 22:30 后才跑完，D/E 永远补不上（漏档实锤）。
    eff = (hh + 24, mm) if hh < _NIGHT_CUT else (hh, mm)
    start = START_TRADING if kind == "trading" else START_T1
    if not force and eff < start:
        # 🛡 2026-09-11 一劳永逸（死区根治）：本数据日的链还没到起点，但**上一数据日**
        #   可能中途失败没跑完 —— 此时唯一正解是补跑上一数据日（见 _backfill_candidate）。
        _bf = _backfill_candidate(root, ref)
        if _bf is None:
            return ("NONE", True,
                    f"⏸ 未到{note}盘后链起点（{start[0]:02d}:{start[1]:02d}，现 {hh:02d}:{mm:02d}）"
                    f"，且上一数据日已无未完成批次 → 空转（合规）",
                    day, kind, out())
        day, kind, note, ready = _bf

    # ── 3) 自愈：缺什么跑什么（纯内容级 · 一环套一环）────────────────────────
    if not ready["A"][0]:
        return ("A", True, f"A 未就绪({ready['A'][1]}) → 跑采集批", day, kind, out())
    if not ready["B"][0]:
        return ("B", True, f"A 就绪({ready['A'][1]}) B 未就绪({ready['B'][1]}) → 跑选股批", day, kind, out())
    if not ready["D"][0]:
        return ("D", True, f"B 就绪({ready['B'][1]}) D 未就绪({ready['D'][1]}) → 跑汇总批（最终推荐）",
                day, kind, out())
    if not ready["E"][0]:
        return ("E", True, f"D 就绪({ready['D'][1]}) E 未就绪({ready['E'][1]}) → 跑回测批", day, kind, out())
    return ("NONE", True, "✅ 四批产物均已就绪 → 空转（合规，真成功）", day, kind, out())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--today", default="", help="指定自然日 YYYY-MM-DD（演练用）")
    ap.add_argument("--hour", type=int, default=-1, help="CST 小时（演练用）")
    ap.add_argument("--minute", type=int, default=-1, help="CST 分钟（演练用）")
    ap.add_argument("--explicit-stage", default="")
    ap.add_argument("--force", action="store_true", help="忽略时间门控（周末/假期审计补跑）")
    ap.add_argument("--recheck", action="store_true",
                    help="只复核就绪度（链尾问责用）：打印 ready_A..E，不做调度决策")
    ap.add_argument("--out", default="", help="写入文件，默认 stdout")
    a = ap.parse_args()
    _ensure_v8_date(a.root)

    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    if a.today:
        try:
            d = dt.datetime.strptime(a.today, "%Y-%m-%d")
            now = now.replace(year=d.year, month=d.month, day=d.day)
        except Exception:
            pass
    if a.hour >= 0:
        now = now.replace(hour=a.hour)
    if a.minute >= 0:
        now = now.replace(minute=a.minute)

    explicit = (a.explicit_stage or "").strip().upper()

    # ── 链尾问责模式：只按「数据日 + 门槛」复核就绪度，避免链尾另写一套新鲜度规则 ──
    if a.recheck:
        if a.today:
            try:
                d = dt.datetime.strptime(a.today, "%Y-%m-%d").date()
            except Exception:
                d = None
        else:
            d = None
        if d is None:
            d, kind, _ = chain_day(now.date(), lookback=3)
            if d is None:
                d, kind = now.date(), "trading"
        else:
            _, kind, _ = chain_day(d, lookback=0)
            if kind == "none":
                kind = "trading"      # --today 传了周日等边缘情况时按交易日口径兜底
        floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
        ds = d.strftime("%Y-%m-%d")
        lines = [f"recheck_day={ds}", f"recheck_kind={kind}"]
        for st in ("A", "B", "D", "E"):
            ok, cnt, _det = check_ready(a.root, st, ds, floor, kind)
            lines.append(f"ready_{st}={cnt}")
        print("\n".join(lines))
        return 0

    target, ok, reason, day, kind, rdy = decide(a.root, now, explicit, a.force)
    proceed = bool(ok and target != "NONE")

    lines = [
        f"target_stage={target}",
        f"stage_ok={'true' if ok else 'false'}",
        f"proceed={'true' if proceed else 'false'}",
        f"chain_day={day.strftime('%Y-%m-%d') if day else 'none'}",
        f"chain_kind={kind}",
        f"cst_hour={now.hour}",
        f"reason={reason}",
    ]
    for k, v in rdy.items():
        lines.append(f"{k}={v}")
    floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
    day_s = day.strftime("%Y-%m-%d") if day else "-"
    det = " | ".join(f"{s}:{check_ready(a.root, s, day_s, floor, kind)[2]}" for s in ("A", "B", "D", "E"))
    lines.append(f"detail={det}")
    body = "\n".join(lines)

    if a.out:
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(body + "\n")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
