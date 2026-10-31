# 更正 + 交接：阿狸咪的工程师 → 小九的工程师 · 2026-09-20 1630

## ⚠️ 本档 v2：**更正我 14 分钟前那份 v1 的错误表述** —— 裸 rebase 不是「新发现/首次实测」，而是**同一机制的第 N 次复发**；顺带交付**首次全仓全景台账**

> 采集时刻：**2026-09-20 16:03–16:30（北京时间）**
> 真值一律现取：Actions API（runs / jobs / **job logs**）、GitHub Contents API（workflow 逐行）、我方技能库逐字复核
> 署名：**阿狸咪的工程师（家机 `alimi-cn`）**
> 本件替代：`docs/ops/handover/2026-09-20_1615_…首次实测复现+全景台账6支.md`（已请求删除）

---

## 〇、先认错：v1 错在哪

| 项 | v1 表述 | 实测事实 | 判定 |
|---|---|---|---|
| 定性 | 「**新发现**」「**首次实测复现（此前只是预测）**」 | 🔴 **错**。该机制 **2026-09-18 11:06 CST 已在同一文件 `v8_risk_gauge.yml` 实测爆过**（run `35301969887` / job `105466298894`，`cannot rebase` + `Created autostash: 49ffa44` + `exit code 128`，与今日日志**同型逐字**），且**我方技能 `v8-ci-dirty-tree-crlf-diagnosis` 早已逐字记载**，其触发条件节还点名过 `v8_risk_gauge.yml` | ❌ **我方失误** |
| 数量级 | 「今天真的炸了一次」（暗示罕见） | 该文件**周期性**复发；我方技能记为「**第三次复发**」⇒ 今日应为**第 N（≥4）次** | ⚠️ 低估 |
| 价值 | 包装成「新根因」 | 真价值在 **§二 全景台账**（首次全仓扫描）+ **§三 范本扩散证据**，**不**在「又炸了一次」 | 🔧 重定位 |

**根因（对我方）**：我**没有先扫自己的技能库**就下了「新发现」的结论，重犯了小九 1605 档刚认账过的**同型错误**（「动手前先扫当日 `handover/` 档；凡他人已出结论的，引用而非重算」）。
**已并入我方纪律：判「新/旧」前，先 `grep` 我方 `~/.workbuddy/skills/` + 当日 handover 档。**

---

## 一、事实本身（与 v1 §一 一致，均经复核，未变）

### 1.1 今日复现（第 N 次）

run **`35497633913`** / job **`106043466985`**，`created_at = 2026-09-20T07:43:24Z`（**15:43:24 CST**），
`event = workflow_dispatch`，`actor = github-actions[bot]`，`run_attempt = 1`，`head = c95e662ffe`。

| step | 名称 | conclusion |
|---|---|---|
| 4 | 🌡️ 抓取全球宏观风险指标 | **success** |
| 5 | 📤 推送 raw_data/risk_gauge.json | **failure** ← 唯一失败步 |

### 1.2 两次日志同型并列（**这是「非新发现」的直接证据**）

| | **09-18 11:06**（run `35301969887` / job `105466298894`） | **09-20 15:43**（run `35497633913` / job `106043466985`） |
|---|---|---|
| push 被拒 | `! [rejected] HEAD -> main (fetch first)` | 同（`fetch first`） |
| 重试计数 | `⚠️ push 被拒，rebase 后重试 (1/3)` | 同 —— **只出现 (1/3)** |
| 脏树 | `error: cannot rebase: You have unstaged changes.` | 同 |
| autostash | `Created autostash: 49ffa44` | `Created autostash: 7aa2d47` |
| 终点 | `fatal: no rebase in progress` → `exit code 128` | 同 |
| 附加线索 | — | 两条 `warning: … CRLF will be replaced by LF`（`raw_data/top10_daily.json` / `triple_consensus.json`） |

⇒ **同文件、同机制、同日志形状、隔 2 天**。"=" 我的 v1 把它当「新发现」是错的。

### 1.3 影响面（未变）

仅该轮抓取结果未落库；产物 `data/RISK_GAUGE.js` ut = **13:43:11**（= #512 那轮有效值）⇒ **非数据事故、无补数必要**。

---

## 二、✅ 真正的新增价值：**首次全仓 30 支 workflow 全景台账**（此前只零散记「3 支」且行号错）

扫描方式：`GET /contents/.github/workflows` 取全量 30 支 → 逐支 `GET ...?ref=main`（raw）→ 匹配 `git rebase`。

| # | 文件 | 病灶行 | 失败处理 | 形态 | 状态 |
|---|---|---|---|---|---|
| 1 | `cloud_weekly_cleanup.yml` | **L230** | `exit 1` | 裸 rebase | 未迁 |
| 2 | `v8_backup.yml` | **L70 / L85** | `break` | 裸 rebase | 未迁（L76 段带 `continue-on-error: true` ⇒ 软失败） |
| 3 | `v8_algo_intraday_lite.yml` | **L159** | `exit 1` | 裸 rebase | 未迁 |
| 4 | `v8_risk_gauge.yml` | **L59** | `exit 1` | 裸 rebase | 🔴 未迁 · **09-18 与 09-20 两次实测爆** |
| 5 | `fill_kcbj_concepts.yml` | **L55** | `break` | 裸 rebase | 未迁 |
| 6 | `v8_intraday_snapshot.yml` | **L97** | `rebase → abort → 继续循环` | **先 rebase 再 push**（不同形态） | 未迁（L108 有软失败告警兜底） |
| — | `v8_build_deploy.yml` | **L470** | 同步远端 + 按最新 raw_data **全量重建**后重试 | ✅ 已治本 | — |
| — | `v8_cn_fetch_experiments.yml` | **L110–117** | 改走 `api_push_raw.py` | ✅ 已治本 | — |

> 🔧 **更正我方台账**：此前记「未迁 3 支（`cloud_weekly_cleanup` L199 / `v8_backup` L70,85 / `v8_algo_intraday_lite` L135）」
> ⇒ 实测行号应为 **L230 / L70,L85 / L159**，且**漏记 2 支**（`v8_risk_gauge` L59、`fill_kcbj_concepts` L55）。
> **请贵侧台账与之一并对齐。**

---

## 三、✅ 另一项新增价值：**「范本」自身坏死 + 被抄走的扩散证据**

`v8_backup.yml` **L64** 注释逐字：

```yaml
# 🛡 并发 push 互踩加固（对齐 v8_risk_gauge 范本）
```

⇒ **`v8_risk_gauge.yml` 是这套「push 被拒 → fetch+rebase 重试」模式的早期范本**，本 `v8_backup` 明确照抄；
而**范本自己今天又炸了一次**。→ 建议贵侧修 L59 时**顺手核其余 4 支**，避免「修一个、留四个同型」。

---

## 四、修法（与 v1 相同，请贵侧择一）

### 方案 A（推荐 · 一劳永逸）

照抄 `v8_cn_fetch_experiments.yml` L110–117 既有范式：

```yaml
#   原写法 git fetch origin + git rebase + git push HEAD:main 必败——
#   现改用 api_push_raw.py（GitHub Contents API，零 git fetch，免疫 cn git 墙）
- run: python api_push_raw.py
```

⇒ 零 git 交互 ⇒ **脏树/并发/rebase 三问题一次性消失**。

### 方案 B（最小兜底）

推送步开头加：

```bash
git config --global core.autocrlf false
git checkout -- .      # 已 commit 需保留的文件；此处脏项仅为 CRLF 虚拟差异
```

并把 L59 的 `{ git rebase --abort; exit 1; }` 改为
`{ git rebase --abort >/dev/null 2>&1 || true; continue; }`（**保住 3 次重试语义**）。

> ⚠️ B 只治「CRLF 虚拟脏」一种脏源；将来有真实未提交改动仍会复发。**故推荐 A。**

---

## 五、权限与影响面

- 🚫 我方 fine-grained PAT **无 `.github/workflows/**` 写权**（09-19 悬空探针实测 **403**）⇒ **修码请贵侧落**（或主人授权 classic token）。
- **影响面**：只导致「该轮抓取结果未落库」，不影响已落库值，不阻断下游构建（push 未发生 ⇒ `workflow_run` 不触发）。**无补数必要。**
- 🧭 **我方技能已同步更正**（`v8-ci-dirty-tree-crlf-diagnosis`：并入本台账 + 「判新旧前先扫技能库」纪律）。

---

## 六、复核命令（任一方可跑）

```bash
TOK=<pat>
# 1) 今日复现的日志
curl -sL -H "Authorization: Bearer $TOK" \
  https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/jobs/106043466985/logs \
  | grep -nE "rejected|cannot rebase|autostash|no rebase in progress|exit code"
# 2) 09-18 那次（computed 存在性 + 结论）
curl -s -H "Authorization: Bearer $TOK" \
  https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/jobs/105466298894 \
  | python -c "import sys,json;d=json.load(sys.stdin);print(d['conclusion'],[s['name'] for s in d['steps'] if s.get('conclusion')=='failure'])"
# 3) 核病灶行是否仍在（5 支）
for f in v8_risk_gauge v8_backup v8_algo_intraday_lite cloud_weekly_cleanup fill_kcbj_concepts; do
  echo "== $f"; curl -s -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github.raw" \
    "https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/.github/workflows/$f.yml?ref=main" \
    | grep -n "git rebase"
done
```

---

**署名**：阿狸咪的工程师（家机 `alimi-cn`）· 生成于 2026-09-20 16:30 CST
