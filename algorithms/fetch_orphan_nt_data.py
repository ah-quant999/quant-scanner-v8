#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 孤儿模块 NT_DATA：异动提醒 + ETF资金流向

2026-08-02 从 v6 fetch_nt_data.py 移植（精简版），路径适配 v8 raw_data。
原文件 943 行（含大量「重要市场日历」生成），本仓聚焦 ETF 监控部分：
- alerts: ETF 异动提醒（涨跌幅≥3%）
- etfFlow: 12 只国家队 ETF 实时行情
- calendar: 暂不实现（已用 V8_CAL 模块代替）

用法：python algorithms/fetch_orphan_nt_data.py
输出：raw_data/nt_data.json
"""

import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "raw_data", "nt_data.json")

# 12 只国家队 ETF 监控列表（与 v6 一致）
ETF_LIST = [
    {"code": "510300", "name": "华泰柏瑞沪深300ETF", "type": "宽基"},
    {"code": "510310", "name": "易方达沪深300ETF",   "type": "宽基"},
    {"code": "159919", "name": "嘉实沪深300ETF",     "type": "宽基"},
    {"code": "510330", "name": "华夏沪深300ETF",     "type": "宽基"},
    {"code": "510050", "name": "华夏上证50ETF",      "type": "宽基"},
    {"code": "510500", "name": "南方中证500ETF",      "type": "宽基"},
    {"code": "159845", "name": "华夏中证1000ETF",    "type": "宽基"},
    {"code": "588000", "name": "华夏科创50ETF",      "type": "宽基"},
    {"code": "512690", "name": "酒ETF",               "type": "行业"},
    {"code": "515050", "name": "5G通信ETF",           "type": "行业"},
    {"code": "159995", "name": "芯片ETF",              "type": "行业"},
    {"code": "512010", "name": "医药ETF",              "type": "行业"},
]


def fetch_etf_realtime():
    """获取 12 只 ETF 的实时行情（akshare 单接口）"""
    etf_data = []
    alerts = []
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            print("  ⚠️ ETF行情返回空")
            return etf_data, alerts
        now_str = datetime.now().strftime("%H:%M")
        for etf in ETF_LIST:
            try:
                row = df[df['代码'] == etf['code']]
                if row.empty:
                    continue
                row = row.iloc[0]
                def _safe_float(val):
                    if val is None or (hasattr(val, 'isna') and val.isna()) or (str(val) == 'nan'):
                        return 0.0
                    try:
                        return float(val) if val else 0.0
                    except Exception:
                        return 0.0
                price = _safe_float(row.get('最新价'))
                change_pct = _safe_float(row.get('涨跌幅'))
                volume = _safe_float(row.get('成交量'))
                amount = _safe_float(row.get('成交额'))
                amplitude = _safe_float(row.get('振幅'))
                etf_data.append({
                    "code": etf["code"],
                    "name": etf["name"],
                    "type": etf["type"],
                    "price": price,
                    "change_pct": change_pct,
                    "volume": volume,
                    "amount": amount,
                    "amplitude": amplitude,
                })
                if abs(change_pct) >= 3:
                    alerts.append({
                        "type": "etf",
                        "severity": "high" if abs(change_pct) >= 5 else "medium",
                        "message": f"{etf['name']} {'大涨' if change_pct > 0 else '大跌'} {abs(change_pct):.2f}%",
                        "time": now_str,
                    })
            except Exception as e:
                print(f"  ⚠️ {etf['name']} 获取失败: {e}")
                continue
    except Exception as e:
        print(f"  ⚠️ ETF行情获取失败: {e}")
    return etf_data, alerts


def main():
    print("=" * 50)
    print("  v8 NT_DATA 抓取（ETF 监控）")
    print("=" * 50)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    short_time = datetime.now().strftime("%H:%M")
    print(f"更新时间: {now_str}")

    etf_list, etf_alerts = fetch_etf_realtime()
    print(f"  ETF数据 {len(etf_list)} 只")
    print(f"  异动提醒 {len(etf_alerts)} 条")

    up_count = sum(1 for e in etf_list if e["change_pct"] > 0)
    down_count = len(etf_list) - up_count
    alerts = list(etf_alerts)
    alerts.insert(0, {
        "type": "summary",
        "severity": "medium" if down_count > up_count else "low",
        "message": f"ETF监测中，{up_count}涨{down_count}跌",
        "time": short_time,
    })

    nt_data = {
        "update_time": now_str,
        "alerts": alerts,
        "etfFlow": {
            "etfs": etf_list,
            "summary": {
                "total": len(ETF_LIST),
                "valid": len(etf_list),
                "up": up_count,
                "down": down_count,
                "alerts_count": len(etf_alerts),
            }
        },
        "calendar": [],  # 暂不实现，已用 V8_CAL 模块代替
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(nt_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 已保存: {OUT_PATH}")
    print("=" * 50)
    print(f"  ETF监测: {len(etf_list)} 只 ({up_count}涨 {down_count}跌)")
    print(f"  异动提醒: {len(alerts)} 条")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 异常: {e}")
        raise