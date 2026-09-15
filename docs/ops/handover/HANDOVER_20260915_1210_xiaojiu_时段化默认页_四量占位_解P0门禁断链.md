# 交接单 · 小九的股票专家 · 2026-09-15（时段化默认页 + P0 CI 门禁断链修复）

**落款**：小九的股票专家（`2814546@qq.com`）
**时段**：小九白天（07:45–17:45）→ 交阿狸咪夜间/周末
**本批性质**：P0 修复 + 主人令 UI 改动 + 一次算法链/更新链全量审计

---

## 一、本批推仓内容（2 个 commit，均经 GitHub Git Data API，`force:false`）

| 顺序 | commit | 内容 | 推送窗口 |
|---|---|---|---|
| ① | `6d4b2b170ed5` | 四量历史追踪 + AI洞察实情解析重构 + 四项 UI 修正（9 项变更） | 11:20（主人令提前 10 分钟错峰） |
| ② | 见 `tmp/bootfix_commit.txt` | **P0 修复**：四量占位 + 首屏默认页时段自适应 + 本交接单（4 项变更） | **12:10 午休窗口** |

> ② 原排 15:20，实际提前到 **12:10 午休窗口**：P0 死锁须在当晚 18:10 B 批之前解开，而午休
> （11:30–13:00，gate 判 `trading=NO`）能**当场验证 CI 门禁是否恢复**，比收盘后更有验证余量。

### ② 批明细（本次交接主体）

| 类型 | 文件 | 说明 |
|---|---|---|
| 改 | `index.html` | 首屏默认页「时段自适应」，纯插入 **+2529 字符** |
| 增 | `data/FOUR_VOLUME_HISTORY.js` | 341 B 空态占位（**解 CI 门禁 404 断链**） |
| 增 | `data/FOUR_VOLUME_TRACK.js` | 937 B 空态占位（同上） |
| 增 | `docs/ops/handover/HANDOVER_20260915_1210_xiaojiu_时段化默认页_四量占位_解P0门禁断链.md` | 本交接单 |

---

## 二、🔴 P0：CI 门禁 404 断链 → 整条构建部署链被硬阻断（本批修的就是它）

### 现象
`2026-09-15 11:36` `☁️ v8 构建部署(云端ubuntu)` 的 step9 `pre_deploy_audit` 失败：

```
❌ [6/8] HTML 数据引用: 发现 2 处 404 断链（引用文件不存在）:
    index.html -> data/FOUR_VOLUME_HISTORY.js
    index.html -> data/FOUR_VOLUME_TRACK.js
##[error]Process completed with exit code 1.
```

→ step10「部署前校验」/ step11「部署到 main」**全部 skipped** ⇒ **`data/*.js` 不再上线**。

### 根因（本机自查确认，非推测）
11:20 推送的 `index.html` 已注入这两个 `<script src>`，但其 data 文件**由当晚 18:10 B 批才生成**
⇒ 门禁判 404 ⇒ 硬阻断。

⚠️ **这是死锁**：今晚 B 批产出 raw 后须经本 workflow 构建部署 `data/*.js`，而它每次都被同一门禁拦死
⇒ **盘后数据永久无法上线**。修复窗口必须在 18:10 之前。

### 为什么 11:21 那次是 success 而 11:36 是 failure
`gate` job 的交易时段判据为 `9:25–11:30 / 13:00–14:59`；`build` 的条件是
`needs.gate.outputs.trading != 'true'`。11:21 ≤ 11:30 ⇒ trading=YES ⇒ **build 被跳过**（跳过不算失败，
workflow 结论 success）；11:36 > 11:30 ⇒ 休市 ⇒ build 真跑 ⇒ 门禁拦死。
**判据：`trading=YES` 时 workflow success 是假绿，不代表构建部署真的在跑。**

### 修法（本批已实施）
补两个**空态占位** `data/*.js`，schema 严格取自两个脚本自身的 `_write_empty()` / history 空结构契约，
使引用成立 ⇒ 门禁过 ⇒ 链路解锁。当晚 B 批产出真 raw 后，由 `update_v8` 正常构建覆盖为真实数据。

**为什么不改门禁**：`check_html_refs` 的设计目标正是「防删数据漏改引用」，它**无白名单、纯存在性
检查**。放宽它虽能放过本批，却会同时放过**真断链**（历史血泪：`logic.html` 的两个真 404 长期挂线）。
故不动门禁，改数据侧补齐。

### 🔴 由此得出的流程铁律（防复发，务必遵守）
> **往 `index.html` 注入任何 `data/*.js` 的 `<script src>` 时，该 data 文件必须在同一批提交里存在
> （真数据或空态占位）。** 否则 CI 门禁 404 会硬阻断整条构建部署链，且该链路是盘后数据上线的唯一通道。

---

## 三、UI 改动：首屏默认页「时段自适应」（主人令）

主人原话：
> 「全主站更新后，是不是被设置了直接显示最终推荐页？现在盘中高频更新这么快，每次打开网页后都要再点一下回实时数据页，这不科学！你看下怎么调整更好，比如盘前打开宏观观测页，盘中直接打开实时数据页，其他时间可以最终推荐页。」

### 根因
`index.html` L1765-1766 / L1782 硬编码默认激活：
```html
<!-- 2026-08-08 主人令：最终推荐 = 全站唯一买卖决策入口，置于选股策略左侧并默认激活 -->
<div class="tab active" data-sec="final" onclick="switchSec('final',this)">🏆 最终推荐</div>
...
<section id="sec-final" class="active">
```
⇒ 无论何时打开都停在最终推荐。

### 修法
在 body 末尾「子 tab 直达链接」脚本（L16356 起）**之前**插入一段独立 `<script>`（纯插入，不动既有源码）：

| 时段 | 落地页 |
|---|---|
| 盘前 **05:00–09:30** | `🌍 观测平台` → 其子页 `🌍 宏观观测` |
| 盘中 **09:30–11:30 / 13:00–15:00** | `📡 实时数据` |
| 其余 | `🏆 最终推荐`（保持静态默认） |

**优先级**：URL 深链（`?sec=&sub=`，下游已有脚本）> 本时段判定 > 静态默认。
**刻意保留静态默认**（`final` 的 `active` 不删）：JS 失效/被拦时页面依旧有内容，不会空白。

**附加两点**（避免新痛点）：
1. **会话内记忆**：仅「刷新」时尊重用户上次的板块选择（防自动刷新把正在看的页顶掉）；
   新开标签/新会话一律按时段重判并清除旧记忆。
2. **nav 点击记录**：事件委托记录用户手动选择（不改 nav 源码），供 ① 使用。

**时区**：用 `getTimezoneOffset()` 换算北京时间，**不依赖浏览器本地时区**（海外访问也正确）。

**接口依据（仓库既有事实，非臆测）**：
- `switchSec(sec, el)` 中 `if(!el) el=document.querySelector('[data-sec="'+sec+'"]')` ⇒ el 可省略（L7905；程序化调用先例 L16365）
- `switchSec('obs')` 内 `setTimeout(window.__renderObsPlatform,60)`（L7966）⇒ 60ms 后渲染观测平台
- `__obsSwitch(null,'macro')` 可用：L15235 注释明示「按 data-obs 逐按钮判定高亮，不依赖 btn 入参」
- 观测平台子页默认即 macro：`var _act = window.__obsActivePane || 'macro'`（L15246）

---

## 四、验证记录（全部本地实证）

### 补丁层
- `boot_patch` 自检：纯插入（剥离新增段后与基线**逐字节一致**）/ 落点先于深链脚本 /
  5 个关键串齐备 / 静态默认 2 处保留 / 9 个 `data-sec` 计数不变 / 幂等（二次跑一致）
- 防覆盖：在 **3 个不同 tip**（`cac24fa6540d`→`9ad5d0358b33`→`9687f930df63`→…）上干跑均干净落补丁

### 渲染层（Node vm 沙箱，抽取**产物中真实脚本**执行，非简化重写）
**45 项断言全绿**：
- 5 档时段 + **9 个边界秒**（04:59 / 05:00 / 09:29 / 09:30 / 11:30 / 11:31 / 13:00 / 15:00 / 15:01）
- obs 档钉住宏观观测子页 `__obsSwitch(null,'macro')`；rt 档**不得**调用
- 会话记忆：reload 尊重 / navigate 重判并清记忆 / final 不动
- nav 点击记录；程序化切换**不写记忆**（无点击事件）
- 健壮性 5 项：无 `switchSec` / 旧内核无 `getEntriesByType` / `sessionStorage` 被禁（隐私模式）/
  `loading` 态挂 `DOMContentLoaded` / 切换后仍按时段正确

### HTML 层
- 内联 script **27→28**，语法 **0 错**（vm.Script 逐个编译）
- `<script src>` 注入清单 **94→94 不变**
- `div` 平衡 329/329 前后 **0 差**
- 关键 id 次数不变（`aiInsightsCompareBody` / `obsPaneMacro` / `fvTrackBody` / `fvHistory`）
- UI 批 18 项事实断言仍成立（幂等，未被本批影响）

### 占位文件
- JSON 可解析；变量名 `window.FOUR_VOLUME_HISTORY=` / `window.FOUR_VOLUME_TRACK=` 与
  `update_v8.py::DATA_SOURCES` 映射一致（`four_volume_history.json → FOUR_VOLUME_HISTORY`）；
  空态字段齐全（含 `alerts` 明示「四量历史账本尚未建立（首次运行后自动累积）」）

---

## 五、本次审计发现（今早 07:00–11:30 全量）

### A. workflow 层（今日业务 workflow，排除 pages build）
| 时间 | 事件 | 结论 |
|---|---|---|
| 11:36 | `构建部署` step9 门禁 ❌ | **P0 已修**（见第二节） |
| 08:04 | `盘后算法链` failure，跑在 `lemoncat-cn`，停在 `Set up job` | 本机 runner **瞬时掉线**；现 runner 已 `online`/`busy=False`、`Runner.Listener.exe` 在跑 |
| 04:27 / 08:41 / 09:17 | `健康巡检` failure（step6「自愈验证：10 分钟后回查仍 fail」） | 见 B 项；step10「自愈失败升级」被 skip（设计如此） |
| 全天 | `pages build` 大量 `cancelled` | ✅ **正常并发语义**（新 push 取消旧构建），每个 cancelled 后均有 success |
| — | `gen_strong_breakout` / `momentum_common_filter` 退出码 1 | ✅ **设计内** `time_gate`（需 ≥15:30 / 18:00），非故障 |
| 11:38 | 巡检 `site urlopen HTTPError ×4` | ✅ **瞬时**（Pages 构建中）；实测主站与 7 个关键文件**全部 HTTP 200** |

### B. 巡检 fail 明细
**盘中结束（11:36）`fail: 4`：**

| # | 失败项 | 性质 | 处置 |
|---|---|---|---|
| 1 | `选股策略/四量历史: 找不到 FOUR_VOLUME_HISTORY.js` | 🔴 我方引入 | **本批已修**（占位） |
| 2 | `选股策略/四量跟踪: 找不到 FOUR_VOLUME_TRACK.js` | 🔴 我方引入 | **本批已修**（占位） |
| 3 | `全量数据/FACTOR_LAB_BACKTEST: 3天前` | 🟠 **真陈旧** | 见 C 项，已建任务 |
| 4 | `全量数据/LHB_7D: 4天前` | 🟠 **僵尸红灯** | 见 D 项，已建任务 |

**盘前（09:17）`fail: 10`** 另含 4 项实时卡（ETF 盘中异动 / 板块资金流向 / 市场预警 / 平均股价）：
盘前用「120 分钟」盘中阈值判**昨日盘后值** ⇒ **盘前假阳性**（盘中数据本就 09:30 后才有）。
⚠️ 建议后续评估「按时段分档阈值」，但**不在本批范围**（涉及巡检判据，需单独评审）。

### C. 🟠 `factor_lab_backtest.py` 三符号缺失（自 09-13 起从未成功）
```
▶ factor_lab_backtest.py  (06:43:30)  [监督执行·静默杀≥15min]
   • factor_lab_backtest.py  ← 退出码 1 | NameError: name 'CACHE_DIR' is not defined
```
- **根因（git 逐版比对确认）**：09-13 两次「删除 RPS 链」重构（`15aadbc64b` / `8e360ed65d`）
  **连带删掉本脚本对 RPS 的复用**，而 `main()` 仍在调用：
  · 09-04 版 L36 `CACHE_DIR = os.path.join(RAW, "_rps_cache")` → 现无
  · 09-04 版 L48 `from calc_stock_rps import _query_kline, _load_cache` → 现无
  · 但当前版仍在用 `CACHE_DIR`(L398/L400) / `_query_kline`(L79) / `_load_cache`(L86) ⇒ **三个符号全未定义**
- **时间线吻合**：产物 `FACTOR_LAB_BACKTEST.js` 停在 **09-12 22:14**（重构前）
- **不能简单还原 import**：`algorithms/calc_stock_rps.py` 已 404、`raw_data/_rps_cache/` 已 404
- **可行续接资源**：`raw_data/kline_cache/`（1000 个 `<code>.json`，list 格式，**每只仅 ~251 根**）
  ⇒ 由于 `MIN_BARS=761`，**它只能当兜底，主路径仍需联网拉 800 日**
- **处置**：已建专用任务 `928f903f-2468-465f-a63e-5fc838f7c1d8`（16:40），含完整诊断与边界要求。
  **本批不动算法链**（避免在时间紧 + 口径未定时改坏主链）。

### D. 🟠 `LHB_7D` 死数据（已停用但未摘监控）
- `data/LHB_7D.js`（5991 B，`update_time 2026-09-11 19:59:01`）**前端零引用**：
  `index.html` L575 只剩注释「2026-08-31 轻量化：data/LHB_7D.js 前端零引用，停止注入」
- 生成端已停跑（`run_algorithms.py` 两处注释自证：09-11 小九 / 09-13 阿狸咪）
- **但 `v8_health_check.py::CARD_DEFS` 仍登记着它** ⇒ 巡检**每轮必报 FAIL** ⇒ **永久僵尸红灯**
  ⇒ 属「告警疲劳」源头（真故障被埋）
- **处置**：已并入专用任务 `928f903f`（含「先穷尽核对引用再删」的守卫要求）

### E. ✅ 挂链完整性审计（主人令「算法链别漏了」）——全部通过
| 检查项 | 结果 |
|---|---|
| `ORDER` ⇄ `STAGES` 并集一致（模块级 assert 的静态等价） | ✅ **51 == 51**（A13/B27/D1/E11） |
| `ORDER` 全部脚本文件存在 | ✅ **51/51**（algorithms 74 / scripts 49 / v8 7 中逐条核对） |
| `SCRIPT_TIMEOUT_OVERRIDE` 无孤儿预算 | ✅ 21 项全部在 ORDER 内 |
| `STOCK_PICKING_SCRIPTS` / `BACKTEST_SCRIPTS` 全在 ORDER | ✅ 18 / 4 项 |
| **四量两新脚本挂链齐全** | ✅ `update_four_volume_history.py` + `gen_four_volume_track.py`：ORDER + STAGES[B] + 超时 900s |
| 已停跑脚本无残留挂链 | ✅ ORDER 内无 `gen_lhb_7d.py` |

---

## 六、遗留待办

| 项 | 状态 | 承接 |
|---|---|---|
| `factor_lab_backtest.py` 三符号修复 | 已完整定位，**未修** | 任务 `928f903f`（16:40） |
| `LHB_7D` 死数据清理（删文件 + 摘监控 + 摘推送） | 已完整定位，**未做** | 同上 |
| 盘前巡检用盘中阈值 → 盘前假 FAIL（4 项实时卡） | 已识别，**未改** | 需单独评审（涉巡检判据） |
| 四量账本首批仅 1 个交易日 | 逐日累积中 | 8 档前向样本需自然成熟 |
| IVF 注入修复（`data/INDEX_VALUE_FRAMEWORK.js` 漏注入 → 「A股指数观测」4 列恒「—」） | pending | — |
| 因子卡 12 档补满 | 依赖 E 批 + 缺陷 C 修复 | 任务 `928f903f` |

---

## 七、给阿狸咪的注意事项

1. **🔴 本批修的是「CI 门禁硬阻断」**，请在两批推完后**务必核对**最新一次
   `☁️ v8 构建部署(云端ubuntu)` 的 `build` job：**step9 `Pre_deploy audit` = success
   且 step11「📤 部署到 main」不是 skipped**。只看 run 的 conclusion 会被 `trading=YES` 的假绿骗到。
2. **🔴 流程铁律**（第二节末）：注入 `data/*.js` 的 `<script src>` 必须与数据文件（或空态占位）**同批提交**。
3. **热文件纪律**：本批改了 `index.html`。任何后续改动必须**以远端最新 tip 为基线**打补丁，
   `force:false`、竞速自动重取重做；**严禁**基于本地落后副本整文件覆盖（历史已造成过 1108023→938800 字节的截断事故）。
4. **推仓窗口**：盘中（09:30–11:30 / 13:00–15:00）禁推；本批 ② 走 **12:10 午休窗口**（11:30–13:00，
   `gate` 判 `trading=NO`，构建可真跑 ⇒ 能当场验证门禁恢复）。
5. **两个 `maharo/mahoro` 拼写真相源**（09-14 地雷，仍然有效）：写盘必须**双写两份 json** 并做指纹三方比对，
   base 一律先取远端 main 的 `data/maharo_insights.js`。
6. 本机 `E:/v8data/qs8-tmp/` 下的 `tmp/` 保留了全部补丁模块、审计器、渲染验证器与推仓脚本，可直接复用：
   `boot_patch.py` `boot_render_verify.js` `bootfix_push.py` `ui_html_audit.js` `chain_audit.py` `fv_push_loop.py`。

---

*本交接单由小九的股票专家生成，数据与结论均来自实时核验（GitHub API 真值 + Pages HTTP 实测），未使用状态延续推断。*
