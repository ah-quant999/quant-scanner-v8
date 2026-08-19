#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算法调度时间守卫 — 防"数据未就绪就跑算法"错配

🛡 2026-08-19 阿狸咪根治（主人令）：
小九 16:18 在单位机本地手动跑了 final_recommend，但港股 16:00 收市后还要 16:10-16:30
数据完整同步，结果 17 张盘后/选股卡数据不准。主人令「所有算法链全部安排在数据全部
就绪后跑」。本模块给关键算法入口加硬守门：早于数据就绪时间直接 sys.exit(1)。

各市场数据就绪时间（CST）：
    A股: 15:30 后（集合竞价 15:00-15:30 完成；数据源 15:30-16:00 陆续同步）
    港股: 16:30 后（16:00 收市 + 16:10 收盘竞价 + 16:30 数据完整；eastmoney push2 16:30 才全量）
    LHB: 17:30 后（17:00 发布 + 30 分钟缓冲，部分券源 17:30 才齐）
    美股: 06:00 后（22:30-05:00 盘前数据 + 06:00 后数据完整）

用法：
    # 算法入口加：
    from utils.time_gate import check, markets_required
    check(markets_required(['hk', 'lhb']))  # 港股 + LHB 都就绪才跑

    # workflow_dispatch 手动触发可加 bypass：
    if not os.environ.get('TIME_GATE_BYPASS'):
        check(markets_required(['hk']))
"""
import os
import sys
import datetime
import logging

# 各市场数据就绪时间（CST, 24h 格式）
MARKET_READY = {
    'a': (15, 30),   # A股 15:30
    'hk': (16, 30),  # 港股 16:30
    'lhb': (17, 30), # 龙虎榜 17:30
    'us': (6, 0),    # 美股盘前 06:00
}

# 依赖哪个市场的中文说明
MARKET_LABEL = {
    'a': 'A股',
    'hk': '港股',
    'lhb': '龙虎榜',
    'us': '美股',
}


def _now_cst():
    return datetime.datetime.now()


def markets_required(markets):
    """返回 markets 列表"""
    return list(markets)


def check(markets, by='unknown'):
    """检查所有 markets 是否都过了数据就绪时间
    markets: list of 'a'/'hk'/'lhb'/'us'
    by: 触发方（用于日志）
    早于就绪时间：sys.exit(1) + 红字报错
    """
    if os.environ.get('TIME_GATE_BYPASS') == '1':
        logging.warning(f'[time_gate] BYPASS 已设置，跳过时间守门（{markets}）')
        return
    now = _now_cst()
    wd = now.weekday()  # 0=Mon..6=Sun
    # 周末不交易：仅 a/hk/lhb 周末无数据，但 us 周末有
    if wd >= 5 and 'us' not in markets:
        # A股/港股/LHB 周末无数据：跳过（不是时间门问题）
        logging.info(f'[time_gate] 周末，跳过 {markets} 守门')
        return
    for m in markets:
        if m not in MARKET_READY:
            logging.warning(f'[time_gate] 未知市场 {m}，跳过')
            continue
        hh, mm = MARKET_READY[m]
        ready = now.hour * 60 + now.minute >= hh * 60 + mm
        if not ready:
            print(f'\n🚫 [time_gate] {MARKET_LABEL[m]} 数据未就绪（需 ≥ {hh:02d}:{mm:02d} CST，当前 {now:%H:%M}）', file=sys.stderr)
            print(f'   触发方: {by}', file=sys.stderr)
            print(f'   等待 markets: {", ".join(MARKET_LABEL[x] for x in markets)}', file=sys.stderr)
            print(f'   绕开（应急）: TIME_GATE_BYPASS=1 环境变量', file=sys.stderr)
            sys.exit(1)
    logging.info(f'[time_gate] 守门通过：{markets}（{now:%H:%M}）')


if __name__ == '__main__':
    # 单元测试：模拟时间
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--markets', default='hk,lhb', help='依赖市场（逗号分隔）')
    args = ap.parse_args()
    mks = args.markets.split(',')
    check(mks, by='cli-test')
    print(f'✅ {mks} 都已就绪（{_now_cst():%H:%M}）')