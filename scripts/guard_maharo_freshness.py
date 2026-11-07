#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观观测卡（window.MAHORO_INSIGHTS / data/maharo_insights.js）时效性与事实守卫。

🎯 修复背景（2026-11-08 主人令）：宏观观测卡曾出现两类硬伤——
  ① 时效性：11 月了，月解析仍停在「2026-10」、周解析停在「10/26–11/1」（不滚动）；
  ② 事实错误：把已退休的「鲍威尔」当现任美联储主席（写「鲍威尔记者会」）。
     真实情况：现任主席是凯文·沃什（Kevin Warsh），2026-05-22 宣誓就职、任期至 2030 年；
     鲍威尔主席任期 2026-05-15 已到期，仅留任理事至 2028-01。

本脚本作为「一劳永逸」拦截：任何一次运行若发现下列任一违规，退出码 1（供自动化告警/自纠）：
  V1. monthly.period 不等于当前 YYYY-MM（月解析没滚动到当月）；
  V2. weekly.period 不等于「本周（M/D–M/D）」当前周区间（周解析没滚动到本周）；
  V3. 文本中仍将鲍威尔当作主席引用（"鲍威尔记者会" / "主席鲍威尔" / "鲍威尔主席" / "美联储主席鲍威尔"）。
       注：鲍威尔 2028-01 前仍是理事，纯「理事鲍威尔」合法；本脚本只拦「主席语境」误用。

用法：
  python3 scripts/guard_maharo_freshness.py [--file data/maharo_insights.js]
退出：0 = 通过；1 = 存在违规（打印明细）。
"""
import sys, os, re, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILE = os.path.join(ROOT, "data", "maharo_insights.js")

# 鲍威尔被当作主席引用的非法模式（仅拦「主席语境」，理事语境放行）
POWELL_CHAIR_PATTERNS = [
    "鲍威尔记者会",
    "主席鲍威尔",
    "鲍威尔主席",
    "美联储主席鲍威尔",
]


def load_maharo(path):
    src = open(path, encoding="utf-8").read()
    m = re.match(r"^\s*window\.(\w+)\s*=\s*", src)
    if not m:
        raise RuntimeError("无法识别 window.XXX = 结构: %s" % path)
    body = src[m.end():].rstrip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def week_range_str(today=None):
    """返回当前周 周一~周日 的 'M/D–M/D' 表示（与卡片格式一致，无前导零、en-dash）。"""
    today = today or datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())  # weekday() 0=周一
    sunday = monday + datetime.timedelta(days=6)
    return "%d/%d–%d/%d" % (monday.month, monday.day, sunday.month, sunday.day)


def _ensure_utf8_output():
    """Windows 下 stdout/stderr 默认 GBK，emoji(🛡/✅/⚠️/❌)会 UnicodeEncodeError 导致脚本崩溃、
    退出码失真（假阳性）。统一切 UTF-8，确保脚本在任意编码环境都能正常打印与返回真实退出码。"""
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8")
            except Exception:
                pass


def main():
    _ensure_utf8_output()
    path = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else DEFAULT_FILE
    if not os.path.isfile(path):
        print("❌ 文件不存在: %s" % path)
        return 1

    try:
        d = load_maharo(path)
    except Exception as e:
        print("❌ 解析失败: %s" % e)
        return 1

    today = datetime.date.today()
    cur_month = "%04d-%02d" % (today.year, today.month)
    cur_week = week_range_str(today)
    violations = []

    # V1: 月解析滚动
    mp = (d.get("monthly") or {}).get("period", "")
    if mp != cur_month:
        violations.append("V1 月解析未滚动: period='%s' 应为 '%s'" % (mp, cur_month))

    # V2: 周解析滚动
    wp = (d.get("weekly") or {}).get("period", "")
    exp_week = "本周（%s）" % cur_week
    if wp != exp_week:
        violations.append("V2 周解析未滚动: period='%s' 应为 '%s'" % (wp, exp_week))

    # V3: 鲍威尔主席语境误用
    blob = json.dumps(d, ensure_ascii=False)
    hits = [p for p in POWELL_CHAIR_PATTERNS if p in blob]
    if hits:
        violations.append("V3 鲍威尔被当作主席引用（非法模式）: %s ｜ 现任主席应为凯文·沃什(Kevin Warsh)" % "、".join(hits))

    # 报告
    print("🛡 宏观观测卡守卫 · %s" % today.isoformat())
    print("   update_time = %s" % d.get("update_time"))
    print("   当前月 = %s ｜ 当前周 = %s" % (cur_month, exp_week))
    print("   monthly.period = %s" % mp)
    print("   weekly.period  = %s" % wp)
    if not violations:
        print("✅ 守卫通过：周期已滚动到当月/本周，且无鲍威尔主席语境误用。")
        return 0
    print("⚠️ 守卫发现 %d 项违规：" % len(violations))
    for v in violations:
        print("   - " + v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
