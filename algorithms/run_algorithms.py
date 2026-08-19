#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_algorithms.py — v8 本地/自托管 cn runner 的盘后算法编排器

流程：
  0) v8 原生化自产「上游输入」到 仓库根/out/（gold_pool / scan_result / watch_result /
     guanlan_* / mahoro_signals），由 scanner.py / guanlan_extractor.py /
     fetch_maharo_signals.py 经 V8_OUT_DIR 钩子产出，彻底脱离 v6。
     （设 V6_SEED=1 可强制回退到 v6 重灌，仅用于应急。）
  1) 按依赖顺序运行 v8/algorithms/ 下的算法脚本（各自写 out/，沿用 v6 文件名）。
  2) stage_to_raw：按 V6_TO_V8 重命名为 raw_data/（v8 命名）+ 注入 update_time。
  3) 若 V8_PUSH=1：调用 api_push_raw.py 经 API 推送 raw_data 到 main。

每个脚本失败不影响其余（continue-on-error），与云端 fetch 行为一致。
"""
import os
import re
import subprocess
import sys
from datetime import datetime

ALGO = os.path.dirname(os.path.abspath(__file__))
V8_ROOT = os.path.dirname(ALGO)
# ⚠️ out 目录必须与被迁移脚本的 os.path.join(BASE, "..", "out") 口径一致：
#   脚本 BASE = algorithms/，故 BASE/../out = 仓库根/out（不是 algorithms/out）。
#   原来这里写 ALGO/out 与脚本对不上 → reseed 灌到 algorithms/out 而脚本读仓库根/out → 全链找不到输入。
OUT = os.path.join(V8_ROOT, "out")
# 🔴 2026-08-06 修复：历史快照目录从 out/history（gitignore，云端丢）→ raw_data/history（git 跟踪 + api_push 持久化）。
#   否则 backtest_tdx / backtest_comprehensive / cockpit_backtest_now 依赖的历史 top10/gold_pool 快照每次跑完丢失，
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
    "fetch_stock_quote_v8.py",         # → raw_data/stock_quote.json + data/STOCK_QUOTE.js（全市场实时报价快照，查股功能用）
    "fetch_sh_index_fib.py",
    "fetch_inst_trade.py",
    "fetch_sector_rs.py",
    "fetch_lhb.py",
    "calc_crds.py",
    "build_candidate_pool.py",         # 读 guanlan/maharo 输入 → gold_pool / candidate_pool
    "calc_stock_rps.py",               # → data/STOCK_RPS.js（个股RPS+RS，读 candidate.json 做 universe）
    "generate_top10.py",               # 读 fundamental_quality / gold_pool → raw_data/top10_daily.json + raw_data/history/top10_daily_YYYYMMDD.json
    "backtest_tdx.py",                 # 读 gold_pool 输入
    "backtest_comprehensive.py",       # 读 raw_data/history/top10_daily_YYYYMMDD.json（必须在 generate_top10 之后）
    "cockpit_backtest_now.py",         # 读 raw_data/history/top10_daily_YYYYMMDD.json（必须在 generate_top10 之后）
    "export_optimized_strategy.py",    # → raw_data/optimized_strategy.json（读 backtest_tdx.json 汇总优化策略效果）
    "strategy_four_volume_60m.py",     # → data/FOUR_VOLUME_60M.js（四量终极60min版，baostock独立数据源）
    "gen_cockpit_tier_recommend.py",   # 读 scan_result 输入
    "gen_cockpit_tier_recommend.py",   # 读 scan_result 输入
    "gen_cockpit_advice.py",           # 读 backtest_tdx
    "update_triple_resonance_history.py",  # 累积 triple_resonance_history
    "gen_triple_consensus.py",         # 读 top10 / cockpit_tier / fundamental / gold_pool
    "gen_triple_track.py",             # 读 triple_history / gold_pool / backtest / cockpit
    "calc_volatility_watch.py",         # → raw_data/volatility.json（v8 原生，独立无依赖）
    "gen_stock_stop.py",                # → data/STOCK_STOP_DATA.js（ATR 精确止损止盈，读候选宇宙日K）
    # ── 孤儿模块原生化（2026-08-02）：原靠 v6→v8 sync_legacy 同步，现由 v8 直接产出 ──
    # 这些脚本直接写 raw_data/<name>.json（不经 out/），stage_to_raw 不二次处理，api_push 直接上传。
    "fetch_orphan_suspension.py",       # → raw_data/suspension_alert.json
    "fetch_orphan_market_alerts.py",    # → raw_data/market_alerts.json
    "fetch_orphan_nt_data.py",          # → raw_data/nt_data.json
    "fetch_orphan_sector_fund_flow.py", # → raw_data/sector_fund_flow_trend.json (+ history 累加)
    # ── 最终推荐（2026-08-10 补入：之前缺失导致 FINAL_RECOMMEND_DATA 等永远不刷新）──
    # final_recommend.py 是整条管线的最终汇聚点，必须排在所有上游之后：
    #   输入 = triple_consensus + cockpit_tier + top10_daily + crds + lhb + sector_rs +
    #          crisis_data + cockpit_backtest + triple_track + four_volume_60m + stock_profile
    #   输出 = raw_data/final_recommend.json + data/FINAL_RECOMMEND_DATA.js（Top5 + 全量推荐池）
    "final_recommend.py",              # → FINAL_RECOMMEND_DATA.js（跨策略共振 Top5，管线最终产物）
    "gen_top5_track.py",               # → TOP5_TRACK.js（finalRec Top5 90 天滚动追踪盘，2026-08-13 落地/2026-08-15 改自 TOP3）
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
    "track_h_auto_buy.py",
]


def step_v8_self_sufficiency():
    """2026-08-02 原生化：v8 自产 4 类上游输入（gold_pool / scan_result / watch_result /
    guanlan_* / mahoro_signals），替代 v6 供给。通过 V8_OUT_DIR 环境变量让被迁移脚本
    把数据写到仓库根 out/（而非 algorithms/data）。"""
    print(f"\n[0-pre] v8 原生化自产上游输入 → out/  (V8_OUT_DIR={OUT})")
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ)
    env["V8_OUT_DIR"] = OUT
    jobs = [
        ("scanner.py", 3600),             # 产出 gold_pool / scan_result / watch_result
        ("guanlan_extractor.py", 600),    # 产出 guanlan_reports / guanlan_watchlist
        ("fetch_maharo_signals.py", 300), # 产出 mahoro_signals（cookie 在 v8 data/）
    ]
    for script, timeout in jobs:
        path = os.path.join(ALGO, script)
        if not os.path.exists(path):
            print(f"  ❌ 缺失脚本: {script}")
            continue
        print(f"  ▶ {script}  ({datetime.now():%H:%M:%S})")
        try:
            # ★ 2026-08-04 修复：scanner.py 必须带 full 子命令，否则只打印用法即退出，
            #   永远不写 gold_pool.json → 连锁导致 backtest_tdx/gen_cockpit_advice 失败。
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


def step_run():
    print(f"\n[1] 运行算法链（{len(ORDER)} 个）")
    ok, fail = 0, 0
    for script in ORDER:
        path = os.path.join(ALGO, script)
        if not os.path.exists(path):
            print(f"  ❌ 缺失脚本: {script}")
            fail += 1
            continue
        print(f"  ▶ {script}  ({datetime.now():%H:%M:%S})")
        try:
            r = subprocess.run([PY, path], cwd=ALGO, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0:
                ok += 1
                # 打印末行摘要
                last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
                print(f"     ✅ ok | {last[0][:80]}")
            else:
                fail += 1
                print(f"     ⚠️ 退出码 {r.returncode}")
                tail = "\n".join(r.stdout.strip().splitlines()[-3:] + r.stderr.strip().splitlines()[-3:])
                print("     " + tail.replace("\n", "\n     ")[:400])
        except subprocess.TimeoutExpired:
            fail += 1
            print(f"     ⏱️ 超时(>30min)，跳过")
        except Exception as e:
            fail += 1
            print(f"     ❌ 异常: {e}")
    print(f"  算法运行: 成功 {ok} / 失败 {fail}")


def step_stage():
    print("\n[2] stage_to_raw（重命名 + 注入 update_time）")
    sys.path.insert(0, ALGO)
    import stage_to_raw
    return stage_to_raw.main()


def step_push():
    if not PUSH:
        print("\n[3] 跳过推送（V8_PUSH != 1）")
        return
    print("\n[3] 推送 raw_data → main（api_push_raw）")
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


def main():
    print(f"=== v8 算法编排  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    step_v8_self_sufficiency()  # 2026-08-02 原生化: 先自产 4 类上游输入
    step_seed_inputs()          # 默认 no-op, V6_SEED=1 才重灌
    step_run()
    n = step_stage()
    step_append_lhb_history()
    step_gen_lhb_7d()
    step_push()
    print(f"\n=== 完成。staged {n} 个文件 ===")


if __name__ == "__main__":
    main()
