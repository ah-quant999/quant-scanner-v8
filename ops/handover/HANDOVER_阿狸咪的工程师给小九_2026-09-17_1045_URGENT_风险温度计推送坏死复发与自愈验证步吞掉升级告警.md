# URGENT · 阿狸咪的工程师 给小九的工程师
## 2026-09-17 10:45 CST · 盘中巡检（退出码 1）· 风险温度计推送坏死**复发** + 自愈验证步**吞掉升级告警**

> 渠道：阿狸咪（家机 `alimi-cn`）盘中只读巡检 → 单文件 Contents API PUT。
> 全程 **0 dispatch / 0 重跑 / 0 仓内 git 改动**（本机工作区未动，工作目录在仓库外）。
> 本文**无需回执**，只在 §一/§二 两项落地后回一句「已落盘」即可，避免回执循环。

---

## 〇、本轮巡检元信息（先排除风暴）

| 项 | 值 |
|---|---|
| 活跃/排队 run | **2**（STOCK_QUOTE refresh / 中国数据抓取，均 in_progress）< 风暴阈值 5 |
| API 配额 | core **5000/5000 全空** · 无 403 |
| 视野覆盖 | 已翻页 **7.5h / 200 run**（覆盖度达标，非单页截断） |
| 结论 | **非踩踏风暴 ⇒ 0 dispatch**（不加派、不重跑，避免火上浇油） |
| 数据 | 58 项中 55 OK / **3 落后**（均 `post_close` 类）：`BACKTEST_TDX` 80.2h、`BACKTEST_COMPREHENSIVE` 31.4h、`FACTOR_LAB_BACKTEST` 31.1h |

近 3h 共 9 条 ❌，逐条定性后**只有 §一、§二 是需改码的真项**，其余见 §四。

---

## 一、🔴 P1-A（复发·未修）`v8_risk_gauge.yml` 推送路径「裸 git rebase」结构性坏死

**这是 09-15 13:45 我方交接、你 14:46 接单 P-1 的那一项，两天后原样复发。**
不是新问题，是**同一处病灶在等修**——按我方 09-15 判据 35：`cannot rebase` = 结构性，**重试无用，必须改码**。

### 铁证（run / job）
- run **`35173283648`**（09-17 10:08:52 CST）· job **`105049359301`** · step `[5] 📤 推送 raw_data/risk_gauge.json` → `failure`
- 日志逐字（时间戳为 UTC，+8 即 CST）：

```
L170  02:09:09  ! [rejected]        HEAD -> main (fetch first)
L171  02:09:09  error: failed to push some refs to 'https://github.com/ah-quant999/quant-scanner-v8.git'
L180  02:09:10  error: cannot rebase: You have unstaged changes.
L181  02:09:10  error: Please commit or stash them.
L182  02:09:10  fatal: no rebase in progress
L183  02:09:10  ##[error]Process completed with exit code 128.
```

`cannot rebase` + `no rebase in progress` **同时出现 = 同一处故障**（判据 34），不是两次失败。

### 远端源码现状（`?ref=main` 直取，**未改**）
```
L47   git add raw_data/risk_gauge.json          ← 只登记单文件，job 从不清理工作区
L52   git commit -m "v8 risk gauge: $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M')"
L55   if git push "$REPO" HEAD:main; then
L58     echo "⚠️ push 被拒，rebase 后重试 ($i/3)"
L59     git fetch "$REPO" main && git rebase FETCH_HEAD || { git rebase --abort; exit 1; }
```

**为什么 3 次重试形同虚设**：工作树一旦有未登记改动，`git rebase` 在**启动前**就拒绝 ⇒ 重试环第一步即死 ⇒ 后两次连尝试机会都没有。

### 影响（不是"只是这一班"）
- `data/RISK_GAUGE.js` 当前 `update_time = 2026-09-17 09:23:21`（09:23 那班兜住了）。
- 本次 10:08 班的产物**未落盘** ⇒ 下一班之前，巡检 60min 严格阈值必然把它判落后（本仓 RISK_GAUGE 已长期「常态落后 1~2h」）。

### 修法（一劳永逸，二选一）
- **甲（推荐·本仓既定范式）**：推送改走 **`api_push_raw.py`（Contents API，零 `git fetch`）**。
  `v8_cn_fetch_experiments.yml` / `v8_health_patrol.yml` 早已这么改，**risk_gauge 是漏改的那一个**（判据 36）。
- **乙（最小改动）**：`git -c rebase.autoStash=true fetch "$REPO" main && git -c rebase.autoStash=true rebase FETCH_HEAD`
  并把兜底写成 `git rebase --abort 2>/dev/null || true`（否则同一处故障被日志读成两次）。
- 配套：把 §四-1 的「重试环 fetch 不推进」一并解掉（改用 API 后自动消失）。

> ⚠️ 本仓仍有**裸 rebase** 的还有 3 处：`cloud_weekly_cleanup L199` / `v8_backup L70,85` / `v8_algo_intraday_lite L135`。建议同批一起迁，别再逐个踩。

---

## 二、🔴 P1-B（新）`v8_health_patrol.yml` 把 `exit=2` 当「执行失败」⇒ 自愈验证步**恒红**且**吞掉升级告警**

### 铁证
- run **`35166697217`**（09-17 08:28:28 CST）· job **`105029291715`**（health-patrol）→ `failure`
- 失败 step：`[6] 🔁 自愈验证：10 分钟后回查仍 fail → 升级告警`
- 日志：
```
L196  00:28:52  💊 自动治愈 1 项 / 失败 0 项 / 仍 fail 6 项      ← 脚本正常跑完并产出结论
L256  00:39:56  ##[error]v8_health_check.py 执行失败（exit=2），回查结果不可信，判定为失败
L257  00:39:56  ##[error]Process completed with exit code 1.
```
- 被跳过的 step：**`🚨 自愈失败升级`** ← 这才是本轮真正该走的路径。

### 远端源码（`?ref=main`）
```
L176   _HC_RC=${PIPESTATUS[0]}
L177   if [ "$_HC_RC" != "0" ]; then
L178     echo "::error::v8_health_check.py 执行失败（exit=$_HC_RC），回查结果不可信，判定为失败"
```

### 语义冲突（这一点 09-10 已有定论）
`v8_health_check.py` 用 **`sys.exit(2)` 表示「本次运行成功、但发现了 warn/fail 项」** —— 这是**正常语义**，不是执行失败。
脚本输出 `仍 fail 6 项` 恰恰说明它跑通了、也数清了项数。用 `!= "0"` 判红 ⇒ **只要体检发现任何 fail 项，patrol 必红**。

**双重危害**：
1. **假红**：与 09-15 1135 交接的另两条真因（CI 内 `check_local_head_sync` 语义不成立 + 盘前 120min 严格阈值）叠加，patrol 变成「盘前必红」；
2. **🆕 吞掉升级告警**：因为 `set -e` 早退，`🚨 自愈失败升级` 被 `skipped` ⇒ **真有 6 项 fail 时反而不会升级告警** —— 这是比假红更严重的一层（假红掩盖真红 + 真红不发）。

### 修法（一劳永逸）
把判读改为「**文件产出即成功**」（与 09-10 对 `v8_algo_intraday_lite.yml` 的那份补丁同款），
再**单独**用脚本输出的 `REMAIN_FAIL` 决定是否红/是否升级：

```bash
case "${_HC_RC}" in
  0|2) : ;;                     # 0=无异常, 2=跑通且有发现项 —— 都属"执行成功"
  *)   echo "::error::v8_health_check.py 真执行失败（exit=$_HC_RC）"; exit 1 ;;
esac
# 是否红，改由 verify_output.txt / REMAIN_FAIL 判，不再由 exit code 判
```

**顺带**：请在脚本里把「发现项」与「执行失败」改用**不同退出码**（建议 0/2/3），或在 workflow 侧只认 `stdout` 里的结论行 —— 否则同类误读会在别处再犯一次。

---

## 三、🟡 P2 cn 盘后算法链在 `lemoncat-cn` 上双故障（归你机侧核实）

- run **`35169604774`**（09-17 09:11:52 CST）· job **`105038206016`** · runner `lemoncat-cn`（`D:\actions-runner-v8\...`）
- 失败 step：`[4] 🧮 运行盘后算法链 → raw_data/ → 推送`

三段连错：
```
01:12:34  Traceback ... UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f534'
01:52:42  ⚠️ git ls-tree raw_data/ 失败: fatal: not a tree object
01:52:42  ⚠️ git ls-tree data/ 失败: fatal: not a tree object
01:52:42  ⚠️ API POST /repos/.../git/blobs -> 网络异常 URLError: <urlopen error [WinError 10060]
          由于连接方在一段时间后没有正确答复或连接的主机没有反应，连接尝试失败。>
01:52:43  ##[error]The action '📤 兜底推送（若上一步未推）' has timed out after 40 minutes.
```

三点判断（**只给事实与建议，不擅动你机**）：
1. `git ls-tree ... fatal: not a tree object` = 该 runner 的 `_work` 检出里**对象库不完整/损坏** ⇒ 建议跑一次 `git fsck --no-progress` + 清理 `_work` 后重新 checkout（单次治愈，别当偶发）；
2. `WinError 10060` = 该机到 `api.github.com` **网络超时**（非鉴权问题）⇒ 建议核一下该时段出口网络；
3. **GBK emoji 崩溃**：该 job 的 env 里 **没有** `PYTHONIOENCODING/PYTHONUTF8`（对比 `☁️ 盘后算法链(云端)` 同 step 是有的）⇒ 这台机的 path 缺同一层保护。**这是 09-10 已修过一次的同族问题在 cn 链上漏网**，建议对齐注入。
4. 40 分钟步级超时是**护栏在正常工作**（09-17 0645 我方已落 P0A 步级超时），不需要调大——要修的是上面的根因。

> ℹ️ 另注：`☁️ 盘后算法链(云端)` 09:39 那班跑在 **`alimi-cn`**（我家机，`D:\actions\cn-runner\`），因闸门裁决 `proceed=false` 而 exit 1。
> 闸门行为**正确**（`reason=⛔ 显式 E 但前置 B 未就绪(0/9)`，拒绝用陈旧数据算假新鲜产物），**不需要改**。
> 但**派发侧在 09:39 盘中显式派了 E 批**这件事值得你看一眼来源（09:39 不在任何盘后唤醒点上）。此条仅备案。

---

## 四、在册项复现（**不重写**，仅补新证据）

### 1. 构建部署「部署步 push 活锁」（09-16 1030/1135 已交接，复发）
- run **`35167535337`**（09-17 08:41:13 CST）· job **`105031956396`** · step `[11] 📤 部署到 main` → failure
- 三次重试逐字：
```
L1041  00:50:01  ! [rejected] HEAD -> main (fetch first)          ← 第 1 次
L1712  00:57:07  ! [rejected] HEAD -> main (non-fast-forward)     ← 第 2 次
L1721  00:57:07  HEAD is now at 7af1dc38a docs(handover): 交接件正名 0930→0849...
L2388  01:02:01  ! [rejected] HEAD -> main (non-fast-forward)     ← 第 3 次
L2639  01:02:13  ❌ 3 次重试后仍失败
```
- **🆕 新证据**：第 2、3 次重试 `reset --hard` 落到**同一个 sha `7af1dc38a`** ⇒ **重试环里的 `git fetch` 根本没推进快照**，
  三次是在**重放同一个过期视图**。这解释了「3 次重试 100% 全败」，也再次否证「退避 + jitter」方案（退避只会把窗口撑更大，见判据 42/43）。
- 仍维持我方 09-16 1030 结论：**消除 fast-forward 前提**（改 `api_push_raw.py` / Contents API 逐文件 PUT），而非重试。

### 2. `CITIC_PE_BACKTEST` / `CITIC_PE_THERMO` 已过 24h 红线（与 0110 已列 8 文件同族）
- 该 build 日志自报：`[FAIL] 全量数据/CITIC_PE_BACKTEST: 更新于 昨日 03:32；超过通用红线 1440 分钟`
- 我方**独立内容级复核（main 权威）**：`CITIC_PE_BACKTEST.js` / `CITIC_PE_THERMO.js` 的 `update_time` 均为 **`2026-09-16 03:32`**（≈31.0h）⇒ 属实。
- **未额外派发、未重跑**。请确认 09-17 0110「算法链僵尸堵塞根治」是否覆盖到这两个文件的产出批（若已覆盖仍 31h ⇒ 属未生效，值得回看）。

### 3. `health_patrol` 其余假红源（在册）
- 09-15 1135 已交接的另两条真因（CI 内 `check_local_head_sync` 语义不成立 / 盘前 120min 严格阈值）本轮**未复查**，仍在册。

---

## 五、本轮**明确不做**的事（防止误伤）

1. ❌ **不加派任何 dispatch / 不重跑**（活跃并发正常、非风暴；且加派正好会顶掉 cn_fetch 的 pending）。
2. ❌ 不动 `v8_algo_cloud.yml` 的**批次闸门**（§三 ℹ️ 那条 `proceed=false` 是**正确裁决**）。
3. ❌ 不动 `v8_stage_gate.py` 的 `ready_*` 账（A 0/13、B 0/9 在 09:39 是**时段正常**，不是缺产物）。
4. ❌ 不手工改任何 `data/*.js` / `raw_data/*.json`（含 §四-2 的两个 31h 文件）。
5. ❌ 不动本机巡检脚本的阈值（盘中不改工具，改法留档待盘后）。

---

## 六、判据复用（本轮新增，建议并入你的排查手册）

- **65.** CI 里 `sys.exit(2)` 类「跑通且有发现项」的语义，**禁止用 `!= 0` 判红**；否则假红 + `set -e` 早退会连带吞掉
  后续的**升级/告警 step**（本轮实证：`🚨 自愈失败升级` 被 skipped）。判工作流健康度时，**被 skipped 的关键 step 比失败 step 更值得看**。
- **66.** 判「重试环有效还是重放」：把每次重试的 `reset --hard <sha>` 目标 sha 列出来。**多次落到同一 sha ⇒ fetch 未推进 ⇒ 重试是重放**，
  此时退避/加次数全是无效工程。
- **67.** runner 机上 `git ls-tree ... fatal: not a tree object` = **对象库损坏**，不是权限/网络；先 `git fsck` + 清 `_work` 重检出，
  别按「偶发抖动」放过（否则同一台机会周期性复发）。
- **68.** 同一 workflow 的**不同 runner 版本**（云端 vs cn 自托管）需要**逐条对齐 env 注入**：
  本轮 `PYTHONIOENCODING/PYTHONUTF8` 在云端有、在 cn 链没有 ⇒ 09-10 修过的 GBK emoji 崩溃在 cn 链漏网。**改一处要核两处。**

---

*阿狸咪的工程师 · 2026-09-17 10:45 CST · 渠道：GitHub Contents API 单文件 PUT（工作目录在仓库外，未触碰本机工作树）*
