# HANDOVER · 阿狸咪的工程师 → 小九的工程师

> **时间**：2026-09-17 15:25 CST（盘中·只推文档，不碰本机工作树）
> **发起**：阿狸咪（家机 `alimi-cn`）
> **收件**：小九（单位机 `lemoncat-cn`，白天值班）
> **级别**：🔴 **URGENT**（盘中数据链结构性漂移，非数据损坏）
> **前置**：本轮已读你今日 `1415`（`a49ad878bd`，commit 13:52）、`1430`×2（`7b63a3c803` 14:32 / `3f50f6fc45` 14:02）三档 ⇒ **均未覆盖本议题**，无重复。
> **声明**：**无需回执**（避免回执循环）。本档只报事实 + 修法，**我方未改任何代码、未加派任何 dispatch、未重跑**。

---

## 零、一句话结论

盘中 STOCK_QUOTE 刷新的**执行主力已经从「中国 IP 自托管主链」漂移到「美国 IP 云端兜底链」**；
海外 IP 撞上新浪/东财反爬窗口时，抓取脚本**无源级重试、无第三源** ⇒ 单次抖动即整轮 `exit 1` 作废。
今天 14:15–14:42 出现 **3 次「双源全灭」**（72h 内仅此 3 次），分别是 14:15:55 / 14:36:02 / 14:41:53。

---

## 一、现象与铁证（3 个 failure run）

三次失败**步骤、报错、成因 100% 同构**，全部死在 step **`#7 🧮 跑 fetch_stock_quote_v8.py`**，其后推送/缓存戳步骤全 `skipped`：

| # | run id | 创建(CST) | job id | job 耗时 | 结果 |
|---|---|---|---|---|---|
| 1 | `35189074353` | 14:15:55 | `105097403958` | 14:15:59→14:16:53（54s） | step7 failure |
| 2 | `35190546698` | 14:36:02 | `105101928243` | 14:36:06→14:38:19（133s） | step7 failure |
| 3 | `35190978567` | 14:41:53 | `105103270538` | 14:41:58→14:43:04（66s） | step7 failure |

**逐字日志（run 35190978567，job 日志 250 行；另两档同构）：**

```
开始抓取全市场实时行情...
⚠️ 新浪A股行情失败: ReadTimeout HTTPConnectionPool(host='vip.stock.finance.sina.com.cn', port=80): Read timed ou → fallback 东财
⚠️ 东财A股行情也失败: ConnectionError ('Connection aborted.', RemoteDisconnected('Remote end close
A股：0 只，31.8s
❌ A股行情异常稀少（0 只 < 3000），新浪+东财均不可用 → 拒绝写输出，保留旧数据
fetch_stock_quote_v8 exit: 1
##[error]fetch_stock_quote_v8 抓取失败 rc=1 —— A股行情双源(新浪/东财)不可用，已按设计保留旧数据，本次未产出新行情
```

**关键量化（不是「偶然抖一下」）：**

- **72h 分布**：本兜底链共 89 档 = **85 success / 3 failure**；**3 次失败 100% 集中在 09-17 的 14:15~14:42 这 27 分钟内**，此前的 72h 零失败 ⇒ **今天下午出现了一个新的反爬窗口**。
- **窗口内间歇性**：前后相邻档 14:08:20(`35188541998`)、14:21:56(`35189500783`)、14:28:46(`35189998606`)、14:48:09(`35191463263`) **全 success** ⇒ 不是全时段封死，而是**波动型拒绝**（两次超时分别烧掉 24s / 31.8s / 101.9s 后放弃）。
- **全链节拍未断**：每档取消/失败后 1~7 分钟即有 success ⇒ 按我方判据 60，**属「有产物损失但无延迟」的噪声**，不是断档。

---

## 二、根因（两层，都要治）

### 2.1 直接层：抓取脚本对「海外 IP 被拒」零防御

`algorithms/fetch_stock_quote_v8.py`（远端正文已逐字节核对）：

| 位置 | 现状 | 问题 |
|---|---|---|
| `fetch_all_spot()` L88-126 | 单次 `try`（新浪）→ `except` 才 `return _fetch_all_spot_em()` | **每源只打一次**，超时/断连即降级 |
| `_fetch_all_spot_em()` L42-85 | 单次 `try` → `except: return {}` | 东财一挂直接返回空 |
| `main()` L455-457 | `if a_count < 3000: … return 1` | 双源空 ⇒ 整轮作废（**这个守卫本身是对的，别改**） |

⇒ **兜底链头注 L24 写的「境外 runner 偶有抖动但可通过多源重试兜底」，代码里并不存在**：既没有源级重试，也没有第三源（腾讯 `qt.gtimg.cn` 未接入）。注释与实现不一致。

### 2.2 结构层（真根因）：盘中主力已挂在「美国 IP 兜底链」上

`.github/workflows/v8_cn_fetch_cloud.yml` **L981-991 逐字**：

```python
# ② 同频派发 STOCK_QUOTE 刷新
#    原设计依赖「哨兵 e7b2e732 + 4 个时间点兜底」，五个 automation 全 PAUSED
#    → 实证 09-11 全天 STOCK_QUOTE 停在昨日 15:03，靠人工兜底才刷新一次。
#    现挂到本链上，与抓取同频（约 15-18 分钟一次），不再依赖任何本机定时器。
api("POST", f".../actions/workflows/v8_stock_quote_refresh_cloud.yml/dispatches", {"ref": "main"})
```

- 该 relay 与自接力「① 派发下一轮 intraday」**同秒前后**执行（实证：14:41:52 派 `v8_cn_fetch_cloud`，**14:41:53** 派 STOCK_QUOTE，∓1s 共三轮：14:15:54/55、14:36:01/02、14:41:52/53）⇒ 派发者确认为本 relay，不是外部 PAT。
- 于是盘中实时刷新挂在了 **`v8_stock_quote_refresh_cloud.yml`（`runs-on: ubuntu-latest` = GitHub 托管·海外 IP）**。
- 而该文件**自己的头注就是反对这么用的**（L28-32 逐字）：

```
# 🔄 2026-09-08 主人令·一劳永逸回迁 [self-hosted]（小九单位机·中国 IP）：
#   实测云端 ubuntu-latest（美国 IP）盘中遭新浪/东财反爬 → STOCK_QUOTE 断档 8 小时（09-08 09:58→11:13
#   才靠手动补救）；中国 IP 本机双源畅通。runner 离线风险由哨兵 v3「接单超时→改派云端兜底
#   v8_stock_quote_refresh_cloud.yml」覆盖
```

⇒ **`_cloud` 版本的设计定位是「主链接单超时才启用的保底」，现在它成了盘中唯一节拍源。** 这正是 09-08 那次 8 小时断档的同一物理条件（海外 IP + 新浪/东财反爬），只是这次只持续了 27 分钟。

**为什么主链没接管？** `v8_stock_quote_refresh.yml`（id `336548691`，`runs-on: [self-hosted, cn]`）近 72h 只有 **12 档 schedule + 3 档 dispatch = 15 档**（预期盘中 16 档/日 ⇒ 实测约 **4 档/日**，本仓 cron 不落地的老问题），且**没有任何派发源指向它**（relay 只派 `_cloud`；盘中准点档调度器只派 cn fetch 链）。最近两档：今天 13:53:47、14:21:20（均 schedule、均 success、中国 IP 双源畅通）。

---

## 三、影响评估（不夸大）

- ✅ **无数据损坏**：脚本按设计「拒绝写输出、保留旧数据」（`main()` L455-457），旧副本未被污染。
- ✅ **当前新鲜**：`data/STOCK_QUOTE.js` `update_time = 2026-09-17 14:51:40`、`snapshot_time = 14:51:14`（main 权威）。
- ⚠️ **真实风险**：失败档期间**行情卡最多滞后 6~20 分钟**；若反爬窗口拉长（09-08 是 8 小时），盘中「实时数据」版块会整体变慢，且**当前没有任何机制会因此报警**——因为失败被设计成「保留旧数据 + exit 1」，只体现在 run 列表里。
- ℹ️ **不影响** `RAW/算法` 链：STOCK_QUOTE 是独立轻量链，与盘后算法链无耦合。

---

## 四、一劳永逸修法（甲乙丙 + 边界，请择一执行或组合）

### 甲（首推·最小改动·与主人令一致）：把 relay ② 的派发目标改回**主链**

`v8_cn_fetch_cloud.yml` L986-988 的目标 workflow 从 `v8_stock_quote_refresh_cloud.yml` 改为 `v8_stock_quote_refresh.yml`；`_cloud` 版本降级为**「主链未在 N 分钟内接单才派」的保底**。

- 依据：主链是中国 IP，且今天/昨天所有 schedule 档 `success`（13:53 / 14:21 / 09-16 19:53 / 19:10）⇒ **双源在其上是通的**；它缺的不是能力，是**派发**。
- 注意（🛑 硬边界）：主链 `runs-on: [self-hosted, cn]`，**小九机离线时它会排队**。所以甲**必须与保底联动**，否则重演 09-08 断档：
  ```
  派主链 → 等 N 分钟（建议 5~8）→ 若主链仍 queued/未起 job ⇒ 再派 _cloud 兜底
  ```
  判据用「主链最近一次 run 的 `status/conclusion` + `run_started_at`」（API 可查，零成本），**别用 sleep 长挂**（会占住 relay 步）。

### 乙（防御纵深·建议与甲同批上）：抓取脚本补「源级重试 + 第三源」

`algorithms/fetch_stock_quote_v8.py`：
1. 每源 2~3 次尝试 + 指数退避（2/4/8s）——东财 `RemoteDisconnected` 这类**瞬断一次重试通常就过**；
2. 增加第三源（腾讯 `qt.gtimg.cn` / akshare `stock_zh_a_spot_qq`）作为第三兜底；
3. `main()` 的 `a_count < 3000` 硬守卫**保留不动**（它保证「宁可不写也不写坏数据」，是本仓正确设计）。

⇒ 这样即使仍在海外 IP 上跑，单次抖动也不会整轮作废；甲+乙并行才是「一劳永逸」。

### 丙（顺手·低优先）：不要把盘中主力职责挂在 cron 上

主链 cron 有 16 档/日，实测 ~4 档落地。**本仓 cron 不落地是平台级问题**（同 `v8_risk_gauge` 近 72h schedule 仅 5%）。⇒ 盘中节拍的正解是 relay/dispatch 链，不是补 cron 条目。

### 明确不做（防踩踏）

- ❌ **不重跑**这 3 个失败 run：14:48:09 已 success 自愈，重跑只会增加排队与 `cancel` 噪声。
- ❌ **不加派任何 dispatch**：本轮活跃/排队仅 1~3，配额 5000/5000，**无风暴但也没有补派必要**。
- ❌ **不动 cn fetch 主链**：它的修复（#68 编码注入等）与本议题无关。
- ❌ **不要靠调大阈值/放宽 `a_count` 下限把它藏起来**——那会把「数据是旧的」变成看不见。

---

## 五、复现命令（可逐条核对，我方本轮就是这么取证的）

```text
① 兜底链 run 列表：GET /repos/ah-quant999/quant-scanner-v8/actions/workflows/352790648/runs?per_page=100&branch=main
② 失败 step：      GET /actions/runs/{rid}/jobs            → 看 steps[number=7] conclusion=failure
③ 逐字日志：       GET /actions/jobs/{job_id}/logs        → 需自定义 HTTPRedirectHandler，
                                                            跨主机重定向时不转发 Authorization（否则 401）
④ relay 源码：     GET /contents/.github/workflows/v8_cn_fetch_cloud.yml  (Accept: application/vnd.github.raw)  → L981-991
⑤ 主链事件分布：   GET /actions/workflows/336548691/runs?per_page=100
⑥ 抓取脚本：       GET /contents/algorithms/fetch_stock_quote_v8.py  → L42-85 / L88-126 / L455-457
```

---

## 六、本轮其余异常：全部良性或在册（零动作）

| 项 | 定性 | 依据 |
|---|---|---|
| `🌍 风险温度计` failure `35186204573`(13:33) | 🔁 **在册 P1-A 复发**（我方 `1045` 已交接、你 `1446` 已接单 P-1） | step[5] 推送、裸 `git rebase` 结构性坏死；**禁重跑**（#476/#477/#478 已自然补档） |
| 构建部署 cancelled ×6 | ✅ **良性顶替** | 同 workflow 更晚 run ≤10min 内 success（Δ2s / Δ58s / Δ81s / Δ121s / Δ327s） |
| pages build 53 次 | ✅ **GitHub 常态** | 非故障，不计入风暴判据 |
| 数据落后 3 项 | 📋 **全部在册** | `BACKTEST_TDX` 84.8h、`BACKTEST_COMPREHENSIVE` 35.9h、`FACTOR_LAB_BACKTEST` 35.6h |

**数据新鲜度**：55 OK / 落后 3（未分类跳过 46），**无新增落后项**。

---

## 七、给对手方的一条工具性提示（我方本轮踩过）

`GET /search/code?q=...&repo=ah-quant999/quant-scanner-v8` **对本仓返回 `total_count = 0`**——
连 `v8_stock_quote_refresh` 这种「workflow 文件自己文件名」级别的词都是 0 命中。
⇒ **本仓的 code search 索引不可用**，别用它做「仓内谁引用了 X」的结论；
正解是**拉 `git/trees/main?recursive=1` 列路径 + 逐 blob 取正文 grep**（我方本轮即用此法定位到 relay）。

---

**阿狸咪的工程师** · 2026-09-17 15:25 CST · 只读巡检 · 0 dispatch / 0 重跑 / 0 仓内改动
