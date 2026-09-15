#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 部署护栏：上线前校验 index.html 关键板块未被误删/清空。

防止后患（2026-08-02 起因）：
  此前一次"按时间点回滚到 8 点前"把 sec-st / sec-ph 两个大板块退回到了
  当天上午修复前的半成品状态，导致线上卡片全变 '--'/空壳，看似"页面没了"。
  根因是：回滚目标是一个 TIME 基线而非 KNOWN-GOOD 提交，且该基线正处于
  开发中的修复前状态。

  本脚本作为 CI 部署前的硬性闸门：任何会把以下关键板块删除或清空的提交
  （回滚失误 / 自动化重构 / 手滑）都会在部署前 FAIL，阻断上线，避免"大页面
  没了"再次静默发生。

用法：python guard_index_sections.py
退出码 0 = 通过，1 = 存在缺失/清空，阻断部署。
"""
import os
import re
import sys

INDEX = "index.html"

# 必须存在且内容不可过短（字符数下界）的板块。
# 阈值取当前实测长度的约 20%-25%，足以捕捉"被删/被清空"，又不会因版本正常
# 增减（如某卡片精简）而误报。实测：sec-st≈16774 / sec-ph≈6277 / sec-rc≈数千。
REQUIRED_SECTIONS = {
    "sec-st": 3000,   # 🎯 选股策略
    "sec-ph": 1200,   # 🌙 盘后数据（2026-08-29 轻量化后仅保留板块资金三合一）
    "sec-rc": 1500,   # 📊 共振日历
}

# 必须存在的独立容器 id（非整段 section，仅校验 id 存在）。
# 注意：hmUpdateTime（完整热力矩阵）是用户刻意未恢复的，不纳入守护。
# 注意：alertScanTime（系统告警）随动态监控区一起被用户删除，不纳入守护。
# 体积上限（2026-08-08 新增）：防止数据被内联回 index.html 导致巨型化。
# 当前正常值约 680KB（~10K 行），阈值留 2 倍余量。
# 上次 6.8MB 巨型化的根因就是某次部署把 data/*.js 内联进 index.html，
# 而旧版护栏只查下界不查上界，反而"越大越通过"放行了。
MAX_INDEX_BYTES = 1_250_000  # 1.25 MB

REQUIRED_IDS = [
    "conceptMapTime",   # 概念资金热力图（treemap）
]


def find_section(h, sid):
    """script-aware 查找 <section id="sid"> 的闭合块。"""
    i = h.find('id="%s"' % sid)
    if i < 0:
        return None
    s = h.rfind("<section", 0, i)
    if s < 0:
        return None
    depth = 0
    j = s
    n = len(h)
    in_sc = False
    while j < n:
        if in_sc:
            e = h.find("</script>", j)
            if e == -1:
                break
            j = e + len("</script>")
            in_sc = False
            continue
        o = h.find("<section", j)
        sc = h.find("<script", j)
        cc = h.find("</section>", j)
        if sc != -1 and (sc < o or o == -1) and (sc < cc or cc == -1):
            j = sc + len("<script>")
            in_sc = True
            continue
        if cc == -1:
            break
        if o != -1 and o < cc:
            depth += 1
            j = o + len("<section")
        else:
            depth -= 1
            j = cc + len("</section>")
            if depth == 0:
                return h[s:j]
    return None


def main():
    if not os.path.exists(INDEX):
        print("❌ %s 不存在，无法校验" % INDEX)
        sys.exit(1)
    h = open(INDEX, encoding="utf-8").read()
    ok = True

    for sid, minlen in REQUIRED_SECTIONS.items():
        b = find_section(h, sid)
        if b is None:
            print("❌ 板块 <section id=\"%s\"> 缺失！" % sid)
            ok = False
        elif len(b) < minlen:
            print("⚠️ 板块 %s 内容过短（%d < %d 字符），疑似被清空/截断"
                  % (sid, len(b), minlen))
            ok = False
        else:
            print("✅ %s 存在（%d 字符）" % (sid, len(b)))

    for cid in REQUIRED_IDS:
        if ("id=\"%s\"" % cid) in h or ("id='%s'" % cid) in h:
            print("✅ 容器 id=%s 存在" % cid)
        else:
            print("⚠️ 关键容器 id=%s 缺失（概念热力图）" % cid)
            ok = False

    # 体积上限校验（防巨型化复发）
    _fsize = os.path.getsize(INDEX)
    if _fsize > MAX_INDEX_BYTES:
        print("❌ index.html 体积超标（%d 字节 / %.1f MB > 阈值 %.1f MB）！"
              % (_fsize, _fsize / 1048576.0, MAX_INDEX_BYTES / 1048576.0))
        print("   可能原因：data/*.js 被内联回 index.html。请检查构建流程，确保数据外置。")
        ok = False
    else:
        print("✅ 体积正常（%d 字节 / %.1f MB，上限 %.1f MB）"
              % (_fsize, _fsize / 1048576.0, MAX_INDEX_BYTES / 1048576.0))

    if not ok:
        print("🚫 护栏失败：关键板块缺失/清空或体积超标，已阻断部署。请先修复再推送。")
        sys.exit(1)
    print("✅ 护栏通过：关键板块齐全且体积正常，允许部署。")
    sys.exit(0)


if __name__ == "__main__":
    main()
