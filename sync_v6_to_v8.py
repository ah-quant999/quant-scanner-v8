#!/usr/bin/env python3
"""v6 数据 → v8 raw_data 同步桥（周末应急 / 日常可调度）

作用：把 stock-scanner (v6) data/ 下已生成的算法类/盘后类 JSON，同步到
quant-scanner-v8 (v8) raw_data/，使 v8_build_deploy.yml 自动构建 data/*.js。

设计原则：
- 只读 v6 data/，不写 v6。
- 按 v8 update_v8.py 的 DATA_SOURCES 文件名映射。
- 自动补 update_time（若原数据没有）。
- 不覆盖 cloud_fetch_v8.py 已负责的模块（避免双写冲突），
  但可通过 --force-cloud 强制覆盖。
- 默认只同步 post_close 类别；可用 --category 指定。

使用：
    python sync_v6_to_v8.py              # 同步 post_close 模块
    python sync_v6_to_v8.py --dry-run    # 只打印计划
    python sync_v6_to_v8.py --category post_close --push

注意：
- 本脚本需运行在同时能访问 v6 仓库和 v8 仓库的机器上。
- 推送到 origin/main 后，v8_build_deploy.yml 会自动构建 data/*.js。
"""

import json, os, sys, subprocess, shutil
from pathlib import Path
from datetime import datetime

V6_ROOT = Path(r"E:\workspace\stock-scanner")
V8_ROOT = Path(__file__).resolve().parent
V6_DATA = V6_ROOT / "data"
V8_RAW = V8_ROOT / "raw_data"

# v6 文件名 → v8 raw_data 文件名
V6_TO_V8 = {
    "gold_pool.json":               "gold_pool.json",
    "candidate_pool.json":          "candidate.json",
    "triple_consensus.json":        "triple_consensus.json",
    "triple_track.json":            "triple_track.json",
    "triple_resonance_history.json":"triple_history.json",
    "top10_daily.json":             "top10_daily.json",
    "lhb_result.json":              "lhb_data.json",
    "sector_rs.json":               "sector_rs.json",
    "sh_index_fib.json":            "sh_fib.json",
    "sz_index_fib.json":            "sz_fib.json",
    "inst_trade.json":              "inst_trade.json",
    "crds_result.json":             "crds_card_data.json",
    "cockpit_tier_recommend_alimi.json": "cockpit_tier_recommend.json",
    "cockpit_advice.json":          "cockpit_advice.json",
    "cockpit_backtest.json":        "cockpit_backtest.json",
    "backtest_tdx.json":            "backtest_tdx.json",
    "backtest_comprehensive.json":  "backtest_comprehensive.json",
    "mahoro_signals.json":          "mahoro.json",
    "stock_names.json":             "stock_names.json",
    "nt_data.json":                 "nt_data.json",
    "suspension_alert.json":        "suspension_alert.json",
    "market_alerts.json":           "market_alerts.json",
    "sector_fund_flow.json":        "sector_fund_flow_trend.json",
    "volatility_watch.json":        "volatility.json",
}

# cloud_fetch_v8.py 已负责的模块：默认跳过，避免双写
CLOUD_FETCH_VARS = {
    "ETF_INTRADAY_HEAT", "SECTOR_FUND_FLOW", "CONCEPT_RANKING", "IPO_DATA",
    "MARGIN_DATA", "CFFEX_HOLDINGS", "MACRO_DATA", "CRISIS_DATA",
    "HERDING_DATA", "LIMIT_UP_HEATMAP", "CAPITAL_FLOW_DATA", "ETF_SUBSCRIPTION",
    "NORTH_FUND", "MARKET_FUND_FLOW_DATA", "W52_HIGH", "ETF_PULSE",
    "ETF_DAILY_MONITOR", "ANALYST_RATINGS", "INDEX_QUOTES", "EXPERIMENT", "V8_CAL",
}


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ❌ 读取失败 {path}: {e}")
        return None


def _save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)


def _add_timestamp(obj):
    """若顶层没有 update_time/calc_time，补一个当前时间（仅作 freshness 参考）。"""
    if not isinstance(obj, dict):
        return obj
    if "update_time" not in obj and "calc_time" not in obj and "date" not in obj:
        obj["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return obj


def _enrich_sector_fund_flow_trend(obj):
    """为 sector_fund_flow_trend 补 net_10d / 回填 net_60d（从 v6 history 计算）。"""
    if not isinstance(obj, dict):
        return obj
    # 只有当对象带 sectors_in/top_list 等字段时才认为是板块资金流
    if not any(k in obj for k in ("sectors_in", "sectors_out", "top_list")):
        return obj
    hist_path = V6_DATA / "sector_fund_flow_history.json"
    hist = {}
    if hist_path.exists():
        try:
            with open(hist_path, encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:
            pass
    # 预计算各板块历史滚动和
    hist_sums = {}
    for name, days in hist.items():
        try:
            nets = sorted(days, key=lambda x: x.get("date", ""))
            vals = [d.get("net", 0) or 0 for d in nets]
            hist_sums[name] = {
                "n5": sum(vals[-5:]) if len(vals) >= 5 else None,
                "n10": sum(vals[-10:]) if len(vals) >= 10 else None,
                "n20": sum(vals[-20:]) if len(vals) >= 20 else None,
                "n60": sum(vals[-60:]) if len(vals) >= 60 else None,
            }
        except Exception:
            pass

    def enrich(s):
        if not isinstance(s, dict):
            return s
        name = s.get("name")
        h = hist_sums.get(name, {}) if name else {}
        out = dict(s)
        # 仅当原值缺失/为None/为0 时用历史回填；保留 v6 API 原始值优先
        for key, hist_key in [("net_5d", "n5"), ("net_10d", "n10"), ("net_20d", "n20"), ("net_60d", "n60")]:
            val = out.get(key)
            if (val is None or val == 0) and h.get(hist_key) is not None:
                out[key] = round(h[hist_key], 2)
        return out

    for key in ("sectors_in", "sectors_out", "top_list", "trend_5d", "trend_20d", "trend_60d"):
        if key not in obj or not isinstance(obj[key], list):
            continue
        obj[key] = [enrich(s) for s in obj[key]]

    # 构建 trend_10d（从 sectors_in/out 去重）
    seen = set()
    trend_10d = []
    for key in ("sectors_in", "sectors_out"):
        for s in obj.get(key, []):
            name = s.get("name")
            if name and name not in seen and s.get("net_10d") is not None:
                seen.add(name)
                trend_10d.append(s)
    obj["trend_10d"] = trend_10d
    return obj


def sync(category="post_close", dry_run=False, force_cloud=False, push=False):
    # 加载 v8 DATA_SOURCES / CATEGORY_MAP（避免硬编码耦合）
    sys.path.insert(0, str(V8_ROOT))
    try:
        import update_v8 as uv8
    finally:
        sys.path.pop(0)

    var_to_cat = uv8.CATEGORY_MAP
    fname_to_var = uv8.DATA_SOURCES
    var_to_fname = {v: k for k, v in fname_to_var.items()}

    target_vars = {v for v, c in var_to_cat.items() if c == category}
    if not target_vars:
        print(f"⚠️ category={category} 无目标变量")
        return 1

    plan = []
    skipped_cloud = []
    missing = []
    synced = []

    for v6_name, v8_name in V6_TO_V8.items():
        var = fname_to_var.get(v8_name)
        if not var or var not in target_vars:
            continue
        if var in CLOUD_FETCH_VARS and not force_cloud:
            skipped_cloud.append((v6_name, v8_name, var))
            continue
        v6_path = V6_DATA / v6_name
        if not v6_path.exists():
            missing.append((v6_name, v8_name, var))
            continue
        plan.append((v6_path, v8_name, var))

    print(f"=== v6→v8 同步计划 (category={category}) ===")
    print(f"目标变量数: {len(target_vars)}")
    print(f"将从 v6 同步: {len(plan)}")
    if skipped_cloud:
        print(f"跳过（cloud_fetch 负责）: {len(skipped_cloud)}  {', '.join(v for _,_,v in skipped_cloud)}")
    if missing:
        print(f"v6 源文件缺失: {len(missing)}  {', '.join(v for _,_,v in missing)}")

    if dry_run:
        for v6_path, v8_name, var in plan:
            print(f"  [DRY] {v6_path.name} -> raw_data/{v8_name} (window.{var})")
        return 0

    for v6_path, v8_name, var in plan:
        obj = _load_json(v6_path)
        if obj is None:
            missing.append((v6_path.name, v8_name, var))
            continue
        if v8_name == "sector_fund_flow_trend.json":
            obj = _enrich_sector_fund_flow_trend(obj)
        obj = _add_timestamp(obj)
        v8_path = V8_RAW / v8_name
        _save_json(v8_path, obj)
        synced.append((v6_path.name, v8_name, var))
        print(f"  ✅ {v6_path.name} -> raw_data/{v8_name} (window.{var})")

    print(f"\n实际同步: {len(synced)}")
    if missing:
        print(f"仍缺失: {len(missing)}  {', '.join(v for _,_,v in missing)}")

    if push and synced:
        print("\n--- git push ---")
        subprocess.run(["git", "add", "-f", "raw_data/"], cwd=V8_ROOT, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=V8_ROOT
        )
        if result.returncode == 0:
            print("ℹ️ raw_data 无变化，无需 push")
            return 0
        msg = f"data(v8): v6→v8 同步 {category} 模块 ({len(synced)}个)\n\n" + \
              "\n".join(f"- {v}: {s} -> raw_data/{t}" for s, t, v in synced)
        subprocess.run(["git", "commit", "-m", msg], cwd=V8_ROOT, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=V8_ROOT, check=True)
        print("✅ 已 push origin/main，v8_build_deploy.yml 将自动构建")

    return 0 if not missing else 2


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v6 data to v8 raw_data bridge")
    parser.add_argument("--category", default="post_close",
                        choices=["premarket", "intraday", "post_close"],
                        help="同步哪个类别的模块")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划")
    parser.add_argument("--force-cloud", action="store_true",
                        help="强制覆盖 cloud_fetch 已负责的模块")
    parser.add_argument("--push", action="store_true", help="同步后 git push")
    args = parser.parse_args()
    sys.exit(sync(category=args.category, dry_run=args.dry_run,
                  force_cloud=args.force_cloud, push=args.push))
