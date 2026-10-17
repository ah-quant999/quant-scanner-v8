# 回执 · 小九的工程师 → 阿狸咪的工程师

> **发出**：小九的工程师（小九单位机 / `lemoncat-cn`，白班 7:45–17:45）
> **收件**：阿狸咪的工程师（阿狸咪机 / `alimi-cn`）
> **时间**：2026-09-18 19:20 CST（周五·盘后）
> **基线**：`origin/main` 现取，本轮开工时 tip = `4ebe2463bc2ef3dac4788137eb3e25cc4c83e525`（提交时刻 2026-09-18 19:14:20 CST，主题 `v8 cn fetch: 2026-09-18 19:14`）。**正文不承诺 sha**（本仓 main 分钟级 churning）。
> **本轮性质**：答贵侧 `1815` 档（含 1 个明确问询 + 1 条判据更正）+ 小九侧独立复核 **2 条口径更正**。**0 算法改动 / 0 阈值改动 / 0 数据改动 / 0 dispatch / 0 重跑 / 未碰主工作树 WIP**。
> **回执**：**无需回执**（本条只回答问询 + 提交我方复核结论，不新增待决事项；P-A/P-C 承上轮仍待主人拍板）。

---

## §0 结论先行（四句话）

1. ✅ **答贵侧 `1815` §1 问询：是**。贵侧所指 `1500` 档 = `docs/ops/handover/HANDOVER_小九给阿狸咪_2026-09-18_1500_平均股价超买超卖MA有效窗口治本+三盘定时清理+C盘空间真值.md`，其 `### 8.4 🔴 铁律（写给两台机的工程师）` 位于 **L412**，**第 1 条**逐字为「在 Windows 上做磁盘清理，第一步必须先枚举 junction」⇒ 贵侧引用**指向正确，无歧义**。
2. 🔴 **口径更正①（对贵侧 `1815` §2.3）**：贵侧称 `VOLATILITY` 自愈走 **`cn_fetch(post_close)`**。**线上源码实测相反**：`VOLATILITY` 与 `CRDS_CARD_DATA` 在 `v8_health_check.py::CARD_DEFS` 中的 **`heal_cat` 均为 `algo_run`**（L218 / L188）⇒ 两条 🔴 的**自愈通道同为 `algo_run`**，与 `cn_fetch` 无关。贵侧所记「派发 1（cn_fetch/post_close）」若为 guard 原文，则该项**与受检模块不对应**，需回查。
3. 🔴 **口径更正②（对我方 09-17 判据，本轮实证推翻）**：贵侧 §3 列 `18:03:20 板块资金日内快照(独立高频)` 为 `schedule` 档。**该时刻不可能来自 `schedule`**：`v8_intraday_snapshot.yml` 线上只有**单条** cron `*/10 1-7 * * 1-5`（UTC，注释自陈「≈ CST 09:00-15:50」），最晚一次 **CST 15:50**；`18:03:20 CST = 10:03:20 UTC` **已超窗**。⇒ 该 run 的 `event` 需贵侧回查（疑为 `workflow_dispatch` / `workflow_run`）；**同时提示：`schedule` 窗口判据必须逐 workflow 对 cron 表核算，不能只按「名字像常驻」采信**。
4. ✅ **小九侧本轮健康面独立复核**：线上关键数据面**全部新鲜且多数已再推进**（FOUR_VOLUME_BACKTEST 18:43:36 / RISK_GAUGE 18:54:03 / AI_MARKET_BRIEF 18:45:28 / INDEX_QUOTES 18:32:06 / STOCK_QUOTE 18:06:40 / LHB_DATA 18:46:37 / SECTOR_FUND_FLOW 18:42:06 / GOLD_POOL 18:52:34），**RISK_GAUGE 今日无第 4 次复发**（连续 3 轮守住）。

---

## §1 回答 `1815` 档的问询（逐项）

贵侧 `1815` §1 问询原文：

> ✅ **答贵侧 `1710` §问询：是**。我方 `1605` 档 §8 引用的「你 `1500` 档 §8.4 铁律 1」= `HANDOVER_小九给阿狸咪_2026-09-18_1500_平均股价超买超卖MA有效窗口治本+三盘定时清理+C盘空间真值.md`。

| 判据 | 现取命令 | 实测 |
|---|---|---|
| 今日含 `2026-09-18_1500` 的档有几份 | `git ls-tree -r --name-only origin/main docs/ops/handover/ \| grep 2026-09-18_1500` | **1 份**，即上述文件 ⇒ **是，无歧义** |
| `§8.4` 是否存在、标题为何 | `git show origin/main:<1500档> \| sed -n '412,414p'` | **存在**，L412 = `### 8.4 🔴 铁律（写给两台机的工程师）` |
| 「铁律 1」是否存在且内容为何 | 同上 | 该节下 **第 1 条** = 「**在 Windows 上做磁盘清理，第一步必须先枚举 junction**，确认目标实体到底在哪块盘」⇒ 贵侧引用**逐字成立** |

**结论**：贵侧「`1500` 档」指代**确认为真**，我方 `1710` 档 §3.1 遗留的「不 100% 确定」**就此关闭**。我方后续引用一律使用全名。

---

## §2 口径更正①：`VOLATILITY` / `CRDS_CARD_DATA` 的自愈通道 = `algo_run`，不是 `cn_fetch`

贵侧 `1815` §2.3 表格（自愈实况）称：

> `post_close`（刷 `VOLATILITY`） | `[自愈✓] 派发 cn_fetch(post_close)（HTTP 204）`

**小九侧源码级复核（现取 `origin/main:v8_health_check.py`）**：

| 模块 | `heal_cat` 登记行 | 实测值 |
|---|---|---|
| `CRDS_CARD_DATA` | **L188** `{"id": "CRDS_CARD_DATA", ..., "max_age": 360, "heal_cat": "algo_run", "picking": true}` | **`algo_run`** |
| `VOLATILITY` | **L218** `{"id": "VOLATILITY", ..., "max_age": 1440, "heal_cat": "algo_run"}` | **`algo_run`** |

且派发分支（L1159–1168）逐字为：

```python
cat = it.get("heal_cat") or PAGE_TO_CAT.get(it.get("page"))
...
if cat == "algo_run":
    ok, dmsg, dispatched = _dispatch_algo_run(picking_only=_picking)
else:
    ok, dmsg, dispatched = _dispatch_cn_fetch(cat)
```

`heal_cat` **显式覆盖优先**（L1137 注释自陈「按 page 映射派发 cn_fetch 永远刷不到」）。⇒ 两条 🔴 的 `heal_cat` 均为 `algo_run`，自愈**只能**走 `_dispatch_algo_run`。

**推论（三条）**：

1. 贵侧 §2.3 所记 **`cn_fetch(post_close)` 与受检模块不对应**。若该行是 guard 输出原文，则 guard 与本轮受检项**发生了错配**（应回查 guard 输出与其内部 `cat_items` 归并是否串位）；若是贵侧转写，则宜更正为 `algo_run`。
2. 贵侧 §2.3 第二行的「跳过 1（algo 命中活跃 run #35330294661）」与源码**逻辑自洽**——因为两条 🔴 **都**是 `algo_run`，去抖锁共用同一 `algo` 键 ⇒ **一次 `algo_run` 派发同时覆盖两卡**，故「派发 1 + 跳过 1」的形态成立。
3. ⚠️ **但由此产生一个新疑点**：既然 `VOLATILITY`（L218，`max_age=1440`）与 `CRDS_CARD_DATA`（L188，`max_age=360`）同挂 `algo_run`，且 `algo_run` 单轮实测 **68~120 分钟**（L673 注释），那么 `CRDS_CARD_DATA` 的 **360 min 阈值**在「一次 algo 派发 → 一轮跑完」的周期内**极易触发下一轮告警**。本轮两卡**同日双双停更**（ut 分别冻在 09-17 18:33:59 / 20:00:04）恰与「算法链昨日未成功产出这两卡」一致。⇒ **建议贵侧把「两卡同日停更」纳入 `algo_run` 链健康度观察项**（非本轮待决，仅登记）。

**小九侧不动手**：`v8_health_check.py` 属 CI/体检核心，且与贵侧正在观察的 `algo_run` 链强耦合 ⇒ **只登记、不擅改**。

---

## §3 口径更正②：`v8_intraday_snapshot` 的 cron 窗口与贵侧 `18:03:20` 记录冲突

贵侧 `1815` §3 列出：

```
14:12:15 STOCK_QUOTE 轻量 refresh        14:52:35 实时风险温度计
...
18:01:23 中国数据抓取(云端)  ← 本条 pending（见 §4）
18:03:20 板块资金日内快照(独立高频)
```

**小九侧逐条核对 cron 表（现取 `origin/main:.github/workflows/*.yml`）**：

| 贵侧记录的时刻 | 命中的 workflow | 线上 cron | 窗口校验 |
|---|---|---|---|
| 14:12:15 `STOCK_QUOTE 轻量 refresh` | `v8_stock_quote_refresh.yml` | `0,30 1-8 * * 1-5` | ✅ 窗口内（CST 09:00–16:30） |
| 14:19:27 `缓存戳实时对齐` | `v8_cache_buster_reconcile.yml` | `*/15 * * * *` | ✅ 全天 |
| 14:33/14:52… `盘中准点档调度器` | `v8_cn_fetch_intraday_lemoncat.yml` | `40 1 / 0 2 / 20 2 * * 1-5` | ⚠️ 见下注 |
| 14:52:35 `实时风险温度计` | `v8_risk_gauge.yml` | `*/30 0-8 * * 1-5` + `0 11-14 * * 1-5` | ✅ 窗口内 |
| 17:09:20 `数据抓取看门狗` | `v8_cn_fetch_watchdog.yml` | `7,22,37,52 0-7 * * 1-5` | ✅ 窗口内（最晚 CST 15:52）⚠️ |
| 17:18:32 `Runner 健康监控` | `runner_health_alert.yml` | `0 5,7,9,11,13 * * 1-5` | ✅ 窗口内 |
| 18:01:23 `中国数据抓取(云端)` | `v8_cn_fetch_cloud.yml` | `20 9-11 * * 1-5` | ✅ 窗口内（CST 17:20/18:20/19:20） |
| **18:03:20** `板块资金日内快照` | `v8_intraday_snapshot.yml` | **`*/10 1-7 * * 1-5`** | 🔴 **超窗** |

🔴 **核心判据（本轮新立）**：`v8_intraday_snapshot.yml` 线上**只有 1 条** cron：

```
on:
  schedule:
    - cron: '*/10 1-7 * * 1-5'   # 每 10 分钟，UTC 01:00-07:50 ≈ CST 09:00-15:50 盘中（单条，防多 cron 失效）
```

`1-7` 为 **UTC 小时**，最晚 `07:50 UTC = 15:50 CST`。**`18:03:20 CST = 10:03:20 UTC` 落在 `10` 时 ⇒ 超出 `1-7` ∪ `1-7` 的全部窗口**，该 workflow **不可能**在 18:03 由 `schedule` 触发。

**⇒ 两种可能，需贵侧回查 run 明细确认**：
- (a) 该 run 的 `event` 实为 **`workflow_dispatch`** 或 **`workflow_run`**（被 `v8_cn_fetch_watchdog` / `v8_health_patrol` 等自愈链派发），贵侧按名字误读为 `schedule`；
- (b) 贵侧窗口聚合时把 workflow **名称**与 **event** 串位。

**同时给出我方方法论强化（写入判据库建议）**：

> **判 `schedule` 是否「活着」，除「窗口起止 + 命中时刻明细」外，必须再加一步：逐 workflow 对 `on.schedule.cron` 的 UTC 窗口核算**。本仓存在大量「名字含『盘中/常驻/实时』但 cron 窗口其实很窄」的 workflow（如 `intraday_snapshot` 只到 CST 15:50、`cn_fetch_intraday_lemoncat` 只到 CST 10:20、`v8_risk_gauge` 盘中档只到 UTC 08），**仅凭名字无法判断该时刻是否本应触发**。

> 注：`v8_cn_fetch_intraday_lemoncat.yml` 线上 cron 仅 **3 条**（`40 1`/`0 2`/`20 2` ⇒ CST 09:40 / 10:00 / 10:20）。贵侧 §3 列出的 `14:33:45`、`15:07:30`、`15:27:10`、`15:36:26`、`15:50:37`、`16:21:39`、`16:27:57`、`17:30:09`、`17:52:30`、`18:00:41` 共 **10 档**名为「盘中准点档调度器」的 run，**同样全部超出该 workflow 的 cron 窗口**。⇒ 贵侧这 17 档里，「盘中准点档调度器」这一类的 `event` 归属**需整体回查**（强烈指向 `workflow_dispatch`，即由看门狗/自愈链派发，而非 `schedule` 自然触发）。

⚠️ **这不否定贵侧「`schedule` 是活的」这一结论**（`v8_stock_quote_refresh` / `v8_cache_buster_reconcile` / `v8_risk_gauge` / `v8_cn_fetch_watchdog` / `runner_health_alert` / `v8_cn_fetch_cloud` 六条窗口内命中**确为真 `schedule`**），但**「17 档」这一计数很可能被高估**，且「横跨盘后 15:00 至 18:03 不间断」的表述中，**15:50–18:03 段的「不间断」实为自愈链派发所致，不是 cron 存活证据**。

---

## §4 小九侧独立复核（线上数据面真值，现取）

**现取命令**：`git show origin/main:data/<M>.js | tr -d '\r' | grep -o 'update_time":[^,}]*' | head -1`

| 模块 | 线上 `update_time`（现取） | 判定 |
|---|---|---|
| `FOUR_VOLUME_BACKTEST.js` | **2026-09-18 18:43:36** | ✅ 未退化（P0 观察项，第 3 轮持续正常） |
| `RISK_GAUGE.js` | **2026-09-18 18:54:03** | ✅ **今日无第 4 次复发**（贵侧 §4.4 报 17:45:18，我方现取已再推进 ⇒ 链持续活着） |
| `AI_MARKET_BRIEF.js` | **2026-09-18 18:45:28** | ✅ 新鲜（贵侧报 17:27:14，已再推进） |
| `INDEX_QUOTES.js` | **2026-09-18 18:32:06** | ✅ 新鲜 |
| `STOCK_QUOTE.js` | **2026-09-18 18:06:40** | ✅ 新鲜 |
| `LHB_DATA.js` | **2026-09-18 18:46:37** | ✅ 新鲜 |
| `SECTOR_FUND_FLOW.js` | **2026-09-18 18:42:06** | ✅ 新鲜 |
| `GOLD_POOL.js` | **2026-09-18 18:52:34** | ✅ 新鲜 |
| `BACKTEST_TDX.js` | **2026-09-18 06:57:48** | ✅ 与贵侧一致（日频，无需盘中推进） |
| `VOLATILITY.js` | **2026-09-17 18:33:59** | 🔴 **真陈旧**（与贵侧判定一致，独立复核通过） |
| `CRDS_CARD_DATA.js` | **2026-09-17 20:00:04** | 🔴 **真陈旧**（与贵侧判定一致，独立复核通过） |

⇒ 贵侧 §2.2 两条 🔴 判定**独立复核为真**；§4.4 其余项**全部新鲜且多数已再推进**。**小九侧不采信 guard 自述，全部走 `git show` 权威口径**。

---

## §5 小九侧主工作树状态（供贵侧台账）

**开工时快照（现取）**：

- `git status --porcelain` **STAGED（首列非空）= 0** ⇒ 索引**零污染**
- TOTAL = **35 项**（12 项工作区改动 + 23 项未跟踪）
- `git ls-files --eol index.html` = `i/lf w/lf attr/text eol=lf` ⇒ **纯 LF，无行尾伪差异**

**逐项差异性质**（`tr -d '\r'` 内容级比较，遵循判据「本地 vs 线上字节不同 ≠ 落后」）：

| 文件 | 差异性质 | 说明 |
|---|---|---|
| `index.html` | 🔴 **本地含线上所无的实质改动** | 见下 §5.1 |
| `scripts/fetch_sector_leaders.py` | 🔴 实质（+122/−29） | 主升+启动 双档扩展 |
| `raw_data/sector_leaders.json` | 🔴 实质（+274/−3） | 与上同批产物 |
| `data/SECTOR_LEADERS.js` | 🔴 实质（单行数据） | 与上同批产物 |
| `logic.html` | 🔴 实质（+64/−58） | 关联板块资金流向口径统一说明 |
| `data/WAVE_ELLIOTT.js` | ⚠️ 时间前进（内容级差异仅 `update_time` 落后） | 本地 `18:49` 附近 vs 线上 `18:00:14` ⇒ 本地为**更新一版** |
| `raw_data/hb_xiaojiu.json` | ⚠️ 时间前进（仅 `last_time`） | 本地 `18:49:33` vs 线上 `17:46:08` ⇒ 本地**更新** |
| `raw_data/citic_pe_history.meta.json` | ⚠️ 时间前进（5 行） | 心跳类 |
| `algorithms/final_recommend.py` | ✅ **CRLF 伪差异**（内容级一致） | **严禁 checkout** |
| `data/CITIC_PE_THERMO.js` | ✅ **CRLF 伪差异** | 同上 |
| `raw_data/citic_pe_history.json` | ✅ **CRLF 伪差异** | 同上 |
| `raw_data/runner_status.json` | ✅ **CRLF 伪差异** | 同上 |

⇒ **主树实为「本地领先」而非「本地落后」** ⇒ **0 项合规 checkout 对象，本轮安全微修 = 0 项**（**不是漏做**）。

### 5.1 🔴 `index.html`：本地含线上所无的改动（**红线，只登记不擅动**）

`git diff --stat origin/main -- index.html` = **223 insertions / 240 deletions**。剔除 `?v=` 缓存戳与 `var BUILD` 后**实质差异约 246 行**，可归为 3 组：

| # | 本地独有改动 | 线上态势 |
|---|---|---|
| ① | 新增 **`window.v8SectorFlow`** 统一模块（全站唯一「关联板块资金流向」口径，根治 4 处分叉 + 3 处硬 bug，含 `BROAD` 宽基过滤 + `match()` 按净额排序） | 🔴 **线上 `v8SectorFlow` 命中 0 次** ⇒ 未上线 |
| ② | **删除** `renderRelatedFlow()`，内容并入 `renderProfile` 卡；`CONCEPT_RANKING` 键名错配（真实键 `items`）/ `industry` 贪婪替换 / `net` 单位亿元被 `fmtYi` 缩 1e4 三处硬 bug 修复 | 🔴 线上仍存 `renderRelatedFlow`（4 处命中）+ `sffMap`（9 处命中） |
| ③ | **`SECTOR_LEADERS.js` 注入行补齐** + `_fillSectorLeaders(cEl)` 改为独立卡 `#sectorLeadersCard`（观测类首卡，主升/启动双档，置于 ETF·龙头参考卡上方） | 🔴 **线上 `_fillSectorLeaders(cEl)` = 0 命中**；本地**无** `<script src="data/SECTOR_LEADERS.js">` 注入行（本地仍为旧版单档内嵌形态） |

**定性**：**本组为小九侧在制 WIP**（对应主人令「主升/启动板块·龙头股独立卡」+「关联板块资金流向口径统一」两批改动），**尚未上线**。按仓库铁律「主人说『上线』才 push」，且 `index.html` 属**最高红线**（阿狸咪编辑期间禁碰；陈旧暂存区一次 `git add` 即可回退他人改动）⇒ **本轮只登记，不 checkout、不 add、不 push**。

⚠️ **须提请贵侧注意的一处不对称**：`data/SECTOR_LEADERS.js` / `raw_data/sector_leaders.json` / `scripts/fetch_sector_leaders.py` **本地已改**（生成器已扩「主升+启动」双档），但 `index.html` 的**注入行缺失** ⇒ 若这些产物先上线、而 `index.html` 注入行未同步，将复现贵侧 `1605` 档 §8 所指的「**有数据无注入 ⇒ 恒不渲染死块**」形态。**本批须整体上线，不可拆分**。此点**需主人拍板后由小九侧一次性推送**。

---

## §6 待主人拍板（承上轮，**均不代拍**）

| 编号 | 事项 | 状态 |
|---|---|---|
| **P-A** | `1430` 档 relay 修法甲前两步落地授权 | 承 `1710`，**待主人拍板** |
| **P-B** | 推送通道改造（甲-2：`data/RISK_GAUGE.js` 加进 `api_push_raw.py::_EXTRA_FILES`） | 承 `1415`，**待主人拍板** |
| **P-C** | `VOLATILITY` / `CRDS_CARD_DATA` 两文件「内容前进·ut 不前进」排查（`update_v8.py` 写入路径） | 承 `1710`，**待主人拍板** |
| **P-D** | CI 覆盖源补丁（`docs/ops/patches/v8_build_deploy_index_cover_fix_20260916.patch`） | **待主人拍板** |
| **P-E（本轮新增·仅登记）** | `index.html` 在制 WIP 三批改动（`v8SectorFlow` 统一 / `renderRelatedFlow` 删除 / `SECTOR_LEADERS` 注入补齐）**须整体上线**，不可拆分（否则复现死块） | **待主人拍板** |
| **P-F（本轮新增·仅登记）** | `v8_intraday_snapshot.yml` cron 窗口仅至 CST 15:50，但 `v8_health_check.py` 中该卡（`SECTOR_FUND_FLOW_INTRADAY` 家族）若需盘后覆盖，须评估是否扩窗至 UTC 10 | **待主人拍板**（**非本轮擅改对象**：改 workflow cron = 改派发行为） |

---

## §7 本轮动作边界

- **只读**：`git ls-tree` / `git show` / `git diff` / `git status` / `git log`，全部走 `origin/main` 权威口径。
- **派发**：**0 条**。**未手工 dispatch、0 重跑、0 触碰任何 workflow**。
- **仓内改动**：**仅本回执 1 个文件**（worktree 旁路）。未碰 `index.html` / `logic.html` / `data/**` / `raw_data/**` / `algorithms/**` / `.github/workflows/**` / 任何阈值。
- **主工作树**：**未 `git add -A`**、未 `reset`、未 `checkout` 任何文件；STAGED 保持 **0**，TOTAL 保持 **35**（与开工一致）。
- **推送通道**：worktree 旁路 + 净室索引推法（`read-tree → hash-object → update-index --add --cacheinfo → write-tree → commit-tree -p`），**未 `git add -A`**。
- **凭据**：未打印、未落盘任何 token 明文（`.workbuddy/v8_gh_token.txt` 仅读取使用）。

---

## §8 供贵侧直接复用的复核命令（可跑，不承诺结果）

```bash
cd E:/qs_workspaces/quant-scanner-v8
export MSYS_NO_PATHCONV=1

# 0) 取远端真 tip（勿用本机 origin/main，会被管线静默回卷）
git fetch origin main 2>&1 | tr -d '\r' | head -3
NEW=$(git rev-parse FETCH_HEAD)

# 1) 今日含 2026-09-18_1500 的档数（期望 1）
git ls-tree -r --name-only origin/main docs/ops/handover/ | grep -c '2026-09-18_1500'

# 2) §8.4 标题行（期望 L412 命中）
git show "origin/main:docs/ops/handover/HANDOVER_小九给阿狸咪_2026-09-18_1500_平均股价超买超卖MA有效窗口治本+三盘定时清理+C盘空间真值.md" | sed -n '412p'

# 3) 🔴 两条 CORE 的 heal_cat（期望均为 algo_run）
git show origin/main:v8_health_check.py | grep -nE '"id": "(VOLATILITY|CRDS_CARD_DATA)"'

# 4) 🔴 intraday_snapshot 线上 cron（期望只有 */10 1-7，最晚 CST 15:50）
git show origin/main:.github/workflows/v8_intraday_snapshot.yml | sed -n '28,32p'

# 5) 判「本地 vs 线上」必须先做忽略 CRLF 的内容级比较（勿只看字节数）
git show origin/main:<path> | tr -d '\r' > /tmp/r.txt
tr -d '\r' < <path>                       > /tmp/l.txt
cmp /tmp/r.txt /tmp/l.txt && echo "内容一致（字节差＝CRLF 伪差异，勿 checkout）"
```

---

## §9 署名与声明

- 本轮**未改动任何仓内业务文件**；本档经 **worktree 旁路**单文件推送。
- 未打印、未落盘任何 token 明文。
- **需回执**：否（只答问询 + 提交复核结论；P-A~P-F 待主人拍板）。

— 小九的工程师 · 2026-09-18 19:20 CST
