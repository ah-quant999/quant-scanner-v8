# 阿狸咪 → 小九 紧急交接：S3 已完成，备机 7×24 就绪

**时间**：2026-09-08 17:53  
**交接人**：阿狸咪（家里机）  
**接收人**：小九（单位机）  
**主题**：S3 睡眠/休眠已彻底关闭；双跑决策已拍板；请把 IP 敏感 workflow 改回 `runs-on: cn`

---

## 1. 家里机现在真实状态（17:53 实测）

| 项 | 状态 | 证据 |
|---|---|---|
| runner 进程 | ✅ 在线 | `Runner.Listener` pid=11732（自 17:23 起稳定） |
| 守护进程 | ✅ 常驻 | `_guard_loop.ps1` pid=3220，每 30s 巡检 |
| 计划任务 | ✅ 运行中 | `v8_cn_runner_guard`，登录触发，崩溃后 1 分钟重启 |
| 电源方案 | ✅ 高性能 | `powercfg /query` GUID = 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c |
| S3 待机 | ✅ 已关 | `standby-ac = 0`, `standby-dc = 0`（timeout=0） |
| 休眠 | ✅ 已关 | `powercfg /hibernate off`；`powercfg /a` 显示"休眠 尚未启用" |
| 硬盘睡眠 | ✅ 已关 | `disk-ac = 0`, `disk-dc = 0` |
| 显示器 | ⚠️ 30 分钟熄 | 仅屏幕熄，机器不睡 |
| 网络 | 默认在线 | 家里网络不稳，但能保持长连 |

→ **阿狸咪已具备 7×24 备机条件**。

---

## 2. 双跑决策（主人 17:30 拍板）

- **接受 active-active 双跑**。
- **小九 = 主机（primary）**：单位机中国 IP 稳定，应多接任务。
- **阿狸咪 = 备机（backup）**：家里网络不稳，仅在小九不可用时兜底。
- 固有代价已如实告知：GHA 同 `cn` label **无主备优先级**，可能偶发双跑；若阿狸咪网络失败，不会自动改派，需你手动重跑。

---

## 3. 需要你做的最后一步

把以下 workflow 的 `runs-on` 改回 `cn`（或加 `cn` 矩阵）：

1. `.github/workflows/v8_algo_cloud.yml`
2. `.github/workflows/v8_stock_quote_refresh.yml`
3. 其他依赖中国 IP / baostock / 东财实时数据的 workflow

示例改动：

```yaml
jobs:
  run:
    runs-on: cn        # 从 ubuntu-latest 改回
    # 或容错写法：
    # runs-on: [self-hosted, cn]
```

> ⚠️ 改 workflow 文件必须用 **Git Database API** + `v8_gh_token.txt`（带 workflow scope），不能用 Contents API。阿狸咪本机脚本在 `backup/push_workflow.sh` 可作参考。

---

## 4. 验证清单（改完请跑）

- [ ] GHA `Settings → Actions → Runners` 中 `alimi-cn` 和 `lemoncat-cn` 都显示 **Idle/Online**
- [ ] 手动 dispatch 一次 `v8_algo_cloud.yml`，确认能派到 `cn` runner 并成功
- [ ] 若失败，检查是否两机都在线；若是网络问题，重跑一次即可

---

## 5. 监控兜底

已建 3 个 WorkBuddy 自动化（跑在阿狸咪本机）：

| 名称 | 频率 | 触发 |
|---|---|---|
| 盘中每小时 | 交易日 9–15 点每小时 | HOURLY;BYDAY=MO-FR;BYHOUR=9..15 |
| 非盘中每2h | 交易日 7-8、16-21 每2h | HOURLY;INTERVAL=2;BYDAY=MO-FR;BYHOUR=7,8,16..21 |
| 周末首日每2h | 仅周六 | HOURLY;INTERVAL=2;BYDAY=SA;BYHOUR=8,10,12,14,16,18,20 |

离线时：自愈 1 次 + 邮件告警到 2814546@qq.com 喊主人远程登录。
夜间 22:00–07:00 不跑，假期后续日不跑。

---

## 6. 本地文件提示

- 产物全在仓库外：`D:\actions\cn-runner\` + `C:\Users\HH20210606\WorkBuddy\2026-08-28-19-46-49\backup\`
- 阿狸咪本地 clone 有历史未提交残留（`v8_algo_cloud.yml`/`DO_NOT_DELETE.md`/`HANDOVER_LOG.jsonl`/`__pycache__` 等），**不是本轮引入**，请勿 `git add -A`。
- 你的 `C:\Users\Administrator\qs8-tmp\v8_deploy_watch.py`（18KB 哨兵）不在仓库，我们不会碰。

---

**改完 workflow 后，双机热备正式闭环。**
