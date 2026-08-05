#!/usr/bin/env python3
"""v8 云端数据抓取（中国源 · 自托管 runner 在中国机器上执行）

⚠️ 重要前提（请小九/阿狸咪确认）：
- GitHub 官方 runner 在美国，抓 A 股数据源（东方财富/新浪/akshare 中国接口）会 60s 超时。
- 因此本工作流必须运行在「标记为 cn 的自托管 runner」上（即小九或阿狸咪的中国 IP 机器）。
- 本脚本用 akshare 抓取，逐模块 try/except：单个源失败只跳过该模块，不影响其他，
  且不会覆盖 data/*.js 中已有的正常数据（update_v8.py 只重写 raw_data 里存在的模块）。

⚠️ Schema 待小九核对：
- 每个 window.<VAR> 的字段结构以 index.html 渲染逻辑为准。本脚本产出的是「尽力而为」的结构，
  首次上线前请小九对照页面逐模块验证字段；字段不符的模块先不 push（脚本只写 raw_data，
  由 update_v8.py 转换，人工确认后再合入 main 的 data/）。

运行：python cloud_fetch_v8.py
依赖：akshare（pip install akshare），中国网络可达。
"""

import json, os, sys, time, subprocess
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# 2026-08-03 修复：Windows cn runner 默认 GBK 终端，emoji 输出会 UnicodeEncodeError 崩溃。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
RAW_DIR.mkdir(exist_ok=True)

# 变量名 → raw_data 文件名（与 update_v8.py 的 DATA_SOURCES 对应）
VAR_TO_RAW = {
    "ETF_INTRADAY_HEAT": "etf_intraday_heat.json",
    "SECTOR_FUND_FLOW": "sector_fund_flow.json",
    "CONCEPT_RANKING": "concept_ranking.json",
    "IPO_DATA": "ipo_score.json",
    "MARGIN_DATA": "margin_data.json",
    "CFFEX_HOLDINGS": "cffex_data.json",
    "MACRO_DATA": "macro_data.json",
    "CRISIS_DATA": "crisis_data.json",
    "MACRO_BRIEF": "macro_brief.json",
    "JUDGMENT_DATA": "judgment_data.json",
    "HERDING_DATA": "herding_data.json",
    "LIMIT_UP_HEATMAP": "limit_up_heatmap.json",
    "CAPITAL_FLOW_DATA": "capital_flow_data.json",
    "ETF_SUBSCRIPTION": "etf_subscription.json",
    "NORTH_FUND": "north_fund.json",
    "MARKET_FUND_FLOW_DATA": "market_fund_flow_data.json",
    "W52_HIGH": "w52_high.json",
    "ETF_PULSE": "etf_pulse.json",
    "ETF_DAILY_MONITOR": "etf_daily_monitor.json",
    "ANALYST_RATINGS": "analyst_ratings.json",
    "INDEX_QUOTES": "index_quotes.json",
    "EXPERIMENT": "experiment.json",
    "V8_CAL": "v8_cal.json",
    "CANDIDATE_QUOTES": "candidate_quotes.json",
    "SH_SZ_HISTORY": "sh_sz_history.json",
    "MARKET_ALERTS": "market_alerts.json",
}

# 变量名 → 更新时段（与 update_v8.py 的 CATEGORY_MAP 对齐）
CATEGORY_MAP = {
    # 盘前
    "V8_CAL": "premarket",
    "IPO_DATA": "premarket",
    "MARGIN_DATA": "premarket",
    "CFFEX_HOLDINGS": "premarket",
    "MACRO_DATA": "premarket",
    "CRISIS_DATA": "premarket",
    "MACRO_BRIEF": "premarket",
    "JUDGMENT_DATA": "premarket",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    "W52_HIGH": "premarket",
    "HERDING_DATA": "premarket",
    # 盘中（含 ETF 三连板、板块资金三连板盘中追热等实时场景）
    "INDEX_QUOTES": "intraday",
    "ETF_PULSE": "intraday",
    "ETF_INTRADAY_HEAT": "intraday",
    "ETF_DAILY_MONITOR": "intraday",
    "ETF_SUBSCRIPTION": "premarket",  # T+1 盘后/盘前更新一次即可
    "SECTOR_FUND_FLOW": "intraday",
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday",
    "CANDIDATE_QUOTES": "intraday",  # 候选池实时行情：行业树图第二层（个股）数据源
    "SH_SZ_HISTORY": "intraday",  # 沪深成交额历史（滚动窗口，盘中最少5刷）
    "MARKET_ALERTS": "intraday",  # 市场预警（孤儿模块 fetch_orphan_market_alerts.py 接入盘中刷新）
    # 盘后（15:30 后）：大盘资金流时间轴，累积历史序列，避免盘中覆盖
    "MARKET_FUND_FLOW_DATA": "post_close",
    # 15:30 收盘数据：EXPERIMENT 等 akshare 可抓的 T+1 数据
    "EXPERIMENT": "post_close",
}

_ak = None

def get_ak():
    global _ak
    if _ak is None:
        import akshare as _ak_mod
        _ak = _ak_mod
    return _ak

# 2026 年中国A股休市区间（与 index.html 硬编码日历保持一致；每年初更新）
_AS_HOLIDAY_RANGES_2026 = [
    ("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
]
_AS_MAKEUP_DAYS_2026 = {"2026-01-04", "2026-02-14", "2026-02-28",
                        "2026-05-09", "2026-09-20", "2026-10-10"}

def _is_trading_day(d=None):
    """判断某天是否为A股交易日。优先用 akshare 交易日历，失败则回退硬编码。"""
    d = d or datetime.now().date()
    iso = d.isoformat()
    if iso in _AS_MAKEUP_DAYS_2026:
        return True
    # 硬编码休市区间兜底
    for start, end in _AS_HOLIDAY_RANGES_2026:
        if start <= iso <= end:
            return False
    if d.weekday() >= 5:  # 周六日
        return False
    # 尝试 akshare 交易日历
    try:
        df = get_ak().tool_trade_date_hist_sina()
        if df is not None and not df.empty and 'trade_date' in df.columns:
            return iso in set(str(x)[:10] for x in df['trade_date'])
    except Exception:
        pass
    return True

def save(var, obj):
    fname = VAR_TO_RAW.get(var)
    if not fname:
        return
    obj = obj if isinstance(obj, dict) else {"data": obj}
    obj["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = RAW_DIR / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"  ✅ {var} → raw_data/{fname}")


# ───────────────────────── 东方财富「延迟镜像」直连 ─────────────────────────
# 说明：东方财富 push2.eastmoney.com / push2his.eastmoney.com 的实时资金流接口
# 在本机/runner 网络下被 WAF 以 TCP 重置（ConnectionError: RemoteDisconnected）拒绝；
# 但其「延迟镜像」push2delay.eastmoney.com 可达且返回相同字段（延迟仅数秒，对日频排名无影响）。
# 故资金流类接口统一走 push2delay，规避实时 host 的封锁。
import requests as _requests

_EM_DELAY = "https://push2delay.eastmoney.com"
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/zjlx/detail.html",
    "Accept": "*/*",
}

def em_clist(fs, fields, fid="f62", stat="1", pz=5000, po="1", timeout=15):
    """东方财富 clist 接口（push2delay 镜像）。返回 data.diff 列表（每项为字段字典）。
    po="1" 降序(取净流入最高)，po="0" 升序(取净流出最高)。"""
    params = {
        "pn": "1", "pz": str(pz), "po": po, "np": "1", "fltt": "2", "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fid": fid, "fs": fs, "stat": stat,
        "fields": fields, "_": int(time.time() * 1000),
    }
    r = _requests.get(f"{_EM_DELAY}/api/qt/clist/get", params=params,
                      headers=_EM_HEADERS, timeout=timeout)
    d = r.json()
    if d.get("rc") != 0 or not d.get("data"):
        return []
    return d["data"].get("diff", []) or []

def _to_yi(v):
    """东财字段单位为元，转亿（保留2位）。"""
    try:
        return round(float(v or 0) / 1e8, 2)
    except Exception:
        return 0.0


# 全市场个股过滤串（沪市/深市/北交所主力，排除指数与债券等）
_IND_FS = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2"

def _all_individual_recs(fields="f12,f14,f2,f3,f62,f184"):
    """取全市场个股主力净流入并集（降序 TOP + 升序 TOP 合并去重），用于准确求和与净流入/流出 TOP。"""
    desc = em_clist(_IND_FS, fields, fid="f62", stat="1", pz=5000, po="1")
    asc = em_clist(_IND_FS, fields, fid="f62", stat="1", pz=5000, po="0")
    by_code = {}
    for r in desc + asc:
        c = str(r.get("f12"))
        if c in by_code:
            continue
        by_code[c] = {
            "code": c,
            "name": r.get("f14"),
            "price": round(float(r.get("f2") or 0), 2),
            "chg": round(float(r.get("f3") or 0), 2),
            "net": _to_yi(r.get("f62")),
            "net_pct": round(float(r.get("f184") or 0), 2),
        }
    return list(by_code.values())

# 单次运行状态跟踪（用于前端定时任务跟踪看板）
_run_status = {}

def _fetch_remote_raw(rel_path):
    """从 GitHub main 拉取 raw_data 已有内容，作为追加型序列（如 sh_sz_history）的权威基线。
    绕过 git/HTTPS 封锁，走 Git Database / Contents API。失败返回 None。
    用途：本地 raw_data 在每次 intraday 运行开头会被清理删除，且 data/SH_SZ_HISTORY.js 滞后于
    推送→构建周期；直接用「上一次成功推送的远端版本」作基线，可根治追加型序列跨天塌缩（每日丢一天）。
    """
    import base64 as _b64
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        return None
    url = f"https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/raw_data/{rel_path}"
    try:
        r = _requests.get(url, headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}, timeout=30)
        d = r.json()
        if not isinstance(d, dict) or "content" not in d:
            return None
        content = _b64.b64decode(d.get("content", "")).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"  ⚠️ 远端基线拉取失败 {rel_path}: {e}")
        return None


def f_judgment():
    """今日判定（盘前 08:25 自动生成，注册于 JUDGMENT_DATA→premarket）。
    v2 动态版(2026-08-05): verdict/warning 根据指数实际幅度、量能、连跌天数、
    美股隔夜等维度动态组合生成，不再使用4套固定模板。
    """
    now = datetime.now()
    today = now.date()
    md = f"{today.month}/{today.day}"

    # 取指数行情
    idx_data = {}
    try:
        q = f_index_quotes()
        if q and q.get("items"):
            for it in q["items"]:
                idx_data[it["code"]] = it
    except Exception:
        idx_data = {}

    mains = [("000001", "上证指数"), ("399001", "深证成指"), ("399006", "创业板指")]
    indices, chgs, amounts = [], [], []
    for code, name in mains:
        it = idx_data.get(code)
        chg = round(float(it.get("chg", 0.0) or 0.0), 2) if it else 0.0
        amount = round(float(it.get("amount", 0.0) or 0.0), 2) if it else 0.0
        ctrl = round(chg, 1)
        fs = round(amount / 1000.0, 1)
        # 动态 warn：根据跌幅幅度给不同提示
        if it and abs(chg) < 0.05:
            warn = ""
        elif it and chg <= -1.5:
            warn = "近5日弱势"
        elif it and chg >= 1.5:
            warn = "近5日强势"
        else:
            warn = ""
        indices.append({"name": name, "ctrl": ctrl, "fs": fs, "warn": warn})
        chgs.append(chg)
        amounts.append(amount)

    neg = sum(1 for c in chgs if c < 0)
    pos = sum(1 for c in chgs if c > 0)
    total_amt = sum(amounts)
    avg_chg = sum(chgs) / len(chgs) if chgs else 0
    max_drop = min(chgs) if chgs else 0
    max_rise = max(chgs) if chgs else 0

    # 市场结构（保留原有逻辑）
    if neg == 3:
        market = "下行结构（三指数控盘全负）"
    elif pos == 3:
        market = "上行结构（三指数全正）"
    elif neg > pos:
        market = "偏弱分化（指数多数控盘为负）"
    elif pos > neg:
        market = "偏强分化（指数多数控盘为正）"
    else:
        market = "震荡分化（指数控盘方向不一）"

    us = _fetch_us_overnight()
    us_str = us if us else "美股隔夜数据获取中（盘前研判以 A 股结构为主）"

    # ====== 动态 verdict 组合生成 ======
    _severity = "强" if abs(avg_chg) > 1.0 else ("中" if abs(avg_chg) > 0.4 else "弱")
    _dir = "跌" if avg_chg < 0 else "涨"
    _vol_level = "放量" if total_amt > 12000 else ("缩量" if total_amt < 7000 else "平量")

    # 基础模板池（按市场状态分类）
    if neg == 3:
        # 全跌
        if max_drop <= -1.5:
            verdict = f"三指数全绿且跌幅超1.5%（{_severity}下行），{_vol_level}下跌中反弹不宜追高，控盘翻正前视为减仓窗口"
        elif max_drop <= -0.8:
            verdict = f"三指数同步调整（平均{avg_chg:+.2f}%），{_vol_level}格局下耐心等待企稳信号，勿急于抄底"
        else:
            verdict = f"三指数微幅低开（平均{avg_chg:+.2f}%），属正常波动范围，观察开盘半小时方向选择"
        warning = "无明确S点信号前持仓勿侥幸；弱势中追涨易被套。" if abs(avg_chg) > 0.8 else "控制仓位，关注抗跌板块。"
    elif pos == 3:
        # 全涨
        if max_rise >= 1.5:
            verdict = f"三指数全线飘红（平均{avg_chg:+.2f}%），{_severity}{_vol_level}上涨中逢回调可择优布局，但警惕冲高回落"
        elif max_rise >= 0.8:
            verdict = f"三指数共振上行（平均{avg_chg:+.2f}%），{_vol_level}健康，可积极参与但避免追涨缩量品种"
        else:
            verdict = f"三指数微幅高开（平均{avg_chg:+.2f}%），方向偏多但力度有限，轻仓试探为宜"
        warning = "普涨日区分真强与补涨，回避纯情绪驱动个股。" if abs(avg_chg) > 0.8 else "关注量价配合，缩量冲高宜减仓。"
    else:
        # 分化
        strong_idx = [i["name"] for i in indices if i["ctrl"] > 0]
        weak_idx = [i["name"] for i in indices if i["ctrl"] < 0]
        s_str = "+".join(strong_idx) if strong_idx else "无"
        w_str = "+".join(weak_idx) if weak_idx else "无"

        if abs(max_rise - max_drop) > 2.0:
            verdict = f"剧烈分化（{s_str}强 vs {w_str}弱，极差{abs(max_rise-max_drop):.1f}%），结构性机会与风险并存，重个股轻指数"
        elif abs(avg_chg) < 0.3:
            verdict = f"窄幅震荡（振幅<0.3%），多空平衡等待方向选择，宜观望或做T不追新仓"
        elif avg_chg > 0:
            verdict = f"偏强分化（{s_str}领涨），资金有明确偏好方向，跟随主流板块择优参与"
        else:
            verdict = f"偏弱分化（{w_str}承压），防御为主，仅限超短线机会"

        if total_amt > 11000:
            warning = f"成交额{total_amt:.0f}亿偏高，分歧加大注意快进快出。"
        elif total_amt < 7000:
            warning = f"成交额{total_amt:.0f}亿偏低，缺乏增量资金入场，谨慎开新仓。"
        else:
            warning = "控制仓位，聚焦资金共识方向，回避边缘题材。"

    return {
        "date": today.strftime("%Y-%m-%d"),
        "title": f"今日判定（{md}）",
        "market": market,
        "indices": indices,
        "us": us_str,
        "verdict": verdict,
        "warning": warning,
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }
def f_macro_brief():
    """每日宏观解读 + 时事要点（盘前 08:25 自动生成，注册于 MACRO_BRIEF→premarket）。
    
    基于当日 MACRO_DATA（利率/汇率/VIX/商品）+ CRISIS_DATA（危机雷达）+ 美股隔夜，
    用规则引擎生成：
      - headline: 一句话宏观结论
      - key_numbers: 3~5 个关键数据变动（含昨日对比）
      - news_brief: 3~5 条数据驱动的"时事要点"（对 A 股有影响的）
      - a_impact: 对 A 股的简短影响评估
    """
    now = datetime.now()
    today = now.date()

    # ---- 读取已生成的 MACRO_DATA ----
    macro = {}
    macro_path = Path(ROOT) / "data" / "MACRO_DATA.js"
    raw_macro_path = Path(ROOT) / "raw_data" / "macro_data.json"
    try:
        for p in [macro_path, raw_macro_path]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if txt.startswith("window.MACRO_DATA"):
                    txt = txt[len("window.MACRO_DATA "):].lstrip("=").lstrip().strip().rstrip(";")
                macro = json.loads(txt)
                if macro:
                    break
    except Exception:
        macro = {}

    gm = macro.get("global_macro", {})
    monetary = macro.get("monetary", {})
    commodities = gm.get("commodities", {})

    # ---- 读取危机雷达 ----
    crisis = {}
    crisis_path = Path(ROOT) / "data" / "CRISIS_DATA.js"
    raw_crisis_path = Path(ROOT) / "raw_data" / "crisis_data.json"
    try:
        for p in [crisis_path, raw_crisis_path]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if txt.startswith("window.CRISIS_DATA"):
                    txt = txt[len("window.CRISIS_DATA "):].lstrip("=").lstrip().strip().rstrip(";")
                crisis = json.loads(txt)
                if crisis:
                    break
    except Exception:
        crisis = {}

    # ---- 提取关键数值 ----
    vix = float(gm.get("vix", {}).get("value", 0) or 0)
    us10y = float(monetary.get("us_bond_10y", {}).get("value", 0) or 0)
    us10y_prev = float(monetary.get("us_bond_10y", {}).get("previous", 0) or 0)
    cn10y = float(monetary.get("cn_bond_10y", {}).get("value", 0) or 0)
    cn10y_prev = float(monetary.get("cn_bond_10y", {}).get("previous", 0) or 0)
    dxy = float(gm.get("dxy", {}).get("value", 0) or 0)
    usdcnh = float(gm.get("usdcnh", {}).get("price", 0) or 0)
    gold = float(commodities.get("gold", {}).get("value", 0) or 0)
    oil = float(commodities.get("oil", {}).get("value", 0) or 0)
    silver = float(commodities.get("silver", {}).get("value", 0) or 0)
    copper = float(commodities.get("copper", {}).get("value", 0) or 0)

    crisis_score = crisis.get("score", crisis.get("total_score", 0))
    crisis_level = crisis.get("level", "")

    # ---- 规则引擎：生成 headline ----
    signals = []
    if vix > 25:
        signals.append(f"VIX 飙升至 {vix:.1f}（恐慌区域）")
    elif vix > 20:
        signals.append(f"VIX 升至 {vix:.1f}（偏高）")
    elif vix < 13:
        signals.append(f"VIX 降至 {vix:.1f}（极度乐观）")

    if us10y > 4.5:
        signals.append(f"美债 10Y 突破 {us10y:.2f}%（紧缩压力）")
    elif us10y < 4.0:
        signals.append(f"美债 10Y 回落至 {us10y:.2f}%（压力缓和）")

    spread = cn10y - us10y if cn10y and us10y else None
    if spread is not None and spread < -2.8:
        signals.append(f"中美利差 {spread:.2f}%（历史深度倒挂收窄中）")

    if gold > 4200:
        signals.append(f"黄金突破 ${gold:.0f}/oz（避险情绪升温）")

    if crisis_score >= 70:
        signals.append(f"危机雷达 {crisis_score} 分（{crisis_level}·高风险）")
    elif crisis_score >= 50:
        signals.append(f"危机雷达 {crisis_score} 分（{crisis_level}·需关注）")

    if not signals:
        signals.append("全球宏观环境平稳，无极端信号")

    headline = "；".join(signals[:3])

    # ---- 关键数据变动表 ----
    key_numbers = []
    def _kn(label, value, prev, unit="", fmt=".2f"):
        if not value and value != 0:
            return
        if prev is None:
            delta = "—"   # 无昨日对比基准，不臆造变动
        else:
            d = value - prev
            arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
            delta = f"{arrow}{abs(d):{fmt}}{unit}" if d != 0 else "持平"
        key_numbers.append({
            "label": label,
            "value": f"{value:{fmt}}{unit}",
            "delta": delta,
        })

    _kn("美债 10Y", us10y, us10y_prev, "%")
    _kn("中国 10Y", cn10y, cn10y_prev, "%")
    _kn("VIX 恐慌指数", vix, None, fmt=".1f")
    _kn("美元指数 DXY", dxy, None, fmt=".2f")
    _kn("USD/CNH 汇率", usdcnh, None, fmt=".4f")
    _kn("黄金 COMEX", gold, None, "$/oz", fmt=".0f")
    _kn("原油 WTI", oil, None, "$/bbl", fmt=".1f")

    # ---- 数据驱动的时事要点（news_brief）----
    news = []

    # 美债
    if us10y and us10y_prev:
        yld_chg = round(us10y - us10y_prev, 4)
        if abs(yld_chg) >= 0.05:
            direction = "飙升" if yld_chg > 0 else "骤降"
            impact = "压制全球风险资产估值" if yld_chg > 0 else "利好风险资产反弹"
            news.append({
                "tag": "🇺🇸 美债",
                "text": f"10Y 美债收益率{direction}至 {us10y:.2f}%（单日{'+' if yld_chg>0 else ''}{yld_chg:+.2f}%bp），{impact}。A 股高估值成长板块承压{'减轻' if yld_chg<0 else '加剧'}。",
            })

    # VIX
    if vix:
        if vix > 25:
            news.append({"tag": "😰 全球风险", "text": f"VIX 跳升至 {vix:.1f}，进入恐慌区域。外围市场波动放大，北向资金可能趋于谨慎，A股开盘或有低开压力。"})
        elif vix < 13:
            news.append({"tag": "😌 全球风险", "text": f"VIX 降至 {vix:.1f} 的极低位，市场过度乐观。警惕均值回归风险，不宜追高。"})
        elif abs(vix - 17) > 3:
            direction = "攀升" if vix > 20 else "回落"
            news.append({"tag": "📊 波动率", "text": f"VIX {direction}至 {vix:.1f}，{'避险情绪升温' if vix>18 else '风险偏好回升'}。关注今日 A 股开盘联动反应。"})

    # 汇率
    if usdcnh:
        if usdcnh > 7.30:
            news.append({"tag": "💱 汇率", "text": f"USD/CNH 报 {usdcnh:.4f}，人民币贬值压力较大。外资流入意愿或受抑制，出口链相对受益。"})
        elif usdcnh < 7.00:
            news.append({"tag": "💱 汇率", "text": f"USD/CNH 回落至 {usdcnh:.4f}，人民币走强。外资配置 A 股环境改善，但出口企业汇兑收益承压。"})
        elif abs(usdcnh - 7.15) > 0.05:
            direction = "升值" if usdcnh < 7.15 else "贬值"
            news.append({"tag": "💱 汇率", "text": f"人民币对美元{direction}，USDCNH={usdcnh:.4f}。{'资金面偏紧' if usdcnh>7.2 else '资金面中性偏松'}。"})

    # 黄金
    if gold:
        if gold > 4300:
            news.append({"tag": "🥇 大宗", "text": f"COMEX 黄金突破 ${gold:.0f}/oz，避险资产持续走强。反映全球不确定性升温，黄金/防御板块相对受益。"})
        elif gold < 3800:
            news.append({"tag": "🥇 大宗", "text": f"COMEX 黄金回落至 ${gold:.0f}/oz，避险需求降温。风险偏好修复时资金可能从黄金回流股市。"})

    # 原油
    if oil:
        if oil > 85:
            news.append({"tag": "🛢️ 大宗", "text": f"WTI 原油突破 $85/bbl，通胀预期升温。可能推迟美联储降息节奏，对 A 股新能源/化工有成本传导影响。"})
        elif oil < 72:
            news.append({"tag": "🛢️ 大宗", "text": f"WTI 原油跌破 $72/bbl，能源成本下降。利好交运/化工等中下游行业，但反映全球需求疲软。"})

    # 中美利差
    if spread is not None:
        if spread > -2.0:
            news.append({"tag": "📈 利差", "text": f"中美 10Y 利差收窄至 {spread:.2f}%，人民币资产吸引力提升空间打开，中长期利好 A 股估值修复。"})
        elif spread < -3.2:
            news.append({"tag": "📉 利差", "text": f"中美 10Y 利差深度倒挂 {spread:.2f}%，资本外流压力仍在。央行货币政策空间受限，A 股估值承压。"})

    # 危机雷达
    if crisis_score >= 70:
        c_items = crisis.get("items", []) if isinstance(crisis.get("items"), list) else []
        top_risks = [it.get("name", it.get("label", "")) for it in c_items[:3] if it]
        risk_str = "、".join(top_risks) if top_risks else "多项指标异常"
        news.append({"tag": "🚨 风控", "text": f"危机雷达亮红灯（{crisis_score}分/{crisis_level}）：{risk_str}。建议降低仓位、提高现金比例，回避高 Beta 个股。"})
    elif crisis_score >= 50:
        news.append({"tag": "⚠️ 风控", "text": f"危机雷达黄色预警（{crisis_score}分），部分指标偏离正常区间。保持中等仓位，设置好止损位。"})

    # 如果没有任何新闻生成，给一条默认的
    if not news:
        news.append({
            "tag": "📋 宏观",
            "text": f"今日关键宏观数据：美债10Y={us10y or '--'}%、VIX={vix or '--'}、USD/CNH={usdcnh or '--'}、黄金=${gold or '--'}/oz。整体环境平稳，以 A 股内部结构性行情为主。",
        })

    # 限制条数
    news = news[:5]

    # ---- A 股影响综合评估 ----
    risk_factors = sum(1 for n in news if any(k in n["tag"] for k in ["😰", "🚨", "⚠️"]))
    benign_factors = sum(1 for n in news if any(k in n["tag"] for k in ["😌", "📈"]))

    if risk_factors >= 3:
        a_impact = "偏空：多重风险信号叠加，建议防守为主，控制仓位在 5 成以下，聚焦确定性高的红利/防御板块。"
    elif risk_factors >= 2:
        a_impact = "谨慎：存在 2-3 个风险因素，建议中性偏低仓位（5-6成），回避高波动题材，关注抗跌板块。"
    elif benign_factors >= 2 and risk_factors == 0:
        a_impact = "偏多：宏观环境友好，可积极布局（6-7成仓），关注受益于当前宏观主题的板块。"
    else:
        a_impact = "中性：多空因素交织，无明显方向性驱动。建议均衡配置（5-6成仓），轻指数重个股，跟随资金流向操作。"

    return {
        "date": today.strftime("%Y-%m-%d"),
        "headline": headline,
        "key_numbers": key_numbers,
        "news_brief": news,
        "a_impact": a_impact,
        "crisis_score": crisis_score,
        "crisis_level": crisis_level,
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "auto": True,
    }


def _fetch_us_overnight():
    """美股隔夜三大指数表现（最佳努力，失败返回空串）。"""
    try:
        r = _requests.get(
            f"{_EM_DELAY}/api/qt/ulist.np/get",
            params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                    "fields": "f12,f14,f3", "secids": "100.GSPC,100.IXIC,100.DJI"},
            headers=_EM_HEADERS, timeout=15)
        j = r.json()
        rows = (j.get("data", {}).get("diff") or [])
        if not rows:
            return ""
        parts = []
        all_up = True
        for x in rows:
            chg = float(x.get("f3") or 0)
            if chg < 0:
                all_up = False
            parts.append(f"{x.get('f14', '')}{chg:+.1f}%")
        return ("涨" if all_up else "跌") + "（" + "/".join(parts) + "）"
    except Exception:
        return ""


def run(label, fn, retries=2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            print(f">>> {label} {datetime.now().isoformat(timespec='seconds')}{' (retry '+str(attempt)+')' if attempt else ''}")
            obj = fn()
            if obj is not None:
                save(label, obj)
                _run_status[label] = {"status": "ok", "msg": "成功"}
            else:
                print(f"  ⚠️ {label}: 返回空，跳过")
                _run_status[label] = {"status": "empty", "msg": "返回空"}
            return
        except Exception as e:
            last_err = e
            print(f"  ❌ {label} 失败(attempt {attempt+1}/{retries+1}): {type(e).__name__}: {e}")
            _run_status[label] = {"status": "fail", "msg": f"{type(e).__name__}: {str(e)[:80]}"}
            time.sleep(2)
    print(f"  🚫 {label} 跳过，最终错误: {type(last_err).__name__}: {last_err}")
    time.sleep(0.5)

# 涨停池缓存（避免 limit_up_heatmap / herding 重复抓取同一份数据）
_zt_cache = {"date": None, "df": None}
def _get_zt_pool():
    d = datetime.now().strftime("%Y%m%d")
    if _zt_cache["date"] == d and _zt_cache["df"] is not None:
        return _zt_cache["df"]
    df = get_ak().stock_zt_pool_em(date=d)
    _zt_cache["date"] = d
    _zt_cache["df"] = df
    return df

# ───────────────────────── 各模块抓取（akshare） ─────────────────────────

def f_etf_intraday_heat():
    # ETF 主力净流入真实排名（东财 push2delay，ETF 市场 m:1+t:9，fid=f62）。
    # 返回：items(净流入TOP，含成交额供内联卡) + categories(宽基/行业/主题/跨境 分类净流入)
    snap = em_clist("m:1+t:9", "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=3000, po="1")
    recs = []
    for r in snap:
        try:
            code = str(r.get("f12"))
            name = r.get("f14")
            recs.append({
                "代码": code, "名称": name,
                "最新价": round(float(r.get("f2") or 0), 3),
                "涨跌幅": round(float(r.get("f3") or 0), 2),
                "成交额": round(float(r.get("f6") or 0), 2),
                "code": code, "name": name,
                "chg": round(float(r.get("f3") or 0), 2),
                "main_net_inflow": round(float(r.get("f62") or 0), 2),  # 元
                "pct": round(float(r.get("f184") or 0), 2),
            })
        except Exception:
            continue
    if not recs:
        return None
    ranked = sorted(recs, key=lambda x: x["main_net_inflow"], reverse=True)
    inflow_top = ranked[:30]
    outflow_top = sorted(recs, key=lambda x: x["main_net_inflow"])[:30]

    def cat_of(name):
        n = str(name or "")
        # 1) 宽基
        if any(k in n for k in ["沪深300", "中证500", "中证1000", "创业板", "科创", "上证50",
                                 "上证180", "深证", "MSCI", "A50", "双创", "300ETF", "500ETF"]):
            return "宽基"
        # 2) 商品（黄金/白银/原油/豆粕/能源/有色金属/商品等实物商品 ETF）
        if any(k in n for k in ["黄金", "白银", "原油", "豆粕", "能源", "有色金属", "商品", "矿业"]):
            return "商品"
        # 3) 跨境
        if any(k in n for k in ["恒生", "纳斯达克", "标普", "纳指", "日经", "德国", "法国", "美国",
                                 "道琼斯", "港股", "中概", "H股", "日本", "东南亚"]):
            return "跨境"
        # 4) 主题
        if any(k in n for k in ["5G", "人工智能", "AI", "半导体", "芯片", "新能源", "碳中和", "国企",
                                 "医药", "消费", "券商", "银行", "证券", "军工", "有色", "煤炭", "地产",
                                 "化工", "食品", "汽车", "光伏", "锂电", "机器人", "算力", "数据", "稀土",
                                 "钢铁", "保险", "传媒", "游戏", "养殖", "农业", "电力", "通信", "环保",
                                 "酒", "中药", "疫苗", "创新药", "VR", "物联网", "区块链", "元宇宙",
                                 "芯片", "科技", "电子", "高端装备", "智能"]):
            return "主题"
        return "行业"

    cats = {"宽基": [], "行业": [], "主题": [], "跨境": [], "商品": []}
    for r in recs:
        cats[cat_of(r["name"])].append(r)
    categories = {}
    for cn, lst in cats.items():
        net_yi = sum(x["main_net_inflow"] for x in lst) / 1e8
        top_in = sorted(lst, key=lambda x: x["main_net_inflow"], reverse=True)[:8]
        top_out = sorted(lst, key=lambda x: x["main_net_inflow"])[:8]
        categories[cn] = {
            "net_inflow_yi": round(net_yi, 2),
            "count": len(lst),
            "top_inflow": [{"code": x["code"], "name": x["name"],
                            "main_net_inflow": x["main_net_inflow"], "pct": x["pct"]} for x in top_in],
            "top_outflow": [{"code": x["code"], "name": x["name"],
                             "main_net_inflow": x["main_net_inflow"], "pct": x["pct"]} for x in top_out],
        }
    return {
        "items": inflow_top,
        "inflow_top": inflow_top,
        "outflow_top": outflow_top,
        "categories": categories,
        "note": "ETF主力净流入真实排名(东财push2delay, ETF市场m:1+t:9, fid=f62)；净流入单位元，分类按名称关键词",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def f_sector_fund_flow():
    # 板块/概念资金流：行业(m:90 t:2) + 概念(m:90 t:3)，主力净流入(f62, 元→亿)
    # 走 push2delay 镜像，规避实时 push2 host 的 WAF 重置。
    # 同时生成 sectors_in/out（供 renderSector 直接渲染）与 top_list（兼容降级）。
    items = []
    for stype, fs in [("行业", "m:90 t:2"), ("概念", "m:90 t:3")]:
        rows = em_clist(fs, "f12,f14,f3,f62,f184", fid="f62", stat="1", pz=200)
        for r in rows:
            net = _to_yi(r.get("f62"))
            if net == 0:
                continue
            items.append({
                "name": r.get("f14"),
                "type": stype,
                "net": net,
                "chg": round(float(r.get("f3") or 0), 2),
            })
    if not items:
        return None
    items.sort(key=lambda x: x["net"], reverse=True)
    sectors_in = [x for x in items if x["net"] > 0]
    sectors_out = [x for x in items if x["net"] < 0]
    return {
        "sectors_in": sectors_in,
        "sectors_out": sectors_out,
        "top_list": items,
        "note": "行业+概念主力净流入(亿)，来源东方财富push2delay",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def f_index_quotes():
    # 四大核心宽基指数实时行情：上证/深证/创业板/科创50
    # 东财 ulist.np 接口，secid 规则：1=上海，0=深圳
    # 2026-08-03 修复：本机/cn runner 直连 push2 host 会被 WAF 重置，改走 push2delay 镜像。
    secids = "1.000001,0.399001,0.399006,1.000688"
    names = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000688": "科创50"}
    short = {"000001": "沪指", "399001": "深成指", "399006": "创业板", "000688": "科创板"}
    rows = []
    for attempt in range(3):
        try:
            r = _requests.get(
                f"{_EM_DELAY}/api/qt/ulist.np/get",
                params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                        "fields": "f2,f3,f4,f5,f6,f12,f13,f14,f18,f20,f21,f104,f105,f106", "secids": secids},
                headers=_EM_HEADERS, timeout=15)
            j = r.json()
            rows = j.get("data", {}).get("diff", []) or []
            if rows:
                break
        except Exception as e:
            print(f"  ⚠️ 东财指数行情失败(尝试{attempt+1}/3): {e}")
            time.sleep(1.5)
    items = []
    for r in rows:
        code = str(r.get("f12") or "")
        # 东财 f13 标记 1=上海 0=深圳
        prefix = "SH" if str(r.get("f13")) == "1" else "SZ"
        full_code = prefix + code
        up = int(r.get("f104") or 0)
        down = int(r.get("f105") or 0)
        flat = int(r.get("f106") or 0)
        items.append({
            "code": code,
            "full_code": full_code,
            "name": names.get(code, r.get("f14", code)),
            "short": short.get(code, r.get("f14", code)),
            "price": round(float(r.get("f2") or 0), 2),
            "chg": round(float(r.get("f3") or 0), 2),
            "change": round(float(r.get("f4") or 0), 2),
            "volume": int(r.get("f5") or 0),
            "amount": round(float(r.get("f6") or 0) / 1e8, 2),  # 元->亿
            "prev_close": round(float(r.get("f18") or 0), 2),
            "total_mv": round(float(r.get("f20") or 0) / 1e8, 2),  # 总市值亿
            "float_mv": round(float(r.get("f21") or 0) / 1e8, 2),  # 流通市值亿
            "up": up,
            "down": down,
            "flat": flat,
        })
    if not items:
        return None
    return {"items": items, "note": "东财实时指数行情(push2delay)"}

def f_concept_ranking():
    # 概念板块列表（涨跌幅 + 主力净流入），push2delay 镜像。
    rows = em_clist("m:90 t:3 f:!50", "f12,f14,f3,f62,f184,f20", fid="f62", stat="1", pz=300)
    items = []
    for r in rows:
        items.append({
            "code": r.get("f12"),
            "name": r.get("f14"),
            "chg": round(float(r.get("f3") or 0), 2),
            "net": _to_yi(r.get("f62")),
            "amount": round(float(r.get("f20") or 0) / 1e8, 2),
        })
    if not items:
        return None
    return {"items": items, "note": "概念板块列表(涨跌幅/主力净流入亿)，来源东方财富push2delay"}

def f_candidate_quotes():
    """候选池实时行情（行业树图第二层·个股数据源）。

    方案：ulist 批量拉取（走 push2delay 延迟镜像，规避实时 push2 host 的 WAF TCP 重置；
    分小批 100 个 secid/批，长 secid 串会偶发被断连）。字段：当日涨跌幅/现价/市值。
    """
    try:
        with open(RAW_DIR / "candidate.json", encoding="utf-8") as f:
            cand = json.load(f)
    except Exception as e:
        print(f"  ⚠️ candidate.json 读取失败: {e}")
        return None
    stocks = cand.get("stocks") or {}
    if not stocks:
        print("  ⚠️ 候选池为空，跳过 CANDIDATE_QUOTES")
        return None
    # 构造 secid 分批：market sh→1, sz→0
    secids = []
    for sid, s in stocks.items():
        code = str(s.get("code") or "")
        if not code:
            continue
        mkt = "1" if str(s.get("market", "")).lower() == "sh" else "0"
        secids.append(f"{mkt}.{code}")
    if not secids:
        return None
    items = []
    BATCH = 100
    for i in range(0, len(secids), BATCH):
        batch = secids[i:i + BATCH]
        rows = []
        for attempt in range(3):
            try:
                r = _requests.get(
                    f"{_EM_DELAY}/api/qt/ulist.np/get",
                    params={"fltt": "2", "invt": "2",
                            "ut": "b2884a393a59ad64002292a3e90d46a5",
                            "fields": "f2,f3,f12,f13,f14,f20,f21",
                            "secids": ",".join(batch)},
                    headers=_EM_HEADERS, timeout=15)
                j = r.json()
                rows = j.get("data", {}).get("diff", []) or []
                if rows:
                    break
            except Exception as e:
                print(f"  ⚠️ 候选池行情批次 {i//BATCH+1} 尝试{attempt+1}失败: {str(e)[:60]}")
                time.sleep(2 * (attempt + 1))
        for r in rows:
            code = str(r.get("f12") or "")
            if not code:
                continue
            # f2 可能为 "-"（停牌/未开），此时视为无行情
            price = r.get("f2")
            if price in (None, "-", ""):
                continue
            items.append({
                "code": code,
                "name": r.get("f14") or code,
                "price": round(float(price), 2),
                "chg": round(float(r.get("f3") or 0), 2),
                "total_mv": round(float(r.get("f20") or 0) / 1e8, 2),   # 元→亿
                "float_mv": round(float(r.get("f21") or 0) / 1e8, 2),
            })
    if not items:
        print("  ⚠️ 候选池行情无有效数据")
        return None
    return {"items": items, "note": "候选池实时行情(涨跌幅/现价/市值)，来源东方财富push2delay"}

def f_ipo_data():
    """打新日历：复用 v6 验证有效的东财 datacenter + 可转债 + 同花顺已上市补充逻辑。"""
    try:
        import fetch_ipo_data_v8 as ipo
        return ipo.generate_ipo_score()
    except Exception as e:
        print(f"  ⚠️ IPO 抓取失败: {e}")
        return None

def f_margin_data():
    """两融余额走势：上交所融资融券汇总（日线）。
    输出结构与 v6 MARGIN_DATA 一致：{sh:[{date,date_raw,rz_balance,rq_balance_amt,total}], update_time}
    """
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    result = {"sh": [], "update_time": ""}
    try:
        df = get_ak().stock_margin_sse(start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        rows = []
        for _, row in df.iterrows():
            dt = str(row["信用交易日期"])
            try:
                d_obj = datetime.strptime(dt, "%Y%m%d")
                dt_fmt = f"{d_obj.month}/{d_obj.day}"
            except Exception:
                dt_fmt = dt
            rows.append({
                "date": dt_fmt,
                "date_raw": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                "rz_balance": round(float(row["融资余额"]) / 1e8),
                "rz_buy": round(float(row["融资买入额"]) / 1e8),
                "rq_balance_amt": round(float(row["融券余量金额"]) / 1e8),
                "total": round(float(row["融资融券余额"]) / 1e8),
            })
        # 按日期升序（旧→新），保证图表方向正确
        rows.sort(key=lambda x: x["date_raw"])
        result["sh"] = rows
        print(f"  ✅ 两融余额：{len(rows)} 条")
    except Exception as e:
        print(f"  ❌ 两融余额失败: {e}")
        return None
    result["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return result

def f_cffex_holdings():
    # 中金所股指期货日行情：动态取最近有数据的交易日（盘后数据通常当日稍晚才出）
    ak = get_ak()
    base = datetime.now()
    for back in range(0, 8):
        dd = (base - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = ak.get_cffex_daily(date=dd)
        except Exception as e:
            df = None
        if df is not None and not df.empty:
            return {"items": df.to_dict(orient="records"),
                    "update_time": dd,
                    "note": "中金所股指期货日行情（最近交易日 %s）" % dd}
    return None

def f_macro_data():
    """宏观数据：保留已有丰富字段，增量更新 CPI/PMI 及债券/Shibor/LPR/M2 前值"""
    import json
    # 以现有 raw_data/macro_data.json 为基线，避免云端 runner 把 rich 结构冲成只有 cpi/pmi
    base_path = RAW_DIR / "macro_data.json"
    out = {}
    if base_path.exists():
        try:
            with open(base_path, encoding="utf-8") as f:
                out = json.load(f)
        except Exception:
            out = {}
    if not isinstance(out, dict):
        out = {}
    # 保证结构
    out.setdefault("monetary", {})
    out.setdefault("economy", {})
    out.setdefault("market_sentiment", {})
    out.setdefault("global_macro", {})
    out.setdefault("indicator_status", {})

    def mark_updated(indicator_key, data_dict):
        sched = {
            'lpr': {'name': 'LPR利率', 'expected_day': 20, 'tolerance_days': 5},
            'm2_yoy': {'name': 'M2同比', 'expected_day': 12, 'tolerance_days': 5},
            'pmi': {'name': '制造业PMI', 'expected_day': 1, 'tolerance_days': 10},
            'cpi': {'name': 'CPI同比', 'expected_day': 10, 'tolerance_days': 5},
            'ppi': {'name': 'PPI同比', 'expected_day': 10, 'tolerance_days': 5},
            'social_financing': {'name': '社融规模', 'expected_day': 10, 'tolerance_days': 8},
            'export_yoy': {'name': '出口增速', 'expected_day': 7, 'tolerance_days': 5},
            'new_investors': {'name': '新增投资者', 'expected_day': 15, 'tolerance_days': 10},
        }
        st = sched.get(indicator_key)
        if not st:
            return
        data_date = str(data_dict.get('date', ''))[:10]
        is_fresh = False
        try:
            from datetime import datetime
            dt = datetime.strptime(data_date, '%Y-%m-%d')
            is_fresh = (datetime.now() - dt).days <= 60
        except Exception:
            pass
        out['indicator_status'][indicator_key] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'is_fresh': is_fresh,
            'name': st['name'],
            'frequency': 'monthly' if indicator_key in ('lpr','m2_yoy','pmi','cpi','ppi','social_financing','export_yoy','new_investors') else 'daily',
        }

    # 1) CPI / PMI 数组（保留原 flat schema 兼容）
    try:
        cpi = get_ak().macro_china_cpi_yearly()
        out["cpi"] = cpi.tail(6).to_dict(orient="records") if cpi is not None else []
    except Exception:
        out.setdefault("cpi", [])
    try:
        pmi = get_ak().macro_china_pmi_yearly()
        out["pmi"] = pmi.tail(6).to_dict(orient="records") if pmi is not None else []
    except Exception:
        out.setdefault("pmi", [])

    # 2) 债券收益率 + 前值
    try:
        df = get_ak().bond_zh_us_rate()
        if df is not None and len(df) > 1:
            cn = df[['日期', '中国国债收益率10年']].dropna()
            us = df[['日期', '美国国债收益率10年']].dropna()
            if len(cn) > 0:
                cl = cn.iloc[-1]
                out['monetary']['cn_bond_10y'] = {
                    'value': round(float(cl['中国国债收益率10年']), 4),
                    'date': str(cl['日期'])[:10],
                    'previous': round(float(cn.iloc[-2]['中国国债收益率10年']), 4) if len(cn) > 1 else None,
                }
            if len(us) > 0:
                ul = us.iloc[-1]
                out['monetary']['us_bond_10y'] = {
                    'value': round(float(ul['美国国债收益率10年']), 4),
                    'date': str(ul['日期'])[:10],
                    'previous': round(float(us.iloc[-2]['美国国债收益率10年']), 4) if len(us) > 1 else None,
                }
            if 'cn_bond_10y' in out['monetary'] and 'us_bond_10y' in out['monetary']:
                cn_v = out['monetary']['cn_bond_10y']['value']
                us_v = out['monetary']['us_bond_10y']['value']
                cn_p = out['monetary']['cn_bond_10y'].get('previous')
                us_p = out['monetary']['us_bond_10y'].get('previous')
                out['monetary']['cn_us_spread'] = {'value': round(cn_v - us_v, 2)}
                if cn_p is not None and us_p is not None:
                    out['monetary']['cn_us_spread']['previous'] = round(cn_p - us_p, 2)
    except Exception as e:
        print(f"  ⚠️ 国债收益率获取失败: {e}")

    # 3) LPR + 前值
    try:
        df_lpr = get_ak().macro_china_lpr()
        if df_lpr is not None and len(df_lpr) > 0:
            lpr_last = df_lpr.iloc[-1]
            out['monetary']['lpr'] = {
                'lpr_1y': float(lpr_last['LPR1Y']),
                'lpr_5y': float(lpr_last['LPR5Y']),
                'date': str(lpr_last['TRADE_DATE'])[:10],
                'previous_1y': float(df_lpr.iloc[-2]['LPR1Y']) if len(df_lpr) > 1 else None,
                'previous_5y': float(df_lpr.iloc[-2]['LPR5Y']) if len(df_lpr) > 1 else None,
            }
            mark_updated('lpr', out['monetary']['lpr'])
    except Exception as e:
        print(f"  ⚠️ LPR获取失败: {e}")

    # 4) Shibor + 前值
    try:
        df_shibor = get_ak().macro_china_shibor_all()
        if df_shibor is not None and len(df_shibor) > 0:
            sh = df_shibor.iloc[-1]
            prev = df_shibor.iloc[-2] if len(df_shibor) > 1 else None
            out['monetary']['shibor'] = {
                'on': float(sh.get('O/N-定价', 0)),
                'w1': float(sh.get('1W-定价', 0)),
                'm1': float(sh.get('1M-定价', 0)),
                'm3': float(sh.get('3M-定价', 0)),
                'date': str(sh.get('日期', ''))[:10],
                'previous_on': float(prev.get('O/N-定价', 0)) if prev is not None else None,
                'previous_w1': float(prev.get('1W-定价', 0)) if prev is not None else None,
            }
    except Exception as e:
        print(f"  ⚠️ Shibor获取失败: {e}")

    # 5) M2/M1 货币供应 + 前值
    try:
        df_m2 = get_ak().macro_china_money_supply()
        if df_m2 is not None and len(df_m2) > 0:
            m2_row = df_m2.iloc[0]
            m2_val = m2_row.get('货币和准货币(M2)-同比增长')
            m2_date = str(m2_row['月份']).replace('年', '-').replace('月份', '-01')
            prev_val = df_m2.iloc[1].get('货币和准货币(M2)-同比增长') if len(df_m2) > 1 else None
            out['monetary']['m2_yoy'] = {
                'value': float(m2_val) if pd.notna(m2_val) else None,
                'date': m2_date,
                'previous': float(prev_val) if prev_val is not None and pd.notna(prev_val) else None,
            }
            if out['monetary']['m2_yoy']['value'] is not None:
                mark_updated('m2_yoy', out['monetary']['m2_yoy'])
    except Exception as e:
        print(f"  ⚠️ M2获取失败: {e}")

    # 6) 把 flat cpi/pmi 数组同步到 economy 对象（index.html 渲染需要 ec.cpi.value / ec.pmi.value）
    def _last_numeric(arr, val_key='今值', prev_key='前值', date_key='日期'):
        if not arr:
            return None
        for row in reversed(arr):
            v = row.get(val_key)
            if v is not None and not pd.isna(v):
                try:
                    return {
                        'value': float(v),
                        'date': str(row.get(date_key, ''))[:10],
                        'previous': float(row[prev_key]) if row.get(prev_key) is not None and not pd.isna(row[prev_key]) else None,
                    }
                except Exception:
                    pass
        return None

    try:
        cpi_last = _last_numeric(out.get('cpi', []))
        if cpi_last:
            out['economy']['cpi'] = cpi_last
            mark_updated('cpi', cpi_last)
        pmi_last = _last_numeric(out.get('pmi', []))
        if pmi_last:
            out['economy']['pmi'] = pmi_last
            mark_updated('pmi', pmi_last)
    except Exception as e:
        print(f"  ⚠️ economy 同步失败: {e}")

    # 7) 全球宏观：离岸人民币、美元指数、VIX、黄金、白银、铜、原油（盘中也可更新）
    def _parse_sina_csv(body):
        """解析 sinajs.cn 返回的多条 var hq_str_xxx=\"...\"; 语句"""
        result = {}
        for line in body.split(';'):
            line = line.strip()
            if not line.startswith('var hq_str_'):
                continue
            eq = line.find('=')
            if eq < 0:
                continue
            key = line[len('var hq_str_'):eq]
            q1 = line.find('"')
            q2 = line.rfind('"')
            rest = line[q1 + 1:q2] if q1 >= 0 and q2 > q1 else ''
            result[key] = rest.split(',') if rest else []
        return result

    gm = out.setdefault('global_macro', {})

    def _fetch_sina_global_macro(retries=2):
        """新浪全球宏观行情，带重试与详细日志。"""
        sina_codes = "fx_susdcnh,DINIW,b_VIX,hf_GC,hf_SI,hf_HG,hf_CL"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "*/*",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                r = _requests.get(
                    f"https://hq.sinajs.cn/list={sina_codes}",
                    headers=headers,
                    timeout=20,
                )
                r.encoding = 'gb2312'
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = _parse_sina_csv(r.text)
                if not data:
                    raise RuntimeError("解析结果为空")
                return data
            except Exception as e:
                last_err = e
                print(f"    ⚠️ 新浪全球宏观尝试 {attempt+1}/{retries+1} 失败: {e}")
                time.sleep(1.5 * (attempt + 1))
        print(f"    🚫 新浪全球宏观最终失败: {last_err}")
        return {}

    data = _fetch_sina_global_macro()

    # 解析函数：安全取值并打印字段数
    def _set_gm(key, value, date_str=None):
        if value is None:
            return
        try:
            gm[key] = {'value': float(value)} if key != 'usdcnh' else {'price': float(value)}
            if date_str:
                gm[key]['date'] = date_str
        except Exception as e:
            print(f"    ⚠️ global_macro {key} 转换失败: value={value}, {e}")

    # 离岸人民币 fx_susdcnh：索引 8=收盘价/即期，17=日期
    parts = data.get('fx_susdcnh', [])
    if len(parts) > 8:
        _set_gm('usdcnh', parts[8], parts[17] if len(parts) > 17 else None)
    else:
        print(f"    ⚠️ fx_susdcnh 字段不足: {len(parts)}")

    # 美元指数 DINIW：索引 8=收盘价，10=日期
    parts = data.get('DINIW', [])
    if len(parts) > 8:
        _set_gm('dxy', parts[8], parts[10] if len(parts) > 10 else None)
    else:
        print(f"    ⚠️ DINIW 字段不足: {len(parts)}")

    # VIX：索引 1=当前值，6=日期
    parts = data.get('b_VIX', [])
    if len(parts) > 1:
        _set_gm('vix', parts[1], parts[6] if len(parts) > 6 else None)
    else:
        print(f"    ⚠️ b_VIX 字段不足: {len(parts)}")

    # 商品：索引 0=最新价，12=日期；统一放到 commodities 对象下保持前端兼容
    commodity_map = [('hf_GC', 'gold'), ('hf_SI', 'silver'), ('hf_HG', 'copper'), ('hf_CL', 'oil')]
    commodities = gm.setdefault('commodities', {})
    for code, name in commodity_map:
        parts = data.get(code, [])
        if parts and parts[0] not in (None, '', '-'):
            try:
                commodities[name] = {'value': float(parts[0])}
                if len(parts) > 12:
                    commodities[name]['date'] = parts[12]
            except Exception as e:
                print(f"    ⚠️ {code}({name}) 转换失败: {parts[0]}, {e}")
        else:
            print(f"    ⚠️ {code}({name}) 无有效价格: {parts[:3] if parts else 'empty'}")

    # fallback：新浪失败时，用 akshare 外汇/商品接口补部分数据
    if not gm.get('usdcnh') or not gm.get('dxy'):
        try:
            ak = get_ak()
            if not gm.get('usdcnh'):
                try:
                    fx = ak.fx_spot_quote()
                    if fx is not None and not fx.empty:
                        usd_cnh = fx[fx['code'] == 'USDCNH']
                        if not usd_cnh.empty:
                            gm['usdcnh'] = {'price': float(usd_cnh.iloc[0]['bid']), 'date': datetime.now().strftime('%Y-%m-%d')}
                            print("    ✅ akshare fallback USDCNH")
                except Exception as e:
                    print(f"    ⚠️ akshare USDCNH fallback 失败: {e}")
        except Exception as e:
            print(f"    ⚠️ akshare fallback 整体失败: {e}")

    print(f"    ✅ 全球宏观结果: { {k: v.get('value') or v.get('price') for k, v in gm.items()} }")
    return out

def f_crisis_data():
    # 危机雷达：三个维度尽量用真实数据
    # 经济维度：中国 PMI（真实）
    economy = None
    try:
        pmi = get_ak().macro_china_pmi_yearly()
        if pmi is not None and not pmi.empty:
            last = pmi.iloc[-1]
            v = last.get("今值")
            if v is None:
                v = last.get("value")
            if v is not None:
                economy = float(v)
    except Exception:
        economy = None

    # 货币维度：中国银行美元汇率（真实，替代估值）
    # 逻辑：USD/CNY 中间价偏离 7.0 基线的程度 → 货币压力分
    currency_score = 0.30  # 默认保守值
    usd_cny_latest = None
    try:
        boc = get_ak().currency_boc_safe()
        if boc is not None and not boc.empty:
            # 取最近有数据的美元列
            usd_col = next((c for c in boc.columns if c == "美元"), None)
            if usd_col:
                # 倒序找最新非空值
                for val in boc[usd_col].iloc[::-1]:
                    if pd.notna(val) and float(val) > 0:
                        usd_cny_latest = float(val)
                        break
                if usd_cny_latest:
                    # BOC 汇率单位为"每100外币"，需除以 100
                    usd_cny_latest = round(usd_cny_latest / 100.0, 4)
                    # 归一化：7.0=健康(0.2), 7.3=警戒(0.5), 7.5+=危险(0.8+)
                    if usd_cny_latest < 6.9:
                        currency_score = 0.15  # 强势人民币
                    elif usd_cny_latest < 7.1:
                        currency_score = 0.25  # 正常偏强
                    elif usd_cny_latest < 7.25:
                        currency_score = 0.40  # 正常区间
                    elif usd_cny_latest < 7.35:
                        currency_score = 0.55  # 有贬值压力
                    else:
                        currency_score = min(0.85, 0.55 + (usd_cny_latest - 7.35) * 0.3)
    except Exception as e:
        print(f"    ⚠️ 汇率数据获取失败: {e}")

    # 全球维度：仍用保守估值（CN 网络难达 VIX/美债等实时源），但标注更清晰
    global_score = 0.40  # 中性

    return {
        "currency": round(currency_score, 3),
        "economy": (round(economy / 100.0, 3) if economy else 0.50),
        "global": round(global_score, 3),
        "pmi_value": economy,
        "usd_cny": usd_cny_latest,
        "note": f"经济维度=中国PMI真实值({economy or 'N/A'})；"
               f"货币维度=中国银行USD/CNY中间价({usd_cny_latest or 'N/A'})；"
               f"全球维度因VIX/美债等源CN不可达暂用中性估值",
    }

def f_herding_data():
    # 羊群效应（抱团板块）：由当日涨停池的行业集中度推导
    # 涨停越集中在少数行业，说明资金抱团越强。
    try:
        df = _get_zt_pool()
    except Exception as e:
        print("  zt_pool err:", e)
        return None
    if df is None or df.empty:
        return None
    ind = {}
    for _, r in df.iterrows():
        name = r.get("所属行业") or "其它"
        if name in (None, "", "None"):
            name = "其它"
        ind[name] = ind.get(name, 0) + 1
    if not ind:
        return None
    clusters = []
    for k, v in sorted(ind.items(), key=lambda x: -x[1])[:3]:
        clusters.append({"sector": k, "direction": "强势抱团", "count": v})
    return {
        "current_clusters": clusters,
        "total_limit_up": int(len(df)),
        "note": "由涨停行业集中度推导的抱团板块（行业涨停数降序）",
    }

def f_limit_up_heatmap():
    # 涨停热力图：近10个交易日板块涨停家数日历时序（v6风格）。
    # 复用 fetch_limit_up_heatmap_v8.generate() 做重建/增量。
    try:
        import fetch_limit_up_heatmap_v8 as hm
        result = hm.generate()
        if not result:
            return None
        # 补充今日涨停池的连板梯队与TOP（保持前端兼容）
        try:
            df = _get_zt_pool()
            ladder = {}
            for _, r in df.iterrows():
                lb = int(r.get("连板数") or 0)
                ladder[lb] = ladder.get(lb, 0) + 1
            top = []
            for _, r in df.sort_values("连板数", ascending=False).head(8).iterrows():
                top.append({"name": r["名称"], "code": r["代码"],
                            "lbc": int(r.get("连板数") or 0),
                            "chg": round(float(r.get("涨跌幅") or 0), 2)})
            result["ladder"] = ladder
            result["top"] = top
            result["total"] = int(len(df))
        except Exception:
            pass
        result["note"] = "东方财富涨停池（真实），近10日板块涨停家数"
        return result
    except Exception as e:
        print(f"  ⚠️ 涨停热力图失败: {e}")
        return None

def f_capital_flow_data():
    # 个股主力净流入排行：全市场降序+升序并集（push2delay 镜像），
    # 规避实时 push2 host 的 WAF 重置，且避免 pz 截断只取头部导致净流出缺失。
    recs = _all_individual_recs()
    if not recs:
        return None
    recs.sort(key=lambda x: x["net"], reverse=True)
    inflow = [x for x in recs if x["net"] > 0][:20]
    outflow = sorted([x for x in recs if x["net"] < 0], key=lambda x: x["net"])[:20]
    market_net = round(sum(x["net"] for x in recs), 2)
    return {
        "top_inflow": inflow,
        "top_outflow": outflow,
        "market_net": market_net,
        "note": "全市场个股主力净流入(亿)，来源东方财富push2delay；非席位四路口径",
    }

# 宽基ETF申赎：行业/主题排除关键词（与 v6 fetch_etf_subscription.py 保持一致）
_ETF_SECTOR_KEYWORDS = [
    '半导体','芯片','医药','医疗','券商','银行','煤炭','通信','消费','军工','电池','新能源','光伏','有色','化工',
    '物联网','云计算','互联','科技','传媒','地产','基建','食品','汽车','钢铁','建材','农业','环保','旅游','教育',
    '港股','恒生','H股','德国','日本','法国','印度','越南','黄金','原油','豆粕','能源','商品','货币','债券','国债',
    '国开','政金','城投','信用','短融','存单','理财','标普','纳斯达克','MSCI','富时','央企','国企','产业','畜牧',
    '养殖','种植','渔业','种业','化肥','农药','服装','家电','造纸','包装','石油','天然气','电力','水务','燃气',
    '供热','固废','污水','风电','核电','水电','储能','氢能','生物质','充电桩','换电','锂电','钠电','固态','燃料电池',
    '电机','电控','轨道交通','航空航天','船舶','港口','机场','公路','铁路','物流','快递','仓储','供应链','贸易',
    '零售','电商','免税','餐饮','酒店','演艺','会展','体育','游戏','动漫','影视','音乐','广告','营销','家政','共享',
    '租赁','卫星','火箭','基因','干细胞','机器人','无人机','虚拟','增强','量子','纳米','石墨烯','超导','核聚变',
    '信创','电子','电信','5G','6G','AI','智能制造','工业','芯','数字','大数据','金融科技','区块链','元宇宙','碳中和',
]
_ETF_BROAD_PATTERNS = [
    r'(?:沪深)?300(?:ETF|指数|基金|[A-Z]|增|价值|成长|质量|ESG|红利|指增|增强)?$',
    r'^(?:中证)?500(?:ETF|指数|基金|质量|低波|价值|成长|增强)?$',
    r'^(?:中证)?1000(?:ETF|指数|基金|价值|成长|增强)?$',
    r'^(?:上证)?50(?:ETF|指数|基金|[A-Z])?$',
    r'^(?:上证)?180(?:ETF|指数|基金|[A-Z])?$',
    r'^创业板(?:ETF|指数|50)?$',
    r'^创50(?:ETF)?$',
    r'^(?:科创板|科创)(?:50|100|200)(?:ETF|指数|基金|[A-Za-z])?$',
    r'^(?:中证)?A500(?:ETF|基金|指数|龙头|添富|富国|华宝|中金|申万|银河|红利|增强|[A-Z])?$',
    r'^A500[EF]?$',
    r'^综指ETF$',
    r'^(?:上证|沪深|中证)综合(?:ETF|指数)?$',
    r'^AH300ETF$',
    r'^AH500ETF$',
    r'^A50ETF$',
    r'^双创50(?:ETF)?$',
]

def _is_broad_etf(name):
    n = str(name or "").strip()
    for kw in _ETF_SECTOR_KEYWORDS:
        if kw in n:
            return False
    for p in _ETF_BROAD_PATTERNS:
        if __import__("re").search(p, n):
            return True
    return False

def _trade_dates(n=60):
    dates = []
    d = datetime.now()
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return list(reversed(dates))

def f_etf_subscription():
    """宽基ETF净申赎：上交所ETF份额日环比，筛选宽基指数ETF。
    输出结构与 v6 ETF_SUBSCRIPTION 一致：{sh:[{date,date_raw,total_shares_bil,net_subscribe_bil}], update_time}
    """
    dates = _trade_dates(60)
    result = {"sh": [], "sh_all": [], "update_time": ""}
    prev_total = None
    prev_total_all = None
    for d in dates:
        try:
            df = get_ak().fund_etf_scale_sse(date=d)
            if df is None or len(df) == 0:
                continue
            # 基金份额字段名兼容
            share_col = "基金份额" if "基金份额" in df.columns else None
            if share_col is None:
                continue
            df_broad = df[df["基金简称"].apply(_is_broad_etf)]
            broad_shares = float(df_broad[share_col].sum()) if len(df_broad) else 0.0
            all_shares = float(df[share_col].sum())
            dt_fmt = f"{int(d[4:6])}/{int(d[6:8])}"
            dt_raw = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            entry = {"date": dt_fmt, "date_raw": dt_raw, "total_shares_bil": round(broad_shares / 1e8, 2)}
            if prev_total is not None:
                entry["net_subscribe_bil"] = round((broad_shares - prev_total) / 1e8, 2)
            else:
                entry["net_subscribe_bil"] = 0.0
            result["sh"].append(entry)
            prev_total = broad_shares

            entry_all = {"date": dt_fmt, "date_raw": dt_raw, "total_shares_bil": round(all_shares / 1e8, 2)}
            if prev_total_all is not None:
                entry_all["net_subscribe_bil"] = round((all_shares - prev_total_all) / 1e8, 2)
            else:
                entry_all["net_subscribe_bil"] = 0.0
            result["sh_all"].append(entry_all)
            prev_total_all = all_shares
        except Exception:
            pass
        time.sleep(0.15)
    if not result["sh"]:
        return None
    result["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"  ✅ 宽基ETF净申赎：{len(result['sh'])} 条")
    return result

def f_north_fund():
    # 北向资金：港交所 2024-05 后停止披露 top_buy，系统标「停止」
    return {"stopped": True, "note": "港交所 2024-05 后停止披露北向 top_buy，无实时数据"}

def f_market_fund_flow_data():
    """大盘资金流向时间轴：东方财富 push2his 日线接口。
    取上证指数(000001)主力资金净流入历史序列，覆盖今年以来到最近交易日。
    f52=主力净流入(元)，f62/f63=上证收盘/涨跌幅，f64/f65=深证收盘/涨跌幅。
    2026-08-05 改进：与远端/本地 baseline 合并，避免接口滞后时跨天塌缩丢失已有最新日期。
    """
    url = "http://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": "1.000001",
        "secid2": "0.399001",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    try:
        r = _requests.get(url, params=params, headers=_EM_HEADERS, timeout=20)
        text = r.text
        start = text.find("{")
        end = text.rfind(")")
        j = json.loads(text[start:end if end > 0 else None])
        klines = j.get("data", {}).get("klines", []) or []
    except Exception as e:
        print(f"  ⚠️ 大盘资金流向接口失败: {e}")
        klines = []

    # 先取已有 baseline：远端 main 优先（避免本地 raw_data 刚被清空），其次本地 raw_data
    baseline = _fetch_remote_raw("market_fund_flow_data.json") or {}
    if not baseline:
        try:
            local_path = RAW_DIR / "market_fund_flow_data.json"
            if local_path.exists():
                baseline = json.loads(local_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️ 读取本地 market_fund_flow_data baseline 失败: {e}")
            baseline = {}

    baseline_daily = {x["date"]: x for x in (baseline.get("daily") or [])}
    baseline_quote = baseline.get("sh_quote") or {}

    if not klines:
        if baseline_daily:
            print("  ⏭️ 大盘资金流向接口无返回，沿用 baseline")
            daily = [baseline_daily[d] for d in sorted(baseline_daily.keys())]
        else:
            return None
    else:
        daily = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            ds = parts[0].replace("-", "")
            # 参照 v6 fetch_market_fund_flow.py：存全 8 字段（date + net_yi + 特大/大/中/小单 + 主力%/小单%）
            def _f(idx):
                try: return round(float(parts[idx]) / 1e8, 2)
                except Exception: return 0.0
            def _pct(idx):
                try: return float(parts[idx])
                except Exception: return None
            entry = {"date": ds, "net_yi": _f(1)}
            if len(parts) >= 8:
                entry["super_large_yi"] = _f(2)
                entry["large_yi"]       = _f(3)
                entry["medium_yi"]      = _f(4)
                entry["small_yi"]       = _f(5)
                entry["main_pct"]       = _pct(6)
                entry["small_pct"]      = _pct(7)
            daily.append(entry)

        # 合并 baseline：保留接口未覆盖但 baseline 中已有的日期（通常无，但可防接口 truncated）
        seen = {x["date"] for x in daily}
        for ds, x in baseline_daily.items():
            if ds not in seen:
                daily.append(x)
        daily.sort(key=lambda x: x["date"])

    # 上证行情 quote：接口有则覆盖，无则沿用 baseline
    sh_quote = dict(baseline_quote)
    if klines:
        for line in klines:
            parts = line.split(",")
            if len(parts) < 15:
                continue
            ds = parts[0].replace("-", "")
            try:
                sh_quote[ds] = {"close": round(float(parts[11]), 2), "chg": round(float(parts[12]), 2)}
            except Exception:
                pass

    # 累计净值
    cum = 0.0
    cumulative = []
    for x in daily:
        cum += float(x.get("net_yi") or 0)
        cumulative.append({"date": x["date"], "cum_yi": round(cum, 2)})

    return {
        "daily": daily,
        "cumulative": cumulative,
        "market_net": daily[-1]["net_yi"] if daily else 0,
        "sh_quote": sh_quote,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "上证指数(000001)单日主力资金净流入滚动累加，来源东方财富push2his",
    }

def f_w52_high():
    # 新高广度信号：东方财富「历史新高」板块 BK0501（真实，可达）
    # 注：CN 网络无法访问真正的「52周新高」专用池(getTopicNewHighPool 返回非 JSON)，
    #     故以「历史新高」板块成分数作为市场新高广度信号（语义等价、真实可用）。
    # 东财板块接口单页硬上限 100 行，故总数取 data.total（真实值），TOP 展示取返回行。
    params = {"pn": "1", "pz": "500", "po": "1", "np": "1", "fltt": "2", "invt": "2",
              "ut": "b2884a393a59ad64002292a3e90d46a5", "fid": "f3",
              "fs": "b:BK0501", "fields": "f12,f14,f2,f3", "_": 1}
    r = _requests.get(f"{_EM_DELAY}/api/qt/clist/get", params=params,
                      headers=_EM_HEADERS, timeout=15).json()
    data = r.get("data") or {}
    rows = data.get("diff") or []
    if not rows:
        return None
    total = data.get("total") or len(rows)
    top_gainers = []
    for rr in rows[:15]:
        try:
            chg = round(float(rr.get("f3") or 0), 2)
        except Exception:
            chg = 0.0
        top_gainers.append({"name": rr.get("f14"), "code": rr.get("f12"), "chg": chg})
    return {
        "total": total,
        "top_gainers": top_gainers,
        "note": "东方财富「历史新高」板块成分数（真实新高广度信号）",
    }


def f_etf_daily_monitor():
    # ETF 日监控：全市场 ETF 当日主力净流入排名（T+1 盘后更新）
    # 数据源：akshare fund_etf_spot_em 含「主力净流入-净额」字段
    df = get_ak().fund_etf_spot_em()
    if df is None or df.empty:
        return None
    net_col = "主力净流入-净额" if "主力净流入-净额" in df.columns else None
    if net_col is None:
        # 字段缺失时退化为成交额排序，保证有数据而非空
        df2 = df.sort_values("成交额", ascending=False).head(20) if "成交额" in df.columns else df.head(20)
        return {"items": df2.to_dict(orient="records"), "note": "主力净流入字段缺失，退化为成交额排序"}
    df = df.copy()
    df[net_col] = pd.to_numeric(df[net_col], errors="coerce").fillna(0.0)
    df = df[df[net_col] != 0.0]  # 去掉无净流入数据的行（避免 nan 污染）
    if df.empty:
        return {"no_data": True, "note": "盘前无主力净流入数据，盘后 T+1 自动更新"}
    inflow = df.sort_values(net_col, ascending=False).head(10)
    outflow = df.sort_values(net_col, ascending=True).head(10)
    total_net = float(df[net_col].sum())
    return {
        "total_etf": int(len(df)),
        "total_net": total_net,
        "top_inflow": [{"name": r["名称"], "code": r["代码"], "net": float(r[net_col])} for _, r in inflow.iterrows()],
        "top_outflow": [{"name": r["名称"], "code": r["代码"], "net": float(r[net_col])} for _, r in outflow.iterrows()],
    }


def f_etf_pulse():
    # ETF 盘中异动：用 fund_etf_spot_em 实时行情筛「量比>1.2 的活跃 ETF」按量比排序
    # 注：本版 akshare 已移除 fund_etf_hist_em 等分钟线接口，故用实时快照的量比/涨跌幅表征异动
    df = get_ak().fund_etf_spot_em()
    if df is None or df.empty:
        return None
    vol_col = "量比" if "量比" in df.columns else None
    chg_col = "涨跌幅" if "涨跌幅" in df.columns else None
    amt_col = "成交额" if "成交额" in df.columns else None
    if vol_col is None and chg_col is None:
        return {"note": "异动字段（量比/涨跌幅）缺失", "etfs": []}
    df = df.copy()
    if vol_col:
        df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0.0)
    if chg_col:
        df[chg_col] = pd.to_numeric(df[chg_col], errors="coerce").fillna(0.0)
    if amt_col:
        df[amt_col] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0.0)
    # 未开盘检测：集合竞价前(<09:30)全市场量比/成交额均为 0，此时输出榜单毫无意义，
    # 直接回 no_data 让前端显示「未开盘」，避免展示一整屏 0.00 的假异动。
    has_vol = bool(vol_col) and float(df[vol_col].max()) > 0
    has_amt = bool(amt_col) and float(df[amt_col].max()) > 0
    if not has_vol and not has_amt:
        return {"no_data": True, "etfs": [],
                "note": "未开盘/集合竞价中，量比与成交额尚未产生，开盘后自动刷新"}

    # 优先筛量比>1.2 的异动；若无显著放量，退化为成交额 TOP（活跃度真实可比，
    # 不用量比排序——量比为 0 时排序结果等同于代码倒序，是无意义的噪声）
    if has_vol:
        hot = df[df[vol_col] > 1.2]
        if not hot.empty:
            base, sort_col, mode = hot, vol_col, "hot"
        else:
            base, sort_col, mode = df, (amt_col or vol_col), "amt"
    else:
        hot = df[df[chg_col].abs() > 2] if chg_col else df.iloc[0:0]
        if not hot.empty:
            base, sort_col, mode = hot, chg_col, "chg"
        else:
            base, sort_col, mode = df, (amt_col or chg_col), "amt"
    base = base.sort_values(sort_col, ascending=False).head(12)
    etfs = []
    for _, r in base.iterrows():
        etfs.append({
            "name": r["名称"], "code": r["代码"],
            "chg": float(r[chg_col]) if chg_col else 0.0,
            "vol": float(r[vol_col]) if vol_col else 0.0,
            "amount": float(r[amt_col]) if amt_col else 0.0,
        })
    note = {
        "hot": "盘中异动：量比>1.2 的放量 ETF（按量比排序）",
        "chg": "盘中异动：涨跌幅>2% 的 ETF",
        "amt": "盘中暂无显著放量，展示成交额最活跃 TOP12",
    }[mode]
    return {"etfs": etfs, "note": note}


def f_analyst_ratings():
    """分析师评级：akshare stock_analyst_rank_em（东财分析师排名 + 最新推荐个股）。
    输出结构兼容 update_v8.py 的 ANALYST_RATINGS 转换：
    {hot_stocks, latest_reports, upgrades, downgrades, new_coverage}"""
    ak = get_ak()
    result = {"hot_stocks": [], "latest_reports": [], "upgrades": [], "downgrades": [], "new_coverage": []}
    year = datetime.now().year

    # ① 分析师年度排名 → 提取 TOP 分析师最新推荐个股作为"热门"
    try:
        df = ak.stock_analyst_rank_em(year=str(year))
        if df is not None and len(df) > 0:
            cols = list(df.columns)
            # 动态匹配年份前缀的列名
            code_col = next((c for c in cols if "股票代码" in c), "")
            name_col = next((c for c in cols if "股票名称" in c), "")
            if not code_col:
                print("    ⚠️ 分析师排名: 未找到股票代码列")
            else:
                seen = set()
                for _, row in df.head(30).iterrows():
                    code = str(row.get(code_col, "")).strip()
                    name = str(row.get(name_col, "")).strip()
                    analyst = str(row.get("分析师名称", "") or "")
                    firm = str(row.get("分析师单位", "") or "")
                    idx_val = row.get("年度指数")
                    ret_12m = row.get("12个月收益率")
                    if not code or code in seen or code == "nan":
                        continue
                    seen.add(code)
                    entry = {
                        "code": code, "name": name,
                        "rating": f"TOP分析师推荐({analyst}/{firm})",
                        "report_count_1m": 1,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "org": firm,
                        "analyst": analyst,
                        "annual_index": idx_val,
                        "ret_12m": ret_12m,
                    }
                    result["hot_stocks"].append(entry)
                    result["latest_reports"].append(entry)
                print(f"    分析师排名: 获取 {len(result['hot_stocks'])} 只推荐股")
    except Exception as e:
        print(f"    ⚠️ 分析师排名获取失败: {e}")

    # ② 尝试获取个股研报明细（补充，失败不阻塞）
    try:
        # 取 hot_stocks 前 5 只的研报
        top_codes = [s["code"] for s in result["hot_stocks"][:5]]
        for code in top_codes[:3]:  # 限 3 只防超时
            try:
                rdf = ak.stock_research_report_em(symbol=code)
                if rdf is not None and len(rdf) > 0:
                    stock_name = next((s["name"] for s in result["hot_stocks"] if s["code"] == code), "")
                    for _, rrow in rdf.head(2).iterrows():
                        title = str(rrow.get("标题", ""))[:40]
                        result["new_coverage"].append({
                            "code": code,
                            "name": stock_name,
                            "rating": "研报覆盖",
                            "report_count_1m": 1,
                            "date": str(rrow.get("发布日期", ""))[:10] if pd.notna(rrow.get("发布日期")) else "",
                            "title": title,
                        })
            except Exception:
                pass
        print(f"    研报明细: 补充 {len(result['new_coverage'])} 条")
    except Exception as e:
        print(f"    ⚠️ 研报明细跳过: {e}")

    return result


def f_experiment():
    # 实验选股调试专区（三重选股）：用全市场个股实时快照(em_clist, 东财push2delay)做透明技术面初筛。
    # 产生 金钻起涨/波段多头/主力进场/主力出货/三重选股 五个名单，供前端「⑤ 三重选股补充候选」渲染。
    # 说明：纯实时快照初筛（非历史回测），验证中请勿依赖。
    desc = em_clist(_IND_FS, "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=5000, po="1")
    asc = em_clist(_IND_FS, "f12,f14,f2,f3,f6,f62,f184", fid="f62", pz=5000, po="0")
    by_code = {}
    for r in desc + asc:
        c = str(r.get("f12"))
        if c in by_code:
            continue
        try:
            by_code[c] = {
                "code": c, "name": r.get("f14"),
                "chg": round(float(r.get("f3") or 0), 2),
                "net": round(float(r.get("f62") or 0) / 1e8, 2),
                "netpct": round(float(r.get("f184") or 0), 2),
            }
        except Exception:
            continue
    stocks = list(by_code.values())
    if not stocks:
        return None

    def pick(pred, key, n=15):
        return [{"code": s["code"], "name": s["name"]}
                for s in sorted([s for s in stocks if pred(s)], key=key, reverse=True)[:n]]

    main_in = pick(lambda s: s["net"] > 0 and s["chg"] > 0, lambda s: s["net"])            # 主力进场
    main_out = pick(lambda s: s["net"] < 0 and s["chg"] < 0, lambda s: s["net"])           # 主力出货
    jin_zuan = pick(lambda s: 3 <= s["chg"] <= 9.8 and s["net"] > 0, lambda s: s["net"])  # 金钻起涨
    bo_duan = pick(lambda s: 1 <= s["chg"] <= 5 and s["net"] > 0, lambda s: s["chg"])      # 波段多头
    triple = [s for s in jin_zuan if s["code"] in {x["code"] for x in main_in}]             # 三重=金钻∩主力进场
    return {
        "triple_select": {
            "lists": {
                "金钻起涨": jin_zuan,
                "波段多头": bo_duan,
                "主力进场": main_in,
                "主力出货": main_out,
                "三重选股": triple,
            },
            "signals": {
                "金钻起涨": len(jin_zuan), "波段多头": len(bo_duan),
                "主力进场": len(main_in), "主力出货": len(main_out), "三重选股": len(triple),
            },
        },
        "note": "实验区：全市场个股实时快照初筛(东财push2delay)。金钻起涨=涨幅3~9.8%且主力净流入; 波段多头=涨幅1~5%且净流入; "
                "主力进场=净流入且上涨; 主力出货=净流出且下跌; 三重=金钻∩主力进场。验证中请勿依赖。",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def f_market_alerts():
    """市场预警（全市场异动速览）：接入盘中刷新。
    复用孤儿模块 algorithms/fetch_orphan_market_alerts.py（原 v6 fetch_market_alerts.py 移植）。
    盘中每30分钟刷新一次，避免长期停更到凌晨的历史残留值。"""
    import subprocess as _sp
    script = ROOT / "algorithms" / "fetch_orphan_market_alerts.py"
    if not script.exists():
        print(f"  ⚠️ 未找到 {script}")
        return None
    print(f"  🔄 调用市场预警孤儿模块: {script.name}")
    try:
        r = _sp.run([sys.executable, str(script)], cwd=str(ROOT),
                    capture_output=True, text=True, timeout=300)
    except Exception as e:
        raise RuntimeError(f"fetch_orphan_market_alerts 调用异常: {e}")
    if r.returncode != 0:
        raise RuntimeError(f"fetch_orphan_market_alerts exit {r.returncode}: {r.stderr[:160]}")
    p = RAW_DIR / "market_alerts.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def f_v8_cal(today=None):
    """重要事件日历：自动生成【当前月】日历。
    - 频率控制：仅在每月 1~3 号执行完整生成；其余日期直接返回已有缓存（v8_cal.json），
      避免每日无意义重跑。每月初跑一次即可（规则事件按公式算，财报日期预估季度更新）。
    - 自动切月：永远渲染「今天所在月」，8/1 起自然显示 8 月。
    - 自动标今天：today 高亮每天动态算。
    - 规则事件自动算：股指期货/ETF期权交割(第3周五/第4周三)、LPR(20日)、A50交割(倒数第2工作日)、
      FOMC(2026年度表)、中国宏观数据日(PMI/CPI/工业增加值，约)、港股/美股休市(2026假期表)。
    - 公司财报：内嵌七姐妹+NVDA+半导体链+亚太+欧股+华为（从 v6 fetch_nt_data.py 移植，
      季度预估日期，每年初校准一次）。
    today 参数仅用于测试（默认取系统当天）。
    """
    import calendar as _cal
    from datetime import date, datetime as _dt
    today = today or date.today()

    # ── 频率控制：非月初(1~3号)且非周六则读缓存 ──
    # 周六作为 T+1 周度/月度统一刷新窗口，强制重建日历（覆盖月度事件调整/财报日期修正）
        # ── 频率控制（2026-08-02 修）：缓存里"今天的 today 标记"是否还在 ──
    # 重建条件（满足任一即重建）：
    #   1) 缓存不存在
    #   2) 缓存月份 ≠ 今天所在月（自然切月）
    #   3) 缓存 update_time 是昨天或更早
    #   4) 缓存 weeks 里没有任何 day 标 today=true 且 num==今天的日子数
    # 否则（缓存新鲜 + 今天是缓存里的 today）→ 直接返回缓存
    # 修前 bug：「day>3 且非周六读缓存」漏掉周日-周六之间隔一整天的边角，
    #  导致 8/2（周日）显示 8/1（周六）数据，today 永远停在 1 号。
    cache_file = RAW_DIR / "v8_cal.json"
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cache_month = cached.get("month", "")
            today_yyyymm = f"{today.year}-{today.month:02d}"
            cache_ut = cached.get("update_time", "")
            cache_has_today = any(
                d.get("today") and d.get("num") == today.day
                for w in cached.get("weeks", []) for d in w.get("days", [])
            )
            cache_stale_day = False
            try:
                if cache_ut:
                    cache_dt = _dt.strptime(cache_ut, "%Y-%m-%d %H:%M:%S")
                    cache_stale_day = cache_dt.date() < today
            except Exception:
                cache_stale_day = True
            if (cache_month == today_yyyymm
                    and not cache_stale_day
                    and cache_has_today):
                print(f"    日历: 缓存新鲜（{cache_ut} · today={today.day} 已标记），直接返回")
                return cached
            else:
                reasons = []
                if cache_month != today_yyyymm: reasons.append(f"月份切换 {cache_month}->{today_yyyymm}")
                if cache_stale_day: reasons.append(f"update_time {cache_ut} 早于今天")
                if not cache_has_today: reasons.append(f"缓存内无 today={today.day} 标记")
                print(f"    日历: 需重建（{'; '.join(reasons)}）")
        except Exception as e:
            print(f"    日历: 缓存解析失败 {e}，重建")

    y, m = today.year, today.month
    last_day = _cal.monthrange(y, m)[1]

    # 2026 港股/美股休市（手工维护，需每年更新；仅供参考）
    HK_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,2,17):"农历新年", (2026,2,18):"农历新年", (2026,2,19):"农历新年",
        (2026,4,3):"耶稣受难节", (2026,4,6):"复活节星期一", (2026,5,1):"劳动节",
        (2026,5,25):"佛诞", (2026,6,19):"端午节", (2026,7,1):"香港回归纪念日",
        (2026,9,25):"中秋节", (2026,10,1):"国庆日", (2026,10,19):"重阳节",
        (2026,12,25):"圣诞节", (2026,12,26):"圣诞节翌日",
    }
    US_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,1,19):"马丁路德金日", (2026,2,16):"总统日",
        (2026,4,3):"耶稣受难节", (2026,5,25):"阵亡将士纪念日", (2026,6,19):"六月节",
        (2026,9,7):"劳动节", (2026,11,26):"感恩节", (2026,12,25):"圣诞节",
    }
    SG_HOLIDAYS_2026 = {
        (2026,1,1):"元旦", (2026,2,17):"农历新年", (2026,3,31):"开斋节",
        (2026,5,1):"劳动节", (2026,5,25):"卫塞节", (2026,8,9):"国庆日",
        (2026,10,22):"屠妖节", (2026,12,25):"圣诞节",
    }
    # FOMC 2026 议息会议（月, 第1天, 决议日）
    FOMC_2026 = [(1,27,28),(3,17,18),(4,28,29),(6,9,10),(7,28,29),(9,15,16),(10,27,28),(12,15,16)]

    def nth_weekday(yy, mm, n, wd):
        d = date(yy, mm, 1)
        off = (wd - d.weekday()) % 7
        return d + timedelta(days=off + 7 * (n - 1))

    def last_weekday(yy, mm, n_from_end):
        d = date(yy, mm, _cal.monthrange(yy, mm)[1])
        cnt = 0
        while True:
            if d.weekday() < 5:
                cnt += 1
                if cnt == n_from_end:
                    return d
            d -= timedelta(days=1)

    def shift_weekend(d):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    ev = {}
    def add(day, text, cls, released=None):
        if 1 <= day <= last_day:
            rel = (day < today.day) if released is None else bool(released)
            ev.setdefault(day, []).append({"text": text, "cls": cls, "released": rel})

    # 期货/期权交割（每月第3周五）
    d3 = nth_weekday(y, m, 3, 4)
    if (d3.year, d3.month) == (y, m):
        add(d3.day, "中金所IF/IH/IC/IM股指期货交割", "future")
        add(d3.day, "中金所股指期权到期", "option")
    # ETF期权（每月第4周三）
    d4 = nth_weekday(y, m, 4, 2)
    if (d4.year, d4.month) == (y, m):
        add(d4.day, "上交所/深交所ETF期权最后交易日", "option")
    # LPR（每月20日，周末顺延）
    dl = shift_weekend(date(y, m, 20))
    if dl.month == m:
        add(dl.day, "LPR利率报价（1年/5年以上）", "cb")
    # 富时A50交割（每月倒数第2工作日）
    da = last_weekday(y, m, 2)
    if da.month == m:
        add(da.day, "富时A50交割日", "a50")
    # FOMC
    for (fm, d1, d2) in FOMC_2026:
        if fm == m:
            add(d1, "🇺🇸 FOMC议息会议第1天", "fomc")
            add(d2, "🇺🇸 FOMC利率决议", "fomc")
    # 宏观数据日（约）
    dc = shift_weekend(date(y, m, 1))
    if dc.month == m:
        add(dc.day, "🇨🇳 财新制造业PMI", "caixin")
    dp = shift_weekend(date(y, m, 10))
    if dp.month == m:
        add(dp.day, "🇨🇳 CPI/PPI数据", "data2")
    dg = shift_weekend(date(y, m, 15))
    if dg.month == m:
        add(dg.day, "🇨🇳 工业增加值/社零/固投", "data")
    dpm = last_weekday(y, m, 1)
    if dpm.month == m:
        add(dpm.day, "🇨🇳 官方制造业PMI", "data")
    # 中国进出口数据（每月约7-10号，遇周末顺延；海关公布）
    de = shift_weekend(date(y, m, 7))
    if de.month == m:
        add(de.day, "🇨🇳 中国出口", "data")
    # 美国非农（每月第一个周五）
    dnf = nth_weekday(y, m, 1, 4)
    if dnf.month == m:
        add(dnf.day, "🇺🇸 美国非农", "us")
    # 美国CPI（每月第二个周三，约10-15号）
    dcpi = nth_weekday(y, m, 2, 2)
    if dcpi.month == m:
        add(dcpi.day, "🇺🇸 美国CPI", "us")
    # MLF操作（每月15日左右，遇周末顺延）
    dmlf = shift_weekend(date(y, m, 15))
    if dmlf.month == m:
        add(dmlf.day, "🇨🇳 MLF操作", "cb")
    # A股中报披露截止（8月31日）
    if m == 8:
        add(31, "🇨🇳 中报披露截止", "ipo")
    # 港股/美股休市
    for (yy, mm2, dd), name in HK_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇭🇰 港股休市（{name}）", "hk")
    for (yy, mm2, dd), name in US_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇺🇸 美股休市（{name}）", "us")
    for (yy, mm2, dd), name in SG_HOLIDAYS_2026.items():
        if (yy, mm2) == (y, m):
            add(dd, f"🇸🇬 SG公假（{name}）", "sg")

    # ════════════════════════════════════════
    #  公司财报（从 v6 fetch_nt_data.py 移植）
    #  季度预估日期，每年初校准一次即可
    # ════════════════════════════════════════
    ym_str = f"{y}-{m:02d}"

    # ── 美股七姐妹（AAPL/MSFT/GOOGL/AMZN/META/TSLA）──
    _magnificent7 = [
        ('2026-01-28','苹果Q1财报'), ('2026-04-29','苹果Q2财报'),
        ('2026-07-29','苹果Q3财报'), ('2026-10-28','苹果Q4财报'),
        ('2027-01-27','苹果Q1财报'), ('2027-04-28','苹果Q2财报'),
        ('2027-07-28','苹果Q3财报'),
        ('2026-01-27','微软Q2财报'), ('2026-04-29','微软Q3财报'),
        ('2026-07-29','微软Q4财报'), ('2026-10-27','微软Q1财报'),
        ('2027-01-26','微软Q2财报'), ('2027-04-28','微软Q3财报'),
        ('2027-07-28','微软Q4财报'),
        ('2026-02-03','谷歌Q4财报'), ('2026-04-28','谷歌Q1财报'),
        ('2026-07-28','谷歌Q2财报'), ('2026-10-27','谷歌Q3财报'),
        ('2027-02-02','谷歌Q4财报'), ('2027-04-27','谷歌Q1财报'),
        ('2027-07-27','谷歌Q2财报'),
        ('2026-01-29','亚马逊Q4财报'), ('2026-04-29','亚马逊Q1财报'),
        ('2026-07-30','亚马逊Q2财报'), ('2026-10-28','亚马逊Q3财报'),
        ('2027-01-28','亚马逊Q4财报'), ('2027-04-28','亚马逊Q1财报'),
        ('2027-07-29','亚马逊Q2财报'),
        ('2026-01-28','Meta Q4财报'), ('2026-04-29','Meta Q1财报'),
        ('2026-07-29','Meta Q2财报'), ('2026-10-28','Meta Q3财报'),
        ('2027-01-27','Meta Q4财报'), ('2027-04-28','Meta Q1财报'),
        ('2027-07-28','Meta Q2财报'),
        ('2026-01-27','特斯拉Q4财报'), ('2026-04-21','特斯拉Q1财报'),
        ('2026-07-21','特斯拉Q2财报'), ('2026-10-20','特斯拉Q3财报'),
        ('2027-01-26','特斯拉Q4财报'), ('2027-04-20','特斯拉Q1财报'),
        ('2027-07-20','特斯拉Q2财报'),
    ]
    for nd, nt in _magnificent7:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 英伟达 ──
    _nvidia = [
        ('2026-02-25','英伟达Q4财报'), ('2026-05-21','英伟达Q1财报+指引'),
        ('2026-08-20','英伟达Q2财报+指引'), ('2026-11-18','英伟达Q3财报+指引'),
        ('2027-02-24','英伟达Q4财报'), ('2027-05-19','英伟达Q1财报+指引'),
        ('2027-08-18','英伟达Q2财报+指引'), ('2027-11-17','英伟达Q3财报+指引'),
    ]
    for nd, nt in _nvidia:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 美股半导体：美光/博通/CSP ──
    _semi = [
        ('2026-01-07','美光Q1财报'), ('2026-03-25','美光Q2财报'),
        ('2026-06-24','美光Q3财报'), ('2026-09-29','美光Q4财报'),
        ('2027-01-06','美光Q1财报'), ('2027-03-24','美光Q2财报'),
        ('2027-06-29','美光Q3财报'), ('2027-09-28','美光Q4财报'),
        ('2026-01-28','博通Q4财报'), ('2026-04-29','博通Q1财报'),
        ('2026-07-29','博通Q2财报'), ('2026-10-28','博通Q3财报'),
        ('2027-01-27','博通Q4财报'), ('2027-04-28','博通Q1财报'),
        ('2027-07-28','博通Q2财报'), ('2027-10-27','博通Q3财报'),
        ('2026-08-12','CSP Q3财报'), ('2026-12-09','CSP Q4财报'),
        ('2027-02-10','CSP Q1财报'), ('2027-05-12','CSP Q2财报'),
        ('2027-08-11','CSP Q3财报'), ('2027-12-08','CSP Q4财报'),
    ]
    for nd, nt in _semi:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "us_earnings")

    # ── 韩国：三星/SK海力士 ──
    _kr = [
        ('2026-01-27','三星Q4财报'), ('2026-04-28','三星Q1财报'),
        ('2026-07-28','三星Q2财报'), ('2026-10-27','三星Q3财报'),
        ('2027-01-26','三星Q4财报'), ('2027-04-27','三星Q1财报'),
        ('2027-07-27','三星Q2财报'),
        ('2026-01-28','SK海力士Q4财报'), ('2026-04-29','SK海力士Q1财报'),
        ('2026-07-29','SK海力士Q2财报'), ('2026-10-28','SK海力士Q3财报'),
        ('2027-01-27','SK海力士Q4财报'), ('2027-04-28','SK海力士Q1财报'),
        ('2027-07-28','SK海力士Q2财报'),
    ]
    for nd, nt in _kr:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "kr")

    # ── 日本：铠侠 ──
    _jp = [
        ('2026-02-12','铠侠Q3财报'), ('2026-05-13','铠侠Q4财报'),
        ('2026-08-12','铠侠Q1财报'), ('2026-11-11','铠侠Q2财报'),
        ('2027-02-10','铠侠Q3财报'), ('2027-05-12','铠侠Q4财报'),
        ('2027-08-11','铠侠Q1财报'), ('2027-11-10','铠侠Q2财报'),
    ]
    for nd, nt in _jp:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "jp")

    # ── 台湾：台积电 ──
    _tw = [
        ('2026-01-15','台积电Q4财报'), ('2026-04-16','台积电Q1财报'),
        ('2026-07-16','台积电Q2财报'), ('2026-10-15','台积电Q3财报'),
        ('2027-01-14','台积电Q4财报'), ('2027-04-15','台积电Q1财报'),
        ('2027-07-15','台积电Q2财报'),
    ]
    for nd, nt in _tw:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "tw")

    # ── 欧洲：ASML ──
    _eu = [
        ('2026-01-28','ASML Q4财报'), ('2026-04-22','ASML Q1财报'),
        ('2026-07-22','ASML Q2财报'), ('2026-10-21','ASML Q3财报'),
        ('2027-01-27','ASML Q4财报'), ('2027-04-21','ASML Q1财报'),
        ('2027-07-21','ASML Q2财报'), ('2027-10-20','ASML Q3财报'),
    ]
    for nd, nt in _eu:
        if nd.startswith(ym_str):
            add(int(nd[-2:]), nt, "eu")

    # ── 华为重要事件 ──
    _huawei = [
        (2026, 3, 20, '华为P系列发布会'),
        (2026, 6, 12, '华为开发者大会HDC·Day1'),
        (2026, 6, 13, '华为开发者大会HDC·Day2'),
        (2026, 6, 14, '华为开发者大会HDC·Day3'),
        (2026, 9, 10, '华为Mate系列发布会'),
        (2027, 3, 20, '华为P系列发布会'),
        (2027, 6, 12, '华为开发者大会HDC·Day1'),
        (2027, 6, 13, '华为开发者大会HDC·Day2'),
        (2027, 6, 14, '华为开发者大会HDC·Day3'),
        (2027, 9, 10, '华为Mate系列发布会'),
    ]
    for hy, hm, hd, ht in _huawei:
        if (hy, hm) == (y, m):
            add(hd, ht, "appl")

    # 合并 seed（手工一次性事件：仅限非财报类补充，财报已内嵌上方）
    seed_path = ROOT / "calendar_seed.json"
    if seed_path.exists():
        try:
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            items = seed.get("events", seed) if isinstance(seed, dict) else seed
            for item in items:
                ds = str(item.get("date", ""))
                try:
                    yy, mm2, dd = map(int, ds.split("-"))
                except Exception:
                    continue
                if (yy, mm2) == (y, m):
                    add(dd, item.get("text", ""), item.get("cls", "data"), item.get("released", False))
        except Exception as e:
            print(f"    ⚠️ calendar_seed.json 解析失败: {e}")

    # 构建周网格（周一对齐，覆盖整月）
    first = date(y, m, 1)
    grid_start = first - timedelta(days=first.weekday())
    weeks = []
    cur = grid_start
    wno = 1
    while cur <= date(y, m, last_day):
        days = []
        for i in range(7):
            d = cur + timedelta(days=i)
            dim = (d.month != m)
            days.append({
                "num": d.day,
                "dim": dim,
                "today": (d == today),
                "events": ev.get(d.day, []) if not dim else [],
            })
        wk_end = cur + timedelta(days=6)
        weeks.append({
            "no": str(wno),
            "dates": f"{cur.month}/{cur.day}-{wk_end.month}/{wk_end.day}",
            "days": days,
        })
        cur += timedelta(days=7)
        wno += 1

    legend = [
        {"title":"重要政策","color":"#c62828","desc":"中国政府/监管机构发布的重大政策、法规、规划等"},
        {"title":"央行/LPR","color":"#1565c0","desc":"央行货币政策、利率决议、LPR报价等"},
        {"title":"中国数据","color":"#f57f17","desc":"国家统计局/央行发布的宏观经济数据"},
        {"title":"财报截止","color":"#673ab7","desc":"A股财报披露法定截止日"},
        {"title":"期权交割","color":"#00838f","desc":"各交易所期权合约到期日"},
        {"title":"期货交割","color":"#1d6f42","desc":"期货合约最后交易日"},
        {"title":"A50交割","color":"#e91e63","desc":"新加坡富时A50期货交割日，外资对冲A股关键窗口"},
        {"title":"港股休市","color":"#ef5350","desc":"香港交易所休市日"},
        {"title":"台股财报","color":"#ff9800","desc":"台股关注股票"},
        {"title":"苹果/华为","color":"#37474f","desc":"两大科技巨头新品发布/重要财报"},
        {"title":"FOMC","color":"#9c27b0","desc":"美联储货币政策会议"},
        {"title":"美股休市","color":"#42a5f5","desc":"NYSE/Nasdaq休市日"},
        {"title":"美股财报","color":"#66bb6a","desc":"美股关注股票"},
        {"title":"欧股财报","color":"#26a69a","desc":"欧股关注股票"},
        {"title":"日股财报","color":"#ab47bc","desc":"日股关注股票"},
        {"title":"韩股财报","color":"#00acc1","desc":"韩股关注股票"},
        {"title":"SG公假","color":"#8e24aa","desc":"新加坡公共假期"},
        {"title":"财新PMI","color":"#5c6bc0","desc":"财新PMI月度数据"},
    ]

    print(f"    日历: {y}年{m}月, {len(weeks)}周, 事件日 {len(ev)} 天")
    return {
        "month": f"{y}年{m}月",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "legend": legend,
        "weeks": weeks,
    }


def main(category=None, only=None):
    print(f"=== v8 云端抓取开始 {datetime.now().isoformat(timespec='seconds')} "
          f"category={category or 'all'} ===")

    # 假期/周末冻结：盘中/盘后/盘前（非周六T+1）遇到非交易日时跳过，保留上一交易日收盘数据
    today = datetime.now().date()
    is_saturday = today.weekday() == 5
    if category in ("intraday", "post_close") and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日，{category} 跳过，保留上一交易日收盘数据")
        return 0
    if category == "premarket" and not is_saturday and not _is_trading_day(today):
        print(f"⏸️ 今日 {today} 非A股交易日且非周六T+1，premarket 跳过")
        return 0

    # 分时段清理：只删除本次任务类别的 raw_data，避免盘中任务把盘前/盘后数据清掉
    target_vars = None
    if category == "all":
        target_vars = set(CATEGORY_MAP.keys())
        print(f"🎯 全量兜底模式，涉及 {len(target_vars)} 个变量")
    elif category:
        target_vars = {var for var, cat in CATEGORY_MAP.items() if cat == category}
        if not target_vars:
            print(f"⚠️ 未知 category={category}，无任务可执行")
            return 0
        print(f"🎯 目标类别 {category}，涉及 {len(target_vars)} 个变量")
    else:
        print("🎯 全量模式，执行全部 cloud_fetch 模块")

    if only:
        target_vars = {only}
        print(f"🎯 --only 模式，仅执行 {only}")

    cleaned = 0

    # 🔧 盘后（15:30）额外补抓 ETF_DAILY_MONITOR（T+1 日监控收盘后定稿，配合盘中实时卡）
    if category == "post_close" and target_vars is not None:
        target_vars.add("ETF_DAILY_MONITOR")
    # 🔧 盘前（08:25）额外补抓 MARKET_FUND_FLOW_DATA（日频资金流时间轴，防止 15:30 post_close 漏跑导致滞后一天）
    if category == "premarket" and target_vars is not None:
        target_vars.add("MARKET_FUND_FLOW_DATA")
    # 🔧 盘中额外补抓 CRISIS_DATA（危机温度计实时刷新，盘前仅一次不够）
    if category == "intraday" and target_vars is not None:
        target_vars.add("CRISIS_DATA")

    if only:
        print("  ⏭️ --only 模式，跳过 raw_data 清理（保留其他时段数据）")
    else:
        for old in RAW_DIR.glob("*.json"):
            if category:
                # 只清理属于当前 category 的文件
                var_for_file = None
                for var, fname in VAR_TO_RAW.items():
                    if fname == old.name:
                        var_for_file = var
                        break
                if var_for_file not in target_vars:
                    continue
            try:
                old.unlink()
                cleaned += 1
            except Exception as e:
                print(f"  ⚠️  清理旧文件失败 {old.name}: {e}")
        if cleaned:
            print(f"  🧹 已清理 {cleaned} 个旧 raw_data/*.json")

    # 任务列表：顺序影响下游构建，保持原有顺序
    def f_sh_sz_history():
        """沪深两市每日成交额历史 + 全市场涨跌家数（量能对比图 / 涨跌家数图）。

        成交额：用 akshare stock_zh_index_daily_em（东财指数日线，含成交额）替代被 WAF 拦截的
               push2his 接口；自动识别单位（元→亿元），避免 10000 倍误差。
        涨跌家数：用 akshare stock_zh_a_spot_em 全市场快照统计 涨/跌/平。
        历史序列从 raw_data（优先）/ data/SH_SZ_HISTORY.js（回退）继承，仅更新/追加最近交易日，
        避免每次全删 raw_data 后序列断裂。
        """
        import re
        import akshare as ak

        now = datetime.now()
        today_md = f"{now.month}/{now.day}"
        is_today_trade = _is_trading_day()

        # ---- 读取历史基线（权威源 = 远端 main raw_data，避免跨天塌缩）----
        baseline = {}
        # 1) 优先远端 main 的 raw_data/sh_sz_history.json（追加型序列的权威基线，根治每日丢一天）
        remote = _fetch_remote_raw("sh_sz_history.json")
        if remote and isinstance(remote, dict) and (remote.get("daily_stats") or remote.get("amount_history")):
            baseline = remote
            print(f"  📥 远端基线命中：daily_stats={len(remote.get('daily_stats') or [])} 条 / amount_history={len(remote.get('amount_history') or [])} 条")
        # 2) 回退：本地 raw_data（intraday 清理后通常不存在，但全量兜底时可能有）
        if not baseline:
            raw_path = RAW_DIR / "sh_sz_history.json"
            if raw_path.exists():
                try:
                    baseline = json.loads(raw_path.read_text(encoding="utf-8"))
                except Exception:
                    baseline = {}
        # 3) 回退：已构建的 data/SH_SZ_HISTORY.js
        if not baseline:
            js_path = ROOT / "data" / "SH_SZ_HISTORY.js"
            if js_path.exists():
                try:
                    txt = js_path.read_text(encoding="utf-8")
                    i = txt.find("=")
                    j = txt.rfind(";")
                    if i != -1 and j != -1 and j > i:
                        baseline = json.loads(txt[i + 1:j].strip())
                except Exception:
                    baseline = {}

        # ---- 成交额历史（akshare 指数日线）----
        amount_history = []
        try:
            amap = {"sh": {}, "sz": {}}
            for key, sym in (("sh", "sh000001"), ("sz", "sz399001")):
                df = ak.stock_zh_index_daily_em(symbol=sym)
                # akshare 不同指数返回列名可能为中文或英文，做兼容
                date_col = next((c for c in df.columns if c in ("日期", "date")), None)
                amount_col = next((c for c in df.columns if c in ("成交额", "amount")), None)
                if not date_col or not amount_col:
                    print(f"  ⚠️ {sym} 日线列名异常，跳过")
                    continue
                for _, row in df.iterrows():
                    ds = str(row[date_col])
                    mm = str(int(ds[5:7])); dd = str(int(ds[8:10]))
                    try:
                        amt = float(row[amount_col])
                        if amt > 1e10:        # 元 → 亿元
                            amt = amt / 1e8
                        amt = round(amt, 1)
                    except Exception:
                        continue
                    amap[key][f"{mm}/{dd}"] = amt
            dates = sorted(set(amap["sh"]) & set(amap["sz"]))
            if dates:
                window = dates[-130:]
                amount_history = [{
                    "date": d,
                    "sh_amount": amap["sh"].get(d, 0.0),
                    "sz_amount": amap["sz"].get(d, 0.0),
                    "total": round(amap["sh"].get(d, 0.0) + amap["sz"].get(d, 0.0), 1),
                } for d in window]
            else:
                amount_history = baseline.get("amount_history") or []
        except Exception as ex:
            print(f"  ⚠️ 沪深成交额获取失败({ex})，沿用历史序列")
            amount_history = baseline.get("amount_history") or []

        # ---- 盘中/收盘补充今日成交额（优先用已抓取的 index_quotes.json，避免 akshare spot 单位异常）----
        # index_quotes.json 由同一次 run 中先执行的 INDEX_QUOTES 任务写入，来源为东财 push2delay，
        # 与前端指数卡片同源，时间和数值更可靠。
        if is_today_trade:
            try:
                idx_path = RAW_DIR / "index_quotes.json"
                idx_data = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
                by_code = {it["code"]: it for it in idx_data.get("items", [])}
                sh_amt = float(by_code.get("000001", {}).get("amount") or 0)
                sz_amt = float(by_code.get("399001", {}).get("amount") or 0)
                if sh_amt > 0 and sz_amt > 0:
                    total_amt = round(sh_amt + sz_amt, 1)
                    rec = {"date": today_md, "sh_amount": round(sh_amt, 1), "sz_amount": round(sz_amt, 1), "total": total_amt}
                    if amount_history and amount_history[-1].get("date") == today_md:
                        amount_history[-1] = rec
                    else:
                        amount_history.append(rec)
                    amount_history = amount_history[-130:]
                    print(f"  ✅ 盘中补充今日成交额 {today_md}: 上证{sh_amt:.1f}亿 / 深证{sz_amt:.1f}亿 / 合计{total_amt:.1f}亿（来源：index_quotes）")
                else:
                    print(f"  ⚠️ index_quotes 缺少今日成交额，沿用日线序列")
            except Exception as ex:
                print(f"  ⚠️ 盘中补充成交额失败({ex})，沿用日线序列")

        # ---- 涨跌家数：沪市 + 深市（与 AI市场速览 口径一致）----
        # index_quotes.json 已含 000001/399001 的 f104/f105/f106，直接读取求和，避免再调 ulist。
        ds_hist = baseline.get("daily_stats") or []
        if is_today_trade:
            try:
                idx_path = RAW_DIR / "index_quotes.json"
                idx_data = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
                by_code = {it["code"]: it for it in idx_data.get("items", [])}
                sh = by_code.get("000001", {})
                sz = by_code.get("399001", {})
                up = int(sh.get("up") or 0) + int(sz.get("up") or 0)
                down = int(sh.get("down") or 0) + int(sz.get("down") or 0)
                flat = int(sh.get("flat") or 0) + int(sz.get("flat") or 0)
                if up + down + flat > 0:
                    rec = {"date": today_md, "up": up, "down": down, "flat": flat}
                    if ds_hist and ds_hist[-1].get("date") == today_md:
                        ds_hist[-1] = rec
                    else:
                        ds_hist.append(rec)
                    ds_hist = ds_hist[-120:]
                    print(f"  ✅ 盘中补充今日涨跌家数 {today_md}: 涨{up}/跌{down}/平{flat}（沪市+深市）")
                else:
                    print(f"  ⚠️ index_quotes 缺少涨跌家数，沿用历史序列")
            except Exception as ex:
                print(f"  ⚠️ 涨跌家数获取失败({ex})，沿用历史序列")
        else:
            print(f"  ⏸️ 今日非交易日，涨跌家数/成交额不追加新记录")

        amount_last_date = amount_history[-1].get("date") if amount_history else ""
        up_down_last_date = ds_hist[-1].get("date") if ds_hist else ""

        return {
            "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "amount_history": amount_history,
            "up_down": ds_hist,  # 同步为最新涨跌家数序列（与 daily_stats 一致）
            "daily_stats": ds_hist,
            "amount_last_date": amount_last_date,
            "up_down_last_date": up_down_last_date,
        }

    tasks = [
        ("ETF_INTRADAY_HEAT", f_etf_intraday_heat),
        ("SECTOR_FUND_FLOW", f_sector_fund_flow),
        ("INDEX_QUOTES", f_index_quotes),
        ("CONCEPT_RANKING", f_concept_ranking),
        ("IPO_DATA", f_ipo_data),
        ("MARGIN_DATA", f_margin_data),
        ("CFFEX_HOLDINGS", f_cffex_holdings),
        ("MACRO_DATA", f_macro_data),
        ("CRISIS_DATA", f_crisis_data),
        ("HERDING_DATA", f_herding_data),
        ("LIMIT_UP_HEATMAP", f_limit_up_heatmap),
        ("CAPITAL_FLOW_DATA", f_capital_flow_data),
        ("ETF_SUBSCRIPTION", f_etf_subscription),
        ("NORTH_FUND", f_north_fund),
        ("MARKET_FUND_FLOW_DATA", f_market_fund_flow_data),
        ("W52_HIGH", f_w52_high),
        ("ETF_PULSE", f_etf_pulse),
        ("ETF_DAILY_MONITOR", f_etf_daily_monitor),
        ("ANALYST_RATINGS", f_analyst_ratings),
        ("EXPERIMENT", f_experiment),
        ("V8_CAL", f_v8_cal),
        ("CANDIDATE_QUOTES", f_candidate_quotes),
        ("SH_SZ_HISTORY", f_sh_sz_history),
        ("JUDGMENT_DATA", f_judgment),
        ("MACRO_BRIEF", f_macro_brief),
        ("MARKET_ALERTS", f_market_alerts),
    ]

    for var, fn in tasks:
        if target_vars is not None and var not in target_vars:
            continue
        run(var, fn)

    # 盘中/收盘/全量抓取后，用实时 raw_data 生成 AI 盘面解读（规则引擎，零成本，稳定可调试）
    # post_close 15:30 运行会生成「收盘」版解读，避免盘中 13:xx 的评论挂到次日。
    if category in ("intraday", "post_close", "all"):
        try:
            script = ROOT / "algorithms" / "gen_market_brief.py"
            print(f"🧠 生成 AI 盘面解读: {script.name}")
            subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)
        except Exception as e:
            print(f"  ⚠️ gen_market_brief 调用失败: {e}")

    # 生成 runner 状态文件，供前端「定时任务跟踪」看板展示
    try:
        runner_status = {
            "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category or "all",
            "hostname": os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", ""),
            "modules": _run_status,
            "summary": {
                "total": len(_run_status),
                "ok": sum(1 for v in _run_status.values() if v.get("status") == "ok"),
                "empty": sum(1 for v in _run_status.values() if v.get("status") == "empty"),
                "fail": sum(1 for v in _run_status.values() if v.get("status") == "fail"),
            },
        }
        with open(RAW_DIR / "runner_status.json", "w", encoding="utf-8") as f:
            json.dump(runner_status, f, ensure_ascii=False, separators=(",", ":"), default=str)
        print(f"📋 runner_status: {runner_status['summary']}")
    except Exception as e:
        print(f"  ⚠️ 写入 runner_status 失败: {e}")

    print(f"=== v8 云端抓取结束 {datetime.now().isoformat(timespec='seconds')} ===")
    print(f"raw_data/ 文件数: {len(list(RAW_DIR.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v8 cloud fetch")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "all"],
                        help="只抓取某一时段类别；all=全量兜底")
    parser.add_argument("--only", default=None,
                        help="只抓取指定变量（如 SH_SZ_HISTORY），跳过 raw_data 清理，不误删其他时段数据")
    args = parser.parse_args()
    sys.exit(main(category=args.category, only=args.only))
