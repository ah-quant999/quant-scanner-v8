# 交接单 · 2026-09-15 · 四量追踪 + AI洞察实情解析 + 四项UI修正

- **发起**：小九的股票专家（小九机 / lemoncat-cn）
- **推送时间**：2026-09-15 **11:20 → 11:23**（休市前 10 分钟**错峰**执行，抢在 11:35 闸门 flush 与同事任务之前，避免同窗踩踏）
- **commit**：`6d4b2b170ed523ad628c75a5ea97ae105eda5976`（父 `22ffe6566cc9`，普通 push / force:false）
- **线上已生效**：`https://ah-quant999.github.io/quant-scanner-v8/`（实时抓取核验通过，见第 2 节）
- **本批含三块改动**（同一天内三条主人令，一次推送、一次核验）

---

## 1. 变更清单（9 项：4 改 + 2 增 + 3 删）

| 类型 | 路径 | 说明 |
|---|---|---|
| 改 | `index.html` | 974084 → 991718 字符（+17634）；四量 7 张子卡 + AI洞察卡重构迁移 + 四项 UI 修正 |
| 改 | `algorithms/update_v8.py` | 60453 → 61460；四量 DATA_SOURCES + CATEGORY_MAP(post_close)，并摘除 ai_insights 桥接映射 |
| 改 | `algorithms/v8_health_check.py` | 133418 → 134117；四量两卡登记 CARD_DEFS（max_age 1440 / picking=True） |
| 改 | `algorithms/run_algorithms.py` | 59726 → 60817；四量挂链（超时预算 900s + ORDER + STAGES[B] + 18:00 门控），摘除 ai_insights 脚本登记 |
| 增 | `algorithms/update_four_volume_history.py` | 12367 字符，逐日账本生产者 |
| 增 | `algorithms/gen_four_volume_track.py` | 17024 字符，跟踪/前向回测/告警/聚类生产者 |
| 删 | `scripts/fetch_ai_insights_compare.py` | 5646 字符，旧统计口径链下线（预状态守卫通过） |
| 删 | `data/AI_INSIGHTS_COMPARE.js` | 5318 字符，同上 |
| 删 | `raw_data/ai_insights_compare.json` | 5726 字符，同上 |

---

## 2. 核验结果（推后 40 项全绿 + 线上实测通过）

**推后核验（API 直读远端 `6d4b2b17`）**：40 项全 ✅，含
- 四量：`id="fvTrackBody"` / `id="fvHistory"` / `data/FOUR_VOLUME_TRACK.js` / `data/FOUR_VOLUME_HISTORY.js` / `window.renderFourVolumeExtra` / `update_four_volume_history.py: 900` / CARD_DEFS 登记 / 两个新文件已存在
- AI 洞察：`var M = window.MAHORO_INSIGHTS;` / `__renderAiInsightsCompare:ok` / 容器 `id="aiInsightsCompareBody"` 仅 1 次且落在 `obsPaneMacro` 内、K 型分层之前 / 旧链 5 个特征串零残留 / `update_v8.py` 已无映射 / `run_algorithms.py` 已无登记
- 三项删除在远端均返回 404
- UI 四项：`中线 · 回测` / `短线 · 实时` / `短线走弱不改中线窗口` / `仅短线机会` / `🔭 仅观测位置 …` / `_verdict='🟡 超卖·轻仓观测'` / `_verdict='🔴 高位·观测'` / 合并判定串 / `anoms=_nx;` 全部就位；`_warns.push('单日跌'` 与 `单日跌'+(` 双写法零残留；`破MA20`/`破MA60`/`📉 卖/减` 保留

**线上实测（HTTP 抓 Pages，硬证据）**：
| 项 | 结果 |
|---|---|
| 四量新卡 `id="fvTrackBody"` + `data/FOUR_VOLUME_TRACK.js` | ✅ |
| AI洞察新数据源 `var M = window.MAHORO_INSIGHTS;` | ✅ |
| 旧统计注入 `<script src="data/AI_INSIGHTS_COMPARE.js` | ✅ 已无（精确口径；粗搜仅剩 1 处**注释**留痕，属有意保留） |
| `id="aiInsightsCompareBody"` 落位三序 | ✅ `obsPaneMacro`(925892) < 容器(928128) < K型分层(928981) |
| UI 尺度标注 / 调和语 / 合并判定 / 位置提示免责注 | ✅ 全部在线 |
| UI 「单日跌」告警 | ✅ 已无 |

---

## 3. 三块改动说明

### ① 四量终极「自己的一整套系统」（主人令：「必须有自己的一整套系统，特别是历史追踪」）

- 两个新生产者：`update_four_volume_history.py`（按**信号日**建 key ⇒ 天然幂等；0 命中的扫描**不广播掉出**，避免假告警）+ `gen_four_volume_track.py`（T+N 按真实交易日轴推进，停牌跳档不填 0；未成熟档显式标注而非 0%）。
- 挂链三处**与三重共识完全同构、零特例**：`update_v8.py`（DATA_SOURCES + CATEGORY_MAP=post_close）、`v8_health_check.py`（CARD_DEFS 两卡，`picking=True` 必标——否则绕过 18:00 门控会在盘前派发整条盘后链 = 半日数据假产物）、`run_algorithms.py`（超时 900s + ORDER + STAGES[B] + STOCK_PICKING_SCRIPTS）。
- 前端：四量 tab 下方 7 张子卡（持仓盈亏跟踪 / 状态迁移告警 / 回测 N 日胜率 / 前向累积 / 板块聚类 / 选股池重叠度 / 入选历史）。
- ⚠️ 首日账本只有 1 个交易日，8 档前向样本需**逐日累积成熟**——近期看到「—」是正常，不是 bug。

### ② AI 洞察·多源观点对比卡：统计 → 实情解析 + 整卡迁移（主人令：改「实情解析」+ 移到核心/解析下方 + 整卡搬到宏观观测 K 型分层上方）

- **数据源换血**：由 `data/AI_INSIGHTS_COMPARE.js`（板块次数 / 句子极性统计）改为**直读 `window.MAHORO_INSIGHTS` 的 `compare` 段** —— 与「机构研究·AI 解析建议」**同源同稿**、随每日 07:15 出稿同步刷新。旧链路末端 19:20 才构建，会让卡滞后约一天半。
- **卡面重做**：删极性百分条 / 板块绝对次数条 /「字数」；新增一句话结论（紫底高亮）+ 日/周/月三段实情解析（每段 ①本段核心矛盾 ②与本段上次相比的边际变化 ③与更长周期的分歧/一致）+ 三段原文折叠 + 底部口径。
- **落位**：由「暂未上架·观测类」迁至「🌍 观测平台 > 🌍 宏观观测」，置于「🌍 宏观景气背景 · K 型分层」上方；派发名单从 `__ulRenderPane` 移入 `__obsRenderPane` 的 macro 分支（含退避重试）。
- **数据契约**（已写入每日 07:15 出稿任务 `30e1b099`）：
  `compare = { generated_at, basis, conclusion(80-140字), segments:{ daily|weekly|monthly : { tension, delta, align } } }`
  `delta` 必须与上一稿**逐段实证比对**得出至少 2 处具体变化；缺字段 ⇒ 卡面四处显示「实情解析待出稿」= 事故。
- **首稿已提前落地**：`data/maharo_insights.js` 13021 → 16748 字节（单行），经发布闸门 staging、11:35 flush 上线，**故本批推仓不含该文件**。

### ③ 四项 UI 修正（主人令 2026-09-15 下午，四条带图）

| # | 主人令原文 | 修法 |
|---|---|---|
| 1 | 「这两条可以合并成一行啊，流入在前，流出在后」 | 市场异动的「个股异动」两条（主力大单流入 / 流出）在**渲染层**合并为一行，流出段前保留红点区分方向。源头 `gen_market_brief.py` 仍产两条独立 anomaly（各带 signal 灯），**未改数据生成脚本** |
| 2 | 「这个你不觉得矛盾啊？」 | 顶部「仓位依据 ✅可开新仓（恐慌下行）」与「盘面观测 偏弱·今日偏弱，注意节奏」本是**两个尺度**（中线回测 regime / 短线实时信号），并列被读成自相矛盾。修法＝两行各标尺度 + 方向相反时补**可执行调和语**（可开+偏弱 → 分批布局、勿追高；不开+偏多 → 仅短线机会），**不删任何原始结论**；因子实验室「⚖ 择时闸门」横幅同源同问题**一并统一**（禁某模块特立独行） |
| 3 | 「把我平均股价 超卖超买那个金色提示指标写回去！」 | 恢复 2026-08 起的「位置观测」胶囊（🔴高位 / 🟠偏高 / 🟢偏低 / 🟡超卖 / ⏸中性），并**挂回免责注**「🔭 仅观测位置 · 开仓以 AI速览 ⚖ 裁决为准」——09-14 删除它的理由「与 AI速览 关口结论打架」由此不再成立（分工：AI速览裁决开仓，本胶囊只报位置） |
| 4 | 「再把这个第二行的 单日跌 删除」 | 删掉 `_warns` 里的「单日跌-x.x%」（日常波动，且与第一行涨跌幅、`_sigSell` 里已有的「单日暴跌」重复告警）；**「破MA20 / 破MA60」保留** |

**验证记录**：UI 补丁在「含 / 不含 ①② 两块补丁」两个基线上增量**逐字节相同**（+2868 字符 / +53 行）⇒ 与①②锚点互不干扰，任一失败都不影响另一块落地；HTML 审计（27 内联 script 语法零错 / script 注入清单完全不变 / div 329 前后 0 差 / 关键 id 次数不变）；**渲染 49 项断言全绿**（合并顺序含逆序输入与多条流入、尺度调和语四象限、位置提示五档与优先级、买卖并存时卖侧优先、「单日跌」双写法零残留、null/缺字段/空输入不崩）。

---

## 4. 数据链时序（本批生效后）

| 时间 | 环节 |
|---|---|
| 每日 07:15 | AI 出稿任务写 `MAHORO_INSIGHTS`（daily/weekly/monthly/**compare**）→ 发布闸门 → `data/maharo_insights.js` ⇒ 机构研究卡 + AI 洞察卡**同时**刷新 |
| 18:10 | B 批跑 `FOUR_VOLUME.js`（四量当日信号） |
| 18:10+ | `update_four_volume_history.py` 建账本（按信号日 key）→ `gen_four_volume_track.py` 出 track |
| 19:20 | `update_v8.py --category post_close` 构建 `data/*.js` ⇒ 前端可见四量新卡 |

---

## 5. 🔴 本机路径坑（09-15 新发现，阿狸咪若在本机操作也会踩）

本机 AI 解析真相源存在**两个拼写不同的文件、且两者都在被读写**：

| 文件 | 谁在读写 |
|---|---|
| `C:/Users/Administrator/.workbuddy/mah**a**ro_insights.json` | 每日出稿生成脚本近两日（09-14 `JSON_PATH` / 09-15 `JSONP`）实际落盘处 |
| `C:/Users/Administrator/.workbuddy/mah**o**ro_insights.json` | `maharo_daily_pull.py:30` 的 `INSIGHTS_PATH` 指向处 |

仓库真名是 `data/mah**a**ro_insights.js`（a 文件名）却声明 `window.MAH**O**RO_INSIGHTS`（o 变量名）。

**只写一份 ⇒ 另一份留旧值 ⇒ 下次读到旧 base ⇒ daily 静默回退**（09-14 已真实发生一次）。

**判据**：写盘**双写两 json** + 与仓库 js 取指纹**三方比对**；base 一律**先取远端 main 的 js**。已写入每日 07:15 任务 prompt 的「路径澄清」段。

---

## 6. 遗留待办

1. 四量账本首批仅 1 个交易日 → 8 档前向样本需逐日累积成熟。
2. IVF 注入修复仍 pending：`data/INDEX_VALUE_FRAMEWORK.js` 漏注入致「A股指数观测」4 列恒「—」（`tmp/pending_lunch/ivf_inject_loop.py` 已备）。
3. 因子卡 12 档待 E 批补满。

---

**落款：小九的股票专家**（2026-09-15 11:25）

---

## 7. 盘后兜底核验（15:35 自动化 · 2026-09-15）

> 本节由 15:35 盘后兜底自动化追加，**原文未作任何改动**（纯 append）。

**① 幂等推送脚本 `tmp/fv_push_loop.py`**

- 运行结果：第 1 轮即中止 —— `index.html: [ui] 打补丁异常 → [P1-仓位依据/盘面观测尺度分层] 起止锚点相距 2224 字符（>1500），疑似错位`
- 判读：**未推送任何内容**。该提示是「补丁已应用」的副产物 —— `ui_patch.py` 的 P1 锚点间距守卫（`max_gap=1500`）在**已打过补丁**的文件上必然触发（新块约 2.2 KB 插在起止锚点之间），
  属**脚本自身对已落地状态非幂等**，**不是线上异常**。故 15:35 未做任何写操作（符合「本批已于 11:20 落地」的事实）。
- 后续建议：给 `ui_patch.py` 的 5 个 STEP 各加一条「已应用」短路（若 `P*_NEW` 的关键串已在文本中则直接返回原文），即可恢复真正的幂等 no-op。

**② 远端逐项核验（GitHub API · main tip `18884e91f746` / head「v8 cn fetch: 2026-09-15 16:04」）**

| 分组 | 结论 |
|---|---|
| ① 四量终极（注入 + 子卡 id + 渲染函数） | ✅ 全过 |
| ② AI 洞察（新源 `window.MAHORO_INSIGHTS`、旧链路零残留、落位序 `obsPaneMacro` < 卡 < K 型分层） | ✅ 全过（`AI_INSIGHTS_COMPARE.js` 仅注释留痕） |
| ③ UI 四项（`中线 · 回测`/`短线 · 实时`/调和语/金色位置提示/条合并/`单日跌` 零残留，`破MA20·MA60` 保留） | ✅ 全过 |
| ④ 脚本侧（`update_v8.py` 映射已换、`v8_health_check.py` 含四量登记、`run_algorithms.py` 挂链） | ✅ 全过 |
| ⑤ 3 删除项 | ⚠️ 2/3 过：`scripts/fetch_ai_insights_compare.py`、`data/AI_INSIGHTS_COMPARE.js` 均 404；**`raw_data/ai_insights_compare.json` 已复活（见 ③）** |

**③ 唯一真实残留：`raw_data/ai_insights_compare.json` 于 11:22 被「v8 cn fetch」复活**

- 提交链：`6d4b2b170e`（11:21 本批删除）→ **`33b8db52b2`（2026-09-15T03:22:06Z = 11:22 CST「v8 cn fetch」重新加入）**
- 文件内容 `update_time=2026-09-15 04:45:50`（**早于删除时刻**）⇒ 属 runner 工作树里的**陈旧残留文件被 `git add` 回灌**，不是重新抓取（抓取脚本已删）。
- 影响：无引用（fetcher / 映射 / 前端注入三者均已下线），**功能无影响**，但违反「彻底清理」要求，且会持续被每日 cn fetch 提交带回。
- 处置建议（需下一写窗口）：① 再次删除该文件；② 同时清掉 **runner 工作树**（`D:/actions-runner-v8/_work/quant-scanner-v8/quant-scanner-v8/raw_data/ai_insights_compare.json`）的同名残留，否则会再次回灌。

**④ 线上 Pages 实时抓取（`index.html?t=<unix>`，HTTP 200 · 994742 字符，与 main 逐字节一致）**

- ① 四量新卡 `id="fvTrackBody"` + 双注入（`FOUR_VOLUME_TRACK.js` / `FOUR_VOLUME_HISTORY.js`）✅
- ② `var M = window.MAHORO_INSIGHTS;` ✅；`<script src="data/AI_INSIGHTS_COMPARE.js` 命中 **0 次** ✅
- ③ `id="aiInsightsCompareBody"` 出现 1 次，且 `obsPaneMacro(926387) < 卡(928623) < K 型分层(929476)` ✅
- ④ UI 四项串全部在线；`_warns.push('单日跌'` 不在线；`破MA20/破MA60` 在线 ✅

**⑤ 盘后数据链（本批新卡的产物状态）**

| 文件 | 状态 |
|---|---|
| `data/FOUR_VOLUME_TRACK.js` (884 B) | ⚠️ **占位**：`update_time 2026-09-15 12:05:00`，`signal_count/tracked_total/history_days` 全 0，alerts=「四量历史账本尚未建立（首次运行后自动累积）」 |
| `data/FOUR_VOLUME_HISTORY.js` (340 B) | ⚠️ **占位**：`_meta` 各计数 0 |
| `raw_data/four_volume_history.json` | ⚠️ 远端 **404** —— 账本真实产物尚未落仓 |
| `data/FOUR_VOLUME.js` | ✅ 6 只（`signal_date=2026-09-14`，`update_time 06:45:24`），**尚未入账** |
| `data/maharo_insights.js` | ✅ `compare` 段齐备（`generated_at` / `basis` / `conclusion` / `segments`） |

- **来源定性**：两文件由 **`97c7ac5553`（12:18 CST「解 P0 CI 门禁 404 断链（补四量占位）」）** 建立，**是刻意的占位补丁**（为让 CI 的「HTML 数据引用必须存在」闸门通过），**并非账本首次产出**。
- 时序说明：本次核验在 **16:1x CST** 进行，**当日 18:10 B 批（算法链）尚未运行** → 此刻为空壳属时序正常；18:10 后应由 `update_four_volume_history.py` 建账、`gen_four_volume_track.py` 出真数据。
- 复核点（18:10 后）：`raw_data/four_volume_history.json` 是否出现、`FOUR_VOLUME_TRACK.js` 的 `track_start/signal_count` 是否非 0、以及 06:45 那 6 只（signal_date 09-14）是否被正确入账。

**⑥ 跨会话同文件合并（`v8_health_check.py`）**

- ✅ 远端**同时**含本批四量登记 `{"id": "FOUR_VOLUME_TRACK", "name": "四量跟踪"` 与同事会话的 `_REG_ACTIVE_WINDOW` ⇒ 两批**互不覆盖、均已正确落地**（无需重推）。

**⑦ 本次核验结论**

本批 11:20 的推送**真实且完整在线**（三块改动 + 9 项文件变更均已生效，仅 1 项删除被 runner 残留回灌）；15:35 兜底**无需也不应重推**；遗留两项见第 6 节 + 本节 ③。
