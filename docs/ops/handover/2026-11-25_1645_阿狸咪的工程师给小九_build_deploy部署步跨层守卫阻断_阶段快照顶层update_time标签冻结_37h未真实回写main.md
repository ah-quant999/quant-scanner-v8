# 交接件：build_deploy 部署步被跨层守卫阻断（顶层 update_time 标签冻结 → 结构性永久误判）

- 发件：阿狸咪的工程师（家机 alimi-cn）
- 收件：小九（lemoncat-cn）
- 时刻：2026-11-25 16:45 CST（主人外出期自主处置）
- HANDOFF item：`crosslayer-deploy-block-1125`（todo / P0 / owner=小九的工程师）
- 前案：`build-audit-404-backtest-cards-1124`（[4/8]+[6/8] 门禁 11-25 上午已由你方收敛转绿，本件是**部署层新阻断**，另立 item）

## 一句话结论

Pre-deploy audit 门禁已转绿，但「📤 部署到 main」步被跨层一致性守卫拦死：**真凶是生成器不刷新 raw 顶层 `update_time` 标签**（结构性、不会自愈），叠加 STOCK_LIST 周度产物误杀族、CONCEPT_ETF_MAP raw 缺失、PULLBACK_TRACK raw 无日期 4 项；自 11-24 03:45 CST 起 build_deploy「构建 data/*.js → 回写 main」已 **37h+ 未真实完成**。

## 证据（全部远端 API 实测，非本机副本）

1. **门禁已转绿（你的修复生效，先确认无争议）**
   - 11-25 04:32/04:33Z 双登记提交 0741094044（运维表行）+ 57b1d7712c（MUST_HAVE_CRON 登记 v8_backtest_weekly）。
   - 实证：run 45548180637（head 39f6698273 ≥ 57b1d7712c）build job 真跑 [1/8]~[15/15] 全绿。
   - 11-25 10:09 CST 你提交 d9a70275b5 落仓两份真实产物 data/CASHFLOW_QUALITY_BACKTEST.js（8861B）+ SHAREHOLDER_INCREASE_BACKTEST.js（9735B），非占位壳。
2. **部署步阻断仍在（本轮实证）**
   - 最新 build job：run **45570489843**（head edf6cdbd35，15:44 CST 起跑，16:25 CST 死于「📤 部署到 main」步）。13:11 CST 前案 run 45548180637 同步死点。
   - job logs API 双 token 均 403 无法直读日志，以下根因逐条 blob 实证：
3. **真错位①（结构性、不会自愈）SECTOR_PHASE_HISTORY**
   - `raw_data/sector_phase_history.json` 顶层 `"update_time": "2026-11-23 01:22"`、`republish_time: "2026-11-23 01:22:26"` **冻结不动**（11-25 16:35 CST blob 实证，size 204,562B）；
   - 但该文件 16:00 CST 仍在正常推送（commit d5b3cde26a），snaps 已含 2026-11-24 快照（snap_count=63，snap 级 update_time 已到 11-25 15:57）。
   - 根因：`v8/gen_sector_phase_history.py` 落盘时不刷新顶层 update_time/republish_time 标签 ⇒ 守卫按标签判「真错位」**永久阻断**。这是生成器 bug，不是数据事故，禁补数。
4. **真错位②（周度产物误杀族）STOCK_LIST**
   - raw=raw_data/stock_names.json ut=2026-11-24 01:44:23 vs data=2026-11-25 08:32:45。属 HANDOFF 在册「周度产物 ut 取上游 mtime 被 24h 红线误杀」同族（all-generic-redline-false-positive 族）。
5. **缺失 raw：CONCEPT_ETF_MAP**（raw_data/ 目录 243 文件中无任何 ETF_MAP 文件，11-25 16:35 实测）。
6. **无法校验：PULLBACK_TRACK raw 无日期字段**（raw_data/pullback_track.json blob 实测，头部仅 version/caliber/horizons）。
7. **连带项已自愈，无需单独修**：BACKTEST_EXPECTANCY data/*.js 层已由 algo 直推链 11-25 09:02 CST 刷新（commit b313c01252），raw meta 也新鲜（generated=2026-11-25 08:04）。部署链恢复后守卫该项自动消除。
8. **影响面**：Pages 发布链正常（run 45577685895@df45115b37 16:36 CST Deploy to GitHub Pages success，主站 200/1.55MB 尾部完整）；cn_fetch/algo 直推链产物全鲜活（experiment 16:00 / sector_leaders 09:02 / algo 08:34 / stock_names 9694）。**受影响的只有 build_deploy 内「重新构建 data/*.js → 回写 main」这一段**，用户端暂无感。

## 修复方向建议（供你拍板，我方未代修）

1. **治本**：`v8/gen_sector_phase_history.py` 每次落盘同步刷新顶层 `update_time` / `republish_time`（与 snap 内容一致）。
2. **守卫降噪**：跨层守卫对周度产物族（STOCK_LIST 等）按 snaps/内容日期校验而非顶层标签；对 PULLBACK_TRACK 无日期 raw 给出明确 skip 而非「无法校验」挂红。
3. CONCEPT_ETF_MAP：确认该 raw 是否已被退役/改名——若已退役，守卫 MUST_HAVE 名单同步摘除；若仍需要，补 fetcher。
4. BACKTEST_EXPECTANCY：无需单独修（见证据 7）。

## 边界（我方未做的事）

- 未改任何业务代码 / 生成器 / 守卫（防踩踏，你方正分钟级活跃迭代）。
- 未派发任何 workflow（业务层禁重试）。
- 未补产物、未造占位壳。
- 同批 HANDOFF 变更：`jinzuan-track-cron-audit-block-1109` 与 `build-audit-404-backtest-cards-1124` 转 `pending-verify`（verified_at=2026-11-25，证据=run 45548180637 实证 15 项全绿 + d9a70275b5 产物落仓），新增 `crosslayer-deploy-block-1125`。
