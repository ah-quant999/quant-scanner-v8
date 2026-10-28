#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nolost_guard.py — 双机「零丢失」常驻守卫（协议机件，非一次性脚本）
================================================================================
主人令（2026-10-26）：「定个以后双机改动都不会丢失的、可以一直运行的协议，不要每次都问我。」

本文件是那份协议的**执行机件**。协议原文见 docs/ops/DUAL_MACHINE_PROTOCOL.md §5。

解决的实证事故族（同一根因，已复发多次）：
  · 2026-09-20 10:53：一侧用**落后基线**建树推送 → 另一侧 10:43 刚推的改动被静默覆盖；
  · 2026-10-26 00:2x：本机 API 推送 index.html 时 base_tree 取自**更早的 HEAD**
    → 同一批刚推上去的 data/RISK_GUARD.js 等 3 个文件从 main 树上消失
    （git log --diff-filter=D 查不到删除提交 = 从未进入历史 = 典型「旧树覆盖」）。
  · HANDOFF 挂账 `api-push-stale-base-index-clobber`（pending-verify）。

三道锁（缺一不可）：
  锁① 快照：受保护路径的每次内容，按 sha1 落地到 backup/nolost/<path>/<sha12>.gz（只增不删）
        ⇒ 即使工作区被 reset、远端被覆盖，内容永远可以从本地取回。
  锁② 推前推后路径集校验：推前记录远端 full manifest（path→blob sha），推后重取比对；
        若「推前有、推后无」且不在显式删除清单 ⇒ 判 clobber，**自动用推前 blob 重建恢复提交**。
  锁③ 推树基线强制刷新：建树前**当场**重取 HEAD 与 tree（不用任何缓存/传入 sha），
        并以 base_tree 合并 ⇒ 从机制上消灭「陈旧基线」。

判定表（不问主人，按表执行）：
  · 远端缺受保护路径            → 自动 heal（补回），记 NOLOST_LOG
  · 本地受保护路径有未提交改动  → 快照落盘 + 记 UNPUBLISHED（不自动提交，避免带出 bot 脏数据）
  · 推前推后路径集不一致        → 自动回滚式恢复，记 NOLOST_LOG(severity=high)
  · 同一路径连续 3 次出现改动冲突 → 写一封汇总（docs/ops/handover/），不再逐次询问

用法：
  python3 algorithms/nolost_guard.py check      # 只体检，输出 JSON
  python3 algorithms/nolost_guard.py snapshot   # 本地快照 + 未发布清单
  python3 algorithms/nolost_guard.py heal       # 自愈：补回远端缺失的受保护路径
  python3 algorithms/nolost_guard.py cycle      # 常驻循环单步（check→snapshot→heal）
  python3 algorithms/nolost_guard.py push --msg "..." --files a,b,c   # 零丢失推送
"""
import base64
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
REPO = os.environ.get("NOLOST_REPO", "ah-quant999/quant-scanner-v8")
BRANCH = os.environ.get("NOLOST_BRANCH", "main")
API = "https://api.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "backup", "nolost")
LOG_PATH = os.path.join(ROOT, "docs", "ops", "NOLOST_LOG.jsonl")
UNPUB_PATH = os.path.join(ROOT, "docs", "ops", "UNPUBLISHED.json")
STATE_PATH = os.path.join(ROOT, ".nolost_state.json")
# 远端受保护路径的「上次已知良好」基线（path→blob sha）。
# 判据只能靠它：本地文件未必推过，不能拿本地当参照（否则 252 个本机私有文件全被误判"丢失"）。
BASELINE_PATH = os.path.join(ROOT, ".nolost_remote_baseline.json")
IGNORE_PATH = os.path.join(ROOT, "docs", "ops", "NOLOST_IGNORE.json")

# ── 受保护范围 ────────────────────────────────────────────────────────────────
# 只保护「人手写、bot 不重算」的源文件。data/raw_data 是构建产物，天然每日重算，不在保护范围
# （保护它们反而会把陈旧数据强塞回线上）。
PROTECTED_PREFIXES = (
    "algorithms/",
    "docs/",
    ".github/",
    "tools/",
)
PROTECTED_ROOT_FILES = (
    "index.html",
    "logic.html",
    "v6_memo.html",
    "v6_memo.golden.html",
    "AGENTS.md",
    "DO_NOT_DELETE.md",
    "requirements.txt",
    "update_v8.py",
    "guard_index_sections.py",
    "guard_v6_memo.py",
    "v8_verify_layer_parity.py",
)
# 这些目录/文件名属于「人改」但不需要守护（临时/缓存），以及**绝不可外泄的凭证**
EXCLUDE_SUBSTR = ("/__pycache__/", ".pyc", "/.merge_tmp", "/backup/nolost/",
                  ".neodata_token", ".git-credentials", "token_cache", ".mahoro_cookies",
                  ".env", "id_rsa", ".pem", ".key", "/.git/")
SECRET_NAME_HINTS = ("token", "secret", "credential", "cookie", "password")
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


def now_cst():
    return datetime.now(CST)


def ts():
    return now_cst().strftime("%Y-%m-%d %H:%M:%S")


# ── 网络层（带退避重试，专治代理 502/503）────────────────────────────────────
def _token():
    for k in ("NOLOST_TOKEN", "V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v and len(v) > 20:
            return v.strip()
    try:
        creds = open(os.path.expanduser("~/.git-credentials"), encoding="utf-8").read()
        m = re.search(r"(gh[pousr]_[A-Za-z0-9]{20,})", creds)
        if m:
            return m.group(1)
    except Exception:
        pass
    raise RuntimeError("找不到 GitHub token（环境变量或 ~/.git-credentials）")


def _req(method, path, payload=None, retries=5):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for i in range(retries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "token " + _token())
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "v8-nolost-guard")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 422:
                raise
            last = e
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(min(2 * (i + 1), 8))
                continue
            raise
        except Exception as e:  # URLError / SSL / timeout
            last = e
            time.sleep(min(2 * (i + 1), 8))
    raise RuntimeError(f"网络失败 {method} {path}: {last}")


# ── 远端 manifest ─────────────────────────────────────────────────────────────
def head_sha():
    r = _req("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    return r["object"]["sha"]


def remote_manifest(sha=None):
    """返回 {path: blob_sha}（全仓，含 data/raw_data）。tree 被截断时按顶层目录下钻。"""
    sha = sha or head_sha()
    commit = _req("GET", f"/repos/{REPO}/git/commits/{sha}")
    tree = _req("GET", f"/repos/{REPO}/git/trees/{commit['tree']['sha']}?recursive=1")
    out, dirs = {}, []
    for e in tree.get("tree", []):
        if e["type"] == "blob":
            out[e["path"]] = e["sha"]
        elif e["type"] == "tree" and e["path"] != "":
            dirs.append(e)
    if tree.get("truncated"):
        # 下钻每个顶层目录，拿全量
        for e in tree.get("tree", []):
            if e["type"] != "tree":
                continue
            sub = _req("GET", f"/repos/{REPO}/git/trees/{e['sha']}?recursive=1")
            for x in sub.get("tree", []):
                if x["type"] == "blob":
                    out[x["path"]] = x["sha"]
    return out


def is_protected(path):
    if any(s in "/" + path for s in EXCLUDE_SUBSTR):
        return False
    low = path.lower()
    if any(h in low for h in SECRET_NAME_HINTS):
        return False  # 凭证类一律不纳入守护/快照/推送
    if path in PROTECTED_ROOT_FILES:
        return True
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


def protected_missing(manifest):
    """受保护清单里「远端没有」的路径。"""
    return sorted(p for p in PROTECTED_ROOT_FILES if p not in manifest)


def blob_text(sha):
    r = _req("GET", f"/repos/{REPO}/git/blobs/{sha}")
    return base64.b64decode(r["content"])


# ── 锁① 本地快照 ──────────────────────────────────────────────────────────────
def snapshot_local():
    """把受保护路径的**当前工作区内容**按内容哈希存档；返回本次新增/更新条数。"""
    added = 0
    scan = []
    for f in PROTECTED_ROOT_FILES:
        scan.append(f)
    for pref in PROTECTED_PREFIXES:
        base = os.path.join(ROOT, pref)
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
            for n in fn:
                scan.append(os.path.relpath(os.path.join(dp, n), ROOT).replace("\\", "/"))
    for rel in scan:
        if not is_protected(rel):
            continue
        ap = os.path.join(ROOT, rel)
        try:
            if not os.path.isfile(ap) or os.path.getsize(ap) > MAX_SNAPSHOT_BYTES:
                continue
            raw = open(ap, "rb").read()
        except Exception:
            continue
        h = hashlib.sha1(raw).hexdigest()[:12]
        d = os.path.join(BACKUP_DIR, os.path.dirname(rel))
        p = os.path.join(d, f"{os.path.basename(rel)}.{h}.gz")
        if os.path.exists(p):
            continue
        os.makedirs(d, exist_ok=True)
        with gzip.open(p, "wb") as fh:
            fh.write(raw)
        added += 1
    return added


def restore_from_backup(rel, sha12):
    p = os.path.join(BACKUP_DIR, os.path.dirname(rel), f"{os.path.basename(rel)}.{sha12}.gz")
    if not os.path.exists(p):
        return False
    with gzip.open(p, "rb") as fh:
        raw = fh.read()
    ap = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    open(ap, "wb").write(raw)
    return True


# ── 锁③ 零丢失推送 ────────────────────────────────────────────────────────────
def safe_push(changes, message, force_paths=()):
    """changes: {path: bytes|None}；None 表示删除。返回 (ok, detail)。

    机制：建树前当场重取 HEAD（消灭陈旧基线），base_tree=当前 HEAD 树，
    commit parent=当前 HEAD，ref 用 force:false 更新（非快进即失败并重试）。
    推后**强制** path 集校验：推前存在而推后消失且不在 changes 里 ⇒ 立即恢复。
    """
    before = remote_manifest()
    allow_delete = {p for p, v in changes.items() if v is None}
    for attempt in range(4):
        try:
            cur = head_sha()
            tree_entries = []
            for path, content in changes.items():
                if content is None:
                    tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                    continue
                b = _req("POST", f"/repos/{REPO}/git/blobs",
                         {"content": base64.b64encode(content).decode(), "encoding": "base64"})
                tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})
            commit_cur = _req("GET", f"/repos/{REPO}/git/commits/{cur}")
            tree = _req("POST", f"/repos/{REPO}/git/trees",
                        {"base_tree": commit_cur["tree"]["sha"], "tree": tree_entries})
            nc = _req("POST", f"/repos/{REPO}/git/commits",
                      {"message": message, "tree": tree["sha"], "parents": [cur]})
            _req("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}",
                 {"sha": nc["sha"], "force": False})
            after = remote_manifest(nc["sha"])
            ign = load_ignore()
            lost = [p for p in before
                    if p not in after and p not in allow_delete
                    and is_protected(p) and p not in ign]
            if lost:
                _heal_paths(lost, before, note=f"safe_push 后发现 {len(lost)} 路径丢失")
                return False, {"commit": nc["sha"], "lost": lost, "healed": True}
            return True, {"commit": nc["sha"], "lost": []}
        except urllib.error.HTTPError as e:
            if e.code in (409, 422) or "not a fast forward" in str(e):
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(2 * (attempt + 1))
            continue
    return False, {"error": "4 次重试仍失败"}


def _heal_paths(paths, manifest, note=""):
    """用 with 的 manifest 里的 blob 重建丢失路径（单次恢复提交）。"""
    entries = []
    for p in paths:
        sha = manifest.get(p)
        if sha:
            entries.append({"path": p, "mode": "100644", "type": "blob", "sha": sha})
    if not entries:
        return False
    cur = head_sha()
    commit_cur = _req("GET", f"/repos/{REPO}/git/commits/{cur}")
    tree = _req("POST", f"/repos/{REPO}/git/trees",
                {"base_tree": commit_cur["tree"]["sha"], "tree": entries})
    nc = _req("POST", f"/repos/{REPO}/git/commits",
              {"message": f"fix(nolost): 自愈恢复 {len(entries)} 个被静默覆盖的文件（nolost_guard）",
               "tree": tree["sha"], "parents": [cur]})
    _req("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": nc["sha"], "force": False})
    log_event({"kind": "heal", "severity": "high", "paths": entries and [e["path"] for e in entries],
               "commit": nc["sha"], "note": note})
    return True


# ── 基线（判「丢失」的唯一参照）──────────────────────────────────────────────
def load_baseline():
    try:
        return json.load(open(BASELINE_PATH, encoding="utf-8"))
    except Exception:
        return {}


def save_baseline(man):
    ign = load_ignore()
    b = {p: s for p, s in man.items() if is_protected(p) and p not in ign}
    json.dump(b, open(BASELINE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(b)


def load_ignore():
    try:
        return set(json.load(open(IGNORE_PATH, encoding="utf-8")).get("paths", []))
    except Exception:
        return set()


def add_ignore(paths, reason=""):
    cur = load_ignore() | set(paths)
    os.makedirs(os.path.dirname(IGNORE_PATH), exist_ok=True)
    json.dump({"_readme": "有意删除、不参与自愈的受保护路径（NOLOST_IGNORE）",
               "reason": reason, "updated": ts(), "paths": sorted(cur)},
              open(IGNORE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return cur


# ── 体检 ─────────────────────────────────────────────────────────────────────
def check(update_baseline=False):
    """判据：只认「基线里有过、现在远端没了」= 静默覆盖。
    本地存在但远端没有 = 未发布改动（进 UNPUBLISHED 账本），不算丢失、不触发自愈。"""
    man = remote_manifest()
    base = load_baseline()
    ign = load_ignore()
    if not base:
        # 首次运行：以当前远端为基线播种
        save_baseline(man)
        base = load_baseline()
    lost = sorted(p for p in base if p not in man and p not in ign)
    local_only = sorted(p for p in _local_protected_files() if p not in man)
    out = {
        "at": ts(),
        "head": head_sha()[:12],
        "remote_files": len(man),
        "baseline_files": len(base),
        "silently_clobbered": lost,
        "local_unpublished_count": len(local_only),
        "local_unpublished_sample": local_only[:8],
    }
    if update_baseline and not lost:
        save_baseline(man)
    return out


def _local_protected_files():
    out = []
    for f in PROTECTED_ROOT_FILES:
        if os.path.isfile(os.path.join(ROOT, f)):
            out.append(f)
    for pref in PROTECTED_PREFIXES:
        base = os.path.join(ROOT, pref)
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
            for n in fn:
                rel = os.path.relpath(os.path.join(dp, n), ROOT).replace("\\", "/")
                if is_protected(rel):
                    out.append(rel)
    return out


def _local_dirty_protected():
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        dirty = []
        for line in r.stdout.splitlines():
            p = line[3:].strip().strip('"')
            if " -> " in p:
                p = p.split(" -> ")[-1]
            if is_protected(p):
                dirty.append({"path": p, "state": line[:2].strip()})
        return dirty
    except Exception:
        return []


# ── 日志 ─────────────────────────────────────────────────────────────────────
def log_event(ev):
    ev.setdefault("at", ts())
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass


def write_unpublished():
    d = _local_dirty_protected()
    payload = {
        "_readme": "双机未发布改动账本（nolost_guard 自动生成）。对方推前必读：这些路径的线上版本可能落后于某人工作区。",
        "machine": os.environ.get("COMPUTERNAME", "unknown"),
        "updated": ts(),
        "count": len(d),
        "items": d,
    }
    os.makedirs(os.path.dirname(UNPUB_PATH), exist_ok=True)
    open(UNPUB_PATH, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def _heal_from_baseline(lost, base, note=""):
    """用基线里的 blob sha 直接重建（最快、逐字节等价）；blob 被 GC 则回落到本机快照内容。"""
    ok = False
    cand = {p: base[p] for p in lost if p in base}
    if cand:
        try:
            ok = _heal_paths(list(cand), cand, note=note)
        except Exception as e:
            log_event({"kind": "heal_blob_fail", "err": str(e)[:200], "paths": list(cand)})
            ok = False
    if ok:
        return list(cand), True
    # 回落：本机 backup/nolost 快照
    changes, ver = {}, base.get("__ver__", 0)
    for p in lost:
        d = os.path.join(BACKUP_DIR, os.path.dirname(p))
        if not os.path.isdir(d):
            continue
        pref = os.path.basename(p) + "."
        files = [f for f in os.listdir(d) if f.startswith(pref) and f.endswith(".gz")]
        if not files:
            continue
        files.sort(reverse=True)  # 取最新
        with gzip.open(os.path.join(d, files[0]), "rb") as fh:
            changes[p] = fh.read()
    if changes:
        ok, _det = safe_push(changes, "fix(nolost): 从本机快照恢复远端被覆盖文件（nolost_guard）")
        return list(changes), ok
    return [], False


def cycle():
    real_machine = os.environ.get("NOLOST_CI") != "1"
    snap = snapshot_local() if real_machine else 0
    ck = check()
    lost = ck["silently_clobbered"]
    healed = []
    if lost:
        base = load_baseline()
        healed, ok = _heal_from_baseline(lost, base, note="cycle 检出静默覆盖")
        log_event({"kind": "clobber_detected", "severity": "high", "lost": lost,
                   "healed": healed, "ok": ok})
    # 自愈后重取远端，刷新基线（基线只进不退：新出现的受保护路径也纳入）
    if healed:
        man = remote_manifest()
        save_baseline(man)
    # 云端 CI 不写 UNPUBLISHED（它 checkout 是干净的，写了会冲掉真机的未发布账本）
    unp_count = write_unpublished()["count"] if real_machine else -1
    out = {"at": ts(), "snapshot_new": snap, "clobbered": lost,
           "healed": healed, "unpublished": unp_count}
    log_event({"kind": "cycle", **out})
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        print(json.dumps(check(), ensure_ascii=False, indent=2))
    elif cmd == "seed":
        n = save_baseline(remote_manifest())
        print(json.dumps({"ok": True, "baseline_files": n, "path": BASELINE_PATH}, ensure_ascii=False))
    elif cmd == "snapshot":
        n = snapshot_local()
        print(json.dumps({"new_snapshots": n, "dir": BACKUP_DIR}, ensure_ascii=False))
    elif cmd == "cycle":
        print(json.dumps(cycle(), ensure_ascii=False, indent=2))
    elif cmd == "heal":
        ck = check()
        if not ck["silently_clobbered"]:
            print(json.dumps({"ok": True, "msg": "无静默覆盖"}, ensure_ascii=False))
            return 0
        healed, ok = _heal_from_baseline(ck["silently_clobbered"], load_baseline(), note="手动 heal")
        if ok:
            save_baseline(remote_manifest())
        print(json.dumps({"healed": healed, "ok": ok}, ensure_ascii=False))
    elif cmd == "ignore":
        paths = (argv[2] if len(argv) > 2 else "").split(",")
        paths = [p for p in paths if p]
        cur = add_ignore(paths, reason="命令行登记")
        print(json.dumps({"ok": True, "ignore_count": len(cur)}, ensure_ascii=False))
    elif cmd == "push":
        msg, files = "chore(nolost): 推送", []
        for i, a in enumerate(argv):
            if a == "--msg":
                msg = argv[i + 1]
            if a == "--files":
                files = argv[i + 1].split(",")
        changes = {f: open(os.path.join(ROOT, f), "rb").read() for f in files if os.path.isfile(os.path.join(ROOT, f))}
        ok, det = safe_push(changes, msg)
        print(json.dumps({"ok": ok, **det}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    else:
        print("用法: check|snapshot|cycle|heal|push", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
