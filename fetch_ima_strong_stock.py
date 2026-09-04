#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ima_strong_stock.py — 抓取 ima「强势股跟踪日报」并接入 v8 管线。

背景：ima 分享页是 React SPA，服务端不渲染数据（裸 HTTP GET 只拿到外壳 HTML），
      必须用无头浏览器执行 JS 才能拿到表格。本脚本用 playwright(chromium) 渲染后提取。

产物：
  raw_data/ima_strong_stock.json   —— 中间数据（供 update_v8.py 转 data/*.js）
  data/IMA_STRONG_STOCK.js         —— window.IMA_STRONG_STOCK = {...}（前端直接读）

用法：
  python fetch_ima_strong_stock.py            # 默认抓默认笔记
  python fetch_ima_strong_stock.py --url XXX  # 指定分享链接
  python fetch_ima_strong_stock.py --inspect # 仅导出渲染 HTML 供调试，不写文件
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")

DEFAULT_URL = "https://ima.qq.com/note/share/_A0YNbqJ8AmbI5kRZ1ZmMQ?channel=5"

STATUS_SET = {"强势", "正常", "回落", "见顶", "走弱"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_date(s):
    return bool(s) and DATE_RE.match(s or "")


def to_float(s):
    try:
        return float(str(s).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def to_int(s):
    try:
        return int(float(to_float(s)))
    except Exception:
        return 0


def extract_from_inner_text(text):
    """按字段类型解析 innerText，容忍行业/买点提示为空。"""
    lines = [l.strip() for l in text.split("\n")]
    stocks = []
    i = 0
    n = len(lines)
    while i < n:
        if re.match(r"^\d{6}$", lines[i]):
            rec = {"code": lines[i]}
            j = i + 1
            # 名称
            rec["name"] = lines[j] if j < n else ""
            j += 1
            # 行业（可能为空）：若下一项不是日期/数字/状态，则是行业
            nxt = lines[j] if j < n else ""
            if nxt and not is_date(nxt) and to_float(nxt) is None and nxt not in STATUS_SET:
                rec["industry"] = nxt
                j += 1
            else:
                rec["industry"] = ""
            # 首次入选日期
            rec["first_selected"] = lines[j] if (j < n and is_date(lines[j])) else ""
            j += 1
            rec["base_price"] = to_float(lines[j]); j += 1
            rec["latest_price"] = to_float(lines[j]); j += 1
            rec["change_pct"] = to_float(lines[j]); j += 1
            rec["drawdown_pct"] = to_float(lines[j]); j += 1
            rec["consecutive_up"] = to_int(lines[j]); j += 1
            rec["status"] = lines[j] if (j < n and lines[j] in STATUS_SET) else ""
            j += 1
            # 买点提示（可能为空）：若下一项不是日期
            nxt = lines[j] if j < n else ""
            if nxt and not is_date(nxt):
                rec["buy_point"] = nxt
                j += 1
            else:
                rec["buy_point"] = ""
            rec["trade_date"] = lines[j] if (j < n and is_date(lines[j])) else ""
            j += 1
            stocks.append(rec)
            i = j
        else:
            i += 1
    return stocks


def parse_summary(text):
    """解析顶部汇总：跟踪 112 只 | 强势 23 | 买点候选 36 | 见顶 12 | 走弱 0；已剔除 27 只。"""
    summary = {}
    m = re.search(r"跟踪\s*(\d+)\s*只", text)
    if m:
        summary["track"] = int(m.group(1))
    for key, pat in [
        ("strong", r"强势\s*(\d+)"),
        ("buy_point", r"买点候选\s*(\d+)"),
        ("top", r"见顶\s*(\d+)"),
        ("weak", r"走弱\s*(\d+)"),
        ("removed", r"已剔除\s*(\d+)"),
    ]:
        mm = re.search(pat, text)
        if mm:
            summary[key] = int(mm.group(1))
    return summary


def extract_via_table(page):
    """兜底：尝试用 DOM 表格解析。"""
    try:
        rows = page.query_selector_all("table tr")
        stocks = []
        for row in rows:
            cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
            if len(cells) >= 10 and re.match(r"^\d{6}$", cells[0]):
                stocks.append({
                    "code": cells[0], "name": cells[1],
                    "industry": cells[2] if len(cells) > 2 else "",
                    "first_selected": cells[3] if len(cells) > 3 else "",
                    "base_price": to_float(cells[4]) if len(cells) > 4 else None,
                    "latest_price": to_float(cells[5]) if len(cells) > 5 else None,
                    "change_pct": to_float(cells[6]) if len(cells) > 6 else None,
                    "drawdown_pct": to_float(cells[7]) if len(cells) > 7 else None,
                    "consecutive_up": to_int(cells[8]) if len(cells) > 8 else 0,
                    "status": cells[9] if len(cells) > 9 else "",
                    "buy_point": cells[10] if len(cells) > 10 else "",
                    "trade_date": cells[11] if len(cells) > 11 else "",
                })
        return stocks
    except Exception:
        return []


def fetch(url, inspect=False):
    from playwright.sync_api import sync_playwright

    print(f"🌐 打开 {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        # 等待内容渲染（出现 6 位代码 或 超时）
        try:
            page.wait_for_selector("text=/\\d{6}/", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        inner = page.inner_text("body")
        if inspect:
            os.makedirs(RAW_DIR, exist_ok=True)
            with open(os.path.join(RAW_DIR, "_ima_page_dump.txt"), "w", encoding="utf-8") as f:
                f.write(inner)
            print("💾 已导出渲染文本 -> raw_data/_ima_page_dump.txt")
            browser.close()
            return None
        stocks = extract_from_inner_text(inner)
        if not stocks:
            print("⚠️ innerText 解析为 0，尝试表格解析")
            stocks = extract_via_table(page)
        summary = parse_summary(inner)
        browser.close()

    print(f"✅ 解析到 {len(stocks)} 只股票；汇总: {summary}")
    return {"summary": summary, "stocks": stocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    data = fetch(args.url, inspect=args.inspect)
    if data is None:
        return

    out = {
        # 🛡 2026-09-04：固定北京时间——云端 runner 是 UTC，旧写法 now() 让卡片把 20:17 显示成 12:17
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ima",
        "note_url": args.url,
        "summary": data["summary"],
        "stocks": data["stocks"],
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    raw_path = os.path.join(RAW_DIR, "ima_strong_stock.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 写入 {raw_path}")

    js_path = os.path.join(DATA_DIR, "IMA_STRONG_STOCK.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.IMA_STRONG_STOCK = ")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"✅ 写入 {js_path}")


if __name__ == "__main__":
    main()
