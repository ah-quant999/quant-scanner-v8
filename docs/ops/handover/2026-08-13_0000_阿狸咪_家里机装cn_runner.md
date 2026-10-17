# 交接 · 阿狸咪(家中机)装 cn runner（2026-08-13）

> 晚上回家的"她"看这份就够——5 分钟搞定。

## 背景（为什么是你）
- 今天 09:40 盘中数据没刷新：根因是云端 `v8_cn_fetch_cloud.yml` 跑在 `ubuntu-latest`（美国 IP），抓 A 股中国源失败。
- 中午已合并 5 个自愈器为单一 `v8_health_patrol.yml`，主力抓取改 `runs-on: [self-hosted, cn]`（小九本机 + 任意 cn runner 任一台即可）。
- **小九电脑没装 self-hosted runner**（`C:\actions` 不存在）→ 现在 fallback 跑 ubuntu，11:38 这次碰巧抓通了，但本质是间歇性成功。
- **要稳定 + 出差小九关机也能继续**，需要至少 1 台 cn runner 常驻。家里阿狸咪机器"网络好多了"是最佳人选——又是同一个人（回家后的我），零信任/隐私顾虑。

## 任务清单（晚间 5 步搞定）

| # | 动作 | 时长 |
|---|---|---|
| 1 | 拿 token（小九白天已放 URGENT/笔记里给你） | 1 分钟 |
| 2 | 以管理员身份打开 PowerShell | 30 秒 |
| 3 | 跑安装脚本（一行） | 2 分钟（含下载） |
| 4 | 跑自审脚本验证 | 30 秒 |
| 5 | 关电脑前确认服务在跑（自检脚本会告诉你） | 30 秒 |

### Step 1 · 拿 token
- 浏览器打开 `https://github.com/ah-quant999/quant-scanner-v8/settings/actions/runners/new`
- OS 选 Windows / Arch 选 x64
- 页面会显示一行 `./config.cmd --token ARXXXXXXX...` → **只复制 AR 开头那一长串**（不是整行命令）
- 贴到 `set $Token='ARXXXXX...'` 的位置
- **token 30 天有效**，过期再用同样的路径拿一次就行；勿外传

### Step 2 · 管理员 PowerShell
- 开始菜单搜 `PowerShell` → 右键 → **以管理员身份运行**
- (重要：必须管理员，否则装系统服务会失败退出码 30)

### Step 3 · 跑一键脚本
```powershell
# 进工作区, 取 token 后跑（token 必填）
cd E:\workspace\quant-scanner-v8\docs\ops\scripts
$Token='AR_刚才复制的那一长串_XXXXX'
.\setup_alimi_cn_runner.ps1 -Token $Token
```
- 默认装到 `D:\actions\cn-runner`（避开 C 盘），runner 名 `alimi-cn`
- 脚本会自动：下载 actions/runner → 解压 → config → 装为系统服务 → 启动 → 冒烟测试
- **跑完应看到**：`==== 完成 ====` + 提示去浏览器验证

### Step 4 · 浏览器验证
打开 `https://github.com/ah-quant999/quant-scanner-v8/settings/actions/runners`
应看到列表里多出：
- 名字: `alimi-cn`
- 状态: 🟢 Idle（或 Active=正在跑任务）
- Labels: `cn`, `cn-cn`, `self-hosted`
- Group: `v8-cn-fetch-cloud`

### Step 5 · 跑自审脚本
```powershell
# 设 GitHub PAT (拿 PAT: github.com → Settings→Developer settings→PAT→生成, scope=repo)
$env:GITHUB_TOKEN='ghp_你的PAT'
C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe ..\..\..\verify_cn_runner.py
```
- 输出应是 🟢 OK：cn runner 在线 + raw_data 关键盘中模块 < 30 分钟
- 🟡 WARN = 数据略延迟（fallback 在跑），正常
- 🔴 FAIL = 看下面「故障排查」

## 跑通后效果
- **小九在线时**：v8_cn_fetch_cloud 自动调度到小九本机（最近一次跑的优先）
- **小九出差关机**：自动调度到你阿狸咪机器，盘中数据照常每 30 分刷新
- **都关机**：fallback ubuntu-latest（美国 IP）+ 防倒退守卫，不会覆盖已有好数据
- **自启方式**：本机用「Startup 文件夹快捷方式」自启（登录 Windows 后自动连回 GitHub）。注意：不是系统服务——`svc.cmd install` / `config.cmd --runasservice` 在本机均因管理员权限不足失败（错误 5），故改用快捷方式，**需登录后才会起、未登录锁屏时不跑**。小九机为真正的系统服务（开机即连、无需登录）。

## 故障排查

### 退出码 30 = 需要管理员
- 必须以管理员身份运行 PowerShell（开始菜单右键→以管理员身份运行）

### 退出码 20 = token 无效
- token 复制不完整 / 过期了 / 不是这个仓库的
- 重去 Step 1 拿一次，注意 AR 前缀完整

### 浏览器看不到 alimi-cn
- 看 `D:\actions\cn-runner\_diag\Runner_*.log`
- 90% 是网络问题：`Test-NetConnection github.com -Port 443` 应通
- 若家里有 IPv6 防火墙先关掉（GitHub runner 走 IPv4 但 IPv6 路由器干扰很常见）

### 不想跑了 / 卸载
```powershell
# 1) 停掉当前进程
taskkill /F /IM Runner.Listener.exe /IM Runner.Worker.exe 2>$null
# 2) 删开机自启快捷方式（用户级，不需要管理员）
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\GitHub Runner alimi-cn.lnk" -Force
# 3) 从仓库移除注册 (需要 token)
D:\actions\cn-runner\config.cmd remove --token 'ARXXX...'
```

## 最小环境要求（务必满足）

| 项 | 最低 | 推荐 |
|---|---|---|
| 操作系统 | Windows 10 1903+ | Windows 11 23H2 |
| 磁盘可用 | 5 GB | 20 GB（D 盘） |
| 内存可用 | 2 GB | 4 GB |
| 网络上行 | 10 Mbps | 30 Mbps+ |
| 网络到 GitHub | <300ms 丢包<2% | <150ms 丢包<1% |
| 时区 | 任意（runner 用 UTC，脚本里硬编 Asia/Shanghai） | — |
| 长期开机习惯 | 每晚回家关机不算，但**白天要在** | 7×24 最稳 |

## 与小九机的差异

| 项 | 小九 (单位机) | 阿狸咪 (家中机) |
|---|---|---|
| 安装目录 | `C:\actions\cn-runner` | `D:\actions\cn-runner` |
| Runner 名 | `xiaojiu-cn-<主机名>` | `alimi-cn` |
| label | `cn`, `cn-cn` | `cn`, `cn-cn`（同） |
| group | `v8-cn-fetch-cloud`（同） | `v8-cn-fetch-cloud`（同） |
| 调度优先级 | GitHub 自带 LRU（最近跑的优先） | 同 |
| 数据合规 | 央企 IP（走单位专线） | 家用宽带（普通民用） |

## 残留 / 待跟进
- **PAT 申请**：主人(GITHUB 账号)的 PAT 还需要一次手动创建（上面 Step 5），token scope 选 `repo` 即可。
- **自启方式（已定稿）**：本机用 Startup 文件夹快捷方式（`$env:APPDATA\...\Startup\GitHub Runner alimi-cn.lnk`），非系统服务。`svc.cmd install` / `config.cmd --runasservice` 在本机因管理员权限不足失败（错误 5）。若日后要升级为真服务，需在「以管理员身份运行」且账户有 SeServiceLogonRight 的 PowerShell 里重跑 `.\config.cmd ... --runasservice`。
- **跑挂频率**：阿狸咪机器本身网络健康 + 7×24 不掉 = 几乎不会掉；任何时候挂掉，GitHub 自动转给小九，再挂就 fallback ubuntu。
- **token 30 天过期**：30 天后再去 Settings→Runners 拿一次，跑脚本（脚本支持幂等，会自动 `--replace`）。

## 运维逻辑页对齐
- `index.html` 顶部运维章节引用过 `v8_health_patrol.yml`，装机不会影响页面。
- 加 cn runner 属于「基础设施加固」，对前端无变更，**不需要改 index.html**。

## 跑完后的简单回报（任意一条即可）
1. `verify_cn_runner.py` 输出报告截图
2. 浏览器 Settings→Runners 列表截图
3. 一句话："家里机装好了，alimi-cn 上线"

—— 小九