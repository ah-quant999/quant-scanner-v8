# 交接件 · 2026-10-02 19:43 · 阿狸咪的工程师 · 三项齐卡排版修复（一行多列 + 统计行去重）

## 一句话
「主题空间·概念资金热度」卡三项齐层：修复 grid 嵌套导致的一行只 1 卡 → 恢复一行 6-7 列（minmax 150px / gap 6）；统计区「三项齐 N 只」三重重复文案整合为一行；删除卡片上方重复的红色口径标题行。

## 主人原始指令
- 「你这排版我也是服了！一行6-7列。」→ 卡片要一行多列排布
- 「这里（图2 圈统计区）重复的整合到一行」

## 根因（2 个）
1. **一行 1 卡**：昨晚重构时 `cards` 变量内部已是 grid 容器，外层 dst.innerHTML 又把整个 `cards` 包进第二个一模一样的 grid —— grid 嵌套 grid，内层被压成单列。
2. **文案重复**：统计区「三项齐 N 只」写了 2 遍（首行 + 「✅ 三项齐」行），卡片上方红色标题「（三项齐 · N 只 · 概念 + 业绩正向 + ROE≥10%）」是第 3 遍。

## 改动（仅 index.html 单文件，3 处，均在 `__renderThemeValue` 内）
| 位置 | 改前 | 改后 |
|---|---|---|
| cards 组装 | 红色口径标题行 + grid minmax(175px,1fr) gap 8 | 标题行删除；grid minmax(150px,1fr) gap 6 |
| 统计区 | 3 行（本主题…三项齐 N 只 / ✅三项齐 N 只·💰资金净流入 / 证据覆盖） | 2 行（本主题…·✅三项齐 N·💰资金净流入 N·概念板块·板块资金·均涨跌·资金最强 一行直出；证据覆盖行保留） |
| dst 输出 | `(cards ? <grid 包 cards> : 空态)` | `(cards ? cards : 空态)` ← 去嵌套（本 bug 核心） |

**未动**：三项齐过滤逻辑（∩ 业绩正向 ∩ ROE≥10）、每主题 40 只封顶、卡片内容结构、其他卡「基本面A档」。

## 验证链
- Node `new Function`：29 个 inline script 0 错
- 渲染桩测试 12/12 PASS（`E:/_alimi_tools/tmp_compare/tv_layout_test_1002b.js`：grid 多列容器/口径标题清零/「三项齐 N」全文仅 1 次/一行含 ✅+💰/卡片全出；翰宇药业缺 ROE 被正确过滤＝闸门有效）
- 离线门禁 `pre_deploy_audit.py`（工作树内权威版）：**14/14 全绿**
- 行尾：纯 LF（CRLF=0）
- 推送：Git Data API，parent=实时 tip `2ba6167ea`（v8 build 19:31），**force:false**，提交 `c3d4a00b1e`；回读远端 blob 与本地逐字节一致
- Pages 轮询：后台进行中（判据=线上含 `minmax(150px,1fr)` 且旧标题「（三项齐 · 」清零）

## 小九侧
无脚本/数据/workflow 变更，**无需任何动作**；纯前端 index.html 单文件排版修复。数据链（FUNDAMENTAL_QUALITY 等）与上轮一致。

## 工作树
`E:/_alimi_tools/v8_themevalue`（detach @2ba6167ea）排版验证完成后将 `git worktree remove --force` 清理。


---

## 追记 · 2026-10-02 20:0x · chip 拆双行（主人第二道截图令）
- **指令**：「第一行就7个固定，第二行金色描边的」→ 第一行固定 7 个长期主题种子，🔥金色热点独占第二行。
- **改动**：仅 __renderThemeValue chip 渲染：chips 单容器拆为 chipsSeed/chipsDyn 两个 flex 行（种子行 margin-bottom:8px，热点行 10px）；样式/交互/排行未动。
- **验证**：渲染桩 14/14 PASS（种子行恰 7 chip 不含热点、热点行不含长期主题；「医疗服务」含「医疗」被种子正确覆盖=关键词逻辑有效）+ 29 script 0 错 + 门禁 14/14 + 纯 LF。
- **推送**：9bb99979ed（parent=实时 tip 4a97d674b，force:false，回读一致）。
