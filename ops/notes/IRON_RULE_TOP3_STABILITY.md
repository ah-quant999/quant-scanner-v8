# 铁律 · TOP3 停滞自查协议（2026-11-01 主人令固化）

> 适用范围：终选输出卡（数据源 `data/TOP10_DAILY.js` / `TOP10_DAILY.top10`）前三名连续多日不变时的强制自查动作。

## 触发条件
终选输出前三名（按 `total_score` 降序的 rank 1/2/3）连续 **≥3 个交易日**未变化（自然日口径，以 `raw_data/history/top10_daily_<YYYYMMDD>.json` 为准）→ **立即自查并写入本铁律**，不得当作"正常"带过。

## 自查清单（按顺序，每条必须给明确结论）
1. **先证伪"死卡/显示冻结"**：比对每日 `top10_daily_<date>.json` 的 `update_time` 与分数。
   - `update_time` 每日更新、且 `total_score` 逐日变化（例：远东 11-01=42.1 / 10-30=43.3）→ **不是显示冻结**，是算法真实输出。
   - `update_time` 停更 / 分数不变 → 才是真死卡（查算法链 cron / `run_algorithms.py` 是否实际跑、是否被静默跳过）。
2. **核对输入新鲜度**（以下数据源必须每日刷新，任一停更都会拖慢轮换）：
   - `data/STOCK_WINRATE.js`（`update_time` 应为当日）
   - `raw_data/gold_pool.json`（金股池，应为当日）
   - 候选池 history 末根 close（滞后应 ≤1 日）
3. **区分两类"稳定"**：
   - ✅ **高信念稳定**：头名领先亚军人 15+ 分（例：远东 42.1 vs 德福 24.6，差 17.5）→ 真实高信念输出，**非 bug，无需"修"**。
   - ❌ **冻结式稳定**：头名与亚军人分差 <5 且分数多日不变 → 真 bug（查 `jinzuan` / `has_chan` 信号源是否停更）。
4. **缠论源陈旧属已知限制（勿误判）**：ima「缠论买点每日推荐」经本机连接器拉取，云端算法链无法刷新；`chan_buy_point_signals.json` 常停更（已确认 2026-09-19 后未更）。它**仅透出展示，不参与 HC 筛选**（HC 的 `chan` 来自日K线实时 `has_chan`）。卡片已自动标"⚠ 缠论源陈旧N天"。**不要因此误判 top3 卡死**。

## 根因处置
- 真死卡 → 查 `v8_algo_cloud.yml` / `v8_algo_run.yml` 是否派发；手动 `repository_dispatch` 补算。
- 缠论源陈旧 → 本机（小九/阿狸咪）重跑 ima 连接器 `fetch_media_content` 落盘 → `v8/fetch_chan_buy_point.py` 解析；属人工/local 步骤，算法链不自动覆盖。
- `consecutive_days` 自追踪器当前恒为 0（金股池 per-stock signal history 未持续维护，窗口仅 09-07~10-10）→ 已知缺口，需 `renormalize_top10_history.py` 接力，待修。

## 铁律
- 自查结论必须写入本文件 + 当轮交接件，**禁止"看起来没变就当正常"**。
- **高信念稳定 ≠ bug**，严禁为制造"变化"而人为扰动算法（违反"最真实最科学"北极星）。
- 任何实质性改动走改后三件套（审计 + 四方对齐 + 推仓 + 交接），防覆盖回旧版。
- 推仓必须基于 `origin/main` 快进、禁止 `--force`、禁止覆盖远程历史。
