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

# 🔴🔴 2026-09-13 小九审计修复：三重共识主口径的**单一真源**（且必须**恰好 1 行** primary）。
#   为何必须是「严格档 · T+5」，三条例证缺一不可：
#   ① **前端按它选档**：index.html `__committeePeriods()` 取「第一条 is_primary 行的 label」
#      归一化出 pat（T+数字→T+#），再只保留 label==pat 的行去算星级。
#      ⇒ 若 primary 有 2 行以上（原实现=三档各 1 行），会取到 band 顺序最靠前的**宽松档**；
#      ⇒ 若 primary 行 label 带额外后缀（原实现有「（主口径）」），归一化后与其余档不等，
#         评级只剩 primary 那一档。实测（node 复刻该函数）：原实现 = 用「宽松档 T+20」单档评星。
#      现改为「严格档 · T+5」且 label **不加任何后缀** ⇒ 严格档 12 档全部参与评级。
#   ② **本文件 L54 铁律**：主口径刻意取 T+5 —— 四量/CRDS 主口径均为 T+5，
#      卡级主表是「同口径横比」，三重共识取 T+20 会使跨卡横比失效（= 文件头警告场景）。
#   ③ `SOURCES.primary` 与产出 label 必须**逐字一致** ⇒ 兜底匹配（label == primary）才成立。
CONSENSUS_PRIMARY_BAND = "共振≥80（严格）"   # = 前端 __STAR_COMPARISON_CARDS 的 resonance_gte80
CONSENSUS_PRIMARY_HOLD = 5                   # T+5，与其余各卡主口径同档
# 🔴 2026-09-12 主人令（拍板第 1 项·①）：各回测脚本持有期已扩为
#   [1, 3] + [5,10,20,30,45,60,75,90,180,250]（同源常量 HOLD_LADDER，见各脚本）。
#   🔴 2026-09-13 主人令扩档：+180/+250（原 8 档）。主人原话：「所有接入算法链的
#      选股策略都按5、10、20、30、45、60、75、90、180、250日的跟踪回测」。
#      ⇒ 各脚本的 lookahead 窗口已同步从 90 交易日口径抬到 250 交易日口径
#        （否则长档 `len(after)-1 < hp` 恒真 → 静默零样本，12 日与 13 日各踩一次）。
#   ⚠️ 本脚本的**主口径刻意仍取 T+5**（各 src 的 primary 字段）：
#     主表是「同口径横比」，T+5 是各卡唯一共同拥有的短档，样本最厚、可比性最强；
#     若改 T+90，则① 长档样本天然薄（回测区间早期信号凑不满 90 日）
#     ② 各卡主口径可能取到不同档 ⇒ 横比失去意义。
#     长档（30/45/60/75/90）全部照常进 ranking_all 明细表 + 前端「持有期档位矩阵」，
#     主人要的「从近到远慢慢跟踪」由明细表承担，不由主表承担。
LOW_WIN_RATE = 45.0       # 胜率红线：低于此判「低胜率」
LOW_AVG_RETURN = 0.0      # 平均收益红线：<= 此判「低收益」（已扣成本口径）

_NIGHT_CUT = 9            # 与闸门 _NIGHT_CUT / _NEXT_DAY_CUTOFF_HOUR / _NIGHT_CUT_HOUR 同源
FLOOR_TRADING = (16, 30)  # 与闸门 FLOOR_TRADING 同源
FLOOR_T1 = (8, 0)         # 与闸门 FLOOR_T1 同源

# 🔴 2026-09-14：因子卡主口径 = T+5 —— 与文件头 L54 铁律一致
#   （「主口径刻意取 T+5」，四量 / CRDS 均 T+5），保证卡级主表可跨卡横比。
#   必须**恰好 1 行** is_primary：前端 __committeePeriods() 靠它定「主口径标签模式」，
#   多于 1 行会取到错误档、0 行则星级静默失真。
#   ⚠️ 定义位置必须在 SOURCES 之前 —— SOURCES 内的 primary= 引用它，否则 NameError。
FACTOR_PRIMARY_HOLD = 5

# ── 源登记表：**card = 前端卡名**（权威出处 index.html 的 V8_PAGE_SCHEDULE + 策略回测页）──
SOURCES = [
    dict(card="三重共识", kind="strategy", page="选股策略", icon="🧲", cat="trade",
         var="BACKTEST_COMPREHENSIVE", rel="data/BACKTEST_COMPREHENSIVE.js",
         parser="comprehensive", label_prefix="共振",
         # ⚠️ 必须与 parse_comprehensive 产出的主口径 label **逐字一致**（见上方常量块 ③）
         primary=f"{CONSENSUS_PRIMARY_BAND} · T+{CONSENSUS_PRIMARY_HOLD}",
         method="信号日次一交易日开盘买入、持有 N 个真实交易日收盘卖出（baostock 前复权·扣双边 0.3%）"),
    dict(card="四量终极", kind="strategy", page="选股策略", icon="📊", cat="trade",
         var="FOUR_VOLUME_BACKTEST", rel="data/FOUR_VOLUME_BACKTEST.js",
         parser="by_period", label_prefix="持有", primary="持有 T+5",
         method="信号日次一交易日开盘买入、持有 N 个真实交易日收盘卖出（前复权·扣双边 0.3%）"),
    dict(card="逆势龙头", kind="strategy", page="选股策略", icon="🐉", cat="trade",
         var="CRDS_BACKTEST", rel="data/CRDS_BACKTEST.js",
         parser="by_period", label_prefix="持有", primary="持有 T+5",
         method="信号日次一交易日开盘买入、持有 N 日收盘卖出（前复权·扣双边 0.3%）"),
    dict(card="强势突破", kind="strategy", page="暂未上架", icon="🚀", cat="trade",
         var="ALGO_BACKTEST_COMPARE", rel="data/ALGO_BACKTEST_COMPARE.js",
         parser="algo_compare", label_prefix="", primary=None,
         method="实盘入选样本同口径聚合（T+1~T+10 前向收益）",
         # 🆕 2026-09-13 主人令：缺口闭环 —— scripts/algo_backtest_compare.py
         #   已挂进 E 批（ORDER + STAGES，位于本聚合器之前），不再是孤儿。
         #   原值 chain_member=False / chain_note="原为孤儿（未挂 STAGES）"。
         chain_member=True,
         chain_note=None),
    dict(card="K线信号层", kind="signal", page="策略回测", icon="📈", cat="signal",
         var="BACKTEST_TDX", rel="data/BACKTEST_TDX.js",
         parser="tdx", label_prefix="", primary=None,
         method="9 类 K 线信号 60 日前向回测：信号日次一交易日开盘买入、持有 N 日收盘卖出（前复权）"),
    # 🔴 2026-09-14 主人令更正：「金股池和候选股池是算法的**上游水源**，不是策略，
    #   **不需要回测**！」—— 候选池（B 批 build_candidate_pool.py）/ 金股池(黄金池,
    #   scanner.py) 是基础股池，作为策略的输入宇宙供给下游，本身无买卖点；
    #   拿 T+1 胜率考核它们必然误导（实测 金股池 T+1 胜率 32.28% 被当成低绩效策略
    #   进了 delist_advice 下架提请）。
    #   ⇒ 已删除两条 SOURCES 条目 + parse_pool()，并删除 algorithms/backtest_pools.py
    #     与 data/{CANDIDATE,GOLD_POOL}_BACKTEST.js。**不得再登记回本表**。
    # 🔴 2026-09-14 主人令（图1「反而缺了因子的回测」）：因子卡面本就挂「📈 选股策略」
    #   徽章，却被登记为 kind=research / cat=research ⇒ 卡面说它是策略、数据层不给它排名，
    #   自相矛盾。现改为交易型（cat=trade），口径 = **L1 最强五分位组合**（见 parse_factor_lab）。
    dict(card="因子实验室", kind="strategy", page="选股策略", icon="🧪", cat="trade",
         var="FACTOR_LAB_BACKTEST", rel="data/FACTOR_LAB_BACKTEST.js",
         parser="factor_lab", label_prefix="", primary=f"L1最强分位 T+{FACTOR_PRIMARY_HOLD}",
         method="因子五分位分层超额（每10交易日调仓·次一交易日开盘入场）"),
]

# 🆕 2026-09-13 主人令：全部接入算法链的选股策略统一 10 档（同源 HOLD_LADDER）。
FULL_LADDER = [5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
# TDX 源（backtest_tdx.py）另产 T+1 / T+3 短档 —— 矩阵同样要显示，故单列全阶。
# ⚠️ 与 algorithms/backtest_tdx.py 的 HOLD_DAYS = [1, 3] + HOLD_LADDER 同源。
HOLD_LADDER_FULL = [1, 3] + FULL_LADDER

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
    row = {
        "card": card or src["card"], "page": src["page"], "icon": src["icon"], "cat": src["cat"],
        "label": label, "source_var": src["var"], "source_file": src["rel"],
        "hold": hold, "sample": _int(sample),
        "win_rate": _num(win_rate), "avg_return": _num(avg_return),
        "extra": extra or {}, "status": status, "method": src.get("method", ""),
        "_primary_override": primary,
    }
    # 🔴 2026-09-13 主人铁律⑭（未知一律 null，绝不用 0 冒充）——统一兜底：
    #   零样本档位的源里常写着 win_rate=0 / avg_return=0.0（如 BACKTEST_TDX 的
    #   win_rate_30d=0、CRDS 旧产物的 avg_return=0），直接透传会在前端显示成
    #   「胜率 0.0% / 收益 0.00%」—— 那是**把「算不出」伪装成「算出来了且很差」**，
    #   会直接污染下架判断（把窗口不足误读成策略失效）。
    #   真实语义 = 「该档尚无足够历史信号，累积中」。故在此统一归零为 None。
    #   放在 _mk_row 本体而非各解析器内，保证同源（各写一套必然漂移）。
    if not row["sample"]:
        row["win_rate"] = None
        row["avg_return"] = None
        if not row["status"]:
            row["status"] = "样本为 0（尚无足够历史信号，该档累积中）"
        elif "样本为 0" not in row["status"] and "累积中" not in row["status"]:
            row["status"] = "样本为 0（该档累积中）；" + row["status"]
    return row


def _hold_days_of(key):
    """从 `hold_20d` / `20` / 20 解析持有天数；解析不出返回 None。

    注意：`_num()` 用 float() 解析 ⇒ 吃不下 `hold_20d` 这种键（返回 None），
    故这里单独补一层数字提取，供 periods 的键使用。
    """
    v = _num(key)
    if v is not None:
        return int(v)
    import re as _re
    m = _re.search(r"(\d+)", str(key))
    return int(m.group(1)) if m else None


# ── 🆕 2026-09-17 小九的股票专家（主人令「星级基准超额数据缺失→从回测产物侧补」）──────
# 基准超额数据层接线：raw_data/market_bench.json（gen_market_bench.py 产出，与策略
# 同入场/出场/成本口径）→ rows[].extra.bench_avg_return / bench_win_rate / bench_days。
# 口径唯一：基准只在数据层算、差值在前端算（index.html __committeePeriods 已按此约定消费）。
# 诚实铁律：按「该行真实信号区间 ∩ 基准覆盖区间」求平均；区间不可解析 → 不写（前端显示 —）；
# 覆盖 <10 个基准交易日 → 不写（宁缺勿滥）；覆盖不满时附 bench_from/bench_to 供核查（不冒充全覆盖）。
_BENCH_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")
_BENCH_YEARS_RE = re.compile(r"近\s*(\d+)\s*年")
_BENCH_MIN_DAYS = 10


def _load_bench(root):
    try:
        p = os.path.join(str(root), "raw_data", "market_bench.json")
        with open(p, encoding="utf-8") as f:
            bd = (json.load(f) or {}).get("by_date") or {}
        return bd or None
    except Exception:
        return None


def _bench_range_of(text, day):
    """signal_date_range 文案 → (start, end)；支持 'YYYY-MM-DD ~ YYYY-MM-DD' 与 '近 N 年'。"""
    if not text:
        return None
    t = str(text)
    m = _BENCH_RANGE_RE.search(t)
    if m:
        a, b = m.group(1), m.group(2)
        return (a, b) if a <= b else (b, a)
    m = _BENCH_YEARS_RE.search(t)
    if m and day:
        try:
            d0 = dt.datetime.strptime(str(day), "%Y-%m-%d").date()
        except Exception:
            return None
        start = (d0 - dt.timedelta(days=365 * int(m.group(1)))).strftime("%Y-%m-%d")
        return (start, str(day))
    return None


def _attach_bench(rows, bench, day):
    n_att = 0
    if not bench:
        return 0
    for r in rows:
        if r.get("hold") is None:
            continue
        hd = _hold_days_of(r["hold"])
        if hd is None:
            continue
        src_rng = r.pop("_src_range", None)
        rng = (_bench_range_of((r.get("extra") or {}).get("signal_date_range"), day)
               or src_rng)
        if not rng:
            continue
        start, end = rng
        vals, wins, days_hit = [], [], []
        for d, per in bench.items():
            if start <= d <= end:
                b = per.get(str(hd)) or {}
                if b.get("avg") is not None:
                    vals.append(b["avg"])
                    wins.append(b.get("win"))
                    days_hit.append(d)
        if len(vals) < _BENCH_MIN_DAYS:
            continue
        ex = r.setdefault("extra", {})
        ex["bench_avg_return"] = round(sum(vals) / len(vals), 4)
        _w = [x for x in wins if x is not None]
        if _w:
            ex["bench_win_rate"] = round(sum(_w) / len(_w), 2)
        ex["bench_days"] = len(vals)
        if days_hit[0] > start or days_hit[-1] < end:
            ex["bench_from"] = days_hit[0]
            ex["bench_to"] = days_hit[-1]
        n_att += 1
    return n_att


def parse_comprehensive(src, obj):
    """BACKTEST_COMPREHENSIVE：共振三档 × **每个持有期一行**（统一 10/12 档矩阵）。

    🔴 2026-09-13 主人令「统一测算标准 · 用最科学的计算」（小九周末审计 P1-2 采纳）：
      原实现「每档只取『最佳持有期』」= 从 12 档里**事后挑最好的那档**报告
      ⇒ 多重比较偏差 / cherry-picking，**系统性高估**该策略；
      且三重共识在 10 档矩阵里只有 1~2 列有数 ⇒ 主人「统一 10 档」的要求只落地了一半
      （与「只加 items 不抬 need = 没加」属同一类「改一半」错误）。
      现改为：**每个持有期各出一行**，全部进矩阵（3 档 × 12 持有期 = 36 行）；
      主口径固定「严格档 · T+5」且**恰好 1 行**（可用 V8_CONSENSUS_PRIMARY_HOLD 覆盖），
      其余档位同为观测值 —— **不再替使用者做「择优」**。
      零样本档由 `_mk_row` 既有兜底自动归 None（绝不用 0 冒充）。

    🔴 2026-09-13 小九审计二次修复（本函数主口径两处错）：
① 主口径原取 **T+20**，与 L54 铁律「主口径刻意取 T+5」矛盾，且四量/CRDS
主口径均为 T+5 ⇒ 卡级主表跨卡横比失效（= 文件头警告的场景）；
      ② 原 `primary=(hd == 主口径)` 使**三档各出 1 行 primary**（共 3 行），
         违反 L638「卡级主表每卡只取 1 行」，且前端取到 band 顺序最前的**宽松档**去评星。
      现：primary 恒为 `CONSENSUS_PRIMARY_BAND · T+CONSENSUS_PRIMARY_HOLD` 一行。
    """
    rows = []
    ov = (obj or {}).get("overview") or {}
    band = [("resonance_all", "共振≥2（宽松）"), ("resonance_gte70_lt80", "共振70-79分"),
            ("resonance_gte80", CONSENSUS_PRIMARY_BAND)]
    primary_hd = _num(__import__("os").environ.get(
        "V8_CONSENSUS_PRIMARY_HOLD", str(CONSENSUS_PRIMARY_HOLD)))
    primary_hd = CONSENSUS_PRIMARY_HOLD if primary_hd is None else int(primary_hd)
    for key, name in band:
        o = ov.get(key)
        per_all = (o or {}).get("periods") or {}
        if not isinstance(o, dict) or not per_all:
            rows.append(_mk_row(src, name, None, None, None, None,
                                status="该分档无有效样本"))
            continue
        for pk in sorted(per_all.keys(), key=lambda x: (_hold_days_of(x) is None,
                                                        _hold_days_of(x) or 0)):
            per = per_all.get(pk) or {}
            hd = _hold_days_of(pk)
            # ⚠️ 唯一一行 primary = 严格档 · 主口径持有期。
            #    label **不得加任何后缀**（如「（主口径）」）：前端 `__committeePeriods()`
            #    把 label 的 T+数字归一成 T+# 后要求与主口径行**逐字相等**，
            #    加后缀会把同档其余 11 档全部过滤掉（实测：12 档退化为 1 档 ⇒ 星级失真）。
            is_primary = (hd is not None and hd == primary_hd
                          and name == CONSENSUS_PRIMARY_BAND)
            lbl = ("%s · T+%d" % (name, hd)) if hd is not None else name
            rows.append(_mk_row(
                src, lbl, per.get("count"),
                per.get("win_rate"), per.get("avg_return"),
                ("T+%d" % hd) if hd is not None else None,
                extra={"best_return": _num(per.get("best_return")),
                       "worst_return": _num(per.get("worst_return")),
                       "max_drawdown": _num(per.get("max_drawdown")),
                       "sharpe": _num(per.get("sharpe_ratio")),
                       "median_return": _num(per.get("median_return")),
                       "decided": _int(per.get("decided")),
                       # 🆕 2026-09-13 主人令「统一测算标准·ret_hold 接线」：
                       #   09-12 新增的**严格持有口径**（忽略中途 stop/target，持到第 hp
                       #   个交易日收盘）此前只写明细、产物/聚合/前端三层全无 ⇒ 功能空转。
                       #   现随旧口径并列下发；缺字段/零样本一律 None（禁止 0 冒充）。
                       "win_rate_hold": _num(per.get("win_rate_hold")),
                       "avg_return_hold": _num(per.get("avg_return_hold")),
                       "count_hold": _int(per.get("count_hold"))},
                primary=is_primary,
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
    """BACKTEST_TDX.summary：每类 K 线信号 × **每个持有期档位** 一行。

    🔴 2026-09-13 主人令（档位扩至 10 档）——真根因修复：
      原实现只取 T+1/T+3/T+5 三档塞进 extra，**长档（T+30…T+250）完全不进 rows**
      ⇒ 前端 10 档矩阵里 K线信号层永远只有 T+1 一列有数。
      更糟的是：源里零样本档写的是 win_rate_30d=0（**0 冒充未知**），
      即使进了 rows 也会被误读成「策略失效」。
      现改为「每个档位一行」，主口径仍标 T+1（该源原始主口径），
      但所有档位都进 rows ⇒ 矩阵完整；零样本档由 _mk_row 统一兜底为 null + 累积中。
    """
    sm = (obj or {}).get("summary") or {}
    rows = []
    if not sm:
        return [_mk_row(src, "—", None, None, None, None, status="无 summary 数据")]
    for k, v in sm.items():
        if not isinstance(v, dict):
            continue
        label = (v.get("label") or k)
        total = _num(v.get("total"))
        for hp in HOLD_LADDER_FULL:
            wr = _num(v.get(f"win_rate_{hp}d"))
            ar = _num(v.get(f"avg_return_{hp}d"))
            win = _num(v.get(f"win_{hp}d"))
            loss = _num(v.get(f"loss_{hp}d"))
            draw = _num(v.get(f"draw_{hp}d"))
            n = None
            if win is not None or loss is not None or draw is not None:
                n = (win or 0) + (loss or 0) + (draw or 0)
            extra = {"total": total, "win": win, "loss": loss, "draw": draw}
            if hp != FULL_LADDER[0]:
                extra["_sibling"] = f"{label}·T+{FULL_LADDER[0]}"
            rows.append(_mk_row(
                src, label, n, wr, ar, f"T+{hp}",
                extra=extra,
                # ⚠️ 必须传 **False** 而非 True：传 True 会被 `bool(ov)` 判真
                #    从而把 12 个档位全标成 is_primary ⇒ 卡级主表出现 12 条同卡重复行。
                primary=False,
            ))
    return rows


def parse_algo_compare(src, obj):
    """ALGO_BACKTEST_COMPARE：多算法同口径聚合，取 T+5 为主口径。

    🔴 2026-09-13 小九审计修复（**假挂链**：挂了链却读不出数，比不挂更隐蔽）：
      scripts/algo_backtest_compare.py 产物的真实结构是
        {"generated":…, "metrics_def":…, "verdict":…,
         "algorithms": {"h_reverse": {"name":…, "rule":…, "source":…,
                                      "summary": {"n_samples":198, "horizons": {"t1":…,"t5":…}}}}}
      而本函数原读 `obj["algos"] or obj["results"]`、且把 `n_samples`/`horizons`
      当**顶层**键取 —— **顶层键名错 + 嵌套层级错**，双重读空 ⇒ 本卡恒返回
      「产物无可用算法行（等待盘后累积）」，强势突破 / H反推 / 高手画像版 三行
      **永远显示「—」**（产物实际有 71 / 198 / 27 条样本）。页面文案还把锅甩给「等待累积」。
      ⇒ 现已兼容两层：顶层键 `algorithms`(真值) → `algos` → `results`；
        样本/持有期改为「顶层优先、再取 summary」。
    """
    rows = []
    algos = ((obj or {}).get("algorithms") or (obj or {}).get("algos")
             or (obj or {}).get("results") or {})
    if isinstance(algos, dict):
        items = algos.items()
    elif isinstance(algos, list):
        items = [(a.get("key") or a.get("algo") or "", a) for a in algos]
    else:
        items = []
    for k, a in items:
        if not isinstance(a, dict):
            continue
        summ = a.get("summary") or {}
        # 扁平结构与「嵌 summary」结构都要能读（见 docstring）
        hs = (a.get("horizons") or summ.get("horizons") or {})
        t5 = hs.get("t5") or {}
        _n = _num(a.get("n_samples"))
        if _n is None:
            _n = _num(summ.get("n_samples"))
        _nm = (a.get("name") or a.get("display_name") or k)
        rows.append(_mk_row(
            src, _nm, _n,
            t5.get("win"), t5.get("avg"), "T+5",
            extra={"hit": _num(t5.get("hit"))},
            status=None if _n else "暂无足够可比历史（等待盘后累积）",
            # 本产物聚合多个算法；只有「强势突破」那一行属于本卡，其余留给其自身卡位
            primary=("强势" in str(_nm)),
        ))
    if not rows:
        return [_mk_row(src, "—", None, None, None, None,
                        status="产物无可用算法行（等待盘后累积）")]
    return rows


def parse_factor_lab(src, obj):
    """FACTOR_LAB_BACKTEST → 交易型行（2026-09-14 主人令「加入因子的」）。

    口径（明示、可复核）：**L1 最强五分位组合** —— 即「因子值最高的那 1/5 标的」
    等权持有。它回答的是「跟着这个因子买最强的那批，各持有期到底赚不赚」，
    与其余策略卡的「信号日买入」同属交易型口径，故 cat=trade，可进策略对比。

    诚实铁律：
      · 档位**动态发现**（扫描 win_{h}d），产物有多少档就出多少行 —— 不硬编码，
        避免「产物加了档、生成器漏改」再次发生；
      · 各档样本数取 n_{h}d（该档真实样本），拿不到则该档不出行，**绝不填 0**；
      · 原「分层价差 / 相对超额」是研究结论（不构成策略收益），
        仍由卡面另一块展示，不再伪装成一行「策略」参与排名；
      · **一张卡只出一条序列**：ROE 侧不产出行（判据见函数尾注释），
        保证本卡 `is_primary` 恰好 1 行 —— 前端 __committeePeriods() 靠它选档，
        多于 1 行会取错档、0 行则星级静默失真。
    """
    import re as _re
    rows = []
    av = (obj or {}).get("abnormal_volume") or {}
    layers = av.get("layers") or {}
    L1 = layers.get("1") or layers.get(1) or {}
    holds = sorted({int(m.group(1)) for k in L1
                    for m in [_re.match(r"^win_(\d+)d$", str(k))] if m})
    for h in holds:
        rows.append(_mk_row(
            src, f"L1最强分位 T+{h}", _num(L1.get(f"n_{h}d")) or _num(L1.get("n")),
            _num(L1.get(f"win_{h}d")), _num(L1.get(f"avg_{h}d")), f"T+{h}",
            extra={"best": _num(L1.get(f"best_{h}d")),
                   "worst": _num(L1.get(f"worst_{h}d")),
                   "factor": "异常量比（缩量=强势）",
                   "layer": "L1 最强五分位"},
            primary=(h == FACTOR_PRIMARY_HOLD),
        ))
    # 🔴 2026-09-14：ROE 侧（obj["roe_largecap"]）**刻意不产出策略行** —— 不是漏掉，是判据。
    #   三条硬理由：
    #   ① **一卡一口径**：卡级主表与档位矩阵都建立在「一张卡 = 一条序列」之上
    #      （`primary` 恰好 1 行 / 前端 __committeePeriods() 取第一条 is_primary 定档）。
    #      L1 与 ROE 是两条不同因子序列，同挂一卡会让主表出现两条同卡行、
    #      档位矩阵出现两条线的「假同源」，正是主人本轮要根治的形态。
    #   ② **口径不可比**：ROE 用的是「**当期** ROE 排名回看历史」，源文件自己写着
    #      methodology_limit「隐含 ROE 排名持续性假设，证据强度弱于量比因子的
    #      point-in-time 分层」。把弱证据塞进同一张胜率排名表，就是本文件
    #      设计铁律②（不把不可比的口径硬塞进同一排名）明令禁止的事。
    #   ③ **不隐瞒**：ROE 的全部真实数值（top30_avg/win/best/worst_{h}d、excess_*）
    #      仍完整保留在 raw_data/factor_lab_backtest.json，并由因子卡自身的
    #      「ROE_TTM 大市值 Top30 vs 全池等权」表原样展示 —— 未被隐藏。
    #   若主人日后要 ROE 单独参评，正确做法是**给它单开一张卡**，而非挤进本卡。
    if not rows:
        return [_mk_row(src, "—", None, None, None, None, status="无分层回测数据（等待下一次因子跑批）")]
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
            r["kind"] = src.get("kind", "strategy")
            r["chain_member"] = src.get("chain_member", True)
            r["chain_note"] = src.get("chain_note")
            if not fresh:
                # 陈旧 ≠ 数字错：陈旧的是「批次」。数值照实保留，只加状态标注（不隐藏）
                r["status"] = (r["status"] + "；" if r["status"] else "") + \
                    f"源未在数据日 {day} 刷新（最后 {r['source_time'] or '未知'}）"
            ov = r.pop("_primary_override", None)
            r["is_primary"] = bool(ov) if ov is not None else (r["label"] == src.get("primary"))
            # 🆕 2026-09-17 基准超额接线：记下该源 summary 的信号区间（供统一补基准）
            r["_src_range"] = (_bench_range_of(((obj or {}).get("summary") or {})
                                               .get("signal_date_range"), day) if obj else None)
            rows.append(r)

    # ── 🆕 2026-09-17 基准超额统一接线（主人令「全站口径统一·诚实」）────────────
    _bench = _load_bench(root)
    _bench_n = _attach_bench(rows, _bench, day)
    print("[bench] 基准超额接线：%d/%d 行补 bench_avg_return" % (_bench_n, len(rows))
          + ("" if _bench else "（raw_data/market_bench.json 不存在或为空 → 本轮不补，前端显示 —）"))

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
        "bench_note": ("基准超额口径：extra.bench_avg_return = 各卡信号区间∩基准覆盖区间的"
                       "全市场等权基准均收益（gen_market_bench.py，与策略同入场/出场/成本口径）；"
                       "前端以 avg_return − bench 求差；区间覆盖不满时附 bench_from/bench_to 供核查。"),
        "chain_kind": kind,
        "chain_note": note + (("；" + extra_note) if extra_note else ""),
        "min_samples": MIN_SAMPLES,
        "low_win_rate": LOW_WIN_RATE,
        "low_avg_return": LOW_AVG_RETURN,
        "sort_rule": "胜率降序 → 平局看平均收益降序（与页内星级对比表同口径）",
# 🔴 2026-09-13 根因修复：本串原先**手写死**，删 RPS 后仍残留「相对强度＝T+5」⇒
#   产物里的口径说明与真实判定不一致（误导）。
        #   现改为**从 SOURCES 派生**（唯一的真值来源），改 SOURCES 即自动同步、永不漂移。
        "primary_rule": ("卡级主表每卡只取 1 行既定主口径（"
                         + "；".join(f"{s['card']}＝{s['primary']}"
                                    for s in SOURCES if s.get("primary"))
                         + "），**不跨持有期横比**；"
                         f"且**样本 < {MIN_SAMPLES} 不进主表**（累积不足不排名）。"
"🔴 候选池 / 金股池(=黄金池) 是算法**上游水源**（基础股池），不是选股策略，"
"**不做回测、不进本表、不进下架提请**（2026-09-14 主人令）。"),
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
# 🔴 2026-09-14 主人令：候选池 / 金股池是**上游水源**（基础股池），不是选股策略
#   ⇒ 既不做回测，也**不作为「缺回测的算法卡」登记**（它们本就不该有回测）。
    known_gaps = [
        {"card": "机游共振", "page": "盘后数据", "status": "⚪ 无独立前向收益回测"},
    ]
    have = {c["card"] for c in out}
    for g in known_gaps:
        if g["card"] not in have:
            out.append(g)
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

    # 🔴 2026-09-12 主人令（拍板第 1 项·②）：低绩效策略下架提醒接**邮件主动触达**。
    #   主人原话：「回测累积到一定时间，收益率和胜率低的要提醒我是否要下架不再跟踪。」
    #   设计取舍（**刻意**如此，勿改）：
    #     · 提醒逻辑放在独立脚本 scripts/v8_delist_advice.py，不写进本聚合器 ——
    #       否则本脚本会依赖 SMTP 配置/网络，一旦邮件通道异常就把 E 批链尾搞红，
    #       连带 BACKTEST_ALL_ALGOS.js 都产不出（本末倒置）。
    #     · 用 subprocess 且 check=False + timeout：提醒失败**绝不**影响回测产物落盘。
    #     · 不新增 workflow / 不新增 cron ⇒ 不动云端与本机的时窗矩阵，零新竞态。
    #     · 提醒用**窄口径**（胜率<40% 且样本≥20），页面用宽口径（45%/30）——
    #       不同值是故意的：页面宁多看，邮件宁少扰。详见该脚本 docstring。
    try:
        import subprocess
        _adv = os.path.join(ROOT, "scripts", "v8_delist_advice.py")
        if os.path.isfile(_adv):
            _r = subprocess.run(
                [sys.executable, _adv, "--quiet-ok"],
                cwd=str(ROOT), capture_output=True, text=True,
                timeout=120, encoding="utf-8", errors="replace")
            for _ln in (_r.stdout or "").strip().splitlines():
                print("    [delist] " + _ln)
            if _r.returncode != 0:
                print(f"    ⚠️ 下架提醒脚本退出码 {_r.returncode}（不影响回测产物）")
        else:
            print("    ⚠️ 未找到 scripts/v8_delist_advice.py → 跳过下架提醒")
    except Exception as _e:
        # 提醒是**尽力而为**：任何异常都不许影响回测产物（产物已落盘，这才是主任务）
        print(f"    ⚠️ 下架提醒调用异常（{_e.__class__.__name__}）：{_e}")
        print("       → 不影响回测产物；可手动 python scripts/v8_delist_advice.py 补发")
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
