#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_urgent_listener.py — 紧急指令监听 + 健康检查（v8 去 v6 化版）
=========================================================
监听 docs/ops/handover/ 下的交接档（唯一交接目录；🔴 2026-09-16 起**全部 .md**，
不再只认 *_URGENT_*.md —— 见下方 `_scan_handover_files_remote` 注释），读取最新内容并：
1. 运行 guard_v8_freshness.py 生成数据新鲜度报告；
2. 根据文件内容中的关键词自动 dispatch 对应 workflow；
3. 输出摘要供 automation 向主人汇报。

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
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
HANDOVER_DIR = BASE / "docs" / "ops" / "handover"   # 2026-09-10 起唯一交接目录
URGENT_DIR = BASE / "docs" / "ops" / "urgent"        # 已停用（历史目录，勿再写入）
REPO = "ah-quant999/quant-scanner-v8"
HANDOVER_REL = "docs/ops/handover"                   # 仓库内相对路径（远端读取用）

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
    """从交接文件名前缀 YYYY-MM-DD_HHmm 推小时数（不依赖 mtime：坚果云会重写 mtime）。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})", name)
    if not m:
        return None
    try:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                      int(m.group(4)), int(m.group(5)),
                      tzinfo=timezone(timedelta(hours=8)))
    except ValueError:
        return None
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


def read_head(item, lines=50):
    """读文件前 N 行：远端优先（git show <ref>:<path>），失败降级本机工作树。"""
    if item.get("src") == "remote":
        txt = _git(["show", f"{item['ref']}:{item['repo_path']}"], timeout=30)
        if txt is not None:
            return "".join(txt.splitlines(keepends=True)[:lines])
    try:
        with open(item["local"], encoding="utf-8") as f:
            return "".join(f.readlines()[:lines])
    except Exception as e:
        return f"[读取失败: {e}]"


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

    files = recent_urgent_files()
    src = files[0]["src"] if files else "-"
    src_txt = {"remote": f"远端优先（{files[0]['ref']}）", "local": "⚠️ 降级：本机工作树（可能陈旧）",
               "-": "-"}[src]
    urgent_n = sum(1 for f in files if "_URGENT_" in f["name"])
    out.append(f"## 最近交接档（{len(files)} 个，其中 URGENT {urgent_n} 个）｜来源：{src_txt}")
    if not files:
        out.append("- 无")
    dispatch_cmds = []
    for i, item in enumerate(files):
        head = read_head(item, 40)
        age_h = item_age_hours(item)
        stamp = f"{age_h:.1f}h" if age_h == age_h else "n/a"
        flag = "🔴 URGENT " if "_URGENT_" in item["name"] else "📄 "
        out.append(f"- {flag}**{item['name']}** (距文件名时间={stamp}，仅参考；排序=提交时间优先+文件名兜底)")
        out.append("```markdown")
        out.append(head)
        out.append("```")
        # 只有最近 1 个文件参与自动 dispatch（避免旧文件反复触发）
        if i == 0:
            dispatch_cmds = parse_dispatch_commands(head, age_h)

    # 健康检查
    out.append("")
    out.append("## v8 数据新鲜度")
    rc, stdout = run_freshness_check()
    out.append(f"- 检查返回码: {rc}")
    out.append("```")
    out.append(stdout[:1500])
    out.append("```")

    # 自动 dispatch
    out.append("")
    out.append("## 自动 dispatch")
    if not dispatch_cmds:
        out.append("- 最新交接档未识别到自动 dispatch 指令，无需操作。")
    else:
        for reason, wf, payload in dispatch_cmds:
            if dry:
                out.append(f"- [DRY-RUN] {reason} → 将 dispatch `{wf}` payload={payload}")
            else:
                ok, msg = dispatch_workflow(wf, payload)
                out.append(f"- {'✅' if ok else '❌'} {reason} → `{wf}`: {msg}")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
