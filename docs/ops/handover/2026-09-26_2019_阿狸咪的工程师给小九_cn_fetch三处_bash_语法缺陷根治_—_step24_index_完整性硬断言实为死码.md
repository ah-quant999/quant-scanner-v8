# HANDOVER｜阿狸咪的工程师 → 小九｜2026-09-26 20:19｜cn_fetch 三处 bash 语法缺陷根治 — step24 index 完整性硬断言实为死码

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

`v8_cn_fetch_cloud.yml` 有 **3 个 `run:` 块存在 bash 语法错误**（2 处是 2026-09-19 阿狸咪插入新 step 时插入点未按 step 边界所致，1 处是 **2026-09-23 小九补丁引入**）；
其中 **`soft_15`「🛡️ 原子提交 index.html ?v」的整段脚本一行都未执行**（heredoc 闭合标签被 YAML 剥成带 2 空格缩进 ⇒ bash 报 `unexpected end of file`），
⇒ 小九 09-23 补的**四项 index 完整性硬断言自引入起就是死码**，且该步的 `git add/commit/push index.html` 也从未跑过。
因 step 是 `continue-on-error: true`，每档只报 exit code 2、conclusion 却恒为 `success`（又一例「假绿」）。
**已由阿狸咪代为修复（`99fef522c817`）**，请小九复核与线上终验。

---

## 正文

### 一、铁证（本轮 run #2320 逐字）

`v8_cn_fetch_cloud` run **#2320**（id `36240203983`，head `e267b89b33bb`，09-26 19:53 CST 触发）step 表显示
`step24 「🛡️ 原子提交 index.html ?v」= success`。但其 job 日志尾部逐字为：

```
2026-09-26T11:55:43.6310695Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {0}
2026-09-26T11:55:43.6433897Z /home/runner/work/_temp/849fb0a0-….sh: line 64: syntax error: unexpected end of file
2026-09-26T11:55:43.6435992Z ##[error]Process completed with exit code 2.
```

⇒ **step 结论 success 与真实执行结果 exit 2 相矛盾**。同一档 step21（`soft_13` 刷新 HEALTH_CHECK）尾部同样
`##[error]Process completed with exit code 2.`。

### 二、本机净室复现（不依赖 CI）

按 YAML 块标量规则还原 run 块后 `bash -n`，**BEFORE / AFTER 对照**：

| # | YAML 行 | step | bash -n 结果（修复前） | 根因 |
|---|---|---|---|---|
| ① | L752 | `soft_13` 🩺 刷新 HEALTH_CHECK.js | `line 9: syntax error: unexpected end of file from 'if' command on line 7` | 块尾**缺 `exit 1` + `fi`** |
| ② | L775 | `soft_13b` 🐲 板块龙头股字典 | `line 11: syntax error near unexpected token 'fi'` | 块尾**多**了一段 `exit 1` + `fi` |
| ③ | L832 | `soft_15` 🛡️ 原子提交 index.html ?v | `line 64: warning: here-document at line 17 delimited by end-of-file (wanted 'PYEOF_IDXGUARD')` + `unexpected end of file from 'for' command on line 5` | heredoc 起始行/内容/闭合标签**整块 12 空格缩进**，YAML 剥离 10 空格基准后闭合标签剩 **2 空格**，bash 不认 |

修复后：**3 个 run 块语法错误 3 → 0**。

### 三、根因与责任（两条独立链路）

**① + ②（同一事故）** —— 2026-09-19 阿狸咪新增「🐲 板块龙头股字典」step 时，插入点选在了 `soft_13` 的
`echo` 之后、`exit 1`/`fi` **之前**（未按 step 边界插入），导致那两行被划入新 step 的 run 块。
⇒ `soft_13` 缺 `fi`、`soft_13b` 多 `fi`。
**影响轻**：bash 是流式执行，`python v8_health_check.py` / `python scripts/fetch_sector_leaders.py`
**仍照常执行**（step21 日志逐字有 `[INFO] 已生成 data/HEALTH_CHECK.js` + `统计 {ok:118,…}`；
第 2 轮亦取到 `fetch_sector_leaders.py:166` 的 traceback）⇒ 仅是**尾部软失败告警/退出码失效**。
**阿狸咪认领并已修**。

**③** —— 2026-09-23 08:52 `631123e0bd8a`「fix(ci): 缺口② cn-fetch-writer-version-drift」引入（小九补丁），
经 `git/blobs` 逐版核对：**自该版起，其后 8 个版本全部带此缺陷**（`52b01b8b7b6a` 等均为 BUG）。
**影响重**：heredoc 未闭合会把后续所有行吞进 heredoc ⇒ `for i in 1 2 3; do … done` 整体无法构造
⇒ bash **在解析阶段即失败，整段一行不执行**。被吞掉的包括：

- 四项 index 完整性硬断言（`MIN_LINES=18800` / 末 200 字含 `</html>` / A2 三锚 / `MIN_BYTES=1250000`）
- `git add -f index.html` + `git commit` + `git push`（即该步**设计目的**本身也从未执行）

### 四、纵深影响评估（**为何定级 P1 而非 P0**）

`index.html` 完整性仍是**三层纵深**：
1. `update_v8.py::_atomic_write_index_html()` 软守卫（末 200 字含 `</html>`）—— **有效**
2. `v8_build_deploy` 的 `[10/10] index 核心标记守卫`（真源 `docs/ops/index_protected_markers.txt`，38 标记）—— **有效**（每档 gate 实跑）
3. **本步的 `soft_15` 四项硬断言 —— 失效（本轮发现）**

⇒ 第 3 层失效，第 1、2 层仍在，故**降级为 P1**（不复现 09-22 的「无防护」态）。
另：`?v` 的原子提交失效 ⇒ 依赖 `v8_cache_buster_reconcile` 兜底；实测线上 `?v` 已是内容哈希且跨多轮零漂移（第 7 轮已验），影响可控。

### 五、修复内容（commit `99fef522c817`，+29 / −30）

| # | 修改 | 说明 |
|---|---|---|
| ① | `soft_13` 块尾补 `exit 1` + `fi` | 行数 +2 |
| ② | `soft_13b` 块尾删残留 `exit 1` + `fi` | 行数 −3 |
| ③ | `soft_15` heredoc 块整块缩进 12 → 10 空格 | 27 行，使其与 `run:` 基准对齐 ⇒ 闭合标签顶格 |

### 六、验证（全部为本轮实测）

- **YAML**：`yaml.safe_load` 通过；**28 个 step 的签名（name/id/if/run 前 40 字）修复前后一一相同 ⇒ 语义零改动**。
- **语法**：该文件 26 个 `run` 块 `bash -n` 错误 **3 → 0**。
- **拦截力复测**（把修复后的守卫 python 抠出独立跑）：
  - c1 正常态（main `149ad390c99a` / 19,315 行 / 1,361,458 B）⇒ **rc=0 放行** ✅
  - c2 删尾 183 行 ⇒ rc=1 拦截（末 200 字无 `</html>`）
  - c3 挖 A2 锚 `{name:'LHB_HISTORY'` ⇒ rc=1 拦截
  - c4 去 `</html>` ⇒ rc=1 拦截
  - c5 **真事故态文件**（`7c78439fe8`，09-22 22:20 那笔，1,338,018 B / 18,966 行）⇒ rc=1 拦截（3 条错误）✅
- **推送自证**：`GET /commits/99fef522c817.files` = **恰 1 个登记路径**；parent = 我真取 tip `865b68e226de`；
  `GET /contents` 回读 89,519 B **逐字节一致**，blob `f4bf6f6d73ac` 符合预期。
- **GitHub 接受**：`GET /actions/workflows?per_page=100`（total_count=35）**含** `v8_cn_fetch_cloud.yml` ✅

### 七、请小九复核 / 线上终验口径（**下一档 cn_fetch 后**）

1. `step24` 日志应出现 **`✅ index.html 完整性断言通过：行数=… 字节=… 尾部闭合=OK A2三锚=OK`**，且**不再有** `syntax error: unexpected end of file`；
2. `step21` / `step22` 尾部**不再有** `##[error]Process completed with exit code 2.`（若脚本因真实失败走 `exit 1`，属**预期**，此时应能看到 `::error title=v8-softfail:soft_13…` 显式告警）；
3. 若 `index.html` 无变化，step24 应打印 `ℹ️ ?v 已最新，无需推送`（说明 `git add/commit` 路径已恢复）。

### 八、复盘（新判据，建议入库）

🔴 **「workflow 里写了的防护」必须做 `bash -n`，不能只看源码 grep** —— 本轮即因前轮只 grep 到
`MIN_LINES = 18800` 等字符串就判「硬断言已就位」，实际它是**死码**。建议把
「还原 run 块 → 替换 `${{ }}` → `bash -n`（**仅 bash 块**，`shell: powershell` 的块须跳过）」
纳入 `pre_deploy_audit` 或独立巡检脚本。
（本轮全仓 34 个 workflow / 180 个 run 块已扫一遍：**除本文件 3 处外，其余命中均为 PowerShell 块的假阳性**。）

---

*阿狸咪的工程师 / alimi-cn ｜ 2026-09-26 20:3x CST ｜ 本轮全程只读 + 2 笔推送，未派发任何 workflow*
