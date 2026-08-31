#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史龙虎榜回填脚本（v8 专用）
- 移植 stock-scanner/fetch_lhb.py v7 的席位分类口径：
    机构专用            -> 机构
    深股通/沪股通        -> 北向
    其余（游资/量化/未识别）-> 未识别（v8 当前数据口径：yz = 未识别 净额）
- 机游共振判定：机构净买>8000万 且 游资(未识别)净买>8000万
- 输出 raw_data/lhb_history.json，结构：
    {
      "update_time": "...",
      "range": ["2026-06-29","2026-08-01"],
      "backfill_days": 40,
      "2026-07-31": {"trading": true, "stocks":[...同 LHB_DATA 单日结构...], "summary":{...}},
      "2026-08-01": {"trading": false},   // 非交易日/无数据
      ...
    }
- 可续跑：已存在的日期会被跳过。
"""
import akshare as ak
import json
import time
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw_data", "lhb_history.json")
THRESHOLD = 8000  # 万，强买阈值
N_CALENDAR_DAYS = 55  # 回溯的日历天数（约 40 个交易日，覆盖 ~6 周）
# 🛡 2026-08-31：强制重抓窗口（自然日）。仅保留"当日"：
#   · 骨架数据（stocks>0 但 seats 全空）/ error 占位 / 空壳 已被 _is_real()
#     判为不完整 → 每轮自动重抓，无需靠本窗口兜底；
#   · 本窗口唯一不可替代的场景是"当日"——可能在龙虎榜发布前被抓过一次，
#     stocks 有值但席位不全，需要隔一段时间补全。
#   · 曾设 4 天，实测每轮 post_close 多花 4-12 分钟重复抓前 3 个交易日，
#     与 job 60 分钟预算（update_v8 单步已占 ~19 分钟）冲突 → 收窄为 1。
FORCE_REFRESH_DAYS = 1


def _load_lhb_seats():
    """加载席位库 out/lhb_seats.json（与算法端 fetch_lhb.py 同源）。缺失则回退空库。"""
    p = os.path.join(HERE, "out", "lhb_seats.json")
    if not os.path.exists(p):
        print("  ⚠️ out/lhb_seats.json 不存在，回退纯规则分类")
        return {"seats": [], "patterns": {}}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ 席位库读取失败: {e}")
        return {"seats": [], "patterns": {}}


def _classify_seat(seat_name, seats_db=None):
    """席位分类：机构专用→机构、深股通/沪股通→北向，其余按席位库模式匹配游资/量化，未命中→未识别。
    与算法端 fetch_lhb.py 口径一致，确保机游共振的「游资」= 游资+量化（剔除北向/未识别）。"""
    if not seat_name:
        return '未识别'
    if '机构专用' in seat_name:
        return '机构'
    if '深股通' in seat_name or '沪股通' in seat_name:
        return '北向'
    seats_db = seats_db or {}
    for s in seats_db.get("seats", []):
        if s.get("name") == seat_name:
            return s.get("type", "游资")
    for p in seats_db.get("patterns", {}).get("游资", []):
        if p in seat_name:
            return '游资'
    for p in seats_db.get("patterns", {}).get("量化", []):
        if p in seat_name:
            return '量化'
    return '未识别'


def _safe_float(v):
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if f != f else f  # NaN->0
    except Exception:
        return 0.0


def _parse_lhb_list_em(df):
    """东财龙虎榜列表 → 统一 stocks 结构（与 fetch_lhb.py 同口径）"""
    stocks = []
    seen = set()
    for _, row in df.iterrows():
        code = str(row.get('代码', '')).zfill(6)
        if code and code not in seen:
            seen.add(code)
            stocks.append({
                'code': code,
                'name': str(row.get('名称', '')),
                'price': _safe_float(row.get('最新价', 0)),
                'pct': _safe_float(row.get('涨跌幅', 0)),
                'amount': _safe_float(row.get('龙虎榜净买额', 0)),
                'reason': str(row.get('上榜原因', '')),
            })
    return stocks


def fetch_lhb_list(date_str, max_retry=4):
    """🛡 2026-08-31 一劳永逸：东财列表重试 + 新浪兜底。

    原实现单次裸调 ak.stock_lhb_detail_em：当日龙虎榜未发布 / 接口抖动时抛
    'NoneType' object is not subscriptable，直接被 main() 的 except 捕获并写成
    error 占位，再因 done 集合永不重试 → 共振日历当日永久空白。
    现改为：4 次指数退避重试 → 新浪列表兜底 → 仍空才返回 []。
    """
    for attempt in range(max_retry):
        try:
            df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
            if df is not None and len(df) > 0:
                return _parse_lhb_list_em(df)
            print(f"    东财列表返回空(第{attempt+1}/{max_retry}次)，重试...")
        except Exception as e:
            print(f"    东财列表异常(第{attempt+1}/{max_retry}次): {type(e).__name__}: {e}")
        if attempt < max_retry - 1:
            time.sleep(3 * (attempt + 1))
    # 兜底：新浪每日龙虎榜列表（无席位明细，保证不空白）
    try:
        df = ak.stock_lhb_detail_daily_sina(date=date_str)
        if df is not None and len(df) > 0:
            stocks, seen = [], set()
            for _, row in df.iterrows():
                code = str(row.get('股票代码', '')).zfill(6)
                if not code or code in seen:
                    continue
                seen.add(code)
                stocks.append({
                    'code': code,
                    'name': str(row.get('股票名称', '')),
                    'price': _safe_float(row.get('收盘价', 0)),
                    'pct': _safe_float(row.get('对应值', 0)),
                    'amount': 0.0,
                    'reason': str(row.get('指标', '')),
                })
            print(f"    新浪兜底列表：{len(stocks)} 只")
            return stocks
    except Exception as e:
        print(f"    新浪兜底失败: {type(e).__name__}: {e}")
    return []


def fetch_seat_detail(stocks, date_str, seats_db=None):
    """逐笔席位明细：合并买入/卖出页并按席位去重。seats_db=席位库（out/lhb_seats.json）。"""
    detail_map = {}
    for s in stocks:
        code = s['code']
        detail_map[code] = {}
        seen = set()
        for flag in ['买入', '卖出']:
            try:
                df = ak.stock_lhb_stock_detail_em(symbol=code, date=date_str, flag=flag)
                if df is None or getattr(df, 'empty', True):
                    continue
                for _, drow in df.iterrows():
                    seat = str(drow.get('交易营业部名称', ''))
                    if not seat:
                        continue
                    buy_amt = _safe_float(drow.get('买入金额', 0)) / 10000.0
                    sell_amt = _safe_float(drow.get('卖出金额', 0)) / 10000.0
                    key = (seat, round(buy_amt, 2), round(sell_amt, 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    stype = _classify_seat(seat, seats_db)
                    if stype not in detail_map[code]:
                        detail_map[code][stype] = {'buy': 0.0, 'sell': 0.0}
                    detail_map[code][stype]['buy'] += buy_amt
                    detail_map[code][stype]['sell'] += sell_amt
            except Exception:
                pass
            time.sleep(0.12)
    return detail_map


def classify(inst_buy, inst_sell, other_buy, other_sell):
    inst_net = inst_buy - inst_sell
    other_net = other_buy - other_sell
    inst_strong = inst_net > THRESHOLD
    other_strong = other_net > THRESHOLD
    if inst_strong and other_strong:
        return '机游共振'
    if inst_strong:
        return '机构独买'
    if other_strong:
        return '游资独买'
    return '不达标'


def process_day(date_str):
    """返回当日记录 dict，或 {'trading': False}。读取 out/lhb_seats.json 做席位分类。"""
    seats_db = _load_lhb_seats()
    stocks = fetch_lhb_list(date_str)
    if not stocks:
        return {'trading': False}
    detail_map = fetch_seat_detail(stocks, date_str, seats_db)
    out_stocks = []
    summary = {'机游共振': 0, '机构独买': 0, '游资独买': 0, '不达标': 0, '总计': len(stocks)}
    for s in stocks:
        code = s['code']
        seats = detail_map.get(code, {})
        inst_buy = seats.get('机构', {}).get('buy', 0.0)
        inst_sell = seats.get('机构', {}).get('sell', 0.0)
        inst_net = inst_buy - inst_sell
        # 机游共振口径：游资 + 量化（剔除北向/未识别），与算法端 fetch_lhb.py 一致
        other_buy = 0.0
        other_sell = 0.0
        for st in ('游资', '量化'):
            other_buy += seats.get(st, {}).get('buy', 0.0)
            other_sell += seats.get(st, {}).get('sell', 0.0)
        other_net = other_buy - other_sell
        cat = classify(inst_buy, inst_sell, other_buy, other_sell)
        summary[cat] += 1
        north = seats.get('北向', {})
        seat_detail = {}
        if inst_buy > 0 or inst_sell > 0:
            seat_detail['机构'] = {'buy': round(inst_buy, 1), 'sell': round(inst_sell, 1)}
        if north.get('buy', 0) > 0 or north.get('sell', 0) > 0:
            seat_detail['北向'] = {'buy': round(north.get('buy', 0), 1), 'sell': round(north.get('sell', 0), 1)}
        for st in ('游资', '量化', '未识别'):
            d = seats.get(st, {})
            if d.get('buy', 0) > 0 or d.get('sell', 0) > 0:
                seat_detail[st] = {'buy': round(d['buy'], 1), 'sell': round(d['sell'], 1)}
        out_stocks.append({
            'code': code,
            'name': s['name'],
            'price': round(s['price'], 2),
            'pct': round(s['pct'], 3),
            'reason': s['reason'],
            'category': cat,
            'inst_net_万': round(inst_net, 1),
            'inst_buy_万': round(inst_buy, 1),
            'inst_sell_万': round(inst_sell, 1),
            'yz_net_万': round(other_net, 1),
            'yz_buy_万': round(other_buy, 1),
            'yz_sell_万': round(other_sell, 1),
            'seats': seat_detail,
        })
    return {'trading': True, 'stocks': out_stocks, 'summary': summary}


def main():
    end = datetime.date.today()
    start = end - datetime.timedelta(days=N_CALENDAR_DAYS)
    # 已有历史
    hist = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding='utf-8') as f:
                hist = json.load(f)
        except Exception:
            hist = {}
    # 🛡 2026-08-31 一劳永逸：done 只认"真实完整数据"。
    #   原实现 done = 所有日期键 → {'trading': False, 'error': ...} 占位也被视为已完成，
    #   导致解析失败/未发布的那一天**永远不会被重抓**（共振日历当日永久空白）。
    #   现改为：只有 trading=True 且 stocks 非空且 seats 非全空 才算完成。
    def _is_real(rec):
        if not isinstance(rec, dict):
            return False
        if rec.get('trading') is not True:
            return False
        st = rec.get('stocks') or []
        if not st:
            return False
        # 骨架检测：stocks>0 但所有股票 seats 全空 → 视为不完整，允许重抓补全
        if all(not (x or {}).get('seats') for x in st):
            return False
        return True

    done = {k for k, v in hist.items()
            if isinstance(k, str) and len(k) == 10 and k[4] == '-' and _is_real(v)}

    dates = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # 跳过周末
            dates.append(d)
        d += datetime.timedelta(days=1)

    # 🛡 强制刷新窗口：最近 FORCE_REFRESH_DAYS 个自然日一律重抓（补全席位 / 覆盖 error 占位）
    force_from = (end - datetime.timedelta(days=FORCE_REFRESH_DAYS - 1)).isoformat()
    force_set = {x.isoformat() for x in dates if x.isoformat() >= force_from}

    print(f"回填区间 {start} ~ {end}，共 {len(dates)} 个交易日，已存在真实数据 {len(done & {x.isoformat() for x in dates})}")
    if force_set:
        print(f"强制重抓窗口（最近 {FORCE_REFRESH_DAYS} 天）：{sorted(force_set)}")
    newly = 0
    for dt in dates:
        ds = dt.strftime("%Y%m%d")
        iso = dt.isoformat()
        if iso in done and iso not in force_set:
            continue
        if iso in force_set and iso in done:
            # 已有真实数据但在强制窗口内：仅当新数据更完整时才覆盖（只增不减）
            _prev_n = len((hist.get(iso) or {}).get('stocks') or [])
        else:
            _prev_n = -1
        try:
            rec = process_day(ds)
            if rec.get('trading'):
                # 强制窗口内已有真实数据 → 只增不减，防止把好数据冲成骨架
                if _prev_n >= 0 and len(rec['stocks']) < _prev_n:
                    print(f"  {iso}: 保留既有 {_prev_n} 只（新抓 {len(rec['stocks'])} 只更少，不覆盖）")
                    continue
                newly += 1
                tag = f"[覆盖{_prev_n}→{len(rec['stocks'])}只]" if _prev_n >= 0 else ""
                print(f"  {iso}: {len(rec['stocks'])} 只  共振{rec['summary']['机游共振']} 机构独买{rec['summary']['机构独买']} 游资独买{rec['summary']['游资独买']} {tag}")
                hist[iso] = rec
            else:
                # 非交易日/无数据：绝不覆盖已有真实数据
                if _prev_n >= 0:
                    print(f"  {iso}: 接口空数据，保留既有真实数据（{_prev_n} 只）")
                    continue
                print(f"  {iso}: 非交易日/无数据")
                hist[iso] = rec
        except Exception as e:
            print(f"  {iso}: 失败 {e}")
            # 🛡 2026-08-26 一劳永逸：已有真实数据的日期绝不被失败重抓覆盖，
            #   否则解析异常日(如 08-24 的 'NoneType' object is not subscriptable')会反复把
            #   手动/历史找回的真实龙虎榜冲成 error 占位（"又没了"根因）。
            _existing = hist.get(iso)
            _real = bool(_existing and _existing.get('trading') is True and len(_existing.get('stocks', [])) > 0)
            if _real:
                print(f"  {iso}: 保留既有真实数据({len(_existing.get('stocks', []))}只)，跳过错误覆盖")
            else:
                hist[iso] = {'trading': False, 'error': str(e)[:80]}
        time.sleep(0.3)

    hist['update_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hist['range'] = [start.isoformat(), end.isoformat()]
    hist['backfill_days'] = len(dates)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    print(f"完成。新增 {newly} 个交易日，文件 {OUT}")


def _only_one(date_str):
    """单日补抓入口（应急 / 守卫调用）：忽略 done 集合与强制窗口，抓到即写。"""
    hist = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:
            hist = {}
    iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    prev = hist.get(iso) or {}
    prev_n = len(prev.get("stocks") or [])
    print(f"[--only] 单日补抓 {iso}（既有 {prev_n} 只）")
    try:
        rec = process_day(date_str)
    except Exception as e:
        print(f"[--only] {iso} 抓取失败: {type(e).__name__}: {e}")
        if prev_n > 0:
            print(f"[--only] 保留既有 {prev_n} 只真实数据，不写 error 占位")
            return 1
        hist[iso] = {"trading": False, "error": str(e)[:80]}
        hist["update_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=1)
        return 2
    if rec.get("trading"):
        if prev_n > 0 and len(rec["stocks"]) < prev_n:
            print(f"[--only] 保留既有 {prev_n} 只（新抓 {len(rec['stocks'])} 只更少）")
            return 0
        hist[iso] = rec
        print(f"[--only] {iso}: {len(rec['stocks'])} 只  共振{rec['summary']['机游共振']} "
              f"机构独买{rec['summary']['机构独买']} 游资独买{rec['summary']['游资独买']} "
              f"[覆盖 {prev_n}→{len(rec['stocks'])}]")
    else:
        if prev_n > 0:
            print(f"[--only] 接口空数据，保留既有 {prev_n} 只，不写占位")
            return 0
        hist[iso] = rec
        print(f"[--only] {iso}: 非交易日/无数据")
    hist["update_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    _only = None
    for _i, _a in enumerate(sys.argv[1:]):
        if _a == "--only" and _i + 1 < len(sys.argv[1:]):
            _only = sys.argv[1:][_i + 1]
        elif _a.startswith("--only="):
            _only = _a.split("=", 1)[1]
    if _only:
        raise SystemExit(_only_one(_only.strip()))
    main()
