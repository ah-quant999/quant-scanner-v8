# HANDOVER｜小九的工程师 → 阿狸咪的工程师｜2026-09-30 18:10｜SECTOR_LEADERS 东财全host断连断供根治（缓存+腾讯兜底已上线，待今晚 run 验证）

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 性质：跨机结构性变更告知（你今晚的 cn_fetch / 盘后链 run 会消费新脚本）——**无需任何操作**。

## 一句话

「暂未上架 > 主升/启动·龙头股」卡断供 2 天的根因 = 东财 push2 对**云端与本机 IP 全 host RemoteDisconnected**（algo_run_report 09-30 16:49 A批 fail=2 实证），旧脚本 `fetch_em_boards()` 不在保护块 ⇒ 整脚本退出 1 ⇒ dict 停在 09-28 ⇒ 今日 2 个启动板块（小金属/风电设备）龙头股位全空。**修复已上线 commit `500ca2a744`，向后兼容，你无需改任何配置。**

## 已上线改动（500ca2a744）

| 层 | 改动 |
|---|---|
| `scripts/fetch_sector_leaders.py` | ① 板块名→BK 映射缓存 `raw_data/em_boards_cache.json`（成功轮全量回写，随 git 跨日累积；东财全断回退缓存，**永不 raise**）② 成员名单缓存 `raw_data/em_members_cache.json` ③ `fetch_cons_safe` 东财两轮全断后走**腾讯 qt.gtimg 批量行情兜底**（与 fetch_us_hk_map 同源，云端已验证可达）④ 产物新增 `em_boards_source`（live/cache/unavailable）审计字段。本机 17:58 实测：东财全断路径 rc=0、产物照写、板块结构保留（no_match 明示），不再退出 1 |
| `index.html`（_fillSectorLeaders） | 「没龙头股」从三态改**四态明示**：新增「东财接口本轮受限（读 em_boards_source=unavailable）」与「本轮新晋板块（in_dict=false）」两态，不再误报「不在抓取名单」 |

## 请你知悉 / 明早验证（verify_how）

1. `data/SECTOR_LEADERS.js` 的 `data_date`/`update_time` 是否恢复日更（当前停 09-28）；
2. `raw_data/em_boards_cache.json` / `em_members_cache.json` 是否出现并逐日累积（东财恢复后自动回写）；
3. `algo_run_report.json` 的 failed_scripts 是否不再出现 `scripts/fetch_sector_leaders.py`；
4. 若东财持续断连：卡面应显示「东财接口本轮受限」黄条而非消失——这是**设计行为**（结构不断供），老板块龙头股由腾讯兜底出（需成员缓存已有，冷启动首日可能仍缺，属预期）。

## 边界声明

- 未动 `v8_stage_gate.py` 问责清单（A 批问责未覆盖此产物是假绿成因之一，但改问责表有全链假红风险，留给主人拍板是否补口）；未动 workflow 文件（PAT 403 红线）；未动任何取数口径。
- 本推送经净室推送器（expect-base 断言 + 回读逐字节自验 ✓），18:07 落仓，若与你 18:00 后的链有基线碰撞以远端为准重放即可。
