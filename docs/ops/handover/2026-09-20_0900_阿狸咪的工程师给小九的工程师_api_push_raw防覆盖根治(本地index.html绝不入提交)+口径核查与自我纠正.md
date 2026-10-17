# 交接 · 阿狸咪的工程师 → 小九的工程师

## `api_push_raw` 防覆盖根治：本地 `index.html` 绝不入提交 + 一处 ?v 口径核查

- 时间：2026-09-20 09:00（北京时间）
- 发起方：阿狸咪的工程师（家机 `alimi-cn`）
- 接收方：小九的工程师（单位机 `lemoncat-cn`）
- commit：`757d2fad66031e2a49affded067df939f8c1ee40`
- 改动文件：`api_push_raw.py`（**唯一**；推后按 blob 粒度自证差异集恰好 1 个）
- 触发：主人令「**要核查一下谁的逻辑正确再确认是否防覆盖，同时几个专家在做事，有可能先后发现问题**」

---

## 〇、一句话结论

`v8_cn_fetch_experiments.yml`（`cron 30 8 * * 1-5` = 每日 16:30 CST，**活跃**）把 `index.html` 放进 `PUSH_FILES`，
**全程没有任何 `git fetch` / `reset`**；而 `api_push_raw.py` 的两道守卫对 `index.html` **双双失效** ⇒
它会把 checkout 时刻的 `index.html` 以「最新 main」为 `base_tree` 静默提交回去，**覆盖他人前端改动、无冲突无告警**。
已在护栏层根治（`.py` 可推）；另纠正一处**被 2026-09-10 主人令废除的 ?v 口径**。

---

## 一、先纠正我自己：上一版判定的假阳性（不把没查实的当结论）

我第一版做的是「谁写 `index.html` 却没先 sync」的**正则普查**，标了 7 个 workflow 为「❌ 写前无 sync ⇒ 风险」。
逐条复核后**全部是我的假阳性**：

- 命中的是**注释行**：`v8_cache_buster_reconcile.yml` 的「首次写 @L25」其实是注释里提到的
  `update_v8.py --only-cache-busters`；真正的 `git add -f index.html` 在 **L90**，其前 **L72-73** 有
  `git fetch origin main` + `git reset --hard origin/main`。
- 或命中的是**同步之前的数据重建步**：`v8_cn_fetch_cloud.yml` L588-592 重建 data → L715-716 才 sync
  → L717-718 才重算 `?v` + 推 `index.html`。

⇒ **方法订正**：判定必须落在「**产生 `index.html` 内容的那一步**」与其后最近一次 push 之间的同步点，
不能拿全文件第一个正则命中当写点。改按 push 步重判后，**5 个推 `index.html` 的 workflow 全部 ✅ 正确**：

| workflow | 内容产生点 | 其前最近同步 | 判定 |
|---|---|---|---|
| `v8_build_deploy.yml` | L340 `reset --hard FETCH_HEAD` → L353/371/446 | L310+L340 | ✅ |
| `v8_cache_buster_reconcile.yml` | L72-73 `reset origin/main` → L81 | L72-73 | ✅ |
| `v8_cn_fetch_cloud.yml` | L715-716 sync → L717 | L715-716 | ✅ |
| `v8_cn_fetch_cloud_hosted.yml` | L367-368 sync → L369 | L367-368 | ✅ |
| `v8_cn_fetch_cloud_selfhosted.yml` | L474-475 sync → L476 | L474-475 | ✅ |

---

## 二、查实的真实风险面（唯一一处）

| 项 | 实测（逐条可复跑） |
|---|---|
| workflow | `v8_cn_fetch_experiments.yml` |
| 触发 | `cron: '30 8 * * 1-5'` = 每日 **16:30 CST**，活跃 |
| 同步 | 全文件 **0 处** `git fetch` / `reset`（grep 实查；仅注释里提过历史写法） |
| 写 index.html 的方式 | L116 `PUSH_FILES="...,index.html"` |
| 内容来源 | `api_push_raw.py` L640-642 `open(_rel, "rb").read()` ⇒ **本地磁盘（checkout 快照）** |
| 守卫①「内容一致」 | L712 `remote_sha = existing.get(path)`；`existing` 由 `_GUARD_PREFIXES = ("raw_data/", "data/")` 构建 ⇒ `index.html` **不在基线** ⇒ `remote_sha=None` ⇒ 不生效 |
| 守卫②「防倒退」 | L736 额外要求 `path.endswith(".json")` ⇒ `.html` **二次豁免** |
| 提交基准 | L897-906 / L931 每次重读最新 main 作 `base_tree` + `parents`，`force=False` ⇒ push 天然 fast-forward，**无冲突、无告警、无 422** |

⇒ 与 `v8_build_deploy` 那个**三度复发**的覆盖**同机制**，只是入口不同（API 路径 vs git 路径）。
⇒ 影响：16:30 那趟 run 的 checkout→push 窗口内（数分钟）任何人对 `index.html` 的改动会被**静默回退**。

---

## 三、顺带查到：一个「假成功」+ 一处被废除的口径

### 3.1 假成功（实测）

`api_push_raw.py` L823-825 走 Contents API 取 `index.html` 正文。实测：

```
GET /repos/ah-quant999/quant-scanner-v8/contents/index.html
  size = 1366370   encoding = 'none'   content 键存在? True   content 长度 = 0
```

`index.html` 1.36MB **> Contents API 的 1MB 上限** ⇒ `encoding:"none"` + `content:""`（**键在、值为空串**）
⇒ `base64.b64decode("")` = 空串 ⇒ `_stamp_index_v("")` 恒无改动 ⇒ 打印
**「ℹ️ index.html ?v 已一致，无需改动」**。**既没对齐，也没说明取不到正文** —— 标准假成功。

### 3.2 口径错误（休眠陷阱）

`_stamp_index_v` / `_neutral_sha` 写的是 **sha1 内容哈希**。而：

- `update_v8.py` L810-818 明载 **2026-09-10 主人令**已改口径：内容哈希在「数据被回滚到旧内容」时
  哈希恰好等于旧版 ⇒ 浏览器缓存旧 `?v` 永远吐旧数据（表现为「最终推荐回退到 2 天前」）⇒
  现行 = **单调 unix 秒令牌**（`_UPDATE_TOKEN = str(int(time.time()))`）。
- `v8_build_deploy.yml` L445-447 提交前核验**已明文报警**：
  `bad = sorted(set(v for v in m if not v.isdigit()))` → `::warning::?v 出现非 unix 秒令牌(旧内容哈希口径回潮)`。

⇒ 若那条路径真执行（正文可读时），会写出十六进制形态 = **被本仓自己的核验判为口径回潮并触发重写**。
当前因「>1MB 取不到正文」而未触发 ⇒ **休眠陷阱**，不是无害。

---

## 四、修复（已落 main，夹具+回退版对照过）

| # | 改动 |
|---|---|
| 1 | 新增 `_SKIP_LOCAL_PUSH = {"index.html"}`，在 **PUSH_FILES 分支**与**全量收集分支**双处剔除 ⇒ 本地 `index.html` **永不入提交** |
| 2 | 新增 `_stamp_remote_index_v()`：取**远端最新正文**（复用 `_blob_text`，`contents?ref=` + raw，**绕开 1MB 截断**）就地重算 `?v`；取不到正文时**显式告警**（不再谎报「已一致」） |
| 3 | `?v` 口径改为 `str(int(_time.time()))` **单调令牌**（与 `update_v8._UPDATE_TOKEN` 同源） |
| 4 | 在 `_neutral_sha` / `_stamp_index_v` 上方加**废除口径标记**（历史留痕；**未删** —— 「无外部 importer」的证明不足） |
| 5 | 该路径全部包 `try/except`：`index.html` 侧失败**绝不阻断**本批 data 推送（沿用 2026-08-15 既有纪律） |

---

## 五、门禁证据（同一夹具，跑两版）

夹具：cwd 内 `index.html` = `STALE-CHECKOUT-SNAPSHOT-MARKER-0920`（模拟 checkout 陈旧快照），另有 `data/DEMO.js`；
`PUSH_FILES=index.html,data/DEMO.js`；`api()` 全桩化（**不发真请求**）。

| 版本 | `index.html` 入提交 | 推的是本地陈旧快照 | `data/DEMO.js` 照常推 |
|---|---|---|---|
| 旧版 `f3c418894b` | True | **True** | True |
| 新版 `757d2fad66` | **False** | False | True |

桩测 `_stamp_remote_index_v`：基准 = 远端 **1,133,650** 字符正文；只改 `data/FOUR_VOLUME.js` 的 `?v`
（`1789865418` → `1789865907`，**纯数字 monotonic token**）；整文长度 **零变化**（delta=0）。

其余门禁：严格 `compile()` 通过；行尾保持 **LF（CRLF=0）**，不制造全文件行尾翻转；
推后回读 sha256 与推送字节**一致**；线上复核 7 项特征位全在位；**文件级差异集恰好 = `['api_push_raw.py']`**（零覆盖）。

---

## 六、副作用与善后（诚实列出）

1. **`v8_ima_strong_stock.yml`（L44-45 有 sync，L51 重算 ?v，L61 推 PUSH_FILES）与 experiments**：
   其 `index.html` 的 `?v` 对齐**改为由 `v8_cache_buster_reconcile` 自愈**。两条链的推送都含 `data/**`，
   会**立即触发** reconcile（另有每 15 分钟兜底）⇒ 窗口从 0 变为 **≤1 分钟**。
   这是**刻意的取舍**：宁可有 ≤1 分钟的 `?v` 陈旧（可自愈），也不要一类静默覆盖前端内容的风险。
2. `update_v8.py::_ensure_momentum_loader()`（往 `index.html` 补 `STOCK_MOMENTUM_STATE.js` 标签）
   经 experiments/ima 路径不再随该批发布；由 `v8_build_deploy`（先 reset、再全量 `update_v8`、
   再 `git add index.html`）在数分钟内补上。**当前线上该标签在位数 4，无回归**（已实测）。
3. **建议（需你方 workflow 权限；本机 PAT 对 `.github/workflows/**` 必 403）**：
   - `v8_cn_fetch_experiments.yml` L116 摘掉 `index.html` —— 现在它已是**静默失效的死条目**，
     留着会被人抄走这个坏范式；
   - 可选加固：给该 workflow 补一步 `git fetch origin main && git reset --hard origin/main`
     （与 ima / cache_buster 对齐）。
   - 补丁件：`docs/ops/patches/PATCH_2026-09-20_0900_cn_fetch_experiments_摘除PUSH_FILES里的index.html.md`

---

## 七、残留（未做，留证）

- `scripts/reconcile_cache_busters.py`（8512 B，仍在 tree 内）依旧写 **sha1 内容哈希**口径，
  但**全 workflow grep 0 处实际调用**（`v8_build_deploy` 仅注释提及）⇒ 疑似退役件。
  **未删**：无外部 importer 的证明不足，删前请确认。
- `data/*.js` 同样没有防倒退守卫（L736 的 `.json` 判据把 `.js` 排除）；但其新内容本就应当覆盖，
  且各调用方均先 sync 或有 reconcile 兜底 ⇒ 我判定**无需改**，仅记录。

---

## 八、请你方复核（我可能错的地方）

1. 「experiments 无 sync」是否与你方设计意图一致（还是原本就打算靠 `api_push_raw` 的守卫兜住）？
2. 「`index.html` 一律剔出本地推送」是否影响你方任何依赖「**本地 index.html 有必须发布的结构改动**」的链？
3. `scripts/reconcile_cache_busters.py` 可否判定退役并删除？

---

## 九、纪律声明（本方本轮）

- 只改 `api_push_raw.py` **一个文件**；`base_tree` 单路径替换 + `force:false`；推后按 **blob 粒度**自证差异集恰好 1 个。
- 未 force、未 `git add`、未触碰坚果云同步仓内任何文件；全部取数走 GitHub API 只读。
- 我上一版正则普查的 7 项「风险」已在本件 **§一** 自我纠正，不留在案。

—— 阿狸咪的工程师（家机 `alimi-cn`）
