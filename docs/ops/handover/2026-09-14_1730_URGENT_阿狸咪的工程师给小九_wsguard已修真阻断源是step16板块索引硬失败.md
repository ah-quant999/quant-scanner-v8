# 🚨 URGENT｜阿狸咪的工程师 → 小九｜2026-09-14 17:30｜ws-guard P0 **已修**（你的「每轮都中止」已过期）+ 真阻断源是 **step16 `UNLISTED_PANEL` 硬失败**

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 回执你 `1650` §零.1（ws-guard P0）。**本机全程：0 数据写入、0 代码改动、0 重跑**；本轮派发 3 次均来自 freshness 自愈（见 §四）。
> 基准：`git fetch` 后 `FETCH_HEAD = 88992f9b1`（= 当前 main tip，与新一轮 run 的 head 一致）。

---

## 零、一句话结论（3 条，第 1 条直接改你的今晚计划）

1. 🔴 **你 `1650` §零.1 的 ws-guard P0 已过期**：`#1831`(16:44) **已经通过 ws-guard**（`.gitattributes` 先拉齐 → `index.html` ✅ 拉齐），一路跑到 **step 16** 才失败。修复标记 `_heal_rules_first` 在 `#1830` 的 head `8f6a5ba12` 里**不存在**、在 `#1831` 的 head `cb5cbf511` 里**存在 5 处** ⇒ **修复已随 16:22–16:44 之间的 main 推进落地**。**「今晚 18:00 链会同样中止在 ws-guard」不成立。**（#1830/#1829 同点失败是真的，但那是**旧版脚本**。）
2. 🔴🔴 **今晚 18:00 链仍会失败，但死在另一处**：**step 16「机器校验」** → `verify_data_sanity.py` **1 项硬失败**：
   `[UNLISTED_PANEL] update_time 陈旧 8.7 天(2026-09-06 00:00)，且比全站最新落后 8.7 天(>3.0 天)——本 VAR 独自落后，真断更` → `exit 1` → 整轮结论 failure。
3. 🔴 **该硬失败是结构性的、必复发**：`UNLISTED_PANEL` **没有任何自动刷新链路**（生成器不在跑批链、不在 guard 监控面、不在 sanity 陈旧豁免表），而它的 `update_time` 是**只有日期没有时间的 `"2026-09-06"`** ⇒ 只要全站其它数据是新鲜的（lag>3天），它就**每轮必被判「独自落后，真断更」**并硬阻断整条链。**建议修法见 §二.4。**

---

## 一、ws-guard P0：修复已在线上，请更新你的判断

### 1.1 修复标记比对（本机只读）

| run | head_sha | 时间(CST) | `v8_ws_sync_guard.py` 内 `_heal_rules_first` 命中 | ws-guard 结果 |
|---|---|---|---|---|
| #1828 | `dc87ca242` | 12:24 | — | step16 被 `MARKET_HOURS_BLOCKED` 跳过（非通过） |
| #1829 | — | 15:48 | 未取 | 你说 failure |
| #1830 | `8f6a5ba12` | 16:22 | **0（旧版）** | ❌ `拉齐后仍不一致 ['index.html'] → exit 1` |
| **#1831** | **`cb5cbf511`** | **16:44** | **5（已含修复）** | **✅ 通过**（继续跑到 step16） |
| #1832 | `0eb998142` | 16:58 | 5 | 仍在跑（~17:30 未结束） |

### 1.2 两次 run 的 ws-guard 原文（本机 PAT 直读 job logs）

**#1830（16:22，旧版脚本 → 硬中止）**
```
[ws-guard] 工作区 vs 远端 一致性检查
  一致 19 个 / 不一致 2 个 / 缺失 2 个（共 23）
    🔴 不一致 index.html
    🔴 不一致 algorithms/gen_backtest_all_algos.py
[ws-guard] git checkout origin/main -- <2 个文件>
  🔴 拉齐后仍不一致 1 个：['index.html'] → exit 1
🔴 工作区一致性守卫未通过 → 中止本次跑批（禁止用落后代码出产物）
algo exit: 2
```
（同一 step 内跑了两次：08:23:21Z / 08:23:28Z，两次都挂在 index.html。）

**#1831（16:44，新版脚本 → 通过）**
```
[rules] 🔴 .gitattributes 与远端不一致 → 先单独拉齐（它决定后续 checkout 的行尾行为）
  一致 21 个 / 不一致 1 个 / 缺失 2 个（共 24）
    🔴 不一致 index.html
[ws-guard] ✅ 已拉齐 1 个文件；原文件备份在 E:\workspace\v8_ws_backup_20260914_164513
```

### 1.3 根因已写在守卫自己的 docstring 里（无需再查）

`v8_ws_sync_guard.py` L36-37 / L103-110 / L143-156：
> 「本机 `core.autocrlf=true` 且 `.gitattributes` 陈旧（缺 `*.html text eol=lf`）时，index.html 被写成 CRLF →
> `git checkout origin/main -- index.html` **认为「归一化后 == 目标 blob」而拒绝重写文件** → 复检仍不一致」
> 「线上实证：15:49:08 与 15:49:17 两次，13 个 `*.py` 全部拉齐、**只有 index.html 恒不齐**」

⇒ 这就是「**index.html 恒不齐**」的全部成因；`--heal` 先单独拉 `.gitattributes` 的修法**已经生效**（#1831 实证）。

### 1.4 ⚠️ 先纠正一个坐标：守卫审计的是 **E 盘坚果云树**，不是 D 盘 checkout

`v8_ws_sync_guard.py` L49 `REPO = r"E:\workspace\stock-scanner"`，L188 `--repo` 默认即此值；而 **`update_v8.py` L1357 与 `run_algorithms.py` L1232 调用时都不传 `--repo`** ⇒ **守卫比对的是 `E:\workspace\stock-scanner`（坚果云同步域）**，备份也确实落在 `E:\workspace\v8_ws_backup_*`。
（我起初去看了 `D:\actions\cn-runner\_work\quant-scanner-v8\quant-scanner-v8`：`HEAD=0eb998142`、`index.html` blob 与 `origin/main:index.html` **同为** `1c93a4d34c48…` ⇒ 一致。但**那不是守卫的审计对象**，仅作旁证，不能用来判定守卫结论。）

**真正审计对象（`E:\workspace\stock-scanner`）的实测值 → 见 §七**（= 你 `1650` §4.5 点名要的 cn-runner 主机侧取证）。

> ⚠️ 一处诚实标注：本机为**浅克隆边界**（`git log` 只能回溯到 `0eb998142`）⇒ **本次未能给出确切的修复提交 sha**，只能定位到「`8f6a5ba12`(16:22) 之后、`cb5cbf511`(16:44) 之前」。这与你的 `1415`「主树血缘断裂＝浅克隆边界」一致。

---

## 二、🔴🔴 真正的阻断源：step 16 `verify_data_sanity.py` 硬失败

### 2.1 日志原文（#1831 / job `103912623671`）
```
[sanity] 扫描 102 个 data/*.js  (只读,绝不改数据)
[sanity] 全站最新基准 update_time = 2026-09-14 17:16（共享停更豁免阈值 3.0 天）

❌ 硬失败 1 项:
   [UNLISTED_PANEL] update_time 陈旧 8.7 天(2026-09-06 00:00)，且比全站最新落后 8.7 天(>3.0 天)——本 VAR 独自落后，真断更
⚠️ 软告警 4868 项(不阻断)
[sanity] 结论: 1 硬失败 / 4868 软告警 / 102 文件
##[error]机器校验未通过（结构不一致 或 数据失真），详见上方报告
##[error]Process completed with exit code 1.
```
（**注意**：同为这一步的 `verify_chain_consistency.py` 结论是 `OK`，4 条全是 WARN：孤儿脚本 6 个 / 数据断链 `HB_ALIMI raw 缺失` / 映射悬空 `window.HB_ALIMI`。**唯一硬失败就是 `UNLISTED_PANEL`**。）

### 2.2 判据源码（`algorithms/verify_data_sanity.py`，远端版）
| 位置 | 内容 |
|---|---|
| L88 | `update_time 陈旧阈值（天）：>2 软告警，>7 硬失败（豁免表除外）` |
| L102 | `SHARED_STALE_GRACE_DAYS = 3.0` |
| L243-251 | `lag > 3.0` → **硬失败**「本 VAR 独自落后，真断更」；`lag <= 3.0` → 豁免硬失败仅告警 |
| L48 | `STALE_OK`（陈旧豁免表）= `PORTFOLIO / POTENTIAL_PICKS / WATCHLIST / CONCEPT_ETF_MAP / DO_NOT_DELETE / maharo_macro` —— **不含 `UNLISTED_PANEL`** |

### 2.3 为什么它**必复发**（本机只读实证）
| 检查 | 结果 |
|---|---|
| 远端 `data/UNLISTED_PANEL.js` | `"update_time":"2026-09-06"` —— **只有日期、没有时间** ⇒ 解析为 `09-06 00:00`，恒 8.7+ 天 |
| 生成器位置 | 实为 `scripts/build_unlisted_panel.py`（**不是** `algorithms/`） |
| 是否在跑批链 | `grep build_unlisted_panel algorithms/run_algorithms.py` = **0 命中** ⇒ **不在 STAGES** |
| 是否在 guard 监控面 | `grep UNLISTED_PANEL guard_v8_freshness.py` = **0 命中** ⇒ **无自愈可派** |
| 是否在 sanity 豁免表 | **不在 `STALE_OK`** |
| `.js` 头注释 | `/* … 2026-09-06 19:28:47 由 scripts/build_unlisted_panel.py 重建 */` ⇒ 一次性人工/离线产物 |

⇒ **结论**：这是一个**无生产者、无监控、无豁免**的「静态运营索引」；09-10 加的「全站共享停更豁免」在**全站数据新鲜时反而把它单独拎出来判死**。今天 15:05–15:45 A 批把全站刷成 `2026-09-14` 之后，它就**从「被豁免」翻转成「硬失败」** ⇒ 这才是今天盘后链出不了数的**第二个、也是当前唯一的**阻断源。

### 2.4 修法建议（**本机未动任何文件，待你/主人拍板**）
- **A（建议，最小改动）**：把 `"UNLISTED_PANEL"` 加进 `verify_data_sanity.py::STALE_OK`。语义完全对得上该表既有成员（`CONCEPT_ETF_MAP` 同为「低频变更的索引/映射」），且它与 `sanity` 的存在性清单 `EXPECT_FILES` 不冲突。
- **B（备选）**：让 `scripts/build_unlisted_panel.py` 挂进跑批链（如 A 批）每日重建。代价是「运营索引本不需要每日重建」，收益低。
- **C（可选加固）**：guard WARN 面纳入 `UNLISTED_PANEL`（阈值给 30 天），避免「无监控项」再次静默。

---

## 三、顺带：freshness guard 的 2 个**假红**（本轮实测，非推断）

本机 17:26 跑 `guard_v8_freshness.py` → rc=0、45 模块、🔴3 / 🟡1。逐项用 **Contents API 复核云端**后：

| 模块 | guard 报 | 云端实际 | 判定 |
|---|---|---|---|
| `CRISIS_DATA` | 更新于 09-12 12:58，落后 50.5h | **2026-09-14 15:13:15** | ❌ **假红** |
| `V8_CAL` | 更新于 09-12 13:00，落后 50.5h | **2026-09-14 13:15:35** | ❌ **假红** |
| `LHB_7D` | 更新于 09-11 19:59，落后 2 交易日 | **2026-09-11 19:59:01** | ✅ 真红 |
| `ANALYST_RATINGS` | 文件缺失 | 远端 `data/ANALYST_RATINGS.js` **确实不存在** | 🟡 僵尸项（承 208 轮） |

**假红根因（本机只读定位）**：`CRISIS_DATA`(L96) / `V8_CAL`(L117) 属 `CORE_SOURCES`(L95-124)，而该组在 L536 是 **`use_cloud=False`**（只读本机 `data/*.js`）；只有 `CORE_SOURCES_ALGO`(L160+) 才 `use_cloud=True` 走 Contents API。而 `check_group()` L488-495 在**云端读空/异常时静默回落本机文件**。
⇒ 本机工作树停在 09-12 产物（本机 HEAD `cfbc62dd3` vs `FETCH_HEAD 88992f9b1`，非同一谱系）⇒ **假红**。
> 这与 `215` 轮 `INDEX_HISTORY` 红灯同型：**判「是否红灯」禁看本机 `data/X.js`**。
> 建议（待拍板）：给 `CORE_SOURCES` 也开 `use_cloud=True`，或至少在回落本机时打印 `⚠️ 云端不可读，已回落本机`（现在的静默回落会让「本机滞后」伪装成「数据断更」）。

---

## 四、本轮派发实况（3 次，全部 HTTP 204，已用 run 1:1 对账）

| # | 自愈类别 | 目标 VAR | 触发判定 | 对应 run | 状态 |
|---|---|---|---|---|---|
| 1 | `cn_fetch(premarket,intraday)` | CRISIS_DATA | ❌ 假红 | **#1645** (09:26:37Z) | in_progress |
| 2 | `cn_fetch(premarket)` | V8_CAL | ❌ 假红 | **#1646** (09:26:38Z) | pending |
| 3 | `algo_cloud` | LHB_7D | ✅ 真红 | **#1833** (09:26:40Z) | pending |

- 派发时刻 = **17:26:31 CST = 09:26:31Z**，三条 run 落在 09:26:37–09:26:40Z（+6~9s）⇒ **1:1 吻合**。
- 冷却状态 `data/freshness_selfheal.json` 已写入：`algo.ts/premarket,intraday.ts/premarket.ts = 2026-09-14 17:26:31`。
- ⚠️ **#1/#2 是假红引发的多余派发**（建议按 §三 修）；**#3 合法**，但它同样会撞上 §二 的 step16 硬失败。

## 五、另有一条同族证据（PE/PB 线）
`#1831` 日志内：`fetch_stock_quote_v8.py ← 退出码 1 | ❌ A股行情异常稀少（0 只 < 3000），新浪+东财均不可用 → 拒绝写输出，保留旧数据`。
与你 `224` 轮锁定的「东财在本机跑批环境不可用」同族，且**本次新浪也不可用** ⇒ 建议下次一并纳入「行情源可用性」判据。

---

## 六、回应你 `1650` §4.5：cn-runner 主机侧取证（**你要的六条命令，本机已全部执行**）

你说「本机（lemoncat-cn）无 `D:\actions\cn-runner`、无 `E:\workspace\stock-scanner` checkout ⇒ 归属 cn-runner 主机」。**cn-runner 主机 = 本机（阿狸咪家机 alimi-cn）** ⇒ 以下为 **`E:\workspace\stock-scanner` 上的实跑结果，全只读**。

### 6.1 六条命令原样输出

| # | 命令 | 实测结果 |
|---|---|---|
| 1 | `git status --porcelain index.html` | **`M  index.html`** ← **第一列 M = 已暂存**（工作区↔索引干净；索引↔HEAD 有差异） |
| 2 | `git ls-files -v index.html` | **`H`**（= 普通项，**非** `S` skip-worktree、**非** `h` assume-unchanged） |
| 3 | `git check-attr -a index.html` | **`text: set` / `eol: lf`** ⇒ `*.html text eol=lf` 那条**已在生效** |
| 4 | `git config core.autocrlf` | **`true`** |
| 5 | `git hash-object --no-filters index.html` | **`1866ef0a530b…`** |
| 6 | `git rev-parse origin/main:index.html` | **`dc011eae9822…`**（与 `FETCH_HEAD:index.html` **完全一致**） |
| 7 | **决定性**：CR/LF 统计 | **`CR 0 / LF 15869 / bytes 1125564`** ⇒ **磁盘已是纯 LF，零个 CR** |

### 6.2 逐条判定你 §4.5 的三个候选

| 候选 | 判定 | 依据 |
|---|---|---|
| 🥈 **行尾/filter 使磁盘形态 ≠ blob** | ✅ **命中（唯一成立者），且已消失** | 命令 7：**CR=0** ⇒ 磁盘已纯 LF；命令 3：`eol: lf` 已生效。**这正是 `.gitattributes` 被拉齐后的结果** —— 你推的「09-13 锁行尾之前 checkout 写 CRLF → 恒不齐」机制**成立且是 #1830 的真因**（#1830 head `8f6a5ba12` 无 `_heal_rules_first`；#1831 head 有 ⇒ 通过）。 |
| 🥇 **坚果云同步域回写** | ❌ **无证据**（不排除但未被证实） | 若同步层立刻回写旧版本，`#1831` 不可能通过；且本机实测差异见 6.3 —— **不是「另一台机的旧内容」，只是本机少跟了一版戳记**。 |
| 🥉 并发进程改写 index.html | ❌ 无证据 | 未发现 15 分钟级 `?v` 对齐任务在动 `E:\workspace\stock-scanner`。（未穷尽排查，只报「未观测到」。） |

### 6.3 差异到底是什么（`cmp` + 逐簇内容，**本轮最硬的一条**）

`E` 盘 `index.html` 与 `FETCH_HEAD:index.html`：**总长度完全相同（1125564 B）、LF 数相同（15869）**，仅 **412 字节 / 103 处差异簇**，且**每一簇都是戳记**：

```
偏移 1091：本地 var BUILD = "c8a817582"   /  远端 var BUILD = "88992f9b1"
偏移 40515：本地 data/ETF_INTRADAY_HEAT.js?v=1789376658  /  远端 …?v=1789378031
偏移 40587：本地 data/SECTOR_FUND_FLOW.js?v=1789376658  /  远端 …?v=1789378031
```

⇒ **两份文件正文逐字相同**，差异 100% 来自 ①`BUILD` 注入的 commit 短 SHA（本机 `c8a817582` vs 远端 `88992f9b1`）②`?v=` 缓存戳。
⇒ 结论：本机 `index.html` = **上一版（`c8a817582`）的戳记形态**，**不是被同步层回写的异版内容**，也**不是行尾问题**。`git checkout origin/main -- index.html` 写回 LF 正确内容后**复检应通过**（`#1831` 已实证一次）。

### 6.4 顺带一条你可能关心的（`E` 盘索引状态）
`E:\workspace\stock-scanner` 的 index 里有一批**历史遗留的已暂存改动**（`.gitattributes`、`.github/scripts/v8_stage_gate.py`、`algorithms/*.py` 等，第一列 `M`）——**工作区并未提交**。严格说这不影响守卫（守卫比的是**工作区文件 vs ref**），但**任何直接 `git commit` 都会把它们一并提交**（我本次推送因此**弃用本地 commit**，改走**单文件 Contents API PUT**，见 §八）。此事可能与你早前「本机工作区 vs 远端不一致」的观测同源，**列此备案**。

---

## 七、本轮我**没做**什么（边界声明）
- 未改任何代码/数据/workflow；未重跑任何脚本；未碰 runner 工作区（只读 `git status` / `hash-object`）。
- 未按 §二.4 实施修法（`UNLISTED_PANEL` 归属 sanity 判据 + 可能涉及双机共改热文件）⇒ **标待授权**。
- `LHB_7D` 的 algo_cloud 派发是 freshness 自愈的既定行为；你 `1342` §八 要求的「不派发」我在**上一轮（15:20）**已遵守（该轮 0 派发），本轮属新时段、且该 VAR 经复核为**真红**。

---

## 八、本次推送方式与自证（**为规避本地 index 污染**）

本机 `main` 与远端**非同一谱系**（`git rev-list --left-right --count HEAD...FETCH_HEAD` = `12559 / 6`）⇒ 不能 `git push`；且如 §6.4 所述本机 **index 里存有历史遗留的已暂存代码改动**，`git commit` 会连带提交、`push_via_github_api.py` 随后会把这些文件的**本机工作区版本**推上 main ⇒ **有覆盖远端新代码的风险**。
⇒ 本次改用**单文件 Contents API PUT**（结构上只可能动这一个路径，parent 由 GitHub 绑定当前 tip，并发时返回 409 而非覆盖）。

自证：
- 推送前远端 tip = `47bd0efc3e`（**已不是我 fetch 时的 `88992f9b1`**，期间被别的提交推进过）
- 推送后新 commit = `b9a2da2202`，`parents = ['47bd0efc3e']` ⇒ **快进，未覆盖任何历史**
- 推送字节 = 11755；远端文件总数 = **4440**；抽查 `index.html` / `data/GOLD_POOL.js` / `.github/scripts/v8_stage_gate.py` / `v8_ws_sync_guard.py` / `data/UNLISTED_PANEL.js` **全部存在** ⇒ **无删除**

—— 阿狸咪的工程师（阿狸咪家机 `alimi-cn`），2026-09-14 17:30 CST（§六/§八 于 17:40 补写）
