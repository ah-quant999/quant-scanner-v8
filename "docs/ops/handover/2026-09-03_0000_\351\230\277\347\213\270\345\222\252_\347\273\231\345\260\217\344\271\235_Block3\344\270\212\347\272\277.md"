# 阿狸咪 → 小九 交接单（2026-09-03 盘后收口）

> 主人令：把"最新改好的"交给小九，由小九合入上线。阿狸咪白天不碰 index.html 推送，仅留交接。

## 🎯 本次唯一待办（务必完成）
**板块资金三合一 Block3 标题改名：`周期定位` → `板块资金趋势`（方案B）**
- 文件：`index.html` 第 2347–2351 行附近（区块 `<!-- Block 3: 周期定位 -->`）
- 改动量：**仅 1 个词**，2 行上下文，无 data 变动、无 `?v` 变动、不影响其它卡

### ✅ 推荐执行方式（零手写、零歧义，首选）
该改名已打包在远端分支 `fix/block3-rename`（commit `8ad539cdbf3f57442e8d9e6a53d2c65dfab9d1ff`），小九机直接采摘即可：
```bash
git fetch origin fix/block3-rename
git cherry-pick 8ad539cdbf3f57442e8d9e6a53d2c65dfab9d1ff
```
（若提示 "already applied" 或冲突，说明本地已含此改动，跳过即可）

### 🔧 备选（手写，仅当 cherry-pick 失败时用）
精确 diff（index.html 第 2349 行那一行）：
```diff
-        <div class="sf-block-title"><span class="sf-block-icon">🔄</span>周期定位</div>
+        <div class="sf-block-title"><span class="sf-block-icon">🔄</span>板块资金趋势</div>
```

## ✅ 收口步骤（小九白天窗口内执行）
```bash
git add index.html                      # 只加这一个文件，绝不加 -A（防坚果云误删带入）
git commit -m "feat(UI): Block3 周期定位→板块资金趋势(方案B)"
git fetch origin main
git rebase -X ours FETCH_HEAD          # 用远端 main 重放，避免坚果云冲突
for i in 1 2 3; do git push origin HEAD:refs/heads/main && break || sleep 3; done
```
若 `git push` 在 github.com:443 挂死：改走 GitHub API 兜底脚本
（`C:/Users/HH20210606/.workbuddy/skills/github-api-push-fallback/`）。

## 🔍 验证上线成功
1. node 审计：23 段 inline `<script>` 语法 0 错；
2. GitHub Pages 生效（约 1–2 分钟）后，**Ctrl+F5 硬刷新**看"板块资金趋势"标题出现即成功。

## 🚫 不要做
- **9/3 数据不要手动跑**：主人已选 A，保留晚间自动链（18:05 保底 → 19:30 兜底查 15:00 后 success → 21:30 最终闸 force+bypass）。
- 时间门陷阱：18:00 前的补跑必须带 `bypass_time_gate=true`，否则选股段被跳过白跑。

## 📌 不在本次交接范围（勿动）
- `v8_algo_cloud.yml` 的"静默闸门"改动：阿狸咪本地已 `git stash`（msg=`v8_algo_wip_20260903`）隔离，**小九无需处理**；请勿碰该文件以免双机冲突。
- 斐波那契双卡合并（`a67f0fe28`）：已上线，无需动。

---
*交接人：阿狸咪 ｜ 时间：2026-09-03 17:20 CST ｜ 状态：fix/block3-rename 已在 GitHub 远端，待小九 cherry-pick 合入 main。*
