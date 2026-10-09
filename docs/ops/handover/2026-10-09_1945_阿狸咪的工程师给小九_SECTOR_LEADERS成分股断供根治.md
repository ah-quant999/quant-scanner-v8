# 交接件：SECTOR_LEADERS 成分股断供根治（东财断连日四层兜底全断）

- **时间**：2026-10-09 19:45（北京时间，阿狸咪夜班）
- **署名**：阿狸咪的工程师（家机 alimi-cn）
- **触发**：主人 19:31 截图「主升/启动 板块·龙头股 卡成分股全—，又挂了」
- **修复提交**：`31b975843a`（fix(sector_leaders): 成分股断供根治——名单缓存入仓 + NeoData token 接电）

## 一、现象

9 个主升/启动板块（风电设备/油气开采及服务/银行/电池/港口航运…）**全部** `no_match=1、leaders=[]、cons_count=0`，卡面成分股位显示「—」+ 黄框「东财接口本轮受限」。`em_boards_source=unavailable`、`neo_fallback=0`、`retained=0`。

## 二、根因链（全部实测举证，非推断）

东财 push2 全家族断连（**09-30 / 10-01 / 10-09 三次复发**；阿狸咪 19:32 家机直连实测 `RemoteDisconnected` 仍断，`quote.eastmoney.com`/`datacenter-web` 可达、push2 家族全断）→ 四层兜底逐层验尸：

| 层 | 设计 | 实况 | 结论 |
|---|---|---|---|
| ① 东财在线 | 换 host 池重试 | 全 host RemoteDisconnected | ❌ 断连 |
| ② 名单缓存 | `raw_data/em_boards_cache.json` 回退、**随 git 跨日累积** | 该两文件**从未存在于 main**（`git/trees` 实证）；云端 runner 每轮新容器、本地缓存永不建立 | ❌ 断供（设计意图从未兑现） |
| ③ 腾讯行情 | members 缓存 + `qt.gtimg.cn` | 腾讯行情本机实测 ✅可达，但 members 缓存不存在 ⇒ 无名单可兜 | ❌ 上游连坐 |
| ④ NeoData | `_neo_cons` 兜底（10-01 建） | repo secrets 实测只有 MAHORO_COOKIE/V8_GH_TOKEN/ZSXQ_TOKEN，**NEODATA_TOKEN 从未配置**（10-05 只预留了 env 口）；本机 token 缓存 93h 前已过期、接口实测 401 | ❌ 无 token |

叠加：今天 17:07/17:55/18:25/19:24/19:34 五轮 cn fetch 全空 ⇒ 同日保底锁（10-05 建）无好名单可过继 ⇒ 空名单逐轮落仓。**云端无 token 的空名单洗回在 10-05 已修（保底锁），本次是新洞：缓存从未入仓 + token 从未接电。**

## 三、修复内容（`31b975843a`，Git Data API 实时 tip + force:false，推后回读自证 ✅）

1. **名单缓存入仓 bootstrap**：`raw_data/em_boards_cache.json`（496 板块，10-05 快照，含 风电设备=BK1032）+ `raw_data/em_members_cache.json`（3 板块成员）。两文件不在 .gitignore（已验证）。云端此后 checkout 即有名单，东财断连日走「BK 码解析 → 成员缓存 + 腾讯行情」主兜底链（**不依赖任何 token**）。
2. **NeoData token 接电**：workflow `v8_cn_fetch_cloud.yml` soft_13b 步加 `env: NEODATA_TOKEN: ${{ secrets.NEODATA_TOKEN }}`（锚点替换、远端 LF 基线、锚点唯一性断言）；repo secret 已用 PyNaCl sealed box 配置。
3. **本机 token 刷新**：`algorithms/.neodata_token`（gitignore 保护 ✅）+ `E:/.workbuddy/skills/.neodata_token` 已写入新 token（NeoData 接口实测 suc=True，风电设备成分可取）。
4. **验证**：已 dispatch post_close 档 cn fetch 验证轮，后台终验判据=风电设备 leaders 非空 / match 含 neodata。

## 四、已知边界（如实告知，不粉饰）

- **NeoData token 12h 过期**：过期后云端第④层兜底再失效。但主兜底链（缓存+腾讯）不依赖 token；token 只服务「板块名在东贓名单真缺失」的别名场景。token 刷新依赖阿狸咪家机（WorkBuddy 会话凭证），小九机无法自助刷新。
- **members 缓存现仅 3 板块**：其余板块断连日走 NeoData（token 活着时）或 `leaders_error` 黄框明示待补。东财恢复后的成功轮会按板块逐轮回写 members 缓存（仅主升/启动板块），随 git 累积、越攒越厚。
- 未改任何取数口径/排序/阈值；前端零改动。

## 五、给小九的注意点

- 本修复与今晚 19:25 盘后算法链无路径冲突（scripts/cache/secret vs 运行中链的 data/raw_data 推送）。
- 明日起若卡面再出「东财接口本轮受限」黄框，属正常降级明示（接口断连日），成分股应随兜底链自动补上；若连续 2 轮 leaders 全空且 `em_boards_source=unavailable`，说明缓存文件被意外删除/覆盖，按本件第三节重推。
- 19:25 算法链链尾推送步「无独立盘中守卫」盲区仍挂账（昨日已挂），与本件无关，勿混淆。
