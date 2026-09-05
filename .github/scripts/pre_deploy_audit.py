#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 Pre-deploy audit（CI 自动门禁，2026-09-05 主人令一劳永逸落地）
================================================================
目的：每次云端 build/deploy 前自动跑 4 项校验，任何一项失败 → 阻断 deploy。
等同「改后三件套」固化为 CI step，不再依赖人工记忆流程。

四项校验：
  1. py_compile        —— 所有 *.py 文件 0 语法错误
  2. new Function      —— index.html 所有 inline <script> 0 语法错误（Node）
  3. 完整性核对        —— data/*.js 数量在合理范围（90~110，与 HEAD 对齐）
  4. align_logic_ops   —— 逻辑详解页与真 workflow 一致（EXIT 0）

退出码：
  0  全部通过
  1  任意一项失败（deploy 阻断）

铁律：纯标准库 + 仅调本地子进程，可被 GitHub Actions ubuntu-latest 干净跑通。
"""
import os, re, sys, subprocess, json, glob, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # .github/scripts/ → repo root
errors = []


def check_py_compile():
    """所有 .py 文件 py_compile，0 错才算过。"""
    py_files = []
    for sub in ["algorithms", "v8", "scripts", ".github/scripts", "" ]:
        if sub:
            d = ROOT / sub
            if d.exists():
                py_files += sorted(d.rglob("*.py"))
        else:
            py_files += sorted(ROOT.glob("*.py"))
    py_files = [p for p in py_files if "__pycache__" not in str(p)]
    if not py_files:
        return (True, "无 .py 文件")
    # 用本地 python；CI 环境用系统 python3
    py = sys.executable if sys.executable else "python3"
    failed = []
    for p in py_files:
        try:
            subprocess.run([py, "-m", "py_compile", str(p)],
                           check=True, capture_output=True, timeout=15)
        except subprocess.CalledProcessError as e:
            failed.append(f"{p.relative_to(ROOT)}: {e.stderr.decode('utf-8', 'replace')[:120]}")
        except subprocess.TimeoutExpired:
            failed.append(f"{p.relative_to(ROOT)}: 超时")
    if failed:
        return (False, f"{len(failed)}/{len(py_files)} 文件语法错:\n  - " + "\n  - ".join(failed[:5]))
    return (True, f"{len(py_files)} 个 .py 文件 0 错误")


def check_new_function():
    """抽 index.html 所有 inline <script> 跑 new Function，0 错才算过。"""
    idx = ROOT / "index.html"
    if not idx.exists():
        return (True, "index.html 不存在（跳过）")
    html = idx.read_text(encoding="utf-8")
    # 含 src= 的不抽（外链脚本）
    pattern = re.compile(r"<script(?!\s[^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", re.IGNORECASE)
    blocks = []
    for m in pattern.finditer(html):
        code = m.group(1)
        # 跳过极短空块或纯 CSS 注释
        if not code.strip() or len(code.strip()) < 30:
            continue
        # 只测有意义的代码（含 window/function/const/let/var/=>/return/document/import）
        if not re.search(r"\b(window|function|const|let|var|=>|return|document|import)\b", code):
            continue
        blocks.append(code)
    if not blocks:
        return (True, "无 inline script 块")
    # 写入临时 js 文件用 node 跑
    tmp = ROOT / ".github/scripts/_pre_deploy_audit_test.js"
    payload = "var __blocks = " + json.dumps(blocks) + ";\n"
    payload += "var __errs = 0;\n"
    payload += "for (var i = 0; i < __blocks.length; i++) {\n"
    payload += "  try { new Function(__blocks[i]); } catch(e) { __errs++; console.log('block#'+i+': '+e.message.slice(0,150)); }\n"
    payload += "}\n"
    payload += "console.log('blocks=' + __blocks.length + ' errors=' + __errs);\n"
    payload += "process.exit(__errs > 0 ? 1 : 0);\n"
    tmp.write_text(payload, encoding="utf-8")
    node = subprocess.run(["node", str(tmp)], capture_output=True, text=True, timeout=60)
    try:
        tmp.unlink()
    except Exception:
        pass
    if node.returncode != 0:
        out = (node.stdout + node.stderr).strip().split("\n")[:8]
        return (False, f"{len(blocks)} 块中部分语法错:\n  " + "\n  ".join(out))
    return (True, f"{len(blocks)} 个 inline script 块 0 错误")


def check_data_integrity():
    """data/*.js 数量在合理范围（90~110），防止 Nutstore 误删导致空白部署。"""
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return (False, "data/ 目录不存在")
    js = list(data_dir.glob("*.js"))
    n = len(js)
    if n < 90 or n > 110:
        return (False, f"data/*.js 数量={n} 超出合理范围 [90,110]")
    # 健康文件最小字节
    too_small = [p.name for p in js if p.stat().st_size < 100]
    if too_small:
        return (False, f"data/ 下过小文件 {len(too_small)} 个: {too_small[:5]}")
    return (True, f"data/*.js 数量={n}, 全部 > 100B")


def check_align_logic_ops():
    """跑 align_logic_ops.py，EXIT 0 算过。"""
    py = sys.executable if sys.executable else "python3"
    r = subprocess.run([py, "align_logic_ops.py"], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        out = (r.stdout + r.stderr).strip().split("\n")[-5:]
        return (False, f"align_logic_ops 失败:\n  " + "\n  ".join(out))
    return (True, "align_logic_ops EXIT 0（逻辑详解页与真 workflow 对齐）")


def write_audit_log(results, exit_code):
    """落盘三件套审计轨迹到 raw_data/code_audit.log（append）。
    让「何时/谁跑过三件套」有据可查。*.log 已被 .gitignore 忽略 → 不入库、不污染工作树。
    日志失败绝不阻断 deploy（静默吞掉）。
    """
    try:
        log_path = ROOT / "raw_data" / "code_audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        env = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"
        try:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            sha = "unknown"
        if not sha:
            sha = "unknown"
        status = "PASS" if exit_code == 0 else "FAIL"
        head = f"[{ts}] env={env} commit={sha} result={status}"
        body = "\n".join(f"    {lb}: {'OK' if ok else 'FAIL'} - {msg}" for lb, ok, msg in results)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(head + "\n" + body + "\n\n")
    except Exception:
        pass


def main():
    checks = [
        ("[1/4] py_compile", check_py_compile),
        ("[2/4] new Function", check_new_function),
        ("[3/4] data 完整性", check_data_integrity),
        ("[4/4] align_logic_ops", check_align_logic_ops),
    ]
    print("=" * 60)
    print("v8 pre-deploy audit（CI 自动门禁，2026-09-05 启用）")
    print("=" * 60)
    fails = 0
    results = []
    for label, fn in checks:
        ok, msg = fn()
        icon = "✅" if ok else "❌"
        print(f"  {icon} {label}: {msg}")
        results.append((label, ok, msg))
        if not ok:
            fails += 1
            errors.append(f"{label}: {msg}")
    print("=" * 60)
    write_audit_log(results, 0 if fails == 0 else 1)
    if fails:
        print(f"🚫 {fails} 项校验失败 → 阻断 deploy！")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("🎉 4 项全部通过 → deploy 可继续")
    sys.exit(0)


if __name__ == "__main__":
    main()
