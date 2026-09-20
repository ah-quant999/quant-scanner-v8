#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""normalize_eol.py — 行尾归一化收口（幂等 · 只动 \\r\\n，不碰其它任何字节）

■ 为什么存在（2026-09-20 根因实证 · run 35497633913）
  ① 本机（Windows）算法/生成脚本落盘普遍是
         open(path, "w", encoding="utf-8")          # newline 未指定
     Python 在 Windows 上 newline=None ⇒ "\\n" 被写成 os.linesep = "\\r\\n"。
     实测（本机复现）：同一份 json.dump(..., indent=1)
         open(...,"w",encoding="utf-8")          → CRLF=6  LF=6     ← 全 CRLF
         open(...,"w",encoding="utf-8",newline="\\n") → CRLF=0  LF=6  ← 纯 LF
  ② api_push_raw.py / scripts/api_put_file.py 以**二进制**读本地文件后走
     GitHub Git Data / Contents API 直推，**完整绕过 .gitattributes 的行尾归一化**
     ⇒ 本地 CRLF 原样进 blob。
  ③ 根 .gitattributes 声明 raw_data/*.json、data/*.js、*.py、*.yml、*.html 等
     为 `text eol=lf`。CI（Linux）checkout 后工作树是 CRLF 而属性要求 LF
     ⇒ `git status` 恒脏 ⇒ **任何 git rebase 在启动前即被拒**：
         warning: in the working copy of 'raw_data/top10_daily.json',
                  CRLF will be replaced by LF the next time Git touches it
         error: cannot rebase: You have unstaged changes.
         error: Please commit or stash them.
         fatal: no rebase in progress
         ##[error]Process completed with exit code 128.
     ⇒ v8 实时风险温度计 / 缓存戳对齐 / 备份 / 盘中快照 / 周清理 等
       9 条带 rebase 的推链会周期性假失败（每次都是「3 次重试全空转」）。

■ 职责边界（三条硬约束，改本文件前必读）
  1. **只做行尾**：除 "\\r\\n"→"\\n" 外逐字节不变；孤立 "\\r"（后面不跟 "\\n"）不动，
     避免误伤二进制/特殊格式。
  2. **只处理「.gitattributes 要求 LF」的路径**。判定真源是 `git check-attr`，
     绝不另写一套会漂移的规则（历史教训：两套口径必然漂移）。
  3. **逻辑例外**：logic.html 属**有意 CRLF**（属性 `-text -eol`，理由见
     .gitattributes 的长注释），`git check-attr` 对它返回 eol=unset ⇒ 自动跳过，
     本模块另加 NEVER_TOUCH 双保险，**永不触碰**。

■ 用法
  python scripts/normalize_eol.py --root . --check          # 只报告不写
  python scripts/normalize_eol.py --root .                  # 就地规范化全仓已跟踪文件
  python scripts/normalize_eol.py --root . --paths a.json b.js   # 只处理指定相对路径
  python scripts/normalize_eol.py --root . --json           # 机器可读摘要

■ 作为库使用（api_push_raw.py / api_put_file.py 的接入方式）
  spec = importlib.util.spec_from_file_location("normalize_eol", <本文件路径>)
  mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
  exp, how = mod.expected_lf(root, rels)        # {rel: 该路径是否应为 LF}
  data = mod.to_lf(data) if exp.get(rel) else data
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# ── 有意保留 CRLF 的例外（双保险；check-attr 已能识别，此处防 git 不可用时的降级误判）──
NEVER_TOUCH = {"logic.html"}

# ── git check-attr 不可用时的降级规则（必须与根 .gitattributes 同步维护）──
_LF_SUFFIX = (".yml", ".yaml", ".sh", ".py")
_LF_EXACT = {".gitattributes", "v6_memo.html", "v6_memo.golden.html"}


def _fallback_expected(rel: str) -> bool:
    """降级判据：无 git 时按 .gitattributes 的字面规则复刻。

    ⚠️ 刻意与 .gitattributes 保持**同粒度**：
       `raw_data/*.json` 只匹配直接子文件，**不含** raw_data/history/*.json
       （fnmatch 的 `*` 不跨 `/`，与 gitattributes 语义一致）。
       对无属性文件做归一化反而会在本机侧制造新的「工作树 vs blob」差异，
       故宁可少做，不可多做。
    """
    p = rel.replace("\\", "/")
    if p in NEVER_TOUCH:
        return False
    if p in _LF_EXACT or p.endswith(_LF_SUFFIX):
        return True
    parts = p.split("/")
    if len(parts) == 1 and parts[0].endswith(".html"):
        return True
    if len(parts) == 2 and parts[0] == "data" and parts[1].endswith(".js"):
        return True
    if len(parts) == 2 and parts[0] == "raw_data" and parts[1].endswith(".json"):
        return True
    return False


def _git_exe() -> str:
    return os.environ.get("V8_GIT_EXE", "git")


def _check_attr(root: str, rels):
    """批量 `git check-attr --stdin -z text eol`，返回 ({rel: 是否应为LF}, 依据) 或 (None, None)。

    输出为 NUL 分隔的三元组流：路径 \\0 属性名 \\0 值 \\0 （重复）。
    值为 "unset" 表示该属性被显式关闭；"unspecified" 表示没有规则。
    """
    try:
        inp = "\0".join(rels) + "\0"
        r = subprocess.run(
            [_git_exe(), "check-attr", "--stdin", "-z", "text", "eol"],
            cwd=root, input=inp.encode("utf-8"),
            capture_output=True, timeout=180)
    except Exception:
        return None, None
    if r.returncode != 0:
        return None, None
    toks = r.stdout.decode("utf-8", "replace").split("\0")
    if toks and toks[-1] == "":
        toks.pop()
    d = {}
    for i in range(0, len(toks) - 2, 3):
        p, a, v = toks[i], toks[i + 1], toks[i + 2]
        d.setdefault(p, {})[a] = v
    got = {}
    for rel in rels:
        if rel.replace("\\", "/") in NEVER_TOUCH:
            got[rel] = False
            continue
        info = d.get(rel)
        if not info:
            got[rel] = _fallback_expected(rel)
            continue
        # 只有显式 `eol=lf` 才是「属性要求 LF」；unset/unspecified/crlf 一律不碰
        got[rel] = (info.get("eol") == "lf")
    return got, "git-check-attr"


def list_tracked(root: str):
    """`git ls-files -z`：仓库已跟踪文件（相对路径，正斜杠）。"""
    r = subprocess.run([_git_exe(), "ls-files", "-z"], cwd=root,
                       capture_output=True, timeout=600)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def expected_lf(root: str, rels):
    """返回 ({rel: 该路径是否按 .gitattributes 应为 LF}, 判定依据字符串)。"""
    rels = list(rels)
    got, how = _check_attr(root, rels)
    if got is None:
        how = "fallback-rules(no-git)"
        got = {r: _fallback_expected(r) for r in rels}
    return got, how


def to_lf(content: bytes) -> bytes:
    """把 CRLF 归一化为 LF（幂等）。孤立 \\r 不动。"""
    if b"\r\n" not in content:
        return content
    return content.replace(b"\r\n", b"\n")


def normalize_bytes(rel: str, content: bytes, exp) -> bytes:
    """按 exp（expected_lf 的结果）决定是否归一化单份内容。供推仓脚本逐文件调用。"""
    try:
        want = exp.get(rel)
    except Exception:
        want = None
    if want is None:
        want = _fallback_expected(rel)
    if not want:
        return content
    return to_lf(content)


def run(root: str = ".", rels=None, check: bool = False):
    root = os.path.abspath(root)
    if rels is None:
        rels = list_tracked(root)
    exp, how = expected_lf(root, rels)
    changed, missing, scanned = [], [], 0
    for rel in sorted(exp):
        if not exp[rel]:
            continue
        full = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            missing.append(rel)
            continue
        scanned += 1
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            missing.append(rel)
            continue
        new = to_lf(data)
        if new == data:
            continue
        changed.append({"path": rel, "before_bytes": len(data),
                        "after_bytes": len(new), "crlf_removed": data.count(b"\r\n")})
        if not check:
            with open(full, "wb") as f:
                f.write(new)
    return {"root": root, "attr_source": how, "candidates": len(rels),
            "lf_expected": int(sum(1 for v in exp.values() if v)),
            "scanned": scanned, "changed": changed, "missing": missing,
            "check_only": bool(check)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--paths", nargs="*", default=None)
    ap.add_argument("--check", action="store_true", help="只报告，不写入")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run(a.root, a.paths, a.check)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print("🔧 行尾归一化（.gitattributes ⇒ eol=lf）")
    print("   判定依据=%s · 候选=%d · 其中应为LF=%d · 实扫=%d"
          % (res["attr_source"], res["candidates"], res["lf_expected"], res["scanned"]))
    if not res["changed"]:
        print("   ✅ 无需改动（全部已是 LF，幂等）")
    else:
        print("   %s %d 个文件（CRLF → LF）:"
              % ("将改动" if a.check else "已改动", len(res["changed"])))
        for c in res["changed"]:
            print("     %-52s -%d bytes（去 CR ×%d）"
                  % (c["path"], c["before_bytes"] - c["after_bytes"], c["crlf_removed"]))
    if res["missing"]:
        print("   ⚠️ %d 个路径不存在（跳过）: %s" % (len(res["missing"]), res["missing"][:5]))
    if a.check and res["changed"]:
        print("   ℹ️ 本次为 --check（未写入）。去掉 --check 即就地规范化。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
