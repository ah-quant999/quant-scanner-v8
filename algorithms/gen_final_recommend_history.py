# -*- coding: utf-8 -*-
"""
最终推荐 · 每日 Top3 历史归档（2026-10-22 主人令「最终推荐的历史记录怎么没了？
我要记录每天前3名」）

背景（根因）：
  final_recommend.py 每天**整体覆盖**写 raw_data/final_recommend.json ⇒ 主站最终推荐
  卡只能看到当日 Top3，历史不可见。虽另有 raw_data/history/final_recommend_YYYYMMDD.json
  dated 快照（37 份，git 已跟踪），但那是**算法侧**归档，没有面向主人的「每天前 3 名」清单。

本脚本（纯汇总，不改算法口径）：
  读 raw_data/history/final_recommend_*.json（真实每日选股 dated 快照）
  → 逐日取 Top3（code/name/close/close_date/final_score/sources）
  → 写 raw_data/final_recommend_history.json（按日期键，滚动保留最近 N 天）
  → 写 data/FINAL_RECOMMEND_HISTORY.js（window.FINAL_RECOMMEND_HISTORY）

口径对齐 gen_final_recommend_backtest.py 的 _attributed_date：
  update_time 小时 < 9 ⇒ 归前一自然日（盘后定稿落次日交易日的口径）。
  同一归因日多份归档只认最新（update_time 最大）——旧版视为被刷新替代。

保留天数：默认 120 天（覆盖约半年，够主人翻阅；文件体积可控）。
"""
import os
import sys
import json
import glob
import datetime as dt

REPO = os.environ.get("V8_ROOT") or r"E:/qs_workspaces/quant-scanner-v8"
RAW = os.path.join(REPO, "raw_data")
DATA = os.path.join(REPO, "data")
HIST = os.path.join(RAW, "history")
OUT_RAW = os.path.join(RAW, "final_recommend_history.json")
OUT_JS = os.path.join(DATA, "FINAL_RECOMMEND_HISTORY.js")
KEEP_DAYS = 120
N_TOP = 3


def _log(m=""):
    print(m, flush=True)


def attributed_date(update_time, file_date):
    """与 gen_final_recommend_backtest.py._attributed_date 同源口径。"""
    try:
        h = int(str(update_time)[11:13]) if update_time and len(str(update_time)) >= 13 else 99
    except Exception:
        h = 99
    d = dt.date.fromisoformat(file_date)
    if h < 9:
        d = d - dt.timedelta(days=1)
    return d.isoformat()


def collect():
    """读全部 dated 快照 → {归因日: {top3:[...], update_time, file}}，同日取最新版。"""
    by_day = {}
    files = sorted(glob.glob(os.path.join(HIST, "final_recommend_*.json")))
    for p in files:
        base = os.path.basename(p)[len("final_recommend_"):-len(".json")]
        try:
            fd = dt.date.fromisoformat(base).isoformat()
        except Exception:
            continue
        try:
            d = json.loads(open(p, encoding="utf-8").read())
        except Exception as e:
            _log("  ⚠️ %s 解析失败: %s" % (os.path.basename(p), e))
            continue
        ut = str(d.get("update_time") or "")
        ad = attributed_date(ut, fd)
        prev = by_day.get(ad)
        if prev and prev["update_time"] >= ut:
            continue   # 旧版被刷新替代
        stocks = []
        for s in (d.get("stocks") or [])[:N_TOP]:
            c = str(s.get("code") or "").strip().lstrip(".")
            if not c:
                continue
            stocks.append({
                "rank": s.get("rank"),
                "code": c,
                "name": s.get("name") or "",
                "close": s.get("close"),
                "close_date": s.get("close_date"),
                "final_score": s.get("final_score"),
                "resonance": s.get("resonance"),
                "sources": s.get("sources") or [],
            })
        if not stocks:
            continue
        by_day[ad] = {
            "date": ad,
            "update_time": ut[:19],
            "file": os.path.basename(p),
            "degraded": bool(d.get("data_degraded")),
            "top3": stocks,
        }
    return by_day


def main():
    _log("=" * 70)
    _log("  最终推荐 · 每日 Top3 历史归档  %s"
         % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _log("=" * 70)
    by_day = collect()
    if not by_day:
        _log("[error] 无 dated 归档可汇总，退出")
        return 1
    days = sorted(by_day.keys())
    if len(days) > KEEP_DAYS:
        drop = set(days[:len(days) - KEEP_DAYS])
        for d in drop:
            by_day.pop(d, None)
        days = days[len(days) - KEEP_DAYS:]
    _log("归因日 %d 天：%s → %s（保留最近 %d 天）" % (len(days), days[0], days[-1], KEEP_DAYS))

    out = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "card": "最终推荐 · 每日 Top3 历史",
        "method": "真实每日选股 dated 快照汇总（raw_data/history/final_recommend_YYYYMMDD.json）",
        "attribution_rule": "update_time 小时 < 9 归前一自然日；同一归因日多份归档只认最新",
        "n_top": N_TOP,
        "days": len(days),
        "date_from": days[0],
        "date_to": days[-1],
        "by_date": {d: by_day[d] for d in days},
    }
    with open(OUT_RAW, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _log("[ok] %s" % OUT_RAW)

    js = ("/* 最终推荐 · 每日 Top3 历史 — gen_final_recommend_history.py 产出 */\n"
          "window.FINAL_RECOMMEND_HISTORY = "
          + json.dumps(out, ensure_ascii=False, indent=2) + ";")
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    _log("[ok] %s (%d B)" % (OUT_JS, os.path.getsize(OUT_JS)))
    for d in days[-3:]:
        _log("  %s → %s" % (d, " / ".join(
            "%s %s" % (s["code"], s["name"]) for s in by_day[d]["top3"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
