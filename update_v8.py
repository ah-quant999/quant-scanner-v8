#!/usr/bin/env python3
"""v8 数据构建脚本 — 从 raw_data/*.json 生成 data/*.js

改造要点（2026-07-31 周末·阿狸咪）：
- 支持按 category 选择性构建：premarket / intraday / post_close / weekly。
- 支持 --detect-changes：只构建本次 push 发生变化的 raw_data 所属类别。
- 缺失 raw_data 的模块：保持既有 data/*.js 不变（carry-forward），由 guard 标陈旧。
- 删除死数据文件 RECOMMEND / SCAN_DATA 的映射。
"""

import json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"
CST = ZoneInfo("Asia/Shanghai")

def now_cst():
    """返回中国标准时间（Asia/Shanghai）的当前 datetime。"""
    return datetime.now(CST)

# 原始文件名 → window 变量名
DATA_SOURCES = {
    "etf_intraday_heat.json":      "ETF_INTRADAY_HEAT",
    "sector_phase_history.json":   "SECTOR_PHASE_HISTORY",  # 2026-08-17 主人令：盘后每日阶段快照（自动累积+前端"今日 vs 上次"对比）
    "sector_fund_flow.json":       "SECTOR_FUND_FLOW",
    "sector_fund_flow_trend.json": "SECTOR_FUND_FLOW_TREND",
    # 🛡 2026-08-19 主人令一劳永逸式修复：原 DATA_SOURCES 缺 sector_fund_flow_intraday.json 映射，
    #   cloud_fetch_v8.py f_sector_fund_flow() 已在抓取时按 intraday 追加快照（line 1168），
    #   但 update_v8 转换层漏挂 → data/SECTOR_FUND_FLOW_INTRADAY.js 永远停在 09:56 的 2 快照版。
    #   根因：与 8/18 OVERSEAS_MARKETS 同类疏漏（fetch 注册了 raw 写，build 没映射）。
    "sector_fund_flow_intraday.json": "SECTOR_FUND_FLOW_INTRADAY",
    "gold_pool.json":              "GOLD_POOL",
    "stock_names.json":            "STOCK_LIST",
    "stock_profile.json":          "STOCK_PROFILE",
    "macro_data.json":             "MACRO_DATA",
    "macro_brief.json":            "MACRO_BRIEF",
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
    # 🆕 2026-08-31 阶段 1：v8 选股生命周期跟踪（专家方法论整合）。
    #   从 algo_track.json 读三 algo 跟踪池，去重 → 状态机判 status → 输出
    #   raw_data/v8_pool_tracker.json + data/V8_POOL_TRACKER.js，注入 window.V8_POOL_TRACKER。
    "v8_pool_tracker.json":        "V8_POOL_TRACKER",
    "triple_consensus.json":       "TRIPLE_CONSENSUS",
    "triple_track.json":           "TRIPLE_TRACK",
    # 🛡 2026-08-26 一劳永逸根因修复：生成器 update_triple_resonance_history.py 写的是
    #   raw_data/triple_resonance_history.json，而此处原读旧名 triple_history.json（同源不同名），
    #   桥接顺序一错位就吃陈旧基线 → 共振日历缺 08-24 等。改为直接读生成器真输出，消除重命名歧义。
    "triple_resonance_history.json": "TRIPLE_HISTORY",
    # 2026-09-04 主人令收尾：cockpit_tier_recommend / cockpit_advice / cockpit_backtest 三映射已删
    #   （09-03「干掉驾驶舱」系列删了生成器与 raw_data，映射永不命中，纯死代码）
    "top10_daily.json":            "TOP10_DAILY",
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
    "limit_up_broken.json":        "LIMIT_UP_BROKEN",
    "herding_data.json":           "HERDING_DATA",
    "analyst_ratings.json":        "ANALYST_RATINGS",
    "suspension_alert.json":       "SUSPENSION_ALERT",
    "volatility.json":             "VOLATILITY",
    "index_quotes.json":           "INDEX_QUOTES",
    "capital_flow_data.json":      "CAPITAL_FLOW_DATA",
    "candidate.json":              "CANDIDATE",
    "backtest_comprehensive.json": "BACKTEST_COMPREHENSIVE",
    # 2026-09-04 主人令收尾：cockpit_backtest.json 映射已删（驾驶舱模块下线）
    "backtest_tdx.json":           "BACKTEST_TDX",
    "optimized_strategy.json":     "OPTIMIZED_STRATEGY",
    "experiment.json":             "EXPERIMENT",
    "etf_pulse.json":              "ETF_PULSE",
    "etf_daily_monitor.json":      "ETF_DAILY_MONITOR",
    # 🛡 2026-08-18 一劳永逸式修复：原 DATA_SOURCES 缺 overseas_markets.json 映射，
    #   update_v8 永远不生成 data/OVERSEAS_MARKETS.js，导致该卡 4 天没更新被健康巡检报 fail。
    #   根本原因：raw_data/overseas_markets.json 由 cloud_fetch_v8.py 抓（line 116 注册 intraday），
    #   但 update_v8 转换层漏挂，data/*.js 永远停在 8/14 旧版本。
    "overseas_markets.json":       "OVERSEAS_MARKETS",
    "v8_cal.json":                 "V8_CAL",
    "candidate_quotes.json":       "CANDIDATE_QUOTES",
    "sh_sz_history.json":         "SH_SZ_HISTORY",
    "ai_market_brief.json":        "AI_MARKET_BRIEF",
    "runner_status.json":          "RUNNER_STATUS",
    "risk_gauge.json":             "RISK_GAUGE",
    "stock_quote.json":            "STOCK_QUOTE",
    "avg_price_data.json":         "AVG_PRICE_DATA",
    "algo_track.json":              "ALGO_TRACK",   # 2026-08-15 三算法独立追踪（四量终极/板块龙头/大牛股猎手）
    "weekend_meta_report.json":      "WEEKEND_META_REPORT",
    # 🛡 2026-08-29 一劳永逸式修复：DELISTED_STOCKS 已删（1MB 死数据，全站 0 渲染引用，renderDelisted 走 CANDIDATE）
    # 映射移除后 update_v8.py 不再尝试写 data/DELISTED_STOCKS.js；data/HEALTH_CHECK.js 健康巡检条目待下次跑批自动收敛
    # 🛡 2026-08-18 一劳永逸式修复：补入 weekend_run.json → WEEKEND_RUN 映射
    #   原 update_v8 漏挂此映射 → data/WEEKEND_RUN.js 永远不被重新生成 → 健康巡检永远 warn
    "weekend_run.json":            "WEEKEND_RUN",
    # 2026-08-19 主人令：路径概率预测卡（艾略特波浪+江恩+缠论+形态匹配），需 5 年长 K 线
    "index_history.json":          "INDEX_HISTORY",
    "market_path_probability.json": "MARKET_PATH_PROBABILITY",
    # 2026-08-19 主人令：利率上行期板块推荐框架（宏观+板块RS+资金流+周期融合；macro.json 删除孤儿后由 market_regime.json 单源触发）
    "market_regime.json":           "MARKET_REGIME",
    "sector_recommendation.json":   "SECTOR_RECOMMENDATION",
    # 🛡 2026-08-26 一劳永逸根因修复：原 DATA_SOURCES 漏挂 final_recommend.json / stock_rps.json 映射，
    #   这两个 .js 仅由算法脚本（final_recommend.py / calc_stock_rps.py）写入，而云端 build 的 update_v8 步骤
    #   不覆盖它们 → data/FINAL_RECOMMEND_DATA.js、data/STOCK_RPS.js 站点读的 window.* 永远停在 08-22（源 raw_data 已是 08-25 新鲜）。
    #   补映射后，云端 build 自动按 raw_data 重建，杜绝复发。
    "final_recommend.json":        "FINAL_RECOMMEND_DATA",
    "stock_rps.json":              "STOCK_RPS_DATA",
    "factor_lab_backtest.json":    "FACTOR_LAB_BACKTEST",  # 🆕 2026-09-04 因子实验室独立分层回测
    # 🛡 2026-08-30 一劳永逸式：补 ETF 申购赎回东方财富口径（股票/债券/货币/商品/跨境 5 类 + 亿元），
    #   替代旧宽基指数 + 亿份口径（旧 ETF_SUBSCRIPTION.js 保留作 legacy，不入 DATA_SOURCES）。
    #   旧 data/ETF_SUBSCRIPTION.js 已写好的 "sh"/"sz"/"update_time" 老口径**保留**，前端同时读 window.ETF_SUBSCRIPTION。
    #   新增 window.ETF_SUBSCRIPTION_EM 走东财口径（5 类聚合 + 亿元）。
    "etf_subscription_em.json":   "ETF_SUBSCRIPTION_EM",
    # 2026-08-30：盘后数据页新增解禁日历 + 业绩预告
    "restricted_release.json":    "RESTRICTED_RELEASE",
    "performance_forecast.json":  "PERFORMANCE_FORECAST",
}

# 🆕 2026-09-05 主人令一劳永逸：运维看板全量覆盖 + 审计轨迹
#   ALL_MODULE_NAMES = 数据管线全部模块变量名（剔除仅元数据/健康类），
#   供 RUNNER_STATUS 补全 + AUDIT_TRAIL 复用，确保运维卡真实覆盖所有模块。
_AUDIT_TRAIL_EXCLUDE = {"RUNNER_STATUS", "RUNNER_STATUS_HEALTH", "HEALTH_CHECK", "AUDIT_TRAIL"}
ALL_MODULE_NAMES = sorted(n for n in DATA_SOURCES.values() if n not in _AUDIT_TRAIL_EXCLUDE)

# 变量名 → 更新时段
CATEGORY_MAP = {
    # 盘前（08:25 cn / 08:35 deploy）
    "V8_CAL": "premarket",
    "IPO_DATA": "premarket",
    "NT_DATA": "premarket",
    "MARGIN_DATA": "premarket,post_close",
    # 2026-08-31：期指主力合约卡移回「实时数据」页，改为 intraday 盘中实时
    "CFFEX_HOLDINGS": "intraday",
    # 🛡 2026-09-04 主人令（一劳永逸·根因修复）：与 cloud_fetch_v8.py 同步加 post_close。
    #   盘后数据页「宏观数据速览」卡读本变量，原只标 premarket → 盘后档不重生成 data/MACRO_DATA.js。
    "MACRO_DATA": "premarket,post_close",
    "CRISIS_DATA": "premarket,intraday",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    "SUSPENSION_ALERT": "premarket",
    "MARKET_ALERTS": "intraday",
    # 🛡 2026-09-04 同上：盘后数据页「市场宽度 · 新高家数与宽度评分」卡读本变量（52周新高广度）。
    "W52_HIGH": "premarket,post_close",
    "HERDING_DATA": "premarket",
    "JUDGMENT_DATA": "premarket",
    "MACRO_BRIEF": "premarket",

    # 盘后（由 v6 算法 calc_volatility_watch.py 同步桥推送）
    "VOLATILITY": "post_close",

    # 盘中（每30分钟 09:40~15:10，由 cn runner 刷新）
    # 注意：ETF_DAILY_MONITOR 虽字段含 T+1，但为配合 ETF 三连板实时卡，归 intraday 盘中更新
    "INDEX_QUOTES": "intraday",
    "ETF_PULSE": "intraday",
    "ETF_INTRADAY_HEAT": "intraday",
    "ETF_SUBSCRIPTION": "premarket",
    "ETF_DAILY_MONITOR": "intraday",
    # 🛡 2026-09-04 一劳永逸（两处映射不一致根治）：cloud_fetch_v8.py 早在 2026-09-03 就把这两个
    #   改成 "intraday,post_close"（盘中 cron 偶发丢档→收盘定格值无着落），但 update_v8.py 侧漏同步，
    #   仍是 "intraday" → 盘后档抓取更新了 raw_data，update_v8 却跳过重生成 data/*.js，
    #   造成「raw 已新、js 仍旧」的半截更新。现补齐对齐。
    "SECTOR_FUND_FLOW": "intraday,post_close",
    "SECTOR_FUND_FLOW_INTRADAY": "intraday,post_close",  # 2026-08-19 主人令：分时快照盘中每30分随 SECTOR_FUND_FLOW 同步发布
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday,post_close",
    "LIMIT_UP_BROKEN": "intraday",
    "CANDIDATE_QUOTES": "intraday",
    "SH_SZ_HISTORY": "intraday",
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
    # 2026-09-04 主人令收尾：COCKPIT_TIER_RECOMMEND/COCKPIT_ADVICE/COCKPIT_BACKTEST heal 分类已删（模块下线）
    "BACKTEST_TDX": "post_close",
    "BACKTEST_COMPREHENSIVE": "post_close",
    "FACTOR_LAB_BACKTEST": "post_close",
    "EXPERIMENT": "post_close",
    "STOCK_LIST": "post_close",
    "STOCK_PROFILE": "post_close",
    # 🆕 2026-08-31：v8 选股生命周期跟踪归属盘后（依赖算法跟踪池，每日盘后产出）。
    "V8_POOL_TRACKER": "post_close",
    # 2026-08-31：AVG_PRICE_DATA 由 scripts/fetch_avg_price.py 在盘中/盘后/周末生成，
    #   映射为 intraday 使 update_v8 在盘中也刷新 AVG_PRICE_DATA.js（数据源单点，无双写冲突）。
    "AVG_PRICE_DATA": "intraday",
    # 2026-08-15：ALGO_TRACK 依赖 FINAL_RECOMMEND_DATA + FOUR_VOLUME，归属盘后
    "ALGO_TRACK": "post_close",
    # 2026-08-19：路径概率预测卡数据源（盘后跑，与算法链节奏一致）
    "INDEX_HISTORY": "post_close",
    "MARKET_PATH_PROBABILITY": "post_close",
    # 2026-08-19：板块推荐框架数据源（盘后跑宏观+板块融合；MACRO.js 已删孤儿→不注册）
    "MARKET_REGIME": "post_close",
    "SECTOR_RECOMMENDATION": "post_close",
    # 🛡 2026-08-26 一劳永逸根因修复：final_recommend / stock_rps 与 FINAL_RECOMMEND_DATA / STOCK_RPS_DATA
    #   归属盘后（与 finalRec 同节奏），补类别映射使 --category post_close / --detect-changes 能正确重建。
    "FINAL_RECOMMEND_DATA": "post_close",
    "STOCK_RPS_DATA": "post_close",
    # 2026-08-30：盘后数据页新增解禁日历 + 业绩预告（cloud_fetch 注册为 premarket，日频）
    # 🛡 2026-09-04 主人令（一劳永逸·根因修复）：与 cloud_fetch_v8.py 同步加 post_close。
    #   注释写着「盘后数据页」却只在盘前重建 data/*.js —— 盘后重抓了 raw 却不重生成 js，半截更新。
    "RESTRICTED_RELEASE": "premarket,post_close",
    "PERFORMANCE_FORECAST": "premarket,post_close",
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
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST lite 裁剪分支已删（驾驶舱模块下线，永不命中）
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
    if name == 'IPO_DATA':
        # 校正 recommend + 自动补全 shadows（依赖 stock_names.json / candidate_quotes.json）
        return _build_ipo_shadows(obj)
    if name == 'W52_HIGH':
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        lite['_lite_note'] = 'stocks 完整列表已裁剪，仅保留 top_gainers 与 total'
        return lite
    if name == 'SECTOR_PHASE_HISTORY':
        # 2026-08-22 主人令：顶层 update_time 取最新一期快照时间（raw 文件 mtime 因
        # git checkout 重置会失真，但 snaps 内每期自带 update_time，以数据为准）。
        snaps = obj.get('snaps') or []
        latest = ""
        for s in snaps:
            t = s.get('update_time') or s.get('date') or ""
            if t > latest:
                latest = t
        out = dict(obj)
        out['update_time'] = latest or obj.get('update_time', '')
        out['snap_count'] = len(snaps)
        return out
    return obj


# ── IPO 影子股与 recommend 校正 ──

# 非推荐等级、不应出现在 recommend 字段的状态词
_IPO_STATUS_WORDS = {
    "待定价", "待上市", "待申购", "申购中", "今日上市", "上市首日",
    "追踪中", "已上市", "过期", "", "—", "-",
}

# 判断 recommend 是否已包含有效建议等级
_IPO_REC_PATTERNS = re.compile(r"强烈|建议|谨慎|不建议|放弃")

# 明显属于市场/风格/指数的通用概念，不应拿来做关联匹配
_IPO_GENERIC_CONCEPTS = {
    "MSCI中国", "机构重仓", "证金持股", "富时罗素", "标准普尔", "沪股通", "深股通",
    "融资融券", "破净股", "长期破净", "权重股", "上证180", "沪深300", "中证500",
    "中证1000", "中证A500", "中证2000", "大盘股", "中盘股", "小盘股", "大盘价值",
    "小盘成长", "低价股", "高价股", "ST板块", "壳资源", "重组", "次新股", "近期新高",
    "近期新低", "预盈预增", "预亏预减", "高送转", "高分红", "高股息", "央企",
    "地方国企", "国企改革", "央企国资改革", "地方国资改革", "债转股", "股权转让",
    "股权激励", "员工持股", "回购", "举牌", "要约收购", "重大合同", "中标", "定增",
    "外资背景", "台资背景", "高校背景", "军工背景", "QFII", "社保基金", "保险重仓",
    "信托重仓", "基金重仓", "券商重仓", "国家队", "汇金", "养老金", "陆股通", "港股通",
    "转融通", "两融标的", "融资融券标的", "节能环保", "碳中和", "碳交易", "ESG",
}


def _sanitize_ipo_recommend(stock):
    """把被 status 污染的 recommend 字段按 score 重新映射为建议等级。

    注意：上市后（tracking / listed_today）的追入建议由 fetch_ipo_data_v8.py
    的 tracking_advice() 生成，含 emoji 与状态描述，不能按申购 score 覆盖为
    「不建议申购」。该 bug 曾于 2026-08-13 导致杰理科技/超纯应材等暴涨 tracking
    股被错误显示为不建议申购。
    """
    status = (stock.get("status") or "").strip()
    rec = (stock.get("recommend") or "").strip()

    # 上市后状态：保留追入/首日建议，仅缺失时兜底
    if status in ("tracking", "listed_today"):
        if not rec:
            stock["recommend"] = "数据不足，无法判断"
            stock["tag_color"] = "#999"
            stock["bg_color"] = "#f5f5f5"
        return stock

    # 已有有效申购建议等级时直接保留
    if rec and rec not in _IPO_STATUS_WORDS and _IPO_REC_PATTERNS.search(rec):
        return stock

    score = stock.get("score") or 0
    if score >= 80:
        rec, tc, bc = "强烈推荐申购", "#2e7d32", "#e8f5e9"
    elif score >= 65:
        rec, tc, bc = "建议申购", "#e65100", "#fff3e0"
    elif score >= 50:
        rec, tc, bc = "谨慎参与", "#f57f17", "#fffde7"
    else:
        rec, tc, bc = "不建议申购", "#c62828", "#ffebee"
    stock["recommend"] = rec
    stock["tag_color"] = tc
    stock["bg_color"] = bc
    return stock


def _clean_concept_name(name):
    """去掉「概念/板块/产业/主题」等后缀，提高 IPO 主营业务文本的匹配率。"""
    return re.sub(r"(概念|板块|产业|主题|指数|风格)$", "", name).strip()


def _build_ipo_shadows(obj):
    """基于 stock_names.json 的行业/概念映射，为 IPO 自动生成影子股列表。

    匹配逻辑（按优先级降序）：
    1. 同行业精确匹配（+3 分，rel_type='同业'）
    2. 主营业务文本命中 A 股概念关键词（+1 分，rel_type='供应链'）
    3. 按总市值从大到小取 top 5，保证关联股质量
    """
    stocks = obj.get("stocks") if isinstance(obj, dict) else None
    if not stocks:
        return obj

    # 读取全市场股票名称/行业/概念
    names_path = RAW_DIR / "stock_names.json"
    if not names_path.exists():
        return obj
    names_data = _load_json(names_path)
    if not names_data or not isinstance(names_data, dict):
        return obj
    stock_items = names_data.get("data") or names_data.get("stocks") or []
    if not stock_items:
        return obj

    # 读取候选行情（取涨跌幅）
    quotes = {}
    quotes_path = RAW_DIR / "candidate_quotes.json"
    if quotes_path.exists():
        qdata = _load_json(quotes_path)
        if qdata and isinstance(qdata, dict):
            for it in (qdata.get("items") or []):
                c = str(it.get("code", ""))
                if c:
                    quotes[c] = it

    candidates = []
    for s in stock_items:
        code = str(s.get("code", ""))
        if not code:
            continue
        concepts = []
        for c in (s.get("concepts") or []):
            if not c or len(c) < 2:
                continue
            cc = _clean_concept_name(c)
            if cc and cc not in _IPO_GENERIC_CONCEPTS:
                concepts.append(cc)
        candidates.append({
            "code": code,
            "name": s.get("name", ""),
            "industry": (s.get("industry") or "").strip(),
            "concepts": list(set(concepts)),
            "mv": 0,
        })

    def _shadows_for(ipo):
        ipo_code = str(ipo.get("code") or "")
        fund = ipo.get("fundamentals") or {}
        industry = (fund.get("industry") or ipo.get("industry_name") or "").strip()
        text = " ".join([
            industry,
            fund.get("main_business") or "",
            ipo.get("name") or "",
            " ".join(ipo.get("highlights") or []),
            ipo.get("track_label") or "",
        ]).strip()
        text_lower = text.lower()

        # ── 关键词双向匹配（2026-08-07 修复：原完整概念名子串匹配命中率极低）──
        # 拆 IPO 文本为 ≥2 字关键词，拆概念名为 ≥2 字关键词，
        # 任一方向命中即算概念关联（score +1），行业精确匹配仍 +3。
        # 关键：长词也生成所有 2~4 字子串，解决「汽车座椅」vs「汽车」粒度不匹配。
        import re as _re
        _STOP = {'的','与','和','或','及','等','其','在','有','为','是','以','中','上','下','从事','研发','生产','销售','服务','提供','制造','开发','设计'}
        def _kw(s):
            base = set(w for w in _re.findall(r'[\u4e00-\u9fff]{2,}', s) if w not in _STOP)
            # 对每个 ≥3 字词生成 2~4 字滑动窗口子串
            extra = set()
            for w in base:
                for L in range(2, min(len(w), 4) + 1):
                    for i in range(len(w) - L + 1):
                        sub = w[i:i+L]
                        if sub not in _STOP:
                            extra.add(sub)
            return base | extra

        ipo_kws = _kw(text)
        ipo_concepts = set()
        for cand in candidates:
            for c in cand["concepts"]:
                c_kws = _kw(c)
                # 双向：概念关键词 ∩ IPO关键词 非空 → 命中
                if ipo_kws & c_kws:
                    ipo_concepts.add(c)

        scored = []
        for cand in candidates:
            if cand["code"] == ipo_code:
                continue
            score = 0
            rel_type = "同业"
            if industry and cand["industry"] == industry:
                score += 3
            else:
                rel_type = "供应链"
            matched = [c for c in cand["concepts"] if c in ipo_concepts]
            if matched:
                score += len(matched)
            if score <= 0:
                continue
            q = quotes.get(cand["code"])
            mv = q.get("total_mv") if q else 0
            chg = q.get("chg") if q else None
            scored.append({
                "code": cand["code"],
                "name": cand["name"],
                "rel_type": rel_type,
                "chg": chg,
                "_score": score,
                "_mv": mv or 0,
            })
        # 按匹配分降序，同分按总市值降序
        scored.sort(key=lambda x: (-x["_score"], -x["_mv"]))
        return [{"code": x["code"], "name": x["name"], "rel_type": x["rel_type"], "chg": x["chg"]}
                for x in scored[:5]]

    for s in stocks:
        _sanitize_ipo_recommend(s)
        s["shadows"] = _shadows_for(s)
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

    now_ts = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    mtime_ts = ""
    if src_path is not None:
        try:
            mtime_ts = datetime.fromtimestamp(src_path.stat().st_mtime, tz=CST).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    def _pick_ts(existing, obj=None):
        """真实优先：源数据自带时间戳 > _meta.last_update（子级更新） > 源文件 mtime > 当前时间。

        2026-08-07 修（主人铁律「不得造假」）：原实现取 max(existing, mtime, now)，
        now_ts 永远最大 → 每次构建都把所有卡片的「更新于」刷成构建时刻，
        导致 ①「更新于」全是假时间 ②「今日已跑完」胶囊在开盘前判错（数据日期被
        改成今天，而交易日归上一日 → 胶囊隐藏）。禁止再改回 max。

        2026-08-27 一劳永逸修复：TRIPLE_HISTORY 等带 _meta 的数据，
        算法跟踪只更新 _meta.last_update 而忘同步顶层 update_time → HEALTH_CHECK 读到陈旧值报 fail。
        此处增加 _meta.last_update 作为第二优先源，取较新者。
        """
        if existing:
            # 有 _meta.last_update 且比 existing 更新？→ 用它（消除顶层/子级时间不同步）
            if obj and isinstance(obj, dict):
                meta_last = (obj.get("_meta") or {}).get("last_update") or ""
                if meta_last and meta_last > existing:
                    return meta_last
            return existing
        if mtime_ts:
            return mtime_ts
        return now_ts

    if isinstance(lite_obj, list):
        # 顶层数组：包装成 dict（同步 sync_v6_to_v8 规则）
        lite_obj = {"data": lite_obj, "update_time": _pick_ts(None), "republish_time": now_ts}
    elif isinstance(lite_obj, dict):
        existing = lite_obj.get("update_time") or lite_obj.get("calc_time") or ""
        lite_obj["update_time"] = _pick_ts(existing, lite_obj)
        # republish_time = 本次构建/重部署时间，仅用于排障与缓存戳，前端不得当作「数据时间」展示
        lite_obj["republish_time"] = now_ts

    # ★★ 2026-08-18 主人令「每次更新部署都是错的」根因根治：构建幂等化 ★★
    #   死循环机制（今日 359 提交实证）：
    #     republish_time 每轮构建必变 → 69 个 data/*.js 文件内容每轮必变 →
    #     build 提交 → 触发 cache_buster_reconcile → 改 index.html ?v → 再触发 build
    #     → 无限循环，每次部署都错。
    #   修复：写文件前先与现有文件比较「中性化 republish_time 后」的内容，
    #    真实数据未变则跳过重写（republish_time 保持旧值）→ git diff 为空 →
    #    build 不提交 → 死循环断开。?v 中性化逻辑与 _sha10 完全一致。
    try:
        if out_path.exists():
            old_text = out_path.read_text(encoding='utf-8')
            new_text = f"window.{var_name} = " + json.dumps(lite_obj, ensure_ascii=False, separators=(',', ':')) + ";\n"
            _neut = lambda t: re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', t)
            if _neut(old_text) == _neut(new_text):
                print(f"  ⏭️  {var_name} 数据未变，跳过重写（幂等）")
                return out_path
    except Exception:
        pass

    with open(out_path, "w", encoding='utf-8') as f:
        f.write(f"window.{var_name} = ")
        json.dump(lite_obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(";\n")
    return out_path


def _data_file_update_time(var_name):
    """获取 data/*.js 的 cache-busting 标记。

    ★ 2026-08-14 主人令永久修复（主站刷新慢根因）：
    原实现优先语义时间、mtime 晚则用 mtime——云端 build 每几分钟 republish 一次
    data 文件，mtime 每次都变 → index.html 里 73 个 ?v= 每次 build 全变 →
    浏览器/CDN 缓存全部失效 → 每次刷新都全量重下 10MB+ → 主站"刷新非常慢"。

    改为「内容哈希」：取文件内容 sha1 前 10 位。内容没变 → URL 不变 → 缓存命中；
    内容真变了（数据更新）→ 哈希变 → 只重下变化的文件。语义时间仅作可读性兜底。

    失败则回退到空字符串。空文件返回空字符串。

    ★ 2026-08-15 根治「build clobber reconcile / CI API 节流致次日 ?v 失配」：
    ?v 一律取自「即将提交到仓库的本地 data/<var>.js 文件本身」——本地文件即权威，
    ?v 与落库文件天然一致，不再依赖线上 API（CI 偶发节流会把回退值算成陈旧本地副本
    致失配），也不因 build 内部 reset/重跑竞态产生新旧内容错位。跨流水线的最终一致性
    （如 cn 单独推送的 5 个 extra 文件被别处再次更新）由独立 reconcile workflow
    （git blobs API 取线上真实内容）每 15 分钟自愈。
    """
    # ★ 2026-08-15 根治「build clobber reconcile / CI API 节流致次日 ?v 失配」：
    # ?v 一律取自「即将提交到仓库的本地 data/<var>.js 文件本身」——本地文件即权威，
    # ?v 与落库文件天然一致，不再依赖线上 API（CI 偶发节流会把回退值算成陈旧本地副本
    # 致失配），也不因 build 内部 reset/重跑竞态产生新旧内容错位。
    # 跨流水线的最终一致性（如 cn 单独推送的 5 个 extra 文件被别处再次更新）由独立
    # reconcile workflow（git blobs API 取线上真实内容）每 15 分钟自愈。
    path = DATA_DIR / f"{var_name}.js"
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding='utf-8')
        import hashlib
        # ★ 2026-08-15 根因修复（ALGO_TRACK ?v 长期失配 + 构建竞态）：
        # _write_js 每次构建都会注入 republish_time（=构建时刻），使同一份数据每
        # 构建一次文件内容都变 → ① ?v 每次都变、丧失缓存命中本意；
        # ② 构建被拒后 reset+重跑的竞态里，?v 与最终落库文件因 republish_time
        #   不同步而失配 → CDN 吐旧副本。
        # 修复：哈希前把 republish_time 的值中性化为空（仅构建时间戳、非数据本身），
        # 使 ?v 只随「真实数据」变化，构建时刻/竞态不再影响 ?v，彻底消除失配。
        neutral = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
        return hashlib.sha1(neutral.encode('utf-8')).hexdigest()[:10]
    except Exception:
        return ""


def _rewrite_index_html_cache_busters():
    """为 index.html 中 data/*.js 引用追加基于文件更新时间的 cache-busting 参数。

    核心用途：防止浏览器/CDN 在数据更新后继续返回旧 data/*.js（典型问题：
    AI市场速览已生成新数据，但页面仍显示旧时间戳）。
    只有文件本身的时间戳发生变化时，对应的 URL 才会变化，未变更文件保持原 URL。
    """
    idx_path = ROOT / "index.html"
    if not idx_path.exists():
        return
    html = idx_path.read_text(encoding='utf-8')
    # 🔴 2026-08-12 主人令修复：原 `[A-Z_]+` 不匹配含数字的变量名（V8_CAL/W52_HIGH/TOP10_DAILY）
    #   → 这些文件永远不加 ?v= 缓存戳 → 浏览器/CDN 永远缓存旧版 → 主站/本地都不更新！
    #   修复：加 0-9，匹配所有 data/*.js
    # 🔴 2026-08-15 根因修复：原正则不匹配 `<script src="..." defer></script>`，
    #   导致 index.html 里所有含 defer 的 data/*.js 缓存戳永远不更新，主站长期回旧版。
    #   改为捕获 tag 前缀/后缀，保留 defer 等全部属性。
    # 🔴 2026-08-15 根因修复（审计发现）：原正则只匹配 `<script src="data/X.js..."></script>` 整段，
    #   但 A2 懒加载把 4 个大文件改为 `var BIG=[{name,url:'data/X.js?v=...'}]` 里的字符串，
    #   正则漏掉 → 这些 ?v 永远是 A2 手填的旧值，CDN 长期吐旧副本（缓存戳失配，正是防覆盖铁律最忌）。
    #   改为全量匹配 index.html 中所有「带引号」的 data/X.js(?:\?v=...)? 出现
    #   （script 标签 / fetch / BIG 数组均引号包裹），统一按内容 sha1 重写 ?v。
    pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')

    def repl(m):
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        var_name = src.split('/')[-1].replace('.js', '')
        ts = _data_file_update_time(var_name)
        if ts:
            # 内容哈希（含字母数字）直接作为 ?v=
            return f'{q1}{src}?v={ts}{q2}'
        return m.group(0)

    new_html = pat.sub(repl, html)
    if new_html != html:
        idx_path.write_text(new_html, encoding='utf-8')
        print("✅ index.html cache-busting 参数已更新")


def _ensure_momentum_loader():
    """确保 index.html 含 STOCK_MOMENTUM_STATE.js 加载标签（构建机偶发以陈旧 checkout 重置
    index.html 会冲掉手动加的 head 标签，导致「个股动量状态」卡显示「数据不可用」）。
    每次构建强制补回；缓存戳逻辑随后为其写入正确的 ?v=。"""
    idx_path = ROOT / "index.html"
    if not idx_path.exists():
        return
    html = idx_path.read_text(encoding='utf-8')
    if "data/STOCK_MOMENTUM_STATE.js" in html:
        return  # 已存在（含 ?v 或刚注入），交给缓存戳逻辑处理
    tag = '<script src="data/STOCK_MOMENTUM_STATE.js" defer></script>'
    # 2026-08-20：原 marker 用 POTENTIAL_PICKS.js（已随「潜力挖掘→AI 预测」删除），
    # 改用同区块的 SENTIMENT_CYCLE.js 作为插入锚点，防止引用失效后行为漂移。
    marker = '<script src="data/SENTIMENT_CYCLE.js'
    if marker in html:
        html = html.replace(marker, marker + "\n    " + tag, 1)
    else:
        html = html.replace("</head>", tag + "\n</head>", 1)
    idx_path.write_text(html, encoding='utf-8')
    print("✅ 已补回 STOCK_MOMENTUM_STATE.js 加载标签（防构建冲掉）")


def _var_category(var_name):
    c = CATEGORY_MAP.get(var_name, "post_close")
    # 支持多类别（逗号分隔），如 "premarket,intraday"
    return [x.strip() for x in c.split(",")]


def _file_category(filename):
    var_name = DATA_SOURCES.get(filename)
    return _var_category(var_name) if var_name else []


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


def _load_js_var_file(path):
    """解析 data/*.js 形如 window.X = {...}; 或 IIFE 壳，返回 (var_name, obj) 或 (None, None)。

    2026-08-28 扩展：支持 IIFE 壳 window.X = (function(){ var data = {...}; ... })()
    （STOCK_MOMENTUM_STATE 等 OCR 产物用此格式），使 stamp_missing_update_time
    不再漏判这些文件。数组壳仍返回 (var, list)。
    """
    try:
        txt = path.read_text(encoding='utf-8')
    except Exception:
        return None, None
    m = re.search(r'window\.([A-Z0-9_]+)\s*=\s*', txt)
    if not m:
        return None, None
    var = m.group(1)
    body = txt[m.end():].rstrip()
    if body.endswith(';'):
        body = body[:-1]
    try:
        obj = json.loads(body)
        return var, obj
    except Exception:
        pass
    # IIFE 壳：window.X = (function(){ var data = {...}; ... })();
    m2 = re.search(r'var\s+data\s*=\s*(\{[\s\S]*?\})\s*;', txt)
    if m2:
        try:
            return var, json.loads(m2.group(1))
        except Exception:
            return var, None
    return var, None


def _is_raw_empty_or_stale(raw_path):
    """🆕 2026-09-05 cn 离线兜底：判空/占位。空则不重建 data/X.js（保留线上旧版）。
    返回 (is_empty, reason)。阈值保守，不误杀合法小产物（CRDS 带 scan_stats 空产物~200B 不误杀）。"""
    try:
        size = raw_path.stat().st_size
    except Exception:
        return (True, "文件不存在")
    if size < 30:
        return (True, f"文件过小({size}B)")
    try:
        obj = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception:
        return (True, "JSON 解析失败")
    if isinstance(obj, list) and len(obj) == 0:
        return (True, "顶层为空列表")
    if isinstance(obj, dict):
        if obj.get("validity") == "unknown":
            return (True, "数据源异常占位(validity=unknown)")
        mc = obj.get("market_context") or {}
        if obj.get("total_scanned") == 0 and mc.get("validity") not in ("ok", "good", "normal"):
            return (True, "0命中且数据源有效性异常")
        if set(obj.keys()) <= {"update_time"}:
            return (True, "仅含时间戳的占位对象")
    return (False, "")


# 🆕 2026-09-05 变量名→raw_data 文件名反向映射（供 RUNNER_STATUS 标 stale）
_VAR_TO_RAW = {v: k for k, v in DATA_SOURCES.items()}


def stamp_missing_update_time():
    """2026-08-22 主人令：为缺失 update_time 的 data/*.js 补入生成时间戳。

    目的：审计发现 9 个文件（HEALTH_CHECK / H_AUTO_BUY / MOMENTUM_FILTER / PORTFOLIO /
    PORTFOLIO_COST / BLOAT_CHECK / RUNNER_STATUS_HEALTH / STOCK_MOMENTUM_STATE /
    STOCK_MOMENTUM_STATE_V2）无 update_time 字段，无法纳入新鲜度监控。

    规则（不造假）：注入的是「文件真实生成时间」= mtime，非数据造假；无法解析为 dict
    的文件（数组壳/IIFE 壳）跳过；已有 update_time 的不动。幂等：补一次后下次构建即跳过。
    """
    stamp_count = 0
    for p in DATA_DIR.glob("*.js"):
        var, obj = _load_js_var_file(p)
        if not isinstance(obj, dict):
            continue
        if "update_time" in obj:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=CST).strftime("%Y-%m-%d %H:%M:%S")
        obj["update_time"] = mtime
        with open(p, "w", encoding='utf-8') as f:
            f.write(f"window.{var} = ")
            json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
            f.write(";\n")
        stamp_count += 1
        print(f"  🕒 补 update_time → {var} ({mtime})")
    if stamp_count:
        print(f"✅ 已为 {stamp_count} 个 data/*.js 补 update_time")


# 🆕 2026-09-05 主人令一劳永逸：运维看板全量覆盖 + 审计轨迹
def _expand_runner_status():
    """把 runner_status.json 的 modules 补全到 ALL_MODULE_NAMES 全量。
    已跑模块用其 status/msg；未跑模块标 skip（运维看板真实覆盖，不再只报跑过的若干）。"""
    p = RAW_DIR / "runner_status.json"
    if not p.exists():
        print("  ⏭️  runner_status.json 不存在，跳过 RUNNER_STATUS 补全")
        return
    try:
        src = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] runner_status.json 解析失败，跳过补全: {e}")
        return
    modules = src.get("modules", {}) or {}
    expanded = {}
    for name in ALL_MODULE_NAMES:
        if name in modules:
            expanded[name] = modules[name]
        else:
            expanded[name] = {"status": "skip", "msg": "本周期未运行（未出现在 runner_status）"}
        # 🆕 2026-09-05 cn 离线兜底：该模块 raw_data 空/占位 → 标 stale（数据源离线可见）
        _fname = _VAR_TO_RAW.get(name)
        if _fname:
            _rp = RAW_DIR / _fname
            if _rp.exists():
                _e, _r = _is_raw_empty_or_stale(_rp)
                if _e:
                    expanded[name] = {**expanded[name], "status": "stale",
                                      "msg": f"数据源离线/产物空：{_r}"}
    out = dict(src)
    out["modules"] = expanded
    out["_expanded"] = True
    out["_module_total"] = len(ALL_MODULE_NAMES)
    out["_module_run"] = len(modules)
    js_path = DATA_DIR / "RUNNER_STATUS.js"
    try:
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window.RUNNER_STATUS = ")
            json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
            f.write(";\n")
        print(f"  ✅ RUNNER_STATUS 补全 {len(modules)}/{len(ALL_MODULE_NAMES)} 模块")
    except Exception as e:
        print(f"  [WARN] 写出 RUNNER_STATUS.js 失败: {e}")


def _generate_audit_trail():
    """合并云端 audit_history.json（v8_daily_audit 22:30 CST 写）
    + 本机 audit_nightly.log（23:30 写 JSONL，可能不存在）为 AUDIT_TRAIL。"""
    history = []
    hp = RAW_DIR / "audit_history.json"
    if hp.exists():
        try:
            history = json.loads(hp.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = [history]
        except Exception as e:
            print(f"  [WARN] audit_history.json 解析失败: {e}")
            history = []
    nightly = []
    nl = RAW_DIR / "audit_nightly.log"
    if nl.exists():
        try:
            for line in nl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    nightly.append(json.loads(line))
                except Exception:
                    continue
        except Exception as e:
            print(f"  [WARN] audit_nightly.log 读取失败: {e}")
    latest = history[-1] if history else None
    return {
        "latest": latest,
        "history": history[-20:],
        "nightly": nightly,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _write_audit_trail_js(trail):
    js_path = DATA_DIR / "AUDIT_TRAIL.js"
    try:
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window.AUDIT_TRAIL = ")
            json.dump(trail, f, ensure_ascii=False, separators=(',', ':'))
            f.write(";\n")
        print(f"  ✅ 写出 AUDIT_TRAIL.js（latest={'有' if trail.get('latest') else '无'}, "
              f"history={len(trail.get('history', []))}, nightly={len(trail.get('nightly', []))}）")
    except Exception as e:
        print(f"  [WARN] 写出 AUDIT_TRAIL.js 失败: {e}")


def _post_build_extras():
    """🆕 2026-09-05：build 后补 RUNNER_STATUS 全量 + AUDIT_TRAIL（供运维看板消费）。"""
    print("  🔧 生成运维 extras（RUNNER_STATUS 全量 + AUDIT_TRAIL）...")
    _expand_runner_status()
    _write_audit_trail_js(_generate_audit_trail())



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
        affected_cats = set()
        for p in changed:
            affected_cats.update(_file_category(p.name))
        print(f"🔍 detect_changes 模式：变化 raw_data {len(changed)} 个，涉及类别 {sorted(affected_cats) or '无'}")
        if not affected_cats:
            print("   无受影响的类别，跳过构建。")
            return 0
        target_files = [p for p in files if set(_file_category(p.name)) & affected_cats]
    elif category:
        print(f"🔍 category={category}（{CATEGORY_LABEL.get(category, category)}） selective build")
        target_files = [p for p in files if category in _file_category(p.name)]
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
        # 🆕 2026-09-05 cn 离线兜底：空/占位产物跳过重建，保留线上旧版 data/X.js（不写空污染前端）
        is_empty, empty_reason = _is_raw_empty_or_stale(src_path)
        if is_empty:
            print(f"  ⏭️  {src_path.name} 判空/占位（{empty_reason}），跳过重建 data/{var_name}.js（保留线上旧版）")
            skipped += 1
            continue
        out_path = _write_js(var_name, obj)
        updated += 1
        print(f"  ✅ {src_path.name} → {out_path.name}")

    print(f"\n完成：更新 {updated} 个，跳过 {skipped} 个。输出目录：{DATA_DIR}")
    return 0


def run_health_check():
    """构建完成后生成 data/HEALTH_CHECK.js，供前端健康面板渲染。"""
    hc_path = Path(__file__).resolve().parent / "v8_health_check.py"
    if not hc_path.exists():
        return
    try:
        # 显式继承当前进程环境（GHA 上的 secrets.GITHUB_TOKEN 等），防 subprocess 默认过滤
        subprocess.run(
            [sys.executable, str(hc_path)],
            check=False, timeout=300,
            env=os.environ.copy(),
        )
    except Exception as e:
        print(f"[WARN] 健康检查调用失败: {e}")


def run_experiment_cards():
    """2026-08-13 主人令：暂未上架三张新卡（涨价弹性榜/情绪周期/潜力挖掘）随数据刷新自动重算。
    三脚本读 data/*.js（build 刚生成的），写 data/COMMODITY_ELASTICITY.js 等。
    2026-08-16 主人令：新增动量共识筛选器（momentum_common_filter.py --emit-js →
    data/MOMENTUM_FILTER.js），与动量卡一起跟踪。
    2026-08-20 主人令：潜力挖掘页已删除 → calc_potential_picks.py 从实验链路移除。
    任何模块失败不阻断主流程（仅告警），避免拖垮云端抓取。
    """
    import subprocess
    algo_dir = Path(__file__).resolve().parent / "algorithms"
    for script in ("calc_commodity_elasticity.py", "calc_sentiment_cycle.py"):
        path = algo_dir / script
        if not path.exists():
            print(f"[experiment] ⚠️ 缺失 {script}，跳过")
            continue
        print(f"[experiment] ▶ {script} ({datetime.now():%H:%M:%S})")
        try:
            r = subprocess.run([sys.executable, str(path)], cwd=str(algo_dir),
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"[experiment]   ✅ {last[0][:80]}")
            else:
                print(f"[experiment]   ⚠️ {script} 退出码 {r.returncode}")
                print("     " + "\n     ".join(r.stdout.strip().splitlines()[-2:] + r.stderr.strip().splitlines()[-2:])[:300])
        except Exception as e:
            print(f"[experiment]   ⚠️ {script} 异常: {e}")

    # 2026-08-22 主人令·脱离PDF：先由「H反推升级算法」(涨幅≥3%+量比≥1.2+突破+RS) 自选强势突破
    # + 重算 V2 动量（写 data/STOCK_MOMENTUM_STATE.js / STOCK_MOMENTUM_STATE_V2.js），
    # 再跑 momentum_common_filter 消费 V2。顺序不可颠倒。
    momentum_self_py = Path(__file__).resolve().parent / "scripts" / "gen_strong_breakout.py"
    if momentum_self_py.exists():
        print(f"[experiment] ▶ gen_strong_breakout.py ({datetime.now():%H:%M:%S})")
        try:
            r = subprocess.run([sys.executable, str(momentum_self_py)],
                               capture_output=True, text=True, timeout=1800)
            if r.returncode == 0:
                last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"[experiment]   ✅ {last[0][:80]}")
            else:
                print(f"[experiment]   ❌ gen_strong_breakout 退出码 {r.returncode}")
                print("     " + "\n     ".join(r.stdout.strip().splitlines()[-4:] + r.stderr.strip().splitlines()[-4:])[:500])
                # 🔴 2026-08-31 07:0x 一劳永逸修复（开盘前紧急，实测 build_deploy 连续 3 次 failure 坐实）：
                #   08-29 的「硬化」把两种性质完全不同的失败混为一谈：
                #     (a) [time_gate] 数据未就绪（需 ≥15:30 CST）—— 凌晨/盘前跑批时的**设计内**状态，
                #         此刻 A 股当日数据本来就不存在，属预期；
                #     (b) 回测数据造假（data_available=false 全 0）—— 真故障，必须阻断。
                #   原实现无差别 raise → 每次凌晨 push 触发 build_deploy 都在 step 8 中断，
                #   导致 data/*.js 明明已更新 57 个却**不部署**（step 9/10 skipped），
                #   夜间抓取的新数据全部卡在本地不上线，线上长期停留在上一交易日。
                #   实测证据：run 33329876518 / 33324547960 / 33321855111 三连 failure，
                #   报错均为 `🚫 [time_gate] A股 数据未就绪（需 ≥ 15:30 CST，当前 03:07）`。
                #   ⇒ (a) 降级为告警并跳过该实验卡，保留其余 data/*.js 正常部署；
                #     (b) 仍照旧 raise，不放松「拒绝发布虚假回测」的红线。
                _sb_out = (r.stdout or "") + "\n" + (r.stderr or "")
                if "[time_gate]" in _sb_out:
                    print("[experiment]   ⏭️ 识别为【时间门控未就绪】——非数据造假，属设计内状态；"
                          "跳过本卡，其余 data/*.js 照常部署（15:30 后本轮会自然产出真实数据）")
                else:
                    # 🛡 2026-08-29 硬化：动量 V2 回测数据必须真实，禁止「data_available=false 全 0」继续发布。
                    #   直接抛异常让 update_v8 / build 失败，触发重试或人工介入。
                    raise RuntimeError(f"gen_strong_breakout 失败（退出码 {r.returncode}），拒绝发布虚假回测")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            print(f"[experiment]   ⚠️ gen_strong_breakout 异常: {e}")
    else:
        print("[experiment] ⚠️ 缺失 scripts/gen_strong_breakout.py，跳过")

    # 2026-08-16 主人令：动量共识筛选器（读 data/STOCK_MOMENTUM_STATE_V2.js + STOCK_QUOTE + SECTOR_RS）
    filter_py = Path(__file__).resolve().parent / "scripts" / "momentum_common_filter.py"
    if filter_py.exists():
        print(f"[experiment] ▶ momentum_common_filter.py --emit-js ({datetime.now():%H:%M:%S})")
        try:
            r = subprocess.run([sys.executable, str(filter_py), "--emit-js"],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"[experiment]   ✅ {last[0][:80]}")
            else:
                print(f"[experiment]   ⚠️ momentum_common_filter 退出码 {r.returncode}")
                print("     " + "\n     ".join(r.stdout.strip().splitlines()[-2:] + r.stderr.strip().splitlines()[-2:])[:300])
        except Exception as e:
            print(f"[experiment]   ⚠️ momentum_common_filter 异常: {e}")
    else:
        print("[experiment] ⚠️ 缺失 scripts/momentum_common_filter.py，跳过")

    # 2026-08-23 主人令：两套算法（H反推 vs 强势突破）回测横向对比，统一口径产出
    # data/ALGO_BACKTEST_COMPARE.js（无网络依赖，纯聚合既有产物；失败不影响主流程）
    compare_py = Path(__file__).resolve().parent / "scripts" / "algo_backtest_compare.py"
    if compare_py.exists():
        print(f"[experiment] ▶ algo_backtest_compare.py ({datetime.now():%H:%M:%S})")
        try:
            r = subprocess.run([sys.executable, str(compare_py)],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"[experiment]   ✅ {last[0][:120]}")
            else:
                print(f"[experiment]   ⚠️ algo_backtest_compare 退出码 {r.returncode}")
        except Exception as e:
            print(f"[experiment]   ⚠️ algo_backtest_compare 异常: {e}")
    else:
        print("[experiment] ⚠️ 缺失 scripts/algo_backtest_compare.py，跳过")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="v8 data builder")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "weekly"],
                        help="只构建某一时段类别")
    parser.add_argument("--detect-changes", action="store_true",
                        help="只构建最近 git diff 发生变化的 raw_data 所属类别")
    parser.add_argument("--only-cache-busters", action="store_true",
                        help="仅重写 index.html 的 data/*.js ?v 缓存戳（基于本地文件内容哈希），不重建任何数据。"
                             "供 v8_cache_buster_reconcile（兜底自愈）/ v8_build_deploy（提交前守卫）/"
                             "生成器 workflow（原子提交 ?v）三处复用同一套权威 ?v 逻辑，彻底消除各 workflow 各算各的导致的失配。")
    args = parser.parse_args()
    # 🛡 2026-09-02 一劳永逸根治「?v 缓存戳失配」：新增 --only-cache-busters 独立开关。
    #   只重写 index.html 的 data/*.js ?v（基于本地文件内容哈希），不重建任何数据。
    #   供 v8_cache_buster_reconcile（兜底自愈）/ v8_build_deploy（提交前守卫）/
    #   生成器 workflow（原子提交 ?v）三处复用同一套权威 ?v 逻辑，彻底消除"各 workflow
    #   各算各的"导致的失配。
    if args.only_cache_busters:
        _ensure_momentum_loader()
        _rewrite_index_html_cache_busters()
        print("✅ 仅重写 ?v 完成（未重建数据）")
        return 0
    rc = build(category=args.category, detect_changes=args.detect_changes)
    if rc == 0:
        run_health_check()
        run_experiment_cards()
        # 2026-08-22 主人令：为缺 update_time 的 data/*.js 补时间戳（须在全部生成之后）
        stamp_missing_update_time()
        # 🆕 2026-09-05 主人令：build 后补 RUNNER_STATUS 全量 + AUDIT_TRAIL
        _post_build_extras()
        # 2026-08-15 缓存戳铁律修复：必须在全部数据生成（含 run_experiment_cards
        # 重写的 COMMODITY_ELASTICITY.js 等）之后才算 ?v，否则 ?v 与最终文件内容
        # 不符 → CDN 吐旧副本。
        _ensure_momentum_loader()
        _rewrite_index_html_cache_busters()
    return rc


if __name__ == '__main__':
    sys.exit(main())
