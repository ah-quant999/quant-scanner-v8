# 僵尸模块审计纠正 + 停跑 LHB_7D + 补注入 FRESHNESS_STATUS

- **发件**：阿狸咪的工程师（`alimi-cn`，家用机）
- **收件**：小九
- **时间**：2026-09-13 10:16 CST
- **上线**：`ec8bb21d`（已 push origin/main，`match=True`）
- **起因**：主人令「审计一下，还有什么是虽然前端已看不到了，但是还在继续跑着的，分析评判一下还有没有留着的必要」

---

## 一、🔴🔴 首先纠正我自己的上一份清单（重要）

我在 `2026-09-13_1005` 那份交接单里给主人的「僵尸清单」**大部分是错的**，根因是我把
**「未注入前端」** 直接等同于 **「僵尸」**，而没有去查 **后端消费方**。本轮逐项取证后推翻如下：

| 我上轮建议 | 实测事实 | 结论 |
|---|---|---|
| 停 `gen_stock_profile.py` | `raw_data/stock_profile.json` 有 **3 个真消费者**：`build_pool_tracker.py:44/102/323`、`final_recommend.py:396`、**`v8_stage_gate.py:127`（A 批闸门 must 项）** | ❌ **绝不能停**，停则闸门不就绪 + 最终推荐读脏数据 |
| 停 `gen_algo_track.py` | `logic.html:8635` 真读 `window.ALGO_TRACK`（`if(!at\|\|!at.total_stats) return null`） | ❌ 不能停，停则逻辑页算法追踪恒 `null` |
| 停 `calc_stock_rps.py` | `raw_data/stock_rps.json` 是 `data/STOCK_RPS_DATA.js`（前端注入的那个）**唯一**上游 | ❌ 不能停 |
| 清 `data/hb_xiaojiu.js` 死链 | 链路已建齐：`update_v8.py:108` 映射 + `v8_peer_monitor.py` 消费，**只等你这侧产出 `raw_data/hb_xiaojiu.json`** | ❌ **不能删**，删 = 废掉待激活功能 |
| 停 `gen_lhb_7d.py` | 前端零引用 + `raw_data/lhb_7d.json` 全仓无读取者 | ✅ **正确，已执行** |

**方法论教训（已写入 skill §8）**：判定僵尸必须查**三层**——
① 前端 `<script src>` 注入性 ② 前端 `window.X` 代码消费 ③ **后端脚本消费（`load_js("X.js")` / 直接读 `raw_data/*.json`）**。
只看第①层会得到一份**大面积误报**的清单。

---

## 二、本轮实际处置（2 项，已上线 `ec8bb21d`）

### 1️⃣ 停跑真僵尸 `gen_lhb_7d.py`

**取证**：
- `data/LHB_7D.js`：`index.html:527` 早在 2026-08-31 就写明「前端零引用，停止注入」
- `raw_data/lhb_7d.json`：`grep -rn "lhb_7d" --include=*.py` 只命中 `gen_lhb_7d.py` **自身写入**，无任何读取者

**但**：`run_algorithms.py` 的 `ORDER`(L197) 与 `STAGES`(L284) 虽已注释，**`L1210` 的硬编码调用仍在**：
```python
if stage in (None, "B", "D"):
    if _is_post_close_picking_ready() and _is_trading_day_now():
        step_append_lhb_history()
        step_gen_lhb_7d()   # ← 这行每天在跑
        step_build_pool_tracker()
```
⇒ 这正是主人问的「**前端已看不到，但还在继续跑**」。

**处置**（`algorithms/run_algorithms.py`）：
- L1210 `step_gen_lhb_7d()` → 注释并附取证说明
- L454 `STOCK_PICKING_SCRIPTS` 内的 `"gen_lhb_7d.py"` 残留 → 清除
- L1146 `step_gen_lhb_7d()` 函数体 → 标 `⚠️ DEPRECATED`，**保留函数体便于随时回滚**

### 2️⃣ 补注入 `data/FRESHNESS_STATUS.js`（2.7 KB）

**取证（反向问题：后端产了、前端拿不到）**：
- `update_v8.py:1109 _emit_freshness_status_js()` 每次 build 都生成该文件（2026-09-11 你修的 P2 死功能）
- `index.html:10793` 与 `logic.html:5634` 的 `renderTaskSchedule()` **真读** `window.FRESHNESS_STATUS.check_time` 作时间候选
- 但 `index.html` **从未注入**它 ⇒ 该行注释至今仍写着「数据源未配置，当前永远空对象」

**处置**：在 `AVG_PRICE_DATA.js` 注入行之前补一行 `<script src="data/FRESHNESS_STATUS.js?v=1789263370" defer></script>`。
安全性：`renderTaskSchedule()` 的时间判定以 `HEALTH_CHECK.updated` 为权威，`FRESHNESS_STATUS` 仅在 `HEALTH_CHECK` 缺失时进入多源 max 兜底 ⇒ **不影响现有判定**。

---

## 三、上线自证（全部实测，非推断）

| 项 | 结果 |
|---|---|
| push 结果 | `ec8bb21d`，`match=True`，远端 main 已核对 |
| `index.html` 含 `src="data/FRESHNESS_STATUS.js` | grep = **1** |
| `run_algorithms.py` 调用已注释 | L1218 `# step_gen_lhb_7d()` ✅ |
| 门控残留已清 | L454 已变注释行 ✅ |
| `htmlcheck.mjs` | 脚本段 25 · **语法失败 0** · 标签净差全 **0** |
| `py_compile run_algorithms.py` | OK |
| `align_logic_ops.py` | **EXIT 0**（`sec-op 515166｜sec-lg 520167｜cron workflow 21 MUST=21/ALLOW=3`） |
| 行尾守恒 | `index.html` CR=0、`run_algorithms.py` CR=0（推前推后一致） |

---

## 四、⏳ 待你回执 / 待主人定夺

### 4.1 请你确认（不影响本次上线）
1. **`data/hb_xiaojiu.js` 生产者**：`update_v8.py:108` 映射已就位、`v8_peer_monitor.py` 已在读，
   但 `raw_data/hb_xiaojiu.json` 仓库内不存在 ⇒ **双机掉线告警恒不触发**（承接 `2026-09-13_0922` 的遗留 P0）。
   请在你侧产出该心跳文件。
2. **`data/maharo_macro.js`**：远端**从未存在过**（本机那份 `updated_at 2026-09-11 08:58` 从未推送），
   而 `index.html:550` 仍在注入 ⇒ **CDN 404**。
   好消息：`renderMahoroCard()` 与 `fetch_ai_insights_compare.py` 都已在 2026-09-13 改为**优先 `MAHORO_INSIGHTS`**，
   所以功能不受影响、这一行注入已是纯冗余。**建议下轮删除该注入行**（我未擅自删，因涉主人令建的卡片）。

### 4.2 报主人定夺（我未执行）
- **`data/STOCK_PROFILE.js`（1.33 MB）产物是否停发**：
  - 事实：前端已改为「`STOCK_LIST` 到位后就地合成 `window.STOCK_PROFILE`」（`index.html:15295-15309`，2026-08-31 轻量化），
    且**全仓无任何脚本 `load_js` 读它** ⇒ 该产物目前前后端均无人消费，却每天随 build 重新入库 1.33 MB。
  - ⚠️ 但**生产它的 `gen_stock_profile.py` 必须保留**（`raw_data/stock_profile.json` 有 3 个消费者，含 A 批闸门 must）。
  - 停产需同步 **4 处**：`update_v8.py`(映射 L39/STAGE_MAP L269)、`cloud_weekly_cleanup.yml`(白名单，否则判孤儿删除)、
    `v8_deploy_guard.py:47`(最小值 222906)、`v8_health_check.py:1710`(低频名单)。
  - **收益**：仓库每日少 1.33 MB 提交；**风险**：中（4 处联动任一漏改即红灯）。**等主人一句话。**

---

## 五、附：本轮完整审计结论表（三层判据）

| 产物 | 前端注入 | 前端消费 | 后端消费 | 判定 |
|---|---|---|---|---|
| `LHB_7D.js` | ❌ | ❌ | ❌ | **真僵尸 → 已停跑** |
| `STOCK_PROFILE.js` | ❌（合成替代） | ✅（读合成结果） | ❌ | 产物冗余 → 待主人定夺 |
| `CANDIDATE_QUOTES.js` | ❌ | ✅ logic.html:3007 | ✅ `final_recommend.py:255` | 活跃，保留 |
| `INDEX_HISTORY.js` | ❌ | ❌ | ✅ `fetch_index_value_framework.py:108` | 活跃，保留 |
| `FRESHNESS_STATUS.js` | ✅（本次补） | ✅ renderTaskSchedule | — | **已闭环** |
| `ALGO_TRACK.js` | ❌ | ✅ logic.html:8635 | — | 边界，保留 |
| `RUNNER_STATUS_HEALTH.js` | ❌ | ❌（仅注释） | ❌（无生产者） | 历史孤儿，已自然停更 |
| `STOCK_RPS.js` | ❌ | ❌ | ✅（raw 产 STOCK_RPS_DATA） | 保留 |
| `hb_xiaojiu.js` | ✅ | ✅ | ✅ peer_monitor | 待激活，保留 |

**data/*.js 全量 102 个的机器审计：A 已注入 95 / B 未注入但有前端消费 3 / C 未注入仅脚本用 4 / D 真僵尸 0。**
（注：`STOCK_PROFILE` 表面上属 B，但其消费的是**合成结果**而非注入文件，故单列。）

---

**署名**：阿狸咪的工程师
