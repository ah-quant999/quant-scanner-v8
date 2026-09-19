window.ALGO_BACKTEST_COMPARE = {
 "generated": "2026-09-19 11:50:35",
 "metrics_def": "胜率=收益>0占比; 平均收益=收益均值%; 命中率=收益>=5%占比",
 "algorithms": {
  "h_reverse": {
   "name": "H 反推短线买点",
   "rule": "涨幅≥3% + 量比≥1.2（PDF 提取算法）",
   "source": "H_AUTO_BUY_TRACK.by_date",
   "summary": {
    "n_samples": 397,
    "horizons": {
     "t1": {
      "n": 397,
      "win": 38.8,
      "avg": -0.33,
      "hit": 9.6
     },
     "t3": {
      "n": 150,
      "win": 28.0,
      "avg": -0.85,
      "hit": 9.3
     },
     "t5": {
      "n": 149,
      "win": 36.2,
      "avg": -0.3,
      "hit": 12.8
     }
    }
   }
  },
  "h_reverse_expert": {
   "name": "高手画像版H反推",
   "rule": "涨幅≥3% + 量比≥1.2 + 价格<15 + 主板 + 医药/化工/贵金属/农业",
   "source": "H_AUTO_BUY_TRACK.expert_by_date",
   "summary": {
    "n_samples": 48,
    "horizons": {
     "t1": {
      "n": 48,
      "win": 27.1,
      "avg": -0.82,
      "hit": 10.4
     },
     "t3": {
      "n": 24,
      "win": 33.3,
      "avg": 1.03,
      "hit": 20.8
     },
     "t5": {
      "n": 24,
      "win": 62.5,
      "avg": 5.74,
      "hit": 33.3
     }
    }
   }
  },
  "strong_breakout": {
   "name": "强势突破（H反推升级）",
   "rule": "涨幅≥3% + 量比≥1.2 + 突破前高 + RS前25%",
   "source": "STOCK_MOMENTUM_STATE_V2",
   "summary": {
    "n_samples": 132,
    "horizons": {
     "t1": {
      "n": 132,
      "win": 11.4,
      "avg": 0.13,
      "hit": 5.3
     },
     "t3": {
      "n": 132,
      "win": 15.9,
      "avg": 0.99,
      "hit": 9.8
     },
     "t5": {
      "n": 132,
      "win": 14.4,
      "avg": 1.07,
      "hit": 9.1
     },
     "t10": {
      "n": 132,
      "win": 15.9,
      "avg": 1.3,
      "hit": 10.6
     }
    }
   }
  }
 },
 "verdict": "T+5 胜率：高手画像版H反推（62.5%）> H 反推（36.2%） > 强势突破（14.4%）；T+5 平均收益：高手画像版H反推（+5.74%）> 强势突破（+1.07%） > H 反推（+-0.3%）"
};
