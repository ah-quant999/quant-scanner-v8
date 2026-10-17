# URGENT · v8 盘中巡检异常交接（阿狸咪 → 小九）

- 时间：2026-09-11 2026-09-11 10:37 CST（盘中 10:27 档巡检）
- 巡检结论：退出码 **1（有异常）**，但 **非 rate-limit 踩踏风暴**
- 本轮动作：**全程未加派任何 dispatch**（遵守防踩踏铁律）

---

## 0. 先说结论：不是风暴，别加派

| 指标 | 实测 | 判定 |
|---|---|---|
| 活跃/排队 run | in_progress 2（中国数据抓取 / 盘后算法链）、pending 1 | 正常，无堆积 |
| 近 3h 真实失败/异常取消 | 1 次（构建部署 run `34553216859` cancelled） | 噪声级，随后 02:18/02:22 两次均 success |
| API 配额 | 充足，无 403 secondary rate limit 迹象 | 安全 |

**唯一需要小九动手的是下面 4 个根因，且都要求「一劳永逸修复」，不要靠重跑救火。**

---

## 1. 【P0·假成功】`v8_algo_cloud.yml` 回退步骤条件失效 → 全链 skipped 却判成功

**证据**：失败 run `34547076648`（09-11 00:34 UTC）job `algo` 步骤序列：

```
📥 Checkout 源码（云端 git 直连，秒级）        -> success
📥 回退·经 GitHub API 同步源码（仅 checkout 失败时） -> failure   ← checkout 明明成功，它却跑了并失败
🔧 修复 git 安全目录                          -> skipped
🗓 解析数据日期                               -> skipped
🐍 配置 Python                                -> skipped
🔒 批次闸门                                   -> success
🧮 运行盘后算法链                              -> skipped
📤 唯一推送                                   -> skipped
🛡 机器校验                                   -> skipped
🛡 结果问责（按目标批次 + 产物完整性 · 杜绝假成功） -> success    ← 全链没干活，它判 success
```

**两个 bug 叠在一起**：
1. 「回退·经 GitHub API 同步源码」的 `if:` 条件没能正确识别 checkout 是否失败（历史同款：2026-08-05 run#16/#17 也挂在这一步，当时归因于 cn runner 网络；现在跑在 self-hosted cn 上同样复现）。
2. 「🛡 结果问责」自称"杜绝假成功"，但对前序步骤 **skipped** 不做校验 → 产出全空仍判 success，是典型的**软失败假绿**。

**一劳永逸修法**（不要重跑）：
- 回退步骤条件显式绑定 checkout 结果：
  ```yaml
  - name: "📥 回退·经 GitHub API 同步源码（仅 checkout 失败时）"
    id: fallback_sync
    if: always() && steps.checkout.outcome == 'failure'
  ```
  并给 `📥 Checkout` 显式加 `id: checkout`。
- 「🛡 结果问责」增加前置断言：若 `steps.run_chain.outcome == 'skipped'` 或 `steps.push.outcome == 'skipped'`，必须 `exit 1`（Gate 判 NONE 空转才允许 success，并显式打印 `target=NONE`）。
- 建议给该 workflow 的 `algo` job 加 `timeout-minutes: 90`，避免长挂占槽（见第 3 条）。

---

## 2. 【P0·假新鲜】INDEX_HISTORY 内容停在 09-07，却被 republish 刷成"看起来新鲜"

**证据**（远端 main `data/INDEX_HISTORY.js`，API 实测）：

```
meta.update_time   = 2026-09-08T16:54:07      ← 真正的"内容时间"
klines 最后一条     = {"d":"2026-09-07", ...}   ← K 线只到 09-07
文件尾 update_time  = 2026-09-10 21:39:15      ← 重新发布刷出来的
republish_time      = 2026-09-10 22:18:15
```

- 即：**09-08 / 09-09 / 09-10 三个交易日的指数 K 线没有追加**，文件只是被重新发布了一遍。
- 危险点：任何取**文件尾部 `update_time`** 判新鲜度的脚本
- 已核对：`intraday_watch.py:187` 用 `re.search` 取**首个** `update_time`（即 `meta.update_time`），所以本轮判 65.6h 是**内容真实落后，判对了，不是误报**；
  但 `v8_health_check.py` 等其它脚本取的是哪个尚未逐条核实，**请一并审计**

**一劳永逸修法**：
1. **新鲜度判据改为「内容时间」优先**：对 `INDEX_HISTORY` 这类带 `meta.update_time` 的产物，判定顺序改为
   `meta.update_time` > `klines[-1].d` > 文件尾 `update_time`；单纯 republish 不得刷新新鲜度。
2. 查 `INDEX_HISTORY` 生成器为什么 09-08 之后不再追加：meta.update_time 停在 09-08T16:54，说明那天之后生成器没再成功写过内容（与第 1 条的假成功是同一条链路，修完第 1 条后大概率自然恢复）。

---

## 3. 【P1·槽位占用】盘后算法链 90 分钟被派发 14 次，且有 run 长挂 1.7h 占槽

**证据**（`v8_algo_cloud.yml` 最近 15 次 run）：

```
09-11 01:05:46Z  pending        id=34549258466   ← 排不上队
09-11 00:56:30Z  cancelled      id=34548603512
09-11 00:53:20Z  in_progress    id=34548389074   ← 08:53 CST 起到 10:40 仍未结束，1.7h+
09-11 00:50:12Z  success
09-11 00:34:42Z  failure        id=34547076648   ← 见第 1 条
09-11 00:22:16Z / 00:19:08Z / 00:11:28Z / 00:09:49Z / 00:06:42Z / 00:03:34Z / 09-10 23:54 / 23:51 / 23:35 / 23:32  success
```

- 23:32 → 01:05 的 **93 分钟里派发了 14 次**，绝大多数被 gate 判 NONE 空转（合规），但：
  - 长挂的 `34548389074` 占着 concurrency 槽（「🧮 运行盘后算法链」步骤 in_progress，后续 5 个步骤全 pending）；
  - `34549258466` 因此一直 pending，且按「同组只保留 1 个 pending」规则，后面再派发会把前面的顶掉。
- 这已具备 **09-10 13:21 交接的"多源派发互顶"型踩踏雏形**，只是当前并发还没到 5+，未触发 403。

**一劳永逸修法**（**不是加派，是减派 + 去抖**）：
1. 给 `algo` job 加 `timeout-minutes: 90`（算法链正常应 <30min，超时立即让位）。
2. 所有派发源（`v8_cloud_watchdog.py` / `v8_health_check.py` / `guard_v8_freshness.py` / `v8_intraday_healer.py` / `v8_runner_guard.py` / WorkBuddy 自动化）统一走**同一个去抖函数**：派发前先 `GET /actions/workflows/v8_algo_cloud.yml/runs?status=in_progress`，**有 in_progress 就绝不派发**。现在各派发源各存各的内存状态，互不可见，这是根因。
3. 去抖状态落到仓库内一个共享文件（如 `raw_data/.dispatch_lock.json`，带 UTC 时间戳 + 过期自动清理），让跨机跨进程可见。

---

## 4. 【P1·仍未闭环】index.html 的 `?v` 口径三分裂（09-10 14:41 已交接，现状更糟）

**证据**（远端 main `index.html`，git blob `1261df8a`，923209 字节）：

```
?v 引用 102 处，distinct 3 种：
  1789093393   ← unix 时间戳（09-11 10:23 CST）
  20260910     ← 日期戳
  20260911     ← 日期戳
BUILD = efd9ad726
```

- 说明现在**至少 3 个写入方**在改 `?v`：有的写 unix 时间戳、有的写日期戳、`v8_stock_quote_refresh.yml` 写内容 sha10。
- 后果：缓存戳不幂等、无法校验，CDN 仍可能吐旧副本（这正是 09-10 那轮"改完第二天数据还是旧的"的老病根）。

**一劳永逸修法**：全站 `?v` 统一为 **内容 sha10**（幂等、可校验），禁用时间戳与日期戳；给 `v8_cache_buster_reconcile.yml`（🛡️ v8 缓存戳实时对齐）加一条**校验+矫正**：凡 `?v` 非 10 位 hex 一律按内容 sha10 重写。

---

## 5. 本轮已闭环 / 已排除

| 项 | 状态 |
|---|---|
| `v8_stock_quote_refresh.yml` L379 `m.group(3)` IndexError（09-10 14:41 交接） | ✅ **已修复**：远端 L389-390 现为 `(data/STOCK_QUOTE\.js\?v=)([a-f0-9]+)` + `m.group(1)+content_sha`，两个捕获组，无越界 |
| 盘中类数据新鲜度（57/62 个） | ✅ 全部合格，盘中链路健康 |
| 踩踏风暴 / 403 rate limit | ✅ 排除，活跃并发 2 |

---

## 6. 给小九的行动清单（按优先级）

1. 修 `v8_algo_cloud.yml` 回退步骤 `if:` 条件 + 「结果问责」skipped 断言（第 1 条）— 这是**假成功**总闸门。
2. 新鲜度判据改「内容时间」优先，先修 `INDEX_HISTORY` 缺失 3 个交易日（第 2 条）。
3. `algo` job 加 `timeout-minutes: 90` + 统一派发去抖（第 3 条）。
4. `?v` 统一 sha10（第 4 条）。

> ⚠️ 全部为**根因修复**，请勿用"手动重跑一遍"代替。修完第 1、2 条后，INDEX_HISTORY 会在当日 19:15 主档自然补齐。