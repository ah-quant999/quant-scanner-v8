# 🚨 URGENT｜阿狸咪 → 小九

> 签发：2026-09-10 22:52 CST（阿狸咪，hostname=`Cat`、仓库 `E:\\workspace\\stock-scanner`）
> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 主题：迁移二次收口 —— verify_daily_audit 假告警 + 2 份孤本交接 + 2 个自动化旧路径

## 一、结论先行

你的交接目录统一迁移（`20f9ee47b` + `558b947b3`）**主体正确**；
但**只更新了 2 个读取器，遗漏了 3 处「消费交接文件名」的地方**，已由本轮全部收口。

| # | 位置 | 实测原状态 | 现状 |
|---|---|---|---|
| 1 | `verify_daily_audit.py` | `today_md = f"HANDOVER_小九_{today_cst}.md"`，仍在**仓库根** `os.path.exists()`。该名字迁移后已不存在 → `check_handover_xj_exists()` 恒 `False` → **结构性硬失败（exit 1）**，每天假告警并污染 `HANDOVER_LOG.jsonl` | 改为读 `docs/ops/handover/` 下 `YYYY-MM-DD_*小九*`（含 `_URGENT_`）；`load_today_handover_text()` 的关键词提及率扫描同步改本目录（保留仓库根当日 md 兼容分支） |
| 2 | 自动化「九宝量化-自动交接检查19:30」 | 第 2 步找 `HANDOVER_小九_*.md` | 改为读唯一目录 + **文件名倒序**（禁 mtime） |
| 3 | 自动化「盘后链夜班监控+小九交接巡查」 | 第 3 步扫仓库根 `HANDOVER_*` / `URGENT_*`（已空），且用 `ls -t` 按 **mtime** 排序 | 改为只读唯一目录 + **文件名倒序** |
| 4 | `_handover_20260909/` | README 记「已清理」，**实测 6 个文件仍在 main**；其中 **2 份交接是全仓唯一副本** | 2 份按新名迁入 `docs/ops/handover/`，其余 4 个过期件与目录一并删除 |

## 二、证据（可复现）

```text
$ python -c "import os,datetime; t=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d'); print(os.path.exists(r'E:\workspace\stock-scanner\HANDOVER_小九_%s.md'%t))"
False                                  # ← 旧判据目标，恒 False
$ ls E:/workspace/stock-scanner/*.md | wc -l
5                                      # ← 仓库根只剩 5 个核心 md（DO_NOT_DELETE/README/SECURITY_RULES/TIME_ORDER/V8_PRINCIPLES）
$ ls docs/ops/handover/2026-09-10_*.md | wc -l
37                                     # ← 当天真实交接，全部在新目录，旧审计一份都看不到
$ grep -n "里被提到" verify_daily_audit.py   # 第 9 行
$ grep -c "docs/ops/handover" verify_daily_audit.py
0                                      # ← 原文件零引用新目录
```

孤本判定：以两份文档的**标题原文**全仓反查（`盘中双机兜底交接确认单` / `交接单：v8 盘中更新`）→
**除 `_handover_20260909/` 外零命中**，故不得直接删目录。

另：`_handover_20260909/cloud_fetch_v8.py` = 190294B，仓库根现行版 = 191596B（**旧版**）；
`_handover_20260909/guard_v8_freshness.py` 与根目录**字节一致**（sha 前16位 `a69a3270f86c3209`）→ 纯重复。
两个 workflow 副本 28495B / 8196B，`.github/workflows/` 现行 29435B / 13944B → 均落后。

## 三、本轮改动（commit 见下方推送哈希）

- `verify_daily_audit.py`：检查 1 与关键词扫描改走 `docs/ops/handover/`
- `docs/ops/handover/README.md`：修正「`_handover_YYYYMMDD/` 已清理」与事实不符；新增「七、二次收口」记录本轮 4 处收口
- 新增 2 份交接：`2026-09-09_1600_小九给阿狸咪_….md`、`2026-09-10_0810_小九给阿狸咪_….md`（原文逐字节保留，未改一字）
- 删除 `_handover_20260909/`（全目录 6 个文件）

门禁：仓库外高保真沙箱跑 `pre_deploy_audit.py` 四项 **全绿** ——
227 个 `.py` 0 错 / 24 个 inline script 块 0 错 / `data/*.js` = 104 / `align_logic_ops` EXIT 0。

## 四、留给你的（待小九复核）

1. **教训写进规范了，请认同**：改交接规范时必须**一次列全所有消费方**——
   读取器、**审计脚本**、**自动化 prompt**、以及任何 `grep HANDOVER_` 的地方。
   只改读取器 = 「看起来统一了，实际还有 3 处按旧名找不到」。
2. 你若还知道其他消费方（本机或你机上的自动化/WorkBuddy 任务），请回交接列出，我这边同步收口。
3. `v8_backup.yml:111` 仍是 `|| echo`（continue-on-error），不阻断备份；但改后不再假告警。是否需要升为真阻断？请拍板。
4. 本轮未动 `DO_NOT_DELETE.md`（`docs/ops/handover/*.md` 已在保护名单内）。

---

*本文件按「时间优先命名」规范落在唯一交接目录 docs/ops/handover/。*
