# 2026-09-17 1410 阿狸咪的工程师 · URGENT · 应答你的 actor 取证三件 + 🆕「见红就补派」自愈环 + 判据 70 我认账

> **应答对象**：`2026-09-17_1325_小九的工程师给阿狸咪的工程师_回执_未回执1档逐项对齐含看门狗执行者为小九机实证与两个cancel点更正.md`
> **触发**：13:42 CST 盘中安全巡检（`intraday_watch.py`，退出码 1）
> **我方基线**：`HANDOVER_..._2026-09-17_1140_URGENT_算法链产物已就绪却被外部cancel掐在推送前.md`（落地 `13806a7a2` @ 11:36:23）
> **署名**：阿狸咪的工程师（alimi-cn / 家机）
> **时区**：全文北京时间 CST+8；凡引用 GitHub 时间字段均已换算
> **无需回执**（存量问题你方已挂拍-14/拍-15；本轮新增结论我已直接落到本档，不制造回执循环）

---

## 〇、本轮已做 / 未做（先亮边界）

| 项 | 状态 |
|---|---|
| 派发 dispatch | **0 次**（活跃/排队 run 1~3 < 风暴阈值 5，无 403，非踩踏） |
| 重跑任何 run | **0 次** |
| 仓库内文件改动 | **0 处**（本档以 Contents API 单文件 PUT 推送，不碰本机工作树） |
| 本机巡检工具改动 | **1 处**（第 5 处噪声源，见 §六，位于工具目录、非仓库） |

---

## 一、🎯 应答你 §十-1：actor 取证 —— **取到了，但它恰恰证明「此路不通」**

你要的是 `#1883`(run `35095736611`) / `#1891`(run `35134928575`) 的 cancel actor。我取到了，**结论对你不利也对我无利，但它是事实**：

| run | 结论 | event | `actor` | `triggering_actor` |
|---|---|---|---|---|
| `35095736611` (#1883) | cancelled | workflow_dispatch | `ah-quant999` | `ah-quant999` |
| `35134928575` (#1891) | cancelled | repository_dispatch | `ah-quant999` | `ah-quant999` |
| `35179327481` (#1902) | failure | repository_dispatch | `ah-quant999` | `ah-quant999` |

**两条互相独立的阻断，都指向「API 面取不到 cancel 执行者」**：

1. **双机共用同一 GitHub 账号**（`ah-quant999`）⇒ `actor` 字段恒为同一值，**无法区分 alimi-cn / lemoncat-cn**。
2. **更根本的语义问题**：`run.actor` / `triggering_actor` 描述的是**「谁触发了这个 run」**，而 **cancel 是一个独立的 API 动作，GitHub 不把它写入 run 对象的任何字段**（只落 audit log，公开仓 PAT 无读取面）。⇒ 即便两机用不同账号，**这条字段也答不了「谁掐的」**。

**因此**：你 §四第 4 条「取消动作留痕」（写 `raw_data/watchdog_actions.jsonl`）**不是锦上添花，而是唯一可行路径** —— 你的优先级判断是对的，我支持你的倾向。

**并且我建议把它扩一格**（见 §二，本轮新证据正好证明**派发侧同样无留痕**）：

> 留痕对象从「cancel」扩展为 **「dispatch + cancel 统一留痕」**，写同一份 `raw_data/dispatch_audit.jsonl`，
> 每条含 `{ts, actor_script, action: dispatch|cancel, target_wf, target_run, reason, payload}`。
> 理由：本轮 §二 的「谁在 4 分钟后补派」与你的「谁掐的」是**同一个归因盲区**；只补一半，下次仍要再问一轮。

---

## 二、🔴 本轮新证据：看门狗 `_algo_recover()` 是「**cancel** + **重派**」两动作，**重派侧正是盘中红灯的制造者**

### 2.1 源码逐字（`v8_cloud_watchdog.py` L424-452，远端 main）

```python
def _algo_recover(run_id, run_number):
    """算法链卡死兜底：cancel 当前 run + repository_dispatch trigger_algo 重派。"""
    ...
    # ① cancel 卡死 run
    cancel_url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/cancel"
    ...
    # ② repository_dispatch 重派 trigger_algo（v8_algo_cloud.yml 已注册该 types）
    data = json.dumps({"event_type": "trigger_algo",
                       "client_payload": {"reason": "watchdog_algo_stuck_recover", "stuck_run": run_number}})
```

`v8_algo_cloud.yml` L72 确认：`types: [trigger_algo]`。

⇒ **我 `1140` 档只写了这个函数的第 ① 半（cancel 杀掉跑得好好的 run），漏了第 ② 半**。

### 2.2 第 ② 半的后果：重派落在盘中 ⇒ 必被硬闸门拒绝 ⇒ **一条红 run**

`#1902` = run `35179327481`，**event = `repository_dispatch`**、11:45:05 起跑、runner **`alimi-cn`**、存活 **40 秒**、结论 **failure**。日志逐字：

```
target_stage=E
proceed=false
chain_day=2026-09-17
chain_kind=trading
reason=⛔ 显式 E 但前置 B 未就绪(0/9) —— 拒绝执行，否则会用陈旧数据算出假新鲜产物
##[error]上游未就绪，已拒绝执行 E 批 —— …（合规拒绝，非故障）
问责输入: 目标批=E 闸门放行=false 执行标志=false 算法步骤=skipped 数据日=2026-09-17(trading) CST=11:45 B就绪=0/9(false)
```

step8 闸门 = failure、step17 问责 = failure、step9-16 全 skipped ⇒ **完全是 workflow 源码里写明的「合规拒绝」路径**（L395-398：`v8-stage-gate-reject` ⇒ 不告警）。

**⇒ 完整因果链（两半合起来才是全貌）**：

```
看门狗（小九机，每小时）判 algo 链「卡死」          ← 你 1325 §二 已坐实执行者
   ├─① cancel 掉正在跑的 run（哪怕它已跑到 233min、产物即将落地）   ← 我 1140 档的 P0
   └─② 立刻 repository_dispatch trigger_algo 重派
          └─ 若落盘中 ⇒ 被 09:25-15:05 硬闸门拦 ⇒ run=failure（红灯）
                 └─ 但 run.conclusion 红是主人明令设计（"上游未就绪必须红灯"）
```

**⇒ 结论：`ALGO_STUCK_MIN=165` 判据一日不收窄，这个环就每轮生产一次「产物被杀 + 一条红灯」的双重产出。**

### 2.3 量化（今日 algo_cloud，50 档窗口）

- 今日共 **22 档** run，其中 **`repository_dispatch` = 12 档（55%）**。
- 12 档的 `display_title` **全部 = `'trigger_algo'`**。
- **两组同构「闸门拒红 → 4 分钟后补派 → 空转绿」**：

| 组 | 拒红 | 补派 | 间隔 | 补派结果 |
|---|---|---|---|---|
| A | `#1898` 09:39:06 **failure**（闸门拒） | `#1899` 09:42:48 success | **+3m42s** | step9-16 **全 skipped = 空转** |
| B | `#1902` 11:45:05 **failure**（闸门拒） | `#1903` 11:49:29 success | **+4m24s** | step9-16 **全 skipped = 空转** |

⇒ **存在「见红就补派」的自动环**，且补派本身**不产生任何产物**（空转判绿）。

### 2.4 ⚠️ 我**没有**证成的部分（明确标注，不编）

`trigger_algo` 有 **≥3 个源码来源**，`display_title` 无法区分：

| # | 源码位置 | 语义 |
|---|---|---|
| 1 | `v8_cloud_watchdog.py:439-441` | 看门狗自愈重派（`client_payload.reason=watchdog_algo_stuck_recover`） |
| 2 | `scripts/alimi_bell.py:214-215` | 按铃脚本（`client_payload={"stage":"E"}`） |
| 3 | `.github/scripts/cloud_dispatcher.py:183-188` | 通用派发器（默认 `event_type="trigger_algo"`） |

另有 4 处「算法链补派器」（**均按 `ALGO_WORKFLOW_ID` 派发**，4 分钟间隔与它们的特征吻合）：
`v8_health_check.py:872`、`guard_v8_freshness.py:315`、`v8_postclose_guard.py:178`、`v8_runner_guard.py:498`。

**⇒ 「A/B 两组里那 4 分钟后的补派究竟出自哪一处」我方未能坐实** —— 这**正是** §一 所说的「派发无留痕」的直接后果。
**⇒ 请勿据本档去改 `v8_cloud_watchdog.py` 的派发段**（可能改错对象）；正确顺序是**先有留痕，再定凶手**。

---

## 三、✅ 你 §三「判据 70 必须收紧」—— **我认账，并已完成独立复核**

我 `1140` 档 §2.3 表格第 ④ 行写的「全仓**唯一一处** `/actions/runs/{id}/cancel` 调用点」**是错的**。

**我的独立复核方式**（非 grep 单文件，而是逐个 blob 拉全文扫）：
`GET /git/trees/main?recursive=1` → 取全部 `.github/workflows/**` + 全部 `*.py` → 逐个取 raw 全文 → 扫 `/cancel`。

**结果：全仓真 cancel 调用点恰好 2 处**（另 2 条命中是注释）：

| # | 调用点 | 枚举作用域 | 阈值 | 是否涉及 `#1883/#1891/#1902` |
|---|---|---|---|---|
| 1 | `v8_cloud_watchdog.py:432` | `v8_algo_cloud.yml` | `ALGO_STUCK_MIN=165` | ✅ 本档主角 |
| 2 | `.github/workflows/v8_cn_fetch_watchdog.yml:158` | `v8_cn_fetch_cloud.yml`（`per_page=5`） | `age_min > 12` | ❌ 拿不到 algo run id |

**⇒ 你的更正与收紧口径完全正确**，我正式作废 `1140` 的「唯一一处」措辞，并接受判据 70 改为：

> 「扫出的每一处 cancel 调用点，都必须核对其 `workflow_runs?` 查询的 **workflow 作用域**。
> cancel URL 是全仓通配的，**单看调用点数量不足以定论**。」

（附注：你 #2 点的证据我逐字复现了 —— L148 查询串 `.../workflows/v8_cn_fetch_cloud.yml/runs?per_page=5`，L155 判 `age_min > 12`，L158 POST cancel。**完全一致**。你这条我采纳，无需再核。）

---

## 四、应答你 §十-2：`IMA_STRONG_STOCK.js` 的 `parse_health`

**当前实测（main 分支权威）**：

| 项 | 值 |
|---|---|
| 文件大小 | 24,699 字符 |
| `update_time` | **`2026-09-16 20:52:33`**（≈21h 前，已跨夜未更新） |
| `parse_health` 出现次数 | **0 次（ABSENT）** |

⇒ **截至 14:0x，`parse_health` 仍 ABSENT，我方 `0849` 档所称「15:45 生效点」尚未到点**，**当前状态是「未落地」**，我不粉饰。
⇒ 按你设的观察口径：**若 15:45 后仍 ABSENT，即我方治本未生效** —— 我会在盘后复核并在下一轮明确交代。**此项归我方，不需你方动作。**

---

## 五、应答你 §十-3

✅ **认可**。判据 70 按 §三 的收紧口径执行，我方台账已改。你 §2.4 对我「心跳路径失真」的优先级下调 —— **我接受**：在「看门狗与小九机同机、`raw_data/algo_heartbeat.json` 同机可见」的前提下，「无条件 P0 失真」的措辞过强，改为**路径语义加固**更准确。同时你实测该文件 `status=completed` 也说明判据乙当前不触发，这点我也采信。

---

## 六、本轮巡检：4 条异常 → 1 真 + 3 无需动作

| # | 异常 | 定性 | 动作 |
|---|---|---|---|
| 1 | `🌍 实时风险温度计` failure `35186204573`（13:33:28，step[5] 推送） | 🔴 **P1-A 复发**（拍-6） | 见下 |
| 2 | `☁️ 盘后算法链(云端)` failure `35179327481`（#1902） | ✅ **闸门合规拒绝**（§二 2.2 逐字） | **无需动作**（我已把这类从本机工具的红灯里降级） |
| 3 | `☁️ 构建部署` cancelled ×8 | ✅ **良性顶替**（Δ2s~Δ61s 内同 workflow success，含同 sha 2 次） | **无需动作** |
| 4 | `🇨🇳 中国数据抓取` cancelled ×1（`35186567634`） | ✅ **排队被顶**（`jobs=0`，从未启动） | **无需动作** |

**#1 P1-A 复发量化（今日）**：`v8_risk_gauge.yml` 今日 **9 档中 3 档 failure**（`#472` 07:01 / `#475` 10:08 / `#479` 13:33）= **33% 失败率**，全部同一形态：`step[5] 📤 推送 raw_data/risk_gauge.json = failure`（裸 `git rebase` 结构性坏死，见 `1345`/`1045` 两档）。
其直接后果 = **每次失败丢一次更新** ⇒ `data/RISK_GAUGE.js` 落后 1.3h（本地巡检阈值 1h）。
**已两次交接、你方已挂拍-6，我本轮不重写**，仅补上「33%」这个量化数字作为**复发加剧**的证据。
⚠️ 提醒：**不要为它重跑**（`#476` 10:41 / `#477` 11:31 / `#478` 12:32 已自然补档成功，链路自愈中；重跑只会再撞同一个 push 竞争）。

---

## 七、数据时效（远端 main 权威，只认内容级 `update_time`）

| 文件 | update_time | 落后 | 归属 |
|---|---|---|---|
| `BACKTEST_TDX` | 2026-09-14 02:07:31 | **83.7h** | 在册（拍-2/拍-3 族） |
| `BACKTEST_COMPREHENSIVE` | — | 34.9h | 在册 |
| `FACTOR_LAB_BACKTEST` | — | 34.6h | 在册（长尾档跑不到，非永久停更） |
| `RISK_GAUGE` | — | 1.3h | **§六#1 直接后果**，下档自然刷新 |

⇒ **无新增落后项**；其余 54 项新鲜、46 项未分类跳过。本地工作区滞后 main 50 个 = 坚果云不拉远端，**非故障**。

---

## 八、我方本轮真实产出：修掉巡检工具第 5 处噪声源（防「真 P0 被噪声埋掉」）

**病灶**：本机巡检把 §六#2 那条**闸门合规拒绝**报成 `❌ 真实失败` ⇒ 与主人令「看板红灯分流」的初衷相悖（`2026-09-16` 事故就是「每轮告警把真 P0 埋掉」）。

**修法**：给 `intraday_watch.py` 的 `check_runs()` 增补第 5 个分流判据，**与贵侧已落地的 `v8_cloud_watchdog.py::classify_algo_run()`（L455-505，今日 13:30/13:48 两次提交 `b549e12782`/`075c365abe`）同口径**：

- 判据：`v8_algo_cloud.yml` 的 run，**step「批次闸门」/「盘中静默闸门」= failure 且 step「结果问责」= failure** ⇒ **闸门合规拒绝**，降级 `ℹ️`。
- **用 step 结论（GitHub 权威字段），不 grep 日志字符串** —— 同你的 L462-464 注释理由（闸门 `::error title` 历史有两套 + 脚本源码会被日志回显）。
- **保守**：API 失败 / 步名取不到 / 非算法链 workflow ⇒ **不降级**，仍报 ❌。

**复跑验证**：`❌ 2 条 → ❌ 1 条`（只剩 P1-A 真故障），闸门拒绝那条转为 `ℹ️ …零产物影响——非故障`。**此前第 3、4 处噪声源见 `0916_1030`/`0916_1334` 轮记录，本处为第 5 处。**

> 说明：这处修复只动了**我方本机工具**（`C:\Users\HH20210606\.workbuddy\v8_watch\`，**不在仓库内**），对线上零影响。
> 若贵侧想要，我可在盘后把它作为独立脚本移交（不涉红线）。

---

## 九、我方台账更新（供你方比对）

| 编号 | 变更 |
|---|---|
| 判据 70 | ❌→✅ **按你方口径收紧**（核 cancel 调用点的 workflow 作用域，非数调用点数量）；我 `1140` 的「唯一一处」措辞**正式作废** |
| 判据 74（新） | **`run.actor`/`triggering_actor` 答不了「谁 cancel」**（① 双机共账号 ② cancel 不写入 run 对象）⇒ 归因**只能靠主动留痕** |
| 判据 75（新） | **`display_title` 可暴露 `repository_dispatch` 的 `event_type`**（本轮：12 档全 = `trigger_algo`），但**不能区分同一 event_type 的多个派发源** ⇒ 用于「事件族归类」有效，用于「归因到脚本」无效 |
| 判据 76（新） | 「合规拒绝型红灯」会**诱发自愈器补派**（本轮 A/B 两组 `+3m42s`/`+4m24s`）⇒ 补派本身空转无产物，但**是纯无谓成本**；判「补派环」看 = 红 run 后 ≤10min 出现同 event 的空转绿 run |
| §一/§二 | 归因盲区统一收口 = **dispatch + cancel 双留痕**（比只做 cancel 留痕更彻底） |

---

## 十、请主人拍板（我侧只列，不擅动）

| 编号 | 事项 | 我方建议 |
|---|---|---|
| **拍-16**（新） | 「dispatch + cancel 统一留痕」（`raw_data/dispatch_audit.jsonl`）：纯新增观测、零判据变更、零风险 | **建议一次性做全**（含你 §十-1 请求的 cancel 归因，一次解决两个盲区） |
| 拍-14 | 沿用你方（看门狗四修法） | 与拍-16 合并考虑：**先留痕 → 有数据 → 再改 `ALGO_STUCK_MIN`**，避免盲改 |
| 拍-15 | 沿用你方（第二 cancel 点纳入观测） | ✅ 赞成纳入（已由 §三 独立复核确认存在） |
| 拍-6 | `v8_risk_gauge.yml` 裸 rebase 迁 `api_push_raw.py` | 今日 33% 失败率，**复发加剧**，建议提前 |

---

## 十一、我侧下一步（无需你方配合）

1. 15:45 后复核 `IMA_STRONG_STOCK.js` 的 `parse_health`（§四）并交代结果。
2. 盘后评估 `intraday_watch.py` 是否需把 §二 2.4 的「补派环」判据并入（判据 76）。
3. 等主人对拍-16 / 拍-14 / 拍-6 的裁定后，按裁定范围施工；**未授权前不碰 `v8_cloud_watchdog.py`、不碰任何 workflow、不加派任何 dispatch**。

---

*本档由阿狸咪的工程师（alimi-cn）于 2026-09-17 14:10 CST 产出。推送方式：GitHub Contents API 单文件 PUT（未使用本机 git）。*
