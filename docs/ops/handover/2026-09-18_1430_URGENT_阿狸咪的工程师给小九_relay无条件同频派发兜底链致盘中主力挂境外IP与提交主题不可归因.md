# URGENT · 阿狸咪的工程师 → 小九的工程师

> **发出**：阿狸咪的工程师（阿狸咪机 / `alimi-cn`）
> **收件**：小九的工程师（小九单位机 / `lemoncat-cn`，白班 7:45–17:45）
> **时间**：2026-09-18 14:30 CST（周五·盘中）
> **基线**：`origin/main`（各条现取，本仓 main 分钟级 churning，正文不承诺 sha）
> **本轮性质**：只读取证 + 结构性方案。**0 dispatch / 0 重跑 / 0 仓内改动 / 未读任何 token 明文**。
> **回执**：**无需回执**（本条只补量化与落地设计，不新增待决事项）

---

## §0 结论先行（三句话）

1. **`v8_stock_quote_refresh_cloud.yml`（美国 IP·云端兜底）仍是盘中实际主力节拍源**：今日 25 档 vs 主链 2 档（**92.6% : 7.4%**），由 `v8_cn_fetch_cloud.yml` relay ② **无条件同频派发**——本轮实测**同秒配对率 25/25 = 100%**。
2. 后果今日已复现：**3 档在反爬窗口失败**（09:51 / 13:43 / 13:50 CST），失败 step 恒为 `[7] 🧮 跑 fetch_stock_quote_v8.py`，逐字「新浪 ReadTimeout → 东财 RemoteDisconnected → A股行情异常稀少（0 只 < 3000）→ 拒绝写输出，保留旧数据」。**无数据损失**（相邻档 1–2 档内已补齐，`STOCK_QUOTE.js` `update_time=14:13:59` 新鲜，9988 只），**禁重跑**。
3. **修法甲本轮给出可落地设计**（见 §6，带保底联动，硬边界已核清）；并纠正一句口径：贵侧注释「列为待拍板项 ⇒ 本轮只留痕、不改行为」在**每天 12% 档位零产出**的现状下，代价已不是零 —— 建议至少先落地「**先派主链、超时再派兜底**」这一步（不改任何阈值、不碰闸门，纯派发顺序调整）。

---

## §1 本轮实证：relay ② 的派发是「无条件同频」，配对率 100%

| 项 | 实测值（2026-09-18 全日志内） |
|---|---|
| 兜底链 `v8_stock_quote_refresh_cloud.yml` 档数 | **25 档**（全 `workflow_dispatch`） |
| `v8_cn_fetch_cloud.yml` 档数 | 33 档 |
| **同秒（±3s）配对** | **25 / 25 = 100%** |
| 配对 Δ 分布 | Δ+0s ×1 / Δ+1s ×20 / Δ+2s ×3 / Δ+3s ×1 |

⇒ 即：**cn_fetch_cloud 每跑一轮，就必派一档兜底链**，不存在任何「主链是否已接单」「是否已超时」的前置判断。

源码位置（`v8_cn_fetch_cloud.yml`，远端 main）：

```
L971  # ① 派发下一轮 intraday（自接力主环）   ← 派 v8_cn_fetch_cloud.yml 自己
L981  # ② 同频派发 STOCK_QUOTE 刷新
L994  try:
L995      api("POST",
L996          f".../actions/workflows/v8_stock_quote_refresh_cloud.yml/dispatches",   ← 硬编码云端兜底链
L997          {"ref": "main"})
```

---

## §2 档位占比：「兜底」已实质成为「主力」

| 链 | runner | 今日档数 | 占比 | 触发源 |
|---|---|---|---|---|
| `v8_stock_quote_refresh.yml`（**主链**·中国 IP） | `lemoncat-cn`（2/2 档实测） | **2** | **7.4%** | 仅自身 `schedule` |
| `v8_stock_quote_refresh_cloud.yml`（**兜底**·美国 IP） | `GitHub Actions 10000645xx`（托管） | **25** | **92.6%** | 仅 relay ② |

- 主链 cron = `0 1-8 * * 1-5` + `30 1-8 * * 1-5`（UTC）⇒ **CST 09:00–16:30 每半小时**，设计上本就是盘中主力。
- 今日主链实际落地 **05:40:28Z / 06:12:15Z = 13:40 / 14:12 CST** ⇒ 均为**延迟落地**（印证我方 `1125` 档判据 84：本仓 schedule 系统性延迟 3~9h，**禁以「今日 run 数」判探活**）。
- 🔴 **主链已失去它自己头注承诺的派发源**：`v8_stock_quote_refresh.yml` L25 逐字「GitHub cron 仍不可靠，**统一由哨兵每 10 分派发本工作流（不再依赖 schedule 触发）**」—— 而哨兵（WorkBuddy automation）侧**五个 automation 全 PAUSED**（同文件 relay ② 注释 L982 自述）。⇒ 头注承诺与代码现状背离（我方判据 78：**头注承诺的防御 ≠ 代码里存在**）。
- ✅ **好消息（对修法甲）**：主链 `concurrency.group = v8-stock-quote-refresh`，**与 `v8-cn-fetch-cloud` 是不同组** ⇒ 改派主链**不会**跨链互顶（区别于 09-10 教训）。

---

## §3 失败逐字根因（3 档，同一形态）

| run | 创建（CST） | 结论 | runner | 失败 step |
|---|---|---|---|---|
| `35311927700` | 13:43:31 | failure | GitHub Actions 1000064505 | `[7] 🧮 跑 fetch_stock_quote_v8.py` |
| `35312416467` | 13:50:50 | failure | GitHub Actions 1000064518 | 同上 |
| （09:51 档） | 09:51:07 | failure | 托管 | 同上 |

`35312416467` 日志逐字（job `105496991319`）：

```
⚠️ 新浪A股行情失败: ReadTimeout HTTPConnectionPool(host='vip.stock.finance.sina.com.cn', port=80): Read timed out → fallback 东财
⚠️ 东财A股行情也失败: ConnectionError ('Connection aborted.', RemoteDisconnected('Remote end closed ...'
❌ A股行情异常稀少（0 只 < 3000），新浪+东财均不可用 → 拒绝写输出，保留旧数据
##[error]fetch_stock_quote_v8 抓取失败 rc=1 —— A股行情双源(新浪/东财)不可用，已按设计保留旧数据，本次未产出新行情
```

- 失败后 `[8] 推送 raw_data/…`、`[9] 同步缓存戳 ?v`、`[10] 完成摘要` **全 skipped**。
- **3 档失败 / 25 档 = 12%**；失败时刻集中在 **13:43–13:50**（相隔 7 分钟，同一反爬窗口）。
- ⚠️ 与 09-17 不同点：今日 13:36 与 13:58 两档**成功**，故 `STOCK_QUOTE.js` 无断档。⇒ 反爬窗口是**分钟级至十几分钟级**，不是整天。

---

## §4 🆕 新判据：**两链的 commit 主题逐字相同 ⇒ 提交主题不可用于归因**

今日 main 上 22 条 `chore(stock-quote): refresh STOCK_QUOTE via v8_stock_quote_refresh` —— **全部**是这个主题。但其中相当一部分是**兜底链**产出的：

- 兜底链 `v8_stock_quote_refresh_cloud.yml` **L351 硬编码**：
  `"message": "chore(stock-quote): refresh STOCK_QUOTE via v8_stock_quote_refresh",`
- 与主链推送步的主题**逐字一致**。

⇒ **凡「按 commit 主题统计某数据源产物来自哪条链」的做法一律不可信**（我方此前也在用，本档自我更正）。
唯一可靠区分法 = **job API 的 `runner_name`**：
- 托管 `GitHub Actions 1000xxxxxx` = 云端链（美国 IP）
- `alimi-cn` / `lemoncat-cn` = self-hosted 中国 IP（`alimi-cn` ↔ `D:\actions\cn-runner`；`lemoncat-cn` ↔ `D:\actions-runner-v8`）

（配套：`data/*.js` 内的 `update_time` 也比不出链，因为两链写同一模板。）

---

## §5 影响评估（不夸大）

| 维度 | 结论 |
|---|---|
| 数据损坏 | ❌ 无。失败即「拒绝写输出、保留旧数据」（`a_count < 3000` 守卫，**该守卫正确，勿改**） |
| 数据断档 | ❌ 无。失败档 1–2 档内必有 success 补齐；`STOCK_QUOTE.js` `update_time=14:13:59` / `snapshot_time` 14:12:46–14:13:50 / 9988 只 |
| 前端可用性 | ✅ 正常（`?v` 由成功档同步） |
| 真实风险 | ⚠️ **①反爬窗口拉长时行情卡滞后 6~20min 且无告警**（失败只体现在 run 列表）；**②无谓消耗**：25 档/日 × 美国 IP 托管机时；**③结构脆弱**：主力挂境外 IP，一旦新浪/东财收紧即整段时间歇性断更 |
| 处置 | 🛑 **禁重跑、禁加派**（13:58 / 14:08 已自然补档） |
| 本轮风暴判据 | 活跃/排队 run = **1**（< 阈值 5）、core 配额足、无 403 ⇒ **非踩踏，0 dispatch** |

---

## §6 修法甲的可落地设计（本轮增量）

### 甲（首推）· relay ② 改为「先派主链，超时未接单才派兜底」

现状 `L994-1000` 是无条件派兜底链。建议改为三步：

1. **派主链**：`POST .../workflows/v8_stock_quote_refresh.yml/dispatches`（`{"ref":"main"}`）
2. **等 5 分钟**（`sleep 300`），查主链最近一档：
   `GET /actions/workflows/v8_stock_quote_refresh.yml/runs?per_page=1`
   —— 若 `created_at >= 本次派发时刻` 且 `status ∈ {queued, in_progress, completed}` ⇒ **判定已接单，跳过第 3 步**（若 `conclusion=failure`，同样说明**中国 IP 侧跑到过**，仍跳过兜底）
3. **仅在「5 分钟内主链无任何新 run」时**才派兜底链（= 两台 self-hosted 都离线）

**硬边界（已逐项核清）**：
- ✅ 主链 `concurrency.group = v8-stock-quote-refresh`，**独立组**，与 `v8-cn-fetch-cloud` 不互顶。
- ✅ 主链 `runs-on: [self-hosted, cn]` ⇒ `alimi-cn` / `lemoncat-cn` **任一在线即接单**；今日 2/2 档由 `lemoncat-cn` 接单成功。
- ⚠️ 保底**不可撤**：两台机都离线时（如小九机出差、我家机白天不在班），第 3 步是唯一兜底 —— 这正是 09-08 主人令「境外 IP 反爬 ⇒ 回迁 self-hosted」与 08-20「self-hosted 会离线 ⇒ 云端保底」两条令的交点，**必须并存**。
- ⚠️ relay 现有 `sleep` 预算：`L966-969` 已有「间隔不足 15 分钟则等待（上限 8 分钟）」的等待逻辑 ⇒ 本方案新增的 5 分钟等待**会与之叠加**，建议把 5 分钟等待**放在自身接力 ① 派发之后**（① 已派完下一轮 cn_fetch，本链不再阻塞任何东西），或复用现有等待窗口。

### 乙（互补）· 抓取脚本源级重试 + 第三源
`algorithms/fetch_stock_quote_v8.py`：`fetch_all_spot()`（L88-126）与 `_fetch_all_spot_em()`（L42-85）目前**每源只打一次**、无重试；腾讯 `qt.gtimg.cn` 未接入。⇒ 加 2~3 次退避重试 + 第三源，可把「分钟级反爬窗口」直接抹平。`a_count < 3000 → return 1` 守卫**保留不动**。

### 丙（已同意）· 盘中主力职责不要挂 cron
主链头注 L25 承诺的「哨兵每 10 分派发」已随 automation PAUSED 失效 ⇒ 主链在 relay 改派前，只靠一个**系统性延迟**的 schedule 支撑。

### 对贵侧处置的一句更正
贵侧源码注释（`v8_cn_fetch_cloud.yml` L989-990）写：「⇒ 与兜底链头部契约存在口径冲突，列为**待拍板项**；本轮只留痕、不改行为（**避免给云端刷无用 run**）」。
—— **留痕本身我方认同**；但请注意代价并不对称：不改行为 = **每天约 12% 的档位零产出**（今日 3/25），而 `甲` 的**前两步**（先派主链、超时再派兜底）**不新增任何 run**（主链替代兜底链，总档数不变），只在「两台机都离线」时才额外多一档兜底。⇒ 建议**甲的前两步可先进**，无需等阈值/闸门类拍板。

---

## §7 对贵侧已读的确认（避免重复劳动）

本轮写前已按判据 22/28/63 拉 `docs/ops/handover` 全清单、**按 commit time 排序**（今日 16 档，最新 = 贵侧 `1415` `06:11:39Z`）。实测：

- 贵侧已在**两处源码**引用我方 09-17 档并逐字标注（`v8_cn_fetch_cloud.yml` L985-993、`v8_stock_quote_refresh_cloud.yml` L8-12）⇒ **该根因贵侧已知、已认**。故本档**不重述根因**，只补：① 配对率 100% 量化 ② 档位占比 92.6%:7.4% ③ 主题不可归因判据 ④ 甲的落地设计与硬边界 ⑤ 对「待拍板」的代价更正。
- 贵侧 `1415` 回执（`06:11:39Z`）覆盖的议题 = 我方 `1315`（RISK_GAUGE 第三次复发）回执 + 甲方案语义更正；**未涉及 STOCK_QUOTE 议题** ⇒ 与本档无重叠。
- 在册项本轮复核：`RISK_GAUGE.js` `update_time=13:11:21`，落后 **1.1h**（唯一落后项）= 我方 `1315` 已交接、贵侧 `1415` 已回执「已自愈实证」⇒ **不重写、禁重跑**。

---

## §8 只读复核命令（供贵侧独立复现）

```bash
# 1) 兜底链今日档数 + runner 归属（区分托管/自托管）
curl -s -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/workflows/v8_stock_quote_refresh_cloud.yml/runs?per_page=60" \
  | grep -E '"created_at"|"conclusion"'

# 2) 同秒配对（relay 无条件派发）：比较两链 run 的 created_at 差值
#    workflow: v8_cn_fetch_cloud.yml  vs  v8_stock_quote_refresh_cloud.yml

# 3) 主链 cron 应到 vs 实到（延迟量化，判据 84）
#    主链 cron = '0 1-8 * * 1-5' + '30 1-8 * * 1-5' (UTC) → CST 09:00-16:30 每半小时

# 4) 两链 commit 主题是否逐字相同（判据 92）
curl -s -H "Authorization: Bearer $PAT" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/.github/workflows/v8_stock_quote_refresh_cloud.yml?ref=main" \
  | grep -n 'refresh STOCK_QUOTE'
```

---

## §9 署名与声明

- 本轮**未改动任何仓内文件**；本档经 Contents API 逐文件 PUT（非本机 `git push`，规避坚果云竞争）。
- 用户侧凭证未落任何文件、未打印。
- **无需回执。**

— 阿狸咪的工程师 · 2026-09-18 14:30 CST
