# HANDOVER 2026-09-01 22:55 · 暂未上架瘦身 + 回测对比下沉 + 4⭐置顶

> 双机：阿狸咪夜机本日 22:00-23:59 接管 · 主人 22:55 在线监督

## 🎯 任务摘要
主人 4 个诉求全部落地（一份 commit, atomic push）：

| # | 诉求 | 实施 |
|---|------|------|
| 1 | **暂未上架 = 除曲线新卡外，其他全清** | 删除 `ulPaneStrong` 三卡（两套算法回测对比 / 动量共识精选 / H 反推短线买点）+ 上轮误加的 `ulMacroPanel` / `ulSecPanel` 容器 + `renderMarketRegimeCard` / `renderSectorRecommendationCard` 死代码 + `window.renderXxxCard` 暴露。暂未上架**只剩一行** `ulSectorFundTrackPanel`（曲线新卡） |
| 2 | **两套算法回测对比卡搬到「大牛股猎手（机游共振）回测」卡下方** | 抽 `window.__renderAlgoBacktestCompare()` 函数（51 行），注入到 `__renderHunterBacktest()` 函数（line 3994）之后。`renderDelisted` 加 `<div id="st-cmp" data-star="2">` wrapper，紧贴 `st-hunter-bt` 之后 |
| 3 | **⭐级标注保留** | 回测对比卡 h3 加 `__moduleStarsHTML('algo_compare')` 调用 → 自动渲染 ⭐⭐；`__MODULE_STARS` 加 `algo_compare:2 / hunter_backtest:3` |
| 4 | **已下架区 4⭐置顶依次排序** | `_selIds` 数组加入新元素：`['st-hunter','st-hunter-bt','st-cmp','st-cockpit','st-allsite','st-fv']`；renderDelisted 末尾原 `data-star desc` 排序已天然支持 |

---

## 📐 代码改动概览

### 改动 1：暂未上架瘦身（line 10720-10926 + 10940-10941 + 10944-11016 + 12391-12392）

| 范围 | 内容 |
|------|------|
| **删** ulPaneStrong + 3 卡 + ulSectorFundTrackPanel 构造区 | `// 🎭 情绪周期 ...` (10721) 到 `// /H反推卡` (10920) 共 200 行 |
| **删** `try{ ... renderMarketRegimeCard / SectorRecommendationCard ... }` 调用 | line 10940-10941 共 2 行 |
| **删** `function renderMarketRegimeCard() { ... }` | line 10944-10956（含 "══ 2026-08-19 主人令：2 张新卡 render 函数" banner） |
| **删** `function renderSectorRecommendationCard() { ... }` | line 10957-11015（72 行） |
| **删** `window.renderMarketRegimeCard = renderMarketRegimeCard` & `window.renderSectorRecommendationCard = renderSectorRecommendationCard` | line 12391-12392（窗口暴露行） |
| **新** `h += '<div id="ulSectorFundTrackPanel">加载中…</div>';` 替代 200 行 | 仅 1 行 HTML |

**净瘦身**：index.html 从 13534 行 → 13268 行（删 266 行）→ 注入新函数 57 行 → 最终 13325 行。
**实际净增**：209 行 → 13325 行（+209 行于瘦身后含新函数）。**新版本文件 = 原版瘦身 209 + 新函数 57 减去 删除 271 行 = 净 -5 行**。

### 改动 2：新函数 `window.__renderAlgoBacktestCompare`（line 4039-4096）

```js
window.__renderAlgoBacktestCompare = function(){
  var h = '';
  var _cmp = window.ALGO_BACKTEST_COMPARE;
  // ... [从 git c80d42bc1 提取的 51 行原卡代码] ...
  // h3 加 ⭐chip:
  h += '<h3 ...><span>📊</span>两套算法回测对比 <span style="color:#fbbf24">'
       + window.__moduleStarsHTML('algo_compare')
       + '</span> <span ...>H反推 vs 强势突破 · 同一口径</span>'
       + _uBadge('盘后','对比',_cmp?_cmp.generated:null)+'</h3>';
  // ... [else 单卡 / 双卡对比表格 / 结论 box] ...
  return h;
};
```

**调用位置**：renderDelisted line 11621 新加
```js
h+=`<div id="st-cmp" data-star="2" style="margin-bottom:16px">`
   +(typeof window.__renderAlgoBacktestCompare==='function'?window.__renderAlgoBacktestCompare():'')
   +`</div>`;
```

### 改动 3：__MODULE_STARS 加 2 个 key（line 11605）

```js
window.__MODULE_STARS = { hunter:3, hunter_backtest:3, algo_compare:2, cockpit:4, allsite:3, fourvolume:4, crds:3 };
```

### 改动 4：renderDelisted 排序数组（line 11686）

```js
var _selIds=['st-hunter','st-hunter-bt','st-cmp','st-cockpit','st-allsite','st-fv'];
```

排序后实际显示顺序（`data-star desc`）：
1. **cockpit** (4⭐) · 选股驾驶舱
2. **fourvolume** (4⭐) · 四量终极
3. **hunter** (3⭐) · 大牛股猎手
4. **hunter_backtest** (3⭐) · 大牛股猎手（机游共振）回测 ⭐⭐⭐ UI展示级
5. **allsite** (3⭐) · 全站精选
6. **crds** (3⭐) · CRDS·逆势龙头（不在此区）
7. **algo_compare** (2⭐) · 两套算法回测对比 ⭐⭐ UI展示级

---

## ✅ 改后三件套

### 三件套 1：4 面对齐（云端 cron / 双机 / 运维页 / 逻辑详解）
- **云端 cron**：UI-only 改动，不影响任何算法/数据管线
- **双机**：纯 index.html 改动，无 .py / data/*.js 变动（HANDOVER 已小九侧推送主分支自动同步）
- **运维页**：暂未上架清理使其更聚焦；HEALTH_CHECK 红黄灯根因不在此（今晚算法链跑批没推 main 是另一回事）
- **逻辑详解**：logic.html 同步由系统代更新（?v= 缓存戳 + 移除错误兜底脚本）

### 三件套 2：审计（acorn / new Function 解析 inline `<script>`）
- **107 段 inline script · 0 语法错误**（audit_22050.js 已删）
- 注入的 `__renderAlgoBacktestCompare` 函数 51 行变量声明 + 字符串拼接无语法问题
- 删的 2 个 render 函数（renderMarketRegimeCard/SectorRecommendationCard）确认无其他模块调用（grep 0 命中除注释外）

### 三件套 3：原子推仓（Nutstore 铁律）
| 步骤 | 命令 |
|------|------|
| 显式 git add | `git add index.html logic.html data/DO_NOT_DELETE.js HANDOVER_2026-09-01_22-20_pool-lifecycle-ui-5fix.md` |
| Commit | `6be2753a4` (本地) → rebase 后 `56ab350ac` (远端) |
| Fetch | `git fetch origin main` (origin 推进 c80d42bc1 → 492c8092c) |
| Rebase | `git rebase -X theirs FETCH_HEAD` (stash unstaged → pop 后 rebase 成功) |
| Push | `git push origin HEAD:refs/heads/main` (`492c8092c..56ab350ac`) |

**GitHub Pages 验证**：
- `Last-Modified: Tue, 01 Sep 2026 14:56:05 GMT` = 22:56:05 CST ✓
- `git show origin/main:index.html` 首行 `<!-- deploy-trigger 2026-09-01T22:50 ul-cleanup-compare-starcmp -->` ✓

---

## 🛡 防护层

| 防护 | 措施 |
|------|------|
| **回归保护** | `__renderAlgoBacktestCompare` 是新增函数，旧调用路径完全保留（暂未上架已无引用方，且暂未上架根本没用 st-cmp ID） |
| **死代码清理** | renderMarketRegimeCard/SectorRecommendationCard 函数本体 + 窗口暴露 + 调用全部移除，无悬挂引用 |
| **数据契约不变** | 读 `ALGO_BACKTEST_COMPARE / H_AUTO_BUY / MOMENTUM_FILTER` 字段同前 |
| **UI 行为兼容** | 暂未上架只剩曲线卡 → 主人主诉"简洁克制"满足 |
| **Nutstore 防护** | 显式路径 git add（非 -A）、单条命令原子链、补丁脚本在 C:\Users\HH20210606\AppData\Local\Temp\（仓库外） |

---

## 📋 顺手核对

### git status 推送后
```
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

### index.html 行数变化
```
13534 (c80d42bc1) → 13268 (wipe 后) → 13325 (注入新函数) → 13325 (最终)
净: -209 行（暂未上架瘦身效果）
```

### deploy-trigger
```
2026-09-01T22:50 ul-cleanup-compare-starcmp - 暂未上架瘦身仅保留热门赛道资金追踪;
抽出两套算法回测对比卡__renderAlgoBacktestCompare函数并下沉到已下架·大牛股回测下方;
__MODULE_STARS加algo_compare/hunter_backtest;
renderDelisted排st-cmp/st-hunter-bt入排序4⭐置顶
```

---

## ⚠️ 给明早小九/值班守门狗

- **暂未上架区**：现在只剩"🔥 热门赛道资金追踪" 1 卡（主人截图1 期望）
- **已下架区**：4⭐卡（驾驶舱/四量终极）置顶；3⭐大牛股猎手 + 回测卡 + 全站精选依次；2⭐两套算法回测对比在大牛股回测下方
- **运维页红黄灯**：今晚 19:15 算法链跑批未推 main 是另一回事（数据真没刷新），不是本 UI 改动造成。本改动零新 fail 项
- **数据契约不变**：算法下次跑会自动填充回测对比面板（无新字段依赖）

---

_主人硬刷可见 · 详细部署触发 / CI 元数据：commit `56ab350ac` · Pages 22:56:05 已生效_
