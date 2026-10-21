window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-21 20:25:55",
  "crisis_score": 33.1,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 27,
  "top_n": 3,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-21 09:28:10",
    "degraded": false,
    "effective": {
      "jinzuan": 1.274,
      "chan": 1.091,
      "trend": -0.615,
      "jigou": -0.415
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 198,
      "chan": 420,
      "trend": 279,
      "jigou": 493
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-10-21 09:28:10",
      "hit": 4,
      "n_snapshots": 90,
      "date_range": [
        "2026-06-06",
        "2026-10-21"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-10-20） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-10-21",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-10-21",
    "pool_total": 8,
    "new_selected": 8,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-10-21",
    "source": "STOCK_QUOTE",
    "covered": 27,
    "total": 27,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "军工电子",
    "军工装备",
    "厨卫电器",
    "小金属",
    "工程机械",
    "汽车零部件",
    "油气开采及服务",
    "电机",
    "白酒",
    "贵金属",
    "银行",
    "黑色家电"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "688525",
      "name": "佰维存储",
      "market": "sh",
      "board": "科创板",
      "horizon": "短线",
      "close": 164.42,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 3.32,
      "stop_loss": 159.13,
      "target_price": 175.0,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.93
      },
      "resonance": 1,
      "strength": 1.93,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 22.7,
      "mix_pct": 100.0,
      "buy_score": 22.7,
      "enter_date": "2026-10-21",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "阿里概念",
        "机器人概念",
        "AI手机",
        "数据中心",
        "科技风格",
        "消费电子概念",
        "MSCI中国",
        "先进封装"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
        "entry_price": 164.42,
        "latest_price": 164.42,
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
      "code": "301308",
      "name": "江波龙",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 248.98,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.62,
      "stop_loss": 244.0,
      "target_price": 258.94,
      "risk_reward": 2.0,
      "support": 234.98,
      "resistance": 357.8,
      "atr": 14.15,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.93
      },
      "resonance": 1,
      "strength": 1.93,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 22.0,
      "mix_pct": 91.3,
      "buy_score": 22.0,
      "enter_date": "2026-10-21",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "HS300",
        "机器人概念",
        "AI手机",
        "科技风格",
        "MSCI中国",
        "2026中报预增",
        "深证100R",
        "AIPC"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
        "entry_price": 248.98,
        "latest_price": 248.98,
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
      "code": "300054",
      "name": "鼎龙股份",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 58.2,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 0.19,
      "stop_loss": 57.6,
      "target_price": 59.4,
      "risk_reward": 2.0,
      "support": 55.89,
      "resistance": 73.93,
      "atr": 3.06,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.93
      },
      "resonance": 1,
      "strength": 1.93,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 19.6,
      "mix_pct": 61.3,
      "buy_score": 19.6,
      "enter_date": "2026-10-21",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "中盘股",
        "光刻机(胶)",
        "科技风格",
        "富时罗素",
        "玻璃基板",
        "MSCI中国",
        "柔性屏(折叠屏)",
        "中芯概念"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
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
  "consensus_stocks": [
    {
      "rank": 1,
      "code": "300296",
      "name": "利亚德",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 5.63,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 20.04,
      "stop_loss": 5.07,
      "target_price": 6.76,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极",
        "强势跟踪"
      ],
      "source_scores": {
        "四量终极": 1.31,
        "强势跟踪": 75.0
      },
      "resonance": 2,
      "strength": 76.31,
      "final_score": 15.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-21",
      "signals": [
        "机构变红",
        "上涨趋势",
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项；强势跟踪（短线情绪选股）当日新入选·强度分 75；高手强势股跟踪池共振（IMA 状态有效）",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MiniLED",
        "小米概念",
        "机器人概念",
        "元宇宙概念",
        "首发经济",
        "增强现实",
        "富时罗素",
        "玻璃基板"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
        "entry_price": 5.63,
        "latest_price": 5.63,
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
      "code": "688525",
      "name": "佰维存储",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 164.42,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 3.32,
      "stop_loss": 159.13,
      "target_price": 175.0,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "atr": null,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.93
      },
      "resonance": 1,
      "strength": 1.93,
      "final_score": 22.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-21",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "阿里概念",
        "机器人概念",
        "AI手机",
        "数据中心",
        "科技风格",
        "消费电子概念",
        "MSCI中国",
        "先进封装"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
        "entry_price": 164.42,
        "latest_price": 164.42,
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
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 248.98,
      "close_date": "2026-10-21",
      "close_source": "STOCK_QUOTE",
      "close_verified": true,
      "pct_chg": 1.62,
      "stop_loss": 244.0,
      "target_price": 258.94,
      "risk_reward": 2.0,
      "support": 234.98,
      "resistance": 357.8,
      "atr": 14.15,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.93
      },
      "resonance": 1,
      "strength": 1.93,
      "final_score": 22.0,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-21",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "HS300",
        "机器人概念",
        "AI手机",
        "科技风格",
        "MSCI中国",
        "2026中报预增",
        "深证100R",
        "AIPC"
      ],
      "tracking": {
        "entry_date": "2026-10-21",
        "entry_price": 248.98,
        "latest_price": 248.98,
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
      "code": "688525",
      "name": "佰维存储",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 164.42,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 3.32,
      "final_score": 22.7,
      "mix_pct": 100.0,
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
        "阿里概念",
        "机器人概念",
        "AI手机",
        "数据中心",
        "科技风格",
        "消费电子概念",
        "MSCI中国",
        "先进封装"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 159.13,
      "target_price": 175.0,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "301308",
      "name": "江波龙",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 248.98,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 1.62,
      "final_score": 22.0,
      "mix_pct": 91.3,
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
        "HS300",
        "机器人概念",
        "AI手机",
        "科技风格",
        "MSCI中国",
        "2026中报预增",
        "深证100R",
        "AIPC"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 244.0,
      "target_price": 258.94,
      "risk_reward": 2.0,
      "support": 234.98,
      "resistance": 357.8,
      "factor_actions": []
    },
    {
      "code": "300054",
      "name": "鼎龙股份",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 58.2,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 0.19,
      "final_score": 19.6,
      "mix_pct": 61.3,
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
        "中盘股",
        "光刻机(胶)",
        "科技风格",
        "富时罗素",
        "玻璃基板",
        "MSCI中国",
        "柔性屏(折叠屏)",
        "中芯概念"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 57.6,
      "target_price": 59.4,
      "risk_reward": 2.0,
      "support": 55.89,
      "resistance": 73.93,
      "factor_actions": []
    },
    {
      "code": "301666",
      "name": "大普微",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 335.0,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 3.72,
      "final_score": 19.6,
      "mix_pct": 61.3,
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
        "抖音概念(字节概念)",
        "数据中心",
        "科技风格",
        "2026一季报扭亏",
        "大盘成长",
        "小红书概念",
        "半导体概念",
        "国产芯片"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 301.5,
      "target_price": 402.0,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 350.8,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 3.45,
      "final_score": 18.9,
      "mix_pct": 52.5,
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
        "碳化硅",
        "AH股",
        "科技风格",
        "富时罗素",
        "MSCI中国",
        "光纤概念",
        "第三代半导体"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 333.1,
      "target_price": 442.03,
      "risk_reward": 5.15,
      "support": 320.02,
      "resistance": 483.8,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 29.54,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 0.55,
      "final_score": 18.5,
      "mix_pct": 47.5,
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
        "光通信模块",
        "中盘股",
        "数据中心",
        "科技风格",
        "富时罗素",
        "网络安全",
        "超导概念",
        "华为概念"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 27.9,
      "target_price": 42.53,
      "risk_reward": 7.92,
      "support": 27.18,
      "resistance": 47.59,
      "factor_actions": []
    },
    {
      "code": "001309",
      "name": "德明利",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 233.81,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 6.5,
      "final_score": 18.4,
      "mix_pct": 46.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "科技风格",
        "MSCI中国",
        "2026一季报扭亏",
        "昨日高换手",
        "AIPC",
        "东方财富热股",
        "半导体概念",
        "国产芯片"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 217.44,
      "target_price": 266.54,
      "risk_reward": 2.0,
      "support": 204.5,
      "resistance": 302.39,
      "factor_actions": []
    },
    {
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 57.23,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": -0.04,
      "final_score": 18.1,
      "mix_pct": 42.5,
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
        "HS300",
        "苹果概念",
        "科技风格",
        "富时罗素",
        "玻璃基板",
        "消费电子概念",
        "MSCI中国",
        "物联网"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 53.22,
      "target_price": 69.0,
      "risk_reward": 2.94,
      "support": 54.23,
      "resistance": 74.45,
      "factor_actions": []
    },
    {
      "code": "688400",
      "name": "凌云光",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 44.59,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 5.76,
      "final_score": 17.1,
      "mix_pct": 30.0,
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
      "enter_date": "2026-10-21",
      "stop_loss": 42.16,
      "target_price": 49.45,
      "risk_reward": 2.0,
      "support": 35.05,
      "resistance": 48.25,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 52.48,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": -5.42,
      "final_score": 16.5,
      "mix_pct": 22.5,
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
        "锂电池概念",
        "中盘股",
        "固态电池",
        "超级电容",
        "富时罗素",
        "MSCI中国",
        "特斯拉概念",
        "2026中报预增"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 47.23,
      "target_price": 68.49,
      "risk_reward": 3.05,
      "support": 54.07,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 17.61,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 0.17,
      "final_score": 16.3,
      "mix_pct": 20.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "industry": "水上运输业",
      "concepts": [
        "HS300",
        "一带一路",
        "2026中报预增",
        "周期股",
        "标准普尔",
        "沪股通",
        "水上运输业",
        "大盘价值"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 17.58,
      "target_price": 22.07,
      "risk_reward": 148.67,
      "support": 17.61,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "300475",
      "name": "香农芯创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 116.78,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 2.04,
      "final_score": 16.2,
      "mix_pct": 18.8,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "批发业",
      "concepts": [
        "科技风格",
        "MSCI中国",
        "2026中报预增",
        "大盘成长",
        "2026一季报预增",
        "半导体概念",
        "存储芯片",
        "融资融券"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 112.6,
      "target_price": 125.14,
      "risk_reward": 2.0,
      "support": 107.9,
      "resistance": 189.92,
      "factor_actions": []
    },
    {
      "code": "688630",
      "name": "芯碁微装",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 301.22,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 0.11,
      "final_score": 16.0,
      "mix_pct": 16.3,
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
        "先进封装",
        "PCB",
        "中盘股",
        "专用设备制造业",
        "光刻机(胶)",
        "沪股通",
        "上证380",
        "AH股"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 300.9,
      "target_price": 323.0,
      "risk_reward": 68.06,
      "support": 291.01,
      "resistance": 448.88,
      "factor_actions": []
    },
    {
      "code": "600498",
      "name": "烽火通信",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 31.05,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 1.17,
      "final_score": 15.4,
      "mix_pct": 8.8,
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
        "光通信模块",
        "中盘股",
        "数据中心",
        "科技风格",
        "富时罗素",
        "F5G概念",
        "网络安全",
        "MSCI中国"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 30.69,
      "target_price": 41.08,
      "risk_reward": 27.86,
      "support": 28.6,
      "resistance": 45.24,
      "factor_actions": []
    },
    {
      "code": "002384",
      "name": "东山精密",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 123.17,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 0.83,
      "final_score": 15.4,
      "mix_pct": 8.8,
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
        "HS300",
        "MiniLED",
        "小米概念",
        "光通信模块",
        "标准普尔",
        "苹果概念",
        "科技风格",
        "富时罗素"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 122.15,
      "target_price": 196.06,
      "risk_reward": 71.46,
      "support": 117.2,
      "resistance": 208.5,
      "factor_actions": []
    },
    {
      "code": "300620",
      "name": "光库科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 260.9,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 9.44,
      "final_score": 15.3,
      "mix_pct": 7.5,
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
        "光通信模块",
        "中盘股",
        "科技风格",
        "MSCI中国",
        "无人驾驶",
        "光纤概念",
        "商业航天",
        "2026中报预增"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 234.81,
      "target_price": 313.08,
      "risk_reward": 2.0,
      "support": 221.0,
      "resistance": 309.75,
      "factor_actions": []
    },
    {
      "code": "300857",
      "name": "协创数据",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 215.11,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 6.86,
      "final_score": 15.2,
      "mix_pct": 6.2,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "缠论买点"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "阿里概念",
        "光通信模块",
        "小米概念",
        "科技风格",
        "网络游戏",
        "MSCI中国",
        "物联网",
        "AIGC概念"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 201.3,
      "target_price": 268.58,
      "risk_reward": 3.87,
      "support": 203.0,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "300296",
      "name": "利亚德",
      "market": "深市",
      "board": "创业板",
      "horizon": "中长线",
      "close": 5.63,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 20.04,
      "final_score": 15.0,
      "mix_pct": 3.8,
      "resonance": 2,
      "sources": [
        "四量终极",
        "强势跟踪"
      ],
      "signals": [
        "上涨趋势",
        "强势跟踪·当日新入选",
        "机构变红",
        "高手共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "MiniLED",
        "小米概念",
        "机器人概念",
        "元宇宙概念",
        "首发经济",
        "增强现实",
        "富时罗素",
        "玻璃基板"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 5.07,
      "target_price": 6.76,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "603341",
      "name": "龙旗科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 40.31,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 5.36,
      "final_score": 15.0,
      "mix_pct": 3.8,
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
        "小米概念",
        "计算机、通信和其他电子设备制造业",
        "小盘股",
        "中证500",
        "沪股通",
        "荣耀概念",
        "上证380",
        "车联网(车路云)"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 37.49,
      "target_price": 45.95,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "301396",
      "name": "宏景科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 132.35,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 4.81,
      "final_score": 14.7,
      "mix_pct": 0.0,
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
        "腾讯云",
        "小盘成长",
        "互联网服务",
        "新型城镇化",
        "空间计算",
        "智慧城市",
        "物联网",
        "QFII重仓"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": 125.62,
      "target_price": 145.81,
      "risk_reward": 2.0,
      "support": 119.26,
      "resistance": 199.9,
      "factor_actions": []
    },
    {
      "code": "301159",
      "name": "三维天地",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 38.76,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 20.0,
      "final_score": 0.0,
      "mix_pct": 100.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "军工",
        "机器人概念",
        "华为概念",
        "微盘精选",
        "物联网",
        "合成生物",
        "数据要素",
        "微盘股"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "688500",
      "name": "慧辰股份",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 37.56,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 20.0,
      "final_score": 0.0,
      "mix_pct": 60.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "603636",
      "name": "南威软件",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 9.78,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 10.01,
      "final_score": 0.0,
      "mix_pct": 46.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "软件和信息技术服务业",
      "concepts": [
        "阿里概念",
        "互联网服务",
        "网络安全",
        "智慧城市",
        "物联网",
        "数据要素",
        "电子身份证",
        "沪股通"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "603330",
      "name": "天洋新材",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 10.09,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 10.03,
      "final_score": 0.0,
      "mix_pct": 46.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "橡胶和塑料制品业",
      "concepts": [
        "新材料",
        "2026中报扭亏",
        "网红经济",
        "光伏概念",
        "参股新三板",
        "专精特新",
        "无线耳机",
        "消费电子概念"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "001239",
      "name": "永达股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 14.74,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 10.0,
      "final_score": 0.0,
      "mix_pct": 26.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "金属制品业",
      "concepts": [
        "工程机械概念",
        "机构重仓",
        "风能",
        "2026中报预减",
        "并购重组概念",
        "破发股",
        "融资融券"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002086",
      "name": "东方海洋",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 2.39,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 10.14,
      "final_score": 0.0,
      "mix_pct": 6.7,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "渔业",
      "concepts": [
        "食品安全",
        "体外诊断概念",
        "预制菜概念",
        "医疗器械概念",
        "机构重仓",
        "病原体防治",
        "幽门螺杆菌概念",
        "精准诊断"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "002835",
      "name": "同为股份",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 15.58,
      "close_date": "2026-10-21",
      "close_verified": true,
      "pct_chg": 10.03,
      "final_score": 0.0,
      "mix_pct": 0.0,
      "resonance": 1,
      "sources": [
        "强势跟踪"
      ],
      "signals": [
        "强势跟踪·当日新入选",
        "高手共振"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "数据安全",
        "安防概念",
        "深圳特区",
        "人工智能",
        "智慧城市",
        "贬值受益"
      ],
      "enter_date": "2026-10-21",
      "stop_loss": null,
      "target_price": null,
      "risk_reward": null,
      "support": null,
      "resistance": null,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-21 20:25:54",
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