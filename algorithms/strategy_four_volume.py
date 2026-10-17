#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 选股策略模块（v8 候选策略 · 暂未上架区）

· calc_siliang_ultimate_signal 本模块自包含，忠实翻译用户 2026-08-05 通达信「四量终极 指标版 副图」公式（原贴完整源码，已核对）。
· 信号 QD = YZC AND JG AND XC AND FOUR：游资点火 YZC=CROSS(W2,0) / 机构托底 JG=C>NLJ / 当天金叉 XC=JGC|SHC|YZC|ZLC（四金叉取或）/ 四路翻多 FOUR=JG&GB1>=0&W2>=0&V6>=0。
· scan_four_volume()  : 复用 scanner 的成交量前N活跃股池 + 日K 抓取，逐只算 XG，
                        收集末根触发 XG 的票，产出命中清单（含组件灯 + 触发理由）。
· write_four_volume_js(): 写出 data/FOUR_VOLUME.js 供 v8 站点渲染。
# · backtest_four_volume(years=3)：已于 2026-10-16 摘链（2026-10-11 主人令：回测只认真实
#   信号流口径；历史规则回放含幸存者偏差作废）。回测卡内容源见 gen_four_volume_track.py。

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




# ── 🔴 2026-10-16 阿狸咪的工程师（摘链）：2026-09-06 P0-C「默认跑回测保外壳新鲜」令与
#   backtest_four_volume() 近 N 年历史规则回放引擎、write_four_volume_backtest_js() 回放
#   外壳直写，已按 2026-10-11 主人令「所有回测只认真真信号流口径」整体作废下线。
#   事故链：回放口径含当前股池幸存者偏差（近5年/1546 样本 T+5 51.8%/+1.97% 与真实流
#   9-14 起 89 笔 T+5 31.6%/-1.25% 严重背离）；且每晚由 run_algorithms 四量硬等待重跑链
#   （_fv_env V8_BACKTEST_YEARS=5 注入，已同步摘除）刷新覆盖，持续产生违规展示。
#   现状：FOUR_VOLUME_BACKTEST.js 由真实流视图驱动（gen_four_volume_track 产 raw +
#   update_v8 映射转换），前端渲染器/回测聚合器 parse_by_period 零结构改动。



def main():
    # 🛡 2026-08-20 主人令·一劳永逸：四量终极属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='strategy_four_volume')

    ap = argparse.ArgumentParser(description="四量终极 选股策略")
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
    # 🔴 2026-10-16 阿狸咪的工程师（摘链）：近 N 年历史规则回放（backtest_four_volume）与
    #   write_four_volume_backtest_js 回放外壳直写已按 2026-10-11 主人令「所有回测只认
    #   真实信号流口径」整体摘除。data/FOUR_VOLUME_BACKTEST.js 内容源改走：
    #   gen_four_volume_track.py::emit_backtest_view() → raw_data/four_volume_backtest.json
    #   → update_v8.py DATA_SOURCES 映射（four_volume_backtest.json→FOUR_VOLUME_BACKTEST）
    #   → 盘后构建统一转换发布。回放口径（含幸存者偏差）作废下线，永不再写。
    return records


if __name__ == "__main__":
    main()
