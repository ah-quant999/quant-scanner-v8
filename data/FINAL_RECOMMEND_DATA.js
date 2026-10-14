window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-10-15 02:45:24",
  "crisis_score": 32.6,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 20,
  "top_n": 2,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-10-15 02:27:41",
    "degraded": false,
    "effective": {
      "jinzuan": 1.785,
      "chan": 1.136,
      "trend": -1.071,
      "jigou": -0.804
    },
    "hardcoded_default": {
      "jinzuan": 0.532,
      "chan": 0.759,
      "trend": -1.532,
      "jigou": -0.66
    },
    "n_on10": {
      "jinzuan": 172,
      "chan": 379,
      "trend": 271,
      "jigou": 473
    },
    "consistent": {
      "jinzuan": true,
      "chan": false,
      "trend": true,
      "jigou": true
    },
    "loaded": {
      "generated": "2026-10-15 02:27:41",
      "hit": 4,
      "n_snapshots": 84,
      "date_range": [
        "2026-06-06",
        "2026-10-15"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-10-14） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-10-14",
    "regime": "panic",
    "open": false,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "realflow_gate": {
    "source": "raw_data/four_volume_track.json::self_backtest.summary[5d]",
    "min_n": 30,
    "count": 81,
    "avg_return": -1.05,
    "win_rate": 34.57,
    "enabled": true,
    "note": ""
  },
  "ima_intake": {
    "data_date": "2026-10-13",
    "pool_total": 0,
    "new_selected": 0,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源；强度分与因子榜分各自池内 min-max 归一化到 0-100 后混排（两把标尺头部都=100，公平竞位，无席位偏向；同分时因子榜优先）",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-10-15",
    "source": "CANDIDATE_QUOTES",
    "covered": 17,
    "total": 20,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "公路铁路运输",
    "小金属",
    "影视院线",
    "文化传媒",
    "油气开采及服务",
    "港口航运",
    "游戏",
    "煤炭开采加工",
    "燃气",
    "证券",
    "贵金属",
    "银行"
  ],
  "stocks": [
    {
      "rank": 1,
      "code": "300857",
      "name": "协创数据",
      "market": "sz",
      "board": "创业板",
      "horizon": "短线",
      "close": 219.72,
      "close_date": "2026-10-15",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -3.63,
      "stop_loss": 197.75,
      "target_price": 278.6,
      "risk_reward": 2.68,
      "support": 213.11,
      "resistance": 278.6,
      "atr": 13.36,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.03
      },
      "resonance": 1,
      "strength": 2.03,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 12.8,
      "mix_pct": 100.0,
      "buy_score": 12.8,
      "enter_date": "2026-10-15",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "中证500",
        "创业成份",
        "AI智能体",
        "AIGC概念",
        "物联网",
        "百元股",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-10-15",
        "entry_price": 219.72,
        "latest_price": 219.72,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（四量真实流负 edge，见 realflow_gate）",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "601872",
      "name": "招商轮船",
      "market": "sh",
      "board": "主板",
      "horizon": "短线",
      "close": 21.48,
      "close_date": "2026-10-15",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 0.8,
      "stop_loss": 19.33,
      "target_price": 22.98,
      "risk_reward": 0.7,
      "support": 19.0,
      "resistance": 22.98,
      "atr": 1.4,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.56
      },
      "resonance": 1,
      "strength": 1.56,
      "sector_score": 0.0,
      "sector_hits": [],
      "sector_fund": [],
      "final_score": 11.7,
      "mix_pct": 81.7,
      "buy_score": 11.7,
      "enter_date": "2026-10-15",
      "signals": [
        "机构变红",
        "缠论买点"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "水上运输业",
      "concepts": [
        "沪股通",
        "融资融券",
        "昨日高振幅",
        "海洋经济",
        "央国企改革",
        "一带一路",
        "大盘价值",
        "MSCI中国"
      ],
      "tracking": {
        "entry_date": "2026-10-15",
        "entry_price": 21.48,
        "latest_price": 21.48,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（四量真实流负 edge，见 realflow_gate）",
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
      "close": 219.72,
      "close_date": "2026-10-15",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": -3.63,
      "stop_loss": 197.75,
      "target_price": 278.6,
      "risk_reward": 2.68,
      "support": 213.11,
      "resistance": 278.6,
      "atr": 13.36,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 2.03
      },
      "resonance": 1,
      "strength": 2.03,
      "final_score": 12.8,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-15",
      "signals": [
        "缠论买点",
        "金钻信号"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "中证500",
        "创业成份",
        "AI智能体",
        "AIGC概念",
        "物联网",
        "百元股",
        "深股通"
      ],
      "tracking": {
        "entry_date": "2026-10-15",
        "entry_price": 219.72,
        "latest_price": 219.72,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（四量真实流负 edge，见 realflow_gate）",
      "market_regime": "panic"
    },
    {
      "rank": 2,
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 21.48,
      "close_date": "2026-10-15",
      "close_source": "CANDIDATE_QUOTES",
      "close_verified": true,
      "pct_chg": 0.8,
      "stop_loss": 19.33,
      "target_price": 22.98,
      "risk_reward": 0.7,
      "support": 19.0,
      "resistance": 22.98,
      "atr": 1.4,
      "sources": [
        "四量终极"
      ],
      "source_scores": {
        "四量终极": 1.56
      },
      "resonance": 1,
      "strength": 1.56,
      "final_score": 11.7,
      "sector_score": 0.0,
      "sector_hits": [],
      "enter_date": "2026-10-15",
      "signals": [
        "缠论买点",
        "机构变红"
      ],
      "_60m_resonance": false,
      "reason": "四量终极 信号2项",
      "industry": "水上运输业",
      "concepts": [
        "沪股通",
        "融资融券",
        "昨日高振幅",
        "海洋经济",
        "央国企改革",
        "一带一路",
        "大盘价值",
        "MSCI中国"
      ],
      "tracking": {
        "entry_date": "2026-10-15",
        "entry_price": 21.48,
        "latest_price": 21.48,
        "return_pct": 0.0,
        "hold_days": 1,
        "exit_type": "hold",
        "note": "今日新入选，自动开始跟踪"
      },
      "action": "观察（四量真实流负 edge，见 realflow_gate）",
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
      "close": 219.72,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.63,
      "final_score": 12.8,
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
        "融资融券",
        "中证500",
        "创业成份",
        "AI智能体",
        "AIGC概念",
        "物联网",
        "百元股",
        "深股通"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 197.75,
      "target_price": 278.6,
      "risk_reward": 2.68,
      "support": 213.11,
      "resistance": 278.6,
      "factor_actions": []
    },
    {
      "code": "601872",
      "name": "招商轮船",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 21.48,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": 0.8,
      "final_score": 11.7,
      "mix_pct": 81.7,
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
        "沪股通",
        "融资融券",
        "昨日高振幅",
        "海洋经济",
        "央国企改革",
        "一带一路",
        "大盘价值",
        "MSCI中国"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 19.33,
      "target_price": 22.98,
      "risk_reward": 0.7,
      "support": 19.0,
      "resistance": 22.98,
      "factor_actions": []
    },
    {
      "code": "600601",
      "name": "方正科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 12.14,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": 0.33,
      "final_score": 11.5,
      "mix_pct": 78.3,
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
        "融资融券",
        "昨日高振幅",
        "沪股通",
        "5G概念",
        "华为概念",
        "计算机、通信和其他电子设备制造业",
        "上证380"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 10.93,
      "target_price": 15.8,
      "risk_reward": 3.01,
      "support": 11.04,
      "resistance": 15.8,
      "factor_actions": []
    },
    {
      "code": "601869",
      "name": "长飞光纤",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 357.4,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.53,
      "final_score": 9.4,
      "mix_pct": 43.3,
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
        "碳化硅",
        "第三代半导体",
        "中证500",
        "超清视频",
        "光纤概念",
        "海工装备",
        "百元股"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 321.66,
      "target_price": 483.8,
      "risk_reward": 3.54,
      "support": 342.34,
      "resistance": 483.8,
      "factor_actions": []
    },
    {
      "code": "300209",
      "name": "行云科技",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 34.36,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.89,
      "final_score": 9.4,
      "mix_pct": 43.3,
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
        "深股通",
        "纳米银",
        "互联网服务",
        "内贸流通",
        "人工智能",
        "创业板综",
        "跨境电商",
        "算力概念"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 30.92,
      "target_price": 41.0,
      "risk_reward": 1.93,
      "support": 29.5,
      "resistance": 38.87,
      "factor_actions": []
    },
    {
      "code": "600019",
      "name": "宝钢股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 6.01,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": 2.21,
      "final_score": 9.4,
      "mix_pct": 43.3,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [],
      "industry": "黑色金属冶炼和压延加工业",
      "concepts": [
        "融资融券",
        "一带一路",
        "证金持股",
        "周期股",
        "中特估",
        "MSCI中国",
        "上证180",
        "央国企改革"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 5.41,
      "target_price": 6.15,
      "risk_reward": 0.23,
      "support": 5.66,
      "resistance": 6.02,
      "factor_actions": []
    },
    {
      "code": "600498",
      "name": "烽火通信",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 30.86,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.98,
      "final_score": 9.1,
      "mix_pct": 38.3,
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
        "一带一路",
        "数据中心",
        "中证500",
        "网络安全",
        "光纤概念",
        "智慧城市",
        "数据要素"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 27.77,
      "target_price": 51.6,
      "risk_reward": 6.72,
      "support": 30.5,
      "resistance": 45.24,
      "factor_actions": []
    },
    {
      "code": "00291",
      "name": "华润啤酒",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 18.17,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": 0.0,
      "final_score": 8.8,
      "mix_pct": 33.3,
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
      "enter_date": "2026-10-15",
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
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -0.91,
      "final_score": 8.8,
      "mix_pct": 33.3,
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
      "enter_date": "2026-10-15",
      "stop_loss": 26.43,
      "target_price": 32.4,
      "risk_reward": 2.0,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "06862",
      "name": "海底捞",
      "market": "港股",
      "board": "港股",
      "horizon": "短线",
      "close": 9.65,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": 1.53,
      "final_score": 8.8,
      "mix_pct": 33.3,
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
      "enter_date": "2026-10-15",
      "stop_loss": 9.5,
      "target_price": 10.36,
      "risk_reward": 4.73,
      "support": null,
      "resistance": null,
      "factor_actions": []
    },
    {
      "code": "300548",
      "name": "长芯博创",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 186.56,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -2.47,
      "final_score": 8.0,
      "mix_pct": 20.0,
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
        "铜缆高速连接",
        "专精特新",
        "中证500",
        "创业成份",
        "中盘成长",
        "光纤概念",
        "百元股"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 167.9,
      "target_price": 247.8,
      "risk_reward": 3.28,
      "support": 170.33,
      "resistance": 247.8,
      "factor_actions": []
    },
    {
      "code": "300037",
      "name": "新宙邦",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 58.69,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -4.65,
      "final_score": 7.8,
      "mix_pct": 16.7,
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
        "氟化工概念",
        "锂电池概念",
        "中证500",
        "创业成份",
        "OLED",
        "固态电池",
        "深股通"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 52.82,
      "target_price": 76.45,
      "risk_reward": 3.03,
      "support": 58.5,
      "resistance": 76.45,
      "factor_actions": []
    },
    {
      "code": "600584",
      "name": "长电科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 58.65,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -2.51,
      "final_score": 7.5,
      "mix_pct": 11.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "汽车芯片",
        "IGBT概念",
        "智能穿戴",
        "华为海思",
        "物联网",
        "新材料",
        "计算机、通信和其他电子设备制造业"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 52.78,
      "target_price": 105.0,
      "risk_reward": 7.9,
      "support": 57.4,
      "resistance": 74.45,
      "factor_actions": []
    },
    {
      "code": "600105",
      "name": "永鼎股份",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 29.73,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -4.86,
      "final_score": 7.4,
      "mix_pct": 10.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "电气机械和器材制造业",
      "concepts": [
        "融资融券",
        "专精特新",
        "一带一路",
        "数据中心",
        "中证500",
        "中盘成长",
        "网络安全",
        "电气机械和器材制造业"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 26.76,
      "target_price": 49.84,
      "risk_reward": 6.76,
      "support": 28.89,
      "resistance": 47.59,
      "factor_actions": []
    },
    {
      "code": "600522",
      "name": "中天科技",
      "market": "沪市",
      "board": "主板",
      "horizon": "短线",
      "close": 27.67,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.66,
      "final_score": 7.4,
      "mix_pct": 10.0,
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
        "融资融券",
        "铜缆高速连接",
        "新能源",
        "一带一路",
        "证金持股",
        "数据中心",
        "机器人概念",
        "锂电池概念"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 24.9,
      "target_price": 43.37,
      "risk_reward": 5.67,
      "support": 27.45,
      "resistance": 38.48,
      "factor_actions": []
    },
    {
      "code": "300502",
      "name": "新易盛",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 330.8,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -5.84,
      "final_score": 7.2,
      "mix_pct": 6.7,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "西部大开发",
        "创业成份",
        "机构重仓",
        "百元股",
        "深股通",
        "大盘成长",
        "5G概念"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 297.72,
      "target_price": 579.42,
      "risk_reward": 7.52,
      "support": 329.12,
      "resistance": 475.0,
      "factor_actions": []
    },
    {
      "code": "688498",
      "name": "源杰科技",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 1118.89,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.79,
      "final_score": 7.1,
      "mix_pct": 5.0,
      "resonance": 1,
      "sources": [
        "四量终极"
      ],
      "signals": [
        "金钻信号"
      ],
      "industry": "计算机、通信和其他电子设备制造业",
      "concepts": [
        "融资融券",
        "西部大开发",
        "中证500",
        "光纤概念",
        "百元股",
        "大盘成长",
        "计算机、通信和其他电子设备制造业",
        "MSCI中国"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 1007.0,
      "target_price": 1918.0,
      "risk_reward": 7.14,
      "support": 1053.15,
      "resistance": 1887.0,
      "factor_actions": []
    },
    {
      "code": "688036",
      "name": "传音控股",
      "market": "沪市",
      "board": "科创板",
      "horizon": "短线",
      "close": 48.29,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -1.33,
      "final_score": 6.9,
      "mix_pct": 1.7,
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
        "AIPC",
        "深圳特区",
        "股权激励",
        "DeepSeek概念",
        "计算机、通信和其他电子设备制造业",
        "一带一路"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 43.46,
      "target_price": 67.71,
      "risk_reward": 4.02,
      "support": 45.26,
      "resistance": 57.17,
      "factor_actions": []
    },
    {
      "code": "002281",
      "name": "光迅科技",
      "market": "深市",
      "board": "主板",
      "horizon": "短线",
      "close": 141.09,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -3.27,
      "final_score": 6.9,
      "mix_pct": 1.7,
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
        "一带一路",
        "数据中心",
        "中证500",
        "抖音概念(字节概念)",
        "光纤概念",
        "百元股",
        "深股通"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 126.98,
      "target_price": 233.62,
      "risk_reward": 6.56,
      "support": 132.7,
      "resistance": 199.48,
      "factor_actions": []
    },
    {
      "code": "300394",
      "name": "天孚通信",
      "market": "深市",
      "board": "创业板",
      "horizon": "短线",
      "close": 229.0,
      "close_date": "2026-10-15",
      "close_verified": true,
      "pct_chg": -7.17,
      "final_score": 6.8,
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
        "专精特新",
        "创业成份",
        "光纤概念",
        "百元股",
        "深股通",
        "大盘成长",
        "5G概念"
      ],
      "enter_date": "2026-10-15",
      "stop_loss": 206.1,
      "target_price": 294.5,
      "risk_reward": 2.86,
      "support": 217.01,
      "resistance": 292.07,
      "factor_actions": []
    }
  ],
  "factor_chain": {
    "update_time": "2026-10-15 02:45:23",
    "score_formula": "final_score = 因子榜 TOP10_DAILY.total_score（2026-09-20 唯一口径：第二套 final_score 公式已整段清除）",
    "where": "algorithms/final_recommend.py :: 方案B 因子融合",
    "gate": {
      "V8_FUSION_NOISE_FILTER": 1,
      "regime_open": false
    },
    "integrated": [],
    "skipped": true,
    "skip_reason": "本轮 FACTOR_LAB.js 缺失/内容陈旧 ⇒ 方案B 因子融合整体跳过（数据降级）"
  },
  "factor_trace": []
};