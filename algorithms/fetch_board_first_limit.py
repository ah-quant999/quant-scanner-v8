# -*- coding: utf-8 -*-
"""
主板首板 · 一进二观察 —— 数据生成器
====================================
数据源：akshare.stock_zt_pool_em（东方财富涨停池，云端 cloud_fetch_v8 同源）
        + 新浪日线（K 线严格过滤用；东财 push2his 本机与云端均被 WAF 拒 → 实测唯一可用源）
口径：主板（60/00 开头，剔除 688/92/30）+ 首板（连板数==1）
观察标签（基础口径，仅用涨停池快照即可判定，无需 K 线）：
  · 流通市值<120亿 或 流通股<4亿
  · 换手率>2%
  · 炸板次数==0（封板干净）
K 线严格过滤（忠实复刻「一进二」通达信公式，口径源 = 交付区
  《选股公式解读与审计_2026-09-21》+ 回测实现 E:/_alimi_tools/backtest/bt_yijiner.py
  的 components()；本文件不另创口径）：
  · 涨停确认     类MACD(EMA8-EMA55)金叉 + 类KDJ(K+D)回升
  · 大趋势       ZBJN17-ZBJN18>0（34日区间位置 EMA8/EMA5）
  · 量差 OR 控盘指数   5日均量<2.5×10日量标准差 ｜ EMA(EMA(C,13),13) 斜率>0
  · 量线粘合      max(MV5,MV20,MV60)/min(MV5,MV60) < 2.75（原公式 MIN(MIN(MV5,MV60),MV60) 笔误，忠实复刻）
  · 三线粘合      max(M8,M13,M21)/min(M8,M13,M21) < 1.0618
  · 角度60        |atan(MA60日变化率%)|<30°
  · 量<6.18×昨量、昨日非涨停、小盘(流通<4亿股 或 市值<120亿)、换手>2%
  ⚠️ 筹码穿刺分支依赖外部指标 SSRP（v8 无此源、定义未知）→ 按审计结论**砍除**，
     该 OR 分支由「量差 OR 控盘指数」承担（与 09-21 回测同口径）。
⚠️ 实测结论（交付区《一进二回测报告_2026-09-21》，面板层 1940 样本 / 1909 只）：
   A 口径（信号日收盘买）T+1~T+10 超额显著；B 口径（次日开盘买，散户真实可行）
   超额 ≈0、|t|<2 ⇒ **本卡是「观察/热度分层」，不是买点、不生成推荐**。

产出：
  raw_data/board_first_limit.json
  data/BOARD_FIRST_LIMIT.js  (window.BOARD_FIRST_LIMIT)
"""
import os, sys, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# K 线严格过滤口径版本：判定口径或取数源有实质变更时必须 +1
# （增量闸门 need_refresh() 据此判定「已采集档是否落后于当前口径」）
KLINE_VER = 1

# 严格过滤失败项的短标签（前端展示用，顺序=判定顺序）
_KLABEL = [
    ('zt', '涨停'), ('ztqr', '涨停确认'), ('minor', '量差/控盘'), ('bigtrend', '大趋势'),
    ('glue3', '三线粘合'), ('gluev', '量线粘合'), ('angle', '角度60'),
    ('volcap', '量<6.18昨量'), ('notprev', '昨日非涨停'), ('small', '小盘'), ('turn', '换手>2%'),
]


def _now_cst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def _latest_trading_day():
    """返回 YYYYMMDD；默认今天(CST)，调用方可覆盖。"""
    return _now_cst().strftime('%Y%m%d')


# ── 交易日历 + 已收盘交易日（2026-09-23 阿狸咪的工程师：错日根因修复）────────────
# 🔴 病灶：东财 getTopicZTPool 对「未收盘的今天 / 未来日」一律吐**最新存量池** ——
#   实测 date=20260924（未来日）返回内容与 20260923 完全相同；周六/周日 → 真返回空池。
#   ⇒ 原「空池才回溯」护栏对「未收盘的今天/未来日」**永不触发**：盘前 08:20 用 date=今天
#     请求即拿到上一交易日的池，却按「请求日」打标 ⇒ 卡面写「今日」实为昨日（假新鲜）。
# 🔴 正解：默认模式先用**交易日历**算出「最近一个已收盘定稿交易日」，只对该日查询；
#   查询空时才沿交易日历（只试真交易日）往前回溯。绝不接受未收盘/非交易日。
_CAL_CACHE = None


def _trade_calendar():
    """A股交易日历 set('YYYYMMDD')；akshare 不可用时返回 None（回退按周一~周五判定）。"""
    global _CAL_CACHE
    if _CAL_CACHE is not None:
        return _CAL_CACHE
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty and 'trade_date' in df.columns:
            _CAL_CACHE = set(str(x)[:10].replace('-', '') for x in df['trade_date'])
            return _CAL_CACHE
    except Exception as e:
        print('WARN: 交易日历获取失败(%s) → 回退按周一~周五判定' % e)
    _CAL_CACHE = None
    return None


def _is_trading_day(d):
    cal = _trade_calendar()
    if cal is not None:
        return d.strftime('%Y%m%d') in cal
    return d.weekday() < 5


def _last_closed_trading_day():
    """最近一个**已收盘定稿**的交易日（date 对象）。

    · 今天是交易日且已过 16:00 CST ⇒ 取今天（给源留定稿余量，避开 15:00 刚收盘未定稿）；
    · 否则（盘前 / 盘中 / 周末 / 节假日）⇒ 取上一个交易日。
    """
    now = _now_cst()
    d = now.date()
    if not (_is_trading_day(d) and (now.hour * 100 + now.minute) >= 1600):
        d = d - datetime.timedelta(days=1)
    for _ in range(20):
        if _is_trading_day(d):
            return d
        d = d - datetime.timedelta(days=1)
    return d


# ══════════════════════════════════════════════════════════════════════════════
# K 线取数（2026-09-23 阿狸咪的工程师：为「K线严格过滤」接入）
# ──────────────────────────────────────────────────────────────────────────────
# 源选择（实测，非推测）：本机对 push2his.eastmoney.com（含 52. 编号子域）与
#   akshare.stock_zh_a_hist（东财）一律 RemoteDisconnected（WAF 拒）；腾讯 gtimg
#   web.ifzq 返回 501；**新浪 money.finance.sina.com.cn getKLineData 返回 09-23 真值**。
#   ⇒ 主源=新浪原始日线（一次 HTTP，datalen=320；实测可返回 320 根）。
#   复权口径已比对：新浪原始与仓内 raw_data/kline_cache 同一日 OHLC 完全一致；
#   量单位差 100 倍（新浪=股 / 缓存=手）——六项过滤全为**比值口径**，不受影响。
# 回退：仓内 raw_data/kline_cache/<code>.json（已入仓·零网络可读），但其尾根日期
#   若 < 信号日 ⇒ 判 'stale'（**不算**过滤结果，绝不拿旧 K 线冒充当日）。
# ══════════════════════════════════════════════════════════════════════════════
_SINA_K = ('https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           'CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d')


def _sina_symbol(code):
    return ('sh' if code[0] == '6' else 'sz') + code


def _fetch_kline_net(code, bars=320):
    """新浪原始日线。返回升序 list[dict(date,open,high,low,close,volume)] 或 None。"""
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = _SINA_K % (_sina_symbol(code), bars)
    for _ in range(2):  # 一次重试（源抖动）
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://finance.sina.com.cn/',
            })
            raw = urllib.request.urlopen(req, timeout=20, context=ctx).read()
            arr = json.loads(raw.decode('utf-8', 'replace'))
            out = []
            for r in arr or []:
                out.append({
                    'date': str(r.get('day'))[:10],
                    'open': float(r.get('open')), 'high': float(r.get('high')),
                    'low': float(r.get('low')), 'close': float(r.get('close')),
                    'volume': float(r.get('volume')),
                })
            if len(out) >= 70:
                return out
        except Exception:
            continue
    return None


def _load_kline_cache(code):
    """仓内缓存兜底（可能陈旧）。返回升序 list 或 None。"""
    p = os.path.join(ROOT, 'raw_data', 'kline_cache', '%s.json' % code)
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
        rows = d if isinstance(d, list) else (d.get('klines') or d.get('data') or [])
        out = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            out.append({
                'date': str(r.get('date'))[:10],
                'open': float(r.get('open')), 'high': float(r.get('high')),
                'low': float(r.get('low')), 'close': float(r.get('close')),
                'volume': float(r.get('volume') or r.get('vol') or 0),
            })
        out.sort(key=lambda x: x['date'])
        return out if len(out) >= 70 else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# K 线严格过滤 —— 六项（忠实复刻 bt_yijiner.py components()，禁自创）
# ══════════════════════════════════════════════════════════════════════════════
def _strict_flags(rows, sig_date):
    """在**信号日截断**的日线序列上算六项过滤（因果：只用 <= sig_date 的数据）。

    返回 (flags:dict|None, read:dict|None)：
      flags 为 None ⇒ K 线未覆盖到信号日（'stale'）或长度不足，**不产出过滤结论**。
    """
    sub = [r for r in rows if r['date'] <= sig_date]
    if len(sub) < 70 or sub[-1]['date'] != sig_date:
        return None, None
    try:
        import numpy as np
        import pandas as pd
        import math

        def ema(s, n):
            return s.ewm(span=n, adjust=False).mean()

        df = pd.DataFrame(sub)
        C, H, L, V, O = df['close'], df['high'], df['low'], df['volume'], df['open']
        # ① 控盘指数：EMA(EMA(C,13),13) 变化率×1000 > 0
        v11 = ema(ema(C, 13), 13)
        kp = ((v11 - v11.shift(1)) / v11.shift(1) * 1000) > 0
        # ② 量差：MA(VOL,5) < 2.5 × STD(VOL,10)
        t1 = V.rolling(5, min_periods=5).mean()
        stdv = V.rolling(10, min_periods=10).std(ddof=1)
        lc = t1 < 2.5 * stdv
        # ③ 大趋势：ZBJN17-ZBJN18 > 0
        z11 = (2 * C + H + L) / 4
        z13 = L.rolling(34, min_periods=34).min()
        z16 = H.rolling(34, min_periods=34).max()
        z17 = ema((z11 - z13) / (z16 - z13) * 100, 8)
        z18 = ema(z17, 5)
        bigtrend = (z17 - z18) > 0
        # ④ 财神彩带 + 涨停确认
        cai = (ema(C, 8) - ema(C, 55)) * 5
        shen = ema(cai, 3)
        caib = cai >= shen
        rsv = ema((C - L.rolling(13, min_periods=13).min()) /
                  (H.rolling(13, min_periods=13).max() -
                   L.rolling(13, min_periods=13).min()) * 100, 3)
        k = ema(rsv, 3)
        dd = ema(k, 3)
        ls = k + dd
        gs = ema(ls.shift(1).fillna(ls.iloc[0] if len(ls) else np.nan), 1)
        ztqr = (ls > 0) & (ls >= gs) & caib
        # ⑤ 主板涨停 / 秒破板（入口）
        pc = C.shift(1)
        zt = ((C - pc) * 100 / pc >= 9.9) & (C == H)
        cb = (H > pc * 1.085) & (C > pc * 1.03) & (C < pc * 1.085) & (C > O)
        pb = (H > pc * 1.09955) & (C < H)
        m60 = C.rolling(60, min_periods=60).mean()
        spb = cb & pb & (C > m60 * 1.01) & (C < m60 * 1.05)
        # ⑥ 三线粘合 / 量线粘合 / 角度60
        m8, m13, m21 = C.rolling(8).mean(), C.rolling(13).mean(), C.rolling(21).mean()
        r3x = np.maximum(np.maximum(m8, m13), m21) / np.minimum(np.minimum(m8, m13), m21)
        mv5, mv20, mv60 = V.rolling(5).mean(), V.rolling(20).mean(), V.rolling(60).mean()
        rlx = np.maximum(np.maximum(mv5, mv20), mv60) / np.minimum(mv5, mv60)
        ang = (m60 / m60.shift(1) - 1) * 100
        ang_deg = np.abs(np.arctan(ang) * 180 / math.pi)

        i = len(df) - 1
        vr = float(V.iloc[i]) / float(V.iloc[i - 1]) if float(V.iloc[i - 1]) else 0.0
        flags = {
            'zt': bool(zt.iloc[i]) or bool(spb.iloc[i]),
            'ztqr': bool(ztqr.iloc[i]),
            'minor': bool(lc.iloc[i]) or bool(kp.iloc[i]),
            'bigtrend': bool(bigtrend.iloc[i]),
            'glue3': bool(r3x.iloc[i] < 1.0618),
            'gluev': bool(rlx.iloc[i] < 2.75),
            'angle': bool(ang_deg.iloc[i] < 30),
            'volcap': bool(vr < 6.18),
            'notprev': not bool(zt.iloc[i - 1]),
        }
        read = {
            'vol_ratio': round(vr, 2),
            'glue3_ratio': round(float(r3x.iloc[i]), 4) if r3x.iloc[i] == r3x.iloc[i] else None,
            'gluev_ratio': round(float(rlx.iloc[i]), 3) if rlx.iloc[i] == rlx.iloc[i] else None,
            'ang_deg': round(float(ang_deg.iloc[i]), 1) if ang_deg.iloc[i] == ang_deg.iloc[i] else None,
            'kp': bool(kp.iloc[i]),
            'lc': bool(lc.iloc[i]),
        }
        return flags, read
    except Exception as e:
        print('WARN: 严格过滤异常 %s: %s' % (sig_date, e))
        return None, None


def build(date=None):
    import akshare as ak
    explicit = date is not None
    if date is None:
        # 2026-09-23 修复：默认不再"以今天为起点试"，而是取最近一个**已收盘定稿交易日**
        date = _last_closed_trading_day().strftime('%Y%m%d')
    df = ak.stock_zt_pool_em(date=date)
    if (df is None or len(df) == 0) and not explicit:
        # 2026-09-23 修复（错日根因）：原「自然日回溯」在拿到未收盘/未来日的**存量池**时
        #   不触发（东财对这些日期返回最新存量而非空）⇒ 错标请求日。现改为**沿交易日历**
        #   往前找最近一个有池的交易日（≤7 个交易日），只试真交易日，杜绝存量池错标。
        _d0 = datetime.datetime.strptime(date, '%Y%m%d').date()
        _tried = 0
        for _i in range(1, 22):
            _d = _d0 - datetime.timedelta(days=_i)
            if not _is_trading_day(_d):
                continue
            _tried += 1
            _df = ak.stock_zt_pool_em(date=_d.strftime('%Y%m%d'))
            if _df is not None and len(_df) > 0:
                date = _d.strftime('%Y%m%d')
                df = _df
                print('BACKFILL: %s 无池 → 回溯到最近有池交易日 %s' % (
                    _d0.strftime('%Y%m%d'), date))
                break
            if _tried >= 7:
                break
    if df is None or len(df) == 0:
        return None, date, "当日无涨停池数据（非交易日或源未更新，含回溯 7 日）"
    cols = list(df.columns)
    sig_date = '%s-%s-%s' % (date[:4], date[4:6], date[6:8])
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
            '_size_ok': bool(size_ok),
            '_turn_ok': bool(turn_ok),
        })

    # ── K 线严格过滤 ────────────────────────────────────────────────────────
    # 对**全部候选**算，而非只算基础达标者：原公式的「一进二」并不含「炸板0次」
    #   （那是本卡基础口径的附加项）⇒ 严格达标与基础达标**非包含关系**，只算基础
    #   达标者会漏掉「严格达标但炸过板」的票。候选仅 20~40 只，取数成本可接受。
    n_kline_ok = 0
    for x in items:
        x['kline'] = 'skip'
        x['strict'] = False
        x['kmiss'] = []
        x['read'] = None
        rows = _fetch_kline_net(x['code'])
        src = 'sina'
        if rows is None:
            rows = _load_kline_cache(x['code'])
            src = 'cache'
        if rows is None:
            x['kline'] = 'na'
            continue
        flags, read = _strict_flags(rows, sig_date)
        if flags is None:
            x['kline'] = 'stale'      # K 线未覆盖到信号日 → 不给结论（不拿旧 K 线冒充）
            continue
        flags['small'] = x.pop('_size_ok')
        flags['turn'] = x.pop('_turn_ok')
        x['kline'] = 'ok'
        x['ksrc'] = src
        x['read'] = read
        x['kmiss'] = [lab for kk, lab in _KLABEL if not flags.get(kk)]
        x['strict'] = (len(x['kmiss']) == 0)
        n_kline_ok += 1
    for x in items:
        x.pop('_size_ok', None)
        x.pop('_turn_ok', None)
        x.pop('_turn_ok_used', None)

    # 排序：严格达标 → 基础达标 → 其余；同级按封板资金降序
    items.sort(key=lambda x: (not x.get('strict'), not x['basic_pass'], -x['seal']))
    basic_n = sum(1 for x in items if x['basic_pass'])
    strict_n = sum(1 for x in items if x.get('strict'))
    kna = sum(1 for x in items if x.get('kline') in ('na', 'stale'))
    out = {
        'update_time': _now_cst().strftime('%Y-%m-%d %H:%M:%S'),
        'date': date,
        'total': len(items),
        'basic_pass': basic_n,
        'strict_pass': strict_n,
        'kline_ok': n_kline_ok,
        'kline_na': kna,
        'kline_ver': KLINE_VER,
        'note': ('主板首板观察（东方财富涨停池派生·已收盘定稿交易日）；'
                 '基础口径=主板+首板+流通市值<120亿或流通股<4亿+换手率>2%+封板干净；'
                 'K线严格过滤=一进二公式六项（涨停确认/大趋势/量差或控盘指数/量线粘合/三线粘合/角度60+量<6.18昨量+昨日非涨停）；'
                 '筹码穿刺分支因外部指标SSRP缺失按审计砍除；实测次日开盘买超额≈0 ⇒ 观察分层非买点'),
        'items': items,
    }
    return out, date, None


# ══════════════════════════════════════════════════════════════════════════════
# 增量闸门（2026-09-23 阿狸咪的工程师）
# ──────────────────────────────────────────────────────────────────────────────
# 【为什么需要】涨停池是**收盘才定稿**的日频数据 ⇒ 盘前 / 盘中每一轮 run 都不可能
#   产出比上一交易日更新的内容；而本步原先「每轮刷新」（含周末 category=all）
#   ⇒ 盘中约 19 轮 × (交易日历 + 涨停池 + 32 只 K 线) 全是空转，属浪费。
# 【判据】仅当「已采集档的 date 落后于最近已收盘交易日」或「K 线口径版本落后」
#   或「K 线覆盖不足以支撑严格过滤（且未试满 3 次）」时才需要真抓。
#   全部不成立 ⇒ 早退（只花 1 次交易日历请求，不发涨停池 / K 线请求）。
# ══════════════════════════════════════════════════════════════════════════════
_KL_TRIES_MAX = 3


def _raw_path():
    return os.path.join(ROOT, 'raw_data', 'board_first_limit.json')


def need_refresh():
    """是否需要重新采集（workflow 与生成器共用，单一真源）。"""
    try:
        with open(_raw_path(), 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return True, '无既有档'
    want = _last_closed_trading_day().strftime('%Y%m%d')
    if str(d.get('date')) != want:
        return True, '既有 date=%s 落后于最近已收盘交易日 %s' % (d.get('date'), want)
    if int(d.get('total') or 0) <= 0:
        return True, '既有档为空壳(total<=0)'
    if int(d.get('kline_ver') or 0) != KLINE_VER:
        return True, 'K 线口径版本落后(%s→%s)' % (d.get('kline_ver'), KLINE_VER)
    total = int(d.get('total') or 0)
    if int(d.get('kline_ok') or 0) >= total * 0.8:
        return False, '已采集且严格过滤 K 线覆盖充足'
    if int(d.get('kline_try') or 0) >= _KL_TRIES_MAX:
        return False, 'K 线不足但已试满 %d 次（今日不再重试，防风暴）' % _KL_TRIES_MAX
    return True, 'K 线覆盖不足(kline_ok=%s/%s)，重试' % (d.get('kline_ok'), total)


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
    if not explicit:
        need, why = need_refresh()
        if not need:
            print('SKIP: %s → 不重抓（增量闸门，零冗余请求）' % why)
            return
        print('NEED: %s' % why)
    out, used_date, err = build(date)
    raw_path = _raw_path()
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
    prev_same = bool(existing and existing.get('date') == out.get('date'))
    # K 线重试计数（同一交易日内累加，供增量闸门封顶，防「源不可用→每轮重试」风暴）
    out['kline_try'] = (int(existing.get('kline_try') or 0) + 1) if prev_same else 1
    if (not explicit and prev_same and existing.get('total', 0) > 0
            and int(existing.get('kline_ver') or 0) == KLINE_VER
            and int(existing.get('kline_ok') or 0) >= int(existing.get('total') or 0) * 0.8):
        print('SKIP: 交易日 %s 已采集且 K 线覆盖充足（existing total=%s kline_ok=%s）→ 不重写'
              % (out.get('date'), existing.get('total'), existing.get('kline_ok')))
        return
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write('// 主板首板·一进二观察 —— 由 algorithms/fetch_board_first_limit.py 生成（东方财富涨停池派生 + 新浪日线严格过滤）\n')
        f.write('window.BOARD_FIRST_LIMIT = ')
        f.write(json.dumps(out, ensure_ascii=False))
        f.write(';\n')
    print('OK date=%s total=%d basic_pass=%d strict_pass=%d kline_ok=%d kline_na=%d -> %s / %s'
          % (used_date, out['total'], out['basic_pass'], out['strict_pass'],
             out['kline_ok'], out['kline_na'], raw_path, js_path))


if __name__ == '__main__':
    main()
