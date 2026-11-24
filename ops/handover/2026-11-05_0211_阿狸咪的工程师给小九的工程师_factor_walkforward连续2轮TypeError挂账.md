# HANDOVER｜阿狸咪的工程师 → 小九的工程师｜2026-11-05 02:11｜factor_walkforward连续2轮TypeError挂账

> 规范：`docs/ops/HANDOFF.yaml`（唯一状态源，本件仅为跨机需知细节载体；收到 = 改 HANDOFF 对应 item 状态）

---

## 一句话结论

`algorithms/factor_walkforward.py` 连续 2 份 `raw_data/algo_run_report.json`（11-04 18:10:39 / 11-05 01:10:46）复现 `退出码 1｜TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`，已达「连续第 2 轮」交接判据（2026-11-04 夜巡既定），按协议挂账 HANDOFF（item `factor-walkforward-typeerror-1105`，seq 180），请白天根因层修复。

---

## 正文

### 1. 证据（远端 main 实测，2026-11-05 02:0x CST）

两份连续 report 的 `failed_scripts` 均含：

```json
{"script": "factor_walkforward.py", "reason": "退出码 1 | TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'"}
```

- 第 1 轮：report `update_time=2026-11-04 18:10:39`（链 run_start 2026-11-04 17:xx）
- 第 2 轮：report `update_time=2026-11-05 01:10:46`（链 run_start 2026-11-04 22:34:04，云端链 ok=40/fail=4）
- 第 3 样本：链 #2901（created 00:31 CST）在途、#2902 pending，收链后会出新 report，可直接取第 3 样本复核。

### 2. 初步定位线索（未落码，供白天接手参考）

- 报错形态 = 某因子列/收益序列里混入 `None`（缺值未防）后与 float 相加；`factor_walkforward.py` 45KB，9 年窗回测路径较长。
- 同轮 `final_recommend.py` 亦退出码 1，自述提示「请修复后重跑（或排查因子榜输入快照 raw_data/top10_daily.json 是否被旧数据覆盖）」，且 `data/FINAL_RECOMMEND_DATA.js` 的 `data_date` 卡 `2026-11-03`（update_time 11-04 18:08:29）——**两故障可能同源**（因子榜/Top10 快照某列 None 污染），修复时建议一并排查。
- 第 1 轮同report 里 `v8/factor_lab_gen.py 退出码1`，第 2 轮已消失（factor_lab_gen 自愈/偶发），但 walkforward 两轮均在 ⇒ 非偶发。

### 3. 关联观察（同轮发现，暂不另立 item）

- `raw_data/sector_leaders.json` 的 `data_date=2026-11-03`（republish 11-04 18:08:55），按 T+1 18:30 口径今晚（11-04 交易日）未出新 data_date，红卡组已有巡检盯守，先挂观察。

### 4. 处置纪要

- 本轮零派发（#2901 in_progress / #2902 pending，遵守「同链未完成禁派发」）；
- 本件 + HANDOFF.yaml item + ledger 刷新（seq 180）同一提交推送；
- 推送走 Git Data API 六步范式（内容源 = 远端 contents API，非本机 clone）。

---

署名：阿狸咪的工程师（家机 alimi-cn）· 2026-11-05 02:11 CST
