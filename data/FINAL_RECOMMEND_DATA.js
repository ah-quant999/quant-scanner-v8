window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-26 00:04:28",
  "crisis_score": 35.6,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 26,
  "top_n": 2,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-25 08:04:00",
    "degraded": false,
    "effective": {
      "jinzuan": -0.389,
      "chan": 0.328,
      "trend": 0.531,
      "jigou": 0.611
    },
    "hardcoded_default": {
      "jinzuan": -0.522,
      "chan": 0.155,
      "trend": 0.339,
      "jigou": 0.449
    },
    "n_on10": {
      "jinzuan": 589,
      "chan": 794,
      "trend": 277,
      "jigou": 518
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-11-25 08:04:00",
      "hit": 4,
      "n_snapshots": 116,
      "date_range": [
        "2026-06-06",
        "2026-11-24"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-11-24） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-11-25",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "index_trend_gate": {
    "triggered": true,
    "close": 3538.95,
    "ma20": 3628.61,
    "note": "上证收盘<MA20且MA20向下 → 防守模式：推票减半（2026-11-21 主人令·该状态历史回测推票 T+20 -23%~-27.7%）"
  },
  "ima_intake": {
    "data_date": "2026-11-24",
    "pool_total": 8,
    "new_selected": 6,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-11-21 主人令：参与 Top3 竞位——高手票按同量纲映射分与因子榜统一排序（V8_IMA_COMPETE=1），进最终推荐仍须先入因子榜池",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-11-25",
    "source": "STOCK_QUOTE",
    "covered": 26,
    "total": 26,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "保险",
    "元件",
    "小金属",
    "机场航运",
    "港口航运",
    "电子化学品",
    "电机",
    "自动化设备",
    "证券",
    "贵金属",
    "通信服务",
    "银行"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "600999",
      "name": "招商证券",
      "market": "sh",
      "board": "主板",
      "horizon": "中长线",
      "close": 15.21,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -2.5,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 14.2,
      "target_price": 18.76,
      "risk_reward": 1.89,
      "support": 15.3,
      "resistance": 16.58,
      "atr": 0.28,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.5
      },
      "resonance": 1,
      "strength": 4.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.5,
      "mix_pct": 100.0,
      "buy_score": 4.5,
      "enter_date": "2026-11-24",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）",
      "industry": "资本市场服务",
      "concepts": [
        "AH股",
        "央国企改革",
        "上证180",
        "大盘价值",
        "券商概念",
        "标准普尔",
        "机构重仓",
        "深圳特区"
      ],
      "tracking": {
        "entry_date": "2026-11-24",
        "entry_price": 15.21,
        "latest_price": 15.21,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（指数趋势防守：该状态历史回测推票大幅负期望）",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "601211",
      "name": "国泰海通",
      "market": "sh",
      "board": "主板",
      "horizon": "中长线",
      "close": 16.09,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -2.07,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 14.72,
      "target_price": 17.75,
      "risk_reward": 0.85,
      "support": 15.59,
      "resistance": 16.76,
      "atr": 0.28,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.5
      },
      "resonance": 1,
      "strength": 4.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.5,
      "mix_pct": 100.0,
      "buy_score": 4.5,
      "enter_date": "2026-11-24",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第2名）",
      "industry": "资本市场服务",
      "concepts": [
        "AH股",
        "上证180",
        "券商概念",
        "标准普尔",
        "机构重仓",
        "并购重组概念",
        "股权激励",
        "金融地产风格"
      ],
      "tracking": {
        "entry_date": "2026-11-24",
        "entry_price": 16.09,
        "latest_price": 16.09,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（指数趋势防守：该状态历史回测推票大幅负期望）",
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
      "close": 8.59,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.18,
      "stop_loss": 7.51,
      "target_price": 14.89,
      "risk_reward": 7.85,
      "support": 7.38,
      "resistance": 14.89,
      "atr": 1.03,
      "sources": [
        "动量共识",
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 3.1,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 4.1,
      "final_score": 3.1,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-24",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第10名）；动量共识筛选共振（无未来函数版）",
      "industry": "零售业",
      "concepts": [
        "融资融券",
        "央国企改革",
        "新零售",
        "长江三角",
        "参股券商",
        "内贸流通"
      ],
      "tracking": {
        "entry_date": "2026-11-24",
        "entry_price": 8.59,
        "latest_price": 8.59,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（指数趋势防守：该状态历史回测推票大幅负期望）",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "688322",
      "name": "奥比中光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 94.8,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -7.16,
      "stop_loss": 91.76,
      "target_price": 122.88,
      "risk_reward": 2.05,
      "support": 82.29,
      "resistance": 122.88,
      "atr": 9.77,
      "sources": [
        "动量共识",
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 3.0,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 4.0,
      "final_score": 3.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-24",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第15名）；动量共识筛选共振（无未来函数版）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "专精特新",
        "机器人概念",
        "机器视觉",
        "英伟达概念",
        "生物识别",
        "破增发价股",
        "国产芯片",
        "元宇宙概念"
      ],
      "tracking": {
        "entry_date": "2026-11-24",
        "entry_price": 94.8,
        "latest_price": 94.8,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（指数趋势防守：该状态历史回测推票大幅负期望）",
      "market_regime": "grind"
    }
  ],
  "all_candidates": [
    {
      "code": "301413",
      "name": "安培龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 82.19,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -8.38,
      "final_score": 4.5,
      "mix_pct": 100.0,
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
        "小盘成长",
        "融资融券",
        "人形机器人",
        "专精特新",
        "创业板综",
        "传感器",
        "深股通",
        "小盘股"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 67.28,
      "target_price": 86.0,
      "risk_reward": 1.5,
      "support": 59.48,
      "resistance": 86.0,
      "factor_actions": []
    },
    {
      "code": "600999",
      "name": "招商证券",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 15.21,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.5,
      "final_score": 4.5,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "AH股",
        "央国企改革",
        "上证180",
        "大盘价值",
        "券商概念",
        "标准普尔",
        "机构重仓",
        "深圳特区"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 14.2,
      "target_price": 18.76,
      "risk_reward": 1.89,
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
      "close": 16.09,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.07,
      "final_score": 4.5,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "AH股",
        "上证180",
        "券商概念",
        "标准普尔",
        "机构重仓",
        "并购重组概念",
        "股权激励",
        "金融地产风格"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 14.72,
      "target_price": 17.75,
      "risk_reward": 0.85,
      "support": 15.59,
      "resistance": 16.76,
      "factor_actions": []
    },
    {
      "code": "300083",
      "name": "创世纪",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 8.83,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.16,
      "final_score": 4.4,
      "mix_pct": 94.4,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "融资融券",
        "工业互联",
        "人形机器人",
        "飞行汽车(eVTOL)",
        "创业板综",
        "医疗器械概念",
        "新型工业化",
        "深股通"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 8.15,
      "target_price": 14.39,
      "risk_reward": 5.9,
      "support": 8.48,
      "resistance": 11.67,
      "factor_actions": []
    },
    {
      "code": "000063",
      "name": "中兴通讯",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 25.51,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.35,
      "final_score": 4.4,
      "mix_pct": 94.4,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "超清视频",
        "智能穿戴",
        "东方财富热股",
        "AH股",
        "物联网",
        "液冷概念",
        "科技风格",
        "IPv6"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 23.98,
      "target_price": 34.89,
      "risk_reward": 3.1,
      "support": 25.62,
      "resistance": 29.12,
      "factor_actions": []
    },
    {
      "code": "300900",
      "name": "广联航空",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 15.75,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.75,
      "final_score": 4.4,
      "mix_pct": 94.4,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "融资融券",
        "无人机",
        "军民融合",
        "人形机器人",
        "飞行汽车(eVTOL)",
        "专精特新",
        "创业板综",
        "航天航空"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 14.8,
      "target_price": 24.86,
      "risk_reward": 5.11,
      "support": 15.08,
      "resistance": 23.83,
      "factor_actions": []
    },
    {
      "code": "600261",
      "name": "阳光照明",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.53,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -6.6,
      "final_score": 4.07,
      "mix_pct": 76.0,
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
        "破增发价股",
        "融资融券",
        "LED概念",
        "证金持股",
        "低价股",
        "贬值受益",
        "氢能源",
        "长江三角"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 3.97,
      "target_price": 6.38,
      "risk_reward": 4.47,
      "support": 3.22,
      "resistance": 6.38,
      "factor_actions": []
    },
    {
      "code": "000657",
      "name": "中钨高新",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 32.47,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.5,
      "final_score": 3.8,
      "mix_pct": 61.1,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "金属制品业",
      "concepts": [
        "央国企改革",
        "可控核聚变",
        "PCB",
        "海南自贸",
        "新材料",
        "深股通",
        "融资融券",
        "养老金"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 31.44,
      "target_price": 69.58,
      "risk_reward": 9.92,
      "support": 32.06,
      "resistance": 43.16,
      "factor_actions": []
    },
    {
      "code": "002432",
      "name": "九安医疗",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 46.19,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.39,
      "final_score": 3.7,
      "mix_pct": 55.6,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "多模态AI",
        "昨日高换手",
        "智能穿戴",
        "东方财富热股",
        "创新医疗服务",
        "物联网",
        "新零售",
        "互联医疗"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 43.58,
      "target_price": 70.95,
      "risk_reward": 4.65,
      "support": 44.84,
      "resistance": 60.42,
      "factor_actions": []
    },
    {
      "code": "688403",
      "name": "汇成股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 12.3,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -8.35,
      "final_score": 3.6,
      "mix_pct": 50.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [],
      "enter_date": "2026-11-24",
      "stop_loss": 11.89,
      "target_price": 27.46,
      "risk_reward": 10.79,
      "support": 12.08,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "300539",
      "name": "横河精密",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 21.42,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.14,
      "final_score": 3.42,
      "mix_pct": 40.0,
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
        "减速器",
        "华为汽车",
        "无人机",
        "股权激励",
        "PEEK材料概念",
        "专精特新",
        "创业板综",
        "机器人概念"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 16.94,
      "target_price": 21.88,
      "risk_reward": 1.63,
      "support": 15.37,
      "resistance": 21.88,
      "factor_actions": []
    },
    {
      "code": "002611",
      "name": "东方精工",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.39,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.33,
      "final_score": 3.28,
      "mix_pct": 32.0,
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
        "多模态AI",
        "氢能源",
        "机器人概念",
        "标准普尔",
        "海洋经济",
        "可控核聚变",
        "无人机",
        "股权激励"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002685",
      "name": "华东重机",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 8.97,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": 0.22,
      "final_score": 3.13,
      "mix_pct": 24.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "TOPCon电池",
        "2026中报预增",
        "融资融券",
        "国产芯片",
        "专精特新",
        "氢能源",
        "半导体概念",
        "传感器"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 7.33,
      "target_price": 9.77,
      "risk_reward": 2.0,
      "support": 4.38,
      "resistance": 8.14,
      "factor_actions": []
    },
    {
      "code": "688158",
      "name": "优刻得",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 22.86,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.96,
      "final_score": 3.1,
      "mix_pct": 22.2,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "互联网和相关服务",
      "concepts": [
        "液冷概念",
        "智谱AI概念",
        "破发股",
        "商业航天",
        "QFII重仓",
        "小盘成长",
        "东数西算",
        "股权激励"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 22.08,
      "target_price": 32.58,
      "risk_reward": 3.28,
      "support": 22.96,
      "resistance": 31.12,
      "factor_actions": []
    },
    {
      "code": "600838",
      "name": "上海九百",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 8.59,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": 1.18,
      "final_score": 3.1,
      "mix_pct": 22.2,
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
        "央国企改革",
        "新零售",
        "长江三角",
        "参股券商",
        "内贸流通"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 7.51,
      "target_price": 14.89,
      "risk_reward": 7.85,
      "support": 7.38,
      "resistance": 14.89,
      "factor_actions": []
    },
    {
      "code": "688836",
      "name": "宇树科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 690.0,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -3.9,
      "final_score": 3.1,
      "mix_pct": 22.2,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-11-24",
      "stop_loss": 637.2,
      "target_price": 809.0,
      "risk_reward": 1.43,
      "support": 565.0,
      "resistance": 809.0,
      "factor_actions": []
    },
    {
      "code": "300825",
      "name": "阿尔特",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 10.7,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -12.58,
      "final_score": 3.1,
      "mix_pct": 22.2,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专业技术服务业",
      "concepts": [
        "多模态AI",
        "飞行汽车(eVTOL)",
        "智谱AI概念",
        "机器人概念",
        "海洋经济",
        "英伟达概念",
        "减速器",
        "宠物经济"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 9.64,
      "target_price": 15.91,
      "risk_reward": 4.86,
      "support": 9.62,
      "resistance": 15.91,
      "factor_actions": []
    },
    {
      "code": "300007",
      "name": "汉威科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 37.14,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.03,
      "final_score": 3.1,
      "mix_pct": 22.2,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "智能穿戴",
        "专精特新",
        "物联网",
        "氢能源",
        "机器人概念",
        "互联医疗",
        "小盘成长",
        "无人机"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 32.49,
      "target_price": 45.37,
      "risk_reward": 2.57,
      "support": 29.12,
      "resistance": 45.37,
      "factor_actions": []
    },
    {
      "code": "603799",
      "name": "华友钴业",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 30.13,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.65,
      "final_score": 3.1,
      "mix_pct": 22.2,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "QFII重仓",
        "融资融券",
        "电池技术",
        "锂电池概念",
        "大盘股",
        "固态电池",
        "小金属概念",
        "上证180"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "688322",
      "name": "奥比中光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 94.8,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.16,
      "final_score": 3.0,
      "mix_pct": 16.7,
      "resonance": 2,
      "sources": [
        "动量共识",
        "因子榜"
      ],
      "signals": [
        "动量共识",
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "专精特新",
        "机器人概念",
        "机器视觉",
        "英伟达概念",
        "生物识别",
        "破增发价股",
        "国产芯片",
        "元宇宙概念"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 91.76,
      "target_price": 122.88,
      "risk_reward": 2.05,
      "support": 82.29,
      "resistance": 122.88,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 19.56,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -3.88,
      "final_score": 3.0,
      "mix_pct": 16.7,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "医药制造业",
      "concepts": [
        "肝炎概念",
        "AI制药（医疗）",
        "医美概念",
        "深圳特区",
        "互联医疗",
        "小盘成长",
        "流感",
        "新消费"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 17.99,
      "target_price": 27.7,
      "risk_reward": 3.86,
      "support": 18.85,
      "resistance": 25.27,
      "factor_actions": []
    },
    {
      "code": "688019",
      "name": "安集科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 197.3,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -9.41,
      "final_score": 2.9,
      "mix_pct": 11.1,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘股",
        "存储芯片",
        "融资融券",
        "中证500",
        "上证380",
        "股权激励",
        "光刻机(胶)",
        "LED概念"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 186.23,
      "target_price": 251.88,
      "risk_reward": 2.17,
      "support": 158.0,
      "resistance": 227.47,
      "factor_actions": []
    },
    {
      "code": "688797",
      "name": "臻宝科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 148.97,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.97,
      "final_score": 2.8,
      "mix_pct": 5.6,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-11-24",
      "stop_loss": 145.24,
      "target_price": 338.18,
      "risk_reward": 10.96,
      "support": 149.49,
      "resistance": 218.0,
      "factor_actions": []
    },
    {
      "code": "000776",
      "name": "广发证券",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 18.19,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -1.52,
      "final_score": 2.8,
      "mix_pct": 5.6,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "2026中报预增",
        "融资融券",
        "AH股",
        "证金持股",
        "深证100R",
        "金融地产风格",
        "深股通",
        "MSCI中国"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 16.79,
      "target_price": 22.39,
      "risk_reward": 2.0,
      "support": 17.58,
      "resistance": 19.55,
      "factor_actions": []
    },
    {
      "code": "603662",
      "name": "柯力传感",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 50.6,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.55,
      "final_score": 2.7,
      "mix_pct": 0.0,
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
        "小盘成长",
        "机器人执行器",
        "融资融券",
        "人形机器人",
        "物联网",
        "华为概念",
        "传感器",
        "边缘计算"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "300408",
      "name": "三环集团",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 62.41,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.31,
      "final_score": 2.7,
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
        "智能穿戴",
        "AH股",
        "科技风格",
        "机构重仓",
        "5G概念",
        "被动元件概念",
        "新材料",
        "深股通"
      ],
      "enter_date": "2026-11-24",
      "stop_loss": 58.81,
      "target_price": 139.5,
      "risk_reward": 11.35,
      "support": 61.58,
      "resistance": 89.5,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-26 00:04:28",
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
    "ima_data_date": "2026-11-24",
    "ima_pool_total": 8,
    "assessed_at": "2026-11-26 00:04:28"
  }
};