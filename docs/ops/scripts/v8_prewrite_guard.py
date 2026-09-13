#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_prewrite_guard.py —— 改动热文件**之前**的基线校验闸（防「整文件快照覆盖」）。

■ 解决什么（2026-09-13 实测事故：既有两道闸都防不住的那一类）
  `atomic_patch_push.py` 的「FETCH_HEAD 派生 + 锚点唯一性断言 + 快进推」能防
  **补丁式改动**的覆盖；`v8_session.py` 登记器能防**语义撞车**（两会话重复犯错）。
  但两者都防不住**整文件快照推送**：

    实测 `a40abe2ec`（新周期判定卡从宏观页下沉到观测类）把 `2b189bf7` 刚推的
    三处 `index.html` 口径文案**静默还原为旧版** —— 读 `origin/main` blob 实证：
      改前 `零样本长档在上层被过滤掉`=1 / `每卡必须恰好 1 行`=1
      改后 两者=0，而旧文案 `（三重共识只有 T+20）` / `rows 仅 3 行` 各复活=1。
    🔴 且其 parent `13baae49c` **确实含** `2b189bf7`
      （`git merge-base --is-ancestor 2b189bf7 a40abe2ec^` = 是）
      ⇒ **不是 commit 图落后**，而是**文件内容取自另一个会话的旧工作副本**。
      git 按整文件快照生效 ⇒ **不报冲突、不报警**（最危险的一类）。

  `cat-2` 会话亦实证：该会话期间 0 次 git 操作即推了 `push_theme_batch.py`，
  `git add <file>` 加入的是**基线很旧**的文件 —— 同因。

■ 三道闸的分工（互补，缺一有洞）
  | 闸 | 防什么 | 时机 |
  |---|---|---|
  | 锚点唯一性断言（`atomic_patch_push.py`） | 补丁式改动的覆盖 | 推时 |
  | `v8_session.py` 登记器 | 语义撞车（重复结论/重复犯错） | 开工 / 落笔 |
  | **本脚本** | **整文件快照覆盖**（基于旧副本整体覆盖） | **改动前 + 推前** |

■ 用法
  python docs/ops/scripts/v8_prewrite_guard.py --files index.html,logic.html
  python docs/ops/scripts/v8_prewrite_guard.py --files index.html --staged

■ 退出码
  0 = 基线新鲜（可改/可推）   2 = 🔴 疑似旧副本（须先同步基线）   3 = 参数/环境错误
"""
import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
FRESH_MIN = 30      # 窗口内远端动过而本机未同步 ⇒ 判「基线可能陈旧」
HOT_FILES = ["index.html", "logic.html", ".github/workflows/", ".github/scripts/",
             "raw_data/"]


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True)


def blob(repo, ref_path):
    """取 ref_path 的**原始字节**（不能走 text=True，否则行尾会被翻译）。"""
    p = subprocess.run(["git", "-C", repo, "show", ref_path], capture_output=True)
    return p.stdout if p.returncode == 0 else None


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description="v8 改动前基线校验闸（防整文件快照覆盖）")
    ap.add_argument("--repo", default=os.environ.get("V8_REPO", r"E:\workspace\stock-scanner"))
    ap.add_argument("--files", required=True, help="逗号分隔的相对路径")
    ap.add_argument("--fresh-min", type=int, default=FRESH_MIN)
    ap.add_argument("--staged", action="store_true",
                    help="核验「已暂存进 index 的内容」vs 远端（推前用）")
    a = ap.parse_args()

    repo = a.repo
    rels = [x.strip().replace("\\", "/") for x in a.files.split(",") if x.strip()]
    if not rels:
        print("no files")
        return 3

    print("=" * 68)
    print("v8 改动前基线校验闸   repo=%s" % repo)
    print("=" * 68)

    f = git(repo, "fetch", "origin", "main", "-q")
    if f.returncode != 0:
        print("❌ fetch 失败: %s" % f.stderr.strip()[:200])
        return 3
    print("远端 tip = %s" % git(repo, "rev-parse", "origin/main").stdout.strip()[:9])

    stale = []
    for rel in rels:
        print("-" * 68)
        print("文件: %s" % rel)
        rb = blob(repo, "origin/main:%s" % rel)
        if rb is None:
            print("  ⚠️ 远端无此文件（新增文件）⇒ 无基线可比，跳过")
            continue
        lt = git(repo, "log", "-1", "--format=%cI", "origin/main", "--", rel).stdout.strip()
        print("  远端内容指纹 = %s   最后改动 = %s" % (sha(rb), lt or "?"))

        if a.staged:
            lb = subprocess.run(["git", "-C", repo, "cat-file", "-p", ":%s" % rel],
                                capture_output=True).stdout
            src = "git index（即将提交）"
            if not lb:
                print("  ⚠️ index 中无 %s（可能未 add）⇒ 跳过" % rel)
                continue
        else:
            p = os.path.join(repo, rel.replace("/", os.sep))
            if not os.path.isfile(p):
                print("  ⚠️ 工作区无此文件 ⇒ 跳过")
                continue
            with open(p, "rb") as fh:
                lb = fh.read()
            src = "工作区文件"
        print("  %s 指纹 = %s" % (src, sha(lb)))
        print("  ✅ 与远端一致" if sha(lb) == sha(rb)
              else "  ❌ **与远端不一致** ⇒ 整文件推送将覆盖远端的这些改动")

        try:
            age = (datetime.now(CST) - datetime.fromisoformat(lt)).total_seconds() / 60.0
        except Exception:
            age = None
        if age is not None and age <= a.fresh_min:
            print("  🔴 远端 %.0f 分钟前刚改过（窗口 %d 分钟）"
                  "⇒ **改动前必须先同步基线**" % (age, a.fresh_min))
            stale.append(rel)
        elif age is not None:
            print("  🟢 远端最后改动距今 %.0f 分钟（超出新鲜度窗口）" % age)

    print("=" * 68)
    if stale:
        print("🔴 结论：%d 个文件基线可能陈旧 ⇒ **不要整文件覆盖**" % len(stale))
        print("   1) git show origin/main:<file> 先看对方改成了什么")
        print("   2) 用补丁式改动（锚点断言）而非整文件快照；或在最新基线上重做")
        print("   3) 推前再跑 --staged，确认 index 内容已含对方改动")
        return 2
    print("🟢 结论：基线新鲜，可继续（推前仍建议再跑一次 --staged）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
