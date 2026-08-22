window.ALGO_BACKTEST_COMPARE = {
 "generated": "2026-08-23 07:33:13",
 "metrics_def": "胜率=收益>0占比; 平均收益=收益均值%; 命中率=收益>=5%占比",
 "algorithms": {
  "h_reverse": {
   "name": "H 反推短线买点",
   "rule": "涨幅≥3% + 量比≥1.2（PDF 提取算法）",
   "source": "H_AUTO_BUY_TRACK",
   "summary": null
  },
  "strong_breakout": {
   "name": "强势突破（H反推升级）",
   "rule": "涨幅≥3% + 量比≥1.2 + 突破前高 + RS前25%",
   "source": "STOCK_MOMENTUM_STATE_V2",
   "summary": {
    "n_samples": 421,
    "horizons": {
     "t5": {
      "n": 421,
      "win": 39.9,
      "avg": -1.03,
      "hit": 22.1
     }
    }
   }
  }
 },
 "verdict": "H 反推暂无历史样本；强势突破已就绪，等待 H 反推累积后对比。"
};
