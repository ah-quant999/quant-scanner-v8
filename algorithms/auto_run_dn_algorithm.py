#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H 反推算法自动跑脚本（脱离 PDF OCR 依赖）
=====================================================

🎯 设计目标：
   把 PDF 8.10/8.17「短线买点」人工标签反推成可代码化的算法，
   每天用 STOCK_QUOTE + 4日均量 自动算出"今日短线买点候选"，
   不再需要主人每天提供 PDF + 跑 OCR。

📐 反推方法（H 任务 · 最小可行版 2026-08-10）：
   涨幅 ≥ 3% （基于样本中位数 3.03，min 0.69, max 10.16）
   量比 ≥ 1.2 （基于样本中位数 1.19，min 0.91, max 1.97）
   量比 = 当日量 / 4日均量

📊 验证结果（来自 raw_data/pdf_dn_817_validation.json）：
   8.17 当日短线买点候选 → hit_rate 75.8%（25/33 命中 PDF 8.17 推荐的 33 只）
   8.10 → 8.17 T+5 回测胜率 45.7%（raw_data/pdf_t5_backtest.json）

🔧 用法：
   python algorithms/auto_run_dn_algorithm.py                  # 当日股票池跑一遍
   python algorithms/auto_run_dn_algorithm.py --date 2026-08-17 # 指定日期验证（用 STK 日线）
   python algorithms/auto_run_dn_algorithm.py --verify          # 验证 8.17 vs PDF baseline 命中率
   python algorithms/auto_run_dn_algorithm.py --emit-js         # 输出 data/H_AUTO_BUY.js 给前端注入

📤 输出：
   raw_data/h_auto_buy_<date>.json   - 当日候选股 + 命中标记
   data/H_AUTO_BUY.js                - 前端注入（window.H_AUTO_BUY）带 ?v= 缓存戳
   命中率打 stdout（vs PDF baseline）

⚠️ 已知边界：
   - 4日均量从腾讯 ifzq K线（前复权）取，本机若无历史 K 线缓存，需走 data_source_gtimg 实时拉
   - 其它 5 个 category（反弹/反弹01/超跌反弹/加速/强势股）暂未反推，留扩展位
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = ROOT / "raw_data"
ALGO_DIR = ROOT / "algorithms"
OUT_JS = DATA_DIR / "H_AUTO_BUY.js"
BASELINE_FILE = RAW_DIR / "pdf_baseline.json"
VALIDATION_FILE = RAW_DIR / "pdf_dn_817_validation.json"

# H 反推阈值（基于 raw_data/pdf_dn_reverse_result.json 35 样本分布）
CHG_MIN = 3.0   # 涨幅下限（中位数 3.03%，覆盖 50%+ 样本）
VR_MIN = 1.2    # 量比下限（中位数 1.19，取整到 1.2）
VR_WINDOW = 4   # 量比窗口：当日量 / 4日均量

# 🛡 2026-09-07 一劳永逸：并发取「前 4 日均量」的线程数。
#   原实现串行逐只 HTTP（数百只）→ 云端 runner 抓中国源必超时被 kill → 无产物。
#   默认 16（网络 IO 密集型，非 CPU 密集）；可用 V8_H_WORKERS 环境变量覆盖。
import os as _os
MAX_WORKERS = int(_os.environ.get("V8_H_WORKERS", "16"))


def load_window_var(path, var_name):
    """读 data/*.js 的 `window.XXX = {...};` 形式（无正则，括号配对版）。

    旧正则 `\\{.*?\\}` 非贪婪会在首个内层 `}` 截断（如 {"sentiment":{"label":...}} 嵌套对象），
    得到非法 JSON。改用括号配对：定位目标变量 -> 从其 `=` 后做配对，遇字符串内 `{}` 跳过，
    配对到 0 才切，嵌套/多变量都正确。
    """
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        print(f"⚠️ 读取 {path} 失败: {e}")
        return None
    try:
        idx = src.find(f"window.{var_name}")
        if idx == -1:
            return None
        eq = src.find("=", idx)
        start = src.find("{", eq) if eq != -1 else -1
        if start == -1:
            return None
        depth = 0
        in_str = esc = False
        for i in range(start, len(src)):
            ch = src[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(src[start : i + 1])
        return None
    except Exception as e:
        print(f"⚠️ 解析 {path} 失败: {e}")
        return None


def _norm_code(code):
    """归一化代码（去前缀/后缀）"""
    return re.sub(r"\D", "", str(code or ""))


def calc_vol_ratio(vol_today, vol_prev_4d):
    """量比 = 当日量 / 4日均量（vr_window=4）"""
    if not vol_prev_4d or vol_prev_4d <= 0:
        return None
    return round(vol_today / vol_prev_4d, 3)


def _market_prefix(code):
    """返回 sh/sz/bj 前缀。"""
    if str(code).startswith(("60","68","90","11","13","5","1")):
        return "sh"
    if str(code).startswith(("00","30","20")):
        return "sz"
    if str(code).startswith(("8","43","92")):
        return "bj"
    return "sh"


def _fetch_kline_akshare(code, bars=250):
    """akshare 东财前复权日线兜底（gtimg 境外抖动/限流时用）。返回 DataFrame 或 None。"""
    try:
        import akshare as ak
        n = _norm_code(code)
        prefix = _market_prefix(n)
        symbol = f"{prefix}{n}"
        end = datetime.now()
        start = end - datetime.timedelta(days=bars * 2)
        df = ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        if df is None or len(df) < 60:
            return None
        return df
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
# 🛡 2026-09-07 一劳永逸：H 反推「前 4 日均量」取数层重写
# ────────────────────────────────────────────────────────────────────────────
# 【事故】2026-09-05 ~ 09-07 H_AUTO_BUY 卡断更 3 天（前端红灯）。
# 【根因】原实现只有「腾讯 gtimg 逐只 HTTP + akshare 单兜底」两条弱源，且对全市场
#   涨幅≥3% 的数百只股票**串行**逐只拉取。云端 runner（美国 IP）抓中国源基本不可达
#   → 请求挂起/失败 → 30 分钟超时被 kill → h_auto_buy_<date>.json 根本没写出来
#   → track_h_auto_buy 主源缺失、兜底读旧 data/H_AUTO_BUY.js → 前端冻结在 09-04。
# 【修法】四层加固（本段代码），调用方再叠加并发：
#   ① 本地缓存 raw_data/kline_cache/<code>.json（随仓入仓，云端零网络可读）新鲜则用
#   ② 复用 calc_stock_rps 的统一三级兜底链「mootdx → 东财 → baostock + 熔断器」
#      （同仓早有成熟取数链，本脚本此前没复用 = 本次事故根子）
#   ③ 上一步取到的 K 线回写缓存，逐晚收敛，缓存越跑越全（与 factor_lab_gen 同款策略）
#   ④ 网络全挂时退回（可能陈旧的）本地缓存并标 degraded，宁可出滞后数据也不出空，
#      最后由 gtimg 老路径兜底
# ════════════════════════════════════════════════════════════════════════════
KLINE_CACHE_DIR = RAW_DIR / "kline_cache"
_KLINE_STAT = {"cache_fresh": 0, "cache_stale": 0, "net": 0, "fail": 0}
_SRC_UNIFIED = None   # calc_stock_rps._query_kline 延迟导入句柄（None=未试，False=失败）


def _unified_query_kline():
    """延迟导入统一三级兜底取数链（mootdx → 东财 → baostock，带 SOURCE_BREAKER 熔断）。

    云端 runner 抓腾讯/东财常失败，但该链会自动降级到 baostock（境外可达），
    不再由本脚本自己硬碰网络。导入失败返回 None（调用方退回 gtimg 老路径）。
    """
    global _SRC_UNIFIED
    if _SRC_UNIFIED is not None:
        return _SRC_UNIFIED or None
    try:
        sys.path.insert(0, str(ALGO_DIR))
        import calc_stock_rps as _rps
        fn = getattr(_rps, "_query_kline", None)
        _SRC_UNIFIED = fn if callable(fn) else False
        if not _SRC_UNIFIED:
            print("  ⚠️ calc_stock_rps._query_kline 不可用，退回 gtimg 老路径")
    except Exception as e:
        print(f"  ⚠️ 导入统一取数链失败（退回 gtimg 老路径）: {e}")
        _SRC_UNIFIED = False
    return _SRC_UNIFIED or None


def _vols_from_cache(code):
    """读本地缓存，返回 (vols_list, last_date_str)；无缓存返回 (None, None)。"""
    try:
        p = KLINE_CACHE_DIR / f"{_norm_code(code)}.json"
        if not p.exists():
            return None, None
        d = json.load(open(p, encoding="utf-8"))
        rows = d if isinstance(d, list) else (d.get("klines") or d.get("data") or [])
        if not isinstance(rows, list) or len(rows) < 5:
            return None, None
        vols, last_date = [], ""
        for r in rows:
            if not isinstance(r, dict):
                continue
            v = r.get("volume") or r.get("vol") or 0
            try:
                vols.append(float(v))
            except Exception:
                continue
            ld = str(r.get("date", ""))[:10]
            if ld > last_date:
                last_date = ld
        return (vols, last_date) if len(vols) >= 5 else (None, None)
    except Exception:
        return None, None


def _vols_to_cache(code, df):
    """把 DataFrame 日线回写本地缓存（逐晚收敛，让后续跑批零网络直取）。失败静默。"""
    try:
        KLINE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        rows = []
        for _, r in df.tail(250).iterrows():
            rows.append({
                "date": str(r.get("date", ""))[:10],
                "open": r.get("open"), "close": r.get("close"),
                "high": r.get("high"), "low": r.get("low"),
                "volume": r.get("volume"), "pct_chg": r.get("pct_chg"),
            })
        if len(rows) < 5:
            return
        p = KLINE_CACHE_DIR / f"{_norm_code(code)}.json"
        json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def _prev4(vols):
    """前 4 日均量（不含当日，最后一格是当日）。"""
    if not vols or len(vols) < 5:
        return None
    prev4 = vols[-5:-1]
    return round(sum(prev4) / len(prev4), 2)


def _stale_days(snapshot_date):
    """行情快照日距今几个自然日（>1 说明 STOCK_QUOTE 陈旧，产物口径需谨慎）。"""
    try:
        d = datetime.strptime(str(snapshot_date)[:10], "%Y-%m-%d").date()
        return (datetime.now().date() - d).days
    except Exception:
        return -1


def get_avg_volume_4d(code, target_date=None, quote_date=None):
    """前 4 日均量。取数链：缓存(新鲜) → 三级兜底网络(回写缓存) → 缓存(陈旧, degraded) → gtimg。

    quote_date: 行情快照日（STOCK_QUOTE.meta.date）。缓存末根日期 >= 它才算新鲜。
    """
    code = _norm_code(code)
    # ① 本地缓存且新鲜 → 零网络直取
    vols, last_date = _vols_from_cache(code)
    if vols and quote_date and last_date and last_date >= str(quote_date)[:10]:
        _KLINE_STAT["cache_fresh"] += 1
        return _prev4(vols)

    # ② 统一三级兜底链（mootdx → 东财 → baostock + 熔断）
    fn = _unified_query_kline()
    if fn is not None:
        try:
            df = fn(code, _market_prefix(code), 60)
            if df is not None and len(df) >= 5:
                v = df["volume"].tolist() if hasattr(df, "columns") else None
                if v:
                    _vols_to_cache(code, df)      # ③ 回写缓存，逐晚收敛
                    _KLINE_STAT["net"] += 1
                    return _prev4(v)
        except Exception:
            pass

    # ④ 网络全挂 → 退回（可能陈旧的）本地缓存，保障出数不空
    if vols:
        _KLINE_STAT["cache_stale"] += 1
        return _prev4(vols)

    # ⑤ 最后兜底：腾讯 gtimg 老路径
    try:
        from data_source_gtimg import fetch_a_daily_gtimg
        kl = fetch_a_daily_gtimg(code, market=_market_prefix(code), bars=250)
        if kl is not None and len(kl) >= 5:
            v = kl["volume"].tolist() if hasattr(kl, "columns") else [k.get("volume", 0) for k in kl]
            if v and len(v) >= 5:
                _KLINE_STAT["net"] += 1
                return _prev4(v)
    except Exception:
        pass

    _KLINE_STAT["fail"] += 1
    return None


def run_for_today(emit_js=False, target_date=None):
    """
    每日跑 H 反推算法：
    1. 读 STOCK_QUOTE.js 当日全市场（涨幅、量）
    2. 对每只股票：涨幅≥3% → 拉 4 日 K线算 vol_ratio → vol_ratio≥1.2 入选
    3. 输出 raw_data/h_auto_buy_<date>.json + data/H_AUTO_BUY.js
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    quote = load_window_var(DATA_DIR / "STOCK_QUOTE.js", "STOCK_QUOTE")
    if not quote or "stocks" not in quote:
        print("❌ data/STOCK_QUOTE.js 不可用")
        return None
    # 🛡 2026-09-07：meta 里未必有 date 字段（实测 STOCK_QUOTE.js 只有 update_time），
    #   必须从 update_time 的日期段兜底取，否则停更时 snapshot_date 会退化成"今天"。
    _meta = quote.get("meta", {}) or {}
    snapshot_date = (_meta.get("date")
                     or str(_meta.get("update_time") or "")[:10]
                     or target_date)
    snapshot_time = str(_meta.get("update_time") or _meta.get("snapshot_time") or "")
    # 🛡 2026-09-07 一劳永逸：文件与数据日期一律跟「行情快照日」走，不能用今天。
    #   原实现用今天命名 → 若 STOCK_QUOTE 停更（本次 09-04 起停 3 天），会把 09-04 的
    #   行情写进 h_auto_buy_20260907.json，track 的 T+1/T+3/T+5 全部按错位日期跟踪，
    #   胜率历史被静默污染（比"不出数"更危险，因为它看起来是正常的）。
    if snapshot_date and target_date != snapshot_date:
        print(f"  🛡 行情快照日 {snapshot_date} ≠ 目标日 {target_date} → 以快照日为准（防日期错位污染跟踪历史）")
        target_date = snapshot_date

    # 过滤有效样本：当日有 prev_close + volume（去掉停牌/新股）
    # 🛡 2026-09-07 一劳永逸：先筛涨幅达标，再「并发」批量取前 4 日均量。
    #   原实现串行逐只 HTTP（数百只 × 网络往返）→ 云端 runner 抓中国源必挂 →
    #   30 分钟超时被 kill → 产物文件根本写不出来（H_AUTO_BUY 断更 3 天的直接诱因）。
    chg_pool = []
    skipped = 0
    total = len(quote["stocks"])
    for raw_key, s in quote["stocks"].items():
        pct = s.get("pct")
        vol = s.get("volume")
        prev = s.get("prev_close")
        price = s.get("price")
        if pct is None or vol is None or prev is None or price is None:
            skipped += 1
            continue
        if pct < CHG_MIN:
            continue  # 涨幅不达标
        chg_pool.append((raw_key, s))

    print(f"  🔎 涨幅≥{CHG_MIN}% 共 {len(chg_pool)} 只 → 并发取前 4 日均量（{MAX_WORKERS} 线程）")
    t0 = datetime.now()
    avg_map = {}
    if chg_pool:
        from concurrent.futures import ThreadPoolExecutor

        def _job(item):
            raw_key, _s = item
            return raw_key, get_avg_volume_4d(_norm_code(raw_key), target_date,
                                              quote_date=snapshot_date)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for raw_key, avg4 in ex.map(_job, chg_pool):
                if avg4 is not None:
                    avg_map[raw_key] = avg4
    print(f"  ⏱ 均量取数 {(datetime.now() - t0).total_seconds():.1f}s｜"
          f"缓存新鲜 {_KLINE_STAT['cache_fresh']} / 网络 {_KLINE_STAT['net']} / "
          f"缓存陈旧 {_KLINE_STAT['cache_stale']} / 失败 {_KLINE_STAT['fail']}")

    candidates = []
    for raw_key, s in chg_pool:
        avg4 = avg_map.get(raw_key)
        if avg4 is None:
            continue
        vol = s.get("volume")
        vr = calc_vol_ratio(vol, avg4)
        if vr is None or vr < VR_MIN:
            continue
        code = _norm_code(raw_key)
        candidates.append({
            "code": code,
            "symbol": raw_key,
            "name": s.get("name", ""),
            "pct": round(s.get("pct"), 2),
            "price": s.get("price"),
            "prev_close": s.get("prev_close"),
            "volume": vol,
            "avg_vol_4d": avg4,
            "vol_ratio": vr,
            "industry": s.get("industry", ""),
            "board": s.get("board", ""),
        })

    # 排序：量比 + 涨幅 综合分
    candidates.sort(key=lambda c: (c["vol_ratio"] * 0.6 + (c["pct"] or 0) * 0.4), reverse=True)

    # 🛡 2026-08-29 高手画像版 H反推对照组：低价(<15元) + 主板 + 医药/化工/贵金属/农业
    EXPERT_MAX_PRICE = 15.0
    EXPERT_BOARDS = {"主板"}
    EXPERT_INDUSTRY_KEYWORDS = {"医药", "化工", "贵金属", "农业"}
    expert_candidates = []
    for c in candidates:
        if (c.get("price") or 999) >= EXPERT_MAX_PRICE:
            continue
        if c.get("board") not in EXPERT_BOARDS:
            continue
        ind = c.get("industry", "")
        if not any(kw in ind for kw in EXPERT_INDUSTRY_KEYWORDS):
            continue
        expert_candidates.append(c)

    _now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = {
        "date": target_date,
        "snapshot_date": snapshot_date,
        "snapshot_time": snapshot_time,
        "method": f"涨幅≥{CHG_MIN}% + 量比≥{VR_MIN}（{VR_WINDOW}日均量，H 反推最小可行版）",
        "total_scanned": total,
        "skipped_no_quote": skipped,
        "hit_chg_only": len(chg_pool),      # 🛡 涨幅达标数（原字段错算成 vol_ratio 后的 candidates 数）
        "final_count": len(candidates),
        "candidates": candidates,
        "expert_method": f"{EXPERT_MAX_PRICE}元以下 + 主板 + 医药/化工/贵金属/农业（高手画像版）",
        "expert_count": len(expert_candidates),
        "expert_candidates": expert_candidates,
        "generated_at": _now_str,
        # 🛡 2026-09-07：update_time 是健康面板判新鲜度的唯一字段。旧版靠 update_v8.py
        #    事后注入（时机不可控，且依赖 build 覆盖到本文件），一旦注入没落到这里，
        #    前端就显示"无时间戳/陈旧"。本脚本直接产出，保证任何时候 H_AUTO_BUY.js 自带时间戳。
        "update_time": _now_str,
        "source": "raw_data/h_auto_buy 反推算法，无 PDF OCR 依赖",
        # 🛡 2026-09-07 可观测性：让「降产出数」与「取数全挂」在产物里显式可见，
        #   而不是像本次事故那样只表现为"文件不存在"，排查要翻日志才知道。
        "kline_stat": dict(_KLINE_STAT),
        "degraded": _KLINE_STAT["net"] == 0 and _KLINE_STAT["cache_fresh"] == 0,
        "degraded_reason": ("全部取数走陈旧本地缓存或失败（网络不可达）"
                            if (_KLINE_STAT["net"] == 0 and _KLINE_STAT["cache_fresh"] == 0)
                            else ""),
        "quote_stale_days": _stale_days(snapshot_date),
    }

    out_path = RAW_DIR / f"h_auto_buy_{target_date.replace('-', '')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ {out_path.name}: 全市场 {total} → 涨幅达标 {len(chg_pool)}")
    print(f"   最终入选（涨幅+量比双达标）：{len(candidates)}"
          + (f"  ⚠️ DEGRADED: {out['degraded_reason']}" if out["degraded"] else ""))

    if emit_js:
        _emit_js(out)
    return out


def _emit_js(out):
    """输出 data/H_AUTO_BUY.js 给前端注入"""
    payload = "/* H 反推算法自动跑（脱离 PDF OCR） */\nwindow.H_AUTO_BUY = " + json.dumps(out, ensure_ascii=False) + ";\n"
    OUT_JS.write_text(payload, encoding="utf-8")
    print(f"✅ {OUT_JS.name} 已写入（含 ?v= 缓存戳待 update_v8.py 注入）")


def verify_against_baseline():
    """
    验证：用 8.17 PDF baseline 的 33 只「短线买点」作为真值，
    看反推算法在 8.17 当日数据上的命中率。
    期望：hit_rate 75.8%（raw_data/pdf_dn_817_validation.json 已有此结果）
    """
    print("=== 验证：H 反推算法 vs PDF 8.17 baseline ===")
    if not VALIDATION_FILE.exists():
        print(f"❌ {VALIDATION_FILE.name} 不存在，无法验证")
        return
    val = json.load(open(VALIDATION_FILE, encoding="utf-8"))
    print(f"  baseline date: {val.get('date')} | category: {val.get('category')}")
    print(f"  总数 {val.get('total')} | 命中 {val.get('hit')} | 命中率 {val.get('hit_rate')}%")
    print(f"  rows 示例: {val.get('rows', [])[:3]}")


def main():
    parser = argparse.ArgumentParser(description="H 反推 PDF 短线买点算法（自动跑，脱离 PDF OCR）")
    parser.add_argument("--date", help="目标日期（YYYY-MM-DD，默认今日）")
    # 🛡 2026-08-19 默认 --emit-js ON：run_algorithms.py daily 调用无需每次加 flag，部署口径统一
    parser.add_argument("--no-emit-js", dest="emit_js", action="store_false", help="不写 data/H_AUTO_BUY.js（默认写）")
    parser.add_argument("--emit-js", dest="emit_js", action="store_true", help="显式开关（与默认相同，保留兼容）")
    parser.set_defaults(emit_js=True)
    parser.add_argument("--verify", action="store_true", help="验证 vs PDF 8.17 baseline 命中率")
    args = parser.parse_args()

    if args.verify:
        verify_against_baseline()
        return 0

    out = run_for_today(emit_js=args.emit_js, target_date=args.date)
    if out is None:
        return 1

    # 自动跑完后顺便显示 PDF baseline 命中率（若文件存在）
    if BASELINE_FILE.exists():
        print("\n=== 8.17 baseline 命中率参考 ===")
        verify_against_baseline()

    return 0


if __name__ == "__main__":
    sys.exit(main())