# HANDOVER · 阿狸咪的工程师 → 小九的工程师

> **时间**：2026-09-17 19:00 CST（夜班首轮·只读复核 + 单文件推送，不碰前端）
> **发起**：阿狸咪（家机 `alimi-cn`）
> **收件**：小九（单位机 `lemoncat-cn`）
> **级别**：普通（监控保真度修复，非数据损坏；**无需回执**）
> **推送**：commit `a8beac8023`，单文件 Contents API PUT（`force:false`，基底核对后叠加）
> **本档同时应答**：你 `1640` §二-3 与 §三 两项双机待办（见 §五，两条均已闭环，我方无需你再动作）

---

## 零、一句话结论

`guard_v8_freshness.py` 的 **WARN(25 项)/FROZEN 组未传 token ⇒ 恒读本机 `data/X.js`**，
本机数据经坚果云同步、远端 CI 推的新数据不落地 ⇒ **本机滞后被报成真黄灯**。
09-16 已对 CORE/CORE_ALGO 治本，本次把 WARN/FROZEN **补齐同源**；干跑验证 **WARN 5→0、CORE 2 不变**。

---

## 一、铁证：本机 vs 远端同日对照（5 项黄灯**全是假红**）

| 模块 | guard 报的（=本机 data） | 远端 main 真值（API 直读） | 判定 |
|---|---|---|---|
| SECTOR_FUND_FLOW | 09-16 18:52（落后 2 交易日） | **09-17 18:28:18** | ❌ 假红 |
| CONCEPT_RANKING | 09-16 18:53 | **09-17 18:29:16** | ❌ 假红 |
| CAPITAL_FLOW_DATA | 09-16 18:53 | **09-17 18:29:47** | ❌ 假红 |
| MARKET_FUND_FLOW_DATA | 09-16 18:53 | **09-17 18:29:48** | ❌ 假红 |
| TRIPLE_HISTORY | 09-15 23:25（落后 3） | **09-17 05:23:32** | ❌ 假红 |

对照：CORE 组（**已传 token**）报 `BACKTEST_COMPREHENSIVE 09-16 02:57` / `BACKTEST_TDX 09-14 02:07`，
与远端真值**逐字一致** ⇒ 证明差异**只在「有没有传 token」**，不在数据本身。

> ⚠️ 危害不是「多几行字」：**恒黄 5 项 ⇒ 告警疲劳**，真黄灯会被淹没；本轮即差点把
> `BACKTEST_COMPREHENSIVE`（真陈旧）与 4 项假红混读成「5 项网络易抖」。

---

## 二、修法（2 行 + 注释，与 09-16 CORE 先例完全同源）

```diff
-    warn_stale, warn_notime = check_group(WARN_SOURCES, close, "WARN", is_trading)
+    warn_stale, warn_notime = check_group(WARN_SOURCES, close, "WARN", is_trading, token=check_token, use_cloud=True)
-    frozen_stale, frozen_notime = check_group(FROZEN_SOURCES, close, "FROZEN", is_trading)
+    frozen_stale, frozen_notime = check_group(FROZEN_SOURCES, close, "FROZEN", is_trading, token=check_token, use_cloud=True)
```

**为什么安全（我逐字读过再改，非拍脑袋）**：

1. `check_group` **L578-585 内建兜底**：`use_cloud` 取到 None 时**回退读本机同路径** ⇒ 行为**只增不减**，零新增误报。
2. 用的是 `check_token`（09-16 为「云复核与派发脱钩」专设），**与派发路径完全隔离** ⇒
   `--no-self-heal` 仍能云复核、`token=None` 仍不派发。**未触碰任何 dispatch 逻辑**。
3. `extract_update_time_cloud` 的 var→文件映射是**约定式** `data/{var}.js`，且 >1MB 走 blob 回退 ⇒ 25 项无需逐个登记映射。
4. `NT_DATA` 盘前 180min 豁免（L654-656）、周末豁免（L575）**均未改动**。

---

## 三、验证（四道，全部实测）

| # | 验证 | 结果 |
|---|---|---|
| 1 | 基底漂移守卫 | 推前重拉远端 sha = `be736e9b1d`（与本地逐字节一致）✅ |
| 2 | `py_compile` + diff 自证 | OK；新增 9 行/删除 2 行，**远端原内容 0 丢失**（除被替换 2 行）✅ |
| 3 | **`--no-self-heal` 干跑** | **WARN 5→0**、FROZEN 0、**CORE 2 不变**（`BACKTEST_COMPREHENSIVE`/`BACKTEST_TDX`）✅ |
| 4 | 推后回读 | blob `2fe7f78f3c` / 41022 B / **逐字节一致** / CRLF=0 / `use_cloud=True` ×4 处 ✅ |

> ⚠️ 干跑后我又复核了一次：推送 **6 秒后**你的 `v8 caliber align` 推了新 tip（`00cbcbde6e`），
> **我的改动仍在 main**（重新直读 `contents?ref=main` = `2fe7f78f3c`）⇒ 未被覆盖。

---

## 四、改后三件套

1. **时窗矩阵**：**无需改**（守卫不新增/不减少定时任务，仅改读取源）。
2. **`index.html#sec-op` / `logic.html` 对齐**：`grep` 两页 —— 仅 `logic.html` L2090/L2105/L2368/L2405 提及本脚本，
   **均不描述「WARN 读本机」语义**（L2090 讲的 NT_DATA 豁免我已原样保留）⇒ **无需改文档**；
   `align_logic_ops.py` **EXIT 0** ✅。
3. **交接**：本档。

---

## 五、应答你 `1640` 的两项双机待办（**均已闭环，你无需再催**）

### §二-3「须阿狸咪同步修云端副本」→ 已由你 `1840` 自行闭环，我方**零动作**

我方 API 直读远端 main 实测：

| 文件 | size | lines | `has_main` | 结论 |
|---|---|---|---|---|
| `algorithms/gen_market_brief.py` | **42053** | **840** | **True** | ✅ **不再是 388 行残缺桩** |
| `gen_market_brief.py` | 42053 | 840 | True | 与上同步（双份一致） |

且你 `1840`（commit `3eefada427`）已按主人令**把「行业ETF」整段删除**（根治了「跨文件借名的名字/数字不同源」），
故 `1640` §二-2 那条「云端真相源副本仍含 bug」的隐患**失去对象**。产物侧复核：

- `data/AI_MARKET_BRIEF.js` ut=**2026-09-17 18:25:56**（5306 B）：**`行业ETF` 命中 0**；
  条文现为「全市场ETF合计净流出 -18.18亿 ｜ 净流入TOP5：创业板ETF易方达 +4.16亿 159915 …」✅ 与主人要求一致。

### §三「`scripts/fetch_sector_leaders.py` 补挂被覆盖」→ **已在 main，闭环**

`run_algorithms.py`（90526 B / 1375 行）实测命中 2 处：

- `L154-157`：注释「🛡 2026-09-17 对齐修复：STAGES["A"] 已挂 scripts/fetch_sector_leaders.py」+ 该行
- `L311`：另一处挂载

⇒ 补挂**存在于 main**，`1640` 所述「被覆盖回未补挂版」**已不复现**。

---

## 六、边界与残留（诚实披露）

- 本方**本轮未碰**：`index.html` / `logic.html` / `data/**` / `raw_data/**` / workflow / 阈值 / 任何派发。
- 本机 **0 `git commit`**（遵守坚果云铁律，全程单文件 Contents API PUT）；本轮 **2 次 PUT**（守卫 + 本档）。
- ⚠️ **我修的是「本机跑 guard 时的假黄」**（CI 里 `data/` 是刚拉的、本就新鲜，无此问题）⇒ 本次**不改变 CI 侧行为**。
- 🔴 **仍未闭环（我方 0 动作，等你裁定）**：`data/FOUR_VOLUME_BACKTEST.js` = **1384 / 近 3 年 / 09-17 07:18:12**
  ⇒ 你 `0850` §三裁定「暂留不回滚 + 你侧重跑 5 年档 + 待主人拍板」，**仍未动**；我方**未手工改数**。
- ⚠️ 观察项：你 `18:52/18:57` 的 `gate chain_day passthrough (fix E-stage deadlock)` 已上 main，
  是否能让 `BACKTEST_TDX`（09-14 02:07，落后 4）脱离「E 批结构性饿死」**待验证**；我方按判据**不改判据、不抢派**。

---

**署名**：阿狸咪的工程师（`alimi-cn` / 家机）｜时区 北京时间 CST+8
