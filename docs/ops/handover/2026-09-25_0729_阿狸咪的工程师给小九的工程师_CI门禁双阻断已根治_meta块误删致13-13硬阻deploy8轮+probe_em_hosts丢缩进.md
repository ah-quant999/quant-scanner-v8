# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-25 07:29｜CI门禁双阻断已根治_meta块误删致13-13硬阻deploy8轮+probe_em_hosts丢缩进

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

v8 云端部署链自 2026-09-24 20:56 CST 起被 **Pre-deploy audit 两项门禁**硬阻断（连阻 8+ 轮 build job failure），
根因 = ① **`HANDOFF.yaml` 的 `meta:` 块被误删**（我 09-24 那笔 `a2b5f1f38f3b` 自己造成的），致 `[13/13]` 读不到 `next_id_seq`；
② **`probe_em_hosts.yml` heredoc 正文丢缩进**，致 `[5/8]` 判 YAML 无效。
**两笔修复已于 `89ae1b937d09` 推送并线上验证通过：run #8210 build job = success，14/14 门禁全绿，`✅ 已部署 main`。**

---

## 一、发现路径（本轮巡检）

- 主站可达 ✅ HTTP 200 / 1,361,458 B（正常）
- 但 `build_deploy`（wf 324135263）**最近 8 轮全 `failure`** —— 与上一轮「推送竞态（`! [rejected]`）」形态**不同**，
  故逐轮下钻：失败步**唯一** = step10 `🛡️ Pre-deploy audit`，其后 step11-14（双盲区静态校验 / 部署前校验 / **部署到 main** / 发布后体检）**全 skipped** ⇒ 部署被硬阻断。
- 逐字证据（run #8208 / job 107866549869）：
  ```
  ❌ [5/8] workflow YAML: 1/34 个 workflow 对 GitHub 无效:
    - probe_em_hosts.yml:17 顶层非法行（YAML 必崩，通常= run: | 块内丢了缩进）→ 'import json, urllib.request, time'
  ❌ [13/13] 交接状态源守卫: next_id_seq / max_next_id_seq 非整数（当前=None ledger=77）
  🚫 2 项校验失败 → 阻断 deploy！
  ```

## 二、根因（均为铁证，非推断）

### ① `[13/13]` — `HANDOFF.yaml` 的 `meta:` 块被误删
- 守卫实现：`.github/scripts/pre_deploy_audit.py:1218` 读 `d["meta"]["next_id_seq"]`；`meta` 缺失 ⇒ `None` ⇒ `int(None)` 抛错 ⇒ FAIL。
- 远端实测：`HANDOFF.yaml` 顶层键**只有 `items`**，`meta` = `None`。
- 责任定位（不回避）：该块在 `136d8f8cdbbe`（09-24 16:08 UTC）仍完好（`meta:` 在第 28 行、`next_id_seq: 77` 在第 61 行），
  被**下一笔 `a2b5f1f38f3b`（09-24 16:15 UTC，「修正上一笔 HANDOFF 追加位置——终验记录改落 item 内」）整块删除**。
  该笔当时的意图是「撤回误插的顶层记录」，但**连带删掉了 `next_id_seq` 与并发写协议注释**。
- 我当时**只重算了 ledger 哈希、未跑完整 pre_deploy_audit** ⇒ 未发现此回归。**这是我的纪律失误，已记入本项。**

### ② `[5/8]` — `probe_em_hosts.yml` heredoc 丢缩进
- 远端 `probe_em_hosts.yml`：`run: |`（8 空格）→ `python - <<'PYEOF'`（10 空格）→ **正文从第 17 行起被顶到第 0 列**。
- 后果：YAML 把 `import json, urllib.request, time` 当顶层键解析 ⇒ 文件对 GitHub 无效。
- 该文件由 `366326594` probe 批次引入（用于东财 host 池探测），**未入任何门禁白名单豁免**，故被 `[5/8]` 正确拦下。

## 三、修复内容（commit `89ae1b937d09`，Git Data API 六步）

| 文件 | 修复 | 校验 |
|---|---|---|
| `docs/ops/HANDOFF.yaml` | 在 `items:` 前**恢复 `meta:` 块**（`next_id_seq: 77` == `ledger.max_next_id_seq`，并复原并发写协议 A/C/D/E 注释） | 插入前后除 meta 块外逐行一致；`yaml.safe_load` 回读 `meta.next_id_seq==77`、`items` 仍 82；守卫逻辑离线模拟 PASS |
| `.github/workflows/probe_em_hosts.yml` | heredoc 正文统一补 **10 空格基准缩进**（保留其相对缩进） | `yaml.safe_load` 解析通过 + heredoc 内 Python `compile()` 通过 + **GitHub 端实测已注册为有效 workflow**（34/34） |

- ledger **无需重算**：`[13/13]` 只断言「ids 超集」与「seq 单调不减」，不校验 `id_content_hashes`；
  实测 `ledger.ids=82 ⊆ yaml.items=82`、`77 >= 77` ✅。

## 四、线上验证（铁证，非「应该好了」）

- run **#8210**（head `0eef8c8864b9`）经 `compare 89ae1b937d09...0eef8c8864b9` = **ahead 1 / behind 0** ⇒ 确为修复后代码。
- 逐字：
  ```
  ✅ [5/8] workflow YAML: 34 个 workflow 全部有效（PyYAML 全量）
  ✅ [13/13] 交接状态源守卫: 交接状态源完好：items=82（ledger 锚 82 个 id 全在）· next_id_seq=77≥77
  🎉 14 项全部通过 → deploy 可继续
  ✅ 已部署 main（第 1 次尝试，GitHub Pages 自动重建）
  ```
- `build` job = **completed success**（此前 8/8 failure）；唯一非 success 步 = step3「抢跑短路」= **skipped（设计）**。
- 部署后主站复测：**HTTP 200 / 1,361,458 B** ✅。

## 五、另一线索（**东财红卡，非本次修复范围，维持「勿再派发」**）

同批巡检确认两红卡 `raw_data/experiment.json`（ut 2026-09-22 18:13:35）与 `raw_data/sector_leaders.json`（ut 2026-09-22 18:15:13）**age ≈61h 仍停更**。
- 09-23 / 09-24 均为**真交易日**（09-25~09-27 才是中秋休市，沪深北 09-17 已公告）⇒ 红卡**确实漏了两个交易日**。
- 决定性证据（post_close run `36021141027` / #2184 step22 真跑日志）：
  ```
  ⚠️ 东财 push2 抖动(push2delay.eastmoney.com) 尝试1/3: HTTP Error 502: Bad Gateway → 换 host 重试
  ⚠️ 东财 push2 抖动(push2.eastmoney.com)      尝试2/3: HTTP Error 502: Bad Gateway → 换 host 重试
  File "scripts/fetch_sector_leaders.py", line 166, in fetch_em_boards
      d = _get_json(url, hosts=EM_HOSTS)
  ```
  ⇒ **换 host 修复符号 `hosts=EM_HOSTS` 确在运行路径被执行**（排除「跑旧代码」），但 14 host 全 502。
- 跨网双形态复核（本机 09-25 07:1x）：`push2.eastmoney.com` / `push2delay` / `82.push2` / `push2his` 的 **API 路径全部 `RemoteDisconnected`（curl 000）**，
  而 `www.eastmoney.com` = 200、`quote.eastmoney.com` = 200 ⇒ **主站活、行情 API 拒连**；CI 侧同 API = 502。
  **双网络双形态 + 修复符号在位仍全败 ⇒ 判东财上游真故障**，非我方管线。
- 处置：按任务书第 3 条**不派发**，维持 `redcard-hostfail-rootfix-0924` 的 `pending-verify`。
  ⚠️ **注意**：此前该 item 的「停更」被部署阻断叠加掩盖——现 deploy 已恢复，**下一次交易（09-28 周一）post_close 是本轮真正的自然恢复判据**。

## 六、给小九的请求（唯一一条）

🔴 **`handoff-ledger-hash-desync`（你 09-23 17:55 的 `note` 点名要我回答）**：
口径我已确认为**仓内脚本** `scripts/handoff_ledger_hash.py`（五步：块 = `- id:` → 下一 `- id:`；剔块尾空行与注释行；块内 `updated` 值归一化；`rstrip()`；`sha256[:16]`）。
我 09-24 20:15 用它直接对**远端 main 真身**实跑 `--check --ids`：`YAML items=81 | ledger ids=80 | hashes=79 ⇒ 命中 78/79、失配 1、未收录 2`。
**请你按此口径一次性重算并校准到 100%**，同批把「哈希 ≡ 现算」并入 `[13/13]` 或加 soft 告警（现在只查 ids/计数，漂移查不出来）。
本项**不影响部署链**（门禁不校验哈希），可排在东财红卡之后。

## 七、纪律自省（写给双机）

1. **改 `HANDOFF.yaml` 这类「被门禁依赖的文件」，收尾必须跑一次完整 `pre_deploy_audit.py`**（或至少 `[13/13]` 单测），
   只重算 ledger 哈希**不足**以防此类回归 —— 本次即因此漏检 8 轮部署。
2. **推 workflow 文件后，必到 GitHub `actions/workflows` 接口核「是否被注册」**，本地 `yaml.safe_load` 通过 ≠ GitHub 接受。

---

> 交接件生成：`python docs/ops/scripts/new_handover.py --from 阿狸咪的工程师 --to 小九的工程师 --topic ...`（禁手写）
> 状态源同步：`docs/ops/HANDOFF.yaml`
