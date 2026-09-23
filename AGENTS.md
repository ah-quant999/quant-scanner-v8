# AGENTS.md — AI 会话入口（本仓强制）

> 🔴 **本文件是「入口索引」，不是协议正文。**
> - 并发协议正文（**唯一权威**）：`docs/ops/skills/v8-handoff-gateway/SKILL.md`
> - 状态源（**唯一权威**）：`docs/ops/HANDOFF.yaml` ＋ 外部锚 `docs/ops/HANDOFF.ledger.json`
>
> 双机经 `git show <tip>:<路径>` 均可读，**无需任何本地副本**。
> 所以本文件**不放协议正文** —— 避免造出第二份权威、避免「哪份为准」的分歧。

本仓由**双机 × 多会话**共写：小九机（白天独家 07:45–17:45）／阿狸咪机（夜间 18:00–次日 07:30 ＋ 周末）。

实测病根（2026-09-21）：`docs/ops/handover/` 累计 **518 档**、峰值 **62 档/天**，
而「什么还没做」散落在几百个档里 ⇒ 下一个会话只能**重新实测一遍**
⇒ **重复劳动 ＝ token 双倍消耗**。

**本文件存在的唯一目的：让每个会话在动手前，知道该读哪一份、以及最容易踩什么坑。**

> 🔴 **主人工作守则（2026-09-23 入协议 · 双机所有会话/专家通用）**：
> ① 只有**不确定主人意图**时才问意见和建议，否则用专家科学方法自主行事——
>   发现问题直接一劳永逸修复，审计没问题直接上线；② 邮件**只发不能自愈/不能解决**的；
> ③ 每笔改动收口**三件套**＝审计 ＋ 云端/双机/运维页/逻辑详解页四方对齐 ＋ 防覆盖推仓并交接。
> 全文见协议 `SKILL.md`「主人工作守则」节（本行只是镜像指针，以协议为准）。

---

## 一、🔴 动手前必读（顺序不可换）

| # | 文件 | 解决什么 |
|---|---|---|
| 1 | `docs/ops/HANDOFF.yaml` | **唯一状态源**。先查「这件事是不是已经有人在做／已做完」—— 这是**防重复劳动的唯一手段** |
| 2 | `docs/ops/skills/v8-handoff-gateway/SKILL.md` | **并发协议正文**：写仓窗口／并发 5 条／交接纪律／编辑状态源的 4 条硬约束 |
| 3 | `SECURITY_RULES.md` | token 与凭证铁律（**本仓是 PUBLIC 仓库**） |
| 4 | `TIME_ORDER.md` | **仅当你要改 cron／workflow 时点**前读（防颠倒依赖致数据被覆盖） |

> 改前端（`index.html` / `logic.html` / `data/*.js`）前，另读
> `.github/scripts/pre_deploy_audit.py` 里的 checks 清单 —— 它是**部署硬门禁**，不过即阻断。

---

## 二、⚡ 一屏速查（最容易踩的 7 条）

**1. 写仓窗口**：盘中 `09:15–11:30` / `12:45–15:00` **禁推、禁碰 `index.html`**。
放行：盘前～`09:15`、午休 `11:30–12:45`、`15:00` 之后。

> 出处：主人令（本机 `v8-write-window-and-push-guard` 载录；2026-09-15 实测「漏起点即出事」）。
> **本行是跨机可见的镜像**：如主人调整窗口，须**同批改此处并登记 `HANDOFF.yaml`**。

**2. 取远端真身**：`raw.githubusercontent.com` 可能**整域不可用**；
`Accept: application/vnd.github.raw` 会 302 跳过去 ⇒ 必失败。
正解 `GET git/blobs/<sha>`（同域 `api.github.com`，base64）。
**`len == 0` 一律判「取失败」**，必须断言长度下限（例：`index.html` ≥ 1 MB）。

**3. 禁写死 sha／tip**：`main` 被云端**分钟级 churn**。一律运行时**现取**。

**4. 判「改的是否真上线」**：只认**内容 blob 逐字节比对 ＋ 字节数 ＋ md5**。
**不认 commit SHA 关系**（会被「整合提交」收编）；**`提交进仓库` ≠ `线上生效`**。

**5. 判「某串是否生效」**：直接 `count()` —— **新串 > 0 且旧串 == 0**。
**别读 diff 的 `+/-` 号**（`-` 属左、`+` 属右，极易读反）。

**6. 推前防覆盖（本仓第一号事故源）**：先比「线上 blob 字节数 ＋ md5」与本地基线；
**不等则走「以线上真身为基底的补丁重放」**，**严禁直推本地整文件**
（本地底稿常落后线上数十万字节，2026-09-21 实测落后 415,823 B）。

**7. 交接只写状态源**：待办／待验证／待拍板一律写 `docs/ops/HANDOFF.yaml`，
**只增自己的项、不改别人的项**。
`docs/ops/handover/*.md` **仅限**「需人拍板」或「跨机需知的结构性变更」；
**禁止回执档、催办档**（收到 ＝ 改 `status` 字段）。
🔴 **改了任何 item ⇒ 必须同一提交刷新 `HANDOFF.ledger.json`**，否则 CI `[13/13]` 拦截。

---

## 三、🚫 硬禁区

- **禁止** `git add -A` / `git add .` / 对主工作树 `reset --hard` / `checkout --`。
  推送新文件用 `git worktree` 或单文件 API（主树长期有大量未提交 WIP，一律不许碰）。
- **禁止**把 token／凭证写进任何入库文件（含临时脚本）。见 `SECURITY_RULES.md`。
- **禁止**新建数据通道：前端**只读注入的 `window.X`**，禁止 `fetch('../data/...')`。
  `data/*.js` 含 `NaN` ⇒ 解析必须 `vm.runInContext`，**禁 `JSON.parse`**。
- **禁止**删除 `DO_NOT_DELETE.md` / `PROTECTED_FILES.json` 列出的资产（含累积型 `raw_data/`）。

---

## 四、🗺️ 文件地图

| 类别 | 路径 | 说明 |
|---|---|---|
| 主站 | `index.html` | 单文件前端（全部 UI ＋ 渲染逻辑），**行尾 LF** |
| 逻辑详解 | `logic.html` | 策略逻辑说明页，**行尾 CRLF 全覆盖**（`bare_lf == 0`） |
| 前端数据 | `data/*.js` | 各卡数据，注入 `window.X`（含 `NaN`，非严格 JSON） |
| 状态源 | `docs/ops/HANDOFF.yaml` | 「什么还没做」的唯一视图 |
| 外部锚 | `docs/ops/HANDOFF.ledger.json` | 只增不减；防「状态源被旧版本静默覆盖」 |
| 协议 | `docs/ops/skills/v8-handoff-gateway/SKILL.md` | 并发协议（唯一权威） |
| 部署门禁 | `.github/scripts/pre_deploy_audit.py` | 部署前硬校验，**不过即阻断** |
| 工作流 | `.github/workflows/` | 30 条链；改 cron 前先读 `TIME_ORDER.md` |
| 数据保护 | `PROTECTED_FILES.json` | 累积型数据，删除不可恢复 |
| 禁删清单 | `DO_NOT_DELETE.md` | 误删防护（另产出 `data/DO_NOT_DELETE.js` 供逻辑页用） |

---

## 五、📌 本文件自身的纪律

- 只放「**往哪读**」＋「**最容易踩的坑**」，**不放协议正文**（避免第二份权威 ⇒ 分歧）。
- 协议正文变更 ⇒ 改 `docs/ops/skills/v8-handoff-gateway/SKILL.md`，本文件**只需保持指针有效**。
- 行尾 **LF**（与仓内其余根级 `.md` 一致）。
- 引入背景与验收记录：`docs/ops/HANDOFF.yaml` → item `handoff-ai-entry-file`。
- 🔴 **改完本文件（或 `SKILL.md`）必须同步到「会话实际工作目录」——否则等于没改。**
  依据（CodeBuddy 官方文档 `/cli/memory` 原文）：记忆文件「**在启动时自动加载到上下文中**」，
  且项目级是「**从当前工作目录向上递归加载**」`CODEBUDDY.md` 与 `AGENTS.md`。
  ⇒ **文件只躺在远端 ＝ 没有会话会读到它。**
  本仓常用 **API 隔离推送**（按设计绕过本地工作树）⇒ 推完**必跑一次本机同步**：

  ```bash
  python C:/Users/Administrator/.workbuddy/scripts/v8_handoff_edit_kit.py ai-entry-sync
  ```

  它把 `AGENTS.md` / `.codebuddy/CODEBUDDY.md` / `SKILL.md` 逐字节落到**本地工作树**＋**本机 skill 副本**。
  验证：重跑一次，输出应全部为「＝ 已一致」（md5 与线上 blob 相同）；任一处打「↑ 已更新」即说明上次漏同步。

- 🔴 **双机用户级目录互相独立**（2026-09-21 实测盲区，曾导致阿狸咪机「不知道入口文件」）：
  小九机铺的 `~/.codebuddy/CODEBUDDY.md` 阿狸咪机**看不到**；且原先写死小九机路径
  `E:\qs_workspaces\quant-scanner-v8`，对她机器是错的（盘符／路径不同）。
  ⇒ **每台机必须单独铺自己的用户级指针**，且指针内容必须是**路径无关**版（已改为
  `git -C <你的仓根> show origin/main:AGENTS.md` 这类与绝对路径无关的法子）。
  - **小九机**（有专属工具）：推完入口文件跑
    `python C:/Users/Administrator/.workbuddy/scripts/v8_handoff_edit_kit.py ai-entry-sync`
    （同步本地工作树＋本机 skill 副本）。
  - **阿狸咪机 / 其他任何机**（无小九机专属工具）：`git pull` 后在仓内跑
    `python scripts/ai_entry_bootstrap.py`（仓内**自包含**脚本，自动探测仓根、写路径无关
    用户级指针，不依赖小九机文件）。
  - **最稳的一步**：直接把 WorkBuddy 会话工作目录设为 **v8 仓根** —— 仓内
    `.codebuddy/CODEBUDDY.md` 会被自动加载，无需任何用户级指针。
