#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股债性价比 · 温度计生成器（2026-11-19 一劳永逸根治）
====================================================
根因：data/EQBOND_ATTRACTION.js 自 2026-11-18 创建起只有 1 个手工提交，
      仓库内没有任何生成脚本 / workflow，因此永远停在 2026-11-17。

本脚本全部用真实公开数据重算，不沿用旧值、不伪造分布：
  · 沪深300 PE_TTM / PB：akshare stock_index_pe_lg / stock_index_pb_lg（理杏仁，日频长历史）
  · 沪深300 股息率：akshare index_value_csindex("000300")（中证指数官方 indicator.xls）
  · 中国 10Y 国债收益率：akshare bond_zh_us_rate()（与 MACRO_DATA 同源）
  · 股债比价：沪深300收盘 / 中债国债指数(000012)收盘，长期历史分位

产出：data/EQBOND_ATTRACTION.js → window.EQBOND_ATTRACTION
刷新：.github/workflows/v8_eqbond_attraction.yml，交易日 19:20 CST。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "EQBOND_ATTRACTION.js"
CST = timezone(timedelta(hours=8))


def log(msg):
    print("[eqbond] " + str(msg), flush=True)


def num(v):
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def dstr(v):
    s = str(v).strip().replace("/", "-")
    return s[:10]


def pick_col(df, *candidates):
    cols = [str(c).lower() for c in df.columns]
    for cand in candidates:
        key = cand.lower()
        for i, c in enumerate(cols):
            if key in c:
                return df.columns[i]
    return None


def to_map(df, date_candidates, value_candidates):
    dc = pick_col(df, *date_candidates)
    vc = pick_col(df, *value_candidates)
    if dc is None or vc is None:
        raise RuntimeError("列缺失 date=%s value=%s cols=%s" % (dc, vc, list(df.columns)[:12]))
    out = {}
    for _, row in df.iterrows():
        d = dstr(row.get(dc))
        v = num(row.get(vc))
        if len(d) == 10 and v is not None:
            out[d] = v
    if not out:
        raise RuntimeError("空序列 value=%s" % vc)
    return out


def pct_rank(values, current):
    vals = sorted(v for v in values if v is not None)
    if not vals or current is None:
        return None
    below = sum(1 for v in vals if v < current)
    eq = sum(1 for v in vals if v == current)
    return round((below + 0.5 * eq) / len(vals) * 100, 2)


def last_n_dates(maps, n=1000):
    if not maps:
        return []
    common = set(maps[0])
    for m in maps[1:]:
        common &= set(m)
    return sorted(common)[-n:]


def value_at_or_before(m, day):
    keys = [k for k in m if k <= day and m[k] is not None]
    return m[max(keys)] if keys else None


def fetch_csindex_dy():
    """直接读中证指数官方 indicator.xls；绕过 akshare 版本导出差异。"""
    import io
    import pandas as pd
    import requests
    url = ("https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/"
           "000300indicator.xls")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=45)
    r.raise_for_status()
    try:
        df = pd.read_excel(io.BytesIO(r.content))
    except Exception:
        df = pd.read_html(io.BytesIO(r.content))[0]
    cols = ["日期", "指数代码", "指数中文全称", "指数中文简称", "指数英文全称", "指数英文简称",
            "市盈率1", "市盈率2", "股息率1", "股息率2"]
    if len(df.columns) >= len(cols):
        df.columns = cols[:len(df.columns)] + list(df.columns[len(cols):])
    else:
        df.columns = cols[:len(df.columns)]
    return df


def fetch_index_close(symbol, canonical):
    """stock_zh_index_daily 与 index_zh_a_hist 双路取指数收盘，任一成功即可。"""
    import akshare as ak
    errors = []
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        m = to_map(df, ("date", "日期"), ("close", "收盘"))
        log("%s close via stock_zh_index_daily: %d 行" % (canonical, len(m)))
        return m
    except Exception as e:
        errors.append("stock_zh_index_daily: %s" % e)
    try:
        code = symbol[2:] if symbol.startswith("sh") else symbol
        df = ak.index_zh_a_hist(symbol=code, period="daily")
        m = to_map(df, ("日期", "date"), ("收盘", "close"))
        log("%s close via index_zh_a_hist: %d 行" % (canonical, len(m)))
        return m
    except Exception as e:
        errors.append("index_zh_a_hist: %s" % e)
    raise RuntimeError("; ".join(errors))


def main():
    try:
        import akshare as ak
    except ImportError:
        log("akshare 未安装")
        return 1

    try:
        pe = to_map(ak.stock_index_pe_lg(symbol="沪深300"), ("日期", "date"), ("滚动市盈率", "pe_ttm"))
        pb = to_map(ak.stock_index_pb_lg(symbol="沪深300"), ("日期", "date"), ("市净率", "pb"))
        cs = fetch_csindex_dy()
        dy1 = to_map(cs, ("日期", "date"), ("股息率1", "dv1", "dividend1"))
        dy2 = to_map(cs, ("日期", "date"), ("股息率2", "dv2", "dividend2"))
        y10 = to_map(ak.bond_zh_us_rate(), ("日期", "date"), ("中国国债收益率10年", "中国10年", "china_10y"))
        px = fetch_index_close("sh000300", "沪深300")
        bd = fetch_index_close("sh000012", "中债国债指数")
    except Exception as e:
        log("数据抓取失败：%s" % e)
        return 2

    # 以全部核心序列都覆盖到的最近交易日为口径日（宁旧勿错，绝不拼未来函数）
    latest = [max(pe), max(pb), max(dy1), max(y10), max(px), max(bd)]
    as_of = min(latest)

    pe_ttm = value_at_or_before(pe, as_of)
    pb_lf = value_at_or_before(pb, as_of)
    dy_ttm = value_at_or_before(dy1, as_of)
    dy_static = value_at_or_before(dy2, as_of)
    y10_v = value_at_or_before(y10, as_of)
    px_v = value_at_or_before(px, as_of)
    bd_v = value_at_or_before(bd, as_of)

    if not all(v and v > 0 for v in (pe_ttm, pb_lf, dy_ttm, y10_v, px_v, bd_v)):
        log("核心数值缺失/非正：pe=%s pb=%s dy=%s y10=%s px=%s bd=%s" %
            (pe_ttm, pb_lf, dy_ttm, y10_v, px_v, bd_v))
        return 3

    erp = round(100.0 / pe_ttm - y10_v, 4)
    spread = round(dy_ttm - y10_v, 4)
    ratio = round(px_v / bd_v, 6)

    # 分位：近 1000 个共同交易日；越高=权益相对债券越便宜（前端红涨绿跌口径）
    erp_dates = last_n_dates((pe, y10))
    erp_hist = [100.0 / pe[d] - y10[d] for d in erp_dates]
    spr_dates = last_n_dates((dy1, y10))
    spr_hist = [dy1[d] - y10[d] for d in spr_dates]
    ratio_dates = last_n_dates((px, bd))
    ratio_hist = [px[d] / bd[d] for d in ratio_dates]

    pe_pct = pct_rank([pe[d] for d in sorted(pe)[-1000:]], pe_ttm)
    pb_pct = pct_rank([pb[d] for d in sorted(pb)[-1000:]], pb_lf)
    dy_pct = pct_rank([dy1[d] for d in sorted(dy1)[-1000:]], dy_ttm)
    y10_pct = pct_rank([y10[d] for d in sorted(y10)[-1000:]], y10_v)
    erp_pct = pct_rank(erp_hist, erp)
    spread_pct = pct_rank(spr_hist, spread)
    ratio_pct = pct_rank(ratio_hist, ratio)

    vals = [pe_pct, pb_pct, dy_pct, y10_pct, erp_pct, spread_pct, ratio_pct]
    if any(v is None for v in vals):
        log("分位计算失败：%s" % vals)
        return 4

    tail_dates = sorted(set(erp_dates) & set(spr_dates))[-10:]
    history_tail = []
    for d in tail_dates:
        history_tail.append({
            "date": d,
            "erp": round(100.0 / pe[d] - y10[d], 3),
            "spread": round(dy1[d] - y10[d], 3),
        })

    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    out = {
        "data_date": as_of,
        "update_time": now,
        "source": "理杏仁沪深300 PE/PB（akshare）/ 中证指数官方000300股息率 / akshare中债10Y / 沪深300与中债国债指数比价",
        "sample_size": max(len(erp_dates), len(spr_dates)),
        "pe_ttm": round(pe_ttm, 4),
        "pe_pct": pe_pct,
        "pb_lf": round(pb_lf, 4),
        "pb_pct": pb_pct,
        "dy_ttm": round(dy_ttm, 4),
        "dy_pct": dy_pct,
        "dy_static": round(dy_static, 4) if dy_static else None,
        "y10": round(y10_v, 4),
        "y10_pct": y10_pct,
        "erp": erp,
        "erp_pct": erp_pct,
        "spread": spread,
        "spread_pct": spread_pct,
        "ratio": ratio,
        "ratio_pct": ratio_pct,
        "history_tail": history_tail,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.EQBOND_ATTRACTION = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")

    log("已写入 %s" % OUT)
    log("data_date=%s pe=%.2f pb=%.3f dy=%.2f y10=%.3f erp=%.2f(%s%%) spread=%.2f(%s%%) ratio=%.2f(%s%%) sample=%d"
        % (as_of, pe_ttm, pb_lf, dy_ttm, y10_v, erp, erp_pct, spread, spread_pct, ratio, ratio_pct,
           out["sample_size"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
