# -*- coding: utf-8 -*-
"""
v8/gen_algo_scorecard.py —— 「算法记分卡」规则聚合（盘后生成，落 data/ALGO_SCORECARD.js）

数据源：raw_data/backtest_all_algos.json（全链回测·真实信号流口径，含基准超额与诚实闸门）。
铁律（沿用回测链 honesty_note）：未知一律 null（前端显示 —），绝不用 0 冒充；
  样本 < min_samples(30) 只观测、不进排名、不做下架评估；研究型不与交易型同列比较。
输出 schema（window.ALGO_SCORECARD）：
  ranked  : 样本≥30 交易型算法（按均收降序），每卡取代表行（is_primary 优先，否则样本最大行）
  watch   : 样本<30 或未就绪的交易型算法（观察名单）
  research: 研究型（因子实验室 / K线信号层）摘要
  oneline : 一句话结论（规则拼装，数值全真实）
"""
import json, os, sys, datetime
from algo_gate_thresholds import (LOW_WIN_RATE as G_LOW_WIN, LOW_AVG_RETURN as G_LOW_RET,
                                  ADMIT_MIN_SAMPLES, ADMIT_MIN_EXCESS, ADMIT_MAX_WORST_TRADE, ADMIT_MAX_CORR_TOP,
                                  ADMIT_MIN_MARKETS, ADMIT_PENDING_FIELDS, OBSERVE_PERIOD)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def bj_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def load(p):
    try:
        return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))
    except Exception as e:
        print('ERR load', p, e); return None

bt = load('raw_data/backtest_all_algos.json')
if not bt or not bt.get('rows'):
    print('❌ backtest_all_algos.json 未就绪，退出'); sys.exit(1)

MIN_SAMPLES = bt.get('min_samples') or 30
rows = bt['rows']

# ── 1) 交易型各卡代表行（cat=trade；is_primary 优先，否则样本最大行）──
#   🔴 因子实验室 = 研究型（因子分层），按回测链 honesty_note 不与交易型同列排名 → 只进 research 区
rep = {}
for r in rows:
    if r.get('cat') != 'trade' or r['card'] == '因子实验室':
        continue
    k = r['card']
    cur = rep.get(k)
    if cur is None or r.get('is_primary') or ((r.get('sample') or 0) > (cur.get('sample') or 0) and not cur.get('is_primary')):
        rep[k] = r

def _gate_of(item, raw_row):
    """🆕 双向闸门状态机（阈值来自 algo_gate_thresholds.py 权威源）：
       'admit'(🟢准入) / 'demote_candidate'(🔴降级候选) / 'incubate'(🟡孵化观察)"""
    n = item.get('sample') or 0
    if n < MIN_SAMPLES:
        return 'incubate'  # 样本不足，只观测不评级
    # 🔴 降级候选：跌破红线 或 未过准入却已在榜（admit_eligible 为 False；缺失则不计）
    below = (item.get('win_rate') is not None and item['win_rate'] < G_LOW_WIN) or \
            (item.get('avg_return') is not None and item['avg_return'] <= G_LOW_RET)
    admit = raw_row.get('admit_eligible')
    if below or (admit is False):
        return 'demote_candidate'
    return 'admit'

def _fmt_row(r, card_rows):
    ex = r.get('extra') or {}
    bench = ex.get('bench_avg_return')
    avg = r.get('avg_return')
    # 同卡最佳持有期（样本≥min_samples 中均收最高；诚实：不足则 null）
    best = None
    for cr in card_rows:
        if (cr.get('sample') or 0) >= MIN_SAMPLES and cr.get('avg_return') is not None:
            if best is None or cr['avg_return'] > best['avg_return']:
                best = cr
    return {
        'card': r['card'], 'icon': r.get('icon') or '', 'page': r.get('page') or '',
        'hold': r.get('hold'), 'sample': r.get('sample'),
        'win_rate': r.get('win_rate'), 'avg_return': avg,
        'max_drawdown': ex.get('max_drawdown'), 'bench': bench,
        'excess': (round(avg - bench, 2) if (avg is not None and bench is not None) else None),
        'best_hold': (best.get('hold') if best else None),
        'best_ret': (best.get('avg_return') if best else None),
        'fresh': r.get('fresh'), 'status': r.get('status') or '',
        'source_time': r.get('source_time') or '',
    }

ranked, watch = [], []
for card, r in rep.items():
    card_rows = [x for x in rows if x['card'] == card and x.get('cat') == 'trade']
    item = _fmt_row(r, card_rows)
    item['gate'] = _gate_of(item, r)  # 🆕 双向闸门状态机
    if (item['sample'] or 0) >= MIN_SAMPLES and item['win_rate'] is not None:
        ranked.append(item)
    else:
        watch.append(item)

ranked.sort(key=lambda x: (x['avg_return'] if x['avg_return'] is not None else -999), reverse=True)
watch.sort(key=lambda x: (x['avg_return'] if x['avg_return'] is not None else -999), reverse=True)

# ── 2) 研究型摘要（不与交易型同列比较） ──
research = []
fac = [r for r in rows if r['card'] == '因子实验室' and r.get('cat') == 'trade' and (r.get('sample') or 0) >= MIN_SAMPLES]
if fac:
    b = max(fac, key=lambda x: x['avg_return'] or -999)
    research.append({'card': '因子实验室', 'icon': '🧪', 'note': '因子分层研究（样本 %s，最佳 %s 胜率 %s%%·均收 %s%%）——研究型，不与交易型同列排名'
                     % (b.get('sample'), b.get('hold'), b.get('win_rate'), b.get('avg_return'))})
sig = [r for r in rows if r.get('cat') == 'signal']
if sig:
    ok = [r for r in sig if r.get('win_rate') is not None and r.get('avg_return') is not None]
    b = max(ok, key=lambda x: x['avg_return']) if ok else None
    research.append({'card': 'K线信号层', 'icon': '🕯', 'note': '信号层测试 %d 项（%s）'
                     % (len(sig), ('最优：%s %s 胜率 %s%%·均收 %s%%' % (b.get('label') or '', b.get('hold') or '', b.get('win_rate'), b.get('avg_return'))) if b else '全部未知（诚实留白）')})

# ── 3) 一句话结论（规则拼装） ──
def _oneline():
    if not ranked:
        return '样本≥30 的交易型算法暂无（回测链未就绪），观察名单 %d 家。' % len(watch)
    t, w = ranked[0], ranked[-1]
    s = '样本≥30 交易型算法 %d 家：最强 %s%s（胜率 %s%%·均收 %+s%%' % (
        len(ranked), t['card'], t['hold'] or '', t['win_rate'], t['avg_return'])
    if t['excess'] is not None:
        s += '·超额 %+s%%' % t['excess']
    s += '）；最弱 %s%s（胜率 %s%%·均收 %+s%%）。' % (
        w['card'], w['hold'] or '', w['win_rate'], w['avg_return'])
    demote = [x for x in ranked if x.get('gate') == 'demote_candidate']
    low = [x for x in ranked if (x['win_rate'] or 0) < (bt.get('low_win_rate') or 45) or (x['avg_return'] or 0) <= (bt.get('low_avg_return') or 0)]
    if demote:
        s += '🔴降级候选 %d 家（跌破闸门，观察期 %d 笔自动裁决去留）：%s。' % (
            len(demote), OBSERVE_PERIOD, '、'.join(x['card'] for x in demote))
    elif low:
        s += '低于闸门（胜率<%s%% 或 均收≤%s%%）：%s —— 跑满观察期再裁决去留。' % (
            bt.get('low_win_rate') or 45, bt.get('low_avg_return') or 0, '、'.join(x['card'] for x in low))
    return s

out = {
    'data_date': bt.get('data_day'),
    'update_time': bj_now().strftime('%Y-%m-%d %H:%M:%S'),
    'source_time': bt.get('update_time'),
    'oneline': _oneline(),
    'ranked': ranked,
    'watch': watch,
    'research': research,
    'gates': {
        'min_samples': MIN_SAMPLES,
        'low_win_rate': bt.get('low_win_rate'),
        'low_avg_return': bt.get('low_avg_return'),
        'admit_min_samples': ADMIT_MIN_SAMPLES,
        'admit_min_excess': ADMIT_MIN_EXCESS,
        'admit_max_worst_trade': ADMIT_MAX_WORST_TRADE,
        'admit_max_corr_top': ADMIT_MAX_CORR_TOP,
        'admit_min_markets': ADMIT_MIN_MARKETS,
        'observe_period': OBSERVE_PERIOD,
        'admit_pending_fields': ADMIT_PENDING_FIELDS,
        'honesty_note': bt.get('honesty_note'),
        'bench_note': bt.get('bench_note'),
        'chain_note': bt.get('chain_note'),
    },
    'method': '记分 = 全链回测真实信号流（次开买入/同持有期/扣双边 0.3%）+ 全市场等权基准超额；样本≥30 才进榜，未知一律留白不用 0 冒充。',
    'disclaimer': '历史回测不代表未来收益；记分卡用于算法去留裁决参考，不构成投资建议。',
}

with open(os.path.join(ROOT, 'data/ALGO_SCORECARD.js'), 'w', encoding='utf-8') as f:
    f.write('window.ALGO_SCORECARD = ' + json.dumps(out, ensure_ascii=False, indent=2) + ';')

print('✅ ALGO_SCORECARD.js 生成： ranked=%d watch=%d research=%d' % (len(ranked), len(watch), len(research)))
for x in ranked:
    print('  🏆 %s%s 样本%s 胜率%s%% 均收%+s%% 超额%s' % (x['icon'], x['card'], x['sample'], x['win_rate'], x['avg_return'], x['excess']))
for x in watch:
    print('  👀 %s 样本%s' % (x['card'], x['sample']))
print('oneline:', out['oneline'])
