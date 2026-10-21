# -*- coding: utf-8 -*-
"""
v8/gen_national_team.py —— 「国家队活跃度」复合信号（盘后规则生成，落 data/NATIONAL_TEAM.js）

设计原则（主人铁律：绝不编造）：
  - 全部数值来自仓内真实数据源；
  - 任一子源缺失 ⇒ 该子项标「未接入/未就绪」，权重按比例重分给其余可用子项；
  - 本指标是「国家队托盘」的代理推算，非汇金官方持仓披露（季报滞后 1-3 月），
    卡面明确标注「代理·非实时」与「滞后说明」。

子信号（权重合计 100%，缺失项权重重分）：
  A. 宽基ETF净申购突变（45%）  ← etf_subscription_eastmoney.js（东财口径·股票型 top_sub 宽基净申购额）
  B. 大金融相对强度（35%）     ← SECTOR_RS.js（银行/证券/保险/多元金融 relative_5d 均值）
  C. 大金融资金净流入（20%）   ← SECTOR_FUND_FLOW.js（银行/证券 板块净流入合计）
  D. 汇金持仓环比（未接入）    ← v8 无季报股东源 ⇒ 永远「未接入」，仅占位说明
"""
import json, os, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

def load(p):
    try:
        s = open(os.path.join(ROOT, p), encoding='utf-8').read()
        return json.loads(s[s.index('{'):s.rindex('}')+1])
    except Exception as e:
        return None

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def bj_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

# ── A. 宽基ETF净申购突变 ──────────────────────────────────────────────
KW_BROAD = ['沪深300','中证500','中证1000','50ETF','科创50','创业板','中证A500','中证2000',
            '300ETF','华夏300','500ETF','1000ETF','A500','科创综']
a_val = None; a_detail = None; a_ready = False
e = load('data/etf_subscription_eastmoney.js')
if e:
    stock = (e.get('categories') or {}).get('股票型') or {}
    subs = stock.get('top_sub') or []
    broad = [s for s in subs if any(k in (s.get('name') or '') for k in KW_BROAD)]
    net = sum((s.get('d_amount_yi') or 0) for s in broad)
    a_val = round(net, 1)
    a_detail = '宽基净申购 %.1f 亿（%d 只宽基ETF）' % (net, len(broad))
    a_ready = True

# ── B. 大金融相对强度 ────────────────────────────────────────────────
KW_FIN = ['银行','证券','保险','多元金融']
b_val = None; b_detail = None; b_ready = False
rs = load('data/SECTOR_RS.js')
if rs and rs.get('sectors'):
    fins = [s for s in rs['sectors'] if (s.get('name') or '') in KW_FIN]
    if fins:
        rels = [ (s.get('relative_5d') or 0) for s in fins ]
        b_val = round(sum(rels)/len(rels), 2)
        b_detail = '大金融 relative_5d 均值 %.2f%%（%s）' % (b_val, '/'.join(s.get('name') for s in fins))
        b_ready = True

# ── C. 大金融资金净流入 ──────────────────────────────────────────────
c_val = None; c_detail = None; c_ready = False
sf = load('data/SECTOR_FUND_FLOW.js')
if sf:
    names_in = { (x.get('name') or ''): (x.get('net') or 0) for x in (sf.get('sectors_in') or []) }
    top = { (x.get('name') or ''): (x.get('net') or 0) for x in (sf.get('top_list') or []) }
    fin_net = 0.0; hit = []
    for kw in KW_FIN:
        v = names_in.get(kw)
        if v is None: v = top.get(kw)
        if v is not None:
            fin_net += v; hit.append('%s %.1f' % (kw, v))
    if hit:
        c_val = round(fin_net, 1)
        c_detail = '大金融净流入 %.1f 亿（%s）' % (fin_net, ';'.join(hit))
        c_ready = True

# ── D. 汇金持仓环比（未接入） ────────────────────────────────────────
d_ready = False

# ── 权重重分 + 计分 ─────────────────────────────────────────────────
W = {'A':45, 'B':35, 'C':20, 'D':0}
ready = {'A':a_ready, 'B':b_ready, 'C':c_ready, 'D':d_ready}
base = {'A':50 + (a_val or 0)/2, 'B':50 + (b_val or 0)*4, 'C':50 + (c_val or 0)/3}
# 仅对就绪项计分；缺失项权重按比例分给就绪项
tot_w = sum(W[k] for k in W if ready[k])
score = 0.0
for k in ['A','B','C']:
    if ready[k]:
        score += clamp(base[k], 10, 100) * (W[k]/tot_w if tot_w else 0)
score = round(score, 1) if tot_w else None

def verdict(s):
    if s is None: return ('未就绪', '#9ca3af')
    if s >= 70: return ('高活跃·国家队明确托盘', '#ef5350')
    if s >= 55: return ('偏活跃', '#f59e0b')
    if s >= 40: return ('中性', '#38bdf8')
    return ('静默·未见托盘', '#26a69a')

vtxt, vcol = verdict(score)

# ── 一句话结论（规则拼装自子信号状态，数值全部来自真实源，禁编造） ──
sc_str = ('—' if score is None else '%.1f' % score)
def _oneline():
    if score is None:
        return '数据未就绪，无法给出结论。'
    parts = []
    if a_val is not None:
        if a_val > 40:   parts.append('宽基ETF净申购 %.1f 亿＝国资托盘指纹明确' % a_val)
        elif a_val >= 0: parts.append('宽基ETF净申购 %.1f 亿＝托盘力度中性' % a_val)
        else:            parts.append('宽基ETF净赎回 %.1f 亿＝未见托盘' % a_val)
    if b_val is not None:
        if b_val > 1:    parts.append('大金融强势')
        elif b_val < -1: parts.append('大金融弱势')
        else:            parts.append('大金融中性')
    if c_val is not None:
        parts.append('大金融资金净%s %.1f 亿' % ('流入' if c_val > 0 else '流出', abs(c_val)))
    if not parts:
        return '数据未就绪。'
    tail = ''
    if a_val is not None and b_val is not None:
        if a_val > 40 and b_val < -1:
            tail = '——国家队托指数、市场缩量轮动，回调低吸优于追高'
        elif a_val > 40 and b_val > 1:
            tail = '——托盘与市场共振，风险偏好可适度放宽'
        elif a_val <= 0 and b_val < -1:
            tail = '——无托盘且市场走弱，宜收紧防守'
    return '综合 %s（%s）：' % (sc_str, vtxt) + '，'.join(parts) + tail + '。'

subs = []
subs.append({
    'key':'A','name':'宽基ETF净申购突变','weight':W['A'],'ready':a_ready,
    'value':a_val,'unit':'亿','detail':a_detail or 'etf_subscription_eastmoney.js 未就绪',
    'status':('✅活跃' if (a_val is not None and a_val>40) else ('🟡中性' if (a_val is not None and a_val>=0) else ('❌净赎回' if a_val is not None else '—未就绪')))
})
subs.append({
    'key':'B','name':'大金融相对强度','weight':W['B'],'ready':b_ready,
    'value':b_val,'unit':'%','detail':b_detail or 'SECTOR_RS.js 未就绪',
    'status':('✅强势' if (b_val is not None and b_val>1) else ('🟡中性' if (b_val is not None and b_val>=-1) else ('❌弱势' if b_val is not None else '—未就绪')))
})
subs.append({
    'key':'C','name':'大金融资金净流入','weight':W['C'],'ready':c_ready,
    'value':c_val,'unit':'亿','detail':c_detail or 'SECTOR_FUND_FLOW.js 未就绪',
    'status':('✅流入' if (c_val is not None and c_val>0) else ('❌流出' if (c_val is not None and c_val<0) else ('—未就绪' if c_val is None else '🟡持平')))
})
subs.append({
    'key':'D','name':'汇金持仓环比','weight':W['D'],'ready':False,
    'value':None,'unit':'','detail':'v8 无季报十大股东源 ⇒ 未接入（季报滞后1-3月，无法实时）',
    'status':'—未接入'
})

out = {
    'data_date': (e.get('data_date') if e else None) or bj_now().strftime('%Y-%m-%d'),
    'update_time': bj_now().strftime('%Y-%m-%d %H:%M:%S'),
    'score': score,
    'verdict': vtxt,
    'verdict_color': vcol,
    'ready_count': sum(1 for k in ['A','B','C'] if ready[k]),
    'subs': subs,
    'method': '3 子信号加权（缺失项权重重分）；宽基ETF净申购45% + 大金融相对强度35% + 大金融资金净流入20%；汇金持仓季报未接入。',
    'disclaimer': '代理推算·非汇金官方实时持仓；宽基ETF净申购为最强国资托盘指纹，但披露存 T+1 滞后，仅作 regime 参考，不构成交易建议。',
    'oneline': _oneline()
}

with open(os.path.join(ROOT, 'data/NATIONAL_TEAM.js'), 'w', encoding='utf-8') as f:
    f.write('window.NATIONAL_TEAM = ' + json.dumps(out, ensure_ascii=False, indent=2) + ';')

print('✅ NATIONAL_TEAM.js 生成： score=%s verdict=%s ready=%d/3' % (score, vtxt, out['ready_count']))
for s in subs:
    print('  [%s] %s w%s %s val=%s %s' % (s['key'], s['name'], s['weight'], s['status'], s['value'], s['detail']))
