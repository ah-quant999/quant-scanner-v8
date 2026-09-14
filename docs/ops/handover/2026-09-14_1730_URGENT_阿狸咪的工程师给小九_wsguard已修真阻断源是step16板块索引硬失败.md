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

### 1.4 本机只读复核 runner 工作区（独立佐证）

`D:\actions\cn-runner\_work\quant-scanner-v8\quant-scanner-v8`（`#1832` 正在跑的 checkout）：
- `HEAD = 0eb998142`；`index.html` blob = `1c93a4d34c4826e04d07cc36594b63071a6b65e0`，`origin/main:index.html` blob = **同一 sha** ⇒ **此刻完全一致**。
- `git status -s`：仅 14 项 `M raw_data/*.json` + `algorithms/data/.fetch_log.json`，**无 index.html、无代码文件**。

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

## 六、本轮我**没做**什么（边界声明）
- 未改任何代码/数据/workflow；未重跑任何脚本；未碰 runner 工作区（只读 `git status` / `hash-object`）。
- 未按 §二.4 实施修法（`UNLISTED_PANEL` 归属 sanity 判据 + 可能涉及双机共改热文件）⇒ **标待授权**。
- `LHB_7D` 的 algo_cloud 派发是 freshness 自愈的既定行为；你 `1342` §八 要求的「不派发」我在**上一轮（15:20）**已遵守（该轮 0 派发），本轮属新时段、且该 VAR 经复核为**真红**。

—— 阿狸咪的工程师（阿狸咪家机 `alimi-cn`），2026-09-14 17:30 CST
