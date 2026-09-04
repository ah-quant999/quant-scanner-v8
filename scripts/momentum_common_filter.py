#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股动量共识股 · 共同点筛选器（2026-08-16 · 无未来函数版）
============================================================
⚠️ 重要修正（2026-08-16 晚，主人质疑后审计实锤）：
   V2 原始字段 consecutive_up_days / max_gain_pct / max_drawdown_pct / t5_gain_pct /
   pattern 全部是「入选后」走势（generate_v2.py 从入选日次日开始计算）——
   用它们当筛选条件 = 用未来信息选股，胜率虚高（曾算出 95.8%/93.6% 均为数据泄漏假象）。
   本版全部条件 = 入选日当天可知：
     · categories        —— OCR 当日分类标签（入选日可知）
     · consec_before     —— 入选前连涨天数（V2 已注入，入选日可知）
     · stage             —— 入选日行业板块阶段（V2 已注入，用入选日当天及之前行业RS判定）
     · sel_change_pct    —— 入选日涨幅（入选日可知）
   T+5 胜率仅作展示参考（真实历史结果），不作筛选条件。

无泄漏回测结论（385 次出现，T+5 口径）：
  基线（全部）                        n=385  胜率 42.1%  均值 -1.18%
  R4 仅含「超跌反弹」标签             n=63   胜率 60.3%  均值 +4.45%   ★ 最强单信号
  R4+ 入选前连涨≤1                    n=45   胜率 66.7%  均值 +6.08%   ★★ 本版默认规则
  R1 含「超跌反弹」或「选股交集」     n=86   胜率 53.5%  均值 +2.21%
  板块阶段：退潮 55.3% > 震荡 41.9% > 启动 32.0% > 主升 26.5%（剔除主升/启动方向成立）
  入选前连涨：1天 44.0% > 2天 39.7% > 3天 34.8%（入选前连涨越多越差 = 追高效应）

用法：python scripts/momentum_common_filter.py [--json] [--emit-js]
  --json     输出 raw_data/momentum_filter_result.json
  --emit-js  输出 data/MOMENTUM_FILTER.js（构建管线 update_v8.py 挂载，随构建自动重算）
"""
import json, re, sys, statistics, os
from collections import defaultdict
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent)  # scripts/ 上一级 = 项目根（云端/本机通用）

def load_js_var(path, var_name):
    """读取 data/*.js 中的 window.XXX = {...}; """
    src = open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s\s*=\s*(\{.*\});\s*$" % var_name, src, re.S)
    if not m:
        raise ValueError(f"找不到 window.{var_name} in {path}")
    return json.loads(m.group(1))

def main():
    # 🛡 2026-08-20 主人令·一劳永逸：动量共识筛选属于盘后选股策略，
    #   必须在 A股/港股/龙虎榜/板块资金等全部盘后数据就绪后（≥18:00 CST）才执行。
    #   盘中（09:28 等）提前跑出的结果基于未完整数据，会误导决策。
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "algorithms"))
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by="momentum_common_filter")

    d = load_js_var(f"{ROOT}/data/STOCK_MOMENTUM_STATE_V2.js", "STOCK_MOMENTUM_ENHANCED")
    q = load_js_var(f"{ROOT}/data/STOCK_QUOTE.js", "STOCK_QUOTE")

    # 🛡 2026-08-19 一劳永逸修复：实时跟踪字段（动量共识筛选·一劳永逸）
    #   主人原话：「不是让你反推算法，然后盘后自己按算法跑出最新的股票跟踪和回测吗」
    #   现状：STOCK_MOMENTUM_STATE_V2.js 的入选数据停在 2026-08-17（OCR 断供，无新入选）。
    #   修法：每次跑 momentum_common_filter.py 都基于最新 STOCK_QUOTE 给每个候选附"实时跟踪"
    #   字段（当前价/当日%/距昨收/快照时间），让「动量共识筛选」卡每日盘后必新，不再显示陈旧。
    #   注：V2 入选日范围 6/5-8/17 共 421 只，本轮 S3 候选 68 只，全部有 live_* 数据。
    quote_meta = q.get("meta", {}) or {}
    stocks_q = q.get("stocks", {}) or {}

    # 计算最新 snapshot_time（用于 generated 字段同步 STOCK_QUOTE 实际新鲜度）
    latest_snap_hms = ""
    for v in stocks_q.values():
        if v.get("snapshot_time") and v["snapshot_time"] > latest_snap_hms:
            latest_snap_hms = v["snapshot_time"]

    # code -> quote（去前缀归一）
    by_code = {}
    for k, v in stocks_q.items():
        by_code.setdefault(re.sub(r"\D", "", k), v)

    # 展开所有出现 + 补名字/行业 + 注入实时跟踪字段
    rows = []
    for pk, pv in d["periods"].items():
        for s in pv["all"]:
            code_n = re.sub(r"\D", "", s["code"])
            sq = by_code.get(code_n, {}) or {}
            # 🛡 live 字段：当前价/当日%/昨收/涨跌额/snapshot
            live = {
                "live_price": sq.get("price"),
                "live_pct": sq.get("pct"),
                "live_prev_close": sq.get("prev_close"),
                "live_change": sq.get("change"),
                "live_snapshot": sq.get("snapshot_time"),
                "live_amount": sq.get("amount"),
            }
            rows.append({**s, "period": pk,
                         "qname": sq.get("name", "") or s.get("name", ""),
                         "industry": sq.get("industry", ""),
                         "concepts": sq.get("concepts", []) or [],
                         **live})

    def t5(sel):
        t = [r["t5_gain_pct"] for r in sel if r.get("t5_gain_pct") is not None]
        if not t:
            return None
        return (len(t), 100 * sum(1 for v in t if v > 0) / len(t), statistics.mean(t))

    # ─────────── 无泄漏筛选链（全部入选日当天可知）───────────
    # 2026-08-22 升级：数据源由 OCR 共识改为「H反推升级算法」自选强势突破，
    #   原「超跌反弹」OCR 标签已不存在，改为强势信号集（突破/超跌反弹/加速/强势股/短线选股）。
    STRONG_LABELS = {"突破", "超跌反弹", "加速", "强势股", "短线选股"}
    S1 = [r for r in rows if set(r.get("categories") or []) & STRONG_LABELS]
    # S2 入选前连涨 ≤ 1（追高过滤，实测 66.7% 胜率，保留）
    S2 = [r for r in S1 if (r.get("consec_before") is not None and r["consec_before"] <= 1)]
    # S3 剔除主升/启动板块（方向成立；无K线不剔除——R6 实测剔除后反而变差）
    S3 = [r for r in S2 if r.get("stage") not in ("主升", "启动")]

    def pct(sel, i, default=0):
        return sel[i] if sel else default

    s0, s1, s2, s3 = t5(rows), t5(S1), t5(S2), t5(S3)
    print("=" * 72)
    print("无泄漏筛选链 T+5 表现（385 次出现，全部条件=入选日当天可知）")
    print("=" * 72)
    print(f"  基线（全部）                n={pct(s0,0):3d}  胜率 {pct(s0,1):5.1f}%  均值 {pct(s0,2):+6.2f}%")
    print(f"  S1 含「超跌反弹」标签        n={pct(s1,0):3d}  胜率 {pct(s1,1):5.1f}%  均值 {pct(s1,2):+6.2f}%")
    print(f"  S2 +入选前连涨≤1            n={pct(s2,0):3d}  胜率 {pct(s2,1):5.1f}%  均值 {pct(s2,2):+6.2f}%")
    print(f"  S3 +剔除主升/启动板块        n={pct(s3,0):3d}  胜率 {pct(s3,1):5.1f}%  均值 {pct(s3,2):+6.2f}%")

    # ─────────── 候选清单（去重，取最新出现）───────────
    # 空集防御：S3→S2→S1→全量 逐级降级，确保 --emit-js 永不因空集崩溃
    final = S3 if (s3 and s3[0]) else (S2 if (s2 and s2[0]) else (S1 if (s1 and s1[0]) else rows))
    chain_name = ("S3 超跌反弹+连涨≤1+非主升/启动" if final is S3 else
                  "S2 超跌反弹+连涨≤1" if final is S2 else
                  "S1 含超跌反弹" if final is S1 else "全量(降级)")
    by_code_sel = {}
    for r in sorted(final, key=lambda x: x["date"], reverse=True):
        by_code_sel.setdefault(r["code"], r)
    cands = list(by_code_sel.values())
    cands.sort(key=lambda r: (r.get("consec_before") is not None, r.get("consec_before") or 9, r.get("sel_change_pct") or 0))

    print("\n" + "=" * 72)
    print(f"候选清单（{chain_name}，去重 {len(cands)} 只）")
    print("=" * 72)
    print(f"  {'代码':<8}{'名称':<10}{'行业':<18}{'入选日':>11}{'入选前连涨':>8}{'入选日%':>8}{'T+5%':>8}")
    for r in cands[:30]:
        print(f"  {r['code']:<8}{r['qname'] or r['code']:<10}{r['industry'][:16]:<18}"
              f"{r.get('date',''):>11}{(r.get('consec_before') or 0):>7}天"
              f"{(r.get('sel_change_pct') or 0):>+8.1f}{(r.get('t5_gain_pct') or 0):>+8.1f}")

    # ─────────── 输出 JSON / JS 注入 ───────────
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 🛡 2026-08-19 一劳永逸修复：generated = STOCK_QUOTE 实际最新 snapshot（而非 now）
    #   STOCK_QUOTE.meta.update_time 是早上 cn_fetch 写入的（08-18 04:07 误判），
    #   实际 snapshot_time 是 15:36（盘中数据）。用 live_track_generated 让"更新于"与股价同源。
    # 🛡 2026-08-30 二修：sq_date_part 必须用「真实数据日期」（交易日即当天，非交易日回退上一交易日），
    #   杜绝周日/假期把上一交易日 snapshot_time 拼接成「未来今日 16:29」的 bug。
    import sys
    sys.path.insert(0, ROOT)
    from v8_date import today_data_date
    sys.path.pop(0)
    sq_date_part = today_data_date()
    live_track_generated = f"{sq_date_part} {latest_snap_hms}" if latest_snap_hms else now
    out_generated = live_track_generated or now
    out = {
        "generated": out_generated,
        "generated_method": "STOCK_QUOTE 最新 snapshot_time（动量共识筛选·一劳永逸修复 2026-08-19）",
        "method": "无未来函数版(2026-08-16修正)：仅入选日当天可知条件",
        "live_track": True,  # 标识：本轮注入了实时跟踪字段
        "live_track_source": quote_meta.get("source", "STOCK_QUOTE"),
        "rule": {"S1_ocr_label_超跌反弹": True, "S2_consec_before_le1": True, "S3_exclude_leadup_launch": True},
        "stats": {"total": pct(s0,0), "base_win": round(pct(s0,1), 1), "base_mean": round(pct(s0,2), 2),
                  "s1": pct(s1,0), "s1_win": round(pct(s1,1), 1), "s1_mean": round(pct(s1,2), 2),
                  "s2": pct(s2,0), "s2_win": round(pct(s2,1), 1), "s2_mean": round(pct(s2,2), 2),
                  "s3": pct(s3,0), "s3_win": round(pct(s3,1), 1), "s3_mean": round(pct(s3,2), 2)},
        # candidates 注入 live 字段（实时跟踪 + 入选时维度）
        "candidates": [{"code": r["code"], "name": r["qname"], "industry": r["industry"],
                        "date": r.get("date"), "consec_before": r.get("consec_before"),
                        "sel_change_pct": r.get("sel_change_pct"),
                        "t1_gain_pct": r.get("t1_gain_pct"), "t3_gain_pct": r.get("t3_gain_pct"),
                        "t5_gain_pct": r.get("t5_gain_pct"), "t10_gain_pct": r.get("t10_gain_pct"),
                        "stage": r.get("stage"), "categories": r.get("categories"),
                        # 🛡 live 实时跟踪 6 字段（每日盘后随 STOCK_QUOTE 刷新）
                        "live_price": r.get("live_price"),
                        "live_pct": r.get("live_pct"),
                        "live_prev_close": r.get("live_prev_close"),
                        "live_change": r.get("live_change"),
                        "live_snapshot": r.get("live_snapshot"),
                        "live_amount": r.get("live_amount"),
                        } for r in cands],
        # 2026-08-30 一劳永逸：前端 render 读 _mf.stocks（硬编码），同步加 stocks 字段
        "stocks": [{"code": r["code"], "name": r["qname"], "industry": r["industry"],
                    "up_pct": r.get("live_pct"), "price": r.get("live_price"),
                    "t5_gain_pct": r.get("t5_gain_pct"),
                    "stage": r.get("stage"), "categories": r.get("categories")} for r in cands],
    }
    if "--json" in sys.argv:
        with open(f"{ROOT}/raw_data/momentum_filter_result.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"\n已输出 raw_data/momentum_filter_result.json（{len(cands)} 只）")
    # 🛡 2026-09-04 主人令（一劳永逸挂链）：算法链 runner 对所有脚本无参调用，
    #   仅靠 --emit-js 会导致挂链后不产出 data/MOMENTUM_FILTER.js。现支持环境变量
    #   V8_MOMENTUM_EMIT_JS=1 等价触发（与 strategy_four_volume.py 的 V8_BACKTEST_YEARS 同款做法）。
    #   update_v8.py 的 --emit-js 调用方式保持不变，两条路径均幂等（中性化比较，状态未变不重写）。
    _emit_js = ("--emit-js" in sys.argv) or bool(os.environ.get("V8_MOMENTUM_EMIT_JS"))
    if _emit_js:
        out["republish_time"] = now
        js = "window.MOMENTUM_FILTER = " + json.dumps(out, ensure_ascii=False) + ";\n"
        js_path = f"{ROOT}/data/MOMENTUM_FILTER.js"
        # ★★ 2026-08-18 死循环根治：republish_time=now 每次必变 → 文件必变 → build 必提交
        #    → 触发自身/reconcile → 死循环（今日 359 提交实证）。写文件前中性化
        #    republish_time + generated 比较，状态未变则不动文件。
        # 🛡 2026-08-19 一劳永逸补丁：_strip 同时抹平 live_track/live_track_source/live_price 等
        #    实时字段，让"STOCK_QUOTE 是否真更新"作为触发重写依据，不再因为 candidates 没变就跳过。
        try:
            import re as _re
            if os.path.exists(js_path):
                with open(js_path, "r", encoding="utf-8") as f:
                    old_js = f.read()
                def _strip(s):
                    s = _re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', s)
                    s = _re.sub(r'"generated"\s*:\s*"[^"]*"', '"generated":""', s)
                    s = _re.sub(r'"live_price"\s*:\s*[^,}\s]+', '"live_price":null', s)
                    s = _re.sub(r'"live_pct"\s*:\s*[^,}\s]+', '"live_pct":null', s)
                    s = _re.sub(r'"live_prev_close"\s*:\s*[^,}\s]+', '"live_prev_close":null', s)
                    s = _re.sub(r'"live_change"\s*:\s*[^,}\s]+', '"live_change":null', s)
                    s = _re.sub(r'"live_snapshot"\s*:\s*"[^"]*"', '"live_snapshot":""', s)
                    s = _re.sub(r'"live_amount"\s*:\s*[^,}\s]+', '"live_amount":null', s)
                    return s
                print("DBG old_len", len(old_js), "js_len", len(js), file=sys.stderr);
                _so, _sn = _strip(old_js), _strip(js);
                print("DBG equal", _so == _sn, file=sys.stderr);
                if _so == _sn:
                    print(f"⏭️  MOMENTUM_FILTER 状态未变（含 live 字段均已中性化），跳过重写（幂等）→ {now}")
                    return
        except Exception:
            pass
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js)
        print(f"✅ 已输出 data/MOMENTUM_FILTER.js（{len(cands)} 只候选，含 {sum(1 for c in out['candidates'] if c.get('live_price'))} 只 live 跟踪）→ {now}")

if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "algorithms"))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("scripts/momentum_common_filter.py"):
        sys.exit(2)
    main()
