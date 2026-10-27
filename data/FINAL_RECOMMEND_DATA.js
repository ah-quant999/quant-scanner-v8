window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-28 01:34:26",
  "crisis_score": 33.1,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 54,
  "top_n": 3,
  "data_degraded": false,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-27 08:12:13",
    "degraded": false,
    "effective": {
      "jinzuan": 0.67,
      "chan": 0.855,
      "trend": -0.48,
      "jigou": -0.308
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
      "trend": 280,
      "jigou": 497
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-27 08:12:13",
      "hit": 4,
      "n_snapshots": 96,
      "date_range": [
        "2026-06-06",
        "2026-10-27"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": null,
  "market_regime": {
    "date": "2026-10-27",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-10-27",
    "pool_total": 0,
    "new_selected": 0,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-10-27",
    "source": "STOCK_QUOTE",
    "covered": 54,
    "total": 54,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "保险",
    "医药商业",
    "小金属",
    "工程机械",
    "机场航运",
    "游戏",
    "电机",
    "白酒",
    "贵金属",
    "银行",
    "零售",
    "食品加工制造"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "600869",
      "name": "远东股份",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 13.89,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.86,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 12.92,
      "target_price": 15.83,
      "risk_reward": 2.0,
      "support": 13.87,
      "resistance": 22.97,
      "atr": 1.37,
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
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "充电桩",
        "电网概念",
        "电商概念",
        "固态电池",
        "中盘股",
        "海洋经济",
        "特高压",
        "智慧城市"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 13.89,
        "latest_price": 13.89,
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
      "close": 34.25,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.62,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 34.04,
      "target_price": 51.56,
      "risk_reward": 82.43,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.51,
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
          "pct_5d": -5.33,
          "relative_5d": -5.33,
          "strong": true
        }
      ],
      "sector_fund": [
        {
          "name": "小金属",
          "pct_5d": -5.33,
          "relative_5d": -5.33,
          "strong": true
        }
      ],
      "final_score": 25.3,
      "mix_pct": 55.8,
      "buy_score": 25.3,
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "房地产业",
      "concepts": [
        "稀缺资源",
        "长江三角",
        "固态电池",
        "标准普尔",
        "小盘股",
        "最近多板",
        "富时罗素",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 34.25,
        "latest_price": 34.25,
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
      "close": 114.36,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -8.6,
      "limit_up": false,
      "limit_up_note": null,
      "stop_loss": 102.92,
      "target_price": 231.8,
      "risk_reward": 10.27,
      "support": 113.53,
      "resistance": 200.3,
      "atr": 10.97,
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
      "final_score": 20.4,
      "mix_pct": 45.0,
      "buy_score": 20.4,
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "通用设备制造业",
      "concepts": [
        "基金重仓",
        "通用设备制造业",
        "半导体概念",
        "科技风格",
        "融资融券",
        "中盘股",
        "百元股",
        "沪股通"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 114.36,
        "latest_price": 114.36,
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
      "close": 13.89,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -4.86,
      "stop_loss": 12.92,
      "target_price": 15.83,
      "risk_reward": 2.0,
      "support": 13.87,
      "resistance": 22.97,
      "atr": 1.37,
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
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "充电桩",
        "电网概念",
        "电商概念",
        "固态电池",
        "中盘股",
        "海洋经济",
        "特高压",
        "智慧城市"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 13.89,
        "latest_price": 13.89,
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
      "close": 34.25,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.62,
      "stop_loss": 34.04,
      "target_price": 51.56,
      "risk_reward": 82.43,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.51,
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
          "pct_5d": -5.33,
          "relative_5d": -5.33,
          "strong": true
        }
      ],
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "房地产业",
      "concepts": [
        "稀缺资源",
        "长江三角",
        "固态电池",
        "标准普尔",
        "小盘股",
        "最近多板",
        "富时罗素",
        "融资融券"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 34.25,
        "latest_price": 34.25,
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
      "close": 114.36,
      "close_date": "2026-10-27",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": -8.6,
      "stop_loss": 102.92,
      "target_price": 231.8,
      "risk_reward": 10.27,
      "support": 113.53,
      "resistance": 200.3,
      "atr": 10.97,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.77
      },
      "resonance": 1,
      "strength": 1.77,
      "final_score": 20.4,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "通用设备制造业",
      "concepts": [
        "基金重仓",
        "通用设备制造业",
        "半导体概念",
        "科技风格",
        "融资融券",
        "中盘股",
        "百元股",
        "沪股通"
      ],
      "tracking": {
        "entry_date": "2026-10-28",
        "entry_price": 114.36,
        "latest_price": 114.36,
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
      "close": 13.89,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -4.86,
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
        "充电桩",
        "电网概念",
        "电商概念",
        "固态电池",
        "中盘股",
        "海洋经济",
        "特高压",
        "智慧城市"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 12.92,
      "target_price": 15.83,
      "risk_reward": 2.0,
      "support": 13.87,
      "resistance": 22.97,
      "factor_actions": []
    },
    {
      "code": "600641",
      "name": "先导基电",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 34.25,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": 0.62,
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
        "稀缺资源",
        "长江三角",
        "固态电池",
        "标准普尔",
        "小盘股",
        "最近多板",
        "富时罗素",
        "融资融券"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 34.04,
      "target_price": 51.56,
      "risk_reward": 82.43,
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
      "close": 114.36,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -8.6,
      "final_score": 20.4,
      "mix_pct": 45.0,
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
        "基金重仓",
        "通用设备制造业",
        "半导体概念",
        "科技风格",
        "融资融券",
        "中盘股",
        "百元股",
        "沪股通"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 102.92,
      "target_price": 231.8,
      "risk_reward": 10.27,
      "support": 113.53,
      "resistance": 200.3,
      "factor_actions": []
    },
    {
      "code": "600498",
      "name": "烽火通信",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 28.17,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -2.66,
      "final_score": 15.7,
      "mix_pct": 34.7,
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
        "科技风格",
        "云计算",
        "中盘股",
        "标准普尔",
        "智慧城市",
        "富时罗素",
        "融资融券"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 30.69,
      "target_price": 41.08,
      "risk_reward": 27.86,
      "support": 27.7,
      "resistance": 45.18,
      "factor_actions": []
    },
    {
      "code": "688432",
      "name": "有研硅",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 31.63,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.81,
      "final_score": 14.7,
      "mix_pct": 32.5,
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
        "半导体概念",
        "中芯概念",
        "融资融券",
        "沪股通",
        "计算机、通信和其他电子设备制造业",
        "存储芯片",
        "小盘股"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 28.47,
      "target_price": 60.59,
      "risk_reward": 9.16,
      "support": 31.51,
      "resistance": 58.93,
      "factor_actions": []
    },
    {
      "code": "300497",
      "name": "富祥股份",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 13.26,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.01,
      "final_score": 9.8,
      "mix_pct": 21.6,
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
        "人造肉",
        "有机硅概念",
        "电池技术",
        "锂电池概念",
        "创新药",
        "融资融券",
        "病原体防治",
        "2026中报扭亏"
      ],
      "enter_date": "2026-10-28",
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
      "close": 113.56,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -6.38,
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
        "软件和信息技术服务业",
        "云计算",
        "小盘股",
        "空间计算",
        "智慧城市",
        "财税数字化",
        "融资融券",
        "ChatGPT概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 102.2,
      "target_price": 132.35,
      "risk_reward": 1.65,
      "support": 111.52,
      "resistance": 199.9,
      "factor_actions": []
    },
    {
      "code": "300567",
      "name": "精测电子",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 120.0,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.48,
      "final_score": 4.7,
      "mix_pct": 10.4,
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
        "转债标的",
        "基金重仓",
        "中盘成长",
        "中芯概念",
        "中盘股",
        "创业成份",
        "富时罗素",
        "锂电池概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 108.0,
      "target_price": 153.0,
      "risk_reward": 2.75,
      "support": 119.0,
      "resistance": 218.92,
      "factor_actions": []
    },
    {
      "code": "600522",
      "name": "中天科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 25.85,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -3.04,
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
        "充电桩",
        "MSCI中国",
        "电网概念",
        "科技风格",
        "长江三角",
        "固态电池",
        "海洋经济",
        "标准普尔"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 24.04,
      "target_price": 30.49,
      "risk_reward": 2.56,
      "support": 25.85,
      "resistance": 38.48,
      "factor_actions": []
    },
    {
      "code": "603083",
      "name": "剑桥科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 138.36,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.16,
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
        "中盘成长",
        "MSCI中国",
        "新型工业化",
        "科技风格",
        "边缘计算",
        "中盘股",
        "AH股",
        "融资融券"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 128.67,
      "target_price": 173.61,
      "risk_reward": 3.64,
      "support": 138.0,
      "resistance": 231.0,
      "factor_actions": []
    },
    {
      "code": "688411",
      "name": "海博思创",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 132.52,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -4.2,
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
      "enter_date": "2026-10-28",
      "stop_loss": 120.83,
      "target_price": 161.1,
      "risk_reward": 2.0,
      "support": 126.01,
      "resistance": 169.89,
      "factor_actions": []
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 19.31,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -0.87,
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
      "enter_date": "2026-10-28",
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
      "close": 25.22,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -2.02,
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
      "enter_date": "2026-10-28",
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
      "close": 127.57,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.31,
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
        "融资融券",
        "通信技术",
        "百元股",
        "沪股通",
        "计算机、通信和其他电子设备制造业",
        "小盘股",
        "2026中报预增"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 114.81,
      "target_price": 244.0,
      "risk_reward": 9.13,
      "support": 125.0,
      "resistance": 239.98,
      "factor_actions": []
    },
    {
      "code": "01833",
      "name": "平安好医生",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 5.36,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -2.46,
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
      "enter_date": "2026-10-28",
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
      "close": 40.0,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -4.9,
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
        "转债标的",
        "充电桩",
        "高压快充",
        "特斯拉概念",
        "小盘股",
        "军工",
        "融资融券",
        "通信技术"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 51.76,
      "target_price": 69.01,
      "risk_reward": 2.0,
      "support": 39.62,
      "resistance": 71.5,
      "factor_actions": []
    },
    {
      "code": "688147",
      "name": "微导纳米",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 61.08,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -7.86,
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
        "转债标的",
        "中盘成长",
        "先进封装",
        "半导体概念",
        "专用设备制造业",
        "融资融券",
        "BC电池",
        "OLED"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 54.97,
      "target_price": 140.5,
      "risk_reward": 13.0,
      "support": 60.88,
      "resistance": 119.78,
      "factor_actions": []
    },
    {
      "code": "301526",
      "name": "国际复材",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 19.04,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -3.15,
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
        "中盘成长",
        "中盘股",
        "创业成份",
        "PCB",
        "融资融券",
        "通信技术",
        "5G概念",
        "华为概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 17.14,
      "target_price": 22.26,
      "risk_reward": 1.69,
      "support": 19.02,
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
      "close": 263.5,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -7.1,
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
      "enter_date": "2026-10-28",
      "stop_loss": 237.15,
      "target_price": 568.98,
      "risk_reward": 11.59,
      "support": 263.0,
      "resistance": 505.68,
      "factor_actions": []
    },
    {
      "code": "300285",
      "name": "国瓷材料",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 40.59,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -6.02,
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
        "中盘成长",
        "科技风格",
        "化学原料和化学制品制造业",
        "固态电池",
        "中盘股",
        "创业成份",
        "最近多板",
        "商业航天"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 36.53,
      "target_price": 47.01,
      "risk_reward": 1.58,
      "support": 40.59,
      "resistance": 75.4,
      "factor_actions": []
    },
    {
      "code": "688629",
      "name": "华丰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 70.43,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -6.21,
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
        "中盘成长",
        "MSCI中国",
        "中盘股",
        "军工",
        "商业航天",
        "先进制造风格",
        "融资融券",
        "计算机、通信和其他电子设备制造业"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 63.39,
      "target_price": 158.43,
      "risk_reward": 12.5,
      "support": 69.98,
      "resistance": 132.18,
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
      "close": 204.38,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -9.04,
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
        "MSCI中国",
        "半导体概念",
        "HS300",
        "科技风格",
        "专用设备制造业",
        "大盘成长",
        "融资融券",
        "大盘股"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 183.94,
      "target_price": 338.92,
      "risk_reward": 6.58,
      "support": 201.59,
      "resistance": 315.8,
      "factor_actions": []
    },
    {
      "code": "300456",
      "name": "赛微电子",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 26.48,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -5.26,
      "final_score": 0.9,
      "mix_pct": 2.0,
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
        "激光雷达",
        "MSCI中国",
        "中盘成长",
        "北交所概念",
        "北斗导航",
        "中盘股",
        "富时罗素",
        "融资融券"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 26.64,
      "target_price": 38.68,
      "risk_reward": 3.07,
      "support": 26.46,
      "resistance": 40.02,
      "factor_actions": []
    },
    {
      "code": "000636",
      "name": "风华高科",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 35.92,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -3.78,
      "final_score": 0.5,
      "mix_pct": 1.1,
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
        "基金重仓",
        "中盘成长",
        "高压快充",
        "中盘股",
        "AI眼镜",
        "锂电池概念",
        "融资融券",
        "通信技术"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 33.41,
      "target_price": 47.17,
      "risk_reward": 4.47,
      "support": 35.92,
      "resistance": 60.15,
      "factor_actions": []
    },
    {
      "code": "688048",
      "name": "长光华芯",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 149.57,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -6.72,
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
        "医美概念",
        "中盘成长",
        "MSCI中国",
        "科技风格",
        "中盘股",
        "商业航天",
        "融资融券",
        "通信技术"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 134.61,
      "target_price": 368.88,
      "risk_reward": 14.66,
      "support": 149.0,
      "resistance": 367.06,
      "factor_actions": []
    },
    {
      "code": "002916",
      "name": "深南电路",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 260.01,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -2.8,
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
        "MSCI中国",
        "科技风格",
        "标准普尔",
        "深圳特区",
        "深证100R",
        "富时罗素",
        "PCB",
        "HS300"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 241.81,
      "target_price": 394.5,
      "risk_reward": 7.39,
      "support": 258.88,
      "resistance": 424.04,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 49.2,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -7.21,
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
        "转债标的",
        "MSCI中国",
        "固态电池",
        "中盘股",
        "创业成份",
        "特斯拉概念",
        "深圳特区",
        "氟化工概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 47.23,
      "target_price": 68.49,
      "risk_reward": 3.05,
      "support": 49.0,
      "resistance": 72.7,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.38,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -3.1,
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
        "华为概念",
        "MSCI中国",
        "PCB",
        "中盘成长",
        "融资融券",
        "长江三角",
        "上证380",
        "通信技术"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 8.72,
      "target_price": 14.62,
      "risk_reward": 7.98,
      "support": 9.33,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 25.3,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -3.21,
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
      "industry": "电气机械和器材制造业",
      "concepts": [
        "基金重仓",
        "中盘成长",
        "MSCI中国",
        "科技风格",
        "长江三角",
        "中盘股",
        "标准普尔",
        "超导概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 23.53,
      "target_price": 42.53,
      "risk_reward": 9.73,
      "support": 25.24,
      "resistance": 47.47,
      "factor_actions": []
    },
    {
      "code": "601168",
      "name": "西部矿业",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.45,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": 0.93,
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
      "industry": "有色金属矿采选业",
      "concepts": [
        "MSCI中国",
        "稀缺资源",
        "中盘股",
        "标准普尔",
        "东方财富热股",
        "题材股",
        "昨日触板",
        "昨日炸板"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 28.67,
      "target_price": 41.15,
      "risk_reward": 4.78,
      "support": 29.58,
      "resistance": 37.36,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-28 01:34:26",
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