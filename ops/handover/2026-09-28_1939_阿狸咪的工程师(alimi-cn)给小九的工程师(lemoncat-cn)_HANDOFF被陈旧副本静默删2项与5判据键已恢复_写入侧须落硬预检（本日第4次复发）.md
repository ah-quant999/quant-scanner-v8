# HANDOVER｜阿狸咪的工程师(alimi-cn) → 小九的工程师(lemoncat-cn)｜2026-09-28 19:39｜HANDOFF 被陈旧副本静默删 2 项 + 5 判据键（已恢复）· 写入侧须落硬预检
> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

`12f0c6f3cbf8`（本日 **17:48 CST**）把 **09-27 22:00 的陈旧本地副本**当内容源写 `docs/ops/HANDOFF.yaml`，**静默删除 2 个挂账项 + 5 个判据键**；`HANDOFF.ledger.json` 被同源一起回退，`[13/13]` 门禁**全程无感**。阿狸咪已按「远端 main 为基底做并集重建」恢复（**items 105 → 107**），并同批官方口径重算 ledger、离线跑真门禁复核。**本日起已第 4 次复发**，写入侧硬预检仍只写在 skill 里、**未落码**。

---

## 正文

### 一、取证链（全部远端 API 真身，非本机副本、非推断）

| 项 | 值 |
|---|---|
| 复发提交 | `12f0c6f3cbf8` @ `2026-09-28T09:48:28Z` = **17:48 CST**，署名 `ah-quant999 <2814546@qq.com>`（双机共用账号） |
| parent | `fd5d97d56e9c` ⇒ **基线是最新的**（该 parent 的 HANDOFF blob = `31fcd17862d0` / 640,509 B / items=106 / next_id_seq=93 / meta.updated=17:15） |
| 该提交改动 | `docs/ops/HANDOFF.yaml` **+60 / -236 行**；同批交接件 `docs/ops/handover/2026-09-28_1749_阿狸咪的工程师(alimi-cn)给小九的工程师(lemoncat-cn)…` ⇒ **写入方为 alimi-cn 侧** |
| 落盘内容 | blob `b1f834ed7c79` / 621,605 B / items=105 / **next_id_seq 93→92** / **meta.updated 17:15→`2026-09-27 22:00`** |
| 硬指纹 | 本机工作树该文件**同态**（621,605 B / seq 92 / updated 09-27 22:00）⇒ 内容源 = **09-27 22:00 的陈旧快照**（违反本仓「内容源取远端 contents API」纪律） |

**净效果 —— 静默删除 2 项 + 5 键，同时新增 1 项：**

- 被删 item：`algo-cloud-noop-wallclock-waste`（本日 08:47 立账，done / P1，owner 阿狸咪）、`lhb-history-size-slim`（todo / P2，owner shared）
- 被删判据键（`alimi_verify_20260928_*`，各自最后一次实测判据**整段蒸发**）：
  `_1650`（owner `experiment-card-stalled-3d-0925`）、`_1715`（`handoff-meta-future-timestamp`）、
  `_1720`（`handoff-ledger-hash-desync`）、`_1730`（`handoff-yaml-stale-base-item-drop`）、`_1810`（`resonance-calendar-lazyload-fail`）
- 新增 item：`lhb-history-today-empty-placeholder`（保留，未回退）

### 二、门禁第 4 次无感（判据本身是盲区）

`docs/ops/HANDOFF.ledger.json` **被同源一起回退**：`ids 106→105`、`max_next_id_seq 93→92`、`updated 17:10→17:48`，两个被删项的哈希锚**同时消失**。

`[13/13]` 的判据只有 `ledger.ids ⊆ yaml.ids` + `next_id_seq ≥ ledger.max_next_id_seq` ⇒ **文件内自洽** ⇒ 跨提交的整段丢失**永远查不出**（与 09-26 立项时记录的盲区逐条一致）。

### 三、本轮处置（单提交，阿狸咪的工程师）

1. **并集重建**：以**远端 main 现文**（blob `b1f834ed7c79`）为基底，逐 item 块与 `fd5d97d56e9c` 比对 —— 同 id 取块内 `updated` 较晚者（并列取字节更长者）、ref 独有项按 fd5d 中的原后继位置插回 ⇒ 恢复 2 项 + 5 键；`lhb-history-today-empty-placeholder` 原样保留。
2. **meta 归位**：`next_id_seq` `92 → 93`；`updated` 取推前实刻。
3. **官方口径重算 ledger**：仓外最小树跑 `scripts/handoff_ledger_hash.py --fix` ⇒ **107/107 命中 · 失配 0 · 未收录 0**（`--fix` 幂等自证 100%）。
4. **离线真门禁复核**：仓外树跑 `.github/scripts/pre_deploy_audit.py::check_handoff_ledger()` ⇒ 逐字
   `(True, '交接状态源完好：items=107（ledger 锚 107 个 id 全在）· next_id_seq=93≥93')`
5. **同批留证**：把本次复发证据（parent / blob / 指纹）作为判据键 `alimi_verify_20260928_1950` 追加进 `handoff-yaml-stale-base-item-drop`，并把该项 `status` 由 `pending-verify` **退回 `doing`**（本日复发即证 fix(B) 未闭环）。
6. 推后逐字节回读自证 + 6 分钟覆盖哨兵（判据：blob sha 与关键 id 集合不变）。

### 四、请小九拍板 / 落码（本项仍未闭环）

本项 `fix(B)「写入侧强制预检」`**至今只写在 skill 里、未落成硬门禁**，本日 17:48 即因未落实再度翻车。建议落两条硬判据：

1. **推送器侧**：造 blob 之前断言「本地基底 blob sha == 远端 tip 该文件 blob sha」，不等即**整轮放弃**；严禁「同内容 blob + 新 parent 重建」自证式动作。
2. **门禁侧**（`[13/13]`，需你拍板 —— 该门禁史上多次硬阻 deploy）：记录 `items` 数与 id 集合的**历史最大值**，下一档出现**减少**即告警。

> 阿狸咪本轮**未改门禁、未改口径脚本**，只做恢复 + 留证。

### 五、附：本轮判据纪律（可复用）

- 判「是否被覆盖」不看行数增减，看 **`meta.next_id_seq` / `meta.updated` 是否倒退** —— 倒退即陈旧快照指纹。
- 判「是否真删除」必须**双读 YAML + ledger**：ledger 一起退 ⇒ 门禁恒绿 ⇒ 只能靠**跨提交 id 集合比对**。
- 恢复动作的基底**永远取远端 contents API**，并逐项按 `updated` 取新，避免把别人 17:48 之后的正当改动回退。
