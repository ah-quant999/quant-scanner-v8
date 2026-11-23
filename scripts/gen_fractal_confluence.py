#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 分型×v8五层共振·回测生成器（2026-11-23 主人令「做」）
=========================================================
问题：裸顶底分型对上证指数几乎无预测力（36年实测 裸底分型 T+5 胜率51.2%/均值+0.13%，
      弱于随机日 53.5%/+0.30%；空头区底分型 48.3%/-0.05% 负期望）。
本生成器验证：叠加过滤层后胜率/期望能否拉正——
  L2 位置层：MA60 多头/空头区（回测可验证 ✅）
  L2+ 超卖/超买：KDJ(9,3,3) J 值极端（回测可验证 ✅）
  L3 量能层：缩量/放量 vs 5日均量（回测可验证 ✅）
  L4 情绪冰点：近10日有单日 ≤-1.5% 急跌（恐慌释放）/ ≥+2% 冲高（回测可验证 ✅）
  L1 资金层（主力净额）与 L5 regime 层：历史深度不足（资金流仅120天、regime 为现行产物）
  → 无法纳入历史回测，【MISSING】如实标注，不在卡内声称已验证。
诚实边界：仅上证指数日线上证自身统计；样本内统计非未来承诺；不构成投资建议。
产出：data/FRACTAL_CONFLUENCE.js（window.FRACTAL_CONFLUENCE）
2026-11-23 13:15 主人令「周度？不能实时？」→ 实时化改造：
  ① 当下判读盘中实时：历史日K（收盘定稿）+ 东财 push2delay 实时 bar（价格/高低/量）合成，
     盘中每轮（~20min）随数据链重算，当下判读随最新价跳动；
  ② 回测统计静态：仅用「已收盘定稿」K线计算（今日未走完的 bar 绝不混入统计口径，防盘中
     半根K线污染胜率表）；胜率表本身是历史统计，不随盘中变化（重算结果不变，零成本）。
  ③ 历史双路：新浪 stock_zh_index_daily → 东财 stock_zh_index_daily_em 兜底。
  ④ 实时源：东财 push2delay ulist（与 f_index_quotes 同源镜像；cn runner 主力链已验证可达）。
  ⑤ 诚实护栏：盘中成交量未满日 ⇒ vol_shrink 置 None（半日量 vs 5日全量均量不可比），
     today.live=true 标注「盘中实时」；实时源失败 ⇒ 回落昨日收盘口径（live=false），不编造。
"""
import json, sys, datetime
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    print("FATAL: akshare 未安装", file=sys.stderr); sys.exit(2)

try:
    import requests
except ImportError:
    requests = None

OUT = "data/FRACTAL_CONFLUENCE.js"
SAMPLE_START = "2005-01-01"  # 股改后现代市场口径
_EM_DELAY = "https://push2delay.eastmoney.com"
_EM_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _bj_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def load_index():
    """历史日K（仅已收盘定稿 bar）：新浪主路 → 东财兜底双路。"""
    df = None
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
    except Exception as e:
        print(f"⚠️ 新浪日线失败，退东财: {e}", file=sys.stderr)
    if df is None or len(df) == 0:
        df = ak.stock_zh_index_daily_em(symbol="000001")
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[df['date'] >= SAMPLE_START].reset_index(drop=True)
    return df


def fetch_realtime_bar():
    """今日上证实时 bar，三源级联：东财 push2delay → 新浪 hq.sinajs → 腾讯 qt.gtimg。

    仅返回「今日确有交易」的 bar（volume==0 = 盘前/停牌 ⇒ None，绝不合并空 bar）。
    各源成交量统一手数口径（与新浪/东财日线一致）。失败返回 None → 当下判读回落
    昨日收盘口径（live=false），不编造。"""
    today = _bj_now().strftime("%Y-%m-%d")

    def _ok(b):
        return b and b.get("close", 0) > 0 and b.get("high", 0) > 0 and b.get("low", 0) > 0 and b.get("volume", 0) > 0

    # ① 东财 push2delay（cn runner 主力链已验证可达；f2价 f5量手 f15高 f16低 f17开）
    if requests is not None:
        for attempt in range(2):
            try:
                r = requests.get(
                    _EM_DELAY + "/api/qt/ulist.np/get",
                    params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                            "fields": "f2,f5,f15,f16,f17,f18", "secids": "1.000001"},
                    headers=_EM_HEADERS, timeout=12)
                j = r.json()
                diff = (j.get("data") or {}).get("diff") or []
                if isinstance(diff, dict):
                    diff = list(diff.values())
                if diff:
                    d0 = diff[0]
                    b = dict(date=today, open=float(d0.get("f17") or 0),
                             high=float(d0.get("f15") or 0), low=float(d0.get("f16") or 0),
                             close=float(d0.get("f2") or 0), volume=float(d0.get("f5") or 0))
                    if _ok(b):
                        return b
            except Exception as e:
                print(f"  ⚠️ 东财实时(尝试{attempt+1}/2): {e}", file=sys.stderr)
        # ② 新浪全量行情（本机实测可达；字段 1开 2昨收 3现价 4高 5低 8量手 30日期 31时间）
        try:
            r = requests.get("https://hq.sinajs.cn/list=sh000001", timeout=12,
                             headers={"Referer": "https://finance.sina.com.cn", **_EM_HEADERS})
            f = r.text.split('"')[1].split(',')
            b = dict(date=f[30], open=float(f[1]), high=float(f[4]), low=float(f[5]),
                     close=float(f[3]), volume=float(f[8]))
            if _ok(b) and b["date"] == today:
                return b
        except Exception as e:
            print(f"  ⚠️ 新浪实时失败: {e}", file=sys.stderr)
        # ③ 腾讯 qt.gtimg（字段 1名 3现价 4昨收 5开 6量手 33高 34低）
        try:
            r = requests.get("https://qt.gtimg.cn/q=sh000001", timeout=12, headers=_EM_HEADERS)
            f = r.text.split('"')[1].split('~')
            b = dict(date=today, open=float(f[5]), high=float(f[33]), low=float(f[34]),
                     close=float(f[3]), volume=float(f[6]))
            if _ok(b):
                return b
        except Exception as e:
            print(f"  ⚠️ 腾讯实时失败: {e}", file=sys.stderr)
    return None


def merge_live_bar(df_hist):
    """把今日实时 bar 合成进历史（返回 (df_live, live_flag)）。统计口径不用它，只用于当下判读。"""
    bar = fetch_realtime_bar()
    if bar is None:
        return df_hist, False
    last_d = str(df_hist['date'].iloc[-1].date())
    row = pd.DataFrame([{"date": pd.to_datetime(bar["date"]), "open": bar["open"],
                         "high": bar["high"], "low": bar["low"], "close": bar["close"],
                         "volume": bar["volume"]}])
    if last_d == bar["date"]:
        df_live = pd.concat([df_hist.iloc[:-1], row], ignore_index=True)
    elif last_d < bar["date"]:
        df_live = pd.concat([df_hist, row], ignore_index=True)
    else:  # 历史比实时还新（异常）→ 不合并
        return df_hist, False
    return df_live, True

def kdj(df, n=9):
    low_n = df['low'].rolling(n).min()
    high_n = df['high'].rolling(n).max()
    rsv = (df['close'] - low_n) / (high_n - low_n) * 100
    K = np.zeros(len(df)); D = np.zeros(len(df))
    K[:] = np.nan; D[:] = np.nan
    kv, dv = 50.0, 50.0
    for i in range(len(df)):
        r = rsv.iloc[i]
        if pd.isna(r): K[i], D[i] = kv, dv; continue
        kv = 2/3*kv + 1/3*r
        dv = 2/3*dv + 1/3*kv
        K[i], D[i] = kv, dv
    J = 3*K - 2*D
    return K, D, J

def build_variants(df, kind):
    """kind='bottom'|'top'；返回变体列表"""
    H, L, C, V = df['high'].values, df['low'].values, df['close'].values, df['volume'].values.astype(float)
    _, _, J = kdj(df)
    n = len(df)
    ma60 = df['close'].rolling(60).mean().values
    vma5 = df['volume'].rolling(5).mean().values
    hi250 = df['high'].rolling(250).max().values
    ret1 = np.concatenate([[0], (C[1:] / C[:-1] - 1) * 100])

    idxs = []
    for i in range(1, n - 1):
        if kind == 'bottom' and L[i] < L[i-1] and L[i] < L[i+1]: idxs.append(i)
        if kind == 'top' and H[i] > H[i-1] and H[i] > H[i+1]: idxs.append(i)

    def fwd(i):
        c = i + 1  # 确认日=第三根K收盘
        if c + 20 >= n or pd.isna(ma60[c]): return None
        return dict(r5=(C[c+5]/C[c]-1)*100, r10=(C[c+10]/C[c]-1)*100, r20=(C[c+20]/C[c]-1)*100,
                    above=bool(C[c] > ma60[c]), j=float(J[c]) if not np.isnan(J[c]) else 50.0,
                    shrink=bool(V[i] < vma5[i] * 0.85) if not np.isnan(vma5[i]) else False,
                    expand=bool(V[i] > vma5[i] * 1.2) if not np.isnan(vma5[i]) else False,
                    drop10=bool((ret1[c-9:c+1] <= -1.5).any()),
                    pop10=bool((ret1[c-9:c+1] >= 2.0).any()),
                    dev250=float(C[c] / hi250[c] - 1) if not np.isnan(hi250[c]) else 0.0)

    recs = []
    for i in idxs:
        f = fwd(i)
        if f: recs.append(f)
    d = pd.DataFrame(recs)
    return d

def summarize(d, mask_fn, name, note, kind):
    sub = d[mask_fn(d)] if mask_fn is not None else d
    if kind == 'bottom':
        wr5 = float((sub.r5 > 0).mean() * 100) if len(sub) else None
    else:  # 顶分型：看跌信号，胜率=跌的概率
        wr5 = float((sub.r5 < 0).mean() * 100) if len(sub) else None
    return dict(name=name, note=note, n=int(len(sub)),
                wr5=round(wr5, 1) if wr5 is not None else None,
                m5=round(float(sub.r5.mean()), 2) if len(sub) else None,
                m10=round(float(sub.r10.mean()), 2) if len(sub) else None,
                m20=round(float(sub.r20.mean()), 2) if len(sub) else None)

def main():
    df = load_index()
    print(f"样本: {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()} | {len(df)} 交易日")
    rand = None
    # 随机对照
    H, C = df['high'].values, df['close'].values
    n = len(df)
    rng = np.random.default_rng(7)
    pick = rng.choice(range(60, n - 21), 3000, replace=False)
    rand = dict(n=3000, wr5=round(float(np.mean([(C[i+5]/C[i]-1) > 0 for i in pick]) * 100), 1),
                m5=round(float(np.mean([(C[i+5]/C[i]-1)*100 for i in pick])), 2))

    out = dict(update_time=_bj_now().strftime("%Y-%m-%d %H:%M:%S"),
               sample=dict(start=str(df['date'].iloc[0].date()), end=str(df['date'].iloc[-1].date()), days=int(len(df))),
               random_baseline=rand, source="新浪/东财双路日K + 东财push2delay实时bar合成", missing_layers="")

    # ===== 底分型 =====
    db = build_variants(df, 'bottom')
    bot = [
        summarize(db, None, "裸底分型（基线）", "无过滤", 'bottom'),
        summarize(db, lambda d: ~d.above, "空头区(<MA60)", "L2位置", 'bottom'),
        summarize(db, lambda d: d.above, "多头区(>MA60)", "L2位置", 'bottom'),
        summarize(db, lambda d: (~d.above) & (d.j < 10), "空头区+KDJ_J<10 超卖", "L2位置+超卖", 'bottom'),
        summarize(db, lambda d: (~d.above) & d.shrink, "空头区+缩量(<5日均量0.85)", "L2位置+L3量能", 'bottom'),
        summarize(db, lambda d: (~d.above) & d.drop10, "空头区+近10日急跌≤-1.5%", "L2位置+L4冰点", 'bottom'),
        summarize(db, lambda d: (~d.above) & (d.j < 10) & d.drop10, "空头区+超卖+急跌冰点", "L2+超卖+L4", 'bottom'),
        summarize(db, lambda d: (~d.above) & (d.j < 10) & d.drop10 & d.shrink, "四重共振：空头+超卖+急跌+缩量", "L2+超卖+L4+L3", 'bottom'),
        summarize(db, lambda d: d.above & d.shrink, "多头区缩量回踩", "L2+L3", 'bottom'),
    ]
    out['bottom'] = bot

    # ===== 顶分型 =====
    dt = build_variants(df, 'top')
    top = [
        summarize(dt, None, "裸顶分型（基线）", "无过滤", 'top'),
        summarize(dt, lambda d: d.above, "多头区(>MA60)逃顶", "L2位置", 'top'),
        summarize(dt, lambda d: d.above & (d.j > 90), "多头区+KDJ_J>90 超买", "L2+超买", 'top'),
        summarize(dt, lambda d: d.above & d.expand, "多头区+放量(>5日均量1.2)", "L2+L3量能", 'top'),
        summarize(dt, lambda d: d.above & d.pop10, "多头区+近10日冲高≥+2%", "L2+L4冲高", 'top'),
        summarize(dt, lambda d: d.above & (d.j > 90) & d.expand, "三重共振：多头+超买+放量", "L2+超买+L3", 'top'),
        summarize(dt, lambda d: d.above & (d.j > 90) & d.expand & d.pop10, "四重共振：多头+超买+放量+冲高", "L2+超买+L3+L4", 'top'),
    ]
    out['top'] = top

    # ===== 当下判读（2026-11-23 实时化：历史定稿bar + 东财实时bar 合成）=====
    df_live, live = merge_live_bar(df)
    C2 = df_live['close'].values; V2 = df_live['volume'].values.astype(float)
    _, _, J2 = kdj(df_live)
    ma60v = df_live['close'].rolling(60).mean().values
    hi250v = df_live['high'].rolling(250).max().values
    nL = len(df_live)
    vma5_live = df_live['volume'].rolling(5).mean().values
    last_bot, last_top = None, None
    LH = df_live['low'].values; HH = df_live['high'].values
    for i in range(nL - 2, 1, -1):
        if last_bot is None and LH[i] < LH[i-1] and LH[i] < LH[i+1]:
            last_bot = str(df_live['date'].iloc[i].date())
        if last_top is None and HH[i] > HH[i-1] and HH[i] > HH[i+1]:
            last_top = str(df_live['date'].iloc[i].date())
        if last_bot and last_top: break
    # 盘中成交量未满日 ⇒ 量能对比失真（半日量 vs 5日全量均量）→ 如实置 None，不判量
    bj = _bj_now()
    hhmm = bj.strftime("%H%M")
    in_session = 930 <= int(hhmm) <= 1500 and bj.weekday() < 5
    vol_shrink = None if (live and in_session) else bool(V2[-1] < vma5_live[-1] * 0.85)
    out['today'] = dict(date=str(df_live['date'].iloc[-1].date()), close=float(C2[-1]),
                        above_ma60=bool(C2[-1] > ma60v[-1]), kdj_j=round(float(J2[-1]), 1),
                        dev250=round(float(C2[-1] / hi250v[-1] - 1) * 100, 2),
                        vol_shrink=vol_shrink,
                        live=bool(live), as_of=bj.strftime("%H:%M"),
                        last_bottom=last_bot, last_top=last_top)

    out['missing_layers'] = "L1主力资金（东财板块历史仅120天）、L5 regime（现行产物无历史）无法纳入历史回测【MISSING】；本回测覆盖 L2位置/L3量能/L4情绪冰点 三层可验证部分"
    out['boundary'] = "样本内统计≠未来承诺；指数日线口径；分型确认滞后1根K线已计入；不构成投资建议"

    js = "window.FRACTAL_CONFLUENCE = " + json.dumps(out, ensure_ascii=False, indent=1) + ";"
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(js)
    print(f"✅ 已生成 {OUT} ({len(js)} chars)")
    for r in bot: print("底:", r['name'], "| n=", r['n'], "| wr5=", r['wr5'], "| m5=", r['m5'])
    for r in top: print("顶:", r['name'], "| n=", r['n'], "| wr5=", r['wr5'], "| m5=", r['m5'])

if __name__ == '__main__':
    main()
