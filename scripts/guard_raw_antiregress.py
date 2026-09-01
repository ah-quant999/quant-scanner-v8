#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""推送前「反回归闸门」：防止用本地旧副本覆盖 origin/main 上更新的 raw_data。

背景（2026-09-01 事故原型）
--------------------------
本机全时段兜底自动化的推送步骤是 `git add raw_data/` —— 无差别暂存。
当本机工作树某个 raw_data 文件【比 origin/main 旧】时（典型成因：该文件由云端
workflow 抓取推送，本机 cloud_fetch_v8.py 不覆盖它，本机副本长期停在过去），
下一次 `git add raw_data/ && git push` 就会用旧副本【覆盖线上更新的数据】，
造成静默数据回滚。
实例：raw_data/avg_price_data.json 由云端 v8_cn_fetch_cloud.yml 在 11:28 抓到
date=2026-09-01 并推送；本机副本仍停在 2026-08-31。若按原流程推送即回滚。

闸门逻辑
--------
1. `git fetch origin main`
2. 取 `git diff --name-only origin/main -- raw_data/` = 本地与远端有差异的文件
3. 逐个提取【内容内部时间戳】（优先级：update_time > gen_time > republish_time >
   as_of > date > 正文首个 ISO 日期；取不到则跳过该文件）
4. 本地时间戳 < 远端时间戳 → 判定 REGRESSION（本地更旧）
   - 默认 dry-run 只报告
   - `--apply` 时执行 `git checkout origin/main -- <path>`，让该文件与远端一致
     （内容相同 → `git diff` 不再显示 → 不会被后续 `git add` 暂存，天然免回滚）
5. **任何异常一律 fail-open（退出码 0）**：闸门只做保护，绝不阻断主流程。

用法
----
    python scripts/guard_raw_antiregress.py            # dry-run 报告
    python scripts/guard_raw_antiregress.py --apply    # 真正恢复本地更旧的文件
    python scripts/guard_raw_antiregress.py --verbose  # 打印每个文件的时间戳对比
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS_KEYS = ("update_time", "gen_time", "republish_time", "as_of", "date",
           "trade_date", "snapshot_time", "fetch_time")
ISO_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})"
                    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?")


def git(args: list[str], text: bool = True):
    r = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True,
                       text=text, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def norm_ts(s: str) -> str | None:
    """把各种时间写法归一成可字典序比较的 'YYYYMMDDHHMMSS'。"""
    if not s:
        return None
    s = str(s).strip()
    m = ISO_RE.search(s)
    if not m:
        return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4) or 0)
    mi = int(m.group(5) or 0)
    ss = int(m.group(6) or 0)
    return "%s%02d%02d%02d%02d%02d" % (y, mo, d, hh, mi, ss)


def extract_ts(content: str) -> str | None:
    """优先读结构化字段的时间戳；退化时正则扫正文。"""
    if not content:
        return None
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            for k in TS_KEYS:
                v = obj.get(k)
                if isinstance(v, (str, int, float)):
                    ts = norm_ts(str(v))
                    if ts:
                        return ts
    except Exception:
        pass
    return norm_ts(content[:4000])


def main() -> int:
    apply_fix = "--apply" in sys.argv
    verbose = "--verbose" in sys.argv or not apply_fix

    rc, _, err = git(["fetch", "origin", "main"])
    if rc != 0:
        print("[gate] fetch 失败，fail-open 跳过闸门:", err[:200])
        return 0

    rc, out, err = git(["diff", "--name-only", "origin/main", "--", "raw_data/"])
    if rc != 0:
        print("[gate] diff 失败，fail-open 跳过闸门:", err[:200])
        return 0

    files = [f.strip() for f in out.splitlines() if f.strip()]
    if not files:
        print("[gate] raw_data 与 origin/main 无差异，无需检查")
        return 0

    regressions: list[str] = []
    checked = 0
    skipped = 0

    for f in files:
        local_path = ROOT / f
        try:
            local = local_path.read_text(encoding="utf-8", errors="replace") \
                if local_path.exists() else ""
        except Exception:
            local = ""
        rc2, remote, _ = git(["show", "origin/main:%s" % f])
        if rc2 != 0:
            remote = ""

        ts_l = extract_ts(local)
        ts_r = extract_ts(remote)
        if not ts_l or not ts_r:
            skipped += 1
            if verbose:
                print("  [skip] %-42s local=%s remote=%s" % (f, ts_l, ts_r))
            continue

        checked += 1
        if ts_l < ts_r:
            regressions.append(f)
            print("  [REGRESSION] %-42s 本地 %s < 远端 %s" % (f, ts_l, ts_r))
        elif verbose:
            print("  [ok]         %-42s 本地 %s >= 远端 %s" % (f, ts_l, ts_r))

    print("[gate] 检查 %d / 跳过(无时间戳) %d / 回归 %d"
          % (checked, skipped, len(regressions)))

    if regressions and apply_fix:
        for f in regressions:
            rc3, _, e3 = git(["checkout", "origin/main", "--", f])
            print("  [apply] %s -> %s" % (f, "已恢复为远端版本" if rc3 == 0 else ("失败:" + e3[:120])))
        # 收尾归位：checkout 会把文件【暂存】，残留的 staged 条目正是「陈旧暂存区地雷」。
        # 【2026-09-01 根治·数据回滚地雷复发】原实现为
        #     git fetch origin main && git reset -q --mixed origin/main
        #   ✗ 致命：`reset --mixed <commit>` 会**连同 HEAD 一起移动**到 origin/main，
        #     而工作树一个字节不动（注释误以为"只动索引"）→
        #     HEAD/索引跑到最新、工作树停在旧状态，git status 暴出 200+ 个
        #     「已修改」的**旧版本**文件（2026-09-01 11:31 实测 218 个 / -114,584 行），
        #     此时任何 `git add -A && commit` 都会造成整站数据回滚 + 文件被删。
        #   ✓ 正确做法：**只取消本次 checkout 产生的暂存，绝不移动 HEAD**。
        #     索引回到 HEAD → staged 恒为 0；工作树保留刚拉回的远端新版本，
        #     后续 `git add raw_data/` 暂存的是**新**内容，天然免回滚。
        # 同源先例：sync_westock_portfolio.py 已于 2026-08-24 用同样思路修过同一地雷。
        git(["reset", "-q", "HEAD", "--"] + regressions)
        _, staged, _ = git(["diff", "--cached", "--name-only"])
        n_staged = len([x for x in staged.splitlines() if x.strip()])
        print("  [apply] 索引已归位，残留 staged 条目 = %d" % n_staged)
    elif regressions:
        print("[gate] dry-run：以上文件本地更旧，加 --apply 可恢复为远端版本")

    return 0  # 永远 fail-open


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # 闸门自身异常绝不阻断主流程
        print("[gate] 异常，fail-open:", repr(exc)[:200])
        sys.exit(0)
