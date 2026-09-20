#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_put_file.py — 经 GitHub REST API 把单个本地文件推送到 origin/main。

绕过 git：本机无法直连 github.com 的 git/HTTPS 协议，但 api.github.com 可达。
用 Contents API 以「base64 + 当前 blob sha」方式提交，天然带冲突检测（409 即远端
已被并发修改，自动重新拉取 sha 后重试）。>1MB 文件自动改用 Git blobs API。

用法: python scripts/api_put_file.py <本地相对路径> [commit message]
"""
import os
import sys
import base64
import json
import hashlib
import urllib.request
import urllib.error

API = "https://api.github.com"


# ═══════════════════════════════════════════════════════════════════════════
# 🛡 2026-09-20 一劳永逸（小九）：**推边界行尾收口（EOL fold）**
#
#   【根因 · 三层实测】
#     ① 本机(Windows)算法/生成脚本普遍以
#            open(path, "w", encoding="utf-8")            # newline 未指定
#        落盘，Python 在 Windows 下 newline=None ⇒ "\n" 被写成 os.linesep = "\r\n"。
#        本机复现（同一份 json.dump(..., indent=1)）：
#            open(...,"w",encoding="utf-8")               → CRLF=6   LF=6
#            open(...,"w",encoding="utf-8",newline="\n")  → CRLF=0   LF=6
#     ② 本脚本以**二进制**读本地文件（open(..., "rb")），再走 GitHub Git Data API
#        (blobs/trees/commits) 直推 ⇒ **完整绕过 .gitattributes 的 `text eol=lf` 归一化**
#        ⇒ 本地 CRLF 原样进 blob。（git add 提交那条路不会，它是 API 直推独有的坑。）
#     ③ 根 .gitattributes 把 raw_data/*.json、data/*.js 等声明为 `text eol=lf`；
#        CI(Linux) checkout 后工作树与属性要求冲突 ⇒ `git status` **恒脏** ⇒
#        **任何 git rebase 在启动前即被拒**：
#            warning: in the working copy of 'raw_data/top10_daily.json',
#                     CRLF will be replaced by LF the next time Git touches it
#            error: cannot rebase: You have unstaged changes.
#            error: Please commit or stash them.
#            fatal: no rebase in progress
#            ##[error]Process completed with exit code 128.
#        ⇒ v8 实时风险温度计 / 缓存戳对齐 / 备份 / 盘中快照 / 周清理 等
#          9 条带 rebase 的推链会周期性假失败（现象是「3 次重试全空转后 exit 1」）。
#        实证：workflow run #513（🌍 v8 实时风险温度计）failure，日志逐行如上。
#
#   【修法】在**推边界替 git 补上它本该做的归一化**：
#     只对「.gitattributes 明确要求 eol=lf」的路径做 CRLF→LF；
#     logic.html 属**有意 CRLF**（属性 `-text -eol`）⇒ 判定为 unset ⇒ 自动跳过，绝不触碰。
#     归一化在 `content` 进入 sha 计算 / 防倒退守卫**之前**完成，
#     否则 blob sha 与守卫用的时间戳口径会与实际推送内容不一致。
#
#   【真源】scripts/normalize_eol.py —— 判定走 `git check-attr`（与 .gitattributes
#     同源，杜绝「另写一套规则必漂移」的历史教训）；该模块缺失时退内联规则表。
# ═══════════════════════════════════════════════════════════════════════════

# 内联降级规则（与根 .gitattributes 同粒度；仅当 scripts/normalize_eol.py 不可用时启用）
_EOL_NEVER = {"logic.html"}
_EOL_SUFFIX = (".yml", ".yaml", ".sh", ".py")
_EOL_EXACT = {".gitattributes", "v6_memo.html", "v6_memo.golden.html"}


def _eol_expected_inline(rel: str) -> bool:
    p = rel.replace("\\", "/")
    if p in _EOL_NEVER:
        return False
    if p in _EOL_EXACT or p.endswith(_EOL_SUFFIX):
        return True
    parts = p.split("/")
    if len(parts) == 1 and parts[0].endswith(".html"):
        return True
    if len(parts) == 2 and parts[0] == "data" and parts[1].endswith(".js"):
        return True
    if len(parts) == 2 and parts[0] == "raw_data" and parts[1].endswith(".json"):
        return True
    return False


def _eol_load_module():
    """加载 scripts/normalize_eol.py（单一真源）；失败返回 None → 退内联规则。"""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "normalize_eol.py")
    if not os.path.isfile(p):
        print("  ℹ️ scripts/normalize_eol.py 不存在 → 行尾收口走内联规则")
        return None
    try:
        spec = importlib.util.spec_from_file_location("v8_normalize_eol", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:      # noqa: BLE001
        print(f"  ⚠️ 行尾收口模块加载失败（{type(e).__name__}: {e}）→ 走内联规则")
        return None


_EOL_MOD = _eol_load_module()


def fold_eol(files: dict, note: str = "") -> int:
    """就地把 files 中「应属 LF」的内容做 CRLF→LF（幂等）。返回实际归一化个数。

    🔴 必须在 `_blob_sha()` / 防倒退守卫**之前**调用 —— 否则 sha 会与推送内容不符。
    ⚠️ 只改 "\r\n"；孤立 "\r"（后不跟 "\n"）不动，避免误伤特殊格式。
    """
    if not files:
        return 0
    exp = {}
    if _EOL_MOD is not None:
        try:
            exp, _how = _EOL_MOD.expected_lf(os.getcwd(), list(files))
        except Exception:       # noqa: BLE001
            exp = {}
    n = 0
    hit = []
    for k in list(files):
        want = exp.get(k)
        if want is None:
            want = _eol_expected_inline(k)
        if not want:
            continue
        c = files[k]
        if b"\r\n" in c:
            files[k] = c.replace(b"\r\n", b"\n")
            n += 1
            hit.append(k)
    if n:
        print(f"🔧 行尾收口（.gitattributes text eol=lf）：{n} 个文件 CRLF→LF{note}")
        for k in hit[:12]:
            print(f"     · {k}")
        if len(hit) > 12:
            print(f"     · …另有 {len(hit) - 12} 个")
    return n


REPO = os.environ.get("GITHUB_REPOSITORY") or "ah-quant999/quant-scanner-v8"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("❌ 缺少 GITHUB_TOKEN"); sys.exit(1)


def _request(method, path, data=None, retry=3):
    url = API + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    last = None
    for _ in range(retry):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=120) as r:
                t = r.read().decode("utf-8")
                return json.loads(t) if t else {}, r.status
        except urllib.error.HTTPError as e:
            last = e.read().decode("utf-8", "replace")
            if e.code == 409 and method == "PUT":
                return {"__conflict__": True, "__msg__": last}, e.code
            print(f"  ⚠️ HTTP {e.code}: {last[:300]}")
            return {"__error__": e.code, "__msg__": last}, e.code
        except Exception as e:  # network
            last = str(e)
            print(f"  ⚠️ 网络异常 {e}")
    return {"__error__": "net", "__msg__": last}, 0


def put_file(local_rel, msg=None):
    local_rel = local_rel.replace("\\", "/")
    path = f"/repos/{REPO}/contents/{local_rel}"
    with open(local_rel, "rb") as f:
        content = f.read()
    # 🛡 2026-09-20 推边界行尾收口（见上方 fold_eol 注释）
    _ef = {local_rel: content}
    fold_eol(_ef)
    content = _ef[local_rel]
    encoded = base64.b64encode(content).decode("ascii")
    is_big = len(content) > 900_000

    for attempt in range(4):
        # 取当前 sha（冲突重试时需要最新）
        cur = _request("GET", path)
        sha = cur[0].get("sha") if isinstance(cur[0], dict) else None
        if sha is None and cur[1] == 404:
            # 新文件：直接创建
            data = {"message": msg or f"chore: add {local_rel}", "content": encoded,
                    "branch": "main"}
            res, st = _request("PUT", path, data)
            if st in (200, 201):
                print(f"✅ 已创建 {local_rel}"); return 0
            if isinstance(res, dict) and res.get("__conflict__"):
                print(f"  ↻ {local_rel} 并发冲突，重试 ({attempt+1})"); continue
            print(f"❌ 创建失败 {local_rel}: {res}"); return 1

        if is_big:
            # 走 git blobs API（>1MB Contents API 会截断）
            bres, bst = _request("POST", f"/repos/{REPO}/git/blobs",
                                 {"content": encoded, "encoding": "base64"})
            if bst != 201 or "__error__" in bres:
                print(f"❌ blob 上传失败 {local_rel}: {bres}"); return 1
            data = {"message": msg or f"chore: update {local_rel}",
                    "content": encoded, "sha": sha, "branch": "main"}
        else:
            data = {"message": msg or f"chore: update {local_rel}",
                    "content": encoded, "sha": sha, "branch": "main"}
        res, st = _request("PUT", path, data)
        if st in (200, 201):
            print(f"✅ 已更新 {local_rel}"); return 0
        if isinstance(res, dict) and res.get("__conflict__"):
            print(f"  ↻ {local_rel} 并发冲突，重试 ({attempt+1})"); continue
        print(f"❌ 更新失败 {local_rel}: {res}"); return 1
    print(f"❌ {local_rel} 多次重试仍失败"); return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/api_put_file.py <本地相对路径> [msg]"); sys.exit(1)
    sys.exit(put_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
