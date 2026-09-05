# 九宝量化 v8.0 - 禁止删除清单

**最后更新**: 2026-08-01 22:42
**维护人**: HH + AI助手
**用途**: 防止误删核心资产，每次项目瘦身/清理前必须核对此清单
**继承自**: v6 DO_NOT_DELETE.md（已验证 v6 2026-07-25 版本）

---

## 🔴 核心页面

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `index.html` | 主站单页面（全站 UI + 数据注入 + 逻辑详解） | 唯一入口，432KB，全站核心 |
| `calendar.html` | 共振日历月历视图 | index.html 内链跳转目标 |
| `v6_memo.html` | v6 遗留参考页（逻辑详解页「📦 v6备忘录」子tab 经 iframe 引用） | 迁移过渡期保留 + 主人 2026-08-15 令：永久防覆盖 |
| `v6_memo.golden.html` | `v6_memo.html` 的**黄金备份**（guard_v6_memo.py 自愈源） | 防覆盖二道防线，禁止删除，否则自愈失效 |
| `guard_v6_memo.py` | v6备忘录 防覆盖护栏（完整性自检 + git/黄金备份自愈 + iframe 缓存击穿） | 部署闸门，禁止删除 |

## 🔴 v6备忘录 防覆盖铁律（2026-08-15 主人令）

> ★ **2026-08-15 主人二次确认：永久禁止删除** — `v6_memo.html` / `v6_memo.golden.html` / `guard_v6_memo.py` 为 v8 逻辑详解页核心资产，**任何清理 / 重构 / 瘦身 / AI 自动化操作均不得删除或覆盖**；pre-commit hook 已拦截其 git 删除，违者阻断提交与部署。

> **逻辑详解页「📦 v6备忘录」子 tab 经 `<iframe src="v6_memo.html?v=<sha10>">` 加载，是 v6→v8 迁移唯一保留的算法逻辑详解参考页。**
> 历史上曾因"V6 覆盖 v8" + CDN 按完整 URL 缓存旧/截断副本，导致它看似"没了"。
> 永久防护（三重）：
> 1. **完整性自愈**：`guard_v6_memo.py` 在每次部署前运行，若 `v6_memo.html` 缺失/截断（<60KB），自动从 git HEAD → `v6_memo.golden.html` 还原。
> 2. **入口守护**：index.html 必须保留 `data-lg="v6"` 子tab + `id="lg-v6"` 面板 + iframe 引用，缺失即 FAIL 部署（阻断丢失态上线）。
> 3. **缓存击穿**：iframe `src` 强制带 `?v=<内容sha10>`（与全站 data/*.js 同口径，用内容 sha 非 mtime），内容变化即换 key，CDN 必重拉，杜绝旧副本复发。
>
> **任何清理/重构/瘦身任务（含 v8_cleanup / cloud_weekly_cleanup / 手动）均不得删除 `v6_memo.html` / `v6_memo.golden.html` / `guard_v6_memo.py`，也不得移除 index.html 中的 v6 备忘录入口。**

## 🔴 v6 历史备份（本地 · 保留中 · 禁止删除）

> ⚠️ **2026-08-07 主人令**：v6 历史备份在 v8 连续稳定运行满一周且主人明确确认前，**禁止任何清理/备份任务删除**。
> 删除前必须征求主人同意（下周末再确认）。涉及文件位于 `/e/workspace`，不在本仓库内：

| 文件路径/模式 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `九宝量化v6.0_*.tar.gz` | v6 完整仓库归档备份 | 迁移过渡期保留，待 v8 稳定一周 + 主人确认后方可清理 |
| `shared/九宝量化v6.0_*` | v6 逻辑详解页/历史追踪页/交接总览 | 同上 |
| `/e/workspace/stock-scanner/backup_2026*` | v6 时代每日增量备份 | 同上 |

**注意**：上述文件为 v6 时代遗留，v8 运行时已不依赖。但主人明确要求保留至 v8 稳定一周后确认，任何自动化清理（云端 weekly_cleanup / v8_backup / v8_cleanup 及本地脚本）均不得触碰。

## 🔴 核心数据文件 (data/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `data/*.js` (全部 48 个) | 前端数据注入层（window.X = {...}） | 全部由 update_v8.py 从 raw_data 构建，index.html 动态引用 |
| `data/STOCK_LIST.js` | 5202 只股票代码+名称+拼音首字母 | 个股查询唯一数据源，含 py 字段（_gen_pinyin.py 生成） |
| `data/LHB_HISTORY.js` | 龙虎榜历史数据（最大文件 1.3MB） | 共振日历数据源 |

**注意**: `data/` 下所有 `.js` 文件都是前端运行时依赖，**禁止批量删除**。`data/freshness_status.json` 由体检 workflow 自动生成。
| `data/DO_NOT_DELETE.js` | 禁止删除清单的视图（window.DO_NOT_DELETE_HTML + UPDATED 注入）；由 `scripts/gen_do_not_delete_js.py` 从 `DO_NOT_DELETE.md` 解析；sha10 缓存戳已回写 index.html | 逻辑详解页「🛡️ 防删」子页 100% 依赖；删除即子页回到「加载中…」 |

> 🟢 **豁免清单（DO_NOT_DELETE.md 为唯一裁判，pre-commit hook 读取本区块内含「豁免」二字的行、放行其中反引号包裹的路径删除）**：
> 🟢 豁免 `data/POTENTIAL_PICKS.js` + `raw_data/potential_picks.json`：潜力挖掘页已删，孤儿产物，全站0引用，允许删除（2026-08-20 主人令）。
> 🟢 豁免 `data/BLOAT_CHECK.js`：v8_bloat_check.py 已停生成（产物迁 .workbuddy/v8_bloat_report.json），全站0引用，允许删除（2026-08-29 轻量化收尾）。
> 🟢 豁免 `data/DELISTED_STOCKS.js`：renderDelisted 已改读 raw_data/delisted_stocks.json，update_v8.py 已移除映射，全站0引用，允许删除（2026-08-29 轻量化收尾）。
> 🟢 豁免 `data/MAHORO.js` + `algorithms/fetch_maharo_signals.py` + `.github/workflows/mahoro_refresh.yml` + `scripts/monitor_maharo_refresh.py`：mahoro 全链路引用/监控已移除（commit 7193a5b93），功能上等同删除，全站0引用，允许物理删除（2026-08-29 主人令：mahoro 孤儿清理）。
> 🟢 豁免 `raw_data/kline_cache/*` + `raw_data/backtest_kline_cache/*` + `raw_data/_rps_cache/*` + `raw_data/_tdx_cache/*`：算法运行时行情缓存（RPS / K线 / TDX / 回测K线），纯本地加速用、可随时重建，`.gitignore` 已忽略（严禁入库）。2026-08-29 仓库瘦身：`git rm --cached` 移出版本跟踪，**本地文件全部保留**，仅删除库内副本，不删本地缓存、不影响任何算法运行。本条为通配符豁免，避免 `raw_data/*.json` 保护规则（其 `*` 跨 `/`）误伤缓存子目录。

---

## 🔴 核心原始数据 (raw_data/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `raw_data/*.json` (全部 45 个) | 数据抓取原始 JSON | data/*.js 的上游源，update_v8.py 构建输入 |

**注意**: `raw_data/` 由 cn runner 的 cloud_fetch_v8.py / algorithms/run_algorithms.py 产出，经 api_push_raw.py 推送。云端 weekly_cleanup 会清理 orphan，但不会删有映射的文件。

**2026-08-29 Tier 1/2 升级新增 raw_data 产物**（下游消费 + freshness_sla 监控）：
| `raw_data/ic_gate.json` | IC 门禁 MVP 每日产物（策略 gate 信号 + ic_weight） | algorithms/generate_top10.py:614 下游消费；也供 gen_triple_consensus/calc_crds 准出门禁 |
| `raw_data/strategy_regime_gate.json` | regime 每日门禁（按主人在 2026-08-19 利率上行期框架给各策略 weight） | 下游选股脚本 compute × weight |
| `raw_data/avg_price.json` | 平均股价（通达信 880003）每日最新值 + 5 日历史 | 由 `scripts/fetch_avg_price.py` 产出；UI 评估后再接驾驶舱/暂未上架页 |
| `raw_data/etf_subscription_em.json` | ETF 申购赎回东方财富分类聚合（5 类 + 亿元） | 替换旧 `data/ETF_SUBSCRIPTION.js` 宽基+亿份口径；旧文件记录在豁免段 |
| `raw_data/freshness_sla.json` | 新鲜度 SLA 体检输出（最近 13 个核心 raw_data 文件的 update_time 状态） | `scripts/freshness_sla.py` 产出；挂 `v8_algo.yml 17:00` |

**🛡 2026-09-06 主人令：RPS 相对强度「30 天样本考核」保护段（前端入口已下线，数据链必须保留到考核出结果）**

> ⚠️ **背景**：相对强度（RPS）选股策略子 tab 已于 2026-09-03 轻量化下线（`renderRpsScreen` 已删、`__MODULE_STARS` 已移除 rps），但主人 2026-09-06 拍板：**数据链保留，按「因子实验室同款标准」跑 30 个交易日样本考核再定去留**。前端无展示 → 极易被当作"无人消费的孤儿"误删，特立此段防遗忘/防误删。
>
> **考核标准（与因子实验室同口径）**：自 2026-09-05 起满 **30 个交易日**（约 2026-10-中），若 `raw_data/rps_backtest.json` 的 **A 档 T+1 胜率 ≥55% 且 T+5/T+10 平均收益为正** → 再谈恢复选股策略子 tab 甚至进评分权重；**不达标 → 彻底降级为「个股详情命中行」展示层，策略页永不恢复**。
>
> **考核期内禁止删除的文件链**：
> | 文件 | 角色 | 产出方 |
> |---|---|---|
> | `v8/backtest_rps.py` | 回测引擎（读日归档 → rps_backtest.json） | 已挂算法链 E 批（2026-09-06） |
> | `raw_data/rps_backtest.json` | 考核核心产物（A档 T+1/3/5/10/20 胜率收益） | `v8/backtest_rps.py`（E 批每日刷新） |
> | `raw_data/history/stock_rps_*.json` | 每日 RPS 快照归档（回测的输入源，删了考核直接报废） | `algorithms/calc_stock_rps.py:668` |
> | `raw_data/stock_rps.json` + `data/STOCK_RPS.js` | 当日 RPS 截面（详情命中行消费） | `calc_stock_rps.py`（B 批） |
> | `data/RPS_BACKTEST.js` | 回测 JS 产物（update_v8 已加映射防孤儿清理，前端暂不注入属正常） | `update_v8.py` |
> | `algorithms/calc_stock_rps.py` 的 history 归档逻辑（:668） | 日归档开关 | 算法链 B 批 |
>
> **防孤儿双保险**：① `update_v8.py` DATA_SOURCES 已加 `"rps_backtest.json": "RPS_BACKTEST"` 映射（weekly_cleanup 有映射不删）；② 本清单 pre-commit 拦截 `raw_data/*.json` 删除。**任何轻量化/瘦身/清理操作不得删除上表文件**。

---

## 🟠 核心脚本 (根目录 *.py)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `cloud_fetch_v8.py` | 中国数据抓取总入口（akshare/东财） | v8_cn_fetch.yml 唯一抓取入口 |
| `api_push_raw.py` | raw_data → GitHub API 推送 | 所有 cn runner 工作流的推送通道 |
| `update_v8.py` | raw_data → data/*.js 选择性构建 | v8_build_deploy.yml 唯一构建入口 |
| `deploy_v8.py` | 本地 SSH 强制部署脚本 | 本机部署入口（git push main → Pages） |
| `guard_v8_freshness.py` | 46 模块新鲜度守卫 | v8_algo / cloud_weekly_cleanup 调用 |
| `guard_v8.py` | 站点健康检查 | 手动诊断工具 |
| `sync_v6_to_v8.py` | v6→v8 数据同步桥（应急） | v8_sync_v6_data.yml 调用 |
| `backfill_lhb_history.py` | LHB 历史回填生成器 | post_close 时段自动跑 |
| `fetch_ipo_data_v8.py` | IPO/打新数据抓取 | premarket 时段调用 |
| `fetch_limit_up_heatmap_v8.py` | 涨停热力矩阵抓取 | intraday 时段调用 |
| `_gen_pinyin.py` | STOCK_LIST.js 拼音首字母生成器 | 重生成 STOCK_LIST 时必须重跑补 py 字段 |
| `split_inline_data.py` | index.html 内联数据拆分工具 | 维护工具 |

**注意**: 根目录下所有 `*.py` 脚本都是核心管线组件，**禁止批量删除**。

---

## 🟠 应用层脚本 (scripts/) — 2026-08-29 Tier 1/2 升级新增

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `scripts/gen_do_not_delete_js.py` | `DO_NOT_DELETE.md` → `data/DO_NOT_DELETE.js` 渲染器（轻量 md 转 HTML、disk_sha 一致性缓存戳回写 index.html） | 逻辑详解页「🛡️ 防删」子页注入源；周日 `v8_cleanup.yml` 末尾固定步骤 |
| `scripts/apply_ic_gate.py` | **Tier 1 第 1 步**：IC 门禁 MVP。读 factor_ic_report + factor_validate + h_auto_buy 累计胜率 → `raw_data/ic_gate.json` | 回测投入→选股质量变现的引擎；下游 generate_top10 / gen_triple_consensus / calc_crds 接入 |
| `scripts/apply_regime_gate.py` | **Tier 1 第 2 步**：regime 自动门控。读 market_regime → `raw_data/strategy_regime_gate.json`（按利率上行/下行/平稳给各策略 weight） | regime 已算但未自动化→选股；按市道 gate 是 backtest_tdx 已发现差异的唯一免费 alpha |
| `scripts/fetch_avg_price.py` | **新功能**：平均股价（通达信 880003）轻量 fetcher；东方财富 push2his | 主人 2026-08-29 周报期待；UI 评估后再接驾驶舱/暂未上架页 |
| `scripts/fetch_etf_subscription_em.py` | **新功能**：ETF 申购赎回东方财富口径 fetcher（旧文件切到 5 类 + 亿元） | 主人 2026-08-29 新需求；旧 ETF_SUBSCRIPTION.js 宽基+亿份与东方财富分类不一致 |
| `scripts/freshness_sla.py` | **Tier 1 第 3 步**：新鲜度 SLA 自动标红 + 告警。扫 raw_data/*.json update_time，缺数据/超时按 FRESHNESS_SLA 表拦截 | 主人 2026-08-29 反馈「图 14 卡在 8-04 没人告警」根因；挂 `v8_algo.yml 17:00` |

**注意**: 上述 6 个脚本均 `py_compile` 0 错；fetcher（avg_price / etf_subscription_em）云端首次跑批时验证真实接口（本机可能因网络限制跑不通）。

---

## 🟠 算法脚本 (algorithms/)

| 目录/文件 | 内容描述 | 禁止删除原因 |
|-----------|---------|------------|
| `algorithms/run_algorithms.py` | 盘后算法链总控 | v8_algo_run.yml 唯一入口 |
| `algorithms/*.py` (全部 22 个) | 选股/回测/龙虎榜/波动率等算法 | 算法链依赖，缺失则对应卡片冻结 |
| `algorithms/stage_to_raw.py` | 算法输出 → raw_data 格式转换 | run_algorithms.py 调用 |

**注意**: `algorithms/data/` 和 `algorithms/out/` 已在 .gitignore 中，可随时重建。

---

## 🟢 GitHub Actions 工作流 (.github/workflows/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `v8_cn_fetch.yml` | 中国数据抓取（cn runner，7个 cron + dispatch） | **唯一数据源工作流**，丢失则全站不更新 |
| `v8_algo_run.yml` | 盘后算法链（cn runner，18:30） | **唯一算法工作流** |
| `v8_build_deploy.yml` | 构建+部署（ubuntu，push 触发） | **唯一部署工作流** |
| `v8_algo.yml` | 每日数据体检（ubuntu，09:00/17:00） | 新鲜度监控 |
| `v8_safety_net.yml` | Safety Net 兜底监控（ubuntu，工作日每30min） | **P0 保险**：cn 断线自动补跑 |
| `v8_self_heal.yml` | 云端自愈器（ubuntu，周六14:00） | **P1 自愈**：周末检测陈旧模块并补跑 |
| `cloud_weekly_cleanup.yml` | 每周清理（ubuntu，周六21:00） | orphan 清理 + 新鲜度体检 |
| `v8_cleanup.yml` | 周日清理（ubuntu，23:00） | 缓存/日志修剪 |
| `v8_sync_v6_data.yml` | v6→v8 应急同步（仅 dispatch） | 应急工具，无定时 |

**注意**: **9 个 yml 缺一不可**。丢失任何一个都会导致对应能力永久失效。特别是 `v8_cn_fetch.yml` 和 `v8_build_deploy.yml` 是整站的「呼吸」和「心跳」。

---

## 🟢 配置和文档

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `.gitignore` | Git 忽略规则 | 保护临时文件不被入库 |
| `.gitattributes` | 换行符规范（LF） | 防止 Windows CRLF 导致 ubuntu runner bash 报错 |
| `README.md` | 项目说明 | 仓库门面 |
| `V8_PRINCIPLES.md` | v8 设计原则文档 | 架构决策记录 |
| `DO_NOT_DELETE.md` (本文件) | 禁止删除清单 | 防误删核心文档 |
| `HANDOVER_LOG.jsonl` | 双机交接索引日志 | 自动化读取最新交接的依据 |
| `docs/ops/handover/HANDOVER*.md` | 双机交接文档归档 | 小九↔阿狸咪协作记录 |
| `docs/ops/urgent/URGENT*.md` | 紧急指令文档归档 | 夜间/周末紧急问题记录 |
| `docs/ops/audit/AUDIT*.md` | 审计报告归档 | 全站/算法审计结论 |
| `docs/ops/scripts/_*.py` | 临时检查/调试脚本归档 | 非核心管线，仅备查 |
| `docs/ops/archive/*.zip` | 历史打包归档 | 临时产物/探针日志归档 |
| `docs/ops/notes/*.md` | 临时解读/备注归档 | 宏观事件等一次性备注 |

---

## ⚪ 可清理文件/目录（超过N天可删除）

| 文件路径/模式 | 可删除条件 | 注意事项 |
|------------|-----------|---------|
| `__pycache__/` | 随时可删 | Python 字节码缓存，自动重建 |
| `algorithms/__pycache__/` | 随时可删 | 同上 |
| `out/` | 随时可删 | 算法中间产物，run_algorithms.py 重建 |
| `_tmp_*/` | 随时可删 | 临时切片目录 |
| `*.log` / `*.err` | 随时可删 | 空日志文件 |
| `_check_scripts.js` | 随时可删 | 一次性语法校验脚本 |

**清理前必须**:
1. 核对本清单，确认不在禁止删除列表中
2. 确认文件不以 `data/`、`raw_data/`、`.github/`、`algorithms/` 开头
3. 如有疑问，先询问再删除

---

## 📝 历史误删记录（教训）

| 日期 | 误删文件 | 原因 | 恢复方法 |
|-----|---------|------|---------|
| （暂无） | — | — | — |

**教训**: v6 曾于 2026-07-03 误删 `data/sh_sz_history.json`（瘦身时清空），从 git 历史恢复。v8 从一开始就建立此清单，避免重蹈覆辙。

---

## 🔄 维护说明

- **本文件必须持续维护**: 每次新增核心文件/目录，必须同步更新此清单
- **清理前必须核对**: 每次 cleanup / 瘦身，必须先读此清单
- **pre-commit hook 已安装**: 删除本清单内文件时 git commit 会自动拦截（exit 1）
- **定期审查**: 每周审查一次，确保清单完整性

---

**最后核对**: 2026-08-08 (v6 备份保留策略已纳入 / 运营文档归档至 docs/ops/) ✅
**下次审查**: 2026-08-15 (每周审查)

---

## 🔴 防覆盖指南（2026-08-29 主人紧急令 — 抵制坚果云 Nutstore 实时同步回退）

> ⚠️ **痛点**：主人本机 `E:\workspace\stock-scanner\` 被**坚果云 Nutstore（NutstoreClient.exe）实时同步**（实测 2~10 秒一轮）。所有本机用 Edit 工具或 Write 工具做的改动，**会在数秒内被云端版本回退覆盖**，除非已 `git commit` 入本地 HEAD。
>
> 实测现象（2026-08-29 多轮确认）：
> - Edit 写好后 `grep` 还在，下一秒再 grep = 没了；`git diff --stat` 瞬间变 clean。
> - `git diff --cached` 显示 staged 还在，working tree 被云覆盖；`git status -s` 出现 100+ 条 `D ` 状态（云工作树被 revert 到某个老态）。
> - 主人另一席位（`C:\Users\Administrator\qs8-tmp`，双机分时铁律的副机）能自助 commit + push origin，导致本地看似「原地提交」。
>
> **铁律（本机操作 v8 必读）**：
>
> 1. **必须 `git commit` 入本地 HEAD 才能保证改动留存**；未 commit 的改动会被云覆盖。
> 2. **Push 要谨慎**：`git push origin main` 前 `git fetch origin main` + `git rebase origin/main`，确认无冲突再推。pre-push hook 已支持自动 rebase。
> 3. **临时文件不要放在仓库根**（Nutstore 把 `__*`/`.tmp`/`.bak` 当 temp 清；本机已观察到此类文件数分钟内被删）。放 `C:\Users\HH20210606\.workbuddy\tmp\`（用户级 tmp，**不在同步区**）。
> 4. **大文件 commit 后 `git status -s` 出现大批 `D ` 状态 = Nutstore 工作树污染，不是真实删除**。不要 `git checkout HEAD -- .`，会冲掉主人本地未保存工作；用 `git show origin/main:<file>` 验证文件远端仍存在。
> 5. **优先使用 `node -e` / `python -c` 原子写入 + 立即 commit**，比 Edit/Write 工具更可靠（不会被工具回调重新读覆盖）。
> 6. **跨机同步冲突**：`tmp_debug.py` / `stash@{0}` / `.git/index.lock` 等临时残留若另一机在跑同步脚，**主人不要 `pop`/`drop`**，需联系小九确认。
>
> **自动化解套路径**（已落地）：
> - `git push` 时 pre-push hook 检测 origin 前进则自动 rebase：若工作树脏，先 `git stash push -u` 再 rebase。
> - 本地 `init.bat`/脚本若被云回退，可用 `git reset --hard origin/main` 一键对齐（仅在用户明确放行时执行）。
> - `stash@{0}`（最近一次工作树备份）+ `stash@{1}`（前一次 Nutstore 噪音 stash）随时可 `git stash list` 检视。

---

## 🟢 豁免白名单（主人 2026-08-30 令 · TOP5 滚动跟踪彻底下线）

> 🟢 豁免 `data/TOP5_TRACK.js`：TOP5 滚动跟踪样本<30 长期空表，主人 2026-08-30 令彻底删除（A 方案），随孤儿脚本一并移除，无前端/下游依赖。
> 🟢 豁免 `algorithms/gen_top5_track.py`：随 TOP5_TRACK 数据一并删除的孤儿算法脚本，run_algorithms.py 已移除其调度，无任何前端/下游依赖。

> 🟢 豁免 `data/RPS_BACKTEST.js`：RPS 相对强度选股层已按主人令（2026-09-05）从选股策略子页全方位下线，data/RPS_BACKTEST.js 全站0引用，允许删除（2026-09-05 轻量化收尾）。
> 🟢 豁免 `raw_data/backtest_h_vs_momentum.json`：老动量 vs H反推回测残留，已归档，全站0引用，允许删除（2026-09-05 轻量化收尾）。
> 🟢 豁免 `raw_data/hunter_backtest.json`：大牛股猎手回测残留，已按主人令（2026-09-03）下线，全站0引用，允许删除（2026-09-05 轻量化收尾）。
