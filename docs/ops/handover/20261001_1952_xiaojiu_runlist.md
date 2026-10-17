# 双机交接运行清单 · 2026-10-01 19:52 CST（阿狸咪 → 小九）

> 出具人：阿狸咪的工程师（alimi-cn，家机）
> 出具时刻：2026-10-01 19:52（国庆休市夜，小九窗口=次日 07:45 起）
> 背景：长假收尾。本件为「该小九跑的归小九、结构性由阿狸咪拍板、其余科学分诊」的权威运行清单。
> 防覆盖纪律：本件与 HANDOFF.yaml / ledger 均经 Git Data API（基底=origin/main 实时、force:false、422 重放、内容级漂移守卫）推送；官方 `scripts/handoff_ledger_hash.py --check` 已复核一致。

---

## 一、小九待执行清单（按优先级，上线即跑，做完回填 HANDOFF status + done_evidence）

### A. 结构性落地（阿狸咪已拍板，见第二节决策，小九实现+交易日验证）

| # | 项 id | 优先级 | 小九动作（精确） | 验证 |
|---|---|---|---|---|
| A1 | `cachebot-build-race` | P0 | `v8_cache_buster_reconcile.yml`：cache-bot 推送前加「内容无变化则跳过」闸（仅当 ?v 真变才推），把 1.1–9.2min 推一次降到「有变更才推」，churn 降 ~90% | 连续 1 交易日：build job step13 failure 率由 25% 趋零 |
| A2 | `concurrency-block-bucket` | P1 | `v8_build_deploy.yml` 确认 `concurrency: group: build-deploy, cancel-in-progress: true`（释放卡住的僵尸 job 占桶） | 同桶不再出现 running+pending×2 三态并存 |
| A3 | `stale-index-landmine` | P0 | 全仓 grep `git checkout <ref> -- <path>` 与裸 `git commit`（无 pathspec），全部改走 Git Data API 安全路径或 `git restore --staged`+定点 commit | 本机 `git diff --cached --name-only | wc -l` 恒为 0；无新 `reset: moving to origin/main` |
| A4 | `cnfetch-api-quota-403-exhausted` | P1 | 查 `api_push_raw.py` 是否仍逐文件 `POST /git/blobs`；若是，改为「收集全部变更→建单 tree→单 commit」（注释显示已部分做，核实并补全） | 单轮 `POST /git/blobs` 调用数≈1；连续 3 交易日无 403 |
| A5 | `cn-fetch-queue-growth` | P1 | `v8_cn_fetch_cloud*.yml` 的 `queue: max` 收窄为按 category 分组 `concurrency + cancel-in-progress:true`，或 dispatcher 加「同 payload 已排队则跳过」 | 连续 3h pending 深度≤2 |
| A6 | `cn-run-start-env-dead-guards-0926` | P1 | `v8_cn_fetch_cloud.yml` L1027/L1178 `V8_RUN_START: ${{ github.run_started_at }}`（`run_started_at` 非合法上下文→恒空）改为：新增一步 `curl` 取 `actions/runs/${{github.run_id}}` 的 `run_started_at` 写入 env，或退化为 `github.event.head_commit.timestamp` | landcheck/relay 段出现真实基准分钟数（非「无法解析」） |
| A7 | `cn-softfail-annotation-dead-under-bash-e` | P2 | 三处 cn workflow 的 `cmd; _v8_rc=$?` 软失败模板，因 `shell: bash` 展开含 `-e` 致后三行永不执行 → 改为 `cmd || _v8_rc=$?` 或步首 `set +e` | 下一档 job 日志 `::error title=v8-softfail:` 行数≥1 |
| A8 | `lhb-push-only-arg-noop-out-dir-unpushed` | P1 | `api_push_raw.py` 加 `--only <tag>` 参数；`v8_lhb_fetch.yml` L155 `python api_push_raw.py --only lhb` 即生效 | 下一档日志不再出现「并发推送启动：5xxx 个文件」全量提示 |

### B. 交易日动态验证（代码已落/待真跑，小九观察回填）

| # | 项 id | 动作 | 验证 |
|---|---|---|---|
| B1 | `threecard-fundflow-anchor-0929` | 下轮 post_close 后看三卡 | W52_HIGH.js update_time 为收盘后；SECTOR_FUND_FLOW 含概念板块 |
| B2 | `intraday-guard-window-gap` | 09:30–09:32 dispatch 一次 | run conclusion≠skipped 且无「迟到档/窗外」 |
| B3 | `maharo-plan-b-three-editions` | 午间 12:30 / 盘后 15:10 各跑一版 | maharo_insights.js update_time 当日 12:3x/15:1x |
| B4 | `intraday-eastmoney-stall-4cards` | 观察≥1交易日 | 概念热力/ETF异动盘中前进；亚太概览不再全 0.00 |
| B5 | `intraday-snapshot-schedule-deregistered-again-0929` | 看 schedule 事件恢复 | 主力净额分时快照 09:3x 起连续 |
| B6 | `cnfetch-step22-raw-unpushed-alert-dead-0929` | 下轮 post_close step22 真跑 | `GET /commits?path=raw_data/sector_leaders.json` 有新增 |

### C. 本机状态项（小九机器资源，需她处理）

| # | 项 id | 动作 |
|---|---|---|
| C1 | `local-worktree-behind` | 先 `git stash`/提交本机 36 项 WIP，再 `git fetch`+对齐 origin/main（勿 `git reset --hard` 丢 WIP） |
| C2 | `maharo-daily-s4u` | `v8-maharo-daily` 计划任务改 LogonType=S4U + 加 WakeToRun（根治 LastTaskResult=1） |
| C3 | `factorlab-conflict-tree-pollution` | 确认改写后无 `checkout --theirs .` 与裸 `add .`；造冲突实测断言只 3 个目标文件被改 |
| C4 | `build13-step-timeout-minutes` | 低优先：step13 已隐式受 job 60min 兜底；可加 `timeout-minutes: 30`，非必须 |

---

## 二、结构性 8 项 · 阿狸咪专家拍板（决策已写入 HANDOFF 对应项 `alimi_decision_20261001`）

| 项 id | 决策（一句话） |
|---|---|
| `cachebot-build-race` | 加「内容无变则跳过」闸降频，而非放开并发；churn 根因=无意义高频推 |
| `concurrency-block-bucket` | 同桶 `cancel-in-progress:true` 释放僵尸占桶；build 幂等可重跑 |
| `handoff-concurrent-write` | 强制所有 HANDOFF 编辑走 Git Data API 基底预检路径（已落地为协议），`--check` 基陈旧硬拒；剩余风险=双机守协议 |
| `cnfetch-api-quota-403-exhausted` | 单树化批 blob（核实 api_push_raw 现状并补全），调用数 N→≈1 |
| `cn-fetch-queue-growth` | 按 category 分组并发+取消，或 dispatcher 同 payload 去重；非盲目放大队列 |
| `build-deploy-retry-loses-race-under-churn` | 保留 step13 现有 3 次重试（已含每次重取最新 main），不追加；属 churn 伴生，根因归 cache-bot/cnfetch 竞态 |
| `build-deploy-blocked-by-crosslayer-stale-guard-0929` | **保留**跨层一致性门（它是安全闸，曾正确拦陈旧上线）；其误报源于已修的竞态 bug，现仅对真实陈旧报警；不删门 |
| `stale-index-landmine` | 根除裸 `git commit`/`git checkout <ref> -- <path>`，统一 Git Data API 安全路径 |

---

## 三、其余共享/阿狸咪项 · 科学分诊（不动 HANDOFF 字段，仅记录判据）

- **已落码·待交易日验证（保持 pending-verify，诚实不谎报）**：`algo-step15-undefined-t`（t 已赋值）、`heartbeat-files-clobbered-by-cnfetch`（last_time 防倒退已上 522406dc82）、`stock-universe-etf-silent-drop-0926`（失败不覆盖已上）、`algo-artifact-date-naked-now-bypass-calendar`（calc_crds 改权威口径）、`trading-day-gate-predeps-fallback`（v8_date 口径）、`cn-runner-ps1-utf8-noBOM-gbk-parse-fail`（静态已判，可复现）、`api-push-stale-base-index-clobber`（静态 23/23 + 门禁 14/14）。
- **共享待落地（todo，需交易日/跑批窗口）**：`redcard-hostfail-rootfix-0924`、`cnfetch-single-source-stale`、`stockquote-noon-gap-relay-cancel`、`theme-value-concept-layer-zero`、`avgprice-source-switch-caliber-gap-0928`、`intraday-schedule-morning-absent`、`probe-intraday-missing-market-alerts`、`all-generic-redline-false-positive`、`maharo-plan-b-three-editions(shared 部分)`、`postclose-reliability-trio`、`ima-snapshot-72h-expiry-trap`、`algo-t1-segment-d-gate-false-red-0926`、`cn-singleflight-schedule-trigger-offset`、`stockquote-cachebuster-noop`、`triple-history-accumulator-caliber`。
- **低优先/有风险（跳过，非无用但今晚不碰）**：`lhb-history-size-slim`（P2 缩表优化）、`quote-third-source`（P2 新集成有风险）、`build13-step-timeout-minutes`（已兜底）。

---

## 四、本轮回合已闭环项（阿狸咪落，已推 main，待小九下轮知悉）

- `handoff-yaml-stale-base-item-drop` → **done**（7 个被删 id 全在；item 数 132；提交 8fcb5e5a0f）
- `handoff-ledger-hash-desync` → **done**（官方 --check 132/132、失配 0）
- `ima-connector-unbound-enterprise-switch` → **done（观测结项）**：实测 `raw_data/ima_strong_stock_full.json` fetched_at=2026-09-30 21:20:43（channel=member-full-text-snapshot），非「须主人重绑」；原假设不成立，按观测结项。

---

## 五、审计与防覆盖自证

- 推送路径：Git Data API，基底取 origin/main 实时内容（非本机陈旧副本），仅替换 `HANDOFF.yaml`+`HANDOFF.ledger.json`+本交接件三路径，`force:false` 快进、422 重放、内容级漂移守卫。
- 推后：`git fetch` 回读逐字节一致；官方 `scripts/handoff_ledger_hash.py --check` 复核台账哈希一致。
- 未触碰：今晚算法链未提交产物（FINAL_RECOMMEND_DATA.js / _peer_monitor_state.json 等）、已落码五项 .py、所有 data/*.js。
