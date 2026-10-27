# -*- coding: utf-8 -*-
"""中央汇金持仓披露抓取器 · 产出 data/HUIJIN_HOLDINGS.js (window.HUIJIN_HOLDINGS)

来源：东方财富数据中心 · 股东增减持（RPT_SHARE_HOLDER_INCREASE）
      · 按股东名称精确匹配 HOLDER_NAME="中央汇金投资有限责任公司"（披露口径逐字一致）。
      · 与「国家大基金」fetch_dajijin_reduction.py 同源同表，仅换主体名。

口径说明（绝不编造·如实标注）：
  · 该表记录「中央汇金」自身法定义务披露的股票增减持 = 其股票持仓变动；
    汇金借道 ETF 的托盘（沪深300/中证500/科创50 等）不在此表，已由国家队活跃度胶囊A覆盖。
  · 按披露日(NOTICE_DATE)归集到季度，季度净变动 = Σ(增持+ / 减持-)（单位 万股 → 亿股）；
    最新披露季 vs 上一有数据季 = 环比（披露口径，数据稀疏且滞后，最新约 2024Q2）。
  · 全量滞后属结构性（汇金只在季报/临时公告披露），卡面与生成器均明确标注「披露口径·滞后」。

产出 window.HUIJIN_HOLDINGS = {
  latest_quarter, latest_net_yi, prev_quarter, prev_net_yi, qoq_yi, qoq_pct,
  total_net_yi, record_count, holdings_sample, one_liner, ...
}

设计纪律（对齐 fetch_dajijin_reduction.py）：
  ① 原子写（tmp + os.replace）+ 写后回读逐字节校验；
  ② NOTICE_DATE 一律截断到「<= 今天」（接口偶发返回次日公告）；
  ③ 单字段语义：CHANGE_NUM 单位=万股、DIRECTION=增/减、AFTER_HOLDER_NUM=变动后持股(万股)。

用法：
  python v8/fetch_huijin_holdings.py            # 正常抓取并写 data/
  python v8/fetch_huijin_holdings.py --dump     # 只打印原始记录（字段核对）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import ssl
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JS = os.path.join(ROOT, "data", "HUIJIN_HOLDINGS.js")

API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT = "RPT_SHARE_HOLDER_INCREASE"
HOLDER = "中央汇金投资有限责任公司"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def _ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _log(msg: str) -> None:
    print("[huijin] %s" % msg, flush=True)


def fetch_holder(holder_name: str, page_size: int = 500, retries: int = 3):
    """按股东全名精确拉取增减持记录，返回 (count, records)。"""
    params = {
        "reportName": REPORT,
        "columns": "ALL",
        "filter": '(HOLDER_NAME="%s")' % holder_name,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": "NOTICE_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
            raw = urllib.request.urlopen(req, timeout=30, context=_ctx()).read()
            d = json.loads(raw.decode("utf-8", "ignore"))
            res = d.get("result") or {}
            return res.get("count"), (res.get("data") or [])
        except Exception as e:  # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, e)
            _log("  重试 %d/%d %s → %s" % (i + 1, retries, holder_name[:12], last))
    raise RuntimeError("拉取失败 %s（%s）" % (holder_name, last))


def _f(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _quarter(dt: _dt.date) -> str:
    return "%dQ%d" % (dt.year, (dt.month - 1) // 3 + 1)


def build(today: _dt.date | None = None):
    today = today or _dt.date.today()
    try:
        cnt, rows = fetch_holder(HOLDER)
        _log("%s → count=%s 取回=%d" % (HOLDER, cnt, len(rows)))
    except Exception as e:  # noqa: BLE001
        _log("⚠ 查询失败：%s" % str(e)[:160])
        return {"data_type": "error", "source": "东方财富数据中心·股东增减持(RPT_SHARE_HOLDER_INCREASE)",
                "caliber": "按股东名称精确匹配「%s」" % HOLDER, "holder": HOLDER,
                "error": str(e)[:200], "update_time": _dt.datetime.now().strftime("%Y-%m-%d %H:%M")}

    from collections import defaultdict
    net_by_q = defaultdict(float)
    cnt_by_q = defaultdict(int)
    sample = []          # 最新披露季样本
    latest_q = None
    for r in rows:
        nd = str(r.get("NOTICE_DATE") or "")[:10]
        if not nd:
            continue
        try:
            d = _dt.date.fromisoformat(nd)
        except ValueError:
            continue
        if d > today:
            continue
        q = _quarter(d)
        ch = _f(r.get("CHANGE_NUM"), 0.0)            # 万股
        dn = str(r.get("DIRECTION") or "")
        s = 1.0 if "增" in dn else (-1.0 if "减" in dn else 0.0)
        net_by_q[q] += ch * s
        cnt_by_q[q] += 1
        if latest_q is None or q > latest_q:
            latest_q = q

    qs = sorted(net_by_q.keys())
    latest_net = net_by_q[latest_q] / 1e4 if latest_q else None   # 亿股
    prev_q = qs[-2] if len(qs) >= 2 else None
    prev_net = (net_by_q[prev_q] / 1e4) if prev_q else None
    if latest_net is not None and prev_net is not None:
        qoq_yi = latest_net - prev_net
        qoq_pct = (qoq_yi / prev_net * 100.0) if prev_net else None
    else:
        qoq_yi, qoq_pct = None, None
    total_net = (sum(net_by_q.values()) / 1e4) if net_by_q else None   # 累计净变动(披露口径)

    # 最新披露季样本（取该季净变动最大的几只）
    if latest_q:
        qrows = [r for r in rows
                 if r.get("NOTICE_DATE") and _quarter(_dt.date.fromisoformat(str(r["NOTICE_DATE"])[:10])) == latest_q]
        for r in qrows[:6]:
            dn = str(r.get("DIRECTION") or "")
            s = 1.0 if "增" in dn else (-1.0 if "减" in dn else 0.0)
            sample.append({
                "date": str(r.get("NOTICE_DATE") or "")[:10],
                "name": str(r.get("SECURITY_NAME_ABBR") or ""),
                "dir": dn,
                "change_yi": round(_f(r.get("CHANGE_NUM"), 0.0) * s / 1e4, 3),
                "after_ratio": _f(r.get("HOLD_RATIO")),
            })

    if latest_net is None:
        one = "近披露记录为空，无法计算汇金持仓环比。"
    else:
        direction = "净增持" if latest_net >= 0 else "净减持"
        tail = ""
        if qoq_yi is not None:
            tail = "，环比上季(%s) %s%.2f 亿股%s" % (
                prev_q, "+" if qoq_yi >= 0 else "",
                qoq_yi, ("（%+0.0f%%）" % qoq_pct) if qoq_pct is not None else "")
        one = "汇金股票披露%s %.2f 亿股（%s）%s · 披露口径·滞后" % (
            direction, abs(latest_net), latest_q, tail)

    return {
        "update_time": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_type": "real",
        "source": "东方财富数据中心·股东增减持(RPT_SHARE_HOLDER_INCREASE)",
        "caliber": "按股东名称精确匹配「%s」法定义务披露的增减持记录（股票持仓变动；ETF渠道不在此表，见胶囊A）" % HOLDER,
        "holder": HOLDER,
        "record_count": len(rows),
        "latest_quarter": latest_q,
        "latest_net_yi": (round(latest_net, 3) if latest_net is not None else None),
        "prev_quarter": prev_q,
        "prev_net_yi": (round(prev_net, 3) if prev_net is not None else None),
        "qoq_yi": (round(qoq_yi, 3) if qoq_yi is not None else None),
        "qoq_pct": (round(qoq_pct, 1) if qoq_pct is not None else None),
        "total_net_yi": (round(total_net, 3) if total_net is not None else None),
        "holdings_sample": sample,
        "one_liner": one,
    }


def write_js(payload: dict) -> int:
    body = ("// 中央汇金持仓披露 · 自动生成，勿手改\n"
            "// 生成器：v8/fetch_huijin_holdings.py\n"
            "window.HUIJIN_HOLDINGS = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT_JS), prefix=".hj_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, OUT_JS)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    back = open(OUT_JS, encoding="utf-8").read()
    if back != body:
        raise RuntimeError("回读不一致 %d != %d" % (len(back), len(body)))
    return len(body.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="打印原始记录明细")
    a = ap.parse_args()
    payload = build()
    if a.dump:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    if payload.get("data_type") == "error" or payload.get("latest_net_yi") is None:
        _log("⚠ 无有效数据 —— 不写文件（避免空壳覆盖旧数据）")
        return 0
    n = write_js(payload)
    _log("✅ 写入 data/HUIJIN_HOLDINGS.js（%d B，回读逐字节一致）" % n)
    _log("  一句话：%s" % payload["one_liner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
