# -*- coding: utf-8 -*-
"""
v8/fetch_broad_etf_volume.py —— 「国家队活跃度」D 路（宽基ETF放量异动）真实数据源
产出 raw_data/broad_etf_volume.json（window 不用，纯本地/云端计算产物，由 gen_national_team.py 消费）。

设计（主人铁律：绝不编造·真实数据）：
  · 取 6 只头部宽基ETF（上证50/沪深300/中证500/科创50/创业板/中证1000）当日成交额 ÷ 前20日均成交额，
    取最大倍数 ratio_max 作为「放量指纹」；
  · 下跌日（上证指数收跌）放量 ⇒ 计护盘分；非下跌日放量不判护盘（中性 50，不编造语义）；
  · 数据来自东方财富 push2his K线（公开、日频、可验证），不依赖任何披露滞后源。
  · 与 gen_national_team.py 跨零点口径一致：data_date 取实际交易日；若生成时刻北京 <07:00 按「昨日」对齐。

调度：挂入 .github/workflows/v8_national_team.yml，在 gen_national_team.py 之前 best-effort 运行，
      将 raw_data/broad_etf_volume.json 提交进仓（checkout 后 gen 直接消费）。
      失败则留空文件/不写，gen 侧自动判 D 未就绪并权重重分，不影响 A/B/C。
"""
import os
import sys
import json
import ssl
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "raw_data", "broad_etf_volume.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 6 只头部宽基ETF：(secid, code, name)
ETFS = [
    ("1.510050", "510050", "华夏上证50ETF"),
    ("1.510300", "510300", "华泰沪深300ETF"),
    ("1.510500", "510500", "南方中证500ETF"),
    ("1.588000", "588000", "华夏科创50ETF"),
    ("0.159915", "159915", "易方达创业板ETF"),
    ("1.512100", "512100", "南方中证1000ETF"),
]
INDEX = ("1.000001", "上证指数")


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def fetch_kline(secid, beg="20260901"):
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
           "?secid=%s&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
           "&klt=101&fqt=0&beg=%s&end=20500101" % (secid, beg))
    d = _get(url)
    return (d.get("data") or {}).get("klines") or []


def main():
    bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    ratios, max_ratio, max_etf, max_amt = [], 0.0, "", 0.0
    ok = 0
    last_date = ""
    for secid, code, name in ETFS:
        try:
            kl = fetch_kline(secid)
        except Exception as e:  # noqa
            print("[broad_etf] ⚠ %s 取数失败: %s" % (name, e), flush=True)
            continue
        if len(kl) < 22:
            print("[broad_etf] ⚠ %s 数据不足(%d)" % (name, len(kl)), flush=True)
            continue
        amts = []
        for row in kl:
            parts = row.split(",")
            try:
                amts.append(float(parts[6]))  # f57 成交额(元)
            except (IndexError, ValueError):
                pass
        if len(amts) < 22:
            continue
        date = kl[-1].split(",")[0]
        last_date = max(last_date, date)
        today_amt = amts[-1]
        prev20 = amts[-22:-2]  # 前20日均额窗口（不含今日）
        avg20 = sum(prev20) / len(prev20)
        ratio = today_amt / avg20 if avg20 > 0 else 0.0
        ratios.append((ratio, name, today_amt))
        ok += 1
        if ratio > max_ratio:
            max_ratio, max_etf, max_amt = ratio, name, today_amt

    # 上证指数：收跌判定
    down_day = None
    idx_chg = None
    try:
        ikl = fetch_kline(INDEX[0])
        closes = []
        for row in ikl:
            parts = row.split(",")
            try:
                closes.append(float(parts[2]))  # f53 收盘
            except (IndexError, ValueError):
                pass
        if len(closes) >= 2 and closes[-2] > 0:
            idx_chg = (closes[-1] / closes[-2] - 1.0) * 100.0
            down_day = idx_chg < 0
    except Exception as e:  # noqa
        print("[broad_etf] ⚠ 指数取数失败: %s" % e, flush=True)

    if ok == 0 or max_ratio <= 0:
        print("[broad_etf] ⚠ 无有效宽基ETF数据，不写文件（gen 侧判 D 未就绪）", flush=True)
        return 1

    payload = {
        "data_date": last_date,
        "update_time": bj.strftime("%Y-%m-%d %H:%M:%S"),
        "ratio_max": round(max_ratio, 3),
        "ratio_etf": max_etf,
        "amount_max_yi": round(max_amt / 1e8, 2),
        "down_day": bool(down_day) if down_day is not None else None,
        "index_chg_pct": (round(idx_chg, 2) if idx_chg is not None else None),
        "ok_count": ok,
        "source": "东方财富 push2his K线（6只头部宽基ETF 当日成交额/前20日均额）",
        "note": "下跌日放量计护盘分；非下跌日中性50。D 路为护盘公开指纹，详见 gen_national_team.py 文档头。",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("[broad_etf] ✅ %s  ratio_max=%.3f (%s, %.2f亿)  大盘%s%.2f%%  覆盖%d/6" % (
        last_date, max_ratio, max_etf, max_amt / 1e8,
        ("跌" if down_day else "涨/平"), (idx_chg or 0), ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
