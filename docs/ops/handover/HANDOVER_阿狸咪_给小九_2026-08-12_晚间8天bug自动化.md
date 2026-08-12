# 交接：小九（8 天 bug 自动化检测+根因修复）

**时间**：2026-08-12 20:35
**提交**：`957e2368f`（已 push main，本地 == 远端）
**主令**：「以后全是港股或者任何一个算法跑出是 0 的，马上回溯哪里有错！」

## 主人愤怒的根因

8 天持续 bug（三重共识全港股 / 黄金池全港股）没被发现，因为 `v8_health_check.py` 的两个检查漏洞：

1. **check_data_cards 显式豁免空 stocks**：
   ```python
   if v == [] and f == "stocks":
       continue  # ← 8 天没人发现的主因！
   ```
   把"空 stocks"当"正常业务状态"跳过，**但实际上 0 只可能是上游 bug**（候选池路径错位 → 没 A 股信号股 → 0 入选）

2. **check_signal_date_freshness 只盯 Top3**：只检查 `FINAL_RECOMMEND_DATA.stocks`，候选池/黄金池/三重共识/驾驶舱等其他池的「全港股」**完全没人查** → 黄金池全港股 5/5 持续 8 天未告警

## 修复（commit `957e2368f`）

### 1. 删除"空 stocks 豁免"盲区
- 改成：0 只本身仍不强制 warn（弱市真实状态可接受）
- 但「全港股 / A 股扫描失败」由新专门检查捕获

### 2. 新增 `check_a_share_coverage` 函数
扫 8 个主要 `*_DATA.js` 的 `stocks` 字段，规则：

| 状态 | 含义 | 告警级别 |
|------|------|----------|
| 总数=0 | 弱市真实状态 | 弱 warn（不报邮件）|
| **总数>0 且 A 股=0** | **A 股扫描失败/上游路径 bug** | **🚨 URGENT（推邮件+标红）** |
| 总数>0 且 A 股≥1 | OK | 无 |

覆盖数据池：
- 候选池 CANDIDATE / 黄金池 GOLD_POOL / 三重共识 TRIPLE_CONSENSUS
- 驾驶舱分档 COCKPIT_TIER_RECOMMEND / 逆势龙头 CRDS_CARD_DATA
- 四量终极 FOUR_VOLUME / 国际投行信号 MAHORO / 龙虎榜 LHB_DATA

### 3. 测试触发
```bash
python v8_health_check.py
# 输出:
# [WARN] 内容审计/黄金池 A股覆盖: 🚨 URGENT: 黄金池 全港股（5/5），A 股扫描失败/上游路径 bug！
# [WARN] 内容审计/三重共识 A股覆盖: ⚠️ 三重共识 今日 0 只...
# [WARN] 内容审计/驾驶舱分档 A股覆盖: ⚠️ 驾驶舱分档 今日 0 只...
```
**8 天 bug 终于被自动化捕获！**

## 黄金池数据恢复

`commit 957e2368f` 之前修过 `scanner.load_candidate_pool` 路径兼容（commit `045ac1c84`），但云端 scanner 还没跑出新数据。本交接发起后：

- 派发了 `v8_algo_cloud.yml` workflow_dispatch（GitHub API），云端立即跑新算法链
- 预计 5-10 分钟后黄金池出 A 股数据
- URGENT 告警将自动转为 OK

如果云端跑后 URGENT 仍报：
1. 检查云端 scanner 跑日志 `gh run view <run_id> --log-failed`
2. 确认 scanner.py 用的是 `045ac1c84` 后的版本（load_candidate_pool 路径兼容）
3. 检查 `data/candidate.json` 的 source_dist 是否含「主板成交前100」等 A 股来源

## 小九必读

### 自动化（已落地）
- v8_health_check.py 已含 A 股覆盖检查（commit `957e2368f`）
- 云端每次 v8_algo / v8_ops_self_heal 跑 health_check 都会自动检测
- URGENT 告警会推邮件（v8_health_report.json 含 items 数组，前端 HEALTH_CHECK.js 展示）

### 任何全港股/0 只异常 → 立即回溯
- 8 个被覆盖数据池：CANDIDATE / GOLD_POOL / TRIPLE_CONSENSUS / COCKPIT_TIER_RECOMMEND / CRDS_CARD_DATA / FOUR_VOLUME / MAHORO / LHB_DATA
- 优先查 scanner.load_candidate_pool 路径（commit `045e1c84` 修过）
- 优先查 fundamental_quality 读文件路径（commit `045ac1c84` 修过）
- 优先查港股 API（akshare / yahoo）

### 纪律
- 看到「全港股」或「0 只」**立刻**查上游（不要再等 8 天）
- 不要手动"补"数据（违反不造假铁律），让上游自愈
- 修完路径后**派发 workflow_dispatch** 立即跑，不要等下一次 cron

## 相关 commit 总览（今夜）

| commit | 内容 |
|---|---|
| `d2bac2576` | 个股查询混合 query 修复 |
| `045ac1c84` | 三重共识 8 天为 0 根因（fundamental 读错 + scanner 候选池路径）|
| `b74bf32d8` | 港股降权 qs -=10 + 本地重跑 |
| `c0cd1362a` | 帮助说明改回双列 |
| `9b4c1a24d` / `cb2495a5d` | 任务看板实时化 + Pages token 修复 + 候选池 update_time |
| `f4525a4d4` | 两融+ETF 走势 x 轴日期标签重叠 |
| `0cdf7eca4` | 持仓成本文案修改 |
| `06260f1fd` | 三重共识前端更新部署跟踪审计 |
| `8e110fc09` | 盘后字形回退修复 |
| `957e2368f` | **本次**：健康检查加 A 股覆盖 URGENT（8 天 bug 主因）|
