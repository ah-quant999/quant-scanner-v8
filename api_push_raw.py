#!/usr/bin/env python3
# api_push_raw.py — 经 GitHub REST API 把 raw_data/ 推送到 main
# 绕过 git：本机(cn runner, NETWORK SERVICE)无法直连 github.com 的 git/HTTPS 协议，
# 但 api.github.com 可达。故用 Git Database API 以「单次 commit」方式提交 raw_data。
import os, sys, json, base64, hashlib, datetime, re
import urllib.request, urllib.error
import urllib.parse
from urllib.parse import quote
import http.client
import time as _time
import subprocess
import threading
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


# ═══════════════════════════════════════════════════════════════════════════
# 🛡 2026-09-17 一劳永逸加固（阿狸咪的工程师）
#   【症状】2026-09-16 20:25 派发的算法链 run #1883 在「📤 唯一推送」步**僵死 3h55m**
#     （job 日志端点返回 BlobNotFound ⇒ 进程已死但状态未上报），
#     占死 v8-algo-cloud 并发组 ⇒ #1884 cancelled / #1885 排队 1h21m
#     ⇒ 回测批（E）与因子实验室整夜没落盘，前端「因子」卡停在 2 天前。
#   【机制·源码实测】本脚本主循环对**每个变更的 .json** 都会
#     api("GET", /git/blobs/{远端sha}) 取时间戳做防倒退比对，而 api() 的 GET
#     有 3 次重试、每次 timeout=300s ⇒ 单请求最坏 906s；
#     blob 上传循环更是 BLOB_MAX_TRY=8 × 300s。网络劣化时总时长**无上限**，
#     只有 job 级 timeout-minutes=360 兜底 ⇒ 最坏堵满 6 小时。
#   【加固】① 心跳式看门狗：连续 PUSH_IDLE_LIMIT_SEC 秒**无任何进展**才判挂死强退
#            （正常慢速推送每处理完一个文件就 _beat()，不会误杀）；
#          ② 小请求不再吃 300s 超时（防倒退 blob 查询 45s / index.html 90s）。
#   【为何强退而非静默跳过】退出码非 0 才会让 run 失败并**释放并发组**，
#     下轮派发自动续推；静默 exit 0 = 假成功，正是主人明令禁止的。
# ═══════════════════════════════════════════════════════════════════════════
_PUSH_HEART = [_time.time()]
_IDLE_LIMIT = int(os.environ.get("PUSH_IDLE_LIMIT_SEC", "480"))


def _beat(what=""):
    """标记「本轮有进展」。任何一次成功的网络往返 / 文件处理都应调用。"""
    _PUSH_HEART[0] = _time.time()
    if what:
        print("      ⏱ 心跳 " + str(what), flush=True)


def _start_watchdog():
    def _wd():
        while True:
            _time.sleep(10)
            idle = _time.time() - _PUSH_HEART[0]
            if idle > _IDLE_LIMIT:
                print("=" * 78, flush=True)
                print("⏱ 推送已 %d 秒无任何进展（> 上限 %d 秒）⇒ 判定跨境网络挂死。"
                      % (int(idle), _IDLE_LIMIT), flush=True)
                print("   本进程立即退出（exit 1）：让 v8-algo-cloud 并发组释放，"
                      "避免整条算法链被单步堵死 6 小时。", flush=True)
                print("   已上传成功的 blob 仍在 GitHub 侧（未提交 tree/commit 不影响 main），"
                      "下轮派发会自动续推。", flush=True)
                print("   若确认只是「很慢」而非挂死，把环境变量 PUSH_IDLE_LIMIT_SEC 调大即可。",
                      flush=True)
                print("=" * 78, flush=True)
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
                os._exit(1)
    threading.Thread(target=_wd, daemon=True).start()


def api(method, path, data=None, timeout=300):
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
            with urllib.request.urlopen(req, timeout=timeout) as r:
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
            # 🔴 2026-09-11 修复（今夜 P0 事故·一劳永逸）：
            #   原实现只对「网络类异常」重试，HTTPError 一律立即 return →
            #   api() 的 3 次重试对 HTTP 5xx 形同虚设。实测今夜 run#1689：
            #   `GET /git/trees/{sha}?recursive=1 -> HTTP 500`（GitHub 瞬时故障）
            #   → 防倒退守卫拿不到基线 → sys.exit(1) → **整条链算完却零推送**，
            #   主站最终推荐整天停在昨天。
            #   修法：幂等请求(GET)遇 5xx / 429（可重试瞬时错）走退避重试。
            if method.upper() == "GET" and (e.code >= 500 or e.code == 429) and i < attempts - 1:
                wait = 2 ** i
                print(f"     ↻ HTTP {e.code} 属可重试瞬时故障，{wait}s 后重试 {i + 1}/{attempts - 1}")
                _time.sleep(wait)
                last_msg = f"HTTP {e.code}"
                continue
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


def _api_get_raw(path, timeout=120, max_bytes=None):
    """GET 取「正文」而非 JSON（raw 通道）。

    🔴 为什么必须存在：`GET /git/blobs/<sha>` 返回 base64 JSON，GitHub 对**大响应**
       的传输在中途断流时，urllib 抛 IncompleteRead 且**无法续传**；
       而 `GET /contents/<path>?ref=<sha>` 配 `Accept: application/vnd.github.raw`
       是**直出正文**、命中 max_bytes 即停（只读头部），单次成功率远高于 git/blobs。

    🔴🔴 2026-09-17 关键实测（阿狸咪的工程师）——**`Accept` 与 `X-GitHub-Api-Version`
       两者不能同用**！同一 URL、同一 token，仅差请求头：
         Accept: application/vnd.github.raw + X-GitHub-Api-Version: 2022-11-28 → IncompleteRead（必失败）
         Accept: application/vnd.github.raw（**不带版本头**）→ OK 逐字节全量（必成功）
       ⇒ 本函数**刻意不发** `X-GitHub-Api-Version`。
    🔴🔴🔴 同夜更深一层的真根因：Windows+OpenSSL 在 ~1.2MB 处把 TLS 连接被中段
       误标为 `FileNotFoundError(2)`，http.client 则抛 `IncompleteRead`。已读到的
       **部分字节对「取头部时间戳」仍可用**（v8 所有 raw_data JSON 的 update_time
       都在文件头部）。故 max_bytes 模式下：达到上限或已攒够头部即返回部分字节
       （best-effort），不再把断流当失败 —— 这正是 E 批守卫 488s 超时的根因解法。
    返回 (bytes, err_str)；成功时 err_str 为空串。
    """
    url = API + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github.raw",
    }
    last = ""
    buf = bytearray()
    _HEAD_MIN = 65536  # 头部时间戳足够用的下限
    for i in range(4):  # 4 次（含首试），每次新建连接
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                buf = bytearray()
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        return bytes(buf), ""
                    buf.extend(chunk)
                    if max_bytes and len(buf) >= max_bytes:
                        return bytes(buf[:max_bytes]), ""
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            print(f"  ⚠️ RAW GET {path} -> HTTP {e.code}")
            if e.code in (500, 502, 503, 504, 429) and i < 3:
                _time.sleep(2 ** i)
                last = f"HTTP {e.code}"
                continue
            return b"", f"HTTP {e.code} {body}"
        except (TimeoutError, urllib.error.URLError, OSError,
                http.client.HTTPException) as e:
            last = f"{type(e).__name__}: {e}"
            print(f"  ⚠️ RAW GET {path} -> 网络异常 {last}")
            # best-effort：已达上限或已攒够头部 → 部分字节即可取时间戳，直接返回
            if max_bytes and len(buf) >= min(max_bytes, _HEAD_MIN):
                return bytes(buf), ""
            if i < 3:
                _time.sleep(2 ** i)
    # 重试耗尽：若已攒够头部仍返回部分字节；否则报错
    if max_bytes and len(buf) >= _HEAD_MIN:
        return bytes(buf), ""
    return b"", last


def _blob_text(commit_ref, path, blob_sha=None, max_bytes=None, local_size=None):
    """取远端某路径在指定 commit 上的**正文文本**（优先 raw 通道，退 base64 JSON）。

    🔴 通道选择依据（2026-09-17 本机 + 云端 E 批双实测）：
       · `contents/<path>?ref=<commit_ref>` + `Accept: application/vnd.github.raw`
         （**不带** X-GitHub-Api-Version）：1.2MB 级一次成功率远高于 git/blobs；
         配合 max_bytes 只读头部，几乎不撞 ~1.2MB 传输墙。
       · `git/blobs/<blob_sha>`：返回 base64 JSON，1.2MB 级必现 IncompleteRead，
         99MB 级超时/挂死 —— 是 E 批 13 个产物零推送的元凶。
    🔴🔴 关键（已实测抓出）：`contents?ref=` 只认 commit/branch/tag **ref**，
          **绝不认 blob sha**；而 `git/blobs` 才认 blob sha。两通道必须分别传
          commit_ref 与 blob_sha，否则会出现「404 → 回落 git/blobs 又截断」的假成功。
    返回 (text_or_None, 通道名)。
    """
    if path and commit_ref:
        cap = max_bytes if max_bytes else 3 * 1024 * 1024
        b, err = _api_get_raw(
            f"/repos/{REPO}/contents/{quote(path, safe='')}?ref={commit_ref}",
            timeout=120, max_bytes=cap)
        if not err and b:
            return b.decode("utf-8", "replace"), "contents-raw"
        if err:
            print(f"  ⚠️ raw 通道失败（{path} @ {str(commit_ref)[:10]}）: {err[:120]}")
    # 退路：base64 JSON（用 blob_sha；仅小文件；大文件此处必失败 → 交给调用方兜底）
    if blob_sha:
        rb = api("GET", f"/repos/{REPO}/git/blobs/{blob_sha}", timeout=45)
        if "__error__" not in rb and rb.get("encoding") == "base64":
            try:
                return base64.b64decode(rb["content"]).decode("utf-8", "replace"), "blobs-b64"
            except Exception:
                return None, "blobs-b64-decode-fail"
    return None, "none"

# 🛡 2026-09-08 审计产物保护（主人令）：审计轨迹只由本机审计脚本经 git 推送（audit_history.json / audit_nightly.log），
#   绝不走 api_push_raw 裸推。否则 cn runner 工作区里的旧审计文件会经 Git Database API 覆盖 main 上的新版，
#   吞掉历史审计轨迹（实测 09-08 多轮审计记录丢失）。此处 + main() PUSH_FILES 分支双重跳过。
# 🛡🛡 2026-09-20 防覆盖护栏（阿狸咪的工程师，家机 alimi-cn 三查实证后落码）：
#   **index.html 绝不从本地推。** 三条铁证（均于 2026-09-20 08:5x 复跑过）：
#     ① 本脚本 PUSH_FILES 分支是从**本地磁盘**读文件（open(_rel, "rb")），而云端 job
#        从 checkout 到推送有数分钟窗口 ⇒ 读-改-写竞态，与 2026-08-09 数据回退事故同一根因；
#     ② 本脚本两道守卫对它**双双失效**：守卫基线 existing 只收 raw_data/ + data/
#        （_GUARD_PREFIXES）⇒ remote_sha=None ⇒「内容一致」与「防倒退」两条都不生效；
#     ③ 数据类即便守卫失效也还有 path.endswith(".json") 兜底，而 index.html 是 .html
#        ⇒ 连这层兜底都没有（双重豁免）。
#   已在案的真实风险面：v8_cn_fetch_experiments.yml（cron 30 8 * * 1-5 = 每日 16:30 CST）
#     把 index.html 放进 PUSH_FILES，且**全程没有任何 git fetch / reset** ⇒ 会把 checkout
#     时刻的 index.html 以「最新 main」为 base_tree 提交回去 = 静默覆盖他人前端改动
#     （无冲突、无告警、无 422）。
#   夹具对照已证（docs/ops/handover/2026-09-20_*_api_push_raw防覆盖.md）：
#     同一夹具下旧版把本地陈旧 index.html 推上去（True），新版不入提交（False）且其余文件照常推。
#   ⇒ 正解：index.html 的 ?v 一律「**取远端最新正文**（raw 通道，绕开 Contents API 的
#     1MB 截断）+ 就地重算单调令牌」后再随本提交原子落地，见 _stamp_remote_index_v；
#     本地副本永不入队。
_SKIP_LOCAL_PUSH = {"index.html"}
_PROTECTED_RAW = {
    "raw_data/audit_history.json",
    "raw_data/audit_nightly.log",
}


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
# 🔴 2026-09-20 补漏（阿狸咪 2313 档 §六-②）：远端 .gitattributes 新增
#    `data/*.json` 与 `raw_data/history/*.json` 两条 eol=lf，本内联表须同步，
#    否则真源模块缺失时会漏判这两族行尾。两条均不跨 `/`、不递归。
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
    if len(parts) == 2 and parts[0] == "data" and (
            parts[1].endswith(".js") or parts[1].endswith(".json")):
        return True
    if len(parts) == 2 and parts[0] == "raw_data" and parts[1].endswith(".json"):
        return True
    if (len(parts) == 3 and parts[0] == "raw_data" and parts[1] == "history"
            and parts[2].endswith(".json")):
        return True
    return False


def _eol_load_module():
    """加载 scripts/normalize_eol.py（单一真源）；失败返回 None → 退内联规则。"""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "scripts", "normalize_eol.py")
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
        # 2026-09-18 主人令：cockpit_backtest 前缀随驾驶舱下线彻底删除
        "optimized_strategy",# export_optimized_strategy.py
        "algo_track",         # gen_algo_track.py（2026-08-15 三算法追踪）
        "commodity_prices_cache",  # calc_commodity_elasticity.py westock 价格缓存（MCP 预抓取）
    )
    push_algo_raw = os.environ.get("PUSH_ALGO_RAW") == "1"
    # 🔴 2026-09-10 阿狸咪根因修复（主人令「全面审计瘦身·千万别删错」）：
    #   原实现 os.walk("raw_data") 全量遍历，只排除「算法产物词根」+ _PROTECTED_RAW，
    #   对【运行时缓存 / 写前备份 / 临时件】零排除。而本函数走 GitHub Git Data API
    #   （blobs/trees/commits）创建提交 —— **完全绕开 .gitignore**。
    #   实测后果（09-01→09-10 仓库 +111MB 的主要来源）：
    #     · raw_data/_rps_cache/* 461 个 / 28.5MB 回潮（08-29 已 git rm --cached 过一次）
    #     · raw_data/*.bak 15 个 / 5.3MB（fetcher 写前备份，scripts/raw_retention.py 已在归档）
    #   实证：raw_data/stock_names.json.bak 由 `v8 cn fetch: 2026-09-05 20:54` 引入本函数。
    #   此处按「目录名剪枝 + 后缀过滤」双重排除，与 .gitignore / DO_NOT_DELETE.md L63 同口径。
    #   ⚠️ 有意不排除 kline_cache：2026-09-08 主人令明确入仓（云端零网络取数，根治静默断更）。
    _SKIP_DIR_NAMES = ("__pycache__", "_rps_cache", "_tdx_cache", "_archive")
    _SKIP_SUFFIXES = (".bak", ".tmp", ".pyc", ".pyo")
    for root, _dirs, files in os.walk("raw_data"):
        # 就地剪枝：不进入被排除的目录（os.walk 原生支持，顺带省一遍遍历）
        _dirs[:] = [d for d in _dirs if d not in _SKIP_DIR_NAMES]
        for f in files:
            if f.startswith(_ALGO_RAW_PREFIXES) and not push_algo_raw:
                continue
            if f.endswith(_SKIP_SUFFIXES):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, ".").replace("\\", "/")
            if rel in _PROTECTED_RAW:  # 🛡 审计产物保护：跳过，不进裸推队列
                continue
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


# 🔴 2026-09-17 加固：传输层断流时远端读取是**截断**的，完整 JSON 解析必失败。
#   故用正则扫描头部字节兜底，仍能命中顶层时间戳（v8 所有 raw_data JSON 的
#   update_time 均在文件头部，截断不影响）。
_TS_RE = re.compile(
    rb'"(?:update_time|gen_time|calc_time|run_time|fetch_time|snapshot_time)"'
    rb'\s*:\s*"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})')

def _content_ts(content: bytes):
    """从 JSON 内容里取顶层时间戳（归一为「YYYY-MM-DD HH:MM」分钟级字符串），取不到返回 None。

    🔴 2026-09-17 加固：远端守卫读取可能因传输层断流而**截断**（见 _api_get_raw）。
       完整 JSON 解析会失败，故先试 json.loads；失败再用正则扫描头部字节，
       仍能命中顶层时间戳（v8 所有 raw_data JSON 的 update_time 均在文件头部）。
    🔴 两种路径**必须归一为同一格式**（分钟级、无尾冒号），否则 guards 的
       `lts < rts` 字符串比较会因精度不一致而误判。
    """
    if not content:
        return None
    best = None
    try:
        obj = json.loads(content.decode("utf-8"))
        if isinstance(obj, dict):
            for k in _TS_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and len(v) >= 16 and v[4] == "-":
                    s = v[:16].replace("T", " ").rstrip(":")  # → YYYY-MM-DD HH:MM
                    if len(s) >= 15 and s[4] == "-" and s[10] == " ":
                        if best is None or s > best:
                            best = s
    except Exception:
        pass
    if best:
        return best
    # 兜底：正则扫描（兼容截断）—— 仅扫前 1MB 字节足矣
    m = _TS_RE.search(content[:1 << 20])
    if m:
        s = m.group(1).decode("ascii").replace("T", " ")
        return s  # 已是 YYYY-MM-DD HH:MM（15 字符）
    return None



def walk_extra():
    """额外推送文件（不在 raw_data/，但由算法脚本直接写 data/）。

    2026-08-10 补入：final_recommend / strategy_four_volume_60m /
    export_optimized_strategy 等脚本直接写 data/*.js 或 raw_data/*.json，
    需在此注册才能被 api_push 推送到 main。
    """
    out = {}
    extra = [
        "data/FOUR_VOLUME.js",          # 四量终极日线版（gen_triple_consensus 产出）
        "data/STOCK_STOP_DATA.js",      # ATR止损止盈（gen_stock_stop 产出）
        # ── 2026-08-10 补入：之前缺失导致这些文件永远不刷新 ──
        "data/FINAL_RECOMMEND_DATA.js", # 跨策略共振 Top3（final_recommend.py 产出）
        "data/FOUR_VOLUME_60M.js",      # 四量终极60min版（strategy_four_volume_60m.py 产出）
        # ── 2026-08-17 补入：商品涨价弹性榜（calc_commodity_elasticity.py 产出）──
        # 之前未注册，导致国内期货 LC/SA 数据永远不显示；现加入云端自动跑 + 推送
        "data/COMMODITY_ELASTICITY.js",
        # ── 2026-08-19 补入：H 反推短线买点 + 跟踪（auto_run_dn_algorithm / track_h_auto_buy） ──
        # 之前仅手动 commit，未注册到 api_push 队列 → 每天盘后算法链跑完也不上传。
        "data/H_AUTO_BUY.js",           # 反推算法当日候选（脱离 PDF OCR）
        # ── 🆕 2026-09-11 补入：全算法回测汇总（gen_backtest_all_algos.py 产出）──
        #   本文件不在 update_v8.py 的 raw→js 映射表内（由脚本自己直接写 data/），
        #   按本函数约定「需在此注册才能被 api_push 推到 main」。
        "data/BACKTEST_ALL_ALGOS.js",
        # 🗑 2026-09-20 摘除登记（阿狸咪的工程师）：原登记项 "data/ALGO_BACKTEST_COMPARE.js"。
        #   该产物由 scripts/algo_backtest_compare.py 直写 data/，2026-09-13 因「强势突破」回测源
        #   而登记上传；现随该模块**全站删除**一并退役，理由（已实证）：
        #     ① 其唯一消费卡「两套算法回测对比」属主人 2026-09-02 明令删除的模块；
        #     ② CDP 真浏览器实测（2026-09-20）：切到「暂未上架」后 ul-pane 数 = 0，
        #        ulPaneStrong 非元素 ⇒ 该卡**全站零生效路径**，产物无人可见；
        #     ③ 生成脚本已同步从算法链 E 批摘除（algorithms/run_algorithms.py ORDER + STAGES）。
        #   ⚠️ 不得再登记回本表；如日后恢复该卡，须先恢复前端渲染（主人令）再一并恢复生产与上传。
        "data/H_AUTO_BUY_TRACK.js",     # 反推算法累计胜率（每日跟踪 T+1/T+3/T+5/T+10）
        # 🧹 2026-09-15：data/LHB_7D.js 已随「无生产者 + 前端零引用」一并退役删除，
        #   故此处不再登记（原 2026-08-20 登记项作废）。
        # 🆕 2026-09-13 主人令「PE/PB 方案 A 落地」：中信 PE 极值温度计双卡产物。
        #   gen_citic_pe.py 直写 data/（不经 update_v8 的 raw→js 映射表）⇒ 必须在此登记。
        #   🔴 不登记 = **降级路径半边修复**：PUSH_FILES 模式（workflow 用 git status 收集
        #      变更）能推到它们，但「清单不可得」时的全量回退
        #      （walk_raw + walk_extra）推不到 ⇒ CITIC 永不刷新。
        "data/CITIC_PE_THERMO.js",      # 中信证券 PE 极值温度计（含分位/极值判定）
        "data/CITIC_PE_BACKTEST.js",    # 中信证券 PE 分位分层历史回测
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
    "data/FOUR_VOLUME_60M.js",
    # 🛡 2026-08-19：H 反推算法相关文件注册到 ?v 重写集，确保 api_push 推送后 index.html 同步对齐缓存戳
    "data/H_AUTO_BUY.js",
    "data/H_AUTO_BUY_TRACK.js",
    # 🧹 2026-09-15：data/LHB_7D.js 已退役删除（同上方 extra 段说明），?v 重写集一并摘除。
    # 2026-08-19：路径概率预测卡（艾略特+江恩+缠论+形态匹配）注册到 ?v 重写集
    "data/INDEX_HISTORY.js",
    # 2026-08-19：板块推荐框架（宏观+板块RS+资金流+周期融合）注册到 ?v 重写集
    "data/MARKET_REGIME.js",
    "data/SECTOR_RECOMMENDATION.js",
    # 🆕 2026-09-13 主人令（PE/PB 方案 A）：中信 PE 双卡注册进 ?v 重写集。
    #   不登记 ⇒ api_push 推了新内容但 index.html 的 ?v 仍指旧哈希 ⇒ CDN/浏览器
    #   吐旧副本，最长撑到 reconcile workflow 跑（~15min 窗口）。
    "data/CITIC_PE_THERMO.js",
    "data/CITIC_PE_BACKTEST.js",
    # 🛡 2026-08-19 阿狸咪根治孤儿：data/MACRO.js 删除（前端 render 0 处引用 window.MACRO）—节省空间+Actions分钟
)
_RE_V = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?[^"\'>\s]+)?([\'"])')


# ⚠️⚠️ 已废除口径（2026-09-10 主人令）——下面这个 sha1 内容哈希**不得再用于 index.html 的 ?v**：
#   · 理由：内容哈希在「数据被回滚到旧内容」时哈希恰好等于旧版 ⇒ 浏览器缓存旧 ?v 永远吐旧数据
#     （表现为「最终推荐回退到 2 天前」「盘中主线卡在旧时刻」）；
#   · 现行口径 = 单调 unix 秒令牌（update_v8._data_file_update_time 与 _stamp_remote_index_v）；
#   · 本仓已有核验会对十六进制形态报警并重写：
#     v8_build_deploy.yml「?v 出现非 unix 秒令牌(旧内容哈希口径回潮)」。
#   ⇒ 2026-09-20 起 index.html 的 ?v 一律走 _stamp_remote_index_v；两者仅作历史留痕。
#     （已证本仓 workflows 内无其他调用点；如需彻底删除请先确认无外部 importer。）
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

def _stamp_remote_index_v(changed: dict, commit_ref: str):
    """取**远端** index.html 正文（raw 通道，绕开 Contents API 的 1MB 截断），
    对 changed 中每个 data/*.js 写入**单调部署令牌**（unix 秒）后就地提交；
    返回新 blob sha（无需改动返回 None）。

    🔴 基准必须是**远端正文**（commit_ref），绝不允许使用本地副本：本地是 checkout 快照，
       直接上传会以「最新 main」为 base_tree 静默覆盖他人的前端改动（见 _SKIP_LOCAL_PUSH）。

    🔴 ?v 口径 = **单调 unix 秒令牌**，与 update_v8._data_file_update_time 的 _UPDATE_TOKEN 同源。
       为何不能用内容哈希：2026-09-10 主人令已改口径 —— 内容哈希在「数据被回滚到旧内容」时
       哈希恰好等于旧版 ⇒ 浏览器缓存旧 ?v 永远吐旧数据（表现为「最终推荐回退到 2 天前」
       「盘中主线卡在旧时刻」）。且本仓已有核验会对十六进制形态报警：
       v8_build_deploy.yml「?v 出现非 unix 秒令牌(旧内容哈希口径回潮)」。
       ⇒ 在此处写 sha1 形态 = 被判口径回潮并触发一次重写，禁止使用 _neutral_sha。

    🔴 旧实现为何必须换掉（2026-09-20 实测）：旧代码走 `GET /contents/index.html` 取正文，
       而 index.html 现为 1.36MB > Contents API 的 1MB 上限 ⇒ 返回 encoding="none" +
       content=""（**键存在、值为空串**）⇒ base64 解出空串 ⇒ _stamp_index_v("") 恒无改动
       ⇒ 打印「ℹ️ index.html ?v 已一致，无需改动」。**这是假成功**：既没对齐，也没说明
       取不到正文。新实现改走 _blob_text（contents?ref= + raw，与守卫时间戳同一通道），
       取不到正文时**显式告警**，绝不谎报「已一致」。
    """
    idx_text, _chan = _blob_text(commit_ref, "index.html", None, max_bytes=8 * 1024 * 1024)
    if not idx_text:
        print("  ⚠️ 取远端 index.html 正文失败（raw + base64 双通道皆不可用）→ ?v 交由 reconcile 自愈")
        return None
    tok = str(int(_time.time()))
    _pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?v=[0-9A-Za-z]+)?([\'"])')

    def _repl(m):
        if m.group(2) in changed:
            return f"{m.group(1)}{m.group(2)}?v={tok}{m.group(3)}"
        return m.group(0)

    new_idx = _pat.sub(_repl, idx_text)
    if new_idx == idx_text:
        print("  ℹ️ index.html 无需改动（本次变更文件不在 ?v 重写集内）")
        return None
    ib = api("POST", f"/repos/{REPO}/git/blobs",
             {"content": base64.b64encode(new_idx.encode("utf-8")).decode(),
              "encoding": "base64"})
    if "__error__" in ib or "sha" not in ib:
        print("  ⚠️ index.html blob 上传失败，?v 将交由 reconcile 自愈")
        return None
    print(f"  🔄 index.html ?v 已重写为单调令牌 {tok}（{len(changed)} 个文件）")
    return ib["sha"]
def _local_tree_paths(base_sha, want_prefixes):
    """用本地 git ls-tree 直接取「受管路径 → blob sha」，**零网络请求**。

    🔴 2026-09-12 一劳永逸修复（P0·小九机链推不出去）——这是最终方案，理由：

      原实现：单次 `GET /git/trees/{sha}?recursive=1`（全仓 3913 文件 ≈1.24MB）→
              跨境必 IncompleteRead ×3 → 拒绝推送 → 整夜白跑（小九机 #1772/#1773 实证）。

      我曾试「分层 BFS + 剪枝」：单次响应降到 41KB，但实测**必须把
      raw_data/kline_cache 排除**才能降下来，而该目录有 3119 个文件、742.6KB
      单层响应（扁平目录、GitHub tree API 不支持分页）。一旦排除它，
      existing 就缺 3119 条 ⇒ 防倒退守卫对 K 线缓存完全失效
      （正是 08-09 大范围数据回退的老路，比崩溃更危险）。

      **真正的事实**：本脚本运行在 runner / 小九机的工作区里，那里本来就有一份
      完整 git 仓库，`git ls-tree -r <sha> -- raw_data/ data/` 一条本地命令就能拿到
      全部 3474 条受管路径的 sha —— 零网络、零截断、零重试、毫秒级。
      用 Git API 去枚举「本地已有的东西」从一开始就是错误路线。

    返回 (mapping, ok)；ok=False 表示本地也拿不到（调用方须拒绝裸推）。
    """
    # 仓库目录解析：环境变量 > 脚本所在目录 > cwd > 逐级向上找 .git
    # （加固原因：不能假定脚本一定就在仓库根，实测在仓库外跑会静默返回空）
    cands = []
    _env = os.environ.get("V8_REPO_DIR", "").strip()
    if _env:
        cands.append(_env)
    cands.append(os.path.dirname(os.path.abspath(__file__)))
    cands.append(os.getcwd())
    repo_dir = None
    for c in cands:
        if c and os.path.isdir(os.path.join(c, ".git")):
            repo_dir = c
            break
    if repo_dir is None:
        print(f"  ⚠️ 未找到 git 仓库根（候选: {cands}），本地 ls-tree 不可用")
        return {}, False
    out = {}
    for pre in want_prefixes:
        args = ["git", "ls-tree", "-r", base_sha]
        if pre:
            args += ["--", pre]
        try:
            r = subprocess.run(args, cwd=repo_dir, capture_output=True,
                               text=True, timeout=180)
        except Exception as e:
            print(f"  ⚠️ git ls-tree {pre or '*'} 异常: {e}")
            continue
        if r.returncode != 0:
            print(f"  ⚠️ git ls-tree {pre or '*'} 失败: {r.stderr.strip()[:200]}")
            continue
        for ln in r.stdout.splitlines():
            try:
                meta, path = ln.split("\t", 1)
                mode, typ, sha = meta.split()
            except ValueError:
                continue
            if typ == "blob":
                out[path] = sha
    return out, bool(out)


def _remote_tree_paths(base_tree, want_prefixes):
    """兜底：本地 git 不可用时，分层 BFS 枚举远端 tree（单次响应 ≤41KB）。

    ⚠️ 已知局限：为避免 742.6KB 的 raw_data/kline_cache 单层响应触发截断，
       本函数会把 kline_cache 等重目录剪掉 ⇒ 返回的基线**不含**这些路径。
       因此它只是本地 ls-tree 的降级预案；调用方应优先走 _local_tree_paths，
       并在本函数结果不完整时继续降级（绝不拿残缺基线当守卫）。

    ⚠️ 关键坑：tree 条目里的目录名**不带尾斜杠**（"raw_data/kline_cache" 而非
       "raw_data/kline_cache/"），因此必须用 `p == K or p.startswith(K + "/")` 判定，
       直接 startswith("xxx/") 会永远匹不中（在 algo_cloud.yml 里先踩过一次）。
    """
    SKIP = ("backup", "docs", "raw_data/kline_cache", "legacy_v6", "out",
            "tdx_formulas", ".git")

    def _skip(p):
        return any(p == k or p.startswith(k + "/") for k in SKIP)

    out = {}
    queue = [("", base_tree)]
    seen = 0
    while queue:
        prefix, sha = queue.pop(0)
        seen += 1
        if seen > 80:
            print("  ⚠️ tree 遍历层数超限（>80），判定枚举不完整")
            return out, False
        d = api("GET", f"/repos/{REPO}/git/trees/{sha}")
        if "__error__" in d or "tree" not in d:
            print(f"  ⚠️ 分层枚举中断于「{prefix or '/'}」: {d.get('__msg__') or d}")
            return out, False
        if d.get("truncated"):
            print(f"  ⚠️ 分层枚举「{prefix or '/'}」被 GitHub 截断")
            return out, False
        for e in d["tree"]:
            p = prefix + e["path"]
            if e["type"] == "tree":
                if _skip(p):
                    continue
                # 只在「该子树可能含有受管路径」时才下钻，避免无谓请求
                if not any((p + "/").startswith(k) or k.startswith(p + "/")
                           for k in want_prefixes):
                    continue
                queue.append((p + "/", e["sha"]))
            elif e["type"] == "blob":
                if not _skip(p) and p.startswith(want_prefixes):
                    out[p] = e["sha"]
    return out, True


def _local_tree_fallback(base_sha):
    """GitHub tree API 不可用（5xx/截断）时，用本地 git ls-tree 生成等价守卫基线。

    🔴 2026-09-11 补：调用点在下方 main() 里（原 P0 修复注释声明"见 _local_tree_fallback"），
      但本函数**从未被定义** —— 一旦 GitHub tree 接口抽风，此处会 NameError 直接把
      整夜算出的成果全丢掉（正是那次 P0 想避免的后果）。
      返回 {"tree": [{"path","mode","type","sha"}...]}；拿不到返回 None（调用方会拒绝裸推）。
    """
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    for cmd in (["git", "ls-tree", "-r", base_sha],):
        try:
            r = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=180)
        except Exception:
            continue
        if r.returncode != 0 or not r.stdout.strip():
            continue
        tree = []
        for ln in r.stdout.splitlines():
            try:
                meta, path = ln.split("\t", 1)
                mode, typ, sha = meta.split()
            except ValueError:
                continue
            tree.append({"path": path, "mode": mode, "type": typ, "sha": sha})
        if tree:
            return {"tree": tree}
    return None


def main():
    # 🛡 2026-09-17：心跳看门狗。无进展超 PUSH_IDLE_LIMIT_SEC 即强退，
    #   绝不让「唯一推送」单步堵死整条算法链（#1883 僵尸事件根治）。
    _start_watchdog()

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
            if _rel in _PROTECTED_RAW:  # 🛡 审计产物保护：绝不裸推
                print(f"  🛡 跳过审计产物（不进 api_push 队列）: {_rel}")
            if _rel in _SKIP_LOCAL_PUSH:
                # 🛡 防覆盖：index.html 只从远端正文重算 ?v，绝不推本地字节（见 _SKIP_LOCAL_PUSH 取证）
                print(f"  🛡 防覆盖：{_rel} 不从本地推（其 ?v 由远端正文就地重算）")
                continue
                continue
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
        # 🛡 防覆盖：全量收集路径同样绝不让本地 index.html 入队（与 PUSH_FILES 分支同一道护栏）
        for _p in list(files):
            if _p in _SKIP_LOCAL_PUSH:
                print(f"  🛡 防覆盖：{_p} 不从本地推（其 ?v 由远端正文就地重算）")
                files.pop(_p)
    # 🛡 2026-09-20 推边界行尾收口（见上方 fold_eol 注释）：必须在 _blob_sha/守卫之前
    fold_eol(files)

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
    # 🔴 2026-09-12 一劳永逸修复（P0·小九机链推不出去）：
    #   原实现单次 `?recursive=1`（全仓 3913 文件 ≈1.24MB）→ 跨境必 IncompleteRead
    #   ×3 → 走兜底或直接拒绝 → 每跑一轮盘后就在这白跑一次。
    #   现改为「本地 git ls-tree 优先（零网络，3474 条一次拿全，含 kline_cache 3119 条）
    #          → 本地不可用才退分层 API 枚举（41KB）」，语义与原实现完全等价。
    _GUARD_PREFIXES = ("raw_data/", "data/")
    existing, _ok = _local_tree_paths(base_sha, _GUARD_PREFIXES)
    if _ok:
        print(f"🛡 守卫基线（本地 git ls-tree，零网络）：{len(existing)} 个受管路径")
    else:
        print("⚠️ 本地 ls-tree 不可用 → 退分层 API 枚举作守卫基线")
        existing, _ok2 = _remote_tree_paths(base_tree, _GUARD_PREFIXES)
        if not _ok2 or not existing:
            print("⚠️ 分层 API 枚举亦未完整 → 退本地全量 ls-tree（不带前缀）")
            existing, _ok3 = _local_tree_paths(base_sha, ())
            if not _ok3:
                print("❌ 守卫基线三种取法全失败，拒绝裸推")
                sys.exit(1)
    # 2026-08-11 修复（159 轮看门狗）·数据回退隐患根治：
    # existing 是「防倒退守卫」的唯一基线。原代码用 tfull.get("tree", []) 兜底，
    # 一旦这次 GET 失败或被 GitHub 截断，existing 会静默变成空/残缺 →
    # 所有本地文件都被判为「远端没有」→ 守卫完全失效 → 用 checkout 时刻的旧内容
    # 覆盖远端更新版本，正是 08-09 大范围数据回退故障的成因。
    # 守卫基线不完整时必须中止，绝不能「无守卫裸推」。
    if not existing:
        print("❌ 守卫基线为空，拒绝裸推")
        sys.exit(1)

    # 上传 blobs（幂等：内容相同则 sha 相同）
    # 2026-08-04：GitHub blob API 对较大文件偶发 HTTP 400 "malformed request"（08-03 stock_names.json
    # 325KB 命中，导致整次推送 sys.exit(1)、全部数据不落地）。加 3 次指数退避重试；仍失败则跳过该文件
    # 而不是整体退出——保证其余数十个数据文件能正常上线。
    import time as _t
    new_entries = {}
    failed_paths = []
    unchanged = 0
    regressed = []
    _guard_miss = []
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
            _beat()
            continue
        # (2) 内容不同：比对时间戳，本地更旧则保留远端版本，绝不覆盖
        # 🛡 2026-09-13 一劳永逸：**累积继承型池类产物**豁免本守卫。
        #   根因（远端真源实测）：金股池由两条链写同一份 out/gold_pool.json ——
        #     · algorithms/scanner.py        （算法链 [0-pre]，run_algorithms.py:360）
        #     · algorithms/build_candidate_pool.py（采集批，v8_cn_fetch_cloud.yml:414）
        #   scanner.py 的两处落盘**从不设置顶层 update_time**（整文件 0 处命中），
        #   产出完全继承 prev 旧值（实测 .bak: update_time=2026-09-11 15:00:00，
        #   而远端已是 2026-09-12 00:53:46）⇒ stage_to_raw 搬进 raw_data 后，
        #   本守卫判 lts < rts ⇒ **永久拒推自锁**（远端越新越推不动）。
        #   旁证：commit ed0d5b659 / 485f1719b 里 raw_data/gold_pool.json.bak 被推送、
        #   gold_pool.json 主文件没有 —— 正因为本守卫判据是 `path.endswith(".json")`，
        #   .bak 天然豁免、主文件被拦。
        #   ⚠️ 只豁免「成员单调累积、以磁盘 prev 为输入、覆盖不丢信号」的池类产物。
        #      lhb_history.json 等 **append 型不在豁免内**（本地更短时覆盖会真丢数据）。
        _NO_REGRESSION_GUARD = {
            "raw_data/gold_pool.json",
            "raw_data/gold_pool_stocks.json",
        }
        if (remote_sha and path.endswith(".json")
                and path not in _NO_REGRESSION_GUARD):
            lts = _content_ts(content)
            if lts:
                # 🛡 2026-09-17 一劳永逸（阿狸咪的工程师）：**取远端时间戳改走
                #   contents?ref= raw 通道**（只读头部 256KB，绕开 ~1.2MB 传输墙），
                #   并传 commit_ref=base_sha（contents?ref= 只认 commit/branch，绝不认
                #   blob sha；git/blobs 才认 blob sha）。旧实现 `GET /git/blobs/{sha}`
                #   在 1.2MB 级必现 IncompleteRead（E 批铁证 fe205ffe9383 → 9.9M/104M），
                #   三次重试又复用 req 零退避连败 ⇒ 488s 无进展 ⇒ 看门狗强退 ⇒ 整批 13 个产物零推送。
                rtext, _chan = _blob_text(base_sha, path, remote_sha, max_bytes=256 * 1024)
                rts = _content_ts(rtext.encode("utf-8")) if rtext else None
                if rts and lts < rts:
                    regressed.append((path, lts, rts))
                    _beat()
                    continue
                if rtext and not rts:
                    # 通道通了、只是该 JSON 顶层没有可识别时间戳 ⇒ 正常放行
                    pass
                elif not rtext:
                    # 🔴🔴 通道**本身**失败（raw + base64 双通道皆不可用）≠「本地更新」。
                    #   此时若静默放行，等于用 checkout 时刻的旧内容覆盖远端新版 ——
                    #   正是 08-09 大范围数据回退故障的成因（守卫完全失效）。
                    #   故累计计数，超阈值即**中止整轮**（宁可不推，绝不倒退）。
                    _guard_miss.append(path)
                _beat()
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
            _beat()
            continue
        new_entries[path] = b["sha"]
        _beat()
        _beat()

    # ── 2026-08-15 根治「cn 单独推送 5 个 extra 文件后 ?v 失配」────────────
    # 仅当本次确实推送了 5 个 extra 文件中的一个，才原子更新 index.html 对应 ?v，
    # 使 ?v 与本次落库内容严格一致，消除「新数据上线 ~ reconcile 跑之前」的失配窗口。
    # 若 index.html 拉取/改写/上传任一步失败，则跳过（交由 reconcile workflow 自愈），
    # 绝不因此阻断整批 raw_data 推送。

    # 🔴 2026-09-17 守卫通道失效闸门（阿狸咪的工程师）：若远端时间戳通道本身
    #   大面积失败（raw + base64 双通道皆不可用），说明是通道故障而非「本地更新」；
    #   此时静默放行 = 用本地旧内容覆盖远端（08-09 数据回退事故根因）。
    #   超阈值即**中止整轮**（宁可不推，绝不倒退）。默认阈值 3，可用 GUARD_MISS_ABORT 调。
    _gm_limit = int(os.environ.get("GUARD_MISS_ABORT", "3"))
    if _guard_miss and len(_guard_miss) >= _gm_limit:
        print("❌ 守卫通道失效闸门触发：%d 个文件通道失败 ≥ 阈值 %d，中止整轮（宁可不推）"
              % (len(_guard_miss), _gm_limit))
        sys.exit(7)
    if _guard_miss:
        print("⚠️ 守卫通道部分失败（%d 个，未达阈值，照常推送）：%s"
              % (len(_guard_miss), ", ".join(_guard_miss[:10])))

    extra_changed = {p: files[p] for p in _EXTRA_FILES if p in new_entries}
    # 🛡🛡 2026-09-20 防覆盖（阿狸咪的工程师）：index.html 的 ?v 以**远端最新正文**为基准就地重算，
    #   本地副本永不进提交（见 _SKIP_LOCAL_PUSH 取证）。同时换掉旧 contents 取正文的实现，
    #   根治「>1MB ⇒ 取到空串 ⇒ 谎报『已一致』」的假成功。失败绝不阻断本批数据推送。
    if extra_changed:
        try:
            _ix_sha = _stamp_remote_index_v(extra_changed, base_sha)
            if _ix_sha:
                new_entries["index.html"] = _ix_sha
                print("✅ index.html ?v 已随本批 extra 文件原子更新（基准=远端最新正文）")
        except Exception as _e:
            print(f"  ⚠️ index.html ?v 对齐异常（不影响本批数据推送）：{type(_e).__name__}: {_e}")

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
