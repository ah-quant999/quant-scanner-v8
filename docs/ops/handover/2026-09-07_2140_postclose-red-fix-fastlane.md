# 交接 · 2026-09-07 21:40 · 盘后链 22 红灯根因修复 + 快链补跑（小九 → 阿狸咪）

> 值班：小九（白班 07:45–17:45，本日延至 21:40）→ 阿狸咪（夜间/周末）
> 仓库：`E:/qs_workspaces/quant-scanner-v8`（**严禁 `E:/workspace/...`，那是坚果云 junction，09-04 整仓删除事故点**）

---

## 一、今晚发生了什么（一句话）

盘后算法链 **A 档当日 0 产出** → 连锁 22 项 `heal_cat=algo_run` 红灯。根因是**双重绞杀**：
1. 云端算法链 4 条 cron 静默失效（老顽疾，今日 16:40/18:10/20:00/21:00 全零触发）；
2. V5 静默闸门 `[6,18)` 把 16/17 点 dispatch 当「选股无效时段」杀掉——**但 09-04 时序重排已把 A 采集批挪到 16:40**，规则没跟着改 → 补跑 dispatch 全部 45 秒空转假 success。

## 二、已落地的修复（4 项，均已入库）

| # | 修复 | 落点 | 状态 |
|---|---|---|---|
| 1 | V5 闸门放行 A 档时段：`[6,18)` → `[6,16)`，16/17 点 dispatch 走采集批（小时映射 STAGE=A，非全链，无风暴风险） | `.github/workflows/v8_algo_cloud.yml` | ✅ 已上线 |
| 2 | **A 档派发自动化补位**（此前 B/D/E 都有兜底，唯独 A 档缺位靠死 cron）→ 新建交易日 16:40 `repository_dispatch` `trigger_algo` + `stage=A` | 自动化 `75e8cfe5` | ✅ ACTIVE |
| 3 | **三重共识空指针崩溃修复**：驾驶舱下线后 `a_map` 恒空 → `a` 恒 `None`，`a.get(...)` 直接 AttributeError 崩脚本（**三重共识自 09-04 起持续未产出的真凶**）→ 统一 `(a or {})` 兜底 | `algorithms/gen_triple_consensus.py` L191-193 | ✅ 已入库 |
| 4 | **最终推荐空指针崩溃修复**：09-03「驾驶舱 A/B 档下线」删代码时**残留孤儿代码块**（仍引用已删除的 `label`/`tech`/`qs`/`tier`）→ `UnboundLocalError`，**D 档 final_recommend 自 09-05 起持续未产出的真凶**。已整段清除 | `algorithms/final_recommend.py` L421-423 | ✅ 已入库 + 今晚产出 |
| 5 | 盘后算法链当日调度时间线沉淀进逻辑详解页（平实矩阵：时间/任务/执行机/前端，不写脚本名数据名） | `logic.html` | ✅ 已上线 |

> **今晚两个崩溃同源**：都是「功能下线时删代码删不干净，留下引用已删除变量的孤儿块」。建议后续同类下线操作后，**必须全量 grep 被删变量确认零残留**。

## 三、当前数据状态（21:34 健康检查：ok 100 / warn 2 / fail 7，红灯 22 → 9）

**已自愈（今晚，github.io 线上已生效）**
| 卡 | update_time | 来源 |
|---|---|---|
| 四量终极 FOUR_VOLUME | 09-07 21:57 | cn 快链 |
| 三重共识 TRIPLE_CONSENSUS | 09-07 20:23 | cn 快链 + 本机补跑 |
| 逆势龙头 CRDS | 09-07 20:57 | cn 快链 |
| **最终推荐 FINAL_RECOMMEND_DATA** | **09-07 21:55** | **本机快链（修 bug 后跑出 5 只：紫金矿业/迈瑞医疗/福耀玻璃/源杰科技/敦煌种业）** |

**仍红（全部 `heal_cat=algo_run`，只能靠算法链自愈）**
`FACTOR_LAB`(09-05，因子实验室，小九本机后台仍在跑，18min+ 大计算) / `BACKTEST_COMPREHENSIVE`(09-04) / `CRDS_BACKTEST`(09-05) / `H_AUTO_BUY`(09-04) / `INDEX_HISTORY`(09-06) / `maharo_macro`(--)
→ 除 FACTOR_LAB 外均为 **E 档回测类**，非核心展示卡，可放夜间低峰跑；`maharo_macro` 需确认数据源是否仍可用（09-04 起无产出）。

### ⚠️ FACTOR_LAB 专项（小九已定位，**别在夜里死磕，交给白天跑**）
- **现象**：本机跑 `v8/factor_lab_gen.py`，卡在 `roe 进度 100/3195` 静止 5 分钟+；加超时重跑后仍卡在 roe 阶段前。**非脚本 bug，是 BaoStock 服务端慢**。
- **判据（同机同数据源对比）**：`calc_crds.py`（425 只拉 K 线）**20:33 与 21:09 两次都只跑 2 分钟**；22:30 之后 factor_lab 就卡住 → **强时间相关，指向 BaoStock 夜间服务端限流/日终维护**，不是本机网络问题。
- **已加固（已入库 `0b5d2018c`）**：全局 `socket.setdefaulttimeout(20)` + `get_roe_ttm` 单只异常兜底。原本单只阻塞会**永久挂死整轮且无任何超时保护**；修后不再无限挂起，但仍受服务端速度制约。
- **给你的建议**：
  1. **不要夜里死磕**——放到**次日盘前/白天**跑，预计 25–40 分钟完成 3195 只。
  2. 若仍慢可缩 universe（主板 3195 只 → 大市值 Top1000），ROE_TTM Top30 结论差异极小。
  3. 缓存已生效（`raw_data/flab_work/flab_roe_cache.json` 随 git 提交），**断点续跑**，不必一次跑完。
  4. 跑完必须 `update_v8.py` 发布 + commit + push。

## 四、阿狸咪夜间作业要点（重要，请照做）

### 1. 铁律：优先快链，云端慢链是下策
- **快链（cn / 本机）≈ 84 分钟；云端 ≈ 2h40m**，且云端跑 BaoStock 逐只 K 线会**超时 45min 被杀**（今晚 18:21 轮就是这么死的，2 小时白跑）。
- 实测：本机跑 `calc_crds.py` **2 分钟** vs 云端 45 分钟超时——**能本机跑的一律本机跑**。
- 本机环境：`E:/workbuddy-data/binaries/python/envs/default/Scripts/python.exe`（baostock/pandas/numpy 齐全）。

### 2. 防互覆盖（今晚最大教训）
- 多 actor（v8-cloud-bot / github-actions[bot] / 云端轮 / cn 轮 / 健康巡检）**高频交替推送**，我的快链产出被覆盖过 3 次（TRIPLE 一度从 20:23 被打回 09-04）。
- **推送前必做**：`git fetch` → `git rev-parse origin/main` 与远端真实 SHA 对账 → rebase/cherry-pick 后立刻 push，**push 完必须回查线上值**（`git show origin/main:data/X.js`），被覆盖就再推。
- 冲突时取**数据更晚**的一方，不要盲取 ours/theirs。
- 主人已手动暂停大部分干扰自动化（21:2x），**夜间若要恢复请逐个恢复并观察 10 分钟**，避免再来一次互踩风暴。

### 3. 已取消/需注意的 run
- 20:37 pending 云端轮已取消（防旧值覆盖）。
- 19:52 云端算法链轮仍在跑（慢链），若你接手时还在跑且已跑 >1 小时无产出，**建议直接取消**，改用本机快链。

### 4. 剩余红灯处理顺序
1. **D 档**：`v8/factor_lab_gen.py` + `final_recommend.py`（最终推荐，主人最关心）— 小九已在跑，若未完成请续跑。
2. **E 档**：回测全家（`backtest_comprehensive.py` / `v8/backtest_crds.py` / `v8/backtest_rps.py` 等）— 耗时，可放夜间低峰。
3. 每档跑完必须跑 `update_v8.py` 发布 + commit + push。

## 五、明日（09-08 周二）待办

- [ ] **验证 STOCK_QUOTE cron 结构性重注册是否生效**：明早开盘后查 workflow 336548691 是否出现 `event=schedule` 的 run（09-07 全天 6 轮全是 `workflow_dispatch` 兜底，`schedule` 自 09-04 18:41 零触发）。**出现 schedule 才算收口**，否则继续靠 15 分级兜底。
- [ ] 验证 A 档 16:40 自动化（75e8cfe5）首次正常派发。
- [ ] 盘后链全档跑完后，确认红灯归零。

## 六、今晚踩到的坑（已记 memory，勿重蹈）

1. **grep `update_time` 会骗人**：文件内嵌套子记录也有该字段（19:14:54 实为子字段）。验证数据是否今日产出，金标准是 `git log --since="今天" -- data/X.js`（零提交=内容必旧）。
2. **前台跑长脚本会被超时杀**：BaoStock 类脚本一律后台跑（`run_in_background`），前台只适合 <2 分钟的命令。
3. **rebase 被工作树运行时文件挡住**会静默失败，push 连报 non-fast-forward 却不说明原因 → 先 `git checkout -- .` 清运行时文件再 rebase。
4. **前台 update_v8 跑 7 分钟会超时**，改后台。
