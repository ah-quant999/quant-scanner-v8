window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-20 21:55:32",
  "crisis_score": 36.3,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 26,
  "top_n": 3,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-20 20:47:40",
    "degraded": false,
    "effective": {
      "jinzuan": -0.475,
      "chan": 0.279,
      "trend": 0.46,
      "jigou": 0.571
    },
    "hardcoded_default": {
      "jinzuan": -0.522,
      "chan": 0.155,
      "trend": 0.339,
      "jigou": 0.449
    },
    "n_on10": {
      "jinzuan": 590,
      "chan": 795,
      "trend": 277,
      "jigou": 519
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-11-20 20:47:40",
      "hit": 4,
      "n_snapshots": 113,
      "date_range": [
        "2026-06-06",
        "2026-11-19"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-11-19） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-11-20",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-11-20",
    "pool_total": 8,
    "new_selected": 6,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-11-20",
    "source": "STOCK_QUOTE",
    "covered": 26,
    "total": 26,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "保险",
    "公路铁路运输",
    "小金属",
    "机场航运",
    "汽车整车",
    "港口航运",
    "电力",
    "白酒",
    "证券",
    "贵金属",
    "银行",
    "黑色家电"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "300790",
      "name": "宇瞳光学",
      "market": "sz",
      "board": "创业板",
      "horizon": "中长线",
      "close": 13.78,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.11,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 12.4,
      "target_price": 20.88,
      "risk_reward": 5.15,
      "support": 13.78,
      "resistance": 17.3,
      "atr": 0.94,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.7
      },
      "resonance": 1,
      "strength": 4.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.7,
      "mix_pct": 100.0,
      "buy_score": 4.7,
      "enter_date": "2026-11-20",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "激光雷达",
        "机器人概念",
        "融资融券",
        "电子后视镜",
        "股权激励",
        "创业板综",
        "职业教育"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 13.78,
        "latest_price": 13.78,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "601991",
      "name": "大唐发",
      "market": "sh",
      "board": "主板",
      "horizon": "中长线",
      "close": 4.48,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -3.03,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 4.03,
      "target_price": 6.03,
      "risk_reward": 3.46,
      "support": 4.46,
      "resistance": 5.01,
      "atr": 0.14,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.7
      },
      "resonance": 1,
      "strength": 4.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.7,
      "mix_pct": 100.0,
      "buy_score": 4.7,
      "enter_date": "2026-11-20",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第2名）",
      "industry": "电力、热力生产和供应业",
      "concepts": [
        "绿色电力",
        "融资融券",
        "标准普尔",
        "央国企改革",
        "AH股",
        "核能核电",
        "沪股通",
        "风能"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 4.48,
        "latest_price": 4.48,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 3,
      "code": "300083",
      "name": "创世纪",
      "market": "sz",
      "board": "创业板",
      "horizon": "中长线",
      "close": 8.64,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -6.49,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 7.78,
      "target_price": 14.39,
      "risk_reward": 6.66,
      "support": 8.64,
      "resistance": 11.67,
      "atr": 0.59,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.7
      },
      "resonance": 1,
      "strength": 4.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.7,
      "mix_pct": 100.0,
      "buy_score": 4.7,
      "enter_date": "2026-11-20",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第3名）",
      "industry": "通用设备制造业",
      "concepts": [
        "深股通",
        "富时罗素",
        "工业互联",
        "飞行汽车(eVTOL)",
        "低空经济",
        "融资融券",
        "小盘股",
        "新型工业化"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 8.64,
        "latest_price": 8.64,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    }
  ],
  "consensus_stocks": [
    {
      "rank": 1,
      "code": "600838",
      "name": "上海九百",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 7.58,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -5.49,
      "stop_loss": 6.82,
      "target_price": 14.89,
      "risk_reward": 9.64,
      "support": 7.57,
      "resistance": 14.89,
      "atr": 1.02,
      "sources": [
        "动量共识",
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 3.2,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 4.2,
      "final_score": 3.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-20",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第16名）；动量共识筛选共振（无未来函数版）",
      "industry": "零售业",
      "concepts": [
        "融资融券",
        "新零售",
        "长江三角",
        "参股券商",
        "央国企改革",
        "内贸流通"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 7.58,
        "latest_price": 7.58,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "002771",
      "name": "真视通",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.82,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 10.01,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "动量共识",
        "强势跟踪"
      ],
      "source_scores": {
        "强势跟踪": 75.0,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 76.0,
      "final_score": 0.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-20",
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "强势跟踪（短线情绪选股）当日新入选·强度分 75；高手强势股跟踪池共振（IMA 状态有效）；动量共识筛选共振（无未来函数版）",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "AI制药（医疗）",
        "互联网服务",
        "网络安全",
        "工业互联",
        "人工智能",
        "数据中心",
        "军工",
        "军民融合"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 15.82,
        "latest_price": 15.82,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 3,
      "code": "300790",
      "name": "宇瞳光学",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 13.78,
      "close_date": "2026-11-20",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.11,
      "stop_loss": 12.4,
      "target_price": 20.88,
      "risk_reward": 5.15,
      "support": 13.78,
      "resistance": 17.3,
      "atr": 0.94,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.7
      },
      "resonance": 1,
      "strength": 4.7,
      "final_score": 4.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-20",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "激光雷达",
        "机器人概念",
        "融资融券",
        "电子后视镜",
        "股权激励",
        "创业板综",
        "职业教育"
      ],
      "tracking": {
        "entry_date": "2026-11-20",
        "entry_price": 13.78,
        "latest_price": 13.78,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    }
  ],
  "all_candidates": [
    {
      "code": "300790",
      "name": "宇瞳光学",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 13.78,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -4.11,
      "final_score": 4.7,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "激光雷达",
        "机器人概念",
        "融资融券",
        "电子后视镜",
        "股权激励",
        "创业板综",
        "职业教育"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 12.4,
      "target_price": 20.88,
      "risk_reward": 5.15,
      "support": 13.78,
      "resistance": 17.3,
      "factor_actions": []
    },
    {
      "code": "601991",
      "name": "大唐发",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 4.48,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -3.03,
      "final_score": 4.7,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电力、热力生产和供应业",
      "concepts": [
        "绿色电力",
        "融资融券",
        "标准普尔",
        "央国企改革",
        "AH股",
        "核能核电",
        "沪股通",
        "风能"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 4.03,
      "target_price": 6.03,
      "risk_reward": 3.46,
      "support": 4.46,
      "resistance": 5.01,
      "factor_actions": []
    },
    {
      "code": "300083",
      "name": "创世纪",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 8.64,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -6.49,
      "final_score": 4.7,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "深股通",
        "富时罗素",
        "工业互联",
        "飞行汽车(eVTOL)",
        "低空经济",
        "融资融券",
        "小盘股",
        "新型工业化"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 7.78,
      "target_price": 14.39,
      "risk_reward": 6.66,
      "support": 8.64,
      "resistance": 11.67,
      "factor_actions": []
    },
    {
      "code": "300900",
      "name": "广联航空",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 15.59,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -7.7,
      "final_score": 4.7,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "深股通",
        "飞行汽车(eVTOL)",
        "融资融券",
        "低空经济",
        "大飞机",
        "军民融合",
        "航天航空",
        "创业板综"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 14.03,
      "target_price": 24.86,
      "risk_reward": 5.95,
      "support": 15.56,
      "resistance": 23.83,
      "factor_actions": []
    },
    {
      "code": "300913",
      "name": "兆龙互连",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 26.36,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -6.36,
      "final_score": 4.6,
      "mix_pct": 93.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "光通信模块",
        "机器人概念",
        "深股通",
        "铜缆高速连接",
        "融资融券",
        "数据中心",
        "小盘股",
        "5G概念"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 23.72,
      "target_price": 47.47,
      "risk_reward": 8.01,
      "support": 26.34,
      "resistance": 31.2,
      "factor_actions": []
    },
    {
      "code": "601126",
      "name": "四方股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 25.2,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -7.15,
      "final_score": 4.6,
      "mix_pct": 93.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "中盘股",
        "人工智能",
        "铁路基建",
        "融资融券",
        "智能电网",
        "先进制造风格",
        "电网概念",
        "军民融合"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 22.68,
      "target_price": 47.02,
      "risk_reward": 8.66,
      "support": 25.2,
      "resistance": 32.7,
      "factor_actions": []
    },
    {
      "code": "600186",
      "name": "莲花控股",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 9.07,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 0.67,
      "final_score": 4.4,
      "mix_pct": 80.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "食品制造业",
      "concepts": [
        "电商概念",
        "味蕾经济",
        "人造肉",
        "融资融券",
        "2026中报预增",
        "小盘股",
        "算力概念",
        "机构重仓"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 8.16,
      "target_price": 14.18,
      "risk_reward": 5.64,
      "support": 7.89,
      "resistance": 9.72,
      "factor_actions": []
    },
    {
      "code": "600206",
      "name": "有研新材",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 37.84,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -4.83,
      "final_score": 4.1,
      "mix_pct": 60.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "存储芯片",
        "融资融券",
        "小盘股",
        "标准普尔",
        "医疗器械概念",
        "央国企改革",
        "沪股通",
        "中芯概念"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 34.06,
      "target_price": 56.18,
      "risk_reward": 4.85,
      "support": 31.56,
      "resistance": 43.0,
      "factor_actions": []
    },
    {
      "code": "002432",
      "name": "九安医疗",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 49.35,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -9.99,
      "final_score": 3.9,
      "mix_pct": 46.7,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "医药医疗风格",
        "融资融券",
        "小盘股",
        "小米概念",
        "多模态AI",
        "昨日高换手",
        "智能穿戴",
        "流感"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 44.41,
      "target_price": 71.68,
      "risk_reward": 4.52,
      "support": 49.35,
      "resistance": 60.42,
      "factor_actions": []
    },
    {
      "code": "000657",
      "name": "中钨高新",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 32.86,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -6.46,
      "final_score": 3.8,
      "mix_pct": 40.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "金属制品业",
      "concepts": [
        "融资融券",
        "PCB",
        "养老金",
        "医疗器械概念",
        "央国企改革",
        "深股通",
        "HS300",
        "MSCI中国"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 29.57,
      "target_price": 69.58,
      "risk_reward": 11.17,
      "support": 32.86,
      "resistance": 43.16,
      "factor_actions": []
    },
    {
      "code": "688059",
      "name": "华锐精密",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 65.03,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -6.69,
      "final_score": 3.7,
      "mix_pct": 33.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "金属制品业",
      "concepts": [
        "机器人概念",
        "融资融券",
        "2026中报预增",
        "机构重仓",
        "专精特新",
        "工业母机",
        "沪股通",
        "2026一季报预增"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 58.53,
      "target_price": 94.7,
      "risk_reward": 4.56,
      "support": 61.6,
      "resistance": 80.49,
      "factor_actions": []
    },
    {
      "code": "688403",
      "name": "汇成股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 12.65,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -9.71,
      "final_score": 3.6,
      "mix_pct": 26.7,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [],
      "enter_date": "2026-11-20",
      "stop_loss": 11.38,
      "target_price": 27.46,
      "risk_reward": 11.71,
      "support": 12.64,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "688432",
      "name": "有研硅",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 29.8,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -5.31,
      "final_score": 3.4,
      "mix_pct": 13.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中芯概念",
        "存储芯片",
        "融资融券",
        "小盘股",
        "半导体概念",
        "沪股通"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 26.82,
      "target_price": 60.59,
      "risk_reward": 10.33,
      "support": 28.16,
      "resistance": 36.67,
      "factor_actions": []
    },
    {
      "code": "688411",
      "name": "海博思创",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 133.58,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -7.75,
      "final_score": 3.4,
      "mix_pct": 13.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [],
      "enter_date": "2026-11-20",
      "stop_loss": 120.22,
      "target_price": 209.9,
      "risk_reward": 5.71,
      "support": 127.3,
      "resistance": 192.4,
      "factor_actions": []
    },
    {
      "code": "688035",
      "name": "德邦科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 51.29,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -12.07,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "存储芯片",
        "新能源车",
        "融资融券",
        "消费电子概念",
        "光伏概念",
        "高带宽内存",
        "专精特新",
        "液冷概念"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 46.16,
      "target_price": 87.9,
      "risk_reward": 7.14,
      "support": 47.8,
      "resistance": 67.0,
      "factor_actions": []
    },
    {
      "code": "600838",
      "name": "上海九百",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 7.58,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -5.49,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 2,
      "sources": [
        "动量共识",
        "因子榜"
      ],
      "signals": [
        "动量共识",
        "因子榜入选"
      ],
      "industry": "零售业",
      "concepts": [
        "融资融券",
        "新零售",
        "长江三角",
        "参股券商",
        "央国企改革",
        "内贸流通"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 6.82,
      "target_price": 14.89,
      "risk_reward": 9.64,
      "support": 7.57,
      "resistance": 14.89,
      "factor_actions": []
    },
    {
      "code": "688082",
      "name": "盛美上海",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 217.03,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -3.11,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "融资融券",
        "HS300",
        "百元股",
        "大盘股",
        "上证180",
        "高带宽内存",
        "专精特新",
        "大盘成长"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 195.33,
      "target_price": 315.8,
      "risk_reward": 4.55,
      "support": 155.0,
      "resistance": 235.0,
      "factor_actions": []
    },
    {
      "code": "000063",
      "name": "中兴通讯",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 26.3,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -3.1,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "证金持股",
        "融资融券",
        "边缘计算",
        "在线教育",
        "标准普尔",
        "智能穿戴",
        "信创",
        "云计算"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 23.67,
      "target_price": 34.89,
      "risk_reward": 3.27,
      "support": 26.26,
      "resistance": 29.12,
      "factor_actions": []
    },
    {
      "code": "600999",
      "name": "招商证券",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 15.68,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": -1.14,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "证金持股",
        "融资融券",
        "标准普尔",
        "央国企改革",
        "AH股",
        "沪股通",
        "HS300",
        "MSCI中国"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 14.11,
      "target_price": 18.76,
      "risk_reward": 1.97,
      "support": 15.3,
      "resistance": 16.58,
      "factor_actions": []
    },
    {
      "code": "601211",
      "name": "国泰海通",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 16.6,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 0.61,
      "final_score": 3.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "证金持股",
        "融资融券",
        "标准普尔",
        "AH股",
        "沪股通",
        "HS300",
        "MSCI中国",
        "大盘股"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 14.94,
      "target_price": 17.75,
      "risk_reward": 0.69,
      "support": 15.59,
      "resistance": 16.76,
      "factor_actions": []
    },
    {
      "code": "002771",
      "name": "真视通",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.82,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 10.01,
      "final_score": 0.0,
      "mix_pct": 100.0,
      "resonance": 2,
      "sources": [
        "动量共识",
        "强势跟踪"
      ],
      "signals": [
        "动量共识",
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "AI制药（医疗）",
        "互联网服务",
        "网络安全",
        "工业互联",
        "人工智能",
        "数据中心",
        "军工",
        "军民融合"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "603324",
      "name": "盛剑科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 27.71,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 10.0,
      "final_score": 0.0,
      "mix_pct": 60.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "中芯概念",
        "昨日高振幅",
        "节能环保",
        "光刻机(胶)",
        "专精特新",
        "2026中报首亏",
        "尾气治理",
        "华为概念"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600360",
      "name": "华微电子",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.01,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 10.01,
      "final_score": 0.0,
      "mix_pct": 60.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "国产芯片",
        "新能源车",
        "昨日高振幅",
        "东北振兴",
        "央国企改革",
        "充电桩",
        "第三代半导体",
        "LED概念"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "301132",
      "name": "满坤科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 51.07,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 20.0,
      "final_score": 0.0,
      "mix_pct": 20.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "光通信模块",
        "机器人概念",
        "深股通",
        "新能源车",
        "融资融券",
        "PCB",
        "创业板综",
        "无人驾驶"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600327",
      "name": "大东方",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.83,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 10.02,
      "final_score": 0.0,
      "mix_pct": 20.0,
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
        "IPO受益",
        "新材料",
        "社区团购",
        "新能源车",
        "参股银行",
        "婴童概念",
        "2026中报预减",
        "机构重仓"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": 4.35,
      "target_price": 7.37,
      "risk_reward": 5.26,
      "support": 3.69,
      "resistance": 7.37,
      "factor_actions": []
    },
    {
      "code": "300812",
      "name": "易天股份",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 18.0,
      "close_date": "2026-11-20",
      "close_verified": true,
      "pct_chg": 20.0,
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
      "industry": "专用设备制造业",
      "concepts": [
        "先进封装",
        "OLED",
        "玻璃基板",
        "MiniLED",
        "柔性屏(折叠屏)",
        "机构重仓",
        "创业板综",
        "深圳特区"
      ],
      "enter_date": "2026-11-20",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-20 21:55:32",
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
  "factor_trace": [],
  "validity": {
    "status": "ok",
    "reason": "候选源正常",
    "ima_data_date": "2026-11-20",
    "ima_pool_total": 8,
    "assessed_at": "2026-11-20 21:55:32"
  }
};