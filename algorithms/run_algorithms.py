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

# ── 单脚本超时（2026-08-31 一劳永逸修复）──────────────────────────────────
# 背景：原代码把 1800s 硬编码在两处 subprocess.run，实测 run 33316835316 中
#   calc_stock_rps.py 因遍历全 universe（数千只）逐只取 K 线 + 网络退避重试，
#   30 分钟不够 → 超时被杀 → data/STOCK_RPS.js 长期陈旧（前端 RPS 卡不更新）。
# 修法：默认阈值可配（V8_ALGO_TIMEOUT），并给重活单独放宽，不影响其他脚本。
import os as _os

DEFAULT_SCRIPT_TIMEOUT = int(_os.environ.get("V8_ALGO_TIMEOUT", "1800"))

# 计算量大 / 网络重活单独放宽（秒）。新增重活在此登记即可，无需改调度代码。
SCRIPT_TIMEOUT_OVERRIDE = {
    "calc_stock_rps.py": 3600,   # 全 universe 逐只取 K 线，实测 30min 偶发不够
    "calc_crds.py": 2700,        # 逆势龙头 CRDS，同样遍历较广
    "gen_stock_profile.py": 2700,
    "v8/backtest_crds.py": 2400,    # 逆势龙头 CRDS 回测：读 crds history + baostock 取 K 线回填收益
    "factor_lab_backtest.py": 1800,  # 🆕 700日长历史抓取+五分位分层回测（cn ~5min / 云端 ~15min）
    "v8/factor_lab_gen.py": 5400,    # 🛡 2026-09-04 云端适配：全市场主板 baostock 逐只，冷启动 ~50-90min（缓存随 raw_data/flab_work 入仓逐晚收敛，热缓存后数分钟）
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
    #   致 calc_potential_picks(潜力挖掘) 与 final_recommend 读脏数据。现正式挂链（仅依赖 stock_names），
    #   使算法链自洽、不依赖上游副作用。门控仍保留作安全网。
    "gen_stock_profile.py",            # → raw_data/stock_profile.json（个股行业/概念，潜力挖掘&最终推荐共用）
    "fetch_stock_quote_v8.py",         # → raw_data/stock_quote.json + data/STOCK_QUOTE.js（全市场实时报价快照，查股功能用）
    "fetch_sh_index_fib.py",
    "fetch_inst_trade.py",
    "fetch_sector_rs.py",
    "fetch_lhb.py",
    # 🛡 2026-08-20 一劳永逸：5 年长 K 线 fetcher 补入算法链（此前无任何调度方，
    #   且只写 out/ 不 bridge raw_data/ → INDEX_HISTORY/MARKET_PATH_PROBABILITY 永不更新）。
    #   必须在 market_path_probability.py 之前执行（它是概率卡的输入源）。
    "scripts/fetch_index_history.py",
    # 🛡 2026-08-29 主人令：补跑第二基准（中证1000 / 国证A指），判断 +6% excess 是 alpha 还是风格 beta。
    "scripts/fetch_index_history_multi.py",
    "calc_crds.py",
    "build_candidate_pool.py",         # 读 guanlan/maharo 输入 → gold_pool / candidate_pool
    "calc_stock_rps.py",               # → data/STOCK_RPS.js（个股RPS+RS，读 candidate.json 做 universe）
    "generate_top10.py",               # 读 fundamental_quality / gold_pool → raw_data/top10_daily.json + raw_data/history/top10_daily_YYYYMMDD.json
    # 🛡 2026-08-29 主人令：A/B 对照（金股池/候选池/全市场同一信号收益），每日累积信号、T+N 后回填收益。
    "scripts/ab_universe_backtest.py",
    "backtest_tdx.py",                 # 读 gold_pool 输入
    "backtest_comprehensive.py",       # 读 raw_data/history/top10_daily_YYYYMMDD.json（必须在 generate_top10 之后）
    "export_optimized_strategy.py",    # → raw_data/optimized_strategy.json（读 backtest_tdx.json 汇总优化策略效果）
    "strategy_four_volume_60m.py",     # → data/FOUR_VOLUME_60M.js（四量终极60min版，baostock独立数据源）
    "strategy_four_volume.py",         # 🛡 2026-08-19 阿狸咪根治孤儿：日线版 FOUR_VOLUME.js 一直在 ORDER 漏挂 → 四星终极卡 4 格 0。render 端已合并读 60m 兜底，这里补齐日线数据链。
    "market_path_probability.py",      # 🛡 2026-08-19 阿狸咪补对齐：路径概率预测卡 → data/INDEX_HISTORY.js + data/MARKET_PATH_PROBABILITY.js（5年上证K线+江恩+缠论+形态匹配+路径ABC）
    "market_regime.py",                # 🛡 2026-08-19 阿狸咪补对齐：宏观环境卡 → data/MACRO.js + data/MARKET_REGIME.js（国债+LPR+银行间利率+利率上行期板块推荐框架）
    "sector_recommendation.py",        # 🛡 2026-08-19 阿狸咪补对齐：板块推荐卡 → data/SECTOR_RECOMMENDATION.js（13板块按优先级+异动跟随/已涨过标）
    "update_triple_resonance_history.py",  # 累积 triple_resonance_history
    "gen_triple_consensus.py",         # 读 top10 / fundamental / gold_pool
    "gen_triple_track.py",             # 读 triple_history / gold_pool / backtest
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
    "calc_potential_picks.py",          # 🔮 2026-08-23 恢复：潜力挖掘（板块+股票预测推荐） → data/POTENTIAL_PICKS.js（读 CONCEPT_RANKING+STOCK_PROFILE+STOCK_QUOTE）
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
    #   2026-09-04 强势突破选股（高手反推 v1）：依赖当日 h_auto_buy 池，须在其后、track 前跑。
    "strong_breakout.py",
    "track_h_auto_buy.py",
    # 🛡 2026-09-04 主人令（一劳永逸挂链）：动量共识筛选器此前零调度成孤儿——
    #   只被 update_v8.py 的 run_experiment_cards() 副作用式调用（部署链，失败仅告警不阻断），
    #   算法链从不调度 → 它是最终推荐 8 源里唯一「链外依赖」的一源，与强势突破不对称。
    #   现正式挂链（B 批，依赖 A 批 fetch_stock_quote_v8.py 产出的 STOCK_QUOTE，纯本地计算无重抓）。
    #   runner 无参调用 → 由 SCRIPT_ENV 注入 V8_MOMENTUM_EMIT_JS=1 触发 --emit-js 等价行为。
    "scripts/momentum_common_filter.py",   # → data/MOMENTUM_FILTER.js（动量共识筛选·无未来函数版）
    #   杜绝「某选股还没跑完，推荐却已生成」的抢跑问题。
    #   🆕 2026-09-04 主人令：因子实验室(FACTOR_LAB.js)此前零调度成孤儿（运维红灯）——
    #      生成器 v8/factor_lab_gen.py 挂在 final_recommend 之前（final_recommend 方案B融合读它）。
    "v8/factor_lab_gen.py",            # → data/FACTOR_LAB.js（异常换手率·重点池 + ROE 全市场主板）
    "final_recommend.py",              # → FINAL_RECOMMEND_DATA.js（跨策略共振 Top5，管线最终产物，置于末尾）
    #   前端策略回顾卡长期为空/陈旧）。统一挂链尾（依赖各自历史/截面数据已就位）。
    #   - rps：读 stock_rps 截面（RPS 为相对强度指标，非选股信号引擎，回测为截面有效性说明）
    #   三者失败均不影响选股结果，仅自身卡片可能不刷新。
    "v8/backtest_crds.py",            # → data/CRDS_BACKTEST.js（逆势龙头 CRDS 真实历史回测）
    # 🆕 2026-09-04 主人令「都按你的建议做」：因子实验室独立分层回测（升4⭐证据链）
    "factor_lab_backtest.py",         # → data/FACTOR_LAB_BACKTEST.js（五分位分层·胜率/回撤/OOS）
]



# 🔴 2026-09-02 主人令「分批跑」：把单轮串行 ORDER 拆成 4 个按时触发的 stage，
#   每 stage 独立触发、独立 timeout，final_recommend 独占 D 批（不再被单窗口掐断）。
#   跨 stage 产物经 main 分支传递：每 stage 跑完即 stage(out→raw_data)+push，
#   下游 stage 的云端 run checkout main 即含上游当日产物。
#   同 stage 内严格沿用 ORDER 相对次序（build_candidate_pool 在 calc_stock_rps 前等依赖不变）。
STAGES = {
    "A": [  # 数据采集批（~16:40 CST，龙虎榜16:30后）：纯 fetch + 上游自产前置
        "fetch_fundamental_quality.py", "fetch_stock_names.py", "gen_stock_profile.py",
        "fetch_stock_quote_v8.py", "fetch_sh_index_fib.py", "fetch_inst_trade.py",
        "fetch_sector_rs.py", "fetch_lhb.py",
        "scripts/fetch_index_history.py", "scripts/fetch_index_history_multi.py",
        "fetch_orphan_suspension.py", "fetch_orphan_market_alerts.py",
        "fetch_orphan_nt_data.py", "fetch_orphan_sector_fund_flow.py",
    ],
    "B": [  # 选股批（~18:10 CST，盘后数据齐）：核心选股策略
        "calc_crds.py", "build_candidate_pool.py", "calc_stock_rps.py", "generate_top10.py",
        "strategy_four_volume_60m.py", "strategy_four_volume.py",
        "market_path_probability.py", "market_regime.py", "sector_recommendation.py",
        "update_triple_resonance_history.py",   # 累积 triple_resonance_history（在 gen_triple_consensus 之前）
        "gen_triple_consensus.py", "gen_triple_track.py", "calc_volatility_watch.py",
        "gen_stock_stop.py", "gen_algo_track.py", "calc_sentiment_cycle.py",
        "refresh_dividend_cninfo.py", "calc_potential_picks.py",
        "refresh_stock_metadata.py", "fetch_weekend_run.py",   # 周末复盘/周度汇总（原 ORDER 漏挂 STAGE）
        "auto_run_dn_algorithm.py", "strong_breakout.py", "track_h_auto_buy.py",
        "scripts/momentum_common_filter.py",   # 🆕 2026-09-04 挂链：动量共识筛选（读 STOCK_QUOTE，纯本地）
    ],
    # 🛡 2026-09-04 主人令「策略全部数据出来→最终数据上线→然后才是回测」时序重排：
    #   原 C(回测 19:15) 在 D(final_recommend 20:00) 之前 → 回测汇总胶囊早于最终推荐，时序倒挂。
    #   现改为 A(16:40 采集) → B(18:10 选股) → D(20:00 汇总·最终推荐上线) → E(21:00 回测)。
    #   键名 C 退役；回测批内容原样迁入 E，另收编 strategy_four_volume.py（回测模式，SCRIPT_ENV 注入）。
    "E": [  # 回测批（~21:00 CST，最终推荐上线后）：backtest 全家
        "scripts/ab_universe_backtest.py", "backtest_tdx.py", "backtest_comprehensive.py",
        "backtest_expectancy.py",          # 🆕 期望收益回测：walk-forward 产出 raw_data/backtest_expectancy.json
        "export_optimized_strategy.py",   # 读 backtest_tdx.json 汇总优化策略（在 backtest_tdx 之后）
        "v8/backtest_crds.py",   # 逆势龙头 回测（原 ORDER 漏挂 STAGE）
        "v8/backtest_rps.py",   # 🆕 2026-09-06 主人令：RPS A档 30 天样本考核（读 history/stock_rps_* 日归档 → raw_data/rps_backtest.json；baostock 失败自动降级空回测不挂 CI）
        "factor_lab_backtest.py",   # 🆕 因子实验室分层回测（读 _rps_cache，依赖 B 批 calc_stock_rps）
        # 2026-09-06 主人令：AI预测卡回测 INVALID → 下架，停跑 path_probability_backtest.py
        "strategy_four_volume.py",  # 四量终极回测模式（SCRIPT_ENV 注入 V8_BACKTEST_YEARS=3 → 补写 FOUR_VOLUME_BACKTEST.js，根治孤儿）
    ],
    "D": [  # 汇总批（~20:00 CST，依赖全部）：因子实验室 + final_recommend（LHB历史/7d/生命周期由主流程前置）
        "v8/factor_lab_gen.py",   # → data/FACTOR_LAB.js（final_recommend 方案B融合依赖，必须在前）
        "final_recommend.py",
    ],
}

# 🛡 2026-09-04 主人令：回测批需要「选股脚本以回测模式运行」——runner 对所有脚本无参调用，
#   故按脚本注入环境变量（strategy_four_volume.py 读 V8_BACKTEST_YEARS>0 时同时跑近 N 年回测
#   并补写 data/FOUR_VOLUME_BACKTEST.js）。仅影响 E 回测批；B 选股批无注入、保持轻快。
SCRIPT_ENV = {
    "strategy_four_volume.py": {"V8_BACKTEST_YEARS": "3"},
    "backtest_expectancy.py": {"V8_USE_BAOSTOCK": "1"},   # 🆕 runner 用 baostock 拉全量K线，产出新鲜回测
    # 🆕 2026-09-04 挂链配套：动量共识筛选器需 --emit-js 才写 data/MOMENTUM_FILTER.js，
    #   而 runner 对所有脚本无参调用 → 用环境变量触发（脚本内已支持，与 --emit-js 等价且幂等）。
    "scripts/momentum_common_filter.py": {"V8_MOMENTUM_EMIT_JS": "1"},
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
    "calc_stock_rps.py",             # 个股 RPS（依赖候选池结果）
    "generate_top10.py",             # 多维共振 TOP10 精选
    "strategy_four_volume.py",       # 四量终极 日线选股
    "strategy_four_volume_60m.py",   # 四量终极 60min 选股
    "update_triple_resonance_history.py",  # 三重历史累积
    "gen_triple_consensus.py",       # 三重共识选股
    "gen_triple_track.py",           # 三重跟踪
    "final_recommend.py",            # 跨策略共振 Top5（管线最终产物）
    "gen_algo_track.py",             # 算法追踪
    "calc_sentiment_cycle.py",       # 情绪周期（读 LIMIT_UP_HEATMAP）
    "auto_run_dn_algorithm.py",      # H 反推算法
    "strong_breakout.py",            # 强势突破选股（高手反推版，依赖当日 h_auto_buy 池）
    "scripts/momentum_common_filter.py",  # 🆕 2026-09-04 挂链：动量共识筛选（读 STOCK_QUOTE 实时快照，属选股类，18:00 前禁跑）
    "track_h_auto_buy.py",           # H 反推跟踪
    "calc_volatility_watch.py",      # 波动率观察选股
    "gen_stock_stop.py",             # ATR 止损止盈（读候选宇宙日K）
    "gen_lhb_7d.py",                 # 龙虎榜 7 日累计（选股向汇总）
}
# 🔴 2026-09-03 主人令「回测页跟着最终推荐的算法时间走，太早算就无效、浪费」：
#   回测批与选股批同一盘后门控 —— 交易日盘中/盘前（06:00-17:59）即使 force 跑链，
#   也禁止重算回测，防止用半日数据重算出「看起来新鲜」的假回测（今日 13:14 事故根因：
#   STOCK_PICKING_SCRIPTS 门控漏掉回测批，盘中 force 链跳过选股但照跑回测并重刷 update_time）。
BACKTEST_SCRIPTS = {
    "scripts/ab_universe_backtest.py",
    "backtest_tdx.py",
    "backtest_comprehensive.py",
    "backtest_expectancy.py",
    "export_optimized_strategy.py",
    "v8/backtest_crds.py",
}
# 18:00 = 所有盘后数据（龙虎榜/北向/板块资金/个股行情/机构调研等）稳定就绪时间
_STOCK_PICKING_READY_HOUR, _STOCK_PICKING_READY_MIN = 18, 0
# 次日凌晨补跑的截止时刻（CST）：过了这个点就属于新交易日的盘前，不再放行
_NEXT_DAY_CUTOFF_HOUR = 6


def _is_post_close_picking_ready():
    """判断当前可否跑盘后选股策略（CST）。

    🛡 2026-08-29 一劳永逸根因修复（候选池停更 3 天的真凶）：
    原写法只判断「hour > 18」，把**次日凌晨补跑**（00:00~05:59）也误判成
    「未到 18:00」→ 实测 run #1204 在北京时间 08-29 00:43 跑算法链，
    20 个选股脚本（calc_crds / build_candidate_pool / calc_stock_rps /
    generate_top10 / strategy_four_volume* ...）被整批跳过 → 候选池不产出 →
    CRDS / RPS / 最终推荐整条选股链停更，链尾闸门随之 failure。

    本门控真正要挡的是「盘中/盘前数据不全时抢跑选股」，不是挡凌晨补跑 ——
    凌晨时上一交易日的盘后数据早已齐全。

      放行 18:00~23:59  当日盘后，数据已齐
      放行 00:00~05:59  次日凌晨补跑，上一交易日盘后数据已齐
      拦截 06:00~17:59  盘前/盘中，当日尚未收盘，禁止生成选股结果
    """
    # 2026-08-29 主人周末审计：V8_FORCE_RUN=1 时直接放行（周末/假期审计验证用，
    # 此时市场已收盘、无盘中抢跑风险；等价于「手动强制跑一轮」）。仅手动 dispatch 带 force_run 时生效。
    if os.environ.get("V8_FORCE_RUN") == "1":
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
    if h < _NEXT_DAY_CUTOFF_HOUR:                  # 00:00 ~ 05:59 凌晨补跑
        return True
    return False                                   # 06:00 ~ 17:59 盘前/盘中


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


def _run_mode():
    """返回本轮运行模式：
    official   交易日 + 盘后窗口(18:00-23:59 / 00:00-05:59) → 全量采集+计算+推送（官方刷新，日期=今天）
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
_FINAL_RECOMMEND_DATA_INPUTS = {
    "FOUR_VOLUME_60M.js": ("strategy_four_volume_60m.py", False),
    "FOUR_VOLUME.js":      ("strategy_four_volume.py", False),
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

def _final_recommend_gate(run_start):
    """final_recommend 前的就绪门控。返回 True=可继续；False=应跳过本轮最终推荐。
    🛡 2026-08-26 补全：校验 raw_data/*.json 核心选股输入（硬，缺失/陈旧则拒绝产出，遵守「不得造假」）。
    🛡 2026-08-31 一劳永逸：四量终极（FOUR_VOLUME_60M/FOUR_VOLUME）降级为软告警——
        其本身为「加分因子，独立于日线版」，final_recommend.py 已做「60m 非今日→回退日线版」
        降级（见 final_recommend.py L289-302）。baostock 60min 源常滞后（曾陈旧到 8/22），
        列硬门控会反复阻断整轮最终推荐，反而让站点长期展示更旧的 FINAL_RECOMMEND（违背「不得造假」本意）。
        故：核心选股输入硬门控，四量软告警；四量陈旧的告警仍打印，但 final_recommend 照常产出。"""
    print(f"\n  🚦 final_recommend 就绪门控（核心选股输入硬门控 + 四量终极为加分因子软告警）")
    # (1) 先把本轮 out/ 产物搬运到 raw_data/，使 out-依赖输入新鲜
    _stage_out_to_raw()
    # 核心选股输入：硬门控（缺失/陈旧且重跑仍失败 → 拒绝产出）
    ok_raw, bad_raw = _gate_ensure_inputs(_FINAL_RECOMMEND_INPUTS, os.path.join(V8_ROOT, "raw_data"), run_start)
    # 四量终极：软告警（脚本自带回退，陈旧不阻断整轮）
    _, bad_data = _gate_ensure_inputs(_FINAL_RECOMMEND_DATA_INPUTS, os.path.join(V8_ROOT, "data"), run_start, soft=True)
    if ok_raw:
        if bad_data:
            print(f"  ⚠️ 四量输入陈旧(软告警，final_recommend 将回退日线版，不阻断): {', '.join(bad_data)}")
        print(f"  ✅ 核心选股输入均为本轮新鲜产出，放行 final_recommend（四量终极为加分因子，陈旧仅告警）")
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
        # 静默杀：已起跑超过启动宽限期(30s) 且 连续无输出 ≥ SILENCE_KILL_SEC
        if elapsed > 30 and silent >= SILENCE_KILL_SEC:
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


def step_run(order=None):
    if order is None:
        order = ORDER
    print(f"\n[1] 运行算法链（{len(order)} 个）")
    # 记录本轮启动时间，供 final_recommend 门控判断「输入是否本轮新鲜产出」
    run_start = datetime.now()
    # 🔴 盘后选股策略统一门控：18:00 前跳过所有选股脚本
    picking_ready = _is_post_close_picking_ready()
    mode = _run_mode()
    is_td = _is_trading_day_now()
    if mode == "backfill":
        os.environ["V8_REF_DATE"] = _last_trading_day()  # 回填：日期改写上一交易日
    skip_fetch = (mode == "backfill")  # 非交易日无新实时数据，跳过 fetch_* 采集脚本（计算照常跑）
    print(f"  🕐 当前时间 {datetime.now():%H:%M} | 盘后选股就绪 {'✅' if picking_ready else '⏳'}"
          f" | 模式={mode}{' | 回填:跳过实时采集+日期改写上一交易日' if skip_fetch else ''}")
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
        # 🛡 2026-09-04：按脚本注入环境变量（SCRIPT_ENV，如 E 回测批让 strategy_four_volume 跑回测模式）
        for _ek, _ev in SCRIPT_ENV.get(script, {}).items():
            os.environ[_ek] = _ev
        _to = _script_timeout(script)
        try:
            rc, last_lines, killed_reason = _supervised_run(script, path, _to)
        except Exception as e:
            fail += 1
            print(f"     ❌ 监督执行异常: {e}")
            FAILED_SCRIPTS.append((script, f"监督执行异常 {e}"))
            continue
        if killed_reason == "silence":
            fail += 1
            print(f"     💀 静默卡死(>{SILENCE_KILL_SEC//60}min 无输出)，监督器已终止并续跑下一脚本")
            FAILED_SCRIPTS.append((script, f"监督器静默杀(>{SILENCE_KILL_SEC//60}min 无输出)"))
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
    manifest = ""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "raw_data/", "data/"],
                             cwd=V8_ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        manifest = ",".join(ln.split(None, 1)[1] for ln in out.stdout.splitlines() if ln.strip())
    except Exception as e:
        print(f"  ⚠️ 收集变更清单失败，回退全量推送: {e}")
    if manifest:
        print(f"  📋 本次变更清单: {manifest[:200]}{'...' if len(manifest) > 200 else ''}")
        env = dict(os.environ)
        env["PUSH_FILES"] = manifest
        r = subprocess.run([PY, "api_push_raw.py"], cwd=V8_ROOT, env=env)
    else:
        print("  ℹ️ 本次无 raw_data/data 变更，跳过推送")
        return
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
    """生成龙虎榜 7 日累计数据（机游共振 + 北向席位），输出 raw_data/lhb_7d.json + data/LHB_7D.js。
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
    if stage in (None, "D"):
        # 🔴 盘后选股策略门控：LHB 7日累计属于选股向汇总，未到 18:00 不处理当日龙虎榜数据
        if _is_post_close_picking_ready() and _is_trading_day_now():
            step_append_lhb_history()
            step_gen_lhb_7d()
            step_build_pool_tracker()
        else:
            print("\n[2.5-2.7] ⏭️ 跳过 LHB 历史累积 + LHB 7日累计 + v8 选股生命周期（非交易日或盘后策略未就绪）")
    else:
        print(f"\n[2.5-2.7] ⏭️ 跳过 LHB 历史累积 + 生命周期前置（stage={stage}，交由 D 汇总批执行）")
    step_run(order=order)
    n = step_stage()
    step_push()
    print(f"\n=== 完成。staged {n} 个文件 ===")


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令·一劳永逸：算法编排器仅允许云端算法链定时任务执行
    #   （v8_algo_cloud 19:15 等）；本地禁止手动跑算法产数据，避免与主站分叉。
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/run_algorithms.py"):
        sys.exit(2)
    main()
