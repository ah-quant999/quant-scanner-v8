# v8 双机自动化上云评估与迁移计划（2026-08-08）

> 评估机器：阿狸咪（家里机）  
> 目标：尽量把生产/巡检类任务搬到 GitHub Actions，解放小九（单位机）和阿狸咪本地资源。

---

## 一、当前本机（阿狸咪）WorkBuddy 自动化清单

| ID | 名称 | 当前 schedule | 功能简述 | 迁移可行性 |
|---|---|---|---|---|
| 1784465134207 | 九宝量化-周六T+1新鲜度巡检 | 周六 09:30 | 跑 `t1_self_heal.py --email` | **可上云** |
| automation-1782763186274 | 阿狸咪-自动读取交接(10:00) | 工作日 10:00 | 读 `HANDOVER_*.md` 向主人汇报 | **必须本机**（文件本地） |
| automation-1782763195471 | 阿狸咪-自动读取交接(14:30) | 工作日 14:30 | 同上 | **必须本机** |
| automation-1782763209713 | 阿狸咪-自动读取交接(18:30回家) | 工作日 18:30 | 同上 | **必须本机** |
| automation-1783523003845 | 九宝量化-自动交接检查19:30(读小九交接) | 工作日 19:30 | 读小九交接文件并汇总 | **必须本机**（文件本地） |
| automation-1783696499491 | 阿狸咪-紧急指令监听 | 每 2 小时 | 监听 `URGENT_阿狸咪_*.md` 并 dispatch | **必须本机**（主人写本地紧急文件） |
| automation-1783744306577 | 九宝量化-周六T+1兜底 | 周六 08:30 | 小九掉线时接棒跑 `batch_update.py close` | **可上云**（云端兜底更可靠） |
| automation-1783744306764 | 九宝量化-周末轻量维护 | 六/日 19:30 | 跑 `batch_update.py weekend_light` | **可上云** |
| automation-1784448887937 | 数据新鲜度自动值守 | 每小时 | 跑 `data_freshness_watchdog.py` 自动修复陈旧数据 | **可上云**（改为 cloud self-heal workflow） |
| automation-1784816785584 | 阿狸咪-小九心跳监控+自动接管 | 每 30 分 | 检查小九心跳，掉线则启动本机救援 | **部分可上云**（监控逻辑可云，接管=dispatch workflow） |
| market_fund_flow_postclose | 九宝量化-长线资金流盘后计算+部署跟踪 | 工作日 18:35 | 跑 `fetch_market_fund_flow.py` | **可上云**（并入盘后算法链或独立 workflow） |

已删除的过期任务：
- `automation-1785768956292` v8_algo_run 复查-2026-08-03（一次性，已过期）
- `automation-1785943946699` 本机24点全部切回hy3（一次性，已 PAUSED/过期）

---

## 二、分类结论

### 1. 必须保留在本机（阿狸咪 detect + dispatch）

核心原因：依赖本地文件事件（主人写的交接/紧急文件）或本地通知通道。

- **紧急指令监听**（automation-1783696499491）：主人写 `URGENT_阿狸咪_*.md` → 本机检测 → dispatch 云端 workflow。**这是 AliMei 的核心职责，不能上云。**
- **自动读取交接**（10:00/14:30/18:30）与 **19:30 小九交接汇总**：文件在本地，汇报对象也是本机前的用户。如要完全上云，需把交接文件同步到云 + 用企业微信/邮件推送，改造较大。**建议保留本机。**
- **小九心跳监控+自动接管**：心跳检测可以上云，但「接管」动作（触发本机/云端救援）可以改为 dispatch 云端 workflow。建议保留一个轻量本机任务，仅做心跳检测 + dispatch。

### 2. 建议迁移到 GitHub Actions

这些任务不依赖本地桌面，本质上是定时数据生产/巡检。

| 任务 | 云上方案 |
|---|---|
| 周六T+1新鲜度巡检 | 新增 `.github/workflows/v8_t1_self_heal.yml`，周六 09:30 CST，跑 `python t1_self_heal.py`（脚本需从 v6 迁移到 v8 或重写） |
| 周六T+1兜底 | 并入上一条，或改为 `workflow_dispatch` 手动/条件触发 |
| 周末轻量维护 | 新增 `v8_weekend_light.yml`，周六/日 19:30，跑 `batch_update.py weekend_light`（脚本需迁移） |
| 数据新鲜度自动值守 | 扩展已有 `v8_safety_net.yml` / `v8_self_heal.yml`，增加每小时巡检 + 自动 dispatch 补跑 |
| 长线资金流盘后计算 | 扩展 `v8_algo_cloud.yml` 增加 18:35 步骤，或新建 `v8_market_fund_flow.yml` |

### 3. 需要先迁移的脚本

上述可上云任务依赖的脚本目前很多还在 `E:/workspace/stock-scanner`（v6）：

- `t1_self_heal.py`
- `batch_update.py`
- `data_freshness_watchdog.py`
- `fetch_market_fund_flow.py`
- `auto_handoff_read.py`（如交接读取要上云，需改读 `docs/ops/handover/`）

**建议顺序**：
1. 先把脚本复制/改写进 `quant-scanner-v8/`（去 v6 依赖）。
2. 新增/扩展 GitHub Actions workflow。
3. 本地 automation 改为 **PAUSED** 或删除，由云上 workflow 接管。
4. 观察 1-2 周稳定后，彻底删除本地 automation。

---

## 三、推荐立即实施的最小可行集（MVP）

如果不想一次性大改，建议先做这 3 步：

1. **把 `fetch_market_fund_flow.py` 并入 `v8_algo_cloud.yml`**（18:35 步骤），然后 PAUSE 本地 `market_fund_flow_postclose`。
2. **把 `v8_self_heal.yml` 从每周六 14:00 加密到每小时/每 30 分钟**，替代本地 `数据新鲜度自动值守`。
3. **保留 AliMei 的「紧急指令监听」+「交接读取」+「心跳监控」**，其余生产任务逐步上云。

---

## 四、风险

1. **脚本未迁移**：直接上云会导致 workflow 找不到脚本。必须先完成脚本去 v6 化。
2. **GitHub Actions 并发/排队**：如果每小时都跑新鲜度值守，可能和盘中 fetch 并发冲突，需设置 `concurrency`。
3. **通知通道**：云上 workflow 出问题后如何通知主人？建议用 GitHub Issues / 企业微信 webhook / 邮件。
4. **小九心跳监控上云后**，如果 GitHub Actions 本身也异常，可能无法检测。建议保留本机作为最后一道检测。

---

## 五、下一步行动

- [ ] 确认哪些脚本需要优先迁移到 v8 仓库。
- [ ] 确认是否接受「本地只保留紧急指令监听 + 交接读取 + 心跳监控」。
- [ ] 开始实施第一个云上 workflow（建议 market_fund_flow 或 T1 巡检）。
