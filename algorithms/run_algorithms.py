#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_algorithms.py — v8 本地/自托管 cn runner 的盘后算法编排器

流程：
  0) v8 原生化自产「上游输入」到 仓库根/out/（gold_pool / scan_result / watch_result /
     guanlan_*），由 scanner.py / guanlan_extractor.py 经 V8_OUT_DIR 钩子产出，彻底脱离 v6.
     （设 V6_SEED=1 可强制回退到 v6 重灌，仅用于应急。）
  1) 按依赖顺序运行 v8/algorithms/ 下的算法脚本（各自写 out/，沿用 v6 文件名）。
  2) stage_to_raw：按 V6_TO_V8 重命名为 raw_data/（v8 命名）+ 注入 update_time。
  3) 若 V8_PUSH=1：调用 api_push_raw.py 经 API 推送 raw_data 到 main。

每个脚本失败不影响其余（continue-on-error），与云端 fetch 行为一致。
"""
import os
import re
import subprocess
import time
import threading

# 🔴🔴 2026-09-17 阿狸咪（拍-8 落地）：cn runner（Windows）默认 GBK 终端 ⇒
#   本编排器拉起的子脚本若 print emoji/中文，会在子进程里抛
#   UnicodeEncodeError('gbk') 崩掉整条盘后链（实测「整条 19:15 链 0 执行」）。
#   修法用**模块级自举**而非逐点给 subprocess 传 env= —— 本文件有 9 处
#   subprocess 调用点（Popen / run），逐点改必漏；而 os.environ 会被**所有**
#   未显式传 env= 的子进程继承 ⇒ 一处生效、全域覆盖，最彻底。
#   （job env 层已在 3 个 [self-hosted, cn] workflow 补同名变量，此处为兜底。）
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass   # 老 Python(<3.7) 或 stdout 被替换为非 TextIOWrapper：静默兜底，不阻断

# ── 单脚本超时（2026-08-31 一劳永逸修复）──────────────────────────────────
# 背景：原代码把 1800s 硬编码在两处 subprocess.run，实测 run 33316835316 中
#   某些脚本网络重活可能超时，故默认阈值可配并允许单脚本放宽。
# 修法：默认阈值可配（V8_ALGO_TIMEOUT），并给重活单独放宽，不影响其他脚本。
import os as _os

DEFAULT_SCRIPT_TIMEOUT = int(_os.environ.get("V8_ALGO_TIMEOUT", "1800"))

# 计算量大 / 网络重活单独放宽（秒）。新增重活在此登记即可，无需改调度代码。
SCRIPT_TIMEOUT_OVERRIDE = {
    # 🛡 2026-09-11 一劳永逸：2700s(45min) 实测不足 —— run#1692 于 05:22 起跑、06:07 被
    #   「超时 >45min」杀掉 → 无产物 → B 批 2/3 → target_stage 恒为 B → D/E 永不执行
    #   （FINAL_RECOMMEND_DATA 停在昨日的结构性真凶）。放宽到 90min 留足余量。
    "calc_crds.py": 5400,        # 逆势龙头 CRDS（全池遍历，实测需 >45min）
    # 2026-09-18：backtest_tdx 产品产物不再含逐笔明细（体积根治），续跑明细缓存
    #   raw_data/_tdx_cache/ 被 .gitignore 排除 ⇒ 云端 runner 每轮需全量重取 221 只日K
    #   （原先靠复用上轮明细仅 ~40s）。给足 90min 总预算，防被 30min 默认超时误杀而再次停更。
    "backtest_tdx.py": 5400,
    "gen_stock_profile.py": 2700,
    "factor_lab_backtest.py": 1800,  # 🆕 700日长历史抓取+五分位分层回测（cn ~5min / 云端 ~15min）
    # 🛡 2026-09-07 一劳永逸：H 反推对「全市场涨幅≥3%」的数百只逐只取前 4 日均量。
    #   原为串行逐只 HTTP（云端抓中国源必挂）→ 30min 被 kill → 产物文件写不出来
    #   → track 兜底读旧 H_AUTO_BUY.js → 前端卡冻结 3 天（09-05~09-07 事故）。
    #   现已改为「本地缓存优先 + 三级兜底链 + 16 线程并发」，实测分钟级；此处登记
    #   显式预算 2400s，避免冷缓存首轮（缓存未命中、全走网络）时再被误杀。
    "auto_run_dn_algorithm.py": 2400,
    # 🛡 2026-09-08 全链审计补登：以下重活此前未登记，走默认 1800s 易被误杀
    #   （被杀 = 产物写不出 = 下游读旧文件 = 静默断更，与 H_AUTO_BUY 同类）。
    "gen_stock_stop.py": 2400,             # 147~200 只逐只 250 根 K 线（已改并发，冷网络留足预算）
    "fetch_fundamental_quality.py": 5400,  # 🛡 2026-09-09 并发根治：单线程串行 baostock 必超 40min 预算被杀→盘后选股链整瘫；改 ProcessPoolExecutor(12) 后实测分钟级，预算放宽到 90min 留足余量
    "refresh_dividend_cninfo.py": 2400,    # ~500 只 × cninfo ×3 重试，无超时
    "fetch_lhb.py": 2400,                  # 逐股 ×2flag ×3attempt 东财 akshare
    "build_candidate_pool.py": 2400,       # missing[:200] 串行东财补全行业
    "fetch_sector_rs.py": 1800,            # ~90 同花顺板块串行
    "calc_volatility_watch.py": 1800,      # 多源兜底，源慢时串行拉长
    # 🛡 2026-09-08 D2-A2 挂链补登：因子实验室生成器（v8/factor_lab_gen.py）此前零调度成孤儿
    #   —— 2026-09-07 主人令已把它「从 D 摘到 E 批」，但只写在注释里，STAGES["E"]/ORDER 均未挂，
    #   导致 data/FACTOR_LAB.js 长期无人刷新（运维暗灯）。现正式挂链并给足冷启动预算
    #   （脚本自述冷启动 50-90min；热缓存后分钟级）。
    "v8/factor_lab_gen.py": 5400,
    "v8/backtest_crds.py": 3600,            # CRDS 回测：逐只回测，给 1h 预算 （2026-09-09 挂链时补）
    # 🛡 2026-09-11 一劳永逸（主人令·选项A）：四量终极 60min 此前**未登记预算** → 走默认 1800s。
    #   它是全链少数走 baostock 独立数据源 + 逐只拉 120 根 60min K 线的脚本（冷缓存慢），
    #   240 只逐只取数在源抖动时极易超过 30min → 被监督器硬超时杀 → 产物写不出。
    #   注意：被杀与「源不可用秒退」是两种不同故障，登记预算只解决前者，后者由
    #   ScanUnavailable 硬失败上报（见该脚本 main()）。给足 90min 余量。
    "strategy_four_volume_60m.py": 5400,
    # 🛡 2026-09-16 阿狸咪的工程师 · 修「5 年版未登记预算」（D7 配套）：
    #   日线版同样逐只取数，且 E 批经 SCRIPT_ENV 注入 V8_BACKTEST_YEARS=5 ⇒ bars >= 1500 全池回测，
    #   实测 > 15min（run 35006805941 实证）。此前未登记 ⇒ 走默认 1800s，与 60min 版同档补 90min。
    #   ⚠️ 总预算与静默阈值是两把锁（见 SILENCE_OVERRIDE），缺任何一把仍会被杀。
    "strategy_four_volume.py": 5400,
    # 🛡 2026-09-11 一劳永逸：以下 5 个实验/研究卡脚本从 v8_cn_fetch_experiments.yml
    #   正式收编进 B 批链尾（详见 ORDER / STAGES["B"] 注释）。均为纯本地计算或
    #   单接口调用（不遍历全 universe），给 900s 足够余量；显式登记避免走默认 1800s
    #   而在极端网络退避下拖长 B 批（B 批在 D 批 20:00 关键路径上）。
    "scripts/gen_factor_audit.py": 900,             # 读 generate_top10.py 源码做静态审计，纯本地
    "scripts/gen_factor_progress.py": 900,          # 读 factor_audit.json，纯本地
    "scripts/fetch_valuation_percentile.py": 1200,  # akshare stock_index_pe_lg（理杏仁），单接口
    "scripts/fetch_index_value_framework.py": 900,  # 读本地 INDEX_HISTORY.js + numpy 计算
    # 🆕 2026-09-11：全算法回测汇总——纯本地读 data/*.js + raw_data/algo_track.json，零网络
    "gen_market_bench.py": 900,   # 🆕 2026-09-17：3120 只×250 根纯本地计算（交接单口径 timeout 900s）
    "gen_backtest_all_algos.py": 900,
    # 🆕 2026-09-15 主人令（四量终极「自己的一整套系统」）：两个脚本均为**纯本地计算**——
    #   history 读 data/FOUR_VOLUME.js + raw_data/stock_quote.json（全市场快照，一次载入、
    #   按 code 建索引，不逐只网络请求）；track 读账本 + 本地 json，零网络。
    #   与三重同族给出 900s 显式预算（避免走默认 1800s 拖长 B 批，B 批在 D 批 20:00 关键路径上）。
    "update_four_volume_history.py": 900,
    "gen_four_volume_track.py": 900,
}


def _script_timeout(script_name):
    """返回该脚本的超时秒数（覆盖表优先，其次环境变量，最后默认）。"""
    return int(SCRIPT_TIMEOUT_OVERRIDE.get(script_name, DEFAULT_SCRIPT_TIMEOUT))


import sys
import json
from datetime import datetime

# 本轮失败/超时脚本清单（供链尾闸门与运维面板消费）
# 🛡 2026-08-28 一劳永逸：过去只在 stdout 打一行「⚠️ 退出码 N」，无人看、无汇总、无告警，
#   导致候选池停更 1.9 天仍无人知晓。现统一收集并落盘 raw_data/algo_run_report.json。
FAILED_SCRIPTS = []

ALGO = os.path.dirname(os.path.abspath(__file__))
V8_ROOT = os.path.dirname(ALGO)
sys.path.insert(0, V8_ROOT)
import v8_date  # v8 统一交易日历/数据日期中枢
# ⚠️ out 目录必须与被迁移脚本的 os.path.join(BASE, "..", "out") 口径一致：
#   脚本 BASE = algorithms/，故 BASE/../out = 仓库根/out（不是 algorithms/out）。
#   原来这里写 ALGO/out 与脚本对不上 → reseed 灌到 algorithms/out 而脚本读仓库根/out → 全链找不到输入。
OUT = os.path.join(V8_ROOT, "out")
#   回测永远只有当天/为空。stage_to_raw 不会处理 history 子目录，故直接落 raw_data/history 由 api_push 整体推送。
HIST_OUT = os.path.join(V8_ROOT, "raw_data", "history")

V6_DATA_DIR = os.environ.get("V6_DATA_DIR", r"\E:\workspace\quant-scanner-v8\raw_data")
PY = os.environ.get("V8_PYTHON", "python")

# 本地测试可能传入 Git-Bash 风格路径（/c/Users/...），Windows CreateProcess 无法解析，
# 统一转成原生 Windows 路径（C:/...）。生产 runner 用原生 python，不受影响。
if PY.startswith("/") and len(PY) > 2 and PY[2] == "/":
    PY = re.sub(r"^/([a-zA-Z])/", lambda m: m.group(1).upper() + ":/", PY)

PUSH = os.environ.get("V8_PUSH", "0") == "1"

# 上游输入（v6 文件名）。2026-08-02 已原生化，正常不再从这里拉取；
# 仅当 V6_SEED=1 才回退使用（应急）。
INPUTS_FROM_V6 = [
    "gold_pool.json",
    "scan_result.json",
    "watch_result.json",       # calc_crds 的输入（逆势龙头候选），过渡期由 v6 scanner 供给
    "guanlan_watchlist.json",
    "guanlan_reports.json",
    "maharo_signals.json",
]

# 依赖顺序：先抓基础数据 → 回测/候选 → 顶层共识/分级
ORDER = [
    "fetch_fundamental_quality.py",   # → fundamental_quality（输入给 top10/triple*）
    "fetch_stock_names.py",
    # 🛡 2026-08-26 一劳永逸（对齐）：原 gen_stock_profile.py 仅被 cloud_fetch_v8 在 post_close
    #   副作用式调用，run_algorithms 算法链从不调度 → 本地跑/该步跳过时 stock_profile.json 陈旧，
    #   致 final_recommend 读脏数据。现正式挂链（仅依赖 stock_names），
    #   使算法链自洽、不依赖上游副作用。门控仍保留作安全网。
    "gen_stock_profile.py",            # → raw_data/stock_profile.json（个股行业/概念，最终推荐用）
    "fetch_stock_quote_v8.py",         # → raw_data/stock_quote.json + data/STOCK_QUOTE.js（全市场实时报价快照，查股功能用）
    "fetch_sh_index_fib.py",
    # 🛡 2026-09-11 一劳永逸：scripts/fetch_index_history.py 此前零调度成孤儿
    #   （只写 out/，不写 raw_data/ + 算法链不挂）→ data/INDEX_HISTORY.js 永停 09-07 假新鲜。
    #   现正式挂进 A 批最前（紧跟 fetch_sh_index_fib 之后），cloud-only 护栏由 v8_algo_cloud 双机调度，
    #   输出 raw_data/index_history.json（bridge 已内置）→ update_v8 后续 post_close 重建 INDEX_HISTORY.js。
    "scripts/fetch_index_history.py",
    "fetch_inst_trade.py",
    "fetch_sector_rs.py",
    "fetch_lhb.py",
    # 🛡 2026-09-17 对齐修复：STAGES["A"] 已挂 scripts/fetch_sector_leaders.py（主升板块龙头股，
    #   必须紧跟 fetch_sector_rs.py 依赖其 SECTOR_RS.js 判档）但 ORDER 漏挂 → 入口自校验
    #   assert _STAGE_UNION == set(ORDER) 炸链（09-07 同类问题复发）。此处补挂对齐。
    "scripts/fetch_sector_leaders.py",
    # 🛡 2026-08-20 一劳永逸：5 年长 K 线 fetcher 补入算法链（此前无任何调度方，
    #   且只写 out/ 不 bridge raw_data/ → INDEX_HISTORY 永不更新）。
    # 🛡 2026-08-29 主人令：补跑第二基准（中证1000 / 国证A指），判断 +6% excess 是 alpha 还是风格 beta。
    "calc_crds.py",
    "v8/factor_lab_gen.py",               # → data/FACTOR_LAB.js（B批最前：final_recommend 前必产完，因子融合用当日新鲜因子；2026-09-09 主人令由 E 前置至此）
    "build_candidate_pool.py",         # 读 guanlan/maharo 输入 → gold_pool / candidate_pool
    "generate_top10.py",               # 读 fundamental_quality / gold_pool → raw_data/top10_daily.json + raw_data/history/top10_daily_YYYYMMDD.json
    # 🛡 2026-08-29 主人令：A/B 对照（金股池/候选池/全市场同一信号收益），每日累积信号、T+N 后回填收益。
    "backtest_tdx.py",                 # 读 gold_pool 输入
    "backtest_comprehensive.py",       # 读 raw_data/history/top10_daily_YYYYMMDD.json（必须在 generate_top10 之后）
    "export_optimized_strategy.py",    # → raw_data/optimized_strategy.json（读 backtest_tdx.json 汇总优化策略效果）
    "strategy_four_volume_60m.py",     # → data/FOUR_VOLUME_60M.js（四量终极60min版，baostock独立数据源）
    "strategy_four_volume.py",         # 🛡 2026-08-19 阿狸咪根治孤儿：日线版 FOUR_VOLUME.js 一直在 ORDER 漏挂 → 四星终极卡 4 格 0。render 端已合并读 60m 兜底，这里补齐日线数据链。
    "market_regime.py",                # 🛡 2026-08-19 阿狸咪补对齐：宏观环境卡 → data/MACRO.js + data/MARKET_REGIME.js（国债+LPR+银行间利率+利率上行期板块推荐框架）
    "sector_recommendation.py",        # 🛡 2026-08-19 阿狸咪补对齐：板块推荐卡 → data/SECTOR_RECOMMENDATION.js（13板块按优先级+异动跟随/已涨过标）
    "update_triple_resonance_history.py",  # 累积 triple_resonance_history
    "gen_triple_consensus.py",         # 读 top10 / fundamental / gold_pool
    "gen_triple_track.py",             # 读 triple_history / gold_pool / backtest
    # 🆕 2026-09-15 主人令：四量终极「自己的一整套系统」= 历史追踪 + 跟踪/前向回测。
    #   必须排在 strategy_four_volume.py（L156，产 data/FOUR_VOLUME.js）之后，
    #   且二者内部有序：history 累积账本 → track 消费账本。
    "update_four_volume_history.py",   # → raw_data/four_volume_history.json（逐日账本 + 自建真实收盘价序列）
    "gen_four_volume_track.py",        # → raw_data/four_volume_track.json（持仓跟踪/告警/前向累积/聚类/重叠）
    "calc_volatility_watch.py",         # → raw_data/volatility.json（v8 原生，独立无依赖）
    "gen_stock_stop.py",                # → data/STOCK_STOP_DATA.js（ATR 精确止损止盈，读候选宇宙日K）
    # ── 孤儿模块原生化（2026-08-02）：原靠 v6→v8 sync_legacy 同步，现由 v8 直接产出 ──
    # 这些脚本直接写 raw_data/<name>.json（不经 out/），stage_to_raw 不二次处理，api_push 直接上传。
    "fetch_orphan_suspension.py",       # → raw_data/suspension_alert.json
    "fetch_orphan_market_alerts.py",    # → raw_data/market_alerts.json
    "fetch_orphan_nt_data.py",          # → raw_data/nt_data.json
    "fetch_orphan_sector_fund_flow.py", # → raw_data/sector_fund_flow_trend.json (+ history 累加)
    # ── 最终推荐（final_recommend.py）──
    #   → raw_data/final_recommend.json + data/FINAL_RECOMMEND_DATA.js（Top5 + 全量推荐池）
    # 🛡 2026-08-26 一劳永逸：原排在 ORDER 前部，可能先于部分选股脚本完成就产出推荐。
    #   现整体移至 ORDER 末尾（见下方 track_h_auto_buy.py 之后），确保所有选股策略数据跑完后再汇总。
    "gen_algo_track.py",                # → ALGO_TRACK.js（四量终极/板块龙头/大牛股猎手 独立追踪，2026-08-15 落地）
    # ── 2026-08-17 主人怒令「每个前端的算法都全面审计」补入：之前完全不调度，前端卡永远陈旧 ──
    "calc_sentiment_cycle.py",          # → data/SENTIMENT_CYCLE.js（情绪周期，读 LIMIT_UP_HEATMAP；之前无任何 workflow 调用 = 孤儿）
    "refresh_dividend_cninfo.py",       # → 更新 STOCK_QUOTE 分红字段（读 PORTFOLIO/CANDIDATE/GOLD_POOL；之前无任何 workflow 调用）
    # 🛡 2026-08-18 一劳永逸式修复：以下两脚本原不在 run_algorithms 链中，导致前端卡长期陈旧
    #   - refresh_stock_metadata.py → raw_data/weekend_meta_report.json（周末复盘，月度个股资料）
    #   - fetch_weekend_run.py → raw_data/weekend_run.json（周度运行汇总）
    "refresh_stock_metadata.py",
    "fetch_weekend_run.py",

    # 🛡 2026-08-19 一劳永逸式修复：H 反推算法从PDF OCR 脱离，反推代码 + 每日盘后自跑 + 跟踪回测。
    #   auto_run_dn_algorithm.py 默认 emit-js（写 data/H_AUTO_BUY.js）；
    #   track_h_auto_buy.py 默认 emit-js（写 data/H_AUTO_BUY_TRACK.js，写 raw_data/h_auto_buy_history.json）。
    #   这两个之前一直在算法链外，导致反推算法即使跑出结果也没人调度、没人推送、没人可见。
    "auto_run_dn_algorithm.py",
    # 🗑 2026-09-19 主人令：强势突破（strong_breakout.py）全站删除，不再调度。
    "track_h_auto_buy.py",
    # 🛡 2026-09-11 小九的股票专家（死数据清理·P1）：LHB_7D.js 前端零引用，
    #   停止调度 gen_lhb_7d.py，释放 B 批算力。
    # "gen_lhb_7d.py",                   # → data/LHB_7D.js（龙虎榜 7 日累计，依赖 A 批 fetch_lhb.py）
    # ⚠️ 2026-09-11 A 类修复（假注释纠正）：上句「现正式挂链（B 批）」**与事实不符** ——
    #   本文件的 ORDER 与 STAGES 里都没有 scripts/momentum_common_filter.py
    #   （实测 `grep -n momentum algorithms/run_algorithms.py` = 0 命中），
    #   MOMENTUM_FILTER.js 的真实重算方是 **update_v8.run_experiment_cards()**（盘后构建链，
    #   失败仅告警不阻断），实测其 update_time 随构建链刷新（09-11 23:40:39）。
    #   ⇒ 结论：它仍是「构建链依赖」而非「算法链依赖」，与强势突破（strong_breakout.py 已在
    #   ORDER 内）**并不对称**。此处保留说明以免后人再被这句注释误导；是否真挂进算法链
    #   属调度口径变更，需主人拍板，不在 A 类修复范围。
    #   附：runner 无参调用依赖 SCRIPT_ENV 注入 V8_MOMENTUM_EMIT_JS=1 触发 --emit-js 等价行为。

    #   杜绝「某选股还没跑完，推荐却已生成」的抢跑问题。
    #   🆕 2026-09-04 主人令：因子实验室(FACTOR_LAB.js)此前零调度成孤儿（运维红灯）——
    #      生成器(factor_lab 生成器)挂在 final_recommend 之前（final_recommend 方案B融合读它）。

    "final_recommend.py",              # → FINAL_RECOMMEND_DATA.js（跨策略共振 Top5，管线最终产物，置于末尾）
    #   前端策略回顾卡长期为空/陈旧）。统一挂链尾（依赖各自历史/截面数据已就位）。
    #   三者失败均不影响选股结果，仅自身卡片可能不刷新。

    # 🆕 2026-09-04 主人令「都按你的建议做」：因子实验室独立分层回测（升4⭐证据链）
    # 🛡 2026-09-09 主人令：因子实验室生成器已前置到 B 批最前（ORDER 下方 B 区 calc_crds 之后），此处 E 区仅留分层回测
    "factor_lab_backtest.py",         # → data/FACTOR_LAB_BACKTEST.js（五分位分层·胜率/回撤/OOS）
    "v8/backtest_crds.py",               # → data/CRDS_BACKTEST.js （逆势龙头回测；2026-09-09 挂链补登，此前零调度成孤儿 → 红灯 age 1447min）
    # 🛡 2026-09-07 修复：以下两脚本曾只挂 E 批 STAGES、漏挂 ORDER → 模块级自校验
    #   `_STAGE_UNION == set(ORDER)` 断言崩（仅STAGES有两脚本），盘后链启动即死、0 产出。
    #   此前被 V5 心跳闸门跳过链本体掩盖，2026-09-07 17:40 #1579 首次真跑暴露。
    "backtest_expectancy.py",         # → raw_data/backtest_expectancy.json（期望收益回测，与 E 批同位）
    # 🔴 2026-09-14 主人令更正（作废原 09-13 令）：「金股池和候选股池是算法的上游水源，
    #   不是策略，不需要回测！」候选池 / 金股池(=黄金池) 是 B 批产出的**基础股池**，
    #   供下游策略取用，本身无买卖点 ⇒ 拿 T+1 胜率考核它们必然误导
    #   （实测 金股池 T+1 胜率 32.28% 被误读成「低绩效策略」）。
    #   ⇒ algorithms/backtest_pools.py 及两条产物已删除，**不得再挂回算法链**。

    # 🆕 2026-09-07 主人令「中信 PE 极值温度计 + 历史回测」双卡：fetcher 拉 sh.600030 PE/PB 时序
    # (raw_data/citic_pe_history.json) + 生成器产 data/CITIC_PE_THERMO.js + CITIC_PE_BACKTEST.js。
    # 同类纳入 E 回测批：baostock 数据源 + 夜间跑（不阻塞盘后 20:00 final_recommend）。

    # 🔴 2026-09-11 主人令「一劳永逸」：以下 5 个实验/研究卡脚本此前**从未挂进任何批次**，
    #   唯一载体是 .github/workflows/v8_cn_fetch_experiments.yml（cron 16:30 CST），
    #   而该 workflow 自创建起只触发过 1 次（run#1 2026-09-10T13:01）且失败：
    #   工作区残留未提交改动（raw_data/kline_cache/*.json）→ git push 被拒 →
    #   重试循环里 `git rebase origin/main` 报 "cannot rebase: You have unstaged changes"
    #   → 3 次重试全败 → 永久静默。
    #   后果：5 张卡长期红灯，全部停在 09-10（AI_INSIGHTS_COMPARE【2026-09-15 已全链下线】 / FACTOR_AUDIT /
    #   FACTOR_PROGRESS / VALUATION_PERCENTILE / INDEX_VALUE_FRAMEWORK）。
    #   根治：正式挂进 B 批链尾（与 STAGES["B"] 同位置），不再依赖那个不稳定的独立 workflow。
    #   ⚠️ 必须与 STAGES["B"] 成对修改，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链。
    # 🗑 2026-09-15 主人令：scripts/fetch_ai_insights_compare.py 全链下线（AI 洞察卡改读
    #   window.MAHORO_INSIGHTS 直供「实情解析」，「统计」口径已删）⇒ 不再列入 ORDER。
    "scripts/gen_factor_audit.py",            # → raw_data/factor_audit.json（多因子 vs v8 审计）
    "scripts/gen_factor_progress.py",         # → raw_data/factor_progress.json（读 factor_audit，须在其后）
    "scripts/fetch_valuation_percentile.py",  # → raw_data/valuation_percentile.json（A股指数 PE 分位）
    "scripts/fetch_index_value_framework.py", # → raw_data/index_value_framework.json（指数中枢+趋势门控）

    # 🆕 2026-09-11 主人令「在每日最终推荐出来后，开始回测所有算法，按前端卡名都写出来」：
    #   全算法回测汇总聚合器。放 ORDER **最末**⇒ 在 E 批内最后执行（同 stage 沿用 ORDER
    #   相对次序）：它要读 E 批其他脚本本轮刚产出的 CRDS_BACKTEST / BACKTEST_TDX /
    #   FOUR_VOLUME_BACKTEST / FACTOR_LAB_BACKTEST，先跑就会读到上一轮旧数。
    # 🗑 2026-09-20 摘链（阿狸咪的工程师 · 主人令 + 真浏览器实测实证）：
    #   原 2026-09-13 在此挂入 scripts/algo_backtest_compare.py（当时为「强势突破」补回测源），
    #   现**正式摘除**，理由三条（逐条均已实证，非推断）：
    #     ① 其产物的**唯一消费卡**「两套算法回测对比」属主人 **2026-09-02 明令删除**的模块
    #        （见 index.html renderUnlisted 内注：「强势突破 pane、模块去向索引、两套算法回测对比 全部删除」）；
    #     ② 该卡所在 pane（ulPaneStrong）**已不在 renderUnlisted 的生成列表**内 ——
    #        CDP 真浏览器实测（2026-09-20 06:5x）：切到「暂未上架」后 panel.len=262174、
    #        ulPaneObserve=true 但 **ul-pane 数 = 0、ulPaneStrong 非元素** ⇒ 全站零生效路径；
    #     ③ 聚合器 gen_backtest_all_algos.py 对其**零硬依赖**（去注释后 scan/parse_algo_compare
    #        调用点 0 处，仅 105-113 墓碑注释）⇒ 摘链无下游副作用。
    #   ⚠️ STAGES["E"] 同步摘除（两处成对，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链）。
    #   ⚠️ 不得再挂回；如日后要恢复该对比能力，须**先恢复前端卡**（主人令），再重写生成器与解析器。
    # 🆕 2026-09-17 小九的股票专家（主人令「星级基准超额数据缺失→从回测产物侧补」）：
    #   全市场等权基准生成器（2026-09-17 阿狸咪的工程师新增）。交接单声称已挂 E 批
    #   （ORDER[47]）但远端实测缺失（疑被裸 rebase 洗掉）——此处补挂对齐。
    #   ⚠️ 必须在聚合器 gen_backtest_all_algos.py 之前（聚合器按各卡信号区间读基准求平均）。
    #   ⚠️ 与 STAGES["E"] 成对修改，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链。
    "gen_market_bench.py",   # → raw_data/market_bench.json（与策略同口径的全市场等权基准）
    "gen_backtest_all_algos.py",   # → raw_data/backtest_all_algos.json + data/BACKTEST_ALL_ALGOS.js

    # 🆕 2026-09-13 主人令「PE/PB 方案 A 落地」：中信证券(sh.600030)历史估值双卡。
    #   脚本 09-07 就写好却**从未挂进任何批次**（只靠手动跑）⇒ CITIC_PE_THERMO 长期 stale。
    #   方案比对定论 = **方案 A（挂 E 批最末）**；**否决方案 B（另建独立 workflow/定时）**——
    #   那是本仓已定罪的错误（见上方 2026-09-11 实验卡判决书：独立 workflow 自创建只触发
    #   1 次且失败 → 5 张卡永久静默）。挂进批次才有闸门监视 / freshness / 失败上报。
    #   ⚠️ 位置必须在**最末**（gen_backtest_all_algos 之后）：CITIC 属实验区卡，不参与
    #      D 批最终推荐 ⇒ baostock 抖动只影响整链结束时刻，不碰关键路径。
    #   ⚠️ 与 STAGES["E"] 成对修改，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链。
    "v8/fetch_citic_pe.py",       # → raw_data/citic_pe_history.json（baostock 增量，断点续跑）
    "v8/gen_citic_pe.py",         # → data/CITIC_PE_THERMO.js + data/CITIC_PE_BACKTEST.js（须在 fetcher 之后）
    # 🆕 2026-09-17 主人令·全站口径统一（⑭）：factor_walkforward 引擎补挂主链 E 批最末。
    #   前端「待回测候选台账」A 组 6 因子长期 pending 根因=发动机从未点火（仅 09-16 手动跑过 1 次）。
    #   产出 raw_data/factor_walkforward.json → scripts/gen_factor_progress.py 判 done/删除 + generate_top10.py 仅 PASS 启用。
    #   ⚠️ 与 STAGES["E"] 成对修改，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链。
    "factor_walkforward.py",   # → raw_data/factor_walkforward.json（walk-forward 回测，全市场 K 线）
    ]



# 🔴 2026-09-02 主人令「分批跑」：把单轮串行 ORDER 拆成 4 个按时触发的 stage，
#   每 stage 独立触发、独立 timeout，final_recommend 独占 D 批（不再被单窗口掐断）。
#   跨 stage 产物经 main 分支传递：每 stage 跑完即 stage(out→raw_data)+push，
#   下游 stage 的云端 run checkout main 即含上游当日产物。
STAGES = {
    "A": [  # 数据采集批（~18:00 CST 后，受闸门 START_TRADING 约束；龙虎榜16:30后）：纯 fetch + 上游自产前置
        "fetch_fundamental_quality.py", "fetch_stock_names.py", "gen_stock_profile.py",
        "fetch_stock_quote_v8.py", "fetch_sh_index_fib.py",
        "scripts/fetch_index_history.py",   # → raw_data/index_history.json（INDEX_HISTORY.js 上游；cloud-only 护栏，09-11 正式挂 A 批）
        "fetch_inst_trade.py",
        "fetch_sector_rs.py", "fetch_lhb.py",
        # 🚀 2026-09-17 主人令：「主升有没有龙头股或者推荐股，要不不知道买什么」
        #   「暂未上架 > 概念/行业 → ETF·龙头 参考」卡下方「主升板块 · 龙头股」块的数据上游。
        #   ⚠️ 必须紧跟 fetch_sector_rs.py —— 它读 data/SECTOR_RS.js 判定「主升」档板块，
        #      再调东财 push2delay 拉板块成分股取涨幅前 5。前置依赖，顺序不可调换。
        #   产出：raw_data/sector_leaders.json + data/SECTOR_LEADERS.js（window.SECTOR_LEADERS）
        #   独立链路：本脚本失败不影响 SECTOR_RS 及任何现有卡片。
        "scripts/fetch_sector_leaders.py",
        "fetch_orphan_suspension.py", "fetch_orphan_market_alerts.py",
        "fetch_orphan_nt_data.py", "fetch_orphan_sector_fund_flow.py"],
    "B": [  # 选股批（~18:10 CST，盘后数据齐）：核心选股策略
        # 🛡 2026-09-09 主人令：因子实验室生成器前置到 B 批最前——必须在 final_recommend(D批20:00) 之前产完，
        #   否则「为更好选股」的因子融合只能吃昨日陈旧数据。生成器 50-90min baostock 冷启动，18:10 起跑→19:40 前产完，D 批必吃到当日新鲜因子。
        "v8/factor_lab_gen.py",   # → data/FACTOR_LAB.js + raw_data/factor_lab.json（baostock，冷启动长）
        "calc_crds.py", "build_candidate_pool.py", "generate_top10.py",
        "strategy_four_volume_60m.py", "strategy_four_volume.py",
        "market_regime.py", "sector_recommendation.py",
        "update_triple_resonance_history.py",   # 累积 triple_resonance_history（在 gen_triple_consensus 之前）
        # 🆕 2026-09-15 主人令：四量终极历史追踪 + 跟踪/前向回测（与三重同批、同序）。
        #   插在 strategy_four_volume.py 之后 → 读到当日新鲜 data/FOUR_VOLUME.js；
        #   ⚠️ 必须在 gen_triple_consensus 之前（本行位置天然满足）。
        "update_four_volume_history.py", "gen_four_volume_track.py",
        "gen_triple_consensus.py", "gen_triple_track.py", "calc_volatility_watch.py",
        "gen_stock_stop.py", "gen_algo_track.py", "calc_sentiment_cycle.py",
        "refresh_dividend_cninfo.py",
        "refresh_stock_metadata.py", "fetch_weekend_run.py",   # 周末复盘/周度汇总（原 ORDER 漏挂 STAGE）

        "auto_run_dn_algorithm.py", "track_h_auto_buy.py",
        # 🛡 2026-09-11 小九的股票专家（死数据清理·P1）：LHB_7D.js 前端零引用，停止调度 gen_lhb_7d.py。
        # "gen_lhb_7d.py",

        # 🛡 2026-09-11 主人令「一劳永逸」：以下 5 个实验/研究卡脚本**从未挂进任何批次**，
        #   只在 v8_cn_fetch_experiments.yml 里跑，而该 workflow 的 cron 只触发过 1 次且
        #   因「工作区有未提交改动 → push 被拒 → rebase 失败」3 次重试全败后永久静默
        #   → 5 张卡长期红灯（AI_INSIGHTS_COMPARE / FACTOR_AUDIT / FACTOR_PROGRESS /
        #   VALUATION_PERCENTILE / INDEX_VALUE_FRAMEWORK 全部停在 09-10）。
        #   ⚠️ 这 5 个脚本在仓库根 scripts/ 而非 algorithms/，必须带 "scripts/" 前缀
        #   （run_algorithms.py:946 的双层路径解析认该前缀），否则报「缺失脚本」。
        #   根治：直接挂进 B 批链尾（它们的输入——maharo_macro / 候选池 / 指数历史 /
        #   FACTOR_AUDIT——在 B 批时均已就绪），不再依赖那个不稳定的独立 workflow。
        # 🗑 2026-09-15 主人令：scripts/fetch_ai_insights_compare.py 全链下线（见 ORDER 同位说明）
        "scripts/gen_factor_audit.py",              # → raw_data/factor_audit.json（多因子 vs v8 审计）
        "scripts/gen_factor_progress.py",           # → raw_data/factor_progress.json（读 factor_audit）
        "scripts/fetch_valuation_percentile.py",    # → raw_data/valuation_percentile.json（A股指数 PE 分位）
        "scripts/fetch_index_value_framework.py",   # → raw_data/index_value_framework.json（指数中枢+趋势门控）
    ],
    # 🛡 2026-09-04 主人令「策略全部数据出来→最终数据上线→然后才是回测」时序重排：
    #   原 C(回测 19:15) 在 D(final_recommend 20:00) 之前 → 回测汇总胶囊早于最终推荐，时序倒挂。
    #   现改为 A(16:40 采集) → B(18:10 选股) → D(20:00 汇总·最终推荐上线) → E(21:00 回测)。
    #   键名 C 退役；回测批内容原样迁入 E，另收编 strategy_four_volume.py（回测模式，SCRIPT_ENV 注入）。
    "E": [  # 回测批（~21:00 CST，最终推荐上线后）：backtest 全家 + 因子实验室分层回测（生成器已前置到 B 批）
        "backtest_tdx.py", "backtest_comprehensive.py",
        "backtest_expectancy.py",          # 🆕 期望收益回测：walk-forward 产出 raw_data/backtest_expectancy.json
        "export_optimized_strategy.py",   # 读 backtest_tdx.json 汇总优化策略（在 backtest_tdx 之后）

        # 🛡 2026-09-09 主人令：因子实验室「生成器」已前置到 B 批最前（必须在 final_recommend 前产完），
        #   此处 E 批仅保留其「分层回测」——读 FACTOR_LAB 做五分位分层验证（研究性质，不进选股打分），置于最终推荐之后无害。
        #   链内由 run_algorithms.py 统一注入 V8_IN_CHAIN=1 → 本脚本自带 git push 自动跳过。
        "factor_lab_backtest.py",   # 🆕 因子实验室分层回测
        "v8/backtest_crds.py",   # → data/CRDS_BACKTEST.js （逆势龙头回测；2026-09-09 挂链补登，此前仅存在于 v8/ 目录、STAGES/ORDER 均未挂 → 永远跑不到）
        # 2026-09-06 主人令：AI预测卡回测 INVALID → 下架，停跑 path_probability_backtest.py
        "strategy_four_volume.py",  # 四量终极回测模式（SCRIPT_ENV 注入 V8_BACKTEST_YEARS=5 → 补写 FOUR_VOLUME_BACKTEST.js，根治孤儿）
        # 🔴 2026-09-14 主人令更正：候选池 / 金股池是**上游水源**（基础股池），不是选股策略
        #   ⇒ 不做回测（原 backtest_pools.py 已删除，见 ORDER 同处说明）。
        # 🆕 2026-09-11 主人令：全算法回测汇总（按前端卡名、胜率/收益降序、低绩效提请下架）。
        #   ⚠️ 必须在 E 批**最后**——读同批其他脚本刚产出的回测产物 + D 批最终推荐。
        # 🗑 2026-09-20 摘链（与上方 ORDER 同处 · 成对修改）：scripts/algo_backtest_compare.py 已摘除，
        #   详见 ORDER 内三条实证理由（消费卡属主人 09-02 明令删除 / pane 已不生成 / 聚合器零硬依赖）。
        "gen_market_bench.py",   # → raw_data/market_bench.json（全市场等权基准，与策略同口径）
        "gen_backtest_all_algos.py",   # → data/BACKTEST_ALL_ALGOS.js（策略回测页总览）
        # 🛡 2026-09-07 主人令「互踢/暴风/覆盖不想再看到·方案 B 一劳永逸根治」：
        #   原 D 批首脚本(factor_lab 生成器)冷启动 50-90min（注释自述），串行堵在
        #   final_recommend 前 → 整批从理论 8min 拖到实测 35-90min。
        #   实测 final_recommend.py:559 对 FACTOR_LAB 缺失只 print warn 跳过（今晚
        #   FACTOR_LAB 停在 09-05 仍出 5 只），生成器根本不该绑在 final_recommend 关键路径上。
        #   现把生成器从 D 摘到 E 批（21:00 夜间跑，不阻塞盘后 20:00 出最终推荐），
        #   D 批瘦身至 final_recommend 单脚本 → 选股策略全部数据出来 30-40min 内出最终推荐。

        # 🆕 2026-09-13 主人令「PE/PB 方案 A 落地」：中信证券(sh.600030)历史估值双卡。
        #   与上方 ORDER 同位置（E 批最末）。两脚本 09-07 写好却从未挂链 ⇒ 长期 stale。
        #   超时预算：fetch 600s（增量拉取；首跑全量约 4000 行需余量）/ gen 300s（纯本地计算）。
        #   ⚠️ 与上方 ORDER 成对修改，否则模块级 assert(_STAGE_UNION == set(ORDER)) 崩链。
        "v8/fetch_citic_pe.py",   # → raw_data/citic_pe_history.json
        "v8/gen_citic_pe.py",     # → data/CITIC_PE_THERMO.js + CITIC_PE_BACKTEST.js
        # 🆕 2026-09-17 主人令·全站口径统一（⑭）：factor_walkforward 引擎补挂主链 E 批最末（与 ORDER 同位置，成对修改）
        "factor_walkforward.py",   # → raw_data/factor_walkforward.json（walk-forward 回测，全市场 K 线）
    ],
    "D": [  # 汇总批（~20:00 CST，依赖全部）：仅 final_recommend（LHB历史/7d/生命周期/factor_lab_gen 前置到 B 批·互踢暴风根治）
        "final_recommend.py",   # 必需上游 = B 批产物（CRDS/TOP10/三重共识/crisis/sector_rs/stock_profile/triple_track）
    ]}

# 🛡 2026-09-04 主人令：回测批需要「选股脚本以回测模式运行」——runner 对所有脚本无参调用，
#   故按脚本注入环境变量（strategy_four_volume.py 读 V8_BACKTEST_YEARS>0 时同时跑近 N 年回测
#   并补写 data/FOUR_VOLUME_BACKTEST.js）。仅影响 E 回测批；B 选股批无注入、保持轻快。
# 🔴 2026-09-17 主人令·全站口径统一（作用域根治）：
#   原键 = **脚本名**（"strategy_four_volume.py"），但该脚本同时在 B（选股）与 E（回测）两批出现
#   ⇒ 键无法区分批次，B 批也被注入 V8_BACKTEST_YEARS=5；且注入写的是**进程级** os.environ
#   且从不还原 ⇒ B 批注入后残留，D 批 _gate_hardwait_four_volume 重跑 strategy_four_volume.py
#   的子进程继承 =5 ⇒ 症状「D 批跑 5 年回测」。
#   现键改为 (stage, script) 二元组，精确到批次；注入侧配套「跑完即还原」（见 step_run）。
SCRIPT_ENV = {
    # 🔴 2026-09-13 主人令（档位扩至 250 交易日）：3 → 5 年。
    #   根因：years=3 时 bars≈810 根，扣掉信号检测窗口后 T+180/T+250 落在区间外
    #   ⇒ 两档恒零样本（前端只能显示「累积中」），并非策略失效而是**回看区间不够**。
    #   years=5 → bars = max(DAILY_BARS, 5*250+250=1500) 足以覆盖 250 交易日最长持有。
    ("E", "strategy_four_volume.py"): {"V8_BACKTEST_YEARS": "5"},
    ("E", "backtest_expectancy.py"): {"V8_USE_BAOSTOCK": "1"},   # 🆕 runner 用 baostock 拉全量K线，产出新鲜回测
}
# 自校验：STAGES 并集必须精确覆盖 ORDER（无遗漏/多余，保证分批模式不丢脚本）
_STAGE_UNION = set()
for _s in STAGES.values():
    _STAGE_UNION.update(_s)
assert _STAGE_UNION == set(ORDER), (
    "STAGES 与 ORDER 不一致: 仅ORDER有=%s, 仅STAGES有=%s"
    % (set(ORDER) - _STAGE_UNION, _STAGE_UNION - set(ORDER))
)

def step_v8_self_sufficiency():
    """2026-08-02 原生化：v8 自产 3 类上游输入（gold_pool / scan_result / watch_result /
    guanlan_*），替代 v6 供给。通过 V8_OUT_DIR 环境变量让被迁移脚本把数据写到仓库根
    out/（而非 algorithms/data）。

    2026-08-28 主人令：mahoro 数据源不再跟踪，已从 jobs 中移除。
    """
    print(f"\n[0-pre] v8 原生化自产上游输入 → out/  (V8_OUT_DIR={OUT})")
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ)
    env["V8_OUT_DIR"] = OUT
    jobs = [
        ("scanner.py", 3600),             # 产出 gold_pool / scan_result / watch_result
        ("guanlan_extractor.py", 600),    # 产出 guanlan_reports / guanlan_watchlist
    ]
    for script, timeout in jobs:
        path = os.path.join(ALGO, script)
        if not os.path.exists(path):
            print(f"  ❌ 缺失脚本: {script}")
            continue
        print(f"  ▶ {script}  ({datetime.now():%H:%M:%S})")
        try:
            #   其他上游脚本不要带 full，避免 argparse 报错。
            args = [PY, path, "full"] if script == "scanner.py" else [PY, path]
            r = subprocess.run(args, cwd=ALGO, env=env,
                                capture_output=True, text=True, timeout=timeout)
            # 2026-08-04 修复2：runner 宿主 sitecustomize.py 会在进程退出时因批量临时文件
            # 清理强制 SystemExit(1)。若 scanner.py 已输出"金股池已更新"，则视为成功。
            stdout_all = r.stdout or ""
            stderr_all = r.stderr or ""
            looks_ok = (r.returncode == 0 or
                        (script == "scanner.py" and "金股池已更新" in stdout_all))
            if looks_ok:
                last = [l for l in stdout_all.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"     ✅ ok | {last[0][:80]}")
            else:
                print(f"     ⚠️ 退出码 {r.returncode}")
                tail = "\n".join(stdout_all.strip().splitlines()[-3:] + stderr_all.strip().splitlines()[-3:])
                print("     " + tail.replace("\n", "\n     ")[:400])
        except subprocess.TimeoutExpired:
            print(f"     ⏱️ 超时(>{timeout}s)，跳过")
        except Exception as e:
            print(f"     ❌ 异常: {e}")


def step_seed_inputs():
    # 2026-08-02 原生化后，默认 no-op；仅 V6_SEED=1 才回退重灌 v6 输入。
    if os.environ.get("V6_SEED", "0") != "1":
        print(f"\n[0] 跳过 v6 重灌（已原生化，设 V6_SEED=1 可强制回退）")
        os.makedirs(OUT, exist_ok=True)
        return
    print(f"\n[0] 重灌 v6 上游输入 → out/  (V6={V6_DATA_DIR})")
    os.makedirs(OUT, exist_ok=True)   # 确保仓库根/out 存在（脚本 open(...,'w') 依赖它）
    for f in INPUTS_FROM_V6:
        src = os.path.join(V6_DATA_DIR, f)
        if os.path.exists(src):
            dst = os.path.join(OUT, f)
            with open(src, "rb") as a:
                data = a.read()
            with open(dst, "wb") as b:
                b.write(data)
            print(f"  ✅ {f}")
        else:
            print(f"  ⚠️ v6 缺失输入: {f}（本轮将跳过依赖它的脚本）")

    # 保存金股池快照，供 backtest_tdx 消除幸存者偏差（用历史池的并集作为回测宇宙）
    try:
        gp_src = os.path.join(OUT, "gold_pool.json")
        if os.path.exists(gp_src):
            hist_dir = HIST_OUT
            os.makedirs(hist_dir, exist_ok=True)
            today_str = datetime.now().strftime("%Y%m%d")
            gp_snap = os.path.join(hist_dir, f"gold_pool_{today_str}.json")
            with open(gp_src, "rb") as a:
                data = a.read()
            with open(gp_snap, "wb") as b:
                b.write(data)
    except Exception as e:
        print(f"  ⚠️ 保存金股池快照失败: {e}")


# 🔴 2026-08-20 主人令·一劳永逸修复：所有选股策略必须在 18:00 盘后数据全就绪后才跑。
#   症状1：16:10 就出最终推荐，但龙虎榜 16:30 才发布 → final_recommend 用不完整/旧 LHB 数据。
#   症状2：CRDS 17:13 就跑出结果（前端显示"更新于今日 17:13"），但大量盘后数据 17:30-18:00 才齐。
#   根因：run_algorithms.py 只有 16:30 龙虎榜门控，且未覆盖 calc_crds / generate_top10 / 四量等选股脚本。
#   修复：统一设"盘后选股策略门控" ≥ 18:00 (CST)。以下脚本在 18:00 前一律跳过；
#         上游纯数据采集（fetch_*）不受影响，仍可提前跑。
STOCK_PICKING_SCRIPTS = {
    # 核心选股策略
    "calc_crds.py",                  # CRDS 逆势龙头（前端 17:13 更新元凶）
    "build_candidate_pool.py",       # 候选池/金股池聚合
    "generate_top10.py",             # 多维共振 TOP10 精选
    "strategy_four_volume.py",       # 四量终极 日线选股
    "strategy_four_volume_60m.py",   # 四量终极 60min 选股
    "update_triple_resonance_history.py",  # 三重历史累积
    "gen_triple_consensus.py",       # 三重共识选股
    "gen_triple_track.py",           # 三重跟踪
    # 🆕 2026-09-15 主人令：四量历史追踪 + 跟踪（读当日 FOUR_VOLUME.js，属盘后选股产物）。
    #   与三重同族一致纳入 18:00 门控 —— 盘中 force 跑链也不得重算（免半日数据假产物）。
    "update_four_volume_history.py",  # 四量历史累积
    "gen_four_volume_track.py",       # 四量跟踪/前向回测
    "final_recommend.py",            # 跨策略共振 Top5（管线最终产物）
    "gen_algo_track.py",             # 算法追踪
    "calc_sentiment_cycle.py",       # 情绪周期（读 LIMIT_UP_HEATMAP）
    "auto_run_dn_algorithm.py",      # H 反推算法
    "track_h_auto_buy.py",           # H 反推跟踪
    "calc_volatility_watch.py",      # 波动率观察选股
    "gen_stock_stop.py",             # ATR 止损止盈（读候选宇宙日K）
    # LHB_7D 已停跑（2026-09-13）：gen_lhb_7d.py 从选股门控名单移除（前端零引用 + raw 无消费方）
}
# 🔴 2026-09-03 主人令「回测页跟着最终推荐的算法时间走，太早算就无效、浪费」：
#   回测批与选股批同一盘后门控 —— 交易日盘中/盘前（06:00-17:59）即使 force 跑链，
#   也禁止重算回测，防止用半日数据重算出「看起来新鲜」的假回测（今日 13:14 事故根因：
#   STOCK_PICKING_SCRIPTS 门控漏掉回测批，盘中 force 链跳过选股但照跑回测并重刷 update_time）。
BACKTEST_SCRIPTS = {
    "backtest_tdx.py",
    "backtest_comprehensive.py",
    "backtest_expectancy.py",
    "export_optimized_strategy.py"}
# 18:00 = 所有盘后数据（龙虎榜/北向/板块资金/个股行情/机构调研等）稳定就绪时间
_STOCK_PICKING_READY_HOUR, _STOCK_PICKING_READY_MIN = 18, 0
# 次日凌晨补跑的截止时刻（CST）：过了这个点就属于新交易日的盘前，不再放行
# 🛡 2026-09-11 一劳永逸：窗口上界 6 → 9，与 v8_stage_gate.py::_NIGHT_CUT 同源。
#   原值 6 的实测缺陷：链 05:16 起跑 → 06:36 才轮到选股脚本 → picking_ready 早在上游
#   判定为 True，但脚本级 time_gate 按「现在 06:36」二次否决 → generate_top10 /
#   strategy_four_volume(_60m) / gen_triple_consensus / calc_crds 全 exit 1（run#1692 实锤）。
_NEXT_DAY_CUTOFF_HOUR = 9


def _is_post_close_picking_ready():
    """判断当前可否跑盘后选股策略（CST）。

    🛡 2026-08-29 一劳永逸根因修复（候选池停更 3 天的真凶）：
    原写法只判断「hour > 18」，把**次日凌晨补跑**（00:00~08:59）也误判成
    「未到 18:00」→ 实测 run #1204 在北京时间 08-29 00:43 跑算法链，
    20 个选股脚本（calc_crds / build_candidate_pool /
    generate_top10 / strategy_four_volume* ...）被整批跳过 → 候选池不产出 →
    CRDS / 最终推荐整条选股链停更，链尾闸门随之 failure。

    本门控真正要挡的是「盘中/盘前数据不全时抢跑选股」，不是挡凌晨补跑 ——
    凌晨时上一交易日的盘后数据早已齐全。

      放行 18:00~23:59  当日盘后，数据已齐
      放行 00:00~08:59  次日凌晨补跑，上一交易日盘后数据已齐
      拦截 06:00~17:59  盘前/盘中，当日尚未收盘，禁止生成选股结果
    """
    # 2026-08-29 主人周末审计：V8_FORCE_RUN=1 时直接放行（周末/假期审计验证用，
    # 此时市场已收盘、无盘中抢跑风险；等价于「手动强制跑一轮」）。仅手动 dispatch 带 force_run 时生效。
    if os.environ.get("V8_FORCE_RUN") == "1":
        return True
    # 🛡 2026-09-11 一劳永逸（两套口径打架根治）：批次闸门（v8_stage_gate.py）是**唯一决策点**，
    #   它一旦放行本链，就说明该数据日的上游产物确已就绪 —— 链内不得再用「现在几点」二次否决。
    #   实测 run#1692：链 05:16 起跑（夜窗内、闸门放行），06:36 轮到选股脚本时被本函数
    #   按「现在 06:36 属盘前」重新否决 → generate_top10 / strategy_four_volume(_60m) /
    #   gen_triple_consensus / calc_crds 全部 exit 1 → B 批残缺 → D/E 永不执行。
    if os.environ.get("V8_GATE_AUTHORIZED") == "1":
        print('[run_algorithms] 批次闸门已授权本链 → 放行选股脚本（不再按钟点二次否决）')
        return True
    # 2026-08-20 根因修复：统一使用 time_gate 的 UTC+8 计算，避免 runner 时区漂移。
    sys.path.insert(0, ALGO)
    try:
        from utils.time_gate import _now_cst
    finally:
        sys.path.pop(0)
    now = _now_cst()
    h, m = now.hour, now.minute
    if h > _STOCK_PICKING_READY_HOUR:              # 19:00 ~ 23:59
        return True
    if h == _STOCK_PICKING_READY_HOUR:             # 18:00 ~ 18:59
        return m >= _STOCK_PICKING_READY_MIN
    if h < _NEXT_DAY_CUTOFF_HOUR:                  # 00:00 ~ 08:59 凌晨补跑
        return True
    return False                                   # 09:00 ~ 17:59 盘前/盘中


# 2026-08-29 科学运行模式（主人：周末/假期放开跑，不要限死；长假仅首日有 T+1）
def _is_trading_day_now():
    """调用 v8_date 判定今日是否 A 股交易日（含调休上班日），全链路统一口径。"""
    try:
        return v8_date.is_trading_day()
    except Exception:
        return True  # 兜底：无法判定时按交易日处理，不阻断


def _last_trading_day():
    """返回最近一个 A 股交易日（含今天；若今天非交易日则往前找）。回填模式用其作为数据日期，
    避免周末/假期跑批把日期错标成今天（周六无交易，数据实为上周五收盘）。
    统一走 v8_date 中枢，确保全链路日期口径一致。"""
    return v8_date.last_trading_day(max_lookback=15)


def _is_t1_data_day():
    """🛡 2026-09-07 主人令铁律落地（根治 09-05 周六全链空转）：
    判定「今天是否持有上一交易日的 T+1 数据」——即今天 == 上一交易日的次日。

    背景（主人原话：「周六和假期第一天都有 T+1 数据，怎么可能不跑，这逻辑就是错的」）：
      龙虎榜 / 机构调研 / 大宗交易 / 融资融券 / 股东增减 等 T+1 类数据，
      在交易日收盘后由交易所陆续发布，**到次日（周六 / 假期首日）才完整**。
      因此周六与假期第一天**必须照常采集**，绝不是「非交易日无新数据」。

    原实现缺陷：backfill 模式一刀切 `skip_fetch=True` 跳过全部 fetch_* 采集，
      使周六全链拿不到任何 T+1 新源 → generate_top10 等生成器检测到输入陈旧
      → 按「不得造假」原则保留上一版本 → D 批 final_recommend 就绪门控拒绝产出
      → **整链 11 个 run 全 success 却零产出**，前端卡片显示「已停更 N 个交易日」。
      实测 2026-09-05（周六）：16:40 A 批 / 18:10 B 批无新源空转，
      top10_daily.json 与 v8_pool_tracker.json 停在 09-04 22:36/22:05。

    修复口径（与「算法链工作日历规则」一致）：
      周六 / 假期第一天 → T+1 窗口，照常采集（skip_fetch=False）
      假期中段 / 最后一天 → 无 T+1，跳过采集（skip_fetch=True，省 API）
      交易日 → official 模式，本就全量采集（不受本函数影响）
    """
    try:
        ltd = v8_date.last_trading_day(max_lookback=15)  # 上一交易日 YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        delta = (datetime.strptime(today, "%Y-%m-%d")
                 - datetime.strptime(ltd, "%Y-%m-%d")).days
        return delta == 1  # 恰好是上一交易日的次日 = 持有 T+1
    except Exception:
        return False  # 判定时失败：保守按「无 T+1」处理（不改变原有行为）


def _run_mode():
    """返回本轮运行模式：
    official   交易日 + 盘后窗口(18:00-23:59 / 00:00-08:59) → 全量采集+计算+推送（官方刷新，日期=今天）
    backfill   非交易日(周末/假期) + force_run → 跳过实时采集(无新数据)，用缓存重算+推送，
               日期统一改写上一交易日（数据实为上周五收盘，不冒充今日）；满足主人「周末放开跑数据」
    blocked    交易日盘中(06:00-17:59) 且无 force → 禁止生成选股结果(等收盘)
    """
    if os.environ.get("V8_FORCE_RUN") == "1":
        return "backfill" if not _is_trading_day_now() else "official"
    sys.path.insert(0, ALGO)
    try:
        from utils.time_gate import _now_cst
    finally:
        sys.path.pop(0)
    now = _now_cst()
    h = now.hour
    post_close = (h > 18) or (h == 18) or (h < 6)
    if _is_trading_day_now() and post_close:
        return "official"
    if not _is_trading_day_now():
        return "backfill"
    return "blocked"


#   step_stage 原在整链跑完后才搬运 → final_recommend 一直读到上一轮的陈旧版本。
#   本门控在 final_recommend 之前：(1) 先做一轮 stage(out→raw_data)；(2) 校验全部选股
#   输入是否本轮回合新鲜产出（mtime≥本轮启动时间）；(3) 任一缺失/陈旧则重跑其生成器并
#   再次 stage；仍失败则拒绝产出最终推荐（绝不拿陈旧数据冒充今日推荐，遵守铁律「不得造假」）。
#   映射： 输入文件 → (生成器脚本, 是否写 out/ 需二次 stage)
_FINAL_RECOMMEND_INPUTS = {
    "triple_consensus.json":       ("gen_triple_consensus.py", False),
    "top10_daily.json":            ("generate_top10.py", False),
    "crds_card_data.json":         ("calc_crds.py", True),
    "lhb_data.json":               ("fetch_lhb.py", True),
    "sector_rs.json":              ("fetch_sector_rs.py", True),
    "stock_profile.json":          ("gen_stock_profile.py", False),
    "triple_track.json":           ("gen_triple_track.py", False),
    # crisis_data.json 由云端 cloud_fetch_v8.py 产出，本地链不重跑；仅做新鲜度告警（见 final_recommend 内部兜底）
}

# 🛡 2026-08-26 补全（昨天门控漏挂四量）：final_recommend 实际读 data/FOUR_VOLUME_60M.js
#   （60min 四量终极共振），四量终极卡还读 data/FOUR_VOLUME.js；二者必须本轮回合新鲜产出，
#   否则最终推荐用陈旧四量汇总（"逻辑不对"根因）。这两脚本直接写 data/*.js（不经 out/，无需 stage）。
# 🛡 2026-09-10 主人令（一劳永逸·硬等待）：final_recommend 实际读 data/FOUR_VOLUME_60M.js（60min），
#   四量终极卡读 data/FOUR_VOLUME.js（日线）。二者必须本轮回合新鲜产出，否则最终推荐用陈旧四量汇总（"逻辑不对"根因）。
#   - FOUR_VOLUME_60M.js：🔴 2026-09-11 起 = 【硬告警·计败不阻断】——陈旧时计入失败账本
#     （algo_run_report.json），但不阻断 final_recommend（final_recommend.py 已做
#      「60m 非今日 → 回退日线版」降级）。
#   - FOUR_VOLUME.js（日线版，主信号源）：升级为【硬等待】——见 _final_recommend_gate，非今日则重跑生成器并等待，
#     超时才拒绝产出（绝不用陈日落盘汇总）。主人 19:52 拍板："盘后算的才有效，算法链停下等重算出来再继续"。
_FINAL_RECOMMEND_DATA_INPUTS = {
    "FOUR_VOLUME_60M.js": ("strategy_four_volume_60m.py", False),  # 硬告警·计败不阻断
}


def _stage_out_to_raw(quiet=False):
    """把 algorithms/out/ 下的产物按 V6_TO_V8 搬运到 raw_data/（幂等，可重复调用）。"""
    try:
        sys.path.insert(0, ALGO)
        import stage_to_raw as _str
        n = _str.main()
        if not quiet:
            print(f"  🔄 stage(out→raw_data)：提升 {n} 个产物")
        return n
    except Exception as e:
        print(f"  ⚠️ stage 异常: {e}")
        return 0


def _gate_ensure_inputs(inputs_map, base_dir, run_start, soft=False):
    """检查一组输入是否本轮回合新鲜产出（mtime ≥ run_start）。缺失/陈旧则重跑生成器并复检。
    返回 (ok, bad_list)。
      ok=False(硬模式)=有输入重跑后仍缺失/陈旧，应拒绝产出最终推荐；
      soft=True=仅尝试重跑刷新，但无论如何返回 ok=True（bad 仅作告警记录，不阻断下游）。"""
    missing, stale = [], []
    for fname, (prod, is_out) in inputs_map.items():
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            missing.append(fname); continue
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < run_start:
            stale.append(fname)
    if not missing and not stale:
        return (True, [])
    print(f"  ⚠️ 输入 缺失={missing} 陈旧={stale} → 重跑生成器" + ("（软模式：仅告警不阻断）" if soft else ""))
    for fname in list(missing) + list(stale):
        prod, is_out = inputs_map[fname]
        p = os.path.join(ALGO, prod)
        if not os.path.exists(p):
            print(f"     ❌ 生成器缺失: {prod}"); continue
        try:
            # 2026-08-31：同主循环，按脚本取超时（重跑重活时不再卡在 1800s 硬编码）
            _gto = _script_timeout(prod)
            r = subprocess.run([PY, p], cwd=ALGO, capture_output=True, text=True, timeout=_gto)
            print(f"     {'✅' if r.returncode == 0 else '⚠️ 退出码 ' + str(r.returncode)} 重跑 {prod}")
        except Exception as e:
            print(f"     ❌ 重跑 {prod} 异常: {e}")
        if is_out:
            _stage_out_to_raw(quiet=True)
    bad = []
    for fname in list(missing) + list(stale):
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            bad.append(f"{fname}(缺失)")
        elif datetime.fromtimestamp(os.path.getmtime(fpath)) < run_start:
            bad.append(f"{fname}(仍陈旧)")
    # 🛡 2026-08-31 一劳永逸：软模式下不阻断——四量终极等「加分因子」陈旧时，
    #   final_recommend.py 自身会回退日线版，无需整轮跳过。
    return (True, bad) if soft else (len(bad) == 0, bad)


def _gate_hardwait_four_volume(run_start, max_retry=3, wait_sec=90, total_budget_sec=None):
    """🛡 2026-09-10 主人令：四量终极其日线版(FOUR_VOLUME.js)硬等待。
    盘后 final_recommend 必须等日线四量今日新鲜产出；非今日则重跑 strategy_four_volume.py 并 sleep 等待，
    最多 max_retry 次。成功产出当日数据→返回 True；超时仍陈旧→返回 False（gate 据此拒绝产出，不用陈旧）。
    区别于旧软告警：旧逻辑陈旧也照常产出（用旧）；本函数实现主人诉求"停下等重算出来再继续"。

    🔴 2026-09-17 主人令·全站口径统一（补总预算 · 与 max_retry 互补）：
      实测单次重跑 strategy_four_volume.py ~55min（9.5s/只 × ~350 只，逐只 HTTP）。
      原实现只有「次数上限 3」而**没有时间上限** ⇒ 最坏 3×5400s(SCRIPT_TIMEOUT_OVERRIDE)
      + 2×90s ≈ 4.5h，足以把整夜盘后链拖死（D 批在拒绝产出之前先空等数小时）。
      现加显式 wall-clock 总预算（默认 5400s=90min，可用 V8_FV_HARDWAIT_BUDGET 覆盖）：
        · 每次重跑**前**检查预算，耗尽 → 立即返回 False（沿用既有语义「拒绝用陈旧数据产出」，不造假）；
        · 重跑的 subprocess timeout 收敛为「剩余预算」（下限 600s），使总耗时**有界**而非线性叠加；
        · 预算正常时（首轮剩余=5400s）行为与改动前**完全一致**，不误杀单次合法重跑。
    """
    import time
    if total_budget_sec is None:
        try:
            total_budget_sec = int(os.environ.get("V8_FV_HARDWAIT_BUDGET", "5400"))
        except ValueError:
            total_budget_sec = 5400
    _t0 = time.time()
    fpath = os.path.join(V8_ROOT, "data", "FOUR_VOLUME.js")
    prod = os.path.join(ALGO, "strategy_four_volume.py")
    for attempt in range(1, max_retry + 1):
        if os.path.exists(fpath) and datetime.fromtimestamp(os.path.getmtime(fpath)) >= run_start:
            return True
        _used = time.time() - _t0
        if _used >= total_budget_sec:
            print(f"  🛑 四量硬等待总预算耗尽（已等 {_used/60:.0f}min ≥ 上限 {total_budget_sec/60:.0f}min）"
                  f"，停止重跑；本项按「陈旧·拒绝产出」处理")
            return False
        print(f"  ⏳ 四量终极其日线版非今日(run_start={run_start})，第{attempt}/{max_retry}次重跑 strategy_four_volume.py 并等待{wait_sec}s"
              f"（预算余额 {(total_budget_sec-_used)/60:.0f}min）")
        try:
            _gto = _script_timeout("strategy_four_volume.py")
            # 收敛到剩余预算（下限 600s）：保证整段硬等待总耗时 ≤ 预算 + 600s，而非 3×5400s 叠加
            _gto = max(600, min(_gto, int(total_budget_sec - _used)))
            _fv_env = dict(os.environ)
            _fv_env["V8_BACKTEST_YEARS"] = "5"  # 防重跑写回3年降级档，与L440 SCRIPT_ENV(E批)同口径
            r = subprocess.run([PY, prod], cwd=ALGO, capture_output=True, text=True, timeout=_gto, env=_fv_env)
            print(f"     {'✅' if r.returncode == 0 else '⚠️ 退出码 ' + str(r.returncode)} 重跑 strategy_four_volume.py")
        except Exception as e:
            print(f"     ❌ 重跑 strategy_four_volume.py 异常: {e}")
        if os.path.exists(fpath) and datetime.fromtimestamp(os.path.getmtime(fpath)) >= run_start:
            return True
        if time.time() - _t0 >= total_budget_sec:
            print(f"  🛑 四量硬等待总预算耗尽（重跑后已用 {(time.time()-_t0)/60:.0f}min），停止重试")
            return False
        if attempt < max_retry:
            time.sleep(wait_sec)
    return False


def _final_recommend_gate(run_start):
    """final_recommend 前的就绪门控。返回 True=可继续；False=应跳过本轮最终推荐。
    🛡 2026-08-26 补全：校验 raw_data/*.json 核心选股输入（硬，缺失/陈旧则拒绝产出，遵守「不得造假」）。
    🛡 2026-08-31 一劳永逸：四量终极（FOUR_VOLUME_60M/FOUR_VOLUME）降级为软告警——
        其本身为「加分因子，独立于日线版」，final_recommend.py 已做「60m 非今日→回退日线版」
        降级（见 final_recommend.py L289-302）。baostock 60min 源常滞后（曾陈旧到 8/22），
        列硬门控会反复阻断整轮最终推荐，反而让站点长期展示更旧的 FINAL_RECOMMEND（违背「不得造假」本意）。
        故：核心选股输入硬门控，四量软告警；四量陈旧的告警仍打印，但 final_recommend 照常产出。
    🔴 2026-09-11 主人令（选项A）：四量 60m 由「软告警」升级为【硬告警·计败不阻断】——
        仍不阻断 final_recommend（理由同上），但陈旧必计入 FAILED_SCRIPTS →
        raw_data/algo_run_report.json，使运维面板/健康检查可见。"""
    print(f"\n  🚦 final_recommend 就绪门控（核心选股输入硬门控 + 四量终极为加分因子软告警）")
    # (1) 先把本轮 out/ 产物搬运到 raw_data/，使 out-依赖输入新鲜
    _stage_out_to_raw()
    # 核心选股输入：硬门控（缺失/陈旧且重跑仍失败 → 拒绝产出）
    ok_raw, bad_raw = _gate_ensure_inputs(_FINAL_RECOMMEND_INPUTS, os.path.join(V8_ROOT, "raw_data"), run_start)
    # 四量终极 60m：🔴 2026-09-11 主人令（选项A：软告警 → 硬告警）
    #   **仍不阻断** final_recommend（脚本自带「60m 非今日 → 回退日线版」降级，
    #   2026-08-31 已实证硬门控会反复阻断整轮推荐、反而让站点展示更旧的 FINAL_RECOMMEND），
    #   但**必须计入失败账本**：写进 raw_data/algo_run_report.json 的 failed_scripts
    #   → 运维面板红灯 + 健康检查可见，杜绝「静默烂 3 天无人喊」。
    _, bad_data = _gate_ensure_inputs(_FINAL_RECOMMEND_DATA_INPUTS, os.path.join(V8_ROOT, "data"), run_start, soft=True)
    if bad_data:
        print(f"  🔴 四量 60m 输入陈旧【硬告警·计败不阻断】: {', '.join(bad_data)}")
        print(f"     （final_recommend 将回退日线版 FOUR_VOLUME.js；本项已计入失败账本）")
        FAILED_SCRIPTS.append(
            ("strategy_four_volume_60m.py",
             f"四量60m 输入陈旧（{'、'.join(bad_data)}）——已回退日线版，计为失败项")
        )
    else:
        print(f"  ✅ 四量 60m 输入为本轮新鲜产出")
    # 🛡 2026-09-10 主人令：四量终极其日线版【硬等待】——必须今日新鲜，否则停等重算，超时拒绝产出
    if not _gate_hardwait_four_volume(run_start):
        print(f"  🛑 四量终极其日线版等待超时仍非今日，拒绝产出最终推荐（避免陈日落盘汇总）")
        return False
    if ok_raw:
        print(f"  ✅ 核心选股输入+四量终极其日线版均为本轮新鲜产出，放行 final_recommend")
        return True
    print(f"  🛑 核心门控未通过，拒绝产出最终推荐（避免陈旧/造假数据）: {', '.join(bad_raw)}")
    return False


def _restore_empty_raw_outputs(run_start):
    """🆕 2026-09-05 cn 离线兜底（架构性P0专项）：本轮算法链写出的空/占位 raw_data 产物
    还原到 HEAD 版本，阻止数据源离线时的空数据经 api_push/CI 覆盖线上好版本。
    仅对前端消费的数据模块（DATA_SOURCES 命中）判空；状态文件/中间产物豁免。"""
    try:
        if V8_ROOT not in sys.path:
            sys.path.insert(0, V8_ROOT)
        from update_v8 import DATA_SOURCES, _is_raw_empty_or_stale
    except Exception as e:
        print(f"  ⚠️ import update_v8 失败（兜底跳过空产物还原）: {e}")
        return
    raw_dir = os.path.join(V8_ROOT, "raw_data")
    if not os.path.isdir(raw_dir):
        return
    restored = []
    for fname in os.listdir(raw_dir):
        if fname not in DATA_SOURCES:
            continue
        fp = os.path.join(raw_dir, fname)
        try:
            if os.path.getmtime(fp) < run_start.timestamp():
                continue
        except Exception:
            continue
        try:
            import pathlib
            is_empty, reason = _is_raw_empty_or_stale(pathlib.Path(fp))
        except Exception:
            continue
        if is_empty:
            try:
                subprocess.run(["git", "checkout", "HEAD", "--", f"raw_data/{fname}"],
                                cwd=V8_ROOT, capture_output=True, text=True, timeout=60)
                restored.append((fname, reason))
                FAILED_SCRIPTS.append((fname, f"产物空/占位({reason})→已还原HEAD防写空"))
            except Exception as e:
                print(f"  ⚠️ 还原 {fname} 失败: {e}")
    if restored:
        print(f"\n  🛑 cn 离线兜底：{len(restored)} 个空产物已还原 HEAD（不污染线上）: " +
              ", ".join(f"{f}({r})" for f, r in restored))


def _write_run_report(ok, fail, skipped, run_start):
    """🛡 2026-08-28：把本轮算法链执行结果落盘 raw_data/algo_run_report.json，
    供链尾 verify_chain_outputs 闸门与运维面板消费，杜绝「静默吞失败」。"""
    try:
        rp = os.path.join(V8_ROOT, "raw_data", "algo_run_report.json")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        report = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_start": run_start.strftime("%Y-%m-%d %H:%M:%S"),
            "ok": ok,
            "fail": fail,
            "failed_scripts": [{"script": s, "reason": w} for s, w in FAILED_SCRIPTS],
            "skipped_by_time_gate": skipped,
        }
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  📄 执行报告已写入 raw_data/algo_run_report.json")
    except Exception as e:
        print(f"  ⚠️ 写执行报告失败: {e}")


# ════════════════════════════════════════════════════════════════════════════
# 🔴 2026-09-01 主人令「监督跑算法更先进」：监督式脚本执行器
#   旧实现：subprocess.run(timeout=_to) 阻塞等待，单脚本卡死要等满 30~60min 才超时
#           （"死盯死等"）；无实时进度、无主动杀进程续跑。
#   新实现：Popen + 独立读线程实时抽 stdout/stderr 写心跳文件；若某脚本连续
#           SILENCE_KILL_SEC 秒无新输出（网络挂起/死循环/进程冻结）→ 判定卡死、
#           kill 进程并 continue 到下一脚本（绝不编造缺失产物的假数据，交由下游
#           continue-on-error / 就绪门控 / 产物完整性闸门按真实数据口径处理）。
#   铁律：被 kill 的脚本其产物视为「未产出」，下游门控会拒绝用陈旧数据冒充今日。
# ════════════════════════════════════════════════════════════════════════════
# 单脚本静默卡死判定秒数（默认 15min）。V8_ALGO_SILENCE 可调大以防极重活误杀。
SILENCE_KILL_SEC = int(_os.environ.get("V8_ALGO_SILENCE", "900"))
# 🛡 2026-09-09 一劳永逸：长静默型重活的「静默杀」阈值单独放宽。
#   背景：全局 15min 无输出即 kill 对绝大多数脚本正确，但对「长时间不发 stdout 的批量抓取型」会误杀
#   —— 实测 v8/factor_lab_gen.py 在 2026-09-09 00:04 被静默杀（冷启动 50-90min，长段落无输出），
#   产物写不出 → FACTOR_LAB 永远刷不出来，链尾还计「失败 1」。
#   现在双保险：① 脚本自带心跳（v8/factor_lab_gen.py 每 30s 一行）② 此处给静默预算兜底。
SILENCE_OVERRIDE = {
    "v8/factor_lab_gen.py": 3600,
    # 🛡 2026-09-11：CRDS 逐只抓取，段落间可能长时间无 stdout → 给 30min 静默预算，
    #   避免被全局 15min 静默杀误杀（与 2.3 的 90min 总预算配套）。
    "calc_crds.py": 1800,   # 冷启动 50-90min，给 1h 静默预算（总时长仍受 5400s 超时约束）
    # 🛡 2026-09-16 阿狸咪的工程师 · 同型第三例（D7）：日线版四量终极 5 年回测在逐只循环内零 stdout，
    #   2026-09-16 03:16:55~03:32:00 被全局 900s 静默杀误杀 ⇒ 产物写不出、卡永久陈旧。
    #   照既有范式双保险：① 脚本自带心跳（strategy_four_volume.py 已补，60s 一片，带 flush）
    #   ② 此处给静默预算兜底。日后新增「长跑 + 长段落无输出」脚本，同样两处一起加。
    "strategy_four_volume.py": 3600,
    # 2026-09-18：同型 —— backtest_tdx 全量重算期间逐只取数、段落间可长时间无 stdout，
    #   全局 900s 静默杀会误杀 ⇒ 给 1h 静默预算（总时长仍受上方 5400s 超时约束）。
    "backtest_tdx.py": 3600,
}


def _silence_budget(script_name):
    """返回该脚本的静默容忍秒数（覆盖表优先，其次环境变量，最后全局默认）。"""
    return int(SILENCE_OVERRIDE.get(script_name, SILENCE_KILL_SEC))
# 算法链心跳文件：实时进度 + 卡死信号，供 v8_cloud_watchdog 跨 run 监督 + 运维面板消费
HEARTBEAT_PATH = os.path.join(V8_ROOT, "raw_data", "algo_heartbeat.json")


def _write_heartbeat(state):
    """增量写心跳文件（失败静默，不阻断算法链）。"""
    try:
        os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
        with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _supervised_run(script, path, timeout):
    """监督式执行单个算法脚本；返回 (returncode, last_lines, killed_reason)。
    killed_reason ∈ {None, 'silence', 'timeout'}。"""
    start_ts = time.time()
    silence_limit = _silence_budget(script)   # 🛡 2026-09-09：长静默型脚本单独放宽，防误杀
    ctx = {"last_output_ts": start_ts, "last_lines": [], "start_ts": start_ts}
    lock = threading.Lock()

    _write_heartbeat({
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": script, "step": "run_algorithms",
        "last_output_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "silent_sec": 0,
        "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "starting",
    })

    proc = subprocess.Popen(
        [PY, path], cwd=ALGO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )

    def reader():
        try:
            for line in proc.stdout:
                s = line.rstrip("\n")
                with lock:
                    ctx["last_output_ts"] = time.time()
                    if s.strip():
                        ctx["last_lines"].append(s)
                        if len(ctx["last_lines"]) > 6:
                            ctx["last_lines"] = ctx["last_lines"][-6:]
        except Exception:
            pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    killed_reason = None
    while True:
        rc = proc.poll()
        if rc is not None:
            break
        now = time.time()
        with lock:
            silent = int(now - ctx["last_output_ts"])
            ls = ctx["last_lines"][-1] if ctx["last_lines"] else ""
        _write_heartbeat({
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "script": script, "step": "run_algorithms", "pid": proc.pid,
            "last_line": ls[:160],
            "last_output_time": datetime.fromtimestamp(ctx["last_output_ts"]).strftime("%Y-%m-%d %H:%M:%S"),
            "silent_sec": silent,
            "started": datetime.fromtimestamp(ctx["start_ts"]).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "running",
        })
        elapsed = now - ctx["start_ts"]
        if elapsed >= timeout:
            killed_reason = "timeout"
            break
        # 静默杀：已起跑超过启动宽限期(30s) 且 连续无输出 ≥ 该脚本的静默预算
        if elapsed > 30 and silent >= silence_limit:
            killed_reason = "silence"
            break
        time.sleep(5)

    if killed_reason:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        with lock:
            silent_now = int(time.time() - ctx["last_output_ts"])
            ls = ctx["last_lines"][-1] if ctx["last_lines"] else ""
        _write_heartbeat({
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "script": script, "step": "run_algorithms",
            "last_line": ls[:160], "silent_sec": silent_now,
            "status": "killed", "reason": killed_reason,
            "note": "卡死被监督器终止，续跑下一脚本（产物视为未产出，遵守不得造假铁律）",
        })
    else:
        # 正常结束：标记 done，避免心跳文件停留在 running 误导跨 run 监督
        with lock:
            ls = ctx["last_lines"][-1] if ctx["last_lines"] else ""
        _write_heartbeat({
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "script": script, "step": "run_algorithms",
            "status": "done", "returncode": rc, "last_line": ls[:160],
            "note": "脚本本轮执行结束",
        })
    # 等读线程把剩余 stdout 抽完，避免末几行丢失（先 join 再关 pipe）
    try:
        reader_thread.join(timeout=15)
    except Exception:
        pass
    try:
        proc.stdout.close()
    except Exception:
        pass

    with lock:
        last_lines = list(ctx["last_lines"])
    rc = proc.returncode
    if rc is None:
        rc = -9
    return rc, last_lines, killed_reason


def _freshness_baseline(stage):
    """🛡 2026-09-17 一劳永逸（D 批整夜不出·根因二）：门控「新鲜度基线」按批次语义取。

    病根（09-17 00:00~06:30 实测三连栽）：
      门控以 `run_start = datetime.now()`（本批启动时刻）判定输入是否新鲜。
      但 B/D/E 批**是分批跑的**，其输入由上批产出并已推送，mtime 必然**早于**本批启动：
        - A 批 04:31 产出 lhb_data.json / sector_rs.json / stock_profile.json
        - D 批 06:27 启动 → 这三个 mtime 比 run_start 早 1h56m → 判「陈旧」
        - 门控重跑生成器（fetch_lhb/fetch_sector_rs/gen_stock_profile 各数分钟），
          重跑产物 mtime 仍可能落在 run_start 之前（并发/时钟/写序），复检仍陈旧
        - → `_final_recommend_gate` 返回 False → **跳过 final_recommend，本轮不产出**
        - → 但 job 退出码 0（脚本 continue-on-error）→ **job 绿色「假成功」**
        - → 线上 FINAL_RECOMMEND_DATA.js 整夜停在昨日 → 主人「6 点了还没出数据」

    修法（口径对齐，不是放宽）：
      * 全链（stage=None）：输入确应由本轮自产 → 基线 = run_start（原口径不变，最严）。
      * 显式分批（stage in A/B/D/E）：该批输入由**上游批次**产出，判定基线改用
        「数据日盘后就绪下限」`FLOOR_TRADING=(16,30)`（与 .github/scripts/v8_stage_gate.py
        同一常量、同一语义）——只要输入是本数据日 16:30 之后产出的，就属「今日盘后新鲜」。
      * 这样既不放过陈旧数据（昨日产物仍会被判 STALE），也**不再要求后批的输入
        「比后批本身还新」**这个物理上不可能的事。
    """
    if stage is None:
        return datetime.now()
    # 数据日：与全链路同一中枢（交易日内=今天；非交易日/09:00 前=最近交易日）
    try:
        _d = _last_trading_day()
    except Exception:
        _d = datetime.now().date()
    try:
        base = datetime(_d.year, _d.month, _d.day, 16, 30)
    except Exception:
        base = datetime.now()
    print(f"  🧭 新鲜度基线（stage={stage} 分批模式）：{base:%Y-%m-%d %H:%M}"
          f"（数据日 {_d} 的盘后就绪下限；全链模式才用 run_start=now）")
    return base


def step_run(order=None, stage=None):
    if order is None:
        order = ORDER
    print(f"\n[1] 运行算法链（{len(order)} 个）")
    # 记录本轮启动时间，供 final_recommend 门控判断「输入是否本轮新鲜产出」
    # 🛡 2026-09-17：分批模式（stage 显式）改用「数据日盘后基线」，见 _freshness_baseline 注释。
    run_start = _freshness_baseline(stage)
    # 🔴 盘后选股策略统一门控：18:00 前跳过所有选股脚本
    picking_ready = _is_post_close_picking_ready()
    # 🛡 2026-09-11 一劳永逸：链级判定必须显式传给子脚本，杜绝「两套时间门打架」。
    #   实测 run#1692（05:16 起跑）：链级 05:16 判 picking_ready=True 放行全部选股脚本，
    #   但 scripts 内的 utils/time_gate.check_stock_picking_ready 在 06:36 按「现在几点」
    #   重新否决 → 4 个脚本 exit 1 → B 批永不满 3/3 → target_stage 恒为 B → D/E 永不执行。
    #   链一旦判定放行，子脚本不得二次否决（闸门是唯一决策点，这是本仓既定铁律）。
    if picking_ready:
        os.environ["TIME_GATE_BYPASS"] = "1"
        print("  🔓 链级已判定盘后选股就绪 → TIME_GATE_BYPASS=1 下发子脚本（口径唯一，杜绝二次否决）")
    mode = _run_mode()
    is_td = _is_trading_day_now()
    if mode == "backfill":
        os.environ["V8_REF_DATE"] = _last_trading_day()  # 回填：日期改写上一交易日
    # 🛡 2026-09-07 主人令铁律：周六 / 假期第一天持有上一交易日的 T+1 数据（龙虎榜/机构调研/
    #   大宗/两融等收盘后发布、次日才全），**必须照常采集**，不得一刀切跳过。
    #   仅「假期中段/最后一天」这类确无 T+1 的日子才跳过采集（省 API、避免空转）。
    #   交易日 official 模式本就全量采集，不受影响。
    _t1 = _is_t1_data_day()
    skip_fetch = (mode == "backfill" and not _t1)
    print(f"  🕐 当前时间 {datetime.now():%H:%M} | 盘后选股就绪 {'✅' if picking_ready else '⏳'}"
          f" | 模式={mode}"
          + (f" | T+1窗口✅照常采集（上一交易日的次日）" if (mode == "backfill" and _t1) else "")
          + (f" | 回填:跳过实时采集+日期改写上一交易日" if skip_fetch else ""))
    ok, fail = 0, 0
    skipped = []
    for script in order:
        # 支持 scripts/ 前缀（仓库根 scripts/）与 v8/ 前缀（仓库根 v8/）
        if script.startswith("scripts/") or script.startswith("v8/"):
            path = os.path.join(V8_ROOT, script)
        else:
            path = os.path.join(ALGO, script)
        if not os.path.exists(path):
            print(f"  ❌ 缺失脚本: {script}")
            fail += 1
            FAILED_SCRIPTS.append((script, "脚本文件缺失"))
            continue
        # 🔧 2026-08-29 验证模式：非交易日跳过数据采集（无新数据，避免把陈旧数据冒充今日/浪费 API）
        if skip_fetch and script.startswith("fetch"):
            print(f"  ⏭️  {script}  ← 跳过采集（非交易日无新数据，validation 模式）")
            skipped.append(script)
            continue
        # 🔴 盘后选股策略门控：未到 18:00 且脚本属于选股策略 → 跳过
        if not picking_ready and (script in STOCK_PICKING_SCRIPTS or script in BACKTEST_SCRIPTS):
            print(f"  ⏭️  {script}  ← 跳过（盘后数据未全就绪，18:00 前禁止生成选股/回测结果，防半日数据假回测）")
            skipped.append(script)
            continue
        # 🛡 2026-08-26 一劳永逸（bug7/bug8）：final_recommend 必须先过就绪门控，
        #   确保所有选股输入均本轮新鲜产出后才汇总，杜绝「某选股还没跑完就推荐完成」。
        if script == "final_recommend.py" and not _final_recommend_gate(run_start):
            print(f"  ⏭️  跳过 final_recommend（就绪门控未通过，本轮不产出最终推荐）")
            FAILED_SCRIPTS.append((script, "就绪门控未通过（上游选股输入陈旧/缺失）"))
            continue
        print(f"  ▶ {script}  ({datetime.now():%H:%M:%S})  [监督执行·静默杀≥{SILENCE_KILL_SEC//60}min]")
        # 2026-09-01 主人令「监督跑算法更先进」：用监督式执行器替代朴素 subprocess.run
        #   —— 实时写心跳 + 静默超时即杀进程续跑（永不再 30~60min 死等单脚本卡死）。
        # 🛡 2026-09-04：链内脚本统一打标 V8_IN_CHAIN=1（v8/ 独立脚本据此跳过自带 git 推送，防双推插针）
        os.environ["V8_IN_CHAIN"] = "1"
        # 🛡 2026-09-04：按「阶段+脚本」注入环境变量（SCRIPT_ENV，如 E 回测批让 strategy_four_volume 跑回测模式）
        # 🔴 2026-09-17 主人令·全站口径统一：注入必须**用完即还原**（finally 兜底）。
        #   原写法 `os.environ[k]=v` 直写进程级 env 且从不还原 ⇒ 残留到后续脚本/后续批次，
        #   与「键=脚本名」叠加后产生「B 批/D 批跑 5 年回测」（详见 SCRIPT_ENV 上方说明）。
        _injected = {}
        for _ek, _ev in SCRIPT_ENV.get((stage, script), {}).items():
            _injected[_ek] = os.environ.get(_ek)
            os.environ[_ek] = _ev
        _to = _script_timeout(script)
        _sl = _silence_budget(script)  # 该脚本的实际静默预算（SILENCE_OVERRIDE 优先）
        try:
            try:
                rc, last_lines, killed_reason = _supervised_run(script, path, _to)
            except Exception as e:
                fail += 1
                print(f"     ❌ 监督执行异常: {e}")
                FAILED_SCRIPTS.append((script, f"监督执行异常 {e}"))
                continue
            if killed_reason == "silence":
                fail += 1
                print(f"     💀 静默卡死(>{_sl//60}min 无输出)，监督器已终止并续跑下一脚本")
                FAILED_SCRIPTS.append((script, f"监督器静默杀(>{_sl//60}min 无输出)"))
                continue
            if killed_reason == "timeout":
                fail += 1
                print(f"     ⏱️ 硬超时(>{_to // 60:.0f}min)，监督器终止并续跑")
                FAILED_SCRIPTS.append((script, f"超时 >{_to // 60:.0f}min"))
                continue
            if rc == 0:
                ok += 1
                last = last_lines[-1] if last_lines else ""
                print(f"     ✅ ok | {last[:80]}")
            else:
                fail += 1
                print(f"     ⚠️ 退出码 {rc}")
                tail = "\n".join(last_lines[-3:])
                print("     " + tail.replace("\n", "\n     ")[:400])
                # 🛡 2026-08-28：抓取末行作为失败原因，供链尾闸门/运维面板定位
                reason = last_lines[-1] if last_lines else f"退出码 {rc}"
                FAILED_SCRIPTS.append((script, f"退出码 {rc} | {reason[:160]}"))
        finally:
            # 🛡 2026-09-17：原值还原（原本没有 → 摘除），杜绝 SCRIPT_ENV 跨脚本/跨批泄漏
            for _ek, _pv in _injected.items():
                if _pv is None:
                    os.environ.pop(_ek, None)
                else:
                    os.environ[_ek] = _pv
    print(f"  算法运行: 成功 {ok} / 失败 {fail}")
    # 🛡 2026-08-28 一劳永逸：失败清单汇总 —— 过去被 continue-on-error 静默吞掉，
    #   导致 08-28 候选池停更 1.9 天仍无人知晓。现在必须显式列出。
    if FAILED_SCRIPTS:
        print(f"\n  🛑 本轮失败/未产出脚本 {len(FAILED_SCRIPTS)} 个（对应前端卡将保持陈旧）:")
        for _s, _why in FAILED_SCRIPTS:
            print(f"     • {_s}  ← {_why}")
    if skipped:
        print(f"\n  ⏭️ 因未到 18:00 跳过的选股脚本 {len(skipped)} 个: {', '.join(skipped)}")
    # 2026-09-01 主人令：算法链本轮执行完毕，心跳置 completed（供跨 run 监督判定"已脱离卡死"）
    _write_heartbeat({
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": "(chain-end)",
        "step": "run_algorithms",
        "status": "completed",
        "ok": ok, "fail": fail,
        "note": "算法链本轮执行完毕",
    })
    _restore_empty_raw_outputs(run_start)
    _write_run_report(ok, fail, skipped, run_start)


def step_stage():
    print("\n[2] stage_to_raw（重命名 + 注入 update_time）")
    sys.path.insert(0, ALGO)
    import stage_to_raw
    return stage_to_raw.main()




def step_push():
    if not PUSH:
        print("\n[3] 跳过推送（V8_PUSH != 1）")
        return
    print("\n[3] 推送 raw_data → main（api_push_raw，来源驱动增量）")
    # 2026-08-22 来源驱动增量推送（主人令升级）：git status 收集"本次 changed"作清单，
    #   聚焦推送本次算法链产物，不再全量 848 文件扫描；配合 api_push_raw 的 PUSH_FILES，
    #   单次 tree 请求大小与仓库规模解耦（422 根治）。
    # 🛡 2026-09-11 一劳永逸（run#1692 实证）：原写法把「清单不可得」误当「无变更」跳过。
    #   自托管 runner 上 git 属主冲突（dubious ownership）会让 git status 直接失败，
    #   清单一空就 return → 整轮 84 分钟产物零推送，且**静默**（只印一句「无变更」）。
    #   现三态严格区分：None=不可得(必须全量推) / ""=确无变更(可跳过) / 有值(增量推)。
    manifest = None
    try:
        out = subprocess.run(["git", "status", "--porcelain", "raw_data/", "data/"],
                             cwd=V8_ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if out.returncode == 0:
            manifest = ",".join(ln.split(None, 1)[1] for ln in out.stdout.splitlines() if ln.strip())
        else:
            print(f"  ⚠️ git status 退出码 {out.returncode}（自托管 runner 属主冲突?）")
    except Exception as e:
        print(f"  ⚠️ 收集变更清单异常: {e}")
    if manifest:
        print(f"  📋 本次变更清单: {manifest[:200]}{'...' if len(manifest) > 200 else ''}")
        env = dict(os.environ)
        env["PUSH_FILES"] = manifest
        r = subprocess.run([PY, "api_push_raw.py"], cwd=V8_ROOT, env=env)
    elif manifest == "":
        print("  ℹ️ git 判定本次无 raw_data/data 变更，交由链尾「唯一推送」步复核")
        return
    else:
        print("  ⚠️ 变更清单不可得 → 全量来源驱动推送（api_push_raw 与远端 tree 比对，不依赖本地 git）")
        r = subprocess.run([PY, "api_push_raw.py"], cwd=V8_ROOT)
    if r.returncode == 0:
        print("  ✅ 已推送")
    else:
        print("  ❌ 推送失败，请检查 GITHUB_TOKEN / 网络")


def step_append_lhb_history():
    """累积龙虎榜历史（raw_data/lhb_data.json → raw_data/lhb_history.json），
    供 index.html 共振日历历史 + lhb_resonance/lhb_north_seat 独立页使用。
    逻辑已内联在 stage_to_raw；lhb_data 由本链 fetch_lhb 产出并 stage 后已就位。"""
    print("\n[2.5] 累积 LHB 历史 → raw_data/lhb_history.json")
    try:
        sys.path.insert(0, ALGO)
        import stage_to_raw
        stage_to_raw.append_lhb_to_history()
        print("  ✅ LHB 历史累积完成")
    except Exception as e:
        print(f"  ⚠️ LHB 历史累积失败: {e}")


def step_gen_lhb_7d():
    """⚠️ DEPRECATED（2026-09-13 阿狸咪的工程师）：本函数已停用，调用点已注释。
    保留函数体仅供回滚；不要再挂回任何批次（产物 LHB_7D.js / lhb_7d.json 均无消费方）。

    生成龙虎榜 7 日累计数据（机游共振 + 北向席位），输出 raw_data/lhb_7d.json + data/LHB_7D.js。
    依赖 step_append_lhb_history 已把当日数据追加进 raw_data/lhb_history.json，同时读取 raw_data/lhb_data.json 当日明细兜底。"""
    print("\n[2.6] 生成 LHB 7 日累计 → data/LHB_7D.js")
    try:
        r = subprocess.run([PY, "gen_lhb_7d.py"], cwd=ALGO)
        if r.returncode == 0:
            print("  ✅ LHB 7 日累计完成")
        else:
            print("  ⚠️ LHB 7 日累计脚本返回非零")
    except Exception as e:
        print(f"  ⚠️ LHB 7 日累计失败: {e}")


def step_build_pool_tracker():
    """🆕 2026-08-31 阶段 1：v8 选股生命周期跟踪。
    读取 raw_data/algo_track.json（三 algo 跟踪池：四量终极/板块龙头/大牛股猎手），
    去重 → 应用专家阈值判状态（强势/回调买点/见顶/走弱/正常）→ 输出
    raw_data/v8_pool_tracker.json + data/V8_POOL_TRACKER.js（注入 window.V8_POOL_TRACKER）。
    零网络依赖；algo_track 缺失时输出空占位不抛错。"""
    print("\n[2.7] v8 选股生命周期跟踪 → data/V8_POOL_TRACKER.js")
    try:
        r = subprocess.run([PY, "build_pool_tracker.py"], cwd=ALGO)
        if r.returncode == 0:
            print("  ✅ v8 选股生命周期跟踪完成")
        else:
            print("  ⚠️ build_pool_tracker 返回非零（继续，不阻断后续）")
    except Exception as e:
        print(f"  ⚠️ v8 选股生命周期跟踪失败: {e}")


def main():
    import argparse
    # 🔴 2026-09-13 一劳永逸（阿狸咪的工程师）：跑批前「工作区 vs 远端」一致性守卫。
    #   根因（09-13 实测）：本机工作区内容由坚果云从另一台机同步，常与远端 HEAD 不一致，
    #   而跑批直接执行工作区里那份脚本 ⇒ 远端已修好的代码被从产物侧**静默撤销**（假成功）。
    #   守卫先把不一致的关键脚本备份到**仓库外**，再 `git checkout <ref> -- <文件>` 拉齐；
    #   拉不齐则**中止本次跑批**（fail-closed，禁止用落后代码出产物）。
    #   逃生舱：环境变量 V8_SKIP_WS_GUARD=1（正常不要设）。
    try:
        import subprocess as _sp, sys as _sys, os as _os
        _d = _os.path.dirname(_os.path.abspath(__file__))
        _cands = [_os.path.join(_d, "v8_ws_sync_guard.py"),
                  _os.path.join(_os.path.dirname(_d), "v8_ws_sync_guard.py")]
        _g = next((c for c in _cands if _os.path.exists(c)), None)
        if _g:
            _r = _sp.run([_sys.executable, _g, "--heal"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
            print((_r.stdout or "").rstrip())
            if _r.returncode != 0:
                print("🔴 工作区一致性守卫未通过 → 中止本次跑批（禁止用落后代码出产物）")
                return 2
        else:
            print("⚠️ 未找到 v8_ws_sync_guard.py → 跳过工作区一致性守卫")
    except Exception as _e:
        print(f"🔴 工作区一致性守卫异常：{_e} → 中止本次跑批（fail-closed）")
        return 2
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=list(STAGES.keys()), default=None)
    ns, _ = ap.parse_known_args()
    stage = ns.stage
    print(f"=== v8 算法编排  {datetime.now():%Y-%m-%d %H:%M:%S}  stage={stage or 'ALL'} ===")
    # 🔴 2026-09-02 主人令「分批跑」：上游自产仅 A 批或全链跑；B/C/D 批依赖 A 已推送的 gold_pool 等
    if stage in (None, "A"):
        step_v8_self_sufficiency()  # 2026-08-02 原生化: 先自产 4 类上游输入
    else:
        print(f"\n[0] 跳过 v8 原生化自产上游输入（stage={stage}，gold_pool 由 A 批产出并已推送）")
        os.makedirs(OUT, exist_ok=True)
    step_seed_inputs()          # 默认 no-op, V6_SEED=1 才重灌
    if stage is None:
        order = ORDER
    else:
        order = STAGES[stage]
        print(f"  🎯 stage={stage} 仅跑 {len(order)} 个脚本（其余由对应批次产出）")
    # 🛡 2026-09-04 主人令一劳永逸：生命周期/LHB 累积前置——必须先落当日 v8 选股生命周期池，
    #   D 批 final_recommend 才能覆盖生命周期卡股票（原顺序 final_recommend 05:37 →
    #   pool_tracker 05:48 倒挂，最终推荐用的是昨日池，主人质疑「不够权威」实锤）。
    #   仅全链(无--stage)或 D 汇总批执行；A/B/E 批跳过（D 批会补）。
    # 🛡 2026-09-11 主人报「生命周期也没更新」一劳永逸修复：
    #   原为 `if stage in (None, "D")` —— 生命周期池(V8_POOL_TRACKER)只有 D 批产出。
    #   但 D 批 PREREQ 依赖 B 就绪，B 又要求 CRDS 新鲜；CRDS 一旦卡住 → D 永久饿死
    #   → **最终推荐与生命周期同时停更**（09-10~09-11 事故实证）。
    #   生命周期池语义属「选股池构建」，D 批 final_recommend 是消费者；
    #   生产者绑在消费者批次里是反向依赖 → 扩为 B/D 均执行。
    if stage in (None, "B", "D"):
        # 🔴 盘后选股策略门控：LHB 7日累计属于选股向汇总，未到 18:00 不处理当日龙虎榜数据
        if _is_post_close_picking_ready() and _is_trading_day_now():
            step_append_lhb_history()
            # 🛑 2026-09-13 阿狸咪的工程师：gen_lhb_7d.py **已停跑（2026-09-13 阿狸咪的工程师）**。
            #   取证：data/LHB_7D.js 前端零引用（index.html L527 早已停止注入）；
            #         raw_data/lhb_7d.json 全仓无任何读取者（grep 仅命中 gen_lhb_7d.py 自身写入）。
            #   但 ORDER(L197)/STAGES(L284) 注释后，本处硬调用仍在 → B/D 批每天白跑。
            #   现一并停用，保留函数体（step_gen_lhb_7d）便于随时回滚。
            # step_gen_lhb_7d()
            step_build_pool_tracker()
        else:
            print("\n[2.5-2.7] ⏭️ 跳过 LHB 历史累积 + LHB 7日累计 + v8 选股生命周期（非交易日或盘后策略未就绪）")
    else:
        print(f"\n[2.5-2.7] ⏭️ 跳过 LHB 历史累积 + 生命周期前置（stage={stage}，A/C/E 批不承担该职责）")
    step_run(order=order, stage=stage)
    n = step_stage()
    step_push()
    print(f"\n=== 完成。staged {n} 个文件 ===")


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令·一劳永逸：算法编排器仅允许云端算法链定时任务执行
    #   （v8_algo_cloud 19:15 等）；本地禁止手动跑算法产数据，避免与主站分叉。
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/run_algorithms.py"):
        sys.exit(2)
    sys.exit(main())
