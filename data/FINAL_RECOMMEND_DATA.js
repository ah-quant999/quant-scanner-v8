window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-07 15:40:24",
  "crisis_score": 34.9,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 8,
  "top_n": 3,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-07 14:35:27",
    "degraded": false,
    "effective": {
      "jinzuan": 0.934,
      "chan": 0.014,
      "trend": -0.594,
      "jigou": -0.704
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 508,
      "chan": 721,
      "trend": 276,
      "jigou": 504
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-11-07 14:35:27",
      "hit": 4,
      "n_snapshots": 104,
      "date_range": [
        "2026-06-06",
        "2026-11-06"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-11-06",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-11-06",
    "pool_total": 8,
    "new_selected": 8,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-11-07",
    "source": "CANDIDATE_QUOTES",
    "covered": 0,
    "total": 8,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "光伏设备",
    "小金属",
    "影视院线",
    "教育",
    "文化传媒",
    "游戏",
    "电池",
    "种植业与林业",
    "能源金属",
    "贵金属",
    "软件开发"
  ],
  "stocks": [],
  "consensus_stocks": [
    {
      "rank": 1,
      "code": "600327",
      "name": "大东方",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "强势跟踪"
      ],
      "source_scores": {
        "强势跟踪": 88.0
      },
      "resonance": 1,
      "strength": 88.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-06",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 88；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "卫生",
      "concepts": [
        "婴童概念",
        "机构重仓",
        "社区团购",
        "内贸流通",
        "新能源车",
        "新零售",
        "长江三角",
        "新材料"
      ],
      "tracking": {
        "entry_date": "2026-11-06",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "601599",
      "name": "浙文影业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "强势跟踪"
      ],
      "source_scores": {
        "强势跟踪": 85.0
      },
      "resonance": 1,
      "strength": 85.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-06",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 85；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "纺织业",
      "concepts": [
        "一带一路",
        "影视概念",
        "低价股",
        "央国企改革",
        "破发股",
        "文娱消费"
      ],
      "tracking": {
        "entry_date": "2026-11-06",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 3,
      "code": "600371",
      "name": "万向德农",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "强势跟踪"
      ],
      "source_scores": {
        "强势跟踪": 73.0
      },
      "resonance": 1,
      "strength": 73.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-06",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 73；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "农、林、牧、渔专业及辅助性活动",
      "concepts": [
        "农业种植",
        "QFII重仓",
        "机构重仓",
        "乡村振兴",
        "微盘股",
        "粮食概念",
        "转基因"
      ],
      "tracking": {
        "entry_date": "2026-11-06",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    }
  ],
  "all_candidates": [
    {
      "code": "600327",
      "name": "大东方",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "卫生",
      "concepts": [
        "婴童概念",
        "机构重仓",
        "社区团购",
        "内贸流通",
        "新能源车",
        "新零售",
        "长江三角",
        "新材料"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "601599",
      "name": "浙文影业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 87.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "纺织业",
      "concepts": [
        "一带一路",
        "影视概念",
        "低价股",
        "央国企改革",
        "破发股",
        "文娱消费"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600371",
      "name": "万向德农",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 34.8,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "农、林、牧、渔专业及辅助性活动",
      "concepts": [
        "农业种植",
        "QFII重仓",
        "机构重仓",
        "乡村振兴",
        "微盘股",
        "粮食概念",
        "转基因"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002310",
      "name": "东方新能",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 8.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "电力、热力生产和供应业",
      "concepts": [
        "富时罗素",
        "标准普尔",
        "小盘股",
        "低价股",
        "绿色电力",
        "央国企改革",
        "2026中报扭亏",
        "小盘成长"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002929",
      "name": "润建股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 8.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "通信技术",
        "大数据",
        "储能概念",
        "充电桩",
        "区块链",
        "智能电网",
        "边缘计算",
        "东数西算"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002578",
      "name": "闽发铝业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 8.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "2026中报首亏",
        "低价股",
        "央国企改革",
        "新能源车",
        "破发股",
        "光伏概念",
        "破增发价股"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "000525",
      "name": "红太阳",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 4.3,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "一带一路",
        "标准普尔",
        "草甘膦",
        "机构重仓",
        "农药兽药",
        "央国企改革",
        "2026中报扭亏",
        "长江三角"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600278",
      "name": "东方创业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 0.0,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "批发业",
      "concepts": [
        "破净股",
        "在线教育",
        "上海自贸",
        "一带一路",
        "沪股通",
        "央国企改革",
        "融资融券",
        "内贸流通"
      ],
      "enter_date": "2026-11-06",
      "stop_loss": 6.41,
      "target_price": 8.54,
      "risk_reward": 2.0,
      "support": 5.96,
      "resistance": 7.12,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-07 15:40:24",
    "score_formula": "final_score = 因子榜 TOP10_DAILY.total_score（2026-09-20 唯一口径：第二套 final_score 公式已整段清除）",
    "where": "algorithms/final_recommend.py :: 方案B 因子融合 + scored 计分",
    "gate": {
      "V8_FUSION_NOISE_FILTER": 1,
      "regime_open": true,
      "regime_coef_note": "非开仓期(_open_regime=False) 因子权重 ×0.3（仅对真计分的因子生效）"
    },
    "integrated": [
      {
        "key": "weak",
        "name": "放量弱势",
        "role": "仅标注",
        "scored": false,
        "adj": 0.0,
        "where": "2026-09-20 已随第二套 final_score 公式清除；仅写 signals 展示",
        "n_hit": 0,
        "evidence": "未回测",
        "why": "FACTOR_LAB 异常换手率 **bottom 档**（放量=弱势）命中池内票即扣分　⚠️ 三重问题（2026-09-18 实测取证）：① **无依据** —— 本档从未纳入 walk-forward 回测（−2.21pp 是 **top 档**的实测值，bottom 档无同类证据），属「凭空的惩罚」，与 P5 明文原则「反向档位无显著负 edge 不给惩罚」冲突；② **设计上不相交** —— bottom 榜 = 极端放量股（abn 最大，弱势特征），而候选池由选股策略产出、天然偏缩量强势，两集合语义相反；实测 bottom ∩ pool = **0** ⇒ 本条几乎恒为 0 分；③ **代码失配（已修）** —— _weak 集合原缺 .lstrip('.') 导致恒不匹配，29 轮 / 1333 条候选命中 0 次"
      },
      {
        "key": "abn",
        "name": "异常换手率",
        "role": "仅展示",
        "scored": false,
        "adj": 0.0,
        "where": "写 tags（V8_FUSION_NOISE_FILTER=1），不写 sources/source_scores",
        "n_hit": 0,
        "evidence": "薄样本(9 信号日 / 85 命中)",
        "why": "实测边际 −2.21pp（负 alpha，命中 85 条）⇒ 整源剔除，不计共振/strength"
      },
      {
        "key": "roe",
        "name": "ROE_TTM",
        "role": "仅展示",
        "scored": false,
        "adj": 0.0,
        "where": "写 signals「高ROE」+ reasons，不写 sources/source_scores",
        "n_hit": 0,
        "evidence": "薄样本(9 信号日 / 89 命中)",
        "why": "实测边际 +0.68pp（弱正，命中 89 条 ≈ 43.9% 覆盖率，无选择性）⇒ 不足与强源同权"
      }
    ],
    "evidence_note": "计分依据分级：①「未回测」= 无任何样本外证据（放量弱势）；②「薄样本」= 9 信号日实测边际，样本不足以定权重，故不计分（异常换手率/ROE_TTM/高手跟踪）；③「walk-forward」= ≥4/5 年 OOS 检验通过才给分（候选池层 P5 的 amt60/turntrend，+6/+3）。本层当前**没有任何因子持有第③级证据** ⇒ 除放量弱势外全部为 0 分，属**有意的保守**。　🔴 结论（2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」）：本层唯一记分的「放量弱势 −0.5」有**三重问题** —— ①无回测依据（bottom 榜从未回测）；②设计上不相交（bottom=极端放量股 vs 候选池=缩量强势，实测交集 0 ⇒ 几乎恒不触发）；③上游 _weak 集合曾因 norm_code 未剥点而恒失配（29 轮命中 0 次，本补丁已修）。⇒ **因子在本层的实际计分影响 = 0**，现状等于「全部只做标注」；要让它真正成为加减分项，须先补 walk-forward 回测（流程见下方 ③ 待接入队列 / 明细见本页 🧪 因子审计卡）。",
    "dedup_note": "因子只对**池内已有票**动作（_factor_in_pool 只查不建）⇒ 不产池、不决定谁能进榜"
  },
  "factor_trace": []
};