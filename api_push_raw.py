#!/usr/bin/env python3
# api_push_raw.py — 经 GitHub REST API 把 raw_data/ 推送到 main
# 绕过 git：本机(cn runner, NETWORK SERVICE)无法直连 github.com 的 git/HTTPS 协议，
# 但 api.github.com 可达。故用 Git Database API 以「单次 commit」方式提交 raw_data。
import os, sys, json, base64, hashlib, datetime
import urllib.request, urllib.error
import http.client
import time as _time
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

def now_cst():
    """返回中国标准时间（Asia/Shanghai）的当前 datetime。"""
    return datetime.datetime.now(CST)

# 2026-08-03 修复：Windows cn runner 默认 stdout/stderr 为 GBK，打印 ℹ️/❌ 等 emoji
# 会触发 UnicodeEncodeError 崩溃（exit 1 但无可见错误）。强制 UTF-8 输出。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPO", "ah-quant999/quant-scanner-v8")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("❌ 缺少 GITHUB_TOKEN"); sys.exit(1)


def api(method, path, data=None):
    url = API + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    # 2026-08-05 修复：timeout 90s 对候选池等大文件 blob 上传太紧，cn runner 网络抖动时
    # 触发 TimeoutError 且未被捕获 → 整个推送进程崩溃（exit 1），54 个文件全部不落地。
    # 1) 超时放宽到 300s；2) 捕获网络类异常（TimeoutError/URLError/OSError）返回错误 dict，
    #    让调用方（blob 上传循环的 3 次重试 + 跳过）逻辑真正生效，而不是整体崩溃。
    # 2026-08-11 修复（157 轮看门狗）：上一版只捕获 (TimeoutError, URLError, OSError)，
    # 但 http.client.IncompleteRead 继承自 HTTPException 而 **不是 OSError 子类**，
    # 因此响应体被中途截断时异常逃逸 → 整个推送进程崩溃(exit 1) → 57 个文件全部不落地
    # （实测 run 31452057629：读 blob 时 IncompleteRead(491873 read, 24313 more expected)，
    #   ETF_DAILY_MONITOR 等盘中数据整批丢失，cn fetch 判 failure）。
    # 修法：1) 异常元组补 http.client.HTTPException；
    #      2) 幂等请求(GET)内建 3 次退避重读，抵御 cn runner 网络抖动，不再靠调用方兜底。
    attempts = 3 if method.upper() == "GET" else 1
    last_msg = ""
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                txt = r.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            print(f"  ⚠️ API {method} {path} -> HTTP {e.code}")
            try:
                err = json.loads(body)
                print(f"     message: {err.get('message')}")
                print(f"     doc: {err.get('documentation_url')}")
            except Exception:
                print(f"     body: {body[:500]}")
            return {"__error__": e.code, "__msg__": body}
        except (TimeoutError, urllib.error.URLError, OSError,
                http.client.HTTPException, json.JSONDecodeError) as e:
            last_msg = f"{type(e).__name__}: {e}"
            print(f"  ⚠️ API {method} {path} -> 网络异常 {last_msg}")
            if i < attempts - 1:
                wait = 2 ** i
                print(f"     ↻ 幂等重试 {i + 1}/{attempts - 1}（{wait}s 后）")
                _time.sleep(wait)
    return {"__error__": "network", "__msg__": last_msg}


def walk_raw():
    out = {}
    if not os.path.isdir("raw_data"):
        return out
    for root, _dirs, files in os.walk("raw_data"):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, ".").replace("\\", "/")
            with open(full, "rb") as fh:
                out[rel] = fh.read()
    return out


_TS_KEYS = ("update_time", "gen_time", "calc_time", "run_time",
            "fetch_time", "snapshot_time")


def _blob_sha(content: bytes) -> str:
    """按 git 规则计算 blob sha1，用于和远端 tree 里的 sha 直接比对。"""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(content))
    h.update(content)
    return h.hexdigest()


def _content_ts(content: bytes):
    """从 JSON 内容里取顶层时间戳（精确到分钟的字符串），取不到返回 None。"""
    try:
        obj = json.loads(content.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    best = None
    for k in _TS_KEYS:
        v = obj.get(k)
        if isinstance(v, str) and len(v) >= 16 and v[4] == "-":
            s = v[:16]
            if best is None or s > best:
                best = s
    return best


def walk_extra():
    """额外推送文件（不在 raw_data/，但由算法脚本直接写 data/）。

    2026-08-10 补入：final_recommend / calc_stock_rps / strategy_four_volume_60m /
    export_optimized_strategy 等脚本直接写 data/*.js 或 raw_data/*.json，
    需在此注册才能被 api_push 推送到 main。
    """
    out = {}
    extra = [
        "data/FOUR_VOLUME.js",          # 四量终极日线版（gen_triple_consensus 产出）
        "data/STOCK_STOP_DATA.js",      # ATR止损止盈（gen_stock_stop 产出）
        # ── 2026-08-10 补入：之前缺失导致这些文件永远不刷新 ──
        "data/FINAL_RECOMMEND_DATA.js", # 跨策略共振 Top3（final_recommend.py 产出）
        "data/STOCK_RPS.js",            # 个股相对强度 RPS+RS（calc_stock_rps.py 产出）
        "data/FOUR_VOLUME_60M.js",      # 四量终极60min版（strategy_four_volume_60m.py 产出）
        # optimized_strategy.json 在 raw_data/，由 walk_raw() 自动覆盖
    ]
    for rel in extra:
        if os.path.isfile(rel):
            with open(rel, "rb") as fh:
                out[rel] = fh.read()
    return out


def main():
    files = walk_raw()
    files.update(walk_extra())
    if not files:
        print("ℹ️ raw_data 为空，跳过"); sys.exit(0)
    print(f"待推送文件: {len(files)} 个 -> {sorted(files)[:5]} ...")

    # 现有 main 树里的 raw_data 子树（及额外文件）的 blob sha，用于变更检测
    ref = api("GET", f"/repos/{REPO}/git/refs/heads/main")
    if "__error__" in ref:
        print("❌ 获取 main ref 失败:", ref.get("__msg__")); sys.exit(1)
    base_sha = ref["object"]["sha"]
    cmt = api("GET", f"/repos/{REPO}/git/commits/{base_sha}")
    base_tree = cmt["tree"]["sha"]
    existing = {}
    tfull = api("GET", f"/repos/{REPO}/git/trees/{base_tree}?recursive=1")
    for e in tfull.get("tree", []):
        if (e["path"].startswith("raw_data/")
            or e["path"] in ("data/FOUR_VOLUME.js", "data/STOCK_STOP_DATA.js",
                              "data/FINAL_RECOMMEND_DATA.js", "data/STOCK_RPS.js",
                              "data/FOUR_VOLUME_60M.js")
            ) and e["type"] == "blob":
            existing[e["path"]] = e["sha"]

    # 上传 blobs（幂等：内容相同则 sha 相同）
    # 2026-08-04：GitHub blob API 对较大文件偶发 HTTP 400 "malformed request"（08-03 stock_names.json
    # 325KB 命中，导致整次推送 sys.exit(1)、全部数据不落地）。加 3 次指数退避重试；仍失败则跳过该文件
    # 而不是整体退出——保证其余数十个数据文件能正常上线。
    import time as _t
    new_entries = {}
    failed_paths = []
    unchanged = 0
    regressed = []
    for path, content in files.items():
        # ---- 2026-08-09 防倒退守卫 ----------------------------------------
        # 根因：walk_raw() 全量读本地 raw_data/，而云端 job 从 checkout 到 push
        # 有数分钟窗口；期间别的 workflow（算法链 / weekend t1）推了新数据，
        # 本次 push 会用 checkout 时刻的旧内容把它覆盖回去（读-改-写竞态）。
        # 实测 candidate.json 被 cn fetch 反复打回 08-04，前端连续多日显示旧数据。
        local_sha = _blob_sha(content)
        remote_sha = existing.get(path)
        # (1) 内容完全一致：直接复用远端 sha，省一次 blob 上传
        if remote_sha and local_sha == remote_sha:
            unchanged += 1
            continue
        # (2) 内容不同：比对时间戳，本地更旧则保留远端版本，绝不覆盖
        if remote_sha and path.endswith(".json"):
            lts = _content_ts(content)
            if lts:
                rb = api("GET", f"/repos/{REPO}/git/blobs/{remote_sha}")
                if "__error__" not in rb and rb.get("encoding") == "base64":
                    try:
                        rts = _content_ts(base64.b64decode(rb["content"]))
                    except Exception:
                        rts = None
                    if rts and lts < rts:
                        regressed.append((path, lts, rts))
                        continue
        # -------------------------------------------------------------------
        payload = {"content": base64.b64encode(content).decode(), "encoding": "base64"}
        b = None
        for attempt in range(3):
            b = api("POST", f"/repos/{REPO}/git/blobs", payload)
            if "__error__" not in b:
                break
            wait = 2 ** attempt
            print(f"  ↻ blob 重试 {attempt + 1}/3（{path}，{wait}s 后）")
            _t.sleep(wait)
        if b is None or "__error__" in b:
            print(f"  ⚠️ 跳过（3 次均失败）: {path}")
            failed_paths.append(path)
            continue
        new_entries[path] = b["sha"]

    print(f"📊 未变化 {unchanged} / 防倒退跳过 {len(regressed)} / 待更新 {len(new_entries)}")
    if regressed:
        for p, lts, rts in regressed:
            print(f"  🛡️ 防倒退跳过 {p}: 本地({lts}) < 远端({rts})")
    if failed_paths:
        print(f"⚠️ 共 {len(failed_paths)} 个文件上传失败，将保留远程旧版本: {failed_paths}")
    if not new_entries:
        if failed_paths:
            print("❌ 全部 blob 上传失败，终止推送"); sys.exit(1)
        print("ℹ️ raw_data 无需更新（内容一致或均被防倒退守卫拦截），跳过提交"); sys.exit(0)

    # 合并策略：保留远程已有的其他 raw_data 文件，只覆盖本次确实更新的文件。
    # 这样 cloud_fetch --category 只更新当次类别，不会删掉盘前/盘后类别的文件。
    merged_entries = dict(existing)  # path -> sha
    merged_entries.update(new_entries)

    tree_items = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                  for p, s in merged_entries.items()]

    msg = "v8 cn fetch: " + now_cst().strftime("%Y-%m-%d %H:%M")
    for attempt in range(1, 4):
        # 重新读取最新 main（与 build_deploy 并发安全）
        r2 = api("GET", f"/repos/{REPO}/git/refs/heads/main")
        base_sha2 = r2["object"]["sha"]
        cmt2 = api("GET", f"/repos/{REPO}/git/commits/{base_sha2}")
        base_tree2 = cmt2["tree"]["sha"]
        new_tree = api("POST", f"/repos/{REPO}/git/trees",
                       {"base_tree": base_tree2, "tree": tree_items})
        if "__error__" in new_tree:
            print("❌ 创建 tree 失败:", new_tree.get("__msg__")); sys.exit(1)
        commit = api("POST", f"/repos/{REPO}/git/commits",
                     {"message": msg, "tree": new_tree["sha"], "parents": [base_sha2]})
        if "__error__" in commit:
            print("❌ 创建 commit 失败:", commit.get("__msg__")); sys.exit(1)
        # 2026-08-03 修复：改用 force=False，避免触发分支保护"Block force pushes"。
        # parent 始终为最新 main，重试逻辑已保证不会丢失他人提交。
        upd = api("PATCH", f"/repos/{REPO}/git/refs/heads/main",
                  {"sha": commit["sha"], "force": False})
        if "__error__" in upd:
            code = upd.get('__error__')
            print(f"⚠️ ref 更新失败 ({code})，重试 ({attempt}/3)")
            if code == 422:
                print("   可能原因：分支保护禁止 force push 或要求 status check / PR review。")
                print("   若 3 次重试仍 422，请检查 Settings > Branches > main 保护规则。")
            continue
        print(f"✅ raw_data 已推送（第 {attempt} 次）commit {commit['sha'][:8]}")
        sys.exit(0)
    print("❌ 3 次重试后仍失败"); sys.exit(1)


if __name__ == "__main__":
    main()
