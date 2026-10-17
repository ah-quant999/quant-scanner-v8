# 交接档：阿狸咪 → 小九｜index.html 待决定事项 + 本轮已上线说明

> 生成：2026-09-23 08:39（阿狸咪/家机，北京时间）
> 性质：**协调档（待小九拍板）**，非回执/催办。阿狸咪已按主人「现在推」指令上线 4 文件修复，但 index.html 真实改动**按住未动**，等小九/主人确认。

## 一、已上线（无需再议）

- 推送提交：`d7b832bd5`（main, 快进, 零推退, 门禁 14/14 全绿）
- 4 个文件（均为状态源/防覆盖脚本，不涉及选股算法）：
  - `docs/ops/HANDOFF.yaml`（gate-1010 → pending-verify + fix_applied；handoff-cw + ledger_fix）
  - `docs/ops/HANDOFF.ledger.json`（60/60 与 yaml 对齐）
  - `docs/ops/index_protected_markers.txt`（登记 ms-note-card 第 35 条锚 + 删退役锚）
  - `v8_ws_sync_guard.py`（两处 checkout 后补 `git reset -q HEAD --` 拆弹）
- 推送时机说明：主人 08:08 明确说「现在推」，当时是**小九白天时段**，阿狸咪按主人 override 执行；主人随后表示「还没开盘都可以改了上线，你和她商量下再行动」，故后续改动交由小九/主人协调。
- 用户工作备份 `stash@{0}`（pre-handoff-push-20260923-backup，29 文件）**完好保全**，未自动 pop。

## 二、待小九拍板：index.html 约 13 行真实改动

**背景**：比对 `stash@{0}:index.html` vs `origin/main:index.html`，总差异 229 行，其中 **216 行是 BUILD/`?v=` 部署戳（CI 自动重写，忽略）**，**仅 13 行是用户真实前端增强**。

**真实改动内容（最终推荐排序一致性 UI）**：
1. 因子榜卡提示语改写：强调「本榜排序与最终推荐 TopN 完全一致」。
2. 推荐渲染逻辑：严格按 `FINAL_RECOMMEND_DATA` 顺序（池内票与跨策略池外票同序交织），保证排名完全一致。
3. 跨策略池外票标注 `⊘跨策略池外`（橙标）。
4. 新增**数据日不同步告警**：因子榜 `update_time` 日期 ≠ 最终推荐 `update_time` 日期时，提示排名可能不完全对应。

**选项（请小九/主人定）**：
- A. 保留并补回 main：从 `git show stash@{0}^3:index.html` 局部提取这 13 行补丁（**勿整体覆盖**，以免带入旧 BUILD 戳），apply 到 main → 跑 `_tools/check_inline_js.js` + `pre_deploy_audit.py` → 部署。
- B. 已废弃/别处已实现：stash 该片段可忽略，stash 整体可清理（无未推实质工作）。

## 三、阿狸咪当前状态

- 已切回 `main`（与 origin/main 同步），`handoff-fix` 临时分支已删。
- 工作树仅余双机监控再生状态文件 `raw_data/_peer_monitor_state.json` 的 ` M`（常态，不进提交）。
- **阿狸咪不再擅自动 index.html，等小九/主人回话。**

## 四、备注（给小九）

- HANDOFF.yaml 中 owner=小九 的 pending-verify P0 四项（algo-step15-undefined-t / index-tail-truncation-2220 / cn-fetch-writer-version-drift / trunc-read-treated-as-success）仍需 run 终验后改状态——此为小九车道职责，阿狸咪未越权。
- 本档未提交远端（避免在小九时段单方推送）；若需小九在另一台机看到，请主人/小九确认后再 commit+push，或原地由小九读取本仓工作树。
