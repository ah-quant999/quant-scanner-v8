window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-27 00:09:44",
  "crisis_score": 33.3,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 54,
  "top_n": 3,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-26 23:11:59",
    "degraded": false,
    "effective": {
      "jinzuan": 0.669,
      "chan": 0.854,
      "trend": -0.476,
      "jigou": -0.306
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 263,
      "chan": 478,
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
      "generated": "2026-10-26 23:11:59",
      "hit": 4,
      "n_snapshots": 95,
      "date_range": [
        "2026-06-06",
        "2026-10-26"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-10-26",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-10-26",
    "pool_total": 0,
    "new_selected": 0,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-10-26",
    "source": "STOCK_QUOTE",
    "covered": 54,
    "total": 54,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "IT服务",
    "医疗器械",
    "医药商业",
    "小金属",
    "工程机械",
    "游戏",
    "电机",
    "自动化设备",
    "贵金属",
    "软件开发",
    "通信服务",
    "黑色家电"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "600869",
      "name": "远东股份",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 14.6,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -6.41,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 13.58,
      "target_price": 16.64,
      "risk_reward": 2.0,
      "support": 14.3,
      "resistance": 23.55,
      "atr": 1.34,
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
      "final_score": 45.3,
      "mix_pct": 100.0,
      "buy_score": 45.3,
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "沪股通",
        "节能环保",
        "融资融券",
        "独角兽",
        "电网概念",
        "复合集流体",
        "液冷概念",
        "数据中心"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 14.6,
        "latest_price": 14.6,
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
      "code": "600641",
      "name": "先导基电",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 34.04,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.11,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 31.66,
      "target_price": 51.56,
      "risk_reward": 7.35,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.57,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -1.88,
          "relative_5d": -1.88,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": -1.88,
          "relative_5d": -1.88,
          "strong": true
        }
      ],
      "final_score": 25.3,
      "mix_pct": 55.8,
      "buy_score": 25.3,
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "房地产业",
      "concepts": [
        "沪股通",
        "融资融券",
        "2026中报预增",
        "小盘股",
        "标准普尔",
        "上证380",
        "稀缺资源",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 34.04,
        "latest_price": 34.04,
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
      "code": "688409",
      "name": "富创精密",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线",
      "close": 125.12,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.73,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 112.61,
      "target_price": 231.8,
      "risk_reward": 8.53,
      "support": 119.6,
      "resistance": 204.2,
      "atr": 10.78,
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
      "final_score": 18.5,
      "mix_pct": 40.8,
      "buy_score": 18.5,
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "通用设备制造业",
      "concepts": [
        "沪股通",
        "专精特新",
        "通用设备制造业",
        "科技风格",
        "融资融券",
        "中盘股",
        "基金重仓",
        "半导体概念"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 125.12,
        "latest_price": 125.12,
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
      "code": "600869",
      "name": "远东股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 14.6,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -6.41,
      "stop_loss": 13.58,
      "target_price": 16.64,
      "risk_reward": 2.0,
      "support": 14.3,
      "resistance": 23.55,
      "atr": 1.34,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 45.3,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "沪股通",
        "节能环保",
        "融资融券",
        "独角兽",
        "电网概念",
        "复合集流体",
        "液冷概念",
        "数据中心"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 14.6,
        "latest_price": 14.6,
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
      "code": "600641",
      "name": "先导基电",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 34.04,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.11,
      "stop_loss": 31.66,
      "target_price": 51.56,
      "risk_reward": 7.35,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.57,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 25.3,
      "sector_score": 1.0,
      "sector_hits": [
        {
          "name": "小金属",
          "pct_5d": -1.88,
          "relative_5d": -1.88,
          "strong": true
        }
      ],
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "房地产业",
      "concepts": [
        "沪股通",
        "融资融券",
        "2026中报预增",
        "小盘股",
        "标准普尔",
        "上证380",
        "稀缺资源",
        "富时罗素"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 34.04,
        "latest_price": 34.04,
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
      "code": "688409",
      "name": "富创精密",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 125.12,
      "close_date": "2026-10-26",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.73,
      "stop_loss": 112.61,
      "target_price": 231.8,
      "risk_reward": 8.53,
      "support": 119.6,
      "resistance": 204.2,
      "atr": 10.78,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 18.5,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-27",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "通用设备制造业",
      "concepts": [
        "沪股通",
        "专精特新",
        "通用设备制造业",
        "科技风格",
        "融资融券",
        "中盘股",
        "基金重仓",
        "半导体概念"
      ],
      "tracking": {
        "entry_date": "2026-10-27",
        "entry_price": 125.12,
        "latest_price": 125.12,
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
      "code": "600869",
      "name": "远东股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 14.6,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -6.41,
      "final_score": 45.3,
      "mix_pct": 100.0,
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
        "沪股通",
        "节能环保",
        "融资融券",
        "独角兽",
        "电网概念",
        "复合集流体",
        "液冷概念",
        "数据中心"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 13.58,
      "target_price": 16.64,
      "risk_reward": 2.0,
      "support": 14.3,
      "resistance": 23.55,
      "factor_actions": []
    },
    {
      "code": "600641",
      "name": "先导基电",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 34.04,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.11,
      "final_score": 25.3,
      "mix_pct": 55.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "房地产业",
      "concepts": [
        "沪股通",
        "融资融券",
        "2026中报预增",
        "小盘股",
        "标准普尔",
        "上证380",
        "稀缺资源",
        "富时罗素"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 31.66,
      "target_price": 51.56,
      "risk_reward": 7.35,
      "support": 32.2,
      "resistance": 52.58,
      "factor_actions": []
    },
    {
      "code": "688409",
      "name": "富创精密",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 125.12,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.73,
      "final_score": 18.5,
      "mix_pct": 40.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "通用设备制造业",
      "concepts": [
        "沪股通",
        "专精特新",
        "通用设备制造业",
        "科技风格",
        "融资融券",
        "中盘股",
        "基金重仓",
        "半导体概念"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 112.61,
      "target_price": 231.8,
      "risk_reward": 8.53,
      "support": 119.6,
      "resistance": 204.2,
      "factor_actions": []
    },
    {
      "code": "600498",
      "name": "烽火通信",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 28.94,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.52,
      "final_score": 15.9,
      "mix_pct": 35.1,
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
        "科技风格",
        "融资融券",
        "云计算",
        "大数据",
        "CPO概念",
        "标准普尔",
        "上证380"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 30.69,
      "target_price": 41.08,
      "risk_reward": 27.86,
      "support": 27.7,
      "resistance": 45.24,
      "factor_actions": []
    },
    {
      "code": "688432",
      "name": "有研硅",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 33.58,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -6.96,
      "final_score": 14.8,
      "mix_pct": 32.7,
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
        "中芯概念",
        "沪股通",
        "融资融券",
        "半导体概念",
        "计算机、通信和其他电子设备制造业",
        "小盘股",
        "存储芯片"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 30.22,
      "target_price": 60.59,
      "risk_reward": 8.04,
      "support": 32.85,
      "resistance": 58.93,
      "factor_actions": []
    },
    {
      "code": "300497",
      "name": "富祥股份",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 13.96,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -3.59,
      "final_score": 9.9,
      "mix_pct": 21.9,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "医药制造业",
      "concepts": [
        "创新药",
        "专精特新",
        "有机硅概念",
        "电池技术",
        "融资融券",
        "2026一季报预增",
        "光刻机(胶)",
        "合成生物"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 12.76,
      "target_price": 17.02,
      "risk_reward": 2.0,
      "support": 13.2,
      "resistance": 21.35,
      "factor_actions": []
    },
    {
      "code": "301396",
      "name": "宏景科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 121.3,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -1.32,
      "final_score": 5.7,
      "mix_pct": 12.6,
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
        "QFII重仓",
        "融资融券",
        "云计算",
        "智慧政务",
        "大数据",
        "小盘股",
        "人工智能",
        "小盘成长"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 109.17,
      "target_price": 145.56,
      "risk_reward": 2.0,
      "support": 111.52,
      "resistance": 199.9,
      "factor_actions": []
    },
    {
      "code": "600522",
      "name": "中天科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 26.66,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.55,
      "final_score": 3.8,
      "mix_pct": 8.4,
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
        "沪股通",
        "QFII重仓",
        "昨日高振幅",
        "科技风格",
        "融资融券",
        "上证180",
        "大数据",
        "东数西算"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 26.41,
      "target_price": 30.49,
      "risk_reward": 15.32,
      "support": 26.01,
      "resistance": 38.48,
      "factor_actions": []
    },
    {
      "code": "603083",
      "name": "剑桥科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 145.89,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -7.89,
      "final_score": 3.7,
      "mix_pct": 8.2,
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
        "科技风格",
        "融资融券",
        "中盘成长",
        "2026中报预增",
        "新型工业化",
        "CPO概念",
        "上证380"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 135.68,
      "target_price": 173.61,
      "risk_reward": 2.71,
      "support": 144.05,
      "resistance": 232.0,
      "factor_actions": []
    },
    {
      "code": "688411",
      "name": "海博思创",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 138.33,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": 1.94,
      "final_score": 3.7,
      "mix_pct": 8.2,
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
        "电气机械和器材制造业"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 120.83,
      "target_price": 161.1,
      "risk_reward": 2.0,
      "support": 126.01,
      "resistance": 172.56,
      "factor_actions": []
    },
    {
      "code": "300567",
      "name": "精测电子",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 126.96,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.61,
      "final_score": 2.9,
      "mix_pct": 6.4,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "仪器仪表制造业",
      "concepts": [
        "中芯概念",
        "仪器仪表制造业",
        "融资融券",
        "中盘成长",
        "高带宽内存",
        "虚拟现实",
        "显示技术",
        "电池技术"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 114.26,
      "target_price": 153.0,
      "risk_reward": 2.05,
      "support": 123.33,
      "resistance": 220.98,
      "factor_actions": []
    },
    {
      "code": "688025",
      "name": "杰普特",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 320.0,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -1.24,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
        "小盘成长",
        "华为概念",
        "专精特新",
        "通信技术",
        "股权激励",
        "沪股通",
        "融资融券",
        "苹果概念"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 288.0,
      "target_price": 471.33,
      "risk_reward": 4.73,
      "support": 290.0,
      "resistance": 471.33,
      "factor_actions": []
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 19.48,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": 0.57,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
      "enter_date": "2026-10-27",
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
      "close": 25.74,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -2.2,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
      "enter_date": "2026-10-27",
      "stop_loss": 26.43,
      "target_price": 32.4,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "688205",
      "name": "德科立",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 134.73,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -3.62,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
        "通信技术",
        "小盘成长",
        "专精特新",
        "沪股通",
        "融资融券",
        "2026中报预增",
        "计算机、通信和其他电子设备制造业",
        "小盘股"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 121.26,
      "target_price": 244.0,
      "risk_reward": 8.11,
      "support": 125.0,
      "resistance": 244.0,
      "factor_actions": []
    },
    {
      "code": "01833",
      "name": "平安好医生",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 5.49,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -0.63,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
      "enter_date": "2026-10-27",
      "stop_loss": 5.53,
      "target_price": 6.78,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "688800",
      "name": "瑞可达",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 42.06,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.48,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
        "小盘股",
        "上证380",
        "5G概念",
        "小盘成长",
        "新能源车",
        "小米汽车"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 51.76,
      "target_price": 69.01,
      "risk_reward": 2.0,
      "support": 39.62,
      "resistance": 71.5,
      "factor_actions": []
    },
    {
      "code": "301526",
      "name": "国际复材",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 19.66,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.66,
      "final_score": 1.9,
      "mix_pct": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "缩量强势",
        "金钻信号"
      ],
      "industry": "非金属矿物制品业",
      "concepts": [
        "QFII重仓",
        "PEEK材料概念",
        "融资融券",
        "中盘成长",
        "2026中报预增",
        "5G概念",
        "央国企改革",
        "中盘股"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 17.69,
      "target_price": 23.59,
      "risk_reward": 2.0,
      "support": 19.09,
      "resistance": 32.59,
      "factor_actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第26／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ]
    },
    {
      "code": "688627",
      "name": "精智达",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 283.65,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -9.31,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
        "专用设备制造业"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 255.28,
      "target_price": 568.98,
      "risk_reward": 10.06,
      "support": 280.07,
      "resistance": 516.99,
      "factor_actions": []
    },
    {
      "code": "300285",
      "name": "国瓷材料",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 43.19,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -7.52,
      "final_score": 1.9,
      "mix_pct": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "化学原料和化学制品制造业",
        "QFII重仓",
        "节能环保",
        "科技风格",
        "融资融券",
        "中盘成长",
        "电池技术",
        "新能源车"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 38.87,
      "target_price": 51.83,
      "risk_reward": 2.0,
      "support": 41.77,
      "resistance": 75.4,
      "factor_actions": []
    },
    {
      "code": "688629",
      "name": "华丰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 75.09,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -2.69,
      "final_score": 1.9,
      "mix_pct": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "缩量强势",
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "沪股通",
        "融资融券",
        "中盘成长",
        "上证380",
        "阿里概念",
        "央国企改革",
        "新能源车",
        "中盘股"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 67.58,
      "target_price": 158.43,
      "risk_reward": 11.1,
      "support": 69.98,
      "resistance": 135.24,
      "factor_actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第3／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ]
    },
    {
      "code": "688082",
      "name": "盛美上海",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 224.68,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.55,
      "final_score": 1.9,
      "mix_pct": 4.2,
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
        "专用设备制造业",
        "专精特新",
        "沪股通",
        "科技风格",
        "融资融券",
        "HS300",
        "MSCI中国",
        "上证180"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 202.21,
      "target_price": 338.92,
      "risk_reward": 5.08,
      "support": 219.9,
      "resistance": 315.8,
      "factor_actions": []
    },
    {
      "code": "300456",
      "name": "赛微电子",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 27.95,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -4.58,
      "final_score": 1.0,
      "mix_pct": 2.2,
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
        "第三代半导体",
        "先进封装",
        "EDA概念",
        "融资融券",
        "中盘成长",
        "传感器",
        "北斗导航",
        "5G概念"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 26.64,
      "target_price": 38.68,
      "risk_reward": 3.07,
      "support": 26.71,
      "resistance": 40.02,
      "factor_actions": []
    },
    {
      "code": "000636",
      "name": "风华高科",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 37.33,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -7.02,
      "final_score": 0.6,
      "mix_pct": 1.3,
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
        "虚拟机器人",
        "融资融券",
        "AI眼镜",
        "中盘成长",
        "2026中报预增",
        "5G概念",
        "电池技术",
        "央国企改革"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 34.72,
      "target_price": 47.17,
      "risk_reward": 3.77,
      "support": 36.6,
      "resistance": 61.75,
      "factor_actions": []
    },
    {
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 158.41,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.63,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "融资融券",
        "中盘成长",
        "2026中报预增",
        "CPO概念",
        "5G概念",
        "中盘股",
        "中证500",
        "深成500"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 142.57,
      "target_price": 231.02,
      "risk_reward": 4.58,
      "support": 152.8,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "688048",
      "name": "长光华芯",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 160.34,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.11,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "科技风格",
        "融资融券",
        "医美概念",
        "中盘成长",
        "数据中心",
        "中盘股",
        "通信技术"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 144.31,
      "target_price": 368.88,
      "risk_reward": 13.01,
      "support": 151.89,
      "resistance": 368.88,
      "factor_actions": []
    },
    {
      "code": "002916",
      "name": "深南电路",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 267.51,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -5.47,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "融资融券",
        "2026中报预增",
        "深圳特区",
        "标准普尔",
        "养老金",
        "5G概念",
        "中特估"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 248.78,
      "target_price": 394.5,
      "risk_reward": 6.78,
      "support": 262.65,
      "resistance": 424.04,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 53.02,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -2.14,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "融资融券",
        "2026一季报预增",
        "2026中报预增",
        "深圳特区",
        "液冷概念",
        "电池技术",
        "新能源车",
        "中盘股"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 47.23,
      "target_price": 68.49,
      "risk_reward": 3.05,
      "support": 49.0,
      "resistance": 73.69,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 196.98,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -1.91,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "QFII重仓",
        "科技风格",
        "融资融券",
        "CPO概念",
        "5G概念",
        "富时罗素",
        "大盘股",
        "深成500"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 177.28,
      "target_price": 267.93,
      "risk_reward": 3.6,
      "support": 181.5,
      "resistance": 290.95,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.68,
      "close_date": "2026-10-26",
      "close_verified": true,
      "pct_chg": -6.11,
      "final_score": 0.0,
      "mix_pct": 0.0,
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
        "5G概念",
        "通信技术",
        "华为概念",
        "沪股通",
        "央国企改革",
        "融资融券",
        "中盘股",
        "MSCI中国"
      ],
      "enter_date": "2026-10-27",
      "stop_loss": 9.0,
      "target_price": 14.62,
      "risk_reward": 7.29,
      "support": 9.38,
      "resistance": 15.8,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-27 00:09:44",
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
        "n_hit": 2,
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
      "code": "301526",
      "name": "国际复材",
      "final_score": 1.9,
      "mix_pct": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第26／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "688629",
      "name": "华丰科技",
      "final_score": 1.9,
      "mix_pct": 4.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "异常换手率",
          "adj": 0.0,
          "scored": false,
          "note": "缩量强势 排名第3／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
        }
      ],
      "adj_total": 0.0
    },
    {
      "code": "603986",
      "name": "兆易创新",
      "final_score": 0.0,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "actions": [
        {
          "factor": "ROE_TTM",
          "adj": 0.0,
          "scored": false,
          "note": "高ROE 排名第30／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
        }
      ],
      "adj_total": 0.0
    }
  ]
};