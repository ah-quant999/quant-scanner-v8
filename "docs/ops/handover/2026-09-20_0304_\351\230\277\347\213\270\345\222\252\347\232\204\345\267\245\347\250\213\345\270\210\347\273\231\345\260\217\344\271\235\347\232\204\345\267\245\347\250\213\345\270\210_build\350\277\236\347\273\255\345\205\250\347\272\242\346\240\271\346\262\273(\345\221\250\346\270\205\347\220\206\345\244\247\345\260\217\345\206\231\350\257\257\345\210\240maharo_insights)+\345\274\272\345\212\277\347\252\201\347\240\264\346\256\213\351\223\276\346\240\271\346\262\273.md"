# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-20 03:04｜build连续全红根治(周清理大小写误删maharo_insights)+强势突破残链根治

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

`v8_build_deploy` **连续 6 次全红、线上 index.html 自 00:21 停更** 的唯一根因已定位并根治
（`cloud_weekly_cleanup` 的 orphan 判定三重缺陷 → 误删 `data/maharo_insights.js` → 门禁 `[6/8]` 报 404）；
同步摘除「强势突破」最后一条活残链。**关联提交**：`aa22ce99e4`、`191dbbaae2`。

---

## 正文

### 一、🔴 最要紧：v8_build_deploy 连续 6 次全红（已根治）

#### 现象（实测）

自 **#7127（`ebf568e8cd`，北京 2026-09-20 00:21）起连续 6 次 failure**（#7127~#7133），
**每次死在同一步**：

```
job build → ✗ step 10 🛡️ Pre-deploy audit（CI 自动门禁）
```

⇒ **线上 `index.html` 自 00:21 起停更**（部署未推进）。

#### 死因（离线复现铁证：本机逐项跑 `pre_deploy_audit.py`）

```
✅ [1/8] py_compile      189 个 .py 0 错误
✅ [2/8] new Function    28 个 inline script 0 错误
✅ [3/8] data 完整性      data/*.js = 108，全部 > 100B
✅ [4/8] align_logic_ops  EXIT 0
✅ [5/8] workflow YAML    30 个全部有效
❌ [6/8] HTML 数据引用    发现 1 处 404 断链：index.html -> data/maharo_insights.js
✅ [7/8] gate 头注一致
✅ [8/8] 心跳产物名一致
```

**唯一失败项 = `[6/8]`：`index.html` 引用的 `data/maharo_insights.js` 不存在。**

#### 根因链（三重缺陷叠加）

`cloud_weekly_cleanup.yml` 的删除判据 = 「不在映射 ∧ 不被引用 ∧ 不在保护名单 ⇒ unlink()」，
但三处判据同时失效：

| # | 缺陷 | 后果 |
|---|---|---|
| ① | 引用面**只读 `index.html`**（站上实为 4 页引用 `data/*.js`） | 只被 `logic.html` 引用的产物必被删 |
| ② | 正则 `data/([A-Z_0-9]+)\.js`，**不匹配小写文件名** | 小写产物的名字永远进不了 `referenced` |
| ③ | 保护名单写大写 `"MAHORO_INSIGHTS"`，实际文件是小写 `maharo_insights.js` | `var_name in PROTECTED_DATA` **恒 False**，保护形同虚设 |

⇒ 2026-09-20 00:08 周清理一次删掉两个文件：

- **`data/maharo_insights.js`**（本机 cookie 拉取的 AI 解析，`window.MAHORO_INSIGHTS`）→ 直接打挂 `[6/8]`
- `data/ALGO_BACKTEST_COMPARE.js`（只被 `logic.html` 引用）

⚠️ **这是本项第 3 次复发** —— `pre_deploy_audit` 的 `[6/8]` docstring 已记录过 09-11、09-13
两次同型事故（「只扫 index.html、漏扫 logic.html」）。

#### 修复（`191dbbaae2`）

1. **恢复** `data/maharo_insights.js`：取自删除提交 `ebf568e8cd` 的**父提交**
   （= 被删前原样，21494 B，内含 `update_time: 2026-09-19 07:30`）—— 是**恢复**，不是伪造。
2. **`cloud_weekly_cleanup.yml` 三层根治**：
   - 引用面扩至 **与 `check_html_refs` 门禁同口径的 4 页**（index / logic / calendar / v6_memo）；
   - 正则改 `[A-Za-z_0-9]+`（支持小写）；
   - 保护 / 映射 / 引用三处比较**统一 `.upper()` 归一**。
   - **原则**：清理面必须 ⊇ 引用面。清理与门禁口径不一致 = 每次清理都制造一次红灯。
3. **`pre_deploy_audit.py` 注记同步**：更正 09-13 那条已失效的
   「勿删 `logic.html` 的 `ALGO_BACKTEST_COMPARE.js` 标签」——并加**反向警告**：
   **不要**照旧注记把该标签加回来（加回即制造新的真 404）。

#### 验证（推前已自证，等价于 CI）

离线 staging 套用修复后重跑门禁：

```
🎉 8 项全部通过 → deploy 可继续
   [6/8] HTML 数据引用: 178 个本地 script 引用全部存在（4 页）
```

---

### 二、「强势突破」残链根治（`aa22ce99e4`）

#### 残留（今日全站删除**漏掉的一条支线**）

聚合器 `algorithms/gen_backtest_all_algos.py` 的 `SOURCES` 仍登记：

```python
dict(card="强势突破", var="ALGO_BACKTEST_COMPARE",
     rel="data/ALGO_BACKTEST_COMPARE.js", parser="algo_compare",
     primary=None, chain_member=True)
```

其数据源已删除 ⇒ 产物残留 **3 行「强势突破」旧值**，其中主口径那行**正是 `delist_advice`
那条「胜率 15.9% < 红线 45%」的来源** —— 即 **「源已删除，却仍拿上一批读到的旧数值发出下架提请」**。

**用户可见后果**：「策略回测」页 **🏁 算法回测总表**（"一个算法一行·按胜率降序"）
仍显示一行 `🚀 强势突破 15.9%`。

#### 修复（同批一次推，判据 107）

1. `gen_backtest_all_algos.py`：摘除该 `SOURCES` 条目 + 移除 `parse_algo_compare()` +
   摘 `PARSERS["algo_compare"]`（三处均留墓碑注释，载明删除理由与恢复前提）；
2. **新增 `fresh` 护栏（通用，防同类复发）**：
   ```python
   if not r.get("fresh"):
       entry["note"] = "源未在本数据日 ... 刷新（数值可能陈旧），不提议下架，仅观察"
       watch.append(entry); continue
   ```
   ⇒ 源不可读 / 未刷新时**只入观察名单、不提议下架**（下架不可逆，陈旧数值不足以支撑）；
3. 产物摘除：`raw_data/backtest_all_algos.json` + `data/BACKTEST_ALL_ALGOS.js`
   （后者由脚本**直写**、非 `update_v8.py` 派生 ⇒ 必须同步推）
   - `rows 196→193`、`ranking 5→4`、`ranking_all 162→159`、`delist_advice 1→0`、`coverage 8→7`
4. `index.html`：修正与事实相反的可见文字 —— 原写「…数据层照常回测、**不删不停更**」
   → 改为「2026-09-19 主人令：连同数据层 / 渲染函数 / 回测源一并移除，已不再产出、不再回测」；
5. `logic.html`：摘除已 404 的 `<script src="data/ALGO_BACKTEST_COMPARE.js">` + 更正
   E 批矩阵表里「补齐强势突破回测源」的过时描述。

---

### 三、给你（小九）的注意事项

1. **`data/maharo_insights.js` 是本机侧（家机 cookie）每日生成的产物**，云端拉不到原文。
   - 云端 checkout 里它本就不存在是正常的，但**仓库里必须有**（`index.html` 引用它，
     `[6/8]` 门禁据此判定）。
   - ⇒ 别在云端批量清理时把它当 orphan。现已加入大小写归一的保护判定。
2. **本机若重跑 `maharo_daily_pull.py`**，正常更新该文件即可（会生成新的 `update_time`）。
3. **周清理与本门禁的耦合**：以后新增「只被 `logic.html` / `calendar.html` / `v6_memo.html`
   引用」的产物**无需**再手动加保护（清理侧已与门禁同口径）。但**新页面**若引入
   `data/*.js` 引用，请**同时**把该页名加进两处清单：
   - `.github/scripts/pre_deploy_audit.py::check_html_refs` 的 `pages`
   - `.github/workflows/cloud_weekly_cleanup.yml` 的 `PAGES`
4. `gen_backtest_all_algos.py` 的 `algo_compare` 相关代码已摘除：**不要**把 `SOURCES`
   条目加回来（会复活一个已删卡的数据行、并可能再发下架提请）。若日后确需
   「H反推 / 高手画像版」同口径对比，**新开一张独立卡**并重写解析器。
5. `scripts/algo_backtest_compare.py` **仍在 E 批链上**（产 `data/ALGO_BACKTEST_COMPARE.js`），
   但其产物**已无任何消费方**（前端 2 页均不再读）。本轮**未**摘链（避免动 E 批结构
   触发链级校验），**留作后续评估**。若你评估后要摘，注意同步 `ORDER` + `STAGES["E"]` 两处。

---

### 四、本轮实证汇总

| 项 | 实测 |
|---|---|
| 离线门禁（修复后） | **8/8 全绿**，`[6/8]` 178 个引用全部存在 |
| `align_logic_ops` | EXIT 0 |
| `v8_verify_layer_parity` | EXIT 0 |
| 产物「强势突破」字面量 | `raw_data` = 0、`data/BACKTEST_ALL_ALGOS.js` = 0 |
| index.html 反向文字 | 「数据层照常回测、不删不停更」= **0** |
| node 门禁 | index 28 段 + logic 6 段 = 34 段 `new Function` **0 错** |
| 推送方式 | GitHub Git Data API，`base_tree` + `force:false`；未碰坚果云工作区 |
| 待验 | `191dbbaae2` 的 build run 结果（推后观察，转绿即闭环） |
