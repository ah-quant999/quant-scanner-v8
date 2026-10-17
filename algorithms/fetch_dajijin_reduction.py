# -*- coding: utf-8 -*-
"""国家大基金（国家集成电路产业投资基金）增减持监控 · 数据抓取器

来源：东方财富数据中心 · 股东增减持（RPT_SHARE_HOLDER_INCREASE）
      https://datacenter-web.eastmoney.com/api/data/v1/get
      · 该表按**股东名称**精确可查（filter=(HOLDER_NAME="...")），字段含
        变动方向 / 变动股数 / 变动后持股比例 / 公告日，属**结构化法定披露**口径。
      · 与「国家大基金持股」概念板块（BK 板块，按季报十大股东打标）是两回事：
        本脚本监控的是**大基金自身的买卖动作**，不是市场资金对该板块的流入。

产出：data/DAJIJIN_REDUCTION.js → window.DAJIJIN_REDUCTION

设计纪律（血训对齐）：
  ① 原子写（tmp + os.replace）+ 写后回读逐字节校验 —— 防 2026-09-22 index.html 非原子写截断类事故；
  ② NOTICE_DATE 一律截断到「<= 今天」—— 该接口会返回次日公告，未来时戳会被 v8 门禁判为异常；
  ③ 单字段语义实测：CHANGE_NUM 单位=万股、HOLD_RATIO 单位=%、金额=万股×均价(元)÷1e4 亿元；
  ④ 任一主体查询失败不静默 —— 记录到 summary.errors，前端可显示部分失败。

用法：
  python algorithms/fetch_dajijin_reduction.py            # 正常抓取并写 data/
  python algorithms/fetch_dajijin_reduction.py --dump     # 只打印原始记录（字段语义核对用）
  python algorithms/fetch_dajijin_reduction.py --window 180
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
OUT_JS = os.path.join(ROOT, "data", "DAJIJIN_REDUCTION.js")

API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT = "RPT_SHARE_HOLDER_INCREASE"

# 三个基金主体（名字必须与披露口径逐字一致，精确匹配；模糊 like 在本接口不生效）
HOLDERS = [
    ("国家集成电路产业投资基金股份有限公司", "一期"),
    ("国家集成电路产业投资基金二期股份有限公司", "二期"),
    ("国家集成电路产业投资基金三期股份有限公司", "三期"),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

DEFAULT_WINDOW_DAYS = 120


def _log(msg: str) -> None:
    print("[dajijin] %s" % msg, flush=True)


def _ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


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
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
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


def build(window_days: int = DEFAULT_WINDOW_DAYS, today: _dt.date | None = None):
    today = today or _dt.date.today()
    cutoff = today - _dt.timedelta(days=window_days)
    records, errors, raw_counts = [], [], {}

    for full_name, alias in HOLDERS:
        try:
            cnt, rows = fetch_holder(full_name)
            raw_counts[alias] = cnt
            _log("%s %s → count=%s 取回=%d" % (alias, full_name[:16], cnt, len(rows)))
        except Exception as e:  # noqa: BLE001
            errors.append({"holder": alias, "error": str(e)[:200]})
            _log("  ⚠ %s 查询失败：%s" % (alias, str(e)[:120]))
            continue

        for r in rows:
            nd = str(r.get("NOTICE_DATE") or "")[:10]
            if not nd:
                continue
            try:
                d = _dt.date.fromisoformat(nd)
            except ValueError:
                continue
            # ② 未来时戳截断：该接口会返回次日公告，必须剔除
            if d > today:
                continue
            if d < cutoff:
                continue
            shares = _f(r.get("CHANGE_NUM"), 0.0)          # 单位：万股（实测：盛科通信 3 笔持股比例 11/10/9.87% 与披露逐位一致）
            close = _f(r.get("CLOSE_PRICE"))               # 公告日收盘价（TRADE_AVERAGE_PRICE 实测恒为 None）
            amount = (shares * close / 1e4) if (close and shares) else None  # 亿元·估算
            records.append({
                "date": nd,
                "code": str(r.get("SECURITY_CODE") or ""),
                "name": str(r.get("SECURITY_NAME_ABBR") or ""),
                "via": str(r.get("MARKET") or ""),          # 减持方式（二级市场/大宗交易…）
                "holder": alias,
                "dir": str(r.get("DIRECTION") or ""),
                "shares": round(shares, 4),                 # 本次变动，万股
                "after_num": _f(r.get("AFTER_HOLDER_NUM")), # 变动后持股数，万股
                "hold_ratio": _f(r.get("HOLD_RATIO")),      # 变动后持股比例 %
                "start": str(r.get("START_DATE") or "")[:10],
                "end": str(r.get("END_DATE") or "")[:10],
                "close": round(close, 3) if close else None,
                "amount_est": round(amount, 4) if amount else None,  # 亿元·估算(万股×收盘价)
                "notice": nd,
            })

    records.sort(key=lambda x: (x["date"], x["code"]), reverse=True)

    reduce_recs = [r for r in records if "减" in r["dir"]]
    raise_recs = [r for r in records if "增" in r["dir"]]
    codes = sorted({r["code"] for r in records})
    reduce_shares = round(sum(r["shares"] for r in reduce_recs), 2)
    raise_shares = round(sum(r["shares"] for r in raise_recs), 2)
    by_holder = {}
    for r in records:
        by_holder.setdefault(r["holder"], {"n": 0, "codes": set(), "shares": 0.0})
        b = by_holder[r["holder"]]
        b["n"] += 1
        b["codes"].add(r["code"])
        b["shares"] += r["shares"]
    for k, v in by_holder.items():
        v["codes"] = len(v["codes"])
        v["shares"] = round(v["shares"], 2)

    if not records:
        one = "近 %d 日无大基金增减持记录（一期/二期/三期均无披露）。" % window_days
    else:
        brk = []
        for k in ("一期", "二期", "三期"):
            if k in by_holder:
                brk.append("%s %d 笔" % (k, by_holder[k]["n"]))
        one = "近 %d 日：大基金合计减持 %d 笔 · %d 只 · %s 万股（%s），增持 %d 笔。" % (
            window_days, len(reduce_recs), len({r["code"] for r in reduce_recs}),
            format(reduce_shares, ",.2f"), "、".join(brk), len(raise_recs))
        if reduce_recs and not raise_recs:
            one += " 全程只减不增 —— 一期已进入回收/延展期，减持属常态，是利空前瞻信号而非入场信号。"

    return {
        "update_time": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_type": "real",
        "source": "东方财富数据中心·股东增减持（RPT_SHARE_HOLDER_INCREASE）",
        "caliber": "按股东名称精确匹配「国家集成电路产业投资基金（一期/二期/三期）」法定义务披露的增减持记录",
        "window_days": window_days,
        "summary": {
            "total": len(records),
            "reduce_cnt": len(reduce_recs),
            "increase_cnt": len(raise_recs),
            "reduce_shares": reduce_shares,
            "increase_shares": raise_shares,
            "stock_cnt": len(codes),
            "by_holder": by_holder,
            "raw_counts": raw_counts,
            "errors": errors,
            "one_liner": one,
        },
        "records": records,
    }


def write_js(payload: dict) -> int:
    """原子写 + 回读逐字节校验。"""
    body = ("// 大基金（国家集成电路产业投资基金）增减持监控 · 自动生成，勿手改\n"
            "// 生成器：algorithms/fetch_dajijin_reduction.py\n"
            "window.DAJIJIN_REDUCTION = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT_JS), prefix=".djj_", suffix=".tmp")
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
    ap.add_argument("--dump", action="store_true", help="打印原始记录明细（字段语义核对）")
    a = ap.parse_args()

    payload = build(a.window)
    s = payload["summary"]
    _log("窗口 %d 天 → 记录 %d 条（减持 %d / 增持 %d）· 涉及 %d 只 · 减持 %.2f 万股"
         % (payload["window_days"], s["total"], s["reduce_cnt"], s["increase_cnt"], s["stock_cnt"], s["reduce_shares"]))
    if s["errors"]:
        _log("⚠ 部分主体失败：%s" % s["errors"])

    if a.dump:
        for r in payload["records"]:
            print("  %s %-7s %-8s %-4s %-3s 变动=%-11s万股 变动后=%-11s万股 持股=%-7s%% 区间=%s~%s 收盘=%-8s 金额≈%s亿"
                  % (r["date"], r["code"], r["name"], r["holder"], r["dir"],
                     r["shares"], r["after_num"], r["hold_ratio"], r["start"], r["end"], r["close"], r["amount_est"]))
        return 0

    if not payload["records"]:
        _log("⚠ 记录为空 —— 不写文件（避免产出空壳卡静默覆盖旧数据）")
        return 0

    n = write_js(payload)
    _log("✅ 写入 data/DAJIJIN_REDUCTION.js（%d B，回读逐字节一致）" % n)
    _log("  一句话结论：%s" % s["one_liner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
