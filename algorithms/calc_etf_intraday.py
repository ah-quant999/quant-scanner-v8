#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_etf_intraday.py — ETF 三件套数据生成
  · ETF_INTRADAY_HEAT（盘中：主力净流入排名 TOP5/OUTFLOW5 + 分类汇总）
  · ETF_DAILY_MONITOR（日监控：TOP_INFLOW/OUTFLOW + 总额统计）
  · ETF_PULSE（放量异动：量比 > 1.2 按量比排序）

数据源：东方财富 push2（fundETFmarketList / ETF 实时价 / 主力净流入）
主要 ETF push2 端点：
  · ETF 列表：https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=200&fs=m:1+t:9 (m:1=沪基金,t:9=ETF)
  · 实时行情：https://push2.eastmoney.com/api/qt/stock/get?secid=1.510300&fields=f43,f44,f45,f46,f47,f48,f60,f62,f168,f169,f170
  · 主力净流入：f62（主力净流入，单位元）
  · 涨跌幅：f170  当日涨跌幅
"""
import os, json, sys, time, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
CST = ZoneInfo("Asia/Shanghai")

ETF_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=300&fs=m:1,t:9,m:0,t:9&fields=f12,f14,f13,f2,f3,f5,f6,f62,f168,f170"
QUOTE_URL_TPL = "https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f12,f13,f43,f44,f45,f46,f47,f48,f60,f62,f168,f169,f170"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/fund/etf/",
    "Accept": "application/json, text/plain, */*",
}


def _http(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"_err": str(e)[:80]}


def fetch_etf_list():
    """拉东方财富 ETF 列表（沪+深 各前 100），返回 [{code,name,pct,amount_main}, ...]"""
    d = _http(ETF_LIST_URL)
    if d.get("_err"):
        return None, d["_err"]
    rows = []
    for it in d.get("data", {}).get("diff", []) or []:
        rows.append({
            "code": str(it.get("f12")).zfill(6),
            "name": it.get("f14"),
            "price": it.get("f2") / 100 if it.get("f2") else None,
            "pct": it.get("f3") / 100 if it.get("f3") else None,
            "amount": (it.get("f5") or 0),
            "vol_ratio": (it.get("f6") or 0),  # 量比
            "main_net_inflow": it.get("f62") or 0,  # 元
            "amplitude": it.get("f168") or 0,
        })
    return rows, None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    # 1) ETF_INTRADAY_HEAT
    items, err = fetch_etf_list()
    # 🛡 2026-08-17 主人怒令发现：网络失败时写 error=True 空结构会覆盖小九真版本（1564 只真数据全没了）
    # 一劳永逸修：网络失败直接 sys.exit(0) 不写任何文件，保留 raw_data/etf_*.json 现有真数据
    # 云端自托管 runner 没这个问题（云端可直连 eastmoney），本守卫只防家里机被风控覆盖
    if items is None:
        print(f"  ❌ eastmoney push2 失败: {err} — 不写盘，保留现有 raw_data/etf_*.json（避免覆盖小九真版本）")
        print(f"  ℹ️  家里机网络风控，请云端 v8_cn_fetch_cloud.yml category=intraday 重跑补救")
        sys.exit(0)
    else:
        # 按主力净流入排序
        items_sorted = sorted(items, key=lambda x: x.get("main_net_inflow", 0), reverse=True)
        inflow_top = [x for x in items_sorted if x.get("main_net_inflow", 0) > 0][:10]
        outflow_top = [x for x in items_sorted if x.get("main_net_inflow", 0) < 0][-10:][::-1]
        for x in items:
            x["main_net_inflow_yi"] = round(x["main_net_inflow"] / 1e8, 2)  # 转亿元
        # 分类汇总（按 code 前缀）
        cats = {"沪市ETF": [], " 深市ETF": [], "跨市场ETF": []}
        for x in items:
            if x["code"].startswith("5"):
                cats["沪市ETF"].append(x)
            elif x["code"].startswith("1"):
                cats[" 深市ETF"].append(x)
            else:
                cats["跨市场ETF"].append(x)
        result_heat = {
            "update_time": now,
            "items": items,
            "inflow_top": inflow_top,
            "outflow_top": outflow_top,
            "categories": cats,
            "note": "主力净流入 TOP10/外流 TOP10，东财 push2 ETF 实时排行",
            "total_etf": len(items),
            "error": False,
        }

    # 2) ETF_DAILY_MONITOR（与 INTRADAY_HEAT 数据同源但简化 + 汇总指标）
    result_daily = {
        "update_time": now,
        "total_etf": result_heat.get("total_etf", 0),
        "total_net": round(sum(x.get("main_net_inflow", 0) for x in items or []) / 1e8, 2) if items else 0,
        "top_inflow": result_heat.get("inflow_top", [])[:5],
        "top_outflow": result_heat.get("outflow_top", [])[:5],
        "note": "ETF 全市场日度汇总，净流入单位亿元",
    }

    # 3) ETF_PULSE（量比 > 1.2 放量异动）
    if items:
        pulse_list = sorted(
            [x for x in items if (x.get("vol_ratio") or 0) > 1.2 and abs(x.get("pct") or 0) > 0.1],
            key=lambda x: x.get("vol_ratio", 0),
            reverse=True,
        )[:30]
    else:
        pulse_list = []
    result_pulse = {
        "update_time": now,
        "etfs": pulse_list,
        "note": "盘中异动：量比>1.2 + 涨跌幅>0.1% 的放量 ETF（按量比排序）",
        "count": len(pulse_list),
    }

    # 写出 raw_data/
    write_json(os.path.join(RAW, "etf_intraday_heat.json"), result_heat)
    write_json(os.path.join(RAW, "etf_daily_monitor.json"), result_daily)
    write_json(os.path.join(RAW, "etf_pulse.json"), result_pulse)
    print(f"  ✅ etf_intraday_heat: total_etf={result_heat.get('total_etf')}, error={result_heat.get('error')}")
    print(f"  ✅ etf_daily_monitor: total_net={result_daily['total_net']}亿")
    print(f"  ✅ etf_pulse: count={result_pulse['count']} (放量 ETF)")
    return result_heat.get("error", False)


if __name__ == "__main__":
    print(f"[calc_etf_intraday] {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    err = build()
    sys.exit(1 if err else 0)
