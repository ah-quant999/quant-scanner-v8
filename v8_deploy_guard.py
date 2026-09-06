#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 部署前产物校验（防空 raw_data 把 good data 覆盖成 shell 致整站空）

规则：
- 关键 data/*.js 必须存在且字节数 >= 阈值（阈值远小于正常体积，只拦 shell/空文件）。
- 首行必须是 `window.<NAME> =` 形式（非报错页/空文件）。
- 全部 data/*.js 合计必须 >= 1MB（防止大面积被 shell 覆盖）。
- 任一不达标 -> exit 1，CI 据此阻断部署，保留上一次 good data。
依赖：仅标准库
"""
import sys
import re
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

MIN_SIZE = {
    "FINAL_RECOMMEND_DATA.js": 8000,
    "CANDIDATE.js": 60000,
    "STOCK_RPS.js": 60000,
    "SECTOR_FUND_FLOW.js": 8000,
    "TOP10_DAILY.js": 4000,
    "STOCK_QUOTE.js": 100000,
    "CANDIDATE_QUOTES.js": 8000,
    "GOLD_POOL.js": 8000,
    "LHB_DATA.js": 8000,
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST.js / COCKPIT_TIER_RECOMMEND.js 尺寸阈值已删（驾驶舱模块下线）
    "JUDGMENT_DATA.js": 576,
    "V8_CAL.js": 1754,
    "CRISIS_DATA.js": 331,
    "MACRO_BRIEF.js": 492,
    "SENTIMENT_CYCLE.js": 392,
    "RISK_GAUGE.js": 741,
    "LIMIT_UP_HEATMAP.js": 748,
    "OVERSEAS_MARKETS.js": 360,
    "MARKET_ALERTS.js": 319,
    "AVG_PRICE_DATA.js": 307,
    "INST_TRADE.js": 4756,
    "IPO_DATA.js": 7655,
    "LHB_7D.js": 1826,
    "LHB_HISTORY.js": 295035,
    "SECTOR_FUND_FLOW_TREND.js": 3378,
    "SECTOR_RS.js": 21907,
    "STOCK_LIST.js": 628871,
    "STOCK_PROFILE.js": 222906,
    "STOCK_STOP_DATA.js": 8526,
    "TRIPLE_CONSENSUS.js": 2193,
    "TRIPLE_TRACK.js": 2234,
    "TRIPLE_HISTORY.js": 563,
    "MARKET_FUND_FLOW_DATA.js": 8950,
    "MARGIN_DATA.js": 2680,
    "ETF_SUBSCRIPTION.js": 3292,
    "ETF_INTRADAY_HEAT.js": 7911,
    "CONCEPT_RANKING.js": 2461,
    "CONCEPT_ETF_MAP.js": 3564,
    "COMMODITY_ELASTICITY.js": 2126,
    "CAPITAL_FLOW_DATA.js": 1195,
    "BACKTEST_TDX.js": 1350,
    "BACKTEST_COMPREHENSIVE.js": 1395,
    "OPTIMIZED_STRATEGY.js": 342,
    "INDEX_QUOTES.js": 348,
    "FOUR_VOLUME.js": 669,
    "FOUR_VOLUME_60M.js": 895,
    "VOLATILITY.js": 716,
    "NT_DATA.js": 628,
    "ANALYST_RATINGS.js": 1076,
    "SH_SZ_HISTORY.js": 5755,
    "CFFEX_HOLDINGS.js": 1773,
    "ETF_PULSE.js": 371,
    "SUSPENSION_ALERT.js": 448,
    "W52_HIGH.js": 312,
    "SH_FIB.js": 750,
    "SZ_FIB.js": 769,
    "MACRO_DATA.js": 823,
    "EXPERIMENT.js": 961,
    "CRDS_CARD_DATA.js": 11284,
    "HEALTH_CHECK.js": 3972,
    "RUNNER_STATUS.js": 442,
    "RUNNER_STATUS_HEALTH.js": 93,
    "PORTFOLIO.js": 426,
    "PORTFOLIO_COST.js": 383,
    "HERDING_DATA.js": 203,
    "NORTH_FUND.js": 94,
    "WEEKEND_RUN.js": 89,
    "WEEKEND_META_REPORT.js": 106
}
MIN_TOTAL = 1000000

def _strip_js_comments(s):
    """剥离 JS 注释，使含 // 行注释或 /* */ 块注释的合法 JSON 数据能被 json.loads 解析。
    2026-08-28 根因修复：data/*.js 末尾常残留人工/管线留下的 `// fix` 等注释，
    旧逻辑直接 json.loads 遇 // 注释即抛错，把合法空占位符/真实数据误判成 shell，
    触发部署前校验失败阻断全部构建。剥离注释后，有 window.X= 且主体为合法 JSON 一律放行。
    保留 http:// https://（负向后查 : 前的 // 不剥），避免误伤 URL。
    """
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    # 行注释：仅当 // 位于行首(可含前导空白)或紧跟空白字符时剥离，
    # 避免误伤 JSON 字符串内的 //（如 http:// 或 "x//y"）。
    # 2026-08-28 根因补丁：旧正则 (?<!:)// 会误删字符串值中的 //，
    # 且本函数必须在 rstrip(";") 之前调用，否则 // fix 在 ; 之后致 json 解析失败。
    s = re.sub(r"(?m)(?:(?<=^)|(?<=\s))//[^\n\r]*", "", s)
    return s


def _is_valid_js_data(text):
    """判定 data/*.js 是否为合法 JSON 数据（非 shell/错误页）。

    合法：含 `window.<NAME> =` 且其后内容能解析为 JSON 对象/数组。
    真 shell：HTML 错误页 / null / undefined / 截断 / 报错字符串，绝不合法 JSON。

    2026-08-17 修复背景：系统会刻意产出两类「体积偏小但合法」的文件，
    旧逻辑用固定 MIN_SIZE 阈值把它们误判成 shell，导致全部构建被拦截部署、
    实时数据卡死数小时：
      (a) 盘前清空/无信号占位符：{"no_data":true,"premarket_cleared":true,...}
          或 {"total":0,"stocks":[]}
      (b) 天然偏小的真实数据：CRDS(少数股) / STOCK_STOP(15只) /
          TRIPLE_CONSENSUS(count:0) —— 都是有效 JSON，仅样本少。
    故「过小」不再直接判 shell，仅当「过小且无法解析为合法 JSON」才拦截。
    """
    m = re.search(r"window\.[A-Z_0-9]+\s*=\s*(.*)", text, re.S)
    if not m:
        return False
    # 2026-08-28 根因补丁：必须先剥 JS 注释再 rstrip(";")。
    # 旧顺序下 body 形如 `{...};\n// fix`，rstrip(";") 因尾部是 \n 剥不到 ;，
    # 注释剥离后残留 `;` 致 json.loads 抛错、合法数据被误判成 shell 阻断全部构建。
    body = _strip_js_comments(m.group(1))
    body = body.strip().rstrip(";").strip()
    if not body:
        return False
    try:
        json.loads(body)
        return True
    except Exception:
        return False


bad = []
actual_total = 0
for p in sorted(DATA.glob("*.js")):
    name = p.name
    sz = p.stat().st_size
    actual_total += sz
    if name not in MIN_SIZE:
        continue
    mn = MIN_SIZE[name]
    if sz < mn:
        # ★ 2026-08-17 修复：尺寸过小不再直接判 shell。
        #   仅当「小且无法解析为合法 JSON」才是真 shell（HTML错误页/null/截断）。
        #   合法空占位符与天然偏小真实数据均含合法 JSON，放行。
        text = p.read_text(encoding="utf-8", errors="ignore")
        if _is_valid_js_data(text):
            print(f"   ℹ️ {name}: {sz}B 合法 JSON(空占位符或天然小数据)，放行")
            continue
        bad.append((name, sz, mn, "过小且非合法JSON(疑似shell)"))
        continue
    # 2026-08-14 修复：部分文件首行是注释（CONCEPT_ETF_MAP/PORTFOLIO/PORTFOLIO_COST），
    # 且变量名可能与文件名不一致（PORTFOLIO.js → window.PORTFOLIO_DATA）。
    # 首行 startswith("window.") 会误伤 → 改为全文正则匹配任意 `window.<NAME> =` 赋值。
    text = p.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"window\.[A-Z_0-9]+\s*=", text):
        bad.append((name, sz, mn, "无 window.<NAME> = 赋值(格式异常)"))

if actual_total < MIN_TOTAL:
    bad.append(("ALL data/*.js total", actual_total, MIN_TOTAL, "总体积过小(大面积shell)"))

if bad:
    print("X 部署前校验失败，疑似空/陈旧 raw_data 生成 shell，阻断部署：".replace("X","❌"))
    for name, sz, mn, why in bad:
        print(f"   {name}: {sz}B ({why}, 阈值 {mn}B)")
    sys.exit(1)

print(f"OK 部署前校验通过：{len(MIN_SIZE)} 个关键产物均非空，data/*.js 总体积 {actual_total}B".replace("OK","✅"))
