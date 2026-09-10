# 🚨 URGENT｜阿狸咪 → 小九｜2026-09-11 00:25｜今夜算法链实况 + 明早请补跑 calc_stock_rps + 东财不可达实据

> 签发时刻：2026-09-11 00:25（CST）。依据：主人 23:51 令「今晚算法链什么时候能部署完成？你要盯住了！有需要小九机跑的速度更快的，就和她紧急交接。我休息了」
> 本单只写**已实测**的事实，每条带命令或时间戳；未查到的写「未查到」。

---

## 0. 一句话结论

**今夜链已在阿狸咪本机（alimi-cn）跑起来了，不需要你派发、不要你抢调度**（§2）。
**但有两件事请你明早在 lemoncat-cn 补**：① 补跑 `calc_stock_rps.py`（今夜被静默杀，`data/STOCK_RPS.js` 仍停 **09-08**）② 确认 FACTOR_LAB 生成器有没有两边同时在跑（§3）。

**预计今晚 01:20–02:00 上线**（B 批收尾 → D 批 → 推送 → 构建）；每再被静默杀一支脚本顺延 15 分钟。

---

## 1. 今夜实测事实（2026-09-11 00:2x，全部当场查过）

| 项 | 实测结果 | 举证方式 |
|---|---|---|
| 运行中 run | `☁️ v8 盘后算法链(云端)` **run#1685**，runner=**alimi-cn**，job started `2026-09-10T15:55:54Z`（CST 23:55:54） | GitHub Actions API `actions/runs` |
| 排队 run | **run#1686**（created `16:09:54Z`），同并发组排队，链跑完自动接上 | 同上，status=pending |
| 闸门判定 | `target_stage=B` / `stage_ok=true` / `proceed=true`；`reason=A 就绪(3/3) B 未就绪(0/3) → 跑选股批` | 本机跑 `.github/scripts/v8_stage_gate.py --root .` |
| 就绪明细 | ready_A=3/3、**ready_B=0/3**、ready_D=0/1、ready_E=2/2 | 同上 `detail=` 行 |
| B 批位置 | 00:24 在 `strategy_four_volume_60m.py`（约 6/~23） | runner 工作区 `raw_data/algo_heartbeat.json` |
| 被静默杀的脚本 | **`calc_stock_rps.py`**：00:01:32 起跑 → `[143/886] 300033 同花顺 ✗ 数据不足(0条)` → 00:06:44 起无输出 → 00:21:52 达 900s 静默阈值被监督器 kill 并续跑 | 心跳 `last_output_time` + `silent_sec`，且该 PID 已消失 |
| 盘后四卡现状 | FINAL_RECOMMEND_DATA=`09-10 04:57`、TRIPLE_CONSENSUS=`09-10 04:46`、FOUR_VOLUME=`09-10 05:37`、CRDS_CARD_DATA=`09-10 04:10` —— **全是今日凌晨旧版（用昨日数据算的），今晚尚未重算** | `git show FETCH_HEAD:data/*.js \| grep update_time` |
| 东财连通性 | 本机 `push2.eastmoney.com` / `push2his.eastmoney.com` / `82.push2.eastmoney.com` 连续 3 次 **HTTP=000（0.15–0.39s 快失败，DNS 解析失败级）**；对照 `qt.gtimg.cn`=200、`hq.sinajs.cn`=200 | 本机 curl x3 |
| 另一条独立进程 | `v8/factor_lab_gen.py` PID 19364，父进程=**19:46 那个旧会话的 bash**，工作目录 `WorkBuddy\2026-08-28-19-46-49\_flab`，日志 `_roe_recalc.log` 00:21 仍在写（`roe 进度 125 / 3195`） | 父进程链 + 日志 tail |

> ⚠️ 上面最后一行是「**两套东西同时在跑**」：链内 B#1 `v8/factor_lab_gen.py` **没产出**（`raw_data/factor_lab.json` 仍是 **09-09 19:48**，`data/FACTOR_LAB.js`=`09-09 19:02`），而我的仓库外手工任务在补它。这就是 §3 第 2 问要你确认的原因。

---

## 2. 请你**不要**做的（避免抢跑 / 风暴）

1. **不要再派发 `v8_algo_cloud`**。并发组 `v8-algo-cloud` = 「1 跑 + 1 排队」（`cancel-in-progress: false`），**run#1686 已在排队**，接力推进器每小时 :10 还会兜底。多派只会被顶掉、制造 `cancelled` 风暴。
2. **不要动 `logic.html` / `index.html`**：今夜前端无人在改（我最后一次改 logic.html 是 `23d2fe676`，已合并你的 `d53e17b0a`）。
3. **不要重复跑 `calc_stock_rps.py`**，除非先确认我这边已停（避免同源争抢）。

---

## 3. 🔴 请你明早在 lemoncat-cn 做的两件事

### 3.1 补跑 `calc_stock_rps.py`（当事机=单位机网络，能救东财口径）

- 现状：`data/STOCK_RPS.js` 的 `update_time` = **2026-09-08 19:57:28**（陈旧 2 天）。
- 后果：`generate_top10.py` / `strong_breakout.py` / `factor_lab_backtest.py` 都吃 RPS；今夜这轮 B 批是在 RPS 缺今日值的情况下跑完的。
- 建议命令（你机路径按你自己习惯）：
  ```bash
  cd <你的 v8 仓库>
  V8_IN_CHAIN=1 python algorithms/calc_stock_rps.py      # V8_IN_CHAIN=1 防它自己 push
  # 跑完显式加索引（禁 git add -A）
  git add data/STOCK_RPS.js raw_data/stock_rps.json
  git commit -m "补跑 calc_stock_rps（东财不可达致 09-10 夜被静默杀）"
  git push origin HEAD:refs/heads/main
  ```
- 如果东财在你那儿也不可达 → **别硬撑、别编数据**，回我一句「东财全站不可达」即可，我另想办法（改走 mootdx/baostock 兜底重算）。

### 3.2 确认 FACTOR_LAB 生成器有没有「两边同时跑」

- 我这边（阿狸咪本机）现在**有一个**在跑：工作目录 `C:\Users\HH20210606\WorkBuddy\2026-08-28-19-46-49\_flab`，用的是仓库外副本，产物写它自己的 `raw_data/flab_work/flab_roe_cache.json`，进度 `roe 125/3195`，按当前速率要到早上才完。
- **请回答**：你机上有没有独立的 FACTOR_LAB / 因子实验室生成任务在跑？
  - 有 → **我立刻停掉我这边的**（baostock 同源争抢会把两边都拖死，这正是 B#1 产出不出来的嫌疑）。
  - 没有 → 我继续跑，明早我把产物交给你并到主仓。

---

## 4. 我这边已安排的收口（你不用管，只作知情）

1. **已建自动化 `9119c1d4`**「阿狸咪-今夜算法链收口值守(等链完成→验收→补STOCK_RPS→瘦身复检→汇报)」：每小时 :40 醒一次，validUntil=2026-09-11。
   动作顺序：链跑完 → 验收四张盘后卡是否当日 → STOCK_RPS 补跑（**你若已补则自动跳过**）→ 瘦身复检 → 汇报并自停。
2. **瘦身提交待推（重要，别当没看见）**：我本地有 **1 个未推提交** `ee450e21d`「771 个运行时遗留移出版本跟踪 + 根治三条回潮路径（-42.4MB）」，另含 3 条根因修复：
   - `api_push_raw.py::walk_raw()` 目录剪枝（`__pycache__`/`_rps_cache`/`_tdx_cache`/`_archive`）+ 后缀过滤（`.bak`/`.tmp`/`.pyc`）——**它走 Git Data API，完全绕开 `.gitignore`**，是缓存回潮真凶；
   - `v8_cleanup.yml` / `v8_algo_intraday_lite.yml` 的 `git add -A` 前补 `git rm --cached`（`git add -A` 只挡未跟踪文件，挡不住已跟踪缓存的改动）；
   - `DO_NOT_DELETE.md` 豁免串污染修复（说明文字里带反引号 `raw_data/*.json` 被钩子当豁免抓走 → `raw_data` 全部 json 的保护长期失效）。
   **我等今夜链推完再推**——因为链用的是 checkout 时的旧版 `api_push_raw.py`，很可能把 `_rps_cache` 推回潮，所以要先让链推完、再复检、再补推。**若你看到我这条提交还没上 main，属正常，不要替我推。**

---

## 5. 铁律复述（两边都按这个来）

1. **判成败只认产物 `update_time`**，不看 run 的 success/failure；凌晨时间按「归前一日 24:xx」双候选解释。
2. **上游未就绪 → 红灯 + 拒绝执行 + 紧急报告**，禁 bypass、禁人工指定 stage。
3. **有 run 在跑时只读不写**；谁主力谁调度，另一台只盯不派。
4. 禁 `git add -A`；禁 `rm` 磁盘文件；`git rm --cached` 只摘索引。
5. 不确定就写「未查到」，**不许凭印象**。

---

## 6. 请回执（一行即可）

- [ ] `calc_stock_rps.py` 已补跑 → `data/STOCK_RPS.js` 新 `update_time` = ______
- [ ] FACTOR_LAB 生成器：我机上 （有 / 没有） 在跑
- [ ] 东财在你机网络： （可达 / 不可达）

—— 阿狸咪，2026-09-11 00:25
