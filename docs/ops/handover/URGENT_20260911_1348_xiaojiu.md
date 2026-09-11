# 🚨 URGENT · 2026-09-11 13:48 CST · 给小九（白天值班机）

> 巡检轮次：2026-09-11 13:46（盘中 13:00-15:00 档）
> 结论：**主链路健康，不是踩踏风暴**。发现 1 个新的 P0 资源空转 + 3 个沿用未修项。
> **全程未加派任何 dispatch。**

---

## 0. 一句话结论

盘中行情链路（中国数据抓取 / STOCK_QUOTE / 构建部署 / 缓存戳对齐 / 板块资金日内快照）**全部 success**。
真正的病灶是：**「盘后算法链」在盘中每 3~10 分钟被派发一次，每次跑完前置 8 步后被闸门判 `MARKET_HOURS_BLOCKED` 空转退出**，
跑在**你机器上（`D:\actions\cn-runner`）**，纯烧资源且每次连锁触发一次构建部署 → 13:34 那次构建部署被互顶 cancel 就是这么来的。

---

## 1. 踩踏风暴判定：❌ 不是（可放心，不要加派）

| 指标 | 实测值 | 判定 |
|---|---|---|
| in_progress / queued | 2 / 0 | ✅ 正常 |
| 近 3h 真实失败 | 1（构建部署 cancelled） | ⚠️ 见根因 5 |
| API 配额 | 充足（无 403） | ✅ |
| 派发形态 | 12 次/小时 workflow_dispatch | ⚠️ 空转型高频（新形态） |

**历史教训回顾**：09-10 那次是 5+ 并发触发 403 的真风暴。本轮**不是**——是同一条链被高频单点派发、每次都被闸门合法拦下。
**不要为此加派任何 run，火上浇油。**

---

## 2. 🔴 根因 1（P0 · 新发现）：盘后算法链盘中高频空转，占用 cn runner

### 铁证（run 34567203921 / 34566998369 / 34566595883，三个 run 步骤完全一致）

```
step 2  📥 Checkout 源码（云端 git 直连，秒级）              success
step 3  📥 回退·经 GitHub API 同步源码（仅 checkout 失败时）   skipped   ← 10:27 交接的①已修，见 §3.1
step 4  🔧 修复 git 安全目录                                success
step 5  🗓 解析数据日期                                     success
step 6  🐍 配置 Python (setup-python 3.13)                 success
step 7  📦 安装 A股依赖（PyPI + 双镜像 + 重试）                success   ← 每次重装依赖
step 8  🔒 批次闸门                                        success
step 9  🧮 运行盘后算法链                                    skipped
step 10 🔗 桥接 raw_data 内部改名                            skipped
step 11 📈 刷新候选池行情                                    skipped
step 12 📤 唯一推送                                         skipped
step 13 🔄 同步缓存戳 ?v 并推送 index.html                   skipped
step 14 🛡 机器校验                                         skipped
step 15 🛡 结果问责                                         success   ← 因此 run 判 success
```

闸门日志原文（run 34567203921）：

```
问责输入: 目标批=MARKET_HOURS_BLOCKED 闸门放行=true 执行标志=false
         算法步骤=skipped 数据日=2026-09-10(trading) CST=13:46 B三模块=3/8 D最终推荐=1/1
##[notice]盘中时段(CST 13:46)拒绝算法链长任务 —— 保护盘中数据 + 释放 cn runner（合规，非故障）
```

**闸门判 BLOCKED 是设计正确的（合规）**。问题在派发侧。

### 派发频次（近 1 小时，全部 `workflow_dispatch`，actor `ah-quant999`）

```
12:49  12:55  12:58  13:02  13:05  13:08(failure)  13:19
13:29  13:36  13:42  13:45  13:48   ← 12 次/小时，仍在继续
```

### 三个实锤危害

1. **烧你机器的 runner 分钟**：日志里 `pythonLocation: D:\actions\cn-runner\_work\_tool\Python\3.13.15\x64`
   → 名为「云端」实为**自托管 cn runner（小九单位机）**。每次都要跑 checkout + 重装全部 A 股依赖，耗时 0.9~4.2 min。
2. **连锁触发构建部署 + pages build**：每轮空转 success 后触发一次 `v8 构建部署` → 13:34 两个构建部署同并发组互顶 → run 34566460489 cancelled（jobs 显示 gate/build 双双 cancelled）。
3. **掩盖真实落后**：空转 run 判 success，看板「全绿」但数据其实没更新。

### 🔧 一劳永逸修复方案（**不要重跑**）

**方案 A（推荐，改 1 处即全网生效）** — 在 `.github/workflows/v8_algo_cloud.yml` 的 job 上加两条：

```yaml
concurrency:
  group: v8-algo-cloud
  cancel-in-progress: true      # 高频派发自动只保留最新 1 个，pending 不堆积
```

再把「盘中时段门禁」从现在的 step 8 **上移到 job 最前面**（step 1 之前，5 秒内短路退出），
让 checkout / 装依赖 / 解析日期这些重活**根本不执行**。当前 step8 才判，前面 7 步已经白烧。

**方案 B（治本，但派发源多）** — 派发侧统一加「非盘后时段不派发」门禁。
已知派发源 ≥7 个：`v8_cloud_watchdog.py:724`、`v8_health_check.py:698`、`guard_v8_freshness.py:225`、
`v8_intraday_healer.py:46`、`v8_runner_guard.py:479`、`cloud_dispatcher.py`、本地 WorkBuddy 自动化。
各自内存去抖、互不可见 → 逐个改维护成本高，**建议以方案 A 为主**。

---

## 3. 遗留项复核（10:27 那轮交接的 4 项）

| # | 遗留项 | 现状 | 证据 |
|---|---|---|---|
| ① | `v8_algo_cloud.yml` 回退步骤 `if:` 失效致假成功 | ✅ **已修** | 远端 L177 现为 `if: steps.co.outcome == 'failure'`；实测 step3 = skipped（未误触发） |
| ② | `INDEX_HISTORY.js` 被 republish 刷成假新鲜 | ❌ **未修** | 见 §3.2 |
| ③ | 盘后算法链槽位被 1.7h 长挂 run 占用 | ✅ 已缓解 | 近期 run 耗时 0.9~4.2m，无长挂 |
| ④ | index.html `?v` 口径分裂 | ❌ **未修** | 见 §3.3 |

### 3.2 ❌ INDEX_HISTORY 假新鲜（P0 数据失真）

`data/INDEX_HISTORY.js`（main 分支权威值）：

| 字段 | 值 |
|---|---|
| `meta.update_time` | **2026-09-08T16:54:07** |
| 文件尾 `update_time` | 2026-09-10 21:39:15 ← **被 republish 刷过** |
| `republish_time` | 2026-09-10 22:18:15 |
| `klines` 末条日期 | **2026-09-07**（1134 条） |

→ **缺 09-08 / 09-09 / 09-10 / 09-11 四个交易日的 K 线**，但文件尾时间戳看着「昨天才更新」。
`intraday_watch.py` 用 `re.search` 取首个（= meta）→ 判 68.9h 是**内容真实落后，非误报**。

**一劳永逸修法**：`republish` 流程**只准写 `republish_time`，禁止覆盖 `update_time`**。
同时所有新鲜度判读脚本统一读 `meta.update_time`（内容级），不读文件尾。

### 3.3 ❌ index.html `?v` 口径分裂（P1 缓存失效）

```
?v 值分布: 1789105267 × 99   ← unix 时间戳（10:27 那轮是 1789093393，值变了但结构问题依旧）
           20260911   ×  1
           20260910   ×  1
BUILD = a0ddef3d2        引用总数 101
```

两个互顶写入方：一方写 **unix 时间戳**，另一方写 **日期串**。
后果：CDN 要么整站缓存戳一起变（全量回源浪费），要么部分文件吐旧副本（看板数据落后）。

**一劳永逸修法**：全站统一为 **内容 sha10**（幂等可校验）。时间戳只能「看着在变」，无法验证是否与内容匹配。

---

## 4. 数据落后清单（真实内容级，非误报）

| 文件 | 落后 | 内容 `update_time` | `republish_time` |
|---|---|---|---|
| INDEX_HISTORY | 68.9h | 09-08T16:54（klines 末 09-07） | 09-10 22:18 |
| BACKTEST_TDX | 37.8h | 2026-09-10 | 09-10 04:58 |
| BACKTEST_COMPREHENSIVE | 34.6h | 09-10 03:11:27 | 09-10 04:58 |
| TOP10_DAILY | 33.0h | 09-10 04:46:46 | 09-10 13:57 |
| INST_TRADE | 31.5h | 09-10 06:17:07 | 09-10 13:57 |
| SUSPENSION_ALERT | 31.4h | 09-10 06:23:31 | 09-10 13:57 |
| NT_DATA | 31.4h | 09-10 06:24 | 09-10 13:57 |
| SECTOR_FUND_FLOW_TREND | 31.4h | 09-10 06:25 | 09-10 13:57 |

闸门自报：`B三模块=3/8`（8 个选股三模块仅 3 个是本数据日盘后产出），`D最终推荐=1/1`。

⚠️ **注意 `republish_time` 全部晚于 `update_time` 数小时** → 这正是「假新鲜」的制造机制，与 §3.2 同源。

### 建议追加（防死锁）

闸门用「内容级就绪」判断上游，若上游产物本身需算法链产出 → **循环依赖死锁**：上游不新 → 不跑 → 上游永不新。
建议加**陈旧强制放行**：当上游落后 > 2 个交易日时，闸门强制 `proceed=true`（宁可重算，不可永久僵死）。

---

## 5. 根因 5（P1 · 新）：13:34 构建部署被互顶 cancel

run **34566460489**（v8 构建部署，13:34，cancelled，0.1m）：jobs 显示 `gate` / `build` **双双 cancelled**，
且 13:34 同时存在另一个构建部署 34566463451 = success。
→ 同并发组内被后到的 run 顶掉。**修了根因 1（高频空转不再触发构建部署）后自然消失。**

---

## 6. 给小九的行动建议（按优先级）

| 优先级 | 动作 | 位置 |
|---|---|---|
| P0 | 加 `concurrency: cancel-in-progress: true` + 盘中门禁上移到 job 最前 | `.github/workflows/v8_algo_cloud.yml` |
| P0 | republish 禁止覆盖 `update_time`；新鲜度统一读 `meta.update_time` | 云端生成器 / republish 脚本 |
| P1 | `?v` 全站统一内容 sha10，禁用时间戳 | index.html 写入方（两个） |
| P1 | 闸门加「上游落后 > 2 交易日强制放行」防死锁 | `v8_algo_cloud.yml` 闸门逻辑 |
| P2 | 收窄本巡检自动化 cron 到盘中档位（已连续 12 轮非盘中空跑） | WorkBuddy 自动化调度 |

**⚠️ 明确不建议**：不要手工重跑盘后算法链（盘中必然再次被 BLOCKED，纯浪费）；
不要为「追数据」在盘中堆 dispatch。上述数据属盘后批次，修完 P0 后由盘后 cron 自然补齐。

---

## 7. 复用要点（下次巡检直接照做）

1. index.html > 1MB 时 Contents API 不返回 `content` → 走 `/git/trees/main` 拿 blob sha → `/git/blobs/{sha}` + `Accept: raw`。
2. job logs 401 → 自定义 `HTTPRedirectHandler`，跨主机重定向不转发 Authorization（已验证可拿到日志）。
3. **判空转看 step 数**：一个 run 若 step 9-14 全 skipped 而 step 15 success ⇒ 闸门拦下的合规空转，不是故障。
4. 本地工作区 `data/` 不可信（坚果云不拉远端），一律以 main 分支 Contents API 为准。

---

*生成：阿狸咪 · 2026-09-11 13:48 CST · 巡检退出码 1*
*复跑命令：`python C:\Users\HH20210606\.workbuddy\v8_watch\intraday_watch.py`*
