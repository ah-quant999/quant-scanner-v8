# 交接件：主题空间卡改造「三项齐」单层直出（阿狸咪 → 小九）

- **时间**：2026-10-02 19:4x（北京时间 CST+8）
- **执行机**：阿狸咪（家机 alimi-cn）
- **触发**：主人截图拍板——「我要这三点都齐的」（概念+业绩正向+ROE 三项齐），B/C 档全删；确认 FUNDAMENTAL_QUALITY 覆盖够后「就修吧」。

## 一、改动内容（提交 `deb372ec79e817b1caafeeb8b1cd0337b526b3cf`，parent `1279aae`）

| 文件 | 改动 |
|---|---|
| `index.html` | 主题空间卡：① 证据源升级 `roe_largecap.top`（大市值 30 只窄门）→ `window.FUNDAMENTAL_QUALITY`（候选/金股池 A 股 ROE+营收增速，Baostock 日更，503 只）；② A/B/C 三档全删，只留「三项齐」单层直出 = 概念命中 ∩ 业绩正向（营收增速>0 或预告预增）∩ ROE≥10%；按板块资金净额降序、每主题封顶 40 只；③ 新增 `<script src="data/FUNDAMENTAL_QUALITY.js">` 注入（戳 `e87ea43011`）；④ FQ 未就绪走同款重试分支；⑤ 卡内文案/口径说明同步改写 |
| `update_v8.py` | ① `DATA_SOURCES` 登记 `fundamental_quality.json → FUNDAMENTAL_QUALITY`（防「raw 已新、js 永旧」半截更新，与 overseas_markets/final_recommend 同类预防）；② `_write_js` 补 `newline=''`（修 Windows 本地跑批尾行 CRLF 漂移） |
| `data/FUNDAMENTAL_QUALITY.js` | 新产物，经 `update_v8._write_js` 生成（106999B，纯 LF），update_time=2026-10-01 09:09:31（源 raw 真值） |

## 二、实测口径（模拟脚本 + Node 实跑双验证）

- 质量合格池（ROE≥10 且营收正增）A 股 **104 只**；与概念命中交集后**三项齐唯一股票 70 只**。
- 各主题：算力·CPO 50（→封顶 40）、数据要素 22、固态电池 16、人形机器人 15、AI医疗 5、创新药 3、低空·航天 1。
- Node 实跑：compute=40 只封顶 ✓、aero=1 只（睿创微纳）✓、动态主题正常 ✓、FQ 缺失走重试不炸 ✓、无 A/B/C 档残留 ✓。
- 门禁 `pre_deploy_audit.py` **14/14 全绿**（含 [10/10] index 核心标记——本改动不涉受保护标记）。

## 三、小九需知（重要）

1. **无需动作**：下轮 build（云端或本机）会经 `DATA_SOURCES` 自动重建 `data/FUNDAMENTAL_QUALITY.js` 并自动打 `?v` 戳；raw 由 `algorithms/fetch_fundamental_quality.py` 日更（Baostock，B 批链）。
2. **⚠️ 别把 `update_v8.py` 回退**：本次映射登记 + `newline=''` 都是修 bug；若你本地有旧副本，拉远端为准。
3. **全站只此一处「A 档」语义变更**：主题空间卡的 A/B/C 档已删；**三重共识卡等处的「基本面A档」是另一套口径（TOP10∧质量），未动**。
4. 口径提示（卡内已写明）：质量库=候选/金股池宇宙（503 只 A 股），库外概念票无法验证一律不列——这是主人拍板的接受项。
5. 节后观察：`data/FUNDAMENTAL_QUALITY.js` 应随每日 build 自动刷新 update_time；若停更，查 `fetch_fundamental_quality.py`（Baostock 超时老毛病）。

## 四、纪律记录

- 基线=远端实时 tip（1279aae，非本地工作区）；Git Data API 单提交 force:false；回读三 blob 逐字节 IDENTICAL。
- 渲染验收四件套：全 inline script 语法（门禁内）+ Node 抽函数实跑（正/反/缺数据三态）+ 门禁 14/14 + 回读逐字节。
- 未碰：三重共识/驾驶舱/选股算法链/其它数据产物。
