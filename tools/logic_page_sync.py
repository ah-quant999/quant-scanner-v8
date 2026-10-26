#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""logic_page_sync.py — 逻辑详解页「双机分段协作协议」执行机件（v3）

主人令 2026-10-26：「逻辑详解页要你和小九重写协议，不要覆盖对方，但又能修改好后马上上线。」

────────────────────────────────────────────────────────────────────────────
病根（实证，不是猜测）
────────────────────────────────────────────────────────────────────────────
`E:\\Nutstore\\v8_logic_private\\logic.full.html` 是 790,208 字节 / 8,960 行的
**单文件**私享真源，双机经坚果云同步。两个人各自「整文件保存」时，同步盘只能
整份 last-writer-wins ⇒ **后保存者的版本必然吃掉对方改动**。
现有护栏 `guard_logic_full.py` 只看「字节数 ≥ 300000 + 有无禁删标记」，
对一个 227 行（约几 KB）的改动**完全无感** —— 这就是"改好了、第二天没了"的机制性原因。

────────────────────────────────────────────────────────────────────────────
协议（三段）
────────────────────────────────────────────────────────────────────────────
① **分段**：把 790KB 单文件按 `<div class="card">` 切成 100+ 个独立段文件
   （`sections/NNN_slug.html` + `manifest.json`）。谁改哪一段，动的是**不同文件**
   ⇒ 物理上不可能互相覆盖。切分必须**可逆**：`build` 重建结果与原文件逐字节相同
   （本机实测 sha256 一致才允许启用）。

② **立即生效**：改完任一段 → `build` 原子重建 `logic.full.html` → 双击
   `open_logic_detail.bat` 立刻看到；另一台机坚果云同步到 sections/ 后
   `watch` 自动重建（默认监视，无需谁去点）。**不再需要"改完等对方/问对方"**。

③ **同段冲突不丢**：两人改了同一段时，坚果云会产生冲突副本（`xxx (1).html` /
   `xxx (小九的冲突副本 2026-10-26).html`）。`conflicts` 检出 → `merge` 把两份
   并排保留（甲方块 + 乙方块，带 `data-nolost-conflict` 标记与时间戳），
   **先上线、后人工收口**，绝不整段替换、绝不静默丢一侧。

配套纪律（写进 docs/ops/DUAL_MACHINE_PROTOCOL.md §6）：
  · 禁止直接整份保存 logic.full.html；只改 sections/ 里的段。
  · 禁止删除/重排 manifest.json 里的段（重排会造成顺序错乱），新增段走 `split --add`。
  · 段标题行（`<h3>`/首行注释）保留原样，便于对方按标题定位。

用法：
  python3 tools/logic_page_sync.py split        # 首次切分（自动备份 + 可逆自证）
  python3 tools/logic_page_sync.py status       # 段清单 / 段数 / 总字节
  python3 tools/logic_page_sync.py verify       # 段级完整性（缺段/改段/断链）
  python3 tools/logic_page_sync.py build        # 重建 logic.full.html（原子写）
  python3 tools/logic_page_sync.py watch        # 常驻：sections/ 有变 → 自动 build
  python3 tools/logic_page_sync.py conflicts    # 检出坚果云冲突副本
  python3 tools/logic_page_sync.py merge        # 冲突副本并排保留（不丢一侧）
  python3 tools/logic_page_sync.py apply --section 042 --from 新段.html
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
# 私享目录：优先环境变量，其次本机坚果云，再其次冷备份目录
CANDIDATES = [
    os.environ.get("V8_LOGIC_DIR"),
    r"E:\Nutstore\v8_logic_private",
    r"E:\v8_logic_private",
    os.path.expanduser("~/Nutstore/v8_logic_private"),
]
DIR = next((p for p in CANDIDATES if p and os.path.isdir(p)), None)
PAGE = os.path.join(DIR, "logic.full.html") if DIR else None
SECDIR = os.path.join(DIR, "sections") if DIR else None
MANIFEST = os.path.join(SECDIR, "manifest.json") if DIR else None
CARD_RE = re.compile(r'<div\s+class="card(?:\s[^"]*)?"')
TITLE_RE = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)


def _now():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _read_bin(p):
    with open(p, "rb") as f:
        return f.read()


def _write_atomic(p, data):
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def _slug(t, i):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)[:18]
    return t or "part"


def split(force=False):
    if not PAGE or not os.path.isfile(PAGE):
        print("❌ 找不到 logic.full.html")
        return 1
    if os.path.isfile(MANIFEST) and not force:
        print("⚠️ 已有 sections/manifest.json；确认要重切请加 --force（会先备份现有 sections）")
        return 2
    raw = _read_bin(PAGE)
    text = raw.decode("utf-8")
    starts = [m.start() for m in CARD_RE.finditer(text)]
    if len(starts) < 20:
        print(f"❌ 卡片数异常（{len(starts)}），拒绝切分")
        return 1
    # 备份原文件
    bak = PAGE + ".bak-" + datetime.now(CST).strftime("%Y%m%d-%H%M%S")
    shutil.copy2(PAGE, bak)
    if os.path.isdir(SECDIR):
        shutil.move(SECDIR, SECDIR + ".bak-" + datetime.now(CST).strftime("%Y%m%d-%H%M%S"))
    os.makedirs(SECDIR, exist_ok=True)

    head = raw[:len(text[:starts[0]].encode("utf-8"))]
    tail_start = starts[-1]
    # 尾段：最后一个卡片之后的所有内容
    items, secs = [], []
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else len(text)
        body = text[st:en].encode("utf-8")
        seg = text[st:en]
        tm = TITLE_RE.search(seg)
        title = tm.group(1) if tm else seg[:60]
        name = "%03d_%s.html" % (i + 1, _slug(title, i))
        with open(os.path.join(SECDIR, name), "wb") as f:
            f.write(body)
        items.append({"idx": i + 1, "file": name, "bytes": len(body), "sha256": _sha(body),
                      "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()[:40]})
    # 尾：最后一个卡片结束到文末（无法从 starts 推出卡片结束位置，改用「整文件 - 前面所有字节」保证可逆）
    head_only = len(head) + sum(x["bytes"] for x in items)
    tail = raw[head_only:]
    with open(os.path.join(SECDIR, "000_head.html"), "wb") as f:
        f.write(head)
    with open(os.path.join(SECDIR, "999_tail.html"), "wb") as f:
        f.write(tail)

    man = {"_readme": "逻辑详解页分段清单。段=一个 div.card。禁止删段/重排；新增走 split --add。",
           "protocol": "docs/ops/DUAL_MACHINE_PROTOCOL.md §6",
           "generated": _now(),
           "source_sha256": _sha(raw), "source_bytes": len(raw),
           "head": {"file": "000_head.html", "bytes": len(head), "sha256": _sha(head)},
           "tail": {"file": "999_tail.html", "bytes": len(tail), "sha256": _sha(tail)},
           "sections": items}
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 可逆自证
    rebuilt = head + b"".join(_read_bin(os.path.join(SECDIR, x["file"])) for x in items) + tail
    ok = _sha(rebuilt) == _sha(raw)
    print(f"✅ 切分完成：{len(items)} 段 + head/tail，原文件已备份 {os.path.basename(bak)}")
    print(f"   可逆自证：重建 sha256 {'一致 ✅' if ok else '不一致 ❌'}（{len(raw)} 字节）")
    return 0 if ok else 1


def load_manifest():
    if not MANIFEST or not os.path.isfile(MANIFEST):
        return None
    return json.load(open(MANIFEST, encoding="utf-8"))


def status():
    man = load_manifest()
    if not man:
        print("未切分（无 sections/manifest.json）")
        return 1
    n = len(man["sections"])
    tot = man["head"]["bytes"] + man["tail"]["bytes"] + sum(s["bytes"] for s in man["sections"])
    print(f"目录: {DIR}")
    print(f"段数: {n} | 合计 {tot} 字节 | 切分时刻 {man['generated']}")
    if os.path.isfile(PAGE):
        cur = _read_bin(PAGE)
        print(f"当前 logic.full.html: {len(cur)} 字节 | 与切分时{'一致 ✅' if _sha(cur)==man['source_sha256'] else '已不同（正常：改过段后需 build）'}")
    print("前 5 段:", ", ".join(s["file"] for s in man["sections"][:5]))
    return 0


def verify():
    man = load_manifest()
    if not man:
        print("未切分")
        return 1
    miss, changed = [], []
    for s in man["sections"]:
        p = os.path.join(SECDIR, s["file"])
        if not os.path.isfile(p):
            miss.append(s["file"])
            continue
        if _sha(_read_bin(p)) != s["sha256"]:
            changed.append({"file": s["file"], "title": s["title"]})
    for k in ("head", "tail"):
        p = os.path.join(SECDIR, man[k]["file"])
        if not os.path.isfile(p):
            miss.append(man[k]["file"])
    print(f"段数期望 {len(man['sections'])} | 缺失 {len(miss)} | 内容已改 {len(changed)}")
    for m in miss[:10]:
        print("  ❌ 缺:", m)
    for c in changed[:15]:
        print("  ✏️ 改:", c["file"], "|", c["title"])
    if not miss and not changed:
        print("✅ 与基线完全一致")
    return 0 if not miss else 1


def build(quiet=False):
    man = load_manifest()
    if not man:
        print("未切分，无法 build")
        return 1
    parts = [_read_bin(os.path.join(SECDIR, man["head"]["file"]))]
    miss = []
    for s in man["sections"]:
        p = os.path.join(SECDIR, s["file"])
        if not os.path.isfile(p):
            miss.append(s["file"])
            parts.append(b"")           # 缺段不阻断上线，但明确报出来
            continue
        parts.append(_read_bin(p))
    parts.append(_read_bin(os.path.join(SECDIR, man["tail"]["file"])))
    data = b"".join(parts)
    _write_atomic(PAGE, data)
    if not quiet:
        print(f"✅ 已重建 logic.full.html：{len(data)} 字节 / {len(man['sections'])} 段（{_now()}）")
        if miss:
            print(f"⚠️ {len(miss)} 个段文件缺失（已按空处理，请尽快补齐）: {miss[:5]}")
        print("   → 双击 open_logic_detail.bat 即见最新版本（无需等对方）")
    return 0


def watch(interval=5):
    print(f"[{_now()}] 监听 {SECDIR}，{interval}s 一轮；Ctrl+C 退出")
    last = None
    while True:
        try:
            man = load_manifest()
            if man:
                sig = tuple((s["file"], os.path.getmtime(os.path.join(SECDIR, s["file"])))
                            for s in man["sections"] if os.path.isfile(os.path.join(SECDIR, s["file"])))
                if sig != last:
                    if last is not None:
                        build(quiet=True)
                        print(f"[{_now()}] 检测到段变更 → 已重建 logic.full.html")
                    last = sig
        except Exception as e:
            print(f"[{_now()}] watch 异常: {e}")
        time.sleep(interval)


def find_conflicts():
    """坚果云冲突副本：文件名含 (1)/(2)/冲突/conflict/机器名 等。"""
    out = []
    if not DIR:
        return out
    pats = re.compile(r"(\(\d+\)|冲突|conflict|副本)", re.I)
    for dp, dn, fn in os.walk(DIR):
        if "sections.bak" in dp or ".bak-" in dp:
            continue
        for n in fn:
            if n.endswith(".html") and pats.search(n):
                out.append(os.path.join(dp, n))
    return out


def conflicts():
    cs = find_conflicts()
    if not cs:
        print("✅ 未发现冲突副本")
        return 0
    print(f"⚠️ 发现 {len(cs)} 个疑似冲突副本：")
    for c in cs:
        print("  -", os.path.relpath(c, DIR), os.path.getsize(c), "字节")
    print("\n下一步：python3 tools/logic_page_sync.py merge  →  并排保留后 build 上线")
    return 1


def merge():
    """把冲突副本并排插入（不丢任何一侧），随后 build 上线。"""
    cs = find_conflicts()
    if not cs:
        print("✅ 无冲突副本，无需合并")
        return 0
    man = load_manifest()
    if not man:
        print("未切分")
        return 1
    done = []
    for c in cs:
        base = os.path.basename(c)
        # 找到最相近的段：按标题关键字匹配，匹配不到就追加为新段（不覆盖任何东西）
        body = _read_bin(c)
        tm = TITLE_RE.search(body.decode("utf-8", "replace"))
        title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else base
        target = None
        for s in man["sections"]:
            if s["title"] and (s["title"] in title or title in s["title"]):
                target = s
                break
        if target:
            p = os.path.join(SECDIR, target["file"])
            cur = _read_bin(p)
            merged = (cur
                      + b"\n<!-- nolost-conflict: \xe4\xbf\x9d\xe7\x95\x99\xe4\xb8\xa4\xe4\xbb\xbd "
                      + base.encode("utf-8") + b" @ " + _now().encode() + b" -->\n"
                      + body)
            _write_atomic(p, merged)
            done.append(("并排保留", target["file"], base))
        else:
            idx = len(man["sections"]) + 1
            name = "%03d_conflict_%s.html" % (idx, _slug(title, idx))
            _write_atomic(os.path.join(SECDIR, name), body)
            man["sections"].append({"idx": idx, "file": name, "bytes": len(body),
                                    "sha256": _sha(body), "title": title[:40]})
            done.append(("新增段", name, base))
        os.rename(c, c + ".merged")
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for how, tgt, src in done:
        print(f"  ✅ {how}: {src} → {tgt}")
    build()
    print("⚠️ 已先上线；并排的双份内容请人工收口（删掉不要的那份再 build 一次）")
    return 0


def apply_section(sec=None, src=None):
    man = load_manifest()
    if not man or not sec:
        print("用法: apply --section 042 --from 新段.html")
        return 2
    target = None
    for s in man["sections"]:
        if s["file"].startswith(sec) or str(s["idx"]).zfill(3) == sec:
            target = s
            break
    if not target:
        print("找不到段:", sec)
        return 1
    body = _read_bin(src)
    _write_atomic(os.path.join(SECDIR, target["file"]), body)
    print(f"✅ 已替换段 {target['file']}（{len(body)} 字节）")
    return build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?",
                    choices=["split", "status", "verify", "build", "watch", "conflicts", "merge", "apply"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--section")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--interval", type=int, default=5)
    a = ap.parse_args()
    if not DIR:
        print("❌ 找不到私享目录（设置 V8_LOGIC_DIR 环境变量）")
        return 2
    cmd = a.cmd or "status"
    if cmd == "split":
        return split(a.force)
    if cmd == "status":
        return status()
    if cmd == "verify":
        return verify()
    if cmd == "build":
        return build()
    if cmd == "watch":
        return watch(a.interval) or 0
    if cmd == "conflicts":
        return conflicts()
    if cmd == "merge":
        return merge()
    if cmd == "apply":
        return apply_section(a.section, a.src)


if __name__ == "__main__":
    sys.exit(main())
