window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-04 18:08:29",
  "crisis_score": 33.8,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 5,
  "top_n": 3,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-04 16:41:57",
    "degraded": false,
    "effective": {
      "jinzuan": -0.027,
      "chan": 0.49,
      "trend": -0.12,
      "jigou": 0.041
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 328,
      "chan": 544,
      "trend": 275,
      "jigou": 498
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-11-04 16:41:57",
      "hit": 4,
      "n_snapshots": 101,
      "date_range": [
        "2026-06-06",
        "2026-11-01"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-11-03） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-11-03",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-11-03",
    "pool_total": 8,
    "new_selected": 5,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-11-04",
    "source": "STOCK_QUOTE",
    "covered": 5,
    "total": 5,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "保险",
    "公路铁路运输",
    "医疗服务",
    "小金属",
    "影视院线",
    "旅游及酒店",
    "机场航运",
    "游戏",
    "白酒",
    "贵金属",
    "食品加工制造",
    "饮料制造"
  ],
  "stocks": [],
  "consensus_stocks": [
    {
      "rank": 1,
      "code": "600261",
      "name": "阳光照明",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.46,
      "close_date": "2026-11-04",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -9.9,
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
        "强势跟踪": 100.0
      },
      "resonance": 1,
      "strength": 100.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-03",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 100；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "参股券商",
        "长江三角",
        "低价股",
        "标准普尔",
        "节能环保",
        "破增发价股",
        "富时罗素",
        "LED概念"
      ],
      "tracking": {
        "entry_date": "2026-11-03",
        "entry_price": 4.46,
        "latest_price": 4.46,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "002652",
      "name": "扬子新材",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.59,
      "close_date": "2026-11-04",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 10.07,
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
        "强势跟踪": 80.0
      },
      "resonance": 1,
      "strength": 80.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-03",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 80；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "金属制品业",
      "concepts": [
        "养老概念",
        "微盘股",
        "纳米银",
        "QFII重仓",
        "雄安新区",
        "机构重仓",
        "新材料"
      ],
      "tracking": {
        "entry_date": "2026-11-03",
        "entry_price": 4.59,
        "latest_price": 4.59,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 3,
      "code": "002522",
      "name": "浙江众成",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.92,
      "close_date": "2026-11-04",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -2.77,
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
        "强势跟踪": 71.0
      },
      "resonance": 1,
      "strength": 71.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-03",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 71；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "橡胶和塑料制品业",
      "concepts": [
        "专精特新",
        "光纤概念",
        "央国企改革",
        "深股通",
        "破增发价股",
        "富时罗素",
        "通信技术",
        "5G概念"
      ],
      "tracking": {
        "entry_date": "2026-11-03",
        "entry_price": 4.92,
        "latest_price": 4.92,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    }
  ],
  "all_candidates": [
    {
      "code": "600261",
      "name": "阳光照明",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.46,
      "close_date": "2026-11-04",
      "close_verified": true,
      "pct_chg": -9.9,
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
      "industry": "电气机械和器材制造业",
      "concepts": [
        "参股券商",
        "长江三角",
        "低价股",
        "标准普尔",
        "节能环保",
        "破增发价股",
        "富时罗素",
        "LED概念"
      ],
      "enter_date": "2026-11-03",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002652",
      "name": "扬子新材",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.59,
      "close_date": "2026-11-04",
      "close_verified": true,
      "pct_chg": 10.07,
      "final_score": 0.0,
      "mix_pct": 37.5,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "金属制品业",
      "concepts": [
        "养老概念",
        "微盘股",
        "纳米银",
        "QFII重仓",
        "雄安新区",
        "机构重仓",
        "新材料"
      ],
      "enter_date": "2026-11-03",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002522",
      "name": "浙江众成",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.92,
      "close_date": "2026-11-04",
      "close_verified": true,
      "pct_chg": -2.77,
      "final_score": 0.0,
      "mix_pct": 9.4,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "橡胶和塑料制品业",
      "concepts": [
        "专精特新",
        "光纤概念",
        "央国企改革",
        "深股通",
        "破增发价股",
        "富时罗素",
        "通信技术",
        "5G概念"
      ],
      "enter_date": "2026-11-03",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "000591",
      "name": "太阳能",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.49,
      "close_date": "2026-11-04",
      "close_verified": true,
      "pct_chg": -2.18,
      "final_score": 0.0,
      "mix_pct": 9.4,
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
        "智能电网",
        "碳交易",
        "央国企改革",
        "储能概念",
        "深成500",
        "机构重仓",
        "西部大开发",
        "钙钛矿电池"
      ],
      "enter_date": "2026-11-03",
      "stop_loss": 4.04,
      "target_price": 4.6,
      "risk_reward": 0.24,
      "support": 3.86,
      "resistance": 4.6,
      "factor_actions": []
    },
    {
      "code": "601123",
      "name": "马矿股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 16.58,
      "close_date": "2026-11-04",
      "close_verified": true,
      "pct_chg": 10.02,
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
      "industry": "",
      "concepts": [],
      "enter_date": "2026-11-03",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-04 18:08:29",
    "score_formula": "final_score = 因子榜 TOP10_DAILY.total_score（2026-09-20 唯一口径：第二套 final_score 公式已整段清除）",
    "where": "algorithms/final_recommend.py :: 方案B 因子融合",
    "gate": {
      "V8_FUSION_NOISE_FILTER": 1,
      "regime_open": true
    },
    "integrated": [],
    "skipped": true,
    "skip_reason": "本轮 FACTOR_LAB.js 缺失/内容陈旧 ⇒ 方案B 因子融合整体跳过（数据降级）"
  },
  "factor_trace": []
};