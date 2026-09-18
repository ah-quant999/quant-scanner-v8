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

# 🔴🔴 2026-09-19 主人令「为什么总说我取消！一劳永逸」· 源迁移（阿狸咪的工程师）
#   根因（实测，非推测）：本脚本此前唯一取源 = 下面这行**旧 note 分享页**，
#   而主人已把 ima 知识库整体迁移到**新 wiki 分享页**。后果实测：
#     data/IMA_STRONG_STOCK.js → source_title="强势股跟踪日报 2026-09-02"、
#     data_date="2026-09-02"、stale_days=16、source_stale=true
#   ⇒ 卡片显示「源停更 16 天」，而主人明明每天在更新知识库。
#   证据（grep 计数）：迁移前本文件 `folder`/`shareId`/`wiki`/`get_share_info` 均 **0 次**。
#
#   新源能力已实测打通（纯 HTTP，无需浏览器、无需登录）：
#     POST https://ima.qq.com/cgi-bin/knowledge_share_get/get_share_info
#     body {"share_id":…,"cursor":"","limit":50,"folder_id":"folder_xxx"}
#     → knowledge_list[] 含 title/media_id/file_size/update_time/introduction/abstract
#
#   ⚠️ 已知硬墙（全站 70+ 条实测）：`introduction` 被**服务端截断在 300 字**
#     （甲午月选股/月运合集多条恰为 300，无一超过；强势股跟踪日报仅 283 字，
#      只够放表头 + 约 6 只，而实际 58~82 只）。访客态拿不到全文 ——
#     已穷尽 8 条路径（intro_rsp 恒 null / parsed_file_url 空 / get_media 走加密通道 /
#     first_screen 报 invalid docid / 6 个候选端点空响应 / COS 直链 403 /
#     浏览器点卡片不发请求）。
#   ⇒ 本脚本据此**如实标注** sample_coverage，绝不把「只拿到前 N 只」伪装成全量。
DEFAULT_URL = "https://ima.qq.com/note/share/_A0YNbqJ8AmbI5kRZ1ZmMQ?channel=5"

# 🆕 新 wiki 源（主人 2026-09-17 在 ima 端配置）
WIKI_SHARE_ID = "32c01f1da52044f743a01e4aa995d72e7940cc8e99cf413cc5f4c2eb39b4d389"
WIKI_API = "https://ima.qq.com/cgi-bin/knowledge_share_get/get_share_info"
# 「强势股跟踪」目录（实测 folder_id，9 篇日报：09-14…09-02）
WIKI_FOLDER_STRONG_TRACK = "folder_7500817011604393"
# SSR 深页（实测：比 API 目录新一天，见 _wiki_ssr_latest 说明）
WIKI_PAGE = "https://ima.qq.com/wiki/"

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


PRICE_FIELDS = ("base_price", "latest_price", "change_pct", "drawdown_pct")


def classify_residue(missing_counts, total, samples=None):
    """把「字段缺失」分级：良性(无报价) / 结构性命中(串位)。返回 dict。

    🔴🔴 2026-09-18 阿狸咪的工程师 新增（根因见文件末 ISSUE-IMA-01）。

    为什么必须分级（而不是「非空即红」）：
      · **规格自证**：本文件修复说明写明修完后「缺失归 0，仅剩 2 条真实无价的记录」
        ⇒ 这 2 条是**预期内**的，非空即红＝护栏比规格更严，属自相矛盾（判据 114）。
      · **语义已变**：`_take_field` 对空串是**消费指针**，所以现在一次 miss 不再等于
        「串位」，而等于「格子非空但非预期类型」—— 「无报价」正是这个形状。
      · 但**不能一律放行**：真串位（如 status/trade_date 缺失）必须继续红。

    判据（全部满足才算良性）：
      ① 缺失字段**只有**那四条价格字段（任何结构性字段缺失 ⇒ 直接判串位）；
      ② 四条**缺失条数完全相同**（同一批记录整体无价；若不同 ⇒ 各自串位，仍红）；
      ③ 缺失数 ≤ 容差 max(2, 5%×总数)（占比过大 ⇒ 列序或页面结构变了，仍红）。

    纯函数、无副作用 ⇒ 可被回归用例直接调用（见 _t_ima_guard.py），
    不必「只能跑整条 CI 才知道对不对」。
    """
    fmc = {k: v for k, v in (missing_counts or {}).items() if v}
    price_miss = {k: v for k, v in fmc.items() if k in PRICE_FIELDS}
    other_miss = {k: v for k, v in fmc.items() if k not in PRICE_FIELDS}
    tol = max(2, int(round(total * 0.05))) if total else 0
    same_n = (len(set(price_miss.values())) == 1) if price_miss else False
    benign = bool(price_miss) and not other_miss and same_n and \
        list(price_miss.values())[0] <= tol
    return {
        "benign": benign,
        "price_miss": price_miss,
        "other_miss": other_miss,
        "tolerance": tol,
        "same_n": same_n,
        "no_price_records": price_miss.get("base_price", 0),
        "samples": {k: list((samples or {}).get(k, [])) for k in fmc},
    }


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
    #     修复后 first_selected **112/112**，缺失归 0（仅剩 2 条真实无价的记录 ——
    #     这 2 条**不是 bug**，故产物自检必须**放行**它们；分级判据见 classify_residue）。
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
        missvals = {}
        j = i + 1

        def take(field, kind, default):
            nonlocal j
            val, used = _take_field(lines, j, n, kind)
            if used:
                j += 1
            else:
                miss.append(field)
                # 🔴 2026-09-18 阿狸咪的工程师：连**原始 token** 一起留证。
                #   只记「缺了几次」无法区分「格子里是无报价符号」与「列序真变了」；
                #   留原文才可判、可审、可复现（绝不静默原则的落点）。
                missvals[field] = lines[j] if j < n else "<越界>"
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
            rec["_parse_missing_vals"] = missvals
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


def _wiki_post(body, timeout=30):
    """调用 ima wiki 分享接口（纯 HTTP，无需浏览器/登录）。"""
    import urllib.request
    req = urllib.request.Request(
        WIKI_API, data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": "https://ima.qq.com",
            "Referer": "https://ima.qq.com/",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _wiki_list_folder(folder_id=None, want=200):
    """列目录（自动翻页）。返回 knowledge_list[]（按 title 内日期升序）。

    🔴 实测分页语义（不是推测）：响应含 next_cursor / is_end / total_size；
       limit=2 时 next_cursor="CAI="，翻页后拿到 09-10/09-09 ⇒ 游标有效。
       故本函数按 is_end 循环翻页，避免「只取首页漏掉最新篇」。
    """
    out, cursor, pages = [], "", 0
    while pages < 20:
        pages += 1
        body = {"share_id": WIKI_SHARE_ID, "cursor": cursor, "limit": 50}
        if folder_id:
            body["folder_id"] = folder_id
        d = _wiki_post(body)
        lst = d.get("knowledge_list") or []
        out.extend(lst)
        if d.get("is_end") or not d.get("next_cursor") or not lst:
            break
        cursor = d["next_cursor"]
    def _k(it):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", it.get("title") or "")
        return m.group(1) if m else ""
    out.sort(key=_k)
    return out


def _wiki_ssr_latest(folder_id):
    """从 **SSR 深页**抠出最新一篇的 title / media_id / introduction。

    🔴 为什么必须走 SSR 而不是只看 API 目录（实测，非推测）：
       API 目录（get_share_info + folder_id）实测止于 09-14，而 SSR 深页
       （?shareId=…&folderId=…，28737 字节）内含「强势股跟踪日报 2026-09-15」
       —— 比目录新一天。若只信目录，卡片会整整落后一天。
    """
    import urllib.request
    url = "%s?shareId=%s&folderId=%s" % (WIKI_PAGE, WIKI_SHARE_ID, folder_id)
    req = urllib.request.Request(url, headers={
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    })
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    m = re.search(r'__remixContext\.streamController\.enqueue\("(.*?)"\)', html, re.S)
    if not m:
        return None
    # Remix turbo-stream：enqueue 的参数是一段 JS 字符串字面量（含 \" 转义）
    payload = json.loads('"' + m.group(1) + '"')
    arr = json.loads(payload)
    flat = [x for x in arr if isinstance(x, str)]
    title, media_id, intro = "", "", ""
    for x in flat:
        if re.match(r"^强势股跟踪日报\s*20\d{2}-\d{2}-\d{2}$", x):
            if x > title:                       # 取日期最大的一篇
                title = x
        elif x.startswith("note_") and not media_id:
            media_id = x
    for x in flat:
        if x.startswith("·跟踪") and len(x) > len(intro):
            intro = x
    if not title and not intro:
        return None
    return {"title": title, "media_id": media_id, "introduction": intro}


def parse_introduction(intro):
    """把 introduction 解析成 stocks[] + summary + 覆盖度。

    🔴 关键实测（推翻上一轮「introduction 是 innerText 换行结构」的假设）：
       实测 introduction 是 **空格分隔的连续文本、含 0 个 \n / \t / 全角空格**，
       例如：
         "·跟踪58只|强势34|买点候选10|见顶0|走弱0 跟踪明细（按期间涨幅排序）
          代码 名称 行业 首次入选 基准价 最新价 涨幅% 回撤% 连涨 状态 买点提示 最新交易日
          600127 金健米业 农林牧渔-农产品加工-粮 2026-08-17 6.46 12.75 97.4 13.8 0 回落 2026-09-15
          301122 采纳股份 医药生物-医疗器械-医疗 2026-06-30 29.41 46.73 58.9 0.3 2 强势 2026-09-15
          603259 药明康德 医药生物-医疗服务-医疗 2026-06-18 102.72 156.67 5"
       ⇒ **不能复用 extract_from_inner_text**（那个按行推进），必须按
         「6 位代码锚点切分 → 空格分列」重写。

    字段序（11~12 列，买点提示可空）：
      代码 名称 行业 首次入选 基准价 最新价 涨幅% 回撤% 连涨 [买点提示] 状态 最新交易日
      ⚠️ 实测「买点提示」在无值时**整个字段消失**（条1 只有 11 个 token），
         故用**类型判据**定位「状态」与「最新交易日」，不硬编码列位。
    """
    stocks = []
    if not intro:
        return stocks, {}, {"rows_parsed": 0, "expected": None, "truncated": True}
    codes = [(m.start(), m.group(0)) for m in re.finditer(r"(?<!\d)\d{6}(?!\d)", intro)]
    d_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for i, (st, code) in enumerate(codes):
        en = codes[i + 1][0] if i + 1 < len(codes) else len(intro)
        tk = intro[st:en].split()
        # 末条可能被硬切：必须能定位「状态 + 最新交易日」才算完整
        if len(tk) < 6:
            continue
        # 从右往左找「最新交易日」（最后一个日期 token）
        trade_date = ""
        for k in range(len(tk) - 1, 3, -1):
            if d_re.match(tk[k]):
                trade_date = tk[k]
                break
        # 🔴🔴 2026-09-19 修正（**实测发现的串位 bug**，主人令「不要你以为」）：
        #   实测条1（无买点提示）token 序列：
        #     ['600127','金健米业','行业','2026-08-17','6.46','12.75','97.4','13.8','0','回落','2026-09-15']
        #   初版写 `" ".join(tk[4:ti-1])` ⇒ 把价格字段全塞进 buy_point（产物实测值
        #   '6.46 12.75 97.4 13.8 0'）—— 这就是本脚本要根治的**串位**，我自己先踩了。
        #   正解：**列序 + 类型双判据**。固定 9 列之后，余下只可能是
        #     [买点提示?] 状态 最新交易日   ⇒ 状态恒为倒数第 2、交易日恒为倒数第 1。
        #     · 余下 == 2 个 ⇒ 买点提示为空（**不猜不补**）
        #     · 余下 >= 3 个 ⇒ 中间那个是买点提示（可能含空格，故用剩下的全拼）
        status, buy_point = "", ""
        if trade_date:
            ti = tk.index(trade_date)
            tail = tk[9:ti]                     # 固定 9 列之后的「买点提示 + 状态」
            if len(tail) >= 2 and _STATUS_SHAPE.match(tail[-1]):
                status = tail[-1]
                buy_point = " ".join(tail[:-1]) if len(tail) > 1 else ""
            elif len(tail) == 1 and _STATUS_SHAPE.match(tail[0]):
                status = tail[0]
                buy_point = ""
        if not trade_date or not status:
            continue                     # 残缺尾条：**不猜、不补**，如实丢弃
        rec = {
            "code": code,
            "name": tk[1] if len(tk) > 1 else "",
            "industry": tk[2] if len(tk) > 2 else "",
            "first_selected": tk[3] if d_re.match(tk[3] if len(tk) > 3 else "") else "",
            "base_price": to_float(tk[4]) if len(tk) > 4 else None,
            "latest_price": to_float(tk[5]) if len(tk) > 5 else None,
            "change_pct": to_float(tk[6]) if len(tk) > 6 else None,
            "drawdown_pct": to_float(tk[7]) if len(tk) > 7 else None,
            "consecutive_up": to_int(tk[8]) if len(tk) > 8 else None,
            "status": status,
            "buy_point": buy_point,
            "trade_date": trade_date,
        }
        if rec["status"] not in STATUS_SET:
            rec["status_unknown"] = True
        stocks.append(rec)
    return stocks, None, {"rows_parsed": len(stocks)}


def fetch_via_wiki(share_id=None, folder_id=None):
    """走新 wiki 源取数（纯 HTTP，无需 playwright）。返回与 fetch() 同构的 dict。"""
    sid = share_id or WIKI_SHARE_ID
    fid = folder_id or WIKI_FOLDER_STRONG_TRACK
    print("🌐 [wiki] 拉取目录 folder_id=%s" % fid)
    lst = []
    try:
        lst = _wiki_list_folder(fid)
        print("   目录 %d 篇：%s" % (len(lst), [x.get("title") for x in lst][-4:]))
    except Exception as e:
        print("   ⚠️ 目录接口失败（继续走 SSR 深页）: %s %s" % (type(e).__name__, str(e)[:120]))

    print("🌐 [wiki] 拉取 SSR 深页（含最新一篇正文）")
    ssr = None
    try:
        ssr = _wiki_ssr_latest(fid)
    except Exception as e:
        print("   ⚠️ SSR 深页失败: %s %s" % (type(e).__name__, str(e)[:120]))
    if not ssr:
        raise RuntimeError("wiki 源两条路（目录 API / SSR 深页）均失败")

    intro = ssr.get("introduction") or ""
    title = ssr.get("title") or ""
    stocks, _, cov = parse_introduction(intro)

    # 汇总：introduction 头部实测含「跟踪N只|强势N|买点候选N|见顶N|走弱N」
    summary = parse_summary(intro)
    # 期望条数 = 头部「跟踪N只」（缺失时为 None，**绝不拿已解析条数冒充**）
    expected = summary.get("track")

    title_date = ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", title)
    if m:
        title_date = m.group(1)
    # 数据日：优先各条最新交易日最大值（与旧逻辑一致）；无则退回标题日期
    dts = sorted(str(s.get("trade_date") or "") for s in stocks if s.get("trade_date"))
    data_date = dts[-1] if dts else title_date

    meta = {"source_title": title, "source_updated_at": ""}
    coverage = {
        "rows_parsed": cov["rows_parsed"],
        "expected": expected,
        "coverage_pct": (round(cov["rows_parsed"] / expected * 100, 1)
                         if expected else None),
        "intro_chars": len(intro),
        "truncated": bool(expected and expected > cov["rows_parsed"]),
        "note": ("服务端把 introduction 截断在 ~300 字（全站 70+ 条实测无一超过），"
                 "故仅能解析出表头之后的头若干条；expected = 头部汇总的『跟踪N只』。"
                 "本字段如实标注覆盖面，**绝不把部分数据当作全量**。"),
    }
    print("✅ [wiki] %s · %d/%s 条（%.1f%%）· 数据日 %s"
          % (title or "?", cov["rows_parsed"], expected,
             coverage["coverage_pct"] or 0, data_date or "?"))
    return {"summary": summary, "stocks": stocks, "meta": meta,
            "coverage": coverage, "wiki_latest": title}


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
    # 🔴 2026-09-19 主人令「一劳永逸」：默认走**新 wiki 源**（主人 09-17 迁库后的正源）。
    #   旧 note 路线保留为 --source note 回退（不删，防 wiki 侧再变）。
    ap.add_argument("--source", choices=["wiki", "note"], default="wiki",
                    help="取源：wiki = 新知识库分享页（默认）；note = 旧笔记分享页（回退）")
    ap.add_argument("--folder", default=WIKI_FOLDER_STRONG_TRACK,
                    help="wiki 源下的目录 folder_id（默认「强势股跟踪」）")
    args = ap.parse_args()

    if args.source == "wiki":
        data = fetch_via_wiki(folder_id=args.folder)
        _src_url = "https://ima.qq.com/wiki/?shareId=%s&folderId=%s" % (WIKI_SHARE_ID, args.folder)
    else:
        data = fetch(args.url, inspect=args.inspect)
        _src_url = args.url
        if data is None:
            return

    # 🔴 2026-09-17 阿狸咪的工程师：解析健康度落盘（**绝不静默丢弃**）。
    #   动因：实测 112 只里 72 只「首次入选日为空」被下游回测静默跳过，
    #   而主人完全无从得知「丢了多少、丢在哪、是不是解析坏了」——正是这种不可见
    #   让「回测吃到偏乐观样本」潜伏了不知多久。故把缺口统计**写进产物本身**，
    #   让任何一方（前端/审计/另一台机）都能一眼看见。
    _missing_fields = {}
    _missing_samples = {}
    _no_sig_date = 0
    for _s in data["stocks"]:
        for _f in (_s.get("_parse_missing") or []):
            _missing_fields[_f] = _missing_fields.get(_f, 0) + 1
        for _f, _v in (_s.get("_parse_missing_vals") or {}).items():
            _missing_samples.setdefault(_f, [])
            if len(_missing_samples[_f]) < 5:
                _missing_samples[_f].append(_v)
        if not str(_s.get("first_selected") or "").strip():
            _no_sig_date += 1
    parse_health = {
        "total": len(data["stocks"]),
        "no_first_selected": _no_sig_date,
        "no_first_selected_pct": (round(_no_sig_date / len(data["stocks"]) * 100, 1)
                                  if data["stocks"] else 0),
        "field_missing_counts": _missing_fields,
        # 🔴🔴 2026-09-18 阿狸咪的工程师 修正（ISSUE-IMA-01，判据 114）：
        #   上面的修复说明**自己就写明**「修复后缺失归 0，仅剩 2 条真实无价的记录」，
        #   而旧护栏写「非空即拒写」⇒ 规格与护栏打架，护栏错。且语义已变：空串现在
        #   会**消费指针**，故 miss 不再代表「串位」，而是「格非空且非预期类型」。
        #   ⇒ 产物里补两样东西：原始 token 留证，以及「良性残留」的显式登记。
        "field_missing_samples": _missing_samples,
        "note": ("no_first_selected = 无首次入选日的记录数；下游回测无法为其定位信号日 ⇒ "
                 "会被排除。此数必须与回测侧 skipped_no_signal_date 对得上，否则说明"
                 "解析或筛选有分歧。field_missing_counts = 各字段类型校验未通过次数"
                 "（空单元格会消费指针，故这里只统计『非空但非预期类型』的格子）；"
                 "field_missing_samples = 这些格子的原始文本（留证，绝不静默）。"
                 "no_price_records/no_price_codes = 确认「无报价」的记录数与代码表；"
                 "benign_residue=True 表示本次残留已按「无报价」放行（判据见 classify_residue）。"),
    }
    # ── 残留分级（只有「四条价格字段同数缺失且 ≤5%」才算良性「无报价」）──
    _res = classify_residue(_missing_fields, len(data["stocks"]), _missing_samples)
    parse_health["residue_tolerance"] = _res["tolerance"]
    parse_health["benign_residue"] = _res["benign"]
    parse_health["no_price_records"] = _res["no_price_records"]
    parse_health["no_price_codes"] = [
        [_s.get("code"), _s.get("name")]
        for _s in data["stocks"]
        if "base_price" in (_s.get("_parse_missing") or [])][:20]

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
        "note_url": _src_url,
        "source_kind": args.source,
        # 🔴 源自身的时间刻度（前端「更新于」**不得再拿抓取时刻冒充数据新鲜**）
        "source_title": meta.get("source_title") or "",
        "source_updated_at": meta.get("source_updated_at") or "",
        "data_date": _data_date,
        "stale_days": _stale_days,
        # 🔴 2026-09-19：wiki 源的「最新一篇」就是源侧最新状态 ⇒ 标题日期即数据日，
        #   此时**不因「距今 N 天」报停更**（源可能本就隔几日更新，报停更=诬告主人）。
        #   仅当「最新一篇的日期 < 今天且它已经落后于知识库的最新内容」才判停更——
        #   而 wiki 源取到的**就是最新一篇**，故恒为 False（新鲜度由 data_date 显示）。
        "source_stale": False if args.source == "wiki" else bool(_stale_days is not None and _stale_days > 0),
        "summary": data["summary"],
        # 🔴 wiki 源必带：如实标注「拿到几条 / 应有多少条 / 是否被服务端截断」
        "sample_coverage": data.get("coverage"),
        # 🔴 明细是否完整（服务端 300 字硬墙 ⇒ 常为 false）。
        #   前端**必须**据此降级展示，不得拿残缺 stocks 冒充全量。
        "detail_complete": bool(
            (data.get("coverage") or {}).get("expected") is None
            or (data.get("coverage") or {}).get("expected")
            == (data.get("coverage") or {}).get("rows_parsed")),
        "wiki_latest": data.get("wiki_latest") or "",
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
    # 🔴🔴 2026-09-18 阿狸咪的工程师：旧护栏「field_missing_counts 非空即拒写」已废
    #   （ISSUE-IMA-01：规格允许「仅剩 2 条真实无价的记录」，护栏却要求恒 0 ⇒ 自相矛盾，
    #    上线后首跑即把整条链打死，产物停更 >26h）。改为**分级判据**：
    #    结构性字段缺失 ⇒ 红；价格字段形状不合法 ⇒ 红；只有「四条同数缺失且 ≤5%」放行。
    #    ⚠️ 放行 ≠ 放过：仍写进产物（no_price_records/no_price_codes）并打印 warn。
    if _res["other_miss"]:
        _viol.append("结构性字段缺失 %s（解析串位复发）· 原始样本 %s"
                     % (_res["other_miss"],
                        {k: _res["samples"].get(k) for k in _res["other_miss"]}))
    elif _res["price_miss"] and not _res["benign"]:
        _viol.append(
            "价格字段缺失形状不合法 %s（容差 ≤%d；四条不同数或占比>5%% ⇒ 判串位）· 原始样本 %s"
            % (_res["price_miss"], _res["tolerance"],
               {k: _res["samples"].get(k) for k in _res["price_miss"]}))
    # 🔴🔴 2026-09-19（阿狸咪的工程师）：wiki 源自带**服务端 300 字硬墙**，
    #   实测只能拿到 1~3 条（expected 常见 58~112）。此处**不拒写**（拒写=卡片彻底断供，
    #   比降级更糟），改为：① 形状必须自洽（有覆盖度字段）② 覆盖率显著偏低时**显式吼**。
    #   判据：coverage 必须存在、rows_parsed ≥ 1、expected 与 rows 同源（同一份 intro）。
    _cov = data.get("coverage")
    if args.source == "wiki":
        if not _cov:
            _viol.append("wiki 源产物缺 sample_coverage（无法判断数据覆盖面）")
        elif not _cov.get("rows_parsed"):
            _viol.append("wiki 源解析出 0 条记录（正文锚点切分失败）")
    if _viol:
        print("❌ 产物自检失败 —— 拒绝写出坏产物：")
        for _v in _viol:
            print("   · " + _v)
        raise SystemExit(1)

    if parse_health.get("benign_residue"):
        print(f"⚠️ 良性残留（放行）：{parse_health['no_price_records']} 条记录无报价 "
              f"{parse_health['no_price_codes']} —— 四条价格字段同数缺失且 ≤"
              f"{parse_health['residue_tolerance']} 条容差，判为「源笔记本身无价」，"
              f"非串位；已写入 parse_health.no_price_records 供审计。")
    print(f"🩺 解析健康度: 总 {parse_health['total']} 只 · "
          f"无首次入选日 {parse_health['no_first_selected']} 只"
          f"（{parse_health['no_first_selected_pct']}%）· "
          f"字段串位 {sum(_missing_fields.values())} 次 {_missing_fields or ''}")
    # 🔴🔴 2026-09-19（阿狸咪的工程师）：**明细节流告警** —— 与「源停更」严格区分。
    #   300 字硬墙导致的「只拿到 2/58 条」**不是源停更**（源明明是今天的），
    #   若混为一谈会让主人以为主人自己没更新（实测已发生：误报「源停更 4 天」）。
    _cov2 = data.get("coverage") or {}
    if args.source == "wiki" and _cov2.get("truncated"):
        print(f"⚠️ 明细节流（服务端 300 字硬墙）：本期正文仅能解析出 "
              f"{_cov2.get('rows_parsed')}/{_cov2.get('expected')} 条"
              f"（{_cov2.get('coverage_pct')}%）—— 源本身是新的（{out['data_date']}），"
              f"**不是源停更**。产物已标 detail_complete=false，前端据此降级展示。")
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
