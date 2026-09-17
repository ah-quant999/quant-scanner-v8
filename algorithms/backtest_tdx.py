#!/usr/bin/env python3
"""
backtest_tdx.py — 通达信60天全量回测引擎 V3.2（方案二：止损止盈升级）
==========================================================================
用通达信K线拉金池股60天日K，计算全部可检测信号的T+1/T+3/T+5/T+10/T+20胜率。
收益口径已升级为「统一止损止盈 + 提前出场」：
  止损 = max(近20日低点, close-2ATR, 固定百分比)
  止盈 = cascade：前高 → 0.618回撤位 → R:R=2对称位（盈亏比≥1.5）
  ret_Nd 为提前出场后收益；raw_ret_Nd 为原持有期收盘价收益。

可检测信号（价格/量可推导）：
  - 上涨趋势  (EMA7>EMA14>EMA20)
  - 缠论买点  (底分型+量确认)
  - 逆势红色  (大盘跌时个股涨)
  - 价格突破  (5日/20日新高)
  - 放量上涨  (量>1.5倍均值+收阳)
  - 量价背离  (价新高但量萎缩）

不可检测（需外部数据）：
  - 金钻/黄柱 (需要XMA+DDX)
  - 机构变红  (需要机构数据)
  - 机游共振  (需要龙虎榜席位）

输出: data/backtest_tdx.json
"""
import json
import math
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

sys.path.insert(0, BASE)
from stop_target_logic import (  # noqa: E402
    compute_stop_target,
    board_from_code,
)

BASE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：历史快照目录从 out/（gitignore，云端丢）→ raw_data/
DATA_DIR = os.path.join(BASE, "..", "raw_data")
OUT = os.path.join(DATA_DIR, "backtest_tdx.json")
TODAY = datetime.now().strftime("%Y-%m-%d")
# 🔴 2026-09-12 主人令（拍板第 1 项·①）：回测持有期统一阶梯（近→远）。
#   主人原话：「可以从近到远，从5天开始、10天、20天、30天、45天、60天、75天、90天
#   这样写出来慢慢跟踪」。短档 1/3 保留（隔日冲高/短线验证有独立价值）。
#   ⚠️ **同源铁律**：本阶梯是唯一真源，四个回测脚本一律引此常量；
#      各写一套必然漂移（本仓历史教训）。
HOLD_LADDER = [5, 10, 20, 30, 45, 60, 75, 90, 180, 250]
# 🔴 2026-09-12 主人令：原 [1,3,5,10,20] → [1,3] + HOLD_LADDER。
#   ⚠️ 只改档位**不够** —— 原 tdx_kline(count=60) 只有 60 根日K，而下面
#      `idx + max(HOLD_DAYS) >= n` 会把近 90 个交易日内的信号**整条跳过**
#      ⇒ 长档静默零样本（不是算出 0，是没算）。故 TDX_BARS 同步放宽。
HOLD_DAYS = [1, 3] + HOLD_LADDER  # 2026-07-26 基线 [1,3,5,10,20]；2026-09-12 扩档
TDX_BARS = 520  # 覆盖 250 交易日持有 + 信号检测自身窗口（2026-09-13 主人令：90→250 档，260→520）

# 🔴 2026-09-13 主人令「统一测算标准 · 回测入场口径统一」——**口径版本号**（小九审计修复）
#   背景：本脚本有**明细级断点续跑缓存**（见下方 `if key in stock_results`）——
#   已回测过的股票直接 `continue` 跳过，只补新股票。于是 09-13 把入场口径从
#   「信号日收盘」改成「次一交易日开盘」后，**既有 221 只股票一条都不会重算**，
#   summary 与旧产物逐字相同（实测：改完重跑，total/胜率/收益全部一模一样）
#   ⇒ 口径统一对 TDX 主数据完全失效 = 「改了但没生效」的隐性形态。
#   修法：把口径版本写进明细，版本不匹配即整只重算 —— 以后每次口径变更只改这一个数字。
#     1 = 信号日收盘价买入（2026-09-13 之前的旧口径）
#     2 = 信号日次一交易日开盘买入（2026-09-13 起）
#     3 = v2 入场口径 + **信号样本窗口修复**（2026-09-14：原判据要求最长档 T+250
#         有完整前瞻数据才记录信号日 ⇒ 近 250 个交易日整条跳过、近一年样本消失；
#         现改为只要求「入场日 + 最短档」，长档未到期即 None。样本集合因此变化，
#         必须整只重算，故升版号 —— 复用同一机制，不新增第二套开关。）
ENTRY_CALIBER_VER = 3

# 2026-09-06 主人令 P1-A：A 股交易成本默认假设（单边 万分之1.5，双边 0.3%）
COST_BPS = 15

# ═══ 2026-08-09 主人令：提胜率优化策略（①+②+③）═══
# ① 持仓周期纪律：把最长持有期从 20d 收紧到 10d
# ② 多源共振过滤：只做 ≥3 信号共振（ge3）
# ③ 行情 regime 门控：上证+沪深300 定义市场状态；
#    数据回测显示"企稳/反弹"段 ge3 信号整体负期望，"阴跌/恐慌"段 ge3 信号显著正期望，
#    故优化策略只在 grind/panic  regimes 开仓，且允许全部 ge3 信号。
OPTIMIZED = {
    "enabled": True,
    "max_hold_days": 10,          # ① 默认最长持有期
    "min_signal_count": 3,        # ② ≥3 共振
    "regime_signals": {           # ③ 市场状态 → 允许子信号
        "stabilize": [],          # 好状态空仓
        "rebound_diverge": [],    # 好状态空仓
        "grind": ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence"],
        "panic": ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence"],
    },
    "report_periods": [5, 10],    # 优化策略主要展示周期
    "note": "数据驱动：仅在市场状态为 grind/panic 时开仓",
}


def _fetch_index_ohlc(code, prefix, days=None):
    """从 baostock 拉取指数日K，返回 [(date, close)]。

    🔴 2026-09-14 小九审计修复（P0 · regime 序列窗口短于信号窗口）：
      原默认 `days=150`（自然日）⇒ 扣掉 regime 自身预热只剩约 76 个交易日，
      而本回测的信号窗口长达两年 ⇒ 两者交集恒为空，OPTIMIZED 的 regime 门控
      **一个样本都匹配不到**（优化策略汇总整块消失，下游导出脚本 exit 1）。
      现默认覆盖「K线窗口 + 最长持有期 + 预热余量」，随 TDX_BARS 自动伸缩，
      以后扩档不会再次失配。
    """
    if days is None:
        days = int((TDX_BARS + max(HOLD_DAYS)) * 365 / 244) + 90
    from fetch_source import socket_timeout, SOURCE_BREAKER
    if SOURCE_BREAKER.is_open("baostock"):
        log(f"  [_fetch_index_ohlc] {code}: baostock 熔断冷却中，跳过")
        return []
    import baostock as bs
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        with socket_timeout(25):
            bs.login()
            rs = bs.query_history_k_data_plus(
                f"{prefix}.{code}", "date,close", start_date=start, end_date=end,
                frequency="d", adjustflag="3"
            )
            bs.logout()
        rows = []
        if rs is not None:
            while (rs.error_code == "0") & rs.next():
                r = rs.get_row_data()
                try:
                    rows.append((r[0], float(r[1])))
                except Exception:
                    pass
        SOURCE_BREAKER.mark_success("baostock")
        rows.sort(key=lambda x: x[0])
        return rows
    except Exception as e:
        SOURCE_BREAKER.mark_failure("baostock")
        log(f"  [_fetch_index_ohlc] {code}: {e}")
        return []


def _compute_regime_series(rows):
    """从指数 close 序列计算每日 regime（与 analyze_regime_filter.py 保持一致）"""
    closes = [c for _, c in rows]
    n = len(closes)
    if n < 22:
        return {}

    log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]

    def _std(xs):
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    daily_vol = []
    for i in range(19, len(log_rets)):
        w = log_rets[i - 19:i + 1]
        daily_vol.append(_std(w) * math.sqrt(252) * 100.0)

    regime_by_date = {}
    for i in range(21, n):
        vol_idx = i - 21
        if vol_idx < 5:
            continue
        vol_20d = daily_vol[vol_idx]
        vol_20d_ago5 = daily_vol[vol_idx - 5]
        vol_trend_pct = ((vol_20d - vol_20d_ago5) / vol_20d_ago5 * 100.0) if vol_20d_ago5 else 0.0
        ret_20d = (closes[i] / closes[i - 20] - 1.0) * 100.0

        if ret_20d >= 0 and vol_trend_pct < 0:
            regime = "stabilize"
        elif ret_20d < 0 and vol_trend_pct < 0:
            regime = "grind"
        elif ret_20d >= 0 and vol_trend_pct >= 0:
            regime = "rebound_diverge"
        else:
            regime = "panic"
        regime_by_date[rows[i][0]] = regime
    return regime_by_date


def _merge_market_regime():
    """合并上证与沪深300 regime，取更悲观者。"""
    priority = {"panic": 3, "grind": 2, "rebound_diverge": 1, "stabilize": 0}
    sh_regime = _compute_regime_series(_fetch_index_ohlc("000001", "sh"))
    hs300_regime = _compute_regime_series(_fetch_index_ohlc("000300", "sh"))
    all_dates = set(sh_regime.keys()) | set(hs300_regime.keys())
    merged = {}
    for d in all_dates:
        r1 = sh_regime.get(d, "stabilize")
        r2 = hs300_regime.get(d, "stabilize")
        merged[d] = r1 if priority.get(r1, 0) >= priority.get(r2, 0) else r2
    return merged


def passes_optimized_filter(sigs, market_regime):
    """判断一组信号是否满足优化策略的入池条件：ge3 + 市场regime-信号匹配。"""
    if not sigs.get("ge3_signals", False):
        return False
    regime = market_regime
    if regime not in OPTIMIZED["regime_signals"]:
        return False
    allowed = OPTIMIZED["regime_signals"][regime]
    active = {k for k, v in sigs.items() if v and not k.startswith("ge")}
    return bool(active & set(allowed))

def log(msg):
    print(f"  {msg}")

# 🔴 2026-09-14 小九审计修复（P0 · 产物体积逼近 GitHub 单文件硬限）：
#   本产物含 12 档 × 221 只的逐笔明细，indent=2 序列化后达 126.9 MB > GitHub 100 MiB
#   单文件硬限 ⇒ push 必被拒（能跑完却推不上去的隐性故障）。改为统一入口紧凑序列化
#   （零信息损失，126.9 MB → 72.6 MB），并加 95 MB 体积告警护栏提前暴露。
_FMT_SEP = (",", ":")
# 2026-09-18 阿狸咪的工程师·体积护栏收紧（P0 根治）：
#   原值 95 MB 形同虚设——产物实测 72.6 MB 时护栏从未触发，而此时已超 GitHub
#   建 blob 上限 ⇒ E 批每天 8 次重试全报 HTTP 422、线上产物永久停在 09-14。
#   产品产物现只含汇总（正常 100 KB 量级），任何超过 5 MB 都说明明细又被写回，须立即暴露。
_SIZE_WARN = 5 * 1024 * 1024
# 明细缓存路径（raw_data/_tdx_cache/ 已在 .gitignore ⇒ 不入仓、不推送）：
#   仅供本机/同一 runner 工作目录内的断点续跑；产品产物 OUT 不再含明细（见文件末写出处）。
_STOCK_CACHE = os.path.join(DATA_DIR, "_tdx_cache", "backtest_tdx_stocks.json")

def _dump_json(obj, path):
    """统一写出入口：紧凑序列化 + 体积护栏（防「能跑但推不上去」的隐性故障）。"""
    _pd = os.path.dirname(path)
    if _pd:
        os.makedirs(_pd, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=_FMT_SEP)
    try:
        _sz = os.path.getsize(path)
    except OSError:
        return
    if _sz > _SIZE_WARN:
        log(f"🔴 [P0] {os.path.basename(path)} 已达 {_sz/1048576:.1f} MB，逼近 GitHub 100 MiB "
            f"单文件硬限 ⇒ push 随时会被拒。请瘦身（可去 win_Nd 冗余档，见交接文档遗留项）")


# ─── 通达信K线工具 ───
def tdx_kline(code, setcode, period="4", count=TDX_BARS):  # 2026-09-13：默认值跟随 TDX_BARS（调用处已显式传参）
    """通过subprocess调通达信MCP接口（因部署环境可能无MCP，做本地回退）"""
    # 如果本地有缓存优先用
    cache_dir = os.path.join(DATA_DIR, "_tdx_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = f"{setcode}_{code}_{period}_{count}"
    cache_file = os.path.join(cache_dir, cache_key.replace(".", "_") + ".json")
    if os.path.exists(cache_file) and os.path.getmtime(cache_file) > time.time() - 86400:
        try:
            d = json.load(open(cache_file, "r", encoding="utf-8"))
            if d.get("rows") and len(d["rows"]) >= 10:
                log(f"  [缓存] {code} ({setcode}) → {len(d['rows'])} 根K")
                return d["rows"]
        except:
            pass
    
    # 用 baostock 作主数据源（云端/本地都能跑，比MCP可靠）
    # 通达信MCP在自动化环境可能不可用，baostock是Pypi包，已安装
    from fetch_source import socket_timeout, SOURCE_BREAKER
    if SOURCE_BREAKER.is_open("baostock"):
        log(f"  [baostock] {code}: 近期连续失败，熔断冷却中，跳过（走缓存/兜底）")
        return None
    import baostock as bs
    try:
        with socket_timeout(25):
            lg = bs.login()
            if lg.error_code != "0":
                log(f"  baostock登录失败: {lg.error_msg}")
                return None
            # code needs to be like "sz.002141" or "sh.601318"
            market_map = {"0": "sz", "1": "sh", "2": "bj", "31": "hk"}
            prefix = market_map.get(str(setcode), "sz")
            bs_code = f"{prefix}.{code}"

            end_date = TODAY  # 保持 YYYY-MM-DD
            # 🔴 2026-09-13 主人令（档位扩至 250 日）——真根因修复：
            #   原经典写死 `timedelta(days=90)`（≈60 交易日），
            #   count 参数**只用于缓存键**、根本没参与 baostock 取数。
            #   故把 TDX_BARS 从 260 改到 520 是**无效改动** ——
            #   窗口没变，T+30 以上仍必然零样本（不是算出 0，是根本没取到那么长的K线）。
            #   现让 count 真正驱动窗口：自然日 ≈ 交易日 × 7/5 + 缓冲（覆盖长假），下限 120 天兜底。
            _span_days = max(120, int(count * 7 / 5) + 30)
            start_dt = (datetime.now() - timedelta(days=_span_days)).strftime("%Y-%m-%d")
            start_date = start_dt

            # baostock 不支持港股，跳过
            if prefix == "hk":
                return None

            rs = bs.query_history_k_data_plus(bs_code,
                "date,close,high,low,open,volume,amount",
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="2")  # 后复权
            bs.logout()
        
        # rs 可能为 None（查询失败）
        if rs is None or rs.error_code != "0":
            log(f"  [baostock] {code}: 查询失败 ({rs.error_msg if rs else 'unknown'})")
            return None
        
        rows = []
        while rs.next():
            r = rs.get_row_data()
            if r[0] and float(r[1]) > 0:
                rows.append({
                    "date": r[0],
                    "close": float(r[1]),
                    "high": float(r[2]) if r[2] else float(r[1]),
                    "low": float(r[3]) if r[3] else float(r[1]),
                    "open": float(r[4]) if r[4] else float(r[1]),
                    "volume": float(r[5]) if r[5] else 0,
                    "amount": float(r[6]) if r[6] else 0,
                })
        
        if rows:
            rows.sort(key=lambda x: x["date"])
            log(f"  [baostock] {code} ({bs_code}) → {len(rows)} 根K ({rows[0]['date']} ~ {rows[-1]['date']})")
            # 缓存
            json.dump({"rows": rows, "ts": TODAY}, open(cache_file, "w", encoding="utf-8"))
            SOURCE_BREAKER.mark_success("baostock")
            return rows
        else:
            log(f"  [baostock] {code}: 空数据")
            return None
    except Exception as e:
        SOURCE_BREAKER.mark_failure("baostock")
        log(f"  [baostock] {code}: {e}")
        return None


# ─── 信号检测器 ───
def detect_signals(rows):
    """从K线序列检测所有可计算信号，返回 {date: {signal_name: bool}}"""
    signals = {}
    n = len(rows)
    if n < 30:
        return signals
    
    # 提前算好所有需要的指标
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    opens = [r["open"] for r in rows]
    volumes = [r["volume"] for r in rows]
    
    # EMA计算
    def ema(data, period):
        result = [data[0]]
        k = 2 / (period + 1)
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result
    
    ema7 = ema(closes, 7)
    ema14 = ema(closes, 14)
    ema20 = ema(closes, 20)
    
    # 均量线
    vol_ma20 = []
    for i in range(len(volumes)):
        start = max(0, i - 19)
        vol_ma20.append(sum(volumes[start:i+1]) / (i - start + 1))
    
    for i in range(20, n):
        date = rows[i]["date"]
        sigs = {}
        
        # 1. 上涨趋势: EMA7 > EMA14 > EMA20
        sigs["trend_up"] = ema7[i] > ema14[i] > ema20[i]
        
        # 2. 下跌趋势 (补充)
        sigs["trend_down"] = ema7[i] < ema14[i] < ema20[i]
        
        # 3. 缠论底分型: 低-低-高 结构 + 量确认
        if i >= 2:
            low_prev2 = lows[i-2]
            low_prev1 = lows[i-1]
            low_curr = lows[i]
            # 底分型: 前低 < 前前低, 当日低 < 前低 (形成底部), 当日收阳
            is_bottom_pattern = lows[i-1] < lows[i-2] and lows[i] < lows[i-1] and closes[i] > lows[i]
            vol_confirm = volumes[i] > vol_ma20[i] * 0.8
            sigs["chan_buy"] = is_bottom_pattern and vol_confirm
        
        # 4. 逆势红色: 大盘跌时个股涨 (简化: 连跌2天后今日收涨)
        if i >= 2:
            prev_down = closes[i-2] > closes[i-1]  # 前日跌
            today_up = closes[i] > opens[i] and closes[i] > closes[i-1]  # 今日收涨
            sigs["contrarian"] = prev_down and today_up
        
        # 5. 价格突破: 创5日新高
        high_5d = max(highs[max(0,i-4):i+1])
        sigs["breakout_5d"] = highs[i] >= high_5d and closes[i] > closes[i-1]
        
        # 6. 放量上涨: 量>1.5×均量 + 收阳
        sigs["volume_surge"] = volumes[i] > vol_ma20[i] * 1.5 and closes[i] > opens[i]
        
        # 7. 量价背离: 价新高但量萎缩
        if i >= 5:
            price_up = closes[i] > closes[i-1] > closes[i-2]
            vol_down = volumes[i] < volumes[i-1] < volumes[i-2]
            sigs["divergence"] = price_up and vol_down
        
        # 8. 综合多信号 (≥2个信号同时触发)
        signal_count = sum(1 for v in sigs.values() if v)
        sigs["ge2_signals"] = signal_count >= 2
        sigs["ge3_signals"] = signal_count >= 3
        
        if any(sigs.values()):
            signals[date] = sigs
    
    return signals


def calc_forward_return(rows, idx, hold_days, board="主板", st_cache=None):
    """计算T+N日收益（方案二：按统一止损止盈口径模拟提前出场）。

    返回 {"ret": 提前出场后收益, "raw_ret": 原持有期收盘价收益,
          "exit_type": 'stop'/'target'/None, "stop_loss": ..., "target_price": ..., "risk_reward": ...}

    st_cache: 可选的「止损/止盈」记忆字典（键=入场日索引）。止损/止盈只与入场日+板块
              有关、与持有档位无关，而本函数对同一信号日会被 HOLD_DAYS 各档各调一次，
              故由调用方传入本字典即可把 12 档的重复计算收敛为 1 次（2026-09-14 小九）。
    """
    # 🔴 2026-09-13 主人令「统一测算标准 · 用最科学的计算」（小九周末审计 P1-1）：
    #   入场 = 信号日**次一交易日开盘**。原取「信号日收盘」= 前视偏差：
    #   本信号由盘后 18:10（B 批）用**当日收盘**数据算出，「当日收盘价买入」实盘做不到；
    #   且动量/突破类信号当日多伴涨 ⇒ 等于白拿尾盘涨幅 ⇒ 系统性高估（T+1 档最失真）。
    n = len(rows)
    entry_idx = idx + 1                     # 次一交易日 = 入场日
    target = entry_idx + hold_days          # 持有期自入场日起算
    if target >= n:
        return None
    entry = rows[entry_idx].get("open")     # 入场价 = 次日开盘
    if not entry or entry <= 0:
        return None
    idx = entry_idx                         # 后续止损模拟/收益窗口一律以入场日为基准

    # 用「入场日之前」数据计算止损/止盈（不含入场日 ⇒ 严格非未来函数）
    # 🛡 2026-09-14 小九性能修复：止损/止盈只与「入场日 + 板块」有关、**与持有档位无关**，
    #   而本函数被 HOLD_DAYS（现 12 档）对同一信号日各调用一次 ⇒ 同一天白算 12 遍。
    #   实测单只 500 根K 的股票需 ~5300 次 compute_stop_target（26s/只 ⇒ 全量 95 分钟）。
    #   以 entry_idx 为键记忆后降到 ~440 次；compute_stop_target 是确定性纯函数
    #   （无 random / 无 now / 无 time），故结果逐位不变（已用 6 只股票逐字节对照验证）。
    if st_cache is not None and idx in st_cache:
        st = st_cache[idx]
    else:
        df = pd.DataFrame(rows[: idx])
        st = compute_stop_target(df, board=board, strategy="tdx")
        if st_cache is not None:
            st_cache[idx] = st
    if st:
        stop_loss = st["stop_loss"]
        target_price = st["target_price"]
        rr = st["risk_reward"]
    else:
        # 数据不足时回退方案三统一口径：固定10%止损 + R:R=1.5止盈
        stop_loss = entry * 0.90
        target_price = entry * 1.15
        rr = 1.5

    # 模拟每日 close 触发止损/止盈
    exit_price = rows[target]["close"]
    exit_type = None
    for j in range(idx + 1, target + 1):
        cp = rows[j]["close"]
        if cp <= stop_loss:
            exit_price = stop_loss
            exit_type = "stop"
            break
        if cp >= target_price:
            exit_price = target_price
            exit_type = "target"
            break

    raw_ret = round((rows[target]["close"] - entry) / entry * 100, 2)
    early_ret = round((exit_price - entry) / entry * 100 - 2 * COST_BPS / 100, 2)  # P1-A 扣双边 0.3%
    return {
        "ret": early_ret,
        "raw_ret": raw_ret,
        "exit_type": exit_type,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_reward": rr,
        "cost_adjusted": True,
    }


def _load_historical_pool_union(current_gp):
    """读取最近 90 天金股池快照的并集，减少「当前池=幸存者」偏差。
    快照不足时回退到当前池，并返回警告标志。"""
    hist_dir = os.path.join(DATA_DIR, "history")
    if not os.path.isdir(hist_dir):
        return current_gp, False, 0

    union_stocks = {}
    today = datetime.now().date()
    snapshots_used = 0
    for fn in sorted(os.listdir(hist_dir), reverse=True):
        if not fn.startswith("gold_pool_") or not fn.endswith(".json"):
            continue
        # 解析日期 gold_pool_YYYYMMDD.json
        try:
            date_str = fn.replace("gold_pool_", "").replace(".json", "")
            snap_date = datetime.strptime(date_str, "%Y%m%d").date()
        except Exception:
            continue
        if (today - snap_date).days > 90:
            continue
        try:
            snap = json.load(open(os.path.join(hist_dir, fn), "r", encoding="utf-8"))
            union_stocks.update(snap.get("stocks", {}))
            snapshots_used += 1
        except Exception:
            pass

    if snapshots_used <= 1:
        # 只有今天或没有快照，尚无法纠偏，回退当前池
        return current_gp, True, snapshots_used
    return union_stocks, False, snapshots_used


def main():
    print(f"\n{'='*60}")
    print(f"  通达信60天全量回测引擎 V3")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 读金股池，并尝试用历史快照并集作为回测宇宙（纠偏幸存者偏差）
    # 🔴 2026-08-11 修复顺序缺陷 + 空文件容错：本轮 fresh gold_pool 由 scanner.py 直产到 out/，
    #    raw_data/gold_pool.json 要等 stage_to_raw（step2）才刷新；本脚本在 step1 运行，
    #    直接读 raw_data 会拿到上一轮的旧/空文件 → 空文件触发 JSONDecodeError 崩溃。
    #    故优先读 out/gold_pool.json（本轮），回退 raw_data，并对损坏/空文件容错。
    def _load_gold_pool():
        for p in (os.path.join(BASE, "..", "out", "gold_pool.json"),
                  os.path.join(DATA_DIR, "gold_pool.json")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict) and d.get("stocks"):
                    return d
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
        return {"stocks": {}}

    gp = _load_gold_pool()
    current_gp_stocks = gp.get("stocks", {})
    gp_stocks, survivor_bias_warning, snapshots_used = _load_historical_pool_union(current_gp_stocks)
    log(f"金股池: 当前 {len(current_gp_stocks)} 只 / 回测宇宙 {len(gp_stocks)} 只（历史快照 {snapshots_used} 个）")
    if survivor_bias_warning:
        log("⚠️ 历史金股池快照不足，回测仍含幸存者偏差（会随着每日快照累积逐步消除）")
    
    # 读取当日明细缓存（用于断点续跑）
    # 🔴 2026-09-18 阿狸咪的工程师·P0 修正（禁「旧数据盖新时间戳」）：
    #   上一版曾回退读产品产物 OUT。但迁移首轮线上 OUT 仍是**旧版含明细**的产物，
    #   而本文件主循环对已存在的 key 会 `continue` **整只跳过**（见下方「跳过已处理的」）⇒
    #   结果 = 历史明细的统计 + 全新 update_time —— 前端显示「今日已更新」而数据实为历史，
    #   直接违反首条铁律「数据新鲜真实」（也是主人点名的「旧结果冒充新结果」）。
    #   ⇒ **永不回退读 OUT**。复用条件须**两者同时满足**，缺一即全量重算：
    #     ① calc_time == 今天（跨日缓存一律丢弃）
    #     ② 缓存文件 2 小时内写过（防「同日早盘缓存被晚间档复用」——早盘 K 线尚未收盘）
    existing = {}
    _cache_age = None
    try:
        _cache_age = time.time() - os.path.getmtime(_STOCK_CACHE)
    except OSError:
        pass
    try:
        _cand = json.load(open(_STOCK_CACHE, "r", encoding="utf-8"))
    except Exception:
        _cand = None
    if (isinstance(_cand, dict) and _cand.get("stocks")
            and _cand.get("calc_time") == TODAY
            and _cache_age is not None and _cache_age < 7200):
        existing = _cand
        log(f"复用当日明细缓存: {len(existing.get('stocks', {}))} 只 "
            f"(calc_time={_cand.get('calc_time')}, {_cache_age / 60:.0f} 分钟前)")
    elif isinstance(_cand, dict) and _cand.get("stocks"):
        _age_s = "n/a" if _cache_age is None else ("%.0f 分钟" % (_cache_age / 60))
        log(f"丢弃陈旧明细缓存 (calc_time={_cand.get('calc_time')}, 年龄={_age_s}) ⇒ 本轮全量重算")
    if not existing:
        log("无可复用当日明细 ⇒ 本轮全量重算（数据必然最新）")
    
    # 🔴 2026-09-14 小九审计修复：陈旧口径条目不得进入汇总（口径混用治本·P0）。
    #   原实现 stock_results 直接继承整份旧产物，而下方 summary / opt_summary 均
    #   遍历**全部** stock_results（不区分是否本轮宇宙）⇒ 掉出宇宙的历史条目因
    #   循环永不遍历而永远得不到重算，会以旧入场口径（信号日收盘买入）永久留在
    #   库里污染头条胜率（实测：296 条中 66 条为旧口径残留，trend_up T+5 虚高 0.2pp、
    #   均收虚高 0.20pp）。修法同 ENTRY_CALIBER_VER 精神 —— 按口径版本号裁剪，
    #   非当前版本一律丢弃；仍在宇宙内的会由下方循环重算补回，不丢样本。
    _raw_existing = existing.get("stocks", {})
    _stale_keys = [k for k, v in _raw_existing.items()
                   if isinstance(v, dict) and v.get("signals")
                   and v.get("entry_caliber_ver") != ENTRY_CALIBER_VER]
    if _stale_keys:
        _sk = set(_stale_keys)
        stock_results = {k: v for k, v in _raw_existing.items() if k not in _sk}
        log(f"[裁剪] {len(_stale_keys)} 只陈旧口径条目(entry_caliber_ver != v{ENTRY_CALIBER_VER})"
            f" 已丢弃，不参与汇总；仍在宇宙内的会于下方重算补回")
    else:
        stock_results = _raw_existing
    stale_caliber_dropped = len(_stale_keys)
    
    # market映射
    setcode_map = {"hk": "31", "sh": "1", "sz": "0", "bj": "2"}
    
    _snap_n = 0  # 2026-09-18：明细快照落盘计数器（见下方「每 25 只一写」）
    for key, s in gp_stocks.items():
        code = s.get("code", "")
        mkt = s.get("market", "")
        name = s.get("name", key)
        
        # 跳过已处理的（缓存），但若旧数据缺少新增周期字段 / **口径版本不符** 则重新计算
        if key in stock_results:
            _old = stock_results[key]
            old_sigs = _old.get("signals") or {}
            has_all_periods = bool(old_sigs) and all(
                f"ret_{d}d" in next(iter(old_sigs.values()), {}) and f"raw_ret_{d}d" in next(iter(old_sigs.values()), {})
                for d in HOLD_DAYS
            )
            # 🔴 2026-09-13 小九审计修复：口径版本校验。原判据只看「周期字段齐不齐」，
            #   故改成「次日开盘买入」后旧明细（信号日收盘口径）会被判为合格而整只跳过
            #   ⇒ 主数据口径不统一且无人察觉。现版本不符即整只重算。
            same_caliber = (_old.get("entry_caliber_ver") == ENTRY_CALIBER_VER)
            if has_all_periods and same_caliber:
                log(f"  跳过 {name}({key}) — 已有回测")
                continue
            if has_all_periods and not same_caliber:
                log(f"  重算 {name}({key}) — 入场口径由 v{_old.get('entry_caliber_ver')} 升到 v{ENTRY_CALIBER_VER}")
            else:
                log(f"  重算 {name}({key}) — 补齐新周期")
        
        setcode = setcode_map.get(mkt, "0")
        rows = tdx_kline(code, setcode, count=TDX_BARS)  # 🛡 2026-09-12 扩档：60 → 260
        if not rows or len(rows) < 30:
            stock_results[key] = {"code": code, "name": name, "market": mkt, "error": "数据不足", "signals": {}}
            continue
        
        # 检测信号
        signals = detect_signals(rows)
        n = len(rows)
        
        # 计算每个信号日期的T+1/T+3/T+5/T+10/T+20收益
        stock_signals = {}
        for date, sigs in signals.items():
            # 找到在K线中的索引
            idx = None
            for j in range(n):
                if rows[j]["date"] == date:
                    idx = j
                    break
            # 🔴 2026-09-14 小九审计修复（P0 · 样本窗口被过长持有期吃掉）：
            #   原判据 `idx + max(HOLD_DAYS) >= n` 要求**最长档（现为 T+250）**有完整前瞻
            #   数据才记录该信号日 ⇒ 持有期阶梯扩到 250 档后，最近 250 个交易日的信号被
            #   **整条跳过**（不是算出 0，是压根没算）。实测后果：
            #     ① 产物信号日止于 2025-09-01 —— 近一年样本凭空消失（短档 T+1/T+5 白损失）；
            #     ② 优化策略的 regime 门控序列只覆盖最近约 76 个交易日，与信号窗口
            #        **交集恒为空** ⇒ opt 汇总 0 样本 ⇒ optimized_summary 被静默丢弃 ⇒
            #        下游 export_optimized_strategy.py 直接 exit 1（全站择时真源一起卡死）。
            #   修法：`calc_forward_return()` 对 `target >= n` 已安全返回 None（见其函数内
            #   `if target >= n: return None`），`_accumulate` 亦对 None 逐档跳过 ⇒
            #   记录信号只需保证「入场日 + 最短档」可取，长档自然落 None（未到期不进样本，
            #   与「数据层禁止 0 冒充」同口径）。
            if idx is None or idx + 1 + min(HOLD_DAYS) >= n:
                continue

            returns = {}
            wins = {}
            raw_returns = {}
            exit_types = {}
            board = board_from_code(code)
            _st_cache = {}   # 本信号日的止损/止盈只与入场日有关，12 档共用一份（见 calc_forward_return）
            for d in HOLD_DAYS:
                res = calc_forward_return(rows, idx, d, board=board, st_cache=_st_cache)
                if res is None:
                    returns[f"ret_{d}d"] = None
                    wins[f"win_{d}d"] = None
                    raw_returns[f"raw_ret_{d}d"] = None
                    exit_types[f"exit_type_{d}d"] = None
                else:
                    returns[f"ret_{d}d"] = res["ret"]
                    wins[f"win_{d}d"] = res["ret"] > 0
                    raw_returns[f"raw_ret_{d}d"] = res["raw_ret"]
                    exit_types[f"exit_type_{d}d"] = res["exit_type"]

            stock_signals[date] = {
                "signals": {k: v for k, v in sigs.items() if v and k not in ("ge2_signals", "ge3_signals")},
                "signal_count": sum(1 for k, v in sigs.items() if v and k not in ("ge2_signals", "ge3_signals")),
                "ge2": sigs.get("ge2_signals", False),
                "ge3": sigs.get("ge3_signals", False),
                "entry_price": rows[idx]["close"],
                **returns,
                **wins,
                **raw_returns,
                **exit_types,
            }
        
        stock_results[key] = {
            "code": code,
            "name": name,
            "market": mkt,
            "date_range": f"{rows[0]['date']}~{rows[-1]['date']}",
            "kline_days": n,
            "days_with_signals": len(stock_signals),
            # 🆕 2026-09-13：入场口径版本 —— 断点续跑据此判定是否需要整只重算（见顶部常量）
            "entry_caliber_ver": ENTRY_CALIBER_VER,
            "signals": stock_signals,
        }
        signal_days = len(stock_signals)
        log(f"  {name}({code}): {n}天K线, {signal_days}天含信号")
        
        # 每处理一只存一次（防中断丢失）
        # 🔴 2026-09-14 小九审计修复：此处原用 json.dump(..., indent=2) 直写 OUT。
        #   ① 格式不一致：最终产物由 _dump_json 紧凑写出，中间态却是 indent=2，
        #      一旦流程在收尾前中断，残留产物体积翻倍（126.9 MB vs 72.6 MB）；
        #   ② IO 浪费：快照随 stock_results 累积逐次变大、221 只共写 221 次全量，
        #      是本脚本耗时的大头之一。统一走 _dump_json（紧凑 + 体积护栏）。
        # 2026-09-18：明细快照由「每只一写」改为「每 25 只一写」——原实现 221 只共写 221 次
        #   全量明细（云端 runner 上写随即被 git clean 清掉、无人读取），是本脚本耗时的大头之一。
        #   保留周期性落盘以防长跑中断，IO 次数压到约 1/25。
        _snap_n += 1
        if _snap_n % 25 == 0:
            _dump_json({
                "calc_time": TODAY,
                "method": f"baostock 日K全量回测({TDX_BARS}根·约{round(TDX_BARS / 244)}年) (T+{', T+'.join(map(str, HOLD_DAYS))})",
                "gold_pool_size": len(gp_stocks),
                "stocks": stock_results,
            }, _STOCK_CACHE)   # 2026-09-18：半成品明细写缓存路径，产品产物 OUT 只出汇总
    
    # ── 汇总统计 ──
    log(f"\n{'='*60}")
    log(f"生成汇总统计...")
    
    # 按信号类型汇总（动态支持 HOLD_DAYS 所有周期）
    def _new_summary():
        d = {"total": 0}
        for d_ in HOLD_DAYS:
            d[f"win_{d_}d"] = 0
            d[f"loss_{d_}d"] = 0
            d[f"draw_{d_}d"] = 0
            d[f"total_ret_{d_}d"] = 0.0
            d[f"win_ret_{d_}d"] = 0.0
            d[f"loss_ret_{d_}d"] = 0.0
        return d
    summary = defaultdict(_new_summary)

    def _accumulate(s, sd):
        """把单个信号日 sd 的各周期收益累加到汇总对象 s。
        胜率口径与 backtest_comprehensive 统一：排除平盘，只统计 win/(win+loss)。"""
        s["total"] += 1
        for d_ in HOLD_DAYS:
            r = sd.get(f"ret_{d_}d")
            if r is None:
                continue
            s[f"total_ret_{d_}d"] += r
            if r > 0:
                s[f"win_{d_}d"] += 1
                s[f"win_ret_{d_}d"] += r
            elif r < 0:
                s[f"loss_{d_}d"] += 1
                s[f"loss_ret_{d_}d"] += r
            else:
                s[f"draw_{d_}d"] += 1

    for key, sr in stock_results.items():
        if "signals" not in sr:
            continue
        for date, sd in sr["signals"].items():
            # 按信号类型
            for sig_name, sig_val in sd.get("signals", {}).items():
                _accumulate(summary[sig_name], sd)
            # 组合信号
            if sd.get("ge2"):
                _accumulate(summary["ge2_signals"], sd)
            if sd.get("ge3"):
                _accumulate(summary["ge3_signals"], sd)

    # ── 优化策略汇总（主人令 2026-08-09：①持仓周期 ②≥3共振 ③regime门控）──
    log("计算市场 regime（上证+沪深300）...")
    try:
        market_regime = _merge_market_regime()
        log(f"市场 regime 覆盖 {len(market_regime)} 个交易日")
    except Exception as e:
        log(f"⚠️ 市场 regime 计算失败，跳过优化策略汇总: {e}")
        market_regime = {}

    opt_summary = defaultdict(_new_summary)
    opt_config = OPTIMIZED
    if market_regime:
        for key, sr in stock_results.items():
            if "signals" not in sr:
                continue
            for date, sd in sr["signals"].items():
                full_sigs = dict(sd.get("signals", {}))
                full_sigs["ge2_signals"] = sd.get("ge2", False)
                full_sigs["ge3_signals"] = sd.get("ge3", False)
                if not passes_optimized_filter(full_sigs, market_regime.get(date)):
                    continue
                _accumulate(opt_summary["optimized"], sd)

    # 格式化
    signal_names = {
        "trend_up": "📈 上涨趋势",
        "trend_down": "📉 下跌趋势",
        "chan_buy": "🟣 缠论买点",
        "contrarian": "🔴 逆势红色",
        "breakout_5d": "🚀 5日突破",
        "volume_surge": "💥 放量上涨",
        "divergence": "⚠️ 量价背离",
        "ge2_signals": "🎯 双信号共振",
        "ge3_signals": "🎯 三信号共振",
        "optimized": "🎯 优化策略(≥3共振+regime+5~10d)",
    }
    
    result_data = {
        "calc_time": TODAY,
        # 🛡 2026-09-11 阿狸咪的工程师：原先只写 calc_time（仅日期 %Y-%m-%d），
        #   导致下游 update_v8 用 calc_time 兜底出「仅日期」的 update_time，
        #   而 stage_gate.read_ut() 对「仅日期」宽松补 23:59 → E 批 floor(16:30)
        #   判据失效 + _newest() 跨批顺序判据被伪 23:59 污染。此处补精确时刻治本。
        #   ⚠️ 只加在最终产物；下方「每只一存」的中间快照刻意不加（半成品，
        #      带上时间戳会造出「有 update_time 但无 summary」的假新鲜产物）。
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # 🔴 2026-09-14：口径版本与裁剪审计入产物，供前端/看门狗做「口径混用」守卫
        "entry_caliber_ver": ENTRY_CALIBER_VER,
        "stale_caliber_dropped": stale_caliber_dropped,
        "method": f"baostock 日K全量回测({TDX_BARS}根·约{round(TDX_BARS / 244)}年) (T+{', T+'.join(map(str, HOLD_DAYS))})",
        "gold_pool_size": len(gp_stocks),
        "stocks_analyzed": len([k for k in stock_results if "signals" in stock_results[k]]),
        "survivor_bias_warning": survivor_bias_warning,
        "pool_snapshots_used": snapshots_used,
        "summary": {},
        # 2026-09-18 阿狸咪的工程师·产物体积根治（P0 · 一劳永逸）：
        #   原此处写 "stocks": stock_results（逐只逐日明细），紧凑序列化后仍 72.6 MB
        #   ⇒ 超 GitHub 建 blob 上限，E 批每天 8 次重试全报 HTTP 422
        #   （Sorry, your input was too large to process）⇒ 线上 raw_data/backtest_tdx.json
        #   永久停在 2026-09-14，而脚本与桥接每天 success（「能跑完却推不上去」的隐性停更）。
        #   消费方核查（全部只读汇总，明细零消费者）：
        #     · update_v8.py::_make_lite('BACKTEST_TDX') → update_time/calc_time/method/
        #       gold_pool_size/stocks_analyzed/summary + 口径审计字段
        #     · export_optimized_strategy.py → optimized_summary / summary.ge3_signals
        #     · 前端读 data/BACKTEST_TDX.js（经 _make_lite 裁剪，本就无明细）
        #   明细改由 _STOCK_CACHE 承载（不入仓），本轮内存统计口径零变化。
    }
    
    print(f"\n{'='*60}")
    print(f"  回测结果汇总")
    print(f"{'='*60}")
    hdr = f"{'信号类型':<16} {'样本':>5}"
    for d_ in HOLD_DAYS:
        hdr += f" {'T+'+str(d_)+'胜率':>8} {'T+'+str(d_)+'收益':>9}"
    print(f"\n{hdr}")
    print(f"{'─'*len(hdr)}")

    for sig_key in ["trend_up", "trend_down", "chan_buy", "contrarian", "breakout_5d", "volume_surge", "divergence", "ge2_signals", "ge3_signals"]:
        s = summary[sig_key]
        if s["total"] == 0:
            continue
        label = signal_names.get(sig_key, sig_key)
        row = f"  {label:<14} {s['total']:>5}"
        sd = {"label": label, "total": s["total"]}
        for d_ in HOLD_DAYS:
            decided = s[f"win_{d_}d"] + s[f"loss_{d_}d"]  # 排除平盘，与 comprehensive 统一
            # 🔴 2026-09-13 禁止 0 冒充：该档未到期/全平盘 ⇒ 胜率 None
            wr = round(s[f"win_{d_}d"] / decided * 100, 1) if decided else None
            ar = round(s[f"total_ret_{d_}d"] / s["total"], 2) if s["total"] else 0
            row += f" {wr:>6}%  {ar:>+8}%"
            sd[f"win_{d_}d"] = s[f"win_{d_}d"]
            sd[f"loss_{d_}d"] = s[f"loss_{d_}d"]
            sd[f"draw_{d_}d"] = s[f"draw_{d_}d"]
            sd[f"win_rate_{d_}d"] = wr
            sd[f"avg_return_{d_}d"] = ar
        print(row)
        result_data["summary"][sig_key] = sd
    
    # 输出优化策略汇总
    if opt_summary:
        opt = opt_summary["optimized"]
        if opt["total"] > 0:
            print(f"\n{'='*60}")
            print(f"  优化策略汇总（≥3共振 + 市场regime空仓门控）")
            print(f"  规则：{OPTIMIZED['min_signal_count']}信号共振；仅在阴跌/恐慌段开仓；企稳/反弹段空仓")
            print(f"{'='*60}")
            hdr = f"{'信号类型':<16} {'样本':>5}"
            for d_ in OPTIMIZED["report_periods"]:
                hdr += f" {'T+'+str(d_)+'胜率':>8} {'T+'+str(d_)+'收益':>9}"
            print(hdr)
            print(f"{'─'*len(hdr)}")
            label = signal_names.get("optimized", "optimized")
            row = f"  {label:<14} {opt['total']:>5}"
            sd = {"label": label, "total": opt["total"], "config": OPTIMIZED}
            for d_ in OPTIMIZED["report_periods"]:
                decided = opt[f"win_{d_}d"] + opt[f"loss_{d_}d"]
                wr = round(opt[f"win_{d_}d"] / decided * 100, 1) if decided else None
                ar = round(opt[f"total_ret_{d_}d"] / opt["total"], 2) if opt["total"] else 0
                row += f" {wr:>6}%  {ar:>+8}%"
                sd[f"win_{d_}d"] = opt[f"win_{d_}d"]
                sd[f"loss_{d_}d"] = opt[f"loss_{d_}d"]
                sd[f"draw_{d_}d"] = opt[f"draw_{d_}d"]
                sd[f"win_rate_{d_}d"] = wr
                sd[f"avg_return_{d_}d"] = ar
            print(row)
            result_data["optimized_summary"] = sd
        else:
            # 🔴 2026-09-14 小九审计修复：0 样本时原来**静默不写** optimized_summary，
            #   产物没有该字段 ⇒ 下游 export_optimized_strategy.py 读到 None 直接 exit 1
            #   ⇒ 全站择时真源 OPTIMIZED_STRATEGY.current_regime 一起停止刷新（假死）。
            #   现在大声报出来，并写入审计字段，杜绝「字段凭空消失且无人知晓」。
            log("🔴 [P0] 优化策略 0 样本：regime 门控与信号日期无交集 ⇒ optimized_summary 缺失，"
                "下游 export_optimized_strategy.py 将无法产出（请检查 regime 序列窗口 vs 信号窗口）")
            result_data["optimized_summary_note"] = "empty:no_regime_signal_overlap"
    elif not market_regime:
        log("🔴 [P0] market regime 序列为空 ⇒ 优化策略汇总无法计算（optimized_summary 缺失）")
        result_data["optimized_summary_note"] = "empty:no_market_regime"

    # 审计字段：让「口径/样本异常」在产物里可见，而不是只活在日志里
    result_data["optimized_samples"] = int(opt_summary["optimized"]["total"]) if opt_summary else 0
    result_data["signal_window"] = None
    _all_sig_dates = sorted({d for sr in stock_results.values() for d in (sr.get("signals") or {})})
    if _all_sig_dates:
        result_data["signal_window"] = f"{_all_sig_dates[0]}~{_all_sig_dates[-1]}"

    total_entries = sum(len(sr.get("signals", {})) for sr in stock_results.values())
    print(f"\n{'─'*56}")
    print(f"  总计: {len(gp_stocks)} 只股, {total_entries} 条信号")
    print(f"  输出: {OUT}")
    _dump_json(result_data, OUT)
    print(f"\n  结果: ✓ {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
