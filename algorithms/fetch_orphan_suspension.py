#!/usr/bin/env python3
"""v8 孤儿模块 SUSPENSION_ALERT：异动停牌观测（🔒 已停牌 + ⚡ 近触发异动预警）

2026-08-02 从 v6 fetch_suspension_alert.py 移植，路径适配 v8 raw_data。
原 fetch_suspension_alert.py 在 stock-scanner 仓，本仓保留独立维护。
"""
import json, os, sys
from datetime import datetime

# v8 raw_data 路径（向上两级到仓根 + raw_data/）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "raw_data")
OUTPUT = os.path.join(DATA_DIR, "suspension_alert.json")
# 兼容旧路径（v6 数据源，扫描用）
V6_DATA_DIR = os.environ.get("V6_DATA_DIR", r"\E:\workspace\quant-scanner-v8\raw_data")

TRIGGER_THRESHOLD = 20  # 连续3日偏离≥20%触发异动停牌

def fetch_suspension():
    """A: 获取当前停牌股票列表（东方财富停复牌接口）"""
    try:
        import akshare as ak
        df = ak.stock_tfp_em(date=datetime.now().strftime("%Y%m%d"))
        if df is None or df.empty:
            print("  [停牌] 无数据")
            return []
        results = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            reason = str(row.get("停牌原因", "")).strip()[:20]
            date_str = str(row.get("停牌时间", "")).strip()
            if not code or not name:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                days = (datetime.now() - d).days
            except Exception:
                try:
                    d = datetime.strptime(date_str, "%Y%m%d")
                    days = (datetime.now() - d).days
                except Exception:
                    days = 0
            # 过滤未来停牌（停牌时间 > 今天，days为负数）
            if days < 0:
                continue
            results.append({"code": code, "name": name, "days": days, "reason": reason})
        # 按停牌天数降序
        results.sort(key=lambda x: -x["days"])
        print(f"  [停牌] 当前 {len(results)} 只")
        return results
    except Exception as e:
        print(f"  [停牌] 异常: {e}")
        return []

def fetch_near_trigger():
    """B: 扫描金股池全量股票 + 概念龙头，寻找接近异动触发阈值的股票"""
    alerts = []
    seen = set()

    def add_alert(code, name, pct, gap):
        if code in seen:
            return
        seen.add(code)
        alerts.append({
            "code": code,
            "name": name,
            "pct": round(pct, 1),
            "gap": round(gap, 1),
        })

    # 来源1：金股池全量扫描（不限三足鼎立）
    pool_path = os.path.join(DATA_DIR, "gold_pool.json")
    # 金股池如未生成则降级到 v6 源（过渡期）
    if not os.path.exists(pool_path):
        pool_path = os.path.join(V6_DATA_DIR, "gold_pool.json")
    if os.path.exists(pool_path):
        try:
            with open(pool_path, "r", encoding="utf-8") as f:
                gp = json.load(f)
            stocks = gp.get("stocks", {})
            for code, s in stocks.items():
                name = s.get("name", "")
                if not name:
                    continue
                # 优先用5日涨幅，其次20日涨幅
                chg_5d = s.get("chg_5d", 0) or 0
                chg_20d = s.get("chg_20d", 0) or 0
                chg = max(chg_5d, chg_20d)
                if chg and chg >= 15:
                    gap = max(0, TRIGGER_THRESHOLD - chg)
                    add_alert(code, name, chg, gap)
        except Exception as e:
            print(f"  [近触发] 金股池扫描异常: {e}")

    # 来源2：概念龙头扫描
    ranking_path = os.path.join(DATA_DIR, "concept_ranking.json")
    if not os.path.exists(ranking_path):
        ranking_path = os.path.join(V6_DATA_DIR, "concept_ranking.json")
    if os.path.exists(ranking_path):
        try:
            with open(ranking_path, "r", encoding="utf-8") as f:
                cr = json.load(f)
            hot_list = cr.get("hot_list", [])[:30]  # TOP30概念
            for item in hot_list:
                leaders = item.get("leading_stocks", [])
                for stock in leaders:
                    code = stock.get("code", "") or ""
                    name = stock.get("name", "") or ""
                    chg_ratio = stock.get("chg_ratio", 0) or 0
                    if code and name and chg_ratio >= 15:
                        gap = max(0, TRIGGER_THRESHOLD - chg_ratio)
                        add_alert(code, name, chg_ratio, gap)
        except Exception as e:
            print(f"  [近触发] 概念龙头扫描异常: {e}")

    # 来源3：涨停板池扫描（最近交易日）
    try:
        import akshare as ak
        from datetime import timedelta
        # 获取最近交易日
        today = datetime.now()
        trade_date = today
        weekday = today.weekday()
        if weekday == 5:
            trade_date = today - timedelta(days=1)
        elif weekday == 6:
            trade_date = today - timedelta(days=2)
        date_str = trade_date.strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=date_str)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("代码", "")).strip()
                name = str(row.get("名称", "")).strip()
                try:
                    pct = float(row.get("涨跌幅", 0) or 0)
                except Exception:
                    continue
                if not code or not name:
                    continue
                # 涨跌幅≥9.5%（逼近涨停），多日累积偏离可能超过20%
                if pct >= 9.5:
                    gap = max(0, TRIGGER_THRESHOLD - pct)
                    add_alert(code, name, pct, gap)
            print(f"  [近触发] 涨停板扫描: {len(df)} 只涨停")
    except Exception as e:
        print(f"  [近触发] 涨停板扫描异常: {e}")

    # 按偏离度升序（距触发越近越靠前），跌幅靠前排除负gap
    alerts = [a for a in alerts if a["gap"] >= 0]
    alerts.sort(key=lambda x: x["gap"])
    print(f"  [近触发] {len(alerts)} 只")
    return alerts[:8]  # 最多展示8只

def main():
    print("=" * 50)
    print("  异动停牌观测")
    print("=" * 50)

    suspended = fetch_suspension()
    near = fetch_near_trigger()

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "suspended": suspended[:8],
        "near_trigger": near,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 已保存: {OUTPUT}")
    print(f"  停牌: {len(suspended)} 只 | 近触发: {len(near)} 只")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 异常: {e}")
        raise
