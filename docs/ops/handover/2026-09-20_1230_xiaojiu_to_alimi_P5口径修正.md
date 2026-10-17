# 小九 → 阿狸咪 · 2026-09-20 P5 年度门槛口径修正 交接

> **本文不含任何 commit sha 作为「已上线」论据**（双机高频 churning 仓库里写死即过期）。
> 需要核验一律走文末「现取命令」。
> 凡涉及「后续会怎样」均改为可跑的复核条件，不作承诺。

---

## 一、这批改了什么（3 件）

| # | 文件 | 改动 | 定性 |
|---|---|---|---|
| 1 | `algorithms/factor_walkforward.py` | `pass_yr` 判定由「全程年份占比 ≥0.8」改为「**连续 5 年窗口内 ≥4 年达标**（取最优窗口）」；新增 `WIN_YEARS/WIN_PASS_N` 常量与新字段 `win_years/win_pass_n/win_best_ok`；`criteria`/`methodology` 文案对齐 | **算法口径变更**（判据数值未变） |
| 2 | `index.html` | P5 卡文案适配新口径；删硬编码「年度跑赢率≥80%」与前端自算 `Math.ceil(total*0.8)`；组 note 旧事实改动态 | 前端文案 |
| 3 | `docs/ops/audit/2026-09-20_P5闸门口径审计_代码实现与主人原文不符.md` | 新增审计档（证据链 + 二项检验 + 回放 + 复核命令） | 文档 |

---

## 二、为什么改（真因，非「放宽门槛」）

**代码把主人的口径实现错了。**

- 主人 2026-09-09 22:31 原文：**「OOS IR > 0.3 且 4/5 连续 5 年胜率 > 55% 方可上线」**
  （见 `scripts/gen_factor_progress.py` 内引述）
- 代码实现：`pass_yr = (n_y > 0 and n_ok / n_y >= 0.8)` —— **全程年份占比**
- `factor_walkforward.py` 自己的 `criteria` / `methodology` 也一直写「≥4/5 年」
  ⇒ **实现与它自己的说明都不一致**，进一步说明是疏漏而非有意设计

**后果**：2026-09-09 时数据约 5 年 ⇒ `0.8` ≈ 「5 年里 4 年」，与主人原文**巧合一致**；
数据积累到 8 年（2019–2026）后 ⇒ `0.8` = 「需 7/8 年 = **87.5%**」，
**门槛随数据年份增长自动变严**，与主人原文偏离。

### 否证「放宽阈值」两条路（防以后有人再提）

| 方案 | 二项检验（真实无效因子 p=0.5） | 结论 |
|---|---|---|
| 放宽到 6/8 | 最好的因子只有 5/8 | **无效动作**（一个都放不进来）|
| 放宽到 5/8 | `P(≥5/8)=0.3633` ⇒ 8 因子里期望 2.9 个是蒙的 | **放进噪声** |

⇒ 唯一正确修法是**恢复主人原有的「连续 5 年窗口」口径**，而非按比例调阈值。

---

## 三、改后效果（真数据回放，数据采集时刻 = 2026-09-19 18:25:37）

用当时的线上产物回放新判定逻辑：

```
factor        ir_oos   旧win  新win   最佳窗口      旧判   新判   变化
max20         0.829      4      4    22-26 4/5    FAIL  PASS  🔴 FAIL -> PASS
ivol60        0.683      5      4    20-24 4/5    FAIL  PASS  🔴 FAIL -> PASS
turntrend     0.952      5      5    21-25 5/5    FAIL  PASS  🔴 FAIL -> PASS
amt60         0.845      5      4    21-25 4/5    FAIL  PASS  🔴 FAIL -> PASS
vol60         0.351      3      3    19-23 3/5    FAIL  FAIL
mom12_1      -0.314      1      1    19-23 1/5    FAIL  FAIL
resid_mom    -0.310      1      1    19-23 1/5    FAIL  FAIL
overnight20   0.239      2      1    19-23 1/5    FAIL  FAIL
```

**⇒ 4 个因子（max20 / ivol60 / turntrend / amt60）转为 PASS。**
待 E 批算法链重跑后，P5 卡会**自动恢复计分**（动态闸门，无需人工干预）。

---

## 四、🔴 需要你留意的两个坑（本次踩到）

### 坑 1：`factor_walkforward.py` 挂在 **STAGES["E"]**，不是每批都跑

- 2026-09-17 主人令（全站口径统一⑭）把它**补挂主链 E 批最末**
  （`run_algorithms.py` 的 `ORDER` 与 `STAGES["E"]` **成对**，改一处必须改两处，
   否则模块级 `assert(_STAGE_UNION == set(ORDER))` 崩链）
- ⇒ 只派发普通 run（闸门自动判批）**不保证**跑到它。
  **要让产物刷新必须显式 `stage=E`**：

  ```bash
  POST /repos/ah-quant999/quant-scanner-v8/actions/workflows/v8_algo_cloud.yml/dispatches
  {"ref":"main","inputs":{"stage":"E","force_run":"true"}}
  ```

### 坑 2：「脚本已改」≠「产物已重跑」

本次实测：先派发的普通 run（`head=29208671` 与 `14e7036a`）**跑完 success**，
但线上 `data/FACTOR_WALKFORWARD.js` 的 `update_time` **未变**、新字段 **x0**。
⇒ 必须看**产物字段**，不能只看 run 的 success。

---

## 五、错标口径防护（前端侧，重要）

P5 卡渲染里有一条**极易写错**的降级逻辑：

```javascript
// ❌ 错误写法：字段缺失时回退到「全程达标年数」，却贴上「窗口内最优 X/5」标签
var WB = (r.win_best_ok != null) ? r.win_best_ok : r.years_beat_gt55;
```

实测会把 **「全程 5/8」错标成「窗口内最优 5/5」**（看起来更宽松）。
现已改为：字段缺失 ⇒ 如实显示「**产物未含窗口字段，待算法重跑**」，**不冒充**。

**若你后续改这段，请勿把 `years_beat_gt55` 当作 `win_best_ok` 的兜底值。**

---

## 六、边界行为（数据不足 5 年时）

```python
if n_y >= WIN_YEARS:
    win_best = max(sum(_yr_seq[s:s+WIN_YEARS]) for s in range(len(_yr_seq)-WIN_YEARS+1))
else:
    win_best = n_ok        # 数据不足一个窗口 ⇒ 按现有年份原样判
```

- **不虚增门槛**（不会因窗口补零而变严）
- **不放宽**（不会因窗口不足而免检）
- 前端文案会显式说明「当前仅 N 年数据，不足一个窗口，按现有年份判」

---

## 七、现取命令（勿引用本文 sha —— 会过期）

```bash
# 1) 判据源码是否为修复版（找 WIN_YEARS 常量）
GET .../git/ref/heads/main                      -> tip
GET .../git/trees/{tip}?recursive=1             -> algorithms/factor_walkforward.py 的 sha/size
#    期望 size = 28661
GET .../git/blobs/{sha}                         -> 搜 'WIN_YEARS' / 'win_best_ok'

# 2) 产物是否已用新代码重跑（关键！）
GET https://ah-quant999.github.io/quant-scanner-v8/data/FACTOR_WALKFORWARD.js
#    判据：含 'win_years'/'win_pass_n'/'win_best_ok' 三字段，且 update_time 新于 2026-09-19 18:25:37

# 3) E 批是否在跑 / 跑没跑
GET .../actions/workflows/v8_algo_cloud.yml/runs?per_page=5
GET .../actions/runs/{id}/jobs                  -> 看 steps[] 「运行盘后算法链」是否 completed
#    ⚠️ 判「卡死」必须看步态推进（已完成步 completed_at 是否增长），
#       不看 status/updated_at（中段长步不刷 updated_at，会得卡死假象）

# 4) 前端文案是否已适配
GET https://ah-quant999.github.io/quant-scanner-v8/index.html
#    搜 '连续 5 年窗口内'（应命中）、'年度跑赢率≥80%'（应 0 命中）
```

---

## 八、复核清单（你接手时逐条打勾）

- [ ] `algorithms/factor_walkforward.py` 线上 blob size = **28661**（含 `WIN_YEARS`）
- [ ] `data/FACTOR_WALKFORWARD.js` 含 `win_years` / `win_pass_n` / `win_best_ok` 三字段
- [ ] 产物 `verdict=PASS` 的因子 = **4 个**（`max20 / ivol60 / turntrend / amt60`）
- [ ] `index.html` 含「连续 5 年窗口内」，且**不含**「年度跑赢率≥80%」
- [ ] P5 卡在页面上显示「4 个 PASS」而非「无一 PASS」
- [ ] 若 `win_*` 字段仍缺失 ⇒ **再派发一次 `stage=E`**（见坑 1）

---

## 九、边界声明

- 本次判据**数值未改**：仍为 `4/5`、`>55%`、`IR_OOS > 0.3`；改的是**窗口定义**（全程占比 → 连续 5 年滑动窗口）
- 本次为**算法口径变更**，授权来源：主人 2026-09-20「不用问我啦，都是选择按你建议处理，把握住我的宗旨和铁律就行」
- 未改动任何其他因子/阈值/权重；未触碰 `generate_top10.py` 的计分逻辑
- E 批产物落地时间**不可预测**（取决于 runner 与 K 线抓取耗时），故本文不写预期时间，只给复核命令
