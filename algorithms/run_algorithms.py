#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_algorithms.py — v8 本地/自托管 cn runner 的盘后算法编排器

流程：
  0) 重灌 v6 仍负责产出的「上游输入」到 algorithms/out/（gold_pool / scan_result /
     guanlan_* / mahoro_signals）。这部分在 1 周过渡期内仍由 v6 供给，之后由
     v8 原生抓取器取代。
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
OUT = os.path.join(ALGO, "out")

V6_DATA_DIR = os.environ.get("V6_DATA_DIR", r"E:\workspace\stock-scanner\data")
PY = os.environ.get("V8_PYTHON", "python")

# 本地测试可能传入 Git-Bash 风格路径（/c/Users/...），Windows CreateProcess 无法解析，
# 统一转成原生 Windows 路径（C:/...）。生产 runner 用原生 python，不受影响。
if PY.startswith("/") and len(PY) > 2 and PY[2] == "/":
    PY = re.sub(r"^/([a-zA-Z])/", lambda m: m.group(1).upper() + ":/", PY)

PUSH = os.environ.get("V8_PUSH", "0") == "1"

# 过渡期仍由 v6 供给的上游输入（v6 文件名）
INPUTS_FROM_V6 = [
    "gold_pool.json",
    "scan_result.json",
    "guanlan_watchlist.json",
    "guanlan_reports.json",
    "maharo_signals.json",
]

# 依赖顺序：先抓基础数据 → 回测/候选 → 顶层共识/分级
ORDER = [
    "fetch_fundamental_quality.py",   # → fundamental_quality（输入给 top10/triple*）
    "fetch_stock_names.py",
    "fetch_sh_index_fib.py",
    "fetch_inst_trade.py",
    "fetch_sector_rs.py",
    "fetch_lhb.py",
    "calc_crds.py",
    "build_candidate_pool.py",         # 读 guanlan/maharo 输入
    "backtest_tdx.py",                 # 读 gold_pool 输入
    "backtest_comprehensive.py",
    "cockpit_backtest_now.py",
    "generate_top10.py",               # 读 fundamental_quality / gold_pool
    "gen_cockpit_tier_recommend.py",   # 读 scan_result 输入
    "gen_cockpit_advice.py",           # 读 backtest_tdx
    "update_triple_resonance_history.py",  # 累积 triple_resonance_history
    "gen_triple_consensus.py",         # 读 top10 / cockpit_tier / fundamental / gold_pool
    "gen_triple_track.py",             # 读 triple_history / gold_pool / backtest / cockpit
]


def step_seed_inputs():
    print(f"\n[0] 重灌 v6 上游输入 → out/  (V6={V6_DATA_DIR})")
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


def main():
    print(f"=== v8 算法编排  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    step_seed_inputs()
    step_run()
    n = step_stage()
    step_push()
    print(f"\n=== 完成。staged {n} 个文件 ===")


if __name__ == "__main__":
    main()
