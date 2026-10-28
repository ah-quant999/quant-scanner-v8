window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-28 09:02:36",
  "crisis_score": 33.0,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 54,
  "top_n": 3,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-28 07:08:48",
    "degraded": false,
    "effective": {
      "jinzuan": 0.606,
      "chan": 0.814,
      "trend": -0.469,
      "jigou": -0.299
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 283,
      "chan": 496,
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
      "generated": "2026-10-28 07:08:48",
      "hit": 4,
      "n_snapshots": 97,
      "date_range": [
        "2026-06-06",
        "2026-10-28"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-10-27） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
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
      "stop_loss": 12.5,
      "target_price": 26.68,
      "risk_reward": 9.21,
      "support": 13.87,
      "resistance": 22.97,
      "atr": 1.37,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 44.7,
      "mix_pct": 100.0,
      "buy_score": 44.7,
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "电气机械和器材制造业",
      "concepts": [
        "光纤概念",
        "人形机器人",
        "先进制造风格",
        "融资融券",
        "新能源车",
        "数据中心",
        "电池技术",
        "智能电网"
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
      "stop_loss": 30.82,
      "target_price": 52.58,
      "risk_reward": 5.35,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.51,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
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
      "final_score": 24.6,
      "mix_pct": 55.0,
      "buy_score": 24.6,
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "房地产业",
      "concepts": [
        "国产芯片",
        "标准普尔",
        "小盘股",
        "小金属概念",
        "融资融券",
        "上证380",
        "半导体概念",
        "光伏概念"
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
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 19.8,
      "mix_pct": 44.3,
      "buy_score": 19.8,
      "enter_date": "2026-10-28",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "通用设备制造业",
      "concepts": [
        "通用设备制造业",
        "沪股通",
        "半导体概念",
        "百元股",
        "基金重仓",
        "专精特新",
        "中盘股",
        "融资融券"
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
      "stop_loss": 12.5,
      "target_price": 26.68,
      "risk_reward": 9.21,
      "support": 13.87,
      "resistance": 22.97,
      "atr": 1.37,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
      "final_score": 44.7,
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
        "光纤概念",
        "人形机器人",
        "先进制造风格",
        "融资融券",
        "新能源车",
        "数据中心",
        "电池技术",
        "智能电网"
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
      "stop_loss": 30.82,
      "target_price": 52.58,
      "risk_reward": 5.35,
      "support": 32.2,
      "resistance": 52.58,
      "atr": 3.51,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
      "final_score": 24.6,
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
        "国产芯片",
        "标准普尔",
        "小盘股",
        "小金属概念",
        "融资融券",
        "上证380",
        "半导体概念",
        "光伏概念"
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
        "四量终极": 1.76
      },
      "resonance": 1,
      "strength": 1.76,
      "final_score": 19.8,
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
        "通用设备制造业",
        "沪股通",
        "半导体概念",
        "百元股",
        "基金重仓",
        "专精特新",
        "中盘股",
        "融资融券"
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
      "final_score": 44.7,
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
        "光纤概念",
        "人形机器人",
        "先进制造风格",
        "融资融券",
        "新能源车",
        "数据中心",
        "电池技术",
        "智能电网"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 12.5,
      "target_price": 26.68,
      "risk_reward": 9.21,
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
      "final_score": 24.6,
      "mix_pct": 55.0,
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
        "国产芯片",
        "标准普尔",
        "小盘股",
        "小金属概念",
        "融资融券",
        "上证380",
        "半导体概念",
        "光伏概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 30.82,
      "target_price": 52.58,
      "risk_reward": 5.35,
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
      "final_score": 19.8,
      "mix_pct": 44.3,
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
        "通用设备制造业",
        "沪股通",
        "半导体概念",
        "百元股",
        "基金重仓",
        "专精特新",
        "中盘股",
        "融资融券"
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
      "final_score": 15.1,
      "mix_pct": 33.8,
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
        "国产芯片",
        "标准普尔",
        "光纤概念",
        "5G概念",
        "融资融券",
        "F5G概念",
        "上证380",
        "数据中心"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 25.35,
      "target_price": 45.24,
      "risk_reward": 6.06,
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
      "final_score": 14.0,
      "mix_pct": 31.3,
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
        "计算机、通信和其他电子设备制造业",
        "沪股通",
        "半导体概念",
        "存储芯片",
        "小盘股",
        "融资融券",
        "中芯概念"
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
      "final_score": 9.2,
      "mix_pct": 20.6,
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
        "病毒防治",
        "2026中报扭亏",
        "合成生物",
        "病原体防治",
        "专精特新",
        "创新药",
        "深股通",
        "锂电池概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 11.93,
      "target_price": 22.45,
      "risk_reward": 6.93,
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
      "final_score": 5.1,
      "mix_pct": 11.4,
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
        "信创",
        "小盘股",
        "融资融券",
        "小盘成长",
        "AI智能体",
        "财税数字化",
        "算力概念",
        "腾讯云"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 102.2,
      "target_price": 231.9,
      "risk_reward": 10.42,
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
      "final_score": 4.1,
      "mix_pct": 9.2,
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
        "国产芯片",
        "高带宽内存",
        "创业成份",
        "先进制造风格",
        "融资融券",
        "虚拟现实",
        "混合现实",
        "电池技术"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 108.0,
      "target_price": 243.26,
      "risk_reward": 10.27,
      "support": 119.0,
      "resistance": 218.92,
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
      "final_score": 3.1,
      "mix_pct": 6.9,
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
        "先进制造风格",
        "融资融券",
        "新能源车",
        "上证380",
        "西部大开发",
        "中证500",
        "中盘成长",
        "昨日高振幅"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 63.39,
      "target_price": 158.43,
      "risk_reward": 12.5,
      "support": 69.98,
      "resistance": 132.18,
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
      "final_score": 3.1,
      "mix_pct": 6.9,
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
        "信创",
        "新型工业化",
        "5G概念",
        "AH股",
        "融资融券",
        "F5G概念",
        "上证380",
        "科技风格"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 124.52,
      "target_price": 237.87,
      "risk_reward": 7.19,
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
      "final_score": 3.1,
      "mix_pct": 6.9,
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
      "stop_loss": 119.27,
      "target_price": 217.48,
      "risk_reward": 6.41,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "计算机、通信和其他电子设备制造业",
        "沪股通",
        "百元股",
        "专精特新",
        "CPO概念",
        "小盘股",
        "融资融券",
        "通信技术"
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "高压快充",
        "5G概念",
        "人形机器人",
        "小盘股",
        "融资融券",
        "新能源车",
        "上证380",
        "光伏概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 36.0,
      "target_price": 71.59,
      "risk_reward": 7.9,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "沪股通",
        "半导体概念",
        "TOPCon电池",
        "百元股",
        "光伏概念",
        "专精特新",
        "中盘股",
        "中盘成长"
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "非金属矿物制品业",
        "创业成份",
        "5G概念",
        "融资融券",
        "西部大开发",
        "风能",
        "中证500",
        "中盘成长"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 17.14,
      "target_price": 40.69,
      "risk_reward": 11.37,
      "support": 19.02,
      "resistance": 32.59,
      "factor_actions": []
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "创业成份",
        "融资融券",
        "新能源车",
        "科技风格",
        "电池技术",
        "中证500",
        "3D打印",
        "中盘成长"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 36.53,
      "target_price": 83.59,
      "risk_reward": 10.59,
      "support": 40.59,
      "resistance": 75.4,
      "factor_actions": []
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
      "final_score": 1.2,
      "mix_pct": 2.7,
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
        "大盘成长",
        "上证180",
        "大盘股",
        "沪股通",
        "半导体概念",
        "MSCI中国",
        "百元股",
        "专精特新"
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
        "6G概念",
        "国产芯片",
        "第三代半导体",
        "5G概念",
        "无人驾驶",
        "融资融券",
        "半导体概念",
        "中盘成长"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 23.83,
      "target_price": 41.8,
      "risk_reward": 5.79,
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
      "final_score": 0.2,
      "mix_pct": 0.4,
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
        "高压快充",
        "5G概念",
        "融资融券",
        "AI眼镜",
        "电池技术",
        "中盘成长",
        "锂电池概念",
        "深成500"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 32.33,
      "target_price": 67.87,
      "risk_reward": 8.89,
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
        "国产芯片",
        "光纤概念",
        "无人驾驶",
        "融资融券",
        "数据中心",
        "科技风格",
        "可控核聚变",
        "半导体概念"
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
        "大盘股",
        "国产芯片",
        "标准普尔",
        "5G概念",
        "深股通",
        "融资融券",
        "科技风格",
        "中特估"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 234.01,
      "target_price": 424.04,
      "risk_reward": 6.31,
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
        "创业成份",
        "氟化工概念",
        "先进制造风格",
        "融资融券",
        "新能源车",
        "电池技术",
        "半导体概念",
        "中证500"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 44.28,
      "target_price": 76.15,
      "risk_reward": 5.48,
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
        "昨日高振幅",
        "计算机、通信和其他电子设备制造业",
        "上证380",
        "MSCI中国",
        "央国企改革",
        "沪股通",
        "中证500"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 8.44,
      "target_price": 15.8,
      "risk_reward": 6.84,
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
        "国产芯片",
        "标准普尔",
        "光纤概念",
        "5G概念",
        "磁悬浮概念",
        "融资融券",
        "新能源车",
        "数据中心"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 22.77,
      "target_price": 47.59,
      "risk_reward": 8.81,
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
        "标准普尔",
        "钒电池",
        "昨日触板",
        "小金属概念",
        "融资融券",
        "电池技术",
        "西部大开发",
        "百日新高"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 27.41,
      "target_price": 43.29,
      "risk_reward": 4.22,
      "support": 29.58,
      "resistance": 37.36,
      "factor_actions": []
    },
    {
      "code": "300568",
      "name": "星源材质",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 12.64,
      "close_date": "2026-10-27",
      "close_verified": true,
      "pct_chg": -4.24,
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
      "industry": "化学原料和化学制品制造业",
      "concepts": [
        "破增发价股",
        "深股通",
        "AH股",
        "小盘股",
        "融资融券",
        "新能源车",
        "电池技术",
        "半导体概念"
      ],
      "enter_date": "2026-10-28",
      "stop_loss": 11.38,
      "target_price": 17.7,
      "risk_reward": 4.0,
      "support": 11.54,
      "resistance": 17.7,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-28 09:02:36",
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