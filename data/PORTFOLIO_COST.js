/* ============================================================
 * PORTFOLIO_COST.js — 持仓成本基准（用户真实买入价）
 * 用途：westock 模拟交易成交价可能与你实际成本不同，
 *       此处为权威成本基准，fetch_portfolio_westock 生成时覆盖。
 * 格式：code(无市场前缀) -> {cost_price, buy_date, qty, note}
 * 注意：本文件为合法 JSON（键名带引号），供 Python json.loads 解析。
 * ============================================================ */
window.PORTFOLIO_COST = {
  "688548": {"cost_price": 9.71, "buy_date": "2026-08-11", "qty": 1000, "note": "科创板·气体设备"},
  "301583": {"cost_price": 167.29, "buy_date": "2026-08-11", "qty": 100, "note": "创业板·精密制造"}
};
