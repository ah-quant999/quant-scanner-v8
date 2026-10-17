# 盘中 09:40 档实况报告（2026-09-10 09:50）

## 一、09:40 触发云端了吗？
- **主调度 `22505803` 触发了**，但**没有派发新的 intraday run** —— 查到 09:32 有 cloud run（#34425888151）`in_progress` 占 `concurrency: v8-cn-fetch-cloud` 锁，按防踩踏逻辑**正确跳过**。
- 09:32 run 是 watchdog（`2d9121c8`，09:30 触发）补漏派发的 intraday，但**卡在 GitHub 云队列 15 分钟、盘中数据零更新**（云队列今天也拥堵，昨天 13 点同因）。

## 二、破局兜底（已执行）
- 取消 09:32 卡住 run（HTTP 202，锁释放）✅
- 派发小九机 **selfhosted intraday 兜底**（run#34426850135，已 `in_progress`）✅
- 小九机 runner `lemoncat-cn` 在线（labels: `cn,xiaojiu`）✅
- 盘中数据（INDEX_QUOTES 等）现仍 08:47（陈旧 62 分），selfhosted 抓取中，**预计 09:55–10:00 推出新鲜数据**。

## 三、暴露的设计漏洞（必须一劳永逸修复，否则每天踩）
1. `already_running` 检查不区分"卡住的 run" —— 一个无效 run 占锁就把主派发档挡掉，导致空窗。
2. 云端 `ubuntu-latest` 今天也拥堵，盘中主派应**优先 selfhosted**（小九机中国 IP，不挤云队列），cloud 作兜底。

## 四、修复方案（稍后做，不影响今天盯盘）
- `22505803` prompt：running run 超 20 分无数据更新 → 强制取消 + 派 selfhosted 兜底。
- 盘中主派发改优先 selfhosted，cloud 作兜底。

## 五、下一步
- 09:55 复查 selfhosted run 结果 + 盘中数据新鲜度；若未更新立即介入。
- 10:00 档照常（`22505803` 触发，查重派发）。
