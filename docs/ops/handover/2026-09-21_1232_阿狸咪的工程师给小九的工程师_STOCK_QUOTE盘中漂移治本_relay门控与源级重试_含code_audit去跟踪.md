# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-21 12:32｜STOCK_QUOTE盘中漂移治本_relay门控与源级重试_含code_audit去跟踪

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

盘中 STOCK_QUOTE 的**执行主力跑在「错的 runner」上**：中国 IP 主链今天只有 **1 档**、海外 IP 兜底链 **15 档**（每 7-8 分钟一次）⇒ 撞新浪/东财反爬 ⇒ 盘中 2 次「双源全灭」（10:08 / 11:21）。根因是 `v8_cn_fetch_cloud.yml` 的 **relay ② 无条件派发兜底链**（09-17 已诊断、当时未修 ⇒ 同一 bug 二次出现）。本轮已改成「**主链优先 + 主链离线才兜底**」三态门控，并给抓取脚本补了源级重试。**已上线**：commit `5728c2175e3f`（parent `d9556121b6`），6 项改动、回读 5/5 逐字节一致。

---

## 正文
> **时间**：2026-09-21 12:3x CST（午休窗口·只走 API 推送，不碰本机落后工作树）
> **发起**：阿狸咪（家机 `alimi-cn`，小九下线期 cn 侧唯一在线节点）
> **收件**：小九（单位机 `lemoncat-cn`）—— **你已于 12:29 回归**（`7f9966897`）并落了你那批协议裁决，
> 本档因此按新规约收窄为「**跨机需知的结构性变更**」；其中 2 项待办我按你的规约指向 `HANDOFF.yaml`。
> **级别**：🔴 **P0 治本**（同一 bug 二次出现，且本次已恶化）
> **前置**：09-17 `URGENT_STOCK_QUOTE盘中刷新漂移海外IP兜底链致双源全灭` 已诊断同题、**只留痕未改行为**
> ⇒ 本次是**该诊断的落地执行**，非新议题。判据 203~206 系本轮新增。
> **声明**：本轮**未改** `index.html` / `logic.html` / 任何数据产物；未重跑算法链；未派发任何 workflow。

---

## 零、一句话结论

盘中 STOCK_QUOTE 的**执行主力跑在「错的 runner」上**：中国 IP 主链今天只有 **1 档**，
海外 IP 兜底链跑了 **15 档**（每 7-8 分钟一次）⇒ 撞新浪/东财反爬 ⇒ 盘中 2 次「双源全灭」。
根因是 `v8_cn_fetch_cloud.yml` 的 **relay ② 无条件派发兜底链**（09-17 已诊断、未修）。
本轮已把它改成「**主链优先 + 主链离线才兜底**」三态门控，并给抓取脚本补了源级重试。

---

## 一、修复前实测（基线·今天）

**两链档数对比（判据指纹：严重不均）**

| 链 | runner | 今天档数 | 明细 |
|---|---|---|---|
| `v8_stock_quote_refresh_cloud.yml`（兜底） | `ubuntu-latest`·**海外 IP** | **15** | 09:46→11:28 每 **7-8 分钟**一档 |
| `v8_stock_quote_refresh.yml`（主链） | `[self-hosted, cn]`·**中国 IP** | **1** | 仅 09:26（`workflow_dispatch`） |

> 兜底链间隔实测：+7.8 / +6.6 / +7.4 / +6.8 / +7.1 / +9.4 / +7.4 / +12.3 / +7.8 / +7.3 / +7.4 / +7.5 / +7.5 分钟
> ⇒ 已是 09-17 记录值（15-18 分钟）的 **2 倍密度**。

**2 次 failure 的原文（`step #7 🧮 跑 fetch_stock_quote_v8.py`）**

```
10:08:02  failure  35553134311
11:21:03  failure  35557224566
   ⚠️ 新浪A股行情失败: JSONDecodeError Can not decode value starting with character '<' → fallback 东财
   ⚠️ 东财A股行情也失败: ConnectionError ('Connection aborted.', RemoteDisconnected('Remote end close
   A股：0 只，93.0s
   ❌ A股行情异常稀少（0 只 < 3000），新浪+东财均不可用 → 拒绝写输出，保留旧数据
```

- `'<'` = 拿到**反爬拦截 HTML 页**（不是 JSON）⇒ 海外 IP 撞新浪反爬的签名；
- `RemoteDisconnected` = 东财掐断连接；
- **相邻档 11:28 即 success** ⇒ 波动型拒绝，属"单次瞬断"格。
- 注：**「拒绝写输出、保留旧数据」的守卫本身是对的**，未污染旧数据 —— 但前端行情卡在这两档最多滞后 ~7 分钟，且**盘中没有任何机制会因此报警**（只体现在 run 列表里）。

---

## 二、根因（两层，本轮都治了）

### 2.1 结构层（真根因）· relay ② 无条件派发「错的链」

`v8_cn_fetch_cloud.yml` 原 relay ②（**本轮已改**）：

```python
api("POST", f".../actions/workflows/v8_stock_quote_refresh_cloud.yml/dispatches", {"ref": "main"})
```

- 该 relay 与 ① 自接力「派下一轮 intraday」**同秒前后**执行 ⇒ 派发源确认；
- 而 `_cloud` 文件**自己的头注**写着「平时不跑、仅本机 runner 接单超时(>12 分)派发」
  ⇒ **契约与实现相反**；09-17 已把此冲突列为"待拍板项"，当时以"避免给云端刷无用 run"为由**未改**。
- 结果：**注释里反对这么用，代码却在这么用**，且持续 4 天 ⇒ 同一 bug 二次出现。

### 2.2 直接层· 抓取脚本对「瞬断/反爬」零防御

- `fetch_all_spot()`（新浪）/ `_fetch_all_spot_em()`（东财）**每源只打一次**（单 `try`）
  ⇒ 一次抖动整轮 `exit 1`；头注写的"境外 runner 偶有抖动但可通过多源重试兜底"**代码里不存在**。
- 无第三源（腾讯接口本机 akshare 1.18.64 **无** `stock_zh_a_spot_qq` ⇒ 本轮不冒进接三方源）。

---

## 三、本轮改动（6 项 · 一次推送）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `.github/workflows/v8_cn_fetch_cloud.yml` | relay ② → **三态门控**（主链优先 + 离线才兜底）；step 结构零变化（28→28） |
| 2 | `algorithms/fetch_stock_quote_v8.py` | 新增 `_retry()`；新浪/东财各 **3 次尝试 + 退避(2,5)s**；`a_count<3000` 守卫**保留不动** |
| 3 | `.github/workflows/v8_stock_quote_refresh.yml` | 头注更正：旧句「统一由哨兵每 10 分派发」与实测不符（今天仅 1 档） |
| 4 | `.github/workflows/v8_stock_quote_refresh_cloud.yml` | 头注补「09-21 起仅主链离线才被派发」的**最终口径** |
| 5 | `raw_data/code_audit.log` | **从远端 tree 删除**（去跟踪；`tree` 项 `sha=None`） |
| 6 | `.github/scripts/pre_deploy_audit.py` | 注释与行为同步（「尚未做 git rm --cached」→「本轮已完成」） |

**门控判据（新增常量，口径可直接复核）**

```
MAIN_SQ  = "v8_stock_quote_refresh.yml"        # 主链·[self-hosted, cn]·中国 IP
CLOUD_SQ = "v8_stock_quote_refresh_cloud.yml"  # 兜底·ubuntu-latest·海外 IP
FRESH_MIN, QUEUE_MAX = 12, 10

取主链最近一次 run r0：
  无 r0                                        → 派主链
  r0 queued/in_progress：queued 且 age ≥ 10 分  → 判 cn runner 离线 → 派兜底
                          否则                 → 不派（防叠加 / 防刷无用 run）
  r0 completed：success 且 age < 12 分          → 不派（已新鲜）
                 否则                          → 派主链
异常                                            → 保守派主链
```

**保底联动不靠 sleep**：主链若离线，下一轮 relay 自会看到 `created_at` 年龄超阈值而改派兜底
（09-17 已警告"别 sleep 长挂 relay 步"，本轮遵守）。

---

## 四、校验（全部离线可复现，脚本在 `E:/workspace/_tmp_audit/`）

| 项 | 结果 |
|---|---|
| A. YAML 解析（3 份 workflow） | ✅ 通过 |
| B. relay heredoc Python **真编译**（115 行 / 缩进基线 10） | ✅ 通过 |
| B2. `def` 先于调用的顺序断言（`_sq_age` / `_sq_dispatch`） | ✅ def@2924<call@2928、def@3145<call@3149 |
| C. **门控 8 分支 mock 实测**（queued 短/长、in_progress、success 新鲜/超时、failure、无 run、窗口外） | ✅ **8/8 通过** |
| D. workflow **结构自检**：step 数 28→28、非 `run` 字段 0 差异、无 `run` 步带 `with`、仅 step#27 run 变化 | ✅ 通过 |
| E. 行尾 CR 计数（全部改动文件） | ✅ 0 |
| F. `align_logic_ops.py`（本机仓库） | ✅ 通过 |
| G. 旧派发残留 `v8_stock_quote_refresh_cloud.yml/dispatches` | ✅ **0 命中** |

---

## 五、上线（本次 commit `5728c2175e3f800da5a1cc00a7074930d10c7ed4`，parent `d9556121b6`）

- 推送方式：**Git Data API + `base_tree` + `force:false`**；推前**当场重取 tip**，
  并对三份源文件做「**基线未漂移断言**」（baseline blob == 远端 blob，均 SAME）。
- 推后：blob 逐字节回读；`raw_data/code_audit.log` 用 `git cat-file -e <tip>:<path>` 断言**已不存在**。
- 触发：`raw_data/**` 命中 `v8_build_deploy` 的 `on.push.paths` ⇒ 会跑一次部署（午休窗口，避开盘中）。

**上线后请重点看（判据：不看"绿"，看"两链条数反转"）**：
1. `v8_stock_quote_refresh.yml`（主链）档数应显著上升（预期 ~12 分钟一档，中国 IP）；
2. `v8_stock_quote_refresh_cloud.yml`（兜底）档数应近零（只在主链排队超时才出现）；
3. 若兜底链仍高频 ⇒ 说明 relay 改动未生效（先查 `v8_cn_fetch_cloud.yml` 的 relay step 日志）。

---

## 六、未做 / 候选（勿误记为已完成）

1. **第三源（腾讯 `qt.gtimg.cn`）**：本机 akshare 1.18.64 无 `stock_zh_a_spot_qq`，
   且云端 runner 的 akshare 版本可能与本机不同 ⇒ 需**先探测能力**再接入，并加"行数 < 3000 即丢弃该源"守卫。
   未做原因：字段映射需实测，冒进有写坏全量行情的风险。
2. **`v6_memo.html`**：经查明**不是过期缺陷** —— 它是主站「逻辑详解 → v6 备忘录」子页（Tab 名已明示 v6），
   主人明令保留、有 `guard_v6_memo.py` 守卫，属**有意留档**。本轮未动（我此前的"内容过期"表述不准确，特此更正）。
3. **本机垃圾目录** `_clean_tmp/`（6.8M）、`_cdn_check2/`（21M）：**未被 git 跟踪**（且被 `.gitignore:7 _*/` 覆盖）
   ⇒ 清理它们**不触发任何 deploy**（此前我说"会触发"有误）。已移至仓外 `E:/workspace/_trash_1221/`（28M）待删。
4. **blob 父子比对**（防覆盖锚点粒度问题的正解）仍未实现。
5. 🟡 **`logic.html` 调度矩阵的既有偏差**（**非本轮引入，本轮未动**，故留痕待办）：
   - **L2156**：`09:00 … v8_stock_quote_refresh` 一行的**执行机写「云端 ubuntu」**
     —— 而 `v8_stock_quote_refresh.yml` 实际 `runs-on: [self-hosted, cn]`（中国 IP）；
     云端 ubuntu 的是**兜底副本** `_cloud`。执行机标签与事实不符。
   - **L2159**：`每 30 分 v8_stock_quote_refresh + v8_risk_gauge` 执行机写「cn self-hosted / 云端 ubuntu」
     —— 未区分主/兜底，未反映"09-21 起主力固定为主链"的最终口径。
   - **本轮为何不改**：`logic.html` **并未描述 relay ② 的派发关系**（只描述调度窗口与执行机），
     即我改的那个契约本身**未落入文档** ⇒ 不构成"文档说谎"；且改前端会扩大午休窗口的推送面。
     建议与卡面文案一并做一次前端口径整理时同批修（届时须走 `index.html/logic.html` 的分节与 `?v` 竞态防护）。

---

## 六-B、连带收口（本轮已做，易漏）

`C:/Users/HH20210606/.workbuddy/v8_watch/intraday_backfill.py`（本机盘中兜底补派器，**不在仓库内**）：
其 `recent_activity()` 用 `(FETCH_WF, QUOTE_WF)` 作「盘中写 main 的链」白名单，
而 `QUOTE_WF` 只指 `_cloud` 兜底链。**主力切到主链后，主链的 run 会被漏算**
⇒ 滞后判据虚高 ⇒ 误派/踩踏。已改为三条写者全登记：

```python
QUOTE_MAIN_WF  = "v8_stock_quote_refresh.yml"         # 主链（09-21 起盘中主力·中国 IP）
QUOTE_CLOUD_WF = "v8_stock_quote_refresh_cloud.yml"   # 兜底
WRITER_WFS = (FETCH_WF, QUOTE_MAIN_WF, QUOTE_CLOUD_WF)
```

> 这是判据「**改门控/契约必须同改全部消费点**」的实例：改一处派发方向，要顺着**消费方**扫一遍。
> 其余派发点已按特征扫全仓：`v8_health_patrol.yml` 有 `GAP_CN ≥ STALE_MIN` 门控 ✅、
> `v8_cn_fetch_intraday_lemoncat.yml` 派的是别的链且小九离线中 ⇒ **同特征仅 relay ② 一处**。

---

## 六-C、为什么这次「去跟踪」能一劳永逸（必要条件已核）

单靠 `.gitignore` **挡不住已跟踪的文件**（判据 204）：`raw_data/code_audit.log` 的 `*.log` 规则
早就写在 `.gitignore:14`，它却一直被打包提交 ⇒ 因为**已跟踪文件不受 ignore 约束**。
从 tree 删除后它转为「**未跟踪**」，规则**从此生效** ⇒ 这才是真正的去跟踪。

**已核全仓三处批量 add 都不会让它回来**（三处**均无 `-f`**，受 `*.log` 约束）：

| 位置 | 语句 |
|---|---|
| `v8_algo_intraday_lite.yml:145` | `git add -A` |
| `v8_cleanup.yml:79` | `git add -A` |
| `cloud_weekly_cleanup.yml:217` | `git add data/freshness_status.json raw_data/ data/*.js …` |

⇒ **不会再入库**。长期验证：看下一轮 `v8_cleanup` / `cloud_weekly_cleanup` 跑完后，
远端是否仍无该路径（`git cat-file -e <tip>:raw_data/code_audit.log` 应持续失败）。

---

## 七、本轮新增判据（已沉淀进技能）

| 判据 | 内容 |
|---|---|
| 202 补 | `TZ=Asia/Shanghai date` 在本机 Git Bash 输出 **UTC**（TZ 语义反转）；**默认 `date` 才是对的** ⇒ 窗口判断一律 Python 显式 `+8` |
| 203 | 🔴 仓内「已存在文件」的编辑**报 success 但不持久化** ⇒ 写入后必须 `grep`/`wc -l`/`hash-object` **独立自证**；仓内改动一律走仓外 staging + API 推送 |
| 204 | `git check-ignore` **不带 `--no-index`** 对已跟踪文件恒 `exit=1` ⇒ 判"是否会被忽略"必须加 `--no-index`；推论：已入库文件光加 `.gitignore` **不会**停止入库 |
| 205 | MSYS 的 `/tmp` 与**原生** Windows Python **路径不互通** ⇒ 中间文件一律用显式盘符路径 |
| 206 | API 推送工具需支持**删除**语义（`tree` 项 `sha=None`），否则"去跟踪"只能退回本地 `git rm --cached` |
| 真凶 ㉑ | **派发源漂移**：两链档数严重不均（15:1）+ 失败集中在一链 + 相邻档 success ⇒ grep 全仓 workflow 名找派发源；细则 `references/06-culprit-21-dispatch-drift.md` |

---

## 八、给下一位的提醒

- 凡「注释写的契约」与「代码实际行为」冲突，且冲突会**持续产生错误行为** ⇒ **当场治本**，
  别以"收益不高"挂起（本议题 09-17 挂起，4 天后同一 bug 复现并恶化到 2 倍密度）。
- 判「某链是否健康」不要只看 failure 数 —— **要看主力跑在哪条链上**。
