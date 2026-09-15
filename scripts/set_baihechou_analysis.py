#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「白河愁博士观点解析」注入 data/BAIHECHOU_MACRO.js 的 analysis 字段。

为什么要单独一个脚本：
  fetch_baihechou_v8.py 只负责抓原文，且**只保留** analysis（绝不写它）；
  解析内容由每日 AI 步骤生成（结构化 JSON），经本脚本合并进产物。
  两者职责分离 ⇒ 抓取失败/原文更新都不会把解析抹掉，解析重写也不会动原文。

用法：
  python scripts/set_baihechou_analysis.py analysis.json     # 从文件读
  cat analysis.json | python scripts/set_baihechou_analysis.py  # 从 stdin 读
  python scripts/set_baihechou_analysis.py --show            # 只打印当前解析
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, "data", "BAIHECHOU_MACRO.js")

REQUIRED = ("verdict", "sections")


def load_js():
    with open(JS, "rb") as f:
        raw = f.read()
    t = raw.decode("utf-8")
    m = re.search(r"window\.BAIHECHOU_MACRO\s*=\s*", t)
    if not m:
        raise SystemExit("❌ data/BAIHECHOU_MACRO.js 里找不到 window.BAIHECHOU_MACRO 赋值")
    s = t[m.end():]
    i = s.find("{")
    depth, end = 0, -1
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    return json.loads(s[i:end])


def dump_js(d):
    js = "window.BAIHECHOU_MACRO = " + json.dumps(
        d, ensure_ascii=False, separators=(",", ":")) + ";\n"
    # 二进制写 + LF：与 fetcher 保持一致，避免 Windows 下自动 CRLF 造成整文件改写
    with open(JS, "wb") as f:
        f.write(js.encode("utf-8"))
    return len(js.encode("utf-8"))


def main():
    if "--show" in sys.argv:
        d = load_js()
        print(json.dumps(d.get("analysis"), ensure_ascii=False, indent=1))
        return 0

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            ana = json.load(f)
    else:
        ana = json.load(sys.stdin)

    for k in REQUIRED:
        if k not in ana:
            raise SystemExit(f"❌ 解析 JSON 缺必填字段：{k}")

    d = load_js()
    old = d.get("analysis") or {}
    d["analysis"] = ana
    d["meta"] = d.get("meta") or {}
    d["meta"]["analysis_source"] = ana.get("by") or "AI"
    d["meta"]["analysis_at"] = ana.get("generated_at") or ""
    n = dump_js(d)

    print(f"✅ analysis 已注入（{n} 字节）")
    print(f"   结论：{ana['verdict'][:80]}")
    print(f"   分段数：{len(ana['sections'])}" + (f"（原 {len(old.get('sections') or [])} 段被替换）" if old else "（首次写入）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
