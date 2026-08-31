# -*- coding: utf-8 -*-
"""
cross_check_dividend.py — 分红方案交叉核对（cninfo 主源 vs 东财 stock_fhps_em）

背景：
  v8 个股查询/情绪龙头/潜力挖掘中的分红字段目前主源为巨潮资讯(cninfo)，
  通过 refresh_dividend_cninfo.py 更新到 raw_data/stock_quote.json。
  但 cninfo 与东财数据偶有差异（如 2026-08 万华化学分红金额异常），
  需要第二独立源做交叉核对，标出差异供人工复核。

本脚本：
  1. 读取 raw_data/stock_quote.json 中的 cninfo 分红数据。
  2. 用 akshare.stock_fhps_em 拉取东财最近 3 个报告期全市场分红数据。
  3. 按 code 合并东财最新记录。
  4. 对 cninfo 有分红记录的每只股票对比：
     - 每股派息（cninfo desc 解析 vs 东财 现金分红比例/10）
     - 股息率（相对误差 > 5% 标差异）
     - 除权除息日（日期不一致）
     - 方案进度（文本差异）
  5. 输出 raw_data/dividend_cross_check.json：
     - summary: 总核对数、一致数、差异数、缺失数
     - discrepancies: 差异明细（含两侧原始字段）
     - missing_in_em: cninfo 有但东财无的股票列表

使用：
  python v8/cross_check_dividend.py              # 全量核对并落盘
  python v8/cross_check_dividend.py --dry        # 只打印摘要，不落盘

注意：
  - 本脚本为本地数据层工具，可被前端「分红待核」逻辑二次消费；
    也可单独跑看差异报告。
  - akshare stock_fhps_em 按报告期取数，9月默认取 2024年报/2025半年报/2025年报三期，
    东财最新记录按「除权除息日/最新公告日期」取最近一条。
  - 差异判定偏保守：金额差异 > 0.02元/股、日期不一致、进度文本不同即标差异。
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import akshare as ak
import pandas as pd

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
QUOTE_FILE = RAW_DIR / "stock_quote.json"
OUT_JSON = RAW_DIR / "dividend_cross_check.json"
OUT_JS = DATA_DIR / "DIVIDEND_CROSS_CHECK.js"
UNIVERSE_FILES = {
    "PORTFOLIO": DATA_DIR / "PORTFOLIO.js",
    "CANDIDATE": DATA_DIR / "CANDIDATE.js",
    "GOLD_POOL": DATA_DIR / "GOLD_POOL.js",
}

# 默认核对的报告期（年报 1231 / 半年报 0630 / 三季报 0930）
DEFAULT_REPORT_PERIODS = ["20241231", "20250630", "20251231"]


def _to_6digit(code8):
    """sh600000 / sz000001 / bj430047 -> 600000 / 000001 / 430047"""
    return re.sub(r"^(sh|sz|bj|hk)", "", str(code8))


def _parse_cninfo_per_share(desc):
    """从 cninfo desc 解析每股派息。'10派3.21元' -> 0.321"""
    if not desc:
        return None
    desc = str(desc)
    # 匹配 10派X元 / 10送Y转Z派X元
    m = re.search(r"10(?:送\d+(?:\.\d+)?)?(?:转\d+(?:\.\d+)?)?派([0-9.]+)\s*元", desc)
    if m:
        return round(float(m.group(1)) / 10, 4)
    # 每股派X元
    m2 = re.search(r"每股派([0-9.]+)\s*元", desc)
    if m2:
        return round(float(m2.group(1)), 4)
    return None


def _parse_em_per_share(ratio):
    """东财'现金分红-现金分红比例'是10派金额，转每股。"""
    if ratio is None or (isinstance(ratio, float) and pd.isna(ratio)):
        return None
    try:
        return round(float(ratio) / 10, 4)
    except Exception:
        return None


def _norm_date(s):
    """统一日期格式为 YYYY-MM-DD，无法解析返回 None。"""
    if not s or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _load_js(path):
    t = open(path, encoding="utf-8").read()
    t = t.split("=", 1)[1].rstrip().rstrip(";").strip()
    return json.loads(t)


def build_universe():
    """与 refresh_dividend_cninfo.py 保持一致：持仓+候选池+黄金池。"""
    codes = set()
    # 持仓
    try:
        d = _load_js(UNIVERSE_FILES["PORTFOLIO"])
        for p in d.get("positions", []):
            c = str(p.get("code", "")).lstrip("shszbjhk")
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 PORTFOLIO 失败:", e)
    # 候选池
    try:
        d = _load_js(UNIVERSE_FILES["CANDIDATE"])
        for k, v in d.get("stocks", {}).items():
            c = str(v.get("code", k.split("_")[-1])).lstrip("shszbjhk")
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 CANDIDATE 失败:", e)
    # 黄金池
    try:
        d = _load_js(UNIVERSE_FILES["GOLD_POOL"])
        for k, v in d.get("candidates", {}).items():
            c = str(v.get("code", k.split("_")[-1])).lstrip("shszbjhk")
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 GOLD_POOL 失败:", e)
    return codes


def _load_cninfo_dividends(universe=None):
    print(f"读取 {QUOTE_FILE} ...")
    with open(QUOTE_FILE, "r", encoding="utf-8") as f:
        q = json.load(f)
    stocks = q.get("stocks", {})
    records = {}
    for code8, v in stocks.items():
        if not isinstance(v, dict):
            continue
        code6 = _to_6digit(code8)
        if universe is not None and code6 not in universe:
            continue
        d = v.get("dividend")
        if not d:
            continue
        records[code6] = {
            "code8": code8,
            "code6": code6,
            "desc": d.get("desc", ""),
            "yield": float(d.get("yield") or 0),
            "cash_ratio": float(d.get("cash_ratio") or 0),
            "ex_date": _norm_date(d.get("ex_date")),
            "progress": str(d.get("progress", "")).strip(),
            "cninfo_per_share": _parse_cninfo_per_share(d.get("desc", "")),
        }
    print(f"  cninfo 有分红记录: {len(records)} 只" + ("（重点池）" if universe else "（全市场）"))
    return records


def _fetch_em_by_period(period):
    """获取东财某报告期全市场分红数据，返回 DataFrame。"""
    print(f"拉取东财 {period} 分红数据 ...")
    try:
        df = ak.stock_fhps_em(date=period)
        if df is None or df.empty:
            return None
        # 列名：代码 名称 送转股份-送转总比例 送转股份-送转比例 送转股份-转股比例
        #       现金分红-现金分红比例 现金分红-股息率 每股收益 每股净资产 ...
        #       预案公告日 股权登记日 除权除息日 方案进度 最新公告日期
        # 保留关键列
        cols = ["代码", "现金分红-现金分红比例", "现金分红-股息率", "除权除息日", "方案进度", "最新公告日期"]
        keep = [c for c in cols if c in df.columns]
        return df[keep].copy()
    except Exception as e:
        print(f"  ⚠️ 东财 {period} 获取失败: {e}")
        return None


def _build_em_lookup(periods):
    """合并多报告期东财数据，按 code6 取最新记录。"""
    lookup = {}
    for period in periods:
        df = _fetch_em_by_period(period)
        if df is None:
            continue
        # 列名标准化
        rename = {}
        for c in df.columns:
            if c == "代码":
                rename[c] = "code6"
            elif c == "现金分红-现金分红比例":
                rename[c] = "cash_ratio"
            elif c == "现金分红-股息率":
                rename[c] = "yield"
            elif c == "除权除息日":
                rename[c] = "ex_date"
            elif c == "方案进度":
                rename[c] = "progress"
            elif c == "最新公告日期":
                rename[c] = "announce_date"
        if rename:
            df = df.rename(columns=rename)
        if "code6" not in df.columns:
            continue
        df["code6"] = df["code6"].astype(str).str.strip()
        for _, row in df.iterrows():
            code6 = row["code6"]
            ex = _norm_date(row.get("ex_date"))
            ann = _norm_date(row.get("announce_date"))
            per_share = _parse_em_per_share(row.get("cash_ratio"))
            rec = {
                "code6": code6,
                "period": period,
                "cash_ratio": float(row.get("cash_ratio") or 0) if pd.notna(row.get("cash_ratio")) else 0,
                "yield": float(row.get("yield") or 0) if pd.notna(row.get("yield")) else 0,
                "ex_date": ex,
                "progress": str(row.get("progress") or "").strip(),
                "announce_date": ann,
                "em_per_share": per_share,
            }
            # 取最新记录：优先最新公告日，其次除权除息日，再次报告期
            old = lookup.get(code6)
            if old is None:
                lookup[code6] = rec
            else:
                def key(r):
                    return (r["announce_date"] or "0000-00-00", r["ex_date"] or "0000-00-00", r["period"])
                if key(rec) > key(old):
                    lookup[code6] = rec
    print(f"  东财合并后最新记录: {len(lookup)} 只")
    return lookup


def _compare(cninfo, em):
    issues = []
    # 每股派息
    cps = cninfo.get("cninfo_per_share")
    eps = em.get("em_per_share")
    if cps is not None and eps is not None:
        if abs(cps - eps) > 0.02:
            issues.append({
                "field": "per_share",
                "cninfo": cps,
                "eastmoney": eps,
                "diff": round(cps - eps, 4),
            })
    elif cps is not None and eps is None:
        issues.append({"field": "per_share", "cninfo": cps, "eastmoney": None, "note": "东财无每股派息"})

    # 股息率（相对误差 > 5% 或绝对差 > 0.002）
    cy = cninfo.get("yield") or 0
    ey = em.get("yield") or 0
    if cy > 0 or ey > 0:
        rel_diff = abs(cy - ey) / max(cy, ey, 1e-9)
        abs_diff = abs(cy - ey)
        if rel_diff > 0.05 and abs_diff > 0.001:
            issues.append({
                "field": "yield",
                "cninfo": cy,
                "eastmoney": ey,
                "rel_diff": round(rel_diff, 4),
            })

    # 除权除息日
    cex = cninfo.get("ex_date")
    eex = em.get("ex_date")
    if cex and eex and cex != eex:
        issues.append({"field": "ex_date", "cninfo": cex, "eastmoney": eex})

    # 方案进度（忽略空值）
    cp = cninfo.get("progress", "")
    ep = em.get("progress", "")
    if cp and ep and cp != ep:
        issues.append({"field": "progress", "cninfo": cp, "eastmoney": ep})

    return issues


def cross_check(cninfo_records, em_lookup):
    total = len(cninfo_records)
    consistent = 0
    discrepancies = []
    missing_in_em = []

    for code6, crec in cninfo_records.items():
        erec = em_lookup.get(code6)
        if erec is None:
            missing_in_em.append(code6)
            continue
        issues = _compare(crec, erec)
        if issues:
            discrepancies.append({
                "code6": code6,
                "code8": crec.get("code8"),
                "cninfo": {k: v for k, v in crec.items() if k not in ["code6", "code8"]},
                "eastmoney": erec,
                "issues": issues,
            })
        else:
            consistent += 1

    return {
        "summary": {
            "total_checked": total,
            "consistent": consistent,
            "discrepancy_count": len(discrepancies),
            "missing_in_eastmoney": len(missing_in_em),
            "calc_time": datetime.now().isoformat(),
            "method": "cninfo(巨潮资讯) vs 东财(stock_fhps_em) 分红方案交叉核对",
            "report_periods": list(em_lookup.values())[0]["period"] if em_lookup else "",
        },
        "discrepancies": discrepancies,
        "missing_in_eastmoney": missing_in_em,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只打印摘要，不落盘")
    parser.add_argument("--all", action="store_true", help="核对全市场（默认只核对 refresh_dividend_cninfo.py 重点池）")
    parser.add_argument("--publish-js", action="store_true", help="同时生成 data/DIVIDEND_CROSS_CHECK.js 供前端引用（默认只写 raw_data JSON）")
    parser.add_argument("--periods", nargs="+", default=DEFAULT_REPORT_PERIODS,
                        help="东财报告期列表，如 20241231 20250630 20251231")
    args = parser.parse_args()

    print("=" * 60)
    print("分红方案交叉核对（cninfo vs 东财 stock_fhps_em）")
    print("=" * 60)

    universe = None if args.all else build_universe()
    cninfo_records = _load_cninfo_dividends(universe=universe)
    em_lookup = _build_em_lookup(args.periods)
    report = cross_check(cninfo_records, em_lookup)

    if not args.dry:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        out_files = [str(OUT_JSON)]
        if args.publish_js:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            js = "window.DIVIDEND_CROSS_CHECK = " + json.dumps(report, ensure_ascii=False, indent=2) + ";\n"
            with open(OUT_JS, "w", encoding="utf-8") as f:
                f.write(js)
            out_files.append(str(OUT_JS))
        print(f"✅ 已写入 {' 与 '.join(out_files)}")

    s = report["summary"]
    print(f"\n核对摘要:")
    print(f"  总样本:     {s['total_checked']}")
    print(f"  一致:       {s['consistent']} ({s['consistent']/max(s['total_checked'],1)*100:.1f}%)")
    print(f"  差异:       {s['discrepancy_count']} ({s['discrepancy_count']/max(s['total_checked'],1)*100:.1f}%)")
    print(f"  东财缺失:   {s['missing_in_eastmoney']} ({s['missing_in_eastmoney']/max(s['total_checked'],1)*100:.1f}%)")

    if report["discrepancies"]:
        print("\n前 10 条差异示例:")
        for d in report["discrepancies"][:10]:
            print(f"  {d['code6']} cninfo:{d['cninfo'].get('desc')} 东财:10派{d['eastmoney'].get('cash_ratio')}元 问题:{d['issues']}")


if __name__ == "__main__":
    main()
