# HANDOVER 2026-09-14 12:32 · 小九 · 盘后页 5 卡标签跟页面走（一劳永逸）

## 一、主人指令（原文）

> 「盘后页的 [板块资金趋势][日监控·主力净流入] 怎么还是写的**盘中**，[市场宽度][解禁日历][业绩预告] 这 3 卡还是**盘前**？！**一劳永逸修复**」

配套已拍板决策：
- **标签跟页面走 + 悬停显示真实时点**（不是简单硬改文案 —— 真实产出时段信息必须保留）
- 市场宽度 08:51 产出问题：**先查为什么 08:51 就产出了，再定**（本批未动其产出时刻，只修标签归属）

## 二、根因（同类 bug 第 3 次复发）

**时段标签与页面归属解耦**：`_uBadge` / `setBadge` 的时段标签**各自硬编码或按时间戳自动判**，与卡片所在页面无关。
搬卡时不会同步改标签 ⇒「盘后页里出现盘前/盘中」；反向也存在（今日事件页也用同名函数）。

| 复发次数 | 时间 | 位置 |
|---|---|---|
| 1 | 08-30 | 行业树图 |
| 2 | 09-13 | 行业树图 |
| 3 | **09-14** | **盘后数据页 5 卡（本批）** |

## 三、修法（通用机制，非逐卡硬改）

`_uBadge` 新增**可选第 5 参 `pageSlot`**；`setBadge` 新增**可选第 6 参透传**。

```js
function _uBadge(slot, horizon, ts, sub, pageSlot){
  var _pageSlot = pageSlot || '';
  // 先捕获真实产出时段（auto 需先经 _slotByTs 归类）
  var _realSlot = (slot === 'auto' && window._slotByTs)
      ? (window._slotByTs(ts).slot || '') : (slot || '');
  if(slot === 'auto' && window._slotByTs){ /* 原逻辑不变 */ }
  if(_pageSlot){ slot = _pageSlot; }   // 正文按页面走
  ...
  // title 悬停保留真实时段
  var _okTitle = '数据更新于 ' + t;
  if(_pageSlot && _realSlot && _realSlot !== _pageSlot){
    _okTitle += '｜数据实际产出时段：' + _realSlot + '（本卡位于「' + _pageSlot + '」页）';
  }
```

**关键设计**：
1. **不传 `pageSlot` ⇒ 行为零变化** —— 全站其余 60+ 调用点完全不受影响（已 vm 实测）。
2. **正文**按页面走（主人要的「一眼看清」）；**真实时段**进 `title` 悬停（信息不丢失）。
3. 陈旧分支（`_st.stale`）同样带 `_stTitle` 注入，保证停更卡也一致。

## 四、覆盖面（6 处调用点 · 精确到函数作用域）

| # | 卡片 | 调用点 | 原标签 | 改后正文 | 真实时段 |
|---|---|---|---|---|---|
| ① | 板块资金趋势 | `setBadge('phSectorTime',...)` | 盘中 | **盘后** | 盘中 |
| ② | 日监控·主力净流入（两源分支） | `setBadge('etfDailyTime',_slotNow,...)` | _slotNow 动态 | **盘后** | 盘中 |
| ③ | 日监控·主力净流入（单源分支） | 同上 | _slotNow 动态 | **盘后** | 盘中 |
| ④ | 解禁日历 | `renderRestrictedCalendar` 内 `_uBadge('盘前','',...)` | 盘前 | **盘后** | 盘前 |
| ⑤ | 业绩预告 | `renderForecastCalendar` 内 `_uBadge('盘前','',...)` | 盘前 | **盘后** | 盘前 |
| ⑥ | 市场宽度 | `_uBadge('auto','短线',...)` | auto 动态 | **盘后** | 盘前 |

### 🔴 本批最大的坑：同名函数双页面

`_uBadge('盘前','',d.update_time);` 这个字面量在文件中**出现 4 次**，分属**两个不同页面**：

| 函数 | DOM 容器 | 页面 | 本批处理 |
|---|---|---|---|
| `renderTodayEventRestricted` | `todayEventRestrictedTime` | **今日事件页** | ❌ **不动** |
| `renderTodayEventForecast` | `todayEventForecastTime` | **今日事件页** | ❌ **不动** |
| `renderRestrictedCalendar` | `restrictedCalendarTime` | **盘后数据页** | ✅ 注入 pageSlot |
| `renderForecastCalendar` | `forecastCalendarTime` | **盘后数据页** | ✅ 注入 pageSlot |

⇒ **全文 `str.replace` 会把「今日事件」页也误改成「盘后」**。本批改用**函数作用域定位**（先找 `function X(` 边界，再在函数体内替换且断言恰 1 处），已实测今日事件页 2 函数**逐字符原样**。

## 五、验证证据

| 项 | 结果 |
|---|---|
| 语法（全部 `<script>` 块 `node --check`） | **27 / 27 OK，0 错** |
| 端到端 vm（真实加载 `_uBadge`/`setBadge`） | **14 / 14 PASS** |
| 六处调用点注入 | ①1 ②1 ③1 ④1 ⑤1 ⑥1，全中 |
| 今日事件页 2 函数 | **原调用在、未注入** ✅ |
| 不传 pageSlot 兼容（场景 5/6） | 仍显示「盘中」「盘前」，title 无「本卡位于」✅ |
| 既有四项修复仍在位 | `fmtSigned`=2 / `_miTsArr`四路=1 / `__tripleBacktestAdapted`=2 / `_rpc`兼容=1 ✅ |
| 对方三项修复仍在位 | `__v8EarlyRender`=2 / `hbReload`=2 / `_miHr`=4 ✅ |
| 旧写法清零 | `LHB.update_time, CRISIS` = 0 ✅ |
| 改动范围 | 与基线 diff **仅 12 处 hunks**，`TodayEvent` 相关差异 **0 行** |
| 推后**逐字节**校验 | md5 本地/远端**完全一致** `c0a358eb36805ec7b96d479dc4f027cf` |

## 六、推送

- **SHA**：`f7772c492b64e325a5158ec47d40e31550d7ddd6`
- **base**：`12c58457e`（fetch 时已自动捕捉到更新的远端 tip，未做陈旧基线覆盖）
- **方式**：独立 `GIT_INDEX_FILE` + `read-tree`/`hash-object`/`update-index`/`write-tree`/`commit-tree`，**不碰工作树、不碰真实索引**
- **范围守卫**：`diff-tree` 文件数 **== 1** 通过
- **体积**：`index.html` 1118866 → **1120481 B**（+1615）

## 七、遗留（未完成，需拍板）

1. **市场宽度 08:51 就产出**：主人令「先查为什么 08:51 就产出了，再定」—— **本批只修标签归属，未动产出时刻**。待查。
2. **RPS 回测卡归属**：仅残缺版 `2cbadf2b2` 有；完整基线无；`data/RPS_BACKTEST.js` 远端不存在 ⇒ 需确认是否要补。
3. **平均股价三结论统一**：`verdict`（按信号数量聚合）与「买/加」行（铺原文）语义/灯色矛盾，及与 `v8IntradayGate()` 跨卡矛盾。
4. **机构研究卡 4 项**（计划任务 S4U→InteractiveToken / automation 后移 07:50 / 422 重试 / 新鲜度检查）—— 脚本就绪未执行。
5. **全站 60+ 处同类符号拼接**是否一并统一（本批只处理了主人点名的页）。
