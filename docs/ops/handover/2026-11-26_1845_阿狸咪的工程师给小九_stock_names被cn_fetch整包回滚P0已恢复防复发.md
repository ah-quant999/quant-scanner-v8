# HANDOVER｜阿狸咪的工程师 → 小九｜2026-11-26 18:45｜stock_names被cn_fetch整包回滚P0已恢复防复发

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

cn_fetch 17:03 提交 `f32c8c34279e`（300 文件整包推送家族）把 `raw_data/stock_names.json` 从 **9654 条（ut=2026-11-26 01:42:26）** 回滚成 **7373 条（ut=2026-11-11 02:04:45）**，P0 指标（entries≥9000）跌破；阿狸咪已于 18:46 按六步范式从远端 parent blob 逐字节恢复（提交 `c627c800`，回读自证 byte-exact 通过），**根因在 runner 本地旧缓存，请小九清理，否则下轮 cn_fetch 会再次覆盖**。

---

## 正文

### 1. 事故证据（全部取自远端 API 实测，非本机副本）

| 时刻 (CST) | commit | stock_names.json 状态 |
|---|---|---|
| 11-26 01:42 起（良好） | `15468c7ef08b`（algo 链落盘） | blob `79e670ebf674` / 2,081,141B / **9654 条** / ut=11-26 01:42:26 |
| 11-26 17:03（事故） | `f32c8c34279e`「v8 cn fetch: 2026-11-26 17:03」 | blob `a7e3932be769` / 1,416,862B / **7373 条** / ut=**2026-11-11 02:04:45** |
| 11-26 18:46（恢复） | `c627c8009723`（阿狸咪 Contents API PUT） | blob `79e670ebf674` / 逐字节回读一致 / 9654 条 ✅ |

- 该 commit 共改 300 文件，符合「本地 tree 全量推送」家族指纹（`git show --name-status` 成片 A/改写，见 AGENTS §35.1/§41 铁律）。
- 回滚载荷的 ut=2026-11-11 02:04:45 ⇒ **runner 本地 raw_data/stock_names.json 是 11-11 的旧缓存**，抓取当轮大概率未刷新该文件（或上游失败降级取旧本地文件），随后被整包带上了远端。
- 16:35 巡检轮实测仍为 9654 条 ⇒ 覆盖精确发生在 16:45–18:39 之间的 17:03 cn_fetch 提交。

### 2. 已完成的自愈（阿狸咪侧，六步范式全记录）

1. 内容源 = 远端 `git/blobs/79e670ebf674`（parent 提交 `f32c8c34279e^`）原样 base64，**未读本机 clone 任何文件**。
2. 漂移断言：推前实测 main 当前 blob sha=`a7e3932be769…` 且 entries<9000，不满足即 sys.exit（本轮实测通过后才 PUT）。
3. PUT 单文件 Contents API（branch=main），提交信息注明恢复来源 blob。
4. 推后逐字节回读：`chk_b64 == good_b64` **True**，entries=9654，ut=2026-11-26 01:42:26，blob sha 回到 `79e670ebf674`。
5. Token scopes 实测 `repo`（有写权），未打印/未落盘。

### 3. 请小九处置（根因，防复发）

1. **清理自托管 runner 本地 `raw_data/stock_names.json`**（其 ut=11-11，已落后 15 天）或修复 stock_names 抓取步骤：抓取失败时**禁用本地旧缓存顶包**，宁缺毋滥（主人铁律①）。
2. 核对 cn_fetch 推送逻辑是否做了**删除感知并集/增量对齐**（铁律：推 `raw_data/` 前必做；「禁本地 tree 全量推送」）。本次 300 文件整包是家族性风险，同一批可能还覆盖过其他产物（本轮抽查 experiment/sector_leaders/algo report/sector_phase_history 均鲜活未受累，但未逐文件全查）。
3. 若下轮 cn_fetch 再次回滚该文件，请直接按 §2 方法恢复，并在 HANDOFF.yaml 更新本件状态（阿狸咪将同步登记）。

### 4. 当前残留观察项（非阻断）

- `sector_leaders.json` data_date 仍=11-25，republish_time=17:16:56 已刷（盘后链待进 11-26，<24h 继续观察）。
- `algo_run_report.json` ut=07:14:59（ok=49/fail=3 既有软故障家族），algo 链 16:42 起有 run in_progress，待其落盘。
- build_deploy 18:15 STEP14 failure 属在册 crosslayer-deploy-block-1125，独立 Deploy v8 Site 链 18:16 success 保障主站，主站 200/1,578,442B/尾部完整。
- HANDOFF.yaml 本轮受「单轮 PUT ≤2 次」铁律约束未同步（本轮已用 2 PUT：恢复+本件），**阿狸咪下轮巡检将补登**（拉远端重放+ledger hash 重算）。
