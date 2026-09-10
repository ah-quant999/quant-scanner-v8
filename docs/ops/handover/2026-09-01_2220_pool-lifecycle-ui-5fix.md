# HANDOVER 2026-09-01 22:20 — 选股策略页 / 选股池 / 暂未上架 五改

## 1. 提交
- 本地：`c80d42bc1`
- 远端：`c80d42bc1`（已推送 origin/main，GitHub Pages 自动部署）
- deploy-trigger: `2026-09-01T21:55 lifeflow-pool-guardian-pool-2026-09-01`
- 审计：`new Function()` 解析 107 段 inline `<script>`，**0 错**

## 2. 5 个改动（按主人截图顺序）

| # | 位置 | 改动 | 行号 |
|---|------|------|------|
| 1 | 主力净额分时累计曲线 | fallback 扩到非盘前时段：snaps 为空时永远回退 prev_snapshots/history，保留上一交易日曲线到次日盘前才清空 | 6920-6944 |
| 2 | 选股策略页 tab 顺序 | 4⭐ 选股生命周期 放到 5⭐ 三重共识 后面：新顺序 = 选股池(5⭐)→三重共识(5⭐)→选股生命周期(4⭐)→相对强度(3⭐)→逆势龙头(无) | 2280-2284 |
| 3 | 选股池外资研投默认展开 | 移除 `stPoolStockList` 的 `display:none` 兜底 + 删除 "▾ 展开明细" 按钮 + 重构为 5 个 `<details>`（外资研投带 `open` 默认展开，其他折叠，summary 显"点击展开/收起"） | 2294 + 9618-9655 |
| 4 | v8 选股生命周期卡加「更新于」 | 复用 `_uBadge('盘后','短线', _upd)` 在卡名后插入胶囊（与 热门赛道资金追踪 21:03 区分，新卡时间不一致必须分开放） | 4202-4203 |
| 5 | 暂未上架补宏观/板块推荐容器 | `<div id="ulMacroPanel">` + `<div id="ulSecPanel">` 加到 ulPaneStrong 内（在 热门赛道资金追踪 容器后面），配合 renderUnlisted 尾部已有的 `renderMarketRegimeCard` / `renderSectorRecommendationCard` 调用 | 10728-10729 |

外加死代码清理：`window.toggleStPoolDetail` 函数（10行）+ `isExpanded` 局部变量（1行）一并删除，注释保留说明为什么移除。

## 3. 4面对齐检查

| 面 | 状态 | 说明 |
|----|------|------|
| 云端 cron | ✅ N/A | 本次纯 UI 改动，workflows 无需变更 |
| 双机 | ✅ N/A | index.html 单文件改动，E:\workspace\stock-scanner 唯一真实工作目录已推 |
| 运维页 | ✅ 不影响 | 运维页 (renderOps) 读 HEALTH_CHECK.js 数据，与本次 UI 改动无依赖 |
| 逻辑详解页 | ✅ 不影响 | 逻辑详解 (renderLogicSec) 静态展示，不读 runtime 数据 |

## 4. ⚠️ 运维盯一下

主人令："算法链跑完后是否全部正常，无报错无红灯黄灯"。

**当前数据状态**（21:54 查证）：
- `CANDIDATE.js` update_time = `2026-09-01 02:17`（凌晨，13+ 小时未刷新）
- `TRIPLE_CONSENSUS.js` = `2026-08-31 19:53`（昨夜）
- `FOUR_VOLUME.js` = `2026-08-31 19:53`
- `GOLD_POOL.js` = `2026-09-01 02:02`
- `COCKPIT_ADVICE.js` = `2026-09-01 03:44`
- `HEALTH_CHECK.js` overall=`fail`、17 项 fail、92 ok、1 warn

**根因**：今晚 9/1 的 `v8_algo_cloud` 19:15 算法链没成功推送数据上 main。GitHub MCP / gh CLI 本机都不可用，无法直接 dispatch 重跑。

**阿狸咪（夜机）处置建议**：
1. 等主人明天早 7:45 上小九后，由小九自托管 runner 跑 `v8_algo_cloud` workflow → 19:15 的 cron 也只是当晚
2. 或主人手动 `git pull && python run_algorithms.py && git add data/*.js && git commit && git push`（阿狸咪机有完整 akshare 依赖）
3. 本次 UI 改动**不会触发任何新红/黄灯**（纯属前端 layout + chip 渲染），已上线，主人硬刷新即可看效果

## 5. 主人硬刷可见效果

| 页面 | 变化 |
|------|------|
| 选股策略 | tab 顺序：选股池 → 三重共识 → **选股生命周期** → 相对强度 → 逆势龙头 |
| 选股池 | "外资研投 XX只" 默认展开，4 个其他来源折叠为 ▸ 点击展开 |
| 选股策略 - 选股生命周期 | 卡名后新增 🦊 更新于 19:53 盘后短线 胶囊 |
| 选股策略 - 热门赛道资金追踪 | 已有 🦊 更新于 21:03 胶囊（验证过，与 19:53 不一致，主人令已满足分开放） |
| 暂未上架 | 强突 3 卡后 + 热门赛道资金追踪 + 🌍 宏观 + 🌐 板块推荐（4 卡同 pane，无子 tab） |
| 主力净额分时曲线 | snaps 为空时回退到 prev_snapshots/history（盘中空时不显示"暂无"，展示上一交易日曲线） |

## 6. 反向核对清单（主人硬刷后请确认）

- [ ] 选股策略 tab 顺序：5⭐→5⭐→4⭐→3⭐→无星
- [ ] 选股池：外资研投默认展开，其他 4 来源折叠
- [ ] v8 选股生命周期卡：卡名后有 🦊 更新于 胶囊
- [ ] 暂未上架：宏观+板块推荐+热门赛道资金追踪+强突 3 卡全在一个页面，无子 tab
- [ ] 主力净额分时曲线：现在不空白（哪怕显示昨天的曲线也算修好）
- [ ] 运维页：等算法链跑完后，红/黄灯应清空（本次改动不影响，但主人令要盯）

— 完
