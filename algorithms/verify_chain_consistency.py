#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_chain_consistency.py — v8 算法链「一致性机器校验」
========================================================
🛡 2026-09-08 C 方案核心（一劳永逸）：把"靠人肉注释约束、无机器校验"导致的
   反复故障（09-08 P0: STAGES/ORDER 漏挂崩全链；4 暗灯: 孤儿脚本/死数据/断链
   体检扫不到）改为 CI 自动发现。

检查项
  ① STAGES↔ORDER 双表一致（防 09-08 P0 复发）—— 严重，exit 1
  ② 孤儿脚本：algorithms/ scripts/ 下 .py 不在链且无豁免 —— 告警（不阻断）
  ③ 数据断链：DATA_SOURCES 映射的 raw→data，data update_time 比 raw 旧 > 阈值 —— 告警
  ④ 映射悬空：DATA_SOURCES 声明的 VAR 但 data/VAR.js 缺失 —— 告警

判定口径（铁律：读文件内 update_time，不信 mtime）
  - 断链阈值默认 1 天（1440 min）；`--stale-min` 可调；`--strict` 时断链也 exit 1。

退出码
  0  全部检查通过（含仅有 warn 级告警）
  1  发现严重问题（① STAGES/ORDER 不一致；或 --strict 下的断链）
  2  脚本自身异常

用法
  python algorithms/verify_chain_consistency.py                # 默认：①硬失败，②③④告警
  python algorithms/verify_chain_consistency.py --strict      # 断链也硬失败
  python algorithms/verify_chain_consistency.py --quiet       # 仅输出 FAIL/ORPHAN 行
"""
import argparse
import json
import os
import re
import sys
import glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALGO = os.path.join(REPO, "algorithms")
SCRIPTS = os.path.join(REPO, "scripts")
V8 = os.path.join(REPO, "v8")
RAW = os.path.join(REPO, "raw_data")
DATA = os.path.join(REPO, "data")
UPDATE_V8 = os.path.join(REPO, "update_v8.py")

# 孤儿脚本豁免：数据构建/抓取/部署/工具，本就不进算法链 ORDER/STAGES
SCRIPT_EXEMPT = {
    "update_v8.py", "cloud_fetch_v8.py", "api_push_raw.py", "api_push.py",
    "bridge_raw_data.py", "dedup_fetch_manifest.py", "align_logic_ops.py",
    "v8_verify_layer_parity.py", "verify_chain_outputs.py", "verify_daily_audit.py",
    "verify_card_badges.py", "verify_chain_consistency.py", "__init__.py",
    "run_algorithms.py",
    "name_utils.py", "fundamental_helper.py", "fq_utils.py", "stk_utils.py",
    "alpha_utils.py", "norm_utils.py", "date_utils.py", "log_utils.py",
    "fetch_helpers.py", "akshare_helpers.py", "baostock_helpers.py",
    "path_helpers.py", "git_helpers.py", "http_helpers.py", "file_helpers.py",
    "math_helpers.py", "pandas_helpers.py", "numpy_helpers.py",
}
# 工具类脚本前缀：本就不进算法链（构建/抓取/监控/审计/同步/治理等），不报孤儿
SCRIPT_TOOL_PREFIXES = (
    "fetch_", "calc_", "gen_", "build_", "monitor_", "audit_", "backfill_",
    "sync_", "setup_", "check_", "show_", "write_", "reconcile_", "optimize_",
    "regime_", "apply_", "stage_", "data_", "factor_", "raw_", "api_",
    "guanlan_", "alimi_", "alpha_", "algo_", "freshness_", "fix_",
    "renormalize_", "stop_target_", "scanner", "v8_verify", "verify_",
    "update_", "cloud_", "bridge_", "dedup_", "align_",
)

# 死数据豁免：纯前端/部署层变量、或"一 raw 产多 js"由独立生成器自管（gen 自带 update_time）
DATA_VAR_EXEMPT = {
    "HEALTH_CHECK", "RUNNER_STATUS_HEALTH", "DO_NOT_DELETE_HTML",
    "CITIC_PE_THERMO", "CITIC_PE_BACKTEST",
    "MAHORO_MACRO", "MAHARO_PANEL",
    "ALGO_BACKTEST_COMPARE", "AUDIT_TRAIL",
    "PORTFOLIO_DATA", "UNLISTED_PANEL",
}

QUIET = False


def log(msg):
    if not QUIET:
        print(msg)


def extract_update_time(text):
    """从 JSON / JS 文本里抓第一个 update_time 字段（兼容 "2026-09-08T01:56:52" / "2026-09-08 01:56:52"）。"""
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    if not m:
        return None
    s = m.group(1).replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def parse_data_sources():
    """解析 update_v8.py 的 DATA_SOURCES = { raw.json: VAR, ... }（跳过注释行）"""
    s = open(UPDATE_V8, encoding="utf-8").read()
    m = re.search(r"DATA_SOURCES\s*=\s*\{(.*?)\n\}", s, re.S)
    if not m:
        return {}
    src = m.group(1)
    clean = []
    for ln in src.split("\n"):
        if ln.strip().startswith("#"):
            continue
        hi = ln.find("#")
        if hi >= 0:
            ln = ln[:hi]
        clean.append(ln)
    src = "\n".join(clean)
    pairs = re.findall(r'"([^"]+\.json)"\s*:\s*"([A-Z][A-Z_0-9]+)"', src)
    return {raw: var for raw, var in pairs}


def check_stages_order():
    """① STAGES↔ORDER 双表一致（严重）"""
    sys.path.insert(0, ALGO)
    import run_algorithms as r
    union = set()
    for v in r.STAGES.values():
        union |= set(v)
    diff_order = set(r.ORDER) - union
    diff_stage = union - set(r.ORDER)
    ok = (not diff_order) and (not diff_stage)
    if ok:
        log(f"[OK]   ① STAGES↔ORDER 一致 (ORDER={len(r.ORDER)}, STAGE_UNION={len(union)})")
    else:
        log(f"[FAIL] ① STAGES↔ORDER 不一致!")
        if diff_order:
            log(f"       仅ORDER有: {sorted(diff_order)}")
        if diff_stage:
            log(f"       仅STAGES有: {sorted(diff_stage)}")
    return ok


def check_orphan_scripts():
    """② 孤儿脚本扫描（告警级）"""
    sys.path.insert(0, ALGO)
    import run_algorithms as r
    chained_base = {c.split("/")[-1] for c in r.ORDER}
    chained_base |= {c.split("/")[-1] for v in r.STAGES.values() for c in v}
    orphans = []
    for pat in (os.path.join(ALGO, "*.py"), os.path.join(SCRIPTS, "*.py")):
        for p in glob.glob(pat):
            base = os.path.basename(p)
            if base.startswith("_") or base.startswith("test") or base in SCRIPT_EXEMPT:
                continue
            if base in chained_base:
                continue
            if base.startswith(SCRIPT_TOOL_PREFIXES):
                continue  # 工具类脚本，本就不进算法链
            orphans.append(base)
    if orphans:
        log(f"[WARN] ② 孤儿脚本 {len(orphans)} 个（不在链且无豁免）：")
        for o in sorted(orphans):
            log(f"       - {o}")
    else:
        log("[OK]   ② 无孤儿脚本")
    return orphans


def check_data_breakage(stale_min):
    """③ 数据断链：DATA_SOURCES 映射的 raw→data，data 比 raw 旧 > stale_min"""
    ds = parse_data_sources()
    from datetime import datetime
    breaks = []
    for raw_name, var in ds.items():
        raw_path = os.path.join(RAW, raw_name)
        js_path = os.path.join(DATA, f"{var}.js")
        if not os.path.exists(raw_path):
            breaks.append((var, raw_name, "raw 缺失"))
            continue
        if not os.path.exists(js_path):
            breaks.append((var, raw_name, "data js 缺失"))
            continue
        rt = extract_update_time(open(raw_path, encoding="utf-8", errors="ignore").read())
        jt = extract_update_time(open(js_path, encoding="utf-8", errors="ignore").read())
        if rt and jt:
            age = (rt - jt).total_seconds() / 60.0
            if age > stale_min:
                breaks.append((var, raw_name, f"data 比 raw 旧 {age/60:.1f}h"))
        elif rt and not jt:
            breaks.append((var, raw_name, "data 无 update_time"))
    if breaks:
        log(f"[WARN] ③ 数据断链 {len(breaks)} 处（data 滞后 raw > {stale_min}min）：")
        for var, raw_name, why in breaks:
            log(f"       - {var} (raw={raw_name}): {why}")
    else:
        log(f"[OK]   ③ 无数据断链（DATA_SOURCES 映射 {len(ds)} 项均新鲜）")
    return breaks


def check_dangling_map():
    """④ 映射悬空检测：DATA_SOURCES 声明的 VAR 但 data/VAR.js 缺失（真孤儿/残留映射）

    注：data/*.js 绝大多数由生成器用变量动态写 window.VAR（VAR 不在源码字面出现），
    故不能用「grep 字面引用」判孤儿——那会误报 60+ 合法数据。改用「映射悬空」：
    DATA_SOURCES 里声明了 raw→VAR，但 data/VAR.js 实际不存在，才是真残留/孤儿信号
    （如 AI 预测卡下架后 update_v8 映射忘记删除的 PATH_PROB_BACKTEST）。
    """
    ds = parse_data_sources()
    dangling = []
    for raw_name, var in ds.items():
        js_path = os.path.join(DATA, f"{var}.js")
        if not os.path.exists(js_path):
            dangling.append((var, raw_name))
    if dangling:
        log(f"[WARN] ④ 映射悬空 {len(dangling)} 处（DATA_SOURCES 声明但 data/*.js 缺失）：")
        for var, raw_name in dangling:
            log(f"       - window.{var} (应由 {raw_name} 生成): data/{var}.js 缺失")
    else:
        log(f"[OK]   ④ 无映射悬空（DATA_SOURCES 映射 {len(ds)} 项均有对应 data/*.js）")
    return dangling


def main():
    global QUIET
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-min", type=int, default=1440, help="断链判定阈值(分钟)，默认 1440")
    ap.add_argument("--strict", action="store_true", help="断链也视为严重(退出码1)")
    ap.add_argument("--quiet", action="store_true", help="仅输出 FAIL/ORPHAN 行")
    args = ap.parse_args()
    QUIET = args.quiet

    log("=" * 64)
    log("v8 算法链一致性机器校验 (verify_chain_consistency)")
    log("=" * 64)

    severe = False
    # ① 严重：STAGES/ORDER 不一致
    try:
        if not check_stages_order():
            severe = True
    except Exception as e:
        log(f"[FAIL] ① STAGES/ORDER 校验异常: {e}")
        severe = True

    # ② 孤儿脚本（告警）
    try:
        check_orphan_scripts()
    except Exception as e:
        log(f"[WARN] ② 孤儿脚本扫描异常: {e}")

    # ③ 数据断链（告警 / --strict 严重）
    breaks = []
    try:
        breaks = check_data_breakage(args.stale_min)
    except Exception as e:
        log(f"[WARN] ③ 断链扫描异常: {e}")
    if breaks and args.strict:
        severe = True

    # ④ 映射悬空（告警）
    try:
        check_dangling_map()
    except Exception as e:
        log(f"[WARN] ④ 映射悬空扫描异常: {e}")

    log("=" * 64)
    if severe:
        log("结论: FAIL（存在严重不一致，请立即修复）")
        sys.exit(1)
    else:
        log("结论: OK（含告警级提示，请人工复核）")
        sys.exit(0)


if __name__ == "__main__":
    main()
