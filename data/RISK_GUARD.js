window.RISK_GUARD = {
  "update_time": "2026-10-26 07:51:43",
  "source": "RISK_GUARD_INPUT.json · equity(累计净值)",
  "has_equity": true,
  "equity_points": 121,
  "max_drawdown": 0.0603,
  "peak_idx": 120,
  "trough_idx": 55,
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
  "note": "策略真实最大回撤 6.03%，触发「正常」档 ⇒ 仓位乘数 ×1.00。前端执行卡已据此真实缩放每只建议仓位。"
};