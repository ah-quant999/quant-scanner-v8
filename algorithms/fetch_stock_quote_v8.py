# -*- coding: utf-8 -*-
"""v8 全市场实时行情 fetcher — 个股查询升级核心数据源
【2026-08-06 主人令：个股查询要升级，至少比 v6 好】
v6 是 lazy 实时查询（akshare 按需调，慢）；v8 改成离线缓存（全市场抓取，每日盘中 + 盘后
各跑一次，data/STOCK_QUOTE.js 嵌入 v8 站点，查询秒出）。

数据源：akshare.stock_zh_a_spot()（新浪接口，~5500 只，27 秒，14 列基础行情）。
akshare.stock_zh_a_spot_em()（东财接口，字段更全但云端 + 阿狸咪都连接超时，故走新浪）。

输出：raw_data/stock_quote.json + data/STOCK_QUOTE.js（键 = shXXXXXX/szXXXXXX/bjXXXXXX）。
"""
import akshare as ak
import json
import os
import time
import datetime
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))                # .../algorithms/
REPO_ROOT = os.path.dirname(ROOT)                                    # 仓库根
RAW_DIR = os.path.join(REPO_ROOT, 'raw_data')
DATA_DIR = os.path.join(REPO_ROOT, 'data')
ic_path = os.path.abspath(os.path.join(ROOT, 'stock_industry_concepts.json'))  # algorithms/ 里

def fetch_all_spot():
    """全市场 A 股实时行情（约 5537 只，14 列，27s）。"""
    df = ak.stock_zh_a_spot()
    # 字段中文化映射
    df = df.rename(columns={
        '代码': 'code', '名称': 'name', '最新价': 'price', '涨跌额': 'change',
        '涨跌幅': 'pct', '买入': 'bid', '卖出': 'ask', '昨收': 'prev_close',
        '今开': 'open', '最高': 'high', '最低': 'low',
        '成交量': 'volume', '成交额': 'amount', '时间戳': 'snapshot_time',
    })
    out = {}
    for _, r in df.iterrows():
        code = str(r['code']).strip()
        if not code:
            continue
        # code 已带 sh/sz/bj 前缀（新浪格式：sh603259 / sz000001 / bj920000）
        try:
            out[code] = {
                'name': r['name'],
                'price': float(r['price']) if r['price'] not in (None, '', '-') else None,
                'change': float(r['change']) if r['change'] not in (None, '', '-') else None,
                'pct': float(r['pct']) if r['pct'] not in (None, '', '-') else None,
                'prev_close': float(r['prev_close']) if r['prev_close'] not in (None, '', '-') else None,
                'open': float(r['open']) if r['open'] not in (None, '', '-') else None,
                'high': float(r['high']) if r['high'] not in (None, '', '-') else None,
                'low': float(r['low']) if r['low'] not in (None, '', '-') else None,
                'volume': float(r['volume']) if r['volume'] not in (None, '', '-') else None,
                'amount': float(r['amount']) if r['amount'] not in (None, '', '-') else None,
                'snapshot_time': r['snapshot_time'],
            }
        except Exception:
            continue
    return out


def merge_industry_concepts(quote_data):
    """合并 algorithms/stock_industry_concepts.json（v8 已 7000+ 只映射）→ board/industry/concepts。"""
    ic_path = os.path.abspath(os.path.join(ROOT, 'stock_industry_concepts.json'))
    if not os.path.exists(ic_path):
        print(f"⚠️ 未找到 {ic_path}，跳过行业概念合并")
        return quote_data
    try:
        with open(ic_path, encoding='utf-8') as f:
            ic = json.load(f)
        merged = 0
        for code, info in quote_data.items():
            # code 形如 sh603259，取 6 位数字
            code6 = code[2:] if len(code) == 8 else code
            if code6 in ic:
                info['board'] = ic[code6].get('board', '')
                info['industry'] = ic[code6].get('industry', '')
                info['concepts'] = ic[code6].get('concepts', [])
                merged += 1
        print(f"✅ 合并行业概念：{merged}/{len(quote_data)} 只")
    except Exception as e:
        print(f"⚠️ 行业概念合并失败: {e}")
    return quote_data


def merge_dividend(quote_data):
    """合并 akshare stock_fhps_em() 全市场分红配送 → 每股股息率/EPS/BVPS/分红状态。

    数据源：东方财富 stock_fhps_em（最新一期分红预案/实施情况，约 5.5 秒抓 3855 只）。
    字段映射到 STOCK_QUOTE.stocks[code].dividend = {
      yield: 0.0244 (2.44%),
      cash_ratio: 9.8974 (%),
      eps: 3.27,
      bvps: 18.57,
      cap_reserve: 9.57,
      undist_profit: 8.68,
      net_profit_yoy: 0.0900,
      total_share: 29.12 (亿),
      plan_date: '2024-03-19',
      record_date: '2024-06-25',
      ex_date: '2024-06-26',
      progress: '实施分配',
      announce_date: '2024-06-20',
    }
    """
    try:
        import akshare as ak
    except ImportError:
        print("⚠️ akshare 未安装，跳过分红合并")
        return quote_data
    try:
        df = ak.stock_fhps_em()
        if df is None or len(df) == 0:
            print("⚠️ stock_fhps_em 返回空")
            return quote_data
        merged = 0
        for _, r in df.iterrows():
            code6 = str(r['代码']).strip()
            # 形如 sh/sz603259
            code8 = ('sh' if code6.startswith(('6', '9', '5')) else 'sz') + code6
            if code8 not in quote_data:
                continue
            def _f(v):
                try: return float(v)
                except Exception: return None
            def _s(v):
                try:
                    import pandas as _pd
                    if _pd.isna(v): return None
                except Exception:
                    pass
                if not v: return None
                return str(v).strip()
            quote_data[code8]['dividend'] = {
                'yield': _f(r.get('现金分红-股息率')),     # 0.0244 = 2.44%
                'cash_ratio': _f(r.get('现金分红-现金分红比例')),  # 9.8974%
                'eps': _f(r.get('每股收益')),
                'bvps': _f(r.get('每股净资产')),
                'cap_reserve': _f(r.get('每股公积金')),
                'undist_profit': _f(r.get('每股未分配利润')),
                'net_profit_yoy': _f(r.get('净利润同比增长')),
                'total_share_yi': _f(r.get('总股本')) / 1e8 if _f(r.get('总股本')) else None,  # 转为亿
                'plan_date': _s(r.get('预案公告日')),
                'record_date': _s(r.get('股权登记日')),
                'ex_date': _s(r.get('除权除息日')),
                'progress': _s(r.get('方案进度')),
                'announce_date': _s(r.get('最新公告日期')),
            }
            merged += 1
        print(f"✅ 合并分红配送：{merged}/{len(quote_data)} 只")
    except Exception as e:
        print(f"⚠️ 分红合并失败: {e}")
    return quote_data


def write_outputs(data):
    """同时写 raw_data/stock_quote.json 和 data/STOCK_QUOTE.js（双格式）。"""
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    meta = {
        'update_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'akshare.stock_zh_a_spot (新浪) + algorithms/stock_industry_concepts.json',
        'count': len(data),
        'fields': ['name','price','change','pct','prev_close','open','high','low','volume','amount','snapshot_time','board','industry','concepts'],
    }
    # raw_data/stock_quote.json（云端抓取落盘位置）
    raw_path = os.path.join(RAW_DIR, 'stock_quote.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump({**{'meta': meta}, **{'stocks': data}}, f, ensure_ascii=False)
    print(f"✅ raw_data/stock_quote.json  {len(data)} stocks | {os.path.getsize(raw_path)//1024} KB")

    # data/STOCK_QUOTE.js（v8 站点嵌入用）
    js_path = os.path.join(DATA_DIR, 'STOCK_QUOTE.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write('window.STOCK_QUOTE = ' + json.dumps({**{'meta': meta}, **{'stocks': data}}, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(f"✅ data/STOCK_QUOTE.js       {len(data)} stocks | {os.path.getsize(js_path)//1024} KB")


def merge_fundamental_quality(quote_data):
    """合并 raw_data/fundamental_quality.json → 财务画像（ROE/营收增速/综合评级/消息面加减分）。

    数据源：v8 算法链产物 fundamental_quality.json（fetch_fundamental_quality.py 用 baostock 抓 ROE/营收增速）。
    字段映射到 STOCK_QUOTE.stocks[code].fundamental = {
      grade: 'A'/'B'/'C'/'D'/'',          # 综合评级：A=极致优质 / B=良好 / C=一般 / D=差 / ''=无数据中性
      score: 70,                         # 质量分 0-100
      roe: 20.5,                         # ROE 净资产收益率 %
      revenue_growth: 25.3,             # 营收增速 %
      eps: 3.27,                         # 每股收益
      news_score: 5,                      # 消息面加减分 ±20（业绩预告/重大公告）
      news_tags: ['业绩预增','重组'],     # 消息面标签
    }
    注意：fundamental_quality.json 只覆盖被选中的 213-700 只候选池股票，不是全市场。
    未入选的股票 quote_data[code].fundamental 不会被合并（不造空白字段）。
    fundamental_quality 的 code 是 sh_002335 格式（带下划线），需转 sh002335。
    """
    ic_path = os.path.abspath(os.path.join(ROOT, '..', 'raw_data', 'fundamental_quality.json'))
    if not os.path.exists(ic_path):
        print(f"⚠️ 未找到 {ic_path}，跳过财务画像合并（明日算法链跑完后会写）")
        return quote_data
    try:
        with open(ic_path, encoding='utf-8') as f:
            qual = json.load(f)
        stocks = qual.get('stocks') or {}
        merged = 0
        for code_underscore, info in stocks.items():
            # code 格式 sh_002335 → 转为 sh002335
            code8 = code_underscore.replace('_', '') if '_' in code_underscore else code_underscore
            if code8 not in quote_data:
                continue
            quote_data[code8]['fundamental'] = {
                'grade': info.get('grade') or info.get('quality_grade') or '',
                'score': info.get('score') or info.get('quality_score'),
                'roe': info.get('roe'),
                'revenue_growth': info.get('revenue_growth') or info.get('revenue'),
                'eps': info.get('eps'),
                'news_score': info.get('news', {}).get('score') if isinstance(info.get('news'), dict) else None,
                'news_tags': info.get('news', {}).get('tags', []) if isinstance(info.get('news'), dict) else [],
            }
            merged += 1
        print(f"✅ 合并财务画像：{merged}/{len(quote_data)} 只（仅候选池覆盖）")
    except Exception as e:
        print(f"⚠️ 财务画像合并失败: {e}")
    return quote_data


def main():
    t0 = time.time()
    print("开始抓取全市场 A 股实时行情（akshare 新浪接口）...")
    data = fetch_all_spot()
    print(f"抓取完成：{len(data)} 只，{time.time()-t0:.1f}s")
    data = merge_industry_concepts(data)
    data = merge_dividend(data)
    data = merge_fundamental_quality(data)
    write_outputs(data)
    print(f"\n总计：{time.time()-t0:.1f}s")
    return 0


if __name__ == '__main__':
    sys.exit(main())