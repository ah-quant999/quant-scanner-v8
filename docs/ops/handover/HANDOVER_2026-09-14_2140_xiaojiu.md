# 交接 · 波浪研报数据源解耦（阿狸咪零 westock 出报告）

**时间**：2026-09-14 21:40（小九）
**触发**：主人将「A股波浪定位」紧急交接给阿狸咪，但阿狸咪机**无 westock 连接器** → 原 `a-share-elliott-wave-report` skill 现场取数失败，无法产出/更新报告。
**结论**：已做数据/渲染解耦，阿狸咪 `git pull` + 跑脚本即可出报告，**零金融连接器依赖**。

---

## 一、改了什么（4 文件，已推 main）

| 文件 | 作用 | 谁维护 |
|---|---|---|
| `data/WAVE_ELLIOTT.js` | 客观数据层（注入 `window.WAVE_ELLIOTT`）：上证日线序列 646 交易日 + 6 浪型拐点 + 5 指数对照 | 小九 / weekend cron 用 westock 拉取覆盖 |
| `v8/wave_report_template.html` | 研报模板（内嵌主观研判文案，读 `window.WAVE_ELLIOTT`） | 小九（研判更新时改） |
| `v8/gen_wave_report.py` | 渲染脚本：读数据 + 模板 → 出 `out/A股波浪定位-YYYYMMDD.html` | 小九 |
| 本交接文档 | — | — |

> 原 `out/A股波浪定位-20260914.html` 保留为历史快照（现已由脚本重生成，内容一致）。

## 二、阿狸咪操作流程（零 westock）

```bash
cd quant-scanner-v8
git pull
python v8/gen_wave_report.py
# 产出 out/A股波浪定位-YYYYMMDD.html，浏览器打开（需联网加载 ECharts CDN）
```
- 脚本自带数据完整性校验（dates/closes 长度、marks/idx 非空），残缺数据会拒出并报错。
- 不需要任何金融 MCP 连接器，不依赖通达信接口。

## 三、数据更新责任（小九 / weekend）

1. 用 westock 重拉：上证日K（`data_kline` sh000001 day）、5 指数日K（sh000300/sz399006/sz399001/sh000688）、估值/广度（`data_market_overview`）。
2. 覆盖 `data/WAVE_ELLIOTT.js` 的 `series.dates / series.closes / marks / idx` + 更新 `meta.date`。
3. `git push`（推 data/ 即可，阿狸咪次日 pull 重跑脚本即得新版）。
4. 主观研判（浪型计数/情景概率/目标位解读）若需调整，改 `v8/wave_report_template.html` 文案并推。

## 四、双机注意事项

- 本批只动 `data/` + `v8/` 两个**新文件**，**不碰 `index.html` 热文件**，与阿狸咪夜间部署无冲突。
- 推送走隔离索引单文件推送（raw-tree-push），范围守卫确认仅本批文件，无 raw_data 泄漏。
- 主站大盘观察卡的「斐波那契校验·艾略特波浪四铁律」仍读 `window.SH_FIB`（客观四铁律，自动），与本研报解耦，互不影响。
- 阿狸咪机若后续接入 westock，可恢复直接用 `a-share-elliott-wave-report` skill 现场出报告（本解耦方案作为无连接器时的兜底）。

## 五、验证记录

- `python v8/gen_wave_report.py` → 产出 `out/A股波浪定位-20260914.html`（20905 字节）✅
- 模板内联 script `node --check` 通过 ✅
- `data/WAVE_ELLIOTT.js` JSON 解析 OK（序列 646 / 拐点 6 / 指数 5 / 日期 2026-09-14）✅
- 提交：`0a9d8f15f`(大盘观察卡) → 本次解耦提交（见 git log）
