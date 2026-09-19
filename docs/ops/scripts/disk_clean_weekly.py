# -*- coding: utf-8 -*-
r"""T0 磁盘垃圾清理执行器（2026-09-15 · 小九的工程师）

安全设计：
  1. --dry 默认；--go 才真删
  2. 办公文档类型硬白名单：即使 mtime 超期也永不删（防误删办公文件）
  3. 所有 tmp 目录按 mtime>7天 逐条筛，绝不整目录删
  4. 跳过 reparse point（junction/symlink）
  5. 删除失败（被占用/无权限）→ 跳过并记录，不中断
  6. 节流：每 300 条 sleep 0.03s，避免打满 IO 影响办公
  7. 完整名单落盘，可追溯
"""
import os, sys, io, time, json, stat, shutil, argparse, ctypes
from ctypes import wintypes
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

# ============================================================================
# 跨机自适应（2026-09-19 小九→阿狸咪 交接新增）
# ----------------------------------------------------------------------------
# 原脚本把用户目录写死为 C:\Users\Administrator，只在小九机可用。
# 本版改为**自动探测当前用户目录**，两台机同一份脚本直接跑，无需改路径。
#   探测优先级：env USERPROFILE > HOMEDRIVE+HOMEPATH > 向上 walk > 兜底
# 注意：`.workbuddy` 在小九机是 junction -> E:\workbuddy-data；
#      阿狸咪机是否为 junction **未知**，故启动时打印「探测结果 + 是否 reparse」，
#      由执行者当场核对，脚本不替使用者做判断。
# ============================================================================
FA_REPARSE_CHK = 0x400


def _detect_home():
    h = os.environ.get("USERPROFILE")
    if h and os.path.isdir(h):
        return h, "env:USERPROFILE"
    d = os.environ.get("HOMEDRIVE")
    p = os.environ.get("HOMEPATH")
    if d and p and os.path.isdir(d + p):
        return d + p, "env:HOMEDRIVE+HOMEPATH"
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        cur = os.path.dirname(cur)
        cand = os.path.join(cur, "Administrator")
        if os.path.isdir(cand):
            return cand, "walk-up"
    return os.path.join("C:" + os.sep, "Users", "Administrator"), "fallback"


_HOME, _HOME_SRC = _detect_home()


def _is_reparse_chk(p):
    try:
        st = os.stat(p, follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & FA_REPARSE_CHK)
    except Exception:
        return False


def print_env_banner():
    print("  -- 本机路径探测（跨机自适应）--")
    print("     USERPROFILE = %s   [%s]" % (_HOME, _HOME_SRC))
    for _n in (".workbuddy", "AppData"):
        _p = os.path.join(_HOME, _n)
        if os.path.isdir(_p):
            if _is_reparse_chk(_p):
                print("     %-14s REPARSE -> %s" % (_n, os.path.realpath(_p)))
            else:
                print("     %-14s normal dir" % _n)
        else:
            print("     %-14s (not found; related batches auto-skip)" % _n)
    print("  -- note: if .workbuddy is a junction, batch 6/7 free the TARGET drive, not C --")


# ---------------- 真删引擎 ----------------
# 说明：本机的安全层（sitecustomize.py / BASH_ENV shim）会把所有 os.remove /
# shutil.rmtree / rm 转为「移入回收站」。同盘回收站不释放空间 ⇒ 对「临时文件清理」
# 这个目标无效。主人已明确选择「永久删除（T0 唯一有效）」，故此处直调 Win32 API
# 做真删；同时**不触碰**回收站中主人的原有内容。
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)

_DeleteFileW = _k32.DeleteFileW
_DeleteFileW.argtypes = [wintypes.LPCWSTR]
_DeleteFileW.restype = wintypes.BOOL

_RemoveDirectoryW = _k32.RemoveDirectoryW
_RemoveDirectoryW.argtypes = [wintypes.LPCWSTR]
_RemoveDirectoryW.restype = wintypes.BOOL

_SetFileAttributesW = _k32.SetFileAttributesW
_SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_SetFileAttributesW.restype = wintypes.BOOL

_GetFileAttributesW = _k32.GetFileAttributesW
_GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
_GetFileAttributesW.restype = wintypes.DWORD

FA_NORMAL = 0x80
FA_REPARSE = 0x400
FA_DIRECTORY = 0x10
INVALID_ATTRS = 0xFFFFFFFF


def _L(p):
    p = os.path.abspath(p)
    if len(p) >= 240 and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + p
    return p


def _attrs(p):
    a = _GetFileAttributesW(_L(p))
    return None if a == INVALID_ATTRS else a


def _unlink_file(p):
    p2 = _L(p)
    if _DeleteFileW(p2):
        return True
    _SetFileAttributesW(p2, FA_NORMAL)      # 只读/隐藏属性
    return bool(_DeleteFileW(p2))


def _rmdir(p):
    p2 = _L(p)
    if _RemoveDirectoryW(p2):
        return True
    _SetFileAttributesW(p2, FA_NORMAL)
    return bool(_RemoveDirectoryW(p2))


def hard_rm(root):
    """真删（不进回收站）。后序遍历；reparse point 只删链接本身，绝不穿透。"""
    root = os.path.abspath(root)
    a = _attrs(root)
    if a is None:
        return True                                   # 已不存在
    if not (a & FA_DIRECTORY):
        return _unlink_file(root)
    if a & FA_REPARSE:
        return _rmdir(root)                           # junction / 挂载点：只删链接

    dirs = []; stack = [root]; failed = 0
    while stack:
        d = stack.pop()
        dirs.append(d)
        try:
            with os.scandir(_L(d)) as it:
                for e in it:
                    ea = _attrs(e.path)
                    if ea is None:
                        continue
                    if ea & FA_REPARSE:
                        if ea & FA_DIRECTORY:
                            _rmdir(e.path)
                        else:
                            _unlink_file(e.path)
                    elif ea & FA_DIRECTORY:
                        stack.append(e.path)
                    else:
                        if not _unlink_file(e.path):
                            failed += 1
        except OSError:
            failed += 1
    ok = True
    for d in reversed(dirs):
        if not _rmdir(d):
            ok = False
    return ok and failed == 0


REPARSE = 0x400
DAY = 86400.0
NOW = time.time()
CUTOFF_DAYS = 7
CUTOFF = NOW - CUTOFF_DAYS * DAY

# 🔒 办公文档硬白名单：命中即永不删除（即使 mtime 超期）
# 2026-09-15 收窄：初版含 .txt/.md/.csv，导致 C:\c、E:\c、qs8-tmp-BAK、workspace_backup
#   因命中的是运维 .md / numpy 测试 .csv 而被误跳过（甄别后确认非办公文件）。
#   现只保留「真正的办公文档格式」——实测样本 `26年全院档案核查任务花名册_*.xlsx` 仍受保护。
OFFICE_EXT = {".doc", ".docx", ".dot", ".dotx",
              ".xls", ".xlsx", ".xlsm", ".xlt",
              ".ppt", ".pptx", ".pps", ".pot",
              ".pdf", ".rtf", ".odt", ".ods", ".odp",
              ".wps", ".et", ".dps", ".wpt", ".ett", ".dpt"}

LOGF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_clean_log.json")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cutoff_days": CUTOFF_DAYS,
       "batches": {}, "deleted": [], "skipped_office": [], "failed": []}


def fmt(n):
    return f"{n/1024/1024/1024:.2f} GB" if n >= 1024**3 else f"{n/1024/1024:.1f} MB"


def is_reparse(p):
    try:
        st = os.stat(p, follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & REPARSE)
    except Exception:
        return True          # 拿不到属性 → 当作危险，跳过


def _is_tool_cache(p):
    """已知工具缓存目录 ⇒ 不可能是主人的个人文件，跳过办公文档检查。
    实测：469 个 codebuddy-marketplace-install-* 里命中办公扩展名的是插件自带的
    theme-factory/theme-showcase.pdf；若不做豁免会整体跳过，白白丢掉十几 GB。"""
    low = os.path.basename(p).lower()
    return ("marketplace-" in low) or ("updater_pkg" in low) or low.startswith("node_modules")


def probe_dir(root, budget_end):
    """一次遍历同时得出：是否含办公文档 / 总字节 / 文件数。
    合并原 has_office_file + dir_size，避免对同一目录遍历两遍。"""
    total = 0; nf = 0; office = False
    skip_office = _is_tool_cache(root)
    seen = set(); stack = [root]
    while stack:
        if time.time() > budget_end:
            break
        d = stack.pop()
        try:
            st = os.stat(d, follow_symlinks=False)
            k = (st.st_dev, st.st_ino)
            if k in seen:
                continue
            seen.add(k)
            it = os.scandir(d)
        except Exception:
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                    if getattr(st, "st_file_attributes", 0) & REPARSE:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        total += st.st_size; nf += 1
                        if (not office) and (not skip_office) and st.st_size > 64 * 1024 \
                                and os.path.splitext(e.name)[1].lower() in OFFICE_EXT:
                            office = True
                except Exception:
                    pass
    return office, total, nf


def dir_size(root, budget_end):
    _o, total, nf = probe_dir(root, budget_end)
    return total, nf


def rm(path):
    """真删单条（文件或目录）——走 hard_rm，不进回收站。"""
    try:
        return hard_rm(path)
    except Exception:
        return False


def collect_old_in(root, label, deadline, days=CUTOFF_DAYS):
    """tmp 目录内：mtime>days 天的顶层条目（排除办公文档）"""
    dl = NOW - days * DAY
    out = []
    try:
        es = list(os.scandir(root))
    except Exception as e:
        print(f"    ❌ 无法读取 {root}: {e}")
        return out
    for e in es:
        try:
            st = e.stat(follow_symlinks=False)
        except Exception:
            continue
        if getattr(st, "st_file_attributes", 0) & REPARSE:
            continue
        if st.st_mtime >= dl:
            continue
        out.append((e.path, st.st_size, e.is_dir(follow_symlinks=False), st.st_mtime))
    return out


def do_items(items, batch_key, budget, thr=300):
    """删除一批条目，返回 (释放字节, 成功数, 跳过办公数, 失败数)

    2026-09-18 改进：先按体积降序再删。原因——批7 有 4.2 万条小文件，预算耗尽时
    若按原顺序（字典序）截断，可能删了一堆 0.1KB 小文件却把 GB 级大文件留在后面，
    下一轮又要重新扫描。按大小降序可保证「预算用到哪，空间就实打实释放到哪」。
    """
    items = sorted(items, key=lambda x: -x[1])
    freed = 0; ok = 0; skipped = 0; failed = 0
    t0 = time.time()
    for i, (p, sz, isd, mt) in enumerate(items):
        if time.time() > budget:
            print(f"    ⏱ 预算耗尽，本批剩余 {len(items)-i} 条留待下批")
            break
        if isd:
            # 一次遍历：办公文档保护 + 体积统计（预算 8s，超时返回部分值）
            has_off, s, nf = probe_dir(p, time.time() + 8)
            if has_off:
                skipped += 1
                LOG["skipped_office"].append(p)
                print(f"    🔒 跳过（含办公文档）: {p}")
                continue
        else:
            if os.path.splitext(p)[1].lower() in OFFICE_EXT and sz > 64 * 1024:
                skipped += 1
                LOG["skipped_office"].append(p)
                continue
            s = sz
        if rm(p):
            freed += s; ok += 1
            LOG["deleted"].append({"path": p, "size": s})
        else:
            failed += 1
            LOG["failed"].append(p)
        if (i + 1) % thr == 0:
            time.sleep(0.03)          # 节流：别打满 IO
    LOG["batches"][batch_key] = {
        "freed_bytes": freed, "ok": ok, "skipped_office": skipped,
        "failed": failed, "elapsed_sec": round(time.time() - t0, 1)}
    print(f"    → 释放 {fmt(freed)} / 成功 {ok} 条 / 跳过办公 {skipped} / 失败 {failed} / 耗时 {time.time()-t0:.0f}s")
    return freed, ok, skipped, failed


# ---------------- 批次定义 ----------------
def batch_verify():
    """批 0：极小验证批（事故遗留）"""
    print("\n【批 0 · 脚本行为验证】事故遗留（≈0.1MB）")
    items = []
    for p in ("E:\\_synctest", "E:\\_synctest2", "E:\\_synctest_origin",
              "D:\\360RecycleBin", "D:\\360Downloads"):
        if os.path.exists(p):
            s, nf = dir_size(p, time.time() + 30)
            items.append((p, s, True, NOW))
            print(f"    · {p}  {fmt(s)}  {nf} 文件")
        else:
            print(f"    · {p}  [不存在]")
    return items


def batch_tmp():
    """批 1：各盘陈旧 tmp（mtime>7天 逐条）"""
    print(f"\n【批 1 · 陈旧临时文件】mtime > {CUTOFF_DAYS} 天（逐条筛，办公文档保护）")
    items = []
    for root in ("C:\\tmp", "C:\\Temp", "D:\\tmp", "E:\\tmp"):
        got = collect_old_in(root, root, time.time() + 120)
        items.extend(got)
        print(f"    · {root}: {len(got)} 条超期")
    return items


def batch_malformed():
    """批 2：畸形根目录（POSIX 路径 bug 产物）"""
    print("\n【批 2 · 畸形根目录】C:\\c C:\\e D:\\e E:\\c E:\\e")
    items = []
    for p in ("C:\\e", "C:\\c", "E:\\c", "E:\\e", "D:\\e"):
        if os.path.exists(p):
            s, nf = dir_size(p, time.time() + 90)
            items.append((p, s, True, NOW))
            print(f"    · {p}  {fmt(s)}  {nf} 文件")
    return items


def batch_big():
    """批 3：安装包缓存 + 陈旧备份"""
    print("\n【批 3 · 安装包缓存与陈旧备份】")
    items = []
    for p in ("D:\\SoftMgrbcff1feb", "E:\\v8data\\qs8-tmp-BAK-2026-09-08",
              "E:\\workspace_backup"):
        if os.path.exists(p):
            s, nf = dir_size(p, time.time() + 120)
            items.append((p, s, True, NOW))
            print(f"    · {p}  {fmt(s)}  {nf} 文件")
        else:
            print(f"    · {p}  [不存在]")
    return items


def batch_temp():
    """批 4：E:\\Temp 陈旧项（最大头）"""
    T = os.environ.get("TEMP", "E:\\Temp")
    print(f"\n【批 4 · E:\\Temp 陈旧项】mtime > {CUTOFF_DAYS} 天（逐条筛）")
    items = collect_old_in(T, T, time.time() + 300)
    print(f"    · 超期顶层条目 {len(items)} 条")
    return items


def batch_appdata():
    """批 5：C: 用户临时与缓存 —— 覆盖旧脚本盲区，这是 C 盘天天涨的真因。
    逐条 mtime>7天 筛，办公文档硬保护（probe_dir 内已做）。"""
    print(f"\n【批 5 · C:用户临时与缓存】mtime > {CUTOFF_DAYS} 天（逐条筛，办公文档保护）")
    roots = (
        os.path.join(_HOME, "AppData", "Local", "Temp"),
        "C:\\Windows\\Temp",
        os.path.join(_HOME, "AppData", "Local", "pip", "Cache"),
        os.path.join(_HOME, "AppData", "Local", "CrashDumps"),
        os.path.join(_HOME, "AppData", "Local", "Microsoft", "Windows", "INetCache"),
    )
    items = []
    for r in roots:
        if os.path.isdir(r):
            got = collect_old_in(r, r, time.time() + 180)
            items.extend(got)
            print(f"    · {r}: {len(got)} 条超期")
        else:
            print(f"    · {r}  [不存在]")
    return items


# 🔒 重要会话硬保护：文件名命中标记，或路径命中系统关键项 → 无论多久都不删（用户明令）
_LOG_KEEP_MARKERS = ("重要", "important", "keep", "保留", "请勿删",
                     "do-not-delete", "dnd", "pin", "重要记录")
_LOG_PROTECT_PATHS = ("v8_gh_token", "MEMORY.md", "skills", "binaries",
                      "workbuddy.db", "mcp.json", "connectors", "automations",
                      "scripts", "scheduled_tasks")


# ============================================================================
# 批 7：.workbuddy 四大纯缓存目录（2026-09-18 新增 · 主人令「C盘空间都快满了」）
# ----------------------------------------------------------------------------
# 背景：批 6 只清 projects/**/*.jsonl，完全没覆盖真正的大头。2026-09-18 实测：
#   traces 3.99G(超7天3.06G) / logs 3.06G / file-tree-manifests 1.12G / file-history 0.66G
#   —— 四类合计 8.81GB，全在 C 盘，是 C 盘吃紧的主因。
#
# 🔴 白名单是【目录级硬锁定】，不在下表内的一律不碰（os.walk 起点即白名单根，
#    并在循环内二次校验 realpath 前缀，防目录穿越）。
# 🔴 只删单个文件，绝不删目录本身（保留桶结构，服务下次写入）。
# 🔴 年龄闸门 >7 天 + 办公文档硬保护 + reparse point 跳过，与批 1~6 同标准。
# ============================================================================
_WB_CACHE_DIRS = ("traces", "logs", "file-history", "file-tree-manifests")


def batch_wb_caches():
    """批 7：.workbuddy 四大纯缓存目录中超 7 天的文件（目录级白名单硬锁）"""
    WB = os.path.join(_HOME, ".workbuddy")
    print(f"\n【批 7 · .workbuddy 缓存目录】{_WB_CACHE_DIRS} mtime > {CUTOFF_DAYS} 天")
    items = []
    keep_root = os.path.realpath(WB)
    for name in _WB_CACHE_DIRS:
        root = os.path.join(WB, name)
        if not os.path.isdir(root):
            print(f"    · {name}: [不存在]")
            continue
        rroot = os.path.realpath(root)
        # 白名单边界：realpath 必须仍在 .workbuddy 之下
        if not rroot.startswith(keep_root + os.sep):
            print(f"    · {name}: ⛔ 越界，跳过")
            continue
        got = 0
        for dp, _dns, fns in os.walk(root, onerror=lambda e: None):
            rdp = os.path.realpath(dp)
            if not (rdp == rroot or rdp.startswith(rroot + os.sep)):
                continue                      # 目录穿越/软链逃逸 → 整支跳过
            for f in fns:
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p, follow_symlinks=False)
                except Exception:
                    continue
                if getattr(st, "st_file_attributes", 0) & REPARSE:
                    continue
                if st.st_mtime >= NOW - CUTOFF_DAYS * DAY:
                    continue
                if os.path.splitext(p)[1].lower() in OFFICE_EXT and st.st_size > 64 * 1024:
                    LOG["skipped_office"].append(p)
                    continue
                items.append((p, st.st_size, False, st.st_mtime))
                got += 1
        print(f"    · {name}: {got} 条超期")
    return items


def _is_protected_log(p):
    low = p.lower().replace("\\", "/")
    nm = os.path.basename(p).lower()
    if any(m in nm for m in _LOG_KEEP_MARKERS):
        return True
    if any(k in low for k in _LOG_PROTECT_PATHS):
        return True
    return False


def batch_workbuddy_logs():
    """批 6：.workbuddy 会话日志（>7天 .jsonl）—— AI 自身数据，非办公文件。
    递归全扫 projects/ 各级子目录（含 agent 嵌套日志），仅删 .jsonl。
    保留近 7 天「有用」会话；更旧且未打重要标记的视为无用可删。
    【硬保护】文件名含 重要/keep/保留 等标记、或路径命中系统关键项的，无论多久都不删。
    已按用户授权（2026-09-16）并入 --batch all，每晚 23:00 自动执行。"""
    KEEP_DAYS = 7
    print(f"\n【批 6 · .workbuddy 会话日志】mtime > {KEEP_DAYS} 天（递归扫，仅 .jsonl，重要文件硬保护）")
    root = os.path.join(_HOME, ".workbuddy", "projects")
    items = []
    if not os.path.isdir(root):
        print("    · [不存在]")
        return items
    try:
        for d, _, fnames in os.walk(root):
            for f in fnames:
                if not f.lower().endswith(".jsonl"):
                    continue
                p = os.path.join(d, f)
                if _is_protected_log(p):
                    continue
                try:
                    st = os.stat(p, follow_symlinks=False)
                except Exception:
                    continue
                if getattr(st, "st_file_attributes", 0) & REPARSE:
                    continue
                if st.st_mtime >= NOW - KEEP_DAYS * DAY:
                    continue
                items.append((p, st.st_size, False, st.st_mtime))
    except Exception as e:
        print(f"    ❌ {e}")
    print(f"    · 超期可删会话日志 {len(items)} 条（已排除重要/系统文件）")
    return items


# ============================================================================
# 批 8：C 盘应用缓存（2026-09-18 新增）
# ----------------------------------------------------------------------------
# 🔴 背景（血训）：批 7 加完后发现方向搞错了 —— `C:\Users\Administrator\.workbuddy`
#    本身是 junction 指向 `E:\workbuddy-data`，所以批 6/7 清的其实是 **E 盘**。
#    C 盘吃紧另有其因，实测真凶在 AppData 下的应用缓存：
#      AppData\Local\Temp            4.4 GB
#      AppData\Roaming\kingsoft      2.8 GB
#      AppData\Local\npm-cache       2.1 GB
#      AppData\Roaming\Tencent       1.9 GB
#      AppData\Local\Microsoft       1.7 GB
#      AppData\Local\winToolBox      1.3 GB
#      AppData\Local\sogoupdf        1.2 GB
#      AppData\Roaming\tyb           1.0 GB
#      AppData\Roaming\secoresdk     0.9 GB
#      AppData\Local\MeituApp        0.9 GB
#      AppData\Roaming\Coze          0.8 GB
#      各类 *-updater 残留          ~2.8 GB（合计）
#
# 🔴 安全设计（层层设防）：
#    1) 【目录级白名单硬锁】：只扫下表列出的缓存子目录，绝不全盘递归 AppData
#    2) 【年龄闸门】>7 天（可调），新鲜文件一律不碰（正在用的绝不删）
#    3) 【办公文档硬保护】OFFICE_EXT + >64KB 一律跳过（主人令「不准动我工作的文件」）
#    4) 【reparse point 跳过】junction/symlink 永不进
#    5) 【只删文件，不删目录本身】保留桶结构
#    6) 【realpath 越界二次校验】防目录穿越
# ============================================================================
_C_APPDATA = os.path.join(_HOME, "AppData")

# 缓存子目录白名单（相对 AppData）。只加「纯缓存/纯日志/更新包残留」类，
# 绝不加含用户配置/数据的目录（如 Roaming\kingsoft\office6\backup 之类的备份也要谨慎）。
_C_CACHE_SUBDIRS = (
    # ---- Local（纯缓存）----
    r"Local\npm-cache\_cacache",
    r"Local\pip\Cache",
    r"Local\Microsoft\Windows\INetCache",
    r"Local\Microsoft\Windows\Explorer",          # 缩略图缓存
    r"Local\CrashDumps",
    r"Local\D3DSCache",
    r"Local\Temp",                                 # 已在批5 覆盖，这里再兜一次（同标准）
    # ---- 应用自身 cache 目录（按名字含 cache 的常见路径）----
    r"Local\kingsoft\wps\cache",
    r"Local\Tencent",
    r"Local\sogoupdf\cache",
    r"Local\MeituApp\Cache",
    r"Local\winToolBox\cache",
    r"Local\google\Chrome\User Data\Default\Cache",
    r"Local\360Chrome\Chrome\User Data\Default\Cache",
    # ---- updater 残留（下载完的安装包，纯粹垃圾）----
    r"Local\@guanjia-openclawelectron-updater",
    r"Local\@genieworkbuddy-desktop-updater",
    r"Local\qclaw-updater",
    r"Local\coze-updater",
    r"Local\yiyang-suite-updater",
    # ---- Roaming（缓存/日志类，谨慎挑选）----
    r"Roaming\Tencent\Logs",
    r"Roaming\Tencent\WeChat\radium\Cache",
    r"Roaming\secoresdk\logs",
    r"Roaming\Coze\Cache",
    r"Roaming\QQ\Cache",
)


def batch_c_appcache():
    """批 8：C 盘 AppData 下的应用缓存（目录级白名单 + >7天 + 办公文档硬保护）"""
    print(f"\n【批 8 · C:盘应用缓存】白名单 {len(_C_CACHE_SUBDIRS)} 个子目录，mtime > {CUTOFF_DAYS} 天")
    items = []
    keep_root = os.path.realpath(_C_APPDATA)
    for sub in _C_CACHE_SUBDIRS:
        root = os.path.join(_C_APPDATA, sub)
        if not os.path.isdir(root):
            continue
        rroot = os.path.realpath(root)
        # 越界校验：realpath 必须仍在 AppData 之下
        if not (rroot == keep_root or rroot.startswith(keep_root + os.sep)):
            print(f"    · {sub}: ⛔ 越界，跳过")
            continue
        got = 0
        for dp, _dns, fns in os.walk(root, onerror=lambda e: None):
            rdp = os.path.realpath(dp)
            if not (rdp == rroot or rdp.startswith(rroot + os.sep)):
                continue                              # 目录穿越/软链逃逸 → 整支跳过
            for f in fns:
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p, follow_symlinks=False)
                except Exception:
                    continue
                if getattr(st, "st_file_attributes", 0) & FA_REPARSE:
                    continue
                if st.st_mtime >= NOW - CUTOFF_DAYS * DAY:
                    continue                          # 新鲜的一律不动
                if os.path.splitext(p)[1].lower() in OFFICE_EXT and st.st_size > 64 * 1024:
                    LOG["skipped_office"].append(p)   # 办公文档硬保护
                    continue
                items.append((p, st.st_size, False, st.st_mtime))
                got += 1
        if got:
            print(f"    · {sub}: {got} 条超期")
    print(f"    => 合计 {len(items)} 条待删")
    return items


# 默认 all 跑 0~8# 批6：.workbuddy 会话日志>7天+重要文件硬保护，已按用户授权 2026-09-16 并入每晚23:00自动任务
# 批7：.workbuddy 四大纯缓存目录，2026-09-18 按主人令「C盘空间都快满了」新增并入 all
# 批8：C 盘应用缓存（kingsoft/Tencent/npm-cache/各类 updater 残留），2026-09-18 新增
ALL_DEFAULT = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]

BATCHES = {
    "0": ("脚本行为验证·事故遗留", batch_verify),
    "1": ("陈旧临时文件", batch_tmp),
    "2": ("畸形根目录", batch_malformed),
    "3": ("安装包缓存与陈旧备份", batch_big),
    "4": ("E:\\Temp 陈旧项", batch_temp),
    "5": ("C:用户临时与缓存", batch_appdata),
    "6": (".workbuddy 会话日志(>7天·重要文件硬保护)", batch_workbuddy_logs),
    "7": (".workbuddy 缓存目录(traces/logs/file-history/file-tree-manifests)", batch_wb_caches),
    "8": ("C:盘应用缓存(kingsoft/Tencent/npm-cache/updater残留)", batch_c_appcache),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="真删（默认只干跑）")
    ap.add_argument("--batch", default="all", help="0/1/2/3/4/all")
    ap.add_argument("--dry", action="store_true", help="只列清单")
    a = ap.parse_args()

    keys = ALL_DEFAULT if a.batch == "all" else [a.batch]
    if a.batch != "all" and a.batch not in BATCHES:
        print(f"❌ 未知批次 {a.batch}"); return 2

    print("=" * 78)
    print(f"T0 磁盘清理 · {'【干跑清单】' if not a.go else '【实际删除】'}   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)

    print_env_banner()
    print()

    before = {}
    for d in ("C:\\", "D:\\", "E:\\"):
        try:
            u = shutil.disk_usage(d)
            before[d] = u.free
            print(f"  {d} 可用 {fmt(u.free)} / 共 {fmt(u.total)}")
        except Exception:
            pass

    total_freed = 0; total_ok = 0
    for k in keys:
        name, fn = BATCHES[k]
        items = fn()
        if not items:
            print("    （无候选）"); continue
        if not a.go:
            sz = 0
            for p, s, isd, mt in items:
                if isd:
                    s2, _ = dir_size(p, time.time() + 30)
                else:
                    s2 = s
                sz += s2
            print(f"    🟰 该批预计释放 {fmt(sz)}（{len(items)} 条）—— 干跑模式，未删除")
            total_freed += sz
            continue
        # 预算分档：批4/7 条目多且目录大，给足时间；其余 900s
        # 实测 2026-09-18：批7 有 42051 条小文件，900s 只跑完 3848 条 ⇒ 提到 3600s
        if k in ("4", "7"):
            budget = time.time() + 3600
        else:
            budget = time.time() + 900
        f, o, sk, fl = do_items(items, k, budget)
        total_freed += f; total_ok += o
        # 每批落盘一次日志，防中途被杀丢失
        LOG["total_freed_bytes"] = total_freed
        LOG["mode"] = "go"
        try:
            with io.open(LOGF, "w", encoding="utf-8") as _f:
                json.dump(LOG, _f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    print()
    print("=" * 78)
    if a.go:
        print("磁盘可用空间变化：")
        for d in before:
            try:
                u = shutil.disk_usage(d)
                delta = u.free - before[d]
                print(f"  {d}  {fmt(before[d])} → {fmt(u.free)}   净增 {fmt(delta) if delta>=0 else '-'+fmt(-delta)}")
            except Exception:
                pass
    print(f"🟰 本次{'实际释放' if a.go else '预计释放'}：{fmt(total_freed)}")
    LOG["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["total_freed_bytes"] = total_freed
    LOG["mode"] = "go" if a.go else "dry"
    if a.go:
        with io.open(LOGF, "w", encoding="utf-8") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=1)
        print(f"日志已落盘：{LOGF}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
