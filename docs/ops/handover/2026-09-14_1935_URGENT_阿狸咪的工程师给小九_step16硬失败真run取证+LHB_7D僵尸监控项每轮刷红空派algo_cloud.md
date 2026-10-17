# 🚨 URGENT｜阿狸咪的工程师 → 小九｜2026-09-14 19:35｜step16 硬失败「真 run 日志取证」+ 新僵尸项 `LHB_7D`：每轮刷红并空派 algo_cloud

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 回你 `1810` 之前的链路判断。**本机全程：0 数据写入、0 代码改动、0 重跑**；本轮派发 1 次，来源 = freshness 自愈（见 §三）。
> 基准：`git fetch` 后 `FETCH_HEAD = ef84216f0`（= 当前 main tip，也与本轮派发的 run head 一致）。

---

## 零、一句话结论（3 条）

1. ✅ **你 `1730` 的诊断（由我方发出）已被真 run 日志独立确认**：`#34827982485`（17:26:40 CST 派发，runner `alimi-cn`）**确实死在 step 16「机器校验」**，硬失败原文 = `[UNLISTED_PANEL] update_time 陈旧 8.8 天(2026-09-06 00:00)…本 VAR 独自落后，真断更`，`1 硬失败 / 4868 软告警` → `##[error]机器校验未通过`。**不是推断，是日志原文。**
2. 🔴 **新发现（可执行、成本极低）：`LHB_7D` 已是「僵尸 CORE 监控项」** —— 生成器 `gen_lhb_7d.py` **09-13 已主动停跑**，但 `guard_v8_freshness.py` **仍把它挂在 `CORE_SOURCES_ALGO`（24h 阈值）+ `ALGO_VARS`** ⇒ **每轮必判红 + 每轮必自愈派 algo_cloud**，而自愈**结构上永远治不好**（没有生产者在跑）⇒ **无限刷红灯 + 无谓 run 风暴燃料**。
3. **建议修法（1 行级，待你/主人拍板）**：把 `LHB_7D` 从 `CORE_SOURCES_ALGO` + `ALGO_VARS` 摘除（或迁入该文件**已经预留好的** `FROZEN_SOURCES` 空字典）；顺带把 `ANALYST_RATINGS` 从 WARN 清单摘掉（同一族僵尸项，每轮固定黄灯）。

---

## 一、step16 硬失败：真 run 日志取证（我方 17:30 判断的独立复核）

### 1.1 run 元数据

| 项 | 值 |
|---|---|
| run id | `34827982485` |
| 派发时间 | `2026-09-14T09:26:40Z` = **17:26:40 CST**（workflow_dispatch） |
| head_sha | `88992f9b1` |
| runner | `alimi-cn`（本机） |
| 结论 | **failure** |
| 失败步 | **step 16「🛡 机器校验（结构一致性 + 数据失真体检）」**（其余步骤无 failure） |
| 结束时刻 | `2026-09-14T10:35:52Z` = **18:35:52 CST**（全链约 69 min） |

### 1.2 step16 日志原文（本机 PAT 直读 `/actions/jobs/103933098064/logs`）

```
[sanity] 扫描 102 个 data/*.js  (只读,绝不改数据)
[sanity] 全站最新基准 update_time = 2026-09-14 18:34（共享停更豁免阈值 3.0 天）
    [UNLISTED_PANEL] update_time 陈旧 8.8 天(2026-09-06 00:00)，且比全站最新落后 8.8 天(>3.0 天)——本 VAR 独自落后，真断更
[sanity] 结论: 1 硬失败 / 4868 软告警 / 102 文件
##[error]机器校验未通过（结构不一致 或 数据失真），详见上方报告
```

⇒ 与我方 `1730` 交接 §零.2 的判断**逐字一致**，且**多了一条新事实**：本次全站最新基准是 `2026-09-14 18:34`（即链内刚产出的一批），`UNLISTED_PANEL` 停在 `2026-09-06 00:00` ⇒ **只要全站新鲜它就必红**，`UNLISTED_PANEL` 自身无刷新链路（生成器 `scripts/build_unlisted_panel.py` 不在 `run_algorithms.py` STAGES、不在 guard 监控面、不在 `verify_data_sanity.py::STALE_OK` 豁免表）。

---

## 二、🆕 `LHB_7D` = 僵尸 CORE 监控项（本轮新发现，建议优先摘除）

### 2.1 三方证据（全部本轮实测）

| 证据 | 命令/来源 | 结果 |
|---|---|---|
| 生产方**已停跑** | `algorithms/run_algorithms.py` L192-194 / L305-306 / L1278-1283 | 注释「2026-09-13 阿狸咪的工程师：`gen_lhb_7d.py` **已停跑**」+ `# step_gen_lhb_7d()` 已注释；ORDER/STAGES 均已摘除 |
| 前端**零消费** | `index.html` L565 | `<!-- 2026-08-31 轻量化：data/LHB_7D.js（5.9 KB）前端零引用，停止注入 -->`（`grep -c LHB_7D index.html` = **1**，仅该注释） |
| 云端产物**已冻结** | Contents API `data/LHB_7D.js` + `raw_data/lhb_7d.json` | `update_time = 2026-09-11 19:59:01`（**落后 2 个交易日**） |
| 监控方**仍在挂** | `guard_v8_freshness.py` **L167**（`CORE_SOURCES_ALGO`，阈值 24h）+ **L207**（`ALGO_VARS`） | 仍判 CORE + 仍参与自愈派发 |

### 2.2 后果（这就是本轮红灯的成因）

```
🔴 核心数据过期（1 个，云端抓取异常）:
  - LHB_7D: 更新于 09-11 19:59，落后 2 个交易日（阈值 1）
🩹 自愈派发（1 个类别需刷新）:
  [自愈✓] 派发 algo_cloud 刷新 LHB_7D（HTTP 204）
```

- **红灯永远不会消**：没有生产者在跑 ⇒ `LHB_7D.js` 永远停在 09-11 ⇒ 每轮 guard 都判红。
- **派发永远无效且重复**：30 min 冷却一过就再派一次 `algo_cloud`；本机 listener 与云端 `v8_health_patrol.yml` 两处 guard 各判各的 ⇒ 与历史上 `INDEX_HISTORY` 的「每轮双派、必有一个被 cancelled」完全同型（本次已见 `34832585102` 与 `34838989193` 两条同并发组）。
- **顺带污染**：`data/freshness_selfheal.json` 的 `algo.ts/vars` 被 `LHB_7D` 占位 ⇒ 真正需要自愈的 ALGO 类模块可能被冷却额度挤掉。

### 2.3 建议修法（本机未改，待拍板）

| 方案 | 动作 | 评价 |
|---|---|---|
| **A（推荐）** | `guard_v8_freshness.py`：`LHB_7D` 移出 `CORE_SOURCES_ALGO`（L167）与 `ALGO_VARS`（L207），迁入 **文件里已预留的 `FROZEN_SOURCES`（L173-176，当前空 dict）** | 一行级改动，语义正确（「无云端生产者的冻结快照」正是它的定义），且**保留可回滚**（函数体仍在） |
| B | 给 `verify_data_sanity.py::STALE_OK` 加 `LHB_7D` | 只治「红」，不治「空派」 |
| **C（一并建议）** | `ANALYST_RATINGS` 从 guard 的 WARN 清单摘除（`update_v8.py` L75-77/L180 早已停止发布，`index.html` 无 script 标签） | 消除每轮固定黄灯，同族僵尸项 |

> ⚠️ 若后续要恢复 LHB 7 日累计：`gen_lhb_7d.py` + `step_gen_lhb_7d()` 函数体**都还在**（仅注释掉调用），回滚即可。

---

## 三、本轮派发、反证与队列实况

### 3.1 本轮派发（1 次，1:1 对账）

| 项 | 值 |
|---|---|
| 派发时刻 | **19:35:30 CST**（= `11:35:30Z`） |
| 触发 | freshness 自愈（`vars = ["LHB_7D"]`，写入 `data/freshness_selfheal.json` → `algo.ts = 2026-09-14 19:35:30`） |
| 目标 | `v8_algo_cloud.yml`（HTTP 204） |
| 对应 run | **`34838989193`**，created `2026-09-14T11:35:35Z` = **19:35:35 CST**（+5s），`pending`，head `ef84216f0` |

### 3.2 队列实况

| run | created (CST) | 状态 | runner | 备注 |
|---|---|---|---|---|
| `34838989193` | 19:35:35 | **pending** | — | **本轮自愈派发** |
| `34832585102` | 18:19:20 | **in_progress** | `alimi-cn` | 非本机派发；job 自 `18:36:36 CST` 起跑 **step9 盘后算法链**，约 59 min，属正常区间 |
| `34827982485` | 17:26:40 | failure | `alimi-cn` | 死在 **step16**（见 §一） |
| `34825466543` | 16:58:43 | failure | — | head `0eb998142` |
| `34824262194` | 16:44:32 | failure | — | head `cb5cbf511`（ws-guard **已通过**，死在 step16） |

`cn_fetch_cloud` 本轮**未派发**（guard 无 cn 类红灯）；最近两条 `34827979877` / `34827977702`（均 17:26:37-38 CST，success）来自上一轮自愈。

### 3.3 结论

> **今晚链的走向没有变化**：ws-guard 已通过（你 `1650` 的 P0 已过期，我方 `1730` 已更正），**真阻断源仍是 step16 的 `UNLISTED_PANEL`**。在我方建议被采纳前，**每轮都必然 failure**，且**每轮都会额外空派一次 algo_cloud（LHB_7D）**。

---

## 四、本机本轮动作清单（只读自证）

- `v8_urgent_listener.py` → exit 0；最新 urgent = `2026-09-14_1730_…`（**本机上一轮自写**），**未识别到主机指令**；远端 `*_URGENT_*` 倒序 TOP1 与之一致 ⇒ **无漏读**（`FETCH_HEAD = ef84216f0`，本机 behind = 3）。
- `guard_v8_freshness.py` → rc=0，受检 45 模块，交易日 09-14 15:30；🔴1（`LHB_7D`）/🟡1（`ANALYST_RATINGS`）。
- 派发 **1** 次（algo_cloud），无其它写操作、无数据产出、未改任何仓库文件（除本交接）。
- 旁注：远端 `HANDOVER_2026-09-14_1810_xiaojiu.md`（「暂未上架 → 大盘观察」子TAB）与 `HANDOVER_2026-09-14_1710_…` 已读，命名无 `_URGENT_` ⇒ 不在监听面，**对我方无 action**。

---
*阿狸咪的工程师 · 2026-09-14 19:35 · 家用机 `alimi-cn`*
