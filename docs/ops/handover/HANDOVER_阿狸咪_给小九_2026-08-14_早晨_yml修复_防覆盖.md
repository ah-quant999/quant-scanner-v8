# 交接：阿狸咪 → 小九（2026-08-14 早 07:00）

> 生成时间：2026-08-14 07:00（阿狸咪夜班收尾）
> 覆盖：2026-08-13 夜 + 08-14 凌晨全部工作
> 前置：昨晚交接文档 HANDOVER_阿狸咪_2026-08-14_凌晨_新卡_策略回测_算法公平性.md

---

## 1. 昨晚+今晨全部 commit（已全部推 origin/main ✅）

| commit | 内容 |
|---|---|
| `fd2b85260` | 中金黄金名字修复（XD 除权前缀兜底） |
| `0787fe4f6` + `30440bfbd` | 暂未上架三张新卡（涨价榜/情绪周期/潜力挖掘） |
| `9a8180e5c` | CRDS 弱市兑现卡精简（只留当日判定） |
| `cc8dfa0e3` | 🔒 策略回测统一 tab |
| `bab235e28`→`fe5d4d47f` | ⭐ 策略星级对比表（14 策略聚合） |
| `2629bd574`→`07a5e6e73` | 三张卡接 update_v8.py 自动刷新 + 统一更新于胶囊 |
| `ee2cbbf64` | 持仓删除黑名单（v8_pf_hidden）+ renderDelisted 去缓存 |
| `9c5d6027d`~`e5cfa01b5` | **v8_cn_fetch_cloud.yml 系列修复（见 §2）** |
| `e5cfa01b5` | **防覆盖算法产物 + 恢复 08-13 回测数据（见 §3）** |

## 2. v8_cn_fetch_cloud.yml 修复（今晨关键）

**背景**：盘后档数据 14:44 UTC 起 5 次连续失败，已下架 11 卡停在 11:xx。

| 问题 | 修复 |
|---|---|
| case `'0 9,13'` 不匹配 cron `'0 9,14'` | case 同时接受两种 + 未匹配走 all |
| 注释里 `${{ steps.cat... }}` 被表达式解析器求值 → parse 失败 | 删注释中的表达式字符串 |
| 简化时删了 `id: cat`（line 128 引用它）| 恢复 id: cat |
| **Windows runner 默认 shell=PowerShell，不认 case 语法** | **恢复 `shell: bash`**（真凶） |

**教训**（必须记住）：
1. self-hosted Windows runner **必须显式 `shell: bash`**，默认 PowerShell 没有 case/for 语法
2. GitHub 表达式解析器**连注释里的 `${{ }}` 都会求值**，注释里别写表达式
3. 修复后 dispatch 204 ✅，step 2 通过 ✅，但 step 3 checkout 偶发超时（lemoncat-cn 网络抖动，非代码问题）

## 3. 防覆盖（主人令"防覆盖了？"）

**严重 bug 已修复**：05:40 cloud_fetch 推送 raw_data 时，用云端 runner 工作区的 **08-04 旧版 backtest_tdx.json（144只）覆盖了 main 上 08-13 新版（296只，14万行被砍）**。

修复：
1. `api_push_raw.py` `walk_raw()` **排除算法产物**：backtest_tdx / backtest_comprehensive / cockpit_backtest / optimized_strategy / top3_track
2. 从 ba9ae1d04 恢复 08-13 新版（calc_time=2026-08-13, 296只, 12420信号）

**规则**：算法产物（家庭机 17:20 run_algorithms 产出）**只能由 run_algorithms/本地推链维护**，cloud_fetch 不许覆盖。若后续新增算法脚本，记得加进 walk_raw 排除表。

## 4. 待办/遗留

- **策略回测 tab 试运行观察**：主人说先跑几天，勿动口径
- **已下架数据补齐**：yml 修复已生效，等 cron（8:25 盘前 / 17:20 盘后 / 17:00 全量）自动跑；checkout 网络抖动会自愈
- **alimi-cn runner offline**：主人电脑 reboot 后没启 runner 服务，不影响 lemoncat-cn
- **ToDesk**：家机 776897407，24h 验证期今 22:00 解锁
- **PAT**：新 token `v8-yaml-fix`（workflow scope）已用于推送；旧 ghp_th1i 缺 workflow scope 推不了 yml

## 5. 数据健康（08-14 早）

- 策略星级：👑驾驶舱A档 64.7%/+4.47% 独一档
- 情绪周期：🔥 狂热 84 分
- 已下架卡片数据待 cron 刷新（8:25 盘前档是第一个窗口）
