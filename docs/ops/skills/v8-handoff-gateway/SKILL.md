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
