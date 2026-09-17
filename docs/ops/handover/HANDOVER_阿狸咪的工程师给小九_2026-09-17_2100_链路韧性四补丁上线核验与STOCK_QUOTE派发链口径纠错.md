# HANDOVER · 阿狸咪的工程师 → 小九

> **时间**：2026-09-17 21:00 CST（夜班·GitHub Git Data API 推送，**全程未碰本机工作树**）
> **发起**：阿狸咪（家机 `alimi-cn`）
> **收件**：小九（单位机 `lemoncat-cn`，白天值班）
> **级别**：普通（链路韧性 + 口径纠错；**无需回执**）
> **本批 4 个 commit**：`d23fe5a75612`（A+B+C）、`c19c0175f81f`（D）、`648e9e4279d5`（F）、本档所在 commit（F 交叉引用 + 本档）
> **前置已读**：你今日 `1430` 总表 / `1540` / `1640` / `1730` / `1840` / `1900`，以及**家机另一条线**（股票专家）的 `1525` URGENT 件。
> ⚠️ **本档不重复 `1525` 议题、不抢跑**：见 §四。

---

## 零、一句话结论

本轮把「**正在造成真实损失**」的三类静默缺陷（裸 rebase 推送空转 / 自愈通道被 exit 2 堵死 / cn 链编码面缺失）修完上线，
并新增 dispatch+cancel 留痕；同时对 `STOCK_QUOTE` 派发链做了**注释与实体口径纠错**（零行为改动）。
**10 项 A–F 全部落地并在 main 上逐字节复核：17 个文件零漂移、3 个 commit 均在 TIP 祖先链。**

---

## 一、A–F 清单与落点（全部已上线）

| 项 | 治什么病 | 落点 | 门禁 | commit |
|---|---|---|---|---|
| **A** | **8 处裸 `git rebase FETCH_HEAD`** 在 CI 里必报 `cannot rebase: You have unstaged changes.` ⇒ 推送重试**环形空转** | 7 个 workflow（`cloud_weekly_cleanup` / `fill_kcbj_concepts` / `v8_algo_intraday_lite` / `v8_backup`×2 / `v8_cleanup` / `v8_intraday_snapshot` / `v8_risk_gauge`）改为 `git -c rebase.autoStash=true rebase` + 行尾 NOTE | 56 项全绿 | `d23fe5a75612` |
| **B** | `v8_health_check.py` 合法返回 **2**（degraded），而 `v8_health_patrol.yml` 只认 0 ⇒ **健康检查的红灯被当脚本崩**、自愈通道被堵 | `v8_health_patrol.yml` rc 白名单 `{0,2}`（独立核实：该脚本只有 `sys.exit(0 if overall=="ok" else 2)`） | 10 项全绿 | 同上 |
| **C** | 3 个 **cn（真 Windows/GBK 面）** workflow 缺 `PYTHONIOENCODING`/`PYTHONUTF8` ⇒ 中文输出乱码/`UnicodeEncodeError` | `v8_algo_run` / `v8_cn_fetch_cloud_selfhosted` / `v8_lhb_fetch` 的 job env 补两项；`algorithms/run_algorithms.py` 加**模块级自举**（该文件有 9 处 subprocess 调用点，逐点改必漏） | 36 项全绿 | 同上 |
| **D** | GitHub 的 **cancel 动作不写入 run 任何字段**（无 actor、无 reason）⇒「谁取消了这一轮」天然不可归因；且「被冷却跳过」这一**未执行**事件无痕 | `v8_cloud_watchdog.py` 新增 `_audit()` 埋 7 个调用点；`v8_cn_fetch_watchdog.yml` 内联 python 埋 4 个（第二 cancel 点 + 派发） | 全门禁 + **判据原样断言** | `c19c0175f81f` |
| **F** | `guard_v8_freshness.py` 注释/日志与**实体机器面相反**（详 §二） | 3 文件（guard + 2 workflow）**纯注释/日志文案** | 20/20（含「非字符串 token 全等」） | `648e9e4279d5` |

**D 项诚实声明（勿误读）**：两个看门狗都是**分钟级**调度，**有意不推仓**审计文件（否则每分钟一个 commit = 风暴）。
⇒ 本批提供的是「**单机 `~/.workbuddy/v8_dispatch_audit.jsonl` + Actions step summary**」可查，**不是跨机实时可查**。
🔴 全程**一行判据都不改**：冷却 30min / `ALGO_STUCK_MIN=165` / 取消阈值 12min / 派发分支顺序 / 所有 return 值 —— 原样，并有门禁断言。

---

## 二、F 项证据（注释 ≠ 真值，判据 92 归位类）

### 2.1 workflow ID 官方档案 vs 注释（API 直读）

| 常量 | guard 原注 | **官方档案实测** | 判定 |
|---|---|---|---|
| `336548691` | 「`v8_stock_quote_refresh.yml`，**云端 ubuntu-latest**」 | `path = .github/workflows/v8_stock_quote_refresh.yml`，job 实体 **`runs-on: [self-hosted, cn]`**（09-08 主人令回迁·中国 IP） | ❌ **与实体相反** |

⇒ 该注释会让人判错「**哪台机器必须在线**」。已改为真值，并写明：
**小九机离线时本 run 只会排队、不会自动改派云端；离线兜底由哨兵 v3 派发 `_cloud` 版承担。**

### 2.2 仓内「派发 STOCK_QUOTE」穷举（211 文件：workflow 30 + 根/一级 py 181）

| # | 位置 | 派发目标 | 宿主 |
|---|---|---|---|
| ① | `guard_v8_freshness.py` L334 | `336548691` = `v8_stock_quote_refresh.yml` | **[self-hosted, cn] 中国 IP** |
| ② | `v8_cn_fetch_cloud.yml` L987（relay ②） | `v8_stock_quote_refresh_cloud.yml` | **ubuntu-latest 海外 IP** |

🔴 **补充你 `1525` 的工具性提示**：`search/code` 对本仓返回 `total_count=0`（你已发现）；本档**复核确认**
—— 改用 `git/trees/main?recursive=1` 列 211 个候选路径 + 逐 blob grep 才拿到上面 2 处。**穷举法有效，code search 不可用，双重确认。**

### 2.3 09-17 run 分布（API 直读，CST）

| 链 | 今日轮数 | event | 结果 | 备注 |
|---|---|---|---|---|
| 主链 `v8_stock_quote_refresh.yml` | **4** | 全部 `schedule` | 4 success（最新 19:55:58） | 自身 cron **迟到交付**（13:53/14:21/19:18/19:55，不在 09:00-16:30 格点上） |
| 兜底链 `_cloud` | **27** | 全部 `workflow_dispatch` | 24 success / **3 failure**（14:36、14:41 等） | 与你 `1525` 的「双源全灭」3 档**同源**（海外 IP 反爬） |

---

## 三、🔴 自我更正（诚实记录，请以此为准）

我 09-17 交接口径里写过「**STOCK_QUOTE 主链零派发源（穷举证实）：全仓仅 1 处派发点**」。
**该结论有误**：当时把 `guard_v8_freshness.py` 当作「机外文件」排除在扫描面之外。
本轮以「workflow 30 + 根/一级 py 181 = 211 文件」重扫，**实为 2 处**（见 §2.2）。
⇒ 修正后语义：**主链在仓内确有派发点（guard 自愈），但盘中主力节拍确实挂在兜底链上**（与你 `1525` §2.2 结论一致）。

---

## 四、与 `1525` 件的关系（不重复、不抢跑；只把「待拍板」落到注释旁）

* 你 `1525` 已给出**甲（首推：relay ② 改派主链 + 须与保底联动）/ 乙（抓取脚本源级重试 + 第三源）/ 丙（别把主力挂 cron）**，并请**择一执行或组合**。
* 我本轮**只做事实层留痕**（把「此处派发的是海外 IP 兜底链」写进 relay ② 与 `_cloud` 头部），并交叉引用 `1525` 件；
  **行为层一行未动**（零 dispatch 变更、零新增派发）。
* **我建议按甲执行，但今晚故意不动**，三条理由（请复核）：
  1. **需与保底联动**：甲单独上，若小九机离线则主链 run 只排队 ⇒ 重演 09-08 的 8 小时断档；
     「等 N 分钟未接单再派 `_cloud`」需在 relay 内联 python 里加轮询逻辑 —— 属行为改动，不宜夜班单方面落。
  2. **归属**：`1525` 的收件是你，且该文件和 relay ② 是你白天链的资产；**同一文件两线并行改动会互相覆盖**。
  3. 我方**能提供的补强证据**（供你执行甲时引用）：
     * 主链今日 4 档**全 success**（中国 IP 双源通）⇒ 它缺的是**派发**不是能力；
     * 主链 72h 内 `workflow_dispatch` 仅 3 档（`1525` 数据）⇒ **「哨兵 v3 每 10 分派发」的契约并没有真的发生**；
     * 主链 concurrency 组 `v8-stock-quote-refresh` 且 `cancel-in-progress: false`
       ⇒ GitHub 语义下**同组只保留 1 个 pending + 1 个 in-progress**，**不会堆积 queued run** ⇒ 甲无「风暴」副作用。
* **若明日盘中你未动**，则 09-08 的物理条件（海外 IP + 反爬窗口）仍在 ⇒ 请**至少**先落乙（源级重试）作防御纵深。

---

## 五、顺手复核（E / G，只读 API 直读）

| 项 | 实测（blob / bytes / update_time） | 判定 |
|---|---|---|
| `data/IMA_STRONG_STOCK.js` | `fc5268a5302a` / **34273 B** / ut **2026-09-17 20:50:19** | ✅ 治本版仍在跑；⚠️ 与 15:53 版**同尺寸（34273 B）但 blob 不同** ⇒ 又一例「**size 相同 ≠ 内容相同**」 |
| `data/FOUR_VOLUME_BACKTEST.js` | `0f225a411709` / 2884 B / ut **2026-09-17 20:02:47** / `total_signals=1429` / `signal_date_range=近 3 年` | 📋 与你 `1900` §六所报「1384 / 近 3 年 / 07:18:12」**已再变**（07:18→18:32→20:02 共三版）；**我方未手工改数**，待你再判 |
| `data/STOCK_QUOTE.js` | `1b4eb2566a74` / 4027834 B / ut **18:08:27** / `snapshot_time=15:30:01` | ✅ 盘后档已刷新（`1525` 报的 14:51:40 已前进） |

---

## 六、判据 84（推前 blob 级 diff 分类）—— 发现一处**双向分歧**，全机须警惕

| 文件 | 本机（家机工作树） | 远端 main | 判定 |
|---|---|---|---|
| `guard_v8_freshness.py` | `2fe7f78f3c1b` / 41022 B | 同 | ✅ 一致 |
| `v8_stock_quote_refresh_cloud.yml` | `72c1f4689c1d` / 21487 B | 同 | ✅ 一致 |
| `v8_cn_fetch_cloud.yml` | 944 行（`$GITHUB_OUTPUT` 改造版） | **993 行** | ⚠️ **双向分歧**：本机独有 13 行 / 远端独有 62 行 |

⇒ 本批**一律以远端 blob 为基线重打补丁**，未用任何单机旧副本。
🔴 **提醒**：该文件在两台机上都不是「落后」而是「**双向分歧**」——**任何一侧拿本机副本整体覆盖都会造成静默回退**，
请勿用 `git add -A` 或整文件 PUT。我的补丁只替换**设计窗口内的行**，其余远端内容 0 丢失（有门禁断言）。

---

## 七、边界与残留（诚实披露）

* 本方本轮**未碰**：`index.html` / `logic.html` / `data/**` / `raw_data/**` / 任何派发行为 / 任何阈值。
* **未碰本机工作树**（`E:/workspace/stock-scanner/`）：0 `git add` / 0 `commit` / 0 `push`；全程 GitHub Git Data API
  （blobs → tree(`base_tree`) → commit(parents=[tip]) → `PATCH force:false`），推后逐字节回读。
* 本轮踩坑自纠（留档防复发）：
  1. 我的门禁「行尾形状守恒」公式**自己写错**（把「插入行必增 bare-LF」判成缺陷）⇒ 正解是
     `bare-LF 增量 == 净增行数`（本例 811→819 = +8 行，全部为新插入行）。
  2. **Python 3.12+ 的 f-string 拆成 `FSTRING_START/MIDDLE/END`，不再产出 `STRING` token**
     ⇒ 只按 `STRING` 过滤会把「f-string 文案改动」误判成「代码改动」；同理 `len(str) ≠ len(bytes)`（中文）。
  3. 又一次实测：`git status` 清洁 **≠** 与线上一致；**判据 84 必须落到 blob 级**（本次正是它捞出上面的双向分歧）。

---

**署名**：阿狸咪的工程师（`alimi-cn` / 家机）｜时区 北京时间 CST+8｜本档只读巡检 + 注释层纠错，**行为层 0 改动**
