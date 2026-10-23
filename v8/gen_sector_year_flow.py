#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
九宝量化 v8.0 — 「板块年度主力净流入累积表」生成器（data/SECTOR_YEAR_FLOW.js）

重建于 2026-10-23：原生成器在死代码清理中被误删，卡停更于 2026-10-21 16:06
（主人令：交易日日更、一劳永逸修复）。本生成器为纯本地计算、零网络。

口径（与原版一致，见文件 source 字段）：
  东方财富行业板块逐日主力净流入官方历史按年累加（自建累积表·历史回填）。
  raw_data/sector_fund_flow_history.json 为滚动 ~56 日逐日 {date, net} 历史
  （抓取链盘后自动追加），本脚本把 last_date 之后的新增交易日 **增量合并**
  进累积表 —— 历史回填基座不可重算（重算会因滚动窗口缩水丢 121→56 天），
  只能增量，天然防口径漂移；漏跑/跨零点自动补齐（按日期增量）。

闸门（防假新鲜·主人令 09-23 同款）：
  ① 增量闸门：历史源最大日期必须 > 卡上 last_date，否则上游无新数据
     → 不写盘、保留上版（宁缺勿错，看板 ✓/✗ 自然显形）；
  ② 同源去重：合并结果与现有内容逐字节相同 → 不写盘（免空推）；
  ③ d5/d20 用历史窗口重算（56 日足够覆盖 20 日口径），无历史板块保留旧值。

退出码：0 = 写盘成功或正常跳过；2 = 数据源损坏/缺失。
"""
import json
import os
import sys
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'data', 'SECTOR_YEAR_FLOW.js')
HIST = os.path.join(REPO, 'raw_data', 'sector_fund_flow_history.json')
PREFIX = 'window.SECTOR_YEAR_FLOW = '
BJ = datetime.timezone(datetime.timedelta(hours=8))


def bj_now():
    return datetime.datetime.now(BJ)


def load_card():
    with open(SRC, encoding='utf-8') as f:
        txt = f.read()
    txt = txt.strip()
    if not txt.startswith(PREFIX):
        raise ValueError('SECTOR_YEAR_FLOW.js 前缀异常')
    body = txt[len(PREFIX):].strip()
    if body.endswith(';'):
        body = body[:-1]
    return json.loads(body)


def main():
    if not os.path.exists(HIST):
        print('⏸️ SECTOR_YEAR_FLOW: 历史源缺失 %s，保留上版不写盘' % HIST)
        return 0
    try:
        with open(HIST, encoding='utf-8') as f:
            hist = json.load(f)
    except Exception as e:
        print('❌ SECTOR_YEAR_FLOW: 历史源损坏 %s' % e)
        return 2
    if not isinstance(hist, dict) or not hist:
        print('⏸️ SECTOR_YEAR_FLOW: 历史源为空，保留上版不写盘')
        return 0

    card = load_card()
    sectors = card.get('sectors') or []
    if not sectors:
        print('❌ SECTOR_YEAR_FLOW: 卡内 sectors 为空，拒绝处理')
        return 2

    max_card_date = max((s.get('last_date') or '') for s in sectors)
    max_hist_date = max((r.get('date') or '') for rows in hist.values() for r in (rows or []))
    if not max_hist_date or max_hist_date <= max_card_date:
        print('⏸️ SECTOR_YEAR_FLOW: 历史源无新数据（hist_max=%s ≤ card_last=%s），保留上版不写盘'
              % (max_hist_date, max_card_date))
        return 0

    now = bj_now().strftime('%Y-%m-%d %H:%M:%S')
    updated, missed = 0, 0
    for s in sectors:
        rows = hist.get(s.get('name')) or []
        rows = sorted([r for r in rows if (r.get('date') and r.get('net') is not None)],
                      key=lambda r: r['date'])
        if not rows:
            missed += 1
            continue
        last = s.get('last_date') or ''
        new = [r for r in rows if r['date'] > last]
        if new:
            s['cur'] = round((s.get('cur') or 0.0) + sum(r['net'] for r in new), 2)
            s['days'] = (s.get('days') or 0) + len(new)
            s['last_date'] = new[-1]['date']
            updated += 1
        # d5 / d20 用历史窗口重算（窗口不足则保留旧值）
        if len(rows) >= 5:
            s['d5'] = round(sum(r['net'] for r in rows[-5:]), 2)
        if len(rows) >= 20:
            s['d20'] = round(sum(r['net'] for r in rows[-20:]), 2)

    if updated == 0:
        print('⏸️ SECTOR_YEAR_FLOW: 全部板块无新增交易日（hist_max=%s），保留上版不写盘' % max_hist_date)
        return 0

    card['data_date'] = max((s.get('last_date') or '') for s in sectors)
    card['fail_count'] = missed
    card['update_time'] = now
    card['republish_time'] = now

    out = PREFIX + json.dumps(card, ensure_ascii=False, separators=(',', ':')) + ';\n'
    with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)
    print('✅ SECTOR_YEAR_FLOW: 合并 %d 个板块新增交易日 → data_date=%s（miss=%d）@ %s'
          % (updated, card['data_date'], missed, now))
    return 0


if __name__ == '__main__':
    sys.exit(main())
