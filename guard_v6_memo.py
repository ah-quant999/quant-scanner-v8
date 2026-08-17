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
     + iframe `src="v6_memo.html"`）。任一缺失即 FAIL 部署，阻断"丢失态"上线。
  3) 缓存击穿：iframe 的 src 必须带 `?v=<内容sha10>` 版本戳（与全站 data/*.js
     同口径，使用内容 sha 而非 mtime），强制 CDN 在内容变化时换 key 重新拉取，
     杜绝"origin 已修复但 CDN 仍吐旧/截断副本"的复发。

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
MIN_BYTES = 60000  # 当前 ~139KB；阈值取 ~43%，足以捕捉"被删/被清空/被截断"


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
    # 2026-08-17 支持两种渲染模式：iframe（旧）或 fetch() 注入（新，一劳永逸）
    has_iframe = 'src="v6_memo.html' in h
    has_fetch = ('__v6MemoLoad' in h) and ('v6MemoBody' in h)
    checks = {
        "子tab data-lg=\"v6\"": 'data-lg="v6"',
        "面板 id=\"lg-v6\"": 'id="lg-v6"',
        "v6 渲染入口(iframe 或 fetch)": None,  # 下面单独判
    }
    missing = []
    for k, v in list(checks.items())[:-1]:  # 跳过最后一项
        if v not in h:
            missing.append(k)
    if not has_iframe and not has_fetch:
        missing.append("v6 渲染入口(iframe src 或 __v6MemoLoad)")
    if missing:
        print("❌ index.html 缺失 v6备忘录 入口：%s —— 阻断部署" % "、".join(missing))
        ok = False
    else:
        mode = "fetch()注入" if has_fetch else "iframe"
        print("✅ index.html 保留 v6备忘录 子tab/面板/%s" % mode)

    # ── 3) 缓存击穿：版本戳 ─────────────────────────────────────
    new_sha = sha10_of(MEMO)
    if has_iframe:
        # 旧模式：更新 iframe src 的 ?v= 参数
        pat = re.compile(r'src="v6_memo\.html(?:\?v=[0-9a-fA-F]+)?"')
        m = pat.search(h)
        if not m:
            print("❌ 未在 index.html 找到 v6_memo.html 的 iframe src，阻断部署")
            sys.exit(1)
        new_src = 'src="v6_memo.html?v=%s"' % new_sha
        if m.group(0) != new_src:
            h2 = pat.sub(new_src, h, count=1)
            open(INDEX, "w", encoding="utf-8").write(h2)
            print("🔄 已更新 v6备忘录 iframe 缓存戳 → ?v=%s" % new_sha)
        else:
            print("✅ v6备忘录 iframe 缓存戳已是最新（?v=%s）" % new_sha)
    elif has_fetch:
        # 新模式：更新 __v6MemoLoad 内的 fetch URL ?v= 参数
        pat = re.compile(r"v6_memo\.html\?v=[0-9a-fA-F]+")
        m = pat.search(h)
        new_url = 'v6_memo.html?v=%s' % new_sha
        if m and m.group(0) != new_url:
            h2 = pat.sub(new_url, h, count=1)
            open(INDEX, "w", encoding="utf-8").write(h2)
            print("🔄 已更新 v6备忘录 fetch URL 缓存戳 → ?v=%s" % new_sha)
        else:
            print("✅ v6备忘录 fetch URL 缓存戳已是最新（?v=%s）" % new_sha)
    else:
        print("❌ 无 v6 渲染入口可更新缓存戳，阻断部署")
        sys.exit(1)

    if not ok:
        print("🚫 护栏失败：v6备忘录 入口缺失，已阻断部署。请先修复 index.html 再推送。")
        sys.exit(1)

    print("✅ 防覆盖护栏通过：v6备忘录 完整且已击穿缓存，允许部署。")
    sys.exit(0)


if __name__ == "__main__":
    main()
