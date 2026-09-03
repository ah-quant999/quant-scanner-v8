#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四量终极 60分钟 选股策略模块（v8 候选策略 · 独立模块，不覆盖日线版）

· 复用 strategy_four_volume.calc_siliang_ultimate_signal() 的信号计算引擎（数学上与周期无关，
  输入 OHLCV 即可），仅数据源切换为 60 分钟 K 线。
· scan_four_volume_60m() : 走成交量前N活跃股池 + baostock 60min K线，逐只算 XG。
· write_four_volume_60m_js(): 写出 data/FOUR_VOLUME_60M.js 供 v8 站点渲染。
· backtest_four_volume_60m(years=1): 对命中票回看近 N 年 60min K线，统计 T+1~20 根 60min bar
  持有收益胜率（非未来函数）。

设计原则：
  - 独立 JS 输出文件（FOUR_VOLUME_60M.js），不覆盖日线版 FOUR_VOLUME.js。
  - 作为选股池的「加分因子」：60min 级别信号更灵敏，可捕捉日内级别资金异动，
    与日线版形成多周期共振验证。
  - 数据源：baostock（frequency="60"），云端/本地均可用，无需 mootdx。

数据来源：baostock query_history_k_data_plus(frequency="60", adjustflag="2" 前复权)。
"""
import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
ROOT = os.path.dirname(BASE_DIR)

# 输出目录解析（v8 双机/预览架构，2026-08-09 修复）：
#  1) 环境变量 V8_DATA_DIR 最高优先（云端/CI 可显式指定输出位置）；
#  2) 本机若存在真实仓库 E:/workspace/stock-scanner（git 源），直接写入其 data/，
#     便于生成后自动提交入库，避免数据只落在预览副本 quant-scanner-v8 而主站缺失；
#  3) 否则沿用脚本所在仓库 ROOT/data（云端 checkout 场景）。
_LOCAL_REPO = r"E:/workspace/stock-scanner"
if os.path.isdir(os.path.join(_LOCAL_REPO, ".git")):
    DATA_DIR = os.path.join(_LOCAL_REPO, "data")
else:
    DATA_DIR = os.path.join(ROOT, "data")
DATA_DIR = os.environ.get("V8_DATA_DIR", DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

# ── 导入日线版的信号计算引擎（纯数学，周期无关）──
from strategy_four_volume import (  # noqa: E402
    calc_siliang_ultimate_signal,
    _build_reason,
)

from scanner import (  # noqa: E402
    fetch_volume_top_stocks,
    resolve_clean_name_s,
)


# ──────────────────────────────────────────────────────────────────────
# 60分钟 K线数据源（baostock）
# ──────────────────────────────────────────────────────────────────────
# baostock frequency 参数:
#   "d"=日 "w"=周 "m"=月 "5"=5min "15"=15min "30"=30min "60"=60min
# 通达信市场代码 → baostock 前缀映射
_BAOSTOCK_MARKET = {"0": "sz", "1": "sh", "2": "bj"}
# 代码前缀 → (baostock_prefix, setcode) 映射（用于无 setcode 时推断）
_CODE_PREFIX_MAP = {
    "6": ("sh", "1"),   # 6xxxxx 主板/科创板
    "0": ("sz", "0"),   # 00xxxx 主板
    "3": ("sz", "0"),   # 30xxxx 创业板
    "8": ("bj", "2"),   # 8xxxxx 北交所
}

# 60min 最小 K 线根数：WMA20 需要 20 根 + 缓冲
MIN_60M_BARS = 60
# 拉取范围：约 120 根 60min bar ≈ 30 个交易日（留足回溯空间）
FETCH_60M_BARS = 120


def _bs_login():
    """获取/复用 baostock 登录连接（带缓存）。"""
    import baostock as bs
    if not getattr(_bs_login, "_logged_in", False):
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
        _bs_login._logged_in = True
        _bs_login._bs = bs
    return _bs_login._bs


def _bs_logout():
    """退出 baostock（模块级清理）。"""
    if getattr(_bs_login, "_logged_in", False):
        try:
            _bs_login._bs.logout()
        except Exception:
            pass
        _bs_login._logged_in = False


def _code_to_baostock(code, market=None):
    """将 code+market 转为 baostock 格式 'sh.600519'。

    Args:
        code: 6 位股票代码字符串（兼容已带 'sh.600519' 前缀）
        market: 'sh'/'sz'/'bj'、setcode '0'/'1'/'2'，或 None（自动推断）

    Returns:
        (bs_code, prefix) 如 ('sh.600519', 'sh')
    """
    code = str(code).strip().split('.')[-1]
    if market:
        # market 可能是 setcode（0/1/2）或 prefix（sh/sz/bj），统一转为 prefix
        prefix = _BAOSTOCK_MARKET.get(str(market), market)
    else:
        prefix, _ = _CODE_PREFIX_MAP.get(code[0], ("sz", "0"))
    return f"{prefix}.{code}", prefix


def fetch_a_60min(code, market=None, bars=FETCH_60M_BARS):
    """拉取单只股票 60 分钟 K 线（baostock，前复权）。

    Args:
        code: 6 位股票代码
        market: 'sh'/'sz'/'bj'（可选，自动推断）
        bars: 最多拉取根数（默认 120）

    Returns:
        pandas.DataFrame(date/open/close/high/low/volume/pct_chg) 或 None
        若数据不足 MIN_60M_BARS 根则返回 None。
    """
    bs_code, prefix = _code_to_baostock(code, market)

    # 北交所/港股 baostock 不支持 60min
    if prefix in ("bj", "hk"):
        return None

    try:
        bs = _bs_login()
    except Exception as e:
        print(f"  [60m] baostock 登录失败: {e}")
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_dt = datetime.now() - timedelta(days=90)  # 90 天足够覆盖 120 根 60min
    start_date = start_dt.strftime("%Y-%m-%d")

    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date, end_date=end_date,
            frequency="60",          # ← 60 分钟 K 线
            adjustflag="2",          # 前复权
        )
    except Exception as e:
        print(f"  [60m] {code} 查询异常: {e}")
        return None

    if rs is None or rs.error_code != "0":
        return None

    rows = []
    while rs.next():
        r = rs.get_row_data()
        try:
            if r[0] and float(r[4]) > 0:  # date 非空且 close > 0
                rows.append({
                    "date": r[0],
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                    "volume": float(r[5]) if r[5] else 0.0,
                })
        except (ValueError, IndexError):
            continue

    if len(rows) < MIN_60M_BARS:
        return None

    df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["pct_chg"] = 0.0
    if len(df) > 1:
        df["pct_chg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
    return df


# ──────────────────────────────────────────────────────────────────────
# 扫描 & 输出
# ──────────────────────────────────────────────────────────────────────

def scan_four_volume_60m(top_cy=80, top_kc=80, top_zb=80, top_hk=0):
    """扫描成交量前N活跃股池，用 60min K 线计算四量终极信号，返回末根 XG=True 的清单。

    注意：港股暂不支持（baostock 无港股 60min），top_hk 强制为 0。
    """
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk=0)
    if not stocks:
        print("  ⚠️ 活跃股池为空，四量终极 60min 扫描跳过")
        return []

    hits = []
    total = len(stocks)
    done = 0

    # 预登录 baostock（避免每只股票重复登录）
    try:
        _bs_login()
    except Exception as e:
        print(f"  ⚠️ baostock 无法启动，60min 扫描终止: {e}")
        return []

    for s in stocks:
        code, name, market, board_label = s[0], s[1], s[2], s[3]
        turnover_rate = s[5] if len(s) > 5 else 0
        mv_yi = s[6] if len(s) > 6 else 0
        fund_type = s[7] if len(s) > 7 else "混合"
        try:
            df = fetch_a_60min(code, market)
            if df is None or len(df) < MIN_60M_BARS:
                continue
            # 复用日线版信号引擎（输入 60min OHLCV）
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
                "board_label": board_label or (
                    "科创板" if code.startswith("688") else (
                        "创业板" if code.startswith("300") else "主板")),
                "close": round(close_price, 2),
                "pct_chg": round(pct, 2),
                "turnover_rate": round(turnover_rate, 2) if turnover_rate else 0,
                "mv_yi": round(mv_yi, 1) if mv_yi else 0,
                "fund_type": fund_type or "混合",
                "components": comp,
                "yzc": bool(comp.get("游资点火")),
                "jg": bool(comp.get("机构托底")),
                "xc": bool(last.get("四量终极_XC", False)),
                "four": bool(last.get("四量终极_FOUR", False)),
                "qd": bool(last.get("四量终极_XG", False)),
                "reason": _build_reason(comp),
                "signal_time": str(last.get("date", "")) if "date" in df.columns else "",
                "enter_date": str(last.get("date", "")) if "date" in df.columns else datetime.now().strftime("%Y-%m-%d"),
                # 标记来源为 60min（前端可据此区分显示）
                "period": "60m",
            })
        except Exception as e:
            print(f"  [WARN] {code} 60min 计算失败: {e}")
        done += 1
        if done % 50 == 0:
            print(f"  四量终极 60min 扫描进度: {done}/{total}, 命中 {len(hits)}")

    _bs_logout()
    print(f"  四量终极 60min 扫描完成: {total} 只, 命中 {len(hits)} 只")
    return hits


def write_four_volume_60m_js(records, out_dir=DATA_DIR):
    """写出 data/FOUR_VOLUME_60M.js（北京时间时间戳，供 v8 渲染）。"""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now() + timedelta(hours=8)
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    records = sorted(records, key=lambda x: -abs(x.get("pct_chg", 0)))
    data = {
        "update_time": update_time,
        "total": len(records),
        "period": "60m",
        "description": "四量终极 60分钟共振信号（加分因子，独立于日线版）",
        "stocks": records,
    }
    path = os.path.join(out_dir, "FOUR_VOLUME_60M.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.FOUR_VOLUME_60M=" + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"  ✅ 写出 {path}（{len(records)} 只命中, 周期=60min）")
    return path


def backtest_four_volume_60m(years=1, top_cy=60, top_kc=60, top_zb=60):
    """回测 60min 版本：对活跃股池逐只找 60min 级 XG 信号，统计持有收益。

    持有期以 60min bar 为单位：T+1/3/5/10/20 根 60min bar（约对应 1h/3h/5h/10h/20h）。
    非未来函数。
    """
    bars_needed = max(FETCH_60M_BARS, int(years * 250) + 60)  # 60min bar 数
    stocks = fetch_volume_top_stocks(top_cy, top_kc, top_zb, top_hk=0)
    periods = {"T+1bar": 1, "T+3bar": 3, "T+5bar": 5, "T+10bar": 10, "T+20bar": 20}
    agg = {k: {"count": 0, "win": 0, "ret_sum": 0.0, "best": -1e9, "worst": 1e9}
           for k in periods}
    total_signals = 0

    try:
        _bs_login()
    except Exception as e:
        print(f"  ⚠️ baostock 无法启动，回测终止: {e}")
        return {"error": str(e)}

    for s in stocks:
        code, market = s[0], s[2]
        try:
            df = fetch_a_60min(code, market, bars=bars_needed)
            if df is None or len(df) < MIN_60M_BARS:
                continue
            df = calc_siliang_ultimate_signal(df)
            xg = df["四量终极_XG"].fillna(False).values
            closes = df["close"].astype(float).values
            for i in range(len(df)):
                if not xg[i]:
                    continue
                total_signals += 1
                for k, off in periods.items():
                    j = i + off
                    if 0 <= j < len(closes):
                        ret = (closes[j] / closes[i] - 1) * 100
                        a = agg[k]
                        a["count"] += 1
                        a["win"] += 1 if ret > 0 else 0
                        a["ret_sum"] += ret
                        a["best"] = max(a["best"], ret)
                        a["worst"] = min(a["worst"], ret)
        except Exception as e:
            print(f"  [WARN] 回测 60min {code} 失败: {e}")

    _bs_logout()

    summary = {
        "years": years,
        "period": "60m",
        "total_signals": total_signals,
        "periods": {},
    }
    for k, a in agg.items():
        c = a["count"]
        summary["periods"][k] = {
            "count": c,
            "win_rate": round(a["win"] / c * 100, 1) if c else 0,
            "avg_return": round(a["ret_sum"] / c, 2) if c else 0,
            "best": round(a["best"], 2) if c else 0,
            "worst": round(a["worst"], 2) if c else 0,
        }
    out = os.path.join(DATA_DIR, "FOUR_VOLUME_60M_BACKTEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    p5 = summary["periods"].get("T+5bar", {})
    print(f"  四量终极 60min 回测: {total_signals} 个信号, "
          f"T+5bar 胜率 {p5.get('win_rate',0)}% / 均值 {p5.get('avg_return',0)}%")
    return summary


def _find_git_root(path):
    """从文件/目录向上查找最近的 .git 仓库根。"""
    cur = os.path.abspath(path)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def auto_commit_and_mirror(paths):
    """生成后：把数据文件提交进真实仓库并推送，再镜像到本地预览副本（best-effort）。

    目的：防止 60m 数据只落在预览副本 quant-scanner-v8 而真实仓库/主站缺失，
    导致三处再次漂移（见 2026-08-09 审计）。仅在文件确实变更时才提交。
    """
    paths = [p for p in paths if p and os.path.exists(p)]
    if not paths:
        return
    repo = _find_git_root(paths[0])
    if repo:
        try:
            rels = [os.path.relpath(p, repo) for p in paths]
            subprocess.run(["git", "add", *rels], cwd=repo, check=True)
            st = subprocess.run(["git", "status", "--porcelain", *rels],
                                cwd=repo, capture_output=True, text=True)
            if st.stdout.strip():
                msg = "data: 自动提交 60m 共振数据 " + ", ".join(
                    os.path.basename(p) for p in paths)
                subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True)
                print(f"  ✅ 已提交至仓库 {repo}")
                pr = subprocess.run(["git", "push", "origin", "main"], cwd=repo,
                                    capture_output=True, text=True)
                if pr.returncode == 0:
                    print("  ✅ 已推送 origin/main")
                else:
                    print(f"  ⚠️ 推送暂被拒（可能需 rebase），稍后重试: {pr.stderr[:160]}")
            else:
                print("  （60m 数据无变化，跳过提交）")
        except Exception as e:
            print(f"  ⚠️ 自动提交失败（文件已生成，未入库）: {e}")
    # 镜像到本地预览副本，保持书签 file:///.../quant-scanner-v8 同步
    preview = r"E:/workspace/quant-scanner-v8/data"
    if os.path.isdir(preview):
        try:
            import shutil
            for p in paths:
                shutil.copy2(p, os.path.join(preview, os.path.basename(p)))
            print(f"  ✅ 已镜像到预览副本 {preview}")
        except Exception as e:
            print(f"  ⚠️ 镜像预览副本失败: {e}")


def main():
    # 🛡 2026-08-20 主人令·一劳永逸：四量终极 60分钟属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='strategy_four_volume_60m')

    ap = argparse.ArgumentParser(description="四量终极 60分钟 选股策略（独立模块）")
    ap.add_argument("--backtest", type=int, default=0,
                    help="同时跑近 N 年回测(0=不跑, 默认0)")
    ap.add_argument("--top", type=int, default=80,
                    help="每板成交量前N(默认80)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    records = []
    try:
        records = scan_four_volume_60m(top_cy=args.top, top_kc=args.top,
                                       top_zb=args.top)
    except Exception as e:
        # 🛡 2026-09-03 一劳永逸：扫描异常也要写出带新鲜时间戳的产物，避免
        #   data/FOUR_VOLUME_60M.js 冻结在上一跑、被运维按陈旧判 fail（静默冻结根因）。
        print(f"  [ERROR] 四量终极60m扫描异常: {e}")
    # 🛡 2026-09-03 一劳永逸：无论命中多少只（含 0 只）都写出带新鲜时间戳的产物，
    #   不再「跳过写入保留上次」——那种写法正是 data/FOUR_VOLUME_60M.js 静默冻结的根因。
    write_four_volume_60m_js(records)
    if args.backtest > 0:
        try:
            backtest_four_volume_60m(years=args.backtest)
        except Exception as e:
            print(f"  [WARN] 60m 回测失败: {e}")
    return records


if __name__ == "__main__":
    main()
