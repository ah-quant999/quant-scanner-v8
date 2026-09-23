#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_crds.py — CRDS 逆势龙头（advanced 档位）历史回测

背景：
  CRDS_CARD_DATA 将信号分为 elite / advanced / watch 三档，
  其中 advanced 为默认主推档（cond1+cond3 重合或得分前列）。

本脚本：
  1. 读取 out/history/crds_*.json + raw_data/history/crds_*.json 历史 CRDS 输出。
  2. 取每日 advanced 列表作为信号（信号日收盘价买入）。
  3. 用 baostock 拉取信号股日K线，计算 T+1/T+3/T+5/T+10/T+20 持有期收益。
  4. 输出 raw_data/crds_backtest.json + data/CRDS_BACKTEST.js。

输出字段（与 HUNTER_BACKTEST 同构，便于前端统一渲染）：
  - summary: update_time, total_signals, calc_time, method, signal_date_range,
             by_period {1/3/5/10/20: {samples, win_rate, avg_return, best_return, worst_return, ...}}
  - signals: 逐信号明细

使用：
  python v8/backtest_crds.py                # 全量回测
  python v8/backtest_crds.py --dry          # 只统计信号数，不拉K线
  python v8/backtest_crds.py --allow-empty  # 人工强制写空骨架（默认绝不用空覆盖好数据）

🔴 2026-09-23 主人令「一劳永逸」（阿狸咪的工程师）：
  本产物是累积型（一次运行覆盖 8/1 以来全部历史信号）。原口径「baostock 登录失败 /
  无历史信号 ⇒ 降级为空回测并写盘」会把积累多日的成果整份抹成 0 ⇒ 前端「逆势龙头·真实回测」
  整卡变空（主人 2026-09-23 截图：12 档 samples 全 0，method 字段自证 "baostock 登录失败，自动降级"）。
  该口径与 algorithms/calc_crds.py::_write_empty_crds_output 的 2026-09-06 主人令
  （「数据源异常时空产物不再覆盖旧数据 —— 空卡比 stale 更伤」）直接冲突 ⇒ 本脚本对齐后者：
    · 已有有效成果（total_signals>0 或任一档有样本）⇒ 保留旧产物、不写盘，仅打印 KEEP 告警；
    · 从未有过有效成果 ⇒ 才写空骨架（诚实空）；
    · 需人工清零时必须显式 --allow-empty（可审计）。
  另：baostock 为免费源且全仓 20+ 脚本共用，同账号并发登录会互踢 ⇒ 登录改为多次重试。

注意：
  - 历史文件时间戳为文件名后 8 位 yyyymmdd，优先取文件内的 update_time/data_time。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import baostock as bs
except ImportError:
    bs = None

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
HISTORY_DIRS = [HERE / "out" / "history", RAW_DIR / "history"]
OUT_JSON = RAW_DIR / "crds_backtest.json"
OUT_JS = DATA_DIR / "CRDS_BACKTEST.js"
# 🔴 2026-09-12 主人令（拍板第 1 项·①）：回测持有期统一阶梯（近→远）。
#   主人原话：「可以从近到远，从5天开始、10天、20天、30天、45天、60天、75天、90天
#   这样写出来慢慢跟踪」。短档 1/3 保留（隔日冲高/短线验证有独立价值）。
#   ⚠️ **同源铁律**：本阶梯是唯一真源，四个回测脚本一律引此常量；
#      各写一套必然漂移（本仓历史教训）。
HOLD_LADDER = [5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
# 🔴 2026-09-12 主人令：原 [1,3,5,10,20] → [1,3] + HOLD_LADDER。
HOLD_PERIODS = [1, 3] + HOLD_LADDER
# 🔴 2026-09-12 同批修复：原 lookahead_days=35（自然日）只够 ~24 个交易日，
#   90 交易日档会静默零样本。90 交易日 ≈ 130 自然日，留余量取 150。
# 🔴 2026-09-13 主人令扩档（90 → 250 交易日）：150 → 380。
#   250 交易日 ≈ 365 自然日；不扩窗口则 180/250 档 `len(after)-1 < hp` 恒真
#   ⇒ 静默零样本（不是算出 0，是根本没取到那么长的 K 线）。
LOOKAHEAD_DAYS = 380

# 2026-09-06 主人令 P1-A：交易成本（单边 万分之1.5 = 0.15%；双边 0.3%）；
# 这是 A 股场内交易的合理默认假设（含印花税+佣金+过户费），写死写在此处
# 也写明在 method 字段，便于审计追溯。前端会显示净收益（已扣成本）。
COST_BPS = 15  # 单边万分之 1.5 = 0.15%


def parse_date_from_filename(name):
    """crds_20260817.json -> 2026-08-17"""
    stem = Path(name).stem
    if stem.startswith("crds_") and len(stem) >= 13:
        d = stem[-8:]
        if d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def load_signals():
    """加载历史 CRDS advanced 信号。"""
    signals = []
    seen = set()
    for hist_dir in HISTORY_DIRS:
        if not hist_dir.exists():
            continue
        for f in sorted(hist_dir.glob("crds_*.json")):
            if f.name == "crds_history.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[skip] {f}: {e}")
                continue
            # 取日期：内部元数据优先
            dt = (data.get("update_time") or data.get("data_time") or "").strip()[:10]
            if not dt or dt == "2026-09-02":
                # 内部日期缺失或明显为今天（可能是重建），用文件名
                dt = parse_date_from_filename(f.name)
            if not dt or len(dt) != 10:
                continue
            # 取 advanced 档信号
            advanced = data.get("advanced") or []
            if not advanced and data.get("cond3_list"):
                advanced = data.get("cond3_list")
            for s in advanced:
                code = str(s.get("code", "")).strip()
                name = str(s.get("name", "")).strip()
                if not code:
                    continue
                key = (dt, code)
                if key in seen:
                    continue
                seen.add(key)
                signals.append({"signal_date": dt, "code": code, "name": name})
    signals.sort(key=lambda x: x["signal_date"])
    return signals


def baostock_login(retries=3, delay=5):
    """登录 baostock（带重试）。

    🔴 2026-09-23（阿狸咪的工程师）：baostock 是免费源，且本仓 20+ 脚本共用同一账号，
    算法链并发跑批时**同账号互踢**高发 ⇒ 单次 login 失败即判死会误伤。
    2026-09-18 01:22、2026-09-23 16:05 两次「登录失败 → 全 0 覆盖」事故，
    其 method 字段均自证为 "baostock 登录失败，自动降级"。
    ⇒ 改为重试 retries 次（每次先 logout 释放会话再重连，间隔 delay 秒），
       显著降低「偶发抽风」被当成「数据源失效」的概率。
    """
    if bs is None:
        print("[baostock] 模块未安装（import 失败）")
        return False
    last = ""
    tries = max(1, int(retries))
    for i in range(1, tries + 1):
        try:
            bs.logout()
        except Exception:
            pass
        try:
            r = bs.login()
            if getattr(r, "error_code", "?") == "0":
                if i > 1:
                    print(f"[baostock] 第 {i}/{tries} 次登录成功（前 {i-1} 次失败）")
                return True
            last = f"{getattr(r, 'error_code', '?')}: {getattr(r, 'error_msg', '')}"
            print(f"[baostock] 第 {i}/{tries} 次登录失败 -> {last}")
        except Exception as e:
            last = str(e)
            print(f"[baostock] 第 {i}/{tries} 次登录异常: {e}")
        if i < tries:
            time.sleep(delay)
    print(f"[baostock] {tries} 次登录均失败，最后一次: {last}")
    return False


def bs_code(code):
    """6位代码转 baostock 格式。"""
    code = code.zfill(6)
    if code.startswith("6") or code.startswith("5") or code.startswith("11") or code.startswith("51"):
        return f"sh.{code}"
    return f"sz.{code}"


def add_trade_days(date_str, n):
    """简单版：按日历日加，不处理节假日。回测口径与 HUNTER_BACKTEST 保持一致即可。"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    d += timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def fetch_close(code, date):
    """获取某股票某交易日收盘价（前复权，与综合回测/通达信 K 线回测口径一致）。

    2026-09-06 主人令 P0-A：CRDS 改用前复权（adjustflag="2"），与 backtest_comprehensive / backtest_tdx
    统一口径。此前不复权（adjustflag="3"）会在除权日制造虚假亏损，扭曲信号真实 alpha。
    """
    if bs is None:
        return None
    try:
        r = bs.query_history_k_data_plus(
            bs_code(code),
            "date,close",
            start_date=date,
            end_date=date,
            frequency="d",
            adjustflag="2",  # 前复权（2026-09-06 P0-A 修复）
        )
        row = r.get_row_data()
        if row and len(row) >= 2 and row[1]:
            return float(row[1])
    except Exception as e:
        print(f"[fetch] {code} {date} error: {e}")
    return None


def fetch_kline_around(code, center_date_str, lookback_days=8, lookahead_days=LOOKAHEAD_DAYS):
    """一次性拉 signal 前后一段连续 K 线（前复权），返回 [(date, open, close), ...]。

    用于：在 K 线序列里找 entry 真实交易日 + 后 N 个真实交易日，避免日历日的提前/延后失真。
    2026-09-06 主人令 P0-A：用 K 线序列替代「日历日+1/3/5/10/20」持有期，与综合回测/通达信口径统一。
    """
    if bs is None:
        return []
    try:
        d = datetime.strptime(center_date_str, "%Y-%m-%d").date()
        start = (d - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end = (d + timedelta(days=lookahead_days)).strftime("%Y-%m-%d")
        r = bs.query_history_k_data_plus(
            bs_code(code),
            "date,open,close",   # 🔴 09-13：入场改用次日开盘 ⇒ 需 open
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",  # 前复权
        )
        rows = []
        while r.error_code == "0" and r.next():
            x = r.get_row_data()
            if x and x[0] and x[2]:
                # 🔴 2026-09-13 统一测算标准（小九审计 P1-1）：入场改用**次日开盘**
                #   ⇒ 需 open；停牌/缺失时回退当日收盘（避免整条信号被丢弃）。
                try:
                    _of = float(x[1]) if x[1] not in (None, "", "0.0000") else float(x[2])
                except Exception:
                    _of = float(x[2])
                rows.append((x[0], _of, float(x[2])))
        return rows
    except Exception as e:
        print(f"[kline] {code} {center_date_str} error: {e}")
        return []


def fmt_pct(v):
    # 🔴 2026-09-13 主人令「统一测算标准 · 禁止 0 冒充」：无样本/未到期
    #   的统计量一律 None（前端显示「—」），绝不用 0 冒充 —— 0 会被读成
    #   「胜率 0% / 收益 0%」，那是把「没数据」谎报成「最差结果」。
    return round(v, 2) if v is not None else None


def fetch_close_roll(code, date_str, max_fwd=8):
    """向前滚动到最近的交易日取收盘价。

    信号生成日可能是周末/节假日（如 2026-08-01 为周六），无法在当日买入，
    须顺延到下一交易日。逐日尝试直到取到有效收盘价即视为该信号的交易日。
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    for i in range(max_fwd + 1):
        cand = (d + timedelta(days=i)).strftime("%Y-%m-%d")
        px = fetch_close(code, cand)
        if px is not None and px > 0:
            return px, cand
    return None, None


def empty_backtest(reason):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": 0,
            "calc_time": now,
            "method": f"CRDS 逆势龙头 advanced 档历史回测 · {reason}",
            "signal_date_range": "—",
            "by_period": {
                str(p): {
                    "samples": 0,
                    "win_rate": None,
                    "avg_return": None,
                    "best_return": None,
                    "worst_return": None,
                    "win_avg": None,
                    "loss_avg": None,
                    "profit_loss_ratio": None,
                }
                for p in HOLD_PERIODS
            },
        },
        "signals": [],
    }
    return payload


def _existing_valid():
    """旧产物是否含**有效历史成果**（「失败不覆盖」的判据）。

    🛡 2026-09-23 主人令：回测产物是累积型（覆盖 8/1 以来的全部历史信号），
    一次运行失败绝不代表历史成果失效 ⇒ 判据取「信号数 > 0 或任一档有样本」。
    返回 dict（有效）或 None（无/不可读）。不可读时**按无效处理**（宁可写诚实空骨架，
    也不把一份损坏文件当成有效成果继续顶着）。
    """
    try:
        if not OUT_JSON.exists():
            return None
        d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[CRDS backtest] 旧产物读取失败（{e}）")
        return None
    sm = d.get("summary") or {}
    try:
        nsig = int(sm.get("total_signals") or 0)
    except Exception:
        nsig = 0
    nz = sum(1 for v in (sm.get("by_period") or {}).values()
             if isinstance(v, dict) and (v.get("samples") or 0))
    if nsig > 0 or nz > 0:
        return {
            "total_signals": nsig,
            "periods_with_samples": nz,
            "update_time": sm.get("update_time") or d.get("update_time") or "?",
            "range": sm.get("signal_date_range") or "—",
        }
    return None


def keep_existing(reason):
    """失败路径：**保留旧产物、不写盘**，仅打印 KEEP 告警。

    返回 True = 已保留（调用方应直接 return，不写空覆盖）；
    返回 False = 从未有过有效成果 ⇒ 调用方写空骨架（诚实空）。
    """
    old = _existing_valid()
    if not old:
        return False
    print("=" * 74)
    print(f"[KEEP] {reason}")
    print("[KEEP] 按主人令「空卡比 stale 更伤」→ **保留上次成功结果，不写空覆盖**")
    print(f"[KEEP]   旧 update_time      = {old['update_time']}")
    print(f"[KEEP]   旧 total_signals    = {old['total_signals']}")
    print(f"[KEEP]   旧有样本档位数      = {old['periods_with_samples']}")
    print(f"[KEEP]   旧 signal_date_range= {old['range']}")
    print(f"[KEEP]   保留文件：{OUT_JSON.name} / {OUT_JS.name}")
    print("[KEEP]   （如需人工清零，请显式加 --allow-empty）")
    print("=" * 74)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只统计信号数，不拉K线")
    parser.add_argument("--allow-empty", action="store_true", dest="allow_empty",
                        help="人工强制写空骨架（默认：有旧成果时保留旧数据、不用 0 覆盖）")
    args = parser.parse_args()

    signals = load_signals()
    print(f"[CRDS backtest] loaded {len(signals)} advanced signals")
    if not signals:
        # 🛡 2026-09-23 主人令：读不到历史信号 ≠ 历史成果失效 ⇒ 有旧成果就保留，不写 0 覆盖。
        if not args.allow_empty and keep_existing("无历史 advanced 信号"):
            return 0
        payload = empty_backtest("无历史 advanced 信号"
                                 + ("（--allow-empty 强制）" if args.allow_empty else "（首次运行，尚无成果）"))
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[CRDS backtest] written empty backtest（确实无有效旧成果）")
        return 0

    if args.dry:
        dates = sorted({s["signal_date"] for s in signals})
        print(f"[DRY] date range: {dates[0]} ~ {dates[-1]}, signals={len(signals)}")
        return 0

    if not baostock_login():
        # 🛡 2026-09-23 主人令（本卡「整卡变空」的**唯一真凶**）：
        #   原实现在此写 empty_backtest 覆盖 ⇒ 09-18 01:22 / 09-23 16:05 两次把
        #   累积的 249 信号 × 12 档成果抹成 0。改为「有旧成果 ⇒ 保留不写」。
        if not args.allow_empty and keep_existing("baostock 登录失败（已重试）"):
            return 0
        payload = empty_backtest("baostock 登录失败"
                                 + ("（--allow-empty 强制）" if args.allow_empty else "（首次运行，尚无成果）"))
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
        print("[CRDS backtest] baostock login failed -> empty backtest（确实无有效旧成果）")
        return 0

    # 2026-09-06 主人令 P0-A：用连续 K 线段取真实入场/出场日（替代旧日历日 +1/3/5/10/20），
    # 与综合回测 / 通达信 K 线回测口径统一。同时扣双边交易成本（万分之1.5 ×2= 0.3%）。
    period_returns = {p: [] for p in HOLD_PERIODS}      # 含成本的净收益（用于卡片展示）
    period_gross = {p: [] for p in HOLD_PERIODS}        # 原收益（不含成本，用于审计对照）
    period_per_signal_equity = {p: [] for p in HOLD_PERIODS}  # 每个信号该持有期内的累计收益曲线（回撤计算用）
    detail_signals = []
    total = len(signals)
    cost_pct = 2 * COST_BPS / 100  # 双边 0.3%
    last_heartbeat = time.time()  # 🛡 2026-09-12 防监督器静默杀时间心跳
    for idx, sig in enumerate(signals, 1):
        # 每 60 秒至少打印一次心跳，避免单个信号拉 K 线卡住时 10 个信号跨度超过 15min
        if time.time() - last_heartbeat >= 60:
            print(f"💓 CRDS 回测心跳: 已处理 {idx-1}/{total} 个信号")
            last_heartbeat = time.time()
        code = sig["code"]
        signal_date = sig["signal_date"]
        # 🔴 2026-09-13 一劳永逸：原写死 lookahead_days=35，把 L60 已定义的
        #   LOOKAHEAD_DAYS=150 **完全覆盖** ⇒ T+30/45/60/75/90 档永久 0 样本
        #   （35 自然日 ≈ 24 交易日，凑不满 30）。这才是「假修复」的真凶。
        rows = fetch_kline_around(code, signal_date, lookback_days=8,
                                  lookahead_days=LOOKAHEAD_DAYS)
        # 🔴 2026-09-13 主人令「统一测算标准 · 用最科学的计算」（小九周末审计 P1-1）：
        #   入场 = 信号日**次一交易日开盘**。原取 `d >= signal_date` = 信号日本身、
        #   价 = 当日收盘 ⇒ 前视偏差（信号由盘后算出，「当日收盘价买入」实盘做不到）。
        sig_idx = None
        for i, r in enumerate(rows):
            if r[0] >= signal_date:
                sig_idx = i; break
        if sig_idx is None:
            print(f"[{idx}/{total}] skip {code} {signal_date}: no kline at/after signal date")
            continue
        entry_idx = sig_idx + 1                  # 次一交易日 = 入场日
        if entry_idx >= len(rows):
            print(f"[{idx}/{total}] skip {code} {signal_date}: no next trading day after signal")
            continue
        entry_td, _entry_o, _entry_c = rows[entry_idx]
        entry_price = _entry_o                   # 入场价 = 次日开盘
        if entry_price is None or entry_price <= 0:
            print(f"[{idx}/{total}] skip {code} {signal_date}: invalid entry price")
            continue
        sig_result = {
            "signal_date": signal_date,
            "entry_trade_date": entry_td,
            "code": code,
            "name": sig["name"],
            "entry_price": round(entry_price, 2),
            "periods": {},
        }
        for p in HOLD_PERIODS:
            target_idx = entry_idx + p
            if target_idx >= len(rows):
                sig_result["periods"][str(p)] = {"return_pct": None, "gross_return": None, "exit_price": None, "exit_date": None}
                continue
            exit_td, _x_o, exit_price = rows[target_idx]   # 卖出按收盘
            gross = (exit_price - entry_price) / entry_price * 100
            net = gross - cost_pct
            sig_result["periods"][str(p)] = {
                "return_pct": fmt_pct(net),
                "gross_return": fmt_pct(gross),
                "exit_price": round(exit_price, 2),
                "exit_date": exit_td,
            }
            period_returns[p].append(net)
            period_gross[p].append(gross)
            # 按持有期内每日累计收益算回撤
            cum_path = []
            for k in range(1, p + 1):
                j = entry_idx + k
                if j >= len(rows): break
                _, _, px2 = rows[j]
                cum_path.append((px2 / entry_price - 1) * 100 - cost_pct)
            period_per_signal_equity[p].append(cum_path)
        detail_signals.append(sig_result)
        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] {code} {signal_date} -> entry {entry_td} done")

    try:
        bs.logout()
    except Exception:
        pass

    # 汇总
    # 2026-09-06 主人令 P0-A：胜率口径统一（排平盘，只算 win/(win+loss)）；P2-C 加最大回撤+夏普；P1-A 标注含成本
    by_period = {}
    for p in HOLD_PERIODS:
        rets = period_returns[p]
        equity_paths = period_per_signal_equity[p]
        if not rets:
            # 🔴 2026-09-13：该档未到期/无样本 ⇒ 统计量一律 None（只留 samples:0）
            by_period[str(p)] = {
                "samples": 0, "win_rate": None, "avg_return": None,
                "best_return": None, "worst_return": None,
                "win_avg": None, "loss_avg": None, "profit_loss_ratio": None,
                "max_drawdown": None, "sharpe_ratio": None,
            }
            continue
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]  # 排平盘
        draws = [r for r in rets if r == 0]
        decided = len(wins) + len(losses)
        avg_ret = sum(rets) / len(rets)
        max_ret = max(rets)
        min_ret = min(rets)
        # 🔴 2026-09-13：无「赢/亏」子集时，对应均值/盈亏比无意义 ⇒ None
        win_avg = sum(wins) / len(wins) if wins else None
        loss_avg = sum(losses) / len(losses) if losses else None
        profit_loss_ratio = abs(win_avg / loss_avg) if (wins and losses) else None
        # 🔴 2026-09-13 一劳永逸修复「回撤量纲错误」：原实现把各信号收益路径
        #   **首尾拼接**后累加求峰谷 —— 那不是任何组合的净值曲线，量纲错误
        #   （实测 CRDS −314.36%，而回撤下界应为 −100%）。现改为**逐信号**算其
        #   持有期内回撤（相对该信号入场价的峰值回撤），再取均值。
        _dds = []
        for pth in equity_paths:
            if not pth:
                continue
            _pk = 0.0
            _wr = 0.0
            for v in pth:
                if v > _pk: _pk = v
                _dd = v - _pk
                if _dd < _wr: _wr = _dd
            _dds.append(_wr)
        global_max_dd = (sum(_dds) / len(_dds)) if _dds else 0.0
        # 夏普：以均收益/收益标准差（简单近似，未年化）
        variance = sum((r - avg_ret) ** 2 for r in rets) / max(len(rets) - 1, 1)
        std_ret = variance ** 0.5
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else None
        by_period[str(p)] = {
            "samples": len(rets),
            "draws": len(draws),  # 透明：平盘数
            "win_rate": fmt_pct(len(wins) / decided * 100) if decided else None,
            "avg_return": fmt_pct(avg_ret),
            "best_return": fmt_pct(max_ret),
            "worst_return": fmt_pct(min_ret),
            "win_avg": fmt_pct(win_avg),
            "loss_avg": fmt_pct(loss_avg),
            "profit_loss_ratio": fmt_pct(profit_loss_ratio),
            "max_drawdown": fmt_pct(global_max_dd),
            "sharpe_ratio": sharpe,
            "cost_adjusted": True,  # 标记净收益已扣双边 0.3% 成本
        }

    dates = sorted({s["signal_date"] for s in signals})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "update_time": now,
        "summary": {
            "update_time": now,
            "total_signals": len(signals),
            "calc_time": now,
            "method": "CRDS 逆势龙头 advanced 档历史回测：信号日取真实下一交易日开盘买入，持有 N 个真实交易日收盘价卖出（前复权；胜率=win/(win+loss) 排平盘；已扣双边交易成本 0.3%）",
            "signal_date_range": f"{dates[0]} ~ {dates[-1]}",
            "cost_bps_per_side": COST_BPS,
            "by_period": by_period,
        },
        "signals": detail_signals,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text("window.CRDS_BACKTEST = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";", encoding="utf-8")
    print(f"[CRDS backtest] done: {len(signals)} signals, periods={ {p: len(period_returns[p]) for p in HOLD_PERIODS} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
