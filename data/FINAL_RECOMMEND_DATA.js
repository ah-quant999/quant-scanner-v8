window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-09-30 06:58:58",
  "crisis_score": 32.9,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-30 05:42:17",
    "degraded": false,
    "effective": {
      "jinzuan": 0.99,
      "chan": 0.857,
      "trend": -1.939,
      "jigou": -1.052
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 168,
      "chan": 334,
      "trend": 248,
      "jigou": 409
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-09-30 05:42:17",
      "hit": 4,
      "n_snapshots": 75,
      "date_range": [
        "2026-06-06",
        "2026-09-30"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-09-29） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-09-29",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-09-30",
    "source": "STOCK_QUOTE",
    "covered": 20,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "厨卫电器",
    "小家电",
    "小金属",
    "房地产",
    "文化传媒",
    "汽车整车",
    "生物制品",
    "贵金属",
    "轨交设备",
    "银行",
    "风电设备"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "688498",
      "name": "源杰科技",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线/中线共振",
      "close": 1638.5,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.96,
      "stop_loss": 1474.65,
      "target_price": 1918.0,
      "risk_reward": 1.71,
      "support": 1439.03,
      "resistance": 1887.0,
      "atr": 86.33,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.42,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 3.07,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 35.4,
      "buy_score": 35.4,
      "enter_date": "2026-09-23",
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分35；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "QFII重仓",
        "基金重仓",
        "沪股通",
        "科技风格"
      ],
      "tracking": {
        "entry_date": "2026-09-23",
        "entry_price": 1638.5,
        "latest_price": 1638.5,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "good",
            "code": "688498",
            "name": "源杰科技",
            "text": "源杰科技(688498) 连续 4 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "300199",
      "name": "翰宇药业",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 22.79,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.74,
      "stop_loss": 20.51,
      "target_price": 27.7,
      "risk_reward": 2.15,
      "support": 22.06,
      "resistance": 24.44,
      "atr": 0.96,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.37,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 3.02,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 34.2,
      "buy_score": 34.2,
      "enter_date": "2026-09-22",
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分34；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "肝炎概念",
        "深圳特区",
        "AI制药（医疗）",
        "幽门螺杆菌概念",
        "融资融券",
        "减肥药",
        "新消费",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 22.79,
        "latest_price": 22.79,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "good",
            "code": "300199",
            "name": "翰宇药业",
            "text": "翰宇药业(300199) 连续 7 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 3,
      "code": "300502",
      "name": "新易盛",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 392.91,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -1.7,
      "stop_loss": 353.62,
      "target_price": 579.42,
      "risk_reward": 4.75,
      "support": 378.56,
      "resistance": 475.0,
      "atr": 21.74,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.27,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.77,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 31.7,
      "buy_score": 31.7,
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分32；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "权重股",
        "HS300",
        "融资融券",
        "大盘成长",
        "算力概念",
        "基金重仓",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 392.91,
        "latest_price": 392.91,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "300502",
            "name": "新易盛",
            "text": "新易盛(300502) 入选以来回撤 -15.8%（2026-08-17 起）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300857",
      "name": "协创数据",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 246.39,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.16,
      "stop_loss": 221.75,
      "target_price": 309.65,
      "risk_reward": 2.57,
      "support": 242.35,
      "resistance": 278.6,
      "atr": 12.05,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.72,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 30.4,
      "buy_score": 30.4,
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分30；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深圳特区",
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "算力概念",
        "深股通",
        "网络游戏"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 246.39,
        "latest_price": 246.39,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "300857",
            "name": "协创数据",
            "text": "协创数据(300857) 入选以来回撤 -8.5%（2026-08-17 起）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 5,
      "code": "002640",
      "name": "跨境通",
      "market": "sz",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 3.94,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.51,
      "stop_loss": 3.55,
      "target_price": 4.22,
      "risk_reward": 0.71,
      "support": 3.2,
      "resistance": 4.22,
      "atr": 0.23,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.09,
        "四量终极": 0.96
      },
      "resonance": 2,
      "strength": 2.05,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 27.3,
      "buy_score": 27.3,
      "enter_date": "2026-09-30",
      "signals": [
        "上涨趋势",
        "机构变红",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分27；四量终极 信号2项",
      "industry": "零售业",
      "concepts": [
        "跨境电商",
        "无线耳机",
        "标准普尔",
        "婴童概念",
        "零售业",
        "富时罗素",
        "内贸流通",
        "拼多多概念"
      ],
      "tracking": {
        "entry_date": "2026-09-30",
        "entry_price": 3.94,
        "latest_price": 3.94,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    }
  ],
  "consensus_stocks": [
    {
      "rank": 1,
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线/中线共振",
      "close": 1638.5,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.96,
      "stop_loss": 1474.65,
      "target_price": 1918.0,
      "risk_reward": 1.71,
      "support": 1439.03,
      "resistance": 1887.0,
      "atr": 86.33,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.42,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 3.07,
      "final_score": 35.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-23",
      "signals": [
        "跨策略共振",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分35；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "QFII重仓",
        "基金重仓",
        "沪股通",
        "科技风格"
      ],
      "tracking": {
        "entry_date": "2026-09-23",
        "entry_price": 1638.5,
        "latest_price": 1638.5,
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 22.79,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.74,
      "stop_loss": 20.51,
      "target_price": 27.7,
      "risk_reward": 2.15,
      "support": 22.06,
      "resistance": 24.44,
      "atr": 0.96,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.37,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 3.02,
      "final_score": 34.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-22",
      "signals": [
        "跨策略共振",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分34；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "肝炎概念",
        "深圳特区",
        "AI制药（医疗）",
        "幽门螺杆菌概念",
        "融资融券",
        "减肥药",
        "新消费",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 22.79,
        "latest_price": 22.79,
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
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 392.91,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -1.7,
      "stop_loss": 353.62,
      "target_price": 579.42,
      "risk_reward": 4.75,
      "support": 378.56,
      "resistance": 475.0,
      "atr": 21.74,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.27,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.77,
      "final_score": 31.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分32；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "权重股",
        "HS300",
        "融资融券",
        "大盘成长",
        "算力概念",
        "基金重仓",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 392.91,
        "latest_price": 392.91,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 246.39,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.16,
      "stop_loss": 221.75,
      "target_price": 309.65,
      "risk_reward": 2.57,
      "support": 242.35,
      "resistance": 278.6,
      "atr": 12.05,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.72,
      "final_score": 30.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分30；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深圳特区",
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "算力概念",
        "深股通",
        "网络游戏"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 246.39,
        "latest_price": 246.39,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 5,
      "code": "002640",
      "name": "跨境通",
      "market": "深市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 3.94,
      "close_date": "2026-09-30",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.51,
      "stop_loss": 3.55,
      "target_price": 4.22,
      "risk_reward": 0.71,
      "support": 3.2,
      "resistance": 4.22,
      "atr": 0.23,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.09,
        "四量终极": 0.96
      },
      "resonance": 2,
      "strength": 2.05,
      "final_score": 27.3,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-30",
      "signals": [
        "跨策略共振",
        "机构变红",
        "上涨趋势"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分27；四量终极 信号2项",
      "industry": "零售业",
      "concepts": [
        "跨境电商",
        "无线耳机",
        "标准普尔",
        "婴童概念",
        "零售业",
        "富时罗素",
        "内贸流通",
        "拼多多概念"
      ],
      "tracking": {
        "entry_date": "2026-09-30",
        "entry_price": 3.94,
        "latest_price": 3.94,
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
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 1638.5,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 2.96,
      "final_score": 35.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "QFII重仓",
        "基金重仓",
        "沪股通",
        "科技风格"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 1474.65,
      "target_price": 1918.0,
      "risk_reward": 1.71,
      "support": 1439.03,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 22.79,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 1.74,
      "final_score": 34.2,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "医药制造业",
      "concepts": [
        "肝炎概念",
        "深圳特区",
        "AI制药（医疗）",
        "幽门螺杆菌概念",
        "融资融券",
        "减肥药",
        "新消费",
        "深股通"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 20.51,
      "target_price": 27.7,
      "risk_reward": 2.15,
      "support": 22.06,
      "resistance": 24.44,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 392.91,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": -1.7,
      "final_score": 31.7,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "权重股",
        "HS300",
        "融资融券",
        "大盘成长",
        "算力概念",
        "基金重仓",
        "深股通"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 353.62,
      "target_price": 579.42,
      "risk_reward": 4.75,
      "support": 378.56,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 246.39,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 0.16,
      "final_score": 30.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深圳特区",
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "算力概念",
        "深股通",
        "网络游戏"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 221.75,
      "target_price": 309.65,
      "risk_reward": 2.57,
      "support": 242.35,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "002640",
      "name": "跨境通",
      "market": "深市",
      "board": "主板",
      "horizon": "中长线",
      "close": 3.94,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": -0.51,
      "final_score": 27.3,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "跨策略共振"
      ],
      "industry": "零售业",
      "concepts": [
        "跨境电商",
        "无线耳机",
        "标准普尔",
        "婴童概念",
        "零售业",
        "富时罗素",
        "内贸流通",
        "拼多多概念"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 3.55,
      "target_price": 4.22,
      "risk_reward": 0.71,
      "support": 3.2,
      "resistance": 4.22,
      "factor_actions": []
    },
    {
      "code": "002916",
      "name": "深南电路",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 375.6,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 1.25,
      "final_score": 26.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "深圳特区",
        "HS300",
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "国产芯片",
        "央国企改革"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 338.04,
      "target_price": 459.8,
      "risk_reward": 2.24,
      "support": 328.21,
      "resistance": 424.04,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 255.99,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 4.57,
      "final_score": 25.5,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "HS300",
        "融资融券",
        "大盘成长",
        "QFII重仓",
        "算力概念",
        "专精特新",
        "深股通"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 230.39,
      "target_price": 294.5,
      "risk_reward": 1.5,
      "support": 237.3,
      "resistance": 292.07,
      "factor_actions": []
    },
    {
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 49.05,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 2.19,
      "final_score": 25.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "独角兽",
        "中盘价值",
        "反内卷概念",
        "融资融券",
        "锂电池概念",
        "储能概念",
        "先进制造风格",
        "深股通"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 44.14,
      "target_price": 96.51,
      "risk_reward": 9.68,
      "support": 47.86,
      "resistance": 65.0,
      "factor_actions": []
    },
    {
      "code": "000703",
      "name": "恒逸石化",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.69,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": -9.1,
      "final_score": 24.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "化学纤维制造业",
      "concepts": [
        "西部大开发",
        "2026中报预增",
        "中盘股",
        "标准普尔",
        "转债标的",
        "中盘价值",
        "一带一路",
        "富时罗素"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 14.12,
      "target_price": 20.13,
      "risk_reward": 2.83,
      "support": 15.53,
      "resistance": 19.37,
      "factor_actions": []
    },
    {
      "code": "300033",
      "name": "同花顺",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 199.71,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 0.84,
      "final_score": 24.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "其他金融业",
      "concepts": [
        "区块链",
        "国产软件",
        "HS300",
        "互联网金融",
        "大盘成长",
        "券商概念",
        "融资融券",
        "长江三角"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 179.74,
      "target_price": 245.48,
      "risk_reward": 2.29,
      "support": 197.97,
      "resistance": 233.65,
      "factor_actions": []
    },
    {
      "code": "688808",
      "name": "联讯仪",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1496.0,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 1.8,
      "final_score": 23.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 1346.4,
      "target_price": 1846.62,
      "risk_reward": 2.34,
      "support": 1435.81,
      "resistance": 1846.62,
      "factor_actions": []
    },
    {
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 218.03,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 2.36,
      "final_score": 23.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "铜缆高速连接",
        "融资融券",
        "国产芯片",
        "专精特新",
        "基金重仓",
        "深股通",
        "F5G概念"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 196.23,
      "target_price": 247.8,
      "risk_reward": 1.37,
      "support": 191.87,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "000737",
      "name": "北方铜业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 13.43,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 2.91,
      "final_score": 21.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "2026中报预增",
        "中盘股",
        "小金属概念",
        "新材料",
        "PCB",
        "中盘成长",
        "黄金概念",
        "昨日高振幅"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 12.09,
      "target_price": 17.2,
      "risk_reward": 2.81,
      "support": 13.05,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 65.93,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": -1.11,
      "final_score": 21.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深圳特区",
        "特斯拉概念",
        "融资融券",
        "锂电池概念",
        "先进制造风格",
        "新能源车",
        "深股通",
        "氟化工概念"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 59.34,
      "target_price": 87.39,
      "risk_reward": 3.25,
      "support": 61.88,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 171.21,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 1.74,
      "final_score": 21.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "5G概念",
        "HS300",
        "昨日高振幅",
        "特斯拉概念",
        "融资融券",
        "长江三角",
        "基金重仓",
        "PCB"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 154.09,
      "target_price": 280.08,
      "risk_reward": 6.36,
      "support": 167.84,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 37.0,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": -3.34,
      "final_score": 21.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "5G概念",
        "昨日高振幅",
        "融资融券",
        "国产芯片",
        "长江三角",
        "QFII重仓",
        "网络安全",
        "专精特新"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 33.3,
      "target_price": 53.33,
      "risk_reward": 4.41,
      "support": 36.18,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "002074",
      "name": "国轩高科",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 28.68,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 10.01,
      "final_score": 21.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "充电桩",
        "HS300",
        "大盘成长",
        "融资融券",
        "锂电池概念",
        "长江三角",
        "储能概念",
        "先进制造风格"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 25.81,
      "target_price": 29.09,
      "risk_reward": 0.14,
      "support": 24.67,
      "resistance": 28.68,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 13.72,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 6.61,
      "final_score": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "2026中报预增",
        "中盘股",
        "5G概念",
        "沪股通",
        "光通信模块",
        "PCB",
        "中盘成长",
        "昨日高振幅"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 12.35,
      "target_price": 15.85,
      "risk_reward": 1.55,
      "support": 11.9,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "688183",
      "name": "生益电子",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 110.5,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 4.29,
      "final_score": 20.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "2026中报预增",
        "沪股通",
        "大盘股",
        "百元股",
        "HS300",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "大盘成长"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 99.45,
      "target_price": 138.47,
      "risk_reward": 2.53,
      "support": 105.0,
      "resistance": 133.8,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 407.95,
      "close_date": "2026-09-30",
      "close_verified": true,
      "pct_chg": 3.48,
      "final_score": 19.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "超清视频",
        "5G概念",
        "昨日高振幅",
        "大盘成长",
        "融资融券",
        "沪股通",
        "富时罗素",
        "科技风格"
      ],
      "enter_date": "2026-09-30",
      "stop_loss": 367.15,
      "target_price": 483.8,
      "risk_reward": 1.86,
      "support": 374.5,
      "resistance": 483.8,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-09-30 06:58:58",
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