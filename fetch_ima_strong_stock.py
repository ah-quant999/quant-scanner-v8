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

    kind: 'date' | 'float' | 'int' | 'status' | 'text' | 'buy_point'

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
    if kind == "buy_point":
        # 🔴 2026-09-17 阿狸咪的工程师 追加（与小九 2115 件 §3 建议同源，我方落地）：
        #   买点提示格**不可能**是纯 `YYYY-MM-DD`。出现日期形状只有一种成因 ——
        #   该行 status 格缺失时，落在那格的值形状不像状态 ⇒ 上面 status 分支判
        #   「不消费」并留痕；紧接着**无条件接受任何值**的 text 型 buy_point 把它
        #   原样吃掉，再让 trade_date 顺移一格 ⇒ 表面「status 已留痕」，实则
        #   **换了个字段继续串位**。这与 status 分支踩的是同一个坑：text 型无条件
        #   接受 = 串位放大器。故按同一思路收口 —— **只认形状、不认内容**：
        #   日期形状 ⇒ 不消费，缺口由 `_parse_missing` 显式留痕（绝不静默）。
        if DATE_RE.match(v):
            return ("", False)
        return (v, True)
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
    # 🔴🔴 2026-09-18 阿狸咪的工程师 根治（主人令「回测必须真实、不得造假」专项）：
    #   **innerText 里「空单元格」占 2 行**（'\ufeff' + 紧随的空串），非空单元格只占 1 行。
    #   上一版把 BOM **无条件 replace 掉** ⇒ 空单元格被拆成 2 个空 token，与「2 个真空行」
    #   再也无法区分；而解析按「1 字段 1 token」推进 ⇒ 每遇一个空「行业」格后续整体左移，
    #   加上类型校验让指针**卡住不消费** ⇒ base_price..trade_date 六字段全塌进 _parse_missing。
    #
    #   实证（真实页面 dump，1521 行 / 112 只，可复现；见 docs/ops/audit/ 同名报告）：
    #     修复前 field_missing_counts = {base_price:72, latest_price:72, change_pct:72,
    #       drawdown_pct:72, status:70, trade_date:70}，有效 first_selected 仅 **40/112**
    #       —— 与线上产物 `parse_health` **逐项完全一致**（⇒ 根因确认，非推测）；
    #     修复后 first_selected **112/112**，缺失归 0（仅剩 2 条真实无价的记录）。
    #   下游后果（为什么当事故修）：first_selected 为空者被回测 `one_trade()` 静默丢弃
    #   （skipped=72），样本从 112 掉到 40 会让回测**系统性偏乐观**
    #   （T+1 40 条 67.5% vs 全量 176 条 50.6%，差 17pp）。
    #
    #   正解：**折叠**（不是 strip、不是 replace）—— 把 '\ufeff'+紧随空串并成 **1 个空 token**，
    #   使「空单元格」与「非空格」在 token 级同构（都是 1 个）。
    raw_lines = text.split("\n")
    lines = []
    _k = 0
    while _k < len(raw_lines):
        if (raw_lines[_k] == "\ufeff"
                and _k + 1 < len(raw_lines) and not raw_lines[_k + 1].strip()):
            lines.append("")          # 空单元格 = BOM 行 + 空行 → 1 个 token
            _k += 2
            continue
        lines.append(raw_lines[_k].replace("\ufeff", "").replace("\u200b", "")
                     .replace("\u200e", "").strip())
        _k += 1
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
        take("buy_point",      "buy_point", "")
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


def parse_note_meta(text):
    """🔴 2026-09-17 阿狸咪的工程师 新增：提取**源笔记自述的元数据**。

    动因（实测，非推测）：本卡 2026-09-17 被主人质疑「都没变化啊」。
    取证结果——源分享页 `document.title` = 「强势股跟踪日报 2026-09-02」，
    页内自述「更新时间：2026.09.02 15:41」，**每行「最新交易日」全为 2026-09-02**；
    而本脚本自 09-03 起每天忠实抓取这份**静止**的笔记，产物价格字段指纹
    （`207238cb37e4`）连续 20 次抓取一字未改 ⇒ 前端却因 `update_time` 用的是
    **抓取时刻** 而显示「更新于 今日 15:53 盘后」= **假新鲜**。

    故把源自身的日期落进产物：`source_title` / `source_updated_at` / `data_date`
    / `stale_days` / `source_stale`。**这是内容级判据，不是 SLA 猜测** ——
    只在源自己标明的数据日落后时才置 stale，日频「今日批次未出」不会误报。
    """
    meta = {}
    for raw in text.split("\n"):
        ln = raw.replace("\ufeff", "").replace("\u200b", "").strip()
        if not ln:
            continue
        if "source_title" not in meta and re.match(r"^强势股跟踪日报", ln):
            meta["source_title"] = ln[:48]
        m = re.search(r"更新时间\s*[：:]\s*(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})", ln)
        if m and "source_updated_at" not in meta:
            y, mo, d, hh, mi = m.groups()
            meta["source_updated_at"] = "%s-%02d-%02d %02d:%s" % (y, int(mo), int(d), int(hh), mi)
    return meta


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
        meta = parse_note_meta(inner)
        browser.close()

    print(f"✅ 解析到 {len(stocks)} 只股票；汇总: {summary}")
    print(f"🏷️ 源笔记自述: {meta.get('source_title') or '?'} · 更新时间 {meta.get('source_updated_at') or '?'}")
    return {"summary": summary, "stocks": stocks, "meta": meta}


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

    # 🔴 2026-09-17 阿狸咪的工程师：「源数据日」判据（**内容级**，不是 SLA 猜测）。
    #   权威数据日取「每行最新交易日」的最大值；全部缺失时回退到源笔记自述更新时间。
    #   源若按日更新 ⇒ data_date 每天前进；源若停更 ⇒ data_date 原地不动 ⇒ source_stale 置真。
    #   为什么不能用 update_time 判：update_time 是**抓取时刻**，抓一份静止的源它也每天变，
    #   正是这个语义错配让本卡停更 15 天却仍显示「更新于 今日 15:53 盘后」。
    meta = data.get("meta") or {}
    _tx = datetime.now(timezone(timedelta(hours=8)))
    _trade_dates = sorted(str(_s.get("trade_date") or "").strip()
                          for _s in data["stocks"] if str(_s.get("trade_date") or "").strip())
    _data_date = _trade_dates[-1] if _trade_dates else str(meta.get("source_updated_at") or "")[:10]
    try:
        _stale_days = (_tx.date() - datetime.strptime(_data_date, "%Y-%m-%d").date()).days
    except Exception:
        _stale_days = None

    out = {
        # 🛡 2026-09-04：固定北京时间——云端 runner 是 UTC，旧写法 now() 让卡片把 20:17 显示成 12:17
        "update_time": _tx.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ima",
        "note_url": args.url,
        # 🔴 源自身的时间刻度（前端「更新于」**不得再拿抓取时刻冒充数据新鲜**）
        "source_title": meta.get("source_title") or "",
        "source_updated_at": meta.get("source_updated_at") or "",
        "data_date": _data_date,
        "stale_days": _stale_days,
        "source_stale": bool(_stale_days is not None and _stale_days > 0),
        "summary": data["summary"],
        "parse_health": parse_health,
        "stocks": data["stocks"],
    }
    # 🔴🔴 2026-09-18 阿狸咪的工程师 新增：**生产者自检**（杜绝「旧脚本假成功」）
    #   为什么放在生产脚本里而不是 CI 的独立 step：本仓 PAT 无 `workflow` scope，
    #   改 .github/workflows/ 会 403，故把断言内聚到生产者自身（**谁产出谁负责**），
    #   且这样连「人工跑一次」也受同样保护。配套事后审计见 verify_ima_sync.py。
    #
    #   真因实证：本脚本 09-17 21:53 上线新版（五字段 + 折叠修复），而 CI cron 是
    #   CST 15:45 ⇒ 当天早已用旧脚本跑完 ⇒ 五字段至今一次未写出、前端红胶囊判据恒假、
    #   回测样本被砍到 40/112，**而整条链全绿、无人知晓**。故形状不对必须立刻红。
    _viol = []
    for _k in ("data_date", "source_stale", "stale_days", "source_updated_at", "source_title"):
        if _k not in out:
            _viol.append("产物缺字段 %s" % _k)
    if parse_health.get("no_first_selected"):
        _viol.append("no_first_selected=%s（应恒为 0，否则空单元格折叠修复失效）"
                     % parse_health["no_first_selected"])
    if parse_health.get("field_missing_counts"):
        _viol.append("field_missing_counts 非空 %s（解析串位复发）"
                     % parse_health["field_missing_counts"])
    if _viol:
        print("❌ 产物自检失败 —— 拒绝写出坏产物：")
        for _v in _viol:
            print("   · " + _v)
        raise SystemExit(1)

    print(f"🩺 解析健康度: 总 {parse_health['total']} 只 · "
          f"无首次入选日 {parse_health['no_first_selected']} 只"
          f"（{parse_health['no_first_selected_pct']}%）· "
          f"字段串位 {sum(_missing_fields.values())} 次 {_missing_fields or ''}")
    # 🔴 2026-09-17：抓取成功 ≠ 数据新鲜。源侧停更必须吼出来（这是「杜绝假成功」的落点）
    if out["source_stale"]:
        print(f"⛔ 源停更告警：源笔记「{out['source_title'] or '?'}」自述更新时间 "
              f"{out['source_updated_at'] or '?'}，最新交易日 {out['data_date']} ⇒ "
              f"**已 {out['stale_days']} 天无新数据**。本次抓取成功但内容与上一期相同"
              f"（源侧停更，不是抓取失败）。")
    else:
        print(f"📅 源数据日 {out['data_date']}（新鲜）· 源自述更新时间 {out['source_updated_at'] or '?'}")

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
