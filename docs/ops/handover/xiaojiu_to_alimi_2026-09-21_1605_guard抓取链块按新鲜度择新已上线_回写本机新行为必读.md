# 小九 → 阿狸咪 ｜ v8_runner_guard.py 抓取链块「按新鲜度择新」已上线

- **撰写时刻**：2026-09-21 16:05（北京时间）
- **级别**：常规交接（非紧急）
- **状态**：**已上线**（线上已验证）
- **涉及文件**：`v8_runner_guard.py`（仓库根目录）

---

## 1. 一句话

`v8_runner_guard.py` 原来会在每轮推送时，**用本机冻结的旧抓取链块覆盖远端当日的链块**，
导致运维页「数据健康总览」在盘中链空档期（夜间/盘前）误报停更。已改为**按 `run_time` 新鲜度整块择一**，
并**把并集结果回写本机**，让本机链块不再永久冻结。

---

## 2. 缺陷根因（2026-09-21 13:2x 取证）

`raw_data/runner_status.json` 有**两个写入者，字段集互不重叠**：

| 写入者 | 拥有的字段 |
|---|---|
| `cloud_fetch_v8.py`（抓取链） | `run_time` / `category` / `hostname` / `modules` / `summary` |
| `v8_runner_guard.py`（健康巡检） | `update_time` / `status` / `process` / `service` / `worker_logs` / `github` / `runner_env` / `actions_taken` / `message` |

旧实现的并集是 `union = dict(remote); union.update(local)` ＝ **本地整文件优先**。

但抓取链**只写 runner 工作目录副本 + 远端，从不写本机 `E:/` 副本**
⇒ 本机文件里的链块**永久冻结**（实测冻结在 `2026-09-18 16:01:50` / `category=post_close` / `summary total=14`）
⇒ 守卫每轮把它推上去，**用 3 天前的链块覆盖远端的当日新鲜链块**。

**实证**：2026-09-21 07:29～13:23 共 10 轮守卫推送，链块全部 = `2026-09-18 16:01:50`。
只有抓取链在守卫之后紧接着再推一次（如 13:23:29 → 13:23:38 相隔 9 秒）才把远端救回来。

---

## 3. 改了什么（3 处，纯增量 64+/5−）

| # | 位置 | 内容 |
|---|---|---|
| A | `push_status_file` 之前 | 新增 `CHAIN_KEYS` 白名单 + `_chain_block_newer()` + `union_status()` |
| B | `push_status_file` 内并集处 | `union = dict(remote_json); union.update(local_json)` → `union = union_status(remote_json, local_json)`，并加 `isinstance(union, dict)` 保护 |
| C | `push_status_file` 内推送成功后 | 新增**并集结果回写本机** `path.write_bytes(content)`（失败仅打 WARN，不影响推送结论） |

`union_status()` 语义：**健康字段仍本地优先；抓取链 5 键整块取 `run_time` 较新的一方**。
`run_time` 空值视为最旧；两侧相同（或远端非 dict）时退回原行为（本地优先）。

---

## 4. 上线与验证记录

| 项 | 值 |
|---|---|
| 上线时刻 | 2026-09-21 16:00:09 |
| commit | `7a5cc693910a954cd6d7a37bb1f89558bd2677ab` |
| blob | `d3cad3c56e5dcaea12a1619f41b1498566e0476f` |
| 字节数 | 42,022 → **45,257 B**（纯 LF） |
| 基底断言 | ✅ 推送前线上 blob `1656c3d8…` 与打补丁时一致，未漂移 |
| 单元验证 | ✅ 12/12 PASS（含「远端新→取远端」「本地新→取本地」「同值→保持本地优先」「入参不被修改」） |
| 缺陷复现夹具 | ✅ 旧逻辑推 `2026-09-18 16:01:50`（覆盖），新逻辑推 `2026-09-21 15:18:19`（保住） |
| **端到端真跑** | ✅ 16:02:35 实跑 `--push`：远端链块 `15:18:19/intraday/20 条` **未被覆盖**，本机已回写，健康字段照常更新 |

---

## 5. 🔴 请阿狸咪特别注意的新行为

**守卫现在会回写本机 `raw_data/runner_status.json`。**

- **好处**：本机链块不再冻结，缺陷从根上不再复发。
- **需注意**：若你的脚本假设「本机 `runner_status.json` 在守卫跑后内容不变」，这个假设已不成立 ——
  守卫跑完后该文件的**抓取链 5 键会被刷成远端较新值**（这是预期行为，不是数据被污染）。
- **未动任何红线文件**：回写只针对 `raw_data/runner_status.json` 这一个文件。

---

## 6. 两条环境级事实（沿用上一轮结论，仍成立）

1. **本机 git 不在 PATH**（`shutil.which("git")` = None，真实路径 `D:\PortableGit\cmd\git.exe`）
   ⇒ 一切脚本（尤其计划任务/服务会话跑的）必须**显式解析 git 路径**，不能依赖 PATH。
2. **本仓库 `refs/remotes/origin/main` 引用不存在** —— 即使显式 refspec fetch 返回 rc=0 也不落地
   ⇒ 远端取证**必须优先用 `FETCH_HEAD`**，否则会 `fail-closed` 产出**假掉线**。

---

## 7. 复核命令（不写死任何 sha/时刻，请现取）

```bash
# 线上当前字节数与内容特征
curl -s "https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/v8_runner_guard.py?ref=main"

# 远端 runner_status.json 的链块时刻（应随抓取链推进，不应长期停在同一值）
curl -s "https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/raw_data/runner_status.json?ref=main"
```

---

## 8. 观察到的旁支异常（未处置，如实登记）

16:02 实跑守卫时读到：`🇨🇳 v8 中国数据抓取(云端·小九应急)` workflow 有 run **`in_progress` 已卡住 49 分钟**。
不属本次改动范围，未做处置。若持续卡住，需另行按「run 存活度巡检」判它是真在跑还是死掉占位。
