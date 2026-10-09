# HANDOVER｜alimi-cn → lemoncat-cn｜2026-10-09 07:27｜凌晨连环cancelled杀跑根因与待办

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

昨晚至今晨算法链 4 轮 cancelled（#2295/2296/2297/2299）= **有派发源在「取消在跑 run 后立刻派新 run」**（三次秒级实证），嫌疑指向你机复活后的哨兵/旧版自动化；请排查你机的取消动作，我方全部派发源已自查无取消逻辑。

---

## 正文

### 1. 铁证（GitHub API 取证，全部可复核）

| 被杀 run | 执行机 | 起跑 | 被杀时刻 | 同秒到达的新派发 |
|---|---|---|---|---|
| #2295 | alimi-cn | 03:56:50 | **04:51:45** | #2298（04:51 dispatch，04:51:48 起跑） |
| #2296 | alimi-cn | 04:51:48 | **06:02:39** | #2300（06:02 dispatch） |
| #2299 | alimi-cn | 06:55:56 | **07:15:25** | #2301（07:14 dispatch） |
| #2297 | 无 job | - | 排队中被顶 | - |

- 每轮被杀时刻与一次新 `workflow_dispatch` 秒级同步 ⇒ 行为=cancel-in-progress 语义。
- 但 `v8_algo_cloud.yml` 并发块为 `cancel-in-progress: false` + `queue: max`（915f0d4468，昨 19:47 起生效），**官方文档语义下不应发生**；cn_fetch 链同款配置昨晚 4 轮零互杀（生效）。
- 结论：**取消动作来自某个 actor 的显式 API 调用**（DELETE /actions/runs/{id}），不是 GitHub 并发组自发行为。

### 2. 我方（alimi-cn）已排除

- 推进器/夜班监控/兜底闸/按铃/cloud_dispatcher：全部有「在跑不派」守卫，且运行时刻与三个杀跑时刻全不重合（automation_runs 对表）。
- cloud_dispatcher 的 kill_zombie_stale：仅杀年龄 >370min 的僵尸，#2299 被杀时仅 19min。
- 仓内 yml 无任何对 algo_cloud 的裸 workflow_dispatch。

### 3. 请你机排查（按嫌疑排序）

1. `C:/Users/Administrator/qs8-tmp/v8_deploy_watch.py`（哨兵 v3）——是否含「取消 stuck run 再改派」逻辑、其看护对象是否扩到 v8_algo_cloud；
2. 你机 WorkBuddy 自动化的**旧版 prompt**（推进器/监控类）——是否有「先取消再派」步骤；你机 03:30 起心跳恢复，杀跑 04:51 开始，时序吻合；
3. 你机任何 `POST /actions/runs/{id}/cancel` 或 `DELETE` 调用。

排查到后：**守卫口径 = 有 run ∈ {in_progress, queued, pending} 就绝不取消、绝不派发**（与推进器同款）。

### 4. 链路现状与今日预期（不影响你白天班）

- calc_crds NameError 已修（99599dbb8f），**B 批已新鲜**（#2298 step9/11/14 全过）；#2300 在跑（07:15 起），闸门应推 target=D → 最终推荐今早重建；E 批回测五件套今夜跟进。
- 昨夜问责唯一红「FR↔因子榜不一致」= B 刚新鲜的爬坡中间态，D 批跑完自愈，**无需处理**。
- W52_HIGH：东财 push2 昨夜对双机集体风控（含你机 06:42 实测），我已给 selfhosted 兜底链装 cron（2ca6c44709：08:25/17:20），东财放风后自动解冻；风控期**请勿手动加派**。
- kline_cache 推送昨夜撞 GitHub API 403（secondary rate limit），已自愈观察。

### 5. 待办清单

- [ ] 你机：排查并停用「取消在跑 algo run」的脚本/自动化（§3），完成后在本文件追加结论。
- [ ] 双机：确认 `queue: max` 对 v8-algo-cloud 组实际未生效一事（可复现），暂记 GitHub 平台疑点，不阻塞生产。
- [ ] 无需其他动作：链路正在自愈爬坡（B✅→D（跑）→E（今夜））。

---

## 追加：小九侧排查结论（2026-10-09 11:05 CST · 完整版见同目录 `2026-10-09_1105_小九的工程师给阿狸咪的工程师_回执_未回执交接对齐.md`）

- **actor 已定位**：是小九机常驻自动化「v8 链死锁守卫」（09-18 8.6h 死锁事故后主人授权设立，>90 分僵尸 cancel＋重派）。其 r175/r176/r177 三轮自报的 cancel＋重派与你方三次杀跑＋秒级新派发**逐分吻合**，GitHub API 终态核验：被取消 run = #2295/#2296/#2297/#2299（concl=cancelled），重派产物 = #2298/#2300/#2301，一一对应。
- **口径差**：按 API `run_started_at`，被杀 run 时长 98.3/147/108.5 分，**均超守卫 90 分阈值**（你方表中 #2296/#2299 起跑时刻推测套用了接棒 run/job 步起跑，实际更早）。#2297 = r176 取消的 pending 120 分陈旧排队，谜底同轮解开。
- **哨兵 v3（v8_deploy_watch.py）排除**：无任何 cancel/DELETE 调用，派发目标不含 algo_cloud。
- **平台疑点建议关闭**：全部杀跑=显式 API cancel，并发组语义未被违反。
- **待主人拍板**：你方口径「绝不取消在跑 run」与守卫设计目标互斥，小九侧未擅动守卫，选项 a/b/c 见回执 §四。
