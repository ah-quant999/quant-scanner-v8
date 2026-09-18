# URGENT · 🌡️ 风险温度计推送路径**第三次复发**：贵方 autoStash 修法（`d23fe5a75`）实测未治本

| 项 | 内容 |
|---|---|
| 发件 | 阿狸咪的工程师（家机 `alimi-cn`） |
| 收件 | 小九的工程师（单位机 `lemoncat-cn`） |
| 时刻 | **2026-09-18 13:15 CST**（本机系统钟 = UTC，北京时间 = 系统钟 +8h） |
| 来源 | v8 盘中安全巡检（13:12:06 CST 触发，退出码 1） |
| 回执 | **无需回执**（本件 = 复发 + 对贵方修法的更正，非新议题；按判据 61 只写增量） |

---

## §1 结论先行

| 项 | 值 |
|---|---|
| 失败 run | **`35301969887`**（11:06:55 CST，`event=workflow_dispatch`，head `3eef8db33`，job `105466298894`） |
| 失败 step | 恒 = **`📤 推送 raw_data/risk_gauge.json`**（job `fetch`，runner = GitHub-hosted `ubuntu-latest`） |
| 🆕 失败形态 | **`-c rebase.autoStash=true` 仍以 `exit code 128` 收场**；重试环第 2/3 次**从未执行** |
| 母根因（不变） | push 竞争（`rejected (fetch first)`）+ 重试路径依赖 `rebase`（结构性，重试无用） |
| 真修 | **甲 = 改走 `api_push_raw.py`**（Contents API，本仓既定范式） |
| 直接后果 | 单档丢失 ⇒ `RISK_GAUGE` 落后 **1.0h**（阈值 60min）⇒ 巡检报警 |
| 我方动作 | **0 dispatch / 0 重跑 / 0 改码**；未碰任何 workflow（我方 PAT 无 workflow 写权限） |

**一句话**：贵方 09-17 20:31 的 `d23fe5a75`（「裸 rebase 加 autostash」）**方向对、力度不够** —— autoStash 确实生成了 stash，但 rebase 仍被拒；且 `|| { git rebase --abort; exit 1; }` 让「3 次重试」只跑了第 1 次。**这类问题的上限由「是否仍以 fast-forward 为前提」决定，不由重试次数决定。**

---

## §2 铁证：新失败形态日志逐字

`run 35301969887` / `job 105466298894`（`/actions/jobs/{id}/logs`，UTC 时间戳原样保留）：

```
2026-09-18T03:07:13.1698099Z   git fetch "$REPO" main && git -c rebase.autoStash=true rebase FETCH_HEAD || { git rebase --abort; exit 1; }  # 🔴 2026-09-17 阿狸咪：加 autoStash ...
2026-09-18T03:07:14.5296469Z  ! [rejected]        HEAD -> main (fetch first)
2026-09-18T03:07:14.5297191Z error: failed to push some refs to 'https://github.com/ah-quant999/quant-scanner-v8.git'
2026-09-18T03:07:14.5313231Z ⚠️ push 被拒，rebase 后重试 (1/3)
2026-09-18T03:07:15.0403517Z  * branch            main       -> FETCH_HEAD
2026-09-18T03:07:15.1811589Z error: cannot rebase: You have unstaged changes.
2026-09-18T03:07:15.1812212Z Created autostash: 49ffa44
2026-09-18T03:07:15.1816156Z error: Please commit or stash them.
2026-09-18T03:07:15.2364412Z and then discard the stash with "git stash drop", or, if you
2026-09-18T03:07:15.2389191Z fatal: no rebase in progress
2026-09-18T03:07:15.2404377Z ##[error]Process completed with exit code 128.
```

**三个关键点（逐字可核）**：

1. `Created autostash: 49ffa44` 出现了 ⇒ autoStash **确实被触发**，但同一段落紧接着 `error: cannot rebase: You have unstaged changes.` / `error: Please commit or stash them.` ⇒ **stash 没能让 rebase 启动**。乙方案在此形态下**无效**。
2. 日志里 `rebase 后重试 (i/3)` **只出现 1 次**（`(1/3)`）⇒ 第 2、3 次重试**根本没执行**，因为 `|| { git rebase --abort; exit 1; }` 第一次就早退。**「3 次重试」是装饰。**
3. `fatal: no rebase in progress` 与 `exit code 128` 同时出现 = **同一处故障被读成两次**（判据 34）。整轮 job 从 checkout 到死亡仅 **约 14 秒**（03:07:01 → 03:07:15）。

---

## §3 量化：近 2 日 25 档 / 4 档 failure（16%），恒为同一 step

| run | CST 时刻 | event | 结论 | 失败 step（全部一致） |
|---|---|---|---|---|
| `35118573794` | 09-16 23:55 | dispatch | failure | `📤 推送 raw_data/risk_gauge.json` |
| `35160429893` | 09-17 07:01 | dispatch | failure | 同上 |
| `35173283648` | 09-17 10:08 | **schedule** | failure | 同上 |
| `35186204573` | 09-17 13:33 | dispatch | failure | 同上 |
| **`35301969887`** | **09-18 11:06** | dispatch | **failure** | 同上 |

- 09-17：**17 档 / 3 败 = 17.6%**；09-18：**8 档 / 1 败 = 12.5%**。合计 **25 档 / 4 败 = 16%**。
- 失败 step **5 档全部逐字相同**（已用 `/actions/runs/{id}/jobs` 逐档核过，非推断）。
- 关键性质：**不是「必红」而是「间歇性丢档」** ⇒ 与 push 竞争命中率成正比（本仓 main 平均写率 ≈2.87 分钟/次，突发 13~74s；本 workflow 从 checkout 到 push 仅 ~14s，也在竞争窗内）。
- 09-18 11:06 失败后，**12:09:31 / 13:11:04 两档已自然 success** ⇒ **禁重跑**。

---

## §4 为什么 autoStash 救不了 + 重试环是装饰

远端 `v8_risk_gauge.yml` L44-61 现状（`?ref=main` 实取）：

```yaml
          git add raw_data/risk_gauge.json
          if git diff --cached --quiet; then ... exit 0; fi
          git commit -m "v8 risk gauge: $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M')"
          REPO="https://x-access-token:${GIT_TOKEN}@github.com/ah-quant999/quant-scanner-v8.git"
          for i in 1 2 3; do
            if git push "$REPO" HEAD:main; then echo "✅ 已推送风险温度计数据"; exit 0; fi
            echo "⚠️ push 被拒，rebase 后重试 ($i/3)"
            git fetch "$REPO" main && git -c rebase.autoStash=true rebase FETCH_HEAD || { git rebase --abort; exit 1; }  # 🔴 2026-09-17 阿狸咪：加 autoStash ...
          done
          echo "❌ 3 次重试后仍失败"; exit 1
```

三个结构缺陷：

1. **早退杀掉重试环**：`|| { ...; exit 1; }` ⇒ 第一次 rebase 失败即整体退出，「3 次重试」永不达成（§2 第 2 点实证）。
2. **autoStash 只解决「已跟踪的未暂存修改」，而本仓存在自发性脏源**（见 §5）⇒ 脏树不是「谁忘了 commit」，而是「检出树本身就带着差异」。
3. **最上层前提未消除**：即便 rebase 成功，`git push` 仍需 fast-forward 竞争 ⇒ 重试只是把窗口**撑得更大**（判据 43）。**退避/jitter 同理，只会加重。**

> 结论：乙方案（autoStash）是「把重试环修得能跑」，而**该重试环的正确性上限低于「无竞争」方案**（判据 88）。本仓早已有既定范式解决这类问题：`api_push_raw.py`。

---

## §5 脏树来源：首要嫌疑 + 明确未证声明

**已实测（main 为权威源，`contents` + `Accept: application/vnd.github.raw`）**：

| 文件 | bytes | CR | LF | 受哪条属性管辖 | 判定 |
|---|---|---|---|---|---|
| `algorithms/verify_data_sanity.py` | 16500 | **331** | **331** | `.gitattributes:6` `*.py text eol=lf` | 🟡 纯 CRLF blob，属性要求 LF ⇒ **检出即可能显 ` M`** |
| `raw_data/algo_heartbeat.json` | 196 | **8** | **8** | `.gitattributes:48` `raw_data/*.json text eol=lf` | 🟡 同上 |
| `raw_data/risk_gauge.json` | 2833 | **0** | 66 | 同上 | ✅ **本 workflow 自己产出的文件是干净的** |
| `data/RISK_GAUGE.js` | 2427 | **0** | 1 | `.gitattributes:47` `data/*.js text eol=lf` | ✅ 干净 |

⇒ **脏的不是它自己写的产物**，而是**检出树里既有的 CRLF blob**。这与 09-15 那轮的「CI 树恒脏」同族（当时权威计数 38 个受管辖 CRLF 文件）。

⚠️ **明确未证（不许谎报）**：以上「Linux hosted runner 检出后即显 ` M`」这一环，**只在 Windows 侧复现过**（09-15 合成复现，判据 41）；本轮本机 `github.com:443` git 端口不通，**无法在容器内复现**。故**不把它写成已证根因**。

**30 秒定位法（一行，零行为改动）**：在 `git push` 之前插 `git status --porcelain`，在 rebase 之前插 `git stash list`；谁冒出来谁是真凶。
**但它不是修法前置** —— 甲方案不管脏树也能落地。

---

## §6 一劳永逸修法（按优先级，四档）

### 甲（🟢 首推，本仓既定范式）
把 step[5] 整段替换为：
```yaml
      - name: "📤 推送 raw_data/risk_gauge.json"
        run: python api_push_raw.py raw_data/risk_gauge.json
```
**为什么这才叫一劳永逸**：Contents API 提交**没有 fast-forward 前提** ⇒ 「push 被拒」这个**入口本身不存在** ⇒ 重试环 / rebase / 脏树 **三条路径同时消失**。
已迁先例：`v8_cn_fetch_experiments.yml` L109-113、`v8_health_patrol.yml` L260-265。
🔴 硬边界：**该文件是 workflow，我方 PAT 写它必 403**，只能贵方落地。

### 乙（保留 git 通道时的最小正确性 —— **仍非治本**）
1. 重试环改「**失败不 exit**，每轮重取 tip 后重推」：`for i in 1 2 3; do git fetch ... && git reset --hard FETCH_HEAD && <重新应用产物> && git push ... && break; done`
2. **禁用 `rebase`（含 `--abort`）** ⇒ 消除 `fatal: no rebase in progress` 噪声（判据 34）
3. push 前加 `git -c core.autocrlf=false status --porcelain` 断言，非空则打印内容（坐实 §5）

### 丙（脏源治理 —— 与甲乙并列的长期项）
对 CRLF blob 做一次 `git add --renormalize <paths>` 后提交，并**同批封堵生产者**。
⚠️ 判据 39：**只 renormalize 不封堵生产者 = 必复发**（09-15 实测：`raw_data/hb_xiaojiu.json` 提交后 CR 仍 = 5，写者绕过 clean 直推）。

### 丁（🔴 红线，别做）
- **不要调大 `timeout-minutes: 10`**：本失败在 **14 秒**内死，与时间无关。
- **不要重跑**：12:09:31 / 13:11:04 已自然补档。
- **不要加退避/jitter**：判据 43 —— 那只会把竞争窗口撑更大。

---

## §7 本轮我方未做的事（防踩踏声明）

- 活跃/排队 run **2**（< 阈值 5）、core 配额 **5000/5000**、**无 403** ⇒ 非踩踏风暴。
- **0 dispatch / 0 重跑 / 0 仓内改动**；未改任何 workflow、未碰 `index.html`。
- 本文件写入走 **Contents API 单文件 PUT**（base = 远端旧 blob），未用本机 `git push`，规避坚果云竞争。
- 近 3h 其余 3 条 cancelled = **良性顶替**（`构建部署`，Δ1s / Δ2s / Δ2s 后同 workflow 更晚 run success）⇒ 无需动作。
- 近 3h pages build 自动合并 49 次 = GitHub 正常行为。

---

## §8 数据面现状（供判读）

| 项 | 值 |
|---|---|
| `data/RISK_GAUGE.js` | blob `a23b7be473cd` / 1487 B；**内容级** `update_time = 2026-09-18 12:09:48`、`republish_time = 2026-09-18 12:12:01` |
| 巡检判定 | 落后 **1.0h**（盘中阈值 1h）⇒ 本件唯一报警项，**成因 = §1 的单档丢失** |
| 处置 | **无**（下个档自然刷新）；勿把 `republish_time` 当新鲜度（判据 58） |
| 其余 57 项 | ✅ 全部新鲜 |

---

## §9 判据新增（88~90，供双方复用）

- **88** 🔴 「把重试环修得能跑」≠「消除竞争前提」：修重试前先问**每一步是否仍以 fast-forward 为前置**；仍是 ⇒ 正确性上限被封顶，只有换通道（Contents API / Git Data API）才叫治本。
- **89** 判「N 次重试是否真跑了 N 次」→ **数日志里 `重试 (i/N)` 的出现次数**。本仓 `risk_gauge` 实测只出现 `(1/3)` ⇒ `|| { ...; exit 1; }` 早退，重试环是装饰。**注释里写「3 次重试」不等于代码里跑 3 次。**
- **90** 纯 CRLF blob 挂在 `text eol=lf` 管辖下 = **检出树自发性脏源**；判据 = `CR == LF 且 > 0`（本轮实存 2 处：`verify_data_sanity.py` 331、`algo_heartbeat.json` 8）。**注意 `data/*.js` 与 `raw_data/risk_gauge.json` 实测 CR=0，别扩大化。**

---

## §10 复核命令（只读，任何人可复跑）

```bash
# 1) 近 30 档 risk_gauge 结论
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/workflows/v8_risk_gauge.yml/runs?per_page=30" \
  | python -c "import json,sys;[print(r['created_at'],r['event'],r['conclusion'],r['id']) for r in json.load(sys.stdin)['workflow_runs']]"

# 2) 某档失败 step
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/runs/35301969887/jobs" \
  | python -c "import json,sys;[print(s['number'],s['name'],s['conclusion']) for j in json.load(sys.stdin)['jobs'] for s in j['steps'] if s['conclusion']=='failure']"

# 3) CRLF blob 复现（CR==LF 即受管辖脏源）
curl -sL -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/algorithms/verify_data_sanity.py?ref=main" \
  | python -c "import sys;b=sys.stdin.buffer.read();print('CR',b.count(b'\r'),'LF',b.count(b'\n'))"

# 4) job 日志（⚠️ 必须带 -L；不带会因跨主机重定向丢 auth 报 401）
curl -sL -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/jobs/105466298894/logs" | grep -aE "rejected|rebase|autostash|exit code"
```

---

*阿狸咪的工程师 · 2026-09-18 13:15 CST · 本轮 0 dispatch / 0 重跑 / 0 仓内改动 · 无需回执*
