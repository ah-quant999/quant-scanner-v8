# CODEBUDDY.md — 项目级记忆（项目根自动加载）

> 本文件是**指针**，不重复任何规则正文。正文见仓根 `AGENTS.md`。

🔴 **动本仓（`quant-scanner-v8`）任何文件之前**，按顺序读：

1. `AGENTS.md` ← 入口索引：必读清单 ＋ 一屏速查 ＋ 硬禁区 ＋ 文件地图
2. `docs/ops/HANDOFF.yaml` ← **唯一状态源**（防重复劳动：先查这事是不是已有人在做）
3. `docs/ops/skills/v8-handoff-gateway/SKILL.md` ← 双机并发协议正文（唯一权威）

⛔ 最容易犯的三个错（详见 `AGENTS.md` §二）：

- 盘中 `09:15–11:30` / `12:45–15:00` 推仓，或改 `index.html`
- 用本地整文件直推、覆盖线上更新（应先比字节数与 md5，以线上真身为基底重放补丁）
- 改完不刷 `docs/ops/HANDOFF.ledger.json` ⇒ CI `[13/13]` 阻断部署
