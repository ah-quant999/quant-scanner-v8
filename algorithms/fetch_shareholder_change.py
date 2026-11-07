# -*- coding: utf-8 -*-
"""股东增减持·结构化监控 fetcher（全市场视角）

来源：东方财富数据中心 · 股东增减持（RPT_SHARE_HOLDER_INCREASE）
      https://datacenter-web.eastmoney.com/api/data/v1/get
      · 与 algorithms/fetch_dajijin_reduction.py **同源报表**，但本脚本**不加 HOLDER_NAME 过滤**，
        拉全市场增减持，按日期窗口 + 方向聚合，产出结构化监控视图。
      · 字段：NOTICE_DATE / SECURITY_CODE / SECURITY_NAME_ABBR / HOLDER_NAME / DIRECTION
        / CHANGE_NUM(万股) / HOLD_RATIO(%) / CLOSE_PRICE / REAL_PRICE / NEWEST_PRICE
        / START_DATE / END_DATE / MARKET。

与「重要公告速览」的区别（避免双源重复）：
      · 重要公告速览 = 当日巨潮**公告标题**按 股东增持/减持 标签归类（只在有正式披露那天出现）。
      · 本脚本 = 法定披露**结构化明细**（增持/减持金额、股东身份、区间、行业聚合），持续可回溯，
        且提供「按金额排序的增持榜/减持榜 + 按行业聚合的板块聚焦」，是重要公告标题之外的补充维度。

行业聚合所用 industry 映射取自 data/STOCK_LIST.js（window.STOCK_LIST.data[].industry）；
若本地无该文件则行业标「未知」，不影响其余字段。

产出：data/SHAREHOLDER_CHANGE.js → window.SHAREHOLDER_CHANGE

设计纪律（与 fetch_dajijin_reduction.py 对齐）：
  ① 原子写（tmp + os.replace）+ 写后回读逐字节校验；
  ② NOTICE_DATE 一律截断到「<= 今天」（接口会返回次日公告，未来时戳会被门禁判异常）；
  ③ CHANGE_NUM 单位=万股、金额=万股×价格(元)÷1e4 亿元；价格优先 CLOSE_PRICE → REAL_PRICE → NEWEST_PRICE；
  ④ 单页/单记录异常不静默中断——计入 summary.errors，前端可显示部分失败；
  ⑤ 无记录则不写文件（避免空壳卡静默覆盖旧数据）。

用法：
  python algorithms/fetch_shareholder_change.py            # 正常抓取并写 data/
  python algorithms/fetch_shareholder_change.py --window 120
  python algorithms/fetch_shareholder_change.py --dump     # 只打印原始记录（字段语义核对用）
  python algorithms/fetch_shareholder_change.py --limit 2000  # 限制最多拉取条数（调试用）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import ssl
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JS = os.path.join(ROOT, "data", "SHAREHOLDER_CHANGE.js")
STOCK_LIST_JS = os.path.join(ROOT, "data", "STOCK_LIST.js")

API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT = "RPT_SHARE_HOLDER_INCREASE"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

DEFAULT_WINDOW_DAYS = 120
PAGE_SIZE = 500
MAX_PAGES = 40            # 上限 ~20000 条，足够 120 日窗口聚合；防极端情况下无限翻页
TOP_N = 30               # 增持榜/减持榜各取前 N
IND_N = 12               # 行业聚合取前 N

_CORP_KEYS = ["公司", "集团", "控股", "投资", "基金", "合伙", "有限", "股份",
              "银行", "保险", "信托", "资管", "证券", "资管", "资产"]
_MGR_KEYS = ["高管", "董事", "监事", "核心人员", "员工持股", "员工持"]


def _log(msg: str) -> None:
    print("[shc] %s" % msg, flush=True)


def _ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _f(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def fetch_page(page_number: int, page_size: int = PAGE_SIZE, retries: int = 3):
    """拉取一页全市场增减持记录（无 HOLDER_NAME 过滤），返回 list[dict]。"""
    params = {
        "reportName": REPORT,
        "columns": "ALL",
        "pageNumber": str(page_number),
        "pageSize": str(page_size),
        "sortColumns": "NOTICE_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
            raw = urllib.request.urlopen(req, timeout=30, context=_ctx()).read()
            d = json.loads(raw.decode("utf-8", "ignore"))
            res = d.get("result") or {}
            return (res.get("count") or 0), (res.get("data") or [])
        except Exception as e:  # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, e)
            _log("  重试页 %d → %s" % (page_number, last))
    raise RuntimeError("拉取失败 页%d（%s）" % (page_number, last))


def _price(r):
    return _f(r.get("CLOSE_PRICE")) or _f(r.get("REAL_PRICE")) or _f(r.get("NEWEST_PRICE"))


def _classify(holder: str) -> str:
    h = holder or ""
    if any(k in h for k in _MGR_KEYS):
        return "高管"
    if any(k in h for k in _CORP_KEYS):
        return "产业资本/机构"
    return "自然人"


def _load_industry_map():
    """从 data/STOCK_LIST.js 解析 code → industry 映射。失败返回空 dict。"""
    if not os.path.exists(STOCK_LIST_JS):
        return {}
    try:
        txt = open(STOCK_LIST_JS, encoding="utf-8").read()
        i = txt.find("window.STOCK_LIST")
        if i < 0:
            return {}
        j = txt.find("{", i)
        # 找到与首个 { 匹配的 }
        depth = 0
        end = -1
        for k in range(j, len(txt)):
            if txt[k] == "{":
                depth += 1
            elif txt[k] == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        if end < 0:
            return {}
        obj = json.loads(txt[j:end + 1])
        arr = obj.get("data") if isinstance(obj, dict) else obj
        m = {}
        if isinstance(arr, list):
            for it in arr:
                if isinstance(it, dict) and it.get("code"):
                    m[str(it.get("code"))] = it.get("industry") or "未知"
        return m
    except Exception as e:  # noqa: BLE001
        _log("  ⚠ industry 映射解析失败：%s" % str(e)[:120])
        return {}


def build(window_days: int = DEFAULT_WINDOW_DAYS, today: _dt.date | None = None,
          max_records: int = PAGE_SIZE * MAX_PAGES):
    today = today or _dt.date.today()
    cutoff = today - _dt.timedelta(days=window_days)
    ind_map = _load_industry_map()
    _log("industry 映射：%d 只" % len(ind_map))

    rows = []
    errors = []
    for pg in range(1, MAX_PAGES + 1):
        try:
            cnt, data = fetch_page(pg)
        except Exception as e:  # noqa: BLE001
            errors.append("页%d: %s" % (pg, str(e)[:120]))
            break
        if not data:
            break
        stop = False
        for r in data:
            nd = str(r.get("NOTICE_DATE") or "")[:10]
            if not nd:
                continue
            try:
                d = _dt.date.fromisoformat(nd)
            except ValueError:
                continue
            if d > today:          # ② 未来时戳截断
                continue
            if d < cutoff:         # 已越过窗口，因按日期降序，后续均可停
                stop = True
                break
            shares = _f(r.get("CHANGE_NUM"), 0.0)     # 万股（绝对值）
            price = _price(r)
            amount = (abs(shares) * price / 1e4) if (price and shares) else None  # 亿元
            hname = str(r.get("HOLDER_NAME") or "")
            rec = {
                "date": nd,
                "code": str(r.get("SECURITY_CODE") or ""),
                "name": str(r.get("SECURITY_NAME_ABBR") or ""),
                "holder": hname,
                "holder_type": _classify(hname),
                "dir": "增" if "增" in str(r.get("DIRECTION") or "") else "减",
                "shares": round(shares, 3),          # 万股
                "amount": round(amount, 4) if amount is not None else None,  # 亿元
                "ratio": _f(r.get("HOLD_RATIO")),     # 变动后持股 %
                "start": str(r.get("START_DATE") or "")[:10],
                "end": str(r.get("END_DATE") or "")[:10],
                "industry": ind_map.get(str(r.get("SECURITY_CODE") or ""), "未知"),
            }
            rows.append(rec)
            if len(rows) >= max_records:
                stop = True
                break
        if stop:
            break

    rows.sort(key=lambda x: (x["date"], x["code"]), reverse=True)
    _log("窗口 %d 天 → 拉取 %d 条（行业已知 %d）" % (window_days, len(rows),
                                                    sum(1 for r in rows if r["industry"] != "未知")))

    inc = [r for r in rows if r["dir"] == "增"]
    red = [r for r in rows if r["dir"] == "减"]
    inc_amt = round(sum(r["amount"] for r in inc if r["amount"]), 2)
    red_amt = round(sum(r["amount"] for r in red if r["amount"]), 2)
    stocks_inc = len({r["code"] for r in inc})
    stocks_red = len({r["code"] for r in red})

    def _by_type(lst):
        d = {}
        for r in lst:
            d[r["holder_type"]] = d.get(r["holder_type"], 0) + 1
        return d

    # 行业聚合（按增持金额）
    ind = {}
    for r in rows:
        k = r["industry"] or "未知"
        b = ind.setdefault(k, {"inc_amt": 0.0, "inc_cnt": 0, "red_amt": 0.0, "red_cnt": 0})
        if r["dir"] == "增":
            if r["amount"] is not None:
                b["inc_amt"] += r["amount"]
            b["inc_cnt"] += 1
        else:
            if r["amount"] is not None:
                b["red_amt"] += r["amount"]
            b["red_cnt"] += 1
    ind_list = [{"industry": k, "inc_amt": round(v["inc_amt"], 2), "inc_cnt": v["inc_cnt"],
                 "red_amt": round(v["red_amt"], 2), "red_cnt": v["red_cnt"],
                 "net_amt": round(v["inc_amt"] - v["red_amt"], 2)}
                for k, v in ind.items()]
    ind_list.sort(key=lambda x: x["inc_amt"], reverse=True)
    ind_agg = ind_list[:IND_N]

    inc_top = sorted([r for r in inc if r["amount"] is not None], key=lambda x: x["amount"], reverse=True)[:TOP_N]
    red_top = sorted([r for r in red if r["amount"] is not None], key=lambda x: x["amount"], reverse=True)[:TOP_N]

    dmin = min((r["date"] for r in rows), default="")
    dmax = max((r["date"] for r in rows), default="")

    one = ("近 %d 日：增持 %d 笔（%d 只 · %.2f 亿）· 减持 %d 笔（%d 只 · %.2f 亿）；"
           "增持最集中行业「%s」（%.2f 亿 / %d 笔）。"
           % (window_days, len(inc), stocks_inc, inc_amt, len(red), stocks_red, red_amt,
              ind_agg[0]["industry"] if ind_agg else "—",
              ind_agg[0]["inc_amt"] if ind_agg else 0,
              ind_agg[0]["inc_cnt"] if ind_agg else 0))

    return {
        "update_time": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_type": "real",
        "source": "东方财富数据中心·股东增减持（RPT_SHARE_HOLDER_INCREASE）",
        "caliber": "全市场法定披露增减持明细（去除未来时戳），按金额聚合增持榜/减持榜与行业板块聚焦",
        "window_days": window_days,
        "date_min": dmin,
        "date_max": dmax,
        "summary": {
            "total": len(rows),
            "increase_cnt": len(inc),
            "reduce_cnt": len(red),
            "increase_amt": inc_amt,
            "reduce_amt": red_amt,
            "stock_cnt_inc": stocks_inc,
            "stock_cnt_red": stocks_red,
            "by_type_inc": _by_type(inc),
            "by_type_red": _by_type(red),
            "top_industry": ind_agg[0] if ind_agg else None,
            "errors": errors,
            "one_liner": one,
        },
        "increase_top": inc_top,
        "reduce_top": red_top,
        "industry_agg": ind_agg,
    }


def write_js(payload: dict) -> int:
    body = ("// 股东增减持·结构化监控 · 自动生成，勿手改\n"
            "// 生成器：algorithms/fetch_shareholder_change.py\n"
            "window.SHAREHOLDER_CHANGE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT_JS), prefix=".shc_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, OUT_JS)          # ① 原子写
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    back = open(OUT_JS, encoding="utf-8").read()
    if back != body:                      # 写后回读校验
        raise RuntimeError("回读不一致 %d != %d" % (len(back), len(body)))
    return len(body.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--limit", type=int, default=PAGE_SIZE * MAX_PAGES)
    ap.add_argument("--dump", action="store_true", help="打印原始记录明细（字段语义核对）")
    a = ap.parse_args()

    payload = build(a.window, max_records=a.limit)
    s = payload["summary"]
    _log("窗口 %d 天 → 记录 %d 条（增持 %d / 减持 %d）· 涉及增持 %d 只 / 减持 %d 只 · 增持 %.2f 亿 / 减持 %.2f 亿"
         % (payload["window_days"], s["total"], s["increase_cnt"], s["reduce_cnt"],
            s["stock_cnt_inc"], s["stock_cnt_red"], s["increase_amt"], s["reduce_amt"]))
    if s["errors"]:
        _log("⚠ 部分页失败：%s" % s["errors"])
    if payload["industry_agg"]:
        _log("增持最集中行业 Top3：%s"
             % "、".join("%s(%.2f亿/%d笔)" % (x["industry"], x["inc_amt"], x["inc_cnt"])
                          for x in payload["industry_agg"][:3]))

    if a.dump:
        for r in payload["increase_top"] + payload["reduce_top"]:
            print("  %s %-7s %-8s %-5s %-4s 万股=%-11s 金额≈%s亿 行业=%s 区间=%s~%s"
                  % (r["date"], r["code"], r["name"], r["holder_type"], r["dir"],
                     r["shares"], r["amount"], r["industry"], r["start"], r["end"]))
        return 0

    if not (payload["increase_top"] or payload["reduce_top"] or payload["industry_agg"]):
        _log("⚠ 无有效记录 —— 不写文件（避免空壳卡静默覆盖旧数据）")
        return 0

    n = write_js(payload)
    _log("✅ 写入 data/SHAREHOLDER_CHANGE.js（%d B，回读逐字节一致）" % n)
    _log("  一句话结论：%s" % s["one_liner"])
    # 输出 cache-buster 哈希供 index.html 注入使用（读取已落盘文件计算，避免局部变量作用域问题）
    h = hashlib.md5(open(OUT_JS, "rb").read()).hexdigest()[:10]
    print("CACHE_V=%s" % h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
