window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-09 04:06:05",
  "crisis_score": 32.8,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 18,
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
    "total": 18,
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
      "stop_loss": 19.83,
      "target_price": 22.98,
      "risk_reward": 0.43,
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
      "final_score": 17.4,
      "buy_score": 17.4,
      "enter_date": "2026-10-09",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "水上运输业",
      "concepts": [
        "沪股通",
        "水上运输业",
        "天然气",
        "一带一路",
        "标准普尔",
        "2026中报预增",
        "周期股",
        "央国企改革"
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
      "target_price": 37.77,
      "risk_reward": 0.05,
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
      "final_score": 15.2,
      "buy_score": 15.2,
      "enter_date": "2026-10-09",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "专用设备制造业",
      "concepts": [
        "光伏概念",
        "固态电池",
        "先进制造风格",
        "储能概念",
        "HS300",
        "富时罗素",
        "燃料电池概念",
        "人工智能"
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
      "stop_loss": 44.44,
      "target_price": 72.2,
      "risk_reward": 4.62,
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
      "final_score": 14.5,
      "buy_score": 14.5,
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "虚拟电厂",
        "电子烟",
        "固态电池",
        "电网概念",
        "昨日高振幅",
        "储能概念",
        "富时罗素",
        "燃料电池概念"
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
      "rank": 4,
      "code": "300390",
      "name": "天华新能",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 50.47,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 2.81,
      "stop_loss": 45.42,
      "target_price": 79.0,
      "risk_reward": 5.65,
      "support": 47.86,
      "resistance": 61.28,
      "atr": 2.01,
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
      "final_score": 13.1,
      "buy_score": 13.1,
      "enter_date": "2026-10-09",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "固态电池",
        "先进制造风格",
        "锂矿概念",
        "储能概念",
        "富时罗素",
        "2026中报扭亏",
        "深股通",
        "中盘价值"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 50.47,
        "latest_price": 50.47,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "300390",
            "name": "天华新能",
            "text": "天华新能(300390) 于 2026-09-30 跌出共识（曾连续 1 日）"
          }
        ]
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
      "stop_loss": 60.16,
      "target_price": 82.48,
      "risk_reward": 2.34,
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
        "固态电池",
        "先进制造风格",
        "富时罗素",
        "深股通",
        "中证500",
        "超级电容",
        "2026中报预增",
        "中盘股"
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
      "stop_loss": 19.83,
      "target_price": 22.98,
      "risk_reward": 0.43,
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
      "final_score": 17.4,
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
        "沪股通",
        "水上运输业",
        "天然气",
        "一带一路",
        "标准普尔",
        "2026中报预增",
        "周期股",
        "央国企改革"
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
      "target_price": 37.77,
      "risk_reward": 0.05,
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
      "final_score": 15.2,
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
        "光伏概念",
        "固态电池",
        "先进制造风格",
        "储能概念",
        "HS300",
        "富时罗素",
        "燃料电池概念",
        "人工智能"
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
      "stop_loss": 44.44,
      "target_price": 72.2,
      "risk_reward": 4.62,
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
      "final_score": 14.5,
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
        "虚拟电厂",
        "电子烟",
        "固态电池",
        "电网概念",
        "昨日高振幅",
        "储能概念",
        "富时罗素",
        "燃料电池概念"
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
      "rank": 4,
      "code": "300390",
      "name": "天华新能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 50.47,
      "close_date": "2026-10-09",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 2.81,
      "stop_loss": 45.42,
      "target_price": 79.0,
      "risk_reward": 5.65,
      "support": 47.86,
      "resistance": 61.28,
      "atr": 2.01,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 13.1,
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
        "固态电池",
        "先进制造风格",
        "锂矿概念",
        "储能概念",
        "富时罗素",
        "2026中报扭亏",
        "深股通",
        "中盘价值"
      ],
      "tracking": {
        "entry_date": "2026-10-09",
        "entry_price": 50.47,
        "latest_price": 50.47,
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
      "stop_loss": 60.16,
      "target_price": 82.48,
      "risk_reward": 2.34,
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
        "固态电池",
        "先进制造风格",
        "富时罗素",
        "深股通",
        "中证500",
        "超级电容",
        "2026中报预增",
        "中盘股"
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
      "final_score": 17.4,
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
        "沪股通",
        "水上运输业",
        "天然气",
        "一带一路",
        "标准普尔",
        "2026中报预增",
        "周期股",
        "央国企改革"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 19.83,
      "target_price": 22.98,
      "risk_reward": 0.43,
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
      "final_score": 15.2,
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
        "光伏概念",
        "固态电池",
        "先进制造风格",
        "储能概念",
        "HS300",
        "富时罗素",
        "燃料电池概念",
        "人工智能"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 33.83,
      "target_price": 37.77,
      "risk_reward": 0.05,
      "support": 29.02,
      "resistance": 35.37,
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
      "final_score": 14.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "虚拟电厂",
        "电子烟",
        "固态电池",
        "电网概念",
        "昨日高振幅",
        "储能概念",
        "富时罗素",
        "燃料电池概念"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 44.44,
      "target_price": 72.2,
      "risk_reward": 4.62,
      "support": 46.35,
      "resistance": 57.02,
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
      "final_score": 13.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "固态电池",
        "先进制造风格",
        "锂矿概念",
        "储能概念",
        "富时罗素",
        "2026中报扭亏",
        "深股通",
        "中盘价值"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 45.42,
      "target_price": 79.0,
      "risk_reward": 5.65,
      "support": 47.86,
      "resistance": 61.28,
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
        "固态电池",
        "先进制造风格",
        "富时罗素",
        "深股通",
        "中证500",
        "超级电容",
        "2026中报预增",
        "中盘股"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 60.16,
      "target_price": 82.48,
      "risk_reward": 2.34,
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
        "中盘价值",
        "动力电池回收",
        "计算机、通信和其他电子设备制造业",
        "磷化工",
        "中证500",
        "固态电池",
        "创业板综",
        "先进制造风格"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 46.08,
      "target_price": 74.2,
      "risk_reward": 4.49,
      "support": 49.44,
      "resistance": 59.77,
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
      "final_score": 10.9,
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
        "固态电池",
        "储能概念",
        "富时罗素",
        "深股通",
        "参股新三板",
        "中盘价值",
        "中证500",
        "苹果概念"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 37.15,
      "target_price": 45.09,
      "risk_reward": 0.92,
      "support": 35.96,
      "resistance": 39.87,
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
      "final_score": 10.7,
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
        "虚拟机器人",
        "HS300",
        "富时罗素",
        "人工智能",
        "大数据",
        "深股通",
        "行业龙头",
        "国产软件"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 172.17,
      "target_price": 245.48,
      "risk_reward": 2.83,
      "support": 196.37,
      "resistance": 228.6,
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
      "final_score": 10.6,
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
        "碳纤维",
        "参股券商",
        "光伏概念",
        "华为概念",
        "固态电池",
        "铁路基建",
        "电网概念",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 27.44,
      "target_price": 49.52,
      "risk_reward": 6.24,
      "support": 30.69,
      "resistance": 38.48,
      "factor_actions": []
    },
    {
      "code": "301487",
      "name": "盟固利",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 17.45,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 1.69,
      "final_score": 10.4,
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
        "动力电池回收",
        "化学原料和化学制品制造业",
        "机构重仓",
        "固态电池",
        "创业板综",
        "人形机器人",
        "电池技术",
        "专精特新"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 15.71,
      "target_price": 18.18,
      "risk_reward": 0.42,
      "support": 14.58,
      "resistance": 17.89,
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
      "final_score": 10.2,
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
        "贬值受益",
        "锂矿概念",
        "昨日高振幅",
        "HS300",
        "富时罗素",
        "有色金属矿采选业",
        "稀缺资源",
        "行业龙头"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 26.43,
      "target_price": 35.47,
      "risk_reward": 2.08,
      "support": 29.01,
      "resistance": 34.53,
      "factor_actions": []
    },
    {
      "code": "000039",
      "name": "中集集团",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 8.68,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 9.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "2026一季报预减",
        "参股券商",
        "先进制造风格",
        "装配建筑",
        "富时罗素",
        "风能",
        "破净股",
        "深股通"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 7.81,
      "target_price": 9.78,
      "risk_reward": 1.27,
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
      "close": 4.18,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 9.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电力、热力生产和供应业",
      "concepts": [
        "破增发价股",
        "光伏概念",
        "储能概念",
        "西部大开发",
        "富时罗素",
        "破净股",
        "深股通",
        "中证500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 3.76,
      "target_price": 4.64,
      "risk_reward": 1.1,
      "support": 4.11,
      "resistance": 4.44,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.65,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -4.17,
      "final_score": 9.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "光通信模块",
        "通信技术",
        "中证500",
        "计算机、通信和其他电子设备制造业",
        "长江三角",
        "沪股通",
        "中盘成长",
        "5G概念"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 11.38,
      "target_price": 15.8,
      "risk_reward": 2.49,
      "support": 11.9,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 33.56,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -7.45,
      "final_score": 9.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "网络安全",
        "磁悬浮概念",
        "昨日高振幅",
        "富时罗素",
        "专精特新",
        "风能",
        "大数据",
        "一带一路"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 30.2,
      "target_price": 53.33,
      "risk_reward": 5.89,
      "support": 36.12,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "600406",
      "name": "国电南瑞",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 22.86,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 8.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "软件和信息技术服务业",
        "虚拟电厂",
        "光伏概念",
        "抽水蓄能",
        "先进制造风格",
        "电网概念",
        "储能概念",
        "HS300"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 20.57,
      "target_price": 25.19,
      "risk_reward": 1.02,
      "support": 21.65,
      "resistance": 22.77,
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
      "final_score": 8.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "DeepSeek概念",
        "昨日高振幅",
        "网络游戏",
        "人工智能",
        "大数据",
        "深股通",
        "阿里概念",
        "中证500"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 211.32,
      "target_price": 309.65,
      "risk_reward": 3.19,
      "support": 242.35,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "300620",
      "name": "光库科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 250.95,
      "close_date": "2026-10-09",
      "close_verified": true,
      "pct_chg": -7.22,
      "final_score": 8.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "中证500",
        "中盘成长",
        "2026中报预增",
        "股权激励",
        "中盘股",
        "激光雷达",
        "机构重仓"
      ],
      "enter_date": "2026-10-09",
      "stop_loss": 225.85,
      "target_price": 333.54,
      "risk_reward": 3.29,
      "support": 251.2,
      "resistance": 309.75,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-09 04:06:05",
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