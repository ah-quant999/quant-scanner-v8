# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-30 15:33｜ima连接器已绑定+shareId固化进fetch_chan_buy_point(勿丢)+访客分享范围观察

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

ima-mcp 连接器已绑定成功（主人 15:09 授权，面板 connected），高手 ima 分享 shareId 已按主人令「不要再弄丢了」固化进 `v8/fetch_chan_buy_point.py` 常量（commit `2fa30c25e3`）；今日 17:00 快照任务首跑＝连接器取全文真验证。

---

## 正文

### 1. 防丢三元组（真源 = 仓库 `v8/fetch_chan_buy_point.py` 常量，commit 2fa30c25e3）

| 项 | 值 |
|---|---|
| 知识库 KB_ID | `7500816604757970`（创建者 梧谷枫灯，库名「强势股跟踪」） |
| 水源文件夹 FOLDER_ID | `folder_7506360161825717`「缠论买点每日推荐」 |
| 分享 SHARE_ID | `32c01f1da52044f743a01e4aa995d72e7940cc8e99cf413cc5f4c2eb39b4d389` |

- 主人令（09-30）：「这个就是高手的ima，不要再弄丢了！」⇒ shareId 已固化进代码常量，**勿删除勿改动**。
- 分享链接：`https://ima.qq.com/wiki/?shareId=<SHARE_ID>`（主人 09-30 提供的原链接）。

### 2. ima-mcp 连接器绑定经过（阿狸咪家机）

1. 主人 15:09 完成授权，token 自动落 `~/.workbuddy/connectors/<acct>/connector-states.v3.json` 的 `headerOverrides.ima-mcp`（主线程日志：`updateHeaders(ima-mcp): C-side library auth detected, marking bound without changing enabled`）；
2. **只标 bound 不自动 enable** ⇒ 阿狸咪直改 v3 文件 `enabled` 数组补 `ima-mcp`（备份 `.bak_20260930_alimi`，主进程未回写覆盖）→ 连接器管理页显示 **connected**；
3. 会话工具注入为启动快照 ⇒ 已开着的会话仍调不到 ima 工具；**automation 开新会话即自动注入**。

### 3. 请小九复核 / 知悉

1. **勿动** `v8/fetch_chan_buy_point.py` 的 SHARE_ID/SHARE_URL 常量（防丢铁令）；
2. 今日 17:00 automation `149ad8ff`（ima 缠论买点全文快照）首跑：**这是连接器登录态取全文的真验证**。若报「文件夹不存在/知识库不可见」⇒ 高手端变更或订阅关系变化，如实上报主人，**禁伪造**；
3. 访客分享接口观察（09-30 15:20 实测，仅访客视角）：该分享公开范围 = 2 笔记 + 4 文件夹（短线情绪选股/短线情绪温度计/九型人格画像/月运合集），**未见**「缠论买点每日推荐」夹；活跃公开夹 = 「短线情绪选股」（09-30 当天仍在更新）。登录态能否看到缠论夹，以 17:00 首跑为准；
4. 连接器状态文件直改（enabled 数组）属应急手段，若后续 WorkBuddy 升级改变该文件结构，以连接器管理页 UI 为准，勿再手改。
