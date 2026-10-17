#!/usr/bin/env python3
"""
v8 自愈监控闭环（self_heal_monitor.py）

设计目标：不再依赖用户发现和催促。
每 10-20 分钟自动运行，检测以下异常并自动修复：

  P0-1: candidate.json 丢失「外资研投」源 → 自动拉取外资研投数据并入 + push
  P0-2: STOCK_MOMENTUM_STATE.js 新鲜度 → 源=PDF OCR 人工流程（主人盘后选股 PDF → OCR）；陈旧只记 WARN 免邮件，不升级 FAIL（与 v8_health_check.py 方针对齐，禁止某模块特立独行）
  P0-3: MOMENTUM_FILTER.js（动量共识筛选卡源）新鲜度确认：缺失/解析失败=FAIL（真异常）；V2 源比 filter 新=待重算 WARN 留痕（dispatcher 应已派发）；其余=OK。本机不 push（云端 cloud_dispatcher/算法链为修复方）
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
import shutil
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

# 外资研投 token 文件
ZSXQ_TOKEN_FILE = ROOT / "data" / "zsxq_token.json"

# 🔴 2026-09-11 主人令「怎么又异常了？也没人通知我」一劳永逸修复之二：
#   根因：token 只存在【仓库工作区】这一处，而本机并发会话/清理类操作会把工作区内
#   未跟踪的 data/*.json 当成"遗留文件"清掉（git 本身不会删 ignored 文件，
#   删除来自文件系统层直接操作）→ 文件消失且本地零副本，只能人工重补。
#   修复：外置权威副本（仓库之外，~/.workbuddy/ 不被仓库清理波及）。
#   - 仓库缺、外置在 → 自动回填（真自愈，无需人工）；
#   - 仓库在、外置缺 → 自动补写外置副本（双写保护，静默）；
#   - 两处皆无/格式非法 → 真异常，走 v8_send_alert.py 发邮件（状态翻转即发，6h 冷却去重）。
ZSXQ_TOKEN_BACKUP = Path.home() / ".workbuddy" / "v8_zsxq_token.json"
ALERT_STATE_FILE = Path.home() / ".workbuddy" / "v8_selfheal_alert_state.json"
TOKEN_ALERT_COOLDOWN_HOURS = 6

# --check-only 模式下禁止一切副作用（不写盘、不发信），保持只读语义
CHECK_ONLY = False

# 关键数据文件
CANDIDATE_FILE = RAW_DIR / "candidate.json"
MOMENTUM_FILE = DATA_DIR / "STOCK_MOMENTUM_STATE.js"
MOMENTUM_FILTER_FILE = DATA_DIR / "MOMENTUM_FILTER.js"
GUANLAN_WATCHLIST = OUT_DIR / "guanlan_watchlist.json"

# STOCK_MOMENTUM_STATE 最大允许陈旧天数（仅用于计龄与展示，不再作为 FAIL 升级阈值）
# 源为 PDF OCR 人工流程：主人盘后选股 PDF → OCR 后才刷新，自动巡检无法修复。
# 容忍 3 天日历间隔用于展示 age，但陈旧本身只记 WARN、不升级 FAIL（与 v8_health_check.py 对齐）。
MOMENTUM_MAX_STALE_DAYS = 3

# 🔴 2026-10-14 一劳永逸对齐：P0-2 源=PDF OCR 人工流程 → 陈旧只 WARN 免邮件，绝不升级 FAIL。
#   （此前误设为 False 并把陈旧判 FAIL/exit=2，与 v8_health_check.py L2297 的「MOMENTUM→warn」降级口径矛盾，
#    造成每轮 P0-2 陈旧都误报 exit=2。现改回 True，陈旧仅留痕、不阻断。）
MOMENTUM_MANUAL_DEPENDENCY = True

# 保留兼容占位（不再使用）
_MOMENTUM_KNOWN_QUIET_PREFIXES = ("last_day=",)


def now_cst():
    return datetime.now(CST)


def log(msg, level="INFO"):
    ts = now_cst().strftime("%H:%M:%S")
    line = "[" + ts + "] [" + level + "] " + msg
    # --json 模式下 stdout 只留纯净 JSON，日志走 stderr（2026-08-19 修复）
    if getattr(log, "to_stderr", False):
        print(line, file=sys.stderr)
    else:
        print(line)


# ── P0-1: candidate.json 外资研投源检查 ─────────────────

def check_candidate_guanlan():
    # 🔴 2026-10-14 实测口径改造（主人授权，根治 28 天化石盲区）：
    #   旧口径只查 source_dist 是否含「外资研投」key —— 47 只 09-16 化石无缝通过 28 天。
    #   新口径: key 存在 **且** 外资研投股票 last_seen 最大值距今 ≤ 4 个日历日。
    #   （4 天 > 单个长周末，覆盖 10-01~10-08 国庆之外的常规假期；真断供第 5 天必炸）
    if not CANDIDATE_FILE.exists():
        return False, {}, 0, "FILE_MISSING"
    try:
        d = json.load(open(CANDIDATE_FILE, encoding="utf-8"))
        sd = d.get("source_dist") or {}
        has = "外资研投" in sd
        total = d.get("total", 0)
        det = "sources=" + str(list(sd.keys())) + ", total=" + str(total)
        if not has:
            return False, sd, total, det + "（缺外资研投源）"
        # 实测新鲜度：扫外资研投股票的 last_seen 最大值
        stocks = d.get("stocks") or {}
        if isinstance(stocks, list):
            stocks = {str(i): s for i, s in enumerate(stocks)}
        max_seen = ""
        n_gk = 0
        for s in stocks.values():
            try:
                if "外资研投" in (s.get("sources") or []):
                    n_gk += 1
                    ls = str(s.get("last_seen", "") or "")
                    if ls > max_seen:
                        max_seen = ls
            except Exception:
                continue
        if n_gk == 0 or not max_seen:
            return False, sd, total, det + "（外资研投 0 只/无 last_seen）"
        try:
            age_days = (datetime.now(CST).date()
                        - datetime.strptime(max_seen, "%Y-%m-%d").date()).days
        except ValueError:
            return False, sd, total, det + f"（last_seen 格式异常: {max_seen}）"
        if age_days > 4:
            return False, sd, total, (det + f"（陈旧: last_seen 最大值 {max_seen}"
                                      f"，距今 {age_days} 天 —— token/抓取链疑断供）")
        return True, sd, total, det + f"（外资研投 {n_gk} 只, last_seen={max_seen}, 新鲜）"
    except Exception as e:
        return False, {}, 0, "PARSE_ERROR: " + str(e)


def heal_candidate_guanlan(dry_run=False):
    # 1. 检查 token
    if not ZSXQ_TOKEN_FILE.exists():
        return False, "zsxq_token.json 不存在，无法拉取外资研投数据。需用户提供 token。"
    # 2. 检查/生成 watchlist —— 🔴 2026-10-14: 缺失 **或陈旧(非今日)** 都重跑 extractor
    #    （旧逻辑只在缺失时跑 → watchlist 停在旧日期也无人刷新，配合池子化石盲区 28 天）
    need_fetch = True
    gw_updated_day = ""
    if GUANLAN_WATCHLIST.exists():
        try:
            gw = json.load(open(GUANLAN_WATCHLIST, encoding="utf-8"))
            gw_updated_day = str(gw.get("updated", ""))[:10]
            need_fetch = (gw_updated_day != now_cst().strftime("%Y-%m-%d"))
        except Exception:
            need_fetch = True
    if need_fetch:
        log("外资研投 watchlist 缺失或陈旧(updated=" + str(gw_updated_day) + ")，运行 guanlan_extractor.py...", "RUN")
        r = subprocess.run(
            [PYTHON, str(ALGO_DIR / "guanlan_extractor.py")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300
        )
        if r.returncode != 0:
            reason = {42: "HTTP 401 凭据失效（token 过期/被注销）",
                      43: "API 持续返回空（限流/接口变化）",
                      44: "帖子解析出 0 研报（解析器疑似失效）"}.get(
                r.returncode, "rc=" + str(r.returncode))
            return False, "guanlan_extractor 硬失败: " + reason + " | " + (r.stdout or "")[-200:]
        log("guanlan_extractor 成功: " + (r.stdout or "")[:100], "OK")
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
        return True, "[DRY_RUN] 将并入外资研投数据并 push"
    # 3. 执行合并
    log("开始增量并入外资研投到 candidate.json...", "RUN")
    merge_result = _merge_guanlan_to_candidate()
    if not merge_result["success"]:
        return False, merge_result["message"]
    # 4. git push
    push_result = _push_candidate(merge_result)
    return push_result["success"], push_result["message"]


def _merge_guanlan_to_candidate():
    sys.path.insert(0, str(ALGO_DIR))
    try:
        from build_candidate_pool import _norm, resolve_clean_name
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
        # 🛡 2026-09-23 一劳永逸（本函数是错名的传播口）：原直接写 clean_name，而 _norm 只做
        #   代码/市场格式化、不校名字 ⇒ 港股研报名被原样贴到 zfill(6) 后的 A 股码上
        #   （00807 上海实业环境 → 000807 顶掉 云铝股份；同理 000591/000703… 共 880 组同号）。
        #   改走全站唯一校入口 resolve_clean_name：
        #   东财 f58(云端权威) > stock_names.json(A股权威) > 干净原名 > 代码兜底。
        _auth = resolve_clean_name(padded_code, mkt_key, clean_name or name)
        key = mkt_key + "_" + padded_code
        if key not in stocks:
            stocks[key] = {
                "name": _auth or clean_name or name,
                "code": padded_code,
                "market": market_raw,
                "sources": ["外资研投"],
                "first_seen": s.get("added_date", ""),
            }
            added += 1
        else:
            if "外资研投" not in stocks[key].get("sources", []):
                stocks[key]["sources"].append("外资研投")
            # 存量条目名字若是错的（历史遗留）→ 用权威名就地纠正，不必等下一轮重建
            if _auth and stocks[key].get("name") != _auth:
                stocks[key]["name"] = _auth

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
    msg = "fix(candidate): 自愈并入外资研投(+" + str(added_val) + ") [self_heal_monitor]"
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
            if "外资研投" not in (d.get("source_dist") or {}):
                log("rebase 冲突导致外资研投被覆盖，重新并入...", "WARN")
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
            # 🔴 2026-09-21 小九·纵深防御：补 pathspec，杜绝吞掉陈旧暂存区（数据回滚地雷）。
            ["git", "commit", "-m", msg, "--", str(CANDIDATE_FILE)],
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


# ── P0-3: MOMENTUM_FILTER.js（动量共识筛选卡源）新鲜度 ──
# 2026-08-19 一劳永逸修复：该卡原被主人投诉「好几天没动静」。根因并非盘中刷新问题，而是：
#   ① 候选清单完全由 OCR 标签(超跌反弹/consec_before/stage)驱动，属【日频信号】，intraday 重算内容不变；
#   ② momentum_common_filter.py 此前不在任何自动链，OCR 输入更新后卡永不重算。
# 现修复：cloud_dispatcher.py 检测「新 OCR 输入」派发 v8_algo_intraday_lite.yml 即时重算 +
#   algorithms/emit_momentum_filter.py 随盘后算法链每晚 18:30 兜底重算（两路互补）。
# 本检查负责「跟踪确认」：缺失/解析失败=真异常(FAIL)；OCR 源比 filter 新=有新 PDF 待重算(WARN 留痕，
#   dispatcher 应已派发)；其余=OK（日频信号，陈旧本身非异常）。本机不直接 push（云端为修复方）。
def check_momentum_filter():
    if not MOMENTUM_FILTER_FILE.exists():
        return "fail", None, 99999, "FILE_MISSING"
    try:
        fsrc = open(MOMENTUM_FILTER_FILE, encoding="utf-8").read()
        mg = re.search(r'["\']generated["\']\s*:\s*["\'](\d{4}-\d{2}-\d{2})', fsrc)
        fg = mg.group(1) if mg else None
        if not fg:
            return "fail", None, 99999, "无法解析 generated"
        # OCR 源(STOCK_MOMENTUM_STATE_V2)最大 date 比 filter 生成日期新 → 有新 PDF 输入尚未重算
        s = MOMENTUM_FILTER_FILE.parent / "STOCK_MOMENTUM_STATE_V2.js"
        if s.exists():
            ssrc = open(s, encoding="utf-8").read()
            dates = re.findall(r'["\']date["\']\s*:\s*["\'](\d{4}-\d{2}-\d{2})', ssrc)
            sd = max(dates) if dates else None
            if sd and sd > fg:
                return "warn", fg, 0, "有新 OCR 输入(源%s>filter%s)待重算(dispatcher应已派发v8_algo_intraday_lite)"
        return "ok", fg, 0, "generated=%s (OCR驱动日频信号, 新PDF输入后自动重算)" % fg
    except Exception as e:
        return "fail", None, 99999, "解析错误: " + str(e)


# ── P1-1: zsxq_token 检查 ───────────────────────────────

def _token_valid(path):
    """校验单份 token 文件：返回 (True/False/None, detail)。None = 文件不存在。"""
    try:
        if not path.exists():
            return None, "TOKEN_FILE_MISSING"
        d = json.load(open(path, encoding="utf-8"))
        token = d.get("token", "")
        if not token or len(token) < 10:
            return False, "TOKEN_INVALID_FORMAT"
        return True, "OK (len=" + str(len(token)) + ")"
    except Exception as e:
        return False, "TOKEN_PARSE_ERROR: " + str(e)


def _read_alert_state():
    try:
        return json.load(open(ALERT_STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _write_alert_state(state):
    try:
        ALERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        log("告警状态写入失败(不影响主流程): " + str(e), "WARN")


def _alert_guanlan_down(heal_msg, check_det):
    """🔴 2026-10-14 新增（主人授权）：P0-1 实测口径失败且**无法自愈** → 邮件告警。
    这是外资研投断供的唯一邮件出口（云端无 SMTP，extractor 只出 exit 码）。
    状态翻转即发；同状态 6h 冷却去重（复用 _alert_token_lost 同款模式）。
    告警失败绝不阻断主流程。"""
    try:
        state = _read_alert_state()
        last_state = state.get("guanlan_state")
        last_alert = state.get("guanlan_last_alert", "")
        now = now_cst()
        cooled = False
        if last_state == "bad" and last_alert:
            try:
                last_dt = datetime.fromisoformat(last_alert)
                cooled = (now - last_dt) < timedelta(hours=TOKEN_ALERT_COOLDOWN_HOURS)
            except Exception:
                cooled = False
        state["guanlan_state"] = "bad"
        state["guanlan_last_seen_bad"] = now.isoformat()
        _write_alert_state(state)
        if cooled:
            log("P0-1 断供告警处于 6h 冷却内(上轮已发)，本轮不重复发信", "WARN")
            return
        from v8_send_alert import send_alert
        subject = "[v8自愈] 外资研投断供且无法自愈 —— token/抓取链需人工介入"
        body = (
            "自愈监控（self_heal_monitor.py，每 10 分钟一轮）检测到：\n\n"
            "  P0-1  外资研投源缺失或陈旧（实测口径: last_seen 距今 >4 天）\n"
            "    检查详情: " + str(check_det) + "\n"
            "    自愈结果: " + str(heal_msg) + "\n\n"
            "影响面：\n"
            "  · 候选池外资研投腿停更（last-good 旧料保留，不再被空数据洗掉）；\n"
            "  · maharo 出稿素材冻结；\n"
            "  · 云端 Secret ZSXQ_TOKEN 与本地 data/zsxq_token.json 需逐一排查换新。\n\n"
            "恢复步骤：\n"
            "  1. 浏览器登录 wx.zsxq.com 取新 zsxq_access_token；\n"
            "  2. 更新本地 data/zsxq_token.json + 云端 Secret ZSXQ_TOKEN（两处都要）；\n"
            "  3. 手动跑一次 guanlan_extractor.py 验证 exit=0。\n"
        )
        send_alert(subject, body, level="infra")
    except Exception as e:
        log("P0-1 告警邮件异常(不阻断): " + str(e), "WARN")


def _mark_guanlan_state_ok():
    """P0-1 恢复正常 → 状态翻回 ok（下次断供状态翻转即立即发信，不吃冷却）。"""
    try:
        state = _read_alert_state()
        if state.get("guanlan_state") not in (None, "ok"):
            log("P0-1 状态翻转: bad → ok（断供恢复）", "HEAL")
        state["guanlan_state"] = "ok"
        state["guanlan_last_ok"] = now_cst().isoformat()
        _write_alert_state(state)
    except Exception:
        pass


def _alert_token_lost(det_repo, det_backup):
    """真异常（两处皆无 token）→ 邮件告警。状态翻转即发；同状态 6h 内冷却去重。
    告警失败绝不阻断主流程（自愈脚本不能因为发不出邮件而崩）。"""
    state = _read_alert_state()
    last_state = state.get("zsxq_state")
    last_alert = state.get("zsxq_last_alert", "")
    now = now_cst()

    cooled = False
    if last_state == "bad" and last_alert:
        try:
            last_dt = datetime.fromisoformat(last_alert)
            cooled = (now - last_dt) < timedelta(hours=TOKEN_ALERT_COOLDOWN_HOURS)
        except Exception:
            cooled = False

    state["zsxq_state"] = "bad"
    state["zsxq_last_seen_bad"] = now.isoformat()

    if cooled:
        log("P1-1 真异常但处于 6h 告警冷却内(上轮已发)，本轮不重复发信", "WARN")
        _write_alert_state(state)
        return

    subject = "[v8自愈] zsxq_token 本地丢失 —— 观澜台本地抓取停摆，需补 token"
    body = (
        "自愈监控（self_heal_monitor.py，每 10 分钟一轮）检测到：\n\n"
        "  P1-1  zsxq_token 两处皆不可用 → 真异常（非例行计数）\n"
        "    仓库内 : " + str(ZSXQ_TOKEN_FILE) + "  → " + str(det_repo) + "\n"
        "    外置副本: " + str(ZSXQ_TOKEN_BACKUP) + "  → " + str(det_backup) + "\n\n"
        "影响面：\n"
        "  · 生产零影响 —— 云端 GitHub Secret ZSXQ_TOKEN 仍在兜底，主站外资研投数据正常；\n"
        "  · 本机侧 —— 观澜台(guanlan_extractor)本地抓取将失败，P0-1 自愈能力降级。\n\n"
        "恢复步骤（1 分钟）：\n"
        "  1. 浏览器登录 wx.zsxq.com；\n"
        "  2. F12 → Application → Cookies → https://wx.zsxq.com；\n"
        "  3. 复制 zsxq_access_token（UUID_哈希，约 53 字符；不是 xq_a_token）；\n"
        "  4. 交给小九写入 data/zsxq_token.json（会自动同步一份外置副本）。\n\n"
        "触发时间: " + now.strftime("%Y-%m-%d %H:%M:%S") + " (CST)\n"
        "来源: self_heal_monitor.py P1-1"
    )
    try:
        sys.path.insert(0, str(ROOT))
        from v8_send_alert import send_alert
        send_alert(subject, body, level="infra")
        state["zsxq_last_alert"] = now.isoformat()
        log("P1-1 真异常已发邮件告警(level=infra)", "ALERT")
    except Exception as e:
        log("P1-1 邮件告警发送失败: " + str(e), "WARN")
    _write_alert_state(state)


def check_zsxq_token():
    """返回 (ok, detail)。ok=True 时保证仓库内文件可用（必要时已自动回填）。"""
    ok, det = _token_valid(ZSXQ_TOKEN_FILE)
    if ok:
        # 仓库在、外置副本缺 → 静默补一份（双写保护，下次被清理即可自愈）
        if not ZSXQ_TOKEN_BACKUP.exists():
            try:
                ZSXQ_TOKEN_BACKUP.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ZSXQ_TOKEN_FILE, ZSXQ_TOKEN_BACKUP)
                log("P1-1 已补写外置副本: " + str(ZSXQ_TOKEN_BACKUP), "OK")
            except Exception as e:
                log("P1-1 外置副本补写失败(不影响本轮): " + str(e), "WARN")
        # 恢复干净态：状态翻转记录复位（下次再坏 = 立即告警）
        st = _read_alert_state()
        if st.get("zsxq_state") == "bad":
            st["zsxq_state"] = "ok"
            st["zsxq_last_recovered"] = now_cst().isoformat()
            _write_alert_state(st)
        return True, det + " [仓库]"

    bok, bdet = _token_valid(ZSXQ_TOKEN_BACKUP)
    if bok:
        if CHECK_ONLY:
            # 仅检查模式：不写盘、不发信，只如实报告（保持 --check-only 的只读语义）
            return True, bdet + " [外置副本可用(仅检查,未回填)]"
        try:
            ZSXQ_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ZSXQ_TOKEN_BACKUP, ZSXQ_TOKEN_FILE)
            st = _read_alert_state()
            st["zsxq_state"] = "ok"
            st["zsxq_last_recovered"] = now_cst().isoformat()
            _write_alert_state(st)
            log("P1-1 仓库 token 缺失，已从外置副本自动回填（真自愈）", "HEAL")
            return True, bdet + " [已从外置副本回填]"
        except Exception as e:
            _alert_token_lost(det, "回填失败: " + str(e))
            return False, "仓库缺失且回填失败: " + str(e)

    if CHECK_ONLY:
        return False, det + " / 外置副本: " + bdet
    _alert_token_lost(det, bdet)
    return False, det + " / 外置副本: " + bdet


# ── 主流程 ──────────────────────────────────────────────

def run_check_only():
    global CHECK_ONLY
    CHECK_ONLY = True
    results = {}
    has, sd, total, det = check_candidate_guanlan()
    results["candidate_guanlan"] = {"ok": has, "detail": det, "source_dist": sd, "total": total}
    icon = "OK" if has else "FAIL"
    log("[" + icon + "] candidate.json 外资研投: " + det)

    fresh, last_day, age, det2 = check_momentum_state()
    results["momentum_state"] = {"ok": fresh, "detail": det2, "last_day": last_day, "age_days": age}
    if not fresh:
        if MOMENTUM_MANUAL_DEPENDENCY and det2.startswith(_MOMENTUM_KNOWN_QUIET_PREFIXES):
            log("[WARN] STOCK_MOMENTUM_STATE.js 陈旧(已知遗留/需PDF OCR, 免告警): " + det2, "WARN")
        else:
            log("[FAIL] STOCK_MOMENTUM_STATE.js: " + det2)
    else:
        log("[OK] STOCK_MOMENTUM_STATE.js: " + det2)

    tok_ok, tok_det = check_zsxq_token()
    results["zsxq_token"] = {"ok": tok_ok, "detail": tok_det}
    icon = "OK" if tok_ok else "FAIL"
    log("[" + icon + "] zsxq_token: " + tok_det)

    # P0-3: 动量共识筛选卡源新鲜度（盘中窗口陈旧→WARN 留痕；缺失/解析失败→FAIL）
    mf_status, mf_gen, mf_age, mf_det = check_momentum_filter()
    results["momentum_filter"] = {"ok": mf_status != "fail", "status": mf_status,
                                   "detail": mf_det, "generated": mf_gen, "age_min": mf_age}
    if mf_status == "fail":
        log("[FAIL] MOMENTUM_FILTER.js: " + mf_det, "FAIL")
    elif mf_status == "warn":
        log("[WARN] MOMENTUM_FILTER.js: " + mf_det, "WARN")
    else:
        log("[OK] MOMENTUM_FILTER.js: " + mf_det, "OK")

    # momentum 陈旧属已知人工依赖、动量共识盘中陈旧属 WARN 留痕，均不计入整体 FAIL 判定
    all_ok = all(v["ok"] for k, v in results.items()
                 if k not in ("momentum_state", "momentum_filter"))
    if all_ok:
        log("=== 全部正常（含已知遗留 WARN）===", "PASS")
        return 0
    issues = [k for k, v in results.items() if not v["ok"] and k != "momentum_state"]
    log("=== 发现问题: " + ", ".join(issues) + " ===", "FAIL")
    return 2


def run_heal(json_output=False):
    actions_taken = []
    heal_results = {}
    exit_code = 0
    if json_output:
        log.to_stderr = True  # stdout 仅输出 JSON（供自动化机器解析），日志走 stderr

    # P0-1
    has, sd, total, det = check_candidate_guanlan()
    if not has:
        log("[FAIL] P0-1: candidate.json 外资研投源缺失或陈旧! " + det, "FAIL")
        success, msg = heal_candidate_guanlan()
        heal_results["candidate_guanlan"] = {"ok": success, "message": msg}
        if success:
            log("[HEAL] P0-1 已自愈: " + msg, "HEAL")
            actions_taken.append("并入外资研投: " + msg)
            _mark_guanlan_state_ok()
        else:
            log("[FAIL] P0-1 无法自愈: " + msg, "FAIL")
            _alert_guanlan_down(msg, det)
            exit_code = 2
    else:
        guanlan_count = sd.get("外资研投", 0)
        log("[OK] P0-1: candidate.json 含外资研投(" + str(guanlan_count) + "只) " + det, "OK")
        heal_results["candidate_guanlan"] = {"ok": True, "message": det}
        _mark_guanlan_state_ok()

    # P0-2: STOCK_MOMENTUM_STATE 新鲜度（源=PDF OCR 人工流程；陈旧只 WARN 免邮件，与 v8_health_check.py 对齐）
    fresh, last_day, age, det2 = check_momentum_state()
    if not fresh:
        # 🔴 2026-10-14 一劳永逸：陈旧=OCR 人工依赖预期态，只 WARN 留痕，不升级 FAIL、不阻断、不发邮件。
        log("[WARN] P0-2: STOCK_MOMENTUM_STATE.js 陈旧(需主人 PDF→OCR 刷新, 免邮件): " + det2, "WARN")
        heal_results["momentum_state"] = {"ok": True, "known_manual_dependency": True, "message": det2}
    else:
        log("[OK] P0-2: STOCK_MOMENTUM_STATE.js 新鲜 (" + det2 + ")", "OK")
        heal_results["momentum_state"] = {"ok": True, "message": det2}

    # P0-3: 动量共识筛选卡源新鲜度（云端盘中刷新为修复方，本机仅检测+留痕，不直接 push）
    mf_status, mf_gen, mf_age, mf_det = check_momentum_filter()
    if mf_status == "fail":
        log("[FAIL] P0-3: MOMENTUM_FILTER.js 真异常! " + mf_det, "FAIL")
        heal_results["momentum_filter"] = {"ok": False, "message": mf_det}
        actions_taken.append("MOMENTUM_FILTER 异常: " + mf_det)
        exit_code = max(exit_code, 2)
    elif mf_status == "warn":
        log("[WARN] P0-3: MOMENTUM_FILTER.js 有新 OCR 待重算(留痕): " + mf_det, "WARN")
        heal_results["momentum_filter"] = {"ok": True, "known_cloud_dependency": True, "message": mf_det}
        actions_taken.append("MOMENTUM_FILTER 新OCR待重算: " + mf_det)
    else:
        log("[OK] P0-3: MOMENTUM_FILTER.js 新鲜 (" + mf_det + ")", "OK")
        heal_results["momentum_filter"] = {"ok": True, "message": mf_det}

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
