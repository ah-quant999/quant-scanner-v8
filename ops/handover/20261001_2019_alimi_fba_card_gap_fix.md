# 交接件：连板梯队前哨卡间距修复（2026-10-01 20:19 阿狸咪的工程师）

## 一句话
「🔭 连板梯队前哨」卡与「🚀 主升/启动 板块·龙头股」卡之间 0 间距贴死，已补 `margin-bottom:14px` 并上线。

## 根因
- `firstBoardAlertCard`（静态卡，index.html）只有 `margin-top:14px`，无 `margin-bottom`；
- 其后 `unlistedPanel`（JS 注入容器）首卡 `sectorLeadersCard` 无 `margin-top` ⇒ 两卡相接 0 间距；
- 对照组：「主升/启动」卡自带 `margin-bottom:16px` ⇒ 与「概念/行业→ETF」卡间距正常（用户截图实证）。

## 修复
- 单行锚点替换：`margin-top:14px;` → `margin-top:14px;margin-bottom:14px;`（卡容器 style，与同卡 margin-top 节奏一致）。

## 审计自证
- 离线门禁 `pre_deploy_audit.py`：**14/14 全绿**（exit=0）。
- inline `<script>` 全量 29 个跑 `new Function`：**0 错**。
- 末尾 `</html>` 完整、行数不变（19225）、纯 LF（`\r` 计数=0）。

## 防覆盖
- 基底=远端实时 tip `4547920cdf2a` 的 index.html blob（非本机副本）；
- Git Data API 单文件单提交、`force:false`、422 重放未触发（attempt 1 一次通过）；
- 提交 `158f255bc07d`，回读 blob 与补丁**逐字节一致**；index.html 最后一次提交=本修复；
- CI build（19:50/19:55/20:05 高频刷 `?v` 戳）与本修复无冲突：只动缓存戳不动内容锚。

## 线上终验
- Pages 实抓 `index.html`：新锚点=1、旧锚点=0（约 40 秒内生效）。

## 小九需知
- 无需动作；仅注意 CI 后续 build 刷 `?v` 时本修复内容锚会自然保留（非生成器产物，scripts/v8/algorithms 无 `firstBoardAlertCard` 引用）。
- 本地工作树 index.html 已同步为补丁后内容（此前漂移仅 `?v`/BUILD 戳陈旧，实质同源）。
