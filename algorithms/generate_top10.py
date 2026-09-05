#!/usr/bin/env python3
"""
generate_top10.py — 多维共振评分 + 每日TOP10精选
- 从 gold_pool.json 读取所有金股池股票
- 结合多维度数据（板块资金/龙虎榜/主力/北向/投行/分析师）计算综合共振评分
- 输出 data/top10_daily.json（TOP20 + 评分明细）
"""
import json
import os
import re

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
from datetime import datetime

from fundamental_helper import fq_key_of, quality_points
from stop_target_logic import compute_stop_target_from_closes, board_from_code
import regime_filter

# 🛡 2026-08-29 元模型升级：regime 驱动的行业风格微调
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import v8_meta_model as _meta_model
except Exception as _meta_err:
    print(f"  ⚠️ v8_meta_model 加载失败，跳过 regime 调整: {_meta_err}")
    _meta_model = None

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：历史快照目录从 out/history（gitignore，云端丢）→ raw_data/history（git 跟踪 + api_push 推送持久化）
DATA_DIR = os.path.join(WORKSPACE, "..", "raw_data")
OUTPUT = os.path.join(DATA_DIR, "top10_daily.json")

# ── 归一化分母（2026-08-28 校准，勿改回 250）─────────────────────────────────
# 原值 250 是【理论上限】累加值，但实测 46 天 756 个信号的 raw_total 分布是
#   P50=69  P75=78  P90=88  P95=93  P99=100  MAX=106
# 用 250 作分母 → 历史最高分仅 42.4 分，≥80 分信号【数学上不可达】
# （近 15 日实测 ≥80 与 70~80 分信号均 0 个，回测阈值对实盘完全失效）。
# 本次同时修复了恒为 0 的 fund/inst/sector 三维度（+0~25 raw），
# 校准后分母取 130：P95≈110、MAX≈130，80 分线重新代表头部约 5% 的信号。
# ⚠️ 改此值必须同步重跑 renormalize_top10_history.py，否则历史口径断裂。
NORM_DIVISOR = 130
NORM_VERSION = 130          # 写入快照，供迁移函数识别是否已按本口径归一


# ─────────────────────────────────────────────────────────────────────────────
# 🔴 P2 信号边缘权重（2026-09-05）：全部来自 walk-forward 回测 edge
# 来源：raw_data/backtest_expectancy.json · by_factor · T+10 edge（全站默认持有 10 日口径）
#   sig_jinzuan +8.11  → 强正，重赏
#   sig_chan    +3.68  → 温和正（与金钻共振时组合 edge +8.37，全样本最优组合）
#   sig_trend   -7.54  → 反向，惩罚（旧代码 +25 赏，与回测相反）
#   sig_jigou   -10.36 → 强反向，重罚（旧代码 +25 赏，与回测相反）
# 运行期尝试读取该 JSON 覆盖默认值，回测重跑后权重自动刷新；读取失败回退硬编码。
# P1 硬化：signal_confidence 按样本量 + T+5/T+10 符号一致性做收缩，防过拟合（薄样本/矛盾证据→0）。
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_EDGE_DEFAULT = {
    "jinzuan": 8.11,
    "chan":    3.68,
    "trend":  -7.54,
    "jigou":  -10.36,
}
SIGNAL_EDGE_TO_SCORE = 2.5   # 每 1% edge ≈ 2.5 分
SIGNAL_SCORE_CAP, SIGNAL_SCORE_FLOOR = 30, -30

def _signal_score_from_edge(edge):
    return max(SIGNAL_SCORE_FLOOR, min(SIGNAL_SCORE_CAP, round(edge * SIGNAL_EDGE_TO_SCORE)))

def load_json(path, default=None):
    """安全加载JSON"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


# ─────────────────────────────────────────────────────────────────────────────
# 🔴 P2 信号边缘权重（运行期加载）：必须在 load_json 定义之后执行
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_EDGE = dict(SIGNAL_EDGE_DEFAULT)
SIGNAL_N, SIGNAL_CONSISTENT = {}, {}
try:
    _bt = load_json(os.path.join(DATA_DIR, "backtest_expectancy.json"), {})
    for _k, _v in (_bt.get("by_factor") or {}).items():
        _name = {"sig_jinzuan": "jinzuan", "sig_chan": "chan",
                 "sig_trend": "trend", "sig_jigou": "jigou"}.get(_k)
        if not _name:
            continue
        SIGNAL_EDGE[_name] = _v.get("edge10", SIGNAL_EDGE[_name])
        SIGNAL_N[_name] = _v.get("n_on10", 0)
        SIGNAL_CONSISTENT[_name] = (_v.get("edge5", 0) > 0) == (_v.get("edge10", 0) > 0)
except Exception as _e:
    print(f"  ⚠️ 回测边缘权重加载失败，用硬编码默认: {_e}")
SIGNAL_SCORE = {k: _signal_score_from_edge(v) for k, v in SIGNAL_EDGE.items()}

def signal_confidence(name):
    """P1 证据置信度（0~1）：样本少或符号矛盾→收缩到 0，避免薄证据主导排名"""
    n = SIGNAL_N.get(name, 0)
    if n <= 0:
        return 1.0
    conf = min(1.0, n / 120.0)
    if not SIGNAL_CONSISTENT.get(name, True):
        conf *= 0.5
    return conf

def signal_edge_score(name, present):
    if not present:
        return 0
    return int(round(SIGNAL_SCORE.get(name, 0) * signal_confidence(name)))

# P2 回测反哺：用 walk-forward by_signal T+10 edge 直接修正排名（替代原 cockpit T+3 胜率，已下线恒50）
BT_BY_SIGNAL = {}
try:
    _bt2 = load_json(os.path.join(DATA_DIR, "backtest_expectancy.json"), {})
    BT_BY_SIGNAL = _bt2.get("by_signal", {})
except Exception:
    BT_BY_SIGNAL = {}

def bt_edge10_for(chan, jinzuan, jigou, trend):
    """给定四信号布尔 (chan, jinzuan, jigou, trend) → walk-forward T+10 edge(%)；
    组合缺失回退 0（中性）。key 格式与 backtest_expectancy.json by_signal 一致：'c,j,t,tr'"""
    key = f"{int(chan)},{int(jinzuan)},{int(jigou)},{int(trend)}"
    rec = BT_BY_SIGNAL.get(key)
    return float((rec or {}).get("edge10", 0) or 0)


# ─────────────────────────────────────────────────────────────────────────────
# 板块资金噪音过滤（2026-08-29 新增）
# sector_fund_flow 的板块表里混有大量【非赛道标签】：业绩类（2026中报预增）、
# 指数/属性类（AH股/权重股/行业龙头/MSCI中国）、交易类（融资融券/沪股通）。
# 它们不是赛道，其资金流不代表赛道景气度；且数值巨大（实测「2026中报预增」
# 达 -104 亿），会淹没真实的赛道信号（全市场最大净流入仅 32.94 亿）。
# ─────────────────────────────────────────────────────────────────────────────
_NOISE_SECTOR_RE = re.compile(
    # 业绩 / 指数 / 交易属性类
    r"预增|预减|扭亏|预盈|业绩|MSCI|标普|标准普尔|富时|融资|融券|沪股通|深股通|转融|"
    r"破净|破发|破增发|高价股|低价股|次新股|送转|增持|回购|减持|AH股|权重股|"
    r"行业龙头|央国企|国企改革|成分股|指数|ST股|创业成份|深成|上证|中证|QFII|社保|"
    r"基金重仓|机构重仓|昨日|近期|连续|多板|专精特新|"
    # 风格 / 属性类（2026-08-29 实测 16 个，其中「题材股 -129.21 亿」为全市场第二大流出，
    # 不过滤会把市场系统性风格切换误当成个股赛道资金动向）
    r"题材股|趋势股|反转股|周期股|成长股|价值股|蓝筹|白马|小盘|中盘|大盘|微盘|"
    r"创投|并购重组|股权转让|壳资源|重组|摘帽|独角兽|涨价")


def is_noise_sector(name):
    """业绩/指数/交易属性类标签不是赛道，其资金流不代表赛道动向"""
    return bool(_NOISE_SECTOR_RE.search(name or ""))


def freshness_warn(name, obj, max_age_days=1.0):
    """数据源陈旧度告警（2026-08-28 新增）

    主人的核心痛点：「算法链或股池断更了我都不知道」。此前三个评分维度
    因读不到数据源而恒为 0，却毫无提示。现对每个关键数据源检查 update_time，
    超过阈值就打印告警 —— 只告警不阻断，保证断更【可见】。
    """
    if not isinstance(obj, dict) or not obj:
        print(f"  ⚠️ {name}: 数据为空，相关评分维度将为 0")
        return False
    ut = obj.get("update_time") or obj.get("fetch_time") or obj.get("date")
    if not ut:
        print(f"  ⚠️ {name}: 无 update_time 字段，无法判断新鲜度")
        return True
    s = str(ut).replace("T", " ").strip()
    dt = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:len(fmt) + 3], fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return True
    age = (datetime.now() - dt).total_seconds() / 86400.0
    if age > max_age_days:
        print(f"  ⚠️ {name} 陈旧: update_time={ut}（{age:.1f} 天前）→ 相关维度可能失真")
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 🔴 2026-08-28 修复：真实 20 日涨幅
# 实测 top10 近 10 日 180/180 条信号的 pct_chg_20d 全为 0，且 gold_pool 中
# 0/65 只股票带该字段 —— 该因子此前完全失效，并造成两处隐性错误：
#   1) enhance 的涨幅分支永远走 else（0<20），涨跌幅调节形同虚设
#   2) form 的 `pct20 < 35` 恒为 True → 每只股票白送 2 分，形态A判断失真
# 现改为从 raw_data/kline_cache 的真实日K计算。
# 2026-08-29 再修复：kline_cache 只是 gen_strong_breakout 的副产物（只覆盖当日涨幅≥3%的
# 强势突破候选），而金股池 65 只股票常常不在其中 → pct_chg_20d 再次 100% 缺失。
# 现增加「缓存miss则实时拉取」兜底，让 generate_top10 对金股池自洽。
# ─────────────────────────────────────────────────────────────────────────────
_KLINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "raw_data", "kline_cache")
_KLINE_CACHE = {}


def _num_code(code):
    return re.sub(r"\D", "", str(code or ""))


def _market_of(code):
    """从 sh_600362 / sz_300319 等格式推断市场"""
    n = _num_code(code)
    if len(n) != 6:
        return None
    if n.startswith("6") or n.startswith("9") or n.startswith("11") or n.startswith("13"):
        return "sh"
    if n.startswith("0") or n.startswith("3") or n.startswith("20"):
        return "sz"
    if n.startswith("8") or n.startswith("4") or n.startswith("43") or n.startswith("92"):
        return "bj"
    return "sh"


def _df_to_records(df):
    """把 DataFrame 转成 kline_cache 统一 records 列表，并清理 NaN"""
    if df is None or len(df) < 2:
        return []
    records = []
    for _, r in df.iterrows():
        try:
            close = float(r["close"])
            if not (close > 0):
                continue
            records.append({
                "date": str(r["date"])[:10],
                "open": float(r["open"]),
                "close": close,
                "high": float(r["high"]),
                "low": float(r["low"]),
                "volume": float(r["volume"]),
            })
        except (TypeError, ValueError):
            continue
    return records


def _fetch_kline_fallback(code):
    """缓存 miss 时尝试从腾讯 GTimg / akshare 拉取日K并写入缓存。失败返回 []"""
    n = _num_code(code)
    mkt = _market_of(code)
    if len(n) != 6 or not mkt:
        return []
    os.makedirs(_KLINE_DIR, exist_ok=True)
    cp = os.path.join(_KLINE_DIR, f"{n}.json")
    try:
        from data_source_gtimg import fetch_a_daily_gtimg
        df = None
        for attempt in range(2):
            df = fetch_a_daily_gtimg(n, market=mkt, bars=250)
            if df is not None and len(df) >= 60:
                break
            alt = "sz" if mkt == "sh" else "sh"
            df = fetch_a_daily_gtimg(n, market=alt, bars=250)
            if df is not None and len(df) >= 60:
                break
        if df is None or len(df) < 60:
            try:
                import akshare as ak
                end = datetime.now()
                start = end - datetime.timedelta(days=600)
                symbol = f"sh{n}" if mkt == "sh" else f"sz{n}"
                df = ak.stock_zh_a_daily(
                    symbol=symbol,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                )
                if df is None or len(df) < 60:
                    return []
                records = []
                for _, r in df.iterrows():
                    records.append({
                        "date": str(r["date"])[:10],
                        "open": float(r["open"]),
                        "close": float(r["close"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "volume": float(r["volume"]),
                    })
                if len(records) < 60:
                    return []
                with open(cp, "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False)
                return records
            except Exception:
                return []
        records = _df_to_records(df)
        if len(records) >= 60:
            with open(cp, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False)
        return records
    except Exception:
        return []


def _load_kline(code):
    """读取个股日K缓存 → [(date, close), ...] 升序；无数据返回 []"""
    if code in _KLINE_CACHE:
        return _KLINE_CACHE[code]
    rows = []
    n = _num_code(code)
    try:
        with open(os.path.join(_KLINE_DIR, f"{n}.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for r in data:
                try:
                    close = r.get("close")
                    if r.get("date") and close is not None and close == close and close > 0:
                        rows.append((r["date"], float(close)))
                except (TypeError, ValueError):
                    continue
            rows.sort(key=lambda x: x[0])
    except Exception:
        rows = []
    # 缓存 miss 或数据不足：实时拉取
    if len(rows) < 21:
        records = _fetch_kline_fallback(code)
        rows = [(r["date"], r["close"]) for r in records if r.get("date") and r.get("close") > 0]
        rows.sort(key=lambda x: x[0])
    _KLINE_CACHE[code] = rows
    return rows


def pct_chg_20d_of(code, asof_date=None):
    """真实 20 交易日涨幅(%)。数据不足返回 None（注意：None ≠ 0，0 是有效值）"""
    rows = _load_kline(code)
    if len(rows) < 2:
        return None
    if asof_date:
        rows = [r for r in rows if r[0] <= asof_date]
        if len(rows) < 2:
            return None
    cur = rows[-1][1]
    base = rows[max(0, len(rows) - 1 - 20)][1]
    if base <= 0:
        return None
    return (cur - base) / base * 100


def _load_kline_full(code):
    """读取个股完整日K（含开高低收量），用于 5日突破 等需要 high 的因子"""
    n = _num_code(code)
    cp = os.path.join(_KLINE_DIR, f"{n}.json")
    records = []
    try:
        with open(cp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            records = [r for r in data if r.get("date") and r.get("close") > 0 and r.get("high") > 0]
    except Exception:
        records = []
    if len(records) < 6:
        records = _fetch_kline_fallback(code)
    records.sort(key=lambda r: r["date"])
    return records


def breakout_5d_of(code, asof_date=None):
    """今日是否触发 5日突破：收盘>昨收 且 今日高价≥近5日高价最高。
    与 backtest_tdx.py 口径对齐（唯一 T+10 正期望信号）。  # 2026-09-03 gen_cockpit_advice.py 已下线"""
    recs = _load_kline_full(code)
    if len(recs) < 6:
        return False
    if asof_date:
        recs = [r for r in recs if r["date"] <= asof_date]
        if len(recs) < 6:
            return False
    today = recs[-1]
    prev = recs[-2]
    high_5d = max(r["high"] for r in recs[-5:])
    return today["high"] >= high_5d and today["close"] > prev["close"]


def _kline_volume_metrics(code, asof_date=None):
    """返回个股量能与位置指标：20日均量、量比、30日/5日分位、今日涨跌幅等；
    用于 P3 研究驱动因子（量能突破、温水煮青蛙、超跌反弹、上涨中继）。"""
    recs = _load_kline_full(code)
    if len(recs) < 30:
        return None
    if asof_date:
        recs = [r for r in recs if r["date"] <= asof_date]
        if len(recs) < 30:
            return None
    today = recs[-1]
    prev_20 = recs[-21:-1]
    vol_20 = sum(r["volume"] for r in prev_20) / len(prev_20)
    high_30 = max(r["high"] for r in recs[-30:])
    low_30 = min(r["low"] for r in recs[-30:])
    high_5 = max(r["high"] for r in recs[-5:])
    low_5 = min(r["low"] for r in recs[-5:])
    open_t = today["open"]
    close_t = today["close"]
    return {
        "today": today,
        "vol_ratio": (today["volume"] / vol_20) if vol_20 > 0 else 1.0,
        "vol_20": vol_20,
        "range_pos_30": ((close_t - low_30) / (high_30 - low_30)) if high_30 > low_30 else 0.5,
        "range_pos_5": ((close_t - low_5) / (high_5 - low_5)) if high_5 > low_5 else 0.5,
        "pct_today": ((close_t - open_t) / open_t * 100) if open_t > 0 else 0.0,
        "recs": recs,
    }


def _volume_surge_score(vm):
    """量能突破：A股实证中换手率/量能是 t 值最高的有效因子。
    放量确认价格行为时加分，缩量拉升不额外奖励。"""
    if not vm:
        return 0
    vr = vm["vol_ratio"]
    if vr >= 2.5:
        return 3
    if vr >= 1.8:
        return 2
    if vr >= 1.3:
        return 1
    return 0


def _frog_in_pan_score(vm):
    """温水煮青蛙（frog in the pan）：连续小阳线、低波动，市场反应不足。
    参考截图#11动量因子本意。"""
    if not vm:
        return 0
    streak = 0
    for r in reversed(vm["recs"]):
        open_p = r["open"]
        if open_p <= 0:
            break
        pct = (r["close"] - open_p) / open_p * 100
        range_pct = (r["high"] - r["low"]) / open_p * 100
        if 0.2 <= pct <= 3.0 and range_pct < 5.0:
            streak += 1
        else:
            break
    if streak >= 5:
        return 4
    if streak >= 3:
        return 2
    return 0


def _oversold_bounce_score(vm, pct20):
    """超跌反弹：20日跌幅>10%，今日收阳，且量能放大（资金开始承接）。"""
    if not vm or pct20 is None or pct20 > -10:
        return 0
    if vm["pct_today"] <= 0:
        return 0
    if vm["vol_ratio"] < 1.2:
        return 0
    return 3


def _range_continuation_score(vm):
    """上涨中继：长周期仍处高位（30日分位>70%），短周期已回落至低位（5日分位<30%）。
    对应截图#11长周期不破70分位、短周期跌破30分位的上涨中继逻辑。"""
    if not vm:
        return 0
    if vm["range_pos_30"] >= 0.7 and vm["range_pos_5"] <= 0.3:
        return 3
    return 0


def _migrate_old_top10_scores(hist_dir):
    """将历史 top10_daily_YYYYMMDD.json 中旧 raw 评分（>100）统一归一化到 0~100，
    保证回测与阈值口径一致。

    2026-08-28 升级：分母 250 → NORM_DIVISOR(130)，并写入 norm_version 标记。
    ⚠️ 若无版本标记，同一文件会被不同口径反复归一化 —— 那正是「回测结论对
       实盘失效」的根因（7/17–7/30 比值 1.00，8/01 起 0.40）。
    """
    if not os.path.isdir(hist_dir):
        return
    changed = 0
    for fn in os.listdir(hist_dir):
        if not fn.startswith("top10_daily_") or not fn.endswith(".json"):
            continue
        path = os.path.join(hist_dir, fn)
        try:
            data = load_json(path, {})
            if not isinstance(data, dict):
                continue
            if data.get("norm_version") == NORM_VERSION:
                continue                      # 已是本口径，跳过
            need_norm = data.get("max_score", 0) > 100   # >100 → 仍是旧 raw 分
            top10 = data.get("top10", [])
            count_80 = 0
            max_s = 0
            for item in top10:
                if need_norm:
                    raw = item.get("total_score", 0)
                    item["total_score"] = round(min(100, max(0, raw / NORM_DIVISOR * 100)), 1)
                s = item.get("total_score", 0) or 0
                max_s = max(max_s, s)
                if s >= 80:
                    count_80 += 1
            data["max_score"] = max_s
            data["count_80plus"] = count_80
            data["norm_version"] = NORM_VERSION
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            changed += 1
        except Exception:
            pass
    if changed:
        print(f"  🔄 历史快照已统一到 NORM_DIVISOR={NORM_DIVISOR} 口径：{changed} 个文件")


def main():
    print("=" * 60)
    print(f"  多维共振评分 · 每日TOP20精选  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 🛡 2026-08-20 主人令·一劳永逸：TOP10 精选属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='generate_top10')

    # ── 1. 加载金股池 ──
    # 🔴 2026-08-11 修复顺序缺陷：本轮 fresh gold_pool 由 scanner.py 直产到 out/，
    #    raw_data/gold_pool.json 要等 stage_to_raw（run_algorithms step2）才刷新；
    #    本脚本在 step1 运行，直接读 raw_data 会拿到上一轮的旧/空文件 → "金股池为空"跳过。
    #    故优先读 out/gold_pool.json（本轮），回退 raw_data。
    _out_gp = os.path.join(WORKSPACE, "..", "out", "gold_pool.json")
    gold_pool = load_json(_out_gp, {})
    if not (isinstance(gold_pool, dict) and gold_pool.get("stocks")):
        gold_pool = load_json(os.path.join(DATA_DIR, "gold_pool.json"), {"stocks": {}})
    gp_stocks = gold_pool.get("stocks", {})
    if not gp_stocks:
        print("  ⚠️  金股池为空，跳过")
        print(f"\n  结果: 跳过 (金股池为空)")
        return
    print(f"  📊 金股池: {len(gp_stocks)} 只")

    # ── 2. 加载辅助数据 ──
    # 🔴 2026-08-28 修复：以下 6 处此前读的是【不存在的文件/键】，导致
    #    score_fund / score_inst / score_sector 三个维度恒为 0（实测近 7 日
    #    140/140 条信号这三项全为 0），评分体系丢掉约 25 分 raw 的区分度。
    #    真实文件名以 stage_to_raw.py 的 V6_TO_V8 映射表与 raw_data 实际产物为准。
    #    ┌ 旧（读不到）              → 新（实际存在）
    #    ├ main_stock.json          → capital_flow_data.json  (.top_inflow/.top_outflow，单位【亿元】)
    #    ├ lhb_result.json          → lhb_data.json           (.stocks)   ← V6_TO_V8 已映射
    #    ├ mahoro_signals.json      → mahoro.json             (.gold_pool_matches) ← V6_TO_V8 已映射
    #    ├ 52w_high.json            → w52_high.json           (.top_gainers)
    #    ├ analyst_ratings[upgrades]→ analyst_ratings (.hot_stocks/.new_coverage)  ← upgrades 恒为空
    #    └ industry_map.json        → candidate.json          (.stocks[].industry/.concepts)
    sector_flow = load_json(os.path.join(DATA_DIR, "sector_fund_flow.json"), {})
    lhb_data = load_json(os.path.join(DATA_DIR, "lhb_data.json"), {})
    capital_flow = load_json(os.path.join(DATA_DIR, "capital_flow_data.json"), {})
    north_fund = load_json(os.path.join(DATA_DIR, "north_fund.json"), {})
    # 2026-08-28 主人令：mahoro 数据源不再跟踪，相关评分项已移除
    w52_high = load_json(os.path.join(DATA_DIR, "w52_high.json"), {})
    # 2026-07-21: 基本面质量分(A=+40, B=+5, D=-10, C=0)
    fundamental = load_json(os.path.join(DATA_DIR, "fundamental_quality.json"), {})
    fundamental_stocks = fundamental.get("stocks", {}) if isinstance(fundamental, dict) else {}
    analyst = load_json(os.path.join(DATA_DIR, "analyst_ratings.json"), {})
    # 行业/概念映射：与 gold_pool 同构的时序坑 —— 本轮产物在 out/candidate_pool.json，
    # 要等 stage_to_raw 才搬运到 raw_data。直接读 raw_data 可能拿到上一轮（实测曾陈旧 2 天）。
    _out_cand = os.path.join(WORKSPACE, "..", "out", "candidate_pool.json")
    industry_map = load_json(_out_cand, {})
    if not (isinstance(industry_map, dict) and industry_map.get("stocks")):
        industry_map = load_json(os.path.join(DATA_DIR, "candidate.json"), {})

    # ── 2.2 数据源新鲜度巡检（断更可见化，不阻断）──
    print("  ── 数据源新鲜度 ──")
    freshness_warn("板块资金流", sector_flow)
    freshness_warn("龙虎榜", lhb_data, max_age_days=2.0)
    freshness_warn("主力资金", capital_flow)
    freshness_warn("52周新高", w52_high)
    freshness_warn("分析师评级", analyst)
    freshness_warn("基本面质量", fundamental)
    freshness_warn("行业概念映射", industry_map, max_age_days=2.0)
    print("  ────────────────")

    # ── 2.5 回测反哺数据源（P2）：walk-forward by_signal T+10 edge ──
    # 已在模块级 BT_BY_SIGNAL / bt_edge10_for() 加载（来自 raw_data/backtest_expectancy.json）。
    # 原 cockpit_backtest.json 已下线，旧的 T+3 胜率反哺恒为 50，已整体替换。

    # ── 2.6 P0-1 择时门控（2026-08-30）：与前端 v8MarketGate() 对齐 ──
    # 唯一权威 = regime_filter（grind/panic 才开仓）。非开仓状态整体降权，
    # 避免 stabilize/rebound 阶段把负期望信号推进 TOP10。
    # ic_gate / strategy_regime_gate 仍读取并打印，但不再让 T+3 低胜率
    # 把默认 T+10 持有策略打到无法出信号（给 ic_weight / regime_weight 设 0.85  floor）。
    _ic_gate = load_json(os.path.join(DATA_DIR, "ic_gate.json"), {})
    _regime_gate = load_json(os.path.join(DATA_DIR, "strategy_regime_gate.json"), {})
    ic_weight = float((_ic_gate.get("factors") or {}).get("ge3", {}).get("ic_weight") or 1.0)
    ic_action = (_ic_gate.get("overall_action") or "ok")
    _strat = (_regime_gate.get("strategies") or {}).get("ge3", {})
    regime_weight = float(_strat.get("weight") or 1.0)
    regime_action = (_regime_gate.get("overall_action") or "ok")
    try:
        _regime_info = regime_filter.get_current_regime(force=False)
        current_regime = (_regime_info or {}).get("regime", "stabilize")
    except Exception as _e:
        current_regime = "stabilize"
    regime_open = regime_filter.is_open_regime(current_regime)
    open_multiplier = 1.0 if regime_open else 0.65   # 非开仓状态显著降权
    ic_weight_adj = max(0.85, min(1.0, ic_weight))
    regime_weight_adj = max(0.85, min(1.0, regime_weight))
    gate_multiplier = max(0.3, min(1.05, open_multiplier * ic_weight_adj * regime_weight_adj))
    print(f"  🚦 择时门控: regime={current_regime}({'开仓' if regime_open else '观望'}) "
          f"× ic={ic_weight:.2f}→{ic_weight_adj:.2f}({ic_action}) "
          f"× regime_w={regime_weight:.2f}→{regime_weight_adj:.2f}({regime_action}) "
          f"→ 乘子={gate_multiplier:.3f}")

    # P2：T+3 胜率反哺已替换为模块级 bt_edge10_for()（walk-forward T+10 edge），见下方 score_backtest。

    # ── 3. 构建辅助查询映射 ──
    # 板块资金：板块名→净流入(亿)
    # 🔴 2026-08-29 修复三处（主人问「板块的资金验证是否有错」后实测确认）：
    #   ① 原只读 sectors_in（净流入榜，200 个全为正数）→ sectors_out（净流出榜，
    #      178 个全为负）从未被读取，导致下方 `best_sector_flow < -5` 的【扣分分支
    #      永远不可能触发】——板块失血从来不扣分。
    #   ② 改用 top_list（378 个 = 流入 200 + 流出 178，正负齐全）；实测覆盖率
    #      从 28.8% 提升到 56.5%。
    #   ③ 过滤非赛道噪音标签（业绩/指数/属性类），详见 is_noise_sector()。
    _src = sector_flow.get("top_list")
    if not _src:
        _src = (sector_flow.get("sectors_in") or []) + (sector_flow.get("sectors_out") or [])
    sector_flow_in = {}
    for s in _src:
        nm = s.get("name", "")
        if nm and not is_noise_sector(nm):
            sector_flow_in[nm] = s.get("net", 0)

    # 龙虎榜：code→inst_net_万
    lhb_map = {}
    for s in lhb_data.get("stocks", []):
        code = s.get("code", "")
        if code:
            lhb_map[code] = {
                "inst_net": s.get("inst_net_万", 0),
                "category": s.get("category", ""),
            }

    # 主力：code→净流入【亿元】（capital_flow_data 口径与旧 main_stock 的万元不同，阈值已换算）
    main_map = {}
    for s in capital_flow.get("top_inflow", []):
        code = s.get("code", "")
        if code:
            main_map[code] = s.get("net", 0)
    for s in capital_flow.get("top_outflow", []):
        code = s.get("code", "")
        if code and code not in main_map:
            main_map[code] = s.get("net", 0)

    # 52周新高：优先按 code 精确匹配，回退 name（旧代码只读 name，易误命中同名股）
    w52_codes, w52_names = set(), set()
    for s in w52_high.get("top_gainers", []):
        if s.get("code"):
            w52_codes.add(s.get("code", ""))
        if s.get("name"):
            w52_names.add(s.get("name", ""))

    # 分析师关注：hot_stocks（TOP分析师推荐）+ new_coverage（新覆盖）
    # 旧代码只读 upgrades，而该键实测恒为空 list，导致此项永久加分失败
    analyst_codes, analyst_names = set(), set()
    for key in ("hot_stocks", "new_coverage", "upgrades"):
        for a in analyst.get(key, []) or []:
            if a.get("code"):
                analyst_codes.add(a.get("code", ""))
            if a.get("name"):
                analyst_names.add(a.get("name", ""))

    # 行业/概念映射：code→[板块名]
    # 数据源由不存在的 industry_map.json 换成 candidate.json（含 industry + concepts）
    ind_map = {}
    im_stocks = industry_map.get("stocks", {})
    if isinstance(im_stocks, dict):
        for code_key, info in im_stocks.items():
            if not isinstance(info, dict):
                continue
            clean = (info.get("code") or code_key.replace("sh_", "").replace("sz_", "")
                     .replace("hk_", "").replace("bj_", ""))
            tags = []
            if info.get("industry"):
                tags.append(info["industry"])
            for c in (info.get("concepts") or []):
                if c:
                    tags.append(c)
            if tags:
                ind_map[clean] = tags

    # ── 4. 计算多维共振评分 ──
    scored = []
    for key, s in gp_stocks.items():
        hist = s.get("history", [])
        latest = hist[-1] if hist else {}
        if isinstance(latest, dict) and "latest" in latest:
            nested = latest["latest"]
            # 嵌套latest必须有close/pct_chg才使用，否则保留外层完整数据
            if isinstance(nested, dict) and nested.get("close") and nested.get("pct_chg") is not None:
                latest = nested
            # 否则保持latest=hist[-1]（外层已有close/pct_chg等字段）

        name = s.get("name", "")
        code = s.get("code", "")
        raw_code = code or key.replace("sz_", "").replace("sh_", "").replace("hk_", "")

        # 基础信号（P2 重写 2026-09-05）：权重 = walk-forward T+10 edge × 置信度收缩
        #   金钻 +20 / 缠论 +9 / 机构变红 −26 / 上涨趋势 −19
        #   旧代码三信号各 +25，把两个反向因子（机构变红/上涨趋势）当正向用，与回测相反。
        has_chan = bool(latest.get("缠论买_日K"))
        has_qizhang = bool(latest.get("金钻_起涨"))
        has_huangzhu = bool(latest.get("金钻_黄柱"))
        has_jigou = bool(latest.get("四量图_机构变红"))
        has_trend = bool(latest.get("上涨趋势"))
        sig_jinzuan = has_qizhang or has_huangzhu
        sig_count = sum([sig_jinzuan, has_chan, has_jigou, has_trend])

        base = (signal_edge_score("jinzuan", sig_jinzuan)
                + signal_edge_score("chan", has_chan)
                + signal_edge_score("jigou", has_jigou)
                + signal_edge_score("trend", has_trend))

        # 增强因子 (-10 ~ +13)
        enhance = 0
        pct20 = latest.get("pct_chg_20d") or s.get("pct_chg_20d") or 0
        if not pct20:
            # 字段缺失（实测 100% 缺失）→ 用真实日K补齐
            _v = pct_chg_20d_of(raw_code)
            if _v is not None:
                pct20 = _v
        # 🔴 方向修正（2026-08-28）：可信回测显示 pct_chg_20d 与未来收益
        #    【负相关】——T5 IC 7月 -0.109 / 8月 -0.228，T10 -0.293、T20 -0.392，
        #    两个月同号率 100%。原代码却给 20~50% 涨幅【加分】，方向相反。
        #    现改为：涨幅越大越扣分（A股短期反转效应），温和小涨给正分。
        if pct20 >= 50:
            enhance -= 6
        elif pct20 >= 35:
            enhance -= 3          # 原 +5 → -3
        elif pct20 >= 20:
            enhance -= 1          # 原 +3 → -1
        elif 0 < pct20 < 10:
            enhance += 2          # 新增：温和上涨（未过热）给正分

        rsi = latest.get("rsi_14") or s.get("rsi_14") or 50
        if rsi > 70:
            enhance -= 5
        elif rsi < 30:
            enhance += 3

        # 连续共振天数（P2：仅统计正向因子 金钻/缠论 的连续出现；反向因子不计入）
        consecutive = 0
        sorted_hist = sorted(hist, key=lambda h: h.get("date", ""), reverse=True)
        for h in sorted_hist:
            h_sig = sum([
                bool(h.get("金钻_起涨") or h.get("金钻_黄柱")),
                bool(h.get("缠论买_日K")),
            ])
            if h_sig >= 1:
                consecutive += 1
            else:
                break
        enhance += min(consecutive * 2, 8)

        # 5日突破（唯一 T+10 正期望信号，2026-08-30 P0 加权）
        breakout_5d = breakout_5d_of(raw_code)
        if breakout_5d:
            enhance += 5

        # ── P3 研究驱动量能/行为因子（2026-09-05）──
        # 截图研究结论：A股换手率/量能 t 值最高；动量应捕捉「温水煮青蛙」式市场反应不足；
        # 上涨中继 = 长周期强势 + 短周期回落。四个因子均只从 K 线（开高低收量）计算，
        # 与现有信号正交，作为 enhance 增量，单票上限 +13。
        vm = _kline_volume_metrics(raw_code)
        research_score = 0
        research_detail = []
        rs = _volume_surge_score(vm)
        if rs:
            research_score += rs
            research_detail.append(f"量能突破x{vm['vol_ratio']:.1f}+{rs}")
        rs = _frog_in_pan_score(vm)
        if rs:
            research_score += rs
            research_detail.append(f"温水煮青蛙+{rs}")
        rs = _oversold_bounce_score(vm, pct20)
        if rs:
            research_score += rs
            research_detail.append(f"超跌反弹+{rs}")
        rs = _range_continuation_score(vm)
        if rs:
            research_score += rs
            research_detail.append(f"上涨中继+{rs}")
        enhance += research_score

        # ── 技术形态分 (2026-07-26): 把驾驶舱 A 档条件合并进主站打分 ──
        # 条件：上涨趋势 + 机构变红 + RSI<68 + 20日涨幅<35% + EMA>=5 + 非涨停
        ema_up = s.get("ema_up") or latest.get("ema_up") or 0
        limit_up = bool(s.get("当日涨停") or latest.get("当日涨停") or False)
        form_score = 0
        form_detail = []
        if ema_up >= 5:
            form_score += 5
            form_detail.append(f"EMA结构={ema_up}")
        elif ema_up >= 3:
            form_score += 3
            form_detail.append(f"EMA结构={ema_up}")
        elif ema_up >= 1:
            form_score += 1
            form_detail.append(f"EMA结构={ema_up}")
        if not limit_up:
            form_score += 2
            form_detail.append("非涨停")
        if pct20 < 35:
            form_score += 2
        if rsi < 68:
            form_score += 2
        if sig_jinzuan and has_chan and ema_up >= 5 and rsi < 68 and pct20 < 35 and not limit_up:
            form_score += 5
            form_detail.append("形态A(金钻+缠论)")
        # 涨停过热直接惩罚（与形态A条件对齐）
        if limit_up:
            form_score -= 5

        # 资金动力 (0 ~ +10)
        fund = 0
        fund_detail = []

        # 主力（capital_flow_data 单位为【亿元】，非旧 main_stock 的万元）
        main_net = main_map.get(raw_code, 0)
        if main_net >= 1:
            fund += 5
            fund_detail.append(f"主力净流入+{main_net:.2f}亿")
        elif main_net > 0:
            fund += 2
            fund_detail.append(f"主力净流入+{main_net:.2f}亿")
        elif main_net <= -1:
            fund -= 2
            fund_detail.append(f"主力净流出{main_net:.2f}亿")

        # 龙虎榜：仅保留「机构净买入」正期望分支；机游共振已剔除（2026-08-30 P0）
        lhb_info = lhb_map.get(raw_code)
        if lhb_info and lhb_info["inst_net"] > 0:
            fund += 3
            fund_detail.append(f"龙虎榜+{lhb_info['inst_net']:.0f}万")

        # 北向资金：2024年5月起港交所不再披露明细，仅data_date空壳，不再加分
        # 铁律：宁可空着也不用假数据

        # 板块共振 (0 ~ +10)
        sector_score = 0
        sector_detail = ""
        stock_sectors = ind_map.get(raw_code, []) or s.get("sectors", [])
        if isinstance(stock_sectors, dict):
            # industry_map 格式可能是 {sector_name: ...}
            stock_sectors = list(stock_sectors.keys()) if isinstance(stock_sectors, dict) else []
        elif isinstance(stock_sectors, str):
            stock_sectors = [stock_sectors]

        sector = s.get("sector", "")
        if sector and sector not in stock_sectors:
            stock_sectors = [sector] + stock_sectors

        # 取【最强流入】的单个赛道板块，而非求和 —— 概念板块高度重叠，求和会
        # 重复计数：实测亨通光电 19 个概念求和达 -1338.91 亿，而全市场最大净流入
        # 板块仅 32.94 亿，数量级完全失真（同一笔资金被重复计了 N 次）。
        # 🔴 初值用 None 而非 0：原写法下若所有板块均为负（弱势市况），
        #    `flow > 0` 恒不成立 → best 保持 0 → 既不加也不扣，
        #    板块失血被当成「无数据」放过。
        best_sector_flow = None
        best_sector_name = ""
        for sec_name in stock_sectors:
            flow = sector_flow_in.get(sec_name)
            if flow is None:
                continue
            if best_sector_flow is None or flow > best_sector_flow:
                best_sector_flow = flow
                best_sector_name = sec_name

        if best_sector_flow is None:
            sector_detail = ""                      # 无板块资金数据，不编造
        elif best_sector_flow > 5:
            sector_score += 5
            sector_detail = f"{best_sector_name}+{best_sector_flow:.1f}亿"
        elif best_sector_flow > 1:
            sector_score += 2
            sector_detail = f"{best_sector_name}+{best_sector_flow:.1f}亿"
        elif best_sector_flow < -5:
            sector_score -= 3                       # 修复后此处才真正可能触发
            sector_detail = f"{best_sector_name}{best_sector_flow:.1f}亿"
        else:
            sector_detail = f"{best_sector_name}{best_sector_flow:+.1f}亿"

        # 机构/投行 (0 ~ +7)  2026-08-28：mahoro 已移除，只剩 52周新高 + 分析师关注
        inst = 0
        inst_detail = []

        if raw_code in w52_codes or name in w52_names:
            inst += 4
            inst_detail.append("52周新高")

        if raw_code in analyst_codes or name in analyst_names:
            inst += 3
            inst_detail.append("分析师关注")

        # ── 止损位 / 目标价 ──
        close_price = latest.get("close") or s.get("close") or 0
        # 近5日最低/最高收盘价（用于辅助计算）
        recent_closes = []
        sorted_hist_all = sorted(hist, key=lambda h: h.get("date", ""), reverse=False)
        for h in sorted_hist_all:
            hc = h.get("close", 0)
            if hc and hc > 0:
                recent_closes.append(hc)
        recent5 = recent_closes[-5:] if len(recent_closes) >= 5 else recent_closes
        recent20 = recent_closes[-20:] if len(recent_closes) >= 20 else recent_closes

        # 方案三统一口径（此处只有收盘价序列，用降级版：固定10%止损 + R:R=1.5止盈）
        stop_loss, target_price = 0, 0
        stop_loss_method, target_price_method, risk_reward = "", "", 0
        if close_price and close_price > 0:
            _board = s.get("board_label", "") or board_from_code(raw_code)
            _st = compute_stop_target_from_closes(recent_closes or [close_price], board=_board, strategy="general")
            if _st:
                stop_loss = _st["stop_loss"]
                target_price = _st["target_price"]
                stop_loss_method = _st["stop_loss_method"]
                target_price_method = _st["target_price_method"]
                risk_reward = _st["risk_reward"]

        # ── 基本面质量分（复用 fundamental_helper，与驾驶舱口径一致；
        #     含港股中性兜底：旧数据 hk 误标 D 自动修正为中性；含消息面加减分）──
        # 格式: fundamental_stocks["hk_00005"] = {grade, score, roe, revenue_growth, reason, news}
        mkt = s.get("market", "")
        raw_code = s.get("code", "")
        fq_key = fq_key_of(mkt, raw_code)
        fq = fundamental_stocks.get(fq_key, {})
        quality_score, quality_grade, quality_detail = quality_points(fq)

        # ── 原始总分（各维度绝对加分之和）──
        raw_total = base + enhance + form_score + fund + sector_score + inst + quality_score

        # ── 回测反哺（P2 重写 2026-09-05）：walk-forward 信号组合 T+10 edge 直接修正 ──
        # edge 每 1% ≈ ±1 分，clamp ±10；组合缺失回退 0（中性）。
        sig_tuple = (has_chan, sig_jinzuan, has_jigou, has_trend)
        bt_edge10 = bt_edge10_for(*sig_tuple)
        score_backtest = max(-10, min(10, round(bt_edge10)))
        raw_total = raw_total + score_backtest
        # T+10 胜率（用于前端展示，来自同一 walk-forward 回测；缺失组合回退 50）
        _wr_rec = BT_BY_SIGNAL.get(f"{int(has_chan)},{int(sig_jinzuan)},{int(has_jigou)},{int(has_trend)}")
        win_rate = float((_wr_rec or {}).get("win10", 50.0)) if _wr_rec else 50.0

        # 🚦 P0-1 门禁乘子：IC × Regime 联合微调（早于归一化，确保 max_score 口径一致）
        raw_total = raw_total * gate_multiplier

        # ── 归一化到 0~100 ──
        # 分母见模块顶部 NORM_DIVISOR 注释：250 已使 ≥80 分不可达，现校准为 130
        total = round(min(100, max(0, raw_total / NORM_DIVISOR * 100)), 1)

        # ── Regime 驱动的行业风格微调（2026-08-29 元模型升级）──
        #   根据 market_regime 推荐/规避板块，给个股 ±8% 的分数乘数。
        #   当前为保守微调，后续结合 v8_factor_ic.py 滚动 IC 再进一步校准。
        regime_adj = 1.0
        if _meta_model is not None:
            try:
                regime_adj = _meta_model.sector_multiplier(stock_sectors, stock_sectors)
                if regime_adj != 1.0:
                    total = round(min(100, max(0, total * regime_adj)), 1)
            except Exception as _e:
                print(f"  ⚠️ {name}({raw_code}) regime 调整失败: {_e}")

        scored.append({
            "code": raw_code,
            "full_code": key,
            "name": name,
            "market": s.get("market", ""),
            "board": s.get("board_label", ""),
            "sig_count": sig_count,
            "close": latest.get("close") or s.get("close") or 0,
            "pct_chg": latest.get("pct_chg") or s.get("pct_chg") or 0,
            "pct_chg_20d": pct20 or 0,
            "breakout_5d": breakout_5d,
            "total_score": total,
            "current_regime": current_regime,
            "regime_open": regime_open,
            "regime_adjust": regime_adj,
            "quality_grade": quality_grade,
            "quality_score": quality_score,
            "sectors": stock_sectors[:8] if isinstance(stock_sectors, list) else [],
            "stop_loss": stop_loss,
            "target_price": target_price,
            "stop_loss_method": stop_loss_method,
            "target_price_method": target_price_method,
            "risk_reward": risk_reward,
            "stop_precise": False,
            "breakdown": {
                "base": base,
                "enhance": enhance,
                "form": form_score,
                "fund": fund,
                "sector": sector_score,
                "inst": inst,
                "quality": quality_score,
                "backtest": score_backtest,
                "breakout": 5 if breakout_5d else 0,
                "research": research_score,
                "signals": {
                    "chan": has_chan,
                    "jinzuan": has_qizhang or has_huangzhu,
                    "jigou": has_jigou,
                    "trend": has_trend,
                    "form_A": sig_jinzuan and has_chan and ema_up >= 5 and rsi < 68 and pct20 < 35 and not limit_up,
                },
            },
            "win_rate": round(win_rate, 1),
            "details": {
                "consecutive_days": consecutive,
                "form": " | ".join(form_detail) if form_detail else "",
                "fund": " | ".join(fund_detail) if fund_detail else "",
                "sector": sector_detail,
                "inst": " | ".join(inst_detail) if inst_detail else "",
                "quality": quality_detail,
                "research": " | ".join(research_detail) if research_detail else "",
            },
        })

    # ── 5. 排序取TOP20 ──
    scored.sort(key=lambda x: -x["total_score"])

    # 格式化为简洁输出（含完整评分明细）
    top10 = []
    for i, s in enumerate(scored[:20]):
        bd = s["breakdown"]
        dt = s["details"]
        top10.append({
            "rank": i + 1,
            "code": s["code"],
            "name": s["name"],
            "market": s["market"],
            "board": s["board"],
            "sig_count": s["sig_count"],
            "close": s["close"],
            "pct_chg": s["pct_chg"],
            "pct_chg_20d": s["pct_chg_20d"],
            "breakout_5d": s.get("breakout_5d", False),
            "total_score": s["total_score"],
            "current_regime": s.get("current_regime", ""),
            "regime_open": s.get("regime_open", False),
            "regime_adjust": s.get("regime_adjust", 1.0),
            "sectors": s["sectors"],
            "stop_loss": s["stop_loss"],
            "target_price": s["target_price"],
            "stop_loss_method": s.get("stop_loss_method", ""),
            "target_price_method": s.get("target_price_method", ""),
            "risk_reward": s.get("risk_reward", 0),
            "stop_precise": s.get("stop_precise", False),
            "score_base": bd["base"],
            "score_enhance": bd["enhance"],
            "score_form": bd.get("form", 0),
            "score_fund": bd["fund"],
            "score_sector": bd["sector"],
            "score_inst": bd["inst"],
            "score_quality": bd.get("quality", 0),
            "score_backtest": bd.get("backtest", 0),
            "score_breakout": bd.get("breakout", 0),
            "score_research": bd.get("research", 0),
            "win_rate": s.get("win_rate", None),
            "quality_grade": s.get("quality_grade", ""),
            "signals": bd["signals"],
            "consecutive_days": dt["consecutive_days"],
            "form_detail": dt.get("form", ""),
            "fund_detail": dt["fund"],
            "sector_detail": dt["sector"],
            "inst_detail": dt["inst"],
            "quality_detail": dt.get("quality", ""),
        })

    count_80plus = sum(1 for s in scored if s.get("total_score", 0) >= 80)
    max_score = max((s.get("total_score", 0) for s in scored), default=0)
    regime_summary = _meta_model.regime_summary() if _meta_model is not None else {}
    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scored": len(scored),
        "count_80plus": count_80plus,
        "max_score": max_score,
        "norm_version": NORM_VERSION,
        "norm_divisor": NORM_DIVISOR,
        # 🔴 2026-08-28：可信回测（入场=次日开盘、扣往返 0.20%、基准=上证指数）
        #    显示持有期与超额收益强相关：
        #      T1 −0.58% / T3 −1.96% / T5 −1.87%  ← 短期跑输大盘
        #      T10 +6.05%(胜率64.5%) / T20 +5.92%(胜率75.1%)  ← 中长持有才有 alpha
        #    故全站默认建议持有 10 个交易日，前端可直接展示。
        "suggested_hold_days": 10,
        "regime_summary": regime_summary,
        # 🚦 P0-1 门禁信号透出（前端可直接展示 ic/regime/乘子，便于主人审核）
        "gate_info": {
            "current_regime": current_regime,
            "regime_open": regime_open,
            "ic_weight": ic_weight,
            "ic_action": ic_action,
            "regime_weight": regime_weight,
            "regime_action": regime_action,
            "gate_multiplier": round(gate_multiplier, 4),
            "applied_to": "ge3 (generate_top10)",
        },
        "top10": top10,
    }

    # 保存当日文件
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 保存历史：当日快照 + 历史汇总（供历史追踪）
    try:
        hist_dir = os.path.join(DATA_DIR, "history")
        os.makedirs(hist_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_file = os.path.join(hist_dir, f"top10_daily_{today_str.replace('-', '')}.json")
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        hist_file = os.path.join(hist_dir, "top10_daily_history.json")
        hist = load_json(hist_file, {})
        if not isinstance(hist, dict):
            hist = {}
        hist[today_str] = {
            "count_80plus": count_80plus,
            "total_scored": len(scored),
            "max_score": max_score,
            "update_time": result["update_time"],
        }
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)

        # 归一化历史快照（一次性过渡，保证旧 raw 分不影响回测口径）
        _migrate_old_top10_scores(hist_dir)
    except Exception as e:
        print(f"  [warn] 保存历史记录失败: {e}")

    gate_note = ""
    if abs(gate_multiplier - 1.0) > 0.01:
        gate_note = f" [门禁×{gate_multiplier:.2f} ic={ic_weight:.2f}({ic_action}) regime={regime_weight:.2f}({regime_action})]"
    print(f"  ✅ TOP10 已生成: {len(top10)} 只{gate_note}")
    for t in top10:
        print(f"     #{t['rank']} {t['name']}({t['code']}) 评分{t['total_score']} "
              f"基础{t['score_base']}+形态{t.get('score_form',0)}+增强{t['score_enhance']}+资金{t['score_fund']}+"
              f"板块{t['score_sector']}+机构{t['score_inst']}+"
              f"质量{t.get('score_quality',0)}{t.get('quality_grade','')}")
    print(f"  总评分: {len(scored)} 只")
    print(f"\n  输出: {OUTPUT}")
    print(f"\n  结果: ✓ 成功 ({datetime.now().strftime('%H:%M:%S')})")


if __name__ == "__main__":
    main()
