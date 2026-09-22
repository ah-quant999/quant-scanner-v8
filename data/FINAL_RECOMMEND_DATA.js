window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-09-23 05:20:51",
  "crisis_score": 32.1,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-23 03:00:32",
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
      "generated": "2026-09-23 03:00:32",
      "hit": 4,
      "n_snapshots": 69,
      "date_range": [
        "2026-06-06",
        "2026-09-23"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-09-22） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-09-22",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-09-23",
    "source": "STOCK_QUOTE",
    "covered": 20,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "互联网电商",
    "光学光电子",
    "化学制药",
    "医疗器械",
    "医疗服务",
    "半导体",
    "家居用品",
    "小金属",
    "房地产",
    "文化传媒",
    "生物制品",
    "贵金属"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "601168",
      "name": "西部矿业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 36.77,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.49,
      "stop_loss": 33.09,
      "target_price": 43.29,
      "risk_reward": 1.77,
      "support": 34.67,
      "resistance": 41.97,
      "atr": 1.54,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.34,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.84,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": 2.61,
          "relative_5d": 2.61,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -2.79,
          "relative_5d": -2.79,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": 2.61,
          "relative_5d": 2.61,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -2.79,
          "relative_5d": -2.79,
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
      "reason": "三重共识 评分34；四量终极 信号0项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "新材料",
        "融资融券",
        "上证180",
        "近期新高",
        "稀缺资源",
        "央国企改革",
        "小金属概念",
        "2026中报预增"
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
      "rank": 2,
      "code": "300199",
      "name": "翰宇药业",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.85,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.1,
      "stop_loss": 21.47,
      "target_price": 27.7,
      "risk_reward": 1.61,
      "support": 22.26,
      "resistance": 24.19,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.55,
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
      "reason": "三重共识 评分30；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "互联医疗",
        "医药制造业",
        "辅助生殖",
        "融资融券",
        "流感",
        "创业板综",
        "深圳特区"
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
      "rank": 3,
      "code": "301308",
      "name": "江波龙",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 348.27,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.14,
      "stop_loss": 313.44,
      "target_price": 749.88,
      "risk_reward": 11.53,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.41,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.55,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.07,
          "relative_5d": 10.07,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 10.07,
          "relative_5d": 10.07,
          "strong": true
        }
      ],
      "final_score": 30.4,
      "buy_score": 30.4,
      "enter_date": "2026-09-15",
      "signals": [
        "机构变红",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分30；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "大盘价值",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "深证100R",
        "百元股",
        "2026中报预增",
        "AI眼镜"
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
            "text": "江波龙(301308) 连续 9 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 4,
      "code": "605117",
      "name": "德业股份",
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 82.38,
      "close_date": "2026-09-23",
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
        "三重共识": 1.18,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.68,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 29.4,
      "buy_score": 29.4,
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分29；四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "MSCI中国",
        "2026中报预增",
        "2026一季报预增",
        "大盘成长",
        "周期股",
        "国产芯片",
        "大盘股"
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
    },
    {
      "rank": 5,
      "code": "603993",
      "name": "洛阳钼业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 17.81,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.25,
      "stop_loss": 16.03,
      "target_price": 21.07,
      "risk_reward": 1.83,
      "support": 17.26,
      "resistance": 19.89,
      "atr": 0.52,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.67
      },
      "resonance": 1,
      "strength": 1.67,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": 2.61,
          "relative_5d": 2.61,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -2.79,
          "relative_5d": -2.79,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": 2.61,
          "relative_5d": 2.61,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -2.79,
          "relative_5d": -2.79,
          "strong": true
        }
      ],
      "final_score": 29.2,
      "buy_score": 29.2,
      "enter_date": "2026-09-23",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "融资融券",
        "权重股",
        "上证180",
        "稀缺资源",
        "小金属概念",
        "2026中报预增",
        "标准普尔",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-09-23",
        "entry_price": 17.81,
        "latest_price": 17.81,
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
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 36.77,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.49,
      "stop_loss": 33.09,
      "target_price": 43.29,
      "risk_reward": 1.77,
      "support": 34.67,
      "resistance": 41.97,
      "atr": 1.54,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.34,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.84,
      "final_score": 33.5,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": 2.61,
          "relative_5d": 2.61,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -2.79,
          "relative_5d": -2.79,
          "strong": true
        }
      ],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分34；四量终极 信号0项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "新材料",
        "融资融券",
        "上证180",
        "近期新高",
        "稀缺资源",
        "央国企改革",
        "小金属概念",
        "2026中报预增"
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
      "rank": 2,
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.85,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.1,
      "stop_loss": 21.47,
      "target_price": 27.7,
      "risk_reward": 1.61,
      "support": 22.26,
      "resistance": 24.19,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.55,
      "final_score": 30.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-22",
      "signals": [
        "跨策略共振",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分30；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "互联医疗",
        "医药制造业",
        "辅助生殖",
        "融资融券",
        "流感",
        "创业板综",
        "深圳特区"
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
      "rank": 3,
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 348.27,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.14,
      "stop_loss": 313.44,
      "target_price": 749.88,
      "risk_reward": 11.53,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.41,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.22,
        "四量终极": 1.33
      },
      "resonance": 2,
      "strength": 2.55,
      "final_score": 30.4,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 10.07,
          "relative_5d": 10.07,
          "strong": true
        }
      ],
      "enter_date": "2026-09-15",
      "signals": [
        "跨策略共振",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分30；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "大盘价值",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "深证100R",
        "百元股",
        "2026中报预增",
        "AI眼镜"
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
      "rank": 4,
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 82.38,
      "close_date": "2026-09-23",
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
        "三重共识": 1.18,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.68,
      "final_score": 29.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分29；四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "MSCI中国",
        "2026中报预增",
        "2026一季报预增",
        "大盘成长",
        "周期股",
        "国产芯片",
        "大盘股"
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
    },
    {
      "rank": 5,
      "code": "603268",
      "name": "松发股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 219.0,
      "close_date": "2026-09-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -1.15,
      "stop_loss": 197.1,
      "target_price": 228.0,
      "risk_reward": 0.41,
      "support": 181.0,
      "resistance": 228.0,
      "atr": 9.38,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.12,
        "四量终极": 1.17
      },
      "resonance": 2,
      "strength": 2.29,
      "final_score": 28.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-22",
      "signals": [
        "跨策略共振",
        "缠论买点",
        "机构变红",
        "上涨趋势"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分28；四量终极 信号3项",
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "大盘成长",
        "2026中报预增",
        "QFII重仓",
        "大盘股",
        "融资融券",
        "先进制造风格",
        "机构重仓",
        "并购重组概念"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 219.0,
        "latest_price": 219.0,
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
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 36.77,
      "close_date": "2026-09-23",
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
        "融资融券",
        "上证180",
        "近期新高",
        "稀缺资源",
        "央国企改革",
        "小金属概念",
        "2026中报预增"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 33.09,
      "target_price": 43.29,
      "risk_reward": 1.77,
      "support": 34.67,
      "resistance": 41.97,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 23.85,
      "close_date": "2026-09-23",
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
        "新消费",
        "互联医疗",
        "医药制造业",
        "辅助生殖",
        "融资融券",
        "流感",
        "创业板综",
        "深圳特区"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 21.47,
      "target_price": 27.7,
      "risk_reward": 1.61,
      "support": 22.26,
      "resistance": 24.19,
      "factor_actions": []
    },
    {
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 348.27,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 0.14,
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
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "大盘价值",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "深证100R",
        "百元股",
        "2026中报预增",
        "AI眼镜"
      ],
      "enter_date": "2026-09-15",
      "stop_loss": 313.44,
      "target_price": 749.88,
      "risk_reward": 11.53,
      "support": 327.45,
      "resistance": 386.88,
      "factor_actions": []
    },
    {
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 82.38,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 0.5,
      "final_score": 29.4,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "MSCI中国",
        "2026中报预增",
        "2026一季报预增",
        "大盘成长",
        "周期股",
        "国产芯片",
        "大盘股"
      ],
      "enter_date": "2026-09-12",
      "stop_loss": 74.14,
      "target_price": 104.56,
      "risk_reward": 2.69,
      "support": 80.84,
      "resistance": 98.32,
      "factor_actions": []
    },
    {
      "code": "603993",
      "name": "洛阳钼业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.81,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 1.25,
      "final_score": 29.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "融资融券",
        "权重股",
        "上证180",
        "稀缺资源",
        "小金属概念",
        "2026中报预增",
        "标准普尔",
        "富时罗素"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 16.03,
      "target_price": 21.07,
      "risk_reward": 1.83,
      "support": 17.26,
      "resistance": 19.89,
      "factor_actions": []
    },
    {
      "code": "603268",
      "name": "松发股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 219.0,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": -1.15,
      "final_score": 28.0,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "大盘成长",
        "2026中报预增",
        "QFII重仓",
        "大盘股",
        "融资融券",
        "先进制造风格",
        "机构重仓",
        "并购重组概念"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 197.1,
      "target_price": 228.0,
      "risk_reward": 0.41,
      "support": 181.0,
      "resistance": 228.0,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 455.0,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": -0.38,
      "final_score": 26.7,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "权重股",
        "机构重仓",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "5G概念",
        "百元股",
        "深证100R"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 409.5,
      "target_price": 618.87,
      "risk_reward": 3.6,
      "support": 378.56,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "000737",
      "name": "北方铜业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.11,
      "close_date": "2026-09-23",
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
        "黄金概念",
        "深股通",
        "2026中报预增",
        "新材料",
        "中盘成长",
        "融资融券",
        "深成500",
        "昨日高振幅"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 13.6,
      "target_price": 17.2,
      "risk_reward": 1.38,
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
      "close_date": "2026-09-23",
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
        "储能概念",
        "中芯概念",
        "2026一季报预增",
        "先进制造风格",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "锂电池概念"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 48.81,
      "target_price": 96.51,
      "risk_reward": 7.8,
      "support": 50.58,
      "resistance": 65.94,
      "factor_actions": []
    },
    {
      "code": "688808",
      "name": "联讯仪器",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 2316.0,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": -0.99,
      "final_score": 24.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 2084.4,
      "target_price": 2733.0,
      "risk_reward": 1.8,
      "support": 2123.0,
      "resistance": 2733.0,
      "factor_actions": []
    },
    {
      "code": "688525",
      "name": "佰维存储",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 217.22,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": -0.17,
      "final_score": 24.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "数据中心",
        "融资融券",
        "智能穿戴",
        "计算机、通信和其他电子设备制造业",
        "上证180",
        "百元股",
        "汽车芯片",
        "消费电子概念"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 195.5,
      "target_price": 515.23,
      "risk_reward": 13.72,
      "support": 204.58,
      "resistance": 238.22,
      "factor_actions": []
    },
    {
      "code": "000807",
      "name": "云铝股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.95,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 0.67,
      "final_score": 23.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "大盘价值",
        "融资融券",
        "深证100R",
        "稀缺资源",
        "央国企改革",
        "2026中报预增",
        "标准普尔",
        "节能环保"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 24.25,
      "target_price": 29.13,
      "risk_reward": 0.81,
      "support": 26.11,
      "resistance": 29.13,
      "factor_actions": []
    },
    {
      "code": "002463",
      "name": "沪电股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 125.14,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": -0.68,
      "final_score": 23.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "2026一季报预增",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "5G概念",
        "深证100R",
        "百元股",
        "2026中报预增",
        "标准普尔"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 112.63,
      "target_price": 158.2,
      "risk_reward": 2.64,
      "support": 110.59,
      "resistance": 131.25,
      "factor_actions": []
    },
    {
      "code": "688257",
      "name": "新锐股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 58.42,
      "close_date": "2026-09-23",
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
        "2026中报预增",
        "2026一季报预增",
        "新材料",
        "融资融券",
        "小盘成长",
        "有色金属冶炼和压延加工业",
        "专精特新",
        "小盘股"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 52.58,
      "target_price": 117.77,
      "risk_reward": 10.16,
      "support": 48.98,
      "resistance": 60.89,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 273.35,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 0.09,
      "final_score": 21.7,
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
        "2026一季报预增",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "创业板综",
        "百元股",
        "物联网",
        "深圳特区",
        "光通信模块"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 246.02,
      "target_price": 343.0,
      "risk_reward": 2.55,
      "support": 232.0,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "000703",
      "name": "恒逸石化",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 16.81,
      "close_date": "2026-09-23",
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
        "新材料",
        "中盘价值",
        "标准普尔",
        "一带一路",
        "转债标的",
        "富时罗素",
        "融资融券"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 15.13,
      "target_price": 20.13,
      "risk_reward": 1.98,
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
      "close_date": "2026-09-23",
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
        "2026一季报预增",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "5G概念",
        "深证100R",
        "百元股",
        "光通信模块",
        "2026中报预增"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 178.31,
      "target_price": 280.08,
      "risk_reward": 4.14,
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
      "close_date": "2026-09-23",
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
        "新材料",
        "大盘价值",
        "融资融券",
        "机构重仓",
        "5G概念",
        "深证100R",
        "稀缺资源",
        "央国企改革"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 5.54,
      "target_price": 7.0,
      "risk_reward": 1.36,
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
      "close_date": "2026-09-23",
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
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "百元股",
        "光通信模块",
        "2026中报预增",
        "QFII重仓",
        "大盘股",
        "光纤概念"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 1577.79,
      "target_price": 1919.0,
      "risk_reward": 0.95,
      "support": 1440.03,
      "resistance": 1888.0,
      "factor_actions": []
    },
    {
      "code": "601600",
      "name": "中国铝业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.27,
      "close_date": "2026-09-23",
      "close_verified": true,
      "pct_chg": 0.98,
      "final_score": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "2026一季报预增",
        "大盘价值",
        "融资融券",
        "有色金属冶炼和压延加工业",
        "稀土永磁",
        "上证180",
        "央国企改革",
        "小金属概念"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 8.34,
      "target_price": 10.25,
      "risk_reward": 1.06,
      "support": 8.95,
      "resistance": 10.09,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-09-23 05:20:51",
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