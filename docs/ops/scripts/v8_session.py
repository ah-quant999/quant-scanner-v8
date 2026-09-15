#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_session.py — 同机双会话（双专家）登记器：让同一台机上的两个会话**互相看得见**。

■ 解决什么（2026-09-13 主人提问「每台机子都有两个专家在一起改，怎么区分和避让」）
  `docs/ops/handover/README.md` §八 已定义「区分」（commit 附 `[host/会话号]`）与
  「避让」（FETCH_HEAD 派生 / 锚点断言 / 快进推 / 失败即重基）。但那套机制能防的是
  **字节级覆盖**。本轮实测暴露出第二类事故：**语义撞车** ——

    同一个「backfill 回填」误判，在本机两个会话里**各发生一次**
    （会话 A 在 2115 单建议「stage_to_raw 加单调保护」，被小九 2145 打掉；
      会话 B 在 2220 单**独立**复核出「gold_pool 继承坏值」并**又建议了一次同样的保护**）。
    两会话都推了 commit、都读了同一批交接，但**互不感知对方的结论**。

  git 层拦不住这种 —— 两次改动不冲突，只是**结论重复且都错**。
  本工具提供一条**会话间结论登记**：开工前登记（begin）、推后留痕（push）、
  落笔结论前自查（check），使「另会话 20 分钟前刚在同一个主题下得了个结论」可见。

■ 与 git 机制的关系（不是替代，是补位）
  · git（FETCH_HEAD + 锚点断言 + 快进推）→ 防**覆盖**（硬冲突）
  · 本工具 → 防**重复劳动 / 重复犯错**（软冲突）

■ 存放位置（关键设计）
  · 工具本体：仓库内 `docs/ops/scripts/v8_session.py` ⇒ 随 git 同步到**两台机**，两边都能用
  · 运行数据：`~/.workbuddy/v8_session_registry.jsonl` ⇒ **机器本地、永不入库**
    （同机两会话天然共享同一份；入库会引入提交冲突与仓库膨胀）

■ 用法
  python docs/ops/scripts/v8_session.py begin --topic "回测口径统一" --files algorithms/run_algorithms.py,logic.html
  python docs/ops/scripts/v8_session.py who --minutes 180
  python docs/ops/scripts/v8_session.py check --files logic.html --minutes 20
  python docs/ops/scripts/v8_session.py push --commit <sha> --files a.py,b.py --msg "主题"
  python docs/ops/scripts/v8_session.py end --summary "已完成 X"

■ 会话号（🔴 2026-09-13 重修：必须**按会话**派生，不能按机器）
  ① 优先环境变量 `V8_SESSION`（如 `alimi-A` / `alimi-B`）—— 人工可覆盖；
  ② 否则按 **cwd 所属的会话目录**（形如 `2026-08-28-21-48-18`）分配，映射存
     `~/.workbuddy/v8_session_ids.json` ⇒ **同机两会话各得稳定且不同的号**；
     可用 `V8_SESSION_DIR` 显式指定会话目录（推送工具应传工具自身所在目录）。
  ③ 上溯不到会话目录 ⇒ 回退旧的机器级 `~/.workbuddy/v8_session_id`，并向 stderr 告警
     —— ⚠️ 该文件**机器级共享**，同机多会话会收敛成同一个号（这正是重修前的实测缺陷）。
  ⚠️ 不许编造身份：三条都拿不到才落 `unknown`。
  🔴 本文件的 `id` 子命令是**会话身份的唯一真源**，推送工具必须调它取号。

■ 退出码（供脚本消费）
  0 = 无冲突   2 = 发现潜在冲突（不阻断，仅提示）   3 = 参数/环境错误
"""
import argparse
import json
import os
import re
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

REG = Path.home() / ".workbuddy" / "v8_session_registry.jsonl"
IDF = Path.home() / ".workbuddy" / "v8_session_id"          # 旧机器级文件（仅作回退）
IDS = Path.home() / ".workbuddy" / "v8_session_ids.json"    # 每会话一条 {会话目录名: 会话号}
_SDIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[-_]\d{2}[-_]\d{2}[-_]\d{2}$")
LEASE_MIN = 90      # `begin` 的租约窗口：窗口内同文件/同主题视为可能撞车
HOT_MIN = 20        # `check` 的热点窗口：窗口内他人改过的文件视为热
KEEP_DAYS = 14      # 登记表自动裁剪：只保留最近 N 天（防无限膨胀）


def _now():
    return datetime.now()


def host():
    return os.environ.get("V8_HOSTNAME") or socket.gethostname()


def _sdir_key():
    """会话身份键 = cwd 所属的**会话目录名**（如 `2026-08-28-21-48-18`）。

    🔴 为什么必须按会话而非按机器：`~/.workbuddy/v8_session_id` 是机器级共享文件，
      同机两个会话未设 `V8_SESSION` 时会**收敛到同一个号** ⇒ commit 尾巴全成
      `[Cat]`/`[Cat/cat-1]` ⇒「同机哪个会话」不可区分。按会话目录分配可根治。
    """
    env = (os.environ.get("V8_SESSION_DIR") or "").strip()
    base = os.path.abspath(env or os.getcwd())
    for anc in [Path(base)] + list(Path(base).parents):
        if _SDIR_RE.match(anc.name):
            return anc.name
    return None


def session_id():
    s = (os.environ.get("V8_SESSION") or "").strip()
    if s:
        return s
    key = _sdir_key()
    try:
        if key:
            m = {}
            if IDS.exists():
                m = json.loads(IDS.read_text(encoding="utf-8")) or {}
                if not isinstance(m, dict):
                    m = {}
            if str(m.get(key, "")).strip():
                return str(m[key]).strip()
            used = set(str(v) for v in m.values())
            prefix = host().split(".")[0].lower() or "unknown"
            i = 1
            while "%s-%d" % (prefix, i) in used:
                i += 1
            sid = "%s-%d" % (prefix, i)
            m[key] = sid
            IDS.parent.mkdir(parents=True, exist_ok=True)
            IDS.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
            return sid
        if IDF.exists():
            v = IDF.read_text(encoding="utf-8").strip()
            if v:
                sys.stderr.write(
                    "[v8_session] ⚠️ 未识别到会话目录，回退机器级 ID %r；"
                    "该文件为机器级共享，**同机多会话会收敛**，"
                    "请设 V8_SESSION 或 V8_SESSION_DIR\n" % v)
                return v
    except Exception:
        pass
    return "unknown"


def norm_files(rel):
    out = []
    for x in (rel or []):
        x = x.strip().replace("\\", "/")
        if x:
            out.append(x)
    return out


def load(minutes=None):
    if not REG.exists():
        return []
    rows = []
    cut = None
    if minutes is not None:
        cut = time.time() - minutes * 60
    for line in REG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if cut is not None and float(r.get("epoch") or 0) < cut:
            continue
        rows.append(r)
    return rows


def append(kind, topic=None, files=None, commit=None, msg=None, summary=None):
    REG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "epoch": time.time(),
        "ts": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "session": session_id(),
        "host": host(),
        "topic": topic,
        "files": norm_files(files),
        "commit": commit,
        "msg": msg,
        "summary": summary,
    }
    with open(REG, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def prune():
    """按 KEEP_DAYS 裁剪，防登记表无限膨胀（失败静默，不影响主流程）。"""
    try:
        rows = load()
        cut = time.time() - KEEP_DAYS * 86400
        rows = [r for r in rows if float(r.get("epoch") or 0) >= cut]
        with open(REG, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _overlap(a, b):
    sa, sb = set(a or []), set(b or [])
    return sorted(sa & sb)


def _topic_alike(t1, t2):
    """主题相似：双向子串，或（去标点后）2 字以上公共片段。粗粒度即可，宁可多提示。"""
    if not t1 or not t2:
        return False
    if t1 in t2 or t2 in t1:
        return True
    a = set(c for c in t1 if "\u4e00" <= c <= "\u9fff" or c.isalnum())
    b = set(c for c in t2 if "\u4e00" <= c <= "\u9fff" or c.isalnum())
    return len(a & b) >= 3


def _others(minutes):
    me = session_id()
    return [r for r in load(minutes) if r.get("session") != me]


def cmd_begin(a):
    topic = a.topic.strip()
    files = norm_files(a.files)
    append("begin", topic=topic, files=files)
    others = _others(LEASE_MIN)
    hits = []
    for r in others:
        ov = _overlap(files, r.get("files"))
        same_topic = _topic_alike(topic, r.get("topic") or "")
        if ov or same_topic:
            hits.append((r, ov, same_topic))
    print("✅ 已登记 begin：会话 %s@%s  主题=%s  文件=%s" % (session_id(), host(), topic, files or "—"))
    if not hits:
        print("🟢 近 %d 分钟内无其他会话在相同主题/文件上活动" % LEASE_MIN)
        prune()
        return 0
    print("\n⚠️  近 %d 分钟内有 %d 条**可能撞车**的他人记录：" % (LEASE_MIN, len(hits)))
    print("%-19s %-10s %-22s %s" % ("时间", "会话", "主题", "重叠"))
    for r, ov, same in hits:
        why = []
        if ov:
            why.append("文件:" + ",".join(ov[:3]) + ("…" if len(ov) > 3 else ""))
        if same:
            why.append("主题相近")
        print("%-19s %-10s %-22s %s" % (r.get("ts", ""), r.get("session", ""),
                                        (r.get("topic") or "—")[:20], " / ".join(why)))
    print("\n⇒ 不是硬阻断。请先 `who` 看清对方在做什么，再决定是否错开主题/文件。")
    prune()
    return 2


def cmd_who(a):
    rows = load(a.minutes)
    if not rows:
        print("🟢 近 %d 分钟无登记记录（登记表 %s）" % (a.minutes, REG))
        return 0
    by = {}
    for r in rows:
        by.setdefault(r.get("session") or "?", []).append(r)
    me = session_id()
    print("近 %d 分钟登记（本会话 = %s）  %s" % (a.minutes, me, REG))
    for sid, rs in sorted(by.items(), key=lambda kv: -max(x.get("epoch", 0) for x in kv[1])):
        mark = " ←我" if sid == me else ""
        print("\n【%s%s】%d 条" % (sid, mark, len(rs)))
        for r in rs[-8:]:
            print("  %s %-6s %s%s" % (r.get("ts", ""), r.get("kind", ""),
                                      (r.get("topic") or r.get("msg") or r.get("summary") or "")[:58],
                                      ("  " + (r.get("commit") or "")[:9]) if r.get("commit") else ""))
    return 0


def cmd_check(a):
    files = norm_files(a.files)
    if not files:
        print("参数错误：--files 必填", file=sys.stderr)
        return 3
    rows = _others(a.minutes)
    hits = [(r, _overlap(files, r.get("files"))) for r in rows]
    hits = [(r, ov) for r, ov in hits if ov]
    if not hits:
        print("🟢 近 %d 分钟内无其他会话改过这些文件：%s" % (a.minutes, files))
        return 0
    print("⚠️  近 %d 分钟内有其他会话改过你即将改的文件：" % a.minutes)
    for r, ov in hits:
        print("  %s  %s  [%s]  %s" % (r.get("ts", ""), r.get("session", ""),
                                      r.get("kind", ""), ",".join(ov)))
    print("⇒ 落笔/推送前请 `git show <ref>:<file>` 看对方**改成了什么**，"
          "以及近 1 小时同主题交接单（防重复结论）。")
    return 2


def cmd_push(a):
    append("push", files=a.files, commit=a.commit, msg=a.msg)
    print("✅ 已登记 push：%s  %s" % ((a.commit or "")[:9], norm_files(a.files) or "—"))
    prune()
    return 0


def cmd_end(a):
    append("end", summary=a.summary)
    print("✅ 已登记 end：%s" % (a.summary or "—"))
    return 0


def cmd_note(a):
    append("note", topic=a.topic, files=a.files, msg=a.msg)
    print("✅ 已登记结论：%s" % (a.msg or a.topic or "—"))
    return 0


def cmd_id(a):
    """打印 `host/session`（供推送工具取号 ⇒ commit 尾巴与登记表**同源**）。

    🔴 单一真源：推送工具**必须**调本命令，禁止自行实现。实测教训：本机
      `atomic_patch_push.py` 曾自行取号 ⇒ 工具落 `[Cat]`、登记表落 `cat-1`，
      两处不同源 ⇒ 同机两会话在 git 层与登记表里都不可区分。
    """
    print("%s/%s" % (host().split(".")[0].lower(), session_id()))
    return 0


def main():
    ap = argparse.ArgumentParser(description="v8 同机双会话登记器")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("begin", help="开工登记（并提示潜在撞车）")
    p.add_argument("--topic", required=True)
    p.add_argument("--files", default="")
    p.set_defaults(fn=cmd_begin)

    p = sub.add_parser("who", help="看近 N 分钟各会话在做什么")
    p.add_argument("--minutes", type=int, default=180)
    p.set_defaults(fn=cmd_who)

    p = sub.add_parser("check", help="自查：这些文件近 N 分钟被他人改过吗")
    p.add_argument("--files", required=True)
    p.add_argument("--minutes", type=int, default=HOT_MIN)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("push", help="推送后留痕（一般是推送工具自动调）")
    p.add_argument("--commit", default=None)
    p.add_argument("--files", default="")
    p.add_argument("--msg", default=None)
    p.set_defaults(fn=cmd_push)

    p = sub.add_parser("end", help="收工登记")
    p.add_argument("--summary", default=None)
    p.set_defaults(fn=cmd_end)

    p = sub.add_parser("note", help="登记一条结论（防两会话重复结论/重复犯错）")
    p.add_argument("--topic", required=True)
    p.add_argument("--msg", default=None)
    p.add_argument("--files", default="")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("id", help="打印当前会话身份 host/session（推送工具取号的唯一真源）")
    p.set_defaults(fn=cmd_id)

    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    # --files 允许用英文逗号分隔
    if hasattr(a, "files") and isinstance(a.files, str):
        a.files = [x for x in a.files.split(",") if x.strip()]
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
