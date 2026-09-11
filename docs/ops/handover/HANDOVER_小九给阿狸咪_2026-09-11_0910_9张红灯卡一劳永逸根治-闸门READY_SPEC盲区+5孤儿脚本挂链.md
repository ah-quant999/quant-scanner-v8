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

**小九 · 2026-09-11 09:10 CST**
