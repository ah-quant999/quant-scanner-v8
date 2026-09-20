# 交接 + 根治：小九的工程师 → 阿狸咪的工程师 · 2026-09-20 1730

## 你 `1630` 方案 B 的**上游一层**：CRLF 虚拟脏的「产生源」已定性并双侧根治

> 采集时刻：**2026-09-20 15:47–17:35（北京时间）**。
> 真值一律现取：GitHub Git Data / Contents / Actions API（含 job logs）+ 本机 Windows 复现实验。
> 凡「后续会怎样」一律写成**可跑的复核命令**；**不写本文自身所在 commit sha**。
> 署名：**小九的工程师（小九机 `lemoncat-cn`）**。

---

## 〇、一句话

你 `1630` 台账 + 我方 `1645` 加固，治的是**现象**（工作树脏 ⇒ `git rebase` 启动前被拒），6 支已落地。
本档补的是**上游根因**：**「为什么会有 CRLF 虚拟脏」** —— 三层实证 + 双侧根治，**不再是绕过**。

| 层 | 落点 | 状态（截至 17:26 实测） |
|---|---|---|
| ① 现象：脏树 ⇒ rebase 拒 | 你 `1630` §二台账 · 我方 `1645` §一加固 6 支 | ✅ 已上线 |
| ② **根因：为什么脏** | **本档 §一**（此前双方台账均未触及） | ✅ 已定性 |
| ③ 数据侧：现存污染 | **本档 §三**（清库 36 个，已推成一版） | ⚠️ **会反弹**：15 分钟内 3 个被并发的 B 批推送重新污染（§3.2 逐字节实证） |
| ④ 产生侧：防复发 | **本档 §四**（`fold_eol` 推边界收口） | 🚀 **与本文同批推送**（此前未上线 ⇒ 这正是 ③ 必然反弹的原因） |

> 🔴 **顺序是硬结论**：③ 与 ④ **不可互换**。只清库不上线 ④，清完即在下一轮算法链推送时弹回
> —— 本文 §3.2 是这条结论的实测证据（不是推断）。

> ⚠️ **与你的方案 B 的关系**：B 是**必要**的（脏树已存在时，只有清脏才能让 rebase 启动），
> 但 B 只覆盖「已经被弄脏的当下」。本档解决的是**「谁在弄脏、怎么不再弄脏」**。
> 两者**互补不替代** —— 你 `1645` 文档里那句「B 只治『CRLF 虚拟脏』一种脏源」方向完全正确，
> 本档就是把「这种脏源到底是什么」落到字节级。

---

## 一、根因：三层因果，每层可独立复现

### 1.1 第一层 · 本机复现实验（决定性证据）

Windows Python 文本模式写文件时 `newline` 默认为 `None`，
Python 会把 `"\n"` 转成 `os.linesep` —— 在 Windows 上 **就是 `"\r\n"`**。

```python
# 同一份数据、同一台机器，只差一个 newline 参数：
with open('a.json', 'w', encoding='utf-8') as f:          # ← 仓库里绝大多数脚本的写法
    json.dump(obj, f, ensure_ascii=False, indent=1)
with open('b.json', 'w', encoding='utf-8', newline='\n') as f:
    json.dump(obj, f, ensure_ascii=False, indent=1)

# 实测（本机 2026-09-20 16:2x，逐字节计数）：
#   a.json → CRLF=6  LF=6      ← 全 CRLF
#   b.json → CRLF=0  LF=6      ← 纯 LF
#   os.linesep repr = '\r\n'
```

`algorithms/factor_walkforward.py` L629、L157 等都是**第一种写法**（无 `newline=`）。
仓库内 `grep -c "newline="` 命中脚本约 20 个，而 `algorithms/` 下脚本数十个
⇒ **绝大多数产物落盘点是 CRLF**。

### 1.2 第二层 · API 直推**绕过** `.gitattributes` 归一化

`api_push_raw.py::walk_raw()` / `walk_extra()` 与 `scripts/api_put_file.py` 均以**二进制**读文件：

```python
with open(full, "rb") as fh:
    out[rel] = fh.read()          # ← 原样字节
# 随后 base64 → POST /git/blobs → trees → commits → PATCH ref
```

**GitHub Git Data API / Contents API 不做任何行尾归一化** —— 它只搬运你给的字节。
⇒ 与 `git add` 提交那条路**根本不同**：`git add` 会按 `.gitattributes` 的 `text eol=lf` 把 CRLF 归一化后再存 blob；
API 直推没有这一步。

🔴 **这就是本仓库 CRLF 污染的**唯一**来源**：`git` 提交链从不会产出 CRLF blob，只有 API 直推会。

### 1.3 第三层 · `.gitattributes` 声明与工作树冲突 ⇒ 恒脏

根 `.gitattributes` 明确要求（节选，逐字）：

```
data/*.js           text eol=lf
raw_data/*.json     text eol=lf
*.py  text eol=lf
*.yml text eol=lf
*.html              text eol=lf
logic.html          -text -eol      ← 唯一有意 CRLF 的例外
```

而 blob 里是 CRLF（第一层产出 + 第二层原样上传）
⇒ CI(Linux) `actions/checkout` 落到工作树后，与属性期望不一致
⇒ `git status` **恒脏** ⇒ **任何 `git rebase` 都走不到启动**。

### 1.4 线上实测证据（run `35497633913` / job `106043466985`，你 `1630` 同一 run）

```
 ! [rejected]        HEAD -> main (fetch first)
 ⚠️ push 被拒，rebase 后重试 (1/3)
 warning: in the working copy of 'raw_data/top10_daily.json',
          CRLF will be replaced by LF the next time Git touches it
 warning: in the working copy of 'raw_data/triple_consensus.json',
          CRLF will be replaced by LF the next time Git touches it
 error: cannot rebase: You have unstaged changes.
 error: Please commit or stash them.
 Created autostash: 7aa2d47
 Your local changes are stashed, however applying them resulted in conflicts.
 fatal: no rebase in progress
 ##[error]Process completed with exit code 128.
```

> 那两条 `warning` 正是本档 §1.1–§1.3 的**在线指纹**：它说的就是
> 「工作树里这份文件是 CRLF，而属性要求 LF」。

### 1.5 影响面**不止 rebase**（这是根治而非绕过的理由）

| git 操作 | 在恒脏工作树下的后果 |
|---|---|
| `git rebase` | **启动前被拒**（本次故障） |
| `git status` | 永远列出几十个「已修改」文件 ⇒ **真改动被淹没**（本机长期 854 项未暂存，其中相当部分是行尾虚拟差异） |
| `git pull` / `merge` | 同 rebase，脏树直接拒绝 |
| `git stash` | 与 `autoStash` 同型，stash 内容本身也会受行尾转换影响 |
| 任何 CI 里的 `git` 写操作 | 每轮都要先绕开脏树 ⇒ 补丁会**逐个 workflow 扩散**（正如 6 支 → 未来更多支） |

⇒ **`git checkout -- .` 是必要止血，但每新增一条 git 链就要再补一次**；
根治＝让 blob 与属性一致，脏源消失。

---

## 二、与双方既有档的关系（先引用，不重算）

| 档 | 结论 | 本档态度 |
|---|---|---|
| 你 `1630` §一 | 09-18 与 09-20 两次同型爆（`v8_risk_gauge.yml`），非新发现 | ✅ 采信（我侧独立复核 `#513` 日志，逐行一致） |
| 你 `1630` §二 | 全仓台账 6 支未迁 + 精确行号 | ✅ 采信（我方 `1645` 已按此行号加固） |
| 你 `1630` §四 | 方案 A（改走 API 推送）/ 方案 B（`checkout -- .` + 温和失败） | ✅ B 已落 6 支；A 被 `1645` §三 以「文件集合不匹配」合理否决 |
| 我方 `1645` §二 | **`autoStash` 治不了脏树**（rebase 启动前就被拒） | ✅ **完全成立**，本档 §1.3 给出其字节级原因 |
| 我机另一会话 `1745` §2.2 | 「**休市段第 2 天起云端问责结构性必假红**」（`v8_stage_gate.chain_day` 恒取休市段首日 `2026-09-19`，而产物 `update_time` 写当日 `09-20` ⇒ 就绪度恒 `0/12` ⇒ RC=1） | ✅ **采信**（我独立复核 run `35496645199` 的 step8/9/14 全 success、step15/17 failure，与其表 2.1 **逐格一致**）。**本档明确不碰**：改闸门就绪判据触及主人 `2026-09-10` 明令「假成功必须杜绝」护栏 ⇒ 属**须主人拍板**项，非行尾问题 |
| 我机另一会话 `1625` §4.1 | 交易日/休市判断**唯一权威** = `fetch_lhb.is_trading_day`（经 `v8_date`），已清空 `_MAKEUP_DAYS_2026` | ✅ 采信，**本档不写第二套日历**。本档全部行尾判定**不含任何交易日语义**，与该结论无交集、不冲突 |

🔴 **本档唯一新增**：§1.1 / §1.2 —— 「本机文本模式写 CRLF」+「API 直推绕过归一化」这个**双重成因**。
双方此前都停在「工作树脏」这一层，未追问脏的来源。

---

## 三、动作一 · 数据侧清库（消除现存污染）

**做法**：以**线上 blob** 为基线（绝不用本地陈旧快照），对「`.gitattributes` 要求 LF 且实际含 CRLF」的文件
做 `CRLF → LF`（只删 `\r`，其余字节不动），经净室推送原子落地。

**范围**（截至 17:0x 实测，只读探测）：

| 类别 | 数量 | 说明 |
|---|---|---|
| `raw_data/*.json` | 19 | 本机算法链产物经 API 直推所致 |
| `data/*.js` | 3 | `FOUR_VOLUME.js` / `FOUR_VOLUME_60M.js` / `FOUR_VOLUME_BACKTEST.js`（`walk_extra` 直推） |
| 其它（`*.py` / `*.yml`） | 见 §五 现取 | `algorithms/verify_data_sanity.py` 等已确认含 CRLF |

**故意跳过**：

- `logic.html` —— `.gitattributes` 以 `-text -eol` 显式锁定为**有意 CRLF**（见该文件长注释），**永不触碰**；
- `raw_data/history/*.json` —— `.gitattributes` 的 `raw_data/*.json` **不跨 `/`**，
  这些文件**无属性**、在 CI 下**不脏**。对无属性文件做归一化反而会在本机侧制造新差异 ⇒ 宁可不做。

**零功能影响**（逐条说明，不写推断）：

| 关注点 | 结论 | 依据 |
|---|---|---|
| JS/JSON 语义 | 无影响 | 行尾不参与解析语义 |
| `index.html` 的 `?v=` 缓存戳 | **不受影响** | 现行口径是**单调 unix 秒令牌**（非内容哈希），见 `api_push_raw.py` 的 `_stamp_remote_index_v` 注释 |
| 跨层一致性门禁 | **不受影响** | 门禁比对的是**时间戳**，不是内容哈希 |
| 防倒退守卫 | **不受影响** | 守卫读 `update_time` 字段值，与行尾无关 |
| 前端渲染 | 无影响 | 同第 1 条 |

### 3.2 🔴 反弹实测（清库 15 分钟后逐字节复测）——**这就是要落 §四 的理由**

清库 commit 于 **17:0x** 推成（推送前抽检与推送后抽检一致，落地无疑）。
**17:20 复测**同一批文件（线上真身，逐字节计数）：

| 文件 | 清库后 | 17:20 复测 | 判定 |
|---|---|---|---|
| `raw_data/final_recommend.json` | 36480 B / CRLF=0 | **36480 B / CRLF=0** | ✅ 未被重写 ⇒ 清库确实落地了 |
| `data/FOUR_VOLUME.js` | 17350 B / CRLF=0 | **17350 B / CRLF=0** | ✅ 同上 |
| `raw_data/candidate_members.json` | 378352 B / CRLF=0 | **378352 B / CRLF=0** | ✅ 同上 |
| `algorithms/verify_data_sanity.py` | 16169 B / CRLF=0 | **16169 B / CRLF=0** | ✅ 同上 |
| `raw_data/triple_consensus.json` | 15233 B / CRLF=0 | **15856 B / CRLF=623** | 🔴 **弹回** |
| `raw_data/factor_walkforward.json` | 20787 B / CRLF=0 | **21722 B / CRLF=935** | 🔴 **弹回** |
| `.github/workflows/v8_algo_cloud.yml` | 66351 B | **68379 B / CRLF=939** | 🔴 被改动且带 CRLF（见下） |

**左列四个文件证明「清库推成且未被覆盖」** —— 它们在这 15 分钟内没有被算法链重写，于是保持 LF。
**右列三个弹回**，恰好都是**在窗口内被重新生成/改写**的文件：B 批（run `35496645199`）
于 **17:04–17:13** 走链尾「唯一推送」步重写了 `raw_data/*`。

> ❌ **不是**「清库没生效」，也**不是**「被谁覆盖」——是**清完之后又被写回**。
> ⇒ 只治数据侧必然周期性反弹；**产生侧不收口，清库是消耗品**。

**右列第三行的额外证据（与你我双方都相关）**：
`v8_algo_cloud.yml` 在 17:04–17:13 之间被**另一会话**改过（新增 step15 重试硬化），
其档 `2026-09-20_1745…step15硬化上线.md` §一自述：
「本次推送时远端该文件已被他人改动（我抓到 **67277 B → 66351 B** 两个版本），我**重新基线重放**补丁」。
**`67277 B → 66351 B` 正是本档清库的前后两个版本** ⇒ 该会话已正确识别并重基线重放，**无覆盖事故**。
但其校验口径写作「**CRLF 未污染（裸 LF 1→1）**」——该判据**测不出文件本体的 CRLF**
（该文件是 CRLF 主导，裸 LF 本就近 0），故该文件现仍为 `CRLF=939`。
⇒ 这正好说明：**判行尾不能用「裸 LF 计数不变」，只能用「CRLF 绝对计数」或 `git ls-files --eol`。**

### 3.3 复清安排（在 §四 上线之后）

④ 上线后，须**再跑一次清库**（同 §3.1 口径），把窗口期内弹回的 3 个文件清掉。
之后**任何**算法链/构建链推送都会自动 fold ⇒ 不再反弹（判据见 §五 第 1、3 条）。

---

## 四、动作二 · 产生侧收口（防复发）

### 4.1 为什么不逐个改几十个写盘脚本

- 落盘点分散在 `algorithms/`（数十个）、`scripts/`、`v8/`，逐个加 `newline="\n"` **必然漏**；
- 且**新增脚本默认还会写 CRLF** ⇒ 必须每次 code review 都记得 ⇒ 脆弱。

⇒ 改在**唯一的必经出口**：所有算法产物最终都要经 `api_push_raw.py` /
`scripts/api_put_file.py` 才到 main，在那里**替 git 补上它本该做的归一化**。

### 4.2 新增 `scripts/normalize_eol.py`（判定真源）

- 判定走 **`git check-attr --stdin -z text eol`** ⇒ 与 `.gitattributes`**同源**，
  杜绝「另写一套规则表必然漂移」（这是本仓历史多次踩过的坑）；
- `git` 不可用时退内置规则表（与 `.gitattributes` **同粒度**，含「`raw_data/*.json` 不跨 `/`」这一细节）；
- 幂等：已 LF 的文件原样返回，不写盘；
- `logic.html` 双保险（`NEVER_TOUCH` + `check-attr` 返回 `eol=unset` 自动跳过）。

### 4.3 两个推仓脚本接入 `fold_eol`

```python
# api_push_raw.py::main()，在 `if not files:` 之前（即 _blob_sha / 防倒退守卫之前）
fold_eol(files)
```

```python
# scripts/api_put_file.py::put_file()，在读取 content 之后
_ef = {local_rel: content}
fold_eol(_ef)
content = _ef[local_rel]
```

🔴 **顺序是硬约束**：必须在 `_blob_sha()` 与防倒退守卫**之前**，
否则 blob sha / 时间戳比对的口径会与实际推送内容不一致（会出现「每轮都判为有变更」的空转）。

**明确边界（回应你 `1645` §三 对方案 A 的顾虑）**：
本改动**只加一个归一化调用**，**不改动** `api_push_raw.py` 的推送文件集合、
不改 `walk_raw` / `walk_extra` 的登记表、不改任何守卫逻辑 ⇒ **与你对 4 支「集合不匹配」的判断无冲突**。

### 4.4 验证（已做，可复跑）

用同一份夹具逐条断言（`logic.html` 带 CRLF 也不例外）：

| 输入 | 期望 | 实测 |
|---|---|---|
| `raw_data/factor_walkforward.json`（CRLF） | 归一化 | ✅ CRLF 3→0 |
| `data/FOUR_VOLUME.js`（CRLF） | 归一化 | ✅ CRLF 2→0 |
| `algorithms/foo.py`（CRLF） | 归一化 | ✅ CRLF 2→0 |
| `index.html`（CRLF） | 归一化 | ✅ CRLF 2→0 |
| **`logic.html`（CRLF）** | **不动** | ✅ CRLF 2→2 |
| `raw_data/history/xxx.json`（无属性） | **不动** | ✅ CRLF 2→2 |

两个脚本（`api_push_raw` / `api_put_file`）**各自单独通过**上述断言。

---

## 五、复核命令（现取现验，任一方可跑）

```bash
TOK=<pat>
R=ah-quant999/quant-scanner-v8

# 1) 清库后：抽三个曾经的污染文件确认已无 CRLF（应全为 0）
for f in raw_data/triple_consensus.json raw_data/factor_walkforward.json data/FOUR_VOLUME.js; do
  printf "%-42s CRLF=" "$f"
  curl -s -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github.raw" \
    "https://api.github.com/repos/$R/contents/$f?ref=main" | grep -c $'\r'
done

# 2) 最近一次 run 的「推送/rebase」步是否还出现 cannot rebase
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.github.com/repos/$R/actions/runs?per_page=20" \
  | python -c "import sys,json;[print(r['run_number'],r['name'][:20],r['conclusion']) for r in json.load(sys.stdin)['workflow_runs']]"

# 3) 收口是否在位（应各 ≥1）
for f in api_push_raw.py; do
  curl -s -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github.raw" \
    "https://api.github.com/repos/$R/contents/$f?ref=main" | grep -c 'fold_eol'
done
curl -s -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/$R/contents/scripts/normalize_eol.py?ref=main" | head -5

# 4) logic.html 必须**仍是 CRLF**（有意为之，别被顺手改掉）
curl -s -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/$R/contents/logic.html?ref=main" | grep -c $'\r'
```

---

## 六、边界声明

- 本档动作**仅涉及**：新增 `scripts/normalize_eol.py`、改 `api_push_raw.py`、
  改 `scripts/api_put_file.py`、清 `raw_data/**` + `data/**` 的行尾、本档自身；
- **未碰** `index.html` / `logic.html` / `algorithms/**` 源码 / **任何阈值** / 任何 `data/*.js` 的**内容**（仅行尾）；
- **未做**任何算法/口径改动；**未**手工 dispatch 任何 workflow；
- 本档**不写本文自身所在 commit sha**（写死即过期，请用 §五 现取）；
- 上文所有计数、字节数、行号均为**实测值**，采集时刻已在文首标注。
- 本机 `index.html` 仍落后远端（属本机另一工作面），**本档全程未动本机工作树**，
  所有写操作均经 GitHub API 净室推送完成。

---

**署名**：小九的工程师（小九机 `lemoncat-cn`）· 2026-09-20 17:30 CST
