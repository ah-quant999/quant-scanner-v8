# 交接件 · 阿狸咪的工程师 → 小九的工程师

- **时间**：2026-09-20 21:29（北京时间）
- **发件**：阿狸咪的工程师（家机 `alimi-cn` / hostname `Cat`）
- **收件**：小九的工程师（单位机 `lemoncat-cn`）
- **仓库**：`ah-quant999/quant-scanner-v8` @ main
- **主题**：家机跟随者治理落地 · 存量 CRLF blob 归一 + index 标记清单解除 deploy 阻断 + pre-push 防覆盖闸门入库

---

## 一、结论速览

| # | 事项 | 结果 | 提交 |
|---|---|---|---|
| ① | 家机树归一为**纯跟随者** | 领先/落后 **0/0**，脏文件 **18~19 → 0**，`git rebase` 由报错 → `up to date` | （树状态，无提交） |
| ② | 🔴 **真根因根治**：存量 CRLF blob 与 `.gitattributes` 矛盾 | 20 个文件 blob CRLF→LF（内容零变更），提交经 API 净室推送 | `0730000d1a64` |
| ③ | index 核心标记守卫**解除 deploy 阻断** | `[10/10]` 由 3 条缺失 → **32/32 全绿**，门禁 10/10 | `66b3d1208ee0` |
| ④ | `pre-push` 防覆盖闸门**入库** | 家机本地拦截非快进/强推（含 `--force`），已实测 | `0a01645d3216` |

---

## 二、②是真根因（与你的推边界 fix 互补，请务必对齐）

**机制**：① 本机脚本 `open(...,"w",encoding="utf-8")` 在 Windows 写 CRLF；② `api_push_raw.py` 二进制读 + Git Data API 直推 ⇒ **绕过 `.gitattributes` 归一化** ⇒ CRLF 进 blob；③ 而属性声明 `data/*.js`、`raw_data/*.json` 为 `text eol=lf` ⇒ git 把工作文件按 clean filter 转 LF 后与 **CRLF blob** 比 ⇒ **永远不等 ⇒ 工作树永远「已修改」**。

**后果链**：树恒脏 → `v8_health_check._heal_local_sync`「脏则跳过自动对齐」被**永久触发** → 家机永不 ff 对齐（越落越远）；CI 侧同源，即你 09-20 实证的「**9 条带 rebase 的推链周期性假失败、exit 128**」。

**量化**（`data/`+`raw_data/` 共 5121 个跟踪文件）
- blob 为 LF：5072
- blob 含 CRLF 且**被 `eol=lf` 覆盖**：**20 个 ← 真·永久脏，已归一**
- blob 含 CRLF 但**未被规则覆盖**（`raw_data/history/*`、`code_audit.log`、`data/FOUR_VOLUME_BACKTEST.json`）：29 个，现状无害（autocrlf 启发式下不显脏），暂不动

**对照实测**

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 脏文件数 | 18~19（reset 后数秒即复脏） | **0** |
| `git status --porcelain` | 非空 | **空** |
| `git rebase --autostash` | `error: cannot rebase: You have unstaged changes.` | **`Current branch main is up to date.`** |

> **与你的 fix 的关系**：你在**推送边界**加 `fold_eol()`（`api_push_raw.py` + 真源 `scripts/normalize_eol.py`）防**新增**；本轮清的是**修复前入库的存量**。二者缺一，症状都会残留 ⇒ 现已闭环。

---

## 三、③为何要动 index 标记清单（不是覆盖事故）

门禁 `[10/10]` 报 3/35 缺失：`window.__renderFactorLab`、`已否决 · 全市场画像因子`、`flBtSlot`。

逐条查证为**有意删除**（非落后基线覆盖）：
- `0d3482be4`「🧹 删 `__renderFactorLab` 死代码（因子卡去两步后容器已删，函数恒早退）」
- `acc01f49c`「删除「已否决·全市场画像因子」卡 + 因子计算卡去两步只留第一步（Git Data API 净室推送）[小九]」

⇒ 按清单自身**维护纪律 2**「有意删除功能 → 必须同步删除对应行」删行 + 留痕注释（含上述两条 sha 证据）。**删后 `[10/10] 32/32 全部在位`，deploy 解除阻断。**

---

## 四、④闸门说明（对你零影响，但请知悉）

- 路径：`.githooks/pre-push`（**入库**）。真钩子目录由 `core.hooksPath=.githooks` 决定——⚠️ 不是 `.git/hooks/`（我最初装错位置，实测真实推送根本没被读取，已纠正）。
- 判据：**不依赖 stdin**（实测非快进场景 git 传空 stdin，靠解析 stdin 会漏掉最危险的覆盖场景），改为状态直查——推 main 且「远端 main 非本地 main 祖先」⇒ 拦（含 `--force`）；快进/非 main ⇒ 放行。
- **主机感知**：仅家机有标记 `~/.workbuddy/v8_home_block_push` 时生效；**你机无标记 ⇒ 行为与装前完全一致**，不会误拦你的推送。
- 实测：真实 `git push origin main` 在**触网前**被拦，`exit=1`。
- `scripts/install_git_hooks.py` 已扩为「装双钩子 + 统一 chmod 0755」（幂等）。

**不受影响**：心跳/数据走 Contents API（`alimi_heartbeat` / `api_push_*`）不触发；`deploy_v8.py`/`guard_v8.py` 在临时克隆推送；云端 CI 不加载该钩子（`core.hooksPath` 是本地 `.git/config`，不入库）。

---

## 五、改后三件套

### ① 时窗矩阵（cron ↔ 双机任务）

**本轮无任何 cron / automation / workflow 调度变更**，逐条对表结论：

| 时间 | 任务 | 执行机 | 前端 | 本轮影响 |
|---|---|---|---|---|
| 7:45–17:45 | 算法链/盘中腿 | 小九（工作日独家） | — | 无 |
| 18:00–次日7:30 + 周末 | 夜班/周末腿 | 阿狸咪 | — | 无 |
| 每 2h `:41` | 家机反向心跳上报 | 阿狸咪 | 运维页心跳卡 | 无（走 Contents API） |
| 7:30 / 19:30 | 自动读交接 | 阿狸咪 | — | 无 |
| 23:00 / 23:30 | 垃圾清理 / 轻量审计 | 阿狸咪 | — | 无 |

> 唯一间接影响：③④使**9 条带 rebase 的云端推链**恢复可用（此前因树恒脏被前置条件拒绝）；这属**修复**，非调度变更。

### ② 离线门禁（原始输出摘录）

```
✅ [1/8] py_compile: 198 个 .py 文件 0 错误
✅ [2/8] new Function: 28 个 inline script 块 0 错误
✅ [3/8] data 完整性: data/*.js 数量=113, 全部 > 100B
✅ [4/8] align_logic_ops: EXIT 0
✅ [5/8] workflow YAML: 30 个 workflow 全部有效
✅ [6/8] HTML 数据引用: 179 个本地 script 引用全部存在（4 页）
✅ [7/8] gate 头注一致
✅ [8/8] 心跳产物名一致（HB_ALIMI/HB_XIAOJIU 0 处漂移）
✅ [9/9] 回测口径守卫: entry_mode=next_open cost=0.2 n=46 覆盖=with_kline 686/803 (85.4%)
✅ [10/10] index 核心标记守卫: 32/32 全部在位
🎉 10 项全部通过 → deploy 可继续
```

### ③ 交接件

本档（`docs/ops/handover/2026-09-20_2129_…md`），经 Git Data API 推送。

---

## 六、请九侧动作（3 项）

1. **【关键】复发防线覆盖面对齐**：`fold_eol` 目前确认只在 `api_push_raw.py`。请确认其余 API 推手是否接入——
   `scripts/api_put_file.py`、`cloud_fetch_v8.py`、`guard_v8_freshness.py`、`scripts/*.py`。
   未接入者会继续产出 CRLF blob ⇒ 本症状会复现（工作树再度恒脏）。
2. **【低优先】钩子 mode**：仓内 API 推送工具固定写 `100644`（`pre-commit` 为 `100755`）；安装器会 chmod 0755，Windows 双机无影响。若要求 index 也记 100755，需另补一次提交。
3. **【低优先】29 个未覆盖 CRLF blob**（`raw_data/history/*` 等）：现状无害，若要彻底统一行尾可后续归一。

---

## 七、附：证据与备份（家机侧）

`E:\WorkBuddy交付\v8-家机跟随者治理_20260920\`
- `README_治理报告.md` 完整报告
- `crlf_blob_list.txt`（49 个） / `fix_list.txt`（需修 20 个） / `stage_lf/`（归一副本）
- `drift_18_backup/`（reset 前 18 文件备份 + `_manifest.json`）/ `pre-push.snapshot`

> 无损性证明：治理前 18 个漂移文件已逐项比字节 —— **17/18 去空白后与远端完全一致**，1 个（`hb_xiaojiu.json`）为**更旧副本**（本地 19:43 / 远端 20:46）⇒ **本地独有内容 = 0**，归一可证无损。

---

*本档由 `docs/ops/scripts/new_handover.py` 生成文件名，内容经家机三查（`tasklist` / `update_time` / `FETCH_HEAD` + API 回读）后落笔。*
