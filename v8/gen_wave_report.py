#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股艾略特波浪定位研报 · 渲染脚本（零 westock 依赖）

【设计目的】
  原波浪研报依赖 westock MCP（通达信行情接口）现场取数，阿狸咪机无此连接器，
  无法独立产出/更新报告。本脚本把「数据」与「渲染」解耦：
    - 数据层 = data/WAVE_ELLIOTT.js（由小九/weekend 用 westock 拉取并推仓库）
    - 渲染层 = v8/wave_report_template.html（内嵌主观研判文案，读 window.WAVE_ELLIOTT）
  阿狸咪只需 git pull 最新数据 + 跑本脚本，即可生成最新研报 HTML，无需任何金融连接器。

【阿狸咪操作流程】
  cd quant-scanner-v8
  git pull
  python v8/gen_wave_report.py
  # 产出 out/A股波浪定位-YYYYMMDD.html（浏览器打开即看，需联网加载 ECharts CDN）

【数据更新（小九/weekend 负责）】
  用 westock 重拉上证日K/5指数日K → 覆盖 data/WAVE_ELLIOTT.js 的
  series.dates / series.closes / marks / idx → 推仓库。
  阿狸咪次日 pull + 重跑脚本即得更新版。
"""
import re, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "WAVE_ELLIOTT.js")
TPL  = os.path.join(ROOT, "v8", "wave_report_template.html")
OUT  = os.path.join(ROOT, "out")


def dump_js(obj):
    """产出与 update_v8.py 一致的压缩态（单行）。"""
    return "window.WAVE_ELLIOTT = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n"


def main():
    if not os.path.exists(DATA):
        sys.exit("✗ 缺少数据源 data/WAVE_ELLIOTT.js（请先 `git pull` 拉取最新）")
    if not os.path.exists(TPL):
        sys.exit("✗ 缺少模板 v8/wave_report_template.html")

    h = open(DATA, encoding="utf-8").read()
    # 兼容两种落盘形态：① 本地美化（多行 indent=1）② update_v8.py 压缩（单行 separators=(',',':')）
    # 不能用要求 "\n}" 的正则——仓库内所有 data/*.js 经 update_v8.py 后均为单行压缩态。
    m = re.search(r'window\.WAVE_ELLIOTT\s*=\s*(\{.*\});\s*$', h.strip(), re.S)
    if not m:
        sys.exit("✗ 无法解析 data/WAVE_ELLIOTT.js（window.WAVE_ELLIOTT 结构异常）")
    try:
        w = json.loads(m.group(1))
    except Exception as e:
        sys.exit("✗ data/WAVE_ELLIOTT.js JSON 解析失败: %s" % e)

    meta = w.get("meta", {})
    date = meta.get("date", "unknown")
    s = w.get("series", {})
    # 数据完整性校验（防残缺数据产出空图）
    if len(s.get("dates", [])) != len(s.get("closes", [])):
        sys.exit("✗ 数据残缺：dates/closes 长度不一致")
    if not w.get("marks") or not w.get("idx"):
        sys.exit("✗ 数据残缺：marks/idx 为空")

    d = date.replace("-", "")
    outp = os.path.join(OUT, "A股波浪定位-%s.html" % d)
    os.makedirs(OUT, exist_ok=True)

    # 产出「自包含 HTML」：把数据内联进产物，抹掉对 ../data/WAVE_ELLIOTT.js 的相对路径依赖。
    # 原因：产物在 out/ 下靠 ../data/ 取数，一旦移动目录或单独发送就白屏。内联后报告可随意流转。
    tpl = open(TPL, encoding="utf-8").read()
    inline = ("<script>\n/* 内联数据快照 生成于脚本运行时（自包含，无外部数据依赖） */\n"
              + dump_js(w)
              + "</script>")
    ref = '<script src="../data/WAVE_ELLIOTT.js"></script>'
    if ref in tpl:
        out_html = tpl.replace(ref, inline, 1)
    else:
        # 模板若改用了别的引用写法，回退为注入到 <head> 末尾之前，保证 window.WAVE_ELLIOTT 先于业务脚本
        out_html = tpl.replace("</head>", inline + "\n</head>", 1)
        if out_html == tpl:
            sys.exit("✗ 模板中既无 ../data/WAVE_ELLIOTT.js 引用也无 </head>，无法内联数据")

    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write(out_html)

    print("✓ 研报已生成（自包含，可单独移动/发送）：%s" % outp)
    print("  数据截至：%s（上证收 %s，%s%%）" % (date, meta.get("last"), meta.get("pct")))
    print("  序列：%d 交易日 | 浪型拐点 %d | 指数对照 %d"
          % (len(s["dates"]), len(w["marks"]), len(w["idx"])))
    print("  数据源：%s" % meta.get("source", "n/a"))
    print("  阿狸咪零 westock 依赖：git pull 最新 data/WAVE_ELLIOTT.js + 本脚本即可重出报告")


if __name__ == "__main__":
    main()
