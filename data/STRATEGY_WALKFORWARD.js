window.STRATEGY_WALKFORWARD = {
  "update_time": "2026-10-26 07:54:17",
  "source": "raw_data/history/final_recommend_*.json（41 个每日快照）",
  "method": "因子清账 + 胜率加权 组合的【样本外选股稳定性】walk-forward（非收益率 OOS，历史快照无已实现盈亏）",
  "is_ratio": 0.7,
  "is_window": {
    "n": 28,
    "overlap_ratio": 0.496,
    "industry_hhi": 0.351,
    "max_industry_pct": 45.714,
    "avg_final_score": 15.272
  },
  "oos_window": {
    "n": 13,
    "overlap_ratio": 0.485,
    "industry_hhi": 0.752,
    "max_industry_pct": 76.923,
    "avg_final_score": 24.545
  },
  "verdict": "样本外需关注 ⚠️",
  "stable": false,
  "metric_notes": {
    "overlap_ratio": "当日 top_n 与次日 top_n 重合比例（稳定性代理；越高=方法越一致）",
    "industry_hhi": "行业集中度（赫芬达尔，1/n→1；越高=越押单一行业）",
    "max_industry_pct": "当日最大单一行业占比（对应「同行业≤30%」闸；>30 即触发约束）",
    "avg_final_score": "当日平均 final_score"
  },
  "rolling": [
    {
      "date": "20260903",
      "overlap_ratio": 0.4,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0
    },
    {
      "date": "20260904",
      "overlap_ratio": 0.7,
      "industry_hhi": 0.24,
      "max_industry_pct": 30.0
    },
    {
      "date": "20260905",
      "overlap_ratio": 0.6,
      "industry_hhi": 0.2267,
      "max_industry_pct": 26.7
    },
    {
      "date": "20260907",
      "overlap_ratio": 0.55,
      "industry_hhi": 0.22,
      "max_industry_pct": 25.0
    },
    {
      "date": "20260908",
      "overlap_ratio": 0.48,
      "industry_hhi": 0.264,
      "max_industry_pct": 32.0
    },
    {
      "date": "20260910",
      "overlap_ratio": 0.4,
      "industry_hhi": 0.2667,
      "max_industry_pct": 33.3
    },
    {
      "date": "20260911",
      "overlap_ratio": 0.414,
      "industry_hhi": 0.3714,
      "max_industry_pct": 42.9
    },
    {
      "date": "20260912",
      "overlap_ratio": 0.413,
      "industry_hhi": 0.36,
      "max_industry_pct": 42.5
    },
    {
      "date": "20260914",
      "overlap_ratio": 0.433,
      "industry_hhi": 0.3511,
      "max_industry_pct": 42.2
    },
    {
      "date": "20260915",
      "overlap_ratio": 0.41,
      "industry_hhi": 0.336,
      "max_industry_pct": 40.0
    },
    {
      "date": "20260916",
      "overlap_ratio": 0.43,
      "industry_hhi": 0.352,
      "max_industry_pct": 42.0
    },
    {
      "date": "20260917",
      "overlap_ratio": 0.39,
      "industry_hhi": 0.36,
      "max_industry_pct": 44.0
    },
    {
      "date": "20260918",
      "overlap_ratio": 0.43,
      "industry_hhi": 0.368,
      "max_industry_pct": 46.0
    },
    {
      "date": "20260919",
      "overlap_ratio": 0.41,
      "industry_hhi": 0.376,
      "max_industry_pct": 48.0
    },
    {
      "date": "20260920",
      "overlap_ratio": 0.45,
      "industry_hhi": 0.376,
      "max_industry_pct": 48.0
    },
    {
      "date": "20260921",
      "overlap_ratio": 0.53,
      "industry_hhi": 0.376,
      "max_industry_pct": 48.0
    },
    {
      "date": "20260922",
      "overlap_ratio": 0.52,
      "industry_hhi": 0.304,
      "max_industry_pct": 42.0
    },
    {
      "date": "20260923",
      "overlap_ratio": 0.54,
      "industry_hhi": 0.304,
      "max_industry_pct": 42.0
    },
    {
      "date": "20260924",
      "overlap_ratio": 0.58,
      "industry_hhi": 0.32,
      "max_industry_pct": 44.0
    },
    {
      "date": "20260925",
      "overlap_ratio": 0.64,
      "industry_hhi": 0.344,
      "max_industry_pct": 48.0
    },
    {
      "date": "20260928",
      "overlap_ratio": 0.66,
      "industry_hhi": 0.344,
      "max_industry_pct": 48.0
    },
    {
      "date": "20260929",
      "overlap_ratio": 0.68,
      "industry_hhi": 0.384,
      "max_industry_pct": 52.0
    },
    {
      "date": "20260930",
      "overlap_ratio": 0.62,
      "industry_hhi": 0.4,
      "max_industry_pct": 54.0
    },
    {
      "date": "20261001",
      "overlap_ratio": 0.6,
      "industry_hhi": 0.4,
      "max_industry_pct": 54.0
    },
    {
      "date": "20261009",
      "overlap_ratio": 0.6,
      "industry_hhi": 0.384,
      "max_industry_pct": 52.0
    },
    {
      "date": "20261010",
      "overlap_ratio": 0.6,
      "industry_hhi": 0.392,
      "max_industry_pct": 52.0
    },
    {
      "date": "20261011",
      "overlap_ratio": 0.58,
      "industry_hhi": 0.392,
      "max_industry_pct": 52.0
    },
    {
      "date": "20261012",
      "overlap_ratio": 0.52,
      "industry_hhi": 0.392,
      "max_industry_pct": 52.0
    },
    {
      "date": "20261013",
      "overlap_ratio": 0.5,
      "industry_hhi": 0.448,
      "max_industry_pct": 56.0
    },
    {
      "date": "20261014",
      "overlap_ratio": 0.42,
      "industry_hhi": 0.504,
      "max_industry_pct": 60.0
    },
    {
      "date": "20261015",
      "overlap_ratio": 0.39,
      "industry_hhi": 0.51,
      "max_industry_pct": 59.0
    },
    {
      "date": "20261016",
      "overlap_ratio": 0.36,
      "industry_hhi": 0.492,
      "max_industry_pct": 56.0
    },
    {
      "date": "20261017",
      "overlap_ratio": 0.44,
      "industry_hhi": 0.548,
      "max_industry_pct": 60.0
    },
    {
      "date": "20261018",
      "overlap_ratio": 0.49,
      "industry_hhi": 0.62,
      "max_industry_pct": 66.0
    },
    {
      "date": "20261019",
      "overlap_ratio": 0.497,
      "industry_hhi": 0.692,
      "max_industry_pct": 72.0
    },
    {
      "date": "20261020",
      "overlap_ratio": 0.45,
      "industry_hhi": 0.756,
      "max_industry_pct": 78.0
    },
    {
      "date": "20261021",
      "overlap_ratio": 0.463,
      "industry_hhi": 0.828,
      "max_industry_pct": 84.0
    },
    {
      "date": "20261022",
      "overlap_ratio": 0.463,
      "industry_hhi": 0.8556,
      "max_industry_pct": 86.7
    },
    {
      "date": "20261023",
      "overlap_ratio": 0.483,
      "industry_hhi": 0.7889,
      "max_industry_pct": 80.0
    },
    {
      "date": "20261024",
      "overlap_ratio": 0.55,
      "industry_hhi": 0.7222,
      "max_industry_pct": 73.3
    },
    {
      "date": "20261025",
      "overlap_ratio": 0.5,
      "industry_hhi": 0.7278,
      "max_industry_pct": 75.0
    }
  ],
  "rows": [
    {
      "date": "20260903",
      "n": 5,
      "overlap": 2,
      "overlap_ratio": 0.4,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 5.16
    },
    {
      "date": "20260904",
      "n": 5,
      "overlap": 5,
      "overlap_ratio": 1.0,
      "industry_hhi": 0.2,
      "max_industry_pct": 20.0,
      "avg_final_score": 5.68
    },
    {
      "date": "20260905",
      "n": 5,
      "overlap": 2,
      "overlap_ratio": 0.4,
      "industry_hhi": 0.2,
      "max_industry_pct": 20.0,
      "avg_final_score": 5.68
    },
    {
      "date": "20260907",
      "n": 5,
      "overlap": 2,
      "overlap_ratio": 0.4,
      "industry_hhi": 0.2,
      "max_industry_pct": 20.0,
      "avg_final_score": 5.58
    },
    {
      "date": "20260908",
      "n": 5,
      "overlap": 1,
      "overlap_ratio": 0.2,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 5.42
    },
    {
      "date": "20260910",
      "n": 5,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 3.38
    },
    {
      "date": "20260911",
      "n": 2,
      "overlap": 1,
      "overlap_ratio": 0.5,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 4.78
    },
    {
      "date": "20260912",
      "n": 5,
      "overlap": 2,
      "overlap_ratio": 0.4,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 5.22
    },
    {
      "date": "20260914",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 6.91
    },
    {
      "date": "20260915",
      "n": 5,
      "overlap": 1,
      "overlap_ratio": 0.2,
      "industry_hhi": 0.2,
      "max_industry_pct": 20.0,
      "avg_final_score": 6.64
    },
    {
      "date": "20260916",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 5.64
    },
    {
      "date": "20260917",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 7.02
    },
    {
      "date": "20260918",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 6.57
    },
    {
      "date": "20260919",
      "n": 5,
      "overlap": 1,
      "overlap_ratio": 0.2,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 6.53
    },
    {
      "date": "20260920",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 35.66
    },
    {
      "date": "20260921",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 34.9
    },
    {
      "date": "20260922",
      "n": 5,
      "overlap": 2,
      "overlap_ratio": 0.4,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 32.34
    },
    {
      "date": "20260923",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 29.94
    },
    {
      "date": "20260924",
      "n": 5,
      "overlap": 5,
      "overlap_ratio": 1.0,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 26.72
    },
    {
      "date": "20260925",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 25.6
    },
    {
      "date": "20260928",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 28.34
    },
    {
      "date": "20260929",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.68,
      "max_industry_pct": 80.0,
      "avg_final_score": 27.55
    },
    {
      "date": "20260930",
      "n": 5,
      "overlap": 1,
      "overlap_ratio": 0.2,
      "industry_hhi": 0.44,
      "max_industry_pct": 60.0,
      "avg_final_score": 31.7
    },
    {
      "date": "20261001",
      "n": 5,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 12.64
    },
    {
      "date": "20261009",
      "n": 5,
      "overlap": 3,
      "overlap_ratio": 0.6,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 20.4
    },
    {
      "date": "20261010",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 0.36,
      "max_industry_pct": 40.0,
      "avg_final_score": 16.84
    },
    {
      "date": "20261011",
      "n": 5,
      "overlap": 1,
      "overlap_ratio": 0.2,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 12.74
    },
    {
      "date": "20261012",
      "n": 5,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 0.28,
      "max_industry_pct": 40.0,
      "avg_final_score": 12.04
    },
    {
      "date": "20261013",
      "n": 5,
      "overlap": 4,
      "overlap_ratio": 0.8,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 15.88
    },
    {
      "date": "20261014",
      "n": 5,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 16.2
    },
    {
      "date": "20261015",
      "n": 2,
      "overlap": 1,
      "overlap_ratio": 0.5,
      "industry_hhi": 0.5,
      "max_industry_pct": 50.0,
      "avg_final_score": 12.75
    },
    {
      "date": "20261016",
      "n": 2,
      "overlap": 1,
      "overlap_ratio": 0.5,
      "industry_hhi": 0.5,
      "max_industry_pct": 50.0,
      "avg_final_score": 53.45
    },
    {
      "date": "20261017",
      "n": 2,
      "overlap": 2,
      "overlap_ratio": 1.0,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 19.65
    },
    {
      "date": "20261018",
      "n": 2,
      "overlap": 1,
      "overlap_ratio": 0.5,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 19.65
    },
    {
      "date": "20261019",
      "n": 3,
      "overlap": 2,
      "overlap_ratio": 0.667,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 21.7
    },
    {
      "date": "20261020",
      "n": 3,
      "overlap": 1,
      "overlap_ratio": 0.333,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 17.77
    },
    {
      "date": "20261021",
      "n": 3,
      "overlap": 1,
      "overlap_ratio": 0.333,
      "industry_hhi": 1.0,
      "max_industry_pct": 100.0,
      "avg_final_score": 21.43
    },
    {
      "date": "20261022",
      "n": 3,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 0.5556,
      "max_industry_pct": 66.7,
      "avg_final_score": 14.27
    },
    {
      "date": "20261023",
      "n": 3,
      "overlap": 3,
      "overlap_ratio": 1.0,
      "industry_hhi": 0.3333,
      "max_industry_pct": 33.3,
      "avg_final_score": 37.43
    },
    {
      "date": "20261024",
      "n": 3,
      "overlap": 2,
      "overlap_ratio": 0.667,
      "industry_hhi": 0.3333,
      "max_industry_pct": 33.3,
      "avg_final_score": 37.57
    },
    {
      "date": "20261025",
      "n": 3,
      "overlap": 0,
      "overlap_ratio": 0.0,
      "industry_hhi": 0.5556,
      "max_industry_pct": 66.7,
      "avg_final_score": 31.33
    }
  ]
};