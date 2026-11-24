# 小九 → 阿狸咪 ｜ P0 补充：云端链「回退同步路径」加根约束（保住 `data/`）

- **签发**：小九的工程师（作者：小九机 lemoncat-cn）
- **采集时刻**：2026-09-21 00:07（北京时间 +8；本机 Python `datetime.now()` 实取）
- **关联 commit**：`56fe8f9ce656`（父 `becfcb1aad4f`）
- **本文性质**：已上线改动的「改后三件套」交接 + 待你侧确认项

> 本文所有结论均为**截至上述采集时刻实测**。凡涉及「后续会怎样」一律给**可跑的复核命令**，不作预测式表述。
> **不写本文自身所在提交的 sha** —— 请用文末命令现取。

---

## 零、一句话结论

你 09-20 的 CRLF 根治二期（`b854ccb54`）与我这份改动**互不冲突**，但你**未纳入** `.github/workflows/`。
我核到云端链的「API 回退同步」**近期 3 轮实际都在跑**（见 §二），而该路径**没有根约束** ⇒
一旦 root tree 截断/某层异常，会**静默少同步**（`data/` 子树丢失即复现我 09-20 定性的因子融合永久降级）。
已加 `ROOT_REQUIRED` 根约束 + 缺根硬失败，**已上线**。

---

## 一、我的改动（就一处，逐字节可验）

| 项 | 值 |
|---|---|
| 文件 | `.github/workflows/v8_algo_cloud.yml` |
| 改动量 | **+26 / −0**（纯新增，无删改） |
| 父 → 我 | `becfcb1aad4f` → `56fe8f9ce656` |
| 线上真身 | blob `a2c554fa4bb73e97a33314ad2a2c9c52f56ba508` / **70081 B** |

**新增内容（两段）**：

1. `ROOT_REQUIRED = ("algorithms", "data", "raw_data", "scripts")`
2. 同步收尾后自检：缺任一顶层子树即 `raise SystemExit("root-required check failed: missing top-level subtree(s) %s, refusing partial sync")`

**为什么必须硬失败而非仅告警**：该步的产物会被后续「唯一推送」直接推上 main。
**半量同步比不同步更危险** —— 会把残缺工作区树推到线上。

---

## 二、为什么这条路径不是「理论隐患」而是**线上实际在走的路**

🔴 **判据（关键）**：该回退步带 `if: steps.co.outcome == 'failure'`，且 `actions/checkout` 带 `continue-on-error: true`
⇒ **步骤 `conclusion` 恒报 `success`，不可信**（我库里已记该坑）。
**真判据 = 步骤耗时**：`skipped` 为 0s；**真跑了是 1000s+**。

截至 2026-09-21 00:07 实测（`v8_algo_cloud.yml` 最近 5 轮）：

| run | created(UTC) | 整轮 | `📥 Checkout 源码` | `📥 回退·经 GitHub API 同步源码` |
|---|---|---|---|---|
| #1997 | 2026-09-20T15:37:47Z | success | success | **success** |
| #1996 | 2026-09-20T14:11:03Z | success | success | **success** |
| #1995 | 2026-09-20T13:12:35Z | success | success | **success** |
| #1994 | 2026-09-20T07:31:07Z | success | success | **skipped** |
| #1993 | 2026-09-20T07:21:26Z | failure | success | **success** |

> 实测：最近 3 轮（#1995/#1996/#1997）回退步均**真跑**（1100s+），#1994 为 `skipped`（0s）。
> ⇒ **云端链近期实际走的就是这条回退路径**，不是备用理论分支。

---

## 三、已落地修复的核验（截至 2026-09-21 00:07 实测）

🔴 **分清楚「已 push」与「已生效」** —— 本条只是「代码已在线上真身」，不等于「已跑过一轮」。

| 核验项 | 方法 | 实测 |
|---|---|---|
| 真身含改动 | 拉 main 的 blob | `ROOT_REQUIRED` ×1 ✅ |
| `data` 在必需清单 | 字符串 | `"data", "raw_data", "scripts"` ✅ |
| 缺根硬失败 | 字符串 | `refusing partial sync` ✅ |
| **逻辑真跑**（非仅字符串） | 抽真身源码喂 5 组假数据 | 正常放行 ×2 / 缺 `data/` 硬失败 / 缺 `raw_data/` 硬失败 / 多缺硬失败 ✅ |
| 结构未受损 | YAML 解析 + 步骤数 | 顶层键不变、`jobs=algo`、**steps 16→16** ✅ |
| 未被覆盖 | GitHub compare API | `behind_by=0` ✅ |
| 唯一改动 | 逐文件 blob 比对 | 仅该文件；同提交内 3 个 `+0/-0` 文件 **blob 完全相同**（GitHub 显示行为，非真实变更）✅ |

**「逻辑真跑」细节**（照抄线上真身语义，非改写）：

| 场景 | `missing` 结果 | 判定 |
|---|---|---|
| 正常全量（`data/` 等均在） | `[]` | 放行 ✅ |
| `data/` 整目录丢失 | `['data']` | 硬失败 ✅ |
| `raw_data/` 整目录丢失 | `['raw_data']` | 硬失败 ✅ |
| 仅剩 `algorithms/`+根文件 | `['data','raw_data','scripts']` | 硬失败 ✅ |
| 边界：只有目录条目（tree 名不带尾斜杠） | `[]` | 放行 ✅ |

---

## 四、本轮我**未**动的东西（避免你重复劳动 / 误判）

| 项 | 状态 | 说明 |
|---|---|---|
| `.github/workflows/*.yml` 行尾 CRLF→LF | **你做的，我未回改** | 追到翻转点 = **09-20 17:35 `4ad886b407`**（`fix(eol)`，第一期）；`926c1d0eb3`(17:19) 仍 CR=939。我 23:1x 首轮补丁因**基线漂移预检**（本地 blob `21f452c4` ≠ 线上 `177f7588`）自动放弃，未覆盖你 |
| `.gitattributes` / `raw_data/history/*.json` / `data/*.json` | **你的 CRLF 二期，我未动** | 见你 `2313` 交接件 |
| `v8_algo_cloud.yml` 其余 15 步 | **未动** | 仅 +26 行新增 |

---

## 五、待你侧确认 / 复核（只给可跑命令，不作承诺）

### 1. `ROOT_REQUIRED` 的取值是否符合你对「必需子树」的定义
我取 `("algorithms", "data", "raw_data", "scripts")`。
理由：这 4 个是算法链直接的输入/输出面。
**若你认为 `v8/` 也应纳入**（实测 `want` 含 `v8` 8 条），请直接改这一行——它是单一常量，改一处即可。

### 2. 🔴 请你评估：回退步耗时已逼近超时红线（我无法单独判定）
- 该步 `timeout-minutes: 25`（=1500s）
- 实测该步耗时：**1124s / 1106s / 1111s**
- 实测全量 `want` 条数：**1293 条**（`raw_data` 894 / `data` 125 / `algorithms` 85 / `scripts` 56 / 根 85 / 其余 48）

⇒ 余量约 **376s**。**加根约束不增加下载量**（只是收尾自检，O(1)），但这条余量本身偏薄。
**是否需要**提高 `timeout-minutes` 或压缩 `want`（如把 `raw_data/kline_cache` 之外的大目录也剪掉），请你定。

### 3. 心跳写入侧收口（你在 `2313` §六③ 点的，我未动）
你在 `10b6144a55` 已做 `fold_eol` 写入侧三处收口。
我这份改动**不涉及** `fold_eol`，无需你二次处理；仅确认一下**三方对齐**无缺角。

---

## 六、可跑复核命令（逐条可直接执行）

```bash
# ① 线上真身含根约束（应 =1）
curl -s https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/.github/workflows/v8_algo_cloud.yml \
  | grep -c 'ROOT_REQUIRED = ("algorithms", "data", "raw_data", "scripts")'

# ② 缺根硬失败在位（应 =1）
curl -s https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/.github/workflows/v8_algo_cloud.yml \
  | grep -c 'refusing partial sync'

# ③ 我的提交未被覆盖（status=identical/ahead, behind_by=0）
gh api "repos/ah-quant999/quant-scanner-v8/compare/56fe8f9ce656...main" \
  --jq '"\(.status) ahead=\(.ahead_by) behind=\(.behind_by)"'

# ④ 行尾：该文件当前应为纯 LF（你的归一化成果，别被我改回 CRLF）
curl -s https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/.github/workflows/v8_algo_cloud.yml \
  | tr -cd '\r' | wc -c     # 期望 0

# ⑤ 回退步是否真跑（看耗时，别看 conclusion；skipped=0s，真跑=1000s+）
gh api "repos/ah-quant999/quant-scanner-v8/actions/workflows/v8_algo_cloud.yml/runs?per_page=5" \
  --jq '.workflow_runs[] | "\(.run_number) \(.created_at) \(.conclusion)"'

# ⑥ 现取本文自身所在提交（本文不写死自己的 sha）
git log --oneline -1 -- docs/ops/handover/
```

---

## 七、遗留给主人的非阻断项（非本次交接责任）

1. **cn 链 P0 尚未被任何一轮 run 执行过** —— 截至 2026-09-21 00:07，`data/FINAL_RECOMMEND_DATA.js` 的
   `update_time` 仍为 `2026-09-20 17:58:27`，`factor_chain.skip_reason` 仍为「FACTOR_LAB.js 缺失/陈旧」。
   `v8_algo_run.yml` 最近一轮为 `#45`（09-20 09:13Z→10:50Z），**在该修复（`9d989f5f`，09-20 14:48Z）之前**。
   ⇒ **不得判定为「已修复生效」**，须等下一轮 cn 链跑完再看（复核命令：拉 `data/FINAL_RECOMMEND_DATA.js` 看 `factor_chain`）。
2. 上述 §五.2 的超时余量属**主人拍板项**。
