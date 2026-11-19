# HANDOVER｜阿狸咪的工程师 → 小九｜2026-11-19 23:41｜eqbond未双登记+intraday文档行回归_align_logic_ops连败12轮

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论



---

## 正文

# HANDOVER｜阿狸咪的工程师 → 小九｜2026-11-19 23:41｜eqbond未双登记+intraday文档行回归 align_logic_ops连败12轮

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

build_deploy 自 21:06 CST 起 [4/8] align_logic_ops 连败 12+ 轮未收敛：①新链 v8_eqbond_attraction（20:47 上线）既未登记 MUST/ALLOW 名单也未文档化；②v8_intraday_precise_sched 今日 13:11（d5b9646373）已双登记的文档行在远端 index.html / logic.full.html 中已归零（疑似晚间 eqbond 卡片/缓存戳编辑覆盖）＝当日先例回归。**Pages 部署本轮实证未停摆**（线上 data/*.js 与 HEAD 对齐：EQBOND 23:21 / EXPERIMENT 22:46），受阻的是 build_deploy 自身一体链路；主站 200 / 产物全鲜活、用户端无感。已按唯一状态源协议在 HANDOFF.yaml 挂账（eqbond-intraday-docregress-block-1119，P1/todo，owner=小九），同提交刷新 ledger。

---

## 正文

### 证据链（全部远端 API / 主站硬抓实测，本机工作树零触碰）

- build_deploy（wf 324135263）21:06-23:27 CST failure 连续 12+ 轮，最新 run 44553694027（head 18650f07c1）：
  gate success，build job 死于 step[10]「🛡️ Pre-deploy audit」[4/8] align_logic_ops，其余项全绿（含 [13/13] ledger 锚）。
  两条未对齐项：① v8_eqbond_attraction 有 cron 但未登记/未文档化；② v8_intraday_precise_sched 有 cron 但文档源未文档化。
- 名单实测：远端 align_logic_ops.py MUST_HAVE_CRON 含 v8_intraday_precise_sched（L76）、不含 eqbond；ALLOW 亦无 eqbond。
- 文档实测：远端 index.html、logic.full.html 对 v8_intraday_precise_sched 提及次数均为 0；eqbond 同为 0。
  而今日 13:11 小九侧已双登记（见 item intraday-precise-sched-align-block-1119 evidence：sec-op L8588-8589 + 逻辑页 L8700-8710）
  ⇒ 判「晚间编辑覆盖丢失」，属同日回归。
- 部署未停摆实证：线上 data/EQBOND_ATTRACTION.js ut=23:21:07、data/EXPERIMENT.js ut=22:46:53，
  与 raw API HEAD 内容一致 ⇒ Pages 走分支构建正常；与午间先例（部署真停摆）影响面不同。
- 产物新鲜度（raw_data，23:41 实测）：experiment.json 22:46 / sector_leaders.json 18:29（data_date 11-18，T+1 18:30 口径合规）/
  algo_heartbeat.json 22:55 ok=43 fail=4（refresh_kline_freshness 超时、fetch_multiyear_kline 超时、
  factor_lab_gen 退出码1「接收数据异常」、fetch_citic_pe 退出码1「增量无数据」＝既有软故障族，无新增系统性事故）。
  主站 200 / 1,419,447B。

### 处置边界

- 23:27 已入阿狸咪夜间窗口且距对方最后人工迭代（20:47 eqbond 上线系列）超 2.5h、门禁未收敛 ⇒ 按铁律挂账出件。
- 不代改 index.html / 文档源 / MUST vs ALLOW 名单意图面（防踩踏；登记语义须登记方拍板）。
- 修复建议按 intraday-precise-sched-align-block-1119 同一先例双登记；intraday 文档行回补或按 09-09 主人令口径
  「文档与名单两边取其一收口」。

### 验收（verify_how）

修复后最新 build_deploy 轮 build job 全绿且 [4/8] align_logic_ops EXIT 0；站上 index.html / logic.full.html
能检索到 v8_eqbond_attraction 与 v8_intraday_precise_sched；数据链产物继续鲜活。
