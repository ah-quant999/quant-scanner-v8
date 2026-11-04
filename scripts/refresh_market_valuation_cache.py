#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# refresh_market_valuation_cache.py — market_valuation_cache.csv 月频估值表自动补齐（治本 2026-11-05）
#
# 根因：raw_data/sw_index_daily_cache/market_valuation_cache.csv 是手工维护的「全市场 PE/PB 月频原始表」
#       （列：date,pe,pb_w,pb_equal,pb_med；1997 起、约 347 行）。v8/gen_market_thermo.py 用其 pe 列
#       算 val10（10 年 PE 滚动分位）。该表末月一旦陈旧（如冻在 2026-09），val10 尾部出现 >1 个连续 None
#       → audit_market_thermo 判「预热后中断」FAIL → 推送停、站点冻结在旧日。
#
# 治本：本脚本在每日管线里，用 akshare 把该表「仅向后追加」最新完成的月末行（绝不重算旧行，保护 27 年
#       历史口径），使 val10 尾部永远只有「当月进行中」一个 None（审计口径内合法，月末自动补齐）。
#
# 数据源（已核实 akshare）：
#       pe       <- stock_market_pe_lg()   （'平均市盈率'，月频，1997-至今，含 ST/亏损扭曲，≈全市场均值）
#       pb_equal <- stock_a_all_pb()       （equalWeightAveragePB，等权 PB）
#       pb_med   <- stock_a_all_pb()       （middlePB，中位数 PB）
#       pb_w     <- 暂留空（无可靠加权 PB 单列源；不影响 val10，仅展示项）
#
# 健壮性（宁旧勿错）：
#       - 仅追加 last_month+1 .. current_month-1（当月视为进行中，不填，与审计「月末补齐」口径一致）。
#       - 严格校验：pe in [5,100]；与近 12 月均值偏离<40%（防列名错配污染口径）；pb in [0.3,15]；月份连续。
#       - 任一源失败 / 校验不过 -> 跳过该月（不写、不污染）；整轮无有效新行 -> 保持原文件、exit 0（不阻断管线）。
#       - 写盘后读回校验行数增加、末月正确；异常则撤销写盘恢复原文件。
#       - 本脚本只写本地磁盘；实际落库由上游 api_push_raw（PUSH_FILES 含本 CSV）统一提交 main。
#
# 用法：python scripts/refresh_market_valuation_cache.py

import os, sys, csv, io, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "raw_data", "sw_index_daily_cache", "market_valuation_cache.csv")
FIELDS = ["date", "pe", "pb_w", "pb_equal", "pb_med"]


def log(s):
    print("[refresh-val] " + s, flush=True)


def parse_month(s):
    # 'YYYY-MM' / 'YYYY-MM-DD' / 'YYYYMMDD' / Timestamp -> 'YYYY-MM'
    if s is None:
        return None
    try:
        t = str(s).strip()
        if len(t) >= 7 and "-" in t:
            y, m = t[:4], t[5:7]
        elif len(t) >= 8 and t.isdigit():
            y, m = t[:4], t[4:6]
        else:
            dt = datetime.datetime.strptime(t[:10], "%Y-%m-%d")
            y, m = dt.strftime("%Y"), dt.strftime("%m")
        y = int(y); m = int(m)
        if 1990 <= y <= 2100 and 1 <= m <= 12:
            return "%04d-%02d" % (y, m)
    except Exception:
        pass
    return None


def pick_col(df, *candidates):
    cols = [str(c).lower() for c in df.columns]
    for cand in candidates:
        cl = cand.lower()
        for i, c in enumerate(cols):
            if cl in c:
                return df.columns[i]
    return None


def fetch_pe_map():
    import akshare as ak
    df = ak.stock_market_pe_lg()
    col = pick_col(df, "平均市盈率", "市盈率", "pe")
    if col is None:
        return {}
    mp = {}
    for _, row in df.iterrows():
        m = parse_month(row.get("日期"))
        v = row.get(col)
        if m and v is not None:
            try:
                mp[m] = float(v)
            except Exception:
                pass
    return mp


def fetch_pb_map():
    import akshare as ak
    df = ak.stock_a_all_pb()
    ceq = pick_col(df, "equalweight", "等权")
    cmd = pick_col(df, "middle", "中位")
    if ceq is None and cmd is None:
        return {}
    mp = {}
    for _, row in df.iterrows():
        m = parse_month(row.get("date"))
        if not m:
            continue
        eqv = mdv = None
        try:
            if ceq is not None and row.get(ceq) is not None:
                eqv = float(row.get(ceq))
        except Exception:
            eqv = None
        try:
            if cmd is not None and row.get(cmd) is not None:
                mdv = float(row.get(cmd))
        except Exception:
            mdv = None
        if eqv is not None or mdv is not None:
            mp[m] = (eqv, mdv)
    return mp


def main():
    if not os.path.exists(CSV_PATH):
        log("CSV 不存在，跳过（宁旧勿错）")
        return 0
    with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        log("CSV 为空，跳过")
        return 0
    for r in rows:
        r["date"] = (r.get("date") or "").strip()
    existing = [r["date"] for r in rows if r["date"]]
    if not existing:
        log("无有效月份行，跳过")
        return 0
    last_month = existing[-1]

    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.datetime.now()
    cur_month = "%04d-%02d" % (now.year, now.month)
    if last_month >= cur_month:
        log("已是最新（last=%s, cur=%s），无需补齐" % (last_month, cur_month))
        return 0

    y, m = map(int, last_month.split("-"))
    targets = []
    while True:
        m += 1
        if m > 12:
            m = 1; y += 1
        cand = "%04d-%02d" % (y, m)
        if cand >= cur_month:
            break
        targets.append(cand)
    if not targets:
        log("无需补齐（last=%s 已贴近当月）" % last_month)
        return 0
    log("目标补齐月份：%s（last=%s, cur=%s）" % ("、".join(targets), last_month, cur_month))

    pe_map, pb_map = {}, {}
    try:
        pe_map = fetch_pe_map()
        log("PE 源：%d 个月观测" % len(pe_map))
    except Exception as e:
        log("WARN PE 源拉取失败（%s），本轮不补齐 pe" % e)
    try:
        pb_map = fetch_pb_map()
        log("PB 源：%d 个月观测" % len(pb_map))
    except Exception as e:
        log("WARN PB 源拉取失败（%s），pb 列留空" % e)

    hist_pe = []
    for r in rows[-24:]:
        try:
            hist_pe.append(float(r["pe"]))
        except Exception:
            pass
    trailing_avg = (sum(hist_pe) / len(hist_pe)) if hist_pe else None

    appended = []
    for mth in targets:
        pe = pe_map.get(mth)
        if pe is None:
            log("  WARN %s 无 PE 观测，跳过（不污染）" % mth)
            continue
        if not (5 <= pe <= 100):
            log("  WARN %s PE=%.2f 越界[5,100]，跳过" % (mth, pe))
            continue
        if trailing_avg and abs(pe - trailing_avg) / trailing_avg > 0.4:
            log("  WARN %s PE=%.2f 与近12月均值%.2f 偏离>40%%，疑列名错配，跳过" % (mth, pe, trailing_avg))
            continue
        pb_eq, pb_md = pb_map.get(mth, (None, None))
        rows.append({
            "date": mth,
            "pe": "%.2f" % pe,
            "pb_w": "",
            "pb_equal": ("%.2f" % pb_eq) if pb_eq is not None else "",
            "pb_med": ("%.2f" % pb_md) if pb_md is not None else "",
        })
        appended.append(mth)

    if not appended:
        log("本轮无有效新行，保持原文件（宁旧勿错）")
        return 0

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: (r.get(k) or "") for k in FIELDS})
    out = buf.getvalue()
    with io.open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(out)

    # 写回校验
    with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        chk = list(csv.DictReader(f))
    if len(chk) == len(rows) and chk[-1]["date"] == appended[-1]:
        log("OK 补齐 %d 个月：%s；末月=%s（原 %s）" % (len(appended), "、".join(appended), chk[-1]["date"], last_month))
        return 0
    # 校验失败：撤销
    log("ERROR 写回校验失败，撤销")
    buf2 = io.StringIO()
    w2 = csv.DictWriter(buf2, fieldnames=FIELDS, lineterminator="\n")
    w2.writeheader()
    for r in rows[:-len(appended)]:
        w2.writerow({k: (r.get(k) or "") for k in FIELDS})
    with io.open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(buf2.getvalue())
    return 1


if __name__ == "__main__":
    sys.exit(main())
