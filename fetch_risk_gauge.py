#!/usr/bin/env python3
"""v8 实时风险温度计 —— 抓取全球宏观风险指标。

数据去向：raw_data/risk_gauge.json → update_v8.py → data/RISK_GAUGE.js
触发：GitHub Actions 云端 runner 每30分钟跑一次（无需中国 IP）。
"""
import json
import os
import sys
import http.cookiejar
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "raw_data", "risk_gauge.json")

# Yahoo Finance v8 chart API（免费，无需 key）
YAHOO_SYMBOLS = {
    "USDJPY": "USDJPY=X",   # 美元兑日元
    "VIX": "^VIX",          # 恐慌指数
    "US10Y": "^TNX",        # 美国 10 年期国债收益率（日债暂缺稳定免费源，用美债替代）
    "USDCNH": "CNH=X",      # 美元兑离岸人民币
}


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Yahoo 近年对无 cookie 的裸请求返回 403，需先预热拿一次 cookie
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)
_opener.addheaders = [
    ("User-Agent", _UA),
    ("Accept", "application/json,text/plain,*/*"),
    ("Accept-Language", "en-US,en;q=0.9"),
]
_cookie_ready = False


def _warm_cookie():
    """访问 Yahoo 首页取 cookie，规避 chart API 的 403。"""
    global _cookie_ready
    if _cookie_ready:
        return
    for u in ("https://fc.yahoo.com", "https://finance.yahoo.com"):
        try:
            _opener.open(u, timeout=12).read(1024)
            _cookie_ready = True
            return
        except Exception:
            continue
    _cookie_ready = True  # 预热失败也只试一次，避免每个指标都重试拖慢


def fetch_yahoo(symbol):
    """从 Yahoo Finance 抓取最新价（query1/query2 双域名 + cookie），失败返回 None。"""
    _warm_cookie()
    last_err = None
    for host in ("query1", "query2"):
        url = (
            f"https://{host}.finance.yahoo.com/v8/finance/chart/"
            f"{symbol}?interval=1d&range=5d"
        )
        try:
            with _opener.open(url, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = data.get("chart", {}).get("result", [None])[0]
            if not result:
                continue
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            if price is None:
                quotes = result.get("indicators", {}).get("quote", [{}])
                closes = quotes[0].get("close", [])
                price = next((v for v in reversed(closes) if v is not None), None)
            if price is not None:
                return price
        except Exception as e:
            last_err = e
            continue
    print(f"[WARN] Yahoo {symbol} 抓取失败: {last_err}", file=sys.stderr)
    return None


# stooq 免费 CSV，作为 VIX / 美债的第三源（Yahoo 全挂时兜底）
STOOQ_SYMBOLS = {"VIX": "^vix", "US10Y": "10usy.b"}


def fetch_stooq(name):
    """stooq CSV 兜底，返回最新收盘价，失败返回 None。"""
    sym = STOOQ_SYMBOLS.get(name)
    if not sym:
        return None
    url = f"https://stooq.com/q/l/?s={urllib.parse.quote(sym)}&f=sd2t2ohlcv&h&e=csv"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        text = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            return None
        cols = lines[0].split(",")
        vals = lines[1].split(",")
        row = dict(zip([c.strip().lower() for c in cols], vals))
        close = row.get("close")
        if close in (None, "", "N/D"):
            return None
        return float(close)
    except Exception as e:
        print(f"[WARN] stooq {name} 抓取失败: {e}", file=sys.stderr)
        return None


def status_for(name, value):
    """根据指标计算状态灯与说明。"""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return {"status": "gray", "status_text": "待更新", "note": "数据暂不可得"}

    if name == "USDJPY":
        if value < 155 or value > 163:
            return {"status": "red", "status_text": "🚨 高危", "note": "突破干预警戒区"}
        if value < 156 or value > 158:
            return {"status": "yellow", "status_text": "⚠️ 警惕", "note": "偏离干预有效区"}
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
    """三源冗余：Yahoo → 新浪（外汇对）/ stooq（VIX、美债）。"""
    value = fetch_yahoo(symbol)
    if value is not None:
        return value

    sina_pairs = {"USDJPY": "fx_susdjpy", "USDCNH": "fx_susdcnh"}
    if name in sina_pairs:
        value = fetch_sina_fx(sina_pairs[name])
        if value is not None:
            print(f"[INFO] {name} 使用新浪兜底数据: {value}", file=sys.stderr)
            return value

    if name in STOOQ_SYMBOLS:
        value = fetch_stooq(name)
        if value is not None:
            print(f"[INFO] {name} 使用 stooq 兜底数据: {value}", file=sys.stderr)
    return value


def format_value(name, value):
    if value is None:
        return None
    if name in ("JP10Y",):
        return round(value, 3)
    if name in ("USDJPY", "USDCNH"):
        return round(value, 4)
    return round(value, 2)


def _load_prev():
    """读取上一次快照：用于"较上次"变化描述 + 本轮抓取失败时兜底沿用。"""
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            old = json.load(f)
        vals = {i.get("name"): i.get("value") for i in old.get("indicators", [])}
        return vals, old.get("update_time", "")
    except Exception:
        return {}, ""


def _delta_text(name, value, prev):
    """生成'较上次 +0.12'一类的变化描述，无历史则返回空串。"""
    p = prev.get(name)
    if value is None or p is None:
        return ""
    d = value - p
    if abs(d) < (0.005 if name in ("USDJPY", "USDCNH") else 0.01):
        return "（较上次持平）"
    digits = 4 if name in ("USDJPY", "USDCNH") else 2
    return f"（较上次 {'+' if d > 0 else ''}{round(d, digits)}）"


def analysis_for(name, value, status, prev):
    """根据当前真实数值动态生成分析解说，而非固定模板。"""
    dt = _delta_text(name, value, prev)
    if value is None:
        if name == "NORTH_FUND":
            return "港交所自 2024-05 起停止披露实时额度，该项暂无数据，不参与红灯计数。"
        return "数据暂不可得，本轮不参与判定。"

    if name == "USDJPY":
        if value > 163:
            return (f"当前 {value}{dt}，已越过 163 干预警戒线。日元极度贬值下日本当局出手概率骤升，"
                    "一旦干预将触发套息交易平仓、抽走全球美元流动性，港股与外资重仓的 A 股核心资产首当其冲，建议压降外资敏感板块仓位。")
        if value > 160:
            return (f"当前 {value}{dt}，距 163 干预线还有 {round(163 - value, 2)}。日元持续走弱、套息头寸仍在积累，"
                    "外资对港股/A 股维持谨慎，尚未形成强制平仓压力，属可观察区间。")
        if value >= 158:
            return (f"当前 {value}{dt}，位于干预有效区 156-158 上沿。日元偏弱但可控，"
                    "对 A 股外资流向影响偏中性，暂不构成额外扰动。")
        if value >= 156:
            return (f"当前 {value}{dt}，处于干预有效区 156-158 内。汇率端平稳，"
                    "套息交易未见异动，外资流向由基本面而非汇率主导。")
        if value >= 155:
            return (f"当前 {value}{dt}，逼近 155 下沿。日元转强意味着套息头寸开始回补，"
                    "新兴市场资金面短期偏紧，但幅度可控。")
        return (f"当前 {value}{dt}，跌破 155。日元快速升值通常对应套息平仓已启动，"
                "新兴市场流动性被抽离，A 股北向与港股短期承压；同时避险情绪抬头，利好黄金与债券。")

    if name == "VIX":
        if value > 25:
            return (f"当前 {value}{dt}，突破 25 恐慌线。美股避险模式开启，"
                    "科技成长与外资重仓股跌幅通常放大，宜降低总仓位、增配红利与防御，规避高 Beta。")
        if value > 20:
            return (f"当前 {value}{dt}，距 25 红线 {round(25 - value, 2)}。风险偏好正在下降，"
                    "外围波动开始向 A 股成长股传导，宜收紧个股买入过滤条件。")
        if value >= 15:
            return (f"当前 {value}{dt}，处于 15-20 中性区。外围情绪平稳，"
                    "A 股走势主要由国内政策与产业逻辑决定，外部波动暂不构成主要矛盾。")
        return (f"当前 {value}{dt}，低于 15 属极低波动。风险偏好可维持，"
                "但历史上极低波动常伴随尾部风险积聚，一旦突发事件出现，回撤幅度容易被放大，不宜满仓裸奔。")

    if name == "US10Y":
        if value > 4.5:
            return (f"当前 {value}%{dt}，超出 4.5% 红线 {round((value - 4.5) * 100)}bp。"
                    "无风险利率高企直接压制成长股估值分母，美元走强加剧外资流出；"
                    "配置上应偏向高股息、低估值与现金流稳健标的，规避高久期科技成长。")
        if value > 4.0:
            return (f"当前 {value}%{dt}，距 4.5% 红线 {round((4.5 - value) * 100)}bp。"
                    "融资成本抬升但尚未失控，对成长股估值形成温和压制，需持续跟踪。")
        if value >= 3.5:
            return (f"当前 {value}%{dt}，处于 3.5%-4.0% 中性区。利率端对 A 股估值影响有限，"
                    "外资流向更多取决于国内景气度。")
        return (f"当前 {value}%{dt}，低于 3.5%。降息预期升温，"
                "利好黄金、高股息与长久期成长资产，外资回流新兴市场的环境相对友好。")

    if name == "USDCNH":
        if value > 7.30:
            return (f"当前 {value}{dt}，突破 7.30。人民币快速贬值将触发外资撤离 A 股/港股，"
                    "进口成本抬升挤压中下游利润，核心资产承压；出口链与人民币贬值受益股相对抗跌。")
        if value > 7.25:
            return (f"当前 {value}{dt}，距 7.30 红线 {round(7.30 - value, 4)}。贬值压力累积中，"
                    "外资净流入意愿转弱，需关注央行中间价指引与逆周期因子。")
        if value >= 7.0:
            return (f"当前 {value}{dt}，位于 7.0-7.25 常态区间。汇率稳定，"
                    "既未对外资形成驱赶，也未过度挤压出口企业利润，属中性环境。")
        return (f"当前 {value}{dt}，低于 7.0，人民币偏强。外资回流环境友好、人民币资产吸引力上升，"
                "利好核心资产与进口型行业；但出口企业汇兑损益与价格竞争力受一定挤压。")

    if name == "NORTH_FUND":
        if value <= -50:
            return f"净流出 {abs(value)} 亿{dt}。外资大额撤离，消费/医药/新能源等核心资产流动性首当其冲。"
        if value < 0:
            return f"净流出 {abs(value)} 亿{dt}。小幅流出，属正常波动范围，尚未形成趋势性撤离。"
        if value >= 50:
            return f"净流入 {value} 亿{dt}。外资大额回补，利好白马龙头与消费/科技主线。"
        return f"净流入 {value} 亿{dt}。温和流入，外资态度中性偏暖。"

    return "暂无解说。"


def build_verdict(indicators, overall, stale_names=None):
    """基于本轮真实数值组合，动态生成综合判定文案。"""
    real = [i for i in indicators if i.get("value") is not None]
    reds = [i for i in real if i["status"] == "red"]
    yellows = [i for i in real if i["status"] == "yellow"]
    greens = [i for i in real if i["status"] == "green"]

    def brief(items):
        return "、".join(f"{i['label']} {i['value']}{i['unit']}" for i in items)

    tip = ""
    if stale_names:
        labels = "、".join(i["label"] for i in indicators if i["name"] in stale_names)
        tip = f"（注：{labels} 本轮数据源不可用，沿用上一次数值）"

    if not real:
        return "本轮外围指标全部抓取失败，风险温度计暂不可用，请以国内数据为准。"

    n = len(reds)
    if n == 0:
        base = f"外围 {len(real)} 项指标无红灯"
        if yellows:
            base += f"，其中 {brief(yellows)} 处于警惕区，需持续跟踪"
        else:
            base += f"（{brief(greens)} 均在安全区）"
        return base + "。A 股主驱动仍在国内政策与基本面，外部环境暂不构成额外约束，仓位与选股标准维持不变。" + tip

    red_names = brief(reds)
    if n == 1:
        r = reds[0]
        focus = {
            "US10Y": "利率端压制估值为主要外部风险，配置偏向高股息与低估值，规避高久期成长",
            "VIX": "外围避险情绪为主要风险，宜收紧买入过滤、降低高 Beta 敞口",
            "USDJPY": "汇率端套息平仓风险为主要变量，需警惕外资对港股与 A 股核心资产的减持",
            "USDCNH": "人民币贬值为主要压力源，外资流出与进口成本上行需同时防范",
            "NORTH_FUND": "外资流出为主要压力源，核心资产流动性需重点观察",
        }.get(r["name"], "该项为当前主要外部风险")
        tail = f"其余指标（{brief(yellows + greens)}）暂未共振" if (yellows or greens) else "其余指标暂未共振"
        return f"当前 1 项亮红灯：{red_names}。{focus}；{tail}，尚不构成系统性风险，建议在标准流程上增加一层过滤。" + tip

    if n == 2:
        return (f"当前 2 项亮红灯：{red_names}。两项外部风险已开始共振，"
                "对成长股与外资重仓股形成叠加压制，建议将权益仓位下调 20%-40%，优先保留低估值防御品种。" + tip)

    return (f"当前 {n} 项亮红灯：{red_names}。外围风险全面共振，属系统性风险区间，"
            "建议权益仓位降至 20% 以下，以现金与防御资产为主，暂停新开仓。" + tip)


def main():
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    prev, prev_time = _load_prev()
    indicators = []
    stale_names = []

    for name, symbol in YAHOO_SYMBOLS.items():
        raw = fetch_with_fallback(name, symbol)
        value = format_value(name, raw)

        # 关键保护：本轮源不可用时沿用上次值，绝不用 None 覆盖已有数据
        stale = False
        if value is None and prev.get(name) is not None:
            value = prev[name]
            stale = True
            stale_names.append(name)
            print(f"[STALE] {name} 本轮抓取失败，沿用上次值 {value}（{prev_time}）", file=sys.stderr)

        st = status_for(name, value)
        if stale:
            st["note"] = f"沿用 {prev_time[5:16] if prev_time else '上次'} 数据（本轮源不可用）"

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
                "stale": stale,
                "analysis": analysis_for(name, value, st["status"], prev),
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
            "analysis": analysis_for("NORTH_FUND", None, "gray", prev),
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
        "verdict": build_verdict(indicators, overall, stale_names),
        "stale_names": stale_names,
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
