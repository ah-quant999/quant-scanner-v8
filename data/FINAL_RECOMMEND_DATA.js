window.FINAL_RECOMMEND_DATA = {
  "update_time": "2026-11-10 19:32:43",
  "crisis_score": 33.3,
  "crisis_high": false,
  "crisis_note": "逆势龙头已于 2026-10-11 下架，不再并入最终推荐",
  "total_candidates": 0,
  "top_n": 3,
  "data_degraded": true,
  "signal_edge": {
    "source": "backtest_expectancy@2026-11-10 17:59:29",
    "degraded": false,
    "effective": {
      "jinzuan": -0.848,
      "chan": 0.038,
      "trend": 0.533,
      "jigou": 0.628
    },
    "hardcoded_default": {
      "jinzuan": -0.522,
      "chan": 0.155,
      "trend": 0.339,
      "jigou": 0.449
    },
    "n_on10": {
      "jinzuan": 491,
      "chan": 702,
      "trend": 275,
      "jigou": 501
    },
    "consistent": {
      "jinzuan": true,
      "chan": true,
      "trend": false,
      "jigou": false
    },
    "loaded": {
      "generated": "2026-11-10 17:59:29",
      "hit": 4,
      "n_snapshots": 105,
      "date_range": [
        "2026-06-06",
        "2026-11-09"
      ]
    },
    "alpha_select": {
      "enabled": true,
      "skipped_no_positive_edge": 0
    }
  },
  "degrade_note": "⚠️ 数据降级：因子实验室（FACTOR_LAB.js）未达数据日（实际 data_date=2026-11-09） ⇒ 方案B 因子融合整体跳过。本结果为「降级放行」产物 —— 排序与信号有效，但上述环节未达最新口径。请对照产物内 factor_chain / signal_edge 元数据判断适用范围。",
  "market_regime": {
    "date": "2026-11-10",
    "regime": "panic",
    "open": true,
    "ok": true,
    "reason": "ok",
    "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）"
  },
  "ima_intake": {
    "data_date": "2026-11-06",
    "pool_total": 0,
    "new_selected": 0,
    "rule": "first_selected==data_date（当日新入选）⇒ 入池独立源（展示+候选池）；2026-10-20 起不参与 Top3 竞位——最终推荐严格=当日因子榜前 N 名（同序同分），进最终推荐须先入因子榜",
    "note": "09-18 walk-forward 曾测「高手跟踪」作四量加分项边际 −1.76pp（n=13、回放口径、四量池上下文）——与本处「IMA 自身信号真实流」非同口径同场景，如实并列不隐瞒；回退开关 V8_IMA_INTAKE=0"
  },
  "price_source": {
    "date": "2026-11-10",
    "source": "STOCK_QUOTE",
    "covered": 0,
    "total": 0,
    "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%"
  },
  "strong_sectors": [
    "光伏设备",
    "半导体",
    "厨卫电器",
    "小金属",
    "影视院线",
    "文化传媒",
    "电池",
    "种植业与林业",
    "贵金属",
    "风电设备"
  ],
  "stocks": [],
  "consensus_stocks": [],
  "all_candidates": [],
  "factor_chain": {
    "update_time": "2026-11-10 19:32:43",
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