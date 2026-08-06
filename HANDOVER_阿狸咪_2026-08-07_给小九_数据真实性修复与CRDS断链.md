# 交接：数据真实性修复 + CRDS 上游断链（阿狸咪 → 小九）

- 时间：2026-08-07 08:0x（开盘前）
- 仓库：`ah-quant999/quant-scanner-v8`，main = `9f675ba`（已推送，CI 会自动构建部署）
- 本轮提交：`5198980`（修复）+ `9f675ba`（重建产物）

---

## 一、最重要的一条：构建流程曾在篡改「更新于」（已修，禁止回退）

### 症状
所有卡片的「更新于」永远显示为最近一次构建时刻，看起来天天都是新数据。

### 根因
`update_v8.py::_write_js` 内的 `_pick_ts`：

```python
# 旧（错）
candidates = [t for t in (existing, mtime_ts, now_ts) if t]
return max(candidates)      # now_ts 永远最大 → 每次构建都覆盖成当前时间
```

`v8_build_deploy` 每天被 push / workflow_run 触发多次，于是**每一次构建都把全站
`data/*.js` 的 `update_time` 刷成构建时刻**。数据陈旧被完全掩盖 = 造假。

### 已改为
```python
# 新（真实优先，禁止改回 max）
if existing: return existing      # 源数据自带的真实产出时间
if mtime_ts: return mtime_ts      # 源文件落盘时间
return now_ts                     # 兜底
```
并额外写入 `build_time` 字段（仅供排障，**前端不得当作「更新于」展示**）。

### 连带影响（需要你知道）
1. 页面上的「更新于」从今天起是**真时间**，某些卡会显示「6天前」——那是真相，不是 bug。
2. 「今日已跑完」胶囊在开盘前（09:30 前，交易日归上一日）不再误隐藏。

---

## 二、CRDS 卡上游断链（**需要你在生产节点排查**）

这是修复后暴露出来的真问题，我在阿狸咪只做了诊断，未动生产。

### 事实
| 项 | 值 |
|---|---|
| `data/CRDS_CARD_DATA.js` 真实 `update_time` | **2026-08-01 15:29:53** |
| `raw_data/crds_card_data.json` 最后一次入库提交 | `f64e326`（8/1 走 v6 同步桥） |
| 阿狸咪本机 `out/crds_result.json` | 2026-08-01 13:20（本机 out/ 整体停在 8/1，因算法链已迁云端，本机数据无参考价值） |

### 判断
`crds_card_data.json` 历史上由 **v6 同步桥**（`sync_v6_to_v8.py` 的 `crds_result.json → crds_card_data.json` 映射）供给。v6 全退役后，这一路断供。
v8 自有链里 `algorithms/run_algorithms.py` 第 63 行确实列了 `calc_crds.py`，`algorithms/stage_to_raw.py` 也复用 `V6_TO_V8` 映射搬运，链路理论上是通的——**但云端产出没有进 raw_data**。

### 请你确认（生产节点）
1. 云端 `v8_algo_cloud` 最近几次运行里，`calc_crds.py` 这一步是成功还是异常/跳过？
   - 该脚本自带保护：K 线连续失败 > 40 次会打印
     `[WARN] 东方财富 K 线连续失败过多，无法计算今日 CRDS，保留上一份 crds_result.json 数据`
     然后**不写文件** → 上游长期静默陈旧。优先在日志里搜这句。
2. 云端 runner 上 `out/crds_result.json` 的时间戳是多少？
3. `stage_to_raw.py` 有没有把它提升到 `raw_data/crds_card_data.json` 并提交？

### 前端已做的兜底（不掩盖问题）
CRDS 卡顶部新增红色警示条，停更 ≥2 天自动出现：
> ⚠️ 本卡数据已停更 6 天（最后产出 6天前 15:29），下列内容为历史快照，请勿据此决策；修复中。

同时「今日已跑完」胶囊对该卡正确地**不显示**（因为确实没跑）。

---

## 三、同批修掉的三个前端硬伤

| # | 问题 | 位置 | 修法 |
|---|---|---|---|
| 1 | 「今日已跑完」胶囊读 `update_time`，被构建时间污染后在开盘前误隐藏 | tc / crds / fv 三处 | 改读 `data_time \|\| gen_time \|\| update_time` |
| 2 | 暂未上架「今日判定」卡头**永远空白** | index.html L3987 | 该 IIFE 立即执行时 `v8CardHeader` 尚未定义（定义在后面的脚本块）→ ReferenceError 静默吞掉整段。改为注册 `window.__renderJudgmentHeader`，由末尾 `initCardBadges` 统一触发；并在定义处显式 `window.v8CardHeader = v8CardHeader`（该块整体在 IIFE 内，函数不会自动挂 window） |
| 3 | 「四量终极」tab 点击无反应 | `renderStTab` 内 `renderFourVolume()` 裸调用（跨块） | 改走 `window.renderFourVolume()` + try/catch |

`guard_index_js_tdz.py` 现已报「✅ 无先用后定义风险」。

---

## 四、修复后的全站真实新鲜度快照（2026-08-07 07:5x）

- **正常（08-06 20:28 ~ 23:33 盘后链产出）**：候选池 / 黄金池 / 三重共识 / 驾驶舱 / 龙虎榜 / 机构 / 危机雷达 / 涨停热力 / 板块 RS / 宏观 / ETF / 四量终极 等 40+ 模块 ✅
- **今晨产出**：`JUDGMENT_DATA` 06:57 ✅
- **陈旧**：`CRDS_CARD_DATA` 08-01（见第二节）
- **边缘**：`STOCK_PROFILE` 08-05 16:00（2 天，按周更口径可能正常，请确认预期频率）
- **无 `update_time` 字段**（不走 `_write_js`，另行生成）：`BLOAT_CHECK` / `HEALTH_CHECK` / `RUNNER_STATUS_HEALTH` — 建议后续补时间戳，否则前端无法判新鲜度

---

## 五、门禁记录（本轮全过）

- `node --check` 内联脚本块 23 / 23 通过
- `guard_index_js_tdz.py` ✅ 无风险
- jsdom 烟测：仅剩 `fetch is not defined`（jsdom 环境限制，浏览器无此问题）
- 胶囊实测：`_tradeDayStr()` = 2026-08-06；四量终极「今日已跑完」显示 ✅；CRDS 胶囊隐藏 + 陈旧条显示 ✅；今日判定卡头 1055 字符 ✅

---

## 六、给你的两条硬约束

1. **`update_v8.py::_pick_ts` 禁止改回 `max()`**，注释已写明原因。任何"时间戳看起来太旧"的诉求，
   都必须去修数据生产端，不能改显示端。
2. 前端新增/修改卡片时，**跨脚本块调用的函数必须走 `window.X`**，或把定义 HOIST 到调用之前；
   裸调用会在加载期抛 ReferenceError 并静默吞掉整段 IIFE（本轮两例都是这个坑）。
