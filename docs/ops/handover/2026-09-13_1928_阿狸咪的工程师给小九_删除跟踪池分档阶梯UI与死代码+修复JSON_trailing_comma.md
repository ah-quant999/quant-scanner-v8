# HANDOVER｜阿狸咪的工程师 → 小九｜2026-09-13 19:28｜删除跟踪池分档阶梯UI与死代码+修复JSON_trailing_comma

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

删除「跟踪池分档阶梯」UI 及其生成器死代码（`gen_backtest_all_algos.py` 的 `build_ladder`），并清理 `data/BACKTEST_ALL_ALGOS.js` 中的 `track_ladder` 字段。

---

## 正文

### 1. 删除原因

- 该表与上方「持有期档位矩阵」视觉重复，用户反馈「看不懂」。
- 数据稀薄：仅四量终极有数据，且只有 T+5（25.0% 胜率 / -4.24% 收益）、T+10（20.6% 胜率 / -6.21% 收益）两档有样本；T+20~T+90 全空。
- 前端删除 + 生成器删除后，下次 E 批运行不会再产出该字段。

### 2. 改动文件

| 文件 | 改动 |
|---|---|
| `index.html` | 删除「跟踪池分档阶梯」HTML 块；顶部注释「三个子块」改为「两个子块」；内联编号清理 |
| `algorithms/gen_backtest_all_algos.py` | 删除 `build_ladder()` 函数定义；删除 `main()` 中 `out["track_ladder"] = build_ladder(root)`；顶部注释更新 |
| `data/BACKTEST_ALL_ALGOS.js` | 删除 `track_ladder` 字段 |

### 3. 验证

- `htmlcheck.mjs`：25 段脚本 0 失败，标签配平 0 差。
- `data/BACKTEST_ALL_ALGOS.js` JSON 解析通过，无 `track_ladder`。
- 当前 main tip：`8d043e5469cec1a64e0815c096ed51c1c411de3f`。

### 4. 踩坑记录

第一次删除 `track_ladder` 时（commit `50a4e5ff`）， removal 逻辑未处理「被删 key 是对象最后一项」的情况，残留 trailing comma 导致 JSON 解析失败。已用 commit `8d043e54` 修复。后续手工从生成数据文件删 key 时，务必处理末尾逗号。

