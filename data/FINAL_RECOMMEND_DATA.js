window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-26 18:58:07",
  "crisis_score": 36.1,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 26,
  "top_n": 2,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-26 17:52:08",
    "degraded": false,
    "effective": {
      "jinzuan": -0.398,
      "chan": 0.328,
      "trend": 0.522,
      "jigou": 0.613
    },
    "hardcoded_default": {
      "jinzuan": -0.522,
      "chan": 0.155,
      "trend": 0.339,
      "jigou": 0.449
    },
    "n_on10": {
      "jinzuan": 589,
      "chan": 800,
      "trend": 277,
      "jigou": 524
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-11-26 17:52:08",
      "hit": 4,
      "n_snapshots": 117,
      "date_range": [
        "2026-06-06",
        "2026-11-25"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-11-26",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "index_trend_gate": {
    "triggered": true,
    "close": 3476.47,
    "ma20": 3613.37,
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
    "date": "2026-11-26",
    "source": "STOCK_QUOTE",
    "covered": 26,
    "total": 26,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "中药",
    "保险",
    "元件",
    "养殖业",
    "农产品加工",
    "小金属",
    "机场航运",
    "港口航运",
    "证券",
    "贵金属",
    "银行",
    "食品加工制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "600838",
      "name": "上海九百",
      "market": "sh",
      "board": "主板",
      "horizon": "中长线",
      "close": 8.83,
      "close_date": "2026-11-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.91,
      "limit_up": false,
      "limit_up_note": null,
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
        "因子榜": 4.2,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 5.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.2,
      "mix_pct": 100.0,
      "buy_score": 4.2,
      "enter_date": "2026-11-26",
      "signals": [
        "动量共识",
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）；动量共识筛选共振（无未来函数版）",
      "industry": "零售业",
      "concepts": [
        "融资融券",
        "参股券商",
        "新零售",
        "内贸流通",
        "长江三角",
        "央国企改革"
      ],
      "tracking": {
        "entry_date": "2026-11-26",
        "entry_price": 8.83,
        "latest_price": 8.83,
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
      "code": "000063",
      "name": "中兴通讯",
      "market": "sz",
      "board": "主板",
      "horizon": "中长线",
      "close": 25.66,
      "close_date": "2026-11-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.9,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 23.98,
      "target_price": 34.89,
      "risk_reward": 3.1,
      "support": 25.62,
      "resistance": 29.12,
      "atr": 0.81,
      "sources": [
        "因子榜"
      ],
      "source_scores": {
        "因子榜": 4.2
      },
      "resonance": 1,
      "strength": 4.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.2,
      "mix_pct": 100.0,
      "buy_score": 4.2,
      "enter_date": "2026-11-26",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第2名）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "云计算",
        "昨日炸板",
        "消费电子概念",
        "网络安全",
        "深圳特区",
        "无线充电",
        "5G概念"
      ],
      "tracking": {
        "entry_date": "2026-11-26",
        "entry_price": 25.66,
        "latest_price": 25.66,
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
      "close": 8.83,
      "close_date": "2026-11-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.91,
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
        "因子榜": 4.2,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 5.2,
      "final_score": 4.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-26",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）；动量共识筛选共振（无未来函数版）",
      "industry": "零售业",
      "concepts": [
        "融资融券",
        "参股券商",
        "新零售",
        "内贸流通",
        "长江三角",
        "央国企改革"
      ],
      "tracking": {
        "entry_date": "2026-11-26",
        "entry_price": 8.83,
        "latest_price": 8.83,
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
      "close": 90.05,
      "close_date": "2026-11-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.61,
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
        "因子榜": 2.5,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 3.5,
      "final_score": 2.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-26",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第16名）；动量共识筛选共振（无未来函数版）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "虚拟现实",
        "中盘成长",
        "国产芯片",
        "上证380",
        "2025三季报扭亏",
        "生物识别",
        "人形机器人"
      ],
      "tracking": {
        "entry_date": "2026-11-26",
        "entry_price": 90.05,
        "latest_price": 90.05,
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
      "close": 80.26,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -2.12,
      "final_score": 4.2,
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
        "人形机器人",
        "融资融券",
        "传感器",
        "新能源车",
        "专精特新",
        "创业板综",
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
      "code": "600838",
      "name": "上海九百",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 8.83,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.91,
      "final_score": 4.2,
      "mix_pct": 100.0,
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
        "参股券商",
        "新零售",
        "内贸流通",
        "长江三角",
        "央国企改革"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 7.51,
      "target_price": 14.89,
      "risk_reward": 7.85,
      "support": 7.38,
      "resistance": 14.89,
      "factor_actions": []
    },
    {
      "code": "000063",
      "name": "中兴通讯",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 25.66,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.9,
      "final_score": 4.2,
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
        "融资融券",
        "云计算",
        "昨日炸板",
        "消费电子概念",
        "网络安全",
        "深圳特区",
        "无线充电",
        "5G概念"
      ],
      "enter_date": "2026-11-26",
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
      "close": 15.36,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -1.85,
      "final_score": 4.2,
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
        "人形机器人",
        "融资融券",
        "低空经济",
        "无人机",
        "军工",
        "飞行汽车(eVTOL)",
        "专精特新",
        "创业板综"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 14.8,
      "target_price": 24.86,
      "risk_reward": 5.11,
      "support": 15.08,
      "resistance": 23.83,
      "factor_actions": []
    },
    {
      "code": "688158",
      "name": "优刻得",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 22.74,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.35,
      "final_score": 4.1,
      "mix_pct": 95.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "互联网和相关服务",
      "concepts": [
        "融资融券",
        "云计算",
        "信创",
        "智慧城市",
        "小盘成长",
        "DeepSeek概念",
        "算力概念",
        "智谱AI概念"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 22.08,
      "target_price": 32.58,
      "risk_reward": 3.28,
      "support": 22.96,
      "resistance": 31.12,
      "factor_actions": []
    },
    {
      "code": "000657",
      "name": "中钨高新",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 33.07,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 2.7,
      "final_score": 3.8,
      "mix_pct": 80.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "金属制品业",
      "concepts": [
        "养老金",
        "融资融券",
        "PCB",
        "创投",
        "富时罗素",
        "新材料",
        "HS300",
        "2026一季报预增"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 31.44,
      "target_price": 69.58,
      "risk_reward": 9.92,
      "support": 32.06,
      "resistance": 43.16,
      "factor_actions": []
    },
    {
      "code": "600261",
      "name": "阳光照明",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.03,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -7.78,
      "final_score": 3.72,
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
        "融资融券",
        "富时罗素",
        "破增发价股",
        "参股券商",
        "低价股",
        "证金持股",
        "节能环保",
        "贬值受益"
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
      "code": "688403",
      "name": "汇成股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 12.24,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.33,
      "final_score": 3.6,
      "mix_pct": 70.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [],
      "enter_date": "2026-11-26",
      "stop_loss": 11.89,
      "target_price": 27.46,
      "risk_reward": 10.79,
      "support": 12.08,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "002432",
      "name": "九安医疗",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 45.5,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -1.09,
      "final_score": 3.5,
      "mix_pct": 65.0,
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
        "消费电子概念",
        "互联医疗",
        "新能源车",
        "医药医疗风格",
        "流感",
        "DeepSeek概念",
        "创投"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 43.58,
      "target_price": 70.95,
      "risk_reward": 4.65,
      "support": 44.84,
      "resistance": 60.42,
      "factor_actions": []
    },
    {
      "code": "300083",
      "name": "创世纪",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 8.73,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -0.34,
      "final_score": 3.4,
      "mix_pct": 60.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "新型工业化",
        "人形机器人",
        "融资融券",
        "低空经济",
        "富时罗素",
        "医疗器械概念",
        "飞行汽车(eVTOL)",
        "5G概念"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 8.15,
      "target_price": 14.39,
      "risk_reward": 5.9,
      "support": 8.48,
      "resistance": 11.67,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 18.48,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -4.74,
      "final_score": 3.1,
      "mix_pct": 45.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "医药制造业",
      "concepts": [
        "融资融券",
        "互联医疗",
        "深圳特区",
        "肝炎概念",
        "医药医疗风格",
        "流感",
        "小盘成长",
        "病原体防治"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 17.99,
      "target_price": 27.7,
      "risk_reward": 3.86,
      "support": 18.85,
      "resistance": 25.27,
      "factor_actions": []
    },
    {
      "code": "300539",
      "name": "横河精密",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 22.79,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 6.64,
      "final_score": 3.0,
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
        "智能家居",
        "新能源车",
        "专精特新",
        "创业板综"
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
      "code": "688432",
      "name": "有研硅",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 26.35,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -1.68,
      "final_score": 3.0,
      "mix_pct": 40.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "存储芯片",
        "半导体概念",
        "沪股通",
        "小盘股",
        "中芯概念"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 27.54,
      "target_price": 60.59,
      "risk_reward": 9.8,
      "support": 28.12,
      "resistance": 36.67,
      "factor_actions": []
    },
    {
      "code": "688549",
      "name": "中巨芯",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 13.78,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 1.55,
      "final_score": 3.0,
      "mix_pct": 40.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "小盘成长",
        "氟化工概念",
        "融资融券",
        "高带宽内存",
        "半导体概念",
        "沪股通",
        "光刻机(胶)",
        "小盘股"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 13.71,
      "target_price": 27.5,
      "risk_reward": 8.06,
      "support": 14.07,
      "resistance": 18.88,
      "factor_actions": []
    },
    {
      "code": "002611",
      "name": "东方精工",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.03,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -2.27,
      "final_score": 2.84,
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
        "融资融券",
        "无人机",
        "标准普尔",
        "无人驾驶",
        "工业互联",
        "人形机器人",
        "富时罗素",
        "机器人概念"
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
      "code": "688797",
      "name": "臻宝科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 143.71,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -2.31,
      "final_score": 2.8,
      "mix_pct": 30.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-11-26",
      "stop_loss": 145.24,
      "target_price": 338.18,
      "risk_reward": 10.96,
      "support": 149.49,
      "resistance": 218.0,
      "factor_actions": []
    },
    {
      "code": "300825",
      "name": "阿尔特",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 10.7,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 2.8,
      "mix_pct": 30.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专业技术服务业",
      "concepts": [
        "减速器",
        "新型工业化",
        "华为汽车",
        "融资融券",
        "车联网(车路云)",
        "汽车热管理",
        "新能源车",
        "无人驾驶"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 9.64,
      "target_price": 15.91,
      "risk_reward": 4.86,
      "support": 9.62,
      "resistance": 15.91,
      "factor_actions": []
    },
    {
      "code": "300408",
      "name": "三环集团",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 64.17,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 3.13,
      "final_score": 2.7,
      "mix_pct": 25.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "基金重仓",
        "5G概念",
        "科技风格",
        "AH股",
        "光纤概念",
        "电池技术",
        "富时罗素"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 58.81,
      "target_price": 139.5,
      "risk_reward": 11.35,
      "support": 61.58,
      "resistance": 89.5,
      "factor_actions": []
    },
    {
      "code": "002685",
      "name": "华东重机",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 8.09,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -10.01,
      "final_score": 2.68,
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
        "融资融券",
        "富时罗素",
        "2026中报预增",
        "传感器",
        "半导体概念",
        "国产芯片",
        "专精特新",
        "TOPCon电池"
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
      "code": "688213",
      "name": "思特威",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 87.5,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -8.66,
      "final_score": 2.6,
      "mix_pct": 20.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "融资融券",
        "无人机",
        "安防概念",
        "虚拟现实",
        "消费电子概念",
        "中盘成长",
        "国产芯片",
        "上证380"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 90.42,
      "target_price": 114.42,
      "risk_reward": 1.39,
      "support": 94.85,
      "resistance": 113.5,
      "factor_actions": []
    },
    {
      "code": "688322",
      "name": "奥比中光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 90.05,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -4.61,
      "final_score": 2.5,
      "mix_pct": 15.0,
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
        "融资融券",
        "虚拟现实",
        "中盘成长",
        "国产芯片",
        "上证380",
        "2025三季报扭亏",
        "生物识别",
        "人形机器人"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 91.76,
      "target_price": 122.88,
      "risk_reward": 2.05,
      "support": 82.29,
      "resistance": 122.88,
      "factor_actions": []
    },
    {
      "code": "002270",
      "name": "华明装备",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 18.04,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 0.56,
      "final_score": 2.5,
      "mix_pct": 15.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "特高压",
        "融资融券",
        "电网概念",
        "新能源",
        "深成500",
        "小盘股",
        "小盘价值",
        "工业母机"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 16.63,
      "target_price": 20.93,
      "risk_reward": 1.33,
      "support": 17.45,
      "resistance": 20.93,
      "factor_actions": []
    },
    {
      "code": "002415",
      "name": "海康威视",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 33.19,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -2.98,
      "final_score": 2.4,
      "mix_pct": 10.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "新型工业化",
        "融资融券",
        "云计算",
        "车联网(车路云)",
        "无人机",
        "安防概念",
        "虚拟现实",
        "趋势股"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 31.63,
      "target_price": 36.18,
      "risk_reward": 0.29,
      "support": 33.73,
      "resistance": 35.8,
      "factor_actions": []
    },
    {
      "code": "000951",
      "name": "中国重汽",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 19.66,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": 1.5,
      "final_score": 2.3,
      "mix_pct": 5.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "汽车制造业",
      "concepts": [
        "中字头",
        "融资融券",
        "小盘价值",
        "富时罗素",
        "深股通",
        "新能源车",
        "汽车整车",
        "深成500"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 17.63,
      "target_price": 22.93,
      "risk_reward": 1.7,
      "support": 18.02,
      "resistance": 20.94,
      "factor_actions": []
    },
    {
      "code": "603662",
      "name": "柯力传感",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 49.39,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -2.22,
      "final_score": 2.2,
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
        "人形机器人",
        "融资融券",
        "机器视觉",
        "传感器",
        "物联网",
        "人工智能",
        "大数据"
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
      "code": "300014",
      "name": "亿纬锂能",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 42.14,
      "close_date": "2026-11-26",
      "close_verified": true,
      "pct_chg": -0.54,
      "final_score": 2.2,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "融资融券",
        "固态电池",
        "安防概念",
        "消费电子概念",
        "新能源车",
        "锂电池概念",
        "富时罗素",
        "电池技术"
      ],
      "enter_date": "2026-11-26",
      "stop_loss": 39.97,
      "target_price": 56.72,
      "risk_reward": 2.77,
      "support": 43.03,
      "resistance": 54.5,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-26 18:58:07",
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
  "factor_trace": [],
  "validity": {
    "status": "ok",
    "reason": "候选源正常",
    "ima_data_date": "2026-11-24",
    "ima_pool_total": 8,
    "assessed_at": "2026-11-26 18:58:07"
  }
};