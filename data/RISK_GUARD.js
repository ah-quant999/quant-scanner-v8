window.RISK_GUARD = {
  "update_time": "2026-11-28 15:31:18",
  "source": "PORTFOLIO(westock 练习赛组合) total_assets 真实累积 · 2026-11-20~2026-11-27 共 4 点",
  "has_equity": true,
  "equity_points": 4,
  "curve_range": "2026-11-20~2026-11-27",
  "max_drawdown": 0.0,
  "peak_idx": 0,
  "trough_idx": 0,
  "tier": "正常",
  "multiplier": 1.0,
  "thresholds": [
    {
      "dd_lt": 0.08,
      "mult": 1.0,
      "tier": "正常"
    },
    {
      "dd_lt": 0.12,
      "mult": 0.5,
      "tier": "减半"
    },
    {
      "dd_lt": 0.15,
      "mult": 0.25,
      "tier": "半仓(上限)"
    },
    {
      "dd_lt": 1.0,
      "mult": 0.0,
      "tier": "清仓"
    }
  ],
  "data_degraded": false,
  "note": "真实账户最大回撤 0.00%，触发「正常」档 ⇒ 仓位乘数 ×1.00。净值=练习赛组合 total_assets 逐日真实累积（当日快照已入账）。"
};