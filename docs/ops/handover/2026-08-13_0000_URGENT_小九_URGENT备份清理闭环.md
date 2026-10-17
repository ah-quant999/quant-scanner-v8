# 交接闭环 · root URGENT/backup 噪声清理（2026-08-13）

## 背景（为何不能只删）
- 仓库根目录长期堆积 `URGENT_小九_*.md`（看门狗每轮留痕）+ `backup/*`（每日 raw_data 备份）。
- 链路核查发现：这些文件**不是死文件**——`v8_cloud_watchdog.py::write_urgent()` / `v8_health_check.py` 每小时在云端重建并写到仓库根；`v8_cleanup.yml` 每周日 23:00 CST 跑 `git add -A` 把它们**重新 commit 回 origin/main**。
- 67 个 root URGENT 已在 origin/main 中。若只本地删，下周日 cleanup 会把新生成的再推回来 → git status 反复脏，**删了等于没删**。

## 一劳永逸式根因修复（已推仓入库防覆盖）
1. **根因守卫**：`.gitignore` 加 `/URGENT_*.md`（仅根目录），并显式 `!` 保留 3 份含根因/交接信息的文件。
   - 效果：`v8_cleanup.yml` 的 `git add -A` 不再回推 root URGENT；`docs/ops/urgent/` 正式交接通道**不受影响**。
2. **清理当前批次**：
   - `git rm` 64 个 tracked root URGENT + 4 个 tracked `backup/*`；
   - 6 个 untracked root URGENT + 3 个 untracked `backup/*` 送 Windows 回收站；
   - 备份见 `.workbuddy/cleanup_backup_20260813_1127.tar.gz`（77 个文件，可恢复）。
3. **保留**（不删、不忽略）：
   - `URGENT_阿狸咪_2026-08-08_添加ZSXQ_TOKEN_Secret.md`（阿狸咪给的 Secret 配置指令）
   - `URGENT_小九_2026-08-11_19-43_根治项+模型全切.md`（主人根治项+模型全切指令）
   - `URGENT_小九_2026-08-10_0117_v8健康自检告警.md`（含 NT_DATA 回退修复笔记）
4. **commit + push origin/main**：`40d8a667`（rebase 过云端多次推送后成功）。

## 三方对齐
- **云端（ubuntu runner）**：行为不变（仍写 URGENT 留痕），但 `.gitignore` 让重建文件永不进仓库 → 不再污染 git。
- **小九（单位机）**：本地工作树已干净，root 仅剩 3 份保留文件。
- **阿狸咪（家中机/主人）**：本交接文档即对齐记录；保留的 3 份 URGENT 含其历史指令，未丢失。

## 运维逻辑详解页对齐
- `index.html` 仅在 line 5438 泛述「某天某源挂了 → 写 URGENT 告警」、line 5511 引用保留的 `19-43 根治项` 文件。
- 删除的是 root noise，页面**无硬链到被删文件**，不出现断链；泛述文案仍准确（云端确实仍写 URGENT，只是 gitignore）。
- **无需改页面**。

## 遗留 / 备注
- `backup/*` 为云端 `v8_backup.yml` 每日重建的安全网，按主人「这次用掉的」指示删当前批次；次日会重新生成（属正常安全网，不污染 git status 长期目标可后续评估是否也 gitignore）。
- `verify_daily_audit.py` 查 commit 是否在 HANDOVER/URGENT 被提到：删除 root URGENT 不影响，HANDOVER_*.md 仍覆盖 commit 提及。
- 后续若想进一步收敛：可改 `write_urgent()` 直接写 `docs/ops/urgent/`（官方消费通道），彻底不落 root。当前 gitignore 方案已达成「git status 清爽 + 防回推」目标。
