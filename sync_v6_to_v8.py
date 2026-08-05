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
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

def now_cst():
    """返回中国标准时间（Asia/Shanghai）的当前 datetime。"""
    return datetime.now(CST)

V6_ROOT = Path(os.environ.get("V6_ROOT", r"E:\workspace\stock-scanner"))
V8_ROOT = Path(__file__).resolve().parent
V6_DATA = V6_ROOT / "data"
V8_RAW = V8_ROOT / "raw_data"

# v6 文件名 → v8 raw_data 文件名
V6_TO_V8 = {
    "stock_names.json":             "stock_names.json",
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
    "market_fund_flow.json":        "market_fund_flow.json",
    "volatility_watch.json":        "volatility.json",
    # ⚠️ 已原生化（2026-08-02）：以下 4 个孤儿不再经本桥同步，由 v8 算法链直接产出：
    #   nt_data.json → nt_data.json                     (fetch_orphan_nt_data.py)
    #   suspension_alert.json → suspension_alert.json   (fetch_orphan_suspension.py)
    #   market_alerts.json → market_alerts.json         (fetch_orphan_market_alerts.py)
    #   sector_fund_flow.json → sector_fund_flow_trend.json (fetch_orphan_sector_fund_flow.py)
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
    """若顶层没有 update_time/calc_time，补一个当前时间（仅作 freshness 参考）。

    顶层是 list（如 STOCK_LIST）：包装成 {"data": [...], "update_time": ...}，
    与 update_v8._write_js 规则一致；index.html 通过 .data 读取实际数组。
    """
    if isinstance(obj, list):
        return {"data": obj, "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S")}
    if not isinstance(obj, dict):
        return obj
    if "update_time" not in obj and "calc_time" not in obj and "date" not in obj:
        obj["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    return obj


def _append_lhb_to_history():
    """把最新一天的分类龙虎榜（raw_data/lhb_data.json）追加进 raw_data/lhb_history.json，
    实现每日自动累积历史（供机游共振/北向席位日历使用）。已存在的日期跳过。"""
    lhb = V8_RAW / "lhb_data.json"
    if not lhb.exists():
        return
    obj = _load_json(lhb)
    if not obj or not obj.get("stocks"):
        return
    ds = str(obj.get("date", ""))  # 形如 20260731
    if len(ds) != 8:
        return
    iso = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
    hist_path = V8_RAW / "lhb_history.json"
    hist = {}
    if hist_path.exists():
        try:
            hist = _load_json(hist_path) or {}
        except Exception:
            hist = {}
    if iso in hist:
        return  # 当日已追加，跳过
    hist[iso] = {
        "trading": True,
        "stocks": obj["stocks"],
        "summary": obj.get("summary", {}),
    }
    hist["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    if "range" not in hist:
        hist["range"] = [iso, iso]
    _save_json(hist_path, hist)
    print(f"  🐉 龙虎榜历史追加 {iso}（{len(obj['stocks'])} 只，共振{obj.get('summary',{}).get('机游共振',0)}）")


def build_stock_profile():
    """从 v6 industry_map.json + stock_names.json 构建压缩版 STOCK_PROFILE。

    仅保留 A 股基础档案（行业、前10概念、板块标签），用于个股查询反查概念/行业。
    大小约 350KB，远小于完整 industry_map（1.9MB）。
    """
    v6_industry = V6_DATA / "industry_map.json"
    v6_names = V6_DATA / "stock_names.json"
    if not v6_industry.exists() or not v6_names.exists():
        print("  ⚠️ 缺少 industry_map.json 或 stock_names.json，跳过 STOCK_PROFILE")
        return False

    ind = _load_json(v6_industry)
    names = _load_json(v6_names)
    if not ind or not names:
        return False

    industry_stocks = ind.get("stocks", {})
    profiles = {}
    for s in names:
        code = s.get("code")
        if not code:
            continue
        market = s.get("market", "")
        if not market:
            fc = (s.get("full_code") or "").lower()
            if fc.startswith(("sh", "sz", "bj")):
                market = fc[:2]
        key = f"{market}_{code}".lower()
        info = industry_stocks.get(key) or industry_stocks.get(code)
        if not info:
            continue
        concepts = info.get("concepts", [])
        # 过滤掉纯指数/风格标签，保留题材概念：去掉以年份、HS/MSCI/上证/深证/中证等开头或含"风格"的
        filtered = [c for c in concepts if not (
            c.startswith(("20", "HS", "MSCI", "上证", "深证", "中证", "富时", "标准", "QFII", "基金", "昨日", "最近", "行业", "周期", "大盘", "中盘", "小盘", "成长", "价值")) or
            "风格" in c or "重仓" in c or "持股" in c or "AH股" in c or "沪股通" in c or "深股通" in c
        )]
        profiles[code] = {
            "industry": info.get("industry"),
            "concepts": filtered[:10],
        }

    out = {
        "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(profiles),
        "profiles": profiles,
    }
    out_path = V8_RAW / "stock_profile.json"
    _save_json(out_path, out)
    print(f"  ✅ STOCK_PROFILE: {len(profiles)} 只（约 {out_path.stat().st_size/1024:.0f}KB）")
    return True


def sync(category="post_close", dry_run=False, force_cloud=False, push=False, only=None):
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
    if only:
        # 仅同步指定孤儿变量（绕过 category 过滤），用于只补 v8 原生链不产出的模块
        only_set = set(only) if isinstance(only, (list, tuple, set)) else {x.strip().upper() for x in str(only).split(",") if x.strip()}
        target_vars = only_set & set(var_to_cat.keys())
        if not target_vars:
            print(f"⚠️ --only 指定的变量均不存在于 CATEGORY_MAP: {only}")
            return 1
        print(f"⚠️ --only 模式：仅同步 {sorted(target_vars)}（绕过 category={category}）")
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
        obj = _add_timestamp(obj)
        v8_path = V8_RAW / v8_name
        _save_json(v8_path, obj)
        synced.append((v6_path.name, v8_name, var))
        print(f"  ✅ {v6_path.name} -> raw_data/{v8_name} (window.{var})")
        if var == "LHB_DATA":
            _append_lhb_to_history()

    print(f"\n实际同步: {len(synced)}")
    if missing:
        print(f"仍缺失: {len(missing)}  {', '.join(v for _,_,v in missing)}")

    # 构建压缩版个股档案（行业/概念/板块），供个股查询使用
    profile_ok = build_stock_profile()

    if push and (synced or profile_ok):
        print("\n--- git push ---")
        subprocess.run(["git", "add", "-f", "raw_data/"], cwd=V8_ROOT, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=V8_ROOT
        )
        if result.returncode == 0:
            print("ℹ️ raw_data 无变化，无需 push")
            return 0
        parts = [f"- {v}: {s} -> raw_data/{t}" for s, t, v in synced]
        if profile_ok:
            parts.append("- STOCK_PROFILE: 压缩个股档案（行业/概念/板块）")
        msg = f"data(v8): v6→v8 同步 {category} 模块 ({len(synced)}个)\n\n" + "\n".join(parts)
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
    parser.add_argument("--only", default=None,
                        help="只同步指定 v8 变量（逗号分隔），绕过 category 过滤；用于只补 v8 原生链不产出的孤儿模块")
    args = parser.parse_args()
    sys.exit(sync(category=args.category, dry_run=args.dry_run,
                  force_cloud=args.force_cloud, push=args.push, only=args.only))
