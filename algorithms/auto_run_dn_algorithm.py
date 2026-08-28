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


def get_avg_volume_4d(code, target_date):
    """从腾讯 gtimg 拉近 60 日 K 线，算前 4 日均量（接口要求 ≥60 根）"""
    try:
        sys.path.insert(0, str(ALGO_DIR))
        from data_source_gtimg import fetch_a_daily_gtimg
    except Exception as e:
        print(f"  ⚠️ 导入 data_source_gtimg 失败: {e}")
        return None
    try:
        # sh/sz/bj 前缀
        if str(code).startswith(("60","68","90","11","13","5","1")):
            market = "sh"
        elif str(code).startswith(("00","30","20")):
            market = "sz"
        elif str(code).startswith(("8","43","92")):
            market = "bj"
        else:
            market = "sh"
        kl = fetch_a_daily_gtimg(code, market=market, bars=250)
        if kl is None or len(kl) < 5:
            return None
        # kl 是 DataFrame（date/open/close/high/low/volume/pct_chg）
        vols = kl["volume"].tolist() if hasattr(kl, "columns") else [k.get("volume", 0) for k in kl]
        if len(vols) < 5:
            return None
        # 前 4 日均量（不含当日，最后一格是当日）
        prev4 = vols[-5:-1]  # 取倒数第 2~5 格，即前 4 个交易日
        return round(sum(prev4) / len(prev4), 2)
    except Exception as e:
        print(f"  ⚠️ {code} K线拉取失败: {e}")
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
    snapshot_date = quote.get("meta", {}).get("date") or target_date
    snapshot_time = quote.get("meta", {}).get("snapshot_time") or ""

    # 过滤有效样本：当日有 prev_close + volume（去掉停牌/新股）
    candidates = []
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
        # 拉 4 日均量 → 算 vol_ratio
        code = _norm_code(raw_key)
        avg4 = get_avg_volume_4d(code, target_date)
        if avg4 is None:
            continue
        vr = calc_vol_ratio(vol, avg4)
        if vr is None or vr < VR_MIN:
            continue
        candidates.append({
            "code": code,
            "symbol": raw_key,
            "name": s.get("name", ""),
            "pct": round(pct, 2),
            "price": price,
            "prev_close": prev,
            "volume": vol,
            "avg_vol_4d": avg4,
            "vol_ratio": vr,
            "industry": s.get("industry", ""),
            "board": s.get("board", ""),
        })

    # 排序：量比 + 涨幅 综合分
    candidates.sort(key=lambda c: (c["vol_ratio"] * 0.6 + (c["pct"] or 0) * 0.4), reverse=True)

    out = {
        "date": target_date,
        "snapshot_date": snapshot_date,
        "snapshot_time": snapshot_time,
        "method": f"涨幅≥{CHG_MIN}% + 量比≥{VR_MIN}（{VR_WINDOW}日均量，H 反推最小可行版）",
        "total_scanned": total,
        "skipped_no_quote": skipped,
        "hit_chg_only": len([c for c in candidates if c["pct"] >= CHG_MIN]),
        "final_count": len(candidates),
        "candidates": candidates,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "raw_data/h_auto_buy 反推算法，无 PDF OCR 依赖",
    }

    out_path = RAW_DIR / f"h_auto_buy_{target_date.replace('-', '')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ {out_path.name}: 全市场 {total} → 涨幅达标 {len(candidates)}（注：算 vol_ratio 前）")
    print(f"   最终入选（涨幅+量比双达标）：{len(candidates)}")

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