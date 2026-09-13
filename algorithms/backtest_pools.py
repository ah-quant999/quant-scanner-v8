#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_pools.py — 候选池 / 金股池 前向收益回测（2026-09-13 主人令）

主人原话：「只要接入算法链的选股策略，都要有回测，这样才能完整观测到底靠不靠谱。
马上把所有接入算法链的选股策略都按5、10、20、30、45、60、75、90、180、250日
的跟踪回测，详细记录在策略回测页。」

背景：候选池（CANDIDATE）与金股池（GOLD_POOL）**已接入盘后算法链**（B 批
build_candidate_pool.py / scanner.py 产出），但**从来没有独立的前向收益回测** ——
在 gen_backtest_all_algos.py 的 coverage 里一直是 known_gaps 硬编码占位。
本脚本补齐这个缺口，使「接了链的选股策略 = 必有回测」成为结构性保证。

【设计铁律 · 不得造假】
  1. **未知一律 null，绝不用 0 冒充**。样本不足的档位 → samples=0 且 win_rate/avg_return
     为 null，前端显示「累积中」；绝不把「没算到」画成「0% 胜率」。
  2. **信号历史多长就只算多长**。候选池信号自 2026-08-29 起、金股池自 2026-09-07 起，
     **不允许**用其它数据源或猜测值填充长档（180/250 现必然为空，如实标注就绪日期）。
  3. **真实价格**。前向收益一律用 baostock 真实前复权日K收盘价，扣双边成本 0.3%。
  4. **入场口径与全站一致**：信号日**次一交易日开盘价**买入（避免用信号日收盘价
     自我实现），持有到第 N 个真实交易日**收盘价**卖出。

数据源：
  · raw_data/candidate_members.json  —— 候选池成员（first_seen = 首次进池日）
  · raw_data/gold_pool.json          —— 金股池（first_date = 首次满足信号日）

输出：
  · raw_data/candidate_backtest.json / data/CANDIDATE_BACKTEST.js
  · raw_data/gold_pool_backtest.json / data/GOLD_POOL_BACKTEST.js

用法：
  python algorithms/backtest_pools.py                # 全跑
  python algorithms/backtest_pools.py --pool candidate   # 只跑候选池
  python algorithms/backtest_pools.py --dry          # 只打印统计，不写文件
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

# ── 与其余四个回测脚本**同源**的持有期阶梯（唯一真源；各写一套必然漂移）──
HOLD_LADDER = [5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
HOLD_PERIODS = [1, 3] + HOLD_LADDER

COST_BPS = 15                 # 单边万分之1.5 → 双边 0.3%
REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "raw_data"
DATA = REPO / "data"

try:
    import baostock as bs
except ImportError:
    bs = None


def now_cst():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return dt.datetime.utcnow() + dt.timedelta(hours=8)


# ────────────────────────── baostock 助手 ──────────────────────────
def bs_code(code, market=None):
    """6/9 开头 → sh，其余 → sz（与 v8 全站口径一致）。"""
    c = str(code).zfill(6)
    if market in ("sh", "sz"):
        return market + "." + c
    if c.startswith(("6", "9", "5")):
        return "sh." + c
    return "sz." + c


class KlineCache:
    """按 code 缓存整段日K（含 380 自然日窗口），避免每档重复请求。

    250 交易日 ≈ 365 自然日 → 预留 380。**不扩窗口则长档静默零样本**
    （2026-09-12 与 09-13 各踩一次的坑，务必保留此注释）。
    """

    LOOKBACK_DAYS = 30
    LOOKAHEAD_DAYS = 380

    def __init__(self):
        self._c = {}
        self.calls = 0
        self.fails = 0

    def get(self, code, market, center_date):
        key = (code, center_date)
        if key in self._c:
            return self._c[key]
        rows = []
        if bs is not None:
            try:
                d = dt.datetime.strptime(center_date, "%Y-%m-%d").date()
                start = (d - dt.timedelta(days=self.LOOKBACK_DAYS)).strftime("%Y-%m-%d")
                end = (d + dt.timedelta(days=self.LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")
                r = bs.query_history_k_data_plus(
                    bs_code(code, market), "date,open,close",
                    start_date=start, end_date=end,
                    frequency="d", adjustflag="2",   # 2 = 前复权
                )
                self.calls += 1
                while r.error_code == "0" and r.next():
                    x = r.get_row_data()
                    if x and x[0] and x[2]:
                        try:
                            rows.append((x[0], float(x[1]) if x[1] else None, float(x[2])))
                        except ValueError:
                            pass
            except Exception:
                self.fails += 1
        self._c[key] = rows
        return rows


def forward_returns(rows, signal_date, periods):
    """信号日**次一交易日开盘**买入 → 持有到第 p 个真实交易日**收盘**卖出。

    🔴 2026-09-13 修正（本轮实测发现的口径 bug）：
       候选池 / 金股池会把信号日期记在**休市日**上（实测 08-29 周六 285 条、
       08-30 周日 6 条、09-12 周六 2 条）。原实现用 `d >= signal_date` 找位置，
       会把休市日信号对齐到**其后**第一个交易日 ⇒ 入场日整体后移一天，
       相当于多等一天才买（与全站「信号日次一交易日开盘买入」口径不符）。
       正确做法：**先把信号日回退到 ≤ 它的最近一个交易日**，再取其次日开盘。
       若无更早交易日可用（信号日早于 K 线起点）则放弃该样本（不出 0 冒充）。

    返回 {p: pct}，缺数据的档位**不出现在结果里**（由调用方落 null，不用 0 冒充）。
    """
    out = {}
    if not rows:
        return out
    # ① 信号日回退到 ≤ signal_date 的**最后一个**交易日（处理休市日信号）
    idx = None
    for i, (d, _o, _c) in enumerate(rows):
        if d <= signal_date:
            idx = i
        else:
            break
    if idx is None:
        # 信号日早于 K 线起点 → 无法定位，放弃（不猜）
        return out
    # ② 入场 = 次一交易日开盘（缺失则用其收盘）
    if idx + 1 >= len(rows):
        return out          # 次日尚未发生 → 该档不可算（如实留空）
    _d, o, c = rows[idx + 1]
    entry = o if (o and o > 0) else (c if c and c > 0 else None)
    base = idx + 1
    if not entry or entry <= 0:
        return out
    for p in periods:
        j = base + p
        if j < len(rows):
            px = rows[j][2]
            if px and px > 0:
                gross = (px / entry - 1.0) * 100.0
                out[p] = round(gross - 2 * COST_BPS / 100.0, 2)   # 扣双边成本
    return out


def agg(per_signal):
    """把逐信号收益聚合成档位统计。**样本 0 → 全部字段为 null**（不用 0 冒充）。"""
    out = {}
    for p in HOLD_PERIODS:
        vals = [d[p] for d in per_signal if p in d]
        if not vals:
            out[str(p)] = {"samples": 0, "win_rate": None, "avg_return": None,
                           "best_return": None, "worst_return": None,
                           "win_avg": None, "loss_avg": None}
            continue
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v <= 0]
        # 胜率 = win/(win+loss)，与全站 by_period 口径一致
        wr = round(len(wins) / len(vals) * 100.0, 2) if vals else None
        out[str(p)] = {
            "samples": len(vals),
            "win_rate": wr,
            "avg_return": round(sum(vals) / len(vals), 2),
            "best_return": round(max(vals), 2),
            "worst_return": round(min(vals), 2),
            "win_avg": round(sum(wins) / len(wins), 2) if wins else None,
            "loss_avg": round(sum(losses) / len(losses), 2) if losses else None,
        }
    return out


# ────────────────────────── 两个池的取信号 ──────────────────────────
def load_candidate_signals():
    """候选池：first_seen = 首次进池日（= 信号日）。

    ⚠️ 候选池是「成交额前N活跃」硬筛，不是择时信号 —— 但主人要求接到链的
       都要有回测，且这正是「观测它到底靠不靠谱」的正当方式。
    """
    p = RAW / "candidate_members.json"
    if not p.exists():
        return [], "raw_data/candidate_members.json 不存在"
    o = json.loads(p.read_text(encoding="utf-8"))
    sigs = []
    for v in (o.get("stocks") or {}).values():
        fd = v.get("first_seen")
        if not fd:
            continue
        sigs.append({"code": v.get("code"), "name": v.get("name"),
                     "market": v.get("market"), "date": fd,
                     "sources": v.get("sources") or []})
    sigs.sort(key=lambda x: x["date"])
    return sigs, None


def load_gold_signals():
    """金股池：first_date = 首次满足信号日。

    只取 first_signal >= 2（多信号共振）作为「强信号」样本 —— 这与前端金股池
    展示口径一致（signal_count 即硬筛条件）；同时保留全部信号作为对照。
    """
    p = RAW / "gold_pool.json"
    if not p.exists():
        return [], "raw_data/gold_pool.json 不存在"
    o = json.loads(p.read_text(encoding="utf-8"))
    sigs = []
    for v in (o.get("stocks") or {}).values():
        fd = v.get("first_date")
        if not fd:
            continue
        sigs.append({"code": v.get("code"), "name": v.get("name"),
                     "market": v.get("market"), "date": fd,
                     "first_signal": v.get("first_signal"),
                     "board_label": v.get("board_label")})
    sigs.sort(key=lambda x: x["date"])
    return sigs, None


def run_pool(name, sigs, cache, note):
    """对一组信号跑全部持有期。"""
    per_signal = []
    dates = sorted({s["date"] for s in sigs})
    for s in sigs:
        rows = cache.get(s["code"], s.get("market"), s["date"])
        fr = forward_returns(rows, s["date"], HOLD_PERIODS)
        if fr:
            per_signal.append(fr)
    return {
        "pool": name,
        "signal_date_range": (f"{dates[0]} ~ {dates[-1]}" if dates else None),
        "signal_days": len(dates),
        "total_signals": len(sigs),
        "priced_signals": len(per_signal),
        "by_period": agg(per_signal),
        "note": note,
    }


def readiness(sig_days, last_date):
    """算「长档何时可算」—— 如实告知，不装作已有。"""
    out = {}
    if not last_date:
        return out
    try:
        d = dt.datetime.strptime(last_date, "%Y-%m-%d").date()
    except ValueError:
        return out
    for p in HOLD_LADDER:
        # 需再积累 p 个交易日 ≈ p*7/5 自然日（粗略，仅作预期提示）
        need = d + dt.timedelta(days=int(p * 7 / 5) + 1)
        out[str(p)] = need.strftime("%Y-%m-%d")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", choices=["candidate", "gold", "all"], default="all")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-baostock", action="store_true", help="离线：只统计信号数，不拉价格")
    a = ap.parse_args()

    global bs
    if a.no_baostock:
        bs = None
    if bs is not None:
        lg = bs.login()
        if lg.error_code != "0":
            print("[baostock] login failed:", lg.error_code, lg.error_msg)
            bs = None
        else:
            print("[baostock] login ok")

    cache = KlineCache()
    now = now_cst()
    print("[backtest_pools] %s" % now.strftime("%Y-%m-%d %H:%M:%S"))
    print("  持有期阶梯:", HOLD_PERIODS)
    print("  成本: 双边 %.2f%%" % (2 * COST_BPS / 100))

    results = {}

    if a.pool in ("candidate", "all"):
        sigs, err = load_candidate_signals()
        if err:
            print("  [候选池] %s" % err)
        else:
            print("\n[候选池] 信号 %d 条" % len(sigs))
            r = run_pool("候选池", sigs, cache,
                         "候选池「首次进池日」次一交易日开盘买入、持有 N 个真实交易日收盘卖出"
                         "（前复权·扣双边 0.3%）。候选池为成交额活跃度硬筛。")
            r["readiness"] = readiness(r["signal_days"], (r["signal_date_range"] or "").split(" ~ ")[-1])
            results["candidate"] = r
            _show(r)

    if a.pool in ("gold", "all"):
        sigs, err = load_gold_signals()
        if err:
            print("  [金股池] %s" % err)
        else:
            print("\n[金股池] 信号 %d 条" % len(sigs))
            r = run_pool("金股池", sigs, cache,
                         "金股池「首次满足信号日」次一交易日开盘买入、持有 N 个真实交易日收盘卖出"
                         "（前复权·扣双边 0.3%）。含多信号共振硬筛。")
            r["readiness"] = readiness(r["signal_days"], (r["signal_date_range"] or "").split(" ~ ")[-1])
            results["gold"] = r
            _show(r)

    print("\n[baostock] 请求 %d 次，失败 %d 次" % (cache.calls, cache.fails))

    if a.dry:
        print("\n--dry：不写文件")
        return 0

    # ── 写产物 ──
    mapping = [("candidate", "candidate_backtest.json", "CANDIDATE_BACKTEST.js",
                "CANDIDATE_BACKTEST", "候选池"),
               ("gold", "gold_pool_backtest.json", "GOLD_POOL_BACKTEST.js",
                "GOLD_POOL_BACKTEST", "金股池")]
    end_day = None
    for key, jf, js, var, label in mapping:
        r = results.get(key)
        if r is None:
            continue
        obj = {
            "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "calc_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "card": label,
            "method": r["note"],
            "cost_bps_per_side": COST_BPS,
            "cost_adjusted": True,
            "hold_periods": HOLD_PERIODS,
            "signal_date_range": r["signal_date_range"],
            "signal_days": r["signal_days"],
            "total_signals": r["total_signals"],
            "priced_signals": r["priced_signals"],
            "readiness": r["readiness"],
            "honesty_note": ("样本不足的档位 samples=0 且 win_rate/avg_return 为 null"
                             "（前端显示「累积中」），绝不用 0 冒充；长档就绪日期为按交易日"
                             "推算的预期值，非承诺。"),
            "summary": {
                "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "calc_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "method": r["note"],
                "signal_date_range": r["signal_date_range"],
                "cost_bps_per_side": COST_BPS,
                "cost_adjusted": True,
                "total_signals": r["total_signals"],
                "by_period": r["by_period"],
            },
        }
        (RAW / jf).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        (DATA / js).write_text(
            "/* %s 前向收益回测 — backtest_pools.py 产出（2026-09-13 主人令） */\n"
            "window.%s = %s;\n" % (label, var, json.dumps(obj, ensure_ascii=False)),
            encoding="utf-8")
        print("  -> wrote raw_data/%s + data/%s" % (jf, js))
        end_day = obj["update_time"]

    if bs is not None:
        try:
            bs.logout()
        except Exception:
            pass
    return 0


def _show(r):
    print("  信号区间 %s（%d 个交易日，%d 条信号，成功定价 %d 条）"
          % (r["signal_date_range"], r["signal_days"], r["total_signals"], r["priced_signals"]))
    for p in HOLD_PERIODS:
        d = r["by_period"][str(p)]
        if d["samples"]:
            print("     T+%-4d n=%-5d 胜率=%-7s 均值=%s%%" % (p, d["samples"], d["win_rate"], d["avg_return"]))
        else:
            print("     T+%-4d 累积中（样本 0）" % p)


if __name__ == "__main__":
    sys.exit(main())
