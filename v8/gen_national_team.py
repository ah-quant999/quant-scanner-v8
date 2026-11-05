# -*- coding: utf-8 -*-
"""
v8/gen_national_team.py —— 「国家队活跃度」复合信号（盘后规则生成，落 data/NATIONAL_TEAM.js）

设计原则（主人铁律：绝不编造）：
  - 全部数值来自仓内真实数据源；
  - 任一子源缺失 ⇒ 该子项标「未接入/未就绪」，权重按比例重分给其余可用子项；
  - 本指标是「国家队托盘」的代理推算，卡面明确标注「代理·非实时」与「T+1 滞后说明」。
  - 汇金持仓环比（季报滞后约2年）胶囊已于 2026-11-04 应主人令移除：其权重本就 0%、与实时信号并列易误读，
    留卡无增量信息；历史数据仍存于 data/HUIJIN_HOLDINGS.js，需要时单独调用。

子信号（权重合计 100%，缺失项权重重分）：
  A. 宽基ETF净申购突变（40%）  ← ETF_SUBSCRIPTION_EASTMONEY.js（东财口径·股票型 top_sub 宽基净申购额；由 update_v8.py 派生）
  B. 大金融相对强度（30%）     ← SECTOR_RS.js（银行/证券/保险/多元金融 relative_5d 均值）
  C. 大金融资金净流入（15%）   ← SECTOR_FUND_FLOW.js（银行/证券 板块净流入合计）
  D. 宽基ETF放量异动（15%）    ← raw_data/broad_etf_volume.json（cloud_fetch_v8 f_broad_etf_volume·post_close 档：
                                  6 只头部宽基ETF 当日成交额/前20日均额 取最大倍数；仅大盘下跌日计护盘分，
                                  非下跌日按中性 50。push2his 为 cn-IP 硬约束源，17:20 selfhosted 落盘 →
                                  本生成器 20:50 消费；缺文件/过期 ⇒ D 未就绪、权重自动重分，不影响 A/B/C）
  （2026-11-05 主人令「找可靠新数据源，能说明国家队活跃度的」：D 路即「下跌日宽基ETF放量」——
    国家队护盘的经典公开指纹，数据可日频验证、无披露滞后；权重从 A/B/C 各让 5/5/5 而来。）

调度：.github/workflows/v8_national_team.yml 工作日 20:50 CST（GitHub Actions ubuntu-latest，
      Contents API 稳健推送）；18:20/19:20 两档盘后资金流链落盘后运行，上游未就绪则保留上版不写盘（宁缺勿错）。
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

# ── A. 宽基ETF净申购突变（东财五分类为主，老源「宽基」分类兜底，防新文件上线竞态/缺失） ──
# 🔴 2026-11-04 一劳永逸根治：原仅读 etf_subscription_eastmoney.js（小写孤儿名，云端从不产出/部署），
#   国家队活跃度(20:50) 跑批 ⇒ load() 返 None ⇒ A 标「未就绪」、权重45%丢失 ⇒ 分从70+掉到46.5。
#   根因：update_v8.py 实际派生的规范文件是大写 ETF_SUBSCRIPTION_EASTMONEY.js（已部署、含东财五分类），
#   生成器却读了一个从不存在的文件名。现修正为读规范大写文件；并加：(1) 稳定 code 集识别宽基
#   （防名称格式突变再翻车）；(2) 东财缺失/空 ⇒ 回落老源 ETF_NET_SUBSCRIPTION.js 的「宽基」分类
#   （始终存在），双源互备，永不再静默丢权重。
KW_BROAD = ['沪深300','中证500','中证1000','50ETF','科创50','创业板','中证A500','中证2000',
            '300ETF','华夏300','500ETF','1000ETF','A500','科创综']
BROAD_CODES = {'588000','510050','510300','510500','512100','159915','510310','510330',
               '512500','560010','588080','159919','510180','510880','515800','563000','561550','563300'}
a_val = None; a_detail = None; a_ready = False; a_src = ''
e = load('data/ETF_SUBSCRIPTION_EASTMONEY.js')
if e:
    stock = (e.get('categories') or {}).get('股票型') or {}
    subs = stock.get('top_sub') or []
    broad = [s for s in subs
             if any(k in (s.get('name') or '') for k in KW_BROAD) or (s.get('code') in BROAD_CODES)]
    net = sum((s.get('d_amount_yi') or 0) for s in broad)
    if broad:
        a_val = round(net, 1)
        a_detail = '宽基净申购 %.1f 亿（%d 只宽基ETF·东财五分类）' % (net, len(broad))
        a_ready = True
        a_src = 'eastmoney'
# 兜底：东财五分类缺失/空 ⇒ 回落老源 ETF_NET_SUBSCRIPTION.js 的「宽基」分类（始终存在）
if not a_ready:
    leg = load('data/ETF_NET_SUBSCRIPTION.js')
    if leg:
        bcat = (leg.get('categories') or {}).get('宽基') or {}
        bnet = bcat.get('net_amount_yi')
        bsubs = bcat.get('top_sub') or []
        if bnet is not None:
            a_val = round(float(bnet), 1)
            a_detail = '宽基净申购 %.1f 亿（兜底·老源宽基分类 %s 只）' % (a_val, bcat.get('count') or len(bsubs))
            a_ready = True
            a_src = 'legacy'
        elif bsubs:
            net = sum((s.get('d_amount_yi') or 0) for s in bsubs)
            a_val = round(net, 1)
            a_detail = '宽基净申购 %.1f 亿（兜底·老源宽基 top_sub）' % a_val
            a_ready = True
            a_src = 'legacy'

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

# ── D. 宽基ETF放量异动（护盘指纹，2026-11-05 主人令新接入）──────────
# 口径见文档头。仅大盘下跌日放量计护盘分（50 + (ratio-1)*33，ratio≥2.5≈满分），
#   非下跌日按中性 50 计（放量不判护盘，不编造语义）；数据缺失/过期 ⇒ 未就绪重分权。
d_val = None; d_detail = None; d_ready = False; d_base = None; d_down = None
bv = load('raw_data/broad_etf_volume.json')
# 跨零点口径与下方盘后闸门一致（GitHub schedule 拖过零点时按「昨日」判定，见闸门注释）
_nt_dt0 = bj_now()
_d_today = (_nt_dt0 - datetime.timedelta(days=1)).strftime('%Y-%m-%d') if _nt_dt0.hour < 7 else _nt_dt0.strftime('%Y-%m-%d')
if bv and bv.get('ratio_max') and bv.get('data_date') == _d_today:
    d_val = round(float(bv['ratio_max']), 2)
    d_down = bool(bv.get('down_day'))
    d_base = (50 + (d_val - 1) * 33.0) if d_down else 50.0
    d_detail = '%s 当日成交 %.1f 亿 = 20日均 %.2f×（%s）' % (
        bv.get('ratio_etf') or '宽基ETF',
        float(bv.get('amount_max_yi') or 0), d_val,
        '大盘%s' % (('跌 %.2f%%' % bv['index_chg_pct']) if bv.get('index_chg_pct') is not None else '下跌日') if d_down else '非下跌日·放量不判护盘')
    if bv.get('ok_count'):
        d_detail += '，覆盖 %d/6 只' % int(bv['ok_count'])
    d_ready = True

# ── 🛡️ 盘后新鲜度闸门（防假新鲜·主人令 09-23） ──────────────────────
# C 源 SECTOR_FUND_FLOW.js 必须为「今日收盘后（hour ≥ 15）」的盘后数据，否则整卡保留上版不写盘。
# 阈值说明：A 股 15:00 收盘，盘后资金流管线固定在 ~15:45 落戳，故以 ≥15（收盘后）判定，
#   原 ≥16 会把每天 15:45 的有效盘后数据误判为「未就绪」→ 卡永久停在旧版（实测卡在 10-20）。
# 手工急救可用 NT_FORCE=1 跳过闸门（会留下 source_time 审计痕迹）。
# GitHub schedule 可能拖数小时跨过北京零点（实测 2026-10-22 拖 5h 落到次日 01:39 CST），
# 跨零点时段（0-7 点）按「昨日」判定，否则盘后闸门永远过不了、卡永久停更。
_nt_now = bj_now()
_nt_today = (_nt_now - datetime.timedelta(days=1)).strftime('%Y-%m-%d') if _nt_now.hour < 7 else _nt_now.strftime('%Y-%m-%d')
_sf_ut = (sf or {}).get('update_time') or ''
_sf_ok = False
if _sf_ut:
    try:
        _sf_dt = datetime.datetime.strptime(_sf_ut[:16], '%Y-%m-%d %H:%M')
        _sf_ok = (_sf_dt.strftime('%Y-%m-%d') == _nt_today and _sf_dt.hour >= 15)
    except ValueError:
        _sf_ok = False
if not _sf_ok and os.environ.get('NT_FORCE') != '1':
    print('⏸️ NATIONAL_TEAM: 盘后资金流未就绪（SECTOR_FUND_FLOW.update_time=%r），'
          '保留上版不写盘（宁缺勿错）' % _sf_ut)
    sys.exit(0)
if not _sf_ok:
    print('⚠️ NATIONAL_TEAM: NT_FORCE=1 强制写盘（盘后资金流仍未就绪：%r）' % _sf_ut)

# ── 权重重分 + 计分 ─────────────────────────────────────────────────
W = {'A':40, 'B':30, 'C':15, 'D':15}  # 2026-11-05 主人令：接入 D 路（宽基ETF放量），A/B/C 各让 5 分
ready = {'A':a_ready, 'B':b_ready, 'C':c_ready, 'D':d_ready}
base = {'A':50 + (a_val or 0)/2, 'B':50 + (b_val or 0)*4, 'C':50 + (c_val or 0)/3, 'D':(d_base if d_base is not None else 50)}
# 仅对就绪项计分；缺失项权重按比例分给就绪项
tot_w = sum(W[k] for k in W if ready[k])
score = 0.0
for k in ['A','B','C','D']:
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
    if d_val is not None:
        if d_down and d_val >= 2:   parts.append('宽基ETF放量 %.2f×＝疑似托盘进场' % d_val)
        elif d_down and d_val >= 1.3: parts.append('下跌日宽基ETF温和放量 %.2f×' % d_val)
        elif d_down:               parts.append('下跌日宽基ETF未显著放量 %.2f×' % d_val)
        else:                      parts.append('非下跌日·放量信号中性 %.2f×' % d_val)
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
    'value':a_val,'unit':'亿','detail':a_detail or '宽基ETF数据源（东财/老源）均未就绪',
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
    'key':'D','name':'宽基ETF放量异动','weight':W['D'],'ready':d_ready,
    'value':d_val,'unit':'×','detail':d_detail or 'broad_etf_volume.json 缺失/过期（post_close 档未落盘）',
    'status':(('✅放量护盘' if (d_down and d_val>=2) else ('🟡温和放量' if (d_down and d_val>=1.3) else ('❌缩量' if d_down else '🟡中性'))) if (d_ready and d_val is not None) else '—未就绪')
})

out = {
    'data_date': (e.get('data_date') if e else None) or bj_now().strftime('%Y-%m-%d'),
    'update_time': bj_now().strftime('%Y-%m-%d %H:%M:%S'),
    'source_time': max(x for x in [(e or {}).get('update_time') or '',
                                   (rs or {}).get('update_time') or '',
                                   (sf or {}).get('update_time') or '',
                                   (bv or {}).get('update_time') or '']),
    'score': score,
    'verdict': vtxt,
    'verdict_color': vcol,
    'ready_count': sum(1 for k in ['A','B','C','D'] if ready[k]),
    'subs': subs,
    'method': '4 子信号加权（缺失项权重重分）；宽基ETF净申购40% + 大金融相对强度30% + 大金融资金净流入15% + 宽基ETF放量异动15%（2026-11-05 主人令新接入：下跌日头部宽基ETF成交额/20日均额，护盘公开指纹）。汇金持仓环比胶囊已于 2026-11-04 移除（季报滞后约2年、权重0%、无增量信息）。',
    'disclaimer': '代理推算·非汇金官方实时持仓；宽基ETF净申购为最强国资托盘指纹，披露存 T+1 滞后，如实标注，不构成交易建议。',
    'oneline': _oneline()
}

# ── 🛡️ 同源去重（防假新鲜·主人令 09-23）：四源 update_time 均未变 ⇒ 不写盘 ──
_prev_nt = load('data/NATIONAL_TEAM.js')
_prev_st = (_prev_nt or {}).get('source_time') or ''
if _prev_st and _prev_st == out['source_time']:
    if os.environ.get('NT_FORCE') == '1':
        print('⚠️ NATIONAL_TEAM: NT_FORCE=1 强制写盘（跳过同源去重）')
    else:
        print('⏸️ NATIONAL_TEAM: 四源 update_time 未变（%s），保留上版不写盘' % _prev_st)
        sys.exit(0)

with open(os.path.join(ROOT, 'data/NATIONAL_TEAM.js'), 'w', encoding='utf-8') as f:
    f.write('window.NATIONAL_TEAM = ' + json.dumps(out, ensure_ascii=False, indent=2) + ';')

print('✅ NATIONAL_TEAM.js 生成： score=%s verdict=%s ready=%d/4' % (score, vtxt, out['ready_count']))
for s in subs:
    print('  [%s] %s w%s %s val=%s %s' % (s['key'], s['name'], s['weight'], s['status'], s['value'], s['detail']))

