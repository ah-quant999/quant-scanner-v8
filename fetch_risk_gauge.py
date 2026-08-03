#!/usr/bin/env python3
"""v8 实时风险温度计 —— 抓取全球宏观风险指标。

数据去向：raw_data/risk_gauge.json → update_v8.py → data/RISK_GAUGE.js
触发：GitHub Actions 云端 runner 每30分钟跑一次（无需中国 IP）。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "raw_data", "risk_gauge.json")

# Yahoo Finance v8 chart API（免费，无需 key）
YAHOO_SYMBOLS = {
    "USDJPY": "USDJPY=X",   # 美元兑日元
    "VIX": "^VIX",          # 恐慌指数
    "US10Y": "^TNX",        # 美国 10 年期国债收益率（日债暂缺稳定免费源，用美债替代）
    "USDCNH": "CNH=X",      # 美元兑离岸人民币
}


def fetch_yahoo(symbol):
    """从 Yahoo Finance 抓取最新价，失败返回 None。"""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval=1d&range=5d"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None
        meta = result.get("meta", {})
        # 优先用实时价/收盘价
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        if price is None:
            # 从 quote 数组兜底
            quotes = result.get("indicators", {}).get("quote", [{}])
            closes = quotes[0].get("close", [])
            price = next((v for v in reversed(closes) if v is not None), None)
        return price
    except Exception as e:
        print(f"[WARN] Yahoo {symbol} 抓取失败: {e}", file=sys.stderr)
        return None


def status_for(name, value):
    """根据指标计算状态灯与说明。"""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return {"status": "gray", "status_text": "待更新", "note": "数据暂不可得"}

    if name == "USDJPY":
        if value < 155 or value > 163:
            return {"status": "red", "status_text": "🚨 高危", "note": "突破干预警戒区"}
        if value < 158 or value > 160:
            return {"status": "yellow", "status_text": "⚠️ 警惕", "note": "接近干预区边缘"}
        return {"status": "green", "status_text": "🟢 有效", "note": "干预有效区 156-158"}

    if name == "VIX":
        if value > 25:
            return {"status": "red", "status_text": "🚨 高危", "note": "恐慌情绪显著升温"}
        if value > 20:
            return {"status": "yellow", "status_text": "⚠️ 警惕", "note": "风险偏好下降"}
        return {"status": "green", "status_text": "🟢 正常", "note": "波动率处于低位"}

    if name == "US10Y":
        if value > 4.5:
            return {"status": "red", "status_text": "🚨 高危", "note": "美债收益率突破 4.5%"}
        if value > 4.0:
            return {"status": "yellow", "status_text": "⚠️ 警惕", "note": "美债融资成本上升"}
        return {"status": "green", "status_text": "🟢 正常", "note": "美债收益率低于 4.0%"}

    if name == "USDCNH":
        if value > 7.30:
            return {"status": "red", "status_text": "🚨 高危", "note": "人民币快速贬值"}
        if value > 7.25:
            return {"status": "yellow", "status_text": "⚠️ 警惕", "note": "人民币贬值压力"}
        return {"status": "green", "status_text": "🟢 正常", "note": "人民币汇率相对稳定"}

    return {"status": "gray", "status_text": "--", "note": ""}


def fetch_sina_fx(pair):
    """新浪外汇行情兜底，pair 如 fx_susdjpy / fx_susdcnh。"""
    url = f"https://hq.sinajs.cn/list={pair}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.sina.com.cn",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            # 新浪返回 GBK
            text = resp.read().decode("gbk", errors="ignore")
        # 格式: var hq_str_fx_susdjpy="时间,买价,卖价,最新价,成交量,..,..,..,..,名称,涨跌...";
        if "hq_str_" in text:
            start = text.find('"') + 1
            end = text.find('"', start)
            if start > 0 and end > start:
                parts = text[start:end].split(",")
                if len(parts) >= 2:
                    return float(parts[1])  # 第2个字段为买价/当前价
    except Exception as e:
        print(f"[WARN] Sina {pair} 抓取失败: {e}", file=sys.stderr)
    return None


def fetch_with_fallback(name, symbol):
    """先 Yahoo，再 Sina（仅外汇对）。"""
    value = fetch_yahoo(symbol)
    if value is not None:
        return value
    sina_pairs = {"USDJPY": "fx_susdjpy", "USDCNH": "fx_susdcnh"}
    if name in sina_pairs:
        value = fetch_sina_fx(sina_pairs[name])
        if value is not None:
            print(f"[INFO] {name} 使用新浪兜底数据: {value}", file=sys.stderr)
    return value


def format_value(name, value):
    if value is None:
        return None
    if name in ("JP10Y",):
        return round(value, 3)
    if name in ("USDJPY", "USDCNH"):
        return round(value, 4)
    return round(value, 2)


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    indicators = []

    for name, symbol in YAHOO_SYMBOLS.items():
        raw = fetch_with_fallback(name, symbol)
        value = format_value(name, raw)
        st = status_for(name, value)

        meta = {
            "USDJPY": {"label": "美元兑日元", "unit": "", "source": "Yahoo Finance"},
            "VIX": {"label": "VIX 恐慌指数", "unit": "", "source": "Yahoo Finance"},
            "US10Y": {"label": "10Y 美债收益率", "unit": "%", "source": "Yahoo Finance"},
            "USDCNH": {"label": "美元兑离岸人民币", "unit": "", "source": "Yahoo Finance"},
        }[name]

        indicators.append(
            {
                "name": name,
                "label": meta["label"],
                "value": value,
                "unit": meta["unit"],
                "source": meta["source"],
                "status": st["status"],
                "status_text": st["status_text"],
                "note": st["note"],
            }
        )

    # 北向资金占位：由中国节点抓取后写入 north_fund.json，前端可合并展示
    indicators.append(
        {
            "name": "NORTH_FUND",
            "label": "北向资金",
            "value": None,
            "unit": "亿",
            "source": "中国数据源",
            "status": "gray",
            "status_text": "待更新",
            "note": "由中国节点抓取后更新",
        }
    )

    # 综合状态：只基于实际抓到的指标（排除占位项）
    real_statuses = [i["status"] for i in indicators if i["value"] is not None]
    if not real_statuses:
        overall = "gray"
    elif "red" in real_statuses:
        overall = "red"
    elif "yellow" in real_statuses:
        overall = "yellow"
    else:
        overall = "green"

    payload = {
        "update_time": now,
        "overall": overall,
        "indicators": indicators,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 风险温度计已写入 {OUT}，overall={overall}")
    for i in indicators:
        print(f"  {i['name']}: {i['value']} {i['unit']} -> {i['status_text']} ({i['note']})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
