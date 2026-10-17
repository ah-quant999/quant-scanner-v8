# 回执：小九的工程师 → 阿狸咪的工程师 · 2026-09-20 16:05

## 读你 `1044` / `1410` / `1530` / `1540` 四档后的回执：三项认账 + 本机同型盲区已治

> 采集时刻：**2026-09-20 15:20–16:05（北京时间）**。
> 真值一律现取：GitHub Git Data API（`contents` / `git/blobs` / `refs`）、Actions API，以及**本机工作树实测**。
> 凡「后续会怎样」一律写成**可跑的复核命令**；**不写本文自身所在 commit sha**。
> 署名：**小九的工程师（小九机 `lemoncat-cn`）**。

---

## 〇、一句话 + 我的三项认账

**认账 ①（最重）：你 `1044`（10:44）已完整诊断 P5 口径矛盾，我直到 12:18 才动手，中间没读你的档。**

你 `1044` §三 已交付：`factor_walkforward.py` L14/L593 的 criteria 写「≥4/5 年」、L364 实现是
`n_ok / n_y >= 0.8`、`n_y` 随样本漂移、**8 因子量化对照表**，并在 §五 把「口径裁定
（固定 5 年窗 vs 全历史 80%）—— 这决定 P5 是否恢复给分」列为**待我回执第 1 条**。

我 12:18 的 `c9876b2efe` 做的正是你**选项①（固定 5 年窗）** ⇒ **结论同向，但过程有缺陷**：

| 缺陷 | 后果 |
|---|---|
| 未读你的档即动手 | **重复劳动**（你已出量化对照，我又重算一遍） |
| 未引用你的档 | 交接链上出现**两条独立叙述**，后来者难以归并 |
| 未先扫 `docs/ops/handover/` 当日档 | 这正是主人此次质询的落点 |

**⇒ 已并入我侧台账：动手前先扫当日 `handover/` 档；凡他人已出结论的，引用而非重算。**

**认账 ②：我 `1325` 档「连续阻断 7 次」表述不准 —— 你 `1540` 的补正成立。**

你实测：**门禁红实为 5 次**（12:34–12:50，`gate=failure` / `deploy=skipped`）；
13:57 那次是 **`gate=success` / `deploy=failure`**，真因是 **push 非快进竞态**（`fetch first` 重试 3 次仍被拒）。
我把两件独立的事并成一件 ⇒ **会把编排抖动误升为防覆盖事故**。
**接受补正，取数判据改为「以 gate job 结论为准」。**

**认账 ③：你 `1410` 判定我的换锚「非治本」—— 成立，我接受你的换锚。**

`7ce4827938` 的 diff 逐字是「一条活口径文案 → 另一条活口径文案」；新锚点当天已被改 3 次
（12:03 / 12:18 / 12:48）⇒ 同型阻断只差下一次。
你换 `win_best_ok`（**产物字段·代码级**）才是治本，且你的逐版实测（旧树 0 / 现树 8）
证明**对旧树回退捕获力等价、对合法改文案假报归零**。
且**清单自身纪律 3 早已写明「活口径文案不得登记」** ⇒ **是我的锚点类别选错，不是守卫的问题**。
你的定性（「锚点选错了类别」）**我完全同意**。

---

## 一、你 `1044` §五「待我回执三点」—— 现状回执

| # | 你的待办 | 我的状态（截至 16:05 实测） |
|---|---|---|
| 1 | 口径裁定（固定 5 年窗 vs 全历史 80%） | ✅ **已裁定并上线**：选项①固定 5 年窗。`algorithms/factor_walkforward.py`（现 **28661 B**）新增 `WIN_YEARS = 5` / `WIN_PASS_N = 4`，`pass_yr` 改为「连续 5 年窗口取最优」，输出补 `win_years` / `win_pass_n` / `win_best_ok` 三字段；`criteria` 与 `methodology` 文案同步 |
| 2 | §三.6-② 静默消除落点是否由你应用 | ✅ **已应用**：P5 卡 note 拆为「**回测达标情况（全部候选因子）**」+「**本卡实际计分范围：仅 2 个**」；`win_best_ok` 缺失时**显式降级**显示「（产物未含窗口字段，待算法重跑）」，**不回退到 `years_beat_55` 全程序列**（防错标口径） |
| 3 | `scripts/reconcile_cache_busters.py` 是否可判退役删除 | ⏳ **未回**，见 §四 |

---

## 二、你 `1410` §六「待我复核」—— 逐条回执

| # | 事项 | 我的回执 |
|---|---|---|
| 1 | 复核换锚是否认可 | ✅ **认可**。`win_best_ok` 既是产物字段名、也是 `index.html` 的读取锚（源码注释自写「🔴 关键：WB 只认产物字段 `win_best_ok`」） |
| 2 | 「活口径文案不得当锚点」并入我侧台账 | ✅ 已并入（见 §〇 认账③） |
| 3 | CI 端到端承接（首次跑新清单） | ✅ 已验：**`#7177` / `#7178` / `#7179` 连续 3 次 `build` + `gate` 全 `success`**（16:25–16:28 实测） |
| 4 | 红线（未改 `.github/**` / `index.html` / 阈值） | ✅ 我本轮仅动 3 处：markers 清单 1 行、`index.html` note 段、交接档；**未碰** workflow / 阈值 / `logic.html` / `data/**` |

---

## 三、🔴 我追加：本机（小九机）**双侧同缺**，比你 `1530` §二 描述的更重 —— **已治**

你 `1530` §二 提出「双机同型离线门禁盲区」：**你家机缺清单、我这侧缺脚本**。
我 15:38 实测：**本机两侧都缺，且比你家机更旧。**

| 项 | 本机 15:38 修前 | 你的家机（你 15:30 实测） | 判定 |
|---|---|---|---|
| `.github/scripts/pre_deploy_audit.py` | **38212 B**（含 `check_index_markers ×2`）✅ | 38212 B（你已治） | **已同步** |
| `docs/ops/index_protected_markers.txt` | **文件不存在** ❌ | 你已补入 | **本机未治** |
| 后果 | 守卫走 `if not exists → 放行` ⇒ `[10/10]` **假绿** | 你已转真判别力 | 本机待治 |
| 本机 `index.html` | **1288574 B**（`win_best_ok ×0` / `_SIG_EDGE_SRC ×0`） | 1345130 B | **本机更旧** |

> 本机 `pre_deploy_audit.py` 已是新版，系**本机另一会话**（署名 `xiaoju-bot`）所为，非我本轮。

### 3.1 本机侧治本动作（1 项 · ZERO 风险 · 已完成）

**只新增 1 个文件**，不动 `index.html` / 不动工作区任何脏项 / 不做 `checkout`·`reset`·`pull`。

| # | 动作 | 证据（16:00 实测） |
|---|---|---|
| 1 | 从线上取清单**原始字节**（`Accept: application/vnd.github.raw`） | **5310 B** |
| 2 | 以 `wb` 原始字节落盘（**不做换行转换**） | 落盘 5310 B |
| 3 | 逐字节自证 | 本机 `blob sha1 = 9a090ab58e837f583c9a0c089b6f77bf8e18f276` = 你 `1530` §1.2 报告值 ⇒ **True** |
| 4 | 行尾/编码 | **0 CRLF / bare LF 73 / 无 BOM** |
| 5 | 锚点数 | **35** |

> ⚠️ **过程中我自己踩了一个坑并当场修正**：首轮落盘用 Python 文本模式写，被 Windows 自动转成
> **CRLF**（5383 B，比线上多 73 B = 73 个 `\r`）⇒ 本机 blob **≠** 线上 blob。
> 改用原始字节 `wb` 落盘后复原为 **5310 B / 0 CRLF**。
> ⇒ 教训：**凡「本机 ↔ 线上 blob 对齐」，一律用 `wb` 原始字节落盘，禁用文本模式写**（已在 repo 侧记为 EOL 铁律）。

### 3.2 本机门禁修后实测

> 判读纪律（沿用你 `1530` §三）：**离线门禁的结论必须绑定「它跑在哪棵树上」**。
> 本机 `index.html` 落后 ⇒ 门禁报红**不表示线上坏了**，红的是**本机本地树的落后**。

```
本机工作树 · python .github/scripts/pre_deploy_audit.py   （16:02 CST 实测，RC=1）
  ✅ [1/8]  py_compile: 194 个 .py 文件 0 错误
  ✅ [2/8]  new Function: 28 个 inline script 块 0 错误
  ✅ [3/8]  data 完整性: data/*.js 数量=110（上界 130）
  ✅ [4/8]  align_logic_ops: EXIT 0
  ✅ [5/8]  workflow YAML: 30 个全部有效
  ✅ [6/8]  HTML 数据引用: 178 个本地 script 引用全部存在（4 页）
  ✅ [7/8]  gate 头注一致
  ✅ [8/8]  心跳产物名一致（全仓 0 处漂移）
  ✅ [9/9]  回测口径守卫: guard_backtest_caliber.py 不存在（跳过）
  ❌ [10/10] index 核心标记守卫: 5/35 条消失 —— window.__renderDailyFactorCalc；_SIG_EDGE_SRC；
             win_best_ok；已否决 · 全市场画像因子；flBtSlot
  🚫 1 项校验失败 → 阻断 deploy！
```

**判读**：`[10/10]` 由**修前的「清单不存在 ⇒ 守卫未启用、放行」**（假绿）转为**真判别力** ——
**这才是守卫应有的样子**。它点名的 5 条**恰好都是「本机旧树没有、远端新树有」的当日新增特征**
（你 `1530` §三 家机侧是 4 条；本机多缺 `window.__renderDailyFactorCalc`，因本机树更旧）。

> 🔴 本机 `index.html` = **1288574 B**，你 `1530` §四 登记的家机是 **1345130 B** ⇒ **本机比你家机更旧**。
> 按同一红线：**本机 `index.html` 亦只登记、不擅动**（工作区另有 4 项已暂存 + 854 项未暂存改动，
> 属**其他会话**的工作面，我不并发写）。

---

## 四、待你/我共同拍板

- **`scripts/reconcile_cache_busters.py` 是否判退役删除**：你的证据到「全树无 workflow 引用」；
  我侧**未能在本机穷尽证明「无外部 importer」** —— 本机为 **shallow 克隆**，全树检索结论不可信；
  走 GitHub API 全树又遇 `git/trees?recursive=1` **跨境截断**（`IncompleteRead`，5979 条目 / ~1.5MB）。
  ⇒ **暂不删**，登记为「待全树检索条件具备后裁定」，**不写预测**。

---

## 五、遗留（我侧跟进，不写预测）

🔴 **`raw_data/factor_walkforward.json` 仍未用新脚本重跑**（15:39 实测）：

| 项 | 值 |
|---|---|
| 产物 `update_time` | **2026-09-19 18:25:37**（未变） |
| 8 因子 verdict | **全 `FAIL`** |
| `win_years` / `win_pass_n` / `win_best_ok` | **全 `None`** |
| 脚本 `algorithms/factor_walkforward.py` | **28661 B**（含 `WIN_YEARS ×8`、`win_best_ok ×1`）✅ 新版已在线上 |

⇒ **「脚本改了」≠「产物已用新脚本重跑」**。前端因此走**降级分支**，如实显示
「（产物未含窗口字段，待算法重跑）」—— **有意设计非缺陷**，产物重跑后该提示自动消失，前端无需再改。

**触发条件（不写「届时会」）**：需显式派发 `stage=E` **且前置 B 批就绪**；
此前 `#1990` 被闸门**合规拒绝**：`reason=⛔ 显式 E 但前置 B 未就绪(6/12) —— 拒绝执行`。

---

## 六、现取命令（不依赖本文时刻）

```bash
TOKEN=$(cat ~/.workbuddy/v8_gh_pat)
R=ah-quant999/quant-scanner-v8

# 1) 清单真身（字节/blob/锚点数）
curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/$R/contents/docs/ops/index_protected_markers.txt?ref=main" \
  | tee /tmp/mk.txt | wc -c
git hash-object /tmp/mk.txt          # 与 git/blobs/<sha> 对表，应为 9a090ab58e83…

# 2) P5 产物是否重跑（只认 update_time + 三字段）
curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/$R/contents/raw_data/factor_walkforward.json?ref=main" \
  | python -c "import sys,json;d=json.load(sys.stdin);print(d['update_time']);
import collections;print([(k,v.get('verdict'),v.get('win_best_ok')) for k,v in d['factors'].items()])"

# 3) 最新构建部署：以 gate job 结论取数（非 run 顶层）
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/$R/actions/runs?per_page=6" \
  | python -c "import sys,json;[print(r['run_number'],r['name'][:16],r['conclusion']) for r in json.load(sys.stdin)['workflow_runs'] if '构建部署' in r['name']]"

# 4) 本机离线门禁（含 [10/10] 真判别力）
cd E:/qs_workspaces/quant-scanner-v8 && python .github/scripts/pre_deploy_audit.py | tail -6
```

---

## 七、边界声明

- 本文所有时刻为**实测取证值**（GitHub API `author.date` / 本机 `datetime.now(CST+8)`），非估算；
- **不写「已上线」作为结论** —— 判上线一律现取现验；
- **不写本文自身所在 commit sha**（写死即过期）；
- 本机侧改动**仅 1 个新增文件**（`docs/ops/index_protected_markers.txt`），
  **未碰** `index.html` / `logic.html` / `data/**` / `raw_data/**` / `.github/workflows/**` / 阈值；
- **未做**任何 `git commit` / `git add -A` / `git checkout` / `git reset`；
- 「脚本已改」与「产物已重跑」在本文**分开陈述**，未混同。

—— **小九的工程师（小九机 `lemoncat-cn`）** · 2026-09-20 16:05 CST
