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
  6. HTML 数据引用     —— 4 页 <script src> 本地引用真实存在（防 404 断链复发）
  7. gate 头注一致     —— v8_stage_gate.py 头注与 READY_SPEC 真源一致（项数/门槛/P0 专项）
  8. 心跳产物名一致    —— HB_*.js 字面量大小写与 update_v8 权威名对齐
                          （2026-09-14 新增：小写 `hb_xiaojiu.js` 在 Windows 侥幸能过，
                           换 Linux/mac 必 silent 判掉线）

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
                    ↳ 🔵 2026-09-14 已闭环（实测：index.html 已是正确大写
                      `data/HB_XIAOJIU.js`；全站 4 页**无任何小写 script 引用**）。
                      ⇒ **不再是 404**；上方列举仅作历史记录。
                      ⚠️ 另注：小写字面量当时还残留在 `v8_peer_monitor.py:HB_FILE`
                        与 `update_v8.py:112` 的注释里（已随 2026-09-14 午休一轮修掉），
                        并新增第 8 项门禁「心跳产物名一致」防漂移复发。
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

def check_heartbeat_name_consistency():
    """心跳产物名一致性门禁（2026-09-14 新增·第 2 条配套）。

    🔴 背景（2026-09-14 P1 血泪）：
      `v8_peer_monitor.py` 的 `HB_FILE` 写成小写 `data/hb_xiaojiu.js`，而实产是
      大写 `data/HB_XIAOJIU.js`（update_v8 映射产物）。
      Windows/NTFS 大小写不敏感 ⇒ 本机侥幸能打开；**换 Linux/mac 必 exists()==False
      ⇒ 沉默判 9999 分钟掉线**。这类跨平台雷 py_compile 查不出、HTML 引用查不出，
      只有本项能拦。

    做法：
      1) 以「真产/映射」为准取权威名 —— 从 `update_v8.py` 的 DATA_SOURCES 里读出
         `<raw>.json -> <VAR>` 中所有以 `HB_` 开头的**值**（大写真源）；
      2) 全仓扫 `.py`/`.html`/`.js`/`.yml` 里出现的 `hb_<something>.js` /
         `HB_<something>.js` 字面量，**但先剔除注释与文档字符串**：
         · `.py`：用 `tokenize` 剥掉 COMMENT，并剥掉「独占整行起头的三引号 docstring」；
           **保留普通字符串字面量**（`"data/hb_xiaojiu.js"` 正是本项要抓的目标）；
         · `.html`/`.js`：剥掉 `<!-- -->`、`//`、`/* */`；
         · `.yml`：剥掉 `#` 注释。
         理由：本项只应抓「真被当作产物路径用的字面量」，注释/说明里提历史旧名
         是**合法**的（本文件自身头注就举了历史反向例子）—— 否则门禁必误报，
         反过来逼人删注释，属本末倒置。
      3) 凡剩下的字面量**大小写**与权威名不一致 → 报。
         （`raw_data/hb_*.json` 小写是**契约**，本项只比对 `.js`。）

    ⚠️ 已知边界：本项是「字面量大小写」检查，不是「运行时存在性」检查。
       运行时路径由 `check_html_refs`（第 6 项）负责，二者互补不重叠。

    纯标准库实现（守本文件「零依赖可用」铁律）。
    """
    # 1) 权威大写名：从 update_v8.py 的 DATA_SOURCES 抽 HB_* 值
    auth_names = set()
    upd = ROOT / "update_v8.py"
    if upd.exists():
        try:
            txt = upd.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"([A-Za-z0-9_]+\.json)"\s*:\s*"(HB_[A-Z0-9_]+)"', txt):
                auth_names.add(m.group(2))
        except Exception:
            pass
    # 兜底：即使解析失败，也认这两个契约名（防止门禁因真源改写而失明）
    auth_names |= {"HB_XIAOJIU", "HB_ALIMI"}

    skip_dirs = {"__pycache__", ".git", "node_modules", ".workbuddy", "_archive", "backup"}
    exts = {".py", ".html", ".htm", ".js", ".yml", ".yaml"}
    pat = re.compile(r"\b([Hh][Bb]_[A-Za-z0-9_]+)\.js\b")

    def _strip_py(text):
        """剥掉 Python 注释与**独占行的三引号 docstring**，保留普通字符串字面量。"""
        import io, tokenize
        _SQ3 = chr(39) * 3
        _DQ3 = chr(34) * 3
        lines = text.splitlines(keepends=True)
        drop = set()
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except Exception:
            toks = []
        if not toks:
            return "\n".join(re.sub(r"#.*$", "", ln) for ln in lines)
        for tok in toks:
            ttype, tstr, (srow, _c), (erow, _e), _l = tok
            if ttype == tokenize.COMMENT:
                drop.add(srow)
            elif ttype == tokenize.STRING and tstr[:3] in (_SQ3, _DQ3):
                head = lines[srow - 1] if srow - 1 < len(lines) else ""
                if head.lstrip()[:3] in (_SQ3, _DQ3):
                    for r in range(srow, erow + 1):
                        drop.add(r)
        return "".join("" if i in drop else ln for i, ln in enumerate(lines, start=1))

    def _strip_js(text):
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        out = []
        for ln in text.splitlines():
            if "//" in ln:
                q = 0; cut = None; i = 0
                while i < len(ln) - 1:
                    c = ln[i]
                    if c in "\"'`":
                        q = 0 if q else 1
                    elif c == "/" and ln[i + 1] == "/" and not q:
                        cut = i; break
                    i += 1
                if cut is not None:
                    ln = ln[:cut]
            out.append(ln)
        return "\n".join(out)

    def _strip_yml(text):
        return "\n".join(re.sub(r"(?<!\S)#.*$", "", ln) for ln in text.splitlines())

    strip = {".py": _strip_py, ".html": _strip_js, ".htm": _strip_js,
             ".js": _strip_js, ".yml": _strip_yml, ".yaml": _strip_yml}

    offenders = []
    for sub in [".", ".github/scripts", "scripts", "v8", "algorithms", "docs"]:
        d = (ROOT / sub) if sub != "." else ROOT
        if not d.exists():
            continue
        for fp in d.rglob("*"):
            if not fp.is_file() or fp.suffix.lower() not in exts:
                continue
            if any(part in skip_dirs for part in fp.parts):
                continue
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            try:
                scanned = strip.get(fp.suffix.lower(), lambda x: x)(raw)
            except Exception:
                scanned = raw
            for m in pat.finditer(scanned):
                lit = m.group(1)
                if lit in auth_names:
                    continue
                if lit.upper() in auth_names:
                    rel = fp.relative_to(ROOT).as_posix()
                    offenders.append("%s : %s.js（应大写 %s.js）" % (rel, lit, lit.upper()))
    if offenders:
        uniq = sorted(set(offenders))
        return (False, "心跳产物名大小写漂移 %d 处（跨平台会 silent 判掉线）:\n    " % len(uniq)
                + "\n    ".join(uniq[:6]))
    return (True, "心跳产物名大小写一致（权威 %s，全仓 0 处漂移）" % "/".join(sorted(auth_names)))


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
        ("[1/8] py_compile", check_py_compile),
        ("[2/8] new Function", check_new_function),
        ("[3/8] data 完整性", check_data_integrity),
        ("[4/8] align_logic_ops", check_align_logic_ops),
        ("[5/8] workflow YAML", check_workflow_yaml),
        ("[6/8] HTML 数据引用", check_html_refs),
        ("[7/8] gate 头注一致", check_gate_headnote),
        ("[8/8] 心跳产物名一致", check_heartbeat_name_consistency),
    ]
    print("=" * 60)
    print("v8 pre-deploy audit（CI 自动门禁，2026-09-05 启用；2026-09-11 扩至 5 项；2026-09-13 扩至 6 项；2026-09-14 扩至 8 项）")
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
    print("🎉 8 项全部通过 → deploy 可继续")
    sys.exit(0)


if __name__ == "__main__":
    main()
