# 紧急交接 · 小九 → 阿狸咪（2026-09-10 10:16）

> 背景：主人发现「机构研究·AI解析建议」卡又被覆盖回浅版（732 字）。已定位根因并做一劳永逸修复，按主人令**盘中不直推、休市窗口（11:35 / 15:05）由发布闸门自动 flush 上线**。本文供阿狸咪接手后核对与值守。

## 一、本次被覆盖的根因（已查实，非 CDN 缓存）

- `maharo_macro.js` 的 `insights` 段由**两台机器各自本地** `C:/Users/Administrator/.workbuddy/maharo_insights.json` 注入。
- 小九机 09:02 推了深版（2208 字，`c5689d7f9`）；**云端 lemoncat-cn 机的同名文件是旧浅版**，其 `maharo_daily_pull.py` 约 08:50 本地重生成 + 09:20 的 `v8 cn fetch` 把浅版 commit 进 main（`0572ae5a5`），覆盖深版。
- 即「双机各自本地 insights 文件打架，谁后 commit 谁赢」。改本机脚本没用（改不到云端那份）。

## 二、一劳永逸修复（已落地本地，待 11:35 休市 flush）

把 hand-authored 的 insights **从 `maharo_macro.js` 拆出来**，独立成 `data/maharo_insights.js`（`window.MAHORO_INSIGHTS`），前端改读该独立文件。
→ 云端每日重生成 `maharo_macro.js` 时，无论它带什么 insights，前端都**不再读取**，等于永不被覆盖。

已改 3 个文件（staging 中，11:35 上线）：
1. `data/maharo_insights.js`（新增，深版单一真相源：daily 2208 / weekly 292 / monthly 230 字）
2. `index.html`：① 新增 `<script src="data/maharo_insights.js?v=...">`；② 渲染改 `var ins = window.MAHORO_INSIGHTS || d.insights || {}`（优先独立文件）
3. `scripts/fetch_ai_insights_compare.py`：优先读 `data/maharo_insights.js`，fallback 到 `maharo_macro.js`

附带：小九机 `maharo_daily_pull.py` 改 `fetch_committed_insights()`，**优先读仓库已提交的深版 insights**（GitHub API 拉 `data/maharo_insights.json`），双机单一真相源。
⚠️ 云端 lemoncat-cn 机的 `maharo_daily_pull.py` 仍是旧代码（读本地浅版）——**无影响**，因为前端已不读 `maharo_macro.js` 的 insights。若阿狸咪想彻底一致，可把小九这份脚本同步过去，但非必须。

## 三、发布闸门纪律（主人新令，务必遵守）

- 任何人工修订 `data/*.js` / 前端 / 脚本，**盘中（09:00–11:30、13:00–15:00）一律不直推**。
- 由 `C:/Users/Administrator/.workbuddy/v8_publish_gate.py` 统一：`build → verify → publish`（盘中自动 staging）→ `flush`（11:35 / 15:05 自动化调用，二次核对后上线）。
- 本次 3 个文件已在 `C:/Users/Administrator/.workbuddy/v8_pending/` 暂存，11:35 自动发布。
- **严禁**再直接 `push_to_main` 绕过闸门（会丢失二次核对，重蹈缩水覆辙）。

## 四、7 大风险（来自阿狸咪 09-10 交接单，需主人拍板的已标 ⚠️）

| # | 风险 | 状态 | 处理方 |
|---|---|---|---|
| C1 | `v8_cn_fetch_intraday_lemoncat.yml` 不在 main | ⚠️需主人拍板+workflow token | 主人/阿狸咪 |
| C2 | 小九空窗 15:00–17:20 漏算 **16:40 A 档** | ⚠️需主人拍板改空窗 | 主人 |
| C3 | `v8_algo_cloud.yml` 在 lemoncat offline 无 fallback | ⚠️需主人拍板加 ubuntu-latest | 主人 |
| C4 | 夜班监控读 HANDOVER 路径错（历史 clone 路径） | ✅小九可自治修 | 小九 |
| C5 | 本地 HEAD 与远端分裂（远端领先 7 commit） | ✅小九可自治 rebase | 小九 |
| C6 | `6d16d809` 自动推 main 条件写死日期永不触发 | ⚠️需主人拍板改动态条件 | 主人 |
| C7 | `53726469` 盘后最终闸 21:30 强制补跑 PAUSED | ⚠️需主人拍板评估 | 主人 |

## 五、小九空窗覆盖（重要）

- 主人确认：**每日 15:15–17:20 小九机不在线**。
- 该空窗覆盖 **16:40 A 档算法派发** + 17:30 前后龙虎榜刷新。
- 处置：C2 拍板后空窗拆为「15:00–16:20 可下线 + **16:40–17:25 必须在线**」；或由阿狸咪/云端 fallback 接管 16:40 A 档。
- 今晚 21:00 E 批（因子实验室 / BACKTEST_COMPREHENSIVE / CRDS_BACKTEST）三红灯须盯转绿，小九机若已离线由阿狸咪接手。

## 六、当前线上状态（10:16）

- `origin/main` `maharo_macro.js`：浅版 732 字（被云端 09:20 覆盖），`updated_at=2026-09-10 08:43`。
- 11:35 flush 后：前端改读 `MAHORO_INSIGHTS`（深版 2208 字），显示恢复正常；`maharo_macro.js` 浅版 insights 不再被前端使用。
- 发布闸门：`v8发布闸门·午间休市flush`（11:35）、`v8发布闸门·盘后flush`（15:05）两个自动化已建并 ACTIVE。

> 阿狸咪接手后：① 确认 11:35 后线上「机构研究·AI解析建议」为深版（Ctrl+F5）；② 切勿在盘中手动直推 data/*.js；③ C1/C2/C3/C6/C7 等主人拍板。
