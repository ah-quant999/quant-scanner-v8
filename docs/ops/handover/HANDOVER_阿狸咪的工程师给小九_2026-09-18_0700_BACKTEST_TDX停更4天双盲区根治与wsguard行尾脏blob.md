# HANDOVER｜阿狸咪的工程师 → 小九

**时间**：2026-09-18 07:00 CST
**主题**：BACKTEST_TDX 停更 4 天「双盲区」根治 + ws-guard 行尾脏 blob（E 批前置路障）
**性质**：P0 修复已上线（4 commit，全部 Git Data API 推送 + 逐字节回读自证）；含 1 项请小九复核
**关联**：本轮由主人 09-18 令「按你建议全做，把握符合我宗旨和铁律」授权自主裁定执行

---

## 0. TL;DR

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| ① | `BACKTEST_TDX` 产物涨到 **76,078,046 B** ⇒ 推送 `POST /git/blobs` 每次 `HTTP 422` ⇒ 线上产物**停更 4 天**（卡在 09-14） | 🔴 P0 | ✅ 已根治 |
| ② | **双盲区**：闸门 E 判据把它放「任一」位 ⇒ 陈旧**不阻塞**；`v8_health_check` 把它列低频豁免 ⇒ 陈旧**不告警** ⇒ 停更 4 天**全链零红灯** | 🔴 P0 | ✅ 已两端闭环 |
| ③ | 上一版修复自己引入的「读旧产物兜底」会产出「**历史明细 + 全新 update_time**」的伪新鲜产物 | 🔴 P0 | ✅ 已自纠（0 污染） |
| ④ | E 批在 `update_v8` 前被 **ws-guard** 判「工作区 ≠ origin/main」`exit 1` 中止 ⇒ 首次暴露：`v8_stage_gate.py` 是 **CRLF 脏 blob**（违反 `.gitattributes` 的 `*.py text eol=lf`） | 🔴 P0 | ✅ 已归正 LF |

---

## 1. ① 根因链（实测闭环，非推断）

| 步 | 实测证据 | 结论 |
|---|---------|------|
| 1 | 远端 `raw_data/backtest_tdx.json` = **76,078,046 B**（`sha fe205ffe9383`） | 产物含 **12 档 × 221 只逐笔明细** |
| 2 | 线上 `data/BACKTEST_TDX.js` = 10,276 B，`update_time = "2026-09-14 02:07:31"`，`republish_time = "2026-09-18 01:43:27"` | 09-18 重建过但**戳由 raw 透传** ⇒ 戳仍是 09-14（`_pick_ts` 语义）。前端读 `update_time` ⇒ 显示「4 天前」红灯 |
| 3 | 推送阶段 `POST /git/blobs` 报 `HTTP 422 Sorry, your input was too large to process`，8 次重试全败 | **超 GitHub 单文件上限** ⇒ 能跑完却推不上去的隐性停更 |
| 4 | 小九 09-14 半成品：紧凑化 126.9 MB → 72.6 MB + 加 **95 MB** 护栏 | **72.6 < 95 ⇒ 护栏从不触发** ⇒ 静默 4 天。护栏阈值必须**低于真实失败点**，否则形同虚设 |
| 5 | 消费方双证：`update_v8.py::_make_lite` 白名单只留 `update_time/summary/stocks_analyzed/...`；`export_optimized_strategy` 亦只读汇总 | `stocks` 明细 **零消费者** ⇒ 可从产品产物安全剥离 |

**修法（`algorithms/backtest_tdx.py`）**：
1. 产品产物 `raw_data/backtest_tdx.json` **只写汇总**（去 `stocks`）；
2. 逐笔明细改写入 **不入仓**缓存 `raw_data/_tdx_cache/backtest_tdx_stocks.json`（`.gitignore:41` 已覆盖，实测确认）；
3. 体积护栏 **95 MB → 5 MB**（真实失败点之下）；
4. `run_algorithms.py`：`backtest_tdx.py` 总超时 **5400s** + 静默预算 **3600s**（明细不入仓 ⇒ 每轮全量取 221 只日K，防 30min 默认超时误杀）；
5. 中间态快照「每只一写」→「**每 25 只一写**」（原 221 次全量 76MB 序列化，云端 runner 上写随即被清、无人读）。

---

## 2. ③ 自纠：禁「旧数据盖新时间戳」（本轮我自己引入又自己修掉）

**背景**：上面第 2 项修法最初写成「**优先读明细缓存，回退读旧产品产物**」，意图是让迁移首轮复用历史明细、不退化。

**实测缺陷**：主循环 `if key in stock_results:` … `continue` —— **对已存在的 key 整只跳过**。而迁移首轮线上 `OUT` 恰是**旧版含明细**的产物 ⇒ 结果 = **历史明细的统计 + 全新 `update_time`** ⇒ 前端显示「今日已更新」而数据实为历史，**直接违反首条铁律「数据新鲜真实」**。

**修法**：**永久移除对 OUT 的回退读取**；复用条件改为**两者同时满足**：
- ① `calc_time == 今天`（跨日缓存一律丢弃）
- ② 缓存文件 **2 小时内**写过（防「同日早盘缓存被晚间档复用」——早盘 K 线未收盘）

⇒ 云端新 runner 缓存不存在 ⇒ **必然全量重算**（数据最新）；同 runner 同日批内重试才复用（真断点续跑）。

**0 污染的实证**：发现时正在跑的 E 批 run `35282674747` 处于 checkout 阶段，**立即 `POST .../cancel`（HTTP 202）**，实测落 `conclusion=cancelled` 且 **step 9 `skipped`** ⇒ 算法链未执行、未产出、未推送。

---

## 3. ② 双盲区根治（两处联动，遵守不变式）

| 端 | 原状 | 现状 |
|---|------|------|
| **闸门** `.github/scripts/v8_stage_gate.py` | `E.items=[CRDS_BACKTEST, BACKTEST_TDX, BACKTEST_ALL_ALGOS]`，`need=2`，`must=[BACKTEST_ALL_ALGOS]` ⇒ BACKTEST_TDX 只在「任一」位 ⇒ 陈旧**不阻塞**就绪 | `must=[BACKTEST_ALL_ALGOS, BACKTEST_TDX]`（need 仍 2）⇒ 两项必须新，第 3 项 CRDS 不参与否决（**不引入「三项全中」过紧约束**） |
| **巡检** `v8_health_check.py::_LOW_FREQ_FILES` | 含 `"BACKTEST_TDX"`，理由「参数变更才重跑」**已过时**（现为 E 批每日产物）⇒ 陈旧降级为「>7 天才告警」 | **已摘除** ⇒ 恢复常规新鲜度判定 |

**✅ 不变式核验（`must ⊆ dedup_fetch_manifest.py::_ALWAYS_PUSH`，缺一即「永久不收敛」）**：
`data/BACKTEST_TDX.js` **已在** `_ALWAYS_PUSH`（该文件 L130，09-13 那轮已按「items∪must 全纳入」规则补入）⇒ 不会被去重器判「伪变更」丢弃 ⇒ `update_time` 能前进 ⇒ must 可满足。**这是提 must 的前置条件，已实测确认，非推断。**

**✅ 可达性核验（防 must 恒 STALE）**：它与 `BACKTEST_ALL_ALGOS` 同批同源产出；凌晨档由 `_cand()` 的「+24h」解释匹配（实测 `01:23 → ("2026-09-17", 25, 23)`，且 `25:23 ≥ 16:30`）⇒ 不恒 STALE。

---

## 4. ④ ws-guard 行尾脏 blob（本轮**首次暴露**，非本轮引入）

**现象**（E 批 run `35283174662`，step 11 内、`python update_v8.py` 之前）：
```
[ws-guard] 工作区 vs 远端 一致性检查
  [ref] 目标 = origin/main (2fa445da97)
  一致 21 个 / 不一致 1 个 / 缺失 2 个（共 24）
    🔴 不一致 .github/scripts/v8_stage_gate.py
  [ws-guard] git checkout origin/main -- <1 个文件>
  🔴 拉齐后仍不一致 1 个：['.github/scripts/v8_stage_gate.py'] → exit 1
🔴 工作区一致性守卫未通过 → 中止本次跑批（禁止用落后代码出产物）
```

**根因（三层实测）**：
1. `.gitattributes` 规定 `*.py text eol=lf`；
2. 但该文件**远端 blob 里存着 833 个 CRLF、0 个裸 LF**（我改之前的 `bd14a6bb` 版本即如此 ⇒ **历史脏 blob**）；对照：`v8_health_check.py` / `dedup_fetch_manifest.py` / `backtest_tdx.py` / `run_algorithms.py` / `update_v8.py` **均为纯 LF** ⇒ 它是唯一违规项；
3. ⇒ checkout 时按 `eol=lf` 规范化出 **LF**，与 **CRLF blob** 永不相等 ⇒ **`git checkout` 也修不好** ⇒ ws-guard `exit 1`。

**为何此前没暴露**：E 批长期被闸门判「已就绪 → 空转」（step 9 `skipped`），**从未真正跑到 `update_v8`**。本轮闸门提 must 后 E 批真正开跑 ⇒ 立即暴露。

**修法**：blob **归正为 LF**（55662 B，CRLF=0），零语义变化（仅删 `\r`）。推送前自算 git blob sha 与 GitHub 返回**一致**（`7d03921c88b0`）⇒ 内容自证。

---

## 5. 本轮 commit 清单（全部 Git Data API，逐字节回读 OK）

| commit | 内容 |
|--------|------|
| `9e04d5597e54` | `run_algorithms.py`：四量重跑 `_gate_hardwait_four_volume` 补 `env`（`V8_BACKTEST_YEARS=5`），防重跑写回 3 年降级档 |
| `174bac00c828` | `backtest_tdx.py` 瘦身（去明细/护栏 5MB/缓存优先）+ `run_algorithms.py` 预算（5400s/3600s） |
| `375c9f54725c` | `backtest_tdx.py` IO 优化（每 25 只一写） |
| `2fa445da97dd` | 4 文件：禁旧数据盖新时间戳（缓存双条件）+ 摘除低频豁免 + E.must 补项 + dedup 注释同步 |
| `f50fb959d4f8` | `logic.html` 同步 E 批 must 口径 + 双盲区根因（三件套之②） |
| `6b41f13dcdc9` | `v8_stage_gate.py` 行尾归正 CRLF→LF（根治 ws-guard 永久不一致） |

---

## 6. ⚠️ 请小九复核 / 待办

1. **ws-guard 检查清单含 2 个远端不存在的文件**：`algorithms/build_unlisted_panel.py`、`.github/scripts/v8_t1_guard.py`（实测 `content` API 返回 **404**）。当前仅告警级（不 fatal），但清单已过期 ⇒ 请确认是「应删清单项」还是「漏推文件」。
2. **仓库体积**：76 MB 的旧 `backtest_tdx.json` blob 仍留在 git 历史中（本轮只是不再产生新的大 blob）。若需压体积，属历史重写范畴，风险高 ⇒ **未擅动**，请主人另行拍板。
3. **交接记录规范**：本件已落 `docs/ops/handover/`。

---

## 7. 验收判据（唯一）

E 批新 run 跑完后：
- `raw_data/backtest_tdx.json` **size 降到 KB 级**（原 76,078,046 B）
- `data/BACKTEST_TDX.js` 的 `update_time` **前进到 09-18**
- 推送阶段日志**不再出现** `HTTP 422 ... 保留远程旧版本`

---
*阿狸咪的工程师 · 2026-09-18 07:00 CST*
