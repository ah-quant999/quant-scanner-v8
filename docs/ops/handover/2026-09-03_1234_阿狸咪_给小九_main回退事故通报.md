# ⚠️ 阿狸咪→小九：main 回退事故通报与防再犯（2026-09-03 19:5x）

## 发生了什么（时间线，均为实时核对）
1. 19:34 前：main = `e5cc7a8b`（09-03 主线，含当天全部 CI build、Block3 改名、交接文件）。
2. 19:37：main 被 force-push 回退到 **09-01 基线**（`659f792b`，父提交 `11f39eb1` = "v8 build: 2026-09-01 12:34"），**丢掉 09-01 以来 786+ 个提交**，Pages 一度开始部署 09-01 旧版。
3. 19:5x：阿狸咪已恢复——main = `e8d20e96`（重建 09-03 主线 + 合入小九的 v8_cn_fetch ETF timeout 修复），Pages 已成功部署，线上已含「板块资金趋势」。

## 根因
小九是从**陈旧 clone**（HEAD 停在 09-01 的本地副本）直接 force-push main 导致回退。

## 🚫 铁律（请小九务必遵守）
1. **push 前必须先对齐**：`git fetch origin && git status` 确认自己的 HEAD 落后于 `origin/main` 时，先 `git pull --rebase origin main`，再改再推。
2. **严禁 `git push --force` / `--force-with-lease` 到 main**。任何 non-FF 被拒都停下来查原因，不许绕过。
3. `E:\workspace\workspace\quant-scanner-v8\` 是陈旧 clone（HEAD 常不同步），**只读参考用**，不要在那里改动后直接推 main；推送一律在最新 pull 过的工作目录进行。
4. 事故现场自查：`git log --oneline origin/main -5`，若发现 main 又回到 09-01 线，**立即停手并通知阿狸咪/主人**，不要自行"修复"。

## 顺带说明
- Block3 改名（周期定位→板块资金趋势）已由阿狸咪在 19:34 直接合入 main 并上线（交接单里的 cherry-pick 任务**已替你完成**，无需再做）。
- 基于 09-01 旧基线的「🇨🇳 中国数据抓取」run 已取消，防止旧基线数据反推 main；下轮调度自动用恢复后的 main。
- 小九的 workflow 修复（v8_cn_fetch ETF step timeout-minutes 20）已确认包含在恢复后的 main 中，无丢失。
