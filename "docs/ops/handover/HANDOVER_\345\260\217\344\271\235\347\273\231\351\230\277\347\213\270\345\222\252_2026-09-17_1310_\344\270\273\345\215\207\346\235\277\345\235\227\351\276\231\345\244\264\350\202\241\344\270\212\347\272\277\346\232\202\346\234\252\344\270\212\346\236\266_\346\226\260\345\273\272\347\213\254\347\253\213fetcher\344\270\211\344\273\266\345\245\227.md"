# HANDOVER · 小九 → 阿狸咪
## 2026-09-17 13:10 · 主升板块 → 龙头股（实时）上线「暂未上架」

---

## 一、本次改动（主人令）

> 「这个主升有没有龙头股或者推荐股，要不不知道买什么。放到暂未上架」
> 附「板块资金趋势」卡截图（主升 1 个板块：**元件**）

**需求解读**：原卡「主升」档只给板块名 + 涨幅（元件 5日 +10.2% / 20日 +10.5%），
看不出该买哪只 ⇒ 在「暂未上架 > 观测类 > 概念/行业 → ETF·龙头 参考」卡下方
新增「🚀 主升板块 · 龙头股」块。

**主人拍板的四个口径**（AskUserQuestion 逐一确认）：

| 项 | 决定 |
|---|---|
| 板块范围 | **只显示「主升」档**（不含启动/震荡/退潮/底部） |
| 每板块股数 | **5 只** |
| 排序依据 | **板块内当日涨幅降序** |
| 数据来源 | **新建轻量 fetcher** |
| 落点 | **只放「暂未上架」页**（不进盘后页原卡） |
| 更新时机 | **盘后跑一次**（跟随算法链 A 批） |
| 展示形式 | **板块行内并列** |

---

## 二、三件套（均已推送 main）

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/fetch_sector_leaders.py` | 🆕 新增 10247 B | 抓取器 |
| `data/SECTOR_LEADERS.js` | 🆕 新增 867 B | 前端注入 `window.SECTOR_LEADERS` |
| `index.html` | ✏️ 修改 1257616 B | 追加 `window._fillSectorLeaders()` |
| `algorithms/run_algorithms.py` | ✏️ 修改 90160 B | A 批接入（紧跟 `fetch_sector_rs.py`） |

**提交记录**
- `9cfd099baf84` — 主升板块·龙头股（index.html + SECTOR_LEADERS.js + fetcher）
- `4ce3379ef0ae` — A 批接入 fetch_sector_leaders.py

**线上核验（硬抓 Pages，非状态推断）**
```
① 仓库真身
   index.html 1257616 B  含 _fillSectorLeaders ✅  sectorLeadersBox ✅
   BUILD = f782d78dc（未被回退）✅
   data/SECTOR_LEADERS.js 867 B ✅   scripts/fetch_sector_leaders.py 10247 B ✅
② Pages 主站 https://ah-quant999.github.io/quant-scanner-v8/
   HTTP 200  1060255 B  含新块 ✅
   data/SECTOR_LEADERS.js HTTP 200 731 B ✅（真实数据）
```

---

## 三、数据链路（🔴 关键，接手必读）

```
data/SECTOR_RS.js（同花顺 90 个行业板块，pct_5d/pct_20d）
        │
        │  阶段判定 v2（三处必须逐字一致！）
        │  主升 = pct_5d > 3 且 pct_20d > 5
        ▼
scripts/fetch_sector_leaders.py
        │
        ├─ ① 东财全量行业板块（496 个）→ {板块名: BK码}
        │     https://push2delay.eastmoney.com/api/qt/clist/get
        │     ?pn=N&pz=100&fs=m:90+t:2&fields=f12,f14,f3
        │
        ├─ ② 同名映射：同花顺板块名 → 东财 BK 码
        │     ⚠️ 只做**同名精确匹配**，禁模糊匹配
        │     实测依据：同花顺「元件 881270」63 只
        │               东财「BK0459 元件」67 只
        │               交集 62 只（重合率 98.4%）⇒ 同名即同股
        │
        ├─ ③ 板块成分股（按当日涨幅降序取前 5）
        │     ?pn=1&pz=400&fs=b:BK0459&fields=f12,f14,f2,f3,f62
        │
        ▼
raw_data/sector_leaders.json  →  data/SECTOR_LEADERS.js
        │
        ▼
index.html :: window._fillSectorLeaders(cEl)
        由 _fillEtfMap() 在其渲染完既有列表后调用
        容器：#dbgEtfMapBody（append，不覆盖既有 ETF 映射列表）
```

### 🔴 三条铁律

1. **阶段判定规则三处逐字一致**：`index.html renderSector()` /
   `algorithms/fetch_sector_rs.py::_phase_of()` / `scripts/fetch_sector_leaders.py::_phase_of()`。
   改一处必改三处，否则该块与卡上「主升」数不符。

2. **CPU 接口选型**：`push2.eastmoney.com` 在本机被拒（`RemoteDisconnected`），
   **只有 `push2delay.eastmoney.com` 可用**。与 `cloud_fetch_v8.py` 同源。

3. **同名映射禁模糊**：模糊匹配会把「元件」错配到东财「印制电路板 BK1340」
   （二者交集 48/48，BK0459 内含 BK1340），给出**完全错误的票**。
   名字对不上 ⇒ 跳过该板块（宁可缺，不可错）。

---

## 四、护栏设计（防孤儿死卡）

| 场景 | 行为 |
|---|---|
| `window.SECTOR_LEADERS` 不存在 | **整块不渲染**（连标题都不出） |
| 今日无主升板块（`sectors: []`） | 同上，**不显示空壳** |
| 板块有但 `leaders` 为空 | 同上 |
| 某板块名对不上东财 | 跳过该板块，其余照常 |
| 成分股拉取失败 | 跳过该板块，其余照常 |

新增块 `append` 到容器末尾，**不覆盖**既有 ETF 映射列表。

---

## 五、验证记录（全部实测通过）

### 真实渲染验证（Node vm + 真实数据）
```
抽出函数体 3108 字符；真实数据载入 sector_count=1
✅ 含标题 主升板块      ✅ 含 龙头股
✅ 含板块名 元件        ✅ 含第 1 名 澳弘电子
✅ 含第 5 名 崇达技术    ✅ 涨幅带 %
✅ 红涨用 --up         ✅ 含免责声明
✅ 不含 undefined      ✅ 不含 NaN      ✅ 不含 [object
序号 1-5 出现次数 = 5 (期望 5)
```

### 边界验证（防孤儿死卡）
```
✅ 无 SECTOR_LEADERS            → 产出 0 字符
✅ SECTOR_LEADERS 无 sectors    → 产出 0 字符
✅ 主升板块为空数组（今日无主升）  → 产出 0 字符
✅ 板块有但 leaders 空           → 产出 0 字符
```

### 语法与结构
```
内联 <script> 块 = 28 个，共 929201 字符，语法错误 0 个
标签配平：所有 tag 差值变化 = 0（未引入新缺口）
  新增块自身：<div> 6/6 ✅  <span> 11/11 ✅
行尾：index.html LF ✅  SECTOR_LEADERS.js LF ✅  fetcher LF ✅
```

---

## 六、当前线上真实数据（13:10）

```json
{
  "update_time": "2026-09-17 12:55:52",
  "data_date": "2026-09-16",
  "phase": "主升",
  "sector_count": 1,
  "sectors": [{
    "name": "元件", "bk": "BK0459",
    "pct_5d": 10.21, "pct_20d": 10.52, "cons_count": 67,
    "leaders": [
      {"code":"605058","name":"澳弘电子","price":48.76,"chg":9.99},
      {"code":"002579","name":"中京电子","price":20.36,"chg":3.61},
      {"code":"603115","name":"海星股份","price":94.65,"chg":3.26},
      {"code":"603920","name":"世运电路","price":44.03,"chg":2.95},
      {"code":"002815","name":"崇达技术","price":23.94,"chg":2.40}
    ]
  }]
}
```

---

## 七、给阿狸咪的注意事项

1. **不要删 `data/SECTOR_LEADERS.js`**（新文件，前端在读 `window.SECTOR_LEADERS`）。
2. **不要改 `run_algorithms.py` A 批里 `fetch_sector_leaders.py` 的位置**——
   必须紧跟 `fetch_sector_rs.py` 之后（前置依赖）。
3. 若发现该块在页面上不显示：先查 `window.SECTOR_LEADERS` 是否 undefined，
   再查 `data/SECTOR_LEADERS.js` 是否 404。
4. 该块是**新增观测项**，独立链路，失败不影响任何现有卡片。
5. 页面路径：主站 → **暂未上架** → 「📌 概念/行业 → ETF·龙头 参考」卡**下方**。

---

## 八、本次推送遇到的坑（供后续参考）

### 基线漂移（CI 高频 churning）
制备补丁时基线 `f782d78dcc23`，推送时已是 `f37c4b16ab33`（CI 在 12:51 推了
`v8 build` 版）。**差异审计**：107 行改动中 105 行是 `?v=` 缓存戳、
1 行是 `BUILD` 短 SHA、0 行实质逻辑差异 ⇒ 换基线重打即可，不影响补丁逻辑。

**做法**：隔离单文件推送（`blob → tree(base_tree=tip) → commit(parents=[tip])
→ PATCH ref{force:false}`），**禁 force push**；推前重取 tip、推后核验
`FETCH` 真身。**不要拿旧基线的 index.html 强推**，那会回退 CI 注入的 `?v=`/BUILD。

### Windows 行尾陷阱
Python `io.open(..., "w", encoding="utf-8")` 在 Windows 上会把 `\n` 写成 `\r\n`
⇒ **`data/*.js` 必须二进制写**（`open(..., "wb")`）。已在推送脚本里加
`real_eol == "LF"` 断言拦截（第一次就是这样拦下的）。

---

**状态：✅ 全部完成，线上已生效**
