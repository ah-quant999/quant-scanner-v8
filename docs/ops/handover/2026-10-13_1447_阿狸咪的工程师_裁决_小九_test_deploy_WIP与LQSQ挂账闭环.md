# 裁决 · 小九 `_test_deploy` WIP 与 LQSQ 挂账闭环（阿狸咪，14:47 CST+8）

- 触发：主人令对《全面接手》交接件中「小九 `_test_deploy` 21 项 WIP + 未推送 commit，待主人裁决合并」一条**专家判定并执行**。

## 一、事实取证（git 权威，非记忆）
- 远端分支全集（`git ls-remote --heads origin`）：`main`=`955857643c`、`feat/v8-detach-v6`、`fix/block3-rename`、`fix/lemoncat-sleep600`。**无 `_test_deploy`。**
- 小九 2 笔 commit `6f5d99c59`/`ad111eecc`：**不在任何远端分支** → 仅存于小九本机（lemoncat-cn，已下线）。
- 结论：该 21 项 WIP + 2 笔未推送 commit **只在小九那台离线单位机上**，阿狸咪物理上无法读取、无法合并、无法删除。

## 二、专家判定
- **生产不受影响**：远端 `main` 干净（`955857643c`）；选股四模块 10-11 `3d4e6b0a5d` delist 已在 main 生效；盘中/日频数据今日持续刷新。小九 WIP 未上远端，**对主站与数据链零作用力**。
- **阿狸咪侧无可执行动作**：不存在「从阿狸咪合并/丢弃」的选项——远端没有对象可操作。此项对阿狸咪即「无需处理」。
- **合并与否的裁决权与动作只能落在小九回归后**，且**严禁小九把 `_test_deploy` 直接 force/合入 main**（其 WIP 含 index.html / workflows×3，与 main 已生效的 delist + LQSQ 前端上架 `f209149449` 分叉，盲合会回退这些）。

## 三、给阿狸咪自己/小九回归的执行口径
1. **阿狸咪**：本项关闭为「生产无碍、本机无从处理」；不做任何 git 动作、不 force、不新建远端分支代推。
2. **小九回归时二选一**（由小九在其本机执行，阿狸咪不代劳）：
   - a) 保留备份：`git push origin _test_deploy`（推成**远端可评审分支**，绝不入 main），再与 main 做差异比对后按主人意图决定；
   - b) 弃掉：在小九本机 `git checkout main && git reset --hard origin/main && git clean -fd`（仅限确认 WIP 无价值后）。
3. 若小九未回归前有人/有流程异常推 main：既有 fast-forward 校验 + v8_build_deploy 门禁会拦，交由「主站盯站值守」发现即报。

## 四、附带闭环：LQSQ 挂账（小九交接 §四 黄点）
- 取证：main 上 `data/LQSQ_TRACK.js`(9161B) / `data/LQSQ_BACKTEST.js` 今日 **14:36 新鲜**；`update_v8.py` LQSQ 映射齐全（lqsq_track→LQSQ_TRACK / lqsq_backtest→LQSQ_BACKTEST，tip `f209149449`）。
- 判定：「量质双擎」卡若曾在某机为空，根因是**该机本地 `update_v8.py` 落后远端一版**（小九 WT 滞后），**生产/主站侧无碍**，无需阿狸咪补刀。

## 五、署名
阿狸咪的工程师（alimi-cn 家机）
2026-10-13 14:47
