#!/usr/bin/env python3
"""
v8 自愈监控闭环（self_heal_monitor.py）

设计目标：不再依赖用户发现和催促。
每 10-20 分钟自动运行，检测以下异常并自动修复：

  P0-1: candidate.json 丢失「观澜台」源 → 自动拉取观澜台数据并入 + push
  P0-2: STOCK_MOMENTUM_STATE.js 陈旧 >1 个交易日 → 告警（需 PDF OCR）
  P1-1: zsxq_token 缺失/失效 → 告警（需用户补 token）

退出码：
  0 = 一切正常（无需动作）
  1 = 已执行自愈修复
  2 = 发现问题但无法自动修复（需人工介入）

用法：
  python self_heal_monitor.py              # 检查 + 自动修复
  python self_heal_monitor.py --check-only # 仅检查，不执行修复
  python self_heal_monitor.py --json       # JSON 输出（供自动化消费）
"""

import json
import os
import re
import sys
import subprocess
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

# ── 配置 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_data"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
ALGO_DIR = ROOT / "algorithms"

CST = timezone(timedelta(hours=8))
PYTHON = "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 观澜台 token 文件
ZSXQ_TOKEN_FILE = ROOT / "data" / "zsxq_token.json"

# 关键数据文件
CANDIDATE_FILE = RAW_DIR / "candidate.json"
MOMENTUM_FILE = DATA_DIR / "STOCK_MOMENTUM_STATE.js"
GUANLAN_WATCHLIST = OUT_DIR / "guanlan_watchlist.json"

# STOCK_MOMENTUM_STATE 最大允许陈旧天数
MOMENTUM_MAX_STALE_DAYS = 1


def now_cst():
    return datetime.now(CST)


def log(msg, level="INFO"):
    ts = now_cst().strftime("%H:%M:%S")
    print("[" + ts + "] [" + level + "] " + msg)


# ── P0-1: candidate.json 观澜台源检查 ─────────────────

def check_candidate_guanlan():
    if not CANDIDATE_FILE.exists():
        return False, {}, 0, "FILE_MISSING"
    try:
        d = json.load(open(CANDIDATE_FILE, encoding="utf-8"))
        sd = d.get("source_dist") or {}
        has = "观澜台" in sd
        total = d.get("total", 0)
        return has, sd, total, "sources=" + str(list(sd.keys())) + ", total=" + str(total)
    except Exception as e:
        return False, {}, 0, "PARSE_ERROR: " + str(e)


def heal_candidate_guanlan(dry_run=False):
    # 1. 检查 token
    if not ZSXQ_TOKEN_FILE.exists():
        return False, "zsxq_token.json 不存在，无法拉取观澜台数据。需用户提供 token。"
    # 2. 检查/生成 watchlist
    if not GUANLAN_WATCHLIST.exists():
        log("观澜台 watchlist 不存在，先运行 guanlan_extractor.py...", "RUN")
        r = subprocess.run(
            [PYTHON, str(ALGO_DIR / "guanlan_extractor.py")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120
        )
        if r.returncode != 0:
            return False, "guanlan_extractor 失败(rc=" + str(r.returncode) + "): " + r.stderr[-200:]
        log("guanlan_extractor 成功: " + r.stdout[:100], "OK")
    if not GUANLAN_WATCHLIST.exists():
        return False, "guanlan_extractor 跑完但 watchlist 仍不存在"
    try:
        gw = json.load(open(GUANLAN_WATCHLIST, encoding="utf-8"))
        gw_updated = gw.get("updated", "")
        gw_total = gw.get("total", 0)
        log("watchlist: updated=" + str(gw_updated) + ", total_stocks=" + str(gw_total), "INFO")
    except Exception as e:
        return False, "watchlist 解析失败: " + str(e)
    if dry_run:
        return True, "[DRY_RUN] 将并入观澜台数据并 push"
    # 3. 执行合并
    log("开始增量并入观澜台到 candidate.json...", "RUN")
    merge_result = _merge_guanlan_to_candidate()
    if not merge_result["success"]:
        return False, merge_result["message"]
    # 4. git push
    push_result = _push_candidate(merge_result)
    return push_result["success"], push_result["message"]


def _merge_guanlan_to_candidate():
    sys.path.insert(0, str(ALGO_DIR))
    try:
        from build_candidate_pool import _norm
    except ImportError as e:
        return {"success": False, "message": "无法导入 _norm: " + str(e)}
    try:
        pool = json.load(open(CANDIDATE_FILE, encoding="utf-8"))
        gw = json.load(open(GUANLAN_WATCHLIST, encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": "文件读取失败: " + str(e)}

    stocks = pool["stocks"]
    gw_stocks = gw.get("stocks", [])
    if isinstance(gw_stocks, dict):
        gw_stocks = list(gw_stocks.values())

    added = 0
    for s in gw_stocks:
        code_raw = str(s.get("code", "")).strip()
        name = s.get("name", "")
        market_raw = s.get("market", "")
        full_code = s.get("full_code", "")
        result = _norm(code_raw, name, market_raw, full_code)
        if result is None:
            continue
        padded_code, clean_name, mkt_key, board = result
        key = mkt_key + "_" + padded_code
        if key not in stocks:
            stocks[key] = {
                "name": clean_name or name,
                "code": padded_code,
                "market": market_raw,
                "sources": ["观澜台"],
                "first_seen": s.get("added_date", ""),
            }
            added += 1
        else:
            if "观澜台" not in stocks[key].get("sources", []):
                stocks[key]["sources"].append("观澜台")

    sd = Counter()
    for v in stocks.values():
        for src in v.get("sources", []):
            sd[src] += 1
    pool["source_dist"] = dict(sd)
    pool["total"] = len(stocks)
    pool["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(CANDIDATE_FILE, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"success": False, "message": "写入失败: " + str(e)}

    return {
        "success": True,
        "message": "并入完成: +" + str(added) + "新, 总计" + str(len(stocks)) + "只",
        "stats": {"total": len(stocks), "added": added, "source_dist": dict(sd)},
    }


def _push_candidate(merge_result):
    stats = merge_result.get("stats", {})
    added_val = stats.get("added", 0)
    msg = "fix(candidate): 自愈并入观澜台(+" + str(added_val) + ") [self_heal_monitor]"
    try:
        # 先检查是否有未解决的冲突
        check_r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=15
        )
        if "UU" in check_r.stdout or "AA" in check_r.stdout or "DU" in check_r.stdout:
            log("检测到未解决冲突，先 abort rebase...", "WARN")
            subprocess.run(["git", "rebase", "--abort"], capture_output=True, timeout=15, cwd=str(ROOT))
            # 重新合并（因为 abort 会丢弃工作区改动）
            retry_merge = _merge_guanlan_to_candidate()
            if not retry_merge["success"]:
                return {"success": False, "message": "冲突abort后重合并失败: " + retry_merge["message"]}
            merge_result = retry_merge

        # 同步远端
        pull_r = subprocess.run(
            ["git", "pull", "--rebase", "--autostash", "origin", "main"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60
        )
        # 检查 rebase 后是否有冲突
        status_r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=15
        )
        if "UU" in status_r.stdout or "AA" in status_r.stdout:
            log("rebase 后出现冲突，自动解决...", "WARN")
            # 对冲突文件取 --theirs（远端版本），只保留 candidate.json 的本地改动
            for line in status_r.stdout.strip().splitlines():
                fpath = line[3:] if len(line) > 3 else ""
                if line.startswith("UU") and "candidate" not in fpath:
                    subprocess.run(["git", "checkout", "--theirs", fpath],
                                   capture_output=True, timeout=10, cwd=str(ROOT))
                    subprocess.run(["git", "add", fpath],
                                   capture_output=True, timeout=10, cwd=str(ROOT))
            # 重新检查 candidate 是否被覆盖
            d = json.load(open(CANDIDATE_FILE, encoding="utf-8"))
            if "观澜台" not in (d.get("source_dist") or {}):
                log("rebase 冲突导致观澜台被覆盖，重新并入...", "WARN")
                retry2 = _merge_guanlan_to_candidate()
                if not retry2["success"]:
                    return {"success": False, "message": "冲突后重合并失败: " + retry2["message"]}
                subprocess.run(["git", "add", str(CANDIDATE_FILE)],
                               capture_output=True, timeout=10, cwd=str(ROOT))

        r = subprocess.run(
            ["git", "add", str(CANDIDATE_FILE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        r = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            return {"success": False, "message": "commit 失败: " + r.stderr[-200:]}
        r = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60
            )
            r2 = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60
            )
            if r2.returncode != 0:
                return {"success": False, "message": "push 失败(含重试): " + r2.stderr[-200:]}
        return {"success": True, "message": "已推送: " + merge_result["message"]}
    except subprocess.TimeoutExpired as e:
        return {"success": False, "message": "git 操作超时: " + str(e)}
    except Exception as e:
        return {"success": False, "message": "git 异常: " + str(e)}


# ── P0-2: STOCK_MOMENTUM_STATE.js 新鲜度 ────────────────

def check_momentum_state():
    if not MOMENTUM_FILE.exists():
        return False, None, 999, "FILE_MISSING"
    try:
        src = open(MOMENTUM_FILE, encoding="utf-8").read()
        # 兼容单/双引号：优先 meta.generated（文件生成时间），
        # 其次取 days 中最大 date（历史窗口最新日），两者取最新。
        candidates = []
        mg = re.search(r"['\"]generated['\"]\s*:\s*['\"](\d{4}-\d{2}-\d{2})", src)
        if mg:
            candidates.append(mg.group(1))
        md = re.findall(r"['\"]date['\"]\s*:\s*['\"](\d{4}-\d{2}-\d{2})['\"]", src)
        if md:
            candidates.append(max(md))
        if not candidates:
            return False, None, 999, "无法解析日期"
        last_day = max(candidates)
        last_dt = datetime.strptime(last_day, "%Y-%m-%d").replace(tzinfo=CST)
        age_days = (now_cst().date() - last_dt.date()).days
        is_fresh = age_days <= MOMENTUM_MAX_STALE_DAYS
        return is_fresh, last_day, age_days, "last_day=" + last_day + ", age=" + str(age_days) + "d"
    except Exception as e:
        return False, None, 999, "解析错误: " + str(e)


# ── P1-1: zsxq_token 检查 ───────────────────────────────

def check_zsxq_token():
    if not ZSXQ_TOKEN_FILE.exists():
        return False, "TOKEN_FILE_MISSING"
    try:
        d = json.load(open(ZSXQ_TOKEN_FILE, encoding="utf-8"))
        token = d.get("token", "")
        if not token or len(token) < 10:
            return False, "TOKEN_INVALID_FORMAT"
        return True, "OK (len=" + str(len(token)) + ")"
    except Exception as e:
        return False, "TOKEN_PARSE_ERROR: " + str(e)


# ── 主流程 ──────────────────────────────────────────────

def run_check_only():
    results = {}
    has, sd, total, det = check_candidate_guanlan()
    results["candidate_guanlan"] = {"ok": has, "detail": det, "source_dist": sd, "total": total}
    icon = "OK" if has else "FAIL"
    log("[" + icon + "] candidate.json 观澜台: " + det)

    fresh, last_day, age, det2 = check_momentum_state()
    results["momentum_state"] = {"ok": fresh, "detail": det2, "last_day": last_day, "age_days": age}
    icon = "OK" if fresh else "FAIL"
    log("[" + icon + "] STOCK_MOMENTUM_STATE.js: " + det2)

    tok_ok, tok_det = check_zsxq_token()
    results["zsxq_token"] = {"ok": tok_ok, "detail": tok_det}
    icon = "OK" if tok_ok else "FAIL"
    log("[" + icon + "] zsxq_token: " + tok_det)

    all_ok = all(r["ok"] for r in results.values())
    if all_ok:
        log("=== 全部正常 ===", "PASS")
        return 0
    issues = [k for k, v in results.items() if not v["ok"]]
    log("=== 发现问题: " + ", ".join(issues) + " ===", "FAIL")
    return 2


def run_heal(json_output=False):
    actions_taken = []
    heal_results = {}
    exit_code = 0

    # P0-1
    has, sd, total, det = check_candidate_guanlan()
    if not has:
        log("[FAIL] P0-1: candidate.json 缺失观澜台源! " + det, "FAIL")
        success, msg = heal_candidate_guanlan()
        heal_results["candidate_guanlan"] = {"ok": success, "message": msg}
        if success:
            log("[HEAL] P0-1 已自愈: " + msg, "HEAL")
            actions_taken.append("并入观澜台: " + msg)
        else:
            log("[FAIL] P0-1 无法自愈: " + msg, "FAIL")
            exit_code = 2
    else:
        guanlan_count = sd.get("观澜台", 0)
        log("[OK] P0-1: candidate.json 含观澜台(" + str(guanlan_count) + "只)", "OK")
        heal_results["candidate_guanlan"] = {"ok": True, "message": det}

    # P0-2
    fresh, last_day, age, det2 = check_momentum_state()
    if not fresh:
        log("[FAIL] P0-2: STOCK_MOMENTUM_STATE.js 陈旧! " + det2, "FAIL")
        heal_results["momentum_state"] = {
            "ok": False,
            "message": "最后交易日=" + str(last_day) + ", 陈旧" + str(age) + "天, 需要当日盘后选股 PDF 做 OCR 抽取",
        }
        actions_taken.append("MOMENTUM_STATE 陈旧(" + str(last_day) + ", " + str(age) + "天): 需 PDF OCR")
        exit_code = max(exit_code, 2)
    else:
        log("[OK] P0-2: STOCK_MOMENTUM_STATE.js 新鲜 (" + det2 + ")", "OK")
        heal_results["momentum_state"] = {"ok": True, "message": det2}

    # P1-1
    tok_ok, tok_det = check_zsxq_token()
    if not tok_ok:
        log("[WARN] P1-1: zsxq_token 异常! " + tok_det, "WARN")
        heal_results["zsxq_token"] = {"ok": False, "message": tok_det}
        actions_taken.append("zsxq_token: " + tok_det)
        exit_code = max(exit_code, 2)
    else:
        log("[OK] P1-1: zsxq_token 正常 (" + tok_det + ")", "OK")
        heal_results["zsxq_token"] = {"ok": True, "message": tok_det}

    if json_output:
        print(json.dumps({
            "timestamp": now_cst().isoformat(),
            "exit_code": exit_code,
            "actions_taken": actions_taken,
            "checks": heal_results,
        }, ensure_ascii=False, indent=2))
    elif actions_taken:
        log("=== 自愈完成: " + str(len(actions_taken)) + "项动作 ===", "SUMMARY")
        for a in actions_taken:
            log("  -> " + a, "ACTION")
    else:
        log("=== 全部正常，无需动作 ===", "PASS")

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="v8 自愈监控闭环")
    parser.add_argument("--check-only", action="store_true", help="仅检查不修复")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()
    if args.check_only:
        rc = run_check_only()
    else:
        rc = run_heal(json_output=args.json)
    sys.exit(rc)


if __name__ == "__main__":
    main()
