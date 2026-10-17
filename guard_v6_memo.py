#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⛔【永久禁止删除 PERMANENT DO-NOT-DELETE】v8 部署护栏：确保「v6备忘录 v6_memo.html」永不丢失 / 被覆盖（2026-08-15 主人二次令：本脚本及 v6_memo.html / v6_memo.golden.html 永久不可删，任何清理/重构/瘦身/AI 操作均不得删除或覆盖）。

背景（2026-08-15 主人令）：
  此前多次发生"v6 覆盖 v8"——远端历史被 V6 归档页覆盖、CDN 按完整 URL 缓存了
  旧/截断副本，导致 v6备忘录 看似"没了"。本脚本作为 CI 部署前的硬性闸门 + 自愈器。

🔴 2026-10-04 主人令（方案B）：
  v6备忘录 已从 logic.html 彻底迁出 —— 本护栏**不再要求 logic.html 承载任何 v6 入口**
  （旧版曾校验 logic.html 的 data-lg="v6" 子 tab + id="lg-v6" 面板 + v6 渲染入口，现全部废除）。
  保护锚点改为 v6_memo.html 本体：
    1) 存在 + 完整（≥ MIN_BYTES）；缺失/截断 → git HEAD → 黄金备份逐级自愈。
    2) 内容标识：必须含 v6 正文标记「九宝量化 V6.0」且以 </html> 收尾，
       防止被替换成占位空页 / 半截文件而"看着还在"。
  v6_memo.html / v6_memo.golden.html / 本脚本 三者仍为【永久禁止删除】核心资产。

用法：python guard_v6_memo.py
退出码 0 = 通过（含已自愈），1 = 存在不可自愈的缺失，阻断部署。
"""
import os
import sys
import hashlib
import subprocess

MEMO = "v6_memo.html"
GOLDEN = "v6_memo.golden.html"
INDEX = "index.html"
LOGIC = "logic.html"  # 2026-10-04 方案B 起已与 v6 解耦，此处仅作信息输出
MIN_BYTES = 60000     # 当前 ~161KB；阈值取 ~37%，足以捕捉"被删/被清空/被截断"
MEMO_BODY_MARKER = "九宝量化 V6.0"


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
    """v6_memo.html 的 ?v 口径：原始字节 sha1 前 10 位（与 reconcile_cache_busters 严格一致）。"""
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

    # ── 2) v6_memo.html 内容标识（方案B 新锚点：锚定本体，不再看 logic.html） ──
    with open(MEMO, encoding="utf-8", errors="replace") as f:
        memo_txt = f.read()
    if MEMO_BODY_MARKER not in memo_txt:
        print("❌ v6_memo.html 缺少 v6 正文标记「%s」——疑似被换成占位页，阻断部署"
              % MEMO_BODY_MARKER)
        ok = False
    elif "</html>" not in memo_txt[-512:]:
        print("❌ v6_memo.html 未以 </html> 收尾——疑似被截断，阻断部署")
        ok = False
    else:
        print("✅ v6_memo.html 含 v6 正文标记且完整收尾")

    # ── 3) 与 logic.html 的解耦状态（信息输出，不阻断部署） ──────────
    if os.path.exists(LOGIC):
        h = open(LOGIC, encoding="utf-8", errors="replace").read()
        if ('data-lg="v6"' in h) or ('id="lg-v6"' in h) or ("v6_memo.html" in h):
            print("ℹ️ logic.html 仍引用 v6 资产（方案B 已迁出；彻底解耦更佳，不阻断）")
        else:
            print("✅ logic.html 已与 v6 备忘录解耦（方案B 生效）")
    else:
        print("ℹ️ logic.html 不存在（本护栏不再要求它，跳过）")

    if os.path.exists(INDEX):
        with open(INDEX, encoding="utf-8", errors="replace") as f:
            hi = f.read()
        if "logic.html" in hi:
            print("✅ index.html 仍引用 logic.html（逻辑详解入口，页面本体已下架）")
        else:
            print("ℹ️ index.html 未引用 logic.html")
    else:
        print("ℹ️ index.html 不存在（软提示，不阻断）")

    if not ok:
        print("🚫 护栏失败：v6备忘录 本体缺失/损坏，已阻断部署。")
        sys.exit(1)

    print("✅ 防覆盖护栏通过：v6备忘录 本体完整（永久禁删资产在位），允许部署。")
    sys.exit(0)


if __name__ == "__main__":
    main()
