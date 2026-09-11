#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_delist_advice.py — 低绩效策略「是否下架」主动提醒（邮件触达）

主人 2026-09-11 令：「回测累积到一定时间，收益率和胜率低的要提醒我是否要下架不再跟踪。」
主人 2026-09-12 拍板第 1 项·②：**接邮件主动触达**，复用 2814546@qq.com 通道。

【设计铁律 · 不得造假】
  1. **只报真达标项**：样本 < MIN_SAMPLES(20) 一律不提下架建议 —— 小样本噪声会
     把「n=4 胜率 100%」推上榜首，也会把「n=3 胜率 0%」误判为低绩效（实为运气）。
     未达标项进「观察区」如实列出，但**不构成下架问题**。
  2. **源不在链内的不提议下架**：数据可能残缺，先修产出再评估（与
     gen_backtest_all_algos.py 的 advice/watch 分流同源）。
  3. **未知一律「—」**：win_rate / avg_return 为 null 时前端与邮件都显示「—」，
     绝不用 0 冒充。
  4. **不重复轰炸**：同一卡在 N 天内已发过建议 → 跳过（状态落在
     raw_data/_delist_advice_state.json，本机/runner 运行态）。除非绩效**进一步恶化**
     （胜率再降 ≥5pt），否则不重发。

【阈值（主人 2026-09-12 拍板）】
  DELIST_WIN_RATE = 40.0   # 胜率红线
  DELIST_MIN_N    = 20     # 累积样本门槛（**双条件同时满足才发信**）
  🔴 与 gen_backtest_all_algos.py 的 LOW_WIN_RATE=45 / MIN_SAMPLES=30 **刻意不同值**：
     · 那里是「页面上标黄/进观察名单」的宽口径（宁可多看）；
     · 这里是「发邮件打扰主人」的窄口径（宁可少发）。
     两个口径**不同源是故意的**，不是漂移 —— 已在两处注释互相指明。
     ⚠️ 也因此，本脚本**不 import** 那边的常量，避免有人误改成同源后把邮件闸门放宽。

【数据源】data/BACKTEST_ALL_ALGOS.js 的 delist_advice + watch_list（由 E 批
  gen_backtest_all_algos.py 产出）。本脚本**不重复计算**回测，只做「读 → 判 → 发信」。

【为什么不做成 workflow】避免新增定时任务与双机抢单；由 E 批链尾的
  gen_backtest_all_algos.py --notify 触发（同一次运行、同一份数据，零额外调度）。

用法：
  python scripts/v8_delist_advice.py            # 读产物 → 判定 → 达标则发信
  python scripts/v8_delist_advice.py --dry      # 只打印不发信（演练）
  python scripts/v8_delist_advice.py --force    # 忽略「N 天内已发」抑制
  python scripts/v8_delist_advice.py --file data/BACKTEST_ALL_ALGOS.js   # 指定产物
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

# ── 阈值（窄口径·发邮件用；与页面宽口径刻意不同，见 docstring）──
DELIST_WIN_RATE = 40.0    # 胜率红线（低于此判低绩效）
DELIST_MIN_N = 20         # 累积样本门槛（低于此不评估下架）
DELIST_AVG_RETURN = 0.0   # 平均收益红线（≤ 此判低收益；已扣成本口径）
RESEND_SUPPRESS_DAYS = 7  # 同一卡 N 天内不重发
RESEND_WORSEN_PT = 5.0    # 但胜率再降 ≥ 此值 → 破例重发

STATE = RAW / "_delist_advice_state.json"
DEFAULT_PRODUCT = DATA / "BACKTEST_ALL_ALGOS.js"


def now_cst():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return dt.datetime.utcnow() + dt.timedelta(hours=8)


def load_product(path):
    """解析 data/BACKTEST_ALL_ALGOS.js 的 window.X = {...};。返回 (obj, 原因)。"""
    p = Path(path)
    if not p.exists():
        return None, "产物不存在"
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
    """数值归一：None/空/NaN → None（绝不用 0 冒充）。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return None if (f != f or f in (float("inf"), float("-inf"))) else f
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_state():
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1),
                         encoding="utf-8", newline="\n")
    except Exception as e:
        print(f"  ⚠️ 状态写盘失败（不影响发信）：{e.__class__.__name__}")


def _fmt(v, unit="%"):
    """None → 「—」（绝不用 0 冒充）。整数型不带小数点。"""
    if v is None:
        return "—"
    f = float(v)
    if f == int(f):
        return f"{int(f)}{unit}"
    return f"{f:g}{unit}"


def _reasons(a):
    """**按本脚本的窄口径重算**触发原因。

    ⚠️ 不能直接用产物里的 `reasons` —— 那是 gen_backtest_all_algos.py 用**宽口径**
       （LOW_WIN_RATE=45）写的，直接引用会让邮件里出现「胜率 38.2% < 红线 45%」
       而正文又写「本邮件门槛 < 40%」⇒ 自相矛盾（实测踩到）。
    正解：以本脚本常量重算，产物 reasons 仅在重算为空时作为补充说明。
    """
    out = []
    wr, ar = _num(a.get("win_rate")), _num(a.get("avg_return"))
    if wr is not None and wr < DELIST_WIN_RATE:
        out.append(f"胜率 {_fmt(wr)} < 红线 {DELIST_WIN_RATE:g}%")
    if ar is not None and ar <= DELIST_AVG_RETURN:
        out.append(f"平均收益 {_fmt(ar)} ≤ 红线 {DELIST_AVG_RETURN:g}%（已扣成本）")
    if not out:
        # 落到这里说明产物判定与本地口径不一致 → 如实标注，绝不伪装成达标
        out = list(a.get("reasons") or [])
        if out:
            out.append(f"（注：本行按页面宽口径触发；本邮件窄口径为胜率<{DELIST_WIN_RATE:g}%"
                       f"且样本≥{DELIST_MIN_N}）")
    return out


def judge(obj, force=False, state=None):
    """返回 (应发建议列表, 观察列表, 抑制说明列表, 待落盘状态)。

    🔴 2026-09-12 修正（实测踩到）：原实现内部 `load_state()`/`save_state()`，
    而 main() 又写 `save_state(load_state())` —— **后者从磁盘重读、把 judge() 的
    内存更新整个丢掉** ⇒ 抑制永不生效（实测 run2/run3 全未抑制）。
    正解：judge() 只做纯判定并**返回**新 state；落盘由 main() 在「确认发信成功」后做
    （也避免 --dry 演练把项标成已发）。
    """
    if not isinstance(obj, dict):
        return [], [], ["产物结构异常（非 dict）"], dict(state or {})

    # 优先用产物自带的 delist_advice（它已做过「链内 + 样本达标」分流）；
    # 若产物结构变化，退化为从 rows 自算（保持本脚本可独立工作）。
    advice = obj.get("delist_advice") or []
    watch = obj.get("watch_list") or []
    rows = obj.get("rows") or []

    if not advice and not watch and rows:
        advice, watch = _from_rows(rows)

    state = dict(state if state is not None else load_state())
    today = now_cst()
    hit, suppressed = [], []

    for a in advice:
        card = a.get("card") or "?"
        wr, n = _num(a.get("win_rate")), _num(a.get("sample")) or 0
        ar = _num(a.get("avg_return"))

        # 双条件闸门（窄口径）：胜率 < 红线 **且** 累计样本 ≥ 门槛
        if wr is None or n < DELIST_MIN_N or wr >= DELIST_WIN_RATE:
            # 未达发信门槛 → 降级为观察（如实说明为何不发）
            why = []
            if n < DELIST_MIN_N:
                why.append(f"样本 {int(n)} < {DELIST_MIN_N}")
            if wr is None:
                why.append("胜率未知")
            elif wr >= DELIST_WIN_RATE:
                why.append(f"胜率 {_fmt(wr)} ≥ 红线 {DELIST_WIN_RATE}%")
            watch.append(dict(a, note="未达发信门槛（" + "；".join(why) + "）"))
            continue

        # 去重抑制
        prev = state.get(card)
        if prev and not force:
            try:
                last = dt.datetime.fromisoformat(prev.get("sent_at"))
            except Exception:
                last = None
            if last is not None:
                days = (today.replace(tzinfo=None) - last).days
                if days < RESEND_SUPPRESS_DAYS:
                    prev_wr = _num(prev.get("win_rate"))
                    worsen = (prev_wr is not None and wr <= prev_wr - RESEND_WORSEN_PT)
                    if not worsen:
                        suppressed.append(
                            f"{card}：{days} 天前已发（胜率 {_fmt(prev_wr)} → {_fmt(wr)}，"
                            f"未恶化 ≥{RESEND_WORSEN_PT:g}pt）")
                        continue
        hit.append(dict(a, win_rate=wr, sample=n, avg_return=ar, reasons=_reasons(a)))
        state[card] = {"sent_at": today.replace(tzinfo=None).isoformat(timespec="seconds"),
                       "win_rate": wr, "sample": n}
    return hit, watch, suppressed, state


def _from_rows(rows):
    """产物无 advice 字段时的兜底：从 rows 自算（仅交易型 + 主口径 + 链内）。"""
    advice, watch = [], []
    cat_ok = {"trade"}
    for r in rows:
        if r.get("cat") not in cat_ok or not r.get("is_primary"):
            continue
        wr, n = _num(r.get("win_rate")), _num(r.get("sample")) or 0
        ar = _num(r.get("avg_return"))
        reasons = []
        if wr is not None and wr < DELIST_WIN_RATE:
            reasons.append(f"胜率 {wr:g}% < 红线 {DELIST_WIN_RATE:g}%")
        if ar is not None and ar <= DELIST_AVG_RETURN:
            reasons.append(f"平均收益 {ar:g}% ≤ 红线 {DELIST_AVG_RETURN:g}%（已扣成本）")
        if not reasons:
            continue
        entry = {"card": r.get("card"), "label": r.get("label"),
                 "sample": n, "win_rate": wr, "avg_return": ar, "reasons": reasons,
                 "source_time": r.get("source_time")}
        if not r.get("chain_member", True):
            entry["note"] = r.get("chain_note") or "该源不在盘后算法链内"
            watch.append(entry)
        elif n < DELIST_MIN_N:
            entry["note"] = f"样本 {n} < 门槛 {DELIST_MIN_N}，累积不足，仅观察"
            watch.append(entry)
        else:
            entry["ask"] = f"是否下架「{entry['card']}」并停止跟踪？"
            advice.append(entry)
    return advice, watch


def build_mail(advice, watch, suppressed, obj):
    """构造邮件主题与正文。"""
    day = obj.get("data_day") or "?"
    n = len(advice)
    subject = f"【v8·策略下架建议】{n} 个策略绩效低于红线（数据日 {day}）"

    L = []
    L.append(f"主人：")
    L.append("")
    L.append(f"E 批回测已跑完（数据日 {day}），按「胜率 < {DELIST_WIN_RATE:g}% 且累计样本 ≥ {DELIST_MIN_N}」"
             f"双条件筛查，有 **{n} 个策略** 达到下架评估门槛，请您决定是否停止跟踪：")
    L.append("")
    for i, a in enumerate(advice, 1):
        L.append(f"{i}. {a.get('icon','')}【{a.get('card')}】{a.get('label','')}")
        L.append(f"   胜率 {_fmt(a.get('win_rate'))} ｜ 平均收益 {_fmt(a.get('avg_return'))} ｜ "
                 f"样本 {int(_num(a.get('sample')) or 0)}")
        rs = _reasons(a)
        if rs:
            L.append(f"   触发原因：{'；'.join(rs)}")
        if a.get("source_time"):
            L.append(f"   产物时间：{a['source_time']}"
                     + ("" if a.get("fresh") else "（⚠️ 非本数据日刷新）"))
        L.append("")

    L.append("─" * 46)
    L.append(f"【只观察、不建议下架】{len(watch)} 项（样本不足 / 源不在链内 / 未达双条件）：")
    if watch:
        for w in watch:
            L.append(f"  · {w.get('card')}·{w.get('label','')}  胜率 {_fmt(_num(w.get('win_rate')))}  "
                     f"样本 {int(_num(w.get('sample')) or 0)}  — {w.get('note','')}")
    else:
        L.append("  （无）")
    L.append("")

    if suppressed:
        L.append(f"【本次抑制重发】{len(suppressed)} 项（{RESEND_SUPPRESS_DAYS} 天内已发且未恶化 "
                 f"≥{RESEND_WORSEN_PT:g}pt）：")
        for s in suppressed:
            L.append(f"  · {s}")
        L.append("")

    L.append("─" * 46)
    L.append("口径说明（务必知悉，避免误判）：")
    L.append(f"  · 本邮件门槛 **胜率 < {DELIST_WIN_RATE:g}% 且 样本 ≥ {DELIST_MIN_N}** —— 双条件同时满足。")
    L.append("    页面上标黄/进观察用的是更宽的阈值（胜率 45% / 样本 30），那是「多看」；")
    L.append("    这里发邮件用的是更窄的阈值，是「少打扰」。两者不同值是刻意的。")
    L.append("  · 平均收益为**扣双边 0.3% 成本**后的净收益；胜率为净收益 > 0 的占比。")
    L.append("  · 样本不足不下架建议：n=4 胜率 100% 与 n=3 胜率 0% 都是运气，不是绩效。")
    L.append("  · 源不在算法链内的产物（数据可能残缺）只列观察，不提议下架。")
    L.append("")
    L.append(f"完整明细见 data/BACKTEST_ALL_ALGOS.js（策略回测页）。")
    L.append(f"邮件由 scripts/v8_delist_advice.py 于 {now_cst():%Y-%m-%d %H:%M:%S} 生成。")
    return subject, "\n".join(L)


def _notify(subject, body, dry=False):
    """经 v8_send_alert 统一闸门发信（level=stale：非交易日静默，属设计预期）。"""
    if dry:
        print("  --dry：不发信。主题预览：")
        print("   ", subject)
        return True
    try:
        sys.path.insert(0, str(ROOT))
        from v8_send_alert import send_alert, LEVEL_STALE
        return send_alert(subject, body, level=LEVEL_STALE)
    except Exception as e:
        print(f"  ⚠️ 邮件通道不可用（{e.__class__.__name__}）：{e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(DEFAULT_PRODUCT))
    ap.add_argument("--dry", action="store_true", help="只打印不发信")
    ap.add_argument("--force", action="store_true", help="忽略 N 天重发抑制")
    ap.add_argument("--quiet-ok", action="store_true", help="无建议时不打印成功行（供链内静默）")
    a = ap.parse_args()

    print(f"[v8_delist_advice] {now_cst():%Y-%m-%d %H:%M:%S}")
    obj, err = load_product(a.file)
    if obj is None:
        # 产物缺失 = 真问题，但**不在此处报警**（它已由健康巡检亮红灯；
        # 重复报警是噪音）。退出码 0 以免拖垮 E 批链。
        print(f"  ⚠️ 产物不可用（{err}）→ 跳过（健康巡检会独立告警，此处不重复）")
        return 0

    advice, watch, suppressed, new_state = judge(obj, force=a.force)
    print(f"  数据日={obj.get('data_day')}  达标建议={len(advice)}  "
          f"观察={len(watch)}  抑制={len(suppressed)}")
    for x in advice:
        print(f"    ⚠️ {x.get('card')} → {'；'.join(x.get('reasons') or [])}"
              f"（n={int(_num(x.get('sample')) or 0)}）")
    for s in suppressed:
        print(f"    ⏸ {s}")

    if not advice:
        if not a.quiet_ok:
            print("  ✅ 无达到下架评估门槛的策略 → 不发邮件（避免噪音）")
        return 0

    subject, body = build_mail(advice, watch, suppressed, obj)
    if a.dry:
        print("  --dry：不发信、不落盘抑制状态")
        return 0
    ok = _notify(subject, body, dry=False)
    if ok:
        # 🔴 只有真发信成功才落盘 —— 否则发送失败会被标成「已发」而静默 7 天
        save_state(new_state)
        print(f"  ✅ 已发信并记录抑制状态（{RESEND_SUPPRESS_DAYS} 天内不重发）")
    else:
        print("  ⚠️ 发信未成功 → **不落盘**抑制状态（下次仍会尝试，不漏报）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
