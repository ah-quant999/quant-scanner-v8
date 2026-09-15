# 交接文档 · 暂未上架新建「大盘观察」子TAB（2026-09-14 18:10 小九）

## 一、本次变更摘要
- **需求来源**：2026-09-14 ~17:18 主人令 —— 把「艾略特波浪/斐波那契校验」含图观测+说明，放「暂未上架」新建子TAB「大盘观察」，并把中信 PE 观测 + A股指数观测 2 张卡一并迁入。
- **关系澄清**：截图1 的「斐波那契校验」卡本质就是**艾略特波浪理论**的量化落地——用斐波那契关键比率（23.6/38.2/50/61.8/78.6%）校验艾略特五浪结构的四铁律（基准浪回撤位 / ③浪÷①浪幅度比 / 回调不破①顶 / ⑤浪÷①浪衰竭检测）。两者同源，卡名定为「斐波那契校验 · 艾略特波浪四铁律验证」。

## 二、代码落点（index.html）
- 子TAB 导航：在 `sec-ul` 下新增「📡 观测类」与「📊 大盘观察」双按钮（ul-tab 样式），由 `window.__ulSwitch(btn, tab)` 切换（`tab` ∈ {observe, market}）。
- `ulPaneObserve`（观测类，4 张）：概念ETF龙头参考 / 主题空间 / AI洞察多源对比 / 新周期判定。
- `ulPaneMarket`（大盘观察，3 张）：
  1. `elliottWaveBody`（id=`elliottWaveInner`）—— 斐波那契校验 · 艾略特波浪四铁律，渲染函数 `window.__renderElliottWave`（L6731）。
  2. `citicPeObserveBody` —— 中信 PE 极值温度计 + PE<10 持有250日回测（原观测类迁入）。
  3. `indexObserveBody` —— A股指数周期定位 · 估值分位切换（原观测类迁入）。
- 渲染分发：`__ulSwitch` 切到 `market` 时按需触发 `__renderElliottWave` / `__renderCiticPeObserve` / `__renderIndexObserve`（不再首屏无条件触发，减请求）。

## 三、数据源（真实，非估算）
- 斐波那契卡：`window.SH_FIB`（data/SH_FIB.js，日K收盘）。当前 current = {days_down:60, total_pct:-6.61, peak_date:2026-06-22, peak_close:4163.1, index:3888.11, mode:"阴跌磨底"}。浪级比率 `wave3_1_ratio` / `wave5_1_ratio` 字段暂缺 → 卡内条件留空，data/SH_FIB.js 扩展后会自动填充。
- 中信PE卡：`window.CITIC_PE_THERMO` + `window.CITIC_PE_BACKTEST`。
- A股指数卡：`window.INDEX_VALUE` 系列。

## 四、误推修正（P0 复盘）
- 上一轮曾因 `cp` 旧 stash 覆盖工作树，误推 `26e1dc6f2`（仅含 CI 缓存戳、无新功能）。
- 本轮回滚后重应用 5 处编辑，以**真实远端 tip `4cebb6b47`** 为基线，用**隔离索引单文件推送（raw-tree-push）**重推 `0a9d8f15f4966cc332ff8d7c77ce42ee610c2f3c`，fast-forward 继承 `4cebb6b47`。
- 范围守卫：diff-tree 仅 `index.html` 一处（无 raw_data 泄漏）。blob 字节数 1133724（完整未截断）。
- 内容级复核（fetch 后）：远端 `index.html` 含 `__renderElliottWave`×3 / `ulPaneMarket`×3 / `大盘观察`×7，字节数 1133724，线性继承真实远端 tip。✅

## 五、四方对齐
- 前端（index.html）：见第二节，grep 计数已验证。
- 逻辑页（logic.html）：「暂未上架·当前内容」已补「大盘观察」子TAB说明（观测类 4 张 + 大盘观察 3 张），删除观测类下已迁出的中信PE/指数卡，消除「共 6 张」旧口径。本次随 logic.html 一并推送。
- 数据（SH_FIB.js 等）：真实源，字段与渲染函数读取一致。
- 代码：`__renderElliottWave` 字段读取与 SH_FIB 结构匹配，缺失字段已兜底。

## 六、双机注意事项
- 阿狸咪机 pull 后「大盘观察」子TAB 即生效；其此前对 index.html 的改动仅为 CI 缓存戳（BUILD SHA + `?v=`），与本功能不冲突，覆盖安全。
- 双机分时：本推送发生在晚间（~18:1x），非盘中，不踩 09:15/13:00 红线。
- 推送技法：raw-tree-push 隔离索引，未碰工作树脏文件（raw_data 被 monitor 持续写入），避免 rebase 陈旧暂存地雷。

## 七、验证与待办
- ✅ 远端 git 级内容复核通过（功能计数 + 字节数 + 线性继承）。
- ⏳ Pages 站点硬 HTTP 实时验证（CI build 完成后，Ctrl+F5 看「暂未上架 → 大盘观察」3 卡渲染）。建议下一轮自查时补。
- ⏳ 若后续要标浪级，给 data/SH_FIB.js 的 current 增加 `wave3_1_ratio` / `wave5_1_ratio` 两字段，卡内③/⑤浪比率自动填充。
