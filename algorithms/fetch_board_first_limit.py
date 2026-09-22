# -*- coding: utf-8 -*-
"""
主板首板 · 一进二观察 —— 数据生成器
====================================
数据源：akshare.stock_zt_pool_em（东方财富涨停池，云端 cloud_fetch_v8 同源）
口径：主板（60/00 开头，剔除 688/92/30）+ 首板（连板数==1）
观察标签（基础口径，仅用涨停池快照即可判定，无需 K 线）：
  · 流通市值<120亿 或 流通股<4亿
  · 换手率>2%
  · 炸板次数==0（封板干净）
K 线类严格过滤（控盘指数/大趋势/三线粘合/量线粘合/角度60/涨停确认/量差/筹码穿刺）
需逐股盘中 K 线，本机缓存仅到 09-07，按北极星不伪造 → 留待云端 K 线步，此处只挂基础口径。

产出：
  raw_data/board_first_limit.json
  data/BOARD_FIRST_LIMIT.js  (window.BOARD_FIRST_LIMIT)
"""
import os, sys, json, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _now_cst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def _latest_trading_day():
    """返回 YYYYMMDD；默认今天(CST)，调用方可覆盖。"""
    return _now_cst().strftime('%Y%m%d')

def build(date=None):
    import akshare as ak
    explicit = date is not None
    if date is None:
        date = _latest_trading_day()
    df = ak.stock_zt_pool_em(date=date)
    if (df is None or len(df) == 0) and not explicit:
        # 2026-09-23 追加（阿狸咪·夜间窗口）：默认模式下当日无池（凌晨/周末/节假日/源未更新）
        # 时，向前最多回溯 7 个自然日找最近一个有涨停池的交易日 —— 本卡语义是
        # 「最近一个已收盘交易日的涨停池观察」，不是「今天必须有」；同日去重护栏保证
        # 已采集过的交易日不会被回溯档覆盖。显式传日期（手动回补）时不回溯，所见即所得。
        for _i in range(1, 8):
            _d = (_now_cst() - datetime.timedelta(days=_i)).strftime('%Y%m%d')
            _df = ak.stock_zt_pool_em(date=_d)
            if _df is not None and len(_df) > 0:
                date = _d
                df = _df
                print('BACKFILL: %s 无池 → 回溯到最近有池交易日 %s' % (
                    _latest_trading_day(), _d))
                break
    if df is None or len(df) == 0:
        return None, date, "当日无涨停池数据（非交易日或源未更新，含回溯 7 日）"
    cols = list(df.columns)
    code_k = '代码'; name_k = '名称'; chg_k = '涨跌幅'; price_k = '最新价'
    cmcap_k = '流通市值'; tmcap_k = '总市值'; turn_k = '换手率'
    seal_k = '封板资金'; ftime_k = '首次封板时间'; ltime_k = '最后封板时间'
    broken_k = '炸板次数'; lbc_k = '连板数'; ind_k = '所属行业'
    items = []
    for _, r in df.iterrows():
        code = str(r[code_k]).zfill(6)
        # 主板过滤：60/00 开头，剔除 688(科创)/92(北交类)/30(创业)
        if not (code.startswith('60') or code.startswith('00')):
            continue
        if code.startswith('688') or code.startswith('92') or code.startswith('30'):
            continue
        lbc = int(r[lbc_k]) if r[lbc_k] is not None else 0
        if lbc != 1:  # 仅首板
            continue
        price = float(r[price_k]) if r[price_k] not in (None, '-', '--') else 0.0
        cmcap_yi = float(r[cmcap_k]) / 1e8 if r[cmcap_k] not in (None, '-', '--') else 0.0  # 亿
        circ_shares_yi = (cmcap_yi * 1e8) / price / 1e8 if price > 0 else 0.0  # 亿股
        turn = float(r[turn_k]) if r[turn_k] not in (None, '-', '--') else 0.0  # %
        seal_yi = float(r[seal_k]) / 1e8 if r[seal_k] not in (None, '-', '--') else 0.0  # 亿
        broken = int(r[broken_k]) if r[broken_k] not in (None, '-', '--') else 0
        chg = float(r[chg_k]) if r[chg_k] not in (None, '-', '--') else 0.0
        # 基础口径达标（公式可离线判定部分）
        size_ok = (cmcap_yi < 120) or (circ_shares_yi < 4)
        turn_ok = turn > 2
        seal_clean = broken == 0
        basic_pass = bool(size_ok and turn_ok and seal_clean)
        items.append({
            'code': code,
            'name': str(r[name_k]),
            'chg': round(chg, 2),
            'price': round(price, 2),
            'circ_mcap': round(cmcap_yi, 1),       # 亿
            'circ_shares': round(circ_shares_yi, 2),  # 亿股
            'turnover': round(turn, 2),            # %
            'seal': round(seal_yi, 2),             # 亿
            'first_time': str(r[ftime_k]),
            'last_time': str(r[ltime_k]),
            'broken': broken,
            'industry': str(r[ind_k]),
            'basic_pass': basic_pass,
        })
    # 排序：基础达标优先，其次封板资金降序
    items.sort(key=lambda x: (not x['basic_pass'], -x['seal']))
    basic_n = sum(1 for x in items if x['basic_pass'])
    out = {
        'update_time': _now_cst().strftime('%Y-%m-%d %H:%M:%S'),
        'date': date,
        'total': len(items),
        'basic_pass': basic_n,
        'note': '主板首板观察（东方财富涨停池派生）；基础口径=主板+首板+流通市值<120亿或流通股<4亿+换手率>2%+封板干净；K线严格过滤待云端K线步',
        'items': items,
    }
    return out, date, None

def main():
    # 2026-09-23 一劳永逸（主人令「一进二观察卡停更 2 天，修」·阿狸咪夜间窗口）：
    # ① 空档不覆盖——涨停池抓空（非交易日/源未更新/接口抖动）时，绝不写
    #    「total=0 + 新鲜 update_time」的空壳去覆盖好档（同族 cnfetch-empty-shell-block
    #    的教训：空壳会让卡片显示 0 只且把新鲜度刷假绿）。
    # ② 同日去重——盘后 post_close 三档（17:20/18:20/19:20 CST）只落第一档，
    #    同一交易日重复采集不再产生假 diff / 重复推送（不踩踏）。
    #    显式传日期参数（手动回补历史）时仍强制覆盖。
    date = sys.argv[1] if len(sys.argv) > 1 else None
    explicit = date is not None
    out, used_date, err = build(date)
    raw_path = os.path.join(ROOT, 'raw_data', 'board_first_limit.json')
    js_path = os.path.join(ROOT, 'data', 'BOARD_FIRST_LIMIT.js')
    if out is None:
        existing_total = None
        if os.path.exists(raw_path):
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    existing_total = json.load(f).get('total')
            except Exception:
                existing_total = None
        print('WARN:', err, '| date=', used_date,
              '→ 不覆盖既有档（防空壳），保住 total=%s 的上一轮好档' % existing_total)
        return
    existing = None
    if os.path.exists(raw_path):
        try:
            with open(raw_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = None
    if not explicit and existing and existing.get('date') == out.get('date') and existing.get('total', 0) > 0:
        print('SKIP: 交易日 %s 已采集（existing total=%s）→ 同日去重不重写'
              % (out.get('date'), existing.get('total')))
        return
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write('// 主板首板·一进二观察 —— 由 algorithms/fetch_board_first_limit.py 生成（东方财富涨停池派生）\n')
        f.write('window.BOARD_FIRST_LIMIT = ')
        f.write(json.dumps(out, ensure_ascii=False))
        f.write(';\n')
    print('OK date=%s total=%d basic_pass=%d -> %s / %s' % (used_date, out['total'], out['basic_pass'], raw_path, js_path))

if __name__ == '__main__':
    main()
