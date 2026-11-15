#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观观测卡（window.MAHORO_INSIGHTS / data/maharo_insights.js）时效性与事实守卫。

🎯 修复背景（2026-11-08 主人令）：宏观观测卡曾出现两类硬伤——
  ① 时效性：11 月了，月解析仍停在「2026-10」、周解析停在「10/26–11/1」（不滚动）；
  ② 事实错误：把已退休的「鲍威尔」当现任美联储主席（写「鲍威尔记者会」）。
     真实情况：现任主席是凯文·沃什（Kevin Warsh），2026-05-22 宣誓就职、任期至 2030 年；
     鲍威尔主席任期 2026-05-15 已到期，仅留任理事至 2028-01。

🔒 2026-11-15 一劳永逸补强（周/月解析丢失事故）：
  fc14d156 提交把 maharo_insights.js 从 daily+compare+weekly+monthly 重写成只剩 daily，
  前端 renderMahoroCard 对缺失块静默 return → 「本周解析/本月解析」整块消失。
  修复=周/月与 daily 解耦，独立种子库 data/maharo_wm.js（window.MAHORO_WM）作权威副本；
  前端与守卫都按「insights 优先、WM 兜底」的组合口径判定。
  新增 V4/V5：daily 缺失、或 weekly/monthly 在两源都无效 → 直接拦截，杜绝残稿上线。

本脚本作为「一劳永逸」拦截：任何一次运行若发现下列任一违规，退出码 1（供自动化告警/自纠）：
  V1. monthly.period 不等于当前 YYYY-MM（月解析没滚动到当月）；
  V2. weekly.period 不等于「本周（M/D–M/D）」当前周区间（周解析没滚动到本周）；
  V3. 文本中仍将鲍威尔当作主席引用（"鲍威尔记者会" / "主席鲍威尔" / "鲍威尔主席" / "美联储主席鲍威尔"）。
       注：鲍威尔 2028-01 前仍是理事，纯「理事鲍威尔」合法；本脚本只拦「主席语境」误用。
  V4. daily 缺失或无 text（主稿结构完整性）；
  V5. weekly / monthly 在 insights 与 MAHORO_WM 种子库两处都缺 text（周/月解析整块丢失）。

用法：
  python3 scripts/guard_maharo_freshness.py                       # 组合校验 insights + wm（推荐，发布闸门用）
  python3 scripts/guard_maharo_freshness.py --file <某文件.js>    # 单文件校验（兼容旧调用）
退出：0 = 通过；1 = 存在违规（打印明细）。
"""
import sys, os, re, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILE = os.path.join(ROOT, "data", "maharo_insights.js")
WM_FILE = os.path.join(ROOT, "data", "maharo_wm.js")

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


def has_text(block):
    """块存在且含非空 text。"""
    return bool(isinstance(block, dict) and str(block.get("text") or "").strip())


def main():
    _ensure_utf8_output()
    single = "--file" in sys.argv
    path = sys.argv[sys.argv.index("--file") + 1] if single else DEFAULT_FILE
    if not os.path.isfile(path):
        print("❌ 文件不存在: %s" % path)
        return 1

    try:
        d = load_maharo(path)
    except Exception as e:
        print("❌ 解析失败: %s" % e)
        return 1

    # 组合模式：加载独立周/月种子库作兜底（与前端 renderMahoroCard 口径一致）
    wm = {}
    if not single and os.path.isfile(WM_FILE):
        try:
            wm = load_maharo(WM_FILE)
        except Exception as e:
            print("⚠️ 种子库 %s 解析失败（将按无兜底处理）: %s" % (WM_FILE, e))

    today = datetime.date.today()
    cur_month = "%04d-%02d" % (today.year, today.month)
    cur_week = week_range_str(today)
    violations = []

    # V4: 主稿 daily 结构完整性
    daily = d.get("daily")
    if not has_text(daily):
        violations.append("V4 daily 缺失或无 text（主稿结构不完整）")

    # 组合口径：weekly/monthly 取 insights 优先，缺失则回退种子库
    def pick(k):
        a = d.get(k)
        if has_text(a):
            return a, "insights"
        b = wm.get(k)
        if has_text(b):
            return b, "WM种子库"
        return {}, "无"

    monthly, monthly_src = pick("monthly")
    weekly, weekly_src = pick("weekly")

    # V5: weekly/monthly 在两源都无效 → 整块丢失
    if not has_text(weekly):
        violations.append("V5 weekly 在 insights 与 MAHORO_WM 两处均无有效 text（本周解析整块丢失）")
    if not has_text(monthly):
        violations.append("V5 monthly 在 insights 与 MAHORO_WM 两处均无有效 text（本月解析整块丢失）")

    # V1: 月解析滚动
    mp = (monthly or {}).get("period", "")
    if mp != cur_month:
        violations.append("V1 月解析未滚动: period='%s' 应为 '%s'（来源=%s）" % (mp, cur_month, monthly_src))

    # V2: 周解析滚动
    wp = (weekly or {}).get("period", "")
    exp_week = "本周（%s）" % cur_week
    if wp != exp_week:
        violations.append("V2 周解析未滚动: period='%s' 应为 '%s'（来源=%s）" % (wp, exp_week, weekly_src))

    # V3: 鲍威尔主席语境误用（合并两源文本）
    blob = json.dumps(d, ensure_ascii=False) + json.dumps(wm, ensure_ascii=False)
    hits = [p for p in POWELL_CHAIR_PATTERNS if p in blob]
    if hits:
        violations.append("V3 鲍威尔被当作主席引用（非法模式）: %s ｜ 现任主席应为凯文·沃什(Kevin Warsh)" % "、".join(hits))

    # 报告
    print("🛡 宏观观测卡守卫 · %s · 模式=%s" % (today.isoformat(), "单文件" if single else "组合(insights+WM)"))
    print("   update_time = %s" % d.get("update_time"))
    print("   当前月 = %s ｜ 当前周 = %s" % (cur_month, exp_week))
    print("   daily    : %s" % ("有效" if has_text(daily) else "缺失"))
    print("   monthly  : period=%s（来源=%s）" % (mp, monthly_src))
    print("   weekly   : period=%s（来源=%s）" % (wp, weekly_src))
    if not violations:
        print("✅ 守卫通过：daily 完整、周/月双源齐备且已滚动到当月/本周，无鲍威尔主席语境误用。")
        return 0
    print("⚠️ 守卫发现 %d 项违规：" % len(violations))
    for v in violations:
        print("   - " + v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
