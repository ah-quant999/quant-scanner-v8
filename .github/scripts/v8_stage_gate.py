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
      现在只保留「盘后链起点」一个时间闸（交易日 18:00 / T+1 日 08:00），
      批次推进完全由上游产物说了算 —— 数据到了就跑，没到就不跑。
  3) 上游未就绪 → stage_ok=false → 调用方**必须红灯 + 拒绝执行 + 紧急报告**
     （主人令「发现前面是错的，就该退回拒绝之后的执行并紧急报告」）。
     🔔 紧急报告 = 本地 v8_cloud_watchdog / health_patrol / 盘后算法链接力推进器 检测到
        本 workflow run 变红（::error + exit 1）后，按 .workbuddy/v8_smtp_config.json
        向 2814546@qq.com 发邮件告警（工作日 7-21 点）。闸门只负责"判红+拒绝"，
        邮件由上述本地链路发出——不在此处另造一套发信。
  4) 🔴 2026-09-11 主人令「一劳永逸」：盘后链起点 = **交易日 18:00**（非 16:00）。
     全部当日交易数据（含龙虎榜 16:30 后、收盘结算）出炉后，A 采集批才允许开跑；
     此前的唤醒一律视为"未到起点"→ 空转或回填上一数据日，绝不抢跑半日数据。
     批次推进完全由上游产物说了算——数据到了就跑，没到就不跑。
     成功定义 = A→B→D→E 四批**全部**为当日产物 + 推送 main + Pages 构建部署上线
     （链尾「产物完整性闸门 + 结果问责」逐批校验，任一停留非当日即整条链变红）。

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
  产物时间戳含「凌晨 00:00-08:59 归前一自然日 24:xx」的候选解释（防凌晨死循环）。
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
        # 🛡 2026-09-11 主人令「一劳永逸」（与 B 批同源根治）：readiness 清单 3 → 10 项。
        #   原清单只校验 3 个代表产物（LHB_DATA / sector_rs / stock_profile），而 A 批实有
        #   12 个脚本。实测（2026-09-11 经 Contents API 直查 main）：
        #   这 3 项鲜活，但 A 批另有 6 个产物停在 09-10 ——
        #     fundamental_quality / stock_quote / inst_trade / suspension_alert /
        #     nt_data / sector_fund_flow_trend
        #   → 闸门判「A 已就绪」→ 这些卡整日红灯却无人重跑
        #     （主人截图中的 SUSPENSION_ALERT / SECTOR_FUND_FLOW_TREND 正是此类）。
        #   故把 A 批全部可读时戳的产物纳入清单。
        #   ⚠️ 不含 stock_names.json：该文件无 update_time/data_date 字段，read_ut 恒返回
        #      None → 会永久计为 MISS 从而拉低命中数（实测已确认）。
        #   need=7/10：容忍 3 项失败仍放行，避免个别抓取源抖动把整条链锁死在 A 批；
        #     而当前 4/10 的状态会被判「未就绪」→ 正确触发补跑。
        "items": [
            "data/LHB_DATA.js",                 # 龙虎榜 = 「16:30后数据」的核心标志（must）
            "raw_data/sector_rs.json",
            "raw_data/stock_profile.json",
            "raw_data/fundamental_quality.json",
            "raw_data/stock_quote.json",
            "raw_data/inst_trade.json",
            "raw_data/suspension_alert.json",
            "raw_data/nt_data.json",
            "raw_data/sector_fund_flow_trend.json",
            "raw_data/market_alerts.json",
        ],
        "need": 7,
        "must": ["data/LHB_DATA.js"],   # 龙虎榜是「16:30后数据」的核心标志
    },
    "B": {
        # 🛡 2026-09-11 主人令「一劳永逸」：readiness 清单从 3 项代表产物扩到 9 项。
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
            "raw_data/gold_pool.json",            # 🛡 2026-09-11：金股池改为 B 批 build_candidate_pool 原生派生，纳入就绪硬约束
        ],
        "need": 8,
        # need 用 8/9：3 个核心选股产物 + 5 个收编产物 + gold_pool，即「只容忍 1 项不新鲜」。
        #   ⚠️ 为何不是 5：实测发现 dedup 去重器会把「内容天然稳定」的卡判为伪变更而丢弃
        #   （见 .github/scripts/dedup_fetch_manifest.py 的 _ALWAYS_PUSH）。在去重器修好之前，
        #   一轮 B 批跑完后线上只会有 3 核心 + 2 张（ai_insights/valuation_percentile）= 5/9。
        #   若 need=5，闸门会据此判「B 已就绪」→ 空转 → 另 4 张（factor_audit /
        #   factor_progress / index_value_framework / gold_pool）永远补不上 → 恒红。
        #   need=8 使闸门在上述状态下判「未就绪」→ 再跑一轮 B → 去重修复生效后 9/9 → 收敛。
        #   容错：9 项中唯一易碎的是 valuation_percentile（依赖 akshare 外部接口），
        #   故 8 恰好容忍它单独失败而不把整链锁死。
        "must": [],
    },
    "D": {"items": ["data/FINAL_RECOMMEND_DATA.js"], "need": 1, "must": []},
    "E": {"items": ["data/CRDS_BACKTEST.js", "data/BACKTEST_TDX.js"], "need": 1, "must": []},
}

# 各批上游：上游不就绪则拒绝开跑（顺序闸门 · 一环套一环）
# 🔴 2026-09-11 主人令「一劳永逸」：A→B→D→E 严格串联，下游批**必须等上游批产出"当日"数据**
#   才放行（PREREQ 上游未就绪 → stage_ok=false → 调用方红灯拒绝 + 邮件告警）。
PREREQ: dict[str, str | None] = {"A": None, "B": "A", "D": "B", "E": "D"}

# 盘后链「起点」（该时刻之前不跑任何批）
# 🔴 2026-09-11 主人令「一劳永逸」：16:00 → 18:00。全部当日交易数据（龙虎榜 16:30 后、
#   收盘结算）出炉后 A 采集批才允许开跑；此前唤醒一律空转或回填上一数据日，绝不抢跑半日数据。
START_TRADING = (18, 0)
START_T1 = (8, 0)
# 产物「算今日盘后」的最低时刻
FLOOR_TRADING = (16, 30)
FLOOR_T1 = (8, 0)

# 🛡 2026-09-11 一劳永逸（run#1692 / run#34535287523 双实证）：夜间补跑窗口上界。
#   原为 6（00:00-05:59）。缺陷：算法链实测耗时 84+ 分钟，凡 05:00 后起跑的夜间补跑
#   必然在跑到一半时跨出窗口 —— run#1692 于 05:16 起跑，B 批 06:43 才跑完，而 06:01
#   派发的那一轮闸门在 06:51 判定「未到本日 16:00 起点 → NONE」→ 整链空转，
#   （注：16:00 是**事发当时**的起点值；起点常量已改为 18:00，本段为历史实证记录，勿当现行口径。）
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
    但该档判定的数据日是「前一自然日」→ 只认原样会永不匹配 → 00:30-08:59 每档重跑该批
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

    🔴 2026-09-11 一劳永逸（阿狸咪的工程师）：非交易日「应跑日」判据精确化。
      主人规则：**周六跑 / 周日不跑 / 假期第一日跑 / 假期第二日起不跑**。
      旧判据 `gap=(d-上一交易日).days; 0 < gap <= 3` ⇒ 距上个交易日不超过 3 天即判 t1，
      实测把**假期第 2、3 天也判成应跑日**（中秋 09-26、国庆 10-02/10-03 全部 t1）：
        · 白跑整链 84 分钟 ×(N-1) 天；
        · 产物 update_time 被刷成**非交易日日期** → 主站卡片显示「10-02」这类不存在的数据日。
      新判据只认「连续休市段的第一天」（前一天是交易日），三条规则**全部自动成立**：
        · 周六         d-1 = 周五(交易日)   → 段首   → 跑
        · 周日         d-1 = 周六(非交易日) → 非段首 → 不跑
        · 假期第一日   d-1 = 交易日         → 段首   → 跑
        · 假期第2日起  d-1 = 非交易日       → 非段首 → 不跑（含假期里落到周六的那天）
      ⚠️ 已知边界（非交易日集合无法区分，已在交接单标注）：若某年假期自**周六**开始，
        则段首=周六；若假期自**周一**开始，段首仍是周六（周末也属该休市段）。两种情况
        都只在段首跑一次，同一目标（下个交易日）的数据不会缺，只是唤醒点比字面少一次。
    """
    for i in range(lookback + 1):
        d = ref - dt.timedelta(days=i)
        if _is_trading_day(d):
            return d, "trading", f"交易日 {d}"
        # 🔴 2026-09-11 精确判据：仅「连续休市段的第一天」为应跑日（详见 docstring）
        if _is_trading_day(d - dt.timedelta(days=1)):
            return d, "t1", f"T+1 数据日 {d}（上一交易日 {_last_trading_day(d)}）"
    return None, "none", "非交易日（休市，无 T+1 需求）"


def _backfill_candidate(root: str, ref: dt.date):
    """上一数据日仍有未完成批次时返回 (day, kind, note, ready)，否则 None。

    🛡 2026-09-11 一劳永逸（闸门死区根治）：
      原设计只在「本数据日的链起点」之后才跑批，工作日 09:00~15:59 遂成死区 ——
      若上一数据日的链中途失败没跑完，这段时段**任何补跑都被判 NONE**。
      实测 run#1692：B 批 06:43 才跑完（链耗时 84min，跨出了夜间补跑窗口），
      06:01 派发的那一轮闸门 06:51 判「未到本日 16:00 → NONE」→ 整链空转，
      （注：16:00 是**当时**起点值，现行为 18:00；本段是 run#1692 历史实证记录。）
      84 分钟成果无人接力，TOP10_DAILY / FINAL_RECOMMEND_DATA / V8_POOL_TRACKER /
      BACKTEST_COMPREHENSIVE 四个模块停更一整天。
      判据严格限定为「上一数据日**确有**未完成批次」，正常日不受任何影响。
    """
    prev = ref - dt.timedelta(days=1)
    # 🔴 2026-09-11 判据改「段首」后，回填需跨过**整段**连续休市（最长 = 国庆 7 天
    #   + 前后周末 ≈ 9~10 天）才能找到上一个应跑日；2 太短会漏掉假期首日。
    pday, pkind, pnote = chain_day(prev, lookback=10)
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
    day, kind, note = chain_day(ref, lookback=10 if force else 0)

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

    # ── 2) 时间闸：盘后链起点（交易日 18:00 = START_TRADING / T+1 日 08:00 = START_T1；
    #   🔴 2026-09-11 修正：此处原写「交易日 16:00」是过时口径（起点常量已改 18:00），--force 跳过）────
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
            d, kind, _ = chain_day(now.date(), lookback=10)
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
            # 🛡 2026-09-11 一劳永逸（阿狸咪）：把闸门的**布尔裁决**一并透出。
            #   链尾问责步曾写死 `[ "$B_FRESH" = "3/3" ]`，而本契约 2026-09-11 已改为
            #   「9 项 / need=8」（ready_B=8/9 或 9/9）→ 字面量永不匹配 → 每轮 B 批假红灯。
            #   透出 true/false 后，问责只消费闸门裁决，不再复制字面量 ⇒ 契约再变也不漂移。
            lines.append(f"ready_ok_{st}={'true' if ok else 'false'}")
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
