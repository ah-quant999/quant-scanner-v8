#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双盲区护栏（Double-Blind Guard）—— 机器可断言的静态一致性校验。

## 事故家族（三次复发，必须一次性封死）

「双盲区」= 同一产物**闸门不覆盖 + 巡检不告警** ⇒ 冻结数日而全链零红灯：

| # | 日期   | 产物                    | 症状                                   | 当时修法        |
|---|--------|-------------------------|----------------------------------------|-----------------|
| 1 | 09-11  | data/FOUR_VOLUME_60M.js | 冻结 3 天（09-08→09-11）零告警         | 仅摘「巡检白名单」 |
| 2 | 09-18  | data/BACKTEST_TDX.js    | 冻结 4 天（停 09-14），76MB 推送 422   | 闸门提 must + 摘白名单（两端） |
| 3 | 09-18  | data/FOUR_VOLUME_60M.js | 冻结逾 24h（09-17 06:54 起），全链零阻塞 | 闸门补 items + 白名单同步（本轮） |

根因：前两次都是**针对单个产物打补丁**，没有校验「所有卡是否都在闸门覆盖内」。
本脚本把「零特例」立成**可执行断言**，让第四次结构上无法发生。

## 校验的三条不变式

1. **I-1 闸门覆盖**：凡 `v8_health_check.py::CARD_DEFS` 中 `heal_cat == "algo_run"`
   且 `picking == True`（即 B/D 批盘后选股产物）的卡，其数据文件
   **必须在 `v8_stage_gate.py::READY_SPEC[*]["items"]` 中出现**
   —— 否则陈旧不阻塞就绪 ⇒ 闸门空转 ⇒ 永不重跑（盲区一）。

2. **I-2 去重白名单**：`READY_SPEC[*]["items"] ∪ must` ⊆
   `dedup_fetch_manifest.py::_ALWAYS_PUSH`
   —— 否则内容稳定时被判「伪变更」丢弃 ⇒ update_time 恒旧 ⇒ 永久不收敛。

3. **I-3 巡检告警**：凡在 READY_SPEC 中出现的产物，其对应巡检 id
   **不得在 `_LOW_FREQ_FILES` 中**（否则陈旧降级为「7 天才告警」⇒ 盲区二）。

退出码：0 = 全部通过；1 = 发现盲区（CI 应硬阻断）。

用法：python .github/scripts/guard_double_blind.py
"""
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if (Path(__file__).resolve().parents[1].name == "scripts") else Path.cwd()


def _resolve_root():
    """仓库根解析：① 命令行参数 ② 环境变量 V8_ROOT ③ 由 __file__ 上溯（.github/scripts/x.py → root）。"""
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).resolve()
        if p.is_dir():
            return p
    env = os.environ.get("V8_ROOT")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "v8_health_check.py").exists() and (parent / ".github" / "scripts").is_dir():
            return parent
    return Path.cwd()
GATE = None
DEDUP = None
HEALTH = None


def _read(p):
    if not p.exists():
        print(f"❌ 找不到文件: {p}")
        sys.exit(2)
    return p.read_text(encoding="utf-8", errors="replace")


def _target_name(node):
    """兼容 `X = ...` 与 `X: T = ...` 两种赋值形式，返回左值名。"""
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                return t.id
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            return node.target.id
    return None


def parse_ready_spec(src):
    """从 v8_stage_gate.py 抽出 READY_SPEC 的 items/must（按批）。"""
    tree = ast.parse(src)
    spec = {}
    for node in ast.walk(tree):
        if _target_name(node) != "READY_SPEC":
            continue
        val = node.value
        if not isinstance(val, ast.Dict):
            continue
        for k, v in zip(val.keys, val.values):
            if not isinstance(k, ast.Constant):
                continue
            batch = k.value
            if not isinstance(v, ast.Dict):
                continue
            entry = {"items": [], "must": []}
            for kk, vv in zip(v.keys, v.values):
                if not isinstance(kk, ast.Constant):
                    continue
                if kk.value in ("items", "must") and isinstance(vv, (ast.List, ast.Tuple)):
                    entry[kk.value] = [
                        e.value for e in vv.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
            spec[batch] = entry
    return spec


def parse_always_push(src):
    """从 dedup_fetch_manifest.py 抽出 _ALWAYS_PUSH 集合。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if _target_name(node) != "_ALWAYS_PUSH":
            continue
        if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            return {
                e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
    return set()


def parse_card_defs(src):
    """从 v8_health_check.py 抽出 CARD_DEFS：[{id, file?, heal_cat, picking}]。

    文件名字段在 CARD_DEFS 里可能叫 `file` / `path` / 由 `_CARD_FILE_MAP` 提供；
    这里同时收集 CARD_DEFS 文本里的 .js 文件名与 id，做宽松匹配。
    """
    tree = ast.parse(src)
    cards = []
    for node in ast.walk(tree):
        if _target_name(node) != "CARD_DEFS":
            continue
        if not isinstance(node.value, ast.List):
            continue
        for el in node.value.elts:
            if not isinstance(el, ast.Dict):
                continue
            d = {}
            for k, v in zip(el.keys, el.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    d[k.value] = v.value
            if "id" in d:
                cards.append(d)
    return cards


def parse_low_freq(src):
    """从 v8_health_check.py 抽出 _LOW_FREQ_FILES 集合。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if _target_name(node) != "_LOW_FREQ_FILES":
            continue
        if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            return {
                e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
    return set()


def parse_card_file_map(src):
    """抽出 `(「X.js」, 「ID」, ...)` 形式的映射（v8_health_check 里大量存在）。"""
    m = {}
    for mt in re.finditer(r'\(\s*"([A-Za-z0-9_]+\.js)"\s*,\s*"([A-Z0-9_]+)"', src):
        m.setdefault(mt.group(2), mt.group(1))
    return m


def main():
    global ROOT, GATE, DEDUP, HEALTH
    ROOT = _resolve_root()
    GATE = ROOT / ".github" / "scripts" / "v8_stage_gate.py"
    DEDUP = ROOT / ".github" / "scripts" / "dedup_fetch_manifest.py"
    HEALTH = ROOT / "v8_health_check.py"

    print("=" * 72)
    print("双盲区护栏（Double-Blind Guard）· 机器可断言静态校验")
    print(f"仓库根: {ROOT}")
    print("=" * 72)

    gate_src = _read(GATE)
    dedup_src = _read(DEDUP)
    health_src = _read(HEALTH)

    spec = parse_ready_spec(gate_src)
    always_push = parse_always_push(dedup_src)
    cards = parse_card_defs(health_src)
    low_freq = parse_low_freq(health_src)
    card_file = parse_card_file_map(health_src)

    print(f"\n解析结果：READY_SPEC 批次={list(spec)}   _ALWAYS_PUSH={len(always_push)} 项"
          f"   CARD_DEFS={len(cards)} 项   _LOW_FREQ_FILES={len(low_freq)} 项")

    gate_items = set()
    gate_must = set()
    for b, e in spec.items():
        gate_items |= set(e["items"])
        gate_must |= set(e["must"])
    gate_all = gate_items | gate_must
    print(f"闸门覆盖产物：items={len(gate_items)}  must={len(gate_must)}  并集={len(gate_all)}")

    problems = []

    # ── I-1 闸门覆盖：algo_run + picking 的卡必须进 READY_SPEC ──
    print("\n【I-1】闸门覆盖校验（algo_run & picking 的卡 ⊆ READY_SPEC）")
    # 文件名推导优先级：
    #   ① CARD_DEFS 显式 file/path 字段
    #   ② 映射表 (「X.js」, 「ID」) 反查
    #   ③ 🔴 兜底：id 本身即文件名主干（本仓库实测约定：id=FOUR_VOLUME_60M ↔ data/FOUR_VOLUME_60M.js）
    #      —— ③ 是必需的：映射表只有 7 条，仅靠它会让多数卡「拿不到文件名就跳过」= 护栏自身变盲。
    #
    # 🔴 分级判据（关键：**不是所有未覆盖都是盲区**）：
    #   · 若该产物**另有闸门代理项**（如 CANDIDATE / GOLD_POOL 由采集批 build_candidate_pool.py 产出，
    #     READY_SPEC["B"].items 用 raw_data/gold_pool.json 作「上游新鲜度抵押」）
    #     ⇒ 属**有意的设计选择**，降级为 NOTE，不阻断 CI。
    #   · 否则 ⇒ **真盲区**（陈旧不阻塞就绪 ⇒ 闸门空转 ⇒ 永不重跑），硬阻断。
    #   代理关系来自 v8_stage_gate.py 内既有注释的明示，硬编码为本表（变更须同步）。
    GATE_PROXY = {
        "CANDIDATE": "raw_data/gold_pool.json",   # 采集批 build_candidate_pool.py 产出（闸门注释 L234-239）
        "GOLD_POOL": "raw_data/gold_pool.json",   # 同上（同日同源，实测 update_time 一致）
    }
    uncovered = []
    noted = []
    for c in cards:
        if c.get("heal_cat") != "algo_run" or not c.get("picking"):
            continue
        cid = c["id"]
        fname = c.get("file") or c.get("path") or card_file.get(cid) or (cid + ".js")
        target = f"data/{fname}"
        if target not in gate_all:
            proxy = GATE_PROXY.get(cid)
            if proxy and proxy in gate_all:
                noted.append((cid, target, proxy))
            else:
                uncovered.append((cid, target))
    if uncovered:
        for cid, target in sorted(uncovered):
            problems.append(f"I-1 闸门盲区：CARD_DEFS[{cid}] → {target} 不在 READY_SPEC 任何批次")
            print(f"  ❌ {cid:28s} → {target:34s} 不在 READY_SPEC")
    else:
        print("  ✅ 全部被闸门覆盖（无真盲区）")
    for cid, target, proxy in sorted(noted):
        print(f"  ⓘ {cid:28s} → {target:34s} 由代理项 {proxy} 抵押（设计选择，不阻断）")

    # ── I-2 去重白名单：READY_SPEC items ∪ must ⊆ _ALWAYS_PUSH ──
    print("\n【I-2】去重白名单校验（READY_SPEC items ∪ must ⊆ _ALWAYS_PUSH）")
    missing_push = sorted(gate_all - always_push)
    if missing_push:
        for f in missing_push:
            problems.append(f"I-2 收敛风险：{f} 在 READY_SPEC 但不在 _ALWAYS_PUSH（内容稳定时永不推送）")
            print(f"  ❌ {f}")
    else:
        print(f"  ✅ 全部 {len(gate_all)} 项均已在白名单")

    # ── I-3 巡检告警：READY_SPEC 产物对应的巡检 id 不得在 _LOW_FREQ_FILES ──
    print("\n【I-3】巡检告警校验（READY_SPEC 产物不得进 _LOW_FREQ_FILES）")
    file_to_id = {v: k for k, v in card_file.items()}
    id_set = {c["id"] for c in cards}
    conflicts = []
    for f in sorted(gate_all):
        if not f.startswith("data/"):
            continue
        fname = f[len("data/"):]
        # id 推导（同 I-1 兜底规则）：映射表优先，其次文件名主干即 id
        cid = file_to_id.get(fname) or (fname[:-3] if fname.endswith(".js") else None)
        if cid and cid in low_freq and cid in id_set:
            conflicts.append((f, cid))
    if conflicts:
        for f, cid in conflicts:
            problems.append(f"I-3 告警盲区：{f}（巡检 id={cid}）在 _LOW_FREQ_FILES 中 ⇒ 24h 红线降为 7 天")
            print(f"  ❌ {f}  巡检 id={cid} 在 _LOW_FREQ_FILES")
    else:
        print("  ✅ 无冲突")

    print("\n" + "=" * 72)
    if problems:
        print(f"❌ 发现 {len(problems)} 处双盲区隐患：")
        for p in problems:
            print(f"   • {p}")
        print("\n处置：按上表修 v8_stage_gate.py / dedup_fetch_manifest.py / v8_health_check.py，"
              "两处必须同时改（缺一即锁死或盲区）。")
        print("=" * 72)
        return 1
    print("✅ 三条不变式全部通过 —— 无双盲区隐患")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
