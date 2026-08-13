# HANDOVER：Top3 90 天滚动追踪 + 个股卡片 UI 紧凑化

> 生成时间：2026-08-13 08:33 CST  
> 主人决策：finalRec Top3 来源 / 入池即持仓 90 天滚动 / 回测+跟踪两行紧凑 / 小九全部负责  
> 红线遵循：**`index.html` 未直接 commit**，改动已整理为 patch 文件，由阿狸咪/主人合并。

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

包含：
- `algorithms/run_algorithms.py` 改动
- `update_v8.py` 改动
- `algorithms/gen_top3_track.py`（新文件）
- `index.html` 改动（UI 紧凑 + script 注入）

---

## 二、如何应用

### 算法/数据层（可立即应用）

```bash
cd E:/workspace/quant-scanner-v8
# 1. 应用 patch（自动跳过 index.html 部分冲突，需核对）
git apply --check docs/ops/handover/HANDOVER_小九_2026-08-13_Top3_追踪.patch
# 若无冲突：
git apply docs/ops/handover/HANDOVER_小九_2026-08-13_Top3_追踪.patch

# 2. 单脚本验证
python algorithms/gen_top3_track.py

# 3. 确认 raw_data/top3_track.json + data/TOP3_TRACK.js 已生成
ls -l raw_data/top3_track.json data/TOP3_TRACK.js
```

### index.html 部分（阿狸咪确认后合并）

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
- ⚠️ `index.html` 未 commit，patch 待应用
- ⚠️ 新文件 `algorithms/gen_top3_track.py` 未提交（当前为 untracked，在 patch 中）

---

## 五、部署注意事项

- `data/TOP3_TRACK.js` 后续由算法自动产出，首次需要把 `data/TOP3_TRACK.js` 与 `raw_data/top3_track.json` 一起推 main。
- `index.html` 的 cache-buster `v=20260813082900` 需与 `TOP3_TRACK.js` 真实更新时间对齐；后续由 `update_v8.py` 自动重写为最新 mtime。
- 盘后算法链跑完后，HEALTH_CHECK.js 会自动把 `TOP3_TRACK` 纳入监控；目前若前端不加卡片，健康检查只会把它当作普通数据文件判陈旧。

---

*小九 2026-08-13 08:33 CST*
