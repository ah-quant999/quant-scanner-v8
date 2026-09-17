# -*- coding: utf-8 -*-
"""v8 工作区一致性守卫 —— 跑批前的 fail-closed 前置检查 + 自动拉齐。

■ 为什么要它（2026-09-13 本机实测根因）
  本机 `E:\\workspace\\stock-scanner` 的工作区内容，会被坚果云从**另一台机**同步过来，
  因此**经常与远端 HEAD 不一致**（本机 HEAD 也落后，`git status` 双双静默）。
  而 `update_v8.py` / `algorithms/run_algorithms.py` 是**直接跑工作区里那份脚本**的。
  ⇒ 远端已经修好的代码，会在本机跑批时被**从产物侧静默撤销**（典型「假成功」）。

  实测证据（2026-09-13 12:5x）：
  · 本机 `algorithms/strategy_four_volume.py` 仍是「多信号路径首尾拼接累加」的旧回撤算法，
    而远端 `FETCH_HEAD` 已是「逐信号峰谷再取均值」；
  · 抽查 6 个关键文件，`git hash-object --no-filters` 与 `git rev-parse FETCH_HEAD:<f>`
    **6/6 全部不等**；
    〔2026-09-14 按语〕上面那次抽查用的是**当时的** `--no-filters` 口径；该口径已被证伪并
    改为 filter-aware 的 `--path`（见 `_worktree_blob` 注释）—— 上面 6/6 全不等的结论
    在当时那个「本机代码确实落后」的场景下成立，但 `--no-filters` 会把**行尾差异**
    误判成代码落后（index.html 恒不齐即由此而来）。
  · 于是本机 E 批（12:58 写 `backtest_all_algos.json`）产出的
    `max_drawdown` 会重新出现 −100% 以下的量纲错误值。

■ 它做什么
  1. `git fetch origin main`（失败则退回本地 `refs/remotes/origin/main`，不因此中断）；
  2. 逐个比对 CRITICAL 列表里的关键脚本：工作区 blob vs 目标 ref blob；
  3. 不一致的 → **先备份到仓库外**（`<repo 同级>/v8_ws_backup_<时间戳>/`），
     再 `git checkout <ref> -- <文件>` 拉齐；
  4. 复检；**仍不一致则 return 1**（fail-closed，让调用方中止跑批，绝不用落后代码出产物）。

■ 用法
  python v8_ws_sync_guard.py            # 只检查，不一致则 exit 1（不改工作区）
  python v8_ws_sync_guard.py --heal     # 检查 + 备份 + 拉齐 + 复检（推荐给跑批入口用）
  python v8_ws_sync_guard.py --ref <sha>  # 指定目标 ref（默认 origin/main，退回 FETCH_HEAD）

■ 说明
  · `V8_SKIP_WS_GUARD=1` 可整体跳过（逃生舱；正常情况不要设）。
  · 🔴 2026-09-14：`--heal` 时会**先单独拉齐 `.gitattributes`**（行尾规则文件），
    再走原有的备份/拉齐/复检流程 —— 否则 index.html 会因本机规则陈旧而恒不齐，
    导致整条盘后算法链恒被中止（详见 _heal_rules_first 注释）。
  · 只比对**脚本/页面**这类「跑批输入」，**不碰 `raw_data/` `data/` `out/`** 产物目录。
  · 备份目录在仓库外，不进 git、不被坚果云同步。
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

REPO = r"E:\workspace\stock-scanner"

# 🔴 跑批输入的关键脚本/页面白名单。只列「被跑批直接执行或直接被前端消费」的文件，
#   不列产物（raw_data/ data/ out/）。
CRITICAL = [
    # 🔴 2026-09-14：**行尾规则文件必须在这里**。git 决定「checkout 写 LF 还是 CRLF」
    #   读的是工作区里的 .gitattributes；它不在白名单里 ⇒ 本机会永远停在旧规则上，
    #   于是 `*.html text eol=lf` 不生效 → index.html 被 core.autocrlf 写成 CRLF
    #   → 与 LF blob 永不一致 → 本守卫恒 exit 1 → 整条盘后链恒被中止。
    #   详见 _heal_rules_first() 注释。
    ".gitattributes",
    "update_v8.py",
    "index.html",
    "logic.html",
    "v8_health_check.py",
    "v8_deploy_guard.py",
    "api_push_raw.py",
    "algorithms/run_algorithms.py",
    "algorithms/scanner.py",
    "algorithms/strategy_four_volume.py",
    "algorithms/final_recommend.py",
    "algorithms/generate_top10.py",
    "algorithms/build_candidate_pool.py",
    "algorithms/calc_crds.py",
    "algorithms/gen_backtest_all_algos.py",
    "algorithms/backtest_tdx.py",
    "algorithms/backtest_comprehensive.py",
    "algorithms/gen_algo_track.py",
    "algorithms/gen_market_brief.py",
    # 🔴 2026-09-18 阿狸咪的工程师·零幽灵路径更正（独立实测复核，见 HANDOVER 09-18 回执）：
    #   原写 `algorithms/build_unlisted_panel.py` 与下方 `.github/scripts/v8_t1_guard.py`
    #   在远端 main **均不存在**（contents API 实测）⇒ 恒进 missing 列表打印「⚠️ 缺失」，
    #   制造噪声并误导后来人以为「漏推了文件」。真身位置如下两行，均为 2026-09-13/14
    #   `scripts/` 归位后的实际落点：
    #     · scripts/build_unlisted_panel.py（生成 data/UNLISTED_PANEL.js）
    #     · v8_t1_guard.py（仓根；由 .github/workflows/v8_t1_guard.yml 在仓根执行）
    "scripts/build_unlisted_panel.py",
    "v8/backtest_crds.py",
    "v8/factor_lab_gen.py",
    ".github/scripts/v8_stage_gate.py",
    "v8_t1_guard.py",
]


def _run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def _blob_of(ref, rel, repo):
    rc, out, _ = _run(["git", "-C", repo, "rev-parse", f"{ref}:{rel}"])
    if rc != 0:
        return None
    return out.decode("utf-8", "replace").strip()


def _worktree_blob(rel, repo):
    """工作区文件的 blob sha —— **必须带 filter**（`--path`），不能用 `--no-filters`。

    🔴 2026-09-14 一劳永逸根因（实测复现 + 证伪 `--no-filters`）：
      git 判断「工作区文件与目标 blob 是否同一份」用的是**经过 clean filter 归一化后**
      的内容。以 index.html（`.gitattributes` 里 `*.html text eol=lf`）为例：
        · 本机 core.autocrlf=true 且 `.gitattributes` 陈旧（缺 `*.html` 那条）时，
          checkout 会写出 **CRLF**；
        · 但此后 `git checkout origin/main -- index.html` 认为「把 CRLF 归一化后 == 目标 blob」
          ⇒ **认为无需重写，直接跳过**；
        · 而本函数原先 `--no-filters` 比的是**原始字节**（CRLF）⇒ 与 LF blob 永远不等
          ⇒ 复检「拉齐后仍不一致」⇒ 守卫恒 exit 1 ⇒ 整条盘后链恒被中止
          （线上实证：15:49:08 与 15:49:17 两次，13 个 *.py 全部拉齐、**只有 index.html 恒不齐**）。

      ⇒ 口径改为随 git 本身（`--path=<rel>` 触发 convert_to_git）：
        · CRLF 工作副本 = 同一内容 ⇒ 一致（本来就不是「用落后代码出产物」）；
        · **真正的代码差异仍然检出**（内容变了，归一化后 sha 必然不同）；
        · `logic.html` 是 `-text -eol`（二进制）⇒ 不做任何转换 ⇒ 判定不变。
    """
    p = os.path.join(repo, rel.replace("/", os.sep))
    if not os.path.exists(p):
        return None
    rc, out, _ = _run(["git", "-C", repo, "hash-object", "--path", rel, p])
    if rc != 0:
        return None
    return out.decode("utf-8", "replace").strip()


def pick_ref(repo):
    """优先拉远端；拉不到就退回本地已有的 origin/main，最后退回 FETCH_HEAD。"""
    rc, _, err = _run(["git", "-C", repo, "fetch", "origin", "main", "-q"])
    if rc == 0:
        print("  [ref] fetch origin main 成功")
    else:
        print(f"  [ref] ⚠️ fetch 失败（{err.decode('utf-8', 'replace')[:120].strip()}）"
              f" → 退回本地已有 ref，不中断")
    for ref in ("origin/main", "FETCH_HEAD"):
        rc, out, _ = _run(["git", "-C", repo, "rev-parse", ref])
        if rc == 0:
            sha = out.decode().strip()
            print(f"  [ref] 目标 = {ref} ({sha[:10]})")
            return ref
    return None


def _heal_rules_first(ref, repo):
    """🔴 2026-09-14 一劳永逸：**行尾规则文件必须在其它文件之前拉齐**。

    为什么不能只把 .gitattributes 塞进 CRITICAL 一起 checkout：
      同一次 `git checkout <ref> -- a b .gitattributes` 里，git 处理每个路径时
      读的仍是**当时**工作区的 .gitattributes（规则文件的生效不早于它自己被写出）
      ⇒ index.html 仍会按旧规则写成 CRLF → 复检仍失败 → 要跑第二次才自愈。
      故必须**单独一趟、先做**。

    为什么 index.html 是唯一受害者：
      · *.py / *.yml / *.sh 自带 `text eol=lf`，且规则是「内置」的（不依赖 .gitattributes 新旧）
        ⇒ checkout 后原始字节即 LF ⇒ 复检通过；
      · logic.html 是 `-text -eol`（blob 自身存 CRLF）⇒ checkout 写 CRLF ⇒ 复检同样通过；
      · 只有 index.html 依赖 2026-09-13 才补上的 `*.html text eol=lf` 那一条
        ⇒ 本机规则陈旧时它必不齐。
    """
    rel = ".gitattributes"
    want = _blob_of(ref, rel, repo)
    have = _worktree_blob(rel, repo)
    if want is None:
        print(f"  [rules] ⚠️ 远端无 {rel} → 跳过（不阻断）")
        return
    if want == have:
        return
    print(f"  [rules] 🔴 {rel} 与远端不一致 → 先单独拉齐（它决定后续 checkout 的行尾行为）")
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(os.path.abspath(repo)), f"v8_ws_backup_rules_{ts}")
    try:
        os.makedirs(bak, exist_ok=True)
        shutil.copy2(os.path.join(repo, rel), os.path.join(bak, rel))
    except OSError as e:
        print(f"  [rules] 🔴 备份 {rel} 失败：{e} → 中止（不冒险覆盖）")
        raise SystemExit(1)
    rc, _, err = _run(["git", "-C", repo, "checkout", ref, "--", rel])
    if rc != 0:
        print(f"  [rules] 🔴 checkout {rel} 失败：{err.decode('utf-8', 'replace')[:300]}")
        raise SystemExit(1)
    if _worktree_blob(rel, repo) != want:
        print(f"  [rules] 🔴 {rel} 拉齐后仍不一致 → 中止（fail-closed）")
        raise SystemExit(1)
    print(f"  [rules] ✅ {rel} 已拉齐（原文件备份在 {bak}）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--heal", action="store_true", help="备份 + 拉齐 + 复检")
    ap.add_argument("--ref", default=None, help="指定目标 ref（默认 origin/main → FETCH_HEAD）")
    a = ap.parse_args()

    if os.environ.get("V8_SKIP_WS_GUARD") == "1":
        print("[ws-guard] V8_SKIP_WS_GUARD=1 → 跳过")
        return 0
    repo = a.repo
    if not os.path.isdir(os.path.join(repo, ".git")):
        print(f"[ws-guard] ⚠️ {repo} 不是 git 仓库 → 跳过（不阻断）")
        return 0

    print("[ws-guard] 工作区 vs 远端 一致性检查")
    ref = a.ref or pick_ref(repo)
    if not ref:
        print("[ws-guard] 🔴 取不到任何远端 ref → 无法校验（fail-closed）")
        return 1

    # 🔴 行尾规则先行：必须早于任何 git checkout（理由见 _heal_rules_first）
    if a.heal:
        _heal_rules_first(ref, repo)

    mism, missing, same = [], [], []
    for rel in CRITICAL:
        rb = _blob_of(ref, rel, repo)
        wb = _worktree_blob(rel, repo)
        if rb is None and wb is None:
            missing.append(rel)
            continue
        if rb is None:
            missing.append(rel)          # 远端无此文件（本机多出来的本地新增）
            continue
        if wb == rb:
            same.append(rel)
        else:
            mism.append(rel)

    print(f"  一致 {len(same)} 个 / 不一致 {len(mism)} 个 / 缺失 {len(missing)} 个"
          f"（共 {len(CRITICAL)}）")
    for rel in mism:
        print(f"    🔴 不一致 {rel}")
    for rel in missing:
        print(f"    ⚠️ 缺失   {rel}")

    if not mism:
        print("[ws-guard] ✅ 工作区与远端一致，可以跑批")
        return 0

    if not a.heal:
        print("[ws-guard] ❌ 存在不一致（未加 --heal，不改动工作区）→ exit 1")
        return 1

    # 备份到仓库外
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(os.path.abspath(repo)), f"v8_ws_backup_{ts}")
    os.makedirs(bak, exist_ok=True)
    print(f"[ws-guard] 备份不一致文件 → {bak}（仓库外，不进 git）")
    for rel in mism:
        src = os.path.join(repo, rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue
        dst = os.path.join(bak, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            print(f"    🔴 备份失败 {rel}: {e} → 中止（不冒险覆盖）")
            return 1

    print(f"[ws-guard] git checkout {ref} -- <{len(mism)} 个文件>")
    rc, out, err = _run(["git", "-C", repo, "checkout", ref, "--"] + mism)
    if rc != 0:
        print(f"  🔴 checkout 失败：{err.decode('utf-8', 'replace')[:300]}")
        return 1

    # 复检
    still = []
    for rel in mism:
        rb = _blob_of(ref, rel, repo)
        wb = _worktree_blob(rel, repo)
        if rb != wb:
            still.append(rel)
    if still:
        print(f"  🔴 拉齐后仍不一致 {len(still)} 个：{still} → exit 1")
        return 1
    print(f"[ws-guard] ✅ 已拉齐 {len(mism)} 个文件；原文件备份在 {bak}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
