window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-09-25 03:01:12",
  "crisis_score": 32.8,
  "crisis_high": false,
  "crisis_note": "危机雷达未达高位，逆势龙头暂不并入",
  "total_candidates": 20,
  "top_n": 5,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-09-25 02:23:49",
    "degraded": false,
    "effective": {
      "jinzuan": 1.063,
      "chan": 0.926,
      "trend": -2.083,
      "jigou": -1.156
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 156,
      "chan": 315,
      "trend": 248,
      "jigou": 405
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-09-25 02:23:49",
      "hit": 4,
      "n_snapshots": 71,
      "date_range": [
        "2026-06-06",
        "2026-09-25"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-09-24） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-09-24",
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
    "医疗器械",
    "医疗服务",
    "半导体",
    "厨卫电器",
    "家居用品",
    "小家电",
    "小金属",
    "房地产",
    "生物制品",
    "美容护理",
    "贵金属",
    "通用设备"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "300199",
      "name": "翰宇药业",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.3,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -4.08,
      "stop_loss": 20.97,
      "target_price": 27.7,
      "risk_reward": 1.89,
      "support": 22.26,
      "resistance": 24.44,
      "atr": 0.93,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.24,
        "四量终极": 1.67
      },
      "resonance": 2,
      "strength": 2.91,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 31.1,
      "buy_score": 31.1,
      "enter_date": "2026-09-22",
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分31；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "融资融券",
        "医药医疗风格",
        "深股通",
        "小盘股",
        "小盘成长",
        "合成生物",
        "流感"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 23.3,
        "latest_price": 23.3,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "good",
            "code": "300199",
            "name": "翰宇药业",
            "text": "翰宇药业(300199) 连续 4 日稳居严格共识（高质量）"
          }
        ]
      },
      "action": "买入",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "688498",
      "name": "源杰科技",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线/中线共振",
      "close": 1700.03,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.96,
      "stop_loss": 1530.03,
      "target_price": 1918.0,
      "risk_reward": 1.28,
      "support": 1439.03,
      "resistance": 1887.0,
      "atr": 96.1,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.07,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.57,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "final_score": 26.7,
      "buy_score": 26.7,
      "enter_date": "2026-09-23",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分27；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "融资融券",
        "上证380",
        "通信技术",
        "沪股通",
        "大盘成长",
        "国产芯片",
        "QFII重仓"
      ],
      "tracking": {
        "entry_date": "2026-09-23",
        "entry_price": 1700.03,
        "latest_price": 1700.03,
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
      "code": "300502",
      "name": "新易盛",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 435.0,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -3.59,
      "stop_loss": 391.5,
      "target_price": 579.42,
      "risk_reward": 3.32,
      "support": 378.56,
      "resistance": 475.0,
      "atr": 21.93,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.29
      },
      "resonance": 1,
      "strength": 1.29,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 24.2,
      "buy_score": 24.2,
      "enter_date": "2026-09-25",
      "signals": [
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "CPO概念",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "创业板综",
        "创业成份",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 435.0,
        "latest_price": 435.0,
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
      "code": "688808",
      "name": "联讯仪器",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线",
      "close": 2231.01,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -2.15,
      "stop_loss": 2007.91,
      "target_price": 2733.0,
      "risk_reward": 2.25,
      "support": 2180.0,
      "resistance": 2733.0,
      "atr": 137.05,
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
      "final_score": 23.6,
      "buy_score": 23.6,
      "enter_date": "2026-09-25",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 2231.01,
        "latest_price": 2231.01,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪",
        "alerts": [
          {
            "level": "warn",
            "code": "688808",
            "name": "联讯仪器",
            "text": "联讯仪器(688808) 于 2026-09-23 跌出共识（曾连续 2 日）"
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
      "close": 70.58,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 1.44,
      "stop_loss": 63.52,
      "target_price": 94.36,
      "risk_reward": 3.37,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.17,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.46
      },
      "resonance": 1,
      "strength": 1.46,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "final_score": 22.4,
      "buy_score": 22.4,
      "enter_date": "2026-09-25",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘股",
        "半导体概念",
        "融资融券",
        "电池技术",
        "液冷概念",
        "深股通",
        "氟化工概念",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 70.58,
        "latest_price": 70.58,
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线/中线共振",
      "close": 23.3,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -4.08,
      "stop_loss": 20.97,
      "target_price": 27.7,
      "risk_reward": 1.89,
      "support": 22.26,
      "resistance": 24.44,
      "atr": 0.93,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.24,
        "四量终极": 1.67
      },
      "resonance": 2,
      "strength": 2.91,
      "final_score": 31.1,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-22",
      "signals": [
        "跨策略共振",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分31；四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "融资融券",
        "医药医疗风格",
        "深股通",
        "小盘股",
        "小盘成长",
        "合成生物",
        "流感"
      ],
      "tracking": {
        "entry_date": "2026-09-22",
        "entry_price": 23.3,
        "latest_price": 23.3,
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
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线/中线共振",
      "close": 1700.03,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -1.96,
      "stop_loss": 1530.03,
      "target_price": 1918.0,
      "risk_reward": 1.28,
      "support": 1439.03,
      "resistance": 1887.0,
      "atr": 96.1,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "source_scores": {
        "三重共识": 1.07,
        "四量终极": 1.5
      },
      "resonance": 2,
      "strength": 2.57,
      "final_score": 26.7,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "enter_date": "2026-09-23",
      "signals": [
        "跨策略共振"
      ],
      "_60m_resonance": false,
      "reason": "三重共识 评分27；四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "融资融券",
        "上证380",
        "通信技术",
        "沪股通",
        "大盘成长",
        "国产芯片",
        "QFII重仓"
      ],
      "tracking": {
        "entry_date": "2026-09-23",
        "entry_price": 1700.03,
        "latest_price": 1700.03,
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
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 435.0,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -3.59,
      "stop_loss": 391.5,
      "target_price": 579.42,
      "risk_reward": 3.32,
      "support": 378.56,
      "resistance": 475.0,
      "atr": 21.93,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.29
      },
      "resonance": 1,
      "strength": 1.29,
      "final_score": 24.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-25",
      "signals": [
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "CPO概念",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "创业板综",
        "创业成份",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 435.0,
        "latest_price": 435.0,
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
      "code": "688808",
      "name": "联讯仪器",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 2231.01,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": -2.15,
      "stop_loss": 2007.91,
      "target_price": 2733.0,
      "risk_reward": 2.25,
      "support": 2180.0,
      "resistance": 2733.0,
      "atr": 137.05,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 23.6,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-09-25",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 2231.01,
        "latest_price": 2231.01,
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
      "close": 70.58,
      "close_date": "2026-09-25",
      "close_source": "四量终极",
      "close_verified": true,
      "pct_chg": 1.44,
      "stop_loss": 63.52,
      "target_price": 94.36,
      "risk_reward": 3.37,
      "support": 61.88,
      "resistance": 76.45,
      "atr": 3.17,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.46
      },
      "resonance": 1,
      "strength": 1.46,
      "final_score": 22.4,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 4.36,
          "relative_5d": 4.36,
          "strong": true
        }
      ],
      "enter_date": "2026-09-25",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘股",
        "半导体概念",
        "融资融券",
        "电池技术",
        "液冷概念",
        "深股通",
        "氟化工概念",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-09-25",
        "entry_price": 70.58,
        "latest_price": 70.58,
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 23.3,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -4.08,
      "final_score": 31.1,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "跨策略共振"
      ],
      "industry": "医药制造业",
      "concepts": [
        "新消费",
        "融资融券",
        "医药医疗风格",
        "深股通",
        "小盘股",
        "小盘成长",
        "合成生物",
        "流感"
      ],
      "enter_date": "2026-09-22",
      "stop_loss": 20.97,
      "target_price": 27.7,
      "risk_reward": 1.89,
      "support": 22.26,
      "resistance": 24.44,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "中长线",
      "close": 1700.03,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -1.96,
      "final_score": 26.7,
      "resonance": 2,
      "sources": [
        "三重共识",
        "四量终极"
      ],
      "signals": [
        "跨策略共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "半导体概念",
        "融资融券",
        "上证380",
        "通信技术",
        "沪股通",
        "大盘成长",
        "国产芯片",
        "QFII重仓"
      ],
      "enter_date": "2026-09-23",
      "stop_loss": 1530.03,
      "target_price": 1918.0,
      "risk_reward": 1.28,
      "support": 1439.03,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 435.0,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -3.59,
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
        "CPO概念",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "创业板综",
        "创业成份",
        "富时罗素"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 391.5,
      "target_price": 579.42,
      "risk_reward": 3.32,
      "support": 378.56,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "688808",
      "name": "联讯仪器",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 2231.01,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -2.15,
      "final_score": 23.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "仪器仪表制造业",
      "concepts": [
        "仪器仪表制造业"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 2007.91,
      "target_price": 2733.0,
      "risk_reward": 2.25,
      "support": 2180.0,
      "resistance": 2733.0,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 70.58,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 1.44,
      "final_score": 22.4,
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
        "中盘股",
        "半导体概念",
        "融资融券",
        "电池技术",
        "液冷概念",
        "深股通",
        "氟化工概念",
        "创业板综"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 63.52,
      "target_price": 94.36,
      "risk_reward": 3.37,
      "support": 61.88,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "000807",
      "name": "云铝股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.03,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 5.6,
      "final_score": 21.7,
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
        "电池技术",
        "融资融券",
        "深股通",
        "周期股",
        "富时罗素",
        "燃料电池概念",
        "标准普尔",
        "大盘价值"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 23.43,
      "target_price": 29.13,
      "risk_reward": 1.19,
      "support": 25.96,
      "resistance": 29.13,
      "factor_actions": []
    },
    {
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 35.19,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 1.13,
      "final_score": 21.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红"
      ],
      "industry": "有色金属矿采选业",
      "concepts": [
        "中盘股",
        "电池技术",
        "融资融券",
        "锂矿概念",
        "昨日触板",
        "沪股通",
        "近期新高",
        "上证180"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 31.67,
      "target_price": 43.29,
      "risk_reward": 2.3,
      "support": 34.67,
      "resistance": 41.97,
      "factor_actions": []
    },
    {
      "code": "000737",
      "name": "北方铜业",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 13.96,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 4.84,
      "final_score": 21.1,
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
        "中盘股",
        "稀缺资源",
        "融资融券",
        "深成500",
        "参股券商",
        "深股通",
        "新材料",
        "PCB"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 12.56,
      "target_price": 17.2,
      "risk_reward": 2.32,
      "support": 13.72,
      "resistance": 17.2,
      "factor_actions": []
    },
    {
      "code": "000703",
      "name": "恒逸石化",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.24,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 6.78,
      "final_score": 20.5,
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
        "中盘股",
        "一带一路",
        "融资融券",
        "深股通",
        "新材料",
        "西部大开发",
        "中证500",
        "2026中报预增"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 15.52,
      "target_price": 20.13,
      "risk_reward": 1.68,
      "support": 15.88,
      "resistance": 19.37,
      "factor_actions": []
    },
    {
      "code": "002975",
      "name": "博杰股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 110.9,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 10.0,
      "final_score": 19.3,
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
        "人形机器人",
        "半导体概念",
        "液冷概念",
        "英伟达概念",
        "深股通",
        "5G概念",
        "通信技术",
        "小盘成长"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 99.81,
      "target_price": 130.3,
      "risk_reward": 1.75,
      "support": 92.8,
      "resistance": 117.64,
      "factor_actions": []
    },
    {
      "code": "688183",
      "name": "生益电子",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 114.08,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -4.13,
      "final_score": 18.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "大盘成长",
        "融资融券",
        "华为概念",
        "HS300",
        "AIPC",
        "PCB",
        "上证180",
        "MSCI中国"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 102.67,
      "target_price": 138.47,
      "risk_reward": 2.14,
      "support": 113.38,
      "resistance": 138.47,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 267.93,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -2.71,
      "final_score": 18.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "CPO概念",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "创业板综",
        "创业成份",
        "富时罗素"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 241.14,
      "target_price": 294.5,
      "risk_reward": 0.99,
      "support": 237.3,
      "resistance": 292.07,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 268.58,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 0.21,
      "final_score": 17.4,
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
        "AI智能体",
        "人形机器人",
        "半导体概念",
        "CPO概念",
        "融资融券",
        "英伟达概念",
        "深股通",
        "通信技术"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 241.72,
      "target_price": 309.8,
      "risk_reward": 1.53,
      "support": 244.44,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "000630",
      "name": "铜陵有色",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 5.89,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 0.46,
      "final_score": 16.8,
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
        "电池技术",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "富时罗素",
        "锂电池概念",
        "标准普尔"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 5.3,
      "target_price": 7.0,
      "risk_reward": 1.88,
      "support": 5.88,
      "resistance": 6.9,
      "factor_actions": []
    },
    {
      "code": "600989",
      "name": "宝丰能源",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 22.33,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 2.13,
      "final_score": 16.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势",
        "机构变红",
        "缠论买点"
      ],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "行业龙头",
        "融资融券",
        "氢能源",
        "HS300",
        "西部大开发",
        "周期股",
        "MSCI中国",
        "上证180"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 20.1,
      "target_price": 25.58,
      "risk_reward": 1.46,
      "support": 22.24,
      "resistance": 25.58,
      "factor_actions": []
    },
    {
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 231.02,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -3.34,
      "final_score": 16.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "机构变红"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘股",
        "CPO概念",
        "融资融券",
        "深股通",
        "5G概念",
        "通信技术",
        "创业板综",
        "创业成份"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 207.92,
      "target_price": 247.8,
      "risk_reward": 0.73,
      "support": 191.87,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "000833",
      "name": "粤桂股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 19.05,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 1.71,
      "final_score": 16.2,
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
        "光伏概念",
        "融资融券",
        "乡村振兴",
        "深股通",
        "小盘股",
        "小盘成长",
        "QFII重仓",
        "西部大开发"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 17.14,
      "target_price": 24.84,
      "risk_reward": 3.04,
      "support": 19.03,
      "resistance": 24.55,
      "factor_actions": []
    },
    {
      "code": "000933",
      "name": "神火股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 25.72,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 5.2,
      "final_score": 16.2,
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
        "中盘股",
        "融资融券",
        "深成500",
        "深股通",
        "MSCI中国",
        "富时罗素",
        "2026中报预增",
        "机构重仓"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 23.15,
      "target_price": 29.06,
      "risk_reward": 1.3,
      "support": 25.63,
      "resistance": 29.06,
      "factor_actions": []
    },
    {
      "code": "002747",
      "name": "埃斯顿",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 29.35,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 16.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "通用设备制造业",
      "concepts": [
        "工业互联",
        "人形机器人",
        "AH股",
        "融资融券",
        "工业母机",
        "通用设备制造业",
        "深股通",
        "机器视觉"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 26.42,
      "target_price": 49.0,
      "risk_reward": 6.7,
      "support": 28.2,
      "resistance": 32.34,
      "factor_actions": []
    },
    {
      "code": "688002",
      "name": "睿创微纳",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 178.85,
      "close_date": "2026-09-25",
      "close_verified": true,
      "pct_chg": -2.83,
      "final_score": 15.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "无人机",
        "中盘股",
        "融资融券",
        "上证380",
        "毫米波概念",
        "传感器",
        "富时罗素",
        "卫星互联网"
      ],
      "enter_date": "2026-09-25",
      "stop_loss": 160.97,
      "target_price": 192.78,
      "risk_reward": 0.78,
      "support": 160.0,
      "resistance": 192.78,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-09-25 03:01:12",
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