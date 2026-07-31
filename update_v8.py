#!/usr/bin/env python3
"""v8 数据构建脚本 — 从 raw_data/*.json 生成 data/*.js

说明：
- v8 已改为轻量模板：index.html 不再内联大数据，而是引用 data/*.js。
- 本脚本负责把原始数据 raw_data/<file>.json 转换为 data/<VAR>.js。
- 原始数据由数据源端（小九/单位机）提供，本脚本只负责格式转换与轻量裁剪。
- 输出文件可直接被 index.html 通过 <script src="./data/VAR.js"> 同步加载。
"""

import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"

# 原始文件名 → window 变量名映射
# 若数据源端直接以变量名命名文件，可省略映射，按文件名自动推断。
DATA_SOURCES = {
    "etf_intraday_heat.json":      "ETF_INTRADAY_HEAT",
    "sector_fund_flow.json":       "SECTOR_FUND_FLOW",
    "scan_data.json":              "SCAN_DATA",
    "gold_pool.json":              "GOLD_POOL",
    "stock_names.json":            "STOCK_LIST",
    "recommend.json":              "RECOMMEND",
    "macro_data.json":             "MACRO_DATA",
    "nt_data.json":                "NT_DATA",
    "lhb_data.json":               "LHB_DATA",
    "concept_ranking.json":        "CONCEPT_RANKING",
    "margin_data.json":            "MARGIN_DATA",
    "cffex_data.json":             "CFFEX_HOLDINGS",
    "ipo_score.json":              "IPO_DATA",
    "crisis_data.json":            "CRISIS_DATA",
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
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{var_name}.js"
    lite_obj = _make_lite(var_name, obj)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"window.{var_name} = ")
        json.dump(lite_obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(";\n")
    return out_path


def build():
    if not RAW_DIR.exists():
        print(f"⚠️  raw_data/ 目录不存在（{RAW_DIR}）。")
        print("   请将数据源端生成的 *.json 放到 raw_data/，再运行本脚本。")
        print("   当前 data/*.js 不会被修改（保持既有线上数据）。")
        return 0

    files = [p for p in RAW_DIR.iterdir() if p.suffix == '.json']
    if not files:
        print(f"⚠️  raw_data/ 为空，无数据可更新。保持既有 data/*.js 不变。")
        return 0

    updated = 0
    skipped = 0
    for src_path in sorted(files):
        var_name = DATA_SOURCES.get(src_path.name)
        if not var_name:
            # 尝试按文件名推断变量名（如 v8_cal.json → V8_CAL）
            stem = src_path.stem
            var_name = stem.upper().replace('-', '_')
        obj = _load_json(src_path)
        if obj is None:
            skipped += 1
            continue
        out_path = _write_js(var_name, obj)
        updated += 1
        print(f"  ✅ {src_path.name} → {out_path.name}")

    print(f"\n完成：更新 {updated} 个，跳过 {skipped} 个。")
    print(f"输出目录：{DATA_DIR}")
    return 0


if __name__ == '__main__':
    sys.exit(build())
