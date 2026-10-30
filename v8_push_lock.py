#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_push_lock.py — 分布式推送锁（跨云 + 本地统一串行化 · 根治多写者抢 main）

════════════════════════════════════════════════════════════════════════════
【问题】quant-scanner-v8 的 main 分支被多路自动写者并发推送：
      · 云端 cn_fetch / algo / stock_quote / market_thermo …（经 api_push_raw.py，Git Data API）
      · 云端 cache-buster / backup / cleanup …（经 git CLI `git push`）
      · 本机（小九）经 v8_push_files.py（Git Data API）
   各路都「基底断言 + force:False」—— 安全（不会静默覆盖），但 main 一旦被别人推进
   就 422 / 拒绝重试 ⇒ 表现为「另一台机在抢 / 推送被拒 / 抖动」，且 git-CLI 的
   `reset --hard FETCH_HEAD` 重试环还可能丢弃并发方的改动。

【解法】在仓库内开一条专用锁分支 `v8-push-lock`，用 Git Data API 做**原子 CAS 锁**：
      · 取锁 = 在锁分支上提交一条 {holder, ts, action:"acquire"} 记录，
        并以「非 force」PATCH ref 从 current_sha → new_sha。
        GitHub 对 force:False 的 ref 更新要求「快进」；若期间别人改了锁分支
        （current_sha 已变）→ 422 → 重试。从而**至多一个持有者**。
      · 放锁 = 再提交一条 action:"release"，同样 CAS。
  这样无论写者来自云端 workflow 还是本机 agent，都先抢到这把锁才能推 main，
  从根本上消除并发竞态。

【铁律 · best-effort 绝不阻断】
      本锁是「串行化增强」，不是「推送前置条件」。任何异常 / 超时 / 网络错误
      ⇒ 一律**放行**（返回即可，调用方照常推送）。现有基底断言已防静默覆盖，
      没有锁只是回到「偶有 422 重试」的旧行为，绝不劣化。故本模块
      acquire/release **永不向调用方抛错**，CLI 退出码恒为 0。
════════════════════════════════════════════════════════════════════════════
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPO", "ah-quant999/quant-scanner-v8")
LOCK_REF = "refs/heads/v8-push-lock"        # 专用锁分支
LOCK_REF_SHORT = "v8-push-lock"
# GitHub 既有的「空树」常量：建锁分支根提交时复用，省一次 POST /git/trees（代理对大 body 偶发 502）
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
# token：环境变量优先，回退到与 v8_push_files.py 同源的本地文件（正斜杠，兼容 msys/win 双环境）
_TOK_FILES = [
    "E:/qs_workspaces/quant-scanner-v8/.workbuddy/v8_gh_token.txt",
    "/e/qs_workspaces/quant-scanner-v8/.workbuddy/v8_gh_token.txt",
    "E:/v8data/qs8-tmp/.workbuddy/v8_gh_token.txt",
    "/e/v8data/qs8-tmp/.workbuddy/v8_gh_token.txt",
    "C:/Users/Administrator/.workbuddy/scripts/.v8_gh_token.txt",
]
_TOKEN = None


def _load_tok():
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env and len(env) >= 20:
        _TOKEN = env
        return _TOKEN
    for fp in _TOK_FILES:
        try:
            if os.path.exists(fp):
                s = open(fp, "r", encoding="utf-8", errors="ignore").read().strip()
                if len(s) >= 20:
                    _TOKEN = s
                    return _TOKEN
        except Exception:
            continue
    return None


def _api(method, path, data=None, timeout=60):
    """极简 GitHub REST 封装；出错一律返回含 __error__ 的 dict，绝不抛。
    网络类 / 5xx / 429 退避重试（锁是 best-effort，但瞬断应自愈）。"""
    tok = _load_tok()
    if not tok:
        return {"__error__": "no_token"}
    url = API + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    last = None
    for _att in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            b = ""
            try:
                b = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            if e.code >= 500 or e.code == 429:
                last = {"__error__": e.code, "__msg__": b}
                if _att < 2:
                    time.sleep(2 ** _att)
                    continue
                return last
            return {"__error__": e.code, "__msg__": b}
        except Exception as e:  # noqa: BLE001
            last = {"__error__": "net", "__msg__": repr(e)[:200]}
            if _att < 2:
                time.sleep(2 ** _att)
                continue
            return last
    return last or {"__error__": "unknown"}


# ── 锁分支初始化（首次使用）──────────────────────────────────────────────
def _ensure_branch():
    """确保 v8-push-lock 分支存在；不存在则建一条孤儿根提交。返回 True/False。"""
    r = _api("GET", f"/repos/{REPO}/git/refs/heads/{LOCK_REF_SHORT}")
    if "__error__" not in r:
        return True
    # 404 → 创建
    # ① 根提交（orphan）：复用 GitHub 既有的空树常量，省一次 POST /git/trees
    c = _api("POST", f"/repos/{REPO}/git/commits",
             {"message": json.dumps({"h": "init", "t": int(time.time()), "a": "init"}),
              "tree": EMPTY_TREE_SHA, "parents": []})
    if "__error__" in c or "sha" not in c:
        return False
    # ③ 建 ref
    rr = _api("POST", f"/repos/{REPO}/git/refs",
              {"ref": LOCK_REF, "sha": c["sha"]})
    if "__error__" in rr:
        return False
    return True


def _read_state(ref_sha):
    """读锁分支当前 tip commit 的状态 {holder, ts, action}；读不出返回 None。"""
    if not ref_sha:
        return None
    c = _api("GET", f"/repos/{REPO}/git/commits/{ref_sha}")
    if "__error__" in c or "message" not in c:
        return None
    try:
        return json.loads(c["message"])
    except Exception:
        return None


def _branch_sha():
    r = _api("GET", f"/repos/{REPO}/git/refs/heads/{LOCK_REF_SHORT}")
    if "__error__" in r or "object" not in r:
        return None
    return r["object"]["sha"]


def _tip_tree_sha(ref_sha):
    c = _api("GET", f"/repos/{REPO}/git/commits/{ref_sha}")
    if "__error__" in c or "tree" not in c:
        return None
    return c["tree"]["sha"]


def _new_commit(parent_sha, state):
    """在锁分支上基于 parent 提交一条 state 记录（复用 parent 的 tree，零 blob 增量）。"""
    tree = _tip_tree_sha(parent_sha)
    if not tree:
        return None
    c = _api("POST", f"/repos/{REPO}/git/commits",
             {"message": json.dumps(state), "tree": tree, "parents": [parent_sha]})
    if "__error__" in c or "sha" not in c:
        return None
    return c["sha"]


def _cas(ref_sha, new_sha):
    """非 force PATCH ref：ref 当前须等于 ref_sha 否则 422。即原子 CAS。"""
    u = _api("PATCH", f"/repos/{REPO}/git/refs/heads/{LOCK_REF_SHORT}",
             {"sha": new_sha, "force": False})
    return "__error__" not in u


# ── 对外接口 ────────────────────────────────────────────────────────────
def acquire(holder, ttl=1200, max_wait=600, poll=5):
    """抢锁。成功返回 True；超时/任何异常返回 False（调用方应照常推送 = best-effort）。

    holder : 持有者标识（建议含 run_id，便于审计）。
    ttl    : 持有者崩溃后，锁在多少秒后允许被别人抢占（防死锁）。
    max_wait: 最多等多久还抢不到；到点返回 False（放行）。
    """
    try:
        if not _ensure_branch():
            return False
        deadline = time.time() + max_wait
        while time.time() < deadline:
            cur = _branch_sha()
            if cur is None:
                time.sleep(poll)
                continue
            st = _read_state(cur)
            now = time.time()
            free = (st is None) or (st.get("a") != "acquire") \
                or (st.get("h") == holder) \
                or (now - float(st.get("t", 0)) > ttl)
            if not free:
                time.sleep(poll)
                continue
            nsha = _new_commit(cur, {"h": holder, "t": int(now), "a": "acquire"})
            if not nsha:
                time.sleep(poll)
                continue
            if _cas(cur, nsha):
                return True
            # 被别人抢先 → 重试
            time.sleep(poll)
        return False
    except Exception:  # noqa: BLE001
        return False


def release(holder):
    """放锁。非持有者 / 任何异常 → 静默返回（best-effort）。"""
    try:
        cur = _branch_sha()
        if cur is None:
            return True
        st = _read_state(cur)
        if st and st.get("a") == "acquire" and st.get("h") == holder:
            nsha = _new_commit(cur, {"h": holder, "t": int(time.time()), "a": "release"})
            if nsha:
                _cas(cur, nsha)
        return True
    except Exception:  # noqa: BLE001
        return True


# ── CLI ─────────────────────────────────────────────────────────────────
def _cli():
    action = sys.argv[1] if len(sys.argv) > 1 else "acquire"
    holder = "unknown"
    ttl, max_wait = 1200, 600
    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--holder" and i + 1 < len(sys.argv):
            holder = sys.argv[i + 1]; i += 2; continue
        if a == "--ttl" and i + 1 < len(sys.argv):
            ttl = int(sys.argv[i + 1]); i += 2; continue
        if a == "--max-wait" and i + 1 < len(sys.argv):
            max_wait = int(sys.argv[i + 1]); i += 2; continue
        i += 1
    # best-effort：CLI 退出码恒 0，绝不阻断调用方流水线。
    if action == "release":
        release(holder)
    else:
        acquire(holder, ttl=ttl, max_wait=max_wait)
    sys.exit(0)


if __name__ == "__main__":
    _cli()
