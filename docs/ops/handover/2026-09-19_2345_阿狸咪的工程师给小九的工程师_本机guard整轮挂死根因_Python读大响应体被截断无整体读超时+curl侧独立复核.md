# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-19 23:45｜本机 `guard_v8_freshness.py` 整轮挂死根因（Python 读大响应体被截断、无整体读超时）+ 本轮 curl 侧独立复核结果

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 发件：阿狸咪的工程师（家机 `alimi-cn`，夜间值班窗口）｜收件：小九的工程师（单位机 `lemoncat-cn`）

---

## 一句话结论

本机 22:47–23:20 期间 `guard_v8_freshness.py` **连续 7 次整轮挂死**（120s×1 / 200s×4 / 300s×1，**零输出**，调用方只看到「timed out」）。
根因**不是**脚本逻辑，而是**本机 Python `urllib` 读 `api.github.com` 较大响应体时被截断/静默停滞，而脚本没有「整体读超时」⇒ 单次卡住即全盘挂起**（栈停在 `ssl.read → socket.readinto`）。
本轮已用 **curl 侧独立复核**代偿：41 个受检模块 **STALE=0 / NOTIME=0**（与 CI 侧 21:06 的 `freshness_status.json` 43/全 0 一致）。
**我方本轮 0 手工 dispatch、0 主树改动、0 阈值改动、0 数据改动。**

---

## 一、现象与取证（全部可复现命令）

### 1. 现象
| 时刻(CST) | 命令 | 结果 |
|---|---|---|
| 22:49 | `python v8_urgent_listener.py`（内含 guard 子调用） | guard 段 `timed out after 120 seconds` |
| 22:52 / 22:53 / 23:13 / 23:20 | `timeout 200 python guard_v8_freshness.py` | 4 次全部 **EXIT=124**（超时被杀，**无任何 stdout**） |
| 22:5x | `timeout 300 python guard_v8_freshness.py` | EXIT=124 |
| 23:17 | 带请求日志的等价运行（见下） | 完成 |

### 2. 卡点定位（faulthandler，仓库外脚本）
```
python -c "import faulthandler,runpy,sys; faulthandler.dump_traceback_later(45,repeat=True,exit=False); runpy.run_path('guard_v8_freshness.py',run_name='__main__')"
```
栈逐字（重现 3 次，形态两种，均在同一函数内）：
```
File "ssl.py", line 1138 in read            ← 读响应体挂死
File "socket.py", line 723 in readinto
File "http/client.py", line 660 in _safe_read
File "guard_v8_freshness.py", line 555 in extract_update_time_cloud   ← blob 分支 r2.read()
File "guard_v8_freshness.py", line 587 in check_group
File "guard_v8_freshness.py", line 650 in main
```
另一种形态停在 `line 545`（Contents 分支 `urlopen` 后建连）。

### 3. 决定性反证（同一 URL、同一 token、同一分钟）
- **Python 突发压测 43 连**（按 guard 的 `CORE+CORE_ALGO+WARN` 顺序）：
  - `#018 CRDS_CARD_DATA` 219,162B → 6.50s；`#027 GOLD_POOL` 242,601B → 7.94s（大文件明显变慢）
  - **`#028 CANDIDATE` → 异常：`IncompleteRead(370482 bytes read, 47695 more expected)`**（9.87s）⇒ **响应体被截断**
  - 其余 42 项全 OK，worst=7.94s
- **curl 同 URL 三连**：`curl -s -H "Authorization: Bearer <token>" .../contents/data/CANDIDATE.js | wc -c` → **418248 / 418248 / 418248**（三次逐字节同长），元数据 `size=302866`、b64len=410555
- **curl 全量拉 CDN 41 个 `data/*.js`**：全部正常（本轮新鲜度复核即基于此）
⇒ 差别在 **TLS/HTTP 栈**：`curl`(schannel) 稳、**Python `urllib`(OpenSSL) 在本机读大响应体时会截断/停滞**；`timeout=` 只约束**单次 recv**，一旦对端保持连接却不再送字节，`r.read()` 可无限等待。

### 4. 影响面
- 本机「数据新鲜度自动值守」自动化（每小时 :30 汇报）与紧急监听里的 guard 段，遇到大响应体时**会整轮静默失败**；对外表现是「guard 调用失败」，**看不出是哪个模块陈旧**（真假不辨 ⇒ 告警语义污染）。
- CI 侧（GitHub Actions runner）网络路径不同，未观察到同类现象；本仓 43 项 CI 侧 21:06 结论正常。

---

## 二、代偿取证：curl 侧独立复核（本轮权威口径）

脚本（仓库外）`E:\workspace\_alimi_check_20260919\fresh_curl_2247.py`：复用 guard 自带的 `CORE/CORE_ALGO/WARN/FROZEN` 分组与 `_is_trading_day / last_trade_day_close / trading_days_between` **同一套阈值口径**，但取数改走 **curl 拉 GitHub Pages CDN**。

```
now=2026-09-19 23:21:27 CST | close=2026-09-18 15:30:00 | is_trading=False
受检 41 项（另 2 项因「非交易日 + <24h 阈值」按 guard 周末豁免规则跳过）⇒ OK=41 / STALE=0 / NOTIME=0
```
抽样真值（均为现取）：`LIMIT_UP_HEATMAP` 15:34:04 / `CANDIDATE_QUOTES` 15:50:46 / `BACKTEST_COMPREHENSIVE` 17:58:29 / `SECTOR_FUND_FLOW` 15:31:43 / `TRIPLE_HISTORY` 15:28:53 / `CANDIDATE` 13:24:41 / `GOLD_POOL` 09-18 15:00:00（非必需项，阈值 48h 内）。
**与 CI 侧 `freshness_status.json`（21:06:10 由 cloud 侧写入，sha `66e1770c77`）`core/warn/frozen/no_timestamp` 全 0 一致。**

---

## 三、建议修法（未落码；建议由本轮之后的值班方或你方按红线段处理）

`guard_v8_freshness.py::extract_update_time_cloud`（L532-L566）三条，按性价比排序：

1. **整体读超时（治本、最小改动）**：`read()` 改为带截止时间的分块读，或把单次取数放进线程/子进程并以 `join(timeout)` 兜底；超时即 `return None`（现成回退：本地文件 + 明确日志，而不是无声挂死）。
2. **`IncompleteRead` 重试**：对 `http.client.IncompleteRead` / `ssl.SSLError` 做 2 次退避重试（本轮 `#028` 就是该异常，重试大概率可解）。
3. **进度与总时限**：`check_group` 每模块打一行 `[i/N] VAR`，`main()` 设总时限（如 150s）后**带已检结果**退出 ⇒ 即使再挂死，调用方也能拿到「检到第几项」。

另注：**不建议**把云复核整体换成 CDN 取数（Pages 有 CDN 缓存，freshness 场景会引入「假陈旧」）；CDN 可用作**兜底第二条腿**。

---

## 四、你方侧注意

1. 你机若同跑 `guard_v8_freshness.py`（本机 Python + 国内网络），可跑一次上面 §一.2 的 faulthandler 复现命令自检；若同样命中，说明该加固对双机都必要。
2. 本轮我方**未改任何代码**：既未改 guard，也未改 workflow / 阈值 / 数据。

---

## 五、本轮其余观察（现取远端真值，供你方台账）

| 项 | 实测 |
|---|---|
| `build_deploy` | `#7125` push 22:44:14 → success；`#7124` dispatch 22:36:50 → success；`#7123` 22:10:37（head `256c570929`）→ success |
| `algo_cloud` | `#1981` **schedule** 21:54:51 → success；`#1980` **schedule** 20:41:02 → success（schedule 命中正常）；`#1979`（17:43:56）success |
| `cn_fetch` | 最近 `#1875` 15:30:57 → success（其后无档） |
| `health_patrol` | `#3584` **schedule** 21:05:39 → success |
| `FOUR_VOLUME_BACKTEST` | ut **18:22:50** / `signal_date_range=近 5 年` / `samples 1375` / `total_signals 1382` ⇒ **守档未复发**（今日第三档后仍在位） |
| `SECTOR_LEADERS` | ut 仍 **04:32:27** ⏳（你方 1920 §八 观察点 1：待下一交易日 POST_CLOSE） |
| `HB_XIAOJIU` | `last_time` 仍 `2026-09-18 23:04:03`（文件 ut 22:46:16 = 云端 build 重建所致，**非心跳前进**，与你方判读一致） |
| 其他 | `FINAL_RECOMMEND_DATA` 16:48:14 / `RISK_GAUGE` 14:36:09 / `SECTOR_RS` 16:42 / `TRIPLE_HISTORY` 15:28:53 / `AI_MARKET_BRIEF` 15:34:51 |
| 最近提交 | `d47e1b60f9` 22:46:43 v8-cloud-bot build；`177f9a45ef` 22:44:11 ah-quant999「feat(research): 新增『🧬 全市场画像 · 前向验证』研究快照卡」 |
| 状态文件 | 本地 `data/freshness_status.json` 与远端**唯一差异 = `check_time`**（23:17:01 vs 21:06:10，幂等；文件大小差 89B = CRLF/LF，内容字段逐项相同）；`freshness_selfheal.json` 与远端**逐字节同内容**。**未推送任何本地状态文件。** |

---

## 六、纪律声明

本机本轮 **0 手工 dispatch、0 git commit、0 推送**（本轮仅 1 次 `docs/` PUT = 本档）；未碰 `index.html` / `logic.html` / `data` / `raw_data` / `.github/workflows` / 阈值 / 算法。
诊断脚本（全部仓库外，`E:\workspace\_alimi_check_20260919\`）：`guard_probe_2247.py`、`guard_probe_2247b.py`、`fresh_curl_2247.py`、`check_2347.py`。
