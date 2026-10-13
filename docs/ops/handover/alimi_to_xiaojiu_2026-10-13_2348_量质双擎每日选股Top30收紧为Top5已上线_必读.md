# 交接件 · 量质双擎（LQSQ）每日选股 Top30 → Top5（已推送上线）

- 交接方：阿狸咪的工程师（alimi-cn）
- 收方：小九的工程师（lemoncat-cn）
- 时间：2026-10-13 23:48 CST
- 线上提交：`e4cbb95e7d`（main tip，11 文件）
- 状态：✅ 已推送 + 远端 blob 全对表 + 线上 Pages 硬验通过

---

## 1. 主人令（唯一动因）

主人在量质双擎卡截图批示（2026-10-13）：

> 「这个太多了，才3天都90只了，没必要，每天也是按评分最高推荐3-5只就好」

即：LQSQ 从「每日归档全量打分 Top30」收紧为「每日按评分最高推 3-5 只」。取区间上限 **N=5**（保回测样本量）。

## 2. 改动清单（11 文件）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `algorithms/gen_lqsq_top30.py` → `algorithms/gen_lqsq_top5.py` | git mv 改名（97% 相似）；`TOP_N=5`；日志名次动态化（`第%d名`）；docstring「全市场直选 Top5」；factor_def 改「升序Top5（最缩量=最强）」；method 加收紧说明 |
| 2 | `algorithms/run_algorithms.py` | 4 处引用改名：L83 预算表 `"gen_lqsq_top5.py": 900,`、L200 ORDER、L379 注释、L381 STAGES |
| 3 | `algorithms/gen_backtest_all_algos.py` | L108-116 LQSQ method 文案改 Top5 口径 |
| 4 | `update_v8.py` | L82/L85 注释改 `gen_lqsq_top5.py` / 「当期 Top5 选股」 |
| 5 | `.github/workflows/v8_lqsq_bootstrap.yml` | L175 命令改 `LQSQ_PUSH=1 python algorithms/gen_lqsq_top5.py` |
| 6 | `index.html` | 8 处文案 + 归档表增「信号日」列（thead/tbody 各 1 处）；表头「📋 归档信号 · 每日 Top5」 |
| 7 | `raw_data/lqsq_history.json` | 3 个信号日各截前 5（90→15）；factor_def 改 Top5；track_start 保持 2026-10-09 |
| 8 | `raw_data/lqsq_track.json` | tracked 过滤至 15 笔；total_signals=15、signal_days=3、self_summary 重算；**update_time 保持 2026-10-13 20:52:39 不动** |
| 9 | `raw_data/lqsq_backtest.json` | method 换新文案；total_signals=15；by_period 仅 T+1 n=10 |
| 10 | `data/LQSQ_TRACK.js` | `update_v8._write_js` 重出 |
| 11 | `data/LQSQ_BACKTEST.js` | `update_v8._write_js` 重出 |

index.html `?v` 同步：`LQSQ_TRACK c2886edd59→97504b364c`、`LQSQ_BACKTEST a765309b4c→c450b7d391`。

## 3. 数据口径关键决策（必读，防未来函数质疑）

1. **归档截断而非只改未来**：主人明言「90 没必要」，故 3 个历史信号日也各截前 5。截断依据 = 各日**自身时点**的因子比率排序切片（`scored.sort()` 升序取前 5），即新规在该日当时可得信息下的同一选择——**无未来函数、无当前股池幸存者偏差**。
2. **收益不重算、update_time 不伪造**：15 笔的持有期收益数字沿用 runner 20:52 轮真算值；`update_time` 保持 `2026-10-13 20:52:39` 不变（防「白名单刷新时间」式造假）。旧 90 只归档在 git 历史可溯（blob `4fb32e68a1…` 一线）。
3. **聚合器不强跑**：`gen_backtest_all_algos.py` 有 time_gate（主人 2026-08-20 铁令「算法一律由云端定时任务跑」），未本地覆盖；`BACKTEST_ALL_ALGOS.js` 的 LQSQ 行明日 E 批自愈。

## 4. 每日 Top5 名单（三日高度稳定）

| 信号日 | Top5（按当日因子比率升序） |
|--------|--------------------------|
| 2026-10-09 | 航天环宇 688523、震有科技 688418、优刻得 688158、阿特斯 688472、容百科技 688005 |
| 2026-10-12 | 航天环宇 688523、震有科技 688418、优刻得 688158、阿特斯 688472、时代电气 688187 |
| 2026-10-13 | 航天环宇 688523、震有科技 688418、优刻得 688158、阿特斯 688472、时代电气 688187 |

前 4 只三日全重合；第 5 名 10-09 为容百科技，10-12/13 为时代电气。

## 5. 诚实数据：收紧前后 T+1 对比（样本小，不构成结论）

| 口径 | n | T+1 胜率 | T+1 均收益 |
|------|---|---------|-----------|
| 旧 Top30 | 60 | 33.3% | −1.05% |
| 新 Top5 | 10 | 40.0% | −0.19% |

最强 5 只 T+1 表现优于 30 只均值，但 n=10 样本量太小，仅如实记录，不作策略结论。T+3/T+5/T+10 档均未成熟（未计入）。

## 6. 生效时点与后续

- **明日（2026-10-14）B 批起**：`gen_lqsq_top5.py` 已入 `run_algorithms.py` ORDER/STAGES + 预算表，新规自动生效，每日归档自然只留 5 只。
- **策略回测页**：LQSQ 旧行（Top30 口径）明日 E 批 `gen_backtest_all_algos.py` 重跑后自愈为 Top5 口径。
- bootstrap workflow（`v8_lqsq_bootstrap.yml`）命令已同步改名。

## 7. 验证证据（全绿）

- 门禁：`import run_algorithms` assert 过；py_compile 4 文件 OK；`grep gen_lqsq_top30` 零残留（replay 脚本除外）；`verify_lqsq_top5.js` 渲染实跑 13/13；`guard_double_blind.py` 三不变式全过；`pre_deploy_audit.py` 15/15。
- 远端 blob 对表：11/11 MATCH（workflow 文件一度报 MISMATCH 系 MSYS 冒号转路径假警，`git ls-tree` 复核实为一致）；全树 `git diff --stat HEAD origin/main` 空。
- 线上 Pages 硬验：`data/LQSQ_TRACK.js?v=97504b364c` 200·2510B（total_signals=15、signal_days=3、track_start=2026-10-09、update_time=2026-10-13 20:52:39、tracked 15 笔）；`data/LQSQ_BACKTEST.js?v=c450b7d391` 200·649B（total_signals=15）；index.html 200·1080942B（「归档信号 · 每日 Top5」1 处、新 ?v 1 处、「信号日」17 处、top30 残留 0）。

## 8. 教训沉淀

1. **cherry-pick 冲突模式再实证**：远端并发为 cn fetch 数据打点（BUILD SHA + 批量 `?v` 刷新），与我方 LQSQ 区域无实质交集，auto-merge 平滑通过。冲突高发区仍是 index.html script 注入锚点行。
2. **`git rev-parse origin/main:<path>` 在 MSYS 下会把冒号转成 Windows 路径列表**（假 MISMATCH）——复核一律用 `git ls-tree origin/main <path> | awk '{print $3}'` 或 `git diff --stat HEAD origin/main`。
3. 小九若在单位机改 `algorithms/gen_lqsq_top5.py` 或 LQSQ 数据，注意 `update_time` 口径：收益数字沿用真算值、时间戳不随截断刷新。
