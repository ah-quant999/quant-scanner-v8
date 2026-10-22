# -*- coding: utf-8 -*-
"""
v8/algo_gate_thresholds.py —— 算法「准入 + 降级」双向闸门阈值（唯一权威源）

🔴 设计目的（主人 2026-10-21 令）：
   确保进入 v8 选股策略的是「有正超额、非拖后腿」的因子/算法，而非噪声或伪增量。
   本文件被以下两处共享引用，杜绝口径打架：
     - algorithms/gen_backtest_all_algos.py  （回测链：产出 row.admit_eligible + delist_advice）
     - scripts/v8_delist_advice.py           （下架建议邮件触达）
   （🗑 2026-10-23 主人令：第三消费方「算法记分卡」v8/gen_algo_scorecard.py 整卡退役，本文件不受影响、继续服务回测闸门。）

🟢 准入闸门（研究区 → 交易区，新因子/算法进策略前的硬校验，缺一不可）：
    ADMIT_MIN_SAMPLES     累积样本 ≥ 30
    ADMIT_MIN_EXCESS      成本后超额 > 0（avg_return − bench_avg_return，无 bench 时退化为 avg_return）
    ADMIT_MAX_WORST_TRADE 单笔最差收益 > -15%（单笔熔断线，≤ 即一票否决）
    ADMIT_MAX_CORR_TOP    与头部算法重叠度 < 0.6（防伪增量；⚠ 待回测链补相关性字段）
    ADMIT_MIN_MARKETS     牛/熊/震荡三档中 ≥ 2 档不亏（⚠ 待回测链补分市场胜率字段）

🔴 2026-10-21 字段语义修正（原 ADMIT_MAX_DD → ADMIT_MAX_WORST_TRADE）：
   原实现把「单笔熔断」阈值套在 max_drawdown（权益回撤）字段上——实证翻车：
   强势跟踪 T+45 权益回撤 -19.27% 被误判「触及熔断」标成降级候选，而其单笔最差
   仅 -7.57%、胜率 87.7%、超额 +23.24%（全站最强卡）。根因：权益回撤随持有期
   机械放大（同卡 T+1 仅 -1.35% → T+45 -19.27%），固定 -15% 闸会误杀一切长
   持有期策略，与「卡住拖后腿者」的设计意图相反。熔断本就该看**单笔尾部风险**
   （worst_return）：龙虎机构 T+5 单笔最差 -50.20% 真实触发，强势跟踪 -7.57%
   真实通过。权益回撤保留展示（记分卡列），不进硬闸。

🔴 降级闸门（存量算法，拖后腿者请出去）：
    MIN_SAMPLES         累积样本门槛（< 30 只观测、不进排名、不评估下架）—— 与回测链同值
    LOW_WIN_RATE        胜率红线 45% —— 低于即「低胜率」
    LOW_AVG_RETURN      平均收益红线 0%（已扣成本）—— ≤ 即「低收益」
    降级流程：跌破红线 → 自动标 🔴降级候选 → 观察期 OBSERVE_PERIOD 笔 → 仍不回升 → 权重归零/下架归档

⚠ 诚实声明：ADMIT_MAX_CORR_TOP / ADMIT_MIN_MARKETS 所需字段回测链当前未产出，
   暂以「待接入」处理，不伪造数值；一旦回测链补字段，本闸门自动生效（阈值已就位）。
"""
# ── 降级闸门（与回测链 gen_backtest_all_algos.py 同值，杜绝「刻意不同值」）──
MIN_SAMPLES = 30
LOW_WIN_RATE = 45.0
LOW_AVG_RETURN = 0.0

# ── 准入闸门（新因子/算法进交易区的硬校验）──
ADMIT_MIN_SAMPLES = 30
ADMIT_MIN_EXCESS = 0.0      # 成本后超额必须 > 0
ADMIT_MAX_WORST_TRADE = -15.0  # 单笔最差收益熔断线（≤ 即否决；原 ADMIT_MAX_DD 套错字段，见上方修正说明）
ADMIT_MAX_CORR_TOP = 0.6    # 与头部算法重叠度上限（防伪增量，待接入）
ADMIT_MIN_MARKETS = 2       # 牛/熊/震荡三档中≥2档不亏（待接入）

# ── 观察期（转正前 / 降级裁决前的累积窗口，单位：笔）──
OBSERVE_PERIOD = 20

# 待回测链补字段的准入项（前端/邮件如实标注「待接入」，不伪造）
ADMIT_PENDING_FIELDS = ["ADMIT_MAX_CORR_TOP", "ADMIT_MIN_MARKETS"]
