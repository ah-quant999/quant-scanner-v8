# 交接：AI速览「ETF资金条」删除行业分类段 + 🔴 恢复被截断的 gen_market_brief.py

- **时间**：2026-09-17 18:40（小九白班）
- **来源指令**：主人截图「行业那个删除吧，我只要总额和流入流出TOP5」
- **推送 commit**：`3eefada427`（API 隔离推送，`force:false`，wave 1 快进）
- **改动文件（4 个）**：`algorithms/gen_market_brief.py`、`gen_market_brief.py`、`raw_data/ai_market_brief.json`、`data/AI_MARKET_BRIEF.js`

---

## 1. 一句话结论

ETF资金条按主人令删掉「行业ETF 净流入 +7.56亿」那一段（分类概览 + 分类兜底），只留
**全市场合计总额 ｜ 净流入TOP5 ／ 净流出TOP5**；同时**顺带救回一条 P0 隐患**——
main 上 `algorithms/gen_market_brief.py` 已被上一笔提交截断成没有 `main()` 的残缺桩，
云端下次跑会「退出码 0 但零产出」静默停更 AI速览，本批以完整版为基线恢复。

---

## 2. 主人可见的变化

| | 旧（16:31 线上） | 新（本批） |
|---|---|---|
| ETF资金条 | 全市场ETF合计净流出 -18.18亿 ｜ **行业ETF 净流入 +7.56亿** ｜ 净流入TOP5：… ／净流出TOP5：… | 全市场ETF合计净流出 -18.18亿 ｜ 净流入TOP5：… ／净流出TOP5：… |

「行业ETF 净流入 +7.56亿」为什么该删：该数字是 **ETF 分类「行业」的合计**（29 只行业类 ETF 加总），
而同一行的 TOP5 是**单只 ETF 榜**，两者不同源、量级不可比 —— 会读成「行业是 ETF 净流入第一」。
主人明确不要，直接下线。

---

## 3. 🔴 P0：被截断的生成器（本批最重要的一件事）

### 现象
`main` 上 `algorithms/gen_market_brief.py` 在提交 `e282c6d31a`（2026-09-17 16:46，上一批「分类标签」修复）
之后只剩 **18214 字节 / 388 行**，文件在 `_etf_cat_name` 的 `return _cat` 处即结束：

- 缺 `_strategy_signal` / `_top_real_concepts` / `_top_picks` / `build_strategy` /
  `get_market_status` / `build_closing_summary` / **`main()`** 共 7 个函数、456 行；
- `python -m py_compile` **通过**、直接执行 **exit=0 且零输出** ⇒ 不会报错、不会告警，
  `cloud_fetch_v8.py` 里那句 `⚠️ gen_market_brief 调用失败` 也捕不到 ⇒ **静默停更**。

### 对照数据
| 版本 | 字节 / 行 | 函数数 | `main()` |
|---|---|---|---|
| `fcba708dba`（09-17 10:50，最后完整版） | 41445 / 844 | 24 | ✅ |
| `e282c6d31a`（09-17 16:46，被截断） | 18214 / 388 | 17 | ❌ |
| 本批恢复后（`3eefada427`） | 42053 / 839 | 23 | ✅ |

### 处理
以 `fcba708dba` 完整版为基线恢复，再叠加本批主人令改动（见 §4）。
根目录那份同名孤儿副本 `gen_market_brief.py` 也同步为完全一致内容（**防再次改错文件**，见 §6 待办）。

### 防复发（本批已做）
推送脚本加入**完整性闸门**：脚本类文件推送前必须通过
`def main() 存在` + `不残留已删函数` + `CR=0` + 特征串 断言，任一不过即中止。
（本次截断点恰好落在函数体中间且语法自洽，纯靠 `py_compile` 无法发现，必须靠调用点断言。）

---

## 4. 代码改动（`algorithms/gen_market_brief.py`）

删除三处（连同唯一调用者一并删，不留死代码）：

1. `_etf_cat_name()` 函数定义（ETF 分类名 → 可读标签）
2. `cat_nets` 计算块（`etf_heat.categories` → 分类合计排序；`_relevant` 白名单随之删）
3. `_etf_parts` 里两段：
   - 分类概览：`if cat_nets and cat_nets[0][1] >= 5:` → 「%sETF 净流入 %+.2f亿」
   - 分类兜底：`elif len(cat_nets) >= 2 and cat_nets[-1][1] <= -3:` → 「%sETF 净流出 %+.2f亿」

保留：总额段（`total_net / 1e8`，红涨绿跌 `#ef5350/#26a69a`）、`净流入TOP5：`、`<br>净流出TOP5：`、
`signal: "green" if _etf_in5 else "red"`。`etf_heat` 参数仍被「3b. ETF 真实行业资金 TOP5」段使用，未动。

函数数 24 → 23（仅少掉被删的 `_etf_cat_name`），文件 844 → 839 行。

---

## 5. 验证证据（全部实测，非推断）

**① 本地真跑（真实数据链路复现）**
用仓库 `raw_data/*.json`（09-17 16:42 批次）执行改后生成器：
`状态: 收盘 | 风向: 情绪震荡 | 涨跌比 0.97 | 异动 5 条 | 策略 2 条`

**② 新旧产物逐条对比**
```
#0 [ETF资金]  文本一致=False   ← 唯一变化
#1 [概念热点] 文本一致=True
#2 [行业资金] 文本一致=True
#3 [个股异动] 文本一致=True
#4 [个股异动] 文本一致=True
策略/指数/情绪/健康 一致: True True True True
```
ETF 条断言：含「行业ETF」=False、分类段=False、总额=True、净流入TOP5=True、净流出TOP5=True、`｜`=1 个。

**③ 线上真身（raw.githubusercontent main）**
- `algorithms/gen_market_brief.py` = 42053 B / 839 行 / CR=0 / `def main()`=True / `def _etf_cat_name`=False / 语法 OK 23 函数
- `data/AI_MARKET_BRIEF.js` = 5306 B / CRLF=0 / 含「行业ETF」=False / 总额+两行 TOP5 齐
- `raw_data/ai_market_brief.json` = 5240 B / `gen_time = update_time = 2026-09-17 18:25:56`（过 CI 跨层一致性门禁）

**④ GitHub Pages 站点**
`data/AI_MARKET_BRIEF.js` = 5306 B，`行业ETF` 命中 **0** ⇒ 主站刷新即见新口径。
CI 已基于 `3eefada427` 触发：🛡️ 缓存戳实时对齐 / ☁️ 构建部署 / pages build。

---

## 6. 待办 / 请主人拍板

1. **根目录同名孤儿副本 `gen_market_brief.py`**：被 git 跟踪，但**全仓无任何引用**
   （唯一调用点是 `cloud_fetch_v8.py:4256` 的 `ROOT/"algorithms"/"gen_market_brief.py"`），
   且其 `ROOT = BASE/..` 逻辑放到根目录执行会读上一级 `raw_data` ⇒ 本就不适合在根目录跑。
   本批已把它同步为与权威版一致（消除「两份不一致」这一隐患），**是否直接删除此副本待主人一句话**。
2. `data/AI_MARKET_BRIEF.js` 的 `?v` 缓存戳由云端「缓存戳实时对齐」工作流维护，
   本批不手改 `index.html`（避免与云端 churning 冲突）。

---

## 7. 给接班机（阿狸咪）的操作提示

- 本文件今天被**单文件 API 推过多次**；`main` 真身请用
  `curl -s https://raw.githubusercontent.com/ah-quant999/quant-scanner-v8/main/algorithms/gen_market_brief.py` 取，
  **不要相信本机工作树里那份**（本机该文件曾长期是 388 行残缺桩，正是本次 P0 的来源）。
- 该脚本**不能靠 `py_compile` 判完整**：截断点语法自洽、执行零输出。判据用
  `grep -c "def main()"` + 函数数应为 23。
- 不要跑 `update_v8.py`（任何参数）：其 `main()` 开头会执行 `v8_ws_sync_guard.py --heal`，
  会把本机与远端不一致的脚本 `git checkout` 拉齐 ⇒ 会覆盖你在本机的未推送改动。
