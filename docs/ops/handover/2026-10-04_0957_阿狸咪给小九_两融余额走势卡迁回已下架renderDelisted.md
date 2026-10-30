# HANDOVER｜阿狸咪 → 小九｜2026-10-04 09:57｜两融余额走势卡迁回「🔒 已下架」renderDelisted（主人令纠正 10-03 无主令擅迁）

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

主人 10-04 截图实锤：「两融余额走势」卡不该出现在「🌍 观测平台 > 📊 大盘观测」下方，它归属「🔒 已下架」页。根因是 10-03 提交 `92628b37b5`（阿狸咪无主令擅迁）把该卡从已下架误迁大盘观测。已按主人令**迁回**「🔒 已下架」renderDelisted，并修复了回迁时引入的 logic.html 行尾脏 diff（CRLF 翻 LF）。已快进推送 origin/main（未覆盖他人 build 戳），线上实测两融卡已在已下架页、大盘观测下方归零。

---

## 正文

### 根因链（实锤）

1. 截图文案：两融余额走势卡出现在大盘观测底部 ⇒ 与主人既定归属「🔒 已下架」冲突。
2. 历史：该卡原在已下架页 renderDelisted（绘制 `drawV8MarginChart()` 读 `window.V8_MARGIN_DATA`）。
3. 10-03 提交 `92628b37b5`「fix(观测平台): 两融余额走势卡真迁大盘观测 + 清MAHARO_MACRO孤儿引用」由阿狸咪**无主令擅迁**（基于「卡已在观测平台」的错误前提，且当时未同步改 v8_health_check.py 的 MARGIN_DATA 归属）。
4. 10-04 主人令纠正：迁回已下架页。
5. 回迁过程中补丁脚本用 `io.open(text)` 把 logic.html 整文件翻成 LF，但 `.gitattributes` 规定 `logic.html -text -eol`（二进制锁 CRLF）⇒ 产生 17636 行脏 diff（commit `2b7c66adbd`）。本次在 `f4738058e5`（10-04 09:38 build，已含两融内容+最新 `?v=` 戳）之上仅把行尾翻回 CRLF 收口。

### 修复内容（推送链）

```
8eb631a9 (原 tip)
  └─ 2b7c66adbd  fix(两融卡): 由大盘观测迁回已下架 renderDelisted（内容正确，但 logic.html 行尾被翻 LF）
       └─ f4738058e5  v8 build 09:38（?v= 戳刷新，逻辑详解/指数等，未触两融区域）
            └─ 81712d727e  fix(logic.html): 恢复 CRLF 二进制（收口脏 diff，净 diff 仅行尾）
```

三文件改动要点（相对原 tip `8eb631a9` 净 diff 全部为两融回迁 + 行尾修复，无其它）：

- **index.html**：
  - `_PAGE_CARD_ORDER`：`MARGIN_DATA` 由「观测平台」组移回「盘后数据」组（与每日 16:15 发布、24h 阈值一致；放「已下架」页会被判 7 天静态卡漏报不可用）。
  - `obsPaneMarket`（大盘观测）：删除 `marginBody` 两融卡块 + `var _mg = function(){...}` 注入函数及其 `setTimeout` 重试调用。
  - `renderDelisted`（已下架页）：还原 `/* 5. 两融余额走势 */` 卡块（`v8CardHeader` + `#v8MarginChart`）+ `drawV8MarginChart();` 调用。
  - 大盘观测 header 注释「5 张内容卡」→「4 张内容卡 · 两融 2026-10-04 主人令迁回已下架」。
- **logic.html**：`renderDelisted` 还原两融卡块 + `drawV8MarginChart();` 调用（同步 index 已下架页）。
- **v8_health_check.py**：`MARGIN_DATA` 的 `"page": "观测平台"` → `"page": "盘后数据"`（L155）+ 注释同步。

### 验证（三重把关全绿 + 线上实测）

- **Node inline 实跑**：index 29 块 / logic 6 块 / **0 错误**。
- **pre_deploy_audit 15/15 全绿**：含 [2/8] new Function 0 错、[10/10] index 标记 43/43、[15/15] logic.html 76 个 `?v=` 戳与数据哈希一致。
- **线上真实验证（curl 抓 GitHub Pages，2026-10-04 09:57 CST）**：
  - `logic.html`：772441 B、**纯 CRLF 8818/8818**、两融命中 `v8MarginChart`+`drawV8MarginChart` = 4 ✅
  - `index.html`：大盘观测区 `marginBody`=0、`_mg`=0、`drawV8MarginChart`=0 ✅（卡已彻底移出）；`drawV8MarginChart` 仅 2 处 = 函数定义 + 已下架页调用（合法）。
  - 结论：两融余额走势卡确在「🔒 已下架」页，大盘观测下方不再出现 —— 与主人截图诉求一致。

### 🔴 残留风险（待小九知会/评估）

- **logic.html 的 `?v=` 注入在云端 `update_v8.py` 以文本模式读写**（`open(...,encoding='utf-8').read()` + `write_text`），会把 CRLF 翻成 LF。本次 `f4738058e5` 的 logic.html 已是纯 LF（脏 diff 被 build 继承），本次 `81712d727e` 已翻回 CRLF 且线上实测为 CRLF。
- **但**：下次 build 若触及 logic.html 引用的某个 data 文件哈希变更（如动量状态 `STOCK_MOMENTUM_STATE.js` 等，每次刷新都会变），`update_v8.py` 重写 logic.html 时会再次翻成 LF ⇒ 脏 diff 复现。
- **功能无影响**（浏览器不区分 CRLF/LF），仅仓库 diff 卫生问题 + 与 `-text -eol` 约定不符。
- **根治建议**：把 `update_v8.py` 的 `?v=` 注入改为二进制读写（`open('rb')` 读 → 字节级正则替换 `?v=...` → `open('wb')` 写），保留原行尾。本仓 `update_v8.py` 在根目录、云端生成器同逻辑；是否登记 HANDOFF.yaml 挂账由小九裁决（迁移已完成，本件不强制挂账）。

### 推送纪律

- 全程**快进、禁 force**；`f4738058e5` 的 build `?v=` 戳（HEALTH_CHECK/COMMODITY_ELASTICITY/SENTIMENT_CYCLE/STOCK_MOMENTUM_STATE[_V2]/MOMENTUM_FILTER/IMA_STRONG_BACKTEST 等）完整保留，未丢失。
- 推送：`f4738058e5..81712d727e  alimi-margin-dl -> main`（push_exit=0）。

---

## 无需小九回退/重做

- 大盘观测两融卡已彻底移除，已下架页已恢复，勿再把两融卡迁回大盘观测（那是无主令擅迁的根）。
- logic.html 行尾当前为 CRLF（线上已验证）；若下次 build 后 diff 显示 logic.html 整文件翻转，属已知 build 文本写问题，按上节根治建议处理，勿手工反复翻行尾。
