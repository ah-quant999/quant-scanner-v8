# 小九读阿狸咪周末交接核对

> 生成时间：2026-08-10 08:17 CST  
> 本地 HEAD：`7fdd0cba`（与 origin/main 已同步）  
> 说明：本文件补全阿狸咪周末交接文档未覆盖的 08-10 清晨增量，用户已确认该增量是早上让阿狸咪改的、来不及交接。

---

## ✅ 已读交接

| 文件 | 内容重点 |
|---|---|
| `HANDOVER_阿狸咪_2026-08-09.md` | 逻辑详解页审计，与改版前端一一对应补齐 |
| `HANDOVER_阿狸咪_2026-08-09_晚间.md` | 周末核心修复清单（A 数据倒退恢复 / B 观澜台·maharo 双源打通 / C 前端体验 / D 候选池去重命名） |
| `HANDOVER_小九_2026-08-08.md` | 含阿狸咪 08-08 上午 4 个提交（UI 补强 + v6 硬依赖清零） |
| `.workbuddy/memory/2026-08-10.md` | 看门狗 128–132 轮自动交接 |

---

## ⚠️ 08-10 清晨 07:00–08:00 新增提交（交接文档未覆盖）

**用户已确认：是早上让阿狸咪改的，交接文档来不及更新。**

| commit | 说明 |
|---|---|
| `33b8b8a7` / `f51867d6` / `42e1cdc7` | 新增 `maharo_refresh.yml`：云端代发/代验证验证码机制（本机 DNS 不通 `data.maharo.cn`，改云端发码） |
| `308c1858` | **fix(health+candidate)**：周一早盘最终推荐误告警 + 候选池双源目录/文件名对齐 |
| `ee5cedb2` | 移除 maharo 临时 DEBUG 打印 |

本地已通过 `git pull --rebase` 同步到 `7fdd0cba`，工作区仅 6 个 `raw_data/*.json` 有本地改动（按红线原样保留）。

---

## 🔴 小九白天红线

1. **push 前必须 `git pull --rebase` 到最新 main**（基准 `7fdd0cba`），禁止基于旧副本改 `index.html`。
2. **`index.html` 属阿狸咪高频在改文件**：小九不 checkout/restore/stash drop，不纳入自己提交；发现 modified 原样保留。
3. **maharo 数据为空**：cookie 过期，需用户邮箱 `ljcat999@gmail.com` 收新验证码配合刷新；禁止代码绕过，等 Secret 更新。
4. **防数据倒退复发**：`api_push_raw.py` 防倒退守卫（`05e39a98`）若被并发 job 绕开会再倒退；排查时先查守卫再查竞态。
5. **pre-push 钩子已启用**：push main 前自动 fetch+rebase，与本地 stash/ff 流程并存，勿手工硬推。
6. **`data/BLOAT_CHECK.js` 是 v8_bloat_check.py 产物**，非小九文件：看到 modified 保持原样，不提交、不删除。

---

## 📌 当前待跟进（需用户拍板/授权）

| 优先级 | 事项 | 阻塞/所需动作 |
|---|---|---|
| P0 | 前端审计整改：删 `IPO_FALLBACK` 硬编码 | 用户授权"修"后执行 |
| P1 | 运维子页改读 `window.BACKTEST_COMPREHENSIVE`/`window.COCKPIT_BACKTEST`（.js 注入），弃用 fetch json | 用户授权后执行 |
| P1 | 6 个未提交变更待推送 main：`calendar.html` / `calendar_seed.json` / `v8_cn_fetch.yml` / `cloud_weekly_cleanup.yml` / `v6_memo.html` / `sync_v6_to_v8.py` | 用户确认"上线"后 commit+push |
| P2 | 清理 3 处死 fetch 定义 + 接入/移除 8 个孤儿注入 | 可延后 |
| — | maharo 验证码刷新 | 用户查邮箱 |
| — | 平均股价 880003 新功能 | 用户明确优先级 |
| — | 板块周期卡片：先方案 B（改名"板块资金趋势"+精简列），后方案 A（合并单卡） | 用户明确先做哪步 |
| — | 选股策略逻辑审计 + GitHub Pages 逻辑说明页 | 用户安排时间 |
