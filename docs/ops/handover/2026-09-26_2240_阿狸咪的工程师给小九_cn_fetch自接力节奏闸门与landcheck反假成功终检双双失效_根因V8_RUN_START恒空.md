# HANDOVER｜阿狸咪的工程师 → 小九｜2026-09-26 22:40｜cn_fetch 自接力节奏闸门与 landcheck 反假成功终检双双失效（根因：V8_RUN_START 恒空）

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

`v8_cn_fetch_cloud.yml` 有两个 step 把 `V8_RUN_START` 取成 `${{ github.run_started_at }}`，
而该属性**不在 GitHub `github` 上下文属性表内**（`run_id`/`run_number`/`run_attempt` 在列，`run_started_at` 不在）
⇒ 服务端表达式求值为 `null` ⇒ 环境变量**恒为空字符串**（实测 6/6 档，含本仓 main 最新 blob）。
后果两条：① 新增的「🔍 数据落地实证终检（杜绝『run 全绿但数据没动』的假成功）」**每档走「保守跳过」分支、自上线起从未生效**；
② 盘中自接力的「派发不得密于 10 分钟」节奏闸门 `gap` 恒为 `999` ⇒ **反爬下限纪律被结构性关闭**。
本轮**刻意未落码**（激活 landcheck 前必须先补「交易日 + 盘中窗口」门控，否则立刻制造假红 + 派发风暴），
交小九裁决是否由阿狸咪代落。

---

## 正文

### 1 铁证（源码面 = 运行面，两面对齐）

**源码面**（远端 main `blob f4bf6f6d73ac`，89,519 B；与 run `#2336` head `b9f7e956e935` 的该文件 blob **逐字节相同**）：

```
 1012|         id: landcheck
 1013|         if: always() && steps.gate.outputs.skip != 'true'
 1014|         shell: bash
 1015|         env:
 1016|           GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
 1017|           V8_CAT: ${{ steps.cat.outputs.category }}
 1018|           V8_RUN_START: ${{ github.run_started_at }}      ← 非法属性
 ...
 1167|         env:
 1168|           GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
 1169|           V8_RUN_START: ${{ github.run_started_at }}      ← 非法属性（同因）
 1170|           V8_RUN_ID: ${{ github.run_id }}                 ← 这个是对的，但没被用来兜底
```

**运行面**：run `#2336`（id `36248589475`，2026-09-26 22:27 CST，job `fetch`）step28 的 runner env dump 逐字
`V8_RUN_START: `（**空值**）；同一档该步输出逐字

```
[landcheck] 无法解析 run_started_at=''，保守跳过（宁可不报，不误报）
```

**历史面**：连续 6 档 `completed` run（`#2332` `#2333` `#2334` `#2335` `#2336` `#2337`）逐一下载 job 日志核对，
landcheck 段**全部**落在同一「保守跳过」分支 —— 不是偶发，是**结构性**。

**文档面**：GitHub「Contexts」参考页 `github` 上下文属性表中
`run_id` / `run_number` / `run_attempt` 均在列，**`run_started_at` 不在列**（官方页 + 3 处镜像一致）。

> ⚠️ 与上文关系：本仓 `v8_cn_fetch_cloud.yml` 里对应「**执行期**」的两个消费点分别是
> `landcheck`（step28 终检）与 `relay`（step29 自接力）。二者共用同一空值来源，故一并交接。

### 2 后果 ①：landcheck 终检**从未生效**

- 该步正是 2026-09-22 为东财停更事故新增的防线（见 item `intraday-eastmoney-stall-4cards` 的 verify ③：
  「landcheck 新增东财源组判红（intraday 东财 5 文件全未推进 → exit 1 → 调度器触发小九 cn 兜底）」）。
- 代码结构决定了它在**取 PROBE 文件新鲜度之前**就退出：
  `started` 空 → `datetime.datetime.strptime('', …)` 抛 `ValueError` → 命中 `except` → 打印「保守跳过」→ `sys.exit(0)`。
  ⇒ **比较逻辑一行都没执行过**。
- 🔴 **直接激活会踩雷**：该步 `if: always() && steps.gate.outputs.skip != 'true'` —— 休市/非交易日同样进入。
  一旦 `started` 有值，周末与假期就会因为「盘中文件本就不刷新」而判红 ⇒ **假红 + 触发 cn 兜底派发风暴**。
  ⇒ **修复必须同批加「交易日 + 盘中窗口」门控**（与 `v8_date.is_trading_day()` / `v8_calendar.py` 同源，禁再立第五份日历）。

### 3 后果 ②：自接力「10 分钟节奏闸门」失效

```
 1215|           gap = 999.0
 1216|           if rstart:
 1217|               try:
 1218|                   t0 = datetime.datetime.fromisoformat(rstart.replace("Z","+00:00")).astimezone(CST)
 1219|                   gap = (now - t0).total_seconds() / 60
 1220|               except Exception as e:
 1221|                   print(f"[relay] 解析 run_started_at 失败: {e}")
 1222|           print(f"[relay] 本轮已跑 {gap:.1f} 分钟（口径：距本轮开跑）")
 1223|           if gap < 10:
 1224|               wait = 10 - gap
 1225|               print(f"[relay] 间隔不足 10 分钟 → 等待 {wait:.0f} 分钟后派发")
 1226|               time.sleep(min(wait * 60, 600))
```

- `rstart` 恒空 ⇒ `gap` 恒 `999.0` ⇒ `gap < 10` 恒 False ⇒ **永不等待**。
- 同文件注释（L1213-1214）逐字写明该闸门的设立理由：
  「⚠️ **下限纪律：不得低于 10 分钟**。09-21 实测派发密到 7~8 分钟时撞新浪/东财反爬 ⇒ 单轮 exit 1。」
- 但同档的**在途查询**（L1233-1246，「已有 queued/in_progress ⇒ 本轮不派发」）**仍在工作**，
  ⇒ 链不会同刻并发。故闸门失效的**实际暴露面** = 前一档跑得很快（休市跳步 / 快速失败）时，下一档**立即**被派发。
- 观测面（本仓 `v8_cn_fetch_cloud`，CST）：09-26 当日 24h 内共 **50 档**；
  其中 21 时 9 档、22 时 5 档；`#2337`(14:29:38Z) → `#2338`(14:31:10Z) → `#2339`(14:31:44Z) 相邻仅 92s / 34s。
- ⚠️ **未定项（不并入本项归因）**：休市日 `relay` 步因 `steps.td.outputs.proceed == 'false'` 被 skip
  （run `#2336` step29 表内 = `skipped`）⇒ 休市期的密集派发**另有派发源**，本轮未定性。

### 4 建议修法

**A（推荐 · 两处同改 · 语义漂移最小）**

1. `landcheck` step 的 `env:` 补一行 `V8_RUN_ID: ${{ github.run_id }}`（`relay` step L1170 已有）。
2. 两处脚本内在 `rstart` 为空时**经 API 兜底**：
   `GET /repos/{repo}/actions/runs/{V8_RUN_ID}` → 取 `run_started_at`
   （该字段**在 REST API 的 run 对象里是真实存在的**，与上文「上下文属性表」不是一回事；
   本仓 item `cn-singleflight-schedule-trigger-offset` 即引用过它）。
   · `landcheck` 步已持 `GITHUB_TOKEN`，直接 urllib 取即可；
   · `relay` 步的 `api()`/`H` 定义在 gap 计算**之后**（L1194-1203），故需把 gap 计算下移，或直接用 `tok` + urllib 取。
3. `landcheck` **同批**加门控：非交易日 / 非盘中窗口 ⇒ 打印原因后 `sys.exit(0)`，避免激活即风暴。

**B（不推荐）** 换 `github.event.repository.updated_at` 之类替代 —— 语义不符（是仓库推送时间，非本轮开跑时间）。

### 5 本轮未落码的理由（请小九裁决是否由阿狸咪代落）

- 属 cn runner workflow 车道；且 ①② 的修复**都会改变运行行为**（① 新增判红路径、② 新增 sleep 等待）。
- 当前为中秋休市窗口（09-25~09-27，据沪深北 09-17 公告）⇒ **无法在盘中观测副作用**。
- 主人令「不要造成踩踏和暴风」⇒ 在无人观测窗口激活一条会判红的守卫，与令相悖。
- 若小九裁定由阿狸咪代落：落码将走 Git Data API 六步范式（远端为基底 + 漂移断言 + 推后逐字节回读），
  并附 `bash -n`（0 错）+ `yaml.safe_load` + **28 个 step 签名一一相同**三项自证（沿用 `99fef522c817` 那一笔的范式）。

### 6 复核命令（可直接粘贴）

```bash
# ① 源码面：两处 env 取值
python - <<'PY'
import json,base64,urllib.request
T=open('/c/Users/HH20210606/.workbuddy/v8_gh_pat').read().strip()
u='https://api.github.com/repos/ah-quant999/quant-scanner-v8/contents/.github/workflows/v8_cn_fetch_cloud.yml?ref=main'
r=urllib.request.Request(u,headers={'Authorization':'Bearer '+T,'User-Agent':'x'})
txt=base64.b64decode(json.load(urllib.request.urlopen(r))['content']).decode()
for i,l in enumerate(txt.split('\n'),1):
    if 'V8_RUN_START' in l or 'run_started_at' in l: print(i,l.strip())
PY

# ② 运行面：任一档 job 日志里的 landcheck 结论（须 curl -sSL，跨 host 不转 Authorization）
curl -sSL -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/jobs/<JOB_ID>/logs | grep landcheck
# 期望（缺陷态）：[landcheck] 无法解析 run_started_at=''，保守跳过（宁可不报，不误报）

# ③ 文档面：github 上下文属性表是否收录 run_started_at
# https://docs.github.com/en/actions/learn-github-actions/contexts  （搜 run_started_at → 无）
```

---

## 附：本轮其它已核事实（供交叉参照，非本件主题）

- 主站 `https://ah-quant999.github.io/quant-scanner-v8/` = HTTP **200** / **1,361,458 B** / 19,314 行 /
  尾 `</html>` 闭合；与远端 blob `9b610c73ceb9`（@commit `d75a2361e960`，tip 前 2 档）**逐字节相同**。
- 两红卡仍停 09-22（`experiment.json` 18:13:35 / `sector_leaders.json` 18:15:13，age ≈100h）——
  中秋休市窗口内为**预期**；`compare 1052d4334162...main` = **ahead 558 / behind 0** ⇒ 换 host 修复在运行路径。
- `algo_run_report.json` / `algo_heartbeat.json` ut = **2026-09-26 08:48:52**；
  `v8_algo_cloud` `#2123`–`#2127` 全 `success` ⇒ t1 段首假红已收束。
- `cnfetch-bash-syntax-dead-steps-0926` 的 verify ① 在**更新的一档**复验通过：
  run `#2336`（head `b9f7e956e935`，含修复 `99fef522c817`，`ahead 48 / behind 0`）step24 日志逐字
  `✅ index.html 完整性断言通过：行数=19315 字节=1361458 尾部闭合=OK A2三锚=OK`，且全档 `syntax error` 命中 **0**。
- 🔴 家机侧东财 push2 **真实 API 路径**仍全拒连（`push2*` / `82.push2` / `push2his` 的 `/api/qt/clist/get` 全 `000`，
  裸 `/` 返 404 = 边缘可达但 API 不可用）⇒ 上游故障持续，与前述结论一致。

---

**署名**：阿狸咪的工程师（alimi-cn）· 2026-09-26 22:40 CST
**认领方式**：收到后只改 `docs/ops/HANDOFF.yaml` 的状态字段（item `cn-run-start-env-dead-guards-0926`），
不写回执档（协议第 4 条）。
