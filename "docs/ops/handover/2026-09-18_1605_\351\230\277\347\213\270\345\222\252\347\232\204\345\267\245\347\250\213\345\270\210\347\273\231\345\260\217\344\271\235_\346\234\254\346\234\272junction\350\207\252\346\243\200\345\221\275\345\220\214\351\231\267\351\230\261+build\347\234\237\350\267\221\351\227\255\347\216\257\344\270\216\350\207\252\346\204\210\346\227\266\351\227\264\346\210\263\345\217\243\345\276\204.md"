# 交接档 · 阿狸咪的工程师 → 小九的工程师

**撰写人**：阿狸咪（夜间/周末班 · 家机，`alimi-cn`）
**撰写时刻**：2026-09-18 16:05（北京时间 CST+8，盘后）
**批次主题**：① 你 `1500` 档 §8「阿狸咪机须自行复核 junction」的复核回执 ② 你 `0930` 档 P0 门禁修复的**端到端闭环实证**（15:22 build job 真跑） ③ 一处小口径：自愈状态文件 `ts` ≠ 派发时刻
**本轮性质**：只读取证 + 本档 1 次 Contents API PUT。**0 本机 git commit / 0 手工 dispatch / 0 数据改动。**

> 本档不写自身所在提交 sha（写死即过期）。需要时按 §二 命令现取 tip。

---

## 一、§8 junction：本机（阿狸咪）命中**同一陷阱** ✅ 已复核

按你 §8.5 给的判据（`os.stat(..., follow_symlinks=False)` + `FILE_ATTRIBUTE_REPARSE_POINT`）自查：

| 路径 | 是否 junction | 真实实体落盘 |
|---|---|---|
| `C:\Users\HH20210606\.workbuddy` | **是** | `\\?\E:\.workbuddy` ⇒ **E 盘** |
| `C:\Users\HH20210606\qs8-tmp` | 不存在 | — |
| `C:\Users\HH20210606\WorkBuddy` | 否 | 实体在 C 盘 |
| `E:\workspace\stock-scanner` | 否 | 实体在 E 盘 |

**结论**：本机若清 `C:\Users\HH20210606\.workbuddy`（会话日志 / 缓存 / skills），**释放量全进 E 盘，C 盘纹丝不动** —— 与你机 `C:\Users\Administrator\.workbuddy → E:\workbuddy-data` 是同型陷阱。你 §8.4 铁律 1 对本机同样成立。

### 新增一条本机专属红线（请勿在合并白名单时误纳）

本机 `~/.workbuddy` **就是凭证存放点**：`C:\Users\HH20210606\.workbuddy\v8_gh_pat` 与 `v8_gh_token.txt` 实体在 `E:\.workbuddy\`。
⇒ 任何白名单 / 清理规则**必须显式排除** `\.workbuddy\v8_gh_pat` 与 `\.workbuddy\v8_gh_token.txt`，否则会清掉双机共用的推送凭证。

### 三盘真值（2026-09-18 16:00 CST 实测，属性名访问 + 自检 `|used+free-total|<1e9` 全 True）

| 盘 | total | used | **free** |
|---|---|---|---|
| `C:\` | 126.28 GB | 92.31 GB | **33.97 GB** |
| `D:\` | 161.13 GB | 65.14 GB | **96.00 GB** |
| `E:\` | 177.68 GB | 62.64 GB | **115.03 GB** |

本机 C 盘 33.97 GB 可用，**暂无告警**，本轮未做任何清理动作。

### 你 §7 第 2 条的复核

`C:\Users\HH20210606\.workbuddy\scripts\` **不存在**（`ls` 实测 No such file or directory）⇒ 本机既无同名脚本、也无照搬路径，与你机 `C:\Users\Administrator\.workbuddy\scripts\disk_clean_weekly.py` 无冲突。

---

## 二、你 `0930` 档 P0（B 批头注 9→12）**端到端闭环实证**

判据严格按你我都认的口径：**看 `build job` 真跑结论，不看 run 结论**。

| run | 创建(CST) | event | `build` job |
|---|---|---|---|
| `#35319080350` | **15:22:08** | push | **completed / success**（start 15:22:20） |
| `#35319968375` | 15:33:11 | workflow_run | completed / cancelled |
| `#35320330189` | 15:37:38 | workflow_run | completed / cancelled |
| `#35321620439` | 15:53:26 | workflow_run | in_progress |

⇒ **收盘后（15:00 之后）首个 build 真跑 = `#35319080350` success**。你 `3c5bbea90d`（09:59）修 L50 头注项数后，门禁对「**非交易时段 → 真跑 build**」这条路径**端到端成立**。
后两条 `cancelled` 属并发组顶替（已知家族，非新问题）。

---

## 三、一处小口径（仅告知，未改码）

`guard_v8_freshness.py` **L627** `now = (datetime.now(timezone.utc) + timedelta(hours=8)).replace(tzinfo=None)` 在 `main()` **开头**捕获；
`_heal_cn` / `_heal_algo` / `_heal_stock_quote` 落 `data/freshness_selfheal.json` 的 `ts` 用的就是这个 `now`，**不是 HTTP POST 时刻**。

**实证（本机本轮）**：

```
data/freshness_selfheal.json
  "post_close": { "ts": "2026-09-18 15:50:30", "vars": ["VOLATILITY"] }
  "algo": { "ts": "2026-09-18 15:50:30", "vars": ["CRDS_CARD_DATA"],
            "note": "skip: active run #35321315178 (in_progress)" }
```

而 workflow `327687211`（`v8_cn_fetch_cloud.yml`）同窗 runs 为：`#35321312858`(15:49:38 in_progress) / `#35321432706`(15:51:04 pending) / `#35321743745`(15:54:58 pending) / `#35321778229`(15:55:23 pending) —— **四条互顶**。

⇒ 结论两条：
1. **`ts` 不能当「派发时刻」用**（冷却是安全的 —— 偏早计时 = 更保守，不会多派；但排查 run 对应关系时勿拿它对表）。
2. 本条**不构成新根因**，我不把 `[自愈✓] HTTP 204` 判成假成功 —— **派发源不可区分（两机共用同一 PAT），我不做归因**。

### 同轮 algo 自愈被「先查再派」跳过，而该活跃 run 是空转

`#35321315178`（15:49:39 CST 派发 → 15:53:24 结束）step 明细：
`step 8 批次闸门 = success` → **`step 9~16 全部 skipped`**（含「运行盘后算法链」「唯一推送」）→ `step 17 结果问责 = success`。
⇒ 又一次「**派发成功 ≠ 刷新成功**」的实证；`CRDS_CARD_DATA` 因此**未刷新**（见 §四）。

---

## 四、云真值（2026-09-18 15:50–16:00 CST · 全部只读、经 Contents/Blobs API）

- **tip** = `1f4223a05284`（15:49:40「v8 healthcheck: 2026-09-18 15:49」）；另有 `d01359f827`（15:56:21 你档 §8 补遗）
- 🔴 `data/VOLATILITY.js` ut **2026-09-17 18:33:59**（1,887 B）⇒ **真陈旧**（guard CORE 命中成立）
- 🔴 `data/CRDS_CARD_DATA.js` ut **2026-09-17 20:00:04**（143,719 B）⇒ **真陈旧**（同上）
- ✅ `data/FOUR_VOLUME_BACKTEST.js` = **1447 / 近 5 年 / 07:11:01** ⇒ **未再退化到 3 年档**（连续第 3 轮守住）
- ✅ `data/BACKTEST_TDX.js` 06:57:48 · `data/RISK_GAUGE.js` **14:52:48** · `data/LHB_DATA.js` 15:15:58 · `data/AI_MARKET_BRIEF.js` 15:14:26
- ✅ 盘中簇 15:03–15:42 新鲜：`SECTOR_RS` 15:16 · `ETF_INTRADAY_HEAT` 15:03:50 · `STOCK_QUOTE` 15:08 · `INDEX_QUOTES` 15:04:58 · `SECTOR_FUND_FLOW_INTRADAY` **15:42:15**
- ✅ **风险温度计链（`325900070`）第三次复发后未再复发**：`#493` 11:06 failure → `#494` 12:09 ✅ → `#495` 13:11 ✅ → `#496` 14:12 ✅ → `#497` 14:52 ✅（截至 16:00，0 次新增失败）

---

## 五、本轮纪律与复核命令

**0 本机 git commit / 1 次 Contents API PUT（仅本档）/ 0 手工 dispatch**；未碰 `index.html` / `logic.html` / `data`（内容）/ `raw_data` / `.github/workflows/**` / 任何阈值。

```bash
# 现取 tip（不写死 sha）
TOKEN=$(cat ~/.workbuddy/v8_gh_pat); curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/ah-quant999/quant-scanner-v8/branches/main | python -c "import json,sys;print(json.load(sys.stdin)['commit']['sha'][:12])"

# 本机 junction 自检（复跑口径）
python -c "import os;FA=0x400;p=r'C:\Users\HH20210606\.workbuddy';print(bool(os.stat(p,follow_symlinks=False).st_file_attributes&FA), os.readlink(p))"

# 三盘真值（属性名访问，勿按位置解包）
python -c "import shutil;[print(d, round(shutil.disk_usage(d).free/2**30,2)) for d in ['C:\\','D:\\','E:\\']]"
```

**下轮我方优先**：① 上表两条真陈旧（`VOLATILITY` / `CRDS_CARD_DATA`）是否被刷 ② 四量下次 algo 落盘是否仍守住近 5 年档 ③ `BACKTEST_TDX` E 批饿死修复后是否恢复日更。
