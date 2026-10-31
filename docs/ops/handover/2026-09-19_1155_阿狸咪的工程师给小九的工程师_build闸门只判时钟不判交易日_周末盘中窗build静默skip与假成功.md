# 📮 交接：阿狸咪的工程师 → 小九的工程师

- **时间**：2026-09-19 11:55（北京时间，周六）
- **主题**：🔴 **`build_deploy` 的 gate 闸门只判「时钟窗」、不判「是否交易日」⇒ 周末/节假日的盘中窗内 `build` job 被静默 skip，而 run 顶层结论仍是 `success`（假成功）；手动 `workflow_dispatch` 同样被 skip**
- **发起机**：家机 `alimi-cn` ｜ 目标机：单位机 `lemoncat-cn`
- **我方核对基线**：`origin/main` tip = `14be666517`（11:53:16，`v8 cn fetch`）— `git ls-remote` 现取
- **本机权限实测（本轮新做，非引用）**：`git/trees` 悬空探针 → **HTTP 403**「Resource not accessible by personal access token」⇒ 我方 PAT **无** `.github/workflows/**` 写权 ⇒ 本修法我落不了，交付你或主人拍板。

---

## 零、一句话

今天（**周六**）我复核 `build_deploy` 健康时发现：全天 28 个 run 里，**唯一被判 `trading=true` 的 `#7073`（10:34:05）正是唯一 `build=skipped` 的那个**，其余 27 个（09:25 前 / 09:25 后非窗内）`build` 全部真跑 success。
追到源码：**gate 的判据（`v8_build_deploy.yml` L100–103）只有 `HH:MM` 时钟窗，完全没有星期/交易日判定**。
⇒ 结论：**周六、周日、法定节假日的 09:25–11:30 与 13:00–14:59（CST），`build` job 结构性不跑**；而 `run` 顶层 `conclusion` 仍为 `success` ⇒ **看 run 结论会得出「已部署」的错误结论**。

---

## 一、铁证（可复现，全部远端只读）

### 1.1 gate 判据逐字（远端 `main` 现取）

```bash
# .github/workflows/v8_build_deploy.yml
L99           run: |
L100            TH=$(TZ=Asia/Shanghai date +%-H); TM=$(TZ=Asia/Shanghai date +%-M)
L101            TR=0
L102            if { [ "$TH" -eq 9 ] && [ "$TM" -ge 25 ]; } || [ "$TH" -eq 10 ] || { [ "$TH" -eq 11 ] && [ "$TM" -le 30 ]; } || [ "$TH" -eq 13 ] || [ "$TH" -eq 14 ]; then TR=1; fi
L103            echo "trading=$([ "$TR" -eq 1 ] && echo true || echo false)" >> "$GITHUB_OUTPUT"
```

**判据取值面**：`09:25–09:59` ∪ `10:00–10:59` ∪ `11:00–11:30` ∪ `13:00–13:59` ∪ `14:00–14:59`。
**缺席的维度**：`date +%u`（星期）、交易日历、`data/*` 里已有的交易日信息 —— **一个都没有**。

### 1.2 两个 job 的互斥条件

```bash
L131  if: needs.gate.outputs.trading != 'true' && (github.event_name == 'workflow_run' || github.event_name == 'workflow_dispatch' || github.event_name == 'push')   # build
L474  if: needs.gate.outputs.trading == 'true'                                                                                                                   # intraday_patrol
```

⇒ 盘中窗内：`build` 不跑、`intraday_patrol` 跑。**注意 L131 白名单里含 `workflow_dispatch`** ⇒ **手动触发也救不回来**。

### 1.3 今日（09-19 周六）全天 28 个 run 的实测矩阵

| run# | created(CST) | event | run 结论 | **build** | **intraday_patrol** | 按 L102 复算 trading |
|---|---|---|---|---|---|---|
| #7071 | 09:03:04 | workflow_run | success | **success** | skipped | false |
| #7072 | 09:23:20 | workflow_run | success | **success** | skipped | false（09:23 < 09:25） |
| **#7073** | **10:34:05** | workflow_run | **success** | **skipped** | **success** | **true（10 点整窗）** |
| （其余 25 个：00:02–08:37 区间） | — | push/workflow_run | success | success | skipped | false |

**一致性检验**：把 L102 判据逐 run 复算，与 `build` job 的真实结论比对 ⇒ **不一致数 = 0**（28/28 命中）。
⇒ 排除「偶发」「并发取消」「超时」等干扰解释：**这是判据本身的确定性行为**。

### 1.4 `intraday_patrol` 在今天的实际执行（`#7073`，job id `105824794712`）

```
Set up job                                    success
Run actions/checkout@v4                       success
🩺 状态机自检（不触网，8 例判定矩阵）              success
🔍 三条盘中链首跑探活（run 数 + 产物新鲜度 双判据）      success
Post Run actions/checkout@v4                  success
Complete job                                  success
```

（其内部 `guard_intraday_firstrun.py --dispatch` 的输出我拿不到：本机 PAT 无 `actions:read`，`/actions/jobs/<id>/logs` 返回 **401**。故本节只报步骤级结论，**不推断它补派了谁**。）

---

## 二、影响面（按「工作日 / 非交易日」分开说，避免扩大化）

| 场景 | gate 判定 | 实际后果 | 是否有害 |
|---|---|---|---|
| **工作日** 盘中窗（09:25–11:30 / 13:00–14:59） | `trading=true` | `build` 不跑、`intraday_patrol` 跑 | ✅ **设计如此，无害**（盘中数据由 `cn_fetch` 直推 `data/*.js` 上线，正是 2026-09-03 那条根治的意图） |
| **工作日** 非盘中窗 | `trading=false` | `build` 真跑 | ✅ 正常 |
| 🔴 **周六 / 周日 / 法定节假日** 同两个窗 | 仍被判 `trading=true` | **`build` 结构性不跑**；`intraday_patrol` 反而在非交易日执行「盘中链探活」（必要时**补派盘中链**） | ❌ **有害**：① 该窗内的 push（含 `index.html` 结构改动）**拿不到 `update_v8` 全量重建与部署**；② `run` 绿 ⇒ **假成功**，看板与人都以为部署过；③ 非交易日跑盘中探活/补派，是**周末幻影数据**的候选来源之一 |
| 🔴 **非交易日 + 手动 `workflow_dispatch`** | 同被判 `trading=true` | **手动也 skip** | ❌ **有害**：主人「周末手动跑更新和部署」的诉求，恰好在 09:25–11:30 / 13:00–14:59 这两段**完全落空**（run 仍绿） |

### 2.1 与「周末幻影快照」的关联 —— **列为候选，不作断言**

你 `1010` 档指出 `SECTOR_PHASE_HISTORY.js` 存在周末档（`08-30` / `09-12` / `09-19`）。我注意到这三档**全部是周六**，与本节「周六盘中窗 `intraday_patrol` 会跑并可能补派盘中链」在机理上同型。
但我**没有拿到 `intraday_patrol` 的补派日志**（401），且 `09-19` 档现已被清污，**无法事后归因** ⇒ 本节**只登记为候选来源**，待你侧或后续 run 复现时取证。**不要当作已证实结论使用。**

### 2.2 顺带实测（供你更新台账，非本档主结论）

- `data/SECTOR_PHASE_HISTORY.js`：`update_time = 2026-09-19 10:23`、`republish_time = 2026-09-19 10:31:28`、`snap_count = **25**`（你 `1010` 档记 28）、**最新档 `date = "2026-09-18"`**（真 K 线日）⇒ **你 0820 档 D-3 的「快照清污」在今日 10:23 那轮已生效，周末幻影已从该文件消失**。
- `data/SECTOR_RS.js`：`update_time = 2026-09-18 15:00:00`（你 `1010` 档记 `2026-09-19 00:41` / `data_date=2026-09-19`）⇒ **亦已归正为真 K 线日口径**。
- 两条都建议你在台账上标「已闭环」，避免下一轮重复排查。

---

## 三、修法建议（**我不落，供拍板**）

### 3.1 最小改动（一条 `if` 前缀）

```bash
# L100 之后插入，让周六/周日恒判非盘中
DOW=$(TZ=Asia/Shanghai date +%u)          # 1..7（1=周一）
if [ "$DOW" -ge 6 ]; then TR=0; else <原 L102 判据>; fi
```

- 优点：**一行级**改动、零新依赖、周末立即恢复 `build` 通道；同时让 `intraday_patrol` 在周末不再执行（消除非交易日探活/补派面）。
- 局限：**法定节假日（周二但休市）仍会误判** —— 与现状同型，只是把「周末」这一最大面先关掉。
- 若要做全：接交易日历。仓库里已有交易日判定能力（`v8_stage_gate.py` 侧），但**我没有逐字确认它的接口是否可被 yml 轻量复用**，故此处不写具体调用，**请以你侧核实后的形态为准**。⚠️ 别让我这份建议里的任何函数名/路径被当成已验证事实。

### 3.2 硬约束（双机铁律，请一并遵守）

1. **不得改 `run` 顶层结论的语义**；本修法是让 `build` 在非交易日恢复执行，**不是**让 `run` 变红。
2. 修完请按 **`build job`** 验证（**禁看 `run` 结论**）—— 本次教训正是「run 绿 ≠ 部署过」。
3. 别引入 `schedule` 依赖（本仓 `schedule` 已有时段性延迟前科）。

---

## 四、我方本轮边界声明

- 本机 **0 次 `git commit`**、**1 次 Contents API PUT（即本档自身）**、**0 次 dispatch**（listener 判定无派发指令）。
- **未碰** `index.html` / `logic.html` / `data/*`（内容）/ `raw_data/*` / `.github/workflows/**` / 任何阈值。
- 无 workflow 写权（**本轮悬空 tree 探针实测 403**）⇒ 本档只作交付与建议，落地权在你或主人。
- 诊断脚本（**仓库外**）：`E:\workspace\_alimi_check_20260919\`（`check_1148.py` / `check_gate_1148.py` / `dump_gate.py` / `check_sat_gate.py` / `check_patrol.py` / `check_phantom.py` / `check_fv_idx.py` / `probe_wf_perm.py`）。

---

*阿狸咪的工程师 · 2026-09-19 11:55 CST*
