# V8 设计原则：从 V6 的失败中汲取教训

> 目的：把 V6 踩过的坑固化成 V8 的红线，确保 V8 **轻装上阵、数据及时真实、算法靠谱**，同时不丢 V6 沉淀的铁律。
> 适用范围：V8（quant-scanner-v8 仓库）的全部代码、数据管道、部署、监控。

---

## 一、V6 的失败清单（我们踩过的坑）

| # | 失败点 | 后果 | V8 是否已规避 |
|---|--------|------|--------------|
| 1 | **大块头单体页**：3.95MB `index.html` 内联 43 个 `window.*` 大 JSON | 首屏慢、移动端差；每次改数据都要重新生成+部署整页；git 历史膨胀（单日 10 次 deploy 改 10 遍整文件） | ✅ 已拆 `data/*.js`，`index.html` 降至 260KB |
| 2 | **部署脚本与架构脱节**：`update_v8.py`/`deploy_v8.py` 引用 `v8/dist/index.html`、`../data`（V6 布局），但 V8 仓库根只有 `index.html` | 按脚本跑必 `open()` 报错，脚本成"死代码" | ✅ 已重写对齐根目录结构 |
| 3 | **guard 脚本指错仓库**：`guard_v8.py` 指向 `quant-scanner-v6.git` 的 gh-pages `/v8/` | 一旦触发会把 V8 内容误写进 V6 | ✅ 已改指 `quant-scanner-v8` |
| 4 | **数据新鲜度监控断裂**：约 15 个数据块停在 07-28/07-29，6 个本应日频刷新的停在昨日 | 页面显示陈旧数据，用户以为"没更新" | ⚠️ 待接 V8 看门狗 |
| 5 | **脚本孤岛**：`fetch_concept_map`/`enhance_dist`/`fetch_etf_flow` 等写了却从未接进流水线 | 写了等于没写，数据缺口长期无人发现 | ⚠️ 新脚本必须接进 `cloud_fetch_v8.py` 或流水线 |
| 6 | **云端 runner 网络物理限制未解决**：GitHub 美国 runner 抓 A 股源必 60s 超时，但 V8 没在中国机器注册自托管 runner | "云端跑数据"落空，数据仍卡在单机 | ✅ 已加 `runs-on:[self-hosted,cn]` 工作流，待注册 runner |
| 7 | **监控信号源错位**：从已停的 V6 管道（`data/`、`_heartbeat.log`）误判"小九失联" | 警报误导，浪费排查精力 | ✅ 监控改以 `quant-scanner-v8` 提交/线上站为准 |
| 8 | **Git/部署顺序脆弱**：`dist` 不同步、gh-pages 用 `cd && git push` shell 形式假成功 | 线上不更新、工作区残留 dirty | ✅ 用列表参数 + `--force`，dist 自动回推 main |

---

## 二、V8 已做对的事（守住的成果）

1. **数据层拆分**：43 个 `window.*` 全部拆到 `data/*.js`，`index.html` 仅 260KB（-93.4%）。
2. **大块头裁剪**：`BACKTEST_TDX`(1.2MB→3KB)、`BACKTEST_COMPREHENSIVE`(388KB→7.5KB)、`COCKPIT_BACKTEST`(47KB→34KB)、`GOLD_POOL`(788KB→405KB)、`W52_HIGH`(~200KB→1KB)——只留 summary/聚合/latest，去历史明细。
3. **脚本对齐架构**：`update_v8.py`/`deploy_v8.py`/`guard_v8.py` 全部重写并指向 `quant-scanner-v8`。
4. **更新健壮性**：`update_v8.py` 无 `raw_data` 不报错（exit 0），只重写存在的模块，绝不覆盖既有正常数据。
5. **云端自托管 runner 工作流**：`cloud_v8_data.yml`（`runs-on:[self-hosted,cn]`），抓数→构建→push `data/`。
6. **单源容错**：`cloud_fetch_v8.py` 逐模块容错，单源失败只跳过，保留旧数据。

---

## 三、V8 铁律（不可丢，从 V6 继承）

- **涨跌色**：红涨绿跌，空数据 `available=false` 不造假。
- **"更新于"相对日期**：所有面板显示 `今日/昨日/X天前`+时分，绝不写裸 `MM-DD HH:MM`。
- **不暴露内部细节**：用户可见文本（面板、详解页）一律不暴露具体数据源、脚本路径、本地/远端文件名、机器节点、跑批时间、内部 API 名。数据流细节只写 HANDOVER + 代码注释。
- **Git 顺序**：改源码后必须 `git add -f <文件>` → `git commit` → `git push origin main` → 再 deploy。`deploy_now` 第 0 步会 checkout origin/main 覆盖，未 push 即被擦。
- **dist 同步**：`deploy` 必须在 gh-pages 推送 + dist 重建**全部完成后**才回推 main，否则重建后的 dist 永远不进 main。
- **gh-pages 推送**：用 `subprocess.run([...], cwd=tmpdir)` 列表形式 + `--force`；严禁 `cd ... && git push` shell 形式（cmd 把 `/U` 当开关导致假成功）。
- **safe_pull 坑**：本质是 `git reset --hard origin/main`，会清掉本地未推送 commit。正确推送姿势：`git add -f` → `git commit` → `git fetch` → `git rebase origin/main` → `git push`。仅拉取远端他人改动且本地无未推送 commit 时才用 safe_pull。
- **git add -f**：`.gitignore` 用白名单放行根 `.py`；新增 `.py`/HTML/`data` 必须 `git add -f`，否则静默忽略。
- **防误删**：`DO_NOT_DELETE` 清单 + pre-commit hook 双保险；删受保护文件先 edit 清单再 `git rm`。

---

## 四、V8 要做到（越来越好）

### 轻量 · 不臃肿
- **数据按需加载**：首屏只拉必要数据，切 tab 再拉其余；关键小数据内联兜底防 fetch 失败空白。
- **缓存粒度细**：每个数据源独立 `data/X.js`，改一个只重传一个，不动整页。
- **新模块先进 `data/*.js`**：严禁退回 inline 大 JSON。任何新数据需求先问"能不能外挂 JSON"。
- **定期审计死脚本**：每季度扫一遍 `*.py`，没接进流水线的直接删或接上，不留孤岛。

### 及时 · 真实可靠
- **每个数据源独立刷新 + 独立部署**：某模块今日没刷新，只需重跑该模块抓取 → `data/X.js` → push，不碰整页。
- **cn 自托管 runner 按时抓**：盘后 16:35 + 盘中 10:35/11:50/14:35 定时 dispatch，中国机器本地执行，绕开美国 runner 超时。
- **看门狗盯新鲜度**：V8 必须接数据新鲜度监控（对标 V6 `data_freshness_watchdog.py`），核心源过期即告警，绝不让陈旧数据静默上线。
- **单源失败跳过不覆盖**：抓不到就保留上一版，页面标"数据暂缓更新"，绝不填假数。
- **数据校验**：抓取后做最小校验（非空、字段齐、日期合理），异常不写库。

### 算法靠谱
- **保留并测试核心算法**：回测、共识、金股聚合算法保留，但要有最小可验证路径（不靠 1.2MB 明细才能跑）。
- **不堆大明细**：历史明细只留聚合/latest，需要下钻的单独接口，不塞首页。
- **算法改动可回溯**：算法变更必须 commit + 说明，禁止无记录的手改。

---

## 五、当前待办（别让 V8  reopen 这些坑）

1. ⛔ **补 3 个空模块**：`SCAN_DATA`、`EXPERIMENT`、`ETF_DAILY_MONITOR`（no_data:true，备注"ETF 资金流 TOP10 数据源尚未接入"）。
2. ⛔ **刷 15 个陈旧数据块**：约 15 个停在 07-28/07-29，6 个日频源停在昨日。
3. ⛔ **注册 cn 自托管 runner**：GitHub → quant-scanner-v8 → Settings → Actions → Runners → `./config.sh --url ... --token ... --labels cn` → `./run.sh` → `pip install akshare`。注册后工作流才真正执行。
4. ⛔ **接 V8 看门狗**：把数据新鲜度监控接上 V8 信号源。
5. ⚠️ **校验 schema**：`cloud_fetch_v8.py` 产出为"尽力而为"结构，字段需对照 `index.html` 渲染逻辑逐模块验证；不符的模块首轮勿 push。
6. ⚠️ **确认 Pages 源分支**：线上仍跑小九 17:51 旧版，轻量版 commit `4366f69` 未生效。确认 Pages → Source 分支 + 必要时加 `.nojekyll`。

---

## 六、一句话总结

> V6 死于**臃肿 + 脚本与架构脱节 + 监控错位**；V8 要赢在**轻量分层、脚本即流水线、数据独立可刷、铁律不可破**。
> 轻装上阵 ≠ 偷工减料——数据的**及时**与**真实**，算法的**靠谱**，是底线，不是可选项。
