# 2026-09-01 策略回顾卡(strpsCard)空白根因修复与三件套

## 一、根因（数据实测，非猜测）
- 用户口语"策略回顾卡" = `strpsCard`（index.html line 2395，「个股相对强度 · RPS + RS + 年线」），位于「🔒 选股策略 → 相对强度」子页。
- 渲染函数 `renderRpsScreen`（line 12382）读 `window.STOCK_RPS_DATA`（line 12383）。
- `data/STOCK_RPS.js` 是 **defer** 脚本（line 492）；init 末尾的普通 `<script>`（line 12821）在解析阶段执行 `tryRun('renderRpsScreen')` 时 `STOCK_RPS_DATA` **尚未注入**（defer 在 DOMContentLoaded 前才执行）→ 卡片写入空表（显示"暂无满足条件的个股"）。
- 既有 DOMContentLoaded 重绘兜底（line 12860）只覆盖 `__renderV8Cal*` / judgment，**漏了 `renderRpsScreen`** → 永久空白。
- 数据本身完全正常：`STOCK_RPS.js` 316 条 records，默认过滤（A档 + RPSmax≥90）命中 **54 只**，`update_time 2026-08-31 19:16`。

## 二、修复（仅改 index.html，无新数据文件）
在 init 的 DOMContentLoaded 兜底链（line 12860 附近）新增：
1. `doRpsRetry()`：DOMContentLoaded 时（defer 已执行、数据就绪）重渲染 `renderRpsScreen`。
2. `setTimeout 400/1200ms` 兜底调用 `doRpsRetry`。
3. **自愈轮询**：每 1s 检测 `strpsBody` 空白且 `STOCK_RPS_DATA.records` 就绪则自动补渲染——范式同 2026-08-19 商品弹性榜(COMMODITY_ELASTICITY) 的 setTimeout+自愈方案，已验证可靠。

## 三、三件套落地
- ① 4 面对齐：纯前端渲染竞态修复，云端 cron / 运维页 / 逻辑详解页均无需改动。
- ② 审计：inline `<script>` 23 段 `new Function()` 校验 **JS 语法 0 错误**；字段完整性已核（STOCK_RPS_DATA 316 条齐全）。
- ③ 推仓防撤回 + 小九交接：本变更单条命令 `git add index.html + 文档 → commit → fetch origin main → rebase FETCH_HEAD → push` 原子完成，规避 Nutstore 实时同步回滚；交接文档入库 `docs/ops/urgent/`。

## 四、验证（硬刷新 Ctrl+F5 后）
进入「🔒 选股策略 → 相对强度」子页：
- 表格显示 54 只 A 档 + RPSmax≥90 个股（默认过滤），按 A/B/C 档 + RPSmax 排序。
- 顶部徽章「✅ 08-31 已计算」。
- 切换分层/最小RPS 下拉框即时刷新。

## 五、同类风险备注（小九关注）
同处 init 末尾 `tryRun` 调用、且数据源为 defer 脚本的卡，若其宿主子页无"切 tab 时 lazy 重渲染"兜底，理论上也存在同样竞态。本轮回填了 `renderRpsScreen`。如后续发现其他卡空白，优先排查是否同一 defer 竞态 + 缺 DOMContentLoaded 重试。
