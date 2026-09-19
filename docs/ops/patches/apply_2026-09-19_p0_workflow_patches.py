#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs/ops/patches/apply_2026-09-19_p0_workflow_patches.py

一键应用两份「改 CI workflow」的 P0 补丁（阿狸咪的 PAT 无 workflow scope ⇒ 须由有权限方执行）。

【为什么要有这个脚本，而不是只给 .patch】
  实测（2026-09-19 08:2x，本机）：
    · P0-1 的补丁**幂等性为假** —— 连应用 3 次就插 3 份 soft_13b（patch 只看上下文，
      不认「已经插过」）⇒ 裸 patch 有插重风险。
    · P0-2 的补丁自带保护（二次应用 patch 自报 "Reversed (or previously applied)" 并跳过），
      但会留下 .rej/.orig 垃圾文件。
  本脚本：**先判已应用 ⇒ 跳过；未应用 ⇒ dry-run 通过才真跑；跑完逐项自证；清理垃圾**。

【用法】（在仓库根目录执行）
    python docs/ops/patches/apply_2026-09-19_p0_workflow_patches.py            # 应用 + 自证
    python docs/ops/patches/apply_2026-09-19_p0_workflow_patches.py --dry-run  # 只看会不会成功

【本脚本不做的事】不 commit、不 push、不碰 index.html。推送命令在末尾打印，请单条原子执行。
"""
import io, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

JOBS = [
    {
        "id": "P0-2",
        "name": "index.html 被 build 静默盖回（根因：备份→reset→盖回，条件在 CI 恒真）",
        "target": ".github/workflows/v8_build_deploy.yml",
        "patch": "v8_build_deploy_index_clobber_fix_20260919.patch",
        "already": lambda s: "index.html.manual" not in s,
        "check": lambda s: (s.count("index.html.manual") == 0
                            and s.count("git reset --hard FETCH_HEAD") == 7),
        "expect": "index.html.manual == 0（原 4）、reset --hard FETCH_HEAD == 7（原 9）",
    },
    {
        "id": "P0-1",
        "name": "cn_fetch 接线 fetch_sector_leaders.py（板块龙头股字典随 SECTOR_RS 同轮）",
        "target": ".github/workflows/v8_cn_fetch_cloud.yml",
        "patch": "v8_cn_fetch_wire_sector_leaders.patch",
        "already": lambda s: "id: soft_13b" in s,
        "check": lambda s: (s.count("id: soft_13b") == 1
                            and s.index("id: soft_13") < s.index("id: soft_13b") < s.index("id: soft_14")
                            and "python scripts/fetch_sector_leaders.py" in s),
        "expect": "id: soft_13b 恰好 1 处，且位置在 id: soft_13 与 id: soft_14 之间",
    },
]

DRY = "--dry-run" in sys.argv


def rd(p):
    return io.open(p, "rb").read().decode("utf-8")


def sh(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True)
    out = (r.stdout or b"").decode("utf-8", "ignore") + (r.stderr or b"").decode("utf-8", "ignore")
    return r.returncode, out.strip()


def cleanup(target_abs):
    """清掉 patch 可能留下的 .rej / .orig（仓库内不留垃圾）。"""
    killed = []
    for suf in (".rej", ".orig"):
        p = target_abs + suf
        if os.path.exists(p):
            os.remove(p)
            killed.append(os.path.basename(p))
    return killed


def main():
    print("仓库根 = %s" % ROOT)
    bad = 0
    to_push = []
    for job in JOBS:
        tgt = os.path.join(ROOT, job["target"])
        pth = os.path.join(HERE, job["patch"])
        print("\n" + "=" * 74)
        print("[%s] %s" % (job["id"], job["name"]))
        print("  目标 = %s" % job["target"])
        if not os.path.exists(tgt):
            print("  ❌ 目标文件不存在（是否在仓库根执行？）")
            bad += 1
            continue
        if not os.path.exists(pth):
            print("  ❌ 补丁件缺失：%s" % pth)
            bad += 1
            continue
        cur = rd(tgt)
        if job["already"](cur):
            ok = job["check"](cur)
            print("  ⏭  已应用过 ⇒ 跳过（自证 %s）" % ("✅" if ok else "❌"))
            if not ok:
                bad += 1
            continue

        rc, out = sh(["patch", "-p1", "--dry-run", "-i", pth], cwd=ROOT)
        print("  dry-run rc=%d  %s" % (rc, out.replace("\n", " | ")))
        if rc != 0:
            print("  ❌ dry-run 未通过 ⇒ 远端可能已漂移，请重取最新文件再生成补丁（勿强行应用）")
            cleanup(tgt)
            bad += 1
            continue
        if DRY:
            print("  （--dry-run：不实际应用）")
            continue

        rc, out = sh(["patch", "-p1", "-i", pth], cwd=ROOT)
        print("  apply   rc=%d  %s" % (rc, out.replace("\n", " | ")))
        killed = cleanup(tgt)
        if killed:
            print("  已清理：%s" % killed)
        if rc != 0:
            bad += 1
            continue
        new = rd(tgt)
        ok = job["check"](new)
        crlf = new.count("\r")
        print("  自证：%s  期望 %s" % ("✅" if ok else "❌", job["expect"]))
        print("  行尾：CRLF=%d（须 0）%s" % (crlf, "✅" if crlf == 0 else "❌"))
        if not (ok and crlf == 0):
            bad += 1
        else:
            to_push.append(job["target"])
    print("\n" + "=" * 74)
    if bad:
        print("❌ 有 %d 项未通过 —— 请**不要**提交；先看上面的失败原因。" % bad)
        return 1
    print("✅ 全部通过。下一步（**逐条显式路径**，禁 `git add -A`）：")
    for p in to_push or ["（本次无需改动：均已应用）"]:
        print("   git add %s" % p)
    if to_push:
        print('   git commit -m "fix(ci): 应用 P0-1/P0-2 workflow 补丁（接口/防覆盖）"')
        print("   git push origin main")
    print("   推送后请回执阿狸咪：`git show origin/main:%s | grep -c 'index.html.manual'` 期望 0"
          % ".github/workflows/v8_build_deploy.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
