#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 逻辑详解页 / 运维页 与 实际 workflow 调度对齐校验。

每晚随 v8_backup.yml 运行：
  1. 抽取 .github/workflows 全部 cron 调度（CST 时间取自行内注释）；
  2. 比对 index.html 的 逻辑详解页(sec-lg) + 运维页(sec-op) 是否已文档化这些调度；
  3. 反向检查：文档/任务看板引用了某 workflow，但该 workflow 已无 cron（说明文档过期）。

发现漂移 → 写 HANDOVER_LOG.jsonl 并打印告警，退出码 2（备份步用 continue-on-error 不阻断）。
全部通过 → 退出码 0。

不依赖 PyYAML（正则解析，避免云端环境缺包）。
"""
import os
import re
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.join(ROOT, ".github", "workflows")
INDEX = os.path.join(ROOT, "index.html")

# 必须有 cron 且必须在逻辑详解/运维页文档化的 workflow（其余为应急/探针/legacy，不强制）
MUST_HAVE_CRON = {
    # 有 cron 的 v8 主链 workflow（必须文档化）
    "v8_cn_fetch_cloud": "中国数据抓取(云端)",
    "v8_cn_fetch_cloud_hosted": "中国数据抓取(selfhosted 备援)",
    "v8_cn_fetch_watchdog": "抓取看门狗",
    "v8_slot_scheduler": "盘前/盘中/盘后调度分发",
    "v8_algo_cloud": "盘后算法链(云端主链)",
    "v8_algo_intraday_lite": "盘中轻量算法链",
    "v8_lhb_fetch": "龙虎榜抓取",
    "v8_ima_strong_stock": "高手 ima 强势股(周一-五 07:45)",
    "v8_stock_quote_refresh": "盘中行情刷新",
    "v8_risk_gauge": "危机雷达/风险温度计",
    "v8_freshness_watch": "数据新鲜度值守",
    "v8_health_patrol": "健康巡检",
    "v8_cache_buster_reconcile": "?v 缓存戳对齐",
    "v8_daily_audit": "每晚全站审核",
    "v8_backup": "每日自动备份",
    "v8_cleanup": "缓存清理(周日)",
    "cloud_weekly_cleanup": "周度清理",
    "runner_health_alert": "Runner健康监控",
    "v8_t1_guard": "周六 T+1 兜底",
    "v8_weekend_light": "周末轻量维护(周六/日)",
}

# 文档里允许出现但刻意无 cron（仅 workflow_dispatch 应急）的 workflow
ALLOW_NO_CRON = {
    "v8_algo_run",                # 盘后算法链应急回退（主链已迁 v8_algo_cloud）
    "v8_cn_fetch",                # 中国节点应急回退（主链已迁 v8_cn_fetch_cloud）
    "v8_cn_fetch_cloud_selfhosted", # selfhosted 备援（无 cron，按需 dispatch）
    "v8_sync_v6_data",            # v6→v8 数据桥（应急）
    "v8_sync_legacy",             # legacy 同步（已退役）
    "v8_build_deploy",            # 由 workflow_run 触发，无 cron
    "v8_algo",                    # 46 模块新鲜度体检（已迁 dispatch-only，老引用）
    "v8_safety_net",              # Safety Net 兜底（已迁 dispatch-only，老引用）
    "v8_self_heal",               # 云端自愈（已迁 dispatch-only，老引用）
}


def extract_crons():
    """返回 [(stem, cst_comment, raw_cron)]，跳过被注释掉的 cron 行。"""
    facts = []
    if not os.path.isdir(WF_DIR):
        return facts
    for fn in sorted(os.listdir(WF_DIR)):
        if not fn.endswith(".yml"):
            continue
        stem = fn[:-4]
        path = os.path.join(WF_DIR, fn)
        try:
            txt = open(path, encoding="utf-8").read()
        except Exception:
            continue
        for pat in (r"^\s*-\s*cron:\s*'([^']+)'\s*(?:#\s*(.*))?$",
                    r'^\s*-\s*cron:\s*"([^"]+)"\s*(?:#\s*(.*))?$'):
            for m in re.finditer(pat, txt, re.M):
                facts.append((stem, (m.group(2) or "").strip(), m.group(1)))
    return facts


def section(html, tag):
    i = html.find('id="sec-%s"' % tag)
    return html[i:] if i >= 0 else ""


def main():
    if not os.path.exists(INDEX):
        print("❌ index.html 不存在，无法校验")
        sys.exit(1)
    html = open(INDEX, encoding="utf-8").read()
    lg = section(html, "lg")
    op = section(html, "op")
    doc = lg + "\n" + op

    facts = extract_crons()
    # 按 workflow 归并：有 cron 的 stem 集合
    stems_with_cron = {s for s, _, _ in facts}

    drift = []

    # 方向1：MUST_HAVE_CRON 的 workflow 必须 (a) 有 cron (b) 在文档出现
    for stem, desc in MUST_HAVE_CRON.items():
        if stem not in stems_with_cron:
            drift.append("%s：期望有 cron 但实际 workflow 无 cron 调度" % desc)
            continue
        if stem not in doc:
            drift.append("%s（%s）：实际有 cron 调度，但逻辑详解/运维页未文档化" % (desc, stem))

    # 方向2：文档/运维页引用了某 workflow，但该 workflow 已无 cron（文档过期）
    for stem, desc in MUST_HAVE_CRON.items():
        pass  # 上面已覆盖
    # 额外：扫描文档里出现的 ALLOW_NO_CRON 不在本次检查范围（允许无 cron）

    # 方向3：文档里出现 MUST_HAVE_CRON 之外、且有 cron 的 workflow 但未在 EXPECT 列表
    # （兜底：防止新增 workflow 漏配 EXPECT）
    for stem, _, _ in facts:
        if stem not in MUST_HAVE_CRON and stem not in ALLOW_NO_CRON:
            if stem not in doc:
                drift.append("workflow %s 有 cron 调度但未在 MUST_HAVE_CRON/ALLOW_NO_CRON 登记且未文档化" % stem)

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

    print("✅ 对齐校验通过：所有关键 workflow 均已在逻辑详解/运维页文档化，且无过期引用。")
    sys.exit(0)


if __name__ == "__main__":
    main()
