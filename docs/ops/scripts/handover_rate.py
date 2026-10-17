#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交接档产出速率统计 —— v8-handoff-gateway 协议 item `handoff-doc-rate-metric` 的落地实现。

为什么需要它
------------
协议 §1.5 规定「只在需拍板 / 跨机结构性变更两种情况下写 .md 档」，
但 2026-09-21 实测：协议 08:45 上线，**当天 08:45 之后仍新增 20 档**（目标 5~10 档/天），
其中 2 份是协议后写的「回执」档。
根因不是大家不认规则，而是**「规则无强制机制 ⇒ 上线即被自己违反」**（协议原文即如此预言）。

本脚本把「档数」从感觉变成数字（先可量化、再谈阻断）。

用法
----
    python docs/ops/scripts/handover_rate.py                      # 近 7 天
    python docs/ops/scripts/handover_rate.py --days 1             # 只看今天
    python docs/ops/scripts/handover_rate.py --asof 2026-09-21    # 回溯某日
    python docs/ops/scripts/handover_rate.py --json               # 机器可读（写回 HANDOFF.yaml meta）

退出码
------
    0  一切正常（含「样本为空」）
    1  超阈值（仅报告，供 CI 决定是否告警；**默认不阻断 deploy** —— 协议：「先可量化、再谈阻断」）

设计约束（勿违反）
------------------
* **只读**：不写任何文件、不碰 git、不联网。可安全挂在任何 CI step 上。
* **不依赖第三方库**（无 pyyaml）—— CI 环境版本不可控。
* 档名日期解析要同时吃下两种命名：
    `2026-09-21_1710_小九给阿狸咪_….md`（标准）
    `xiaojiu_to_alimi_2026-09-21_0007_….md`（旧自由命名，日期在中间）
  ⇒ 一律用「找第一个 `20xx-xx-xx`」而不是取前 10 字符（实测 560 档里两种都有）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import sys
from collections import Counter

# 「回执 / 催办」判定词 —— 与协议 §3/§4 同口径
HANDSHAKE_WORDS = ("回执", "催办", "紧急", "URGENT", "急件")
# 协议 §1.5 上线时刻（CST 2026-09-21 08:45）—— 用于「回归监测」分段
PROTOCOL_START = _dt.datetime(2026, 9, 21, 8, 45)
# 目标区间（档/天）
TARGET_LO, TARGET_HI = 5, 10

_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
_TIME_RE = re.compile(r"_(\d{4})_")


def parse_name(name: str):
    """从档名解析 (datetime, 是否回执催办类)；解析不出日期返 None。"""
    m = _DATE_RE.search(name)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    tm = _TIME_RE.search(name[: m.end() + 6])
    hh, mm = (int(tm.group(1)[:2]), int(tm.group(1)[2:])) if tm else (0, 0)
    if hh > 23 or mm > 59:          # 形如 _2026_ 的误命中
        hh = mm = 0
    try:
        dt = _dt.datetime(y, mo, d, hh, mm)
    except ValueError:
        return None
    return dt, any(w in name for w in HANDSHAKE_WORDS)


def collect(handover_dir: str):
    rows = []
    if not os.path.isdir(handover_dir):
        return rows
    for name in os.listdir(handover_dir):
        if not name.lower().endswith(".md"):
            continue
        got = parse_name(name)
        if got:
            rows.append({"name": name, "dt": got[0], "handshake": got[1]})
    rows.sort(key=lambda r: r["dt"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="交接档目录（默认 docs/ops/handover）")
    ap.add_argument("--repo-root", default=None, help="仓库根（默认自动向上寻找）")
    ap.add_argument("--days", type=int, default=7, help="统计窗口（默认近 7 天）")
    ap.add_argument("--asof", default=None, help="以该日 23:59 为窗口终点（YYYY-MM-DD）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.dir:
        hdir = args.dir
    else:
        root = args.repo_root or os.getcwd()
        cand = os.path.join(root, "docs", "ops", "handover")
        while not os.path.isdir(cand) and os.path.dirname(root) != root:
            root = os.path.dirname(root)
            cand = os.path.join(root, "docs", "ops", "handover")
        hdir = cand

    rows = collect(hdir)
    if args.asof:
        end = _dt.datetime.strptime(args.asof, "%Y-%m-%d") + _dt.timedelta(hours=23, minutes=59)
    else:
        end = _dt.datetime.now()
    start = end - _dt.timedelta(days=args.days)

    win = [r for r in rows if start <= r["dt"] <= end]
    per_day = Counter(r["dt"].strftime("%Y-%m-%d") for r in win)
    hs = [r for r in win if r["handshake"]]
    after = [r for r in rows if r["dt"] > PROTOCOL_START and PROTOCOL_START <= end]

    # 只在「窗口覆盖了协议上线日之后」时输出回归监测，避免历史窗口误报
    regress = None
    if end > PROTOCOL_START:
        after_win = [r for r in after if r["dt"] >= start]
        days_span = max(1, (end - max(start, PROTOCOL_START)).days + 1)
        regress = {
            "protocol_start": PROTOCOL_START.strftime("%Y-%m-%d %H:%M"),
            "docs_after_protocol": len(after_win),
            "days_span": days_span,
            "per_day_avg": round(len(after_win) / days_span, 1),
            "handshake_after_protocol": len([r for r in after_win if r["handshake"]]),
            "handshake_names": [r["name"] for r in after_win if r["handshake"]][-12:],
        }

    per_day_avg = round(len(win) / max(1, args.days), 1)
    report = {
        "handover_dir": hdir,
        "total_docs": len(rows),
        "window_days": args.days,
        "window": [start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")],
        "docs_in_window": len(win),
        "per_day_avg": per_day_avg,
        "per_day": dict(sorted(per_day.items())),
        "handshake_docs": len(hs),
        "handshake_names": [r["name"] for r in hs],
        "target_range": [TARGET_LO, TARGET_HI],
        "verdict": ("ok" if len(win) <= TARGET_HI * args.days else
                    ("warn" if len(win) <= TARGET_HI * args.days * 2 else "over")),
        "regression": regress,
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        # Windows 控制台默认 GBK ⇒ 中文 stdout 会 UnicodeEncodeError；CI(Linux) 亦不保证 UTF-8
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        sys.stdout.write(
            "交接档产出速率（目录 %s）\n" % hdir
            + "  窗口 %s ~ %s（%d 天）\n" % (report["window"][0], report["window"][1], args.days)
            + "  窗口内新增 %d 档 / 日均 %.1f 档  [目标 %d~%d 档/天]  ⇒ %s\n"
            % (len(win), per_day_avg, TARGET_LO, TARGET_HI, report["verdict"])
            + "  其中回执/催办/紧急类 %d 档\n" % len(hs)
            + "".join("    🔴 %s\n" % n for n in report["handshake_names"])
            + ("  逐日：%s\n" % json.dumps(report["per_day"], ensure_ascii=False))
            + (("  协议(08:45)后新增 %d 档 / %d 天 日均 %.1f（回执类 %d）\n"
                % (regress["docs_after_protocol"], regress["days_span"],
                   regress["per_day_avg"], regress["handshake_after_protocol"]))
               if regress else "")
        )

    # 超 2 倍目标才返 1，且仅是「报告不阻断」——调用方自行决定
    return 1 if report["verdict"] == "over" else 0


if __name__ == "__main__":
    sys.exit(main())
