# 🚨 URGENT · 给小九（单位机白天值班）— v8 盘中巡检异常

- **发出方**：阿狸咪（盘中安全巡检自动化）· 2026-09-10 10:09 CST（周四·盘中）
- **触发**：v8 盘中巡检退出码 1
- **结论一句话**：**不是踩踏风暴**（活跃并发仅 1 个）。3 个失败里 2 个是同一个根因 —— `Pre-deploy audit` 恒定阻断，已由阿狸咪一劳永逸修复并验证转绿；剩 1 个需小九执行（PAT 无 workflow scope 推不了）。

---

## 一、先排雷：不是风暴，别加派 dispatch

| 项 | 实测值 | 判定 |
|---|---|---|
| 活跃/排队 run | **1**（🇨🇳 中国数据抓取·小九应急） | ✅ 无并发堆积 |
| API 剩余配额 | **5000/5000** | ✅ 未被限流 |
| 近 3h 失败/取消 | 11 次（集中在 01:20-01:48 UTC） | ⚠️ 同一根因连锁，非风暴 |

→ **已确认无风暴苗头，未新增任何 dispatch。** 历史教训（自愈派发器每 1-2 分钟补派 → 5+ 并发 → 403 secondary rate limit）本次不适用。

---

## 二、根因 A（✅ 已修复并验证）：Pre-deploy audit 恒定阻断整条部署链

### 现象
`☁️ v8 构建部署(云端ubuntu)` run 34425092781 在 `🛡️ Pre-deploy audit` 步骤失败：

```
✅ [1/4] py_compile: 169 个 .py 0 错误
✅ [2/4] new Function: 24 个 inline script 0 错误
✅ [3/4] data 完整性: 103 个 data/*.js 全部 >100B
❌ [4/4] align_logic_ops: 抓取看门狗：期望有 cron 但实际 workflow 无 cron 调度
🚫 1 项校验失败 → 阻断 deploy！
```

### 根因（对不上账的两份配置）
1. 2026-09-09「盘中更新审计·一劳永逸」改造已**刻意删除** `v8_cn_fetch_watchdog.yml` 的 GitHub schedule cron，改由 WorkBuddy 自动化「v8 看门狗驱动(每15分)」dispatch 触发（理由：云端 schedule 高负载时静默漏触发，实测 2026-09-01 全天 0 次）。
2. 但 `align_logic_ops.py` 的 `MUST_HAVE_CRON` **没有同步更新**，仍把 `v8_cn_fetch_watchdog` 列为「必须有 cron」。

→ 于是**只要跑就必挂**，deploy 步骤永远 skipped → 盘中 `data/*.js` 全站不更新。

### 💡 坑点（务必记下）
本地 `E:\workspace\stock-scanner` 工作区里的 `v8_cn_fetch_watchdog.yml` **是带 cron 的旧版**（坚果云把远端新版回退成了旧版），所以**本地跑 `align_logic_ops.py` 是通过的、云端 CI 必挂**。
→ 这文件不能再信本地副本，以后判定必须以 `git show FETCH_HEAD:` 或 GitHub API 取的远端内容为准。

### 修复（阿狸咪已推 main，commit `81a3f3a74`）
把 `v8_cn_fetch_watchdog` 从 `MUST_HAVE_CRON` 移入 `ALLOW_NO_CRON`（与既有先例 `v8_slot_scheduler`、`v8_cn_fetch_intraday_lemoncat` 处理方式一致），并附完整理由注释。

### ✅ 验证（推送后 2 分钟内全部转绿）
| workflow | 修复前 | 修复后 |
|---|---|---|
| ☁️ v8 构建部署(云端ubuntu) | ❌ failure | ✅ **success** |
| 🩺 v8 云端健康巡检(合并·自愈+体检) | ❌ failure | ✅ **success** |
| ☁️ v8 盘中算法追踪(轻量) | ❌ failure | ✅ **success** |
| pages build and deployment | cancelled | ✅ queued → 发布中 |

> 健康巡检的失败是 A 的**连带**（自愈验证回查仍 fail），根因解除后自动恢复，无需单独处理。

---

## 三、根因 B（⛔ 待小九执行）：HEALTH_CHECK 被「发现陈旧项」误判失败，堵住推送

> 阿狸咪 PAT 是 fine-grained 最小权限、**无 `workflow` scope**，GitHub 拒绝推送 `.github/workflows/*`（403）。这是主人的凭证安全铁律，**已选择不绕过**，故交小九执行。

### 现象
`☁️ v8 盘中算法追踪(轻量)` run 34425087315 在 `🩺 刷新 HEALTH_CHECK.js` 失败，日志：

```
[INFO] 已生成 data/HEALTH_CHECK.js          ← 明明已经成功写出！
[INFO] 总体: warn | 统计: {'ok':110,'warn':3,'fail':2,'total':115}
[FAIL] 全量数据/TRIPLE_HISTORY: 更新于 2天前 20:14；超过通用红线 1440 分钟
[FAIL] 全量数据/VOLATILITY:    更新于 2天前 20:14；超过通用红线 1440 分钟
[HEAL✓] 当前 09:22 非盘后产出窗口(16:00-21:30)，跳过 algo_run 派发（防风暴）
##[error] v8_health_check.py 失败，健康面板未刷新
##[error] Process completed with exit code 1.
```

### 根因（语义混淆）
`v8_health_check.py:2622` → `sys.exit(0 if report["overall"]=="ok" else 2)`

- `exit 2` 本意是「**体检发现 warn/fail 项**」，跟「**脚本跑挂**」是两码事。
- `TRIPLE_HISTORY` / `VOLATILITY` 是**盘后产出类**（16:00-21:30 才有新数据），**上午跑必然判陈旧** → 恒定 exit 2。
- workflow 写的是 `python v8_health_check.py || { echo error; exit 1; }` → job 红 → **后续 `📤 推送变更到 main` 步骤 skipped**
- → **已经生成好的 HEALTH_CHECK.js 反而推不上 main**。这是纯自伤。

> 自愈逻辑本身是对的（日志 `[HEAL✓] 非盘后产出窗口，跳过派发（防风暴）`），不要动它。

### 🔧 一劳永逸修复（请小九执行，替换 `.github/workflows/v8_algo_intraday_lite.yml` 第 98-102 行）

把：
```yaml
      - name: "🩺 刷新 HEALTH_CHECK.js"
        # 🔴 2026-09-08 主人令「禁止假 success」：删 continue-on-error + || true。
        #    体检脚本跑挂 = 监控失效，必须可见。
        run: |
          python v8_health_check.py || { echo "::error::v8_health_check.py 失败，健康面板未刷新"; exit 1; }
```
改成：
```yaml
      - name: "🩺 刷新 HEALTH_CHECK.js"
        # 🔴 2026-09-08 主人令「禁止假 success」：删 continue-on-error + || true。
        # 🛡 2026-09-10 一劳永逸根因修复：v8_health_check.py 用 sys.exit(2) 表示「体检发现 warn/fail 项」，
        #    与「脚本跑挂」是两回事。盘后产出类数据（TRIPLE_HISTORY / VOLATILITY 等 16:00-21:30 才产出）
        #    在上午必然判陈旧 → 恒定 exit 2 → 本步 exit 1 → 后续 push 步骤 skipped
        #    → 已成功生成的 HEALTH_CHECK.js 反而推不上 main（2026-09-10 09:22 实测，run 34425087315）。
        #    正确语义：报告已产出即算刷新成功；陈旧项由健康面板红黄灯呈现 + v8_health_patrol 自愈，不阻断推送。
        #    注：v8_health_patrol 仍依赖 exit 2 做自愈判定，本改动不动脚本本体、只改本 workflow 的判读。
        run: |
          set +e
          python v8_health_check.py
          rc=$?
          set -e
          echo "v8_health_check.py 退出码=$rc (0=全绿 / 2=有 warn-fail 项但报告已产出)"
          if [ ! -s data/HEALTH_CHECK.js ]; then
            echo "::error::v8_health_check.py 未产出 data/HEALTH_CHECK.js（rc=$rc），健康面板未刷新"
            exit 1
          fi
```

**不要改 `v8_health_check.py` 本体**：`v8_health_patrol` 的自愈判定依赖 exit 2，改成恒 0 会让整个自愈体系失效。

---

## 四、待观察 C：🇨🇳 中国数据抓取(云端) 被取消（**原因未确证，别当结论用**）

- run 34425888151，`workflow_dispatch`，09:32 CST 起跑，**09:48 CST 在 `💰 分红方案刷新（cninfo·云端主跑）` 步骤被 cancelled**，后续 18 个步骤全 skipped。
- 已排除：① 不是超时（16min < job timeout 60min）② 不是同组顶掉（`v8-cn-fetch-cloud` 的 `cancel-in-progress: false`，2026-08-24 起）。
- **未确证**：怀疑是人工取消（该时段有「小九应急」run 在跑），但**没有日志证据，不打包票**。
- 建议小九查证命令：`gh api repos/ah-quant999/quant-scanner-v8/actions/runs/34425888151` 看 `event` / `actor`，或看 Actions 页面操作记录。

---

## 五、数据新鲜度快照（只看文件内 `update_time`，不看 mtime）

新鲜 OK 35 / 未分类跳过 43 / **落后 22**。盘中类最要命的 3 个（阈值 1h）：

| 数据 | 落后 | 说明 |
|---|---|---|
| `INDEX_QUOTES` | 18.7h | 盘中类，根因 A 阻断所致 |
| `AVG_PRICE_DATA` | 18.7h | 同上 |
| `ETF_INTRADAY_HEAT` | 18.7h | 同上 |

日更类落后 40h+ 的一批（`INDEX_HISTORY` / `INST_TRADE` / `SUSPENSION_ALERT` / `NT_DATA` / `SECTOR_FUND_FLOW_TREND` 等）是盘后产出，**今天 16:00 后自然会补**，不用管。

→ 根因 A 修复后构建链已恢复，**这一批应在下一轮跑批后自动追平，不需要手工重跑**（重跑是掩盖，不是修复）。

---

## 六、给小九的待办清单

| # | 事项 | 状态 |
|---|---|---|
| 1 | 执行第三节的 `v8_algo_intraday_lite.yml` 补丁（需 workflow scope 凭据 / 本地 git push） | ⬜ 待小九 |
| 2 | 查证第四节 cn_fetch 被取消的真因 | ⬜ 待小九 |
| 3 | 确认今日 16:00 后盘后链正常跑，INDEX_QUOTES 等追平 | ⬜ 待观察 |
| 4 | **本地 `v8_cn_fetch_watchdog.yml` 是坚果云回退的旧版**，下次改这文件前先 `git fetch origin main` 对齐 | 📌 记住 |

---

*本文件由阿狸咪盘中巡检自动生成并推送至 main（Contents API，未使用本机 git push，规避坚果云同步竞争）。*
