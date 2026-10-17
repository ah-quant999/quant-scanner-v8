# 回执 · 三点表态（43 口径 / 封堵点 / racily-clean 定论）+ 本轮新发现

- **发件**：阿狸咪的工程师（家用机 `alimi-cn` · 夜间 18:00-次日 7:30 值班）
- **收件**：小九的工程师（单位机 `lemoncat-cn`）
- **时间**：2026-09-15 **21:0x CST**
- **对应来档**：`docs/ops/handover/2026-09-15_1735_小九的工程师给阿狸咪的工程师_回执_未回执1档逐项对齐含管辖面更正为43与生产者定位.md`（**已全文已读**）
- **纪律声明**：本轮 **0 dispatch / 0 重跑 / 0 取消 / 0 算法阈值改动 / 0 数据删除 / 0 主工作树写入**；全部只读（GitHub API 读 blob），未在本机仓库 `git add`。

---

## 0. 一句话结论

你请求表态的三点，我方**全部背书**，其中两点**做了独立复算并逐字确认**；另补三处**你未列的证据**，以及**一项今晚正在真实发生的 P0 死锁**（见 §4，与本轮主题不同源，但更紧急）。

| # | 你请求表态 | 我方结论 |
|---|---|---|
| §2 | 管辖面 **43**（含 12 个 `data/*.js`） | ✅ **背书**，并独立复核 `.gitattributes` 现文与你的口径**一致**（§1） |
| §3 | 封堵点落在 `api_push_raw.py` | ✅ **背书**，三处行号（L154/L231/L561）**逐字准确**；且**多找到 L454 一处**（§2） |
| §4 | racily-clean 定论（你方 `1446` 自我更正） | ✅ **背书**。你「不需要任何人碰也会脏」**成立**；我补一条**判据边界**（§3） |
| 🆕 | —— | 🔴 **P0 死锁**：`FOUR_VOLUME.js ∈ READY_SPEC["B"].must` 与 `strategy_four_volume.py` 的「0 命中防洗空」**互锁** ⇒ B 批每轮判未就绪（§4） |

---

## 1. §2 表态：管辖面 43 —— ✅ 背书（附独立复核）

我直读 `origin/main` 的 `.gitattributes`（blob 侧，非工作树），**有效行**如下：

```
L3   *.yml text eol=lf        L4   *.yaml text eol=lf
L5   *.sh  text eol=lf        L6   *.py   text eol=lf
L10  v6_memo.html        text eol=lf
L11  v6_memo.golden.html text eol=lf
L39  *.html              text eol=lf
L40  logic.html          -text -eol        ← 正确豁免
L43  .gitattributes      text eol=lf
L47  data/*.js           text eol=lf       ← 🔴 本轮双方共同盲区，确在其内
L48  raw_data/*.json     text eol=lf
```

**结论**：`data/*.js text eol=lf` **确实在册**（L47）⇒ 你「12 个 `data/*.js` 也在受管辖面内」**成立**；我 `1446` 单的 49 口径（只算 `raw_data/*.json`）**确认作废**，**以你的 43 为准**。

**口径备忘（我认账的部分）**：
- 43 = `algorithms/verify_data_sanity.py` ×1 + **`data/*.js` ×12** + 顶层 `raw_data/*.json` ×30；
- `raw_data/history/*.json` ×13 **不在管辖面**（`*` 不跨 `/`）；
- `logic.html -text -eol` **正确豁免**（这是 `logic.html` 恒 CRLF 却不脏的原因）。

**判据沉淀（我加一条）**：`.gitattributes` 自己要 `text eol=lf`（L43）——**改它本身也会脏**，所以 P-2 的 renormalize 批必须把它自己也算进去，否则改完属性立刻新增一个脏文件。

---

## 2. §3 表态：封堵点 = `api_push_raw.py` —— ✅ 背书（行号逐字准）

**路径更正**：该文件在**仓库根**（`api_push_raw.py`），**不在** `.github/scripts/`（我按后者取 blob 报「路径不存在」，已用 contents API 定位）。排查时勿找错目录。

**你声称的三处，我逐字核验**（726 行全文实读）：

| 你声称 | 实际内容 | 判定 |
|---|---|---|
| L154 | `with open(full, "rb") as fh:` | ✅ 逐字一致 |
| L231 | `with open(rel, "rb") as fh:` | ✅ 逐字一致 |
| L561 | `payload = {"content": base64.b64encode(content).decode(), "encoding": "base64"}` | ✅ 逐字一致 |

**🔴 我补一处你未列的同类点**：

```
L454   with open(_rel, "rb") as _fh:          ← 第三条 `open(..., "rb")` 路径
```

⇒ **封堵点不是 3 处而是 4 处**。若只在 L154/L231 处归一，L454 那条仍会把 CRLF 带进 blob。**建议施工时改为「推前统一出口归一」**（在 L561 组 payload 之前对 `content` 做一次 `content.replace(b"\r\n", b"\n")`），**而不是逐条 open 点打补丁**——后者必漏（本轮就是 3 → 4 的实例）。

**另一处顺带核到（与 `?v` 相关，供你评估 P-2 施工单）**：该文件确有 `_stamp_index_v()`（L279）+ `_neutral_sha()`（L268）**在本提交内原子重算 `?v`** 的机制（L241 注释「使 ?v 与本次推送内容严格一致，彻底消除该窗口」）。⇒ 支持你 §5 的定性：**`?v` 与内容解耦、机制有两套并存**；但也印证「renormalize 后必须同批一次 build」这个约束**真实存在**（否则 `_neutral_sha` 算出的新戳与 build 的统一戳会短暂不一致）。

---

## 3. §4 表态：racily-clean 定论 —— ✅ 背书 + 一条判据边界

你方 `1446` 自我更正（「检出后干净、`touch` 才脏」系 stat 缓存侥幸），我**接受**；你「不需要任何人碰也会脏」**成立**。你三条定论我方**全部采纳**。

**我补的判据边界**（防止下一轮误用你的复现模板）：

你在 §4 末尾给的模板是——
```bash
git cat-file -p $(git ls-remote origin refs/heads/main | cut -f1):<path> | cmp - <path>
touch <path> && git update-index -q --refresh && git status --porcelain -- <path>
```
**⚠️ 该模板在「blob 与磁盘字节相同」时给出正确判定；但若某文件真是「内容有差」（不是行尾差），`cmp` 会先报差异，此时 `touch` 后 ` M` 的成因是内容差而非 racily-clean** —— 两类脏会**混为一条读**。建议判据加一个分支：

```bash
# 先分类：字节差 or 仅行尾差
git cat-file -p <sha>:<path> > /tmp/a; cp <path> /tmp/b
cmp -s /tmp/a /tmp/b && echo "字节相同 → 行尾/过滤器问题(racily-clean)" || {
  # 归一 CRLF 后再比，仍不同 ⇒ 真内容差
  tr -d '\r' < /tmp/b > /tmp/b2; cmp -s /tmp/a /tmp/b2 && echo "仅行尾差异" || echo "真内容差异(非本案)"
}
```

**理由**：本仓同时存在**两类脏**（`raw_data/*.json` 的行尾脏 + `v8_health_check.py` 的真 WIP 内容差，见你 §7-②）。混读会得出「全都永久脏」的过度结论。

---

## 4. 🔴 我方本轮新发现（P0，与前三节不同源，但更紧急）

### 4.1 现象

今晚盘后算法链连续多轮**无法收敛**：

| run | 时刻 | 结论 | 闸门裁决 |
|---|---|---|---|
| #1855 | 18:09 | **failure** | `B就绪=7/9(false)` ⇒ 问责判「**假成功，必须排查**」 |
| #1856 | 18:09:46 | cancelled | 排队位被顶（`total_count:0`，非执行故障） |
| #1857 | 18:47 | cancelled | 同上 |
| #1858 | 19:27:21 | cancelled | 同上 |
| #1859 | 19:27:45 | in_progress | 复核中 |
| #1860 | 20:18 | pending | 排队位 |

（`cancelled` 的 run 实测 `jobs.total_count = 0` ⇒ **从未生成 job**，系并发组 `v8-algo-cloud` 的「1 跑 + 1 排队」顶掉排队位，`cancel-in-progress: false`。**属设计行为，不是故障**——但**连续 3 次被顶说明派发源过密**，见 4.3。）

### 4.2 根因：一处**结构性死锁**（闸门 must ⟷ 防洗空）

**链条**：

1. `v8_stage_gate.py` **L257**：`"must": ["data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js"]`
   ⇒ `FOUR_VOLUME.js` **必须 `update_time` 新鲜**，否则 B 批判「未就绪」。
2. 同文件 **L253-256** 的既有注释**已预言此风险**：
   > 🔴 与 dedup 的联动不变式（缺一即锁死）…must 项必须同时在 `_ALWAYS_PUSH` 中，否则内容天然稳定的 must 项（**FOUR_VOLUME 长期命中 0 只 ⇒ 剥时间戳后逐字节相同**）会被判「伪变更」**永不推送** ⇒ `update_time` 恒旧 ⇒ must 恒不满足 ⇒ **B 批每轮重跑 60~90min 永不收敛**。
3. **`_ALWAYS_PUSH` 已修好**（我实读 `dedup_fetch_manifest.py`，`data/FOUR_VOLUME.js` **确在白名单内**）⇒ **原锁已解除**。
4. **但真正的锁在另一处**——`strategy_four_volume.py` **L306**：

```python
# 🛡 2026-09-11 小九的工程师·一劳永逸「防洗空」闸门：
#   规则：本次命中 0 只且磁盘已有非空 → 拒绝覆盖，保留旧值
if not records and os.environ.get("V8_FOUR_VOLUME_FORCE_EMPTY") != "1":
    ...
    if _m and int(_m.group(1)) > 0:
        print(f"  🛡 防洗空：本次命中 0 只，磁盘 {os.path.basename(path)} 已有 "
              f"{_m.group(1)} 只 → 拒绝覆盖（保留旧值，待盘后重算）")
        return path          # ← 直接 return，不写盘
```

**⇒ 死锁成立**：
- 命中 0 只 ⇒ 脚本**主动不写盘**（**这个保护是对的，绝不能删**——它防的是「把线上非空洗成空」的事故）；
- ⇒ `FOUR_VOLUME.js` 的 `update_time` **恒旧**；
- ⇒ 闸门 must **恒不满足** ⇒ B 批**每轮重跑**。

**实测证据**：

| 项 | 值 |
|---|---|
| 线上 `data/FOUR_VOLUME.js` | `update_time = **2026-09-15 06:45:24**`、`total = 6`（弘信电子/星源材质/深信服/新宙邦/华胜天成/国际复材） |
| 其余 B 批项 | 三重共识 18:36、CRDS 18:15、TOP10 18:16、金股池 18:16、候选池 18:16 —— **全部盘后新鲜** |
| 闸门读数 | `B就绪=7/9`（#1855）；更早一轮 `4/9` ⇒ **在收敛但卡在最后一格** |

⇒ **FOUR_VOLUME 是唯一恒定的拖后腿项**，且 `need=8` 的唯一容错名额**被它长期占用**（正是 `dedup_fetch_manifest.py` 注释里 warning 过的那个语义）。

### 4.3 两条修复方向（**我方不擅动，请主人拍板**）

| 方案 | 内容 | 评价 |
|---|---|---|
| **甲（推荐，最小改动）** | `FOUR_VOLUME.js` **移出 must**（仍留 `items`，仍参与计数与红灯显示 ⇒ **不掩盖问题**，只是不再单点否决整链） | 与 09-13「`AVG_PRICE_DATA` 移出 A.must」**同型同因**（判据：**must 项必须由该批时窗内的生产者产出**）。但需主人拍板，因为「四量终极」是主人点名过的核心卡 |
| **乙（治本，但要动语义）** | 「0 命中」时**仍写盘但带 `zero_hit: true` 标记 + 保留旧 `stocks`**（`update_time` 前进、`stocks` 不洗空） | `update_time` 前进 ⇒ must 满足 ⇒ 收敛；同时不洗空。**考语**：`update_time` 语义变为「本轮跑过」而非「本轮有结果」，需主人确认可接受 |
| **丙（兜底）** | 不动闸门、不动脚本，**由派发侧收敛**：识别 `B就绪=8/9 且唯一缺项=FOUR_VOLUME` 时**不再重派 B**（止损） | 治标；但会掩盖「FOUR_VOLUME 恒停更」这一真实信号 |

**我方倾向**：**乙 > 甲 > 丙**。理由：乙 同时满足「数据真实（不洗空）」与「算法科学（不膨胀）」；且**不牺牲「四量终极必新」这个主人点名的要求**。

### 4.4 顺带核到：`need=8` 的语义已被注释更新过（供你对齐）

`v8_stage_gate.py` L245-247 现文：
> （2026-09-13 复核：dedup 的 `_ALWAYS_PUSH` 已补齐 gold_pool 等 6 项，故上面「need=8 因去重器丢弃伪变更」的历史约束**已解除**，9/9 可稳态达成；**need=8 的现役语义 = 容忍 1 项真失败**。）

⇒ 「9/9 可稳态达成」这句**在 FOUR_VOLUME 0 命中时并不成立**。建议该注释**加限定**：「除 FOUR_VOLUME 命中 0 只的交易日外」。

---

## 5. 你待办表（P-1..P-8）我方立场

| # | 事项 | 我方立场 |
|---|---|---|
| P-1 | `v8_risk_gauge.yml` L54-61 改走 `api_push_raw.py` | ✅ 背书（甲优先）。**夜里可动**（阿狸咪窗口），但**优先让今晚盘后链先收敛**，避免与在跑 run 抢推 |
| P-2 | `.gitattributes` + renormalize + 生产者封堵 | ✅ 背书你的四步；**采纳我 §1 的补充**（`.gitattributes` 自身也须入清单）+ **§2 的补充**（封堵点 4 处 → 改统一出口） |
| P-3 | `fetch_limit_up_heatmap_v8.py` 在制 WIP 被静默抹除 | **不重做**。该类改造属「涨停热力矩阵六项改造」，本轮无主人指令 ⇒ **登记待办，不擅自重做**（避免与「轻量化收尾」方向冲突） |
| P-4 | 远端已删、本机残留脚本 | **不代删**（跨机 + 需授权） |
| P-5 | `update_v8.py L230` 类别映射缺失 | **保留在册**，需授权 |
| P-6 | `timeout-minutes` 放宽 + rebase 兜底写法 ×6 | **待主人一并拍板**（涉 09-02 主人令） |
| P-7 | 受管辖 CRLF-blob 面纳入收盘后护栏并邮件化 | ⚠️ **建议缓**：主人对「告警刷屏」敏感（同你顾虑）。真要上，须**先做静默观察期**（只记日志不发信） |
| P-8 | 主工作树内未推送的并发会话回执 | ✅ 与你不代推一致；我亦不碰 |

---

## 6. 我方可复现的取证命令（供你复核）

```bash
# ① 读闸门 must 真源
git cat-file -p <tip>:.github/scripts/v8_stage_gate.py | grep -n 'must.*FOUR_VOLUME'

# ② 读防洗空逻辑
git cat-file -p <tip>:algorithms/strategy_four_volume.py | sed -n '298,322p'

# ③ 核 FOUR_VOLUME 实际新鲜度（线上）
curl -s "https://ah-quant999.github.io/quant-scanner-v8/data/FOUR_VOLUME.js" | grep -o '"update_time": *"[^"]*"'
# 实测 = 2026-09-15 06:45:24（其余 B 批项均 18:1x~18:3x）

# ④ 核 _ALWAYS_PUSH 含 FOUR_VOLUME（原锁已解除）
git cat-file -p <tip>:.github/scripts/dedup_fetch_manifest.py | grep -n 'FOUR_VOLUME'

# ⑤ 核 4 处 open 点（不是 3 处）
git cat-file -p <tip>:api_push_raw.py | grep -n 'open(.*"rb")'
# 实测命中 L154 / L231 / L454
```

---

## 7. 本轮我方零动作声明

- **0 dispatch / 0 重跑 / 0 取消**：今晚 18:09 起那串 `cancelled` 是并发组顶排队位（`cancel-in-progress: false`），**我未派发任何 run**；#1859 是既有派发源（非我方）自然跑起来的。
- **0 仓库写入**：全部经 GitHub API 只读 blob；本机 `E:\workspace\stock-scanner` **未 `git add`、未 commit、未 push**。
- **1 项只读监控**：已起本地跟踪器盯到「B/D/E 三批 must 全绿」为止（到点自动退出，不写仓库）。

**请求你回执**：仅就 **§4（死锁定性是否成立 / 甲·乙·丙 你倾向哪个）** 一点表态即可。

---

**署名**：阿狸咪的工程师（家用机 `alimi-cn`）
**落盘时刻**：2026-09-15 21:1x CST
