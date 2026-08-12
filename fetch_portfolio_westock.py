#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_portfolio_westock.py — TOP3 持仓跟踪数据生成器

数据流：
  westock MCP (portfolio_paper_positions + data_quote)
      → 本脚本（合并 PORTFOLIO_COST.js 真实成本基准）
      → data/PORTFOLIO.js (window.PORTFOLIO_DATA)

用法（由 agent/自动化调用）：
  python fetch_portfolio_westock.py --positions '<json>' --quotes '<json>' [--account '<json>']

  --positions: westock portfolio_paper_positions 返回的 data 对象（含 positions 数组）
  --quotes:    westock data_quote 返回的 data 对象（code->quote 映射）
  --account:   westock portfolio_paper_portfolio 返回的 data.portfolio 对象（可选）
"""
import json
import sys
import re
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
COST_FILE = os.path.join(HERE, "data", "PORTFOLIO_COST.js")
OUT_FILE = os.path.join(HERE, "data", "PORTFOLIO.js")


def load_cost():
    """从 data/PORTFOLIO_COST.js 解析 window.PORTFOLIO_COST = {...};（合法 JSON，花括号平衡匹配）"""
    try:
        with open(COST_FILE, "r", encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"window\.PORTFOLIO_COST\s*=\s*", txt)
        if not m:
            return {}
        start = txt.index("{", m.end())
        depth = 0
        end = start
        for i in range(start, len(txt)):
            if txt[i] == "{":
                depth += 1
            elif txt[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        return json.loads(txt[start:end])
    except Exception as e:
        print("WARN load_cost:", e, file=sys.stderr)
    return {}


def _load_arg(val):
    """支持 @file 读取大 JSON，或内联 JSON 字符串。"""
    if val and val.startswith("@"):
        try:
            with open(val[1:], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print("WARN read file", val, e, file=sys.stderr)
            return "{}"
    return val


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", default="{}")
    ap.add_argument("--quotes", default="{}")
    ap.add_argument("--account", default="")
    args = ap.parse_args()

    try:
        pos_data = json.loads(_load_arg(args.positions))
    except Exception as e:
        print("ERROR parse positions:", e, file=sys.stderr)
        pos_data = {}
    try:
        quote_data = json.loads(_load_arg(args.quotes))
    except Exception as e:
        print("ERROR parse quotes:", e, file=sys.stderr)
        quote_data = {}
    account = None
    if args.account:
        try:
            account = json.loads(args.account)
        except Exception:
            account = None

    cost_map = load_cost()
    ws_positions = pos_data.get("positions", []) if isinstance(pos_data, dict) else []

    # 构建 code(无前缀)->position 映射
    def norm_code(c):
        return re.sub(r"^[shszSHSZ]+", "", str(c or ""))

    out_positions = []
    seen = set()
    for p in ws_positions:
        code = p.get("code", "")
        nc = norm_code(code)
        c = cost_map.get(nc, {})
        # 优先用真实成本基准；westock 无则退用模拟成交价
        cost_price = c.get("cost_price", p.get("costPrice") or p.get("currentPrice") or 0)
        live_price = p.get("currentPrice") or quote_data.get(code, {}).get("price")
        try:
            live_price = float(live_price)
        except Exception:
            live_price = None
        out_positions.append({
            "code": code,
            "name": p.get("name", ""),
            "market": code[:2].lower() if code[:2].lower() in ("sh", "sz", "hk") else "sh",
            "qty": int(p.get("quantity", 0) or 0),
            "cost_price": float(cost_price),
            "live_price": live_price,
            "buy_date": c.get("buy_date", ""),
            "note": c.get("note", "")
        })
        seen.add(nc)

    # 成本基准中有但 westock 暂无持仓的（如订单未成交），也补入
    for nc, c in cost_map.items():
        if nc in seen:
            continue
        # 尝试从 quotes 拿实时价
        live = None
        for k, v in quote_data.items():
            if norm_code(k) == nc:
                live = v.get("price")
                break
        out_positions.append({
            "code": (c.get("market", "sh") + nc),
            "name": c.get("name", nc),
            "market": c.get("market", "sh"),
            "qty": int(c.get("qty", 0) or 0),
            "cost_price": float(c.get("cost_price", 0)),
            "live_price": live,
            "buy_date": c.get("buy_date", ""),
            "note": c.get("note", ""),
            "pending": True  # 标记：westock 侧订单未成交
        })

    # 账户概览
    if account:
        acct = {
            "name": account.get("name", "练习赛组合"),
            "total_assets": float(account.get("totalAssets", 0) or 0),
            "market_value": float(account.get("marketValue", 0) or 0),
            "available_cash": float(account.get("availableCash", 0) or 0),
            "total_profit": float(account.get("totalProfit", 0) or 0),
            "total_profit_rate": float(account.get("totalProfitRate", 0) or 0)
        }
    else:
        acct = {
            "name": "练习赛组合",
            "total_assets": 1000000.00,
            "market_value": sum(p["cost_price"] * p["qty"] for p in out_positions if p["qty"]),
            "available_cash": 1000000.00,
            "total_profit": 0.0,
            "total_profit_rate": 0.0
        }

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = {
        "updated_at": now,
        "source": "westock-mcp",
        "account": acct,
        "positions": out_positions
    }

    js = "// AUTO-GENERATED by fetch_portfolio_westock.py — 勿手动编辑\n"
    js += "window.PORTFOLIO_DATA = " + json.dumps(out, ensure_ascii=False, indent=2) + ";\n"
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(js)
    print("OK wrote", OUT_FILE, "positions:", len(out_positions), "updated_at:", now)


if __name__ == "__main__":
    main()
