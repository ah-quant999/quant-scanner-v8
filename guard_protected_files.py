# -*- coding: utf-8 -*-
"""🔴 受保护文件守卫 —— 任何清理/瘦身/删除流程跑前必须先过这里。

用法：
    python guard_protected_files.py          # 检查受保护文件是否齐全
    python guard_protected_files.py --clean-check   # 供清理脚本调用，缺文件则 exit 2

设计动机（2026-09-16 主人令）：
    「用于累积的文件一定要打上不得误删之类的重要文件标签」
    data/SECTOR_CYCLE_ARCHIVE.js 等累积型档案，删除后**无法恢复**
    （数据源只保留 1 个月），故必须有机器可读的守卫，而非仅靠注释提醒。
"""
import io, os, json, sys

REPO = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(REPO, "PROTECTED_FILES.json")

def load():
    if not os.path.exists(MANIFEST):
        return None
    try:
        return json.load(io.open(MANIFEST, encoding="utf-8"))
    except Exception as e:
        print(f"⚠️ 读 {MANIFEST} 失败: {e}")
        return None

def main():
    clean_mode = "--clean-check" in sys.argv
    m = load()
    if m is None:
        print("⚠️ 未找到 PROTECTED_FILES.json，跳过受保护文件校验")
        return 0
    files = m.get("files", [])
    missing, ok = [], []
    for f in files:
        rel = f["path"]
        if os.path.exists(os.path.join(REPO, rel)):
            ok.append(rel)
        else:
            missing.append((rel, f.get("why", "")))
    print(f"受保护文件校验：齐全 {len(ok)} / 共 {len(files)}")
    for r in ok:
        print(f"  ✅ {r}")
    for r, why in missing:
        print(f"  🔴 缺失 {r}")
        print(f"      原因：{why[:110]}")
    if missing:
        print()
        print("🔴🔴 检测到**累积型重要档案缺失**！")
        print("    这些文件删除后无法恢复（数据源只保留 1 个月）。")
        print("    请立即检查是否被清理脚本误删；可用 git 历史恢复：")
        for r, _ in missing:
            print(f"      git checkout <上一次提交> -- {r}")
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
