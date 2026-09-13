#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 Pre-deploy audit（CI 自动门禁，2026-09-05 主人令一劳永逸落地）
================================================================
目的：每次云端 build/deploy 前自动跑 **5** 项校验，任何一项失败 → 阻断 deploy。
等同「改后三件套」固化为 CI step，不再依赖人工记忆流程。

五项校验：
  1. py_compile        —— 所有 *.py 文件 0 语法错误
  2. new Function      —— index.html 所有 inline <script> 0 语法错误（Node）
  3. 完整性核对        —— data/*.js 数量在合理范围（90~110，与 HEAD 对齐）
  4. align_logic_ops   —— 逻辑详解页与真 workflow 一致（EXIT 0）
  5. workflow YAML     —— .github/workflows/*.yml 对 GitHub 真正有效
                          （2026-09-11 新增：`3ce9dd972` 丢 run 块内一行缩进
                          致整份 workflow 无效 → schedule 不触发/dispatch 被拒）

退出码：
  0  全部通过
  1  任意一项失败（deploy 阻断）

铁律：纯标准库 + 仅调本地子进程，可被 GitHub Actions ubuntu-latest 干净跑通。
"""
import os, re, sys, subprocess, json, glob, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # .github/scripts/ → repo root
errors = []


def check_py_compile():
    """所有 .py 文件 py_compile，0 错才算过。"""
    py_files = []
    for sub in ["algorithms", "v8", "scripts", ".github/scripts", "" ]:
        if sub:
            d = ROOT / sub
            if d.exists():
                py_files += sorted(d.rglob("*.py"))
        else:
            py_files += sorted(ROOT.glob("*.py"))
    py_files = [p for p in py_files if "__pycache__" not in str(p)]
    if not py_files:
        return (True, "无 .py 文件")
    # 用本地 python；CI 环境用系统 python3
    py = sys.executable if sys.executable else "python3"
    failed = []
    for p in py_files:
        try:
            subprocess.run([py, "-m", "py_compile", str(p)],
                           check=True, capture_output=True, timeout=15)
        except subprocess.CalledProcessError as e:
            failed.append(f"{p.relative_to(ROOT)}: {e.stderr.decode('utf-8', 'replace')[:120]}")
        except subprocess.TimeoutExpired:
            failed.append(f"{p.relative_to(ROOT)}: 超时")
    if failed:
        return (False, f"{len(failed)}/{len(py_files)} 文件语法错:\n  - " + "\n  - ".join(failed[:5]))
    return (True, f"{len(py_files)} 个 .py 文件 0 错误")


def check_new_function():
    """抽 index.html 所有 inline <script> 跑 new Function，0 错才算过。"""
    idx = ROOT / "index.html"
    if not idx.exists():
        return (True, "index.html 不存在（跳过）")
    html = idx.read_text(encoding="utf-8")
    # 含 src= 的不抽（外链脚本）
    pattern = re.compile(r"<script(?!\s[^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", re.IGNORECASE)
    blocks = []
    for m in pattern.finditer(html):
        code = m.group(1)
        # 跳过极短空块或纯 CSS 注释
        if not code.strip() or len(code.strip()) < 30:
            continue
        # 只测有意义的代码（含 window/function/const/let/var/=>/return/document/import）
        if not re.search(r"\b(window|function|const|let|var|=>|return|document|import)\b", code):
            continue
        blocks.append(code)
    if not blocks:
        return (True, "无 inline script 块")
    # 写入临时 js 文件用 node 跑
    tmp = ROOT / ".github/scripts/_pre_deploy_audit_test.js"
    payload = "var __blocks = " + json.dumps(blocks) + ";\n"
    payload += "var __errs = 0;\n"
    payload += "for (var i = 0; i < __blocks.length; i++) {\n"
    payload += "  try { new Function(__blocks[i]); } catch(e) { __errs++; console.log('block#'+i+': '+e.message.slice(0,150)); }\n"
    payload += "}\n"
    payload += "console.log('blocks=' + __blocks.length + ' errors=' + __errs);\n"
    payload += "process.exit(__errs > 0 ? 1 : 0);\n"
    tmp.write_text(payload, encoding="utf-8")
    node = subprocess.run(["node", str(tmp)], capture_output=True, text=True, timeout=60)
    try:
        tmp.unlink()
    except Exception:
        pass
    if node.returncode != 0:
        out = (node.stdout + node.stderr).strip().split("\n")[:8]
        return (False, f"{len(blocks)} 块中部分语法错:\n  " + "\n  ".join(out))
    return (True, f"{len(blocks)} 个 inline script 块 0 错误")


def check_data_integrity():
    """data/*.js 数量在合理范围（90~110），防止 Nutstore 误删导致空白部署。"""
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return (False, "data/ 目录不存在")
    js = list(data_dir.glob("*.js"))
    n = len(js)
    if n < 90 or n > 110:
        return (False, f"data/*.js 数量={n} 超出合理范围 [90,110]")
    # 健康文件最小字节
    too_small = [p.name for p in js if p.stat().st_size < 100]
    if too_small:
        return (False, f"data/ 下过小文件 {len(too_small)} 个: {too_small[:5]}")
    return (True, f"data/*.js 数量={n}, 全部 > 100B")


def check_align_logic_ops():
    """跑 align_logic_ops.py，EXIT 0 算过。"""
    py = sys.executable if sys.executable else "python3"
    r = subprocess.run([py, "align_logic_ops.py"], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        out = (r.stdout + r.stderr).strip().split("\n")[-5:]
        return (False, f"align_logic_ops 失败:\n  " + "\n  ".join(out))
    return (True, "align_logic_ops EXIT 0（逻辑详解页与真 workflow 对齐）")


def check_workflow_yaml():
    """校验 .github/workflows/*.yml 对 GitHub **真正有效**。

    🔴 2026-09-11 P0 血泪（#1771 实证）：`3ce9dd972` 在 `run: |` 块里丢了一行的
    10 空格缩进 → YAML literal block scalar 在此终止 → 后文被当顶层键 → 整份
    workflow 对 GitHub **无效**：run name 退回文件路径 / jobs=0 / 瞬时 failure，
    进而 schedule 不触发、workflow_dispatch 被拒 = 「后面的出不来」。
    注：这类损坏 py_compile 查不出、HTML 校验查不出、data 完整性查不出，
    只有本项门禁能拦 —— 故 2026-09-11 新增。

    双层校验（守本文件「纯标准库」铁律）：
      层1 零依赖「顶层行合法性」扫描 —— 精准命中上述事故签名；
      层2 若环境有 PyYAML，再做全量 safe_load 复核（CI 一般预装）。
    """
    wf_dir = ROOT / ".github" / "workflows"
    if not wf_dir.exists():
        return (True, "无 workflows 目录（跳过）")
    files = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))
    if not files:
        return (True, "无 workflow 文件")

    # YAML 顶层合法形式：注释 / 文档分隔符 / %指令 / 键值 / 列表项
    top_key = re.compile(r"""^(?:[A-Za-z_][\w.\-]*|'[^']+'|"[^"]+")\s*:(?:\s|$)""")
    failed = []
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            failed.append("%s: 读取失败 %s" % (f.name, e))
            continue
        for i, raw in enumerate(lines, 1):
            s = raw.rstrip()
            if not s.strip() or s.lstrip().startswith("#"):
                continue
            if raw[0] in " \t":          # 有缩进 → 属于某个块/嵌套，跳过
                continue
            if s in ("---", "...") or s.startswith("- ") or s.startswith("%"):
                continue
            if top_key.match(s):
                continue
            failed.append(
                "%s:%d 顶层非法行（YAML 必崩，通常= run: | 块内丢了缩进）→ %r"
                % (f.name, i, s[:70]))
            break                      # 一个文件报一处即可

    # 层2：有 PyYAML 则全量复核（无则静默降级，不破坏「纯标准库可用」）
    try:
        import yaml as _yaml
    except Exception:
        _yaml = None
    if _yaml is not None:
        for f in files:
            try:
                _yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception as e:
                msg = str(e).replace("\n", " ")[:110]
                if not any(x.startswith(f.name + ":") for x in failed):
                    failed.append("%s: YAML 解析失败 → %s" % (f.name, msg))

    if failed:
        return (False, "%d/%d 个 workflow 对 GitHub 无效:\n  - %s"
                       % (len(failed), len(files), "\n  - ".join(failed[:4])))
    tag = "PyYAML 全量" if _yaml is not None else "零依赖扫描"
    return (True, "%d 个 workflow 全部有效（%s）" % (len(files), tag))


def check_html_refs():
    """HTML 的本地 <script src> 引用必须真实存在（防「删数据漏改引用」复发）。

    🔴 2026-09-13 P1 血泪（阿狸咪逐字节复核实证）：小九两次「前端零引用死数据」
    清理（9a27eca71 砍 6 项 / 2026-09-11 停用 algo_backtest_compare）**只扫了
    index.html、漏扫 logic.html** ⇒ 三个真 404 长期挂在线上：

        index.html : data/hb_xiaojiu.js（大小写错，实产 HB_XIAOJIU.js）
        logic.html : data/ETF_SUBSCRIPTION_EM.js
        logic.html : data/ALGO_BACKTEST_COMPARE.js
                    ↳ 🔵 2026-09-13 已闭环：该引用**已恢复且文件已重新产出**
                      （scripts/algo_backtest_compare.py 重新挂进 E 批，
                       位于聚合器 gen_backtest_all_algos.py 之前）。
                      ⇒ 它现在**不再是 404**；上方列举仅作历史记录。
                      ⚠️ 请勿再以本条为依据删除 logic.html 的该 script 标签：
                        该标签支撑「两套算法回测对比」卡（logic.html L6707）。

    这类断链 py_compile 查不出、new Function 查不出、data 完整性查不出
    （文件本来就不该存在）、YAML 更查不出 —— 只有本项能拦。
    故 2026-09-13 新增为第 6 项硬门禁。

    纯标准库实现（守本文件「零依赖可用」铁律）。
    """
    pages = ["index.html", "logic.html", "calendar.html", "v6_memo.html"]
    pat = re.compile(r"""<script[^>]*\bsrc=["']([^"']+)["']""", re.IGNORECASE)
    checked, missing = 0, []
    for page in pages:
        fp = ROOT / page
        if not fp.exists():
            continue
        try:
            html = fp.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            missing.append("%s: 读取失败 %s" % (page, e))
            continue
        for src in pat.findall(html):
            if src.startswith(("http://", "https://", "//", "data:")):
                continue
            local = src.split("?")[0].split("#")[0].strip()
            if not local or local.startswith("/"):
                continue          # 站外/绝对路径不判
            checked += 1
            if not (ROOT / local).exists():
                missing.append("%s -> %s" % (page, local))
    if missing:
        uniq = sorted(set(missing))
        return (False, "发现 %d 处 404 断链（引用文件不存在）:\n    " % len(uniq)
                + "\n    ".join(uniq[:8]))
    return (True, "%d 个本地 script 引用全部存在（4 页）" % checked)

def write_audit_log(results, exit_code):
    """落盘三件套审计轨迹到 raw_data/code_audit.log（append）。
    让「何时/谁跑过三件套」有据可查。*.log 已被 .gitignore 忽略 → 不入库、不污染工作树。
    日志失败绝不阻断 deploy（静默吞掉）。
    """
    try:
        log_path = ROOT / "raw_data" / "code_audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        env = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"
        try:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            sha = "unknown"
        if not sha:
            sha = "unknown"
        status = "PASS" if exit_code == 0 else "FAIL"
        head = f"[{ts}] env={env} commit={sha} result={status}"
        body = "\n".join(f"    {lb}: {'OK' if ok else 'FAIL'} - {msg}" for lb, ok, msg in results)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(head + "\n" + body + "\n\n")
    except Exception:
        pass



def check_gate_headnote():
    """[7/7] 闸门模块头注 vs READY_SPEC 真源一致性（2026-09-14 新增）。

    为什么需要：头注漂移不影响运行时裁决，但会污染下一轮审计的前提 ——
    小九 bd5349de1 §4.3 发现头注写「must 含 AVG_PRICE_DATA」而真源不含，
    这正是 P0（7 项不存在产物致 A 批永久锁死）的认知根因在头注上重演。

    只校验可机器精确判定的三项：项数、门槛(need)、AVG_PRICE_DATA 不得列在 must 侧。
    不做产物名名单比对 —— 头注用中文别名、真源用英文名，名单比对必误报（v1/v2 实测）。
    """
    import ast
    gate = ROOT / ".github" / "scripts" / "v8_stage_gate.py"
    if not gate.exists():
        return True, "闸门文件不存在（跳过）"
    try:
        src = gate.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except Exception as e:
        return False, "闸门解析失败: %s" % e

    spec = None
    for node in ast.walk(tree):
        tgts = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in tgts:
            if isinstance(t, ast.Name) and t.id == "READY_SPEC":
                try:
                    spec = ast.literal_eval(node.value)
                except Exception:
                    pass
    if not isinstance(spec, dict):
        return False, "未能从闸门抽出 READY_SPEC（真源缺失）"

    head = ast.get_docstring(tree) or ""
    if not head:
        return False, "闸门模块无 docstring（头注缺失）"

    fails = []
    for key, label in [("A", "A 采集批"), ("B", "B 选股批"), ("E", "E 回测批")]:
        st = spec.get(key) or {}
        items = st.get("items") or []
        need = st.get("need")
        must = st.get("must") or []

        head_line = ""
        for ln in head.splitlines():
            if ln.strip().startswith(label):
                head_line = ln
                break
        if not head_line:
            continue

        # (1) 项数
        m = re.search(r"(\d+)\s*项", head_line)
        if m and int(m.group(1)) != len(items):
            fails.append("%s 头注项数 %s != 真源 %d" % (label, m.group(1), len(items)))
        # (2) 门槛
        m = re.search(r"[≥>=]+\s*(\d+)\s*项", head_line)
        if m and need is not None and int(m.group(1)) != need:
            fails.append("%s 头注门槛 >=%s != 真源 need %s" % (label, m.group(1), need))
        # (3) P0 专项：AVG_PRICE_DATA 不得出现在 must 侧
        must_txt = " ".join(p.split("/")[-1].rsplit(".", 1)[0] for p in must)
        if "must" in head_line and "AVG_PRICE_DATA" in head_line:
            if "AVG_PRICE_DATA" not in must_txt:
                fails.append("%s 头注 must 侧提到 AVG_PRICE_DATA，真源 must 不含"
                             "（P0 方向性错误：放回 must 会致该批永久锁死）" % label)
    if fails:
        return False, "；".join(fails[:4])
    return True, "闸门头注与 READY_SPEC 真源一致（项数/门槛/P0 专项）"

def main():
    checks = [
        ("[1/6] py_compile", check_py_compile),
        ("[2/6] new Function", check_new_function),
        ("[3/6] data 完整性", check_data_integrity),
        ("[4/6] align_logic_ops", check_align_logic_ops),
        ("[5/6] workflow YAML", check_workflow_yaml),
        ("[6/6] HTML 数据引用", check_html_refs),
        ("[7/7] gate 头注一致", check_gate_headnote),
    ]
    print("=" * 60)
    print("v8 pre-deploy audit（CI 自动门禁，2026-09-05 启用；2026-09-11 扩至 5 项；2026-09-13 扩至 6 项；2026-09-14 扩至 7 项）")
    print("=" * 60)
    fails = 0
    results = []
    for label, fn in checks:
        ok, msg = fn()
        icon = "✅" if ok else "❌"
        print(f"  {icon} {label}: {msg}")
        results.append((label, ok, msg))
        if not ok:
            fails += 1
            errors.append(f"{label}: {msg}")
    print("=" * 60)
    write_audit_log(results, 0 if fails == 0 else 1)
    if fails:
        print(f"🚫 {fails} 项校验失败 → 阻断 deploy！")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("🎉 7 项全部通过 → deploy 可继续")
    sys.exit(0)


if __name__ == "__main__":
    main()
