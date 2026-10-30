# HANDOVER · 小九给阿狸咪 · 2026-09-11 09:10

## 主题：9 张红灯卡「一劳永逸」根治 —— 闸门 READY_SPEC 盲区 + 5 孤儿脚本挂链

**指令来源**：主人 08:25 甩 3 张截图「怎么还是这么多失败和红灯！到底哪里出错了！马上一劳永逸式修复！」

**我的提交**：`b9606fb9c`（已推 main，head 现为 `35a7d23f4`）
**你（阿狸咪）同期提交**：`01f948afb`「根治金股池被洗空 P0」—— 已确认与我无冲突，你的修复已生效（见下文 §4）。

---

## 1. 9 张红灯清单（截图所见）

AI_INSIGHTS_COMPARE / BACKTEST_COMPREHENSIVE / FACTOR_AUDIT / FACTOR_PROGRESS /
INDEX_VALUE_FRAMEWORK / SECTOR_FUND_FLOW_TREND / SUSPENSION_ALERT / TOP10_DAILY /
VALUATION_PERCENTILE —— 全部显示「昨日」陈旧，本地实测均停在 **2026-09-10**。

---

## 2. 三层根因（全部实证，非推测）

### ① 5 个孤儿脚本从未挂进任何批次 → 5 卡停在 09-10

| 脚本 | 产物 | 位置 |
|---|---|---|
| `fetch_ai_insights_compare.py` | `raw_data/ai_insights_compare.json` | **`scripts/`** |
| `gen_factor_audit.py` | `raw_data/factor_audit.json` | **`scripts/`** |
| `gen_factor_progress.py` | `raw_data/factor_progress.json` | **`scripts/`** |
| `fetch_valuation_percentile.py` | `raw_data/valuation_percentile.json` | **`scripts/`** |
| `fetch_index_value_framework.py` | `raw_data/index_value_framework.json` | **`scripts/`** |

⚠️ **关键**：这 5 个脚本住在仓库根 **`scripts/`**，不在 `algorithms/`。

唯一载体是 `.github/workflows/v8_cn_fetch_experiments.yml`（cron `30 8 * * 1-5` = 16:30 CST），
而该 workflow **自创建起只触发过 1 次**（run#1，2026-09-10T13:01）**且失败** → 之后永久静默。

### ② 闸门 READY_SPEC 盲区 = `target_stage=NONE` 空转（9 卡集体红灯的**真凶**）

`.github/scripts/v8_stage_gate.py` 的 `READY_SPEC["B"]` 原本**只校验 3 个代表产物**：

```python
"B": {"items": ["data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js"], "need": 3}
```

而 B 批实有 **28 个脚本**、产出几十个 `raw_data/*.json`。当这 3 项鲜活、其余全部陈旧时：

```
target_stage=NONE
OUTCOME=skipped
reason="✅ 四批产物均已就绪 → 空转（合规，真成功）"
ready_A=3/3  ready_B=3/3  ready_D=1/1  ready_E=2/2
```

→ **闸门判「都齐了」→ 整链空转 → 9 张卡整日无人重跑。**

**这就是「六管线全绿却满屏红灯」的机制**：闸门只认 8 个代表产物。

### ③ experiments workflow 推送步**必失败**

`update_v8.py` 在工作区留下**未提交**改动（`raw_data/kline_cache/*.json` 等）→
`git push` 被拒 → 重试循环里：

```
git fetch origin main && git rebase origin/main
error: cannot rebase: You have unstaged changes.
```

→ 3 次重试全败 → `::error` 后 workflow 永久静默。

---

## 3. 修复内容（commit `b9606fb9c`，三文件）

### 3.1 `algorithms/run_algorithms.py`
- `STAGES["B"]` 链尾 + `ORDER` **成对**追加 5 脚本（**必须带 `scripts/` 前缀**，
  走 `run_algorithms.py:946` 的双层路径解析 `if script.startswith("scripts/") or script.startswith("v8/")`）
- `SCRIPT_TIMEOUT_OVERRIDE` 登记预算：ai_insights/factor_audit/factor_progress/index_value = 900s，
  valuation_percentile = 1200s（akshare 单接口）

### 3.2 `.github/scripts/v8_stage_gate.py`
```python
"B": {
    "items": [
        "data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js",
        "raw_data/ai_insights_compare.json", "raw_data/factor_audit.json",
        "raw_data/factor_progress.json", "raw_data/valuation_percentile.json",
        "raw_data/index_value_framework.json",
    ],
    "need": 5,     # 3 核心 + 5 新中至少 2
    "must": [],
}
```
> `check_ready()` 的判定是 `ready = must_ok and hit >= need`，故 8 项 / need=5 语义为
> 「3 个核心选股产物必须鲜活 + 5 个新收编产物至少再命中 2 个」。

### 3.3 `.github/workflows/v8_cn_fetch_experiments.yml`
- rebase 前先 `git add -u -- raw_data data index.html` + `git commit` 清掉 unstaged
- `git fetch` 失败不再被 `set -e` 中断重试循环
- rebase 失败降级 `git merge -X ours origin/main --no-edit`

---

## 4. 实证证据

### 4.1 闸门 A/B 对照（可复现）
```
[修复前口径] B ready=True  3/3  → target_stage=NONE（空转，9 卡红灯）
[修复后口径] B ready=False 3/8  → target_stage=B  （派发补跑，9 卡治愈）
             5 项 STALE 具名
```
本地重跑 5 脚本后：`B ready = True 8/8` —— 双向都正确。

### 4.2 线上 run 对照（决定性）
| run | head | step9「运行盘后算法链」 |
|---|---|---|
| #1713 | `86da49855` | **skipped** ← 空转真凶 |
| #1714 | `35a7d23f4` | **in_progress** ← 链真跑起来了 |

派发命令：`POST /actions/workflows/v8_algo_cloud.yml/dispatches`，`inputs={}`（留空由闸门自判）→ 返回 204。

### 4.3 5 个脚本本地实测全部 exit 0 且写出产物
```
ai_insights_compare.json    ut=2026-09-11 09:01:12
factor_audit.json           ut=2026-09-11 09:01:13
factor_progress.json        ut=2026-09-11 09:01:13
valuation_percentile.json   ut=2026-09-11 09:01:26
index_value_framework.json  ut=2026-09-11 09:01:20
```

### 4.4 静态一致性校验
`ORDER` 47 项 == `STAGES` 并集 47 项，`assert(_STAGE_UNION == set(ORDER))` 通过；
**47 个脚本路径全部可解析**（含 5 个新的 `scripts/` 前缀路径）。

---

## 5. 关于你 08:20 我记的两项「新阻断」——**已修正**

- ❌ **我 08:20 记的「TOP10 因 gold_pool.stocks 被洗空」是旧快照结论，已失效。**
  你的 `01f948afb` 修复已生效：`raw_data/gold_pool.json` 现为 **184 只**、
  `update_time=2026-09-11 08:42:26`、带 `restored_from` 字段。感谢。
- ✅ **BACKTEST_COMPREHENSIVE 是 `_pure_pc` 保护副作用**（`update_v8.py:1110-1115`）——
  仍需 `--category post_close` 构建才会重写 js。**我未改**（改回去会让 9/10 最终推荐回退事故重演），
  随本轮 B/E 批跑完 + 云端 build 自愈。
- ✅ **盘前跨层闸门 100% 阻断部署**（`v8_verify_layer_parity.py`）——**仍待你/主人拍板方案**，本轮未动。

---

## 6. 需要你注意 / 对齐的点

1. **改 `run_algorithms.py` 的 STAGES 必须成对改 ORDER** —— `assert(_STAGE_UNION == set(ORDER))`
   是**模块级**断言，只改一边 = import 即崩 = 整链 0 产出（历史已犯 2 次）。
   校验请用 `ast` 静态解析比对，**不要 import**（import 会执行整个模块）。
2. **新增脚本先 `find` 确认位置** —— `algorithms/` 无前缀，`scripts/`、`v8/` **必须带前缀**。
   我首轮就漏了前缀，靠「逐条验证路径可解析」自检抓出。
3. **`v8_cn_fetch_experiments.yml` 现已冗余但保留**：5 个脚本主力路径改为 B 批，
   该 workflow 作为独立兜底保留（推送步已修）。若你判断应停用/删除，请提出——
   **我不擅自删 workflow**。
4. **闸门 `need` 语义**：`hit >= need` 是「命中数」而非「必须全中」。
   若你希望 5 张新卡**必须全中**（`need=8`），告诉我，我改——但需注意
   `valuation_percentile` 依赖 akshare，接口不稳时会把整链锁死，故我取了 5。

---

## 7. 遗留 / 待主人拍板

| # | 事项 | 状态 |
|---|---|---|
| 1 | 盘前跨层闸门豁免方案（A/B/C） | **待拍板**，本轮未动 |
| 2 | B 批 `need=5` 是否收紧为 8（全中） | 待确认 |
| 3 | `v8_cn_fetch_experiments.yml` 是否停用 | 待确认 |
| 4 | BACKTEST_COMPREHENSIVE 的 `_pure_pc` 保护是否调整 | **不动**（防 9/10 事故重演） |

---

---

# 【补篇】09:10 → 10:05 第二轮深挖：又挖出两层阻断（均已根治）

第一轮修完（挂链 + 闸门 8 项 + experiments 推送步）后做了端到端推演，发现**还差两环**
才能真正让卡片转绿。补记如下，避免你按第一轮的结论判断"已经好了"。

## 8. 阻断④：dedup 去重器把「内容稳定」的卡当伪变更丢掉 → 时间戳永不前进

**这是最隐蔽的一层。** `.github/scripts/dedup_fetch_manifest.py`（仅 `v8_algo_cloud.yml`
推送步使用）的判据是「**剥掉时间戳字段后内容是否改变**」。

对**数据内容天然稳定**的研究/审计类卡片，剥掉时间戳后逐字节相同 → 判「伪变更」→ **永不推送**。

实测（本地文件 vs `origin/main`，都过 `strip_ts()` 再逐字节比）：

```
raw_data/ai_insights_compare.json     ✅ 内容真变 → 会推送
raw_data/valuation_percentile.json    ✅ 内容真变 → 会推送
raw_data/factor_audit.json            ⚠️ 仅时间戳差异 → 被丢弃
raw_data/factor_progress.json         ⚠️ 仅时间戳差异 → 被丢弃
raw_data/index_value_framework.json   ⚠️ 仅时间戳差异 → 被丢弃
```

**为何内容稳定**：`factor_audit` 审计的是 `generate_top10.py` 的**源码**（源码不改则内容不变）；
`factor_progress` 读 `factor_audit`；`index_value_framework` 依赖 `INDEX_HISTORY` 的刷新节奏。

**两层后果**：
1. 前端恒显示「昨日」红灯 —— 卡片新鲜度就是 `update_time`，而它永不前进；
2. 闸门 `READY_SPEC` 读同一批文件判就绪 → 永远 STALE → 该批（60~90min）**反复重跑**，永不收敛。

**修复**：新增 `_ALWAYS_PUSH` 白名单（5 卡 raw + 5 卡 js）→ 强制推送。
单文件 1~8KB，开销可忽略。**注意：原 `v8_cn_fetch_experiments.yml` 本来就是无条件
`git add + push` 这几个文件**，所以强制推送正是原始设计意图。

## 9. 阻断⑤：A 批闸门**完全同源**的盲区（不是 B 批独有）

我原以为只有 B 批的 `READY_SPEC` 太窄。**A 批一模一样**，而且实测更严重。

A 批 `READY_SPEC` 只校验 3 个代表产物（`LHB_DATA` / `sector_rs` / `stock_profile`），
而 A 批实有 **12 个脚本**。经 Contents API 直查 main 实证，这 3 项鲜活，但另有 **6 个产物
停在 09-10**：

```
fundamental_quality.json     09-10 06:12
stock_quote.json             09-10 15:03
inst_trade.json              09-10 06:17
suspension_alert.json        09-10 06:23   ← 主人截图红灯
nt_data.json                 09-10 06:24
sector_fund_flow_trend.json  09-10 06:25   ← 主人截图红灯
```

→ 闸门判「A 已就绪」→ 这 6 个产物整日无人重跑。

**修复**：`items` 3 → 10（纳入 A 批全部**可读时戳**的产物），`need=7/10`。

⚠️ **有意不含 `stock_names.json`**：该文件**无** `update_time` / `data_date` 字段，
`read_ut()` 恒返回 `None` → 会永久计 MISS 从而拉低命中数（已实测确认）。**新挂产物前
务必用 `read_ut()` 验证能否读到时戳**，否则等于给自己挖坑。

`need=7` 而非更严的理由：A 未就绪时闸门**只跑 A**，会挡住 B/D/E，所以不能设得过严
—— 需容忍 3 项失败仍放行。T+1 日（周六/假期首日）走既有放宽分支（`need=1`），不会死锁。

## 10. 阻断⑥（连带）：B 批 `need` 必须 ≥7，否则 3 张卡永远补不上

dedup 修好前，一轮 B 批跑完线上只得 3 核心 + 2 张 = **5/8**。若 `need=5`，闸门会据此判
「B 已就绪」→ 空转 → 另 3 张（`factor_audit` / `factor_progress` / `index_value_framework`）
**永远补不上，恒红**。

→ `need` 5 → **7**（只容忍 1 项不新鲜）。8 项中唯一易碎的是 `valuation_percentile`
（依赖 akshare 外部接口），7 恰好容忍它单独失败而不把整链锁死。

## 11. 完整管线（四环，缺一不可 · 现已全部打通）

| 环 | 内容 | 提交 |
|---|---|---|
| ① | 5 脚本挂进 B 批 → raw 每日生成 | `b9606fb9c` |
| ② | 闸门 `READY_SPEC` A=10项/B=8项 + `need` → 链不再误判空转 | `b9606fb9c` / `3682d70f` / `babc6f72` |
| ③ | `dedup` `_ALWAYS_PUSH` 强制推送 → raw 时间戳真正到达 main | `057eab8d8` |
| ④ | `v8_cn_fetch_cloud` 17:20/18:20/19:20 的 **post_close 构建** → `data/*.js` 重生成 → 前端转绿 | 既有，已核 |

**④ 为何关键**（易被忽略）：`update_v8.py:1139` 的 `_pure_pc` 保护决定
「纯盘后产物只在 `--category post_close` 构建时才重写」。
而算法链完成触发的 build 走 `--detect-changes`，**`category` 为 None → 必然跳过 pure_pc 卡片**。
唯一会跑 `--category post_close` 的是 **cn_fetch 链（17:20/18:20/19:20 CST）**
和 experiments workflow。且 `v8_build_deploy.yml` 的 schedule **已被有意移除**
（见该文件 17-19 行：与算法链竞态，用旧 raw 洗新 data）——**不要试图把 schedule 加回来**。
**结论：raw 更新后，`data/*.js` 要到当天 17:20 后的 post_close 构建才会跟着更新。**

## 12. 闸门实测对照（同一时刻 2026-09-11 09:50 并发跑两版）

```
[修复前] target_stage=NONE | reason=⏸ 未到交易日 2026-09-11 盘后链起点（16:00，现 09:50），
                              且上一数据日已无未完成批次 → 空转（合规）
[修复后] target_stage=A    | reason=A 未就绪(3/10) → 跑采集批
```

**「空转（合规）」正是主人看到的「满屏红灯却六管线全绿」的原始形态。**

**另一处需你知晓（我未擅自改）**：`check_ready` 要求 `c[0] == day`（产物日期必须**等于**
数据日）。后果：09:00–15:59 时段触发的「补跑上一数据日」即使跑完，产物日期是**今天**，
仍无法满足**昨天**的判定 → 该时段内每次派发都会再判「上一日未完成」。
**实践中不构成死循环**：派发只在 16:10–01:00（本机接力推进器）+ 云端 cron ≥16:40，
09:00–15:59 **没有派发**。但如果你后续要在白天加派发档位，需一并处理这个语义。

## 13. 本轮我实际推送的提交（作者署名：小九的股票专家）

| 提交 | 内容 |
|---|---|
| `b9606fb9c` | 5 孤儿脚本挂 B 批 + 闸门 B 批 3→8 项 + experiments 推送步修 rebase |
| `057eab8d8` | dedup `_ALWAYS_PUSH` 强制推送白名单 |
| `babc6f72` | 闸门 B 批 `need` 5→7 |
| `3682d70f` | 闸门 A 批 3→10 项 + `need=7` |
| `1f50a42d` | 5 个实验卡 raw 实测数据（09:30 新鲜，经 `api_push_raw` 推） |

> 补充约定：本机（小九）改动署名统一为**「小九的股票专家」**（git `user.name` 已设，
> commit message 亦带标识）。你那台机对应「阿狸咪的股票专家」，便于双机辨认。

## 14. 待你拍板 / 建议你接手的

| # | 事项 | 我的建议 |
|---|---|---|
| 1 | 盘前跨层闸门 100% 阻断部署（`v8_verify_layer_parity.py`） | 加时段白名单：盘前/盘中类只 warn，post_close 仍硬阻断 |
| 2 | `check_ready` 的 `c[0] == day` 严格等值语义 | 若白天加派发档位需放宽为「≥ 数据日」；现不改 |
| 3 | BACKTEST_COMPREHENSIVE 的 `_pure_pc` 保护 | **不动**（改回去会让 9/10 最终推荐回退事故重演） |
| 4 | `v8_cn_fetch_experiments.yml` 是否停用 | 保留作兜底（推送步已修）；5 脚本主力已在 B 批 |

**小九的股票专家 · 2026-09-11 10:05 CST**
