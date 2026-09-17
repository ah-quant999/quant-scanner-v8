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

STATUS_SET = {"强势", "正常", "回落", "见顶", "走弱", "连涨强势"}
# 🔴 2026-09-17 阿狸咪的工程师（主人令「算法不得出错」专项）：补 "连涨强势"。
#   实证判据（不是推测）：线上产物 data/IMA_STRONG_STOCK.js（09-16 15:53，旧解析器产出）
#   的 `buy_point` 字段取值分布里出现 `'连涨强势'` **4 次** —— 该字段因串位吃到了
#   status 位的值，而 "连涨强势" 当时**不在**本集合 ⇒ 被原逻辑判为「类型不符」
#   ⇒ 那 4 行的 status 被清空、且指针继续前移污染后续字段。
#   ⚠️ 曾疑需补 "跟踪"：已证伪 —— 汇总行「跟踪 112 只」的 112 = 全表行数（汇总标签），
#      且 112 条记录**任何字段**都不含「跟踪」二字（已全字段扫描）。故不补。
#   设计上仍保留 `_take_field` 的类型校验（不匹配**不消费**）⇒ 日后若 ima 再添新状态词，
#      最坏结果只是该字段显式留空 + `_parse_missing` 留痕，**绝不会再串位**。

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 🔴 2026-09-17：「状态格形状」判据 —— 见 _take_field 的 status 分支说明。
#   只接受 2~8 个纯中文/字母字符（如 连涨强势 / 跟踪 / 走弱），
#   任何含数字、括号、% 、小数点的值（日期、价格、买点提示「回调买点(回撤9.3%)」）都不算状态。
_STATUS_SHAPE = re.compile(r"^[\u4e00-\u9fa5A-Za-z]{2,8}$")


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


def _take_field(lines, j, n, kind):
    """按类型取第 j 项，返回 (值, 是否消费指针)。

    kind: 'date' | 'float' | 'int' | 'status' | 'text'

    规则（这是阻断「字段串位」的核心）：
      · 行尾越界         ⇒ (None, False)  —— 不消费
      · 空串（空单元格） ⇒ (空默认值, True) —— **消费**：HTML 空单元格在 innerText 里
                           就是空行，属「字段存在但为空」，必须照常推进指针
      · 非空且类型匹配   ⇒ (解析值, True)
      · 非空但类型不符   ⇒ (空默认值, False) —— **不消费**：这是串位信号，
                           宁可把该字段显式留空并留痕，也不让指针偏移一格污染后续全部字段
      ⚠️ 例外：kind='status' 走**形状判据**（见该分支注释）—— 因为 buy_point 是 text 类型、
         无条件接受任何值，「不消费」会立刻被它吃掉而变成另一种串位。
    """
    v = lines[j] if j < n else None
    if v is None:
        return None, False
    if v == "":
        return ("" if kind in ("date", "status", "text") else None), True
    if kind == "date":
        return (v, True) if is_date(v) else ("", False)
    if kind == "float":
        f = to_float(v)
        return (f, True) if f is not None else (None, False)
    if kind == "int":
        t = to_int(v)
        return (t, True) if t is not None else (None, False)
    if kind == "status":
        # 🔴 2026-09-17 二次修正（自证用例 5 暴露的**第一版漏洞**）：
        #   第一版「不在白名单 ⇒ 不消费」在 text 字段面前失效 —— 因为 buy_point 是
        #   `text` 类型、**无条件接受任何值**，于是 status 格里的未知词会被 buy_point
        #   原样吃掉，再让 trade_date 顺移 ⇒ 表面「没串位」实则**换了个字段串位**。
        #   实证（自造用例 5，输入 status="超级无敌强势"）：第一版得
        #   buy_point='超级无敌强势'、trade_date='' ❌。
        #
        #   正解依据**列序固定**这一事实：那一格就是 status 格。故
        #     ① 空串      ⇒ 走上面的空分支，消费为空（安全）；
        #     ② 白名单命中 ⇒ 消费为状态；
        #     ③ 形状像状态（2~8 个纯中文/字母）⇒ **仍消费**，保留原值（上层标 status_unknown）；
        #     ④ 含数字/括号/百分号等（日期、价格、「回调买点(回撤9.3%)」）⇒ 才判定为
        #        「该行真的少一格」，不消费并留痕。
        if v in STATUS_SET:
            return (v, True)
        if _STATUS_SHAPE.match(v):
            return (v, True)
        return ("", False)
    if kind == "text":
        return (v, True)
    return (None, False)


def extract_from_inner_text(text):
    """按字段类型解析 innerText，容忍行业/买点提示为空。

    🔴 2026-09-17 阿狸咪的工程师 修复（主人令「回测也必须真实」专项审计）：

    **原实现的缺陷（实证，非推测）**：每个字段都用 `lines[j]` 硬取后**无条件** `j += 1`，
    完全没有类型校验 ⇒ 一旦某字段缺失，指针就会**吃掉下一个字段并整体串位一格**。
    旁证特征：某字段里出现**别的字段的取值** —— 实测 112 只样本中，那 72 只
    「首次入选日为空」的记录里 `buy_point` 存的是 `status` 的词、`consecutive_up`
    中位异常为 10，正是整体串位一格的指纹。

    **后果（为什么当事故修）**：下游回测以 `first_selected` 为信号日，
    空值者被 `one_trade()` 的 `if sig_date not in ds: return None` **静默丢弃**
    （实测 `skipped_no_signal_date = 72`），而**被丢弃那批真实涨幅显著更低**
    （区间涨幅中位 +20.24% vs 保留下来的 +56.58%）⇒ 回测结果系统性偏乐观。

    **修法（一劳永逸，两条）**：
      ① 类型校验 + 不匹配不消费 ⇒ 串位被物理阻断（规则见 `_take_field`），
         缺口显式留下，不去污染邻居字段；
      ② 逐条留痕 ⇒ 每条记录带 `_parse_missing`（哪些字段空/类型不符），上层落盘统计。
         **绝不静默丢弃** —— 要让「缺多少、缺在哪」一眼可见。
    """
    # 🔴 2026-09-17：清掉 BOM / 零宽字符。实测真实页面抓下来的 innerText 里
    #   有 25 个字段值是 '\ufeff'（BOM），会被当成「有内容但类型不符」⇒ 误判为串位。
    #   这是数据清洗，不是格式猜测 —— 只剔零宽不可见字符，不改任何可见内容。
    lines = [l.replace("\ufeff", "").replace("\u200b", "").replace("\u200e", "").strip()
             for l in text.split("\n")]
    stocks = []
    i, n = 0, len(lines)
    while i < n:
        if not re.match(r"^\d{6}$", lines[i]):
            i += 1
            continue
        rec = {"code": lines[i]}
        miss = []
        j = i + 1

        def take(field, kind, default):
            nonlocal j
            val, used = _take_field(lines, j, n, kind)
            if used:
                j += 1
            else:
                miss.append(field)
            rec[field] = default if val is None else val

        # 固定列序（与 extract_via_table 的 HTML 列序一致）——**不再用「类型猜测」判行业**：
        # 猜测本身在字段为空时就会误判，正是串位的源头之一。
        take("name",           "text",   "")
        take("industry",       "text",   "")
        take("first_selected", "date",   "")
        take("base_price",     "float",  None)
        take("latest_price",   "float",  None)
        take("change_pct",     "float",  None)
        take("drawdown_pct",   "float",  None)
        take("consecutive_up", "int",    None)
        take("status",         "status", "")
        take("buy_point",      "text",   "")
        take("trade_date",     "date",   "")
        # 🔴 2026-09-17：状态词**尚未登记**进 STATUS_SET 时，保留原值并显式打标
        #   `status_unknown: true`，而**不是静默清空** —— 让 ima 新添的状态词
        #   在产物里自己显形（这是「绝不静默丢弃」原则的落地方式）。
        #   下次抓取后只要 grep `status_unknown` 就能发现该补白名单了。
        if rec["status"] and rec["status"] not in STATUS_SET:
            rec["status_unknown"] = True
        if miss:
            rec["_parse_missing"] = miss
        stocks.append(rec)
        i = j
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

    # 🔴 2026-09-17 阿狸咪的工程师：解析健康度落盘（**绝不静默丢弃**）。
    #   动因：实测 112 只里 72 只「首次入选日为空」被下游回测静默跳过，
    #   而主人完全无从得知「丢了多少、丢在哪、是不是解析坏了」——正是这种不可见
    #   让「回测吃到偏乐观样本」潜伏了不知多久。故把缺口统计**写进产物本身**，
    #   让任何一方（前端/审计/另一台机）都能一眼看见。
    _missing_fields = {}
    _no_sig_date = 0
    for _s in data["stocks"]:
        for _f in (_s.get("_parse_missing") or []):
            _missing_fields[_f] = _missing_fields.get(_f, 0) + 1
        if not str(_s.get("first_selected") or "").strip():
            _no_sig_date += 1
    parse_health = {
        "total": len(data["stocks"]),
        "no_first_selected": _no_sig_date,
        "no_first_selected_pct": (round(_no_sig_date / len(data["stocks"]) * 100, 1)
                                  if data["stocks"] else 0),
        "field_missing_counts": _missing_fields,
        "note": ("no_first_selected = 无首次入选日的记录数；下游回测无法为其定位信号日 ⇒ "
                 "会被排除。此数必须与回测侧 skipped_no_signal_date 对得上，否则说明"
                 "解析或筛选有分歧。field_missing_counts = 各字段类型校验未通过（串位）次数，"
                 "恒为 0 表示行结构与 HTML 列序完全对齐。"),
    }

    out = {
        # 🛡 2026-09-04：固定北京时间——云端 runner 是 UTC，旧写法 now() 让卡片把 20:17 显示成 12:17
        "update_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ima",
        "note_url": args.url,
        "summary": data["summary"],
        "parse_health": parse_health,
        "stocks": data["stocks"],
    }
    print(f"🩺 解析健康度: 总 {parse_health['total']} 只 · "
          f"无首次入选日 {parse_health['no_first_selected']} 只"
          f"（{parse_health['no_first_selected_pct']}%）· "
          f"字段串位 {sum(_missing_fields.values())} 次 {_missing_fields or ''}")

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
