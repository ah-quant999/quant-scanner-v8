# HANDOVER 小九 → 阿狸咪 · 2026-09-16 18:00 · AI速览「ETF资金」条品种块改版（代码另起一行）

## 一、主人令（两连）

1. 16:55 「AI速览这 2 条写出具体的 TOP5 流入和流出」→ 已改：ETF资金条给具体品种 TOP5、个股异动条由各 2 只扩到各 5 只。
2. 17:48 「ETF 的代码写在名字下方，要不会很长」+「名称下面的代码，字小一点，不要占用太大版面，字色提亮」→ 本轮改的就是这条。

## 二、本轮改了什么（单文件 · 单点）

**改动文件**：`algorithms/gen_market_brief.py`（唯一改动文件，未碰 index.html / 未碰 data/）

| 项 | 内容 |
|---|---|
| blob | `6d83a706a370` → `579d3f90a38d`（本地=远端逐字节一致） |
| 推送 | Contents API 单文件（`scripts/api_put_file.py`，带当前 blob sha ⇒ 天然 409 冲突检测） |
| commit | `1db9ef7b6ab6`（force:false，未整仓推） |
| 位置 | `detect_anomalies()` 内 ETF 段的 `_etf_top5()` |

**版式前 → 后**（每品种由「一行长串」改为「两行小块」）：

```
改前：净流入TOP5：科创50ETF华夏 +10.66亿、通信ETF国泰 +4.80亿、…
改后：净流入TOP5：[科创50ETF华夏 +10.66亿]   [通信ETF国泰 +4.80亿]  …
                   588000                      515880
```

落地实现（每个品种一个 `inline-block` 小块，代码在 `<br>` 之后）：

```html
<span style="display:inline-block;vertical-align:top;margin:0 16px 0 0;line-height:1.45;white-space:nowrap;">名称 +x.xx亿<br><span style="font-size:11px;color:#cbd5e1;">代码</span></span>
```

- 代码行：**11px**（正文 13px）、字色 **`#cbd5e1`**（比 `var(--dim)` 提亮）、不换行。
- 品种之间**去掉中文顿号**：inline-block 自带 `margin-right:16px`，顿号会挤在两行块的基线上错位。

**为什么"横向零增宽"**：块宽由第一行决定（`名称 +金额` ≈ 137px），代码行仅 6 位数字 ≈ 33px < 137px ⇒ 块宽不变。若按旧写法把代码续在名字后（`科创50ETF华夏(588000) +10.66亿`）块宽会涨到 ≈182px（+33%），5 个并排就溢出。这正是主人要的效果。

## 三、两条不可破的约束（改前已确认，改时必须守）

1. **`anomalies` 上限 6 条、当前正好用满 6 条**（`detect_anomalies()` 末尾 `unique[:6]`）。ETF资金条**只能是一条**，拆成「流入/流出」两条会把后面的「个股异动」静默挤掉。故一律用 `" ｜ "` 分段合并。
2. **个股异动的流入/流出两条在渲染层被合并成一行**（index.html 约 L2266–2284，按 `主力大单流入/流出` **前缀**匹配）。改文案必须保留前缀，否则合并失效、裂成两行。

## 四、本条的 HTML 是有意约定（给阿狸咪的红线）

ETF资金条的 `text` 现在**合法携带行内标签**，这不是脏数据：

- 前端 anomalies 渲染走 `innerHTML`（index.html ≈ L2286 `h += a.text`）⇒ `<br>`/`<span>` 正常生效。
- 该条 `signal` 由生成器**显式给定**（green/red），因此 `lightDot(a.signal || _fallbackLight(a.text))` 不会走 `_fallbackLight()` 的文本分支。
- 数据链 `raw_data/ai_market_brief.json` → `data/AI_MARKET_BRIEF.js` 是 `json.loads` → `json.dump` 对称序列化（update_v8.py L332/L724/L733）⇒ 双引号自动转义，**不会二次转义、不会损坏标签**。

⚠️ **请勿**：① 对这条 `text` 做 HTML 转义（escape/`html.escape`）后处理；② 在其它消费方按"纯文本长度"或"不含尖括号"做校验（会误判）。已全仓核查过消费方：`update_v8.py`（只读键名）、`scripts/audit_empty_cards.js`（只判整体非空）、`logic.html`（只做 `<script src>` 与表格登记），均不解析本条文本。

## 五、三件套（已做，全部通过）

| 环节 | 手段 | 结果 |
|---|---|---|
| ① 改后校验 | `py_compile` + 离线 `gmb_test` 用**真实 16:30 收盘数据**复跑 | ✅ 6 条不变、ETF 条出 TOP5 且带代码换行 |
| ② 远端真值核验 | Contents API 读回 `algorithms/gen_market_brief.py` 与本地逐字节比对 | ✅ `579d3f90a38d`，37556 bytes 完全一致 |
| ③ 真实渲染验证 | Node + jsdom **只渲染 anomalies 段**（不做全页解析）：复刻 index.html 渲染结构后断言 | ✅ ETF 条 `行内 <br>=10`、`代码小字块=10`、首块子节点序列 `#text → BR → SPAN`；其余 5 条零变化 |

另：降级路径复测（抽掉 `etf_daily_monitor.json`）不崩、行为与改前一致，无回归。

## 六、给阿狸咪的注意点

1. **本文件今天被单文件 API 推过两次**（16:xx 首轮 TOP5、18:00 本轮代码换行）。接班请以 `git show origin/main:algorithms/gen_market_brief.py` 取真身；本机 `E:/qs_workspaces/quant-scanner-v8` 的 main 线是**幽灵线（领先 113 / 落后 1）**，暂存区有陈旧条目 —— **不要整仓 commit/push**，单文件走 API。
2. 生成器是「云端 CI 跑」的：本地落盘/推仓 ≠ 页面立刻变。要 AI速览 出数据，需一轮 `🇨🇳 v8 中国数据抓取(云端)`（AI_MARKET_BRIEF 档位 = `intraday,post_close`）重算，随后 `build_deploy` 部署。
3. **别再往回加**：ETF资金条不要拆成两条、不要退回"只报分类第一名"、个股异动不要退回各 2 只。
4. 若主人后续要求"代码不要显示"或"改回一行"，只动 `_etf_top5()` 一处即可（其余 5 条异动不受影响）。

## 七、待办（顺延）

- ① 等本轮 `cn_fetch` + `build_deploy` 跑完，核线上 `data/AI_MARKET_BRIEF.js` 出现 `<br>` 即生效。
- ② 观察 `guard_index_sections.py` 那次 failure（head=`3fde9e2187`，17:56 构建，疑为他人提交触发的护栏误判，与本轮改动无关）是否复发。
- ③ 主人此前顺延项：刷新机制（已明确不查）、共振日历（已出数据、不再跟）。

—— 小九的股票专家 2026-09-16 18:00
