# 🚨 URGENT · 2026-09-11 15:05 盘中巡检交接（阿狸咪 → 小九）

> 巡检时间：2026-09-11 15:00（周五·盘中 13:00-15:00 档）
> 巡检结论：**退出码 1（发现异常）**
> **非踩踏风暴**：GitHub core 配额 5000/5000 满、无 403、无 5+ 并发风暴。
> **全程未加派任何 dispatch**（遵守风暴铁律）。
> 数据落后基准：**GitHub main 分支（Contents API 权威）**，非本地工作区。

---

## 0. 一句话结论

**盘后算法链在盘中 1 小时被派发 15 次，每次都跑完整套前置步骤后被闸门合规拦下、判 success 空转，白占两台自托管机；闸门脚本本身疑似已失效，今晚 15:05 后首批大概率直接报红。**

---

## 1. 根因 ①（P0 · 复发且加剧 · 13:48 已交接未修）

### 现象
`☁️ v8 盘后算法链(云端)` 近 3 小时 **15 次** `workflow_dispatch`，平均 **4 分钟一次**：

```
14:01  4.0m success   14:20  2.8m success   14:42  6.1m success
14:07  5.8m success   14:23  2.8m success   14:51  0.9m success
14:13  2.7m success   14:26  1.0m success   14:54  0.9m success
14:16  2.5m success   14:29  1.0m success   14:57  2.9m success
                      14:32  7.7m success   15:00  in_progress
```

### 链上实证（run 34572198334 / 34571971809）
- 闸门输出 `target_stage=MARKET_HOURS_BLOCKED`
- 核心 step 9-14 全部 `skipped`，末尾「🛡 盘后算法链结果问责」判 **success**
- `pythonLocation` 两条机器路径：
  - `D:\actions-runner-v8\_work\_tool\Python\3.13.14\x64`（runner `lemoncat-cn`）
  - `D:\actions\cn-runner\_work\_tool\Python\3.13.15\x64`（runner `alimi-cn`）
  → **两台自托管机同时被空转占用**

### 判读（重要）
`v8_algo_cloud.yml` L421-435 是你（小九）今天加的「源头无关盘中硬闸门」（`DOW<=5 && HHMM 925..1505` → BLOCKED），
L700 判 BLOCKED 为**合规空转 success**。**闸门本身设计正确、不要改坏它。**
**病灶 100% 在派发侧**：没有任何「盘中不派盘后算法链」的门禁。

### 连锁损失
- 每次算法链跑完连锁触发 `☁️ v8 构建部署(云端ubuntu)` → 近 3h **15 次**
- → `pages build and deployment` **47 次**，其中 **19 次 cancelled**（同组互顶）

### 一劳永逸修复（按优先级，建议全做）
| # | 动作 | 位置 |
|---|---|---|
| A1 | **把时段门禁上移到 job 最前**：在 job 顶部新增 `if:` 或第一个 step 里先算 `HHMM`，盘中直接 `exit 0`，不跑 checkout/装依赖（现在闸门在 L379，前 8 步白烧 1-8 分钟） | `v8_algo_cloud.yml` job 开头 |
| A2 | **派发侧统一门禁**：所有会 `workflow_dispatch` 盘后算法链的脚本（已知 7 个源：`v8_cloud_watchdog.py` / `v8_health_check.py` / `v8_runner_guard.py` / `v8_intraday_healer.py` / `guard_v8_freshness.py` / `cloud_dispatcher.py` / 本地自动化）**共用同一个 `can_dispatch()` 判定**：盘中 09:25-15:05 且周一~五 → 直接 return，不派 | 各派发脚本 |
| A3 | **`concurrency` 改 `cancel-in-progress: true`**：盘中反正都是空转，被顶掉无损；盘后由 A2 保证不会高频派 | `v8_algo_cloud.yml` L94-96 |
| A4 | **算法链跑完不要无条件触发构建部署**：仅当本轮真有产物变更（`target_stage != MARKET_HOURS_BLOCKED`）时才触发 | 链尾触发步 |

---

## 2. 根因 ②（P1 · 新发现 · 疑似，需你今晚立刻验）

### 现象
闸门 step 的 `set -x` trace 显示 **L397 被实际执行**：
```
echo "::error title=v8-stage-gate-crash::批次闸门未产出判定（脚本异常/输出解析失败）—— 拒绝放行，请排查"
```
即 `L393 TGT=$(printf '%s' "$OUT" | grep -m1 '^target_stage=' | cut -d= -f2)` **取到空值**
→ 说明 `.github/scripts/v8_stage_gate.py` 没有产出 `target_stage=` 行（脚本异常 / 输出解析失败）。

只是**恰好被盘中硬闸门（L435）兜住**写了 `MARKET_HOURS_BLOCKED`，所以看起来一切正常。

### 风险（今晚就会爆）
15:05 之后盘中闸门不再拦截，若 `TGT` 仍为空：
- `L707: echo "::error title=v8-algo-no-gate::批次闸门未产出判定（脚本异常）—— 不能当成功，请排查"; exit 1`
- → **今晚 16:40 / 18:10 / 20:00 / 21:00 四轮唤醒全部报红，算法链整晚停摆**

### 建议动作
1. 立刻本地跑一次 `python .github/scripts/v8_stage_gate.py`（带上 workflow 里同样的 env），看 stdout 有没有 `target_stage=` 行。
2. 若没有 → 修 `v8_stage_gate.py` 的异常（很可能是未捕获异常被吞 / 输出走了 stderr）。
3. 顺手加一条：**闸门脚本无输出时必须 job 失败**，不要让下游 step `skipped` 静默。

---

## 3. 遗留项复核（对照 13:48 交接）

| # | 遗留项 | 本轮状态 | 证据 |
|---|---|---|---|
| ① | `v8_algo_cloud.yml` 回退步骤 `if:` 失效致假成功 | ✅ **已修** | L177 `if: steps.co.outcome=='failure'`，本轮未见异常 |
| ② | `INDEX_HISTORY.js` 被 republish 刷成假新鲜 | ❌ **未修，且恶化** | 见下 |
| ③ | 盘后算法链槽位被长挂 run 占用 | ✅ **已缓解** | 各 run 0.1-7.7m，无 1h+ 长挂 |
| ④ | `index.html` `?v` 口径分裂 | ❌ **未修，且恶化** | 见下 |

### ② INDEX_HISTORY 假新鲜（main 权威，内容级）
```
首个 update_time(内容级, meta) = 2026-09-08T16:54:07
文件尾 update_time             = 2026-09-10 21:39:15
republish_time                 = 2026-09-10 22:18:15
klines 末条日期                 = 2026-09-07   （共 1134 条）
```
→ **真实内容落后 70.1h**，缺 **09-08 / 09-09 / 09-10 / 09-11 四个交易日**，
却被 republish 刷成「看着新鲜」。巡检脚本取首个（meta）判 70.1h 是**内容真实落后，判对非误报**。

修法（一劳永逸）：**禁止 republish 改写 `update_time`**，republish 只能写 `republish_time`；
新鲜度判定一律以 `meta.update_time` / 内容级时间戳为准。

### ④ `?v` 口径分裂（main 权威）
103 处引用，**4 种口径**：
| 处数 | 值 | 说明 |
|---|---|---|
| 100 | `?v=1789110339` | unix 时间戳（生成器「原子提交」写） |
| 1 | `?v=20260911` | `data/maharo_macro.js` 日期戳 |
| 1 | `?v=20260910` | `data/maharo_insights.js` **日期戳停在昨天，内容已变 → CDN 吐旧副本** |
| 1 | `?v=<sha>` | `data/DO_NOT_DELETE.js` **模板占位符原样泄漏，替换逻辑没渲染** |

修法：全站统一为**内容 sha10**（幂等可校验），禁用时间戳/日期戳；`DO_NOT_DELETE.js` 若非真实数据引用则直接删掉该行。

---

## 4. 数据落后清单（main 权威 · 内容级 update_time）

| 文件 | 落后 | 类别 |
|---|---|---|
| INDEX_HISTORY | **70.1h** | post_close |
| BACKTEST_TDX | 39.0h | post_close |
| BACKTEST_COMPREHENSIVE | 35.8h | post_close |
| TOP10_DAILY | 34.2h | post_close |
| INST_TRADE | 32.7h | post_close |
| SUSPENSION_ALERT | 32.6h | premarket |
| NT_DATA | 32.6h | premarket |
| SECTOR_FUND_FLOW_TREND | 32.6h | post_close |

> 新鲜 OK 51 个，未分类跳过 42 个。本地工作区滞后 main 属坚果云不拉远端，非故障。

---

## 5. 两条「看着新鲜其实很陈」的被 cancel run

| run | 结论 | jobs | 判读 |
|---|---|---|---|
| 34571593916（中国数据抓取·小九应急） | cancelled | **0** | 排队阶段被顶掉，**未真正启动**，非跑挂 |
| 34570723833（中国数据抓取） | cancelled | **0** | 同上 |

**不要去翻 job 日志**（没有 job）。要查的是 concurrency 槽位与派发源。

---

## 6. 阿狸咪本轮遵守的约束

- ✅ 未加派任何 `workflow_dispatch`
- ✅ token 仅从 `C:\Users\HH20210606\.workbuddy\v8_gh_pat` 读取，未打印、未写入任何文件
- ✅ 未使用 `git add -A`，未 cp 备份进仓库；本文档经 **Contents API** 推送到 main
- ✅ 新鲜度只看文件内 `update_time` 字段，不看 mtime
- ✅ 白天（7:45-17:45）归小九值班，本轮只诊断+交接，**未改任何业务代码**

---

## 7. 建议处理顺序（今晚）

1. **先验 ②**（`v8_stage_gate.py` 是否空输出）—— 不修则今晚四轮全红
2. **再做 A2**（派发侧盘中门禁）—— 根治 15 次/小时空转
3. 再做 A1 / A3 / A4（截断白烧 + 槽位 + 连锁部署）
4. ④ `?v` 统一 sha10 + 清掉 `<sha>` 泄漏
5. ② republish 禁止改写 `update_time`

---

_生成：阿狸咪 · 2026-09-11 15:05 CST_
_诊断脚本（仓库外可复用）：`C:\Users\HH20210606\.workbuddy\v8_watch\_diag_20260911_1500.py` / `_diag2_...py` / `_diag3_...py`_
