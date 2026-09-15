# 🚨 URGENT · v8 盘中巡检告警 → 小九（白天值班 7:45-17:45）

- **发现时间**：2026-09-10 13:21 CST（周四·盘中 13:00-15:00 档）
- **巡检退出码**：1
- **是否踩踏风暴**：⚠️ **不是** rate-limit 风暴（活跃并发 1、API 配额 5000/5000），
  但是**「多源派发互相顶掉 pending run」型踩踏** —— 40 分钟内 8 次派发 7 次被 cancel。
- **处置**：✅ 全程**未加派任何一次 dispatch**。

---

## 一句话结论

> 不是 GitHub 限流，是**自家人互相顶**。
> ① `v8-cn-fetch-cloud` 并发组只保留 1 个 pending run，7 个派发源各派各的、去抖状态不共享 →
> 后派的把先排队的 cancel 掉，40 分钟 8 派发只有 1 次跑完；
> ② `v8_health_check.py:2627` 的 `sys.exit(2)` 把「有 warn 项」当成硬失败 →
> 盘中算法链「🩺 刷新 HEALTH_CHECK.js」红 → 「📤 推送变更到 main」恒 skipped。
> 两者叠加 → 6 个日更数据文件停在 **09-08 17:xx，落后 44h**。

---

## 一、现场事实（全部经 GitHub API 查证，非推测）

| 时间(CST) | run | workflow | 结论 | 触发源 | 备注 |
|---|---|---|---|---|---|
| 12:32:44 | 34437593624 | 🇨🇳 中国数据抓取(云端) | ✅ success | dispatch | **40 分钟内唯一一次成功** |
| 12:32:46 | 34437595678 | 同上 | ❌ cancelled | dispatch | job 未启动 |
| 12:33:26 | 34437638216 | 同上 | ❌ cancelled | dispatch | job 未启动 |
| 12:37:50 | 34437920287 | 同上 | ❌ cancelled | dispatch | job 未启动 |
| 12:37:53 | 34437922489 | 同上 | ❌ cancelled | dispatch | job 未启动 |
| 12:50:29 | 34438730515 | 同上 | ❌ cancelled | dispatch | 排队 450s 后被杀 |
| 12:57:58 | 34439199856 | 同上 | ❌ cancelled | **schedule** | |
| 13:10:53 | 34440040904 | 同上 | ❌ cancelled | dispatch | 5 秒后被杀 |
| 13:10:56 | 34440043987 | 同上 | ❌ cancelled | dispatch | 109 秒后被杀 |
| 13:12:43 | 34440156217 | 同上 | ❌ cancelled | dispatch | |
| 12:58:01 | 34439202469 | 🩺 健康巡检 | ❌ failure | workflow_run | step「🔁 自愈验证：10分钟后回查仍 fail」 |
| 12:41:08 | 34438131394 | ☁️ 盘中算法追踪(轻量) | ❌ failure | dispatch | step「🩺 刷新 HEALTH_CHECK.js」 |
| 12:19:57 | 34436767070 | ☁️ 盘中算法追踪(轻量) | ❌ failure | dispatch | 同上 |

**关键判据**：被 cancel 的 run **连一个 job 都没启动**（`jobs` 返回空）→ 不是跑挂了，
是**在排队阶段就被顶掉**，符合 concurrency 槽位溢出特征。

**数据陈旧（main 分支权威值，非本地 mtime）**

| 文件 | update_time | 落后 |
|---|---|---|
| INDEX_HISTORY.js | 2026-09-08 16:54 | 44.4h |
| INST_TRADE.js | 2026-09-08 17:24 | 43.9h |
| SUSPENSION_ALERT.js | 2026-09-08 17:29 | 43.9h |
| NT_DATA.js | 2026-09-08 17:30 | 43.8h |
| SECTOR_FUND_FLOW_TREND.js | 2026-09-08 17:31 | 43.8h |
| GOLD_POOL.js | 09-08 前后（字段格式特殊，解析不到） | ~43.6h |

---

## 二、根因 A（主）：concurrency 组只有 1 个 pending 槽，派发源却有 7 个

### 证据（仓库自己写着的，v8_health_check.py L607-622）

```
云端 fetch/build workflow 均设 `concurrency: cancel-in-progress: false`，
GitHub 该模式下每个 group **只保留 1 个 pending run**，新的 workflow_dispatch
会把原先排队的那个 cancel 掉。同一轮巡检里看门狗 auto_dispatch 与本文件
self_heal 各派发一次 → 后者顶掉前者，实测导致盘中数据断档 69 分钟
```

### 派发源清单（全部命中 `v8-cn-fetch-cloud` 组，各自独立去抖、状态不共享）

| # | 派发源 | 代码位置 |
|---|---|---|
| 1 | `v8_cn_fetch_cloud.yml` 自身 cron | `cron: '25 0 * * 1-5' / '20 9-11 * * 1-5'` |
| 2 | `v8_cloud_watchdog.py` | L724 dispatch CN_WORKFLOW_ID |
| 3 | `v8_health_check.py` self_heal | L698 dispatch CN_WORKFLOW_ID |
| 4 | `guard_v8_freshness.py` | L225 dispatch CN_WORKFLOW_ID |
| 5 | `v8_intraday_healer.py` | L46 dispatch CN_FETCH_WF_NAME |
| 6 | `v8_runner_guard.py` / `v8_postclose_guard.py` / `v8_dispatch_fetch.py` / `v8_t1_guard.py` | L479 / L178 / — / L120 |
| 7 | 本地 WorkBuddy 自动化（看门狗驱动每 15 分 + 阿狸咪守卫） | 仓库外 |

去抖逻辑 `_has_pending_run()` 只查 **pending**、刻意放行 in_progress（L617-618 注释）。
但 `cancel-in-progress:false` 下 **in_progress + 1 pending 就是满槽**，
再来一个 dispatch 就顶掉那个 pending → 所以「放行 in_progress」在实际槽位模型下是**错的**。

另有 `v8_cloud_watchdog.py` L432 的 `POST /actions/runs/{id}/cancel`（算法链卡死兜底），
会额外杀 run。

---

## 三、根因 B：`sys.exit(2)` 阻断整条推送链（11:28 已交接，**main 上仍未改**）

`v8_health_check.py:2627`
```python
sys.exit(0 if report["overall"] == "ok" else 2)
```

- 盘中 `overall` 必然非 ok（TRIPLE_HISTORY / VOLATILITY 等**盘后产物**按日更阈值判陈旧）→ rc=2。
- `v8_algo_intraday_lite.yml` L98-102 该 step **无** `V8_HEALTH_SOFT_EXIT`，且 2026-09-08
  已按主人令删掉 `continue-on-error` / `|| true` → step 直接红 → **L104「📤 推送变更到 main」恒 skipped**。
- 实测：`v8_algo_intraday_lite.yml` 近期 **34 失败 / 6 成功**，今日仅 10:07 一次成功；
  `v8_health_patrol.yml` 19 失败同源（step「🔁 自愈验证：10 分钟后回查仍 fail」）。

---

## 四、一劳永逸修复（**不要重跑**，重跑只会再被顶掉）

### 修复 A：让「派发」变成单点串行 —— 三档任选，建议直接上 A1

**A1（推荐·根治）**：所有守护脚本**禁止直接 dispatch** `v8_cn_fetch_cloud.yml`。
改为：只写派发意图（`raw_data/dispatch_request.json`，带 `requested_at` + `reason`），
由仓库里已有的 **`v8_slot_scheduler.yml`** 单点串行消费——它先查同组
`in_progress OR queued` 是否存在，**存在即跳过本轮**，不存在才派发。
好处：去抖状态从「7 份内存」收敛成「1 份磁盘契约」，跨机跨脚本天然一致。

**A2（最小改动·5 分钟止血）**：把所有派发前置检查统一改成
> `in_progress` **或** `queued` 任一存在 → **直接 return，不派发**

即把 `v8_health_check.py:607 _has_pending_run()` 的语义从「只查 pending」改为「查 pending + in_progress」
（L617-618 那段「只有 in_progress 时照常派发」在满槽模型下必须反转），
并同步改 `v8_cloud_watchdog.py` 的同名函数。

**A3（改槽位模型）**：`v8_cn_fetch_cloud.yml` 去掉 workflow 级 `concurrency`，
改在 job 第一步做**全局互斥锁**（`raw_data/.fetch_lock.json` 带 TTL，拿不到锁 `exit 0`）。
彻底摆脱 GitHub「1 pending 槽」这个反直觉行为。

> 另外 `v8_cloud_watchdog.py:432` 的 cancel 兜底建议加**白名单**：只 cancel 自己派发、
> 且 stuck 超过 N 分钟的 run，避免误杀刚入队的正常 run。

### 修复 B：一行 env，解开推送链（零代码风险）

`v8_algo_intraday_lite.yml` 的 step「🩺 刷新 HEALTH_CHECK.js」加 env：
```yaml
      - name: "🩺 刷新 HEALTH_CHECK.js"
        env:
          V8_HEALTH_SOFT_EXIT: "1"     # ← 新增
        run: |
          python v8_health_check.py || { echo "::error::v8_health_check.py 失败，健康面板未刷新"; exit 1; }
```
依据：`v8_health_check.py` L2624-2626 **已内置**该开关（2026-09-03 阿狸咪加的软退出模式），
行为是「报告照写 + 自愈照跑 + 邮件照发 + rc=0」，**告警职责仍由 strict lane（健康巡检/每日审核）承担**，
且 `|| exit 1` 保留——**真崩溃照样红**，不违反 2026-09-08「禁止假 success」主人令。

`v8_health_patrol.yml` 的「🔁 自愈验证」step 同处理。

> 备选（若不想动 workflow）：把 `v8_health_check.py:2627` 改成
> 「`write_health_js` 成功落盘 ⇒ exit 0；异常未落盘 ⇒ exit 2」，
> 把「有 warn/fail 项」与「本次执行失败」解耦。但会影响所有 lane 的严格语义，
> **不如 B 的 env 方案安全**。

---

## 五、⛔ 明令

1. **不要再手工 dispatch `v8_cn_fetch_cloud.yml`** —— pending 槽只有 1 个，
   此时加派 = 顶掉正在排队的那个，火上浇油。等当前 in_progress 跑完再说。
2. 修好 A 之前，**不要靠「多派几次碰运气」补数据**，实测 8 派 1 中就是这么来的。
3. 数据落后 44h 属**盘后批次断档**，修好 A 后由 `cron '20 9-11 * * 1-5'`（= CST 17:20/18:20/19:20）
   自然补齐；**无需手工补跑历史**。

---

## 六、阿狸咪已做 / 未做

| 项 | 状态 |
|---|---|
| 判定非 rate-limit 风暴、未加派 dispatch | ✅ |
| 抓全失败 run 的 job 级根因 | ✅ |
| 定位 cancel 来自 concurrency 槽位 + `v8_cloud_watchdog.py:432` | ✅ |
| 交叉核验 main 分支文件 update_time | ✅ |
| 改 workflow / 脚本 | ❌ **未动**（白天归小九；阿狸咪 PAT 对 `.github/workflows/*` 403，且本轮以交接为准） |

---

*由 v8 盘中安全巡检自动生成 · 2026-09-10 13:25 CST · 阿狸咪（夜班/周末）*
