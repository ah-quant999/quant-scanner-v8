window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-26 01:37:51",
  "crisis_score": 35.6,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 26,
  "top_n": 2,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-26 00:18:47",
    "degraded": false,
    "effective": {
      "jinzuan": -0.383,
      "chan": 0.334,
      "trend": 0.537,
      "jigou": 0.617
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
      "generated": "2026-11-26 00:18:47",
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
    "date": "2026-11-25",
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
    "date": "2026-11-25",
    "source": "STOCK_QUOTE",
    "covered": 25,
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
      "code": "600999",
      "name": "招商证券",
      "market": "sh",
      "board": "主板",
      "horizon": "中长线",
      "close": 15.18,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -2.69,
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
        "因子榜": 4.4
      },
      "resonance": 1,
      "strength": 4.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.4,
      "mix_pct": 100.0,
      "buy_score": 4.4,
      "enter_date": "2026-11-25",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第1名）",
      "industry": "资本市场服务",
      "concepts": [
        "互联网金融",
        "深圳特区",
        "周期股",
        "央国企改革",
        "证金持股",
        "大盘价值",
        "AH股",
        "金融地产风格"
      ],
      "tracking": {
        "entry_date": "2026-11-25",
        "entry_price": 15.18,
        "latest_price": 15.18,
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
      "close": 16.0,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -2.62,
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
        "因子榜": 4.4
      },
      "resonance": 1,
      "strength": 4.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 4.4,
      "mix_pct": 100.0,
      "buy_score": 4.4,
      "enter_date": "2026-11-25",
      "signals": [
        "因子榜入选"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第2名）",
      "industry": "资本市场服务",
      "concepts": [
        "互联网金融",
        "周期股",
        "并购重组概念",
        "上证50",
        "权重股",
        "证金持股",
        "AH股",
        "股权激励"
      ],
      "tracking": {
        "entry_date": "2026-11-25",
        "entry_price": 16.0,
        "latest_price": 16.0,
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
      "close": 8.75,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 3.06,
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
        "因子榜": 4.3,
        "动量共识": 1.0
      },
      "resonance": 2,
      "strength": 5.3,
      "final_score": 4.3,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-11-25",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第3名）；动量共识筛选共振（无未来函数版）",
      "industry": "零售业",
      "concepts": [
        "参股券商",
        "内贸流通",
        "融资融券",
        "长江三角",
        "新零售",
        "央国企改革"
      ],
      "tracking": {
        "entry_date": "2026-11-25",
        "entry_price": 8.75,
        "latest_price": 8.75,
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
      "close": 94.4,
      "close_date": "2026-11-25",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -7.55,
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
      "enter_date": "2026-11-25",
      "signals": [
        "因子榜入选",
        "动量共识"
      ],
      "_60m_resonance": false,
      "reason": "因子积分榜入选（第19名）；动量共识筛选共振（无未来函数版）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "机器视觉",
        "虚拟现实",
        "中证500",
        "英伟达概念",
        "人工智能",
        "中盘成长",
        "3D摄像头",
        "上证380"
      ],
      "tracking": {
        "entry_date": "2026-11-25",
        "entry_price": 94.4,
        "latest_price": 94.4,
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
      "close": 82.0,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -8.59,
      "final_score": 4.4,
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
        "传感器",
        "小盘股",
        "小盘成长",
        "深股通",
        "融资融券",
        "人形机器人",
        "新能源车",
        "创业板综"
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
      "close": 15.18,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.69,
      "final_score": 4.4,
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
        "互联网金融",
        "深圳特区",
        "周期股",
        "央国企改革",
        "证金持股",
        "大盘价值",
        "AH股",
        "金融地产风格"
      ],
      "enter_date": "2026-11-25",
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
      "close": 16.0,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.62,
      "final_score": 4.4,
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
        "互联网金融",
        "周期股",
        "并购重组概念",
        "上证50",
        "权重股",
        "证金持股",
        "AH股",
        "股权激励"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 14.72,
      "target_price": 17.75,
      "risk_reward": 0.85,
      "support": 15.59,
      "resistance": 16.76,
      "factor_actions": []
    },
    {
      "code": "600838",
      "name": "上海九百",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 8.75,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": 3.06,
      "final_score": 4.3,
      "mix_pct": 94.7,
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
        "参股券商",
        "内贸流通",
        "融资融券",
        "长江三角",
        "新零售",
        "央国企改革"
      ],
      "enter_date": "2026-11-25",
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
      "close": 25.43,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.65,
      "final_score": 4.3,
      "mix_pct": 94.7,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "昨日高振幅",
        "智能穿戴",
        "网络安全",
        "深圳特区",
        "通信技术",
        "5G概念",
        "AI手机",
        "数据中心"
      ],
      "enter_date": "2026-11-25",
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
      "close": 15.65,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -6.34,
      "final_score": 4.3,
      "mix_pct": 94.7,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "低空经济",
        "无人机",
        "商业航天",
        "军工",
        "深股通",
        "航天航空",
        "大飞机",
        "融资融券"
      ],
      "enter_date": "2026-11-25",
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
      "close": 22.66,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -6.79,
      "final_score": 4.2,
      "mix_pct": 89.5,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "互联网和相关服务",
      "concepts": [
        "互联网服务",
        "DeepSeek概念",
        "商业航天",
        "VPN",
        "数据中心",
        "人工智能",
        "信创",
        "小盘股"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 22.08,
      "target_price": 32.58,
      "risk_reward": 3.28,
      "support": 22.96,
      "resistance": 31.12,
      "factor_actions": []
    },
    {
      "code": "300083",
      "name": "创世纪",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 8.76,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.91,
      "final_score": 4.2,
      "mix_pct": 89.5,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "医疗器械概念",
        "新型工业化",
        "低空经济",
        "小盘股",
        "机构重仓",
        "工业母机",
        "富时罗素",
        "深股通"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 8.15,
      "target_price": 14.39,
      "risk_reward": 5.9,
      "support": 8.48,
      "resistance": 11.67,
      "factor_actions": []
    },
    {
      "code": "600261",
      "name": "阳光照明",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.37,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -9.9,
      "final_score": 3.94,
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
        "参股券商",
        "氢能源",
        "贬值受益",
        "富时罗素",
        "标准普尔",
        "LED概念",
        "融资融券",
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
      "close": 32.2,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.29,
      "final_score": 3.8,
      "mix_pct": 68.4,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "金属制品业",
      "concepts": [
        "医疗器械概念",
        "昨日高振幅",
        "养老金",
        "新材料",
        "周期股",
        "央国企改革",
        "工业母机",
        "MSCI中国"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 31.44,
      "target_price": 69.58,
      "risk_reward": 9.92,
      "support": 32.06,
      "resistance": 43.16,
      "factor_actions": []
    },
    {
      "code": "688403",
      "name": "汇成股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 12.2,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -9.09,
      "final_score": 3.6,
      "mix_pct": 57.9,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [],
      "enter_date": "2026-11-25",
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
      "close": 46.0,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -2.79,
      "final_score": 3.5,
      "mix_pct": 52.6,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "医疗器械概念",
        "数据要素",
        "昨日高振幅",
        "智能穿戴",
        "中证500",
        "互联医疗",
        "DeepSeek概念",
        "小米概念"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 43.58,
      "target_price": 70.95,
      "risk_reward": 4.65,
      "support": 44.84,
      "resistance": 60.42,
      "factor_actions": []
    },
    {
      "code": "300539",
      "name": "横河精密",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 21.37,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.36,
      "final_score": 3.26,
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
        "创业板综",
        "股权激励",
        "无人机",
        "深股通",
        "智能家居",
        "减速器",
        "机器人概念",
        "新能源车"
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
      "close": 12.31,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.93,
      "final_score": 3.11,
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
        "无人驾驶",
        "华为概念",
        "人工智能",
        "氢能源",
        "小盘股",
        "股权激励",
        "多模态AI",
        "军工"
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 19.4,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.67,
      "final_score": 3.1,
      "mix_pct": 31.6,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "医药制造业",
      "concepts": [
        "医美概念",
        "深圳特区",
        "互联医疗",
        "华为概念",
        "创业板综",
        "AI制药（医疗）",
        "辅助生殖",
        "小盘股"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 17.99,
      "target_price": 27.7,
      "risk_reward": 3.86,
      "support": 18.85,
      "resistance": 25.27,
      "factor_actions": []
    },
    {
      "code": "688432",
      "name": "有研硅",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 26.8,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -8.84,
      "final_score": 3.0,
      "mix_pct": 26.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "沪股通",
        "小盘股",
        "存储芯片",
        "融资融券",
        "中芯概念"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 27.54,
      "target_price": 60.59,
      "risk_reward": 9.8,
      "support": 28.12,
      "resistance": 36.67,
      "factor_actions": []
    },
    {
      "code": "300007",
      "name": "汉威科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 36.94,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.53,
      "final_score": 3.0,
      "mix_pct": 26.3,
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
        "互联医疗",
        "华为概念",
        "核污染防治",
        "小米概念",
        "创业板综",
        "地下管网",
        "氢能源"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 32.49,
      "target_price": 45.37,
      "risk_reward": 2.57,
      "support": 29.12,
      "resistance": 45.37,
      "factor_actions": []
    },
    {
      "code": "688549",
      "name": "中巨芯",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 13.57,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -9.83,
      "final_score": 3.0,
      "mix_pct": 26.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "沪股通",
        "小盘股",
        "小盘成长",
        "氟化工概念",
        "高带宽内存",
        "融资融券",
        "中芯概念"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 13.71,
      "target_price": 27.5,
      "risk_reward": 8.06,
      "support": 14.07,
      "resistance": 18.88,
      "factor_actions": []
    },
    {
      "code": "002685",
      "name": "华东重机",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 8.99,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": 0.45,
      "final_score": 2.96,
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
        "半导体概念",
        "传感器",
        "氢能源",
        "富时罗素",
        "深股通",
        "2026中报预增",
        "融资融券",
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
      "code": "688797",
      "name": "臻宝科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 2.9,
      "mix_pct": 21.1,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-11-25",
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
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -12.58,
      "final_score": 2.9,
      "mix_pct": 21.1,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "专业技术服务业",
      "concepts": [
        "新型工业化",
        "数据要素",
        "DeepSeek概念",
        "无人驾驶",
        "英伟达概念",
        "人工智能",
        "华为汽车",
        "创业板综"
      ],
      "enter_date": "2026-11-25",
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
      "close": 62.22,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -5.6,
      "final_score": 2.7,
      "mix_pct": 10.5,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "被动元件概念",
        "基金重仓",
        "智能穿戴",
        "新材料",
        "华为概念",
        "通信技术",
        "5G概念",
        "周期股"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 58.81,
      "target_price": 139.5,
      "risk_reward": 11.35,
      "support": 61.58,
      "resistance": 89.5,
      "factor_actions": []
    },
    {
      "code": "688213",
      "name": "思特威",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 95.8,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.2,
      "final_score": 2.6,
      "mix_pct": 5.3,
      "resonance": 1,
      "sources": [
        "因子榜"
      ],
      "signals": [
        "因子榜入选"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "医疗器械概念",
        "机器视觉",
        "虚拟现实",
        "智能穿戴",
        "安防概念",
        "中证500",
        "无人驾驶",
        "小米概念"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 90.42,
      "target_price": 114.42,
      "risk_reward": 1.39,
      "support": 94.85,
      "resistance": 113.5,
      "factor_actions": []
    },
    {
      "code": "603662",
      "name": "柯力传感",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 50.51,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -4.72,
      "final_score": 2.5,
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
        "传感器",
        "机器视觉",
        "小盘股",
        "小盘成长",
        "沪股通",
        "华为概念",
        "物联网",
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
      "code": "688322",
      "name": "奥比中光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 94.4,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -7.55,
      "final_score": 2.5,
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
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "机器视觉",
        "虚拟现实",
        "中证500",
        "英伟达概念",
        "人工智能",
        "中盘成长",
        "3D摄像头",
        "上证380"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 91.76,
      "target_price": 122.88,
      "risk_reward": 2.05,
      "support": 82.29,
      "resistance": 122.88,
      "factor_actions": []
    },
    {
      "code": "688200",
      "name": "华峰测控",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 182.42,
      "close_date": "2026-11-25",
      "close_verified": true,
      "pct_chg": -10.28,
      "final_score": 2.5,
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
        "半导体概念",
        "昨日高振幅",
        "上证380",
        "中证500",
        "基金重仓",
        "沪股通",
        "股权激励",
        "华为概念"
      ],
      "enter_date": "2026-11-25",
      "stop_loss": 178.65,
      "target_price": 423.0,
      "risk_reward": 11.31,
      "support": 179.5,
      "resistance": 260.0,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-11-26 01:37:51",
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
    "assessed_at": "2026-11-26 01:37:51"
  }
};