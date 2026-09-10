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
       凌晨(00:00-05:59) → 归前一自然日（夜间补跑窗口，允许继续跑未完的批）
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
        "items": ["data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js"],
        "need": 3,
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
        ok = bool(r and r[0] == day and (r[1], r[2]) >= floor)
        if ok:
            hit += 1
            parts.append(f"{os.path.basename(it)}=OK({r[0]} {r[1]:02d}:{r[2]:02d})")
        elif r:
            parts.append(f"{os.path.basename(it)}=STALE({r[0]} {r[1]:02d}:{r[2]:02d})")
        else:
            parts.append(f"{os.path.basename(it)}=MISS")
        if it in must and not ok:
            must_ok = False
    return (must_ok and hit >= need), f"{hit}/{len(spec['items'])}", " ".join(parts)


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


def decide(root: str, now: dt.datetime, explicit: str, force: bool):
    hh, mm = now.hour, now.minute
    ref = now.date()
    if hh < 6:                      # 凌晨归前一自然日（夜间补跑窗口）
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
    #   凌晨 00:00-05:59 属**前一数据日的夜间补跑窗口** → 有效时刻按 24:xx 计，
    #   否则 00:30 接力档会恒判「未到起点」→ B 若 22:30 后才跑完，D/E 永远补不上（漏档实锤）。
    eff = (hh + 24, mm) if hh < 6 else (hh, mm)
    start = START_TRADING if kind == "trading" else START_T1
    if not force and eff < start:
        return ("NONE", True,
                f"⏸ 未到{note}盘后链起点（{start[0]:02d}:{start[1]:02d}，现 {hh:02d}:{mm:02d}）→ 空转（合规）",
                day, kind, out())

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
