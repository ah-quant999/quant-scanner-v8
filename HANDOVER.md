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

---

## 【23:45 补充】第二批前端补丁已上 main（commit 89f65067f7，Pages 9882 success）

主人 23:3x 审批后阿狸咪已完成的第二批量工作，小九明早核对：

| # | 改动 | 位置 | 核对方法 |
|---|---|---|---|
| 1 | **因子实验室迁入「暂未上架」**（★★ 观测仓·调试与回测中，升 4⭐ 再转正选股策略子页；原选股生命周期 pane 内卡已移除） | 运维→暂未上架 第 4 卡 | 打开暂未上架页见「🧪 因子实验室 ⭐⭐」卡 |
| 2 | 因子实验室**卡面只展示「🟢可关注」标的**，完整榜单（异常换手 Top30+Bottom10 / ROE Top30）点击「📄 完整榜单」弹窗查看 | 同上 | 卡面应只有可关注行+2 个弹窗按钮 |
| 3 | 因子实验室**胶囊统一**：更新时间紧跟卡名（🕐 更新 MM-DD HH:MM），靠右旧时间已删 | 同上 | 头行无右侧时间 |
| 4 | **CRDS 半成品闸门**：扫描 0 只+全列表空时显示「⏳ 盘后计算中…非报错」横幅 | CRDS 卡顶部 | 今晚 21:33 半成品被 cn#23 新数据替换后横幅自动消失；若再见空壳卡应显示横幅而非 unknown |
| 5 | **高手共振口径统一**：全局 `__v8NormCode/__inGaoshouReso/__gaoshouResoCount`，池徽章=IMA∩(生命周期池∪最终推荐候选)，Top5/候选行「高手共振」pill 需过同一判定 | 高手池头部徽章 + 最终推荐 | 徽章数应 ≥ Top5 中带pill数，且不再 1 vs 3 矛盾 |

**数据真相**（主人问「高手共振错了吧」）：紫金/海鸥/招商轮船确在高手 IMA 池（ima 自动同步，非盘后链产物）——标签真实，错在两处口径不一致，已统一。

**cn#23 进度**：23:21 启动，23:4x 已入 step4 算法链本体。跑完后今晚全部旧数据卡（市场宽度/宏观/解禁/业绩预告/精选预判/宽基ETF/高手池/因子实验室/CRDS/最终推荐）自动刷新。

**明早核对清单（5 分钟）**：
1. `git ls-remote` 看 main 最新 commit 是否含 cn#23 的数据推送（约 00:0x 前后）；
2. 打开选股策略页 Ctrl+F5：胶囊带日期时间、候选池前20+⭐评分、Top5 分析齐平；
3. 暂未上架页：因子实验室卡正常渲染（⭐⭐+可关注+弹窗）；
4. CRDS 卡：脱离 21:33 半成品（total_scanned>0）；
5. 高手池徽章数与最终推荐高手共振数口径一致。

---

## 【01:45 补充】cn#23 收尾异常 + 时间闸门根修 + cn#24 重派（阿狸咪 01:45 写）

**cn#23 结局**：结论 cancelled（01:26 step8 兜底推送中被取消，非人为；数据推送 step4-7 已全部落 main）。算法链本体 84m28s（云端 2h40m → 提速 ~50%+），**39 成功 / 4 失败**。

**4 失败与根因**（algo_run_report.json 实锤）：
| 脚本 | 原因 | 处置 |
|---|---|---|
| gen_triple_consensus.py / strategy_four_volume.py / final_recommend.py | 脚本级时间闸门 check_stock_picking_ready 只判 ≥18:00，无凌晨补跑窗口；链跨午夜 00:0x~00:30 轮到它们被误拒 | ✅ **根修已上 main（commit 827509ad64）**：time_gate.py 补 00:00~05:59 放行窗口，与链级闸门口径对齐 |
| scripts/ab_universe_backtest.py | 监督器静默杀 >15min（云端同病，老问题） | 📌 明日待办：查该脚本为何 15min 无输出 |

**cn#24**：01:31 已重派（含 time_gate 根修代码），预计 ~02:55 完成，将补产 TRIPLE_CONSENSUS / FINAL_RECOMMEND_DATA / FOUR_VOLUME（含 BACKTEST）。SECTOR_FUND_TRACK 归属云端 v8_cn_fetch_cloud（#1260 success 但数据仍 09-02 16:18，待查）；FOUR_VOLUME_BACKTEST 由 strategy_four_volume 产出，根修后 #24 自愈。

**明早核对清单增补**：
6. 选股策略页：三重共识/最终推荐/四量 更新时间应为 09-04 02:xx（cn#24 产物）；
7. algo_run_report.json 的 failed_scripts 应只剩 ab_universe_backtest（或 0）；
8. 健康面板 SECTOR_FUND_TRACK 若仍 09-02 → 查 v8_cn_fetch_cloud #1260 日志 build_sector_fund_track 步骤。

---

## 【03:30 终验完成】cn#24 success——时间闸门根修实证生效（阿狸咪）

**cn#24**：success（01:31→03:28，链本体 ~84min）。algo_run_report：**41 成功 / 2 失败，skipped_by_time_gate = []（根修生效）**。

| 数据文件 | 时间 | 状态 |
|---|---|---|
| TRIPLE_CONSENSUS | 09-04 02:03 | ✅ 完整产出；count=0 为**真结果**（无股票同时满足三条严格标准），near_miss 5 只全字段齐（荣昌生物 rank1） |
| FINAL_RECOMMEND_DATA | 09-04 02:35 | ✅ 66 候选；Top5 全字段（紫金 rank1 sources=[ROE_TTM,高手跟踪]——点前缀根修自愈实证，close/止损/目标/支撑/ATR/backtest/tracking/action 全齐） |
| CRDS_CARD_DATA | 09-04 01:39 | ✅ total_scanned=137（脱离 21:33 半成品） |
| BACKTEST_COMPREHENSIVE | 09-04 01:58 | ✅ 脱离 13:14 旧值 |
| CANDIDATE_QUOTES / H_AUTO_BUY | 01:54 / 00:20 | ✅ |

剩余 2 失败均为监督器静默杀（>15min 无输出）：ab_universe_backtest + auto_run_dn_algorithm——**明日待办 #1**，查这两脚本为何长时间无输出（云端同病）。

其他遗留（交接原 8 条核对清单基础上）：SECTOR_FUND_TRACK 仍 09-02 16:18（查 v8_cn_fetch_cloud #1260 日志）；FACTOR_LAB 09-03 01:55 / MACRO / ETF_SUBSCRIPTION 12:5x 未被 algo 链覆盖（归 cn_fetch 链，今日白天链会刷）。

---

## 【06:50 补充】主人晨起令「2到5现在做」——四件全部落地（阿狸咪 06:50 写）

| # | 事项 | 落地内容 | 核对方法 |
|---|---|---|---|
| 2 | **探针自动路由** | `v8_algo_cloud.yml` 新增「🧭 探针路由」步：schedule/repository_dispatch 跑前用 V8_GH_TOKEN 查 lemoncat-cn 是否 online+idle → 在线则按 CST 小时算 stage 转派 cn 链（v8_algo_run.yml inputs.stage），云端重活全跳；离线/忙/转派失败**一律回落云端永不断供**。手动 workflow_dispatch 不路由（保留 force_run 语义） | 今晚 16:40 stage A 看云端 run 日志「🧭 探针路由」输出 |
| 3 | **calc_stock_rps 并行化** | 串行 60min（占全链 37%）→ 8 线程并行：mootdx 改线程本地连接（pytdx 非线程安全）、baostock 全局锁串行化、缓存写加锁；三级兜底与输出口径不变 | 明晚 B 批 step 耗时应 60min→10-15min |
| 4 | **cn 版包装层移植** | `v8_algo_run.yml`：inputs（stage/force_run/bypass_time_gate）+ concurrency（v8-algo-cn，1跑1排队）+ timeout 120→240 + 运行步支持 --stage + **ALGO_TRACK ?v 缓存戳步**（Contents API 读 main index.html，>1MB 回落 raw 模式） | 路由发生后看 cn run 步骤列表 |
| 5 | **因子实验室升4⭐证据链** | 新脚本 `algorithms/factor_lab_backtest.py`（异常量比五分位分层 point-in-time 回测：700日长历史×~40调仓点，各层净收/胜率/净值回撤/OOS/分季稳定性 + ROE Top30 对比），挂链 STAGE-C，`update_v8` 映射 window.FACTOR_LAB_BACKTEST，暂未上架因子卡新增「📊 独立分层回测」区块（升3⭐判据自动判定） | 今晚 19:15 C 批后暂未上架卡出现回测表 |

**质量关**：回测脚本过了**沙箱单元测试**（合成数据植入已知效应 → 正确测出 PASS）；run_algorithms 生产级 STAGES 并集 assert 通过；node 23 段 0 错；4+2 文件全部回读逐字节一致。

**⚠️ 生效时点**：探针路由/并行化/回测挂链均自**下一轮链**（今晚 16:40 A 批）生效；cn 版 workflow 变更自下次 dispatch 生效。

**小九注意**：① `v8/factor_lab_gen.py`（本机脚本）今晚不动，全市场扫描开关未实现（卡片措辞已中性化）；② 云端链被路由跳过时结论是 success（秒级完成属正常，看日志「🧭 探针路由」确认转派）；③ cn#24 之后 runner 无异常不要手动 dispatch。

---

## 【06:55 补充】小九专属任务清单（阿狸咪做不了/需本机现场，主人 06:47 令「清清楚楚交接」）

| # | 任务 | 为什么必须小九做 | 具体步骤 | 验收 |
|---|---|---|---|---|
| 1 | **FACTOR_LAB 恢复跑批**（当前 FAIL：09-03 01:55 后未更新，超 24h 红线） | `v8/factor_lab_gen.py` 是本机脚本（baostock+仓库外缓存），阿狸咪无本机执行权 | 查本机定时任务为何 09-03 白天没跑：是漏跑、跑了失败、还是失败没推送？修复后手动跑一次 | 健康面板 all_FACTOR_LAB 转绿；data/FACTOR_LAB.js 时间戳=今日 |
| 2 | **因子实验室全市场扫描**（升 4⭐ 最后一环） | 同上，且首跑需数小时建全市场 K 线缓存 | `v8/factor_lab_gen.py` 异常换手扫描从重点池 351 只扩到全市场；建好缓存后每晚会很快 | FACTOR_LAB.abnormal_turnover 覆盖数 >351；配合今晚已挂链的 factor_lab_backtest 复验升 3⭐ |
| 3 | **监督器静默杀 ×2 现场诊断** | 需 runner 本机看实时输出/进程资源（阿狸咪只能看 GitHub 落盘日志，看不到"为什么 15 分钟不吐行"） | 对 `scripts/ab_universe_backtest.py` 和 `auto_run_dn_algorithm.py`：手动跑一次，观察卡在哪一步、是否 print 缓冲未 flush；最小修复=关键循环加 flush=True 或心跳输出 | 下一轮算法链 failed_scripts 不再出现这两个 |
| 4 | **cn#23 step8 被 cancel 之谜**（低优先） | runner 侧行为，只有本机日志能解释 | 看 lemoncat-cn runner 服务日志 09-04 01:26 前后有无重启/看门狗记录 | 知道原因即可，无需修复 |

**阿狸咪自己接手的（小九勿动）**：
- `data/SECTOR_FUND_TRACK.js` 是**孤儿死文件**（前端 0 引用、仓库无生成器，疑上次轻量化删卡漏删数据）——阿狸咪今晚删文件+健康检查排除，**小九不要在本机重跑或恢复它**；
- `FOUR_VOLUME_BACKTEST` 0 信号时 update_time 不前移导致健康面板误报 FAIL——阿狸咪改 `strategy_four_volume.py` 0 信号也刷新时间戳；
- 探针自动路由/并行化/因子回测挂链已于今晨上线，今晚 16:40 A 批首次实战，小九只需旁观。

---

## 【07:15 更正+收尾】零遗留终审（阿狸咪 07:15 写，主人上班前令）

**更正 06:55 段两处**（以本段为准）：
1. ~~"SECTOR_FUND_TRACK 孤儿死文件，阿狸咪今晚删文件"~~ → **已改为非破坏性处置**：该文件由云端 cn_fetch step9 生成器持续产出（#1257 实跑 success），删文件会被下轮链复活。已改 `v8_health_check.py`：新增 `_RETIRED_FILES={"SECTOR_FUND_TRACK"}` 从 items[] 排除 → `all_SECTOR_FUND_TRACK` 误报 FAIL 消除。**彻底清理（删生成器步骤+raw/data 文件）属破坏性操作，待主人拍板**（热门赛道卡 09-02 曾被主人令恢复过一次，后再移除，意图存疑不硬删）。
2. ~~"FOUR_VOLUME_BACKTEST 待办"~~ → **已修完**：`strategy_four_volume.py` 新增 `write_four_volume_backtest_js()`，链上每次跑完四量即刷新 `.js` 规范化外壳（前端策略回顾读 .js 非 .json；此前 09-02 手工空壳无人回写）。`--backtest>0` 手动跑时自动附带真实分层。下轮链（今晚 16:40）生效后 `all_FOUR_VOLUME_BACKTEST` FAIL 消除。

**收尾补丁质量关**：patch_final_audit.py 锚点断言 count==1 ×4 组 → py_compile 双文件 0 错 → Contents API PUT → 回读逐字节一致 ×2。

**当前健康面板预期**（下轮巡检起）：3 个 FAIL → 0（FACTOR_LAB 待小九恢复跑批后消除；另两项已消误报源）。

**待主人拍板（不阻塞）**：①生命周期 3 卡编号方案甲/乙（已当面汇报）；②SECTOR_FUND_TRACK 彻底清理；③今晚 16:40 A 批探针路由首次实战，明早看 B 批 calc_stock_rps 耗时应 60min→10-15min。


## 07:25 补记（阿狸咪）
- ✅ 主人拍板**方案乙**已上线（commit a6d202a620d0）：选股生命周期 3 卡卡名后追加角色小标签（⚡强势突破·①发现信号 / 📡高手跟踪·②共振确认 / 🧬选股生命周期·③持有管理），卡序不动、10.5px dim 灰非徽章样式。语法审计 0 错 + diff 恰 3 行 + 回读逐字节一致。小九白天**无需重复此改动**。
- ⏳ 仍待主人拍板：SECTOR_FUND_TRACK 彻底清理（删生成器+文件）。
- ⏳ 小九今日 4 项不变：FACTOR_LAB 恢复跑批 / 因子全市场扫描 / 监督器静默杀×2 诊断 / cn#23 step8 cancel（低优先）。


## 🔴 08:45 紧急补记（阿狸咪）：main 回退事故 + SECTOR_FUND_TRACK 清理完成
1. **main 曾被强制回退**：08:15-08:35 窗口内，main 被**某个客户端用陈旧本地副本 force push 回退到 06:56(4396e93d)**，丢掉了 07:15 之后的全部提交（方案乙角色标签 a6d202a6、health_check 补丁、07:25 交接补记、08:09 CI build 等约 29 个提交/173 文件）。**阿狸咪已用 Git Database refs API 无损恢复到 1049319b**（纯 fast-forward，零丢失），随后在其上完成 SECTOR_FUND_TRACK 清理（21e0574e/9329d358/0b2a56bd 三个提交）。
2. **小九铁律（立即生效）**：任何 push 前**必须** `git fetch origin main && git reset --hard origin/main`（或 rebase FETCH_HEAD）对齐远端；**严禁 `git push --force`/`+main`**。部署脚本若内置 force push 参数必须先摘除。今天上午若你本地有未推成的改动，先 pull 对齐后再重推。
3. ✅ **SECTOR_FUND_TRACK 已彻底清理完毕（主人 08:15 拍板「确认无关联没用的就清」）**：cn_fetch 死步骤、health_check _RETIRED_FILES 死代码、raw_data/sector_fund_track.json 孤儿文件三处全删。考证结论：生成器与 data js 早在 09-02 7c1363b9 就已删除，本次只是清掉残留。**小九勿重复处理。**
4. 另：Contents API 的 raw GET 在本机代理下可能返回陈旧缓存版本（本次差点用旧版覆盖新版），读取关键文件务必用 `git rev-parse HEAD:<path>` blob sha 与线上 meta sha 双验证。


---

## 【22:50 阿狸咪夜班对接确认回执】已逐条核实小九今晚全部改动，无冲突、正向协同 ✅

主人 22:43 令「认真对接」。阿狸咪已逐提交核实（16:00 CST 后约 214 文件改动）：

| 小九今晚改动 | 提交 | 阿狸咪核实结论 |
|---|---|---|
| 动量共识正式挂链 5 处（emit-js/ORDER/STAGES[B]/SCRIPT_ENV/盘后门控） | 41d71727 | ✅ 8 源唯一链外依赖一劳永逸修复，审计全绿，明早起生效 |
| logic.html 4 处补写（8源对应表/执行机列/算法对比表/双机状态） | 41d71727 | ✅ **增量修改未覆盖**——阿狸咪 16:26 的 7 处补写（3卡关系/因子实验室/高手共振/main回退/探针路由/time_gate双口径/rps并行化）在 main 全部存活 |
| 预览指引 E:/workspace → E:/qs_workspaces | 6ead42f8 | ✅ 合理（主站文档不应引导写坚果云同步目录）；口径变化已记录 |
| dispatch 分批派发（云端 dispatch/repo_dispatch 按 CST 小时进批） | 402d102d70 | ✅ 与阿狸咪昨夜探针路由**对齐闭环**：cn 链 stage 入参 ↔ 云端 dispatch stage 入参互认，22/23 点防漂移保 final_recommend，设计正确 |
| v8_cloud_watchdog 修复 | cf21ea8f | ✅ |
| 边界遵守 | — | ✅ 未碰 v8_health_check.py / time_gate.py / SECTOR_FUND_TRACK 生成器 / 阿狸咪交接双文档 |

**实证好信号**：`FOUR_VOLUME_BACKTEST.js` 已被今晚链上刷新（ca20d56bc6）——阿狸咪今晨 `write_four_volume_backtest_js()` 修复实战生效，健康面板该 FAIL 应已消除。

**仍待办（不阻塞）**：
1. **FACTOR_LAB 恢复跑批（小九任务#1）仍未完成**：`data/FACTOR_LAB.js` update_time 仍 `2026-09-03 01:55:04`——小九明日继续，其余 3 项任务清单不变。
2. main 上有少量 `*.bak`（LHB_7D.js.bak / 若干 raw_data/*.json.bak）——链上产物冗余，待主人拍板是否纳入轻量化清理。

阿狸咪夜班继续值守（18:00-次日 7:30 窗口），cn 链/云端链异常随叫随到。

---

## 【2026-09-05 06:52 阿狸咪晨间补记】待办闭环 + .bak 轻量化清理

主人令「待办的完成了吗？同意纳入轻量化清理。还有什么没做的？」。核实结论：

### ✅ 本次完成
- **.bak 冗余备份清理（19 个全删，0 失败）**：data/LHB_7D.js.bak、data/STOCK_LIST.js.bak + raw_data/ 下 17 个 `*.json.bak`。均为链上产物冗余，前端不读 .bak，删除符合「仓库内禁止备份」铁律，main 已清零（tree 复核 0 个）。

### ⏳ 待小九侧（非阿狸咪可控）
- **FACTOR_LAB 恢复跑批（小九任务#1）数据仍未重算**：`data/FACTOR_LAB.js` update_time 仍 `2026-09-03 01:55`。但小九 9/4 22:48 提交 `cab3bd364a (fix: 云端适配根治 FACTOR_LAB 云端必挂)` 已**根治跑批必挂根因**，障碍清除。待小九 9/5 白天窗口（07:45 起）实际跑批触发，届时时间戳刷新才算真正完成。
- **小九剩余 3 项任务清单**：② 因子全市场扫描（升 4⭐ 最后一环）③ 监督器静默杀×2 现场诊断（ab_universe_backtest + auto_run_dn_algorithm）④ cn#23 step8 cancel 之谜（低优先）。进度以她交接本为准。

### ✅ 已闭环（不需再动）
方案乙角色标签 / SECTOR_FUND_TRACK 清理 / main 回退恢复+分支保护 / logic.html 7 处补写 / 与小九对接回执 / .bak 清理。

### ⚠️ 待用户手动（客户端动作）
- **模型转 Hy3 免费版**：9/4 09:20 提醒已过期（一次性任务）。该设置在 WorkBuddy 界面层模型选择器，智能体无工具可代切，需主人手动点选。若尚未切换，现在切即可。

### 分支健康
main 分支保护生效（forbid force push + enforce_admins），9/4 22:51 build 后无回退。

阿狸咪晨间值守至 07:30，随后小九接管白天窗口。
