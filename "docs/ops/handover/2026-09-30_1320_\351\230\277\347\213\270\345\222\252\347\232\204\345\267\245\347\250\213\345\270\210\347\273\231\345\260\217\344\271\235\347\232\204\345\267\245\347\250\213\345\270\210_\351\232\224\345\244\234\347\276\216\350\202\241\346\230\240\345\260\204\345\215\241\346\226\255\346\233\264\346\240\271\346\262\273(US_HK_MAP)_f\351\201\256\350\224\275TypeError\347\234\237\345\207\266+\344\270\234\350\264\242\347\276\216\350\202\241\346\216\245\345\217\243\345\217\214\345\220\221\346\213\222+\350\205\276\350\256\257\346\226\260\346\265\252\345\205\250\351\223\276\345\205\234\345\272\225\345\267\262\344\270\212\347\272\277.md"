# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-09-30 13:20｜隔夜美股映射卡断更根治(US_HK_MAP)_f遮蔽TypeError真凶+东财美股接口双向拒+腾讯新浪全链兜底已上线

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

「🌙 隔夜美股强势·映射 A/港股」卡冻结在 09-28 09:20 的真凶是 **09-29 断更根治补丁自带的 `_f` 变量遮蔽 TypeError**（闸门 `as _f` 覆盖了模块级 float 转换函数），叠加**东财美股 ulist 接口 09-28 起对本机与云端同时拒绝**；已修复遮蔽 + 新增腾讯报价+新浪日K全链兜底（86/86 实测、口径逐位对齐），主站已恢复（update_time=2026-09-30 13:09:04，commit `7b52b0a616`）。

---

## 正文

### 1. 根因链（两层，缺一不会断）

1. **致命层（代码 bug，任何机器必炸）**：09-29「断更根治」补丁在 `scripts/fetch_us_hk_map.py` 闸2（今日已产出检查）写了 `with open(...) as _f:` —— 把模块级 `_f()`（float 安全转换，L170）**遮蔽成文件对象**且 with 块结束后不恢复 ⇒ 此后 build() 内所有 `_f(...)` 调用 `TypeError: '_io.TextIOWrapper' object is not callable`。
   - 铁证：09-30 08:47 云端 premarket run（36651983480）日志 L448 栈帧 `"price": _f(row.get("f2"))`。
   - 该 bug 在**任何机器**（云端/小九/本机）、**东财通不通**都必炸 ⇒ 09-29 小九的三档化+锚兜底全被它废掉（假修复）。
2. **背景层（数据源，兜底动机）**：东财美股 ulist（push2delay/push2 系）09-28 09:20 后对本机（中国家宽直连）与云端（GHA 美国机房）**同时** RemoteDisconnected（双侧实测）；A 股 52 周新高（W52_HIGH）同轮也失败，但 SH_SZ/CAPITAL_FLOW 等正常 ⇒ 东财部分接口收紧，美股 ulist 全拒。原兜底只覆盖三大指数锚，86 只明细全空 ⇒ items 空 ⇒ return None ⇒ 不覆盖旧产物（该防护工作正常）⇒ 卡面冻结。

### 2. 修复内容（commit `7b52b0a616`，4 文件原子推送）

| 文件 | 改动 |
|---|---|
| `scripts/fetch_us_hk_map.py` | ① `as _f` → `as _prev_fh`（遮蔽根治）；② 新增腾讯报价 `_tx_quotes`（qt.gtimg.cn，p[1]/p[3]/p[32]/p[30]）+ 新浪日K `_sina_closes`（US_MinKService.getDailyK num=3000 一次全量、末根=最近收盘日）+ `_mom_from_closes`（dN=c[-1]/c[-1-N]-1，**末根日期≠腾讯报价美东日期则整体 None** 护栏）+ `_resolve_tx`（造东财同构伪行，下游零改动）；③ `resolve()` 对东财未命中差集自动降级（部分命中只补缺失）；④ gate 透明新增 `us_tx_fallback`/`us_source`，note 兜底声明 |
| `raw_data/us_hk_map.json` | 今日实测产物（update_time=2026-09-30 13:09:04，86 标的/strong 9/data_date=09-29） |
| `data/US_HK_MAP.js` | 同步重生成（update_v8 同构格式） |
| `index.html` | 仅 `US_HK_MAP.js?v=a5bc52af51` → `?v=b66b9f4513`（**以远端 blob 为基替换**，其余逐字节不动） |

- **口径硬证据**：新浪以 09-25 为端点复算 BABA 六周期 = 东财 09-28 产物 mom **逐位一致**（-0.8/-5.65/-3.09/0.4/-5.65/11.99）。
- **实测**：本机 build() 95.7s，adr_ok=31/31、etf_ok=55/55、tgt_missing=0（腾讯中文名过闸门零剔除）、us_tx_fallback=83/86。
- **主站实锤**：Pages index `?v=b66b9f4513`；US_HK_MAP.js update_time=2026-09-30 13:09:04；`v8_build_deploy` CI success。
- **防复发**：闸2「今日已产出跳过」语义不变 ⇒ 今日剩余各档（盘中/盘后）自动跳过；**明早 08:25 premarket 起云端全自动接管**（云端东财不通 ⇒ 自动腾讯+新浪兜底出货），单点消除、不依赖小九在线。

### 3. 请小九复核（4 项）

1. **明早首轮确认**：10-01 08:25 premarket 后 `raw_data/us_hk_map.json` update_time 变 10-01 且 `gate.us_source=tencent+sina...`（或东财若恢复则 eastmoney）⇒ 云端自愈闭环成立。
2. **authornames**：本批 US_HK_MAP 挂三档（09-29 你做的）语义正确；闸1（ET 盘中拒产出）/闸2（当日已产出跳过）我未改动逻辑，仅修遮蔽名。
3. **W52_HIGH 同轮失败**（push2 5 次重试仍空）：不在本次范围，但同属东财收紧嫌疑，建议下轮巡检盯它的卡（52周新高广度）是否也在退化。
4. **兜底行 f13=""**：`us_secid`/targets `secid` 会成 `.BABA`/`.513050` 形态 —— 前端已 grep 实证零消费，仅产物字段形态变化，知会即可。

### 4. 风险与边界

- 新浪 `US_MinKService.getDailyK` 为老接口（无鉴权），若日后失效 ⇒ 动量字段自动 None（护栏），报价/名称/涨跌仍出（腾讯），卡片降级不断更。
- 腾讯美股覆盖个别冷门 ETF 可能缺（本次 86/86 全命中，暂无缺失；缺失者诚实计入 gate，不编造）。
- 云端验证轮（05:15:59Z dispatch premarket）应见「今日已产出 → 跳过重抓」而非 TypeError —— 这就是遮蔽根治的运行态证明。
