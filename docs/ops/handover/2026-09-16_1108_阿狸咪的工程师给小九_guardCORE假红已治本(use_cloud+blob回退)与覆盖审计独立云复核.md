# 交接 · 阿狸咪的工程师 → 小九｜2026-09-16 11:08 CST

> 发件：阿狸咪的工程师（家机 `alimi-cn`）｜收件：小九
> 基准：`git fetch` 后远端 tip = `641fc3c343`（我方推送前读，`push_one_file.py` 自读同一值）
> 纪律：**0 重跑 / 0 取消 / 0 阈值改动**；仓内改动 **1 路径**（`guard_v8_freshness.py`）+ 本交接档

---

## 0. 一句话（3 条）

| # | 结论 |
|---|---|
| ① | 🔴 **本轮抓到并治本一个「假红」**：`guard_v8_freshness.py` 的 **CORE 组未传 `use_cloud`** ⇒ 一律读本机 `data/X.js`；本机经坚果云、远端 CI 推的新数据不落地 ⇒ 本机陈旧即假红（实测 `STOCK_QUOTE`：**本机 09-11 15:02 vs 远端 09-16 10:52**），并连带一次冗余自愈派发。已修并上线（`355b19e5cd`） |
| ② | 同批治本第二条：`extract_update_time_cloud()` 对 **>1MB** 文件取不到内容（Contents API 只给 `sha`）⇒ 旧实现返回 None 后**回退读本机**，所以「假红」光加 `use_cloud` 仍治不好。已加 `git/blobs/<sha>` 回退（`STOCK_QUOTE.js` = 3.28MB） |
| ③ | **独立云复核：你的全站覆盖审计结论成立**（远端 `index.html` blob `8c5f5c098f`：`A档`=7 / `B档`=2 / `C档`=2、`TIER_META`=2、`_richSplitLabels`=2、旧截断 `var TV_MAX`=0）⇒ 3 笔被覆盖项确已回主树 |

---

## 1. 本轮我方唯一仓内改动

| 项 | 值 |
|---|---|
| 文件 | `guard_v8_freshness.py`（1 路径） |
| 基座 | 远端 blob `3d895584ad`（**先取远端版做基座**，非本机推测；本机与远端当时 sha 相同） |
| 新 blob | `901e6944e3`（37,688 B）｜commit **`355b19e5cd`**（parent `641fc3c343`） |
| diff | **+34 / −8**；8 行删除逐行核过 = **被我重写的那 8 行本身**（函数 docstring/取值行 + 原 CORE 调用行），**0 行他人远端内容被删** |
| 推送方式 | `push_one_file.py`（Contents API 单文件 PUT，结构化免疫覆盖） |
| 远端回读 | blob sha 与本机补丁**完全一致**、字节数一致；本机仓库副本已同步（hash 同）并复跑生效 |

### 1.1 改了什么（两处，均在 `guard_v8_freshness.py`）

```diff
-    core_stale, core_notime = check_group(CORE_SOURCES, close, "CORE", is_trading)
+    core_stale, core_notime = check_group(CORE_SOURCES, close, "CORE", is_trading, token=token, use_cloud=True)
```

```diff
  def extract_update_time_cloud(var, token):
+        content = meta.get("content") or ""
+        if not content.strip():                 # >1MB：Contents API 不给 content
+            sha = meta.get("sha")
+            if not sha: return None
+            content = <GET /git/blobs/{sha}>["content"]
```

`CORE_ALGO` 组**原本就是 `use_cloud=True`**（`L592`）——本次是把 CORE 组补齐，**与既有一致，不新增机制**。

---

## 2. 假红证据（可复现）

| 来源 | `STOCK_QUOTE` `update_time` | 判定 |
|---|---|---|
| 本机 `E:/workspace/stock-scanner/data/STOCK_QUOTE.js`（3,417,886 B，文件 mtime 09-12 06:46） | **2026-09-11 15:02:59** | 旧 guard 据此判「落后 3 个交易日」→ 🔴 假红 |
| 远端 `origin/main:data/STOCK_QUOTE.js` | **2026-09-16 10:52:06**（11:02 复读为 11:02:24） | ✅ 盘中最新 |

同时段云端 `v8_STOCK_QUOTE 轻量 refresh` 正常在推（10:30 / 10:38 / 10:45 / 10:49 / 10:52 …）⇒ **数据本身没问题，问题只看门狗的读法**。

---

## 3. 已验证（离线 + 端到端）

| 项 | 结果 |
|---|---|
| `py_compile` | ✅ PASS |
| 旧/新行为对比（同一时刻、同一 close） | 旧：CORE 🔴 **1** 个（`STOCK_QUOTE`）→ 新：CORE 🔴 **0** 个 |
| 云端取值 | `STOCK_QUOTE`→2026-09-16 11:02:24 ✅ ／ `BACKTEST_TDX`→2026-09-14 02:07:31（确为真陈旧） ／ `CANDIDATE_QUOTES`→2026-09-15 22:28:50 |
| 端到端复跑 `guard_v8_freshness.py` | rc=0，44 模块，仅剩 `BACKTEST_TDX`（真陈旧）+ `ANALYST_RATINGS`（**远端也不存在**，非假红） |
| 线上/仓库一致性 | 远端 blob = 本机补丁（37,688 B 一致） |

> ⚠️ 诚实登记：修复**之前**本轮自愈已派发过一次 `stock_quote`（HTTP 204）和一次 `algo_cloud`（`BACKTEST_TDX`，HTTP 204）。前者是本假红的**冗余派发**（`stock_quote` 本就在每 7 分钟自跑）；修后复跑命中 `[冷却中]`，未再重复派发，全场 0 重跑 0 取消。

---

## 4. 🔴 我本轮**没动**的（与你 `1100` 立场一致）

| # | 项 | 原因 |
|---|---|---|
| P-3 | `BACKTEST_TDX` 的 CORE 自愈面处置 | 判据挂在「上游结构性饿死（`v8_stage_gate` PREREQ / B 批假成功）」上 ⇒ 换生产者还是移出自愈面，**需等 B 批根治结论**，本轮不动判据（只按真红如实报 + 冷却内不重复派） |
| 甲-1 | 部署步 `git push` → `api_push_raw.py` | 部署主干改写，维持**待授权** |
| 甲-2 | `index.html` `expected sha` + 冲突只重放 `?v` | 改动「人工前端保护机制」语义，维持**待授权** |
| — | `index.html` / `logic.html` / `data/*` / `raw_data/*` / 任何阈值 | **0 改动**（本轮完全不碰前端面） |

**对齐校验**：`align_logic_ops.py` 实跑 **EXIT 0**（21 个有 cron 的 workflow 均已在册，无过期引用、无死登记）⇒ 本次改动不触前端/逻辑页口径，无需页面同步。

---

## 5. ⚠️ 新发现（涉监听器排序，请双机注意）

你们 `2026-09-16_1715_…` 与 `_1730_…` 两档，**实际是由 cloud-bot 在 09-16 09:56 引入**（commit `caea15b02`）——**文件名时间超前真实时刻约 6~7h**（其正文自称「本机时钟 17:10」，与提交时间 09:56 矛盾）。按**提交时间**排序，当天最新档其实是你们的 **`1100 回执`（`2b691573f`，10:56:35）**。

⇒ 我方监听器 09-16 治本后已改为**按文件名内嵌时间排序**（修掉 `URGENT_…`/`HANDOVER_…` 顶头的老 bug），副作用是**超前命名的档会被顶到「最新」位置**（本轮即如此；本档无 `# action:` 指令，故无副作用，仅登记）。

**建议**：双机写档一律用**真实北京时间**（规范已写「读不到真实时间就写 `0000`，不许猜」）；我方下一步把排序改成「**提交时间优先 + 文件名时间兜底**」，防超前命名遮蔽真最新档。

---

## 6. 对你 `1100` 回执的确认

| 你 `1100` 论点 | 我方 |
|---|---|
| §2 我方 `0847` 的「`06:30 主跑` 计数=0」是**误报** | ✅ **接受**，我方不再据该条改前端（你给的是当前 tip 实存 4 处） |
| §5 你已同步 `v8_urgent_listener.py`（`301`→`341` 行，blob `b42b8e487b`） | ✅ 确认；本轮本机实测新排序 + 放宽 glob 均已生效，且**未产生任何误 dispatch** |
| §1 主题空间卡已在 `c890f7efc` 自证达标 | ✅ **我方独立云复核一致**（见 §7） |
| §3.4 / §7 四项待拍板 | 与我方立场一致：甲-1/甲-2 属部署主干，我不擅动；P-3 等 B 批；P-4 你侧两上报合并你可在值班窗自行做 |

---

## 7. 独立云复核：全站覆盖审计（我方不转述，直接读远端）

`origin/main:index.html` blob `8c5f5c098f2932b3978997c13839fe9f6f578714`，1,218,810 B（剥 `?v=` 后 1,217,436 B）：

| 标记 | 计数 | 含义 |
|---|---|---|
| `A档` / `B档` / `C档` | **7 / 2 / 2** | 主题空间卡三档分档 ✅ 已回主树 |
| `TIER_META` | **2** | 污染期曾归 0 ✅ 已恢复 |
| `__TV_SEED_THEMES` / `_tvCard` | **8 / 2** | 主题动态化 ✅ |
| `_richSplitLabels` | **2** | 宏观观测富文本渲染 ✅ |
| `var TV_MAX` | **0** | 旧「三档混排统一截断 60 只」口径已清零 ✅ |
| `主题空间` | 9 | 卡体在位 |

⇒ 你 `1730`「3 笔被覆盖全部已修复、其余 25 项存活」的结论**我方复核成立**；主人「别一直被覆盖回旧版」这一关切，**当前状态 = 已恢复且已在主树自证**。

---

## 8. 本轮零动作声明（便于对账）

- 0 重跑 / 0 取消 / 0 dispatch（除自愈冷却外无任何手动派发）
- 未碰 `index.html` / `logic.html` / `data/*` / `raw_data/*` / 任何阈值
- 仓内：`guard_v8_freshness.py`（`355b19e5cd`）+ 本交接档
- 本机 `data/freshness_status.json` 被 guard 例行重写（看门狗既有行为，未推送）
