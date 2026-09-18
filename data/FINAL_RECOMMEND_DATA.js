window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-09-18 19:36:18",
  "crisis_score": 32.2,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-18 07:06:51",
    "degraded": false,
    "effective": {
      "jinzuan": 8.581,
      "chan": 4.408,
      "trend": -7.495,
      "jigou": -9.422
    },
    "hardcoded_default": {
      "jinzuan": 8.11,
      "chan": 3.68,
      "trend": -7.54,
      "jigou": -10.36
    },
    "n_on10": {
      "jinzuan": 130,
      "chan": 239,
      "trend": 218,
      "jigou": 334
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-09-18 07:06:51",
      "hit": 4,
      "n_snapshots": 63,
      "date_range": [
        "2026-06-06",
        "2026-09-17"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-09-18",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-09-18",
    "source": "STOCK_QUOTE",
    "covered": 76,
    "total": 76,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "互联网电商",
    "元件",
    "光学光电子",
    "其他电子",
    "医疗服务",
    "半导体",
    "塑料制品",
    "小金属",
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
      "close": 346.96,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 3.54,
      "stop_loss": 328.5,
      "target_price": 383.88,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.32,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.69,
        "四量终极": 2.29
      },
      "resonance": 2,
      "strength": 3.98,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "final_score": 7.98,
      "buy_score": 7.98,
      "enter_date": "2026-09-15",
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分42；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "深成500",
        "深证100R",
        "AI眼镜",
        "机器人概念",
        "小米汽车",
        "2026中报预增",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-09-15",
        "entry_price": 346.96,
        "latest_price": 346.96,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "good",
            "code": "301308",
            "name": "江波龙",
            "text": "江波龙(301308) 连续 4 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 2,
      "code": "603993",
      "name": "洛阳钼业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 17.51,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.92,
      "stop_loss": 16.28,
      "target_price": 19.96,
      "risk_reward": 2.0,
      "support": 17.26,
      "resistance": 19.89,
      "atr": 0.57,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -1.74,
          "relative_5d": -1.74,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -6.22,
          "relative_5d": -6.22,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": -1.74,
          "relative_5d": -1.74,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -6.22,
          "relative_5d": -6.22,
          "strong": true
        }
      ],
      "final_score": 7.34,
      "buy_score": 7.34,
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项；基本面因子 高ROE 排名第21",
      "industry": "有色金属矿采选业",
      "concepts": [
        "昨日高振幅",
        "富时罗素",
        "小金属概念",
        "黄金概念",
        "上证180",
        "权重股",
        "2026中报预增",
        "标准普尔"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 17.51,
        "latest_price": 17.51,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "603993",
            "name": "洛阳钼业",
            "text": "洛阳钼业(603993) 于 2026-08-29 跌出共识（曾连续 2 日）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "grind"
    },
    {
      "rank": 3,
      "code": "300390",
      "name": "天华新能",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 54.2,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.9,
      "stop_loss": 52.3,
      "target_price": 58.0,
      "risk_reward": 2.0,
      "support": 50.58,
      "resistance": 70.8,
      "atr": 2.15,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "final_score": 6.34,
      "buy_score": 6.34,
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "独角兽",
        "2026一季报预增",
        "半导体概念",
        "深成500",
        "固态电池",
        "富时罗素",
        "中盘价值",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 54.2,
        "latest_price": 54.2,
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
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 84.63,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.09,
      "stop_loss": 76.17,
      "target_price": 107.12,
      "risk_reward": 2.66,
      "support": 80.84,
      "resistance": 98.32,
      "atr": 2.53,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.35,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.85,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 5.85,
      "buy_score": 5.85,
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分34；四量终极 信号0项；基本面因子 高ROE 排名第9",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "光伏概念",
        "HS300",
        "储能概念",
        "先进制造风格",
        "2026一季报预增",
        "国产芯片",
        "融资融券",
        "大盘成长"
      ],
      "tracking": {
        "entry_date": "2026-09-12",
        "entry_price": 84.63,
        "latest_price": 84.63,
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
      "code": "688111",
      "name": "金山办公",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线",
      "close": 223.61,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.25,
      "stop_loss": 201.25,
      "target_price": 268.33,
      "risk_reward": 2.0,
      "support": 220.0,
      "resistance": 251.36,
      "atr": 6.34,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 5.34,
      "buy_score": 5.34,
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "2026一季报预增",
        "上证180",
        "茅指数",
        "国产软件",
        "Kimi概念",
        "大盘股",
        "信创",
        "AI应用"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 223.61,
        "latest_price": 223.61,
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
      "close": 346.96,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 3.54,
      "stop_loss": 328.5,
      "target_price": 383.88,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88,
      "atr": 12.32,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.69,
        "四量终极": 2.29
      },
      "resonance": 2,
      "strength": 3.98,
      "final_score": 7.98,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "enter_date": "2026-09-15",
      "signals": [
        "跨策略共振",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分42；四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "深成500",
        "深证100R",
        "AI眼镜",
        "机器人概念",
        "小米汽车",
        "2026中报预增",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-09-15",
        "entry_price": 346.96,
        "latest_price": 346.96,
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
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 84.63,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.09,
      "stop_loss": 76.17,
      "target_price": 107.12,
      "risk_reward": 2.66,
      "support": 80.84,
      "resistance": 98.32,
      "atr": 2.53,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.35,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.85,
      "final_score": 5.85,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-12",
      "signals": [
        "跨策略共振",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分34；四量终极 信号0项；基本面因子 高ROE 排名第9",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "光伏概念",
        "HS300",
        "储能概念",
        "先进制造风格",
        "2026一季报预增",
        "国产芯片",
        "融资融券",
        "大盘成长"
      ],
      "tracking": {
        "entry_date": "2026-09-12",
        "entry_price": 84.63,
        "latest_price": 84.63,
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
      "code": "603993",
      "name": "洛阳钼业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.51,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.92,
      "stop_loss": 16.28,
      "target_price": 19.96,
      "risk_reward": 2.0,
      "support": 17.26,
      "resistance": 19.89,
      "atr": 0.57,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "final_score": 7.34,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -1.74,
          "relative_5d": -1.74,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -6.22,
          "relative_5d": -6.22,
          "strong": true
        }
      ],
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项；基本面因子 高ROE 排名第21",
      "industry": "有色金属矿采选业",
      "concepts": [
        "昨日高振幅",
        "富时罗素",
        "小金属概念",
        "黄金概念",
        "上证180",
        "权重股",
        "2026中报预增",
        "标准普尔"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 17.51,
        "latest_price": 17.51,
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
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 54.2,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 2.9,
      "stop_loss": 52.3,
      "target_price": 58.0,
      "risk_reward": 2.0,
      "support": 50.58,
      "resistance": 70.8,
      "atr": 2.15,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "final_score": 6.34,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.3,
          "relative_5d": 4.3,
          "strong": true
        }
      ],
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "独角兽",
        "2026一季报预增",
        "半导体概念",
        "深成500",
        "固态电池",
        "富时罗素",
        "中盘价值",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 54.2,
        "latest_price": 54.2,
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
      "code": "688111",
      "name": "金山办公",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 223.61,
      "close_date": "2026-09-18",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.25,
      "stop_loss": 201.25,
      "target_price": 268.33,
      "risk_reward": 2.0,
      "support": 220.0,
      "resistance": 251.36,
      "atr": 6.34,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 3.84
      },
      "resonance": 1,
      "strength": 3.84,
      "final_score": 5.34,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-18",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "2026一季报预增",
        "上证180",
        "茅指数",
        "国产软件",
        "Kimi概念",
        "大盘股",
        "信创",
        "AI应用"
      ],
      "tracking": {
        "entry_date": "2026-09-18",
        "entry_price": 223.61,
        "latest_price": 223.61,
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
      "close": 346.96,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 3.54,
      "final_score": 7.98,
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
        "半导体概念",
        "深成500",
        "深证100R",
        "AI眼镜",
        "机器人概念",
        "小米汽车",
        "2026中报预增",
        "创业板综"
      ],
      "enter_date": "2026-09-15",
      "stop_loss": 328.5,
      "target_price": 383.88,
      "risk_reward": 2.0,
      "support": 327.45,
      "resistance": 386.88
    },
    {
      "code": "603993",
      "name": "洛阳钼业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.51,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.92,
      "final_score": 7.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号",
        "高ROE"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "昨日高振幅",
        "富时罗素",
        "小金属概念",
        "黄金概念",
        "上证180",
        "权重股",
        "2026中报预增",
        "标准普尔"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 16.28,
      "target_price": 19.96,
      "risk_reward": 2.0,
      "support": 17.26,
      "resistance": 19.89
    },
    {
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 54.2,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 2.9,
      "final_score": 6.34,
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
        "2026一季报预增",
        "半导体概念",
        "深成500",
        "固态电池",
        "富时罗素",
        "中盘价值",
        "储能概念"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 52.3,
      "target_price": 58.0,
      "risk_reward": 2.0,
      "support": 50.58,
      "resistance": 70.8
    },
    {
      "code": "605117",
      "name": "德业股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 84.63,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 2.09,
      "final_score": 5.85,
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
        "光伏概念",
        "HS300",
        "储能概念",
        "先进制造风格",
        "2026一季报预增",
        "国产芯片",
        "融资融券",
        "大盘成长"
      ],
      "enter_date": "2026-09-12",
      "stop_loss": 76.17,
      "target_price": 107.12,
      "risk_reward": 2.66,
      "support": 80.84,
      "resistance": 98.32
    },
    {
      "code": "688111",
      "name": "金山办公",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 223.61,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.25,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "2026一季报预增",
        "上证180",
        "茅指数",
        "国产软件",
        "Kimi概念",
        "大盘股",
        "信创",
        "AI应用"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 201.25,
      "target_price": 268.33,
      "risk_reward": 2.0,
      "support": 220.0,
      "resistance": 251.36
    },
    {
      "code": "600030",
      "name": "中信证券",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.54,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 1.45,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "互联网金融",
        "科创板做市商",
        "富时罗素",
        "上证180",
        "参股期货",
        "资本市场服务",
        "权重股",
        "2026中报预增"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 26.16,
      "target_price": 27.3,
      "risk_reward": 2.0,
      "support": 26.08,
      "resistance": 28.33
    },
    {
      "code": "300124",
      "name": "汇川技术",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 52.45,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 1.67,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "深成500",
        "深证100R",
        "富时罗素",
        "工业母机",
        "茅指数",
        "机器人概念",
        "小米汽车",
        "人形机器人"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 51.59,
      "target_price": 54.17,
      "risk_reward": 2.0,
      "support": 49.95,
      "resistance": 63.2
    },
    {
      "code": "600031",
      "name": "三一重工",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.89,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": -1.0,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "一带一路",
        "专用设备制造业",
        "富时罗素",
        "上证180",
        "茅指数",
        "工程机械概念",
        "标准普尔",
        "参股银行"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 16.81,
      "target_price": 20.6,
      "risk_reward": 2.0,
      "support": 17.55,
      "resistance": 20.56
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 18.22,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.28,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 16.97,
      "target_price": 20.8,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "09866",
      "name": "蔚来-SW",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 29.1,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 3.93,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 28.58,
      "target_price": 29.7,
      "risk_reward": 6.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "09987",
      "name": "百胜中国",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 324.2,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": -1.04,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 309.69,
      "target_price": 379.62,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "01109",
      "name": "华润置地",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 28.64,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.49,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 26.49,
      "target_price": 32.47,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "06862",
      "name": "海底捞",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 9.51,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.05,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 8.95,
      "target_price": 10.97,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "02318",
      "name": "中国平安",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 53.2,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.66,
      "final_score": 5.34,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-09-18",
      "stop_loss": 49.29,
      "target_price": 60.42,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null
    },
    {
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 36.03,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 1.64,
      "final_score": 5.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "有色金属矿采选业",
      "concepts": [
        "昨日高振幅",
        "题材股",
        "百日新高",
        "钒电池",
        "小金属概念",
        "黄金概念",
        "上证180",
        "2026中报预增"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 32.97,
      "target_price": 41.15,
      "risk_reward": 2.3,
      "support": 34.67,
      "resistance": 41.97
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 267.89,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 0.34,
      "final_score": 3.1,
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
        "昨日高振幅",
        "2026一季报预增",
        "云计算",
        "车联网(车路云)",
        "半导体概念",
        "深成500",
        "AI眼镜",
        "AIGC概念"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 266.98,
      "target_price": 269.71,
      "risk_reward": 2.0,
      "support": 231.77,
      "resistance": 275.99
    },
    {
      "code": "600183",
      "name": "生益科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 143.93,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": -1.44,
      "final_score": 3.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "高ROE"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "昨日高振幅",
        "富时罗素",
        "上证180",
        "QFII重仓",
        "最近多板",
        "PCB",
        "2026中报预增",
        "标准普尔"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 133.85,
      "target_price": 164.08,
      "risk_reward": 2.0,
      "support": 122.05,
      "resistance": 157.5
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 445.0,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 4.87,
      "final_score": 2.1,
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
        "深成500",
        "深证100R",
        "富时罗素",
        "权重股",
        "基金重仓",
        "2026中报预增",
        "创业板综",
        "创业成份"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 400.5,
      "target_price": 534.0,
      "risk_reward": 2.0,
      "support": 378.56,
      "resistance": 453.78
    },
    {
      "code": "603268",
      "name": "松发股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 208.0,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": 7.49,
      "final_score": 2.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点",
        "高ROE"
      ],
      "industry": "铁路、船舶、航空航天和其他运输设备制造业",
      "concepts": [
        "贬值受益",
        "先进制造风格",
        "融资融券",
        "大盘成长",
        "铁路、船舶、航空航天和其他运输设备制造业",
        "船舶制造",
        "2026中报预增",
        "并购重组概念"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 193.44,
      "target_price": 237.12,
      "risk_reward": 2.0,
      "support": 178.0,
      "resistance": 212.0
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 23.5,
      "close_date": "2026-09-18",
      "close_verified": true,
      "pct_chg": -0.63,
      "final_score": 2.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "医药制造业",
        "医药医疗风格",
        "肝炎概念",
        "2026中报预增",
        "AI制药（医疗）",
        "创业板综",
        "病原体防治"
      ],
      "enter_date": "2026-09-18",
      "stop_loss": 21.09,
      "target_price": 28.12,
      "risk_reward": 2.0,
      "support": 21.7,
      "resistance": 24.19
    }
  ]
};