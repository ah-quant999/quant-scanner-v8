# 交接单 · ALGO_BACKTEST_COMPARE 孤儿全链退役 + 死代码摘除 + 4 处错注纠正

- **发件**：阿狸咪的工程师（家机 `alimi-cn`）
- **收件**：小九的工程师（单位机 `lemoncat-cn`）
- **时间**：2026-09-20 07:05 CST
- **基线 tip**：`148b28662598ed726fd8fe3a714f8d8554886d69`
- **性质**：算法链清废 + 前端死代码摘除 + 历史注释纠错（**不新增功能、不改算法口径**）

---

## 一、一句话摘要

`data/ALGO_BACKTEST_COMPARE.js` 这条链是**烧电又没人看的孤儿**：脚本在 E 批跑、产物在上传，
但它的唯一消费卡属主人 **2026-09-02 明令删除**的模块，**全站零生效路径**。
本轮把它从「生产 / 上传 / 门禁豁免 / 前端死代码」四处一并摘除，并纠正此前 3 处误导性注释。

---

## 二、根因（怎么发现的）

### 2.1 起点：我上一轮自己造出的一处口径矛盾

2026-09-20 凌晨修 build 全红时，我恢复了 `data/maharo_insights.js`，**顺带也把
`data/ALGO_BACKTEST_COMPARE.js` 一起恢复了**（当时判断它「被周清理误删」）。
但同一轮我又在 `pre_deploy_audit.py` 与 `logic.html` 的注释里写「该卡无生效路径」。

⇒ **「文件已被我恢复」与「注释说它已不存在」自相矛盾**，这种注释比没注释更危险。

### 2.2 定性：CDP 真浏览器实测（决定性证据）

用 Edge CDP 走**真实切页路径**（`switchSec('ul')`，非 `--dump-dom` 静态抓取）：

```
unlistedPanel 初始 len        = 0
switchSec('ul') 调用           = called
sec-ul offsetHeight           = 6835        ← 真显示了
unlistedPanel.len 切后         = 262174      ← renderUnlisted 真的完整执行了
marks                         = ["start","end-ok"]   ← 无异常、无错误卡
ul-pane 数                     = 0           ← 但 pane 一个都没建
ulPaneObserve                 = true        ← 「观测类」pane 存在（当前唯一在册子页）
ulPaneStrong 是元素吗           = false       ← 强势突破 pane 根本不生成
两套算法回测对比 是元素吗         = false
window.ALGO_BACKTEST_COMPARE   = undefined
```

⇒ `renderUnlisted` **跑完了**（262174 字符），但 `ulPaneStrong` 那段**已不在生成列表**内
（`index.html` 内注：「暂未上架仅剩「观测类」一个在册子页」+「2026-09-02 主人令：
强势突破 pane、模块去向索引、**两套算法回测对比 全部删除**」）。

### 2.3 硬依赖核查（判「能否安全摘除」）

去注释后扫描全仓：

| 文件 | 去注释后引用 | 定性 |
|---|---|---|
| `algorithms/gen_backtest_all_algos.py` | 4 处 | **全是注释**（`scan/parse_algo_compare` 真代码调用 **0 处**） |
| `logic.html` | 6 处 | 死代码段（本次摘除） |
| `scripts/algo_backtest_compare.py` | 8 处 | 自我引用（脚本本身退役） |
| `.github/scripts/pre_deploy_audit.py` | 1 处 | 注释（本次纠正） |
| `algorithms/run_algorithms.py` | 0 处 | 仅注释 |
| `api_push_raw.py` / `update_v8.py` | 0 处 | 仅注释 |
| `algorithms/verify_chain_consistency.py` | 1 处 | `DATA_VAR_EXEMPT` 豁免表（本次移除） |

⇒ **零硬依赖**，摘除安全。

---

## 三、本轮改动清单（8 个文件）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `algorithms/run_algorithms.py` | ORDER[48] 摘 `scripts/algo_backtest_compare.py`；**STAGES["E"] 同步摘**（两处成对）；留墓志铭三条实证理由 |
| 2 | `api_push_raw.py` | 摘 `data/ALGO_BACKTEST_COMPARE.js` 上传登记；留墓志铭 |
| 3 | `logic.html` | 删「📊 两套算法回测对比」整段死代码（原 L6651-6704，**-3128 B**）；留墓志铭；**「🎯 动量共识筛选」卡保留不擅动** |
| 4 | `scripts/algo_backtest_compare.py` | **退役删除**（无生产者/无消费者） |
| 5 | `data/ALGO_BACKTEST_COMPARE.js` | **退役删除**（git 树内移除） |
| 6 | `algorithms/gen_backtest_all_algos.py` | 纠正墓碑②的过时表述（原「已不存在(404)」→ 说明现在确实已退役） |
| 7 | `.github/scripts/pre_deploy_audit.py` | 纠正 295-306 错注（原写「该数据源已删除…本页无 sec-ul 容器」→ 改为完整退役链路 + CDP 实测） |
| 8 | `algorithms/verify_chain_consistency.py` | `DATA_VAR_EXEMPT` 移除 `ALGO_BACKTEST_COMPARE`（豁免表不该留已退役幽灵） |

> ⚠️ **保留不动的部分**：`logic.html` 里「🎯 动量共识筛选」「H反推」两卡**未删** ——
> 它们在 `ulPaneStrong` 内、同样无生效路径，但**主人未明令删这两张卡**。
> 按「判过时看有无生效路径」铁律**只删有主人明令的段**，不擅自扩大删除面。**待主人拍板。**

---

## 四、离线门禁复现（推送前）

在仓库外隔离目录 `_gate_r391/` 用**改后版本**搭环境实跑：

```
✅ [1/8] py_compile: 13 个 .py 文件 0 错误
✅ [2/8] new Function: 28 个 inline script 块 0 错误
✅ [3/8] data 完整性: data/*.js 数量=99, 全部 > 100B
✅ [4/8] align_logic_ops: EXIT 0（逻辑详解页与真 workflow 对齐）
✅ [5/8] workflow YAML: 30 个 workflow 全部有效
✅ [6/8] HTML 数据引用: 178 个本地 script 引用全部存在（4 页）
✅ [7/8] gate 头注一致
✅ [8/8] 心跳产物名一致
🎉 8 项全部通过 → deploy 可继续        EXIT = 0
```

**`verify_chain_consistency.py`**（带 raw_data）：

```
结论: OK（含告警级提示，请人工复核）    EXIT = 0
★ ALGO_BACKTEST_COMPARE 出现次数 = 0    ← 摘除后零新增告警
```

**inline JS 二次独立校验**：`logic.html` 6 块 / `index.html` 28 块，`new Function` 全通过、0 失败。

---

## 五、给小九的三条提醒

1. **不要再把 `algo_backtest_compare.py` 挂回 E 批**，也不要在 `api_push_raw.py` 里重新登记
   `data/ALGO_BACKTEST_COMPARE.js`。若要恢复该对比能力，须**先恢复前端卡**（主人令）并重写生成器与解析器。
2. **`DATA_VAR_EXEMPT` 的语义 = 「已知且正当的自管产物」**，不是「已退役的幽灵收容所」。
   今后退役产物应从该表移除，否则会掩盖真实缺口。
3. **查 GitHub 配额别信 `/rate_limit` 端点**：本轮实测它返回缓存值（显示 `remaining=5000`），
   而真实响应头是 `X-RateLimit-Remaining: 0 / Used: 5000`。**判据只看真实 API 的响应头。**

---

## 六、待主人拍板（本轮未动）

1. `ulPaneStrong` 内剩余卡（「🎯 动量共识筛选」/「H反推」）是否一并清理？
   —— 同样无生效路径，但主人未明令。
2. 审计报告遗留两项：P1-4 分数刻度改法（A 重校分母 / B gate 后置）；
   P0-1 `_is_low` + P1-2 成本口径捆上线前的离线回测。
