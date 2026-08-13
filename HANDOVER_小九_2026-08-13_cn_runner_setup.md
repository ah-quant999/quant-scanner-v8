# 即时指引 · 小九（白天）配 cn runner（2026-08-13）

> 今天两件事要做：(1) 拿 token 自己装本机 (2) 把 PAT/交接文档给晚间阿狸咪
> 每件 ≤ 1 分钟。

## A. 现在（白天）· 本机装 cn runner
1. **拿 token**：浏览器打开
   `https://github.com/ah-quant999/quant-scanner-v8/settings/actions/runners/new`
   OS=Windows / Arch=x64 → 页面会显示一行 `./config.cmd --token ARXXXXXXX...`
   → **只复制 AR 开头的长串**
2. **管理员 PowerShell**：
   ```powershell
   cd E:\workspace\quant-scanner-v8\docs\ops\scripts
   $Token='AR_刚才复制的那一长串_XXXXX'
   .\setup_cn_runner.ps1 -Token $Token -RunnerName 'xiaojiu-cn-office'
   ```
3. **验证**：浏览器刷新 `https://github.com/ah-quant999/quant-scanner-v8/settings/actions/runners`
   → 看到 `xiaojiu-cn-office` 状态 Idle → 立刻看 [Runners tab](https://github.com/ah-quant999/quant-scanner-v8/actions/workflows/v8_cn_fetch_cloud.yml) 看下一次云端调度是不是跑在你这台（cron `*/30 1-8` 即 CST 9:00–16:30 每 30 分）

## B. PAT 申请（晚间阿狸咪自审要用）
1. 浏览器：`https://github.com/settings/tokens?type=beta`
2. Generate new token → name=`v8-cn-runner-verify` / expiration=No expiration / scope=`repo`
3. **复制 token（ghp_开头）** → 放在你本机 `C:/Users/Administrator/.workbuddy/secrets/v8_gh_pat.txt`
   （已 gitignore，**不要提交**；晚间阿狸咪脚本会读这个文件做自审）
   ```powershell
   # 一次性写入（无回显）
   'ghp_你的token' | Set-Content -NoNewline 'C:/Users/Administrator/.workbuddy/secrets/v8_gh_pat.txt'
   $env:GITHUB_TOKEN = Get-Content 'C:/Users/Administrator/.workbuddy/secrets/v8_gh_pat.txt'
   ```

## C. 给晚间阿狸咪的交接
- **token 单独再发一份**：晚间阿狸咪也要 token（与本机独立，30 天各自过期）
- **PAT 共享**：晚间阿狸咪从坚果云同步拿到 `v8_gh_pat.txt`（坚果云 E 盘已同步到 C 盘用户目录）
- 让她直接看 `docs/ops/handover/HANDOVER_阿狸咪_2026-08-13_家里机装cn_runner.md`
- **不需要**：她自己生成 token（你帮她拿即可，省她 1 分钟）

## D. 不要做的事
- ❌ 不要把 token commit 到 git
- ❌ 不要把 PAT 写进 workflow 文件（写到 `docs/ops/handover/` 也不可以）
- ❌ 不要在阿狸咪机器上跑本机的 `setup_cn_runner.ps1`（默认装 C 盘会挤爆系统盘）
  - 正确：用 `setup_alimi_cn_runner.ps1`（默认装 D 盘）
- ❌ 不要先 dispatch 一个测试 workflow 测 runner（脚本里已有冒烟测试）

## E. 装完后自审（任一台都行）
```powershell
$env:GITHUB_TOKEN = Get-Content 'C:/Users/Administrator/.workbuddy/secrets/v8_gh_pat.txt'
C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe E:\workspace\quant-scanner-v8\docs\ops\scripts\verify_cn_runner.py
```
- 🟢 OK = 都到位（cn ≥ 1 台 online + 数据 < 30 分钟）
- 🟡 WARN = cn runner 离线但 fallback 兜着（数据稍延迟，正常）
- 🔴 FAIL = 数据 > 45 分钟 且 0 cn runner（**fallback 也挂了**）→ 看云端 Actions 日志

## F. 时机
- 本机：建议**今天**就装，越早装 9:30/10:00 之后的云端 cron 就自动调度到本机
- 阿狸咪机器：等晚间回家（按你的计划），不用急
- 跨日注意：token 30 天后失效，到时候再走 Step A 重拿一次（脚本支持幂等）