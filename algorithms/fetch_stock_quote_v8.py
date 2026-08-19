# -*- coding: utf-8 -*-
"""v8 全市场实时行情 fetcher — 个股查询升级核心数据源
【2026-08-06 主人令：个股查询要升级，至少比 v6 好】
v6 是 lazy 实时查询（akshare 按需调，慢）；v8 改成离线缓存（全市场抓取，每日盘中 + 盘后
各跑一次，data/STOCK_QUOTE.js 嵌入 v8 站点，查询秒出）。

数据源：
  - A 股：akshare.stock_zh_a_spot()（新浪接口，~5500 只，27 秒，14 列基础行情）
  - 港股：akshare.stock_hk_spot()（新浪接口，~2800 只）
  - ETF：akshare.fund_etf_spot_em()（东财接口，~1500 只）

2026-08-13 修复：原 STOCK_QUOTE 只含 A 股，导致个股查询搜到港股/ETF 后详情页显示「未收录」。
现合并 A 股 + 港股 + ETF，统一键为 shXXXXXX/szXXXXXX/bjXXXXXX/hkXXXXX/sh/sz15XXXX。

输出：raw_data/stock_quote.json + data/STOCK_QUOTE.js。
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

def _safe_float(v):
    try:
        if v in (None, '', '-'):
            return None
        f = float(v)
        if f != f:  # NaN → None（2026-08-19 一劳永逸：东财 NaN 不抛异常会直通，前端显示 NaN）
            return None
        return f
    except Exception:
        return None


def _fetch_all_spot_em():
    """东财全市场 A 股实时行情（akshare.stock_zh_a_spot_em）—— 新浪接口风控/抖动时的自动 fallback。
    2026-08-19 一劳永逸：新浪 stock_zh_a_spot 当日两次抖动（ConnectionError / JSONDecodeError 返回 HTML），
    双源互备后任一路通都能出全量数据，杜绝「个股查询整表陈旧/错值」复发。"""
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"⚠️ 东财A股行情也失败: {type(e).__name__} {str(e)[:60]}")
        return {}
    df = df.rename(columns={
        '代码': 'code', '名称': 'name', '最新价': 'price', '涨跌额': 'change',
        '涨跌幅': 'pct', '昨收': 'prev_close', '今开': 'open', '最高': 'high',
        '最低': 'low', '成交量': 'volume', '成交额': 'amount',
    })
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%H:%M:%S')
    out = {}
    for _, r in df.iterrows():
        code = str(r.get('code', '')).strip().zfill(6)
        if not code or code == '0':
            continue
        if code.startswith(('6', '9', '5')):
            key = 'sh' + code
        elif code.startswith(('0', '1', '2', '3')):
            key = 'sz' + code
        else:
            key = 'bj' + code
        try:
            out[key] = {
                'name': r.get('name'),
                'price': _safe_float(r.get('price')),
                'change': _safe_float(r.get('change')),
                'pct': _safe_float(r.get('pct')),
                'prev_close': _safe_float(r.get('prev_close')),
                'open': _safe_float(r.get('open')),
                'high': _safe_float(r.get('high')),
                'low': _safe_float(r.get('low')),
                'volume': _safe_float(r.get('volume')),
                'amount': _safe_float(r.get('amount')),
                'snapshot_time': now,
            }
        except Exception:
            continue
    print(f"✅ 东财A股行情：{len(out)} 只（新浪不可用时 fallback）")
    return out


def fetch_all_spot():
    """全市场 A 股实时行情（约 5537 只，14 列，27s）。
    2026-08-19 一劳永逸：主源新浪 stock_zh_a_spot，失败自动 fallback 东财 stock_zh_a_spot_em，
    双源互备杜绝「整表陈旧/错值」复发。"""
    try:
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
                    'price': _safe_float(r['price']),
                    'change': _safe_float(r['change']),
                    'pct': _safe_float(r['pct']),
                    'prev_close': _safe_float(r['prev_close']),
                    'open': _safe_float(r['open']),
                    'high': _safe_float(r['high']),
                    'low': _safe_float(r['low']),
                    'volume': _safe_float(r['volume']),
                    'amount': _safe_float(r['amount']),
                    'snapshot_time': r['snapshot_time'],
                }
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"⚠️ 新浪A股行情失败: {type(e).__name__} {str(e)[:80]} → fallback 东财")
        return _fetch_all_spot_em()


def fetch_hk_spot():
    """港股实时行情（akshare 新浪接口，约 2800 只）。"""
    try:
        df = ak.stock_hk_spot()
    except Exception as e:
        print(f"⚠️ 港股行情获取失败: {type(e).__name__} {str(e)[:60]}")
        return {}
    if df is None or df.empty:
        print("⚠️ 港股行情返回空")
        return {}
    out = {}
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%H:%M:%S')
    for _, r in df.iterrows():
        code = str(r.get('代码', '')).strip()
        name = str(r.get('中文名称', '')).strip()
        if not code or not name or not code.isdigit():
            continue
        code = code.zfill(5)
        key = 'hk' + code
        try:
            out[key] = {
                'name': name,
                'price': _safe_float(r.get('最新价')),
                'change': _safe_float(r.get('涨跌额')),
                'pct': _safe_float(r.get('涨跌幅')),
                'prev_close': _safe_float(r.get('昨收')),
                'open': _safe_float(r.get('今开')),
                'high': _safe_float(r.get('最高')),
                'low': _safe_float(r.get('最低')),
                'volume': _safe_float(r.get('成交量')),
                'amount': _safe_float(r.get('成交额')),
                'snapshot_time': now,
                'board': '港股',
                'industry': '',
                'concepts': [],
            }
        except Exception:
            continue
    print(f"✅ 港股行情：{len(out)} 只")
    return out


def fetch_etf_spot():
    """ETF 实时行情（akshare 东财接口，约 1500 只）。"""
    try:
        df = ak.fund_etf_spot_em()
    except Exception as e:
        print(f"⚠️ ETF 行情获取失败: {type(e).__name__} {str(e)[:60]}")
        return {}
    if df is None or df.empty:
        print("⚠️ ETF 行情返回空")
        return {}
    out = {}
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%H:%M:%S')
    for _, r in df.iterrows():
        code = str(r.get('代码', '')).strip()
        name = str(r.get('名称', '')).strip()
        if not code or not name or not code.isdigit() or len(code) != 6:
            continue
        prefix = 'sh' if code.startswith('5') else 'sz'
        key = prefix + code
        try:
            out[key] = {
                'name': name,
                'price': _safe_float(r.get('最新价')),
                'change': _safe_float(r.get('涨跌额')),
                'pct': _safe_float(r.get('涨跌幅')),
                'prev_close': _safe_float(r.get('昨收')),
                'open': _safe_float(r.get('开盘价')),
                'high': _safe_float(r.get('最高价')),
                'low': _safe_float(r.get('最低价')),
                'volume': _safe_float(r.get('成交量')),
                'amount': _safe_float(r.get('成交额')),
                'snapshot_time': now,
                'board': 'ETF',
                'industry': '',
                'concepts': [],
            }
        except Exception:
            continue
    print(f"✅ ETF 行情：{len(out)} 只")
    return out


def merge_industry_concepts(quote_data):
    """合并 algorithms/stock_industry_concepts.json（v8 已 7000+ 只映射）→ board/industry/concepts。
    港股/ETF 已在 fetch_hk_spot/fetch_etf_spot 中设置 board，此处跳过。"""
    ic_path = os.path.abspath(os.path.join(ROOT, 'stock_industry_concepts.json'))
    if not os.path.exists(ic_path):
        print(f"⚠️ 未找到 {ic_path}，跳过行业概念合并")
        return quote_data
    try:
        with open(ic_path, encoding='utf-8') as f:
            ic = json.load(f)
        merged = 0
        for code, info in quote_data.items():
            # 跳过港股/ETF：只给 A 股/北交所补行业概念
            if code.startswith('hk') or info.get('board') == 'ETF':
                continue
            # code 形如 sh603259/bj920000，取 6 位数字
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


def _fmt_dividend_plan(r):
    """把 stock_fhps_em 的送转/现金比例字段转成人类可读的分红方案字符串。
    字段含义均为「每10股」：现金分红比例 4.2 = 10派4.2元；
    送转比例 0.5 = 10送5股；转股比例 0.3 = 10转增3股。"""
    def _to_float(v):
        try: return float(v)
        except Exception: return None
    parts = []
    cash = _to_float(r.get('现金分红-现金分红比例'))
    give = _to_float(r.get('送转股份-送转比例'))      # 送股比例
    conv = _to_float(r.get('送转股份-转股比例'))      # 转股比例
    if give and give > 0:
        parts.append(f"10送{give:.1f}".rstrip('0').rstrip('.') + "股")
    if conv and conv > 0:
        parts.append(f"10转{conv:.1f}".rstrip('0').rstrip('.') + "股")
    if cash and cash > 0:
        parts.append(f"10派{cash:.2f}".rstrip('0').rstrip('.') + "元")
    if not parts:
        return None
    return "；".join(parts)


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
      desc: '10派4.2元' or '10送2转3派4.2元',
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
            if not code6.isdigit() or len(code6) != 6:
                continue
            # 形如 sh/sz603259；ETF 以 5/15/16 开头也跳过（fund_etf_spot_em 代码在此列但无分红）
            code8 = ('sh' if code6.startswith(('6', '9', '5')) else 'sz') + code6
            if code8 not in quote_data or code8.startswith('hk') or quote_data[code8].get('board') == 'ETF':
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
            existing = quote_data[code8].get('dividend') or {}
            new_desc = _fmt_dividend_plan(r)
            # 若已有 cninfo 的 desc（更权威），保留；否则用 stock_fhps_em 生成
            desc = existing.get('desc') if existing.get('desc') else new_desc
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
                'desc': desc,
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
    a_count = sum(1 for k in data if k.startswith(('sh','sz','bj')) and data[k].get('board') != 'ETF')
    hk_count = sum(1 for k in data if k.startswith('hk'))
    etf_count = sum(1 for k in data if data[k].get('board') == 'ETF')
    meta = {
        'update_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'akshare.stock_zh_a_spot(新浪A股)+stock_hk_spot(新浪港股)+fund_etf_spot_em(东财ETF)+algorithms/stock_industry_concepts.json',
        'count': len(data),
        'a_count': a_count,
        'hk_count': hk_count,
        'etf_count': etf_count,
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
    print("开始抓取全市场实时行情...")
    data = fetch_all_spot()
    a_count = sum(1 for k in data if k.startswith(('sh', 'sz', 'bj')))
    print(f"A股：{a_count} 只，{time.time()-t0:.1f}s")
    # 🛡 2026-08-19 一劳永逸：A 股数量守卫——双源均不可用（新浪/东财同时风控）时
    #   拒绝写输出，保留旧文件，杜绝「个股查询整表被残缺数据覆盖成未收录」。
    if a_count < 3000:
        print(f"❌ A股行情异常稀少（{a_count} 只 < 3000），新浪+东财均不可用 → 拒绝写输出，保留旧数据")
        return 1
    hk_data = fetch_hk_spot()
    etf_data = fetch_etf_spot()
    # 合并：A 股为基础，港股/ETF 补充（不覆盖 A 股）
    for k, v in hk_data.items():
        if k not in data:
            data[k] = v
    for k, v in etf_data.items():
        if k not in data:
            data[k] = v
    print(f"合并后：{len(data)} 只")
    data = merge_industry_concepts(data)
    data = merge_dividend(data)
    data = merge_fundamental_quality(data)
    write_outputs(data)
    print(f"\n总计：{time.time()-t0:.1f}s")
    return 0


if __name__ == '__main__':
    sys.exit(main())