# 小九 → 阿狸咪 · P0「cn 链方案B 因子融合永久降级」一劳永逸根治

- **撰写人**：小九的工程师（小九机）
- **数据采集时刻**：2026-09-20 23:00（北京时间）
- **关联 commit**：`9d989f5f5666`
- **本件性质**：已上线改动的三件套交接 + 待你侧确认项

> 本文所有结论均为**截至 2026-09-20 23:00 实测**。凡涉及「后续会如何」一律写成可跑的复核命令，
> 不作预测式表述。**不写本文自身所在提交的 sha** —— 请用文末命令现取。

---

## 一、问题定性（已用线上真身 + 源码逐行确证）

### 现象
`data/FINAL_RECOMMEND_DATA.js` 长期携带 `data_degraded: true`，且其内部：

```
factor_chain.skipped = true
factor_chain.skip_reason = "本轮 FACTOR_LAB.js 缺失/内容陈旧 ⇒ 方案B 因子融合整体跳过（数据降级）"
factor_chain.integrated = []
degrade_note = "⚠️ 数据降级：上游采集（A 批）已落后 ? 个交易日（阈值 2）…"
```

即：**「方案B 因子融合」从未真正执行**，且降级文案把原因指向了 A 批上游（错的方向）。

### 根因 A（主因 · 永久性）
`.github/workflows/v8_algo_run.yml` 第 2 步「📥 经 GitHub API 同步源码」的同步范围：

```python
_PREF = ("algorithms/", "scripts/build_delisted.py")
...
if p.startswith("algorithms/") or p == "scripts/build_delisted.py" or ("/" not in p and p.endswith(".py")):
```

⇒ 只同步 `algorithms/` + `scripts/build_delisted.py` + 根级 `.py`，**`data/` 整目录不参与同步**。

而 `algorithms/final_recommend.py` 的因子新鲜校验读的是 `data/FACTOR_LAB.js`
（`load_js` → `os.path.join(ROOT, "data", name)`）⇒ 在该 runner 工作树上恒为
「上一轮残留 / 缺失」⇒ 20 次等待全败 ⇒ `_fl_degraded = True`。

**这是永久性失效，不是偶发**：只要同步范围不含 `data/`，每一轮 cn 链的因子融合都必然被跳过。

### 根因 B（误导性文案）
`final_recommend.py` 中降级标记是三源或：

```python
_degraded = (DEGRADED_UPSTREAM == "1") or _fl_degraded or SIGNAL_EDGE_DEGRADED
```

但 `degrade_note` 只描述 `DEGRADED_UPSTREAM` ⇒ 因子降级时却报「上游 A 批落后 `?` 个交易日」，
既答非所问、又暴露空值 `?`，会把排查引向错误方向。

---

## 二、已落地的修复

| # | 文件 | 改动 | 状态 |
|---|---|---|---|
| FIX-1 | `.github/workflows/v8_algo_run.yml` | `_PREF` 增加 `"data/"`；过滤条件增加 `p.startswith("data/")` | ✅ 已上线 |
| FIX-2 | `algorithms/final_recommend.py` | 新增 `_build_degrade_note()`，按**真实来源**（上游 / 因子陈旧 / signal_edge 加载失败）逐条分述；`degrade_note` 改调该函数 | ✅ 已上线 |

**线上真身核验（截至 2026-09-20 23:00 实测）**：

- `v8_algo_run.yml`：含 `"data/"`、含 `p.startswith("data/")`、含 `P0 修复` 注释 → 全 True
- `final_recommend.py`：含 `_build_degrade_note`、含中文分述文案 → 全 True
- 祖先判定（GitHub compare API，`base=9d989f5f5666, head=main tip`）：`status=ahead, behind=0` ⇒ **未被覆盖**

---

## 三、待你侧确认 / 复核（不预测、只给命令）

### 1. 下一轮 cn 链跑完后，确认因子融合是否真的恢复
```bash
# 取 main 上最新 FINAL_RECOMMEND_DATA.js，看 factor_chain.skipped 是否转 false
curl -s https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/data/FINAL_RECOMMEND_DATA.js   | grep -o '"factor_chain":{[^}]*}[^}]*}' | head -c 600
```
判据：`"skipped":false` 且 `"integrated"` 非空 ⇒ 修复生效；
仍 `skipped:true` 则需再查 runner 工作树上 `data/FACTOR_LAB.js` 的实际内容与 mtime。

### 2. 确认 sync 步新增 data/ 后未引入同步耗时超限
`data/` 目录文件数较多，请留意第 2 步耗时是否显著上升。
判据：run 的第 2 步（`📥 经 GitHub API 同步源码`）耗时若接近 step timeout，需评估是否收窄为
「仅 `data/FACTOR_LAB.js` + `data/TOP10_DAILY.js` 等算法链实际消费的少量文件」。

### 3. degrade_note 新文案落地确认
```
"degrade_note": "⚠️ 数据降级：<真实来源分述>…"
```
判据：不再出现「上游采集（A 批）已落后 ? 个交易日」这种在因子降级时的错位表述。

---

## 四、本会话遗留与自我纠错（如实登记）

| 项 | 说明 |
|---|---|
| 我上轮删死代码 `0d3482be` 误删 `_renderPostReady` 定义 | 已由你方 `2d217a8e8`（22:15）恢复；线上实测 `function _renderPostReady` 已存活（出现 8 次）✅ |
| `__renderFactorLab` 线上仍余 2 处 | 经定位是**你方撰写的事故说明注释**（非代码，不产生 ReferenceError），我判断应保留为历史记录 —— 若你方希望一并清除请告知 |
| 「有调用无定义」另有 4 个（`__renderCycleLadderCard` / `__renderLimitUpHeatmap` / `__renderOps` / `__retryJudgmentRender`） | 经逐处定位**均为假阳性**：它们用 `window.X = X` 形式导出（非 `window.X = function`），定义齐备。已复核，无需改动 |

---

## 五、环境坑（供你侧参考）

本机在本次排查中出现：`git` PATH 间歇失效、Bash shim 报 `dirname/cd: null directory`、
`head`/`tail`/`wc` 不可用。**已验证可行的绕法**：
1. git 绝对路径 `C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd/git.exe`；
2. 大文件（index.html 1.3MB）不可经 Contents API 拉取（跨境 `IncompleteRead`），改 `git show <ref>:<path>` 落盘；
3. **本地仓为浅/不完整克隆** —— 本地 `git merge-base --is-ancestor` 会给出「Not a valid object name」
   之类的**假阴性**，祖先判定请用 GitHub compare API（`/compare/<cand>...<tip>`，看 `behind` 是否为 0）。

---

## 六、现取本文所在提交（避免写死 sha 过期）
```bash
curl -s "https://api.github.com/repos/ah-quant999/quant-scanner-v8/commits?path=docs/ops/handover/&per_page=1"   | grep -m1 '"sha"'
```
