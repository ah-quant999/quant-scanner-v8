window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-09 04:20:50",
  "crisis_score": 32.8,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-09 02:41:00",
    "degraded": false,
    "effective": {
      "jinzuan": 1.285,
      "chan": 0.811,
      "trend": -1.698,
      "jigou": -1.153
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 169,
      "chan": 354,
      "trend": 254,
      "jigou": 438
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-09 02:41:00",
      "hit": 4,
      "n_snapshots": 78,
      "date_range": [
        "2026-06-06",
        "2026-10-09"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-09-30） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-10-08",
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
    "小家电",
    "小金属",
    "油气开采及服务",
    "港口航运",
    "煤炭开采加工",
    "燃气",
    "电池",
    "贵金属",
    "银行",
    "风电设备",
    "饮料制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "601872",
      "name": "招商轮船",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 22.03,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 9.33,
      "stop_loss": 20.49,
      "target_price": 25.11,
      "risk_reward": 2.0,
      "support": 17.79,
      "resistance": 22.98,
      "atr": 1.36,
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
      "final_score": 16.1,
      "buy_score": 16.1,
      "enter_date": "2026-10-09",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "水上运输业",
      "concepts": [
        "2026中报预增",
        "上证180",
        "MSCI中国",
        "融资融券",
        "周期股",
        "天然气",
        "标准普尔",
        "海洋经济"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 22.03,
        "latest_price": 22.03,
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
      "code": "300450",
      "name": "先导智能",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 37.59,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 7.58,
      "stop_loss": 33.83,
      "target_price": 45.11,
      "risk_reward": 2.0,
      "support": 29.02,
      "resistance": 35.37,
      "atr": 1.29,
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
      "final_score": 12.7,
      "buy_score": 12.7,
      "enter_date": "2026-10-09",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "专用设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "人工智能",
        "AH股",
        "专用设备制造业",
        "新型工业化",
        "深成500",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 37.59,
        "latest_price": 37.59,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "300450",
            "name": "",
            "text": "(300450) 于 2026-10-08 跌出共识（曾连续 1 日）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 3,
      "code": "601899",
      "name": "紫金矿业",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 29.37,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.41,
      "stop_loss": 27.31,
      "target_price": 33.48,
      "risk_reward": 2.0,
      "support": 29.01,
      "resistance": 34.53,
      "atr": 0.96,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.88
      },
      "resonance": 1,
      "strength": 1.88,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -6.79,
          "relative_5d": -6.79,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -9.42,
          "relative_5d": -9.42,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": -6.79,
          "relative_5d": -6.79,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -9.42,
          "relative_5d": -9.42,
          "strong": true
        }
      ],
      "final_score": 12.7,
      "buy_score": 12.7,
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "小金属概念",
        "MSCI中国",
        "上证180",
        "融资融券",
        "稀缺资源",
        "黄金概念",
        "一带一路",
        "反转股"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 29.37,
        "latest_price": 29.37,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "601899",
            "name": "紫金矿业",
            "text": "紫金矿业(601899) 于 2026-09-08 跌出共识（曾连续 1 日）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300438",
      "name": "鹏辉能源",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 49.38,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 0.63,
      "stop_loss": 47.63,
      "target_price": 52.88,
      "risk_reward": 2.0,
      "support": 46.35,
      "resistance": 57.02,
      "atr": 1.73,
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
      "final_score": 12.0,
      "buy_score": 12.0,
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "基金重仓",
        "融资融券",
        "消费电子概念",
        "无线耳机",
        "电气机械和器材制造业",
        "充电桩",
        "石墨烯",
        "深成500"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 49.38,
        "latest_price": 49.38,
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
      "close": 66.85,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 0.5,
      "stop_loss": 65.93,
      "target_price": 68.49,
      "risk_reward": 1.78,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.09,
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
      "final_score": 11.0,
      "buy_score": 11.0,
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "2026一季报预增",
        "计算机、通信和其他电子设备制造业",
        "深成500",
        "电池技术",
        "新能源车",
        "中证500"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 66.85,
        "latest_price": 66.85,
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
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 22.03,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 9.33,
      "stop_loss": 20.49,
      "target_price": 25.11,
      "risk_reward": 2.0,
      "support": 17.79,
      "resistance": 22.98,
      "atr": 1.36,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.44
      },
      "resonance": 1,
      "strength": 1.44,
      "final_score": 16.1,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "水上运输业",
      "concepts": [
        "2026中报预增",
        "上证180",
        "MSCI中国",
        "融资融券",
        "周期股",
        "天然气",
        "标准普尔",
        "海洋经济"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 22.03,
        "latest_price": 22.03,
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
      "code": "300450",
      "name": "先导智能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 37.59,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 7.58,
      "stop_loss": 33.83,
      "target_price": 45.11,
      "risk_reward": 2.0,
      "support": 29.02,
      "resistance": 35.37,
      "atr": 1.29,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.44
      },
      "resonance": 1,
      "strength": 1.44,
      "final_score": 12.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "专用设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "人工智能",
        "AH股",
        "专用设备制造业",
        "新型工业化",
        "深成500",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 37.59,
        "latest_price": 37.59,
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
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 29.37,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.41,
      "stop_loss": 27.31,
      "target_price": 33.48,
      "risk_reward": 2.0,
      "support": 29.01,
      "resistance": 34.53,
      "atr": 0.96,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.88
      },
      "resonance": 1,
      "strength": 1.88,
      "final_score": 12.7,
      "sector_score": 2.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -6.79,
          "relative_5d": -6.79,
          "strong": true
        },
        {
          "name": "贵金属",
          "pct_5d": -9.42,
          "relative_5d": -9.42,
          "strong": true
        }
      ],
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "有色金属矿采选业",
      "concepts": [
        "小金属概念",
        "MSCI中国",
        "上证180",
        "融资融券",
        "稀缺资源",
        "黄金概念",
        "一带一路",
        "反转股"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 29.37,
        "latest_price": 29.37,
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
      "code": "300438",
      "name": "鹏辉能源",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 49.38,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 0.63,
      "stop_loss": 47.63,
      "target_price": 52.88,
      "risk_reward": 2.0,
      "support": 46.35,
      "resistance": 57.02,
      "atr": 1.73,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 12.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "基金重仓",
        "融资融券",
        "消费电子概念",
        "无线耳机",
        "电气机械和器材制造业",
        "充电桩",
        "石墨烯",
        "深成500"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 49.38,
        "latest_price": 49.38,
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
      "close": 66.85,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 0.5,
      "stop_loss": 65.93,
      "target_price": 68.49,
      "risk_reward": 1.78,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.09,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 11.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "2026一季报预增",
        "计算机、通信和其他电子设备制造业",
        "深成500",
        "电池技术",
        "新能源车",
        "中证500"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 66.85,
        "latest_price": 66.85,
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
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 22.03,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 9.33,
      "final_score": 16.1,
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
        "2026中报预增",
        "上证180",
        "MSCI中国",
        "融资融券",
        "周期股",
        "天然气",
        "标准普尔",
        "海洋经济"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 20.49,
      "target_price": 25.11,
      "risk_reward": 2.0,
      "support": 17.79,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "300450",
      "name": "先导智能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 37.59,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 7.58,
      "final_score": 12.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "人工智能",
        "AH股",
        "专用设备制造业",
        "新型工业化",
        "深成500",
        "储能概念"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 33.83,
      "target_price": 45.11,
      "risk_reward": 2.0,
      "support": 29.02,
      "resistance": 35.37,
      "factor_actions": []
    },
    {
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 29.37,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -1.41,
      "final_score": 12.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "小金属概念",
        "MSCI中国",
        "上证180",
        "融资融券",
        "稀缺资源",
        "黄金概念",
        "一带一路",
        "反转股"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 27.31,
      "target_price": 33.48,
      "risk_reward": 2.0,
      "support": 29.01,
      "resistance": 34.53,
      "factor_actions": []
    },
    {
      "code": "300438",
      "name": "鹏辉能源",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 49.38,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.63,
      "final_score": 12.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "基金重仓",
        "融资融券",
        "消费电子概念",
        "无线耳机",
        "电气机械和器材制造业",
        "充电桩",
        "石墨烯",
        "深成500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 47.63,
      "target_price": 52.88,
      "risk_reward": 2.0,
      "support": 46.35,
      "resistance": 57.02,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 66.85,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.5,
      "final_score": 11.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "2026一季报预增",
        "计算机、通信和其他电子设备制造业",
        "深成500",
        "电池技术",
        "新能源车",
        "中证500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 65.93,
      "target_price": 68.49,
      "risk_reward": 1.78,
      "support": 61.88,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "301358",
      "name": "湖南裕能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 51.2,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 1.01,
      "final_score": 11.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "锂电池概念",
        "深成500",
        "储能概念",
        "MSCI中国",
        "融资融券",
        "创业板综",
        "中盘股",
        "中盘价值"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 46.08,
      "target_price": 61.44,
      "risk_reward": 2.0,
      "support": 49.44,
      "resistance": 59.77,
      "factor_actions": []
    },
    {
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 50.47,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 2.81,
      "final_score": 10.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "2026一季报预增",
        "中芯概念",
        "计算机、通信和其他电子设备制造业",
        "深成500",
        "储能概念",
        "反内卷概念"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 49.05,
      "target_price": 53.31,
      "risk_reward": 2.0,
      "support": 47.86,
      "resistance": 61.28,
      "factor_actions": []
    },
    {
      "code": "300073",
      "name": "当升科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 41.28,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 6.17,
      "final_score": 10.2,
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
        "小金属概念",
        "新材料",
        "融资融券",
        "深成500",
        "储能概念",
        "电池技术",
        "新能源车",
        "钠离子电池"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 37.15,
      "target_price": 49.54,
      "risk_reward": 2.0,
      "support": 35.96,
      "resistance": 39.87,
      "factor_actions": []
    },
    {
      "code": "000039",
      "name": "中集集团",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 9.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "MSCI中国",
        "2026一季报预减",
        "融资融券",
        "海洋经济",
        "一带一路",
        "AH股",
        "深成500",
        "参股银行"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 7.74,
      "target_price": 9.78,
      "risk_reward": 1.37,
      "support": 8.48,
      "resistance": 9.66,
      "factor_actions": []
    },
    {
      "code": "000591",
      "name": "太阳能",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 9.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电力、热力生产和供应业",
      "concepts": [
        "小盘价值",
        "融资融券",
        "钙钛矿电池",
        "深成500",
        "储能概念",
        "电力、热力生产和供应业",
        "机器人概念",
        "成渝特区"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 3.75,
      "target_price": 4.64,
      "risk_reward": 1.13,
      "support": 4.11,
      "resistance": 4.44,
      "factor_actions": []
    },
    {
      "code": "600522",
      "name": "中天科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.49,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -2.06,
      "final_score": 9.3,
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
        "特高压",
        "上证180",
        "MSCI中国",
        "新材料",
        "融资融券",
        "央视50",
        "海洋经济",
        "一带一路"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 28.36,
      "target_price": 34.76,
      "risk_reward": 2.0,
      "support": 30.69,
      "resistance": 38.48,
      "factor_actions": []
    },
    {
      "code": "600406",
      "name": "国电南瑞",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 8.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "特高压",
        "上证180",
        "MSCI中国",
        "融资融券",
        "PPP模式",
        "一带一路",
        "车联网(车路云)",
        "沪股通"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 20.27,
      "target_price": 25.19,
      "risk_reward": 1.18,
      "support": 21.65,
      "resistance": 22.77,
      "factor_actions": []
    },
    {
      "code": "300033",
      "name": "同花顺",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 191.3,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -2.92,
      "final_score": 8.2,
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
        "MSCI中国",
        "融资融券",
        "人工智能",
        "互联网金融",
        "ChatGPT概念",
        "证金持股",
        "区块链",
        "深成500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 172.17,
      "target_price": 229.56,
      "risk_reward": 2.0,
      "support": 196.37,
      "resistance": 228.6,
      "factor_actions": []
    },
    {
      "code": "300045",
      "name": "华力创通",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 11.83,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 6.67,
      "final_score": 8.2,
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
        "数字孪生",
        "军民融合",
        "融资融券",
        "虚拟现实",
        "人工智能",
        "小盘成长",
        "创投",
        "富时罗素"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 10.65,
      "target_price": 14.2,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600096",
      "name": "云天化",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 31.91,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 5.17,
      "final_score": 8.1,
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
        "上证180",
        "MSCI中国",
        "融资融券",
        "新材料",
        "一带一路",
        "沪股通",
        "电池技术",
        "碳交易"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 29.68,
      "target_price": 36.38,
      "risk_reward": 2.0,
      "support": 27.06,
      "resistance": 32.0,
      "factor_actions": []
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 18.17,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 7.6,
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
      "enter_date": "2026-10-09",
      "stop_loss": 16.9,
      "target_price": 20.71,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "09866",
      "name": "蔚来-SW",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 28.42,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -0.91,
      "final_score": 7.6,
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
      "enter_date": "2026-10-09",
      "stop_loss": 26.43,
      "target_price": 32.4,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "06862",
      "name": "海底捞",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 9.65,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 1.53,
      "final_score": 7.6,
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
      "enter_date": "2026-10-09",
      "stop_loss": 9.5,
      "target_price": 10.36,
      "risk_reward": 4.73,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "000833",
      "name": "粤桂股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 23.22,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 1.71,
      "final_score": 7.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "缠论买点"
      ],
      "industry": "综合",
      "concepts": [
        "西部大开发",
        "光伏概念",
        "2026中报预增",
        "2025三季报预增",
        "小盘股",
        "融资融券",
        "乡村振兴",
        "2026一季报预增"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 21.59,
      "target_price": 26.47,
      "risk_reward": 2.0,
      "support": 18.31,
      "resistance": 24.55,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 234.8,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -6.51,
      "final_score": 7.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MSCI中国",
        "融资融券",
        "2026一季报预增",
        "车联网(车路云)",
        "人工智能",
        "CPO概念",
        "计算机、通信和其他电子设备制造业",
        "深成500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 211.32,
      "target_price": 281.76,
      "risk_reward": 2.0,
      "support": 242.35,
      "resistance": 278.6,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-09 04:20:50",
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