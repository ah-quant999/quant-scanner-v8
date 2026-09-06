#!/usr/bin/env python3
# api_push_raw.py — 经 GitHub REST API 把 raw_data/ 推送到 main
# 绕过 git：本机(cn runner, NETWORK SERVICE)无法直连 github.com 的 git/HTTPS 协议，
# 但 api.github.com 可达。故用 Git Database API 以「单次 commit」方式提交 raw_data。
import os, sys, json, base64, hashlib, datetime, re
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
    # 🛡️ 2026-08-14 防覆盖（主人令"防覆盖了？"）：算法产物只在家庭机 17:20 run_algorithms 跑，
    #    cloud_fetch 不产出它们。但云端 runner 工作区里常有旧版副本，walk_raw 全量推
    #    会覆盖 main 上的新版（实测 05:40 fetch 把 backtest_tdx.json 从 08-13 新版
    #    142061 行覆盖回 08-04 旧版，策略回测页数据倒退）。
    #    故此处排除算法产物，仅由 run_algorithms/本地推链维护。
    #    2026-08-14 升级：由写死集合改为「词根前缀」自动匹配，新增算法脚本产物
    #    （如 backtest_xxx / top3_track_xxx / cockpit_backtest_xxx / optimized_strategy_xxx）
    #    自动纳入排除，根除「漏把新算法产物加进排除表导致再被覆盖」的根因。
    # 🔴 2026-08-20 根因修复：v8_algo_cloud 自己就是 run_algorithms 的 runner，必须
    #    把算法产物推上去；否则 backtest_*/cockpit_backtest* 等
    #    永远停在本地旧版，策略回测/驾驶舱卡片长期 stale。通过环境变量
    #    PUSH_ALGO_RAW=1 显式开启（仅 v8_algo_cloud.yml 设置），cloud_fetch 不设置
    #    保持原有防覆盖行为。
    _ALGO_RAW_PREFIXES = (
        "backtest",          # backtest_tdx.py / backtest_comprehensive.py 等
        "cockpit_backtest",  # cockpit_backtest_now.py
        "optimized_strategy",# export_optimized_strategy.py
        "algo_track",         # gen_algo_track.py（2026-08-15 三算法追踪）
        "commodity_prices_cache",  # calc_commodity_elasticity.py westock 价格缓存（MCP 预抓取）
    )
    push_algo_raw = os.environ.get("PUSH_ALGO_RAW") == "1"
    for root, _dirs, files in os.walk("raw_data"):
        for f in files:
            if f.startswith(_ALGO_RAW_PREFIXES) and not push_algo_raw:
                continue
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
        # ── 2026-08-17 补入：商品涨价弹性榜（calc_commodity_elasticity.py 产出）──
        # 之前未注册，导致国内期货 LC/SA 数据永远不显示；现加入云端自动跑 + 推送
        "data/COMMODITY_ELASTICITY.js",
        # ── 2026-08-19 补入：H 反推短线买点 + 跟踪（auto_run_dn_algorithm / track_h_auto_buy） ──
        # 之前仅手动 commit，未注册到 api_push 队列 → 每天盘后算法链跑完也不上传。
        "data/H_AUTO_BUY.js",           # 反推算法当日候选（脱离 PDF OCR）
        "data/H_AUTO_BUY_TRACK.js",     # 反推算法累计胜率（每日跟踪 T+1/T+3/T+5/T+10）
        # 🔴 2026-08-20 根因修复：LHB_7D.js 由 gen_lhb_7d.py 直写 data/，之前未注册
        #    到 extra → 算法链跑完也不上传，页面 7 日龙虎榜/机游共振长期 stale。
        "data/LHB_7D.js",
        # optimized_strategy.json 在 raw_data/，由 walk_raw() 按算法产物前缀自动排除（不推送，免覆盖）
    ]
    for rel in extra:
        if os.path.isfile(rel):
            with open(rel, "rb") as fh:
                out[rel] = fh.read()
    return out


# ── 2026-08-15 根治「cn 单独推送 5 个 extra 文件后 ?v 失配」────────────────
# 根因：api_push_raw 经 Git Database API 推送 data/FOUR_VOLUME.js 等 5 个
# extra 文件，但从不更新 index.html 的 ?v；新内容上线后，直到 reconcile
# workflow 跑（最多 ~15min 窗口）?v 一直指向旧哈希 → CDN/浏览器吐旧副本。
# 修复：cn 推送这 5 个文件的同时，在本提交内原子更新 index.html 对应 ?v，
# 使 ?v 与本次推送内容严格一致，彻底消除该窗口。
# 说明：无论 build / cn / 盘后算法链谁推送 data，reconcile workflow 仍是
# 全局自愈兜底；此处只是把「最高频的 cn extra 推送」做成零窗口。
_EXTRA_FILES = (
    "data/FOUR_VOLUME.js",
    "data/STOCK_STOP_DATA.js",
    "data/FINAL_RECOMMEND_DATA.js",
    "data/STOCK_RPS.js",
    "data/FOUR_VOLUME_60M.js",
    # 🛡 2026-08-19：H 反推算法相关文件注册到 ?v 重写集，确保 api_push 推送后 index.html 同步对齐缓存戳
    "data/H_AUTO_BUY.js",
    "data/H_AUTO_BUY_TRACK.js",
    # 🔴 2026-08-20：LHB_7D.js 同步对齐缓存戳
    "data/LHB_7D.js",
    # 2026-08-19：路径概率预测卡（艾略特+江恩+缠论+形态匹配）注册到 ?v 重写集
    "data/INDEX_HISTORY.js",
    # 2026-08-19：板块推荐框架（宏观+板块RS+资金流+周期融合）注册到 ?v 重写集
    "data/MARKET_REGIME.js",
    "data/SECTOR_RECOMMENDATION.js",
    # 🛡 2026-08-19 阿狸咪根治孤儿：data/MACRO.js 删除（前端 render 0 处引用 window.MACRO）—节省空间+Actions分钟
)
_RE_V = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')


def _neutral_sha(content: bytes) -> str:
    """与 update_v8._rewrite / reconcile_cache_busters 完全一致的中性化哈希：
    先剔除 republish_time 的构建时间戳（非数据本体），再取 sha1 前 10 位。"""
    try:
        text = content.decode("utf-8")
    except Exception:
        text = content.decode("utf-8", "replace")
    neutral = re.sub(r'"republish_time"\s*:\s*"[^"]*"', '"republish_time":""', text)
    return hashlib.sha1(neutral.encode("utf-8")).hexdigest()[:10]


def _stamp_index_v(index_text: str, changed: dict) -> tuple:
    """对 index.html 文本，为 changed 中每个 data/X.js 用其新内容重算 ?v 并替换。
    changed: { "data/FOUR_VOLUME.js": b"..." }。
    返回 (new_text, changed_bool)。空内容(未就绪)不写空 ?v，保留原 ?v 等下次对齐。
    """
    def repl(m):
        q1, src, q2 = m.group(1), m.group(2), m.group(3)
        if src in changed:
            data = changed[src]
            if not data.strip():
                return m.group(0)
            return f"{q1}{src}?v={_neutral_sha(data)}{q2}"
        return m.group(0)
    new = _RE_V.sub(repl, index_text)
    return new, new != index_text


def main():
    # 2026-08-22 来源驱动增量推送（主人令升级）：支持 PUSH_FILES 环境变量（逗号分隔相对路径）。
    #   - 有 PUSH_FILES：只处理清单内文件（workflow 用 git status 收集"本次 changed"，聚焦且不漏）；
    #   - 无 PUSH_FILES：回退全量 walk_raw + walk_extra（兼容旧调用/本地手动跑）。
    # 两种模式都只把「变更集」提交进 tree（base_tree 增量），单次请求大小与仓库规模解耦，
    # 彻底绕开 Git Trees API 的 "input too large" 422。
    # 🛡 累计数据守卫（主人令）：history/ 与 *_history.json 等时间序列为「只增不改」数据——
    #   ① 任何模式都不从 tree 中删除（base_tree 继承未列出路径，天然保留）；
    #   ② 防倒退时间戳守卫（下方 existing 比对）保证绝不覆盖远端更新版本。
    push_files_env = os.environ.get("PUSH_FILES", "").strip()
    if push_files_env:
        files = {}
        _missing = []
        for _rel in [p.strip() for p in push_files_env.split(",") if p.strip()]:
            if os.path.isfile(_rel):
                with open(_rel, "rb") as _fh:
                    files[_rel] = _fh.read()
            else:
                _missing.append(_rel)
        if _missing:
            print(f"⚠️ 清单中 {len(_missing)} 个文件不存在（跳过）: {_missing[:10]}")
    else:
        files = walk_raw()
        files.update(walk_extra())
    if not files:
        print("ℹ️ 无文件可推送，跳过"); sys.exit(0)
    print(f"待推送文件: 收集 {len(files)} 个 -> {sorted(files)[:5]} ...")

    # 现有 main 树里的 raw_data 子树（及额外文件）的 blob sha，用于变更检测
    ref = api("GET", f"/repos/{REPO}/git/refs/heads/main")
    if "__error__" in ref:
        print("❌ 获取 main ref 失败:", ref.get("__msg__")); sys.exit(1)
    base_sha = ref["object"]["sha"]
    cmt = api("GET", f"/repos/{REPO}/git/commits/{base_sha}")
    # 2026-08-11 修复（159 轮看门狗）：原来直接 cmt["tree"]["sha"]，网络异常时 api()
    # 返回 {"__error__":...} → KeyError 未捕获 → traceback 崩溃，整批文件全丢
    # （与 157 轮 IncompleteRead 同类：单点网络抖动毁掉全批推送）。
    if "__error__" in cmt or "tree" not in cmt:
        print("❌ 获取 base commit 失败:", cmt.get("__msg__")); sys.exit(1)
    base_tree = cmt["tree"]["sha"]
    existing = {}
    tfull = api("GET", f"/repos/{REPO}/git/trees/{base_tree}?recursive=1")
    # 2026-08-11 修复（159 轮看门狗）·数据回退隐患根治：
    # existing 是「防倒退守卫」的唯一基线。原代码用 tfull.get("tree", []) 兜底，
    # 一旦这次 GET 失败或被 GitHub 截断，existing 会静默变成空/残缺 →
    # 所有本地文件都被判为「远端没有」→ 守卫完全失效 → 用 checkout 时刻的旧内容
    # 覆盖远端更新版本，正是 08-09 大范围数据回退故障的成因。
    # 守卫基线不完整时必须中止，绝不能「无守卫裸推」。
    if "__error__" in tfull or "tree" not in tfull:
        print("❌ 获取 base tree 失败（防倒退守卫无基线，拒绝裸推）:", tfull.get("__msg__"))
        sys.exit(1)
    if tfull.get("truncated"):
        print("❌ base tree 被 GitHub 截断（truncated=true），守卫基线残缺，拒绝裸推")
        sys.exit(1)
    for e in tfull.get("tree", []):
        if (e["path"].startswith("raw_data/")
            or e["path"] in ("data/FOUR_VOLUME.js", "data/STOCK_STOP_DATA.js",
                              "data/FINAL_RECOMMEND_DATA.js", "data/STOCK_RPS.js",
                              "data/FOUR_VOLUME_60M.js",
                              # 🛡 2026-08-19：H 反推注册到防倒退守卫远端基线
                              "data/H_AUTO_BUY.js", "data/H_AUTO_BUY_TRACK.js")
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
        # 🔴 2026-09-02 根治令（涨停热力连续多轮静默丢数据事故）：
        #    实测 09-02 盘中多轮 raw_data/limit_up_heatmap.json（仅 3.4KB，非大文件）
        #    连续 3 次 HTTP 500 后「跳过 → 保留远程旧版本」，而 workflow 依旧报 success（假绿），
        #    导致前端涨停热力卡在 08:45 盘前值、连续数小时无人知晓。三处加固：
        #      1) 重试 3 → 8 次，退避封顶 30s（1/2/4/8/16/30/30，总约 91s），
        #         足以跨过 GitHub 服务端 5xx 抖动窗口（实测抖动通常 <60s）；
        #      2) 仅对「可重试错误」重试：5xx / 429 / 网络类异常。
        #         4xx（400/403/404/422）属客户端错误，重试无意义 → 快速失败，不拖慢整轮；
        #      3) 仍失败时打 ::error:: 注解（见下方 failed_paths 汇总），
        #         Actions UI 直接标红，不再伪装成 success。
        BLOB_MAX_TRY = 8
        for attempt in range(BLOB_MAX_TRY):
            b = api("POST", f"/repos/{REPO}/git/blobs", payload)
            if "__error__" not in b:
                break
            code = b.get("__error__")
            retryable = (code == "network"
                         or (isinstance(code, int) and (code >= 500 or code == 429)))
            if not retryable:
                print(f"  ❌ 不可重试错误（HTTP {code}），放弃该文件: {path}")
                break
            if attempt < BLOB_MAX_TRY - 1:
                wait = min(2 ** attempt, 30)
                print(f"  ↻ blob 重试 {attempt + 1}/{BLOB_MAX_TRY - 1}"
                      f"（{path}，HTTP {code}，{wait}s 后）")
                _t.sleep(wait)
        if b is None or "__error__" in b:
            code = (b or {}).get("__error__")
            print(f"  ⚠️ 跳过（{BLOB_MAX_TRY} 次均失败，HTTP {code}）: {path}")
            failed_paths.append(path)
            continue
        new_entries[path] = b["sha"]

    # ── 2026-08-15 根治「cn 单独推送 5 个 extra 文件后 ?v 失配」────────────
    # 仅当本次确实推送了 5 个 extra 文件中的一个，才原子更新 index.html 对应 ?v，
    # 使 ?v 与本次落库内容严格一致，消除「新数据上线 ~ reconcile 跑之前」的失配窗口。
    # 若 index.html 拉取/改写/上传任一步失败，则跳过（交由 reconcile workflow 自愈），
    # 绝不因此阻断整批 raw_data 推送。
    extra_changed = {p: files[p] for p in _EXTRA_FILES if p in new_entries}
    if extra_changed:
        idx_meta = api("GET", f"/repos/{REPO}/contents/index.html")
        if "__error__" not in idx_meta and "content" in idx_meta:
            idx_text = base64.b64decode(idx_meta["content"]).decode("utf-8", "replace")
            new_idx, idx_changed = _stamp_index_v(idx_text, extra_changed)
            if idx_changed:
                ib = api("POST", f"/repos/{REPO}/git/blobs",
                         {"content": base64.b64encode(new_idx.encode("utf-8")).decode(),
                          "encoding": "base64"})
                if "__error__" not in ib and "sha" in ib:
                    new_entries["index.html"] = ib["sha"]
                    print("✅ index.html ?v 已随 5 个 extra 文件原子更新")
                else:
                    print("  ⚠️ index.html blob 上传失败，?v 将交由 reconcile 自愈")
            else:
                print("ℹ️ index.html ?v 已一致，无需改动")
        else:
            print("  ⚠️ 拉取 index.html 失败，?v 将交由 reconcile 自愈")

    print(f"📊 未变化 {unchanged} / 防倒退跳过 {len(regressed)} / 待更新 {len(new_entries)}")
    # 🛡 2026-08-22 规模巡检（主人令）：单次提交过大 = 全量重建/仓库膨胀信号，告警便于及时发现
    if len(new_entries) > 300:
        print(f"⚠️ 单次提交 {len(new_entries)} 个文件（>300）——推送规模偏大，"
              f"疑似全量重建或仓库膨胀，请核查来源驱动清单是否生效")
    if regressed:
        for p, lts, rts in regressed:
            print(f"  🛡️ 防倒退跳过 {p}: 本地({lts}) < 远端({rts})")
    if failed_paths:
        print(f"⚠️ 共 {len(failed_paths)} 个文件上传失败，将保留远程旧版本: {failed_paths}")
        # 🔴 2026-09-02 根治令：原逻辑只 print 一行 ⚠️，workflow 依旧报 success（假绿），
        #    数据静默丢失无人知晓（涨停热力连续多轮卡 08:45 未被发现，主人自己看出来的）。
        #    现同时写入 ::error:: 注解 + $GITHUB_STEP_SUMMARY，
        #    使失败在 Actions 步骤详情标红、在 Job Summary 顶部以表格呈现，一眼可见。
        for _p in failed_paths:
            print(f"::error title=数据未上线::{_p} 本轮上传失败，线上保留旧版本（update_time 不刷新）")
        try:
            import os as _os
            _sf = _os.environ.get("GITHUB_STEP_SUMMARY")
            if _sf:
                with open(_sf, "a", encoding="utf-8") as _fh:
                    _fh.write("\n## ⚠️ 本轮有数据文件未上线\n\n")
                    _fh.write("| 文件 | 状态 |\n| --- | --- |\n")
                    for _p in failed_paths:
                        _fh.write(f"| `{_p}` | ❌ 上传失败，线上保留旧版本 |\n")
                    _fh.write("\n> 这些文件的 `update_time` **不会刷新**，前端将持续显示陈旧数据。"
                              "下轮 fetch 会重试；若连续多轮失败请排查 GitHub API 状态。\n")
        except Exception:
            pass
    if not new_entries:
        if failed_paths:
            # 🔴 2026-08-18 主人根治令：全部 blob 上传失败 ≠ 错误。保留远程旧版本
            #   正常退出（exit 0），避免看门狗/云端 workflow 因「无新数据可推」误判为失败
            #   而派发兜底、烧小九 token。数据基础仍由云端下次 fetch 尝试。
            print("ℹ️ 本地 blob 全部上传失败，保留远程旧版本（不算错误）"); sys.exit(0)
        print("ℹ️ raw_data 无需更新（内容一致或均被防倒退守卫拦截），跳过提交"); sys.exit(0)

    # 合并策略：保留远程已有的其他 raw_data 文件，只覆盖本次确实更新的文件。
    # 这样 cloud_fetch --category 只更新当次类别，不会删掉盘前/盘后类别的文件。
    # 🛡 2026-08-21 一劳永逸根治「tree 创建超时 input too large」：
    #   根因：把全量 merged_entries（existing 数百文件 + 本次变更）塞进单个 POST /git/trees，
    #   GitHub Git Trees API 请求体超限 → 超时失败 → 下午 15:35 等盘中快照抓到本地但推不上
    #   main → 前端「主力净额分时累计曲线」下午无数据（主人 8/21 22:51 报告）。
    #   修复①：tree_items 只含「本次变更文件」——base_tree 参数会保留远端其余路径，语义等价。
    tree_items = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                  for p, s in new_entries.items()]

    msg = "v8 cn fetch: " + now_cst().strftime("%Y-%m-%d %H:%M")
    # 2026-08-11 修复（159 轮看门狗）：提交环节的三类「单点致命」问题一并根治——
    #   ① r2/cmt2 直接下标取值，网络异常时 KeyError 崩溃（blob 已全部上传完却前功尽弃）；
    #   ② 创建 tree / commit 失败即 sys.exit(1)，明明外层就是 3 次重试循环却不复用，
    #      一次瞬时网络抖动 = 整批 raw_data 不落地（与 157 轮同一失败家族）。
    # 改为：本轮任一步失败 → 记录原因 → continue 进入下一次重试；3 次耗尽才退出。
    last_err = ""
    for attempt in range(1, 4):
        # 重新读取最新 main（与 build_deploy 并发安全）
        r2 = api("GET", f"/repos/{REPO}/git/refs/heads/main")
        if "__error__" in r2 or "object" not in r2:
            last_err = f"读取 main ref 失败: {r2.get('__msg__')}"
            print(f"⚠️ {last_err}，重试 ({attempt}/3)"); _t.sleep(2 ** attempt); continue
        base_sha2 = r2["object"]["sha"]
        cmt2 = api("GET", f"/repos/{REPO}/git/commits/{base_sha2}")
        if "__error__" in cmt2 or "tree" not in cmt2:
            last_err = f"读取 base commit 失败: {cmt2.get('__msg__')}"
            print(f"⚠️ {last_err}，重试 ({attempt}/3)"); _t.sleep(2 ** attempt); continue
        base_tree2 = cmt2["tree"]["sha"]
        # 修复②：变更文件 >100 时分批链式创建 tree（base_tree 逐批叠加），杜绝单请求超时。
        _BATCH = 100
        _cur_base = base_tree2
        _tree_ok = True
        for _bi in range(0, len(tree_items), _BATCH):
            _batch = tree_items[_bi:_bi + _BATCH]
            _nt = api("POST", f"/repos/{REPO}/git/trees",
                      {"base_tree": _cur_base, "tree": _batch})
            if "__error__" in _nt or "sha" not in _nt:
                last_err = f"创建 tree 分批{_bi // _BATCH + 1}失败: {_nt.get('__msg__')}"
                print(f"⚠️ {last_err}，重试 ({attempt}/3)"); _t.sleep(2 ** attempt)
                _tree_ok = False
                break
            _cur_base = _nt["sha"]
        if not _tree_ok:
            continue
        new_tree = {"sha": _cur_base}
        commit = api("POST", f"/repos/{REPO}/git/commits",
                     {"message": msg, "tree": new_tree["sha"], "parents": [base_sha2]})
        if "__error__" in commit or "sha" not in commit:
            last_err = f"创建 commit 失败: {commit.get('__msg__')}"
            print(f"⚠️ {last_err}，重试 ({attempt}/3)"); _t.sleep(2 ** attempt); continue
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
    print(f"❌ 3 次重试后仍失败{('：' + last_err) if last_err else ''}"); sys.exit(1)


if __name__ == "__main__":
    main()
