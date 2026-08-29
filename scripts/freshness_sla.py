#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freshness_sla.py — v8 数据新鲜度 SLA 自动标红 + 告警（Tier 1 第 3 步）

主人 2026-08-29 报告"图14 实际读 LHB_DATA 而非 FOUR_VOLUME，raw_data 卡在 2026-08-04"
→ 缺乏 SLA 监控：陈旧数据静默留在卡上不报警。

本脚本：
  - 扫 raw_data/*.json 每个文件的 update_time
  - 与"应有周期"对比：
      premarket    < 24h
      intraday     < 4h
      post_close   < 24h
  - 输出 raw_data/freshness_sla.json + 终端告警
  - v8_algo.yml 17:00 体检后追加调用

阈值通过 FRESHNESS_SLA 字典定义，可在不重启的情况下追加。
"""
import os, json, sys, glob
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")

# 文件名 → SLA 配置（小时）
# ⚠️ 与 v8_health_check.py 的 SLA 表保持一致（主人 2026-08-27 拍的）
FRESHNESS_SLA = {
    "factor_ic_report.json":        {"max_age_h": 24, "category": "post_close"},
    "factor_validate_report.json":  {"max_age_h": 24, "category": "post_close"},
    "market_regime.json":           {"max_age_h": 24, "category": "post_close"},
    "cockpit_backtest.json":        {"max_age_h": 48, "category": "post_close"},
    "lhb_data.json":                {"max_age_h": 24, "category": "post_close"},
    "top5_track.json":              {"max_age_h": 24, "category": "post_close"},
    "h_auto_buy_track.json":        {"max_age_h": 24, "category": "post_close"},
    "stock_quote.json":             {"max_age_h": 4,  "category": "intraday"},
    "limit_up_heatmap.json":        {"max_age_h": 4,  "category": "intraday"},
    "sector_fund_flow.json":        {"max_age_h": 24, "category": "post_close"},
    "sector_fund_flow_intraday.json":{"max_age_h": 4,  "category": "intraday"},
    "avg_price.json":               {"max_age_h": 24, "category": "post_close"},
    "etf_subscription_em.json":     {"max_age_h": 24, "category": "post_close"},
}

def parse_update_time(s):
    if not s or not isinstance(s, str):
        return None
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=CST)
        except ValueError:
            continue
    return None

def fresh_pct(actual_age_h, max_age_h):
    if max_age_h <= 0:
        return 0.0
    return round(min(100, actual_age_h / max_age_h * 100), 1)

def main():
    if not os.path.isdir(RAW_DIR):
        print(f"[err] raw_data not found: {RAW_DIR}", file=sys.stderr)
        return 1

    now = datetime.now(CST)
    report = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "policy": "freshness_sla_v1",
        "overall_status": "OK",
        "breaches": [],
        "files": []
    }

    all_files = {f for f in os.listdir(RAW_DIR) if f.endswith(".json")}
    for fname, sla in FRESHNESS_SLA.items():
        path = os.path.join(RAW_DIR, fname)
        if not os.path.exists(path):
            rec = {"file": fname, "exists": False, "configured": True,
                   "expected_max_h": sla["max_age_h"], "category": sla["category"],
                   "status": "MISSING"}
            report["files"].append(rec)
            report["breaches"].append(f"{fname}: MISSING (预期频率 {sla['category']})")
            report["overall_status"] = "BREACH"
            continue

        try:
            obj = json.load(open(path, "r", encoding="utf-8"))
        except Exception as e:
            report["files"].append({"file": fname, "exists": True, "status": "CORRUPT", "err": str(e)[:120]})
            report["breaches"].append(f"{fname}: JSON 损坏 ({e})")
            report["overall_status"] = "BREACH"
            continue

        ut = parse_update_time(obj.get("update_time"))
        if not ut:
            rec = {"file": fname, "exists": True, "configured": True,
                   "expected_max_h": sla["max_age_h"], "category": sla["category"],
                   "status": "NO_UPDATE_TIME", "update_time": obj.get("update_time")}
            report["files"].append(rec)
            report["breaches"].append(f"{fname}: 无 update_time 字段")
            if report["overall_status"] == "OK":
                report["overall_status"] = "WARN"
            continue

        age_h = round((now - ut).total_seconds() / 3600, 2)
        ok = age_h <= sla["max_age_h"]
        warn = age_h <= sla["max_age_h"] * 1.3
        if ok: status = "OK"
        elif warn: status = "WARN"
        else: status = "BREACH"

        rec = {
            "file": fname, "exists": True, "configured": True,
            "expected_max_h": sla["max_age_h"], "category": sla["category"],
            "update_time": obj.get("update_time"),
            "age_h": age_h,
            "freshness_pct": fresh_pct(age_h, sla["max_age_h"]),
            "status": status
        }
        report["files"].append(rec)
        if not ok:
            msg = f"{fname}: age {age_h}h > {sla['max_age_h']}h ({sla['category']})"
            report["breaches"].append(msg)
            report["overall_status"] = "BREACH"
        elif status == "WARN" and report["overall_status"] == "OK":
            report["overall_status"] = "WARN"

    out = os.path.join(RAW_DIR, "freshness_sla.json")
    open(out, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=2))

    if report["breaches"]:
        print(f"[{report['overall_status']}] {len(report['breaches'])} breach(es):")
        for b in report["breaches"]:
            print(f"  ⚠️  {b}")
    else:
        print(f"[{report['overall_status']}] all {len(report['files'])} files fresh")
    return 0 if report["overall_status"] != "BREACH" else 2

if __name__ == "__main__":
    sys.exit(main())
