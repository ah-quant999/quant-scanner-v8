# 交接：RPS 机械误删致 IndentationError（阻断全站 deploy 约 5.5 小时）+ 周末两处数据异常核验

- **发件**：阿狸咪的工程师（alimi-cn）
- **收件**：小九（lemoncat-cn）
- **时间**：2026-09-13 20:18 CST
- **关联提交**：`4f2fc4cae`（修复）｜`e97ac47d4`（修复后首次 build 成功）

## 一、一句话

`algorithms/auto_run_dn_algorithm.py` 在 RPS 下线时被**机械删除**留下空壳 `if`，**语法层面无法解析** ⇒
① 云端 `v8_build_deploy` 的 `pre_deploy_audit`（py_compile）恒红，**今日 09-13 连续 26 次构建部署失败（15:33–20:08 CST）**；
② 该脚本是 `data/H_AUTO_BUY.js` 的**唯一生产者** ⇒ 该卡断更。
现已一劳永逸修复，**20:09:51 起恢复成功**。

## 二、取证（全部实测，可复核）

### 2.1 CI 真日志（run `34746094232`｜runner `lemoncat-cn`｜09-13 16:18:15 CST｜algo 链）
```
▶ auto_run_dn_algorithm.py  (16:18:15)  [监督执行·静默杀≥15min]
     File "...\algorithms\auto_run_dn_algorithm.py", line 190
   IndentationError: expected an indented block after 'if' statement on line 189
   • auto_run_dn_algorithm.py  ← 退出码 1 | IndentationError: expected an indented block
   • track_h_auto_buy.py       ← 监督器静默杀(>15min 无输出)
```

### 2.2 Actions API 统计（`v8_build_deploy.yml`，09-13 当日）
| 结论 | 次数 |
|---|---|
| failure | **26**（连续窗口 `6e6c9e693` 15:33 → `f1bcbc577` 20:08） |
| success | 23（修复后 `4f2fc4cae` 20:09:51 起恢复） |
| cancelled | 1 |

⚠️ **掩盖效应**：同期 GitHub 原生 `pages build and deployment` **一直 success**（静态页照常发布）
⇒ 表面「站点没挂」，实际**数据重生成/部署链全灭**。这类「半挂」必须看 `v8_build_deploy` 而非只看站点 200。

### 2.3 全仓语法扫描（远端 tip `e97ac47d45`，materialize 166 个 `.py`）
`py_compile` **全部通过** ⇒ 无同类残留损伤（不是还有别处也被删坏）。

### 2.4 孤儿引用扫描
`calc_stock_rps` / `_rps` 在 `algorithms/`、`.github/`、`update_v8.py` 中**只剩注释与历史文档**，无任何代码引用
（`run_algorithms.py` 已清干净）⇒ 该项无剩余欠账。

## 三、改了什么（`4f2fc4cae`，单文件 16+/12-）

`algorithms/auto_run_dn_algorithm.py::_unified_query_kline()`：
由「延迟 `import calc_stock_rps as _rps` 取 `_query_kline`」改为**显式恒返回 `None` 的占位**。
理由：`calc_stock_rps.py` 已随 RPS 一并删除 ⇒ 该「统一三级兜底取数链」**不存在**；
调用点（L273 `if fn is not None:`）已有完整降级：→ 本地缓存（新鲜/陈旧）→ gtimg 老路径。行为等价、不假成功。

## 四、修复有效性判据

- `v8_build_deploy`：20:09:51Z `4f2fc4cae` **success**；20:12:15 `e97ac47d4` 产出 build 提交，
  `data/HEALTH_CHECK.js update_time = 2026-09-13 20:12:08`（新鲜）✅
- `data/H_AUTO_BUY.js` **尚未翻新**：`update_time = 2026-09-12 21:56:26`。
  其生产者即本脚本（+ `track_h_auto_buy.py`），今天 15:47 那次链跑批 step9 里本脚本已退出码 1
  ⇒ **下一次链跑批（今晚夜窗）应翻新**；若仍不动，按「step 9 软失败」继续追。

## 五、⚠️ 顺带核验发现（**我未动手，请小九核查**）

1. **26 次构建失败窗口（15:33–20:08）内数据重生成链未通过审计**：同期 `v8 cn fetch` 链仍有推送
   （如 `b8c191f65` 16:59），请确认 **是否有卡因这段窗口漏更新**。
2. **金股池数据回退**（疑真问题）：`data/GOLD_POOL.js` 与 `raw_data/gold_pool.json` 由
   `update_time = 2026-09-12 00:53:46`（`total_count 253` / `candidate_total 875`）
   **回退**为 `2026-09-11 15:00:00`，发生在 `b8c191f65`（v8 cn fetch，09-13 16:59）。回退方向 = 新值更旧，需定因。
3. **候选池自 09-11 15:00 未再产出**：同一 run 的问责步实测原文：
```
##[error]B 批跑完但选股批次仍非本数据日盘后产出（闸门裁决=未就绪 0/9，执行=success）—— 假成功，必须排查
候选池   ❌ 陈旧 1 天   2026-09-11 15:00:00   必需   raw_data/candidate.json
金股池   ❌ 陈旧 1 天   2026-09-11 15:00:00   可选   raw_data/gold_pool.json
         ↳ 基准日 2026-09-12，产物停留在 2026-09-11
```
   请核对闸门 `chain_day()`（`v8_stage_gate.py:395+`）在「09-12 周六 + 09-13 周日 **双非交易日**」下的
   基准日口径是否为已知设计；**若 09-12 被当成交易日，则周末必红**。我**未定论**，只报事实。
4. **`track_h_auto_buy.py` 被监督器静默杀**（>15min 无输出）——与 H_AUTO_BUY 停更可能双重叠加，请一并看。

## 六、小九侧待办核验（实测状态）

- 你的自动交接 `HANDOVER_小九_2026-09-13.md` 仍是 **12:05 槽位**版本（唯一提交 `ca2e6ef98`），
  **18:00 槽位未产出**；`data/RUNNER_STATUS.js` 最后上报 `2026-09-13 16:57:38`（hostname `LEMONCAT`）。
  请确认 18:00 交接自动化是否掉线。
- 我 09-13 **16:00 / 16:30 两份 URGENT 交接单**（v8 待办收敛 14 项；PE/PB 跑批验证）**尚未见回执**，请回一句进度。

## 七、未做（有意留白，等主人拍板）

- 未改任何任务面/闸门阈值、未删任何数据文件、未动仓库根 `.bak`。
- 未处置：金股池下架建议、三重共识 4⭐ vs 5⭐、策略回顾页与主表**跨页星源不一致**（前者逐行算分、后者走星级委员会）—— 等主人一句话。
