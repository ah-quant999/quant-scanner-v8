# HANDOVER｜阿狸咪的工程师 → 小九｜2026-11-14 21:28｜market_regime缺macro_json连续4轮自举失败

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

algo 链 `market_regime.py` 因缺 `out/macro.json` 自举失败（`fetch_macro.py` 退出码 1 且 stderr 为空），11-14 已连续 4 轮实证（06:27 chain-end 首现 → 10:06 schedule run 43544426183 → 13:39 schedule run 43562549536 → 14:40 chain-end 18:05:01 fail=3 再现），`data/MARKET_REGIME.js` 停更 >39h（update_time=2026-11-13T06:07:29）。按铁律未派发未重试（algo 20:27 已有 in_progress 轮 43594897073 会自然复现），挂账 `market-regime-macro-json-bootstrap-fail-1114`（P1/todo/owner=你）催办。

---

## 正文

### 实证（全部远端 API 实核，2026-11-14 21:19–21:29 CST）

| 轮次(CST) | 证据 | 结果 |
|---|---|---|
| 11-14 06:27:40 | chain-end run_report（run_start 03:46:13） | fail=3 首现 market_regime |
| 11-14 10:06 | schedule run 43544426183 | failure（🛡 结果问责步） |
| 11-14 13:39 | schedule run 43562549536 | failure（🛡 结果问责步） |
| 11-14 18:05:01 | chain-end run_report（run_start 14:40:13，ok=43 fail=3） | market_regime 再现 |

run 日志原文（run 43562549536）：

```
market_regime.py  (17:19:55)  [监督执行·静默杀≥15min]
[market_regime] 缺 /home/runner/work/quant-scanner-v8/quant-scanner-v8/out/macro.json，自动先跑 fetch_macro.py 自举依赖…
[market_regime] fetch_macro.py 退出码 1:   （stderr 为空，无栈帧）
[market_regime.py ← 退出码 1 | 自举 fetch_macro.py 后仍不存在，放弃
```

### 产品影响

- `data/MARKET_REGIME.js` update_time=**2026-11-13T06:07:29**，截至 11-14 21:20 停更 >39h（raw_data/market_regime.json 同步停更）。
- 同报告 fail=3 中 `fetch_citic_pe.py`「增量无数据，退出」：11-11 21:53 单轮首现后 11-14 18:05 报告再现 ⇒ 复现级观察项。fetch_macro 退出码 1 且 stderr 为空，疑与 citic_pe 同为**上游数据接口静默失败**，建议根因排查时一并核。
- 已知非问题：`refresh_kline_freshness` / `fetch_multiyear_kline` 超时=软闸基线（连续多轮原样），不属本件。

### 不代修的理由 + 请你完成（一劳永逸口径）

1. 根因未定位：fetch_macro.py 退出码 1 且 stderr 为空，日志无死因；算法链产物口径属小九落码域。请先在 runner 环境手动复跑 `fetch_macro.py` 抓真实栈帧（**修复已生效最强判据 = 失败栈帧里出现修复符号**）。
2. 若上游接口确死：换源或降级产物口径，在数据生成层修，**禁前端硬编/占位壳**。
3. 修复推 main 后核：algo 链下一轮 run **head_sha ≥ 修复提交 sha** 且 run_report `failed_scripts` 不再含 market_regime（**看产物不看 run conclusion**）；`raw_data/market_regime.json` 与 `data/MARKET_REGIME.js` update_time 前进。

HANDOFF.yaml 已同步（item `market-regime-macro-json-bootstrap-fail-1114`，status=todo，owner=小九机AI），ledger 已同批用仓内唯一口径 `scripts/handoff_ledger_hash.py` 的 `content_hash` 重算，本件与 HANDOFF 同一提交推送（Git Data API 六步，base=4e556d84de blob）。
