window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-13 07:41:12",
  "crisis_score": 32.7,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-11 13:01:19",
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
      "generated": "2026-10-11 13:01:19",
      "hit": 4,
      "n_snapshots": 80,
      "date_range": [
        "2026-06-06",
        "2026-10-11"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-10-12） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-10-12",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-10-13",
    "source": "CANDIDATE_QUOTES",
    "covered": 18,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "医药商业",
    "小金属",
    "影视院线",
    "文化传媒",
    "游戏",
    "电池",
    "白酒",
    "贵金属",
    "钢铁",
    "银行",
    "饮料制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "300857",
      "name": "协创数据",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 223.26,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -4.05,
      "stop_loss": 200.93,
      "target_price": 287.16,
      "risk_reward": 2.86,
      "support": 218.9,
      "resistance": 278.6,
      "atr": 12.71,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.92
      },
      "resonance": 1,
      "strength": 1.92,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 11.0,
      "buy_score": 11.0,
      "enter_date": "2026-10-13",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "云计算",
        "半导体概念",
        "AI眼镜",
        "科技风格",
        "人工智能",
        "2026中报预增",
        "车联网(车路云)"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 223.26,
        "latest_price": 223.26,
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
      "code": "600584",
      "name": "长电科技",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 59.99,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -4.38,
      "stop_loss": 53.99,
      "target_price": 106.61,
      "risk_reward": 7.77,
      "support": 58.73,
      "resistance": 74.45,
      "atr": 3.03,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 10.1,
      "buy_score": 10.1,
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "最近多板",
        "生物识别",
        "半导体概念",
        "科技风格",
        "玻璃基板",
        "毫米波概念",
        "2026中报预增",
        "苹果概念"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 59.99,
        "latest_price": 59.99,
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
      "code": "600105",
      "name": "永鼎股份",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 30.64,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -5.64,
      "stop_loss": 27.58,
      "target_price": 49.87,
      "risk_reward": 6.28,
      "support": 30.61,
      "resistance": 47.62,
      "atr": 2.45,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 9.9,
      "buy_score": 9.9,
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "可控核聚变",
        "长江三角",
        "超导概念",
        "电气机械和器材制造业",
        "通信技术"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 30.64,
        "latest_price": 30.64,
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
      "code": "300037",
      "name": "新宙邦",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 60.11,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -7.22,
      "stop_loss": 54.1,
      "target_price": 76.45,
      "risk_reward": 2.72,
      "support": 59.45,
      "resistance": 76.45,
      "atr": 3.19,
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
      "final_score": 9.8,
      "buy_score": 9.8,
      "enter_date": "2026-10-13",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "半导体概念",
        "特斯拉概念",
        "2026中报预增",
        "深圳特区",
        "超级电容",
        "深成500",
        "OLED"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 60.11,
        "latest_price": 60.11,
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
      "code": "300502",
      "name": "新易盛",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 347.6,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -6.1,
      "stop_loss": 312.84,
      "target_price": 579.42,
      "risk_reward": 6.67,
      "support": 347.57,
      "resistance": 475.0,
      "atr": 23.44,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 9.8,
      "buy_score": 9.8,
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "算力概念",
        "大盘成长",
        "通信技术",
        "大盘股"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 347.6,
        "latest_price": 347.6,
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
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 223.26,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -4.05,
      "stop_loss": 200.93,
      "target_price": 287.16,
      "risk_reward": 2.86,
      "support": 218.9,
      "resistance": 278.6,
      "atr": 12.71,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.92
      },
      "resonance": 1,
      "strength": 1.92,
      "final_score": 11.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-13",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "云计算",
        "半导体概念",
        "AI眼镜",
        "科技风格",
        "人工智能",
        "2026中报预增",
        "车联网(车路云)"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 223.26,
        "latest_price": 223.26,
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
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 59.99,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -4.38,
      "stop_loss": 53.99,
      "target_price": 106.61,
      "risk_reward": 7.77,
      "support": 58.73,
      "resistance": 74.45,
      "atr": 3.03,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 10.1,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "最近多板",
        "生物识别",
        "半导体概念",
        "科技风格",
        "玻璃基板",
        "毫米波概念",
        "2026中报预增",
        "苹果概念"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 59.99,
        "latest_price": 59.99,
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
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.64,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -5.64,
      "stop_loss": 27.58,
      "target_price": 49.87,
      "risk_reward": 6.28,
      "support": 30.61,
      "resistance": 47.62,
      "atr": 2.45,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 9.9,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "可控核聚变",
        "长江三角",
        "超导概念",
        "电气机械和器材制造业",
        "通信技术"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 30.64,
        "latest_price": 30.64,
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
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 60.11,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -7.22,
      "stop_loss": 54.1,
      "target_price": 76.45,
      "risk_reward": 2.72,
      "support": 59.45,
      "resistance": 76.45,
      "atr": 3.19,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.65
      },
      "resonance": 1,
      "strength": 1.65,
      "final_score": 9.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-13",
      "signals": [
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "半导体概念",
        "特斯拉概念",
        "2026中报预增",
        "深圳特区",
        "超级电容",
        "深成500",
        "OLED"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 60.11,
        "latest_price": 60.11,
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
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 347.6,
      "close_date": "2026-10-13",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -6.1,
      "stop_loss": 312.84,
      "target_price": 579.42,
      "risk_reward": 6.67,
      "support": 347.57,
      "resistance": 475.0,
      "atr": 23.44,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 9.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-13",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "算力概念",
        "大盘成长",
        "通信技术",
        "大盘股"
      ],
      "tracking": {
        "entry_date": "2026-10-13",
        "entry_price": 347.6,
        "latest_price": 347.6,
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
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 223.26,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -4.05,
      "final_score": 11.0,
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
        "深股通",
        "云计算",
        "半导体概念",
        "AI眼镜",
        "科技风格",
        "人工智能",
        "2026中报预增",
        "车联网(车路云)"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 200.93,
      "target_price": 287.16,
      "risk_reward": 2.86,
      "support": 218.9,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 59.99,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -4.38,
      "final_score": 10.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "最近多板",
        "生物识别",
        "半导体概念",
        "科技风格",
        "玻璃基板",
        "毫米波概念",
        "2026中报预增",
        "苹果概念"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 53.99,
      "target_price": 106.61,
      "risk_reward": 7.77,
      "support": 58.73,
      "resistance": 74.45,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.64,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -5.64,
      "final_score": 9.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "可控核聚变",
        "长江三角",
        "超导概念",
        "电气机械和器材制造业",
        "通信技术"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 27.58,
      "target_price": 49.87,
      "risk_reward": 6.28,
      "support": 30.61,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 60.11,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -7.22,
      "final_score": 9.8,
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
        "半导体概念",
        "特斯拉概念",
        "2026中报预增",
        "深圳特区",
        "超级电容",
        "深成500",
        "OLED"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 54.1,
      "target_price": 76.45,
      "risk_reward": 2.72,
      "support": 59.45,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 347.6,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -6.1,
      "final_score": 9.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "算力概念",
        "大盘成长",
        "通信技术",
        "大盘股"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 312.84,
      "target_price": 579.42,
      "risk_reward": 6.67,
      "support": 347.57,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1122.11,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -6.96,
      "final_score": 9.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "科技风格",
        "基金重仓",
        "2026中报预增",
        "大盘成长",
        "通信技术",
        "大盘股",
        "沪股通"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 1009.9,
      "target_price": 1918.0,
      "risk_reward": 7.09,
      "support": 1122.11,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 362.18,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -6.62,
      "final_score": 9.4,
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
        "科技风格",
        "2026中报预增",
        "超清视频",
        "AH股",
        "大盘成长",
        "通信技术",
        "大盘股",
        "碳化硅"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 325.96,
      "target_price": 483.8,
      "risk_reward": 3.36,
      "support": 362.02,
      "resistance": 483.8,
      "factor_actions": []
    },
    {
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 179.64,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -5.49,
      "final_score": 9.3,
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
        "深股通",
        "基金重仓",
        "2026中报预增",
        "通信技术",
        "F5G概念",
        "华为概念",
        "深成500",
        "中证500"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 161.68,
      "target_price": 247.8,
      "risk_reward": 3.79,
      "support": 179.2,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 229.54,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -2.34,
      "final_score": 9.3,
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
        "深股通",
        "科技风格",
        "算力概念",
        "大盘成长",
        "通信技术",
        "大盘股",
        "深证100R",
        "华为概念"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 206.59,
      "target_price": 294.5,
      "risk_reward": 2.83,
      "support": 223.8,
      "resistance": 292.07,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 11.6,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -2.77,
      "final_score": 9.3,
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
        "沪股通",
        "融资融券",
        "中盘股",
        "光通信模块",
        "华为概念",
        "5G概念",
        "PCB",
        "MSCI中国"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 10.44,
      "target_price": 15.8,
      "risk_reward": 3.62,
      "support": 11.39,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 20.0,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -9.38,
      "final_score": 9.3,
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
        "水上运输业",
        "天然气",
        "沪股通",
        "融资融券",
        "油气资源",
        "大盘股",
        "昨日高振幅",
        "2026中报预增"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 18.0,
      "target_price": 22.98,
      "risk_reward": 1.49,
      "support": 18.5,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "688036",
      "name": "传音控股",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 49.36,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": 0.84,
      "final_score": 9.1,
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
        "沪股通",
        "融资融券",
        "养老金",
        "深圳特区",
        "AI眼镜",
        "DeepSeek概念",
        "AIPC",
        "MSCI中国"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 44.42,
      "target_price": 67.71,
      "risk_reward": 3.72,
      "support": 45.26,
      "resistance": 57.17,
      "factor_actions": []
    },
    {
      "code": "002270",
      "name": "华明装备",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 18.92,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": 0.58,
      "final_score": 9.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "新能源",
        "深股通",
        "光伏概念",
        "融资融券",
        "电网概念",
        "工业母机",
        "小盘股",
        "深成500"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 17.03,
      "target_price": 21.2,
      "risk_reward": 1.21,
      "support": 16.78,
      "resistance": 19.85,
      "factor_actions": []
    },
    {
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.22,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -1.88,
      "final_score": 9.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "2026中报预增",
        "AH股",
        "上证50",
        "证金持股",
        "大盘股",
        "沪股通",
        "小金属概念",
        "有色金属矿采选业"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 27.2,
      "target_price": 35.47,
      "risk_reward": 1.74,
      "support": 29.01,
      "resistance": 34.53,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 135.9,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -6.59,
      "final_score": 8.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "科技风格",
        "基金重仓",
        "特斯拉概念",
        "PCB",
        "2026中报预增",
        "LED概念",
        "苹果概念"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 122.31,
      "target_price": 280.08,
      "risk_reward": 10.61,
      "support": 135.15,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "600176",
      "name": "中国巨石",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 38.3,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -0.7,
      "final_score": 8.7,
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
        "PCB",
        "2026中报预增",
        "大盘股",
        "沪股通",
        "风能",
        "养老金",
        "新材料",
        "非金属矿物制品业"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 34.47,
      "target_price": 56.0,
      "risk_reward": 4.62,
      "support": 36.01,
      "resistance": 51.68,
      "factor_actions": []
    },
    {
      "code": "300620",
      "name": "光库科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 239.21,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -3.08,
      "final_score": 8.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深股通",
        "科技风格",
        "2026中报预增",
        "通信技术",
        "激光雷达",
        "深成500",
        "卫星互联网",
        "中证500"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 215.29,
      "target_price": 333.54,
      "risk_reward": 3.94,
      "support": 236.82,
      "resistance": 309.75,
      "factor_actions": []
    },
    {
      "code": "600030",
      "name": "中信证券",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.06,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": 0.58,
      "final_score": 8.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "资本市场服务",
      "concepts": [
        "2026中报预增",
        "AH股",
        "上证50",
        "证金持股",
        "深圳特区",
        "大盘股",
        "沪股通",
        "参股银行"
      ],
      "enter_date": "2026-10-13",
      "stop_loss": 23.45,
      "target_price": 28.83,
      "risk_reward": 1.06,
      "support": 25.3,
      "resistance": 28.13,
      "factor_actions": []
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 18.17,
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 8.2,
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
      "enter_date": "2026-10-13",
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
      "close_date": "2026-10-13",
      "close_verified": true,
      "pct_chg": -0.91,
      "final_score": 8.2,
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
      "enter_date": "2026-10-13",
      "stop_loss": 26.43,
      "target_price": 32.4,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-13 07:41:12",
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