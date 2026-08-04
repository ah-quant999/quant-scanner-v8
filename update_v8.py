#!/usr/bin/env python3
"""v8 数据构建脚本 — 从 raw_data/*.json 生成 data/*.js

改造要点（2026-07-31 周末·阿狸咪）：
- 支持按 category 选择性构建：premarket / intraday / post_close / weekly。
- 支持 --detect-changes：只构建本次 push 发生变化的 raw_data 所属类别。
- 缺失 raw_data 的模块：保持既有 data/*.js 不变（carry-forward），由 guard 标陈旧。
- 删除死数据文件 RECOMMEND / SCAN_DATA 的映射。
"""

import json, os, sys, subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"

# 原始文件名 → window 变量名
DATA_SOURCES = {
    "etf_intraday_heat.json":      "ETF_INTRADAY_HEAT",
    "sector_fund_flow.json":       "SECTOR_FUND_FLOW",
    "sector_fund_flow_trend.json": "SECTOR_FUND_FLOW_TREND",
    "gold_pool.json":              "GOLD_POOL",
    "stock_names.json":            "STOCK_LIST",
    "macro_data.json":             "MACRO_DATA",
    "nt_data.json":                "NT_DATA",
    "lhb_data.json":               "LHB_DATA",
    "lhb_history.json":           "LHB_HISTORY",
    "concept_ranking.json":        "CONCEPT_RANKING",
    "margin_data.json":            "MARGIN_DATA",
    "cffex_data.json":             "CFFEX_HOLDINGS",
    "ipo_score.json":              "IPO_DATA",
    "crisis_data.json":            "CRISIS_DATA",
    "judgment_data.json":          "JUDGMENT_DATA",
    "crds_card_data.json":         "CRDS_CARD_DATA",
    "triple_consensus.json":       "TRIPLE_CONSENSUS",
    "triple_track.json":           "TRIPLE_TRACK",
    "triple_history.json":         "TRIPLE_HISTORY",
    "cockpit_tier_recommend.json": "COCKPIT_TIER_RECOMMEND",
    "top10_daily.json":            "TOP10_DAILY",
    "cockpit_advice.json":         "COCKPIT_ADVICE",
    "sh_fib.json":                 "SH_FIB",
    "sz_fib.json":                 "SZ_FIB",
    "sector_rs.json":              "SECTOR_RS",
    "inst_trade.json":             "INST_TRADE",
    "north_fund.json":             "NORTH_FUND",
    "market_alerts.json":          "MARKET_ALERTS",
    "market_fund_flow_data.json":  "MARKET_FUND_FLOW_DATA",
    "etf_subscription.json":       "ETF_SUBSCRIPTION",
    "w52_high.json":               "W52_HIGH",
    "limit_up_heatmap.json":       "LIMIT_UP_HEATMAP",
    "herding_data.json":           "HERDING_DATA",
    "analyst_ratings.json":        "ANALYST_RATINGS",
    "suspension_alert.json":       "SUSPENSION_ALERT",
    "volatility.json":             "VOLATILITY",
    "index_quotes.json":           "INDEX_QUOTES",
    "capital_flow_data.json":      "CAPITAL_FLOW_DATA",
    "mahoro.json":                 "MAHORO",
    "candidate.json":              "CANDIDATE",
    "backtest_comprehensive.json": "BACKTEST_COMPREHENSIVE",
    "cockpit_backtest.json":       "COCKPIT_BACKTEST",
    "backtest_tdx.json":           "BACKTEST_TDX",
    "experiment.json":             "EXPERIMENT",
    "etf_pulse.json":              "ETF_PULSE",
    "etf_daily_monitor.json":      "ETF_DAILY_MONITOR",
    "v8_cal.json":                 "V8_CAL",
    "candidate_quotes.json":       "CANDIDATE_QUOTES",
    "sh_sz_history.json":         "SH_SZ_HISTORY",
    "risk_gauge.json":             "RISK_GAUGE",
    "ai_market_brief.json":        "AI_MARKET_BRIEF",
    "runner_status.json":          "RUNNER_STATUS",
}

# 变量名 → 更新时段
CATEGORY_MAP = {
    # 盘前（08:25 cn / 08:35 deploy）
    "V8_CAL": "premarket",
    "IPO_DATA": "premarket",
    "NT_DATA": "premarket",
    "MARGIN_DATA": "premarket",
    "CFFEX_HOLDINGS": "premarket",
    "MACRO_DATA": "premarket",
    "CRISIS_DATA": "premarket",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    "SUSPENSION_ALERT": "premarket",
    "MARKET_ALERTS": "premarket",
    "W52_HIGH": "premarket",
    "HERDING_DATA": "premarket",
    "JUDGMENT_DATA": "premarket",

    # 盘后（由 v6 算法 calc_volatility_watch.py 同步桥推送）
    "VOLATILITY": "post_close",

    # 盘中（每30分钟 09:40~15:10，由 cn runner 刷新）
    # 注意：ETF_DAILY_MONITOR 虽字段含 T+1，但为配合 ETF 三连板实时卡，归 intraday 盘中更新
    "INDEX_QUOTES": "intraday",
    "ETF_PULSE": "intraday",
    "ETF_INTRADAY_HEAT": "intraday",
    "ETF_SUBSCRIPTION": "premarket",
    "ETF_DAILY_MONITOR": "intraday",
    "SECTOR_FUND_FLOW": "intraday",
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday",
    "CANDIDATE_QUOTES": "intraday",
    "SH_SZ_HISTORY": "intraday",
    "RISK_GAUGE": "intraday",
    "AI_MARKET_BRIEF": "intraday",
    # 盘后：大盘资金流时间轴，累积历史序列
    "MARKET_FUND_FLOW_DATA": "post_close",

    # 盘后（17:00，主要由 v6 算法推送；cloud_fetch 暂无生产者）
    "SECTOR_FUND_FLOW_TREND": "post_close",
    "GOLD_POOL": "post_close",
    "CANDIDATE": "post_close",
    "TRIPLE_CONSENSUS": "post_close",
    "TRIPLE_TRACK": "post_close",
    "TRIPLE_HISTORY": "post_close",
    "TOP10_DAILY": "post_close",
    "LHB_DATA": "post_close",
    "LHB_HISTORY": "post_close",
    "SECTOR_RS": "post_close",
    "SH_FIB": "post_close",
    "SZ_FIB": "post_close",
    "INST_TRADE": "post_close",
    "CRDS_CARD_DATA": "post_close",
    "COCKPIT_TIER_RECOMMEND": "post_close",
    "COCKPIT_ADVICE": "post_close",
    "COCKPIT_BACKTEST": "post_close",
    "BACKTEST_TDX": "post_close",
    "BACKTEST_COMPREHENSIVE": "post_close",
    "MAHORO": "post_close",
    "EXPERIMENT": "post_close",
    "STOCK_LIST": "post_close",
}

CATEGORY_LABEL = {
    "premarket": "盘前",
    "intraday": "盘中",
    "post_close": "盘后",
    "weekly": "每周清理",
}


def _load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️  读取失败 {path}: {e}")
        return None


def _make_lite(name, obj):
    """轻量裁剪：只保留累计/计算数值，去掉历史明细。"""
    if not isinstance(obj, dict):
        return obj
    if name == 'BACKTEST_TDX':
        return {
            'calc_time': obj.get('calc_time'),
            'method': obj.get('method'),
            'gold_pool_size': obj.get('gold_pool_size'),
            'stocks_analyzed': obj.get('stocks_analyzed'),
            'summary': obj.get('summary', {}),
            '_lite_note': '个股历史信号明细已裁剪，仅保留汇总统计',
        }
    if name == 'BACKTEST_COMPREHENSIVE':
        lite = {k: v for k, v in obj.items() if k != 'details'}
        lite['_lite_note'] = 'details 回测明细已裁剪，仅保留 overview/comparison'
        return lite
    if name == 'COCKPIT_BACKTEST':
        lite = {k: v for k, v in obj.items() if k != 'results'}
        results = obj.get('results', [])
        lite['results'] = results[:20]
        lite['_lite_note'] = 'results 已裁剪至最近 20 条明细'
        return lite
    if name == 'GOLD_POOL':
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        stocks_lite = {}
        for sid, s in obj.get('stocks', {}).items():
            stocks_lite[sid] = {
                'code': s.get('code'),
                'name': s.get('name'),
                'market': s.get('market'),
                'board_label': s.get('board_label'),
                'fund_type': s.get('fund_type'),
                'first_date': s.get('first_date'),
                'first_signal': s.get('first_signal'),
                'max_signal': s.get('max_signal'),
                'signal_count': s.get('signal_count'),
                'sources': s.get('sources'),
                'latest': s.get('latest'),
                'industry': s.get('industry'),
                'sectors': s.get('sectors'),
                'concepts': s.get('concepts'),
                'board': s.get('board'),
            }
        lite['stocks'] = stocks_lite
        lite['_lite_note'] = 'stocks 已去掉 history 日明细，仅保留 latest 聚合'
        return lite
    if name == 'ANALYST_RATINGS':
        # v6 源结构(upgrades/downgrades/hot_stocks/latest_reports) → v8 期望 {ratings:[...]}
        merged = {}
        for k in ('hot_stocks', 'latest_reports', 'upgrades', 'downgrades', 'new_coverage'):
            for r in (obj.get(k) or []):
                code = str(r.get('code', ''))
                if not code or code in merged:
                    continue
                merged[code] = {
                    'code': code,
                    'name': r.get('name', ''),
                    'rating': r.get('rating', '-'),
                    'count': r.get('report_count_1m') or 1,
                    'date_range': r.get('date', ''),
                }
        return {'update_time': obj.get('update_time'), 'ratings': list(merged.values())}
    if name == 'SUSPENSION_ALERT':
        # v6 源结构(suspended/near_trigger) → v8 期望 {stocks:[...]}
        stocks = []
        for r in (obj.get('suspended') or []):
            code = str(r.get('code', ''))
            if not code:
                continue
            stocks.append({'code': code, 'name': r.get('name', ''), 'status': '停牌',
                           'days': r.get('days'), 'reason': r.get('reason', '')})
        for r in (obj.get('near_trigger') or []):
            code = str(r.get('code', ''))
            if not code:
                continue
            stocks.append({'code': code, 'name': r.get('name', ''), 'status': '临停预警',
                           'days': None,
                           'reason': '临近触发阈值(pct=%s, gap=%s)' % (r.get('pct'), r.get('gap'))})
        return {'update_time': obj.get('update_time'), 'stocks': stocks}
    if name == 'W52_HIGH':
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        lite['_lite_note'] = 'stocks 完整列表已裁剪，仅保留 top_gainers 与 total'
        return lite
    return obj


def _write_js(var_name, obj):
    """把 obj 写入 data/<var>.js，同时强制注入顶层 update_time。

    强制规则（2026-08-02 收紧）：
    - 顶层是 dict 且已有 update_time/calc_time：保留较新者
    - 顶层是 dict 但缺 update_time：用源文件 mtime 兜底，无源文件则用当前时间
    - 顶层是 list（如 STOCK_LIST）：包装成 {"data": [...], "update_time": ...}，
      index.html 需读 .data；此规则对应 sync_v6_to_v8._add_timestamp()
    """
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{var_name}.js"
    lite_obj = _make_lite(var_name, obj)

    # 找源文件以取 mtime
    src_path = None
    for fname, var in DATA_SOURCES.items():
        if var == var_name:
            sp = RAW_DIR / fname
            if sp.exists():
                src_path = sp
            break

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mtime_ts = ""
    if src_path is not None:
        try:
            mtime_ts = datetime.fromtimestamp(src_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    def _pick_ts(existing):
        """从已有时间戳列表中挑最新的。"""
        candidates = [t for t in (existing, mtime_ts, now_ts) if t]
        if not candidates:
            return now_ts
        return max(candidates)

    if isinstance(lite_obj, list):
        # 顶层数组：包装成 dict（同步 sync_v6_to_v8 规则）
        lite_obj = {"data": lite_obj, "update_time": _pick_ts(None)}
    elif isinstance(lite_obj, dict):
        existing = lite_obj.get("update_time") or lite_obj.get("calc_time") or ""
        lite_obj["update_time"] = _pick_ts(existing)

    with open(out_path, "w", encoding='utf-8') as f:
        f.write(f"window.{var_name} = ")
        json.dump(lite_obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(";\n")
    return out_path


def _var_category(var_name):
    return CATEGORY_MAP.get(var_name, "post_close")


def _file_category(filename):
    var_name = DATA_SOURCES.get(filename)
    return _var_category(var_name) if var_name else None


def _list_changed_raw_files():
    """通过 git diff HEAD~1..HEAD 找出变化的 raw_data 文件（用于 v6 push 触发构建）。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=30
        )
        if result.returncode != 0:
            # 可能是第一次提交或浅克隆，尝试 HEAD
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=ROOT, capture_output=True, text=True, check=False, timeout=30
            )
        if result.returncode != 0:
            return []
        changed = [line.strip() for line in result.stdout.splitlines()
                   if line.strip().startswith("raw_data/")]
        return [Path(ROOT) / p for p in changed]
    except Exception as e:
        print(f"  ⚠️  git diff 检测失败: {e}")
        return []


def build(category=None, detect_changes=False):
    if not RAW_DIR.exists():
        print(f"⚠️  raw_data/ 目录不存在（{RAW_DIR}）。保持既有 data/*.js 不变。")
        return 0

    files = [p for p in RAW_DIR.iterdir() if p.suffix == '.json']
    if not files:
        print(f"⚠️  raw_data/ 为空，无数据可更新。保持既有 data/*.js 不变。")
        return 0

    if detect_changes:
        changed = _list_changed_raw_files()
        changed_names = {p.name for p in changed}
        affected_cats = {_file_category(p.name) for p in changed}
        affected_cats.discard(None)
        print(f"🔍 detect_changes 模式：变化 raw_data {len(changed)} 个，涉及类别 {sorted(affected_cats) or '无'}")
        if not affected_cats:
            print("   无受影响的类别，跳过构建。")
            return 0
        target_files = [p for p in files if _file_category(p.name) in affected_cats]
    elif category:
        print(f"🔍 category={category}（{CATEGORY_LABEL.get(category, category)}） selective build")
        target_files = [p for p in files if _file_category(p.name) == category]
    else:
        print("🔍 全量构建模式")
        target_files = files

    # runner_status.json 跨所有时段，每次构建都带上，保证前端任务跟踪看板最新
    runner_path = RAW_DIR / "runner_status.json"
    if runner_path.exists() and runner_path not in target_files:
        target_files.append(runner_path)

    if not target_files:
        print(f"⚠️ 没有属于目标类别的 raw_data 文件，保持 data/*.js 不变。")
        return 0

    updated = 0
    skipped = 0
    for src_path in sorted(target_files):
        var_name = DATA_SOURCES.get(src_path.name)
        if not var_name:
            print(f"  ⏭️  {src_path.name} 不在 DATA_SOURCES 映射中，跳过（避免废弃数据复活）")
            skipped += 1
            continue
        obj = _load_json(src_path)
        if obj is None:
            skipped += 1
            continue
        out_path = _write_js(var_name, obj)
        updated += 1
        print(f"  ✅ {src_path.name} → {out_path.name}")

    print(f"\n完成：更新 {updated} 个，跳过 {skipped} 个。输出目录：{DATA_DIR}")
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="v8 data builder")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "weekly"],
                        help="只构建某一时段类别")
    parser.add_argument("--detect-changes", action="store_true",
                        help="只构建最近 git diff 发生变化的 raw_data 所属类别")
    args = parser.parse_args()
    return build(category=args.category, detect_changes=args.detect_changes)


if __name__ == '__main__':
    sys.exit(main())
