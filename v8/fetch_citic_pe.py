# -*- coding: utf-8 -*-
"""
中信证券历史估值 fetcher（小九 cn 链 · baostock 数据源）
======================================================================
  - 目标：拉中信证券 (sh.600030) 2010-01-01 ~ 当前 PE/PB/PS TTM 时序
  - 输出：raw_data/citic_pe_history.json
  - 特性：
      1) baostock 字段：date, code, close, peTTM, pbMRQ, psTTM
      2) 日频，frequency='d', adjustflag='2' (前复权)
      3) 断点续跑：fetch_meta.json 记录 last_update，下次仅重拉增量
      4) 自适应：REPO/WORK/OUT 按仓库内/外自动判定
  - 触发：算法链（云端）每日 19:00；手动 `python v8/fetch_citic_pe.py`
  - 2026-09-07 主人令：为「中信 PE 极值温度计 + 历史回测」双卡供数
"""
import baostock as bs
import json, os, sys, datetime as dt, traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(REPO, "raw_data", "citic_pe_history.json")
META = os.path.join(REPO, "raw_data", "citic_pe_history.meta.json")

CODE       = "sh.600030"
START_DATE = "2010-01-01"
END_DATE   = dt.datetime.now().strftime("%Y-%m-%d")


def log(*a):
    print("[citic-pe-fetch]", *a, flush=True)


def fetch_range(start_date, end_date):
    """拉取 [start_date, end_date] 区间的 PE/PB 时序"""
    lg = bs.login()
    if lg.error_msg != "success":
        log("baostock login FAIL:", lg.error_msg)
        return None
    rs = bs.query_history_k_data_plus(
        CODE,
        "date,code,close,peTTM,pbMRQ,psTTM",
        start_date=start_date, end_date=end_date,
        frequency="d", adjustflag="2",
    )
    if rs.error_msg != "success":
        log("query FAIL:", rs.error_msg)
        bs.logout()
        return None
    rows = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    bs.logout()
    log(f"区间 {start_date}~{end_date} 拉取：{len(rows)} 行")
    return rows


def fetch_all():
    """一次性拉全量历史 PE TTM 时序（首跑 fallback）"""
    return fetch_range(START_DATE, END_DATE)


def normalize(rows):
    """baostock 原始 → JSON 结构化"""
    out = {
        "code": "600030",
        "name": "中信证券",
        "source": "baostock",
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": rows[0][0] if rows else None,
        "end_date": rows[-1][0] if rows else None,
        "row_count": len(rows),
        "data": [],
    }
    for r in rows:
        try:
            out["data"].append({
                "d": r[0],
                "c": float(r[2]) if r[2] else None,   # close
                "pe": float(r[3]) if r[3] else None,  # peTTM
                "pb": float(r[4]) if r[4] else None,  # pbMRQ
                "ps": float(r[5]) if r[5] else None,  # psTTM
            })
        except (ValueError, IndexError):
            continue
    return out


def main():
    log("REPO:", REPO)
    log("OUT :", OUT)

    # 🆕 2026-09-07 断点续跑：读 meta.last_date，若存在仅拉 last_date+1 ~ NOW。
    #   全仓每晚 ~1-3 个交易日新增（A股工作日），百毫秒内完成；首跑 fallback 16 年全量。
    existing = None
    last_date = None
    if os.path.exists(META):
        try:
            with open(META, "r", encoding="utf-8") as f:
                meta = json.load(f)
                last_date = meta.get("end_date")
                log(f"📌 meta.last_date={last_date}, row_count={meta.get('row_count')}")
        except Exception as e:
            log("⚠️ meta 读失败:", e)

    if last_date:
        # 增量模式：last_date + 1 天 ~ 今天（baostock 自然跳过周末/节假日）
        inc_start = (dt.datetime.strptime(last_date, "%Y-%m-%d") + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        if inc_start > END_DATE:
            log(f"✅ 已是最新（last_date={last_date} ≥ today={END_DATE}），跳过")
            return
        log(f"🔄 增量模式：{inc_start} ~ {END_DATE}")
        rows = fetch_range(inc_start, END_DATE)
        if not rows:
            log("❌ 增量无数据，退出")
            sys.exit(1)
        # 读已有 out 把增量并入
        with open(OUT, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_rows = []
        for d in existing["data"]:
            existing_rows.append([d["d"], "sh.600030", str(d.get("c") or ""), str(d.get("pe") or ""), str(d.get("pb") or ""), str(d.get("ps") or "")])
        rows = existing_rows + rows
        log(f"📦 现有 {len(existing_rows)} 行 + 增量 {len(rows) - len(existing_rows)} 行")
    else:
        # 首跑：16 年全量
        log("🚀 首跑全量模式：2010-01-01 ~ NOW")
        rows = fetch_all()
        if not rows:
            log("❌ 无数据，退出")
            sys.exit(1)

    out = normalize(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open(META, "w", encoding="utf-8") as f:
        json.dump({
            "last_update": out["update_time"],
            "row_count": out["row_count"],
            "end_date": out["end_date"],
        }, f, ensure_ascii=False, indent=2)
    log(f"✅ 写盘 {OUT} ({os.path.getsize(OUT)//1024} KB)")
    log(f"   {out['row_count']} 行, {out['start_date']} ~ {out['end_date']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("💥 异常:", e)
        traceback.print_exc()
        sys.exit(1)
