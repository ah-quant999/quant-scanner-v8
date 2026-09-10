#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 批次自愈判定 + 上游顺序闸门（2026-09-10 主人令「一劳永逸·以后都用这个逻辑算当天数据」）

■ 为什么要这个脚本（今晚事故根因）
  旧逻辑：workflow 只按 CST 小时「盲猜」该跑哪批 ——
    16/17→A  18/19→B  20→D  21→E
  21:00 的 E(回测) cron 于 21:07 触发时，**完全不管 B(选股)/D(汇总) 跑没跑**，
  于是拿凌晨的陈旧数据去跑回测；而 16:40/18:10/20:00 三轮若被静默跳过（假成功），
  整晚就只剩一个毫无意义的回测 —— 这就是「最终推荐被回退 / E 抢跑」的机制。
  旧逻辑「按小时」隐含假设：定时器一定准时且上游一定成功。现实两条都不成立
  （GHA cron 实测延迟 4h；闸门时区 bug 让三轮静默跳过）。

■ 新逻辑（本脚本）
  1) 显式 --explicit-stage（人工应急/测试）→ 采纳，但必须过「上游就绪」闸门；
  2) 未显式 → 「缺什么跑什么」：
       A 未就绪             → A
       A就绪 且 B未就绪(≥18) → B
       B就绪 且 D未就绪(≥20) → D
       D就绪 且 E未就绪(≥21) → E
       全就绪 / 未到时段      → NONE（空转，真成功，不是假成功）
  3) 上游未就绪 → stage_ok=false → 调用方**必须红灯**，严禁静默跳过（杜绝假成功）。

■ 就绪判据：读文件内容里的 update_time（不吃 git checkout 的 mtime）
  今日盘后 = update_time 的日期 == 目标交易日 且 小时 >= 16。

输出（stdout，key=value，供 GitHub Actions $GITHUB_OUTPUT 消费）：
  target_stage=A|B|D|E|NONE
  stage_ok=true|false
  ready_A / ready_B / ready_D / ready_E   （如 2/3）
  reason=<人类可读说明>
  detail=<各文件实测值，便于排障>
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

# ── 就绪判据：(至少命中项数, [代表性产物清单]) ──────────────────────────────
#   A 采集批：龙虎榜(16:30后) / 板块相对强度 / 个股档案
#   B 选股批：三模块与 workflow step9「静默闸门」口径**必须一致**（三模块 3/3），
#            否则会出现「闸门说已产出而这里说未就绪」的自相矛盾。
#   D 汇总批：最终推荐
#   E 回测批：回测自身产物（前置仍是 D 就绪）
READY_SPEC: dict[str, tuple[int, list[str]]] = {
    "A": (2, ["data/LHB_DATA.js", "raw_data/sector_rs.json", "raw_data/stock_profile.json"]),
    "B": (3, ["data/TRIPLE_CONSENSUS.js", "data/FOUR_VOLUME.js", "data/CRDS_CARD_DATA.js"]),
    "D": (1, ["data/FINAL_RECOMMEND_DATA.js"]),
    "E": (1, ["data/CRDS_BACKTEST.js", "data/BACKTEST_TDX.js"]),
}

# ── 各批「最早允许开跑」的 CST 小时（盘后数据齐备时间）─────────────────────
MIN_HOUR: dict[str, int] = {"A": 16, "B": 18, "D": 20, "E": 21}

# ── 各批的「上游」——上游不就绪则拒绝开跑（顺序闸门）────────────────────────
PREREQ: dict[str, str | None] = {"A": None, "B": "A", "D": "B", "E": "D"}

# 盘后产物的判定小时下限
POST_CLOSE_HOUR = 16

_UT_RE = re.compile(r'"update_time"\s*:\s*"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2})')
_DATE_RE = re.compile(r'"data_date"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')


def read_ut(root: str, rel: str):
    """读产物 update_time → (YYYY-MM-DD, hour)；只有 data_date 时 hour 视为 23（宽松）。"""
    path = os.path.join(root, rel)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(6000)
    except OSError:
        return None
    m = _UT_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", int(m.group(4))
    m = _DATE_RE.search(head)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 23
    return None


def check_ready(root: str, stage: str, today: str) -> tuple[bool, str, str]:
    """返回 (是否就绪, '命中/总数', 明细)。"""
    need, items = READY_SPEC[stage]
    hit = 0
    parts = []
    for it in items:
        r = read_ut(root, it)
        if r and r[0] == today and r[1] >= POST_CLOSE_HOUR:
            hit += 1
            parts.append(f"{os.path.basename(it)}=OK({r[0]} {r[1]:02d})")
        elif r:
            parts.append(f"{os.path.basename(it)}=STALE({r[0]} {r[1]:02d})")
        else:
            parts.append(f"{os.path.basename(it)}=MISS")
    return hit >= need, f"{hit}/{len(items)}", " ".join(parts)


def decide(root: str, today: str, hh: int, explicit: str, bypass: bool):
    ready: dict[str, tuple[bool, str, str]] = {
        s: check_ready(root, s, today) for s in READY_SPEC
    }

    def ready_out() -> dict[str, str]:
        return {f"ready_{s}": ready[s][1] for s in ("A", "B", "D", "E")}

    # ── 1) 显式 stage（人工应急）─────────────────────────────────────────
    if explicit in ("A", "B", "D", "E"):
        pre = PREREQ[explicit]
        if bypass:
            return explicit, True, f"显式{explicit}（bypass_stage_gate 强制放行）", ready_out()
        if pre is None:
            return explicit, True, f"显式{explicit}（最上游，无前置）", ready_out()
        if ready[pre][0]:
            return explicit, True, f"显式{explicit}，前置 {pre} 就绪({ready[pre][1]})", ready_out()
        return (
            explicit,
            False,
            f"⛔ 显式{explicit} 但前置 {pre} 未就绪({ready[pre][1]}) —— 拒绝开跑，否则将用陈旧数据算出假新鲜产物",
            ready_out(),
        )

    # ── 2) 自愈：「缺什么跑什么」────────────────────────────────────────
    if not ready["A"][0] and hh >= MIN_HOUR["A"]:
        return "A", True, f"A 未就绪({ready['A'][1]}) → 跑采集批", ready_out()
    if ready["A"][0] and not ready["B"][0] and hh >= MIN_HOUR["B"]:
        return "B", True, f"A就绪 B未就绪({ready['B'][1]}) → 跑选股批", ready_out()
    if ready["B"][0] and not ready["D"][0] and hh >= MIN_HOUR["D"]:
        return "D", True, f"B就绪 D未就绪({ready['D'][1]}) → 跑汇总批", ready_out()
    if ready["D"][0] and not ready["E"][0] and hh >= MIN_HOUR["E"]:
        return "E", True, f"D就绪 E未就绪({ready['E'][1]}) → 跑回测批", ready_out()

    allok = all(ready[s][0] for s in READY_SPEC)
    why = "全部批次产物已就绪" if allok else "未到该批最早时段（等下一轮触发）"
    return "NONE", True, f"{why} → 空转（真成功）", ready_out()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--today", default="", help="目标交易日 YYYY-MM-DD；留空=按 CST 现时（凌晨归前一自然日）")
    ap.add_argument("--hour", type=int, default=-1, help="CST 小时；留空自动算")
    ap.add_argument("--explicit-stage", default="")
    ap.add_argument("--bypass", action="store_true")
    ap.add_argument("--out", default="", help="写入文件，默认 stdout")
    a = ap.parse_args()

    now_cst = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    hh = a.hour if a.hour >= 0 else now_cst.hour
    if a.today:
        today = a.today
    else:
        # 凌晨(00:00-05:59)归属前一自然日 —— 与 workflow step9 口径一致
        base = now_cst - dt.timedelta(days=1) if hh < 6 else now_cst
        today = base.strftime("%Y-%m-%d")

    explicit = (a.explicit_stage or "").strip().upper()
    target, ok, reason, rdy = decide(a.root, today, hh, explicit, a.bypass)

    lines = [
        f"target_stage={target}",
        f"stage_ok={'true' if ok else 'false'}",
        f"today={today}",
        f"cst_hour={hh}",
        f"reason={reason}",
    ]
    for k, v in rdy.items():
        lines.append(f"{k}={v}")
    det = " | ".join(
        f"{s}:{check_ready(a.root, s, today)[2]}" for s in ("A", "B", "D", "E")
    )
    lines.append(f"detail={det}")
    body = "\n".join(lines)

    if a.out:
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(body + "\n")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
