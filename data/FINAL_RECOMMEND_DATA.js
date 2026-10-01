window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-01 12:48:03",
  "crisis_score": 32.9,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-30 07:19:18",
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
      "generated": "2026-09-30 07:19:18",
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
    "date": "2026-09-30",
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
      "code": "301358",
      "name": "湖南裕能",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": 45.51,
      "target_price": 74.88,
      "risk_reward": 4.81,
      "support": 49.44,
      "resistance": 62.1,
      "atr": 1.46,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 10.4,
      "buy_score": 10.4,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "创业成份",
        "中证500",
        "中盘价值",
        "先进制造风格",
        "中盘股",
        "储能概念",
        "MSCI中国",
        "锂电池概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "002636",
      "name": "金安国纪",
      "market": "sz",
      "board": "主板",
      "horizon": "短线",
      "close": 73.18,
      "close_date": "2026-10-01",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 5.43,
      "stop_loss": 68.06,
      "target_price": 83.43,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "atr": 5.97,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.46
      },
      "resonance": 1,
      "strength": 1.46,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 8.8,
      "buy_score": 8.8,
      "enter_date": "2026-10-01",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "标准普尔",
        "富时罗素",
        "昨日高振幅",
        "PCB",
        "小盘股",
        "2026中报预增",
        "小盘成长",
        "医疗器械概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 73.18,
        "latest_price": 73.18,
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
      "code": "300496",
      "name": "中科创达",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 8.2,
      "buy_score": 8.2,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "中证500",
        "富时罗素",
        "AIPC",
        "边缘计算",
        "车联网(车路云)",
        "破增发价股",
        "英伟达概念",
        "AI眼镜"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300001",
      "name": "特锐德",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 8.2,
      "buy_score": 8.2,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "数据中心",
        "高压快充",
        "中证500",
        "富时罗素",
        "新能源车",
        "一带一路",
        "储能概念",
        "雅下水电概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 5,
      "code": "300750",
      "name": "宁德时代",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 358.1,
      "close_date": "2026-10-01",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.5,
      "stop_loss": 322.29,
      "target_price": 429.72,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.68
      },
      "resonance": 1,
      "strength": 1.68,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 8.0,
      "buy_score": 8.0,
      "enter_date": "2026-10-01",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "钠离子电池",
        "富时罗素",
        "百元股",
        "蚂蚁概念",
        "新能源车",
        "行业龙头",
        "锂矿概念",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 358.1,
        "latest_price": 358.1,
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
      "code": "301358",
      "name": "湖南裕能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": 45.51,
      "target_price": 74.88,
      "risk_reward": 4.81,
      "support": 49.44,
      "resistance": 62.1,
      "atr": 1.46,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 10.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "创业成份",
        "中证500",
        "中盘价值",
        "先进制造风格",
        "中盘股",
        "储能概念",
        "MSCI中国",
        "锂电池概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "002636",
      "name": "金安国纪",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 73.18,
      "close_date": "2026-10-01",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 5.43,
      "stop_loss": 68.06,
      "target_price": 83.43,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "atr": 5.97,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.46
      },
      "resonance": 1,
      "strength": 1.46,
      "final_score": 8.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "标准普尔",
        "富时罗素",
        "昨日高振幅",
        "PCB",
        "小盘股",
        "2026中报预增",
        "小盘成长",
        "医疗器械概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 73.18,
        "latest_price": 73.18,
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
      "code": "300496",
      "name": "中科创达",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 8.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "中证500",
        "富时罗素",
        "AIPC",
        "边缘计算",
        "车联网(车路云)",
        "破增发价股",
        "英伟达概念",
        "AI眼镜"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 4,
      "code": "300001",
      "name": "特锐德",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_source": null,
      "close_verified": false,
      "pct_chg": null,
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 8.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "数据中心",
        "高压快充",
        "中证500",
        "富时罗素",
        "新能源车",
        "一带一路",
        "储能概念",
        "雅下水电概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": null,
        "latest_price": null,
        "return_pct": null,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "等待行情数据开始跟踪"
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 5,
      "code": "300750",
      "name": "宁德时代",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 358.1,
      "close_date": "2026-10-01",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.5,
      "stop_loss": 322.29,
      "target_price": 429.72,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.68
      },
      "resonance": 1,
      "strength": 1.68,
      "final_score": 8.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "钠离子电池",
        "富时罗素",
        "百元股",
        "蚂蚁概念",
        "新能源车",
        "行业龙头",
        "锂矿概念",
        "储能概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 358.1,
        "latest_price": 358.1,
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
      "code": "301358",
      "name": "湖南裕能",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 10.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "创业成份",
        "中证500",
        "中盘价值",
        "先进制造风格",
        "中盘股",
        "储能概念",
        "MSCI中国",
        "锂电池概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 45.51,
      "target_price": 74.88,
      "risk_reward": 4.81,
      "support": 49.44,
      "resistance": 62.1,
      "factor_actions": []
    },
    {
      "code": "002636",
      "name": "金安国纪",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 73.18,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 5.43,
      "final_score": 8.8,
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
        "标准普尔",
        "富时罗素",
        "昨日高振幅",
        "PCB",
        "小盘股",
        "2026中报预增",
        "小盘成长",
        "医疗器械概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 68.06,
      "target_price": 83.43,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "factor_actions": []
    },
    {
      "code": "300496",
      "name": "中科创达",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 8.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "中证500",
        "富时罗素",
        "AIPC",
        "边缘计算",
        "车联网(车路云)",
        "破增发价股",
        "英伟达概念",
        "AI眼镜"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "300001",
      "name": "特锐德",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 8.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "数据中心",
        "高压快充",
        "中证500",
        "富时罗素",
        "新能源车",
        "一带一路",
        "储能概念",
        "雅下水电概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "300750",
      "name": "宁德时代",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 358.1,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -1.5,
      "final_score": 8.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "钠离子电池",
        "富时罗素",
        "百元股",
        "蚂蚁概念",
        "新能源车",
        "行业龙头",
        "锂矿概念",
        "储能概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 322.29,
      "target_price": 429.72,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "000725",
      "name": "京东方Ａ",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 5.92,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.34,
      "final_score": 7.0,
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
        "富时罗素",
        "OLED",
        "UWB概念",
        "钙钛矿电池",
        "荣耀概念",
        "裸眼3D",
        "央国企改革",
        "电子竞技"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 5.51,
      "target_price": 6.75,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "601138",
      "name": "工业富联",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 64.04,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.28,
      "final_score": 6.8,
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
        "富时罗素",
        "车联网(车路云)",
        "深圳特区",
        "英伟达概念",
        "独角兽",
        "计算机、通信和其他电子设备制造业",
        "区块链",
        "东方财富热股"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 59.56,
      "target_price": 73.01,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 39.8,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -2.93,
      "final_score": 6.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "数据中心",
        "中证500",
        "富时罗素",
        "QFII重仓",
        "网络安全",
        "新能源车",
        "科技风格",
        "一带一路"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 37.01,
      "target_price": 45.37,
      "risk_reward": 2.0,
      "support": 36.18,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "00762",
      "name": "中国联通",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 5.63,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.72,
      "final_score": 6.3,
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
      "enter_date": "2026-10-01",
      "stop_loss": 5.24,
      "target_price": 6.42,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "00941",
      "name": "中国移动",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 79.5,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.32,
      "final_score": 6.3,
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
      "enter_date": "2026-10-01",
      "stop_loss": 73.94,
      "target_price": 90.63,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "09987",
      "name": "百胜中国",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 349.8,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.74,
      "final_score": 6.3,
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
      "enter_date": "2026-10-01",
      "stop_loss": 325.31,
      "target_price": 398.77,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "03690",
      "name": "美团-W",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 76.65,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -2.85,
      "final_score": 6.3,
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
      "enter_date": "2026-10-01",
      "stop_loss": 71.28,
      "target_price": 87.38,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "601208",
      "name": "东材科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 51.28,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 4.44,
      "final_score": 5.9,
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
        "OLED",
        "燃料电池概念",
        "新能源车",
        "化学原料和化学制品制造业",
        "PCB",
        "电网概念",
        "MLCC",
        "苹果概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 47.69,
      "target_price": 58.46,
      "risk_reward": 2.0,
      "support": 44.76,
      "resistance": 56.78,
      "factor_actions": []
    },
    {
      "code": "000039",
      "name": "中国北大荒",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 5.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "中证500",
        "富时罗素",
        "破净股",
        "天然气",
        "商业航天",
        "深圳特区",
        "可燃冰",
        "2026一季报预减"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 7.7,
      "target_price": 9.78,
      "risk_reward": 1.44,
      "support": 8.48,
      "resistance": 9.66,
      "factor_actions": []
    },
    {
      "code": "01211",
      "name": "比亚迪股份",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 88.25,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 1.2,
      "final_score": 5.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-10-01",
      "stop_loss": 82.07,
      "target_price": 100.6,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002850",
      "name": "科达利",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 5.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "PEEK材料概念",
        "中证500",
        "富时罗素",
        "百元股",
        "深圳特区",
        "新能源车",
        "人形机器人",
        "特斯拉概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600176",
      "name": "中国巨石",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 43.2,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 1.31,
      "final_score": 5.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "industry": "非金属矿物制品业",
      "concepts": [
        "PEEK材料概念",
        "中字头",
        "富时罗素",
        "央国企改革",
        "非金属矿物制品业",
        "东方财富热股",
        "行业龙头",
        "一带一路"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 40.18,
      "target_price": 49.25,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002437",
      "name": "誉衡药业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 4.86,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 9.95,
      "final_score": 4.9,
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
        "创新药",
        "病原体防治",
        "标准普尔",
        "低价股",
        "肝炎概念",
        "2026一季报预增",
        "破发股",
        "深股通"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 4.52,
      "target_price": 5.54,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "600362",
      "name": "江西铜业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 49.01,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.39,
      "final_score": 4.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "缠论买点"
      ],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "富时罗素",
        "央国企改革",
        "稀缺资源",
        "一带一路",
        "大盘价值",
        "大盘股",
        "融资融券",
        "沪股通"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 45.58,
      "target_price": 55.87,
      "risk_reward": 2.0,
      "support": 40.73,
      "resistance": 50.84,
      "factor_actions": []
    },
    {
      "code": "002371",
      "name": "创联控股",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": null,
      "close_date": null,
      "close_verified": false,
      "pct_chg": null,
      "final_score": 4.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "专用设备制造业",
      "concepts": [
        "高带宽内存",
        "OLED",
        "百元股",
        "富时罗素",
        "第三代半导体",
        "央国企改革",
        "专用设备制造业",
        "东方财富热股"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-01 12:48:03",
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