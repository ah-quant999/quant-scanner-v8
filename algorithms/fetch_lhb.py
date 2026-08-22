#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙虎榜席位全量分析 v7
- 东方财富 stock_lhb_stock_detail_em：逐笔席位明细，全部统计
- 机构专用 / 深股通沪股通 / 游资 / 量化 / 未识别 → 全部计入
- 分类：机构净买>8000万 + 非机构净买>8000万 = 纯共振
"""
import akshare as ak
import json
import time
import datetime
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys

OUT = os.path.join(BASE, "..", "out", "lhb_result.json")
THRESHOLD = 8000  # 强买阈值：净买入 > 8000万
SEATS_PATH = os.path.join(os.path.dirname(__file__), "..", "out", "lhb_seats.json")
DETAIL_LIMIT = 90  # 最多分析前90只股票的逐笔席位（2026-08-12 主人质疑8/4/5/7/10北向日历空白：原 40 太少，北向在排序靠后；提到 90 覆盖全天上榜股）

def log(msg):
    print(f"  {msg}", flush=True)

def _load_lhb_seats():
    if not os.path.exists(SEATS_PATH):
        log(f"[WARN] lhb_seats.json 不存在")
        return {"seats": [], "patterns": {}}
    with open(SEATS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _classify_seat(seat_name, seats_db):
    """分类席位：返回 (类型, 别名或模式名)
    知名游资精确匹配 → ('游资', '章盟主')
    模式匹配游资 → ('游资', '拉萨团结路')  // 具体模式名
    机构/北向/量化 → ('机构', '') 等
    未识别 → ('未识别', '')
    """
    if not seat_name:
        return ('未识别', '')
    if '机构专用' in seat_name:
        return ('机构', '')
    if '深股通' in seat_name or '沪股通' in seat_name:
        return ('北向', '')
    # 精确匹配已知席位 → 返回别名
    for s in seats_db.get("seats", []):
        if s["name"] == seat_name:
            return (s.get("type", "游资"), s.get("alias", ""))
    # 4. 模糊匹配模式 → 返回模式名作为标签（如"拉萨团结路"、"宁波桑田路"）
    for p in seats_db.get("patterns", {}).get("游资", []):
        if p in seat_name:
            return ('游资', p)
    for p in seats_db.get("patterns", {}).get("量化", []):
        if p in seat_name:
            return ('量化', p)
    return ('未识别', '')

def get_date_str(target_date=None):
    if target_date is None:
        target_date = datetime.date.today()
    # 17点前 → 取上一个交易日（当日龙虎榜数据尚未发布）
    now = datetime.datetime.now()
    if now.hour < 17:
        target_date = target_date - datetime.timedelta(days=1)
    # 回退到最近一个交易日（排除周末）
    while target_date.weekday() >= 5:
        target_date = target_date - datetime.timedelta(days=1)
    return target_date.strftime("%Y%m%d")

_TRADE_CAL_CACHE = {"ts": 0, "set": None}
_TRADE_CAL_TTL = 24 * 3600  # 24h 缓存一次

def _get_trade_cal():
    """从 akshare 拉取交易日历（带缓存）。失败返回 None。"""
    import time
    if time.time() - _TRADE_CAL_CACHE["ts"] < _TRADE_CAL_TTL and _TRADE_CAL_CACHE["set"] is not None:
        return _TRADE_CAL_CACHE["set"]
    try:
        df = ak.tool_trade_date_hist_sina()
        if df is None or len(df) == 0:
            return None
        cal = set(str(d) for d in df["trade_date"].tolist())
        _TRADE_CAL_CACHE["set"] = cal
        _TRADE_CAL_CACHE["ts"] = time.time()
        return cal
    except Exception as e:
        log(f"⚠️ 拉取交易日历失败: {e}，回退到周末判定")
        return None

def is_trading_day(date_str):
    """判断给定日期是否为真实交易日（用于防 API 抖动把交易日误标 trading=False）。
    优先级：交易日历 > 周末判定 > 默认 True（保守不写占位）。
    返回 True 表示是交易日，False 表示非交易日（可写占位）。
    """
    if len(date_str) == 8:
        try:
            d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]))
        except Exception:
            return True
    else:
        try:
            d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return True
    if d.weekday() >= 5:
        return False
    cal = _get_trade_cal()
    if cal is not None:
        return d.strftime("%Y-%m-%d") in cal
    return True  # 查不到日历时保守：视为交易日（不写占位）

def _parse_lhb_list_em(df):
    """东财龙虎榜列表 → 统一 stocks 结构"""
    stocks = []
    seen = set()
    for _, row in df.iterrows():
        code = str(row.get('代码', '')).zfill(6)
        if code and code not in seen:
            seen.add(code)
            stocks.append({
                'code': code,
                'name': str(row.get('名称', '')),
                'price': float(row.get('最新价', 0) or 0),
                'pct': float(row.get('涨跌幅', 0) or 0),
                'amount': float(row.get('龙虎榜净买额', 0) or 0),
                'reason': str(row.get('上榜原因', '')),
            })
    return stocks

def _fetch_lhb_list_em_with_retry(date_str, max_retry=3):
    """东财列表主源（指数退避重试），全部失败返回 None。
    2026-08-22 加：东财接口抖动常返回空/抛错，必须重试+兜底，否则整页空白。"""
    import time
    for attempt in range(max_retry):
        try:
            df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
            if df is not None and len(df) > 0:
                return _parse_lhb_list_em(df)
            log(f"东财列表返回空(第{attempt+1}/{max_retry}次)，重试...")
        except Exception as e:
            log(f"东财列表失败(第{attempt+1}/{max_retry}次): {e}")
        if attempt < max_retry - 1:
            time.sleep(3 * (attempt + 1))
    return None

def fetch_lhb_list_sina(date_str):
    """非东财第三兜底：新浪每日龙虎榜列表（akshare stock_lhb_detail_daily_sina）。
    仅含上榜股列表/原因，无逐笔席位与净买额，作为东财主源全失败时的降级来源，
    保证页面不空白。对应值≈涨跌幅(偏离值)，净买额不可得置 0。"""
    try:
        df = ak.stock_lhb_detail_daily_sina(date=date_str)
        if df is None or len(df) == 0:
            log("新浪龙虎榜列表：无数据")
            return []
        stocks = []
        seen = set()
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).zfill(6)
            if not code or code in seen:
                continue
            seen.add(code)
            stocks.append({
                'code': code,
                'name': str(row.get('股票名称', '')),
                'price': float(row.get('收盘价', 0) or 0),
                'pct': float(row.get('对应值', 0) or 0),
                'amount': 0.0,
                'reason': str(row.get('指标', '')),
            })
        log(f"新浪龙虎榜列表：{len(stocks)} 只（降级：无席位明细）")
        return stocks
    except Exception as e:
        log(f"新浪龙虎榜列表失败: {e}")
        return []

def fetch_lhb_list(date_str):
    # ★ 2026-08-22 修复：东财主源重试 → 新浪列表兜底，杜绝"整页空白"
    stocks = _fetch_lhb_list_em_with_retry(date_str)
    src = 'em'
    if stocks is None:
        log("东财列表主源全失败，切换新浪列表兜底...")
        stocks = fetch_lhb_list_sina(date_str)
        src = 'sina'
    if not stocks:
        log(f"龙虎榜：暂无{date_str}数据（来源：{src}）")
        return []
    log(f"龙虎榜列表来源：{src}，{len(stocks)} 只")
    return stocks

def fetch_seat_detail(stocks, date_str):
    """逐笔席位明细：合并买入/卖出页并去重，避免同一席位重复计算。
    东财的买入 Top5 和卖出 Top5 会重叠同一营业部，需按完整行去重。
    """
    seats_db = _load_lhb_seats()

    # 优先分析新浪机构净买入大的股票，后面 fallback 也覆盖
    codes = [s['code'] for s in stocks]
    detail_map = {}

    for code in codes:
        detail_map[code] = {}
        seen = set()
        for flag in ['买入', '卖出']:
            # ★ 2026-08-22 加：游资逐笔席位东财独家，瞬时抖动需重试，否则该股席位缺失
            df = None
            for attempt in range(3):
                try:
                    df = ak.stock_lhb_stock_detail_em(symbol=code, date=date_str, flag=flag)
                    if df is not None and not df.empty:
                        break
                except Exception:
                    pass
                if attempt < 2:
                    time.sleep(1)
            if df is None or df.empty:
                continue
            try:
                for _, drow in df.iterrows():
                    seat = str(drow.get('交易营业部名称', ''))
                    if not seat:
                        continue
                    buy_raw = drow.get('买入金额', 0)
                    sell_raw = drow.get('卖出金额', 0)
                    # 东财卖出页/买入页的对应列可能为 NaN，必须当 0 处理
                    def _safe_float(v):
                        if v is None or (isinstance(v, float) and v != v):
                            return 0.0
                        try:
                            return float(v)
                        except Exception:
                            return 0.0
                    buy_amt = _safe_float(buy_raw) / 10000  # 元→万
                    sell_amt = _safe_float(sell_raw) / 10000
                    # 按 (营业部名称, 买入额, 卖出额) 去重，避免买卖两侧重复
                    key = (seat, round(buy_amt, 2), round(sell_amt, 2))
                    if key in seen:
                        continue
                    seen.add(key)

                    stype, alias = _classify_seat(seat, seats_db)
                    if stype not in detail_map[code]:
                        detail_map[code][stype] = {'buy': 0, 'sell': 0}

                    detail_map[code][stype]['buy'] += buy_amt
                    detail_map[code][stype]['sell'] += sell_amt

                    if alias:
                        if 'aliases' not in detail_map[code][stype]:
                            detail_map[code][stype]['aliases'] = []
                        if alias not in detail_map[code][stype]['aliases']:
                            detail_map[code][stype]['aliases'].append(alias)
                time.sleep(0.2)
            except Exception:
                pass

    total_seats = sum(len(v) for v in detail_map.values())
    log(f"逐笔席位：{total_seats} 种类型命中，覆盖 {len(detail_map)} 只股票")
    return detail_map

def _fetch_inst_sina(date_str=None):
    """新浪机构席位接口：按日期过滤，返回 {code: {'buy':万, 'sell':万, 'net':万}}"""
    inst_map = {}
    try:
        df = ak.stock_lhb_jgmx_sina()
        if df is None or df.empty:
            return inst_map
        # 过滤日期：date_str 形如 20260713 -> 2026-07-13
        if date_str and len(date_str) == 8:
            target = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            df = df[df['交易日期'].astype(str) == target]
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).zfill(6)
            # 新浪接口金额字段单位已经是"万"，无需再除以 10000
            buy = float(row.get('机构席位买入额', 0) or 0)
            sell = float(row.get('机构席位卖出额', 0) or 0)
            inst_map[code] = {'buy': buy, 'sell': sell, 'net': buy - sell}
    except Exception as e:
        log(f"新浪机构接口: {e}")
    return inst_map

def classify(inst_buy, inst_sell, other_buy, other_sell):
    """机构 vs 游资(不含北向) 净买入判定 — 按站点"数据口径说明"表
    ★ 2026-07-17 重构:
      - 4 分类：机游共振 / 机构独买 / 游资独买 / 不达标
      - 口径：机游共振 = 机构净买入>0.8亿 且 游资净买入>0.8亿（双方都强买）
      - 口径：独买 = 任一>阈值(0.8亿) 且 另一方<=0.8亿
      - 低于阈值或不满足上述条件 → 不达标
    """
    inst_net = inst_buy - inst_sell
    other_net = other_buy - other_sell
    inst_strong = inst_net > THRESHOLD
    other_strong = other_net > THRESHOLD
    # 双方都强买 → 机游共振
    if inst_strong and other_strong:
        return '机游共振', inst_net, other_net
    # 单边强买
    if inst_strong and not other_strong:
        return '机构独买', inst_net, other_net
    if other_strong and not inst_strong:
        return '游资独买', inst_net, other_net
    return '不达标', inst_net, other_net

def main():
    print("=" * 50)
    date_str = get_date_str()
    print(f"龙虎榜席位全量分析 v7（日期：{date_str}，阈值：{THRESHOLD}万）")
    print("=" * 50)

    stocks = fetch_lhb_list(date_str)
    if not stocks:
        # ★ 2026-08-14 主人令永久修复：API 抖动也会返回空，不能仅凭"接口空数据"就写 trading=False。
        # 真实教训：2026-08-04~13 因 cn runner 网络抖动，ak 接口返回空，
        #   fetch_lhb 把 7 个正常交易日误标为非交易日 → 共振日历显示空白 → 主人截图报错。
        # 永久解法：先用交易日历校验；只有日历确认是非交易日才写占位；否则只打日志不写。
        if not is_trading_day(date_str):
            print(f"  📅 {date_str} 经交易日历确认为非交易日，写占位 trading=False")
            _update_lhb_history({}, date_str, trading=False)
        else:
            print(f"  ⚠️ {date_str} 交易日历显示为交易日，但龙虎榜接口空数据 —— API 抖动/限流，**不写占位**以免污染历史日历")
        return

    # 按龙虎榜净买额绝对值排序，只分析前 DETAIL_LIMIT 只（防超时/限流）
    stocks = sorted(stocks, key=lambda s: abs(s.get('amount', 0)), reverse=True)[:DETAIL_LIMIT]
    print(f"  取净买额前 {len(stocks)} 只进行席位明细分析")

    # 新浪机构席位接口：兜底（新浪把北向卖出误并入机构卖出，必须以东财「机构专用」为主源）
    inst_map = _fetch_inst_sina(date_str)

    detail_map = fetch_seat_detail(stocks, date_str)

    results = {'机游共振': [], '机构独买': [], '游资独买': [], '不达标': []}
    for s in stocks:
        code = s['code']
        seats = detail_map.get(code, {})

        # ★ 2026-07-17 修复：东财「机构专用」优先（贴近交易所原始披露），
        #   新浪作为兜底。新浪 bug：把北向(深股通)卖出误并入机构卖出，
        #   导致机构净买入被高估。
        inst_buy = 0
        inst_sell = 0
        inst_net = 0
        if '机构' in seats and (seats['机构']['buy'] > 0 or seats['机构']['sell'] > 0):
            inst_buy = seats['机构']['buy']
            inst_sell = seats['机构']['sell']
            inst_net = inst_buy - inst_sell
        else:
            # 东财缺数据时，用新浪兜底
            inst_data = inst_map.get(code, {'buy': 0, 'sell': 0, 'net': 0})
            inst_buy = inst_data['buy']
            inst_sell = inst_data['sell']
            inst_net = inst_data['net']

        # ★ 2026-07-17 修复：按站点"数据口径说明"表 — 「机游共振」= 机构+游资同时净买入，
        #   明确「本页不涉及北向」。所以 yz 必须剔除北向：游资+量化。
        #   2026-08-01 再修：「未识别」席位也不得并入游资，避免把无名席位误判为游资共振。
        other_buy = 0
        other_sell = 0
        for stype in ('游资', '量化'):
            d = seats.get(stype, {'buy': 0, 'sell': 0})
            other_buy += d['buy']
            other_sell += d['sell']
        # 北向/未识别单独算（不归入 yz，供其他用途）
        # var bx = seats.get('北向', {'buy': 0, 'sell': 0})

        cat, _, other_net = classify(
            inst_buy, inst_sell,
            other_buy, other_sell
        )

        # 席位明细（类型→金额，紧凑格式）
        # 机构用新浪数据覆盖，保证与 inst_net 一致；其余用 seat detail
        seat_detail = {}
        if inst_buy > 0 or inst_sell > 0:
            seat_detail['机构'] = {
                'buy': round(inst_buy, 1),
                'sell': round(inst_sell, 1),
            }
        for stype in ('北向', '游资', '量化', '未识别'):
            d = seats.get(stype, {'buy': 0, 'sell': 0})
            if d['buy'] > 0 or d['sell'] > 0:
                item = {
                    'buy': round(d['buy'], 1),
                    'sell': round(d['sell'], 1),
                }
                if d.get('aliases'):
                    item['aliases'] = d['aliases']
                seat_detail[stype] = item

        results[cat].append({
            'code': code,
            'name': s['name'],
            'price': s['price'],
            'pct': s['pct'],
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

    # 输出
    os.makedirs('data', exist_ok=True)
    output = {
        'date': date_str,
        'update_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'stocks': results['机游共振'] + results['机构独买'] + results['游资独买'] + results['不达标'],
        'summary': {
            '机游共振': len(results['机游共振']),
            '机构独买': len(results['机构独买']),
            '游资独买': len(results['游资独买']),
            '不达标': len(results['不达标']),
            '总计': len(stocks),
        }
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 机游共振日历
    _update_lhb_history(results, date_str)

    print(f"\n完成！")
    print(f"  机游共振（双方都买）：{len(results['机游共振'])} 只")
    for r in results['机游共振'][:5]:
        types = '/'.join(r['seats'].keys()) if r.get('seats') else '无'
        print(f"    {r['code']} {r['name']} 机构{r['inst_net_万']}万 游资{r['yz_net_万']}万")
    print(f"  机构独买：{len(results['机构独买'])} 只")
    print(f"  游资独买：{len(results['游资独买'])} 只")
    print(f"  不达标：{len(results['不达标'])} 只")

def _update_lhb_history(results, date_str, trading=True):
    """写入机游共振日历（2026-07-17 改：纯共振→机游共振）。
    trading=False 用于节假日占位，避免历史日历显示陈旧数据。"""
    path = os.path.join(BASE, "..", "out", "lhb_history.json")
    hist = {}
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                hist = json.load(f)
        except Exception:
            pass
    pure_simple = []
    if trading:
        for item in results.get('机游共振', results.get('纯共振', [])):
            pure_simple.append({
                'code': item['code'],
                'name': item['name'],
                'amount': f"{item['inst_net_万']/10000:.2f}亿" if abs(item['inst_net_万']) >= 10000 else f"{item['inst_net_万']:.0f}万",
            })
    if len(date_str) == 8:
        fmt_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    else:
        fmt_date = datetime.date.today().strftime('%Y-%m-%d')
    hist[fmt_date] = {'trading': trading, 'pure': pure_simple}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    from fetch_logger import record_success, record_failure
    try:
        main()
        record_success(__file__)
    except Exception as e:
        record_failure(__file__, str(e))
        raise

