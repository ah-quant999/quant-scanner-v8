#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_do_not_delete_js.py — 把仓库根的 DO_NOT_DELETE.md（禁止删除清单）渲染成
前端可直接注入的 data/DO_NOT_DELETE.js（window.DO_NOT_DELETE_HTML）。

用途：
  - 逻辑详解页「防删」子页读取 window.DO_NOT_DELETE_HTML 渲染，管理员可见。
  - 每次 DO_NOT_DELETE.md 变动（新增保护文件/豁免条目）后，本脚本重新生成视图，
    使页面与清单保持同步。
  - 固定挂接在 .github/workflows/v8_cleanup.yml（周日 23:00 CST）末尾步骤，
    实现「跟着每周日定时任务一起跟踪更新维护」。

渲染约定：
  - 轻量 Markdown → HTML 转换器，仅覆盖本清单实际用到的语法
    （#/##/### 标题、> 引用块、| 表格、无序/有序列表、**加粗**、`代码`、--- 分隔线）。
  - 全部 HTML 经 json 转义后写入 JS 字符串，杜绝引号/换行破坏脚本。
  - 计算内容 sha256 前 10 位作为 ?v 缓存戳，并回写 index.html 中
    data/DO_NOT_DELETE.js?v= 的戳值（与 update_v8.py 对其它 data/*.js 的口径一致）。

铁律：数据必须走 window.X 注入，禁止 fetch('../data/...')。本脚本产物即 window.X。
"""

import os
import re
import json
import hashlib
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "DO_NOT_DELETE.md")
OUT = os.path.join(ROOT, "data", "DO_NOT_DELETE.js")
INDEX = os.path.join(ROOT, "index.html")


def esc_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s: str) -> str:
    """行内格式：**加粗** 与 `代码`。先转义 HTML 特殊字符。"""
    s = esc_html(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def split_row(line: str):
    """把 `| a | b | c |` 拆成 ['a','b','c']（去首尾空管道与空白）。"""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_sep(cells):
    return all(re.fullmatch(r":?-+:?", c) for c in cells if c != "")


def render_table(rows):
    body_rows = []
    header = None
    for idx, r in enumerate(rows):
        cells = split_row(r)
        if idx == 1 and is_sep(cells):
            continue  # 分隔线行
        if idx == 0:
            header = cells
            continue
        body_rows.append(cells)
    out = ['<table class="lg-table">']
    if header:
        out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead>")
    out.append("<tbody>")
    for cells in body_rows:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def is_special(line: str) -> bool:
    s = line.lstrip()
    if s.startswith("#"):
        return True
    if s.startswith(">"):
        return True
    if s.startswith("|"):
        return True
    if re.match(r"^\s*[-*]\s+", line):
        return True
    if re.match(r"^\s*\d+\.\s+", line):
        return True
    if line.strip() == "---":
        return True
    return False


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out = []
    i, n = 0, len(lines)
    quote_style = (
        "border-left:3px solid var(--gold);background:rgba(251,191,36,.06);"
        "padding:10px 14px;border-radius:8px;margin:10px 0;line-height:1.85;"
    )
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped == "---":
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("### "):
            out.append(f'<h3>{inline(line[4:])}</h3>')
            i += 1
            continue
        if stripped.startswith("## "):
            out.append(f'<h2>{inline(line[3:])}</h2>')
            i += 1
            continue
        if stripped.startswith("# "):
            out.append(f'<h1>{inline(line[2:])}</h1>')
            i += 1
            continue
        if stripped.startswith("|"):
            tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            out.append(render_table(tbl))
            continue
        if line.lstrip().startswith(">"):
            qb = []
            while i < n and lines[i].lstrip().startswith(">"):
                qb.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append(f'<blockquote style="{quote_style}">{md_to_html(chr(10).join(qb))}</blockquote>')
            continue
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                m = re.match(r"^\s*[-*]\s+(.*)", lines[i])
                items.append(inline(m.group(1)))
                i += 1
            out.append('<ul style="margin:8px 0 8px 20px;line-height:1.9;">' +
                       "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                m = re.match(r"^\s*\d+\.\s+(.*)", lines[i])
                items.append(inline(m.group(1)))
                i += 1
            out.append('<ol style="margin:8px 0 8px 20px;line-height:1.9;">' +
                       "".join(f"<li>{x}</li>" for x in items) + "</ol>")
            continue
        if stripped == "":
            i += 1
            continue
        # 段落：合并连续非特殊行
        para = [line]
        i += 1
        while i < n and lines[i].strip() != "" and not is_special(lines[i]):
            para.append(lines[i])
            i += 1
        out.append(f'<p style="line-height:1.9;margin:8px 0;">{inline(" ".join(para))}</p>')
    return "\n".join(out)


def patch_index_v(hash10: str) -> bool:
    """回写 index.html 中 data/DO_NOT_DELETE.js?v= 的缓存戳；若无此标签则插入。"""
    if not os.path.exists(INDEX):
        return False
    with open(INDEX, "r", encoding="utf-8") as f:
        html = f.read()
    tag_re = re.compile(r'<script src="data/DO_NOT_DELETE\.js\?v=[0-9a-f]+" defer></script>')
    if tag_re.search(html):
        html2 = tag_re.sub(
            f'<script src="data/DO_NOT_DELETE.js?v={hash10}" defer></script>', html)
    else:
        # 在最后一个 data/*.js defer 脚本后插入
        anchor = re.compile(r'(<script src="data/[A-Z_]+?\.js\?v=[0-9a-f]+" defer></script>)')
        last = None
        for m in anchor.finditer(html):
            last = m
        if last:
            ins = f'<script src="data/DO_NOT_DELETE.js?v={hash10}" defer></script>'
            html2 = html[:last.end()] + "\n    " + ins + html[last.end():]
        else:
            html2 = html
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html2)
    return True


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"❌ 找不到源文件：{SRC}")
    with open(SRC, "r", encoding="utf-8") as f:
        md = f.read()
    html = md_to_html(md)
    hash10 = hashlib.sha256(html.encode("utf-8")).hexdigest()[:10]
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    payload = (
        "// 由 scripts/gen_do_not_delete_js.py 自动生成，勿手改。\n"
        f"// 源：DO_NOT_DELETE.md  | 生成：{now} (Asia/Shanghai)  | 内容sha10：{hash10}\n"
        f"window.DO_NOT_DELETE_HTML = {json.dumps(html, ensure_ascii=False)};\n"
        f"window.DO_NOT_DELETE_UPDATED = {json.dumps(now)};\n"
        f"window.DO_NOT_DELETE = {{\"update_time\": {json.dumps(now)}, \"html_sha10\": {json.dumps(hash10)}, \"html_len\": {len(html)}}};\n"
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(payload)
    # 🔧 一致性：写完后再算磁盘文件 sha10（含 timestamp + window.X 包装），
    #    用最终 disk_sha 作为 ?v 缓存戳回写 index.html，杜绝 CDN 缓存失配
    hash10 = hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:10]
    # 把 payload 头部注释里的 hash10 修正成 disk_sha（让注释和 ?v 一致）
    payload2 = re.sub(r"内容sha10：[a-f0-9]{10}", f"内容sha10：{hash10}", payload, count=1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(payload2)
    # 二次确认稳定（不会有 modify 链）
    hash10 = hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:10]
    patched = patch_index_v(hash10)
    print(f"✅ 生成 {os.path.relpath(OUT, ROOT)}  (HTML {len(html)} 字节, ?v={hash10})")
    print(f"✅ index.html ?v 回写: {'已更新' if patched else '未改动（标签缺失）'}")


if __name__ == "__main__":
    main()
