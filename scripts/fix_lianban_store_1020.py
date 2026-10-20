#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连板回测实证 store 毒数据一次性重建（2026-10-20 · 主人令「全部一劳永逸修复」）

【病灶实证】（三项交叉验证，集合比对全部 0 差异）：
  ① 东财 getTopicZTPool 对**未发布日期静默返回最新可用池**（实测请求 20261021/22
     均返回 10-20 池；过去非交易日返空）⇒ 午夜看门狗派发（工作日 00:07-07:52 每
     15 分）与周末 09:00 周度档按**运行日**把上一交易日池错录成当日信号；
  ② LIANBAN_WINRATE 幂等闸门原按 last_run_date（运行日）判重 ⇒ 早班盖了当日的章
     ⇒ 当晚 15:30/17:20/18:20/19:20 全被跳过 ⇒ 当日真池永远录不上；
  ③ store 实测：board_date 10-17/18/19 的各 58 条与 **10-16（周五）真池**逐一
     集合比对 0 差异（同一池错录 3 次）；10-20 的 44 条与 **10-19（周一）真池**
     0 差异。10-17/18 为周六/周日，新浪日K无该日 ⇒ 218 条全部永远无法成熟。

【重建口径】毒 pending 全清（远端实证 matured/expired/dropped 均为 0，无有效成果
  可保留）；按**真实涨停池**重录 feature 上线窗口内三个交易日：
    2026-10-16（58 条）= 被错录成 10-17/18/19 的那批真身
    2026-10-19（44 条）= 被错录成 10-20 的那批真身
    2026-10-20（48 条）= 当晚被闸门漏录的真池（15:00 已定型，19:55 实测在库）
  录入口径与 v8/lianban_winrate.update() 完全一致（剔 ST / lbc∈{1,2} / dedup /
  type 判定同源，不写第二套实现）；成熟统计仍从 0 起按 T+5 自然推进——不补插、
  不篡改任何历史结论（10-11 回测口径铁律：未走满样本不计入）。

【防再犯（代码侧三连修，本脚本只治已发生的数据）】
  · cloud_fetch_v8.f_lianban_winrate：时段+交易日闸门 / 信号覆盖日判重
    （last_signal_date，替代 last_run_date）/ 今日池新鲜度校验（与上一交易日池
    全等=未发布）/ 过期补录（缺信号日按真实日期补录）；
  · cloud_fetch_v8.f_first_board_alert：同源闸门（前哨卡同根因假刷新）；
  · v8/lianban_winrate：signal_dates/last_signal_date 字段 + 行级 board_date。

运行：python scripts/fix_lianban_store_1020.py [--dry-run]
产出：raw_data/lianban_winrate.json + data/LIANBAN_WINRATE.js（与抓取链同格式）
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CST = ZoneInfo("Asia/Shanghai")

# feature 上线窗口内、有真实涨停池可录的三个交易日（错录链实证后的真身映射）
REPAIR_DATES = ["2026-10-16", "2026-10-19", "2026-10-20"]
# 重建前毒 store 的实测口径（防呆：对不上就拒绝执行，禁默默写错）
EXPECT_POISON = {"signals_total": 218, "matured_total": 0, "expired": 0,
                 "dropped_yiziban": 0,
                 "pending_by_date": {"2026-10-17": 58, "2026-10-18": 58,
                                     "2026-10-19": 58, "2026-10-20": 44}}


def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, str(ROOT / rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只审计不写盘")
    args = ap.parse_args()

    lw = _load("lianban_winrate", "v8/lianban_winrate.py")
    cf = _load("cloud_fetch_v8", "cloud_fetch_v8.py")

    # ── ① 读现store 做防呆校验（毒口径对得上才允许重建）──
    store_path = ROOT / "raw_data" / "lianban_winrate.json"
    base = json.loads(store_path.read_text(encoding="utf-8"))
    from collections import Counter
    poison_now = {
        "signals_total": int(base.get("signals_total") or 0),
        "matured_total": int(base.get("matured_total") or 0),
        "expired": int(base.get("expired") or 0),
        "dropped_yiziban": int(base.get("dropped_yiziban") or 0),
        "pending_by_date": dict(sorted(Counter(
            p.get("board_date") for p in base.get("pending") or []).items())),
    }
    print("现 store 口径:", json.dumps(poison_now, ensure_ascii=False))
    for k, v in EXPECT_POISON.items():
        if poison_now.get(k) != v:
            raise SystemExit(
                f"防呆失败：{k} 期望 {v} 实际 {poison_now.get(k)}——store 已被别轮改动，"
                f"请人工核对后再决定是否重建（禁默默覆盖）")
    print("防呆校验通过：确认为 2026-10-20 错录链毒 store（无成熟成果，可安全重建）")

    # ── ② 按真实池重录（与抓取链同一 _zt_pool_rows，禁第二套取数实现）──
    st = lw.skeleton()
    total = {}
    for d in REPAIR_DATES:
        rows = cf._zt_pool_rows(d.replace("-", ""))
        if not rows:
            raise SystemExit(f"{d} 涨停池取数为空——东财数据异常，终止重建（禁写半成品）")
        for r in rows:
            r["board_date"] = d
        st = lw.update(st, rows)          # 同源录入口径（剔ST/dedup/type 判定）
        total[d] = len(rows)
        print(f"  ✅ {d}: 录入 {len(rows)} 条（lbc∈{{1,2}}，已剔 ST/去重）")

    # ── ③ 重建后审计（全部硬断言，不过即终止）──
    sd = st.get("signal_dates") or {}
    assert st["signals_total"] == sum(total.values()) == 150, (st["signals_total"], total)
    assert sd == {d: n for d, n in total.items()}, sd
    assert st["first_date"] == "2026-10-16", st["first_date"]
    assert st["last_signal_date"] == "2026-10-20", st["last_signal_date"]
    assert len(st["pending"]) == 150 and st["matured_total"] == 0
    assert all((g or {}).get("n", 0) == 0 for g in st["groups"].values())
    assert all(p["board_date"] in REPAIR_DATES for p in st["pending"])
    st["first_mature_eta"] = cf._lianban_first_eta(st, lw)
    print(f"重建审计通过：signals=150  first_date=10-16  信号覆盖={sorted(sd)}  "
          f"在途=150  成熟=0  最早出数日(预计)={st['first_mature_eta']}")

    if args.dry_run:
        print("--dry-run：不写盘")
        return

    # ── ④ 落盘（raw 紧凑 JSON 与 data/*.js 均与抓取链/update_v8 同格式）──
    now_s = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    st["update_time"] = now_s
    store_path.write_text(cf._safe_json_dumps(st), encoding="utf-8")
    js_path = ROOT / "data" / "LIANBAN_WINRATE.js"
    payload = dict(st)
    payload["republish_time"] = now_s
    js_path.write_text("window.LIANBAN_WINRATE = " + cf._safe_json_dumps(payload) + ";\n",
                       encoding="utf-8")
    print(f"已写盘：raw_data/lianban_winrate.json（{store_path.stat().st_size}B）+ "
          f"data/LIANBAN_WINRATE.js（{js_path.stat().st_size}B）")
    print("下一步：git 提交推送（须早于次日 15:30 post_close 轮，让 runner 拿到新基线）；"
          "前端 index.html 连板卡同步改诚实空态（在途/预计出数日）。")


if __name__ == "__main__":
    main()
