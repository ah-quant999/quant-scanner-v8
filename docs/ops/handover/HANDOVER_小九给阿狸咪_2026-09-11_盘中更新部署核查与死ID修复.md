# 交接单：小九(白班) → 阿狸咪(夜班/周末) · 2026-09-11 盘中更新部署核查

> 署名：小九的股票专家 ｜ 交班时刻：2026-09-11 约 15:50 CST ｜ 接班：阿狸咪 18:00 起

## 一、本班结论：盘中更新部署 ✅ 已全部修复并上线

今天盘中更新部署**唯一未修复的部署级 bug** 已定位并根治：

- **病灶**：派发入口 `v8_dispatch_fetch.py` 仍指向**已删除的 workflow `324135267`**（旧 `v8_cn_fetch.yml`，已重构删除）。
- **后果**：任何 on-demand 派发 / 看门狗自愈都打到不存在的 workflow → **盘中更新自愈合失效**（基础定时抓取不受影响，但异常时无法自动重触发）。
- **修复**：3 个脚本的死 ID 全部重定向到现存活 workflow，已 push main（merge commit `292065678`）。

### 实证（用实时说话，非推测）
| 校验项 | 结果 |
|---|---|
| `api/actions/workflows` active 列表 | `324135267` **不在**；`327687211`=v8_cn_fetch_cloud(云端主力)、`336661558`=v8_cn_fetch_cloud_selfhosted(小九应急)、`324833339`=v8_algo_run(self-hosted 算法链) |
| 今日 git log | 15:xx 仍有 `v8 cn fetch` / `v8 build` 提交 → 盘中数据管线下午持续产出（活跃 job 创建于早盘、长运行持续 commit） |
| 本机 self-hosted runner | 15:37 仍在跑 `fetch_sh_index_fib.py`（algo_heartbeat 实测 `status=running`, pid 19020） |
| 安静窗守卫 | `v8_dispatch_fetch.py:52` `_QUIET_WINDOWS=[(9,20)-(11,30),(12,50)-(15,0)]` 已 live，交易时段非 intraday 派发自动 no-op |
| 修复后 main 核验 | `v8_dispatch_fetch.py` WF_IDS 全 `327687211`；`v8_postclose_guard.py` `WF_FETCH_CN=336661558`；`v8_runner_guard.py` `SELFHOSTED_WORKFLOW_IDS=[336661558,324833339]`（无 324135267）✅ |

## 二、今日已上线修复汇总（本班 + 早班，均在 main）
1. **9 张红灯卡**（孤儿脚本挂链 + 闸门 READY_SPEC 扩容 + dedup 白名单 + 跨层闸门方向/时段双判）— 早班根治。
2. **盘中安静窗铁律**（派发入口守卫，任何窗内非 intraday 派发 no-op）。
3. **6 死数据 / 死功能清理**（FRESHNESS_STATUS 修复、probe_algo_cloud 删除、ALLSITE/COCKPIT 残留注释清理）。
4. **本班**：派发/守护脚本死 ID 重定向（commit `292065678`）。

## 三、⚠️ 待主人拍板 3 项（我问过、尚未回复）
① **哨兵类自动化是否限交易安静窗？**
   候选：`ad288000`(断档告警) / `automation-1786961773708`(自愈监控) / `automation-1786696074524`(runner守护)。
   我建议【保留不限窗】——属盘中健康基础设施，暂停=盘中失明。等主人确认。

② **ETF「行业 TOP5」分类 bug 是否修？**
   `calc_etf_intraday.py` 把**货币/宽基/债券** ETF 误归「行业」：银华日利(511880)+1.77亿、华宝添益(511990)+0.65亿、政金债(511520)+0.41亿、城投债(511220)+0.36亿、中证2000ETF(563300)+1.01亿。
   真实行业资金 TOP5：通信设备 +27.1亿 / 被动元件 +25.3亿 / 通信 +24.2亿 / 元件 +22.1亿 / 通信网络设备及器件 +20.8亿。
   是否修分类口径并把真行业 TOP5 写入 AI_MARKET_BRIEF？

③ **盘前速览卡升级（悬而未决）**
   主人曾发截图要"读图升级这张卡"，但本会话不支持读图；需主人用**文字标注**要改的点（或选方案 A/B/C），否则无法动手。

## 四、双机交接要点
- 小九白班 7:45–17:45 收工；阿狸咪 18:00 起夜班/周末接手。
- 本机自动化（小九侧）：westock 持仓同步已改期到 **12:00 / 15:00 / 16:00 / 19:00**（避开安静窗）。
- 阿狸咪侧自动化应仍为 **PAUSED**（双机铁律），恢复 ACTIVE 需主人明令。
- 推送用 **SSH/22**（HTTPS/443 连 GitHub 超时）；本机有自动化定期 `git reset --hard origin/main`，改动务必即时 commit+push。

## 五、风险提醒（接手前必读）
- 本机工作树常"幽灵落后"，接手前先 `git fetch && git merge --ff-only origin/main`。
- `raw_data/` `data/` 是管线产物，**以远端为主**；本地脏数据直接 `git checkout --` 丢弃，勿手推覆盖（会被 CI 下次 build 洗回）。
- 判"有没有推上去"永远以 `git merge-base --is-ancestor <sha> origin/main` 为准，不以本地 push 退出码为准。
