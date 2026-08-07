# 阿狸咪 → 小九 交接（2026-08-07 夜间）

> 主人今晚 23:4x 指令：机游 + 北向席位 **7 日累计数据**、AI 报告解读 **规则模板（B 方案）**、北向资金/席位标签、以及「所有修复一步到位不留尾巴 + 23点备份任务加推仓防覆盖」。以下为已落地内容，小九 `git pull` 即可见。

## 一、本次改动（已推 origin/main，CI 构建 `2dfc911` 已上线）

### 1. 机游 + 北向席位 7 日累计数据
- 新增 `algorithms/gen_lhb_7d.py`：读 `raw_data/lhb_history.json` + 当日 `raw_data/lhb_data.json`（兜底当日），取最近 7 个有数据交易日聚合，输出 `raw_data/lhb_7d.json` 与 `data/LHB_7D.js`。
- 窗口当前 = `2026-07-28 ~ 2026-08-07`，去重 249 只股票；含 7日机游共振 TOP5、机构净买/净卖 TOP5、游资净买 TOP5、北向席位净买/净卖 TOP5，以及每日摘要。
- 挂入 `algorithms/run_algorithms.py` **step [2.6]**（在 `step_append_lhb_history` 之后），盘后算法链每日自动生成。
- `index.html` 已加载 `data/LHB_7D.js`，并在「机游共振日历」与「龙虎榜北向席位日历」两卡底部新增「**近7日累计**」TOP5 区。

### 2. AI 报告解读卡（B 方案 · 规则模板，不调 LLM）
- 替换原「需接入 LLM 服务」框架占位：基于 **危机雷达分数 + 涨停总数 + 连板高度 + 龙虎榜机游共振数** 自动拼接 100~200 字市场解读与操作建议。
- 标签显示「规则模板解读 · 未调用 LLM」，状态非「无数据」。

### 3. 北向资金 vs 北向席位硬标签（写入项目 `MEMORY.md`）
- **北向资金（NORTH_FUND.js）**：港交所 2024-05 后停披露 aggregate top_buy，**永久停更**。
- **龙虎榜北向席位**：沪深交易所每日龙虎榜席位明细（深股通/沪股通/外资券商席位），**仍每日披露**，数据在 `LHB_DATA.js`/`LHB_HISTORY.js` 的 `seats['北向']`。两者严禁再混淆。

### 4. 23点备份任务加「防覆盖推仓」
- `v8_backup.yml`（每日 21:00 CST 自动备份）新增 **「🛡️ 推送当天所有修改（防覆盖安全网）」** step：
  - `git add -u`（仅已跟踪文件改动）+ 备份包 → commit → push origin main。
  - 不扫入未跟踪的实验残留（如 `*.bak`、`threshold_consistency.py`、`algorithms/raw_data/`）。
  - `continue-on-error`，绝不阻断备份。

## 二、校验
- `_check_syntax.py`：23/23 通过
- `guard_index_js_tdz.py`：仅既有 1 处 `switchSec` hoisted 风险（历史遗留，非本次引入）
- 部署后 `origin/main:index.html` 已正确引用 `data/LHB_7D.js?v=20260807234429`，`data/LHB_7D.js` 已在部署仓存在

## 三、数据注意（交接小九）
- `raw_data/lhb_history.json` 中 **2026-08-07 当日条目 `trading:false, error`**（fetch_lhb 当晚失败），但 `raw_data/lhb_data.json` 有 8-07 数据，gen_lhb_7d 已用后者覆盖，7日窗口完整。
- **2026-08-04、08-05 两日 lhb_history 缺有效数据**（数据缺口），7日窗口自动跳过，不影响其余 7 日聚合。小九若需补全可重跑 `fetch_lhb` 对该两日。
- `update_v8.py::_rewrite_index_html_cache_busters()` 会在每次构建按 `LHB_7D.js` 的 `update_time` 自动刷新 `?v=`，次日算法链重生成后缓存戳自动更新，无需手动改 index.html。

## 四、本地残留（非本次任务，未提交，无影响）
- `algorithms/raw_data/`、`raw_data/sector_fund_flow_history.json.bak.before_merge`、`threshold_consistency.py` 为早前会话遗留未跟踪文件，未纳入本次提交，不影响站点。

---
**结论**：今晚所有修复均一步到位、无遗留尾巴；备份任务已加推仓安全网；本地与 origin/main 完全同步于 `7ed681a`。
