window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-10 02:36:42",
  "crisis_score": 32.6,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-10 02:16:58",
    "degraded": false,
    "effective": {
      "jinzuan": 1.486,
      "chan": 0.86,
      "trend": -1.62,
      "jigou": -1.202
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 169,
      "chan": 363,
      "trend": 263,
      "jigou": 455
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-10 02:16:58",
      "hit": 4,
      "n_snapshots": 79,
      "date_range": [
        "2026-06-06",
        "2026-10-10"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-10-09",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": null,
    "source": null,
    "covered": 0,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "化学原料",
    "小家电",
    "小金属",
    "影视院线",
    "房地产",
    "文化传媒",
    "煤炭开采加工",
    "电池",
    "种植业与林业",
    "贵金属",
    "饮料制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "601899",
      "name": "紫金矿业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 30.8,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 4.87,
      "stop_loss": 27.72,
      "target_price": 35.47,
      "risk_reward": 1.52,
      "support": 29.01,
      "resistance": 34.53,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 0.96,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 2.61,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        }
      ],
      "final_score": 18.9,
      "buy_score": 18.9,
      "enter_date": "2026-08-17",
      "signals": [
        "缠论买点",
        "缩量强势",
        "跨策略共振",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分24；四量终极 信号1项；基本面因子 高ROE 排名第15",
      "industry": "有色金属矿采选业",
      "concepts": [
        "机构重仓",
        "HS300",
        "标准普尔",
        "小金属概念",
        "黄金概念",
        "周期股",
        "AH股",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 30.8,
        "latest_price": 30.8,
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
      "code": "300821",
      "name": "东岳硅材",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 17.15,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 20.01,
      "stop_loss": 15.43,
      "target_price": 30.49,
      "risk_reward": 7.78,
      "support": 14.07,
      "resistance": 17.15,
      "atr": 0.71,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.24
      },
      "resonance": 1,
      "strength": 2.24,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 18.6,
      "buy_score": 18.6,
      "enter_date": "2026-10-10",
      "signals": [
        "多周期共振(日线口径)",
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "机构重仓",
        "氢能源",
        "2025三季报预减",
        "有机硅概念",
        "化学原料和化学制品制造业",
        "2026中报预增",
        "深股通",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 17.15,
        "latest_price": 17.15,
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
      "code": "600988",
      "name": "赤峰黄金",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 41.38,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 5.91,
      "stop_loss": 37.24,
      "target_price": 51.99,
      "risk_reward": 2.56,
      "support": 36.83,
      "resistance": 47.63,
      "atr": 2.04,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        }
      ],
      "final_score": 16.9,
      "buy_score": 16.9,
      "enter_date": "2026-10-10",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "题材股",
        "黄金概念",
        "昨日炸板",
        "AH股",
        "富时罗素",
        "MSCI中国",
        "中盘成长",
        "昨日高振幅"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 41.38,
        "latest_price": 41.38,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "600988",
            "name": "赤峰黄金",
            "text": "赤峰黄金(600988) 于 2026-08-22 跌出共识（曾连续 2 日）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300045",
      "name": "华力创通",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 12.74,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 7.69,
      "stop_loss": 11.47,
      "target_price": 18.6,
      "risk_reward": 4.6,
      "support": 11.04,
      "resistance": 13.26,
      "atr": 0.58,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.44
      },
      "resonance": 1,
      "strength": 1.44,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 15.7,
      "buy_score": 15.7,
      "enter_date": "2026-10-10",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "网络安全",
        "大飞机",
        "小盘成长",
        "小盘股",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "无人机",
        "数字孪生"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 12.74,
        "latest_price": 12.74,
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
      "code": "300037",
      "name": "新宙邦",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 64.79,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -3.08,
      "stop_loss": 58.31,
      "target_price": 82.48,
      "risk_reward": 2.73,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.08,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 14.1,
      "buy_score": 14.1,
      "enter_date": "2026-10-10",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "氟化工概念",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "MSCI中国",
        "锂电池概念",
        "融资融券",
        "电池技术",
        "转债标的"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 64.79,
        "latest_price": 64.79,
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
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线/中线共振",
      "close": 30.8,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 4.87,
      "stop_loss": 27.72,
      "target_price": 35.47,
      "risk_reward": 1.52,
      "support": 29.01,
      "resistance": 34.53,
      "atr": 0.91,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 0.96,
        "四量终极": 1.65
      },
      "resonance": 2,
      "strength": 2.61,
      "final_score": 18.9,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        }
      ],
      "enter_date": "2026-08-17",
      "signals": [
        "跨策略共振",
        "缠论买点",
        "缩量强势",
        "高ROE"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分24；四量终极 信号1项；基本面因子 高ROE 排名第15",
      "industry": "有色金属矿采选业",
      "concepts": [
        "机构重仓",
        "HS300",
        "标准普尔",
        "小金属概念",
        "黄金概念",
        "周期股",
        "AH股",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-08-17",
        "entry_price": 30.8,
        "latest_price": 30.8,
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
      "code": "300821",
      "name": "东岳硅材",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 17.15,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 20.01,
      "stop_loss": 15.43,
      "target_price": 30.49,
      "risk_reward": 7.78,
      "support": 14.07,
      "resistance": 17.15,
      "atr": 0.71,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.24
      },
      "resonance": 1,
      "strength": 2.24,
      "final_score": 18.6,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-10",
      "signals": [
        "多周期共振(日线口径)",
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "机构重仓",
        "氢能源",
        "2025三季报预减",
        "有机硅概念",
        "化学原料和化学制品制造业",
        "2026中报预增",
        "深股通",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 17.15,
        "latest_price": 17.15,
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
      "code": "600988",
      "name": "赤峰黄金",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 41.38,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 5.91,
      "stop_loss": 37.24,
      "target_price": 51.99,
      "risk_reward": 2.56,
      "support": 36.83,
      "resistance": 47.63,
      "atr": 2.04,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 16.9,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "贵金属",
          "pct_5d": -0.13,
          "relative_5d": -0.13,
          "strong": true
        },
        {
          "name": "小金属",
          "pct_5d": -4.65,
          "relative_5d": -4.65,
          "strong": true
        }
      ],
      "enter_date": "2026-10-10",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "题材股",
        "黄金概念",
        "昨日炸板",
        "AH股",
        "富时罗素",
        "MSCI中国",
        "中盘成长",
        "昨日高振幅"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 41.38,
        "latest_price": 41.38,
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
      "code": "300045",
      "name": "华力创通",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 12.74,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 7.69,
      "stop_loss": 11.47,
      "target_price": 18.6,
      "risk_reward": 4.6,
      "support": 11.04,
      "resistance": 13.26,
      "atr": 0.58,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.44
      },
      "resonance": 1,
      "strength": 1.44,
      "final_score": 15.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-10",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "网络安全",
        "大飞机",
        "小盘成长",
        "小盘股",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "无人机",
        "数字孪生"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 12.74,
        "latest_price": 12.74,
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
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 64.79,
      "close_date": "2026-10-10",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -3.08,
      "stop_loss": 58.31,
      "target_price": 82.48,
      "risk_reward": 2.73,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.08,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 14.1,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-10",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "氟化工概念",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "MSCI中国",
        "锂电池概念",
        "融资融券",
        "电池技术",
        "转债标的"
      ],
      "tracking": {
        "entry_date": "2026-10-10",
        "entry_price": 64.79,
        "latest_price": 64.79,
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
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "中长线",
      "close": 30.8,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 4.87,
      "final_score": 18.9,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "缩量强势",
        "跨策略共振",
        "高ROE"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "机构重仓",
        "HS300",
        "标准普尔",
        "小金属概念",
        "黄金概念",
        "周期股",
        "AH股",
        "富时罗素"
      ],
      "enter_date": "2026-08-17",
      "stop_loss": 27.72,
      "target_price": 35.47,
      "risk_reward": 1.52,
      "support": 29.01,
      "resistance": 34.53,
      "factor_actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第25／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        },
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第15／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ]
    },
    {
      "code": "300821",
      "name": "东岳硅材",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 17.15,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 20.01,
      "final_score": 18.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "多周期共振(日线口径)",
        "机构变红",
        "缠论买点"
      ],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "机构重仓",
        "氢能源",
        "2025三季报预减",
        "有机硅概念",
        "化学原料和化学制品制造业",
        "2026中报预增",
        "深股通",
        "融资融券"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 15.43,
      "target_price": 30.49,
      "risk_reward": 7.78,
      "support": 14.07,
      "resistance": 17.15,
      "factor_actions": []
    },
    {
      "code": "600988",
      "name": "赤峰黄金",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 41.38,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 5.91,
      "final_score": 16.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "题材股",
        "黄金概念",
        "昨日炸板",
        "AH股",
        "富时罗素",
        "MSCI中国",
        "中盘成长",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 37.24,
      "target_price": 51.99,
      "risk_reward": 2.56,
      "support": 36.83,
      "resistance": 47.63,
      "factor_actions": []
    },
    {
      "code": "300045",
      "name": "华力创通",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 12.74,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 7.69,
      "final_score": 15.7,
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
        "网络安全",
        "大飞机",
        "小盘成长",
        "小盘股",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "无人机",
        "数字孪生"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 11.47,
      "target_price": 18.6,
      "risk_reward": 4.6,
      "support": 11.04,
      "resistance": 13.26,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 64.79,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -3.08,
      "final_score": 14.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "氟化工概念",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "MSCI中国",
        "锂电池概念",
        "融资融券",
        "电池技术",
        "转债标的"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 58.31,
      "target_price": 82.48,
      "risk_reward": 2.73,
      "support": 61.88,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "600176",
      "name": "中国巨石",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 38.57,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -2.48,
      "final_score": 13.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "非金属矿物制品业",
      "concepts": [
        "中字头",
        "HS300",
        "标准普尔",
        "风能",
        "周期股",
        "新材料",
        "富时罗素",
        "MSCI中国"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 34.71,
      "target_price": 63.0,
      "risk_reward": 6.33,
      "support": 36.01,
      "resistance": 51.68,
      "factor_actions": []
    },
    {
      "code": "688036",
      "name": "传音控股",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 48.95,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 6.18,
      "final_score": 13.1,
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
        "HS300",
        "AI智能体",
        "DeepSeek概念",
        "AI手机",
        "股权激励",
        "沪股通",
        "融资融券",
        "大盘股"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 44.06,
      "target_price": 70.78,
      "risk_reward": 4.46,
      "support": 45.26,
      "resistance": 57.8,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 232.68,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -0.9,
      "final_score": 13.0,
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
        "大盘成长",
        "AIGC概念",
        "百元股",
        "存储芯片",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "物联网",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 209.41,
      "target_price": 309.65,
      "risk_reward": 3.31,
      "support": 218.9,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 370.2,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -2.19,
      "final_score": 12.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "机构重仓",
        "HS300",
        "大盘成长",
        "百元股",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "MSCI中国",
        "基金重仓"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 333.18,
      "target_price": 579.42,
      "risk_reward": 5.65,
      "support": 350.1,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1206.01,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -6.54,
      "final_score": 12.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "大盘成长",
        "光纤概念",
        "QFII重仓",
        "百元股",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "昨日高振幅",
        "基金重仓"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 1085.41,
      "target_price": 1918.0,
      "risk_reward": 5.9,
      "support": 1156.0,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "002270",
      "name": "华明装备",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 18.81,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 12.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "电气机械和器材制造业",
        "特高压",
        "光伏概念",
        "小盘价值",
        "深成500",
        "融资融券",
        "深股通",
        "工业母机"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 16.93,
      "target_price": 21.2,
      "risk_reward": 1.27,
      "support": 16.78,
      "resistance": 19.85,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 145.49,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -3.43,
      "final_score": 11.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "HS300",
        "标准普尔",
        "周期股",
        "百元股",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "富时罗素",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 130.94,
      "target_price": 280.08,
      "risk_reward": 9.25,
      "support": 139.0,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 62.74,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.22,
      "final_score": 11.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "HS300",
        "毫米波概念",
        "标准普尔",
        "存储芯片",
        "新材料",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "生物识别"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 56.47,
      "target_price": 113.82,
      "risk_reward": 8.14,
      "support": 58.73,
      "resistance": 74.45,
      "factor_actions": []
    },
    {
      "code": "601138",
      "name": "工业富联",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 56.07,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.68,
      "final_score": 11.3,
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
        "HS300",
        "标准普尔",
        "独角兽",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国",
        "富时罗素",
        "物联网",
        "工业互联"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 50.46,
      "target_price": 70.97,
      "risk_reward": 2.66,
      "support": 53.4,
      "resistance": 66.88,
      "factor_actions": []
    },
    {
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 22.07,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.18,
      "final_score": 11.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "水上运输业",
      "concepts": [
        "昨日高振幅",
        "HS300",
        "央国企改革",
        "海洋经济",
        "大盘价值",
        "2026中报预增",
        "天然气",
        "水上运输业"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 19.86,
      "target_price": 22.98,
      "risk_reward": 0.41,
      "support": 18.5,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "300661",
      "name": "圣邦股份",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 95.97,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -0.03,
      "final_score": 11.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "HS300",
        "无线耳机",
        "百元股",
        "存储芯片",
        "AH股",
        "富时罗素",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 86.37,
      "target_price": 136.3,
      "risk_reward": 4.2,
      "support": 92.3,
      "resistance": 127.47,
      "factor_actions": []
    },
    {
      "code": "002139",
      "name": "拓邦股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.83,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 10.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "鸿蒙概念",
        "华为汽车",
        "光伏概念",
        "储能概念",
        "无线耳机",
        "小盘股",
        "电网概念",
        "智能电网"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 8.85,
      "target_price": 10.65,
      "risk_reward": 0.83,
      "support": 9.1,
      "resistance": 10.15,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 387.87,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": -1.55,
      "final_score": 10.7,
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
        "大盘成长",
        "标准普尔",
        "光纤概念",
        "碳化硅",
        "百元股",
        "海工装备",
        "AH股",
        "富时罗素"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 349.08,
      "target_price": 483.8,
      "risk_reward": 2.47,
      "support": 366.01,
      "resistance": 483.8,
      "factor_actions": []
    },
    {
      "code": "002407",
      "name": "多氟多",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 31.89,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 6.12,
      "final_score": 10.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "股权激励",
        "氟化工概念",
        "化工原料",
        "标准普尔",
        "储能概念",
        "新材料",
        "独角兽",
        "富时罗素"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 28.7,
      "target_price": 45.69,
      "risk_reward": 4.33,
      "support": 29.4,
      "resistance": 34.71,
      "factor_actions": []
    },
    {
      "code": "300568",
      "name": "星源材质",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 15.69,
      "close_date": "2026-10-10",
      "close_verified": true,
      "pct_chg": 0.45,
      "final_score": 10.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "股权激励",
        "新材料",
        "小盘股",
        "AH股",
        "富时罗素",
        "锂电池概念",
        "融资融券",
        "电池技术"
      ],
      "enter_date": "2026-10-10",
      "stop_loss": 14.12,
      "target_price": 19.25,
      "risk_reward": 2.27,
      "support": 13.75,
      "resistance": 17.7,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-10 02:36:42",
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
        "n_hit": 1,
        "evidence": "薄样本(9 信号日 / 89 命中)",
        "why": "实测边际 +0.68pp（弱正，命中 89 条 ≈ 43.9% 覆盖率，无选择性）⇒ 不足与强源同权"
      }
    ],
    "evidence_note": "计分依据分级：①「未回测」= 无任何样本外证据（放量弱势）；②「薄样本」= 9 信号日实测边际，样本不足以定权重，故不计分（异常换手率/ROE_TTM/高手跟踪）；③「walk-forward」= ≥4/5 年 OOS 检验通过才给分（候选池层 P5 的 amt60/turntrend，+6/+3）。本层当前**没有任何因子持有第③级证据** ⇒ 除放量弱势外全部为 0 分，属**有意的保守**。　🔴 结论（2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」）：本层唯一记分的「放量弱势 −0.5」有**三重问题** —— ①无回测依据（bottom 榜从未回测）；②设计上不相交（bottom=极端放量股 vs 候选池=缩量强势，实测交集 0 ⇒ 几乎恒不触发）；③上游 _weak 集合曾因 norm_code 未剥点而恒失配（29 轮命中 0 次，本补丁已修）。⇒ **因子在本层的实际计分影响 = 0**，现状等于「全部只做标注」；要让它真正成为加减分项，须先补 walk-forward 回测（流程见下方 ③ 待接入队列 / 明细见本页 🧪 因子审计卡）。",
    "dedup_note": "因子只对**池内已有票**动作（_factor_in_pool 只查不建）⇒ 不产池、不决定谁能进榜"
  },
  "factor_trace": [
    {
      "code": "601899",
      "name": "紫金矿业",
      "final_score": 18.9,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第25／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        },
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第15／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    }
  ]
};