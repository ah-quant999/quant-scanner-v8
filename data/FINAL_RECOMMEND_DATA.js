window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-01 13:08:27",
  "crisis_score": 32.9,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-30 23:18:21",
    "degraded": false,
    "effective": {
      "jinzuan": 1.156,
      "chan": 0.83,
      "trend": -1.816,
      "jigou": -1.087
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 168,
      "chan": 344,
      "trend": 251,
      "jigou": 424
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-09-30 23:18:21",
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
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-09-30） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-09-30",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "price_source": {
    "date": "2026-10-01",
    "source": "STOCK_QUOTE",
    "covered": 20,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "医疗服务",
    "厨卫电器",
    "小家电",
    "小金属",
    "房地产",
    "汽车整车",
    "生物制品",
    "贵金属",
    "银行",
    "风电设备",
    "饮料制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "301358",
      "name": "湖南裕能",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 50.69,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.24,
      "stop_loss": 45.62,
      "target_price": 60.83,
      "risk_reward": 2.0,
      "support": 49.44,
      "resistance": 59.77,
      "atr": 1.48,
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
      "final_score": 7.9,
      "buy_score": 7.9,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘价值",
        "计算机、通信和其他电子设备制造业",
        "储能概念",
        "深股通",
        "动力电池回收",
        "电池技术",
        "MSCI中国",
        "锂电池概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 50.69,
        "latest_price": 50.69,
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
      "code": "300496",
      "name": "中科创达",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 52.9,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.64,
      "stop_loss": 47.61,
      "target_price": 63.48,
      "risk_reward": 2.0,
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
      "final_score": 7.5,
      "buy_score": 7.5,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "AI智能体",
        "通信技术",
        "MSCI中国",
        "软件和信息技术服务业",
        "国产软件",
        "元宇宙概念",
        "无人机",
        "创业成份"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 52.9,
        "latest_price": 52.9,
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
      "code": "002636",
      "name": "金安国纪",
      "market": "sz",
      "board": "主板",
      "horizon": "短线",
      "close": 79.45,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.31,
      "stop_loss": 73.89,
      "target_price": 90.57,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "atr": 6.05,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.45
      },
      "resonance": 1,
      "strength": 1.45,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 5.6,
      "buy_score": 5.6,
      "enter_date": "2026-10-01",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "PCB",
        "计算机、通信和其他电子设备制造业",
        "标准普尔",
        "2026中报预增",
        "昨日高振幅",
        "深股通",
        "医疗器械概念",
        "小盘成长"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 79.45,
        "latest_price": 79.45,
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
      "code": "300001",
      "name": "特锐德",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 34.48,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.53,
      "stop_loss": 31.03,
      "target_price": 41.38,
      "risk_reward": 2.0,
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
      "final_score": 5.6,
      "buy_score": 5.6,
      "enter_date": "2026-10-01",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "数据中心",
        "新能源车",
        "MSCI中国",
        "一带一路",
        "创业成份",
        "电网概念",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 34.48,
        "latest_price": 34.48,
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
      "code": "601138",
      "name": "工业富联",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 58.2,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.38,
      "stop_loss": 54.13,
      "target_price": 66.35,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.45
      },
      "resonance": 1,
      "strength": 1.45,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 5.5,
      "buy_score": 5.5,
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
        "MSCI中国",
        "沪股通",
        "深圳特区",
        "物联网",
        "HS300",
        "英伟达概念",
        "行业龙头"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 58.2,
        "latest_price": 58.2,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "601138",
            "name": "",
            "text": "(601138) 于 2026-08-30 跌出共识（曾连续 1 日）"
          }
        ]
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
      "close": 50.69,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.24,
      "stop_loss": 45.62,
      "target_price": 60.83,
      "risk_reward": 2.0,
      "support": 49.44,
      "resistance": 59.77,
      "atr": 1.48,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 7.9,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘价值",
        "计算机、通信和其他电子设备制造业",
        "储能概念",
        "深股通",
        "动力电池回收",
        "电池技术",
        "MSCI中国",
        "锂电池概念"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 50.69,
        "latest_price": 50.69,
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
      "code": "300496",
      "name": "中科创达",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 52.9,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.64,
      "stop_loss": 47.61,
      "target_price": 63.48,
      "risk_reward": 2.0,
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
      "final_score": 7.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "软件和信息技术服务业",
      "concepts": [
        "AI智能体",
        "通信技术",
        "MSCI中国",
        "软件和信息技术服务业",
        "国产软件",
        "元宇宙概念",
        "无人机",
        "创业成份"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 52.9,
        "latest_price": 52.9,
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
      "code": "002636",
      "name": "金安国纪",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 79.45,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.31,
      "stop_loss": 73.89,
      "target_price": 90.57,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "atr": 6.05,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.45
      },
      "resonance": 1,
      "strength": 1.45,
      "final_score": 5.6,
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
        "PCB",
        "计算机、通信和其他电子设备制造业",
        "标准普尔",
        "2026中报预增",
        "昨日高振幅",
        "深股通",
        "医疗器械概念",
        "小盘成长"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 79.45,
        "latest_price": 79.45,
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
      "code": "300001",
      "name": "特锐德",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 34.48,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.53,
      "stop_loss": 31.03,
      "target_price": 41.38,
      "risk_reward": 2.0,
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
      "final_score": 5.6,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-01",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "数据中心",
        "新能源车",
        "MSCI中国",
        "一带一路",
        "创业成份",
        "电网概念",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 34.48,
        "latest_price": 34.48,
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
      "code": "601138",
      "name": "工业富联",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 58.2,
      "close_date": "2026-10-01",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -0.38,
      "stop_loss": 54.13,
      "target_price": 66.35,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.45
      },
      "resonance": 1,
      "strength": 1.45,
      "final_score": 5.5,
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
        "MSCI中国",
        "沪股通",
        "深圳特区",
        "物联网",
        "HS300",
        "英伟达概念",
        "行业龙头"
      ],
      "tracking": {
        "entry_date": "2026-10-01",
        "entry_price": 58.2,
        "latest_price": 58.2,
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
      "close": 50.69,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.24,
      "final_score": 7.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘价值",
        "计算机、通信和其他电子设备制造业",
        "储能概念",
        "深股通",
        "动力电池回收",
        "电池技术",
        "MSCI中国",
        "锂电池概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 45.62,
      "target_price": 60.83,
      "risk_reward": 2.0,
      "support": 49.44,
      "resistance": 59.77,
      "factor_actions": []
    },
    {
      "code": "300496",
      "name": "中科创达",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 52.9,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.64,
      "final_score": 7.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "AI智能体",
        "通信技术",
        "MSCI中国",
        "软件和信息技术服务业",
        "国产软件",
        "元宇宙概念",
        "无人机",
        "创业成份"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 47.61,
      "target_price": 63.48,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002636",
      "name": "金安国纪",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 79.45,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -4.31,
      "final_score": 5.6,
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
        "PCB",
        "计算机、通信和其他电子设备制造业",
        "标准普尔",
        "2026中报预增",
        "昨日高振幅",
        "深股通",
        "医疗器械概念",
        "小盘成长"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 73.89,
      "target_price": 90.57,
      "risk_reward": 2.0,
      "support": 63.8,
      "resistance": 92.0,
      "factor_actions": []
    },
    {
      "code": "300001",
      "name": "特锐德",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 34.48,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.53,
      "final_score": 5.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "数据中心",
        "新能源车",
        "MSCI中国",
        "一带一路",
        "创业成份",
        "电网概念",
        "创业板综"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 31.03,
      "target_price": 41.38,
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
      "close": 58.2,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.38,
      "final_score": 5.5,
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
        "MSCI中国",
        "沪股通",
        "深圳特区",
        "物联网",
        "HS300",
        "英伟达概念",
        "行业龙头"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 54.13,
      "target_price": 66.35,
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
      "close": 155.8,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -1.5,
      "final_score": 5.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "新能源车",
        "电池技术",
        "MSCI中国",
        "PEEK材料概念",
        "百元股",
        "深圳特区",
        "先进制造风格",
        "锂电池概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 144.89,
      "target_price": 177.61,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "00762",
      "name": "中国联通",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 5.54,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 4.4,
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
      "close": 79.35,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 4.4,
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
      "close": 321.2,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 4.4,
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
      "close": 70.45,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 4.4,
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
      "code": "600176",
      "name": "中国巨石",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 39.41,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.7,
      "final_score": 4.2,
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
        "标准普尔",
        "MSCI中国",
        "一带一路",
        "PEEK材料概念",
        "沪股通",
        "央国企改革",
        "PCB",
        "周期股"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 36.65,
      "target_price": 44.93,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "000039",
      "name": "中集集团",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 8.6,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.58,
      "final_score": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "金属制品业",
      "concepts": [
        "雄安新区",
        "标准普尔",
        "参股银行",
        "破净股",
        "MSCI中国",
        "装配建筑",
        "一带一路",
        "可燃冰"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 8.0,
      "target_price": 9.8,
      "risk_reward": 2.0,
      "support": 8.48,
      "resistance": 9.66,
      "factor_actions": []
    },
    {
      "code": "000725",
      "name": "京东方Ａ",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 5.72,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.17,
      "final_score": 3.8,
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
        "MicroLED",
        "标准普尔",
        "显示技术",
        "MSCI中国",
        "央国企改革",
        "医美概念",
        "国产芯片",
        "荣耀概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 5.32,
      "target_price": 6.52,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002532",
      "name": "天山铝业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.18,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -0.25,
      "final_score": 3.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "有色金属冶炼和压延加工业",
      "concepts": [
        "储能概念",
        "2026一季报预增",
        "2026中报预增",
        "深股通",
        "HS300",
        "锂电池概念",
        "钠离子电池",
        "MSCI中国"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 11.33,
      "target_price": 13.89,
      "risk_reward": 2.0,
      "support": 11.59,
      "resistance": 14.18,
      "factor_actions": []
    },
    {
      "code": "300750",
      "name": "宁德时代",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 291.11,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 1.5,
      "final_score": 2.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "储能概念",
        "茅指数",
        "动力电池回收",
        "新能源车",
        "电池技术",
        "MSCI中国",
        "百元股",
        "创业成份"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 262.0,
      "target_price": 358.1,
      "risk_reward": 2.3,
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
      "close": 48.22,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -4.57,
      "final_score": 2.7,
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
        "通信技术",
        "特高压",
        "新能源车",
        "电池技术",
        "沪股通",
        "MLCC",
        "电网概念",
        "6G概念"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 44.84,
      "target_price": 54.97,
      "risk_reward": 2.0,
      "support": 44.76,
      "resistance": 56.78,
      "factor_actions": []
    },
    {
      "code": "09988",
      "name": "阿里巴巴-W",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 106.2,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 2.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "",
      "concepts": [],
      "enter_date": "2026-10-01",
      "stop_loss": 102.67,
      "target_price": 125.86,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "01211",
      "name": "比亚迪股份",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 75.75,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 2.5,
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
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 36.26,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": -2.0,
      "final_score": 2.4,
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
        "通信技术",
        "标准普尔",
        "数据中心",
        "新能源车",
        "MSCI中国",
        "一带一路",
        "长江三角",
        "沪股通"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 33.72,
      "target_price": 41.34,
      "risk_reward": 2.0,
      "support": 36.12,
      "resistance": 47.62,
      "factor_actions": []
    },
    {
      "code": "600362",
      "name": "江西铜业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 41.8,
      "close_date": "2026-10-01",
      "close_verified": true,
      "pct_chg": 0.14,
      "final_score": 1.9,
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
        "标准普尔",
        "参股银行",
        "小金属概念",
        "电池技术",
        "MSCI中国",
        "有色金属冶炼和压延加工业",
        "一带一路",
        "机构重仓"
      ],
      "enter_date": "2026-10-01",
      "stop_loss": 38.87,
      "target_price": 49.01,
      "risk_reward": 2.46,
      "support": 40.73,
      "resistance": 50.84,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-01 13:08:26",
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