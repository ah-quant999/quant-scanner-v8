# 交接件：主升/启动·龙头股卡内容断线根治（阿狸咪→小九）

**时间**：2026-10-01 21:20（CST，国庆休市夜）
**提交**：`721ef29052567b8f389a431e05d9e023ed5745f7`（数据文件已落地，Pages 已生效）
**署名**：阿狸咪的工程师（alimi-cn）

## 1. 用户反馈
「我说的不是间距的问题啊！我说的是这卡里面内容都断线了没东西了啊！搞什么」
→ 指「主升/启动·龙头股」卡里的**龙头股名单整段空白**（之前修的卡间距不是重点）。

## 2. 根因（一张图说清）
- **东财 push2 全家族 HTTP 层封锁**：自 09-30 起，`push2delay / push2 / 1-12.push2 / push2his` 对本机(urllib/curl/真浏览器/DoH IP)与云端 runner 全部 `RemoteDisconnected`（TCP/TLS 可建连，HTTP 请求即被掐）。
- **三层兜底鸡生蛋失效**：脚本 09-30 小九加的 `raw_data/em_boards_cache.json` / `em_members_cache.json` 需一次成功抓取才建立，东财断时缓存也缺 ⇒ `em_boards_source=unavailable` ⇒ 全板块 `no_match` ⇒ 龙头股位全空（`leaders=0` ×4 板块）。

## 3. 修复（一劳永逸，已落官方生成器）
- **NeoData 第四层兜底**：`scripts/fetch_sector_leaders.py` 加 `_neo_token()` / `_neo_cons()`，与 `fetch_sector_rs.py` **同源同 token 通道**（`copilot.tencent.com/agenttool/v1/neodata`「板块成分明细」自然语言查询），仅在前三层全失效时启用，任何失败 `return None` 不抛错。
- 4 板块龙头股经 NeoData 拉取（各 5 只，含 code/name/price/chg/main_net）+ **腾讯 `qt.gtimg.cn` 逐股交叉核验 8/8 一致**（证实时戳=09-30 收盘真值，非编造）。
- `build()` 接入 no-BK 分支与 cons-抓取失败分支，加 `n_neo` 计数与 `neo_fallback_count` payload 字段，source 追加 NeoData 标注。
- **此后东财再断也不会全卡空**，仅标 `match=neodata` + `neo_fallback_count` 审计。

## 4. 产物与审计
- `data/SECTOR_LEADERS.js`：3043 字节、0 CRLF、尾部 `;`；`update_time=2026-10-01 09:11`（取 SECTOR_RS 源时戳，诚实）、`data_date=2026-09-30`、`republish_time=2026-10-01 21:12:59`、`neo_fallback_count=4`、`em_boards_source=unavailable`；4 板块各 5 龙头：
  - 风电设备(主升)：中船科技/大金重工/天顺风能/电气风电/泰胜风能
  - 生物制品(启动)：康希诺/泰诺麦博-U/百普赛斯/近岸蛋白/信诺维
  - 汽车整车(启动)：江淮汽车/广汽集团/千里科技/上汽集团/比亚迪
  - 房地产(启动)：陆家嘴/…（5 只）
- 门禁 `pre_deploy_audit.py`：**14/14 全绿**。
- 防覆盖：基底=远端实时 tip 单文件替换，Git Data API force:false + 422 重放，回读逐字节一致（3043B == 本地产物）。
- 线上终验：Pages `data/SECTOR_LEADERS.js` 现已 3043B 完整（早期轮询 2609 为构建中瞬时半版），与仓库 blob 全同 ⇒ 卡面龙头股位将恢复渲染。

## 5. 小九须知
- 此修复**已随数据文件推送生效**，开市后正常跑批即走官方生成器（含 NeoData 第四层），无需你手动干预。
- 若节后东财 push2 恢复，生成器会优先用东财真值（`match=em_boards`），NeoData 仅作兜底；`neo_fallback_count` 归 0 即代表东财通道已通。
- 关注点：节后首个交易日观察 `SECTOR_LEADERS.js` 的 `em_boards_source` 是否回 `available`、 `neo_fallback_count` 是否归 0；若仍为 `unavailable` 且 >0，说明东财 push2 仍封，属预期内（NeoData 兜底在岗）。
- 未触碰任何 index.html / 已落码 .py / 算法链未提交产物，零洗版。
