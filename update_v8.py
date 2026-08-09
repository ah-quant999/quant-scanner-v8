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
    "sector_fund_flow.json":       "SECTOR_FUND_FLOW",
    "sector_fund_flow_trend.json": "SECTOR_FUND_FLOW_TREND",
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
    "ai_market_brief.json":        "AI_MARKET_BRIEF",
    "runner_status.json":          "RUNNER_STATUS",
    "risk_gauge.json":             "RISK_GAUGE",
    "stock_quote.json":            "STOCK_QUOTE",
    "avg_price_data.json":         "AVG_PRICE_DATA",
    "weekend_meta_report.json":      "WEEKEND_META_REPORT",
    "delisted_stocks.json":        "DELISTED_STOCKS",
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
    "CRISIS_DATA": "premarket,intraday",
    "NORTH_FUND": "premarket",
    "ANALYST_RATINGS": "premarket",
    "SUSPENSION_ALERT": "premarket",
    "MARKET_ALERTS": "intraday",
    "W52_HIGH": "premarket",
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
    "SECTOR_FUND_FLOW": "intraday",
    "CAPITAL_FLOW_DATA": "intraday",
    "CONCEPT_RANKING": "intraday",
    "LIMIT_UP_HEATMAP": "intraday",
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
    "COCKPIT_TIER_RECOMMEND": "post_close",
    "COCKPIT_ADVICE": "post_close",
    "COCKPIT_BACKTEST": "post_close",
    "BACKTEST_TDX": "post_close",
    "BACKTEST_COMPREHENSIVE": "post_close",
    "MAHORO": "post_close",
    "EXPERIMENT": "post_close",
    "STOCK_LIST": "post_close",
    "STOCK_PROFILE": "post_close",
    "AVG_PRICE_DATA": "post_close",
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
    if name == 'IPO_DATA':
        # 校正 recommend + 自动补全 shadows（依赖 stock_names.json / candidate_quotes.json）
        return _build_ipo_shadows(obj)
    if name == 'W52_HIGH':
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        lite['_lite_note'] = 'stocks 完整列表已裁剪，仅保留 top_gainers 与 total'
        return lite
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
    """把被 status 污染的 recommend 字段按 score 重新映射为建议等级。"""
    rec = (stock.get("recommend") or "").strip()
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

    def _pick_ts(existing):
        """真实优先：源数据自带时间戳 > 源文件 mtime > 当前时间。

        2026-08-07 修（主人铁律「不得造假」）：原实现取 max(existing, mtime, now)，
        now_ts 永远最大 → 每次构建都把所有卡片的「更新于」刷成构建时刻，
        导致 ①「更新于」全是假时间 ②「今日已跑完」胶囊在开盘前判错（数据日期被
        改成今天，而交易日归上一日 → 胶囊隐藏）。禁止再改回 max。
        """
        if existing:
            return existing
        if mtime_ts:
            return mtime_ts
        return now_ts

    if isinstance(lite_obj, list):
        # 顶层数组：包装成 dict（同步 sync_v6_to_v8 规则）
        lite_obj = {"data": lite_obj, "update_time": _pick_ts(None), "republish_time": now_ts}
    elif isinstance(lite_obj, dict):
        existing = lite_obj.get("update_time") or lite_obj.get("calc_time") or ""
        lite_obj["update_time"] = _pick_ts(existing)
        # republish_time = 本次构建/重部署时间，仅用于排障与缓存戳，前端不得当作「数据时间」展示
        lite_obj["republish_time"] = now_ts

    with open(out_path, "w", encoding='utf-8') as f:
        f.write(f"window.{var_name} = ")
        json.dump(lite_obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(";\n")
    return out_path


def _data_file_update_time(var_name):
    """获取 data/*.js 的 cache-busting 时间戳。

    优先读取文件内容中的 update_time/updated/run_time/calc_time（语义稳定），
    失败则回退到文件 mtime。空文件返回空字符串。
    """
    path = DATA_DIR / f"{var_name}.js"
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding='utf-8')
        for key in ('"update_time":"', '"updated":"', '"run_time":"', '"calc_time":"'):
            m = re.search(re.escape(key) + r'([^"]+)"', text)
            if m:
                return m.group(1)
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=CST).strftime("%Y-%m-%d %H:%M:%S")
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
    pat = re.compile(r'<script src="(data/[A-Z_]+\.js)(?:\?[^"]*)?"></script>')

    def repl(m):
        src = m.group(1)
        var_name = src.split('/')[-1].replace('.js', '')
        ts = _data_file_update_time(var_name)
        if ts:
            ts_compact = re.sub(r'[^\d]', '', ts)
            return f'<script src="{src}?v={ts_compact}"></script>'
        return m.group(0)

    new_html = pat.sub(repl, html)
    if new_html != html:
        idx_path.write_text(new_html, encoding='utf-8')
        print("✅ index.html cache-busting 参数已更新")


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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="v8 data builder")
    parser.add_argument("--category", choices=["premarket", "intraday", "post_close", "weekly"],
                        help="只构建某一时段类别")
    parser.add_argument("--detect-changes", action="store_true",
                        help="只构建最近 git diff 发生变化的 raw_data 所属类别")
    args = parser.parse_args()
    rc = build(category=args.category, detect_changes=args.detect_changes)
    if rc == 0:
        run_health_check()
        _rewrite_index_html_cache_busters()
    return rc


if __name__ == '__main__':
    sys.exit(main())
