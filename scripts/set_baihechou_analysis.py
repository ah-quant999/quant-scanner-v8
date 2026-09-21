#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「白河愁博士观点解析」注入 data/BAIHECHOU_MACRO.js 的 analysis 字段，
**并同步写出独立文件 data/BAIHECHOU_ANALYSIS.js**（window.BAIHECHOU_ANALYSIS）。

🛡 2026-09-21 小九（一劳永逸 · 补生产者）：
  2026-09-18 阿狸咪把 AI 解析拆成独立文件前端优先读（index.html 注入行 + `window.BAIHECHOU_ANALYSIS || d.analysis`），
  目的是「抓取方用陈旧本地副本整文件覆盖解析」不再可能。但**当时只改了前端与注释，没给独立文件生产者**：
  本脚本仍只写 MACRO 的 analysis 字段 ⇒ data/BAIHECHOU_ANALYSIS.js 自 09-18 06:31 起 3 天零写入
  （远端提交历史仅 1 笔 c3a152ca63），而它因「优先读」把每天照常出新的 MACRO.analysis 屏蔽掉，
  卡面解析冻结在 09-17 窗口；健康检查 BAIHECHOU_ANALYSIS 判 fail（age 4692min）。
  本脚本即补上这一半：注入与独立文件**同源同写**，任一都不再可能独缺。
  ⚠️ 独立文件顶层必须带 update_time —— 健康检查判龄（v8_health_check.py 该卡）与
     baihechou_daily.py::cmd_push 的「防倒退」保护（远端比本地新则拒推）都只认它。

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
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, "data", "BAIHECHOU_MACRO.js")
# 🛡 2026-09-21：独立解析文件（前端优先读它，见 index.html 注入行）。与 JS 双写，不可只写其一。
ANA_JS = os.path.join(BASE, "data", "BAIHECHOU_ANALYSIS.js")

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


def dump_analysis_js(ana):
    """把同一份解析写成独立文件 data/BAIHECHOU_ANALYSIS.js（单行压缩 + LF）。

    结构对齐 09-18 手工创建的那份（顶层 key 顺序保持）：解析字段原样 + update_time + source + note。
    update_time 是硬要求：健康检查判龄与 cmd_push 防倒退都只认它。
    """
    o = dict(ana)
    if not o.get("update_time"):
        # 优先用解析自身的出稿时刻（真实），缺失才退当前时刻（不臆造）
        o["update_time"] = o.get("generated_at") or time.strftime("%Y-%m-%d %H:%M")
    o["source"] = "AI 解析（原文 window.BAIHECHOU_MACRO）"
    o["note"] = ("本文件由每日 AI 解析步骤写入，与原文抓取解耦；抓取方不写本文件。"
                 "生产者 scripts/set_baihechou_analysis.py（经 scripts/baihechou_daily.py finish 调用）。")
    js = "window.BAIHECHOU_ANALYSIS = " + json.dumps(
        o, ensure_ascii=False, separators=(",", ":")) + ";\n"
    with open(ANA_JS, "wb") as f:
        f.write(js.encode("utf-8"))
    return len(js.encode("utf-8"))


def main():
    if "--show" in sys.argv:
        d = load_js()
        print(json.dumps(d.get("analysis"), ensure_ascii=False, indent=1))
        return 0

    # 🛡 2026-09-21：仅重建独立文件（用 MACRO 里已有的当期解析）——
    #   用于「独立文件缺生产者」事故的即时恢复：无需重跑 AI 出稿，把同一份解析搬过去即可。
    if "--rebuild-analysis-only" in sys.argv:
        d = load_js()
        ana = d.get("analysis") or {}
        if not (ana.get("verdict") and ana.get("sections")):
            raise SystemExit("❌ MACRO 内 analysis 缺 verdict/sections，无法重建独立文件")
        n = dump_analysis_js(ana)
        print(f"✅ 独立文件已重建（{n} 字节，generated_at={ana.get('generated_at')}）")
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
    m = dump_analysis_js(ana)   # 🛡 双写：独立文件与 MACRO.analysis 必须同源同写

    print(f"✅ analysis 已注入（{n} 字节）")
    print(f"✅ 独立文件已同步（{m} 字节 · data/BAIHECHOU_ANALYSIS.js）")
    print(f"   结论：{ana['verdict'][:80]}")
    print(f"   分段数：{len(ana['sections'])}" + (f"（原 {len(old.get('sections') or [])} 段被替换）" if old else "（首次写入）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
