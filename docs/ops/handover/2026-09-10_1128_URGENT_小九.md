# 🚨 URGENT 给小九 · 2026-09-10 11:28 CST（阿狸咪盘中巡检）

> 盘中巡检（11:15 / 11:26 两轮）退出码 1。已逐项查证，**非踩踏风暴**（活跃并发 0-1，API 配额充足），
> 全程**未加派任何 dispatch**。以下为查证结论 + 一劳永逸方案，**请勿用「重跑一遍」处理**。

---

## 一、结论速览

| # | 事项 | 状态 | 归属 |
|---|------|------|------|
| 1 | 巡检误报「盘中数据落后 20h」 | ✅ **阿狸咪已修**（脚本判读改 main 分支权威源） | 阿狸咪 |
| 2 | Bug ④ 架构死锁（concurrency 同组互锁） | ✅ **你已修**，commit `5d7185948` 11:00:58 已到 main，已验证 | 小九 |
| 3 | **今日盘中 14 档仅触发 1 档，11:00/11:20 档缺失** | ❌ **未解决**，盘中数据落后 1.3h | **需小九** |
| 4 | post_close 类盘中判「落后 35-42h」 | ⚠️ 阈值误伤（盘后数据盘中本就不该刷） | 阿狸咪后续修 |

---

## 二、已查证根因链（附证据）

### ① 盘中数据的唯一调度源今天基本没跑起来

`v8_cn_fetch_intraday_lemoncat.yml`（盘中 14 档准点档调度器）是盘中**唯一**调度源
（`v8_cn_fetch_cloud.yml` 的 cron 已确认只剩 08:25 盘前 / 17:20·18:20·19:20 盘后三档 / 周末 09:00，**盘中无 cron**）。

查证结果（API `actions/workflows/v8_cn_fetch_intraday_lemoncat.yml/runs`）：

```
workflow state : active
今日 run 总数  : 1
  10:46 CST | completed cancelled   ← 仅此一档（10:40 档，cron 延迟 6 分钟触发）
```

- 09:40 / 10:00 / 10:20 / **11:00 / 11:20** 档：**全部未触发**。
- 唯一触发的 10:40 档，跑到 `sleep 600s` 结束时被外力 cancelled（02:46→02:56 UTC），
  `check` / `兜底 dispatch` 两步全部 skipped → **一档 20 分钟白跑**。
  这正是你 11:00:58 提交的 Bug ④（本 yml 与它 dispatch 出去的 cloud/selfhosted 同属
  `v8-cn-fetch-cloud` 组 → 占组 20 分钟 → 被调度者排队 → 检查时还在 queued → 死锁）。

### ② Bug ④ 修复已落地并验证

远端 `.github/workflows/v8_cn_fetch_intraday_lemoncat.yml` 第 64-77 行已改为：

```yaml
concurrency:
  group: v8-cn-fetch-slot
  cancel-in-progress: true
```

✅ 已移出 `v8-cn-fetch-cloud` 组，死锁解除。**修得对，这条不用再动。**

### ③ 但修完之后 11:00 / 11:20 两档仍未触发

- 修复 commit `5d7185948` 落地时间 **11:00:58 CST**，11:00 档（cron `0 3 * * 1-5`）几乎同时刻，
  判定为**错过本档**（GitHub 对 default branch 上新变更的 workflow，schedule 注册有滞后）。
- 11:20 档（cron `20 3 * * 1-5`）截至 11:27 仍无 run，total_count 依旧是 1。
- 当前盘中数据（main 分支 API 实测）：`INDEX_QUOTES` / `AVG_PRICE_DATA` / `ETF_INTRADAY_HEAT`
  停在 **10:09:05**，落后约 **78 分钟**（阈值 60min）。

---

## 三、一劳永逸方案（按优先级）

### 🔴 方案 A（强烈推荐）：**去掉 sleep 600s，改事件驱动**

现在的「dispatch → sleep 10min → 查状态」是**最脆弱的一环**：
占着 self-hosted cn runner 干等 10 分钟，一旦被 cancel / 超时 / cron 丢档，整档直接报废，
而且今日已经实证它报废过一次。

改成**两段式事件驱动**：

1. 调度器只负责 dispatch，然后**立即结束**（job 时长 10 秒，不再占用 runner）。
2. 新建（或复用）一个 workflow，用 `on: workflow_run: workflows: ["🇨🇳 v8 中国数据抓取(云端)"] types: [completed]` 触发：
   - `conclusion == success` → 本档结束，什么都不做；
   - `conclusion != success` → dispatch `v8_cn_fetch_cloud_selfhosted`（小九 cn 兜底）。

收益：① 不再占 runner 空等 ② 不再依赖 sleep 的存活 ③ 状态判断由 GitHub 事件保证准确
④ 一档耗时从 20+ 分钟压到实际抓取时长。

### 🟠 方案 B：**档位补跑守卫**（兜住 cron 丢档）

GitHub 官方明确 schedule **不保证触发**、高负载时会整档丢弃 —— 今日 09:40/10:00/10:20 三连丢就是实例。
建议让 `v8_cn_fetch_watchdog.yml`（已是 dispatch-only）顺带承担补档职责：

> 每次被触发时，先算「当前 CST 时间落在哪一档」，
> 再查该档时间窗内 `v8_cn_fetch_intraday_lemoncat.yml` 是否已有 run；
> **没有 → 补 dispatch 一次云端抓取**（同 `v8-cn-fetch-cloud` 组互斥排队，不会踩踏）。

这样即使 cron 丢档，最多延后一档（≤20 分钟）自动补齐，不再出现「整段午前无数据」。

### 🟡 方案 C：**新 workflow 的 schedule 落地校验**

今日事故链起点是「workflow 昨晚只 commit 未生效、盘中才发现」。
建议在 `align_logic_ops.py` 的校验里加一条：
**`.github/workflows/*.yml` 中含 `schedule:` 的文件，必须同时存在于 main 分支且 state=active**，
否则 CI 直接报红。避免「写了 cron 但没真正跑」这类哑火再次发生。

---

## 四、请勿做的事

- ❌ **不要连续 dispatch 补数据** —— 当前链路健康（11:20 小九应急正在跑，10:56 那次 success），
  堆派发只会重演 secondary rate limit 403。
- ❌ 不要把 `v8_cn_fetch_intraday_lemoncat.yml` 再塞回 `v8-cn-fetch-cloud` 组（会复发 Bug ④）。
- ❌ 不要重跑 10:40 那一档（数据已过窗口，跑了也是废数据）。

---

## 五、阿狸咪侧已完成的修复（供你同步认知）

`intraday_watch.py`（仓库外 `~/.workbuddy/v8_watch/`）原用**本地** `E:\workspace\stock-scanner\data\*.js`
判新鲜度。实测本地停在 09-09 15:19 / main 已是 09-10 10:09（坚果云只同步双机工作区，**不拉远端**），
导致盘中数据被误报「落后 20h」。已改为：

- 判读一律走 **GitHub Contents API 取 main 分支**（权威源）；
- 本地副本与 main 的落差单独列为 `ℹ️` 提示（46 个文件滞后，**不计入异常**）；
- 修复后复跑：盘中类落后显示由 20.0h → **真实 1.3h**。

**→ 同理提醒：任何「看本地 data/ 判断线上新鲜度」的脚本都有这个坑，建议统一改判 main 分支。**

---

**阿狸咪（夜班/周末机）· 2026-09-10 11:28 CST**
本轮只做只读查证 + 自修巡检脚本，未改动任何 workflow、未派发任何 dispatch。
