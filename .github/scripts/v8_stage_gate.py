#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 批次闸门（唯一决策点）—— 2026-09-10 主人令「一劳永逸·简化优化·不缺档·不抢跑」

■ 这个脚本解决什么（09-10 事故根因，两条都实测过）
  ① 旧逻辑按 CST 小时「盲猜」批次（16/17→A 18/19→B 20→D 21→E），
     21:00 的 E(回测) 触发时完全不管 B(选股)/D(汇总) 跑没跑，拿凌晨陈旧数据跑回测
     → 「最终推荐被回退」；查得 A/B/D 三批当日从未真跑。
  ② 更深一层：本仓库 GitHub Actions 的 schedule(cron) 实测约 95% 不触发
     （09-10 全天 v8_algo_cloud 14 个 run 里 13 个是 workflow_dispatch，
       intraday_snapshot 应 42 次只触发 1 次）。所以「哪天跑、跑哪批」绝不能靠钟点，
     只能靠**产物内容**判定。

■ 本脚本 = 唯一决策点（替代：按小时盲猜 / 静默闸门V5 / 探针路由 三层历史设计）
  1) 先定「今天该不该跑、跑哪个数据日」——用统一交易日历 v8_date：
       交易日            → 数据日=今天，盘后产出须 >= 16:30
       周六 / 假期首日    → T+1 数据日，当日 08:00 后即可
       周日 / 假期中末段  → NONE（休市，无 T+1）
       凌晨(00:00-08:59) → 归前一自然日（夜间补跑窗口，允许继续跑未完的批）
  2) 再「缺什么跑什么」（**纯内容级**，不吃 git checkout 的 mtime）：
       A 未就绪            → A
       A 就绪 且 B 未就绪   → B
       B 就绪 且 D 未就绪   → D
       D 就绪 且 E 未就绪   → E
       全就绪 / 未到起点    → NONE（空转=真成功，不是假成功）
     说明：删掉了旧版每批各自的 MIN_HOUR(16/18/20/21)。
      那套钟点阈值有两个毛病 ——
        (a) 凌晨 eff_hour 归 0 → 00:30 接力档恒判 NONE，B 若 22:30 后才完，
            D/E 当晚**永远补不上**（漏档实锤）；
        (b) 与内容级就绪重复，A 已新鲜还硬等 18 点，纯拖延。
      现在只保留「盘后链起点」一个时间闸（交易日 18:00 / T+1 日 08:00），
      批次推进完全由上游产物说了算 —— 数据到了就跑，没到就不跑。
  3) 上游未就绪 → stage_ok=false → 调用方**必须红灯 + 拒绝执行 + 紧急报告**
     （主人令「发现前面是错的，就该退回拒绝之后的执行并紧急报告」）。
     🔔 紧急报告 = 本地 v8_cloud_watchdog / health_patrol / 盘后算法链接力推进器 检测到
        本 workflow run 变红（::error + exit 1）后，按 .workbuddy/v8_smtp_config.json
        向 2814546@qq.com 发邮件告警（工作日 7-21 点）。闸门只负责"判红+拒绝"，
        邮件由上述本地链路发出——不在此处另造一套发信。
  4) 🔴 2026-09-11 主人令「一劳永逸」：盘后链起点 = **交易日 18:00**（非 16:00）。
     全部当日交易数据（含龙虎榜 16:30 后、收盘结算）出炉后，A 采集批才允许开跑；
     此前的唤醒一律视为"未到起点"→ 空转或回填上一数据日，绝不抢跑半日数据。
     批次推进完全由上游产物说了算——数据到了就跑，没到就不跑。
     成功定义 = A→B→D→E 四批**全部**为当日产物 + 推送 main + Pages 构建部署上线
     （链尾「产物完整性闸门 + 结果问责」逐批校验，任一停留非当日即整条链变红）。

■ 就绪判据（READY_SPEC）
  A 采集批：13 项中 ≥11 项鲜活（老 10 项容错保留 6 项 + 新增 3 项）+ **龙虎榜 / lhb_data / ETF_NET_SUBSCRIPTION must 必新** ← 以 READY_SPEC["A"] 为唯一真源
           ⚠️ 2026-09-14 00:1x P0 修正：原扩至「19 项 / ≥13 / must 含 AVG_PRICE_DATA」，其中 7 项在仓库中**并不存在**（TDX_BACKTEST 真名 BACKTEST_TDX 且属 E 批；AVG_PRICE 真名 AVG_PRICE_DATA；ETF_SUBSCRIPTION 系旧口径已下线；etf_subscription/avg_price/etf_spot/zsxq_posts 从未存在）⇒ read_ut() 返 None ⇒ must 恒不满足 ⇒ **A 批永久锁死且不报错**。已收敛为 13/11/3。
           🔴 `AVG_PRICE_DATA` 现为**非 must**：cloud_fetch_v8 的 post_close 档不写其时戳（仅 intraday 写）⇒ 放回 must 会立即复现锁死；须待「方案乙」落地后方可考虑加回。
  B 选股批：12 项产物中 ≥8 项鲜活 + 三重共识/四量终极/逆势龙头（must）必新  ← 以 READY_SPEC["B"] 为唯一真源
  D 汇总批：最终推荐                              → 1/1
  E 回测批：全算法回测汇总 + TDX 回测（**两项必新 must**）+ CRDS 回测 → 2/3 项
            ⚠️ 原 must 仅 [BACKTEST_ALL_ALGOS]：need 是**纯计数**，表达不了「哪几项必新」；
               只占「任一」位的 BACKTEST_TDX 陈旧时**不阻塞**就绪，而健康检查又把它列低频豁免
               ⇒ **双盲区**。实测后果（2026-09-18）：其产物涨到 76 MB 超 GitHub 单文件上限，
               推送每次 HTTP 422，线上停更 4 天而**全链零红灯**。现 must 补为两项；第 3 项 CRDS
               不参与否决（不引入「三项全中」过紧约束）。⚠️ 提 must 前必核不变式：
               must ⊆ dedup_fetch_manifest.py::_ALWAYS_PUSH。
            🔴 2026-09-14 主人令更正：候选池 / 金股池(=黄金池) 是算法**上游水源**、
               不是选股策略 ⇒ **不需要回测**。原 CANDIDATE_BACKTEST / GOLD_POOL_BACKTEST
               两项已从 items/must 移除（并删除 algorithms/backtest_pools.py）。
  「今日盘后」= update_time 的日期==数据日 且 (时:分) >= 该日门槛。

■ 用法
  python .github/scripts/v8_stage_gate.py --root .                        # 自动
  python .github/scripts/v8_stage_gate.py --root . --explicit-stage B      # 人工指定(仍过上游闸门)
  python .github/scripts/v8_stage_gate.py --root . --force                 # 忽略时间门控(周末审计补跑)
  python .github/scripts/v8_stage_gate.py --root . --hour 22 --today 2026-09-10  # 本地演练

■ 输出（stdout key=value，供 $GITHUB_OUTPUT 消费）
  target_stage=A|B|D|E|ALL|NONE

■ 跨批顺序（2026-09-10 加严，实测两缺陷后修）
  下游最新产物 必须 ≥ 上游基准产物（SEQ_REF），否则判未就绪 → 重算。
  产物时间戳含「凌晨 00:00-08:59 归前一自然日 24:xx」的候选解释（防凌晨死循环）。
  stage_ok=true|false
  proceed=true|false            ← 后续步骤只看这一个值
  chain_day=YYYY-MM-DD|none      chain_kind=trading|t1|none
  today / cst_hour / reason / ready_A..E / detail
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
v8_date = None
try:
    import v8_date  # 统一交易日历（内部复用 fetch_lhb 的日历缓存）
except Exception:
    pass


def _ensure_v8_date(root: str) -> None:
    """确保能从 --root（仓库根）导入 v8_date；导入失败时退回「周一~周五」保守日历。"""
    global v8_date
    if v8_date is not None:
        return
    try:
        ra = os.path.abspath(root)
        if ra not in sys.path:
            sys.path.insert(0, ra)
        import v8_date as _vd  # type: ignore
        v8_date = _vd
    except Exception:
        v8_date = None

# ── 就绪判据 ────────────────────────────────────────────────────────────────
#   items : 代表性产物（读文件内容 update_time / data_date）
#   need  : 至少命中几项算就绪
#   must  : 其中必须命中（全中）的关键项
#            ⚠️ must 必须是 items 的子集 —— 不在 items 里的项不进判定循环，会**静默失效**。
#            ⚠️ 不变式：must ⊆ dedup_fetch_manifest.py::_ALWAYS_PUSH（详见该文件注释）。
READY_SPEC: dict[str, dict] = {
    "A": {
        # 🛡 2026-09-11 主人令「一劳永逸」（与 B 批同源根治）：readiness 清单 3 → 10 项。
        #   原清单只校验 3 个代表产物（LHB_DATA / sector_rs / stock_profile），而 A 批实有
        #   12 个脚本。实测（2026-09-11 经 Contents API 直查 main）：
        #   这 3 项鲜活，但 A 批另有 6 个产物停在 09-10 ——
        #     fundamental_quality / stock_quote / inst_trade / suspension_alert /
        #     nt_data / sector_fund_flow_trend
        #   → 闸门判「A 已就绪」→ 这些卡整日红灯却无人重跑
        #     （主人截图中的 SUSPENSION_ALERT / SECTOR_FUND_FLOW_TREND 正是此类）。
        #   故把 A 批全部可读时戳的产物纳入清单。
        #   ⚠️ 不含 stock_names.json：该文件无 update_time/data_date 字段，read_ut 恒返回
        #      None → 会永久计为 MISS 从而拉低命中数（实测已确认）。
        #   need=13/19（must=1）：见 items 末尾 2026-09-13 的账，余量 6→12（更宽松）；
        #   ⚠️ 原写「need=7/10：容忍 3 项」是**改前**旧账，已按现值更正；
        #     而当前 4/10 的状态会被判「未就绪」→ 正确触发补跑。
        "items": [
            "data/LHB_DATA.js",                 # 龙虎榜 = 「16:30后数据」的核心标志（must）
            "raw_data/sector_rs.json",
            "raw_data/stock_profile.json",
            "raw_data/fundamental_quality.json",
            "raw_data/stock_quote.json",
            "raw_data/inst_trade.json",
            "raw_data/suspension_alert.json",
            "raw_data/nt_data.json",
            "raw_data/sector_fund_flow_trend.json",
            "raw_data/market_alerts.json",
            # 🛡 2026-09-13 主人令（拍板「A 批 9 项纳入」）：items 10 → 19，need 7 → 22。
            #   这 9 项是 A 批**实际产出、主站有卡、却未被本清单覆盖**的产物 ⇒
            #   老 10 项新鲜而它们整日红灯时，闸门仍判「A 已就绪」⇒ 空转 ⇒ 永远补不上
            #   （与 09-11 / 09-12 两次同类事故同因）。
            #   🔴 账（先核实再动手，**must 只有 1 项**，不是 16 项 —— 我第一版算错过）：
            #     改前 items=10 / need=7 / must=1 ⇒ 容错余量 = 7 − 1 = 6；
            #     改后 items=19 / need=13 / must=1 ⇒ 余量 = 13 − 1 = **12**。
            #     ⇒ 余量不减反增（更宽松），且新增 9 项**确实参与**判定。
            #     ⚠️ 铁律：**只加 items 不抬 need = 没加**（need 是纯计数）；
            #        但 **need 绝不能 > len(items)**（那会永不就绪、锁死）——
            #        我第一版写 need=22 > items=19，被自检当场拦下。
            #   🔴 联动：新增项必须同步进 dedup_fetch_manifest.py::_ALWAYS_PUSH，
            #     否则内容天然稳定项被判伪变更 ⇒ 恒旧 ⇒ 每轮重跑不收敛。
            "raw_data/lhb_data.json",              # 龙虎榜明细（LHB_DATA.js 的源）
            "data/AVG_PRICE_DATA.js",              # 平均股价（源 raw_data/avg_price_data.json）
            "data/ETF_NET_SUBSCRIPTION.js",        # ETF 净申赎（真实份额口径，09-11 主人 P1）
        ],
        "need": 11,
        # 🔴 2026-09-14 阿狸咪的工程师（方案甲·P0 联动的账）：
        #   need 12 → 11。理由：AVG_PRICE_DATA 移出 must 后不再受硬否决，
        #   它若陈旧只占用容错额度；need 是「纯计数」门槛，须与 must 解耦。
        #   账（复核）：items=13 / need=11 / must=3 ⇒ 容错余量 = 11 − 3 = 8（不变）；
        #   need(11) <= len(items)(13) ✔、must(3) ⊆ items ✔ ⇒ 无锁死风险。
        # 🔴 方案丙（2026-09-13 定稿）+ 🔴🔴 同日 23:5x 紧急修正（P0）：
        #   need=12 保留老 10 项的 6 项容错（采集批抓取源抖动常见，不宜一刀切全须新）；
        #   新增的**真实存在**项进 must（逐项必新）⇒ 它们任一陈旧即 not ready
        #   （must 与 need 计数无关，直接否决）⇒ 缺口被根治。
        #   ⚠️ must 的代价：must 项必须同步进 dedup_fetch_manifest.py::_ALWAYS_PUSH
        #      （已在本补丁 D1 落地），否则内容天然稳定项被判伪变更 ⇒ must 恒不满足 ⇒ 锁死。
        # 🔴🔴 P0 教训（2026-09-13 23:40 → 23:5x 修正）：
        #   我原把 9 项「以为存在」的产物写进 items+must，其中 **7 项在 origin/main 根本不存在**
        #   （TDX_BACKTEST / AVG_PRICE / ETF_SUBSCRIPTION / etf_subscription / avg_price /
        #    etf_spot / zsxq_posts）⇒ read_ut 返回 None ⇒ **must 恒不满足 ⇒ A 批永久
        #   不就绪 ⇒ 整条链锁死**。
        #   根因：**凭名字猜产物名**（真名是 AVG_PRICE_DATA.js / BACKTEST_TDX.js /
        #   ETF_NET_SUBSCRIPTION.js），且把 **09-06 主人令已下线**的旧口径产物当现存项。
        #   ⇒ 铁律：**纳入 READY_SPEC 前必须 `git cat-file -e origin/main:<path>` 逐项验证存在**，
        #     且**must 项必须由 A 批时窗内的生产者产出**（E 批产物放 A 批 must = 批次错位）。
        "must": [
            "data/LHB_DATA.js",                       # 原有：龙虎榜（16:30 后数据核心标志）
            # 2026-09-13 新增 3 项（均已 git cat-file -e 验证存在 + A 批时窗内产出）
            "raw_data/lhb_data.json",                 # LHB_DATA.js 的源（龙虎榜 fetcher 17:30 档）
            "data/ETF_NET_SUBSCRIPTION.js",           # 映射 premarket,post_close ⇒ A 批时窗内可刷
            # 🔴🔴 2026-09-14 阿狸咪的工程师（方案甲·P0）：
            #   data/AVG_PRICE_DATA.js 已**移出 must，保留在 items**。
            #   根因（三层实测）：
            #     ① A 批门槛 FLOOR_TRADING=(16,30)（本文件 L269）；
            #     ② 该产物唯一写入者 cloud_fetch_v8.py 的 CATEGORY_MAP 里
            #        "AVG_PRICE_DATA": "intraday" —— **只在盘中档刷，post_close 不刷**；
            #     ③ run_algorithms.py 的 STAGES["A"] 13 项**不含** avg_price 脚本
            #        ⇒ A 批自己跑完也刷不动它。
            #   实测佐证：数据/AVG_PRICE_DATA.js 的 update_time=09-13 15:33:14，
            #     而 republish_time=16:09:45 ⇒ 16:09 重建过、戳仍是 15:33
            #     （戳由 update_v8.py::_pick_ts 从 raw 透传，**不是**构建时刻）。
            #   后果：交易日盘中档最高约 15:1x–16:11，**结构性达不到 16:30**
            #     ⇒ must_ok 恒 False（本文件 check_ready：must 任一不 ok 即 not ready）
            #     ⇒ target_stage 恒 = A ⇒ B/D/E 永不推进 ⇒ 最终推荐/回测停更。
            #   ⚠️ 原注释写「映射 intraday,post_close」是**引用错了源**：
            #     update_v8.py 的 "intraday,post_close" 管的是「在哪些档**重建 .js**」，
            #     与「哪个档**写时戳**」（决定闸门判据）是两回事 —— 这正是本 P0 的认知根因。
            #   纪律沉淀：**must 项必须由该批时窗内的生产者产出**（与 09-13 TDX_BACKTEST
            #     批次错位同源同因）。移出 must 后它仍在 items，仍参与计数与红灯显示，
            #     因此**不掩盖问题**，只是不再单点否决整条链。
            #   🔴 若要让 must 名副其实，需主人拍板方案乙：
            #     给 cloud_fetch_v8.py 的 post_close 档补抓 AVG_PRICE_DATA
            #     （参考 ETF_DAILY_MONITOR 的显式登记思路）—— 动抓取链，不擅动。
        ],   # 龙虎榜是「16:30后数据」的核心标志
    },
    "B": {
        # 🛡 2026-09-11 主人令「一劳永逸」：readiness 清单从 3 项代表产物扩到 9 项。
        #   根因（2026-09-11 09:5x 实证）：原清单只校验 3 个代表产物，而 B 批实际有
        #   28 个脚本、产出几十个 raw_data/*.json。当这 3 项鲜活、其余产物陈旧时，
        #   闸门判「B 批已就绪」→ target_stage=NONE / OUTCOME=skipped
        #   （reason=「✅ 四批产物均已就绪 → 空转」）→ 9 张卡（AI_INSIGHTS_COMPARE /
        #   FACTOR_AUDIT / FACTOR_PROGRESS / VALUATION_PERCENTILE / INDEX_VALUE_FRAMEWORK /
        #   TOP10_DAILY / BACKTEST_COMPREHENSIVE / SUSPENSION_ALERT /
        #   SECTOR_FUND_FLOW_TREND）整日红灯却无人重跑。
        #   修法：纳入 5 个刚从 experiments workflow 收编的新产物，使「B 批已就绪」
        #   必须以它们也鲜活为前提 —— 标本兼治（挂链 + 闸门双向对齐）。
        "items": [
            "data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js",
            "raw_data/ai_insights_compare.json",
            "raw_data/factor_audit.json",
            "raw_data/factor_progress.json",
            "raw_data/valuation_percentile.json",
            "raw_data/index_value_framework.json",
            # 🛡 2026-09-11 纳入；2026-09-13 修正生产者属性（原注释误写为「B 批派生」）：
            #   实际产出者是**采集批** v8_cn_fetch_cloud.yml 的
            #   `python algorithms/build_candidate_pool.py` —— 该脚本不在 v8_algo_cloud.yml
            #   的算法链里（实测 grep 无命中）。
            #   本项保留为「上游新鲜度抵押」：它鲜活即证明采集批正常。
            #   need=8 的容错语义与 items 清单均未改动。
            "raw_data/gold_pool.json",
            # 🛡 2026-09-18 小九（双盲区根治·P0 · 事故家族第三次复发）：补入 FOUR_VOLUME_60M.js。
            #   根因（实测闭环）：该项**既不在 items 也不在 must**，而 v8_health_check.py 的
            #   _LOW_FREQ_FILES 于 09-11 已按主人令把它移出（max_age=1440 硬告警）
            #   ⇒ 闸门不覆盖（陈旧不阻塞就绪 → target=NONE 空转 → **永不重跑**）
            #     + 健康检查只报不做 ⇒ 产物自 09-17 06:54 冻结逾 24h 而全链「零阻塞」。
            #   与 09-18 阿狸咪修的 BACKTEST_TDX 属**同一事故家族**
            #   （注释原文：「两个监控都不覆盖」），本次为第三次复发 ⇒ 另加机器可断言护栏。
            #   ✅ 可达性核验：它与 data/FOUR_VOLUME.js 同批同源（ORDER 190/191，STAGES["B"]），
            #      nightly 夜窗 00:00~08:59 由 picking 门控放行（run_algorithms.py L627）
            #      ⇒ 不恒 STALE；实测 runner 环境(CLOUD_RUNNER=true)全链 96s 跑通、命中 11 只。
            #   ✅ 不变式核验：已同步纳入 dedup_fetch_manifest.py::_ALWAYS_PUSH（见该文件）。
            #   ⚠️ need 仍为 8（2026-09-18 更正：items 已达 12 项 ⇒ 实为「12 项容忍 4 项不新鲜」）—— 60m 是「加分因子」，
            #      不因此收紧要挟整条 B 批；它参与计数即可驱散空转。
            "data/FOUR_VOLUME_60M.js",
            # 🛡 2026-09-18 小九（同轮双盲区根治·家族第四次同型）：四量终极自建系统两产物。
            #   2026-09-15 主人令「四量也要像三重共识有自己的整套系统」新增
            #   update_four_volume_history.py / gen_four_volume_track.py（STAGES["B"] ORDER 200+），
            #   但**未同步登记进本闸门** ⇒ 与 60m 完全同型的「闸门不覆盖」盲区。
            #   本轮由 guard_double_blind.py（机器可断言护栏）自动发现，非人工逐个补。
            #   ✅ 可达性：与 data/FOUR_VOLUME.js 同批同源（读它刚产的当日新鲜账本）。
            #   ✅ 不变式：已同步纳入 dedup_fetch_manifest.py::_ALWAYS_PUSH。
            "data/FOUR_VOLUME_HISTORY.js",
            "data/FOUR_VOLUME_TRACK.js",
        ],
        "need": 8,
        # need 用 8/9：3 个核心选股产物 + 5 个收编产物 + gold_pool，即「只容忍 1 项不新鲜」。
        #   ⚠️ 为何不是 5：实测发现 dedup 去重器会把「内容天然稳定」的卡判为伪变更而丢弃
        #   （见 .github/scripts/dedup_fetch_manifest.py 的 _ALWAYS_PUSH）。在去重器修好之前，
        #   一轮 B 批跑完后线上只会有 3 核心 + 2 张（ai_insights/valuation_percentile）= 5/9。
        #   若 need=5，闸门会据此判「B 已就绪」→ 空转 → 另 4 张（factor_audit /
        #   factor_progress / index_value_framework / gold_pool）永远补不上 → 恒红。
        #   need=8 使闸门在上述状态下判「未就绪」→ 再跑一轮 B → 去重修复生效后 9/9 → 收敛。
        #   （2026-09-13 复核：dedup 的 _ALWAYS_PUSH 已补齐 gold_pool 等 6 项，
        #     故上面「need=8 因去重器丢弃伪变更」的历史约束已解除，9/9 可稳态达成；
        #     need=8 的现役语义 = 容忍 1 项真失败。）
        #
        # 🛡 2026-09-13 主人令（拍板 P1 · 一劳永逸）：must 由 [] 收紧为**三项核心选股产物**。
        #   根因：need 是**纯计数**，表达不了「哪几项必新」。当陈旧项恰好是三重共识 /
        #   四量终极 / 逆势龙头时，闸门仍判「B 已就绪」→ 空转 → 三张核心卡整日停更
        #   而全链零红灯（主人 09-12 令「必新」在 B 批从未真正生效）。
        #   🔴 与 dedup 的联动不变式（缺一即锁死，详见 dedup_fetch_manifest.py::_ALWAYS_PUSH）：
        #      must 项必须同时在 _ALWAYS_PUSH 中，否则内容天然稳定的 must 项
        #      （FOUR_VOLUME 长期命中 0 只 ⇒ 剥时间戳后逐字节相同）会被判「伪变更」永不推送
        #      ⇒ update_time 恒旧 ⇒ must 恒不满足 ⇒ B 批每轮重跑 60~90min 永不收敛。
        "must": ["data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js"],
    },
    "D": {"items": ["data/FINAL_RECOMMEND_DATA.js"], "need": 1, "must": []},
    # 🔴 2026-09-12 主人令（拍板第 2 项·一劳永逸）：E 批就绪清单 2 → 3 项，need 1 → 2。
    #   根因（实测）：algorithms/gen_backtest_all_algos.py 已挂 STAGES["E"]（ORDER 47/48），
    #   但 data/BACKTEST_ALL_ALGOS.js **远端不存在**时全链零红灯 —— 它不在本清单里。
    #   🔴 关键：**只加 items 不抬 need = 没加**。need=1 的语义是「任一鲜活即就绪」，
    #      新增项在 need=1 下不参与判定。故必须 need 1 → 2，语义变为：
    #      「CRDS_BACKTEST / BACKTEST_TDX 至少 1 项鲜活」**且**「BACKTEST_ALL_ALGOS 鲜活」。
    #   可行性：该脚本是同批最后跑的一个（ORDER 47/48，排在其它回测之后，要读它们刚产出的源），
    #      只要它跑成功就必有产物 ⇒ 正常情况下不会把 E 批锁死成「永不就绪」。
    #      它若失败 → 正该重跑 E（而非静默）—— 这正是本改动的目的。
    #
    # 🛡 2026-09-13 主人令（拍板 P1 · 一劳永逸）：need 是纯计数 ⇒ 必须补 must 才真正闭环。
    #   只计 need 保证不了「哪几项必新」：若陈旧项恰好是 BACKTEST_ALL_ALGOS.js
    #   （主人 09-12 令点名必新的那一项）→ 闸门仍判 E 已就绪 → 空转 → 汇总卡停更，全链零红灯。
    #   现 must = [BACKTEST_ALL_ALGOS.js]；第 2 项由 CRDS_BACKTEST / BACKTEST_TDX 任一补足
    #   （保持「至少 1 项」语义）⇒ 1(must) + 1(任一) = need 2，自洽。
    #   🔴 同样受 must ⊆ dedup_fetch_manifest.py::_ALWAYS_PUSH 不变式约束（见 B 批注释）。
    # 🔴 2026-09-14 主人令更正：候选池 / 金股池(=黄金池) 是算法**上游水源**（B 批基础股池），
    #   不是选股策略 ⇒ **不需要回测**。原 5 项 / need 4 里的两池回测已移除（3 项 / need 2），
    #   同时删除 algorithms/backtest_pools.py 与 data/{CANDIDATE,GOLD_POOL}_BACKTEST.js。
    "E": {"items": ["data/CRDS_BACKTEST.js", "data/BACKTEST_TDX.js",
                    "data/BACKTEST_ALL_ALGOS.js"], "need": 2,
          # 🔴 2026-09-18 阿狸咪的工程师（双盲区根治·P0）：must 补入 BACKTEST_TDX。
          #   根因（实测闭环）：原它只占 items（need=2 的「任一」位）⇒ 陈旧**不阻塞**就绪；
          #   而 v8_health_check.py::_LOW_FREQ_FILES 又把它列为低频豁免 ⇒ 陈旧**不告警**
          #   ⇒ **两个监控都不覆盖**。后果：raw_data/backtest_tdx.json 涨到 76,078,046 B
          #   （12 档 × 221 只逐笔明细），推送 POST /git/blobs 每次 HTTP 422
          #   （超 GitHub 单文件上限），线上 data/BACKTEST_TDX.js 永久停在 09-14
          #   —— **停更 4 天而全链零红灯**。（与主人 09-12 点名的 BACKTEST_ALL_ALGOS
          #   「静默不产出无人知晓」同型同因，属同一事故家族第二次复发。）
          #   ✅ 不变式核验（must ⊆ _ALWAYS_PUSH，缺一即「永久不收敛」）：
          #      data/BACKTEST_TDX.js 已在 dedup_fetch_manifest.py::_ALWAYS_PUSH（L130）
          #      ⇒ 不会被去重器判「伪变更」丢弃 ⇒ update_time 能前进 ⇒ must 可满足。
          #   ✅ 可达性核验（防 must 恒 STALE）：它与 BACKTEST_ALL_ALGOS 同批同源产出；
          #      凌晨档由 _cand() 的「+24h」解释匹配（01:23 → 25:23 ≥ 16:30）⇒ 不恒 STALE。
          #   ✅ 代价可控：need=2 且 must 两项 ⇒ 判定等价于「这两项必须新」，第 3 项
          #      CRDS_BACKTEST 不参与否决（保留原有容错语义，不引入「三项全中」过紧约束）。
          "must": ["data/BACKTEST_ALL_ALGOS.js", "data/BACKTEST_TDX.js"]},
}

# 各批上游：上游不就绪则拒绝开跑（顺序闸门 · 一环套一环）
# 🔴 2026-09-11 主人令「一劳永逸」：A→B→D→E 严格串联，下游批**必须等上游批产出"当日"数据**
#   才放行（PREREQ 上游未就绪 → stage_ok=false → 调用方红灯拒绝 + 邮件告警）。
# 🔴🔴 2026-09-17 主人令「看板一大片红灯·一劳永逸」（小九）：E 的上游由 D 改为 B —— 解「E 被 D 单点串死」的当晚级死锁。
#   病根（09-17 实测，7 项红灯）：E 批 PREREQ=D + SEQ_REF=E←FINAL_RECOMMEND_DATA，而 D 的上游 B 因
#     factor_lab_gen 冷启动 50-90min 常拖到 04:30 才完 ⇒ D 06:26 才开跑 ⇒ E 要再等一整轮唤醒，
#     而 08:00 那档已在夜窗末班（接力推进器 08:59 收工、09:00 进入新数据日）⇒ E 被挤掉，
#     产物停 09-16 05:12，次日看板 all_* 回测类 7 项全红（超 1440min 红线 26h）。
#   **依据（逐脚本核验，非推断）**：E 批 14 个脚本**零个**读 data/FINAL_RECOMMEND_DATA.js——
#     真实输入 = gold_pool.json / history/top10_daily_*.json / factor_lab.json /
#     H_AUTO_BUY_TRACK.js / CRDS 信号 ⇒ **全部来自 A 或 B 批**。
#     gen_backtest_all_algos.py 的 SOURCES 登记表 6 条全部指向 **E 批自产**的同级产物。
#   ⇒ 「E 依赖 D」是历史残留的过严依赖；E 与 D 实为**平行兄弟**（同依赖 B）。
#   ⚠️ 不可反向操作：factor_lab_gen **必须留在 B 批**——final_recommend.py L661-674 硬等
#     data/FACTOR_LAB.js 当日新鲜（_fl_max_wait=20，逐分钟打印心跳），挪到 E 批会让 D 吃陈旧因子。
#   ⚠️ E 仍排在 D 之后跑（见下方自愈段 for 顺序）：汇总先上线、回测后跑，业务语义不变。
PREREQ: dict[str, str | None] = {"A": None, "B": "A", "D": "B", "E": "B"}

# 盘后链「起点」（该时刻之前不跑任何批）
# 🔴 2026-09-11 主人令「一劳永逸」：16:00 → 18:00。全部当日交易数据（龙虎榜 16:30 后、
#   收盘结算）出炉后 A 采集批才允许开跑；此前唤醒一律空转或回填上一数据日，绝不抢跑半日数据。
START_TRADING = (18, 0)
START_T1 = (8, 0)
# 产物「算今日盘后」的最低时刻
FLOOR_TRADING = (16, 30)
FLOOR_T1 = (8, 0)

# 🛡 2026-09-11 一劳永逸（run#1692 / run#34535287523 双实证）：夜间补跑窗口上界。
#   原为 6（00:00-05:59）。缺陷：算法链实测耗时 84+ 分钟，凡 05:00 后起跑的夜间补跑
#   必然在跑到一半时跨出窗口 —— run#1692 于 05:16 起跑，B 批 06:43 才跑完，而 06:01
#   派发的那一轮闸门在 06:51 判定「未到本日 16:00 起点 → NONE」→ 整链空转，
#   （注：16:00 是**事发当时**的起点值；起点常量已改为 18:00，本段为历史实证记录，勿当现行口径。）
#   B 批 84 分钟成果无人接力，TOP10_DAILY/FINAL_RECOMMEND_DATA 整日停更。
#   修法：窗口放宽到 08:59（开盘前），使「本日链未到起点」的时段仍能补跑上一数据日。
#   与 algorithms/run_algorithms.py::_NEXT_DAY_CUTOFF_HOUR、algorithms/utils/time_gate.py::
#   _NIGHT_CUT_HOUR 三处同源对齐 —— 两套口径必然漂移（历史教训）。
_NIGHT_CUT = 9

_UT_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})')
_DT_ONLY_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})')
_DATE_RE = re.compile(r'"data_date"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')


def read_ut(root: str, rel: str):
    """读产物时间 → (YYYY-MM-DD, hh, mm)；只有日期无时刻时记为 23:59（宽松）。"""
    path = os.path.join(root, rel)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(20000)
    except OSError:
        return None
    m = _UT_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", int(m.group(4)), int(m.group(5))
    m = _DT_ONLY_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 23, 59
    m = _DATE_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 23, 59
    return None


def _cand(r):
    """把 (day, hh, mm) 展开成候选解释：原样 +（若 hh<6）归前一自然日的 24:xx。

    🔴 2026-09-10 实测缺陷修复：夜间补跑窗口（00:00-08:59）写出的产物戳是「当天」，
    但该档判定的数据日是「前一自然日」→ 只认原样会永不匹配 → 00:30-08:59 每档重跑该批
    （死循环，实测已复现）。两种解释都接受即根治。
    """
    out = [(r[0], r[1], r[2])]
    if r[1] < _NIGHT_CUT:
        d = dt.date.fromisoformat(r[0]) - dt.timedelta(days=1)
        out.append((d.strftime("%Y-%m-%d"), r[1] + 24, r[2]))
    return out


def _newest(root: str, items):
    """取这些产物里「最新」的时间戳（含凌晨候选解释），无则 None。"""
    best = None
    for it in items:
        r = read_ut(root, it)
        if not r:
            continue
        for c in _cand(r):
            if best is None or c > best:
                best = c
    return best


# 🚪 逃生门（2026-09-12 主人令·一劳永逸）：上游落后超阈值时的强制放行。
#
# 背景（真危险，非理论）：B 批 need=8/9，只要 A 的 9 项里有 2 项长期不鲜，
#   闸门就永远判「B 未就绪」→ 每轮都去跑 B → **D 批（最终推荐）永久不触发**。
#   系统只亮红灯、不会自己绕过去 ⇒ 最终推荐永久停更（比「带降级标记的旧结果」更糟）。
#
# 主人拍板语义：「宁可给带降级标记的结果，也不要永久空白（标记可见就不算假成功）。」
#
# 生效条件（两者同时满足才算「上游长坏」）：
#   ① A 批未就绪，且
#   ② A 批**最新**产物的数据日 距当前数据日 > UPSTREAM_LAG_MAX 个自然日。
# 效果：B 批强行放行（由 PREREQ 让 D 也能跑），并在日志/产物打 `DEGRADED_UPSTREAM` 标记。
UPSTREAM_LAG_MAX = 2


def _upstream_lag_days(root: str, items, day: str) -> int | None:
    """上游最新产物距目标数据日落后几个自然日；无任何产物时返回 None。"""
    newest = _newest(root, items)
    if not newest:
        return None
    try:
        d_new = dt.date.fromisoformat(newest[0])
        d_tgt = dt.date.fromisoformat(day)
        return (d_tgt - d_new).days
    except Exception:
        return None


def _escape_gate(root: str, day: str) -> tuple[bool, str, int]:
    """判断是否满足逃生门（上游长坏 > UPSTREAM_LAG_MAX 天）。

    返回 (是否放行, 原因文案, 落后天数)。滞后天数用 -1 表示「无从判断（产物全缺）」。
    原因文案仅供日志/人读；机器消费请用 rdy 里的 DEGRADED_UPSTREAM / degrade_lag_days。
    """
    lag = _upstream_lag_days(root, READY_SPEC["A"]["items"], day)
    if lag is None:
        # A 批一个产物都没有：可能是首次冷启动。仍给逃生门（否则整链永远起不来），
        # 但标记要更醒目 —— 「无上游」比「上游落后」更需要人工看一眼。
        return True, ("🚪 DEGRADED_UPSTREAM：A 批产物全部缺失（无从判断落后天数）"
                      "→ 强制放行 B 批，下游带「数据降级」标记"), -1
    if lag > UPSTREAM_LAG_MAX:
        return True, (f"🚪 DEGRADED_UPSTREAM：A 批最新产物落后 {lag} 天 "
                      f"(> {UPSTREAM_LAG_MAX}) → 强制放行 B 批，"
                      f"避免 D 批（最终推荐）永久饿死；下游带「数据降级」标记"), lag
    return False, f"A 批落后 {lag} 天（≤ {UPSTREAM_LAG_MAX}，仍在容忍窗内）→ 不放行，先补采 A", lag


# 🔴 跨批顺序判据（一环套一环的硬约束）：下游最新产物必须 ≥ 上游基准产物。
#   基准只挑「单一来源、写一次就固定」的产物，避免被后续抓取链刷新导致反复重算。
SEQ_REF: dict[str, str] = {
    "B": "data/LHB_DATA.js",             # A 批核心标志（17:30 落盘后不再变）
    "D": "data/TRIPLE_CONSENSUS.js",     # B 批代表产物
    # 🔴🔴 2026-09-17 一劳永逸（小九，同 PREREQ 处说明）：原值 = "data/FINAL_RECOMMEND_DATA.js"（D 批产物）。
    #   该基准把 E 的「就绪」判定绑死在 D 的时间戳上（check_ready L444-454：E 产物早于基准即判未就绪需重算），
    #   与 PREREQ 双锁叠加 ⇒ 即使 PREREQ 改了，E 仍会被本行卡住。故必须同改。
    #   新值 = B 批代表产物，与 D 同基准（语义自洽：E 与 D 同依赖 B，互为平行兄弟）。
    #   ⚠️ 基准须满足「单一来源、写一次就固定」：TRIPLE_CONSENSUS.js 由 B 批 gen_triple_consensus.py
    #     一次产出，不被后续抓取链刷新 ⇒ 符合要求。
    "E": "data/TRIPLE_CONSENSUS.js",     # B 批代表产物（2026-09-17 由 D 批产物改；解 E 被 D 串死）
}


def check_ready(root: str, stage: str, day: str, floor: tuple[int, int], kind: str = "trading"):
    """返回 (是否就绪, '命中/总数', 明细)。

    kind='t1'（周六/假期首日）时放宽 A 采集批：T+1 日数据天然是「部分刷新」，
      若仍按交易日 3/3 + 龙虎榜必新，A 会永远不就绪 → 整条 T+1 链卡死（漏档）。
      放宽为「任一 A 产物当日刷新即视为采集完成」，把节奏交给 B/D/E 三批。
    """
    spec = READY_SPEC[stage]
    need = spec["need"]
    must = list(spec["must"])
    if kind != "trading" and stage == "A":
        need, must = 1, []
    hit, must_ok, parts = 0, True, []
    for it in spec["items"]:
        r = read_ut(root, it)
        ok = bool(r and any(c[0] == day and (c[1], c[2]) >= floor for c in _cand(r)))
        if ok:
            hit += 1
            parts.append(f"{os.path.basename(it)}=OK({r[0]} {r[1]:02d}:{r[2]:02d})")
        elif r:
            parts.append(f"{os.path.basename(it)}=STALE({r[0]} {r[1]:02d}:{r[2]:02d})")
        else:
            parts.append(f"{os.path.basename(it)}=MISS")
        if it in must and not ok:
            must_ok = False

    ready = must_ok and hit >= need
    # 🔴 跨批顺序闸门：下游算完但上游之后又被刷新过 → 判未就绪，必须重算（防「拿旧上游算下游」）
    if ready and stage in SEQ_REF:
        up = read_ut(root, SEQ_REF[stage])
        mine = _newest(root, spec["items"])
        if up and mine:
            up_best = max(_cand(up))
            if mine < up_best:
                parts.append(
                    "\u26d4\u4e0b\u6e38\u65e9\u4e8e\u4e0a\u6e38(%s=%s %02d:%02d)\u2192\u9700\u91cd\u7b97"
                    % (os.path.basename(SEQ_REF[stage]), up_best[0], up_best[1], up_best[2]))
                ready = False
    return ready, f"{hit}/{len(spec['items'])}", " ".join(parts)


# ── 交易日历：今天该跑哪个「数据日」 ─────────────────────────────────────────
def _is_trading_day(d: dt.date) -> bool:
    if v8_date is None:
        return d.weekday() < 5
    try:
        return bool(v8_date.is_trading_day(d))
    except Exception:
        return d.weekday() < 5


def _last_trading_day(ref: dt.date) -> dt.date | None:
    if v8_date is None:
        d = ref
        for _ in range(15):
            if d.weekday() < 5:
                return d
            d -= dt.timedelta(days=1)
        return None
    try:
        return dt.datetime.strptime(v8_date.last_trading_day(ref, max_lookback=15), "%Y-%m-%d").date()
    except Exception:
        return None


def chain_day(ref: dt.date, lookback: int = 0):
    """返回 (数据日 | None, 类型 trading|t1|none, 说明)。

    lookback>0 时向前找最近一个「应跑日」（供 --force 周末审计补跑）。

    🔴 2026-09-11 一劳永逸（阿狸咪的工程师）：非交易日「应跑日」判据精确化。
      主人规则：**周六跑 / 周日不跑 / 假期第一日跑 / 假期第二日起不跑**。
      旧判据 `gap=(d-上一交易日).days; 0 < gap <= 3` ⇒ 距上个交易日不超过 3 天即判 t1，
      实测把**假期第 2、3 天也判成应跑日**（中秋 09-26、国庆 10-02/10-03 全部 t1）：
        · 白跑整链 84 分钟 ×(N-1) 天；
        · 产物 update_time 被刷成**非交易日日期** → 主站卡片显示「10-02」这类不存在的数据日。
      新判据只认「连续休市段的第一天」（前一天是交易日），三条规则**全部自动成立**：
        · 周六         d-1 = 周五(交易日)   → 段首   → 跑
        · 周日         d-1 = 周六(非交易日) → 非段首 → 不跑
        · 假期第一日   d-1 = 交易日         → 段首   → 跑
        · 假期第2日起  d-1 = 非交易日       → 非段首 → 不跑（含假期里落到周六的那天）
      ⚠️ 已知边界（非交易日集合无法区分，已在交接单标注）：若某年假期自**周六**开始，
        则段首=周六；若假期自**周一**开始，段首仍是周六（周末也属该休市段）。两种情况
        都只在段首跑一次，同一目标（下个交易日）的数据不会缺，只是唤醒点比字面少一次。
    """
    for i in range(lookback + 1):
        d = ref - dt.timedelta(days=i)
        if _is_trading_day(d):
            return d, "trading", f"交易日 {d}"
        # 🔴 2026-09-11 精确判据：仅「连续休市段的第一天」为应跑日（详见 docstring）
        if _is_trading_day(d - dt.timedelta(days=1)):
            return d, "t1", f"T+1 数据日 {d}（上一交易日 {_last_trading_day(d)}）"
    return None, "none", "非交易日（休市，无 T+1 需求）"


def _backfill_candidate(root: str, ref: dt.date):
    """上一数据日仍有未完成批次时返回 (day, kind, note, ready)，否则 None。

    🛡 2026-09-11 一劳永逸（闸门死区根治）：
      原设计只在「本数据日的链起点」之后才跑批，工作日 09:00~15:59 遂成死区 ——
      若上一数据日的链中途失败没跑完，这段时段**任何补跑都被判 NONE**。
      实测 run#1692：B 批 06:43 才跑完（链耗时 84min，跨出了夜间补跑窗口），
      06:01 派发的那一轮闸门 06:51 判「未到本日 16:00 → NONE」→ 整链空转，
      （注：16:00 是**当时**起点值，现行为 18:00；本段是 run#1692 历史实证记录。）
      84 分钟成果无人接力，TOP10_DAILY / FINAL_RECOMMEND_DATA / V8_POOL_TRACKER /
      BACKTEST_COMPREHENSIVE 四个模块停更一整天。
      判据严格限定为「上一数据日**确有**未完成批次」，正常日不受任何影响。
    """
    prev = ref - dt.timedelta(days=1)
    # 🔴 2026-09-11 判据改「段首」后，回填需跨过**整段**连续休市（最长 = 国庆 7 天
    #   + 前后周末 ≈ 9~10 天）才能找到上一个应跑日；2 太短会漏掉假期首日。
    pday, pkind, pnote = chain_day(prev, lookback=10)
    if pkind == "none" or pday is None:
        return None
    pfloor = FLOOR_TRADING if pkind == "trading" else FLOOR_T1
    pday_s = pday.strftime("%Y-%m-%d")
    pready = {s: check_ready(root, s, pday_s, pfloor, pkind) for s in READY_SPEC}
    if all(pready[s][0] for s in ("A", "B", "D", "E")):
        return None
    missing = "/".join(s for s in ("A", "B", "D", "E") if not pready[s][0])
    return (pday, pkind,
            f"{pnote}·上一数据日链未完成({missing})→补跑（本数据日链未到起点）",
            pready)


def _backfill_feasible(root: str, stage: str, tday: dt.date) -> bool:
    """回填目标日 tday 时，stage 是否可能被「有意义地」补跑。

    🔴🔴 2026-09-14 P0 修复（回填死锁根治）：
    盘后批次（cloud_fetch / run_algorithms）产出的产物以「实际运行时刻」打 update_time，
    而非「数据日」。因此回填一个过去的数据日 T 时，若其**上游输入链**
    （PREREQ 链 + 自身采集输入）中任一文件的日期已严格晚于 T（被后续日覆盖），
    重跑该 stage 只会把更新日期的产物再写一遍 → 永远填不上 T → 无意义 → 判不可能。
    只有上游链仍停留在 T（或缺失）时，补跑才可能产出 T 日产物。

    等价判据：stage 的全部上游输入里，不存在日期 > T 的项。
    （A 批无 PREREQ，自身采集输入即其上游；其余批沿 PREREQ 向上追溯整条链。）
    """
    s = stage
    items = []
    while s is not None:
        items.extend(READY_SPEC[s]["items"])
        s = PREREQ.get(s)
    for it in items:
        r = read_ut(root, it)
        if r is None:
            continue
        for c in _cand(r):
            try:
                if dt.date.fromisoformat(c[0]) > tday:
                    return False
            except (ValueError, TypeError):
                return False
    return True


def decide(root: str, now: dt.datetime, explicit: str, force: bool):
    hh, mm = now.hour, now.minute
    ref = now.date()
    if hh < _NIGHT_CUT:             # 凌晨归前一自然日（夜间补跑窗口）
        ref -= dt.timedelta(days=1)
    day, kind, note = chain_day(ref, lookback=10 if force else 0)

    if kind == "none":
        return ("NONE", True, f"⏸ {note} → 不跑任何批（合规空转）", day, kind, {})

    floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
    day_s = day.strftime("%Y-%m-%d")
    ready = {s: check_ready(root, s, day_s, floor, kind) for s in READY_SPEC}

    def out():
        return {f"ready_{s}": ready[s][1] for s in ("A", "B", "D", "E")}

    # 🚪 逃生门（2026-09-12 主人令）：上游长坏时强制放行 B 批，防 D 批永久饿死。
    #   放在所有「显式 stage」分支**之前**判定，但只在**自动链**路径生效
    #   （人工 --explicit-stage 仍尊重人工意图，见下方分支顺序）。
    _escape = (False, "", 0)
    if not ready["A"][0] and not explicit:
        _escape = _escape_gate(root, day_s)

    # ── 0) 显式全链（人工应急全量补算）──────────────────────────────────────
    if explicit == "ALL":
        return ("ALL", True, "显式 ALL：应急全量补算（缺什么跑什么，由 run_algorithms 全链兜底）",
                day, kind, out())

    # ── 1) 显式 stage（人工应急）—— 仍必须过上游顺序闸门 ─────────────────────
    _explicit_yield = ""   # 显式批「已就绪让位」留痕（写进 §3 reason，可见即可纠偏）
    if explicit in ("A", "B", "D", "E"):
        pre = PREREQ[explicit]
        # 🔴🔴 2026-09-17 一劳永逸（主人令「看板一大片红灯」· 小九）：解「显式 stage 单点占轮」。
        #   病根：本分支原为**无条件尊重显式意图**并直接 return —— 只要某个派发源带了
        #     client_payload.stage（实测存在多个：`v8 只补缺批·自动接力` 显式带 stage、
        #     `v8盘后链A档派发` 带 stage=A、`v8 E档回测批·今晚一次性兜底派发` 带 stage=E、
        #     `scripts/alimi_bell.py` 带 stage=E），gate 就当轮只跑那一批，
        #     **完全不看别的批是否更缺** ⇒ E 批即使最陈旧、前置也已满足，仍拿不到夜窗名额。
        #   实证（09-17）：06:26 那轮 reason=「显式 D，前置 B 已就绪(8/9)」→ 全轮只跑 D，
        #     而 E 批 7 个回测产物停 09-16 05:12（超 1440min 红线 26h）→ 次日看板一片红。
        #   ⇒ 与另一处「自愈段串行遮蔽」（见下方 §3）是**同一根因的两个单点**，须同解。
        #   **修法**：仅当「显式批**自身已就绪**」时让位 —— 此时跑它纯属重复劳动
        #     （幂等但白烧一个夜窗名额），交回下方 §3 自愈段按「缺什么跑什么」选真正最缺的批。
        #   零回归 + 人工意图不丢：
        #     · 显式批**未就绪**            → 与旧完全一致（放行 or 拒执行），人工意图 100% 尊重
        #     · 显式批**已就绪 + 其它批缺**  → 让位，且 reason 显式标注「已就绪让位」+ 原显式值
        #                                     （日志可见 ⇒ 人工若确需强跑，去掉 stage 语义或先改就绪状态即可）
        #     · 显式批**已就绪 + 全都就绪**  → 让位后 §3 落到 NONE（合规空转，旧语义本就该空转）
        #   ⚠️ **A 批（采集批）排除在让位之外**（2026-09-17 小九判据，演练 S6 实证）：
        #     人工派 stage=A 的意图几乎必然包含「我要刷新一次采集」（数据源抖动/限流恢复后的
        #     急救）——**重采必须真跑**，让位会吞掉这个急救动作。而 D/E 是**计算批**，
        #     产物就绪即幂等、重跑纯属浪费一个夜窗名额 ⇒ **只有计算批（B/D/E）让位**。
        #     （B 亦为计算批：其产物 TRIPLE_CONSENSUS 等由当日 A 数据算出，就绪即幂等。）
        _yield_ok = (explicit != "A"
                     and ready[explicit][0] and pre is not None and ready[pre][0])
        if _yield_ok:
            _explicit_yield = (f"显式 {explicit} 已就绪，让位给最缺批"
                               f"（原显式意图未执行；若需强跑 {explicit} 请先使其不就绪）")
        else:
            if pre is None:
                return (explicit, True, f"显式 {explicit}（最上游，无前置）", day, kind, out())
            if ready[pre][0]:
                return (explicit, True, f"显式 {explicit}，前置 {pre} 已就绪({ready[pre][1]})", day, kind, out())
            return (explicit, False,
                    f"⛔ 显式 {explicit} 但前置 {pre} 未就绪({ready[pre][1]}) —— 拒绝执行，"
                    f"否则会用陈旧数据算出假新鲜产物", day, kind, out())

    # ── 2) 时间闸：盘后链起点（交易日 18:00 = START_TRADING / T+1 日 08:00 = START_T1；
    #   🔴 2026-09-11 修正：此处原写「交易日 16:00」是过时口径（起点常量已改 18:00），--force 跳过）────
    #   凌晨 00:00-08:59 属**前一数据日的夜间补跑窗口** → 有效时刻按 24:xx 计，
    #   否则 00:30 接力档会恒判「未到起点」→ B 若 22:30 后才跑完，D/E 永远补不上（漏档实锤）。
    eff = (hh + 24, mm) if hh < _NIGHT_CUT else (hh, mm)
    start = START_TRADING if kind == "trading" else START_T1
    if not force and eff < start:
        # 🛡 2026-09-11 一劳永逸（死区根治）：本数据日的链还没到起点，但**上一数据日**
        #   可能中途失败没跑完 —— 此时唯一正解是补跑上一数据日（见 _backfill_candidate）。
        _bf = _backfill_candidate(root, ref)
        if _bf is None:
            return ("NONE", True,
                    f"⏸ 未到{note}盘后链起点（{start[0]:02d}:{start[1]:02d}，现 {hh:02d}:{mm:02d}）"
                    f"，且上一数据日已无未完成批次 → 空转（合规）",
                    day, kind, out())
        day, kind, note, ready = _bf

    # ── 3) 自愈：缺什么跑什么（纯内容级 · 一环套一环）────────────────────────
    # 🔴🔴 2026-09-14 P0 修复（回填死锁根治）：
    #   回填模式下，若某 stage 的上游输入链（PREREQ 链 + 自身采集输入）已被后续日
    #   覆盖（日期严格晚于回填目标日），重跑只会产出更新日期的产物，永远填不上目标日
    #   → 该 stage 不可能回填 → 跳过；四个非就绪 stage 全不可能 → 返回 NONE（等本日起点）。
    _is_backfill = (day != (now.date() if hh >= _NIGHT_CUT
                                  else now.date() - dt.timedelta(days=1)))
    _stages_to_try = ["A", "B", "D", "E"]
    # 🔴🔴 2026-09-17 一劳永逸（主人令「看板一大片红灯」· 小九）：解「串行遮蔽」。
    #   旧行为：`for _s in [...]: if ready: continue; ... return` —— 遇**第一个**未就绪即 return。
    #     后果：D 未就绪时循环在 _s="D" 就返回，**排在后面的 E 连被看见的机会都没有**，
    #     哪怕 E 自身前置已满足、已可跑。E 于是永远排在链尾、永远最容易被夜窗挤掉
    #     （09-17 实测：B 04:30 才完 → D 06:26 才开跑 → E 等下一轮已跨出夜窗 → 7 项红灯）。
    #   新行为：保持 A→B→D→E **优先级顺序不变**，但**前置批未就绪者跳过本批、不遮蔽后续批**。
    #     于是「E 前置（现为 B）已就绪」时，即使 D 因故跑不动，E 仍能被选中 ⇒ 可达性不再被单点掐死。
    #   ⚠️ 零回归保证（逐场景）：
    #     · B 未就绪（正常夜）            → D/E 均因前置 B 未就绪而跳过 → 仍返回 "B"（同旧）
    #     · B 就绪、D 未就绪、E 未就绪     → D 前置 B 已就绪 ⇒ 先返回 "D"（同旧，汇总仍先跑）
    #     · B 就绪、D 就绪、E 未就绪       → D 被 continue，返回 "E"（同旧）
    #     · B 就绪、D 不可回填被跳过、E 未就绪 → 旧逻辑可能落到 NONE；新逻辑返回 "E"（**本次收益**）
    _skip_why: dict[str, str] = {}
    for _s in _stages_to_try:
        if ready[_s][0]:
            continue
        if _is_backfill and not _backfill_feasible(root, _s, day):
            _skip_why[_s] = "回填不可能（上游已被后续日覆盖）"
            continue  # 上游已全被后续日覆盖 → 回填不可能，跳过该 stage

        # 🆕 前置就绪校验：前置未就绪 ⇒ 本批跳过（沿用陈旧上游只会算出假新鲜产物），
        #   但**继续看后面的批**，不遮蔽。
        _pre = PREREQ.get(_s)
        if _pre and not ready[_pre][0]:
            _skip_why[_s] = f"前置 {_pre} 未就绪({ready[_pre][1]})"
            continue

        # 原有放行逻辑（逃生门 + 正常）
        if _s == "A" and _escape[0]:
            return ("B", True,
                    f"A 未就绪({ready['A'][1]})，但{_escape[1]}；"
                    f"→ 本轮跑选股批 B（降级放行，D 批将据此后继放行）",
                    day, kind, dict(out(), DEGRADED_UPSTREAM="1",
                                    degrade_lag_days=str(_escape[2])))
        _reason_map = {
            "A": f"A 未就绪({ready['A'][1]}) -> 跑采集批",
            "B": f"A 就绪({ready['A'][1]}) B 未就绪({ready['B'][1]}) -> 跑选股批",
            "D": f"B 就绪({ready['B'][1]}) D 未就绪({ready['D'][1]}) -> 跑汇总批(最终推荐)",
            "E": f"B 就绪({ready['B'][1]}) E 未就绪({ready['E'][1]}) -> 跑回测批",
        }
        _extra = ("；" + "、".join(f"{k} 跳过({v})" for k, v in _skip_why.items())) if _skip_why else ""
        # 🆕 显式让位留痕（见 §1）：让人工从 reason 立刻看出「我派的批没跑」及原因，可即时纠偏
        _ey = (f"；[{_explicit_yield}]" if _explicit_yield else "")
        return (_s, True, _reason_map[_s] + _extra + _ey, day, kind, out())

    # 所有非就绪 stage 都不可能回填？
    if _is_backfill:
        _imp = [s for s in ("A","B","D","E") if not ready[s][0]]
        if _imp:
            _why = ("；" + "、".join(f"{k}={v}" for k, v in _skip_why.items())) if _skip_why else ""
            _ey2 = (f"；[{_explicit_yield}]" if _explicit_yield else "")
            return ("NONE", True,
                    f"回填目标 {day} 的 {_imp} 全被后续日覆盖->不可能->空转等本日起点{_why}{_ey2}",
                    day, kind, out())
    return ("NONE", True,
            "四批产物均已就绪 -> 空转（合规，真成功）"
            + (f"；[{_explicit_yield}]" if _explicit_yield else ""),
            day, kind, out())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--today", default="", help="指定自然日 YYYY-MM-DD（演练用）")
    ap.add_argument("--hour", type=int, default=-1, help="CST 小时（演练用）")
    ap.add_argument("--minute", type=int, default=-1, help="CST 分钟（演练用）")
    ap.add_argument("--explicit-stage", default="")
    ap.add_argument("--force", action="store_true", help="忽略时间门控（周末/假期审计补跑）")
    ap.add_argument("--recheck", action="store_true",
                    help="只复核就绪度（链尾问责用）：打印 ready_A..E，不做调度决策")
    ap.add_argument("--out", default="", help="写入文件，默认 stdout")
    a = ap.parse_args()
    _ensure_v8_date(a.root)

    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    if a.today:
        try:
            d = dt.datetime.strptime(a.today, "%Y-%m-%d")
            now = now.replace(year=d.year, month=d.month, day=d.day)
        except Exception:
            pass
    if a.hour >= 0:
        now = now.replace(hour=a.hour)
    if a.minute >= 0:
        now = now.replace(minute=a.minute)

    explicit = (a.explicit_stage or "").strip().upper()

    # ── 链尾问责模式：只按「数据日 + 门槛」复核就绪度，避免链尾另写一套新鲜度规则 ──
    if a.recheck:
        if a.today:
            try:
                d = dt.datetime.strptime(a.today, "%Y-%m-%d").date()
            except Exception:
                d = None
        else:
            d = None
        if d is None:
            d, kind, _ = chain_day(now.date(), lookback=10)
            if d is None:
                d, kind = now.date(), "trading"
        else:
            _, kind, _ = chain_day(d, lookback=0)
            if kind == "none":
                kind = "trading"      # --today 传了周日等边缘情况时按交易日口径兜底
        floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
        ds = d.strftime("%Y-%m-%d")
        lines = [f"recheck_day={ds}", f"recheck_kind={kind}"]
        for st in ("A", "B", "D", "E"):
            ok, cnt, _det = check_ready(a.root, st, ds, floor, kind)
            lines.append(f"ready_{st}={cnt}")
            # 🛡 2026-09-11 一劳永逸（阿狸咪）：把闸门的**布尔裁决**一并透出。
            #   链尾问责步曾写死 `[ "$B_FRESH" = "3/3" ]`，而本契约 2026-09-11 已改为
            #   「9 项 / need=8」（ready_B=8/9 或 9/9）→ 字面量永不匹配 → 每轮 B 批假红灯。
            #   透出 true/false 后，问责只消费闸门裁决，不再复制字面量 ⇒ 契约再变也不漂移。
            lines.append(f"ready_ok_{st}={'true' if ok else 'false'}")
        print("\n".join(lines))
        return 0

    target, ok, reason, day, kind, rdy = decide(a.root, now, explicit, a.force)
    proceed = bool(ok and target != "NONE")

    lines = [
        f"target_stage={target}",
        f"stage_ok={'true' if ok else 'false'}",
        f"proceed={'true' if proceed else 'false'}",
        f"chain_day={day.strftime('%Y-%m-%d') if day else 'none'}",
        f"chain_kind={kind}",
        f"cst_hour={now.hour}",
        f"reason={reason}",
    ]
    for k, v in rdy.items():
        lines.append(f"{k}={v}")
    floor = FLOOR_TRADING if kind == "trading" else FLOOR_T1
    day_s = day.strftime("%Y-%m-%d") if day else "-"
    det = " | ".join(f"{s}:{check_ready(a.root, s, day_s, floor, kind)[2]}" for s in ("A", "B", "D", "E"))
    lines.append(f"detail={det}")
    body = "\n".join(lines)

    if a.out:
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(body + "\n")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
