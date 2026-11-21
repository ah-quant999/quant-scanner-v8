window.RISK_GUARD = {
  "update_time": "2026-11-22 04:42:58",
  "source": "PORTFOLIO(westock 练习赛组合) total_assets 真实累积 · 现有 1 点",
  "has_equity": false,
  "equity_points": 1,
  "curve_range": "2026-11-20~2026-11-20",
  "max_drawdown": 0.0,
  "tier": "正常(真实净值累积中)",
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
  "note": "真实账户净值曲线累积中（<2 点），回撤闸暂不降杠杆 ×1.00；随 PORTFOLIO.js 逐日快照累积，曲线生长后自动真实生效。旧 RISK_GUARD_INPUT.json 假曲线已于 2026-11-21 根除。"
};