# 双机交接（阿狸咪 → 小九）2026-09-04 00:20 CST

## 今夜阿狸咪已办（全部已上 main，无需重做）
1. **算法链换机**：云端链 #1468/#1469（跨境抓数慢，step 9 实测 2h40m，其中 calc_stock_rps 单脚本 60 分钟）已主动 cancel，改派 **cn 版链 `v8_algo_run.yml` run #23 在 lemoncat-cn（小九单位机）上跑**，23:21 启动。预期 40~70 分钟跑完全链。
2. **final_recommend.py 根修已上 main**（提交 77f29224）：norm_code 剥点前缀（.601899 类）修画像/止损/行情失配 + ROE/高手跟踪补 reason + CANDIDATE_QUOTES 行情兜底 + 概念标签 4→8。**cn 链 #23 拉的就是新代码**，今晚 FINAL_RECOMMEND 应产出完整画像（紫金矿业类 1、2 名分析补齐到与第 3 名一致）。
3. **index.html 前端合并补丁已上 main**（905426 字节，回读逐字节验证✅，node 23 段 inline 0 错）：
   - `_runBadgeInfo` 全站胶囊一律带准确「MM-DD HH:MM」，禁止只写「今日已跑完」（主人令）；
   - 候选池行首 ⭐ final_score 评分 chip + 概念标签 slice(0,8) + RPS chip + **短线只展示评分前 20 名**（标题带 X/总数）；
   - Top5 全名次统一：⭐综合分 chip + 新分析角度行（个股历史共振胜率/策略级回测最佳持有/跟踪浮盈/操作建议）+ STOCK_PROFILE/STOCK_QUOTE 前端兜底。

## 小九明早请核（按序，5 分钟）
1. cn 链 #23 结论是否 success（Actions →「🇨🇳 v8 盘后算法链(cn)」）。若 failure：看日志哪步挂，优先重跑 dispatch 一次；仍挂则改回云端 `v8_algo_cloud.yml` dispatch（并通知阿狸咪勿重复排查）。
2. 数据新鲜度：TRIPLE_CONSENSUS 应脱离「09-03 20:07 count=0 半成品」；BACKTEST_COMPREHENSIVE 应脱离「13:14」；FINAL_RECOMMEND_DATA 应为今晚新产。
3. Pages 部署后 Ctrl+F5 抽查：选股策略页胶囊是否带具体日期时间、候选池是否前 20 名+评分、Top5 第 1/2 名分析是否与第 3 名同等详略。
4. ⚠️ 云端 `v8_algo_cloud.yml` 的 schedule（明 16:40/18:10/19:15/20:00）照常自动触发，与 cn 版并存勿手动双跑（会互相覆盖 raw_data）。cn 版仍是 dispatch-only 应急/加速通道。

## 遗留（非紧急）
- 治本级优化（runs-on 自动路由探针：lemoncat 在线走 cn、离线自动回落云端）已设计未实施，等主人拍板后做。
- calc_stock_rps（60 分钟/轮）串行抓数并行化待办。
