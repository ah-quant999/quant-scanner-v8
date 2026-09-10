#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 逻辑详解页 / 运维页 与 实际 workflow 调度对齐校验。

调用方：
  · .github/scripts/pre_deploy_audit.py 第 [4/4] 项 —— **CI 门禁，EXIT != 0 会阻断 deploy**
  · v8_backup.yml 每晚（该处 continue-on-error，仅记录不阻断）

校验四项：
  1. 抽取 .github/workflows 全部 cron 调度；
  2. MUST_HAVE_CRON 的 workflow 必须 (a) 真有 cron、(b) 已在文档源出现；
  3. 兜底：任何有 cron 的 workflow 都必须落在 MUST/ALLOW 名单内且已文档化；
  4. 名单自净：名单里的 workflow 文件必须真实存在于 .github/workflows/（防名单积灰误导）。

发现漂移 → 写 HANDOVER_LOG.jsonl + 打印告警，退出码 2（全部通过 → 0）。

🔴 2026-09-10 阿狸咪修正（原版逻辑缺陷）
   原版 `section(html,"lg")` 只在 **index.html** 里找 `id="sec-lg"`，但逻辑详解页自
   2026-08-31 已拆为独立文件 logic.html —— index.html **没有** `id="sec-lg"`。
   后果：`lg` 恒为空串，**逻辑详解页从未被纳入校验**，两页可长期互相漂移而无任何告警。
   现改为三源合并（见 DOC_SOURCES），并在输出里打印各源字符数，防止再次「失明」。

不依赖 PyYAML（纯正则解析，避免云端环境缺包）。
"""
import os
import re
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.join(ROOT, ".github", "workflows")
INDEX = os.path.join(ROOT, "index.html")
LOGIC = os.path.join(ROOT, "logic.html")

# 文档源（2026-09-10 起三源合并；任一缺失只记录不报错）
DOC_SOURCES = [
    (INDEX, "lg", "index.html#sec-lg"),
    (INDEX, "op", "index.html#sec-op"),
    (LOGIC, "lg", "logic.html#sec-lg"),
]

# ── 必须有 cron 且必须文档化的 workflow ──────────────────────────
# 🔴 新增带 cron 的 workflow 必须双登记：(1) 本名单 (2) 文档源。
#    漏登记 → Pre-deploy audit 失败 → v8_build_deploy 全链阻断（数据推了不部署）。
MUST_HAVE_CRON = {
    "v8_cn_fetch_cloud": "中国数据抓取(云端主链)",
    "v8_cn_fetch_cloud_hosted": "中国数据抓取(hosted 备援)",
    "v8_cn_fetch_watchdog": "抓取看门狗(唯一状态型兜底)",
    "v8_algo_cloud": "盘后算法链(云端主链)",
    "v8_algo_intraday_lite": "盘中轻量算法链",
    "v8_lhb_fetch": "龙虎榜抓取",
    "v8_ima_strong_stock": "高手 ima 强势股",
    "v8_stock_quote_refresh": "盘中行情刷新",
    "v8_risk_gauge": "危机雷达/风险温度计",
    "v8_health_patrol": "健康巡检+自愈",
    "v8_cache_buster_reconcile": "?v 缓存戳对齐",
    "v8_daily_audit": "每晚全站审核",
    "v8_backup": "每日自动备份",
    "v8_cleanup": "缓存清理(周日)",
    "cloud_weekly_cleanup": "周度清理",
    "runner_health_alert": "Runner 健康监控",
    "v8_t1_guard": "周六 T+1 兜底",
    "v8_weekend_light": "周末轻量维护(周六/日)",
    # 2026-09-10 阿狸咪补登记：板块资金日内快照（独立高频·根治上午空白）
    "v8_intraday_snapshot": "板块资金日内快照(盘中每10分钟)",
    # 2026-09-10 阿狸咪归类纠正：准点档调度器**事实持有 14 条 cron**（9:40–15:00 每 20 分），
    #   旧版把它归入 ALLOW_NO_CRON 属分类错误（当时 cron 一度被注释，现早已恢复）。
    "v8_cn_fetch_intraday_lemoncat": "盘中准点档调度器(14 档·唯一主线)",
    # 2026-09-10 阿狸咪升格：实验卡抓取链有 16:30 CST cron 且已文档化 → ALLOW → MUST
    "v8_cn_fetch_experiments": "暂未上架·实验卡抓取(16:30)",
    # 注：v8_freshness_watch / v8_slot_scheduler 已于 2026-09-10 删除（派发源精简），
    #     从本名单彻底移除，勿再登记。
}

# ── 刻意无 cron（仅 workflow_dispatch 应急 / 事件驱动）──────────
# 2026-09-10 清理死登记：原列的 v8_cn_fetch / v8_algo / v8_sync_v6_data / v8_sync_legacy
#   四个 workflow 文件**早已不存在于仓库**，留着只会误导后来人（第 4 项校验会拦住复活）。
ALLOW_NO_CRON = {
    "v8_algo_run": "盘后算法链应急回退（主链已迁 v8_algo_cloud）",
    "v8_cn_fetch_cloud_selfhosted": "selfhosted 备援（无 cron，按需 dispatch）",
    "v8_build_deploy": "由 push / workflow_run 触发，无 cron",
}


def _read(path):
    try:
        return open(path, encoding="utf-8").read()
    except Exception:
        return ""


def extract_crons():
    """返回 [(stem, cst_comment, raw_cron)]，跳过被注释掉的 cron 行。"""
    facts = []
    if not os.path.isdir(WF_DIR):
        return facts
    for fn in sorted(os.listdir(WF_DIR)):
        if not fn.endswith(".yml"):
            continue
        stem = fn[:-4]
        txt = _read(os.path.join(WF_DIR, fn))
        for pat in (r"^\s*-\s*cron:\s*'([^']+)'\s*(?:#\s*(.*))?$",
                    r'^\s*-\s*cron:\s*"([^"]+)"\s*(?:#\s*(.*))?$'):
            for m in re.finditer(pat, txt, re.M):
                facts.append((stem, (m.group(2) or "").strip(), m.group(1)))
    return facts


def section(html, tag):
    """取 id="sec-<tag>" 起的正文（到文件末；宽松匹配面，避免误报）。"""
    i = html.find('id="sec-%s"' % tag)
    return html[i:] if i >= 0 else ""


def load_doc():
    """三源合并 → (doc_text, [(源名, 字符数)])。"""
    parts, srcs = [], []
    for path, tag, label in DOC_SOURCES:
        if not os.path.exists(path):
            srcs.append((label, -1))   # -1 = 文件不存在
            continue
        seg = section(_read(path), tag)
        srcs.append((label, len(seg)))
        if seg:
            parts.append(seg)
    return "\n".join(parts), srcs


def main():
    if not os.path.exists(INDEX):
        print("❌ index.html 不存在，无法校验")
        sys.exit(1)

    doc, srcs = load_doc()
    print("📚 文档源（2026-09-10 起三源合并，修复「逻辑详解页从未被校验」缺陷）：")
    for label, n in srcs:
        print("   · %-22s %s" % (label, "文件不存在（跳过）" if n < 0 else "%d 字符" % n))
    if not doc.strip():
        print("⚠️ 文档源全部为空 → 无法判定文档化，按漂移处理")
    print()

    facts = extract_crons()
    stems_with_cron = {s for s, _, _ in facts}
    print("🔧 实际有 cron 的 workflow：%d 个；名单：MUST=%d / ALLOW=%d"
          % (len(stems_with_cron), len(MUST_HAVE_CRON), len(ALLOW_NO_CRON)))
    print()

    drift = []

    # 方向1：MUST_HAVE_CRON 必须 (a) 有 cron (b) 文档化
    for stem, desc in MUST_HAVE_CRON.items():
        if stem not in stems_with_cron:
            drift.append("%s（%s）：期望有 cron 但实际 workflow 无 cron 调度" % (desc, stem))
            continue
        if stem not in doc:
            drift.append("%s（%s）：实际有 cron 调度，但文档源（逻辑详解页/运维页）未文档化"
                         % (desc, stem))

    # 方向2：兜底 —— 任何有 cron 的 workflow 都要登记且文档化
    for stem in sorted(stems_with_cron):
        if stem in MUST_HAVE_CRON or stem in ALLOW_NO_CRON:
            continue
        if stem not in doc:
            drift.append("workflow %s 有 cron 调度，但既未登记 MUST/ALLOW 名单、也未文档化" % stem)
        else:
            drift.append("workflow %s 已文档化但未登记 MUST_HAVE_CRON 名单（漏登记 → 未来改名/删 cron 时无人察觉）"
                         % stem)

    # 方向3：名单自净 —— 登记了但文件不存在 = 死登记（2026-09-10 新增）
    if os.path.isdir(WF_DIR):
        for group, mapping in (("MUST_HAVE_CRON", MUST_HAVE_CRON), ("ALLOW_NO_CRON", ALLOW_NO_CRON)):
            for stem in sorted(mapping):
                if not os.path.exists(os.path.join(WF_DIR, stem + ".yml")):
                    drift.append("死登记：%s 里的 %s 在 .github/workflows/ 下已无对应文件，请清理名单"
                                 % (group, stem))

    if drift:
        print("⚠️ 逻辑详解页/运维页 与 实际 workflow 存在未对齐项：")
        for d in drift:
            print("  - " + d)
        try:
            ts = subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"]).decode().strip()
        except Exception:
            ts = "unknown"
        rec = {"time": ts, "mode": "align_logic_ops", "drift": drift}
        try:
            with open(os.path.join(ROOT, "HANDOVER_LOG.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print("📝 已写入 HANDOVER_LOG.jsonl")
        except Exception as e:
            print("⚠️ 写日志失败：%s" % e)
        sys.exit(2)

    print("✅ 对齐校验通过：关键 workflow 均已文档化，无过期引用，名单无死登记。")
    sys.exit(0)


if __name__ == "__main__":
    main()
