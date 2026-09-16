#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 选股策略模块（v8 候选策略 · 暂未上架区）

· calc_siliang_ultimate_signal 本模块自包含，忠实翻译用户 2026-08-05 通达信「四量终极 指标版 副图」公式（原贴完整源码，已核对）。
· 信号 QD = YZC AND JG AND XC AND FOUR：游资点火 YZC=CROSS(W2,0) / 机构托底 JG=C>NLJ / 当天金叉 XC=JGC|SHC|YZC|ZLC（四金叉取或）/ 四路翻多 FOUR=JG&GB1>=0&W2>=0&V6>=0。
· scan_four_volume()  : 复用 scanner 的成交量前N活跃股池 + 日K 抓取，逐只算 XG，
                        收集末根触发 XG 的票，产出命中清单（含组件灯 + 触发理由）。
· write_four_volume_js(): 写出 data/FOUR_VOLUME.js 供 v8 站点渲染。
· backtest_four_volume(years=3): 对命中票回看近 N 年日K，统计 XG 信号日的
                        T+1/3/5/10/20 持有收益胜率/均值（非未来函数）。

数据来源：本地双机走 mootdx/akshare；云端 GHA（CLOUD_RUNNER）走腾讯 GTimg 前复权日K，
与 scanner.fetch_a_daily 一致。
"""
import os
import sys
import json
import re
import time
import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 🔴 2026-09-12 主人令（拍板第 1 项·①）：回测持有期统一阶梯（近→远）。
#   主人原话：「可以从近到远，从5天开始、10天、20天、30天、45天、60天、75天、90天
#   这样写出来慢慢跟踪」。短档 1/3 保留（隔日冲高/短线验证有独立价值）。
#   ⚠️ **同源铁律**：四个回测脚本共引此阶梯（backtest_tdx / backtest_comprehensive /
#      strategy_four_volume / backtest_crds），不各写一套 —— 各写一套必然漂移。
HOLD_LADDER = [5, 10, 20, 30, 45, 60, 75, 90, 180, 250]  # __SFV_LADDER_ANCHOR__

from scanner import (  # noqa: E402
    fetch_volume_top_stocks,
    fetch_a_daily, fetch_hk_daily, DAILY_BARS, resolve_clean_name_s,
)


# ──────────────────────────────────────────────────────────────────────────
# 四量终极 信号计算（自包含，忠实翻译用户 2026-08-05 通达信「指标版 副图」公式）
#   QD: YZC AND JG AND XC AND FOUR
#   游资点火 YZC = CROSS(W2, 0)
#   机构托底 JG  = C > NLJ
#   当天金叉 XC  = JGC OR SHC OR YZC OR ZLC（四金叉取或）
#   四路翻多 FOUR= JG AND GB1>=0 AND W2>=0 AND V6>=0
#   其中 JGC=CROSS(NLJ,MA(NLJ,6)) / SHC=CROSS(GB1,0) / ZLC=CROSS(V6,0)
#   加权价 MID=(3C+O+L+H)/6；NLJ=NLS=DKX=MID 同一条 20 周期加权线（含 REF(MID,19)→REF(MID,20) 替换）
#   非未来函数。
# ──────────────────────────────────────────────────────────────────────────
def _obv(close, vol):
    """累计能量潮 OBV（非未来函数）。"""
    c = np.asarray(close, dtype=float)
    v = np.asarray(vol, dtype=float)
    n = len(c)
    sign = np.zeros(n)
    d = np.diff(c)
    sign[1:] = np.where(d > 0, 1.0, np.where(d < 0, -1.0, 0.0))
    return np.cumsum(sign * v)


def _cross(a, b):
    """CROSS(a,b)：a 上穿 b（非未来函数）。b 可为数组或标量。"""
    a = np.asarray(a, dtype=float)
    if np.isscalar(b):
        b = np.full(a.shape, float(b), dtype=float)
    else:
        b = np.asarray(b, dtype=float)
    prev = np.r_[a[0], a[:-1]] <= np.r_[b[0], b[:-1]]
    cur = a > b
    return prev & cur


def _wma20(mid):
    """通达信式 20 周期加权移动平均（含 REF(MID,19)→REF(MID,20) 替换）。
    权重 REF(k):(20-k)/210, k=0..18，再以 REF(20) 系数1 顶替 REF(19)（即 -REF19+REF20）。"""
    mid = np.asarray(mid, dtype=float)
    n = len(mid)
    if n < 20:
        return np.full(n, np.nan)
    b = np.arange(20, 0, -1, dtype=float) / 210.0  # [20,19,...,1]/210
    full = np.convolve(mid, b, mode='full')         # length n+19
    out = full[:n].copy()
    out[:19] = np.nan
    ref19 = np.r_[np.full(19, np.nan), mid[:-19]]
    ref20 = np.r_[np.full(20, np.nan), mid[:-20]]
    out = out + (ref20 - ref19)
    return out


def _ema(x, n):
    """通达信 EMA(X,N)（adjust=False 的 Wilder 平滑）。"""
    return pd.Series(np.asarray(x, dtype=float)).ewm(span=n, adjust=False).mean().values


def _turnover(df, V):
    """换手率：优先 turnover_rate 列；其次 circ_mv 估算；否则用成交量 5 日均归一近似。"""
    if "turnover_rate" in df.columns:
        return df["turnover_rate"].astype(float).values
    if "circ_mv" in df.columns:
        circ = df["circ_mv"].astype(float).values
        with np.errstate(divide='ignore', invalid='ignore'):
            t = np.where(circ > 0, V * 100.0 / (circ * 1e8), np.nan)
        return np.nan_to_num(t, nan=np.nan)
    return V / pd.Series(V).rolling(5, min_periods=1).mean().values


def calc_siliang_ultimate_signal(df):
    """四量终极 选股信号（忠实翻译用户 2026-08-05 通达信「指标版 副图」公式）。

    非未来函数。输出 df 列：四量终极_*（JG/JGC/SHC/YZC/ZLC/GB1/W2/V6/XC/FOUR/XG）。
    """
    # 列名兼容：数据源(fetch_a_daily/fetch_hk_daily)返回 volume，公式内部统一用 vol。
    # 2026-08-07 修复：此前 vol 缺失直接走 early-return → 所有组件恒为 False → 0 命中。
    if "vol" not in df.columns and "volume" in df.columns:
        df = df.rename(columns={"volume": "vol"})
    req = ["close", "open", "high", "low", "vol"]
    if not all(k in df.columns for k in req):
        df["四量终极_XG"] = False
        return df
    C = df["close"].astype(float).values
    O = df["open"].astype(float).values
    H = df["high"].astype(float).values
    L = df["low"].astype(float).values
    V = df["vol"].astype(float).values

    # 加权典型价 MID = (3C + O + L + H)/6；20 周期加权线（同一条，MID9=MID1=MID=DKX=NLJ=NLS）
    mid = (3.0 * C + O + L + H) / 6.0
    MID = _wma20(mid)
    NLJ = MID
    NLS = MID
    DKX = MID

    # 机构托底 JG：收盘价在量能线之上
    JG = C > NLJ
    # 机构金叉 JGC：NLJ 上穿其 6 日均线
    JGC = _cross(NLJ, pd.Series(NLJ).rolling(6, min_periods=1).mean().values)

    # 广度 GB1 = (C - NLS) + (ZH - SHH)；散户金叉 SHC = GB1 上穿 0
    turnover = _turnover(df, V)
    ZH = pd.Series(turnover).rolling(5, min_periods=1).mean().values
    SHH = pd.Series(turnover).rolling(55, min_periods=1).mean().values
    GB = C - NLS
    GBB = ZH - SHH
    GB1 = GB + GBB
    SHC = _cross(GB1, 0.0)

    # 游资点火 YZC：W2 上穿 0
    Q = _ema(V, 5)
    Q1 = _ema(V, 50)
    W = (Q - Q1) * 0.00001
    obv = _obv(C, V)
    OBV1 = _ema(obv, 5)
    OBV2 = _ema(obv, 50)
    W1 = (OBV1 - OBV2) * 0.000001
    W2 = W + W1
    YZC = _cross(W2, 0.0)

    # 主力金叉 ZLC：V6 上穿 0
    MADKX = pd.Series(DKX).rolling(6, min_periods=1).mean().values
    MDD = (DKX - MADKX) * 1.2
    V1 = (C * 2.0 + H + L) / 4.0 * 10.0
    V2v = _ema(V1, 6) - _ema(V1, 55)
    V5 = (V2v - _ema(V2v, 6)) * 0.06
    V6 = MDD + V5
    ZLC = _cross(V6, 0.0)

    # 当天金叉 XC：四金叉任一
    XC = JGC | SHC | YZC | ZLC
    # 四路翻多 FOUR：机构托底 + 广度翻多 + 游资量能翻多 + 主力动量翻多
    FOUR = JG & (GB1 >= 0) & (W2 >= 0) & (V6 >= 0)
    # 终极信号 QD
    XG = YZC & JG & XC & FOUR

    df["四量终极_JG"] = JG
    df["四量终极_JGC"] = JGC
    df["四量终极_SHC"] = SHC
    df["四量终极_YZC"] = YZC
    df["四量终极_ZLC"] = ZLC
    df["四量终极_GB1"] = np.round(GB1, 4)
    df["四量终极_W2"] = np.round(W2, 4)
    df["四量终极_V6"] = np.round(V6, 4)
    df["四量终极_XC"] = XC
    df["四量终极_FOUR"] = FOUR
    df["四量终极_XG"] = XG
    return df


def _build_reason(comp):
    parts = []
    if comp.get("游资点火"):
        parts.append("游资点火(YZC)")
    if comp.get("机构托底"):
        parts.append("机构托底(JG)")
    if comp.get("广度翻多"):
        parts.append("广度翻多(GB1≥0)")
    if comp.get("主力动量翻多"):
        parts.append("主力动量翻多(V6≥0)")
    if comp.get("机构金叉"):
        parts.append("机构金叉")
    if comp.get("散户金叉"):
        parts.append("散户金叉")
    if comp.get("主力金叉"):
        parts.append("主力金叉")
    return " + ".join(parts) if parts else "—"


def scan_four_volume(top_cy=100, top_kc=100, top_zb=100, top_hk=50):
    """扫描成交量前N活跃股池，返回末根 XG=True 的命中清单。"""
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk)
    if not stocks:
        print("  ⚠️ 活跃股池为空（数据源可能断连），四量终极扫描跳过")
        return []
    hits = []
    total = len(stocks)
    done = 0
    for s in stocks:
        code, name, market, board_label = s[0], s[1], s[2], s[3]
        turnover_rate = s[5] if len(s) > 5 else 0
        mv_yi = s[6] if len(s) > 6 else 0
        fund_type = s[7] if len(s) > 7 else "混合"
        try:
            df = fetch_hk_daily(code) if market == "hk" else fetch_a_daily(code)
            if df is None or len(df) < 60:
                continue
            df = calc_siliang_ultimate_signal(df)
            last = df.iloc[-1]
            if not bool(last.get("四量终极_XG", False)):
                continue
            comp = {
                "游资点火": bool(last.get("四量终极_YZC", False)),
                "机构托底": bool(last.get("四量终极_JG", False)),
                "广度翻多": float(last.get("四量终极_GB1", 0) or 0) >= 0,
                "主力动量翻多": float(last.get("四量终极_V6", 0) or 0) >= 0,
                "机构金叉": bool(last.get("四量终极_JGC", False)),
                "散户金叉": bool(last.get("四量终极_SHC", False)),
                "主力金叉": bool(last.get("四量终极_ZLC", False)),
            }
            pct = float(last.get("pct_chg", 0)) if "pct_chg" in df.columns else 0
            close_price = float(last["close"])
            hits.append({
                "code": code,
                "name": resolve_clean_name_s(code, market, name),
                "market": market,
                "board_label": board_label or ("港股" if market == "hk" else (
                    "科创板" if code.startswith("688") else (
                        "创业板" if code.startswith("300") else "主板"))),
                "close": round(close_price, 2),
                "pct_chg": round(pct, 2),
                "turnover_rate": round(turnover_rate, 2) if turnover_rate else 0,
                "mv_yi": round(mv_yi, 1) if mv_yi else 0,
                "fund_type": fund_type or "混合",
                "components": comp,
                # 2026-08-07 修复：UI renderFourVolume 读顶层 yzc/jg/xc/four/qd 标记，
                # 此前只写嵌套 components → 卡片永远显示 QD=0、无标签。现补齐顶层布尔。
                "yzc": bool(comp.get("游资点火")),
                "jg": bool(comp.get("机构托底")),
                "xc": bool(last.get("四量终极_XC", False)),
                "four": bool(last.get("四量终极_FOUR", False)),
                "qd": bool(last.get("四量终极_XG", False)),
                "reason": _build_reason(comp),
                "signal_date": str(last.get("date", "")) if "date" in df.columns else "",
                # 2026-08-08 修复：给每只股票打 enter_date，前端「M-D已入仓」胶囊可区分当日新入选。
                "enter_date": str(last.get("date", "")) if "date" in df.columns else datetime.now().strftime("%Y-%m-%d"),
            })
        except Exception as e:
            print(f"  [WARN] {code} 计算失败: {e}")
        done += 1
        if done % 50 == 0:
            print(f"  四量终极扫描进度: {done}/{total}, 命中 {len(hits)}")
    print(f"  四量终极扫描完成: {total} 只, 命中 {len(hits)} 只")
    return hits


def write_four_volume_js(records, out_dir=DATA_DIR, scan_error=None):
    """写出 data/FOUR_VOLUME.js（北京时间时间戳，供 v8 暂未上架区渲染）。"""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now() + timedelta(hours=8)  # 兜底：UTC+8
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    records = sorted(records, key=lambda x: -abs(x.get("pct_chg", 0)))
    data = {
        "update_time": update_time,
        "total": len(records),
        "stocks": records,
    }
    path = os.path.join(out_dir, "FOUR_VOLUME.js")

    # 🛡 2026-09-11 小九的工程师·一劳永逸「防洗空」闸门：
    #   实证故障：2026-09-11 盘中某轮抓取跑本策略（当日日线尚未收盘成型）→ 命中 0 只 →
    #   把线上非空的 FOUR_VOLUME.js（5 只）直接覆盖成 total:0/stocks:[]（commit 049925d5）→
    #   ① 前端「四量终极」卡空；② CI pre_deploy_audit 判「data/ 下过小文件」硬阻断
    #      整站部署（后续好数据也上不了线）。
    #   与金股池（out/gold_pool.json 被洗空）同族：**累积态一旦允许空写就必然被洗**。
    #   规则：本次命中 0 只且磁盘已有非空 → 拒绝覆盖，保留旧值；确需清空须显式
    #   V8_FOUR_VOLUME_FORCE_EMPTY=1（人工授权）。
    # 🛡 2026-09-16 阿狸咪的工程师·一劳永逸【死锁根治】（主人全权授权 · 采「乙」方案）：
    #   实证冲突：0 命中时原闸门 return 不写盘 ⇒ 文件 mtime 冻结 ⇒
    #   run_algorithms._gate_hardwait_four_volume 的判据是 **mtime >= run_start**（L742/L751）
    #   ⇒ 永远判「非今日」⇒ 重跑 strategy_four_volume.py（单轮 60–90min）×3 + 每次 sleep 90s
    #   ⇒ 超时 return False ⇒ _final_recommend_gate 拒绝产出 ⇒ **整轮 D 批白跑、不收敛**。
    #   「防洗空」要「不写」，「新鲜度」要「必须写」——两个闸门语义直接打架。
    #   乙方案 = **仍写盘，但口径绝不造假**（主人宗旨①数据新鲜真实）：
    #     · update_time = 本轮真实计算时间（新鲜度据此放行，死循环解除）
    #     · total       = 本轮真实命中数（0 就是 0，**绝不用旧值冒充**）
    #     · stocks      = []（本轮真实结果）
    #       🔴 旧命中**不可塞回 stocks**：update_four_volume_history.py L152 直接读
    #          fv["stocks"] 记信号历史，塞回旧值＝把今天伪造成命中日 → 污染历史。
    #     · zero_hit    = True（显式披露「本轮确为 0 命中」）
    #     · carryover   = 上一有效批 {update_time,total,stocks}（**仅供前端兜底展示并标注来源**）
    #   人工强制清空仍走 V8_FOUR_VOLUME_FORCE_EMPTY=1。
    _zero_hit = (not records) and os.environ.get("V8_FOUR_VOLUME_FORCE_EMPTY") != "1"
    if _zero_hit:
        _carry = None
        try:
            if os.path.exists(path):
                _old = open(path, "r", encoding="utf-8", errors="replace").read()
                _oj = _old.split("=", 1)[1].strip().rstrip(";") if "=" in _old else ""
                _od = json.loads(_oj) if _oj else {}
                _ot = int(_od.get("total") or 0)
                _ostk = _od.get("stocks") or []
                if _ot > 0 and _ostk:
                    _carry = {"update_time": _od.get("update_time"),
                              "total": _ot, "stocks": _ostk}
        except Exception as _e:
            print(f"  [warn] carryover 解析失败（不影响写盘）: {_e}")
        data["total"] = 0
        data["stocks"] = []
        data["zero_hit"] = True
        _err_txt = ("；扫描异常：" + str(scan_error)) if scan_error is not None else ""
        if scan_error is not None:
            data["scan_error"] = str(scan_error)
        if _carry:
            data["carryover"] = _carry
            data["note"] = (f"本轮扫描 0 命中（真实无信号）{_err_txt}"
                            f"；卡片展示沿用 {_carry.get('update_time') or '上一有效批'} 的 "
                            f"{_carry['total']} 只（显式回退，非本轮结果）")
        else:
            data["note"] = f"本轮扫描 0 命中（真实无信号）{_err_txt}；且无可用历史批"

    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME=" + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（{len(records)} 只命中{'; 🛡 零命中仍写盘·防死锁（zero_hit）' if _zero_hit else ''}）")
    return path




def write_four_volume_backtest_js(records, bt_summary=None, out_dir=DATA_DIR):
    """写出 data/FOUR_VOLUME_BACKTEST.js 规范化外壳（策略回顾回测区 window.FOUR_VOLUME_BACKTEST）。

    🛡 2026-09-04 主人令·一劳永逸：外壳此前为 09-02 手工空壳、无人回写 → update_time 冻结，
    健康面板 all_FOUR_VOLUME_BACKTEST 永远 FAIL（误报）。每次四量跑完即刷新本外壳；
    bt_summary（backtest_four_volume 返回值）存在时附带真实分层回测数据（1d→1 等键名映射）。
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now() + timedelta(hours=8)  # 兜底：UTC+8
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    n = len(records or [])
    by_period = {}
    if bt_summary:
        for k, v in (bt_summary.get("periods") or {}).items():
            # 🔴 2026-09-11 主人令「真实回测，不得造假」根因修复（阿狸咪的工程师）：
            #   原写 v.get("best", 0) / v.get("worst", 0) —— 但 backtest_four_volume
            #   实际写出的键名是 **best_return / worst_return**，键名不匹配 ⇒ 永远取默认 0
            #   ⇒ 前端「最佳/最差」恒 0.00%，真实值（实测 T+5 best=+121.73% /
            #   worst=-24.74%）被静默丢弃；且 max_drawdown / sharpe_ratio 从未复制
            #   ⇒ 前端「DD 0.00% / SR 0.00」亦是假 0。
            #   另一条铁律：**未知一律 None，绝不用 0 冒充**（0=算出来真是 0，
            #   None=没算；前端分别渲染 0.00% 与 —）。
            by_period[str(k).replace("d", "")] = {
                "samples": v.get("count"),
                "win_rate": v.get("win_rate"),
                "avg_return": v.get("avg_return"),
                "best_return": v.get("best_return"),
                "worst_return": v.get("worst_return"),
                "max_drawdown": v.get("max_drawdown"),
                "sharpe_ratio": v.get("sharpe_ratio"),
            }
    method = "四量终极历史回测：信号日次一交易日开盘买入，持有N个交易日收盘价卖出"
    # 🆕 2026-09-11：原文案没写成本口径，页面上看不出收益是否已扣费（口径不透明 = 半假）
    if bt_summary:
        method += f"（前复权；已扣双边交易成本 {2 * COST_BPS / 100:.2f}%）"
    if not by_period:
        method += ("（当前 0 信号，待四量信号恢复后自动填充）" if n == 0
                   else "（当前 %d 信号；深度分层回测待 --backtest 手动跑）" % n)
    data = {
        "update_time": update_time,
        "summary": {
            "update_time": update_time,
            "calc_time": update_time,
            "total_signals": (bt_summary or {}).get("total_signals", n),
            "method": method,
            # 🆕 2026-09-11：run_backtest 的 years 是唯一的区间事实，原来恒写 "—" 是空话
            "signal_date_range": (f"近 {(bt_summary or {}).get('years')} 年"
                                   if (bt_summary or {}).get("years") else None),
            "cost_bps_per_side": (bt_summary or {}).get("cost_bps_per_side"),
            "cost_adjusted": (bt_summary or {}).get("cost_adjusted"),
            "by_period": by_period,
        },
    }
    path = os.path.join(out_dir, "FOUR_VOLUME_BACKTEST.js")
    # 🛡 2026-09-16 主人令「不是真实的我不要」：回测口径防降级覆盖。
    #   事故：云端刷新链 cloud_fetch_v8.f_four_volume 重跑本脚本时不注入 V8_BACKTEST_YEARS
    #   → argparse 默认 3 年 → 09-16 02:09 把 E 批 5 年真值(861 信号)覆盖成 3 年/1400 信号。
    #   铁律：本外壳只允许「同档或升档」覆盖 —— 已存在更高 years 的分层真值时，
    #   低档回测或无回测(空壳)一律不得落盘，真值原地不动。
    try:
        _new_years = (bt_summary or {}).get("years")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as _f:
                _old = _f.read()
            import re as _re
            _m_y = _re.search(r'[\'"]signal_date_range[\'"]\s*:\s*[\'"]近 (\d+) 年', _old)
            _old_years = int(_m_y.group(1)) if _m_y else None
            _old_has_data = bool(_re.search(r'[\'"]by_period[\'"]\s*:\s*\{\s*[\'"]', _old))
            if _old_has_data and (_new_years is None
                                  or (_old_years is not None and _new_years < _old_years)):
                print(f"  🛡 跳过覆盖 {os.path.basename(path)}：已存 {_old_years} 年真值"
                      f"（本次 {'无回测' if _new_years is None else str(_new_years) + ' 年'}口径），禁止降级覆盖")
                return path
    except Exception as _e:
        print(f"  [warn] 回测外壳防降级检查异常，按原流程写出: {_e}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME_BACKTEST = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（回测外壳刷新，{data['summary']['total_signals']} 信号）")
    return path


# ── 2026-09-06 主人令 P0-C：默认跑回测（原 0=不跑 → 3=跑近 3 年）；保证 .js 外壳永不空 ===
# 原因：此前默认 0 → run_algorithms 即使注入 V8_BACKTEST_YEARS=3（现为 5），也被 0 覆盖场景未走主链路，
# 实际跑过但回测 → bt_summary=None → by_period={} → FOUR_VOLUME_BACKTEST.js 健康面板永 fail。
# 现默认值 3 + 任何情况下都跑空保底（无 XG 信号也写 n=0 + N 年 + 提示）。
COST_BPS = 15  # 单边万分之 1.5


def backtest_four_volume(years=3, top_cy=60, top_kc=60, top_zb=60, top_hk=30):
    """回看近 N 年，对活跃股池逐只找 XG 信号日，统计持有收益（非未来函数）。

    2026-09-06 主人令 P0-C/P1-A/P2-C：
      - 扣双边交易成本（万分之1.5×2 = 0.3%）
      - 输出 max_drawdown（按累计收益路径算全局最大回撤）
      - 输出 sharpe_ratio（均收益/收益样本标准差，简单近似）
j    - 前复权（fetch_a_daily 走 akshare/腾讯前复权，前端 np 已处理）
    """
    # 🔴 2026-09-12 扩档：+60 → +120 且下限抬到 480（覆盖 max(HOLD_LADDER)=90 交易日；
    #   原 3 年=810 根本身够，但 years 调小或 DAILY_BARS 被改小时会静默截断长档）。
    # 2026-09-13 主人令扩档：90 → 250 交易日，窗口下限 480 → 640。
    #   原式 int(years*250)+120：years=5 时 = 1370 够；但 years 被调小或
    #   DAILY_BARS 变小则 250 档静默截断 ⇒ 下限同步抬到 640 兜底。
    bars = max(DAILY_BARS, int(years * 250) + 250, 640)
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk)
    # 🔴 2026-09-12 主人令（拍板第 1 项·①）：持有期扩档 [1,3] + HOLD_LADDER。
    #   本脚本用 "Nd" 字符串键（与前端 by_period 键名一致），故在此展开为 str 形式；
    #   值来源是模块级 HOLD_LADDER（同源真源），不另立一套。
    periods = {f"{d}d": d for d in ([1, 3] + HOLD_LADDER)}
    cost_pct = 2 * COST_BPS / 100
    agg = {k: {"count": 0, "win": 0, "loss": 0, "draw": 0,
               "ret_sum": 0.0, "best": -1e9, "worst": 1e9,
               "equity_path": [],  # 每个信号的持有期收益路径（逐条算回撤）
               "nets": []}          # 单笔净收益（夏普用，不可与路径混用）
           for k in periods}
    total_signals = 0
    # 🔴 2026-09-16 阿狸咪的工程师 · 修「静默杀误杀」（D7 根因）：
    #   run_algorithms.py::_supervised_run 对「连续 SILENCE_KILL_SEC（默认 900s = 15min）无 stdout」
    #   判卡死并 kill 进程。本函数逐只抓 K 线、**循环体全程零输出**（原实现仅失败时与末尾各一处 print），
    #   5 年档（years=5 → bars >= max(1500, 640)）实测必被误杀 —— run 35006805941 / stage=E 实证：
    #   本脚本 03:16:55 起跑、03:32:00 被「静默卡死(>15min 无输出)，监督器已终止」，
    #   回测外壳写不出 ⇒ data/FOUR_VOLUME_BACKTEST.js 真值冻在旧 calc_time（health_check 永久红灯）。
    #   同型 2026-09-09 已在 v8/factor_lab_gen.py 修过一次（该脚本每 30s 一行心跳），此处同法补心跳。
    #   ⚠️ 必须 flush=True：监督器读的是 Popen 管道，Python 对管道默认块缓冲，
    #      print 不打进管道就等于没输出（这正是「有 print 也不够」的坑）。
    #   按「时间片」而非「只数」发心跳（单只取数本身可能很慢），保证任意时刻静默 < 60s；
    #   真挂死时心跳自然停止 ⇒ 监督器仍会 kill（不放松任何守门）。
    _hb_t = time.time()
    _hb_n = 0
    for s in stocks:
        code, market = s[0], s[2]
        _hb_n += 1
        if time.time() - _hb_t >= 60:
            print(f"  [backtest] 逐只回测进度 {_hb_n}/{len(stocks)} 只（心跳，防静默杀）", flush=True)
            _hb_t = time.time()
        try:
            df = fetch_hk_daily(code) if market == "hk" else fetch_a_daily(code, bars=bars)
            if df is None or len(df) < 60:
                continue
            df = calc_siliang_ultimate_signal(df)
            xg = df["四量终极_XG"].fillna(False).values
            closes = df["close"].astype(float).values
            opens = df["open"].astype(float).values
            for i in range(len(df)):
                if not xg[i]:
                    continue
                # 🔴 2026-09-13 主人令「统一测算标准 · 用最科学的计算」（小九周末审计 P1-1）：
                #   入场 = 信号日**次一交易日开盘**（原取信号日收盘 = 前视偏差：
                #   信号由当日收盘算出，「当日收盘价买入」实盘做不到 ⇒ 系统性高估）。
                e = i + 1                        # 入场日索引 = 信号日次一交易日
                if e >= len(df):
                    continue
                total_signals += 1
                entry_px = opens[e]              # 入场价 = 次日开盘
                if not (entry_px > 0):
                    continue
                for k, off in periods.items():
                    j = e + off
                    if 0 <= j < len(closes):
                        gross = (closes[j] / entry_px - 1) * 100
                        net = gross - cost_pct
                        a = agg[k]
                        a["count"] += 1
                        if net > 0:
                            a["win"] += 1
                        elif net < 0:
                            a["loss"] += 1
                        else:
                            a["draw"] += 1
                        a["ret_sum"] += net
                        a["best"] = max(a["best"], net)
                        a["worst"] = min(a["worst"], net)
                        # 🔴 2026-09-13 一劳永逸修复「算出的路径被丢弃」：
                        #   原实现逐日累加出 cum 后**从未使用**，只 append 单笔 net ⇒
                        #   下游「最大回撤」把单笔收益当净值累加求峰谷，量纲错误
                        #   （实测得 −133.56%，而回撤下界应为 −100%）。
                        #   现改为 append 该信号的持有期收益路径（成本按持有期比例摊，
                        #   与 net 同口径）。
                        _path = []
                        for m in range(1, off + 1):
                            jm = e + m
                            if 0 <= jm < len(closes):
                                _path.append((closes[jm] / entry_px - 1) * 100
                                             - cost_pct * (m / off))
                        a["equity_path"].append(_path)
                        a["nets"].append(net)
        except Exception as e:
            print(f"  [WARN] 回测 {code} 失败: {e}")
    summary = {
        "years": years,
        "total_signals": total_signals,
        "cost_bps_per_side": COST_BPS,
        "cost_adjusted": True,
        "periods": {},
    }
    for k, a in agg.items():
        c = a["count"]
        decided = a["win"] + a["loss"]
        # 🔴 2026-09-13 禁止 0 冒充：未到期/无样本 ⇒ None（前端「—」）
        win_rate = round(a["win"] / decided * 100, 1) if decided else None
        avg_return = round(a["ret_sum"] / c, 2) if c else None
        # 🔴 2026-09-13 一劳永逸修复「回撤量纲错误」：原实现把所有信号拼成一条线
        #   累加求峰谷 —— 那不是任何组合的净值曲线（实测 −133.56%，回撤下界应为
        #   −100%）。现改为**逐信号**算其持有期内回撤（相对该信号入场价的峰值回撤），
        #   再取均值 =>「单笔持仓期间的平均最大回撤」，下界天然 ≥ −100%。
        _dds = []
        for _pth in a["equity_path"]:
            if not _pth:
                continue
            _pk = 0.0
            _wr = 0.0
            for _v in _pth:
                if _v > _pk: _pk = _v
                _dd = _v - _pk
                if _dd < _wr: _wr = _dd
            _dds.append(_wr)
        max_dd = (sum(_dds) / len(_dds)) if _dds else 0.0
        # 夏普：用**单笔净收益**序列（与路径严格分开，绝不复用 equity_path）
        if c > 1:
            variance = sum((v - avg_return) ** 2 for v in a["nets"]) / (c - 1)
            std_ret = variance ** 0.5
            sharpe = round(avg_return / std_ret, 2) if std_ret > 0 else 0
        else:
            sharpe = 0
        summary["periods"][k] = {
            "count": c,
            "samples": c,
            "win": a["win"], "loss": a["loss"], "draw": a["draw"],
            "win_rate": win_rate,
            "avg_return": avg_return,
            # 无样本时写 None（不写 0）——0 会被前端画成「最佳 0.00%」，是假数据
            "best_return": round(a["best"], 2) if c else None,
            "worst_return": round(a["worst"], 2) if c else None,
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": sharpe,
        }
    out = os.path.join(DATA_DIR, "FOUR_VOLUME_BACKTEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    # 🛡 2026-09-04 主人令一劳永逸：同步补写 data/FOUR_VOLUME_BACKTEST.js —— 此前只写 .json，
    #   .js 自 09-02 手工跑后无人再生成（运维 all_ 动态扫描按通用 24h 红线必报孤儿 fail）。
    summary_out = dict(summary)
    summary_out["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_out["method"] = f"四量终极历史回测：信号日次一交易日开盘买入，持有N个真实交易日收盘价卖出（前复权；已扣双边交易成本 {2*COST_BPS/100:.2f}%）"
    with open(os.path.join(DATA_DIR, "FOUR_VOLUME_BACKTEST.js"), "w", encoding="utf-8") as f:
        f.write("/* 四量终极历史回测 strategy_four_volume.py 默认 3 年回测 */\n")
        f.write("window.FOUR_VOLUME_BACKTEST = " + json.dumps(summary_out, ensure_ascii=False) + ";\n")
    p5 = summary["periods"]["5d"]
    print(f"  四量终极回测: {total_signals} 个信号, "
          f"T+5 胜率 {p5['win_rate']}% / 均值 {p5['avg_return']}% / 最大回撤 {p5['max_drawdown']}%")
    return summary


def main():
    # 🛡 2026-08-20 主人令·一劳永逸：四量终极属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='strategy_four_volume')

    ap = argparse.ArgumentParser(description="四量终极 选股策略")
    ap.add_argument("--backtest", type=int,
                    default=int(os.environ.get("V8_BACKTEST_YEARS", "3") or 3),  # 2026-09-06 P0-C：默认跑回测（3 年）
                    help="同时跑近 N 年回测（0=不跑；E 回测批经 SCRIPT_ENV 注入 V8_BACKTEST_YEARS=5）")
    ap.add_argument("--top", type=int, default=80,
                    help="每板成交量前N(默认80, 控制扫描规模)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    records = []
    _scan_err = None
    try:
        records = scan_four_volume(top_cy=args.top, top_kc=args.top,
                                   top_zb=args.top, top_hk=max(20, args.top // 2))
    except Exception as e:
        # 🛡 2026-09-03 一劳永逸：扫描异常也要写出带新鲜时间戳的产物，避免
        #   data/FOUR_VOLUME.js 冻结在上一跑、被运维按陈旧判 fail（静默冻结根因）。
        print(f"  [ERROR] 四量终极日线扫描异常: {e}")
        _scan_err = e
    write_four_volume_js(records, scan_error=_scan_err)
    # 2026-09-06 P0-C：默认就跑回测（不再 0 不跑）。即便 args.backtest=0 或 records 空，也尝试 sync 写
    # 一个空回测外壳以保 FOUR_VOLUME_BACKTEST.js 新鲜。
    bt_summary = None
    if args.backtest and args.backtest > 0:
        try:
            bt_summary = backtest_four_volume(years=args.backtest)
        except Exception as e:
            print(f"  [WARN] 四量终极回测失败: {e} — 写空回测外壳保底")
            bt_summary = {
                "years": args.backtest,
                "total_signals": 0,
                "cost_bps_per_side": COST_BPS,
                "cost_adjusted": True,
                "periods": {
                    k: {"count": 0, "samples": 0, "win_rate": None, "avg_return": None,
                        "best_return": None, "worst_return": None,
                        "max_drawdown": None, "sharpe_ratio": None}
                    for k in ["1d", "3d", "5d", "10d", "20d"]
                },
                "method": f"四量终极历史回测：{e}",
            }
    # 🛡 2026-09-04 一劳永逸：策略回顾回测区读 .js 外壳（非 .json），此前为 09-02 手工
    #   空壳无人回写 → update_time 冻结、健康面板 all_FOUR_VOLUME_BACKTEST 永远 FAIL（误报）。
    write_four_volume_backtest_js(records, bt_summary)
    return records


if __name__ == "__main__":
    main()
