# URGENT 交接 · 小九第186轮看门狗巡检（2026-08-13 18:45-18:47）

> 通道：小九 ↔ 阿狸咪 每小时紧急交接（看门狗 + 自动修复 + 前端健康检查 + 邮件告警）
> 执行机：小九（白天窗口末端 18:45，即将交接阿狸咪夜间 18:00-次日 7:30）
> 运行命令：`v8_cloud_watchdog.py --heal --auto-dispatch --health-check --alert`
> 解释器：`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`（纯标准库，无需 pandas）

## 一、巡检结论（一句话）
🔴 **cn_fetch / algo 云端双 workflow 仍死在 `actions/checkout@v4`**（自 11:47 起约 7 小时 outage 持续；run 228/229/230 全部 completed/failure，实测 checkout 步骤仍 `completed/failure`）。本机小九直抓兜住盘中/今事件卡；盘后 algo 派生卡（融资融券/股指期货持仓，冻结于 11:05）与候选池（观澜台 token 缺失）继续冻结。1 封告警邮件已发（活跃窗口，非静音抑制）。

## 二、看门狗六管线
| 管线 | 状态 | 详情 |
|------|------|------|
| runner | ✅ OK | lemoncat-cn online=True busy=True（在线能接单，本轮回显 busy 仍在工作） |
| cn_fetch | ❌ FAIL | run 230 in_progress→completed/failure @ 18:48（实测 checkout@v4 步骤 completed/failure）；上轮 229 同死；自 11:47 连续零成功 |
| build_deploy | ❌ FAIL | completed/skipped @ 18:41（age 4m）— 触发但被 skip（无相关变更则良性，看门狗判 FAIL） |
| raw_data | ✅ OK | last commit 18:17（age 28m，阈值 1.5h）— 小九本地直抓兜底 |
| site | ✅ OK | HTTP 200 |
| auto_dispatch | ✅ OK | 派发 post_close[融资融券, 股指期货持仓]（命中死 algo workflow 必失败，设计边界） |

## 三、前端健康检查（data/HEALTH_CHECK.js @ 18:46，v8_health_check.py --heal）
- **overall=fail · ok38 / warn3 / fail3 / total44**
- ❌ FAIL 3 项：
  - 融资融券（age >360min，上次 algo 成功 ≈ 11:05，outage 后冻结）
  - 股指期货持仓（age >360min，同上 algo 派生盘后源）
  - 本地与 origin/main 同步（本地落后：local / origin 3462b79c0；云 health patrol 持续写 HEALTH_CHECK.js 所致，架构预期内良性）
- ⚠️ WARN 3 项：
  - Pages 部署同步（no token / 网络抖动瞬时，三通路重试失败，非真故障）
  - 最终推荐市场分布（Top3 全 A股：000100 MINIMAX-W / 688331 荣昌生物 / 600489 中金黄，疑似数据源异常，与丢观澜台源同源）
  - 国际投行信号 A股覆盖（今日 0 只，弱市可接受）
- 🔧 HEAL 动作：本地同步因 1 项未提交改动跳过（防 stash/pop 污染 data/*.js）；post_close 自动派发在 standalone 无 token 下失败（看门狗自身有 token 已派发）

## 四、与 185 轮对比（趋势）
- fail 3（185）→ **3（186）**：融资融券/股指期货持仓/本地同步 三项纹丝不动；候选池未单列 FAIL（观澜台源缺失属内容审计 WARN 同源，未进 fail 计数）。
- cn_fetch 连续第 ~13 轮零成功（run 218-230 全 failure），outage 进入第 7 小时。
- 🔧 **修正 18:45 初步乐观判断**：当时见 cn_fetch「in_progress @18:41」误以为 checkout 可能恢复；实测 run 229/230 均仍死 checkout@v4（completed/failure），**确认 outage 未恢复**。`in_progress` 仅代表 checkout 步骤正在执行后失败，并非通过。

## 五、处置（红线内未执行）
- 🔴 **P0 修 lemoncat-cn checkout**：runner 上 git.exe 不在 PATH / `_work` 损坏 / node20 运行时缺失（checkout 步骤 completed/failure，非 60s 超时）。仓库根已备 `setup_alimi_cn_runner.ps1` + `verify_cn_runner.py` 修复包（阿狸咪夜间窗口执行）。
- 🟠 **P1 观澜台 token**：需 HH 提供 `data/zsxq_token.json`{"token":...} → 小九本机即可自足产观澜台，脱离云端独立兜底候选池。
- ⛔ **明确禁止**：拆丢源守卫、手工拷 out→raw（会丢观澜台 61 只属倒退）。

## 六、静音核查
18:45 处于活跃窗口（7-21），1 封告警邮件（cn_fetch/健康检查真失败）已发 18:46:11，非静音抑制。夜间 22:00-07:00 静音段已内置，不发邮件仅留痕。

## 七、致命窗口预警
⚠️ 今晚阿狸咪夜间 + 明早盘前：小九直抓停摆后，若 runner 仍坏 → **全站回落陈旧**（盘中/今事件卡也将失鲜），候选池/融资融券/股指期货持仓届时无当日数据。请阿狸咪夜间优先修 runner checkout。

## 八、git / 文件状态
- HEAD `2ea94dd40` @ main（本地落后 origin，预期内；未 push，红线内不擅动）
- 工作区脏项（预期内，未提交）：`data/HEALTH_CHECK.js`（本轮回写）
- index.html 未触碰（红线）；本 URGENT 文件落盘 E 盘坚果云 junction，阿狸咪可见。

---
_下轮（187）跟踪：① cn_fetch 仍 failure=outage 持续第 8h → 升级催修 runner；② token 是否落地→有则本机直跑候选池转 OK；③ 恢复双标志=cn_fetch success + 候选池 update_time 转当日。_
