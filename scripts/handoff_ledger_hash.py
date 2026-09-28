# -*- coding: utf-8 -*-
"""handoff_ledger_hash.py — HANDOFF ledger 内容哈希的**唯一口径实现**（双机共用）。

为什么要有这个仓内脚本（2026-09-23 收口）：
    原先口径只存在于「各机 `~/.workbuddy/scripts/v8_handoff_edit_kit.py`」这一**本机副本**里，
    而 `docs/ops/HANDOFF.ledger.json` 的 `id_content_hash_note` 又对口径另有一份**文字描述**。
    实测两者**不一致**（描述说「剔除块尾分隔注释」，实现却没剔），且线上 62 项哈希
    与 13 种候选口径**全部 0 命中** ⇒ 口径不可复现、防覆盖能力静默失效。
    本脚本把口径**落到仓内、只此一份**，双机 pull 后行为必然一致。

口径（权威定义，逐条可验）：
    1. 取 item 块 = 从 `  - id: <iid>` 行起，到下一个 `  - id:` 行之前（或文件末）；
    2. **剔除块尾的「空行」与「以 # 开头的注释行」**（循环直到遇到实义行）——
       消除「新 item 连同其前导分隔注释被算进上一个 item 块尾」造成的假阳性；
    3. 把块内**所有** `updated:` 行的值归一化为字面量 `<ts>`（保留键名与缩进，抹掉时间漂移）；
    4. `rstrip()` 去尾部空白；
    5. `sha256(utf-8).hexdigest()[:16]`。

用法：
    python scripts/handoff_ledger_hash.py --check      # 只比对，打印命中率（不改文件）
    python scripts/handoff_ledger_hash.py --fix        # 全量重算并写入 ledger（原子写+回读校验）
    python scripts/handoff_ledger_hash.py --ids        # 附带列出未收录哈希的 id
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML_PATH = os.path.join(ROOT, "docs", "ops", "HANDOFF.yaml")
LEDGER_PATH = os.path.join(ROOT, "docs", "ops", "HANDOFF.ledger.json")

ID_RE = re.compile(r"(?m)^  - id:\s*(\S+)\s*$")
UPD_RE = re.compile(r"^(\s*updated:\s*).*$", re.M)


def item_ids(text: str) -> list[str]:
    return [m.group(1) for m in ID_RE.finditer(text)]


def _strip_tail_block(blk: str) -> str:
    """口径第 2 步：剔除块尾空行与 # 注释行。"""
    lines = blk.split("\n")
    while lines:
        s = lines[-1].strip()
        if s == "" or s.startswith("#"):
            lines.pop()
        else:
            break
    return "\n".join(lines)


def item_block(text: str, want: str) -> str:
    hits = [(m.start(), m.group(1)) for m in ID_RE.finditer(text)]
    for i, (pos, iid) in enumerate(hits):
        if iid == want:
            return text[pos:(hits[i + 1][0] if i + 1 < len(hits) else len(text))]
    raise KeyError(want)


def content_hash(text: str, iid: str) -> str:
    """口径第 1~5 步。"""
    blk = _strip_tail_block(item_block(text, iid))
    blk = UPD_RE.sub(r"\g<1><ts>", blk)
    return hashlib.sha256(blk.rstrip().encode("utf-8")).hexdigest()[:16]


def _read(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def _atomic_write(path: str, body: str) -> None:
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".led_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    if _read(path) != body:
        raise RuntimeError("回读不一致，写入被拒")


def _git(*args, timeout=60):
    """返回 (rc, bytes)。git 不可用/超时 ⇒ (None, b'')。"""
    import subprocess
    try:
        p = subprocess.run(["git", "-C", ROOT] + list(args),
                           capture_output=True, timeout=timeout)
        return p.returncode, p.stdout
    except Exception:
        return None, b""


def _remote_baseline_check():
    """🔴 fix(B) 写侧硬预检（2026-09-28 22:1x 阿狸咪的工程师 落码）。

    背景（当日第 5 次复发，写入方脚本已定位）：
      `E:\\_alimi_tools\\_patch_finalrec_ledger_1933.py`（20:43:12）直接读**本机工作树**
      `docs/ops/HANDOFF.yaml`（当时停在 09-27 22:00 快照 / next_id_seq=91）当基底，
      追加 1 项后覆写并推送 ⇒ 相对远端 107 项 **静默删掉 3 个 item + 6 个判据键**，
      其自身 `assert 'next_id_seq: 91' in s` 因「基底本就是 91」而**照常通过**。

    本函数把 skill §铁律 1「基底必须取远端 API，禁本机副本」变成**可执行硬拒**：
      本地 HANDOFF.yaml 原始字节 != `origin/main:docs/ops/HANDOFF.yaml` 原始字节
      ⇒ 判「本地基陈旧」，`--fix` **拒绝执行**（exit 2），既不改 YAML 也不改 ledger。

    fail-open：无 git / fetch 失败 / 浅克隆读不到 ⇒ 返回 (True, '跳过…')，只告警放行，
    以免误伤离线 CI 与只读巡检。
    """
    rc, _ = _git("fetch", "origin", "main", "-q", timeout=60)
    if rc is None:
        return True, "跳过（git 不可用或超时）"
    rc, remote = _git("show", "origin/main:docs/ops/HANDOFF.yaml", timeout=30)
    if rc != 0 or not remote:
        return True, "跳过（读不到 origin/main:docs/ops/HANDOFF.yaml，rc=%s）" % rc
    with open(YAML_PATH, "rb") as f:
        local = f.read()
    h = lambda b: hashlib.sha256(b).hexdigest()[:12]
    if local != remote:
        return False, ("🔴 本地 HANDOFF.yaml 基陈旧：本地 %d B / sha256=%s  !=  "
                       "origin/main %d B / sha256=%s" % (len(local), h(local), len(remote), h(remote)))
    return True, "✅ 本地基底 == origin/main（%d B / sha256=%s）" % (len(local), h(local))


def _history_shrink_report():
    """非阻断「历史收缩」报告：把 origin/main 上 HANDOFF.yaml **最近两版** 的 id 集合相比，
    列出「上一版有、这一版无」的 id。用于在**不冻结部署**的前提下把「陈旧副本整文件覆盖」喊出来。"""
    rc, out = _git("log", "origin/main", "-n", "2", "--format=%H", "--", "docs/ops/HANDOFF.yaml", timeout=30)
    if rc != 0 or not out:
        return None
    shas = [x for x in out.decode("utf-8", "ignore").split() if x]
    if len(shas) < 2:
        return None
    rc, prev = _git("show", "%s:docs/ops/HANDOFF.yaml" % shas[1], timeout=30)
    if rc != 0 or not prev:
        return None
    prev_ids = [m.group(1) for m in ID_RE.finditer(prev.decode("utf-8", "ignore"))]
    rc, cur = _git("show", "%s:docs/ops/HANDOFF.yaml" % shas[0], timeout=30)
    if rc != 0 or not cur:
        return None
    cur_ids = [m.group(1) for m in ID_RE.finditer(cur.decode("utf-8", "ignore"))]
    gone = [i for i in prev_ids if i not in set(cur_ids)]
    return (shas[0][:12], shas[1][:12], len(prev_ids), len(cur_ids), gone)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--ids", action="store_true")
    a = ap.parse_args()
    if not (a.check or a.fix):
        a.check = True

    base_ok, base_msg = _remote_baseline_check()
    print("[基线预检] " + base_msg)
    if not base_ok:
        if a.fix:
            print("\n🔴 [--fix 已拒] 本地基陈旧：若在此基上重算 ledger，会把「远端已有、本地没有」的条目"
                  "\n   连锚一起回退（[13/13] 门禁将全程无感）⇒ 本工具按 skill §铁律 1 硬拒写入。"
                  "\n   正解：先 `git show origin/main:docs/ops/HANDOFF.yaml > docs/ops/HANDOFF.yaml`"
                  "（或按 API 路径重取远端内容）再重放你自己的改动，然后重跑本脚本。")
            return 2
        print("🔴 [--check] 继续只读比对，但**结论不可信**（基线落后远端）⇒ 先同步基底再判读。")

    rep = _history_shrink_report()
    if rep:
        s0, s1, n0, n1, gone = rep
        print("[历史收缩] origin/main 最近两版 HANDOFF.yaml：%s(%d 项) <- %s(%d 项)  消失 id=%s"
              % (s0, n1, s1, n0, gone if gone else "无"))
        if gone:
            print("   🔴 有 item 从状态源消失 ⇒ 疑似「陈旧副本整文件覆盖」（当日已复发 5 次）。"
                  "\n      判据/处置见 docs/ops/HANDOFF.yaml 的 handoff-yaml-stale-base-item-drop。")

    y = _read(YAML_PATH)
    led_text = _read(LEDGER_PATH)
    led = json.loads(led_text)
    ids = item_ids(y)
    calc = {i: content_hash(y, i) for i in ids}
    old = led.get("id_content_hashes") or {}

    common = [i for i in ids if i in old]
    hit = [i for i in common if old[i] == calc[i]]
    miss = [i for i in common if old[i] != calc[i]]
    missing = [i for i in ids if i not in old]
    print("YAML items = %d | ledger ids = %d | ledger hashes = %d" % (len(ids), len(led.get("ids") or []), len(old)))
    print("命中 = %d/%d | 失配 = %d | 未收录 = %d" % (len(hit), len(common), len(miss), len(missing)))
    if a.ids or miss:
        for i in miss[:10]:
            print("   MISS %-42s old=%s new=%s" % (i, old[i], calc[i]))
        for i in missing[:10]:
            print("   NEW  %-42s new=%s" % (i, calc[i]))

    if not a.fix:
        print("\n[--check] 未改动任何文件。" + ("" if not miss and not missing else "（口径失配 ⇒ 需 --fix 收口）"))
        return 0

    tail = "\n" if led_text.endswith("\n") else ""
    gen = dict(led)
    gen["ids"] = ids
    gen["id_content_hashes"] = {k: calc[k] for k in sorted(calc)}
    # ⚠️ 锚值取 YAML 的 meta.next_id_seq（**不是** len(ids)）—— 两者语义不同：
    #   len(ids) 是「条目数」，next_id_seq 是「序号计数器」，历史上二者并不相等（items=68 时 seq=67）。
    #   取 len(ids) 会让锚值虚高，令 [13/13] 的 `meta.next_id_seq >= max_next_id_seq` 无端失败。
    # 🔴 2026-09-23 19:5x 小九修 bug：原正则写作 r"...next_id_seq://s*(//d+)//s*$"，
    #    `\s`/`\d` 被退化成字面量 `//s`/`//d`（heredoc 转义事故残留）⇒ **恒不匹配** ⇒ 静默走
    #    `len(ids)` 分支，上述"修正"实际从未生效（只因当时 items==seq==69 恰好相等而被掩盖）。
    #    现已改为正确转义；若再失配将打印告警而非静默回退。
    _m = re.search(r"(?m)^  next_id_seq:\s*(\d+)\s*$", y)
    if not _m:
        print("[warn] 未能从 meta 解析 next_id_seq ⇒ 回退 len(ids)=%d（请核查缩进）" % len(ids))
    _seq = int(_m.group(1)) if _m else len(ids)
    gen["max_next_id_seq"] = max(int(gen.get("max_next_id_seq") or 0), _seq)
    gen["updated"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = json.dumps(gen, ensure_ascii=False, indent=1) + tail
    json.loads(body)                       # 自校验：必须是合法 JSON
    _atomic_write(LEDGER_PATH, body)
    back = json.loads(_read(LEDGER_PATH))
    assert back["id_content_hashes"] == gen["id_content_hashes"], "回读哈希不一致"
    print("\n[--fix] ✅ 已写入 %d 项哈希（原子写 + 回读校验通过），updated=%s" % (len(calc), gen["updated"]))

    # 幂等自证：立刻用新文件重算一次，必须 100% 命中
    y2, led2 = _read(YAML_PATH), json.loads(_read(LEDGER_PATH))
    again = {i: content_hash(y2, i) for i in item_ids(y2)}
    ok = all(led2["id_content_hashes"].get(k) == v for k, v in again.items())
    print("[--fix] 幂等自证：重算 %d 项 %s" % (len(again), "100% 命中 ✅" if ok else "仍有失配 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
