#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_urgent_listener.py — 紧急指令监听 + 健康检查（v8 去 v6 化版）
=========================================================
监听 docs/ops/handover/ 下的交接档（唯一交接目录；🔴 2026-09-16 起**全部 .md**，
不再只认 *_URGENT_*.md —— 见下方 `_scan_handover_files_remote` 注释），读取最新内容并：
1. 运行 guard_v8_freshness.py 生成数据新鲜度报告；
2. 扫描交接档中的**显式指令**（第 1 档=显式标记+关键词推断；其余档=显式指令行+
   显式 workflow 名），自动 dispatch 对应 workflow；去重=**文件名+内容 hash**；
3. 输出摘要供 automation 向主人汇报。

🔴 2026-09-16 治本（第三步，P-A）：排序「提交时间优先」在**浅克隆**下会被 graft 边界
污染（一批档拿到同一个假 ``%ct``，不是「取不到」⇒ 原容错不触发、静默退化成文件名口径）
⇒ ① 新增退化检测 ``_is_degenerate_times``；② 检出后退化时对有界近档走 GitHub Commits
API 精算真值 ``_api_commit_ts``（≤12 次请求），失败才退回文件名口径**并在输出显式标注**；
③ 派发权不再单挂 ``files[0]``（``scan_dispatch`` 扫前 8 档 + hash 去重），
即使排序把超前命名档顶到首位，真实新指令也不会被静默漏派。

🔴 2026-09-15 修复（漏读高危）：清单与正文**远端优先**（best-effort git fetch → FETCH_HEAD /
origin/main → git ls-tree / git show），仅当 git 不可用时才降级本机工作树并在输出显式标注。
本机从不 pull，工作树会陈旧（实测 09-15：本机 1 份 vs 远端 10 份）⇒ 只读工作树会把
「真有指令的新交接」误报成「无指令」。

用法:
  python v8_urgent_listener.py              # 扫描 + 健康检查 + 自动 dispatch
  python v8_urgent_listener.py --dry-run    # 仅打印，不真 dispatch
  python v8_urgent_listener.py --no-fetch   # 跳过 git fetch（离线/调试）
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
HANDOVER_DIR = BASE / "docs" / "ops" / "handover"   # 2026-09-10 起唯一交接目录
URGENT_DIR = BASE / "docs" / "ops" / "urgent"        # 已停用（历史目录，勿再写入）
REPO = "ah-quant999/quant-scanner-v8"
HANDOVER_REL = "docs/ops/handover"                   # 仓库内相对路径（远端读取用）

# ---- 2026-09-16 治本（第三步）：浅克隆排序退化处置 + 派发面不再单挂 files[0] ----
GRAFT_MIN_ENTRIES = 5      # 条数少于这个值不判退化（样本太小）
GRAFT_UNIQUE_RATIO = 0.1   # 唯一时间戳占比低于此 ⇒ 判为 graft 边界退化
API_TS_MAX = 12            # 退化时最多走 API 精算的档数（有界，防请求风暴）
API_TS_WINDOW_H = 120      # 只对「文件名时间在近 N 小时」的档做 API 精算
ACTION_SCAN_N = 8          # 显式指令扫描档数（原实现只判 files[0]）
DISPLAY_N = 5              # 输出里展开正文的档数（其余只列名）
ACTION_STATE = BASE / "data" / "_urgent_dispatch_state.json"   # 派发去重状态
SORT_DIAG = {"mode": "-", "api_n": 0, "degenerate": False, "entries": 0, "unique": 0}

# workflow 文件名 -> dispatch payload
WF_MAP = {
    "cn_fetch_cloud": ("v8_cn_fetch_cloud.yml", {"ref": "main"}),
    "cn_fetch":       ("v8_cn_fetch_cloud.yml", {"ref": "main"}),  # 统一走云端主力
    "algo_cloud":     ("v8_algo_cloud.yml",     {"ref": "main"}),
    "algo":           ("v8_algo_cloud.yml",     {"ref": "main"}),
    "build_deploy":   ("v8_build_deploy.yml",   {"ref": "main"}),
    "safety_net":     ("v8_safety_net.yml",     {"ref": "main"}),
    "self_heal":      ("v8_self_heal.yml",      {"ref": "main"}),
    "weekly_cleanup": ("cloud_weekly_cleanup.yml", {"ref": "main"}),
}


def _load_token():
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    for p in [
        BASE / ".workbuddy" / "v8_gh_token.txt",
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def _git(args, timeout=30):
    """跑只读 git 命令（禁写）。失败返回 None，由调用方降级。"""
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=BASE, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _remote_ref():
    """远端权威 ref。FETCH_HEAD = 最近一次 fetch 的 tip（最新）；origin/main 兜底。

    ⚠️ 2026-09-15 铁律：本机（阿狸咪）从不 pull，docs/ops/handover/ 工作树会陈旧
    （实测 09-15：本机 1 份 vs 远端 10 份）⇒ 只读工作树 = 漏读新交接 + 把「真有指令」
    误报成「无指令」。与 auto_handoff_read.py 同口径：一律远端优先。
    """
    for ref in ("FETCH_HEAD", "origin/main"):
        if _git(["rev-parse", "--verify", ref], timeout=15):
            return ref
    return None


def _hours_from_name(name):
    """从交接文件名内嵌时间推小时数（不依赖 mtime：坚果云会重写 mtime）。

    2026-09-16 治本（P2，小九 `1520` §3.4 点名我方认领；采纳其**乙案**）：
    原实现用 ``re.match``（**行首锚定**），只认「文件名**以** ``YYYY-MM-DD_HHMM``
    开头」⇒ ``HANDOVER_<…>_YYYY-MM-DD_HHMM_`` 家族（前缀 ``HANDOVER_``）**恒返回
    None** ⇒ 被 ``(_hours_from_name(nm) or 1e9) <= 120`` 判为「不在窗口」而**整族
    排除在 API 精算之外**，继续携带 graft 假值、靠文件名兜底排序。因今日文件名
    时间恰好真实而「看起来对」⇒ 静默假治本（判据 62）。

    现改为**委托唯一真源** ``_name_sort_key()``（``re.search``，不锚定）⇒ 排序
    与「是否进精算窗口」**同一个口径**，消除同名两答案（判据 65）。
    """
    dt = _name_sort_key(name)
    if dt == datetime.min:          # 无任何时间戳 ⇒ 与排序同口径，视为不可知
        return None
    dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return (datetime.now(timezone(timedelta(hours=8))) - dt).total_seconds() / 3600.0


def _name_sort_key(name):
    """交接档排序键 = 文件名内嵌的日期时间（供升序排序）。

    2026-09-16 新增：覆盖面放宽到全部交接档后，**单纯按文件名字符串倒序会出错** ——
    遗留命名 ``URGENT_20260914_…`` / ``HANDOVER_…`` / ``AUDIT_…`` 的首字符
    'U'/'H'/'A' ASCII 码大于 ``2026-…`` 的 '2' ⇒ 这些**旧档会被排到最前**，
    把真正最新的交接挤出视野（实测：放宽首跑把 09-14 的 URGENT 排到了 09-16 前面）。
    改按内嵌时间排序；两种口径都认：
      · ``YYYY-MM-DD[_ ]HHMM``（现行命名，也认只有日期的 ``YYYY-MM-DD_``）
      · ``YYYYMMDD_HHMM``（遗留命名）
    无任何时间戳者归 ``datetime.min`` ⇒ 排最后，不污染头部。
    """
    for pat in (r"(\d{4})-(\d{2})-(\d{2})[_\s]?(\d{2})?(\d{2})?",
                r"(\d{4})(\d{2})(\d{2})[_\s](\d{2})(\d{2})"):
        m = re.search(pat, name)
        if not m:
            continue
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4) or 0), int(m.group(5) or 0))
        except ValueError:
            continue
    return datetime.min


def _scan_handover_files_remote(ref):
    """远端 tip 下的【全部】交接档清单（.md）。返回 [文件名] 或 None（不可用）。

    2026-09-16 放宽（P1 治本）：原先只认 ``*_URGENT_*.md`` ⇒ 小九的普通交接档
    （``…_回执_…`` / ``HANDOVER_…`` / ``…_交接_…``）被整批漏读。实测 09-15 23:05
    之后到 09-16 08:42 新增 13 份档（含小九 2150 档的 2139 全站 404 P0、
    09-16 0830 主题空间卡二次覆盖 P0）**全部未进监听视野**。
    ⇒ URGENT 从「过滤器」降为「标注」，覆盖面 = 全部交接档。
    自动 dispatch 的安全性不靠文件名，由 ``parse_dispatch_commands`` 的
    显式标记（``[ACTION]`` / ``!dispatch`` / ``# action:``）兜底 ⇒ 放宽不增风险。
    """
    out = _git(["ls-tree", "-r", "--name-only", ref, "--", HANDOVER_REL + "/"])
    if out is None:
        return None
    names = []
    for line in out.splitlines():
        rel = line.strip()
        if not rel or not rel.startswith(HANDOVER_REL + "/"):
            continue
        base = rel[len(HANDOVER_REL) + 1:]
        if not base.endswith(".md"):
            continue
        if base.startswith(("README", "_")):
            continue
        names.append(base)
    return names


def _commit_times_remote(ref, limit=60):
    """远端 ref 下交接档的「最后一次提交时间」映射 ``{文件名: epoch 秒}``。

    2026-09-16 排序治本（第二步，P1）：``_name_sort_key`` 只看**文件名内嵌时间**，
    而文件名时间**可能超前真实时刻** ⇒ 超前命名档会长期顶在「最新」位。实测：
    小九 ``2026-09-16_1730_…`` / ``_1715_…`` 两档实际是 **09:56 由 cloud-bot 提交**
    （``caea15b02``，正文自称「本机时钟 17:10」），按名排序会一直压到当天 17:30 之后；
    而 ``main()`` 只对 ``files[0]`` 判 action 标记 ⇒ **这 6~7 小时内任何真实的新
    ``# action:`` 指令都会被遮蔽、静默漏派**。
    ⇒ 排序改为「**提交时间优先 + 文件名时间兜底**」（``recent_urgent_files``）。

    取不到时间（浅克隆/网络失败）⇒ 返回空 dict，排序自动退回纯文件名口径，不报错。
    """
    out = _git(["log", "--name-only", "--format=@%ct", "-n", str(limit),
                ref, "--", HANDOVER_REL + "/"], timeout=40)
    if out is None:
        return {}
    ct, res = None, {}
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("@"):
            try:
                ct = int(s[1:])
            except ValueError:
                ct = None
            continue
        if ct and s.startswith(HANDOVER_REL + "/"):
            base = s[len(HANDOVER_REL) + 1:]
            # log 为倒序 ⇒ 同名首次出现即「最后一次提交」
            if base.endswith(".md") and base not in res:
                res[base] = ct
    return res


def _is_degenerate_times(cts):
    """判 ``_commit_times_remote`` 的结果是否被 **graft 边界** 污染（浅克隆）。

    2026-09-16 P-A 治本（小九 `1320` 回执 §2 认领项）：
    浅克隆里 graft 边界 commit 在 ``git log --name-only`` 下**被当成 root**（父缺失）
    ⇒ 它的 ``%ct`` 被安给该 commit 树的**全部**档，于是「取到了同一个错值」而不是
    「取不到」——原实现的容错（取不到才退 ``{}``）**根本不会触发**，
    「提交时间优先」静默退化成纯文件名口径，且**不报错**（与判据 59/94 同源）。
    实测：阿狸咪机 325 档 / 3 个唯一值（323 档同值）；小九机 324 档 / 1 个唯一值。
    """
    if len(cts) < GRAFT_MIN_ENTRIES:
        return False
    return len(set(cts.values())) < max(2, int(len(cts) * GRAFT_UNIQUE_RATIO))


def _api_commit_ts(names):
    """走 GitHub Commits API 取交接档**权威**提交时间 ``{档名: epoch 秒}``。

    ``GET /repos/{repo}/commits?path=<rel>&per_page=1`` ⇒ ``[0].commit.committer.date``。
    绕开浅克隆（不依赖本地历史深度）。**只对有界的一小撮档调用**（调用方已按
    文件名时间收紧到近 ``API_TS_WINDOW_H`` 小时、上限 ``API_TS_MAX``），防请求风暴。
    任一步失败 ⇒ 该档跳过；全失败 ⇒ 返回 ``{}``（不报错，调用方退回文件名口径）。
    """
    token = _load_token()
    if not token or not names:
        return {}
    out = {}
    for nm in names:
        path = urllib.parse.quote(f"{HANDOVER_REL}/{nm}")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/commits?path={path}&per_page=1",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                arr = json.loads(r.read().decode("utf-8", "replace"))
            iso = arr[0]["commit"]["committer"]["date"]
            out[nm] = int(datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
                          .replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            continue
    return out


def _fetch_remote():
    """尽力刷新 FETCH_HEAD / origin/main（只动 .git 引用，不碰工作树）。失败不报错。"""
    if "--no-fetch" in sys.argv:
        return False
    return _git(["fetch", "origin", "main", "-q"], timeout=25) is not None


def recent_urgent_files(n=5):
    """按【提交时间优先 + 文件名内嵌时间兜底】倒序取最近 N 份交接档。

    覆盖面 = **全部**交接档（2026-09-16 放宽；原只认 *_URGENT_*.md，见
    _scan_handover_files_remote 注释）。URGENT 只在输出里加 🔴 标注，不作过滤。
    排序口径见 `_commit_times_remote`（2026-09-16 治本：防超前命名档遮蔽真最新档）。

    远端优先；git 不可用时降级读本机工作树（并在输出里显式标注，不掩盖降级）。
    """
    _fetch_remote()
    ref = _remote_ref()
    if ref:
        names = _scan_handover_files_remote(ref)
        if names:
            cts = _commit_times_remote(ref)
            SORT_DIAG.update({"mode": "提交时间优先", "api_n": 0, "degenerate": False,
                              "entries": len(cts), "unique": len(set(cts.values()))})
            if _is_degenerate_times(cts):
                # 甲：判定退化（不假装治本）；乙：对有界近档走 API 取真值
                SORT_DIAG["degenerate"] = True
                cands = [nm for nm in names
                         if (_hours_from_name(nm) or 1e9) <= API_TS_WINDOW_H]
                cands.sort(key=_name_sort_key, reverse=True)
                api = _api_commit_ts(cands[:API_TS_MAX])
                if api:
                    cts.update(api)
                    SORT_DIAG.update({"mode": "提交时间优先（API 精算）",
                                      "api_n": len(api), "degenerate": False})
                else:
                    SORT_DIAG["mode"] = "⚠️ 文件名口径（提交时间不可信）"
            names.sort(key=lambda nm: (cts.get(nm, 0), _name_sort_key(nm)),
                       reverse=True)
            return [{"name": nm, "repo_path": f"{HANDOVER_REL}/{nm}",
                     "src": "remote", "ref": ref, "local": HANDOVER_DIR / nm}
                    for nm in names[:n]]
    # 降级：本机工作树
    d = HANDOVER_DIR
    if not d.is_dir():
        return []
    local = sorted((p for p in d.glob("*.md")
                    if not p.name.startswith(("README", "_"))),
                   key=lambda p: _name_sort_key(p.name), reverse=True)
    return [{"name": p.name, "repo_path": None, "src": "local",
             "ref": None, "local": p} for p in local[:n]]


def read_text(item):
    """读整份文件：远端优先（git show <ref>:<path>），失败降级本机工作树。

    2026-09-16 新增：显式指令可能出现在档末（如「## 8. 明确不做」之后的派发行），
    只看前 40 行会漏 ⇒ 派发判定改用全文。
    """
    if item.get("src") == "remote":
        txt = _git(["show", f"{item['ref']}:{item['repo_path']}"], timeout=40)
        if txt is not None:
            return txt
    try:
        return item["local"].read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[读取失败: {e}]"


def read_head(item, lines=50):
    """读文件前 N 行：远端优先，失败降级本机工作树（供输出摘要用）。"""
    return "".join(read_text(item).splitlines(keepends=True)[:lines])


def item_age_hours(item):
    """优先用文件名时间戳；无前缀（旧命名）才回退 mtime。"""
    h = _hours_from_name(item["name"])
    if h is not None:
        return h
    try:
        return (datetime.now().timestamp() - os.path.getmtime(item["local"])) / 3600.0
    except Exception:
        return float("nan")



def run_freshness_check():
    try:
        r = subprocess.run(
            [sys.executable, "guard_v8_freshness.py"],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, f"guard_v8_freshness.py 调用失败: {e}"


def parse_dispatch_commands(text, mtime_hours=24):
    """从 urgent 文本中识别 dispatch 指令。返回 [(reason, wf_name, payload)]

    仅当文本含显式 `[ACTION]` / `!dispatch` / `# action:` 标记时才自动触发；
    普通交接/巡检文档中的历史关键词不触发，避免误 dispatch。
    """
    cmds = []
    lower = text.lower()

    # 显式指令标记
    if not re.search(r"\[ACTION\]|!dispatch|# action:|## action", lower):
        return cmds

    # 直接显式 workflow 名
    for key, (wf, payload) in WF_MAP.items():
        if re.search(rf"\bdispatch\s+{key.replace('_', '[_-]?')}\b", lower):
            cmds.append((f"显式 ACTION 指令 dispatch {key}", wf, payload))

    # 无显式 workflow 名时，按关键词推断
    if re.search(r"\b(马上刷新|立即刷新|重新抓取|数据缺失|数据没更新|cn fetch|云端抓取)\b", lower):
        if not any(c[1] == "v8_cn_fetch_cloud.yml" for c in cmds):
            cmds.append(("ACTION：刷新/数据缺失", "v8_cn_fetch_cloud.yml", {"ref": "main"}))
    if re.search(r"\b(跑算法|算法链|盘后算法|algo|v8_algo_run)\b", lower):
        if not any(c[1] == "v8_algo_cloud.yml" for c in cmds):
            cmds.append(("ACTION：算法链", "v8_algo_cloud.yml", {"ref": "main"}))
    if re.search(r"\b(重新部署|部署网站|deploy|build and deploy)\b", lower):
        if not any(c[1] == "v8_build_deploy.yml" for c in cmds):
            cmds.append(("ACTION：部署", "v8_build_deploy.yml", {"ref": "main"}))
    return cmds


def _strip_code(text):
    """去掉围栏代码块与行内 ``code`` 片段（**含双反引号**）。

    交接档经常**引用**指令标记来讨论它（实测小九 `1320` 回执、以及本机 `1322` 档
    都原样写了标记做示例）⇒ 不剥引用就会**误派**。
    🔴 2026-09-16 实测补刀：只按**单**反引号配对会漏 —— 写 ``` `` `示例` `` ``` 这种
    「双反引号包行内反引号」的写法，配对会错位，示例标记**活下来**并真的触发了派发。
    ⇒ 必须先剥双反引号对，再剥单反引号对。
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    text = re.sub(r"``.+?``", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


# 🔴 指令行的**严格语法**（多档扫描的误派防火墙）：
#   整行 = [行首装饰] + [标记] + dispatch + <workflow 名> + [收尾标点]，**其余一律不算**。
#   · 行首装饰：`>`/`-`/`*`/`•` 与 `#`(≤3 个)
#   · 标记：`[ACTION]` / `ACTION:`（大小写不敏感）/ `!dispatch`
#   · workflow 名必须**显式**给出且在 WF_MAP 中；**不做关键词推断**
# 为什么要「整行唯一」：草案版只要求「行内含标记 + 行内含 dispatch <wf>」⇒
#   实测**本机自写的测试档**（正文里举例 `- [ACTION] dispatch algo_cloud`）把自己
#   判成了指令，误派 2 次（cn_fetch_cloud + algo_cloud）。收紧到「整行唯一位」后
#   任何「引用/举例/表格行」都不再命中。
_DIRECTIVE_RE = re.compile(
    r"^\s*[>\-*•]*\s*#{0,3}\s*"
    r"(?:(?:\[ACTION\]|ACTION:)\s*dispatch|!dispatch)\s+"
    r"([A-Za-z_][A-Za-z_0-9]*)\s*[.。！!]*\s*$", re.I)


def explicit_directives(text):
    """**收紧版**指令识别：只认「独立成行、语法唯一」的显式指令 + 档内显式 workflow 名。

    2026-09-16 P-A 治本（第三步）：原实现只对 ``files[0]`` 判 action 标记 ⇒ 一旦
    排序把旧档（含超前命名档）顶到首位，真实新指令就被静默漏派。放宽扫描面必须同时
    把误派风险压到最低 ⇒ 对 ``files[1:]`` 只接受 ``_DIRECTIVE_RE`` 那种**整行唯一**
    的写法（见其上方注释；一经实测收紧：自测档误派 2 次 → 0 次）。
    """
    cmds = []
    for line in _strip_code(text).splitlines():
        m = _DIRECTIVE_RE.match(line)
        if not m:
            continue
        key = m.group(1).lower()
        if key in WF_MAP:
            wf, payload = WF_MAP[key]
            cmds.append((f"显式指令行 dispatch {key}", wf, payload))
    return cmds


def _load_action_state():
    """派发去重状态 ``{档名: 内容 sha1 前 16 位}``（缺失/损坏 ⇒ {}）。"""
    try:
        d = json.loads(ACTION_STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_action_state(state):
    """只留最近 300 条（dict 保序），防状态文件无限增长。失败不阻断。"""
    try:
        ACTION_STATE.parent.mkdir(parents=True, exist_ok=True)
        if len(state) > 300:
            for k in list(state)[:len(state) - 300]:
                state.pop(k, None)
        ACTION_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    except Exception:
        pass


def scan_dispatch(files, dry=False):
    """扫描前 ``ACTION_SCAN_N`` 档的显式指令并派发。返回 (输出行列表, 实际派发数)。

    去重口径（2026-09-16 补齐原待办）：``文件名 + 内容 sha1`` —— **不用时效门**
    （24h 门会漏掉跨巡检窗口的真指令），同一档内容不变则只处置一次；
    派发失败**不登记** ⇒ 下一轮自动重试。
    ``files[0]`` 维持原口径（显式标记 + 关键词推断）；``files[1:]`` 走收紧口径
    （``explicit_directives``：显式行 + 显式 workflow 名）。
    """
    lines = []
    state = {} if dry else _load_action_state()
    todo = []          # [(档名, content_hash, [(reason, wf, payload)])]
    for i, item in enumerate(files[:ACTION_SCAN_N]):
        text = read_text(item)
        h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:16]
        if state.get(item["name"]) == h:
            continue
        cmds = (parse_dispatch_commands(text, item_age_hours(item)) if i == 0
                else explicit_directives(text))
        todo.append((item["name"], h, cmds))
    n = 0
    for name, h, cmds in todo:
        if not cmds:
            state[name] = h          # 无指令 ⇒ 登记（内容变了才会重扫）
            continue
        ok_all = True
        for reason, wf, payload in cmds:
            if dry:
                lines.append(f"- [DRY-RUN] {name}：{reason} → 将 dispatch `{wf}`")
                continue
            ok, msg = dispatch_workflow(wf, payload)
            ok_all = ok_all and ok
            lines.append(f"- {'✅' if ok else '❌'} {name}：{reason} → `{wf}`：{msg}")
            if ok:
                n += 1
        if ok_all:
            state[name] = h          # 失败 ⇒ 不登记，下一轮重试
    if not dry:
        _save_action_state(state)
    return lines, n


def dispatch_workflow(wf_name, payload):
    token = _load_token()
    if not token:
        return False, "未找到 GitHub token"
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_name}/dispatches"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, str(e)[:150]


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    out = [f"# v8 紧急指令监听 ({now})", ""]

    files = recent_urgent_files(ACTION_SCAN_N)
    src = files[0]["src"] if files else "-"
    src_txt = {"remote": f"远端优先（{files[0]['ref']}）", "local": "⚠️ 降级：本机工作树（可能陈旧）",
               "-": "-"}[src]
    urgent_n = sum(1 for f in files if "_URGENT_" in f["name"])
    out.append(f"## 最近交接档（{len(files)} 个，其中 URGENT {urgent_n} 个）｜来源：{src_txt}")
    out.append(f"- 排序口径：{SORT_DIAG['mode']}（提交时间条目 {SORT_DIAG['entries']} / "
               f"唯一值 {SORT_DIAG['unique']}"
               + (f" / API 精算 {SORT_DIAG['api_n']} 档" if SORT_DIAG["api_n"] else "")
               + ("；⚠️ 检出 graft 退化，已按兜底口径排序" if SORT_DIAG["degenerate"] else "") + "）")
    if not files:
        out.append("- 无")
    for i, item in enumerate(files):
        if i >= DISPLAY_N:            # 仅展开前 N 档；其余仍在派发扫描面内
            out.append(f"- … 另有 {len(files) - DISPLAY_N} 档在派发扫描面内（未展开）："
                       + "、".join(f["name"] for f in files[DISPLAY_N:]))
            break
        head = read_head(item, 40)
        age_h = item_age_hours(item)
        stamp = f"{age_h:.1f}h" if age_h == age_h else "n/a"
        flag = "🔴 URGENT " if "_URGENT_" in item["name"] else "📄 "
        out.append(f"- {flag}**{item['name']}** (距文件名时间={stamp}，仅参考；位次={i + 1})")
        out.append("```markdown")
        out.append(head)
        out.append("```")

    # 健康检查
    out.append("")
    out.append("## v8 数据新鲜度")
    rc, stdout = run_freshness_check()
    out.append(f"- 检查返回码: {rc}")
    out.append("```")
    out.append(stdout[:1500])
    out.append("```")

    # 自动 dispatch（2026-09-16：扫描面前 8 档，带 文件名+内容 hash 去重）
    out.append("")
    out.append("## 自动 dispatch")
    out.append(f"- 扫描面：前 {ACTION_SCAN_N} 档（第 1 档=显式标记+关键词推断；"
               f"其余=显式指令行+显式 workflow 名）｜去重=文件名+内容 hash")
    dlines, n_dispatched = scan_dispatch(files, dry=dry)
    if not dlines and not n_dispatched:
        out.append("- 无新增派发指令（前 8 档已判过或均无显式指令）。")
    else:
        out.extend(dlines)
        out.append(f"- 本轮实际派发 **{n_dispatched}** 次。")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
