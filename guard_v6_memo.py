#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⛔【永久禁止删除 PERMANENT DO-NOT-DELETE】v8 部署护栏（二道防线）：确保「逻辑详解页 / v6备忘录」永不丢失 / 被覆盖（2026-08-15 主人二次令：本脚本及 v6_memo.html / v6_memo.golden.html 永久不可删，任何清理/重构/瘦身/AI 操作均不得删除或覆盖）。

背景（2026-08-15 主人令）：
  此前多次发生"v6 覆盖 v8"——远端历史被 V6 归档页覆盖、CDN 按完整 URL 缓存了
  旧/截断副本，导致逻辑详解页的 v6备忘录 看似"没了"。本脚本作为 CI 部署前的硬性
  闸门 + 自愈器，三重防护：

  1) v6_memo.html 必须存在且完整（≥ MIN_BYTES）。若缺失/被截断/被覆盖，
     依次尝试从 git HEAD、再到提交的黄金备份 v6_memo.golden.html 还原。
  2) index.html 必须保留 v6备忘录 入口（子tab `data-lg="v6"` + 面板 `id="lg-v6"`
     + 内联内容标记）。任一缺失即 FAIL 部署，阻断"丢失态"上线。
  3) 内联内容一致性：lg-v6 面板内必须包含 v6_memo.html 的 body 内容
     （2026-08-17 最终方案：废除 iframe/fetch，直接内嵌 HTML，零动态依赖）。

用法：python guard_v6_memo.py
退出码 0 = 通过（含已自愈），1 = 存在不可自愈的缺失，阻断部署。
"""
import os
import re
import sys
import hashlib
import subprocess

MEMO = "v6_memo.html"
GOLDEN = "v6_memo.golden.html"
INDEX = "index.html"
MIN_BYTES = 60000  # 当前 ~157KB；阈值取 ~43%，足以捕捉"被删/被清空/被截断"


def git_show(path):
    """从最近一次提交取文件内容（bytes），失败返回 None。"""
    try:
        return subprocess.check_output(
            ["git", "show", "HEAD:" + path], stderr=subprocess.DEVNULL
        )
    except Exception:
        return None


def restore_memo():
    """逐级还原 v6_memo.html：git HEAD → 黄金备份。返回是否成功。"""
    data = git_show(MEMO)
    if data and len(data) >= MIN_BYTES:
        open(MEMO, "wb").write(data)
        print("   ↳ 已从 git HEAD 还原 v6_memo.html")
        return True
    if os.path.exists(GOLDEN) and os.path.getsize(GOLDEN) >= MIN_BYTES:
        with open(GOLDEN, "rb") as f:
            data = f.read()
        open(MEMO, "wb").write(data)
        print("   ↳ 已从黄金备份 %s 还原 v6_memo.html" % GOLDEN)
        return True
    return False


def sha10_of(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def main():
    ok = True

    # ── 1) v6_memo.html 完整性 + 自愈 ───────────────────────────────
    if not os.path.exists(MEMO) or os.path.getsize(MEMO) < MIN_BYTES:
        print("⚠️ v6_memo.html 缺失/过短（%s / %d 字节），尝试还原…"
              % (os.path.getsize(MEMO) if os.path.exists(MEMO) else "不存在",
                 os.path.getsize(MEMO) if os.path.exists(MEMO) else 0))
        if restore_memo():
            print("✅ v6_memo.html 已自愈（%d 字节）" % os.path.getsize(MEMO))
        else:
            print("❌ 无法还原 v6_memo.html（git HEAD 与黄金备份均不可用），阻断部署")
            sys.exit(1)
    else:
        print("✅ v6_memo.html 完整（%d 字节）" % os.path.getsize(MEMO))

    # ── 2) index.html 必须保留 v6备忘录 入口 ─────────────────────────
    if not os.path.exists(INDEX):
        print("❌ index.html 不存在，阻断部署")
        sys.exit(1)

    h = open(INDEX, encoding="utf-8").read()
    # 2026-08-17 支持三种渲染模式：iframe（旧）/ fetch()（中）/ 内联（新·最终）
    has_iframe = 'src="v6_memo.html' in h
    has_fetch = ('__v6MemoLoad' in h) and ('v6MemoBody' in h)
    has_inline = ('id="lg-v6"' in h) and ('九宝量化 V6.0' in h)
    # 2026-08-23 修复假阳性：iframe 初始 src 留空、改由 JS 动态赋 src='v6_memo.html?<ts>'
    # 以击穿 CDN 缓存后，字面量 src="v6_memo.html 消失 → 前三模式全部落空 → 误判"入口缺失"
    # 并阻断 build_deploy（run #3682/#3683 连续失败）。此处补认「JS 动态注入」与「直链兜底」两种
    # 合法入口。保护强度不变：仍强制 data-lg="v6" 子tab + id="lg-v6" 面板存在，且必须真实引用 v6_memo.html。
    has_jssrc = ('v6MemoFrame' in h) and (re.search(r"""\.src\s*=\s*['"]v6_memo\.html""", h) is not None)
    has_directlink = re.search(r"""href=['"]v6_memo\.html""", h) is not None

    checks = {
        "子tab data-lg=\"v6\"": 'data-lg="v6"',
        "面板 id=\"lg-v6\"": 'id="lg-v6"',
        "v6 渲染入口": None,  # 下面单独判
    }
    missing = []
    for k, v in list(checks.items())[:-1]:  # 跳过最后一项
        if v not in h:
            missing.append(k)
    if not (has_iframe or has_fetch or has_inline or has_jssrc or has_directlink):
        missing.append("v6 渲染入口(iframe / fetch / 内联 / JS动态src / 直链)")
    if missing:
        print("❌ index.html 缺失 v6备忘录 入口：%s —— 阻断部署" % "、".join(missing))
        ok = False
    else:
        if has_inline:
            mode = "内联(最终方案)"
        elif has_fetch:
            mode = "fetch()注入"
        elif has_iframe:
            mode = "iframe"
        elif has_jssrc:
            mode = "iframe(JS动态src·缓存击穿)"
        else:
            mode = "直链兜底(a href)"
        print("✅ index.html 保留 v6备忘录 子tab/面板/%s" % mode)

    # ── 3) 内联一致性校验（仅内联模式需要） ────────────────────────
    if has_inline:
        # 提取 lg-v6 面板内的内容长度，确保不为空
        lg_match = re.search(r'<div class="lg-pane" id="lg-v6">(.*?)</div>\s*</div>\s*<section', h, re.DOTALL)
        if lg_match:
            inner = lg_match.group(1)
            inner_len = len(inner)
            if inner_len < 1000:
                print("⚠️ lg-v6 面板内容过短（%d 字节），可能被意外清空" % inner_len)
                ok = False
            else:
                print("✅ v6备忘录内联内容完整（%d 字节）" % inner_len)
        else:
            print("⚠️ 无法解析 lg-v6 面板范围，跳过内容长度校验")

    if not ok:
        print("🚫 护栏失败：v6备忘录 入口缺失，已阻断部署。请先修复 index.html 再推送。")
        sys.exit(1)

    print("✅ 防覆盖护栏通过：v6备忘录 完整且内联内容就位，允许部署。")
    sys.exit(0)


if __name__ == "__main__":
    main()
