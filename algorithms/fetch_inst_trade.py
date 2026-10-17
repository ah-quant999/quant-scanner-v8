#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机构买卖统计抓取 — 龙虎榜机构净买卖排名
输出: data/inst_trade.json
"""
import json, os, sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "..", "out")
DATA_FILE = os.path.join(DATA_DIR, "inst_trade.json")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def _fetch_lhb_with_retry(today, max_retry=4):
    """带指数退避重试的龙虎榜机构买卖抓取（东财 jgmmtj 接口），全部失败返回 None"""
    import akshare as ak
    import time
    last_err = None
    for attempt in range(max_retry):
        try:
            return ak.stock_lhb_jgmmtj_em(start_date=today, end_date=today)
        except Exception as e:
            last_err = e
            log(f"akshare(jgmmtj)失败(第{attempt+1}/{max_retry}次): {e}")
            if attempt < max_retry - 1:
                wait = 5 * (2 ** attempt)
                log(f"  等待 {wait}s 后重试...")
                time.sleep(wait)
    return None

def _fetch_lhb_detail_with_retry(today, max_retry=4):
    """兜底：东财 stock_lhb_detail_em（盘后席位分析同款接口，常年可用）抓机构买卖统计。
    2026-08-04 新增：主接口 jgmmtj 连日返回 NoneType 报错，detail_em 列名略有差异，
    下方用容错 _num/_txt 读取。"""
    import akshare as ak
    import time
    last_err = None
    for attempt in range(max_retry):
        try:
            df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
            if df is None or len(df) == 0:
                return None
            return df
        except Exception as e:
            last_err = e
            log(f"akshare(detail)失败(第{attempt+1}/{max_retry}次): {e}")
            if attempt < max_retry - 1:
                wait = 5 * (2 ** attempt)
                log(f"  等待 {wait}s 后重试...")
                time.sleep(wait)
    return None

def _fetch_lhb_jgmx_sina_with_retry(today, max_retry=3):
    """非东财第三兜底：新浪机构明细（akshare stock_lhb_jgmx_sina）。
    返回含 股票代码/股票名称/交易日期/机构席位买入额/机构席位卖出额/类型 的 DataFrame。
    按交易日过滤；东财 jgmmtj/detail 全失败时启用，保证机构净买卖统计不空白。"""
    import akshare as ak
    import time
    for attempt in range(max_retry):
        try:
            df = ak.stock_lhb_jgmx_sina()
            if df is None or len(df) == 0:
                return None
            if len(today) == 8:
                target = f"{today[:4]}-{today[4:6]}-{today[6:]}"
                df = df[df['交易日期'].astype(str) == target]
            if df is None or len(df) == 0:
                return None
            return df
        except Exception as e:
            log(f"新浪jgmx失败(第{attempt+1}/{max_retry}次): {e}")
            if attempt < max_retry - 1:
                time.sleep(3 * (attempt + 1))
    return None

def _normalize_sina_jgmx(df):
    """把新浪机构明细列名归一化为 detail_em 同款列，复用下方 dedup 逻辑。
    新浪仅给 机构席位买入额/卖出额，机构数/总成交额/占比等不可得置空。"""
    import pandas as pd
    out = pd.DataFrame()
    out['代码'] = df['股票代码'].astype(str).str.zfill(6)
    out['名称'] = df['股票名称'].astype(str)
    out['机构买入净额'] = (df['机构席位买入额'].astype(float) - df['机构席位卖出额'].astype(float))
    out['机构净买额'] = out['机构买入净额']
    out['买方机构数'] = 0
    out['卖方机构数'] = 0
    out['机构买入总额'] = df['机构席位买入额'].astype(float)
    out['机构卖出总额'] = df['机构席位卖出额'].astype(float)
    out['市场总成交额'] = float('nan')
    out['机构净买额占总成交额比'] = float('nan')
    out['换手率'] = float('nan')
    out['上榜原因'] = ''
    out['收盘价'] = float('nan')
    out['最新价'] = float('nan')
    out['涨跌幅'] = float('nan')
    return out

def _num(row, *names, default=0.0):
    """容错读数值：多候选列名，None/NaN/缺失返回 default"""
    for n in names:
        if n in row and row[n] is not None:
            try:
                v = float(row[n])
                if v == v:  # 非 NaN
                    return v
            except Exception:
                pass
    return default

def _txt(row, *names, default=''):
    for n in names:
        if n in row and row[n] is not None:
            return str(row[n])
    return default

def _get_recent_trade_date(ref=None):
    """龙虎榜机构数据 T+1 发布且盘中未收盘时无当日数据：
    17 点前取上一交易日，并跳过周末，与 fetch_lhb.py 对齐。"""
    from datetime import date, timedelta, datetime
    if ref is None:
        ref = date.today()
    # 17点前（含盘前/早盘）当日龙虎榜尚未公布，取上一交易日
    if datetime.now().hour < 17:
        ref = ref - timedelta(days=1)
    while ref.weekday() >= 5:
        ref = ref - timedelta(days=1)
    return ref.strftime('%Y%m%d')

def main():
    # 2026-07-18 修正：周末同样执行。龙虎榜机构数据 T+1 发布，周六需抓取
    # 最近交易日数据。原守卫导致周六 T+1 补全跳过。
    log("=" * 40)
    log("机构买卖统计抓取")
    log("=" * 40)
    
    today = _get_recent_trade_date()
    log(f"目标交易日: {today}")

    df = _fetch_lhb_with_retry(today)
    src = "jgmmtj"
    if df is None or len(df) == 0:
        log("主接口(jgmmtj)无数据，切换兜底接口(detail_em)...")
        df = _fetch_lhb_detail_with_retry(today)
        src = "detail_em"
    if df is None or len(df) == 0:
        log("东财接口全失败，切换新浪机构明细兜底(jgmx_sina)...")
        df = _fetch_lhb_jgmx_sina_with_retry(today)
        src = "sina_jgmx"
    if df is None or len(df) == 0:
        log("全部接口重试仍失败，保留旧数据（如有）")
        sys.exit(1)
    # 新浪机构明细列名与东财不同，归一化为东财同款列再走 dedup
    if src == "sina_jgmx":
        df = _normalize_sina_jgmx(df)
    log(f"数据源: {src}，命中 {len(df)} 行")

    # Deduplicate by code (keep max net buy)；容错读列（两套接口列名不同）
    deduped = {}
    for _, r in df.iterrows():
        code = str(_txt(r, '代码')).zfill(6)
        if not code:
            continue
        amt = _num(r, '机构买入净额', '机构净买额')
        if code not in deduped or abs(amt) > abs(deduped[code]['net_amt']):
            deduped[code] = {
                'code': code,
                'name': _txt(r, '名称'),
                'close': _num(r, '收盘价', '最新价'),
                'pct': _num(r, '涨跌幅'),
                'buy_inst': int(_num(r, '买方机构数')),
                'sell_inst': int(_num(r, '卖方机构数')),
                'buy_amt': _num(r, '机构买入总额'),
                'sell_amt': _num(r, '机构卖出总额'),
                'net_amt': amt,
                'total_amt': _num(r, '市场总成交额', '总成交额'),
                'net_ratio': _num(r, '机构净买额占总成交额比'),
                'turnover': _num(r, '换手率'),
                'reason': _txt(r, '上榜原因')[:80],
            }
    
    stocks = sorted(deduped.values(), key=lambda x: x['net_amt'], reverse=True)
    
    # Stats
    total_net = sum(s['net_amt'] for s in stocks)
    buy_count = sum(1 for s in stocks if s['net_amt'] > 0)
    sell_count = sum(1 for s in stocks if s['net_amt'] < 0)
    
    # Top 10
    top_buy = [s for s in stocks if s['net_amt'] > 0][:10]
    top_sell = sorted([s for s in stocks if s['net_amt'] < 0], key=lambda x: x['net_amt'])[:5]
    
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': today,
        'total_net': round(total_net / 100000000, 2),  # 元 → 亿
        'buy_count': buy_count,
        'sell_count': sell_count,
        'total_count': len(stocks),
        'top_buy': top_buy,
        'top_sell': top_sell,
        'all': stocks,
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    total_net_yi = round(total_net / 100000000, 2)
    log(f"✅ {len(stocks)}只股票, 机构净{('买' if total_net > 0 else '卖')}{abs(total_net_yi):.1f}亿")
    log(f"   净买{buy_count}只, 净卖{sell_count}只")

if __name__ == "__main__":
    from fetch_logger import record_success, record_failure
    try:
        main()
        record_success(__file__)
    except Exception as e:
        record_failure(__file__, str(e))
        raise

