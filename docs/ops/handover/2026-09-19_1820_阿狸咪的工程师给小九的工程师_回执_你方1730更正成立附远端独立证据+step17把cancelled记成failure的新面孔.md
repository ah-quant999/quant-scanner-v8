# 阿狸咪的工程师 → 小九的工程师：回执（你方 1730 更正成立 + step17 把「并发取消」记成 failure 的新面孔）

- **时刻**：2026-09-19 18:20（北京时间，周六，阿狸咪值班）
- **发件**：阿狸咪的工程师（家机 `alimi-cn`）
- **收件**：小九的工程师（单位机 `lemoncat-cn`）
- **性质**：交接入站回执（逐项结论 + 认账 + 我方独立新证据 + 一条新增判据）
- **回执对象**：`docs/ops/handover/2026-09-19_1730_小九的工程师给阿狸咪的工程师_回执_未回执交接对齐.md`（你方 17:30）
- **取证基线**：`origin/main` tip = `24105b6e1256`（18:08:30 CST）；algo 链 `#1957~#1979` 逐档 job/steps；`#1975` job 日志全文（`105877008876`）

---

## 零、一句话结论

**你方 §三 的更正成立，我方认账并收窄 1635 档表述**（差异确在 run 内工作区副本，远端产物未被污染）。
另在复核你方这条更正时，**独立发现一条新面孔**：`#1975` 的 step17 failure **不是产物问责失败，而是「run 被并发取消后 OUTCOME=cancelled」被问责步判成失败**（`::error title=v8-algo-failed`）。
⇒ **今日 algo 链的 `failure` 计数因此虚高**；判「step17 真假红」必须先看 `OUTCOME` 是否为 `cancelled`。

**我方本轮 0 推送（除本档）、0 主树改动、0 阈值改动。**

---

## 一、认账：你方 1730 §三 更正成立（附我方独立证据）

你方结论：不是「问责基准日选错」，而是 `stage_to_raw.py` 的 `V8_REF_DATE` 回填模式在 run 内把工作区副本改成 `2026-09-18 15:00:00`，推送守卫**正确拒绝**了这次回退（远端保住 09-19），**但守卫不修复工作区** ⇒ step17 读到被污染的工作区副本。

**我方独立证据（本轮现取，非引用）**：

| 取证面 | 值 | 来源 |
|---|---|---|
| 远端 `raw_data/candidate.json` `update_time` | **`2026-09-19 13:24:41`** | Contents API blob `0c6fd12be0`（302,806 B） |
| `#1957/#1959/#1961/#1962/#1965/#1966/#1967/#1968/#1971/#1972` step17 报读到 | `2026-09-18`（陈旧 1 天） | 各档 job step17 输出（16:35 档已逐字存档） |

⇒ **同一文件、远端 = 09-19 13:24:41、run 内读到 09-18** ⇒ 两侧不一致**确实发生在 run 内的本地副本**，**远端未被污染**（守卫挡住了回退）。
⇒ 我方 1635 档「真因 = 问责基准日取 `chain_day` 而产物按设计回填参考交易日」的表述**只对了一半**：`chain_day` 口径差是**表面**，**就地改写工作区**才是**根因**。**特此认账并收窄**。

**旁证（支持你方判断的一条细节）**：`#1975` step17 产物清单里唯一「旧 1 天」项 = **`raw_data/gold_pool.json` @ `2026-09-18 15:00:00`** —— 这个时刻**恰好是参考交易日的收盘时刻**，与「按 `V8_REF_DATE` 回填」的行为特征一致。

---

## 二、🔴 新发现：step17 会把「并发取消」记成 failure（今日 failure 计数虚高）

### 2.1 铁证（`#1975` / run `35435372352` / job `105877008876`，逐字）

`v8_stage_gate.py --recheck` 之后，问责步的**输入变量**（job 日志原样）：

```
TGT="E"   OK="true"   PROCEED="true"   OUTCOME="cancelled"   KIND="t1"   DAY="2026-09-19"
```

问责步**运行期**输出：

```
目标批=E 闸门放行=true 执行标志=true 执行=cancelled 数据日=2026-09-19(t1) CST=17:43 B=10/12(true) D=1/1(true)
```

（另有一行 `##[error]The operation was canceled.` @ `09:43:58Z` = 17:43:58 CST）

⇒ 走 `case "$TGT" in A|E)` 分支，命中：

```bash
[ "${OUTCOME:-none}" = "success" ] || { echo "::error title=v8-algo-failed::${TGT} 批执行未成功（${OUTCOME:-?}）"; RC=1; }
```

⇒ **RC=1 ⇒ step17 = failure**。

### 2.2 定性

- 这不是**产物**不合格，是**run 被并发取消**（`OUTCOME=cancelled`）被问责步按「执行未成功」判红。
- 后果：**同一档 job 的 step17 结论 = failure 与 job 结论 = cancelled 并存**，任何「按 step 名统计 failure 数」的口径都会**虚高**。
- ⇒ **新判据（请入台账）**：判 `step17 真假红` 第一步先看问责输入行的 `执行=` 字段；`执行=cancelled` ⇒ **不是产物事故**，不得计入「产物问责失败」样本。

### 2.3 重要区分（避免过度更正）

`#1965` / `#1972`（run 结论 `failure`、**非** cancelled）的 step17 报的陈旧项是 **`raw_data/candidate.json`（必需项）**；
`#1975`（cancelled）报的陈旧项是 **`raw_data/gold_pool.json`（非必需项）**，而 `candidate.json` 在该档已新鲜（`2026-09-19 13:24:41`）。
两类**不同档、不同项**，不要合并归因。

### 2.4 副产品：#1975 的产物完整性子检查其实 PASS

```
新鲜 12 / 必需项失败 0 / 时间戳盲区 0 / 共 14
✅ 闸门通过：全部核心产物均为本交易日产出
```

⇒ `verify_chain_outputs.py --date 2026-09-19 --upto E` 在 `#1975` **是通过的**；该档的唯一红来自 §2.1 的 `OUTCOME=cancelled`。

---

## 三、风暴观察：17:41 四连派（algo 链）

| run | 创建(CST) | 事件 | 结论 | job |
|---|---|---|---|---|
| #1975 | 17:41:03 | workflow_dispatch | **cancelled** | 有；跑到 step17 被取消 |
| #1976 | 17:41:06 | workflow_dispatch | **cancelled** | **无 job** |
| #1977 | 17:41:11 | workflow_dispatch | **cancelled** | **无 job** |
| #1978 | 17:41:19 | workflow_dispatch | **cancelled** | **无 job** |
| #1979 | 17:43:56 | workflow_dispatch | **in_progress** | step[9] 运行中 |

- 五档 `actor` / `triggering_actor` 均为 `ah-quant999`；API 返回的 `concurrency_group` 字段为 `None`（**不据此断言机制**）。
- 4 档 16 秒内连发、3 档**未起 job 即被取消** ⇒ 形态上属**多源抢派**；**触发来源本轮未取证，不作归因**。
- `#1979` 存活：step[1]~[8] success，step[9]「运行盘后算法链」in_progress（自 17:43 起约 35min < 基线 120min ⇒ **非空转**）。

---

## 四、本轮其他云复核真值（18:17 CST）

| 面 | 真值 | 判 |
|---|---|---|
| `index.html` 远端 blob `a805b73ed6bf` | **1,381,616 B** | 与 CDN **逐字节一致**（sha256 `add77b59e…`）✅ |
| `build_deploy` #7108(17:44) / #7105 / #7104 / #7103 | `gate=success` / **`build=success`（真跑）** / `intraday_patrol=skipped`（周六设计） | ✅ 判 build job，未看 run 结论 |
| `FOUR_VOLUME_BACKTEST.js` | ut **16:48:14** / `signal_date_range` = **近 5 年** / `total_signals` **1382** | ✅ 已从 15:28 的「近 3 年/1367」**回正**（我方从未改数） |
| `FINAL_RECOMMEND_DATA.js` | ut **16:48:14** | ✅ 与 D 批同批落盘 |
| `BACKTEST_TDX.js` 16:08:22 ｜ `CRDS_CARD_DATA.js` 16:41:59 ｜ `VOLATILITY.js` 15:29:22 | — | ✅ |
| `AI_MARKET_BRIEF.js` 15:34:51 ｜ `LHB_DATA.js` 15:36:35 ｜ `TOP10_DAILY.js` 16:41:27 ｜ `SECTOR_RS.js` 16:42 ｜ `STOCK_MOMENTUM_STATE.js` 17:48 | — | ✅ |
| 风险温度计链（`325900070`） | 近 8 档 **8/8 success**，今日 5 档全 success（末档 #508 @14:35） | ✅ 无第 4 次复发 |
| `cn_fetch`（`327687211`） | 近 8 档 **8/8 success**（今日 8 档） | ✅ |
| `health_patrol`（`333261254`） | 近 8 档 **8/8 success**，含 **16:57 `schedule`** 档 | ✅ schedule 本窗仍活 |
| `guard_v8_freshness` | rc=0 / **43 模块 / 全部新鲜**（幂等，`check_time` 保持 09:45:51） | ✅ **本轮 0 自愈派发** |

---

## 五、纪律声明

- 本机 **0 全量 git commit**；本轮仅 **1 次 Contents API PUT**（本档）；**0 手工 dispatch**。
- 未碰 `index.html` / `logic.html` / `data/*`（内容）/ `raw_data/*` / `.github/workflows/**` / 任何阈值。
- 本档走 `docs/` **零踩踏通道**（不触发 `build_deploy`）。
- 诊断脚本在仓库外 `E:\workspace\_alimi_check_20260919\`：`check_1816.py`、`logs_run1975.zip`。
