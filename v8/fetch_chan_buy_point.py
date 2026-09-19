# -*- coding: utf-8 -*-
"""
【本机侧】ima「缠论买点每日推荐」全文快照生成器（阿狸咪的工程师 · 2026-09-19）

背景：与「强势跟踪」同源同构 —— 知识库分享页访客视角只拿 ~290 字截断，
      必须由有登录态的本机经连接器取全文，落 raw_data 快照，云端再解析。

水源：知识库 7500816604757970（创建者 梧谷枫灯）
      目录 folder_7506360161825717「缠论买点每日推荐」
      实测 2 篇：2026.9.16（38 只）/ 2026-09-17（17 只）

本脚本做的事（**幂等**）：
  1) 读本地已有的「取回全文」（_holdq/_chan_*.md，由连接器 fetch_media_content 落盘）
     —— 也可由 --in 指定任意全文文件
  2) 解析出结构化信号（代码/名称/走势类型/买点判定）
  3) 写 raw_data/chan_buy_point_full.md（原文）+ .json（meta）
     + raw_data/chan_buy_point_signals.json（信号账本：{code, name, signal_date, point}）

⚠️ 本脚本**不联网**（取全文那一步由连接器完成）；它只做落盘与解析，
    这样本机/云端都能跑，且可被 CI 复用。

用法：
  python v8/fetch_chan_buy_point.py --in _chan_0916.md --date 2026-09-16
  python v8/fetch_chan_buy_point.py --from-dir <目录>   # 批量
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"

SNAPSHOT_MD = RAW / "chan_buy_point_full.md"
SNAPSHOT_META = RAW / "chan_buy_point_full.json"
SIGNALS_JSON = RAW / "chan_buy_point_signals.json"

KB_ID = "7500816604757970"
KB_NAME = "强势股跟踪"
KB_CREATOR = "梧谷枫灯"
FOLDER_ID = "folder_7506360161825717"
FOLDER_NAME = "缠论买点每日推荐"


def _now():
    return datetime.now(CST)


def parse_chan_report(text: str):
    """解析缠论买入筛选报告 → (signals, meta)

    signals: [{"code","name","trend","point","note"}]
    表结构（实测）：|股票代码|名称|当前走势类型|买卖点判定|买入说明|
    """
    signals = []
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        code = cells[0]
        # 只认 6 位纯数字（过滤表头 / 分隔线 / 推荐榜的排名数字）
        if not re.fullmatch(r"\d{6}", code):
            continue
        signals.append({
            "code": code,
            "name": cells[1],
            "trend": cells[2],
            "point": cells[3],
            "note": cells[4] if len(cells) > 4 else "",
        })
    # 标题里的日期：优先 "# 盘后选股缠论买入筛选报告（2026-09-17）" / "# 2026.9.16缠论买入筛选报告"
    data_date = None
    m = re.search(r"(20\d{2})[-.](\d{1,2})[-.](\d{1,2})", text)
    if m:
        data_date = "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # 股票池/候选数（源方自述，用于对账）
    pool = None
    m2 = re.search(r"股票池[：:]\s*(\d+)\s*只", text)
    if m2:
        pool = int(m2.group(1))
    m3 = re.search(r"共\s*(\d+)\s*只候选", text)
    if pool is None and m3:
        pool = int(m3.group(1))
    # 买入明细条数（源方自述）
    claimed = None
    m4 = re.search(r"买入明细[（(]\s*(\d+)\s*只", text)
    if m4:
        claimed = int(m4.group(1))
    return signals, {"data_date": data_date, "pool": pool, "claimed": claimed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=None, help="单篇全文 md 路径")
    ap.add_argument("--date", default=None, help="信号日 YYYY-MM-DD（--in 时用，可省自动识别）")
    ap.add_argument("--from-dir", default=None, help="批量：目录内全部全文 md")
    ap.add_argument("--title", default="缠论买入筛选报告")
    ap.add_argument("--media-id", default=None)
    args = ap.parse_args()

    docs = []
    if args.inp:
        p = Path(args.inp)
        if not p.exists():
            print("❌ 文件不存在:", p)
            return 2
        docs.append((p, args.date))
    elif args.from_dir:
        d = Path(args.from_dir)
        for p in sorted(d.glob("*.md")):
            docs.append((p, None))
    else:
        print("❌ 需指定 --in 或 --from-dir")
        return 2

    all_sig = []
    metas = []
    merged_md = []
    for p, force_date in docs:
        text = p.read_text(encoding="utf-8")
        sig, meta = parse_chan_report(text)
        dd = force_date or meta["data_date"]
        print("📄 %s  解析 %d 条  信号日=%s  源自述买入=%s 池=%s" % (
            p.name, len(sig), dd, meta["claimed"], meta["pool"]))
        if meta["claimed"] is not None and meta["claimed"] != len(sig):
            print("   ⚠️ 源自述 %d 条 ≠ 实解析 %d 条（差 %d）—— 记入 coverage，不掩盖"
                  % (meta["claimed"], len(sig), meta["claimed"] - len(sig)))
        for s in sig:
            s["signal_date"] = dd
            all_sig.append(s)
        metas.append({
            "file": p.name, "data_date": dd, "rows_parsed": len(sig),
            "claimed": meta["claimed"], "pool": meta["pool"],
        })
        merged_md.append(text)

    # 去重（同 code 同 signal_date 视为一条）
    seen = set()
    uniq = []
    for s in all_sig:
        k = (s["code"], s["signal_date"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s)
    uniq.sort(key=lambda x: (x["signal_date"], x["code"]))

    RAW.mkdir(parents=True, exist_ok=True)
    merged = "\n\n---\n\n".join(merged_md)
    SNAPSHOT_MD.write_text(merged, encoding="utf-8", newline="\n")
    meta = {
        "fetched_at": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "fetched_tz": "CST+8",
        "kb_id": KB_ID, "kb_name": KB_NAME, "kb_creator": KB_CREATOR,
        "folder_id": FOLDER_ID, "folder_name": FOLDER_NAME,
        "title": args.title,
        "media_id": args.media_id,
        "docs": metas,
        "rows_parsed": len(uniq),
        "source_chars": len(merged),
        "signal_dates": sorted({s["signal_date"] for s in uniq if s["signal_date"]}),
        "channel": "member-full-text-snapshot",
        "note": ("本快照由本机（有 ima 登录态）经知识连接器取**全文**后落盘；"
                 "云端 fetch_chan_buy_point.py 优先读它，缺失/过期自动回退访客通道。"),
    }
    SNAPSHOT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                             encoding="utf-8", newline="\n")
    SIGNALS_JSON.write_text(json.dumps({
        "update_time": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "raw_data/chan_buy_point_full.md",
        "card": "缠论买点",
        "method": "缠论三类买卖点（源方：日线前复权→包含处理→分型→笔→中枢→MACD背驰）",
        "market": "A股",
        "count": len(uniq),
        "signal_dates": sorted({s["signal_date"] for s in uniq if s["signal_date"]}),
        "signals": uniq,
    }, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print()
    print("✅ 落盘：")
    print("   %s  (%d 字符)" % (SNAPSHOT_MD.name, len(merged)))
    print("   %s" % SNAPSHOT_META.name)
    print("   %s  (%d 条信号)" % (SIGNALS_JSON.name, len(uniq)))
    print("   信号日:", meta["signal_dates"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
