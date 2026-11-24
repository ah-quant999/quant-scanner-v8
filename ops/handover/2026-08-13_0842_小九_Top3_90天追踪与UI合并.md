# HANDOVER：Top3 90 天滚动追踪 + 个股卡片 UI 紧凑化

> 生成时间：2026-08-13 08:42 CST  
> 主人决策：finalRec Top3 来源 / 入池即持仓 90 天滚动 / 回测+跟踪两行紧凑 / 小九全部负责  
> 红线遵循：**`index.html` 未直接 commit**，改动已整理为 patch 文件，由阿狸咪/主人合并。  
> 更新：算法/数据层已 push 至 main（commit `aed21861`），patch 现在**仅包含 index.html UI 改动**。

---

## 一、做了什么

### 1. 新增算法 `algorithms/gen_top3_track.py`

- 输入：`raw_data/final_recommend.json`（Top3）+ `raw_data/stock_quote.json`（价格）+ `data/STOCK_STOP_DATA.js`（精确止损/止盈）
- 输出：`raw_data/top3_track.json` + `data/TOP3_TRACK.js`
- 逻辑：
  - 每日盘后追加今日 Top3；已存在的标的不重开，续追踪
  - 每只在池标的每日推进 `days_in`；price 来自 `stock_quote.stocks[code]`
  - 退出判定：`STOCK_STOP_DATA.stop_loss` / `target_price` / 90 天 timeout
  - 归档：`history` 仅保留 90 天内出场的样本
- stats：胜率、均收、最佳/最差、持有分布

### 2. 接入 `algorithms/run_algorithms.py`

在 `final_recommend.py` 之后加一行：

```python
"gen_top3_track.py",  # → TOP3_TRACK.js（finalRec Top3 90 天滚动追踪盘，2026-08-13）
```

### 3. 接入 `update_v8.py`

- `DATA_SOURCES`：`"top3_track.json": "TOP3_TRACK"`
- `CATEGORY_MAP`：`"TOP3_TRACK": "post_close"`（与 finalRec 同节奏）

### 4. UI 改动（`index.html` patch）

- `data/TOP3_TRACK.js` script 注入（放在 `FINAL_RECOMMEND_DATA.js` 后面）
- 个股卡片「止损/目标/盈亏比/现价/涨跌」5 段 → 1 行紧凑 4 段
- 「回测 & 跟踪」10 KPI cell → 2 行紧凑（保留全部信息，删除重复字段）

### 5. patch 文件

`docs/ops/handover/HANDOVER_小九_2026-08-13_Top3_追踪.patch`

**注意**：算法/数据层已随 main 上线，本 patch **仅包含 `index.html` 改动**：
- `data/TOP3_TRACK.js` script 注入
- 个股卡片 fr-row 紧凑化
- 回测 & 跟踪 10 KPI 紧凑化

---

## 二、如何应用

### 算法/数据层（已从 main pull，无需 patch）

```bash
cd E:/workspace/quant-scanner-v8
git pull --ff-only origin main

# 验证单脚本
python algorithms/gen_top3_track.py

# 确认 raw_data/top3_track.json + data/TOP3_TRACK.js 已生成
ls -l raw_data/top3_track.json data/TOP3_TRACK.js
```

### index.html 部分（应用 patch 或手动复制）

```bash
# 仅对 index.html 应用 UI patch
git apply --check docs/ops/handover/HANDOVER_小九_2026-08-13_Top3_追踪.patch
git apply docs/ops/handover/HANDOVER_小九_2026-08-13_Top3_追踪.patch
```

如果担心 patch 自动合并覆盖你的 WIP，可以只对 `index.html` 手动复制 3 处：

1. **script 注入**：在 `<script src="data/FINAL_RECOMMEND_DATA.js...` 下一行加：
   ```html
   <script src="data/TOP3_TRACK.js?v=20260813082900"></script>
   ```
2. **fr-row 紧凑化**：把 `// 止损 / 目标 / 盈亏比` 那 8 行替换为 patch 中 `// 止损 / 目标 / 盈亏比 / 现价（一行紧凑显示，2026-08-13）` 部分。
3. **fr-bt-grid 紧凑化**：把 `// 回测 & 跟踪` 下 10 个 cell 替换为 patch 中「2026-08-13：10 KPI 合并为 2 行」部分。

---

## 三、验证

```bash
# 1. 跑算法（盘后）
python algorithms/gen_top3_track.py

# 2. 跑构建（盘后类别）
python update_v8.py --category post_close

# 3. 护栏
python guard_index_sections.py

# 4. 数据格式抽查
python -c "import json; d=json.load(open('raw_data/top3_track.json')); print(d['stats'])"
```

---

## 四、当前状态

- ✅ `algorithms/gen_top3_track.py` 已单脚本跑通，生成 `data/TOP3_TRACK.js`（首日为 3 只 tracking / 0 history）
- ✅ `update_v8.py` 已接入 `TOP3_TRACK`
- ✅ `run_algorithms.py` 已接入
- ✅ 算法/数据层已 push 至 origin main
- ✅ `index.html` UI 紧凑化 + `TOP3_TRACK.js` 注入已 push 至 origin main（`d05b2c18`）
- ✅ `guard_index_sections.py` 与 `v8_health_check.py` 护栏通过

---

## 五、给阿狸咪的交接说明

1. **Top3 追踪盘已上线**：算法层（`gen_top3_track.py`）+ 数据层（`TOP3_TRACK.js`）+ 前端渲染均已入库，`index.html` 已注入 `data/TOP3_TRACK.js`。后续由盘后算法链自动产出，无需手动干预。
2. **自动化精简**：已按主人要求暂停 2 个功能重叠的 automation（保留发现错误-自愈闭环）：
   - 已暂停：`小九-v8管线看门狗(每2h自动修复·紧急交接)`（被每小时紧急交接通道超集覆盖）
   - 已暂停：`小九-盘中云端任务定时触发+监控兜底`（被盘中实时数据刷新兜底覆盖）
   - 保留：`小九-v8每小时紧急交接通道(看门狗+自动修复)`、`小九-v8盘中实时数据刷新兜底(每30分)`
3. **IPO 上市后建议显示 bug（已修复）**：`update_v8.py::_sanitize_ipo_recommend` 已豁免 `status==='tracking'`/`'listed_today'`，不再把追入/首日建议覆盖成「不建议申购」。commit `c1ef3801` 已 push，同时升级了 IPO 情绪分因子。

---

## 2026-08-13 09:18 追加：港股/A股公平性改造（主人令）

### 改动点
1. **`algorithms/fundamental_helper.py`**
   - 移除 reason 含「港股」时的强制 -10 降权。
   - 缺失基本面数据（含港股暂无数据源）统一按中性 0 分处理。
   - 原则：市场来源本身不是负面信号；加分只给真实正面信号，扣分只给真实负面信号。

2. **`index.html` 候选池（`renderFinalCandInner`）**
   - 取消 A股/港股分组排序，统一按 `final_score` 综合分排序。
   - 移除橙色「⚠️已降权」标签。
   - 港股因暂无基本面数据源，显示灰色信息标签「数据待补」。
   - 标题/说明同步更新，不再出现「A股优先·港股已降权后排」。

3. **逻辑详解页（`index.html`「全站精选 - 说明」卡片）**
   - 新增「候选池排序与标签」条目。
   - 更新「基本面质量分」条目，写入公平性原则备忘。

### 影响范围
- `generate_top10.py` / `gen_cockpit_tier_recommend.py` / `gen_cockpit_advice.py` 均通过 `fundamental_helper.quality_points()` 读取基本面分，改造后港股质量分从 -10 升至 0。
- `final_recommend.py` 早在 2026-08-11 已设 `HK_PENALTY=0`，本次与其对齐。
- 候选池前端展示不再市场歧视，与 Top3 公平竞争逻辑一致。

### 给阿狸咪的交接
- 云端 runner 盘后执行 `run_algorithms.py` 时会自动继承 `fundamental_helper.py` 新逻辑；无需额外脚本改动。
- 若发现港股在候选池/Top10/驾驶舱排名明显上升，属预期行为（中性 0 分替代 -10 分），不是数据源异常。
- 健康检查中「全港股 Top3」等兜底告警仍保留，用于发现 akshare 港股接口异常导致的虚高。

---

*小九 2026-08-13 09:18 CST*
