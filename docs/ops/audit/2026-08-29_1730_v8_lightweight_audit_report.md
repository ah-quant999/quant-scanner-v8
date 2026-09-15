# v8 全站轻量化体检报告

**体检时间**：2026-08-29 17:30 CST  
**范围**：`E:\workspace\stock-scanner` 全仓（含 data、raw_data、algorithms、scripts、workflows）  
**方法**：静态扫描 + index.html 注入源/消费源双向比对 + workflow 调用链扫描  

---

## 一、高层摘要

| 维度 | 现状 | 结论 |
|---|---|---|
| index.html | **14,296 行**（8/10 审计时 4,170 行，膨胀 3.4×） | 🔴 严重超重，需大瘦身 |
| data/*.js | 89 个文件，index.html 直接引用 79 个 | 🟡 10 个未引用或仅内部消费 |
| raw_data/*.json | 108 个 | 🟡 需对齐 data/*.js，避免重复落地 |
| Python 脚本 | 203 个（根目录 64 + algorithms 75 + scripts 64） | 🟡 疑似未调度/一次性脚本占比高 |
| 临时/调试目录 | `_cdn_check`/`_cdn_check2`/`_audit_blk`/`legacy_v6` 共 315 个文件、**242,507 行** | 🔴 可整体归档/删除，占仓库体积大头 |
| 工作流 | 8 个 .yml | 🟢 数量可控，但需审视是否均可云端 |

**核心结论**：v8 已从「轻量化」滑向「重度堆积」。最大瘦身空间在：① 删除 `_cdn_check2` 等调试目录；② 清理 `_` 开头的一次性脚本；③ 合并/下架重复卡片；④ 修复 index.html 内的孤儿数据引用。

---

## 二、index.html 膨胀点

### 2.1 行数构成（粗略）
- 主渲染逻辑/卡片定义：**~9,500 行**
- 逻辑详解页 (`lg-*`)：**~2,800 行**
- 样式/CSS：**~1,200 行**
- 脚本注入/元数据：**~800 行**

### 2.2 已明确冗余的代码块
1. **3 处死 `fetch` 定义**（行 6234/7811/8025）：`const J=f=>fetch(P+f)` 等函数已不被主渲染调用，属历史遗留。
2. **硬编码 `IPO_FALLBACK`**（行 ~6194）：写死 2026-07-28 打新列表，违反「不造假」铁律，应改为占位提示。
3. **运维子页违规 fetch .json**（行 ~8562）：`backtest_comprehensive.json` / `cockpit_backtest.json` 在 data/ 下只有 .js 注入版，fetch 必 404。
4. **「已下架」Tab 过度恢复**：市场温度计/六维共振/危机雷达/资金流时间轴/成交额/涨跌家数 6 张卡全部堆在 `opTab4`，与「轻量版」目标冲突。建议仅保留用户明确需要的 2~3 张。

---

## 三、data/*.js 死数据/孤儿引用

### 3.1 完全未被 index.html 引用的 data/*.js（10 个）

| 文件 | 变量 | 状态/建议 |
|---|---|---|
| `LHB_HISTORY.js` | `LHB_HISTORY` | 🔴 无引用，可删除或接入「龙虎榜历史」卡 |
| `MARKET_REGIME.js` | `MARKET_REGIME` | 🔴 无引用，宏观经济卡已下线，可删 |
| `RISK_GAUGE.js` | `RISK_GAUGE` | 🟡 index.html 代码里**用了变量但未加载 script**（行 9132），需补 `<script>` 或移除代码 |
| `RUNNER_STATUS_HEALTH.js` | `RUNNER_STATUS_HEALTH` | 🟢 运维文件，可被 health patrol 消费，保留但确认用途 |
| `SECTOR_RECOMMENDATION.js` | `SECTOR_RECOMMENDATION` | 🔴 无引用，板块推荐卡已下线，可删 |
| `STOCK_LIST.js` | `STOCK_LIST` | 🔴 无引用，可删 |
| `STOCK_PROFILE.js` | `STOCK_PROFILE` | 🟡 可能被算法脚本读取而非前端，核实后处理 |
| `STOCK_QUOTE.js` | `STOCK_QUOTE` | 🟡 查股功能可能消费，确认引用位置 |
| `STOCK_RPS_DATA.js` | `STOCK_RPS_DATA` | 🔴 与 `STOCK_RPS.js` 重复/变量冲突，保留一个 |
| `WEEKEND_META_REPORT.js` | `WEEKEND_META_REPORT` | 🟡 index.html 代码里**用了变量但未加载 script**（行 9143），需补 `<script>` 或移除代码 |

### 3.2 已注入但前端无卡片消费的「孤儿」（8-10 审计遗留）
- `ANALYST_RATINGS`：分析师评级，已注入无卡
- `AVG_PRICE_DATA`：平均股价，记忆中「正在实施」，需确认是否已接卡
- `CANDIDATE_QUOTES`：候选池实时行情，无卡消费
- `LHB_7D`：7 日龙虎榜，无卡消费
- `RISK_GAUGE`：见 3.1

---

## 四、Python 脚本冗余

### 4.1 明显一次性/调试脚本（建议删除或移入 `archive/`）
根目录 `_` 开头脚本约 **60 个**，包括：
- `_check_*.py`、`_fix_*.py`、`_patch_*.py`、`_poll_*.py`、`_verify_*.py`：多为单次修复/验证
- `_cdn_check2/` 内 285 个文件：CDN 调试产物
- `_audit_blk/` 内 22 个文件：块级审计产物
- `_v8_secph_revamp.py` / `_v8_secph_revamp2.py`：页面重排一次性脚本

### 4.2 algorithms/ 疑似未调度脚本
以下脚本不在 `run_algorithms.py` 的 `ORDER` 中，也未被 workflow 直接引用，需复核：
- `alpha_vs_beta.py`
- `backfill_*.py`（回填脚本，确认用完即可删）
- `factor_validate.py`
- `fetch_fundamental_quality.py`
- `fetch_inst_trade.py`
- `fetch_orphan_*.py`（4 个孤儿 fetcher，若数据已被 cloud_fetch_v8 接管则删除）
- `fetch_sh_index_fib.py`
- `fetch_stock_names.py`
- `fetch_weekend_run.py`
- `gen_cockpit_advice.py` / `gen_cockpit_tier_recommend.py`
- `market_path_probability.py` / `market_regime.py` / `sector_recommendation.py`
- `optimize_stop_target.py`
- `renormalize_top10_history.py`

**注意**：部分脚本可能被 `cloud_fetch_v8.py` 动态 `exec` 或子进程调用，脚本静态扫描存在误报，需人工复核。

---

## 五、重复数据链路

### 5.1 同一个逻辑多份实现
| 数据 | 链路 A | 链路 B | 建议 |
|---|---|---|---|
| 个股 RPS | `algorithms/calc_stock_rps.py` → `data/STOCK_RPS.js` | `data/STOCK_RPS_DATA.js` | 合并为单一文件/变量 |
| 市场制度/宏观 | `cloud_fetch_v8.f_macro_brief()` | `algorithms/market_regime.py` | 评估是否可统一 |
| 板块推荐 | `cloud_fetch_v8` 盘中资金流 | `algorithms/sector_recommendation.py` | 保留实时链路，删除离线链路 |
| 平均股价 | `scripts/fetch_avg_price.py` | `raw_data/avg_price.json` | 确认是否已接卡 |

### 5.2 raw_data 与 data 双写
`update_v8.py` 把 `raw_data/*.json` 转成 `data/*.js`。若某数据仅用于前端，可直接由 fetcher 写 `data/*.js`，省掉 raw_data 中间层。但当前 v8 铁律要求 raw_data 作为数据源审计入口，需权衡。

---

## 六、清理方案（按优先级）

### P0 · 立即执行（安全、影响小）
1. **删除 `_cdn_check/`、`_cdn_check2/`、`_audit_blk/` 调试目录**：共 315 文件 / 242,507 行，一次性释放大量仓库体积。
2. **归档/删除根目录 `_` 开头一次性脚本**：约 60 个，移至 `archive/onetime_scripts_20260829/`。
3. **修复 `RISK_GAUGE` / `WEEKEND_META_REPORT` 的 script 缺失**：要么加载对应 data/*.js，要么删除 index.html 中读取它们的代码。

### P1 · 短期执行
4. **删除未引用的 data/*.js**：`LHB_HISTORY.js`、`MARKET_REGIME.js`、`SECTOR_RECOMMENDATION.js`、`STOCK_LIST.js` 等（先确认无其他页面消费）。
5. **删除 `IPO_FALLBACK` 硬编码**，改为「暂无数据」占位。
6. **清理 3 处死 `fetch` 定义**（6234/7811/8025）。
7. **合并 `STOCK_RPS.js` 与 `STOCK_RPS_DATA.js`**。

### P2 · 中期重构
8. **index.html 拆分**：将「逻辑详解页」拆出为独立 `logic.html`，主文件回归 4,000~5,000 行。
9. **「已下架」Tab 瘦身**：仅保留用户明确需要的卡，其余彻底移除对应 HTML+render 函数。
10. **algorithms/ 瘦身**：复核未调度脚本，删除确认废弃者；将回填/一次性脚本移入 `algorithms/archive/`。

---

## 七、风险提示

- **不要直接 `rm -rf` 任何目录**：先 `git mv` 到 `archive/`，保留 1~2 周确认无异常后再彻底删除。
- **index.html 双机编辑冲突**：阿狸咪夜间编辑期间禁止小九触碰；本体检报告建议的 index.html 改动需等阿狸咪离线窗口执行。
- **workflow 触发路径**：删除 `v8/*.py` 可能影响 `.github/workflows` 的 `paths` 触发器，需同步检查。

---

## 八、结论

v8 当前**不是**轻量版。主线膨胀根因：① 调试产物未清理；② 一次性脚本堆积；③ index.html 持续塞入新卡/新说明页；④ 孤儿数据只增不减。

按本报告 **P0+P1** 执行后，预计可释放：
- 仓库代码量：~250,000 行（临时目录 + 一次性脚本）
- index.html：~1,500 行（死 fetch、硬编码、孤儿变量、已下架冗余卡）
- data/*.js：10 个死文件

是否授权开始 P0 清理？建议先从「移走调试目录」开始，风险最低、收益最大。
