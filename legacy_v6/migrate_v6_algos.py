#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_v6_algos.py — 将 v6 的算法产出脚本选择性复制到 v8/algorithms/

策略（选择性复制，非整体移动）：
- 只复制 v8 真正需要的「算法产出」脚本（post_close 盘后计算链），
  不复制 v6 的 batch_update 大编排器（那才是 v6 臃肿本体）。
- 仅把脚本里的 data/ 路径改写为 out/（staging 目录，仍用 v6 文件名，
  避免任何跨脚本改名导致的断裂）。
- 真正重命名为 v8 的 raw_data 文件名，由 stage_to_raw.py 依据 V6_TO_V8 完成。
- 本地依赖 fundamental_helper.py / fetch_logger.py 一并复制。

运行：python migrate_v6_algos.py   （在 v8 仓库根目录执行）

⚠️ 2026-08-01 起：algorithms/ 下的副本已在 v8 侧手工修复多处 bug（见各文件内
   "2026-08-01 修正" 注释：triple_consensus 漏股 / calc_crds 崩溃与分值上限 /
   backtest_comprehensive 收益错标(P0) / cockpit_tier 死项 / fetch_sector_rs BASE 等）。
   **切勿直接重跑本脚本覆盖！** 如确需重新迁移，请先把这些修复同步回 v6 原件，
   否则会用未修复的 v6 版本覆盖掉 v8 侧的修复。
"""
import os
import re

V6 = r"E:\workspace\stock-scanner"
V8 = os.path.dirname(os.path.abspath(__file__))
ALGO = os.path.join(V8, "algorithms")
OUT_REL = os.path.join("..", "out")  # 相对脚本目录

# 需要复制的算法产出脚本（相对 v6 根）
PRODUCERS = [
    "build_candidate_pool.py",
    "generate_top10.py",
    "fetch_lhb.py",
    "fetch_sector_rs.py",
    "fetch_sh_index_fib.py",
    "fetch_inst_trade.py",
    "calc_crds.py",
    "gen_cockpit_tier_recommend.py",
    "gen_cockpit_advice.py",
    "gen_triple_track.py",
    "gen_triple_consensus.py",
    "cockpit_backtest_now.py",
    "backtest_tdx.py",
    "backtest_comprehensive.py",
    "fetch_stock_names.py",
    "update_triple_resonance_history.py",
    "fetch_fundamental_quality.py",
]
DEPS = ["fundamental_helper.py", "fetch_logger.py"]

# CWD 相对 data/ 字面量（少数脚本用 "data/xxx.json" 而非 os.path.join）
CWD_LITERALS = {
    "fetch_lhb.py": [
        ('OUT = "data/lhb_result.json"', 'OUT = os.path.join(BASE, "..", "out", "lhb_result.json")'),
        ('path = "data/lhb_history.json"', 'path = os.path.join(BASE, "..", "out", "lhb_history.json")'),
    ],
    "fetch_sector_rs.py": [
        ('OUT = "data/sector_rs.json"', 'OUT = os.path.join(BASE, "..", "out", "sector_rs.json")'),
    ],
}


def transform(content: str, fname: str) -> str:
    # 1) 注入 BASE 守卫（供 CWD 相对字面量使用；已定义则不变）
    if "import os" in content:
        guard = (
            "\ntry:\n    _ = BASE\nexcept NameError:\n"
            "    BASE = os.path.dirname(os.path.abspath(__file__))\n"
        )
        lines = content.split("\n")
        for i, ln in enumerate(lines):
            if re.search(r"^\s*import\s+.*\bos\b", ln):
                lines.insert(i + 1, guard.rstrip("\n"))
                break
        content = "\n".join(lines)

    # 2) os.path.join(X, "data", REST) -> os.path.join(X, "..", "out", REST)
    content = re.sub(
        r'os\.path\.join\(([^,]+),\s*"data",\s*([^)]*)\)',
        r'os.path.join(\1, "..", "out", \2)',
        content,
    )
    # 3) os.path.join(X, "data") -> os.path.join(X, "..", "out")
    content = re.sub(
        r'os\.path\.join\(([^,]+),\s*"data"\)',
        r'os.path.join(\1, "..", "out")',
        content,
    )
    # 4) CWD 相对字面量替换
    for old, new in CWD_LITERALS.get(fname, []):
        if old in content:
            content = content.replace(old, new)
        else:
            print(f"  ⚠️ {fname}: 未找到字面量 {old!r}，请人工核对")
    return content


def main():
    os.makedirs(ALGO, exist_ok=True)
    os.makedirs(os.path.join(ALGO, "out"), exist_ok=True)

    for fn in PRODUCERS + DEPS:
        src = os.path.join(V6, fn)
        if not os.path.exists(src):
            print(f"  ❌ 源缺失: {fn}")
            continue
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        if fn not in DEPS:
            content = transform(content, fn)
        out = os.path.join(ALGO, fn)
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ 复制 {fn} -> algorithms/{fn}" + ("" if fn in DEPS else " (data→out)"))

    # 写 .gitkeep 占位 out/（避免空目录不进 git）
    open(os.path.join(ALGO, "out", ".gitkeep"), "w").close()
    print(f"\n完成。共复制 {len(PRODUCERS)} 个算法脚本 + {len(DEPS)} 个依赖。")


if __name__ == "__main__":
    main()
