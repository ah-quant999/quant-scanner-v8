# -*- coding: utf-8 -*-
"""verify_ima_sync.py — ima 强势股同步链的**产物形状断言**（杜绝「旧脚本假成功」）

━━━ 为什么需要这一步（真因，有据可查）━━━

2026-09-17 21:53 新版 `fetch_ima_strong_stock.py` 上线（含 `data_date` / `source_stale`
/ `stale_days` / `source_updated_at` / `source_title` 五字段 + 空单元格折叠修复），
而 `v8_ima_strong_stock.yml` 的 cron 是 CST **15:45** —— 当天 15:45 早已用**旧脚本**跑完。

⇒ 后果（实测，非推测）：
  1. 线上产物顶层只有 6 个键，**五字段一次都没被写出过**；
     前端红胶囊判据 `if(D.source_stale && D.data_date)` 恒假 ⇒ 源停更 15 天而页面照显「今日」；
  2. 旧解析器把 innerText 里「空单元格占 2 行」的格子拆成 2 个空 token ⇒ 指针卡住，
     六字段塌进 `_parse_missing`，**112 只里 72 只丢了「首次入选日」**（有效仅 40/112）；
     回测侧 `skipped_no_signal_date = 72` 静默丢弃 ⇒ 样本砍 64%，回测**系统性偏乐观**；
  3. **整条链没有任何一步报错**（job 全绿）⇒ 事故潜伏了不知多久。

本脚本把上述三件事变成**硬断言**：形状不对就 fail，并指名原因。

━━━ 断言清单 ━━━
  A. 五字段必须存在                    （否则 = 跑的是旧脚本 / checkout 未取最新 main）
  B. `parse_health.no_first_selected` 必须为 0  （否则 = 折叠修复失效或被回退）
  C. `parse_health.field_missing_counts` 必须为空（否则 = 解析串位复发）
  D. `source_stale` / `stale_days` 只告警不失败（源侧停更是外部原因，不该红，但必须吼）

用法：python verify_ima_sync.py    （退出码 0 = 通过；1 = 断言失败）
"""
import io
import json
import os
import sys

PATH = os.path.join("raw_data", "ima_strong_stock.json")
REQUIRED = ["data_date", "source_stale", "stale_days", "source_updated_at", "source_title"]

# 允许「本机无产物」时静默跳过（本地开发/审计场景不必红）
if not os.path.exists(PATH):
    print("⚠️ 未找到 %s —— 跳过断言（仅 CI 产物链需要）" % PATH)
    sys.exit(0)

try:
    j = json.load(io.open(PATH, encoding="utf-8"))
except Exception as e:
    print("::error::产物无法解析：%s" % e)
    sys.exit(1)

fails = []

# ── A. 五字段 ──
miss = [k for k in REQUIRED if k not in j]
if miss:
    fails.append(
        "产物缺字段 %s ⇒ 跑的是**旧版脚本**（checkout 未取到最新 main / reset 步被跳过）。"
        "修复：确认「同步远端最新 main」步成功，且 fetch_ima_strong_stock.py 为 origin/main 版。"
        % miss)

# ── B / C. 解析健康度 ──
ph = j.get("parse_health") or {}
nos = ph.get("no_first_selected")
fmc = ph.get("field_missing_counts") or {}
if not ph:
    fails.append("产物缺 `parse_health` ⇒ 无法判定解析健康度（旧脚本特征）")
else:
    if nos:
        fails.append(
            "`no_first_selected=%s`（应恒为 0）⇒ **空单元格折叠修复失效或被回退**。"
            "下游影响：这 %s 只无法定位信号日，回测会静默丢弃，样本从 112 掉到 %s，"
            "回测结果系统性偏乐观。" % (nos, nos, ph.get("total", 0) - nos))
    if fmc:
        fails.append(
            "`field_missing_counts` 非空 %s ⇒ **解析串位复发**（检查 innerText 空单元格折叠）。" % fmc)

# ── 输出 ──
print("=" * 78)
print("ima 同步链产物断言：%s" % PATH)
print("=" * 78)
print("  顶层键      : %s" % ", ".join(sorted(j.keys())))
print("  data_date   : %s" % j.get("data_date"))
print("  stale_days  : %s" % j.get("stale_days"))
print("  source_stale: %s" % j.get("source_stale"))
print("  源自述标题  : %s" % (j.get("source_title") or "(空)"))
print("  源自述更新  : %s" % (j.get("source_updated_at") or "(空)"))
print("  解析健康度  : 总 %s 只 · 无首次入选日 %s · 字段缺失 %s"
      % (ph.get("total"), nos, fmc))

if fails:
    print()
    for f in fails:
        print("::error::%s" % f)
    print("\n❌ 断言失败 %d 项 —— 产物形状不是新版，CI 必须红（否则又是假成功）" % len(fails))
    sys.exit(1)

# ── D. 源停更：告警但不失败（外部原因，不该让 job 红；但必须可见）──
if j.get("source_stale") is True:
    print()
    print("::warning::源侧停更：data_date=%s（已 %s 天无新数据）。本次抓取成功但内容与上一期相同 ⇒ "
          "最终推荐的「高手共振」已被消费端熔断跳过（不参与加分）。这是**外部源问题**，非本站故障。"
          % (j.get("data_date"), j.get("stale_days")))
    print("⛔ 源停更告警（不失败）")
    sys.exit(0)

print("\n✅ 断言通过：产物为新版形状，源数据日 %s（新鲜）" % j.get("data_date"))
sys.exit(0)
