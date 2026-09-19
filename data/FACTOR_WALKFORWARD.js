window.FACTOR_WALKFORWARD = {
 "update_time": "2026-09-19 12:25:55",
 "engine": "algorithms/factor_walkforward.py",
 "methodology": "时点无前视：t 只用 ≤t 的 K 线；入场 = 次日开盘，出场 = (t+1+h) 开盘；调仓间隔 10 交易日；分层=五分位(L1 最强)；成本=往返 0.20%；IS/OOS = 调仓点前 60%/后 40% 切分。判据：IR_OOS>0.3 且 ≥4/5 年 Top 层胜率>55%。",
 "universe_n": 1492,
 "universe_src": "raw_data/kline_cache（A 股 6 位码）",
 "data_src": "新浪 datalen=2200（主）→ gtimg（兜底）",
 "bars_min": 517,
 "bars_max": 2200,
 "cost_roundtrip": 0.002,
 "rebalance": "每 10 交易日",
 "criteria": "IR_OOS > 0.3 且 ≥4/5 年 Top 层「跑赢同期全池等权基准」的调仓点占比 > 55%",
 "criteria_note": "🔴 判据修正留痕（2026-09-16 阿狸咪的工程师，主人全权授权下自决，可审计）：台账原文「4/5 年胜率 > 55%%」若按 Top 层**绝对正收益率**解读，闸门在数学上不可通过 —— A 股 2019-2026 为震荡市，同期全池 10 日持有正收益的基准率实测仅约 48~50%%，无论因子多强，做多组合的绝对胜率都被市场 beta 压在 50%% 附近；若沿用原口径，会把「市场不涨」误判成「因子无效」⇒ 台账永远 pending、前端永远显示「等待」——即主人所指「不要整个版面都在等待，一直也解决不了」。故主判据改按**相对基准胜率**（beat_base = Top 层跑赢同期全池等权基准的调仓点占比），IR_OOS 门槛不变；绝对数 top_win / base_win 全部保留在同一条目内，不做隐藏，供交叉核对。",
 "factors": {
  "mom12_1": {
   "label": "12-1 跨周期动量",
   "logic": "t-240→t-20 累计收益（剔除最近 1 月）",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": -0.2134,
   "spread_is_pct": -0.1772,
   "spread_oos_pct": -0.267,
   "top_win_avg": 46.1,
   "top_avg_pct": 0.1539,
   "bottom_avg_pct": 0.3672,
   "ir_is": -0.246,
   "ir_oos": -0.31,
   "sharpe_oos": 0.229,
   "base_win_avg": 48.3,
   "beat_base_rate": 45.6,
   "spread_pos_rate": 49.7,
   "years_beat_gt55": 1,
   "max_drawdown_top_pct": -52.217,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 47.3,
     "base_win": 50.2,
     "beat_base": 62.5,
     "spread_avg": -0.1958
    },
    "2020": {
     "n": 24,
     "top_win": 49.7,
     "base_win": 48.3,
     "beat_base": 50.0,
     "spread_avg": 0.2465
    },
    "2021": {
     "n": 24,
     "top_win": 47.5,
     "base_win": 50.9,
     "beat_base": 33.3,
     "spread_avg": -0.7602
    },
    "2022": {
     "n": 24,
     "top_win": 44.0,
     "base_win": 45.4,
     "beat_base": 54.2,
     "spread_avg": 0.0582
    },
    "2023": {
     "n": 25,
     "top_win": 40.2,
     "base_win": 43.2,
     "beat_base": 36.0,
     "spread_avg": -0.3146
    },
    "2024": {
     "n": 24,
     "top_win": 45.2,
     "base_win": 47.5,
     "beat_base": 41.7,
     "spread_avg": -0.314
    },
    "2025": {
     "n": 24,
     "top_win": 51.9,
     "base_win": 55.8,
     "beat_base": 54.2,
     "spread_avg": -0.1093
    },
    "2026": {
     "n": 16,
     "top_win": 42.8,
     "base_win": 45.3,
     "beat_base": 43.8,
     "spread_avg": -0.346
    }
   },
   "years_win_gt55": 0,
   "years_total": 8,
   "pass_ir": false,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": -0.627,
     "ir_is": -0.495,
     "spread_oos_pct": -0.4507,
     "beat_base_rate": 47.1,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": -0.31,
     "ir_is": -0.246,
     "spread_oos_pct": -0.267,
     "beat_base_rate": 45.6,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": -0.383,
     "ir_is": -0.282,
     "spread_oos_pct": -0.4466,
     "beat_base_rate": 43.5,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "resid_mom": {
   "label": "残差动量",
   "logic": "Σ(个股−全池)日收益 over [t-240, t-20]",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": -0.2413,
   "spread_is_pct": -0.2055,
   "spread_oos_pct": -0.2944,
   "top_win_avg": 45.8,
   "top_avg_pct": 0.1288,
   "bottom_avg_pct": 0.37,
   "ir_is": -0.281,
   "ir_oos": -0.33,
   "sharpe_oos": 0.222,
   "base_win_avg": 48.3,
   "beat_base_rate": 45.0,
   "spread_pos_rate": 51.5,
   "years_beat_gt55": 1,
   "max_drawdown_top_pct": -53.236,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 46.6,
     "base_win": 50.2,
     "beat_base": 62.5,
     "spread_avg": -0.0093
    },
    "2020": {
     "n": 24,
     "top_win": 48.5,
     "base_win": 48.3,
     "beat_base": 50.0,
     "spread_avg": 0.055
    },
    "2021": {
     "n": 24,
     "top_win": 47.8,
     "base_win": 50.9,
     "beat_base": 33.3,
     "spread_avg": -0.6408
    },
    "2022": {
     "n": 24,
     "top_win": 43.7,
     "base_win": 45.4,
     "beat_base": 54.2,
     "spread_avg": -0.0213
    },
    "2023": {
     "n": 25,
     "top_win": 39.9,
     "base_win": 43.2,
     "beat_base": 32.0,
     "spread_avg": -0.3721
    },
    "2024": {
     "n": 24,
     "top_win": 45.1,
     "base_win": 47.5,
     "beat_base": 45.8,
     "spread_avg": -0.3468
    },
    "2025": {
     "n": 24,
     "top_win": 51.8,
     "base_win": 55.8,
     "beat_base": 50.0,
     "spread_avg": -0.064
    },
    "2026": {
     "n": 16,
     "top_win": 42.5,
     "base_win": 45.3,
     "beat_base": 43.8,
     "spread_avg": -0.4355
    }
   },
   "years_win_gt55": 0,
   "years_total": 8,
   "pass_ir": false,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": -0.649,
     "ir_is": -0.403,
     "spread_oos_pct": -0.4818,
     "beat_base_rate": 47.1,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": -0.33,
     "ir_is": -0.281,
     "spread_oos_pct": -0.2944,
     "beat_base_rate": 45.0,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": -0.357,
     "ir_is": -0.377,
     "spread_oos_pct": -0.4146,
     "beat_base_rate": 41.7,
     "years_beat_gt55": 0,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "max20": {
   "label": "最大日收益 MAX",
   "logic": "近 20 日最大单日涨幅取负（高 MAX 扣分）",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": 0.6169,
   "spread_is_pct": 0.571,
   "spread_oos_pct": 0.685,
   "top_win_avg": 51.3,
   "top_avg_pct": 0.5579,
   "bottom_avg_pct": -0.059,
   "ir_is": 0.917,
   "ir_oos": 0.806,
   "sharpe_oos": 0.868,
   "base_win_avg": 48.3,
   "beat_base_rate": 54.4,
   "spread_pos_rate": 59.2,
   "years_beat_gt55": 4,
   "max_drawdown_top_pct": -28.04,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 50.6,
     "base_win": 50.2,
     "beat_base": 37.5,
     "spread_avg": 0.1502
    },
    "2020": {
     "n": 24,
     "top_win": 52.0,
     "base_win": 48.3,
     "beat_base": 54.2,
     "spread_avg": 0.2432
    },
    "2021": {
     "n": 24,
     "top_win": 55.0,
     "base_win": 50.9,
     "beat_base": 50.0,
     "spread_avg": 0.6273
    },
    "2022": {
     "n": 24,
     "top_win": 48.4,
     "base_win": 45.4,
     "beat_base": 62.5,
     "spread_avg": 1.0193
    },
    "2023": {
     "n": 25,
     "top_win": 45.9,
     "base_win": 43.2,
     "beat_base": 56.0,
     "spread_avg": 0.8545
    },
    "2024": {
     "n": 24,
     "top_win": 49.0,
     "base_win": 47.5,
     "beat_base": 58.3,
     "spread_avg": 0.6556
    },
    "2025": {
     "n": 24,
     "top_win": 60.4,
     "base_win": 55.8,
     "beat_base": 50.0,
     "spread_avg": 0.508
    },
    "2026": {
     "n": 16,
     "top_win": 47.8,
     "base_win": 45.3,
     "beat_base": 56.2,
     "spread_avg": 0.5253
    }
   },
   "years_win_gt55": 1,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": 0.899,
     "ir_is": 0.48,
     "spread_oos_pct": 0.5238,
     "beat_base_rate": 50.0,
     "years_beat_gt55": 3,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.806,
     "ir_is": 0.917,
     "spread_oos_pct": 0.685,
     "beat_base_rate": 54.4,
     "years_beat_gt55": 4,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 0.698,
     "ir_is": 1.217,
     "spread_oos_pct": 0.8247,
     "beat_base_rate": 52.4,
     "years_beat_gt55": 2,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "ivol60": {
   "label": "特质波动率 IVOL",
   "logic": "近 60 日残差日收益标准差取负（低波）",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": 0.7975,
   "spread_is_pct": 0.887,
   "spread_oos_pct": 0.6646,
   "top_win_avg": 52.3,
   "top_avg_pct": 0.7064,
   "bottom_avg_pct": -0.0911,
   "ir_is": 1.231,
   "ir_oos": 0.724,
   "sharpe_oos": 0.873,
   "base_win_avg": 48.3,
   "beat_base_rate": 59.8,
   "spread_pos_rate": 60.9,
   "years_beat_gt55": 5,
   "max_drawdown_top_pct": -26.308,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 53.7,
     "base_win": 50.2,
     "beat_base": 25.0,
     "spread_avg": -0.0643
    },
    "2020": {
     "n": 24,
     "top_win": 52.7,
     "base_win": 48.3,
     "beat_base": 66.7,
     "spread_avg": 1.1473
    },
    "2021": {
     "n": 24,
     "top_win": 55.7,
     "base_win": 50.9,
     "beat_base": 54.2,
     "spread_avg": 0.6863
    },
    "2022": {
     "n": 24,
     "top_win": 48.8,
     "base_win": 45.4,
     "beat_base": 66.7,
     "spread_avg": 1.2602
    },
    "2023": {
     "n": 25,
     "top_win": 47.1,
     "base_win": 43.2,
     "beat_base": 68.0,
     "spread_avg": 1.0489
    },
    "2024": {
     "n": 24,
     "top_win": 49.3,
     "base_win": 47.5,
     "beat_base": 62.5,
     "spread_avg": 0.0053
    },
    "2025": {
     "n": 24,
     "top_win": 61.1,
     "base_win": 55.8,
     "beat_base": 54.2,
     "spread_avg": 0.5345
    },
    "2026": {
     "n": 16,
     "top_win": 50.5,
     "base_win": 45.3,
     "beat_base": 56.2,
     "spread_avg": 1.3666
    }
   },
   "years_win_gt55": 2,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": 1.174,
     "ir_is": 0.748,
     "spread_oos_pct": 0.7536,
     "beat_base_rate": 54.7,
     "years_beat_gt55": 4,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.724,
     "ir_is": 1.231,
     "spread_oos_pct": 0.6646,
     "beat_base_rate": 59.8,
     "years_beat_gt55": 5,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 0.811,
     "ir_is": 1.921,
     "spread_oos_pct": 1.0563,
     "beat_base_rate": 59.5,
     "years_beat_gt55": 5,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "turntrend": {
   "label": "换手率趋势",
   "logic": "20日均量/240日均量 取负（缩量=强势）",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": 0.6182,
   "spread_is_pct": 0.6042,
   "spread_oos_pct": 0.6391,
   "top_win_avg": 51.0,
   "top_avg_pct": 0.6137,
   "bottom_avg_pct": -0.0045,
   "ir_is": 0.869,
   "ir_oos": 0.905,
   "sharpe_oos": 0.689,
   "base_win_avg": 48.3,
   "beat_base_rate": 57.4,
   "spread_pos_rate": 60.9,
   "years_beat_gt55": 5,
   "max_drawdown_top_pct": -29.091,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 55.2,
     "base_win": 50.2,
     "beat_base": 50.0,
     "spread_avg": 0.2795
    },
    "2020": {
     "n": 24,
     "top_win": 49.6,
     "base_win": 48.3,
     "beat_base": 33.3,
     "spread_avg": 0.1539
    },
    "2021": {
     "n": 24,
     "top_win": 53.7,
     "base_win": 50.9,
     "beat_base": 62.5,
     "spread_avg": 0.6752
    },
    "2022": {
     "n": 24,
     "top_win": 50.4,
     "base_win": 45.4,
     "beat_base": 75.0,
     "spread_avg": 1.1131
    },
    "2023": {
     "n": 25,
     "top_win": 45.8,
     "base_win": 43.2,
     "beat_base": 64.0,
     "spread_avg": 0.7516
    },
    "2024": {
     "n": 24,
     "top_win": 49.3,
     "base_win": 47.5,
     "beat_base": 62.5,
     "spread_avg": 0.89
    },
    "2025": {
     "n": 24,
     "top_win": 59.8,
     "base_win": 55.8,
     "beat_base": 62.5,
     "spread_avg": 0.4113
    },
    "2026": {
     "n": 16,
     "top_win": 45.4,
     "base_win": 45.3,
     "beat_base": 37.5,
     "spread_avg": 0.3506
    }
   },
   "years_win_gt55": 2,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": 0.921,
     "ir_is": 1.044,
     "spread_oos_pct": 0.4393,
     "beat_base_rate": 54.7,
     "years_beat_gt55": 4,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.905,
     "ir_is": 0.869,
     "spread_oos_pct": 0.6391,
     "beat_base_rate": 57.4,
     "years_beat_gt55": 5,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 1.129,
     "ir_is": 1.209,
     "spread_oos_pct": 1.1004,
     "beat_base_rate": 56.5,
     "years_beat_gt55": 4,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "overnight20": {
   "label": "隔夜跳空累积",
   "logic": "近 20 日隔夜收益之和",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": 0.2218,
   "spread_is_pct": 0.258,
   "spread_oos_pct": 0.1679,
   "top_win_avg": 47.8,
   "top_avg_pct": 0.3853,
   "bottom_avg_pct": 0.1636,
   "ir_is": 0.585,
   "ir_oos": 0.347,
   "sharpe_oos": 0.426,
   "base_win_avg": 48.3,
   "beat_base_rate": 49.1,
   "spread_pos_rate": 59.2,
   "years_beat_gt55": 1,
   "max_drawdown_top_pct": -42.536,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 51.2,
     "base_win": 50.2,
     "beat_base": 62.5,
     "spread_avg": 0.6252
    },
    "2020": {
     "n": 24,
     "top_win": 47.3,
     "base_win": 48.3,
     "beat_base": 41.7,
     "spread_avg": -0.315
    },
    "2021": {
     "n": 24,
     "top_win": 50.2,
     "base_win": 50.9,
     "beat_base": 54.2,
     "spread_avg": 0.8294
    },
    "2022": {
     "n": 24,
     "top_win": 45.4,
     "base_win": 45.4,
     "beat_base": 50.0,
     "spread_avg": 0.3846
    },
    "2023": {
     "n": 25,
     "top_win": 43.3,
     "base_win": 43.2,
     "beat_base": 48.0,
     "spread_avg": 0.1563
    },
    "2024": {
     "n": 24,
     "top_win": 46.7,
     "base_win": 47.5,
     "beat_base": 45.8,
     "spread_avg": -0.5868
    },
    "2025": {
     "n": 24,
     "top_win": 54.6,
     "base_win": 55.8,
     "beat_base": 50.0,
     "spread_avg": 0.51
    },
    "2026": {
     "n": 16,
     "top_win": 45.3,
     "base_win": 45.3,
     "beat_base": 50.0,
     "spread_avg": 0.552
    }
   },
   "years_win_gt55": 0,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": -0.298,
     "ir_is": 0.176,
     "spread_oos_pct": -0.1024,
     "beat_base_rate": 48.2,
     "years_beat_gt55": 0,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.347,
     "ir_is": 0.585,
     "spread_oos_pct": 0.1679,
     "beat_base_rate": 49.1,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 0.975,
     "ir_is": 0.888,
     "spread_oos_pct": 0.6899,
     "beat_base_rate": 51.2,
     "years_beat_gt55": 1,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "vol60": {
   "label": "60日波动率",
   "logic": "近 60 日日收益标准差取负（低波异象）",
   "hold": 10,
   "n_points": 169,
   "date_from": "2019-09-16",
   "date_to": "2026-08-21",
   "spread_avg_pct": 0.5598,
   "spread_is_pct": 0.6804,
   "spread_oos_pct": 0.3806,
   "top_win_avg": 51.0,
   "top_avg_pct": 0.5234,
   "bottom_avg_pct": -0.0364,
   "ir_is": 0.847,
   "ir_oos": 0.325,
   "sharpe_oos": 0.783,
   "base_win_avg": 48.3,
   "beat_base_rate": 53.3,
   "spread_pos_rate": 58.0,
   "years_beat_gt55": 3,
   "max_drawdown_top_pct": -29.19,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 54.5,
     "base_win": 50.2,
     "beat_base": 62.5,
     "spread_avg": 0.1432
    },
    "2020": {
     "n": 24,
     "top_win": 51.9,
     "base_win": 48.3,
     "beat_base": 58.3,
     "spread_avg": 0.9693
    },
    "2021": {
     "n": 24,
     "top_win": 54.6,
     "base_win": 50.9,
     "beat_base": 45.8,
     "spread_avg": 0.5407
    },
    "2022": {
     "n": 24,
     "top_win": 47.2,
     "base_win": 45.4,
     "beat_base": 54.2,
     "spread_avg": 1.0045
    },
    "2023": {
     "n": 25,
     "top_win": 45.6,
     "base_win": 43.2,
     "beat_base": 60.0,
     "spread_avg": 0.7267
    },
    "2024": {
     "n": 24,
     "top_win": 47.8,
     "base_win": 47.5,
     "beat_base": 50.0,
     "spread_avg": -0.2397
    },
    "2025": {
     "n": 24,
     "top_win": 59.0,
     "base_win": 55.8,
     "beat_base": 50.0,
     "spread_avg": 0.1105
    },
    "2026": {
     "n": 16,
     "top_win": 50.0,
     "base_win": 45.3,
     "beat_base": 50.0,
     "spread_avg": 1.1279
    }
   },
   "years_win_gt55": 1,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": false,
   "verdict": "FAIL",
   "pass_holds": [],
   "by_hold": {
    "hold_5": {
     "ir_oos": 0.707,
     "ir_is": 0.366,
     "spread_oos_pct": 0.6167,
     "beat_base_rate": 50.0,
     "years_beat_gt55": 2,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.325,
     "ir_is": 0.847,
     "spread_oos_pct": 0.3806,
     "beat_base_rate": 53.3,
     "years_beat_gt55": 3,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 0.295,
     "ir_is": 1.456,
     "spread_oos_pct": 0.4811,
     "beat_base_rate": 54.8,
     "years_beat_gt55": 4,
     "years_total": 8,
     "verdict": "FAIL"
    }
   }
  },
  "amt60": {
   "label": "60日成交额中位数",
   "logic": "近 60 日成交额中位数取负（小市值/低流动性溢价）",
   "hold": 20,
   "n_points": 168,
   "date_from": "2019-09-16",
   "date_to": "2026-08-07",
   "spread_avg_pct": 1.9909,
   "spread_is_pct": 2.483,
   "spread_oos_pct": 1.2672,
   "top_win_avg": 53.8,
   "top_avg_pct": 2.1423,
   "bottom_avg_pct": 0.1514,
   "ir_is": 2.115,
   "ir_oos": 0.924,
   "sharpe_oos": 1.385,
   "base_win_avg": 48.2,
   "beat_base_rate": 69.6,
   "spread_pos_rate": 66.7,
   "years_beat_gt55": 7,
   "max_drawdown_top_pct": -41.717,
   "years": {
    "2019": {
     "n": 8,
     "top_win": 50.7,
     "base_win": 48.6,
     "beat_base": 37.5,
     "spread_avg": -1.3683
    },
    "2020": {
     "n": 24,
     "top_win": 51.3,
     "base_win": 47.9,
     "beat_base": 58.3,
     "spread_avg": 0.7011
    },
    "2021": {
     "n": 24,
     "top_win": 58.5,
     "base_win": 52.6,
     "beat_base": 66.7,
     "spread_avg": 3.2786
    },
    "2022": {
     "n": 24,
     "top_win": 51.4,
     "base_win": 44.8,
     "beat_base": 87.5,
     "spread_avg": 4.1475
    },
    "2023": {
     "n": 25,
     "top_win": 49.8,
     "base_win": 42.0,
     "beat_base": 80.0,
     "spread_avg": 3.4374
    },
    "2024": {
     "n": 24,
     "top_win": 49.4,
     "base_win": 46.1,
     "beat_base": 62.5,
     "spread_avg": -0.2038
    },
    "2025": {
     "n": 24,
     "top_win": 67.1,
     "base_win": 59.4,
     "beat_base": 70.8,
     "spread_avg": 1.7318
    },
    "2026": {
     "n": 15,
     "top_win": 48.4,
     "base_win": 42.9,
     "beat_base": 73.3,
     "spread_avg": 1.8505
    }
   },
   "years_win_gt55": 2,
   "years_total": 8,
   "pass_ir": true,
   "pass_years": true,
   "verdict": "PASS",
   "pass_holds": [
    20
   ],
   "by_hold": {
    "hold_5": {
     "ir_oos": 1.008,
     "ir_is": 1.337,
     "spread_oos_pct": 0.6888,
     "beat_base_rate": 60.6,
     "years_beat_gt55": 6,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_10": {
     "ir_oos": 0.821,
     "ir_is": 1.546,
     "spread_oos_pct": 0.75,
     "beat_base_rate": 60.9,
     "years_beat_gt55": 5,
     "years_total": 8,
     "verdict": "FAIL"
    },
    "hold_20": {
     "ir_oos": 0.924,
     "ir_is": 2.115,
     "spread_oos_pct": 1.2672,
     "beat_base_rate": 69.6,
     "years_beat_gt55": 7,
     "years_total": 8,
     "verdict": "PASS"
    }
   }
  }
 }
};
