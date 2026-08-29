#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 臃肿度与崩溃风险巡检（周末体检）
- 检查 index.html 体积、行数、script 标签平衡、重复 id
- 检查 data/*.js 重复 window.X 注入、总大小
- 用 node --check 做 JS 语法闸门
- 🛡 2026-08-29 一劳永逸：产物从 data/BLOAT_CHECK.js 迁到 .workbuddy/v8_bloat_report.json
  （原产物 4KB 死数据，全站 0 渲染引用；新路径入 .workbuddy/ 内部隐藏目录）
- 异常时邮件反馈（遵守 22:00-07:00 静音时段）

运行方式：
  python v8_bloat_check.py           # 本地生成报告
  python v8_bloat_check.py --alert   # 有严重风险时发送邮件
"""
import argparse
import html.parser
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from v8_send_alert import send_alert
except Exception:
    send_alert = None

REPO_ROOT = Path(__file__).resolve().parent
INDEX_HTML = REPO_ROOT / "index.html"
DATA_DIR = REPO_ROOT / "data"
# 🛡 2026-08-29 一劳永逸式修复：产物从 data/BLOAT_CHECK.js 迁到 .workbuddy/v8_bloat_report.json
#  旧产物为死数据（全站 0 渲染引用、纯 CDN 累赘），新路径入 .workbuddy/ 隐藏目录
#  - 不再被 v8_health_check 白名单审计（白名单已删 BLOAT_CHECK 项）
#  - 不再被 cloud_weekly_cleanup.yml 误删（保护列表已删 BLOAT_CHECK 项）
#  - 保留邮件告警能力（main 流程 send_bloat_email 不变）
OUT_JS = REPO_ROOT / ".workbuddy" / "v8_bloat_report.json"

QUIET_HOURS_START = 22
QUIET_HOURS_END = 7

# 2026-08-24 根因修复：加 30 分钟邮件去重。原 send_bloat_email 完全无去重，
# 一旦被高频跑批(如周末 15:30 任务 coupled 其他调度)每轮都发，即成邮件轰炸。
_BLOAT_ALERT_STATE = REPO_ROOT / ".workbuddy" / "v8_bloat_alert_state.json"
_BLOAT_DEDUPE_MIN = 30


def _bloat_alert_deduped(now_cst):
    """同组风险 30 分钟内只发一封。返回 (should_send, reason)。"""
    try:
        if _BLOAT_ALERT_STATE.exists():
            st = json.loads(_BLOAT_ALERT_STATE.read_text(encoding="utf-8"))
            last, last_key = st.get("last_ts"), st.get("last_key")
            if last and last_key == "bloat":
                ago = (now_cst.timestamp() - last) / 60
                if ago < _BLOAT_DEDUPE_MIN:
                    return False, f"距上次体检邮件仅 {ago:.0f}min < {_BLOAT_DEDUPE_MIN}min"
    except Exception:
        pass
    return True, ""


def _save_bloat_alert_state(now_cst):
    try:
        _BLOAT_ALERT_STATE.parent.mkdir(parents=True, exist_ok=True)
        _BLOAT_ALERT_STATE.write_text(
            json.dumps({"last_ts": now_cst.timestamp(), "last_key": "bloat"}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def in_quiet_hours(now_cst=None):
    """判断当前是否处于夜间静音时段（北京时间 22:00-07:00）。"""
    n = now_cst or datetime.now(timezone(timedelta(hours=8)))
    h = n.hour
    if QUIET_HOURS_START <= QUIET_HOURS_END:
        return QUIET_HOURS_START <= h < QUIET_HOURS_END
    return h >= QUIET_HOURS_START or h < QUIET_HOURS_END


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def add_item(items, name, status, message, metric=None):
    items.append({
        "name": name,
        "status": status,
        "message": message,
        "metric": metric,
    })


def check_file_exists():
    if not INDEX_HTML.exists():
        return [{
            "name": "index.html 存在性",
            "status": "fail",
            "message": f"找不到 {INDEX_HTML}",
            "metric": None,
        }]
    return []


def check_size(text):
    size_bytes = INDEX_HTML.stat().st_size
    size_kb = round(size_bytes / 1024, 1)
    status = "ok"
    if size_kb > 1200:
        status = "fail"
    elif size_kb > 800:
        status = "warn"
    msg = f"{size_kb} KB"
    if status != "ok":
        msg += "；体积偏大，建议拆分或清理死代码"
    return [{"name": "index.html 体积", "status": status, "message": msg, "metric": size_kb}]


def check_lines(text):
    lines = text.count("\n") + 1
    status = "ok"
    if lines > 30000:
        status = "fail"
    elif lines > 20000:
        status = "warn"
    msg = f"{lines} 行"
    if status != "ok":
        msg += "；行数偏多，关注可维护性"
    return [{"name": "index.html 行数", "status": status, "message": msg, "metric": lines}]


class _ScriptCounter(html.parser.HTMLParser):
    """用浏览器同款 HTML 解析统计 <script>/</script>，天然忽略注释与 script 内容里的字样。"""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.opens = 0
        self.closes = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.opens += 1

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self.closes += 1


def check_script_balance(text):
    """检查 <script> 与 </script> 是否成对，并统计 script 块数。

    用 HTMLParser 而非正则计数：JS 注释里的 '<script>' 字样（如
    "// 在后续 <script> 块里定义"）不会污染统计。
    """
    counter = _ScriptCounter()
    counter.feed(text)
    opens, closes = counter.opens, counter.closes
    status = "ok"
    msg = f"{opens} 个 <script> 块，{closes} 个 </script>"
    metric = {"opens": opens, "closes": closes}
    if opens != closes:
        status = "fail"
        msg += "；SCRIPT 标签未配对，可能导致页面崩溃"
    return [{"name": "script 标签平衡", "status": status, "message": msg, "metric": metric}]


def check_duplicate_ids(text):
    ids = re.findall(r'id=["\']([^"\']+)["\']', text)
    counts = Counter(ids)
    dups = {k: v for k, v in counts.items() if v > 1}
    status = "ok"
    msg = f"共 {len(ids)} 个 id，无重复"
    metric = {"total": len(ids), "duplicates": 0}
    if dups:
        status = "fail"
        top = list(dups.items())[:5]
        msg = f"发现 {len(dups)} 个重复 id：{', '.join(f'{k}({v}次)' for k, v in top)}"
        if len(dups) > 5:
            msg += f" 等"
        metric["duplicates"] = len(dups)
    return [{"name": "重复 id 检查", "status": status, "message": msg, "metric": metric}]


def check_node_syntax():
    """提取所有 <script> 块内容为临时 .js，调用 node --check 做 JS 语法闸门。"""
    node_paths = [
        Path("C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe"),
        Path("C:/Users/Administrator/.workbuddy/binaries/node/versions/22.12.0/node.exe"),
        Path("E:/node/node.exe"),
        Path("node.exe"),
    ]
    node = None
    for p in node_paths:
        if p.exists() and p.is_file():
            node = str(p)
            break
    if not node:
        # 尝试 PATH
        try:
            subprocess.check_output(["node", "--version"], stderr=subprocess.STDOUT, timeout=10)
            node = "node"
        except Exception:
            return [{"name": "node --check 语法闸门", "status": "warn",
                     "message": "未找到 node，跳过语法检查", "metric": None}]

    text = INDEX_HTML.read_text(encoding="utf-8", errors="replace")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script\s*>", text, re.I)
    if not scripts:
        return [{"name": "node --check 语法闸门", "status": "warn",
                 "message": "未找到 script 内容", "metric": None}]

    import tempfile
    combined = "\n".join(scripts)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(combined)
            tmp = f.name
        result = subprocess.run(
            [node, "--check", tmp],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return [{"name": "node --check 语法闸门", "status": "ok",
                     "message": f"语法检查通过（{len(scripts)} 个 script 块）", "metric": len(scripts)}]
        else:
            err = (result.stderr or result.stdout or "").strip().replace("\n", " ")[:200]
            return [{"name": "node --check 语法闸门", "status": "fail",
                     "message": f"语法错误：{err}", "metric": None}]
    except Exception as e:
        return [{"name": "node --check 语法闸门", "status": "warn",
                 "message": f"检查失败：{e}", "metric": None}]
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def check_top_level_duplicates(text):
    """粗略检查顶层全局作用域是否有重复 function 定义（不含 IIFE 内部）。
    仅作风险参考，不直接判 fail。
    """
    lines = text.splitlines()
    funcs = Counter()
    for line in lines:
        # 只统计真正顶层作用域：行首无缩进
        if line.startswith((" ", "\t")):
            continue
        if not line.startswith("function "):
            continue
        m = re.match(r"function\s+(\w+)\s*\(", line)
        if m:
            funcs[m.group(1)] += 1
    dups = {k: v for k, v in funcs.items() if v > 1}
    status = "ok"
    msg = f"顶层 function {len(funcs)} 个，无重复"
    metric = {"total": len(funcs), "duplicates": 0}
    if dups:
        status = "warn"
        top = list(dups.items())[:5]
        msg = f"发现 {len(dups)} 个顶层重复函数：{', '.join(f'{k}({v}次)' for k, v in top)}"
        metric["duplicates"] = len(dups)
    return [{"name": "顶层重复函数", "status": status, "message": msg, "metric": metric}]


def check_data_js():
    """检查 data/*.js 的体积、重复 window.X 变量、是否被 index.html 引用。"""
    items = []
    if not DATA_DIR.exists():
        add_item(items, "data 目录存在性", "fail", "data 目录不存在")
        return items

    js_files = sorted(DATA_DIR.glob("*.js"))
    total_size = sum(p.stat().st_size for p in js_files)
    total_kb = round(total_size / 1024, 1)

    status = "ok"
    msg = f"{len(js_files)} 个文件，共 {total_kb} KB"
    if total_kb > 12000:
        status = "fail"
        msg += "；体积偏大，建议拆分或清理死代码"
    elif total_kb > 9000:
        status = "warn"
        msg += "；体积偏多，关注可维护性"
    add_item(items, "data/*.js 总体积", status, msg, {"files": len(js_files), "kb": total_kb})

    # 重复 window.X 变量
    var_counts = Counter()
    for p in js_files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"window\.(\w+)\s*=", txt):
            var_counts[m.group(1)] += 1
    dups = {k: v for k, v in var_counts.items() if v > 1}
    status = "ok"
    msg = f"{len(var_counts)} 个 window.X 注入，无重复"
    if dups:
        status = "fail"
        msg = f"发现 {len(dups)} 个重复 window 变量：{', '.join(dups)}"
    add_item(items, "重复 window.X 注入", status, msg, {"total": len(var_counts), "duplicates": len(dups)})

    # 未在 index.html 中引用的 data/*.js
    # 三种引用方式都算已引用：
    #   1. <script src="data/NAME.js" 或 src="data/NAME.js?v=sha10"（含 defer）
    #   2. 代码中直接使用 window.NAME / window['NAME']
    #   3. 字符串字面量 "data/NAME.js" 或 'data/NAME.js'
    html_text = INDEX_HTML.read_text(encoding="utf-8", errors="replace")
    unreferenced = []
    for p in js_files:
        # 检查报告自身不需要被页面引用
        if p.name == OUT_JS.name:
            continue
        var_name = p.name[:-3]  # 去掉 .js
        # 1) script src 引用
        src_pat = re.compile(r'src=["\']data/' + re.escape(p.name) + r'(\?[^"\']*)?["\']')
        # 2) window 变量引用（含可选空格、点号、方括号、&&/||）
        win_pat = re.compile(r'\bwindow\.["\']?' + re.escape(var_name) + r'["\']?\b')
        # 3) 字符串字面量中出现 data/NAME.js
        lit_pat = re.compile(r'["\']data/' + re.escape(p.name) + r'["\']')
        if not (src_pat.search(html_text) or win_pat.search(html_text) or lit_pat.search(html_text)):
            unreferenced.append(p.name)
    status = "ok"
    msg = "全部已引用"
    if unreferenced:
        status = "warn"
        msg = f"{len(unreferenced)} 个未引用：{', '.join(unreferenced[:5])}"
    add_item(items, "data/*.js 引用检查", status, msg, {"unreferenced": len(unreferenced)})

    return items


def build_report(items):
    ok = sum(1 for x in items if x["status"] == "ok")
    warn = sum(1 for x in items if x["status"] == "warn")
    fail = sum(1 for x in items if x["status"] == "fail")
    overall = "ok" if fail == 0 else ("warn" if fail <= 2 else "fail")
    return {
        "updated": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "overall": overall,
        "summary": {"ok": ok, "warn": warn, "fail": fail, "total": len(items)},
        "items": items,
    }


def write_bloat_js(report):
    # 🛡 2026-08-29 一劳永逸：产物落到 .workbuddy/（内部、不入白名单、不入 CDN）
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    # 改写为 JSON（不再写 .js window 注入），前端不读取，仅供人工查阅 + 邮件附件
    OUT_JS.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[INFO] 已生成 {OUT_JS}")


def send_bloat_email(report):
    if not send_alert:
        print("[WARN] 邮件发送器未导入，跳过邮件")
        return False
    if report["overall"] == "ok":
        print("[INFO] 总体健康，跳过邮件")
        return False
    if in_quiet_hours():
        print("[INFO] 当前处于夜间静音时段（22:00-07:00），跳过邮件，仅记录日志")
        return False

    now_cst = datetime.now(timezone(timedelta(hours=8)))
    send, why = _bloat_alert_deduped(now_cst)
    if not send:
        print(f"[INFO] 体检邮件去抖：{why}，跳过（仅记录日志）")
        return False

    subject = f"【v8周末体检】{report['summary']['fail']} 项风险 / {report['updated']}"
    lines = [
        f"v8 臃肿度/崩溃风险检查时间：{report['updated']}",
        f"总体状态：{report['overall']}",
        f"统计：✓ {report['summary']['ok']} / ⚠ {report['summary']['warn']} / ✗ {report['summary']['fail']}",
        "",
        "异常项：",
    ]
    for item in report["items"]:
        if item["status"] != "ok":
            flag = "✗" if item["status"] == "fail" else "⚠"
            lines.append(f"{flag} {item['name']}: {item['message']}")
    lines.append("")
    lines.append("建议：非交易时段可抽时间清理死代码、拆分大文件、修复重复 id/函数。")
    _save_bloat_alert_state(now_cst)
    return send_alert(subject, "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="v8 臃肿度与崩溃风险巡检")
    parser.add_argument("--alert", action="store_true", help="有严重风险时发送邮件")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    print(f"[INFO] v8 bloat check start @ {now_cst().strftime('%Y-%m-%d %H:%M:%S')}")

    items = []
    items.extend(check_file_exists())
    if INDEX_HTML.exists():
        text = INDEX_HTML.read_text(encoding="utf-8", errors="replace")
        items.extend(check_size(text))
        items.extend(check_lines(text))
        items.extend(check_script_balance(text))
        items.extend(check_duplicate_ids(text))
        items.extend(check_top_level_duplicates(text))
        items.extend(check_node_syntax())
    items.extend(check_data_js())

    report = build_report(items)
    write_bloat_js(report)

    print(f"[INFO] 总体: {report['overall']} | 统计: {report['summary']}")
    for item in report["items"]:
        if item["status"] != "ok":
            print(f"  [{item['status'].upper()}] {item['name']}: {item['message']}")

    if args.alert:
        send_bloat_email(report)

    sys.exit(0 if report["overall"] == "ok" else 2)


if __name__ == "__main__":
    main()
