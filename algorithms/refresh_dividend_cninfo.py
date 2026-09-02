"""
refresh_dividend_cninfo.py — 用巨潮资讯(cninfo)刷新重点股票的「最新分红方案」字段。

背景（2026-08-13 宝丰能源 600989 分红陈旧 bug）：
  fetch_stock_quote_v8.py::merge_dividend() 只用 akshare stock_fhps_em()，
  该源对「最新一期分红预案/方案」覆盖不全、且常停留在已实施的上一年度，
  导致个股查询/行情详情里的分红字段显示陈旧方案（宝丰仍显 2024 年度分配）。
  巨潮资讯 stock_dividend_cninfo() 是交易所法定披露源，含完整历史+最新预案，
  能正确取到刚公布的分红方案（宝丰 2026-04-22 公告的 2025 年报 10派4.2）。

本脚本（根因修复，非数据补丁）：
  1. 从 data/PORTFOLIO.js(持仓) + data/CANDIDATE.js(候选池) + data/GOLD_POOL.js(黄金池)
     合并出「重点关注股票池」（约 300+ 只，非全市场，避免 cninfo 逐只限流）。
  2. 对每只调用 ak.stock_dividend_cninfo(code6)，取「最新一期分红方案」行。
  3. 更新 raw_data/stock_quote.json 中对应 stocks[code8].dividend 的方案字段
     （plan_date/record_date/ex_date/progress/announce_date/cash_ratio/yield），
     不动 em 提供的 fundamentals(eps/bvps 等)。
  4. 重新生成 data/STOCK_QUOTE.js（update_v8._write_js），让看板即时生效。
  5. 不改动其它字段、不碰 index.html，可安全 commit/push 让云端继承。

调用：
  python refresh_dividend_cninfo.py            # 刷新默认三池并集
  python refresh_dividend_cninfo.py --dry      # 只打印将更新的方案，不落盘
由盘前/晚间 automation 调用，跑完自行 commit+push（见调度脚本）。
"""
import json
import re
import sys
import time
from datetime import datetime, date

import akshare as ak

HERE = __import__("pathlib").Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
RAW_DIR = HERE / "raw_data"
DATA_DIR = HERE / "data"
QUOTE_RAW = RAW_DIR / "stock_quote.json"
TODAY = date.today()

UNIVERSE_FILES = {
    "PORTFOLIO": DATA_DIR / "PORTFOLIO.js",
    "CANDIDATE": DATA_DIR / "CANDIDATE.js",
    "GOLD_POOL": DATA_DIR / "GOLD_POOL.js",
}
# 手动关注列表（用户指定、但不在候选池/持仓/黄金池里的票，如宝丰能源 600989）
WATCH_FILE = DATA_DIR / "DIVIDEND_WATCH.json"


def _load_js(p):
    t = open(p, encoding="utf-8").read()
    t = t.split("=", 1)[1].rstrip().rstrip(";").strip()
    return json.loads(t)


def build_universe():
    codes = set()
    # 持仓
    try:
        d = _load_js(UNIVERSE_FILES["PORTFOLIO"])
        for p in d.get("positions", []):
            c = p.get("code", "")
            c = re.sub(r"^(sh|sz|bj|hk)", "", str(c))
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 PORTFOLIO 失败:", e)
    # 候选池
    try:
        d = _load_js(UNIVERSE_FILES["CANDIDATE"])
        for k, v in d.get("stocks", {}).items():
            c = str(v.get("code", k.split("_")[-1]))
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 CANDIDATE 失败:", e)
    # 黄金池
    try:
        d = _load_js(UNIVERSE_FILES["GOLD_POOL"])
        for k, v in d.get("candidates", {}).items():
            c = str(v.get("code", k.split("_")[-1]))
            if c.isdigit() and len(c) == 6:
                codes.add(c)
    except Exception as e:
        print("⚠️ 读 GOLD_POOL 失败:", e)
    # 手动关注列表
    try:
        if WATCH_FILE.exists():
            w = json.loads(WATCH_FILE.read_text(encoding="utf-8"))
            for c in w.get("codes", []):
                c = str(c).lstrip("shszbjhk")
                if c.isdigit() and len(c) == 6:
                    codes.add(c)
    except Exception as e:
        print("⚠️ 读 DIVIDEND_WATCH 失败:", e)
    return codes


def _to_date(s):
    if not s or (isinstance(s, float) and s != s):  # NaN
        return None
    if isinstance(s, (int, float)):
        return None
    s = str(s).strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    return None


def _report_sort_date(rep):
    """把 '2025年报'/'2025半年报' 等映射成可排序日期，用于选最新方案。"""
    if not rep:
        return None
    rep = str(rep)
    ym = re.search(r"(\d{4})", rep)
    if not ym:
        return None
    y = int(ym.group(1))
    if "一季" in rep:
        return date(y, 3, 31)
    if "半年" in rep or "中报" in rep:
        return date(y, 6, 30)
    if "三季" in rep:
        return date(y, 9, 30)
    return date(y, 12, 31)


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^0-9.\-]", "", str(v))
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def pick_latest_plan(df):
    """从 cninfo DataFrame 选最新一期分红方案，返回映射字典。"""
    rows = []
    for _, r in df.iterrows():
        impl = _to_date(r.get("实施方案公告日期"))
        rep = _report_sort_date(r.get("报告时间"))
        key = impl or rep
        if key is None:
            continue
        rows.append(
            {
                "key": key,
                "impl": impl,
                "rep": r.get("报告时间"),
                "type": r.get("分红类型"),
                "cash": _num(r.get("派息比例")),
                "record": _to_date(r.get("股权登记日")),
                "ex": _to_date(r.get("除权日")),
                "desc": r.get("实施方案分红说明"),
            }
        )
    if not rows:
        return None
    rows.sort(key=lambda x: x["key"], reverse=True)
    latest = rows[0]
    ex = latest["ex"]
    impl = latest["impl"]
    if ex and ex <= TODAY:
        progress = "实施分配"
    elif impl and impl <= TODAY:
        progress = "实施分配"
    else:
        progress = "预案"
    return {
        "plan_date": (impl.isoformat() if impl else (latest["rep"] or "")),
        "announce_date": (impl.isoformat() if impl else ""),
        "record_date": (latest["record"].isoformat() if latest["record"] else ""),
        "ex_date": (ex.isoformat() if ex else ""),
        "progress": progress,
        "cash_ratio": latest["cash"],
        "report_period": (latest["rep"] or ""),
        "type": (latest["type"] or ""),
        "desc": (latest["desc"] or ""),
    }


def code8_of(code):
    """估算 STOCK_QUOTE 的键前缀。"""
    if code[0] in "69":
        return "sh" + code
    if code[0] in "84":
        return "bj" + code
    return "sz" + code


def main():
    dry = "--dry" in sys.argv
    codes = build_universe()
    # 支持 --codes 600989,000333 仅刷新指定票（用于定向修补）
    for a in sys.argv:
        if a.startswith("--codes="):
            codes = set(c.lstrip("shszbjhk") for c in a.split("=", 1)[1].split(",") if c.strip())
    print(f"🎯 重点股票池: {len(codes)} 只（持仓+候选池+黄金池+手动关注）")

    quote = json.load(open(QUOTE_RAW, encoding="utf-8"))
    stocks = quote.get("stocks", {})
    updated = 0
    failed = 0
    highlights = []
    for code in sorted(codes):
        c8 = code8_of(code)
        if c8 not in stocks:
            for pre in ("sh", "sz", "bj"):
                if pre + code in stocks:
                    c8 = pre + code
                    break
        if c8 not in stocks:
            continue
        df = None
        for _ in range(3):
            try:
                df = ak.stock_dividend_cninfo(symbol=code)
                break
            except Exception:
                time.sleep(2)
        if df is None:
            failed += 1
            continue
        if df is None or len(df) == 0:
            continue
        plan = pick_latest_plan(df)
        if not plan:
            continue
        div = stocks[c8].get("dividend") or {}
        price = stocks[c8].get("price") or stocks[c8].get("close")
        if plan["cash_ratio"] is not None and price:
            try:
                plan["yield"] = round((plan["cash_ratio"] / 10.0) / float(price), 10)
            except Exception:
                plan["yield"] = div.get("yield")
        else:
            plan["yield"] = div.get("yield")
        for k in ("eps", "bvps", "cap_reserve", "undist_profit", "net_profit_yoy", "total_share_yi"):
            if k in div:
                plan[k] = div[k]
        if dry:
            print(f"[dry] {c8} -> {plan['plan_date']} 10派{plan['cash_ratio']} {plan['progress']}")
            updated += 1
            continue
        stocks[c8]["dividend"] = plan
        updated += 1
        if code == "600989":
            highlights.append(
                f"✅ 宝丰能源(600989): {plan['plan_date']} 10派{plan['cash_ratio']} "
                f"{plan['progress']} 除权{plan['ex_date']}"
            )
        time.sleep(0.05)  # 礼貌限速，避免 cninfo 限流

    print(f"📊 已更新分红方案: {updated} 只 / 失败跳过: {failed} 只")
    for h in highlights:
        print(h)

    if dry:
        print("（dry 模式，未落盘）")
        return

    quote["stocks"] = stocks
    json.dump(quote, open(QUOTE_RAW, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    sys.path.insert(0, str(HERE))
    import update_v8
    out = update_v8._write_js("STOCK_QUOTE", quote)
    print(f"✅ 已写回 {QUOTE_RAW.name} 并重建 {out}")


if __name__ == "__main__":
    main()
