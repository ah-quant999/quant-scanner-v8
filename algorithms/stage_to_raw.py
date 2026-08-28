#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stage_to_raw.py — 把 algorithms/out/ 下的 v6 命名文件，按 V6_TO_V8 重命名为
v8 raw_data/ 命名，并注入 update_time。

只提升 V6_TO_V8 中登记的产物；out/ 里的“输入类”文件（scan_result /
guanlan_* / mahoro_signals / fundamental_quality / lhb_history 等）保持不动，
作为下一轮运行的输入，由 run_algorithms.py 每轮从 v6 重新灌入。

2026-08-09 修复：原先 `sys.path.insert(V8_ROOT); import sync_v6_to_v8` 从仓库根
导入同步桥，而 commit 5a4ba34b 已把该文件迁到 legacy_v6/ 子目录 → ImportError，
导致 v8_algo_cloud 的 [2] stage_to_raw 整步崩溃、盘后产物自 08-04 起冻结。
现把映射表与工具函数【内联】到本文件，算法链不再依赖 legacy_v6 同步桥。
"""
import os
import sys
import json
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")


def now_cst():
    return datetime.datetime.now(CST)


# 2026-08-07 修复：以下产物由生成器【直写 raw_data/】（gen_triple_consensus /
# gen_triple_track 于 08-06 改造），out/ 下同名文件是历史僵尸副本。
# 若继续搬运，会用 08-06 旧数据覆盖当日新结果 -> 前端长期显示 3 天前数据。
SKIP_STAGE = {
    "triple_consensus.json",
    "triple_track.json",
}

V8_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALGO = os.path.dirname(os.path.abspath(__file__))
# out 目录与 run_algorithms / 被迁移脚本口径一致 = 仓库根/out
OUT = os.path.join(V8_ROOT, "out")
RAW = os.path.join(V8_ROOT, "raw_data")

# ---------------------------------------------------------------------------
# v6 产物名 → v8 raw_data 名（内联自 legacy_v6/sync_v6_to_v8.py，勿再 import）
# ---------------------------------------------------------------------------
V6_TO_V8 = {
    "stock_names.json":                  "stock_names.json",
    "gold_pool.json":                    "gold_pool.json",
    "candidate_pool.json":               "candidate.json",
    "triple_consensus.json":             "triple_consensus.json",
    "triple_track.json":                 "triple_track.json",
    "triple_resonance_history.json":     "triple_history.json",
    "top10_daily.json":                  "top10_daily.json",
    "lhb_result.json":                   "lhb_data.json",
    "sector_rs.json":                    "sector_rs.json",
    "sh_index_fib.json":                 "sh_fib.json",
    "sz_index_fib.json":                 "sz_fib.json",
    "inst_trade.json":                   "inst_trade.json",
    "crds_result.json":                  "crds_card_data.json",
    "cockpit_tier_recommend_alimi.json": "cockpit_tier_recommend.json",
    "cockpit_advice.json":               "cockpit_advice.json",
    "cockpit_backtest.json":             "cockpit_backtest.json",
    "backtest_tdx.json":                 "backtest_tdx.json",
    "backtest_comprehensive.json":       "backtest_comprehensive.json",
    # 2026-08-28 主人令：mahoro 不再跟踪，移除映射
    "market_fund_flow.json":             "market_fund_flow.json",
    "volatility_watch.json":             "volatility.json",
    # 已原生化（2026-08-02）：nt_data / suspension_alert / market_alerts /
    # sector_fund_flow 由 fetch_orphan_*.py 直写 raw_data，不走本表。
}


def _load_json(path):
    _p = Path(path)
    try:
        with open(_p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # 2026-08-24 抗丢失：主文件损坏时从 .bak 恢复，防止 lhb_history 等
        # 累积型文件被并发取消风暴清空后彻底丢失（共振日历「数据又没了」根因）。
        _bak = _p.with_suffix(_p.suffix + ".bak")
        if _bak.exists():
            try:
                with open(_bak, encoding="utf-8") as f:
                    print(f"  ↩️ {path} 读取损坏，从 .bak 恢复: {e}")
                    return json.load(f)
            except Exception:
                pass
        print(f"  ❌ 读取失败 {path}: {e}")
        return None


def _save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _bak = path.with_suffix(path.suffix + ".bak")
    _tmp = path.with_suffix(path.suffix + ".tmp")
    # 2026-08-24 抗丢失：原子写（临时文件 replace）+ 写成功后存 .bak。
    # 避免被并发取消风暴杀掉时留下半截 JSON 清空数据。
    with open(_tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
    _tmp.replace(path)
    try:
        with open(_bak, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        pass


def _add_timestamp(obj):
    """顶层无 update_time/calc_time/date 时补当前时间；list 包装成 {"data": [...]}，
    与 update_v8._write_js 口径一致（index.html 通过 .data 读实际数组）。"""
    if isinstance(obj, list):
        return {"data": obj, "update_time": now_cst().strftime("%Y-%m-%d %H:%M:%S")}
    if not isinstance(obj, dict):
        return obj
    if "update_time" not in obj and "calc_time" not in obj and "date" not in obj:
        obj["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    return obj


def append_lhb_to_history():
    """把最新一天的分类龙虎榜（raw_data/lhb_data.json）追加进 raw_data/lhb_history.json，
    供机游共振 / 北向席位日历使用。
    2026-08-11 修复：空壳占位符(trading=False/stocks=0)不再阻塞真实数据，改为覆盖更新。
    2026-08-12 修复：骨架数据(trading=True 但 seats 全空)也允许覆盖——主人质疑北向席位日历 4 天空白，
    原 c232edf5a 拉回了 trading+stocks 但 seats={}，需要让后续回填能覆盖。"""
    lhb = Path(RAW) / "lhb_data.json"
    if not lhb.exists():
        return False
    obj = _load_json(lhb)
    if not obj or not obj.get("stocks"):
        return False
    ds = str(obj.get("date", ""))  # 形如 20260731
    if len(ds) != 8:
        return False
    iso = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
    hist_path = Path(RAW) / "lhb_history.json"
    hist = {}
    if hist_path.exists():
        hist = _load_json(hist_path) or {}
    # 修复：空壳占位符 OR 骨架数据(stocks>0 但所有股票 seats={})应被真实数据覆盖，而非永久阻塞
    if iso in hist:
        existing = hist[iso]
        existing_stocks = existing.get("stocks", []) or []
        is_shell = existing.get("trading") is False or len(existing_stocks) == 0
        # 骨架检测：trading=True 且 stocks>0，但所有股票的 seats 全空
        is_skeleton = existing.get("trading") is True and len(existing_stocks) > 0 and all(
            (not (s or {}).get("seats")) for s in existing_stocks
        )
        has_real_data = existing.get("trading") is True and len(existing_stocks) > 0 and not is_skeleton
        if has_real_data:
            return False  # 真实数据（含 seats）已存在，跳过
        if is_skeleton:
            print(f"  🔄 覆盖骨架数据 {iso}（原 trading=True stocks={len(existing_stocks)} 但 seats 全空 → 新 {len(obj['stocks'])} 只）")
        else:
            print(f"  🔄 覆盖空壳占位 {iso}（原 trading={existing.get('trading')} "
                  f"stocks={len(existing_stocks)} → 新 {len(obj['stocks'])} 只）")
    hist[iso] = {
        "trading": True,
        "stocks": obj["stocks"],
        "summary": obj.get("summary", {}),
    }
    hist["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    if "range" not in hist:
        hist["range"] = [iso, iso]
    _save_json(hist_path, hist)
    print(f"  🐉 龙虎榜历史追加 {iso}（{len(obj['stocks'])} 只，"
          f"共振{obj.get('summary', {}).get('机游共振', 0)}）")
    return True


_TS_KEYS = ("update_time", "gen_time", "calc_time", "run_time",
            "fetch_time", "snapshot_time")


def _ts_full(path):
    """取文件内容里的完整时间戳(YYYY-MM-DD HH:MM:SS)；取不到返回 ''。

    2026-08-11 新增：原 _ts_date 只比到「日」，同一天内 out 旧版覆盖 raw 新版
    不会被拦截（实例：out 08:00 的 4 源候选池覆盖 raw 06:59 的 6 源修复版）。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            for k in _TS_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and len(v) >= 19:
                    return v[:19].replace("T", " ")
    except Exception:
        pass
    return ""


def _source_names(path):
    """取 source_dist 的有效源名集合（用于判定搬运是否会丢源）。取不到返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        sd = obj.get("source_dist") if isinstance(obj, dict) else None
        if isinstance(sd, dict) and sd:
            return {k for k, v in sd.items() if v}
    except Exception:
        pass
    return None


def _ts_date(path):
    """取文件内容里的时间戳日期(YYYY-MM-DD)；无时间戳字段则回退到 mtime 日期。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            for k in _TS_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and len(v) >= 10:
                    return v[:10]
    except Exception:
        pass
    try:
        return datetime.datetime.fromtimestamp(
            os.path.getmtime(path)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def main():
    os.makedirs(RAW, exist_ok=True)
    promoted = 0
    for v6_name, v8_name in V6_TO_V8.items():
        src = os.path.join(OUT, v6_name)
        if not os.path.exists(src):
            continue
        # (1) 生成器直写 raw_data 的产物，禁止再从 out/ 搬运覆盖。
        #     但若 v6/v8 命名不同（如 triple_resonance_history.json → triple_history.json），
        #     生成器直写的是 raw_data/<v6_name>，需桥接复制到 raw_data/<v8_name>，
        #     否则 update_v8 读 <v8_name> 永远拿到旧数据（2026-08-10 修复）。
        if v6_name in SKIP_STAGE or v8_name in SKIP_STAGE:
            if v6_name != v8_name:
                raw_src = os.path.join(RAW, v6_name)
                if os.path.exists(raw_src):
                    obj = _load_json(raw_src)
                    if obj is not None:
                        obj = _add_timestamp(obj)
                        _save_json(Path(RAW) / v8_name, obj)
                        promoted += 1
                        print(f"  [bridge] raw_data/{v6_name} -> raw_data/{v8_name}")
                        continue
            print(f"  [skip] 生成器直写 raw_data: {v6_name}")
            continue
        # (2) 防僵尸覆盖：out 源比 raw 目标旧则拒绝搬运
        dst_path = os.path.join(RAW, v8_name)
        if os.path.exists(dst_path):
            s_date, d_date = _ts_date(src), _ts_date(dst_path)
            if s_date and d_date and s_date < d_date:
                print(f"  [guard] out更旧({s_date}) < raw({d_date}): {v6_name}")
                continue
            # (2a) 同日内的时间戳倒退也要拦（原守卫只比到「日」，同日无效）
            s_ts, d_ts = _ts_full(src), _ts_full(dst_path)
            if s_ts and d_ts and s_ts < d_ts:
                print(f"  [guard] out更旧({s_ts}) < raw({d_ts}): {v6_name}")
                continue
# (2b) 丢源守卫：搬运会让 source_dist 少源则拒绝
#      2026-08-11 修复：out/candidate_pool.json 曾两次用少源版本覆盖
#      raw_data/candidate.json（观澜台/maharo 丢失 → 前端「公开资讯 0 只」）。
#      2026-08-12 主人全面审核：发现历史丢源是「src（out）比 dst（raw）少源」的反向场景——
#      out 端丢了观澜台/maharo 时，反过来覆盖 raw 端原本完整的 6 源。
#      修复：双向检查 → src 缺源（dst 更全）也应拒绝搬运
            s_src, d_src = _source_names(src), _source_names(dst_path)
            if s_src is not None and d_src is not None:
                src_missing = d_src - s_src  # src 比 dst 少的源（dst 更全）
                if src_missing:
                    print(f"  [guard] src 比 dst 少源 {sorted(src_missing)}（dst 更全），保留 raw: {v6_name}")
                    continue
        obj = _load_json(src)
        if obj is None:
            print(f"  ⚠️ 跳过（解析失败）: {v6_name}")
            continue
        obj = _add_timestamp(obj)
        # 2026-08-18 补：sector_rs.json 兜底注入 data_date（板块周期卡比对锚点）
        if v8_name == "sector_rs.json" and isinstance(obj, dict):
            if not obj.get("data_date"):
                ut = obj.get("update_time") or ""
                obj["data_date"] = ut[:10] if len(ut) >= 10 else now_cst().strftime("%Y-%m-%d")
                print(f"  [fix] sector_rs.json 兜底注入 data_date={obj['data_date']}")
        _save_json(Path(RAW) / v8_name, obj)
        promoted += 1
        print(f"  ✅ {v6_name} -> raw_data/{v8_name}")
    print(f"\nstaged: {promoted} 个文件")
    return promoted


if __name__ == "__main__":
    main()
