# 盘前审核报告（2026-09-10 08:48 · CST）

> 审核人：小九机（lemoncat-cn）｜宗旨：盘中不踩踏不风暴，但兜底必须成功｜方法：实时读 Actions run 时间戳 + 自动化 prompt + workflow concurrency 配置

## 一、结论速览

| 项 | 结论 |
|---|---|
| 踩踏/风暴风险 | ✅ **已清除**（盘前实测密集派发源已停） |
| 兜底链路 | ✅ **三重冗余可靠**（主调度自带 + 看门狗补漏 + 阿狸咪错峰补漏） |
| 并发硬保险 | ✅ 云端主链/selfhosted 共用 `concurrency: v8-cn-fetch-cloud`，不双写半截 JSON |
| 阿狸咪 30 分档 | ⚠️ **必须错峰到 `:30` 单点**（不要碰小九的 `:00/:20/:40`），否则双机 `:00` 重叠 |

## 二、实时证据：盘前已出现踩踏苗头（本次审核的起点）

盘前 08:16–08:46 这 30 分钟内，`v8_cn_fetch_cloud.yml` 实测产生 **6 个 run**（2 success + 2 cancelled + 1 in_progress + 1 pending），含 `08:40→08:45→08:46` 连续派发+取消节奏：

```
09-10 08:46 workflow_dispatch pending   run#37539
09-10 08:45 workflow_dispatch cancelled run#73473
09-10 08:40 workflow_dispatch in_progress run#12406
09-10 08:33 workflow_dispatch success   run#29424
09-10 08:18 workflow_dispatch cancelled run#58606
09-10 08:16 workflow_dispatch success   run#78716   ← 盘前守卫 1785888730897（08:15）
```

而盘中主调度 `22505803` 最早 09:40 才触发（当时 08:48，尚未跑过）。**说明盘前已有老哨兵在高频重复派发云端**——这正是主人最担心的「踩踏和风暴」。

## 三、已落地修复（盘前已完成）

| 动作 | 对象 | 原因 | 状态 |
|---|---|---|---|
| ⏸️ PAUSE | `e7b2e732` 每10分全链路自愈哨兵 | **风暴主源**：prompt 证实每10分 `dispatch v8_cn_fetch_cloud` + `dispatch v8_stock_quote_refresh` + `dispatch v8_build_deploy`，且「查询失败一律 fail-open 继续派发」→ 盘前密集 run 元凶 | ✅ 已停 |
| ✅ ACTIVE | `2d9121c8` 看门狗驱动（每15分） | watchdog.yml 是**纯补漏式**（`if stale:` 才派发 + 云端拥堵改 selfhosted），非主派发；恢复它=恢复云端侧独立兜底层，强化「兜底成功」 | ✅ 已恢复 |
| ✅ ACTIVE | `automation-1786961773708` 自愈监控闭环 | **误暂停已纠正**：prompt 证实它只读写 `raw_data/candidate.json`，**绝不 dispatch 主抓取链**，与云端踩踏无关；暂停会丢候选池/动量监控质量 | ✅ 已恢复 |

> 其余重叠调度（`195d8839`/`74077cbe`/`82038f74`/`1787108824799`/`1785898357370`/`2d9121c8`此前已 PAUSED）维持不变。

## 四、盘中架构（09:40–15:00）：单一主派 + 三重兜底

```
┌─ 主派发（唯一权威）── 22505803 小九机盘中调度器（14档·20分）
│     每档：查重→派发云端 intraday→sleep 600→查新鲜度→兜底(先 selfhosted 后 cloud)
│
├─ 兜底层① 22505803 自带：10分后查新鲜度失败→selfhosted 兜底
├─ 兜底层② 2d9121c8→watchdog.yml（每15分，stale才派，拥堵改 selfhosted）
└─ 兜底层③ 阿狸咪（开盘后每30分，只读检查+补漏，待她建；建议 :30 错峰）
```

**为何不踩踏**：所有派发源都带「查重（running 跳过）」；`22505803` 成功时数据新鲜，watchdog 不派发；阿狸咪 `:30` 错峰不与 `:00/:20/:40` 重叠。

## 五、并发硬保险（根防双写）

`v8_cn_fetch_cloud.yml` 与 `v8_cn_fetch_cloud_selfhosted.yml` **共用同一把锁**：

```yaml
concurrency:
  group: v8-cn-fetch-cloud
  cancel-in-progress: false   # 新派发排队而非互杀
```

→ 任一时刻只有一条 fetch 在写 main，从根上杜绝「你派云端我派自托管→api_push_raw 互踢→半截 JSON」。

## 六、兜底成功率与残余风险

| 兜底路径 | 依赖 | 可靠性 |
|---|---|---|
| selfhosted（小九机专用 runner） | 小九机在线 | ⭐⭐⭐ 专用机器不挤 GitHub 公共队列，**公共队列拥堵时仍稳**；盘中 9:40–15:00 小九机在线且算法链 18:10 才跑→空闲接单快 |
| cloud（ubuntu-latest） | 公共队列不拥堵 | ⭐⭐ 昨天 13 点事故根因=公共队列拥堵，需 selfhosted 兜底接力 |
| 三重冗余 | 任一源故障 | ⭐⭐⭐ 22505803 + watchdog + 阿狸咪，单点失效不影响整体 |

⚠️ **唯一兜底下风险**：小九机若盘中离线 → selfhosted 兜底失败，退 cloud（公共队列可能拥堵）。今日盘中在线，无此风险；若未来需盘中下线，须先确证阿狸咪机 self-hosted runner 可用（当前 alimi-cn PATH 受限，跑不了）。

## 七、给阿狸咪的错峰指令（她机建自动化时务必遵守）

**盘中兜底检查用 `BYMINUTE=30` 单点，不要 `0,30`**：

```
rrule: FREQ=HOURLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9,10,11,13,14,15;BYMINUTE=30
```

→ 小九在 `:00/:20/:40` 主派+兜底，阿狸咪在 `:30` 补漏，**彻底错峰**，双机永不在同一分钟触发 fetch。

## 八、待主人确认

1. 阿狸咪机 self-hosted runner（alimi-cn）PATH 未修前，盘中兜底仍可靠（小九机在线）；但**盘后算法链/LHB/STOCK_QUOTE 永远只能小九机跑**，小九机须在线到 ~21:30。
2. 若未来需小九机盘中下线，必须先修复 alimi-cn PATH 或确认其 runner 可接 selfhosted 兜底，否则盘中兜底退化。
