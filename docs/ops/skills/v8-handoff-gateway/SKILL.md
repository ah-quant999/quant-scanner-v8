---
name: v8-handoff-gateway
description: |
  用于 quant-scanner-v8（及同类双机/多会话共写仓库）的双机交接治理。
  触发场景——主人说「最近双机联合改动大，是不是遇到很多交接方面的问题」
  「有什么办法解决么」「不浪费时间也不浪费token」「交接太乱了」，
  或你要写/读一份 `docs/ops/handover/*.md` 交接档之前。
  核心：把「每事一档」的聊天式交接，改为「唯一状态源 + 代码注释 + 仅在需人拍板时写档」。
  一句话：**交接档是给人拍板用的，不是给机器同步状态用的。**
---

> ## 🔴 载体与版本（2026-09-21 入仓 · 阿狸咪评审 `handoff-skill-inrepo` P1 的落地）
>
> **本文件（仓内 `docs/ops/skills/v8-handoff-gateway/SKILL.md`）是唯一权威载体。**
> `~/.workbuddy/skills/v8-handoff-gateway/SKILL.md` 是**派生物** —— 双机各自 `cp` 得到。
> 入仓前实测：阿狸咪机 `~/.workbuddy/skills/` 下此 skill **MISSING**、仓内 `find -name "*handoff-gateway*"` **0 命中**
> ⇒ 协议自述目标「让 AI 会话自动遵守，**不靠人记**」对另一台机**已落空**。
>
> **纪律**：改协议必须「先改仓内 → 再 `cp` 到本地」。反向（本地改了没进仓）会造成双机分叉 ——
> 那正是本仓在 `index.html` 上已吃过两次亏的同一形态。
>
> 同步命令（双机通用）：
> ```bash
> cp docs/ops/skills/v8-handoff-gateway/SKILL.md ~/.workbuddy/skills/v8-handoff-gateway/SKILL.md
> ```
>
> ### 2026-09-21 12:0x 新增协议要素（随入仓一并固化）
>
> **① 并发写协议 = A + C + D**（原项 `handoff-concurrent-write`）
> - **A** 一次 push 只改自己 owner 的 item。
> - **C** 本地 git 路径：写前 `git pull --rebase`，冲突即 abort，禁裸 push。
> - **D** 🔴 **API 路径（本仓实际主用 `base_tree` + `force:false`）**：
>   该路径**不产生 merge 冲突** —— 若「现取 tip」再推同一文件，自己的 blob 会**静默顶掉**对方改动。
>   ⇒ 比冲突严重一档：**冲突会喊，覆盖不会**。
>   故：推单文件前**重取该文件 blob sha**；与读取时不一致 ⇒ **不是 abort，而是基于新内容重放**
>   （本文件写入语义是「追加/改自己项」，天然可重放）。
>   这与本仓既有铁律「基线漂移预检：字节数不等即重基线重放，绝不 force」同型。
>
> **② 状态源有 [13/13] 门禁了**（原项 `handoff-yaml-guard`）
> `pre_deploy_audit.py` 的 `check_handoff_ledger()` 断言：
> `yaml` 可解析 / 每项 id+priority+owner+status 齐全 / status ∈ 白名单 /
> `pending-verify` 必有 `verify_how` / **无未来时戳**（容差 5min）/
> **`ids ⊇ docs/ops/HANDOFF.ledger.json` 的 ids** / **`next_id_seq ≥ ledger.max_next_id_seq`**。
>
> 🔴 **为什么需要外部锚 `HANDOFF.ledger.json`**：单文件下 `next_id_seq` 与条目序号会**一起回滚**，
> 「文件内部自洽性」**永远检查不出被旧版本覆盖**。
> ⇒ **推 `HANDOFF.yaml` 时必须同一提交刷新 ledger**：追加新 id、抬高 `max_next_id_seq`；
> 每月清理已完成项时同批更新 `ids`。ledger 缺失 ⇒ 门禁放行并告警（守卫自身不成单点）。


# 双机交接网关（HANDOFF Gateway）

## 0. 为什么需要这个 skill（实测病根）

2026-09-21 实测本仓 `docs/ops/handover/`：

| 指标 | 实测值 |
|---|---|
| 交接档总数 | **518 个** |
| 近 7 天字节数 | **431 KB** |
| 峰值日（09-20） | **62 档/天**，21 时一小时 **9 档** |
| 「回执_未回执交接对齐」纯握手档 | **22 个 / 417 KB / 均值 19 KB，零技术内容** |
| 09-20 单档标题重复次数 | 同一标题 **7 次**（催办） |

**三层病根**：

1. **把「聊天」当「交接」** —— 回执档（「收到」「已核验」）+ 催办档（「还没回我」）占大头，零技术内容。
2. **同一件事拆成 3–5 档** —— 典型链条：`改 → 核验 → 催办` 三连。
   实测 06:58(改动) / 07:05(收口) / 01:47(催办) 是**同一件事**。
3. **状态散落** —— 「什么还没做」散在几百个档里；下一个会话（甚至同一台机的我）
   **无法快速知道当前挂账**，只能重新实测一遍 ⇒ **重复劳动 = 双重浪费**。

**真实代价**：每档 = 写 + push + 对方拉 + 读 + 回写。双机各一次。
且每档永久进 git 历史，`git log`/`grep` 检索被稀释。

---

## 1. 铁律（改任何交接行为前先读）

1. 🔴 **状态只写 `docs/ops/HANDOFF.yaml`，不散落在档里。**
   查「还有什么没做完」= 读这一个文件，**不翻 handover 目录**。
2. 🔴 **技术细节写进代码注释。** 「改了哪行、为什么这么改」就地可查 ——
   改代码的人必然看到注释，但不会去翻 500 个档。
3. 🔴 **改动记录写进 git commit message。** 这是**天然的交接收件箱**：
   `git log --oneline` 一行可查，不占额外文件、不需额外推送。
4. 🔴 **严禁「回执档」「催办档」。**
   收到 = 改 `HANDOFF.yaml` 的 `status` 字段（一次编辑，几行）。
   需要催办 = 说明档里没写清「谁该做什么」⇒ **修根因，不加催办**。
5. 🔴 **只在两种情况写 .md 档**：
   (a) **需要人拍板**（决策类，含选项与推荐）；
   (b) **跨机需知的结构性变更**（改了双机共同依赖的协议/口径）。
   技术改动、核验结果、进度汇报 —— **一律不写档**。
6. 🔴 **`pending-verify` 状态不得宣称「已修复」。**
   判据纪律：`代码改了` ≠ `产物重跑了` ≠ `被 run 验证生效`。
   必须填 `verified_at` 才能置 `done`。

---

## 2. 状态源格式（`docs/ops/HANDOFF.yaml`）

```yaml
meta:
  updated: "YYYY-MM-DD HH:MM"
  updated_by: "小九(lemoncat-cn)"      # 或 阿狸咪(alimi-cn)
  next_id_seq: 12

items:
  - id: build13-timeout-guard           # 稳定标识，用于跨档引用
    priority: P0                        # P0 / P1 / P2
    owner: shared                       # 小九 / 阿狸咪 / shared
    status: pending-verify              # todo/doing/pending-verify/blocked/done
    what: "第13步超时护栏缺口：只包 git 命令未包 python 重建"
    fix: "已加 timeout 300 + 失败即 exit 1"
    evidence: "commit 61bc3fc03070"
    verify_how: "等下一轮 run 核对 step[13] 耗时 ≤20min"   # pending-verify 必填
    verified_at: null                   # done 时必填
    updated: "2026-09-21 08:40"
```

### status 语义（**最易误用的一栏**）

| status | 含义 | 对外可否称「已修」 |
|---|---|---|
| `todo` | 未开始 | 否 |
| `doing` | 进行中，有 active owner | 否 |
| `pending-verify` | **改动已上线，尚未被运行验证** | 🔴 **否** |
| `blocked` | 等外部条件（等 run / 等对方 / 等拍板） | 否 |
| `done` | **已验证生效**（须填 `verified_at`） | 可 |

---

## 3. SOP

### 3.1 开工前（成本 1 次读取）

```bash
# 读状态源，确认当前挂账
python -c "
import io,yaml
d=yaml.safe_load(io.open('docs/ops/HANDOFF.yaml',encoding='utf-8').read())
for i in d['items']:
    if i['status']!='done':
        print('[%-14s] %-28s %s' % (i['status'], i['id'], i['owner']))
"
```

**不要**先去 `ls docs/ops/handover/ | head -30` —— 那是 518 个档，读不完且没重点。

### 3.2 做完一件事

1. 技术改动 ⇒ 写**代码注释**（含「为什么」）+ **commit message**（含改动理由）。
2. 更新 `HANDOFF.yaml` 对应项的 `status` / `evidence` / `updated`。
3. **若状态是 `pending-verify`，到此为止 —— 不发档、不发回执。**

### 3.3 需要对方做事

在 `HANDOFF.yaml` 里加一条 `owner: 阿狸咪` 的 item，把 `verify_how` 写成**可跑的命令**。
**不要**为此写一份 .md 档。

### 3.4 需要主人拍板

**这才写 .md 档**，且必须含：选项对比 + 明确推荐 + 理由。
文件名格式：`YYYY-MM-DD_HHMM_小九给主人_<决策主题>.md`

### 3.5 收尾（替代「回执」）

在 `HANDOFF.yaml` 改状态字段即完成握手。
若确需对方留意，在 item 里加 `note_to: 阿狸咪` 字段。

---

## 4. 判据陷阱

| 陷阱 | 正解 |
|---|---|
| 档里写「已修复」但其实是 `代码改了` | 查 `status` 是否 `done` **且**有 `verified_at` |
| 「对方没回」⇒ 写催办档 | 说明 `owner`/`verify_how` 没写清 ⇒ 修 item，不加档 |
| 「这次改动很重要，得写详细点」 | 重要 ⇒ 注释写详细。**档的数量不因重要性增加** |
| 想用交接档做「工作记录/日志」 | 用 `git log`。交接档是**决策与跨机协议**载体，不是日志 |

---

## 5. 判据口诀

> **档 = 给人拍板的。**
> **状态 = 给机器同步的（HANDOFF.yaml）。**
> **细节 = 给改代码的人看的（注释）。**
> **历史 = 给检索用的（commit message）。**

四者不要混。混了就是今天的 518 个档。

---

## 6. 历史档处置（不删，只归档）

518 个旧档**不删除**（是审计证据链），但：
- 在 `docs/ops/handover/README.md` 说明「本目录为**历史归档**，当前挂账见 `../HANDOFF.yaml`」。
- 新增档一律进 `docs/ops/handover/` 但**数量受 §1.5 约束**（只拍板类 + 协议类）。
- 需要查旧档时用 `grep -l <关键词>` 精确定位，**不要 `ls | head` 通读**。

---

## 🔵 2026-09-21 实战教训（随本批一并入仓）

> 本节已随本批（commit 见 `git log`）**一并入仓**，双机本地副本与仓内逐字节一致。
> 本节内容全部来自 2026-09-21 午休窗一次真实上线的实战取证，非推测。

### 1. 🔴 「冲突」与「静默覆盖」是两个不同严重度的问题

设计并发防护时，最常见的错误是把它们混为一谈：

| 路径 | base 落后时的表现 | 严重度 |
|---|---|---|
| **本地 git push** | `non-fast-forward` **报错**（rejected） | 🟢 安全失败 —— 会喊 |
| **Git Data API**（`base_tree` + `force:false`） | **不报错**，自己的 blob **静默顶掉**对方对同文件的改动 | 🔴 危险 —— 不会喊 |

⇒ 本仓双机**实际主用 API 路径**，故只防「merge 冲突」是不够的。
**正解（协议 D 条）**：推单文件前**重取该文件 blob sha**；与读取时不一致
⇒ **不是 abort，而是基于新内容重放**（账本类文件的写入语义是「追加/改自己项」，天然可重放）。

**实战证据（2026-09-21 12:20 午休窗）**：一次 7 文件推送**连续 2 轮** `422 Update is not a fast forward`，
第 3 轮成功 —— 取 tip 到 PATCH ref 之间被 cache-bot churn 顶掉。
若当时是「不重取 tip 直接 force」，那两次就是**静默覆盖**。

### 2. 🔴 单文件账本的「自洽性检测」永远检测不出回滚 ⇒ 必须有外部锚

这是把状态源收敛为**单文件**后**新引入**的盲区（不是原有问题的放大）：

```
单文件场景：next_id_seq 回退 ⟺ 条目序号也一起回退  ⇒ 文件内部「看起来完全自洽」
多文件场景：某一份被旧版本覆盖，另外几分仍在 ⇒ 交叉比对能发现
```

⇒ **必须有一个文件之外、只增不减的锚**。本仓落地：`docs/ops/HANDOFF.ledger.json`
（`{max_next_id_seq, ids[]}`），门禁断言 `ids ⊇ ledger.ids` + `next_id_seq ≥ max_next_id_seq`。

**维护纪律**：推账本时**同一提交**刷新 ledger；清理已完成项时同批更新 `ids`。
ledger 缺失 ⇒ 门禁**放行并告警**（守卫自身不得成为新的单点阻断源）。

### 3. 🔴🔴 改代码时，**断言比代码更容易写错**（本轮血训，5 处中 3 处属此类）

本轮我写错的**断言/测试**数量 > 写错的**代码**数量。逐项列出，都是有迷惑性的假阴性：

| 症状 | 真因 | 正确写法 |
|---|---|---|
| 「门禁没抓住未来时戳」 | 反测用例把新 `updated` **插在已有 key 之前** ⇒ YAML 同 key 后者胜，被原值覆盖 | 必须**替换**已有值，不插入 |
| 「某文件本地与线上不一致」 | `len(str)` 是**字符数**不是字节数（中文 UTF-8 3 字节） | 比 `len(s.encode("utf-8"))` 或直接比 `bytes` |
| 「7 个文件字节数全部虚高 38%」 | `/git/blobs` 用 `Accept: application/vnd.github+json` ⇒ 返回 **JSON 包装**（base64 + 双引号转义） | 必须 `application/vnd.github.raw` |
| 相减抛 `TypeError`（非返错值） | `datetime.now(timezone.utc)` 是 **aware**，`strptime` 产出 **naive** | `.replace(tzinfo=None)` 统一口径 |
| 门禁「挂载了却没执行」 | 被检查函数**抛未捕获异常** ⇒ 前面 N 项已打印 ✅、第 N+1 项静默消失、exit code 非 0 | 离线**单独调用**该函数抓 traceback，别只看总输出 |

**通则**：① 反测（负向测试）必须**单独验证**，不能只看「正向绿了」；
② 断言里的「数量/长度/字节」必须**写明单位口径**；
③ 新挂的门禁，先**离线单跑该项**确认无异常，再看整体。

### 4. 🔴 一次性上线快照的清单**会过期**

本机定时快照（`scheduledAt` 的一次性自动化）在**创建时刻**固化了「要推哪些文件、基线多少」。
若其后又改了产物（本轮：创建后又写了 3 项裁决），快照会按**旧清单**推
⇒ 轻则**丢掉新改动**，重则**与外部锚失配**（ledger 与账本对不上，门禁红）。

**纪律**：快照触发前若产物已变更 ⇒ **暂停快照 → 手推 → 删除快照**，
不要「让快照跑完再补推」（会产生两次 build + 中间态不一致）。

### 5. 「离线跑通」≠「CI 里生效」

门禁/脚本在本地跑绿，**只证明它能跑**；要证明「已挂进链路并生效」，
必须看**该 commit 对应的 CI run**，且看 **step 级**结论而非 run 级：
- 门禁 step `success` **且下游部署 step 未 `skipped`** ⇒ 才说明门禁真的通过了（而不是被绕过）。
- ⚠️ 注意 `continue-on-error: true` 的 step 在 API 里**恒报 success**，需靠「下游步是否 skipped」反推。
