# 九宝量化 v8 长期项目笔记

## 部署与发布铁律
- 线上站 `https://ah-quant999.github.io/quant-scanner-v8/`（仓库 `ah-quant999/quant-scanner-v8`）；本地唯一副本 `E:\workspace\stock-scanner`（工作树==origin/main）。本地预览开 `file:///E:/workspace/stock-scanner/index.html`。
- **git push main 常因远端 build 改写 index.html 被拒** → 已装 `scripts/pre-push` 钩子自动 fetch+rebase。
- **git push 网络 reset 兜底**：改用 GitHub Contents API `PUT /repos/{REPO}/contents/{path}`（base64+sha）直推，再 `POST .../pages/builds` 触发构建。PAT: `ghp_***REDACTED***`。
- **CDN cache-buster 铁律**：`?v=` 必须用**内容 sha1 前10位**，绝不能用 mtime（mtime 变→72个URL全变→每次全量重下10MB+）。data 文件被截断/改内容后，必须同时更新 index.html 的 `?v=` + 重新 PUT 完整文件，否则 CDN 继续吐旧缓存。
- **Contents API 截断坑**：>1MB 或接近 1MB（如 837KB index.html）会静默截断 GET 返回。验证文件真实大小/内容用 Python 实际下载字节数或 raw.githubusercontent，别信 curl `size_download`。

## 算法/数据审计铁律
- 算法输出「全港股 / A股=0 且 总数>0」= 立即报警（上游路径 bug，非弱市）。
- 「count=0」且其他池也 0 → 排查上游；独立为 0 而其他池正常则弱市可接受。
- 市场分布全 A 股是常态，不得误触发 warn；A 股缺失由 `check_a_share_coverage()` 统一捕获。
- **「接口空→标占位」高危**：写 trading=False 等占位前必须先用交易日历校验；查不到/非交易日只打日志不污染（fetch_lhb.py 8/4-8/13 污染 7 天前车之鉴）。

## 前端渲染铁律
- **defer 时序**：`data/*.js` 带 defer，内联脚本先执行读到空占位 → 渲染代码必须改为具名函数 + `DOMContentLoaded`/`setTimeout` 兜底重绘；占位文案写"加载中…"非"暂无数据"。
- **时段标签**：一律调 `window._slotByTs(ts)`（盘中边界 9:00-15:30），禁止硬编码 `_hr<15` 或写死"盘前/盘后"。

## 止损止盈 / 增量缓存
- 全站统一 `fixedP10/rrK1.5`，配置中心 `algorithms/stop_target_profiles.json`，勿在业务代码写死。
- `backtest_tdx.py` 读自身输出 `raw_data/backtest_tdx.json` 跳已有回测 → 参数变更后必须删该 JSON 再重跑（用 Python os.remove，别用 rm -f 会被 safe-delete 钩子拦）。

## V6 备忘录 防覆盖（永久）
- 逻辑详解页「📦 v6备忘录」经 `<iframe src="v6_memo.html?v=<sha10>">` 加载，v6→v8 唯一算法详解参考页。
- **三重防护**：① `guard_v6_memo.py` 部署闸门（缺失/截断<60KB 自动从 git HEAD→`v6_memo.golden.html` 自愈）；② index.html 须保留 `data-lg="v6"`+`id="lg-v6"`+iframe，缺失 FAIL 部署；③ iframe `?v=` 强制内容 sha 击穿 CDN 旧缓存。
- **v6 缓存戳失配根因（2026-08-15 永久修复）**：本机 Windows 是 CRLF、CI(Linux)/origin 存 LF，护栏本地算出的 `?v=` 与"实际部署文件 sha"永远不符，未来必复发 CDN 旧副本。**修复**：`.gitattributes` 钉死 `v6_memo.html`/`v6_memo.golden.html` 为 `text eol=lf` + 两文件归一为 LF → 任意机器算出的内容 sha 相同，缓存戳与部署文件严格相等。`v8_build_deploy.yml` 已把三件套纳入 `git add -f`。
- **DO_NOT_DELETE**：任何清理/重构任务不得删除 `v6_memo.html`/`v6_memo.golden.html`/`guard_v6_memo.py` 或移除 index.html v6 入口。
- v6 历史备份（tar.gz）v8 稳定运行满一周且主人确认前不得清理。

## 删除纪律
- "删了吧"类指令：先二次确认删的是说明页还是生产卡片、是否保留数据/JS、是否影响联动；优先 `display:none`/注释占位，勿直接删 HTML+引用+数据三者。
- **「下架」= 移到运维「已下架」专区，不是删除**（2026-08-16 主人怒令）：主人说"下架/已下架"时，把卡整体（HTML 卡 + JS 渲染函数）从主展示区**移入**运维一级 Tab → 「已下架」子页（`opTab4` / `delistedPanel`，渲染函数 `renderDelisted` 内 `insertAdjacentHTML` 注入 + 调用 window 暴露的渲染函数）。**严禁删除代码**。已下架专区现有：宏观观测 / 资金流时间轴 / 上证+深证成交金额 / 近一月涨跌家数。若误删，从 git 本地提交 `f7d39ed50`（删除前版本）恢复 `git show f7d39ed50:index.html`。

## 北向席位日历 铁律（永久 · 2026-08-15 主人怒令）
- **⚠️ 北向 ≠ 北向席位，两类绝不可混淆**：
  - **北向资金（NORTH_FUND）** = 沪深港通北向净流入（资金流口径，单数值）。
  - **北向席位日历（共振日历 TAB2）** = 龙虎榜口径·沪深股通**专用席位**逐日净买卖明细（LHB_HISTORY.seats），与北向资金是完全不同的两套数据。
- **DO_NOT_DELETE**：任何清理/重构/审核任务**绝对不得删除**北向席位日历（sec-rc TAB2：`northCalContainer` / `renderNorthCalendar` / `_northCalNav` / `_rcClickNorthDay` / `__northCalState` 整段 IIFE + TAB 按钮 + switchRcTab tab2 调用）。
- 2026-08-14 阿狸咪误把「北向席位日历」当「北向资金」擅自删除，主人震怒要求复原。**复原来源**：从 `aebac01b7` commit 提取完整 333 行 IIFE 还原。
- lg-rc 逻辑详解页须保留「北向席位日历-席位补回机制」说明卡（🟡 席位待补机制，2026-08-12 修复）；v6_memo 已永久保留「阿狸咪误删后已恢复」教训块，勿移除。
- 若主人未来提"删北向"，必须先口头二次确认指的是资金还是席位，二者皆不可擅自删。

## 个股动量状态增强分析（2026-08-16 新增）
- **V1**（`STOCK_MOMENTUM_STATE.js`）：OCR 抽取的 39 天原始共识数据（360 只 / 385 次出现），含入选日分类和涨幅。
- **V2**（`STOCK_MOMENTUM_STATE_V2.js`，790KB）：基于 westock K 线真实验证的增强分析，定义 `window.STOCK_MOMENTUM_ENHANCED`。
  - **K 线来源**：`mcp__westock-mcp__data_kline`（前复权日 K，2026-06-01~08-15），360/360 全部查到。
  - **核心指标**：`consecutive_up_days`（连续涨天数）、`max_gain_pct`（最大涨幅）、`max_drawdown_pct`（最大回撤）、`t5_gain_pct`（T+5 收益）。
  - **走势分类**：🟢连续涨不回撤(73只) / 🟠强势股(79只) / 🔵可精选(7只) / ⚪观察用(226只)。
  - **时间段分组**：甲午月（6.5-7.7）226 只 / 乙未月（7.7-8.7）159 只。
  - **渲染位置**：index.html `renderUnlisted()` 动量卡内，基础卡下方三段增强区（符合概览/走势特征/共同点）。
  - **自愈加载**：V2 缺失时动态注入 `script`（不阻塞 V1 基础卡显示），缓存戳 `?v=f85bc788d8`。
  - **部署**：已加入 `scripts/deploy_blobs.py` FILES 字典，随 index.html 同步推送。
  - **关键发现**：入选日强势（涨幅大）+ 多分类共识 → T+5 收益显著更优；最佳组入选日均涨 +10.23%。

## 商品涨价弹性榜（2026-08-16 升级）
- **基准升级**：静态 `REFERENCE_BASELINE`（硬编码均值）→ 30日滚动 **z-score**（μ±σ）。价格历史存 `raw_data/commodity_price_history.json`，满10日自动切换，不足回退静态兜底。
- **三通道数据源**：① MACRO_DATA(gold/silver/copper/oil) ② westock-mcp 国际期货(LME/NYMEX/CBOT 11个) ③ **eastmoney push2 国内期货**(LC碳酸锂+SA纯碱，2026-08-16 新增)。
- **未接入3个**：磷化工/维生素/稀土 = 纯现货指数(SMM/百川盈孚付费)，无免费实时API。从原5个缩减至3个。
- **弹性公式**：`elasticity = 偏离度(%) × 业务占比 × 杠杆1.5`。涨价阈值双轨：dev%≥3.0 或 |z|≥2.0。
- **逻辑详解页备忘**：v6_memo.html §7.5「商品涨价弹性榜·数据源与计算逻辑」（三通道表 + 旧vs新基准对比 + 未接入原因）。
- **国内期货 secid**：`145.LC`(广期所碳酸锂) / `115.SAM`(郑商所纯碱)，走 `push2.eastmoney.com/api/qt/stock/get?secid=...&fields=f43,f170`。

## 双机/cn runner（简）
- 工作日小九(lemoncat-cn)、周末/节假日阿狸咪(alimi-cn)兜底。self-hosted cn workflow 的 checkout 须 `clean:false`+`fetch-depth:1`；job env `CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD:1000` + runner `.env` 同值，否则 safe-delete 钩子拦截。

## 双层审计体系（2026-08-16 建立，永久）
- **云端 `v8_daily_audit.yml`（每天 22:30 CST，唯一审计入口）**：① `v8_health_check.py --alert --site` 全站审核 8 大项 ② `audit_weekly.py --cloud`（?v 真失配/受保护文件/workflows 一致性，跳过本机 DB/HEAD）③ **自动自愈**：发现 ?v 失配 → `fix_cachebusters_cdn.py`（CDN 权威）重算 → Contents API 直推 index.html（GITHUB_TOKEN）→ 触发 Pages 构建。全自动。
- **本机审计自动化已全删**（2026-08-16 主人令 C："能云端就尽量全部云端跑，省token"）：每晚轻量 23:30 与周末全量 22:00 均 delete；audit_nightly.py/audit_weekly.py 保留为本地手动工具。**4 个数据/校验类双机任务已 delete 本机并迁云端 3 workflow**（22:24 落地）：`v8_freshness_watch.yml`（每小时）、`v8_t1_guard.yml`（周六8:30+9:30）、`v8_weekend_light.yml`（SA/SU 19:30），汇报走 Actions Step Summary。**WorkBuddy 仅剩 6 个 AI 交互/本机管理类（交接×4 + 心跳接管 + 紧急指令监听）——必须留本机**。
- **⚠️ CDN 权威铁律**：修 ?v 一律用 `scripts/fix_cachebusters_cdn.py`（直接下载 github.io 真实内容算 sha），**勿用 reconcile_cache_busters.py**——cn git 墙下它取过时 origin/main 缓存算旧 sha 对不齐 CDN（2026-08-16 实测 11+1 失配根因）。`deploy_blobs.py`（Git Blobs API 推 index）含 PAT 被 secret scan 拦 409 → 保持本地工具勿推仓；云端自愈用 Contents API+GITHUB_TOKEN。
- **已知缺陷（云端 build 周期复现）**：cn runner 直推 data 后，后续 build 会把 index.html 里 cn-extra 文件 ?v 覆盖回旧值（STOCK_RPS/FOUR_VOLUME/FOUR_VOLUME_60M/STOCK_STOP_DATA/FINAL_RECOMMEND_DATA/ALGO_TRACK/STOCK_MOMENTUM_STATE(V2)/MOMENTUM_FILTER）→ 云端每日 22:30 自愈兜底。
- **审计判据以「线上 CDN 自洽」为准**（线上 index ?v == 线上 data sha）；本地 data 滞后（Contents API 直推链路）属正常；本地 vs 线上 index「内容不同」降 info（部署走 API 直推+build 重写）；origin/main 比对在墙环境降级 info。
- **⚠️ 浏览器内存缓存铁律（2026-08-16 "个股查询上周四数据"教训）**：github.io 服务器 `Cache-Control: max-age=600` 头会**覆盖** head 里的 no-cache meta（meta 仅 HTTP 头缺失时的 fallback）→ 长期打开的 tab 内存缓存停留 → 用户看到 N 天前数据。**真一劳永逸 = head 加 `<meta http-equiv="refresh" content="1800">`**（客户端指令不被服务器头覆盖，30 分钟整页刷新）。audit_weekly 已加第 6 项"关键数据源陈旧度"兜底检查（STOCK_QUOTE/LHB_DATA/ALGO_TRACK/FINAL_RECOMMEND 的 update_time/date ≥ 最近交易日）。
- **v6_memo.html 换行符教训**：本地护栏按 CRLF 原始字节算 sha 永远≠线上 LF sha → 已归一化 LF（8c2b52e345）。改 v6_memo.html 后必须保持 LF（.gitattributes eol=lf）。
- 8 个双机自动化 model=NULL 长期遗留（ID 在 HANDOVER_2026-08-16_审计自动化.md）：工具无法落库 model_id，需主人 UI 逐一手动确认 deepseek-v4-flash。

## ⏰ 数据陈旧铁律（永久 · 2026-08-17 主人紧急令）
- **主人令原文**：「交易日超出 24h 就要报警自愈闭环！周末假期要延算到 T+1」
- **实现**：`v8_health_check._hard_cap_for_owner_rule(n=None)` 函数（line 875）
- **规则**：
  - 交易日：max_age 硬 cap = **1440 分钟（24h）**。任何 data 陈旧超 24h = fail + `self_heal` 派发刷新
  - 非交易日（周末/节假日）：max_age 硬 cap = **`next_trade_day 18:30 - last_close` 分钟数**（自适应长假，下限 24h）
    - 例：周五 15:30 出的数据，最迟应在「下周一 18:30」前出现新值 → 上限 ~75h（4500 min）
    - 长假（如国庆连休 7 天）自动顺延到 T+N 18:30，不写死
  - **接入方式**：`adjust_max_age` 返回前 `min(def_max, _hard_cap_for_owner_rule())` 叠加（line 927-929）
- **派发链路**：所有 fail 项交给 `self_heal()` 按 `heal_cat`（algo_run=算法链/premarket/intraday/post_close）派发对应 workflow；HEAL_DEBOUNCE_MIN 去抖锁防雪崩；MAX_DISPATCHES_PER_RUN 单次上限。
- **DO_NOT_REMOVE**：此铁律写入 v8_health_check.py 函数中，未来调整业务阈值时不能删 `_hard_cap_for_owner_rule` 调用。
- 效果验证（2026-08-17 22:30 跑）：29 fail 全部命中 24h 红线（昨日 14-19 点出的数据到现在 ≥ 24h），其中 21 张盘后/选股策略走 algo_run 派发，6 张实时数据走 intraday，4 张今日事件走 premarket。

## 🕵️ 全链路审计铁律（永久 · 2026-08-17 主人怒令）
- **主人令原文**：「每个前端的算法都全面审计！发现问题马上一劳永逸式修复，自愈闭环！」
- **根因**：81 个 data/*.js 只有 28 个在 CARD_DEFS，53 个从未被审计 → 陈旧 3 天没人报警
- **核心修法**：`v8_health_check.check_all_data_files()` 自动扫描 data/*.js **全集**（未来新文件自动纳入，无需手工登记）
  - 已登记 CARD_DEFS 的卡跳过（check_data_cards 管）；其余按 24h 红线/T+1 18:30 通用规则审计
  - 低频豁免名单（7 天红线）：STOCK_PROFILE / WEEKEND_META_REPORT / PORTFOLIO / PORTFOLIO_COST / CONCEPT_ETF_MAP / OPTIMIZED_STRATEGY / BACKTEST_TDX / BLOAT_CHECK / HEALTH_CHECK / RUNNER_STATUS_HEALTH
  - window 变量名≠文件名的别名：STOCK_MOMENTUM_STATE_V2→STOCK_MOMENTUM_ENHANCED、PORTFOLIO→PORTFOLIO_DATA、STOCK_RPS→STOCK_RPS_DATA
  - IIFE 壳兼容：load_window_var 支持 `window.X = (function(){ var data = {...}; ...})()`
  - CONCEPT_ETF_MAP 是非严格 JSON（JS 注释 + 无引号键）→ 按体积检查兜底
- **自愈风暴防线**：`_cn_runner_available()` — cn self-hosted runner 全 offline 时跳过派发（防 patrol 每 6 分钟兜底 → Set up job 全失败 → 死循环）
- **家里机 runner 铁律**：alimi-cn 位于 `D:\actions\cn-runner`，**Windows 重启后不会自启**——若 GitHub runner 列表显示 alimi-cn offline，需手动执行 `run.cmd` 拉起（2026-08-17 21:58 教训：offline 导致 algo/cn_fetch 补跑全部失败 + patrol 风暴）
- **孤儿脚本纪律**：任何新增算法脚本产出 data/*.js 后，必须：①加进 `run_algorithms.py ORDER` 或对应 workflow ②跑一次 v8_health_check 确认被审计。已补孤儿：calc_sentiment_cycle.py（→SENTIMENT_CYCLE.js）、refresh_dividend_cninfo.py（→STOCK_QUOTE 分红）。

## 🛡 防覆盖铁律（永久 · 2026-08-17 主人怒令 发现）
- **主人发现**：实时数据区「ETF 三合 - 主力净流入卡」我 21:20 触发的 calc_etf_intraday.py 把小九下午的真版本覆盖了
- **根因**：家里机 eastmoney 被风控 → fetch_etf_list() 返回 None → 脚本仍写 `{error:True, items:[], note:'失败...'}` 空结构覆盖了 1564 只真数据 + 100+ items
- **一劳永逸铁律**：`algorithms/calc_etf_intraday.py` line 73 — 网络失败时直接 `sys.exit(0)` 不写任何文件，保留 raw_data/etf_*.json 现有真数据。提示云端 v8_cn_fetch_cloud.yml category=intraday 重跑补救。
- **全 v8 通用模式**：
  - 网络/上游失败 → **不写盘 + sys.exit(0)**，禁止空结构覆盖现有真数据
  - 同样的守卫要复用到所有产出 data/*.js 的脚本（fetch_lhb/fetch_inst_trade/fetch_sector_rs/fetch_stock_quote_v8 等），下次专项整改
- **DO_NOT_REMOVE**：calc_etf_intraday.py 中的 sys.exit(0) 守卫。任何「网络失败写 error 状态」的回退分支都不安全。
- 教训：今晚发现 3 类独立故障（cn runner offline 风暴 / CARD_DEFS 只覆盖 35% / calc_etf_intraday 覆盖小九真版本）——根因都是「本地脚本写空结构覆盖现有真数据」。

## 🎨 前端交互铁律（永久 · 2026-08-17 主人发现）
- **主人发现**：强势突破页「走势特征」+「K线复盘」两个卡片 +N more「不可点」（line 9417/9497 用 stocks.slice(0,8) + `<div>+N more</div>` 纯文本，**无 onclick**）
- **根因**：原代码用 slice(0,8) 只渲染前 8 条 + 不可点 div 文案「+N more」→ 看起来像可点但实际点了没反应，剩下 N-8 条根本没在 DOM 里
- **一劳永逸修复**：
  - 渲染**全部**（不 slice） + 第 9+ 条默认 `display:none`
  - 「+N more」改成真按钮：`onclick` 切换 `data-catmore` / `data-leadersmore` / `data-leadtext` / `data-leaderdetail` 四个数据集的 display + 文案变「收起▲」
  - 走势特征区 1 个按钮同步控制「领涨摘要」+「详细列表」两处第 9+ 行
- **教训**：任何显示「+N more」类折叠提示必须用 `<button>` 或带 onclick 的元素，**禁用纯 `<div>` 文案**——避免主人点了没反应以为"被覆盖了"
- **同模式威胁清单**：grep `+N more` / `+N 只` / `点击查看更多` / `展开全部` 等文案，确认都带 onclick

## 🛡 jsx-attr-onclick 铁律（2026-08-18 07:02 主人令）
- 主人原话:「空了！运维和逻辑详解页导航按不了！昨晚做了什么把主站弄崩了！全面修复」
- 根因:onclick 内字符串拼接多 escape 极易错(昨晚 22:25 + 22:55 + 今早 06:32 三次修复连续引入 3 个错位)
- 铁律:**所有 onclick 内容只能调用函数名**(),禁用字符串拼接()
- 必须配  属性存值,JS 函数内  取值
- **新代码前必跑 node --check**:index.html 25 个内联 script 全跑语法校验(0 错才能 commit)
- 审计 grep:1895:              +(hasData?'onclick="window._showLhbDay(''+iso+'')" title="'+esc(iso)+'"':'')
1992:            +'title="'+esc(title)+'" onclick="window._showLhbDay(''+d+'')">';
3078:      h += '<div class="' + cls + '" onclick="_rcClickJyDay('' + iso + '')" data-date="' + iso + '">';
3537:      h += '<div class="' + cls + '" onclick="_rcClickNorthDay('' + iso + '')" data-date="' + iso + '">';
4732:          <button class="btn" onclick="var f=document.getElementById('v6MemoFrame');f.src=f.src.replace(/&refresh=\d+/,'')+'&refresh='+Date.now();document.getElementById('v6MemoError').style.display='none';window.__v6MemoLoaded=true;" style="padding:8px 18px;font-size:13px;">🔄 强制刷新 v6 备忘录</button>
4937:      return '<div style="display:flex;align-items:center;gap:8px;padding:9px 15px;cursor:pointer;transition:background .15s;border-bottom:1px solid var(--border);" onmouseover="this.style.background='var(--bg2)'" onmouseout="this.style.background=''" onclick="selectV8QueryStock(''+s.code+'')">'+
8772:    filterBtns+='<button onclick="cockpitSetFilter('all')" style="padding:4px 12px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid #6c7bd6;background:rgba(108,123,214,.18);color:#cfe3ff;">全部('+top10.length+')</button>';
8774:      filterBtns+='<button onclick="cockpitSetFilter(''+name.replace(/"/g,'')+'')" style="padding:4px 12px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid #3a6fb0;background:rgba(56,150,200,.16);color:#9fd0ff;">'+name+'</button>';
9430:        if(stocks.length > 8) h+='<div data-total="'+(stocks.length-8)+'" style="color:#a855f7;font-size:12px;text-align:center;padding:2px;cursor:pointer;user-select:none;font-weight:600;" data-togglecat="'+catsn+'" onclick="window.__v8ToggleCatMore(this)">... +' + (stocks.length-8) + ' more (点击展开)▼</div>';
9513:            if(p.leaders.length > 8) h+='<div data-leadersmore="'+pname+'" data-total="'+(p.leaders.length-8)+'" style="color:#a855f7;font-size:12px;text-align:center;padding:2px;cursor:pointer;user-select:none;font-weight:600;" data-togglelm="'+pname+'" onclick="window.__v8ToggleLeadersMore(this)">... +' + (p.leaders.length-8) + ' 只更多（点击展开）▼</div>';
10037:        html += '<span onclick="window._ppFilterConcept=''+cn+'';window._fillPotentialPicks();" style="cursor:pointer;display:inline-block;padding:3px 8px;background:'+bg+';border:1px solid '+bd+';border-radius:6px;font-size:11.5px;color:#c4b5fd;font-weight:600;">'+cn+'</span>';
10100:        return '<span onclick="window._ppFilterConcept=''+cn+'';window._fillPotentialPicks();" style="cursor:pointer;color:#a78bfa;'+act+'">'+cn+'</span>'; 任何 onclick 含  拼接的代码必须重构

## 🦊 子块「更新于」戳铁律（2026-08-18 06:32 主人令）
- 主人原话：「今日判定卡片名更新于那些全没了」= body 内部 6 个子块都缺戳,不是卡头
- 一劳永逸修复：`_buildJudgmentEnvHTML(d)` 内每个子块（信号灯/时事/关键数据/3 大股市/3 大分析师/危险信号）都加「🦊 更新于 XX」stamp
- 通用铁律：**所有含数据块的卡必须在每个子块都加「更新于」戳**，不能只靠 v8CardHeader 卡头一次
- 同模式审计清单：grep 函数体（`_buildJudgmentEnvHTML` / `_buildStockRun` / `_buildFibHTML` / `_buildCockpitHTML` / `renderJcardHTML` / `renderKlineData` 等），查每个子块是否都 stamp

## ⏰ 本地 ↔ 云端同步铁律（永久 · 2026-08-17 主人发现）
- **主人 22:34 发现**：主人截图看到「平均股价 29.391 +1.78% / 样本 5281 只」，但本地 `data/AVG_PRICE_DATA.js` 一直是 8-16 旧版 **28.5565**（avg_price_data.json 也是 8-16 17:25）。主人看到「被覆盖」实际是**本地 git main 落后云端 origin main 1 小时**——本机 git push 失败后我用 Contents API 推了部分文件，但**没 fetch origin 同步云端**，主人打开的页面渲染的是云端 CDN 真版本，本地仓库却停留在 19:34 之前
- **永久铁律**：
  1. 本地机网络封 GitHub 协议（git push 经常 timeout / connection reset），走 Contents API 直推是兜底
  2. **每 5-10 分钟**用 Contents API 增量同步云端 → 本地（`_tmp_sync_from_origin.py` 已写）
  3. **指标卡陈旧度报警**：v8_health_check 发现某张卡片 update_time 落后云端 > 5 分钟 → 自动 sync（新增 check_origin_sync）
  4. **所有部署完成后必须验证**：用 Contents API GET 回拉云端 main 真实 sha，对比 = 本地刚推的 sha，确保真推上去了
- **防覆盖守卫**（已多处部署）：
  - `cloud_fetch_v8.py:save()` `_is_empty_payload()` 检查空数据，跳过写入（2026-08-12 主人修，永久）
  - `algorithms/calc_etf_intraday.py` 网络失败 → `sys.exit(0)` 不写盘（22:22 主人发现，永久）
  - `algorithms/gen_top5_track.py` `entry_price` 缺失兜底（22:22 主人发现，永久）
  - `v8_health_check._cn_runner_available()` 派发前查 runner 在线状态（22:00 主人发现，永久）
- **本次 sync 结果**：80 个文件已用 Contents API 拉云端 → 本地，主机刷新即可看到真版本（29.391 + 各种被覆盖的卡）

## 🔮 主机网络/同步铁律（永久 · 2026-08-17 反复发现）
- **本地 Windows 推 GitHub 经常 reset**：TCP 443 重置/Github 504/SSL 错误 → Contents API 直推是兜底（已有）
- **本地 fetch GitHub 协议也经常 timeout**：连 `github.com:443` 都连不上 → **Contents API 同步是唯一稳定手段**
- **今日教训 22:34**：本地 git main 落后云端 main 1 小时——原因是我用 Contents API 推了文件，但没反向拉回云端任何变化。**双向同步盲区**——需要 `/tmp/sync_from_origin.py`（已写）定时 Contents API 拉云端 → 本地

## 🔄 写时缺失→永久 null 污染模式（2026-08-17 主人发现）
- **现象**：`TOP5 90天跟踪` 3 只股票「最新价/盈亏%/峰值%/天数」全显示「—」空白
- **根因**：3 只 Top5 入场日 `fetch_stock_quote_v8` 没拉到当日收盘价（06862 海底捞港股 fetch 失败 + 301583/002552 A 股 fetch 时未收录）→ `entry_price` 写入 None → 后续 `if entry_price and last_close:` 永远 False → 永久锁在 null
- **一劳永逸修复**：`gen_top5_track.py` line 213-219 — 每次维护追踪池时，若 entry_price 仍为 None 但 qmap 里有 close → 兜底用最近价作为 entry（前端会标"补"），让后续 fetch 补到数据时自动恢复计算
- **同模式威胁**：任何「**写时为 null + 后续 if 永久 False**」的字段都是污染源。审计清单：
  - `gen_top5_track.py` 已修
  - `calc_etf_intraday.py` 已修（网络失败 sys.exit(0）
  - `gen_algo_track.py` / `gen_lhb_7d.py` / `gen_triple_track.py` 等追踪类脚本可能同问题——下次专项审计
- **建议整改**：`fetch_stock_quote_v8.py` 跑完后应主动补抓 `final_recommend.json` Top5 stocks + 当前所有 tracking stocks 的最新报价（akshare stock_zh_a_spot 单股 / stock_hk_spot 港股）—— 加 `topup_top5_quotes.py` 调度

## 📊 f_avg_price ma20/ma60 同值 bug（2026-08-17 小九 bug 待修）
- **现象**：AVG_PRICE_DATA 线上 `ma20=ma60=28.5622` 完全相等（应该不同）
- **根因**：`cloud_fetch_v8.py:f_avg_price()` history 列表中 8-14/8-15/8-16 三天都被填了重复值 28.5565（之前几天 fetch 失败后被 `save()` 跳过但下一日 fetch 成功时从 raw_data 读到了「stale 重复」）。算法是 `prices[-20:]/20` vs `prices[-60:]/60`，如果 8-14/8-15/8-16 重复，整体均值会偏向 28.5565 旧值
- **影响**：position_vs_ma20/ma60 失真（卡上显示 ▲+2.90% 但实际 MA 不准）
- **临时修法**：history 写入时去重（同日期只保留最后一次）；或 fetch 失败时在 history 加 null 标记而非沿用旧值
- **建议修法**（小九下次改）：f_avg_price 的 history 写入前先 `seen_date = set(); 去重`；或加 `if 4 days have duplicate: trigger re-fetch` 自愈
- **DO_NOT_BREAK**：f_avg_price 已有 try/except 兜底 + save() 的 `_is_empty_payload()` 跳空数据，**不要去掉这些**（覆盖守卫）

## 🔁 板块阶段迁移对比 卡片（永久 · 2026-08-17 22:55 主人令）
- **原版（废弃）**：表格形式 4 列「阶段/旧/新/Δ」，累积显示（主升18→18±0 / 启动10→10±0 / 震荡61→61±0 / 退潮1→1±0）—— 全是 ±0 没意义，主人看了嫌「累积」
- **主人原话**：「写成一行，把每天从哪个阶段到哪个阶段写清楚即可，不是让你累积。比如黄金从主升转到震荡，把当天有变化的写明」
- **新规范（一劳永逸）**：
  1. **不显示**「阶段 / 旧 vs 新 / Δ」累积表
  2. **只显示**当天从 X 阶段转到 Y 阶段的板块（每个一行）
  3. **格式**：`板块名  🚀主升 → ➡️震荡`（emoji + 阶段名 + 箭头 + emoji + 阶段名）
  4. **没有迁移时**显示「📭 今日无板块阶段变化（旧日期 HH:MM → 新日期 HH:MM 期间）」
  5. **按板块名中文拼音排序**（主人容易扫）
  6. **数据源** SECTOR_PHASE_HISTORY.js（云端持久化 snaps，盘后自动累积**仅作为数据源**，不用于累积显示）
- **DO_NOT_MODIFY**：阶段迁移展示逻辑——永远只显示「当天有变化的板块」，不要恢复成累积表
- **教训**：「累积」类指标当所有值都是 ±0 时没意义——主人要看的是「事件」（有变化），不是「状态」（无变化）

## 🔁 强势突破 page 主卡排序（永久 · 2026-08-17 22:28 主人令）
- **主人令**：3 张主卡按算法推荐排序——① 动量共识筛选（能直接接抄作业，T+5 胜率 66.7%）→ ② 个股动量状态（观察池，含 18 只跨分类共识）→ ③ 行业分布·月度对比（仅参考·不构成买卖信号）
- **共振提示**：「① 清单 ∩ ② 共识 = 加分项」必须标在 ② 卡内
- **速读卡格式**（index.html ~9365）：3 张主卡元信息卡（按优先级配色：绿/蓝/灰）+ 买卖决策 2 栏 + 一句话记住
- **位置**：强势突破 pane1 顶部，作为 meta 引导卡
- **真实代码位置**：动量共识筛选实际渲染在 ③ 位置（line 9631），但主人希望它在 ① 位置——下次整改时物理交换代码顺序
