# 小九 → 阿狸咪 · 紧急交接单

**时间**：2026-11-27 20:10（周五夜，阿狸咪时段）
**交接原因**：主人令「阿狸咪正在整改，你紧急交接给她，让她来吧」——小九停止施工，本单交阿狸咪全权接手。
**小九施工状态**：主体已改完（本地工作区），**未 commit、未 push**。因远端你已推进到 `eab79fbb86`（含 `2384e3702b 政策事件路径卡移入盘后数据页`），与本次施工同区域，小九**主动放弃推送**，避免撞车。

---

## 一、主人令原文与判据

**主人三条指令（按时间序）**

1. 「共振日历还有留着的必要吗？我看回测不怎么样」
2. 「到底删除共振什么？要根据我的宗旨，留下必要的，回测差的应该不用跟踪了吧」
3. 「那把每日洞察和三通表合并，放盘后数据页，共振日历 TAB 页和该算法删除干净，逻辑详解页记录下架原因，运维和看板对应删除」

**宗旨（唯一判据）**：① 判断大盘走势 ② 选出未来收益率最高的股。不服务这两条的、回测无 edge 的，一律不留。

**为什么删（数据说话，勿再质疑）**

「龙虎榜机构净买 >0 且游资净买 >0 且合计 ≥8000万」这个双正共振信号，全样本回测**单调负超额**：

| 持有期 | 胜率 | 均超额 |
|---|---|---|
| T+1 | 46.9% | +0.31pp（≈抛硬币） |
| T+5 | 41.3% | −1.70pp |
| T+10 | 33.5% | −3.69pp |
| T+20 | 18.2% | **−8.66pp** |

样本：409 个信号 / 358 个成熟样本，2026-06-10 → 2026-11-25。持有越久亏越多 ⇒ 无任何可交易 edge ⇒ 月历只是把无效历史逐日铺开，属纯历史台账。

**保留什么**：每日洞察（八路汇合，服务大盘走势）+ 龙虎榜三通道（当日/近7日/本月，资金面事实披露）→ **合并为盘后数据页同一张卡**。

---

## 二、仓库现状（务必先读，防止重复劳动）

小九已核对：本地 HEAD `53c0dff802` vs 远端 `eab79fbb86`。

### ✅ 已上线，不用管（远端已含）

| 项目 | 状态 |
|---|---|
| `algorithms/fetch_orphan_sector_fund_flow.py` 的 `semi_gate`（半导体资金闸门） | 远端一致，零差异 |
| `align_logic_ops.py` MUST 名单含 `v8_sector_resonance` | 远端一致，零差异 |
| 第①②轮全部（`post_close_deadline` 21:00 判死线 / `soft_age` 6h-24h / `runner_health_alert` 单条 cron / `_mom` 80pp 断裂护栏 / logic.html 6 条口径） | 已上线 |

### ❌ 未上线（本单要做的）

| 文件 | 差异 | 内容 |
|---|---|---|
| `index.html` | −1234 行 | 删月历全套 + 合并卡 + 去推荐表述 |
| `v8_main.css` | −60 行 | 月历死样式 |
| `logic.html` | +14 行 | 下架记录（原文可直接抄，见第六节） |
| `v8_health_check.py` | +2 −6 | 摘 `RESONANCE_TRACK` 白名单 + 阈值 |
| `update_v8.py` | +7 −23 | 摘映射 + experiment 段 |
| `algorithms/run_algorithms.py` | +3 −3 | 摘 E 批末步 |
| `guard_index_sections.py` | +1 −1 | 摘 `sec-rc` 守护 |
| 删 3 文件 | — | `algorithms/track_resonance.py`、`data/RESONANCE_TRACK.js`、`raw_data/resonance_track.json` |

### ⚠️ 假差异，**不要提交**

`.github/workflows/runner_health_alert.yml` 小九本地显示 +134 −134，实测 `--ignore-all-space` 后**零差异**，纯 CRLF/LF 行尾噪声。远端版本内容正确（单条 cron），以远端为准。

### 📌 小九本地实验稿

小九本机工作区仍保留整套改动（`index.html`/`v8_main.css`/`logic.html` + `backend.patch`/`frontend.patch`/`*.mine` 快照）。**阿狸咪不要试图拉取或合并它**——base 不同（小九基于 `53c0dff802`，你最远端已多 583 行），强行 rebase 必冲突。请按本单在自己最新 tip 上重做语义改动，本单第三节已给出全部锚点与代码，照抄即可。

---

## 三、施工单（锚点行号基于 `eab79fbb86`，每改一步先 `git pull` 确认没再漂）

> 通用要求：`index.html` 是 CRLF 文件，改动时保持 `newline=''` 读写，勿整文件转 LF。

### 第 1 步 · 导航页签删除

**锚点**：第 2166 行，特征 `data-sec="rc"`
**操作**：整行删除
```html
<div class="tab" data-sec="rc" onclick="switchSec('rc',this)">🧲 共振日历</div>
```
**验收**：`grep -c 'data-sec="rc"' index.html` → `0`

---

### 第 2 步 · 把合并卡插入盘后数据页 `sec-ph`

**锚点**：`sec-ph` 范围 3375–3516 行。末尾 3512 行是 `<!-- 已下架：资金流时间轴（2026-08-16 主人令） -->`
**插入位置**：第 3497 行「📐 政策事件路径 · 锚定对比」（**你 19:41 刚加的**）之后、3512 行已下架注释之前。**此处零冲突**。

```html
    <!-- 🆕 2026-11-27 主人令「把每日洞察和三通表合并，放盘后数据页；共振日历 TAB 页删除干净」：
         原「🧲 共振日历」页整页下架（机游共振月历 / 北向席位月历两 tab 随页删除），
         其唯一保留内容「📊 每日洞察」与本来的「🐉 龙虎榜三通道」合并为一张卡，落在盘后数据页。
         理由：龙虎榜席位共振信号回测无稳定 edge（T+1 46.9%/+0.31pp → T+5 −1.70 → T+10 −3.69 → T+20 −8.66pp 单调衰减），
         只能作资金面事实披露，不足以独立成页充当信号。 -->
    <div class="card" id="insightCard" style="margin-bottom:16px">
      <!-- ① 每日洞察（八路汇合）：危机雷达 / 选股池 / 板块资金 / 波动率 / 指数 / 沪深历史 / 龙虎榜 / 北向席位 -->
      <div id="insightContainer"><div class="note">加载中…</div></div>

      <!-- ② 龙虎榜三通道：当日 + 近7日 + 本月（机构 / 游资 / 北向席位）—— 全站唯一龙虎榜汇总出口 -->
      <div style="margin-top:16px;padding-top:12px;border-top:1px dashed rgba(71,85,105,.35)">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
          <span style="font-size:14px;font-weight:700;color:#c084fc">🐉 龙虎榜三通道</span>
          <span style="font-size:11px;color:var(--dim);font-weight:600">机构 / 游资 / 北向 · 当日 + 近7日 + 本月</span>
          <span id="lhbThreeChannelTime" style="display:inline-flex;align-items:center">—</span>
        </div>
        <div id="lhbThreeChannelBody"><div class="note">加载中…</div></div>
        <div class="note">口径：仅龙虎榜上榜个股；北向=龙虎榜北向席位，非全市场北向资金流。红涨绿跌。只做事实汇总与同向/分歧判断，不构成投资建议。</div>
      </div>
    </div>
```

**注意**：`#insightContainer` 和 `#lhbThreeChannelBody` 两个 id 必须原样保留——渲染函数按 id 取容器，改名即空卡。
**验收**：`grep -c 'id="insightCard"'` → `1`；页面盘后数据页能看到这张卡且不空。

---

### 第 3 步 · 删除 `<section id="sec-rc">` 整节

**锚点**：第 3683 行 `<section id="sec-rc">` 起，至其配对的 `</section>`（含前置注释块「============ 每日洞察 ============」与内部 `rc-pane`/`insightContainer` 壳）
**操作**：整节删除，原位留一行注释
```html
  <!-- 🗑 2026-11-27 主人令「共振日历 TAB 页删除干净」：原「共振日历」整个 section（data-sec=rc）已删除。
       其唯一保留内容「每日洞察」已并入盘后数据页 #insightCard（与龙虎榜三通道同卡）。
       数据层 window._rcDays / _rcNorthOf / _rcDataDateBadge 保留（三通道卡与洞察仍消费）。 -->
```
**验收**：`grep -c 'id="sec-rc"'` → `0`

---

### 第 4 步 · 删 tab 状态机与月历渲染全套

**要删的符号（远端行号）**

| 符号 | 行号 |
|---|---|
| `switchRcTab` 定义 | 3736 |
| `__rcActiveTab` | 3716 / 3742 / 3851 |
| `__rcPollHistory`（重写，见下） | 3719 / 3938 / 4338 / 5407 / 5410 |
| `__rcRedrawBoth` | 3720 / 3732 / 22003 / 22032 / 22034 |
| `renderResonanceTrack` | 3754 / 3851 / 15502 |
| `_rcJyDayListsHtml` | 3873 / 4163 |
| `_rcWeekRangeOf` | 3906 / 4111 |
| `renderJyCalendar` | 3923 |
| `_jyCalNav` / `·Prev` / `·Next` | 4271 / 4279 / 4280 |
| `_rcClickJyDay` | 4036 / 4189 |
| `renderNorthCalendar` | 4296 |
| `_northCalNav` / `·Prev` / `·Next` | 4286 / 4294 / 4295 |
| `_rcClickNorthDay` | 4399 / 4485 |

**⚠️ 必须保留（不是死代码，是三通道卡和洞察的真实依赖）**

| 符号 | 行号 | 用途 |
|---|---|---|
| `window._rcDays` | 3213 / 3250 | `LHB_HISTORY + LHB_DATA` 按日合并，三通道卡「近7日/本月」靠它算 |
| `window._rcNorthOf` | 3231 | 北向席位归属判定 |
| `window._rcDataDateBadge` | 3249 | 数据日期胶囊（防陈旧冒充当日） |

**`__rcPollHistory` 重写为**（原逻辑只重绘月历，现在只重绘卡）
```js
  /* ===== 每日洞察 · 数据就绪重绘 ===== */
  /* 2026-11-27 主人令（一劳永逸）：三 tab 收敛为单页后，switchRcTab 状态机与「最强共振·回测跟踪」
     渲染器（renderResonanceTrack + 数据兜底轮询）一并删除。LHB_HISTORY 到位后只需重绘：
     ① 龙虎榜三通道卡（近7日/本月累计靠它算）② 每日洞察。 */
  window.__lhbRedraw = function(){
    try{ if(typeof window.renderLhbThreeChannel==='function') window.renderLhbThreeChannel(); }catch(e){}
    try{ if(typeof renderInsight==='function'){ window.__insightRendered=false; renderInsight(); } }catch(e){}
  };
  window.__rcPollHistory = function(){
    if(window.LHB_HISTORY) { window.__lhbRedraw(); return; }
    var n = 0;
    var iv = setInterval(function(){
      n++;
      if(window.LHB_HISTORY){ clearInterval(iv); window.__lhbRedraw(); }
      else if(n > 400){ clearInterval(iv); }   // ~120s（大表跨境加载慢，9s 内未到位会永久空白）
    }, 300);
  };
```

---

### 第 5 步 · 自动渲染入口改直出

**锚点**：第 5405 行 `/* Auto-render TAB1 on load */`
**操作**：`renderJyCalendar()` → `renderInsight()`
```js
  /* Auto-render 每日洞察 on load */
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ renderInsight(); if(window.__rcPollHistory) window.__rcPollHistory(); });
  } else {
    renderInsight();
    if(window.__rcPollHistory) window.__rcPollHistory();
  }
```

**另需删**：`switchSec` 内进入 `rc` 页时调 `switchRcTab('tab1',...)` 的引导块（单页无 tab 可切）。

---

### 第 6 步 · 删「最强共振 · 回测跟踪」卡与 `RESONANCE_TRACK` 数据源

**锚点（`RESONANCE_TRACK` 引用）**：1401（`<script src="data/RESONANCE_TRACK.js">`）、3757、3844、3848、15526、15527

| 位置 | 操作 |
|---|---|
| 1401 script 标签 | 删除，留注释 `<!-- 🗑 2026-11-27：RESONANCE_TRACK.js 注入摘除（卡已下架，无稳定 edge） -->` |
| 回测跟踪卡 DOM（`resonTrackContainer` 所在卡） | 整卡删，留注释说明下架理由与回测数据 |
| 15527 `bt:function()` | 从 `return !!(window.RESONANCE_TRACK && window.FINAL_RECOMMEND_BACKTEST)` 改为 `return !!window.FINAL_RECOMMEND_BACKTEST` |
| 15502 `renderResonanceTrack()` 调度 | 删除（函数已删，留着是死调用） |
| 回测页 banner 「两张回测卡」 | 改为「本页唯一的回测卡」 |

**验收**：`grep -c 'RESONANCE_TRACK' index.html` → `0`

---

### 第 7 步 · 「对次日开盘推荐」改纯事实披露

**锚点**：4685 / 4711 行，特征 `对次日开盘`

| 原文 | 改为 |
|---|---|
| `共振日历（机游共振+北向席位）今日净买标的，对次日开盘推荐。` | `龙虎榜三通道（机构/游资/北向席位）今日净买标的 —— 资金流向的事实披露，非次日买入建议（该信号回测 T+5 起为负超额）。` |
| `共振日历（机游共振+北向席位）今日净卖标的，对次日开盘风险。…` | `龙虎榜三通道（机构/游资/北向席位）今日净卖标的 —— 资金流出的客观披露，非卖出建议。` |
| `暂无共振日历净买信号` | `今日无三通道净买标的` |

**理由**：回测已证该信号无 edge，卡面继续写「对次日开盘推荐」= 用负 edge 信号给建议，属误导，必须去掉。

---

### 第 8 步 · 看板与运维页登记收口

| 位置 | 行号 | 操作 |
|---|---|---|
| `CARD_DEFS` 第 `id:'rc'` 整条 | 13192 | 整条删（4 张卡：危机雷达死登记 + 三张同源 LHB_DATA） |
| `_PAGE_ORDER` | 13912 | 删 `'共振日历'` |
| `_PAGE_CARD_ORDER` `'共振日历': ['CRISIS_DATA','LHB_DATA']` | 13924 | 整行删 |
| `_PAGE_CARD_ORDER` `'盘后数据'` | 13923 | 数组内 `'SECTOR_FUND_FLOW_TREND'` 之后插入 `'LHB_DATA'`（按前端真实卡序） |
| 算法页白名单 `['盘后数据','选股策略','共振日历',...]` | grep `共振日历` 定位 | 删 `'共振日历'` |
| 盘后数据 CARD_DEFS 巡检项 `{name:'龙虎榜三通道',...}` | grep 定位 | 改为 `{name:'每日洞察（含龙虎榜三通道）', ..., note:'八路汇合洞察 + 机构/游资/北向 当日·近7日·本月；2026-11-27 两卡合并、共振日历页下架'}` |
| 运维表 「龙虎榜 fetcher（cn runner · 共振日历水源）」 | grep 定位 | 改「三通道卡水源」 |

**验收**：`grep -c '共振日历' index.html` 只剩历史注释（下架说明），无活配置。

---

### 第 9 步 · CSS 死样式清理（`v8_main.css`）

删这些小节（改前先 `grep -c` 确认 index.html 内零引用）：
`.rc-tabs` / `.rc-tab-btn` / `.rc-pane` / `.cal-grid` / `.cal-cell` / `.cal-head` / `.cal-date-num` / `.cal-net` / `.cal-sub` / `.cal-detail` / `.jy-week` / `.jy-day-card` / `.jy-block` / `.jy-li` / `.jy-badge` / `.jy-name` / `.week-cards` / `.wk-card` / `.wk-item` / `.month-summary` / `.ms-col` / `.ms-item` / `.ms-note`

小九已实测这 60 行全部零引用。**但 `.cal-*` 里若有其它页在用的，先 grep 再删**——宁可少删不留死码。

---

### 第 10 步 · 后端摘除（算法链 + 巡检 + 部署）

| 文件 | 操作 |
|---|---|
| `algorithms/run_algorithms.py` | 删 `STAGES["E"]` 与 `ORDER` 里的 `track_resonance.py`（两处必须成对，否则 `assert _STAGE_UNION==set(ORDER)` 崩链） |
| `update_v8.py` | ① `RAW_MAP` 删 `"resonance_track.json": "RESONANCE_TRACK"` ② 删 `TIER` 里 `"RESONANCE_TRACK": "post_close"` ③ 删 `[experiment]` 段调 `track_resonance.py` 的整块（约 20 行） |
| `v8_health_check.py` | ① `_LOW_FREQ_FILES` 删 `"RESONANCE_TRACK"` ② `_LOW_FREQ_MAX_AGE` 删 `"RESONANCE_TRACK": 30*24*60`（留着 = 每天假红） |
| `guard_index_sections.py` | 删 `"sec-rc": 250` 守护项（页已不存在，留着必报错） |
| 删文件 | `algorithms/track_resonance.py`、`data/RESONANCE_TRACK.js`、`raw_data/resonance_track.json` |

**改完必跑**：`python -c "import py_compile; py_compile.compile('algorithms/run_algorithms.py', doraise=True)"` + 两个 py 同理。

**`LHB_DATA` / `LHB_HISTORY` 数据层与采集链一律不动**——三通道卡和洞察还在消费。

---

### 第 11 步 · `logic.html` 登记下架原因

**插入位置**：`<li><b>概念资金热力 / 板块资金趋势</b>` 之前。
**另需改**：原句 `共振日历两 tab 仅保留月历与当日详情，不再重复周月汇总。` 尾部追加 `<b style="color:#ffd024">（2026-11-27 更新：两 tab 已整页下架，详见下方下架记录。）</b>`

**新增条目原文**（已写好，直接抄）
```html
  <li><b>🗑 2026-11-27 下架记录：共振日历页（机游共振月历 / 北向席位月历）＋「最强共振 · 回测跟踪」卡 ＋ track_resonance.py 算法</b>
  （主人令「根据我的宗旨，留必要的；回测差的不用跟踪；算法删除干净」）：
  <b>下架原因</b>=该「龙虎榜机构净买&gt;0 且游资净买&gt;0 且合计≥8000万」双正共振信号，全样本回测为<b>单调负超额</b>——
T+1 胜率 46.9% / 均 +0.31pp（≈抛硬币）、T+5 41.3% / −1.70pp、T+10 33.5% / −3.69pp、T+20 18.2% / −8.66pp
（409 个信号 / 358 个成熟样本，2026-06-10→11-25），持有越久亏得越多，不具备任何可交易 edge。
月历只是把这段无效历史逐日铺开，属纯历史台账，不服务宗旨「判断大盘走势 + 选出未来收益率最高的股」，故整页删除。
  <b>保留内容</b>=「每日洞察」（危机雷达/选股池/板块资金/波动率/指数/沪深历史/龙虎榜/北向席位 八路汇合，服务大盘走势判断）
与「龙虎榜三通道」（当日+近7日+本月，资金面事实披露）已合并为<b>盘后数据页同一张卡</b>，容器 insightContainer + lhbThreeChannelBody。
  <b>同步删除</b>=data/RESONANCE_TRACK.js、raw_data/resonance_track.json、algorithms/track_resonance.py、算法主链 E 批末步、
巡检项 RESONANCE_TRACK、看板与运维页 id=rc 整页登记、导航「共振日历」页签。
  <b>口径警示</b>=该龙虎榜席位信号今后只作「当日资金流水」看，<b>不构成买卖建议、不参与选股评分、不得再复活为选股信号</b>。
  <b>数据源保留</b>=LHB_DATA / LHB_HISTORY 本身不删（三通道卡与每日洞察仍消费）。</li>
```

---

## 四、红线（踩了就是事故）

1. **不要 `git add -A` / `git add .`** —— 本地有一堆不该入库的：
   `.pt/`、`NUL_log.txt`、`runs.json`、`job_*json`、`_maharo_base_1127.js`、`v8_send_alert.py.bak_1118`、`backup/`、`.playwright-cli/`、`.github/workflows/tmp_check.py`
   **提交前逐行 `git status --short` 确认**，只 add 明确列出的文件。
2. **不要复活该信号**。不许以「多因子合成」「加权修正」等名义把龙虎榜席位共振塞回选股链。它回测是负的。
3. **不要删 `LHB_DATA` / `LHB_HISTORY`**。
4. **不要动 `.github/workflows/runner_health_alert.yml`** —— 你本地/小九本地那份都是纯行尾噪声，远端内容正确。
5. **不要碰 `algorithms/fetch_orphan_sector_fund_flow.py` 的 `semi_gate`** 和 `align_logic_ops.py` 的 MUST 名单 —— 已上线且零差异。
6. `index.html` 是 CRLF，读写保持原样，别整文件转 LF（会造成 4000+ 行假 diff）。

---

## 五、改后三件套（必须全走，缺一不算完）

**① 审计**
```bash
python guard_index_sections.py                 # 板块守护，0 失败
python align_logic_ops.py                      # 门禁 8 项，[4/8] MUST 名单
python -c "import py_compile; [py_compile.compile(f,doraise=True) for f in ['v8_health_check.py','update_v8.py','algorithms/run_algorithms.py','guard_index_sections.py']]"
# 内联 JS 逐个 node --check（抽 <script> 无 src 块）
node --check <每个内联块>
# 死引用扫描：以下必须全 0
for f in renderJyCalendar renderNorthCalendar switchRcTab renderResonanceTrack _rcJyDayListsHtml _rcWeekRangeOf _jyCalNav _northCalNav __rcRedrawBoth __rcActiveTab RESONANCE_TRACK rc-tabs; do echo "$f: $(grep -c "$f" index.html)"; done
```

**② 净室推送**
- `git fetch` 后 `git diff --stat origin/main` 逐文件核对，只推本单列出的文件
- 提交信息建议：`v8 精简: 共振日历整页下架 + 每日洞察并入盘后数据 + 回测跟踪与算法彻底删除 (2026-11-27)`
- 推完硬抓 Pages 验证：页面不空白、盘后数据页 `#insightCard` 有内容、导航无「共振日历」页签

**③ 对齐**
- `align_logic_ops.py` 通过 + `logic.html` 已登记下架记录
- 交接单归档（本文件即交接单，推仓库即有档）

---

## 六、小九本机参考件（读不到就照本单抄，本单已含全部代码）

| 文件 | 内容 |
|---|---|
| `.pt/handover_20261127_2006/index.html.mine` | 小九改完的完整 index.html（base 旧，仅供对照结构） |
| `.pt/handover_20261127_2006/frontend.patch` | 前端全量 diff（1874 行） |
| `.pt/handover_20261127_2006/backend.patch` | 后端全量 diff（613 行） |

**⚠️ 这三个文件只是备份，不是可 apply 的补丁**（base 不同，必冲突）。需要看具体某一段怎么改，让主人转达或让小九直发片段。

---

## 七、完工回报

改完请回一条：
- 三件套三项各自结果（通过/失败）
- Pages 实测截图或硬抓结果
- `grep -c '共振日历' index.html` 的实际值（应只剩历史注释）
- 有无遗留风险

小九待命，随时可补位排查。
