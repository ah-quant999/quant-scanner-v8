# HANDOVER｜阿狸咪的工程师(alimi-cn) → 小九的工程师(lemoncat-cn)｜2026-09-28 16:56｜共振日历两项修复收口+真浏览器终验（含一处静默降级 bug 根治）

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

共振日历两个问题（卡头胶囊回归 + 懒加载空白）**均已在远端 main 上线并经真浏览器终验通过**；
本轮另外**挖出并根治了一处「静默降级」bug**（断源时明示提示被自己的重绘吞掉，主人看到看似正常的日历却零提示）。
`resonance-calendar-lazyload-fail` 因此由 `pending-verify` **转 done**；长期项 `lhb-history-size-slim` 已立账。

---

## 变更清单

| # | 文件 | 动作 | 说明 |
|---|---|---|---|
| 1 | `index.html` | 修复 + 上线 | `onFail()` 分支追加降级提示（机游 `jyCalContainer` + 北向 `northCalContainer` 对称） |
| 2 | `docs/ops/HANDOFF.yaml` | 更新 | `resonance-calendar-lazyload-fail` → done（追加 `alimi_verify_20260928_1810` 终验记录 + `fix_ext_20260928`）；新增 `lhb-history-size-slim`(todo/P2)；`meta.next_id_seq` 91→92 |
| 3 | `docs/ops/HANDOFF.ledger.json` | 同步 | 105 项哈希重算，脚本 `--check` 105/105 命中、0 失配 |
| 4 | 本交接件 | 新增 | — |

### 线上真身自证

- `main` tip（本轮）：`dbf22740b8e9bfa81589f4ee71b0cc825bb1d816`
- `index.html` 本地 ↔ 远端 contents API 回读 **逐字节一致**，md5 = `d92777d94a8649481f6b2621429522f4`
- GitHub Pages 线上已上线：`1,364,111 B` / sha256 前 16 = `69aae18017f4f9ca`（轮询 105s 内抓到新标记）
- 门禁 `pre_deploy_audit.py` **14 项全绿**（含 `[2/8] new Function: 28 个 inline script 块 0 错误`、_CORE `[10/10] 38/38 标记在位`_）

---

## 一）两项共振日历修复的现状（均 PASS）

| 项 | 状态 | 终验方式 |
|---|---|---|
| `rc-calendar-capsule-regression`（卡头胶囊回归） | 已 done（本轮复核仍在线上） | 硬抓线上真身：旧回归标记 `_uBadge('盘后','短线'` = **0**；新写法 `window._rcDataDateBadge() + '</span>'` = **2**（即「📅 机游共振日历 + 数据日期」，不再是「🦊 更新于…」） |
| `resonance-calendar-lazyload-fail`（P0 懒加载空白） | **本轮转 done** | 真浏览器（Edge headless）直打 Pages，见下 |

### 懒加载终验：正常路径

```
LHB_HISTORY 已注入字节: 1,602,143        ← 兜底源 fastly.jsdelivr.net 扛住
机游 jyCalContainer   : 97,228 字节      ✅
北向 northCalContainer: 22,112 字节      ✅
控制台: [A2 lazy] LHB_HISTORY 到位，重绘两个共振日历
```
→ 病灶（Pages 跨境 1.8MB 三次全失败）已消除，两个 tab **均有数据**。

---

## 二）本轮挖出并根治的真 bug：断源时的「静默降级」

**现象**：故意断掉全部 `LHB_HISTORY.js` 源（Pages 源 + CDN 源，共 6 次尝试 = 2 源 × 3 轮），
日志走到 `[A2 lazy] 所有源与重试均失败： LHB_HISTORY`，但页面上看不到任何提示。

**根因**（`index.html` `onFail()`）：
```js
try{ if(typeof window.__rcRedrawBoth==='function') window.__rcRedrawBoth(); }catch(e){}   // ① 先用 LHB_DATA 把容器填满
try{
  var _el=document.getElementById('jyCalContainer');
  if(_el && !String(_el.innerHTML||'').trim()){ ... 提示 ... }                              // ② 容器已非空 ⇒ 恒为假，整条跳过
}catch(e){}
```
① 先把容器填满了，② 的「容器为空才提示」判据便**恒为假** ⇒ 明示提示整条被吞。
净效果：主人看到一张**看起来完全正常的日历**，实际是降级态（只有当日、历史日期缺失），**页面零提示 ＝ 静默降级**，
与该项 `fix` ③「全源全轮皆败 ⇒ 用 LHB_DATA 降级渲染 + **明确提示**（绝不静默空白）」**直接相悖**。

**修法**（已落盘并上线）：容器为空 → 仍走整块占位提示（保留原路径）；容器已有内容 → **追加**醒目提示条且**绝不覆盖日历**；
幂等（同 id 至多一条）；两个共振容器**同步处理**，禁止某一路特立独行。

**修复后断源复验（PASS）**：
```
纯文本首行 = ⚠️历史大表（1.8MB）多轮加载失败，当前仅显示当日龙虎榜数据（历史日期可能缺失）。请刷新页面重试。
jyCalContainer 长度 = 23,251（日历仍在下方渲染，未覆盖）✅  非空白 ✅
```

---

## 三）遗留 / 后续（已立账，请勿丢失）

- **`lhb-history-size-slim`（P2 · todo · owner=shared）**：共振日历两 tab 全量依赖 `data/LHB_HISTORY.js`
  （1.6–1.8MB / 79 天）。多源兜底 + 3 轮重试只是**缓解**，任一源被跨境掐断仍会降级缺历史。
  根治方向 = **缩表**（实测裁 `reason`/`price` 等冗余字段可省 ~40%），目标 ≤1.0MB，并同步确认北向席位等消费方字段依赖。
- **长期观察**：后续若再出现共振日历缺历史日期，请先查 `LHB_HISTORY.js` 实际体积，再怀疑前端。

---

## 四）回滚提示

本轮 `index.html` 改动范围极小（仅 `onFail()` 一个分支内**追加**提示条，不触碰任何渲染/取数逻辑）。
如需回滚，只需把新增的 `try{ … _TIP … }` 整段删除即可，对既有行为零影响。

---

## 五）提示（给接手方）

本文件仅覆盖共振日历。同日另有一批**盘后算法链/D 批**相关的调查与发现（闸门 D 批结构性死锁等）见当日其它交接件/日志，未混写在本件内。
