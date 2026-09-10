#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 每日审计：当天修改审核通过防覆盖 + 与单位机小九交接。

挂在 v8_backup.yml 23:00 CST 备份任务里跑（与 align_logic_ops.py / verify_card_badges.py 并列）。
该 step 自 2026-09-10 起为【真阻断】：结构性漂移 → 退出码 1 → job 失败（不再 continue-on-error）。

检查项：
  1. 当天小九的常规交接文档存在
     （唯一交接目录 docs/ops/handover/ 下的 YYYY-MM-DD_HHmm[*_URGENT]_*小九* 文件）
     → 否则告警（未与小九做常规交接）
  2. 当天 origin/main 所有 commit 的 short hash 至少在一份当日交接文档里被提到
     → 否则告警（修改未经审计/未记录，防覆盖场景下是高风险 commit）
退出码：结构性硬失败（上述 1 或 2 未提及比例 > MANUAL_MISS_HARD_RATIO）→ 1；
        非结构性软告警 / 无法判定 → 0（仅落 HANDOVER_LOG.jsonl，不阻断）。

不依赖 PyYAML；仅用 subprocess 调 git。
"""
import os, re, sys, json, subprocess
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT, "HANDOVER_LOG.jsonl")

# 北京时间
CST = timezone(timedelta(hours=8))
today_cst = datetime.now(CST).strftime("%Y-%m-%d")
today_compact = today_cst.replace("-", "")     # 20260806
# 2026-09-10 主人令：交接文档统一到唯一目录 docs/ops/handover/，
#   命名 YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md
#   按【文件名】排序 = 时间排序；禁用 mtime（坚果云同步会重写 mtime）
HANDOVER_DIR = os.path.join(ROOT, "docs", "ops", "handover")
today_prefix = today_cst + "_"                 # 当天交接文件名前缀
short_sha_re = re.compile(r"\b[0-9a-f]{7,40}\b")

# 🛡 2026-09-10 主人拍板「结构性错误硬阻断 + 非结构性降 warn 不阻断」：
#   结构性错误（硬失败，退出码 1）：
#     ① 当天缺失小九的常规交接文档（docs/ops/handover/<今日>_*小九*）—— 完全未交接
#     ② 当天人工 commit 未提及比例 > MANUAL_MISS_HARD_RATIO —— 大面积未记录 = 交接实质缺失
#   非结构性（降软告警，不影响退出码）：
#     ③ 个别 commit 关键词未命中 —— 关键词为模糊匹配，个例属误差，不应误杀整轮审计
MANUAL_MISS_HARD_RATIO = 0.5
SOFT = "soft"   # 软告警哨兵（与 True 通过 / False 硬失败 / None 无法判定 区分）



def run(cmd, cwd=ROOT):
    """Run a shell command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30,
                           shell=isinstance(cmd, str))
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return 255, "", str(e)


def get_today_origin_commits():
    """拉今天 (CST 00:00 起) origin/main 的全部 commit，return [(short_sha, subject), ...]"""
    rc, out, err = run(["git", "fetch", "origin", "main"], cwd=ROOT)
    if rc != 0:
        print(f"⚠️ git fetch origin 失败：{err}（可能是 github.com:443 间歇中断）")
        return None  # 信号：无法判定

    # git log origin/main --since=YYYY-MM-DDT00:00:00+08:00 --until=tomorrow
    since = f"{today_cst}T00:00:00+08:00"
    rc, out, err = run([
        "git", "log", "origin/main",
        f"--since={since}",
        "--format=%h %s",
    ], cwd=ROOT)
    if rc != 0:
        print(f"⚠️ git log origin/main 失败：{err}")
        return None

    commits = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and re.match(r"^[0-9a-f]+$", parts[0]):
            commits.append((parts[0], parts[1]))
    return commits


def load_today_handover_text():
    """读当天全部交接文档（唯一目录 docs/ops/handover/）+ 自动化 memory.md，return list[str]

    🛡 2026-09-10 交接目录统一后修正：原先扮 os.listdir(ROOT) 找当日 *.md，
       迁移后仓库根只剩 5 个核心 md（当日交接全在 docs/ops/handover/）→
       命中面归零会使检查 2 的「关键词提及率」恒超阈值而误判硬失败。
    """
    texts = []
    # ① 唯一交接目录内当天全部交接（含 _URGENT_），按文件名升序读取
    if os.path.isdir(HANDOVER_DIR):
        for fn in sorted(os.listdir(HANDOVER_DIR)):
            if not fn.endswith(".md") or not fn.startswith(today_prefix):
                continue
            if fn.startswith(("README", "_")):
                continue
            texts.append(("handover/" + fn,
                          open(os.path.join(HANDOVER_DIR, fn), encoding="utf-8").read()))
    # ② 兼容：仓库根若仍有当日 md（历史遗留/临时件）一并纳入，防漏读
    for fn in os.listdir(ROOT):
        if not fn.endswith(".md"):
            continue
        if today_compact in fn or today_cst in fn:
            texts.append((fn, open(os.path.join(ROOT, fn), encoding="utf-8").read()))
    # 也读 .workbuddy/memory 里的当日记忆（跨仓视野）
    # 🛡 2026-09-10 修复路径 BUG：原写死 E:\workspace\quant-scanner-v8（不存在的副本目录），
    #    且 auto_root 误带前导反斜杠，本机运行时两处恒不命中 → 命中面被无谓砍掉。
    #    改为多候选探测，兼容双机真实工作目录。
    _mem_candidates = [
        os.path.join(ROOT, ".workbuddy", "memory"),
        os.path.join(ROOT, os.pardir, "quant-scanner-v8", ".workbuddy", "memory"),
        "E:" + os.sep + "workspace" + os.sep + "stock-scanner" + os.sep + ".workbuddy" + os.sep + "memory",
        "E:" + os.sep + "qs_workspaces" + os.sep + "quant-scanner-v8" + os.sep + ".workbuddy" + os.sep + "memory",
    ]
    for mem_root in _mem_candidates:
        mem_file = os.path.join(mem_root, today_cst + ".md")
        if os.path.exists(mem_file):
            texts.append(("memory/" + today_cst + ".md", open(mem_file, encoding="utf-8").read()))
            break
    # 自动化 memory（automation-*.md）
    _auto_candidates = [os.path.join(m, os.pardir, "automations") for m in _mem_candidates]
    auto_root = next((a for a in _auto_candidates if os.path.isdir(a)), None)
    if auto_root:
        for ad in os.listdir(auto_root):
            mfile = os.path.join(auto_root, ad, "memory.md")
            if os.path.exists(mfile):
                txt = open(mfile, encoding="utf-8").read()
                if today_compact in txt or today_cst in txt:
                    texts.append((f"automations/{ad}/memory.md", txt))
    return texts


def check_handover_xj_exists():
    """检查 1：当天小九的常规交接文档是否存在（唯一目录 docs/ops/handover/）

    命中判据：文件名以 <今日>_ 开头且含「小九」；`*_URGENT_*` 紧急件同样计入
    （紧急件本身就是一次交接，不应判「未交接」）。
    """
    hits = []
    if os.path.isdir(HANDOVER_DIR):
        for fn in sorted(os.listdir(HANDOVER_DIR)):
            if not fn.endswith(".md") or not fn.startswith(today_prefix):
                continue
            if fn.startswith(("README", "_")):
                continue
            if "小九" in fn:
                hits.append(fn)
    if hits:
        return True, ("✅ 当天小九交接已存在：" + "、".join(hits[:3])
                      + ("…" if len(hits) > 3 else ""))
    return False, (
        f"⚠️ 缺失当天小九的常规交接 —— docs/ops/handover/ 下无 「{today_cst}_*小九*」文件。"
        f"当天未与小九做常规交接；如本端(阿狸咪)已完成交接任务，请补写。"
    )


# 自动化 commit 前缀（机器产物，无需人手审计提及）
AUTO_COMMIT_PREFIXES = (
    "v8 build:",            # build_deploy workflow 自动产物
    "runner health:",       # runner 健康检查自动 commit
    "Merge origin/main",    # watchdog 自动 rebase 合并
)

# 人工 commit 的类型前缀（用于剥离，得到核心短语）
COMMIT_TYPE_PREFIX = re.compile(
    r"^(fix|chore|feat|refactor|docs|style|perf|test|build|ci)\s*(\([^)]*\))?\s*[:：]\s*"
)


def is_auto_commit(subject):
    return any(subject.startswith(p) for p in AUTO_COMMIT_PREFIXES)


def extract_keywords(subject):
    """从 commit subject 抽取多个关键词。
    优先级：
      1) 英文/数字 token（连续字母/数字/下划线，长度≥3）—— 如 safety_net, P0, 327687211
      2) 中文短语（连续中文 4 字以上）—— 如 兜底目标
      3) 含特殊 token 的中文片段（包含数字/英文）—— 如 35轮, cn_fetch
    返回 5-10 个关键词。
    """
    kws = []
    # 1) 英文+数字 token
    kws.extend(re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", subject))
    # 2) 中文 4 字以上
    kws.extend(re.findall(r"[\u4e00-\u9fa5]{4,}", subject))
    # 3) 中文+数字混合 3 字以上
    kws.extend(re.findall(r"[\u4e00-\u9fa5][\u4e00-\u9fa50-9a-zA-Z_]{2,}", subject))
    # 去重并按长度降序，取前 8 个
    seen = set()
    out = []
    for k in sorted(kws, key=len, reverse=True):
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= 8:
            break
    return out


def check_commits_audit(commits, handover_texts):
    """检查 2：当天 origin/main 的【人工】commit 至少在一份 HANDOVER/URGENT/memory 文件里被提及
       （自动化 commit 由 message 前缀识别；人工 commit 抽取 5-8 个关键词，任一出现在文档即视为提及）"""
    if commits is None:
        return None, "⚠️ 无法判定（git fetch 失败，可能是 github.com:443 间歇中断）"
    if not commits:
        return True, "ℹ️ 当天 origin/main 尚无新 commit（备份任务跑时已是 21:00，可接受）"

    all_text = "\n".join(t for _, t in handover_texts)

    auto_commits   = [(s, sub) for s, sub in commits if is_auto_commit(sub)]
    manual_commits = [(s, sub) for s, sub in commits if not is_auto_commit(sub)]

    not_mentioned = []
    for short, subj in manual_commits:
        kws = extract_keywords(subj)
        hit = [k for k in kws if k in all_text]
        if kws and hit:
            continue  # 至少一个关键词命中
        not_mentioned.append((short, subj, kws))

    lines = [f"  当天 origin/main 共 {len(commits)} 个 commit（自动化 {len(auto_commits)} + 人工 {len(manual_commits)}）"]
    if not manual_commits:
        lines.append("  ℹ️ 全部为自动化 commit，无需人工审计提及")
    elif not not_mentioned:
        lines.append(f"  ✅ 全部 {len(manual_commits)} 个人工 commit 关键词在交接文档里命中")
    else:
        lines.append(f"  ⚠️ {len(not_mentioned)}/{len(manual_commits)} 个人工 commit 关键词在交接文档里均未命中（防覆盖检查失败）：")
        for short, subj, kws in not_mentioned:
            lines.append(f"    - {short} {subj[:70]}")
            lines.append(f"        关键词: {kws}")

    if not_mentioned:
        ratio = len(not_mentioned) / max(1, len(manual_commits))
        # 🛡 2026-09-10 主人拍板：结构性错误硬阻断，非结构性降 warn 不阻断
        if ratio > MANUAL_MISS_HARD_RATIO:
            lines.append(f"  ❌ 未提及比例 {ratio:.0%} > {MANUAL_MISS_HARD_RATIO:.0%} → 结构性缺失（硬失败）")
            return False, "\n".join(lines)
        lines.append(f"  ⚠️ 未提及比例 {ratio:.0%} ≤ {MANUAL_MISS_HARD_RATIO:.0%} → 属个例误差，降软告警（不阻断）")
        return SOFT, "\n".join(lines)
    return True, "\n".join(lines)


def main():
    print(f"=== v8 每日审计 · {today_cst} CST ===\n")
    findings = []

    # 1. 与小九交接
    ok1, msg1 = check_handover_xj_exists()
    print(msg1)
    findings.append(("handover_xj", ok1, msg1))

    # 2. 当天 commit 审核
    commits = get_today_origin_commits()
    handover_texts = load_today_handover_text()
    print(f"  （读入 {len(handover_texts)} 份当日交接/记忆文件）")
    ok2, msg2 = check_commits_audit(commits, handover_texts)
    print(msg2)
    findings.append(("commits_audit", ok2, msg2))

    # 汇总
    print()
    has_drift = any(o is False for _, o, _ in findings)     # 结构性硬失败
    has_soft = any(o == SOFT for _, o, _ in findings)       # 非结构性软告警
    has_unknown = any(o is None for _, o, _ in findings)

    log = {
        "time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "verify_daily_audit",
        "host": "GitHubActions" if os.environ.get("GITHUB_ACTIONS") else "Local",
        "date_cst": today_cst,
        "commits_today": len(commits) if commits else 0,
        "handover_files": len(handover_texts),
        "findings": [
            {"name": n, "ok": o, "msg": m.split("\n")[0]} for n, o, m in findings
        ],
        "success": not has_drift,
        "soft_warn": has_soft,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")

    if has_drift:
        print(f"❌ 每日审计发现【结构性】漂移（硬失败），已写入 HANDOVER_LOG.jsonl（v8_backup.yml 审计步将真阻断本 job）")
        sys.exit(1)
    if has_soft:
        print(f"⚠️ 每日审计有【非结构性】软告警（不阻断，详见上方逐项）")
    if has_unknown:
        print(f"⚠️ 每日审计有项无法判定（网络/数据问题），已记录，不阻断")
    if has_soft or has_unknown:
        sys.exit(0)
    print(f"✅ 每日审计全部通过")


if __name__ == "__main__":
    main()
