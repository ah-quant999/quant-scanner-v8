#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_cli_contract.py — CLI 契约静态护栏（断根 --upto 类参数漂移）
================================================================
🛡 2026-09-19 一劳永逸（小九）：根治「脚本参数被误删、workflow 调用点未同步
   → 每轮 run 假 failure」类事故（实证见 verify_chain_outputs.py L82-95 注释）。

根因回顾
    cd1ccb3dd0（09-18「清除干净」）把 verify_chain_outputs.py 的 --upto 参数连同
    死代码一起删掉，但 v8_algo_cloud.yml L913 仍在调用 `--upto "$TGT"` ⇒
    argparse rc=2 ⇒ 兜底 echo 触发 ⇒ 步 failure。误删能逃过自检，是因为
    「调用点在 YAML」用 grep algorithms/ 只会得到「无引用」假结论。

本护栏做什么
    用 ast.parse 精确提取「目标脚本 argparse 接受的参数集合」（不依赖注释/
    字符串匹配，注释里的 --xxx 不会被误算），再扫描 .github/workflows/*.yml
    中对该脚本的所有调用，提取实际传的 --flags，断言：
        {调用参数} ⊆ {脚本 argparse 参数}
    一旦有人再删参数而忘改 workflow（或反之），本护栏在 CI 预检步亮红灯/警告，
    把「静默每轮假失败」变成「提交即暴露」。

用法
    python algorithms/check_cli_contract.py
    python algorithms/check_cli_contract.py --script algorithms/verify_chain_outputs.py
    python algorithms/check_cli_contract.py --strict     # 违反则 exit 1（硬护栏）
    # 默认 --warn 模式：违反只打印警告、exit 0，不阻断主链（上线观察期）

设计铁律
    🔴 本脚本自身只允许「纯标准库 + ast」，零第三方依赖（CI 环境即开即用）。
    🔴 不修改任何被检文件，只读。
"""
import argparse
import ast
import os
import re
import sys


def script_accepted_args(py_path):
    """用 ast.parse 提取脚本 argparse 接受的参数（首参或 name= 关键字）。"""
    src = open(py_path, encoding="utf-8").read()
    tree = ast.parse(src)
    flags = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        # 首位置参数（如 "--upto" / "-h"）
        if node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-"):
                flags.add(a.value.split()[0])
        # name= 关键字（如 name="--foo"）
        for kw in node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str) and kw.value.value.startswith("-"):
                flags.add(kw.value.value.split()[0])
    return flags


def workflow_calls(yml_path, script_rel):
    """扫描 yml 中对 script_rel 的所有调用行，提取实际传的 --flags。"""
    txt = open(yml_path, encoding="utf-8").read()
    calls = []
    for line in txt.splitlines():
        if script_rel not in line:
            continue
        # 只取到 `||` 之前的命令段（之后是错误处理，不算调用参数）
        seg = line.split("||")[0]
        flags = set(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", seg))
        if flags:
            calls.append((line.strip(), flags))
    return calls


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.dirname(here)  # algorithms/ 的上一级 = 仓库根
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="algorithms/verify_chain_outputs.py",
                    help="要校验契约的算法脚本（相对仓库根）")
    ap.add_argument("--workflows-dir", default=".github/workflows")
    ap.add_argument("--repo-root", default=default_root)
    ap.add_argument("--strict", dest="strict", action="store_true",
                    help="违反契约则 exit 1（硬护栏）；默认 --warn 只警告")
    args = ap.parse_args()

    root = args.repo_root
    sp = os.path.join(root, args.script)
    if not os.path.exists(sp):
        print("🔴 脚本不存在: %s" % sp)
        return 2
    accepted = script_accepted_args(sp)
    print("📋 %s 接受的 argparse 参数: %s" % (args.script, sorted(accepted)))

    wd = os.path.join(root, args.workflows_dir)
    if not os.path.isdir(wd):
        print("🔴 workflows 目录不存在: %s" % wd)
        return 2

    bad = []
    for fn in sorted(os.listdir(wd)):
        if not fn.endswith(".yml"):
            continue
        for line, flags in workflow_calls(os.path.join(wd, fn), args.script):
            missing = flags - accepted
            if missing:
                bad.append((fn, line, missing))
                print("❌ [%s] 调用参数不在 argparse 中: %s" % (fn, sorted(missing)))
                print("     调用: %s" % line[:180])

    if bad:
        print("\n🔴 CLI 契约自检失败：%d 处调用参数漂移（调用参数 ⊄ 脚本 argparse 参数）" % len(bad))
        print("   → 这是 --upto 类事故的先兆：脚本参数与 workflow 调用点不一致。")
        print("   → 请同步修改：要么把参数加回脚本，要么去掉 workflow 里的调用参数。")
        return 1 if args.strict else 0
    print("\n✅ CLI 契约自检通过：所有 workflow 调用参数 ⊆ 脚本 argparse 参数（无漂移）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
