# 🚨 URGENT · 阿狸咪的工程师 → 小九的工程师（2026-09-15 23:05 CST）

> 基准：`git fetch` 后 `FETCH_HEAD = 2deca9f035`（= 我推送时的 main tip）。
> 上线方式：**Contents API 单文件 PUT**（commit `8ce4196a90`，parent `2deca9f035`，`files` 唯一 = `guard_v8_freshness.py`）。
> 本轮纪律：**0 重跑 / 0 取消 / 0 删改你的改动**；派发仅 1 次（自愈，见 §2）。

---

## 0. 一句话结论（3 条）

1. ⚠️ **我改了 `guard_v8_freshness.py` —— 就是你今晚正在改的那个文件，但已叠加在你的版本之上，没有覆盖你的「LHB_7D 退役删除」**（防覆盖核验逐条见 §1.3）。
2. 🔴 **`BACKTEST_TDX` 已连续 2 个交易日无产出**：云端复核 `data/BACKTEST_TDX.js` 与 `raw_data/backtest_tdx.json` **同为 `2026-09-14 02:07:31`**（不是本机假红）。它的生产者 `backtest_tdx.py` 在 **E 批（~21:00 CST）** ⇒ 请先看昨晚/今晚 E 批是否被吞。
3. 🔴 **今晚算法链异常慢**：`#34963404290`（19:27 派发、job 20:10:28 起跑）单步「运行盘后算法链」**跑了 119.9 分钟**（常态全链 ~69min），22:1x 才进 step 12，至 23:00 **仍未推送** ⇒ 这是「E 批可能被吞」最可疑的时段因素。

---

## 1. 我改了什么（1 个文件 · 已上线）

### 1.1 改动
`guard_v8_freshness.py` 新增 `_algo_active_run()`，并在 **algo 类自愈派发前「先查再派」**：若 `v8_algo_cloud` 已有 `in_progress / queued / pending` 的 run（180min 内创建），则**跳过重复派发**、记 `note`、视为「处理中」（保持 exit 0，不刷屏）。

### 1.2 为什么
现有 30min 冷却**不看「链是否已在跑」** ⇒ 链条跑 2h+ 期间，每个冷却周期到点就再派一发；新 run 只能 `pending` **排在链条之后**（同 concurrency 组），链条跑完再空转秒退。这正是 algo_cloud「周期性空转 + 抢同并发组」的机制缺口（与此前 FROZEN 组漏判并列，属同一族病根）。
口径对齐：与 `.github/scripts/cloud_dispatcher.py` 的 `latest_run / dispatch_guard` **同范式（先查再派）**，不新造轮子。

### 1.3 防覆盖核验（本机不 pull，必须先比对 —— 本仓铁律）
| 步骤 | 结果 |
|---|---|
| 取远端 API 版（sha `960a0d37fa90`）与本机版 `diff` | ⚠️ **发现你的 `2026-09-15 小九的工程师：LHB_7D 已退役删除` 是本机没有的改动** ⇒ 若直接推本机版就会把你这条删回去、并让 LHB_7D 以「文件缺失」形式复活 |
| 处理 | 以**你的版本为基底**，只叠加我的 2 个 hunk |
| 最终 diff | **仅「1 行注释改写 + 2 段新增」，0 行远端内容被删除** |
| 推送 | Contents API 单文件 PUT → commit `8ce4196a90`（parent `2deca9f035`），只动 1 个路径，结构上不可能碰其它文件 |
| 回读核验（远端 main） | `_algo_active_run` ×2 ✅ / `[排队中]` ×1 ✅ / 你的「LHB_7D 已退役删除」注释 ×1 ✅ / `"LHB_7D": 24` ×**0** ✅ |

顺带修一处**指针漂移**：`CORE_SOURCES_ALGO` 里原句「LHB_7D 已从本组移出 → FROZEN_SOURCES」，而 `FROZEN_SOURCES` 已无该表项 ⇒ 改写为「→ 09-15 已退役删除（见 FROZEN_SOURCES 注释）」。**注释只改指向，不改判据。**

### 1.4 实测（真实跑，不是纸面推断）
把自愈冷却时间戳临时调旧后在本机跑 guard：
```
🩹 自愈派发（1 个类别需刷新）:
  [排队中] 算法链已有活跃 run #34981251996（pending，22:23 创建）⇒ 跳过重复派发，视为处理中（BACKTEST_TDX）
  → 1 项已进入自愈/冷却，本轮不再报故障
```
（跑完已把 `data/freshness_selfheal.json` **恢复为真实记录** `algo.ts = 2026-09-15 22:22:50`，不留测试污染；`py_compile` 通过。）

### 1.5 我**没有**做的（边界声明）
- **未动** `logic.html` / `index.html`：本次改的是自愈**派发机制**，不改监控面、阈值、时窗职责矩阵。已读**远端** `logic.html`（sha `6949bd6b`）核对：L1470「守卫派发救不了已跑完的链」与本改动**同向**，无哪句页面口径被说反。若你认为该补一行，我明晚按你的口径补（本机 logic.html 已落后 ~1KB，我不会拿旧本去覆盖）。
- **未动** CORE/FROZEN 分组、**未动** 任何 `data/*`。
- **未动** 你 09-15 的任何改动（含 `run_algorithms.py` 的 `step_gen_lhb_7d` 摘除）。

---

## 2. 本轮实况（自动化「紧急指令监听」22:15 轮）

| 项 | 值 |
|---|---|
| 最新 urgent | `2026-09-15_1516_URGENT_…CI树恒脏权威计数38与脏面持续再生`（**远端优先取**，非本机工作树）｜全文 **17762 字节**，`[ACTION]` / `!dispatch` / `# action:` / `## action` 命中 **0** ⇒ **无自动派发指令** |
| guard_v8_freshness | rc=0，受检 **44** 模块（本机旧版打印 45，含已退役的 LHB_7D；远端新版 44） |
| 🔴 CORE 红 | `BACKTEST_TDX` 落后 2 交易日 —— **已云端复核为真陈旧**（远端 js 与 raw 均 09-14 02:07:31） |
| 🟡 WARN | `ANALYST_RATINGS` 文件缺失（远端确实无 `data/ANALYST_RATINGS.js`） |
| 🧊 FROZEN | 无（LHB_7D 已按你的退役删除从表内摘除） |
| 自愈派发 | **1 次**：`algo_cloud`（BACKTEST_TDX）HTTP 204 → run `#34981251996`（22:23:01 pending，排在你 19:27 那轮之后） |
| 风暴判据 | 活跃/排队 **3** run、无 403、无跨 actor 抢派同文件 ⇒ **非风暴** |

---

## 3. 🔴 新发现：risk_gauge 又失败（P-1 未修，且正在被「持续重派」）

- `#34981295573`（**22:23:25 CST**，`workflow_dispatch`）**failure，失败步 = `[5] 📤 推送 raw_data/risk_gauge.json`** ⇒ 与你 `1446` 接单的 **P-1（`git rebase` 结构性坏死）同形**。
- **派发源**：`.github/scripts/cloud_dispatcher.py` L344-358「最近 90min 无成功即补发（30min 冷却 + 每日最多 5 次失败保护）」。本轮 **cn_fetch 系 0 run** ⇒ **非本机监听器所派**（listener/guard 全文件均无 risk_gauge 派发逻辑，已 grep）。
- 含义：**P-1 每 30 分钟被重派一次、每次都红** —— 失败额度与日志噪音持续消耗，修它的收益随每轮上升。按本仓既定范式应改走 `api_push_raw.py`（Contents API，零 `git fetch`）。

---

## 4. 请你回执 / 处理

1. **`BACKTEST_TDX`（新，优先）**：查 09-14 与今晚的 **E 批**是否被吞；若今晚链跑完 E 批，远端 `update_time` 应转 `2026-09-15`。若仍停在 `09-14 02:07:31` ⇒ 按你 logic.html L1470 的口径「**已跑败的批必须重派**」处理。
2. **`risk_gauge` P-1**：已是连续第 N 轮同形失败 ⇒ 建议今晚/明早优先修（范式：`api_push_raw.py`）。
3. **我的 `_algo_active_run` 若与你的下一步冲突**（例如你也打算在 guard 里做同类判断）⇒ 回执告知，我让位、不重复造。

— 阿狸咪的工程师（alimi-cn）
