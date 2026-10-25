window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-25 15:40:03",
  "crisis_score": 33.7,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 20,
  "top_n": 3,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-25 09:18:31",
    "degraded": false,
    "effective": {
      "jinzuan": 0.726,
      "chan": 0.883,
      "trend": -0.478,
      "jigou": -0.308
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 243,
      "chan": 460,
      "trend": 281,
      "jigou": 498
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-25 09:18:31",
      "hit": 4,
      "n_snapshots": 94,
      "date_range": [
        "2026-06-06",
        "2026-10-25"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-10-23",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-10-23",
    "pool_total": 0,
    "new_selected": 0,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-10-23",
    "source": "STOCK_QUOTE",
    "covered": 20,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "IT服务",
    "其他电子",
    "半导体",
    "小金属",
    "工程机械",
    "消费电子",
    "电机",
    "自动化设备",
    "贵金属",
    "软件开发",
    "通用设备",
    "黑色家电"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "002138",
      "name": "顺络电子",
      "market": "sz",
      "board": "主板",
      "horizon": "短线",
      "close": 42.18,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.83,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 37.96,
      "target_price": 55.86,
      "risk_reward": 3.24,
      "support": 38.0,
      "resistance": 55.86,
      "atr": 2.72,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.6
      },
      "resonance": 1,
      "strength": 1.6,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 36.8,
      "mix_pct": 100.0,
      "buy_score": 36.8,
      "enter_date": "2026-10-25",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "PCB",
        "小米概念",
        "富时罗素",
        "MSCI中国",
        "中证500",
        "标准普尔",
        "消费电子概念",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 42.18,
        "latest_price": 42.18,
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 25.8,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 4.71,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 23.22,
      "target_price": 27.7,
      "risk_reward": 0.74,
      "support": 22.06,
      "resistance": 27.7,
      "atr": 1.54,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.41
      },
      "resonance": 1,
      "strength": 1.41,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 29.2,
      "mix_pct": 67.5,
      "buy_score": 29.2,
      "enter_date": "2026-10-25",
      "signals": [
        "上涨趋势"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "合成生物",
        "小盘成长",
        "融资融券",
        "工业大麻",
        "2026中报预增",
        "AI制药（医疗）",
        "流感",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 25.8,
        "latest_price": 25.8,
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
      "code": "603186",
      "name": "华正新材",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 201.65,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 6.19,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 181.49,
      "target_price": 264.0,
      "risk_reward": 3.09,
      "support": 169.75,
      "resistance": 242.8,
      "atr": 18.31,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 2.95,
          "relative_5d": 2.95,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "半导体",
          "pct_5d": 2.95,
          "relative_5d": 2.95,
          "strong": true
        }
      ],
      "final_score": 28.0,
      "mix_pct": 62.4,
      "buy_score": 28.0,
      "enter_date": "2026-10-25",
      "signals": [
        "四量终极共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "电池技术",
        "锂电池概念",
        "固态电池",
        "计算机、通信和其他电子设备制造业",
        "PCB",
        "2026中报预增",
        "冷链物流",
        "半导体概念"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 201.65,
        "latest_price": 201.65,
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
      "code": "002138",
      "name": "顺络电子",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 42.18,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.83,
      "stop_loss": 37.96,
      "target_price": 55.86,
      "risk_reward": 3.24,
      "support": 38.0,
      "resistance": 55.86,
      "atr": 2.72,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.6
      },
      "resonance": 1,
      "strength": 1.6,
      "final_score": 36.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-25",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "PCB",
        "小米概念",
        "富时罗素",
        "MSCI中国",
        "中证500",
        "标准普尔",
        "消费电子概念",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 42.18,
        "latest_price": 42.18,
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
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 25.8,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 4.71,
      "stop_loss": 23.22,
      "target_price": 27.7,
      "risk_reward": 0.74,
      "support": 22.06,
      "resistance": 27.7,
      "atr": 1.54,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.41
      },
      "resonance": 1,
      "strength": 1.41,
      "final_score": 29.2,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-25",
      "signals": [
        "上涨趋势"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号1项",
      "industry": "医药制造业",
      "concepts": [
        "合成生物",
        "小盘成长",
        "融资融券",
        "工业大麻",
        "2026中报预增",
        "AI制药（医疗）",
        "流感",
        "创业板综"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 25.8,
        "latest_price": 25.8,
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
      "code": "603186",
      "name": "华正新材",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 201.65,
      "close_date": "2026-10-23",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 6.19,
      "stop_loss": 181.49,
      "target_price": 264.0,
      "risk_reward": 3.09,
      "support": 169.75,
      "resistance": 242.8,
      "atr": 18.31,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.5
      },
      "resonance": 1,
      "strength": 1.5,
      "final_score": 28.0,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "半导体",
          "pct_5d": 2.95,
          "relative_5d": 2.95,
          "strong": true
        }
      ],
      "enter_date": "2026-10-25",
      "signals": [],
      "_60m_resonance": false,
      "reason": "四量终极 信号0项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "电池技术",
        "锂电池概念",
        "固态电池",
        "计算机、通信和其他电子设备制造业",
        "PCB",
        "2026中报预增",
        "冷链物流",
        "半导体概念"
      ],
      "tracking": {
        "entry_date": "2026-10-25",
        "entry_price": 201.65,
        "latest_price": 201.65,
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
      "code": "002138",
      "name": "顺络电子",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 42.18,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 1.83,
      "final_score": 36.8,
      "mix_pct": 100.0,
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
        "小米概念",
        "富时罗素",
        "MSCI中国",
        "中证500",
        "标准普尔",
        "消费电子概念",
        "融资融券"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 37.96,
      "target_price": 55.86,
      "risk_reward": 3.24,
      "support": 38.0,
      "resistance": 55.86,
      "factor_actions": []
    },
    {
      "code": "300199",
      "name": "翰宇药业",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 25.8,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 4.71,
      "final_score": 29.2,
      "mix_pct": 67.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "上涨趋势"
      ],
      "industry": "医药制造业",
      "concepts": [
        "合成生物",
        "小盘成长",
        "融资融券",
        "工业大麻",
        "2026中报预增",
        "AI制药（医疗）",
        "流感",
        "创业板综"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 23.22,
      "target_price": 27.7,
      "risk_reward": 0.74,
      "support": 22.06,
      "resistance": 27.7,
      "factor_actions": []
    },
    {
      "code": "603186",
      "name": "华正新材",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 201.65,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 6.19,
      "final_score": 28.0,
      "mix_pct": 62.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "电池技术",
        "锂电池概念",
        "固态电池",
        "计算机、通信和其他电子设备制造业",
        "PCB",
        "2026中报预增",
        "冷链物流",
        "半导体概念"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 181.49,
      "target_price": 264.0,
      "risk_reward": 3.09,
      "support": 169.75,
      "resistance": 242.8,
      "factor_actions": []
    },
    {
      "code": "301511",
      "name": "德福科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 72.19,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 0.49,
      "final_score": 28.0,
      "mix_pct": 62.4,
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
        "电池技术",
        "养老金",
        "锂电池概念",
        "深成500",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "中盘成长",
        "PCB"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 64.97,
      "target_price": 118.51,
      "risk_reward": 6.42,
      "support": 65.8,
      "resistance": 115.63,
      "factor_actions": []
    },
    {
      "code": "002491",
      "name": "通鼎互联",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 16.41,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": -0.55,
      "final_score": 26.1,
      "mix_pct": 54.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "光纤概念",
        "电气机械和器材制造业",
        "融资融券",
        "大数据",
        "富时罗素",
        "通信技术",
        "深股通",
        "北交所概念"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 14.77,
      "target_price": 25.4,
      "risk_reward": 5.48,
      "support": 15.16,
      "resistance": 25.4,
      "factor_actions": []
    },
    {
      "code": "301183",
      "name": "东田微",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 225.81,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": -0.96,
      "final_score": 25.8,
      "mix_pct": 53.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "激光雷达",
        "无人驾驶",
        "2026中报预增",
        "小米概念",
        "荣耀概念",
        "通信技术"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 203.23,
      "target_price": 319.99,
      "risk_reward": 4.17,
      "support": 204.0,
      "resistance": 319.99,
      "factor_actions": []
    },
    {
      "code": "300613",
      "name": "富瀚微",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 69.3,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 6.6,
      "final_score": 23.3,
      "mix_pct": 42.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "电子后视镜",
        "人工智能",
        "鸿蒙概念",
        "安防概念",
        "融资融券",
        "国产芯片",
        "机构重仓",
        "软件和信息技术服务业"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 62.37,
      "target_price": 89.88,
      "risk_reward": 2.97,
      "support": 60.18,
      "resistance": 89.88,
      "factor_actions": []
    },
    {
      "code": "600641",
      "name": "先导基电",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 35.5,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": -0.45,
      "final_score": 22.8,
      "mix_pct": 40.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "房地产业",
      "concepts": [
        "富时罗素",
        "存储芯片",
        "稀缺资源",
        "OLED",
        "上证380",
        "标准普尔",
        "创投",
        "固态电池"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 31.95,
      "target_price": 52.58,
      "risk_reward": 4.81,
      "support": 32.2,
      "resistance": 52.58,
      "factor_actions": []
    },
    {
      "code": "688689",
      "name": "银河微电",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 37.0,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 2.55,
      "final_score": 20.9,
      "mix_pct": 32.1,
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
        "计算机、通信和其他电子设备制造业"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 33.3,
      "target_price": 44.28,
      "risk_reward": 1.97,
      "support": 32.08,
      "resistance": 44.28,
      "factor_actions": []
    },
    {
      "code": "688099",
      "name": "晶晨股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 100.68,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 6.63,
      "final_score": 18.9,
      "mix_pct": 23.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "科创板做市股",
        "融资融券",
        "国产芯片",
        "中盘股",
        "AI芯片",
        "半导体概念",
        "人工智能",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 90.61,
      "target_price": 103.78,
      "risk_reward": 0.31,
      "support": 85.0,
      "resistance": 103.78,
      "factor_actions": []
    },
    {
      "code": "688388",
      "name": "嘉元科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 23.06,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 4.06,
      "final_score": 18.2,
      "mix_pct": 20.5,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "电池技术",
        "锂电池概念",
        "2026一季报预增",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "固态电池",
        "PCB",
        "2026中报预增"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 20.75,
      "target_price": 31.78,
      "risk_reward": 3.78,
      "support": 20.77,
      "resistance": 31.78,
      "factor_actions": []
    },
    {
      "code": "688409",
      "name": "富创精密",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 131.33,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 0.1,
      "final_score": 17.4,
      "mix_pct": 17.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "通用设备制造业",
      "concepts": [
        "融资融券",
        "2026中报预增",
        "中盘股",
        "半导体概念",
        "沪股通",
        "科技风格",
        "专精特新",
        "基金重仓"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 118.2,
      "target_price": 231.8,
      "risk_reward": 7.65,
      "support": 119.6,
      "resistance": 206.67,
      "factor_actions": []
    },
    {
      "code": "002050",
      "name": "三花智控",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 35.08,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 6.66,
      "final_score": 17.3,
      "mix_pct": 16.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缩量强势"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "液冷概念",
        "华为汽车",
        "富时罗素",
        "MSCI中国",
        "机器人概念",
        "通用设备制造业",
        "标准普尔",
        "新能源车"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 31.57,
      "target_price": 40.33,
      "risk_reward": 1.5,
      "support": 30.12,
      "resistance": 37.13,
      "factor_actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第23／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ]
    },
    {
      "code": "002353",
      "name": "杰瑞股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 91.73,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 2.62,
      "final_score": 15.3,
      "mix_pct": 8.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "专用设备制造业",
      "concepts": [
        "天然气",
        "周期股",
        "专用设备制造业",
        "富时罗素",
        "MSCI中国",
        "基金重仓",
        "标准普尔",
        "锂电池概念"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 82.56,
      "target_price": 170.35,
      "risk_reward": 8.57,
      "support": 82.56,
      "resistance": 128.45,
      "factor_actions": []
    },
    {
      "code": "688037",
      "name": "芯源微",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 266.0,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 1.44,
      "final_score": 14.7,
      "mix_pct": 5.6,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "专用设备制造业",
      "concepts": [
        "中芯概念",
        "专用设备制造业",
        "MSCI中国",
        "中证500",
        "基金重仓",
        "上证380",
        "融资融券",
        "国产芯片"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 239.4,
      "target_price": 379.0,
      "risk_reward": 4.25,
      "support": 245.88,
      "resistance": 371.5,
      "factor_actions": []
    },
    {
      "code": "600885",
      "name": "宏发股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.35,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 4.62,
      "final_score": 14.5,
      "mix_pct": 4.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "电气机械和器材制造业",
        "华为汽车",
        "富时罗素",
        "MSCI中国",
        "中证500",
        "上证380",
        "标准普尔",
        "新能源车"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 27.32,
      "target_price": 37.28,
      "risk_reward": 2.28,
      "support": 28.7,
      "resistance": 34.9,
      "factor_actions": []
    },
    {
      "code": "600498",
      "name": "烽火通信",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.31,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 1.92,
      "final_score": 14.0,
      "mix_pct": 2.6,
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
        "液冷概念",
        "算力概念",
        "计算机、通信和其他电子设备制造业",
        "富时罗素",
        "MSCI中国",
        "中证500",
        "数据要素",
        "上证380"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 27.28,
      "target_price": 45.24,
      "risk_reward": 4.93,
      "support": 27.7,
      "resistance": 45.24,
      "factor_actions": []
    },
    {
      "code": "002636",
      "name": "金安国纪",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 60.44,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 2.96,
      "final_score": 13.9,
      "mix_pct": 2.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "医疗器械概念",
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "PCB",
        "2026中报预增",
        "富时罗素",
        "深股通",
        "小盘成长"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 54.4,
      "target_price": 92.0,
      "risk_reward": 5.22,
      "support": 54.33,
      "resistance": 92.0,
      "factor_actions": []
    },
    {
      "code": "300657",
      "name": "弘信电子",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 33.8,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 4.03,
      "final_score": 13.9,
      "mix_pct": 2.1,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "液冷概念",
        "算力概念",
        "计算机、通信和其他电子设备制造业",
        "PCB",
        "小米概念",
        "小盘成长",
        "OLED",
        "机器人概念"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 30.42,
      "target_price": 39.03,
      "risk_reward": 1.55,
      "support": 29.55,
      "resistance": 39.03,
      "factor_actions": []
    },
    {
      "code": "688110",
      "name": "东芯股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 58.65,
      "close_date": "2026-10-23",
      "close_verified": true,
      "pct_chg": 3.62,
      "final_score": 13.4,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "计算机、通信和其他电子设备制造业",
        "国产芯片",
        "中盘股",
        "半导体概念",
        "存储芯片",
        "MSCI中国",
        "沪股通"
      ],
      "enter_date": "2026-10-25",
      "stop_loss": 52.78,
      "target_price": 85.84,
      "risk_reward": 4.64,
      "support": 52.9,
      "resistance": 84.54,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-25 15:40:03",
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
        "n_hit": 0,
        "evidence": "薄样本(9 信号日 / 89 命中)",
        "why": "实测边际 +0.68pp（弱正，命中 89 条 ≈ 43.9% 覆盖率，无选择性）⇒ 不足与强源同权"
      }
    ],
    "evidence_note": "计分依据分级：①「未回测」= 无任何样本外证据（放量弱势）；②「薄样本」= 9 信号日实测边际，样本不足以定权重，故不计分（异常换手率/ROE_TTM/高手跟踪）；③「walk-forward」= ≥4/5 年 OOS 检验通过才给分（候选池层 P5 的 amt60/turntrend，+6/+3）。本层当前**没有任何因子持有第③级证据** ⇒ 除放量弱势外全部为 0 分，属**有意的保守**。　🔴 结论（2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」）：本层唯一记分的「放量弱势 −0.5」有**三重问题** —— ①无回测依据（bottom 榜从未回测）；②设计上不相交（bottom=极端放量股 vs 候选池=缩量强势，实测交集 0 ⇒ 几乎恒不触发）；③上游 _weak 集合曾因 norm_code 未剥点而恒失配（29 轮命中 0 次，本补丁已修）。⇒ **因子在本层的实际计分影响 = 0**，现状等于「全部只做标注」；要让它真正成为加减分项，须先补 walk-forward 回测（流程见下方 ③ 待接入队列 / 明细见本页 🧪 因子审计卡）。",
    "dedup_note": "因子只对**池内已有票**动作（_factor_in_pool 只查不建）⇒ 不产池、不决定谁能进榜"
  },
  "factor_trace": [
    {
      "code": "002050",
      "name": "三花智控",
      "final_score": 17.3,
      "mix_pct": 16.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第23／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ],
      "adj_total": 0.0
    }
  ]
};