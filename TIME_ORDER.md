# 九宝量化 v8.0 — 定时任务时序锁定表

**最后更新**: 2026-08-02（4 孤儿原生化进 algo_run，sync_legacy 退役）
**维护人**: 阿狸咪 + 主人
**用途**: 防止日后调整 cron 时序时，无意颠倒依赖关系导致数据被覆盖。
**变更纪律**: 任何 cron / workflow 的时点变更，必须先查本表 → 评估对下游影响 → 经主人拍板。

---

## 一、时序图（北京时间 / 全部在工作日 MO-FR 跑）

```
            盘前                          盘中                               盘后
  ──────────────────────────────────────────────────────────────────────────────────────►
  06:30     08:25       10:30  11:30  13:05  14:00  15:05      18:30           21:00
    │         │           │      │      │      │      │           │              │
    │         │           ▼      ▼      ▼      ▼      ▼           ▼              ▼
    │         │        v8_cn_fetch (盘中 5 抓)                  v8_algo_run     v8_algo
    │         ▼                                                  (算法链)       (体检)
    │      v8_cn_fetch                                          ─────────     ────────
    │      (盘前 1 抓)                                          │ 18:30 │     │ 21:00 │
    │                                                           │  1h  │     │       │
  v8_self_heal                                                  │      │     │       │
  (周末 14:00)                                                  ▼      ▼     ▼       ▼
                                                          LHB_HISTORY  push  体检
                                                          累积完成    raw   写入
                                                                     data  freshness
                                                                     到main _status.json
                                                          (含 NT_DATA / SUSPENSION_ALERT /
                                                           MARKET_ALERTS / SECTOR_FUND_FLOW_TREND
                                                           4 孤儿，已原生化进本链)

  云端其它工作流（ubuntu runner，不依赖中国网络）：
  - v8_algo.yml (09:00 / 17:00)：数据体检，写 freshness_status.json
  - v8_safety_net (工作日每 30 分钟)：cn 断线时云端兜底
  - cloud_weekly_cleanup (周六 21:00)：orphan 清理 + 新鲜度体检
  - v8_cleanup (周日 23:00)：缓存/日志修剪
  - v8_sync_legacy.yml：**已退役**（no-op，仅 workflow_dispatch 应急回退；4 孤儿已原生化）
```

---

## 二、依赖关系矩阵（必须严格遵守）

| 上游 workflow | 下游 workflow | 间隔 | 为什么不能颠倒 | 颠倒后果 |
|---|---|---|---|---|
| ~~**v8_sync_legacy** (19:30)~~ | **已退役** | — | 4 个孤儿模块（NT_DATA / SUSPENSION_ALERT / MARKET_ALERTS / SECTOR_FUND_FLOW_TREND）已于 2026-08-02 原生化进 `v8_algo_run` 算法链（`run_algorithms.py` ORDER 末尾 4 个 `fetch_orphan_*.py`），不再需要独立同步 workflow | 无 |
| **v8_algo_run** (18:30) | **v8_build_deploy** (push 触发) | 0 | algo_run 推 raw_data 触发云端构建部署 | 自动 chain，无需人为调整 |
| **v8_cn_fetch** (08:25 盘前) | **v8_algo_run** (18:30) | ~10h | 18:30 跑算法时引用 cn_fetch 当天抓的盘中/盘后数据 | 早盘数据缺口（已可容忍） |
| **v8_algo_run** (18:30) | **v8_algo.yml** (09:00 次日) | 14h | 次日体检看 18:30 算法链产出的 raw_data 是否新鲜 | 无 |
| **v8_cn_fetch** (盘中 5 抓) | **v8_build_deploy** (push 触发) | 0 | cn_fetch 推 raw_data 触发云端构建 | 自动 chain |

---

## 三、各时段 cron 表（详细）

### 盘前
- **08:25 CST** `v8_cn_fetch.yml` — 盘前抓取（akshare/东财）：V8_CAL / IPO_DATA / MARGIN_DATA / CFFEX_HOLDINGS / MACRO_DATA / CRISIS_DATA / NORTH_FUND / ANALYST_RATINGS / SUSPENSION_ALERT / MARKET_ALERTS / W52_HIGH / HERDING_DATA
- **08:35 CST** `v8_build_deploy.yml` — 跟随 push 触发云端构建（盘前数据上线）

### 盘中
- **10:30 / 11:30 / 13:05 / 14:00 / 15:05 CST** `v8_cn_fetch.yml` — 盘中 5 抓：INDEX_QUOTES / ETF_PULSE / ETF_INTRADAY_HEAT / ETF_DAILY_MONITOR / SECTOR_FUND_FLOW / CAPITAL_FLOW_DATA / CONCEPT_RANKING / LIMIT_UP_HEATMAP / CANDIDATE_QUOTES / SH_SZ_HISTORY
- **15:30 CST** `v8_cn_fetch.yml` — 收盘数据抓取（EXPERIMENT）

### 盘后（关键时序段，18:30 不可动）
- **18:30 CST** `v8_algo_run.yml` — 盘后算法链：fetch_* + calc_* + gen_* + backtest_*，写 raw_data + push main
- ~~**19:30 CST** `v8_sync_legacy.yml`~~ — **已退役**（no-op）。4 孤儿已原生化进 `v8_algo_run` 算法链（见 `run_algorithms.py` ORDER 末尾 4 个 `fetch_orphan_*.py`），不再需要独立同步 workflow；如日后 v8 原生 fetcher 集体故障，可 `workflow_dispatch` 手动触发旧同步应急。
- **21:00 CST（工作日）** `v8_algo.yml` — 数据体检，写 freshness_status.json

### 周维护
- **周六 14:00** `v8_self_heal.yml` — 云端自愈器（周末检测陈旧模块并补跑）
- **周六 21:00** `cloud_weekly_cleanup.yml` — orphan 清理 + 新鲜度体检
- **周日 23:00** `v8_cleanup.yml` — 缓存/日志修剪

---

## 四、历史时序事故记录（教训）

### 2026-08-01 审计发现：`v8_algo_run` 误设 17:00
- **问题**：原 cron `0 9 * * 1-5`（17:00 CST），与交易所龙虎榜 17 点后发布冲突
- **后果**：17:00 跑 fetch_lhb 时龙虎榜未出，返回空 → LHB_DATA 静默保留昨日 → 三重共识/机游共振用隔夜数据
- **修正**：改为 `30 10 * * 1-5`（18:30 CST），对齐 v6 close_p2 时点
- **教训**：盘后算法时点必须**晚于龙虎榜发布**（交易所 18:00 后），否则全链用昨日数据

### 2026-08-01 审计发现：`v8_build_deploy` 17:00 schedule 与 algo_run 竞态
- **问题**：两个 workflow 都在 17:00 跑，且都执行 `update_v8.py`，会并发 push main 触发 rebase
- **后果**：白烧 Actions 分钟数；偶发 rebase 冲突
- **修正**：删除 `v8_build_deploy.yml` 的 17:00 schedule，改为**仅 push 触发**（algo_run push 时自动 chain）
- **教训**：两个 workflow 执行同一逻辑必有竞态，**合并为 push 触发**是去重最简方法

### 2026-08-02 决策升级：4 孤儿原生化，`v8_sync_legacy` 退役
- **背景**：`v8_sync_legacy` 仅补 4 个孤儿模块（NT_DATA / SUSPENSION_ALERT / MARKET_ALERTS / SECTOR_FUND_FLOW_TREND），依赖 v6 仓 `data/` 数据；主人要求「逐渐都原生化，不再依赖 v6，v6 怕不知道什么时候就运行不了就完蛋了」
- **决策**：4 孤儿改用 v8 原生 fetcher（`algorithms/fetch_orphan_*.py`）直接写 raw_data，接入 `v8_algo_run` 的 `run_algorithms.py` ORDER（18:30 与算法链同跑）；`v8_sync_legacy.yml` 改为 no-op（仅 `workflow_dispatch` 应急回退）；`sync_v6_to_v8.py` 移除 4 个映射 + 删除 `_enrich_sector_fund_flow_trend()` 富集函数（逻辑已内移至原生 fetcher）
- **收益**：彻底脱离 v6 依赖；时序依赖从「跨 workflow 双重保险」简化为「单链内部顺序」，不再有颠倒风险
- **教训**：能用原生 fetcher 替代的同步桥，应尽早原生化，减少跨仓脆弱依赖

---

## 五、变更检查清单（每次改 cron 前必走）

- [ ] 查本表第二节「依赖关系矩阵」
- [ ] 评估「上游改了 → 下游是否需要同步改」
- [ ] 在 PR/commit message 写明时序变更原因
- [ ] 测试验证：手动 `workflow_dispatch` 跑上游 → 等完成 → 跑下游
- [ ] 通知主人拍板（cron 是高风险操作）

---

**核对**: 2026-08-02 ✅
**下次审查**: 每周日 `v8_cleanup.yml` 跑完后