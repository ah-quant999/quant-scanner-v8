window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-14 05:29:30",
  "crisis_score": 32.7,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-13 21:35:31",
    "degraded": false,
    "effective": {
      "jinzuan": 1.824,
      "chan": 1.087,
      "trend": -1.222,
      "jigou": -0.938
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 169,
      "chan": 374,
      "trend": 268,
      "jigou": 469
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-13 21:35:31",
      "hit": 4,
      "n_snapshots": 82,
      "date_range": [
        "2026-06-06",
        "2026-10-13"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-10-13） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-10-13",
    "regime": "grind",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-10-14",
    "source": "CANDIDATE_QUOTES",
    "covered": 19,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "农产品加工",
    "医药商业",
    "小金属",
    "影视院线",
    "文化传媒",
    "港口航运",
    "游戏",
    "白酒",
    "种植业与林业",
    "贵金属",
    "零售"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "300548",
      "name": "长芯博创",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 191.28,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 6.48,
      "stop_loss": 190.08,
      "target_price": 231.02,
      "risk_reward": 33.12,
      "support": 170.33,
      "resistance": 247.8,
      "atr": 16.09,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 16.8,
      "buy_score": 16.8,
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "中证500",
        "创业板综",
        "通信技术",
        "CPO概念",
        "中盘成长",
        "MSCI中国",
        "铜缆高速连接"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 191.28,
        "latest_price": 191.28,
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
      "code": "300394",
      "name": "天孚通信",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 246.7,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 7.48,
      "stop_loss": 235.04,
      "target_price": 267.93,
      "risk_reward": 1.82,
      "support": 217.01,
      "resistance": 292.07,
      "atr": 16.91,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 16.7,
      "buy_score": 16.7,
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "创业板综",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "算力概念"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 246.7,
        "latest_price": 246.7,
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
      "code": "002281",
      "name": "光迅科技",
      "market": "sz",
      "board": "主板",
      "horizon": "短线",
      "close": 145.86,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 4.06,
      "stop_loss": 135.65,
      "target_price": 166.28,
      "risk_reward": 2.0,
      "support": 132.7,
      "resistance": 199.48,
      "atr": 10.62,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 16.3,
      "buy_score": 16.3,
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "中证500",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "标准普尔"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 145.86,
        "latest_price": 145.86,
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
      "code": "688498",
      "name": "源杰科技",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线",
      "close": 1163.0,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 3.64,
      "stop_loss": 1046.7,
      "target_price": 1718.0,
      "risk_reward": 4.77,
      "support": 1053.15,
      "resistance": 1887.0,
      "atr": 114.01,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.83
      },
      "resonance": 1,
      "strength": 1.83,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 16.2,
      "buy_score": 16.2,
      "enter_date": "2026-10-14",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中证500",
        "科技风格",
        "通信技术",
        "上证380",
        "大盘成长",
        "MSCI中国",
        "国产芯片",
        "计算机、通信和其他电子设备制造业"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 1163.0,
        "latest_price": 1163.0,
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
      "code": "601869",
      "name": "长飞光纤",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 370.48,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 2.29,
      "stop_loss": 344.55,
      "target_price": 442.03,
      "risk_reward": 2.76,
      "support": 342.34,
      "resistance": 483.8,
      "atr": 25.34,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 15.0,
      "buy_score": 15.0,
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中证500",
        "超清视频",
        "第三代半导体",
        "科技风格",
        "富时罗素",
        "海工装备",
        "通信技术",
        "上证380"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 370.48,
        "latest_price": 370.48,
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
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 191.28,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 6.48,
      "stop_loss": 190.08,
      "target_price": 231.02,
      "risk_reward": 33.12,
      "support": 170.33,
      "resistance": 247.8,
      "atr": 16.09,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "final_score": 16.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "中证500",
        "创业板综",
        "通信技术",
        "CPO概念",
        "中盘成长",
        "MSCI中国",
        "铜缆高速连接"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 191.28,
        "latest_price": 191.28,
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
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 246.7,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 7.48,
      "stop_loss": 235.04,
      "target_price": 267.93,
      "risk_reward": 1.82,
      "support": 217.01,
      "resistance": 292.07,
      "atr": 16.91,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "final_score": 16.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "创业板综",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "算力概念"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 246.7,
        "latest_price": 246.7,
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
      "code": "002281",
      "name": "光迅科技",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 145.86,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 4.06,
      "stop_loss": 135.65,
      "target_price": 166.28,
      "risk_reward": 2.0,
      "support": 132.7,
      "resistance": 199.48,
      "atr": 10.62,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "final_score": 16.3,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "中证500",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "标准普尔"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 145.86,
        "latest_price": 145.86,
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
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1163.0,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 3.64,
      "stop_loss": 1046.7,
      "target_price": 1718.0,
      "risk_reward": 4.77,
      "support": 1053.15,
      "resistance": 1887.0,
      "atr": 114.01,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.83
      },
      "resonance": 1,
      "strength": 1.83,
      "final_score": 16.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-14",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中证500",
        "科技风格",
        "通信技术",
        "上证380",
        "大盘成长",
        "MSCI中国",
        "国产芯片",
        "计算机、通信和其他电子设备制造业"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 1163.0,
        "latest_price": 1163.0,
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
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 370.48,
      "close_date": "2026-10-14",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 2.29,
      "stop_loss": 344.55,
      "target_price": 442.03,
      "risk_reward": 2.76,
      "support": 342.34,
      "resistance": 483.8,
      "atr": 25.34,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.02
      },
      "resonance": 1,
      "strength": 2.02,
      "final_score": 15.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-14",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中证500",
        "超清视频",
        "第三代半导体",
        "科技风格",
        "富时罗素",
        "海工装备",
        "通信技术",
        "上证380"
      ],
      "tracking": {
        "entry_date": "2026-10-14",
        "entry_price": 370.48,
        "latest_price": 370.48,
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
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 191.28,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 6.48,
      "final_score": 16.8,
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
        "深成500",
        "中证500",
        "创业板综",
        "通信技术",
        "CPO概念",
        "中盘成长",
        "MSCI中国",
        "铜缆高速连接"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 190.08,
      "target_price": 231.02,
      "risk_reward": 33.12,
      "support": 170.33,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 246.7,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 7.48,
      "final_score": 16.7,
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
        "深成500",
        "创业板综",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "算力概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 235.04,
      "target_price": 267.93,
      "risk_reward": 1.82,
      "support": 217.01,
      "resistance": 292.07,
      "factor_actions": []
    },
    {
      "code": "002281",
      "name": "光迅科技",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 145.86,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 4.06,
      "final_score": 16.3,
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
        "深成500",
        "中证500",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念",
        "大盘成长",
        "标准普尔"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 135.65,
      "target_price": 166.28,
      "risk_reward": 2.0,
      "support": 132.7,
      "resistance": 199.48,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1163.0,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 3.64,
      "final_score": 16.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中证500",
        "科技风格",
        "通信技术",
        "上证380",
        "大盘成长",
        "MSCI中国",
        "国产芯片",
        "计算机、通信和其他电子设备制造业"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 1046.7,
      "target_price": 1718.0,
      "risk_reward": 4.77,
      "support": 1053.15,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 370.48,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 2.29,
      "final_score": 15.0,
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
        "中证500",
        "超清视频",
        "第三代半导体",
        "科技风格",
        "富时罗素",
        "海工装备",
        "通信技术",
        "上证380"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 344.55,
      "target_price": 442.03,
      "risk_reward": 2.76,
      "support": 342.34,
      "resistance": 483.8,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 139.75,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 2.83,
      "final_score": 14.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "周期股",
        "PCB",
        "OLED",
        "深成500",
        "科技风格",
        "富时罗素",
        "通信技术",
        "特斯拉概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 129.97,
      "target_price": 196.06,
      "risk_reward": 5.76,
      "support": 130.14,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "688808",
      "name": "联讯仪器",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1332.8,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 4.37,
      "final_score": 14.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 1199.52,
      "target_price": 2471.0,
      "risk_reward": 8.54,
      "support": 1258.19,
      "resistance": 1846.62,
      "factor_actions": []
    },
    {
      "code": "000833",
      "name": "粤桂股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 23.22,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 1.71,
      "final_score": 14.2,
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
        "2026一季报预增",
        "农业种植",
        "2026中报预增",
        "西部大开发",
        "小盘成长",
        "QFII重仓",
        "磷化工",
        "小盘股"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 21.59,
      "target_price": 26.47,
      "risk_reward": 2.0,
      "support": 18.31,
      "resistance": 24.55,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 31.28,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 2.09,
      "final_score": 14.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "可控核聚变",
        "电气机械和器材制造业",
        "超导概念",
        "中证500",
        "科技风格",
        "富时罗素",
        "通信技术",
        "CPO概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 29.09,
      "target_price": 42.53,
      "risk_reward": 5.14,
      "support": 28.92,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 351.3,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 1.06,
      "final_score": 13.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "机构重仓",
        "科技风格",
        "富时罗素",
        "权重股",
        "创业板综",
        "通信技术",
        "CPO概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 316.17,
      "target_price": 435.0,
      "risk_reward": 2.38,
      "support": 329.12,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 228.0,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 2.12,
      "final_score": 13.9,
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
        "深成500",
        "存储芯片",
        "中证500",
        "DeepSeek概念",
        "创业板综",
        "科技风格",
        "AI眼镜",
        "通信技术"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 205.2,
      "target_price": 268.58,
      "risk_reward": 1.78,
      "support": 213.11,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.1,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 4.31,
      "final_score": 13.8,
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
        "长江三角",
        "昨日高振幅",
        "PCB",
        "MSCI中国",
        "上证380",
        "中盘股",
        "中证500",
        "2026中报预增"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 11.93,
      "target_price": 14.62,
      "risk_reward": 14.82,
      "support": 11.04,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "601138",
      "name": "工业富联",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 52.29,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 0.46,
      "final_score": 13.8,
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
        "新型工业化",
        "科技风格",
        "富时罗素",
        "权重股",
        "CPO概念",
        "算力概念",
        "标准普尔"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 48.63,
      "target_price": 59.61,
      "risk_reward": 2.0,
      "support": 49.66,
      "resistance": 66.7,
      "factor_actions": []
    },
    {
      "code": "600176",
      "name": "中国巨石",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 38.46,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 0.42,
      "final_score": 13.0,
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
        "周期股",
        "PCB",
        "DeepSeek概念",
        "富时罗素",
        "标准普尔",
        "PEEK材料概念",
        "MSCI中国",
        "养老金"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 35.77,
      "target_price": 43.84,
      "risk_reward": 2.0,
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
      "close": 251.41,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 5.1,
      "final_score": 12.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "深成500",
        "中证500",
        "机构重仓",
        "科技风格",
        "创业板综",
        "通信技术",
        "CPO概念",
        "中盘成长"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 246.8,
      "target_price": 261.03,
      "risk_reward": 2.09,
      "support": 226.13,
      "resistance": 309.75,
      "factor_actions": []
    },
    {
      "code": "688036",
      "name": "传音控股",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 48.94,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": -0.85,
      "final_score": 12.6,
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
        "MSCI中国",
        "AI手机",
        "大盘股",
        "融资融券",
        "AIPC",
        "上证180",
        "养老金",
        "DeepSeek概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 44.05,
      "target_price": 58.73,
      "risk_reward": 2.0,
      "support": 45.26,
      "resistance": 57.17,
      "factor_actions": []
    },
    {
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 60.16,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 0.28,
      "final_score": 12.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "智能穿戴",
        "存储芯片",
        "科技风格",
        "富时罗素",
        "通信技术",
        "华为海思",
        "CPO概念",
        "IGBT概念"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 55.95,
      "target_price": 69.0,
      "risk_reward": 2.1,
      "support": 57.4,
      "resistance": 74.45,
      "factor_actions": []
    },
    {
      "code": "601899",
      "name": "紫金矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.4,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 0.6,
      "final_score": 12.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "周期股",
        "有色金属矿采选业",
        "贬值受益",
        "机构重仓",
        "富时罗素",
        "权重股",
        "标准普尔",
        "MSCI中国"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 29.37,
      "target_price": 32.46,
      "risk_reward": 2.0,
      "support": 29.01,
      "resistance": 34.53,
      "factor_actions": []
    },
    {
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 21.31,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 6.55,
      "final_score": 11.8,
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
        "标准普尔",
        "周期股",
        "昨日高振幅",
        "MSCI中国",
        "2026中报预增",
        "天然气",
        "大盘股",
        "融资融券"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 19.89,
      "target_price": 24.15,
      "risk_reward": 2.0,
      "support": 18.5,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "300209",
      "name": "行云科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 35.75,
      "close_date": "2026-10-14",
      "close_verified": true,
      "pct_chg": 6.56,
      "final_score": 11.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "零售业",
      "concepts": [
        "互联网服务",
        "跨境电商",
        "国产软件",
        "人工智能",
        "2026中报预增",
        "创业板综",
        "纳米银",
        "内贸流通"
      ],
      "enter_date": "2026-10-14",
      "stop_loss": 34.46,
      "target_price": 38.33,
      "risk_reward": 2.0,
      "support": 29.5,
      "resistance": 38.87,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-14 05:29:30",
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