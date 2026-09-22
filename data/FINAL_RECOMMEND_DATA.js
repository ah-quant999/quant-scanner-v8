window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-09-22 20:34:56",
  "crisis_score": 32.1,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-22 19:23:58",
    "degraded": false,
    "effective": {
      "jinzuan": 1.092,
      "chan": 0.921,
      "trend": -1.817,
      "jigou": -0.918
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 147,
      "chan": 298,
      "trend": 248,
      "jigou": 404
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-09-22 19:23:58",
      "hit": 4,
      "n_snapshots": 68,
      "date_range": [
        "2026-06-06",
        "2026-09-22"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-09-22",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-09-22",
    "source": "STOCK_QUOTE",
    "covered": 20,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "互联网电商",
    "光学光电子",
    "其他电子",
    "医疗服务",
    "半导体",
    "塑料制品",
    "小金属",
    "生物制品",
    "电子化学品",
    "贵金属",
    "通信设备",
    "风电设备"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "301308",
      "name": "江波龙",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 348.27,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.14,
      "stop_loss": 328.5,
      "target_price": 386.37,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.41,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.64,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 3.14,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "final_score": 37.3,
      "buy_score": 37.3,
      "enter_date": "2026-09-15",
      "signals": [
        "机构变红",
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分41；四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "深股通",
        "深证100R",
        "国产芯片",
        "融资融券",
        "信创",
        "计算机、通信和其他电子设备制造业",
        "HS300"
      ],
      "tracking": {
        "entry_date": "2026-09-15",
        "entry_price": 348.27,
        "latest_price": 348.27,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "good",
            "code": "301308",
            "name": "江波龙",
            "text": "江波龙(301308) 连续 8 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "601168",
      "name": "西部矿业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 36.77,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.49,
      "stop_loss": 32.97,
      "target_price": 41.15,
      "risk_reward": 2.3,
      "support": 34.67,
      "resistance": 41.97,
      "atr": 1.54,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.46,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.96,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "贵金属",
          "pct_5d": -2.34,
          "relative_5d": -2.34,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": 3.94,
          "relative_5d": 3.94,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "贵金属",
          "pct_5d": -2.34,
          "relative_5d": -2.34,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": 3.94,
          "relative_5d": 3.94,
          "strong": true
        }
      ],
      "final_score": 33.5,
      "buy_score": 33.5,
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分37；四量终极 信号0项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "新材料",
        "昨日高振幅",
        "融资融券",
        "题材股",
        "有色金属矿采选业",
        "锂矿概念",
        "电池技术",
        "央国企改革"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 36.77,
        "latest_price": 36.77,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "601168",
            "name": "西部矿业",
            "text": "西部矿业(601168) 入选以来回撤 -16.5%（2026-08-17 起）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 3,
      "code": "300857",
      "name": "协创数据",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 273.35,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.09,
      "stop_loss": 266.98,
      "target_price": 285.34,
      "risk_reward": 2.0,
      "support": 232.0,
      "resistance": 278.6,
      "atr": 12.82,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.39,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.89,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "final_score": 31.1,
      "buy_score": 31.1,
      "enter_date": "2026-08-17",
      "signals": [
        "机构变红",
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分35；四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "通信技术",
        "深股通",
        "国产芯片",
        "昨日高振幅",
        "融资融券",
        "算力概念",
        "中证500"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 273.35,
        "latest_price": 273.35,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 4,
      "code": "300199",
      "name": "翰宇药业",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.85,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.1,
      "stop_loss": 23.43,
      "target_price": 23.91,
      "risk_reward": 2.0,
      "support": 22.26,
      "resistance": 24.19,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.29,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.62,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 30.4,
      "buy_score": 30.4,
      "enter_date": "2026-09-22",
      "signals": [
        "机构变红",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分32；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "深股通",
        "AI制药（医疗）",
        "互联医疗",
        "融资融券",
        "华为概念",
        "辅助生殖",
        "2026中报预增",
        "新消费"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 23.85,
        "latest_price": 23.85,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 5,
      "code": "605117",
      "name": "德业股份",
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 82.38,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.5,
      "stop_loss": 74.14,
      "target_price": 104.56,
      "risk_reward": 2.69,
      "support": 80.84,
      "resistance": 98.32,
      "atr": 2.5,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.1,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.6,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 29.4,
      "buy_score": 29.4,
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分28；四量终极 信号0项；基本面因子 高ROE 排名第9",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "上证180",
        "2026一季报预增",
        "2026中报预增",
        "电气机械和器材制造业",
        "大盘成长",
        "国产芯片",
        "先进制造风格",
        "周期股"
      ],
      "tracking": {
        "entry_date": "2026-09-12",
        "entry_price": 82.38,
        "latest_price": 82.38,
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
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 348.27,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.14,
      "stop_loss": 328.5,
      "target_price": 386.37,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.41,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.64,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 3.14,
      "final_score": 37.3,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "enter_date": "2026-09-15",
      "signals": [
        "跨策略共振",
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分41；四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "深股通",
        "深证100R",
        "国产芯片",
        "融资融券",
        "信创",
        "计算机、通信和其他电子设备制造业",
        "HS300"
      ],
      "tracking": {
        "entry_date": "2026-09-15",
        "entry_price": 348.27,
        "latest_price": 348.27,
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
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 36.77,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.49,
      "stop_loss": 32.97,
      "target_price": 41.15,
      "risk_reward": 2.3,
      "support": 34.67,
      "resistance": 41.97,
      "atr": 1.54,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.46,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.96,
      "final_score": 33.5,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "贵金属",
          "pct_5d": -2.34,
          "relative_5d": -2.34,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": 3.94,
          "relative_5d": 3.94,
          "strong": true
        }
      ],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分37；四量终极 信号0项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "新材料",
        "昨日高振幅",
        "融资融券",
        "题材股",
        "有色金属矿采选业",
        "锂矿概念",
        "电池技术",
        "央国企改革"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 36.77,
        "latest_price": 36.77,
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
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 273.35,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.09,
      "stop_loss": 266.98,
      "target_price": 285.34,
      "risk_reward": 2.0,
      "support": 232.0,
      "resistance": 278.6,
      "atr": 12.82,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.39,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.89,
      "final_score": 31.1,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.73,
          "relative_5d": 10.73,
          "strong": true
        }
      ],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振",
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分35；四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "通信技术",
        "深股通",
        "国产芯片",
        "昨日高振幅",
        "融资融券",
        "算力概念",
        "中证500"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 273.35,
        "latest_price": 273.35,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 4,
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.85,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.1,
      "stop_loss": 23.43,
      "target_price": 23.91,
      "risk_reward": 2.0,
      "support": 22.26,
      "resistance": 24.19,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.29,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.62,
      "final_score": 30.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-22",
      "signals": [
        "跨策略共振",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分32；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "深股通",
        "AI制药（医疗）",
        "互联医疗",
        "融资融券",
        "华为概念",
        "辅助生殖",
        "2026中报预增",
        "新消费"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 23.85,
        "latest_price": 23.85,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 5,
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 82.38,
      "close_date": "2026-09-22",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.5,
      "stop_loss": 74.14,
      "target_price": 104.56,
      "risk_reward": 2.69,
      "support": 80.84,
      "resistance": 98.32,
      "atr": 2.5,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.1,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.6,
      "final_score": 29.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分28；四量终极 信号0项；基本面因子 高ROE 排名第9",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "上证180",
        "2026一季报预增",
        "2026中报预增",
        "电气机械和器材制造业",
        "大盘成长",
        "国产芯片",
        "先进制造风格",
        "周期股"
      ],
      "tracking": {
        "entry_date": "2026-09-12",
        "entry_price": 82.38,
        "latest_price": 82.38,
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
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 348.27,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.14,
      "final_score": 37.3,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "深股通",
        "深证100R",
        "国产芯片",
        "融资融券",
        "信创",
        "计算机、通信和其他电子设备制造业",
        "HS300"
      ],
      "enter_date": "2026-09-15",
      "stop_loss": 328.5,
      "target_price": 386.37,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88,
      "factor_actions": []
    },
    {
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 36.77,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 1.49,
      "final_score": 33.5,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "新材料",
        "昨日高振幅",
        "融资融券",
        "题材股",
        "有色金属矿采选业",
        "锂矿概念",
        "电池技术",
        "央国企改革"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 32.97,
      "target_price": 41.15,
      "risk_reward": 2.3,
      "support": 34.67,
      "resistance": 41.97,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 273.35,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.09,
      "final_score": 31.1,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "通信技术",
        "深股通",
        "国产芯片",
        "昨日高振幅",
        "融资融券",
        "算力概念",
        "中证500"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 266.98,
      "target_price": 285.34,
      "risk_reward": 2.0,
      "support": 232.0,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 23.85,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 1.1,
      "final_score": 30.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "跨策略共振"
      ],
      "industry": "医药制造业",
      "concepts": [
        "深股通",
        "AI制药（医疗）",
        "互联医疗",
        "融资融券",
        "华为概念",
        "辅助生殖",
        "2026中报预增",
        "新消费"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 23.43,
      "target_price": 23.91,
      "risk_reward": 2.0,
      "support": 22.26,
      "resistance": 24.19,
      "factor_actions": []
    },
    {
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 82.38,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.5,
      "final_score": 29.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振",
        "高ROE"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "上证180",
        "2026一季报预增",
        "2026中报预增",
        "电气机械和器材制造业",
        "大盘成长",
        "国产芯片",
        "先进制造风格",
        "周期股"
      ],
      "enter_date": "2026-09-12",
      "stop_loss": 74.14,
      "target_price": 104.56,
      "risk_reward": 2.69,
      "support": 80.84,
      "resistance": 98.32,
      "factor_actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第9／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ]
    },
    {
      "code": "688808",
      "name": "联讯仪器",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 2316.0,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -0.99,
      "final_score": 28.6,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "enter_date": "2026-09-07",
      "stop_loss": 2307.8,
      "target_price": 2471.0,
      "risk_reward": 4.21,
      "support": 2123.0,
      "resistance": 2733.0,
      "factor_actions": []
    },
    {
      "code": "603993",
      "name": "洛阳钼业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.81,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 1.25,
      "final_score": 28.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "高ROE"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "昨日高振幅",
        "融资融券",
        "AH股",
        "有色金属矿采选业",
        "HS300",
        "权重股",
        "2026中报预增",
        "黄金概念"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 17.51,
      "target_price": 17.75,
      "risk_reward": 2.0,
      "support": 17.26,
      "resistance": 19.89,
      "factor_actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第21／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ]
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 455.0,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -0.38,
      "final_score": 26.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "通信技术",
        "深股通",
        "深证100R",
        "融资融券",
        "算力概念",
        "CPO概念",
        "计算机、通信和其他电子设备制造业",
        "基金重仓"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 411.06,
      "target_price": 548.08,
      "risk_reward": 2.0,
      "support": 378.56,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "603268",
      "name": "松发股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 219.0,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -1.15,
      "final_score": 26.7,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "缠论买点",
        "跨策略共振",
        "高ROE"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "大盘成长",
        "2026中报预增",
        "机构重仓",
        "先进制造风格",
        "QFII重仓",
        "融资融券",
        "铁路、船舶、航空航天和其他运输设备制造业",
        "沪股通"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 208.0,
      "target_price": 248.65,
      "risk_reward": 2.0,
      "support": 181.0,
      "resistance": 228.0,
      "factor_actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第3／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ]
    },
    {
      "code": "000737",
      "name": "北方铜业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.11,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 4.71,
      "final_score": 26.1,
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
        "央国企改革",
        "2026中报预增",
        "稀缺资源",
        "新材料",
        "深股通",
        "黄金概念",
        "昨日高振幅",
        "融资融券"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 15.71,
      "target_price": 17.99,
      "risk_reward": 2.0,
      "support": 13.72,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 54.23,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.07,
      "final_score": 26.1,
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
        "半导体概念",
        "深股通",
        "中盘价值",
        "融资融券",
        "储能概念",
        "新能源车",
        "华为概念",
        "中证500"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 52.3,
      "target_price": 58.0,
      "risk_reward": 2.0,
      "support": 50.58,
      "resistance": 65.94,
      "factor_actions": []
    },
    {
      "code": "000807",
      "name": "云铝股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.95,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.67,
      "final_score": 23.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "高ROE"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "深股通",
        "深证100R",
        "融资融券",
        "新能源车",
        "HS300",
        "电池技术",
        "央国企改革",
        "2026中报预增"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 27.49,
      "target_price": 32.11,
      "risk_reward": 2.0,
      "support": 26.11,
      "resistance": 29.13,
      "factor_actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第23／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ]
    },
    {
      "code": "688257",
      "name": "新锐股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 58.42,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -1.93,
      "final_score": 22.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "2026一季报预增",
        "2026中报预增",
        "小盘股",
        "新材料",
        "专精特新",
        "融资融券",
        "沪股通",
        "有色金属冶炼和压延加工业"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 53.61,
      "target_price": 71.48,
      "risk_reward": 2.0,
      "support": 48.98,
      "resistance": 60.89,
      "factor_actions": []
    },
    {
      "code": "000703",
      "name": "恒逸石化",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 16.81,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -0.83,
      "final_score": 21.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "化学纤维制造业",
      "concepts": [
        "2026中报预增",
        "机构重仓",
        "一带一路",
        "富时罗素",
        "中盘价值",
        "新材料",
        "深股通",
        "昨日高振幅"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 17.57,
      "target_price": 21.53,
      "risk_reward": 2.0,
      "support": 15.88,
      "resistance": 19.37,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 198.12,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 1.59,
      "final_score": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "60min多周期共振",
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "通信技术",
        "深股通",
        "深证100R",
        "昨日高振幅",
        "融资融券",
        "新能源车",
        "华为概念",
        "计算机、通信和其他电子设备制造业"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 182.82,
      "target_price": 219.42,
      "risk_reward": 2.0,
      "support": 176.75,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "000630",
      "name": "铜陵有色",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 6.16,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 1.15,
      "final_score": 20.5,
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
        "通信技术",
        "新材料",
        "深证100R",
        "深股通",
        "融资融券",
        "HS300",
        "电池技术",
        "央国企改革"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 6.11,
      "target_price": 7.49,
      "risk_reward": 2.0,
      "support": 5.98,
      "resistance": 6.9,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1753.1,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -4.65,
      "final_score": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "通信技术",
        "国产芯片",
        "昨日高振幅",
        "融资融券",
        "中证500",
        "计算机、通信和其他电子设备制造业",
        "基金重仓"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 1685.15,
      "target_price": 2145.38,
      "risk_reward": 2.0,
      "support": 1440.03,
      "resistance": 1888.0,
      "factor_actions": []
    },
    {
      "code": "688525",
      "name": "佰维存储",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 217.22,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": -0.17,
      "final_score": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "国产芯片",
        "融资融券",
        "信创",
        "股权激励",
        "计算机、通信和其他电子设备制造业",
        "消费电子概念",
        "基金重仓"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 216.88,
      "target_price": 218.98,
      "risk_reward": 2.0,
      "support": 204.58,
      "resistance": 238.22,
      "factor_actions": []
    },
    {
      "code": "688400",
      "name": "凌云光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 46.94,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 0.02,
      "final_score": 19.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [],
      "enter_date": "2026-09-22",
      "stop_loss": 42.44,
      "target_price": 56.58,
      "risk_reward": 2.0,
      "support": 42.44,
      "resistance": 49.4,
      "factor_actions": []
    },
    {
      "code": "002074",
      "name": "国轩高科",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 27.73,
      "close_date": "2026-09-22",
      "close_verified": true,
      "pct_chg": 3.98,
      "final_score": 19.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缩量强势"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "深股通",
        "动力电池回收",
        "融资融券",
        "储能概念",
        "新能源车",
        "华为概念",
        "新能源",
        "智能电网"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 24.96,
      "target_price": 29.09,
      "risk_reward": 0.49,
      "support": 24.67,
      "resistance": 28.64,
      "factor_actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第7／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ]
    }
  ],
  "factor_chain": {
    "update_time": "2026-09-22 20:34:56",
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
        "n_hit": 1,
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
        "n_hit": 4,
        "evidence": "薄样本(9 信号日 / 89 命中)",
        "why": "实测边际 +0.68pp（弱正，命中 89 条 ≈ 43.9% 覆盖率，无选择性）⇒ 不足与强源同权"
      }
    ],
    "evidence_note": "计分依据分级：①「未回测」= 无任何样本外证据（放量弱势）；②「薄样本」= 9 信号日实测边际，样本不足以定权重，故不计分（异常换手率/ROE_TTM/高手跟踪）；③「walk-forward」= ≥4/5 年 OOS 检验通过才给分（候选池层 P5 的 amt60/turntrend，+6/+3）。本层当前**没有任何因子持有第③级证据** ⇒ 除放量弱势外全部为 0 分，属**有意的保守**。　🔴 结论（2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」）：本层唯一记分的「放量弱势 −0.5」有**三重问题** —— ①无回测依据（bottom 榜从未回测）；②设计上不相交（bottom=极端放量股 vs 候选池=缩量强势，实测交集 0 ⇒ 几乎恒不触发）；③上游 _weak 集合曾因 norm_code 未剥点而恒失配（29 轮命中 0 次，本补丁已修）。⇒ **因子在本层的实际计分影响 = 0**，现状等于「全部只做标注」；要让它真正成为加减分项，须先补 walk-forward 回测（流程见下方 ③ 待接入队列 / 明细见本页 🧪 因子审计卡）。",
    "dedup_note": "因子只对**池内已有票**动作（_factor_in_pool 只查不建）⇒ 不产池、不决定谁能进榜"
  },
  "factor_trace": [
    {
      "code": "605117",
      "name": "德业股份",
      "final_score": 29.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第9／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "603993",
      "name": "洛阳钼业",
      "final_score": 28.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第21／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "603268",
      "name": "松发股份",
      "final_score": 26.7,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第3／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "000807",
      "name": "云铝股份",
      "final_score": 23.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第23／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "002074",
      "name": "国轩高科",
      "final_score": 19.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第7／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ],
      "adj_total": 0.0
    }
  ]
};