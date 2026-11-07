# -*- coding: utf-8 -*-
"""
【做T空间】生成器（2026-11-07 主人令①：数据源由 v8 自带，不依赖外部工具）

数据来源（真实、已在主站 data/ 注入）：
  - data/STOCK_QUOTE.js   —— window.STOCK_QUOTE.stocks["sh600000"] = {name,price,open,high,low,prev_close,pct,...}
      提供每票「今日」实际 最高/最低 → 即真实日内做T空间
  - data/STOCK_STOP_DATA.js —— window.STOCK_STOP_DATA.stocks[code] = {support,resistance,...}
      提供波段 支撑/压力 作为「波段T位」次级参考

做T空间定义（诚实、可解释）：
  主口径（日内）：
    高抛(参考) = 今日最高 high
    低吸(参考) = 今日最低 low
    空间%      = (high - low) / low × 100   ← 当日可在高低之间做T的真实幅度
  副口径（波段，仅当 support/resistance 有效）：
    波段低吸 = support(支撑)   波段高抛 = resistance(压力)
  红涨绿跌语义：空间% 大=红(日内波动大、做T机会多)，小=绿。

前端：个股查询卡内 renderDoTSpace(code) 按查询代码取数展示；键用纯代码(去市场前缀)。

幂等：纯本地读取现有 data 文件，不联网，CI/本机均可跑。
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUOTE = ROOT / "data" / "STOCK_QUOTE.js"
STOP = ROOT / "data" / "STOCK_STOP_DATA.js"
OUT = ROOT / "data" / "DO_T_SPACE.js"


def _extract_js_obj(src: str) -> dict:
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", src, re.S)
    if not m:
        raise ValueError("无法解析 JSON 主体")
    return json.loads(m.group(1))


def _load_quotes() -> dict:
    """返回 纯代码 -> quote 映射（去掉 sh/sz/bj 前缀）。"""
    if not QUOTE.exists():
        return {}
    obj = _extract_js_obj(QUOTE.read_text(encoding="utf-8"))
    stocks = obj.get("stocks", obj)  # 兼容 {stocks:{...}} 或直接 {...}
    out = {}
    for key, q in stocks.items():
        code = re.sub(r"^(sh|sz|bj)", "", key)
        out[code] = q
    return out


def _load_stops() -> dict:
    if not STOP.exists():
        return {}
    obj = _extract_js_obj(STOP.read_text(encoding="utf-8"))
    return obj.get("stocks", {})


def main():
    quotes = _load_quotes()
    stops = _load_stops()
    update_time = ""
    out = {}

    # 以行情表为主（含 name + 今日 high/low）
    for code, q in quotes.items():
        high = q.get("high")
        low = q.get("low")
        if not high or not low or low <= 0:
            continue
        spread = round((high - low) / low * 100, 2)
        rec = {
            "code": code,
            "name": q.get("name", ""),
            "price": q.get("price"),
            "pct": q.get("pct"),
            "open": q.get("open"),
            "high": round(high, 2),
            "low": round(low, 2),
            "high_throw": round(high, 2),   # 高抛参考 = 今高
            "low_suck": round(low, 2),      # 低吸参考 = 今低
            "spread_pct": spread,           # 日内空间%
        }
        # 波段参考（若有）
        st = stops.get(code) or {}
        sup = st.get("support")
        res = st.get("resistance")
        if sup and res and sup > 0 and res > 0:
            rec["swing_low"] = round(sup, 2)
            rec["swing_high"] = round(res, 2)
            rec["swing_spread_pct"] = round((res - sup) / sup * 100, 2)
        out[code] = rec

    # 补：行情表没有但止损表有的票（极少数），仅给波段位
    for code, st in stops.items():
        if code in out:
            continue
        sup = st.get("support")
        res = st.get("resistance")
        if not sup or not res or sup <= 0 or res <= 0:
            continue
        out[code] = {
            "code": code,
            "name": st.get("name", ""),
            "swing_low": round(sup, 2),
            "swing_high": round(res, 2),
            "swing_spread_pct": round((res - sup) / sup * 100, 2),
        }

    payload = {
        "update_time": update_time or (quotes and "from STOCK_QUOTE"),
        "source": "STOCK_QUOTE(今日high/low=日内做T) + STOCK_STOP_DATA(支撑/压力=波段T位)",
        "count": len(out),
        "stocks": out,
    }
    OUT.write_text(
        "window.DO_T_SPACE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    # 统计有多少带日内空间
    intraday = sum(1 for v in out.values() if "spread_pct" in v)
    print(f"[gen_do_t_space] 生成 {OUT.name}: 共 {len(out)} 只 (日内空间 {intraday} 只)")


if __name__ == "__main__":
    main()
