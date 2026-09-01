# 阿狸咪 v8 数据保底通道配置指南

> **来源**：小九 2026-08-14 11:48 交付
> **目的**：在你家机器上配置第二路数据保底，与小九本机错峰运行
> **仓库**：`ah-quant999/quant-scanner-v8`（同一仓库，同一 main 分支）

---

## 一、架构概览

```
┌──────────────┐         ┌──────────────┐
│   小九本机    │         │  阿狸咪本机   │
│  (主通道)     │         │  (保底通道)   │
│              │         │              │
│ :00/:20/:40  │◄─错峰──►│ :15/:45      │
│ freshness_   │         │ freshness_   │
│ guard 检查   │         │ guard 检查   │
│              │         │              │
│  ↓ 陈旧则抓   │         │  ↓ 陈旧则抓   │
│  ↓ push raw  │         │  ↓ push raw  │
│  ↓ 验证新鲜度 │         │  ↓ 验证新鲜度 │
└──────┬───────┘         └──────┬────────┘
       │                        │
       └───────┬────────────────┘
               ▼
        GitHub origin/main
               │
        云端 v8_build_deploy
        (自动 update_v8.py → Pages)
```

**核心原则**：
1. **两机独立运行**，不互相依赖
2. **都靠 `freshness_guard.py` 反应式触发**——数据新鲜就跳过，不浪费资源
3. **都只推 `raw_data/` 目录**——不动红线文件
4. **靠 `api_push_raw.py` 防倒退守卫**——旧时间戳自动跳过
5. **错开 15-30 分钟窗口**——避免同时 push 冲突

---

## 二、前置条件（你机器上必须有的）

| 项目 | 要求 | 验证命令 |
|------|------|----------|
| Python 3.13+ | 含 akshare/pandas | `python -c "import akshare,pandas;print('OK')"` |
| Git | 已配 SSH 或 token | `ssh -T git@github.com` 返回 Hi |
| 仓库克隆 | `quant-scanner-v8` | `cd quant-scanner-v8 && git remote -v` |
| freshness_guard.py | 仓库根目录 | `ls freshness_guard.py` |

**如果 freshness_guard.py 不存在**（你本地落后）：
```bash
cd /path/to/quant-scanner-v8
git pull --rebase --autostash origin main
# 应该能看到 freshness_guard.py 在仓库根目录
```

---

## 三、WorkBuddy 自动化配置

### 方法 A：通过 WorkBuddy UI 创建（推荐）

在阿狸咪的 WorkBuddy 中创建自动化：

**名称**：`阿狸咪-v8盘中数据保底(错峰·freshness_guard)`

**Schedule（RRULE）**：
```
FREQ=HOURLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9,10,11,12,13,14;BYMINUTE=15,45
```
- 触发时间：**09:15/09:45/10:15/10:45/11:15/11:45/12:15/.../14:45**
- 与小九主通道(:00/:20/:40)错开 15 分钟

**工作目录（cwds）**：
```
<你的仓库路径>/quant-scanner-v8
```

**Prompt（完整复制以下内容）**：

---

```
阿狸咪-v8盘中数据保底（freshness_guard · 第二路错峰通道）

⚠️ 你是小九的冗余保底。两机独立运行，互不依赖。
⚠️ 与小九主通道错开 15 分钟：你在 :15/:45，他在 :00/:20/:40。

工作目录：<你的仓库路径>/quant-scanner-v8
Python：用你机器上的托管 venv python（含 akshare/pandas）
  示例：C:/Users/<你的用户名>/.workbuddy/binaries/python/envs/default/Scripts/python.exe
  （路径根据你机器实际情况调整）

执行流程（每次触发均执行）：

## Step 0: 时间 + 新鲜度双检
HHMM=$(date +%H%M)
PYTHON=<你的python全路径>

GUARD_OUT=$($PYTHON freshness_guard.py --category intraday --quiet 2>/dev/null)
echo "守卫结果: $GUARD_OUT"

### 时间判定：
- HHMM 在 0930-1130 或 1300-1500 → 盘中模式，继续 Step 1
- HHMM 在 1130-1300 → 午休模式，继续 Step 1（阈值宽松到65min）
- 其他 → 输出「非交易时段，跳过」并结束

### 新鲜度判定：
- "$GUARD_OUT" == "FRESH" → 输出「✅ 数据新鲜，跳过本次」并立即结束
- "$GUARD_OUT" 以 "STALE:" 开头 → 存在陈旧文件，继续 Step 1
- 守卫脚本异常 → 保守策略：继续执行抓取（宁抓勿漏）

## Step 1: 本机直抓（中国IP）
cd <你的仓库路径>/quant-scanner-v8
$PYTHON cloud_fetch_v8.py --category intraday

- 记录输出中的模块数和关键指标
- 若脚本报错且无任何模块成功 → 回报「抓取完全失败」并结束（不push空壳）
- 单模块失败不影响整体（脚本已容错）

## Step 2: 校验 + 推送（只动 raw_data/）
git fetch origin main
git add raw_data/
if [ -n "$(git status --short raw_data/)" ]; then
  git commit -m "data: 阿狸咪保底补抓(intraday) $(date +%Y%m%d-%H%M)" raw_data/
  git pull --rebase --autostash origin main || true
  git push origin main
  echo "✅ 已推送"
else
  echo "ℹ️ raw_data 无变化，跳过推送"
fi

## Step 3: 推送后验证
$PYTHON freshness_guard.py --category intraday --quiet
- "FRESH" → ✅ 补抓成功
- 仍 "STALE" → ⚠️ 警告

## 铁律（绝对不可违反）：
1. 只 push raw_data/ 目录
2. 严禁触碰 index.html / HEALTH_CHECK.js / PORTFOLIO.js / BLOAT_CHECK.js
3. 严禁 git checkout -- / git restore 对红线文件操作
4. push 必须先 pull --rebase --autostash，严禁 --force
5. 不本地 deploy、不跑 update_v8.py（由云端 build 负责）
6. 不 dispatch 云端 cn_fetch workflow（美国 runner 抓不到中国数据）
7. 若本机无中国网络（直抓返回空数据），跳过本次不 push

输出简报（中文 ≤6 行）：守卫结果、抓取模块数、推送结果、验证结果。
```

---

### 方法 B：通过 API 创建（如果你有 API 访问权限）

调用 automation_update tool，mode="create"，参数同上。

---

## 四、关键文件说明

| 文件 | 作用 | 你需要知道的 |
|------|------|-------------|
| `freshness_guard.py` | 数据新鲜度守卫 | 每次 trigger 前必跑；退出码 0=新鲜/1=陈旧 |
| `cloud_fetch_v8.py` | 数据抓取脚本 | `--category intraday` 抓盘中 14+ 模块 |
| `api_push_raw.py` | 防倒退守卫 | 由 cloud_fetch 内部调用；旧时间戳自动跳过 |
| `update_v8.py` | raw→js 转换 | **不要本地跑**，由云端 build 自动执行 |

---

## 五、故障排查

| 症状 | 可能原因 | 解决方法 |
|------|----------|----------|
| 守卫报 "FILE_MISSING" | 文件不存在 | `git pull` 更新本地仓库 |
| 守卫永远报 "STALE" | 抓取成功但 push 失败 | 检查 git 凭据/SSH key |
| push 被 reject | 远端有新 commit | 加 `--autostash` 重试 |
| cloud_fetch 全部失败 | 网络问题 | 跳过本次，下个触发点重试 |
| freshness_guard.py 不存在 | 本地仓库落后 | `git pull --rebase --autostash origin main` |

---

## 六、与小九的分工边界

| 职责 | 小九（主通道） | 阿狸咪（保底） |
|------|---------------|---------------|
| 触发时间 | :00/:20/:40 | :15/:45 |
| index.html 改动 | ❌ 不碰 | ❌ 不碰 |
| HEALTH_CHECK.js | ❌ 不碰 | ❌ 不碰 |
| raw_data/ push | ✅ 主力 | ✅ 保底补漏 |
| 盘前 08:15 | ✅ 负责 | 可选（小九已覆盖） |
| 盘后 15:30/17:00 | ✅ 负责 | 可选 |
| 故障通知 | 自动化日志 | 同上 |

**冲突处理**：若两机同时 push 导致 rebase 冲突：
- raw_data 文件冲突 → 取 update_time 较新的版本
- 绝不 `git push --force`
- 冲突无法解决 → `git rebase --abort`，下次再试

---

## 七、首次启用检查清单

- [ ] 仓库已 clone 到最新（`git pull` 有 freshness_guard.py）
- [ ] Python 环境有 akshare/pandas（`python -c "import akshare"`）
- [ ] Git SSH 已配置（`ssh -T git@github.com` 返回用户名）
- [ ] WorkBuddy 自动化已创建（RRULE + Prompt 完整）
- [ ] 手动测试一次：在非交易时段运行 prompt，确认流程走通
- [ ] 下一个交易日观察：09:15 是否正常触发并输出报告

---

*文档版本：2026-08-14 v1.0 | 作者：小九 | 最后更新：11:50 CST*
