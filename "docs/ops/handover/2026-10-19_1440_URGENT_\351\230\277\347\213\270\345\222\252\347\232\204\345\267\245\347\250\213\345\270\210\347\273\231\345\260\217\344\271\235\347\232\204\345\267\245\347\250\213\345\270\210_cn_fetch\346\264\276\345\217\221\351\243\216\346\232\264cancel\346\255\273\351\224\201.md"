# 2026-10-19 14:40 [URGENT] 阿狸咪的工程师：cn_fetch 自愈派发风暴 + cancel-in-progress 自残死锁

## 一句话结论
- 今日 09:00 CST 起，`v8_cn_fetch_cloud`（wf 327687211）被 **workflow_dispatch 每 5~60 秒一枚连片派发**（基线 ≈1 枚/小时），
  且新派发把**在跑轮 cancel 掉**（cancel-in-progress 自残）⇒ 跑不完⇒派发方看到的"陈旧"永不修复⇒继续派发，
  **结构性死锁**。截至 14:31 CST 仍在注入。最后一次 success = **13:03 CST**（run 39189871402）。
- 同风格风暴同时打在 `v8_stock_quote_refresh_cloud`（wf 352790648，每 2~6 秒一枚、全部 cancelled）。
- 派发 actor = **ah-quant999（workflow_dispatch 事件）**；两机 token 同账号，**本件无法从 API 侧归因到具体机器**，需两机各自自查。

## 实测证据（全部 GitHub API 实拉，CST+8）
1. 派发量按小时分布（runs created_at，event=workflow_dispatch）：
   - 10-18 全天：每小时 1 枚（正常基线）。
   - 10-19：09 时段 22 枚 → 10 时段 45 枚 → 11 时段 24 枚 → 12 时段 10 枚 → 13 时段 2 枚（短暂回落）→ **14 时段 46+ 枚且每 5 秒一枚仍在到**。
2. 自残实证：run 39208501716（14:11:39 起 in_progress）于 **14:28:17 被 cancel**；run 39208636974 同款。
   ⇒ 在跑轮活不到出数，队列 pending 一度 38+。
3. 数据面现状（14:25 实测 raw_data blobs）：EXPERIMENT=10-19 08:44:09（5.8h，尚可）、SECTOR_LEADERS=10-17 02:15
   （data_date 10-16，T+1 口径今晚 18:30 前合法）、ALGO_HEARTBEAT=10-18 02:59:29（判定点=今晚 18:30，本件不改判）。
   **若死锁不解，EXPERIMENT 将在今晚阈值后转真红卡。**
4. health_patrol（wf 333261254）今日每 1~4 分钟一轮但最新轮 health-patrol step=skipped ⇒ **不是派发源**；
   cn_fetch_watchdog 今日仅 2 轮 success ⇒ 不是派发源。派发源在**某台机器的常驻进程/自动化**里
   （嫌疑：某 stale 检查 → 自愈表无冷却重派；触发阈值疑似 EXPERIMENT/STOCK_QUOTE 某口径过期）。

## 请收件方（两机都要做，先小九白天档）
1. **先止血**：找到本机对 `v8_cn_fetch_cloud` / `v8_stock_quote_refresh_cloud` 的 dispatch 循环并停掉
   （查 WorkBuddy automation_runtime_state + 自愈/监听脚本日志；关键词 dispatch 327687211 / workflow_dispatch）。
2. 止血后**手动补一枚** cn_fetch 把积压数据追平（防 18:30 红卡）。
3. 根治：自愈派发必须带**冷却 + 同 group 未完成 run 存在即跳过**（本巡检铁律同款）；连续派发上限 + 告警。
4. 复核 STOCK_QUOTE 刷新链：`v8_stock_quote_refresh`（336548691）成功推提交每 5~25 分钟一枚，
   push 又再触发下游——确认是否存在 push→dispatch 反馈环。

## 防踩踏约定
- 阿狸咪本轮**零派发、零重试**；接本件后若你也在派发前先查同 workflow 未完成 run（铁律）。
- HANDOFF.yaml 已同步新增 item `cnfetch-dispatch-storm-cancel-deadlock-1019`（status=todo，owner=小九的工程师），
  同提交已按并发写协议 D 重放基底 blob 409be557e7 并刷新 ledger。

—— 阿狸咪的工程师（alimi-cn），2026-10-19 14:40 CST
