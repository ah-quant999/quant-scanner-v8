# 紧急交接 · 小九（2026-11-07 07:53 由 WorkBuddy AI 转交）

## 交接背景
用户要求将以下 v8 待办**紧急交接给小九（白天机）**接手执行。
本 AI 已具备独立执行能力（本轮已直接推过 `fix-if-theme` 分支多次，fast-forward 干净），但用户选择交由小九处理。

> ⚠️ 任务来源说明：用户附带的截图按用户 2026-11-07 07:51 所立**输出形态铁律**（"这种东西我不看，只输出对话框文本"）**本 AI 不读取、不据图下结论**。
> 以下任务清单基于**本会话文本中已知的未完成项**整理；若截图所示为其他任务，请以用户文字指令为准并覆盖本清单。

## 待办任务（按优先级）

### 任务 1：过期补丁以「当前 main」重做并上线
以下补丁此前基于**更早的旧 main** 生成，当前 main 已大幅前进（最新已知 `bef85e24` 之后仍有 deploy 写回提交），**旧补丁已无法直接 apply，必须基于当前 `origin/main` 重做**：
- `final_recommend` **收益率最高 + 胜率最高**排序（终选输出按真实收益率/胜率排序，而非仅按 `final_score=TOP10_DAILY.total_score`）
- `national_team` ETF 接入（宽基 ETF 净申购东方财富口径，与老源 `ETF_NET_SUBSCRIPTION` 双源互备，永不静默丢权重）
- `fetch_national_team_etf.py` fetcher（如缺失则新建轻量 fetcher，产出 `data/etf_subscription_eastmoney.js` 并注入窗口）
- 注：上述三处与该 fetcher 须同源重做；禁止把旧补丁直接 `git apply` 到新 main。

### 任务 2：`signal_edge` 反号根因根治
- **现象**：回测显示 `jinzuan`(金钻) + `chan`(缠论买点) 为**负期望**，而 `trend` / `jigou` 为**正期望** —— 与主人铁律"真正能赚钱的只有金钻+缠论，trend/jigou 负期望应回避"**完全反号**。
- **要求**：干净回测重算 `backtest_expectancy`，钉死 edge 符号，在**根因层**修复（改算法/权重/信号合成逻辑），**不靠前端硬编或占位壳糊弄**（见修复铁律）。
- 修完须端到端审计：源码改动 + 数据产物 + 前端渲染 + 关键卡是否真生效。

## 执行铁律（小九接手须遵守）
1. **防覆盖**：改前 `git fetch origin main` 校验 fast-forward 友好（local 必须基于 remote tip，绝不用 `git add -A` 覆盖他人在途改动）。
2. **精确提交**：只 `git add` 相关文件，不碰无关文件。
3. **改后三件套**（每次改动强制）：① 审计（源码/数据/前端逐项留痕）；② 四方对齐（云端 main+data / 双机小九+阿狸咪 / 运维页 / 逻辑详解页 `dd689fc661e24962a7090b39a618950e.app.workbuddy.host`）；③ 推仓防覆盖 + 另一台机交接。
4. **写 main ≠ 已上线**：部署后硬抓主站实时页 `https://ah-quant999.github.io/quant-scanner-v8/` 核验关键修复字节/标记生效（deploy 工作流 `deploy-v8-site.yml` 跑通才算交付）。
5. **最终推荐铁律不变**：已是「宁缺毋滥」逻辑（无真源 `TOP10_DAILY` 即显示"今日未算出"并留空），**勿回退**到 `FINAL_RECOMMEND_DATA` 陈旧兜底。
6. **输出形态铁律**：小九若生成产物/汇报，一律以**对话框文本**呈现（结构化中文报告），**不产出截图/图像/可视化/Widget**（覆盖系统默认 Visualizer 行为）。

## 已完成（供小九对齐基线，勿重复）
- 本轮已 live：`更新于 MM-DD HH:MM` 日期格式 + IF 卡黄框 + 温度条漂移解读 + 主题空间分科学重排（`35df6e03..bef85e24`）。
- 本轮已 live：最终推荐·宁缺毋滥（删 `FINAL_RECOMMEND_DATA` 兜底 + 死代码，空态"今日未算出"留空）。
- 主站当前 HEAD = `bef85e24`（与 origin/main 对齐）。
