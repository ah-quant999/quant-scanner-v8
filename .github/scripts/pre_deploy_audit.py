#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 Pre-deploy audit（CI 自动门禁，2026-09-05 主人令一劳永逸落地）
================================================================
目的：每次云端 build/deploy 前自动跑 **12** 项校验，任何一项失败 → 阻断 deploy。
等同「改后三件套」固化为 CI step，不再依赖人工记忆流程。

十二项校验：
  1. py_compile        —— 所有 *.py 文件 0 语法错误
  2. new Function      —— index.html 所有 inline <script> 0 语法错误（Node）
  3. 完整性核对        —— data/*.js 数量在下界 90 与**动态上界**之间
                             （上界 = max(130, 声明面+20)；声明面 = DATA_SOURCES 注册 VAR
                              ∪ 页面 <script src> 引用。2026-09-19 二次根治，见函数内注）
  4. align_logic_ops   —— 逻辑详解页与真 workflow 一致（EXIT 0）
  5. workflow YAML     —— .github/workflows/*.yml 对 GitHub 真正有效
                          （2026-09-11 新增：`3ce9dd972` 丢 run 块内一行缩进
                          致整份 workflow 无效 → schedule 不触发/dispatch 被拒）
  6. HTML 数据引用     —— 4 页 <script src> 本地引用真实存在（防 404 断链复发）
  7. gate 头注一致     —— v8_stage_gate.py 头注与 READY_SPEC 真源一致（项数/门槛/P0 专项）
  8. 心跳产物名一致    —— HB_*.js 字面量大小写与 update_v8 权威名对齐
                          （2026-09-14 新增：小写 `hb_xiaojiu.js` 在 Windows 侥幸能过，
                           换 Linux/mac 必 silent 判掉线）
  9. 回测口径守卫      —— raw_data/backtest_expectancy.json（融合器权重唯一真源）
                          必须符合 new 口径（next_open + 扣费 + IS/OOS + 超额下架）
                          （2026-09-20 新增：全仓 34 个校验脚本无一覆盖该产物 ⇒
                           产物被反向覆盖回旧口径时静默无人拦。
                           本项**分档**：脚本口径漂移=阻断；产物未重跑=告警放行，
                            防误杀 v8_build_deploy.yml 与 v8_cn_fetch_cloud.yml 两条链）
  10. index 核心标记守卫 —— index.html 关键锚点在位（防「落后基线旧树」静默覆盖）
                           （2026-09-20 阿狸咪新增）
  11. defer 数据缓存守卫 —— defer 加载的数据源不得进「结果缓存」
                           （2026-09-20 阿狸咪实证 + 小九固化为门禁：数据未就位即缓存
                            空值 ⇒ 此后永空且全程不报错，属静默失效。
                            详见 check_defer_cache_guard 内注）
  12. 调用点定义守卫    —— index.html 内联脚本中「调用点存在但全文无定义」的
                           `_xxx()` / `__xxx()` / `window.__xxx()` ⇒ 阻断。
                          （2026-09-21 小九新增：`0d3482be4` 删 `__renderFactorLab`
                           死代码时把紧邻的 `_renderPostReady` 一并删掉、调用点仍在 ⇒
                           ReferenceError 致策略回测区初始渲染全挂。
                           该形态**语法合法**，[2/8] 抓不到（已受控复现：11 项全绿放行）。
                           详见 check_callee_defined 内注）

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


# ── [3/8] 判据：下界固定，上界**动态** ─────────────────────────────────────────
# 🔴 2026-09-19 阿狸咪的工程师（第二跳：上界再也不能是固定数）
#   第一跳（同日更早）只把上界 110 → 130：治住了「当时真值恰好贴顶」，
#   但**余量仍随卡片增长单调消耗**（实测 09-14=105 → 09-19=111）⇒ 数周后必然再贴顶。
#   而贴顶的后果不是「报个警」，是**同时打挂两条链**
#   （v8_build_deploy.yml 与 v8_cn_fetch_cloud.yml 都调用本脚本）。
#   第二跳改为**动态上界**：面 = 「应产出」的两个可程序化真源之并集
#     · update_v8.py::DATA_SOURCES 的 VAR 名（每条注册 ⇒ 产出 data/<VAR>.js）
#     · 页面里真实存在的 <script src="data/<NAME>.js"> 引用（index.html + logic.html）
#   ⇒ 上界 = max(基线 130, 面 + 容差 20)。
#   新增卡片**必然**同时抬高面（要么注册 DATA_SOURCES，要么加 <script src>）
#   ⇒ 正常增长永不打挂本项；异常暴增（如某脚本把产物批量写进 data/）仍会被抓。
#
# 🔴 为什么**不**拿「当前实际个数」当上界依据：那是同义反复 —— 门槛恒等于被考核值，
#   等于取消本项门禁。面只取**声明面**（注册表 / 页面引用），与 disk 实际数无关。
# 🔴 取不到面（文件缺失/解析异常）⇒ 退回基线 130 并**打印原因**，禁静默降级。
# 🔴 下界 90 未动：它才是本项的真正防线（防坚果云同步层误删 ⇒ 空白部署）。
# ⚠️ 已知口径（**实测，非推测**，2026-09-19，防后人误推）：
#   本处正则**不剥注释** ⇒ 注册面实测 **79**（严格口径 `^\s*"..."` 为 77，多出的 2 条是
#   注释里的示例对）。对裁决**无影响**（保底 130 生效，79 与 77 都远低于 130-20）。
#   之所以不改成 ast/剥注释版：本项是门禁，多一层解析就多一个「解析炸掉 ⇒ 两条链全停」的面，
#   而这里的松动方向是**更宽容**（不会误杀）。若将来面逼近上界，再评估是否收紧。
DATA_JS_MIN = 90                 # 真防线（不动）
DATA_JS_BASELINE_MAX = 130       # 声明面取不到时的保底上界
DATA_JS_FACE_TOLERANCE = 20      # 声明面之外的合法产物容差（未登记的临时/在途新增）


def _data_js_face():
    """→ (面大小 int, 说明 str)。面 = DATA_SOURCES 注册 VAR ∪ 页面 <script src> 引用。

    两个来源各自失败都**不影响**另一个；两面都取不到才返回 (0, 原因)。
    纯标准库实现（守本文件「零依赖」铁律）。
    """
    face, notes = set(), []

    upd = ROOT / "update_v8.py"
    if upd.exists():
        try:
            txt = upd.read_text(encoding="utf-8", errors="replace")
            v = set(m.group(1) + ".js"
                    for m in re.finditer(r'"[^"]+\.json"\s*:\s*"([A-Za-z0-9_]+)"', txt))
            if v:
                face |= v
                notes.append("注册 %d" % len(v))
            else:
                notes.append("注册面解析为空")
        except Exception as e:
            notes.append("注册面读取失败(%s)" % type(e).__name__)
    else:
        notes.append("缺 update_v8.py")

    ref = set()
    for page in ("index.html", "logic.html"):
        fp = ROOT / page
        if not fp.exists():
            continue
        try:
            h = fp.read_text(encoding="utf-8", errors="replace")
            ref |= set(re.findall(r'src=["\'](?:\.\./)?data/([A-Za-z0-9_\-\.]+\.js)', h))
        except Exception:
            notes.append("%s 读取失败" % page)
    if ref:
        face |= ref
        notes.append("引用 %d" % len(ref))

    return len(face), "＋".join(notes) if notes else "空"


def check_data_integrity():
    """data/*.js 数量落在 [90, 动态上界]，且每个 ≥100 B，防止 Nutstore 误删导致空白部署。

    上界为**动态**（声明面 + 容差，见上方 2026-09-19 注）；glob 非递归 ⇒ data/archive/* 不参与。
    """
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return (False, "data/ 目录不存在")
    js = list(data_dir.glob("*.js"))
    n = len(js)
    face, why = _data_js_face()
    if face:
        cmax = max(DATA_JS_BASELINE_MAX, face + DATA_JS_FACE_TOLERANCE)
        bound = "%d（动态＝面 %d ＋ 容差 %d）" % (cmax, face, DATA_JS_FACE_TOLERANCE)
    else:
        cmax = DATA_JS_BASELINE_MAX
        bound = "%d（基线·声明面取不到：%s）" % (cmax, why)
    if n < DATA_JS_MIN or n > cmax:
        return (False, "data/*.js 数量=%d 超出合理范围 [%d, %s]（面来源：%s）"
                       % (n, DATA_JS_MIN, bound, why))
    # 健康文件最小字节
    too_small = [p.name for p in js if p.stat().st_size < 100]
    if too_small:
        return (False, f"data/ 下过小文件 {len(too_small)} 个: {too_small[:5]}")
    return (True, f"data/*.js 数量={n}（上界 {bound}）, 全部 > 100B")


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
                    ↳ 🔵 2026-09-13 曾闭环（恢复引用 + 脚本重新挂 E 批）；
                      🗑 **2026-09-20 全链正式退役**（阿狸咪的工程师 · 主人令收口）：
                        · 前端：其唯一消费卡「两套算法回测对比」属主人 **2026-09-02 明令删除**的模块，
                          该卡所在 pane（ulPaneStrong）**已不在 renderUnlisted 生成列表**内 ——
                          CDP 真浏览器实测（走真实 switchSec('ul') 路径）：panel.len=262174、
                          ulPaneObserve=true，但 **ul-pane 数 = 0 / ulPaneStrong 非元素**
                          ⇒ 该卡**全站零生效路径**，从未渲染 ✅（本次已连同死代码段一并摘除）。
                        · 生产：algorithms/run_algorithms.py 的 ORDER **与** STAGES["E"] 成对摘除；
                        · 上传：api_push_raw.py 的 data/ALGO_BACKTEST_COMPARE.js 登记摘除；
                        · 产物与脚本：data/ALGO_BACKTEST_COMPARE.js、scripts/algo_backtest_compare.py 退役删除。
                      ⇒ 该 script 引用已不存在，本页**不再是 404**；上方列举仅作历史记录。
                      🔴 **反向警告**：**不要**照 09-13 的旧注记把该 script 标签加回来 ——
                        加回即立刻制造一处真 404 并打挂本项门禁（产物已退役）。
                      ⚠️ 2026-09-20 另修：weekly cleanup 的 orphan 判定原先**只扫 index.html**
                        且正则不匹配小写名 ⇒ 只被 logic.html 引用的产物会被它删掉，
                        与本门禁形成「清理 vs 门禁」拉锯（实测打挂 6 次 build）。
                        现已把清理侧引用面扩至同 4 页并大小写归一，两者口径一致。

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


def check_backtest_caliber():
    """[9/9] 回测口径守卫（2026-09-20 小九新增·口径回退结构性封堵）。

    🔴 背景（2026-09-20 事故家族）：
      `raw_data/backtest_expectancy.json` 是**融合器权重的唯一真源**
      （`generate_top10.py` / `final_recommend.py` 都读它的 excess 值给分）。
      2026-09-20 实测发现该产物被 A 批 fetch 在 7 分钟内**反向覆盖**回旧口径
      （`generated` 倒退、`n_snapshots` 65→46、`entry_mode` 变 None）
      —— 而全仓 34 个校验/守卫脚本**无一覆盖该产物** ⇒ 口径回退静默无人拦。
      本项把「产物必须符合新口径」立成 CI 可断言校验，结构上封死复发。

    做法：**不复制守卫逻辑**，直接调仓根 `guard_backtest_caliber.py`（单一真源），
      用 `--json` 拿结构化结果，再按本项的过渡策略裁决。

    ⚠️ 过渡策略（**故意宽松，防误杀整条部署链**）：
      该守卫的产物是 **E 批盘后算法链**产出的；而在产物被 E 批重跑定稿之前，
      磁盘上仍是旧口径产物 ⇒ 若本项硬阻断，**每次 build 都会红**，
      而 build/deploy 被 `v8_build_deploy.yml` 与 `v8_cn_fetch_cloud.yml` 两处调用
      ⇒ 等于同时打挂两条链（这正是 pre_deploy_audit 自己头注里警告过的失败模式）。
      故本项分档：
        · 产物**合规**            → ✅ 通过，报各项计数
        · 产物**不合规**          → ⚠️ 告警通过（不阻断），打印前 6 条问题
        · **脚本**本身口径漂移    → ❌ 阻断（脚本是真源，漂移立即修，与产物新旧无关）
        · 守卫文件/产物**缺失**   → ⚠️ 告警通过（缺失由 E 批链自身负责产出，非本项职责）

    纯标准库 + 仅调本地子进程，守本文件「零依赖可用」铁律。
    """
    guard = ROOT / "guard_backtest_caliber.py"
    art = ROOT / "raw_data" / "backtest_expectancy.json"
    if not guard.exists():
        return (True, "⚠️ guard_backtest_caliber.py 不存在（跳过；产物未纳入口径守卫）")
    py = sys.executable if sys.executable else "python3"
    try:
        r = subprocess.run([py, str(guard), "--path", str(art), "--json"],
                           capture_output=True, timeout=60, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return (True, "⚠️ 口径守卫超时（已放行，不阻断两链）")
    except Exception as e:
        return (True, "⚠️ 口径守卫无法执行（%s，已放行）" % type(e).__name__)
    out = r.stdout.decode("utf-8", "replace")
    try:
        j = json.loads(out)
    except Exception:
        return (True, "⚠️ 口径守卫输出非 JSON（rc=%s，已放行）" % r.returncode)
    probs = j.get("problems") or []
    warns = j.get("warns") or []
    # ⚠️ 守卫的 info 是**字符串列表**（人类可读行），不是 dict —— 需自行抽字段
    info_lines = j.get("info") or []
    if isinstance(info_lines, dict):
        info_lines = ["%s = %s" % (k, v) for k, v in info_lines.items()]
    info = {}
    for ln in info_lines:
        if "=" not in ln:
            continue
        k, _, v = ln.partition("=")
        info[k.strip()] = v.strip()
    # 区分「脚本口径漂移（必阻断）」与「产物未重跑（放行）」两类问题
    script_drift = [p for p in probs if ("脚本" in p) or ("source" in p.lower())
                    or ("ENTRY_MODE" in p) or ("COST_ROUND_TRIP" in p)]
    if r.returncode == 2 or j.get("missing") or not art.exists():
        return (True, "⚠️ 产物缺失（%s）→ 已放行，等 E 批产出" % art.name)
    if script_drift:
        return (False, "脚本口径漂移 %d 处（真源必须先修）:\n    " % len(script_drift)
                + "\n    ".join(script_drift[:6]))
    if probs:
        return (True, "⚠️ 产物仍为旧口径 %d 项（等 E 批重跑定稿，不阻断）: "
                      "entry_mode=%s n=%s | 首条: %s"
                % (len(probs), info.get("entry_mode"), info.get("n_snapshots"), probs[0][:110]))
    tail = ("（%d 条提示）" % len(warns)) if warns else ""
    return (True, "产物口径合规：entry_mode=%s cost=%s n=%s 覆盖=%s %s"
            % (info.get("entry_mode"), info.get("cost"), info.get("n_snapshots"),
               info.get("coverage"), tail))


def write_audit_log(results, exit_code):
    """落盘三件套审计轨迹到 raw_data/code_audit.log（append）。
    让「何时/谁跑过三件套」有据可查。
    日志失败绝不阻断 deploy（静默吞掉）。

    2026-09-21 阿狸咪修正（原注释与实现漂移，判据「注释≠真值」）：
      · 原文写「*.log 已被 .gitignore 忽略 → 不入库」——**与事实不符**：
        .gitignore:14 的 `*.log` 只管**未跟踪**文件，而本文件早在规则生效前就已被跟踪
        ⇒ gitignore 对它无效，它一直被自动任务反复提交（如 481fc4dd1）。
      · **本轮已做**：写侧显式 `newline="\\n"`（防 Windows 文本模式写 CRLF，
        导致「blob=LF / 工作树=CRLF」每次 add 都整文件转换）。
      · **尚未做（可选 · 低优先级，勿误记为已完成）**：`git rm --cached` 解除跟踪，
        使其真正回归「不入库」的设计意图。未做原因：该路径匹配 `v8_build_deploy.yml`
        的 `on.push.paths: raw_data/**` ⇒ 推送会触发部署链；而收益仅「仓库少 ~3KB
        + 少一次自动提交噪音」，按「盘中不推」纪律不值得现在做。
      · **当前状态无害**：写侧已是 LF ⇒ 入库 blob 与工作树行尾一致、`git status` 不脏。
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
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
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

def check_defer_cache_guard():
    """[11/11] defer 数据 × 结果缓存 = 空结果永久固化（2026-09-20 阿狸咪实证·小九固化门禁）。

    背景（阿狸咪 `2026-09-20_2323` 交接件 §二，含**受控复现**）：
      `data/BACKTEST_COMPREHENSIVE.js` 等外链数据均为 **defer 加载**，而内联 <script>
      在解析期先执行 ⇒ 首屏渲染时 `window.X` 可能仍 undefined。
      此时若把「空结果」写进结果缓存（`window.__xxxCache = 空`），此后即便数据到位也
      **永远返回空** ⇒ 卡片永久显示「暂无历史回测信号」。
      受控复现（CDP `Network.setBlockedURLs` 屏蔽该脚本）：
        ① 屏蔽 → 缓存写入 total_signals=0 ⇒ 卡显示「暂无」
        ② 解除屏蔽 + 注入已就位数据 → **仍返回 0**（缓存被复用）⇒ 固化成立
        ③ 修复版（不写缓存）同场景 → 恢复 127/12 档 ✅
      已清理两处：`__tripleBacktestCache`（三重共识回测）、`__gaoshouSetCache`（高手共振）。
      同仓先例：`__strongTrackBacktest` 自 2026-09-16 起注释即明写「绝不能缓存」。

    为什么必须做成**门禁**（而非只修那两处）：
      这类缺陷**完全不报错** —— `new Function` 语法检查通过、页面无 console error、
      构建全绿，只是渲染结果恒空。属「静默失效」，只能靠结构不变式拦。

    判据（纯结构，不看注释、不看运行时）：
      ① 真源：index.html 中带 `defer` 的 `<script src="data/<NAME>.js">` ⇒ 延迟数据名集合 D
      ② 扫 index.html 取出所有「结果缓存变量」赋值 `window.__<xx>Cache = ...`
      ③ 对每个缓存变量所属的**函数体**（自上而下最近一个 `function`/`= function`），
         若函数体内出现 D 中任一数据名（形如 `window.<NAME>`）⇒ **FAIL**

    为什么这样判**不会误杀**：
      · 只认 `window.__*Cache` 这一命名族（真缓存）；不碰 `__lifeModalCache` 这类
        纯 DOM 片段缓存 —— 后者不读 defer 数据，故第 ③ 步自然不命中。
      · 若某函数**先判数据就位再缓存**（合法写法），其函数体内仍会出现数据名 ⇒ 会命中。
        这是**有意的摩擦力**：该函数应改为「数据未就位则 return，不写缓存」；
        与其赌它写对了，不如强制它走「每次实时取数」这条已被实证正确的路。
      · 数据名取自 **defer 清单真源**（index.html 自身），不硬编码名单。

    维护纪律：新增 defer 数据源无需改本项（自动纳入）；**新增结果缓存**才会触发本项。
      若有正当理由要缓存，请在缓存值里带上数据时间戳做失效判定，并在此处登记豁免。
    """
    idx = ROOT / "index.html"
    if not idx.exists():
        return True, "index.html 不存在（放行）"
    try:
        txt = idx.read_text(encoding="utf-8")
    except Exception as e:
        return False, "index.html 读取失败: %s" % e

    # ① defer 数据源真源
    defer_names = set()
    for m in re.finditer(r'<script\s+src="data/([A-Za-z0-9_]+)\.js(?:\?v=[^"]*)?"([^>]*)>', txt):
        if "defer" in (m.group(2) or "").lower():
            defer_names.add(m.group(1))
    if not defer_names:
        return True, "未探测到 defer 数据源（放行，避免守卫自身成为单点）"

    # ② 结果缓存变量
    caches = sorted(set(re.findall(r'window\.(__[A-Za-z0-9_]*Cache[A-Za-z0-9_]*)\s*=', txt)))
    if not caches:
        return True, "无结果缓存变量（defer 数据 %d 个，0 风险）" % len(defer_names)

    # ③ 定位每个缓存变量所属函数体
    lines = txt.splitlines()
    offenders = []
    for var in caches:
        # 找赋值行；若有多处，逐处查
        for i, ln in enumerate(lines):
            if not re.search(r'window\.' + re.escape(var) + r'\s*=', ln):
                continue
            # 向上找最近的函数起始（window.<fn> = function 或 function <fn>）
            fn_start, fn_name = None, "?"
            for j in range(i, max(-1, i - 400), -1):
                m2 = re.search(r'(?:window\.)?([A-Za-z0-9_$]+)\s*=\s*function\s*\(', lines[j])
                if m2:
                    fn_start, fn_name = j, m2.group(1)
                    break
                m3 = re.search(r'function\s+([A-Za-z0-9_$]+)\s*\(', lines[j])
                if m3:
                    fn_start, fn_name = j, m3.group(1)
                    break
            if fn_start is None:
                fn_start, fn_name = i, "(顶层)"
            # 函数体：向下到大括号配平（最多 400 行，防失控）
            depth, body_end = 0, min(len(lines), fn_start + 400)
            started = False
            for j in range(fn_start, min(len(lines), fn_start + 400)):
                depth += lines[j].count("{") - lines[j].count("}")
                if lines[j].count("{"):
                    started = True
                if started and depth <= 0:
                    body_end = j
                    break
            body = "\n".join(lines[fn_start:body_end + 1])
            hit = sorted(n for n in defer_names if ("window." + n) in body)
            if hit:
                offenders.append("%s() → 缓存 %s，却读 defer 数据 %s（第 %d 行）"
                                 % (fn_name, var, "/".join(hit[:3]), i + 1))
                break  # 同一变量报一次即可
    if offenders:
        return (False, "%d 处「defer 数据 × 结果缓存」空结果固化风险"
                       "（数据未就位即缓存空值 ⇒ 此后永空，且全程不报错）:\n    "
                % len(offenders) + "\n    ".join(offenders[:6]))
    return (True, "defer 数据 %d 个 × 结果缓存 %d 个：0 处空结果固化风险"
            % (len(defer_names), len(caches)))


def check_callee_defined():
    """[12/12] 调用点 × 定义缺失守卫（2026-09-21 小九新增·封堵「删函数连带删邻函数」事故）。

    背景（2026-09-20 实测事故，阿狸咪修复并留证于 index.html L8361-8364）：
      提交 `0d3482be4`「🧹 删 __renderFactorLab 死代码」把**紧邻其上的
      `_renderPostReady` 定义一并删掉**，但下方调用点仍在 ⇒
      `ReferenceError: _renderPostReady is not defined` ⇒ **策略回测区初始渲染全挂**。

    为什么既有的 [2/8] `new Function` **拦不住**（本项存在的唯一理由，已受控复现）：
      语法畸形（如 `try` 裸露）会被 [2/8] 抓住；但**整块干净删除**后 JS **语法依然合法**，
      [2/8] 报「28 个 inline script 块 0 错误」、11 项全绿 → deploy 放行（实测 rc=0）。
      即：这类事故 100% 穿透全部既有门禁，属于**只在浏览器运行时才炸**的盲区。

    判据（纯结构；只认「确定会 ReferenceError」的形态，不猜动态用法）：
      真源 = index.html 自身内联 <script> 块（剔除注释与字符串字面量后）：
        ① **裸标识符调用**：形如 `_renderPostReady()` 出现在**非定义位**、且
           该标识符全文**无任何定义形态** ⇒ 进候选。
           定义形态 = `function NAME(` / `NAME = function` / `NAME = (...) =>` /
                       `var|let|const NAME =` / `window.NAME =` / `class NAME` /
                       `function NAME` 声明 / 函数参数（`(NAME)` 参数位）/
                       `NAME: function`（对象方法）。
        ② **window.X 成员调用**：形如 `window.__renderXxx()` 且全文**无**
           `window.__renderXxx =` / `function __renderXxx` ⇒ 进候选。
        ③ **引用传递**：`setTimeout(X, …)` / `addEventListener('…', X)` 中的 X
           （传引用同样会 ReferenceError）⇒ 进候选。
        ④ **两档裁决**：
           · 候选且**无** `typeof X === 'function'` / `window.X &&` 守卫
             ⇒ ❌ **阻断**（一旦执行必炸，`0d3482be4` 即此档）
           · 候选但**有**守卫 ⇒ ⚠️ **告警放行**（不炸，但功能恒不执行=静默失效；
             实测存量命中 1 处 `__retryJudgmentRender`）。
             该档故意不阻断：属存量问题，一阻断会立刻打挂两条部署链。

    为什么这样判**不误杀**（关键）：
      · **只查页面自建的「__ / 下划线前缀」族**，不查第三方 API
        （`Math.max` / `JSON.parse` / `localStorage.getItem` 等一律不进候选）。
      · **注释/字符串先剥离**：`'..._renderPostReady()...'` 与 `// _renderPostReady()`
        不计入调用点。
        🔴 剥离必须**等长替换**（保留换行）—— 否则行号整体前移，红字报的 L 无法对位原文。
        🔴 且必须区分「除号 / 正则起点」—— 本仓含 `/[<>&"]/g` 这类正则，
           朴素「遇 // 即注释」会吞掉其后大段代码（实测把 970KB 压到 286KB，
           14 个真实定义集体消失 ⇒ 全盘误报）。
      · **探测不到内联块/清单缺失 ⇒ 放行**，避免守卫自身成为新的单点阻断源。

    维护纪律：**有意删除一个被调用的函数**时，必须同时改调用点（或加 `typeof` 守卫）
      —— 这正是本项要建立的摩擦力；改完本项自然转绿，无需登记豁免。
    """
    idx = ROOT / "index.html"
    if not idx.exists():
        return True, "index.html 不存在（放行）"
    try:
        txt = idx.read_text(encoding="utf-8")
    except Exception as e:
        return False, "index.html 读取失败: %s" % e

    # ── 只取内联 <script> 块（外链数据由 [6/8] 管；此处要看 JS 实体）──
    #    同时记录每个块在**原 index.html 中的起始行号**，使红字里报的 L 号可直接对位原文。
    blocks, base_lines = [], []
    for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", txt, re.S):
        base_lines.append(txt[:m.start(1)].count("\n") + 1)
        blocks.append(m.group(1))
    if not blocks:
        return True, "未探测到内联 script 块（放行，避免守卫自身成为单点）"

    # 用「块内行号 → 原 index.html 行号」的分段映射
    def _to_orig(block_idx, inner_ln):
        return base_lines[block_idx] + inner_ln - 1

    raw = "\n".join(blocks)

    # ── 剥离注释与字符串字面量（**等长替换**，保留换行 ⇒ 行号与原文一致）──
    #    为什么必须剥离：注释里常写到「下方 _xxx() 调用点仍在」这种**描述旧 bug 的句子**，
    #    计入调用点会产生大量假阳性（实测线上真身即命中一处纯注释）。
    #    🔴 为什么必须是「等长替换」而非「删除」：删除会把后续行号整体前移，
    #       红字里报的 L 号无法与 index.html 对位，排查时反而更费事。
    #    🔴 为什么不能只做朴素字符扫描：本仓含大量正则字面量（如 `/[<>&"]/g`），
    #       朴素的「遇 // 即行注释」会把正则内部当注释起点，进而**吞掉其后大段代码**
    #       （实测：朴素版把 970KB 压到 286KB，14 个真实定义集体消失 ⇒ 全盘误报）。
    #       故此处显式区分「除号 / 正则起点」，并跳过字符串内的转义。
    def _strip_keep_len(t):
        n = len(t)
        buf = list(t)
        i = 0
        while i < n:
            c = t[i]
            # ① 块注释 /* ... */
            if c == "/" and i + 1 < n and t[i + 1] == "*":
                j = t.find("*/", i + 2)
                j = n if j == -1 else j + 2
                for k in range(i, j):
                    if buf[k] != "\n":
                        buf[k] = " "
                i = j
                continue
            # ② HTML 注释 <!-- ... -->
            if c == "<" and t.startswith("<!--", i):
                j = t.find("-->", i + 4)
                j = n if j == -1 else j + 3
                for k in range(i, j):
                    if buf[k] != "\n":
                        buf[k] = " "
                i = j
                continue
            # ③ 行注释 // ...（要求 // 前是空白或分隔符，排除 http:// 与正则）
            if c == "/" and i + 1 < n and t[i + 1] == "/":
                prev = t[i - 1] if i > 0 else "\n"
                if prev in " \t\n;({[,=:!&|?+*%<>~^":
                    j = t.find("\n", i)
                    j = n if j == -1 else j
                    for k in range(i, j):
                        buf[k] = " "
                    i = j
                    continue
            # ④ 字符串字面量（含模板串，处理转义）
            if c in "\"'`":
                q = c; j = i + 1
                while j < n:
                    if t[j] == "\\":
                        j += 2; continue
                    if t[j] == q:
                        j += 1; break
                    j += 1
                for k in range(i, j):
                    if buf[k] != "\n":
                        buf[k] = " "
                i = j
                continue
            # ⑤ 正则字面量：仅在「运算符位」出现的 / 才是正则起点
            if c == "/":
                k = i - 1
                while k >= 0 and t[k] in " \t\n":
                    k -= 1
                p = t[k] if k >= 0 else ""
                if p == "" or p in "(,=:[!&|?{};+-*%~^<>":
                    j = i + 1; inclass = False
                    while j < n:
                        ch = t[j]
                        if ch == "\\":
                            j += 2; continue
                        if ch == "[":
                            inclass = True
                        elif ch == "]":
                            inclass = False
                        elif ch == "/" and not inclass:
                            j += 1; break
                        elif ch == "\n":
                            break
                        j += 1
                    for k2 in range(i, j):
                        if buf[k2] != "\n":
                            buf[k2] = " "
                    i = j
                    continue
            i += 1
        return "".join(buf)

    try:
        code = _strip_keep_len(raw)
    except Exception:
        code = raw
    # 剥离前/后长度必须相等（等长替换不变式）；不等则退回原文（宁可有噪音，不可漏报）
    if len(code) != len(raw):
        code = raw

    # ── 块内行号 → 原 index.html 行号的映射表 ──
    #    raw 是各块用 "\n" 拼起来的；每个块的行数可知，据此把 raw 行号换算回原文行号。
    _map, _acc = [], 0
    for bi, b in enumerate(blocks):
        nln = b.count("\n") + 1
        _map.append((_acc, _acc + nln, bi))    # [start, end) 在原 raw 中的行区间
        _acc += nln
    def _orig_ln(raw_ln):
        """raw（拼接串）的 1-based 行号 → 原 index.html 的 1-based 行号"""
        for st, en, bi in _map:
            if st <= raw_ln - 1 < en:
                return _to_orig(bi, (raw_ln - 1) - st + 1)
        return raw_ln

    # ── ① 已定义的标识符集合 ──
    defs = set()
    defs |= set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", code))
    defs |= set(re.findall(r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=", code))
    defs |= set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*=\s*function\b", code))
    defs |= set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", code))
    defs |= set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*=\s*[A-Za-z_$][\w$]*\s*=>", code))
    defs |= set(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", code))
    # 🔴 window.X = ... 只认「赋值右侧是函数/值」的形态；且必须先剔除
    #    `window.__renderFoo = function` 中的名字 —— 这是定义位，不是调用位。
    defs |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=(?!=)", code))
    # 对象属性简写定义（本仓常见）：{ _renderXxx: function(){...} }
    defs |= set(re.findall(r"([A-Za-z_$][\w$]*)\s*:\s*function\b", code))
    # 函数形参（含解构之外的单标识符形参）
    for ps in re.findall(r"function\s*[A-Za-z_$\w]*\s*\(([^)]*)\)", code):
        for p in ps.split(","):
            p = p.strip().split("=")[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", p):
                defs.add(p)
    for ps in re.findall(r"\(([^)]*)\)\s*(?:=>|\{)", code):
        for p in ps.split(","):
            p = p.strip().split("=")[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", p):
                defs.add(p)
    # for / catch 绑定
    defs |= set(re.findall(r"\bfor\s*\(\s*(?:var|let|const)\s+([A-Za-z_$][\w$]*)", code))
    defs |= set(re.findall(r"\bcatch\s*\(\s*([A-Za-z_$][\w$]*)", code))

    # ── ② 候选调用点：仅「_ 前缀」与「__ 前缀」与「window.__ 前缀」族 ──
    calls = {}   # name -> 首次出现行号
    # window.__xxx(  形式
    for m in re.finditer(r"window\.(__[A-Za-z0-9_$]+)\s*\(", code):
        nm = m.group(1)
        if nm not in calls:
            calls[nm] = _orig_ln(code[:m.start()].count("\n") + 1)
    # 裸 __xxx( / _xxx(  形式（排除紧跟 . 的成员调用，如 a._x()）
    for m in re.finditer(r"(?<![\w$.])(__?[A-Za-z][A-Za-z0-9_$]*)\s*\(", code):
        nm = m.group(1)
        if nm in ("_", "__"):
            continue
        # 🔴 定义位排除（必须精确，否则「删定义」会被误认为「定义仍在」）：
        #   ① `function NAME(`        —— 函数声明
        #   ② `NAME(…){` 且前导为 `function` / `get` / `set` / `async`
        #   ③ `NAME: function(`       —— 对象方法
        #   ④ `NAME = function(` / `NAME = (…) =>`
        pre = code[max(0, m.start() - 60):m.start()]
        if re.search(r"(?:^|[^\w$])(?:function|get|set|async)\s*$", pre):
            continue
        if re.search(r"[:=]\s*$", pre):                      # NAME: function( 或 NAME = function(
            continue
        if nm not in calls:
            calls[nm] = _orig_ln(code[:m.start()].count("\n") + 1)

    # ── ③ 兜底分支豁免：typeof X === 'function' / window.X && / if(X) ──
    #    🔴 本仓渲染器大量使用「先探测再调用」写法；这类调用**不会 ReferenceError**，
    #       若判为缺陷会产生巨量假阳性（实测不豁免则 13 处误报）。
    #    🔴 **必须在剥离前的 raw 上检测**，不能在 code 上：
    #       等长剥离把字符串字面量 `'function'` 换成了空白 ⇒ 在 code 上匹配不到
    #       `typeof X === 'function'` ⇒ 守卫识别失效、又把安全调用误判为硬缺陷
    #       （实测 S5 场景即因此误报）。注释剥离与否不影响本判定，故用 raw 安全。
    safe = set()
    def _scan_safe(src):
        for m in re.finditer(r"typeof\s+([A-Za-z_$][\w$.]*)\s*===?\s*['\"]function['\"]", src):
            safe.add(m.group(1).split(".")[-1])
        # window.X && ... 短路
        for m in re.finditer(r"\bwindow\.(__?[A-Za-z0-9_$]+)\s*&&", src):
            safe.add(m.group(1))
        # if(X) / if(window.X) 形态
        for m in re.finditer(r"if\s*\(\s*(?:window\.)?(__?[A-Za-z][A-Za-z0-9_$]*)\s*\)", src):
            safe.add(m.group(1))
    _scan_safe(raw)
    # 兜底：即使 raw 扫描异常，也把 code 上的 typeof X 形态补进 safe
    for m in re.finditer(r"typeof\s+([A-Za-z_$][\w$.]*)\s*===?\s*['\"]func", code):
        safe.add(m.group(1).split(".")[-1])
    # 引用传递（非调用）：setTimeout(X, …) / addEventListener('…', X)
    #   —— 传引用同样会 ReferenceError，故一并纳入候选
    for m in re.finditer(r"setTimeout\s*\(\s*(?:window\.)?(__?[A-Za-z][A-Za-z0-9_$]*)\s*,", code):
        calls.setdefault(m.group(1), _orig_ln(code[:m.start()].count("\n") + 1))
    for m in re.finditer(r"addEventListener\s*\(\s*['\"][^'\"]*['\"]\s*,\s*(?:window\.)?(__?[A-Za-z][A-Za-z0-9_$]*)\s*[,)]", code):
        calls.setdefault(m.group(1), _orig_ln(code[:m.start()].count("\n") + 1))

    # ── ④ 判定（**两档**，都与「运行期必炸」正交，故分开报告）──
    #   档一（❌ 阻断）：调用点存在、全文无定义、**且无 typeof/&& 守卫**
    #                    ⇒ 一旦执行必 ReferenceError，属硬事故（0d3482be4 即此档）。
    #   档二（⚠️ 告警，不阻断）：有 typeof/&& 守卫但全文无定义
    #                    ⇒ 不炸，但**功能恒不执行**（静默失效）。
    #                      本仓实测命中 1 处：`__retryJudgmentRender`（L8814/L18222 调用，
    #                      全文无 `window.__retryJudgmentRender =` 定义）⇒ 判定渲染重试
    #                      从未生效。该档**故意不阻断** deploy：它是「既有存量问题」，
    #                      一旦阻断会立刻打挂两条部署链；靠告警让它进入待修清单。
    hard, soft = [], []
    for nm, ln in sorted(calls.items(), key=lambda kv: kv[1]):
        if nm in defs:
            continue
        if nm in safe:
            soft.append("%s（L%d，有 typeof/&& 守卫）" % (nm, ln))
        else:
            hard.append("%s() 调用点 L%d，全文无定义且无守卫" % (nm, ln))
    if hard:
        return (False, "%d 处「无守卫的悬空调用」⇒ 运行期必 ReferenceError"
                       "（语法层检测不出，仅在浏览器执行时炸）:\n    "
                % len(hard) + "\n    ".join(hard[:8]))
    if soft:
        return (True, "⚠️ 无硬悬空调用；但发现 %d 处「有守卫的悬空调用」"
                      "（不炸但功能恒不执行，属静默失效，建议修）: %s"
                % (len(soft), "；".join(soft[:6])))
    return (True, "内联 script 候选调用点 %d 个：全部有定义（0 处悬空）" % len(calls))


def check_index_markers():
    """[10/10] index.html 核心标记守卫（2026-09-20 阿狸咪新增·结构性封堵「旧树静默覆盖」）。

    背景（2026-09-20 实测事故，双方各自独立复核）：
      10:43 小九推 A/B/C 三改（index.html +76/−18）；
      10:53 另一侧用**落后基线**的本机树推「强势跟踪卡改造」——父提交是当时 tip，
           但树里的 index.html 是旧版 ⇒ **快进提交**静默顶掉 A/B/C，CI 随后重建，
           线上 index.html 退回旧版（1371317 B），A/B/C 全 x0。
      `force:false` 拦不住（那本来就是快进）；「推送前断言线上 blob == 补丁基线」只在
      推送侧、且换个脚本就失效 ⇒ 需要一道**部署期、与推送者无关**的门禁。

    判据：真源 = docs/ops/index_protected_markers.txt（每行 `标记|说明|登记日期`）。
      任一标记在 index.html 中 0 命中 ⇒ **FAIL 阻断 deploy**（Pages 保持上一版，
      用户侧不受影响），并在红字里点名消失的标记。

    维护纪律（有意的摩擦力）：
      · 新增长期锚点（卡片渲染器 / 页面分节 / 数据源全局名）→ 追加一行；
      · **有意删除功能** → 必须同步删除对应行，否则本项会红（这正是设计目的）；
      · 清单文件缺失 ⇒ 放行并告警，避免守卫自身变成新的单点阻断源。
    """
    mf = ROOT / "docs" / "ops" / "index_protected_markers.txt"
    if not mf.exists():
        return True, "标记清单不存在（守卫未启用，放行）"
    idx = ROOT / "index.html"
    if not idx.exists():
        return True, "index.html 不存在（由 [6/8] 负责，放行）"
    try:
        txt = idx.read_text(encoding="utf-8")
    except Exception as e:
        return False, "index.html 读取失败: %s" % e

    rows, miss = 0, []
    for ln in mf.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [x.strip() for x in ln.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        rows += 1
        if parts[0] not in txt:
            miss.append(parts[0])
    if rows == 0:
        return True, "标记清单为空（放行）"
    if miss:
        return False, ("%d/%d 条核心标记在 index.html 中消失（疑似被落后基线覆盖，或功能整块删除"
                       "而未同步清单）：%s" % (len(miss), rows, "；".join(miss[:8])))
    return True, "index.html 核心标记 %d/%d 全部在位（卡片/分节/数据源锚点）" % (rows, rows)


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
        ("[9/9] 回测口径守卫", check_backtest_caliber),
        ("[10/10] index 核心标记守卫", check_index_markers),
        ("[11/11] defer 数据缓存守卫", check_defer_cache_guard),
        ("[12/12] 调用点定义守卫", check_callee_defined),
    ]
    print("=" * 60)
    print("v8 pre-deploy audit（CI 自动门禁，2026-09-05 启用；2026-09-11 扩至 5 项；"
          "2026-09-13 扩至 6 项；2026-09-14 扩至 8 项；2026-09-20 扩至 9 项（回测口径守卫）；"
          "同日扩至 10 项（[10/10] index.html 核心标记守卫·防旧树覆盖）；"
          "同日扩至 11 项（[11/11] defer 数据缓存守卫·防空结果固化）；"
          "2026-09-21 扩至 12 项（[12/12] 调用点定义守卫·防删函数连带删邻函数致 ReferenceError））")
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
    print(f"🎉 {len(checks)} 项全部通过 → deploy 可继续")
    sys.exit(0)


if __name__ == "__main__":
    main()
