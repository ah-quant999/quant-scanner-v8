#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safe_batch_commit.py — 批量提交链前置对齐守卫（协议机件，非一次性脚本）
================================================================================
主人令（2026-11-20）：「加！不要一直被覆盖！」

根因（2026-11-20 01:51 实证事故，8760 文件怪物提交）：
  持久工作区（cn runner 残留旧 clone / 交接档·心跳链 / 夜班批量提交链）**从不 pull 就整批
  add+commit+push** → 落后基线上 rebase 把旧内容重放成新提交 → 覆盖 Contents API 单文件
  推送的新版（stock_names/resonance_track 被盖回 11-11，parity 拦截立功才没上线）。

三道闸（缺一不可，双机同规）：
  闸① 提交前强制对齐：fetch + 落后即 pull --rebase --autostash；对齐失败 exit 1
       —— **绝不带旧树提交**（落后基线 rebase = 旧内容重放，事故机制本体）。
  闸② 数据文件时间戳否决：data/ raw_data/ 下与远端有差异的文件，比对
       update_time/generated/data_date，本地更旧 ⇒ 丢弃本地取远端
       （防「本地文件被碰过但内容旧」——2026-11-20 parity 拦截的同类场景）。
  闸③ push 失败 fetch+rebase 重试 3 次（并发互踩常规姿势，与 algo_intraday_lite 同款）。

用法（所有批量提交链一律经本脚本提交，禁裸 git add -A + commit + push）：
  python algorithms/safe_batch_commit.py --msg "..." [--paths data/ raw_data/ ...]
    --paths 省略 = 整树（等价 add -A；密钥/缓存摘除由调用链先行自行处理，本脚本不越权）
  --dry  只跑闸①②并打印将提交的清单，不提交不推送（演练/体检用）
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIME_KEY_RE = re.compile(
    r'"?(update_time|generated|data_date|generated_at|updateTime)"?\s*[:=]\s*"?([^",\n\r}]+)"?'
)
DATA_DIRS = ("data/", "raw_data/")


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败 rc={r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def data_ts(text):
    """取顶层权威时间戳（首个命中，键优先级 update_time > generated > data_date > generated_at）。
    ISO 风格字符串可直接字典序比较；无 ⇒ None。
    （不取 max：行级时间戳噪声会把整文件判新，2026-11-20 单测实证）"""
    for key in ("update_time", "generated", "data_date", "generated_at", "updateTime"):
        m = re.search(r'"?' + key + r'"?\s*[:=]\s*"?([^",\n\r}]+)"?', text)
        if m:
            return m.group(1).strip().strip("'\"")
    return None


def blob_of(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--msg", required=True)
    ap.add_argument("--paths", nargs="*", default=None,
                    help="待提交路径（目录或文件）；省略=整树")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    # ── 闸① 提交前强制对齐 ──────────────────────────────────────────────
    git("fetch", "origin", "main")
    behind = git("rev-list", "--count", "HEAD..origin/main", check=False)
    if behind and behind != "0":
        print(f"⚠️ 本地落后 origin/main {behind} 笔 → 强制 pull --rebase --autostash 对齐")
        r = subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"❌ 对齐失败（绝不带旧树提交）：{r.stderr.strip()[:400]}")
            print("   处置：人工解决冲突后重跑；禁止绕过本守卫直接 commit")
            sys.exit(1)
        print("✅ 已对齐到 origin/main 最新")

    # ── 闸② 数据文件时间戳否决 ──────────────────────────────────────────
    # 注意：porcelain 行首是状态码空格，不能用 .strip() 后的输出（会吃掉行首空格导致路径错位）
    raw = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stdout
    changed = [l for l in raw.splitlines() if l.strip()]
    candidates = []
    for line in changed:
        st, path = line[:2], line[3:].strip().strip('"')
        if st == "D " or st == "D":          # 显式删除不否决
            candidates.append(path)
            continue
        candidates.append(path)
    vetoed, kept = [], []
    for path in candidates:
        if not path.startswith(DATA_DIRS):
            kept.append(path)
            continue
        local_p = ROOT / path
        if not local_p.is_file():
            kept.append(path)
            continue
        try:
            local_ts = data_ts(local_p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            local_ts = None
        remote_ts = data_ts(blob_of("origin/main", path) or "")
        if local_ts and remote_ts and local_ts < remote_ts:
            git("checkout", "origin/main", "--", path)
            vetoed.append(f"{path} (本地{local_ts} < 远端{remote_ts})")
        else:
            kept.append(path)
    for v in vetoed:
        print(f"🛑 陈旧否决：{v}")
    if not kept:
        print("⏭️ 对齐+否决后无任何待提交变更")
        return

    # ── 提交 + 闸③ push 重试 ────────────────────────────────────────────
    if a.dry:
        print(f"[dry] 将提交 {len(kept)} 个文件（前 10 个）:")
        for p in kept[:10]:
            print("   ", p)
        return
    if a.paths:
        git("add", "--", *a.paths)
    else:
        git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        print("⏭️ 暂存区无变化，跳过提交")
        return
    git("commit", "-m", a.msg)
    for i in range(1, 4):
        r = subprocess.run(["bash", "v8_git_push.sh", "origin", "HEAD:main"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print(f"✅ 已推送（第 {i} 次）：{a.msg}")
            return
        print(f"⚠️ push 被拒，fetch+rebase 后重试 ({i}/3)")
        subprocess.run(["git", "checkout", "--", "."], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "-c", "rebase.autoStash=true", "rebase", "FETCH_HEAD"],
                       cwd=ROOT, capture_output=True)
    print("❌ 3 次重试后仍失败（本批已 commit 在本地，未推上；请人工核查）")
    sys.exit(1)


if __name__ == "__main__":
    main()
